# Ожидаемый API (STAGE4-P3 spec, §2): ai_dm.master.context -- STAGES, Candidates, ContextPlan,
# window_budget, budget, estimate_tokens, request_tokens, recent_window, plan.
# Единый сборщик контекста: бюджет Д1 (min(80% окна, context_cap)), вытеснение ТЗ 11 по ступеням
# turns -> scenes -> npcs -> locations, G1 (неустранимое > cap -> потолок = 80% окна).
# Здесь plan проверяется на искусственном render: размеры известны, пороги считаются точно.
import json

import pytest
from master_kit import app_cfg, turn_record
from pydantic import ValidationError

from ai_dm.llm.types import ChatRequest, Message, Text
from ai_dm.master.context import (
    STAGES,
    Candidates,
    ContextPlan,
    budget,
    estimate_tokens,
    plan,
    recent_window,
    request_tokens,
    window_budget,
)
from ai_dm.state.memory import ChapterSummary, Memory, SceneSummary

OPUS = "claude-opus-5-5"
HAIKU = "claude-haiku-4-5"
CPT = 1.0
BIG = 10**9


def memory_with(count):
    return Memory(recent_turns=[turn_record(n) for n in range(1, count + 1)])


# окно recent_turns

def test_recent_window_takes_last_n():
    turns = recent_window(memory_with(12), 8)
    assert [t.turn_seq for t in turns] == [5, 6, 7, 8, 9, 10, 11, 12]


def test_recent_window_with_fewer_turns_gives_all():
    assert [t.turn_seq for t in recent_window(memory_with(3), 8)] == [1, 2, 3]


def test_recent_window_empty_memory():
    assert recent_window(Memory(), 8) == []


def test_recent_window_zero_is_empty():
    assert recent_window(memory_with(5), 0) == []


def test_recent_window_negative_is_empty():
    assert recent_window(memory_with(5), -2) == []


def test_recent_window_one_gives_last_turn():
    assert [t.turn_seq for t in recent_window(memory_with(5), 1)] == [5]


def test_recent_window_does_not_change_memory():
    memory = memory_with(12)
    recent_window(memory, 8)
    assert len(memory.recent_turns) == 12


# бюджет по модели

def test_window_budget_is_80_percent_of_window():
    assert window_budget(app_cfg(), OPUS) == 800_000
    assert window_budget(app_cfg(), HAIKU) == 160_000


def test_budget_of_1m_window_is_capped_by_context_cap():
    assert budget(app_cfg(), OPUS, 0) == 16_000


def test_budget_of_small_window_is_80_percent():
    app = app_cfg().model_copy(deep=True)
    app.context_windows[OPUS] = 20_000
    assert budget(app, OPUS, 0) == 16_000


def test_budget_takes_cap_when_it_is_below_window_80():
    app = app_cfg().model_copy(deep=True)
    app.master.context_cap = 10_000
    app.context_windows[HAIKU] = 200_000
    assert budget(app, HAIKU, 0) == 10_000


def test_budget_equal_cap_and_window_80():
    app = app_cfg().model_copy(deep=True)
    app.context_windows[OPUS] = 12_500
    app.master.context_cap = 10_000
    assert budget(app, OPUS, 0) == 10_000


def test_budget_adds_static_to_context_cap():
    assert budget(app_cfg(), OPUS, 20_000) == 36_000


def test_budget_depends_on_model():
    app = app_cfg().model_copy(deep=True)
    app.context_windows[HAIKU] = 5_000
    assert budget(app, HAIKU, 0) == 4_000
    assert budget(app, OPUS, 0) == 16_000


# оценка токенов

def test_estimate_tokens_rounds_up():
    assert estimate_tokens("12345", 2.5) == 2
    assert estimate_tokens("123456", 2.5) == 3
    assert estimate_tokens("1234567", 2.5) == 3


def test_estimate_tokens_empty_is_zero():
    assert estimate_tokens("", 2.5) == 0


def test_estimate_tokens_exact_division_does_not_round_up():
    assert estimate_tokens("x" * 10, 2.0) == 5


def test_estimate_tokens_one_char_is_one_token():
    assert estimate_tokens("я", 2.5) == 1


def test_estimate_tokens_depends_on_chars_per_token():
    assert estimate_tokens("x" * 100, 2.0) == 50
    assert estimate_tokens("x" * 100, 4.0) == 25


def test_estimate_tokens_is_deterministic():
    text = "Привет, мир! " * 50
    assert estimate_tokens(text, 2.5) == estimate_tokens(text, 2.5)


def make_req(text="привет", system_text=None):
    from ai_dm.llm.types import SystemBlock

    system = [] if system_text is None else [SystemBlock(text=system_text, cache=True)]
    return ChatRequest(
        role="narrator", model=OPUS, system=system,
        messages=[Message(role="user", content=[Text(text=text)])], max_tokens=100,
    )


def test_request_tokens_is_estimate_of_whole_json():
    request = make_req("ввод игрока", system_text="правила мира")
    assert request_tokens(request, 2.5) == estimate_tokens(request.model_dump_json(), 2.5)


def test_request_tokens_counts_system_too():
    short = request_tokens(make_req(), 2.5)
    long = request_tokens(make_req(system_text="п" * 1000), 2.5)
    assert long - short >= 400


def test_request_tokens_grows_with_message():
    assert request_tokens(make_req("а" * 500), 2.5) > request_tokens(make_req("а"), 2.5)


def test_request_json_keeps_cyrillic_unescaped():
    # риск Р1: если бы JSON экранировал кириллицу (\uXXXX), оценка была бы завышена ~в 6 раз
    request = make_req("Привет, мир" * 20)
    dump = request.model_dump_json()
    assert "\\u04" not in dump
    assert "Привет" in dump


# искусственный render: размер запроса известен

TURN_CHARS = 50
SCENE_CHARS = 70
NPC_CHARS = 40
LOC_CHARS = 30
BASE_CHARS = 200
CHAPTER_CHARS = 60


def make_render(calls=None):
    def render(c):
        if calls is not None:
            calls.append(c.model_copy(deep=True))
        text = "B" * BASE_CHARS
        text += "T" * (TURN_CHARS * len(c.turns))
        text += "S" * (SCENE_CHARS * len(c.scenes))
        text += "N" * (NPC_CHARS * len(c.npcs))
        text += "L" * (LOC_CHARS * len(c.locations))
        text += "C" * (CHAPTER_CHARS * (len(c.chapters) + len(c.fixed_chapters)))
        return make_req(text)

    return render


def scene(n):
    return SceneSummary(id=f"sc{n}", chapter_id="ch", title=f"С{n}", summary=f"Выжимка {n}")


def cands(turns=8, scenes=4, npcs=3, locations=3, floor=1):
    return Candidates(
        turns=[turn_record(n) for n in range(1, turns + 1)],
        floor=floor,
        scenes=[scene(n) for n in range(1, scenes + 1)],
        npcs=[f"npc{n}" for n in range(1, npcs + 1)],
        locations=[f"loc{n}" for n in range(1, locations + 1)],
    )


def size(c, cpt=CPT):
    return request_tokens(make_render()(c), cpt)


def chapter(n):
    return ChapterSummary(id=f"ch{n}", number=n, title=f"Г{n}", summary=f"Итог {n}")


def with_chapters(c, folded=3, fixed=1):
    # folded -- уже в game_summary (number <= game_summary_chapter), fixed -- ещё нет
    c.chapters = [chapter(n) for n in range(1, folded + 1)]
    c.fixed_chapters = [chapter(n) for n in range(folded + 1, folded + fixed + 1)]
    return c


def run_plan(c, cap, window80=BIG, cpt=CPT, calls=None, static=0):
    return plan(c, make_render(calls), cap=cap, window80=window80, cpt=cpt, static=static)


def trimmed(c, turns=None, scenes=None, npcs=None, locations=None, chapters=None):
    # те же кандидаты без первых N элементов по ступеням
    return Candidates(
        turns=c.turns[turns or 0:], floor=c.floor, scenes=c.scenes[scenes or 0:],
        npcs=c.npcs[npcs or 0:], locations=c.locations[locations or 0:],
        chapters=c.chapters[chapters or 0:], fixed_chapters=c.fixed_chapters,
    )


def test_stages_order():
    assert STAGES == ("turns", "scenes", "npcs", "locations", "chapters")


# ничего не вытесняется

def test_nothing_dropped_when_it_fits():
    c = cands()
    result = run_plan(c, cap=BIG)
    assert result.dropped == []
    assert result.raised is False
    assert result.overflow is False
    assert result.turns == c.turns
    assert result.scene_summaries == c.scenes
    assert result.npc_ids == c.npcs
    assert result.location_ids == c.locations


def test_estimate_is_size_of_rendered_request():
    c = cands()
    assert run_plan(c, cap=BIG).estimate == size(c)


def test_estimate_uses_chars_per_token():
    c = cands()
    assert run_plan(c, cap=BIG, cpt=2.5).estimate == size(c, 2.5)
    assert size(c, 2.5) < size(c, 1.0)


def test_budget_and_cap_are_reported():
    result = run_plan(cands(), cap=BIG, window80=BIG * 2)
    assert result.cap == BIG
    assert result.budget == BIG


def test_cap_equal_to_estimate_drops_nothing():
    c = cands()
    result = run_plan(c, cap=size(c))
    assert result.dropped == []
    assert result.estimate == size(c)


def test_cap_one_below_estimate_drops_exactly_oldest_turn():
    c = cands()
    result = run_plan(c, cap=size(c) - 1)
    assert result.dropped == [("turns", "1")]
    assert [t.turn_seq for t in result.turns] == [2, 3, 4, 5, 6, 7, 8]


# ступень 1: ходы

def test_three_oldest_turns_are_dropped_first():
    c = cands()
    result = run_plan(c, cap=size(trimmed(c, turns=3)))
    assert result.dropped == [("turns", "1"), ("turns", "2"), ("turns", "3")]
    assert [t.turn_seq for t in result.turns] == [4, 5, 6, 7, 8]


def test_turn_stage_keeps_scenes_npcs_and_locations():
    c = cands()
    result = run_plan(c, cap=size(trimmed(c, turns=3)))
    assert result.scene_summaries == c.scenes
    assert result.npc_ids == c.npcs
    assert result.location_ids == c.locations


def test_turn_drop_is_minimal():
    c = cands()
    result = run_plan(c, cap=size(trimmed(c, turns=2)) - 1)
    assert result.dropped == [("turns", "1"), ("turns", "2"), ("turns", "3")]


def test_turn_id_is_turn_seq_as_string():
    c = cands()
    c.turns = [turn_record(n) for n in (41, 42, 43)]
    result = run_plan(c, cap=size(trimmed(c, turns=2)))
    assert result.dropped == [("turns", "41"), ("turns", "42")]


def test_floor_keeps_last_turn_while_everything_else_is_dropped():
    c = cands(floor=1)
    result = run_plan(c, cap=size(trimmed(c, turns=7, scenes=4, npcs=3, locations=3)))
    assert [t.turn_seq for t in result.turns] == [8]
    assert result.raised is False
    assert len(result.dropped) == 7 + 4 + 3 + 3


def test_floor_two_keeps_two_last_turns():
    c = cands(floor=2)
    result = run_plan(c, cap=1)
    assert [t.turn_seq for t in result.turns] == [7, 8]


def test_floor_zero_can_drop_all_turns():
    c = cands(floor=0)
    result = run_plan(c, cap=size(trimmed(c, turns=8, scenes=4, npcs=3, locations=3)))
    assert result.turns == []
    assert result.raised is False


def test_floor_above_turn_count_never_drops_turns():
    c = cands(turns=3, floor=5)
    result = run_plan(c, cap=1)
    assert [t.turn_seq for t in result.turns] == [1, 2, 3]
    assert [s for s, _ in result.dropped if s == "turns"] == []


def test_no_turns_no_scenes_is_fine():
    c = cands(turns=0, scenes=0, npcs=0, locations=0)
    result = run_plan(c, cap=BIG)
    assert result.dropped == []
    assert result.turns == []


# ступень 2: выжимки сцен, только после ходов до floor

def test_scenes_are_not_touched_while_turns_can_be_dropped():
    c = cands()
    # хватит убрать все лишние ходы: сцены целы
    result = run_plan(c, cap=size(trimmed(c, turns=7)))
    assert [s for s, _ in result.dropped] == ["turns"] * 7
    assert result.scene_summaries == c.scenes


def test_oldest_scenes_are_dropped_first_after_turns():
    c = cands()
    result = run_plan(c, cap=size(trimmed(c, turns=7, scenes=2)))
    assert result.dropped == [("turns", str(n)) for n in range(1, 8)] + [
        ("scenes", "sc1"), ("scenes", "sc2"),
    ]
    assert [s.id for s in result.scene_summaries] == ["sc3", "sc4"]
    assert [t.turn_seq for t in result.turns] == [8]


def test_scene_drop_keeps_npcs_and_locations():
    c = cands()
    result = run_plan(c, cap=size(trimmed(c, turns=7, scenes=2)))
    assert result.npc_ids == c.npcs
    assert result.location_ids == c.locations


def test_scene_drop_is_minimal():
    c = cands()
    result = run_plan(c, cap=size(trimmed(c, turns=7, scenes=2)) + SCENE_CHARS - 1)
    assert [i for s, i in result.dropped if s == "scenes"] == ["sc1", "sc2"]


def test_scene_stage_with_floor_zero_drops_last_turn_before_scenes():
    c = cands(floor=0)
    result = run_plan(c, cap=size(trimmed(c, turns=8, scenes=1)))
    assert result.dropped[:8] == [("turns", str(n)) for n in range(1, 9)]
    assert result.dropped[8:] == [("scenes", "sc1")]


# ступень 3: NPC и ступень 4: локации

def test_npcs_are_dropped_in_given_order_after_scenes():
    c = cands()
    result = run_plan(c, cap=size(trimmed(c, turns=7, scenes=4, npcs=2)))
    assert result.dropped[-2:] == [("npcs", "npc1"), ("npcs", "npc2")]
    assert result.npc_ids == ["npc3"]
    assert result.scene_summaries == []
    assert result.location_ids == c.locations


def test_npcs_are_not_dropped_while_scenes_remain():
    c = cands()
    result = run_plan(c, cap=size(trimmed(c, turns=7, scenes=3)))
    assert result.npc_ids == c.npcs
    assert [s for s, _ in result.dropped].count("npcs") == 0


def test_locations_are_dropped_in_given_order_last():
    c = cands()
    result = run_plan(c, cap=size(trimmed(c, turns=7, scenes=4, npcs=3, locations=2)))
    assert result.dropped[-2:] == [("locations", "loc1"), ("locations", "loc2")]
    assert result.location_ids == ["loc3"]
    assert result.npc_ids == []


def test_locations_are_not_dropped_while_npcs_remain():
    c = cands()
    result = run_plan(c, cap=size(trimmed(c, turns=7, scenes=4, npcs=2)))
    assert result.location_ids == c.locations


def test_full_drop_order_by_stages():
    c = cands()
    result = run_plan(c, cap=1)
    assert result.dropped == (
        [("turns", str(n)) for n in range(1, 8)]
        + [("scenes", f"sc{n}") for n in range(1, 5)]
        + [("npcs", f"npc{n}") for n in range(1, 4)]
        + [("locations", f"loc{n}") for n in range(1, 4)]
    )


def test_stages_never_go_backwards():
    c = cands(turns=6, scenes=3, npcs=5, locations=4)
    for cap in range(size(c), 0, -37):
        stages = [STAGES.index(s) for s, _ in run_plan(c, cap=cap).dropped]
        assert stages == sorted(stages)


def test_drop_is_a_prefix_of_full_order_for_every_cap():
    c = cands(turns=6, scenes=3, npcs=5, locations=4)
    full = run_plan(c, cap=1).dropped
    for cap in range(size(c), 0, -29):
        dropped = run_plan(c, cap=cap).dropped
        assert dropped == full[: len(dropped)]


def test_next_stage_starts_only_when_previous_is_empty():
    c = cands(turns=6, scenes=3, npcs=5, locations=4, floor=2)
    for cap in range(size(c), 0, -23):
        result = run_plan(c, cap=cap)
        stages = [s for s, _ in result.dropped]
        if "scenes" in stages:
            assert len(result.turns) == 2
        if "npcs" in stages:
            assert result.scene_summaries == []
        if "locations" in stages:
            assert result.npc_ids == []


# итог: estimate <= budget и равен размеру итогового запроса

@pytest.mark.parametrize("turns", [0, 1, 8])
@pytest.mark.parametrize("scenes", [0, 5])
@pytest.mark.parametrize("npcs", [0, 6])
@pytest.mark.parametrize("locations", [0, 4])
@pytest.mark.parametrize("floor", [0, 2])
def test_estimate_fits_budget_and_matches_final_request(turns, scenes, npcs, locations, floor):
    c = cands(turns, scenes, npcs, locations, floor)
    total = size(c)
    for cap in (BIG, total, total - 1, total * 2 // 3, total // 2, total // 3, 1):
        result = run_plan(c, cap=cap)
        final = Candidates(
            turns=result.turns, floor=floor, scenes=result.scene_summaries,
            npcs=result.npc_ids, locations=result.location_ids,
        )
        assert result.estimate == size(final)
        assert result.estimate <= result.budget
        if not result.raised:
            assert result.estimate <= cap


def test_dropped_count_matches_what_is_missing():
    c = cands()
    result = run_plan(c, cap=size(c) // 2)
    kept = (
        len(result.turns) + len(result.scene_summaries) + len(result.npc_ids)
        + len(result.location_ids)
    )
    assert kept + len(result.dropped) == 8 + 4 + 3 + 3


def test_render_is_called_with_whole_candidates_each_time():
    calls = []
    c = cands(turns=3, scenes=0, npcs=0, locations=0, floor=0)
    run_plan(c, cap=size(trimmed(c, turns=2)), calls=calls)
    assert [len(x.turns) for x in calls] == [3, 2, 1]


def test_plan_does_not_change_candidates():
    c = cands()
    before = c.model_dump_json()
    run_plan(c, cap=1)
    assert c.model_dump_json() == before


def test_plan_is_deterministic():
    c = cands()
    cap = size(c) // 2
    assert run_plan(c, cap=cap) == run_plan(c, cap=cap)


# G1: неустранимое > cap

def test_unavoidable_over_cap_raises_budget_to_window_80():
    c = cands()
    window80 = size(c) * 2
    result = run_plan(c, cap=1, window80=window80)
    assert result.raised is True
    assert result.overflow is True
    assert result.budget == window80
    assert result.cap == 1


def test_raised_plan_drops_everything_droppable_and_keeps_floor():
    c = cands(floor=2)
    result = run_plan(c, cap=1, window80=BIG)
    assert [t.turn_seq for t in result.turns] == [7, 8]
    assert result.scene_summaries == []
    assert result.npc_ids == []
    assert result.location_ids == []
    assert len(result.dropped) == 6 + 4 + 3 + 3


def test_raised_estimate_is_unavoidable_part():
    c = cands(floor=1)
    result = run_plan(c, cap=1)
    assert result.estimate == size(trimmed(c, turns=7, scenes=4, npcs=3, locations=3))
    assert result.estimate > result.cap


def test_estimate_above_window_80_still_returns_plan():
    c = cands()
    result = run_plan(c, cap=1, window80=2)
    assert result.raised is True
    assert result.overflow is True
    assert result.budget == 2
    assert result.estimate > result.budget


def test_cap_exactly_at_unavoidable_is_not_raised():
    c = cands(floor=1)
    bare = size(trimmed(c, turns=7, scenes=4, npcs=3, locations=3))
    result = run_plan(c, cap=bare)
    assert result.raised is False
    assert result.overflow is False
    assert result.budget == bare
    assert len(result.dropped) == 17


def test_cap_one_below_unavoidable_is_raised():
    c = cands(floor=1)
    bare = size(trimmed(c, turns=7, scenes=4, npcs=3, locations=3))
    result = run_plan(c, cap=bare - 1, window80=BIG)
    assert result.raised is True
    assert result.budget == BIG


def test_raised_does_not_bring_dropped_back():
    c = cands()
    low = run_plan(c, cap=1, window80=BIG)
    assert len(low.turns) == 1
    assert len(low.dropped) == 7 + 4 + 3 + 3


# meta и неизменяемость

def test_meta_has_all_fields():
    c = cands()
    result = run_plan(c, cap=size(trimmed(c, turns=2)), window80=BIG)
    assert result.meta() == {
        "budget": result.cap, "cap": result.cap, "static": 0, "estimate": result.estimate,
        "dropped": [["turns", "1"], ["turns", "2"]], "raised": False, "overflow": False,
    }


def test_meta_of_raised_plan():
    result = run_plan(cands(), cap=1, window80=5000)
    meta = result.meta()
    assert meta["raised"] is True
    assert meta["overflow"] is True
    assert meta["budget"] == 5000
    assert meta["cap"] == 1
    assert meta["estimate"] == result.estimate


def test_meta_dropped_is_list_of_lists_and_json_serializable():
    result = run_plan(cands(), cap=1)
    meta = result.meta()
    assert all(isinstance(pair, list) and len(pair) == 2 for pair in meta["dropped"])
    assert json.loads(json.dumps(meta)) == meta


def test_context_plan_is_frozen():
    result = run_plan(cands(), cap=BIG)
    assert isinstance(result, ContextPlan)
    with pytest.raises(ValidationError):
        result.raised = True


# Ж0 п.0: статика запроса не входит в потолок динамики

def test_plan_reports_static():
    assert run_plan(cands(), cap=BIG, static=1234).static == 1234


def test_plan_static_defaults_to_zero():
    result = plan(cands(), make_render(), cap=BIG, window80=BIG, cpt=CPT)
    assert result.static == 0
    assert result.cap == BIG


def test_plan_cap_is_total_cap_minus_static():
    result = run_plan(cands(), cap=5000, static=1200)
    assert result.cap == 3800


def test_plan_cap_is_never_negative():
    assert run_plan(cands(), cap=100, static=300).cap == 0


def test_plan_cap_equal_to_static_is_zero():
    assert run_plan(cands(), cap=300, static=300).cap == 0


def test_plan_budget_is_total_cap_not_dynamic_cap():
    result = run_plan(cands(), cap=BIG, static=1000, window80=BIG * 2)
    assert result.budget == BIG


def test_static_does_not_change_estimate():
    c = cands()
    assert run_plan(c, cap=BIG, static=777).estimate == size(c)


def test_static_does_not_change_what_is_dropped():
    c = cands()
    cap = size(trimmed(c, turns=3))
    assert run_plan(c, cap=cap, static=50).dropped == run_plan(c, cap=cap).dropped


def test_raised_compares_estimate_with_total_cap_including_static():
    c = cands(floor=1)
    bare = size(trimmed(c, turns=7, scenes=4, npcs=3, locations=3))
    result = run_plan(c, cap=bare, static=bare // 2)
    assert result.raised is False
    assert result.budget == bare


def test_raised_one_below_unavoidable_with_static():
    c = cands(floor=1)
    bare = size(trimmed(c, turns=7, scenes=4, npcs=3, locations=3))
    result = run_plan(c, cap=bare - 1, static=bare // 2, window80=BIG)
    assert result.raised is True
    assert result.overflow is True
    assert result.budget == BIG


def test_raised_with_cap_below_static_lifts_budget_to_window_80():
    c = cands()
    result = run_plan(c, cap=10, static=500, window80=BIG)
    assert result.cap == 0
    assert result.raised is True
    assert result.budget == BIG


def test_meta_reports_static():
    result = run_plan(cands(), cap=BIG, static=4321)
    assert result.meta()["static"] == 4321


def test_meta_cap_is_dynamic_cap():
    result = run_plan(cands(), cap=5000, static=1200)
    assert result.meta()["cap"] == 3800
    assert result.meta()["budget"] == 5000


# Ж0 п.0, BACKLOG 15: пятая ступень -- выжимки глав, уже свёрнутые в game_summary

def test_chapters_default_to_empty_in_plan():
    assert run_plan(cands(), cap=BIG).chapters == []


def test_nothing_dropped_keeps_all_chapters_folded_first_then_fixed():
    c = with_chapters(cands(), folded=3, fixed=1)
    result = run_plan(c, cap=BIG)
    assert [x.id for x in result.chapters] == ["ch1", "ch2", "ch3", "ch4"]
    assert result.dropped == []


def test_estimate_counts_chapters():
    c = with_chapters(cands(), folded=3, fixed=1)
    assert run_plan(c, cap=BIG).estimate == size(cands()) + 4 * CHAPTER_CHARS


def test_chapters_are_not_touched_while_locations_remain():
    c = with_chapters(cands())
    result = run_plan(c, cap=size(trimmed(c, turns=7, scenes=4, npcs=3, locations=2)))
    assert [s for s, _ in result.dropped if s == "chapters"] == []
    assert [x.id for x in result.chapters] == ["ch1", "ch2", "ch3", "ch4"]


def test_oldest_chapters_are_dropped_first_after_locations():
    c = with_chapters(cands())
    result = run_plan(c, cap=size(trimmed(c, turns=7, scenes=4, npcs=3, locations=3, chapters=2)))
    assert result.dropped[-2:] == [("chapters", "ch1"), ("chapters", "ch2")]
    assert [x.id for x in result.chapters] == ["ch3", "ch4"]
    assert result.location_ids == []
    assert result.raised is False


def test_chapter_drop_is_minimal():
    c = with_chapters(cands())
    bare = size(trimmed(c, turns=7, scenes=4, npcs=3, locations=3, chapters=2))
    result = run_plan(c, cap=bare + CHAPTER_CHARS - 1)
    assert [i for s, i in result.dropped if s == "chapters"] == ["ch1", "ch2"]


def test_chapter_id_is_chapter_id_not_number():
    c = cands()
    c.chapters = [ChapterSummary(id="kappa", number=7, title="К", summary="и")]
    result = run_plan(c, cap=1)
    assert ("chapters", "kappa") in result.dropped


def test_fixed_chapters_never_leave():
    c = with_chapters(cands(), folded=2, fixed=2)
    result = run_plan(c, cap=1)
    assert [x.id for x in result.chapters] == ["ch3", "ch4"]
    assert [i for s, i in result.dropped if s == "chapters"] == ["ch1", "ch2"]
    assert result.raised is True


def test_fixed_chapters_alone_are_not_dropped_even_when_over_cap():
    c = cands(turns=0, scenes=0, npcs=0, locations=0)
    c.fixed_chapters = [chapter(1), chapter(2)]
    result = run_plan(c, cap=1)
    assert result.dropped == []
    assert [x.id for x in result.chapters] == ["ch1", "ch2"]
    assert result.raised is True


def test_full_drop_order_ends_with_chapters():
    c = with_chapters(cands(), folded=3, fixed=0)
    result = run_plan(c, cap=1)
    assert result.dropped == (
        [("turns", str(n)) for n in range(1, 8)]
        + [("scenes", f"sc{n}") for n in range(1, 5)]
        + [("npcs", f"npc{n}") for n in range(1, 4)]
        + [("locations", f"loc{n}") for n in range(1, 4)]
        + [("chapters", f"ch{n}") for n in range(1, 4)]
    )


def test_chapters_stage_comes_only_when_everything_before_it_is_gone():
    c = with_chapters(cands())
    for cap in range(size(c), 0, -31):
        result = run_plan(c, cap=cap)
        if any(s == "chapters" for s, _ in result.dropped):
            assert result.location_ids == []
            assert result.npc_ids == []
            assert result.scene_summaries == []


def test_plan_does_not_change_chapter_candidates():
    c = with_chapters(cands())
    before = c.model_dump_json()
    run_plan(c, cap=1)
    assert c.model_dump_json() == before
