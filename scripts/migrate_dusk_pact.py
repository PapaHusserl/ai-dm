#!/usr/bin/env python3
"""Одноразовая правка сейва мира dusk_academy-d3de6c57: сюжетная врезка «Договор Хранителей».

Только стандартная библиотека Python 3. Порядок: обновить репозиторий (git pull), запустить игру
один раз (догрузка добавит фракцию «Хранители Договора» и гадалку Тётушку Мирту), выйти, запустить
этот скрипт. Скрипт ставит спящему триггеру визита гадалки срок «текущее время мира + DAYS суток»,
включает его и триггер успокоения, ставит флаг pact:together (Мира и Люциан вместе), дописывает
абзац о Договоре в описание мира и правду мира, заметки Люциана и (если пусты) Мирты.
Правит только world/world.json слота.
Перед записью копирует слот в <каталог мира>/backup-pact-<метка времени>/<слот>.

Запуск: python3 migrate_dusk_pact.py <каталог мира или каталог слота>
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
DAY_S = 86400
FACTION_ID = "pact_keepers"
VISIT_ID = "fortune_visit"
CALM_ID = "calm_sign"
FORTUNE_TELLER_ID = "fortune_teller_haven"
LUCIAN_ID = "lucian"
FLAG_TOGETHER = "pact:together"
FLAG_KNOWN = "pact:known"
SECRET_ID = "pact"

TRUTH = (
    "Остров держится на Договоре Хранителей — клятве, которую древние Хранители,"
    " старше Академии и её совета, заключили с ночным народом, когда люди пришли"
    " на эти берега. Договор разделил день и ночь: ночной народ хранит остров от того,"
    " что приходит из тумана, но не связывает себя с людьми узами сердца. Пока клятва"
    " цела, море спокойно, фонари горят, а Серебровод чист."
)
RULE_FOR_NARRATOR = (
    "Для рассказчика: когда Мира и Люциан явно расстались — `set_flag pact:together false`;"
    " когда снова сошлись — `set_flag pact:together true`."
)
WORLD_TEXT = (
    TRUTH
    + " Если наследник ночного народа отдаёт сердце человеку, Договор начинает мстить:"
    " сперва ему самому — он становится холоднее, отстранённее, теряет куски памяти,"
    " особенно тёплые, — а затем и острову. Злого умысла в нём нет — это яд клятвы,"
    " а не его воля. Стоит паре расстаться — равновесие возвращается, а с ним и сам"
    " наследник. Сойдутся снова — всё начнётся заново. Сами Хранители давно не"
    " показываются людям; об их воле говорят знаки, сны и те, кто умеет читать воск."
    "\n\n"
    + RULE_FOR_NARRATOR
    + " Отравление Люциана показывай сам, постепенно, без жестокости."
)
LUCIAN_NOTES = (
    "Договор Хранителей отравляет Люциана, пока он с героиней. Он холоднее,"
    " сдержаннее, иногда отвечает невпопад и не помнит недавних тёплых мгновений"
    " (подарков, обещаний, слов), но он не жесток и не груб — скорее растерян и закрыт."
    " Причины сам не знает: чувствует, что с ним что-то не так, и злится на себя."
    " Правду ему откроют древние Хранители — во сне, знаком или голосом из тумана,"
    " когда рассказчик сочтёт уместным. После расставания холод уходит за несколько"
    " дней, память возвращается; он снова тот самый Люциан — и, возможно, помнит,"
    " от чего отказался. "
    + RULE_FOR_NARRATOR
)
LUCIAN_SECRET = (
    "Договор Хранителей отравляет Люциана, пока он с героиней: холодность и провалы"
    " в тёплой памяти — яд клятвы, а не его воля. Играй это постепенно и не называй"
    " причину, пока героиня не узнала о Договоре от гадалки."
)
FORTUNE_TELLER_NOTES = (
    "Мирта видела в воске треснувшую печать и два переплетённых имени — героини и"
    " Люциана. Она знает о Договоре Хранителей из старых песен своей бабки и боится"
    " его. С Мирой говорит мягко и по-матерински, но не скрывает правды: сначала"
    " показывает знак в воске, потом рассказывает о Договоре и о том, что яд клятвы"
    " уже коснулся Люциана. Не приказывает и не судит — говорит: «Выбор твой, девочка,"
    " но остров платит за него каждый день». Советует спросить Люциана, не стал ли он"
    " забывать то, что было между ними. Когда рассказала героине о Договоре —"
    " set_flag pact:known true."
)


def fail(message):
    print(f"Отказ: {message}. Ничего не записано.")
    sys.exit(1)


def find_slot(path):
    if (path / "manifest.json").is_file():
        return path
    if (path / "slots" / "auto" / "manifest.json").is_file():
        return path / "slots" / "auto"
    fail(f"в {path} нет manifest.json ни у каталога, ни у slots/auto")


def append_text(old, text, separator):
    return f"{old}{separator}{text}" if old else text


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
    if faction is None or FORTUNE_TELLER_ID not in world["npcs"]:
        fail(
            "в мире ещё нет Хранителей Договора и гадалки. Сначала запустите игру один раз"
            " (догрузка добавит их), выйдите и повторите"
        )
    triggers = {t["id"]: t for t in faction["opportunity"]}
    if VISIT_ID not in triggers or CALM_ID not in triggers:
        fail(f"у фракции {FACTION_ID!r} нет триггеров {VISIT_ID!r} и {CALM_ID!r}")
    if triggers[VISIT_ID]["state"] != "disabled":
        print("Уже применено: изменений нет.")
        return
    now_s = world["clock"]["now_s"]
    backup = slot.parent.parent / f"backup-pact-{datetime.now():%Y%m%dT%H%M%S}" / slot.name
    shutil.copytree(slot, backup)
    triggers[VISIT_ID]["if_"]["seconds"] = now_s + DAYS * DAY_S
    triggers[VISIT_ID]["state"] = "active"
    triggers[CALM_ID]["state"] = "active"
    world["flags"][FLAG_TOGETHER] = True
    lore = world["lore"]
    lore["world_text"] = append_text(lore.get("world_text", ""), WORLD_TEXT, "\n\n")
    lore["truths"] = append_text(lore.get("truths", ""), f"- {TRUTH}", "\n")
    lucian = world["npcs"][LUCIAN_ID]
    lucian["notes"] = append_text(lucian.get("notes", ""), LUCIAN_NOTES, "\n\n")
    lucian["secrets"].append(
        {
            "id": SECRET_ID,
            "text": LUCIAN_SECRET,
            "reveal_if": {"type": "flag", "name": FLAG_KNOWN, "value": True},
            "revealed": False,
            "narrative_ok": False,
        }
    )
    fortune_teller = world["npcs"][FORTUNE_TELLER_ID]
    if not fortune_teller.get("notes"):
        fortune_teller["notes"] = FORTUNE_TELLER_NOTES
    tmp = world_path.with_name("world.json.tmp")
    tmp.write_text(json.dumps(world, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(world_path)
    print(f"Готово. Бэкап слота: {backup}")


if __name__ == "__main__":
    main()
