# scripts/fix_dusk_ships.py <каталог мира|слота> -- правка сейва dusk_academy: шхуна «Бродячая Луна»
# переезжает к ferry_pier, фрегат «Северный барс» получает обратную связь от причала.
# Тесты на синтетическом мире во tmp_path, запуск отдельным процессом.
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[3] / "scripts" / "fix_dusk_ships.py"
WORLD_ID = "dusk_academy-d3de6c57"
SLOTS = ["auto", "auto-1", "manual-quick"]


def edge(to, metres, **extra):
    return {"to": to, "distance_m": metres, **extra}


def make_locations():
    spec = {
        "wandering_moon_deck": ("white_lily_mansion", [edge("white_lily_mansion", 500)]),
        "white_lily_mansion": (
            "court_expert_room",
            [edge("court_expert_room", 400), edge("wandering_moon_deck", 500)],
        ),
        "ferry_pier": ("misty_haven", [edge("misty_haven", 300)]),
        "frigate_deck": ("nord_harbor_docks", [edge("nord_harbor_docks", 20)]),
        "nord_harbor_docks": (
            "upper_market",
            [edge("upper_market", 450, kind="road", needs_transport=False)],
        ),
        "court_expert_room": ("frigate_deck", [edge("frigate_deck", 20), edge("misty_haven", 5)]),
        "misty_haven": (None, []),
        "upper_market": (None, []),
    }
    return {
        pid: {"id": pid, "parent_id": parent, "connections": conns}
        for pid, (parent, conns) in spec.items()
    }


def make_world(root, slots=SLOTS, locations=None, world_id=WORLD_ID):
    world_dir = root / "saves" / world_id
    for name in slots:
        slot = world_dir / "slots" / name
        (slot / "world").mkdir(parents=True)
        manifest = {"schema_version": 14, "world_id": world_id, "slot": name}
        (slot / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        found = locations or make_locations()
        world = {"world_id": world_id, "flags": {"a": 1}, "locations": found}
        (slot / "world" / "world.json").write_text(
            json.dumps(world, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return world_dir


def run(path, *flags):
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), *flags, str(path)], capture_output=True, text=True,
        encoding="utf-8", check=False,
    )


def locs(world_dir, slot="auto"):
    path = world_dir / "slots" / slot / "world" / "world.json"
    return json.loads(path.read_text(encoding="utf-8"))["locations"]


def targets(world_dir, place_id, slot="auto"):
    return [c["to"] for c in locs(world_dir, slot)[place_id]["connections"]]


def snapshot(root):
    return {p: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_moon_moves_to_ferry_pier(tmp_path):
    world = make_world(tmp_path)
    assert run(world).returncode == 0
    assert locs(world)["wandering_moon_deck"]["parent_id"] == "ferry_pier"


def test_moon_linked_to_pier_both_ways_20m(tmp_path):
    world = make_world(tmp_path)
    run(world)
    found = locs(world)
    assert edge("ferry_pier", 20) in found["wandering_moon_deck"]["connections"]
    assert edge("wandering_moon_deck", 20) in found["ferry_pier"]["connections"]


def test_moon_unlinked_from_mansion_both_ways(tmp_path):
    world = make_world(tmp_path)
    run(world)
    assert "white_lily_mansion" not in targets(world, "wandering_moon_deck")
    assert "wandering_moon_deck" not in targets(world, "white_lily_mansion")
    assert "court_expert_room" in targets(world, "white_lily_mansion")


def test_frigate_gets_return_edge_and_loses_court_edge(tmp_path):
    world = make_world(tmp_path)
    run(world)
    assert "frigate_deck" in targets(world, "nord_harbor_docks")
    assert targets(world, "court_expert_room") == ["misty_haven"]
    assert targets(world, "frigate_deck") == ["nord_harbor_docks"]


def test_new_edge_has_only_to_and_distance(tmp_path):
    world = make_world(tmp_path)
    run(world)
    added = next(c for c in locs(world)["nord_harbor_docks"]["connections"]
                 if c["to"] == "frigate_deck")
    assert added == edge("frigate_deck", 20)


def test_existing_edge_fields_are_not_lost(tmp_path):
    found = make_locations()
    found["frigate_deck"]["connections"] = [edge("nord_harbor_docks", 20, kind="dock")]
    found["court_expert_room"]["connections"] = [edge("frigate_deck", 20, kind="dock")]
    world = make_world(tmp_path, locations=found)
    run(world)
    kept = locs(world)["frigate_deck"]["connections"]
    assert kept == [edge("nord_harbor_docks", 20, kind="dock")]


def test_all_slots_are_fixed(tmp_path):
    world = make_world(tmp_path)
    run(world)
    for slot in SLOTS:
        assert locs(world, slot)["wandering_moon_deck"]["parent_id"] == "ferry_pier"


def test_slot_path_fixes_only_that_slot(tmp_path):
    world = make_world(tmp_path)
    assert run(world / "slots" / "auto").returncode == 0
    assert locs(world, "auto")["wandering_moon_deck"]["parent_id"] == "ferry_pier"
    assert locs(world, "auto-1")["wandering_moon_deck"]["parent_id"] == "white_lily_mansion"


def test_rest_of_world_json_is_kept(tmp_path):
    world = make_world(tmp_path)
    run(world)
    doc = json.loads((world / "slots" / "auto" / "world" / "world.json").read_text("utf-8"))
    assert doc["flags"] == {"a": 1}
    assert locs(world)["misty_haven"] == make_locations()["misty_haven"]


def test_backup_holds_original_world(tmp_path):
    world = make_world(tmp_path)
    original = (world / "slots" / "auto" / "world" / "world.json").read_bytes()
    run(world)
    copies = [p for p in world.glob("backup-ships-*/auto/world/world.json")]
    assert [p.read_bytes() for p in copies] == [original]


def test_second_run_changes_nothing_and_makes_no_backup(tmp_path):
    world = make_world(tmp_path)
    run(world)
    after_first = snapshot(tmp_path)
    second = run(world)
    assert second.returncode == 0
    assert snapshot(tmp_path) == after_first


def test_partially_applied_state_is_completed_without_duplicates(tmp_path):
    found = make_locations()
    found["nord_harbor_docks"]["connections"].append(edge("frigate_deck", 20))
    found["court_expert_room"]["connections"] = [edge("misty_haven", 5)]
    world = make_world(tmp_path, locations=found)
    run(world)
    assert targets(world, "nord_harbor_docks").count("frigate_deck") == 1
    assert locs(world)["wandering_moon_deck"]["parent_id"] == "ferry_pier"


def test_missing_location_is_skipped_with_message(tmp_path):
    found = make_locations()
    del found["wandering_moon_deck"]
    world = make_world(tmp_path, locations=found)
    result = run(world)
    assert result.returncode == 0
    assert "wandering_moon_deck" in result.stdout
    assert "frigate_deck" in targets(world, "nord_harbor_docks")
    assert "wandering_moon_deck" not in targets(world, "white_lily_mansion")


def test_dry_run_writes_nothing_and_reports(tmp_path):
    world = make_world(tmp_path)
    before = snapshot(tmp_path)
    result = run(world, "--dry-run")
    assert result.returncode == 0
    assert "parent_id wandering_moon_deck -> ferry_pier" in result.stdout
    assert snapshot(tmp_path) == before


def test_foreign_world_is_an_error_without_any_write(tmp_path):
    world = make_world(tmp_path, world_id="other_world-00000001")
    before = snapshot(tmp_path)
    assert run(world).returncode != 0
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("args", [[], ["a", "b"]])
def test_wrong_arguments_give_usage(args):
    result = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), *args], capture_output=True, text=True,
        encoding="utf-8", check=False,
    )
    assert result.returncode == 2
