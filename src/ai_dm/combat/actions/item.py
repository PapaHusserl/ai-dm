from ai_dm.core.events import DomainEvent
from ai_dm.rules.derived import clock_text
from ai_dm.rules.inventory import drink_item, equip, find_item, unequip, use_item


def swap(engine, ref, option) -> list[DomainEvent]:
    # смена оружия или щита: свободное взаимодействие или действие -- как посчитал вариант
    turn = engine.part(ref).turn
    if option.cost == "free":
        turn.free_interaction = False
    else:
        turn.action = False
    hero = engine.heroes[ref]
    slot = option.params["slot"]
    if option.kind == "unequip":
        item_id = unequip(hero, slot)
        verb = "снимает" if slot == "shield" else "убирает"
    else:
        item_id = option.params["item"]
        equip(hero, item_id, engine.registry, slot)
        verb = "надевает" if slot == "shield" else "берёт"
    engine.log(f"{engine.name(ref)} {verb}: {find_item(engine.registry, item_id)[1].name}")
    return []


def use(engine, ref, option) -> list[DomainEvent]:
    engine.part(ref).turn.bonus = False
    item_id = option.params["item"]
    item = find_item(engine.registry, item_id)[1]
    if item.effects[0].type == "ac_bonus":
        now_s = engine.world.clock.now_s
        was_active = drink_item(engine.heroes[ref], item_id, engine.registry, now_s)
        until = clock_text(now_s + item.effects[0].duration_s)
        if was_active:
            name = item.short_name or item.name
            engine.log(f"{engine.name(ref)}: {name} уже действовала — продлена до {until}")
            return []
        engine.log(f"{engine.name(ref)}: {item.name}, +{item.effects[0].value} КД до {until}")
        return []
    healed = use_item(engine.heroes[ref], item_id, engine.registry, engine.rng)
    engine.log(f"{engine.name(ref)}: {item.name} +{healed}, {engine.hp_text(ref)}")
    return []
