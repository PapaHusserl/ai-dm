# К0-фикс-б (K0-FIX-PLAN, решение Q12 (в)): в /sheet пол и местоимения НЕ показываются --
# вывод листа не зависит от gender / pronouns героя (пол виден только промпту рассказчика).
from pathlib import Path

import pytest
from game_kit import ReactiveAdapter, make_app
from ranger_kit import make_class_hero

from ai_dm.campaign.loader import load_pack, pack_content_dir
from ai_dm.content.loader import load_registry
from ai_dm.game.sheet_text import title_line
from ai_dm.game.starter import new_world_from_pack

DRAGON = Path(__file__).resolve().parents[3] / "campaigns" / "drunk_dragon"
SCORES = {"str": 15, "dex": 13, "con": 14, "int": 8, "wis": 10, "cha": 12}


@pytest.fixture
def dragon_app(cfg, tmp_path):
    registry = load_registry([pack_content_dir(DRAGON)])
    bundle = new_world_from_pack(
        registry, cfg, load_pack(DRAGON, registry), hero="grey", seed=1, world_id="w1",
        saved_at="2026-01-01T00:00:00",
    )
    return make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)


def sheet(app):
    return "\n".join(app.handle("/sheet").lines)


def test_sheet_is_the_same_with_and_without_gender(dragon_app):
    hero = dragon_app.bundle.heroes[0]
    hero.gender = None
    hero.pronouns = ""
    before = sheet(dragon_app)
    hero.gender = "male"
    hero.pronouns = "он"
    assert sheet(dragon_app) == before


@pytest.mark.parametrize("gender", ["male", "female", "other"])
def test_sheet_does_not_show_gender_words(dragon_app, gender):
    hero = dragon_app.bundle.heroes[0]
    hero.gender = gender
    hero.pronouns = "они"
    text = sheet(dragon_app)
    words = ("(муж.)", "(жен.)", "(др.)", "местоимения", "мужской", "женский", "male", "female")
    for word in words:
        assert word not in text


def test_title_line_is_unchanged_by_gender(registry):
    hero = make_class_hero("fighter", SCORES)
    before = title_line(hero, registry)
    hero.gender = "female"
    hero.pronouns = "она"
    assert title_line(hero, registry) == before
    assert before == "Тест — человек, воин 1 ур., опыт 0/300"
