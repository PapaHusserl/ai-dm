# /inv со стеками разной цены/качества (docs/plan-custom-items.md, разд. 8, партия 0).
#   inv_lines(hero, registry, money_text): стек (id, cost_cp, quality) -- отдельная строка;
#   качество видно в имени строки (формат решает реализация: «Скимитар (поношенное)» или
#   «поношенный скимитар»): для worn в строке есть корень «поношенн»; без качества --
#   имя из реестра («Скимитар») без пометок.
#   Количество стека -- в его строке (x2 / ×2), а не суммой по id.
import re

from ai_dm.game.sheet_text import inv_lines
from ai_dm.rules.inventory import add_item
from ai_dm.state.creature import CreatureState
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState


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


def lines_of(hero, registry):
    return inv_lines(hero, registry, "0 мм")


def row(lines, text):
    return [line for line in lines if text in line.casefold()]


def plain_rows(lines):
    return [line for line in row(lines, "скимитар") if "поношенн" not in line.casefold()]


def test_worn_stack_and_plain_stack_are_separate_lines(registry):
    hero = make_hero()
    add_item(hero, "scimitar", 2, cost_cp=150, quality="worn")
    add_item(hero, "scimitar", cost_cp=2500)
    lines = lines_of(hero, registry)
    assert len(row(lines, "поношенн")) == 1
    assert len(plain_rows(lines)) == 1


def test_worn_stack_line_shows_its_own_quantity(registry):
    hero = make_hero()
    add_item(hero, "scimitar", 2, cost_cp=150, quality="worn")
    add_item(hero, "scimitar", cost_cp=2500)
    line = row(lines_of(hero, registry), "поношенн")[0]
    assert re.search(r"[x×]\s*2\b", line)


def test_plain_stack_line_is_not_summed_with_the_worn_one(registry):
    hero = make_hero()
    add_item(hero, "scimitar", 2, cost_cp=150, quality="worn")
    add_item(hero, "scimitar", cost_cp=2500)
    line = plain_rows(lines_of(hero, registry))[0]
    assert not re.search(r"[x×]\s*[23]", line)


def test_junk_stack_is_a_separate_line_with_a_mark(registry):
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=10, quality="junk")
    add_item(hero, "scimitar", cost_cp=2500)
    lines = row(lines_of(hero, registry), "скимитар")
    assert len(lines) == 2
    assert lines[0].strip() != lines[1].strip()


def test_two_prices_without_quality_are_two_lines(registry):
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=2500)
    add_item(hero, "scimitar", cost_cp=150)
    assert len(row(lines_of(hero, registry), "скимитар")) == 2


def test_stack_without_quality_is_the_registry_name(registry):
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=0)
    line = row(lines_of(hero, registry), "скимитар")[0]
    assert line.strip() == "Скимитар"


def test_weapon_stacks_stay_in_the_weapon_group(registry):
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=150, quality="worn")
    lines = lines_of(hero, registry)
    position = lines.index(row(lines, "поношенн")[0])
    assert lines.index("Оружие:") < position < lines.index("Деньги: 0 мм")


def test_worn_mark_is_only_on_the_most_expensive_stack(registry):
    from ai_dm.rules.inventory import equip

    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=2500)
    add_item(hero, "scimitar", cost_cp=150, quality="worn")
    equip(hero, "scimitar", registry)
    lines = lines_of(hero, registry)
    assert row(lines, "★") == plain_rows(lines)
    assert "★" not in row(lines, "поношенн")[0]


def test_unknown_item_id_is_shown_by_id_in_gear(registry):
    hero = make_hero()
    add_item(hero, "ghost_relic", 2, cost_cp=0)
    lines = lines_of(hero, registry)
    assert "Снаряжение и инструменты:" in lines
    line = row(lines, "ghost_relic")[0]
    assert re.search(r"[x×]\s*2", line)
    assert lines.index("Снаряжение и инструменты:") < lines.index(line)


def test_worn_mark_has_the_standard_look(registry):
    from ai_dm.rules.inventory import equip

    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=0)
    equip(hero, "scimitar", registry)
    assert row(lines_of(hero, registry), "скимитар")[0] == "  ★ Скимитар"


def test_equal_price_stacks_get_one_worn_mark(registry):
    from ai_dm.rules.inventory import equip

    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=150)
    add_item(hero, "scimitar", cost_cp=150, quality="worn")
    equip(hero, "scimitar", registry)
    assert len(row(lines_of(hero, registry), "★")) == 1


def test_unknown_id_does_not_hide_the_next_items(registry):
    hero = make_hero()
    add_item(hero, "ghost_relic", cost_cp=0)
    add_item(hero, "scimitar", cost_cp=150)
    lines = lines_of(hero, registry)
    assert row(lines, "скимитар")
    assert row(lines, "ghost_relic")


def test_unknown_id_line_has_no_effect_text(registry):
    hero = make_hero()
    add_item(hero, "ghost_relic", cost_cp=0)
    assert "—" not in row(lines_of(hero, registry), "ghost_relic")[0]


def test_armor_line_has_no_effect_text(registry):
    hero = make_hero()
    add_item(hero, "shield", cost_cp=0)
    line = row(lines_of(hero, registry), "щит")[0]
    assert "—" not in line
