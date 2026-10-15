# T5 (мини-партия #18, TV-PLAN): ends_with_choice, MasterSession.choices_missing / ask_choices,
# CHOICES_ASK. Ход кончился вопросом/списком, а offer_choices не вызван -- один дополнительный
# вызов в том же цикле (тег choices_retry), без повтора хода.
import pytest
from master_kit import (
    combat_ctx,
    flag_call,
    make_ctx,
    make_session,
    reject_all,
    scripted,
    text_step,
    tools_step,
)

from ai_dm.llm.types import Text
from ai_dm.master.session import CHOICES_ASK, TurnFailed, ends_with_choice
from ai_dm.protocol.apply import apply

QUESTION = "Ты стоишь у двери.\n\nОткрыть её?"
TRANSIENT = {"error": "transient", "message": "сеть недоступна"}


def offer_call(call_id="o1", choices=("Бежать", "Драться")):
    return {
        "id": call_id, "name": "offer_choices",
        "input": {"type": "offer_choices", "choices": list(choices)},
    }


def check_call(call_id="sc1"):
    return {
        "id": call_id, "name": "skill_check",
        "input": {
            "type": "skill_check", "skill": "perception", "category": "medium",
            "stakes": "normal",
        },
    }


def go(steps, tmp_path, registry, cfg, role="narrator", mode="explore", executor=apply, **kw):
    adapter = scripted(steps)
    session, journal, _, sleeps = make_session(adapter, tmp_path, role=role, **kw)
    ctx = make_ctx(registry, cfg, mode=mode)
    result = session.run(ctx, "Иду.", executor, mode)
    return adapter, result, ctx


# ends_with_choice

@pytest.mark.parametrize("text", [
    "Ты у двери. Открыть её?",
    "Сцена.\n\n- Бежать\n- Драться",
    "Сцена.\n\n— Бежать\n— Драться",
    "Сцена.\n\n1. Бежать\n2) Драться",
    "Сцена.\n\n• Бежать\n• Драться",
    "Сцена.\n\n* Бежать\n* Драться",
    "Сцена.\n\nБежать\nДраться\nСпрятаться",
    "Сцена.\n\nБежать | Драться",
    "Сцена.\n\nВыбери:\n- Бежать\n- Драться\n",
])
def test_ends_with_choice_true(text):
    assert ends_with_choice(text) is True


@pytest.mark.parametrize("text", [
    "Сцена.\n\n- Бежать",
    "Сцена.\n\nБежать.\nДраться.",
    "Сцена.\n\nБежать!\nДраться…",
    "Сцена.\n\n«Бежать»\n«Драться»",
    "Сцена.\n\n" + "а" * 121 + "\n" + "б" * 121,
    "Ты стоишь у двери. Ветер стих.",
    "— Ну что? — спрашивает Селена.",
    "",
    "   \n  ",
    "Вопрос?\n\nСцена закончилась.",
    "Сцена.\n\nОдна короткая строка",
])
def test_ends_with_choice_false(text):
    assert ends_with_choice(text) is False


def test_ends_with_choice_line_of_120_is_short_and_121_is_long():
    ok = "а" * 120
    assert ends_with_choice(f"Сцена.\n\n{ok}\n{ok}") is True
    long = "а" * 121
    assert ends_with_choice(f"Сцена.\n\n{ok}\n{long}") is False


def test_ends_with_choice_mixed_marker_and_bare_lines_is_false_for_markers():
    # маркеры не у всех строк; строки не «голые» (одна с маркером): ни одно правило не сработало
    assert ends_with_choice("Сцена.\n\n- Бежать\nДраться.") is False


def test_ends_with_choice_question_not_last_line_is_false():
    assert ends_with_choice("Открыть её?\n\nОна заперта.") is False


def test_ends_with_choice_last_paragraph_only():
    # список в середине, последний абзац — проза
    assert ends_with_choice("- a\n- b\n\nКонец сцены.") is False


DRAGON_TAILS = [
    "Выбери дальнейшее действие:\n- Осмотреть замок и повернуть ключ в решётчатой двери\n"
    "- Проверить тоннель позади на случай погони\n"
    "- Обыскать стены и ниши вокруг шлюза в поисках скрытых знаков или ловушек",
    "Ты подходишь к преграде вплотную. Рука уверенно ложится на холодный металл ключа.\n\n"
    "Осмотреть замок и повернуть ключ в решётчатой двери?",
    "Выбери дальнейшее действие:\n- Ступить в тёмный коридор галереи и двигаться вперёд\n"
    "- Осмотреть шлюзовую камеру на предмет потайных дверей или улик\n"
    "- Осторожно прислушаться к звукам впереди, припав к стене вместе с Акелой",
    "Путь к заветным камерам Ратуши лежит прямо через их пост.\n\n"
    "Осторожно двинуться вперёд вместе с Акелой и атаковать врагов из тени\n"
    "Обойти пост по старому вентиляционному лазу, запримеченному под потолком\n"
    "Подождать в засаде, пока один из культистов не отойдёт вглубь коридора",
]


@pytest.mark.parametrize("tail", DRAGON_TAILS)
def test_ends_with_choice_real_dragon_tails(tail):
    assert ends_with_choice(tail) is True


# CHOICES_ASK

def test_choices_ask_text():
    assert "offer_choices" in CHOICES_ASK
    assert "два или три" in CHOICES_ASK
    assert "не повторяй" in CHOICES_ASK


# приписка: запрос

def test_question_without_offer_makes_one_more_call(tmp_path, registry, cfg):
    adapter, _, _ = go(
        [text_step(QUESTION), tools_step(offer_call())], tmp_path, registry, cfg
    )
    assert len(adapter.requests) == 2


def test_ask_request_appends_assistant_and_user_ask(tmp_path, registry, cfg):
    adapter, _, _ = go([text_step(QUESTION), tools_step(offer_call())], tmp_path, registry, cfg)
    first, second = adapter.requests
    assert len(second.messages) == len(first.messages) + 2
    assistant, user = second.messages[-2], second.messages[-1]
    assert assistant.role == "assistant"
    assert [b.text for b in assistant.content] == [QUESTION]
    assert user.role == "user"
    assert [type(b) for b in user.content] == [Text]
    assert user.content[0].text == CHOICES_ASK


def test_ask_messages_have_no_cache_and_first_message_is_unchanged(tmp_path, registry, cfg):
    adapter, _, _ = go([text_step(QUESTION), tools_step(offer_call())], tmp_path, registry, cfg)
    first, second = adapter.requests
    assert second.messages[0] == first.messages[0]
    assert second.messages[-2].cache is False
    assert second.messages[-1].cache is False


def test_ask_after_tool_round_keeps_history(tmp_path, registry, cfg):
    steps = [tools_step(flag_call("a", "c1")), text_step(QUESTION), tools_step(offer_call())]
    adapter, _, _ = go(steps, tmp_path, registry, cfg)
    assert len(adapter.requests) == 3
    assert len(adapter.requests[2].messages) == len(adapter.requests[1].messages) + 2


# приписка: результат

def test_ask_answer_offer_choices_is_executed(tmp_path, registry, cfg):
    _, result, ctx = go([text_step(QUESTION), tools_step(offer_call())], tmp_path, registry, cfg)
    assert ctx.bundle.session.offered_choices == ["Бежать", "Драться"]
    assert [r.type for r in result.requests] == ["offer_choices"]
    assert [d.status for d in result.decisions] == ["accepted"]
    assert "offer_choices" in result.accepted


def test_ask_answer_texts_are_not_in_narration(tmp_path, registry, cfg):
    steps = [text_step(QUESTION), tools_step(offer_call(), text="Лишний текст.")]
    _, result, _ = go(steps, tmp_path, registry, cfg)
    assert result.texts == [QUESTION]
    assert result.narration == QUESTION
    assert "Лишний" not in result.narration


def test_ask_has_choices_retry_tag(tmp_path, registry, cfg):
    _, result, _ = go([text_step(QUESTION), tools_step(offer_call())], tmp_path, registry, cfg)
    assert result.report_tags == ["choices_retry"]


def test_ask_does_not_change_rounds_and_invalid_count(tmp_path, registry, cfg):
    _, result, _ = go([text_step(QUESTION), tools_step(offer_call())], tmp_path, registry, cfg)
    assert result.rounds == 0
    assert result.invalid_count == 0


def test_ask_does_not_change_rounds_after_tool_round(tmp_path, registry, cfg):
    steps = [tools_step(flag_call("a", "c1")), text_step(QUESTION), tools_step(offer_call())]
    _, result, _ = go(steps, tmp_path, registry, cfg)
    assert result.rounds == 1


def test_ask_stop_reason_is_from_ask_answer(tmp_path, registry, cfg):
    steps = [text_step(QUESTION), tools_step(offer_call(), stop="max_tokens")]
    _, result, _ = go(steps, tmp_path, registry, cfg)
    assert result.stop_reason == "max_tokens"


def test_ask_tool_use_stop_reason_is_tool_use(tmp_path, registry, cfg):
    _, result, _ = go([text_step(QUESTION), tools_step(offer_call())], tmp_path, registry, cfg)
    assert result.stop_reason == "tool_use"


def test_ask_answer_with_text_only_accepts_turn_as_is(tmp_path, registry, cfg):
    adapter, result, ctx = go([text_step(QUESTION), text_step("Не буду.")], tmp_path, registry, cfg)
    assert len(adapter.requests) == 2
    assert result.narration == QUESTION
    assert result.texts == [QUESTION]
    assert result.report_tags == ["choices_retry"]
    assert result.requests == []
    assert ctx.bundle.session.offered_choices == []


def test_ask_is_made_once_only(tmp_path, registry, cfg):
    steps = [text_step(QUESTION), text_step("Опять вопрос?"), text_step("лишний")]
    adapter, _, _ = go(steps, tmp_path, registry, cfg)
    assert len(adapter.requests) == 2


def test_ask_offer_choices_with_four_items_is_accepted_as_is(tmp_path, registry, cfg):
    four = offer_call(choices=("а", "б", "в", "г"))
    steps = [text_step(QUESTION), tools_step(four), text_step("лишний")]
    adapter, result, ctx = go(steps, tmp_path, registry, cfg)
    assert len(adapter.requests) == 2
    assert result.invalid_count == 0
    assert result.narration == QUESTION
    assert result.report_tags == ["choices_retry"]
    assert result.decisions == []
    assert ctx.bundle.session.offered_choices == []


def test_ask_executes_only_offer_choices_not_skill_check(tmp_path, registry, cfg):
    steps = [text_step(QUESTION), tools_step(check_call(), offer_call())]
    _, result, _ = go(steps, tmp_path, registry, cfg)
    assert [r.type for r in result.requests] == ["offer_choices"]
    assert [d.status for d in result.decisions] == ["accepted"]


def test_ask_offer_choices_first_then_skill_check(tmp_path, registry, cfg):
    steps = [text_step(QUESTION), tools_step(offer_call(), check_call())]
    _, result, _ = go(steps, tmp_path, registry, cfg)
    assert [r.type for r in result.requests] == ["offer_choices"]
    assert len(result.decisions) == 1


def test_ask_skill_check_alone_is_not_executed(tmp_path, registry, cfg):
    _, result, _ = go([text_step(QUESTION), tools_step(check_call())], tmp_path, registry, cfg)
    assert result.requests == []
    assert result.decisions == []
    assert result.narration == QUESTION


def test_ask_executes_only_the_first_offer_choices(tmp_path, registry, cfg):
    steps = [
        text_step(QUESTION),
        tools_step(offer_call("o1", ("а", "б")), offer_call("o2", ("в", "г", "д"))),
    ]
    _, result, ctx = go(steps, tmp_path, registry, cfg)
    assert len(result.requests) == 1
    assert ctx.bundle.session.offered_choices == ["а", "б"]


# приписка: сбои приписки не откатывают ход

def test_ask_refusal_is_swallowed(tmp_path, registry, cfg):
    adapter, result, _ = go([text_step(QUESTION), {"stop": "refusal"}], tmp_path, registry, cfg)
    assert result.narration == QUESTION
    assert result.report_tags == ["choices_retry"]
    assert len(adapter.requests) == 2


def test_ask_network_failure_is_swallowed(tmp_path, registry, cfg):
    steps = [text_step(QUESTION)] + [TRANSIENT] * 4
    adapter, result, _ = go(steps, tmp_path, registry, cfg)
    assert result.narration == QUESTION
    assert result.report_tags == ["choices_retry"]
    assert len(adapter.requests) == 5


def test_ask_fatal_is_swallowed(tmp_path, registry, cfg):
    steps = [text_step(QUESTION), {"error": "fatal", "message": "плохой ключ"}]
    _, result, _ = go(steps, tmp_path, registry, cfg)
    assert result.narration == QUESTION
    assert result.report_tags == ["choices_retry"]


def test_failures_of_the_main_call_are_still_raised(tmp_path, registry, cfg):
    with pytest.raises(TurnFailed) as info:
        go([{"stop": "refusal"}], tmp_path, registry, cfg)
    assert info.value.reason == "refusal"


# приписки нет

def test_no_ask_when_offer_choices_accepted_in_early_exit(tmp_path, registry, cfg):
    steps = [tools_step(offer_call(), text=QUESTION), text_step("лишний")]
    adapter, result, _ = go(steps, tmp_path, registry, cfg)
    assert len(adapter.requests) == 1
    assert result.report_tags == []


def test_no_ask_when_offer_choices_accepted_in_earlier_round(tmp_path, registry, cfg):
    steps = [tools_step(offer_call(), flag_call("a", "c1")), text_step(QUESTION)]
    adapter, result, _ = go(steps, tmp_path, registry, cfg)
    assert len(adapter.requests) == 2
    assert "choices_retry" not in result.report_tags


def test_no_ask_when_offer_choices_accepted_and_text_in_final(tmp_path, registry, cfg):
    steps = [tools_step(offer_call()), text_step(QUESTION)]
    adapter, result, _ = go(steps, tmp_path, registry, cfg)
    assert len(adapter.requests) == 2
    assert result.report_tags == []


@pytest.mark.parametrize("role", ["world", "summarizer"])
def test_no_ask_for_other_roles(tmp_path, registry, cfg, role):
    adapter, result, _ = go([text_step(QUESTION), text_step("лишний")], tmp_path, registry, cfg,
                            role=role)
    assert len(adapter.requests) == 1
    assert result.report_tags == []


def test_no_ask_in_combat_narrate(tmp_path, registry, cfg):
    adapter = scripted([text_step(QUESTION), text_step("лишний")])
    session, _, _, _ = make_session(adapter, tmp_path)
    ctx = combat_ctx(registry, cfg, "combat_narrate")
    result = session.run(ctx, "Бью.", apply, "combat_narrate")
    assert len(adapter.requests) == 1
    assert result.report_tags == []


def test_no_ask_in_combat_classify(tmp_path, registry, cfg):
    from master_kit import player_action_call

    steps = [tools_step(player_action_call()), text_step(QUESTION), text_step("лишний")]
    adapter = scripted(steps)
    session, _, _, _ = make_session(adapter, tmp_path)
    ctx = combat_ctx(registry, cfg, "combat_classify")
    result = session.run(ctx, "Бью.", apply, "combat_classify")
    assert len(adapter.requests) == 2
    assert "choices_retry" not in result.report_tags


def test_no_ask_when_combat_is_active_in_explore(tmp_path, registry, cfg):
    adapter = scripted([text_step(QUESTION), text_step("лишний")])
    session, _, _, _ = make_session(adapter, tmp_path)
    ctx = combat_ctx(registry, cfg, "explore")
    result = session.run(ctx, "Иду.", apply, "explore")
    assert len(adapter.requests) == 1
    assert result.report_tags == []


def test_no_ask_for_text_without_signs(tmp_path, registry, cfg):
    adapter, result, _ = go([text_step("Ты идёшь дальше."), text_step("лишний")],
                            tmp_path, registry, cfg)
    assert len(adapter.requests) == 1
    assert result.report_tags == []


def test_no_ask_for_text_without_signs_after_rejected_offer(tmp_path, registry, cfg):
    steps = [tools_step(offer_call()), text_step("Ты идёшь дальше."), text_step("лишний")]
    adapter, result, _ = go(steps, tmp_path, registry, cfg, executor=reject_all)
    assert len(adapter.requests) == 2
    assert "choices_retry" not in result.report_tags


def test_ask_after_rejected_offer_and_list_text_once(tmp_path, registry, cfg):
    steps = [
        tools_step(offer_call()), text_step("Сцена.\n\n- Бежать\n- Драться"),
        tools_step(offer_call("o2")),
    ]
    calls = []

    def executor(ctx, request):
        calls.append(request.type)
        if len(calls) == 1:
            return reject_all(ctx, request)
        return apply(ctx, request)

    adapter, result, ctx = go(steps, tmp_path, registry, cfg, executor=executor)
    assert len(adapter.requests) == 3
    assert "choices_retry" in result.report_tags
    assert ctx.bundle.session.offered_choices == ["Бежать", "Драться"]


def test_no_ask_after_invalid_offer_without_signs(tmp_path, registry, cfg):
    bad = {"id": "o1", "name": "offer_choices", "input": {"type": "offer_choices"}}
    steps = [tools_step(bad), text_step("Ты идёшь дальше."), text_step("лишний")]
    adapter, result, _ = go(steps, tmp_path, registry, cfg)
    assert len(adapter.requests) == 2
    assert "choices_retry" not in result.report_tags


# короткий текст

def test_short_question_text_only_turn_is_asked(tmp_path, registry, cfg):
    adapter, result, _ = go([text_step("Дверь?"), tools_step(offer_call())], tmp_path, registry,
                            cfg)
    assert len(adapter.requests) == 2
    assert result.rounds == 0
    assert result.report_tags == ["choices_retry"]


# журнал

def test_ask_call_is_in_journal_under_same_run_id_with_next_number(tmp_path, registry, cfg):
    adapter = scripted([text_step(QUESTION), tools_step(offer_call())])
    session, journal, _, _ = make_session(adapter, tmp_path)
    ctx = make_ctx(registry, cfg, mode="explore")
    session.run(ctx, "Иду.", apply, "explore")
    records = journal.read_records()
    assert [r["run_id"] for r in records] == ["run-1", "run-1"]
    assert [r["call_id"] for r in records] == ["run-1-1", "run-1-2"]


# мутанты ТВ (партия #18): plan и refusal в ask_choices

def test_ask_call_in_journal_has_context_meta_like_main_call(tmp_path, registry, cfg):
    adapter = scripted([text_step(QUESTION), tools_step(offer_call())])
    session, journal, _, _ = make_session(adapter, tmp_path)
    ctx = make_ctx(registry, cfg, mode="explore")
    session.run(ctx, "Иду.", apply, "explore")
    records = journal.read_records()
    assert "context" in records[0]["meta"]
    assert "context" in records[1]["meta"]


def test_ask_refusal_answer_with_offer_choices_is_not_executed(tmp_path, registry, cfg):
    steps = [text_step(QUESTION), tools_step(offer_call(), stop="refusal")]
    _, result, ctx = go(steps, tmp_path, registry, cfg)
    assert result.requests == []
    assert ctx.bundle.session.offered_choices == []
    assert result.stop_reason == "refusal"
