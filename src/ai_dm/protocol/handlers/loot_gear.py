from ai_dm.core.events import DomainEvent
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.rules import custom_items, loot, money
from ai_dm.rules.auto_flags import apply_events
from ai_dm.rules.inventory import add_item, entry_name


def gold_loot(ctx, request):
    if request.direction != "gain":
        return Invalid(code="bad_amount", message="loot_individual только для gain")
    last = ctx.bundle.session.last_combat
    if last is None:
        return Invalid(
            code="no_combat_loot", message="нет завершённого боя, с которого можно взять добычу"
        )
    if last.looted and (last.gear_looted or not last.gear):
        return Decision(
            status="rejected", reason="добыча с этого боя уже получена",
            signal_to_master="Добыча с последнего боя уже выдана: больше денег и вещей с него нет.",
        )
    amount = 0
    if not last.looted:
        amount = loot.defeated_treasure(last.defeated, ctx.rng, ctx.registry)
        last.looted = True
        money.add_money(ctx.hero, amount)
    items, returned = loot_gear(ctx, last)
    log = []
    if amount > 0:
        log.append(f"Добыча: +{money.format_cp(amount)}")
    if items:
        log.append(f"Добыча: {', '.join(item_words(item) for item in items)}")
    log += returned
    return Decision(
        status="accepted",
        result={"amount_cp": amount, "money_cp": ctx.hero.money_cp, "items": items}, log=log,
    )


def item_words(item) -> str:
    return item["name"] if item["qty"] == 1 else f"{item['name']} x{item['qty']}"


def loot_gear(ctx, last) -> tuple[list[dict], list[str]]:
    # снаряжение с тел в инвентарь героя (один раз); квестовое у держателя возвращается миру героя
    if last.gear_looted:
        return [], []
    last.gear_looted = True
    items = []
    returned = []
    for entry in last.gear:
        if entry.item_id in ctx.bundle.world.custom_items:
            custom_items.recover(ctx.bundle.world, entry.item_id)
            returned.append(f"Возвращён предмет: {entry_name(entry, ctx.registry)} x{entry.qty}")
        add_item(ctx.hero, entry.item_id, entry.qty, cost_cp=entry.cost_cp, quality=entry.quality)
        name = entry_name(entry, ctx.registry)
        items.append({"item_id": entry.item_id, "qty": entry.qty, "name": name})
        event = DomainEvent(type="item_gained", data={"item": entry.item_id, "qty": entry.qty})
        apply_events(ctx.bundle.world, [event])
        ctx.events.append(event)
    return items, returned
