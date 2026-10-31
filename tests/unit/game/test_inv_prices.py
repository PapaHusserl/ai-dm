# Торговля, партия Т4 (docs/plan-trade.md, разд. 5, В-Т5): /inv показывает цену экземпляра.
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
    assert line.endswith(", 1 зм")


def test_price_is_per_item_not_per_stack(registry):
    hero = make_hero()
    add_item(hero, "scimitar", 2, cost_cp=100, quality="worn")
    line = row(inv_lines(hero, registry, "0 мм"), "поношенн")[0]
    assert "x2" in line
    assert line.endswith(", 1 зм")


def test_price_is_not_the_sell_price(registry):
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=200, quality="worn")
    line = row(inv_lines(hero, registry, "0 мм"), "поношенн")[0]
    assert line.endswith(", 2 зм")


def test_item_without_price_has_no_tail(registry):
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=0, quality="worn")
    line = row(inv_lines(hero, registry, "0 мм"), "поношенн")[0]
    assert line.endswith("мастерство: Проворство")
    assert "зм" not in line and "мм" not in line


def test_each_stack_has_its_own_price(registry):
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=2500)
    add_item(hero, "scimitar", cost_cp=100, quality="worn")
    lines = inv_lines(hero, registry, "0 мм")
    assert row(lines, "поношенн")[0].endswith(", 1 зм")
    new = [x for x in lines if "кимитар" in x and "поношенн" not in x.casefold()][0]
    assert new.endswith(", 25 зм")


def test_priced_armor_shows_price(registry):
    hero = make_hero()
    add_item(hero, "shield", cost_cp=1000)
    line = row(inv_lines(hero, registry, "0 мм"), "щит")[0]
    assert line.endswith(", 10 зм")


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
    assert line.endswith(", 1 мм")


# К2 П1: строки оружия и доспеха (решение 4) -- урон, свойства, мастерство, КД, цена после запятой


def line_of(registry, item_id, name, cost_cp):
    hero = make_hero()
    add_item(hero, item_id, cost_cp=cost_cp)
    return row(inv_lines(hero, registry, "0 мм"), name)[0]


def test_versatile_weapon_line_shows_both_dice_properties_mastery_and_price(registry):
    line = line_of(registry, "longsword", "длинный меч", 1500)
    expected = "1d8 руб. (двумя руками 1d10), универсальное, мастерство: Ослабление, 15 зм"
    assert line.endswith(expected)


def test_musket_line_has_range_next_to_ammunition(registry):
    line = line_of(registry, "musket", "мушкет", 0)
    assert line.endswith(
        "1d12 кол., двуручное, перезарядка, боеприпас 40/120, мастерство: Замедление"
    )


def test_blowgun_line_keeps_one_die_one_damage(registry):
    # Р30: урон трубки остаётся «1d1»
    assert registry.get("weapon", "blowgun").damage_dice == "1d1"
    assert "1d1 кол." in line_of(registry, "blowgun", "духовая трубка", 100)


def test_cunning_action_text_names_hide(registry):
    description = registry.get("feature", "cunning_action").description
    assert "Спрятаться" in description
    assert "Засада" not in description


def test_thrown_weapon_line_shows_thrown_range(registry):
    line = line_of(registry, "spear", "копьё", 100)
    assert "метательное 20/60" in line
    assert "универсальное" in line


def test_chain_mail_line_shows_flat_ac(registry):
    assert "КД 16" in line_of(registry, "chain_mail", "кольчуга", 7500)


def test_chain_mail_line_has_no_dex_part(registry):
    assert "Лов" not in line_of(registry, "chain_mail", "кольчуга", 7500)


def test_shield_line_shows_bonus_to_ac(registry):
    assert "+2 к КД" in line_of(registry, "shield", "щит", 1000)


def test_chain_shirt_line_shows_capped_dex(registry):
    line = line_of(registry, "chain_shirt", "кольчужная рубаха", 5000)
    assert "КД 13 + Лов (не больше +2)" in line


def test_leather_armor_line_shows_uncapped_dex(registry):
    line = line_of(registry, "leather_armor", "кожаный доспех", 1000)
    assert "КД 11 + Лов" in line
    assert "не больше" not in line


# К2 П1, мутанты weapon_text: прямой вызов с собранным оружием


def bare_weapon(**fields):
    from ai_dm.content.models.items import Weapon

    base = {
        "id": "test_blade", "name": "Тестовый клинок", "category": "simple", "kind": "melee",
        "damage_dice": "1d6", "damage_type": "slashing", "cost_cp": 100,
    }
    return Weapon(**(base | fields))


def test_weapon_text_unknown_damage_type_shows_raw_type():
    from ai_dm.game.sheet_text import weapon_text

    assert weapon_text(bare_weapon(damage_type="fire"), None) == "1d6 fire"


def test_weapon_text_known_damage_type_shows_short_word():
    from ai_dm.game.sheet_text import weapon_text

    assert weapon_text(bare_weapon(damage_type="bludgeoning"), None) == "1d6 дроб."


def test_weapon_text_appends_weapon_effects():
    from ai_dm.content.models.common import EffectSpec
    from ai_dm.game.sheet_text import weapon_text

    weapon = bare_weapon(effects=[EffectSpec(type="pierce_armor")])
    assert weapon_text(weapon, None) == "1d6 руб., пробивает доспех"
