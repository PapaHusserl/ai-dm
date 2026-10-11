import copy


def migrate_v5_to_v6(data: dict, context) -> dict:
    # цена у каждого экземпляра: записи инвентаря героев и выбитое оружие боя получают cost_cp
    # (цена из реестра по id; неизвестный id -- 0 и строка в context.report); quality не ставится
    data = copy.deepcopy(data)
    costs = context.item_cost

    def fill(entries):
        for entry in entries:
            if "cost_cp" in entry:
                continue
            item_id = entry["item_id"]
            if item_id not in costs:
                context.report.append(f"нет цены предмета {item_id!r} в реестре: cost_cp=0")
            entry["cost_cp"] = costs.get(item_id, 0)

    for hero in data.get("heroes", []):
        fill(hero.get("inventory", []))
    combat = data.get("session", {}).get("active_combat")
    if combat is not None:
        fill(combat.get("ground_items", []))
    # сюжетные предметы: каталог мира, счётчик сцены, трофеи последнего боя
    world = data.get("world")
    if world is not None:
        world.setdefault("custom_items", {})
        world.setdefault("custom_item_seq", 0)
    scene = data.get("session", {}).get("current_scene")
    if scene is not None:
        scene.setdefault("custom_created", 0)
    last = data.get("session", {}).get("last_combat")
    if last is not None:
        # бой уже завершён без трофеев: задним числом не выдаём
        last.setdefault("gear", [])
        last.setdefault("gear_looted", True)
    return data
