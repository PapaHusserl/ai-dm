from ai_dm.protocol.handlers.resources import USE_EFFECTS
from ai_dm.rules.inventory import ARMOR_MINUTES, SLOTS, find_item, item_totals

SLOT_WORDS = {
    "доспех": "armor", "броня": "armor", "armor": "armor",
    "щит": "shield", "shield": "shield",
    "правая": "main_hand", "правую": "main_hand", "оружие": "main_hand", "main_hand": "main_hand",
    "левая": "off_hand", "левую": "off_hand", "off_hand": "off_hand",
}


def minutes_for(registry, item_id, off) -> int:
    # вне боя: минуты на надеть/снять доспех по SRD; щит -- 1 минута (решение проектировщика)
    found = find_item(registry, item_id)
    if found is None or found[0] != "armor":
        return 0
    if found[1].category == "shield":
        return 1
    return ARMOR_MINUTES[found[1].category][int(off)]


def drinkable(found) -> bool:
    return found[0] == "item" and bool(found[1].effects) and found[1].effects[0].type in USE_EFFECTS


def equippable(found) -> bool:
    return found[0] in ("weapon", "armor")


def find_entry(hero, registry, text, accepts):
    # предмет инвентаря по id или названию (целиком, иначе по части); (id, None) или (None, текст)
    wanted = text.casefold()
    exact = []
    partial = []
    names = {}
    for item_id in item_totals(hero):
        found = find_item(registry, item_id)
        if found is None or not accepts(found):
            continue
        item = found[1]
        titles = [item_id.casefold(), item.name.casefold()]
        if found[0] == "item" and item.short_name:
            titles.append(item.short_name.casefold())
        names[item_id] = item.name
        if wanted in titles:
            exact.append(item_id)
        elif any(wanted in title for title in titles):
            partial.append(item_id)
    chosen = exact or partial
    if not chosen:
        return None, f"В инвентаре нет подходящего предмета: {text}."
    if len(chosen) > 1:
        return None, "Уточните, какой: " + ", ".join(names[i] for i in chosen) + "."
    return chosen[0], None


def name_of(registry, item_id) -> str:
    return find_item(registry, item_id)[1].name


def refusal_text(error, registry) -> str:
    # отказ rules: «<причина>: <id>» -> та же причина с названием предмета
    reason, _, item_id = str(error).rpartition(": ")
    if reason and find_item(registry, item_id) is not None:
        return f"{reason}: {name_of(registry, item_id)}"
    return str(error)


def worn_slot(hero, registry, text):
    # слот по слову («щит», «левая») или названию надетой вещи (первый подходящий); None -- не понял
    wanted = text.casefold()
    if wanted in SLOT_WORDS:
        return SLOT_WORDS[wanted]
    for slot in SLOTS:
        worn = getattr(hero.equipped, slot)
        if worn is not None and wanted in (worn, name_of(registry, worn).casefold()):
            return slot
    return None


def slot_of(found, left):
    kind, item = found
    if kind == "weapon":
        return "off_hand" if left else "main_hand"
    return "shield" if item.category == "shield" else "armor"
