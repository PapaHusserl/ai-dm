#!/usr/bin/env python3
"""Одноразовая правка сейва Сумеречной Академии: Нокс Велар — равный партнёр героини.

Только стандартная библиотека Python 3. Запускать при закрытой игре. Скрипт дописывает Ноксу
заметки (живут вместе, видит в ней равную, её просьбы — обещания, решил сделать предложение),
ставит motive, цель love на героиню («сделать предложение») и отношение не ниже 80.
Старые заметки сохраняет строкой «Раньше:». Правит только world/world.json слота auto.
Перед записью копирует каталог мира в <каталог мира>.bak-<метка времени>.

Запуск: python3 migrate_dusk_knox.py <каталог мира> ["просьба 1" "просьба 2" ...]
Просьбы героини (необязательно) попадают в заметки строкой «Просьбы героини: 1) …; 2) …».
"""
import glob
import json
import shutil
import sys
import time
from pathlib import Path

NAME = "Нокс"

world_dir = Path(sys.argv[1].rstrip("/"))
requests = sys.argv[2:]
slot = world_dir / "slots" / "auto"
world_path = slot / "world" / "world.json"

backup = Path(f"{world_dir}.bak-{time.strftime('%Y%m%d-%H%M%S')}")
shutil.copytree(world_dir, backup)
print("бэкап:", backup)

world = json.loads(world_path.read_text(encoding="utf-8"))
found = [k for k, v in world["npcs"].items() if NAME in v.get("name", "")]
if len(found) != 1:
    sys.exit(f"Нокс найден {len(found)} раз: {found} — поправь NAME")
npc = world["npcs"][found[0]]

hero_files = glob.glob(str(slot / "heroes" / "*" / "hero.json"))
hero = json.loads(Path(hero_files[0]).read_text(encoding="utf-8"))
she = hero["name"].split()[0]

notes = (
    f"{she} — его любимая, они живут вместе. Видит в ней равную: советуется с ней "
    "перед решениями, не опекает, не отмахивается и не сводит её слова к шутке "
    "или «милой заботе»; спорит с ней как со взрослой. Её просьбы — обещания: "
    "помнит их, выполняет или сам возвращается к ним с отчётом, не дожидаясь "
    "напоминания. Решил сделать ей предложение руки и сердца: готовит кольцо "
    "и момент — сделает его в ближайшей спокойной сцене наедине."
)
if requests:
    notes += "\nПросьбы героини: " + "; ".join(
        f"{i}) {r}" for i, r in enumerate(requests, 1))
old = npc.get("notes", "")
npc["notes"] = notes + ("\nРаньше: " + old if old and old not in notes else "")
npc["motive"] = f"Построить семью с героиней ({she}) на равных."
npc["goals"] = [g for g in npc.get("goals", []) if g["kind"] != "love"]
npc["goals"].append({
    "kind": "love", "target": hero["id"],
    "text": "сделать ей предложение руки и сердца",
    "since_s": world["clock"]["now_s"], "status": "active",
})
npc["attitude"] = max(npc.get("attitude", 0), 80)

world_path.write_text(json.dumps(world, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"готово: {npc['name']} ({found[0]}) → {hero['name']} ({hero['id']})")
print(npc["notes"])
