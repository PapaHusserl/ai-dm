# Ожидаемый API (P0 этапа 5, STAGE5-PLAN A2): ai_dm.ui.screen -- модель экрана без ввода-вывода.
# Допущения об именах (в плане их нет, выбраны здесь -- это ТРЕБОВАНИЕ к реализации):
#   Block(kind, text="", items=(), title=None) -- атрибуты .kind .text .items .title
#   reply_blocks(app, reply, xp_before) -> list[Block]   (бывший show_reply)
#   screen_blocks(app) -> list[Block]                     (бывший show_screen)
#   status_line(app), limit_state(app), LABELS            (переезжают из simple как есть)
# Текст блока берётся и из .text, и из .items: лишнее разбиение на строки тестам не важно.
import ast
from pathlib import Path

from ui_kit import DESCEND, TALK, scene_app, text_app, text_step

from ai_dm.game.app import Reply
from ai_dm.game.scene import hero_of
from ai_dm.game.turn import TurnResult

FATAL = [{"error": "fatal", "message": "ключ отозван"}]
OFFER = {
    "tool_calls": [
        {"id": "c1", "name": "offer_choices",
         "input": {"type": "offer_choices", "choices": ["Спросить про подвал", "Заказать эль"]}},
    ]
}
UI = Path(__file__).resolve().parents[3] / "src" / "ai_dm" / "ui"


def kinds(blocks):
    return [block.kind for block in blocks]


def texts(blocks, kind):
    result = []
    for block in blocks:
        if block.kind == kind:
            result += [block.text] if block.text else list(block.items)
    return result


def turn_with(**fields):
    turn = TurnResult("r1")
    turn.committed = True
    for name, value in fields.items():
        setattr(turn, name, value)
    return turn


# reply_blocks: ветки

def test_empty_reply_gives_no_blocks(registry, tmp_path):
    from ai_dm.ui.screen import reply_blocks

    app = text_app(registry, tmp_path, [text_step()])
    assert reply_blocks(app, Reply(), 0) == []


def test_narration_is_a_narration_block(registry, tmp_path):
    from ai_dm.ui.screen import reply_blocks

    app = text_app(registry, tmp_path, [text_step()])
    blocks = reply_blocks(app, Reply(narration="Трактирщик кивает."), 0)
    assert kinds(blocks) == ["narration"]
    assert "Трактирщик кивает." in texts(blocks, "narration")[0]


def test_reply_lines_are_note_blocks(registry, tmp_path):
    from ai_dm.ui.screen import reply_blocks

    app = text_app(registry, tmp_path, [text_step()])
    blocks = reply_blocks(app, Reply(lines=["Раз", "Два"]), 0)
    assert kinds(blocks) == ["note", "note"]
    assert texts(blocks, "note") == ["Раз", "Два"]


def test_raw_lines_are_a_raw_block(registry, tmp_path):
    from ai_dm.ui.screen import reply_blocks

    app = text_app(registry, tmp_path, [text_step()])
    blocks = reply_blocks(app, Reply(raw=["a  b", "c   d"]), 0)
    assert kinds(blocks) == ["raw"]
    assert texts(blocks, "raw") == ["a  b", "c   d"]


def test_hint_is_a_hint_or_note_block_after_lines(registry, tmp_path):
    from ai_dm.ui.screen import reply_blocks

    app = text_app(registry, tmp_path, [text_step()])
    blocks = reply_blocks(app, Reply(lines=["Строка"], hint="Совет"), 0)
    assert kinds(blocks)[0] == "note"
    assert kinds(blocks)[-1] == "hint"
    assert texts(blocks, "hint") == ["Совет"]


def test_roll_line_from_turn_rolls_is_a_roll_block(registry, tmp_path):
    from ai_dm.ui.screen import reply_blocks

    app = text_app(registry, tmp_path, [text_step()])
    turn = turn_with(lines=["Арн: d20 (14)", "Заметка"], rolls=["Арн: d20 (14)"])
    blocks = reply_blocks(app, Reply(turn=turn), 0)
    assert kinds(blocks) == ["roll", "note"]
    assert texts(blocks, "roll") == ["Арн: d20 (14)"]
    assert texts(blocks, "note") == ["Заметка"]


def test_turn_line_already_in_log_is_not_repeated(registry, tmp_path):
    from ai_dm.ui.screen import reply_blocks

    app = text_app(registry, tmp_path, [text_step()])
    turn = turn_with(lines=["Удар"], log=["Удар"])
    blocks = reply_blocks(app, Reply(turn=turn), 0)
    assert texts(blocks, "note") == ["Удар"]
    assert len(blocks) == 1


def test_log_lines_come_after_turn_lines(registry, tmp_path):
    from ai_dm.ui.screen import reply_blocks

    app = text_app(registry, tmp_path, [text_step()])
    turn = turn_with(lines=["Первая"], log=["Вторая"])
    blocks = reply_blocks(app, Reply(turn=turn), 0)
    assert texts(blocks, "note") == ["Первая", "Вторая"]


def test_service_lines_are_dropped_from_lines_and_log(registry, tmp_path):
    from ai_dm.ui.screen import reply_blocks

    app = text_app(registry, tmp_path, [text_step()])
    turn = turn_with(
        lines=["Действие игрока: иду", "Варианты ответа предложены: 2", "Нужная"],
        log=["Действие игрока: иду", "Варианты ответа предложены: 2"],
    )
    blocks = reply_blocks(app, Reply(turn=turn), 0)
    assert texts(blocks, "note") == ["Нужная"]


def test_service_prefix_is_kept_in_reply_lines(registry, tmp_path):
    # фильтр касается только строк хода, не reply.lines (как в show_reply)
    from ai_dm.ui.screen import reply_blocks

    app = text_app(registry, tmp_path, [text_step()])
    blocks = reply_blocks(app, Reply(lines=["Действие игрока: x"]), 0)
    assert texts(blocks, "note") == ["Действие игрока: x"]


def test_order_turn_lines_narration_boundary_reply_lines_raw_hint(registry, tmp_path):
    from ai_dm.ui.screen import reply_blocks

    app = text_app(registry, tmp_path, [text_step()])
    turn = turn_with(lines=["Строка хода"], chapter_closed=(1, "Пролог"))
    reply = Reply(
        lines=["Строка ответа"], narration="Рассказ", turn=turn, raw=["сырая"], hint="Совет"
    )
    blocks = reply_blocks(app, reply, 0)
    order = kinds(blocks)
    assert order[0] == "note"
    assert texts(blocks, "note")[0] == "Строка хода"
    assert order.index("narration") == 1
    assert order[-3:] == ["note", "raw", "hint"]
    assert texts(blocks, "note")[-1] == "Строка ответа"
    assert "boundary" in order
    assert order.index("narration") < order.index("boundary") < order.index("raw")


def test_boundary_block_for_closed_chapter(registry, tmp_path):
    from ai_dm.game.boundary import boundary_lines
    from ai_dm.ui.screen import reply_blocks

    app = text_app(registry, tmp_path, [text_step()])
    turn = turn_with(chapter_closed=(2, "Подвал"), offscreen=["Где-то далеко упал камень"])
    blocks = reply_blocks(app, Reply(turn=turn), 0)
    assert kinds(blocks) == ["boundary"] * len(boundary_lines(turn.chapter_closed, turn.offscreen))
    assert texts(blocks, "boundary") == boundary_lines(turn.chapter_closed, turn.offscreen)


def test_no_boundary_without_turn(registry, tmp_path):
    from ai_dm.ui.screen import reply_blocks

    app = text_app(registry, tmp_path, [text_step()])
    assert "boundary" not in kinds(reply_blocks(app, Reply(lines=["x"]), 0))


def test_victory_adds_outcome_note_and_gains_with_xp(registry, tmp_path):
    from ai_dm.ui.screen import reply_blocks

    app = text_app(registry, tmp_path, [text_step()])
    hero = hero_of(app.bundle)
    before = hero.sheet.xp
    hero.sheet.xp = before + 50
    blocks = reply_blocks(app, Reply(turn=turn_with(combat_outcome="victory")), before)
    assert any("победа" in text.lower() for text in texts(blocks, "note"))
    assert kinds(blocks)[-1] == "gains"
    assert "Получено опыта: 50" in texts(blocks, "gains")[0]


def test_victory_xp_is_not_duplicated_in_gains_items(registry, tmp_path):
    from ai_dm.ui.screen import reply_blocks

    app = text_app(registry, tmp_path, [text_step()])
    hero = hero_of(app.bundle)
    before = (hero.sheet.xp, {}, hero.money_cp)
    hero.sheet.xp = before[0] + 50
    blocks = reply_blocks(app, Reply(turn=turn_with(combat_outcome="victory")), before[0], before)
    gains = [block for block in blocks if block.kind == "gains"][0]
    assert gains.text == "Получено опыта: 50"
    assert not any("Опыт: +" in item for item in gains.items)


def test_victory_notes_come_last_after_narration(registry, tmp_path):
    from ai_dm.ui.screen import reply_blocks

    app = text_app(registry, tmp_path, [text_step()])
    blocks = reply_blocks(
        app, Reply(narration="Гоблин падает.", turn=turn_with(combat_outcome="victory")), 0
    )
    assert kinds(blocks)[0] == "narration"
    assert kinds(blocks)[1:] == ["note", "gains"]


def test_other_outcome_gives_no_gains(registry, tmp_path):
    from ai_dm.ui.screen import reply_blocks

    app = text_app(registry, tmp_path, [text_step()])
    blocks = reply_blocks(app, Reply(turn=turn_with(combat_outcome="defeat")), 0)
    assert "gains" not in kinds(blocks)
    assert not any("победа" in text.lower() for text in texts(blocks, "note"))


def test_no_gains_without_turn(registry, tmp_path):
    from ai_dm.ui.screen import reply_blocks

    app = text_app(registry, tmp_path, [text_step()])
    assert "gains" not in kinds(reply_blocks(app, Reply(lines=["x"]), 0))


# screen_blocks: ветки

def test_screen_pending_gives_menu_block_with_labels(registry, tmp_path):
    from ai_dm.ui.screen import LABELS, screen_blocks

    app = text_app(registry, tmp_path, FATAL)
    app.pending = "error_menu"
    blocks = screen_blocks(app)
    assert kinds(blocks) == ["menu"]
    assert list(blocks[0].items) == [LABELS[key] for key in app.menu_for("error_menu")]
    assert blocks[0].title == "Выбери:"


def test_screen_pending_model_choice_uses_menu_label(registry, tmp_path):
    from ai_dm.ui.screen import screen_blocks

    app = text_app(registry, tmp_path, [text_step()])
    app.pending = "model_choice"
    blocks = screen_blocks(app)
    assert list(blocks[0].items) == [app.menu_label(key) for key in app.menu_for("model_choice")]


def test_screen_offered_choices_is_a_menu_block(registry, tmp_path):
    from ai_dm.ui.screen import screen_blocks

    app = text_app(registry, tmp_path, [text_step()])
    app.bundle.session.offered_choices = ["Спросить", "Заказать"]
    blocks = screen_blocks(app)
    assert kinds(blocks) == ["menu"]
    assert list(blocks[0].items) == ["Спросить", "Заказать"]
    assert blocks[0].title == "Что делаешь?"


def test_screen_empty_gives_no_blocks(registry, tmp_path):
    from ai_dm.ui.screen import screen_blocks

    app = text_app(registry, tmp_path, [text_step()])
    assert screen_blocks(app) == []


def test_pending_wins_over_offered_choices(registry, tmp_path):
    from ai_dm.ui.screen import screen_blocks

    app = text_app(registry, tmp_path, FATAL)
    app.bundle.session.offered_choices = ["Спросить"]
    app.pending = "error_menu"
    assert kinds(screen_blocks(app)) == ["menu"]
    assert "Спросить" not in screen_blocks(app)[0].items


def combat_app(registry, tmp_path):
    from slots_kit import ScriptedInput
    from ui_kit import PlainOutput

    from ai_dm.ui.simple import run

    app, _ = scene_app(registry, tmp_path, hp=200)
    run(app, ScriptedInput([TALK, "1", DESCEND]), PlainOutput())
    assert app.bundle.session.active_combat is not None
    return app


def test_screen_in_combat_gives_map_turn_menu_and_hint(registry, tmp_path):
    from ai_dm.ui.screen import screen_blocks

    app = combat_app(registry, tmp_path)
    app.hinted_combat = None
    blocks = screen_blocks(app)
    assert kinds(blocks) == ["combat_map", "turn_menu", "combat_hint"]
    assert len(texts(blocks, "turn_menu")) > 0


def test_screen_combat_hint_only_once_per_combat(registry, tmp_path):
    from ai_dm.ui.screen import screen_blocks

    app = combat_app(registry, tmp_path)
    app.hinted_combat = None
    screen_blocks(app)
    assert kinds(screen_blocks(app)) == ["combat_map", "turn_menu"]


def test_screen_combat_ignores_offered_choices(registry, tmp_path):
    from ai_dm.ui.screen import screen_blocks

    app = combat_app(registry, tmp_path)
    app.bundle.session.offered_choices = ["Старый вариант"]
    assert "menu" not in kinds(screen_blocks(app))


# status_line, limit_state, LABELS

def test_status_line_is_the_same_as_in_simple(registry, tmp_path):
    from ai_dm.ui.screen import status_line
    from ai_dm.ui.simple import status_line as simple_status

    app = text_app(registry, tmp_path, [text_step()])
    assert status_line(app) == simple_status(app)


def test_status_line_shows_cursed_after_hp(registry, tmp_path):
    from ai_dm.game.scene import hero_of
    from ai_dm.state.creature import AppliedCondition
    from ai_dm.ui.screen import status_line

    app = text_app(registry, tmp_path, [text_step()])
    creature = hero_of(app.bundle).creature
    creature.conditions.append(AppliedCondition(id="cursed"))
    expected = f"HP {creature.hp_current}/{creature.hp_max} · проклят · "
    assert status_line(app).startswith(expected)


def test_status_line_without_conditions_has_no_condition_part(registry, tmp_path):
    from ai_dm.game.scene import hero_of
    from ai_dm.ui.screen import status_line

    app = text_app(registry, tmp_path, [text_step()])
    creature = hero_of(app.bundle).creature
    line = status_line(app)
    assert line.startswith(f"HP {creature.hp_current}/{creature.hp_max} · ")
    assert "проклят" not in line
    assert " ·  · " not in line


def test_status_line_lists_every_condition_once(registry, tmp_path):
    from ai_dm.game.scene import hero_of
    from ai_dm.state.creature import AppliedCondition
    from ai_dm.ui.screen import status_line

    app = text_app(registry, tmp_path, [text_step()])
    creature = hero_of(app.bundle).creature
    creature.conditions.extend(AppliedCondition(id="cursed") for _ in range(2))
    assert status_line(app).count("проклят") == 1


def groomed_effect(until):
    from ai_dm.state.creature import ActiveEffect, Expiry

    return ActiveEffect(
        id="groomed", source="service:tobb", kind="modifier",
        params={"target": "ability_check", "ability": "cha", "dice": "1d4", "consume": True},
        expires=Expiry(kind="seconds", value=until),
    )


def test_status_line_shows_groomed_after_hp(registry, tmp_path):
    from ai_dm.ui.screen import status_line

    app = text_app(registry, tmp_path, [text_step()])
    creature = hero_of(app.bundle).creature
    creature.active_effects.append(groomed_effect(app.bundle.world.clock.now_s + 3600))
    assert status_line(app).startswith(f"HP {creature.hp_current}/{creature.hp_max} · ухожен · ")


def test_status_line_shows_inspiration(registry, tmp_path):
    from ai_dm.ui.screen import status_line

    app = text_app(registry, tmp_path, [text_step()])
    creature = hero_of(app.bundle).creature
    hero_of(app.bundle).heroic_inspiration = True
    expected = f"HP {creature.hp_current}/{creature.hp_max} · вдохновение · "
    assert status_line(app).startswith(expected)


def test_status_line_puts_conditions_before_boons(registry, tmp_path):
    from ai_dm.state.creature import AppliedCondition
    from ai_dm.ui.screen import status_line

    app = text_app(registry, tmp_path, [text_step()])
    hero = hero_of(app.bundle)
    hero.creature.conditions.append(AppliedCondition(id="cursed"))
    hero.creature.active_effects.append(groomed_effect(app.bundle.world.clock.now_s + 3600))
    hero.heroic_inspiration = True
    assert " · проклят · ухожен · вдохновение · " in status_line(app)


def test_status_line_drops_expired_groomed(registry, tmp_path):
    from ai_dm.ui.screen import status_line

    app = text_app(registry, tmp_path, [text_step()])
    creature = hero_of(app.bundle).creature
    creature.active_effects.append(groomed_effect(app.bundle.world.clock.now_s))
    assert "ухожен" not in status_line(app)


def test_status_line_without_boons_has_no_boon_words(registry, tmp_path):
    from ai_dm.ui.screen import status_line

    app = text_app(registry, tmp_path, [text_step()])
    hero_of(app.bundle).heroic_inspiration = False
    line = status_line(app)
    assert "ухожен" not in line
    assert "вдохновение" not in line
    assert " ·  · " not in line


def test_simple_status_line_shows_cursed_too(registry, tmp_path):
    from ai_dm.game.scene import hero_of
    from ai_dm.state.creature import AppliedCondition
    from ai_dm.ui.simple import status_line

    app = text_app(registry, tmp_path, [text_step()])
    hero_of(app.bundle).creature.conditions.append(AppliedCondition(id="cursed"))
    assert " · проклят · " in status_line(app)


def test_limit_state_off_by_default_is_ok(registry, tmp_path):
    from ai_dm.ui.screen import limit_state

    app = text_app(registry, tmp_path, [text_step()])
    assert limit_state(app) == "ok"


def test_labels_cover_all_menu_keys_in_russian(registry, tmp_path):
    from ai_dm.ui.screen import LABELS

    assert LABELS["retry"] == "Повторить ход"
    assert LABELS["save_and_quit"] == "Сохранить и выйти"
    assert LABELS["quit"] == "Выйти"
    assert LABELS["load_last_save"] == "Загрузить последнее сохранение"


# сторож: никакого textual

def imported_modules(path):
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_screen_session_simple_do_not_import_textual():
    for name in ("screen.py", "session.py", "simple.py"):
        found = imported_modules(UI / name)
        assert not [module for module in found if module.split(".")[0] == "textual"], name


# мутанты: limit_state, combat_map_lines, combat_blocks

def fake_check_limit(by_limit):
    def check(cfg, spent_nano, limit_micro):
        return by_limit[limit_micro]

    return check


def limit_state_with(monkeypatch, registry, tmp_path, session_level, day_level):
    from ai_dm.ui import screen

    app = text_app(registry, tmp_path, [text_step()])
    cfg = app.settings.app.cost_limits
    cfg.session_limit_micro = 1
    cfg.day_limit_micro = 2
    monkeypatch.setattr(screen, "check_limit", fake_check_limit({1: session_level, 2: day_level}))
    return screen.limit_state(app)


def test_limit_state_session_pause_beats_day_warn(monkeypatch, registry, tmp_path):
    assert limit_state_with(monkeypatch, registry, tmp_path, "pause", "warn") == "pause"


def test_limit_state_day_pause_beats_session_warn(monkeypatch, registry, tmp_path):
    assert limit_state_with(monkeypatch, registry, tmp_path, "warn", "pause") == "pause"


def test_limit_state_warn_beats_ok(monkeypatch, registry, tmp_path):
    assert limit_state_with(monkeypatch, registry, tmp_path, "ok", "warn") == "warn"
    assert limit_state_with(monkeypatch, registry, tmp_path, "warn", "ok") == "warn"


def test_combat_map_lines_use_ui_width(registry, tmp_path):
    from ai_dm.game.battle_map import battle_map_lines
    from ai_dm.ui.screen import combat_map_lines

    app = combat_app(registry, tmp_path)
    app.settings.app.ui.width = 30
    state = app.bundle.session.active_combat
    narrow = battle_map_lines(state, app.bundle.world, hero_of(app.bundle), 30)
    assert narrow != battle_map_lines(state, app.bundle.world, hero_of(app.bundle))
    assert combat_map_lines(app) == narrow


def test_combat_turn_menu_carries_ac_text(registry, tmp_path):
    from ai_dm.ui.screen import screen_blocks

    app = combat_app(registry, tmp_path)
    blocks = screen_blocks(app)
    turn_menu = [block for block in blocks if block.kind == "turn_menu"][0]
    assert turn_menu.args[2] == app.runner.ac_text()
    assert turn_menu.args[2]


# limit_percent: процент лимита трат для строки состояния TUI (P2)

def percent_app(registry, tmp_path, session_micro, day_micro, enabled=True):
    app = text_app(registry, tmp_path, [text_step()])
    cfg = app.settings.app.cost_limits
    cfg.enabled = enabled
    cfg.session_limit_micro = session_micro
    cfg.day_limit_micro = day_micro
    return app


def spend(app, nano, role="narrator"):
    from ai_dm.llm.types import Usage

    app.ledger.add(
        call_id=f"p-{nano}", role=role, model="claude-opus-5-5", usage=Usage(input=1),
        cost_nano=nano, day=app.now().astimezone().date(),
    )


def test_limit_percent_is_none_when_limit_is_off(registry, tmp_path):
    from ai_dm.ui.screen import limit_percent

    app = percent_app(registry, tmp_path, 10, 10, enabled=False)
    spend(app, 5_000)
    assert limit_percent(app) is None


def test_limit_percent_is_none_when_both_limits_are_zero(registry, tmp_path):
    from ai_dm.ui.screen import limit_percent

    app = percent_app(registry, tmp_path, 0, 0)
    spend(app, 5_000)
    assert limit_percent(app) is None


def test_limit_percent_by_session(registry, tmp_path):
    from ai_dm.ui.screen import limit_percent

    app = percent_app(registry, tmp_path, 10, 0)
    spend(app, 5_000)
    assert limit_percent(app) == 50


def test_limit_percent_is_exactly_100_when_limit_is_spent(registry, tmp_path):
    from ai_dm.ui.screen import limit_percent

    app = percent_app(registry, tmp_path, 10, 0)
    spend(app, 10_000)
    assert limit_percent(app) == 100


def test_limit_percent_by_day_when_session_limit_is_off(registry, tmp_path):
    from ai_dm.ui.screen import limit_percent

    app = percent_app(registry, tmp_path, 0, 20)
    spend(app, 5_000)
    assert limit_percent(app) == 25


def test_limit_percent_day_includes_another_world(registry, tmp_path):
    from ai_dm.llm.cost import CostLedger
    from ai_dm.llm.types import Usage
    from ai_dm.ui.screen import limit_percent

    app = percent_app(registry, tmp_path, 0, 10)
    CostLedger(tmp_path, "other-world").add(
        call_id="o-1", role="narrator", model="claude-opus-5-5", usage=Usage(input=1),
        cost_nano=5_000, day=app.now().astimezone().date(),
    )
    assert limit_percent(app) == 50


def test_limit_percent_takes_the_larger_when_day_is_larger(registry, tmp_path):
    from ai_dm.ui.screen import limit_percent

    app = percent_app(registry, tmp_path, 100, 10)
    spend(app, 5_000)
    assert limit_percent(app) == 50


def test_limit_percent_takes_the_larger_when_session_is_larger(registry, tmp_path):
    from ai_dm.ui.screen import limit_percent

    app = percent_app(registry, tmp_path, 10, 100)
    spend(app, 5_000)
    assert limit_percent(app) == 50


def test_limit_percent_is_whole_number_rounded_down(registry, tmp_path):
    from ai_dm.ui.screen import limit_percent

    app = percent_app(registry, tmp_path, 3, 0)
    spend(app, 1_000)
    assert limit_percent(app) == 33


# turn_blocks, gains_block (Ж1: reply_blocks разбит на части, поведение прежнее)

def test_turn_blocks_roll_and_note_lines_in_order(registry, tmp_path):
    from ai_dm.ui.screen import turn_blocks

    app = text_app(registry, tmp_path, [text_step()])
    turn = turn_with(lines=["Бросок: 15", "Тихо"], rolls=["Бросок: 15"])
    blocks = turn_blocks(app, turn)
    assert [(b.kind, b.text, b.combat) for b in blocks] == [
        ("roll", "Бросок: 15", False), ("note", "Тихо", False),
    ]


def test_turn_blocks_skip_service_lines(registry, tmp_path):
    from ai_dm.ui.screen import turn_blocks

    app = text_app(registry, tmp_path, [text_step()])
    turn = turn_with(lines=["Действие игрока: удар", "Варианты ответа предложены", "Тихо"])
    assert texts(turn_blocks(app, turn), "note") == ["Тихо"]


def test_turn_blocks_log_goes_after_lines_as_combat_blocks(registry, tmp_path):
    from ai_dm.ui.screen import turn_blocks

    app = text_app(registry, tmp_path, [text_step()])
    turn = turn_with(lines=["Удар", "Тихо"], log=["Удар"])
    blocks = turn_blocks(app, turn)
    assert [(b.text, b.combat) for b in blocks] == [("Тихо", False), ("Удар", True)]


def test_turn_blocks_rolls_in_fight_are_combat_blocks(registry, tmp_path):
    from ai_dm.ui.screen import turn_blocks

    app = text_app(registry, tmp_path, [text_step()])
    turn = turn_with(lines=["Бросок: 15"], rolls=["Бросок: 15"], log=["Лог боя"])
    assert turn_blocks(app, turn)[0].combat is True


def test_turn_blocks_skip_service_lines_in_log(registry, tmp_path):
    from ai_dm.ui.screen import turn_blocks

    app = text_app(registry, tmp_path, [text_step()])
    turn = turn_with(log=["Действие игрока: удар", "Гоблин падает"])
    assert texts(turn_blocks(app, turn), "note") == ["Гоблин падает"]


def test_gains_block_without_victory_and_snapshot_is_empty(registry, tmp_path):
    from ai_dm.ui.screen import gains_block

    app = text_app(registry, tmp_path, [text_step()])
    assert gains_block(app, False, 0, None) == []


def test_gains_block_victory_shows_xp_difference(registry, tmp_path):
    from ai_dm.ui.screen import gains_block

    app = text_app(registry, tmp_path, [text_step()])
    hero_of(app.bundle).sheet.xp = 150
    [block] = gains_block(app, True, 100, None)
    assert (block.kind, block.text, block.items) == ("gains", "Получено опыта: 50", ())


def test_gains_block_items_come_from_snapshot(registry, tmp_path):
    from ai_dm.ui.screen import gains_block, loot_snapshot

    app = text_app(registry, tmp_path, [text_step()])
    before = loot_snapshot(app)
    hero_of(app.bundle).money_cp += 100
    [block] = gains_block(app, False, 0, before)
    assert block.text == ""
    assert block.items == ("Деньги: +1 зм",)


def test_gains_block_victory_does_not_duplicate_xp_in_items(registry, tmp_path):
    from ai_dm.ui.screen import gains_block, loot_snapshot

    app = text_app(registry, tmp_path, [text_step()])
    before = loot_snapshot(app)
    hero_of(app.bundle).sheet.xp += 40
    [block] = gains_block(app, True, before[0], before)
    assert block.text == "Получено опыта: 40"
    assert block.items == ()


def test_gains_block_no_changes_with_snapshot_is_empty(registry, tmp_path):
    from ai_dm.ui.screen import gains_block, loot_snapshot

    app = text_app(registry, tmp_path, [text_step()])
    assert gains_block(app, False, 0, loot_snapshot(app)) == []


def test_gains_block_without_victory_keeps_xp_in_items(registry, tmp_path):
    from ai_dm.ui.screen import gains_block, loot_snapshot

    app = text_app(registry, tmp_path, [text_step()])
    before = loot_snapshot(app)
    hero_of(app.bundle).sheet.xp += 40
    [block] = gains_block(app, False, before[0], before)
    assert block.items == ("Опыт: +40",)


def test_reply_blocks_snapshot_without_victory_gives_gains_items(registry, tmp_path):
    from ai_dm.ui.screen import loot_snapshot, reply_blocks

    app = text_app(registry, tmp_path, [text_step()])
    before = loot_snapshot(app)
    hero_of(app.bundle).money_cp += 100
    blocks = reply_blocks(app, Reply(lines=["Тихо"]), 0, before)
    assert [b.items for b in blocks if b.kind == "gains"] == [("Деньги: +1 зм",)]


def test_reply_blocks_victory_with_snapshot_passes_it_to_gains(registry, tmp_path):
    from ai_dm.ui.screen import loot_snapshot, reply_blocks

    app = text_app(registry, tmp_path, [text_step()])
    before = loot_snapshot(app)
    hero_of(app.bundle).money_cp += 100
    reply = Reply(turn=turn_with(combat_outcome="victory"))
    blocks = reply_blocks(app, reply, before[0], before)
    assert [b.items for b in blocks if b.kind == "gains"] == [("Деньги: +1 зм",)]
