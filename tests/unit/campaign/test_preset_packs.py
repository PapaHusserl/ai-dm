# П37: обратный индекс «пресет -> паки» (campaign.presets.preset_packs) и тон по умолчанию
# трёх паков каталога (manifest.preset заполнен у vale, drunk_dragon, dusk_academy).
# Ожидаемый API: preset_packs(campaigns_dir) -> {preset_id: [(pack_id, name), ...]},
# список по pack_id; читает только campaign.yaml через yaml.safe_load, чужое молча пропускает.
import pytest
import yaml
from campaign_kit import ROOT

CATALOG = ROOT / "campaigns"
THREE = ("vale", "drunk_dragon", "dusk_academy")


def put(root, dirname, data):
    path = root / dirname
    path.mkdir(parents=True)
    text = data if isinstance(data, str) else yaml.safe_dump(data, allow_unicode=True)
    (path / "campaign.yaml").write_text(text, encoding="utf-8")


def index(root):
    from ai_dm.campaign.presets import preset_packs

    return preset_packs(root)


def test_pack_with_preset_is_indexed_and_pack_without_is_not(tmp_path):
    put(tmp_path, "rose", {"id": "rose", "name": "Розы", "preset": "romantic"})
    put(tmp_path, "mini", {"id": "mini", "name": "Мини"})
    assert index(tmp_path) == {"romantic": [("rose", "Розы")]}


def test_two_packs_of_one_preset_are_sorted_by_id(tmp_path):
    put(tmp_path, "rose", {"id": "rose", "name": "Розы", "preset": "romantic"})
    put(tmp_path, "aa", {"id": "aa", "name": "Аа", "preset": "romantic"})
    assert index(tmp_path) == {"romantic": [("aa", "Аа"), ("rose", "Розы")]}


def test_different_presets_are_separate_keys(tmp_path):
    put(tmp_path, "a", {"id": "a", "name": "А", "preset": "grim"})
    put(tmp_path, "b", {"id": "b", "name": "Б", "preset": "heroic"})
    assert index(tmp_path) == {"grim": [("a", "А")], "heroic": [("b", "Б")]}


def test_preset_pack_marker_is_skipped(tmp_path):
    put(tmp_path, "rose", {"id": "rose", "name": "Розы", "preset": "pack"})
    assert index(tmp_path) == {}


@pytest.mark.parametrize("value", ["", None])
def test_empty_preset_is_skipped(tmp_path, value):
    put(tmp_path, "rose", {"id": "rose", "name": "Розы", "preset": value})
    assert index(tmp_path) == {}


def test_import_temp_dir_is_skipped(tmp_path):
    put(tmp_path, ".import-rose-abc", {"id": "rose", "name": "Розы", "preset": "grim"})
    assert index(tmp_path) == {}


def test_dir_without_campaign_yaml_is_skipped(tmp_path):
    (tmp_path / "empty").mkdir()
    put(tmp_path, "rose", {"id": "rose", "name": "Розы", "preset": "grim"})
    assert index(tmp_path) == {"grim": [("rose", "Розы")]}


def test_file_instead_of_dir_is_skipped(tmp_path):
    (tmp_path / "note.txt").write_text("preset: grim", encoding="utf-8")
    assert index(tmp_path) == {}


def test_broken_yaml_is_skipped(tmp_path):
    put(tmp_path, "broken", ": :")
    put(tmp_path, "rose", {"id": "rose", "name": "Розы", "preset": "grim"})
    assert index(tmp_path) == {"grim": [("rose", "Розы")]}


def test_yaml_list_is_skipped(tmp_path):
    put(tmp_path, "lst", "- preset: grim\n- b\n")
    assert index(tmp_path) == {}


def test_empty_yaml_is_skipped(tmp_path):
    put(tmp_path, "nothing", "")
    assert index(tmp_path) == {}


def test_missing_name_falls_back_to_id(tmp_path):
    put(tmp_path, "rose", {"id": "rose", "preset": "grim"})
    assert index(tmp_path) == {"grim": [("rose", "rose")]}


def test_missing_id_falls_back_to_dir_name(tmp_path):
    put(tmp_path, "rosedir", {"name": "Розы", "preset": "grim"})
    assert index(tmp_path) == {"grim": [("rosedir", "Розы")]}


def test_missing_id_and_name_use_dir_name_for_both(tmp_path):
    put(tmp_path, "rosedir", {"preset": "grim"})
    assert index(tmp_path) == {"grim": [("rosedir", "rosedir")]}


def test_missing_campaigns_dir_gives_empty_index(tmp_path):
    assert index(tmp_path / "nowhere") == {}


def test_accepts_str_path(tmp_path):
    put(tmp_path, "rose", {"id": "rose", "name": "Розы", "preset": "grim"})
    assert index(str(tmp_path)) == {"grim": [("rose", "Розы")]}


def test_index_does_not_validate_manifest(tmp_path):
    put(tmp_path, "rose", {"preset": "grim", "start": "мусор"})
    assert index(tmp_path) == {"grim": [("rose", "rose")]}


# данные репозитория (локально рядом может лежать untracked campaigns/test)

def catalog_index():
    return {
        preset: [pack for pack in packs if pack[0] in THREE]
        for preset, packs in index(CATALOG).items()
        if any(pack[0] in THREE for pack in packs)
    }


def test_catalog_packs_are_mapped_to_presets():
    assert catalog_index() == {
        "heroic": [("vale", "Вейл")],
        "grim": [("drunk_dragon", "Пьяный Дракон")],
        "romantic": [("dusk_academy", "Академия Сумеречного Мыса")],
    }


def test_fairytale_has_no_catalog_pack():
    assert "fairytale" not in catalog_index()


def test_catalog_preset_ids_exist_in_preset_catalog():
    from ai_dm.campaign.presets import load_presets

    assert set(catalog_index()) <= set(load_presets())


@pytest.mark.parametrize("name", THREE)
def test_real_pack_loads_with_manifest_preset(name):
    from ai_dm.campaign.loader import load_pack, pack_content_dir
    from ai_dm.content.loader import load_registry

    content = pack_content_dir(CATALOG / name)
    pack = load_pack(CATALOG / name, load_registry([content] if content else []))
    assert pack.manifest.preset


# тон по умолчанию: pick_tone без preset_id берёт manifest.preset

def manifest_of(name):
    from ai_dm.campaign.loader import load_pack, pack_content_dir
    from ai_dm.content.loader import load_registry

    content = pack_content_dir(CATALOG / name)
    return load_pack(CATALOG / name, load_registry([content] if content else [])).manifest


@pytest.mark.parametrize("name", THREE)
def test_default_tone_is_manifest_preset_applied(name):
    from ai_dm.campaign.build import pick_tone
    from ai_dm.campaign.presets import apply_preset, load_presets

    manifest = manifest_of(name)
    preset = load_presets()[manifest.preset]
    tone, entry = pick_tone(manifest, None)
    assert tone == apply_preset(manifest.tone, preset)
    assert entry == f"Пресет мира: {preset.name}"


@pytest.mark.parametrize("name", THREE)
def test_explicit_pack_gives_manifest_tone_and_no_entry(name):
    from ai_dm.campaign.build import pick_tone

    manifest = manifest_of(name)
    tone, entry = pick_tone(manifest, "pack")
    assert tone == manifest.tone
    assert entry is None


def test_dusk_academy_keeps_pack_limits_and_adds_pack_softening():
    manifest = manifest_of("dusk_academy")
    from ai_dm.campaign.build import pick_tone

    tone, _ = pick_tone(manifest, None)
    assert len(tone.hard_limits) >= 2
    assert tone.hard_limits[:2] == manifest.tone.hard_limits[:2]
    assert set(manifest.tone.soft_limits) <= set(tone.soft_limits)
    assert any("пошлост" in line for line in tone.soft_limits)
    assert tone.romance == "чувственно"
    assert tone.horror == "умеренно"


def test_dusk_academy_lore_says_night_folk_are_neighbours():
    from ai_dm.campaign.loader import CAMPAIGNS_DIR

    text = (CAMPAIGNS_DIR / "dusk_academy" / "world.md").read_text(encoding="utf-8").lower()
    assert "соседи" in text


def test_drunk_dragon_default_tone_axes():
    from ai_dm.campaign.build import pick_tone

    tone, _ = pick_tone(manifest_of("drunk_dragon"), None)
    assert tone.romance == "откровенно"
    assert tone.language == "грубо"
    assert tone.horror == "сильно"


def test_drunk_dragon_play_style_lines_live_in_soft_limits():
    from ai_dm.campaign.build import pick_tone

    manifest = manifest_of("drunk_dragon")
    assert len(manifest.tone.soft_limits) >= 3
    tone, _ = pick_tone(manifest, None)
    assert set(manifest.tone.soft_limits) <= set(tone.soft_limits)
    assert any("мета-игрово" in line for line in tone.soft_limits)


def test_vale_default_tone_axes():
    from ai_dm.campaign.build import pick_tone

    tone, _ = pick_tone(manifest_of("vale"), None)
    assert tone.romance == "намёки"


def test_id_from_manifest_wins_over_dir_name(tmp_path):
    put(tmp_path, "somedir", {"id": "rose", "name": "Розы", "preset": "grim"})
    assert index(tmp_path) == {"grim": [("rose", "Розы")]}


def test_sorting_is_by_dir_walk_and_entries_keep_manifest_ids(tmp_path):
    put(tmp_path, "b_dir", {"id": "zz", "name": "Зэ", "preset": "grim"})
    put(tmp_path, "a_dir", {"id": "yy", "name": "Игрек", "preset": "grim"})
    assert index(tmp_path) == {"grim": [("yy", "Игрек"), ("zz", "Зэ")]}
