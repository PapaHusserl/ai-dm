from ai_dm.rules.inventory import add_catalog_item, count_item, find_item, remove_item
from ai_dm.state.creature import ActiveEffect

# флаг героя: сколько боеприпасов каждого вида потрачено в этом бою ({id предмета: штук})
FLAG = "ammo_spent"


def plain_ammo(engine, ref, info) -> str | None:
    # обычный боеприпас оружия героя (id предмета); у монстров и оружия без боеприпаса -- None
    if not engine.is_hero(ref) or info.weapon_id is None:
        return None
    return engine.registry.get("weapon", info.weapon_id).ammo


def left(engine, ref, info) -> int | None:
    # сколько обычных боеприпасов осталось у героя; None -- оружию боеприпас не нужен
    item_id = plain_ammo(engine, ref, info)
    if item_id is None:
        return None
    return count_item(engine.heroes[ref], item_id)


def stock_text(engine, ref, info) -> str:
    # « (осталось 19)» для подписи пункта; у оружия без боеприпаса пусто
    remaining = left(engine, ref, info)
    return "" if remaining is None else f" (осталось {remaining})"


def plural_name(engine, item_id) -> str:
    # название боеприпаса для лога («стрелы», «зажигательные стрелы»)
    item = find_item(engine.registry, item_id)[1]
    return (item.name_plural or item.name).lower()


def can_shoot(engine, ref, info) -> bool:
    remaining = left(engine, ref, info)
    return remaining is None or remaining > 0


def spend(engine, ref, info, ammo) -> None:
    # выстрел снимает особую стрелу (ammo) или один обычный боеприпас и записывает потраченное
    item_id = ammo or plain_ammo(engine, ref, info)
    if item_id is None:
        return
    hero = engine.heroes[ref]
    remove_item(hero, item_id)
    flags = [e for e in hero.creature.active_effects if e.id == FLAG]
    if not flags:
        flags = [ActiveEffect(id=FLAG, source=ref, kind="flag")]
        hero.creature.active_effects.append(flags[0])
    flags[0].params[item_id] = int(flags[0].params.get(item_id, 0)) + 1
    if count_item(hero, item_id) == 0:
        engine.log(f"{engine.name(ref)}: {plural_name(engine, item_id)} кончились")


def recover(engine, won) -> None:
    # после боя: победители подбирают половину (вниз) потраченного; флаг снимается всегда
    for ref, hero in engine.heroes.items():
        effects = hero.creature.active_effects
        spent = {}
        for effect in effects:
            if effect.id == FLAG:
                spent.update(effect.params)
        hero.creature.active_effects = [e for e in effects if e.id != FLAG]
        if not won or hero.status != "active":
            continue
        for item_id, qty in spent.items():
            if qty // 2 > 0:
                add_catalog_item(hero, engine.registry, item_id, qty // 2)
                name = plural_name(engine, item_id)
                engine.log(f"{engine.name(ref)}: подобрал {name} ×{qty // 2}")
