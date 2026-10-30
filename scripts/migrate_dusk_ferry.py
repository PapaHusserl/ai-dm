#!/usr/bin/env python3
"""Одноразовая правка сейва мира dusk_academy-d3de6c57: паром с новыми персонажами.

Только стандартная библиотека Python 3. Порядок: обновить репозиторий (git pull), запустить игру
один раз (догрузка добавит Франциска, Нокса и фракцию «Паром с материка»), выйти, запустить
этот скрипт. Скрипт ставит спящему триггеру прибытия срок «текущее время мира + DAYS суток»,
включает его и кладёт слух накануне. Правит только world/world.json слота.
Перед записью копирует слот в <каталог мира>/backup-ferry-<метка времени>/<слот>.

Запуск: python3 migrate_dusk_ferry.py <каталог мира или каталог слота>
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
DAYS = 1
RUMOR_BEFORE_DAYS = 1
DAY_S = 86400
OWNER_ID = "mainland_ferry"
TRIGGER_ID = "arrival"
NPC_IDS = ["francis", "knox"]
RUMOR_TEXT = "Ура, прибывает новый паром! Наверное привезет новых учеников!"


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
    faction = world["factions"].get(OWNER_ID)
    if faction is None or any(npc_id not in world["npcs"] for npc_id in NPC_IDS):
        fail(
            "в мире ещё нет парома и приезжих. Сначала запустите игру один раз"
            " (догрузка добавит персонажей), выйдите и повторите"
        )
    trigger = next((t for t in faction["opportunity"] if t["id"] == TRIGGER_ID), None)
    if trigger is None:
        fail(f"у фракции {OWNER_ID!r} нет триггера {TRIGGER_ID!r}")
    if trigger["state"] != "disabled":
        print("Уже применено: изменений нет.")
        return
    now_s = world["clock"]["now_s"]
    backup = slot.parent.parent / f"backup-ferry-{datetime.now():%Y%m%dT%H%M%S}" / slot.name
    shutil.copytree(slot, backup)
    trigger["if_"]["seconds"] = now_s + DAYS * DAY_S
    trigger["state"] = "active"
    world["notices"].append(
        {
            "id": f"ferry_rumor_{now_s}",
            "at_s": now_s,
            "deliver_at_s": now_s + (DAYS - RUMOR_BEFORE_DAYS) * DAY_S,
            "visibility": "rumor",
            "text": RUMOR_TEXT,
            "refs": list(NPC_IDS),
        }
    )
    tmp = world_path.with_name("world.json.tmp")
    tmp.write_text(json.dumps(world, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(world_path)
    print(f"Готово. Бэкап слота: {backup}")


if __name__ == "__main__":
    main()
