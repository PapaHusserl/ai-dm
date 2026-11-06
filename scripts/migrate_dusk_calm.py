#!/usr/bin/env python3
"""Одноразовая правка сейва мира dusk_academy-d3de6c57: «лилии вянут» без причины.

Только стандартная библиотека Python 3. migrate_dusk_pact.py безусловно поставил флаг pact:together
в True, хотя Мира и Люциан не вместе: триггер blight_sign фракции pact_keepers (без cooldown) шлёт
беды каждый ход, а calm_sign ждёт False, которого никто не ставил. Скрипт ставит pact:together в
False и задаёт триггеру blight_sign cooldown «7d» (в любом случае), чтобы при будущем воссоединении
беды не шли каждый ход. Больше ничего не трогает; правит только world/world.json слота.
Перед записью копирует слот в <каталог мира>/backup-calm-<метка времени>/<слот>.

Запуск: python3 migrate_dusk_calm.py <каталог мира или каталог слота>
Каталог мира: saves/dusk_academy-d3de6c57 (правится слот auto).
Каталог слота: saves/dusk_academy-d3de6c57/slots/auto (или другой слот).
"""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

WORLD_ID = "dusk_academy-d3de6c57"
SCHEMA_VERSIONS = (9, 10, 11, 12, 13, 14)
FACTION_ID = "pact_keepers"
BLIGHT_ID = "blight_sign"
BLIGHT_COOLDOWN = "7d"
FLAG_TOGETHER = "pact:together"


def fail(message):
    print(f"Отказ: {message}. Ничего не записано.")
    sys.exit(1)


def find_slot(path):
    if (path / "manifest.json").is_file():
        return path
    if (path / "slots" / "auto" / "manifest.json").is_file():
        return path / "slots" / "auto"
    fail(f"в {path} нет manifest.json ни у каталога, ни у slots/auto")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    slot = find_slot(Path(sys.argv[1]).expanduser().resolve())
    manifest = json.loads((slot / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("world_id") != WORLD_ID:
        fail(f"это мир {manifest.get('world_id')!r}, нужен {WORLD_ID!r}")
    if manifest.get("schema_version") not in SCHEMA_VERSIONS:
        fail(f"версия сейва {manifest.get('schema_version')}, нужна одна из {SCHEMA_VERSIONS}")
    world_path = slot / "world" / "world.json"
    world = json.loads(world_path.read_text(encoding="utf-8"))
    faction = world["factions"].get(FACTION_ID)
    if faction is None:
        fail(f"в мире нет фракции {FACTION_ID!r}")
    blight = next((t for t in faction["opportunity"] if t["id"] == BLIGHT_ID), None)
    if blight is None:
        fail(f"у фракции {FACTION_ID!r} нет триггера {BLIGHT_ID!r}")
    flags = world["flags"]
    if flags.get(FLAG_TOGETHER) is False and blight.get("cooldown") == BLIGHT_COOLDOWN:
        print("Уже применено: изменений нет.")
        return
    backup = slot.parent.parent / f"backup-calm-{datetime.now():%Y%m%dT%H%M%S}" / slot.name
    shutil.copytree(slot, backup)
    flags[FLAG_TOGETHER] = False
    blight["cooldown"] = BLIGHT_COOLDOWN
    tmp = world_path.with_name("world.json.tmp")
    tmp.write_text(json.dumps(world, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(world_path)
    print(f"Готово. Бэкап слота: {backup}")


if __name__ == "__main__":
    main()
