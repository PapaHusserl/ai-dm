# ФС П2 (BACKLOG 134): конспект выпавших ходов текущей сцены собирает движок из состояния.
import json

import pytest
from master_kit import make_bundle, make_ctx
from test_master_context_build import add_npc, app_with

from ai_dm.llm.types import ToolSpec
from ai_dm.master.context import request_tokens
from ai_dm.master.prompt import PromptBuilder, draft_plan
from ai_dm.master.recap import RECAP_LINE_MAX, RECAP_MAX, dropped_turns, scene_recap, turns_word
from ai_dm.protocol.schema import tool_set
from ai_dm.state.scene import TurnRecord


def record(n, scene_id="scene_1", narration="Ход.", outcomes=()):
    return TurnRecord(
        turn_seq=n, at_s=n * 60, player_input=f"ввод {n}", narration=narration,
        scene_id=scene_id, outcomes=list(outcomes),
    )


def bundle_with(registry, turns):
    bundle = make_bundle(registry)
    bundle.memory.recent_turns = turns
    return bundle


def test_dropped_turns_takes_current_scene_turns_outside_kept(registry):
    bundle = bundle_with(registry, [record(1), record(2, "old"), record(3), record(4)])
    result = dropped_turns(bundle.memory, bundle.session.current_scene, {4})
    assert [t.turn_seq for t in result] == [1, 3]


def test_recap_is_none_without_scene(registry):
    bundle = bundle_with(registry, [record(1)])
    bundle.session.current_scene = None
    assert scene_recap(bundle, set(), max_chars=RECAP_MAX) is None


def test_recap_is_none_without_dropped_turns(registry):
    bundle = bundle_with(registry, [record(1), record(2)])
    assert scene_recap(bundle, {1, 2}, max_chars=RECAP_MAX) is None


def test_recap_names_turn_range_and_count(registry):
    bundle = bundle_with(registry, [record(n) for n in range(1, 10)])
    recap = scene_recap(bundle, {9}, max_chars=RECAP_MAX)
    assert recap["turns"] == "t1–t8 (8 ходов)"
    assert recap["events"] == []
    assert recap["npcs"] == []


@pytest.mark.parametrize(
    "n, word",
    [(1, "1 ход"), (2, "2 хода"), (4, "4 хода"), (5, "5 ходов"), (11, "11 ходов"),
     (12, "12 ходов"), (21, "21 ход"), (22, "22 хода"), (25, "25 ходов"), (111, "111 ходов"),
     (3, "3 хода"), (13, "13 ходов"), (14, "14 ходов")],
)
def test_turns_word_declension(n, word):
    assert turns_word(n) == word


def test_recap_npc_names_count_against_budget_and_old_event_drops(registry):
    name = "Длинноимённый Персонаж"
    turns = [
        record(1, narration=f"Здесь {name}.", outcomes=["ab"]),
        record(2, outcomes=["cd"]),
        record(3),
    ]
    bundle = bundle_with(registry, turns)
    add_npc(bundle.world, "long", name=name)
    recap = scene_recap(bundle, {3}, max_chars=len(name) + len("t2: cd"))
    assert recap["npcs"] == [name]
    assert recap["events"] == ["t2: cd"]
    roomy = scene_recap(bundle, {3}, max_chars=len(name) + 2 * len("t2: cd"))
    assert roomy["events"] == ["t1: ab", "t2: cd"]


def test_recap_skips_turns_of_other_scene(registry):
    bundle = bundle_with(registry, [record(1, "old"), record(2, "old"), record(3), record(4)])
    assert scene_recap(bundle, {4}, max_chars=RECAP_MAX)["turns"] == "t3 (1 ход)"


def test_recap_events_skip_rejected_lines_and_keep_order(registry):
    turns = [
        record(1, outcomes=["gold: +5 зм", "rest: отклонено (not_allowed)"]),
        record(2, outcomes=["Получен предмет: меч"]),
        record(3),
    ]
    recap = scene_recap(bundle_with(registry, turns), {3}, max_chars=RECAP_MAX)
    assert recap["events"] == ["t1: gold: +5 зм", "t2: Получен предмет: меч"]


def test_recap_event_line_is_clipped(registry):
    turns = [record(1, outcomes=["слово " * 100]), record(2)]
    (event,) = scene_recap(bundle_with(registry, turns), {2}, max_chars=RECAP_MAX)["events"]
    assert RECAP_LINE_MAX - 6 <= len(event) <= RECAP_LINE_MAX
    assert event.startswith("t1: слово")
    assert event.endswith("…")


def test_recap_drops_oldest_events_over_limit(registry):
    turns = [record(n, outcomes=[f"событие {n}"]) for n in range(1, 6)] + [record(6)]
    recap = scene_recap(bundle_with(registry, turns), {6}, max_chars=26)
    assert recap["events"] == ["t4: событие 4", "t5: событие 5"]


def test_recap_events_fit_exact_limit(registry):
    turns = [record(1, outcomes=["ab"]), record(2)]
    recap = scene_recap(bundle_with(registry, turns), {2}, max_chars=len("t1: ab"))
    assert recap["events"] == ["t1: ab"]


def test_recap_lists_named_living_npcs_mentioned_in_dropped_turns(registry):
    turns = [record(1, narration="К вам подошёл Зоя."), record(2, narration="Рюрик молчит.")]
    bundle = bundle_with(registry, [*turns, record(3)])
    add_npc(bundle.world, "zoya", name="Зоя")
    add_npc(bundle.world, "dead_one", name="Рюрик", status="dead")
    add_npc(bundle.world, "anon", name="Мирон", named=False)
    add_npc(bundle.world, "absent", name="Борис")
    bundle.memory.recent_turns[2].narration = "Мирон и Борис в последнем ходу."
    recap = scene_recap(bundle, {3}, max_chars=RECAP_MAX)
    assert recap["npcs"] == ["Зоя"]


def test_recap_finds_npc_named_at_start_of_later_dropped_turn(registry):
    # ходы склеиваются через пробел: имя в начале не первого хода не прилипает к соседнему слову
    turns = [record(1), record(2, narration="Зоя вышла вперёд."), record(3)]
    bundle = bundle_with(registry, turns)
    add_npc(bundle.world, "zoya", name="Зоя")
    assert scene_recap(bundle, {3}, max_chars=RECAP_MAX)["npcs"] == ["Зоя"]


def test_prompt_has_scene_recap_when_turns_fall_out(registry, cfg):
    bundle = bundle_with(registry, [record(n, outcomes=[f"gold: {n}"]) for n in range(1, 11)])
    request = PromptBuilder(app_with(recent_turns=3, recent_turns_floor=1)).build(
        make_ctx(registry, cfg, bundle=bundle), "Осматриваюсь.", "explore"
    )
    data = json.loads(request.messages[0].content[0].text)
    assert [t["turn_seq"] for t in data["recent_turns"]] == [8, 9, 10]
    assert data["scene_recap"]["turns"] == "t1–t7 (7 ходов)"
    assert data["scene_recap"]["events"][0] == "t1: gold: 1"


def test_prompt_has_no_scene_recap_when_all_turns_kept(registry, cfg):
    bundle = bundle_with(registry, [record(n) for n in range(1, 4)])
    request = PromptBuilder(app_with()).build(
        make_ctx(registry, cfg, bundle=bundle), "Осматриваюсь.", "explore"
    )
    assert "scene_recap" not in json.loads(request.messages[0].content[0].text)


def test_prompt_recap_with_tiny_cap_reports_dropped_seqs(registry, cfg):
    bundle = bundle_with(registry, [record(n) for n in range(1, 9)])
    request = PromptBuilder(app_with(cap=1)).build(
        make_ctx(registry, cfg, bundle=bundle), "Осматриваюсь.", "explore"
    )
    data = json.loads(request.messages[0].content[0].text)
    kept = [t["turn_seq"] for t in data["recent_turns"]]
    assert kept == [8]
    assert data["scene_recap"]["turns"] == "t1–t7 (7 ходов)"


def test_estimate_never_grows_when_turn_is_evicted(registry, cfg):
    # конспект растёт на <= RECAP_LINE_MAX на ход, ход уходит целиком: оценка не растёт
    story, outcome = "Длинный рассказ о событиях сцены. " * 12, ["gold: " + "x" * 200]
    turns = [record(n, narration=story, outcomes=outcome) for n in range(1, 11)]
    ctx = make_ctx(registry, cfg, bundle=bundle_with(registry, turns))
    builder = PromptBuilder(app_with(recent_turns=10, recent_turns_floor=1))
    tools = [ToolSpec.model_validate(d) for d in tool_set("explore")]
    left = builder.candidates(ctx)
    cpt = builder.app_cfg.master.cpt_for(builder.role_cfg.provider)
    estimates = []
    while True:
        request = builder.request(ctx, "Осматриваюсь.", tools, "", draft_plan(left))
        estimates.append(request_tokens(request, cpt))
        if len(left.turns) <= left.floor:
            break
        left.turns.pop(0)
    assert len(estimates) == 10
    assert estimates == sorted(estimates, reverse=True)
