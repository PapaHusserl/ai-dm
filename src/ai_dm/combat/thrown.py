from ai_dm.rules.inventory import dearest_cost, remove_item
from ai_dm.state.combat import GroundItem


def drop(engine, ref, info, target_ref) -> None:
    # брошенное оружие (самый дорогой стек) падает в зоне цели; remove_item сам освобождает руку,
    # когда стек кончился
    hero = engine.heroes[ref]
    weapon_id = info.weapon_id
    removed = remove_item(hero, weapon_id, cost_cp=dearest_cost(hero, weapon_id))[0]
    engine.state.ground_items.append(
        GroundItem(
            item_id=weapon_id, zone_id=engine.part(target_ref).zone_id, owner_ref=ref,
            cost_cp=removed.cost_cp, quality=removed.quality,
        )
    )
