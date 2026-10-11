# Этап 5, P6 (STAGE5-P6-PLAN, п. 7; ответы проектировщика В-1..В-5): сторожа каталога рисунков.
# Ожидаемый API (ТРЕБОВАНИЕ к коду): пакет ai_dm.art; рядом data/index.yaml (модель ArtIndex,
#   extra="forbid": events, locations, location_tags, monsters, creature_types -> id рисунка) и
#   data/<id>.txt (один рисунок = один файл). Сторожа идут по файлам динамически: новый рисунок
#   проверяется без правки теста. Лимиты: обычный <= 36x14, заставка (events.title) <= 76x16;
#   символы 0x20-0x7E и ░▒▓ (В-3); без табов и хвостовых пробелов; cell_len каждого символа 1.
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from rich.cells import cell_len
from rich.text import Text

import ai_dm.art as art_pkg

DATA = Path(art_pkg.__file__).resolve().parent / "data"
ROOT = Path(__file__).resolve().parents[3]
FILES = sorted(DATA.glob("*.txt"))
EXTRA = set("░▒▓")
EVENTS = ["title", "victory", "death", "level_up"]
TAGS_REQUIRED = ["таверна", "город", "деревня", "болото", "руины", "магазин", "горы", "гробница",
                 "равнина"]


def raw_index():
    return yaml.safe_load((DATA / "index.yaml").read_text(encoding="utf-8"))


def all_ids(raw):
    ids = set(raw["events"].values()) | set(raw["locations"].values())
    ids |= set(raw["location_tags"].values()) | set(raw["monsters"].values())
    return ids | set(raw["creature_types"].values())


def limits_of(path):
    if path.stem == raw_index()["events"]["title"]:
        return 76, 16
    return 36, 14


def lines_of(path):
    return path.read_text(encoding="utf-8").splitlines()


def test_catalog_has_files():
    assert FILES


def test_catalog_has_at_least_twenty_drawings():
    assert len(FILES) >= 20


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_drawing_is_not_empty(path):
    assert any(line.strip() for line in lines_of(path))


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_drawing_fits_width_limit(path):
    width = max(cell_len(line) for line in lines_of(path))
    assert width <= limits_of(path)[0]


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_drawing_fits_height_limit(path):
    assert len(lines_of(path)) <= limits_of(path)[1]


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_drawing_has_only_allowed_characters(path):
    text = path.read_text(encoding="utf-8").replace("\n", "")
    bad = sorted({ch for ch in text if not (0x20 <= ord(ch) <= 0x7E or ch in EXTRA)})
    assert bad == []


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_drawing_has_no_tabs(path):
    assert "\t" not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_drawing_has_no_carriage_returns(path):
    assert "\r" not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_drawing_has_no_trailing_spaces(path):
    assert [line for line in lines_of(path) if line != line.rstrip()] == []


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_every_character_is_one_cell_wide(path):
    text = path.read_text(encoding="utf-8").replace("\n", "")
    assert [ch for ch in text if cell_len(ch) != 1] == []


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_drawing_as_text_keeps_brackets_literal(path):
    # рисунок выводится как Text, не как markup: скобки остаются буквами
    text = path.read_text(encoding="utf-8")
    assert Text(text).plain == text


# индекс

def test_index_validates_as_art_index():
    art_pkg.ArtIndex.model_validate(raw_index())


def test_art_index_forbids_unknown_fields():
    raw = dict(raw_index(), bogus={"x": "y"})
    with pytest.raises(ValidationError):
        art_pkg.ArtIndex.model_validate(raw)


def test_index_sets_all_four_events():
    assert sorted(raw_index()["events"]) == sorted(EVENTS)


def test_every_referenced_drawing_has_a_file():
    names = {path.stem for path in FILES}
    assert sorted(all_ids(raw_index()) - names) == []


def test_no_orphan_drawing_files():
    names = {path.stem for path in FILES}
    assert sorted(names - all_ids(raw_index())) == []


def test_monster_ids_exist_in_srd(registry):
    missing = [mid for mid in raw_index()["monsters"] if not registry.has("monster", mid)]
    assert missing == []


def test_location_ids_exist_in_vale_pack():
    text = (ROOT / "campaigns" / "vale" / "locations.yaml").read_text(encoding="utf-8")
    vale = {entry["id"] for entry in yaml.safe_load(text)}
    assert sorted(set(raw_index()["locations"]) - vale) == []


# минимальный набор (п. 4)

@pytest.mark.parametrize("monster_id", ["goblin_warrior", "goblin_boss", "guard"])
def test_required_monsters_have_own_drawing(monster_id):
    assert monster_id in raw_index()["monsters"]


@pytest.mark.parametrize("kind", ["humanoid", "beast", "undead"])
def test_required_creature_types_have_fallback(kind):
    assert kind in raw_index()["creature_types"]


@pytest.mark.parametrize("location_id", ["vale", "lame_goose", "cellar"])
def test_required_vale_locations_have_own_drawing(location_id):
    assert location_id in raw_index()["locations"]


@pytest.mark.parametrize("tag", TAGS_REQUIRED)
def test_required_location_tags_have_fallback(tag):
    assert tag in raw_index()["location_tags"]


def test_temple_or_sanctuary_tag_has_fallback():
    tags = raw_index()["location_tags"]
    assert "храм" in tags or "святилище" in tags


def test_dragon_tavern_gets_drawing_by_tag():
    # «Пьяный дракон» подхватывается по тегам, без ссылок по id (п. 4, п. 6)
    text = (ROOT / "campaigns" / "drunk_dragon" / "locations.yaml").read_text(encoding="utf-8")
    places = {entry["id"]: entry for entry in yaml.safe_load(text)}
    tavern = places["tavern_drunken_dragon"]
    assert "таверна" in tavern["tags"]
    assert raw_index()["location_tags"]["таверна"]


def test_index_source_is_custom():
    assert raw_index()["source"] == "custom"


# русский интерфейс (A7 этапа 5): латиницы в рисунках нет вообще (решение по ревью P6)

@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_drawing_has_no_latin_letters(path):
    import re

    assert re.findall(r"[A-Za-z]", path.read_text(encoding="utf-8")) == []
