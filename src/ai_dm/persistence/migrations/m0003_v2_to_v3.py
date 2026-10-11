import copy

# литералы заморожены в v3: миграция не зависит от текущих моделей
CHAPTER_KEYS = {"id", "number", "title", "started_at_s", "scene_count", "closed_reason"}
TONE_SCALES = {
    "violence": ["мягко", "реалистично", "жестоко"],
    "horror": ["нет", "умеренно", "сильно"],
    "romance": ["нет", "намёки", "есть"],
    "language": ["сдержанно", "грубо"],
}
DAY = 86400


def chapter_or_none(item):
    # форма ChapterState: иначе None (игра откроет главу 1 при загрузке)
    if not isinstance(item, dict) or not set(item) <= CHAPTER_KEYS:
        return None
    if type(item.get("number")) is not int or not isinstance(item.get("title"), str):
        return None
    chapter = dict(item)
    chapter.setdefault("id", f"ch_{chapter['number']}")
    chapter.setdefault("started_at_s", 0)
    chapter.setdefault("scene_count", 0)
    chapter.setdefault("closed_reason", None)
    return chapter


def convert_tone(tone):
    notes = []
    for scale, allowed in TONE_SCALES.items():
        value = tone.get(scale, "")
        if value != "":
            notes.append(f"{scale}: {value}")
        if value not in allowed:
            tone[scale] = ""
    old = tone.get("notes", "")
    if notes:
        tone["notes"] = "; ".join([old] * bool(old) + notes)
    else:
        tone["notes"] = old


def convert_scenes(items):
    result = []
    for number, item in enumerate(items, start=1):
        if not isinstance(item, dict) or not isinstance(item.get("summary"), str):
            continue
        result.append({
            "id": item.get("id", f"sc_{number}"),
            "chapter_id": item.get("chapter_id", ""),
            "title": item.get("title", ""),
            "summary": item["summary"],
            "at_s": item.get("at_s", 0),
        })
    return result


def convert_chapters(items):
    result = []
    for number, item in enumerate(items, start=1):
        if not isinstance(item, dict) or not isinstance(item.get("summary"), str):
            continue
        result.append({
            "id": item.get("id", f"ch_{number}"),
            "number": item.get("number", number),
            "title": item.get("title", ""),
            "summary": item["summary"],
        })
    return result


def convert_entries(items):
    result = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("text"), str):
            continue
        if "at_s" in item:
            at_s = item["at_s"]
        elif "day" in item:
            at_s = (item["day"] - 1) * DAY
        else:
            at_s = 0
        result.append({"at_s": at_s, "kind": "imported", "text": item["text"], "refs": []})
    return result


def migrate_v2_to_v3(data: dict, context=None) -> dict:
    # типизированные глава, выжимки, хроника, tone; новые поля берут значения моделей по умолчанию
    data = copy.deepcopy(data)
    session = data["session"]
    session["current_chapter"] = chapter_or_none(session.get("current_chapter"))
    session["boundary_pending"] = False
    world = data["world"]
    # все миры этапа 2 -- Вейл
    if world.get("campaign_id") is None and str(world.get("world_id", "")).startswith("vale-"):
        world["campaign_id"] = "vale"
        data["manifest"]["campaign_id"] = "vale"
    # last_season и last_year инициализирует первый тик (П5)
    world["sim"] = {"last_day": world.get("clock", {}).get("now_s", 0) // DAY}
    convert_tone(world.setdefault("tone", {}))
    world_text = world.get("settings", {}).get("world_text")
    world["lore"] = {"world_text": world_text if isinstance(world_text, str) else "", "truths": ""}
    memory = data["memory"]
    memory["scenes"] = convert_scenes(memory.get("scenes", []))
    memory["chapters"] = convert_chapters(memory.get("chapters", []))
    data["chronicle"]["entries"] = convert_entries(data["chronicle"].get("entries", []))
    return data
