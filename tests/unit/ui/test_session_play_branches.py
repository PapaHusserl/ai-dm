# AD1: ветки PlaySession.play / render_step, которые раньше проверялись вскользь.
from ui_kit import DESCEND, TALK, scene_app, text_app, text_step

from ai_dm.state.scene import TurnRecord

PAID = {"text": "Рассказ.", "usage": {"input": 1500, "output": 60}}
OFFER_STEP = {
    "text": "Трактирщик кивает.",
    "tool_calls": [
        {"id": "c1", "name": "offer_choices",
         "input": {"type": "offer_choices", "choices": ["Спросить", "Уйти"]}},
    ],
}


def make_session(app):
    from ai_dm.ui.session import PlaySession

    return PlaySession(app)


def kinds(step):
    return [b.kind for b in step.blocks]


def mark_offered(app, choices):
    app.bundle.session.offered_choices = list(choices)
    app.bundle.memory.recent_turns.append(
        TurnRecord(turn_seq=0, at_s=0, player_input="x", narration="y", requests=["offer_choices"])
    )


def test_digit_in_combat_is_not_mapped_even_when_offer_is_fresh(registry, tmp_path):
    app, _ = scene_app(registry, tmp_path, hp=200)
    session = make_session(app)
    for line in (TALK, "1", DESCEND):
        session.submit(line)
    assert app.bundle.session.active_combat is not None
    mark_offered(app, ["Свежий вариант"])
    session.submit("1")
    assert app.bundle.memory.recent_turns[-2].player_input != "Свежий вариант"
    assert app.bundle.memory.recent_turns[-1].player_input == "1"


def test_digit_out_of_fresh_offer_range_goes_as_text(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    mark_offered(app, ["Один"])
    make_session(app).submit("2")
    assert app.bundle.memory.recent_turns[-1].player_input == "2"


def test_load_command_shows_loaded_offer_menu(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    app.bundle.session.offered_choices = ["Спросить"]
    app.save_current("auto")
    step = make_session(app).submit("/load auto")
    assert "menu" in kinds(step)


def test_help_command_over_limit_does_not_show_limit_menu(registry, tmp_path):
    app = text_app(registry, tmp_path, [PAID, PAID])
    app.settings.app.cost_limits.enabled = True
    app.settings.app.cost_limits.session_limit_micro = 1
    first = make_session(app)
    first.submit("Иду")
    assert first.limit_menu is True
    second = make_session(app)
    step = second.submit("/help")
    assert second.limit_menu is False
    assert "menu" not in kinds(step)
    assert "лимит" not in "\n".join(b.text for b in step.blocks if b.kind == "note").lower()


def test_pending_menu_digit_out_of_range_gives_note_only(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    app.pending = "hero_dead"
    step = make_session(app).submit("9")
    assert kinds(step) == ["note"]
    assert step.blocks[0].text == "Нет такого варианта."


def test_warning_is_remembered_after_first_warn(registry, tmp_path):
    app = text_app(registry, tmp_path, [PAID])
    app.settings.app.cost_limits.enabled = True
    app.settings.app.cost_limits.session_limit_micro = 8500
    session = make_session(app)
    step = session.submit("Иду")
    assert "80%" in "\n".join(b.text for b in step.blocks if b.kind == "note")
    assert session.warned is True
    assert session.limit_menu is False


# Б1-фикс п.2: после /load показывается последний рассказ загруженного мира

def test_load_command_shows_last_narration_of_loaded_world(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step("Трактирщик кивает.")])
    session = make_session(app)
    session.submit("Здравствуйте")
    app.save_current("auto")
    step = session.submit("/load")
    narrations = [b.text for b in step.blocks if b.kind == "narration"]
    assert narrations == ["Трактирщик кивает."]


def test_load_command_order_is_note_narration_menu_status(registry, tmp_path):
    app = text_app(registry, tmp_path, [OFFER_STEP])
    session = make_session(app)
    session.submit("Здравствуйте")
    app.save_current("auto")
    step = session.submit("/load")
    assert kinds(step) == ["note", "narration", "menu", "status"]


def test_load_missing_slot_shows_no_narration(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step("Трактирщик кивает.")])
    session = make_session(app)
    session.submit("Здравствуйте")
    step = session.submit("/load nosuchslot")
    assert "narration" not in kinds(step)


def test_load_without_recent_turns_shows_no_narration(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    app.save_current("auto")
    step = make_session(app).submit("/load")
    assert "narration" not in kinds(step)
    assert kinds(step)[0] == "note"
    assert kinds(step)[-1] == "status"


def test_load_of_dead_hero_shows_narration_and_dead_menu(registry, tmp_path):
    from ai_dm.game.scene import hero_of

    app = text_app(registry, tmp_path, [text_step("Удар в спину.")])
    session = make_session(app)
    session.submit("Иду")
    hero_of(app.bundle).status = "dead"
    app.save_current("auto")
    step = session.submit("/load")
    assert app.pending == "hero_dead"
    assert [b.text for b in step.blocks if b.kind == "narration"] == ["Удар в спину."]
    assert kinds(step).index("narration") < kinds(step).index("menu")
    assert len(step.blocks[kinds(step).index("menu")].items) == 2


def test_other_command_does_not_repeat_narration(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step("Трактирщик кивает.")])
    session = make_session(app)
    session.submit("Здравствуйте")
    assert "narration" not in kinds(session.submit("/help"))


def test_load_prefix_text_in_other_command_is_not_a_load(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step("Трактирщик кивает.")])
    session = make_session(app)
    session.submit("Здравствуйте")
    assert "narration" not in kinds(session.submit("/save auto"))


def test_dead_menu_load_last_save_shows_last_narration(registry, tmp_path):
    # «Загрузить последнее сохранение» из меню смерти -- та же загрузка, что /load
    app = text_app(registry, tmp_path, [text_step("Трактирщик кивает.")])
    session = make_session(app)
    session.submit("Здравствуйте")
    app.save_current("auto")
    app.pending = "hero_dead"
    step = session.submit("1")
    assert app.pending is None
    assert [b.text for b in step.blocks if b.kind == "narration"] == ["Трактирщик кивает."]
    assert kinds(step)[-1] == "status"
