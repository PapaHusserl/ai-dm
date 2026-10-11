from ai_dm.core.events import DomainEvent
from ai_dm.protocol.decision import Decision
from ai_dm.protocol.handlers.resources import clamped
from ai_dm.protocol.handlers.trade_pick import (
    buy_source,
    category_problem,
    merchant_base_problem,
    merchant_problem,
    sell_stack,
)
from ai_dm.protocol.handlers.world import rejected
from ai_dm.rules import checks, custom_items, money
from ai_dm.rules import trade as trade_rules
from ai_dm.rules.auto_flags import apply_events
from ai_dm.rules.inventory import add_item, entry_name, remove_item
from ai_dm.state.hero import InventoryEntry


def trade(ctx, request):
    world = ctx.bundle.world
    npc = world.npcs.get(request.npc_id)
    problem = merchant_problem(ctx, request, npc)
    if problem is not None:
        return problem
    if request.direction == "list":
        return category_list(ctx, request, npc)
    scene = ctx.scene
    if scene is not None and scene.trades >= ctx.cfg.trade.ops_per_scene:
        return rejected(
            f"лимит сделок за сцену: {ctx.cfg.trade.ops_per_scene}",
            "В этой сцене больше нельзя торговать: опиши по факту.",
        )
    trade_rules.restock(npc.trade, world.clock.now_s, ctx.cfg)
    action = buy if request.direction == "buy" else sell
    decision = action(ctx, request, npc)
    if isinstance(decision, Decision) and decision.status != "rejected" and scene is not None:
        scene.trades += 1
    return decision


def haggle(ctx, request):
    now_s = ctx.bundle.world.clock.now_s
    npc = ctx.bundle.world.npcs.get(request.npc_id)
    problem = merchant_base_problem(ctx, request, npc)
    if problem is not None:
        return problem
    profile = npc.trade
    if not trade_rules.can_haggle(profile, now_s):
        today = trade_rules.active_haggle(profile, now_s)
        return rejected(
            "уже торговались сегодня",
            f"Сегодня с {npc.name} уже торговались ({today:+d}%): опиши отказ по факту.",
        )
    dc = trade_rules.haggle_dc(npc.attitude, ctx.cfg)
    mode = trade_rules.haggle_mode(npc.attitude, ctx.cfg)
    result = checks.skill_check(
        ctx.hero, ctx.registry, ctx.rng, "persuasion", dc=dc, base_adv=mode,
        base_adv_label="недружелюбен", tags={"stakes": "normal"}, now_s=now_s,
    )
    ref = ctx.add_roll(result, ctx.hero.id)
    percent = trade_rules.haggle_percent_for(result.outcome, result.total, dc, ctx.cfg)
    trade_rules.apply_haggle(profile, percent, now_s)
    return Decision(
        status="accepted",
        result={
            "roll_ref": ref, "outcome": result.outcome, "dc": result.dc, "total": result.total,
            "haggle_percent": percent, "until": "конец дня",
        },
        log=[result.log.text, f"Торг с {npc.name}: цены покупки {percent:+d}% до конца дня"],
    )


def category_list(ctx, request, npc):
    # без сделки: лимит сцены не тратится, состояние не меняется
    models, problem = category_problem(ctx, request, npc)
    if problem is not None:
        return problem
    now_s = ctx.bundle.world.clock.now_s
    items = [
        {
            "item_id": m.id, "name": m.name,
            "price_cp": trade_rules.merchant_buy_quote(m.cost_cp, npc, now_s, ctx.cfg),
        }
        for m in sorted(models, key=lambda m: (m.cost_cp, m.id))
    ]
    return Decision(status="accepted", result={"category": request.category, "items": items})


def short_of_money(ctx, name, unit):
    return rejected(
        f"не хватает денег: нужно {money.format_cp(unit)}, "
        f"есть {money.format_cp(ctx.hero.money_cp)}",
        f"Герою не хватает денег на {name}: нужно {money.format_cp(unit)} за штуку, есть "
        f"{money.format_cp(ctx.hero.money_cp)}. Опиши отказ по факту.",
    )


def buy(ctx, request, npc):
    world = ctx.bundle.world
    profile = npc.trade
    source, problem = buy_source(ctx, request, npc)
    if problem is not None:
        return problem
    unit = trade_rules.merchant_buy_quote(source.cost_cp, npc, world.clock.now_s, ctx.cfg)
    entry = InventoryEntry(
        item_id=request.item_id, qty=1, cost_cp=source.cost_cp, quality=source.quality
    )
    name = entry_name(entry, ctx.registry)
    qty = min(request.qty, source.cap, ctx.cfg.limits.give_item_max_qty)
    if unit > 0:
        qty = min(qty, ctx.hero.money_cp // unit)
    if qty == 0:
        return short_of_money(ctx, name, unit)
    money.spend_money(ctx.hero, unit * qty)
    add_item(ctx.hero, request.item_id, qty, cost_cp=source.cost_cp, quality=source.quality)
    if source.stack is not None:
        source.stack.qty -= qty
        profile.stock = [e for e in profile.stock if e.qty > 0]
    elif source.holder is not None:
        source.holder.qty -= qty
        if source.holder.qty == 0:
            custom_items.recover(world, request.item_id)
    event = DomainEvent(type="item_gained", data={"item": request.item_id, "qty": qty})
    apply_events(world, [event])
    ctx.events.append(event)
    result = trade_result(ctx, npc, request, unit, qty)
    log = [f"Куплено: {name} x{qty} за {money.format_cp(unit * qty)}"]
    if qty < request.qty:
        return clamped(
            f"запрошено {request.qty}, куплено {qty}",
            f"Куплено только {qty} шт. вместо {request.qty} (не хватило денег или товара): "
            "опиши по факту.",
            result, log,
        )
    return Decision(status="accepted", result=result, log=log)


def trade_result(ctx, npc, request, unit, qty):
    result = {
        "direction": request.direction, "item_id": request.item_id, "qty": qty,
        "price_cp": unit, "total_cp": unit * qty, "money_cp": ctx.hero.money_cp,
        "purse_cp": npc.trade.purse_cp,
    }
    haggle_percent = trade_rules.active_haggle(npc.trade, ctx.bundle.world.clock.now_s)
    if request.direction == "buy" and haggle_percent != 0:
        result["haggle_percent"] = haggle_percent
    return result


def sell(ctx, request, npc):
    world = ctx.bundle.world
    profile = npc.trade
    stack, free, problem = sell_stack(ctx, request, npc)
    if problem is not None:
        return problem
    name = entry_name(stack, ctx.registry)
    unit = trade_rules.sell_quote(stack.cost_cp, npc.attitude, ctx.cfg)
    if unit == 0:
        return rejected(
            f"{name} ничего не стоит", f"{name} ничего не стоит: торговец не берёт. Опиши по факту."
        )
    qty = min(request.qty, free, profile.purse_cp // unit)
    if qty == 0:
        return rejected(
            f"у торговца не хватает денег: нужно {money.format_cp(unit)}, "
            f"есть {money.format_cp(profile.purse_cp)}",
            f"У {npc.name} не хватает денег на {name}: опиши отказ по факту.",
        )
    remove_item(ctx.hero, request.item_id, qty, cost_cp=stack.cost_cp, quality=stack.quality)
    money.add_money(ctx.hero, unit * qty)
    profile.purse_cp -= unit * qty
    given = InventoryEntry(
        item_id=request.item_id, qty=qty, cost_cp=stack.cost_cp, quality=stack.quality
    )
    if request.item_id in world.custom_items:
        custom_items.hand_to_npc(world, npc, given, world.clock.now_s)
    else:
        put_in_stock(profile, given)
    event = DomainEvent(type="item_sold", data={"item": request.item_id, "qty": qty})
    apply_events(world, [event])
    ctx.events.append(event)
    result = trade_result(ctx, npc, request, unit, qty)
    log = [f"Продано: {name} x{qty} за {money.format_cp(unit * qty)}"]
    if qty < request.qty:
        return clamped(
            f"запрошено {request.qty}, продано {qty}",
            f"Продано только {qty} шт. вместо {request.qty} (нет столько или у торговца не "
            "хватает денег): опиши по факту.",
            result, log,
        )
    return Decision(status="accepted", result=result, log=log)


def put_in_stock(profile, given):
    for entry in profile.stock:
        same = entry.cost_cp == given.cost_cp and entry.quality == given.quality
        if same and entry.item_id == given.item_id:
            entry.qty += given.qty
            return
    profile.stock.append(given)
