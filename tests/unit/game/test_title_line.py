# К0б (K0-PLAN A8): заголовок листа героя -- порог следующего уровня берётся из таблицы xp,
# на потолке max_level(registry) = 20 части «/порог» нет.
from ranger_kit import make_class_hero

from ai_dm.game.sheet_text import title_line

SCORES = {"str": 15, "dex": 13, "con": 14, "int": 8, "wis": 10, "cha": 12}


def hero_at(level, xp):
    hero = make_class_hero("fighter", SCORES)
    hero.sheet.primary.level = level
    hero.sheet.level_history = ["fighter"] * level
    hero.sheet.xp = xp
    return hero


def test_title_line_at_level_20_has_no_threshold(registry):
    assert title_line(hero_at(20, 355000), registry).endswith("опыт 355000")


def test_title_line_at_level_20_does_not_show_slash(registry):
    assert "/" not in title_line(hero_at(20, 400000), registry)


def test_title_line_at_level_5_shows_threshold_of_level_6(registry):
    assert title_line(hero_at(5, 7000), registry).endswith("опыт 7000/14000")


def test_title_line_at_level_19_shows_threshold_of_level_20(registry):
    assert title_line(hero_at(19, 310000), registry).endswith("опыт 310000/355000")


def test_title_line_at_level_1_shows_threshold_of_level_2(registry):
    assert title_line(hero_at(1, 10), registry).endswith("опыт 10/300")


def test_title_line_full_text_without_subclass(registry):
    text = title_line(hero_at(20, 355000), registry)
    assert text == "Тест — человек, воин 20 ур., опыт 355000"


def test_title_line_full_text_with_subclass_and_threshold(registry):
    hero = make_class_hero("ranger", SCORES)
    hero.sheet.primary.level = 3
    hero.sheet.level_history = ["ranger"] * 3
    hero.sheet.primary.subclass_id = "beast_master"
    hero.sheet.xp = 900
    name = registry.get("subclass", "beast_master").name
    assert title_line(hero, registry) == f"Тест — человек, следопыт 3 ур. ({name}), опыт 900/2700"
