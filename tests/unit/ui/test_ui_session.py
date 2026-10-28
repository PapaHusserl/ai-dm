# Ожидаемый API (P0 этапа 5, STAGE5-PLAN A3): ai_dm.ui.session.PlaySession -- контроллер ввода.
# Допущения об интерфейсе (в плане нет точных имён, выбраны здесь -- ТРЕБОВАНИЕ к реализации):
#   PlaySession(app, replay=False, secrets=(), opening=None)
#   .start() / .submit(line) / .finish() -> Step
#   Step: .blocks , .quit (bool), .exit_code (int, 0 по умолчанию)
#   «Сохранено: auto.» / «Нет такого варианта.» / «Ошибка хода: …» -- блоки kind "note"
#   Меню лимита -- блок kind "menu" с двумя пунктами, до него note со словом «лимит».
#   Выход по «2» в меню лимита и /quit -- step.quit True.
from slots_kit import list_slots
from ui_kit import DESCEND, TALK, requests_with_tools, scene_app, text_app, text_step

from ai_dm.game.app import Reply
from ai_dm.game.scene import hero_of
from ai_dm.state.scene import TurnRecord

COST = {"input": 1500, "output": 60}
PAID = {"text": "Рассказ.", "usage": COST}
OFFER = {
    "tool_calls": [
        {"id": "c1", "name": "offer_choices",
         "input": {"type": "offer_choices", "choices": ["Спросить про подвал", "Заказать эль"]}},
    ]
}
FATAL = [{"error": "fatal", "message": "ключ отозван"}]
CLASSIFY = {"player_action", "unsupported_action"}


def kinds(step):
    return [block.kind for block in step.blocks]


def texts(step, kind=None):
    result = []
    for block in step.blocks:
        if kind is None or block.kind == kind:
            result += [block.text] if block.text else list(block.items)
    return result


def notes_text(step):
    return "\n".join(texts(step, "note")).lower()


def limited_app(registry, root, steps, limit_micro):
    app = text_app(registry, root, steps)
    app.settings.app.cost_limits.enabled = True
    app.settings.app.cost_limits.session_limit_micro = limit_micro
    return app


def make_session(app, **kw):
    from ai_dm.ui.session import PlaySession

    return PlaySession(app, **kw)


# старт

def test_start_gives_startup_notes_first_then_status(registry, tmp_path):
    from ai_dm.ui.screen import status_line

    app = text_app(registry, tmp_path, [text_step()])
    app.startup_lines.append("Строка старта")
    step = make_session(app).start()
    assert kinds(step)[:2] == ["note", "status"]
    assert texts(step, "note")[0] == "Строка старта"
    assert texts(step, "status") == [status_line(app)]
    assert step.quit is False
    assert step.exit_code == 0


def test_start_shows_pending_menu(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    app.pending = "hero_dead"
    step = make_session(app).start()
    assert kinds(step)[-1] == "menu"
    assert len(step.blocks[-1].items) == 2


def test_take_opening_gives_opening_once_then_none(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    session = make_session(app, opening="Начало.")
    assert session.take_opening() == "Начало."
    assert session.take_opening() is None


def test_take_opening_without_opening_is_none(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    assert make_session(app).take_opening() is None


def test_start_with_opening_does_not_show_last_narration(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step("Прошлый рассказ.")])
    make_session(app).submit("Иду")
    step = make_session(app, opening="Начало.").start()
    assert "narration" not in kinds(step)


def test_start_shows_last_narration_when_world_is_continued(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step("Прошлый рассказ.")])
    make_session(app).submit("Иду")
    step = make_session(app).start()
    assert "narration" in kinds(step)
    assert "Прошлый рассказ." in texts(step, "narration")[0]
    assert kinds(step).index("narration") < kinds(step).index("status")


def test_start_in_replay_does_not_show_last_narration(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step("Прошлый рассказ.")])
    make_session(app).submit("Иду")
    step = make_session(app, replay=True).start()
    assert "narration" not in kinds(step)


def test_start_does_not_show_last_narration_for_a_new_world(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    assert "narration" not in kinds(make_session(app).start())


# ход

def test_submit_text_gives_narration_then_status(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step("Трактирщик кивает.")])
    step = make_session(app).submit("Здравствуйте")
    assert kinds(step) == ["narration", "status"]
    assert "Трактирщик кивает." in texts(step, "narration")[0]
    assert app.bundle.session.turn_seq == 1
    assert step.quit is False


def test_submit_strips_the_line(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    make_session(app).submit("  /help  ")
    assert app.bundle.session.turn_seq == 0


def test_command_gives_lines_and_status_but_no_screen(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    app.bundle.session.offered_choices = ["Спросить"]
    step = make_session(app).submit("/help")
    assert "menu" not in kinds(step)
    assert kinds(step)[-1] == "status"


def test_load_command_shows_screen(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    app.save_current("auto")
    app.bundle.session.offered_choices = ["Спросить"]
    step = make_session(app).submit("/load auto")
    assert "menu" in kinds(step) or "status" in kinds(step)
    assert kinds(step)[-1] == "status"


def test_quit_command_sets_quit_and_gives_no_status(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    step = make_session(app).submit("/quit")
    assert step.quit is True
    assert "status" not in kinds(step)
    assert step.exit_code == 0


def test_turn_shows_offered_choices_menu(registry, tmp_path):
    app = text_app(registry, tmp_path, [OFFER, text_step("Трактирщик косится.")])
    step = make_session(app).submit("Иду")
    menus = [block for block in step.blocks if block.kind == "menu"]
    assert len(menus) == 1
    assert list(menus[0].items) == ["Спросить про подвал", "Заказать эль"]
    assert kinds(step)[-1] == "status"


# цифры

def test_digit_picks_offered_choice_as_player_text(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    app.bundle.session.offered_choices = ["Спросить про подвал", "Заказать эль"]
    app.bundle.memory.recent_turns.append(
        TurnRecord(turn_seq=0, at_s=0, player_input="x", narration="y", requests=["offer_choices"])
    )
    make_session(app).submit("2")
    assert app.bundle.memory.recent_turns[-1].player_input == "Заказать эль"


def test_digit_out_of_offered_range_goes_as_text(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    app.bundle.session.offered_choices = ["Спросить про подвал"]
    make_session(app).submit("5")
    assert app.bundle.memory.recent_turns[-1].player_input == "5"


def test_digit_zero_goes_as_text(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    app.bundle.session.offered_choices = ["Спросить про подвал"]
    make_session(app).submit("0")
    assert app.bundle.memory.recent_turns[-1].player_input == "0"


def test_digit_in_pending_menu_chooses_item(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    app.save_current("auto")
    app.pending = "hero_dead"
    step = make_session(app).submit("1")
    assert "Загружено: auto." in "\n".join(texts(step, "note"))
    assert app.pending is None


def test_digit_out_of_pending_menu_range_is_rejected(registry, tmp_path):
    app = text_app(registry, tmp_path, FATAL)
    session = make_session(app)
    session.submit("Иду")
    step = session.submit("9")
    assert "нет такого варианта" in notes_text(step)
    assert app.pending == "error_menu"
    assert len(step.blocks) == 1


def test_digit_zero_in_pending_menu_is_rejected(registry, tmp_path):
    app = text_app(registry, tmp_path, FATAL)
    session = make_session(app)
    session.submit("Иду")
    assert "нет такого варианта" in notes_text(session.submit("0"))


def test_digit_in_combat_is_not_mapped_to_offered_choices(registry, tmp_path):
    app, adapter = scene_app(registry, tmp_path, hp=200)
    session = make_session(app)
    for line in (TALK, "1", DESCEND):
        session.submit(line)
    assert app.bundle.session.active_combat is not None
    app.bundle.session.offered_choices = ["Старый вариант"]
    session.submit("1")
    assert app.bundle.session.turn_seq == 4
    assert requests_with_tools(adapter, CLASSIFY) == []
    assert app.bundle.memory.recent_turns[-1].player_input == "1"


def test_menu_choice_in_error_menu_save_and_quit_quits(registry, tmp_path):
    app = text_app(registry, tmp_path, FATAL)
    session = make_session(app)
    session.submit("Иду")
    step = session.submit("3")
    assert step.quit is True
    assert "auto" in list_slots(tmp_path, "vale-ui")


# исключения хода

def raising(app, name, message):
    def boom(*args):
        raise RuntimeError(message)

    setattr(app, name, boom)


def test_turn_exception_is_a_redacted_note_and_session_lives(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    raising(app, "handle", "упало sk-secret-123")
    session = make_session(app, secrets=("sk-secret-123",))
    step = session.submit("Иду")
    text = "\n".join(texts(step, "note"))
    assert "Ошибка хода:" in text
    assert "sk-secret-123" not in text
    assert "***" in text
    assert step.exit_code == 0
    assert step.quit is False
    assert "status" not in kinds(step)


def test_turn_exception_in_replay_gives_exit_code_1(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    raising(app, "handle", "упало")
    step = make_session(app, replay=True).submit("Иду")
    assert step.exit_code == 1
    assert step.quit is True
    assert "Ошибка хода:" in "\n".join(texts(step, "note"))


def test_choose_exception_is_handled_too(registry, tmp_path):
    app = text_app(registry, tmp_path, FATAL)
    session = make_session(app, secrets=("sk-zzz",))
    session.submit("Иду")
    raising(app, "choose", "упало sk-zzz")
    step = session.submit("1")
    assert "Ошибка хода:" in "\n".join(texts(step, "note"))
    assert "sk-zzz" not in "\n".join(texts(step, "note"))


# мягкий лимит

def test_limit_off_gives_no_limit_notes(registry, tmp_path):
    app = text_app(registry, tmp_path, [PAID])
    step = make_session(app).submit("Иду")
    assert "лимит" not in notes_text(step)
    assert "menu" not in kinds(step)


def test_limit_warn_is_given_once(registry, tmp_path):
    from ai_dm.llm.cost import check_limit

    probe = text_app(registry, tmp_path / "probe", [PAID])
    make_session(probe).submit("Иду")
    nano = probe.ledger.report(probe.now().astimezone().date()).session.total_nano
    app = limited_app(registry, tmp_path / "main", [PAID, PAID], nano // 900)
    cfg = app.settings.app.cost_limits
    session = make_session(app)
    first = session.submit("Иду")
    assert check_limit(cfg, nano, cfg.session_limit_micro) == "warn"
    assert "лимит" in notes_text(first)
    assert f"{cfg.warn_percent}%" in notes_text(first)
    assert "menu" not in kinds(first)
    second = session.submit("Ещё")
    assert f"{cfg.warn_percent}%" not in notes_text(second)


def test_limit_pause_gives_note_and_two_item_menu(registry, tmp_path):
    app = limited_app(registry, tmp_path, [PAID, PAID], 1)
    step = make_session(app).submit("Иду")
    assert "лимит" in notes_text(step)
    menu = [block for block in step.blocks if block.kind == "menu"][-1]
    assert len(menu.items) == 2
    assert "продолж" in menu.items[0].lower()
    assert "сохран" in menu.items[1].lower()
    assert kinds(step).index("status") < kinds(step).index("menu")


def test_limit_pause_is_asked_once(registry, tmp_path):
    app = limited_app(registry, tmp_path, [PAID, PAID, PAID], 1)
    session = make_session(app)
    session.submit("Иду")
    session.submit("1")
    step = session.submit("Ещё")
    assert "лимит" not in notes_text(step)
    assert app.bundle.session.turn_seq == 2


def test_limit_menu_blocks_the_turn_until_answered(registry, tmp_path):
    app = limited_app(registry, tmp_path, [PAID, PAID], 1)
    session = make_session(app)
    session.submit("Иду")
    step = session.submit("Ещё")
    assert "нет такого варианта" in notes_text(step)
    assert app.bundle.session.turn_seq == 1
    assert len(step.blocks) == 1


def test_limit_menu_digit_outside_range_is_rejected(registry, tmp_path):
    app = limited_app(registry, tmp_path, [PAID, PAID], 1)
    session = make_session(app)
    session.submit("Иду")
    assert "нет такого варианта" in notes_text(session.submit("3"))
    assert "нет такого варианта" in notes_text(session.submit("0"))
    assert app.bundle.session.turn_seq == 1


def test_limit_continue_plays_on(registry, tmp_path):
    app = limited_app(registry, tmp_path, [PAID, PAID], 1)
    session = make_session(app)
    session.submit("Иду")
    step = session.submit("1")
    assert step.quit is False
    session.submit("Ещё")
    assert app.bundle.session.turn_seq == 2


def test_limit_continue_shows_screen_again(registry, tmp_path):
    app = limited_app(registry, tmp_path, [PAID, PAID], 1)
    app.bundle.session.offered_choices = ["Спросить"]
    session = make_session(app)
    session.submit("Иду")
    app.bundle.session.offered_choices = ["Спросить"]
    step = session.submit("1")
    assert kinds(step) == ["menu"]
    assert list(step.blocks[0].items) == ["Спросить"]


def test_limit_save_and_quit_saves_and_quits(registry, tmp_path):
    app = limited_app(registry, tmp_path, [PAID, PAID], 1)
    session = make_session(app)
    session.submit("Иду")
    step = session.submit("2")
    assert step.quit is True
    assert step.exit_code == 0
    assert "сохранено" in notes_text(step)
    assert "auto" in list_slots(tmp_path, "vale-ui")


def test_limit_save_and_quit_is_refused_when_hero_is_dead(registry, tmp_path):
    app = limited_app(registry, tmp_path, [PAID, PAID], 1)
    session = make_session(app)
    session.submit("Иду")
    app.pending = "hero_dead"
    step = session.submit("2")
    assert step.quit is False
    assert "погиб" in notes_text(step)
    assert "сохранять нельзя" in notes_text(step)
    assert list_slots(tmp_path, "vale-ui") == []


def refuse_save(slot):
    raise ValueError("диск недоступен")


def test_limit_save_failure_is_a_note_and_does_not_quit(registry, tmp_path):
    app = limited_app(registry, tmp_path, [PAID, PAID], 1)
    session = make_session(app)
    session.submit("Иду")
    app.save_current = refuse_save
    step = session.submit("2")
    assert step.quit is False
    assert "не удалось сохранить" in notes_text(step)
    assert list_slots(tmp_path, "vale-ui") == []


def test_limit_menu_stays_open_after_refused_exit(registry, tmp_path):
    app = limited_app(registry, tmp_path, [PAID, PAID], 1)
    session = make_session(app)
    session.submit("Иду")
    app.pending = "hero_dead"
    session.submit("2")
    app.pending = None
    step = session.submit("Ещё")
    assert "нет такого варианта" in notes_text(step)


def test_limit_not_checked_while_menu_is_pending(registry, tmp_path):
    app = limited_app(registry, tmp_path, FATAL, 1)
    step = make_session(app).submit("Иду")
    assert app.pending == "error_menu"
    assert "лимит" not in notes_text(step)


def test_limit_not_checked_for_a_command(registry, tmp_path):
    app = limited_app(registry, tmp_path, [PAID], 1)
    step = make_session(app).submit("/help")
    assert "лимит" not in notes_text(step)


def test_day_limit_pauses_when_session_limit_is_off(registry, tmp_path):
    app = text_app(registry, tmp_path, [PAID, PAID])
    cfg = app.settings.app.cost_limits
    cfg.enabled = True
    cfg.session_limit_micro = 0
    cfg.day_limit_micro = 1
    step = make_session(app).submit("Иду")
    assert "лимит" in notes_text(step)
    assert [block for block in step.blocks if block.kind == "menu"]


# выход: автосейв

def test_finish_saves_auto_and_says_so(registry, tmp_path):
    from ai_dm.persistence.store import load_slot

    app = text_app(registry, tmp_path, [text_step()])
    session = make_session(app)
    session.submit("Привет")
    step = session.finish()
    assert "Сохранено: auto." in texts(step, "note")
    assert load_slot(tmp_path, "vale-ui", "auto").session.turn_seq == 1
    assert step.exit_code == 0


def test_finish_does_not_save_in_replay(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    step = make_session(app, replay=True).finish()
    assert list_slots(tmp_path, "vale-ui") == []
    assert "сохранено" not in notes_text(step)
    assert step.exit_code == 0


def test_finish_does_not_save_when_hero_is_dead(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    app.bundle.heroes[0].status = "dead"
    app.pending = "hero_dead"
    step = make_session(app).finish()
    assert list_slots(tmp_path, "vale-ui") == []
    assert "сохранено" not in notes_text(step)


def test_finish_reports_save_failure(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    app.save_current = refuse_save
    step = make_session(app).finish()
    assert "Не удалось сохранить:" in "\n".join(texts(step, "note"))
    assert list_slots(tmp_path, "vale-ui") == []


def test_finish_does_not_raise_for_hero_dead_after_a_normal_turn(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    session = make_session(app)
    session.submit("Привет")
    assert app.pending is None
    assert session.finish().quit in (True, False)


# gains: снимок до/после хода (P0: «на фикстуре с наградой»)
# Награду имитируем в app.handle: он меняет героя и отдаёт Reply, как после реального хода.

def reward_app(registry, tmp_path, xp=0, money=0, item=None, outcome=None):
    from ai_dm.game.turn import TurnResult
    from ai_dm.state.hero import InventoryEntry

    app = text_app(registry, tmp_path, [text_step()])

    def handle(line):
        hero = hero_of(app.bundle)
        hero.sheet.xp += xp
        hero.money_cp += money
        if item:
            hero.inventory.append(InventoryEntry(item_id=item, qty=2, cost_cp=0))
        turn = TurnResult("r1")
        turn.committed = True
        turn.combat_outcome = outcome
        return Reply(turn=turn, narration="Бой окончен.")

    app.handle = handle
    return app


def gains_text(step):
    parts = []
    for block in step.blocks:
        if block.kind == "gains":
            parts += [block.text] + list(block.items)
    return "\n".join(parts)


def test_gains_after_victory_has_xp(registry, tmp_path):
    app = reward_app(registry, tmp_path, xp=75, outcome="victory")
    step = make_session(app).submit("Бью")
    assert "Получено опыта: 75" in gains_text(step)


def test_gains_xp_counts_from_the_turn_start_not_from_session_start(registry, tmp_path):
    app = reward_app(registry, tmp_path, xp=10, outcome="victory")
    hero_of(app.bundle).sheet.xp = 100
    step = make_session(app).submit("Бью")
    assert "Получено опыта: 10" in gains_text(step)


def test_gains_has_gold_when_money_grew(registry, tmp_path):
    app = reward_app(registry, tmp_path, money=250, outcome="victory")
    step = make_session(app).submit("Бью")
    assert "зм" in gains_text(step)


def test_gains_has_item_when_inventory_grew(registry, tmp_path):
    item = registry.ids("item")[0]
    name = registry.get("item", item).name
    app = reward_app(registry, tmp_path, item=item, outcome="victory")
    step = make_session(app).submit("Бью")
    assert item in gains_text(step) or name in gains_text(step)


def test_no_gains_when_nothing_changed(registry, tmp_path):
    app = reward_app(registry, tmp_path)
    step = make_session(app).submit("Иду")
    assert "gains" not in kinds(step)


# мутанты: limit_answer, начальное состояние

def test_limit_menu_is_closed_at_start(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    assert make_session(app).limit_menu is False


def test_limit_menu_is_closed_after_continue(registry, tmp_path):
    app = limited_app(registry, tmp_path, [PAID, PAID], 1)
    session = make_session(app)
    session.submit("Иду")
    session.submit("1")
    assert session.limit_menu is False


def test_limit_refused_exit_note_is_exact(registry, tmp_path):
    app = limited_app(registry, tmp_path, [PAID, PAID], 1)
    session = make_session(app)
    session.submit("Иду")
    app.pending = "hero_dead"
    step = session.submit("2")
    assert texts(step, "note") == ["Герой погиб: сохранять нельзя."]


def test_limit_saved_note_is_exact(registry, tmp_path):
    app = limited_app(registry, tmp_path, [PAID, PAID], 1)
    session = make_session(app)
    session.submit("Иду")
    step = session.submit("2")
    assert texts(step, "note") == ["Сохранено."]


def test_key_command_puts_request_into_step(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    assert make_session(app).submit("/key").request == "key"


def test_ordinary_turn_and_commands_have_no_request(registry, tmp_path):
    session = make_session(text_app(registry, tmp_path, [text_step()]))
    assert session.submit("/help").request is None
    assert session.submit("Иду").request is None


def test_limit_unknown_answer_note_is_exact(registry, tmp_path):
    app = limited_app(registry, tmp_path, [PAID, PAID], 1)
    session = make_session(app)
    session.submit("Иду")
    step = session.submit("Ещё")
    assert texts(step, "note") == ["Нет такого варианта."]
