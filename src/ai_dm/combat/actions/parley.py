from ai_dm.combat import disarm
from ai_dm.combat.controllers import EngineTactics
from ai_dm.combat.zones import distance
from ai_dm.core.events import DomainEvent
from ai_dm.rules.checks import skill_check
from ai_dm.rules.names import SKILL_NAMES
from ai_dm.rules.results import Rejected
from ai_dm.state.creature import ActiveEffect, Expiry

# навык -> какие исходы он допускает (SRD 5.2: Influence); «ссорится» отложен (BACKLOG)
ALLOWED = {
    "intimidation": ("surrender", "flee"),
    "persuasion": ("surrender", "flee", "defect"),
    "deception": ("flee", "waver"),
}
# что предлагает меню героя: одна строка на навык и цель, остальное -- фразой
MENU = (("intimidation", "surrender"), ("persuasion", "defect"), ("deception", "flee"))
OUTCOME_WORDS = {
    "surrender": "сдаться", "flee": "отступить", "defect": "перейти на вашу сторону",
    "waver": "заколебаться",
}
# метки на существе цели; на NPC живут до конца боя (убирает game/combat_flow)
FLAG_IDS = (
    "parley_tried", "wavering", "parley_defected", "parley_offended", "parley_advantage",
)


def rejected(reason) -> Rejected:
    return Rejected(reason=reason, report_tag=None)


def leads(engine, leader_ref, group_id) -> bool:
    # лидер боеспособен и всё ещё в своей группе (перебежчик группу не представляет)
    return engine.is_capable(leader_ref) and engine.part(leader_ref).group_id == group_id


def has_flag(engine, ref, flag_id) -> bool:
    return any(e.id == flag_id for e in engine.creature(ref).active_effects)


def choice_problem(engine, ref, skill, outcome):
    # причина отказа по самому выбору (кто, навык, исход, действие) или None
    p = engine.part(ref)
    checks = (
        ("not_a_hero", ref not in engine.heroes),
        ("unknown_skill", skill not in ALLOWED),
        ("unknown_outcome", outcome not in OUTCOME_WORDS),
        ("outcome_not_allowed", outcome not in ALLOWED.get(skill, ())),
        ("not_available", p.status != "active" or not p.turn.action),
    )
    for reason, bad in checks:
        if bad:
            return reason
    return None


def target_problem(engine, ref, target):
    # цель из другой стороны и боеспособна
    sides = {q.ref: q.side for q in engine.state.participants}
    if target is None or sides.get(target) is None or sides[target] == engine.part(ref).side:
        return "target_required"
    if not engine.is_capable(target):
        return "target_not_active"
    return None


def mind_problem(engine, ref, target):
    # цель разумна и слышит: своя или соседняя зона
    cfg = engine.cfg.parley
    if not engine.monster_of(target):
        return "not_sentient"
    monster = engine.monster(target)
    if monster.abilities["int"] <= cfg.min_int or monster.creature_type in cfg.immune_types:
        return "not_sentient"
    if distance(engine.state.zones, engine.part(ref).zone_id, engine.part(target).zone_id) > 1:
        return "out_of_hearing"
    return None


def history_problem(engine, outcome, target):
    # одна попытка на цель за бой; ключевой NPC не переходит
    if has_flag(engine, target, "parley_tried"):
        return "already_tried"
    npc = engine.world.npcs.get(target)
    if outcome == "defect" and npc is not None and npc.key:
        return "key_npc_cannot_defect"
    return None


def check_request(engine, ref, skill, outcome, target):
    # возвращает Rejected или None; ничего не бросает и не тратит
    reason = choice_problem(engine, ref, skill, outcome)
    if reason is None:
        reason = target_problem(engine, ref, target)
    if reason is None:
        reason = mind_problem(engine, ref, target)
    if reason is None:
        reason = history_problem(engine, outcome, target)
    if reason is None:
        return None
    return rejected(reason)


def parley_dc(engine, ref, target, skill, outcome):
    # (СЛ, режим броска, слагаемые для лога); режим: normal | disadvantage
    cfg = engine.cfg.parley
    state = engine.state
    monster = engine.monster(target)
    base = cfg.base_dc
    label = "база"
    if monster.abilities["int"] > base:
        base = monster.abilities["int"]
        label = "Инт цели"
    parts = [(label, base)]
    mode = "normal"
    npc = engine.world.npcs.get(target)
    if npc is None or npc.attitude <= cfg.hostile_attitude:
        mode = "disadvantage"
    elif npc.attitude >= cfg.friendly_attitude:
        parts.append(("дружелюбен", -cfg.friendly_bonus))
    creature = engine.creature(target)
    if creature.hp_current * 4 <= creature.hp_max:
        parts.append(("HP ≤ 25%", -cfg.hp_quarter_bonus))
    elif creature.hp_current * 2 <= creature.hp_max:
        parts.append(("HP ≤ 50%", -cfg.hp_half_bonus))
    if has_flag(engine, target, "disarmed"):
        parts.append(("обезоружен", -cfg.disarmed_bonus))
    target_part = engine.part(target)
    group = [q for q in state.participants if q.group_id == target_part.group_id]
    out = [q for q in group if q.status != "active"]
    if len(out) * 2 >= len(group):
        parts.append(("потери группы", -cfg.losses_bonus))
    # лидер, перешедший на сторону героев, для группы выбыл (его group_id уже другой)
    leader = engine.part(state.groups[target_part.group_id].leader_id)
    if leader.status != "active" or leader.group_id != target_part.group_id:
        parts.append(("лидер выбыл", -cfg.leader_down_bonus))
    if skill == "intimidation":
        mine = [q for q in state.participants if q.side == engine.part(ref).side]
        theirs = [q for q in state.participants if q.side == target_part.side]
        if sum(engine.is_capable(q.ref) for q in mine) >= 2 * sum(
            engine.is_capable(q.ref) for q in theirs
        ):
            parts.append(("перевес героев", -cfg.overwhelm_bonus))
    if outcome == "defect":
        parts.append(("переход", cfg.defect_penalty))
    if outcome == "waver":
        parts.append(("колебание", -cfg.waver_bonus))
    if npc is not None and npc.key:
        parts.append(("ключевой", cfg.key_penalty))
    return sum(value for _, value in parts), mode, parts


def parts_text(parts) -> str:
    texts = [f"{parts[0][0]} {parts[0][1]}"]
    texts += [f"{label} {value:+d}" for label, value in parts[1:]]
    return ", ".join(texts)


def menu_entries(engine, ref) -> list:
    # (навык, исход, цель, СЛ, режим) для строк меню, пока переговоры возможны
    result = []
    for q in engine.state.participants:
        for skill, outcome in MENU:
            if check_request(engine, ref, skill, outcome, q.ref) is not None:
                continue
            dc, mode, _ = parley_dc(engine, ref, q.ref, skill, outcome)
            result.append((skill, outcome, q.ref, dc, mode))
    return result


def resolve(engine, ref, skill, outcome, target) -> list[DomainEvent]:
    # запрос уже прошёл check_request: тратим действие, бросаем, применяем исход
    engine.part(ref).turn.action = False
    engine.creature(target).active_effects.append(
        ActiveEffect(id="parley_tried", source=ref, kind="flag")
    )
    dc, mode, parts = parley_dc(engine, ref, target, skill, outcome)
    label = ""
    if mode == "disadvantage":
        label = "враждебен"
    result = skill_check(
        engine.heroes[ref], engine.registry, engine.rng, skill, dc=dc,
        base_adv=mode, base_adv_label=label,
    )
    engine.log(
        f"{engine.name(ref)}: переговоры с {engine.name(target)} "
        f"({SKILL_NAMES[skill]}, цель: {OUTCOME_WORDS[outcome]}), "
        f"СЛ {dc} [{parts_text(parts)}]: {result.log.text}"
    )
    if result.outcome == "success":
        return APPLY[outcome](engine, ref, target)
    if outcome == "defect" and dc - result.total >= engine.cfg.parley.offended_margin:
        offend(engine, ref, target)
    return []


def parley(engine, ref, skill, outcome, target=None):
    bad = check_request(engine, ref, skill, outcome, target)
    if bad is not None:
        return bad
    return engine.finish(resolve(engine, ref, skill, outcome, target))


def perform(engine, ref, option) -> list[DomainEvent]:
    params = option.params
    return resolve(engine, ref, params["skill"], params["outcome"], params["target"])


def offend(engine, ref, target) -> None:
    # грубый провал «переходи к нам»: следующая атака цели по герою с преимуществом;
    # метка parley_offended нужна и после боя (отношение NPC падает)
    creature = engine.creature(target)
    creature.active_effects.append(ActiveEffect(id="parley_offended", source=ref, kind="flag"))
    creature.active_effects.append(
        ActiveEffect(
            id="parley_advantage", source=ref, kind="modifier",
            params={"target": "attack_roll", "mode": "advantage", "against": ref, "consume": True},
            expires=Expiry(kind="end_of_turn", owner=target),
        )
    )
    engine.log(f"  {engine.name(target)} оскорблён")


def apply_surrender(engine, ref, target) -> list[DomainEvent]:
    engine.part(target).status = "surrendered"
    engine.log(f"  {engine.name(target)} сдаётся")
    disarm.surrender_drop(engine, target)
    return [DomainEvent(type="participant_surrendered", data={"id": target})]


def apply_flee(engine, ref, target) -> list[DomainEvent]:
    engine.part(target).status = "fled"
    engine.log(f"  {engine.name(target)} уходит")
    return [DomainEvent(type="participant_fled", data={"id": target})]


def apply_defect(engine, ref, target) -> list[DomainEvent]:
    p = engine.part(target)
    # исходная группа остаётся в метке: по ней перебежчик станет NPC мира
    flag = ActiveEffect(id="parley_defected", source=ref, kind="flag", params={"group": p.group_id})
    p.side = "heroes"
    p.controller = "engine"
    p.group_id = engine.part(ref).group_id
    p.intent = None
    engine.controllers[target] = EngineTactics(engine)
    engine.creature(target).active_effects.append(flag)
    engine.log(f"  {engine.name(target)} переходит на вашу сторону")
    return [DomainEvent(type="participant_defected", data={"id": target})]


def apply_waver(engine, ref, target) -> list[DomainEvent]:
    engine.creature(target).active_effects.append(
        ActiveEffect(id="wavering", source=ref, kind="flag")
    )
    engine.log(f"  {engine.name(target)} колеблется")
    return []


APPLY = {
    "surrender": apply_surrender, "flee": apply_flee, "defect": apply_defect,
    "waver": apply_waver,
}


def lose_turn(engine, ref) -> bool:
    # колеблющийся теряет ровно один ход: метка снимается
    creature = engine.creature(ref)
    if not any(e.id == "wavering" for e in creature.active_effects):
        return False
    creature.active_effects = [e for e in creature.active_effects if e.id != "wavering"]
    engine.log(f"{engine.name(ref)} колеблется и теряет ход")
    return True
