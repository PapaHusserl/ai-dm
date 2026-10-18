from typing import NamedTuple

from ai_dm.combat.engine import participant_name
from ai_dm.rules.goals import add_goal
from ai_dm.rules.knowledge import MET, fact, is_near, mentions, remember_fact, rename_met
from ai_dm.rules.npc_memory import remember
from ai_dm.rules.npc_names import name_hidden, shown_name
from ai_dm.rules.uniqueness import id_taken
from ai_dm.state.relations import NpcEvent
from ai_dm.state.world import NPC

# исходы боя, после которых выжившие остаются в мире
FIGHT_OUTCOMES = ("victory", "fled", "ended_by_master")
# вид выжившего -> (вид события памяти, текст)
MEMORY = {
    "defected": ("spared", "перешёл на сторону героя в бою"),
    "surrendered": ("spared", "сдался герою в бою"),
    "spared": ("spared", "герой пощадил в бою"),
    "fled": ("other", "бежал из боя"),
}


LIFE_DEBT_TEXT = "обязан герою жизнью: перешёл на его сторону в бою"
GRATITUDE_TEXT = "благодарен герою: тот пощадил его в бою"
REVENGE_TEXT = "хочет отомстить герою за поражение в бою"


class Survivor(NamedTuple):
    part: object
    kind: str
    label: str
    group: str


def defect_flag(part):
    return next((e for e in part.creature.active_effects if e.id == "parley_defected"), None)


def kind_of(part, outcome):
    # вид выжившего или None; зовётся до finish_combat (тот снимает метки переговоров)
    if defect_flag(part) is not None:
        return None if part.status == "dead" else "defected"
    if part.side != "enemies":
        return None
    if part.status in ("surrendered", "fled"):
        return part.status
    if part.status == "down" or (part.status == "active" and outcome == "ended_by_master"):
        return "spared"
    return None


def classify(bundle, hero) -> list[Survivor]:
    state = bundle.session.active_combat
    if state.outcome not in FIGHT_OUTCOMES or hero.status == "dead":
        return []
    heroes = {hero.id: hero}
    found = []
    for part in state.participants:
        if part.creature is None or part.monster_id is None or part.ref in bundle.world.npcs:
            continue
        kind = kind_of(part, state.outcome)
        if kind is not None:
            label = participant_name(state, heroes, part.ref)
            found.append(Survivor(part, kind, label, group_of(part, kind)))
    return found


def group_of(part, kind) -> str:
    # исходная группа перебежчика -- из метки (group_id уже группа героя)
    if kind == "defected":
        return defect_flag(part).params.get("group", part.group_id)
    return part.group_id


def free_id(bundle, monster_id) -> str:
    prefix = f"{monster_id}_t{bundle.session.turn_seq}_"
    number = 1
    while id_taken(bundle.world, bundle.heroes, f"{prefix}{number}"):
        number += 1
    return f"{prefix}{number}"


def landing(world, hero, kind):
    # бежавший уходит в соседнюю локацию; остальные остаются там, где герой
    place = world.locations.get(hero.location_id)
    if kind != "fled" or place is None:
        return hero.location_id
    # связи в любую сторону, первая по id (как nearby_locations мастера)
    near = {c.to for c in place.connections}
    near |= {o.id for o in world.locations.values() if any(c.to == place.id for c in o.connections)}
    near &= set(world.locations)
    return min(near) if near else hero.location_id


def make_npc(bundle, hero, survivor, cfg) -> NPC:
    part = survivor.part
    return NPC(
        id=free_id(bundle, part.monster_id), name=survivor.label, named=False,
        means=[survivor.label], combat={"monster_id": part.monster_id, "label": survivor.label},
        creature=part.creature.model_copy(deep=True),
        equipment=part.equipment and part.equipment.model_copy(deep=True), groups=[survivor.group],
        location_id=landing(bundle.world, hero, survivor.kind),
        attitude=start_attitude(cfg.survivors, survivor.kind), origin="engine",
    )


def start_attitude(config, kind) -> int:
    by_kind = {
        "defected": config.defected, "surrendered": config.surrendered,
        "spared": config.spared, "fled": config.fled,
    }
    return by_kind[kind]


def vengeful(npc, cfg) -> bool:
    return npc.attitude <= cfg.survivors.revenge_attitude_max


def remember_fight(bundle, hero, npc, survivor, cfg) -> None:
    # события боя пишет движок (пересмотр Q7 Ж0); нет сцены -- без памяти
    scene = bundle.session.current_scene
    if scene is not None:
        kind, text = MEMORY[survivor.kind]
        event = NpcEvent(kind=kind, turn_seq=bundle.session.turn_seq, text=text)
        remember(npc, scene, event, cfg.npc_memory)
    now_s = bundle.world.clock.now_s
    if survivor.kind == "defected":
        add_goal(npc, "life_debt", hero.id, LIFE_DEBT_TEXT, now_s)
    elif survivor.kind == "spared":
        add_goal(npc, "gratitude", hero.id, GRATITUDE_TEXT, now_s)
    elif survivor.kind in ("fled", "surrendered") and vengeful(npc, cfg):
        add_goal(npc, "revenge", hero.id, REVENGE_TEXT, now_s)


def materialize(bundle, hero, survivors, cfg) -> list[NPC]:
    # выжившие -> world.npcs; зовётся после note_combat (тот пропускает участников из npcs)
    created = []
    for survivor in survivors:
        npc = make_npc(bundle, hero, survivor, cfg)
        bundle.world.npcs[npc.id] = npc
        remember_fight(bundle, hero, npc, survivor, cfg)
        note_met(bundle, hero, npc, cfg)
        created.append(npc)
    return created


def note_met(bundle, hero, npc, cfg) -> None:
    # выжившие знакомы герою по виду: запись о знакомстве с меткой вместо имени
    text = MET + shown_name(npc)
    remember_fact(hero, fact("npc", npc.id, text, "seen", bundle.world.clock.now_s), cfg.knowledge)


def reveal_names(hero, world, text) -> None:
    # имя выжившего открывается, когда придуманное рассказчиком имя прозвучало в тексте хода
    low = text.lower()
    for npc in sorted(world.npcs.values(), key=lambda n: n.id):
        if not name_hidden(npc) or npc.name == shown_name(npc) or not is_near(npc, hero):
            continue
        if mentions(npc.name.lower(), low):
            npc.known_name = npc.name
            rename_met(hero, npc)
