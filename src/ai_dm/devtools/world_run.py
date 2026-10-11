import argparse
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from ai_dm.campaign.loader import load_pack, pack_content_dir
from ai_dm.config.app import load_settings
from ai_dm.content.loader import load_registry
from ai_dm.core.clock import DAY
from ai_dm.game import boundary
from ai_dm.game.starter import new_world_from_pack
from ai_dm.llm.cost import CostLedger
from ai_dm.llm.journal import Journal
from ai_dm.llm.mock import ScriptedAdapter
from ai_dm.master.world import WorldSession

# фиксированные время и метка сохранения: два прогона дают побайтно равные бандлы
MOMENT = datetime(2000, 1, 1, tzinfo=UTC)
SAVED_AT = MOMENT.isoformat()


class WorldRun:
    def __init__(self, bundle, journal, chronicle):
        self.bundle = bundle
        self.journal = journal
        self.chronicle = chronicle


def run_world(
    registry, cfg, pack_dir, *, days, seed, world_adapter, saves_root, flags=None,
    mortality_per_day=None,
) -> WorldRun:
    # N границ по игровому дню: «нарратор» без модели двигает время на день и закрывает сцену,
    # дальше обычная граница (триггеры, вызов world) с журналом в saves_root
    app_cfg = load_settings().app
    pack = load_pack(pack_dir, registry)
    bundle = new_world_from_pack(
        registry, cfg, pack, hero=pack.manifest.start.heroes[0], seed=seed,
        world_id=f"{pack.manifest.id}-world-run", saved_at=SAVED_AT,
    )
    bundle.world.flags.update(flags or {})
    if mortality_per_day is not None:
        bundle.world.mortality_per_day = mortality_per_day
    world_id = bundle.world.world_id
    journal = Journal(Path(saves_root), world_id, app_cfg.journal)
    ledger = CostLedger(Path(saves_root), world_id)
    world = None
    if world_adapter is not None:
        world = WorldSession(
            world_adapter, app_cfg, journal=journal, ledger=ledger, now=lambda: MOMENT
        )
    for day in range(1, days + 1):
        bundle.world.clock.advance(DAY)
        boundary.close_boundary(bundle, cfg, "end_scene")
        run_id = f"bnd-world-run-{day}"
        done = boundary.finish_boundary(bundle, cfg, registry, world, run_id)
        if done.world_run_id is not None:
            journal.mark_turn(done.world_run_id, "aborted" if done.error else "committed")
        if done.error is not None:
            raise RuntimeError(f"день {day}: {done.error}")
        bundle = done.bundle
    return WorldRun(bundle, journal, bundle.chronicle)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="world_run")
    parser.add_argument("--pack", required=True, help="папка пака кампании")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--mock", metavar="PATH", help="YAML-сценарий роли world")
    parser.add_argument("--out", help="папка для журнала (по умолчанию временная)")
    parser.add_argument("--flag", action="append", default=[], help="флаг мира на старте")
    args = parser.parse_args(argv)
    settings = load_settings()
    content_dir = pack_content_dir(args.pack)
    registry = load_registry([content_dir] if content_dir is not None else [])
    world_adapter = None
    if args.mock:
        world_adapter = ScriptedAdapter.from_yaml(args.mock)
    out = args.out or tempfile.mkdtemp(prefix="ai-dm-world-run-")
    result = run_world(
        registry, settings.rules, Path(args.pack), days=args.days, seed=args.seed,
        world_adapter=world_adapter, saves_root=out, flags={name: True for name in args.flag},
    )
    records = result.journal.read_records()
    calls = len({r["run_id"] for r in records})
    print(f"Дней: {args.days}, дата: {result.bundle.world.clock.to_date()}, сид: {args.seed}")
    print(f"Вызовов world: {calls}, записей хроники: {len(result.chronicle.entries)}")
    print(f"Журнал: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
