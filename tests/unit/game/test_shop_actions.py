# Выбор в /shop командой (BACKLOG 164, П1): ai_dm.game.shop_actions через GameApp.handle.
#   /shop услуга <npc> <услуга> [кол-во] · /shop купить <npc> <предмет> [кол-во] [junk|worn|used]
#   · /shop продать <npc> <предмет> [кол-во]; без аргумента -- текст /shop как был.
#   Движок вне хода мастера: тот же apply, что у инструментов service/trade (деньги, лимит
#   scene.trades, отказы, броски последствий); мастер не зовётся.
#   Принято/урезано -- строки лога (+ причина при урезании), заметка в inv_notes («оплатил услугу
#   «имя» xN у <npc.name> (сумма)», «купил ...», «продал ... <npc.name> ...»), автосейв; следующий
#   словесный ход несёт заметку префиксом ровно раз. Отказ/Invalid -- одна строка, без заметки
#   и сейва. Ошибка разбора -- USAGE. pending -- «Сначала нужно сделать выбор в меню.».
#   world.rng после сделки записывается обратно (меняется только если были броски).
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ui"))

import pytest  # noqa: E402
from game_kit import (  # noqa: E402
    ReactiveAdapter,
    make_app,
    script_then_react,
    start_combat_call,
    state_of,
    text_step,
    tools_step,
)
from protocol_kit import make_bundle  # noqa: E402
from ui_kit import build_app, text_app  # noqa: E402
from ui_kit import text_step as ui_text_step  # noqa: E402

from ai_dm.core.rng import Rng  # noqa: E402
from ai_dm.game.scene import hero_of  # noqa: E402
from ai_dm.game.shop_actions import USAGE, parse  # noqa: E402
from ai_dm.persistence.store import load_slot  # noqa: E402
from ai_dm.rules.inventory import add_item, count_item  # noqa: E402
from ai_dm.state.creature import AppliedCondition  # noqa: E402
from ai_dm.state.hero import InventoryEntry  # noqa: E402
from ai_dm.state.world import NPC, TradeProfile  # noqa: E402

FAR = 10**9
PREFIX = "Перед этим герой сам: "


def make_inn(registry, tmp_path, services=("ale", "room_modest", "bath"), app=None, **fields):
    app = app or text_app(registry, tmp_path, [ui_text_step()])
    hero = hero_of(app.bundle)
    fields.setdefault("location_id", hero.location_id)
    app.bundle.world.npcs["grok"] = NPC(
        id="grok", name="Грок", means=["трактир"], services=list(services), **fields
    )
    return app


def add_mara(app, stock=()):
    app.bundle.world.npcs["mara"] = NPC(
        id="mara", name="Мара", means=["товары"], location_id=hero_of(app.bundle).location_id,
        trade=TradeProfile(kind="general", purse_cp=5000, restock_at_s=FAR, stock=list(stock)),
    )


def merchant_app(registry, tmp_path, stock=()):
    app = text_app(registry, tmp_path, [ui_text_step()])
    hero = hero_of(app.bundle)
    hero.money_cp = 1000
    hero.inventory.clear()
    add_mara(app, stock)
    return app


def money(app):
    return hero_of(app.bundle).money_cp


def flat(reply):
    return " ".join(line.strip() for line in reply.lines)


# разбор и приглашение

def test_unknown_verb_gives_usage_and_changes_nothing(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    before = app.bundle.model_dump_json()
    assert app.handle("/shop чепуха").lines == [USAGE]
    assert app.bundle.model_dump_json() == before


def test_verb_without_an_item_gives_usage(registry, tmp_path):
    app = merchant_app(registry, tmp_path)
    assert app.handle("/shop купить mara").lines == [USAGE]


def test_extra_word_gives_usage(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    assert app.handle("/shop услуга grok ale 2 лишнее").lines == [USAGE]
    assert money(app) == 1400


def test_non_numeric_quantity_gives_usage(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    assert app.handle("/shop услуга grok ale много").lines == [USAGE]


def test_quality_is_not_accepted_for_a_service(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    assert app.handle("/shop услуга grok ale 1 used").lines == [USAGE]


def test_quality_is_not_accepted_for_a_sale(registry, tmp_path):
    app = merchant_app(registry, tmp_path)
    assert app.handle("/shop продать mara dagger 1 used").lines == [USAGE]


def test_unknown_quality_word_gives_usage(registry, tmp_path):
    app = merchant_app(registry, tmp_path)
    assert app.handle("/shop купить mara quiver 1 shiny").lines == [USAGE]


def test_parse_without_quality_gives_none():
    assert parse("купить mara quiver") == ("buy", "mara", "quiver", 1, None)


def test_verb_is_case_insensitive(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    app.handle("/shop УСЛУГА grok ale")
    assert app.bundle.session.current_scene.trades == 1


def test_waits_while_a_menu_choice_is_pending(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    app.pending = "level_up"
    reply = app.handle("/shop услуга grok ale")
    assert reply.lines == ["Сначала нужно сделать выбор в меню."]
    assert money(app) == 1400


def test_pending_is_checked_after_the_parse(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    app.pending = "level_up"
    assert app.handle("/shop чепуха").lines == [USAGE]


def test_shop_without_arguments_still_shows_the_text(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    assert app.handle("/shop").lines[0] == "Грок — услуги"


def test_help_does_not_break(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    assert app.handle("/help shop").lines


# услуги

def test_service_pays_and_logs(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    reply = app.handle("/shop услуга grok ale 2")
    assert reply.lines == ["Заказано: эль (кружка) x2 у Грок за 8 мм"]


def test_service_counts_one_scene_trade(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    app.handle("/shop услуга grok ale 2")
    assert app.bundle.session.current_scene.trades == 1


def test_service_note_for_the_narrator(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    app.handle("/shop услуга grok ale 2")
    assert app.inv_notes == ["оплатил услугу «эль (кружка)» x2 у Грок (8 мм)"]


def test_service_quantity_defaults_to_one(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    app.handle("/shop услуга grok room_modest")
    assert app.inv_notes == ["оплатил услугу «комната (скромная)» x1 у Грок (5 см)"]


def test_service_saves_the_autosave(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    app.handle("/shop услуга grok room_modest")
    saved = load_slot(tmp_path, "vale-ui", "auto")
    assert saved.heroes[0].money_cp == 1400 - 50


def test_service_does_not_call_the_narrator(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    app.handle("/shop услуга grok ale")
    assert app.adapter.requests == []


def test_service_does_not_move_the_clock(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    before = app.bundle.world.clock.now_s
    app.handle("/shop услуга grok room_modest")
    assert app.bundle.world.clock.now_s == before


def test_room_sets_the_lodging_flag(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    app.handle("/shop услуга grok room_modest")
    assert f"lodging:{hero_of(app.bundle).id}" in app.bundle.world.flags


def test_second_room_is_refused_without_note_or_charge(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    app.handle("/shop услуга grok room_modest")
    left = money(app)
    notes = list(app.inv_notes)
    reply = app.handle("/shop услуга grok room_modest")
    assert "ночлег уже оплачен" in flat(reply)
    assert money(app) == left
    assert app.inv_notes == notes


def test_clamped_service_logs_the_reason_and_notes_the_real_amount(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    reply = app.handle("/shop услуга grok ale 100")
    assert reply.lines[0].startswith("Заказано: эль (кружка) x20 у Грок")
    assert any("запрошено 100, оплачено 20" in line for line in reply.lines)
    assert app.inv_notes == ["оплатил услугу «эль (кружка)» x20 у Грок (8 см)"]


def test_bath_removes_smelly(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    hero = hero_of(app.bundle)
    hero.creature.conditions.append(AppliedCondition(id="smelly", source="test"))
    reply = app.handle("/shop услуга grok bath")
    assert not any(c.id == "smelly" for c in hero.creature.conditions)
    assert "вонь смыта" in flat(reply)


def test_companion_consequences_run_outside_the_master_turn(registry, tmp_path):
    app = make_inn(registry, tmp_path, services=("companion_cheap",))
    app.bundle.world.rng = Rng(1).state
    reply = app.handle("/shop услуга grok companion_cheap")
    hero = hero_of(app.bundle)
    assert any("Спасбросок Тел" in line for line in reply.lines)
    assert any(c.id == "diseased" for c in hero.creature.conditions)
    assert app.bundle.session.current_scene.trades == 1
    assert app.adapter.requests == []


# отказы движка

def test_refusing_npc_gives_the_reason_without_note_or_charge(registry, tmp_path):
    app = make_inn(registry, tmp_path, attitude=-60)
    reply = app.handle("/shop услуга grok ale")
    assert reply.lines == ["Грок отказывается торговать"]
    assert money(app) == 1400
    assert app.inv_notes == []


def test_refusal_does_not_save(registry, tmp_path):
    app = make_inn(registry, tmp_path, attitude=-60)
    app.handle("/shop услуга grok ale")
    with pytest.raises(FileNotFoundError):
        load_slot(tmp_path, "vale-ui", "auto")


def test_scene_trade_limit_is_a_refusal(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    app.bundle.session.current_scene.trades = app.runner.cfg.trade.ops_per_scene
    reply = app.handle("/shop услуга grok ale")
    assert reply.lines == ["лимит сделок за сцену: 20"]
    assert app.inv_notes == []
    assert money(app) == 1400


def test_no_money_is_a_refusal(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    hero_of(app.bundle).money_cp = 0
    reply = app.handle("/shop услуга grok room_modest")
    assert reply.lines[0].startswith("не хватает денег")
    assert app.inv_notes == []


def test_combat_refuses_with_a_message(registry, tmp_path):
    steps = [tools_step(start_combat_call(intent="kill")), text_step("Гоблины бросаются на вас.")]
    app = make_app(
        registry, tmp_path, script_then_react(steps), bundle=make_bundle(registry)
    )
    app.handle("Бью ногой дверь")
    make_inn(registry, tmp_path, app=app)
    reply = app.handle("/shop услуга grok ale")
    assert reply.lines == ["во время боя не торгуют"]
    assert app.inv_notes == []


def test_unknown_npc_is_a_message_not_an_exception(registry, tmp_path):
    app = merchant_app(registry, tmp_path)
    reply = app.handle("/shop купить nobody quiver")
    assert len(reply.lines) == 1
    assert app.inv_notes == []


def test_unknown_item_is_a_message_not_an_exception(registry, tmp_path):
    app = merchant_app(registry, tmp_path)
    reply = app.handle("/shop купить mara nope")
    assert len(reply.lines) == 1
    assert "nope" in reply.lines[0]
    assert app.inv_notes == []


def test_zero_quantity_is_an_invalid_message_without_note_or_save(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    reply = app.handle("/shop услуга grok ale 0")
    assert reply.lines == ["количество должно быть не меньше 1"]
    assert app.inv_notes == []
    assert money(app) == 1400
    with pytest.raises(FileNotFoundError):
        load_slot(tmp_path, "vale-ui", "auto")


def test_unknown_service_is_a_message(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    reply = app.handle("/shop услуга grok castle")
    assert len(reply.lines) == 1
    assert app.inv_notes == []


# товары

def test_buy_gives_the_item_and_takes_the_money(registry, tmp_path):
    app = merchant_app(registry, tmp_path)
    reply = app.handle("/shop купить mara quiver 2")
    hero = hero_of(app.bundle)
    assert count_item(hero, "quiver") == 2
    assert money(app) == 800
    assert reply.lines == ["Куплено: Колчан x2 за 2 зм"]


def test_buy_note_for_the_narrator(registry, tmp_path):
    app = merchant_app(registry, tmp_path)
    app.handle("/shop купить mara quiver 2")
    assert app.inv_notes == ["купил «Колчан» x2 у Мара (2 зм)"]


def test_buy_saves_the_autosave(registry, tmp_path):
    app = merchant_app(registry, tmp_path)
    app.handle("/shop купить mara quiver")
    assert load_slot(tmp_path, "vale-ui", "auto").heroes[0].money_cp == 900


def test_buy_counts_one_scene_trade(registry, tmp_path):
    app = merchant_app(registry, tmp_path)
    app.handle("/shop купить mara quiver")
    assert app.bundle.session.current_scene.trades == 1


def test_buy_quality_picks_the_stack_of_that_quality(registry, tmp_path):
    stock = [
        InventoryEntry(item_id="quiver", qty=1, cost_cp=100),
        InventoryEntry(item_id="quiver", qty=1, cost_cp=20, quality="junk"),
    ]
    app = merchant_app(registry, tmp_path, stock)
    app.handle("/shop купить mara quiver 1 junk")
    entries = [e for e in hero_of(app.bundle).inventory if e.item_id == "quiver"]
    assert [e.quality for e in entries] == ["junk"]
    assert money(app) == 1000 - 20


def test_buy_without_quality_does_not_force_one(registry, tmp_path):
    stock = [InventoryEntry(item_id="quiver", qty=1, cost_cp=100)]
    app = merchant_app(registry, tmp_path, stock)
    app.handle("/shop купить mara quiver")
    entries = [e for e in hero_of(app.bundle).inventory if e.item_id == "quiver"]
    assert [e.quality for e in entries] == [None]


def test_sell_moves_the_item_to_the_stock(registry, tmp_path):
    app = merchant_app(registry, tmp_path)
    hero = hero_of(app.bundle)
    add_item(hero, "dagger", cost_cp=200)
    reply = app.handle("/shop продать mara dagger")
    assert count_item(hero, "dagger") == 0
    assert any(e.item_id == "dagger" for e in app.bundle.world.npcs["mara"].trade.stock)
    assert money(app) > 1000
    assert reply.lines[0].startswith("Продано:")


def test_sell_note_for_the_narrator(registry, tmp_path):
    app = merchant_app(registry, tmp_path)
    add_item(hero_of(app.bundle), "dagger", cost_cp=200)
    app.handle("/shop продать mara dagger")
    assert app.inv_notes == ["продал «Кинжал» x1 Мара (1 зм)"]


def test_sell_of_a_worn_item_is_refused(registry, tmp_path):
    app = merchant_app(registry, tmp_path)
    hero = hero_of(app.bundle)
    add_item(hero, "dagger", cost_cp=200)
    hero.equipped.main_hand = "dagger"
    reply = app.handle("/shop продать mara dagger")
    assert "предмет надет" in flat(reply)
    assert app.inv_notes == []
    assert count_item(hero, "dagger") == 1


# состояние rng

def test_rng_state_is_written_back_after_rolls(registry, tmp_path):
    app = make_inn(registry, tmp_path, services=("companion_cheap",))
    before = app.bundle.world.rng.model_copy()
    app.handle("/shop услуга grok companion_cheap")
    assert app.bundle.world.rng != before


def test_rng_state_is_unchanged_without_rolls(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    before = app.bundle.world.rng.model_copy()
    app.handle("/shop услуга grok ale")
    assert app.bundle.world.rng == before


# заметка уходит мастеру

def test_next_word_turn_carries_the_note_exactly_once(registry, tmp_path):
    adapter = ReactiveAdapter()
    app = build_app(registry, tmp_path, adapter)
    make_inn(registry, tmp_path, app=app)
    app.handle("/shop услуга grok ale 2")
    app.handle("Пью")
    first = state_of(adapter.requests[0])["player_input"]
    assert first == f"({PREFIX}оплатил услугу «эль (кружка)» x2 у Грок (8 мм).) Пью"
    assert app.inv_notes == []
    app.handle("Ещё глоток")
    assert state_of(adapter.requests[-1])["player_input"] == "Ещё глоток"


def test_refused_deal_leaves_no_prefix(registry, tmp_path):
    adapter = ReactiveAdapter()
    app = build_app(registry, tmp_path, adapter)
    make_inn(registry, tmp_path, app=app, attitude=-60)
    app.handle("/shop услуга grok ale")
    app.handle("Пью")
    assert state_of(adapter.requests[0])["player_input"] == "Пью"
