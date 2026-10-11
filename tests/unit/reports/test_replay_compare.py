# Ожидаемый API (этап 6а, P2): ai_dm.reports.replay.compare(expected, actual) -> list[str] --
# расхождения двух SaveBundle по сериализованному виду; пусто -- совпало. Время реального мира
# (manifest.saved_at) в сравнении не участвует, всё остальное -- участвует.
from reports_kit import make_capture

from ai_dm.reports.replay import compare
from ai_dm.state.memory import ChronicleEntry


def two_bundles(registry):
    base = make_capture(registry).before
    return base, base.model_copy(deep=True)


def test_equal_bundles_have_no_differences(registry):
    expected, actual = two_bundles(registry)
    assert compare(expected, actual) == []


def test_saved_at_is_ignored(registry):
    expected, actual = two_bundles(registry)
    actual.manifest.saved_at = "2030-05-05T05:05:05Z"
    assert compare(expected, actual) == []


def test_rng_state_difference_is_reported(registry):
    expected, actual = two_bundles(registry)
    actual.world.rng.state += 1
    assert compare(expected, actual) != []


def test_world_difference_is_reported(registry):
    expected, actual = two_bundles(registry)
    actual.world.mortality_per_day += 1
    assert compare(expected, actual) != []


def test_hero_difference_is_reported(registry):
    expected, actual = two_bundles(registry)
    actual.heroes[0].creature.hp_current -= 1
    assert compare(expected, actual) != []


def test_session_difference_is_reported(registry):
    expected, actual = two_bundles(registry)
    actual.session.current_scene = None
    assert compare(expected, actual) != []


def test_memory_difference_is_reported(registry):
    expected, actual = two_bundles(registry)
    actual.memory.game_summary = "новое"
    assert compare(expected, actual) != []


def test_chronicle_difference_is_reported(registry):
    expected, actual = two_bundles(registry)
    actual.chronicle.entries.append(ChronicleEntry(at_s=1, kind="event", text="было"))
    assert compare(expected, actual) != []


def test_other_manifest_field_is_not_ignored(registry):
    expected, actual = two_bundles(registry)
    actual.manifest.current_hero_id = "other"
    assert compare(expected, actual) != []


def test_manifest_slot_difference_is_not_ignored(registry):
    expected, actual = two_bundles(registry)
    actual.manifest.slot = "other"
    assert compare(expected, actual) != []


def test_differences_are_strings_and_one_per_changed_part(registry):
    expected, actual = two_bundles(registry)
    actual.world.rng.state += 1
    actual.heroes[0].creature.hp_current -= 1
    result = compare(expected, actual)
    assert len(result) >= 2
    assert all(isinstance(line, str) and line for line in result)


def test_time_difference_next_to_real_one_reports_only_real(registry):
    expected, actual = two_bundles(registry)
    actual.manifest.saved_at = "2030-05-05T05:05:05Z"
    assert compare(expected, actual) == []
    actual.world.rng.state += 1
    assert len(compare(expected, actual)) >= 1


def test_many_differences_are_cut_with_a_tail_line(registry):
    expected, actual = two_bundles(registry)
    actual.world.flags = {f"flag_{n:02d}": True for n in range(25)}
    result = compare(expected, actual)
    assert len(result) == 21
    assert "и ещё 5" in result[-1]


def test_exactly_at_limit_is_not_cut(registry):
    expected, actual = two_bundles(registry)
    actual.world.flags = {f"flag_{n:02d}": True for n in range(20)}
    result = compare(expected, actual)
    assert len(result) == 20
    assert "ещё" not in result[-1]


def test_difference_line_names_the_field_and_both_values(registry):
    expected, actual = two_bundles(registry)
    actual.world.mortality_per_day = 777
    (line,) = compare(expected, actual)
    assert line.startswith("world.mortality_per_day")
    assert "777" in line


def test_list_of_other_length_is_one_difference(registry):
    expected, actual = two_bundles(registry)
    actual.heroes = []
    result = compare(expected, actual)
    assert len(result) == 1
    assert result[0].startswith("heroes")


def test_list_element_difference_has_indexed_path(registry):
    expected, actual = two_bundles(registry)
    actual.heroes[0].creature.hp_current -= 1
    (line,) = compare(expected, actual)
    assert line.startswith("heroes[0].creature.hp_current")


def test_difference_line_shows_expected_and_actual_values(registry):
    expected, actual = two_bundles(registry)
    expected.world.mortality_per_day = 111
    actual.world.mortality_per_day = 222
    (line,) = compare(expected, actual)
    assert "ожидалось 111" in line
    assert "получено 222" in line


def test_key_only_in_actual_is_marked_missing_in_expected(registry):
    expected, actual = two_bundles(registry)
    actual.world.flags = {"new_flag": True}
    (line,) = compare(expected, actual)
    assert line.startswith("world.flags.new_flag")
    assert "ожидалось '<нет>'" in line


def test_key_only_in_expected_is_marked_missing_in_actual(registry):
    expected, actual = two_bundles(registry)
    expected.world.flags = {"old_flag": True}
    (line,) = compare(expected, actual)
    assert "получено '<нет>'" in line


def test_long_values_are_cut_to_80_chars(registry):
    expected, actual = two_bundles(registry)
    expected.memory.game_summary = "а" * 300
    actual.memory.game_summary = "б" * 300
    (line,) = compare(expected, actual)
    assert "а" * 79 in line
    assert "а" * 80 not in line
    assert "б" * 79 in line
    assert "б" * 80 not in line


def test_dump_is_plain_json_without_saved_at(registry):
    import json

    from ai_dm.reports.replay import dump

    data = dump(make_capture(registry).before)
    assert json.loads(json.dumps(data)) == data
    assert "saved_at" not in data["manifest"]
    assert data["manifest"]["world_id"] == "w1"


def test_missing_value_is_not_the_same_as_none():
    from ai_dm.reports.replay import diff

    lines = []
    diff("", {}, {"a": None}, lines)
    assert len(lines) == 1
    lines = []
    diff("", {"a": None}, {}, lines)
    assert len(lines) == 1
