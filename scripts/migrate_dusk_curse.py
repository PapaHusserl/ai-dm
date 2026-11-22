#!/usr/bin/env python3
"""Одноразовая правка сейва мира dusk_academy-d3de6c57: Договор Хранителей разрушен по сюжету.

Только стандартная библиотека Python 3. Запускать при закрытой игре. На Первом пороге Серебровода
(сцена 236) Мира и Нокс вывели Люциана из ледяного оцепенения Договора, но мир этого не знал:
заметки Люциана и гадалки Мирты описывали яд клятвы как действующий, а триггер blight_sign
фракции pact_keepers слал беды, пока pact:together = True. Скрипт:
- ставит флаг pact:broken = True (pact:together не трогает: Мира и Люциан вместе);
- переписывает notes Люциана и Мирты и текст секрета pact в прошедшем времени;
- выключает триггеры blight_sign и calm_sign (state = "disabled").
Заодно — ручные репорты игрока после migrate_dusk_mainland (t3189–t4000): дописывает строки
в world.tone.notes (капризность, уменьшительные, «толстушки», «помогает» по дому, «потребовать»,
усы у бритых) и в заметки Нокса, лорда Кассиана, леди Изольды и стряпчего Юлиана.
Строки дописываются, только если их ещё нет; остальное в заметках сохраняется.
Правит только world/world.json слота. Перед записью копирует слот в
<каталог мира>/backup-curse-<метка времени>/<слот>.

Запуск: python3 migrate_dusk_curse.py <каталог мира или каталог слота>
Каталог мира: saves/dusk_academy-d3de6c57 (правится слот auto).
Каталог слота: saves/dusk_academy-d3de6c57/slots/auto (или другой слот).
"""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

WORLD_ID = "dusk_academy-d3de6c57"
MIN_SCHEMA_VERSION = 14
FACTION_ID = "pact_keepers"
TRIGGER_IDS = ("blight_sign", "calm_sign")
FLAG_BROKEN = "pact:broken"
SECRET_ID = "pact"

LUCIAN_NOTES = (
    "Договор Хранителей разрушен: на Первом пороге Серебровода Мира и Нокс вывели Люциана из ледяного "
    "оцепенения, яд клятвы ушёл и больше не действует. Холодность, провалы в тёплой памяти и "
    "растерянность прошли — он снова тот самый Люциан и помнит всё, в том числе время под проклятием. "
    "Учится заново жить и держать рубеж без саморазрушения. Близость с Мирой ему и острову больше не "
    "вредит; проклятие не возвращать и его симптомов не играть."
)
MIRTA_NOTES = (
    "Мирта когда-то видела в воске треснувшую печать и два переплетённых имени — героини и Люциана — и "
    "предупредила Миру о Договоре Хранителей. Теперь Договор разрушен, печать в воске больше не "
    "трескается, и Мирта с облегчением говорит об этом как о прошлом. С Мирой — мягкая и "
    "по-матерински тёплая."
)
SECRET_TEXT = (
    "Договор Хранителей отравлял Люциана, пока он был с героиней: холодность и провалы в тёплой "
    "памяти были ядом клятвы, а не его волей. Теперь Договор разрушен, яд ушёл."
)
TONE_LINES = (
    "- Просьбы и желания Миры — не каприз: не называй её капризной и не пиши, что она «капризно тянет», "
    "пока она сама так не скажет",
    "- Мира — взрослая женщина: без уменьшительных о ней (личико, ручки, носик) ни в речи героев, "
    "ни в тексте мастера",
    "- Никого не называть толстушками и не высмеивать тело — даже капибару",
    "- Мужчина, который делает что-то по дому, где живёт, не «помогает», а просто живёт: так его и описывай",
    "- Не подсказывай Мире что-то требовать у домашних: она просит, они делают сами",
    "- У Нокса, Киллиана и других бритых мужчин усов нет: никаких «усмехнулся в усы»",
)
NPC_LINES = {
    "knox": (
        "Ласковые прозвища, которые Мире неприятны: «глупая моя радость», «соня». Не использовать; "
        "зови по имени — Мира.",
        "Нокс — ночной народ, а не нежить и не жуткий вампир: живой, тёплый, без клыков, крови и "
        "замогильной жути.",
    ),
    "lord_cassian": (
        "Лорд, а не князь. Живёт с леди Изольдой в поместье Вороний Утёс на острове, в столицу не "
        "переезжает.",
    ),
    "lady_isolda": (
        "Живёт с лордом Кассианом в поместье Вороний Утёс на острове, в столицу не переезжает.",
    ),
    "clerk_julian": (
        "Живёт и работает в Городской канцелярии Норд-Харбора. В доме Миры не живёт; приходит только "
        "по делу или по приглашению и в её частные разговоры не вмешивается.",
    ),
}


def append_lines(text, lines):
    # дописывает недостающие строки в конец текста; возвращает новый текст
    text = text or ""
    missing = [line for line in lines if line not in text]
    if not missing:
        return text
    head = [text.rstrip()] if text.strip() else []
    return "\n".join(head + missing)


def fail(message):
    print(f"Отказ: {message}. Ничего не записано.")
    sys.exit(1)


def find_slot(path):
    if (path / "manifest.json").is_file():
        return path
    if (path / "slots" / "auto" / "manifest.json").is_file():
        return path / "slots" / "auto"
    fail(f"в {path} нет manifest.json ни у каталога, ни у slots/auto")


def pick(items, item_id, what):
    found = next((x for x in items if x["id"] == item_id), None)
    if found is None:
        fail(f"нет {what} {item_id!r}")
    return found


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
    npcs = world["npcs"]
    for npc_id in ("lucian", "fortune_teller_haven", *NPC_LINES):
        if npc_id not in npcs:
            fail(f"в мире нет NPC {npc_id!r}")
    faction = world["factions"].get(FACTION_ID)
    if faction is None:
        fail(f"в мире нет фракции {FACTION_ID!r}")
    triggers = [pick(faction["opportunity"], t, "триггера") for t in TRIGGER_IDS]
    secret = pick(npcs["lucian"]["secrets"], SECRET_ID, "секрета")
    before = json.dumps(world, ensure_ascii=False, sort_keys=True)
    world["flags"][FLAG_BROKEN] = True
    npcs["lucian"]["notes"] = LUCIAN_NOTES
    npcs["fortune_teller_haven"]["notes"] = MIRTA_NOTES
    secret["text"] = SECRET_TEXT
    for trigger in triggers:
        trigger["state"] = "disabled"
    world["tone"]["notes"] = append_lines(world["tone"].get("notes"), TONE_LINES)
    for npc_id, lines in NPC_LINES.items():
        npcs[npc_id]["notes"] = append_lines(npcs[npc_id].get("notes"), lines)
    if json.dumps(world, ensure_ascii=False, sort_keys=True) == before:
        print("Уже применено: изменений нет.")
        return
    backup = slot.parent.parent / f"backup-curse-{datetime.now():%Y%m%dT%H%M%S}" / slot.name
    shutil.copytree(slot, backup)
    tmp = world_path.with_name("world.json.tmp")
    tmp.write_text(json.dumps(world, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(world_path)
    print(f"Готово. Бэкап слота: {backup}")


if __name__ == "__main__":
    main()
