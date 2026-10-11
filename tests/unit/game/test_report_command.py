# Ожидаемый API: /report через GameApp.handle (этап 6а, P0): «/report <текст>» пишет репорт
# saves/<world>/issues/<имя>/ и отвечает строкой «Записан репорт: <путь>»; «/report» без текста --
# подсказка, файла нет; до первого хода репорт со снимком состояния, без раздела хода; работает
# при любом pending; не зовёт модель и не меняет бандл.
import json

from game_kit import ReactiveAdapter, core_dump, make_app, scripted, text_step


def issues(tmp_path):
    folder = tmp_path / "w1" / "issues"
    if not folder.exists():
        return []
    return sorted(folder.iterdir())


def text_of(reply):
    return "\n".join(reply.lines)


def test_report_with_text_writes_dir(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([text_step("Рассказ.")]))
    app.handle("Иду")
    app.handle("/report дверь не открылась")
    assert len(issues(tmp_path)) == 1


def test_report_reply_has_path(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([text_step("Рассказ.")]))
    app.handle("Иду")
    reply = app.handle("/report дверь не открылась")
    assert f"Записан репорт: {issues(tmp_path)[0]}" in text_of(reply)


def test_report_md_has_player_text_and_manual_mark(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([text_step("Рассказ.")]))
    app.handle("Иду")
    app.handle("/report дверь не открылась")
    report = (issues(tmp_path)[0] / "report.md").read_text(encoding="utf-8")
    assert "дверь не открылась" in report
    assert "ручной" in report
    assert issues(tmp_path)[0].name.endswith("-manual")


def test_report_refers_to_last_turn(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([text_step("Раз."), text_step("Два.")]))
    app.handle("первая фраза")
    app.handle("вторая фраза")
    app.handle("/report баг")
    report = (issues(tmp_path)[0] / "report.md").read_text(encoding="utf-8")
    # с P1 прошлые ходы есть в «Последних ходах»; раздел хода -- про последний
    assert "Фраза игрока: вторая фраза" in report.split("## Ход\n")[1].split("\n## ")[0]
    assert "-t2-" in issues(tmp_path)[0].name


def test_report_meta_has_turn_run_id(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([text_step("Рассказ.")]))
    result = app.handle("Иду").turn
    app.handle("/report баг")
    meta = json.loads((issues(tmp_path)[0] / "meta.json").read_text(encoding="utf-8"))
    assert meta["run_ids"] == [result.run_id]
    assert meta["status"] == "committed"


def test_report_without_text_gives_hint_and_no_file(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([text_step("Рассказ.")]))
    app.handle("Иду")
    reply = app.handle("/report")
    assert "/report <что не так>" in text_of(reply)
    assert issues(tmp_path) == []


def test_report_with_spaces_only_gives_hint_and_no_file(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([text_step("Рассказ.")]))
    app.handle("Иду")
    reply = app.handle("/report    ")
    assert "/report <что не так>" in text_of(reply)
    assert issues(tmp_path) == []


def test_report_before_first_turn_writes_snapshot_without_turn(registry, tmp_path):
    app = make_app(registry, tmp_path, ReactiveAdapter())
    reply = app.handle("/report ничего не работает")
    assert "Записан репорт" in text_of(reply)
    assert len(issues(tmp_path)) == 1
    report = (issues(tmp_path)[0] / "report.md").read_text(encoding="utf-8")
    assert "ничего не работает" in report
    assert "ходов в сессии ещё не было" in report
    assert "Номер хода" not in report


def test_report_before_first_turn_has_empty_run_ids(registry, tmp_path):
    app = make_app(registry, tmp_path, ReactiveAdapter())
    app.handle("/report ничего не работает")
    meta = json.loads((issues(tmp_path)[0] / "meta.json").read_text(encoding="utf-8"))
    assert meta["run_ids"] == []
    assert meta["status"] == "none"
    assert meta["player_input"] is None


def test_report_works_in_error_menu(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([{"stop": "refusal"}]))
    app.handle("Иду")
    assert app.pending == "error_menu"
    reply = app.handle("/report не отвечает")
    assert "Записан репорт" in text_of(reply)
    assert app.pending == "error_menu"
    assert any(p.name.endswith("-manual") for p in issues(tmp_path))


def test_report_of_aborted_turn_has_status_aborted(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([{"stop": "refusal"}]))
    app.handle("Иду")
    app.handle("/report не отвечает")
    manual = [p for p in issues(tmp_path) if p.name.endswith("-manual")][0]
    meta = json.loads((manual / "meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == "aborted"
    assert meta["failure_reason"] == "refusal"


def test_report_works_in_other_pendings(registry, tmp_path):
    app = make_app(registry, tmp_path, ReactiveAdapter())
    for pending in ("level_up", "hero_dead", "model_choice"):
        app.pending = pending
        reply = app.handle("/report баг")
        assert "Записан репорт" in text_of(reply)
        assert app.pending == pending


def test_report_does_not_call_model_or_change_state(registry, tmp_path):
    adapter = ReactiveAdapter()
    app = make_app(registry, tmp_path, adapter)
    before = core_dump(app.bundle)
    reply = app.handle("/report баг")
    assert reply.turn is None
    assert reply.quit is False
    assert adapter.requests == []
    assert core_dump(app.bundle) == before


def test_report_writes_in_mock_mode_without_auto_reports(registry, tmp_path):
    # ручной репорт пишется всегда, даже при auto_reports=False (mock/replay)
    app = make_app(registry, tmp_path, scripted([text_step()]), auto_reports=False)
    app.handle("Иду")
    app.handle("/report баг")
    assert len(issues(tmp_path)) == 1


def test_report_after_load_is_snapshot_without_turn(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([text_step("Рассказ.")]))
    app.handle("Иду")
    app.handle("/save a")
    app.handle("/load a")
    app.handle("/report после загрузки")
    report = (issues(tmp_path)[0] / "report.md").read_text(encoding="utf-8")
    assert "ходов в сессии ещё не было" in report


def test_report_write_error_is_line_not_exception(registry, tmp_path):
    (tmp_path / "w1").mkdir()
    (tmp_path / "w1" / "issues").write_text("не каталог", encoding="utf-8")
    app = make_app(registry, tmp_path, ReactiveAdapter())
    reply = app.handle("/report баг")
    assert "Репорт не записан" in text_of(reply)
