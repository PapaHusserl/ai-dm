# ТМ (docs/TM-PLAN.md, §1 п.4-5): recent_turns в промпте рассказчика.
#   master.prompt.turn_data(turn) -> dict:
#   ровно {turn_seq, at_s, player_input, narration, outcomes};
#     без requests, rolls, scene_id, money_delta_cp (модель копировала requests и повторяла вызовы).
#   PromptBuilder.state_data кладёт turn_data для каждой записи окна; окно и вытеснение прежние.
#   Summarizer и relevance читают записи как раньше (requests / rolls у summarizer остаются).
#   narrator_rules.md: recent_turns -- прошлое, вызовы не повторять.
import json
from importlib import resources

from master_kit import app_cfg, make_bundle, make_ctx, turn_record

from ai_dm.master.prompt import PromptBuilder, turn_data
from ai_dm.master.summarizer import SummarizerPromptBuilder
from ai_dm.state.scene import TurnRecord

KEYS = {"turn_seq", "at_s", "player_input", "narration", "outcomes"}


def full_turn(seq=5, **extra):
    data = {
        "turn_seq": seq, "at_s": 900, "player_input": "Обыскать тела",
        "narration": "Находишь кошель.", "requests": ["gold", "rest"],
        "rolls": ["Скрытность: 14 против СЛ 12"], "scene_id": "scene_3",
        "outcomes": ["Золото: +20 зм"], "money_delta_cp": 2000,
    }
    data.update(extra)
    return TurnRecord(**data)


def recent_of(ctx, app=None):
    request = PromptBuilder(app or app_cfg()).build(ctx, "Иду.", "explore")
    return json.loads(request.messages[0].content[0].text)["recent_turns"]


# turn_data

def test_turn_data_has_exactly_the_five_keys():
    assert set(turn_data(full_turn())) == KEYS


def test_turn_data_values():
    assert turn_data(full_turn()) == {
        "turn_seq": 5, "at_s": 900, "player_input": "Обыскать тела",
        "narration": "Находишь кошель.", "outcomes": ["Золото: +20 зм"],
    }


def test_turn_data_has_no_requests_rolls_scene_or_money():
    data = turn_data(full_turn())
    for key in ("requests", "rolls", "scene_id", "money_delta_cp"):
        assert key not in data


def test_turn_data_outcomes_empty_list_by_default():
    record = TurnRecord(turn_seq=1, at_s=0, player_input="a", narration="b")
    assert turn_data(record)["outcomes"] == []


def test_turn_data_outcomes_is_a_copy():
    record = full_turn()
    data = turn_data(record)
    data["outcomes"].append("x")
    assert record.outcomes == ["Золото: +20 зм"]


def test_turn_data_is_json_serializable():
    json.dumps(turn_data(full_turn()), ensure_ascii=False)


def test_turn_data_keeps_several_outcomes_in_order():
    record = full_turn(outcomes=["a", "gold: отклонено (повтор начисления)", "b"])
    assert turn_data(record)["outcomes"] == ["a", "gold: отклонено (повтор начисления)", "b"]


# PromptBuilder.state_data

def test_prompt_recent_turn_keys_are_exactly_the_five(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.memory.recent_turns = [full_turn(1), full_turn(2)]
    for turn in recent_of(ctx):
        assert set(turn) == KEYS


def test_prompt_recent_turn_has_outcomes_from_record(registry, cfg):
    ctx = make_ctx(registry, cfg)
    rejected = "use_item: отклонено (нечего применить)"
    ctx.bundle.memory.recent_turns = [full_turn(1, outcomes=[rejected])]
    assert recent_of(ctx)[0]["outcomes"] == ["use_item: отклонено (нечего применить)"]


def test_prompt_recent_turn_from_old_save_has_empty_outcomes(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.memory.recent_turns = [turn_record(1)]
    assert recent_of(ctx)[0]["outcomes"] == []


def test_prompt_does_not_leak_requests_into_message(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.memory.recent_turns = [full_turn(1, requests=["offer_choices_marker"])]
    request = PromptBuilder(app_cfg()).build(ctx, "Иду.", "explore")
    assert "offer_choices_marker" not in request.messages[0].content[0].text


def test_prompt_window_and_order_are_unchanged(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.memory.recent_turns = [full_turn(n) for n in range(1, 13)]
    assert [t["turn_seq"] for t in recent_of(ctx)] == [5, 6, 7, 8, 9, 10, 11, 12]


def test_prompt_window_comes_from_config(registry, cfg):
    app = app_cfg()
    app.master.recent_turns = 2
    ctx = make_ctx(registry, cfg)
    ctx.bundle.memory.recent_turns = [full_turn(n) for n in range(1, 6)]
    assert [t["turn_seq"] for t in recent_of(ctx, app)] == [4, 5]


def test_prompt_without_turns_has_empty_list(registry, cfg):
    assert recent_of(make_ctx(registry, cfg)) == []


def test_prompt_player_input_and_narration_pass_through(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.memory.recent_turns = [full_turn(1)]
    turn = recent_of(ctx)[0]
    assert (turn["player_input"], turn["narration"]) == ("Обыскать тела", "Находишь кошель.")


def test_recent_turns_are_not_modified_by_prompt(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.memory.recent_turns = [full_turn(1)]
    before = ctx.bundle.memory.recent_turns[0].model_copy(deep=True)
    recent_of(ctx)
    assert ctx.bundle.memory.recent_turns[0] == before


# summarizer без изменений

def test_summarizer_input_still_has_requests_and_rolls(registry, cfg):
    bundle = make_bundle(registry)
    record = full_turn(1, scene_id=bundle.session.current_scene.id)
    bundle.memory.recent_turns.append(record)
    ctx = make_ctx(registry, cfg, bundle=bundle)
    state = SummarizerPromptBuilder(app_cfg()).state_data(ctx)
    assert state["turns"] == [{
        "turn_seq": 1, "player_input": "Обыскать тела", "narration": "Находишь кошель.",
        "requests": ["gold", "rest"], "rolls": ["Скрытность: 14 против СЛ 12"],
    }]


# правило narrator_rules.md

def rules_text():
    return (resources.files("ai_dm.master") / "prompts" / "narrator_rules.md").read_text(
        encoding="utf-8"
    )


def rule_sentence():
    text = rules_text()
    start = text.index("`recent_turns` —")
    return text[start:text.index("\n", start)]


def test_rule_lists_the_fields_of_recent_turns():
    sentence = rule_sentence()
    for field in ("player_input", "narration", "outcomes"):
        assert field in sentence


def test_rule_says_calls_of_past_turns_are_not_repeated():
    assert "не повторяй" in rule_sentence()


def test_rule_names_what_is_already_counted():
    sentence = rule_sentence()
    for word in ("золото", "отдых", "предметы"):
        assert word in sentence


def test_rule_says_not_to_retell_the_text_and_answer_current_input():
    sentence = rule_sentence()
    assert "не пересказывай" in sentence
    assert "текущий `player_input`" in sentence


def test_rule_sits_in_the_state_block_after_player_input_paragraph():
    text = rules_text()
    assert text.index("Каждое сообщение — JSON") < text.index("`recent_turns` —")


def test_rule_does_not_mention_removed_fields():
    sentence = rule_sentence()
    for word in ("requests", "rolls"):
        assert word not in sentence
