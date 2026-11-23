from ai_dm.core.dice import roll_dice
from ai_dm.core.events import DomainEvent
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.protocol.handlers.resources import concentration_note
from ai_dm.protocol.handlers.service_extras import add_signal, boon_and_risks, remember_deal
from ai_dm.protocol.handlers.service_pay import (
    affordable_qty,
    free_here,
    free_line,
    paid,
    price_tail,
    rest_signal,
    service_result,
    short_cause,
)
from ai_dm.protocol.handlers.trade import short_of_money
from ai_dm.protocol.handlers.trade_pick import refusal_problem, scene_problem
from ai_dm.protocol.handlers.world import rejected
from ai_dm.protocol.hints import allowed
from ai_dm.rules import money, time_ops
from ai_dm.rules import services as service_rules
from ai_dm.rules import trade as trade_rules
from ai_dm.rules.auto_flags import apply_events
from ai_dm.rules.healing import heal

# что снято обрядом -> слово в заголовке лога
CURE_TITLES = {
    ("cursed",): "Проклятие снято", ("diseased",): "Болезнь снята",
    ("cursed", "diseased"): "Проклятие и болезнь сняты",
}

# глагол лога по эффекту услуги
LOG_WORDS = {
    "meal": "Заказано", "lodging": "Снято", "heal": "Лечение", "rest_short": "Оплачено",
    "plain": "Оплачено",
}


def service(ctx, request):
    world = ctx.bundle.world
    npc = world.npcs.get(request.npc_id)
    problem = provider_problem(ctx, request, npc)
    if problem is not None:
        return problem
    if request.direction == "list":
        return service_list(ctx, npc)
    kind = ctx.cfg.services.kinds.get(request.service_id)
    if kind is None or request.service_id not in npc.services:
        return Invalid(
            code="unknown_service",
            message=f"{npc.name} не оказывает {request.service_id!r}"
            + allowed(service_ids(ctx, npc)),
        )
    scene = ctx.scene
    if scene is not None and scene.trades >= ctx.cfg.trade.ops_per_scene:
        return rejected(
            f"лимит сделок за сцену: {ctx.cfg.trade.ops_per_scene}",
            "В этой сцене больше нельзя платить за услуги и торговать: опиши по факту.",
        )
    free = free_here(ctx, request, npc, kind)
    unit = service_rules.quote(kind, npc, world, ctx.cfg, request.service_id)
    actions = {"heal": heal_service, "cure": cure_service, "passage": passage_service}
    action = actions.get(kind.effect, pay_service)
    decision = action(ctx, request, npc, kind, unit)
    if isinstance(decision, Decision) and decision.status != "rejected":
        if free and kind.effect != "passage":
            service_rules.mark_free(request.service_id, npc, world)
        if kind.intimate and not free:
            remember_deal(ctx, npc, kind, decision)
        if kind.boon or kind.intimate:
            boon_and_risks(ctx, npc, kind, decision)
        if scene is not None:
            scene.trades += 1
    return decision


def provider_problem(ctx, request, npc):
    # Invalid/rejected, если услугами NPC сейчас не воспользоваться, иначе None
    problem = scene_problem(ctx, request, npc, "service")
    if problem is not None:
        return problem
    if request.direction != "list" and request.qty < 1:
        return Invalid(code="bad_amount", message="количество должно быть не меньше 1")
    return refusal_problem(ctx, npc)


def service_ids(ctx, npc):
    return [kind_id for kind_id, _kind in service_rules.kinds_of(npc, ctx.cfg)]


def service_list(ctx, npc):
    # без оплаты: лимит сцены не тратится, состояние не меняется
    world = ctx.bundle.world
    items = [
        {
            "id": kind_id, "name": kind.name, "unit": kind.unit,
            "price_cp": service_rules.quote(kind, npc, world, ctx.cfg, kind_id),
            "description": kind.description,
        }
        for kind_id, kind in service_rules.kinds_of(npc, ctx.cfg)
    ]
    return Decision(status="accepted", result={"npc_id": npc.id, "items": items})


def pay_service(ctx, request, npc, kind, unit):
    # еда, ночлег, платный отдых: деньги и лог; ночлег ещё и флаг для rest long
    world = ctx.bundle.world
    free = free_here(ctx, request, npc, kind)
    if kind.effect == "lodging":
        if service_rules.lodging_paid(world, ctx.hero.id, ctx.cfg):
            return rejected(
                "ночлег уже оплачен",
                "Ночлег на сегодня уже оплачен: повторно не плати, вызови rest long.",
            )
        # комната снимается на одну ночь, qty не важен
        request = request.model_copy(update={"qty": 1})
    qty = affordable_qty(ctx, request, unit, free)
    if qty == 0:
        return short_of_money(ctx, kind.name, unit)
    cause = short_cause(ctx, request, unit, free)
    money.spend_money(ctx.hero, unit * qty)
    result = service_result(ctx, npc, request, unit, qty)
    if free:
        log = [free_line(kind, npc, qty)]
    else:
        log = [
            f"{LOG_WORDS[kind.effect]}: {kind.name} x{qty} у {npc.name} за "
            f"{money.format_cp(unit * qty)}"
        ]
    if kind.effect == "lodging":
        flag = f"{service_rules.LODGING_FLAG}:{ctx.hero.id}"
        world.flags[flag] = trade_rules.day_of(world.clock.now_s)
        if not free:
            log[0] = (
                f"Ночлег оплачен: {kind.name} у {npc.name} — {money.format_cp(unit * qty)}"
            )
    decision = paid(request, qty, result, log, cause)
    # сигнал отдыха и при clamped: после текста урезания через пробел
    note = rest_signal(kind, npc, free)
    if note:
        add_signal(decision, note)
    return decision


def passage_service(ctx, request, npc, kind, unit):
    # перевозка: один переход по ребру нужного рода; герой и спутники с follows -- в destination
    hero = ctx.hero
    free = free_here(ctx, request, npc, kind)
    world = ctx.bundle.world
    targets = service_rules.passage_targets(world, hero.location_id, kind.transport, ctx.cfg)
    edge = targets.get(request.destination)
    if edge is None:
        return Invalid(
            code="no_passage",
            message=f"{npc.name} не везёт в это место" + allowed(targets),
        )
    if hero.money_cp < unit:
        return short_of_money(ctx, kind.name, unit)
    money.spend_money(hero, unit)
    service_rules.remember_ferry_home(world, npc)
    home = world.flags[f"{service_rules.FERRY_HOME_FLAG}:{npc.id}"]
    world.clock.advance(time_ops.edge_seconds(edge.distance_m, edge.kind, "normal", ctx.cfg))
    hero.location_id = request.destination
    companions = []
    for companion in world.npcs.values():
        if companion.follows == hero.id and companion.status == "alive":
            companion.location_id = request.destination
            companions.append(companion.name)
    npc.location_id = request.destination
    returned = service_rules.return_ferrymen(world, request.destination)
    event = DomainEvent(type="location_visited", data={"id": request.destination})
    apply_events(world, [event])
    ctx.events.append(event)
    result = service_result(ctx, npc, request, unit, 1)
    result["location_id"] = request.destination
    name = world.locations[request.destination].name
    if free:
        log = [f"{npc.name} перевёз даром"]
    else:
        log = [f"Перевозка: {npc.name}, {money.format_cp(unit)} — «{name}»"]
    if companions:
        log.append("С тобой: " + ", ".join(companions))
    concentration_note(ctx, log, result)
    fare = "" if free else "; обратно — ещё одна плата"
    signal = (
        f"{npc.name} переправился с героем и ждёт здесь{fare}. "
        f"Его берег — «{world.locations[home].name}»"
    )
    if returned:
        signal += "; " + service_rules.returned_signal(world, returned)
    return Decision(status="accepted", result=result, log=log, signal_to_master=signal)


def cure_service(ctx, request, npc, kind, unit):
    # снимает разом все состояния из kind.cures за одну цену; qty не важен
    hero = ctx.hero
    if hero.status == "dead":
        return Invalid(code="hero_dead", message="герой мёртв: обряд снятия не нужен")
    conditions = hero.creature.conditions
    cured = [c.id for c in conditions if c.id in kind.cures]
    if not cured:
        return rejected(
            "снимать нечего",
            "На герое нет проклятия, которое снимает эта услуга: обряд не проведён, деньги не "
            "списаны. Опиши по факту.",
            report_tag="nothing_to_cure",
        )
    if hero.money_cp < unit:
        return short_of_money(ctx, kind.name, unit)
    money.spend_money(hero, unit)
    conditions[:] = [c for c in conditions if c.id not in kind.cures]
    event = DomainEvent(type="cured", data={"id": hero.id, "conditions": ",".join(cured)})
    apply_events(ctx.bundle.world, [event])
    ctx.events.append(event)
    result = service_result(ctx, npc, request, unit, 1)
    result["cured"] = cured
    known = tuple(c for c in ("cursed", "diseased") if c in cured)
    title = CURE_TITLES.get(known, "Состояние снято")
    tail = price_tail(unit, free_here(ctx, request, npc, kind))
    log = [f"{title}: {kind.name} у {npc.name} {tail}"]
    return Decision(status="accepted", result=result, log=log)


def heal_service(ctx, request, npc, kind, unit):
    # лечит только героя; по броску кости на каждое лечение, пока не полные хиты
    hero = ctx.hero
    free = free_here(ctx, request, npc, kind)
    if hero.status == "dead":
        return Invalid(code="hero_dead", message="герой мёртв: услуга лечения не нужна")
    creature = hero.creature
    if creature.hp_current >= creature.hp_max:
        return rejected(
            "лечить нечего",
            "Герой здоров, хиты полные: лечение не оказано, деньги не списаны. Опиши по факту.",
        )
    qty = affordable_qty(ctx, request, unit, free)
    if qty == 0:
        return short_of_money(ctx, kind.name, unit)
    cause = short_cause(ctx, request, unit, free)
    done = 0
    healed = 0
    while done < qty and creature.hp_current < creature.hp_max:
        healed += heal(hero, roll_dice(kind.heal, ctx.rng).total)
        done += 1
    money.spend_money(hero, unit * done)
    result = service_result(ctx, npc, request, unit, done)
    result.update({"healed": healed, "hp": creature.hp_current, "hp_max": creature.hp_max})
    log = [
        f"{LOG_WORDS[kind.effect]}: {kind.name} x{done} у {npc.name}: +{healed} HP "
        f"(теперь {creature.hp_current}/{creature.hp_max}) {price_tail(unit * done, free)}"
    ]
    if creature.hp_current >= creature.hp_max:
        cause = "герой исцелён раньше"
    return paid(request, done, result, log, cause)
