# Шаг К2, П2: Тактический ум воина 2+ ур. (docs/plan-k2.md, решения 18, 50; rules/tactical_mind.py).
#   При провале проверки навыка (skill_check с СЛ) воин сам добавляет 1d10 за заряд Второго дыхания:
#   * удалась -- заряд тратится, итог и исход меняются, в логе «Тактический ум: +1d10 (N) = X →
#     успех, заряд Второго дыхания потрачен»;
#   * не удалась -- заряд остаётся, в логе «... → провал, заряд не тратится»;
#   * пул пуст, проверка удалась без помощи, нет умения (1 ур.) -- d10 не бросается.
from protocol_kit import ScriptedRng, fighter_choices

from ai_dm.rules.builder import build_character
from ai_dm.rules.checks import skill_check
from ai_dm.rules.derived import skill_bonus
from ai_dm.rules.progression import sync_resources

DC = 15
STEALTH = "stealth"


def mind_hero(registry, level=2):
    hero = build_character(fighter_choices("hero"), registry)
    hero.sheet.primary.level = level
    sync_resources(hero, registry)
    return hero


def check(registry, hero, total, d10=()):
    # d20 подбирается так, чтобы итог до Тактического ума был total
    face = total - skill_bonus(hero, registry, STEALTH)
    rng = ScriptedRng(d20=[face], d10=list(d10))
    return skill_check(hero, registry, rng, STEALTH, dc=DC), rng


def pool(hero):
    return hero.creature.resources["second_wind"]


def test_rescued_check_becomes_a_success(registry):
    hero = mind_hero(registry)
    result, _ = check(registry, hero, 12, d10=[3])
    assert (result.outcome, result.total) == ("success", 15)


def test_rescued_check_spends_a_charge(registry):
    hero = mind_hero(registry)
    check(registry, hero, 12, d10=[3])
    assert pool(hero).current == 1


def test_rescued_check_log_names_the_charge(registry):
    hero = mind_hero(registry)
    result, _ = check(registry, hero, 12, d10=[3])
    assert result.log.text.endswith(
        "; Тактический ум: +1d10 (3) = 15 → успех, заряд Второго дыхания потрачен"
    )


def test_failed_rescue_stays_a_failure(registry):
    hero = mind_hero(registry)
    result, _ = check(registry, hero, 12, d10=[2])
    assert (result.outcome, result.total) == ("fail", 12)


def test_failed_rescue_keeps_the_charge(registry):
    hero = mind_hero(registry)
    check(registry, hero, 12, d10=[2])
    assert pool(hero).current == 2


def test_failed_rescue_log_says_the_charge_stays(registry):
    hero = mind_hero(registry)
    result, _ = check(registry, hero, 12, d10=[2])
    assert result.log.text.endswith("; Тактический ум: +1d10 (2) = 14 → провал, заряд не тратится")


def test_empty_pool_rolls_nothing(registry):
    hero = mind_hero(registry)
    pool(hero).current = 0
    result, rng = check(registry, hero, 12, d10=[10])
    assert (result.outcome, rng.left("d10")) == ("fail", 1)


def test_successful_check_does_not_use_the_mind(registry):
    hero = mind_hero(registry)
    result, rng = check(registry, hero, 16, d10=[3])
    assert (result.outcome, rng.left("d10"), pool(hero).current) == ("success", 1, 2)


def test_first_level_fighter_has_no_tactical_mind(registry):
    hero = mind_hero(registry, level=1)
    result, rng = check(registry, hero, 12, d10=[10])
    assert (result.outcome, rng.left("d10")) == ("fail", 1)


def test_check_without_a_dc_is_left_alone(registry):
    # проверка без исхода (например, броски без СЛ) Тактический ум не трогает
    from ai_dm.rules import tactical_mind
    from ai_dm.rules.roll_pipeline import RollLogEntry, RollResult

    hero = mind_hero(registry)
    bare = RollResult(kind="check", terms=[], total=5, outcome="fail", log=RollLogEntry(text="x"))
    rng = ScriptedRng(d10=[10])
    assert tactical_mind.apply(hero, registry, rng, bare) is bare
    assert rng.left("d10") == 1
