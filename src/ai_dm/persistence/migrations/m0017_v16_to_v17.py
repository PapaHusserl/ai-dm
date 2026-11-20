import copy


def migrate_v16_to_v17(data: dict, context=None) -> dict:
    # схема v17: Journey.walked_s (М0 П3а); поле с default, данных не меняет
    return copy.deepcopy(data)
