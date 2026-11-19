#!/usr/bin/env python3
"""Одноразовая правка сейва мира drunk_dragon-00000001: рёбра карты (М0 П2, Приложение Б).

Только стандартная библиотека Python 3. Скрипт даёт явные рёбра 15 локациям без рёбер (18 рёбер)
и правит четыре длины: А -- убирает ребро таверны к Старой башне в 48270 м (остаётся встречное в
3218 м), Б -- Аббатство к смолокурне 3200 м, В -- Остров гадюк к кургану 2000 м тропой, Г --
Железный Кряж к городу 230400 м. Правит только world/world.json слота. Повторный запуск ничего не
меняет.
Перед записью копирует слот в <каталог мира>/backup-edges-<метка времени>/<слот>.

Запуск: python3 migrate_dragon_edges.py <каталог мира или каталог слота>
Каталог мира: saves/drunk_dragon-00000001 (правится слот auto).
Каталог слота: saves/drunk_dragon-00000001/slots/auto (или другой слот).
"""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

WORLD_ID = "drunk_dragon-00000001"
MIN_SCHEMA_VERSION = 16

# (откуда, куда, метры, род пути): Приложение Б, строки 1-15 без «п»
NEW_EDGES = [
    ("city_ratusha", "upper_city_ratusha_square", 100, "road"),
    ("grey_quarter", "sanctuary_of_dawn", 800, "road"),
    ("varen_manor", "grey_quarter", 300, "road"),
    ("olbrecht_manor", "grey_quarter", 300, "road"),
    ("shop_hunting_horn", "upper_city_square", 80, "road"),
    ("dry_heather", "sanctuary_of_dawn", 700, "road"),
    ("ash_forge", "east_shaft", 300, "mine"),
    ("ancient_tomb", "ash_forge", 500, "mine"),
    ("iron_ridge_foothills_villages", "iron_ridge_foothills", 3000, "road"),
    ("dead_pine_gorge", "watch_tower_outpost", 30400, "trail"),
    ("dead_pine_gorge", "ash_forge", 30400, "trail"),
    ("deep_shaft", "watch_tower_outpost", 43200, "mine"),
    ("deep_shaft", "ash_forge", 43200, "mine"),
    ("white_winds_ledge", "watch_tower_outpost", 42000, "offroad"),
    ("white_winds_ledge", "ash_forge", 42000, "offroad"),
    ("wolf_teeth_pass", "iron_ridge", 2000, "trail"),
    ("swamp_topkoe", "old_gat", 1500, "offroad"),
    ("devils_backwater", "swamp_topkoe", 2500, "offroad"),
]
# строка А: убрать это ребро (встречное old_tower -> tavern_drunken_dragon 3218 м остаётся)
DROP_EDGE = ("tavern_drunken_dragon", "old_tower")
# строки Б-Г: (откуда, куда, метры, род пути или None -- род не меняется)
NEW_LENGTHS = [
    ("abbey_scarlet_mist", "old_tar_works", 3200, None),
    ("viper_island", "dead_barrow", 2000, "trail"),
    ("iron_ridge", "city", 230400, None),
]


def fail(message):
    print(f"Отказ: {message}. Ничего не записано.")
    sys.exit(1)


def find_slot(path):
    if (path / "manifest.json").is_file():
        return path
    if (path / "slots" / "auto" / "manifest.json").is_file():
        return path / "slots" / "auto"
    fail(f"в {path} нет manifest.json ни у каталога, ни у slots/auto")


def find_edge(locations, source, target):
    return next((c for c in locations[source]["connections"] if c["to"] == target), None)


def check_places(locations, places):
    missing = sorted({p for p in places if p not in locations})
    if missing:
        fail(f"в мире нет локаций: {', '.join(missing)}")


def plan_changes(locations):
    # список действий (текст, функция правки); пусто -- уже применено
    check_places(locations, [p for a, b, *_ in NEW_EDGES for p in (a, b)])
    check_places(locations, [p for a, b, *_ in NEW_LENGTHS for p in (a, b)])
    changes = []
    for source, target, metres, kind in NEW_EDGES:
        if find_edge(locations, source, target) or find_edge(locations, target, source):
            continue
        edge = {"to": target, "distance_m": metres, "kind": kind, "needs_transport": False}
        connections = locations[source]["connections"]
        changes.append((f"ребро {source} -> {target}", connections.append, edge))
    for source, target, metres, kind in NEW_LENGTHS:
        edge = find_edge(locations, source, target)
        if edge is None:
            fail(f"нет ребра {source} -> {target}")
        if edge["distance_m"] != metres or (kind and edge["kind"] != kind):
            update = {"distance_m": metres, **({"kind": kind} if kind else {})}
            changes.append((f"длина {source} -> {target}", edge.update, update))
    drop = find_edge(locations, *DROP_EDGE)
    if drop is not None:
        connections = locations[DROP_EDGE[0]]["connections"]
        changes.append((f"убрано ребро {DROP_EDGE[0]} -> {DROP_EDGE[1]}", connections.remove, drop))
    return changes


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    slot = find_slot(Path(sys.argv[1]).expanduser().resolve())
    manifest = json.loads((slot / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("world_id") != WORLD_ID:
        fail(f"это мир {manifest.get('world_id')!r}, нужен {WORLD_ID!r}")
    if (manifest.get("schema_version") or 0) < MIN_SCHEMA_VERSION:
        fail(f"версия сейва {manifest.get('schema_version')}, нужна {MIN_SCHEMA_VERSION} или новее")
    world_path = slot / "world" / "world.json"
    world = json.loads(world_path.read_text(encoding="utf-8"))
    changes = plan_changes(world["locations"])
    if not changes:
        print("Уже применено: изменений нет.")
        return
    backup = slot.parent.parent / f"backup-edges-{datetime.now():%Y%m%dT%H%M%S}" / slot.name
    shutil.copytree(slot, backup)
    for text, action, argument in changes:
        action(argument)
        print(text)
    tmp = world_path.with_name("world.json.tmp")
    tmp.write_text(json.dumps(world, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(world_path)
    print(f"Готово. Бэкап слота: {backup}")


if __name__ == "__main__":
    main()
