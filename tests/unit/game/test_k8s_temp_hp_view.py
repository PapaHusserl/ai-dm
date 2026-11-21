# К8с П1: временные HP видны (решение 11, Р-К8с-4 = а): статус-строка и /sheet показывают
# «HP 40/52 +7 врем.»; без временных HP строка прежняя («HP 40/52»).
from game_kit import ReactiveAdapter, make_app
from protocol_kit import make_bundle

from ai_dm.ui.screen import status_line
from ai_dm.ui.tui.widgets import hero_lines


def temp_app(registry, tmp_path, temp):
    bundle = make_bundle(registry)
    creature = bundle.heroes[0].creature
    creature.hp_max = 52
    creature.hp_current = 40
    creature.hp_temp = temp
    return make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)


def test_status_line_shows_temp_hp(registry, tmp_path):
    assert "HP 40/52 +7 врем." in status_line(temp_app(registry, tmp_path, 7))


def test_status_line_without_temp_hp_is_as_before(registry, tmp_path):
    line = status_line(temp_app(registry, tmp_path, 0))
    assert "HP 40/52 ·" in line
    assert "врем." not in line


def test_sheet_shows_temp_hp(registry, tmp_path):
    text = "\n".join(temp_app(registry, tmp_path, 7).handle("/sheet").lines)
    assert "HP 40/52 +7 врем." in text


def test_sheet_shows_single_temp_hp(registry, tmp_path):
    text = "\n".join(temp_app(registry, tmp_path, 1).handle("/sheet").lines)
    assert "HP 40/52 +1 врем." in text


def test_sheet_without_temp_hp_has_no_temp_mark(registry, tmp_path):
    text = "\n".join(temp_app(registry, tmp_path, 0).handle("/sheet").lines)
    assert "врем." not in text


def test_sheet_temp_hp_has_no_term_mark(registry, tmp_path):
    # М0 П4 (решение 127): срока временных HP нет -- «(до …)» не показывается
    text = "\n".join(temp_app(registry, tmp_path, 8).handle("/sheet").lines)
    assert "+8 врем." in text
    assert "(до " not in text


def test_tui_hero_panel_shows_temp_hp(registry, tmp_path):
    assert "HP 40/52 +7 врем." in hero_lines(temp_app(registry, tmp_path, 7))


def test_tui_hero_panel_without_temp_hp_is_plain(registry, tmp_path):
    assert "HP 40/52" in hero_lines(temp_app(registry, tmp_path, 0))
