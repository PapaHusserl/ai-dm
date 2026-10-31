# Помощники тестов следопыта 2-5 ур. (не фикстуры). Герой -- Грей из пака Вейл (человек-следопыт
# 1 ур.): ЛОВ 17, МДР 15, ТЕЛ 13; владения: скрытность, выживание, запугивание, восприятие,
# проницательность, природа; снаряжение -- длинный лук и кожаный доспех, скимитар в рюкзаке.
from ai_dm.game.starter import ranger_choices
from ai_dm.rules.builder import build_character
from ai_dm.rules.progression import level_up
from ai_dm.state.creature import CreatureState
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState


def make_ranger(registry):
    return build_character(ranger_choices("hero"), registry)


def ranger_at(registry, level):
    # поднимает по числам (average), без выборов уровня; экспертиза 2 ур. считается выбранной
    # с 3 уровня (иначе required_choices добирает её, решение 26 К2)
    hero = make_ranger(registry)
    while hero.sheet.level < level:
        level_up(hero, registry, hp_method="average")
        if hero.sheet.level == 3:
            hero.sheet.skill_expertise = ["stealth"]
    return hero


def make_class_hero(class_id, abilities):
    # герой без сборки через builder: хватает для level_up (кость хитов и ячейки)
    sheet = CharacterSheet(
        species_id="human", classes=[ClassLevel(class_id=class_id)], level_history=[class_id],
        background=BackgroundSpec(
            name="Тест", abilities=["str", "dex", "con"], skills=["athletics", "stealth"],
            tool="dice_set", feat="alert",
        ),
        abilities=abilities,
    )
    return HeroState(
        id="h1", ordinal=1, name="Тест", sheet=sheet,
        creature=CreatureState(hp_current=10, hp_max=10),
    )
