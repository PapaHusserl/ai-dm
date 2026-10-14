# Партия К7д, п. 7: сцена сетки «подвал Вейла» (devtools/sim_cellar.py, docs/K7D-PLAN.md, В6, В7).
#   CELLAR_POOL -- кортеж id монстров от дорогих к дешёвым: wight, ghast, ghoul, shadow, skeleton,
#     zombie, giant_rat; CELLAR_CAP = 6.
#   fill_budget(budget, pool, registry, cap=CELLAR_CAP) -> list[str]: детерминированный жадный
#     набор: по порядку пула каждого вида ставим, пока его цена (ПО из cr_xp) влезает в остаток
#     бюджета и в cap; пустой пул или нулевой бюджет -- [].
#   build_cellar(registry, cfg, seed, hero, difficulty) -> Scenario: бюджет = party_budget(уровень
#     героя, tier_of(мир с settings.difficulty)); зоны stairs -- barrels (cover_half) -- crypt;
#     герой в stairs (auto_hero), враги enemy_1.. по списку fill_budget, зоны по очереди crypt /
#     barrels, группа "crypt" (лидер enemy_1, intent kill); без врагов -- только группа party;
#     hero=None -- воин 1 ур.; difficulty попадает в world.settings["difficulty"].
#   sim_combat.SCENARIOS включает "cellar"; build_scenario("cellar", ...) = build_cellar.
# Цены: wight 700, ghast 450, ghoul 200, shadow 100, skeleton/zombie 50, giant_rat 25.
# Бюджет героя 1 ур.: easy 50, normal 75, hard 100; 5 ур.: hard 1100.
import pytest

from ai_dm.combat.setup import validate_start
from ai_dm.devtools import sim_cellar
from ai_dm.devtools.grid_heroes import build_hero
from ai_dm.devtools.sim_cellar import CELLAR_CAP, CELLAR_POOL, build_cellar, fill_budget
from ai_dm.devtools.sim_combat import SCENARIOS, build_scenario, simulate


def enemies(scenario):
    return [p.monster_id for p in scenario.state.participants if p.side == "enemies"]


def test_pool_and_cap_constants():
    assert CELLAR_POOL == (
        "wight", "ghast", "ghoul", "shadow", "skeleton", "zombie", "giant_rat",
    )
    assert CELLAR_CAP == 6


def test_pool_is_ordered_from_expensive_to_cheap(registry):
    costs = [sim_cellar.enemy_cost(m, registry) for m in CELLAR_POOL]
    assert costs == sorted(costs, reverse=True)


# fill_budget

@pytest.mark.parametrize(
    "budget, expected",
    [
        (0, []),
        (24, []),
        (25, ["giant_rat"]),
        (50, ["skeleton"]),
        (75, ["skeleton", "giant_rat"]),
        (100, ["shadow"]),
        (700, ["wight"]),
        (1000, ["wight", "ghoul", "shadow"]),
        (1100, ["wight", "ghoul", "ghoul"]),
    ],
)
def test_fill_budget_table(registry, budget, expected):
    assert fill_budget(budget, CELLAR_POOL, registry) == expected


def test_fill_budget_repeats_a_kind_while_it_fits(registry):
    assert fill_budget(150, ("skeleton",), registry) == ["skeleton"] * 3


def test_fill_budget_stops_at_the_cap(registry):
    assert fill_budget(1000, ("giant_rat",), registry) == ["giant_rat"] * 6


def test_fill_budget_takes_the_cap_argument(registry):
    assert fill_budget(1000, ("giant_rat",), registry, cap=2) == ["giant_rat"] * 2


def test_fill_budget_cap_zero_gives_nothing(registry):
    assert fill_budget(1000, CELLAR_POOL, registry, cap=0) == []


def test_fill_budget_of_the_empty_pool(registry):
    assert fill_budget(1000, (), registry) == []


def test_fill_budget_follows_the_pool_order(registry):
    assert fill_budget(150, ("giant_rat", "skeleton"), registry) == ["giant_rat"] * 6


def test_fill_budget_skips_an_unaffordable_kind_and_goes_on(registry):
    assert fill_budget(60, ("wight", "skeleton"), registry) == ["skeleton"]


def test_fill_budget_exact_budget_is_spent_in_full(registry):
    assert fill_budget(100, ("skeleton",), registry) == ["skeleton", "skeleton"]


def test_fill_budget_is_deterministic(registry):
    assert fill_budget(900, CELLAR_POOL, registry) == fill_budget(900, CELLAR_POOL, registry)


# build_cellar

def build(registry, cfg, difficulty=None, level=1, seed=1):
    return build_cellar(registry, cfg, seed, build_hero("fighter", level, registry), difficulty)


@pytest.mark.parametrize(
    "difficulty, expected",
    [
        ("easy", ["skeleton"]),
        ("normal", ["skeleton", "giant_rat"]),
        ("hard", ["shadow"]),
        (None, ["skeleton", "giant_rat"]),
    ],
)
def test_difficulty_changes_the_cast(registry, cfg, difficulty, expected):
    assert enemies(build(registry, cfg, difficulty)) == expected


def test_higher_level_gets_a_bigger_budget(registry, cfg):
    assert enemies(build(registry, cfg, "hard", level=5)) == ["wight", "ghoul", "ghoul"]


def test_difficulty_lands_in_the_world_settings(registry, cfg):
    assert build(registry, cfg, "hard").world.settings["difficulty"] == "hard"


def test_no_difficulty_leaves_the_settings_empty(registry, cfg):
    assert "difficulty" not in build(registry, cfg).world.settings


def test_zones_and_hero(registry, cfg):
    state = build(registry, cfg).state
    assert [z.id for z in state.zones] == ["stairs", "barrels", "crypt"]
    barrels = state.zones[1]
    assert [f.kind for f in barrels.features] == ["cover_half"]
    hero = state.participants[0]
    assert (hero.ref, hero.side, hero.zone_id, hero.controller) == (
        "hero", "heroes", "stairs", "auto_hero",
    )


def test_enemies_alternate_between_crypt_and_barrels(registry, cfg):
    scenario = build(registry, cfg, "hard", level=5)
    rows = [(p.ref, p.zone_id) for p in scenario.state.participants[1:]]
    assert rows == [("enemy_1", "crypt"), ("enemy_2", "barrels"), ("enemy_3", "crypt")]


def test_enemy_participants_are_full_hp_named_monsters(registry, cfg):
    scenario = build(registry, cfg, "hard")
    enemy = scenario.state.participants[1]
    shadow = registry.get("monster", "shadow")
    assert (enemy.name, enemy.creature.hp_current, enemy.creature.hp_max) == (
        shadow.name, shadow.hp, shadow.hp,
    )
    assert (enemy.side, enemy.group_id) == ("enemies", "crypt")


def test_groups_with_enemies(registry, cfg):
    groups = build(registry, cfg, "hard").state.groups
    assert (groups["party"].leader_id, groups["crypt"].leader_id) == ("hero", "enemy_1")
    assert groups["crypt"].intent == "kill"


def test_empty_budget_gives_a_scene_without_enemies(registry, cfg, monkeypatch):
    monkeypatch.setattr(sim_cellar, "fill_budget", lambda *args, **kwargs: [])
    scenario = build(registry, cfg)
    assert list(scenario.state.groups) == ["party"]
    assert [p.ref for p in scenario.state.participants] == ["hero"]


def test_default_hero_is_a_level_one_fighter(registry, cfg):
    scenario = build_cellar(registry, cfg, 1, None, "easy")
    hero = scenario.heroes["hero"]
    assert (hero.sheet.level, hero.sheet.classes[0].class_id) == (1, "fighter")


def test_scenario_has_the_seed_rng_and_registry(registry, cfg):
    scenario = build(registry, cfg, seed=5)
    assert scenario.rng.state.seed == 5
    assert (scenario.registry, scenario.cfg) == (registry, cfg)


@pytest.mark.parametrize("difficulty", ["easy", "normal", "hard"])
def test_start_is_valid(registry, cfg, difficulty):
    assert validate_start(build(registry, cfg, difficulty).state) == []


# сцена в sim_combat

def test_cellar_is_a_known_scenario():
    assert "cellar" in SCENARIOS and "goblins3" in SCENARIOS


def test_build_scenario_routes_cellar(registry, cfg):
    hero = build_hero("fighter", 1, registry)
    scenario = build_scenario("cellar", registry, cfg, 3, hero=hero, difficulty="hard")
    assert enemies(scenario) == ["shadow"]


def test_build_scenario_cellar_without_hero_uses_the_default_fighter(registry, cfg):
    scenario = build_scenario("cellar", registry, cfg, 3)
    assert enemies(scenario) == ["skeleton", "giant_rat"]


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_simulate_finishes_on_three_seeds(registry, cfg, seed):
    result = simulate(build_scenario("cellar", registry, cfg, seed, difficulty="easy"))
    assert result.outcome is not None and result.rounds > 0


def test_simulate_is_deterministic(registry, cfg):
    def run():
        return simulate(build_scenario("cellar", registry, cfg, 2, difficulty="hard")).log

    assert run() == run()


def test_sim_combat_cli_runs_the_cellar(capsys):
    from ai_dm.devtools.sim_combat import main

    code = main(["--scenario", "cellar", "--seed", "1"])
    assert code == 0
    assert "outcome:" in capsys.readouterr().out


def test_sim_grid_cli_runs_the_cellar_scene(capsys):
    from ai_dm.devtools.sim_grid import main

    code = main(["--seeds", "2", "--classes", "fighter", "--levels", "1", "--scene", "cellar"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Сцена cellar" in out and "goblins3" not in out


def test_sim_grid_difficulty_changes_the_cellar_cell(registry, cfg):
    from ai_dm.devtools.sim_grid import run_cell

    easy = run_cell(("fighter", 1, "cellar"), (registry, cfg), range(8), difficulty="easy")
    hard = run_cell(("fighter", 1, "cellar"), (registry, cfg), range(8), difficulty="hard")
    assert easy != hard


def test_zone_names_and_ids(registry, cfg):
    state = build(registry, cfg).state
    assert [z.name for z in state.zones] == ["У лестницы", "Бочки", "Крипта"]
    assert state.id == "fight_1"
    assert [list(z.adjacent) for z in state.zones] == [
        ["barrels"], ["stairs", "crypt"], ["barrels"],
    ]


def test_world_id(registry, cfg):
    assert build(registry, cfg).world.world_id == "sim"


def test_build_scenario_keeps_the_given_hero_level(registry, cfg):
    hero = build_hero("fighter", 5, registry)
    scenario = build_scenario("cellar", registry, cfg, 3, hero=hero, difficulty="hard")
    assert enemies(scenario) == ["wight", "ghoul", "ghoul"]
