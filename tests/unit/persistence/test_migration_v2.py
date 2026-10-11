# Ожидаемый API: ai_dm.persistence.migrations.m0002_v1_to_v2 (этап 2, партия 1; ТЗ 5.3, A3)
#   migrate_v1_to_v2(data: dict) -> dict  -- чистое dict -> dict, вход не мутирует; schema_version
#       ставит фреймворк migrate(); MIGRATIONS[1] is migrate_v1_to_v2; CURRENT_SCHEMA_VERSION == 2.
#       Миграция заморожена в v2: не импортирует и не использует модели SceneState / TurnRecord
#       (правило ARCHITECTURE A3: persistence не читает старые файлы текущими моделями).
#   Правила (зафиксированы тестировщиком, проектировщик может поправить):
#     session.current_scene: dict этапа 1 (голая форма, например {"id": "tavern"}) -> None.
#         Этап 1 настоящих сцен не писал, переносить нечего; None уже и остаётся None.
#     session.turn_seq = 0; session.offered_choices = [] (setdefault: уже есть -- не трогаем)
#     session.current_chapter и прочие ключи session не трогаются
#     memory.recent_turns: оставляются только записи формы TurnRecord -- dict с turn_seq (int),
#         at_s (int), player_input (str), narration (str); requests / rolls -- списки строк (если
#         ключа нет -- допишется []). Остальные (например {"t": 1}, нет narration) отбрасываются;
#         порядок оставшихся сохраняется
#     всё остальное (world, heroes, chronicle, memory.scenes / chapters / game_summary) не трогается
#   Фикстура tests/fixtures/saves/v1/ собрана кодом этапа 1 (схема save_v1.schema.json), слот
#   "auto" мира old_world: current_scene={"id": "tavern"}, current_chapter={"id": "c1"},
#   recent_turns = [валидный ход turn_seq=1, {"t": 1}, ход без narration].
#   load_slot по v1-слоту: бэкап auto-v1-<ts> байт в байт, перезапись в v2, повторная загрузка --
#   без нового бэкапа; v0 -> v2 цепочкой (фикстура v0), один бэкап версии v0.
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
from ai_dm.persistence.migrations.m0002_v1_to_v2 import migrate_v1_to_v2
from ai_dm.state.save import SaveBundle

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "saves"
FIXTURE_V0 = FIXTURES / "v0"
FIXTURE_V1 = FIXTURES / "v1"
BACKUP_TS = "20260101T000000Z"

TURN = {
    "turn_seq": 1, "at_s": 90000, "player_input": "Осматриваюсь", "narration": "Таверна гудит.",
    "requests": ["skill_check"], "rolls": ["Внимательность 14 vs СЛ 10"],
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


def raw_v1(**session):
    return {
        "manifest": {
            "schema_version": 1, "engine_version": "0.1.0", "world_id": "old_world",
            "campaign_id": None, "slot": "auto", "saved_at": "2026-01-01T12:00:00Z",
            "current_hero_id": None, "heroes": [],
        },
        "world": {"world_id": "old_world", "flags": {"a": True},
                  "rng": {"algo": "pcg32", "seed": 7, "state": 5, "inc": 109, "draws": 0}},
        "chronicle": {"entries": []},
        "memory": {"scenes": [{"id": "s0"}], "chapters": [], "game_summary": "кратко",
                   "recent_turns": []},
        "heroes": [],
        "session": {"current_scene": None, "current_chapter": None, "active_combat": None,
                    "pending_decision": None, **session},
    }


def with_turns(turns):
    data = raw_v1()
    data["memory"]["recent_turns"] = turns
    return data


# реестр

def test_registry_has_step_from_v1():
    assert MIGRATIONS[1] is migrate_v1_to_v2
    assert CURRENT_SCHEMA_VERSION >= 2


# чистая миграция dict -> dict

def test_free_form_scene_dict_becomes_none():
    result = migrate_v1_to_v2(raw_v1(current_scene={"id": "tavern"}))
    assert result["session"]["current_scene"] is None


def test_missing_scene_stays_none():
    assert migrate_v1_to_v2(raw_v1())["session"]["current_scene"] is None


def test_turn_seq_and_offered_choices_are_added():
    session = migrate_v1_to_v2(raw_v1())["session"]
    assert session["turn_seq"] == 0
    assert session["offered_choices"] == []


def test_session_without_scene_key_gets_new_keys():
    data = raw_v1()
    data["session"] = {}
    session = migrate_v1_to_v2(data)["session"]
    assert session["turn_seq"] == 0
    assert session["offered_choices"] == []


def test_chapter_and_combat_keys_are_untouched():
    data = raw_v1(current_chapter={"id": "c1"})
    session = migrate_v1_to_v2(data)["session"]
    assert session["current_chapter"] == {"id": "c1"}
    assert session["active_combat"] is None
    assert session["pending_decision"] is None


def test_valid_turn_is_kept_unchanged():
    result = migrate_v1_to_v2(with_turns([TURN]))
    assert result["memory"]["recent_turns"] == [TURN]


def test_invalid_turns_are_dropped():
    broken = {"turn_seq": 2, "at_s": 90600, "player_input": "Иду"}
    result = migrate_v1_to_v2(with_turns([{"t": 1}, TURN, broken]))
    assert result["memory"]["recent_turns"] == [TURN]


def test_turn_with_wrong_field_type_is_dropped():
    wrong = dict(TURN, turn_seq="один")
    assert migrate_v1_to_v2(with_turns([wrong]))["memory"]["recent_turns"] == []


def test_turn_without_lists_gets_empty_lists():
    short = {k: v for k, v in TURN.items() if k not in ("requests", "rolls")}
    turns = migrate_v1_to_v2(with_turns([short]))["memory"]["recent_turns"]
    assert turns == [dict(short, requests=[], rolls=[])]


def test_order_of_kept_turns_is_preserved():
    second = dict(TURN, turn_seq=2)
    third = dict(TURN, turn_seq=3)
    result = migrate_v1_to_v2(with_turns([TURN, {"t": 1}, second, third]))
    assert [t["turn_seq"] for t in result["memory"]["recent_turns"]] == [1, 2, 3]


def test_other_memory_world_and_heroes_are_untouched():
    data = raw_v1()
    result = migrate_v1_to_v2(data)
    assert result["memory"]["scenes"] == [{"id": "s0"}]
    assert result["memory"]["game_summary"] == "кратко"
    assert result["world"] == data["world"]
    assert result["heroes"] == data["heroes"]
    assert result["chronicle"] == data["chronicle"]


def test_migrate_v1_to_v2_does_not_mutate_input():
    data = with_turns([TURN, {"t": 1}])
    data["session"]["current_scene"] = {"id": "tavern"}
    before = copy.deepcopy(data)
    migrate_v1_to_v2(data)
    assert data == before


def test_framework_sets_schema_version_two():
    result = migrate(raw_v1(), current_version=2)
    assert result["manifest"]["schema_version"] == 2


def test_migrated_dict_validates_as_current_bundle():
    data = with_turns([TURN, {"t": 1}])
    data["session"]["current_scene"] = {"id": "tavern"}
    bundle = SaveBundle.model_validate(migrate(data, context=MigrationContext(item_cost={})))
    assert bundle.session.current_scene is None
    assert bundle.session.turn_seq == 0
    assert [t.turn_seq for t in bundle.memory.recent_turns] == [1]


def test_already_v2_dict_is_not_migrated_again():
    data = raw_v1(turn_seq=5, offered_choices=["Да"])
    data["manifest"]["schema_version"] = 2
    assert migrate(data, current_version=2) == data


# фикстура v1 на диске

def test_fixture_v1_is_stage1_format():
    manifest = json.loads((FIXTURE_V1 / "manifest.json").read_text(encoding="utf-8"))
    session = json.loads((FIXTURE_V1 / "session.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert session["current_scene"] == {"id": "tavern"}
    assert "turn_seq" not in session


def test_load_v1_returns_current_bundle(saves):
    install(saves, FIXTURE_V1)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.manifest.schema_version == CURRENT_SCHEMA_VERSION
    assert bundle.session.current_scene is None
    assert bundle.session.turn_seq == 0
    assert bundle.session.offered_choices == []
    # v3: свободная форма главы не совпала с ChapterState -> None (m0003)
    assert bundle.session.current_chapter is None


def test_load_v1_keeps_valid_turn_and_drops_invalid(saves):
    install(saves, FIXTURE_V1)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert [t.turn_seq for t in bundle.memory.recent_turns] == [1]
    assert bundle.memory.recent_turns[0].narration == "Таверна гудит."
    assert bundle.memory.recent_turns[0].rolls == ["Внимательность 14 vs СЛ 10"]


def test_load_v1_keeps_world_and_hero(saves):
    install(saves, FIXTURE_V1)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.world.flags == {"met_aldric": True}
    assert bundle.world.npcs["mentor_aldric"].attitude == 20
    assert [h.id for h in bundle.heroes] == ["h1"]
    assert bundle.heroes[0].money_cp == 1235


def test_load_v1_makes_byte_exact_backup(saves):
    install(saves, FIXTURE_V1)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    backup = saves / "old_world" / "backups" / f"auto-v1-{BACKUP_TS}"
    assert tree(backup) == tree(FIXTURE_V1)


def test_load_v1_rewrites_slot_as_current(saves):
    folder = install(saves, FIXTURE_V1)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    session = json.loads((folder / "session.json").read_text(encoding="utf-8"))
    memory = json.loads((folder / "world" / "memory.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == CURRENT_SCHEMA_VERSION
    assert session["current_scene"] is None
    assert session["turn_seq"] == 0
    assert session["offered_choices"] == []
    assert len(memory["recent_turns"]) == 1


def test_load_v1_twice_makes_no_second_backup_and_same_bundle(saves):
    install(saves, FIXTURE_V1)
    first = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    second = load_slot(saves, "old_world", "auto", backup_ts="20260202T000000Z")
    assert second == first
    assert len(list((saves / "old_world" / "backups").iterdir())) == 1


def test_load_v1_does_not_touch_fixture_itself(saves):
    before = tree(FIXTURE_V1)
    install(saves, FIXTURE_V1)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert tree(FIXTURE_V1) == before


# цепочка v0 -> v2

def test_load_v0_chain_reaches_current_with_single_backup(saves):
    install(saves, FIXTURE_V0)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.manifest.schema_version == CURRENT_SCHEMA_VERSION
    assert bundle.session.current_scene is None
    assert bundle.session.turn_seq == 0
    assert bundle.memory.recent_turns == []
    assert bundle.heroes[0].name == "Старый Арн"
    backups = sorted((saves / "old_world" / "backups").iterdir())
    assert [b.name for b in backups] == [f"auto-v0-{BACKUP_TS}"]
    assert tree(backups[0]) == tree(FIXTURE_V0)


def test_v0_dict_chain_runs_both_steps_in_order():
    data = {
        "manifest": {"engine_version": "0.0.1", "world_id": "old_world", "campaign_id": None,
                     "slot": "auto", "saved_at": "2025-12-01T10:00:00Z", "current_hero_id": None},
        "world": {"world_id": "old_world",
                  "rng": {"algo": "pcg32", "seed": 7, "state": 5, "inc": 109, "draws": 0}},
        "session": {"current_scene": {"id": "tavern"}},
    }
    result = migrate(data, context=MigrationContext(item_cost={}))
    assert result["manifest"]["schema_version"] == CURRENT_SCHEMA_VERSION
    assert result["session"]["current_scene"] is None
    assert result["session"]["turn_seq"] == 0
    assert result["memory"]["recent_turns"] == []


# запись с лишним ключом -- не TurnRecord (ревью партии 1, п.1)

def test_turn_with_extra_key_is_dropped():
    extra = dict(TURN, bogus=1)
    assert migrate_v1_to_v2(with_turns([extra]))["memory"]["recent_turns"] == []


def test_turn_with_extra_key_is_dropped_but_valid_neighbours_stay():
    extra = dict(TURN, turn_seq=2, mood="angry")
    result = migrate_v1_to_v2(with_turns([TURN, extra]))
    assert result["memory"]["recent_turns"] == [TURN]
