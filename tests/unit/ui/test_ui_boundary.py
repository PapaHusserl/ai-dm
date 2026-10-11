# Вывод границы сцены в ui.simple (П2 этапа 3): строка главы и блок «За кадром».
# Строки: «Глава N: название» (без названия -- «Глава N закончена.»), «За кадром:» и «— текст».
# Пустой блок не печатается.
from game_kit import end_scene_call, make_app, scripted, text_step, tools_step
from protocol_kit import make_bundle
from slots_kit import ScriptedInput
from ui_kit import PlainOutput

from ai_dm.state.session import ChapterState
from ai_dm.state.world import Notice
from ai_dm.ui.simple import run


def end_chapter_call(title):
    return {"id": "ec-1", "name": "end_chapter", "input": {"type": "end_chapter", "title": title}}


def notice(text, visibility="visible", deliver_at_s=0, id="n1"):
    return Notice(
        id=id, at_s=0, deliver_at_s=deliver_at_s, visibility=visibility, text=text
    )


def boundary_app(registry, tmp_path, steps, notices=()):
    bundle = make_bundle(registry)
    bundle.session.current_chapter = ChapterState(
        id="ch_1", number=1, started_at_s=0, scene_count=1
    )
    bundle.world.notices = list(notices)
    return make_app(registry, tmp_path, scripted(steps), bundle=bundle)


def play(app, lines):
    out = PlainOutput()
    run(app, ScriptedInput(lines), out)
    return out


def test_closed_chapter_is_printed_with_number_and_title(registry, tmp_path):
    steps = [tools_step(end_scene_call(), end_chapter_call("Пролог")), text_step("Конец.")]
    out = play(boundary_app(registry, tmp_path, steps), ["Иду"])
    assert "Глава 1: Пролог" in out.text


def test_closed_chapter_without_title_is_still_printed(registry, tmp_path):
    steps = [tools_step(end_scene_call(), end_chapter_call("")), text_step("Конец.")]
    out = play(boundary_app(registry, tmp_path, steps), ["Иду"])
    assert "Глава 1" in out.text


def test_no_chapter_line_when_chapter_not_closed(registry, tmp_path):
    steps = [tools_step(end_scene_call()), text_step("Конец.")]
    out = play(boundary_app(registry, tmp_path, steps), ["Иду"])
    assert "Глава 1" not in out.text


def test_offscreen_block_is_printed_with_delivered_notices(registry, tmp_path):
    steps = [tools_step(end_scene_call()), text_step("Конец.")]
    notices = [notice("Олдрик покинул город.")]
    out = play(boundary_app(registry, tmp_path, steps, notices), ["Иду"])
    assert "За кадром:" in out.text
    assert "Олдрик покинул город." in out.text


def test_empty_offscreen_block_is_not_printed(registry, tmp_path):
    steps = [tools_step(end_scene_call()), text_step("Конец.")]
    out = play(boundary_app(registry, tmp_path, steps), ["Иду"])
    assert "За кадром" not in out.text


def test_hidden_and_future_notices_are_not_printed(registry, tmp_path):
    steps = [tools_step(end_scene_call()), text_step("Конец.")]
    notices = [
        notice("Тайна.", visibility="hidden", id="n1"),
        notice("Слух потом.", deliver_at_s=10**9, id="n2"),
    ]
    out = play(boundary_app(registry, tmp_path, steps, notices), ["Иду"])
    assert "За кадром" not in out.text
    assert "Тайна." not in out.text
    assert "Слух потом." not in out.text


def test_offscreen_block_is_printed_once(registry, tmp_path):
    steps = [
        tools_step(end_scene_call("e1")), text_step("Раз."),
        tools_step(end_scene_call("e2")), text_step("Два."),
    ]
    app = boundary_app(registry, tmp_path, steps, [notice("Весть.")])
    out = play(app, ["a", "b"])
    assert out.text.count("Весть.") == 1


def test_quiet_turn_prints_neither_chapter_nor_offscreen(registry, tmp_path):
    out = play(boundary_app(registry, tmp_path, [text_step("Тихо.")]), ["Иду"])
    assert "За кадром" not in out.text
    assert "Глава" not in out.text


def test_boundary_failure_is_shown_with_error_menu(registry, tmp_path, monkeypatch):
    import ai_dm.game.boundary as boundary
    from ai_dm.master.session import TurnFailed

    def broken(work, cfg, registry):
        raise TurnFailed("fatal", "нет связи")

    monkeypatch.setattr(boundary, "tick_days", broken)
    steps = [tools_step(end_scene_call()), text_step("Конец.")]
    app = boundary_app(registry, tmp_path, steps, [notice("Весть.")])
    out = play(app, ["Иду"])
    assert app.pending == "error_menu"
    assert "За кадром" not in out.text
