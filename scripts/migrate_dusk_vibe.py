#!/usr/bin/env python3
"""Одноразовая правка сейва мира dusk_academy-d3de6c57: вольный хиппово-мирный дух мира.

Только стандартная библиотека Python 3. Запускать при закрытой игре. Скрипт дописывает в
world.tone.notes четыре строки (вольный дух, взаимный флирт и равенство, многолюбие без осуждения,
ревность вслух и спокойно), в world.lore.world_text — фразу про нравы острова, а Ноксу заменяет
ревность со срывами (из migrate_dusk_ship) на спокойную; у приятелей с «Бродячей Луны» смягчает
заметки про ревность, угождение и страх перед Ноксом (если они уже есть в сейве).
Всё остальное в заметках сохраняется. Правит только world/world.json слота.
Перед записью копирует слот в <каталог мира>/backup-vibe-<метка времени>/<слот>.

Запуск: python3 migrate_dusk_vibe.py <каталог мира или каталог слота>
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
MARKER = "хиппово-беззаботный"
TONE_LINES = [
    "Дух мира вольный, хиппово-беззаботный: любовь и влечение — радость и свобода, без агрессии,"
    " насилия, давления и собственничества",
    "Флирт взаимный: героиня сама зовёт, дразнит и выбирает; нет «главы семьи» и мужчины-решалы,"
    " решения принимают вместе, на равных",
    "Многолюбие и свободные союзы — норма, окружающие принимают их спокойно и без осуждения",
    "Ревность — обычное чувство, его говорят вслух спокойно («мне немного ревниво, обнимешь?»);"
    " без срывов, ссор, вызовов и запретов",
]
WORLD_OLD = "Тон игры — добрая романтическая история о дружбе, доверии и первой любви."
WORLD_NEW = (
    f"{WORLD_OLD} Нравы на острове вольные, почти хиппи: любовь и влечение здесь радость без"
    " насилия, давления и собственничества, флирт взаимный, равных союзов много, и никто не"
    " осуждает, если любят сразу нескольких."
)
KNOX_ID = "knox"
KNOX_OLD = (
    "Ревность к старым приятелям: когда друзья с «Бродячей Луны» подкатывают к героине, "
    "Нокс ревнует. Иногда держит лицо и отшучивается, иногда срывается — резкое слово, "
    "вызов на спор, уводит героиню прочь. Друзей любит: ссорится с ними, но не до разрыва, "
    "быстро остывает и мирится."
)
KNOX_NEW = (
    "Ревность к приятелям и брату он чувствует, но говорит о ней спокойно и открыто, без срывов"
    " и ссор: признаётся, обнимает, отшучивается; героиню не удерживает и не ограничивает."
    " Многолюбие принимает без осуждения."
)
MOOD_ADD = "вольный хиппово-мирный дух"
# npc_id -> поле -> [(старый фрагмент, новый)]
NPC_REPLACEMENTS = {
    "henry": {
        "notes": [
            (
                "старается угодить ей во всём. Нокса считает другом, но его ревность задевает"
                " Генри, и он не уступает.",
                "заботится о ней по-дружески и на равных. Нокса считает другом; когда тот спокойно"
                " признаётся в ревности, Генри отвечает так же честно и по-доброму, без"
                " соперничества.",
            )
        ],
        "motive": [("и угождать ей во всём.", "и радовать её заботой.")],
    },
    "orlando": {
        "notes": [("Нокса немного побаивается.", "С Ноксом ему легко и по-приятельски.")]
    },
    "zimmer": {
        "notes": [
            (
                "на его ревность отвечает шуткой.",
                "на его спокойно названную ревность отвечает шуткой и объятием.",
            )
        ]
    },
    "killian": {
        "notes": [
            (
                "слушает её, спрашивает мнения, не давит.",
                "слушает её, спрашивает мнения, не давит; рад, когда она сама делает шаг первой.",
            )
        ]
    },
    "kurt": {"notes": [("Нокса уважает и не хочет с ним ссориться.", "Нокса уважает.")]},
}


def fail(message):
    print(f"Отказ: {message}. Ничего не записано.")
    sys.exit(1)


def find_slot(path):
    if (path / "manifest.json").is_file():
        return path
    if (path / "slots" / "auto" / "manifest.json").is_file():
        return path / "slots" / "auto"
    fail(f"в {path} нет manifest.json ни у каталога, ни у slots/auto")


def soften_knox(knox):
    notes = knox.get("notes", "")
    if KNOX_OLD in notes:
        knox["notes"] = notes.replace(KNOX_OLD, KNOX_NEW)
    elif KNOX_NEW not in notes:
        knox["notes"] = f"{notes}\n\n{KNOX_NEW}" if notes else KNOX_NEW


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
    original = json.dumps(world, ensure_ascii=False, indent=2)
    tone = world["tone"]
    if MARKER not in tone.get("notes", ""):
        lines = "\n".join(f"- {line}" for line in TONE_LINES)
        tone["notes"] = f"{tone['notes']}\n{lines}" if tone.get("notes") else lines
    if MOOD_ADD not in tone.get("mood", ""):
        tone["mood"] = f"{tone['mood']}; {MOOD_ADD}" if tone.get("mood") else MOOD_ADD
    lore = world["lore"]
    if WORLD_OLD in lore["world_text"] and WORLD_NEW not in lore["world_text"]:
        lore["world_text"] = lore["world_text"].replace(WORLD_OLD, WORLD_NEW)
    if KNOX_ID in world["npcs"]:
        soften_knox(world["npcs"][KNOX_ID])
    for npc_id, fields in NPC_REPLACEMENTS.items():
        npc = world["npcs"].get(npc_id)
        if npc is None:
            continue
        for field, pairs in fields.items():
            for old, new in pairs:
                if field in npc:
                    npc[field] = npc[field].replace(old, new)
    result = json.dumps(world, ensure_ascii=False, indent=2)
    if result == original:
        print("Уже применено: изменений нет.")
        return
    backup = slot.parent.parent / f"backup-vibe-{datetime.now():%Y%m%dT%H%M%S%f}" / slot.name
    shutil.copytree(slot, backup)
    tmp = world_path.with_name("world.json.tmp")
    tmp.write_text(result, encoding="utf-8")
    tmp.replace(world_path)
    print(f"Готово. Бэкап слота: {backup}")


if __name__ == "__main__":
    main()
