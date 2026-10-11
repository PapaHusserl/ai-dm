# Этап 5, P6, В-2 (решение проектировщика): простой режим показывает ТОЛЬКО заставку-титул
# при старте; рисунков локаций, монстров и событий в нём нет.
# Остальной вывод простого режима не меняется.
from ui_kit import play, text_app, text_step

from ai_dm.art import art_for_event, load_art


def rows_of(art):
    return [line.rstrip() for line in art.splitlines() if line.strip()]


def other_rows():
    # строки всех рисунков, кроме заставки (короткие и общие с заставкой отбрасываем)
    title = set(rows_of(art_for_event("title")))
    pictures = load_art().pictures
    rows = set()
    for text in pictures.values():
        if text != art_for_event("title"):
            rows |= {row for row in rows_of(text) if len(row.strip()) >= 6 and row not in title}
    return rows


def test_simple_mode_prints_title_at_start(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    out = play(app, [])
    assert [row for row in rows_of(art_for_event("title")) if row not in out.lines] == []


def test_title_is_printed_before_status_line(registry, tmp_path):
    from ai_dm.ui.simple import status_line

    app = text_app(registry, tmp_path, [text_step()])
    out = play(app, [])
    first = rows_of(art_for_event("title"))[0]
    assert out.lines.index(first) < out.lines.index(status_line(app))


def test_title_is_printed_once_over_several_turns(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step("Раз."), text_step("Два.")])
    out = play(app, ["Иду", "Смотрю"])
    assert out.text.count(art_for_event("title")) == 1


def test_simple_mode_prints_no_other_drawing_after_turn(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step("Раз.")])
    out = play(app, ["Иду"])
    assert [row for row in other_rows() if row in out.lines] == []


def test_simple_mode_prints_no_event_drawing_on_quit(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step("Раз.")])
    out = play(app, ["Иду", "/quit"])
    assert [row for row in other_rows() if row in out.lines] == []
