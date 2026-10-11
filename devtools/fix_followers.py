# Разовый скрипт (не pytest, в тестах не запускается): спутники Дракона отстали от героя
# (docs/decisions/stage3-live-followers.md, F5). Выставляет follows = id героя и локацию героя
# четырём NPC слота; перед правкой копирует слот в backups/ (make_backup).
# Запуск только с согласия проектировщика:
#   uv run python devtools/fix_followers.py saves drunk_dragon-ee8aa926 auto
import argparse
import sys

from ai_dm.persistence.backup import make_backup
from ai_dm.persistence.migrations import CURRENT_SCHEMA_VERSION
from ai_dm.persistence.store import load_slot, write_slot

COMPANIONS = ("bran_sedogriv", "jorgen", "lira", "edrin")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="fix_followers")
    parser.add_argument("root")
    parser.add_argument("world_id")
    parser.add_argument("slot")
    args = parser.parse_args(argv)

    bundle = load_slot(args.root, args.world_id, args.slot)
    hero = next(h for h in bundle.heroes if h.id == bundle.manifest.current_hero_id)
    backup = make_backup(args.root, args.world_id, args.slot, CURRENT_SCHEMA_VERSION)
    print(f"бэкап слота: {backup}")
    for npc_id in COMPANIONS:
        npc = bundle.world.npcs[npc_id]
        print(f"{npc.name}: {npc.location_id} -> {hero.location_id}, follows = {hero.id}")
        npc.location_id = hero.location_id
        npc.follows = hero.id
    write_slot(
        args.root, args.world_id, bundle, args.slot, saved_at=bundle.manifest.saved_at,
        version=CURRENT_SCHEMA_VERSION,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
