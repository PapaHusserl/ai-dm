#!/usr/bin/env python3
"""Одноразовая правка сейва мира dusk_academy-d3de6c57: пометка «все персонажи 18+».

Только стандартная библиотека Python 3. Меняет в слоте auto два поля:
world.lore.world_text и world.tone.notes. Перед записью копирует слот в
<каталог мира>/backup-18plus-<метка времени>/<слот>.

Запуск: python3 migrate_dusk_18plus.py <каталог мира или каталог слота>
Каталог мира: saves/dusk_academy-d3de6c57 (правится слот auto).
Каталог слота: saves/dusk_academy-d3de6c57/slots/auto (или другой слот).
"""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

WORLD_ID = "dusk_academy-d3de6c57"
SCHEMA_VERSIONS = (9, 10, 11)
MARKER = "(18+)"
TEXT_REPLACEMENTS = [
    (
        "старая школа магии со шпилями, оранжереей и библиотекой, где свечи никогда не гаснут.",
        "высшая школа магии со шпилями, оранжереей и библиотекой, где свечи никогда не гаснут."
        " Все студенты, включая первокурсников, — взрослые люди (18+);"
        " ночной народ дома Веларов — взрослые, нестареющие.",
    ),
    ("учатся дети людей,", "учатся молодые люди,"),
    ("несколько юных представителей", "несколько молодых на вид представителей"),
]
NOTES_LINE = "Все персонажи — совершеннолетние (18+)"


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
    text = world["lore"]["world_text"]
    notes = world["tone"]["notes"]
    text_done = MARKER in text
    notes_done = MARKER in notes
    if text_done and notes_done:
        print("Уже применено: изменений нет.")
        return
    if not text_done:
        for old, new in TEXT_REPLACEMENTS:
            if old not in text:
                fail(f"в world_text нет ожидаемого фрагмента {old[:40]!r}")
            text = text.replace(old, new)
    if not notes_done:
        notes = f"{notes}\n- {NOTES_LINE}" if notes else f"- {NOTES_LINE}"
    backup = slot.parent.parent / f"backup-18plus-{datetime.now():%Y%m%dT%H%M%S}" / slot.name
    shutil.copytree(slot, backup)
    world["lore"]["world_text"] = text
    world["tone"]["notes"] = notes
    tmp = world_path.with_name("world.json.tmp")
    tmp.write_text(json.dumps(world, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(world_path)
    print(f"Готово. Бэкап слота: {backup}")


if __name__ == "__main__":
    main()
