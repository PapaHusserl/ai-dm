# М0-П1 (docs/plan-m0.md): миграция v15 -> v16 -- рёбрам kind="road", needs_transport=False;
# NPC с trade -- hours {open_hour: 8, close_hour: 16}; остальное -- значения по умолчанию.
# API: ai_dm.persistence.migrations.m0016_v15_to_v16.migrate_v15_to_v16(data, context=None) -> dict
#   -- чистое dict -> dict, вход не мутирует; MIGRATIONS[15] is migrate_v15_to_v16.
#   Отпечаток: tests/schema/save_v16.schema.json. Загрузка фикстуры v13 цепочкой до 16.
import ast
import copy
import json
import shutil
from pathlib import Path

import pytest
from persist_kit import load_slot

from ai_dm.persistence.migrations import (
    CURRENT_SCHEMA_VERSION,
    MIGRATIONS,
    SaveTooNew,
    migrate,
)
from ai_dm.persistence.migrations.m0016_v15_to_v16 import migrate_v15_to_v16
from ai_dm.state.save import SaveBundle

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "saves"
FIXTURE_V13 = FIXTURES / "v13"
SCHEMA_DIR = ROOT / "tests" / "schema"
WORLD_ID = "zh0_world"
BACKUP_TS = "20260101T000000Z"
MIGRATION_FILE = (
    ROOT / "src" / "ai_dm" / "persistence" / "migrations" / "m0016_v15_to_v16.py"
)
HOURS_8_16 = {"open_hour": 8, "close_hour": 16}


def raw_v15():
    return {
        "manifest": {"schema_version": 15, "world_id": "w"},
        "world": {
            "world_id": "w",
            "locations": {
                "a": {"id": "a", "connections": [{"to": "b", "distance_m": 1000}]},
                "b": {"id": "b", "connections": []},
            },
            "npcs": {
                "shop": {"id": "shop", "trade": {"kind": "general"}, "services": []},
                "inn": {"id": "inn", "trade": None, "services": ["lodging"]},
                "plain": {"id": "plain", "trade": None, "services": []},
            },
        },
        "heroes": [{"id": "h1", "inventory": [], "companions": []}],
        "session": {"turn_seq": 2},
    }


def migrated():
    return migrate_v15_to_v16(raw_v15())


def test_registry_has_step_from_v15():
    assert MIGRATIONS[15] is migrate_v15_to_v16
    assert CURRENT_SCHEMA_VERSION >= 16


def test_framework_sets_schema_version_sixteen():
    assert migrate(raw_v15(), current_version=16)["manifest"]["schema_version"] == 16


def test_v15_to_v15_is_not_touched():
    assert migrate(raw_v15(), current_version=15) == raw_v15()


def test_engine_v15_refuses_a_v16_dict():
    data = raw_v15()
    data["manifest"]["schema_version"] = 16
    with pytest.raises(SaveTooNew):
        migrate(data, current_version=15)


def test_migration_does_not_mutate_input():
    data = raw_v15()
    before = copy.deepcopy(data)
    migrate_v15_to_v16(data)
    assert data == before


def test_migration_returns_a_copy():
    data = raw_v15()
    assert migrate_v15_to_v16(data) is not data


def test_migration_works_without_context_argument():
    assert migrate_v15_to_v16(raw_v15(), None) == migrate_v15_to_v16(raw_v15())


def test_migration_without_world_key_returns_data_unchanged():
    data = {"manifest": {"schema_version": 15, "world_id": "w"}}
    assert migrate_v15_to_v16(data) == data


def test_migration_does_not_import_state_or_content_models():
    names = []
    for node in ast.walk(ast.parse(MIGRATION_FILE.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    assert not [n for n in names if n.startswith(("ai_dm.state", "ai_dm.content"))]


# рёбра

def test_connection_gets_road_kind():
    edge = migrated()["world"]["locations"]["a"]["connections"][0]
    assert edge["kind"] == "road"


def test_connection_gets_needs_transport_false():
    edge = migrated()["world"]["locations"]["a"]["connections"][0]
    assert edge["needs_transport"] is False


def test_connection_distance_is_kept():
    edge = migrated()["world"]["locations"]["a"]["connections"][0]
    assert (edge["to"], edge["distance_m"]) == ("b", 1000)


def test_connection_with_kind_is_not_overwritten():
    data = raw_v15()
    data["world"]["locations"]["a"]["connections"][0]["kind"] = "trail"
    edge = migrate_v15_to_v16(data)["world"]["locations"]["a"]["connections"][0]
    assert edge["kind"] == "trail"


# часы работы

def test_trader_gets_hours_8_16():
    assert migrated()["world"]["npcs"]["shop"]["hours"] == HOURS_8_16


def test_npc_with_services_gets_no_hours():
    assert migrated()["world"]["npcs"]["inn"].get("hours") is None


def test_npc_without_trade_and_services_gets_no_hours():
    assert migrated()["world"]["npcs"]["plain"].get("hours") is None


def test_trader_with_hours_is_not_overwritten():
    data = raw_v15()
    data["world"]["npcs"]["shop"]["hours"] = {"open_hour": 6, "close_hour": 12}
    npc = migrate_v15_to_v16(data)["world"]["npcs"]["shop"]
    assert npc["hours"] == {"open_hour": 6, "close_hour": 12}


# отпечаток v16

def test_v16_fingerprint_file_exists():
    assert (SCHEMA_DIR / "save_v16.schema.json").is_file()


def test_v16_fingerprint_equals_current_schema():
    stored = json.loads((SCHEMA_DIR / "save_v16.schema.json").read_text(encoding="utf-8"))
    assert stored == json.loads(json.dumps(SaveBundle.model_json_schema()))


NEW_V16_FIELDS = [
    ("Connection", "kind"), ("Connection", "needs_transport"),
    ("Location", "temporary"),
    ("NPC", "hours"), ("NPC", "partner"), ("NPC", "links"),
    ("CustomItem", "base_id"), ("CustomItem", "mods"),
    ("WorldState", "preset"), ("WorldState", "scene_weights"), ("WorldState", "pending"),
    ("InventoryEntry", "mods"),
    ("Equipped", "clothing"), ("Equipped", "neck"), ("Equipped", "ring_1"),
    ("Equipped", "ring_2"), ("Equipped", "wrists"), ("Equipped", "head"),
    ("HeroState", "transport"), ("HeroState", "journey"),
    ("CreatureState", "hp_temp_expires"), ("CreatureState", "wake_at_s"),
]
NEW_V16_MODELS = [
    "WorkHours", "Partner", "Contract", "NpcLink", "PendingEvent",
    "ItemMods", "Transport", "Journey",
]


@pytest.mark.parametrize(("model", "field"), NEW_V16_FIELDS)
def test_v15_fingerprint_lacks_new_field(model, field):
    v15 = json.loads((SCHEMA_DIR / "save_v15.schema.json").read_text(encoding="utf-8"))
    assert field not in v15["$defs"][model]["properties"]


@pytest.mark.parametrize(("model", "field"), NEW_V16_FIELDS)
def test_v16_schema_has_new_field(model, field):
    assert field in SaveBundle.model_json_schema()["$defs"][model]["properties"]


@pytest.mark.parametrize("model", NEW_V16_MODELS)
def test_v15_fingerprint_lacks_new_model(model):
    v15 = json.loads((SCHEMA_DIR / "save_v15.schema.json").read_text(encoding="utf-8"))
    assert model not in v15["$defs"]


def test_v16_item_mods_fields():
    props = SaveBundle.model_json_schema()["$defs"]["ItemMods"]["properties"]
    assert {
        "damage_bonus", "range_normal_ft", "range_long_ft", "ac_bonus",
        "weight_centilb", "cost_cp", "label",
    } <= set(props)


def test_v16_new_models_fields():
    defs = SaveBundle.model_json_schema()["$defs"]
    assert {"open_hour", "close_hour"} <= set(defs["WorkHours"]["properties"])
    assert {"level", "xp", "loot_share_percent", "contract"} <= set(defs["Partner"]["properties"])
    assert {
        "until_s", "pay_cp_per_day", "payer", "paid_until_s", "leaves_unpaid", "transport",
    } <= set(defs["Contract"]["properties"])
    assert {"npc_id", "text"} <= set(defs["NpcLink"]["properties"])
    assert {"at_s", "target", "kind", "ref", "text"} <= set(defs["PendingEvent"]["properties"])
    assert {"kind", "name", "owner_npc", "until_s"} <= set(defs["Transport"]["properties"])
    assert {
        "to", "pace", "start_id", "road_id", "from_id", "edge_to", "edge_done_s",
    } <= set(defs["Journey"]["properties"])


# загрузка слота v13 цепочкой до v16

def install(saves):
    shutil.copytree(FIXTURE_V13, saves / WORLD_ID / "slots" / "auto")
    return saves / WORLD_ID / "slots" / "auto"


def load_v13(saves):
    install(saves)
    return load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS)


def test_load_v13_hero_transport_is_none(saves):
    assert load_v13(saves).heroes[0].transport is None


def test_load_v13_hero_journey_is_none(saves):
    assert load_v13(saves).heroes[0].journey is None


def test_load_v13_world_pending_is_empty(saves):
    assert load_v13(saves).world.pending == []


def test_load_v13_world_preset_is_empty(saves):
    assert load_v13(saves).world.preset == ""


def test_load_v13_world_scene_weights_is_empty(saves):
    assert load_v13(saves).world.scene_weights == {}


def test_load_v13_equipped_ring_is_none(saves):
    assert load_v13(saves).heroes[0].equipped.ring_1 is None


def test_load_v13_every_location_is_not_temporary(saves):
    bundle = load_v13(saves)
    assert [p.id for p in bundle.world.locations.values() if p.temporary] == []


def test_load_v13_every_connection_is_road(saves):
    bundle = load_v13(saves)
    kinds = {c.kind for p in bundle.world.locations.values() for c in p.connections}
    assert kinds <= {"road"}


def test_load_v13_rewrites_slot_as_current_version(saves):
    folder = install(saves)
    load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == CURRENT_SCHEMA_VERSION


# модели М0-П1

def test_work_hours_round_the_clock_is_accepted():
    from ai_dm.state.world import WorkHours

    hours = WorkHours(open_hour=0, close_hour=24)
    assert (hours.open_hour, hours.close_hour) == (0, 24)


def test_work_hours_through_midnight_is_accepted():
    from ai_dm.state.world import WorkHours

    hours = WorkHours(open_hour=20, close_hour=4)
    assert (hours.open_hour, hours.close_hour) == (20, 4)


def test_work_hours_equal_hours_are_rejected():
    from pydantic import ValidationError

    from ai_dm.state.world import WorkHours

    with pytest.raises(ValidationError):
        WorkHours(open_hour=8, close_hour=8)


def test_work_hours_open_at_24_is_rejected():
    from pydantic import ValidationError

    from ai_dm.state.world import WorkHours

    with pytest.raises(ValidationError):
        WorkHours(open_hour=24, close_hour=6)


def test_work_hours_close_at_24_with_nonzero_open_is_rejected():
    from pydantic import ValidationError

    from ai_dm.state.world import WorkHours

    with pytest.raises(ValidationError):
        WorkHours(open_hour=18, close_hour=24)


def test_work_hours_out_of_range_is_rejected():
    from pydantic import ValidationError

    from ai_dm.state.world import WorkHours

    with pytest.raises(ValidationError):
        WorkHours(open_hour=-1, close_hour=6)
    with pytest.raises(ValidationError):
        WorkHours(open_hour=8, close_hour=25)


def test_contract_payer_defaults_to_none_meaning_hero():
    from ai_dm.state.world import Contract

    assert Contract().payer is None


def test_contract_payer_accepts_npc_id():
    from ai_dm.state.world import Contract

    assert Contract(payer="finn").payer == "finn"


def test_journey_pace_is_required():
    from pydantic import ValidationError

    from ai_dm.state.hero import Journey

    with pytest.raises(ValidationError):
        Journey(to="b", start_id="a")


def test_journey_with_pace_is_accepted():
    from ai_dm.state.hero import Journey

    assert Journey(to="b", start_id="a", pace="normal").pace == "normal"
