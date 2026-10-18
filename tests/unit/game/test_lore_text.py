# Ж3 (docs/plan-zh3.md, пп. 0.9, 12): game/lore_text.py -- текст журнала знаний для /lore и окна.
#   lore_groups(hero, world, registry) -> [(вид, [(ref, имя, записи)])]: виды по KNOWLEDGE_KINDS,
#     сущности по имени без регистра, пустые виды опущены; имя -- у npc/location/faction/god из
#     мира, у creature из реестра, у situation и неизвестного id -- сам ref;
#   find_entity(groups, query) -> (вид, ref, имя, записи) | None: подстрока имени или ref без
#     регистра, точное совпадение первым;
#   entry_line(entry, world): «— текст (источник[: рассказавший], дата)»;
#   lore_lines(hero, world, registry, arg) -> строки ответа /lore.
import pytest
from protocol_kit import make_bundle

from ai_dm.game.lore_text import (
    KIND_TITLES,
    LORE_EMPTY,
    LORE_HINT,
    SOURCE_WORDS,
    date_of,
    entity_name,
    entry_line,
    entry_lines,
    find_entity,
    lore_groups,
    lore_lines,
)
from ai_dm.state.knowledge import KNOWLEDGE_KINDS, KNOWLEDGE_SOURCES, KnowledgeEntry
from ai_dm.state.world import Faction, God


def entry(text="факт", kind="npc", ref="aldric", source="seen", at_s=0, from_ref=None):
    return KnowledgeEntry(
        kind=kind, ref=ref, text=text, source=source, at_s=at_s, from_ref=from_ref
    )


@pytest.fixture
def bundle(registry):
    b = make_bundle(registry)
    b.world.factions["guild"] = Faction(id="guild", name="Гильдия")
    b.world.pantheon["selune"] = God(id="selune", name="Селунэ")
    return b


def hero_of(bundle):
    return bundle.heroes[0]


def fill(bundle, *entries):
    hero_of(bundle).knowledge += list(entries)


# словари

def test_kind_titles_cover_every_kind():
    assert sorted(KIND_TITLES) == sorted(KNOWLEDGE_KINDS)


def test_source_words_cover_every_source():
    assert sorted(SOURCE_WORDS) == sorted(KNOWLEDGE_SOURCES)


def test_empty_message_is_not_empty_string():
    assert LORE_EMPTY
    assert LORE_HINT.startswith("Подробнее")


# entity_name

@pytest.mark.parametrize(
    "kind,ref,name",
    [
        ("npc", "aldric", "Олдрик"), ("location", "forest", "Лес"), ("faction", "guild", "Гильдия"),
        ("god", "selune", "Селунэ"), ("creature", "goblin_warrior", "Воин-гоблин"),
    ],
)
def test_entity_name_from_source(kind, ref, name, bundle, registry):
    assert entity_name(kind, ref, bundle.world, registry) == name


@pytest.mark.parametrize(
    "kind,ref",
    [
        ("npc", "ghost"), ("location", "ghost"), ("faction", "ghost"), ("god", "ghost"),
        ("creature", "ghost"), ("situation", "plague"),
    ],
)
def test_entity_name_falls_back_to_ref(kind, ref, bundle, registry):
    assert entity_name(kind, ref, bundle.world, registry) == ref


# lore_groups

def test_empty_journal_has_no_groups(bundle, registry):
    assert lore_groups(hero_of(bundle), bundle.world, registry) == []


def test_groups_follow_kind_order_and_skip_empty_kinds(bundle, registry):
    fill(
        bundle,
        entry(kind="situation", ref="plague"),
        entry(kind="god", ref="selune"),
        entry(kind="npc", ref="aldric"),
    )
    groups = lore_groups(hero_of(bundle), bundle.world, registry)
    assert [kind for kind, _ in groups] == ["npc", "god", "situation"]


def test_group_item_is_ref_name_entries(bundle, registry):
    first = entry("а")
    second = entry("б")
    fill(bundle, first, second)
    [(kind, [(ref, name, entries)])] = lore_groups(hero_of(bundle), bundle.world, registry)
    assert (kind, ref, name) == ("npc", "aldric", "Олдрик")
    assert entries == [first, second]


def test_items_sorted_by_name_not_by_ref(bundle, registry):
    fill(bundle, entry(ref="grakh"), entry(ref="aldric"))
    [(_, items)] = lore_groups(hero_of(bundle), bundle.world, registry)
    assert [name for _, name, _ in items] == ["Гракх", "Олдрик"]


def test_items_sort_ignores_case(bundle, registry):
    bundle.world.npcs["aldric"].name = "олдрик"
    fill(bundle, entry(ref="grakh"), entry(ref="aldric"))
    [(_, items)] = lore_groups(hero_of(bundle), bundle.world, registry)
    assert [name for _, name, _ in items] == ["Гракх", "олдрик"]


def test_items_sort_by_lowercased_name(bundle, registry):
    # «ё» в нижнем регистре стоит после «я», в верхнем -- перед «а»
    bundle.world.npcs["aldric"].name = "Ёж"
    bundle.world.npcs["grakh"].name = "Ян"
    fill(bundle, entry(ref="grakh"), entry(ref="aldric"))
    [(_, items)] = lore_groups(hero_of(bundle), bundle.world, registry)
    assert [name for _, name, _ in items] == ["Ян", "Ёж"]


def test_entries_of_other_entities_are_separate(bundle, registry):
    fill(bundle, entry(ref="aldric"), entry(ref="grakh"), entry("ещё", ref="aldric"))
    [(_, items)] = lore_groups(hero_of(bundle), bundle.world, registry)
    assert {ref: len(entries) for ref, _, entries in items} == {"aldric": 2, "grakh": 1}


# find_entity

def groups_of(bundle, registry):
    return lore_groups(hero_of(bundle), bundle.world, registry)


def test_find_by_name_substring_ignoring_case(bundle, registry):
    fill(bundle, entry(ref="grakh"))
    hit = find_entity(groups_of(bundle, registry), "ГРАК")
    assert hit[:3] == ("npc", "grakh", "Гракх")


def test_find_returns_kind_ref_name_entries(bundle, registry):
    e = entry(ref="grakh")
    fill(bundle, e)
    assert find_entity(groups_of(bundle, registry), "гракх") == ("npc", "grakh", "Гракх", [e])


def test_find_by_ref_substring(bundle, registry):
    fill(bundle, entry(ref="grakh"))
    assert find_entity(groups_of(bundle, registry), "rak")[1] == "grakh"


def test_find_strips_query(bundle, registry):
    fill(bundle, entry(ref="grakh"))
    assert find_entity(groups_of(bundle, registry), "  гракх  ") is not None


def test_find_nothing_gives_none(bundle, registry):
    fill(bundle, entry(ref="grakh"))
    assert find_entity(groups_of(bundle, registry), "дракон") is None


def test_find_prefers_exact_name_over_earlier_substring(bundle, registry):
    bundle.world.npcs["grakh"].name = "Гракхи"
    bundle.world.npcs["aldric"].name = "Гракх"
    fill(bundle, entry(ref="grakh"), entry(ref="aldric"))
    assert find_entity(groups_of(bundle, registry), "гракх")[1] == "aldric"


def test_find_prefers_exact_ref(bundle, registry):
    fill(bundle, entry(kind="situation", ref="plague"), entry(kind="situation", ref="plague_2"))
    assert find_entity(groups_of(bundle, registry), "plague")[1] == "plague"


def test_find_prefers_exact_name_sorted_after_substring_match(bundle, registry):
    bundle.world.npcs["aldric"].name = "Аккот"
    bundle.world.npcs["grakh"].name = "Кот"
    fill(bundle, entry(ref="aldric"), entry(ref="grakh"))
    assert find_entity(groups_of(bundle, registry), "КОТ")[1] == "grakh"


def test_find_prefers_exact_ref_sorted_after_name_match(bundle, registry):
    bundle.world.npcs["aldric"].name = "Big grakh"
    fill(bundle, entry(ref="aldric"), entry(ref="grakh"))
    assert find_entity(groups_of(bundle, registry), "GRAKH")[1] == "grakh"


def test_find_takes_first_in_group_order_when_not_exact(bundle, registry):
    fill(bundle, entry(ref="grakh"), entry(ref="aldric"))
    assert find_entity(groups_of(bundle, registry), "к")[1] == "grakh"


# date_of, entry_line

def test_date_of_uses_given_time_not_current(bundle):
    bundle.world.clock.now_s = 10 * 86400
    assert date_of(bundle.world.clock, 0) != date_of(bundle.world.clock, 10 * 86400)


def test_date_of_does_not_change_clock(bundle):
    bundle.world.clock.now_s = 500
    date_of(bundle.world.clock, 0)
    assert bundle.world.clock.now_s == 500


def test_date_of_looks_like_a_date(bundle):
    assert len(date_of(bundle.world.clock, 0).split("-")) == 3


@pytest.mark.parametrize("source", KNOWLEDGE_SOURCES)
def test_entry_line_has_source_word_and_date(source, bundle):
    line = entry_line(entry("Хранит ключ", source=source), bundle.world)
    assert line == f"— Хранит ключ ({SOURCE_WORDS[source]}, {date_of(bundle.world.clock, 0)})"


def test_entry_line_unknown_source_is_shown_as_is(bundle):
    line = entry_line(entry("Хранит ключ", source="legend"), bundle.world)
    assert line == f"— Хранит ключ (legend, {date_of(bundle.world.clock, 0)})"


def test_entry_line_with_teller_name(bundle):
    line = entry_line(entry(source="told", from_ref="grakh"), bundle.world)
    assert f"({SOURCE_WORDS['told']}: Гракх, " in line


def test_entry_line_with_unknown_teller_shows_id(bundle):
    line = entry_line(entry(source="told", from_ref="ghost"), bundle.world)
    assert f"({SOURCE_WORDS['told']}: ghost, " in line


def test_entry_line_uses_entry_time(bundle):
    old = entry_line(entry(at_s=0), bundle.world)
    new = entry_line(entry(at_s=30 * 86400), bundle.world)
    assert old != new


def test_entry_lines_keep_order(bundle):
    lines = entry_lines([entry("а"), entry("б")], bundle.world)
    assert [line.split()[1] for line in lines] == ["а", "б"]


# lore_lines

def test_lore_lines_empty_journal(bundle, registry):
    assert lore_lines(hero_of(bundle), bundle.world, registry, "") == [LORE_EMPTY]


def test_lore_lines_empty_journal_with_query_is_still_empty_message(bundle, registry):
    assert lore_lines(hero_of(bundle), bundle.world, registry, "гракх") == [LORE_EMPTY]


def test_lore_lines_overview_lists_kinds_and_counts(bundle, registry):
    fill(bundle, entry("а"), entry("б"), entry(ref="grakh"), entry(kind="god", ref="selune"))
    lines = lore_lines(hero_of(bundle), bundle.world, registry, "")
    assert lines == [
        "Люди:", "  Гракх — 1 зап.", "  Олдрик — 2 зап.",
        "Боги:", "  Селунэ — 1 зап.",
        "", LORE_HINT,
    ]


def test_lore_lines_blank_arg_is_overview(bundle, registry):
    fill(bundle, entry())
    assert lore_lines(hero_of(bundle), bundle.world, registry, "   ")[-1] == LORE_HINT


def test_lore_lines_query_shows_entity_entries(bundle, registry):
    fill(bundle, entry("Хранит ключ", source="rumor"), entry("Любит эль"))
    lines = lore_lines(hero_of(bundle), bundle.world, registry, "олдрик")
    assert lines[0] == "Олдрик (Люди):"
    assert lines[1] == f"  — Хранит ключ (слух, {date_of(bundle.world.clock, 0)})"
    assert len(lines) == 3


def test_lore_lines_query_other_entity_not_included(bundle, registry):
    fill(bundle, entry("про Олдрика"), entry("про Гракха", ref="grakh"))
    lines = lore_lines(hero_of(bundle), bundle.world, registry, "гракх")
    assert "про Олдрика" not in "\n".join(lines)


def test_lore_lines_query_not_found(bundle, registry):
    fill(bundle, entry())
    assert lore_lines(hero_of(bundle), bundle.world, registry, " дракон ") == [
        "Не найдено: дракон.", LORE_HINT,
    ]


def test_lore_lines_include_engine_entries(bundle, registry):
    fill(bundle, entry("Знакомство: Олдрик"), entry("Место: Вейл", kind="location", ref="vale"))
    text = "\n".join(lore_lines(hero_of(bundle), bundle.world, registry, "вейл"))
    assert "Место: Вейл" in text


def test_lore_lines_creature_uses_bestiary_title(bundle, registry):
    fill(bundle, entry("Бой: Воин-гоблин — победа", kind="creature", ref="goblin_warrior"))
    lines = lore_lines(hero_of(bundle), bundle.world, registry, "")
    assert lines[:2] == [f"{KIND_TITLES['creature']}:", "  Воин-гоблин — 1 зап."]
