# BACKLOG 177 (docs/plan-dogovor.md): scripts/migrate_dusk_pact.py <каталог мира|слота> --
# одноразовая правка сейва dusk_academy: спящему триггеру fortune_visit фракции pact_keepers
# ставится срок now_s + DAYS, state=active; calm_sign активируется; флаг pact:together=True;
# в lore дописываются абзац о Договоре и правда; Люциану -- заметки и секрет pact; Мирте --
# заметки, если пусты. stdlib, бэкап до записи, идемпотентность, отказ без записи на чужом
# мире / не той версии / до догрузки пака.
# Тесты на синтетическом слоте во tmp_path; запуск отдельным процессом. Вторая половина -- пак v4
# и сквозная секция на настоящем паке: merge_new -> скрипт -> границы сцены.
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[3] / "scripts" / "migrate_dusk_pact.py"
WORLD_ID = "dusk_academy-d3de6c57"  # id мира зашит в скрипте; каталог -- синтетический, во tmp_path
NOW_S = 22616325
DAY = 86400
OLD_WORLD_TEXT = "Остров Сумеречного Мыса."
OLD_TRUTHS = "- Фонари гаснут сами."
OLD_LUCIAN_NOTES = "Старые заметки Люциана."
OLD_MIRTA_NOTES = "Заметки Мирты из пака."


def pact_faction(visit_state="disabled", calm_state="disabled", visit_fired=0):
    return {
        "id": "pact_keepers", "name": "Хранители Договора", "members": ["fortune_teller_haven"],
        "opportunity": [
            {
                "id": "fortune_visit", "if_": {"type": "time_after", "seconds": 0},
                "then": "Мирта идёт к героине", "once": True, "state": visit_state,
                "fired_count": visit_fired,
            },
            {
                "id": "blight_sign",
                "if_": {"type": "flag", "name": "pact:together", "value": True},
                "then": "беда", "once": False, "cooldown": "1d", "state": "active",
            },
            {
                "id": "calm_sign",
                "if_": {"type": "flag", "name": "pact:together", "value": False},
                "then": "успокоение", "once": False, "cooldown": "30d", "state": calm_state,
            },
        ],
    }


def make_slot(
    root, *, version=9, world_id=WORLD_ID, faction=True, teller=True, visit_state="disabled",
    calm_state="disabled", visit_fired=0, mirta_notes="", lucian_notes=OLD_LUCIAN_NOTES,
    world_text=OLD_WORLD_TEXT, truths=OLD_TRUTHS,
):
    slot = root / "saves" / world_id / "slots" / "auto"
    (slot / "world").mkdir(parents=True)
    manifest = {
        "schema_version": version, "engine_version": "0.1.0", "world_id": world_id,
        "campaign_id": "dusk_academy", "slot": "auto", "saved_at": "2026-10-15T15:38:18+00:00",
        "current_hero_id": "hero", "heroes": ["hero"],
    }
    world = {
        "world_id": world_id, "campaign_id": "dusk_academy", "campaign_version": "3",
        "clock": {"now_s": NOW_S}, "flags": {"met_maya": True},
        "factions": {"pact_keepers": pact_faction(visit_state, calm_state, visit_fired)}
        if faction else {},
        "npcs": {
            "maya": {"name": "Майя"},
            "lucian": {"name": "Люциан Велар", "notes": lucian_notes, "secrets": []},
        },
        "lore": {"world_text": world_text, "truths": truths},
        "notices": [],
    }
    if teller:
        world["npcs"]["fortune_teller_haven"] = {"name": "Тётушка Мирта", "notes": mirta_notes}
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


def trigger_of(slot, trigger_id):
    triggers = world_of(slot)["factions"]["pact_keepers"]["opportunity"]
    return next(t for t in triggers if t["id"] == trigger_id)


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
def test_apply_sets_visit_seconds_to_now_plus_days(tmp_path, version):
    slot = make_slot(tmp_path, version=version)
    run(slot)
    assert trigger_of(slot, "fortune_visit")["if_"]["seconds"] == NOW_S + DAY


@pytest.mark.parametrize("version", [9, 12])
def test_apply_activates_visit(tmp_path, version):
    slot = make_slot(tmp_path, version=version)
    run(slot)
    assert trigger_of(slot, "fortune_visit")["state"] == "active"


@pytest.mark.parametrize("version", [9, 12])
def test_apply_activates_calm_sign(tmp_path, version):
    slot = make_slot(tmp_path, version=version)
    run(slot)
    assert trigger_of(slot, "calm_sign")["state"] == "active"


def test_apply_keeps_visit_condition_type(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    assert trigger_of(slot, "fortune_visit")["if_"]["type"] == "time_after"


def test_apply_does_not_touch_blight_sign(tmp_path):
    slot = make_slot(tmp_path)
    before = trigger_of(slot, "blight_sign")
    run(slot)
    assert trigger_of(slot, "blight_sign") == before


def test_apply_does_not_touch_calm_sign_condition(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    assert trigger_of(slot, "calm_sign")["if_"] == {
        "type": "flag", "name": "pact:together", "value": False,
    }


def test_apply_sets_together_flag_true(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    assert world_of(slot)["flags"]["pact:together"] is True


def test_apply_keeps_existing_flags(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    assert world_of(slot)["flags"]["met_maya"] is True


def test_apply_appends_world_text_keeping_old(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    text = world_of(slot)["lore"]["world_text"]
    assert text.startswith(OLD_WORLD_TEXT)
    assert "Договоре Хранителей" in text
    assert "pact:together" in text


def test_apply_appends_truth_as_list_item_keeping_old(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    truths = world_of(slot)["lore"]["truths"]
    assert truths.startswith(OLD_TRUTHS + "\n- ")
    assert "Договоре Хранителей" in truths


def test_apply_with_empty_lore_does_not_start_with_separator(tmp_path):
    slot = make_slot(tmp_path, world_text="", truths="")
    run(slot)
    lore = world_of(slot)["lore"]
    assert lore["world_text"].startswith("Остров держится")
    assert lore["truths"].startswith("- Остров держится")


def test_apply_appends_lucian_notes_keeping_old(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    notes = world_of(slot)["npcs"]["lucian"]["notes"]
    assert notes.startswith(OLD_LUCIAN_NOTES)
    assert "отравляет Люциана" in notes


def test_lucian_notes_end_with_narrator_flag_rule(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    notes = world_of(slot)["npcs"]["lucian"]["notes"]
    assert notes.endswith(
        "Для рассказчика: когда Мира и Люциан явно расстались — `set_flag pact:together false`;"
        " когда снова сошлись — `set_flag pact:together true`."
    )


def test_script_mirta_notes_equal_pack_notes_whole(registry, tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    pack_notes = next(
        n for n in dusk_pack(registry).npcs if n.id == "fortune_teller_haven"
    ).notes
    assert world_of(slot)["npcs"]["fortune_teller_haven"]["notes"] == pack_notes


def test_apply_with_empty_lucian_notes_does_not_start_with_separator(tmp_path):
    slot = make_slot(tmp_path, lucian_notes="")
    run(slot)
    assert world_of(slot)["npcs"]["lucian"]["notes"].startswith("Договор Хранителей")


def test_apply_fills_empty_mirta_notes(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    notes = world_of(slot)["npcs"]["fortune_teller_haven"]["notes"]
    assert "треснувшую печать" in notes
    assert "pact:known" in notes


def test_apply_keeps_nonempty_mirta_notes(tmp_path):
    slot = make_slot(tmp_path, mirta_notes=OLD_MIRTA_NOTES)
    run(slot)
    assert world_of(slot)["npcs"]["fortune_teller_haven"]["notes"] == OLD_MIRTA_NOTES


def test_apply_adds_one_pact_secret_to_lucian(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    secrets = world_of(slot)["npcs"]["lucian"]["secrets"]
    assert len(secrets) == 1
    assert secrets[0]["id"] == "pact"
    assert secrets[0]["revealed"] is False


def test_pact_secret_waits_for_known_flag(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    secret = world_of(slot)["npcs"]["lucian"]["secrets"][0]
    assert secret["reveal_if"]["type"] == "flag"
    assert secret["reveal_if"]["name"] == "pact:known"


def test_apply_keeps_the_rest_of_world_json(tmp_path):
    slot = make_slot(tmp_path)
    before = world_of(slot)
    run(slot)
    after = world_of(slot)
    for doc in (before, after):
        doc["flags"].pop("pact:together", None)
        del doc["lore"]
        del doc["npcs"]["lucian"]
        del doc["npcs"]["fortune_teller_haven"]
        for trigger in doc["factions"]["pact_keepers"]["opportunity"]:
            trigger.pop("state")
            trigger["if_"].pop("seconds", None)
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


def test_backup_is_named_backup_pact(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    found = backups(tmp_path, slot)
    assert found[0].parents[2].name.startswith("backup-pact-")


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
    assert trigger_of(slot, "fortune_visit")["state"] == "active"


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


def test_version_14_is_refused(tmp_path):
    assert refused(tmp_path, version=14).returncode == 1


def test_missing_faction_is_refused_with_hint(tmp_path):
    result = refused(tmp_path, faction=False)
    assert result.returncode == 1
    assert "запустите игру" in result.stdout


def test_missing_fortune_teller_is_refused_with_hint(tmp_path):
    result = refused(tmp_path, teller=False)
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


def test_second_run_does_not_duplicate_texts_or_secret(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    run(slot)
    world = world_of(slot)
    assert world["lore"]["world_text"].count("древние Хранители") == 1
    assert len(world["npcs"]["lucian"]["secrets"]) == 1


def test_fired_visit_means_already_applied(tmp_path):
    slot = make_slot(tmp_path, visit_state="fired", visit_fired=1)
    before = snapshot(tmp_path)
    result = run(slot)
    assert result.returncode == 0
    assert "Уже применено" in result.stdout
    assert snapshot(tmp_path) == before


def test_active_visit_means_already_applied(tmp_path):
    slot = make_slot(tmp_path, visit_state="active")
    before = snapshot(tmp_path)
    assert "Уже применено" in run(slot).stdout
    assert snapshot(tmp_path) == before


# пак: фракция, NPC, версия

DUSK_DIR = Path(__file__).parents[3] / "campaigns" / "dusk_academy"


def dusk_pack(registry):
    from ai_dm.campaign.loader import load_pack, pack_content_dir
    from ai_dm.content.loader import load_registry

    content = pack_content_dir(DUSK_DIR)
    return load_pack(DUSK_DIR, load_registry([content] if content is not None else []))


def pact_faction_of_pack(registry):
    return next(f for f in dusk_pack(registry).factions if f.id == "pact_keepers")


def pack_trigger(registry, trigger_id):
    return next(t for t in pact_faction_of_pack(registry).opportunity if t.id == trigger_id)


def test_pack_version_is_four(registry):
    assert dusk_pack(registry).manifest.version == "4"


def test_pack_loads_without_errors(registry):
    from campaign_kit import pack_errors

    from ai_dm.campaign.loader import pack_content_dir
    from ai_dm.content.loader import load_registry

    content = pack_content_dir(DUSK_DIR)
    assert pack_errors(DUSK_DIR, load_registry([content] if content is not None else [])) is None


def test_pack_faction_members_is_fortune_teller(registry):
    assert pact_faction_of_pack(registry).members == ["fortune_teller_haven"]


def test_pack_faction_has_three_triggers(registry):
    ids = [t.id for t in pact_faction_of_pack(registry).opportunity]
    assert ids == ["fortune_visit", "blight_sign", "calm_sign"]


@pytest.mark.parametrize(
    ("trigger_id", "state"),
    [("fortune_visit", "disabled"), ("blight_sign", "active"), ("calm_sign", "disabled")],
)
def test_pack_trigger_state(registry, trigger_id, state):
    assert pack_trigger(registry, trigger_id).state == state


def test_pack_fortune_visit_is_once_and_sleeping_on_time(registry):
    trigger = pack_trigger(registry, "fortune_visit")
    assert trigger.once is True
    assert trigger.if_.type == "time_after"


def test_pack_blight_sign_repeats_daily_on_flag_true(registry):
    trigger = pack_trigger(registry, "blight_sign")
    assert trigger.once is False
    assert trigger.cooldown == "1d"
    assert trigger.if_.type == "flag"
    assert trigger.if_.name == "pact:together"
    assert trigger.if_.value is True


def test_pack_calm_sign_waits_for_flag_false(registry):
    trigger = pack_trigger(registry, "calm_sign")
    assert trigger.once is False
    assert trigger.cooldown == "30d"
    assert trigger.if_.name == "pact:together"
    assert trigger.if_.value is False


def test_pack_visit_then_names_the_fortune_teller(registry):
    assert "fortune_teller_haven" in pack_trigger(registry, "fortune_visit").then


def test_pack_fortune_teller_notes_mention_pact_and_flag(registry):
    npc = next(n for n in dusk_pack(registry).npcs if n.id == "fortune_teller_haven")
    assert "Договор" in npc.notes
    assert "pact:known" in npc.notes


def test_pack_no_pact_faction_member_is_key(registry):
    npcs = {n.id: n for n in dusk_pack(registry).npcs}
    assert all(npcs[m].key is False for m in pact_faction_of_pack(registry).members)


def test_pack_world_text_and_truths_mention_pact():
    assert "Договор" in (DUSK_DIR / "world.md").read_text(encoding="utf-8")
    assert "Договор" in (DUSK_DIR / "truths.md").read_text(encoding="utf-8")


# догрузка настоящего пака

def pact_bundle(registry):
    # старый мир без Хранителей и Мирты + догрузка настоящего пака; героя берём из мини-бандла
    from protocol_kit import make_bundle

    from ai_dm.campaign.merge import merge_new

    bundle = make_bundle(registry)
    bundle.world.world_id = WORLD_ID
    bundle.manifest.world_id = WORLD_ID
    report = merge_new(bundle, dusk_pack(registry))
    return bundle, report


def test_merge_into_v2_adds_faction_and_fortune_teller(registry):
    bundle, report = pact_bundle(registry)
    assert "faction:pact_keepers" in report.added
    assert "npc:fortune_teller_haven" in report.added
    assert "fortune_teller_haven" in bundle.world.npcs


def test_merge_into_v3_adds_only_faction(registry):
    from ai_dm.campaign.merge import merge_new

    bundle, _ = pact_bundle(registry)
    del bundle.world.factions["pact_keepers"]
    again = merge_new(bundle, dusk_pack(registry))
    assert "faction:pact_keepers" in again.added
    assert [a for a in again.added if a.startswith("npc:")] == []


def test_merge_keeps_visit_and_calm_disabled(registry):
    bundle, _ = pact_bundle(registry)
    states = {t.id: t.state for t in bundle.world.factions["pact_keepers"].opportunity}
    assert states == {"fortune_visit": "disabled", "blight_sign": "active", "calm_sign": "disabled"}


def test_second_merge_adds_nothing(registry):
    from ai_dm.campaign.merge import merge_new

    bundle, _ = pact_bundle(registry)
    again = merge_new(bundle, dusk_pack(registry))
    assert [a for a in again.added if a.startswith(("npc:", "faction:"))] == []


def test_fortune_teller_on_pier_is_relevant_only_as_merchant(registry):
    # план ждал «невидима для роли world», но у неё услуга fortune -> причина merchant
    # (BACKLOG 132); here/active/key/with_hero у Мирты нет
    from ai_dm.master.relevance import npc_reasons

    bundle, _ = pact_bundle(registry)
    bundle.heroes[0].location_id = "academy"
    assert npc_reasons(bundle)["fortune_teller_haven"] == {"merchant"}


# движок: триггеры фракции (фиксируем существующее поведение на данных пака)

def pact_candidates(bundle, cfg):
    from ai_dm.world_sim import triggers

    check = triggers.check(bundle, cfg)
    return [c.ref for c in check.candidates if c.ref.startswith("trigger:pact_keepers:")]


def advance(bundle, seconds):
    bundle.world.clock.now_s += seconds


def test_blight_sign_acts_when_together_is_true(registry, cfg):
    bundle, _ = pact_bundle(registry)
    bundle.world.flags["pact:together"] = True
    assert "trigger:pact_keepers:blight_sign" in pact_candidates(bundle, cfg)


def test_blight_sign_is_silent_without_flag(registry, cfg):
    bundle, _ = pact_bundle(registry)
    assert pact_candidates(bundle, cfg) == []


def test_blight_sign_is_silent_when_together_is_false(registry, cfg):
    bundle, _ = pact_bundle(registry)
    bundle.world.flags["pact:together"] = False
    assert "trigger:pact_keepers:blight_sign" not in pact_candidates(bundle, cfg)


def test_blight_sign_waits_for_cooldown(registry, cfg):
    bundle, _ = pact_bundle(registry)
    bundle.world.flags["pact:together"] = True
    pact_candidates(bundle, cfg)
    advance(bundle, DAY - 1)
    assert pact_candidates(bundle, cfg) == []


def test_blight_sign_acts_again_after_cooldown(registry, cfg):
    bundle, _ = pact_bundle(registry)
    bundle.world.flags["pact:together"] = True
    pact_candidates(bundle, cfg)
    advance(bundle, DAY)
    assert "trigger:pact_keepers:blight_sign" in pact_candidates(bundle, cfg)


def test_calm_sign_in_new_world_without_flag_is_never_ready(registry):
    from ai_dm.rules.triggers_eval import is_ready

    bundle, _ = pact_bundle(registry)
    calm = next(t for t in bundle.world.factions["pact_keepers"].opportunity if t.id == "calm_sign")
    assert is_ready(calm, 10**9) is False


def test_calm_sign_in_new_world_without_flag_gives_no_candidate(registry, cfg):
    bundle, _ = pact_bundle(registry)
    advance(bundle, 100 * DAY)
    assert "trigger:pact_keepers:calm_sign" not in pact_candidates(bundle, cfg)


# сквозное: пак -> догрузка -> скрипт -> границы сцены

def migrated_bundle(registry, tmp_path):
    # пишем слот, гоняем скрипт процессом, читаем обратно движком
    from ai_dm.persistence.store import load_slot, save_slot

    bundle, _ = pact_bundle(registry)
    bundle.world.clock.now_s = NOW_S
    save_slot(tmp_path / "saves", bundle, "auto", saved_at="2026-10-15T15:38:18+00:00")
    result = run(tmp_path / "saves" / WORLD_ID)
    assert result.returncode == 0, result.stdout
    return load_slot(tmp_path / "saves", WORLD_ID, "auto")


def trigger_in(bundle, trigger_id):
    triggers = bundle.world.factions["pact_keepers"].opportunity
    return next(t for t in triggers if t.id == trigger_id)


def test_script_output_loads_into_engine(registry, tmp_path):
    loaded = migrated_bundle(registry, tmp_path)
    visit = trigger_in(loaded, "fortune_visit")
    assert visit.state == "active"
    assert visit.if_.seconds == NOW_S + DAY
    assert trigger_in(loaded, "calm_sign").state == "active"
    assert loaded.world.flags["pact:together"] is True


def test_script_fills_pack_mirta_notes_only_when_empty(registry, tmp_path):
    loaded = migrated_bundle(registry, tmp_path)
    pack_notes = next(
        n for n in dusk_pack(registry).npcs if n.id == "fortune_teller_haven"
    ).notes
    assert loaded.world.npcs["fortune_teller_haven"].notes == pack_notes


def test_visit_does_not_act_before_term(registry, cfg, tmp_path):
    loaded = migrated_bundle(registry, tmp_path)
    loaded.world.clock.now_s = NOW_S + DAY - 1
    assert "trigger:pact_keepers:fortune_visit" not in pact_candidates(loaded, cfg)


def test_visit_acts_at_term_with_then(registry, cfg, tmp_path):
    from ai_dm.world_sim import triggers

    loaded = migrated_bundle(registry, tmp_path)
    loaded.world.clock.now_s = NOW_S + DAY
    check = triggers.check(loaded, cfg)
    found = [c for c in check.candidates if c.ref == "trigger:pact_keepers:fortune_visit"]
    assert len(found) == 1
    assert found[0].kind == "act"
    assert "fortune_teller_haven" in found[0].then


def test_blight_sign_is_candidate_at_term_after_script(registry, cfg, tmp_path):
    loaded = migrated_bundle(registry, tmp_path)
    loaded.world.clock.now_s = NOW_S + DAY
    assert "trigger:pact_keepers:blight_sign" in pact_candidates(loaded, cfg)


def test_visit_acts_only_once(registry, cfg, tmp_path):
    loaded = migrated_bundle(registry, tmp_path)
    loaded.world.clock.now_s = NOW_S + DAY
    pact_candidates(loaded, cfg)
    loaded.world.clock.now_s = NOW_S + 5 * DAY
    assert "trigger:pact_keepers:fortune_visit" not in pact_candidates(loaded, cfg)
    assert trigger_in(loaded, "fortune_visit").fired_count == 1


def test_calm_sign_acts_after_flag_removed_to_false(registry, cfg, tmp_path):
    loaded = migrated_bundle(registry, tmp_path)
    loaded.world.flags["pact:together"] = False
    found = pact_candidates(loaded, cfg)
    assert "trigger:pact_keepers:calm_sign" in found
    assert "trigger:pact_keepers:blight_sign" not in found


def test_calm_sign_is_silent_while_together(registry, cfg, tmp_path):
    loaded = migrated_bundle(registry, tmp_path)
    assert "trigger:pact_keepers:calm_sign" not in pact_candidates(loaded, cfg)


def test_script_output_survives_boundary(registry, cfg, tmp_path):
    import ai_dm.game.boundary as boundary_mod

    loaded = migrated_bundle(registry, tmp_path)
    loaded.world.clock.now_s = NOW_S + DAY
    boundary_mod.close_boundary(loaded, cfg, "end_scene")
    result = boundary_mod.finish_boundary(loaded, cfg, registry)
    assert result.error is None
    assert trigger_in(result.bundle, "fortune_visit").state == "fired"


# секрет Люциана (Р2 = б)

def lucian_in_hero_location(loaded):
    lucian = loaded.world.npcs["lucian"]
    lucian.location_id = "academy"
    lucian.status = "alive"
    return lucian


def test_pact_secret_is_visible_where_lucian_stands(registry, tmp_path):
    from ai_dm.rules.secrets import hidden_secrets

    loaded = migrated_bundle(registry, tmp_path)
    lucian = lucian_in_hero_location(loaded)
    found = hidden_secrets(loaded.world, lucian.location_id)
    assert ("lucian", "pact") in [(n.id, s.id) for n, s in found]


def test_pact_secret_reveal_without_flag_is_too_early(registry, tmp_path):
    from ai_dm.rules.results import Rejected
    from ai_dm.rules.secrets import reveal

    loaded = migrated_bundle(registry, tmp_path)
    lucian = lucian_in_hero_location(loaded)
    result = reveal(lucian, "pact", loaded.world, loaded.heroes[0])
    assert isinstance(result, Rejected)
    assert result.reason == "too_early"


def test_pact_secret_reveal_with_known_flag_succeeds(registry, tmp_path):
    from ai_dm.rules.secrets import reveal

    loaded = migrated_bundle(registry, tmp_path)
    lucian = lucian_in_hero_location(loaded)
    loaded.world.flags["pact:known"] = True
    events = reveal(lucian, "pact", loaded.world, loaded.heroes[0])
    assert [e.type for e in events] == ["secret_revealed"]
    assert lucian.secrets[0].revealed is True
