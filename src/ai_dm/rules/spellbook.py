from ai_dm.rules.derived import cantrip_limit, class_cantrips, spell_slots_for

# выборы уровня, которые кладутся в known_of() (заговоры, книга волшебника, Знаток воплощения)
PICK_KEYS = ("cantrip", "spellbook", "savant_spell")
SAVANT_FEATURE = "evocation_savant"
# сколько заклинаний воплощения подвид вносит в книгу на уровне героя
SAVANT_PICKS = {3: 2, 5: 1}


def cantrip_growth(char_class, level: int) -> int:
    # на сколько на этом уровне растёт число заговоров класса
    casting = char_class.spellcasting
    return class_cantrips(casting, level) - class_cantrips(casting, level - 1)


def book_growth(char_class) -> int:
    # сколько заклинаний вносится в книгу волшебника за уровень
    casting = char_class.spellcasting
    if casting is None or not casting.spellbook:
        return 0
    return casting.spellbook_per_level


def savant_due(registry, subclass_id, level: int) -> int:
    # заклинания воплощения в книгу от подкласса с умением «Знаток воплощения»
    if subclass_id is None:
        return 0
    subclass = registry.get("subclass", subclass_id)
    if not any(r.feature == SAVANT_FEATURE and r.level <= level for r in subclass.features):
        return 0
    return SAVANT_PICKS.get(level, 0)


def picks_due(hero, registry, key, level, subclass_id=None) -> int:
    # сколько вариантов ключа key (PICK_KEYS) герой выбирает на уровне level
    char_class = registry.get("class", hero.sheet.class_id)
    if key == "cantrip":
        return cantrip_growth(char_class, level)
    if key == "spellbook":
        return book_growth(char_class)
    return savant_due(registry, subclass_id or hero.sheet.subclass_id, level)


def picks_missing(hero, registry, choices, key) -> bool:
    due = picks_due(hero, registry, key, hero.sheet.level, choices.subclass_id)
    return len(choices.feature_choices.get(key, [])) < due


def picked(choices, *keys) -> list[str]:
    result = []
    for key in keys:
        result += choices.feature_choices.get(key, []) if choices else []
    return result


def max_circle(hero, registry) -> int:
    spellcasting = registry.get("class", hero.sheet.class_id).spellcasting
    if spellcasting is None:
        return 0
    return max(spell_slots_for(registry, spellcasting.progression, hero.sheet.level), default=0)


def known_cantrips(hero, registry) -> list[str]:
    class_id = hero.sheet.class_id
    spells = [registry.get("spell", s) for s in hero.sheet.known_of()]
    return [s.id for s in spells if s.level == 0 and class_id in s.classes]


def cantrip_candidates(hero, registry, choices) -> list[str]:
    # заговоры класса, которых герой ещё не знает
    sheet = hero.sheet
    taken = set(sheet.known_of()) | set(picked(choices, "cantrip"))
    return [
        s.id for s in registry.all("spell")
        if sheet.class_id in s.classes and s.level == 0 and s.id not in taken
    ]


def book_candidates(hero, registry, choices, school=None) -> list[str]:
    # заклинания класса 1+ круга по ячейкам героя, которых нет в книге (school -- только эта школа)
    sheet = hero.sheet
    circle = max_circle(hero, registry)
    taken = set(sheet.known_of()) | set(picked(choices, *PICK_KEYS))
    return [
        s.id for s in registry.all("spell")
        if sheet.class_id in s.classes and 1 <= s.level <= circle and s.id not in taken
        and (school is None or s.school == school)
    ]


def savant_candidates(hero, registry, choices) -> list[str]:
    return book_candidates(hero, registry, choices, school="evocation")


def book_errors(hero, registry, choices, needed) -> list[tuple[str, str]]:
    # заговоры, книга и Знаток воплощения при повышении уровня (feature_choices[PICK_KEYS])
    errors = []
    allowed = {
        "cantrip": cantrip_candidates(hero, registry, None),
        "spellbook": book_candidates(hero, registry, None),
        "savant_spell": savant_candidates(hero, registry, None),
    }
    seen = []
    for key in PICK_KEYS:
        picks = choices.feature_choices.get(key, [])
        if not picks:
            continue
        if key not in needed:
            errors.append((f"{key}_invalid", f"выбор {key} на этом уровне не делается"))
            continue
        due = picks_due(hero, registry, key, hero.sheet.level, choices.subclass_id)
        errors += pick_errors(key, picks, due, allowed[key], seen)
        seen += picks
    if choices.feature_choices.get("cantrip"):
        limit = cantrip_limit(hero, registry)
        total = len(known_cantrips(hero, registry)) + len(choices.feature_choices["cantrip"])
        if total > limit:
            errors.append(("cantrip_invalid", f"заговоров больше {limit}"))
    return errors


def pick_errors(key, picks, due, allowed, seen) -> list[tuple[str, str]]:
    # число выборов, повторы (в том числе между ключами) и допустимость каждого
    errors = []
    if len(picks) > due:
        errors.append((f"{key}_invalid", f"{key}: не больше {due}"))
    for spell_id in picks:
        if spell_id in seen or picks.count(spell_id) > 1:
            errors.append((f"{key}_invalid", f"заклинание выбрано дважды: {spell_id}"))
        elif spell_id not in allowed:
            errors.append((f"{key}_invalid", f"недоступно: {spell_id}"))
    return errors
