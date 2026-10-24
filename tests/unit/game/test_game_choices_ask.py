# T5 (мини-партия #18): приписка CHOICES_ASK на уровне TurnRunner/GameApp -- ход кончился
# вопросом, а offer_choices не вызван: один дополнительный вызов в том же прогоне, тег
# choices_retry, авто-репорт; в бою приписки нет.
import json

from game_kit import (
    make_app,
    make_rig,
    player_action_input,
    run_records,
    script_then_react,
    scripted,
    start_combat_call,
    text_step,
    tools_step,
)

from ai_dm.llm.types import Text
from ai_dm.master.session import CHOICES_ASK
from ai_dm.ui.session import offer_is_stale

QUESTION = "Ты стоишь у двери.\n\nОткрыть её?"
OFFER = {
    "id": "of", "name": "offer_choices",
    "input": {"type": "offer_choices", "choices": ["Открыть", "Уйти"]},
}


def asked(steps, registry, cfg, tmp_path):
    adapter = scripted(steps)
    rig = make_rig(registry, cfg, tmp_path, adapter)
    return rig, adapter, rig.runner.play("Иду")


def test_question_turn_gets_choices_retry(registry, cfg, tmp_path):
    rig, adapter, result = asked(
        [text_step(QUESTION), tools_step(OFFER)], registry, cfg, tmp_path
    )
    assert result.committed is True
    assert result.narration == QUESTION
    assert result.report_tags == ["choices_retry"]
    assert result.failure is None
    assert len(adapter.requests) == 2


def test_ask_is_in_the_request(registry, cfg, tmp_path):
    _, adapter, _ = asked([text_step(QUESTION), tools_step(OFFER)], registry, cfg, tmp_path)
    last = adapter.requests[1].messages[-1]
    texts = [b.text for b in last.content if isinstance(b, Text)]
    assert len(texts) == 1
    assert texts[0].endswith(CHOICES_ASK)
    assert QUESTION in texts[0]
    assert "Фраза игрока: Иду" in texts[0]


def test_ask_request_is_cheap_one_message_one_tool(registry, cfg, tmp_path):
    _, adapter, _ = asked([text_step(QUESTION), tools_step(OFFER)], registry, cfg, tmp_path)
    ask = adapter.requests[1]
    assert len(ask.messages) == 1
    assert [t.name for t in ask.tools] == ["offer_choices"]


def test_turn_record_has_offer_choices_and_offer_is_fresh(registry, cfg, tmp_path):
    app = make_app(registry, tmp_path, scripted([text_step(QUESTION), tools_step(OFFER)]))
    reply = app.handle("Иду")
    assert reply.turn.requests == ["offer_choices"]
    assert "offer_choices" in app.bundle.memory.recent_turns[-1].requests
    assert offer_is_stale(app) is False
    assert app.bundle.session.offered_choices == ["Открыть", "Уйти"]


def test_ask_is_not_a_retry_of_the_turn(registry, cfg, tmp_path):
    rig, adapter, result = asked(
        [text_step(QUESTION), tools_step(OFFER)], registry, cfg, tmp_path
    )
    assert rig.runner.note is None
    assert rig.runner.bundle.session.turn_seq == 1
    assert len(rig.runner.bundle.memory.recent_turns) == 1


def test_journal_has_ask_call_under_same_run_id_and_next_number(registry, cfg, tmp_path):
    rig, _, result = asked([text_step(QUESTION), tools_step(OFFER)], registry, cfg, tmp_path)
    records = run_records(rig.journal, result.run_id)
    assert [r["call_id"] for r in records] == [f"{result.run_id}-1", f"{result.run_id}-2"]
    assert {r["turn_status"] for r in records} == {"committed"}


def test_ask_failure_does_not_fail_the_turn(registry, cfg, tmp_path):
    rig, _, result = asked(
        [text_step(QUESTION), {"stop": "refusal"}], registry, cfg, tmp_path
    )
    assert result.committed is True
    assert result.failure is None
    assert result.narration == QUESTION
    assert result.report_tags == ["choices_retry"]


def test_text_answer_to_ask_commits_turn_without_menu_offer(registry, cfg, tmp_path):
    app = make_app(registry, tmp_path, scripted([text_step(QUESTION), text_step("Ладно.")]))
    reply = app.handle("Иду")
    assert reply.turn.committed is True
    assert reply.turn.requests == []
    assert offer_is_stale(app) is True


def test_no_ask_when_offer_choices_called(registry, cfg, tmp_path):
    steps = [tools_step(OFFER, text=QUESTION), text_step("лишний")]
    _, adapter, result = asked(steps, registry, cfg, tmp_path)
    assert result.report_tags == []
    assert len(adapter.requests) == 1


# бой

def fight(registry, cfg, tmp_path):
    steps = [
        tools_step(start_combat_call(intent="capture")),
        text_step("Твой ход — как ты атакуешь?"),
    ]
    adapter = script_then_react(steps)
    return make_rig(registry, cfg, tmp_path, adapter), adapter


def asks_in(adapter):
    return [
        b for r in adapter.requests for m in r.messages for b in m.content
        if isinstance(b, Text) and b.text.endswith(CHOICES_ASK)
    ]


def test_start_combat_turn_with_question_is_not_asked(registry, cfg, tmp_path):
    rig, adapter = fight(registry, cfg, tmp_path)
    result = rig.runner.play("Нападаю")
    assert rig.runner.bundle.session.active_combat is not None
    assert "choices_retry" not in result.report_tags
    assert asks_in(adapter) == []


def test_combat_turn_is_not_asked(registry, cfg, tmp_path):
    rig, adapter = fight(registry, cfg, tmp_path)
    rig.runner.play("Нападаю")
    adapter.then.classify = [player_action_input(["end_turn"])]
    result = rig.runner.play("Стою и жду")
    assert "choices_retry" not in result.report_tags
    assert asks_in(adapter) == []


# авто-репорт

def issues(tmp_path, world_id="w1"):
    folder = tmp_path / world_id / "issues"
    return sorted(folder.iterdir()) if folder.exists() else []


def test_choices_retry_writes_auto_report(registry, tmp_path):
    adapter = scripted([text_step(QUESTION), tools_step(OFFER)])
    app = make_app(registry, tmp_path, adapter, auto_reports=True)
    reply = app.handle("Иду")
    assert reply.turn.report_tags == ["choices_retry"]
    assert len(issues(tmp_path)) == 1
    assert issues(tmp_path)[0].name.endswith("-choices_retry")
    meta = json.loads((issues(tmp_path)[0] / "meta.json").read_text(encoding="utf-8"))
    assert "choices_retry" in json.dumps(meta, ensure_ascii=False)


def test_choices_retry_report_off_writes_nothing(registry, tmp_path):
    adapter = scripted([text_step(QUESTION), tools_step(OFFER)])
    app = make_app(registry, tmp_path, adapter, auto_reports=False)
    app.handle("Иду")
    assert issues(tmp_path) == []
