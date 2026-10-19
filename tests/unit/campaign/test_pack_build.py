# Сборка нового мира из пака (этап 3, партия 1; STAGE3-PLAN A2, A3).
#   ai_dm.game.starter.new_world_from_pack(registry, cfg, pack, *, hero, seed, world_id=None,
#       saved_at, conflicts=None) -> SaveBundle   (hero -- id пресета; conflicts -- список, куда
#       кладутся Conflict-ы; отказ старта -- ai_dm.campaign.build.StartRefused)
# Мир собирается из мини-пака (campaign_kit): часы -- из start.date / start.time, смертность -- из
# пресета или per_day, глава -- из start.chapter, выжимка сцены -- из start.scene_summary.
import pytest
from campaign_kit import SAVED_AT, default_files, load, write_pack

DAY = 86400


def build(tmp_path, registry, cfg, files=None, **kwargs):
    from ai_dm.game.starter import new_world_from_pack

    pack = load(write_pack(tmp_path, files), registry)
    return new_world_from_pack(
        registry, cfg, pack, hero="arn", seed=1, world_id="w1", saved_at=SAVED_AT, **kwargs
    )


def test_world_gets_campaign_id_version_and_seed(tmp_path, registry, cfg):
    from ai_dm.core.rng import Rng

    bundle = build(tmp_path, registry, cfg)
    assert bundle.world.campaign_id == "mini"
    assert bundle.world.campaign_version == "1.0"
    assert bundle.manifest.campaign_id == "mini"
    assert bundle.world.rng == Rng(1).state


def test_world_has_entities_of_pack(tmp_path, registry, cfg):
    world = build(tmp_path, registry, cfg).world
    assert sorted(world.locations) == ["cellar", "tavern", "town"]
    assert sorted(world.npcs) == ["aldric", "guard"]
    assert sorted(world.factions) == ["guild"]
    assert sorted(world.pantheon) == ["selune"]


def test_lore_is_copied_from_pack(tmp_path, registry, cfg):
    lore = build(tmp_path, registry, cfg).world.lore
    assert "город с таверной" in lore.world_text
    assert "сырой" in lore.truths


def test_clock_starts_at_pack_date_and_time(tmp_path, registry, cfg):
    clock = build(tmp_path, registry, cfg).world.clock
    assert clock.to_date() == "0100-03-01"
    assert clock.now_s % DAY == 8 * 3600


def test_clock_uses_pack_time(tmp_path, registry, cfg):
    files = default_files()
    files["campaign.yaml"]["start"]["time"] = "21:30"
    clock = build(tmp_path, registry, cfg, files).world.clock
    assert clock.now_s % DAY == 21 * 3600 + 30 * 60


def test_clock_uses_pack_calendar(tmp_path, registry, cfg):
    files = default_files()
    files["campaign.yaml"]["calendar"] = {
        "months": [{"name": f"М{i}", "days": 36} for i in range(1, 11)],
        "seasons": [{"name": "холод", "months": [1, 2, 3, 4, 5]},
                    {"name": "тепло", "months": [6, 7, 8, 9, 10]}],
    }
    files["campaign.yaml"]["start"]["date"] = "0002-10-36"
    world = build(tmp_path, registry, cfg, files).world
    assert world.clock.to_date() == "0002-10-36"
    assert world.clock.calendar.days_in_year == 360


def test_default_mortality_is_normal_preset(tmp_path, registry, cfg):
    assert build(tmp_path, registry, cfg).world.mortality_per_day == 20000


def test_mortality_preset_from_pack(tmp_path, registry, cfg):
    files = default_files()
    files["campaign.yaml"]["mortality"] = {"preset": "harsh"}
    assert build(tmp_path, registry, cfg, files).world.mortality_per_day == 5000


def test_mortality_per_day_overrides_preset(tmp_path, registry, cfg):
    files = default_files()
    files["campaign.yaml"]["mortality"] = {"preset": "calm", "per_day": 123}
    assert build(tmp_path, registry, cfg, files).world.mortality_per_day == 123


def test_nudge_and_natural_events_from_pack(tmp_path, registry, cfg):
    files = default_files()
    files["campaign.yaml"]["nudge"] = {"scenes": 5}
    files["campaign.yaml"]["natural_events"] = {"chance_percent_per_season": 12}
    world = build(tmp_path, registry, cfg, files).world
    assert world.nudge_scenes == 5
    assert world.natural.chance_percent_per_season == 12


def test_tone_and_flags_from_pack(tmp_path, registry, cfg):
    files = default_files()
    files["campaign.yaml"]["tone"] = {
        "mood": "мрачно", "violence": "жестоко", "romance": "чувственно",
    }
    files["campaign.yaml"]["flags"] = {"chapter_two": True}
    world = build(tmp_path, registry, cfg, files).world
    assert world.tone.mood == "мрачно"
    assert world.tone.violence == "жестоко"
    assert world.tone.romance == "чувственно"
    assert world.flags["chapter_two"] is True


def test_first_chapter_is_opened_from_start_section(tmp_path, registry, cfg):
    chapter = build(tmp_path, registry, cfg).session.current_chapter
    assert chapter.number == 1
    assert chapter.id == "ch_1"
    assert chapter.closed_reason is None


def test_chapter_two_start_like_drunk_dragon(tmp_path, registry, cfg):
    files = default_files()
    files["campaign.yaml"]["start"]["chapter"] = {"number": 2, "title": "Глава II"}
    chapter = build(tmp_path, registry, cfg, files).session.current_chapter
    assert (chapter.id, chapter.number, chapter.title) == ("ch_2", 2, "Глава II")


def test_start_scene_is_in_hero_location_with_pack_summary(tmp_path, registry, cfg):
    files = default_files()
    files["campaign.yaml"]["start"]["scene_summary"] = "Герой сидит в таверне."
    bundle = build(tmp_path, registry, cfg, files)
    scene = bundle.session.current_scene
    assert scene.id == "scene_1"
    assert scene.location_id == "tavern"
    assert scene.summary == "Герой сидит в таверне."
    assert bundle.session.boundary_pending is False


def test_start_memory_and_chronicle_are_copied(tmp_path, registry, cfg):
    files = default_files()
    files["start/memory.yaml"] = {"game_summary": "Герой пришёл в город."}
    files["start/chronicle.yaml"] = {"entries": [{"at_s": 0, "kind": "event", "text": "Начало"}]}
    bundle = build(tmp_path, registry, cfg, files)
    assert bundle.memory.game_summary == "Герой пришёл в город."
    assert bundle.chronicle.entries[0].text == "Начало"


def test_hero_is_built_from_preset(tmp_path, registry, cfg):
    bundle = build(tmp_path, registry, cfg)
    hero = bundle.heroes[0]
    assert hero.id == "hero"
    assert hero.name == "Арн"
    assert hero.location_id == "tavern"
    assert bundle.manifest.current_hero_id == "hero"
    assert bundle.manifest.heroes == ["hero"]


def test_preset_state_is_applied_on_top_of_built_hero(tmp_path, registry, cfg):
    files = default_files()
    files["heroes/arn.yaml"].update({
        "money_cp": 777, "inventory_extra": [{"item_id": "potion_of_healing", "qty": 2}],
        "favor": {"selune": 3}, "deity_id": "selune", "birth_date": "0080-01-01",
    })
    hero = build(tmp_path, registry, cfg, files).heroes[0]
    assert hero.money_cp == 777
    assert {e.item_id: e.qty for e in hero.inventory}["potion_of_healing"] == 2
    assert hero.favor == {"selune": 3}
    assert hero.deity_id == "selune"
    assert hero.birth_s == 79 * 360 * DAY


def test_preset_level_is_applied(tmp_path, registry, cfg):
    files = default_files()
    files["heroes/arn.yaml"]["level"] = 2
    assert build(tmp_path, registry, cfg, files).heroes[0].sheet.level == 2


def test_unknown_preset_is_value_error(tmp_path, registry, cfg):
    from ai_dm.game.starter import new_world_from_pack

    pack = load(write_pack(tmp_path), registry)
    with pytest.raises(ValueError):
        new_world_from_pack(registry, cfg, pack, hero="ghost", seed=1, saved_at=SAVED_AT)


def test_new_world_id_is_unique_when_not_given(tmp_path, registry, cfg):
    from ai_dm.game.starter import new_world_from_pack

    pack = load(write_pack(tmp_path), registry)
    first = new_world_from_pack(registry, cfg, pack, hero="arn", seed=1, saved_at=SAVED_AT)
    second = new_world_from_pack(registry, cfg, pack, hero="arn", seed=1, saved_at=SAVED_AT)
    assert first.world.world_id != second.world.world_id


def test_same_arguments_give_equal_bundles(tmp_path, registry, cfg):
    first = build(tmp_path / "a", registry, cfg)
    second = build(tmp_path / "b", registry, cfg)
    assert first.model_dump_json() == second.model_dump_json()


# конфликты при создании мира

def test_conflicting_entity_is_not_loaded_and_is_reported(tmp_path, registry, cfg):
    files = default_files()
    files["npcs.yaml"].append({"id": "twin", "name": "Олдрик", "named": True, "means": ["меч"]})
    conflicts = []
    bundle = build(tmp_path, registry, cfg, files, conflicts=conflicts)
    assert "twin" not in bundle.world.npcs
    assert [c.id for c in conflicts] == ["twin"]


def test_clean_pack_reports_no_conflicts(tmp_path, registry, cfg):
    conflicts = []
    build(tmp_path, registry, cfg, conflicts=conflicts)
    assert conflicts == []


def test_npc_with_hero_name_is_dropped_not_the_hero(tmp_path, registry, cfg):
    files = default_files()
    files["npcs.yaml"].append({"id": "double", "name": "Арн", "named": True, "means": ["меч"]})
    conflicts = []
    bundle = build(tmp_path, registry, cfg, files, conflicts=conflicts)
    assert "double" not in bundle.world.npcs
    assert bundle.heroes[0].name == "Арн"
    assert [c.id for c in conflicts] == ["double"]


def test_dropped_start_location_refuses_start(tmp_path, registry, cfg):
    from ai_dm.campaign.build import StartRefused

    files = default_files()
    files["locations.yaml"].append({"id": "tavern_2", "name": "Таверна", "parent_id": "town"})
    files["campaign.yaml"]["start"]["hero_location"] = "tavern_2"
    files["heroes/arn.yaml"].pop("location_id")
    with pytest.raises(StartRefused) as err:
        build(tmp_path, registry, cfg, files)
    assert "tavern_2" in "\n".join(err.value.lines)


def test_dropped_preset_location_refuses_start(tmp_path, registry, cfg):
    from ai_dm.campaign.build import StartRefused

    files = default_files()
    files["locations.yaml"].append({"id": "tavern_2", "name": "Таверна", "parent_id": "town"})
    files["heroes/arn.yaml"]["location_id"] = "tavern_2"
    with pytest.raises(StartRefused):
        build(tmp_path, registry, cfg, files)


def test_chapter_from_pack_starts_with_scene_count_1(tmp_path, registry, cfg):
    bundle = build(tmp_path, registry, cfg)
    assert bundle.session.current_chapter.scene_count == 1


def test_chapter_two_from_pack_also_has_scene_count_1(tmp_path, registry, cfg):
    files = default_files()
    files["campaign.yaml"]["start"]["chapter"] = {"number": 2, "title": "Глава II"}
    assert build(tmp_path, registry, cfg, files).session.current_chapter.scene_count == 1


# Б0-П2: лёгкий пресет мира. build_world(preset_id=...) -> new_world_from_pack(preset_id=...):
# preset_id -> manifest.preset -> "" (тон пака); наложение через apply_preset; запись хроники
# kind="tone" "Пресет мира: <name>" -- одна, только при наложении.

def tone_entries(bundle):
    return [e for e in bundle.chronicle.entries if e.kind == "tone"]


def pack_tone_files():
    files = default_files()
    files["campaign.yaml"]["tone"] = {
        "mood": "авторское", "violence": "реалистично", "horror": "нет", "romance": "намёки",
        "language": "сдержанно", "hard_limits": ["пак-запрет"], "soft_limits": ["пак-мягкий"],
        "notes": "голос пака",
    }
    return files


def test_preset_id_overlays_pack_tone(tmp_path, registry, cfg):
    tone = build(tmp_path, registry, cfg, pack_tone_files(), preset_id="grim").world.tone
    assert tone.mood != "авторское"
    assert tone.violence == "жестоко"
    assert tone.horror == "сильно"
    assert tone.romance == "откровенно"
    assert tone.language == "грубо"
    assert tone.notes != "голос пака"
    assert tone.notes


def test_preset_tone_equals_apply_preset(tmp_path, registry, cfg):
    from ai_dm.campaign.presets import apply_preset, load_presets

    files = pack_tone_files()
    tone = build(tmp_path, registry, cfg, files, preset_id="grim").world.tone
    pack = load(write_pack(tmp_path / "again", files), registry)
    assert tone == apply_preset(pack.manifest.tone, load_presets()["grim"])


def test_preset_keeps_pack_limits(tmp_path, registry, cfg):
    tone = build(tmp_path, registry, cfg, pack_tone_files(), preset_id="grim").world.tone
    assert tone.hard_limits == ["пак-запрет"]
    assert tone.soft_limits == ["пак-мягкий"]


def test_no_preset_keeps_pack_tone(tmp_path, registry, cfg):
    tone = build(tmp_path, registry, cfg, pack_tone_files()).world.tone
    assert tone.mood == "авторское"
    assert tone.romance == "намёки"
    assert tone.notes == "голос пака"
    assert tone.hard_limits == ["пак-запрет"]


def test_no_preset_writes_no_tone_entry(tmp_path, registry, cfg):
    assert tone_entries(build(tmp_path, registry, cfg, pack_tone_files())) == []


def test_empty_manifest_preset_keeps_pack_tone(tmp_path, registry, cfg):
    files = pack_tone_files()
    files["campaign.yaml"]["preset"] = ""
    bundle = build(tmp_path, registry, cfg, files)
    assert bundle.world.tone.notes == "голос пака"
    assert tone_entries(bundle) == []


def test_manifest_preset_is_applied(tmp_path, registry, cfg):
    files = pack_tone_files()
    files["campaign.yaml"]["preset"] = "heroic"
    tone = build(tmp_path, registry, cfg, files).world.tone
    assert tone.violence == "реалистично"
    assert tone.romance == "намёки"
    assert tone.horror == "умеренно"
    assert tone.notes != "голос пака"


def test_explicit_preset_id_beats_manifest_preset(tmp_path, registry, cfg):
    files = pack_tone_files()
    files["campaign.yaml"]["preset"] = "heroic"
    assert build(tmp_path, registry, cfg, files, preset_id="fairytale").world.tone.romance == "нет"


def test_manifest_preset_writes_tone_entry(tmp_path, registry, cfg):
    files = pack_tone_files()
    files["campaign.yaml"]["preset"] = "heroic"
    assert len(tone_entries(build(tmp_path, registry, cfg, files))) == 1


def test_preset_writes_exactly_one_tone_entry_with_name(tmp_path, registry, cfg):
    from ai_dm.campaign.presets import load_presets

    bundle = build(tmp_path, registry, cfg, preset_id="grim")
    entries = tone_entries(bundle)
    assert len(entries) == 1
    assert entries[0].text == f"Пресет мира: {load_presets()['grim'].name}"


def test_tone_entry_is_at_start_time(tmp_path, registry, cfg):
    bundle = build(tmp_path, registry, cfg, preset_id="grim")
    assert tone_entries(bundle)[0].at_s == bundle.world.clock.now_s


def test_tone_entry_comes_after_pack_chronicle(tmp_path, registry, cfg):
    files = default_files()
    files["start/chronicle.yaml"] = {"entries": [{"at_s": 0, "kind": "event", "text": "было"}]}
    bundle = build(tmp_path, registry, cfg, files, preset_id="grim")
    assert [e.kind for e in bundle.chronicle.entries] == ["event", "tone"]


def test_preset_does_not_touch_other_world_fields(tmp_path, registry, cfg):
    files = pack_tone_files()
    files["campaign.yaml"]["flags"] = {"chapter_two": True}
    world = build(tmp_path, registry, cfg, files, preset_id="grim").world
    assert world.flags["chapter_two"] is True
    assert world.campaign_id == "mini"
    assert sorted(world.locations) == ["cellar", "tavern", "town"]


def test_same_preset_gives_equal_bundles(tmp_path, registry, cfg):
    first = build(tmp_path / "a", registry, cfg, preset_id="grim")
    second = build(tmp_path / "b", registry, cfg, preset_id="grim")
    assert first.model_dump() == second.model_dump()


def test_preset_tone_is_not_shared_between_worlds(tmp_path, registry, cfg):
    first = build(tmp_path / "a", registry, cfg, preset_id="grim").world.tone
    first.hard_limits.append("зз")
    first.notes = "испорчено"
    second = build(tmp_path / "b", registry, cfg, preset_id="grim").world.tone
    assert second.hard_limits == []
    assert second.notes != "испорчено"


def test_unknown_manifest_preset_is_pack_error_line(tmp_path, registry):
    from campaign_kit import pack_errors

    files = default_files()
    files["campaign.yaml"]["preset"] = "nowhere"
    lines = pack_errors(write_pack(tmp_path, files), registry)
    assert lines is not None
    assert any("campaign.yaml" in line and "nowhere" in line for line in lines)


def test_known_manifest_preset_gives_no_pack_error(tmp_path, registry):
    from campaign_kit import pack_errors

    files = default_files()
    files["campaign.yaml"]["preset"] = "grim"
    assert pack_errors(write_pack(tmp_path, files), registry) is None


def test_manifest_preset_defaults_to_empty(tmp_path, registry):
    pack = load(write_pack(tmp_path), registry)
    assert pack.manifest.preset == ""


def test_check_manifest_reports_unknown_preset(tmp_path, registry):
    from ai_dm.campaign.loader import check_manifest

    files = default_files()
    pack = load(write_pack(tmp_path, files), registry)
    pack.manifest.preset = "nowhere"
    lines = check_manifest(pack, registry)
    assert len(lines) == 1
    assert "nowhere" in lines[0]
    pack.manifest.preset = "grim"
    assert check_manifest(pack, registry) == []


# служебное значение preset "pack" -- тон пака без наложения

def test_preset_id_pack_keeps_pack_tone_without_entry(tmp_path, registry, cfg):
    bundle = build(tmp_path, registry, cfg, pack_tone_files(), preset_id="pack")
    pack = load(write_pack(tmp_path / "again", pack_tone_files()), registry)
    assert bundle.world.tone == pack.manifest.tone
    assert tone_entries(bundle) == []


def test_preset_id_pack_beats_manifest_preset(tmp_path, registry, cfg):
    files = pack_tone_files()
    files["campaign.yaml"]["preset"] = "grim"
    bundle = build(tmp_path, registry, cfg, files, preset_id="pack")
    assert bundle.world.tone.notes == "голос пака"
    assert bundle.world.tone.romance == "намёки"
    assert tone_entries(bundle) == []


def test_manifest_preset_pack_is_valid_and_keeps_pack_tone(tmp_path, registry, cfg):
    from campaign_kit import pack_errors

    files = pack_tone_files()
    files["campaign.yaml"]["preset"] = "pack"
    assert pack_errors(write_pack(tmp_path / "p", files), registry) is None
    bundle = build(tmp_path, registry, cfg, files)
    assert bundle.world.tone.notes == "голос пака"
    assert tone_entries(bundle) == []


# Б1а (B1-PLAN A4): герой на лету -- build_world(hero_id=HeroSheet)

import sys  # noqa: E402
from pathlib import Path  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

from hero_kit import base_sheet, narrative_trigger, vale_pack  # noqa: E402

from ai_dm.campaign.build import (  # noqa: E402
    ON_THE_FLY_ID,
    StartRefused,
    apply_hooks,
    known_ids,
    resolve_hero_preset,
    taken_names,
)
from ai_dm.campaign.models import HeroPreset  # noqa: E402
from ai_dm.campaign.presets import apply_preset, load_presets  # noqa: E402
from ai_dm.game.starter import new_world_from_pack  # noqa: E402
from ai_dm.rules.triggers_eval import KnownIds  # noqa: E402


def build_sheet(registry, cfg, pack, sheet=None, **kwargs):
    return new_world_from_pack(
        registry, cfg, pack, hero=sheet or base_sheet(), seed=1, world_id="w1",
        saved_at=SAVED_AT, **kwargs
    )


def with_choice(sheet, **changes):
    choices = sheet.choices.model_copy(update=changes)
    return sheet.model_copy(update={"choices": choices})


def mini(tmp_path, registry, files=None):
    return load(write_pack(tmp_path, files), registry)


def test_sheet_hero_starts_in_manifest_location_of_vale(registry, cfg):
    bundle = build_sheet(registry, cfg, vale_pack(registry))
    assert bundle.heroes[0].location_id == "lame_goose"


def test_sheet_hero_starts_in_manifest_location_of_mini_pack(tmp_path, registry, cfg):
    bundle = build_sheet(registry, cfg, mini(tmp_path, registry))
    assert bundle.heroes[0].location_id == "tavern"


def test_sheet_hero_has_id_hero_and_is_current(registry, cfg):
    bundle = build_sheet(registry, cfg, vale_pack(registry))
    assert [h.id for h in bundle.heroes] == ["hero"]
    assert bundle.manifest.current_hero_id == "hero"
    assert bundle.manifest.heroes == ["hero"]


def test_sheet_hero_is_built_from_sheet_choices(registry, cfg):
    hero = build_sheet(registry, cfg, vale_pack(registry)).heroes[0]
    assert hero.name == "Борин"
    assert hero.sheet.class_id == "fighter"
    assert hero.sheet.species_id == "human"
    assert hero.sheet.level == 1
    assert hero.sheet.xp == 0
    assert hero.sheet.background.name == "Бывший цирковой акробат"


def test_sheet_hero_gets_motive_means_and_opportunity(registry, cfg):
    hero = build_sheet(registry, cfg, vale_pack(registry)).heroes[0]
    assert hero.motive == "Найти сестру."
    assert hero.means == ["острый ум"]
    assert [t.id for t in hero.opportunity] == ["o1"]
    assert hero.opportunity[0].once is True


def test_sheet_hero_hooks_are_copies(registry, cfg):
    sheet = base_sheet()
    hero = build_sheet(registry, cfg, vale_pack(registry), sheet).heroes[0]
    hero.means.append("ещё")
    hero.opportunity[0].fired_count = 5
    assert sheet.means == ["острый ум"]
    assert sheet.opportunity[0].fired_count == 0


def test_sheet_hero_money_is_background_gold_plus_kit_gold(registry, cfg):
    hero = build_sheet(registry, cfg, vale_pack(registry)).heroes[0]
    assert hero.money_cp == 1000 + 400


def test_sheet_hero_has_kit_items_and_equipment(registry, cfg):
    from ai_dm.rules.inventory import count_item

    hero = build_sheet(registry, cfg, vale_pack(registry)).heroes[0]
    assert count_item(hero, "chain_mail") == 1
    assert count_item(hero, "greatsword") == 1
    assert hero.equipped.armor == "chain_mail"
    assert hero.equipped.main_hand == "greatsword"


def test_sheet_hero_gets_pack_world_and_start_scene(registry, cfg):
    bundle = build_sheet(registry, cfg, vale_pack(registry))
    assert bundle.world.campaign_id == "vale"
    assert bundle.session.current_scene is not None
    assert sorted(bundle.world.npcs) == ["grakh", "innkeeper"]


def test_sheet_hero_with_preset_gets_preset_tone(registry, cfg):
    pack = vale_pack(registry)
    bundle = build_sheet(registry, cfg, pack, preset_id="heroic")
    expected = apply_preset(pack.manifest.tone, load_presets()["heroic"])
    assert bundle.world.tone == expected


def test_sheet_hero_without_preset_uses_manifest_preset_tone(registry, cfg):
    from ai_dm.campaign.presets import apply_preset, load_presets

    pack = vale_pack(registry)
    bundle = build_sheet(registry, cfg, pack)
    preset = load_presets()[pack.manifest.preset]
    assert bundle.world.tone == apply_preset(pack.manifest.tone, preset)


def test_sheet_hero_build_does_not_change_the_sheet(registry, cfg):
    sheet = base_sheet()
    before = sheet.model_dump_json()
    build_sheet(registry, cfg, vale_pack(registry), sheet)
    assert sheet.model_dump_json() == before


def test_same_sheet_and_seed_give_equal_bundles(registry, cfg):
    first = build_sheet(registry, cfg, vale_pack(registry))
    second = build_sheet(registry, cfg, vale_pack(registry))
    assert first.model_dump_json() == second.model_dump_json()


def test_sheet_with_unknown_kit_refuses_start_with_custom_id(registry, cfg):
    sheet = with_choice(base_sheet(), class_kit="z")
    with pytest.raises(StartRefused) as info:
        build_sheet(registry, cfg, vale_pack(registry), sheet)
    assert "custom" in "\n".join(info.value.lines)
    assert "z" in "\n".join(info.value.lines)


def test_sheet_with_name_of_named_npc_refuses_start(tmp_path, registry, cfg):
    sheet = with_choice(base_sheet(), name="Олдрик")
    with pytest.raises(StartRefused) as info:
        build_sheet(registry, cfg, mini(tmp_path, registry), sheet)
    text = "\n".join(info.value.lines)
    assert "Олдрик" in text
    assert "уже занято" in text
    assert "custom" in text


def test_sheet_with_name_of_unnamed_npc_is_fine(tmp_path, registry, cfg):
    sheet = with_choice(base_sheet(), name="Стражник")
    conflicts = []
    bundle = build_sheet(registry, cfg, mini(tmp_path, registry), sheet, conflicts=conflicts)
    assert "guard" in bundle.world.npcs
    assert conflicts == []


def test_preset_hero_id_still_builds_as_before(tmp_path, registry, cfg):
    from ai_dm.core.rng import Rng

    bundle = new_world_from_pack(
        registry, cfg, mini(tmp_path, registry), hero="arn", seed=1, world_id="w1",
        saved_at=SAVED_AT,
    )
    assert bundle.heroes[0].name == "Арн"
    assert bundle.heroes[0].means == []
    assert bundle.heroes[0].opportunity == []
    assert bundle.world.rng == Rng(1).state


def test_unknown_preset_string_is_still_value_error(registry, cfg):
    with pytest.raises(ValueError):
        new_world_from_pack(
            registry, cfg, vale_pack(registry), hero="nobody", seed=1, world_id="w1",
            saved_at=SAVED_AT,
        )


# resolve_hero_preset / apply_hooks

def test_resolve_hero_preset_by_id_returns_pack_preset(registry):
    pack = vale_pack(registry)
    assert resolve_hero_preset(pack, "arn") is next(p for p in pack.heroes if p.id == "arn")


def test_resolve_hero_preset_unknown_id_is_value_error(registry):
    with pytest.raises(ValueError):
        resolve_hero_preset(vale_pack(registry), "nobody")


def test_resolve_hero_preset_for_sheet_makes_custom_preset(registry):
    sheet = base_sheet()
    preset = resolve_hero_preset(vale_pack(registry), sheet)
    assert isinstance(preset, HeroPreset)
    assert preset.id == ON_THE_FLY_ID == "custom"
    assert preset.choices == sheet.choices
    assert preset.motive == "Найти сестру."
    assert preset.location_id is None
    assert preset.money_cp is None
    assert preset.level == 1
    assert preset.xp == 0
    assert preset.inventory_extra == []
    assert preset.equipped is None
    assert preset.companion is None
    assert preset.favor == {}
    assert preset.deity_id is None


def test_apply_hooks_copies_motive_means_and_triggers(registry):
    from ai_dm.rules.builder import build_character

    sheet = base_sheet()
    hero = build_character(sheet.choices, registry)
    apply_hooks(hero, sheet)
    assert hero.motive == sheet.motive
    assert hero.means == sheet.means
    assert hero.means is not sheet.means
    assert hero.opportunity == sheet.opportunity
    assert hero.opportunity[0] is not sheet.opportunity[0]


def test_apply_hooks_full_sheet_replaces_previous_hooks(registry):
    from ai_dm.rules.builder import build_character

    hero = build_character(base_sheet().choices, registry)
    hero.motive = "старый мотив"
    hero.means = ["старое"]
    hero.opportunity = [narrative_trigger("old")]
    apply_hooks(hero, base_sheet())
    assert hero.motive == "Найти сестру."
    assert hero.means == ["острый ум"]
    assert [t.id for t in hero.opportunity] == ["o1"]


def test_apply_hooks_empty_opportunity_keeps_previous_opportunity(registry):
    from ai_dm.rules.builder import build_character

    hero = build_character(base_sheet().choices, registry)
    hero.means = ["старое"]
    hero.opportunity = [narrative_trigger("old")]
    apply_hooks(hero, base_sheet(opportunity=[]))
    assert [t.id for t in hero.opportunity] == ["old"]
    assert hero.means == ["острый ум"]
    assert hero.motive == "Найти сестру."


def test_apply_hooks_empty_means_keeps_previous_means(registry):
    from ai_dm.rules.builder import build_character

    hero = build_character(base_sheet().choices, registry)
    hero.means = ["старое"]
    apply_hooks(hero, base_sheet(means=[]))
    assert hero.means == ["старое"]


def test_apply_hooks_empty_motive_keeps_previous_motive(registry):
    from ai_dm.rules.builder import build_character

    hero = build_character(base_sheet().choices, registry)
    hero.motive = "старый мотив"
    apply_hooks(hero, base_sheet(motive=""))
    assert hero.motive == "старый мотив"


def test_apply_hooks_all_empty_leaves_hero_untouched(registry):
    from ai_dm.rules.builder import build_character

    hero = build_character(base_sheet().choices, registry)
    hero.motive = "старый мотив"
    hero.means = ["старое"]
    hero.opportunity = [narrative_trigger("old")]
    apply_hooks(hero, base_sheet(motive="", means=[], opportunity=[]))
    assert hero.motive == "старый мотив"
    assert hero.means == ["старое"]
    assert [t.id for t in hero.opportunity] == ["old"]


# means / opportunity пресета пака (шаг 34)

def hooks_files(**changes):
    files = default_files()
    files["heroes/arn.yaml"].update({
        "motive": "найти правду",
        "means": ["а", "б"],
        "opportunity": [{"id": "o1", "if": {"hero_at": "tavern"}, "then": "делает дело",
                         "once": True}],
    })
    files["heroes/arn.yaml"].update(changes)
    return files


def test_preset_means_and_opportunity_reach_hero(tmp_path, registry, cfg):
    hero = build(tmp_path, registry, cfg, hooks_files()).heroes[0]
    assert hero.motive == "найти правду"
    assert hero.means == ["а", "б"]
    assert [t.id for t in hero.opportunity] == ["o1"]
    assert hero.opportunity[0].once is True


def test_preset_hooks_are_copies_in_hero(tmp_path, registry, cfg):
    from ai_dm.game.starter import new_world_from_pack

    pack = load(write_pack(tmp_path, hooks_files()), registry)
    hero = new_world_from_pack(
        registry, cfg, pack, hero="arn", seed=1, world_id="w1", saved_at=SAVED_AT
    ).heroes[0]
    preset = pack.heroes[0]
    assert hero.means == preset.means
    assert hero.means is not preset.means
    assert hero.opportunity[0] is not preset.opportunity[0]
    hero.means.append("ещё")
    hero.opportunity[0].fired_count = 5
    assert preset.means == ["а", "б"]
    assert preset.opportunity[0].fired_count == 0


def test_preset_without_hooks_gives_empty_means_and_opportunity(tmp_path, registry, cfg):
    hero = build(tmp_path, registry, cfg).heroes[0]
    assert hero.means == []
    assert hero.opportunity == []


def test_hero_preset_model_accepts_means_and_opportunity_fields():
    preset = HeroPreset.model_validate({
        "id": "x", "choices": base_sheet().choices.model_dump(),
        "means": ["а"],
        "opportunity": [{"id": "o1", "if": {"flag": "f"}, "then": "т"}],
    })
    assert preset.means == ["а"]
    assert [t.id for t in preset.opportunity] == ["o1"]


def test_hero_preset_model_defaults_to_empty_means_and_opportunity():
    preset = HeroPreset.model_validate({"id": "x", "choices": base_sheet().choices.model_dump()})
    assert preset.means == []
    assert preset.opportunity == []


# known_ids / taken_names

def test_known_ids_of_vale(registry):
    known = known_ids(vale_pack(registry))
    assert isinstance(known, KnownIds)
    assert known.npcs == {"innkeeper", "grakh"}
    assert known.locations == {"vale", "lame_goose", "cellar", "old_crypt"}
    assert known.pantheon == set()


def test_taken_names_of_vale(registry):
    assert sorted(taken_names(vale_pack(registry))) == ["Гарт", "Гракх"]


def test_known_ids_of_mini_pack(tmp_path, registry):
    known = known_ids(mini(tmp_path, registry))
    assert known.npcs == {"aldric", "guard"}
    assert known.locations == {"town", "tavern", "cellar"}
    assert known.pantheon == {"selune"}


def test_taken_names_of_mini_pack_has_named_npcs_gods_factions_only(tmp_path, registry):
    names = taken_names(mini(tmp_path, registry))
    assert sorted(names) == ["Гильдия воров", "Олдрик", "Селунэ"]
    assert "Стражник" not in names


def test_taken_names_is_a_list(registry):
    assert isinstance(taken_names(vale_pack(registry)), list)


def test_apply_hooks_triggers_are_deep_copies(registry):
    from ai_dm.rules.builder import build_character

    sheet = base_sheet()
    hero = build_character(sheet.choices, registry)
    apply_hooks(hero, sheet)
    hero.opportunity[0].if_.text = "другое"
    assert sheet.opportunity[0].if_.text == "герой узнаёт о сестре"


# Б3: пак без героя (как после import) -- мир стартует только героем на лету

def pack_without_heroes(tmp_path, registry):
    files = default_files()
    files["heroes/arn.yaml"] = None
    files["campaign.yaml"]["start"]["heroes"] = []
    return mini(tmp_path, registry, files)


def test_sheet_hero_starts_on_pack_without_heroes(tmp_path, registry, cfg):
    bundle = build_sheet(registry, cfg, pack_without_heroes(tmp_path, registry))
    assert bundle.heroes[0].name == "Борин"
    assert bundle.heroes[0].location_id == "tavern"
    assert bundle.world.campaign_id == "mini"


def test_sheet_hero_on_pack_without_heroes_gets_known_and_taken_names(tmp_path, registry, cfg):
    pack = pack_without_heroes(tmp_path, registry)
    assert known_ids(pack).npcs == {"aldric", "guard"}
    assert "Олдрик" in taken_names(pack)
    sheet = with_choice(base_sheet(), name="Олдрик")
    with pytest.raises(StartRefused):
        build_sheet(registry, cfg, pack, sheet)


def test_preset_hero_on_pack_without_heroes_is_unknown(tmp_path, registry, cfg):
    pack = pack_without_heroes(tmp_path, registry)
    with pytest.raises(ValueError):
        new_world_from_pack(
            registry, cfg, pack, hero="arn", seed=1, world_id="w1", saved_at=SAVED_AT
        )
