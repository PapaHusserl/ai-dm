import copy

# литералы заморожены в v8: миграция не зависит от текущих моделей
ROMANCE = ["", "нет", "намёки", "чувственно", "откровенно"]


def migrate_v7_to_v8(data: dict, context=None) -> dict:
    # шкала романтики 1-4: старое «есть» (верх шкалы) -> «откровенно», мусор -> ""
    data = copy.deepcopy(data)
    tone = data.get("world", {}).get("tone")
    if tone is not None:
        value = tone.get("romance", "")
        if value == "есть":
            tone["romance"] = "откровенно"
        elif value not in ROMANCE:
            tone["romance"] = ""
    return data
