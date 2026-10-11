# Общие помощники тестов import пака (Б3, B3-PLAN, раздел B). Не фикстуры, а функции.
#   pack_input(**changes)       -- канонический валидный ввод инструмента pack (словарь, все поля
#                                  как у strict-схемы): 2 локации square/inn со связями, NPC mara
#                                  (именованная, триггер flag, секрет narrative) и guard, фракция
#                                  watch, бог selune со слугой mara, тон grim-подобный,
#                                  start.hero_location = inn, scene_summary;
#   pack_call(call_id, **ch)    -- то же вызовом инструмента для ScriptedAdapter;
#   bad_pack_call(call_id)      -- вызов с двумя ошибками загрузчика: битая hero_location и
#                                  член фракции-призрак (обе строки load_pack);
#   conflict_pack_call(call_id) -- пак грузится, но конфликт 5.3 (два именованных NPC с одним
#                                  именем); load_pack проверяет ссылки раньше 5.3, поэтому
#                                  обе ошибки одним вызовом дать нельзя;
#   import_task(id)             -- ImportTask по id пака;
#   import_deps(adapter, registry, cfg, folder) -- HeroCreateDeps с Journal(folder, ".import");
#   staged(tmp_path)            -- (каталог campaigns, staging-каталог в нём);
#   pack_files(**changes)       -- словарь файлов пака, как их даёт конвертер протокола;
#   written_pack(tmp_path, **ch) -- staging с записанными файлами пака;
#   summary_text()              -- выжимка из нескольких абзацев.
import sys
from pathlib import Path

TESTS_UNIT = Path(__file__).resolve().parents[1]
for sub in ("master", "protocol", "llm", "rules", "game"):
    if str(TESTS_UNIT / sub) not in sys.path:
        sys.path.insert(0, str(TESTS_UNIT / sub))

from hero_kit import NOW, deps  # noqa: E402, F401
from master_kit import app_cfg  # noqa: E402

from ai_dm.llm.journal import Journal  # noqa: E402

PACK_ID = "mini_import"
STAGE_NAME = f".import-{PACK_ID}-abc123"


def trigger_input(**changes):
    data = {
        "id": "leave", "then": "уходит из города", "kind": "flag", "ref": "debt_paid",
        "status": "", "gte": 0,
    }
    data.update(changes)
    return data


def secret_input(**changes):
    data = {
        "id": "debt", "text": "Мара должна гильдии.", "kind": "narrative",
        "ref": "герой завоевал её доверие", "status": "", "gte": 0,
    }
    data.update(changes)
    return data


def location_input(**changes):
    data = {
        "id": "square", "name": "Площадь", "parent_id": "", "description": "Шумная площадь.",
        "connections": [{"to": "inn", "distance_m": 50}],
    }
    data.update(changes)
    return data


def npc_input(**changes):
    data = {
        "id": "mara", "name": "Мара", "means": ["знает все слухи"], "named": True, "key": True,
        "motive": "Хочет выкупить долг.", "location_id": "inn", "trade_kind": "none",
        "species_id": "human", "opportunity": [trigger_input()], "secrets": [secret_input()],
    }
    data.update(changes)
    return data


def guard_input(**changes):
    data = {
        "id": "guard", "name": "Стражник", "means": ["копьё"], "named": False, "key": False,
        "motive": "", "location_id": "square", "trade_kind": "none", "species_id": "",
        "opportunity": [], "secrets": [],
    }
    data.update(changes)
    return data


def faction_input(**changes):
    data = {
        "id": "watch", "name": "Стража", "motive": "Порядок в городе.", "means": ["патрули"],
        "members": ["guard"], "regions": ["square"], "opportunity": [],
    }
    data.update(changes)
    return data


def god_input(**changes):
    data = {
        "id": "selune", "name": "Селунэ", "domains": ["луна"], "role": "богиня ночи",
        "motive": "", "pleased_by": ["милосердие"], "angered_by": [], "rivals": [],
        "means": ["знамения"], "realm": "", "servants": ["mara"], "opportunity": [],
    }
    data.update(changes)
    return data


def tone_input(**changes):
    data = {
        "mood": "мрачное фэнтези", "violence": "жестоко", "horror": "умеренно",
        "romance": "намёки", "language": "грубо", "hard_limits": [], "soft_limits": [],
        "notes": "Мир суров.",
    }
    data.update(changes)
    return data


def start_input(**changes):
    data = {
        "date": "0100-03-01", "time": "08:00", "hero_location": "inn", "chapter_number": 1,
        "chapter_title": "", "scene_summary": "В трактире шумно, Мара считает монеты.",
    }
    data.update(changes)
    return data


def pack_input(**changes):
    data = {
        "type": "pack", "name": "Мини-импорт", "start": start_input(), "tone": tone_input(),
        "world_text": "Город у реки: площадь и трактир.", "truths": "Река не замерзает.",
        "locations": [
            location_input(),
            location_input(
                id="inn", name="Трактир", parent_id="square", description="",
                connections=[{"to": "square", "distance_m": 50}],
            ),
        ],
        "npcs": [npc_input(), guard_input()],
        "factions": [faction_input()],
        "pantheon": [god_input()],
    }
    data.update(changes)
    return data


def pack_call(call_id="pack-1", **changes):
    return {"id": call_id, "name": "pack", "input": pack_input(**changes)}


def bad_pack_call(call_id="pack-bad"):
    # две ошибки загрузчика разом: hero_location не из своих локаций и член фракции-призрак
    return pack_call(
        call_id, start=start_input(hero_location="nowhere"),
        factions=[faction_input(members=["ghost"])],
    )


def conflict_pack_call(call_id="pack-conflict"):
    # пак грузится, но ломает 5.3: два именованных NPC с одним именем
    twin = npc_input(id="mara2", opportunity=[], secrets=[])
    return pack_call(call_id, npcs=[npc_input(), twin, guard_input()])


def import_task(campaign_id=PACK_ID):
    from ai_dm.protocol.context import ImportTask

    return ImportTask(campaign_id)


def import_deps(adapter, registry, cfg, folder, **kw):
    from ai_dm.game.hero_create import HeroCreateDeps

    kw.setdefault("now", lambda: NOW)
    return HeroCreateDeps(
        adapter=adapter, app_cfg=app_cfg(), registry=registry, cfg=cfg,
        journal=Journal(folder, ".import", app_cfg().journal), **kw,
    )


def staged(tmp_path):
    campaigns = tmp_path / "campaigns"
    folder = campaigns / STAGE_NAME
    folder.mkdir(parents=True)
    return campaigns, folder


def pack_files(campaign_id=PACK_ID, **changes):
    from ai_dm.protocol.handlers.pack import files_from_request
    from ai_dm.protocol.requests import parse_request

    return files_from_request(parse_request(pack_input(**changes), "pack_import"), campaign_id)


def written_pack(tmp_path, **changes):
    from ai_dm.campaign.importer import write_pack_files

    _, folder = staged(tmp_path)
    write_pack_files(folder, pack_files(**changes))
    return folder


def summary_text():
    return (
        "Город у реки. На площади стоит стража, рядом трактир.\n\n"
        "Хозяйка трактира Мара знает все слухи, но должна денег гильдии.\n\n"
        "Селунэ почитают ночью; Мара ей служит."
    )
