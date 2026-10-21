# 96а П2: окно /inv в TUI (InvModal): список предметов героя, описание выделенного, действия
# клавишами e/l/u/d и Enter (первое действие); выбор -- подкоманда /inv, ход игры, эхо в ленте.
# Герой -- воин из protocol_kit: кольчуга, щит, длинный меч надеты; копьё, лук и прочее в рюкзаке.
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "game"))

from game_kit import (  # noqa: E402
    ReactiveAdapter,
    make_app,
    script_then_react,
    start_combat_call,
    text_step,
    tools_step,
)
from protocol_kit import make_bundle  # noqa: E402

from ai_dm.content.models.common import EffectSpec  # noqa: E402
from ai_dm.rules.inventory import add_item, find_item  # noqa: E402
from ai_dm.ui.session import PlaySession  # noqa: E402
from ai_dm.ui.tui.app import AiDmApp  # noqa: E402
from ai_dm.ui.tui.blocks import inv_actions_of, inv_rows  # noqa: E402
from ai_dm.ui.tui.modals import InvModal, TextModal  # noqa: E402

ERROR = "Ошибка хода"


def run(app, steps, size=(140, 40)):
    async def scenario():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            return await steps(app, pilot)

    return asyncio.run(scenario())


def feed(tui, app):
    return tui.flat(tui.text_of(app.query_one("#feed")))


def hero_game(registry, tmp_path, *items, steps=None):
    bundle = make_bundle(registry)
    for item in items:
        add_item(bundle.heroes[0], item, cost_cp=0)
    adapter = ReactiveAdapter() if steps is None else script_then_react(steps)
    return make_app(registry, tmp_path, adapter, bundle=bundle)


def inv_app(registry, tmp_path, *items):
    game = hero_game(registry, tmp_path, *items)
    return AiDmApp(PlaySession(game)), game


def fight_app(registry, tmp_path, *items):
    steps = [tools_step(start_combat_call(intent="kill")), text_step("Гоблины бросаются на вас.")]
    game = hero_game(registry, tmp_path, *items, steps=steps)
    return AiDmApp(PlaySession(game)), game


def equipped(game):
    return game.bundle.heroes[0].equipped


def labels(game):
    return [row[0] for row in inv_rows(game)]


def row_of(game, label):
    return next(row for row in inv_rows(game) if row[0] == label)


def option_texts(app):
    menu = app.screen.query_one("#inv-list")
    return [str(menu.get_option_at_index(i).prompt) for i in range(menu.option_count)]


def description(tui, app):
    return tui.flat(str(app.screen.query_one("#inv-description").render()))


async def open_inv(tui, app, pilot):
    await tui.submit(app, pilot, "/inv")


async def highlight(app, pilot, label):
    # стрелками вниз до строки с подписью
    start = app.screen.query_one("#inv-list").highlighted
    for _ in range(len(app.screen.rows)):
        if label in option_texts(app)[app.screen.query_one("#inv-list").highlighted]:
            return
        await pilot.press("down")
        await pilot.pause()
    raise AssertionError(f"нет строки {label} (старт {start})")


async def finish(app, pilot):
    await app.workers.wait_for_complete()
    await pilot.pause()


# inv_rows

def test_rows_mark_worn_items_with_a_star(registry, tmp_path):
    game = hero_game(registry, tmp_path)
    assert "★ Щит" in labels(game)
    assert "★ Кольчуга" in labels(game)
    assert "Копьё" in labels(game)


def test_rows_show_quantity_of_a_stack(registry, tmp_path):
    game = hero_game(registry, tmp_path)
    add_item(game.bundle.heroes[0], "potion_of_healing", 2, cost_cp=0)
    assert "Зелье лечения x2" in labels(game)


def test_rows_single_item_has_no_quantity_suffix(registry, tmp_path):
    game = hero_game(registry, tmp_path, "dagger")
    assert "Кинжал" in labels(game)


def test_row_description_comes_from_the_item(registry, tmp_path):
    game = hero_game(registry, tmp_path)
    assert row_of(game, "★ Щит")[1] == "Бонус +2 к КД."


def test_row_of_unknown_item_id_keeps_the_id_without_actions(registry, tmp_path):
    game = hero_game(registry, tmp_path)
    game.bundle.heroes[0].inventory.append(
        type(game.bundle.heroes[0].inventory[0])(item_id="ghost_item", qty=1, cost_cp=0)
    )
    assert ("ghost_item", "", []) in inv_rows(game)


def test_unworn_weapon_offers_equip_and_left_hand(registry, tmp_path):
    game = hero_game(registry, tmp_path)
    actions = row_of(game, "Копьё")[2]
    assert actions == [
        ("e", "Надеть", "/inv надеть spear", "Надеть: Копьё"),
        ("l", "В левую руку", "/inv надеть spear левая", "В левую руку: Копьё"),
    ]


def test_worn_weapon_offers_unequip_and_left_hand_only(registry, tmp_path):
    game = hero_game(registry, tmp_path)
    keys = [a[0] for a in row_of(game, "★ Длинный меч")[2]]
    assert keys == ["u", "l"]
    assert row_of(game, "★ Длинный меч")[2][0][2] == "/inv снять правая"


def test_worn_shield_and_armor_offer_only_unequip_outside_combat(registry, tmp_path):
    game = hero_game(registry, tmp_path)
    assert row_of(game, "★ Щит")[2] == [("u", "Снять", "/inv снять щит", "Снять: Щит")]
    assert row_of(game, "★ Кольчуга")[2] == [("u", "Снять", "/inv снять доспех", "Снять: Кольчуга")]


def test_potion_offers_drink(registry, tmp_path):
    game = hero_game(registry, tmp_path, "potion_of_healing")
    assert row_of(game, "Зелье лечения")[2] == [
        ("d", "Выпить", "/inv выпить potion_of_healing", "Выпить: Зелье лечения")
    ]


def test_plain_gear_has_no_actions(registry, tmp_path):
    game = hero_game(registry, tmp_path)
    assert row_of(game, "Колчан")[2] == []


def test_armor_in_pack_offers_equip(registry, tmp_path):
    game = hero_game(registry, tmp_path, "leather_armor")
    game.bundle.heroes[0].equipped.armor = None
    actions = next(row[2] for row in inv_rows(game) if "Кожан" in row[0])
    assert [a[0] for a in actions] == ["e"]
    assert actions[0][2] == "/inv надеть leather_armor"


def test_shield_in_pack_offers_equip_when_slot_is_free(registry, tmp_path):
    game = hero_game(registry, tmp_path)
    game.handle("/inv снять щит")
    assert row_of(game, "Щит")[2] == [("e", "Надеть", "/inv надеть shield", "Надеть: Щит")]


def test_rows_in_combat_hide_armor_and_potions(registry, tmp_path, tui):
    app, game = fight_app(registry, tmp_path, "potion_of_healing")

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Бью ногой дверь")
        return game.bundle.session.active_combat is not None

    assert run(app, steps) is True
    assert row_of(game, "★ Кольчуга")[2] == []
    assert row_of(game, "Зелье лечения")[2] == []
    assert row_of(game, "★ Щит")[2][0][0] == "u"
    assert [a[0] for a in row_of(game, "Копьё")[2]] == ["e"]


def test_potion_in_combat_points_to_the_combat_menu(registry, tmp_path, tui):
    app, game = fight_app(registry, tmp_path, "potion_of_healing")

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Бью ногой дверь")

    run(app, steps)
    assert "В бою — меню, пункт «Использовать»." in row_of(game, "Зелье лечения")[1]


def test_plain_gear_description_says_no_actions(registry, tmp_path):
    game = hero_game(registry, tmp_path)
    assert row_of(game, "Колчан")[1] == "Действий нет."


def test_potion_in_combat_description_joins_text_and_note_with_blank_line(registry, tmp_path, tui):
    app, game = fight_app(registry, tmp_path, "potion_of_healing")

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Бью ногой дверь")

    run(app, steps)
    expected = (
        "Выпить зелье — бонусное действие; восстанавливает 2d4 + 2 хит-пойнта."
        "\n\nВ бою — меню, пункт «Использовать»."
    )
    assert row_of(game, "Зелье лечения")[1] == expected


def test_plain_gear_in_combat_does_not_get_potion_note(registry, tmp_path, tui):
    app, game = fight_app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Бью ногой дверь")

    run(app, steps)
    assert row_of(game, "Колчан")[1] == "Действий нет."


def test_description_falls_back_to_effect_texts(registry, tmp_path):
    base = registry.get("item", "potion_of_healing")
    stone = base.model_copy(
        update={
            "id": "glow_stone",
            "name": "Светящийся камень",
            "description": "",
            "effects": [EffectSpec(type="ac_bonus", value=1)],
        }
    )
    game = hero_game(registry.with_items({"item": [stone]}), tmp_path, "glow_stone")
    assert row_of(game, "Светящийся камень")[1].startswith("+1 КД")


def test_inv_actions_of_in_combat_drops_armor_unequip(registry, tmp_path, tui):
    app, game = fight_app(registry, tmp_path)
    found = find_item(registry, "chain_mail")

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Бью ногой дверь")

    assert inv_actions_of(game, "chain_mail", found, ["armor"])[0][0] == "u"
    run(app, steps)
    assert game.bundle.session.active_combat is not None
    assert inv_actions_of(game, "chain_mail", found, ["armor"]) == []


def test_off_hand_item_offers_r_to_unequip_left(registry, tmp_path):
    game = hero_game(registry, tmp_path, "dagger")
    game.handle("/inv снять щит")
    game.handle("/inv надеть кинжал левая")
    assert equipped(game).off_hand == "dagger"
    actions = row_of(game, "★ Кинжал")[2]
    assert ("r", "Снять из левой руки", "/inv снять левая", "Снять: Кинжал") in actions
    assert "u" not in [a[0] for a in actions]


def test_weapon_in_left_hand_offers_no_second_left_hand_equip(registry, tmp_path):
    game = hero_game(registry, tmp_path, "dagger")
    game.handle("/inv снять щит")
    game.handle("/inv надеть кинжал левая")
    assert [a[0] for a in row_of(game, "★ Кинжал")[2]] == ["r", "e"]


def test_r_key_takes_weapon_out_of_left_hand(registry, tmp_path, tui):
    app, game = inv_app(registry, tmp_path, "dagger")
    game.handle("/inv снять щит")
    game.handle("/inv надеть кинжал левая")

    async def steps(app, pilot):
        await open_inv(tui, app, pilot)
        await highlight(app, pilot, "★ Кинжал")
        await pilot.press("r")
        await finish(app, pilot)
        return feed(tui, app)

    text = run(app, steps)
    assert equipped(game).off_hand is None
    assert "▸ Ты: Снять: Кинжал" in text


def test_in_combat_blocked_left_hand_and_shield_are_not_offered(registry, tmp_path, tui):
    # щит надет -- в левую руку не положить; план: недоступное окно не предлагает
    app, game = fight_app(registry, tmp_path, "dagger")

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Бью ногой дверь")

    run(app, steps)
    assert "l" not in [a[0] for a in row_of(game, "Кинжал")[2]]
    assert "l" not in [a[0] for a in row_of(game, "Копьё")[2]]
    assert "l" not in [a[0] for a in row_of(game, "★ Длинный меч")[2]]


# окно

def test_inv_opens_window_with_numbered_items(registry, tmp_path, tui):
    app, game = inv_app(registry, tmp_path)

    async def steps(app, pilot):
        await open_inv(tui, app, pilot)
        return len(app.screen_stack), isinstance(app.screen, InvModal), option_texts(app)

    depth, is_inv, texts = run(app, steps)
    assert (depth, is_inv) == (2, True)
    assert texts[0] == f"1. {labels(game)[0]}"
    assert len(texts) == len(labels(game))


def test_inv_window_shows_description_of_highlighted_item(registry, tmp_path, tui):
    app, _ = inv_app(registry, tmp_path)

    async def steps(app, pilot):
        await open_inv(tui, app, pilot)
        await highlight(app, pilot, "★ Щит")
        return description(tui, app)

    text = run(app, steps)
    assert "Бонус +2 к КД." in text
    assert "u — Снять" in text


def test_inv_window_says_no_actions_for_plain_gear(registry, tmp_path, tui):
    app, _ = inv_app(registry, tmp_path)

    async def steps(app, pilot):
        await open_inv(tui, app, pilot)
        await highlight(app, pilot, "Колчан")
        return description(tui, app)

    assert "Действий нет." in run(app, steps)


def test_enter_on_unworn_weapon_equips_it_and_closes_window(registry, tmp_path, tui):
    app, game = inv_app(registry, tmp_path)

    async def steps(app, pilot):
        await open_inv(tui, app, pilot)
        await highlight(app, pilot, "Копьё")
        await pilot.press("enter")
        await finish(app, pilot)
        return len(app.screen_stack), feed(tui, app), app.query_one("#input").has_focus

    depth, text, _ = run(app, steps)
    assert depth == 1
    assert "▸ Ты: Надеть: Копьё" in text
    assert ERROR not in text
    assert equipped(game).main_hand == "spear"


def test_enter_on_unequipped_shield_puts_it_on(registry, tmp_path, tui):
    # образец из плана: /inv -> окно, Enter на щите -> надет
    app, game = inv_app(registry, tmp_path)
    game.handle("/inv снять щит")
    assert equipped(game).shield is None

    async def steps(app, pilot):
        await open_inv(tui, app, pilot)
        await highlight(app, pilot, "Щит")
        await pilot.press("enter")
        await finish(app, pilot)
        return feed(tui, app)

    text = run(app, steps)
    assert equipped(game).shield == "shield"
    assert "▸ Ты: Надеть: Щит" in text


def test_u_key_takes_off_highlighted_item(registry, tmp_path, tui):
    app, game = inv_app(registry, tmp_path)

    async def steps(app, pilot):
        await open_inv(tui, app, pilot)
        await highlight(app, pilot, "★ Щит")
        await pilot.press("u")
        await finish(app, pilot)
        return len(app.screen_stack), feed(tui, app)

    depth, text = run(app, steps)
    assert depth == 1
    assert equipped(game).shield is None
    assert "▸ Ты: Снять: Щит" in text


def test_l_key_puts_weapon_in_left_hand(registry, tmp_path, tui):
    app, game = inv_app(registry, tmp_path, "dagger")

    async def steps(app, pilot):
        await open_inv(tui, app, pilot)
        await highlight(app, pilot, "Кинжал")
        await pilot.press("l")
        await finish(app, pilot)

    run(app, steps)
    assert equipped(game).off_hand == "dagger"


def test_d_key_drinks_potion(registry, tmp_path, tui):
    app, game = inv_app(registry, tmp_path, "potion_of_healing")
    hero = game.bundle.heroes[0]
    hero.creature.hp_current = 1

    async def steps(app, pilot):
        await open_inv(tui, app, pilot)
        await highlight(app, pilot, "Зелье лечения")
        await pilot.press("d")
        await finish(app, pilot)
        return feed(tui, app)

    text = run(app, steps)
    assert "▸ Ты: Выпить: Зелье лечения" in text
    assert hero.creature.hp_current > 1


def test_key_without_such_action_keeps_window_open(registry, tmp_path, tui):
    app, game = inv_app(registry, tmp_path)

    async def steps(app, pilot):
        await open_inv(tui, app, pilot)
        await highlight(app, pilot, "Колчан")
        before = game.bundle.session.turn_seq
        await pilot.press("d")
        await pilot.press("e")
        await pilot.pause()
        return len(app.screen_stack), before, game.bundle.session.turn_seq

    depth, before, after = run(app, steps)
    assert depth == 2
    assert after == before


def test_enter_on_item_without_actions_keeps_window_open(registry, tmp_path, tui):
    app, game = inv_app(registry, tmp_path)

    async def steps(app, pilot):
        await open_inv(tui, app, pilot)
        await highlight(app, pilot, "Колчан")
        before = game.bundle.session.turn_seq
        await pilot.press("enter")
        await pilot.pause()
        return len(app.screen_stack), before, game.bundle.session.turn_seq

    depth, before, after = run(app, steps)
    assert depth == 2
    assert after == before


def test_escape_closes_window_without_turn(registry, tmp_path, tui):
    app, game = inv_app(registry, tmp_path)

    async def steps(app, pilot):
        await open_inv(tui, app, pilot)
        before = game.bundle.session.turn_seq
        await pilot.press("escape")
        await pilot.pause()
        return (
            len(app.screen_stack), feed(tui, app), before, game.bundle.session.turn_seq,
            app.query_one("#input").has_focus,
        )

    depth, text, before, after, focus = run(app, steps)
    assert depth == 1
    assert "Надеть" not in text
    assert after == before
    assert focus is True


# /inv с аргументами и пустой инвентарь

def test_inv_with_arguments_goes_to_feed_without_window(registry, tmp_path, tui):
    app, game = inv_app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/inv снять щит")
        return len(app.screen_stack), feed(tui, app)

    depth, text = run(app, steps)
    assert depth == 1
    assert equipped(game).shield is None
    assert "Щит" in text


def test_empty_inventory_stays_a_plain_text_window(registry, tmp_path, tui):
    app, game = inv_app(registry, tmp_path)
    game.bundle.heroes[0].inventory.clear()

    async def steps(app, pilot):
        await open_inv(tui, app, pilot)
        return len(app.screen_stack), type(app.screen)

    depth, kind = run(app, steps)
    assert depth == 2
    assert kind is TextModal


# is_game_line

@pytest.mark.parametrize(
    ("line", "expected"),
    [("/inv", False), ("/inv надеть копьё", False), ("/sheet", False), ("Иду", True)],
)
def test_inv_line_outside_combat(registry, tmp_path, line, expected):
    app, _ = inv_app(registry, tmp_path)
    assert app.is_game_line(line) is expected


@pytest.mark.parametrize(("line", "expected"), [("/inv", False), ("/inv надеть копьё", True)])
def test_inv_line_in_combat(registry, tmp_path, tui, line, expected):
    app, game = fight_app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Бью ногой дверь")
        assert game.bundle.session.active_combat is not None
        return app.is_game_line(line)

    assert run(app, steps) is expected


def test_window_choice_in_combat_is_a_turn_step(registry, tmp_path, tui):
    app, game = fight_app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Бью ногой дверь")
        await open_inv(tui, app, pilot)
        assert isinstance(app.screen, InvModal)
        await highlight(app, pilot, "Копьё")
        before = game.bundle.session.turn_seq
        await pilot.press("e")
        await finish(app, pilot)
        return len(app.screen_stack), feed(tui, app), before, game.bundle.session.turn_seq

    depth, text, before, after = run(app, steps)
    assert depth == 1
    assert "▸ Ты: Надеть: Копьё" in text
    assert ERROR not in text
    assert equipped(game).main_hand == "spear"
    assert after > before


def test_refused_inv_line_in_combat_keeps_combat_menu(registry, tmp_path, tui):
    # щит надет -- «в левую руку» отказ без хода; боевое меню на месте
    app, game = fight_app(registry, tmp_path, "dagger")

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Бью ногой дверь")
        before = game.bundle.session.turn_seq
        await tui.submit(app, pilot, "/inv надеть dagger левая")
        return (
            before, game.bundle.session.turn_seq, app.query_one("#actions").display,
            feed(tui, app),
        )

    before, after, shown, text = run(app, steps)
    assert equipped(game).off_hand is None
    assert after == before
    assert "Сначала сними" in text
    assert shown is True


def test_combat_menu_stays_after_choice_in_combat(registry, tmp_path, tui):
    app, game = fight_app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Бью ногой дверь")
        before = app.query_one("#actions").display
        await open_inv(tui, app, pilot)
        await highlight(app, pilot, "Копьё")
        await pilot.press("e")
        await finish(app, pilot)
        return before, app.query_one("#actions").display, feed(tui, app)

    before, shown, text = run(app, steps)
    assert before is True
    assert shown is True, text
    assert equipped(game).main_hand == "spear"
