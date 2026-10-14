# Партия К7к, п. 4.3: сетка sim_grid -- класс x уровень x сцена (docs/K7K-PLAN.md, В1а, В8а,
# Q2а, Q3а).
#   SCENES = {"goblins3": "goblins3"}; LEVELS = range(1, 6); не входит в `make test` (цель
#   `make sim-grid` = `python -m ai_dm.devtools.sim_grid --check`).
#   Cell(wins, deaths, other, mean_rounds): total, share (доля побед в %); исход "victory" --
#     победа, "hero_dead" -- смерть, остальное -- other;
#   run_cell((class_id, level, scene), (registry, cfg), seeds, difficulty=None) -> Cell: герой
#     build_hero, на каждый сид своя копия героя, build_scenario(scene, ..., hero=, difficulty=);
#   run_grid((registry, cfg), (classes, levels, scenes), seeds, difficulty=None) -> list[Row]:
#     порядок сцена -> класс -> уровень;
#   table_lines(rows): «Сцена <имя>: ...», на клетку строка
#     «  <класс> <L> ур.: побед N/M (p %), ср. раундов R»;
#   compare(rows, baseline, tolerance) -> list[str]: baseline {сцена: {класс: {уровень: доля}}};
#     клетка хуже базовой больше чем на tolerance п.п. -- «класс L ур.: 20 % < базовой 32 % −
#     10 п.п.»; ровно на границе -- пусто; нет клетки в базовой -- «класс L ур.: нет базовой линии»;
#   baseline_data(rows, seeds, tolerance) -> {seeds, tolerance_pp, сцена: {класс: {уровень: доля}}};
#   main(argv): --seeds --classes --levels --scene --difficulty --check --write-baseline
#     --baseline PATH; печатает таблицу; --check: код 1, если есть строки compare (допуск из
#     файла базовой линии), иначе 0; --write-baseline пишет YAML с seeds и tolerance_pp.
#   devtools/sim_grid_baseline.yaml -- базовая линия 200 сидов, допуск 10 п.п., 5 классов x 1-5 ур.
from pathlib import Path

import pytest
import yaml

from ai_dm.devtools import sim_grid
from ai_dm.devtools.grid_heroes import CLASSES
from ai_dm.devtools.sim_grid import (
    LEVELS,
    SCENES,
    Cell,
    Row,
    baseline_data,
    compare,
    main,
    run_cell,
    run_grid,
    table_lines,
)

ROOT = Path(__file__).resolve().parents[3]


def row(class_id="fighter", level=1, share_wins=1, total=4, scene="goblins3"):
    return Row(scene, class_id, level, Cell(share_wins, total - share_wins, 0, 3.5))


def baseline(value, class_id="fighter", level=1, scene="goblins3"):
    return {scene: {class_id: {level: value}}}


def run_main(argv, capsys):
    code = main(argv)
    return code, capsys.readouterr().out


# константы

def test_scenes_and_levels():
    assert SCENES == {"goblins3": "goblins3"}
    assert list(LEVELS) == [1, 2, 3, 4, 5]


# Cell

def test_cell_total_and_share():
    cell = Cell(wins=3, deaths=1, other=0, mean_rounds=2.0)
    assert cell.total == 4
    assert cell.share == 75.0


def test_cell_total_counts_other():
    assert Cell(1, 1, 2, 1.0).total == 4


# run_cell

def test_run_cell_counts_add_up(registry, cfg):
    cell = run_cell(("fighter", 1, "goblins3"), (registry, cfg), range(3))
    assert cell.wins + cell.deaths + cell.other == 3
    assert cell.total == 3
    assert cell.mean_rounds > 0


def test_run_cell_is_deterministic(registry, cfg):
    one = run_cell(("fighter", 2, "goblins3"), (registry, cfg), range(5))
    two = run_cell(("fighter", 2, "goblins3"), (registry, cfg), range(5))
    assert one == two


def test_run_cell_uses_the_seeds_given(registry, cfg):
    one = run_cell(("fighter", 1, "goblins3"), (registry, cfg), [0])
    two = run_cell(("fighter", 1, "goblins3"), (registry, cfg), [0, 1, 2, 3, 4, 5])
    assert one.total == 1
    assert two.total == 6


def test_run_cell_accepts_a_generator_of_seeds(registry, cfg):
    cell = run_cell(("fighter", 1, "goblins3"), (registry, cfg), (n for n in range(3)))
    assert cell.total == 3


def test_run_cell_mean_rounds_is_the_mean(registry, cfg, monkeypatch):
    class Result:
        def __init__(self, rounds, outcome):
            self.rounds = rounds
            self.outcome = outcome

    results = iter([
        Result(2, "victory"), Result(5, "hero_dead"), Result(8, "ended_by_master"),
        Result(5, "hero_dead"), Result(5, "hero_dead"),
    ])
    monkeypatch.setattr(sim_grid, "simulate", lambda scenario: next(results))
    cell = run_cell(("fighter", 1, "goblins3"), (registry, cfg), range(5))
    assert (cell.wins, cell.deaths, cell.other) == (1, 3, 1)
    assert cell.mean_rounds == 5.0


def test_run_cell_gives_every_seed_its_own_hero_copy(registry, cfg, monkeypatch):
    heroes = []
    real = sim_grid.build_scenario

    def spy(name, registry_, cfg_, seed, **kwargs):
        heroes.append(kwargs["hero"])
        return real(name, registry_, cfg_, seed, **kwargs)

    monkeypatch.setattr(sim_grid, "build_scenario", spy)
    run_cell(("fighter", 1, "goblins3"), (registry, cfg), range(3))
    assert len({id(h) for h in heroes}) == 3


def test_run_cell_hero_is_not_spoiled_by_earlier_fights(registry, cfg):
    # бой 1 сида одинаков до и после боёв на других сидах
    alone = run_cell(("fighter", 1, "goblins3"), (registry, cfg), [7])
    after = run_cell(("fighter", 1, "goblins3"), (registry, cfg), [3, 4, 5, 6, 7])
    assert alone.total == 1
    assert after.total == 5


def test_run_cell_passes_scene_difficulty_and_hero(registry, cfg, monkeypatch):
    seen = []
    real = sim_grid.build_scenario

    def spy(name, registry_, cfg_, seed, **kwargs):
        seen.append((name, seed, kwargs["difficulty"], kwargs["hero"].sheet.class_id))
        return real(name, registry_, cfg_, seed, **kwargs)

    monkeypatch.setattr(sim_grid, "build_scenario", spy)
    run_cell(("ranger", 1, "goblins3"), (registry, cfg), range(2), difficulty="hard")
    assert seen == [("goblins3", 0, "hard", "ranger"), ("goblins3", 1, "hard", "ranger")]


def test_run_cell_without_difficulty_passes_none(registry, cfg, monkeypatch):
    seen = []
    real = sim_grid.build_scenario

    def spy(name, registry_, cfg_, seed, **kwargs):
        seen.append(kwargs["difficulty"])
        return real(name, registry_, cfg_, seed, **kwargs)

    monkeypatch.setattr(sim_grid, "build_scenario", spy)
    run_cell(("fighter", 1, "goblins3"), (registry, cfg), range(1))
    assert seen == [None]


def test_run_cell_unknown_scene_raises(registry, cfg):
    with pytest.raises(KeyError):
        run_cell(("fighter", 1, "nowhere"), (registry, cfg), range(1))


def test_fighter_level_1_cell_matches_the_k1_measure(registry, cfg):
    # k1-sim-combat: воин 1 ур. против трёх гоблинов -- 64 победы из 200 сидов
    cell = run_cell(("fighter", 1, "goblins3"), (registry, cfg), range(200))
    assert cell.wins == 64
    assert cell.share == 32.0


def test_stronger_fighter_wins_more(registry, cfg):
    weak = run_cell(("fighter", 1, "goblins3"), (registry, cfg), range(40))
    strong = run_cell(("fighter", 5, "goblins3"), (registry, cfg), range(40))
    assert strong.wins > weak.wins


# run_grid

def test_run_grid_rows_in_order(registry, cfg):
    rows = run_grid(
        (registry, cfg), (["fighter", "wizard"], [1, 2], ["goblins3"]), range(2)
    )
    assert [(r.scene, r.class_id, r.level) for r in rows] == [
        ("goblins3", "fighter", 1), ("goblins3", "fighter", 2),
        ("goblins3", "wizard", 1), ("goblins3", "wizard", 2),
    ]
    assert all(r.cell.total == 2 for r in rows)


def test_run_grid_full_grid_has_25_rows(registry, cfg, monkeypatch):
    calls = []

    def fake(cell, context, seeds, difficulty=None):
        class_id, level, scene = cell
        calls.append((class_id, level, scene, list(seeds), difficulty))
        return Cell(1, 0, 0, 1.0)

    monkeypatch.setattr(sim_grid, "run_cell", fake)
    rows = run_grid((registry, cfg), (CLASSES, LEVELS, SCENES), range(2))
    assert len(rows) == 25
    assert {(r.class_id, r.level) for r in rows} == {(c, n) for c in CLASSES for n in LEVELS}
    assert calls[0] == ("fighter", 1, "goblins3", [0, 1], None)


def test_run_grid_passes_difficulty(registry, cfg, monkeypatch):
    seen = []

    def fake(cell, context, seeds, difficulty=None):
        seen.append(difficulty)
        return Cell(1, 0, 0, 1.0)

    monkeypatch.setattr(sim_grid, "run_cell", fake)
    run_grid((registry, cfg), (["fighter"], [1], ["goblins3"]), range(1), difficulty="easy")
    assert seen == ["easy"]


def test_run_grid_two_scenes_go_scene_by_scene(registry, cfg, monkeypatch):
    monkeypatch.setattr(sim_grid, "run_cell", lambda *args, **kwargs: Cell(1, 0, 0, 1.0))
    rows = run_grid((registry, cfg), (["fighter", "rogue"], [1], ["a", "b"]), range(1))
    assert [(r.scene, r.class_id) for r in rows] == [
        ("a", "fighter"), ("a", "rogue"), ("b", "fighter"), ("b", "rogue"),
    ]


# table_lines

def test_table_lines_format():
    rows = [row("fighter", 1, 1, 4), row("wizard", 2, 3, 4)]
    assert table_lines(rows) == [
        "Сцена goblins3: побед N/M (доля), средние раунды",
        "  fighter  1 ур.: побед 1/4 (25.0 %), ср. раундов 3.50",
        "  wizard   2 ур.: побед 3/4 (75.0 %), ср. раундов 3.50",
    ]


def test_table_lines_empty():
    assert table_lines([]) == []


def test_table_lines_group_by_scene():
    rows = [row("fighter", 1, scene="a"), row("fighter", 1, scene="b"), row("rogue", 1, scene="a")]
    lines = table_lines(rows)
    assert [line for line in lines if line.startswith("Сцена")] == [
        "Сцена a: побед N/M (доля), средние раунды", "Сцена b: побед N/M (доля), средние раунды",
    ]
    assert [line.split()[0] for line in lines] == ["Сцена", "fighter", "rogue", "Сцена", "fighter"]


# compare

def test_compare_cell_below_the_line_gives_a_line():
    assert compare([row(share_wins=1, total=5)], baseline(32.0), 10) == [
        "fighter 1 ур.: 20 % < базовой 32 % − 10 п.п."
    ]


def test_compare_exactly_on_the_border_is_clean():
    # 22 % == 32 - 10
    assert compare([row(share_wins=11, total=50)], baseline(32.0), 10) == []


def test_compare_just_below_the_border_gives_a_line():
    assert len(compare([row(share_wins=219, total=1000)], baseline(32.0), 10)) == 1


def test_compare_better_than_the_line_is_clean():
    assert compare([row(share_wins=4, total=5)], baseline(32.0), 10) == []


def test_compare_uses_the_tolerance_given():
    cell = [row(share_wins=1, total=5)]
    assert compare(cell, baseline(32.0), 12) == []
    assert compare(cell, baseline(32.0), 11) != []


def test_compare_zero_tolerance_is_strict():
    assert compare([row(share_wins=1, total=5)], baseline(20.0), 0) == []
    assert compare([row(share_wins=1, total=5)], baseline(20.1), 0) != []


def test_compare_missing_level_is_no_baseline():
    assert compare([row(level=2)], baseline(32.0, level=1), 10) == [
        "fighter 2 ур.: нет базовой линии"
    ]


def test_compare_missing_class_is_no_baseline():
    assert compare([row("rogue")], baseline(32.0), 10) == ["rogue 1 ур.: нет базовой линии"]


def test_compare_missing_scene_is_no_baseline():
    assert compare([row(scene="other")], baseline(32.0), 10) == [
        "fighter 1 ур.: нет базовой линии"
    ]


def test_compare_empty_baseline_is_no_baseline():
    assert compare([row()], {}, 10) == ["fighter 1 ур.: нет базовой линии"]


def test_compare_goes_on_after_a_cell_without_baseline():
    rows = [row("fighter", 2, 0, 5), row("fighter", 1, 0, 5)]
    assert compare(rows, baseline(50.0), 10) == [
        "fighter 2 ур.: нет базовой линии", "fighter 1 ур.: 0 % < базовой 50 % − 10 п.п.",
    ]


def test_compare_reports_every_bad_cell_in_order():
    rows = [row("fighter", 1, 0, 5), row("fighter", 2, 5, 5), row("wizard", 1, 0, 5)]
    base = {"goblins3": {"fighter": {1: 50.0, 2: 50.0}, "wizard": {1: 50.0}}}
    assert compare(rows, base, 10) == [
        "fighter 1 ур.: 0 % < базовой 50 % − 10 п.п.",
        "wizard 1 ур.: 0 % < базовой 50 % − 10 п.п.",
    ]


# baseline_data

def test_baseline_data_layout():
    rows = [row("fighter", 1, 1, 3), row("fighter", 2, 2, 3), row("wizard", 1, 0, 3)]
    assert baseline_data(rows, 200, 10) == {
        "seeds": 200, "tolerance_pp": 10,
        "goblins3": {"fighter": {1: 33.3, 2: 66.7}, "wizard": {1: 0.0}},
    }


def test_baseline_data_roundtrips_into_compare():
    rows = [row("fighter", 1, 1, 3)]
    data = baseline_data(rows, 200, 10)
    assert compare(rows, data, data["tolerance_pp"]) == []


# main

def small(tmp_path, *extra):
    return ["--seeds", "3", "--classes", "fighter", "--levels", "1", "--baseline",
            str(tmp_path / "base.yaml"), *extra]


def write_baseline(tmp_path, value, tolerance, level=1):
    data = {"seeds": 3, "tolerance_pp": tolerance, "goblins3": {"fighter": {level: value}}}
    (tmp_path / "base.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")


def test_main_prints_the_table_and_returns_zero(tmp_path, capsys):
    code, out = run_main(small(tmp_path), capsys)
    assert code == 0
    assert "Сцена goblins3" in out
    assert "fighter  1 ур.: побед" in out


def test_main_runs_the_classes_and_levels_asked(tmp_path, capsys):
    argv = ["--seeds", "2", "--classes", "fighter", "wizard", "--levels", "1", "2"]
    code, out = run_main(argv, capsys)
    assert code == 0
    cells = [line for line in out.splitlines() if " ур.:" in line]
    assert len(cells) == 4


def test_main_default_grid_is_25_cells(capsys, monkeypatch):
    monkeypatch.setattr(sim_grid, "run_cell", lambda *args, **kwargs: Cell(1, 0, 0, 1.0))
    code, out = run_main(["--seeds", "1"], capsys)
    assert code == 0
    assert len([line for line in out.splitlines() if " ур.:" in line]) == 25


def test_main_passes_seeds_and_difficulty(capsys, monkeypatch):
    seen = {}

    def fake(context, grid, seeds, difficulty=None):
        seen.update(
            classes=grid[0], levels=grid[1], scenes=grid[2], seeds=seeds, difficulty=difficulty
        )
        return []

    monkeypatch.setattr(sim_grid, "run_grid", fake)
    main(["--seeds", "7", "--classes", "rogue", "--levels", "2", "3", "--difficulty", "hard"])
    assert list(seen["seeds"]) == list(range(7))
    assert seen["classes"] == ["rogue"]
    assert seen["levels"] == [2, 3]
    assert seen["scenes"] == ["goblins3"]
    assert seen["difficulty"] == "hard"


def test_main_default_seeds_are_200(capsys, monkeypatch):
    seen = {}

    def fake(context, grid, seeds, difficulty=None):
        seen.update(
            classes=grid[0], levels=grid[1], scenes=grid[2], seeds=seeds, difficulty=difficulty
        )
        return []

    monkeypatch.setattr(sim_grid, "run_grid", fake)
    main([])
    assert len(list(seen["seeds"])) == 200
    assert seen["difficulty"] is None


def test_main_unknown_class_is_rejected():
    with pytest.raises(SystemExit):
        main(["--classes", "bard"])


def test_main_without_check_ignores_the_baseline(tmp_path, capsys):
    write_baseline(tmp_path, 1000.0, 0)
    code, _ = run_main(small(tmp_path), capsys)
    assert code == 0


def test_check_passes_against_a_low_baseline(tmp_path, capsys):
    write_baseline(tmp_path, -1000.0, 10)
    code, out = run_main(small(tmp_path, "--check"), capsys)
    assert code == 0
    assert "базовой" not in out


def test_check_fails_against_an_impossible_baseline(tmp_path, capsys):
    write_baseline(tmp_path, 1000.0, 0)
    code, out = run_main(small(tmp_path, "--check"), capsys)
    assert code == 1
    assert "fighter 1 ур.:" in out
    assert "< базовой 1000 % − 0 п.п." in out


def test_check_takes_the_tolerance_from_the_baseline_file(tmp_path, capsys):
    write_baseline(tmp_path, 1000.0, 2000)
    code, _ = run_main(small(tmp_path, "--check"), capsys)
    assert code == 0


def test_check_fails_on_a_cell_without_baseline(tmp_path, capsys):
    write_baseline(tmp_path, -1000.0, 10, level=2)
    code, out = run_main(small(tmp_path, "--check"), capsys)
    assert code == 1
    assert "нет базовой линии" in out


def test_write_baseline_writes_yaml_with_seeds_and_tolerance(tmp_path, capsys):
    code, out = run_main(small(tmp_path, "--write-baseline"), capsys)
    assert code == 0
    data = yaml.safe_load((tmp_path / "base.yaml").read_text(encoding="utf-8"))
    assert data["seeds"] == 3
    assert data["tolerance_pp"] == 10
    assert list(data["goblins3"]) == ["fighter"]
    assert list(data["goblins3"]["fighter"]) == [1]
    assert 0 <= data["goblins3"]["fighter"][1] <= 100
    assert "базовая линия записана" in out


def test_written_baseline_passes_its_own_check(tmp_path, capsys):
    run_main(small(tmp_path, "--write-baseline"), capsys)
    code, _ = run_main(small(tmp_path, "--check"), capsys)
    assert code == 0


def test_write_baseline_then_check_in_one_run(tmp_path, capsys):
    code, _ = run_main(small(tmp_path, "--write-baseline", "--check"), capsys)
    assert code == 0


def test_main_accepts_the_scene_and_difficulty_choices(capsys):
    code, _ = run_main(
        ["--seeds", "1", "--classes", "fighter", "--levels", "1", "--scene", "goblins3",
         "--difficulty", "normal"],
        capsys,
    )
    assert code == 0


def test_main_unknown_difficulty_is_rejected():
    with pytest.raises(SystemExit):
        main(["--difficulty", "epic"])


def test_main_unknown_scene_is_rejected():
    with pytest.raises(SystemExit):
        main(["--scene", "nowhere"])


@pytest.mark.parametrize("value", ["easy", "hard"])
def test_main_accepts_every_difficulty(value, capsys, monkeypatch):
    seen = {}

    def fake(context, grid, seeds, difficulty=None):
        seen.update(
            classes=grid[0], levels=grid[1], scenes=grid[2], seeds=seeds, difficulty=difficulty
        )
        return []

    monkeypatch.setattr(sim_grid, "run_grid", fake)
    assert main(["--difficulty", value]) == 0
    assert seen["difficulty"] == value


def test_main_default_baseline_is_the_module_path(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(sim_grid, "BASELINE_PATH", tmp_path / "default.yaml")
    code, _ = run_main(
        ["--seeds", "1", "--classes", "fighter", "--levels", "1", "--write-baseline"], capsys
    )
    assert code == 0
    assert (tmp_path / "default.yaml").is_file()


def test_written_baseline_keeps_the_key_order(tmp_path, capsys):
    run_main(small(tmp_path, "--write-baseline"), capsys)
    data = yaml.safe_load((tmp_path / "base.yaml").read_text(encoding="utf-8"))
    assert list(data) == ["seeds", "tolerance_pp", "goblins3"]
