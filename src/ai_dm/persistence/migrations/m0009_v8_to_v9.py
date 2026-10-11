import copy


def migrate_sheet(sheet: dict) -> None:
    # класс героя -- список classes; заклинания и выборы умений -- по классам и списками
    if "classes" in sheet:
        return
    class_id = sheet.pop("class_id")
    level = sheet.pop("level", 1)
    sheet["classes"] = [
        {"class_id": class_id, "level": level, "subclass_id": sheet.pop("subclass_id", None)}
    ]
    sheet["level_history"] = [class_id] * level
    sheet["spells_known"] = {class_id: sheet.get("spells_known", [])}
    sheet["spells_prepared"] = {class_id: sheet.get("spells_prepared", [])}
    options = sheet.pop("feature_options", {})
    sheet["feature_choices"] = {key: [value] for key, value in options.items()}
    sheet.setdefault("spells_always_prepared", [])


def migrate_creature(creature: dict, context) -> None:
    # концентрация -- объект с кругом заклинания; временная форма появляется пустой
    spell_id = creature.get("concentration")
    if isinstance(spell_id, str):
        if spell_id not in context.spell_level:
            context.report.append(f"нет заклинания {spell_id!r} в реестре: круг концентрации 1")
        circle = context.spell_level.get(spell_id, 1)
        creature["concentration"] = {"spell_id": spell_id, "circle": circle, "until_s": None}
    creature.setdefault("concentration", None)
    creature.setdefault("temp_form", None)


def hit_dice_key(class_id: str, context) -> str:
    if class_id not in context.class_hit_die:
        context.report.append(f"нет класса {class_id!r} в реестре: кость хитов d8")
    return f"hit_dice:d{context.class_hit_die.get(class_id, 8)}"


def migrate_hero(hero: dict, context) -> None:
    migrate_sheet(hero["sheet"])
    creature = hero["creature"]
    migrate_creature(creature, context)
    resources = creature.get("resources", {})
    if "hit_dice" in resources:
        key = hit_dice_key(hero["sheet"]["classes"][0]["class_id"], context)
        creature["resources"] = {
            (key if name == "hit_dice" else name): pool for name, pool in resources.items()
        }
    companion = hero.pop("companion", None)
    hero.setdefault("companions", [] if companion is None else [companion])
    hero.setdefault("attuned", [])
    hero.setdefault("pending_level", None)


def migrate_holder(holder: dict, context) -> None:
    # NPC и участник боя: снаряжение не задано, существо (если есть) мигрирует
    holder.setdefault("equipment", None)
    if holder.get("creature") is not None:
        migrate_creature(holder["creature"], context)


def migrate_v8_to_v9(data: dict, context) -> dict:
    # схема v9: классы списком, концентрация объектом, спутники списком, pending_level,
    # снаряжение NPC и участников боя; кости хитов по граням (hit_dice:dN)
    data = copy.deepcopy(data)
    for hero in data.get("heroes", []):
        migrate_hero(hero, context)
    for npc in data.get("world", {}).get("npcs", {}).values():
        migrate_holder(npc, context)
    combat = data.get("session", {}).get("active_combat")
    if combat is not None:
        for participant in combat.get("participants", []):
            migrate_holder(participant, context)
    return data
