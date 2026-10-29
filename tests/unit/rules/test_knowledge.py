# Ж3 (docs/plan-zh3.md, пп. 0.3-0.7): rules/knowledge.py -- чистые функции журнала знаний героя.
#   remember_fact(hero, entry, cfg) -> bool: дубль (kind, ref, текст без регистра/лишних пробелов)
#     -> False; полный лимит max_per_ref -> уходит старейшая (at_s, при равенстве ранняя);
#   shorten_text(text, limit); note_presence(hero, world, text, cfg) -> строки лога;
#   note_combat(hero, world, state, registry, cfg); note_favor(hero, god, detail, now_s, cfg);
#   note_secret(hero, npc, secret, now_s, cfg); met_npc_ids(bundle); backfill(bundle, cfg) -> число
#   новых записей (идемпотентна); ensure_journal -- только пустой журнал; spoils(text, secrets);
#   prompt_entries(hero, refs_by_kind, limit) -> {вид: {ref: [строки]}}.
import pytest
from protocol_kit import make_bundle

from ai_dm.config.settings import KnowledgeConfig
from ai_dm.rules.knowledge import (
    backfill,
    ensure_journal,
    entries_for,
    evict_oldest,
    has_entry,
    is_near,
    mentions,
    met_npc_ids,
    normalize,
    note_combat,
    note_favor,
    note_presence,
    note_secret,
    prompt_entries,
    remember_fact,
    rename_met,
    shorten_text,
    spoils,
)
from ai_dm.state.combat import CombatState, Participant
from ai_dm.state.knowledge import KnowledgeEntry
from ai_dm.state.memory import ChapterSummary, SceneSummary
from ai_dm.state.relations import NpcEvent, NpcSceneMemory
from ai_dm.state.scene import TurnRecord
from ai_dm.state.triggers import Secret
from ai_dm.state.world import NPC, God

CFG = KnowledgeConfig()
ONE = KnowledgeConfig(max_per_ref=1)


def entry(text="факт", kind="npc", ref="aldric", source="seen", at_s=0, from_ref=None):
    return KnowledgeEntry(
        kind=kind, ref=ref, text=text, source=source, at_s=at_s, from_ref=from_ref
    )


def hero_of(bundle):
    return bundle.heroes[0]


def texts(hero):
    return [e.text for e in hero.knowledge]


# normalize, has_entry, entries_for

def test_normalize_lowers_and_collapses_spaces():
    assert normalize("  Ключ   ОТ\tсклепа ") == "ключ от склепа"


def test_has_entry_by_kind_and_ref(registry):
    hero = hero_of(make_bundle(registry))
    hero.knowledge.append(entry())
    assert has_entry(hero, "npc", "aldric")
    assert not has_entry(hero, "location", "aldric")
    assert not has_entry(hero, "npc", "grakh")


def test_has_entry_by_text_prefix(registry):
    hero = hero_of(make_bundle(registry))
    hero.knowledge.append(entry("Знакомство: Олдрик"))
    assert has_entry(hero, "npc", "aldric", "Знакомство: ")
    assert not has_entry(hero, "npc", "aldric", "Место: ")


def test_has_entry_prefix_ignores_source(registry):
    hero = hero_of(make_bundle(registry))
    hero.knowledge.append(entry("Знакомство: слух", source="rumor"))
    assert has_entry(hero, "npc", "aldric", "Знакомство: ")


def test_has_entry_prefix_must_be_at_start(registry):
    hero = hero_of(make_bundle(registry))
    hero.knowledge.append(entry("Это не Знакомство: нет"))
    assert not has_entry(hero, "npc", "aldric", "Знакомство: ")


def test_has_entry_empty_prefix_matches_any_text(registry):
    hero = hero_of(make_bundle(registry))
    hero.knowledge.append(entry("что угодно", source="told"))
    assert has_entry(hero, "npc", "aldric")


def test_entries_for_keeps_journal_order(registry):
    hero = hero_of(make_bundle(registry))
    hero.knowledge += [entry("а"), entry("б", ref="grakh"), entry("в")]
    assert [e.text for e in entries_for(hero, "npc", "aldric")] == ["а", "в"]


# remember_fact

def test_remember_fact_adds_and_returns_true(registry):
    hero = hero_of(make_bundle(registry))
    assert remember_fact(hero, entry(), CFG) is True
    assert texts(hero) == ["факт"]


def test_remember_fact_duplicate_returns_false(registry):
    hero = hero_of(make_bundle(registry))
    remember_fact(hero, entry(), CFG)
    assert remember_fact(hero, entry(), CFG) is False
    assert len(hero.knowledge) == 1


def test_remember_fact_duplicate_ignores_case_and_spacing(registry):
    hero = hero_of(make_bundle(registry))
    remember_fact(hero, entry("Ключ  от склепа"), CFG)
    assert remember_fact(hero, entry(" ключ от  СКЛЕПА "), CFG) is False


def test_remember_fact_duplicate_ignores_source_and_time(registry):
    hero = hero_of(make_bundle(registry))
    remember_fact(hero, entry(source="seen", at_s=1), CFG)
    assert remember_fact(hero, entry(source="rumor", at_s=9), CFG) is False


def test_same_text_for_other_ref_is_new(registry):
    hero = hero_of(make_bundle(registry))
    remember_fact(hero, entry(ref="aldric"), CFG)
    assert remember_fact(hero, entry(ref="grakh"), CFG) is True


def test_same_ref_other_kind_is_new_and_not_counted_in_limit(registry):
    hero = hero_of(make_bundle(registry))
    remember_fact(hero, entry("а", kind="npc", ref="x"), ONE)
    assert remember_fact(hero, entry("а", kind="situation", ref="x"), ONE) is True
    assert len(hero.knowledge) == 2


def test_sixth_entry_evicts_the_oldest(registry):
    hero = hero_of(make_bundle(registry))
    for i in range(5):
        remember_fact(hero, entry(f"факт {i}", at_s=10 + i), CFG)
    assert remember_fact(hero, entry("факт 5", at_s=20), CFG) is True
    assert texts(hero) == [f"факт {i}" for i in range(1, 6)]


def test_fifth_entry_does_not_evict(registry):
    hero = hero_of(make_bundle(registry))
    for i in range(5):
        remember_fact(hero, entry(f"факт {i}", at_s=i), CFG)
    assert len(hero.knowledge) == 5


def test_eviction_takes_min_at_s_not_first_in_journal(registry):
    hero = hero_of(make_bundle(registry))
    hero.knowledge += [entry("новая", at_s=50), entry("старая", at_s=5), entry("средняя", at_s=20)]
    remember_fact(hero, entry("ещё", at_s=60), KnowledgeConfig(max_per_ref=3))
    assert texts(hero) == ["новая", "средняя", "ещё"]


def test_eviction_tie_takes_earlier_in_journal(registry):
    hero = hero_of(make_bundle(registry))
    hero.knowledge += [entry("первая", at_s=7), entry("вторая", at_s=7)]
    remember_fact(hero, entry("третья", at_s=8), KnowledgeConfig(max_per_ref=2))
    assert texts(hero) == ["вторая", "третья"]


def test_max_per_ref_one_replaces_entry(registry):
    hero = hero_of(make_bundle(registry))
    remember_fact(hero, entry("старое", at_s=1), ONE)
    remember_fact(hero, entry("новое", at_s=2), ONE)
    assert texts(hero) == ["новое"]


def test_eviction_touches_only_that_entity(registry):
    hero = hero_of(make_bundle(registry))
    remember_fact(hero, entry("чужое", ref="grakh", at_s=0), ONE)
    remember_fact(hero, entry("а", at_s=1), ONE)
    remember_fact(hero, entry("б", at_s=2), ONE)
    assert texts(hero) == ["чужое", "б"]


def test_evict_oldest_removes_one(registry):
    hero = hero_of(make_bundle(registry))
    hero.knowledge += [entry("а", at_s=3), entry("б", at_s=1)]
    evict_oldest(hero, "npc", "aldric")
    assert texts(hero) == ["а"]


# shorten_text

def test_shorten_keeps_text_at_limit():
    assert shorten_text("я" * 10, 10) == "я" * 10


def test_shorten_keeps_empty():
    assert shorten_text("", 10) == ""


def test_shorten_hard_cut_without_space():
    assert shorten_text("я" * 30, 10) == "я" * 9 + "…"


def test_shorten_cuts_at_last_space():
    assert shorten_text("слово слово слово", 15) == "слово слово…"


def test_shorten_result_never_exceeds_limit():
    assert len(shorten_text("слово " * 50, 20)) <= 20


def test_shorten_leading_space_is_not_a_cut_point():
    assert shorten_text(" " + "я" * 30, 10) == (" " + "я" * 8).rstrip() + "…"


# note_presence

def test_presence_records_visited_location_once(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    log = note_presence(hero, bundle.world, "", CFG)
    assert log == ["Журнал: место Вейл"]
    assert texts(hero) == ["Место: Вейл"]
    assert (hero.knowledge[0].kind, hero.knowledge[0].ref) == ("location", "vale")
    assert hero.knowledge[0].source == "seen"


def test_presence_second_call_adds_nothing(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    note_presence(hero, bundle.world, "", CFG)
    assert note_presence(hero, bundle.world, "", CFG) == []
    assert len(hero.knowledge) == 1


def test_presence_time_is_world_clock(registry):
    bundle = make_bundle(registry)
    bundle.world.clock.now_s = 4321
    hero = hero_of(bundle)
    note_presence(hero, bundle.world, "", CFG)
    assert hero.knowledge[0].at_s == 4321


def test_presence_unknown_location_writes_no_place(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    hero.location_id = "nowhere"
    assert note_presence(hero, bundle.world, "", CFG) == []
    assert hero.knowledge == []


def test_presence_new_location_gets_its_own_entry(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    note_presence(hero, bundle.world, "", CFG)
    hero.location_id = "forest"
    note_presence(hero, bundle.world, "", CFG)
    assert texts(hero) == ["Место: Вейл", "Место: Лес"]


def test_presence_npc_in_hero_location_named_in_text(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    log = note_presence(hero, bundle.world, "Герой кивнул ГРАКХУ.", CFG)
    assert "Журнал: знакомство Гракх" in log
    assert has_entry(hero, "npc", "grakh", "Знакомство: ")
    assert "Знакомство: Гракх" in texts(hero)


def test_presence_name_match_is_case_insensitive(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    note_presence(hero, bundle.world, "гракх молчит", CFG)
    assert has_entry(hero, "npc", "grakh")


def test_presence_npc_not_named_in_text_is_skipped(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    note_presence(hero, bundle.world, "Тихий вечер.", CFG)
    assert not has_entry(hero, "npc", "grakh")


def test_presence_npc_elsewhere_is_skipped(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    note_presence(hero, bundle.world, "Олдрик далеко, но о нём говорят.", CFG)
    assert not has_entry(hero, "npc", "aldric")


def test_presence_companion_counts_anywhere(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    bundle.world.npcs["aldric"].follows = hero.id
    note_presence(hero, bundle.world, "Олдрик ворчит.", CFG)
    assert has_entry(hero, "npc", "aldric", "Знакомство: ")


def test_presence_dead_npc_is_skipped(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    bundle.world.npcs["grakh"].status = "dead"
    note_presence(hero, bundle.world, "Гракх лежит.", CFG)
    assert not has_entry(hero, "npc", "grakh")


def test_presence_second_turn_adds_no_second_meeting(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    note_presence(hero, bundle.world, "Гракх", CFG)
    count = len(hero.knowledge)
    assert note_presence(hero, bundle.world, "Гракх снова", CFG) == []
    assert len(hero.knowledge) == count


def test_presence_does_not_meet_again_after_told_entry(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    hero.knowledge.append(entry("слух", ref="grakh", source="rumor"))
    note_presence(hero, bundle.world, "Гракх", CFG)
    assert has_entry(hero, "npc", "grakh", "Знакомство: ")


def test_narrator_seen_note_does_not_block_meeting(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    hero.knowledge.append(entry("Шрам через лицо", ref="grakh", source="seen"))
    log = note_presence(hero, bundle.world, "Гракх", CFG)
    assert "Журнал: знакомство Гракх" in log
    assert "Знакомство: Гракх" in texts(hero)


def test_narrator_seen_note_does_not_block_visit(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    hero.knowledge.append(entry("Рынок", kind="location", ref="vale", source="seen"))
    assert note_presence(hero, bundle.world, "", CFG) == ["Журнал: место Вейл"]


def test_presence_location_known_only_by_rumor_is_still_visited(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    hero.knowledge.append(entry("слух о Вейле", kind="location", ref="vale", source="rumor"))
    assert note_presence(hero, bundle.world, "", CFG) == ["Журнал: место Вейл"]
    assert has_entry(hero, "location", "vale", "Место: ")


# имя с начала слова (mentions)

def test_presence_russian_ending_is_found(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    note_presence(hero, bundle.world, "Я отдал письмо Гракху.", CFG)
    assert has_entry(hero, "npc", "grakh", "Знакомство: ")


def test_presence_name_inside_other_word_is_not_found(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    note_presence(hero, bundle.world, "Это сверхгракх!", CFG)
    assert not has_entry(hero, "npc", "grakh", "Знакомство: ")


def test_short_name_matches_whole_word_only(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    bundle.world.npcs["grakh"].name = "Ян"
    note_presence(hero, bundle.world, "Зашёл в Яндексе поискать.", CFG)
    assert not has_entry(hero, "npc", "grakh", "Знакомство: ")
    note_presence(hero, bundle.world, "Ян кивнул.", CFG)
    assert has_entry(hero, "npc", "grakh", "Знакомство: ")


def test_short_name_not_found_with_ending(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    bundle.world.npcs["grakh"].name = "Ян"
    note_presence(hero, bundle.world, "Подошёл к Яну.", CFG)
    assert not has_entry(hero, "npc", "grakh", "Знакомство: ")


def test_four_letter_name_takes_ending(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    bundle.world.npcs["grakh"].name = "Тарн"
    note_presence(hero, bundle.world, "Отвечаю Тарну.", CFG)
    assert has_entry(hero, "npc", "grakh", "Знакомство: ")


@pytest.mark.parametrize("text", [
    "подошёл к бранке", "бранка ушла", "видел бранку", "с бранкой", "о бранке", "нет бранки",
])
def test_mentions_name_in_cases(text):
    assert mentions("бранка", text)


@pytest.mark.parametrize("text", ["у матушки греты", "матушка грета здесь", "матушку грету"])
def test_mentions_two_word_name_in_cases(text):
    assert mentions("матушка грета", text)


def test_mentions_two_word_name_needs_every_word():
    assert not mentions("матушка грета", "только матушка пришла")
    assert not mentions("матушка грета", "только грета пришла")


@pytest.mark.parametrize("text", ["в яндексе", "яндекс", "к яну"])
def test_mentions_short_name_is_not_inside_longer_word(text):
    assert not mentions("ян", text)


def test_mentions_short_name_as_whole_word():
    assert mentions("ян", "ян кивнул")


def test_mentions_stem_is_not_inside_other_word():
    assert not mentions("бранка", "сверхбранка")
    assert not mentions("бранка", "бранковый")


def test_mentions_empty_name_is_never_found():
    assert not mentions("", "любой текст")


def test_met_by_name_with_ending_in_summary(registry):
    bundle = make_bundle(registry)
    bundle.memory.game_summary = "Герой помог Гракху."
    assert met_npc_ids(bundle) == ["grakh"]


def test_not_met_by_name_inside_other_word(registry):
    bundle = make_bundle(registry)
    bundle.memory.game_summary = "Про сверхгракх никто не слышал."
    assert met_npc_ids(bundle) == []


def test_short_name_not_met_by_longer_word_in_summary(registry):
    bundle = make_bundle(registry)
    bundle.world.npcs["grakh"].name = "Ян"
    bundle.memory.game_summary = "Купил что-то в Яндексе."
    assert met_npc_ids(bundle) == []


def test_short_name_met_as_whole_word_in_summary(registry):
    bundle = make_bundle(registry)
    bundle.world.npcs["grakh"].name = "Ян"
    bundle.memory.game_summary = "Ян ушёл."
    assert met_npc_ids(bundle) == ["grakh"]


# вытеснение записей движка

def test_eviction_keeps_engine_entry_while_others_exist(registry):
    hero = hero_of(make_bundle(registry))
    hero.knowledge += [entry("Знакомство: Олдрик", at_s=0)]
    hero.knowledge += [entry(f"факт {i}", source="told", at_s=10 + i) for i in range(4)]
    remember_fact(hero, entry("новый", source="told", at_s=50), CFG)
    got = texts(hero)
    assert "Знакомство: Олдрик" in got
    assert "факт 0" not in got


def test_engine_entry_survives_many_notes_without_rewrite(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    bundle.world.npcs["aldric"].location_id = "vale"
    note_presence(hero, bundle.world, "Олдрик", CFG)
    for i in range(12):
        remember_fact(hero, entry(f"факт {i}", source="told", at_s=100 + i), CFG)
        assert note_presence(hero, bundle.world, "Олдрик", CFG) == []
    assert has_entry(hero, "npc", "aldric", "Знакомство: ")
    assert len(entries_for(hero, "npc", "aldric")) == 5


def test_engine_entry_is_evicted_when_it_is_the_only_one(registry):
    hero = hero_of(make_bundle(registry))
    hero.knowledge.append(entry("Знакомство: Олдрик", at_s=0))
    remember_fact(hero, entry("новый", source="told", at_s=5), ONE)
    assert texts(hero) == ["новый"]


def test_all_engine_entries_oldest_one_goes(registry):
    hero = hero_of(make_bundle(registry))
    hero.knowledge += [
        entry("Знакомство: А", at_s=7), entry("Знакомство: Б", at_s=3),
    ]
    remember_fact(hero, entry("новый", source="told", at_s=9), KnowledgeConfig(max_per_ref=2))
    assert texts(hero) == ["Знакомство: А", "новый"]


def test_evict_oldest_skips_engine_entry_even_if_oldest(registry):
    hero = hero_of(make_bundle(registry))
    hero.knowledge += [entry("Знакомство: Олдрик", at_s=0), entry("факт", at_s=9)]
    evict_oldest(hero, "npc", "aldric")
    assert texts(hero) == ["Знакомство: Олдрик"]


def test_narrator_seen_entry_is_not_engine_and_can_be_evicted(registry):
    hero = hero_of(make_bundle(registry))
    hero.knowledge += [entry("Шрам", source="seen", at_s=0), entry("Знакомство: Олдрик", at_s=5)]
    evict_oldest(hero, "npc", "aldric")
    assert texts(hero) == ["Знакомство: Олдрик"]


def test_engine_prefix_with_non_seen_source_is_not_protected(registry):
    hero = hero_of(make_bundle(registry))
    hero.knowledge += [
        entry("Знакомство: слух", source="rumor", at_s=0), entry("Знакомство: Олдрик", at_s=5),
    ]
    evict_oldest(hero, "npc", "aldric")
    assert texts(hero) == ["Знакомство: Олдрик"]


# обрезка секрета и милости до предела

def test_note_secret_text_is_shortened_to_limit(registry):
    from ai_dm.state.knowledge import KNOWLEDGE_TEXT_MAX

    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    long = Secret.model_validate(
        {"id": "s2", "text": "слово " * 60, "reveal_if": {"flag": "f"}}
    )
    note_secret(hero, bundle.world.npcs["aldric"], long, 1, CFG)
    text = hero.knowledge[0].text
    assert len(text) <= KNOWLEDGE_TEXT_MAX
    assert text.endswith("…")


def test_note_secret_short_text_is_unchanged(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    note_secret(hero, bundle.world.npcs["aldric"], secret(), 1, CFG)
    assert hero.knowledge[0].text == "сестра жива"


def test_note_favor_text_is_shortened_to_limit(registry):
    from ai_dm.state.knowledge import KNOWLEDGE_TEXT_MAX

    hero = hero_of(make_bundle(registry))
    note_favor(hero, God(id="selune", name="Селунэ"), "причина " * 60, 1, CFG)
    text = hero.knowledge[0].text
    assert len(text) <= KNOWLEDGE_TEXT_MAX
    assert text.startswith("Селунэ: ")
    assert text.endswith("…")


def test_note_favor_short_text_is_unchanged(registry):
    hero = hero_of(make_bundle(registry))
    note_favor(hero, God(id="selune", name="Селунэ"), "доволен", 1, CFG)
    assert hero.knowledge[0].text == "Селунэ: доволен"


# note_combat

def fight(outcome, enemies=(("g1", "goblin_warrior"),), extra=()):
    parts = [Participant(ref="hero", side="heroes", group_id="h")]
    parts += [
        Participant(ref=ref, side="enemies", group_id="e", monster_id=monster)
        for ref, monster in enemies
    ]
    parts += list(extra)
    return CombatState(id="c1", zones=[], participants=parts, groups={}, outcome=outcome)


@pytest.mark.parametrize(
    "outcome,word",
    [
        ("victory", "победа"), ("fled", "бегство"), ("ended_by_master", "прерван"),
        ("hero_dead", "поражение"), ("defeat_pending", "поражение"), ("hero_dying", "поражение"),
        (None, "поражение"),
    ],
)
def test_combat_outcome_words(outcome, word, registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    note_combat(hero, bundle.world, fight(outcome), registry, CFG)
    assert texts(hero) == [f"Бой: Воин-гоблин — {word}"]


def test_combat_entry_is_creature_seen_by_monster_id(registry):
    bundle = make_bundle(registry)
    bundle.world.clock.now_s = 900
    hero = hero_of(bundle)
    note_combat(hero, bundle.world, fight("victory"), registry, CFG)
    e = hero.knowledge[0]
    assert (e.kind, e.ref, e.source, e.at_s) == ("creature", "goblin_warrior", "seen", 900)


def test_combat_two_same_monsters_give_one_entry(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    state = fight("victory", enemies=(("g1", "goblin_warrior"), ("g2", "goblin_warrior")))
    note_combat(hero, bundle.world, state, registry, CFG)
    assert len(hero.knowledge) == 1


def test_combat_different_monsters_give_entry_each(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    state = fight("victory", enemies=(("g1", "goblin_warrior"), ("b1", "black_bear")))
    note_combat(hero, bundle.world, state, registry, CFG)
    assert sorted(e.ref for e in hero.knowledge) == ["black_bear", "goblin_warrior"]


def test_combat_named_npc_enemy_is_skipped(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    state = fight("victory", enemies=(("grakh", "goblin_warrior"),))
    note_combat(hero, bundle.world, state, registry, CFG)
    assert hero.knowledge == []


def test_combat_heroes_side_is_skipped(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    ally = Participant(ref="w1", side="heroes", group_id="h", monster_id="black_bear")
    note_combat(hero, bundle.world, fight("victory", enemies=(), extra=(ally,)), registry, CFG)
    assert hero.knowledge == []


def test_combat_enemy_without_monster_id_is_skipped(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    stranger = Participant(ref="x", side="enemies", group_id="e")
    note_combat(hero, bundle.world, fight("victory", enemies=(), extra=(stranger,)), registry, CFG)
    assert hero.knowledge == []


def test_combat_enemy_after_foreign_heroes_side_monster_is_still_noted(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    ally = Participant(ref="w1", side="heroes", group_id="h", monster_id="black_bear")
    enemy = Participant(ref="g1", side="enemies", group_id="e", monster_id="goblin_warrior")
    state = CombatState(
        id="c1", zones=[], participants=[ally, enemy], groups={}, outcome="victory"
    )
    note_combat(hero, bundle.world, state, registry, CFG)
    assert texts(hero) == ["Бой: Воин-гоблин — победа"]


def test_combat_defector_on_heroes_side_is_noted(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    defector = Participant(ref="w1", side="heroes", group_id="h", monster_id="black_bear")
    state = fight("victory", enemies=(), extra=(defector,))
    note_combat(hero, bundle.world, state, registry, CFG, ["w1"])
    assert [e.ref for e in hero.knowledge] == ["black_bear"]


def test_second_fight_with_other_result_adds_entry(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    note_combat(hero, bundle.world, fight("fled"), registry, CFG)
    note_combat(hero, bundle.world, fight("victory"), registry, CFG)
    assert texts(hero) == ["Бой: Воин-гоблин — бегство", "Бой: Воин-гоблин — победа"]


def test_same_fight_result_twice_is_not_duplicated(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    note_combat(hero, bundle.world, fight("victory"), registry, CFG)
    note_combat(hero, bundle.world, fight("victory"), registry, CFG)
    assert len(hero.knowledge) == 1


# note_favor, note_secret

def test_note_favor_writes_god_entry(registry):
    hero = hero_of(make_bundle(registry))
    note_favor(hero, God(id="selune", name="Селунэ"), "доволен (помог жрецу)", 321, CFG)
    e = hero.knowledge[0]
    assert (e.kind, e.ref, e.text, e.source, e.at_s) == (
        "god", "selune", "Селунэ: доволен (помог жрецу)", "deduced", 321
    )


def test_note_favor_same_detail_is_not_duplicated(registry):
    hero = hero_of(make_bundle(registry))
    god = God(id="selune", name="Селунэ")
    note_favor(hero, god, "доволен", 1, CFG)
    note_favor(hero, god, "доволен", 2, CFG)
    assert len(hero.knowledge) == 1


def secret():
    return Secret.model_validate({"id": "s1", "text": "сестра жива", "reveal_if": {"flag": "f"}})


def test_note_secret_writes_secret_text(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    note_secret(hero, bundle.world.npcs["aldric"], secret(), 55, CFG)
    e = hero.knowledge[0]
    assert (e.kind, e.ref, e.text, e.source, e.at_s) == (
        "npc", "aldric", "сестра жива", "deduced", 55
    )


def test_note_secret_twice_is_not_duplicated(registry):
    bundle = make_bundle(registry)
    hero = hero_of(bundle)
    npc = bundle.world.npcs["aldric"]
    note_secret(hero, npc, secret(), 55, CFG)
    note_secret(hero, npc, secret(), 66, CFG)
    assert len(hero.knowledge) == 1


# met_npc_ids

def test_fresh_world_has_no_met_npcs(registry):
    assert met_npc_ids(make_bundle(registry)) == []


def test_met_by_known_to_player(registry):
    bundle = make_bundle(registry)
    bundle.world.npcs["aldric"].known_to_player = ["s"]
    assert met_npc_ids(bundle) == ["aldric"]


def test_met_by_memory(registry):
    bundle = make_bundle(registry)
    bundle.world.npcs["aldric"].memory = [
        NpcSceneMemory(
            scene_id="s", at_s=1, weight=0, events=[NpcEvent(kind="helped", turn_seq=1, text="х")]
        )
    ]
    assert met_npc_ids(bundle) == ["aldric"]


def test_met_by_follows_hero(registry):
    bundle = make_bundle(registry)
    bundle.world.npcs["aldric"].follows = "hero"
    assert met_npc_ids(bundle) == ["aldric"]


def test_follows_someone_else_is_not_met(registry):
    bundle = make_bundle(registry)
    bundle.world.npcs["aldric"].follows = "stranger"
    assert met_npc_ids(bundle) == []


@pytest.mark.parametrize("attitude", [-5, 3])
def test_met_by_nonzero_attitude(attitude, registry):
    bundle = make_bundle(registry)
    bundle.world.npcs["aldric"].attitude = attitude
    assert met_npc_ids(bundle) == ["aldric"]


def turn(narration, player_input=""):
    return TurnRecord(turn_seq=1, at_s=0, player_input=player_input, narration=narration)


def test_met_by_name_in_recent_narration(registry):
    bundle = make_bundle(registry)
    bundle.memory.recent_turns.append(turn("К столу подошёл олдрик."))
    assert met_npc_ids(bundle) == ["aldric"]


def test_met_by_name_in_recent_player_input(registry):
    bundle = make_bundle(registry)
    bundle.memory.recent_turns.append(turn("", player_input="Спрашиваю Олдрика"))
    assert met_npc_ids(bundle) == ["aldric"]


def test_met_by_name_in_scene_summary(registry):
    bundle = make_bundle(registry)
    bundle.memory.scenes.append(SceneSummary(id="s1", summary="Разговор с Гракх у ворот."))
    assert met_npc_ids(bundle) == ["grakh"]


def test_met_by_name_in_chapter_summary(registry):
    bundle = make_bundle(registry)
    bundle.memory.chapters.append(ChapterSummary(id="c1", number=1, summary="Гракх предал."))
    assert met_npc_ids(bundle) == ["grakh"]


def test_met_by_name_in_game_summary(registry):
    bundle = make_bundle(registry)
    bundle.memory.game_summary = "Давно герой помог Олдрик."
    assert met_npc_ids(bundle) == ["aldric"]


def test_text_parts_are_joined_without_extra_symbols(registry):
    bundle = make_bundle(registry)
    bundle.world.npcs["aldric"].name = "X"
    bundle.memory.recent_turns.append(turn("тихо", player_input="жду"))
    assert met_npc_ids(bundle) == []


def test_unnamed_npc_is_not_met_by_name(registry):
    bundle = make_bundle(registry)
    bundle.world.npcs["thug"] = NPC(id="thug", name="Громила", means=["кулаки"])
    bundle.memory.game_summary = "Громила ударил."
    assert met_npc_ids(bundle) == []


def test_location_alone_is_not_a_meeting(registry):
    bundle = make_bundle(registry)
    assert bundle.world.npcs["grakh"].location_id == "vale"
    assert met_npc_ids(bundle) == []


def test_dead_npc_can_be_met(registry):
    bundle = make_bundle(registry)
    npc = bundle.world.npcs["aldric"]
    npc.status = "dead"
    npc.attitude = 5
    assert met_npc_ids(bundle) == ["aldric"]


def test_met_ids_are_sorted(registry):
    bundle = make_bundle(registry)
    bundle.world.npcs["grakh"].attitude = 1
    bundle.world.npcs["aldric"].attitude = 1
    assert met_npc_ids(bundle) == ["aldric", "grakh"]


# backfill

def test_backfill_on_new_world_adds_nothing(registry):
    bundle = make_bundle(registry)
    assert backfill(bundle, CFG) == 0
    assert hero_of(bundle).knowledge == []


def test_backfill_writes_meeting_for_met_npc(registry):
    bundle = make_bundle(registry)
    bundle.world.npcs["aldric"].attitude = 2
    assert backfill(bundle, CFG) == 1
    e = hero_of(bundle).knowledge[0]
    assert (e.kind, e.ref, e.text, e.source) == ("npc", "aldric", "Знакомство: Олдрик", "seen")


def test_backfill_time_is_scene_start(registry):
    bundle = make_bundle(registry)
    bundle.world.clock.now_s = 9999
    bundle.session.current_scene.started_at_s = 120
    bundle.world.npcs["aldric"].attitude = 2
    backfill(bundle, CFG)
    assert hero_of(bundle).knowledge[0].at_s == 120


def test_backfill_time_without_scene_is_world_clock(registry):
    bundle = make_bundle(registry, with_scene=False)
    bundle.world.clock.now_s = 777
    bundle.world.npcs["aldric"].attitude = 2
    backfill(bundle, CFG)
    assert hero_of(bundle).knowledge[0].at_s == 777


def test_backfill_writes_visited_locations_only(registry):
    bundle = make_bundle(registry)
    bundle.world.locations["forest"].visited = True
    assert backfill(bundle, CFG) == 1
    assert texts(hero_of(bundle)) == ["Место: Лес"]


def test_backfill_does_not_write_current_unvisited_location(registry):
    bundle = make_bundle(registry)
    backfill(bundle, CFG)
    assert not has_entry(hero_of(bundle), "location", "vale")


def test_backfill_writes_known_secret_as_deduced(registry):
    bundle = make_bundle(registry)
    npc = bundle.world.npcs["aldric"]
    npc.secrets.append(secret())
    npc.known_to_player = ["s1"]
    assert backfill(bundle, CFG) == 2
    deduced = [e for e in hero_of(bundle).knowledge if e.source == "deduced"]
    assert [e.text for e in deduced] == ["сестра жива"]


def test_backfill_known_secret_is_npc_entry(registry):
    bundle = make_bundle(registry)
    npc = bundle.world.npcs["aldric"]
    npc.secrets.append(secret())
    npc.known_to_player = ["s1"]
    backfill(bundle, CFG)
    [e] = [e for e in hero_of(bundle).knowledge if e.source == "deduced"]
    assert (e.kind, e.ref) == ("npc", "aldric")


def test_backfill_counts_every_met_npc(registry):
    bundle = make_bundle(registry)
    bundle.world.npcs["aldric"].attitude = 1
    bundle.world.npcs["grakh"].attitude = 1
    assert backfill(bundle, CFG) == 2


def test_backfill_counts_npcs_and_visited_locations_together(registry):
    bundle = make_bundle(registry)
    bundle.world.npcs["aldric"].attitude = 1
    bundle.world.locations["forest"].visited = True
    bundle.world.locations["vale"].visited = True
    assert backfill(bundle, CFG) == 3


def test_backfill_skips_unknown_secret(registry):
    bundle = make_bundle(registry)
    npc = bundle.world.npcs["aldric"]
    npc.secrets.append(secret())
    npc.attitude = 1
    backfill(bundle, CFG)
    assert "сестра жива" not in texts(hero_of(bundle))


def test_backfill_is_idempotent(registry):
    bundle = make_bundle(registry)
    bundle.world.npcs["aldric"].attitude = 2
    bundle.world.locations["forest"].visited = True
    backfill(bundle, CFG)
    before = bundle.model_dump_json()
    assert backfill(bundle, CFG) == 0
    assert bundle.model_dump_json() == before


def test_backfill_is_deterministic_by_sorted_ids(registry):
    bundle = make_bundle(registry)
    bundle.world.npcs["grakh"].attitude = 1
    bundle.world.npcs["aldric"].attitude = 1
    backfill(bundle, CFG)
    assert [e.ref for e in hero_of(bundle).knowledge] == ["aldric", "grakh"]


def test_backfill_for_dead_met_npc(registry):
    bundle = make_bundle(registry)
    npc = bundle.world.npcs["aldric"]
    npc.status = "dead"
    npc.attitude = 1
    assert backfill(bundle, CFG) == 1


def test_backfill_uses_current_hero(registry):
    bundle = make_bundle(registry)
    bundle.world.npcs["aldric"].attitude = 1
    backfill(bundle, CFG)
    assert len(hero_of(bundle).knowledge) == 1


# ensure_journal

def test_ensure_journal_builds_empty_journal(registry):
    bundle = make_bundle(registry)
    bundle.world.npcs["aldric"].attitude = 1
    assert ensure_journal(bundle, CFG) == 1
    assert len(hero_of(bundle).knowledge) == 1


def test_ensure_journal_leaves_nonempty_journal_alone(registry):
    bundle = make_bundle(registry)
    bundle.world.npcs["aldric"].attitude = 1
    hero_of(bundle).knowledge.append(entry("слух", kind="situation", ref="rumor_1"))
    assert ensure_journal(bundle, CFG) == 0
    assert texts(hero_of(bundle)) == ["слух"]


def test_ensure_journal_on_new_world_stays_empty(registry):
    bundle = make_bundle(registry)
    assert ensure_journal(bundle, CFG) == 0


# spoils

SECRET = "сестра Олдрика обращена вампиром и прячется в склепе"


def test_spoils_false_without_secrets():
    assert spoils("что угодно", []) is False


def test_spoils_exact_text():
    assert spoils(SECRET, [SECRET]) is True


def test_spoils_unrelated_text():
    assert spoils("Любит эль и кости", [SECRET]) is False


def test_spoils_ignores_case_and_punctuation():
    assert spoils("СЕСТРА, Олдрика: обращена... вампиром! прячется; склепе", [SECRET]) is True


def test_spoils_threshold_is_inclusive():
    # значимые слова: alpha beta gamma delta epsilon -- 3 из 5 = 0.6
    secret = "alpha beta gamma delta epsilon"
    assert spoils("alpha beta gamma", [secret]) is True
    assert spoils("alpha beta", [secret]) is False


def test_spoils_ignores_short_words():
    # слова короче 4 знаков не значимы: ключ -- только «склеп» и «вход»
    assert spoils("вот он и тут под ним", ["вот он и тут склеп вход"]) is False
    assert spoils("склеп вход", ["вот он и тут склеп вход"]) is True


def test_spoils_secret_without_significant_words_never_matches():
    assert spoils("он и я", ["он и я"]) is False


def test_spoils_checks_any_secret():
    assert spoils(SECRET, ["совсем другое дело про золото", SECRET]) is True


# prompt_entries

ALL = {"npc": None, "location": None, "faction": None, "god": None, "creature": None,
       "situation": None}


def journal_hero(registry, *entries):
    hero = hero_of(make_bundle(registry))
    hero.knowledge += list(entries)
    return hero


def test_prompt_empty_journal_is_empty(registry):
    assert prompt_entries(journal_hero(registry), ALL, 30) == {}


def test_prompt_groups_by_kind_and_ref_with_source(registry):
    hero = journal_hero(registry, entry("Хранит ключ", source="rumor"))
    assert prompt_entries(hero, ALL, 30) == {"npc": {"aldric": ["Хранит ключ (rumor)"]}}


def test_prompt_told_line_has_teller(registry):
    hero = journal_hero(registry, entry("Хранит ключ", source="told", from_ref="mira"))
    assert prompt_entries(hero, ALL, 30)["npc"]["aldric"] == ["Хранит ключ (told: mira)"]


def test_prompt_skips_kind_not_in_refs(registry):
    hero = journal_hero(registry, entry("а", kind="creature", ref="goblin_warrior"))
    assert prompt_entries(hero, {"npc": None}, 30) == {}


def test_prompt_filters_ref_by_set(registry):
    hero = journal_hero(registry, entry("а", ref="aldric"), entry("б", ref="grakh"))
    assert prompt_entries(hero, {"npc": {"grakh"}}, 30) == {"npc": {"grakh": ["б (seen)"]}}


def test_prompt_empty_ref_set_skips_kind(registry):
    hero = journal_hero(registry, entry("а"))
    assert prompt_entries(hero, {"npc": set()}, 30) == {}


def test_prompt_none_refs_take_all(registry):
    hero = journal_hero(registry, entry("а", ref="aldric"), entry("б", ref="grakh"))
    assert sorted(prompt_entries(hero, ALL, 30)["npc"]) == ["aldric", "grakh"]


def test_prompt_hides_meeting_entry(registry):
    hero = journal_hero(registry, entry("Знакомство: Олдрик"))
    assert prompt_entries(hero, ALL, 30) == {}


def test_prompt_hides_visited_entry(registry):
    hero = journal_hero(registry, entry("Место: Вейл", kind="location", ref="vale"))
    assert prompt_entries(hero, ALL, 30) == {}


def test_prompt_shows_engine_prefix_text_from_other_source(registry):
    hero = journal_hero(registry, entry("Знакомство: слух", source="rumor"))
    assert prompt_entries(hero, ALL, 30) != {}


def test_prompt_shows_seen_without_engine_prefix(registry):
    hero = journal_hero(registry, entry("Бой: Воин-гоблин — победа", kind="creature", ref="g"))
    assert prompt_entries(hero, ALL, 30) == {
        "creature": {"g": ["Бой: Воин-гоблин — победа (seen)"]}
    }


def test_prompt_limit_keeps_newest_by_time(registry):
    hero = journal_hero(
        registry, entry("новая", at_s=30), entry("старая", at_s=10), entry("средняя", at_s=20)
    )
    got = prompt_entries(hero, ALL, 2)
    assert got == {"npc": {"aldric": ["новая (seen)", "средняя (seen)"]}}


def test_prompt_limit_tie_prefers_later_in_journal(registry):
    hero = journal_hero(registry, entry("первая", at_s=5), entry("вторая", at_s=5))
    assert prompt_entries(hero, ALL, 1) == {"npc": {"aldric": ["вторая (seen)"]}}


def test_prompt_limit_zero_gives_nothing(registry):
    assert prompt_entries(journal_hero(registry, entry("а")), ALL, 0) == {}


def test_prompt_limit_counts_only_selected_entries(registry):
    hero = journal_hero(
        registry, entry("нужная", at_s=1), entry("лишняя", ref="grakh", at_s=99)
    )
    assert prompt_entries(hero, {"npc": {"aldric"}}, 1) == {"npc": {"aldric": ["нужная (seen)"]}}


def test_prompt_lines_keep_journal_order_not_time_order(registry):
    hero = journal_hero(registry, entry("б", at_s=20), entry("а", at_s=10))
    assert prompt_entries(hero, ALL, 30)["npc"]["aldric"] == ["б (seen)", "а (seen)"]


def test_prompt_kinds_follow_canonical_order(registry):
    hero = journal_hero(
        registry,
        entry("с", kind="situation", ref="plague"),
        entry("н", kind="npc", ref="aldric"),
        entry("г", kind="god", ref="selune"),
    )
    assert list(prompt_entries(hero, ALL, 30)) == ["npc", "god", "situation"]


def test_prompt_refs_sorted_alphabetically(registry):
    hero = journal_hero(registry, entry("а", ref="zed"), entry("б", ref="aldric"))
    assert list(prompt_entries(hero, ALL, 30)["npc"]) == ["aldric", "zed"]


# Ж1 (docs/plan-zh1.md, п. 0.6): скрытое имя выжившего боя -- note_presence по имени его не ищет,
# is_near, rename_met, is_met/backfill читают shown_name

def survivor(bundle, **kwargs):
    base = {
        "id": "goblin_warrior_1", "name": "Гракх", "means": ["бой"], "origin": "engine",
        "location_id": "vale", "named": False,
        "combat": {"monster_id": "goblin_warrior", "label": "Воин-гоблин 1"},
    }
    npc = NPC(**{**base, **kwargs})
    bundle.world.npcs[npc.id] = npc
    return npc


def test_presence_hidden_name_in_text_is_not_a_meeting(registry):
    bundle = make_bundle(registry)
    survivor(bundle)
    note_presence(hero_of(bundle), bundle.world, "Гракх опускает взгляд.", CFG)
    assert not has_entry(hero_of(bundle), "npc", "goblin_warrior_1")


def test_presence_hidden_name_gives_no_log_line(registry):
    bundle = make_bundle(registry)
    survivor(bundle, name="Мурк")
    log = note_presence(hero_of(bundle), bundle.world, "Мурк", CFG)
    assert all("знакомство" not in line for line in log)


def test_presence_known_name_of_survivor_is_a_meeting(registry):
    bundle = make_bundle(registry)
    survivor(bundle, known_name="Гракх")
    note_presence(hero_of(bundle), bundle.world, "Гракх опускает взгляд.", CFG)
    assert "Знакомство: Гракх" in texts(hero_of(bundle))


def test_presence_pack_npc_name_still_found(registry):
    bundle = make_bundle(registry)
    note_presence(hero_of(bundle), bundle.world, "Гракх молчит.", CFG)
    assert "Знакомство: Гракх" in texts(hero_of(bundle))


def test_is_near_same_location(registry):
    bundle = make_bundle(registry)
    assert is_near(bundle.world.npcs["grakh"], hero_of(bundle)) is True


def test_is_near_follower_elsewhere(registry):
    bundle = make_bundle(registry)
    npc = bundle.world.npcs["aldric"]
    npc.follows = hero_of(bundle).id
    assert is_near(npc, hero_of(bundle)) is True


def test_is_near_other_location_is_false(registry):
    bundle = make_bundle(registry)
    assert is_near(bundle.world.npcs["aldric"], hero_of(bundle)) is False


def test_is_near_dead_npc_is_false(registry):
    bundle = make_bundle(registry)
    npc = bundle.world.npcs["grakh"]
    npc.status = "dead"
    assert is_near(npc, hero_of(bundle)) is False


def test_rename_met_updates_meeting_text_to_shown_name(registry):
    bundle = make_bundle(registry)
    npc = survivor(bundle)
    hero = hero_of(bundle)
    hero.knowledge.append(entry("Знакомство: Воин-гоблин 1", ref=npc.id))
    npc.known_name = "Гракх"
    rename_met(hero, npc)
    assert texts(hero) == ["Знакомство: Гракх"]


def test_rename_met_keeps_other_entries_of_the_npc(registry):
    bundle = make_bundle(registry)
    npc = survivor(bundle, known_name="Гракх")
    hero = hero_of(bundle)
    hero.knowledge.append(entry("Знакомство: Воин-гоблин 1", ref=npc.id))
    hero.knowledge.append(entry("любит эль", ref=npc.id, source="told"))
    rename_met(hero, npc)
    assert texts(hero) == ["Знакомство: Гракх", "любит эль"]


def test_rename_met_does_not_touch_other_npcs(registry):
    bundle = make_bundle(registry)
    npc = survivor(bundle, known_name="Гракх")
    hero = hero_of(bundle)
    hero.knowledge.append(entry("Знакомство: Олдрик", ref="aldric"))
    rename_met(hero, npc)
    assert texts(hero) == ["Знакомство: Олдрик"]


def test_hidden_survivor_is_not_met_by_real_name_in_text(registry):
    bundle = make_bundle(registry)
    survivor(bundle, named=True)
    bundle.memory.game_summary = "Гракх ударил."
    assert "goblin_warrior_1" not in met_npc_ids(bundle)


def test_hidden_survivor_is_met_by_label_in_text(registry):
    bundle = make_bundle(registry)
    survivor(bundle, named=True)
    bundle.memory.game_summary = "Воин-гоблин 1 сдался."
    assert "goblin_warrior_1" in met_npc_ids(bundle)


def test_survivor_with_known_name_is_met_by_that_name(registry):
    bundle = make_bundle(registry)
    survivor(bundle, named=True, known_name="Мурк", name="Другое")
    bundle.memory.game_summary = "Мурк сдался."
    assert "goblin_warrior_1" in met_npc_ids(bundle)


def test_backfill_hidden_survivor_is_written_by_label(registry):
    bundle = make_bundle(registry)
    survivor(bundle, attitude=20)
    backfill(bundle, CFG)
    assert texts(hero_of(bundle)) == ["Знакомство: Воин-гоблин 1"]


def test_backfill_survivor_with_known_name_is_written_by_it(registry):
    bundle = make_bundle(registry)
    survivor(bundle, attitude=20, known_name="Гракх")
    backfill(bundle, CFG)
    assert texts(hero_of(bundle)) == ["Знакомство: Гракх"]
