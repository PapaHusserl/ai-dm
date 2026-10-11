# ruff: noqa: E501
# Одноразовый конвертер сырого слота «Пьяный Дракон» в пак campaigns/drunk_dragon/ (этап 3, П7).
# Детерминированный, без модели: те же входные файлы -- те же байты на выходе.
# Запуск: uv run python devtools/import_dragon.py
#         uv run python devtools/import_dragon.py --slot <слот> --out <каталог пака> --drafts-doc <файл.md>
# Черновики ИИ лежат в devtools/dragon_drafts.yaml; в пак они попадают с комментарием `# draft`.
import argparse
import json
import re
import shutil
from pathlib import Path

import yaml

from ai_dm.core.clock import DAY, GameClock, default_calendar

ROOT = Path(__file__).resolve().parents[1]
DRAFTS_FILE = Path(__file__).resolve().parent / "dragon_drafts.yaml"
DEFAULT_SLOT = ROOT / "saves" / "drunk_dragon" / "slots" / "manual-import"
DEFAULT_OUT = ROOT / "campaigns" / "drunk_dragon"
DEFAULT_DRAFTS_DOC = ROOT / "docs" / "decisions" / "stage3-p7-drafts.md"

HEADER = (
    "# Сгенерировано devtools/import_dragon.py из слота saves/drunk_dragon/slots/manual-import.\n"
    "# `# draft` -- поле заполнил ИИ (решение 4а), на утверждение проектировщику; список --\n"
    "# docs/decisions/stage3-p7-drafts.md.\n"
)

WORLD_MD = """\
Мир «Пьяного Дракона» -- тёмное героическое фэнтези на стыке болот и гор: расследование заговора, культ, чума, редкие тёплые моменты. Осень, год 1.

Город над Топями (Нижний, Верхний и Старый город, Ратуша и штаб Городской Стражи, водонапорный комплекс) стоит на краю Топкого болота и Чёрных Топей. На севере -- Вересковые Пустоши, предгорья Железного Кряжа и Кузница Пепла, старая гномья крепость в жерле потухшего вулкана над Древним Могильником. Таверна «Пьяный Дракон» -- место, откуда всё началось: здесь живёт Мило с медным амулетом Селунэ.

Орден Разбитого Ключа, он же Братство Бездонного Мора, поклоняется высшему демону Бездны и ищет «Ключи Погребения» -- три кристалла, чтобы вскрыть древние печати и Врата и пробудить Мор-Владыку, запечатанного в Древнем Могильнике. Главный враг сейчас -- Верховный Жрец Назир в Кузнице Пепла.

Против Ордена стоят Городская Стража (Капитан) и тайная Ложа Северного Ветра -- егеря с тайными тропами и оружием из звёздного железа. Боги: Селунэ (Лунная Дева) и Латандр (Светлый Бог, рассвет) дают знамения и благословения; Шар -- враг Селунэ.
"""

TRUTHS_MD = """\
- Крона -- золотая монета; 1 крона = 100 мм.
- День 1 кампании -- 0001-10-01 (Листопад, осень).
- Все три Кристалла (красный/алый, зелёный, синий) уничтожены.
- Ольбрехт мёртв (убит Греем в Ратуше); Верховный Иерарх, Второй и Третий Иерархи мертвы; Варен жив и сидит в казематах Ратуши.
- Орден Разбитого Ключа, Братство и Братство Бездонного Мора -- одна фракция.
- Мило -- мальчишка-подросток, называет Грея «дядя Грей».
- Брон -- кузнец в Чернолесье; Бран Седогрив -- мастер Ложи Северного Ветра в Городе. Это разные люди.
- Эдрину 23 года.
- Ритуал Назира начнётся на рассвете дня 6; Эдрин -- добровольный проводник и в бою не участвует.
"""


# мотив героя -- решение проектировщика (stage3-p7-review.md, Q2); в источнике был другой
GREY_MOTIVE = "Поддерживать баланс мира: как охотник жить в гармонии с природой и беречь жизнь в любом её виде"

# локации, добавленные по решению проектировщика (Q3): на них ссылаются регионы событий и фракций
EXTRA_LOCATIONS = [
    {
        "id": "iron_ridge_foothills_villages", "name": "Предгорья Кряжа", "parent_id": "iron_ridge",
        "description": "Деревни предгорий Железного Кряжа: сюда идут набеги орков за жертвами; заслон Капитана Стражи держит сигнальные костры.",
        "tags": ["деревня", "предгорья"], "connections": [], "visited": False,
    },
    {
        "id": "grey_quarter", "name": "Серый Квартал", "parent_id": "city",
        "description": "Квартал торговой гильдии в Городе; здесь жили Советник Варен и Казначей Ольбрехт.",
        "tags": ["квартал", "гильдия"], "connections": [], "visited": True,
    },
]


# теги существ Мора: по ним серебряные стрелы и Клинок Северного Ветра бьют сильнее
NPC_TAGS = {"bloodfang": ["mor"], "mor_lord": ["mor"], "plague_brute": ["mor"]}


class PackDumper(yaml.SafeDumper):
    pass


def represent_str(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


PackDumper.add_representer(str, represent_str)


def dump(value) -> str:
    return yaml.dump(
        value, Dumper=PackDumper, allow_unicode=True, sort_keys=False, width=10**6,
        default_flow_style=False,
    )


def entity_text(fields, draft_keys) -> str:
    # одна запись списка; у полей из draft_keys первая строка получает `# draft`
    lines = []
    for key, value in fields.items():
        block = dump({key: value}).rstrip("\n").split("\n")
        if key in draft_keys:
            block[0] += "  # draft"
        lines += block
    lines[0] = "- " + lines[0]
    return "\n".join(lines[:1] + ["  " + line for line in lines[1:]]) + "\n"


def write_list(path, entities) -> None:
    # entities: [(поля, множество ключей-черновиков)], порядок -- по id
    entities = sorted(entities, key=lambda e: e[0]["id"])
    text = HEADER
    if not entities:
        text += "[]\n"
    for fields, draft_keys in entities:
        text += entity_text(fields, draft_keys)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# поправки проектировщика к месту NPC (импорт поставил их не туда)
NPC_LOCATION_FIXES = {
    # Капитан с заслоном стережёт подступы к предгорным деревням от «жатвы», не идёт с отрядом
    "captain_of_guard": "iron_ridge_foothills_villages",
}

# отряд героя в начале главы II: у подъёма к шахте они идут с героем (id героя в игре -- hero)
NPC_FOLLOWS = {
    "bran_sedogriv": "hero", "jorgen": "hero", "lira": "hero", "edrin": "hero",
}

DRAGON_STYLE_NOTES = (
    "- Двигаемся маленькими кусками: одна сцена или один ход за ответ, детальное прохождение\n"
    "- Игрок часто спрашивает статус, снаряжение, расстояния и время -- отвечать конкретно\n"
    "- Мета-реплики игрок помечает словом «мета-игрово:»; это не игровые действия"
)


def write_yaml(path, value, header="") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + dump(value), encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_drafts() -> dict:
    # (kind, id) -> {field: запись}
    records = yaml.safe_load(DRAFTS_FILE.read_text(encoding="utf-8"))
    drafts = {}
    for record in records:
        drafts.setdefault((record["kind"], record["id"]), {})[record["field"]] = record
    return drafts


def norm(text) -> str:
    return text.casefold().replace("ё", "е").strip()


def strip_parens(text) -> str:
    return re.sub(r"\s*\([^)]*\)", "", text)


def find_location(name, locations):
    # locations: id -> название; точное совпадение, без скобок, потом по началу или концу названия
    key = norm(name)
    for loc_id, loc_name in locations.items():
        if norm(loc_name) == key:
            return loc_id
    key = norm(strip_parens(name))
    for loc_id, loc_name in locations.items():
        if norm(strip_parens(loc_name)) == key:
            return loc_id
    found = [
        loc_id for loc_id, loc_name in locations.items()
        if norm(loc_name).startswith(key + " ") or norm(loc_name).endswith(" " + key)
    ]
    if len(found) == 1:
        return found[0]
    return None


def resolve_regions(names, locations, where, report) -> list[str]:
    # имена регионов -> id локаций; не найдено -- строка в отчёте и регион выкидывается
    ids = []
    for name in names:
        found = find_location(name, locations)
        if found is not None:
            parts = [found]
        else:
            parts = []
            for piece in re.split(r"[/,:;]", name):
                if piece.strip() == "":
                    continue
                part = find_location(piece, locations)
                if part is None:
                    report.append(f"{where}: регион {piece.strip()!r} не найден среди локаций -- выкинут")
                else:
                    parts.append(part)
        for part in parts:
            if part not in ids:
                ids.append(part)
    return ids


def clean_description(text) -> str:
    # в источнике перед оценками расстояний стоит обрывок «Пути (из кампании, distance_m -- оценка):»
    return re.sub(r"\s*Пути \(из кампании, distance_m — оценка\): ", ". Расстояния (оценка): ", text)


def pick_draft(drafts, kind, entity_id, field, current):
    # запись черновика, если поле пусто в источнике; иначе None
    record = drafts.get((kind, entity_id), {}).get(field)
    if record is None or current:
        return None
    return record


def npc_entity(npc, drafts, report):
    fields = {"id": npc["id"], "name": npc["name"], "named": npc["named"]}
    draft_keys = set()
    key = npc["key"]
    record = drafts.get(("npc", npc["id"]), {}).get("key")
    if record is not None and key and npc["status"] == "dead":
        key = record["value"]
        draft_keys.add("key")
    fields["key"] = key
    if npc["status"] != "alive":
        fields["status"] = npc["status"]
    if npc["death"] is not None:
        fields["death"] = npc["death"]
    motive = npc["motive"]
    record = pick_draft(drafts, "npc", npc["id"], "motive", motive)
    if record is not None:
        motive = record["value"]
        draft_keys.add("motive")
    fields["motive"] = motive
    fields["means"] = npc["means"]
    record = pick_draft(drafts, "npc", npc["id"], "opportunity", npc["opportunity"])
    if record is not None:
        fields["opportunity"] = record["value"]
        draft_keys.add("opportunity")
    elif npc["opportunity"]:
        report.append(f"npcs.{npc['id']}: opportunity источника не перенесён")
    if npc["attitude"] != 0:
        fields["attitude"] = npc["attitude"]
    if npc["known_to_player"]:
        fields["known_to_player"] = npc["known_to_player"]
    if npc["secrets"]:
        fields["secrets"] = [secret_entity(s, npc["id"], report) for s in npc["secrets"]]
    location_id = NPC_LOCATION_FIXES.get(npc["id"], npc["location_id"])
    if location_id is not None:
        fields["location_id"] = location_id
    if npc["id"] in NPC_FOLLOWS:
        fields["follows"] = NPC_FOLLOWS[npc["id"]]
    if npc["species_id"] is not None:
        fields["species_id"] = npc["species_id"]
    if npc["favor"]:
        fields["favor"] = npc["favor"]
    if npc["relations_text"]:
        fields["relations_text"] = npc["relations_text"]
    if npc["combat"] is not None or npc["creature"] is not None:
        report.append(f"npcs.{npc['id']}: combat/creature источника не перенесены")
    if npc["id"] in NPC_TAGS:
        fields["tags"] = NPC_TAGS[npc["id"]]
    fields["origin"] = "pack"
    return fields, draft_keys


def secret_entity(secret, npc_id, report):
    out = {"id": secret["id"], "text": secret["text"]}
    reveal = secret["reveal_if"]
    if reveal["type"] == "narrative":
        out["reveal_if"] = {"narrative": reveal["text"]}
    else:
        report.append(f"npcs.{npc_id}.secrets.{secret['id']}: условие не нарративное, перенесено как есть")
        out["reveal_if"] = reveal
    if secret["revealed"]:
        out["revealed"] = True
    return out


def faction_entity(faction, drafts, locations, report):
    fields = {"id": faction["id"], "name": faction["name"], "motive": faction["motive"]}
    draft_keys = set()
    if faction["means"]:
        fields["means"] = faction["means"]
    record = pick_draft(drafts, "faction", faction["id"], "opportunity", faction["opportunity"])
    if record is not None:
        fields["opportunity"] = record["value"]
        draft_keys.add("opportunity")
    if faction["members"]:
        fields["members"] = faction["members"]
    regions = resolve_regions(
        faction["regions"], locations, f"factions.{faction['id']}.regions", report
    )
    if regions:
        fields["regions"] = regions
    return fields, draft_keys


def god_entity(god, drafts):
    fields = {"id": god["id"], "name": god["name"]}
    draft_keys = set()
    if god["domains"]:
        fields["domains"] = god["domains"]
    if god["role"]:
        fields["role"] = god["role"]
    for field in ("motive", "pleased_by", "angered_by", "rivals"):
        value = god[field]
        record = pick_draft(drafts, "god", god["id"], field, value)
        if record is not None:
            value = record["value"]
            draft_keys.add(field)
        if value:
            fields[field] = value
    if god["means"]:
        fields["means"] = god["means"]
    record = pick_draft(drafts, "god", god["id"], "opportunity", god["opportunity"])
    if record is not None:
        fields["opportunity"] = record["value"]
        draft_keys.add("opportunity")
    record = pick_draft(drafts, "god", god["id"], "season_power", {})
    if record is not None:
        fields["season_power"] = record["value"]
        draft_keys.add("season_power")
    fields["origin"] = "pack"
    return fields, draft_keys


def location_entity(location):
    fields = {"id": location["id"], "name": location["name"]}
    if location["parent_id"] is not None:
        fields["parent_id"] = location["parent_id"]
    fields["description"] = clean_description(location["description"])
    if location["tags"]:
        fields["tags"] = location["tags"]
    if location["connections"]:
        fields["connections"] = [
            {"to": c["to"], "distance_m": c["distance_m"]} for c in location["connections"]
        ]
    fields["visited"] = location["visited"]
    fields["origin"] = "pack"
    return fields, set()


def event_entity(event, locations, report):
    fields = {"id": event["id"], "type": event["type"]}
    fields["regions"] = resolve_regions(
        event["regions"], locations, f"events.{event['id']}.regions", report
    )
    if event["affects"]:
        fields["affects"] = event["affects"]
    if event["mortality_multiplier"] != 1:
        fields["mortality_multiplier"] = event["mortality_multiplier"]
    if event["hazard"] is not None:
        fields["hazard"] = event["hazard"]
    if event["started_s"] is not None:
        fields["started_s"] = event["started_s"]
    if event["ends_at_s"] is not None:
        fields["ends_at_s"] = event["ends_at_s"]
    ends_when = event["ends_when"]
    if ends_when is not None:
        if ends_when["type"] == "narrative":
            ends_when = {"narrative": ends_when["text"]}
        fields["ends_when"] = ends_when
    fields["cause"] = event["cause"]
    fields["kind"] = "caused"
    return fields, set()


def one_line(value) -> str:
    # вложенный словарь источника -> «ключ: значение; ключ: значение»
    if isinstance(value, dict):
        return "; ".join(f"{k}: {one_line(v)}" for k, v in value.items())
    if isinstance(value, list):
        return ", ".join(one_line(v) for v in value)
    return str(value)


META_SENTENCE = re.compile(r"[^.]*мета-вопрос[^.]*\.\s*")
STEP_NOTE = re.compile(r"\s*\(?по шагу \d+\)?(\s*\(механика\))?")


def clean_meta(text) -> str:
    # служебные следы старой сессии (подсказки по шагам, мета-вопросы про подписку) -- не сюжет
    return STEP_NOTE.sub("", META_SENTENCE.sub("", text))


def scene_summary(session, recent_turns) -> str:
    # стрелка «→» зарезервирована под строки ходов, в остальном тексте она заменяется на «->»
    def arrow(text) -> str:
        return clean_meta(text).replace("→", "->")

    scene = session["current_scene"]
    decision = session["pending_decision"]
    parts = []
    parts.append("Ситуация. " + scene["title"] + ". " + scene["situation"])
    parts.append("Отряд:\n" + "\n".join(f"- {k}: {one_line(v)}" for k, v in scene["party"].items()))
    parts.append(
        "Известно о враге:\n"
        + "\n".join(
            f"- {k}: {one_line(v)}"
            for k, v in scene["enemies_known"].items()
            if not k.startswith("dm_hint")
        )
    )
    parts.append(
        "Сроки:\n" + "\n".join(f"- {d['what']}: {d['when']}" for d in scene["deadlines"])
    )
    text = arrow("\n\n".join(parts))
    turns = [
        f"{i}. {arrow(t['player'])} → {arrow(t['dm_short'])}" for i, t in enumerate(recent_turns, 1)
    ]
    text += "\n\nПоследние ходы (кратко: реплика игрока, затем ответ мастера):\n" + "\n".join(turns)
    choice = decision["player_choice"]
    extra = [m for m in decision["unanswered_player_messages"] if m != choice]
    tail = f"Игрок выбрал «{choice}»"
    for message in extra:
        tail += f" и следом спросил «{message}»"
    tail += " -- мастер ещё не ответил."
    text += "\n\nНезакрытый выбор. Варианты мастера:\n" + arrow("\n".join(decision["options"]))
    text += "\n" + arrow(tail)
    return text


def clock_start(clock_data, report):
    clock = GameClock.model_validate(clock_data)
    if clock.calendar != default_calendar():
        report.append("календарь источника не стандартный: в паке нужен calendar, проверьте вручную")
    rest = clock.now_s % DAY
    return clock.to_date(), f"{rest // 3600:02d}:{rest % 3600 // 60:02d}"


def chapter_id(source_id) -> str:
    return re.sub(r"^ch(\d+)$", r"ch_\1", source_id)


def hero_preset(hero, location_id, report, drafts) -> dict:
    sheet = hero["sheet"]
    background = sheet["background"]
    first, second = background["abilities"][0], background["abilities"][1]
    bonus = {first: 2, second: 1}
    scores = {a: v - bonus.get(a, 0) for a, v in sheet["abilities"].items()}
    if sorted(scores.values()) != [8, 10, 12, 13, 14, 15]:
        report.append(f"герой {hero['id']}: характеристики не складываются в стандартный набор")
    skills = sheet["skill_proficiencies"]
    equipped = hero["equipped"]
    equip = [equipped[slot] for slot in ("armor", "shield", "main_hand", "off_hand") if equipped[slot]]
    choices = {
        "name": hero["name"],
        "species_id": sheet["species_id"],
        "class_id": sheet["class_id"],
        "background": background,
        "ability_method": "standard_array",
        "ability_scores": scores,
        "background_bonus": bonus,
        "class_skills": skills[len(background["skills"]):-1],
        "weapon_masteries": sheet["weapon_masteries"],
        "inventory": equip,
        "equip": list(equip),
        "species_choices": {"skill": skills[-1], "feat": sheet["feats"][-1]},
    }
    extra = [e for e in hero["inventory"] if e["item_id"] not in equip]
    preset = {"id": hero["id"], "choices": choices}
    preset["inventory_extra"] = [{"item_id": e["item_id"], "qty": e["qty"]} for e in extra]
    preset["equipped"] = {slot: item for slot, item in equipped.items() if item}
    preset["money_cp"] = hero["money_cp"]
    preset["motive"] = GREY_MOTIVE
    preset["location_id"] = location_id
    preset["level"] = sheet["level"]
    preset["xp"] = sheet["xp"]
    # решения проектировщика по герою: уровень, опыт, выборы уровней, спутник
    for field in ("level", "xp", "level_choices", "companion"):
        record = drafts.get(("hero", hero["id"]), {}).get(field)
        if record is not None:
            preset[field] = record["value"]
    if hero["means"]:
        report.append(f"герой {hero['id']}: means не перенесены (в HeroPreset нет поля)")
    if hero["scars"]:
        report.append(f"герой {hero['id']}: scars не перенесены")
    return preset


def scene_chapter_id(scene) -> str:
    return chapter_id(scene["chapter"])


def start_memory(memory) -> dict:
    scenes = []
    for number, scene in enumerate(memory["scenes"], 1):
        scenes.append({
            "id": f"sc_{number}",
            "chapter_id": scene_chapter_id(scene),
            "title": scene["title"],
            "summary": scene["summary"],
        })
    chapters = []
    for number, chapter in enumerate(memory["chapters"], 1):
        chapters.append({
            "id": chapter_id(chapter["id"]),
            "number": number,
            "title": chapter["title"],
            "summary": chapter["summary"],
        })
    return {"game_summary": memory["game_summary"], "chapters": chapters, "scenes": scenes}


def start_chronicle(chronicle) -> dict:
    entries = []
    for entry in chronicle["entries"]:
        entries.append({"at_s": (entry["day"] - 1) * DAY, "kind": "imported", "text": entry["text"]})
    return {"entries": entries}


def copy_content(src, out) -> None:
    for path in sorted(src.rglob("*")):
        if path.is_file():
            target = out / path.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)


def convert(slot_dir, out_dir) -> list[str]:
    # сырой слот -> пак; возвращает строки отчёта о том, что не распознано или не перенесено
    slot = Path(slot_dir)
    out = Path(out_dir)
    report = []
    world = read_json(slot / "world" / "world.json")
    memory = read_json(slot / "world" / "memory.json")
    chronicle = read_json(slot / "world" / "chronicle.json")
    session = read_json(slot / "session.json")
    hero = read_json(sorted(slot.glob("heroes/*/hero.json"))[0])
    drafts = load_drafts()

    for extra in EXTRA_LOCATIONS:
        world["locations"][extra["id"]] = extra
    locations = {loc["id"]: loc["name"] for loc in world["locations"].values()}
    npcs = [npc_entity(n, drafts, report) for n in world["npcs"].values()]
    factions = [faction_entity(f, drafts, locations, report) for f in world["factions"].values()]
    gods = [god_entity(g, drafts) for g in world["pantheon"].values()]
    places = [location_entity(loc) for loc in world["locations"].values()]
    events = [event_entity(e, locations, report) for e in world["events"]]
    write_list(out / "npcs.yaml", npcs)
    write_list(out / "factions.yaml", factions)
    write_list(out / "pantheon.yaml", gods)
    write_list(out / "locations.yaml", places)
    write_list(out / "events.yaml", events)

    date, time = clock_start(world["clock"], report)
    tone = world["tone"]
    campaign = {
        "id": world["campaign_id"],
        "name": "Пьяный Дракон",
        "version": "1",
        "start": {
            "date": date,
            "time": time,
            "hero_location": session["current_scene"]["location_id"],
            "heroes": [hero["id"]],
            "chapter": {
                "number": 2,
                "title": session["current_chapter"]["title"],
            },
            "scene_summary": scene_summary(session, memory["recent_turns"]),
        },
        # шкалы тона утверждены проектировщиком (3а, G6); mood -- из источника; notes -- только
        # стиль текста: оформление вывода (рамки, колонки, броски, варианты) рисует игра, не модель
        "tone": {
            "mood": tone["mood"],
            "violence": "жестоко",
            "horror": "умеренно",
            "romance": "есть",
            "language": "сдержанно",
            "hard_limits": [],
            "soft_limits": [],
            "notes": DRAGON_STYLE_NOTES,
        },
        "flags": world["flags"],
    }
    write_yaml(out / "campaign.yaml", campaign)
    (out / "world.md").write_text(WORLD_MD, encoding="utf-8")
    (out / "truths.md").write_text(TRUTHS_MD, encoding="utf-8")
    write_yaml(out / "heroes" / f"{hero['id']}.yaml", hero_preset(hero, hero["location_id"], report, drafts))
    write_yaml(out / "start" / "memory.yaml", start_memory(memory))
    write_yaml(out / "start" / "chronicle.yaml", start_chronicle(chronicle))
    if (slot.parents[1] / "content").is_dir():
        copy_content(slot.parents[1] / "content", out / "content")
    else:
        report.append("нет каталога content рядом со слотом -- предметы не скопированы")

    count = sum(len(keys) for _, keys in npcs + factions + gods)
    report.append(f"draft-полей в паке: {count}")
    return report


def drafts_markdown() -> str:
    # лист на утверждение проектировщику: по сущности -- что предложено, почему, где в источнике
    records = yaml.safe_load(DRAFTS_FILE.read_text(encoding="utf-8"))
    titles = {"npc": "NPC", "faction": "Фракции", "god": "Боги", "hero": "Герои (решения проектировщика)"}
    lines = [
        "# П7: черновики ИИ для пака «Пьяный Дракон» (на утверждение проектировщику)",
        "",
        "Решение 4а (grooming): мотивы, триггеры, opportunity NPC и фракций, pleased_by/angered_by/rivals",
        "богов -- черновик ИИ, проектировщик правит. В паке `campaigns/drunk_dragon/` каждое такое поле",
        "помечено комментарием `# draft`. Файл собран из `devtools/dragon_drafts.yaml` (тот же источник,",
        "что у конвертера `devtools/import_dragon.py`). Правка -- в YAML пака руками (и в",
        "`dragon_drafts.yaml`, если конвертер будет запускаться снова).",
        "",
        f"Всего черновых полей: {len([r for r in records if r['kind'] != 'hero'])}.",
        "",
        "Не draft (утверждено): шкалы тона (3а, G6) и всё, что перенесено из источника как есть.",
        "Не заполнено намеренно: `servants` богов (слуг-охотников в источнике нет), `means` богов,",
        "новые `key: true` (10 ключевых NPC источника остаются как есть, решение Q1).",
        "Ссылки на источник: `ch1` = `saves/drunk_dragon/_import/source/chapter1_gemini_web.txt`,",
        "`ch2` = `chapter2_agy.txt` (число после двоеточия -- номер строки); `world.json`, `session.json` --",
        "`saves/drunk_dragon/slots/manual-import/`.",
        "",
    ]
    for kind in ("npc", "faction", "god", "hero"):
        lines += [f"## {titles[kind]}", ""]
        entity_ids = []
        for record in records:
            if record["kind"] == kind and record["id"] not in entity_ids:
                entity_ids.append(record["id"])
        for entity_id in entity_ids:
            lines += [f"### {entity_id}", ""]
            for record in records:
                if record["kind"] != kind or record["id"] != entity_id:
                    continue
                lines.append(f"- **{record['field']}**")
                lines.append("  ```yaml")
                for line in dump({record["field"]: record["value"]}).rstrip("\n").split("\n"):
                    lines.append("  " + line)
                lines.append("  ```")
                lines.append(f"  Почему: {record['why']}")
                lines.append(f"  Источник: {record['source']}")
            lines.append("")
    lines += [
        "## Отчёт конвертера (не draft, правит проектировщик)",
        "",
        "- Локации «Предгорья Кряжа» и «Серый Квартал» добавлены конвертером (решение Q3); на них",
        "  ссылаются регионы `harvest_raids` и `city_council_conspiracy`.",
        "- Мотив Грея взят из решения проектировщика (Q2), а не из `hero.json`; средства героя не перенесены.",
        "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="import_dragon")
    parser.add_argument("--slot", default=str(DEFAULT_SLOT))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--drafts-doc", default=str(DEFAULT_DRAFTS_DOC))
    args = parser.parse_args(argv)
    for line in convert(args.slot, args.out):
        print(line)
    doc = Path(args.drafts_doc)
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(drafts_markdown(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
