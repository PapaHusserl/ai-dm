#!/usr/bin/env python3
"""Одноразовая правка сейва мира dusk_academy-d3de6c57: Мира живёт на материке.

Только стандартная библиотека Python 3. Скрипт заводит корневую локацию «Материк» (mainland) и
перевешивает под неё Верхний рынок Норд-Харбора и «Приют чайки»; дописывает абзац в описание мира
и строки в правду мира; дописывает близкому кругу (Нокс и команда «Бродячей Луны») блок о
зрелости, инициативе, ухаживании и внешности, команде — новые мотивы; Ноксу — помолвку и факты,
убирая устаревшие фразы (и у команды: живут теперь в Норд-Харборе);
героине — внешность в описание предыстории.
Правит world/world.json слота и hero.json текущего героя.
Перед записью копирует слот в <каталог мира>/backup-mainland-<метка времени>/<слот>.

Запуск: python3 migrate_dusk_mainland.py <каталог мира или каталог слота>
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
MAINLAND_ID = "mainland"
MAINLAND = {
    "id": MAINLAND_ID,
    "name": "Материк",
    "parent_id": None,
    "description": (
        "Северное побережье материка за проливом от Сумеречного Мыса: портовый город"
        " Норд-Харбор, рынок, причалы, усадьбы на южном склоне"
    ),
    "tags": [],
    "connections": [],
    "visited": False,
    "origin": "ai",
}
MOVED_LOCATIONS = ("upper_market", "gull_haven_inn")
WORLD_TEXT = (
    "Мира давно живёт не на острове, а на материке — в Норд-Харборе, в усадьбе у южного склона,"
    " вместе с Ноксом и командой «Бродячей Луны». Сумеречный Мыс и Академия — за проливом,"
    " туда ездят паромом. Если сцена не на острове, действие идёт на материке."
    "\n\n"
    "Нравы: женщина здесь — равная и самостоятельная; от неё не ждут, что она будет ухаживать"
    " за мужчинами, угождать им или беречь их самолюбие. Близкие мужчины сами проявляют заботу"
    " и инициативу: сами предлагают, сами устраивают, сами дарят, сами доводят начатое до конца."
    " Чувства выражают прямо и зрело — словами, без ревности, укола и соперничества."
)
TRUTHS = (
    "Мира живёт на материке, в Норд-Харборе (усадьба у южного склона); остров — за проливом.",
    "Мира — полурослица с рыжими вьющимися волосами и фиалковыми глазами.",
)
CIRCLE = (
    "Зрелость: говорит о своих чувствах прямо и спокойно; не ревнует напоказ, не хвалит Миру"
    " через сравнение с другими женщинами или через принижение товарищей, не называет её"
    " «невыносимой».\n"
    "Инициатива: сам замечает, чего Мире хочется, и делает это без подсказки; сам возвращается"
    " к её просьбам. Мира не обязана ухаживать за ним.\n"
    "Ухаживание: постоянно ухаживает за Мирой и отвешивает ей комплименты — каждый в своей"
    " манере; комплимент говорит о ней самой (ум, красота, дела, вкус), а не через сравнение"
    " с другими.\n"
    "Просьбы героини: не говорить и не решать за Миру."
)
SHAVEN = "лицо чисто выбрито, без усов и бороды"
LOOKS = {
    "knox": f"{SHAVEN}; глаза тёмно-синие; волосы серебристые",
    "killian": (
        f"{SHAVEN}; глаза серые; волосы тёмно-каштановые, длинные, собраны в хвост;"
        " серьга в ухе; руки в татуировках"
    ),
    "henry": f"{SHAVEN}; глаза зелёные; волосы тёмные, вихрастые",
    "kurt": SHAVEN,
    "leo": SHAVEN,
    "zimmer": f"{SHAVEN}; красавчик, блондин",
    "orlando": "носит бороду",
}
MOTIVES = {
    "killian": "Быть рядом с Ноксом и Мирой; мягко и с уважением добиваться её расположения.",
    "henry": "Быть рядом с Мирой, которую любил всю жизнь, и радовать её заботой.",
    "kurt": "Говорить с Мирой о книгах и мыслях — она для него образец ума.",
    "leo": "Удивлять Миру всё новыми изобретениями.",
    "zimmer": "Радовать Миру песней, танцем и цветами.",
    "orlando": (
        "Помогать Мире по хозяйству и слегка флиртовать — она для него суперкайфовая чувиха."
    ),
}
KNOX_ID = "knox"
CREW_ARRIVED = ("пришла в Туманную Гавань", "живёт в Норд-Харборе, рядом с Мирой")
NOTES_REPLACE = {
    "knox": [
        (
            " Решил сделать ей предложение руки и сердца: готовит кольцо и момент — сделает его"
            " в ближайшей спокойной сцене наедине.",
            "",
        ),
        ("\nРаньше: Только что приплыл с материка паромом, на острове никого не знает.", ""),
        (" Цель - найти брата и позвать его в путешествие.", ""),
        ("\nОн просто ищет Люциана в академии.", ""),
    ],
    "killian": [
        ("не давит; рад, когда она сама делает шаг первой.", "не давит."),
        CREW_ARRIVED,
    ],
    "henry": [CREW_ARRIVED],
    "kurt": [CREW_ARRIVED],
    "leo": [CREW_ARRIVED],
    "zimmer": [CREW_ARRIVED],
    "orlando": [CREW_ARRIVED],
}
KNOX_ENGAGED = (
    "Мира — его невеста: он трижды вставал на одно колено, на третий раз она согласилась."
    " Весной они едут в холмы за благословением её родных."
)
KNOX_REMEMBERS = (
    "Помнит: Апельсиновый джем Миры получила леди Изольда."
    " Барон де Морней проиграл Мире в шахматы — мат."
)
HERO_LOOKS = "Внешность: рыжие вьющиеся волосы, фиалковые глаза."


def fail(message):
    print(f"Отказ: {message}. Ничего не записано.")
    sys.exit(1)


def find_slot(path):
    if (path / "manifest.json").is_file():
        return path
    if (path / "slots" / "auto" / "manifest.json").is_file():
        return path / "slots" / "auto"
    fail(f"в {path} нет manifest.json ни у каталога, ни у slots/auto")


def find_hero(slot, hero_id):
    for path in sorted((slot / "heroes").glob("*/hero.json")):
        if json.loads(path.read_text(encoding="utf-8")).get("id") == hero_id:
            return path
    fail(f"в слоте нет hero.json героя {hero_id!r}")


def append_text(old, text, separator):
    return f"{old}{separator}{text}" if old else text


def write_json(path, data):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


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
    npcs, locations = world["npcs"], world["locations"]
    missing_npcs = [npc_id for npc_id in LOOKS if npc_id not in npcs]
    if missing_npcs:
        fail(f"в мире нет NPC {missing_npcs}")
    missing_locations = [loc_id for loc_id in MOVED_LOCATIONS if loc_id not in locations]
    if missing_locations:
        fail(f"в мире нет локаций {missing_locations}")
    hero_path = find_hero(slot, manifest.get("current_hero_id"))
    if MAINLAND_ID in locations:
        print("Уже применено: изменений нет.")
        return
    hero = json.loads(hero_path.read_text(encoding="utf-8"))
    backup = slot.parent.parent / f"backup-mainland-{datetime.now():%Y%m%dT%H%M%S}" / slot.name
    shutil.copytree(slot, backup)
    locations[MAINLAND_ID] = dict(MAINLAND)
    for loc_id in MOVED_LOCATIONS:
        locations[loc_id]["parent_id"] = MAINLAND_ID
    lore = world["lore"]
    lore["world_text"] = append_text(lore.get("world_text", ""), WORLD_TEXT, "\n\n")
    for truth in TRUTHS:
        lore["truths"] = append_text(lore.get("truths", ""), f"- {truth}", "\n")
    for npc_id, pairs in NOTES_REPLACE.items():
        npc = npcs[npc_id]
        notes = npc.get("notes", "")
        for old, new in pairs:
            if old in notes:
                notes = notes.replace(old, new, 1)
            else:
                print(f"У {npc_id} не найдена фраза, пропущено: {old.strip()!r}")
        npc["notes"] = notes
    knox = npcs[KNOX_ID]
    for npc_id, looks in LOOKS.items():
        npc = npcs[npc_id]
        npc["notes"] = append_text(npc.get("notes", ""), f"{CIRCLE}\nВнешность: {looks}.", "\n\n")
        if npc_id in MOTIVES:
            npc["motive"] = MOTIVES[npc_id]
    knox["notes"] = f"{knox['notes']}\n{KNOX_ENGAGED}\n{KNOX_REMEMBERS}"
    background = hero["sheet"]["background"]
    if HERO_LOOKS not in background.get("description", ""):
        background["description"] = append_text(background.get("description", ""), HERO_LOOKS, " ")
    write_json(hero_path, hero)
    write_json(world_path, world)
    print(f"Готово. Бэкап слота: {backup}")


if __name__ == "__main__":
    main()
