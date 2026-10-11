# Ожидаемый API: ai_dm.persistence.migrations.m0003_v2_to_v3 (этап 3, партия 1; STAGE3-PLAN A3)
#   migrate_v2_to_v3(data: dict) -> dict  -- чистое dict -> dict, вход не мутирует; schema_version
#       ставит фреймворк migrate(); MIGRATIONS[2] is migrate_v2_to_v3; CURRENT_SCHEMA_VERSION == 3.
#       Миграция заморожена в v3: не импортирует модели ai_dm.state.* (литералы заморожены).
#   Правила (STAGE3-PLAN A3):
#     session.current_chapter: dict формы ChapterState {id, number, title, started_at_s,
#         scene_count, closed_reason} -> остаётся; иначе (например {"id": "c1"}) -> None
#     session.boundary_pending = False; остальные ключи session не трогаются
#     world.tone: значение шкалы (violence/horror/romance/language) вне списка ТЗ 3 -> "";
#         "русский" в language -> ""; исходный текст непустых шкал попадает в tone.notes;
#         mood сохраняется
#     memory.scenes / memory.chapters: элементы с "summary" остаются (id = sc_<i> / ch_<i>, если
#         id нет), остальные выкидываются
#     chronicle.entries: {at_s | day, text} -> kind "imported"; day -> at_s = (day - 1) * 86400
#     world.lore.world_text = settings["world_text"], если был, иначе пусто
#     world.events[*].regions не трогаются; все новые поля v3 -- по умолчанию (валидный бандл)
#   Фикстура tests/fixtures/saves/v2/ -- сейв Вейла этапа 2 (слот auto мира old_world, обезличен;
#   в tone добавлены violence="реалистично" и horror="кровавый" -- вне списка v3).
import ast
import copy
import json
import shutil
from pathlib import Path

from persist_kit import load_slot

from ai_dm.persistence.migrations import (
    CURRENT_SCHEMA_VERSION,
    MIGRATIONS,
    MigrationContext,
    migrate,
)
from ai_dm.persistence.migrations.m0003_v2_to_v3 import migrate_v2_to_v3
from ai_dm.persistence.store import save_slot
from ai_dm.state.save import SaveBundle

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "saves"
FIXTURE_V0 = FIXTURES / "v0"
FIXTURE_V2 = FIXTURES / "v2"
BACKUP_TS = "20260101T000000Z"
SAVED_AT = "2026-01-01T12:00:00Z"
MIGRATION_FILE = (
    Path(__file__).resolve().parents[3]
    / "src" / "ai_dm" / "persistence" / "migrations" / "m0003_v2_to_v3.py"
)

CHAPTER = {
    "id": "ch_1", "number": 1, "title": "Начало", "started_at_s": 0, "scene_count": 2,
    "closed_reason": None,
}


def tree(folder):
    return {
        p.relative_to(folder).as_posix(): p.read_bytes()
        for p in sorted(folder.rglob("*")) if p.is_file()
    }


def install(saves, fixture, slot="auto"):
    target = saves / "old_world" / "slots" / slot
    shutil.copytree(fixture, target)
    return target


def raw_v2(**changes):
    data = {
        "manifest": {
            "schema_version": 2, "engine_version": "0.1.0", "world_id": "old_world",
            "campaign_id": None, "slot": "auto", "saved_at": SAVED_AT,
            "current_hero_id": None, "heroes": [],
        },
        "world": {
            "world_id": "old_world", "flags": {"a": True},
            "rng": {"algo": "pcg32", "seed": 7, "state": 5, "inc": 109, "draws": 0},
            "tone": {"mood": "мрачно", "violence": "", "horror": "", "romance": "",
                     "language": "русский", "hard_limits": [], "soft_limits": []},
            "settings": {},
            "events": [{"id": "plague", "type": "plague", "regions": ["no_such_place"]}],
        },
        "chronicle": {"entries": []},
        "memory": {"scenes": [], "chapters": [], "game_summary": "", "recent_turns": []},
        "heroes": [],
        "session": {"current_scene": None, "current_chapter": None, "active_combat": None,
                    "pending_decision": None, "turn_seq": 3, "offered_choices": ["Да"],
                    "last_combat": None},
    }
    for path, value in changes.items():
        section, key = path.split("__")
        data[section][key] = value
    return data


# реестр

def test_registry_has_step_from_v2():
    assert MIGRATIONS[2] is migrate_v2_to_v3


def test_framework_sets_schema_version_three():
    assert migrate(raw_v2(), current_version=3)["manifest"]["schema_version"] == 3


def test_already_v3_dict_is_not_migrated_again():
    data = raw_v2()
    data["manifest"]["schema_version"] = 3
    assert migrate(data, current_version=3) == data


def test_migrate_v2_to_v3_does_not_mutate_input():
    data = raw_v2(session__current_chapter=CHAPTER)
    data["world"]["tone"]["violence"] = "очень"
    data["memory"]["scenes"] = [{"summary": "x"}, {"t": 1}]
    data["chronicle"]["entries"] = [{"day": 2, "text": "y"}]
    before = copy.deepcopy(data)
    migrate_v2_to_v3(data)
    assert data == before


def test_migration_does_not_import_state_models():
    names = []
    for node in ast.walk(ast.parse(MIGRATION_FILE.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    assert [n for n in names if n.startswith("ai_dm.state") or n == "ai_dm"] == []


# session

def test_free_form_chapter_becomes_none():
    result = migrate_v2_to_v3(raw_v2(session__current_chapter={"id": "c1"}))
    assert result["session"]["current_chapter"] is None


def test_missing_chapter_stays_none():
    assert migrate_v2_to_v3(raw_v2())["session"]["current_chapter"] is None


def test_chapter_in_state_form_is_kept():
    result = migrate_v2_to_v3(raw_v2(session__current_chapter=CHAPTER))
    assert result["session"]["current_chapter"] == CHAPTER


def test_boundary_pending_is_false_and_other_session_keys_stay():
    session = migrate_v2_to_v3(raw_v2())["session"]
    assert session["boundary_pending"] is False
    assert session["turn_seq"] == 3
    assert session["offered_choices"] == ["Да"]


# tone

def test_language_russian_becomes_empty_and_goes_to_notes():
    tone = migrate_v2_to_v3(raw_v2())["world"]["tone"]
    assert tone["language"] == ""
    assert "русский" in tone["notes"]
    assert tone["mood"] == "мрачно"


def test_known_scale_value_is_kept():
    data = raw_v2()
    data["world"]["tone"]["violence"] = "реалистично"
    tone = migrate_v2_to_v3(data)["world"]["tone"]
    assert tone["violence"] == "реалистично"
    assert "реалистично" in tone["notes"]


def test_unknown_scale_value_becomes_empty_but_text_is_in_notes():
    data = raw_v2()
    data["world"]["tone"]["horror"] = "кровавый"
    tone = migrate_v2_to_v3(data)["world"]["tone"]
    assert tone["horror"] == ""
    assert "кровавый" in tone["notes"]


def test_limits_stay_in_tone():
    data = raw_v2()
    data["world"]["tone"]["hard_limits"] = ["насилие над детьми"]
    data["world"]["tone"]["soft_limits"] = ["пытки"]
    tone = migrate_v2_to_v3(data)["world"]["tone"]
    assert tone["hard_limits"] == ["насилие над детьми"]
    assert tone["soft_limits"] == ["пытки"]


def test_tone_notes_are_appended_to_existing_notes():
    data = raw_v2()
    data["world"]["tone"]["notes"] = "старый стиль"
    notes = migrate_v2_to_v3(data)["world"]["tone"]["notes"]
    assert "старый стиль" in notes
    assert "русский" in notes


# memory и хроника

def test_scenes_with_summary_are_kept_and_get_ids():
    data = raw_v2(memory__scenes=[{"summary": "Гоблины убиты"}, {"t": 1}])
    scenes = migrate_v2_to_v3(data)["memory"]["scenes"]
    assert len(scenes) == 1
    assert scenes[0]["summary"] == "Гоблины убиты"
    assert scenes[0]["id"].startswith("sc_")


def test_scene_with_own_id_keeps_it():
    data = raw_v2(memory__scenes=[{"id": "scene_9", "summary": "Тихо"}])
    assert migrate_v2_to_v3(data)["memory"]["scenes"][0]["id"] == "scene_9"


def test_chapters_with_summary_are_kept_and_get_ids():
    data = raw_v2(memory__chapters=[{"summary": "Глава о гусе"}, {"title": "без выжимки"}])
    chapters = migrate_v2_to_v3(data)["memory"]["chapters"]
    assert len(chapters) == 1
    assert chapters[0]["id"].startswith("ch_")


def test_chronicle_entry_with_at_s_becomes_imported():
    data = raw_v2(chronicle__entries=[{"at_s": 500, "text": "Пришли в Вейл"}])
    entry = migrate_v2_to_v3(data)["chronicle"]["entries"][0]
    assert entry["kind"] == "imported"
    assert entry["at_s"] == 500
    assert entry["text"] == "Пришли в Вейл"


def test_chronicle_entry_with_day_gets_at_s():
    data = raw_v2(chronicle__entries=[{"day": 3, "text": "Третий день"}])
    entry = migrate_v2_to_v3(data)["chronicle"]["entries"][0]
    assert entry["at_s"] == 2 * 86400
    assert entry["kind"] == "imported"


# мир

def test_lore_takes_world_text_from_settings():
    data = raw_v2(world__settings={"world_text": "Вейл — деревня."})
    assert migrate_v2_to_v3(data)["world"]["lore"]["world_text"] == "Вейл — деревня."


def test_lore_is_empty_without_world_text():
    assert migrate_v2_to_v3(raw_v2())["world"]["lore"]["world_text"] == ""


def test_event_regions_with_unknown_ids_are_not_touched():
    result = migrate_v2_to_v3(raw_v2())
    assert result["world"]["events"][0]["regions"] == ["no_such_place"]


def test_migrated_dict_validates_as_current_bundle():
    data = raw_v2(session__current_chapter={"id": "c1"},
                  memory__scenes=[{"summary": "Гоблины убиты"}],
                  chronicle__entries=[{"day": 3, "text": "Третий день"}])
    bundle = SaveBundle.model_validate(migrate(data, context=MigrationContext(item_cost={})))
    assert bundle.session.current_chapter is None
    assert bundle.session.boundary_pending is False
    assert bundle.memory.scenes[0].summary == "Гоблины убиты"
    assert bundle.chronicle.entries[0].kind == "imported"
    assert bundle.world.tone.language == ""


# фикстура v2 на диске

def test_fixture_v2_is_stage2_format():
    manifest = json.loads((FIXTURE_V2 / "manifest.json").read_text(encoding="utf-8"))
    session = json.loads((FIXTURE_V2 / "session.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 2
    assert "boundary_pending" not in session


def test_load_v2_returns_v3_bundle(saves):
    install(saves, FIXTURE_V2)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.manifest.schema_version == CURRENT_SCHEMA_VERSION
    assert bundle.session.current_chapter is None
    assert bundle.session.boundary_pending is False
    assert bundle.session.current_scene.id == "scene_2"
    assert bundle.session.turn_seq == 17


def test_load_v2_tone_language_is_empty_and_text_in_notes(saves):
    install(saves, FIXTURE_V2)
    tone = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS).world.tone
    assert tone.language == ""
    assert tone.violence == "реалистично"
    assert tone.horror == ""
    assert "русский" in tone.notes
    assert "кровавый" in tone.notes
    assert tone.mood == "приключенческое фэнтези"


def test_load_v2_keeps_world_and_hero(saves):
    install(saves, FIXTURE_V2)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert "grakh" in bundle.world.npcs
    assert bundle.world.flags["visited:cellar"] is True
    assert [h.id for h in bundle.heroes] == ["hero"]
    assert len(bundle.memory.recent_turns) > 0


def test_load_v2_new_sections_are_empty_not_none(saves):
    install(saves, FIXTURE_V2)
    world = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS).world
    assert world.dangers == []
    assert world.notices == []
    assert world.fired == []


def test_load_v2_makes_byte_exact_backup(saves):
    install(saves, FIXTURE_V2)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    backup = saves / "old_world" / "backups" / f"auto-v2-{BACKUP_TS}"
    assert tree(backup) == tree(FIXTURE_V2)


def test_load_v2_rewrites_slot_as_v3(saves):
    folder = install(saves, FIXTURE_V2)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    session = json.loads((folder / "session.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == CURRENT_SCHEMA_VERSION
    assert session["current_chapter"] is None
    assert session["boundary_pending"] is False


def test_load_v2_twice_makes_no_second_backup_and_same_bundle(saves):
    install(saves, FIXTURE_V2)
    first = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    second = load_slot(saves, "old_world", "auto", backup_ts="20260202T000000Z")
    assert second == first
    assert len(list((saves / "old_world" / "backups").iterdir())) == 1


def test_load_v2_does_not_touch_fixture_itself(saves):
    before = tree(FIXTURE_V2)
    install(saves, FIXTURE_V2)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert tree(FIXTURE_V2) == before


def test_resave_of_migrated_v2_is_byte_stable(saves):
    install(saves, FIXTURE_V2)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    save_slot(saves, bundle, "manual-a", saved_at=SAVED_AT)
    first = tree(saves / "old_world" / "slots" / "manual-a")
    again = load_slot(saves, "old_world", "manual-a", backup_ts=BACKUP_TS)
    save_slot(saves, again, "manual-a", saved_at=SAVED_AT)
    assert tree(saves / "old_world" / "slots" / "manual-a") == first


# цепочка v0 -> v3

def test_load_v0_chain_reaches_v3_with_single_backup(saves):
    install(saves, FIXTURE_V0)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.manifest.schema_version == CURRENT_SCHEMA_VERSION
    assert bundle.session.current_chapter is None
    assert bundle.session.boundary_pending is False
    assert bundle.heroes[0].name == "Старый Арн"
    backups = sorted((saves / "old_world" / "backups").iterdir())
    assert [b.name for b in backups] == [f"auto-v0-{BACKUP_TS}"]
    assert tree(backups[0]) == tree(FIXTURE_V0)


def test_v0_dict_chain_reaches_v3():
    data = {
        "manifest": {"engine_version": "0.0.1", "world_id": "old_world", "campaign_id": None,
                     "slot": "auto", "saved_at": "2025-12-01T10:00:00Z", "current_hero_id": None},
        "world": {"world_id": "old_world",
                  "rng": {"algo": "pcg32", "seed": 7, "state": 5, "inc": 109, "draws": 0}},
        "session": {"current_scene": {"id": "tavern"}},
    }
    result = migrate(data, context=MigrationContext(item_cost={}))
    assert result["manifest"]["schema_version"] == CURRENT_SCHEMA_VERSION
    assert result["session"]["boundary_pending"] is False
    assert SaveBundle.model_validate(result).session.current_chapter is None


# R1: миры Вейла этапа 2 получают campaign_id, R6: last_day из часов

def vale_world(world_id="vale-b4f452b1", campaign_id=None):
    data = raw_v2()
    data["world"]["world_id"] = world_id
    data["world"]["campaign_id"] = campaign_id
    data["manifest"]["world_id"] = world_id
    data["manifest"]["campaign_id"] = campaign_id
    return data


def test_vale_world_gets_campaign_id_in_world_and_manifest():
    result = migrate_v2_to_v3(vale_world())
    assert result["world"]["campaign_id"] == "vale"
    assert result["manifest"]["campaign_id"] == "vale"


def test_not_vale_world_keeps_empty_campaign_id():
    result = migrate_v2_to_v3(vale_world("custom-world"))
    assert result["world"]["campaign_id"] is None
    assert result["manifest"]["campaign_id"] is None


def test_world_with_campaign_id_keeps_it():
    result = migrate_v2_to_v3(vale_world("vale-1", campaign_id="other"))
    assert result["world"]["campaign_id"] == "other"
    assert result["manifest"]["campaign_id"] == "other"


def test_sim_last_day_comes_from_clock():
    data = raw_v2()
    data["world"]["clock"] = {"now_s": 3 * 86400 + 100}
    assert migrate_v2_to_v3(data)["world"]["sim"]["last_day"] == 3


def test_sim_last_day_is_zero_at_start():
    data = raw_v2()
    data["world"]["clock"] = {"now_s": 4536}
    assert migrate_v2_to_v3(data)["world"]["sim"]["last_day"] == 0
