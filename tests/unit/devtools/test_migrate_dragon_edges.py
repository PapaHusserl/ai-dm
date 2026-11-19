# М0 П2 (docs/plan-m0.md, Приложение Б, решения 58, 66–68):
# scripts/migrate_dragon_edges.py <каталог мира|слота> -- одноразовая правка сейва drunk_dragon:
# 18 явных рёбер локациям без рёбер и четыре правки длины (строки А–Г).
# Имя скрипта и формат запуска — предположение доебы по образцу migrate_dusk_ferry.py
# (вопрос к папе/кабану). Тесты на синтетическом слоте во tmp_path (словарь-образец с локациями
# Приложения Б), запуск отдельным процессом.
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[3] / "scripts" / "migrate_dragon_edges.py"
WORLD_ID = "drunk_dragon-00000001"

# 18 новых рёбер сейва (Приложение Б, строки 1–15 без «п»): (откуда, куда, метры, род)
NEW_EDGES = [
    ("city_ratusha", "upper_city_ratusha_square", 100, "road"),
    ("grey_quarter", "sanctuary_of_dawn", 800, "road"),
    ("varen_manor", "grey_quarter", 300, "road"),
    ("olbrecht_manor", "grey_quarter", 300, "road"),
    ("shop_hunting_horn", "upper_city_square", 80, "road"),
    ("dry_heather", "sanctuary_of_dawn", 700, "road"),
    ("ash_forge", "east_shaft", 300, "mine"),
    ("ancient_tomb", "ash_forge", 500, "mine"),
    ("iron_ridge_foothills_villages", "iron_ridge_foothills", 3000, "road"),
    ("dead_pine_gorge", "watch_tower_outpost", 30400, "trail"),
    ("dead_pine_gorge", "ash_forge", 30400, "trail"),
    ("deep_shaft", "watch_tower_outpost", 43200, "mine"),
    ("deep_shaft", "ash_forge", 43200, "mine"),
    ("white_winds_ledge", "watch_tower_outpost", 42000, "offroad"),
    ("white_winds_ledge", "ash_forge", 42000, "offroad"),
    ("wolf_teeth_pass", "iron_ridge", 2000, "trail"),
    ("swamp_topkoe", "old_gat", 1500, "offroad"),
    ("devils_backwater", "swamp_topkoe", 2500, "offroad"),
]
ISOLATED = sorted({a for a, *_ in NEW_EDGES})
NEIGHBOURS = sorted({b for _, b, *_ in NEW_EDGES} - set(ISOLATED))


def edge(to, metres, kind="road"):
    return {"to": to, "distance_m": metres, "kind": kind, "needs_transport": False}


# рёбра, уже лежащие в сейве: четыре спорные строки и прочие (прочие не должны измениться)
UNTOUCHED = {
    "tavern_drunken_dragon": [edge("market", 120)],
    "market": [edge("tavern_drunken_dragon", 120), edge("old_tower", 700, "trail")],
    "old_tar_works": [edge("market", 900)],
    "dead_barrow": [edge("market", 1100, "offroad")],
    "city": [edge("market", 300)],
}
CHANGED = {
    "tavern_drunken_dragon": [edge("old_tower", 48270)],
    "old_tower": [edge("tavern_drunken_dragon", 3218)],
    "abbey_scarlet_mist": [edge("old_tar_works", 42680)],
    "viper_island": [edge("dead_barrow", 42680)],
    "iron_ridge": [edge("city", 1_080_000)],
}


def make_locations(skip=()):
    ids = set(ISOLATED) | set(NEIGHBOURS) | set(UNTOUCHED) | set(CHANGED) | {"old_tower", "market"}
    ids -= set(skip)
    connections = {}
    for source in (UNTOUCHED, CHANGED):
        for place_id, edges in source.items():
            connections.setdefault(place_id, []).extend(edges)
    return {
        place_id: {
            "id": place_id, "name": place_id, "connections": list(connections.get(place_id, [])),
        }
        for place_id in sorted(ids)
    }


def make_slot(root, skip=()):
    slot = root / "saves" / WORLD_ID / "slots" / "auto"
    (slot / "world").mkdir(parents=True)
    manifest = {
        "schema_version": 16, "engine_version": "0.1.0", "world_id": WORLD_ID,
        "campaign_id": "drunk_dragon", "slot": "auto", "saved_at": "2026-11-18T10:00:00+00:00",
        "current_hero_id": "hero", "heroes": ["hero"],
    }
    world = {
        "world_id": WORLD_ID, "campaign_id": "drunk_dragon", "clock": {"now_s": 1234},
        "flags": {"met": True}, "locations": make_locations(skip), "npcs": {},
    }
    (slot / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    (slot / "world" / "world.json").write_text(
        json.dumps(world, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (slot / "session.json").write_text('{"turn_seq": 7}', encoding="utf-8")
    return slot


def run(path):
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), str(path)], capture_output=True, text=True,
        encoding="utf-8", check=False,
    )


def world_of(slot):
    return json.loads((slot / "world" / "world.json").read_text(encoding="utf-8"))


def edges_of(slot, place_id):
    return world_of(slot)["locations"][place_id]["connections"]


def snapshot(root):
    return {p: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def edge_count(slot):
    return sum(len(p["connections"]) for p in world_of(slot)["locations"].values())


def test_script_exists():
    assert SCRIPT.is_file()


def test_apply_exits_zero(tmp_path):
    assert run(make_slot(tmp_path)).returncode == 0


@pytest.mark.parametrize(("a", "b", "metres", "kind"), NEW_EDGES)
def test_apply_adds_edge_from_appendix_b(tmp_path, a, b, metres, kind):
    slot = make_slot(tmp_path)
    run(slot)
    assert edge(b, metres, kind) in edges_of(slot, a)


def test_apply_adds_exactly_eighteen_edges_and_removes_one(tmp_path):
    slot = make_slot(tmp_path)
    before = edge_count(slot)
    run(slot)
    assert edge_count(slot) == before - 1 + 18


def test_apply_leaves_no_location_without_edges(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    locations = world_of(slot)["locations"]
    linked = {p for p, v in locations.items() if v["connections"]}
    linked |= {c["to"] for v in locations.values() for c in v["connections"]}
    assert [p for p in ISOLATED if p not in linked] == []


def test_row_a_drops_long_edge_and_keeps_short_one(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    assert edges_of(slot, "tavern_drunken_dragon") == [edge("market", 120)]
    assert edges_of(slot, "old_tower") == [edge("tavern_drunken_dragon", 3218)]


def test_row_b_abbey_to_tar_works_is_3200(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    assert edges_of(slot, "abbey_scarlet_mist") == [edge("old_tar_works", 3200)]


def test_row_c_viper_island_to_barrow_is_2000_trail(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    assert edges_of(slot, "viper_island") == [edge("dead_barrow", 2000, "trail")]


def test_row_d_iron_ridge_to_city_is_230400(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    assert edges_of(slot, "iron_ridge") == [edge("city", 230400)]


@pytest.mark.parametrize("place_id", sorted(UNTOUCHED))
def test_other_edges_are_not_touched(tmp_path, place_id):
    slot = make_slot(tmp_path)
    run(slot)
    assert edges_of(slot, place_id) == UNTOUCHED[place_id]


def test_apply_keeps_the_rest_of_world_json(tmp_path):
    slot = make_slot(tmp_path)
    before = world_of(slot)
    run(slot)
    after = world_of(slot)
    for doc in (before, after):
        del doc["locations"]
    assert after == before


def test_apply_does_not_touch_manifest_and_session(tmp_path):
    slot = make_slot(tmp_path)
    manifest = (slot / "manifest.json").read_bytes()
    session = (slot / "session.json").read_bytes()
    run(slot)
    assert (slot / "manifest.json").read_bytes() == manifest
    assert (slot / "session.json").read_bytes() == session


def test_apply_creates_backup_with_original_world(tmp_path):
    slot = make_slot(tmp_path)
    original = (slot / "world" / "world.json").read_bytes()
    run(slot)
    copies = [p for p in tmp_path.rglob("world.json") if p != slot / "world" / "world.json"]
    assert [p.read_bytes() for p in copies] == [original]


def test_second_run_changes_nothing(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    after_first = (slot / "world" / "world.json").read_bytes()
    second = run(slot)
    assert second.returncode == 0
    assert (slot / "world" / "world.json").read_bytes() == after_first


def test_second_run_makes_no_second_backup(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    run(slot)
    copies = [p for p in tmp_path.rglob("world.json") if p != slot / "world" / "world.json"]
    assert len(copies) == 1


@pytest.mark.parametrize("missing", ["east_shaft", "old_gat", "upper_city_square", "dead_barrow"])
def test_missing_neighbour_is_an_error_without_any_write(tmp_path, missing):
    slot = make_slot(tmp_path, skip=[missing])
    before = snapshot(tmp_path)
    result = run(slot)
    assert result.returncode != 0
    assert snapshot(tmp_path) == before
