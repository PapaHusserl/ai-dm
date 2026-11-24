#!/usr/bin/env python3
"""Правка сейва мира dusk_academy: привязка кораблей связи к своим причалам.

Только стандартная библиотека Python 3. Шхуна «Бродячая Луна» (wandering_moon_deck) стоит у
ferry_pier: parent_id ferry_pier, связь палуба <-> ferry_pier 20 м в обе стороны, связи с
white_lily_mansion убираются в обе стороны. Фрегат «Северный барс» (frigate_deck): добавляется
nord_harbor_docks -> frigate_deck 20 м, убирается court_expert_room -> frigate_deck.
Правит по факту состояния: нет локации -- пропуск с сообщением, связь уже есть -- не дублируется,
у существующих связей поля не теряются; новая связь -- только to и distance_m, как в сейве.
Повторный запуск ничего не меняет.
Правит world/world.json всех слотов. Перед записью копирует изменённый слот в
<каталог мира>/backup-ships-<метка времени>/<слот>.

Запуск: python3 fix_dusk_ships.py [--dry-run] <каталог мира или каталог слота>
--dry-run: только показать, что изменится, ничего не писать.
"""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

WORLD_ID = "dusk_academy-d3de6c57"

DECK_MOON = "wandering_moon_deck"
DECK_FRIGATE = "frigate_deck"
# (корабль, новый parent_id)
NEW_PARENTS = [(DECK_MOON, "ferry_pier")]
# (откуда, куда, метры): добавить связь, если её нет
ADD_EDGES = [
    (DECK_MOON, "ferry_pier", 20),
    ("ferry_pier", DECK_MOON, 20),
    ("nord_harbor_docks", DECK_FRIGATE, 20),
]
# (откуда, куда): убрать связь, если она есть
DROP_EDGES = [
    (DECK_MOON, "white_lily_mansion"),
    ("white_lily_mansion", DECK_MOON),
    ("court_expert_room", DECK_FRIGATE),
]


def fail(message):
    print(f"Отказ: {message}. Ничего не записано.")
    sys.exit(1)


def find_slots(path):
    if (path / "manifest.json").is_file():
        return [path]
    slots = sorted(p.parent for p in path.glob("slots/*/manifest.json"))
    if not slots:
        fail(f"в {path} нет manifest.json ни у каталога, ни у slots/*")
    return slots


def find_edge(locations, source, target):
    return next((c for c in locations[source]["connections"] if c["to"] == target), None)


def plan_changes(locations):
    # список (текст, функция правки, аргумент); пусто -- уже применено; пропуски -- в skipped
    changes, skipped = [], []
    for ship, parent in NEW_PARENTS:
        if ship not in locations:
            skipped.append(f"нет локации {ship}: parent_id не правлю")
        elif locations[ship].get("parent_id") != parent:
            changes.append((f"parent_id {ship} -> {parent}", locations[ship].update,
                            {"parent_id": parent}))
    for source, target, metres in ADD_EDGES:
        missing = [p for p in (source, target) if p not in locations]
        if missing:
            skipped.append(f"нет локации {', '.join(missing)}: связь {source}->{target} пропущена")
        elif find_edge(locations, source, target) is None:
            connections = locations[source]["connections"]
            changes.append((f"связь {source} -> {target} {metres} м", connections.append,
                            {"to": target, "distance_m": metres}))
    for source, target in DROP_EDGES:
        if source not in locations:
            skipped.append(f"нет локации {source}: связь {source} -> {target} не убираю")
            continue
        edge = find_edge(locations, source, target)
        if edge is not None:
            changes.append((f"убрана связь {source} -> {target}",
                            locations[source]["connections"].remove, edge))
    return changes, skipped


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]
    if len(args) != 1:
        print(__doc__)
        sys.exit(2)
    path = Path(args[0]).expanduser().resolve()
    slots = find_slots(path)
    world_dir = slots[0].parent.parent  # slots/<слот> -> каталог мира
    stamp = f"{datetime.now():%Y%m%dT%H%M%S}"
    for slot in slots:
        manifest = json.loads((slot / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("world_id") != WORLD_ID:
            fail(f"слот {slot.name}: мир {manifest.get('world_id')!r}, нужен {WORLD_ID!r}")
    for slot in slots:
        world_path = slot / "world" / "world.json"
        world = json.loads(world_path.read_text(encoding="utf-8"))
        changes, skipped = plan_changes(world["locations"])
        for text in skipped:
            print(f"[{slot.name}] пропуск: {text}")
        if not changes:
            print(f"[{slot.name}] Уже применено: изменений нет.")
            continue
        backup = world_dir / f"backup-ships-{stamp}" / slot.name
        if not dry_run:
            shutil.copytree(slot, backup)
        for text, action, argument in changes:
            action(argument)
            print(f"[{slot.name}] {text}")
        if dry_run:
            print(f"[{slot.name}] сухой прогон: ничего не записано.")
            continue
        tmp = world_path.with_name("world.json.tmp")
        tmp.write_text(json.dumps(world, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(world_path)
        print(f"[{slot.name}] Готово. Бэкап слота: {backup}")


if __name__ == "__main__":
    main()
