from pydantic import BaseModel, Field

from ai_dm.rules.secrets import hidden_secrets
from ai_dm.rules.triggers_eval import Truth, evaluate, is_ready
from ai_dm.state.triggers import Condition

OWNER_RANK = {"god": 0, "faction": 1, "npc": 2, "hero": 3}


class Candidate(BaseModel):
    # kind: verdict -- вердикт world по нарративному остатку; act -- сработал, исполнить then
    ref: str
    kind: str
    owner_kind: str
    owner_id: str
    owner_name: str
    motive: str = ""
    means: list[str] = Field(default_factory=list)
    # id триггера или секрета
    item_id: str
    condition_text: str = ""
    then: str = ""
    residual: Condition | None = None


def trigger_ref(owner_id, trigger_id) -> str:
    return f"trigger:{owner_id}:{trigger_id}"


def secret_ref(npc_id, secret_id) -> str:
    return f"secret:{npc_id}:{secret_id}"


def current_hero(bundle):
    for hero in bundle.heroes:
        if hero.id == bundle.manifest.current_hero_id:
            return hero
    return None


def god_due(god, bundle) -> bool:
    # бог проверяется реже (ТЗ 4.2): первая проверка сразу, дальше -- через check_every_days
    # после предыдущей проверки (со срабатыванием или без)
    last = bundle.world.sim.god_checked_s.get(god.id)
    if last is None:
        return True
    return bundle.world.clock.now_s - last >= god.check_every_days * 86400


def owners(bundle) -> list[tuple]:
    # (вид, владелец, герой для условий): боги, фракции, живые NPC, активные герои; внутри -- по id
    world = bundle.world
    main = current_hero(bundle)
    result = []
    for god in sorted(world.pantheon.values(), key=lambda g: g.id):
        if god.status == "alive" and god_due(god, bundle):
            result.append(("god", god, main))
    for faction in sorted(world.factions.values(), key=lambda f: f.id):
        result.append(("faction", faction, main))
    for npc in sorted(world.npcs.values(), key=lambda n: n.id):
        if npc.status == "alive":
            result.append(("npc", npc, main))
    for hero in sorted(bundle.heroes, key=lambda h: h.id):
        if hero.status == "active":
            result.append(("hero", hero, hero))
    return result


def make_candidate(
    kind, owner_kind, owner, item_id, ref, *, condition_text="", then="", residual=None,
):
    return Candidate(
        ref=ref, kind=kind, owner_kind=owner_kind, owner_id=owner.id, owner_name=owner.name,
        motive=owner.motive, means=list(owner.means), item_id=item_id,
        condition_text=condition_text, then=then, residual=residual,
    )


def sort_key(candidate):
    if candidate.kind == "act":
        group = 2
    elif candidate.ref.startswith("secret:"):
        group = 1
    else:
        group = 0
    return (group, OWNER_RANK[candidate.owner_kind], candidate.owner_id, candidate.item_id)


def verdict_candidates(bundle, owner_list=None) -> list[Candidate]:
    # чистая функция: триггеры с выполненной структурной частью и нарративным остатком,
    # затем секреты NPC закрытой сцены; состояние не меняет
    world = bundle.world
    now_s = world.clock.now_s
    result = []
    if owner_list is None:
        owner_list = owners(bundle)
    for kind, owner, hero in owner_list:
        for trigger in owner.opportunity:
            if not is_ready(trigger, now_s):
                continue
            ev = evaluate(trigger.if_, world, hero)
            if ev.truth != Truth.NEEDS_NARRATIVE:
                continue
            result.append(
                make_candidate(
                    "verdict", kind, owner, trigger.id, trigger_ref(owner.id, trigger.id),
                    condition_text="; ".join(ev.narrative), then=trigger.then,
                    residual=ev.residual,
                )
            )
    # секреты NPC закрытой сцены (локация сцены, не героя: при location_changed герой уже ушёл)
    scene = bundle.session.current_scene
    main = current_hero(bundle)
    if scene is not None:
        for npc, secret in hidden_secrets(world, scene.location_id):
            if secret.narrative_ok:
                continue
            ev = evaluate(secret.reveal_if, world, main)
            if ev.truth != Truth.NEEDS_NARRATIVE:
                continue
            result.append(
                make_candidate(
                    "verdict", "npc", npc, secret.id, secret_ref(npc.id, secret.id),
                    condition_text="; ".join(ev.narrative), residual=ev.residual,
                )
            )
    return sorted(result, key=sort_key)
