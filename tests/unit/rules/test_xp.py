# Ожидаемый API: ai_dm.rules.xp (этап 2, партия 1; ТЗ 2.3 «Опыт»)
#   combat_xp(defeated_monster_ids: list[str], registry) -> int
#       сумма опыта за побеждённых: для каждого id (повтор id считается каждый раз)
#       registry.get("monster", id).cr -> таблица "cr_xp" (CR -- строка: "1/8", "1/4", "1").
#       Пустой список -> 0; неизвестный id -> KeyError (как registry.get).
#       Данные SRD-слоя: guard (CR 1/8) = 25, goblin_warrior (CR 1/4) = 50,
#       goblin_boss (CR 1) = 200; критерий этапа 2: 2 гоблина + босс = 300. Делить опыт между
#       героями -- дело вызывающего.
#   quest_xp(hero: HeroState, scale: str, registry, cfg: RulesConfig) -> int
#       scale: "minor" | "medium" | "major" -> доля cfg.xp.quest_{scale}_percent (10 / 25 / 50).
#       Доля считается от размера текущего уровня героя:
#       xp_for_level(level + 1) - xp_for_level(level), целочисленно,
#       округление вниз: (span * percent) // 100. Уровень 1 (300): 30 / 75 / 150;
#       уровень 2 (600): 60 / 150 / 300; уровень 4 (3800): 380 / 950 / 1900.
#       Уровень 20 (максимум, max_level(registry)) -> 0; на 5 и 19 доля от размера уровня
#       (7500 / 50 000). Неизвестный scale -> ValueError. hero не мутируется
#       (начисляет вызывающий). Процент берётся из cfg, не из констант.
import pytest

from ai_dm.config.settings import load_rules_config
from ai_dm.rules.xp import combat_xp, quest_xp
from ai_dm.state.creature import CreatureState
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState


def make_hero(level=1, xp=0):
    sheet = CharacterSheet(
        species_id="human",
        classes=[ClassLevel(class_id="fighter", level=level)], level_history=["fighter"] * level,
        background=BackgroundSpec(
            name="Солдат",
            abilities=["str", "dex", "con"],
            skills=["athletics", "intimidation"],
            tool="dice_set",
            feat="savage_attacker",
        ),
        abilities={"str": 17, "dex": 13, "con": 15, "int": 8, "wis": 10, "cha": 12},
        xp=xp,
    )
    return HeroState(
        id="h1", ordinal=1, name="Арн", sheet=sheet,
        creature=CreatureState(hp_current=12, hp_max=12),
    )


# опыт за бой

def test_empty_defeated_list_gives_zero(registry):
    assert combat_xp([], registry) == 0


@pytest.mark.parametrize(
    "monster_id, xp", [("guard", 25), ("goblin_warrior", 50), ("goblin_boss", 200)]
)
def test_single_monster_gives_cr_xp(monster_id, xp, registry):
    assert combat_xp([monster_id], registry) == xp


def test_two_goblins_and_boss_give_300(registry):
    assert combat_xp(["goblin_warrior", "goblin_warrior", "goblin_boss"], registry) == 300


def test_same_id_is_counted_each_time(registry):
    assert combat_xp(["guard"] * 4, registry) == 100


def test_order_does_not_matter(registry):
    ids = ["goblin_boss", "guard", "goblin_warrior"]
    assert combat_xp(ids, registry) == combat_xp(list(reversed(ids)), registry) == 275


def test_unknown_monster_raises_key_error(registry):
    with pytest.raises(KeyError):
        combat_xp(["no_such_monster"], registry)


def test_combat_xp_returns_int(registry):
    assert type(combat_xp(["guard"], registry)) is int


# опыт за квест

@pytest.mark.parametrize(
    "level, scale, expected",
    [
        (1, "minor", 30), (1, "medium", 75), (1, "major", 150),
        (2, "minor", 60), (2, "medium", 150), (2, "major", 300),
        (4, "minor", 380), (4, "medium", 950), (4, "major", 1900),
    ],
)
def test_quest_xp_is_share_of_current_level_span(level, scale, expected, registry, cfg):
    assert quest_xp(make_hero(level=level), scale, registry, cfg) == expected


def test_quest_xp_does_not_depend_on_current_xp(registry, cfg):
    assert quest_xp(make_hero(level=2, xp=300), "minor", registry, cfg) == 60
    assert quest_xp(make_hero(level=2, xp=850), "minor", registry, cfg) == 60


@pytest.mark.parametrize("scale", ["minor", "medium", "major"])
def test_max_level_hero_gets_no_quest_xp(scale, registry, cfg):
    assert quest_xp(make_hero(level=20, xp=355000), scale, registry, cfg) == 0


@pytest.mark.parametrize(
    "level, scale, expected",
    [
        (5, "minor", 750), (5, "major", 3750),
        (19, "minor", 5000), (19, "medium", 12500), (19, "major", 25000),
    ],
)
def test_quest_xp_above_level_4_is_share_of_span(level, scale, expected, registry, cfg):
    assert quest_xp(make_hero(level=level), scale, registry, cfg) == expected


def test_quest_xp_scales_are_ordered(registry, cfg):
    hero = make_hero(level=3)
    minor = quest_xp(hero, "minor", registry, cfg)
    medium = quest_xp(hero, "medium", registry, cfg)
    major = quest_xp(hero, "major", registry, cfg)
    assert 0 < minor < medium < major


def test_quest_xp_takes_percent_from_config(registry):
    cfg = load_rules_config("[xp]\nquest_minor_percent = 20\n")
    assert quest_xp(make_hero(level=1), "minor", registry, cfg) == 60


def test_quest_xp_rounds_down(registry):
    cfg = load_rules_config("[xp]\nquest_minor_percent = 11\n")
    assert quest_xp(make_hero(level=1), "minor", registry, cfg) == 33


def test_unknown_scale_raises_value_error(registry, cfg):
    with pytest.raises(ValueError):
        quest_xp(make_hero(), "huge", registry, cfg)


def test_quest_xp_does_not_change_hero(registry, cfg):
    hero = make_hero(level=2, xp=400)
    quest_xp(hero, "major", registry, cfg)
    assert (hero.sheet.xp, hero.sheet.level) == (400, 2)


def test_quest_xp_returns_int(registry, cfg):
    assert type(quest_xp(make_hero(), "minor", registry, cfg)) is int
