from ai_dm.core.dice import roll_dice
from ai_dm.core.events import DomainEvent
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.protocol.handlers.resources import clamped
from ai_dm.protocol.handlers.trade import short_of_money
from ai_dm.protocol.handlers.trade_pick import refusal_problem, scene_problem
from ai_dm.protocol.handlers.world import rejected
from ai_dm.protocol.hints import allowed
from ai_dm.rules import money
from ai_dm.rules import services as service_rules
from ai_dm.rules import trade as trade_rules
from ai_dm.rules.auto_flags import apply_events
from ai_dm.rules.boons import BOONS, grant_boon
from ai_dm.rules.healing import heal

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
    unit = service_rules.quote(kind, npc, world, ctx.cfg)
    action = {"heal": heal_service, "cure": cure_service}.get(kind.effect, pay_service)
    decision = action(ctx, request, npc, kind, unit)
    if isinstance(decision, Decision) and decision.status != "rejected":
        if kind.boon:
            boon_and_risks(ctx, npc, kind, decision)
        if scene is not None:
            scene.trades += 1
    return decision


def boon_and_risks(ctx, npc, kind, decision) -> None:
    # бонус услуги после принятой оплаты: result, строка лога, сигнал мастеру
    line, granted = grant_boon(ctx, kind.boon, npc)
    decision.result["boon"] = kind.boon
    decision.log.append(line)
    if granted:
        note = f"Герою достался бонус: {BOONS[kind.boon][0]}."
        decision.signal_to_master = " ".join(x for x in (decision.signal_to_master, note) if x)


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
            "price_cp": service_rules.quote(kind, npc, world, ctx.cfg),
            "description": kind.description,
        }
        for kind_id, kind in service_rules.kinds_of(npc, ctx.cfg)
    ]
    return Decision(status="accepted", result={"npc_id": npc.id, "items": items})


def service_result(ctx, npc, request, unit, qty):
    result = {
        "service_id": request.service_id, "qty": qty, "price_cp": unit, "total_cp": unit * qty,
        "money_cp": ctx.hero.money_cp,
    }
    slot = service_rules.haggle_slot(npc, ctx.bundle.world)
    haggle_percent = trade_rules.active_haggle(slot, ctx.bundle.world.clock.now_s)
    if haggle_percent != 0:
        result["haggle_percent"] = haggle_percent
    return result


def affordable_qty(ctx, request, unit):
    qty = min(request.qty, ctx.cfg.limits.give_item_max_qty)
    if unit > 0:
        qty = min(qty, ctx.hero.money_cp // unit)
    return qty


def short_cause(ctx, request, unit):
    # почему qty меньше запрошенного: лимит за раз или деньги (считать до списания)
    cap = ctx.cfg.limits.give_item_max_qty
    if request.qty > cap and (unit == 0 or ctx.hero.money_cp // unit >= cap):
        return f"лимит количества за раз: {cap}"
    return "не хватило денег"


def pay_service(ctx, request, npc, kind, unit):
    # еда, ночлег, платный отдых: деньги и лог; ночлег ещё и флаг для rest long
    world = ctx.bundle.world
    if kind.effect == "lodging":
        if service_rules.lodging_paid(world, ctx.hero.id, ctx.cfg):
            return rejected(
                "ночлег уже оплачен",
                "Ночлег на сегодня уже оплачен: повторно не плати, вызови rest long.",
            )
        # комната снимается на одну ночь, qty не важен
        request = request.model_copy(update={"qty": 1})
    qty = affordable_qty(ctx, request, unit)
    if qty == 0:
        return short_of_money(ctx, kind.name, unit)
    cause = short_cause(ctx, request, unit)
    money.spend_money(ctx.hero, unit * qty)
    result = service_result(ctx, npc, request, unit, qty)
    log = [
        f"{LOG_WORDS[kind.effect]}: {kind.name} x{qty} у {npc.name} за "
        f"{money.format_cp(unit * qty)}"
    ]
    signal = None
    if kind.effect == "lodging":
        flag = f"{service_rules.LODGING_FLAG}:{ctx.hero.id}"
        world.flags[flag] = trade_rules.day_of(world.clock.now_s)
        log[0] = (
            f"Ночлег оплачен: {kind.name} у {npc.name} — {money.format_cp(unit * qty)}"
        )
        signal = "Ночлег оплачен: теперь rest long в этом же ходу."
    elif kind.effect == "rest_short":
        signal = "Платный отдых оплачен: теперь rest short в этом же ходу."
    decision = paid(request, qty, result, log, cause)
    if decision.status == "accepted":
        decision.signal_to_master = signal
    return decision


def paid(request, qty, result, log, cause="не хватило денег"):
    if qty < request.qty:
        return clamped(
            f"запрошено {request.qty}, оплачено {qty}",
            f"Оплачено только {qty} из {request.qty} ({cause}): опиши по факту.",
            result, log,
        )
    return Decision(status="accepted", result=result, log=log)


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
    log = [f"Проклятие снято: {kind.name} у {npc.name} за {money.format_cp(unit)}"]
    return Decision(status="accepted", result=result, log=log)


def heal_service(ctx, request, npc, kind, unit):
    # лечит только героя; по броску кости на каждое лечение, пока не полные хиты
    hero = ctx.hero
    if hero.status == "dead":
        return Invalid(code="hero_dead", message="герой мёртв: услуга лечения не нужна")
    creature = hero.creature
    if creature.hp_current >= creature.hp_max:
        return rejected(
            "лечить нечего",
            "Герой здоров, хиты полные: лечение не оказано, деньги не списаны. Опиши по факту.",
        )
    qty = affordable_qty(ctx, request, unit)
    if qty == 0:
        return short_of_money(ctx, kind.name, unit)
    cause = short_cause(ctx, request, unit)
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
        f"(теперь {creature.hp_current}/{creature.hp_max}) за {money.format_cp(unit * done)}"
    ]
    if creature.hp_current >= creature.hp_max:
        cause = "герой исцелён раньше"
    return paid(request, done, result, log, cause)
