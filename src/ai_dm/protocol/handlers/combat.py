from pydantic import ValidationError

from ai_dm.combat.actions.improvise import EFFECTS, spec_problem
from ai_dm.combat.defeat import DefeatParams, apply_defeat_outcome
from ai_dm.combat.engine import CombatEngine
from ai_dm.combat.setup import validate_start
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.protocol.hints import allowed
from ai_dm.rules import encounter
from ai_dm.state.combat import CombatState, Group, Participant, Zone, ZoneFeature
from ai_dm.state.creature import AppliedCondition, CreatureState

# коды validate_start -> подсказка мастеру
SETUP_HINTS = {
    "zones_count": "зон должно быть от 2 до 5",
    "zone_ids_duplicate": "id зон должны быть разными",
    "zone_names_duplicate": "названия зон должны быть разными",
    "graph_unknown_zone": "в adjacent указана зона, которой нет в zones",
    "graph_asymmetric": "связь зон должна быть взаимной: если A соседняя с B, то B с A",
    "graph_disconnected": "граф зон несвязный: из любой зоны должен быть путь в любую",
    "participant_unplaced": "у участника не указана зона",
    "participant_zone_unknown": "участник в в зоне, которой нет в zones (zone врага или hero_zone)",
    "participant_duplicate": "ref врагов должны быть разными и не совпадать с героем",
    "group_unknown": "у врага указана группа, которой нет в groups",
    "group_intent_missing": "у группы врагов должно быть намерение (intent)",
    "group_leader_invalid": "лидер группы должен быть врагом из этой же группы",
}


# коды spec_problem -> подсказка модели; {…} подставляет improvise_problem
IMPROVISE_HINTS = {
    "target_required": "эффект {effect} требует target — ref врага: {enemies}",
    "zone_required": "push требует zone — зона, соседняя с зоной цели {target} ({home}): "
    "{adjacent}",
    "zone_not_adjacent": "зона {zone!r} не подходит для push: цель {target} стоит в зоне {home}"
    "{own}; нужна соседняя зона: {adjacent}",
    "unknown_effect": "нет эффекта {effect!r}; допустимые: {effects}",
}


def improvise_problem(state, spec):
    code = spec_problem(state, spec.effect, spec.target, spec.zone)
    if code is None:
        return None
    home = next((p.zone_id for p in state.participants if p.ref == spec.target), "")
    adjacent = next((z.adjacent for z in state.zones if z.id == home), [])
    message = IMPROVISE_HINTS[code].format(
        effects=", ".join(EFFECTS), effect=spec.effect, target=spec.target,
        zone=spec.zone, home=home,
        adjacent=", ".join(adjacent),
        enemies=", ".join(p.ref for p in state.participants if p.side == "enemies"),
        own=", это её собственная зона" if spec.zone == home else "",
    )
    return Invalid(code=code, message=message)


def setup_message(codes, state):
    hints = [f"{code}: {SETUP_HINTS.get(code, 'плохой старт боя')}" for code in codes]
    zones = ", ".join(z.id for z in state.zones)
    refs = ", ".join(f"{p.ref} (зона {p.zone_id}, группа {p.group_id})" for p in state.participants)
    groups = ", ".join(f"{gid} (лидер {g.leader_id})" for gid, g in state.groups.items())
    return (
        "плохой старт боя: " + "; ".join(hints)
        + f". Зоны: {zones}. Участники: {refs}. Группы: {groups}."
    )


def next_combat_number(ctx):
    world = ctx.bundle.world
    active = ctx.bundle.session.active_combat
    number = 1
    while f"combat_ended:combat_{number}" in world.flags or (
        active is not None and active.id == f"combat_{number}"
    ):
        number += 1
    return number


def make_feature(spec):
    fields = {"kind": spec.kind, "damage": spec.damage, "save": spec.save}
    if spec.damage_type is not None:
        fields["damage_type"] = spec.damage_type
    if spec.dc is not None:
        fields["dc"] = spec.dc
    return ZoneFeature(**fields)


def make_zone(spec):
    features = [make_feature(f) for f in spec.features or []]
    return Zone(
        id=spec.id, name=spec.name, adjacent=list(spec.adjacent), features=features,
        exit=bool(spec.exit), elevation=spec.elevation,
        pos=list(spec.pos) if len(spec.pos) == 2 else None,
    )


def make_enemy(ctx, spec):
    npc = ctx.bundle.world.npcs.get(spec.ref)
    monster = ctx.registry.get("monster", spec.monster_id)
    name = spec.name or (npc.name if npc is not None else monster.name)
    part = Participant(
        ref=spec.ref, side="enemies", group_id=spec.group, zone_id=spec.zone,
        monster_id=spec.monster_id, name=name,
    )
    if npc is None:
        part.creature = CreatureState(hp_current=monster.hp, hp_max=monster.hp)
    elif npc.key:
        part.controller = "external"
    return part


def start_combat(ctx, request):
    world = ctx.bundle.world
    session = ctx.bundle.session
    hero = ctx.hero
    if session.active_combat is not None:
        return Invalid(code="combat_already_active", message="бой уже идёт")
    if not request.enemies:
        return Invalid(code="no_enemies", message="в бою должен быть хотя бы один враг")
    limit = ctx.cfg.limits.max_enemies
    cut = len(request.enemies) > limit
    enemies = request.enemies[:limit]
    cut_refs = [spec.ref for spec in request.enemies[limit:]]
    limit_refs = list(cut_refs)
    for spec in enemies:
        if not ctx.registry.has("monster", spec.monster_id):
            return Invalid(
                code="unknown_monster",
                message=f"нет монстра {spec.monster_id!r}" + allowed(ctx.registry.ids("monster")),
            )
        npc = world.npcs.get(spec.ref)
        if npc is not None and npc.status != "alive":
            return Invalid(
                code="npc_unavailable",
                message=f"NPC {spec.ref!r} не может участвовать в бою: статус {npc.status!r}",
            )
    for spec in request.groups:
        if spec.lair_location_id is not None and spec.lair_location_id not in world.locations:
            return Invalid(
                code="unknown_location",
                message=f"нет локации {spec.lair_location_id!r}" + allowed(world.locations),
            )
    try:
        zones = [make_zone(spec) for spec in request.zones]
    except ValidationError as error:
        return Invalid(code="bad_zone_feature", message=str(error))
    # бюджет боя (ТЗ 2.3): сверх бюджета без оснований враги убираются с конца, лидеры остаются
    budget = encounter.party_budget([hero.sheet.level], ctx.registry, ctx.cfg)
    leaders = {spec.leader for spec in request.groups}
    fitted, over = encounter.fit_to_budget(enemies, leaders, budget, ctx.registry)
    reason = None
    budget_cut = False
    if len(fitted) < len(enemies) or over == "leader":
        reason = encounter.override_reason(ctx.bundle, hero.location_id, request.initiated_by)
        if reason is None:
            reason = over
            budget_cut = len(fitted) < len(enemies)
            kept_refs = [spec.ref for spec in fitted]
            cut_refs += [spec.ref for spec in enemies if spec.ref not in kept_refs]
            enemies = fitted
        # основание есть: бой без урезания по бюджету
    cut = len(enemies) < len(request.enemies)
    participants = [
        Participant(
            ref=hero.id, side="heroes", group_id="party", zone_id=request.hero_zone,
            controller="external", name=hero.name,
        )
    ]
    participants += [make_enemy(ctx, spec) for spec in enemies]
    groups = {"party": Group(leader_id=hero.id)}
    for spec in request.groups:
        members = [e.ref for e in enemies if e.group == spec.id]
        if cut and not members and any(e.group == spec.id for e in request.enemies):
            # все члены группы отрезаны срезом
            continue
        leader = spec.leader
        if leader in cut_refs and members:
            leader = members[0]
        groups[spec.id] = Group(
            leader_id=leader, intent=spec.intent, lair_location_id=spec.lair_location_id
        )
    state = CombatState(
        id=f"combat_{next_combat_number(ctx)}", zones=zones, participants=participants,
        groups=groups, budget_override_reason=reason,
    )
    codes = validate_start(state)
    if codes:
        return Invalid(code=codes[0], message=setup_message(codes, state))
    if request.hero_hidden:
        # засада: герой скрыт, первая атака с преимуществом
        hero.creature.conditions.append(AppliedCondition(id="invisible", source="hidden", dc=15))
    session.active_combat = state
    if request.initiated_by == "hero" and ctx.scene is not None:
        ctx.scene.hero_initiated_combat = True
    result = {"combat_id": state.id}
    log = [f"Бой: врагов {len(enemies)}, зон {len(zones)}"]
    if request.hero_hidden:
        log.append(f"{hero.name} скрыт: первая атака с преимуществом")
    log.append(encounter.budget_text(hero.sheet.level, budget, enemies, ctx.registry, ctx.cfg))
    if reason is not None:
        log.append(f"Бой сверх бюджета: {encounter.REASON_WORDS[reason]}")
    budget_dropped = [e for e in request.enemies if e.ref in cut_refs and e.ref not in limit_refs]
    if budget_dropped:
        text = encounter.counts_text(budget_dropped, ctx.registry)
        log.append(f"Не вступили в бой (сверх бюджета): {text}")
    limit_dropped = [e for e in request.enemies if e.ref in limit_refs]
    if limit_dropped:
        text = encounter.counts_text(limit_dropped, ctx.registry)
        log.append(f"Не вступили в бой (больше {limit} врагов): {text}")
    if budget_cut or cut:
        # один сигнал на оба предела: бюджет сложности и max_enemies
        why = []
        signal = f"В бой вошли только {len(enemies)} из {len(request.enemies)} врагов. "
        if budget_cut:
            why.append("бой сверх бюджета сложности")
            signal += (
                "Бой сверх бюджета без предупреждения об опасности недопустим. "
            )
        if len(request.enemies) > limit:
            why.append(f"врагов больше {limit}")
            signal += f"Больше {limit} врагов в бою быть не может. "
        signal += "Опиши остальных иначе (разведчики, подкрепление позже, не вступили в бой)."
        return Decision(
            status="clamped", reason="; ".join(why), signal_to_master=signal,
            report_tag="limit-exceeded", result=result, log=log,
        )
    return Decision(status="accepted", result=result, log=log)


def player_action(ctx, request):
    if ctx.bundle.session.active_combat is None:
        return Invalid(code="no_active_combat", message="сейчас нет боя")
    if ctx.combat_options and request.steps:
        ids = [option["id"] for option in ctx.combat_options]
        if request.steps[0] not in ids:
            return Invalid(
                code="unknown_step",
                message=f"первый шаг {request.steps[0]!r} не из combat.options: {ids}",
            )
    if request.improvise is not None:
        problem = improvise_problem(ctx.bundle.session.active_combat, request.improvise)
        if problem is not None:
            return problem
    result = {"steps": list(request.steps)}
    if request.improvise is not None:
        result["improvise"] = request.improvise.model_dump()
    if request.parley is not None:
        result["parley"] = request.parley.model_dump()
    tag = None
    if request.unsupported is not None:
        result["unsupported"] = request.unsupported
        tag = "missing-mechanic"
    return Decision(
        status="accepted", result=result, report_tag=tag,
        log=[f"Действие игрока: {request.steps}"],
    )


def npc_action(ctx, request):
    if ctx.mode != "npc_choice":
        return Invalid(code="not_available_in_mode", message="npc_action только в режиме NPC")
    if request.choice not in (ctx.npc_options or []):
        return Invalid(code="unknown_option", message=f"нет варианта {request.choice!r}")
    return Decision(
        status="accepted", result={"choice": request.choice}, log=[f"Выбор NPC: {request.choice}"]
    )


def defeat_params(request, rob_items):
    fields = {
        "lair_location_id": request.lair_location_id, "rob_items": rob_items,
        "scar_ability": request.scar_ability, "scar_skill": request.scar_skill,
        "debt_to": request.debt_to,
    }
    if request.scar_text is not None:
        fields["scar_text"] = request.scar_text
    if request.debt_text is not None:
        fields["debt_text"] = request.debt_text
    return DefeatParams(**fields)


def chapter_id_of(ctx) -> str:
    chapter = ctx.bundle.session.current_chapter
    return "" if chapter is None else chapter.id


def scene_id_of(ctx) -> str:
    return "" if ctx.scene is None else ctx.scene.id


def defeat_outcome(ctx, request):
    state = ctx.bundle.session.active_combat
    world = ctx.bundle.world
    if state is None:
        return Invalid(code="no_active_combat", message="сейчас нет боя")
    if state.outcome != "defeat_pending":
        return Invalid(code="no_defeat_pending", message="герой не ждёт последствий поражения")
    if request.lair_location_id is not None and request.lair_location_id not in world.locations:
        return Invalid(
            code="unknown_location",
            message=f"нет локации {request.lair_location_id!r}" + allowed(world.locations),
        )
    if request.debt_to is not None and request.debt_to not in world.npcs:
        return Invalid(
            code="unknown_npc",
            message=f"нет NPC {request.debt_to!r}" + allowed(world.npcs),
        )
    rob_items = request.rob_items
    cut = False
    if rob_items is not None and not 1 <= rob_items <= 2:
        rob_items = max(1, min(2, rob_items))
        cut = True
    done = apply_defeat_outcome(
        state, request.consequences, defeat_params(request, rob_items), world=world,
        hero=ctx.hero, registry=ctx.registry, cfg=ctx.cfg, rng=ctx.rng,
        chapter_id=chapter_id_of(ctx), scene_id=scene_id_of(ctx),
    )
    if done.status == "rejected":
        return Invalid(code="invalid_defeat", message=done.reason, report_tag="invalid-defeat")
    ctx.events.extend(done.events)
    log = [f"Последствие поражения: {name}" for name in request.consequences]
    log += done.notes
    if cut:
        return Decision(
            status="clamped", reason=f"предметов к изъятию {request.rob_items}, взято {rob_items}",
            signal_to_master=f"Отобрано не больше {rob_items} предметов: опиши по факту.",
            report_tag="limit-exceeded", log=log,
        )
    if done.status == "clamped":
        return Decision(
            status="clamped", reason="нечего отбирать",
            signal_to_master="Отбирать было нечего: опиши по факту.",
            report_tag="limit-exceeded", log=log,
        )
    return Decision(status="accepted", log=log)


def end_combat(ctx, request):
    state = ctx.bundle.session.active_combat
    if state is None:
        return Invalid(code="no_active_combat", message="сейчас нет боя")
    engine = CombatEngine(
        state, ctx.bundle.world, {ctx.hero.id: ctx.hero}, ctx.registry, ctx.cfg, ctx.rng
    )
    if engine.is_over:
        return Invalid(code="combat_already_over", message="бой уже окончен")
    ctx.events.extend(engine.end_combat())
    reason = request.reason or "без причины"
    return Decision(
        status="accepted", result={"outcome": state.outcome},
        log=[f"Бой завершён мастером: {reason}"],
    )
