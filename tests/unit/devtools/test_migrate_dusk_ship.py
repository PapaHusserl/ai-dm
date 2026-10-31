# scripts/migrate_dusk_ship.py <каталог мира|слота> -- одноразовая правка сейва dusk_academy:
# триггеру фракции wandering_moon_crew ставится срок now_s + DAYS, state=active, в notices кладётся
# слух накануне, Ноксу дописывается ревность в notes. stdlib, бэкап до записи, идемпотентность,
# отказ без записи на чужом мире / не той версии / до догрузки пака.
# Тесты на синтетическом слоте во tmp_path; запуск отдельным процессом. Вторая половина -- пак v5
# и сквозная секция на настоящем паке: merge_new -> скрипт -> границы сцены.
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[3] / "scripts" / "migrate_dusk_ship.py"
WORLD_ID = "dusk_academy-d3de6c57"  # id мира зашит в скрипте; каталог -- синтетический, во tmp_path
NOW_S = 22700000
DAY = 86400
NPC_IDS = ["killian", "zimmer", "kurt", "leo", "henry", "orlando"]
RUMOR = "В гавани видели паруса «Бродячей Луны»: вольное судно идёт к Паромному пирсу."
OLD_KNOX_NOTES = "Нокс любит героиню и хочет сделать ей предложение."


def ship_faction(state="disabled", fired_count=0):
    return {
        "id": "wandering_moon_crew", "name": "Команда «Бродячей Луны»", "members": NPC_IDS,
        "opportunity": [
            {
                "id": "arrival", "if_": {"type": "time_after", "seconds": 0},
                "then": "пришла «Бродячая Луна»", "once": True, "state": state,
                "fired_count": fired_count,
            }
        ],
    }


def make_slot(
    root, *, version=9, world_id=WORLD_ID, faction=True, npcs=True, knox=True, state="disabled",
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
        "world_id": world_id, "campaign_id": "dusk_academy", "campaign_version": "4",
        "clock": {"now_s": NOW_S}, "flags": {"met_maya": True},
        "factions": {"wandering_moon_crew": ship_faction(state)} if faction else {},
        "npcs": {"maya": {"name": "Майя"}},
        "notices": notices if notices is not None else [],
    }
    if npcs:
        for npc_id in NPC_IDS:
            world["npcs"][npc_id] = {"name": npc_id, "location_id": None}
    if knox:
        world["npcs"]["knox"] = {"name": "Нокс Велар", "notes": OLD_KNOX_NOTES, "attitude": 80}
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
    return world_of(slot)["factions"]["wandering_moon_crew"]["opportunity"][0]


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
def test_apply_sets_trigger_seconds_to_now_plus_one_day(tmp_path, version):
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


def test_rumor_is_delivered_at_once_day_before_arrival(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    notice = world_of(slot)["notices"][0]
    assert notice["deliver_at_s"] == NOW_S
    assert notice["at_s"] == NOW_S


def test_rumor_refs_are_crew(tmp_path):
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


def test_apply_appends_jealousy_to_knox_notes(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    notes = world_of(slot)["npcs"]["knox"]["notes"]
    assert notes.startswith(OLD_KNOX_NOTES + "\n\nРевность к приятелям")
    assert "спокойно" in notes
    assert "без срывов и ссор" in notes


def test_apply_keeps_knox_other_fields(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    knox = world_of(slot)["npcs"]["knox"]
    assert knox["name"] == "Нокс Велар"
    assert knox["attitude"] == 80


def test_apply_keeps_the_rest_of_world_json(tmp_path):
    slot = make_slot(tmp_path)
    before = world_of(slot)
    run(slot)
    after = world_of(slot)
    for doc in (before, after):
        del doc["notices"]
        del doc["npcs"]["knox"]["notes"]
        del doc["factions"]["wandering_moon_crew"]["opportunity"][0]["state"]
        del doc["factions"]["wandering_moon_crew"]["opportunity"][0]["if_"]["seconds"]
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


def test_backup_is_named_backup_ship(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    found = backups(tmp_path, slot)
    assert found[0].parents[2].name.startswith("backup-ship-")


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


def test_missing_crew_is_refused_with_hint(tmp_path):
    result = refused(tmp_path, npcs=False)
    assert result.returncode == 1
    assert "запустите игру" in result.stdout


def test_missing_knox_is_refused_with_hint(tmp_path):
    result = refused(tmp_path, knox=False)
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


def test_second_run_does_not_duplicate_jealousy(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    run(slot)
    assert world_of(slot)["npcs"]["knox"]["notes"].count("Ревность к приятелям") == 1


@pytest.mark.parametrize("state", ["fired", "active"])
def test_started_trigger_means_already_applied(tmp_path, state):
    slot = make_slot(tmp_path, state=state)
    before = snapshot(tmp_path)
    result = run(slot)
    assert result.returncode == 0
    assert "Уже применено" in result.stdout
    assert snapshot(tmp_path) == before


# пак: фракция и NPC

DUSK_DIR = Path(__file__).parents[3] / "campaigns" / "dusk_academy"


def dusk_pack(registry):
    from ai_dm.campaign.loader import load_pack, pack_content_dir
    from ai_dm.content.loader import load_registry

    content = pack_content_dir(DUSK_DIR)
    return load_pack(DUSK_DIR, load_registry([content] if content is not None else []))


def test_pack_version_is_five(registry):
    assert dusk_pack(registry).manifest.version == "5"


def test_pack_has_crew_faction_with_members(registry):
    faction = next(f for f in dusk_pack(registry).factions if f.id == "wandering_moon_crew")
    assert faction.members == NPC_IDS


def test_pack_crew_trigger_is_sleeping(registry):
    faction = next(f for f in dusk_pack(registry).factions if f.id == "wandering_moon_crew")
    assert len(faction.opportunity) == 1
    trigger = faction.opportunity[0]
    assert trigger.id == "arrival"
    assert trigger.state == "disabled"
    assert trigger.once is True


def test_pack_crew_then_names_everyone_and_pier(registry):
    faction = next(f for f in dusk_pack(registry).factions if f.id == "wandering_moon_crew")
    then = faction.opportunity[0].then
    for npc_id in NPC_IDS:
        assert npc_id in then
    assert "ferry_pier" in then


def test_pack_crew_destination_exists_in_pack(registry):
    assert "ferry_pier" in {loc.id for loc in dusk_pack(registry).locations}


@pytest.mark.parametrize("npc_id", NPC_IDS)
def test_pack_crew_npc_is_homeless_named_not_key(registry, npc_id):
    npc = next(n for n in dusk_pack(registry).npcs if n.id == npc_id)
    assert npc.location_id is None
    assert npc.named is True
    assert npc.key is False
    assert npc.gender == "male"
    assert npc.means
    assert "Нокса" in npc.notes
    assert "Мир" in npc.notes


def test_pack_henry_is_halfling_from_heroine_village(registry):
    npc = next(n for n in dusk_pack(registry).npcs if n.id == "henry")
    assert "полурослик" in npc.notes.casefold()
    assert "родной деревни" in npc.notes
    assert "около 20 лет" in npc.notes


def test_pack_orlando_is_gnome_cook_who_only_lightly_flirts_with_mira(registry):
    npc = next(n for n in dusk_pack(registry).npcs if n.id == "orlando")
    assert "гном" in npc.notes
    assert "коком" in npc.notes
    assert "совсем чуть-чуть" in npc.notes
    assert "помогает ей по хозяйству" in npc.notes
    assert "по-приятельски" in npc.notes


# сквозное: пак -> догрузка -> скрипт -> границы сцены

def ship_bundle(registry):
    # старый мир без корабля + догрузка настоящего пака; героя берём из мини-бандла
    from protocol_kit import make_bundle

    from ai_dm.campaign.merge import merge_new

    bundle = make_bundle(registry)
    bundle.world.world_id = WORLD_ID
    bundle.manifest.world_id = WORLD_ID
    report = merge_new(bundle, dusk_pack(registry))
    return bundle, report


def test_merge_new_adds_crew_faction_and_homeless_npcs(registry):
    bundle, report = ship_bundle(registry)
    assert "faction:wandering_moon_crew" in report.added
    for npc_id in NPC_IDS:
        assert f"npc:{npc_id}" in report.added
        assert bundle.world.npcs[npc_id].location_id is None


def test_merge_new_keeps_trigger_disabled(registry):
    bundle, _ = ship_bundle(registry)
    assert bundle.world.factions["wandering_moon_crew"].opportunity[0].state == "disabled"


def test_second_merge_new_adds_nothing(registry):
    from ai_dm.campaign.merge import merge_new

    bundle, _ = ship_bundle(registry)
    again = merge_new(bundle, dusk_pack(registry))
    assert [a for a in again.added if a.startswith(("npc:", "faction:"))] == []


def test_sleeping_crew_is_invisible_to_world_role(registry):
    from ai_dm.master.relevance import relevant_npcs

    bundle, _ = ship_bundle(registry)
    found = relevant_npcs(bundle)
    for npc_id in NPC_IDS:
        assert npc_id not in found


def migrated_bundle(registry, tmp_path):
    # пишем слот, гоняем скрипт процессом, читаем обратно движком
    from ai_dm.persistence.store import load_slot, save_slot

    bundle, _ = ship_bundle(registry)
    bundle.world.clock.now_s = NOW_S
    save_slot(tmp_path / "saves", bundle, "auto", saved_at="2026-10-15T15:38:18+00:00")
    result = run(tmp_path / "saves" / WORLD_ID)
    assert result.returncode == 0, result.stdout
    return load_slot(tmp_path / "saves", WORLD_ID, "auto")


def boundary(bundle, cfg, registry):
    import ai_dm.game.boundary as boundary_mod

    boundary_mod.close_boundary(bundle, cfg, "end_scene")
    return boundary_mod.finish_boundary(bundle, cfg, registry)


def test_script_output_loads_into_engine(registry, tmp_path):
    loaded = migrated_bundle(registry, tmp_path)
    trigger = loaded.world.factions["wandering_moon_crew"].opportunity[0]
    assert trigger.state == "active"
    assert trigger.if_.seconds == NOW_S + DAY
    assert "Ревность к приятелям" in loaded.world.npcs["knox"].notes


def test_ship_does_not_fire_before_term(registry, cfg, tmp_path):
    loaded = migrated_bundle(registry, tmp_path)
    loaded.world.clock.now_s = NOW_S + DAY - 1
    result = boundary(loaded, cfg, registry)
    assert result.error is None
    assert result.bundle.world.factions["wandering_moon_crew"].opportunity[0].fired_count == 0


def test_ship_fires_on_boundary_at_term(registry, cfg, tmp_path):
    loaded = migrated_bundle(registry, tmp_path)
    loaded.world.clock.now_s = NOW_S + DAY
    result = boundary(loaded, cfg, registry)
    assert result.error is None
    trigger = result.bundle.world.factions["wandering_moon_crew"].opportunity[0]
    assert trigger.fired_count == 1
    assert trigger.state == "fired"


def test_ship_trigger_yields_act_candidate_with_then(registry, cfg, tmp_path):
    from ai_dm.world_sim import triggers

    loaded = migrated_bundle(registry, tmp_path)
    loaded.world.clock.now_s = NOW_S + DAY
    check = triggers.check(loaded, cfg)
    found = [c for c in check.candidates if c.ref == "trigger:wandering_moon_crew:arrival"]
    assert len(found) == 1
    assert found[0].kind == "act"
    assert "killian" in found[0].then


def test_ship_does_not_fire_twice(registry, cfg, tmp_path):
    loaded = migrated_bundle(registry, tmp_path)
    loaded.world.clock.now_s = NOW_S + DAY
    first = boundary(loaded, cfg, registry)
    first.bundle.world.clock.now_s = NOW_S + 3 * DAY
    second = boundary(first.bundle, cfg, registry)
    assert second.bundle.world.factions["wandering_moon_crew"].opportunity[0].fired_count == 1


def test_rumor_is_delivered_on_first_boundary(registry, cfg, tmp_path):
    loaded = migrated_bundle(registry, tmp_path)
    result = boundary(loaded, cfg, registry)
    assert RUMOR in result.notices


def test_rumor_is_delivered_only_once(registry, cfg, tmp_path):
    loaded = migrated_bundle(registry, tmp_path)
    first = boundary(loaded, cfg, registry)
    second = boundary(first.bundle, cfg, registry)
    assert RUMOR not in second.notices
