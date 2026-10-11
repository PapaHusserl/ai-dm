# Ожидаемый API (STAGE3-PLAN A8, П6а, ТЗ 4.2): /sheet показывает благосклонность приблизительно,
# строкой «<имя бога>: милость / безразличие / гнев» (>= 3 / -2..2 / <= -3), без чисел
#   шкалы.
import pytest
from game_kit import ReactiveAdapter, make_app
from protocol_kit import make_bundle

from ai_dm.state.world import God


def sheet_text(registry, tmp_path, favor):
    bundle = make_bundle(registry)
    bundle.world.pantheon["selune"] = God(id="selune", name="Селунэ")
    bundle.heroes[0].favor = {"selune": favor}
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    return "\n".join(app.handle("/sheet").lines)


def test_sheet_says_wrathful_at_minus_four(registry, tmp_path):
    text = sheet_text(registry, tmp_path, -4)
    assert "Селунэ" in text
    assert "гнев" in text


@pytest.mark.parametrize("favor", [-3, -10])
def test_sheet_says_wrathful_from_minus_three(registry, tmp_path, favor):
    assert "гнев" in sheet_text(registry, tmp_path, favor)


@pytest.mark.parametrize("favor", [3, 9])
def test_sheet_says_favorable_from_three(registry, tmp_path, favor):
    assert "милость" in sheet_text(registry, tmp_path, favor)


@pytest.mark.parametrize("favor", [-2, 0, 2])
def test_sheet_says_indifferent_in_the_middle(registry, tmp_path, favor):
    text = sheet_text(registry, tmp_path, favor)
    assert "безразличие" in text
    assert "гнев" not in text


def test_sheet_does_not_show_exact_favor_number(registry, tmp_path):
    text = sheet_text(registry, tmp_path, -7)
    assert "-7" not in text and "−7" not in text



def test_sheet_lists_every_pantheon_god_even_untouched(registry, tmp_path):
    # живой прогон: у Грея favor пуст -- боги пантеона всё равно видны, с безразличием
    bundle = make_bundle(registry)
    bundle.world.pantheon["selune"] = God(id="selune", name="Селунэ")
    bundle.world.pantheon["lathander"] = God(id="lathander", name="Латандр")
    bundle.heroes[0].favor = {}
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    text = "\n".join(app.handle("/sheet").lines)
    assert "Селунэ: безразличие" in text and "Латандр: безразличие" in text
