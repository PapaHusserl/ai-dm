# Партия «Меню боя: сначала цель» (docs/plan-combat-menu.md, раздел 3 и 8, ответы В1-В7).
# Ожидаемое поведение (ТРЕБОВАНИЕ к коду):
#   в бою вместо панели #actions -- виджет CombatMenu (ai_dm.ui.tui.widgets): заголовок,
#   строка чипов целей
#   (TargetBar), строки меню «N. подпись» (1..9, затем 0); последняя строка -- «Ещё…»;
#   пустое поле ввода: 1-9/0 -- строка меню, Tab / Shift+Tab -- следующая / прошлая цель,
#   F3 -- оглушающий («Оглушающий: вкл» в заголовке), F4 -- «Ещё…» (MoreModal на весь экран:
#   OptionList с ПОЛНЫМ списком
#   вариантов, Esc закрывает без хода); клик по чипу цели и по строке -- то же, что клавиши;
#   непустое поле -- цифра и Tab идут в поле; busy -- клавиши меню не работают;
#   «цифра+Enter» в поле -- номер ВИДИМОЙ строки; эхо в ленту -- полный label варианта (с целью);
#   на виду всё доступное оружие по цели (В7), строк меню не больше 10 при любом числе врагов;
#   простой режим не меняется (плоская нумерация).
# Бой: Грей против 4 воинов-гоблинов (лук, гарпунный дротик, бросок подручного предмета).
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "game"))

from game_kit import script_then_react, start_combat_call, text_step, tools_step  # noqa: E402
from test_tui_spells import grey_game  # noqa: E402
from ui_kit import DESCEND, TALK, numbered_lines, play, scene_app  # noqa: E402

from ai_dm.ui.session import PlaySession  # noqa: E402
from ai_dm.ui.tui.app import AiDmApp  # noqa: E402

ROW = re.compile(r"^[│\s]*(\d)\.\s+(.*?)[\s│]*$")
LONGBOW = "Атака: композитный лук следопыта"
HARPOON = "Атака: гарпунный дротик с тросом"
THROWN = "Атака: бросок подручного предмета"
GOBLIN = "Воин-гоблин"
STONESKIN = "Выпить: Каменная Кожа"
MAX_ROWS = 10


def run(app, steps, size=(140, 40)):
    async def scenario():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            return await steps(app, pilot)

    return asyncio.run(scenario())


def goblins_game(cfg, tmp_path, count=4):
    call = start_combat_call()
    call["input"]["enemies"] = [
        {"ref": f"g{i}", "monster_id": "goblin_warrior", "zone": "hall", "group": "goblins"}
        for i in range(1, count + 1)
    ]
    steps = [tools_step(call), text_step("Гоблины бросаются на вас.")]
    return grey_game(cfg, tmp_path, script_then_react(steps))


def goblins_app(cfg, tmp_path, count=4):
    game = goblins_game(cfg, tmp_path, count)
    return AiDmApp(PlaySession(game)), game


async def start_fight(tui, app, pilot):
    await tui.submit(app, pilot, "Бью ногой дверь")
    assert app.game.bundle.session.active_combat is not None


def menu_lines(app):
    # строки экрана внутри области CombatMenu (без рамки по бокам)
    from ai_dm.ui.tui.widgets import CombatMenu

    menu = app.query_one(CombatMenu)
    region = menu.region
    rows = [strip.text for strip in app.screen._compositor.render_strips()]
    return [row[region.x:region.right] for row in rows[region.y:region.bottom]]


def menu_rows(app):
    # {номер: подпись} видимых строк меню
    result = {}
    for line in menu_lines(app):
        match = ROW.match(line)
        if match:
            result[int(match.group(1))] = match.group(2)
    return result


def row_key(app, text):
    # клавиша строки меню, в подписи которой есть text («0» -- десятая)
    for number, label in menu_rows(app).items():
        if text in label:
            return str(number)
    raise AssertionError(f"нет строки «{text}» в меню: {menu_rows(app)}")


def feed(tui, app):
    return tui.flat(tui.text_of(app.query_one("#feed")))


async def settle(app, pilot):
    await app.workers.wait_for_complete()
    await pilot.pause()


def more_labels(app):
    menu = app.screen.query_one("OptionList")
    return [tui_flat(str(menu.get_option_at_index(i).prompt)) for i in range(menu.option_count)]


def tui_flat(text):
    return " ".join(text.split())


def click_text(app, pilot, text, nth=0):
    # клик по nth-му (с нуля) вхождению text внутри CombatMenu
    from ai_dm.ui.tui.widgets import CombatMenu

    region = app.query_one(CombatMenu).region
    for dy, line in enumerate(menu_lines(app)):
        at = -1
        for _ in range(nth + 1):
            at = line.find(text, at + 1)
            if at < 0:
                break
        if at >= 0:
            return pilot.click(offset=(region.x + at, region.y + dy))
    raise AssertionError(f"нет «{text}» в меню")


# цифры: строки меню и цель по умолчанию

def test_digit_picks_attack_on_default_target_and_echoes_full_label(cfg, tmp_path, tui):
    app, game = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        key = row_key(app, LONGBOW)
        before = game.bundle.session.turn_seq
        await pilot.press(key)
        await settle(app, pilot)
        return key, before, game.bundle.session.turn_seq, feed(tui, app)

    key, before, after, text = run(app, steps)
    assert key == "1"
    assert after == before + 1
    assert f"▸ Ты: {LONGBOW} (осталось 20) → {GOBLIN} 1" in text


def test_shot_lowers_the_stock_in_the_next_menu(cfg, tmp_path, tui):
    app, game = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        before = [label for label in menu_rows(app).values() if LONGBOW in label]
        await pilot.press(row_key(app, LONGBOW))
        await settle(app, pilot)
        await pilot.press(row_key(app, "Закончить ход"))
        await settle(app, pilot)
        after = [label for label in menu_rows(app).values() if LONGBOW in label]
        return before, after

    before, after = run(app, steps)
    assert len(before) == 1 and "(осталось 20)" in before[0]
    assert len(after) == 1 and "(осталось 19)" in after[0]


def test_menu_replaces_flat_numbering_with_visible_rows(cfg, tmp_path, tui):
    app, game = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        return menu_rows(app)

    rows = run(app, steps)
    flat = len(game.runner.preview_turn())
    assert 1 < len(rows) <= MAX_ROWS
    assert len(rows) < flat
    assert sorted(rows) == list(range(1, len(rows) + 1)) or 0 in rows


def test_all_available_weapons_are_visible_for_target(cfg, tmp_path, tui):
    app, _ = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        return " | ".join(menu_rows(app).values())

    text = run(app, steps)
    for weapon in (LONGBOW, HARPOON, THROWN):
        assert weapon in text


def test_more_is_the_last_row(cfg, tmp_path, tui):
    app, _ = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        return menu_rows(app)

    rows = run(app, steps)
    order = [rows[n] for n in sorted(rows, key=lambda n: (n == 0, n))]
    assert "Ещё" in order[-1]
    assert not any("Ещё" in label for label in order[:-1])


# цель: Tab, Shift+Tab, клик

def test_tab_switches_target_and_digit_attacks_new_target(cfg, tmp_path, tui):
    app, _ = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        await pilot.press("tab")
        await pilot.pause()
        await pilot.press(row_key(app, LONGBOW))
        await settle(app, pilot)
        return feed(tui, app)

    text = run(app, steps)
    assert f"▸ Ты: {LONGBOW} (осталось 20) → {GOBLIN} 2" in text


def test_tab_keeps_focus_in_input(cfg, tmp_path, tui):
    app, _ = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        await pilot.press("tab")
        await pilot.pause()
        return app.query_one("#input").has_focus, app.query_one("#input").value

    assert run(app, steps) == (True, "")


def test_shift_tab_goes_back_around_the_circle(cfg, tmp_path, tui):
    app, _ = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        await pilot.press("shift+tab")
        await pilot.pause()
        await pilot.press(row_key(app, LONGBOW))
        await settle(app, pilot)
        return feed(tui, app), app.query_one("#input").has_focus

    text, focus = run(app, steps)
    assert f"▸ Ты: {LONGBOW} (осталось 20) → {GOBLIN} 4" in text
    assert focus is True


def test_tab_four_times_returns_to_first_target(cfg, tmp_path, tui):
    app, _ = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        for _ in range(4):
            await pilot.press("tab")
            await pilot.pause()
        await pilot.press(row_key(app, LONGBOW))
        await settle(app, pilot)
        return feed(tui, app)

    assert f"▸ Ты: {LONGBOW} (осталось 20) → {GOBLIN} 1" in run(app, steps)


def test_click_on_target_chip_switches_target(cfg, tmp_path, tui):
    # двое врагов: чипы влезают в строку целей, клик по чипу выбирает цель
    app, _ = goblins_app(cfg, tmp_path, count=2)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        await click_text(app, pilot, "[", nth=1)
        await pilot.pause()
        await pilot.press(row_key(app, LONGBOW))
        await settle(app, pilot)
        return feed(tui, app), app.query_one("#input").has_focus

    text, focus = run(app, steps)
    assert f"▸ Ты: {LONGBOW} (осталось 20) → {GOBLIN} 2" in text
    assert focus is True


def test_click_on_compact_target_line_switches_to_next_target(cfg, tmp_path, tui):
    # врагов много, чипы не влезают: «Цель: … Tab», клик по строке -- следующая цель
    app, _ = goblins_app(cfg, tmp_path, count=4)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        await click_text(app, pilot, "Цель:")
        await pilot.pause()
        await pilot.press(row_key(app, LONGBOW))
        await settle(app, pilot)
        return feed(tui, app)

    assert f"▸ Ты: {LONGBOW} (осталось 20) → {GOBLIN} 2" in run(app, steps)


def test_click_on_menu_row_makes_the_same_turn_as_digit(cfg, tmp_path, tui):
    app, game = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        before = game.bundle.session.turn_seq
        await click_text(app, pilot, HARPOON)
        await settle(app, pilot)
        return before, game.bundle.session.turn_seq, feed(tui, app)

    before, after, text = run(app, steps)
    assert after == before + 1
    assert f"▸ Ты: {HARPOON} → {GOBLIN} 1" in text


def test_chosen_target_is_kept_for_the_next_step_of_the_turn(cfg, tmp_path, tui):
    # R5: после шага хода (атака потратила действие) цель остаётся выбранной
    app, game = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        await pilot.press("tab")
        await pilot.press("tab")
        await pilot.pause()
        await pilot.press(row_key(app, LONGBOW))
        await settle(app, pilot)
        assert game.bundle.session.active_combat is not None
        return "\n".join(menu_lines(app))

    assert f"Цель: {GOBLIN} 3" in run(app, steps)


# оглушающий (F3)

def test_f3_toggles_nonlethal_in_header(cfg, tmp_path, tui):
    app, _ = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        before = "Оглушающий: вкл" in "\n".join(menu_lines(app))
        await pilot.press("f3")
        await pilot.pause()
        on = "Оглушающий: вкл" in "\n".join(menu_lines(app))
        await pilot.press("f3")
        await pilot.pause()
        off = "Оглушающий: вкл" in "\n".join(menu_lines(app))
        return before, on, off

    assert run(app, steps) == (False, True, False)


def test_f3_then_digit_sends_nonlethal_melee_attack(registry, tmp_path, tui):
    # Арн с мечом: строка атаки при F3 -- «Оглушающая атака»
    game, _ = scene_app(registry, tmp_path, hp=200)
    app = AiDmApp(PlaySession(game))

    async def steps(app, pilot):
        await tui.submit(app, pilot, TALK)
        await tui.submit(app, pilot, "1")
        await tui.submit(app, pilot, DESCEND)
        for _ in range(6):
            if any("Атака" in label for label in menu_rows(app).values()):
                break
            await pilot.press(row_key(app, "Идти"))
            await settle(app, pilot)
        await pilot.press("f3")
        await pilot.pause()
        await pilot.press(row_key(app, "Оглушающая атака"))
        await settle(app, pilot)
        return feed(tui, app)

    assert "▸ Ты: Оглушающая атака:" in run(app, steps)


def test_f3_does_nothing_with_text_in_input(cfg, tmp_path, tui):
    app, _ = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        app.query_one("#input").value = "стре"
        await pilot.press("f3")
        await pilot.pause()
        return app.query_one("#input").value

    assert run(app, steps) == "стре"


# «Ещё…»

def test_more_row_opens_full_screen_modal(cfg, tmp_path, tui):
    from ai_dm.ui.tui.modals import MoreModal

    app, _ = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        await pilot.press(row_key(app, "Ещё"))
        await pilot.pause()
        return len(app.screen_stack), isinstance(app.screen, MoreModal)

    assert run(app, steps) == (2, True)


def test_f4_opens_more_modal(cfg, tmp_path, tui):
    from ai_dm.ui.tui.modals import MoreModal

    app, _ = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        await pilot.press("f4")
        await pilot.pause()
        return len(app.screen_stack), isinstance(app.screen, MoreModal)

    assert run(app, steps) == (2, True)


def test_more_modal_choice_makes_the_turn(cfg, tmp_path, tui):
    app, game = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        before = game.bundle.session.turn_seq
        await pilot.press("f4")
        await pilot.pause()
        labels = more_labels(app)
        index = next(i for i, label in enumerate(labels) if STONESKIN in label)
        app.screen.query_one("OptionList").highlighted = index
        await pilot.pause()
        await pilot.press("enter")
        await settle(app, pilot)
        return before, game.bundle.session.turn_seq, feed(tui, app), len(app.screen_stack)

    before, after, text, depth = run(app, steps)
    assert depth == 1
    assert after == before + 1
    assert f"▸ Ты: {STONESKIN}" in text


def test_escape_closes_more_modal_without_turn_and_focus_returns_to_input(cfg, tmp_path, tui):
    app, game = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        before = game.bundle.session.turn_seq
        await pilot.press("f4")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        focus = app.query_one("#input").has_focus
        return before, game.bundle.session.turn_seq, len(app.screen_stack), focus

    before, after, depth, focus = run(app, steps)
    assert (after, depth, focus) == (before, 1, True)


def test_more_modal_lists_every_flat_option(cfg, tmp_path, tui):
    # страховка: любой вариант достижим за 2 нажатия («Ещё…» + выбор), даже скрытый из меню
    app, game = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        await pilot.press("f4")
        await pilot.pause()
        return " || ".join(more_labels(app))

    text = run(app, steps)
    for option in game.runner.preview_turn():
        if option.kind not in ("equip", "unequip"):
            assert tui_flat(option.label) in text, option.id


def test_more_modal_hides_the_equipment_swap_options(cfg, tmp_path, tui):
    # смена экипировки идёт только из окна inv: ни в меню, ни в «Ещё…» её нет
    app, game = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        await pilot.press("f4")
        await pilot.pause()
        return " || ".join(more_labels(app))

    text = run(app, steps)
    hidden = [o for o in game.runner.preview_turn() if o.kind in ("equip", "unequip")]
    assert hidden
    for option in hidden:
        assert tui_flat(option.label) not in text, option.id


def test_every_target_variant_is_visible_after_choosing_that_target(cfg, tmp_path, tui):
    # по каждой цели (Tab) в меню есть атака; переговоры -- если влезли
    app, game = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        seen = {}
        for number in range(1, 5):
            seen[number] = " | ".join(menu_rows(app).values())
            await pilot.press("tab")
            await pilot.pause()
        return seen

    seen = run(app, steps)
    for number, text in seen.items():
        assert LONGBOW in text, number


# поле ввода

def test_digit_goes_to_input_when_field_is_not_empty(cfg, tmp_path, tui):
    app, game = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        before = game.bundle.session.turn_seq
        app.query_one("#input").value = "стре"
        app.query_one("#input").cursor_position = 4
        await pilot.press("1")
        await pilot.pause()
        return before, game.bundle.session.turn_seq, app.query_one("#input").value

    before, after, value = run(app, steps)
    assert (after, value) == (before, "стре1")


def test_tab_does_not_switch_target_when_field_is_not_empty(cfg, tmp_path, tui):
    app, _ = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        app.query_one("#input").value = "стре"
        await pilot.press("tab")
        await pilot.pause()
        app.query_one("#input").value = ""
        await pilot.press(row_key(app, LONGBOW))
        await settle(app, pilot)
        return feed(tui, app)

    assert f"▸ Ты: {LONGBOW} (осталось 20) → {GOBLIN} 1" in run(app, steps)


def test_typed_digit_and_enter_is_visible_row_number(cfg, tmp_path, tui):
    app, game = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        label = menu_rows(app)[3]
        await tui.submit(app, pilot, "3")
        return label, feed(tui, app), game.bundle.session.turn_seq

    label, text, _ = run(app, steps)
    start = label.rstrip("…")[:20]
    assert f"▸ Ты: {start}" in text


def test_menu_keys_are_off_while_busy(cfg, tmp_path, tui):
    app, game = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        before = game.bundle.session.turn_seq
        app.busy = True
        for key in ("1", "tab", "f3", "f4"):
            await pilot.press(key)
        await pilot.pause()
        depth = len(app.screen_stack)
        app.busy = False
        return before, game.bundle.session.turn_seq, depth

    before, after, depth = run(app, steps)
    assert (after, depth) == (before, 1)


# размеры

def numbered_count(app):
    return len(menu_rows(app))


def test_menu_has_at_most_ten_rows_with_many_enemies_wide(cfg, tmp_path, tui):
    app, _ = goblins_app(cfg, tmp_path, count=5)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)

        combat = app.query_one("#combat")
        return numbered_count(app), tui.shown(combat), combat.region.height

    rows, combat, map_height = run(app, steps, (120, 40))
    assert 1 < rows <= MAX_ROWS
    assert combat is True
    assert map_height >= 3


def test_menu_has_at_most_ten_rows_in_80x24_and_lines_do_not_overflow(cfg, tmp_path, tui):
    app, _ = goblins_app(cfg, tmp_path, count=5)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        await pilot.press("f2")
        await pilot.pause()
        from ai_dm.ui.tui.widgets import CombatMenu

        menu = app.query_one(CombatMenu)
        lines = menu_lines(app)
        return (
            numbered_count(app), menu.region.width, [len(line.rstrip()) for line in lines],
            tui.shown(app.query_one("#combat")),
        )

    rows, width, widths, combat = run(app, steps, (80, 24))
    assert 1 < rows <= MAX_ROWS
    assert max(widths) <= width
    assert combat is True


def test_menu_rows_are_numbered_in_order_in_80x24(cfg, tmp_path, tui):
    app, _ = goblins_app(cfg, tmp_path, count=5)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        await pilot.press("f2")
        await pilot.pause()
        return menu_rows(app)

    rows = run(app, steps, (80, 24))
    assert rows[1].startswith(LONGBOW[:20])


def test_number_beyond_menu_does_not_start_a_turn_and_says_so(cfg, tmp_path, tui):
    app, game = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        before = game.bundle.session.turn_seq
        await tui.submit(app, pilot, "12")
        return before, game.bundle.session.turn_seq, feed(tui, app)

    before, after, text = run(app, steps)
    assert after == before
    assert "Нет такой строки" in text


def test_zero_key_is_the_tenth_row(cfg, tmp_path, tui):
    app, game = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        rows = menu_rows(app)
        before = game.bundle.session.turn_seq
        await pilot.press("0")
        await pilot.pause()
        return rows, before, game.bundle.session.turn_seq, len(app.screen_stack)

    rows, before, after, depth = run(app, steps)
    assert "Ещё" in rows[0]
    # десятая строка -- «Ещё…»: модалка, не ход
    assert (after, depth) == (before, 2)


def test_zero_plus_enter_in_field_is_the_tenth_row(cfg, tmp_path, tui):
    app, game = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        before = game.bundle.session.turn_seq
        app.query_one("#input").value = "0"
        await pilot.press("enter")
        await pilot.pause()
        return before, game.bundle.session.turn_seq, len(app.screen_stack)

    before, after, depth = run(app, steps)
    assert (after, depth) == (before, 2)


def test_f3_marks_ranged_attack_as_not_stunning(cfg, tmp_path, tui):
    app, _ = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        before = menu_rows(app)
        await pilot.press("f3")
        await pilot.pause()
        return before, menu_rows(app)

    before, rows = run(app, steps)
    # подпись с пометкой «(дальнобойным — не оглушить)»; длинная обрезается «…»
    assert rows[1] != before[1]
    assert rows[1].startswith(before[1][:20])
    assert "(" in rows[1]


def test_arrows_group_expands_lists_arrows_and_escape_returns(cfg, tmp_path, tui):
    app, _ = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        before = menu_rows(app)
        await pilot.press(row_key(app, "Стрелы ▸"))
        await pilot.pause()
        opened = menu_rows(app)
        await pilot.press("escape")
        await pilot.pause()
        return before, opened, menu_rows(app)

    before, opened, after = run(app, steps)
    assert before[2] == "Стрелы ▸"
    assert opened[1] == "← Назад"
    assert len(opened) == 5 and "осталось" in opened[2]
    assert after == before


def test_arrow_digit_in_group_makes_turn_and_echoes_full_label(cfg, tmp_path, tui):
    app, game = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        await pilot.press(row_key(app, "Стрелы ▸"))
        await pilot.pause()
        before = game.bundle.session.turn_seq
        await pilot.press("2")
        await settle(app, pilot)
        return before, game.bundle.session.turn_seq, feed(tui, app)

    before, after, text = run(app, steps)
    assert after == before + 1
    assert f"▸ Ты: {LONGBOW} — " in text
    assert "(осталось" in text and f"→ {GOBLIN} 1" in text


def test_more_modal_digits_pick_options_one_to_nine(cfg, tmp_path, tui):
    app, game = goblins_app(cfg, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        before = game.bundle.session.turn_seq
        await pilot.press("f4")
        await pilot.pause()
        labels = more_labels(app)
        await pilot.press("1")
        await settle(app, pilot)
        return labels, before, game.bundle.session.turn_seq, len(app.screen_stack)

    labels, before, after, depth = run(app, steps)
    assert (after, depth) == (before + 1, 1)
    assert any(label.lstrip().startswith("1.") for label in labels)


# простой режим не меняется

def test_simple_mode_keeps_flat_numbering_in_combat(cfg, tmp_path):
    game = goblins_game(cfg, tmp_path)
    out = play(game, ["Бью ногой дверь"])
    flat = [
        option.label for option in game.runner.preview_turn()
        if option.kind not in ("equip", "unequip")
    ]
    shown = numbered_lines(out.lines)[-len(flat):]
    assert [number for number, _ in shown] == list(range(1, len(flat) + 1))
    assert [text[:30] for _, text in shown] == [label[:30] for label in flat]
    assert "F3" not in out.text
    assert "Ещё…" not in out.text
