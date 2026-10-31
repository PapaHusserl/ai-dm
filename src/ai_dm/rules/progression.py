import copy
from typing import Literal

from ai_dm.content.models.common import ABILITIES, SKILLS
from ai_dm.rules.derived import (
    always_prepared,
    by_level,
    hero_feature_ids,
    mastery_limit,
    prepared_limit,
    resource_maxes,
    spell_slots_for,
    table_value,
    weapon_proficient,
)
from ai_dm.state.creature import ResourcePool
from ai_dm.state.hero import LevelChoices

# уровень, на котором выбирается подкласс (у всех классов SRD)
SUBCLASS_LEVEL = 3
ASI_FEAT = "ability_score_improvement"


def max_level(registry) -> int:
    # потолок уровня = старший уровень таблицы опыта
    return max(int(key) for key in registry.get("table", "xp").rows)


def check_level(level: int, registry) -> None:
    top = max_level(registry)
    if level < 1 or level > top:
        raise ValueError(f"уровень вне 1..{top}: {level}")


def xp_for_level(level: int, registry) -> int:
    check_level(level, registry)
    return table_value(registry, "xp", level)


def level_for_xp(xp: int, registry) -> int:
    if xp < 0:
        raise ValueError("опыт не может быть отрицательным")
    result = 1
    for level in range(1, max_level(registry) + 1):
        if xp >= xp_for_level(level, registry):
            result = level
    return result


def proficiency_bonus(level: int, registry) -> int:
    check_level(level, registry)
    return table_value(registry, "proficiency", level)


def can_level_up(hero, registry) -> bool:
    level = hero.sheet.level
    if level >= max_level(registry):
        return False
    return hero.sheet.xp >= xp_for_level(level + 1, registry)


def sync_resources(hero, registry) -> None:
    # заводит недостающие пулы ресурсов; у выросшего максимума текущее растёт на разницу
    resources = hero.creature.resources
    for pool, new_max in resource_maxes(hero, registry).items():
        if pool not in resources:
            resources[pool] = ResourcePool(current=new_max, max=new_max)
            continue
        grow = max(0, new_max - resources[pool].max)
        resources[pool].max = new_max
        resources[pool].current = min(new_max, resources[pool].current + grow)


def hp_gain(hero, registry, hp_method: Literal["average", "roll"], rng) -> int:
    # HP по выбору игрока: average — фиксированное среднее (кость // 2 + 1), по умолчанию;
    # roll — бросок кости хитов (нужен rng). К обоим прибавляется мод. ТЕЛ, итог не меньше 1.
    if hp_method not in ("average", "roll"):
        raise ValueError(f"неизвестный метод HP: {hp_method!r}")
    if hp_method == "roll" and rng is None:
        raise ValueError("для hp_method='roll' нужен rng")
    hit_die = registry.get("class", hero.sheet.class_id).hit_die
    con_mod = (hero.sheet.abilities["con"] - 10) // 2
    base = rng.d(hit_die) if hp_method == "roll" else hit_die // 2 + 1
    return max(1, base + con_mod)


def apply_level(hero, registry, gain: int) -> None:
    sheet = hero.sheet
    sheet.primary.level += 1
    sheet.level_history.append(sheet.primary.class_id)
    hero.creature.hp_max += gain
    hero.creature.hp_current += gain
    sync_resources(hero, registry)


def level_up(
    hero, registry, *, hp_method: Literal["average", "roll"] = "average", rng=None
) -> None:
    # Поднимает уровень на 1. Хватает ли опыта — проверяет вызывающий (can_level_up);
    # здесь проверяется только максимальный уровень.
    if hero.sheet.level >= max_level(registry):
        raise ValueError("максимальный уровень уже достигнут")
    apply_level(hero, registry, hp_gain(hero, registry, hp_method, rng))


def option_features_at(registry, feature_refs, level) -> set[str]:
    # умения с вариантами среди умений данного уровня
    result = set()
    for ref in feature_refs:
        if ref.level == level and registry.get("feature", ref.feature).options:
            result.add(ref.feature)
    return result


def expertise_total(registry, char_class, level: int) -> int:
    # сколько навыков с экспертизой дают умения класса до уровня level (эффект экспертизы)
    total = 0
    for ref in char_class.features:
        if ref.level > level:
            continue
        for effect in registry.get("feature", ref.feature).effects:
            if effect.type == "proficiency" and effect.mode == "expertise":
                total += effect.count or 0
    return total


def expertise_due(hero, registry, level: int) -> int:
    # сколько навыков для экспертизы герой выбирает на уровне level: те, что умение даёт именно
    # на этом уровне, а при недоборе (плут 1 ур. без экспертизы, решение 26) — недостающие
    char_class = registry.get("class", hero.sheet.class_id)
    now = expertise_total(registry, char_class, level)
    new = now - expertise_total(registry, char_class, level - 1)
    return max(new, now - len(hero.sheet.skill_expertise))


def mastery_growth(char_class, level: int) -> int:
    # на сколько на этом уровне растёт число видов оружия с мастерством (воин)
    table = char_class.weapon_mastery_by_level
    if table is None:
        return 0
    return by_level(table, level) - by_level(table, level - 1)


def required_choices(hero, registry, level: int) -> set[str]:
    # что игрок обязан выбрать при получении уровня level (после level_up):
    # fighting_style, expertise, weapon_mastery, subclass, asi_or_feat и id умений с вариантами
    char_class = registry.get("class", hero.sheet.class_id)
    result = set()
    for ref in char_class.features:
        if ref.level != level:
            continue
        if ref.feature == "fighting_style":
            result.add("fighting_style")
        if ref.feature == "ability_score_improvement":
            result.add("asi_or_feat")
    if expertise_due(hero, registry, level) > 0:
        result.add("expertise")
    if mastery_growth(char_class, level) > 0:
        result.add("weapon_mastery")
    result |= option_features_at(registry, char_class.features, level)
    if hero.sheet.subclass_id is not None:
        subclass = registry.get("subclass", hero.sheet.subclass_id)
        result |= option_features_at(registry, subclass.features, level)
    elif level == SUBCLASS_LEVEL and registry.subclasses_of(hero.sheet.class_id):
        result.add("subclass")
    return result


# ключи required_choices, которые не являются умениями с вариантами
FIXED_CHOICES = {"fighting_style", "expertise", "weapon_mastery", "asi_or_feat", "subclass"}


def needed_choices(hero, registry, choices) -> set[str]:
    # обязательные выборы уровня с учётом подкласса, выбираемого в этих же выборах
    needed = required_choices(hero, registry, hero.sheet.level)
    found = [s for s in registry.subclasses_of(hero.sheet.class_id) if s.id == choices.subclass_id]
    if "subclass" in needed and found:
        needed.discard("subclass")
        needed |= option_features_at(registry, found[0].features, hero.sheet.level)
    return needed


def expertise_missing(hero, registry, choices) -> bool:
    return len(choices.expertise) < expertise_due(hero, registry, hero.sheet.level)


def mastery_missing(hero, registry, choices) -> bool:
    growth = mastery_growth(registry.get("class", hero.sheet.class_id), hero.sheet.level)
    return len(choices.feature_choices.get("weapon_mastery", [])) < growth


def missing_choices(hero, registry, choices) -> list[str]:
    # сообщения о том, чего не хватает в выборах (для старта пака и меню игры)
    needed = needed_choices(hero, registry, choices)
    result = []
    if "subclass" in needed:
        result.append("не выбран подкласс")
    if "fighting_style" in needed and choices.fighting_style is None:
        result.append("не выбран боевой стиль")
    if "expertise" in needed and expertise_missing(hero, registry, choices):
        result.append("не выбрана экспертиза")
    if "weapon_mastery" in needed and mastery_missing(hero, registry, choices):
        result.append("не выбрано мастерство оружия")
    if "asi_or_feat" in needed and choices.asi is None and choices.feat is None:
        result.append("нужно выбрать повышение характеристик или черту")
    for feature_id in sorted(needed - FIXED_CHOICES):
        if feature_id not in choices.feature_choices:
            result.append(f"не выбран вариант умения {feature_id}")
    return result


def next_choice(hero, registry, choices) -> str | None:
    # следующий невыбранный пункт в порядке меню: стиль, экспертиза, мастерство оружия, подкласс,
    # варианты умений, повышение характеристик; None -- все обязательные выборы сделаны
    needed = needed_choices(hero, registry, choices)
    if "fighting_style" in needed and choices.fighting_style is None:
        return "fighting_style"
    if "expertise" in needed and expertise_missing(hero, registry, choices):
        return "expertise"
    if "weapon_mastery" in needed and mastery_missing(hero, registry, choices):
        return "weapon_mastery"
    if "subclass" in needed:
        return "subclass"
    for feature_id in sorted(needed - FIXED_CHOICES):
        if feature_id not in choices.feature_choices:
            return feature_id
    if "asi_or_feat" in needed and choices.asi is None and choices.feat is None:
        return "asi_or_feat"
    if spell_candidates(hero, registry, choices) and spells_left(hero, registry, choices) > 0:
        return "spells"
    return None


def spells_left(hero, registry, choices) -> int:
    # сколько заклинаний ещё можно подготовить до лимита уровня (Метка не считается)
    limit = prepared_limit(hero, registry)
    if limit is None:
        return 0
    return limit - len(hero.sheet.prepared_of()) - len(choices.spells_add)


def spell_candidates(hero, registry, choices) -> list[str]:
    # заклинания класса 1+ круга, доступные по ячейкам и ещё не подготовленные
    sheet = hero.sheet
    spellcasting = registry.get("class", sheet.class_id).spellcasting
    if spellcasting is None or spellcasting.prepared_by_level is None:
        return []
    max_circle = max(spell_slots_for(registry, spellcasting.progression, sheet.level), default=0)
    taken = sheet.prepared_of() + choices.spells_add + always_prepared(hero, registry)
    return [
        spell.id for spell in registry.all("spell")
        if sheet.class_id in spell.classes and 1 <= spell.level <= max_circle
        and spell.id not in taken
    ]


def mastery_candidates(hero, registry, choices) -> list[str]:
    # оружие с мастерством, которым герой владеет и которого нет среди его мастерств;
    # огнестрел (world_only) — только если лежит в инвентаре
    char_class = registry.get("class", hero.sheet.class_id)
    picked = choices.feature_choices.get("weapon_mastery", []) if choices else []
    taken = hero.sheet.weapon_masteries + picked
    owned = {entry.item_id for entry in hero.inventory}
    result = []
    for weapon in registry.all("weapon"):
        if weapon.source == "world" or weapon.mastery is None or weapon.id in taken:
            continue
        if weapon.world_only and weapon.id not in owned:
            continue
        if weapon_proficient(char_class, weapon):
            result.append(weapon.id)
    return result


def choice_options(hero, registry, key, choices=None) -> list[str]:
    # варианты для пункта выбора (id для меню); для asi_or_feat: "dex+2", "dex+wis" и id черт
    sheet = hero.sheet
    if key == "fighting_style":
        return [
            f.id for f in registry.all("feat")
            if f.category == "fighting_style" and f.id not in sheet.feats
        ]
    if key == "expertise":
        taken = sheet.skill_expertise + (choices.expertise if choices else [])
        return [s for s in SKILLS if s in sheet.skill_proficiencies and s not in taken]
    if key == "weapon_mastery":
        return mastery_candidates(hero, registry, choices)
    if key == "subclass":
        return [s.id for s in registry.subclasses_of(sheet.class_id)]
    if key == "asi_or_feat":
        result = []
        for number, first in enumerate(ABILITIES):
            if sheet.abilities[first] + 2 <= 20:
                result.append(f"{first}+2")
            for second in ABILITIES[number + 1:]:
                if sheet.abilities[first] + 1 <= 20 and sheet.abilities[second] + 1 <= 20:
                    result.append(f"{first}+{second}")
        for feat in registry.all("feat"):
            free = feat.id not in sheet.feats or feat.repeatable
            if feat.category == "general" and feat.id != ASI_FEAT and free:
                result.append(feat.id)
        return result
    if key == "spells":
        return spell_candidates(hero, registry, choices or LevelChoices(level=sheet.level))
    return list(registry.get("feature", key).options)


def mastery_errors(hero, registry, choices, needed) -> list[tuple[str, str]]:
    # мастерство оружия при повышении уровня (feature_choices["weapon_mastery"])
    picks = choices.feature_choices.get("weapon_mastery", [])
    if not picks:
        return []
    if "weapon_mastery" not in needed:
        return [("mastery_count_invalid", "мастерство оружия на этом уровне не выбирается")]
    limit = mastery_limit(hero, registry)
    errors = []
    if len(hero.sheet.weapon_masteries) + len(picks) > limit or len(set(picks)) != len(picks):
        text = f"мастерство оружия: всего не больше {limit}, без повторов"
        errors.append(("mastery_count_invalid", text))
    allowed = mastery_candidates(hero, registry, None)
    for weapon_id in picks:
        if weapon_id not in allowed:
            errors.append(("mastery_weapon_invalid", f"мастерство оружия недоступно: {weapon_id}"))
    return errors


def choice_errors(hero, registry, choices) -> list[tuple[str, str]]:
    # (код, сообщение) по всем выборам; hero не меняет
    errors = []
    sheet = hero.sheet
    if choices.level != sheet.level:
        text = f"выборы для уровня {choices.level}, у героя {sheet.level}"
        errors.append(("level_mismatch", text))
        return errors
    needed = needed_choices(hero, registry, choices)
    if choices.subclass_id is not None:
        found = [s for s in registry.subclasses_of(sheet.class_id) if s.id == choices.subclass_id]
        if "subclass" not in required_choices(hero, registry, sheet.level):
            errors.append(("subclass_invalid", "подкласс на этом уровне не выбирается"))
        elif not found:
            errors.append(("subclass_invalid", f"нет подкласса у класса: {choices.subclass_id}"))
    # боевой стиль
    style = choices.fighting_style
    if style is not None:
        feat = registry.get("feat", style) if registry.has("feat", style) else None
        if "fighting_style" not in needed:
            errors.append(("fighting_style_invalid", "боевой стиль на этом уровне не выбирается"))
        elif feat is None or feat.category != "fighting_style":
            errors.append(("fighting_style_invalid", f"не боевой стиль: {style}"))
        elif style in sheet.feats:
            errors.append(("fighting_style_invalid", f"стиль уже есть: {style}"))
    # экспертиза
    picks = choices.expertise
    if picks and "expertise" not in needed:
        errors.append(("expertise_invalid", "экспертиза на этом уровне не выбирается"))
    elif picks:
        due = expertise_due(hero, registry, sheet.level)
        if len(picks) > due or len(set(picks)) != len(picks):
            text = f"экспертиза: не больше {due} навыков, без повторов"
            errors.append(("expertise_invalid", text))
        for skill in picks:
            if skill not in SKILLS or skill not in sheet.skill_proficiencies:
                errors.append(("expertise_invalid", f"экспертиза: нет владения навыком {skill}"))
            elif skill in sheet.skill_expertise:
                errors.append(("expertise_invalid", f"экспертиза уже есть: {skill}"))
    # варианты умений
    errors += mastery_errors(hero, registry, choices, needed)
    for feature_id, picks in choices.feature_choices.items():
        if feature_id == "weapon_mastery":
            continue
        if feature_id not in needed - FIXED_CHOICES:
            errors.append(("option_invalid", f"умение {feature_id} на этом уровне не выбирается"))
            continue
        for option in picks:
            if option not in registry.get("feature", feature_id).options:
                errors.append(("option_invalid", f"нет такого варианта: {feature_id} -> {option}"))
    # повышение характеристик или черта
    if "asi_or_feat" not in needed and (choices.asi is not None or choices.feat is not None):
        errors.append(("asi_invalid", "повышение характеристик на этом уровне не выбирается"))
    if choices.asi is not None and choices.feat is not None:
        errors.append(("asi_invalid", "нужно одно из двух: повышение характеристик или черта"))
    if choices.asi is not None and "asi_or_feat" in needed:
        errors += asi_errors(hero, choices.asi)
    if choices.feat is not None and "asi_or_feat" in needed:
        feat = registry.get("feat", choices.feat) if registry.has("feat", choices.feat) else None
        if feat is None or feat.category != "general" or choices.feat == ASI_FEAT:
            errors.append(("feat_invalid", f"нужна общая черта, не повышение: {choices.feat}"))
        elif choices.feat in sheet.feats and not feat.repeatable:
            errors.append(("feat_invalid", f"черта уже есть: {choices.feat}"))
    errors += spell_errors(hero, registry, choices)
    return errors


def asi_errors(hero, asi) -> list[tuple[str, str]]:
    values = sorted(asi.values())
    if values not in ([2], [1, 1]):
        return [("asi_invalid", "повышение: +2 к одной или +1 к двум характеристикам")]
    errors = []
    for ability, value in asi.items():
        if ability not in ABILITIES:
            errors.append(("asi_invalid", f"нет такой характеристики: {ability}"))
        elif hero.sheet.abilities[ability] + value > 20:
            errors.append(("asi_invalid", f"характеристика выше 20: {ability}"))
    return errors


def spell_errors(hero, registry, choices) -> list[tuple[str, str]]:
    always = always_prepared(hero, registry)
    adds = [s for s in choices.spells_add if s not in always]
    if not adds:
        return []
    sheet = hero.sheet
    spellcasting = registry.get("class", sheet.class_id).spellcasting
    if spellcasting is None:
        return [("spells_invalid", "класс не владеет заклинаниями")]
    errors = []
    if len(set(adds)) != len(adds):
        errors.append(("spells_invalid", "заклинания: есть повторы"))
    max_circle = max(spell_slots_for(registry, spellcasting.progression, sheet.level), default=0)
    for spell_id in adds:
        if not registry.has("spell", spell_id):
            errors.append(("spells_invalid", f"неизвестное заклинание: {spell_id}"))
            continue
        spell = registry.get("spell", spell_id)
        if sheet.class_id not in spell.classes:
            errors.append(("spells_invalid", f"заклинание не из списка класса: {spell_id}"))
        elif spell.level < 1:
            errors.append(("spells_invalid", f"заговоры здесь не выбираются: {spell_id}"))
        elif spell.level > max_circle:
            errors.append(("spells_invalid", f"круг заклинания недоступен: {spell_id}"))
        elif spell_id in sheet.prepared_of():
            errors.append(("spells_invalid", f"заклинание уже подготовлено: {spell_id}"))
    limit = prepared_limit(hero, registry)
    if limit is not None and len(sheet.prepared_of()) + len(adds) > limit:
        errors.append(("spells_invalid", f"подготовленных заклинаний больше {limit}"))
    return errors


def apply_level_choices(hero, registry, choices):
    # применяет выборы уровня после level_up; при ошибке героя не меняет (ValidationErrors).
    # Обязательность выбора здесь не проверяется: это missing_choices / next_choice
    # (импорт здесь: builder импортирует этот модуль)
    from ai_dm.rules.builder import ValidationErrors

    errors = choice_errors(hero, registry, choices)
    if errors:
        return ValidationErrors([e[0] for e in errors], [e[1] for e in errors])
    sheet = hero.sheet
    if choices.subclass_id is not None:
        sheet.primary.subclass_id = choices.subclass_id
    if choices.fighting_style is not None:
        sheet.feats.append(choices.fighting_style)
    sheet.skill_expertise += choices.expertise
    sheet.weapon_masteries += choices.feature_choices.get("weapon_mastery", [])
    options = {k: v for k, v in choices.feature_choices.items() if k != "weapon_mastery"}
    sheet.feature_choices.update(copy.deepcopy(options))
    if choices.asi is not None:
        for ability, value in choices.asi.items():
            sheet.abilities[ability] += value
        sheet.feats.append(ASI_FEAT)
    if choices.feat is not None:
        sheet.feats.append(choices.feat)
    for spell_id in choices.spells_add:
        if spell_id in always_prepared(hero, registry):
            continue
        sheet.known_of().append(spell_id)
        sheet.prepared_of().append(spell_id)
    for language in choices.languages:
        if language not in sheet.languages:
            sheet.languages.append(language)
    sync_resources(hero, registry)
    return None


def feature_swap_problem(hero, registry, feature_id, option):
    # смена варианта умения после отдыха (Добыча охотника): (код, сообщение) или None
    if feature_id not in hero_feature_ids(hero, registry):
        return ("no_feature", f"у героя нет умения {feature_id}")
    options = registry.get("feature", feature_id).options
    if not options:
        return ("no_feature", f"у умения {feature_id} нет вариантов")
    if option not in options:
        allowed = ", ".join(options)
        return ("unknown_option", f"нет такого варианта: {option}; допустимые: {allowed}")
    if not hero.sheet.feature_choices.get(feature_id):
        return ("no_choice", f"у умения {feature_id} не выбран вариант")
    if hero.sheet.feature_choices.get(feature_id) == [option]:
        return ("same_option", f"вариант уже выбран: {option}")
    return None


def swap_feature_choice(hero, registry, feature_id, option) -> None:
    hero.sheet.feature_choices[feature_id] = [option]
