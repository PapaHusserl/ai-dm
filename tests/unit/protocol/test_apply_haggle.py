# Торговля, партия Т5 (docs/TRADE-PLAN.md, «Т5: план»): инструмент haggle{npc_id}.
#   Движок сам берёт СЛ (15, при attitude >= 50 -- 10) и бросает Убеждение героя; при attitude < 0
#   помеха. Успех -10%, успех с запасом >= 5 -- -20%, провал +10% на цены ПОКУПКИ героем до конца
#   игрового дня; один торг в день на торговца независимо от исхода (повтор -> rejected без броска).
#   Результат {roll_ref, outcome, dc, total, haggle_percent, until}. Проверки как у trade:
#   бой -> Invalid in_combat, нет NPC/не торговец/мёртвый -> Invalid, attitude <= -50 -> rejected.
#   Торг не тратит scene.trades. trade list/buy берут цену с поправкой, sell -- прежнюю.
import pytest
from protocol_kit import ScriptedRng, combat_request, dump, make_ctx, req

from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.rules.derived import skill_bonus
from ai_dm.rules.trade import DAY_S
from ai_dm.state.hero import InventoryEntry
from ai_dm.state.world import NPC, TradeProfile

FAR = 10**9


def haggle_ctx(registry, cfg, rolls, money=1000, stock=None, **fields):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=rolls))
    ctx.hero.money_cp = money
    fields.setdefault("location_id", "vale")
    ctx.bundle.world.npcs["mara"] = NPC(
        id="mara", name="Mara", means=["товары"],
        trade=TradeProfile(kind="general", purse_cp=5000, restock_at_s=FAR, stock=stock or []),
        **fields,
    )
    return ctx


def face_for(ctx, total):
    # грань d20, дающая нужную сумму Убеждения героя
    return total - skill_bonus(ctx.hero, ctx.registry, "persuasion")


def total_ctx(registry, cfg, total, **fields):
    # контекст, где единственный бросок даст сумму total
    probe = haggle_ctx(registry, cfg, [10])
    return haggle_ctx(registry, cfg, [face_for(probe, total)], **fields)


def haggle(ctx, npc_id="mara"):
    return apply(ctx, req("haggle", npc_id=npc_id))


def merchant(ctx):
    return ctx.bundle.world.npcs["mara"].trade


def buy(ctx, item_id="arrows", npc_id="mara"):
    return apply(
        ctx, req("trade", npc_id=npc_id, direction="buy", item_id=item_id, qty=1, quality="any")
    )


def listing(ctx, category):
    return apply(
        ctx, req("trade", npc_id="mara", direction="list", item_id="", qty=0, category=category)
    )


# исходы

def test_success_gives_minus_10(registry, cfg):
    ctx = total_ctx(registry, cfg, 15)
    d = haggle(ctx)
    assert isinstance(d, Decision)
    assert d.status == "accepted"
    assert d.result["outcome"] == "success"
    assert d.result["haggle_percent"] == -10


def test_strong_success_gives_minus_20(registry, cfg):
    ctx = total_ctx(registry, cfg, 20)
    d = haggle(ctx)
    assert d.result["outcome"] == "success"
    assert d.result["haggle_percent"] == -20


def test_success_just_below_strong_gives_minus_10(registry, cfg):
    ctx = total_ctx(registry, cfg, 19)
    assert haggle(ctx).result["haggle_percent"] == -10


def test_fail_gives_plus_10(registry, cfg):
    ctx = total_ctx(registry, cfg, 14)
    d = haggle(ctx)
    assert d.status == "accepted"
    assert d.result["outcome"] == "fail"
    assert d.result["haggle_percent"] == 10


def test_result_has_dc_total_roll_ref_and_until(registry, cfg):
    ctx = total_ctx(registry, cfg, 17)
    result = haggle(ctx).result
    assert result["dc"] == 15
    assert result["total"] == 17
    assert result["roll_ref"]
    assert result["until"] == "конец дня"


def test_roll_is_one_persuasion_check(registry, cfg):
    ctx = total_ctx(registry, cfg, 15)
    d = haggle(ctx)
    assert ctx.rng.calls == ["d20"]
    assert "Убеждение" in d.log[0]


def test_log_has_roll_line_and_price_note(registry, cfg):
    ctx = total_ctx(registry, cfg, 15)
    d = haggle(ctx)
    assert len(d.log) == 2
    assert "Убеждение" in d.log[0]
    assert "Mara" in d.log[1]
    assert "-10%" in d.log[1]


def test_fail_log_shows_plus(registry, cfg):
    ctx = total_ctx(registry, cfg, 14)
    assert "+10%" in haggle(ctx).log[1]


def test_profile_gets_percent_and_today(registry, cfg):
    ctx = total_ctx(registry, cfg, 15)
    ctx.bundle.world.clock.advance(2 * DAY_S + 50)
    haggle(ctx)
    assert (merchant(ctx).haggle_percent, merchant(ctx).haggle_day) == (-10, 2)


def test_haggle_on_day_zero_marks_day_zero(registry, cfg):
    ctx = total_ctx(registry, cfg, 15)
    haggle(ctx)
    assert merchant(ctx).haggle_day == 0


# СЛ и режим

def test_good_attitude_uses_dc_10(registry, cfg):
    ctx = total_ctx(registry, cfg, 10, attitude=50)
    d = haggle(ctx)
    assert d.result["dc"] == 10
    assert d.result["outcome"] == "success"


def test_attitude_49_uses_dc_15(registry, cfg):
    ctx = total_ctx(registry, cfg, 10, attitude=49)
    d = haggle(ctx)
    assert d.result["dc"] == 15
    assert d.result["outcome"] == "fail"


def test_zero_attitude_rolls_once(registry, cfg):
    ctx = haggle_ctx(registry, cfg, [12, 12], attitude=0)
    haggle(ctx)
    assert ctx.rng.calls == ["d20"]


def test_negative_attitude_rolls_with_disadvantage(registry, cfg):
    bonus = skill_bonus(make_ctx(registry, cfg).hero, registry, "persuasion")
    ctx = haggle_ctx(registry, cfg, [15 - bonus + 3, 2], attitude=-10)
    d = haggle(ctx)
    assert ctx.rng.calls == ["d20", "d20"]
    assert d.result["total"] == 2 + bonus
    assert d.result["outcome"] == "fail"


def test_disadvantage_line_names_the_reason(registry, cfg):
    ctx = haggle_ctx(registry, cfg, [14, 13], attitude=-10)
    assert "недружелюбен" in haggle(ctx).log[0]


# один торг в день

@pytest.mark.parametrize("total", [15, 14])
def test_second_haggle_same_day_is_rejected_without_roll(registry, cfg, total):
    ctx = total_ctx(registry, cfg, total)
    haggle(ctx)
    before = dump(ctx)
    calls = list(ctx.rng.calls)
    d = haggle(ctx)
    assert isinstance(d, Decision)
    assert d.status == "rejected"
    assert d.signal_to_master
    assert ctx.rng.calls == calls
    assert dump(ctx) == before


def test_second_haggle_hint_names_merchant_and_percent(registry, cfg):
    ctx = total_ctx(registry, cfg, 15)
    haggle(ctx)
    assert "Mara" in haggle(ctx).signal_to_master
    assert "-10%" in haggle(ctx).signal_to_master


def test_next_day_haggle_is_allowed_again(registry, cfg):
    ctx = haggle_ctx(registry, cfg, [14, 14])
    haggle(ctx)
    ctx.bundle.world.clock.advance(DAY_S)
    d = haggle(ctx)
    assert d.status == "accepted"
    assert merchant(ctx).haggle_day == 1


def test_next_day_old_haggle_does_not_affect_prices(registry, cfg):
    ctx = total_ctx(registry, cfg, 20)
    haggle(ctx)
    ctx.bundle.world.clock.advance(DAY_S)
    assert buy(ctx).result["price_cp"] == 100


def test_other_merchant_can_still_be_haggled(registry, cfg):
    ctx = haggle_ctx(registry, cfg, [14, 14])
    ctx.bundle.world.npcs["tilda"] = NPC(
        id="tilda", name="Tilda", means=["товары"], location_id="vale",
        trade=TradeProfile(kind="general", purse_cp=5000, restock_at_s=FAR),
    )
    haggle(ctx)
    assert haggle(ctx, npc_id="tilda").status == "accepted"


# недоступный торговец

def test_haggle_in_combat_is_invalid(registry, cfg):
    ctx = total_ctx(registry, cfg, 15)
    apply(ctx, combat_request())
    before = dump(ctx)
    d = haggle(ctx)
    assert isinstance(d, Invalid)
    assert d.code == "in_combat"
    assert dump(ctx) == before


def test_unknown_npc_is_invalid(registry, cfg):
    ctx = total_ctx(registry, cfg, 15)
    before = dump(ctx)
    d = haggle(ctx, npc_id="nobody")
    assert isinstance(d, Invalid)
    assert d.code == "unknown_npc"
    assert dump(ctx) == before


def test_npc_in_another_location_is_absent(registry, cfg):
    ctx = total_ctx(registry, cfg, 15, location_id="forest")
    d = haggle(ctx)
    assert isinstance(d, Invalid)
    assert d.code == "npc_absent"


@pytest.mark.parametrize("status", ["dead", "gone"])
def test_not_alive_npc_is_invalid(registry, cfg, status):
    ctx = total_ctx(registry, cfg, 15, status=status)
    d = haggle(ctx)
    assert isinstance(d, Invalid)
    assert d.code in ("unknown_npc", "npc_absent")


def test_not_a_merchant_is_invalid(registry, cfg):
    ctx = total_ctx(registry, cfg, 15)
    before = dump(ctx)
    d = haggle(ctx, npc_id="grakh")
    assert isinstance(d, Invalid)
    assert d.code == "not_merchant"
    assert dump(ctx) == before


@pytest.mark.parametrize("attitude", [-50, -100])
def test_hostile_merchant_refuses_to_haggle(registry, cfg, attitude):
    ctx = haggle_ctx(registry, cfg, [14], attitude=attitude)
    before = dump(ctx)
    d = haggle(ctx)
    assert d.status == "rejected"
    assert d.signal_to_master
    assert ctx.rng.calls == []
    assert dump(ctx) == before


def test_attitude_just_above_refusal_haggles(registry, cfg):
    ctx = haggle_ctx(registry, cfg, [14, 14], attitude=-49)
    assert haggle(ctx).status == "accepted"


# лимит сцены

def test_haggle_does_not_spend_scene_trades(registry, cfg):
    ctx = total_ctx(registry, cfg, 15)
    haggle(ctx)
    assert ctx.scene.trades == 0


def test_haggle_works_at_the_scene_limit(registry, cfg):
    ctx = total_ctx(registry, cfg, 15)
    ctx.scene.trades = cfg.trade.ops_per_scene
    assert haggle(ctx).status == "accepted"


def test_haggle_does_not_move_time(registry, cfg):
    ctx = total_ctx(registry, cfg, 15)
    haggle(ctx)
    assert ctx.bundle.world.clock.now_s == 0


# цены после торга

def test_buy_after_success_is_10_percent_cheaper(registry, cfg):
    ctx = total_ctx(registry, cfg, 15)
    haggle(ctx)
    d = buy(ctx)
    assert d.result["price_cp"] == 90
    assert ctx.hero.money_cp == 910


def test_buy_after_success_reports_haggle_percent(registry, cfg):
    ctx = total_ctx(registry, cfg, 15)
    haggle(ctx)
    assert buy(ctx).result["haggle_percent"] == -10


def test_buy_without_haggle_has_no_haggle_percent(registry, cfg):
    ctx = total_ctx(registry, cfg, 15)
    assert "haggle_percent" not in buy(ctx).result


def test_buy_after_strong_success_is_20_percent_cheaper(registry, cfg):
    ctx = total_ctx(registry, cfg, 20)
    haggle(ctx)
    assert buy(ctx).result["price_cp"] == 80


def test_buy_after_fail_is_10_percent_dearer(registry, cfg):
    ctx = total_ctx(registry, cfg, 14)
    haggle(ctx)
    assert buy(ctx).result["price_cp"] == 110


def test_good_attitude_success_buys_at_81_percent(registry, cfg):
    ctx = total_ctx(registry, cfg, 12, attitude=60)
    haggle(ctx)
    assert buy(ctx).result["price_cp"] == 81


def test_good_attitude_strong_success_is_clamped_to_80_percent(registry, cfg):
    ctx = total_ctx(registry, cfg, 15, attitude=60)
    haggle(ctx)
    assert merchant(ctx).haggle_percent == -20
    assert buy(ctx).result["price_cp"] == 80


def test_list_after_haggle_uses_the_new_price(registry, cfg):
    ctx = total_ctx(registry, cfg, 15)
    before = {i["item_id"]: i["price_cp"] for i in listing(ctx, "gear").result["items"]}
    haggle(ctx)
    after = {i["item_id"]: i["price_cp"] for i in listing(ctx, "gear").result["items"]}
    assert after["arrows"] == 90
    assert before["arrows"] == 100


def test_buy_from_stock_after_haggle(registry, cfg):
    stock = [InventoryEntry(item_id="scimitar", qty=2, cost_cp=100, quality="junk")]
    ctx = total_ctx(registry, cfg, 15, stock=stock)
    haggle(ctx)
    assert buy(ctx, "scimitar").result["price_cp"] == 90


def test_buy_back_quest_item_from_holder_after_haggle(registry, cfg):
    ctx = total_ctx(registry, cfg, 15, money=0)
    apply(ctx, req(
        "give_custom_item", name="Ржавый ключ", description="", qty=1, weight_lb=0,
        cost_cp=700, quest=True,
    ))
    apply(ctx, req(
        "trade", npc_id="mara", direction="sell", item_id="custom_1", qty=1, quality="any"
    ))
    ctx.hero.money_cp = 1000
    haggle(ctx)
    assert buy(ctx, "custom_1").result["price_cp"] == 630


def test_sell_after_haggle_keeps_the_old_price(registry, cfg):
    ctx = total_ctx(registry, cfg, 20)
    ctx.hero.inventory = [InventoryEntry(item_id="scimitar", qty=1, cost_cp=1000)]
    ctx.hero.equipped.main_hand = None
    haggle(ctx)
    d = apply(
        ctx, req("trade", npc_id="mara", direction="sell", item_id="scimitar", qty=1, quality="any")
    )
    assert d.result["price_cp"] == 500
    assert "haggle_percent" not in d.result


def test_failed_haggle_does_not_change_money_or_inventory(registry, cfg):
    ctx = total_ctx(registry, cfg, 14)
    inventory = ctx.hero.model_dump_json()
    haggle(ctx)
    assert ctx.hero.model_dump_json() == inventory


# бросок в журнале контекста

def test_roll_is_stored_for_the_hero(registry, cfg):
    ctx = total_ctx(registry, cfg, 15)
    ref = haggle(ctx).result["roll_ref"]
    assert ctx.roll_actors[ref] == ctx.hero.id


def test_stored_roll_is_the_persuasion_check_against_the_dc(registry, cfg):
    ctx = total_ctx(registry, cfg, 17)
    roll = ctx.rolls[haggle(ctx).result["roll_ref"]]
    assert (roll.dc, roll.total, roll.outcome) == (15, 17, "success")


def test_stored_roll_has_normal_stakes(registry, cfg):
    ctx = total_ctx(registry, cfg, 15)
    roll = ctx.rolls[haggle(ctx).result["roll_ref"]]
    assert roll.tags == {"stakes": "normal"}
