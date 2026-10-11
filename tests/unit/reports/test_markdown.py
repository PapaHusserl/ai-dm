# Ожидаемый API: ai_dm.reports.markdown.render(capture, text) -> str (этап 6а, P0): заголовок
# (метки / «ручной»), текст игрока, мир, кампания, номер хода, сид и состояние RNG до хода,
# модель рассказчика, статус хода и причина сбоя. Чистая функция.
from reports_kit import make_capture

from ai_dm.reports.markdown import render


def test_manual_report_title_says_manual(registry):
    assert render(make_capture(registry), "не работает").splitlines()[0] == "# Репорт: ручной"


def test_tag_report_title_has_tags(registry):
    capture = make_capture(registry, tags=["limit-exceeded", "invalid-death"])
    head = render(capture, "").splitlines()[0]
    assert head == "# Репорт: limit-exceeded, invalid-death"


def test_auto_report_title_is_not_manual(registry):
    capture = make_capture(registry, tags=["refusal"])
    assert "ручной" not in render(capture, "").splitlines()[0]


def test_text_has_player_report_text(registry):
    assert "дверь не открылась" in render(make_capture(registry), "дверь не открылась")


def test_auto_report_has_no_player_text_section(registry):
    capture = make_capture(registry, tags=["refusal"])
    assert "Текст игрока" not in render(capture, "")


def test_text_has_player_input_of_turn(registry):
    capture = make_capture(registry, player_input="Бью ногой дверь")
    assert "Бью ногой дверь" in render(capture, "текст")


def test_text_has_tags(registry):
    capture = make_capture(registry, tags=["missing-mechanic", "context_overflow"])
    text = render(capture, "")
    assert "missing-mechanic" in text
    assert "context_overflow" in text


def test_text_has_seed_of_rng_before_turn(registry):
    capture = make_capture(registry)
    capture.before.world.rng.seed = 987654
    assert "987654" in render(capture, "текст")


def test_text_has_rng_state_before_turn(registry):
    capture = make_capture(registry)
    rng = capture.before.world.rng
    rng.state = 1234567890123
    rng.draws = 7788
    text = render(capture, "текст")
    assert "1234567890123" in text
    assert "7788" in text


def test_text_has_narrator_model(registry):
    capture = make_capture(registry, model="gemini-3.8-flash")
    assert "gemini-3.8-flash" in render(capture, "текст")


def test_text_has_turn_seq(registry):
    assert "4242" in render(make_capture(registry, turn_seq=4242), "текст")


def test_text_has_world_id(registry):
    capture = make_capture(registry)
    assert capture.before.world.world_id in render(capture, "текст")


def test_text_has_committed_status(registry):
    assert "принят" in render(make_capture(registry, status="committed"), "текст")


def test_text_has_aborted_status_and_reason(registry):
    capture = make_capture(registry, status="aborted", failure_reason="refusal")
    text = render(capture, "")
    assert "откатан" in text
    assert "refusal" in text


def test_committed_text_has_no_failure_reason(registry):
    assert "Причина сбоя" not in render(make_capture(registry), "текст")


def test_text_has_run_ids(registry):
    capture = make_capture(registry, run_ids=["run-20261007-1", "bnd-x-1"])
    text = render(capture, "")
    assert "run-20261007-1" in text
    assert "bnd-x-1" in text


def test_capture_without_turn_has_no_turn_section_details(registry):
    capture = make_capture(
        registry, status="none", run_ids=[], player_input=None, turn_seq=0,
    )
    text = render(capture, "текст")
    assert "ходов в сессии ещё не было" in text
    assert "Номер хода" not in text
    assert "Фраза игрока" not in text


def test_render_is_pure(registry):
    capture = make_capture(registry, tags=["refusal"])
    assert render(capture, "текст") == render(capture, "текст")


def test_text_has_sections(registry):
    capture = make_capture(registry, tags=["refusal"])
    lines = render(capture, "текст").splitlines()
    assert "## Текст игрока" in lines
    assert "## Ход" in lines
    assert "## Мир" in lines


def test_sections_go_in_order(registry):
    capture = make_capture(registry, tags=["refusal"])
    lines = render(capture, "текст").splitlines()
    assert lines.index("## Текст игрока") < lines.index("## Ход") < lines.index("## Мир")


def test_capture_without_turn_has_turn_section(registry):
    capture = make_capture(registry, status="none", run_ids=[], player_input=None)
    assert "## Ход" in render(capture, "текст").splitlines()


def test_manual_report_with_tags_keeps_title_text_and_tags(registry):
    capture = make_capture(registry, tags=["limit-exceeded", "refusal"])
    lines = render(capture, "текст игрока").splitlines()
    assert lines[0] == "# Репорт: ручной"
    assert "Метки хода: limit-exceeded, refusal" in lines
    assert "текст игрока" in lines


def test_text_has_several_run_ids_in_line(registry):
    capture = make_capture(registry, run_ids=["run-1", "bnd-2"])
    assert "Вызовы хода (run_id): run-1, bnd-2" in render(capture, "").splitlines()


def test_text_has_player_input_line(registry):
    capture = make_capture(registry, player_input="Бью ногой дверь")
    assert "Фраза игрока: Бью ногой дверь" in render(capture, "").splitlines()
