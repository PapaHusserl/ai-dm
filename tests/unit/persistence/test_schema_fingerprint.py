# Тест-отпечаток схемы сейва (шаг 22, A3): SaveBundle.model_json_schema() должна совпадать с
# tests/schema/save_v<CURRENT_SCHEMA_VERSION>.schema.json. Изменил модель сейва без подъёма
# версии -- тест красный.
#
# ПРАВИЛО (важно):
#   * (история) ДО релиза этапа 1 отпечаток v1 перегенерировался осознанно, версия не поднималась:
#     сейвов у пользователей ещё нет. В частности схема боя (SessionState.active_combat,
#     pending_decision сейчас -- dict) будет типизирована в партии 5, и отпечаток v1 тогда
#     обновится одной командой (ниже).
#   * ПОСЛЕ релиза этапа 1 (тег stage-1) любое изменение схемы = CURRENT_SCHEMA_VERSION + 1,
#     новое звено миграции, новый файл save_v<N+1>.schema.json (старый файл остаётся как история).
#
# Этап 2: CURRENT_SCHEMA_VERSION = 2, отпечаток tests/schema/save_v2.schema.json (SceneState,
# TurnRecord, SessionState.turn_seq / offered_choices). save_v1.schema.json остаётся как
# исторический артефакт и не перегенерируется.
#
# Перегенерация отпечатка v2 (из корня проекта, ПОСЛЕ реализации моделей этапа 2):
#   uv run python -c "import json; from ai_dm.state.save import SaveBundle; \
#   f = open('tests/schema/save_v2.schema.json', 'w', encoding='utf-8'); \
#   json.dump(SaveBundle.model_json_schema(), f, ensure_ascii=False, indent=2, sort_keys=True); \
#   f.write('\n')"
#
# Этап 3: CURRENT_SCHEMA_VERSION = 3, отпечаток tests/schema/save_v3.schema.json. До закрытия этапа
# версия одна (v3, Т-18): схема меняется осознанно, отпечаток перегенерируется той же командой
# с save_v3 вместо save_v2. save_v1 / save_v2 -- история, не перегенерируются.
#
# Этап 4 (следопыт 2-5, docs/plan-ranger-2-5.md): CURRENT_SCHEMA_VERSION = 4, отпечаток
# tests/schema/save_v4.schema.json (CharacterSheet.skill_expertise / languages / feature_options,
# HeroState.companion). save_v3 -- история. Перегенерация -- командой выше с save_v4.
# Ожидаемый API: ai_dm.persistence.migrations.CURRENT_SCHEMA_VERSION, ai_dm.state.save.SaveBundle
import json
from pathlib import Path

from ai_dm.persistence.migrations import CURRENT_SCHEMA_VERSION
from ai_dm.state.save import SaveBundle

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schema"


def fingerprint_path(version):
    return SCHEMA_DIR / f"save_v{version}.schema.json"


def test_fingerprint_file_exists_for_current_version():
    assert fingerprint_path(CURRENT_SCHEMA_VERSION).is_file()


def test_save_bundle_schema_matches_fingerprint():
    stored = json.loads(fingerprint_path(CURRENT_SCHEMA_VERSION).read_text(encoding="utf-8"))
    assert SaveBundle.model_json_schema() == stored


def test_fingerprint_describes_all_bundle_sections():
    stored = json.loads(fingerprint_path(CURRENT_SCHEMA_VERSION).read_text(encoding="utf-8"))
    assert sorted(stored["properties"]) == [
        "chronicle", "heroes", "manifest", "memory", "session", "world",
    ]


# этап 2: v1-отпечаток -- история, v2 знает новые модели

def test_v1_fingerprint_is_kept_as_history_without_stage2_models():
    stored = json.loads(fingerprint_path(1).read_text(encoding="utf-8"))
    assert "SceneState" not in stored["$defs"]
    assert "TurnRecord" not in stored["$defs"]


def test_current_schema_knows_scene_and_turn_models():
    defs = SaveBundle.model_json_schema()["$defs"]
    assert "SceneState" in defs
    assert "TurnRecord" in defs


# v4: новые поля героя

def test_v4_schema_knows_ranger_fields():
    defs = json.loads(fingerprint_path(8).read_text(encoding="utf-8"))["$defs"]
    sheet = defs["CharacterSheet"]["properties"]
    assert {"skill_expertise", "languages", "feature_options"} <= set(sheet)
    assert "companion" in defs["HeroState"]["properties"]


def test_v3_fingerprint_is_kept_as_history_without_ranger_fields():
    stored = json.loads(fingerprint_path(3).read_text(encoding="utf-8"))
    assert "skill_expertise" not in stored["$defs"]["CharacterSheet"]["properties"]


# этап 4, P1: CURRENT_SCHEMA_VERSION = 5, отпечаток tests/schema/save_v5.schema.json (источник
# выжимок, Memory.game_summary_chapter, TurnRecord.scene_id). save_v4 -- история, не
# перегенерируется. Перегенерация v5 -- командой из шапки с save_v5 вместо save_v2.

def test_v5_schema_knows_memory_fields():
    defs = SaveBundle.model_json_schema()["$defs"]
    assert "source" in defs["SceneSummary"]["properties"]
    assert {"source", "at_s"} <= set(defs["ChapterSummary"]["properties"])
    assert "game_summary_chapter" in SaveBundle.model_json_schema()["$defs"]["Memory"]["properties"]
    assert "scene_id" in defs["TurnRecord"]["properties"]


def test_v4_fingerprint_is_kept_as_history_without_stage4_memory_fields():
    stored = json.loads(fingerprint_path(4).read_text(encoding="utf-8"))
    assert "game_summary_chapter" not in stored["$defs"]["Memory"]["properties"]
    assert "scene_id" not in stored["$defs"]["TurnRecord"]["properties"]


# партия «переговоры»: Participant.status получил "surrendered", версия остаётся v5 (отпечаток
# перегенерирован осознанно); старые сейвы читаются без миграции.

def test_v5_schema_knows_surrendered_status():
    defs = SaveBundle.model_json_schema()["$defs"]
    assert "surrendered" in defs["Participant"]["properties"]["status"]["enum"]


# партия «торговля» Т0: CURRENT_SCHEMA_VERSION = 7, отпечаток tests/schema/save_v7.schema.json
# (NPC.trade: TradeProfile, SceneState.trades / merchants_created). save_v6 -- история.

def test_v7_schema_knows_trade_fields():
    defs = SaveBundle.model_json_schema()["$defs"]
    assert "TradeProfile" in defs
    assert {"kind", "purse_cp", "restock_at_s", "stock"} <= set(defs["TradeProfile"]["properties"])
    assert "trade" in defs["NPC"]["properties"]
    assert {"trades", "merchants_created"} <= set(defs["SceneState"]["properties"])


def test_v6_fingerprint_is_kept_as_history_without_trade_fields():
    stored = json.loads(fingerprint_path(6).read_text(encoding="utf-8"))
    assert "TradeProfile" not in stored["$defs"]
    assert "trade" not in stored["$defs"]["NPC"]["properties"]


# Б0-П0: CURRENT_SCHEMA_VERSION = 8, отпечаток save_v8.schema.json (Tone.romance расширена,
# BackgroundSpec.description). save_v7 -- история.

def test_v8_schema_knows_new_romance_values():
    defs = SaveBundle.model_json_schema()["$defs"]
    assert defs["Tone"]["properties"]["romance"]["enum"] == [
        "", "нет", "намёки", "чувственно", "откровенно",
    ]


def test_v8_schema_knows_background_description():
    defs = SaveBundle.model_json_schema()["$defs"]
    assert "description" in defs["BackgroundSpec"]["properties"]


def test_v7_fingerprint_is_kept_as_history_with_old_romance():
    stored = json.loads(fingerprint_path(7).read_text(encoding="utf-8"))
    assert "есть" in stored["$defs"]["Tone"]["properties"]["romance"]["enum"]
    assert "description" not in stored["$defs"]["BackgroundSpec"]["properties"]


# К0а: CURRENT_SCHEMA_VERSION = 9, отпечаток save_v9.schema.json (classes / level_history,
# Concentration, TempForm, Equipment, GrantedSpell, PendingLevel, companions). save_v8 -- история.

def test_v9_schema_knows_new_models():
    defs = SaveBundle.model_json_schema()["$defs"]
    for name in ("ClassLevel", "PendingLevel", "Concentration", "TempForm", "Equipment",
        "GrantedSpell"):
        assert name in defs


def test_v9_sheet_has_no_scalar_class_fields():
    sheet = SaveBundle.model_json_schema()["$defs"]["CharacterSheet"]["properties"]
    assert not {"class_id", "level", "subclass_id", "feature_options"} & set(sheet)
    assert {"classes", "level_history", "feature_choices", "spells_always_prepared"} <= set(sheet)


def test_v9_hero_has_companions_but_no_companion():
    hero = SaveBundle.model_json_schema()["$defs"]["HeroState"]["properties"]
    assert "companion" not in hero
    assert {"companions", "attuned", "pending_level"} <= set(hero)


def test_v9_creature_has_concentration_object_and_temp_form():
    creature = SaveBundle.model_json_schema()["$defs"]["CreatureState"]["properties"]
    assert {"concentration", "temp_form"} <= set(creature)


def test_v9_equipment_on_npc_and_participant():
    defs = SaveBundle.model_json_schema()["$defs"]
    assert "equipment" in defs["NPC"]["properties"]
    assert "equipment" in defs["Participant"]["properties"]


def test_v8_fingerprint_is_kept_as_history_with_scalar_class():
    stored = json.loads(fingerprint_path(8).read_text(encoding="utf-8"))
    assert "class_id" in stored["$defs"]["CharacterSheet"]["properties"]
    assert "ClassLevel" not in stored["$defs"]


# Ж0 подшаг 1: CURRENT_SCHEMA_VERSION = 11, отпечаток save_v11.schema.json (память/цели NPC,
# known_name, family, services, KnowledgeEntry, scene_mood, pending_acts). save_v10 -- история.

# ФС: CURRENT_SCHEMA_VERSION = 13, отпечаток save_v13.schema.json (DeathRecord.cause + left).
# save_v12 -- история.

def test_v13_fingerprint_exists_and_v14_is_current():
    assert CURRENT_SCHEMA_VERSION == 14
    assert fingerprint_path(13).is_file()
    assert fingerprint_path(14).is_file()


def test_v11_schema_knows_new_models():
    defs = SaveBundle.model_json_schema()["$defs"]
    for name in ("NpcEvent", "NpcSceneMemory", "NpcGoal", "FamilyLink", "KnowledgeEntry"):
        assert name in defs


def test_v11_npc_fields():
    npc = SaveBundle.model_json_schema()["$defs"]["NPC"]["properties"]
    assert {"memory", "goals", "known_name", "family", "services"} <= set(npc)
    assert "relations_text" not in npc


def test_v11_hero_scene_and_sim_fields():
    defs = SaveBundle.model_json_schema()["$defs"]
    assert {"family", "knowledge"} <= set(defs["HeroState"]["properties"])
    assert "scene_mood" in defs["SceneState"]["properties"]
    assert "pending_acts" in defs["WorldSim"]["properties"]


def test_v11_closed_enums_open_kinds():
    defs = SaveBundle.model_json_schema()["$defs"]
    assert defs["NpcGoal"]["properties"]["status"]["enum"] == ["active", "done", "dropped"]
    assert defs["FamilyLink"]["properties"]["kind"]["enum"] == ["parent", "spouse", "child"]
    assert "enum" not in defs["NpcEvent"]["properties"]["kind"]
    assert "enum" not in defs["NpcGoal"]["properties"]["kind"]
    assert "enum" not in defs["KnowledgeEntry"]["properties"]["kind"]
    assert "enum" not in defs["KnowledgeEntry"]["properties"]["source"]


def test_v10_fingerprint_is_kept_as_history_with_relations_text():
    stored = json.loads(fingerprint_path(10).read_text(encoding="utf-8"))
    assert "relations_text" in stored["$defs"]["NPC"]["properties"]
    assert "NpcSceneMemory" not in stored["$defs"]
