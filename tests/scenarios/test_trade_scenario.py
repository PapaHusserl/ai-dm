# Сквозной сценарий партии Т3 (docs/TRADE-PLAN.md, «Тесты» Т3): «продаю трофеи Маре» на мок-LLM.
# Мир «Вейл», у героя два трофейных скимитара (стек junk по 100 мм), в локации героя торговец Мара
# (пресет general, кошелёк 5000 мм). Мок-мастер за ход делает два вызова trade sell и рассказывает:
#   * контекст первого запроса мастера: scene_npcs[mara].merchant == "general", ключ trade с Марой;
#   * деньги героя выросли на 2 x 50 мм, трофеи ушли, кошелёк Мары уменьшился, скимитары в stock;
#   * в строках хода (turn.lines) две строки «Продано».
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "game"))

from game_kit import OPUS, SAVED_AT, make_app, settings, state_of  # noqa: E402
from slots_kit import WORLD_TEXT  # noqa: E402

from ai_dm.game.scene import hero_of  # noqa: E402
from ai_dm.game.starter import new_world  # noqa: E402
from ai_dm.llm.mock import ScriptedAdapter  # noqa: E402
from ai_dm.rules.inventory import add_item, count_item  # noqa: E402
from ai_dm.state.world import NPC, TradeProfile  # noqa: E402

SELL = "Продаю трофеи Маре"


def sell_call(call_id):
    return {
        "id": call_id, "name": "trade",
        "input": {
            "type": "trade", "npc_id": "mara", "direction": "sell", "item_id": "scimitar",
            "qty": 1, "quality": "any",
        },
    }


def trade_story(registry, root, purse=5000):
    bundle = new_world(
        registry, settings().rules, hero="arn", seed=7, world_id="vale-trade", saved_at=SAVED_AT
    )
    hero = bundle.heroes[0]
    bundle.world.npcs["mara"] = NPC(
        id="mara", name="Мара", means=["товары"], location_id=hero.location_id,
        trade=TradeProfile(kind="general", purse_cp=purse, restock_at_s=10**9),
    )
    add_item(hero, "scimitar", 2, cost_cp=100, quality="junk")
    steps = [
        {"tool_calls": [sell_call("tr-1"), sell_call("tr-2")]},
        {"text": "Мара пересчитывает монеты и убирает клинки под прилавок."},
    ]
    adapter = ScriptedAdapter(steps, provider="anthropic", model=OPUS)
    app = make_app(registry, root, adapter, bundle=bundle, world_text=WORLD_TEXT, model=OPUS)
    money = hero.money_cp
    reply = app.handle(SELL)
    return app, adapter, reply, money


def test_turn_is_committed(registry, tmp_path):
    _, _, reply, _ = trade_story(registry, tmp_path)
    assert reply.turn.committed is True
    assert reply.turn.requests == ["trade", "trade"]


def test_context_marks_mara_as_merchant(registry, tmp_path):
    _, adapter, _, _ = trade_story(registry, tmp_path)
    state = state_of(adapter.requests[0])
    mara = [n for n in state["scene_npcs"] if n["id"] == "mara"][0]
    assert mara["merchant"] == "general"


def test_context_has_trade_key_with_mara(registry, tmp_path):
    _, adapter, _, _ = trade_story(registry, tmp_path)
    trade = state_of(adapter.requests[0])["trade"]
    assert [t["npc_id"] for t in trade] == ["mara"]
    assert trade[0]["purse_cp"] == 5000


def test_money_grows_by_two_quotes(registry, tmp_path):
    app, _, _, before = trade_story(registry, tmp_path)
    assert hero_of(app.bundle).money_cp == before + 100


def test_trophies_leave_the_hero(registry, tmp_path):
    app, _, _, _ = trade_story(registry, tmp_path)
    assert count_item(hero_of(app.bundle), "scimitar") == 0


def test_merchant_purse_shrinks_and_stock_grows(registry, tmp_path):
    app, _, _, _ = trade_story(registry, tmp_path)
    profile = app.bundle.world.npcs["mara"].trade
    assert profile.purse_cp == 4900
    assert sum(e.qty for e in profile.stock if e.item_id == "scimitar") == 2


def test_log_has_two_sold_lines(registry, tmp_path):
    _, _, reply, _ = trade_story(registry, tmp_path)
    sold = [line for line in reply.turn.lines if line.startswith("Продано")]
    assert len(sold) == 2


def test_next_turn_context_has_the_sold_stock_first(registry, tmp_path):
    app, adapter, _, _ = trade_story(registry, tmp_path)
    adapter.steps.append({"text": "Мара ждёт."})
    app.handle("Смотрю на прилавок")
    state = state_of(adapter.requests[-1])
    assert state["trade"][0]["stock"][0] == {
        "item_id": "scimitar", "price_cp": 100, "quality": "junk"
    }
    assert state["trade"][0]["purse_cp"] == 4900


def test_purse_too_small_clamps_the_second_sale(registry, tmp_path):
    app, _, reply, before = trade_story(registry, tmp_path, purse=50)
    assert hero_of(app.bundle).money_cp == before + 50
    assert count_item(hero_of(app.bundle), "scimitar") == 1



# торг Убеждением (партия Т5): «игрок торгуется» -> haggle -> trade buy по цене с поправкой.
# Бросок идёт на сидированном rng мира, поэтому исход не фиксирован: проверяем связь исхода с ценой.

HAGGLE = "Давай скинь цену, я хороший покупатель"


def haggle_call(call_id):
    return {
        "id": call_id, "name": "haggle", "input": {"type": "haggle", "npc_id": "mara"},
    }


def buy_call(call_id):
    return {
        "id": call_id, "name": "trade",
        "input": {
            "type": "trade", "npc_id": "mara", "direction": "buy", "item_id": "arrows",
            "qty": 1, "quality": "any",
        },
    }


def haggle_story(registry, root, extra_calls=()):
    bundle = new_world(
        registry, settings().rules, hero="arn", seed=7, world_id="vale-haggle", saved_at=SAVED_AT
    )
    hero = bundle.heroes[0]
    bundle.world.npcs["mara"] = NPC(
        id="mara", name="Мара", means=["товары"], location_id=hero.location_id,
        trade=TradeProfile(kind="general", purse_cp=5000, restock_at_s=10**9),
    )
    steps = [
        {"tool_calls": [haggle_call("hg-1"), buy_call("hg-2"), *extra_calls]},
        {"text": "Мара хмыкает и называет цену."},
    ]
    adapter = ScriptedAdapter(steps, provider="anthropic", model=OPUS)
    app = make_app(registry, root, adapter, bundle=bundle, world_text=WORLD_TEXT, model=OPUS)
    money = hero.money_cp
    reply = app.handle(HAGGLE)
    return app, adapter, reply, money


def test_haggle_turn_is_committed(registry, tmp_path):
    _, _, reply, _ = haggle_story(registry, tmp_path)
    assert reply.turn.committed is True
    assert reply.turn.requests == ["haggle", "trade"]


def test_haggle_is_written_to_the_merchant_profile(registry, tmp_path):
    app, _, _, _ = haggle_story(registry, tmp_path)
    profile = app.bundle.world.npcs["mara"].trade
    assert profile.haggle_percent in (-20, -10, 10)
    assert profile.haggle_day == app.bundle.world.clock.now_s // 86400


def test_purchase_price_follows_the_haggle_outcome(registry, tmp_path):
    app, _, _, before = haggle_story(registry, tmp_path)
    percent = app.bundle.world.npcs["mara"].trade.haggle_percent
    assert before - hero_of(app.bundle).money_cp == 100 * (100 + percent) // 100


def test_second_haggle_in_the_same_turn_is_refused(registry, tmp_path):
    app, _, reply, _ = haggle_story(registry, tmp_path, extra_calls=[haggle_call("hg-3")])
    profile = app.bundle.world.npcs["mara"].trade
    first = profile.haggle_percent
    assert reply.turn.requests == ["haggle", "trade"]
    assert profile.haggle_percent == first


def test_next_context_shows_the_haggle_key(registry, tmp_path):
    app, adapter, _, _ = haggle_story(registry, tmp_path)
    adapter.steps.append({"text": "Мара ждёт."})
    app.handle("Смотрю на прилавок")
    merchant = state_of(adapter.requests[-1])["trade"][0]
    assert merchant["haggle"] == {"percent": app.bundle.world.npcs["mara"].trade.haggle_percent}


def test_first_context_has_no_haggle_key(registry, tmp_path):
    _, adapter, _, _ = haggle_story(registry, tmp_path)
    assert "haggle" not in state_of(adapter.requests[0])["trade"][0]
