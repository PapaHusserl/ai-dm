# Этап 5, P6 (п. 1, 7): выбор. Ожидаемый API (ТРЕБОВАНИЕ к коду): ai_dm.art.load_art() (кэш),
#   art_for_location(loc), art_for_monster(mon), art_for_event(name) -> str | None; текст --
#   содержимое data/<id>.txt без хвостового перевода строки.
#   Цепочка: точный id -> тег/тип -> None;
#   порядок тегов локации = приоритет.
from pathlib import Path

import pytest
import yaml

import ai_dm.art as art_pkg
from ai_dm.state.world import Location

DATA = Path(art_pkg.__file__).resolve().parent / "data"


def index():
    return yaml.safe_load((DATA / "index.yaml").read_text(encoding="utf-8"))


def drawing(art_id):
    return (DATA / f"{art_id}.txt").read_text(encoding="utf-8").removesuffix("\n")


def place(location_id="nowhere", tags=()):
    return Location(id=location_id, name="Место", tags=list(tags))


def monster(registry, base="goblin_warrior", monster_id=None, creature_type=None):
    update = {}
    if monster_id is not None:
        update["id"] = monster_id
    if creature_type is not None:
        update["creature_type"] = creature_type
    return registry.get("monster", base).model_copy(update=update)


def test_load_art_is_cached():
    assert art_pkg.load_art() is art_pkg.load_art()


# события

@pytest.mark.parametrize("name", ["title", "victory", "death", "level_up"])
def test_event_returns_its_drawing(name):
    assert art_pkg.art_for_event(name) == drawing(index()["events"][name])


def test_unknown_event_has_no_drawing():
    assert art_pkg.art_for_event("earthquake") is None


def test_event_drawings_are_different():
    names = ["title", "victory", "death", "level_up"]
    assert len({art_pkg.art_for_event(name) for name in names}) == 4


# локации

@pytest.mark.parametrize("location_id", ["vale", "lame_goose", "cellar"])
def test_exact_location_id_gives_its_drawing(location_id):
    expected = drawing(index()["locations"][location_id])
    assert art_pkg.art_for_location(place(location_id)) == expected


def test_exact_id_beats_tag():
    expected = drawing(index()["locations"]["cellar"])
    assert art_pkg.art_for_location(place("cellar", ["руины"])) == expected


def test_unknown_id_uses_tag():
    expected = drawing(index()["location_tags"]["болото"])
    assert art_pkg.art_for_location(place("fen_x", ["болото"])) == expected


def test_first_matching_tag_wins():
    tags = index()["location_tags"]
    assert tags["болото"] != tags["руины"]
    first = art_pkg.art_for_location(place("x", ["болото", "руины"]))
    second = art_pkg.art_for_location(place("x", ["руины", "болото"]))
    assert first == drawing(tags["болото"])
    assert second == drawing(tags["руины"])


def test_tag_without_drawing_is_skipped_for_next_tag():
    expected = drawing(index()["location_tags"]["горы"])
    assert art_pkg.art_for_location(place("x", ["зачищено", "горы"])) == expected


def test_no_id_no_tag_gives_none():
    assert art_pkg.art_for_location(place("x")) is None


def test_only_unknown_tags_give_none():
    assert art_pkg.art_for_location(place("x", ["зачищено", "заброшено"])) is None


# монстры

@pytest.mark.parametrize("monster_id", ["goblin_warrior", "goblin_boss", "guard"])
def test_exact_monster_gives_its_drawing(registry, monster_id):
    expected = drawing(index()["monsters"][monster_id])
    assert art_pkg.art_for_monster(monster(registry, monster_id)) == expected


def test_monster_drawings_are_different(registry):
    ids = ["goblin_warrior", "goblin_boss", "guard"]
    assert len({art_pkg.art_for_monster(monster(registry, i)) for i in ids}) == 3


def test_exact_monster_beats_creature_type(registry):
    # гоблины -- fey, у стражи -- humanoid: точная ссылка главнее типа
    guard = monster(registry, "guard", creature_type="beast")
    assert art_pkg.art_for_monster(guard) == drawing(index()["monsters"]["guard"])


@pytest.mark.parametrize("kind", ["humanoid", "beast", "undead"])
def test_unknown_monster_uses_creature_type(registry, kind):
    mon = monster(registry, monster_id="mystery_x", creature_type=kind)
    assert art_pkg.art_for_monster(mon) == drawing(index()["creature_types"][kind])


def test_unknown_monster_with_unknown_type_gives_none(registry):
    mon = monster(registry, monster_id="mystery_x", creature_type="zzz_unknown")
    assert art_pkg.art_for_monster(mon) is None


def test_unknown_monster_with_empty_type_gives_none(registry):
    mon = monster(registry, monster_id="mystery_x", creature_type="")
    assert art_pkg.art_for_monster(mon) is None


def test_load_art_holds_index_and_pictures_by_file_name():
    art = art_pkg.load_art()
    assert isinstance(art.index, art_pkg.ArtIndex)
    assert set(art.pictures) == {path.stem for path in DATA.glob("*.txt")}


def test_art_object_keeps_what_it_is_given():
    art = art_pkg.Art("i", {"a": "b"})
    assert (art.index, art.pictures) == ("i", {"a": "b"})
