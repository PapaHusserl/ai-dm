# BACKLOG 146 (docs/plan-ferry-npcs.md): scripts/migrate_dusk_ferry.py <каталог мира|слота> --
# одноразовая правка сейва dusk_academy: триггеру фракции mainland_ferry ставится срок now_s + DAYS,
# state=active, в notices кладётся слух накануне. stdlib, бэкап до записи, идемпотентность,
# отказ без записи на чужом мире / не той версии / до догрузки пака.
# Тесты на синтетическом слоте во tmp_path; запуск отдельным процессом. Последняя секция --
# сквозная: настоящий пак -> merge_new -> скрипт -> границы сцены (триггер, слух, видимость).
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[3] / "scripts" / "migrate_dusk_ferry.py"
WORLD_ID = "dusk_academy-d3de6c57"  # id мира зашит в скрипте; каталог -- синтетический, во tmp_path
NOW_S = 21348982
DAY = 86400
NPC_IDS = ["francis", "knox"]
RUMOR = "Ура, прибывает новый паром! Наверное привезет новых учеников!"


def ferry_faction(state="disabled", fired_count=0):
    return {
        "id": "mainland_ferry", "name": "Паром с материка", "members": NPC_IDS,
        "opportunity": [
            {
                "id": "arrival", "if_": {"type": "time_after", "seconds": 0},
                "then": "сошли francis и knox", "once": True, "state": state,
                "fired_count": fired_count,
            }
        ],
    }


def make_slot(
    root, *, version=9, world_id=WORLD_ID, faction=True, npcs=True, state="disabled",
    notices=None,
):
    slot = root / "saves" / world_id / "slots" / "auto"
    (slot / "world").mkdir(parents=True)
    manifest = {
        "schema_version": version, "engine_version": "0.1.0", "world_id": world_id,
        "campaign_id": "dusk_academy", "slot": "auto", "saved_at": "2026-10-15T15:38:18+00:00",
        "current_hero_id": "hero", "heroes": ["hero"],
    }
    world = {
        "world_id": world_id, "campaign_id": "dusk_academy", "campaign_version": "2",
        "clock": {"now_s": NOW_S}, "flags": {"met_maya": True},
        "factions": {"mainland_ferry": ferry_faction(state)} if faction else {},
        "npcs": {"maya": {"name": "Майя"}},
        "notices": notices if notices is not None else [],
    }
    if npcs:
        for npc_id in NPC_IDS:
            world["npcs"][npc_id] = {"name": npc_id, "location_id": None}
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


def trigger_of(slot):
    return world_of(slot)["factions"]["mainland_ferry"]["opportunity"][0]


def snapshot(root):
    return {p: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def backups(root, slot):
    original = slot / "world" / "world.json"
    return [p for p in root.rglob("world.json") if p != original]


# применение

def test_script_exists():
    assert SCRIPT.is_file()


def test_apply_exits_zero(tmp_path):
    assert run(make_slot(tmp_path)).returncode == 0


def test_apply_prints_done_with_backup_path(tmp_path):
    result = run(make_slot(tmp_path))
    assert result.stdout.startswith("Готово. Бэкап слота: ")


@pytest.mark.parametrize("version", [9, 12])
def test_apply_sets_trigger_seconds_to_now_plus_days(tmp_path, version):
    slot = make_slot(tmp_path, version=version)
    run(slot)
    assert trigger_of(slot)["if_"]["seconds"] == NOW_S + DAY


@pytest.mark.parametrize("version", [9, 12])
def test_apply_activates_trigger(tmp_path, version):
    slot = make_slot(tmp_path, version=version)
    run(slot)
    assert trigger_of(slot)["state"] == "active"


def test_apply_keeps_condition_type(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    assert trigger_of(slot)["if_"]["type"] == "time_after"


def test_apply_adds_one_rumor_notice(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    notices = world_of(slot)["notices"]
    assert len(notices) == 1
    assert notices[0]["visibility"] == "rumor"
    assert notices[0]["text"] == RUMOR


def test_rumor_is_delivered_one_day_before_ferry(tmp_path):
    # DAYS=1, RUMOR_BEFORE_DAYS=1: слух сразу доставим (deliver_at_s == now_s)
    slot = make_slot(tmp_path)
    run(slot)
    notice = world_of(slot)["notices"][0]
    assert notice["deliver_at_s"] == NOW_S
    assert notice["at_s"] == NOW_S


def test_rumor_refs_are_new_npcs(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    assert world_of(slot)["notices"][0]["refs"] == NPC_IDS


def test_apply_keeps_existing_notices(tmp_path):
    old = {
        "id": "n0", "at_s": 5, "deliver_at_s": 6, "visibility": "rumor", "text": "старое",
        "refs": [],
    }
    slot = make_slot(tmp_path, notices=[old])
    run(slot)
    notices = world_of(slot)["notices"]
    assert notices[0] == old
    assert len(notices) == 2


def test_apply_keeps_the_rest_of_world_json(tmp_path):
    slot = make_slot(tmp_path)
    before = world_of(slot)
    run(slot)
    after = world_of(slot)
    for doc in (before, after):
        del doc["notices"]
        del doc["factions"]["mainland_ferry"]["opportunity"][0]["state"]
        del doc["factions"]["mainland_ferry"]["opportunity"][0]["if_"]["seconds"]
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
    found = backups(tmp_path, slot)
    assert len(found) == 1
    assert found[0].read_bytes() == original


def test_backup_is_named_backup_ferry(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    found = backups(tmp_path, slot)
    assert found[0].parents[2].name.startswith("backup-ferry-")


def test_apply_leaves_no_tmp_file(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    assert not list(tmp_path.rglob("*.tmp"))


def test_apply_does_not_create_files_outside_the_world_dir(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    world_dir = tmp_path / "saves" / WORLD_ID
    extra = [p for p in tmp_path.rglob("*") if p.is_file() and world_dir not in p.parents]
    assert extra == []


def test_world_dir_argument_edits_auto_slot(tmp_path):
    slot = make_slot(tmp_path)
    result = run(tmp_path / "saves" / WORLD_ID)
    assert result.returncode == 0
    assert trigger_of(slot)["state"] == "active"


def test_no_argument_exits_two(tmp_path):
    result = subprocess.run(
        [sys.executable, "-I", str(SCRIPT)], capture_output=True, text=True, encoding="utf-8",
        check=False,
    )
    assert result.returncode == 2


# отказ без записи

def refused(tmp_path, **kwargs):
    slot = make_slot(tmp_path, **kwargs)
    before = snapshot(tmp_path)
    result = run(slot)
    assert snapshot(tmp_path) == before
    return result


def test_other_world_is_refused(tmp_path):
    result = refused(tmp_path, world_id="other_world-1")
    assert result.returncode == 1
    assert "Отказ" in result.stdout


def test_version_8_is_refused(tmp_path):
    result = refused(tmp_path, version=8)
    assert result.returncode == 1
    assert "Отказ" in result.stdout


def test_version_15_is_refused(tmp_path):
    assert refused(tmp_path, version=15).returncode == 1


def test_missing_faction_is_refused_with_hint(tmp_path):
    result = refused(tmp_path, faction=False)
    assert result.returncode == 1
    assert "запустите игру" in result.stdout


def test_missing_npcs_are_refused_with_hint(tmp_path):
    result = refused(tmp_path, npcs=False)
    assert result.returncode == 1
    assert "запустите игру" in result.stdout


def test_missing_manifest_is_refused(tmp_path):
    (tmp_path / "empty").mkdir()
    result = run(tmp_path / "empty")
    assert result.returncode == 1
    assert "Отказ" in result.stdout


# идемпотентность

def test_second_run_says_already_applied(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    result = run(slot)
    assert result.returncode == 0
    assert "Уже применено" in result.stdout


def test_second_run_changes_nothing(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    before = snapshot(tmp_path)
    run(slot)
    assert snapshot(tmp_path) == before


def test_second_run_makes_no_second_backup(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    run(slot)
    assert len(backups(tmp_path, slot)) == 1


def test_fired_trigger_means_already_applied(tmp_path):
    slot = make_slot(tmp_path, state="fired")
    before = snapshot(tmp_path)
    result = run(slot)
    assert result.returncode == 0
    assert "Уже применено" in result.stdout
    assert snapshot(tmp_path) == before


def test_active_trigger_means_already_applied(tmp_path):
    slot = make_slot(tmp_path, state="active")
    before = snapshot(tmp_path)
    assert "Уже применено" in run(slot).stdout
    assert snapshot(tmp_path) == before


# пак: фракция и NPC

DUSK_DIR = Path(__file__).parents[3] / "campaigns" / "dusk_academy"


def dusk_pack(registry):
    from ai_dm.campaign.loader import load_pack, pack_content_dir
    from ai_dm.content.loader import load_registry

    content = pack_content_dir(DUSK_DIR)
    return load_pack(DUSK_DIR, load_registry([content] if content is not None else []))


def test_pack_version_is_at_least_two(registry):
    # паром пришёл с версией 2; версия пака растёт
    assert int(dusk_pack(registry).manifest.version) >= 2


def test_pack_has_ferry_faction_with_members(registry):
    faction = next(f for f in dusk_pack(registry).factions if f.id == "mainland_ferry")
    assert faction.members == NPC_IDS


def test_pack_ferry_trigger_is_sleeping(registry):
    faction = next(f for f in dusk_pack(registry).factions if f.id == "mainland_ferry")
    assert len(faction.opportunity) == 1
    trigger = faction.opportunity[0]
    assert trigger.id == "arrival"
    assert trigger.state == "disabled"
    assert trigger.once is True


def test_pack_ferry_then_names_both_npcs_and_academy(registry):
    faction = next(f for f in dusk_pack(registry).factions if f.id == "mainland_ferry")
    then = faction.opportunity[0].then
    assert "francis" in then
    assert "knox" in then
    assert "academy" in then


@pytest.mark.parametrize("npc_id", NPC_IDS)
def test_pack_new_npc_is_homeless_named_not_key(registry, npc_id):
    npc = next(n for n in dusk_pack(registry).npcs if n.id == npc_id)
    assert npc.location_id is None
    assert npc.named is True
    assert npc.key is False
    assert npc.means
    assert "паромом" in npc.notes


def test_pack_knox_name_is_knox_velar(registry):
    npc = next(n for n in dusk_pack(registry).npcs if n.id == "knox")
    assert npc.name == "Нокс Велар"


def test_pack_ferry_destination_exists_in_pack(registry):
    pack = dusk_pack(registry)
    assert "academy" in {loc.id for loc in pack.locations}


# сквозное: пак -> догрузка -> скрипт -> границы сцены

def ferry_bundle(registry, tmp_path):
    # старый мир без парома + догрузка настоящего пака; героя берём из мини-бандла
    from protocol_kit import make_bundle

    from ai_dm.campaign.merge import merge_new

    bundle = make_bundle(registry)
    world = bundle.world
    world.world_id = WORLD_ID
    bundle.manifest.world_id = WORLD_ID
    pack = dusk_pack(registry)
    report = merge_new(bundle, pack)
    return bundle, report


def test_merge_new_adds_ferry_faction_and_homeless_npcs(registry, tmp_path):
    bundle, report = ferry_bundle(registry, tmp_path)
    assert "faction:mainland_ferry" in report.added
    assert "npc:francis" in report.added
    assert "npc:knox" in report.added
    assert bundle.world.npcs["francis"].location_id is None
    assert bundle.world.npcs["knox"].location_id is None


def test_merge_new_keeps_trigger_disabled(registry, tmp_path):
    bundle, _ = ferry_bundle(registry, tmp_path)
    trigger = bundle.world.factions["mainland_ferry"].opportunity[0]
    assert trigger.state == "disabled"


def test_second_merge_new_adds_nothing(registry, tmp_path):
    from ai_dm.campaign.merge import merge_new

    bundle, _ = ferry_bundle(registry, tmp_path)
    again = merge_new(bundle, dusk_pack(registry))
    assert [a for a in again.added if a.startswith(("npc:", "faction:"))] == []


def test_sleeping_ferry_npcs_are_invisible_to_world_role(registry, tmp_path):
    from ai_dm.master.relevance import relevant_npcs

    bundle, _ = ferry_bundle(registry, tmp_path)
    found = relevant_npcs(bundle)
    assert "francis" not in found
    assert "knox" not in found


def test_disabled_trigger_is_never_ready():
    from ai_dm.rules.triggers_eval import is_ready
    from ai_dm.state.world import Trigger

    trigger = Trigger.model_validate(
        {"id": "t", "if": {"type": "time_after", "seconds": 0}, "then": "x", "state": "disabled"}
    )
    assert is_ready(trigger, 10**9) is False


def migrated_bundle(registry, cfg, tmp_path):
    # пишем слот, гоняем скрипт процессом, читаем обратно движком
    from ai_dm.persistence.store import load_slot, save_slot

    bundle, _ = ferry_bundle(registry, tmp_path)
    bundle.world.clock.now_s = NOW_S
    save_slot(tmp_path / "saves", bundle, "auto", saved_at="2026-10-15T15:38:18+00:00")
    result = run(tmp_path / "saves" / WORLD_ID)
    assert result.returncode == 0, result.stdout
    return load_slot(tmp_path / "saves", WORLD_ID, "auto")


def boundary(bundle, cfg, registry):
    import ai_dm.game.boundary as boundary_mod

    boundary_mod.close_boundary(bundle, cfg, "end_scene")
    return boundary_mod.finish_boundary(bundle, cfg, registry)


def test_script_output_loads_into_engine(registry, cfg, tmp_path):
    loaded = migrated_bundle(registry, cfg, tmp_path)
    trigger = loaded.world.factions["mainland_ferry"].opportunity[0]
    assert trigger.state == "active"
    assert trigger.if_.seconds == NOW_S + DAY


def test_ferry_does_not_fire_before_term(registry, cfg, tmp_path):
    loaded = migrated_bundle(registry, cfg, tmp_path)
    loaded.world.clock.now_s = NOW_S + DAY - 1
    result = boundary(loaded, cfg, registry)
    assert result.error is None
    assert result.bundle.world.factions["mainland_ferry"].opportunity[0].fired_count == 0


def test_ferry_fires_on_boundary_at_term(registry, cfg, tmp_path):
    loaded = migrated_bundle(registry, cfg, tmp_path)
    loaded.world.clock.now_s = NOW_S + DAY
    result = boundary(loaded, cfg, registry)
    assert result.error is None
    trigger = result.bundle.world.factions["mainland_ferry"].opportunity[0]
    assert trigger.fired_count == 1
    assert trigger.state == "fired"


def test_ferry_trigger_yields_act_candidate_with_then(registry, cfg, tmp_path):
    from ai_dm.world_sim import triggers

    loaded = migrated_bundle(registry, cfg, tmp_path)
    loaded.world.clock.now_s = NOW_S + DAY
    check = triggers.check(loaded, cfg)
    found = [c for c in check.candidates if c.ref == "trigger:mainland_ferry:arrival"]
    assert len(found) == 1
    assert found[0].kind == "act"
    assert "francis" in found[0].then


def test_ferry_does_not_fire_twice(registry, cfg, tmp_path):
    loaded = migrated_bundle(registry, cfg, tmp_path)
    loaded.world.clock.now_s = NOW_S + DAY
    first = boundary(loaded, cfg, registry)
    first.bundle.world.clock.now_s = NOW_S + 3 * DAY
    second = boundary(first.bundle, cfg, registry)
    assert second.bundle.world.factions["mainland_ferry"].opportunity[0].fired_count == 1


def test_rumor_is_delivered_on_first_boundary(registry, cfg, tmp_path):
    loaded = migrated_bundle(registry, cfg, tmp_path)
    result = boundary(loaded, cfg, registry)
    assert RUMOR in result.notices


def test_rumor_is_removed_from_world_after_delivery(registry, cfg, tmp_path):
    loaded = migrated_bundle(registry, cfg, tmp_path)
    result = boundary(loaded, cfg, registry)
    assert [n for n in result.bundle.world.notices if n.text == RUMOR] == []


def test_rumor_is_delivered_only_once(registry, cfg, tmp_path):
    loaded = migrated_bundle(registry, cfg, tmp_path)
    first = boundary(loaded, cfg, registry)
    second = boundary(first.bundle, cfg, registry)
    assert RUMOR not in second.notices


def test_rumor_with_later_deliver_at_waits_for_its_time(registry, cfg, tmp_path):
    # слух с deliver_at_s в будущем (DAYS > RUMOR_BEFORE_DAYS) не доставляется раньше срока
    loaded = migrated_bundle(registry, cfg, tmp_path)
    loaded.world.notices[0].deliver_at_s = NOW_S + DAY
    early = boundary(loaded, cfg, registry)
    assert RUMOR not in early.notices
    early.bundle.world.clock.now_s = NOW_S + DAY
    late = boundary(early.bundle, cfg, registry)
    assert RUMOR in late.notices
