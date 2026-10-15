# 19ф Ф4 (docs/19F-PLAN.md п.1 Ф4.4): после /fight экран перерисовывается сразу -- карта боя,
# меню действий и подсказка; SCREEN_COMMANDS = ("/load", "/fight"); /help по-прежнему без экрана.
from ui_kit import text_app, text_step

from ai_dm.ui.session import SCREEN_COMMANDS, PlaySession


def kinds(step):
    return [block.kind for block in step.blocks]


def test_screen_commands_are_load_and_fight():
    assert tuple(SCREEN_COMMANDS) == ("/load", "/fight")


def test_fight_command_shows_combat_map_and_menu(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    step = PlaySession(app).submit("/fight goblin_warrior")
    assert "combat_map" in kinds(step)
    assert "turn_menu" in kinds(step)
    assert kinds(step)[-1] == "status"


def test_fight_command_shows_combat_hint_once(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    step = PlaySession(app).submit("/fight goblin_warrior")
    assert "combat_hint" in kinds(step)


def test_fight_command_does_not_show_narration(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    step = PlaySession(app).submit("/fight goblin_warrior")
    assert "narration" not in kinds(step)


def test_refused_fight_draws_no_combat_screen(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    step = PlaySession(app).submit("/fight dragon_of_doom")
    assert "combat_map" not in kinds(step)
    assert kinds(step)[-1] == "status"


def test_help_still_has_no_screen_after_fight_was_added(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    app.bundle.session.offered_choices = ["Спросить"]
    step = PlaySession(app).submit("/help")
    assert "menu" not in kinds(step)
    assert "combat_map" not in kinds(step)
    assert kinds(step)[-1] == "status"
