# Живой прогон 1, п. 5: в меню хода заклинание без механики -- строка без номера «пока недоступно
# в бою»; нумерация вариантов не сдвигается; простой режим (render блока turn_menu) -- то же.
from types import SimpleNamespace

from ai_dm.ui.format import INERT_NOTE, turn_menu_lines
from ai_dm.ui.screen import Block
from ai_dm.ui.simple import render

TURN = SimpleNamespace(action=True, attacks_left=0, bonus=True, move=30, reaction=True)
OPTIONS = [
    SimpleNamespace(cost="action", kind="attack", label="Атака мечом"),
    SimpleNamespace(cost="action", kind="dash", label="Рывок"),
    SimpleNamespace(cost="bonus", kind="mark", label="Метка охотника"),
]


def test_inert_spell_line_has_no_number():
    lines = turn_menu_lines(OPTIONS, TURN, 80, inert=("Сигнал тревоги",))
    line = next(x for x in lines if "Сигнал тревоги" in x)
    assert INERT_NOTE in line
    assert not line.strip()[0].isdigit()


def test_numbering_is_the_same_with_and_without_inert():
    plain = turn_menu_lines(OPTIONS, TURN, 80)
    with_inert = turn_menu_lines(OPTIONS, TURN, 80, inert=("Сигнал тревоги", "Лечебные ягоды"))
    numbered = [x for x in with_inert if x.strip()[:2] in ("1.", "2.", "3.", "4.")]
    assert numbered == [x for x in plain if x in numbered]
    assert len(numbered) == 3
    assert not any("4." in x for x in with_inert)


def test_each_inert_spell_gets_its_own_line():
    lines = turn_menu_lines(OPTIONS, TURN, 80, inert=("Сигнал тревоги", "Лечебные ягоды"))
    assert len([x for x in lines if INERT_NOTE in x]) == 2


def test_no_inert_lines_without_inert_spells():
    assert not any(INERT_NOTE in x for x in turn_menu_lines(OPTIONS, TURN, 80))


def test_long_inert_name_wraps_within_width():
    lines = turn_menu_lines(OPTIONS, TURN, 30, inert=("Очень длинное название заклинания",))
    assert all(len(x) <= 30 for x in lines)
    assert INERT_NOTE.split()[-1] in " ".join(lines)


def test_simple_mode_renders_inert_spell_without_number():
    block = Block(
        "turn_menu", items=tuple(OPTIONS), args=(TURN, "", "КД 15", "", ("Сигнал тревоги",))
    )
    lines = render(block, 80)
    line = next(x for x in lines if "Сигнал тревоги" in x)
    assert INERT_NOTE in line
    assert not line.strip()[0].isdigit()
    assert [x for x in lines if x.strip().startswith("3.")]
    assert not [x for x in lines if x.strip().startswith("4.")]
