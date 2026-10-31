# Шаг К2, П2: умения героя как источник поправок броска (rules/modifiers/features.py).
#   Выдающийся атлет (Чемпион 3 ур.): преимущество на инициативу и на проверки Силы (Атлетика) --
#   две кости d20 в броске; другие навыки и воин без подкласса -- обычный бросок.
#   Улучшенный критический удар: диапазон крита атаки 19-20 (бросок атаки kind="attack").
from protocol_kit import ScriptedRng, fighter_choices

from ai_dm.rules.builder import build_character
from ai_dm.rules.checks import skill_check
from ai_dm.rules.progression import sync_resources
from ai_dm.rules.roll_pipeline import RollRequest, roll


def fighter_at(registry, level=3, subclass="champion"):
    hero = build_character(fighter_choices("hero"), registry)
    hero.sheet.primary.level = level
    hero.sheet.primary.subclass_id = subclass
    sync_resources(hero, registry)
    return hero


def initiative(registry, hero, rng):
    request = RollRequest(kind="initiative", actor=hero, actor_id="hero", ability="dex", bonus=1)
    return roll(request, rng, registry)


def attack(registry, hero, rng):
    request = RollRequest(
        kind="attack", actor=hero, actor_id="hero", ability="str", bonus=5, dc=15,
    )
    return roll(request, rng, registry)


# --- Выдающийся атлет ---

def test_champion_rolls_initiative_with_advantage(registry):
    result = initiative(registry, fighter_at(registry), ScriptedRng(d20=[4, 17]))
    assert (result.advantage, result.d20_rolls, result.total) == ("advantage", [4, 17], 18)


def test_initiative_log_shows_both_dice(registry):
    result = initiative(registry, fighter_at(registry), ScriptedRng(d20=[4, 17]))
    assert "4" in result.log.text and "17" in result.log.text


def test_fighter_without_subclass_rolls_initiative_normally(registry):
    result = initiative(registry, fighter_at(registry, subclass=None), ScriptedRng(d20=[4]))
    assert (result.advantage, result.d20_rolls) == ("normal", [4])


def test_champion_below_level_3_rolls_initiative_normally(registry):
    result = initiative(registry, fighter_at(registry, level=2), ScriptedRng(d20=[4]))
    assert result.advantage == "normal"


def test_athletics_check_has_advantage(registry):
    rng = ScriptedRng(d20=[3, 12])
    result = skill_check(fighter_at(registry), registry, rng, "athletics", dc=15)
    assert (result.advantage, result.d20_rolls) == ("advantage", [3, 12])


def test_other_skill_check_has_no_advantage(registry):
    rng = ScriptedRng(d20=[20])
    result = skill_check(fighter_at(registry), registry, rng, "stealth", dc=15)
    assert result.advantage == "normal"


def test_athletics_without_the_feature_is_normal(registry):
    rng = ScriptedRng(d20=[20])
    result = skill_check(fighter_at(registry, subclass=None), registry, rng, "athletics", dc=15)
    assert result.advantage == "normal"


# --- Улучшенный критический удар ---

def test_champion_crits_on_19(registry):
    assert attack(registry, fighter_at(registry), ScriptedRng(d20=[19])).outcome == "crit"


def test_champion_hits_on_18_without_a_crit(registry):
    assert attack(registry, fighter_at(registry), ScriptedRng(d20=[18])).outcome == "hit"


def test_fighter_without_subclass_does_not_crit_on_19(registry):
    result = attack(registry, fighter_at(registry, subclass=None), ScriptedRng(d20=[19]))
    assert result.outcome == "hit"


def test_natural_20_still_crits_without_the_feature(registry):
    result = attack(registry, fighter_at(registry, subclass=None), ScriptedRng(d20=[20]))
    assert result.outcome == "crit"
