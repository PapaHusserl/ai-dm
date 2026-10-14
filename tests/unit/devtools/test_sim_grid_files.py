# Партия К7к, п. 4.3-4.4: файлы репозитория вокруг сетки -- базовая линия и цель Makefile.
# Отдельно от test_sim_grid.py: читают корень репозитория (под mutmut его нет).
from pathlib import Path

import yaml

from ai_dm.devtools import sim_grid
from ai_dm.devtools.grid_heroes import CLASSES
from ai_dm.devtools.sim_grid import main

ROOT = Path(__file__).resolve().parents[3]


def small(tmp_path, *extra):
    return ["--seeds", "3", "--classes", "fighter", "--levels", "1", "--baseline",
            str(tmp_path / "base.yaml"), *extra]


def test_write_baseline_does_not_touch_the_repo_baseline(tmp_path, capsys):
    path = ROOT / "devtools" / "sim_grid_baseline.yaml"
    before = path.read_bytes()
    main(small(tmp_path, "--write-baseline"))
    capsys.readouterr()
    assert path.read_bytes() == before


# базовая линия репозитория и Makefile

def repo_baseline():
    return yaml.safe_load((ROOT / "devtools" / "sim_grid_baseline.yaml").read_text("utf-8"))


def test_repo_baseline_header():
    data = repo_baseline()
    assert data["seeds"] == 200
    assert data["tolerance_pp"] == 10


def test_repo_baseline_covers_the_whole_grid():
    scene = repo_baseline()["goblins3"]
    assert list(scene) == list(CLASSES)
    for class_id in CLASSES:
        assert sorted(scene[class_id]) == [1, 2, 3, 4, 5]
        for share in scene[class_id].values():
            assert 0 <= share <= 100


def test_repo_baseline_fighter_level_1_is_the_k1_measure():
    assert repo_baseline()["goblins3"]["fighter"][1] == 32.0


def test_default_baseline_path_is_the_repo_file():
    assert sim_grid.BASELINE_PATH == ROOT / "devtools" / "sim_grid_baseline.yaml"


def test_makefile_has_the_sim_grid_target():
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "\nsim-grid:\n\tuv run python -m ai_dm.devtools.sim_grid --check\n" in text
    phony = next(line for line in text.splitlines() if line.startswith(".PHONY"))
    assert "sim-grid" in phony.split()


def test_sim_grid_is_not_part_of_quality_or_test():
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith(("quality:", "test:", "cov:")):
            assert "sim-grid" not in line


# К7д: сцена cellar в базовой линии, goblins3 прежняя

GOBLINS3_K7K = {
    "fighter": {1: 32.0, 2: 69.5, 3: 87.0, 4: 97.5, 5: 99.5},
    "rogue": {1: 0.0, 2: 1.0, 3: 1.5, 4: 7.5, 5: 17.0},
    "cleric": {1: 0.0, 2: 0.0, 3: 1.0, 4: 5.0, 5: 11.0},
    "wizard": {1: 0.0, 2: 8.0, 3: 27.0, 4: 52.0, 5: 67.5},
    "ranger": {1: 1.5, 2: 6.0, 3: 14.0, 4: 22.0, 5: 88.0},
}


def test_repo_baseline_goblins3_is_unchanged():
    assert repo_baseline()["goblins3"] == GOBLINS3_K7K


def test_repo_baseline_covers_the_whole_cellar_grid():
    scene = repo_baseline()["cellar"]
    assert list(scene) == list(CLASSES)
    for class_id in CLASSES:
        assert sorted(scene[class_id]) == [1, 2, 3, 4, 5]
        for share in scene[class_id].values():
            assert 0 <= share <= 100


def test_repo_baseline_scene_order():
    assert list(repo_baseline())[2:] == ["goblins3", "cellar"]
