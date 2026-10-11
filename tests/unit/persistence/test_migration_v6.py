# Ожидаемый API: ai_dm.persistence.migrations.m0006_v5_to_v6 (CUSTOM-ITEMS-PLAN, партия 0).
#   migrate_v5_to_v6(data: dict, context: MigrationContext) -> dict -- чистое dict -> dict, вход не
#       мутирует; schema_version ставит фреймворк; MIGRATIONS[5] is migrate_v5_to_v6;
#       CURRENT_SCHEMA_VERSION == 6. Миграция заморожена: не импортирует ai_dm.state.* и content.
#   MigrationContext(item_cost: dict[str, int]) -- цены предметов по id (из реестра);
#       .report: list[str] -- записи о том, что миграция не смогла (строка содержит id предмета).
#       Живёт в ai_dm.persistence.migrations вместе с MigrationContextRequired.
#   migrate(data, *, registry=None, current_version=None, context=None): шаг, которому нужны цены
#       (v5 -> v6), без context -- MigrationContextRequired; цепочка без этого шага context не
#       требует; уже v6 -- не мигрируется и context не нужен.
#   Правила (партия 0): каждой записи heroes[*].inventory и session.active_combat.ground_items
#       проставляется cost_cp = item_cost[item_id] (setdefault: заданная цена не трогается);
#       неизвестный id -> cost_cp = 0 и запись в context.report (не падать); quality не ставится
#       (None = «как новый»); остальное не меняется.
#   store.load_slot строит context сам (из встроенного реестра) и делает бэкап слота
#       backups/<slot>-v5-<ts> байт в байт.
#   Фикстуры: tests/fixtures/saves/v5 -- слот auto мира old_world (герой Арн: longsword x1 надет,
#       scimitar x2, potion_of_healing x3, shield x1, ghost_relic x1 -- id нет в реестре);
#       v5_combat -- то же + session.last_combat (looted=false). Сгенерированы движком v5.
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
    MigrationContext,
    MigrationContextRequired,
    SaveTooNew,
    migrate,
)
from ai_dm.persistence.migrations.m0006_v5_to_v6 import migrate_v5_to_v6
from ai_dm.persistence.store import save_slot

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "saves"
FIXTURE_V5 = FIXTURES / "v5"
FIXTURE_V5_COMBAT = FIXTURES / "v5_combat"
BACKUP_TS = "20260101T000000Z"
SAVED_AT = "2026-01-01T12:00:00Z"
MIGRATION_FILE = (
    Path(__file__).resolve().parents[3]
    / "src" / "ai_dm" / "persistence" / "migrations" / "m0006_v5_to_v6.py"
)
COSTS = {"longsword": 1500, "scimitar": 2500, "potion_of_healing": 5000}


def tree(folder):
    return {
        p.relative_to(folder).as_posix(): p.read_bytes()
        for p in sorted(folder.rglob("*")) if p.is_file()
    }


def install(saves, fixture, slot="auto", world_id="old_world"):
    target = saves / world_id / "slots" / slot
    shutil.copytree(fixture, target)
    return target


def ctx(costs=None):
    return MigrationContext(item_cost=dict(COSTS if costs is None else costs))


def raw_hero(hero_id="hero", inventory=()):
    return {"id": hero_id, "ordinal": 1, "name": "Арн", "inventory": list(inventory)}


def raw_v5(heroes=(), ground=None):
    session = {"turn_seq": 2, "active_combat": None}
    if ground is not None:
        session["active_combat"] = {"id": "c1", "ground_items": list(ground)}
    return {
        "manifest": {"schema_version": 5, "world_id": "old_world"},
        "world": {"world_id": "old_world"},
        "heroes": list(heroes),
        "session": session,
    }


def entry(item_id, qty=1, **extra):
    return {"item_id": item_id, "qty": qty, **extra}


def ground(item_id, **extra):
    return {"item_id": item_id, "zone_id": "hall", "owner_ref": None, "qty": 1, **extra}


def inventory_of(data, index=0):
    return data["heroes"][index]["inventory"]


# реестр и фреймворк

def test_registry_has_step_from_v5():
    assert MIGRATIONS[5] is migrate_v5_to_v6
    assert CURRENT_SCHEMA_VERSION >= 6


def test_framework_sets_schema_version_six():
    assert migrate(raw_v5(), context=ctx(), current_version=6)["manifest"]["schema_version"] == 6


def test_v5_without_context_is_refused():
    with pytest.raises(MigrationContextRequired):
        migrate(raw_v5([raw_hero(inventory=[entry("longsword")])]))


def test_v5_without_context_is_refused_even_with_empty_inventory():
    with pytest.raises(MigrationContextRequired):
        migrate(raw_v5())


def test_v5_to_v5_does_not_need_a_context():
    assert migrate(raw_v5(), current_version=5) == raw_v5()


def test_already_v6_dict_is_not_migrated_again():
    data = raw_v5([raw_hero(inventory=[entry("longsword")])])
    data["manifest"]["schema_version"] = 6
    assert migrate(data, current_version=6) == data


def test_engine_v5_refuses_a_v6_dict():
    data = raw_v5()
    data["manifest"]["schema_version"] = 6
    with pytest.raises(SaveTooNew):
        migrate(data, current_version=5)


def test_migrate_v5_to_v6_does_not_mutate_input():
    data = raw_v5([raw_hero(inventory=[entry("longsword")])], [ground("scimitar")])
    before = copy.deepcopy(data)
    migrate_v5_to_v6(data, ctx())
    assert data == before


def test_migration_does_not_import_state_or_content_models():
    names = []
    for node in ast.walk(ast.parse(MIGRATION_FILE.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    assert not [n for n in names if n.startswith(("ai_dm.state", "ai_dm.content"))]


# цены записей

def test_hero_entries_get_the_price_from_the_context():
    data = raw_v5([raw_hero(inventory=[entry("longsword"), entry("scimitar", 2)])])
    result = migrate(data, context=ctx(), current_version=6)
    assert [e["cost_cp"] for e in inventory_of(result)] == [1500, 2500]


def test_qty_and_id_of_entries_stay():
    data = raw_v5([raw_hero(inventory=[entry("scimitar", 2)])])
    result = migrate(data, context=ctx(), current_version=6)
    assert (inventory_of(result)[0]["item_id"], inventory_of(result)[0]["qty"]) == ("scimitar", 2)


def test_every_hero_gets_prices():
    data = raw_v5([
        raw_hero("a", [entry("longsword")]), raw_hero("b", [entry("potion_of_healing")]),
    ])
    result = migrate(data, context=ctx(), current_version=6)
    assert inventory_of(result, 0)[0]["cost_cp"] == 1500
    assert inventory_of(result, 1)[0]["cost_cp"] == 5000


def test_quality_is_not_set_for_old_entries():
    result = migrate(raw_v5([raw_hero(inventory=[entry("longsword")])]), context=ctx(),
        current_version=6)
    assert inventory_of(result)[0].get("quality") is None


def test_existing_cost_is_not_overwritten():
    data = raw_v5([raw_hero(inventory=[entry("longsword", cost_cp=77)])])
    assert inventory_of(migrate(data, context=ctx(), current_version=6))[0]["cost_cp"] == 77


def test_price_comes_from_the_context_not_from_a_constant():
    data = raw_v5([raw_hero(inventory=[entry("longsword")])])
    result = migrate(data, context=ctx({"longsword": 42}), current_version=6)
    assert inventory_of(result)[0]["cost_cp"] == 42


def test_hero_without_inventory_is_fine():
    data = raw_v5([{"id": "hero", "ordinal": 1, "name": "Арн"}])
    assert migrate(data, context=ctx(), current_version=6)["heroes"][0]["id"] == "hero"


def test_no_heroes_is_fine():
    assert migrate(raw_v5(), context=ctx(), current_version=6)["heroes"] == []


def test_two_entries_of_one_id_both_get_the_price():
    data = raw_v5([raw_hero(inventory=[entry("scimitar"), entry("scimitar", 2)])])
    assert [e["cost_cp"] for e in inventory_of(migrate(data, context=ctx(),
        current_version=6))] == [2500, 2500]


# неизвестный id

def test_unknown_id_gets_zero_cost_and_does_not_fail():
    data = raw_v5([raw_hero(inventory=[entry("ghost_relic")])])
    assert inventory_of(migrate(data, context=ctx(), current_version=6))[0]["cost_cp"] == 0


def test_unknown_id_goes_to_the_report():
    context = ctx()
    migrate(raw_v5([raw_hero(inventory=[entry("ghost_relic")])]), context=context,
        current_version=6)
    assert any("ghost_relic" in line for line in context.report)


def test_known_ids_leave_the_report_empty():
    context = ctx()
    migrate(raw_v5([raw_hero(inventory=[entry("longsword")])]), context=context, current_version=6)
    assert context.report == []


def test_unknown_ground_item_goes_to_the_report_too():
    context = ctx()
    migrate(raw_v5(ground=[ground("ghost_blade")]), context=context, current_version=6)
    assert any("ghost_blade" in line for line in context.report)


def test_each_unknown_id_is_reported():
    context = ctx()
    migrate(raw_v5([raw_hero(inventory=[entry("ghost_a"), entry("ghost_b")])]), context=context,
        current_version=6)
    text = "\n".join(context.report)
    assert "ghost_a" in text and "ghost_b" in text


def test_known_neighbour_of_an_unknown_id_keeps_its_price():
    data = raw_v5([raw_hero(inventory=[entry("ghost_relic"), entry("longsword")])])
    assert [e["cost_cp"] for e in inventory_of(migrate(data, context=ctx(),
        current_version=6))] == [0, 1500]


# предметы на земле

def test_ground_items_get_the_price():
    result = migrate(raw_v5(ground=[ground("scimitar", owner_ref="goblin_1")]), context=ctx(),
        current_version=6)
    item = result["session"]["active_combat"]["ground_items"][0]
    assert item["cost_cp"] == 2500
    assert (item["item_id"], item["owner_ref"], item["zone_id"]) == ("scimitar", "goblin_1", "hall")


def test_ground_item_cost_is_not_overwritten():
    result = migrate(raw_v5(ground=[ground("scimitar", cost_cp=9)]), context=ctx(),
        current_version=6)
    assert result["session"]["active_combat"]["ground_items"][0]["cost_cp"] == 9


def test_every_ground_item_gets_its_own_price():
    result = migrate(raw_v5(ground=[ground("longsword"), ground("scimitar")]), context=ctx(),
        current_version=6)
    items = result["session"]["active_combat"]["ground_items"]
    assert [i["cost_cp"] for i in items] == [1500, 2500]


def test_no_active_combat_stays_none():
    assert migrate(raw_v5(), context=ctx(), current_version=6)["session"]["active_combat"] is None


def test_other_fields_stay():
    data = raw_v5([raw_hero(inventory=[entry("longsword")])])
    before = copy.deepcopy(data)
    result = migrate(data, context=ctx(), current_version=6)
    assert result["session"] == before["session"]
    world = dict(result["world"])
    assert world.pop("custom_items") == {}
    assert world.pop("custom_item_seq") == 0
    assert world == before["world"]
    assert result["heroes"][0]["name"] == "Арн"


# фикстуры v5

def test_fixture_v5_is_v5_format_without_prices():
    manifest = json.loads((FIXTURE_V5 / "manifest.json").read_text(encoding="utf-8"))
    hero = json.loads(next((FIXTURE_V5 / "heroes").glob("*/hero.json")).read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 5
    assert len(hero["inventory"]) == 5
    assert all("cost_cp" not in e for e in hero["inventory"])


def test_fixture_v5_combat_has_unlooted_last_combat():
    session = json.loads((FIXTURE_V5_COMBAT / "session.json").read_text(encoding="utf-8"))
    assert session["last_combat"]["looted"] is False


def test_load_v5_returns_current_bundle(saves):
    install(saves, FIXTURE_V5)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.manifest.schema_version == CURRENT_SCHEMA_VERSION
    assert bundle.heroes[0].name == "Арн"


def test_load_v5_gives_srd_prices_from_the_registry(saves, registry):
    install(saves, FIXTURE_V5)
    hero = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS).heroes[0]
    prices = {e.item_id: e.cost_cp for e in hero.inventory}
    assert prices["longsword"] == registry.get("weapon", "longsword").cost_cp
    assert prices["scimitar"] == registry.get("weapon", "scimitar").cost_cp
    assert prices["potion_of_healing"] == registry.get("item", "potion_of_healing").cost_cp
    assert prices["shield"] == registry.get("armor", "shield").cost_cp


def test_load_v5_unknown_id_costs_zero(saves):
    install(saves, FIXTURE_V5)
    hero = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS).heroes[0]
    assert [e.cost_cp for e in hero.inventory if e.item_id == "ghost_relic"] == [0]


def test_load_v5_keeps_qty_quality_and_equipped(saves):
    install(saves, FIXTURE_V5)
    hero = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS).heroes[0]
    assert {e.item_id: e.qty for e in hero.inventory} == {
        "longsword": 1, "scimitar": 2, "potion_of_healing": 3, "shield": 1, "ghost_relic": 1,
    }
    assert {e.quality for e in hero.inventory} == {None}
    assert hero.equipped.main_hand == "longsword"


def test_load_v5_makes_byte_exact_backup(saves):
    install(saves, FIXTURE_V5)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    backup = saves / "old_world" / "backups" / f"auto-v5-{BACKUP_TS}"
    assert tree(backup) == tree(FIXTURE_V5)


def test_load_v5_combat_makes_byte_exact_backup(saves):
    install(saves, FIXTURE_V5_COMBAT)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    backup = saves / "old_world" / "backups" / f"auto-v5-{BACKUP_TS}"
    assert tree(backup) == tree(FIXTURE_V5_COMBAT)


def test_load_v5_rewrites_slot_as_v6_with_prices(saves):
    folder = install(saves, FIXTURE_V5)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    hero = json.loads(next((folder / "heroes").glob("*/hero.json")).read_text(encoding="utf-8"))
    assert manifest["schema_version"] == CURRENT_SCHEMA_VERSION
    assert all("cost_cp" in e for e in hero["inventory"])


def test_load_v5_twice_makes_no_second_backup(saves):
    install(saves, FIXTURE_V5)
    first = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    second = load_slot(saves, "old_world", "auto", backup_ts="20260202T000000Z")
    assert second == first
    assert len(list((saves / "old_world" / "backups").iterdir())) == 1


def test_resave_after_load_is_byte_stable(saves):
    folder = install(saves, FIXTURE_V5)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    migrated = tree(folder)
    save_slot(saves, bundle, "auto", saved_at=bundle.manifest.saved_at)
    assert tree(folder) == migrated


def test_load_v5_combat_keeps_last_combat(saves):
    install(saves, FIXTURE_V5_COMBAT)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.session.last_combat.defeated == ["goblin", "goblin"]


def test_v6_slot_is_too_new_for_engine_v5(saves):
    install(saves, FIXTURE_V5)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    with pytest.raises(SaveTooNew):
        load_slot(saves, "old_world", "auto", current_version=5)


def test_v6_save_and_load_round_trip(saves):
    install(saves, FIXTURE_V5)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    save_slot(saves, bundle, "manual-x", saved_at=SAVED_AT)
    again = load_slot(saves, "old_world", "manual-x", backup_ts=BACKUP_TS)
    assert again.heroes == bundle.heroes


# старые фикстуры проходят цепочку до v6

@pytest.mark.parametrize("name", ["v0", "v1", "v2", "v3", "v4"])
def test_old_fixture_chain_reaches_current_version(saves, name):
    install(saves, FIXTURES / name)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.manifest.schema_version == CURRENT_SCHEMA_VERSION


def test_v4_dragon_chain_reaches_current_version(saves):
    install(saves, FIXTURES / "v4_dragon", world_id="dd")
    bundle = load_slot(saves, "dd", "auto", backup_ts=BACKUP_TS)
    assert bundle.manifest.schema_version == CURRENT_SCHEMA_VERSION


def test_chain_from_v4_matches_load_from_v5(saves, tmp_path):
    # v5-фикстура собрана из v4-фикстуры: общие части сейва после цепочки совпадают
    install(saves, FIXTURE_V5)
    from_v5 = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    other = tmp_path / "other"
    install(other, FIXTURES / "v4")
    from_v4 = load_slot(other, "old_world", "auto", backup_ts=BACKUP_TS)
    assert from_v5.world == from_v4.world
    assert from_v5.memory == from_v4.memory


def test_load_v5_uses_the_given_context(saves):
    install(saves, FIXTURE_V5)
    context = ctx({"longsword": 42})
    hero = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS, context=context).heroes[0]
    assert {e.item_id: e.cost_cp for e in hero.inventory}["longsword"] == 42
    assert {e.item_id: e.cost_cp for e in hero.inventory}["scimitar"] == 0
    assert any("scimitar" in line for line in context.report)


def test_load_v5_with_srd_registry_reports_only_the_unknown_id(saves, registry):
    from ai_dm.persistence.migrations import MigrationContext as Context

    install(saves, FIXTURE_V5)
    context = Context.from_registry(registry)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS, context=context)
    assert len(context.report) == 1
    assert "ghost_relic" in context.report[0]


def test_entry_with_a_price_does_not_stop_the_next_ones():
    data = raw_v5([raw_hero(inventory=[entry("longsword", cost_cp=77), entry("scimitar")])])
    assert [e["cost_cp"] for e in inventory_of(migrate(data, context=ctx(),
        current_version=6))] == [77, 2500]


def test_dict_without_heroes_and_session_is_fine():
    data = {"manifest": {"schema_version": 5, "world_id": "w"}, "world": {}}
    assert migrate(data, context=ctx(), current_version=6)["manifest"]["schema_version"] == 6


def test_combat_without_ground_items_is_fine():
    data = raw_v5()
    data["session"]["active_combat"] = {"id": "c1"}
    assert migrate(data, context=ctx(),
        current_version=6)["session"]["active_combat"] == {"id": "c1"}


def test_hero_without_inventory_key_gets_none_added():
    data = raw_v5([{"id": "hero", "ordinal": 1, "name": "Арн"}])
    assert "cost_cp" not in json.dumps(migrate(data, context=ctx(), current_version=6)["heroes"])


def test_framework_does_not_mutate_the_input_dict():
    data = raw_v5([raw_hero(inventory=[entry("longsword")])], [ground("scimitar")])
    before = copy.deepcopy(data)
    migrate(data, context=ctx(), current_version=6)
    assert data == before


# контракт context (ревью партии 0)

def test_load_slot_without_context_for_v5_is_refused_and_files_stay(saves):
    from ai_dm.persistence import store

    folder = install(saves, FIXTURE_V5)
    with pytest.raises(MigrationContextRequired):
        store.load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert tree(folder) == tree(FIXTURE_V5)
    assert not (saves / "old_world" / "backups").exists()


def test_load_slot_without_context_is_fine_for_a_current_slot(saves):
    from ai_dm.persistence import store

    install(saves, FIXTURE_V5)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    bundle = store.load_slot(saves, "old_world", "auto")
    assert bundle.manifest.schema_version == CURRENT_SCHEMA_VERSION


def test_context_is_required_only_for_the_price_step_itself():
    # подменённая цепочка: на ключе 5 чужая функция -- context не нужен
    steps = {5: lambda data, context=None: data}
    assert migrate(raw_v5(), registry=steps, current_version=6)["manifest"]["schema_version"] == 6


def test_every_step_gets_the_context():
    seen = []

    def step(data, context=None):
        seen.append(context)
        return data

    given = ctx()
    migrate(raw_v5(), registry={5: step}, context=given, current_version=6)
    assert seen == [given]


def test_warning_names_the_unknown_ids():
    context = ctx()
    migrate(raw_v5([raw_hero(inventory=[entry("ghost_a"), entry("ghost_b")])]), context=context,
        current_version=6)
    text = context.warning()
    assert "ghost_a" in text and "ghost_b" in text


def test_peek_campaign_id_reads_the_manifest(saves):
    from ai_dm.persistence.store import peek_campaign_id

    install(saves, FIXTURES / "v4_dragon", world_id="dd")
    assert peek_campaign_id(saves, "dd", "auto") == "drunk_dragon"


def test_peek_campaign_id_recovers_an_interrupted_write(saves):
    from ai_dm.persistence.store import peek_campaign_id

    install(saves, FIXTURES / "v4_dragon", slot=".old-abc", world_id="dd")
    assert peek_campaign_id(saves, "dd", "auto") == "drunk_dragon"
    assert (saves / "dd" / "slots" / "auto" / "manifest.json").is_file()


def test_game_app_load_shows_the_migration_warning(registry, tmp_path):
    from game_kit import ReactiveAdapter, make_app, make_bundle

    bundle = make_bundle(registry)
    bundle.world.world_id = "old_world"
    bundle.manifest.world_id = "old_world"
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    install(tmp_path, FIXTURE_V5)
    lines = app.load("auto")
    assert any("ghost_relic" in line for line in lines)
