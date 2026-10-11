import copy


def migrate_v3_to_v4(data: dict, context=None) -> dict:
    # умения следопыта 2-5: экспертиза, языки, выбор умений, зверь-спутник
    data = copy.deepcopy(data)
    for hero in data.get("heroes", []):
        sheet = hero["sheet"]
        sheet.setdefault("skill_expertise", [])
        sheet.setdefault("languages", [])
        sheet.setdefault("feature_options", {})
        hero.setdefault("companion", None)
    return data
