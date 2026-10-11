# Оформление вывода (stage2-live-1, U1-U6): ширина, рамка, абзацы, переносы, варианты, броски,
# строка состояния. Здесь смотрим СЫРОЙ вывод (out.raw); содержимое без оформления проверяют
# остальные тесты ui через PlainOutput.
import re

from ui_kit import (
    DESCEND,
    ROLL_MARKERS,
    TALK,
    plain_lines,
    play,
    scene_app,
    text_app,
    text_step,
)

WIDTH = 80
TOP = "╭" + "─" * (WIDTH - 2) + "╮"
BOTTOM = "╰" + "─" * (WIDTH - 2) + "╯"
BLANK = "│" + " " * (WIDTH - 2) + "│"
FIRST = "Ты спускаешься по скрипучим ступеням. " * 4
SECOND = "— Ещё эля? — хрипло спрашивает трактирщик, вытирая кружку грязной тряпкой. " * 2
NARRATION = FIRST.strip() + "\n\n" + SECOND.strip()
LONG_CHOICE = (
    "Согласиться и сразу спуститься в подвал вместе с трактирщиком, не задавая лишних вопросов"
)
OFFER = {
    "tool_calls": [
        {"id": "c1", "name": "offer_choices",
         "input": {"type": "offer_choices", "choices": [LONG_CHOICE, "Сначала расспросить Гарта"]}},
    ]
}


def narrated(registry, tmp_path, text=NARRATION):
    app = text_app(registry, tmp_path, [text_step(text)])
    return play(app, ["Привет"]).raw


def frame_rows(raw):
    return [line for line in raw if line.startswith("│")]


def frame_words(raw):
    words = []
    for row in frame_rows(raw):
        words += row[1:-1].split()
    return words


# U1: ширина

def test_no_output_line_is_longer_than_width_in_narration(registry, tmp_path):
    assert max(len(line) for line in narrated(registry, tmp_path)) <= WIDTH


def test_no_output_line_is_longer_than_width_in_a_scene_with_rolls_and_combat(registry, tmp_path):
    app, _ = scene_app(registry, tmp_path)
    raw = play(app, [TALK, "1", DESCEND]).raw
    assert max(len(line) for line in raw) <= WIDTH


def test_no_output_line_is_longer_than_width_with_long_offered_choice(registry, tmp_path):
    app = text_app(registry, tmp_path, [OFFER, text_step("Трактирщик косится.")])
    raw = play(app, ["Здравствуйте"]).raw
    assert max(len(line) for line in raw) <= WIDTH


def test_width_is_counted_in_characters_for_cyrillic(registry, tmp_path):
    raw = narrated(registry, tmp_path, "Я " * 200)
    assert max(len(line) for line in raw) <= WIDTH


# U2: рамка

def test_narration_is_framed_with_top_and_bottom_of_exact_width(registry, tmp_path):
    raw = narrated(registry, tmp_path)
    assert TOP in raw
    assert BOTTOM in raw
    assert raw.index(TOP) < raw.index(BOTTOM)


def test_every_frame_row_is_exactly_width_and_closed(registry, tmp_path):
    rows = frame_rows(narrated(registry, tmp_path))
    assert rows
    for row in rows:
        assert len(row) == WIDTH
        assert row.startswith("│ ") or row == BLANK
        assert row.endswith(" │") or row == BLANK


def test_frame_is_opened_and_closed_once_per_narration(registry, tmp_path):
    raw = narrated(registry, tmp_path)
    assert len([line for line in raw if line.startswith("╭")]) == 1
    assert len([line for line in raw if line.startswith("╰")]) == 1


def test_frame_rows_lie_between_top_and_bottom(registry, tmp_path):
    raw = narrated(registry, tmp_path)
    inside = raw[raw.index(TOP) + 1:raw.index(BOTTOM)]
    assert inside
    assert all(line.startswith("│") for line in inside)


def test_paragraphs_are_kept_as_blank_row_inside_frame(registry, tmp_path):
    raw = narrated(registry, tmp_path)
    inside = raw[raw.index(TOP) + 1:raw.index(BOTTOM)]
    assert BLANK in inside
    assert inside[0] != BLANK
    assert inside[-1] != BLANK


def test_paragraph_text_stays_in_its_own_paragraph(registry, tmp_path):
    raw = narrated(registry, tmp_path)
    inside = raw[raw.index(TOP) + 1:raw.index(BOTTOM)]
    split = inside.index(BLANK)
    first = " ".join(row[1:-1].strip() for row in inside[:split])
    second = " ".join(row[1:-1].strip() for row in inside[split + 1:])
    assert first.split() == FIRST.split()
    assert second.split() == SECOND.split()


def test_wrap_does_not_break_words(registry, tmp_path):
    raw = narrated(registry, tmp_path)
    assert frame_words(raw) == (FIRST + SECOND).split()


def test_wrap_goes_by_words_for_a_single_long_paragraph(registry, tmp_path):
    text = " ".join(f"слово{n}" for n in range(60))
    raw = narrated(registry, tmp_path, text)
    assert frame_words(raw) == text.split()
    assert len(frame_rows(raw)) > 1


def test_single_short_line_is_one_row(registry, tmp_path):
    raw = narrated(registry, tmp_path, "Ветер шумит.")
    assert len(frame_rows(raw)) == 1
    assert "Ветер шумит." in frame_rows(raw)[0]


def test_plain_lines_gives_back_narration_paragraphs(registry, tmp_path):
    lines = plain_lines(narrated(registry, tmp_path))
    assert FIRST.strip() in lines
    assert SECOND.strip() in lines


def test_frame_is_only_around_narration(registry, tmp_path):
    app, _ = scene_app(registry, tmp_path)
    raw = play(app, [TALK, "1", DESCEND]).raw
    for line in raw:
        if line.startswith("│"):
            assert len(line) == WIDTH
    for marker in ROLL_MARKERS:
        assert not any(line.startswith("│") and marker in line for line in raw)


# U3: броски и лог боя

def test_roll_lines_have_indent_and_marker(registry, tmp_path):
    app, _ = scene_app(registry, tmp_path)
    raw = play(app, [TALK, "1"]).raw
    rolls = [line for line in raw if re.search(r"d20 \(\d+\).* = \d+ против СЛ 15 → ", line)]
    assert rolls
    for line in rolls:
        assert line.startswith("  ")
        assert any(line[2:].startswith(marker + " ") for marker in ROLL_MARKERS)


def test_roll_marker_is_the_same_on_every_roll_line(registry, tmp_path):
    app, _ = scene_app(registry, tmp_path)
    raw = play(app, [TALK, "1", DESCEND]).raw
    markers = {
        marker for line in raw for marker in ROLL_MARKERS if line.startswith("  " + marker + " ")
    }
    assert len(markers) == 1


def test_combat_log_lines_are_indented(registry, tmp_path):
    app, _ = scene_app(registry, tmp_path)
    raw = play(app, [TALK, "1", DESCEND]).raw
    lines = [line for line in raw if "Бой начался" in line]
    assert lines
    for line in lines:
        assert line.startswith("  ")


# U4: варианты

def test_offered_choices_have_header_and_indented_numbers(registry, tmp_path):
    app = text_app(registry, tmp_path, [OFFER, text_step("Трактирщик косится.")])
    raw = play(app, ["Здравствуйте"]).raw
    assert "  Что делаешь?" in raw
    assert "    2. Сначала расспросить Гарта" in raw
    assert raw.index("  Что делаешь?") < raw.index("    2. Сначала расспросить Гарта")


def test_long_choice_wraps_under_the_text_of_the_item(registry, tmp_path):
    app = text_app(registry, tmp_path, [OFFER, text_step("Трактирщик косится.")])
    raw = play(app, ["Здравствуйте"]).raw
    start = next(i for i, line in enumerate(raw) if line.startswith("    1. "))
    end = next(i for i, line in enumerate(raw) if line.startswith("    2. "))
    assert end - start >= 2
    for line in raw[start + 1:end]:
        assert line.startswith(" " * 7)
        assert not line.startswith(" " * 8)
    words = " ".join(line.strip() for line in raw[start:end]).split()
    assert words == ("1. " + LONG_CHOICE).split()


def test_menu_in_combat_is_indented_and_numbered(registry, tmp_path):
    app, _ = scene_app(registry, tmp_path, hp=200)
    raw = play(app, [TALK, "1", DESCEND]).raw
    items = [line for line in raw if re.match(r"^ {4}\d+\. ", line)]
    assert items
    assert any(line.strip().endswith("Закончить ход") for line in items)


# U5: строка состояния

def test_status_line_is_separator_of_full_width(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    raw = play(app, []).raw
    status = [line for line in raw if "HP 12/12" in line]
    assert status
    for line in status:
        assert line.startswith("── ")
        assert line.endswith("──")
        assert len(line) == WIDTH


def test_status_line_keeps_the_content(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    raw = play(app, []).raw
    status = next(line for line in raw if "HP 12/12" in line)
    assert re.search(r"HP 12/12 · .+ \d\d:\d\d · сессия \$\d+\.\d+", status)


def test_status_line_is_after_each_turn(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step("Раз."), text_step("Два.")])
    raw = play(app, ["Первое", "Второе"]).raw
    assert len([line for line in raw if "HP 12/12" in line]) == 3


# U6: служебные сообщения

def test_service_message_is_indented_without_frame(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    raw = play(app, []).raw
    saved = [line for line in raw if "Сохранено: auto" in line]
    assert saved
    for line in saved:
        assert line.startswith("  ")
        assert not line.startswith("│")


def test_quit_output_fits_width(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    raw = play(app, ["/quit"]).raw
    assert max(len(line) for line in raw) <= WIDTH


LONG_ROLL = (
    "Атака (длинный лук): d20 (14) + 4 Лов + 2 мастерство + 2 Стрельба + 1d4 (3) Благословение "
    "= 25 против КД 13 → попадание"
)


def test_long_labeled_roll_line_is_wrapped_within_width():
    from ai_dm.ui.format import note_lines, roll_lines

    for lines in (roll_lines(LONG_ROLL), note_lines(LONG_ROLL)):
        assert len(lines) > 1
        assert all(len(line) <= WIDTH for line in lines)


def test_wrapped_roll_line_keeps_all_words():
    from ai_dm.ui.format import roll_lines

    words = " ".join(line.strip() for line in roll_lines(LONG_ROLL)).split()
    assert words[1:] == LONG_ROLL.split()
