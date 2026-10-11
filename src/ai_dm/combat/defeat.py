from typing import Literal

from pydantic import BaseModel, ConfigDict

from ai_dm.content.models.common import Ability, Skill
from ai_dm.core.dice import roll_dice
from ai_dm.core.events import DomainEvent
from ai_dm.rules import divine
from ai_dm.rules.auto_flags import apply_events
from ai_dm.rules.custom_items import hand_over
from ai_dm.rules.exhaustion import add_exhaustion
from ai_dm.rules.healing import remove_zero_hp_unconscious
from ai_dm.rules.inventory import pick_valuables, remove_item
from ai_dm.rules.results import Rejected
from ai_dm.state.creature import DeathSaves
from ai_dm.state.hero import Equipped
from ai_dm.state.triggers import Trigger
from ai_dm.state.world import ItemHolder

CONSEQUENCES = ("capture", "rob", "left_to_die", "scar", "exhaustion", "debt")


class DefeatParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lair_location_id: str | None = None
    rob_items: int | None = None
    scar_ability: Ability | None = None
    scar_skill: Skill | None = None
    scar_text: str = ""
    debt_to: str | None = None
    debt_text: str = ""


class DefeatResult(BaseModel):
    status: Literal["applied", "clamped"]
    events: list[DomainEvent]
    notes: list[str] = []


def invalid(reason) -> Rejected:
    return Rejected(reason=reason, report_tag="invalid-defeat")


def lair_of(state, params) -> str | None:
    group = state.groups.get(state.defeat_group_id)
    if group is not None and group.lair_location_id is not None:
        return group.lair_location_id
    return params.lair_location_id


def creditor_of(state, params) -> str | None:
    if params.debt_to is not None:
        return params.debt_to
    group = state.groups.get(state.defeat_group_id)
    if group is None:
        return None
    # лидер-перебежчик (group_id сменился) кредитором не бывает
    leader = [p for p in state.participants if p.ref == group.leader_id][0]
    if leader.group_id != state.defeat_group_id:
        return None
    return group.leader_id


def check_request(state, consequences, params) -> Rejected | None:
    # всё проверяется до первого изменения: применение атомарно
    if not 1 <= len(consequences) <= 2:
        return invalid("нужно одно или два последствия")
    for kind in consequences:
        if kind not in CONSEQUENCES:
            return invalid(f"неизвестное последствие: {kind!r}")
    if len(set(consequences)) != len(consequences):
        return invalid("последствия не должны повторяться")
    if "scar" in consequences and (params.scar_ability is None) == (params.scar_skill is None):
        return invalid("шрам: нужна ровно одна из scar_ability / scar_skill")
    if "capture" in consequences and lair_of(state, params) is None:
        return invalid("плен: неизвестно логово")
    if "debt" in consequences and creditor_of(state, params) is None:
        return invalid("долг: неизвестен кредитор")
    return None


def robber_of(state, world, hero, registry) -> tuple[str, str, str]:
    # кто забрал предмет: (вид, ref, подпись) -- лидер группы поражения или место потери
    group = state.groups.get(state.defeat_group_id)
    if group is None:
        return "location", hero.location_id, "потеряно в пути"
    leader_id = group.leader_id
    if leader_id in world.npcs:
        return "npc", leader_id, world.npcs[leader_id].name
    leaders = [p for p in state.participants if p.ref == leader_id]
    if not leaders:
        return "location", hero.location_id, "потеряно в пути"
    leader = leaders[0]
    name = leader.name or registry.get("monster", leader.monster_id).name
    return "band", leader_id, f"{name}, банда"


def do_capture(state, params, world, hero, registry, cfg, rng, notes):
    lair = lair_of(state, params)
    # кастомные предметы (и сюжетные, и нет) уходят в тайник логова, SRD-предметы очищаются
    stacks = {}
    for entry in hero.inventory:
        if entry.item_id in world.custom_items:
            stacks.setdefault(entry.item_id, []).append(entry)
    for item_id, group in stacks.items():
        hand_over(world, item_id, ItemHolder(
            kind="location", ref=lair, label="тайник логова", location_id=lair,
            since_s=world.clock.now_s, qty=sum(e.qty for e in group), cost_cp=group[0].cost_cp,
        ))
        notes.append(f"Отобрано: {world.custom_items[item_id].name} — тайник логова")
    hero.location_id = lair
    hero.inventory = []
    hero.equipped = Equipped()
    return "applied", [DomainEvent(type="location_visited", data={"id": lair})]


def do_rob(state, params, world, hero, registry, cfg, rng, notes):
    taken = hero.money_cp * cfg.defeat.robbery_gold_percent // 100
    count = params.rob_items
    if count is None:
        count = rng.randint(1, 2)
    items = pick_valuables(hero, registry, rng, count)
    hero.money_cp -= taken
    for item in items:
        remove_item(hero, item.item_id, cost_cp=item.cost_cp, quality=item.quality)
    # отобранные сюжетные предметы мир помнит: у кого они теперь
    custom_taken = {}
    for item in items:
        if item.item_id in world.custom_items:
            custom_taken.setdefault(item.item_id, []).append(item)
    kind, ref, label = robber_of(state, world, hero, registry)
    for item_id, group in custom_taken.items():
        hand_over(world, item_id, ItemHolder(
            kind=kind, ref=ref, label=label, location_id=lair_of(state, params) or hero.location_id,
            since_s=world.clock.now_s, qty=len(group), cost_cp=group[0].cost_cp,
        ))
        notes.append(f"Отобрано: {world.custom_items[item_id].name} — у {label}")
    if taken == 0 and not items:
        return "clamped", []
    return "applied", []


def do_left_to_die(state, params, world, hero, registry, cfg, rng):
    creature = hero.creature
    creature.hp_current = min(creature.hp_max, cfg.defeat.left_to_die_hp)
    creature.death_saves = DeathSaves()
    remove_zero_hp_unconscious(creature)
    hours = roll_dice(cfg.defeat.left_to_die_hours_dice, rng).total
    world.clock.advance(hours * 3600)
    return "applied", []


def do_scar(state, params, world, hero, registry, cfg, rng):
    if params.scar_ability is not None:
        hero.sheet.abilities[params.scar_ability] -= 1
    hero.scars.append(params.scar_text)
    return "applied", []


def do_exhaustion(state, params, world, hero, registry, cfg, rng, chapter_id="", scene_id=""):
    def intervene(target):
        return divine.try_intervention(target, world, rng, cfg, chapter_id, scene_id)

    add_exhaustion(hero, 1, now_s=world.clock.now_s, cause="goal", intervene=intervene)
    return "applied", []


def do_debt(state, params, world, hero, registry, cfg, rng):
    creditor = creditor_of(state, params)
    world.flags[f"debt:{hero.id}"] = creditor
    npc = world.npcs.get(creditor)
    if npc is not None:
        text = params.debt_text or f"{hero.name} должен услугу"
        trigger = Trigger.model_validate(
            {"id": f"debt_{hero.id}", "if": {"narrative": text}, "then": text}
        )
        npc.opportunity.append(trigger)
    return "applied", []


DO = {
    "capture": do_capture, "rob": do_rob, "left_to_die": do_left_to_die, "scar": do_scar,
    "exhaustion": do_exhaustion, "debt": do_debt,
}


def apply_defeat_outcome(
    state, consequences, params, *, world, hero, registry, cfg, rng, chapter_id="", scene_id=""
) -> DefeatResult | Rejected:
    bad = check_request(state, consequences, params)
    if bad is not None:
        return bad
    status = "applied"
    events = []
    notes = []
    for kind in consequences:
        if kind in ("capture", "rob"):
            done, more = DO[kind](state, params, world, hero, registry, cfg, rng, notes)
        elif kind == "exhaustion":
            done, more = do_exhaustion(
                state, params, world, hero, registry, cfg, rng, chapter_id, scene_id
            )
        else:
            done, more = DO[kind](state, params, world, hero, registry, cfg, rng)
        if done == "clamped":
            status = "clamped"
        events += more
        events.append(DomainEvent(type="defeat_applied", data={"consequence": kind}))
    apply_events(world, events)
    return DefeatResult(status=status, events=events, notes=notes)
