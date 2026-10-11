# AD1, W2: PlaySession.submit не роняет worker, что бы ни упало.
#   до хода (loot_snapshot, hero_of) -> заметка «Ошибка хода», ход не применён, сейв не тронут;
#   после хода (reply_blocks, turn_events, screen_blocks) -> заметка «Ход сделан, но
#   экран не обновился», ход в состоянии, затем строка состояния (упала и она -- одна заметка).
# Текст исключения проходит redact(secrets); в replay -- quit=True и exit_code=1.
import pytest
from ui_kit import text_app, text_step

from ai_dm.persistence.layout import slot_dir
from ai_dm.persistence.store import load_slot

BEFORE = "Ошибка хода"
AFTER = "Ход сделан, но экран не обновился"
SECRET = "sk-ant-secret-123"


def make_session(app, **kw):
    from ai_dm.ui.session import PlaySession

    return PlaySession(app, **kw)


def notes(step):
    return "\n".join(b.text for b in step.blocks if b.kind == "note")


def kinds(step):
    return [b.kind for b in step.blocks]


def breaker(monkeypatch, name, message="сломалось", times=1):
    # ai_dm.ui.session.<name> падает первые times раз, потом работает как раньше
    import ai_dm.ui.session as module

    real = getattr(module, name)
    left = [times]

    def broken(*args, **kwargs):
        if left[0] > 0:
            left[0] -= 1
            raise RuntimeError(message)
        return real(*args, **kwargs)

    monkeypatch.setattr(module, name, broken)


def auto_files(app, tmp_path):
    folder = slot_dir(tmp_path, "vale-ui", "auto")
    return {p.name: p.read_bytes() for p in folder.rglob("*") if p.is_file()}


# до хода

@pytest.mark.parametrize("name", ["loot_snapshot", "hero_of"])
def test_failure_before_turn_gives_error_note(registry, tmp_path, monkeypatch, name):
    app = text_app(registry, tmp_path, [text_step()])
    breaker(monkeypatch, name)
    step = make_session(app).submit("Иду")
    assert kinds(step) == ["note"]
    assert notes(step) == f"{BEFORE}: сломалось"
    assert step.quit is False
    assert step.exit_code == 0


@pytest.mark.parametrize("name", ["loot_snapshot", "hero_of"])
def test_failure_before_turn_does_not_apply_turn(registry, tmp_path, monkeypatch, name):
    app = text_app(registry, tmp_path, [text_step()])
    breaker(monkeypatch, name)
    make_session(app).submit("Иду")
    assert app.bundle.session.turn_seq == 0
    assert app.bundle.memory.recent_turns == []


def test_failure_before_turn_does_not_touch_save(registry, tmp_path, monkeypatch):
    app = text_app(registry, tmp_path, [text_step()])
    app.save_current("auto")
    saved = auto_files(app, tmp_path)
    breaker(monkeypatch, "loot_snapshot")
    make_session(app).submit("Иду")
    assert auto_files(app, tmp_path) == saved


def test_failure_before_turn_makes_no_autosave(registry, tmp_path, monkeypatch):
    app = text_app(registry, tmp_path, [text_step()])
    breaker(monkeypatch, "loot_snapshot")
    make_session(app).submit("Иду")
    assert not slot_dir(tmp_path, "vale-ui", "auto").exists()


def test_session_lives_after_failure_before_turn(registry, tmp_path, monkeypatch):
    app = text_app(registry, tmp_path, [text_step("Трактирщик кивает.")])
    breaker(monkeypatch, "loot_snapshot")
    session = make_session(app)
    session.submit("Иду")
    step = session.submit("Здравствуйте")
    assert kinds(step) == ["narration", "status"]
    assert app.bundle.session.turn_seq == 1


# после хода

@pytest.mark.parametrize("name", ["reply_blocks", "turn_events", "screen_blocks"])
def test_failure_after_turn_gives_saved_note_and_status(registry, tmp_path, monkeypatch, name):
    app = text_app(registry, tmp_path, [text_step()])
    app.bundle.session.offered_choices = ["Спросить"]
    breaker(monkeypatch, name)
    step = make_session(app).submit("Иду")
    assert kinds(step) == ["note", "status"]
    assert notes(step) == f"{AFTER}: сломалось"
    assert step.quit is False
    assert step.exit_code == 0


def test_failure_after_turn_keeps_turn_for_autosave_on_exit(registry, tmp_path, monkeypatch):
    # автосейв делает finish() (не handle): ход к этому моменту уже в состоянии
    app = text_app(registry, tmp_path, [text_step()])
    breaker(monkeypatch, "reply_blocks")
    session = make_session(app)
    session.submit("Иду")
    assert app.bundle.session.turn_seq == 1
    session.finish()
    assert load_slot(tmp_path, "vale-ui", "auto").session.turn_seq == 1


def test_failure_after_turn_with_broken_status_gives_only_note(registry, tmp_path, monkeypatch):
    app = text_app(registry, tmp_path, [text_step()])
    breaker(monkeypatch, "reply_blocks")
    breaker(monkeypatch, "status_block", "статус тоже")
    step = make_session(app).submit("Иду")
    assert kinds(step) == ["note"]
    assert notes(step).startswith(AFTER)


def test_session_lives_after_failure_after_turn(registry, tmp_path, monkeypatch):
    app = text_app(registry, tmp_path, [text_step(), text_step("Второй рассказ.")])
    breaker(monkeypatch, "reply_blocks")
    session = make_session(app)
    session.submit("Иду")
    step = session.submit("Дальше")
    assert kinds(step) == ["narration", "status"]
    assert app.bundle.session.turn_seq == 2


# секреты и replay

def test_secret_is_redacted_in_failure_before_turn(registry, tmp_path, monkeypatch):
    app = text_app(registry, tmp_path, [text_step()])
    breaker(monkeypatch, "loot_snapshot", f"ключ {SECRET} отклонён")
    step = make_session(app, secrets=(SECRET,)).submit("Иду")
    assert SECRET not in notes(step)
    assert "***" in notes(step)
    assert notes(step).startswith(BEFORE)


def test_secret_is_redacted_in_failure_after_turn(registry, tmp_path, monkeypatch):
    app = text_app(registry, tmp_path, [text_step()])
    breaker(monkeypatch, "reply_blocks", f"ключ {SECRET} отклонён")
    step = make_session(app, secrets=(SECRET,)).submit("Иду")
    assert SECRET not in notes(step)
    assert "***" in notes(step)
    assert notes(step).startswith(AFTER)


def test_secret_is_redacted_in_failure_of_turn_itself(registry, tmp_path, monkeypatch):
    app = text_app(registry, tmp_path, [text_step()])

    def broken(line):
        raise RuntimeError(f"ключ {SECRET}")

    monkeypatch.setattr(app, "handle", broken)
    step = make_session(app, secrets=(SECRET,)).submit("Иду")
    assert SECRET not in notes(step)
    assert notes(step).startswith(BEFORE)


@pytest.mark.parametrize("name", ["loot_snapshot", "reply_blocks"])
def test_replay_failure_quits_with_code_1(registry, tmp_path, monkeypatch, name):
    app = text_app(registry, tmp_path, [text_step()])
    breaker(monkeypatch, name)
    step = make_session(app, replay=True).submit("Иду")
    assert step.quit is True
    assert step.exit_code == 1


def test_replay_failure_of_turn_itself_quits_with_code_1(registry, tmp_path, monkeypatch):
    app = text_app(registry, tmp_path, [text_step()])

    def broken(line):
        raise RuntimeError("упало")

    monkeypatch.setattr(app, "handle", broken)
    step = make_session(app, replay=True).submit("Иду")
    assert (step.quit, step.exit_code) == (True, 1)
    assert notes(step).startswith(BEFORE)


def test_failure_of_turn_itself_in_normal_mode_keeps_playing(registry, tmp_path, monkeypatch):
    app = text_app(registry, tmp_path, [text_step()])

    def broken(line):
        raise RuntimeError("упало")

    monkeypatch.setattr(app, "handle", broken)
    step = make_session(app).submit("Иду")
    assert (step.quit, step.exit_code) == (False, 0)
    assert kinds(step) == ["note"]
