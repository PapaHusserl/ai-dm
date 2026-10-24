# ЖП3 П1 (BACKLOG 104): ai_dm.master.leaks.cut_leaks -- служебный текст в рассказе.
# Формы (а)-(д) из решения 9: JSON offer_choices, строка offer_choices с блоком, «Подсказка по
# результатам», хвостовой список при принятом offer_choices, HTML-теги.
import pytest

from ai_dm.master.leaks import LEAK_LINE, cut_choice_head, cut_leaks, looks_like_plan

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


# 141/171 (Фикс dusk П3): cut_choice_head -- заголовок вариантов последней строкой

@pytest.mark.parametrize("head", [
    "Игрок получает варианты действий:",
    "Варианты:",
    "Выбор за тобой:",
    "Варианты действий:  ",
])
def test_choice_head_last_line_is_cut(head):
    assert cut_choice_head(f"{SCENE}\n\n{head}") == (SCENE, True)


def test_choice_head_trailing_blank_lines_are_ignored():
    assert cut_choice_head(f"{SCENE}\n\nВарианты:\n\n") == (SCENE, True)


def test_choice_head_cuts_only_the_last_line_of_multiline_text():
    assert cut_choice_head("Раз.\nДва.\nВарианты:") == ("Раз.\nДва.", True)


def test_choice_head_only_line_gives_empty_text():
    assert cut_choice_head("Варианты:") == ("", True)


def test_choice_head_with_leading_marker_is_cut():
    assert cut_choice_head(f"{SCENE}\n\n**Варианты:") == (SCENE, True)


def test_choice_head_case_is_ignored():
    assert cut_choice_head(f"{SCENE}\n\nВАРИАНТЫ:") == (SCENE, True)


def test_ordinary_last_line_is_kept():
    text = f"{SCENE}\n\nОн ждал ответа."
    assert cut_choice_head(text) == (text, False)


def test_choice_head_not_last_line_is_kept():
    text = f"{SCENE}\n\nВарианты:\n\nЛира молчит."
    assert cut_choice_head(text) == (text, False)


def test_choice_head_with_list_after_it_is_kept():
    text = f"{SCENE}\n\nВарианты:\n- А\n- Б"
    assert cut_choice_head(text) == (text, False)


def test_choice_head_without_colon_is_kept():
    text = f"{SCENE}\n\nВарианты"
    assert cut_choice_head(text) == (text, False)


def test_choice_head_with_text_after_colon_is_kept():
    text = f"{SCENE}\n\nВарианты: бежать или драться"
    assert cut_choice_head(text) == (text, False)


def test_choice_head_with_long_phrase_before_colon_is_kept():
    text = f"{SCENE}\n\nВарианты " + "а" * 41 + ":"
    assert cut_choice_head(text) == (text, False)


def test_choice_head_with_phrase_of_40_chars_before_colon_is_cut():
    text = f"{SCENE}\n\nВарианты" + "а" * 40 + ":"
    assert cut_choice_head(text) == (SCENE, True)


def test_choice_head_in_empty_text():
    assert cut_choice_head("") == ("", False)


# 141 (Фикс dusk П3): looks_like_plan -- план сцены вместо рассказа

PLAN_T492 = (
    "Опиши:\n"
    "1. Герой входит в зал.\n"
    "2. Стражник заступает дорогу.\n"
    "5. Гоблины падают.\n\n"
    "Инструменты gold и advance_time были отклонены.\n\n"
    "Сделай `end_combat`."
)


def test_plan_t492_sample_is_a_plan():
    assert looks_like_plan(PLAN_T492) is True


def test_plan_head_with_two_marked_lines_is_a_plan():
    assert looks_like_plan("Опиши:\n- Зал\n- Стражник") is True


def test_plan_head_with_text_before_it_is_a_plan():
    assert looks_like_plan("Ход.\n\nОпиши встречу:\n1. Зал\n2) Стражник") is True


def test_plan_head_with_blank_lines_between_items_is_a_plan():
    assert looks_like_plan("Опиши:\n\n- Зал\n\n- Стражник") is True


def test_plan_head_with_one_marked_line_is_not_a_plan():
    assert looks_like_plan("Опиши:\n- Зал") is False


def test_plan_head_without_list_is_not_a_plan():
    assert looks_like_plan("Опиши:\nЗал большой.\nСтражник хмур.") is False


def test_plan_list_before_head_is_not_a_plan():
    assert looks_like_plan("- Зал\n- Стражник\n\nОпиши:") is False


def test_plan_head_without_colon_is_not_a_plan():
    assert looks_like_plan("Опиши зал\n- Зал\n- Стражник") is False


def test_plan_story_with_list_at_the_end_is_not_a_plan():
    assert looks_like_plan("Лира кивает.\n\n- Бежать\n- Драться") is False


def test_plan_npc_asks_to_describe_without_list_is_not_a_plan():
    assert looks_like_plan("— Опиши мне, что ты видел, — просит стражник.") is False


def test_plan_describe_inside_replica_with_colon_and_one_item_is_not_a_plan():
    text = "Стражник хмурится.\n\n— Опиши, что ты видел:\n— Я видел волка."
    assert looks_like_plan(text) is False


def test_plan_describe_not_at_line_start_is_not_a_plan():
    assert looks_like_plan("Лира: опиши, что видел:\n- Зал\n- Стражник") is False


@pytest.mark.parametrize("text", [
    "Инструмент gold отклонён.",
    "Эти инструменты недоступны в режиме.",
    "Отклонён вызов, инструмент не подходит.",
    "Недоступен инструмент advance_time.",
    "Сделай `end_combat`.",
])
def test_plan_tool_talk_is_a_plan(text):
    assert looks_like_plan(text) is True


def test_plan_tool_word_alone_is_not_a_plan():
    assert looks_like_plan("Кузнец берёт инструмент и бьёт по железу.") is False


def test_plan_rejection_alone_is_not_a_plan():
    assert looks_like_plan("Стража отклонила просьбу героя.") is False


def test_plan_do_without_backticks_is_not_a_plan():
    assert looks_like_plan("Сделай end_combat.") is False


def test_plan_empty_text_is_not_a_plan():
    assert looks_like_plan("") is False
