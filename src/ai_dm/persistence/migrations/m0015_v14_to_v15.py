import copy


def migrate_v14_to_v15(data: dict, context=None) -> dict:
    # схема v15: HeroState.minions (призванные существа, К3б П4); поле с default, данных не меняет
    return copy.deepcopy(data)
