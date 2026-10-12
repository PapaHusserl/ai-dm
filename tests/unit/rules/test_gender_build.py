# К0-фикс-б (K0-FIX-PLAN, 7.2): build_character переносит пол и местоимения из выборов в героя.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

from hero_kit import base_choices  # noqa: E402

from ai_dm.rules.builder import build_character  # noqa: E402


def test_build_character_copies_gender(registry):
    hero = build_character(base_choices(gender="female"), registry)
    assert hero.gender == "female"


def test_build_character_copies_pronouns(registry):
    hero = build_character(base_choices(gender="other", pronouns="они"), registry)
    assert hero.pronouns == "они"


def test_build_character_without_gender_leaves_it_unset(registry):
    hero = build_character(base_choices(), registry)
    assert hero.gender is None
    assert hero.pronouns == ""


def test_build_character_pronouns_without_gender(registry):
    hero = build_character(base_choices(pronouns="госпожа"), registry)
    assert hero.gender is None
    assert hero.pronouns == "госпожа"
