# Му-а (MU-PLAN B1): ai_dm.audio.catalog -- load_audio, theme_for_tags, theme_files.
# Сторож данных: настоящий audio/data/index.yaml (10 тем, теги ссылаются на существующие темы).
import pytest
from audio_kit import audio, audio_dir, file_names, index, index_dict
from pydantic import ValidationError

from ai_dm.audio.catalog import AUDIO_DIR, AudioIndex, load_audio, theme_files, theme_for_tags

THEMES = ["combat", "tavern", "town", "nature", "dungeon", "dark", "explore", "romance",
          "wilds", "romance_sensual"]


def real():
    return load_audio()


# сторож данных пакета

def test_package_index_has_the_ten_themes():
    assert sorted(real().index.themes) == sorted(THEMES)


def test_every_theme_has_a_music_file_name():
    for name, theme in real().index.themes.items():
        assert theme.music, name


def test_location_tags_point_to_existing_themes():
    idx = real().index
    assert idx.location_tags
    assert set(idx.location_tags.values()) <= set(idx.themes)


def test_locations_point_to_existing_themes():
    idx = real().index
    assert set(idx.locations.values()) <= set(idx.themes)


def test_tone_and_combat_point_to_existing_themes():
    idx = real().index
    assert {idx.tone.horror_strong, idx.tone.default, idx.combat} <= set(idx.themes)


def test_package_tone_defaults_are_dark_and_explore():
    idx = real().index
    assert (idx.combat, idx.tone.horror_strong, idx.tone.default) == ("combat", "dark", "explore")


def test_package_tags_from_the_plan_exist():
    tags = real().index.location_tags
    for tag in ["таверна", "город", "деревня", "храм", "горы", "лес", "руины", "шахта", "долина",
                "подвал", "святилище", "кладбище"]:
        assert tag in tags, tag


def test_combat_theme_has_no_ambient():
    assert not real().index.themes["combat"].ambient


def test_audio_dir_constant_is_the_package_data_folder():
    assert AUDIO_DIR.name == "data"
    assert (AUDIO_DIR / "index.yaml").is_file()


def test_load_audio_default_folder_is_package_data():
    assert real().folder == AUDIO_DIR


def test_load_audio_reads_custom_folder(tmp_path):
    data = audio(tmp_path)
    assert data.folder == tmp_path / "audio"
    assert data.index == index()


# модель

def test_extra_key_in_index_yaml_is_rejected(tmp_path):
    bad = {**index_dict(), "bogus": 1}
    with pytest.raises(ValidationError):
        load_audio(audio_dir(tmp_path, data=bad))


def test_extra_key_in_theme_is_rejected():
    with pytest.raises(ValidationError):
        AudioIndex.model_validate({**index_dict(), "themes": {"x": {"music": "x.ogg", "q": 1}}})


def test_theme_ambient_defaults_to_empty():
    assert index().themes["combat"].ambient == ""


# theme_for_tags

def test_theme_for_tags_first_known_tag():
    assert theme_for_tags(index(), ("нечто", "руины", "город")) == "dungeon"


def test_theme_for_tags_unknown_gives_none():
    assert theme_for_tags(index(), ("нечто",)) is None


def test_theme_for_tags_empty_gives_none():
    assert theme_for_tags(index(), ()) is None


# theme_files

def test_theme_files_both_present(tmp_path):
    data = audio(tmp_path)
    folder = data.folder
    expected = (folder / "tavern.ogg", folder / "crowd.ogg")
    assert theme_files(data.index, folder, "tavern") == expected


def test_theme_files_theme_without_ambient(tmp_path):
    data = audio(tmp_path)
    assert theme_files(data.index, data.folder, "combat") == (data.folder / "combat.ogg", None)


def test_theme_files_missing_ambient_file_gives_none(tmp_path):
    names = [n for n in file_names() if n != "crowd.ogg"]
    data = audio(tmp_path, files=names)
    assert theme_files(data.index, data.folder, "tavern") == (data.folder / "tavern.ogg", None)


def test_theme_files_missing_music_file_gives_none_music(tmp_path):
    names = [n for n in file_names() if n != "tavern.ogg"]
    data = audio(tmp_path, files=names)
    assert theme_files(data.index, data.folder, "tavern") == (None, data.folder / "crowd.ogg")


def test_theme_files_unknown_theme(tmp_path):
    data = audio(tmp_path)
    assert theme_files(data.index, data.folder, "nope") == (None, None)


def test_theme_files_no_files_at_all(tmp_path):
    data = audio(tmp_path, files=[])
    assert theme_files(data.index, data.folder, "town") == (None, None)


@pytest.mark.parametrize("tag", ["чаща", "тёмный лес", "топь"])
def test_real_dark_wood_tags_give_wilds(tag):
    assert theme_for_tags(real().index, (tag,)) == "wilds"


def test_real_horror_variant_turns_nature_into_wilds():
    assert real().index.tone.horror_variants == {"nature": "wilds"}


def test_real_explicit_romance_variant_turns_romance_into_sensual():
    assert real().index.tone.romance_variants == {"откровенно": {"romance": "romance_sensual"}}


def test_real_variants_point_to_existing_themes():
    tone = real().index.tone
    themes = set(real().index.themes)
    assert set(tone.horror_variants) | set(tone.horror_variants.values()) <= themes
    for variants in tone.romance_variants.values():
        assert set(variants) | set(variants.values()) <= themes
