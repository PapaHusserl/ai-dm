import copy


def migrate_v17_to_v18(data: dict, context=None) -> dict:
    # схема v18: Location.hostile / traps / hidden / garrison (шаг 262 П1);
    # поля с default, данных не меняет
    return copy.deepcopy(data)
