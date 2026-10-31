from ai_dm.game.starter import fighter_choices, ranger_choices, wizard_choices
from ai_dm.rules.builder import CharacterChoices, build_character
from ai_dm.rules.progression import (
    apply_level_choices,
    choice_options,
    level_up,
    next_choice,
)
from ai_dm.state.hero import LevelChoices

CLASSES = ("fighter", "rogue", "cleric", "wizard", "ranger")


def rogue_choices() -> CharacterChoices:
    return CharacterChoices(
        name="Тень", species_id="human", class_id="rogue", background="soldier",
        ability_method="standard_array",
        ability_scores={"str": 8, "dex": 15, "con": 14, "int": 10, "wis": 12, "cha": 13},
        background_bonus={"dex": 2, "con": 1},
        class_skills=["acrobatics", "insight", "perception", "stealth"],
        weapon_masteries=["dagger", "shortsword"], expertise=["stealth", "perception"],
        species_choices={"skill": "persuasion", "feat": "skilled"},
        feat_choices={"skilled": ["investigation", "history", "medicine"]},
        class_kit="a", hero_id="hero",
    )


def cleric_choices() -> CharacterChoices:
    return CharacterChoices(
        name="Отец Марк", species_id="human", class_id="cleric", background="soldier",
        ability_method="standard_array",
        ability_scores={"str": 10, "dex": 8, "con": 14, "int": 12, "wis": 15, "cha": 13},
        background_bonus={"str": 2, "con": 1}, class_skills=["history", "insight"],
        weapon_masteries=[],
        species_choices={"skill": "stealth", "feat": "skilled"},
        feat_choices={"skilled": ["medicine", "religion", "nature"]},
        spells=["bless", "cure_wounds"], prepared=["bless", "cure_wounds"],
        class_kit="a", hero_id="hero",
    )


def level1_choices(class_id) -> CharacterChoices:
    if class_id == "fighter":
        return fighter_choices("hero")
    if class_id == "wizard":
        return wizard_choices("hero")
    if class_id == "ranger":
        return ranger_choices("hero")
    if class_id == "rogue":
        return rogue_choices()
    if class_id == "cleric":
        return cleric_choices()
    raise ValueError(f"неизвестный класс: {class_id!r}")


def pick(choices, key, options) -> None:
    # первый вариант из списка, детерминированно
    first = options[0]
    if key == "fighting_style":
        choices.fighting_style = first
    elif key == "expertise":
        choices.expertise.append(first)
    elif key == "weapon_mastery":
        choices.feature_choices.setdefault(key, []).append(first)
    elif key == "subclass":
        choices.subclass_id = first
    elif key == "spells":
        choices.spells_add.append(first)
    elif key == "asi_or_feat":
        choices.asi = {first.partition("+")[0]: 2}
    else:
        choices.feature_choices[key] = [first]


def auto_level(hero, registry, level) -> None:
    # поднимает героя до level: средние HP, первые варианты в каждом выборе
    while hero.sheet.level < level:
        level_up(hero, registry, hp_method="average")
        choices = LevelChoices(level=hero.sheet.level)
        key = next_choice(hero, registry, choices)
        while key is not None:
            pick(choices, key, choice_options(hero, registry, key, choices))
            key = next_choice(hero, registry, choices)
        errors = apply_level_choices(hero, registry, choices)
        if errors is not None:
            raise ValueError(f"{hero.sheet.class_id} {hero.sheet.level} ур.: {errors.messages}")


def build_hero(class_id, level, registry):
    hero = build_character(level1_choices(class_id), registry)
    if not hasattr(hero, "sheet"):
        raise ValueError(f"{class_id}: {hero.messages}")
    auto_level(hero, registry, level)
    return hero
