import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from ai_dm.config.settings import load_rules_config
from ai_dm.content.loader import load_registry
from ai_dm.devtools.grid_heroes import CLASSES, build_hero
from ai_dm.devtools.sim_combat import build_scenario, simulate
from ai_dm.game.difficulty import DIFFICULTIES

# сцены сетки: имя сценария sim_combat; сцены паков добавятся вместе с монстрами (К7д)
SCENES = {"goblins3": "goblins3"}
LEVELS = range(1, 6)
BASELINE_PATH = Path(__file__).resolve().parents[3] / "devtools" / "sim_grid_baseline.yaml"
DEFAULT_SEEDS = 200
DEFAULT_TOLERANCE_PP = 10


@dataclass
class Cell:
    wins: int
    deaths: int
    other: int
    mean_rounds: float

    @property
    def total(self) -> int:
        return self.wins + self.deaths + self.other

    @property
    def share(self) -> float:
        return 100 * self.wins / self.total


@dataclass
class Row:
    scene: str
    class_id: str
    level: int
    cell: Cell


def run_cell(cell, context, seeds, difficulty=None) -> Cell:
    # cell -- (класс, уровень, сцена); context -- (registry, cfg)
    class_id, level, scene = cell
    registry, cfg = context
    hero = build_hero(class_id, level, registry)
    wins = deaths = other = rounds = 0
    seeds = list(seeds)
    for seed in seeds:
        scenario = build_scenario(
            SCENES[scene], registry, cfg, seed, hero=hero.model_copy(deep=True),
            difficulty=difficulty,
        )
        result = simulate(scenario)
        rounds += result.rounds
        if result.outcome == "victory":
            wins += 1
        elif result.outcome == "hero_dead":
            deaths += 1
        else:
            other += 1
    return Cell(wins, deaths, other, rounds / len(seeds))


def run_grid(context, grid, seeds, difficulty=None) -> list[Row]:
    # grid -- (классы, уровни, сцены); порядок сцена -> класс -> уровень
    classes, levels, scenes = grid
    rows = []
    for scene in scenes:
        for class_id in classes:
            for level in levels:
                cell = run_cell((class_id, level, scene), context, seeds, difficulty)
                rows.append(Row(scene, class_id, level, cell))
    return rows


def table_lines(rows) -> list[str]:
    lines = []
    for scene in dict.fromkeys(row.scene for row in rows):
        lines.append(f"Сцена {scene}: побед N/M (доля), средние раунды")
        for row in rows:
            if row.scene != scene:
                continue
            cell = row.cell
            lines.append(
                f"  {row.class_id:8} {row.level} ур.: побед {cell.wins}/{cell.total} "
                f"({cell.share:.1f} %), ср. раундов {cell.mean_rounds:.2f}"
            )
    return lines


def compare(rows, baseline, tolerance) -> list[str]:
    # клетки хуже базовой линии больше чем на tolerance п.п.; клетки без базовой -- тоже строка
    lines = []
    for row in rows:
        known = baseline.get(row.scene, {}).get(row.class_id, {})
        label = f"{row.class_id} {row.level} ур."
        if row.level not in known:
            lines.append(f"{label}: нет базовой линии")
            continue
        base = known[row.level]
        if row.cell.share < base - tolerance:
            lines.append(
                f"{label}: {row.cell.share:.0f} % < базовой {base:.0f} % − {tolerance} п.п."
            )
    return lines


def baseline_data(rows, seeds, tolerance) -> dict:
    data = {"seeds": seeds, "tolerance_pp": tolerance}
    for row in rows:
        scene = data.setdefault(row.scene, {})
        scene.setdefault(row.class_id, {})[row.level] = round(row.cell.share, 1)
    return data


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="sim_grid")
    parser.add_argument("--seeds", type=int, default=DEFAULT_SEEDS)
    parser.add_argument("--classes", nargs="+", choices=CLASSES, default=list(CLASSES))
    parser.add_argument("--levels", nargs="+", type=int, default=list(LEVELS))
    parser.add_argument("--scene", nargs="+", choices=list(SCENES), default=list(SCENES))
    parser.add_argument(
        "--difficulty", choices=DIFFICULTIES,
        help="сложность в settings мира; на будущее, для сцен с бюджетом боя (К7д)",
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--baseline", type=Path, default=BASELINE_PATH)
    args = parser.parse_args(argv)
    context = (load_registry(), load_rules_config())
    grid = (args.classes, args.levels, args.scene)
    rows = run_grid(context, grid, range(args.seeds), args.difficulty)
    for line in table_lines(rows):
        print(line)
    if args.write_baseline:
        data = baseline_data(rows, args.seeds, DEFAULT_TOLERANCE_PP)
        args.baseline.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        print(f"базовая линия записана: {args.baseline}")
    if args.check:
        baseline = yaml.safe_load(args.baseline.read_text(encoding="utf-8"))
        worse = compare(rows, baseline, baseline["tolerance_pp"])
        for line in worse:
            print(line)
        return 1 if worse else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
