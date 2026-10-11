# AD1, W5: ограда блока в report.md длиннее любой серии ` внутри текста, иначе текст закрывает
# блок раньше времени. Без ` в тексте -- прежние три обратные кавычки.
from ai_dm.reports.markdown import call_lines, fence, message_lines


def text_block(text):
    return {"type": "text", "text": text}


def message(*texts):
    return {"role": "user", "content": [text_block(t) for t in texts]}


def record(response_texts, message_texts=("Привет",)):
    return {
        "call_id": "c1", "role": "narrator", "attempt": 1, "run_id": "r1", "model": "m",
        "requested_model": "m", "stop_reason": "end_turn", "turn_status": "committed",
        "error": None,
        "request": {
            "system_sha256": "s", "tools_sha256": "t",
            "messages": [message(*message_texts)],
        },
        "response": {"content": [text_block(t) for t in response_texts]},
    }


def fences_of(lines):
    # строки-ограды отступлены на два пробела, текст блока -- нет
    return [line.strip() for line in lines if line.startswith("  `")]


# fence

def test_fence_of_plain_text_is_three_backticks():
    assert fence("просто текст") == "```"


def test_fence_of_empty_text_is_three_backticks():
    assert fence("") == "```"


def test_fence_of_one_backtick_is_three():
    assert fence("a `b` c") == "```"


def test_fence_of_two_backticks_is_three():
    assert fence("a ``b`` c") == "```"


def test_fence_of_three_backticks_is_four():
    assert fence("до\n```\nпосле") == "````"


def test_fence_of_four_backticks_is_five():
    assert fence("````") == "`````"


def test_fence_uses_longest_run_not_total():
    assert fence("`` `` `` ``") == "```"


def test_fence_run_at_end_of_text_counts():
    assert fence("конец ```") == "````"


def test_fence_run_at_start_of_text_counts():
    assert fence("```начало") == "````"


def test_fence_longest_run_after_shorter_run():
    assert fence("`` потом ````` и ```") == "``````"


# message_lines

def test_message_without_backticks_is_as_before():
    assert message_lines(message("Привет")) == ["- user:", "", "  ```", "Привет", "  ```"]


def test_message_with_code_fence_gets_longer_fence():
    lines = message_lines(message("до\n```\nпосле"))
    assert lines == ["- user:", "", "  ````", "до\n```\nпосле", "  ````"]


def test_message_blocks_get_fences_each_by_own_text():
    lines = message_lines(message("обычный", "код ```"))
    assert fences_of(lines) == ["```", "```", "````", "````"]


def test_message_tool_result_with_backticks_is_fenced():
    msg = {"role": "user", "content": [{"type": "tool_result", "content": "```x```"}]}
    assert fences_of(message_lines(msg)) == ["````", "````"]


# call_lines

def test_call_response_without_backticks_is_as_before():
    lines = call_lines(record(["Ответ"]))
    assert lines[lines.index("Ответ:") + 2:][:3] == ["  ```", "Ответ", "  ```"]


def test_call_response_with_code_fence_gets_longer_fence():
    lines = call_lines(record(["```py\nx\n```"]))
    start = lines.index("Ответ:") + 2
    assert lines[start:start + 3] == ["  ````", "```py\nx\n```", "  ````"]


def test_call_request_with_code_fence_gets_longer_fence():
    lines = call_lines(record(["Ответ"], message_texts=("```",)))
    request_part = lines[lines.index("Запрос:"):lines.index("Ответ:")]
    assert fences_of(request_part) == ["````", "````"]


def test_call_response_fences_are_independent_per_block():
    lines = call_lines(record(["обычный", "````"]))
    response_part = lines[lines.index("Ответ:"):]
    assert fences_of(response_part) == ["```", "```", "`````", "`````"]


def test_call_without_response_has_no_response_section():
    data = record(["x"])
    data["response"] = None
    assert "Ответ:" not in call_lines(data)


def test_markdown_never_closes_block_early():
    # открывающая ограда блока строго длиннее любой серии внутри текста
    text = "a ``` b ```` c"
    lines = message_lines(message(text))
    bar = fence(text)
    assert lines[2].strip() == bar
    assert "`" * len(bar) not in text
