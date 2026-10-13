# Ожидаемый API: ai_dm.ui.simple (status_line, run) -- контракт в ui_kit.py.
# Рендер ответов GameApp в строки и цикл на ScriptedInput / CaptureOutput, без настоящего stdin.
# Сид 3, герой Арн, мир «Вейл»: бросок инициативы «Арн: инициатива d20 (9) + 1 = 10» известен.
import re

from slots_kit import list_slots
from ui_kit import (
    DESCEND,
    OPUS,
    TALK,
    FactorySpy,
    FightInput,
    PlainOutput,
    numbered_lines,
    play,
    requests_with_tools,
    scene_app,
    state_of,
    text_app,
    text_step,
)

from ai_dm.art import art_for_event
from ai_dm.game.scene import hero_of

COST = {"input": 1500, "output": 60}
PAID = {"text": "Рассказ.", "usage": COST}
FATAL = [{"error": "fatal", "message": "ключ отозван"}]
OFFER = {
    "tool_calls": [
        {"id": "c1", "name": "offer_choices",
         "input": {"type": "offer_choices", "choices": ["Спросить про подвал", "Заказать эль"]}},
    ]
}
CLASSIFY = {"player_action", "unsupported_action"}


def run_lines(app, lines):
    from slots_kit import ScriptedInput

    from ai_dm.ui.simple import run

    out = PlainOutput()
    source = ScriptedInput(lines)
    run(app, source, out)
    return out, source


def spent_nano(app):
    return app.ledger.report(app.now().date()).session.total_nano


def limited_app(registry, root, steps, limit_micro):
    app = text_app(registry, root, steps)
    app.settings.app.cost_limits.enabled = True
    app.settings.app.cost_limits.session_limit_micro = limit_micro
    return app


# строка состояния

def test_status_line_has_hp_date_time_and_session_cost(registry, tmp_path):
    from ai_dm.ui.simple import status_line

    app = text_app(registry, tmp_path, [text_step()])
    hero = hero_of(app.bundle)
    line = status_line(app)
    assert f"HP {hero.creature.hp_current}/{hero.creature.hp_max}" in line
    assert app.bundle.world.clock.to_date() in line
    assert "00:00" in line
    assert re.search(r"сессия \$0\.0{3,4}$", line)
    assert re.search(r"HP \d+/\d+ · КД \d+ · ", line)
    assert line.count(" · ") == 3


def test_status_line_hp_follows_hero(registry, tmp_path):
    from ai_dm.ui.simple import status_line

    app = text_app(registry, tmp_path, [text_step()])
    hero_of(app.bundle).creature.hp_current = 5
    assert f"HP 5/{hero_of(app.bundle).creature.hp_max}" in status_line(app)


def test_status_line_shows_calendar_date_and_time_of_day(registry, tmp_path):
    from ai_dm.ui.simple import status_line

    app = text_app(registry, tmp_path, [text_step()])
    clock = app.bundle.world.clock
    clock.now_s = 3 * 86400 + 8 * 3600 + 30 * 60
    line = status_line(app)
    assert clock.to_date() in line
    assert "08:30" in line


def test_status_line_cost_comes_from_ledger_in_dollars(registry, tmp_path):
    from ai_dm.ui.simple import status_line

    app = text_app(registry, tmp_path, [PAID])
    play(app, ["Иду"])
    nano = spent_nano(app)
    assert nano > 0
    shown = re.search(r"сессия \$(\d+\.\d+)$", status_line(app)).group(1)
    assert len(shown.split(".")[1]) in (3, 4)
    assert float(shown) == round(nano / 1e9, len(shown.split(".")[1]))


# цикл: старт, конец, вывод ответа

def test_startup_lines_are_printed_first(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    app.startup_lines.append("Сохранённая модель не подключена: тест")
    out = play(app, [])
    # P6, В-2: при старте простой режим сначала печатает заставку-титул
    title_rows = len(art_for_event("title").split("\n"))
    assert out.lines[title_rows] == "Сохранённая модель не подключена: тест"


def test_status_line_is_printed_at_start(registry, tmp_path):
    from ai_dm.ui.simple import status_line

    app = text_app(registry, tmp_path, [text_step()])
    out = play(app, [])
    assert status_line(app) in out.lines


def test_narration_is_printed(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step("Трактирщик кивает вам.")])
    out = play(app, ["Здравствуйте"])
    assert "Трактирщик кивает вам." in out.text


def test_status_line_is_printed_after_reply(registry, tmp_path):
    from ai_dm.ui.simple import status_line

    app = text_app(registry, tmp_path, [PAID])
    out = play(app, ["Здравствуйте"])
    assert out.lines[-2] == status_line(app)
    assert out.lines[-1] == "Сохранено: auto."


def test_command_output_is_printed(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    out = play(app, ["/sheet"])
    assert "Арн" in out.text


def test_quit_stops_the_loop(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step(), text_step()])
    out, source = run_lines(app, ["/quit", "Привет"])
    assert source.remaining == ["Привет"]
    assert app.bundle.session.turn_seq == 0
    assert out.lines


def test_quit_saves_auto_and_says_so(registry, tmp_path):
    from slots_kit import list_slots

    app = text_app(registry, tmp_path, [text_step()])
    out = play(app, ["/quit"])
    assert list_slots(tmp_path, "vale-ui") == ["auto"]
    assert "Сохранено: auto" in out.text


def test_end_of_input_saves_auto_and_says_so(registry, tmp_path):
    from slots_kit import list_slots

    from ai_dm.persistence.store import load_slot

    app = text_app(registry, tmp_path, [text_step()])
    out = play(app, ["Привет"])
    assert list_slots(tmp_path, "vale-ui") == ["auto"]
    assert load_slot(tmp_path, "vale-ui", "auto").session.turn_seq == 1
    assert "Сохранено: auto" in out.text


def test_end_of_input_does_not_save_when_hero_is_dead(registry, tmp_path):
    from slots_kit import list_slots

    app = text_app(registry, tmp_path, [text_step()])
    app.bundle.heroes[0].status = "dead"
    app.pending = "hero_dead"
    out = play(app, [])
    assert list_slots(tmp_path, "vale-ui") == []
    assert "Сохранено: auto" not in out.text


def test_quit_does_not_save_when_hero_is_dead(registry, tmp_path):
    from slots_kit import list_slots

    app = text_app(registry, tmp_path, [text_step()])
    app.bundle.heroes[0].status = "dead"
    app.pending = "hero_dead"
    play(app, ["/quit"])
    assert list_slots(tmp_path, "vale-ui") == []


def test_loop_ends_when_input_ends(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step(), text_step()])
    play(app, ["Привет", "Ещё"])
    assert app.bundle.session.turn_seq == 2


def test_each_line_is_one_turn(registry, tmp_path):
    adapter_app = text_app(registry, tmp_path, [text_step("Раз."), text_step("Два.")])
    out = play(adapter_app, ["Первое", "Второе"])
    assert out.text.index("Раз.") < out.text.index("Два.")


# броски

def test_roll_lines_have_prefix_and_tz6_format(registry, tmp_path):
    app, _ = scene_app(registry, tmp_path)
    out = play(app, [TALK, "1"])
    rolls = [line for line in out.lines if line.startswith("[бросок] ")]
    assert rolls
    assert any(re.search(r"d20 \(\d+\).* = \d+ против СЛ 15 → ", line) for line in rolls)


def test_every_recorded_roll_line_is_printed_with_prefix(registry, tmp_path):
    app, _ = scene_app(registry, tmp_path)
    out = play(app, [TALK, "1"])
    rolls = app.bundle.memory.recent_turns[-1].rolls
    assert rolls
    for line in rolls:
        assert f"[бросок] {line}" in out.lines


def test_combat_log_lines_are_printed(registry, tmp_path):
    app, _ = scene_app(registry, tmp_path)
    out = play(app, [TALK, "1", DESCEND])
    assert "Бой начался" in out.text
    assert "Арн: инициатива d20 (9) + 1 = 10" in out.text
    # строки лога переносятся по ширине: склеиваем
    assert "против КД 19 → промах" in " ".join(out.lines)


# варианты

def test_offered_choices_are_numbered(registry, tmp_path):
    app = text_app(registry, tmp_path, [OFFER, text_step("Трактирщик косится.")])
    out = play(app, ["Здравствуйте"])
    assert "1. Спросить про подвал" in out.lines
    assert "2. Заказать эль" in out.lines


def test_number_picks_offered_choice_as_player_text(registry, tmp_path):
    app = text_app(registry, tmp_path, [OFFER, text_step("Раз."), text_step("Два.")])
    play(app, ["Здравствуйте", "2"])
    adapter = app.adapter
    assert state_of(adapter.requests[2])["player_input"] == "Заказать эль"


def test_text_is_sent_as_is_when_choices_are_offered(registry, tmp_path):
    app = text_app(registry, tmp_path, [OFFER, text_step("Раз."), text_step("Два.")])
    play(app, ["Здравствуйте", "Сам решу"])
    assert state_of(app.adapter.requests[2])["player_input"] == "Сам решу"


def test_combat_actions_are_numbered_from_one(registry, tmp_path):
    app, _ = scene_app(registry, tmp_path)
    out = play(app, [TALK, "1", DESCEND])
    options = app.runner.preview_turn()
    assert options
    for number, option in enumerate(options, start=1):
        assert f"{number}. {option.label}" in out.lines
    assert f"{len(options)}. Закончить ход" in out.lines


def test_number_in_combat_is_an_action_not_an_old_offered_choice(registry, tmp_path):
    app, adapter = scene_app(registry, tmp_path, hp=200)
    play(app, [TALK, "1", DESCEND, "1"])
    assert app.bundle.session.turn_seq == 4
    assert requests_with_tools(adapter, CLASSIFY) == []


def test_actions_are_shown_again_after_a_combat_turn(registry, tmp_path):
    from ai_dm.ui.simple import run

    app, _ = scene_app(registry, tmp_path, hp=200)
    out = PlainOutput()
    run(app, FightInput(out, [TALK, "1", DESCEND], limit=1), out)
    assert app.bundle.session.turn_seq == 4
    ends = [n for n, text in numbered_lines(out.lines) if text == "Закончить ход"]
    assert len(ends) == 2


def test_resumed_combat_shows_actions_at_start(registry, tmp_path):
    app, _ = scene_app(registry, tmp_path)
    play(app, [TALK, "1", DESCEND])
    out = play(app, [])
    options = app.runner.preview_turn()
    for number, option in enumerate(options, start=1):
        assert f"{number}. {option.label}" in out.lines


# меню ошибки хода

def test_error_menu_is_numbered_with_three_items(registry, tmp_path):
    app = text_app(registry, tmp_path, FATAL)
    out = play(app, ["Иду"])
    items = [text.lower() for _, text in numbered_lines(out.lines)]
    assert [n for n, _ in numbered_lines(out.lines)] == [1, 2, 3]
    assert "повтор" in items[0]
    assert "модел" in items[1]
    assert "сохран" in items[2]


def test_error_menu_shows_failure_hint(registry, tmp_path):
    app = text_app(registry, tmp_path, FATAL)
    out = play(app, ["Иду"])
    assert "ключ отозван" in out.text


def test_refusal_hint_mentions_tone_and_model(registry, tmp_path):
    app = text_app(registry, tmp_path, [{"stop": "refusal"}] * 2)
    out = play(app, ["Иду"]).text.lower()
    assert "tone" in out
    assert "модел" in out


def test_error_menu_retry_plays_the_turn_again(registry, tmp_path):
    app = text_app(registry, tmp_path, FATAL + [text_step("Починилось.")])
    out = play(app, ["Иду", "1"])
    assert "Починилось." in out.text
    assert app.bundle.session.turn_seq == 1
    assert app.pending is None


def test_error_menu_switch_model_shows_model_options(registry, tmp_path):
    app = text_app(registry, tmp_path, FATAL, adapter_factory=FactorySpy())
    out = play(app, ["Иду", "2"])
    texts = [text for _, text in numbered_lines(out.lines)]
    assert f"anthropic:{OPUS}" in texts


def test_error_menu_pick_model_returns_to_error_menu(registry, tmp_path):
    spy = FactorySpy()
    app = text_app(registry, tmp_path, FATAL, adapter_factory=spy)
    options = app.model_options()
    pick = str(options.index(f"anthropic:{OPUS}") + 1)
    out = play(app, ["Иду", "2", pick])
    assert spy.calls == [("anthropic", OPUS)]
    assert app.pending == "error_menu"
    assert "повтор" in " ".join(text.lower() for _, text in numbered_lines(out.lines[-6:]))


def test_error_menu_save_and_quit_saves_and_ends(registry, tmp_path):
    app = text_app(registry, tmp_path, FATAL)
    out, source = run_lines(app, ["Иду", "3", "Ещё"])
    assert "auto" in list_slots(tmp_path, "vale-ui")
    assert source.remaining == ["Ещё"]
    assert out.lines


def test_menu_number_out_of_range_is_rejected(registry, tmp_path):
    app = text_app(registry, tmp_path, FATAL)
    out = play(app, ["Иду", "9"])
    assert "нет такого варианта" in out.text.lower()
    assert app.pending == "error_menu"


# повышение уровня

def level_app(registry, root, steps):
    app = text_app(registry, root, steps)
    hero_of(app.bundle).sheet.xp = 300
    return app


def test_level_up_menu_is_numbered(registry, tmp_path):
    app = level_app(registry, tmp_path, [text_step()])
    out = play(app, ["Иду"])
    items = [text.lower() for _, text in numbered_lines(out.lines)]
    assert len(items) == 2
    assert "средн" in items[0]
    assert "бросок" in items[1]


def test_level_up_average_applies(registry, tmp_path):
    app = level_app(registry, tmp_path, [text_step()])
    play(app, ["Иду", "1"])
    assert hero_of(app.bundle).sheet.level == 2
    assert app.pending is None


def test_level_up_roll_applies_and_moves_rng(registry, tmp_path):
    app = level_app(registry, tmp_path, [text_step()])
    draws = app.bundle.world.rng.draws
    play(app, ["Иду", "2"])
    assert hero_of(app.bundle).sheet.level == 2
    assert app.bundle.world.rng.draws > draws


def test_turn_is_not_played_while_level_menu_is_open(registry, tmp_path):
    app = level_app(registry, tmp_path, [text_step(), text_step("Лишнее.")])
    out = play(app, ["Иду", "Ещё иду"])
    assert app.bundle.session.turn_seq == 1
    assert "Лишнее." not in out.text


# смерть героя

def test_hero_dead_menu_is_numbered(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    app.pending = "hero_dead"
    out = play(app, [])
    items = [text.lower() for _, text in numbered_lines(out.lines)]
    assert len(items) == 2
    assert "загруз" in items[0]
    assert "выйти" in items[1]


def test_hero_dead_quit_ends_the_loop(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    app.pending = "hero_dead"
    out, source = run_lines(app, ["2", "Привет"])
    assert source.remaining == ["Привет"]
    assert out.lines


def test_hero_dead_load_without_save_says_so_and_keeps_menu(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    app.pending = "hero_dead"
    out = play(app, ["1"])
    assert "нет сохранений" in out.text
    assert app.pending == "hero_dead"


def test_hero_dead_load_last_save_loads_auto(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    app.save_current("auto")
    app.pending = "hero_dead"
    out = play(app, ["1"])
    assert "Загружено: auto." in out.text
    assert app.pending is None


# мягкий лимит

def probe_nano(registry, root):
    app = text_app(registry, root, [PAID])
    play(app, ["Иду"])
    return spent_nano(app)


def test_soft_limit_off_by_default_prints_nothing(registry, tmp_path):
    app = text_app(registry, tmp_path, [PAID])
    out = play(app, ["Иду"])
    assert "лимит" not in out.text.lower()


def test_soft_limit_warns_at_warn_percent(registry, tmp_path):
    from ai_dm.llm.cost import check_limit

    nano = probe_nano(registry, tmp_path / "probe")
    app = limited_app(registry, tmp_path / "main", [PAID], nano // 900)
    cfg = app.settings.app.cost_limits
    assert check_limit(cfg, nano, cfg.session_limit_micro) == "warn"
    out = play(app, ["Иду"])
    warn = [line for line in out.lines if "лимит" in line.lower()]
    assert any("80%" in line for line in warn)
    assert app.bundle.session.turn_seq == 1


def test_soft_limit_pause_offers_continue_or_save_and_quit(registry, tmp_path):
    app = limited_app(registry, tmp_path, [PAID, PAID], 1)
    out = play(app, ["Иду"])
    assert any("лимит" in line.lower() for line in out.lines)
    items = [text.lower() for _, text in numbered_lines(out.lines)]
    assert "продолж" in items[0]
    assert "сохран" in items[1]
    assert "выйти" in items[1]


def test_soft_limit_pause_save_and_quit(registry, tmp_path):
    app = limited_app(registry, tmp_path, [PAID, PAID], 1)
    out, source = run_lines(app, ["Иду", "2", "Ещё"])
    assert source.remaining == ["Ещё"]
    assert app.bundle.session.turn_seq == 1
    assert "auto" in list_slots(tmp_path, "vale-ui")
    assert out.lines


def test_soft_limit_pause_continue_plays_on(registry, tmp_path):
    app = limited_app(registry, tmp_path, [PAID, PAID], 1)
    play(app, ["Иду", "1", "Ещё"])
    assert app.bundle.session.turn_seq == 2


def test_soft_limit_does_not_ask_before_a_turn_when_far_from_limit(registry, tmp_path):
    app = limited_app(registry, tmp_path, [PAID], 10**9)
    out = play(app, ["Иду"])
    assert numbered_lines(out.lines) == []
    assert "лимит" not in out.text.lower()


# B4: вывод хода без дублей, [бросок] только у бросков, без служебных строк

def test_combat_start_initiative_lines_are_printed_once_each(registry, tmp_path):
    app, _ = scene_app(registry, tmp_path)
    out = play(app, [TALK, "1", DESCEND])
    initiative = [line for line in out.lines if "инициатива" in line]
    assert len(initiative) >= 2
    assert len(initiative) == len(set(initiative))
    assert len([line for line in initiative if "Арн: инициатива" in line]) == 1


def test_no_turn_line_is_printed_twice_on_the_combat_start_turn(registry, tmp_path):
    from ai_dm.ui.simple import show_reply

    app, _ = scene_app(registry, tmp_path)
    play(app, [TALK, "1"])
    reply = app.handle(DESCEND)
    out = PlainOutput()
    show_reply(app, reply, out, 0)
    assert reply.turn.log
    for line in reply.turn.log:
        assert " ".join(out.lines).count(line) == 1


def test_roll_prefix_only_on_lines_from_turn_rolls(registry, tmp_path):
    app, _ = scene_app(registry, tmp_path)
    out = play(app, [TALK, "1", DESCEND])
    rolls = [line for turn in app.bundle.memory.recent_turns for line in turn.rolls]
    prefixed = [line for line in out.lines if line.startswith("[бросок] ")]
    assert prefixed
    for line in prefixed:
        assert line[len("[бросок] "):] in rolls


def test_combat_start_line_has_no_roll_prefix(registry, tmp_path):
    app, _ = scene_app(registry, tmp_path)
    out = play(app, [TALK, "1", DESCEND])
    assert "Бой начался" in out.lines
    assert "[бросок] Бой начался" not in out.lines


def test_protocol_service_lines_are_not_printed(registry, tmp_path):
    app, _ = scene_app(registry, tmp_path)
    out = play(app, [TALK, "1", DESCEND])
    assert "Действие игрока" not in out.text
    assert "Варианты ответа предложены" not in out.text


def test_offer_choices_service_line_is_not_printed(registry, tmp_path):
    app = text_app(registry, tmp_path, [OFFER, text_step("Трактирщик косится.")])
    out = play(app, ["Здравствуйте"])
    assert "Варианты ответа предложены" not in out.text


# B5: дневной лимит при выключенном сессионном

def day_limited_app(registry, root, steps, day_limit_micro):
    app = text_app(registry, root, steps)
    app.settings.app.cost_limits.enabled = True
    app.settings.app.cost_limits.session_limit_micro = 0
    app.settings.app.cost_limits.day_limit_micro = day_limit_micro
    return app


def test_day_limit_pauses_when_session_limit_is_off(registry, tmp_path):
    app = day_limited_app(registry, tmp_path, [PAID, PAID], 1)
    out = play(app, ["Иду"])
    assert any("лимит" in line.lower() for line in out.lines)
    items = [text.lower() for _, text in numbered_lines(out.lines)]
    assert "продолж" in items[0]


def test_day_limit_warns_at_warn_percent(registry, tmp_path):
    nano = probe_nano(registry, tmp_path / "probe")
    app = day_limited_app(registry, tmp_path / "main", [PAID], nano // 900)
    out = play(app, ["Иду"])
    assert any("80%" in line for line in out.lines if "лимит" in line.lower())
    assert numbered_lines(out.lines) == []


def test_day_limit_zero_and_session_limit_zero_print_nothing(registry, tmp_path):
    app = day_limited_app(registry, tmp_path, [PAID], 0)
    out = play(app, ["Иду"])
    assert "лимит" not in out.text.lower()


def test_limit_state_takes_the_worse_of_session_and_day(registry, tmp_path):
    from ai_dm.ui.simple import limit_state

    app = limited_app(registry, tmp_path, [PAID], 10**9)
    app.settings.app.cost_limits.day_limit_micro = 1
    play(app, ["Иду"])
    assert limit_state(app) == "pause"


def test_day_limit_counts_spending_of_another_world(registry, tmp_path):
    # P14: траты соседнего мира за сегодня входят в дневной лимит
    from ai_dm.llm.cost import CostLedger
    from ai_dm.llm.types import Usage
    from ai_dm.ui.simple import limit_state

    app = day_limited_app(registry, tmp_path, [text_step()], 1)
    day = app.now().astimezone().date()
    CostLedger(tmp_path, "other-world").add(
        call_id="o-1", role="narrator", model="claude-opus-5-5", usage=Usage(input=1),
        cost_nano=5_000, day=day,
    )
    assert limit_state(app) == "pause"


# D3: лимит не открывается поверх другого меню

def test_limit_menu_is_not_opened_over_level_up_menu(registry, tmp_path):
    app = limited_app(registry, tmp_path, [PAID, PAID], 1)
    hero_of(app.bundle).sheet.xp = 300
    out = play(app, ["Иду"])
    assert app.pending == "level_up"
    assert [n for n, _ in numbered_lines(out.lines)] == [1, 2]
    assert "лимит" not in out.text.lower()


# D4: «Сохранить и выйти» из меню лимита

class DeadAfterLimitMenu:
    # первый ввод -- ход, второй -- «2» в меню лимита, но перед ним герой «погибает»
    def __init__(self, app):
        self.app = app
        self.lines = ["Иду", "2", "Ещё"]

    def read(self, prompt=""):
        if not self.lines:
            return None
        line = self.lines.pop(0)
        if line == "2":
            self.app.pending = "hero_dead"
        return line


def test_limit_menu_save_and_quit_is_refused_when_hero_is_dead(registry, tmp_path):
    from ai_dm.ui.simple import run

    app = limited_app(registry, tmp_path, [PAID, PAID], 1)
    source = DeadAfterLimitMenu(app)
    out = PlainOutput()
    run(app, source, out)
    assert "auto" not in list_slots(tmp_path, "vale-ui")
    assert "Сохранено." not in out.lines
    assert source.lines == []


def test_limit_menu_save_error_is_a_message_and_loop_goes_on(registry, tmp_path):
    app = limited_app(registry, tmp_path, [PAID, PAID], 1)

    def broken(slot):
        raise ValueError("диск полон")

    app.save_current = broken
    out, source = run_lines(app, ["Иду", "2", "Ещё"])
    assert "диск полон" in out.text
    assert "Сохранено." not in out.lines
    assert source.remaining == []


# D2: ошибка посреди хода в run()

def test_run_error_in_handle_is_printed_and_loop_goes_on(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step("После ошибки.")])
    original = app.handle
    calls = []

    def broken(line):
        calls.append(line)
        if len(calls) == 1:
            raise RuntimeError("сломалось")
        return original(line)

    app.handle = broken
    out = play(app, ["Первое", "Второе"])
    assert "Ошибка хода: сломалось" in out.text
    assert "После ошибки." in out.text
    assert app.bundle.session.turn_seq == 1


def test_run_error_in_replay_mode_returns_1(registry, tmp_path):
    from slots_kit import ScriptedInput

    from ai_dm.ui.simple import run

    app = text_app(registry, tmp_path, [text_step()])

    def broken(line):
        raise RuntimeError("сломалось")

    app.handle = broken
    source = ScriptedInput(["Первое", "Второе"])
    code = run(app, source, PlainOutput(), replay=True)
    assert code == 1
    assert source.remaining == ["Второе"]


# run с opening (Д1, A3): первый ход из opening, ввод не читается

def run_opening(app, lines, opening):
    from slots_kit import ScriptedInput

    from ai_dm.ui.simple import run

    out = PlainOutput()
    source = ScriptedInput(lines)
    run(app, source, out, opening=opening)
    return out, source


def test_run_opening_makes_first_turn_without_input(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step("Рассказ начала.")])
    out, _ = run_opening(app, [], "Начало.")
    assert app.bundle.session.turn_seq == 1
    assert "Рассказ начала." in out.text
    assert out.lines[-1] == "Сохранено: auto."


def test_run_opening_text_goes_to_first_request(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step("Рассказ начала.")])
    run_opening(app, [], "Начало.")
    assert state_of(app.adapter.requests[0])["player_input"] == "Начало."


def test_run_opening_then_reads_input(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step("Раз."), text_step("Два.")])
    _, source = run_opening(app, ["Иду"], "Начало.")
    assert app.bundle.session.turn_seq == 2
    assert source.remaining == []
    requests = app.adapter.requests
    assert state_of(requests[0])["player_input"] == "Начало."
    assert state_of(requests[1])["player_input"] == "Иду"


def test_run_without_opening_and_input_makes_no_turn(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    run_opening(app, [], None)
    assert app.bundle.session.turn_seq == 0
    assert app.adapter.requests == []


# run: приглашение ввода и секреты (старые выжившие мутанты run)

def test_run_reads_input_with_prompt(registry, tmp_path):
    from ai_dm.ui.simple import run

    class Source:
        def __init__(self):
            self.prompts = []

        def read(self, prompt=""):
            self.prompts.append(prompt)
            return None

    app = text_app(registry, tmp_path, [text_step()])
    source = Source()
    run(app, source, PlainOutput())
    assert source.prompts == ["> "]


def test_run_redacts_secrets_in_turn_failure(registry, tmp_path, monkeypatch):
    from slots_kit import ScriptedInput

    from ai_dm.ui.simple import run

    def broken(*args, **kwargs):
        raise RuntimeError("ключ sk-ant-secret-123 отклонён")

    app = text_app(registry, tmp_path, [text_step()])
    monkeypatch.setattr("ai_dm.ui.session.loot_snapshot", broken)
    out = PlainOutput()
    run(app, ScriptedInput(["Иду"]), out, secrets=("sk-ant-secret-123",))
    assert "sk-ant-secret-123" not in out.text
    assert "***" in out.text
