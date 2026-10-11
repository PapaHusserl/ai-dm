# Ожидаемый API (этап 6а, P1): render(capture, text, calls=None, recent_turns=5) -> str.
# calls=None -- журнал отключён; [] -- «вызовов модели в ходе не было»; иначе по каждой записи:
# роль, модель (запрошенная), попытка, stop_reason, статус хода, ссылки на блобы system/tools
# (не инлайн), сообщения запроса и ответ. «Последние ходы» -- последние recent_turns из памяти
# after (если ход принят) или before, с фразой, рассказом и бросками.
from reports_kit import make_capture

from ai_dm.reports.markdown import render
from ai_dm.state.scene import TurnRecord


def turn(n, rolls=()):
    return TurnRecord(
        turn_seq=n, at_s=n, player_input=f"фраза-{n}-x", narration=f"рассказ-{n}-y",
        rolls=list(rolls),
    )


def call(**fields):
    data = {
        "call_id": "c1", "run_id": "run-1", "role": "narrator", "attempt": 1,
        "model": "claude-opus-5-5", "requested_model": "claude-opus-5-5",
        "stop_reason": "end_turn", "turn_status": "committed", "error": None,
        "request": {
            "system_sha256": "a" * 64, "tools_sha256": "b" * 64,
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": "запрос-игрока-z"}]},
            ],
        },
        "response": {"content": [{"type": "text", "text": "ответ-мастера-w"}]},
    }
    data.update(fields)
    return data


def capture_with_turns(registry, count, **fields):
    capture = make_capture(registry, **fields)
    capture.before.memory.recent_turns = [turn(n) for n in range(1, count + 1)]
    return capture


def recent_part(report):
    start = report.index("## Последние ходы")
    end = report.find("\n## ", start + 1)
    return report[start:] if end == -1 else report[start:end]


# журнал

def test_calls_none_says_journal_is_off(registry):
    report = render(make_capture(registry), "текст", None)
    assert "журнал отключён, воспроизведение невозможно" in report.lower()


def test_calls_empty_says_no_model_calls(registry):
    report = render(make_capture(registry), "текст", [])
    assert "Вызовов модели в ходе не было" in report
    assert "журнал отключён" not in report.lower()


def test_call_has_role_attempt_stop_reason_and_status(registry):
    report = render(make_capture(registry), "текст", [call(role="world", attempt=2)])
    assert "world" in report
    assert "попытка 2" in report
    assert "stop_reason: end_turn" in report
    assert "статус хода: committed" in report


def test_call_has_model_and_requested_model(registry):
    record = call(model="gemini-x", requested_model="gemini-requested")
    report = render(make_capture(registry), "текст", [record])
    assert "gemini-x" in report
    assert "gemini-requested" in report


def test_call_has_request_message_and_response(registry):
    report = render(make_capture(registry), "текст", [call()])
    assert "запрос-игрока-z" in report
    assert "ответ-мастера-w" in report


def test_call_references_blobs_by_sha(registry):
    report = render(make_capture(registry), "текст", [call()])
    assert f"journal/blobs/{'a' * 64}.json" in report
    assert f"journal/blobs/{'b' * 64}.json" in report


def test_call_with_error_shows_error_kind_and_no_response(registry):
    error = {"kind": "transient", "message": "сеть", "retry_after": None}
    record = call(error=error, response=None)
    report = render(make_capture(registry), "текст", [record])
    assert "transient" in report
    assert "Ответ:" not in report


def test_call_shows_tool_call_and_tool_result_blocks(registry):
    record = call()
    record["response"] = {
        "content": [{"type": "tool_call", "id": "t1", "name": "advance_time", "input": {"m": 5}}],
    }
    record["request"]["messages"].append(
        {"role": "user", "content": [{"type": "tool_result", "call_id": "t1", "content": "итог-z"}]}
    )
    report = render(make_capture(registry), "текст", [record])
    assert "advance_time" in report
    assert "итог-z" in report


def test_two_calls_are_both_in_report(registry):
    records = [call(call_id="c1", attempt=1), call(call_id="c2", attempt=2)]
    report = render(make_capture(registry), "текст", records)
    assert "Вызов c1" in report
    assert "Вызов c2" in report


def test_models_section_lists_model_per_role(registry):
    records = [call(role="narrator", model="m-narr"), call(role="world", model="m-world")]
    report = render(make_capture(registry), "текст", records)
    assert "narrator: m-narr" in report
    assert "world: m-world" in report


# последние ходы

def test_recent_turns_are_cut_to_n(registry):
    report = render(capture_with_turns(registry, 7), "текст", [], 3)
    part = recent_part(report)
    for n in (5, 6, 7):
        assert f"фраза-{n}-x" in part
    assert "фраза-4-x" not in part


def test_recent_turns_default_is_five(registry):
    part = recent_part(render(capture_with_turns(registry, 7), "текст", []))
    assert "фраза-3-x" in part
    assert "фраза-2-x" not in part


def test_recent_turns_has_narration(registry):
    part = recent_part(render(capture_with_turns(registry, 2), "текст", []))
    assert "рассказ-1-y" in part
    assert "рассказ-2-y" in part


def test_recent_turns_in_chronological_order(registry):
    part = recent_part(render(capture_with_turns(registry, 3), "текст", []))
    assert part.index("фраза-1-x") < part.index("фраза-2-x") < part.index("фраза-3-x")


def test_recent_turns_has_rolls(registry):
    capture = make_capture(registry)
    capture.before.memory.recent_turns = [turn(1, rolls=["d20=17 Убеждение"])]
    assert "d20=17 Убеждение" in recent_part(render(capture, "текст", []))


def test_recent_turns_without_rolls_has_no_rolls_header(registry):
    part = recent_part(render(capture_with_turns(registry, 1), "текст", []))
    assert "Броски" not in part


def test_recent_turns_note_when_fewer_than_n(registry):
    part = recent_part(render(capture_with_turns(registry, 2), "текст", [], 5))
    assert "меньше ходов, чем запрошено" in part
    assert "Показано ходов: 2" in part


def test_recent_turns_no_note_when_exactly_n(registry):
    part = recent_part(render(capture_with_turns(registry, 5), "текст", [], 5))
    assert "меньше ходов, чем запрошено" not in part


def test_recent_turns_taken_from_after_when_committed(registry):
    capture = capture_with_turns(registry, 1)
    after = capture.before.model_copy(deep=True)
    after.memory.recent_turns.append(turn(2))
    capture.after = after
    part = recent_part(render(capture, "текст", []))
    assert "фраза-2-x" in part


def test_recent_turns_taken_from_before_when_aborted(registry):
    capture = capture_with_turns(registry, 2, status="aborted")
    part = recent_part(render(capture, "текст", []))
    assert "фраза-2-x" in part


def test_recent_turns_empty_memory_does_not_fail(registry):
    part = recent_part(render(make_capture(registry), "текст", []))
    assert "Показано ходов: 0" in part


# точные строки разметки

def test_section_headers_are_separate_lines(registry):
    lines = render(capture_with_turns(registry, 1), "текст", [call()]).splitlines()
    assert "## Последние ходы" in lines
    assert "## Вызовы модели хода" in lines
    assert "### Ход 1" in lines


def test_journal_off_lines_are_exact(registry):
    lines = render(make_capture(registry), "текст", None).splitlines()
    assert "## Вызовы модели" in lines
    assert "Журнал отключён, воспроизведение невозможно." in lines


def test_no_calls_line_is_exact_and_followed_by_blank_or_end(registry):
    lines = render(make_capture(registry), "текст", []).splitlines()
    assert "Вызовов модели в ходе не было." in lines
    assert "## Вызовы модели хода" in lines


def test_fewer_turns_note_is_exact_line(registry):
    lines = render(capture_with_turns(registry, 1), "текст", [], 5).splitlines()
    assert "В памяти игры хранится меньше ходов, чем запрошено." in lines


def test_rolls_header_is_exact_line_with_items(registry):
    capture = make_capture(registry)
    capture.before.memory.recent_turns = [turn(1, rolls=["a-roll", "b-roll"])]
    lines = render(capture, "текст", []).splitlines()
    assert "Броски:" in lines
    assert "- a-roll" in lines
    assert "- b-roll" in lines


def test_turn_in_recent_has_blank_lines_between_parts(registry):
    lines = render(capture_with_turns(registry, 1), "текст", []).splitlines()
    i = lines.index("### Ход 1")
    assert lines[i + 1] == ""
    assert lines[i + 2] == "Фраза игрока: фраза-1-x"
    assert lines[i + 3] == ""
    assert lines[i + 4] == "рассказ-1-y"


def test_message_with_two_blocks_shows_both_and_role(registry):
    record = call()
    record["request"]["messages"] = [
        {"role": "assistant", "content": [
            {"type": "text", "text": "блок-один"}, {"type": "text", "text": "блок-два"},
        ]},
    ]
    report = render(make_capture(registry), "текст", [record])
    assert "- assistant:" in report
    assert "блок-один" in report
    assert "блок-два" in report


def test_message_blocks_are_fenced(registry):
    report = render(make_capture(registry), "текст", [call()])
    assert report.count("  ```") >= 4


def test_tool_call_input_is_rendered_as_json_with_cyrillic(registry):
    record = call()
    record["response"] = {
        "content": [{"type": "tool_call", "id": "t1", "name": "x", "input": {"текст": "привет"}}],
    }
    report = render(make_capture(registry), "текст", [record])
    assert 'вызов x: {"текст": "привет"}' in report


def test_opaque_block_is_marked_with_provider(registry):
    record = call()
    record["response"] = {"content": [{"type": "opaque", "provider": "gemini", "raw": {}}]}
    assert "(служебный блок gemini)" in render(make_capture(registry), "текст", [record])


def test_calls_header_stays_with_several_calls(registry):
    report = render(make_capture(registry), "текст", [call(call_id="c1"), call(call_id="c2")])
    assert "## Вызовы модели хода" in report.splitlines()


def test_call_without_request_blocks_shows_status_and_blob_lines_exactly(registry):
    lines = render(make_capture(registry), "текст", [call()]).splitlines()
    assert "- run_id: run-1" in lines
    assert "- stop_reason: end_turn" in lines
    assert f"- system: journal/blobs/{'a' * 64}.json" in lines
    assert f"- tools: journal/blobs/{'b' * 64}.json" in lines
    assert "- модель: claude-opus-5-5 (запрошена claude-opus-5-5)" in lines
    assert "Запрос:" in lines
    assert "Ответ:" in lines
