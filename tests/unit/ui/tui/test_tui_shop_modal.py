# 164 П2: окно /shop в TUI (ShopModal, NpcModal, QtyModal) -- Pilot-тесты.
#   /shop без аргументов: один торговец или NPC с услугами -- сразу ShopModal; несколько --
#   NpcModal (цифра, Enter или Esc), затем ShopModal выбранного; никого, бой, отказ всех --
#   справочная TextModal.
#   Enter на строке: cap <= 1 -- сразу сделка (эхо «<глагол>: <имя> (<NPC>)», команда ... 1);
#   иначе QtyModal: целое 1..cap -- сделка с эхом «... xN»; 0, больше cap, пусто -- окно остаётся;
#   Esc -- снова ShopModal того же NPC. Enter в QtyModal не уходит в поле ввода хода.
#   Мастер не зовётся: сделка идёт командой движка.
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "game"))

from game_kit import (  # noqa: E402
    make_app,
    script_then_react,
    start_combat_call,
    text_step,
    tools_step,
)
from protocol_kit import make_bundle  # noqa: E402
from ui_kit import text_app  # noqa: E402
from ui_kit import text_step as ui_text_step  # noqa: E402

from ai_dm.game.scene import hero_of  # noqa: E402
from ai_dm.rules.money import format_cp  # noqa: E402
from ai_dm.state.hero import InventoryEntry  # noqa: E402
from ai_dm.state.world import NPC, TradeProfile  # noqa: E402
from ai_dm.ui.session import PlaySession  # noqa: E402
from ai_dm.ui.tui import strings  # noqa: E402
from ai_dm.ui.tui.app import MODALS, AiDmApp  # noqa: E402
from ai_dm.ui.tui.modals import NpcModal, QtyModal, ShopModal, TextModal  # noqa: E402

FAR = 10**9
MINUS = "−"


def run(app, steps, size=(140, 40)):
    async def scenario():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            return await steps(app, pilot)

    return asyncio.run(scenario())


def put_inn(game, services=("ale", "room_modest", "bath")):
    game.bundle.world.npcs["grok"] = NPC(
        id="grok", name="Грок", means=["трактир"], services=list(services),
        location_id=hero_of(game.bundle).location_id,
    )


def put_mara(game, **fields):
    game.bundle.world.npcs["mara"] = NPC(
        id="mara", name="Мара", means=["товары"], location_id=hero_of(game.bundle).location_id,
        trade=TradeProfile(kind="general", purse_cp=5000, restock_at_s=FAR), **fields,
    )


def shop_game(registry, tmp_path, inn=True, mara=False, money=1400, **mara_fields):
    game = text_app(registry, tmp_path, [ui_text_step()])
    hero = hero_of(game.bundle)
    hero.money_cp = money
    hero.inventory.clear()
    if inn:
        put_inn(game)
    if mara:
        put_mara(game, **mara_fields)
    return game


def money(game):
    return hero_of(game.bundle).money_cp


def feed(tui, app):
    return tui.flat(tui.text_of(app.query_one("#feed")))


def option_texts(app, list_id="#inv-list"):
    menu = app.screen.query_one(list_id)
    return [str(menu.get_option_at_index(i).prompt) for i in range(menu.option_count)]


async def choose(app, pilot, prefix):
    # вкладка со строкой -> стрелки вниз до неё -> Enter
    for _ in range(len(app.screen.tabs)):
        if any(row[0].startswith(prefix) for row in app.screen.rows):
            break
        await pilot.press("right")
        await pilot.pause()
    index = next(i for i, row in enumerate(app.screen.rows) if row[0].startswith(prefix))
    for _ in range(index):
        await pilot.press("down")
        await pilot.pause()
    await pilot.press("enter")
    await app.workers.wait_for_complete()
    await pilot.pause()


async def open_shop(tui, app, pilot):
    await tui.submit(app, pilot, "/shop")


async def enter_qty(app, pilot, value):
    app.screen.query_one("#qty-input").value = value
    await pilot.press("enter")
    await app.workers.wait_for_complete()
    await pilot.pause()


def new_app(game):
    return AiDmApp(PlaySession(game))


# какое окно открывается

def test_only_services_npc_opens_shop_window_with_services_tab(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        return (
            isinstance(app.screen, ShopModal), [name for name, _ in app.screen.tabs],
            option_texts(app),
        )

    window, tabs, texts = run(new_app(game), steps)
    assert window is True
    assert tabs == ["Услуги"]
    assert texts[0] == "1. эль (кружка) — 4 мм / порция"


def test_two_npcs_open_the_choice_window(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path, mara=True)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        title = app.screen.query_one("#modal").border_title
        return isinstance(app.screen, NpcModal), title, option_texts(app, "#npc-list")

    is_npc, title, texts = run(new_app(game), steps)
    assert is_npc is True
    assert title == "Торговля"
    assert texts == [
        "1. Мара (general) — кошелёк торговца: 50 зм",
        "2. Грок — услуги",
    ]


def test_npc_window_shows_its_hint(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path, mara=True)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        return tui.flat(str(app.screen.query_one("#npc-title").render()))

    assert run(new_app(game), steps) == strings.SHOP_NPC_PICK


def test_digit_two_opens_the_second_npc_window(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path, mara=True)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        await pilot.press("2")
        await pilot.pause()
        return isinstance(app.screen, ShopModal), [row[2][0][2] for row in app.screen.rows]

    window, commands = run(new_app(game), steps)
    assert window is True
    assert all("grok" in command for command in commands)


def test_digit_one_opens_the_first_npc_window(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path, mara=True)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        await pilot.press("1")
        await pilot.pause()
        return isinstance(app.screen, ShopModal), app.screen.rows[0][2][0][2]

    window, command = run(new_app(game), steps)
    assert window is True
    assert "mara" in command


def test_enter_in_npc_window_opens_the_highlighted_npc(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path, mara=True)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()
        return isinstance(app.screen, ShopModal), app.screen.rows[0][2][0][2]

    window, command = run(new_app(game), steps)
    assert window is True
    assert "grok" in command


def test_digit_above_the_list_is_ignored_in_npc_window(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path, mara=True)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        await pilot.press("3")
        await pilot.pause()
        return isinstance(app.screen, NpcModal)

    assert run(new_app(game), steps) is True


def test_escape_in_npc_window_returns_to_input_without_a_turn(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path, mara=True)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        await pilot.press("escape")
        await pilot.pause()
        return len(app.screen_stack), app.focused.id

    assert run(new_app(game), steps) == (1, "input")
    assert game.adapter.requests == []


def test_escape_in_shop_window_returns_to_input_without_a_turn(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        await pilot.press("escape")
        await pilot.pause()
        return len(app.screen_stack), app.focused.id

    assert run(new_app(game), steps) == (1, "input")
    assert game.adapter.requests == []


def test_nobody_to_trade_with_keeps_text_modal(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path, inn=False)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        return isinstance(app.screen, TextModal)

    assert run(new_app(game), steps) is True


def test_everybody_refusing_keeps_text_modal_with_the_refusal(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path, inn=False, mara=True, attitude=-100)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        return isinstance(app.screen, TextModal), tui.flat(tui.visible_text(app))

    is_text, text = run(new_app(game), steps)
    assert is_text is True
    assert "отказывается торговать" in text


def test_refusing_npc_is_not_offered_next_to_a_willing_one(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path, mara=True, attitude=-100)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        return isinstance(app.screen, ShopModal), [row[2][0][2] for row in app.screen.rows]

    window, commands = run(new_app(game), steps)
    assert window is True
    assert all("grok" in command for command in commands)


def test_shop_in_combat_keeps_text_modal(registry, tmp_path, tui):
    steps_script = [tools_step(start_combat_call(intent="kill")), text_step("Гоблины.")]
    game = make_app(
        registry, tmp_path, script_then_react(steps_script), bundle=make_bundle(registry)
    )
    put_inn(game)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Бью ногой дверь")
        assert game.bundle.session.active_combat is not None
        await open_shop(tui, app, pilot)
        return isinstance(app.screen, TextModal), app.can_shop()

    assert run(new_app(game), steps) == (True, False)


def test_can_shop_true_with_a_provider(registry, tmp_path):
    assert new_app(shop_game(registry, tmp_path)).can_shop() is True


def test_can_shop_false_without_providers(registry, tmp_path):
    assert new_app(shop_game(registry, tmp_path, inn=False)).can_shop() is False


def test_can_shop_false_while_a_menu_is_pending(registry, tmp_path):
    game = shop_game(registry, tmp_path)
    game.pending = "level_up"
    assert new_app(game).can_shop() is False


def test_can_shop_false_during_the_limit_menu(registry, tmp_path):
    app = new_app(shop_game(registry, tmp_path))
    app.session.limit_menu = True
    assert app.can_shop() is False


def test_can_shop_false_when_all_refuse(registry, tmp_path):
    game = shop_game(registry, tmp_path, inn=False, mara=True, attitude=-100)
    assert new_app(game).can_shop() is False


def test_shop_targets_skip_refusing_npcs(registry, tmp_path):
    game = shop_game(registry, tmp_path, mara=True, attitude=-100)
    assert [npc.id for npc in new_app(game).shop_targets()] == ["grok"]


def test_shop_targets_list_merchants_before_providers(registry, tmp_path):
    game = shop_game(registry, tmp_path, mara=True)
    assert [npc.id for npc in new_app(game).shop_targets()] == ["mara", "grok"]


def test_new_windows_are_in_modals():
    assert ShopModal in MODALS and NpcModal in MODALS and QtyModal in MODALS


def test_shop_window_bindings_are_only_escape_and_arrows():
    keys = {binding.key for binding in ShopModal.BINDINGS}
    assert keys == {"escape", "left", "right"}


def test_digit_over_npc_window_does_not_reach_the_combat_menu(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path, mara=True)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        return isinstance(app.screen, MODALS), app.menu_ready()

    assert run(new_app(game), steps) == (True, False)


# вкладки и описание

def test_arrows_switch_between_goods_and_services_tabs(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path, inn=False, mara=True, services=["room_modest"])

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        first = str(app.screen.query_one("#inv-tabs").active_tab.label)
        await pilot.press("right")
        await pilot.pause()
        second = str(app.screen.query_one("#inv-tabs").active_tab.label)
        await pilot.press("left")
        await pilot.pause()
        return first, second, str(app.screen.query_one("#inv-tabs").active_tab.label)

    assert run(new_app(game), steps) == ("Снаряжение", "Услуги", "Снаряжение")


def test_description_shows_the_kind_description_and_the_hint(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path)
    desc = game.settings.rules.services.kinds["room_modest"].description

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        first = tui.flat(str(app.screen.query_one("#inv-description").render()))
        await pilot.press("down")
        await pilot.pause()
        return first, tui.flat(str(app.screen.query_one("#inv-description").render()))

    first, second = run(new_app(game), steps)
    assert desc
    assert first == "Enter — Оплатить"
    assert second == f"{desc} Enter — Оплатить"


def test_inventory_letter_keys_do_nothing_in_shop_window(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        for key in ("e", "l", "u", "r", "d"):
            await pilot.press(key)
        await pilot.pause()
        return isinstance(app.screen, ShopModal), len(app.screen_stack)

    assert run(new_app(game), steps) == (True, 2)
    assert game.adapter.requests == []
    assert money(game) == 1400


# сделка без вопроса о количестве

def test_room_has_no_quantity_question_and_is_paid(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        await choose(app, pilot, "комната")
        return len(app.screen_stack), feed(tui, app), tui.flat(tui.text_of(app.query_one("#gains")))

    depth, text, gains = run(new_app(game), steps)
    assert depth == 1
    assert "▸ Ты: Оплатить: комната (скромная) (Грок)" in text
    assert "x1" not in text
    assert "Ночлег оплачен: комната (скромная)" in text
    assert f"Потрачено: {MINUS}5 см" in gains
    assert money(game) == 1400 - 50
    assert game.adapter.requests == []


def test_unaffordable_item_goes_straight_to_the_engine_refusal(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path, money=0)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        await choose(app, pilot, "эль")
        return len(app.screen_stack), feed(tui, app)

    depth, text = run(new_app(game), steps)
    assert depth == 1
    assert "▸ Ты: Оплатить: эль (кружка) (Грок)" in text
    assert "не хватает денег" in text
    assert money(game) == 0


def test_purchase_of_one_item_without_quantity_question(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path, inn=False, mara=True, money=100)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        await choose(app, pilot, "Колчан")
        return len(app.screen_stack), feed(tui, app)

    depth, text = run(new_app(game), steps)
    assert depth == 1
    assert "▸ Ты: Купить: Колчан (Мара)" in text
    assert money(game) == 0
    assert [e.item_id for e in hero_of(game.bundle).inventory] == ["quiver"]


def test_purchase_without_quantity_question_takes_exactly_one_unit(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path, inn=False, mara=True, money=250)
    game.bundle.world.npcs["mara"].trade.stock.append(
        InventoryEntry(item_id="quiver", qty=1, cost_cp=100)
    )

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        await choose(app, pilot, "Колчан — 1 зм")

    run(new_app(game), steps)
    assert [(e.item_id, e.qty) for e in hero_of(game.bundle).inventory] == [("quiver", 1)]
    assert money(game) == 150


def test_cap_one_by_money_sends_the_command_with_quantity_one(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path, inn=False, mara=True, money=100)
    app = new_app(game)
    sent = []

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        app.start_turn = sent.append
        await choose(app, pilot, "Колчан")

    run(app, steps)
    assert sent == ["/shop купить mara quiver 1"]


# вопрос о количестве

def test_item_with_cap_above_one_opens_quantity_window(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        await choose(app, pilot, "эль")
        screen = app.screen
        title = screen.query_one("#modal").border_title
        hint = tui.flat(str(screen.query_one("#qty-title").render()))
        value = screen.query_one("#qty-input").value
        return isinstance(screen, QtyModal), title, hint, value, app.focused.id

    is_qty, title, hint, value, focus = run(new_app(game), steps)
    assert is_qty is True
    assert title == "Торговля"
    assert hint == "Оплатить: эль (кружка) (Грок) " + strings.SHOP_QTY.format(cap=20)
    assert (value, focus) == ("1", "qty-input")
    assert money(game) == 1400


def test_quantity_three_pays_three_units_with_echo(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        await choose(app, pilot, "эль")
        await enter_qty(app, pilot, "3")
        return len(app.screen_stack), feed(tui, app), tui.flat(tui.text_of(app.query_one("#gains")))

    depth, text, gains = run(new_app(game), steps)
    assert depth == 1
    assert "▸ Ты: Оплатить: эль (кружка) (Грок) x3" in text
    assert "Заказано: эль (кружка) x3" in text
    assert f"Потрачено: {MINUS}1 см 2 мм" in gains
    assert money(game) == 1400 - 12
    assert game.adapter.requests == []


def test_default_quantity_is_one(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        await choose(app, pilot, "эль")
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()
        return len(app.screen_stack)

    assert run(new_app(game), steps) == 1
    assert money(game) == 1400 - 4


def test_quantity_equal_to_cap_is_accepted(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path, money=10)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        await choose(app, pilot, "эль")
        await enter_qty(app, pilot, "2")
        return len(app.screen_stack)

    assert run(new_app(game), steps) == 1
    assert money(game) == 2


def test_sale_asks_for_quantity_by_free_instances(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path, inn=False, mara=True)
    from ai_dm.rules.inventory import add_item

    add_item(hero_of(game.bundle), "quiver", 3, cost_cp=100)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        await choose(app, pilot, "Колчан x3")
        asked = isinstance(app.screen, QtyModal)
        await enter_qty(app, pilot, "2")
        return asked, feed(tui, app)

    asked, text = run(new_app(game), steps)
    assert asked is True
    assert "▸ Ты: Продать: Колчан (Мара) x2" in text
    assert money(game) == 1400 + 2 * 50
    assert hero_of(game.bundle).inventory[0].qty == 1


def test_purchase_with_quantity_gives_items(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path, inn=False, mara=True)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        await choose(app, pilot, "Колчан")
        await enter_qty(app, pilot, "2")
        return feed(tui, app)

    text = run(new_app(game), steps)
    assert "▸ Ты: Купить: Колчан (Мара) x2" in text
    assert hero_of(game.bundle).inventory[0].qty == 2
    assert money(game) == 1200


def test_invalid_quantities_keep_the_window_open(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        await choose(app, pilot, "эль")
        states = []
        for value in ("0", "21", "99", ""):
            await enter_qty(app, pilot, value)
            states.append(isinstance(app.screen, QtyModal))
        return states, feed(tui, app), app.query_one("#input").value

    states, text, typed = run(new_app(game), steps)
    assert states == [True, True, True, True]
    assert text.count("▸ Ты:") == 1
    assert "99" not in text
    assert typed == ""
    assert money(game) == 1400
    assert game.adapter.requests == []


def test_non_numeric_quantity_keeps_the_window_open(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        await choose(app, pilot, "эль")
        await enter_qty(app, pilot, "-3")
        return isinstance(app.screen, QtyModal)

    assert run(new_app(game), steps) is True
    assert money(game) == 1400


def test_enter_in_quantity_window_does_not_start_a_turn_from_the_input(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        await choose(app, pilot, "эль")
        await enter_qty(app, pilot, "5")
        return feed(tui, app)

    text = run(new_app(game), steps)
    assert "Ты: 5" not in text
    assert "Ты: Оплатить: эль (кружка) (Грок) x5" in text
    assert text.count("▸ Ты:") == 2
    assert game.adapter.requests == []


def test_escape_in_quantity_window_returns_to_the_same_shop_window(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path, mara=True)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        await pilot.press("2")
        await pilot.pause()
        await choose(app, pilot, "эль")
        assert isinstance(app.screen, QtyModal)
        await pilot.press("escape")
        await pilot.pause()
        return (
            isinstance(app.screen, ShopModal), len(app.screen_stack),
            [row[2][0][2] for row in app.screen.rows], feed(tui, app),
        )

    window, depth, commands, text = run(new_app(game), steps)
    assert (window, depth) == (True, 2)
    assert all("grok" in command for command in commands)
    assert text.count("▸ Ты:") == 1
    assert money(game) == 1400
    assert game.adapter.requests == []


def test_escape_twice_after_quantity_closes_everything(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        await choose(app, pilot, "эль")
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        return len(app.screen_stack), app.focused.id

    assert run(new_app(game), steps) == (1, "input")


# ввод строкой с аргументами и сама модалка

def test_typed_shop_command_with_arguments_goes_to_the_feed_without_window(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/shop услуга grok ale 2")
        return len(app.screen_stack), feed(tui, app), tui.flat(tui.text_of(app.query_one("#gains")))

    depth, text, gains = run(new_app(game), steps)
    assert depth == 1
    assert "Заказано: эль (кружка) x2" in text
    assert f"Потрачено: {MINUS}8 мм" in gains
    assert money(game) == 1400 - 8


def test_shop_command_with_one_argument_goes_to_the_feed_without_window(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/shop услуга")
        return len(app.screen_stack)

    assert run(new_app(game), steps) == 1


def test_model_command_with_one_argument_goes_to_the_feed_without_window(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/model world")
        return len(app.screen_stack)

    assert run(new_app(game), steps) == 1


def test_npc_window_shows_the_preset_purse_of_a_due_restock(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path, mara=True)
    game.bundle.world.npcs["mara"].trade.restock_at_s = 0
    preset_purse = game.settings.rules.trade.presets["general"].purse_cp

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        return option_texts(app, "#npc-list")[0]

    purse = format_cp(preset_purse)
    assert run(new_app(game), steps) == f"1. Мара (general) — кошелёк торговца: {purse}"


def test_description_joins_several_action_hints_with_a_dot(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path)
    actions = [("Enter", "Купить", "x", "e", 1), ("k", "Иначе", "y", "e", 1)]
    tabs = [("Товары", [("Лот", "Описание", actions, "Товары")])]

    async def steps(app, pilot):
        app.push_screen(ShopModal("Торговля", tabs))
        await pilot.pause()
        return tui.flat(str(app.screen.query_one("#inv-description").render()))

    assert run(new_app(game), steps) == "Описание Enter — Купить · k — Иначе"


def test_quantity_input_ignores_letters(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path)

    async def steps(app, pilot):
        await open_shop(tui, app, pilot)
        await choose(app, pilot, "эль")
        await pilot.press("a", "b")
        await pilot.pause()
        return app.screen.query_one("#qty-input").value

    assert run(new_app(game), steps) == "1"


def test_quantity_window_dismisses_with_number_by_itself(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path)
    results = []

    async def steps(app, pilot):
        app.push_screen(QtyModal("Торговля", "Эль", 5), results.append)
        await pilot.pause()
        await enter_qty(app, pilot, "5")
        return len(app.screen_stack)

    assert run(new_app(game), steps) == 1
    assert results == [5]


def test_quantity_window_above_cap_gives_nothing(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path)
    results = []

    async def steps(app, pilot):
        app.push_screen(QtyModal("Торговля", "Эль", 5), results.append)
        await pilot.pause()
        await enter_qty(app, pilot, "6")
        return isinstance(app.screen, QtyModal)

    assert run(new_app(game), steps) is True
    assert results == []


def test_quantity_window_lowest_value_is_one(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path)
    results = []

    async def steps(app, pilot):
        app.push_screen(QtyModal("Торговля", "Эль", 5), results.append)
        await pilot.pause()
        await enter_qty(app, pilot, "1")
        return len(app.screen_stack)

    assert run(new_app(game), steps) == 1
    assert results == [1]


def test_quantity_window_escape_gives_none(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path)
    results = []

    async def steps(app, pilot):
        app.push_screen(QtyModal("Торговля", "Эль", 5), results.append)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

    run(new_app(game), steps)
    assert results == [None]


def test_npc_window_selection_by_arrow_and_enter_returns_the_npc_id(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path)
    results = []

    async def steps(app, pilot):
        rows = [("mara", "Мара"), ("grok", "Грок")]
        app.push_screen(NpcModal("Торговля", rows), results.append)
        await pilot.pause()
        await pilot.press("down", "enter")
        await pilot.pause()

    run(new_app(game), steps)
    assert results == ["grok"]


def test_npc_window_escape_gives_none(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path)
    results = []

    async def steps(app, pilot):
        app.push_screen(NpcModal("Торговля", [("mara", "Мара")]), results.append)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

    run(new_app(game), steps)
    assert results == [None]


def test_npc_window_digit_gives_id_of_that_row(registry, tmp_path, tui):
    game = shop_game(registry, tmp_path)
    results = []

    async def steps(app, pilot):
        rows = [("mara", "Мара"), ("grok", "Грок"), ("liss", "Лисса")]
        app.push_screen(NpcModal("Торговля", rows), results.append)
        await pilot.pause()
        await pilot.press("3")
        await pilot.pause()

    run(new_app(game), steps)
    assert results == ["liss"]
