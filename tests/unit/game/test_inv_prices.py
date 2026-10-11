# Торговля, партия Т4 (docs/TRADE-PLAN.md, разд. 5, В-Т5): /inv показывает цену экземпляра.
#   У каждой строки с cost_cp > 0 в хвосте «— 1 зм» (полная цена экземпляра за штуку, не цена
#   продажи); cost_cp == 0 -- хвоста нет; сюжетные предметы показывают цену как раньше
#   (в скобках у описания), второй раз цена не дублируется.
from ai_dm.game.sheet_text import inv_lines
from ai_dm.rules.custom_items import world_registry
from ai_dm.rules.inventory import add_item
from ai_dm.state.creature import CreatureState
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState
from ai_dm.state.world import CustomItem


def make_hero():
    sheet = CharacterSheet(
        species_id="human",
        classes=[ClassLevel(class_id="fighter")], level_history=["fighter"] * 1,
        background=BackgroundSpec(
            name="Солдат",
            abilities=["str", "dex", "con"],
            skills=["athletics", "intimidation"],
            tool="dice_set",
            feat="savage_attacker",
        ),
        abilities={"str": 17, "dex": 13, "con": 15, "int": 8, "wis": 10, "cha": 12},
    )
    return HeroState(
        id="h1", ordinal=1, name="Арн", sheet=sheet,
        creature=CreatureState(hp_current=12, hp_max=12),
    )


def row(lines, text):
    return [line for line in lines if text in line.casefold()]


def test_worn_scimitar_shows_its_price(registry):
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=100, quality="worn")
    line = row(inv_lines(hero, registry, "0 мм"), "поношенн")[0]
    assert line.endswith("— 1 зм")


def test_price_is_per_item_not_per_stack(registry):
    hero = make_hero()
    add_item(hero, "scimitar", 2, cost_cp=100, quality="worn")
    line = row(inv_lines(hero, registry, "0 мм"), "поношенн")[0]
    assert "x2" in line
    assert line.endswith("— 1 зм")


def test_price_is_not_the_sell_price(registry):
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=200, quality="worn")
    line = row(inv_lines(hero, registry, "0 мм"), "поношенн")[0]
    assert line.endswith("— 2 зм")


def test_item_without_price_has_no_tail(registry):
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=0, quality="worn")
    line = row(inv_lines(hero, registry, "0 мм"), "поношенн")[0]
    assert "—" not in line
    assert "зм" not in line and "мм" not in line


def test_each_stack_has_its_own_price(registry):
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=2500)
    add_item(hero, "scimitar", cost_cp=100, quality="worn")
    lines = inv_lines(hero, registry, "0 мм")
    assert row(lines, "поношенн")[0].endswith("— 1 зм")
    new = [x for x in lines if "кимитар" in x and "поношенн" not in x.casefold()][0]
    assert new.endswith("— 25 зм")


def test_priced_armor_shows_price(registry):
    hero = make_hero()
    add_item(hero, "shield", cost_cp=1000)
    line = row(inv_lines(hero, registry, "0 мм"), "щит")[0]
    assert line.endswith("— 10 зм")


def test_priced_gear_shows_price(registry):
    hero = make_hero()
    add_item(hero, "quiver", cost_cp=100)
    line = row(inv_lines(hero, registry, "0 мм"), "колчан")[0]
    assert line.endswith("1 зм")


def test_money_line_is_unchanged(registry):
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=100)
    assert inv_lines(hero, registry, "7 зм")[-1] == "Деньги: 7 зм"


class World:
    def __init__(self):
        self.custom_items = {}


def test_quest_item_keeps_old_price_format_without_duplicate(registry):
    world = World()
    world.custom_items["custom_1"] = CustomItem(
        id="custom_1", name="Ржавый ключ", description="Ключ от ворот", quest=True, created_s=0
    )
    hero = make_hero()
    add_item(hero, "custom_1", cost_cp=500)
    lines = inv_lines(hero, world_registry(registry, world), "0 мм")
    line = row(lines, "ржавый ключ")[0]
    assert "(5 зм)" in line
    assert line.count("5 зм") == 1


def test_quest_item_without_price_has_no_price(registry):
    world = World()
    world.custom_items["custom_1"] = CustomItem(
        id="custom_1", name="Ржавый ключ", description="Ключ от ворот", quest=True, created_s=0
    )
    hero = make_hero()
    add_item(hero, "custom_1", cost_cp=0)
    lines = inv_lines(hero, world_registry(registry, world), "0 мм")
    assert "зм" not in row(lines, "ржавый ключ")[0]


def test_price_comes_after_effects_with_comma(registry):
    hero = make_hero()
    add_item(hero, "potion_of_healing", cost_cp=5000)
    line = row(inv_lines(hero, registry, "0 мм"), "зелье лечения")[0]
    assert "—" in line
    assert line.endswith(", 50 зм")


def test_price_of_one_copper_is_shown(registry):
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=1)
    line = row(inv_lines(hero, registry, "0 мм"), "скимитар")[0]
    assert line.endswith("— 1 мм")
