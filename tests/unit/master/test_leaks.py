# ЖП3 П1 (BACKLOG 104): ai_dm.master.leaks.cut_leaks -- служебный текст в рассказе.
# Формы (а)-(д) из решения 9: JSON offer_choices, строка offer_choices с блоком, «Подсказка по
# результатам», хвостовой список при принятом offer_choices, HTML-теги.
import pytest

from ai_dm.master.leaks import LEAK_LINE, cut_leaks

SCENE = "Лира кивает и отводит взгляд."


# (а) JSON

def test_json_offer_choices_is_cut_and_choices_returned():
    text = SCENE + '\n\n{ "offer_choices": [ "А", "Б" ] }'
    assert cut_leaks(text) == (SCENE, ["А", "Б"])


def test_json_with_type_and_three_choices():
    text = SCENE + '\n\n{ "type": "offer_choices", "choices": [ "А", "Б", "В" ] }'
    assert cut_leaks(text) == (SCENE, ["А", "Б", "В"])


@pytest.mark.parametrize("items", ['"А"', '"А", "Б", "В", "Г"'])
def test_json_with_wrong_number_of_choices_is_cut_without_choices(items):
    text = SCENE + '\n\n{ "offer_choices": [ ' + items + " ] }"
    assert cut_leaks(text) == (SCENE, None)


def test_json_choices_not_strings_are_not_returned():
    text = SCENE + '\n\n{ "offer_choices": [ 1, 2 ] }'
    assert cut_leaks(text) == (SCENE, None)


def test_truncated_json_is_cut_to_the_end():
    text = SCENE + '\n\n{ "offer_choices": [ "А",'
    assert cut_leaks(text) == (SCENE, None)


def test_json_in_the_middle_keeps_text_around():
    text = 'До.\n\n{ "offer_choices": [ "А", "Б" ] }\n\nПосле.'
    assert cut_leaks(text) == ("До.\n\nПосле.", ["А", "Б"])


def test_two_json_blocks_first_choices_win():
    text = (
        SCENE + '\n\n{ "offer_choices": [ "А", "Б" ] }\n\n{ "offer_choices": [ "В", "Г" ] }'
    )
    assert cut_leaks(text) == (SCENE, ["А", "Б"])


def test_second_json_is_cut_even_if_first_had_bad_choices():
    text = (
        SCENE + '\n\n{ "offer_choices": [ "А" ] }\n\n{ "offer_choices": [ "В", "Г" ] }'
    )
    assert cut_leaks(text) == (SCENE, ["В", "Г"])


# (б) строка offer_choices

def test_name_line_with_array_is_cut():
    text = SCENE + '\n\n`offer_choices`\n- ["А", "Б"]'
    assert cut_leaks(text) == (SCENE, ["А", "Б"])


def test_name_line_bold_with_colon_and_marked_list_is_cut_without_choices():
    text = SCENE + "\n\n**offer_choices:**\n- А\n- Б"
    assert cut_leaks(text) == (SCENE, None)


def test_name_line_cut_keeps_text_after_block():
    text = "До.\n\noffer_choices\n- А\n- Б\n\nПосле."
    assert cut_leaks(text) == ("До.\n\nПосле.", None)


def test_name_line_with_bad_array_is_cut_without_choices():
    text = SCENE + "\n\noffer_choices\n- [не json"
    assert cut_leaks(text) == (SCENE, None)


def test_name_line_without_block_keeps_next_prose_line():
    text = "До.\n\noffer_choices\nПосле."
    assert cut_leaks(text) == ("До.\n\nПосле.", None)


def test_name_line_with_one_marked_line_keeps_next_prose_line():
    text = "До.\n\noffer_choices\n- А\nПосле."
    assert cut_leaks(text) == ("До.\n\nПосле.", None)


def test_name_line_with_three_marked_lines_keeps_next_prose_line():
    text = "До.\n\noffer_choices\n- А\n- Б\n- В\nПосле."
    assert cut_leaks(text) == ("До.\n\nПосле.", None)


def test_word_offer_choices_inside_a_sentence_is_kept():
    text = "Он шепчет: «offer_choices», и никто не понимает."
    assert cut_leaks(text) == (text, None)


# (в) подсказка

HINT = (
    "**Подсказка по результатам:**\n- Бросок успешен\n\nОпиши ответ Лиры без цифр."
)


def test_hint_up_to_separator_is_cut():
    text = HINT + "\n\n---\n\nЛира осторожно берёт кошель."
    assert cut_leaks(text) == ("Лира осторожно берёт кошель.", None)


def test_hint_without_separator_cuts_only_its_paragraph():
    text = "**Подсказка по результатам:**\n- Бросок успешен\n\nЛира осторожно берёт кошель."
    assert cut_leaks(text) == ("Лира осторожно берёт кошель.", None)


def test_hint_after_scene_keeps_scene():
    text = SCENE + "\n\n" + HINT + "\n\n---\n\nПродолжение."
    assert cut_leaks(text) == (SCENE + "\n\nПродолжение.", None)


def test_hint_word_not_at_paragraph_start_is_kept():
    text = "Он сказал: Подсказка по результатам боя не нужна."
    assert cut_leaks(text) == (text, None)


def test_hint_with_heading_marks_is_cut():
    text = "# Подсказка по результатам\n\nЛира берёт кошель."
    assert cut_leaks(text) == ("Лира берёт кошель.", None)


def test_hint_word_after_foreign_letter_is_kept():
    text = "XПодсказка по результатам боя.\n\nКонец."
    assert cut_leaks(text) == (text, None)


def test_separator_before_hint_is_kept_and_hint_without_separator_is_cut():
    text = "А.\n\n---\n\n**Подсказка по результатам:**\n\nПроза."
    assert cut_leaks(text) == ("А.\n\n---\n\nПроза.", None)


# (г) хвостовой список

TAIL = "Лира ждёт.\n\n**Что ты решишь?**\n\n1. А\n2. Б"


def test_tail_list_cut_when_choices_taken():
    assert cut_leaks(TAIL, choices_taken=True) == ("Лира ждёт.\n\n**Что ты решишь?**", None)


def test_tail_list_kept_by_default():
    assert cut_leaks(TAIL) == (TAIL, None)


def test_tail_list_with_trailing_newline_is_cut():
    assert cut_leaks(TAIL + "\n", choices_taken=True) == ("Лира ждёт.\n\n**Что ты решишь?**", None)


def test_tail_list_of_three_is_cut():
    text = "Лира ждёт.\n\n1. А\n2. Б\n3. В"
    assert cut_leaks(text, choices_taken=True) == ("Лира ждёт.", None)


def test_whole_text_as_list_is_cut_to_empty():
    assert cut_leaks("- А\n- Б", choices_taken=True) == ("", None)


def test_tail_list_kept_when_choices_not_taken():
    assert cut_leaks(TAIL, choices_taken=False) == (TAIL, None)


def test_tail_single_marked_line_is_kept_even_when_taken():
    text = "Лира ждёт.\n\n- А"
    assert cut_leaks(text, choices_taken=True) == (text, None)


def test_tail_list_in_the_middle_is_kept_when_taken():
    text = "Список:\n\n- А\n- Б\n\nИ дальше проза."
    assert cut_leaks(text, choices_taken=True) == (text, None)


def test_tail_block_with_plain_line_is_kept_when_taken():
    text = "Лира ждёт.\n\n- А\nпроза"
    assert cut_leaks(text, choices_taken=True) == (text, None)


# (д) HTML

def test_html_tags_are_stripped_text_kept():
    text = "<p><strong>Осталось флаконов: 1.</strong></p>"
    assert cut_leaks(text) == ("Осталось флаконов: 1.", None)


@pytest.mark.parametrize("tag", ["p", "strong", "em", "b", "i"])
def test_each_html_tag_is_stripped(tag):
    assert cut_leaks(f"a <{tag}>b</{tag}> c") == ("a b c", None)


def test_br_tag_is_stripped():
    assert cut_leaks("a<br>b<br/>c") == ("abc", None)


def test_other_html_tag_is_kept():
    text = "<div>Текст</div>"
    assert cut_leaks(text) == (text, None)


# LEAK_LINE

def test_leak_line_alone_is_cut_without_double_blank_lines():
    text = "Первый.\n\n" + LEAK_LINE + "\n\nВторой."
    assert cut_leaks(text) == ("Первый.\n\nВторой.", None)


def test_leak_line_inside_paragraph_is_cut():
    text = "Первый " + LEAK_LINE + " конец."
    cleaned, choices = cut_leaks(text)
    assert LEAK_LINE not in cleaned
    assert cleaned.startswith("Первый") and cleaned.endswith("конец.")
    assert choices is None


def test_blank_runs_are_collapsed_after_cut():
    text = 'А.\n\n\n\n{ "offer_choices": [ "А", "Б" ] }\n\n\n\nБ.'
    cleaned, _ = cut_leaks(text)
    assert "\n\n\n" not in cleaned


# без утечки

def test_secret_sign_in_braces_is_kept():
    text = "На двери нарисован {тайный знак}."
    assert cut_leaks(text) == (text, None)


def test_clean_text_is_returned_as_is():
    assert cut_leaks(SCENE) == (SCENE, None)


def test_clean_text_whitespace_is_not_stripped():
    text = "  " + SCENE + "\n\n\n\nЕщё.  "
    assert cut_leaks(text) == (text, None)


def test_empty_text():
    assert cut_leaks("") == ("", None)
