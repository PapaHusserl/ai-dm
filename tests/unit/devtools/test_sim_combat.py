# Devtools симуляции боя (шаг 23): ai_dm.devtools.sim_combat -- ИСТОЧНИК фикстуры «гоблины-3»
# (ARCHITECTURE, «Тестовые сценарии»): сценарные тесты и golden берут бой отсюда, отдельной
# копии в tests/ нет.
#   SCENARIOS = ("goblins3",); VARIANTS = ("default", "weak")
#   build_scenario(name, registry, cfg, seed, *, variant="default", intent="kill") -> Scenario
#     Scenario: state (CombatState, ещё без инициативы: round == 0), world (WorldState),
#       heroes: dict[str, HeroState], registry, cfg, rng: Rng(seed); world.rng == rng.state;
#       engine(controllers=None) -> CombatEngine (без start()).
#     goblins3: зоны door "У двери" -- hall "Центр зала" -- balcony "Балкон" (cover_half);
#       герой "hero" (человек-воин 1 ур., солдат, кольчуга, щит, длинный меч, Defense;
#       КД 19) в door, controller "auto_hero", группа "party" (лидер hero);
#       goblin_1 и goblin_2 (goblin_warrior, безымянные: состояние в Participant.creature, в
#       world.npcs их нет) в hall, goblin_3 (с луком) в balcony,
#       controller "engine", группа "goblins" (лидер goblin_1, intent = аргумент intent).
#       variant "weak" -- вместо воина волшебник 1 ур. (id всё тот же "hero", class_id "wizard").
#     неизвестный сценарий / вариант -> ValueError
#   simulate(scenario, max_rounds=None) -> SimResult: engine().start() + run_to_end();
#     SimResult(outcome: str | None, rounds: int, log: list[str], events: list[DomainEvent],
#               scenario: Scenario); rounds == state.round; log == state.log
#   find_seed(name, outcome, *, registry, cfg, variant="default", intent="kill", limit=500)
#     -> int | None: первый seed из range(limit), чей simulate даёт этот outcome; неизвестный
#     outcome -> ValueError
#   main(argv=None) -> int: CLI `python -m ai_dm.devtools.sim_combat --seed N --scenario goblins3
#     [--variant weak] [--intent capture]` печатает state.log построчно, затем строку
#     "outcome: <outcome> rounds: <N>", возвращает 0;
#     `--find-outcome victory [--limit N]` печатает найденный seed (или "none" и код 1).
#     Неизвестный сценарий -- ненулевой код (argparse: SystemExit(2)).
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ai_dm.combat.setup import validate_start
from ai_dm.devtools.sim_combat import (
    SCENARIOS,
    VARIANTS,
    build_scenario,
    find_seed,
    main,
    simulate,
)
from ai_dm.rules.derived import armor_class

SRC = Path(__file__).resolve().parents[3] / "src"


def build(registry, cfg, seed=1, **kwargs):
    return build_scenario("goblins3", registry, cfg, seed, **kwargs)


def run_main(argv, capsys):
    try:
        code = main(argv)
    except SystemExit as exit_:
        code = exit_.code
    return code, capsys.readouterr().out


# сценарий

def test_known_scenarios_and_variants():
    assert "goblins3" in SCENARIOS
    assert set(VARIANTS) == {"default", "weak"}


def test_scenario_zones(registry, cfg):
    zones = build(registry, cfg).state.zones
    assert [z.id for z in zones] == ["door", "hall", "balcony"]
    assert [z.name for z in zones] == ["У двери", "Центр зала", "Балкон"]
    assert [z.adjacent for z in zones] == [["hall"], ["door", "balcony"], ["hall"]]


def test_balcony_has_half_cover(registry, cfg):
    balcony = build(registry, cfg).state.zones[2]
    assert [f.kind for f in balcony.features] == ["cover_half"]


def test_scenario_participants(registry, cfg):
    state = build(registry, cfg).state
    assert [(p.ref, p.zone_id, p.side) for p in state.participants] == [
        ("hero", "door", "heroes"),
        ("goblin_1", "hall", "enemies"),
        ("goblin_2", "hall", "enemies"),
        ("goblin_3", "balcony", "enemies"),
    ]
    assert [p.controller for p in state.participants] == [
        "auto_hero", "engine", "engine", "engine",
    ]


def test_scenario_groups(registry, cfg):
    groups = build(registry, cfg).state.groups
    assert groups["party"].leader_id == "hero"
    assert groups["goblins"].leader_id == "goblin_1"
    assert groups["goblins"].intent == "kill"


def test_intent_argument_sets_the_group_intent(registry, cfg):
    assert build(registry, cfg, intent="capture").state.groups["goblins"].intent == "capture"


def test_scenario_hero_is_a_fighter_in_chain_mail(registry, cfg):
    hero = build(registry, cfg).heroes["hero"]
    assert hero.sheet.class_id == "fighter"
    assert hero.sheet.species_id == "human"
    assert hero.sheet.background.name == "Солдат"
    assert hero.equipped.main_hand == "longsword"
    assert "defense" in hero.sheet.feats
    assert armor_class(hero, registry) == 19


def test_weak_variant_has_a_wizard(registry, cfg):
    scenario = build(registry, cfg, variant="weak")
    hero = scenario.heroes["hero"]
    assert hero.sheet.class_id == "wizard"
    assert hero.creature.hp_max == 8
    assert [p.ref for p in scenario.state.participants] == [
        "hero", "goblin_1", "goblin_2", "goblin_3",
    ]


def test_goblins_are_anonymous_participants(registry, cfg):
    scenario = build(registry, cfg)
    assert scenario.world.npcs == {}
    goblins = [p for p in scenario.state.participants if p.side == "enemies"]
    assert [p.creature.hp_current for p in goblins] == [10, 10, 10]
    assert {p.name for p in goblins} == {"Воин-гоблин"}
    assert {p.monster_id for p in goblins} == {"goblin_warrior"}


def test_scenario_start_is_valid(registry, cfg):
    assert validate_start(build(registry, cfg).state) == []


def test_scenario_rng_follows_the_seed(registry, cfg):
    scenario = build(registry, cfg, seed=77)
    assert scenario.rng.state.seed == 77
    assert scenario.world.rng == scenario.rng.state


def test_same_seed_builds_identical_scenarios(registry, cfg):
    first, second = build(registry, cfg, seed=5), build(registry, cfg, seed=5)
    assert first.state.model_dump_json() == second.state.model_dump_json()
    assert first.world.model_dump_json() == second.world.model_dump_json()


def test_unknown_scenario_and_variant_are_errors(registry, cfg):
    with pytest.raises(ValueError):
        build_scenario("dragons", registry, cfg, 1)
    with pytest.raises(ValueError):
        build(registry, cfg, variant="godlike")


def test_scenario_builds_an_engine_without_starting_it(registry, cfg):
    engine = build(registry, cfg).engine()
    assert engine.state.round == 0


# simulate / find_seed

def test_simulate_returns_outcome_rounds_and_log(registry, cfg):
    result = simulate(build(registry, cfg, seed=3))
    assert result.outcome == result.scenario.state.outcome
    assert result.outcome is not None
    assert result.rounds == result.scenario.state.round
    assert result.log == result.scenario.state.log
    assert result.log
    assert result.events[-1].type == "combat_ended"


def test_find_seed_returns_a_seed_with_that_outcome(registry, cfg):
    seed = find_seed("goblins3", "victory", registry=registry, cfg=cfg, limit=200)
    assert seed is not None
    assert simulate(build(registry, cfg, seed=seed)).outcome == "victory"


def test_find_seed_is_the_first_matching_seed(registry, cfg):
    seed = find_seed("goblins3", "victory", registry=registry, cfg=cfg, limit=200)
    for earlier in range(seed):
        assert simulate(build(registry, cfg, seed=earlier)).outcome != "victory"


def test_find_seed_with_variant_and_intent(registry, cfg):
    seed = find_seed(
        "goblins3", "defeat_pending", registry=registry, cfg=cfg, variant="weak",
        intent="capture", limit=300,
    )
    assert seed is not None
    result = simulate(build(registry, cfg, seed=seed, variant="weak", intent="capture"))
    assert result.outcome == "defeat_pending"


def test_find_seed_rejects_an_unknown_outcome(registry, cfg):
    with pytest.raises(ValueError):
        find_seed("goblins3", "draw", registry=registry, cfg=cfg)


# CLI

def test_cli_prints_the_log_and_returns_zero(capsys):
    code, out = run_main(["--seed", "1", "--scenario", "goblins3"], capsys)
    assert code == 0
    lines = out.splitlines()
    assert len(lines) > 2
    assert lines[-1].startswith("outcome: ")
    assert " rounds: " in lines[-1]


def test_cli_is_deterministic(capsys):
    _, first = run_main(["--seed", "4", "--scenario", "goblins3"], capsys)
    _, second = run_main(["--seed", "4", "--scenario", "goblins3"], capsys)
    assert first == second


def test_cli_other_seed_other_log(capsys):
    _, first = run_main(["--seed", "1", "--scenario", "goblins3"], capsys)
    _, second = run_main(["--seed", "2", "--scenario", "goblins3"], capsys)
    assert first != second


def test_cli_accepts_variant_and_intent(capsys):
    code, out = run_main(
        ["--seed", "1", "--scenario", "goblins3", "--variant", "weak", "--intent", "capture"],
        capsys,
    )
    assert code == 0
    assert out.splitlines()[-1].startswith("outcome: ")


def test_cli_unknown_scenario_fails(capsys):
    code, _ = run_main(["--seed", "1", "--scenario", "dragons"], capsys)
    assert code not in (0, None)


def test_cli_finds_a_seed(capsys):
    code, out = run_main(
        ["--scenario", "goblins3", "--find-outcome", "victory", "--limit", "200"], capsys
    )
    assert code == 0
    assert out.strip().isdigit()


def test_cli_runs_as_a_module():
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    done = subprocess.run(
        [sys.executable, "-m", "ai_dm.devtools.sim_combat",
         "--seed", "1", "--scenario", "goblins3"],
        capture_output=True, text=True, env=env, timeout=120,
    )
    assert done.returncode == 0
    assert done.stdout.splitlines()[-1].startswith("outcome: ")
