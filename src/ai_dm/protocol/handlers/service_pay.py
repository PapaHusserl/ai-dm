from ai_dm.protocol.decision import Decision
from ai_dm.protocol.handlers.resources import clamped
from ai_dm.rules import money
from ai_dm.rules import services as service_rules
from ai_dm.rules import trade as trade_rules


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


def free_here(ctx, request, npc, kind):
    # услуга сейчас даровая: друг, раз в день на вид (перевозка -- всегда)
    return service_rules.is_free(request.service_id, kind, npc, ctx.bundle.world, ctx.cfg)


def affordable_qty(ctx, request, unit, free=False):
    # даровая услуга -- одна единица (решение 153)
    qty = 1 if free else min(request.qty, ctx.cfg.limits.give_item_max_qty)
    if unit > 0:
        qty = min(qty, ctx.hero.money_cp // unit)
    return qty


def short_cause(ctx, request, unit, free=False):
    # почему qty меньше запрошенного: лимит за раз или деньги (считать до списания)
    if free:
        return "у друга даром раз в день"
    cap = ctx.cfg.limits.give_item_max_qty
    if request.qty > cap and (unit == 0 or ctx.hero.money_cp // unit >= cap):
        return f"лимит количества за раз: {cap}"
    return "не хватило денег"


def free_line(kind, npc, qty):
    # строка ленты даровой услуги (решение 150)
    if kind.effect == "lodging":
        return f"Ночлег: {kind.name} у {npc.name} — даром"
    if kind.effect == "meal":
        return f"Заказано: {kind.name} x{qty} у {npc.name} — даром"
    return f"Даром: {kind.name} x{qty} у {npc.name}"


def price_tail(total, free):
    return "— даром" if free else f"за {money.format_cp(total)}"


def rest_signal(kind, npc, free):
    # сигнал мастеру: после ночлега -- rest long, после отдыха -- rest short (решение 152)
    if kind.effect == "lodging":
        if free:
            return f"Ночлег у {npc.name} даром: теперь rest long в этом же ходу."
        return "Ночлег оплачен: теперь rest long в этом же ходу."
    if kind.effect == "rest_short":
        if free:
            return f"Отдых у {npc.name} даром: теперь rest short в этом же ходу."
        return "Платный отдых оплачен: теперь rest short в этом же ходу."
    return None


def paid(request, qty, result, log, cause="не хватило денег"):
    if qty < request.qty:
        return clamped(
            f"запрошено {request.qty}, оплачено {qty}",
            f"Оплачено только {qty} из {request.qty} ({cause}): опиши по факту.",
            result, log,
        )
    return Decision(status="accepted", result=result, log=log)
