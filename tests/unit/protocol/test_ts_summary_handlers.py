# ТС #22 (docs/plan-ts.md §1 п.2, §4): мягкий предел выжимки. trim_text режет по границе
# предложения, fit_text считает переполнения по ключам (scene/chapter/game) и после
# summary_trim_after отклонений отдаёт обрезанный текст; хендлеры scene_summary / chapter_summary /
# game_summary принимают его с логом и меткой summary_trimmed.
import pytest
from protocol_kit import make_ctx

from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.protocol.handlers.summary import accepted, fit_text, trim_text
from ai_dm.protocol.requests import parse_request

WORDS = "слово " * 300


def req(type_name, **fields):
    return parse_request({"type": type_name, **fields}, mode="summarize_scene")


def scene_ctx(registry, cfg, limit=600, after=2):
    ctx = make_ctx(registry, cfg, mode="summarize_scene")
    ctx.summary_max = limit
    ctx.summary_trim_after = after
    return ctx


def chapter_ctx(registry, cfg, chapter=1500, game=3000, after=2):
    ctx = make_ctx(registry, cfg, mode="summarize_chapter")
    ctx.chapter_summary_max = chapter
    ctx.game_summary_max = game
    ctx.summary_trim_after = after
    return ctx


# trim_text

def test_trim_text_keeps_text_not_longer_than_limit():
    assert trim_text("Короткий текст.", 100) == "Короткий текст."


def test_trim_text_keeps_text_exactly_at_limit():
    text = "а" * 50
    assert trim_text(text, 50) == text


def test_trim_text_cuts_by_last_sentence_end():
    text = "Первое предложение. Второе предложение. Третье предложение без конца"
    assert trim_text(text, 45) == "Первое предложение. Второе предложение."


def test_trim_text_sentence_end_exactly_at_limit_is_kept():
    text = "а" * 49 + ". продолжение текста"
    assert trim_text(text, 50) == "а" * 49 + "."


@pytest.mark.parametrize("mark", ["!", "?", "…"])
def test_trim_text_other_sentence_marks_are_boundaries(mark):
    text = f"Он ушёл далеко{mark} Потом вернулся обратно домой"
    assert trim_text(text, 30) == f"Он ушёл далеко{mark}"


def test_trim_text_keeps_closing_quote_after_sentence_end():
    text = "Он крикнул «Стой!» Потом они долго шли вдоль реки"
    assert trim_text(text, 25) == "Он крикнул «Стой!»"


def test_trim_text_keeps_closing_bracket_after_sentence_end():
    text = "Он ушёл (быстро.) Потом они долго шли вдоль реки"
    assert trim_text(text, 22) == "Он ушёл (быстро.)"


def test_trim_text_dot_inside_number_is_not_a_boundary():
    result = trim_text("Он прошёл 3.5 километра по дороге вдоль реки к вечеру", 30)
    assert result.endswith("…")
    assert len(result) <= 30


def test_trim_text_boundary_before_half_limit_goes_by_space_with_ellipsis():
    text = "Да. " + "слово " * 20
    result = trim_text(text, 40)
    assert result.endswith("слово…")
    assert len(result) <= 40
    assert len(result) > 4


def test_trim_text_by_space_does_not_cut_word():
    result = trim_text("слово " * 30, 40)
    assert result.endswith("слово…")
    assert len(result) <= 40


def test_trim_text_without_spaces_cuts_and_adds_ellipsis():
    result = trim_text("я" * 100, 50)
    assert result == "я" * 49 + "…"
    assert len(result) == 50


@pytest.mark.parametrize("size", [601, 750, 1568])
def test_trim_text_result_fits_600_and_is_not_empty(size):
    text = ("Герой пришёл в город и встретил Бранна. " * 60)[:size]
    result = trim_text(text, 600)
    assert 0 < len(result) <= 600


@pytest.mark.parametrize("size", [601, 750, 1568])
def test_trim_text_of_one_long_word_fits_600(size):
    result = trim_text("я" * size, 600)
    assert 0 < len(result) <= 600


def test_trim_text_no_sentence_marks_with_words_fits_limit():
    result = trim_text(WORDS, 600)
    assert 0 < len(result) <= 600
    assert result.endswith("слово…")


def test_trim_text_prefers_latest_sentence_boundary():
    text = "Раз. " + "а" * 20 + ". " + "б" * 20 + ". " + "в" * 40
    result = trim_text(text, 60)
    assert result.endswith("б" * 20 + ".")


# fit_text

def test_fit_text_empty_is_empty_summary_and_not_counted(registry, cfg):
    ctx = scene_ctx(registry, cfg)
    result = fit_text(ctx, "scene", "", 600, "Выжимка")
    assert isinstance(result, Invalid)
    assert result.code == "empty_summary"
    assert "Выжимка" in result.message
    assert ctx.summary_overflows == {}


def test_fit_text_within_limit_is_returned_and_not_counted(registry, cfg):
    ctx = scene_ctx(registry, cfg)
    assert fit_text(ctx, "scene", "Нормально.", 600, "Выжимка") == "Нормально."
    assert ctx.summary_overflows == {}


def test_fit_text_exactly_at_limit_is_valid(registry, cfg):
    ctx = scene_ctx(registry, cfg)
    text = "я" * 600
    assert fit_text(ctx, "scene", text, 600, "Выжимка") == text
    assert ctx.summary_overflows == {}


def test_fit_text_one_over_limit_is_overflow(registry, cfg):
    ctx = scene_ctx(registry, cfg)
    result = fit_text(ctx, "scene", "я" * 601, 600, "Выжимка")
    assert isinstance(result, Invalid)
    assert result.code == "summary_too_long"
    assert ctx.summary_overflows == {"scene": 1}


def test_fit_text_trim_after_zero_never_trims(registry, cfg):
    ctx = scene_ctx(registry, cfg, after=0)
    for _ in range(5):
        result = fit_text(ctx, "scene", "я" * 900, 600, "Выжимка")
        assert isinstance(result, Invalid)
        assert result.code == "summary_too_long"
        # без обрезки модели не обещают ни попыток, ни обрезки
        assert "Попытка" not in result.message
        assert "обрежет" not in result.message
    assert ctx.summary_overflows == {"scene": 5}


def test_fit_text_default_context_never_trims(registry, cfg):
    ctx = make_ctx(registry, cfg)
    for _ in range(4):
        assert isinstance(fit_text(ctx, "scene", "я" * 900, 600, "Выжимка"), Invalid)


def test_fit_text_first_two_overflows_are_invalid_with_attempt_numbers(registry, cfg):
    ctx = scene_ctx(registry, cfg)
    first = fit_text(ctx, "scene", "я" * 900, 600, "Выжимка")
    second = fit_text(ctx, "scene", "я" * 900, 600, "Выжимка")
    assert "Попытка 1 из 2" in first.message
    assert "Попытка 2 из 2" in second.message


def test_fit_text_message_has_length_limit_and_ratio(registry, cfg):
    ctx = scene_ctx(registry, cfg)
    message = fit_text(ctx, "scene", "я" * 900, 600, "Выжимка").message
    assert "900 симв." in message
    assert "предел 600" in message
    assert "в 1.5 раза" in message


def test_fit_text_message_ratio_has_one_decimal(registry, cfg):
    ctx = scene_ctx(registry, cfg)
    message = fit_text(ctx, "scene", "я" * 1200, 600, "Выжимка").message
    assert "в 2.0 раза" in message


def test_fit_text_message_keeps_label(registry, cfg):
    ctx = chapter_ctx(registry, cfg)
    message = fit_text(ctx, "chapter", "я" * 2000, 1500, "Выжимка главы").message
    assert message.startswith("Выжимка главы ")


def test_fit_text_third_overflow_is_trimmed_to_limit(registry, cfg):
    ctx = scene_ctx(registry, cfg)
    text = "Герой пришёл в город. " * 40
    fit_text(ctx, "scene", text, 600, "Выжимка")
    fit_text(ctx, "scene", text, 600, "Выжимка")
    result = fit_text(ctx, "scene", text, 600, "Выжимка")
    assert isinstance(result, str)
    assert 0 < len(result) <= 600
    assert result.endswith("в город.")
    assert ctx.summary_overflows == {"scene": 3}


def test_fit_text_trim_after_one_trims_on_second(registry, cfg):
    ctx = scene_ctx(registry, cfg, after=1)
    assert isinstance(fit_text(ctx, "scene", "я" * 900, 600, "Выжимка"), Invalid)
    assert isinstance(fit_text(ctx, "scene", "я" * 900, 600, "Выжимка"), str)


def test_fit_text_counters_are_separate_per_key(registry, cfg):
    ctx = chapter_ctx(registry, cfg)
    fit_text(ctx, "chapter", "я" * 2000, 1500, "Выжимка главы")
    fit_text(ctx, "chapter", "я" * 2000, 1500, "Выжимка главы")
    game = fit_text(ctx, "game", "я" * 4000, 3000, "game_summary")
    assert isinstance(game, Invalid)
    assert "Попытка 1 из 2" in game.message
    assert ctx.summary_overflows == {"chapter": 2, "game": 1}


def test_fit_text_empty_between_overflows_does_not_count(registry, cfg):
    ctx = scene_ctx(registry, cfg)
    fit_text(ctx, "scene", "я" * 900, 600, "Выжимка")
    fit_text(ctx, "scene", "", 600, "Выжимка")
    second = fit_text(ctx, "scene", "я" * 900, 600, "Выжимка")
    assert isinstance(second, Invalid)
    assert "Попытка 2 из 2" in second.message


# accepted

def test_accepted_without_trim_has_plain_log_and_no_tag():
    decision = accepted("Выжимка сцены", "Текст.", "Текст.")
    assert isinstance(decision, Decision)
    assert decision.status == "accepted"
    assert decision.log == ["Выжимка сцены принята"]
    assert decision.report_tag is None


def test_accepted_with_trim_logs_lengths_and_sets_tag():
    decision = accepted("Выжимка сцены", "я" * 750, "я" * 600)
    assert decision.status == "accepted"
    assert decision.log == ["Выжимка сцены принята с обрезкой 750→600 симв."]
    assert decision.report_tag == "summary_trimmed"


# scene_summary

def test_scene_summary_valid_text_is_accepted_without_tag(registry, cfg):
    ctx = scene_ctx(registry, cfg)
    decision = apply(ctx, req("scene_summary", title="Т", summary="  Герой пришёл.  "))
    assert decision.status == "accepted"
    assert decision.report_tag is None
    assert decision.log == ["Выжимка сцены принята"]
    assert ctx.summary_text == "Герой пришёл."
    assert ctx.summary_title == "Т"
    assert ctx.marks == []


def test_scene_summary_empty_title_is_empty_string(registry, cfg):
    ctx = scene_ctx(registry, cfg)
    apply(ctx, req("scene_summary", title="", summary="Текст."))
    assert ctx.summary_title == ""


def test_scene_summary_whitespace_only_is_empty_summary(registry, cfg):
    ctx = scene_ctx(registry, cfg)
    result = apply(ctx, req("scene_summary", title="", summary="   "))
    assert isinstance(result, Invalid)
    assert result.code == "empty_summary"
    assert ctx.summary_text is None


def test_scene_summary_second_call_is_already_done(registry, cfg):
    ctx = scene_ctx(registry, cfg)
    apply(ctx, req("scene_summary", title="", summary="Первая."))
    result = apply(ctx, req("scene_summary", title="", summary="Вторая."))
    assert isinstance(result, Invalid)
    assert result.code == "already_done"
    assert ctx.summary_text == "Первая."


def test_scene_summary_already_done_does_not_count_overflow(registry, cfg):
    ctx = scene_ctx(registry, cfg)
    apply(ctx, req("scene_summary", title="", summary="Первая."))
    apply(ctx, req("scene_summary", title="", summary="я" * 900))
    assert ctx.summary_overflows == {}


def test_scene_summary_overflow_is_invalid_and_state_untouched(registry, cfg):
    ctx = scene_ctx(registry, cfg)
    result = apply(ctx, req("scene_summary", title="Т", summary="я" * 601))
    assert isinstance(result, Invalid)
    assert result.code == "summary_too_long"
    assert ctx.summary_text is None
    assert ctx.summary_title == ""
    assert ctx.marks == []


def test_scene_summary_third_overflow_is_accepted_trimmed_with_tag(registry, cfg):
    ctx = scene_ctx(registry, cfg)
    text = "Герой пришёл в город. " * 40
    apply(ctx, req("scene_summary", title="", summary=text))
    apply(ctx, req("scene_summary", title="", summary=text))
    decision = apply(ctx, req("scene_summary", title="Т", summary=text))
    assert decision.status == "accepted"
    assert decision.report_tag == "summary_trimmed"
    assert 0 < len(ctx.summary_text) <= 600
    assert ctx.summary_title == "Т"
    assert ctx.marks == ["summary_trimmed"]
    assert decision.log == [
        f"Выжимка сцены принята с обрезкой {len(text.strip())}→{len(ctx.summary_text)} симв."
    ]


def test_scene_summary_trim_after_zero_never_accepts_overflow(registry, cfg):
    ctx = scene_ctx(registry, cfg, after=0)
    for _ in range(4):
        result = apply(ctx, req("scene_summary", title="", summary="я" * 900))
        assert isinstance(result, Invalid)
    assert ctx.summary_text is None
    assert ctx.marks == []


def test_scene_summary_uses_summary_max_of_context(registry, cfg):
    ctx = scene_ctx(registry, cfg, limit=10)
    result = apply(ctx, req("scene_summary", title="", summary="я" * 11))
    assert isinstance(result, Invalid)


def test_scene_summary_text_of_exact_limit_is_accepted_untrimmed(registry, cfg):
    ctx = scene_ctx(registry, cfg)
    decision = apply(ctx, req("scene_summary", title="", summary="я" * 600))
    assert decision.report_tag is None
    assert len(ctx.summary_text) == 600


# chapter_summary

def test_chapter_summary_valid_text_is_accepted_without_tag(registry, cfg):
    ctx = chapter_ctx(registry, cfg)
    decision = apply(ctx, req("chapter_summary", title="Глава", summary=" Итог главы. "))
    assert decision.status == "accepted"
    assert decision.report_tag is None
    assert decision.log == ["Выжимка главы принята"]
    assert ctx.chapter_text == "Итог главы."
    assert ctx.chapter_title_new == "Глава"


def test_chapter_summary_empty_is_invalid(registry, cfg):
    ctx = chapter_ctx(registry, cfg)
    result = apply(ctx, req("chapter_summary", title="", summary=""))
    assert isinstance(result, Invalid)
    assert result.code == "empty_summary"
    assert "главы" in result.message


def test_chapter_summary_repeat_overwrites(registry, cfg):
    ctx = chapter_ctx(registry, cfg)
    apply(ctx, req("chapter_summary", title="", summary="Первая."))
    apply(ctx, req("chapter_summary", title="", summary="Вторая."))
    assert ctx.chapter_text == "Вторая."


def test_chapter_summary_overflow_uses_chapter_key_and_limit(registry, cfg):
    ctx = chapter_ctx(registry, cfg)
    result = apply(ctx, req("chapter_summary", title="", summary="я" * 1501))
    assert isinstance(result, Invalid)
    assert result.code == "summary_too_long"
    assert "предел 1500" in result.message
    assert result.message.startswith("Выжимка главы ")
    assert ctx.summary_overflows == {"chapter": 1}
    assert ctx.chapter_text is None


def test_chapter_summary_third_overflow_is_trimmed_with_tag(registry, cfg):
    ctx = chapter_ctx(registry, cfg)
    text = "Герой пришёл в город. " * 100
    for _ in range(2):
        apply(ctx, req("chapter_summary", title="", summary=text))
    decision = apply(ctx, req("chapter_summary", title="Г", summary=text))
    assert decision.report_tag == "summary_trimmed"
    assert 0 < len(ctx.chapter_text) <= 1500
    assert ctx.chapter_title_new == "Г"
    assert ctx.marks == ["summary_trimmed"]
    assert decision.log[0].startswith("Выжимка главы принята с обрезкой ")


# game_summary

def test_game_summary_valid_text_is_accepted_without_tag(registry, cfg):
    ctx = chapter_ctx(registry, cfg)
    decision = apply(ctx, req("game_summary", summary=" История игры. "))
    assert decision.status == "accepted"
    assert decision.report_tag is None
    assert decision.log == ["Выжимка игры принята"]
    assert ctx.game_text == "История игры."


def test_game_summary_empty_is_invalid(registry, cfg):
    ctx = chapter_ctx(registry, cfg)
    result = apply(ctx, req("game_summary", summary=""))
    assert isinstance(result, Invalid)
    assert result.code == "empty_summary"
    assert "Выжимка игры пустая" in result.message


def test_game_summary_overflow_uses_game_key_and_limit(registry, cfg):
    ctx = chapter_ctx(registry, cfg)
    result = apply(ctx, req("game_summary", summary="я" * 3001))
    assert isinstance(result, Invalid)
    assert "предел 3000" in result.message
    assert result.message.startswith("Выжимка игры ")
    assert ctx.summary_overflows == {"game": 1}
    assert ctx.game_text is None


def test_game_summary_third_overflow_is_trimmed_with_tag(registry, cfg):
    ctx = chapter_ctx(registry, cfg)
    text = "Герой пришёл в город. " * 200
    for _ in range(2):
        apply(ctx, req("game_summary", summary=text))
    decision = apply(ctx, req("game_summary", summary=text))
    assert decision.report_tag == "summary_trimmed"
    assert 0 < len(ctx.game_text) <= 3000
    assert ctx.marks == ["summary_trimmed"]
    assert decision.log[0].startswith("Выжимка игры принята с обрезкой ")


def test_chapter_and_game_overflows_do_not_share_counter(registry, cfg):
    ctx = chapter_ctx(registry, cfg)
    for _ in range(2):
        apply(ctx, req("chapter_summary", title="", summary="я" * 2000))
    result = apply(ctx, req("game_summary", summary="я" * 4000))
    assert isinstance(result, Invalid)
    assert ctx.game_text is None


# усиление по мутантам (ts-review.md, «Мутанты»)

def test_trim_text_without_marks_and_tiny_limit_cuts_by_char_with_ellipsis():
    assert trim_text("абвгд", 3) == "аб…"


def test_trim_text_boundary_at_odd_half_limit_is_taken():
    text = "а" * 21 + ". " + "б" * 40
    assert trim_text(text, 45) == "а" * 21 + "."


def test_trim_text_boundary_between_third_and_half_goes_by_space_with_ellipsis():
    text = "а" * 11 + ". " + "б" * 40
    assert trim_text(text, 30) == "а" * 11 + ".…"


def test_trim_text_boundary_right_after_first_char_is_taken_for_limit_two():
    assert trim_text(". абвгд", 2) == "."


def test_trim_text_space_at_index_zero_does_not_leave_only_ellipsis():
    assert trim_text(" " + "я" * 100, 50) == " " + "я" * 48 + "…"


def test_trim_text_space_at_index_one_is_a_cut_point():
    assert trim_text("а " + "я" * 100, 50) == "а…"


def test_trim_text_double_space_before_cut_leaves_no_trailing_space():
    assert trim_text("аааа  " + "б" * 100, 50) == "аааа…"


def test_fit_text_trim_after_one_first_overflow_says_attempt_one_of_one(registry, cfg):
    ctx = scene_ctx(registry, cfg, after=1)
    message = fit_text(ctx, "scene", "я" * 900, 600, "Выжимка").message
    assert "Попытка 1 из 1" in message


def test_scene_summary_overflow_counts_under_scene_key_with_plain_label(registry, cfg):
    ctx = scene_ctx(registry, cfg)
    result = apply(ctx, req("scene_summary", title="", summary="я" * 601))
    assert ctx.summary_overflows == {"scene": 1}
    assert result.message.startswith("Выжимка 601 симв., предел 600")
