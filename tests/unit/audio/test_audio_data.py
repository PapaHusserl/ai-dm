# Му-б (MU-PLAN B2): сторож данных audio/data -- треки, форматы, размеры, ATTRIBUTION.
# Читает настоящую папку пакета (AUDIO_DIR), но только метаданные файлов и первые байты.
import re

import pytest

from ai_dm.audio.catalog import AUDIO_DIR, load_audio

MIB = 1024 * 1024
LICENSES = ("CC0", "CC BY")


def music_files():
    return sorted({t.music for t in load_audio().index.themes.values() if t.music})


def ambient_files():
    return sorted({t.ambient for t in load_audio().index.themes.values() if t.ambient})


def ogg_files():
    return sorted(p.name for p in AUDIO_DIR.glob("*.ogg"))


def attribution_rows():
    # строки таблицы: ячейки без крайних "|" и пробелов
    rows = []
    for line in (AUDIO_DIR / "ATTRIBUTION.md").read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
        if line.startswith("|") and cells[0].endswith(".ogg"):
            rows.append(cells)
    return rows


def test_every_theme_has_a_music_file_that_exists():
    for name in music_files():
        assert (AUDIO_DIR / name).is_file(), name


def test_every_ambient_file_exists():
    assert ambient_files()
    for name in ambient_files():
        assert (AUDIO_DIR / name).is_file(), name


def test_every_theme_music_is_set():
    for name, theme in load_audio().index.themes.items():
        assert theme.music, name


def test_total_size_of_ogg_files_is_at_most_40_mib():
    assert sum((AUDIO_DIR / n).stat().st_size for n in ogg_files()) <= 40 * MIB


@pytest.mark.parametrize("name", ogg_files())
def test_file_is_ogg(name):
    assert (AUDIO_DIR / name).read_bytes()[:4] == b"OggS"


@pytest.mark.parametrize("name", music_files())
def test_music_file_is_at_most_3_5_mib(name):
    assert 0 < (AUDIO_DIR / name).stat().st_size <= 3.5 * MIB


@pytest.mark.parametrize("name", ambient_files())
def test_ambient_file_is_at_most_1_5_mib(name):
    assert 0 < (AUDIO_DIR / name).stat().st_size <= 1.5 * MIB


def test_attribution_table_is_not_empty():
    assert attribution_rows()


def test_attribution_mentions_every_ogg_file():
    assert set(ogg_files()) <= {row[0] for row in attribution_rows()}


def test_attribution_has_no_rows_for_missing_files():
    assert {row[0] for row in attribution_rows()} <= set(ogg_files())


def test_attribution_lists_each_file_once():
    names = [row[0] for row in attribution_rows()]
    assert len(names) == len(set(names))


def test_every_row_has_all_columns():
    for row in attribution_rows():
        assert len(row) == 8, row[0]
        assert all(cell for cell in row), row[0]


def test_every_row_has_allowed_license_with_link():
    for row in attribution_rows():
        license_cell = row[4]
        assert license_cell.startswith(tuple(f"[{name}" for name in LICENSES)), row[0]
        assert re.search(r"\]\(https?://", license_cell), row[0]


def test_every_row_has_source_page_link():
    for row in attribution_rows():
        assert re.fullmatch(r"<https?://\S+>", row[5]), row[0]


def test_every_row_has_check_date():
    for row in attribution_rows():
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", row[6]), row[0]


def test_no_unlisted_files_in_data_folder():
    allowed = set(ogg_files()) | {"index.yaml", "ATTRIBUTION.md"}
    assert {p.name for p in AUDIO_DIR.iterdir() if p.name != "__pycache__"} <= allowed


def test_every_ogg_file_is_used_by_index():
    assert set(ogg_files()) <= set(music_files()) | set(ambient_files())
