import copy


def migrate_v12_to_v13(data: dict, context=None) -> dict:
    # схема v13: DeathRecord.cause + "left" (уход NPC без причины, ФС П3); данных не меняет
    return copy.deepcopy(data)
