# Ф1 (F1-PLAN п.2.4): rules.derived.companion_due(hero, registry) -- герой с умением
# Зверь-спутник, у которого зверя нет.
from master_kit import make_bundle

from ai_dm.game.starter import ranger_choices
from ai_dm.rules.builder import build_character
from ai_dm.rules.derived import companion_due
from ai_dm.state.hero import Companion


def ranger(registry, level=3, subclass="beast_master"):
    hero = build_character(ranger_choices("hero"), registry)
    hero.sheet.primary.level = level
    hero.sheet.level_history = ["ranger"] * level
    hero.sheet.primary.subclass_id = subclass
    return hero


def test_beast_master_level_3_without_beast_is_due(registry):
    assert companion_due(ranger(registry), registry) is True


def test_level_2_has_no_feature_yet(registry):
    assert companion_due(ranger(registry, level=2, subclass=None), registry) is False


def test_beast_master_with_beast_is_not_due(registry):
    hero = ranger(registry)
    hero.companions = [Companion(name="Акела", kind="волк")]
    assert companion_due(hero, registry) is False


def test_hunter_is_not_due(registry):
    assert companion_due(ranger(registry, subclass="hunter"), registry) is False


def test_fighter_is_not_due(registry):
    assert companion_due(make_bundle(registry).heroes[0], registry) is False


def test_beast_master_is_due_again_after_beast_is_gone(registry):
    hero = ranger(registry)
    hero.companions = [Companion(name="Акела", kind="волк")]
    hero.companions = []
    assert companion_due(hero, registry) is True
