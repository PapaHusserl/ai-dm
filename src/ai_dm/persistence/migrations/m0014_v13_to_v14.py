import copy

# стрелы стали поштучными (docs/plan-bp.md): было «Стрелы (20 шт.)» за 100 мед., стало 5 за стрелу
PACK_SIZE = 20


def migrate_v13_to_v14(data: dict, context=None) -> dict:
    # схема v14 не меняется; у героев запись arrows: qty *= 20, cost_cp //= 20
    data = copy.deepcopy(data)
    for hero in data.get("heroes", []):
        for entry in hero.get("inventory", []):
            if entry.get("item_id") == "arrows":
                entry["qty"] *= PACK_SIZE
                entry["cost_cp"] //= PACK_SIZE
    return data
