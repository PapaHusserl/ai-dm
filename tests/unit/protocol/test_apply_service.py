# Реестр услуг, партия П1 (docs/plan-u0.md): инструмент service{npc_id, direction, service_id, qty}
# и связанные изменения trade/haggle/npc_update/npc_create.
#   list -- позиции NPC с ценами (id, name, unit, price_cp, description), без оплаты, без
#       траты scene.trades. buy -- проверки: бой -> Invalid in_combat, нет NPC -> unknown_npc,
#       NPC не здесь -> npc_absent, нет services -> no_services, услуги нет у NPC ->
#       unknown_service, qty < 1 -> bad_amount, attitude <= -50 -> rejected,
#       scene.trades >= ops_per_scene -> rejected.
#   qty урезается по деньгам (clamped); нет денег на одну -> rejected. Сделка тратит scene.trades
#       (общий лимит с trade).
#   heal: лечит героя бросками кости вида, при полных хитах -> rejected без списания,
#       мёртвому герою -> Invalid.
#   cure (П3): снимает состояния kind.cures разом за одну цену, qty всегда 1; нет состояния ->
#       rejected nothing_to_cure без списания; нет денег -> short_of_money; мёртвому -> Invalid.
#   haggle у NPC без лавки -- состояние во флаге haggle:<npc_id> (зарезервирован для set_flag),
#       с лавкой -- торг общий на товары и услуги.
#   npc_update/npc_create services: объединение без дублей, неизвестный id ->
#       Invalid unknown_service.
import pytest
from protocol_kit import ScriptedRng, combat_request, dump, make_ctx, req

from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.rules.derived import skill_bonus
from ai_dm.rules.trade import DAY_S
from ai_dm.state.creature import AppliedCondition
from ai_dm.state.world import NPC, TradeProfile

FAR = 10**9


def service_ctx(
    registry, cfg, money=1000, rng=None, services=("room_modest", "meal_modest"), **fields
):
    ctx = make_ctx(registry, cfg, rng)
    ctx.hero.money_cp = money
    fields.setdefault("location_id", "vale")
    ctx.bundle.world.npcs["grok"] = NPC(
        id="grok", name="Грок", means=["трактир"], services=list(services), **fields
    )
    return ctx


def buy(ctx, service_id="meal_modest", qty=1, npc_id="grok"):
    return apply(
        ctx, req("service", npc_id=npc_id, direction="buy", service_id=service_id, qty=qty)
    )


def listing(ctx, npc_id="grok"):
    return apply(ctx, req("service", npc_id=npc_id, direction="list", service_id="", qty=0))


def prices(decision):
    return {item["id"]: item["price_cp"] for item in decision.result["items"]}


def grok(ctx):
    return ctx.bundle.world.npcs["grok"]


# list

def test_list_shows_services_with_prices(registry, cfg):
    d = listing(service_ctx(registry, cfg))
    assert isinstance(d, Decision)
    assert d.status == "accepted"
    assert d.result["npc_id"] == "grok"
    assert prices(d) == {"room_modest": 50, "meal_modest": 10}


def test_list_item_has_name_unit_and_description(registry, cfg):
    d = listing(service_ctx(registry, cfg, services=["room_modest"]))
    item = d.result["items"][0]
    assert item["name"] == "комната (скромная)"
    assert item["unit"] == "night"
    assert item["description"] == cfg.services.kinds["room_modest"].description


def test_list_keeps_npc_order(registry, cfg):
    d = listing(service_ctx(registry, cfg, services=["meal_modest", "ale", "room_modest"]))
    assert [i["id"] for i in d.result["items"]] == ["meal_modest", "ale", "room_modest"]


def test_list_does_not_spend_money_or_scene_trades(registry, cfg):
    ctx = service_ctx(registry, cfg)
    before = dump(ctx)
    listing(ctx)
    assert dump(ctx) == before
    assert ctx.scene.trades == 0
    assert ctx.events == []


def test_list_works_at_the_scene_limit(registry, cfg):
    ctx = service_ctx(registry, cfg)
    ctx.scene.trades = cfg.trade.ops_per_scene
    assert listing(ctx).status == "accepted"


def test_list_prices_follow_attitude(registry, cfg):
    d = listing(service_ctx(registry, cfg, attitude=60))
    assert prices(d) == {"room_modest": 45, "meal_modest": 9}


def test_list_works_with_no_money(registry, cfg):
    assert listing(service_ctx(registry, cfg, money=0)).status == "accepted"


# buy: успех

def test_buy_spends_money_and_reports(registry, cfg):
    ctx = service_ctx(registry, cfg)
    d = buy(ctx, "meal_modest", 3)
    assert d.status == "accepted"
    assert ctx.hero.money_cp == 970
    assert d.result["service_id"] == "meal_modest"
    assert d.result["qty"] == 3
    assert d.result["price_cp"] == 10
    assert d.result["total_cp"] == 30
    assert d.result["money_cp"] == 970


def test_buy_log_names_service_npc_and_total(registry, cfg):
    d = buy(service_ctx(registry, cfg), "meal_modest", 2)
    assert len(d.log) == 1
    assert "еда (скромная)" in d.log[0]
    assert "x2" in d.log[0]
    assert "Грок" in d.log[0]
    assert "2 см" in d.log[0]


def test_buy_meal_log_starts_with_meal_word(registry, cfg):
    assert buy(service_ctx(registry, cfg), "meal_modest").log[0].startswith("Заказано")


def test_buy_spends_one_scene_trade(registry, cfg):
    ctx = service_ctx(registry, cfg)
    buy(ctx, "meal_modest", 5)
    assert ctx.scene.trades == 1


def test_buy_without_scene_still_works(registry, cfg):
    ctx = service_ctx(registry, cfg)
    ctx.bundle.session.current_scene = None
    assert buy(ctx).status == "accepted"


def test_buy_price_follows_attitude(registry, cfg):
    ctx = service_ctx(registry, cfg, attitude=60)
    assert buy(ctx, "room_modest").result["price_cp"] == 45
    assert ctx.hero.money_cp == 955


def test_buy_exact_money_leaves_zero(registry, cfg):
    ctx = service_ctx(registry, cfg, money=10)
    assert buy(ctx).status == "accepted"
    assert ctx.hero.money_cp == 0


def test_buy_without_haggle_has_no_haggle_percent(registry, cfg):
    assert "haggle_percent" not in buy(service_ctx(registry, cfg)).result


def test_buy_free_service_takes_requested_qty(registry, cfg):
    ctx = service_ctx(registry, cfg, money=0)
    cfg_free = cfg.model_copy(deep=True)
    cfg_free.services.kinds["meal_modest"].price_cp = 0
    ctx.cfg = cfg_free
    d = buy(ctx, "meal_modest", 3)
    assert d.status == "accepted"
    assert d.result["qty"] == 3


def test_buy_qty_is_capped_by_give_item_max_qty(registry, cfg):
    ctx = service_ctx(registry, cfg, money=10**6)
    d = buy(ctx, "meal_modest", cfg.limits.give_item_max_qty + 5)
    assert d.result["qty"] == cfg.limits.give_item_max_qty
    assert d.status == "clamped"
    assert "лимит количества за раз" in d.signal_to_master
    assert "не хватило денег" not in d.signal_to_master


def test_buy_over_limit_and_money_blames_money(registry, cfg):
    cap = cfg.limits.give_item_max_qty
    ctx = service_ctx(registry, cfg, money=10 * (cap - 1))
    d = buy(ctx, "meal_modest", cap + 5)
    assert d.result["qty"] == cap - 1
    assert "не хватило денег" in d.signal_to_master
    assert "(не хватило денег)" in d.signal_to_master


def test_buy_over_limit_with_money_exactly_for_limit_blames_limit(registry, cfg):
    cap = cfg.limits.give_item_max_qty
    ctx = service_ctx(registry, cfg, money=10 * cap)
    d = buy(ctx, "meal_modest", cap + 5)
    assert d.result["qty"] == cap
    assert "(лимит количества за раз: " in d.signal_to_master


def test_buy_free_service_over_limit_blames_limit(registry, cfg):
    cap = cfg.limits.give_item_max_qty
    ctx = service_ctx(registry, cfg, money=0)
    cfg_free = cfg.model_copy(deep=True)
    cfg_free.services.kinds["meal_modest"].price_cp = 0
    ctx.cfg = cfg_free
    d = buy(ctx, "meal_modest", cap + 5)
    assert d.result["qty"] == cap
    assert "лимит количества за раз" in d.signal_to_master


def test_buy_one_cp_service_short_of_money_blames_money(registry, cfg):
    cap = cfg.limits.give_item_max_qty
    ctx = service_ctx(registry, cfg, money=cap - 1)
    cfg_cheap = cfg.model_copy(deep=True)
    cfg_cheap.services.kinds["meal_modest"].price_cp = 1
    ctx.cfg = cfg_cheap
    d = buy(ctx, "meal_modest", cap + 5)
    assert d.result["qty"] == cap - 1
    assert "(не хватило денег)" in d.signal_to_master


def test_buy_without_money_names_the_service_in_signal(registry, cfg):
    d = buy(service_ctx(registry, cfg, money=9), "meal_modest")
    assert "на еда (скромная)" in d.signal_to_master


def test_heal_over_limit_blames_limit(registry, cfg):
    cap = cfg.limits.give_item_max_qty
    ctx = heal_ctx(registry, cfg, hp=1, die=0, rolls=[1] * (cap + 1), money=10**6)
    ctx.hero.creature.hp_max = 10**4
    d = buy(ctx, "heal_barber", cap + 1)
    assert d.status == "clamped"
    assert d.result["qty"] == cap
    assert "лимит количества за раз" in d.signal_to_master


# buy: урезание и нехватка денег

def test_buy_is_clamped_by_money(registry, cfg):
    ctx = service_ctx(registry, cfg, money=25)
    d = buy(ctx, "meal_modest", 3)
    assert d.status == "clamped"
    assert d.result["qty"] == 2
    assert ctx.hero.money_cp == 5
    assert d.signal_to_master
    assert "x2" in d.log[0]


def test_clamped_buy_still_spends_scene_trade(registry, cfg):
    ctx = service_ctx(registry, cfg, money=25)
    buy(ctx, "meal_modest", 3)
    assert ctx.scene.trades == 1


def test_buy_without_money_for_one_is_rejected(registry, cfg):
    ctx = service_ctx(registry, cfg, money=9)
    before = dump(ctx)
    d = buy(ctx, "meal_modest")
    assert d.status == "rejected"
    assert d.signal_to_master
    assert dump(ctx) == before
    assert ctx.events == []


def test_rejected_for_money_does_not_spend_scene_trade(registry, cfg):
    ctx = service_ctx(registry, cfg, money=0)
    buy(ctx)
    assert ctx.scene.trades == 0


# buy: проверки

def test_buy_in_combat_is_invalid(registry, cfg):
    ctx = service_ctx(registry, cfg)
    apply(ctx, combat_request())
    before = dump(ctx)
    d = buy(ctx)
    assert isinstance(d, Invalid)
    assert d.code == "in_combat"
    assert dump(ctx) == before


def test_list_in_combat_is_invalid(registry, cfg):
    ctx = service_ctx(registry, cfg)
    apply(ctx, combat_request())
    assert listing(ctx).code == "in_combat"


def test_unknown_npc_is_invalid_with_provider_hint(registry, cfg):
    ctx = service_ctx(registry, cfg)
    d = buy(ctx, npc_id="nobody")
    assert isinstance(d, Invalid)
    assert d.code == "unknown_npc"
    assert "grok" in d.message


def test_npc_in_another_location_is_absent(registry, cfg):
    ctx = service_ctx(registry, cfg, location_id="forest")
    before = dump(ctx)
    d = buy(ctx)
    assert isinstance(d, Invalid)
    assert d.code == "npc_absent"
    assert dump(ctx) == before


def test_npc_without_services_is_invalid_no_services(registry, cfg):
    ctx = service_ctx(registry, cfg)
    before = dump(ctx)
    d = buy(ctx, npc_id="grakh")
    assert isinstance(d, Invalid)
    assert d.code == "no_services"
    assert "grok" in d.message
    assert dump(ctx) == before


def test_merchant_without_services_is_no_services(registry, cfg):
    ctx = service_ctx(registry, cfg, services=[])
    grok(ctx).trade = TradeProfile(kind="general", purse_cp=100, restock_at_s=FAR)
    assert buy(ctx).code == "no_services"


def test_list_for_npc_without_services_is_no_services(registry, cfg):
    assert listing(service_ctx(registry, cfg), npc_id="grakh").code == "no_services"


def test_dead_provider_is_invalid(registry, cfg):
    ctx = service_ctx(registry, cfg, status="dead")
    d = buy(ctx)
    assert isinstance(d, Invalid)
    assert d.code in ("unknown_npc", "npc_absent")


def test_service_the_npc_does_not_provide_is_unknown(registry, cfg):
    ctx = service_ctx(registry, cfg)
    before = dump(ctx)
    d = buy(ctx, "heal_temple")
    assert isinstance(d, Invalid)
    assert d.code == "unknown_service"
    assert "meal_modest" in d.message
    assert dump(ctx) == before


def test_service_id_missing_in_registry_is_unknown(registry, cfg):
    ctx = service_ctx(registry, cfg, services=["room_modest", "no_such"])
    d = buy(ctx, "no_such")
    assert d.code == "unknown_service"
    assert "no_such" not in d.message.split("допустимые id:")[1]


@pytest.mark.parametrize("qty", [0, -1])
def test_qty_below_one_is_invalid(registry, cfg, qty):
    ctx = service_ctx(registry, cfg)
    before = dump(ctx)
    d = buy(ctx, qty=qty)
    assert isinstance(d, Invalid)
    assert d.code == "bad_amount"
    assert dump(ctx) == before


@pytest.mark.parametrize("attitude", [-50, -100])
def test_hostile_provider_refuses(registry, cfg, attitude):
    ctx = service_ctx(registry, cfg, attitude=attitude)
    before = dump(ctx)
    d = buy(ctx)
    assert d.status == "rejected"
    assert d.signal_to_master
    assert dump(ctx) == before


def test_hostile_provider_refuses_list_too(registry, cfg):
    assert listing(service_ctx(registry, cfg, attitude=-50)).status == "rejected"


def test_attitude_just_above_refusal_serves(registry, cfg):
    assert buy(service_ctx(registry, cfg, attitude=-49)).status == "accepted"


# лимит сцены

def test_scene_limit_is_shared_20th_passes_21st_rejected(registry, cfg):
    ctx = service_ctx(registry, cfg)
    ctx.scene.trades = cfg.trade.ops_per_scene - 1
    assert buy(ctx).status == "accepted"
    assert ctx.scene.trades == cfg.trade.ops_per_scene
    before = dump(ctx)
    d = buy(ctx)
    assert d.status == "rejected"
    assert d.signal_to_master
    assert d.signal_to_master.startswith("В этой сцене")
    assert d.signal_to_master.endswith("опиши по факту.")
    assert dump(ctx) == before


def test_trade_deals_count_toward_service_limit(registry, cfg):
    ctx = service_ctx(registry, cfg, money=10**6)
    ctx.bundle.world.npcs["mara"] = NPC(
        id="mara", name="Mara", means=["товары"], location_id="vale",
        trade=TradeProfile(kind="general", purse_cp=5000, restock_at_s=FAR),
    )
    for _ in range(cfg.trade.ops_per_scene):
        d = apply(ctx, req(
            "trade", npc_id="mara", direction="buy", item_id="arrows", qty=1, quality="any"
        ))
        assert d.status == "accepted"
    assert buy(ctx).status == "rejected"


def test_service_deals_count_toward_trade_limit(registry, cfg):
    ctx = service_ctx(registry, cfg, money=10**6)
    ctx.bundle.world.npcs["mara"] = NPC(
        id="mara", name="Mara", means=["товары"], location_id="vale",
        trade=TradeProfile(kind="general", purse_cp=5000, restock_at_s=FAR),
    )
    for _ in range(cfg.trade.ops_per_scene):
        assert buy(ctx).status == "accepted"
    d = apply(ctx, req(
        "trade", npc_id="mara", direction="buy", item_id="arrows", qty=1, quality="any"
    ))
    assert d.status == "rejected"


# heal

def heal_ctx(registry, cfg, hp, die, money=1000, service="heal_barber", rolls=None):
    ctx = service_ctx(
        registry, cfg, money=money, rng=ScriptedRng(d8=rolls or [die]), services=[service]
    )
    ctx.hero.creature.hp_max = 10
    ctx.hero.creature.hp_current = hp
    return ctx


def test_heal_adds_rolled_hp_and_spends_money(registry, cfg):
    ctx = heal_ctx(registry, cfg, hp=3, die=5)
    d = buy(ctx, "heal_barber")
    assert d.status == "accepted"
    assert ctx.hero.creature.hp_current == 8
    assert ctx.hero.money_cp == 950
    assert d.result["healed"] == 5
    assert d.result["hp"] == 8
    assert d.result["hp_max"] == 10


def test_heal_caps_at_max_hp(registry, cfg):
    ctx = heal_ctx(registry, cfg, hp=8, die=8)
    d = buy(ctx, "heal_barber")
    assert ctx.hero.creature.hp_current == 10
    assert d.result["healed"] == 2


def test_heal_log_has_hp_and_price(registry, cfg):
    d = buy(heal_ctx(registry, cfg, hp=3, die=5), "heal_barber")
    assert len(d.log) == 1
    assert d.log[0].startswith("Лечение")
    assert "+5 HP" in d.log[0]
    assert "8/10" in d.log[0]
    assert "5 см" in d.log[0]


def test_heal_at_full_hp_is_rejected_without_charge(registry, cfg):
    ctx = heal_ctx(registry, cfg, hp=10, die=5)
    before = dump(ctx)
    d = buy(ctx, "heal_barber")
    assert d.status == "rejected"
    assert d.reason == "лечить нечего"
    assert d.signal_to_master.startswith("Герой здоров")
    assert d.signal_to_master.endswith("Опиши по факту.")
    assert dump(ctx) == before
    assert ctx.rng.calls == []


def test_heal_without_money_is_rejected(registry, cfg):
    ctx = heal_ctx(registry, cfg, hp=3, die=5, money=49)
    before = dump(ctx)
    d = buy(ctx, "heal_barber")
    assert d.status == "rejected"
    assert "на лечение цирюльника" in d.signal_to_master
    assert dump(ctx) == before


def test_heal_to_dead_hero_is_invalid(registry, cfg):
    ctx = heal_ctx(registry, cfg, hp=0, die=5)
    ctx.hero.status = "dead"
    before = dump(ctx)
    d = buy(ctx, "heal_barber")
    assert isinstance(d, Invalid)
    assert d.code == "hero_dead"
    assert d.message.startswith("герой мёртв")
    assert d.message.endswith("не нужна")
    assert dump(ctx) == before


def test_heal_spends_scene_trade(registry, cfg):
    ctx = heal_ctx(registry, cfg, hp=3, die=5)
    buy(ctx, "heal_barber")
    assert ctx.scene.trades == 1


def test_rejected_heal_does_not_spend_scene_trade(registry, cfg):
    ctx = heal_ctx(registry, cfg, hp=10, die=5)
    buy(ctx, "heal_barber")
    assert ctx.scene.trades == 0
    assert ctx.events == []


def test_heal_qty_two_rolls_twice_and_charges_twice(registry, cfg):
    ctx = heal_ctx(registry, cfg, hp=1, die=0, rolls=[2, 3])
    d = buy(ctx, "heal_barber", 2)
    assert d.status == "accepted"
    assert ctx.rng.calls == ["d8", "d8"]
    assert ctx.hero.creature.hp_current == 6
    assert ctx.hero.money_cp == 900
    assert d.result["qty"] == 2
    assert d.result["total_cp"] == 100
    assert d.result["healed"] == 5
    assert "+5 HP" in d.log[0]


def test_heal_qty_stops_when_hp_is_full(registry, cfg):
    ctx = heal_ctx(registry, cfg, hp=7, die=0, rolls=[8, 8])
    d = buy(ctx, "heal_barber", 2)
    assert ctx.rng.calls == ["d8"]
    assert ctx.hero.money_cp == 950
    assert d.status == "clamped"
    assert d.result["qty"] == 1
    assert "(герой исцелён раньше)" in d.signal_to_master
    assert "не хватило денег" not in d.signal_to_master


def test_heal_qty_is_clamped_by_money(registry, cfg):
    ctx = heal_ctx(registry, cfg, hp=1, die=0, rolls=[1, 1], money=60)
    d = buy(ctx, "heal_barber", 2)
    assert d.status == "clamped"
    assert d.result["qty"] == 1
    assert ctx.hero.money_cp == 10
    assert "не хватило денег" in d.signal_to_master


def test_temple_heal_rolls_2d8_plus_4(registry, cfg):
    ctx = heal_ctx(registry, cfg, hp=1, die=0, service="heal_temple", rolls=[1, 1])
    ctx.hero.creature.hp_max = 30
    d = buy(ctx, "heal_temple")
    assert d.result["healed"] == 6
    assert ctx.hero.creature.hp_current == 7
    assert ctx.hero.money_cp == 800


def test_heal_price_follows_attitude(registry, cfg):
    ctx = heal_ctx(registry, cfg, hp=3, die=5)
    grok(ctx).attitude = 60
    assert buy(ctx, "heal_barber").result["price_cp"] == 45


# cure (У0 П3): uncurse_temple снимает cursed за 2500 мм; нет проклятия -> nothing_to_cure

def cure_ctx(registry, cfg, money=3000, cursed=True, service="uncurse_temple"):
    ctx = service_ctx(registry, cfg, money=money, services=[service])
    if cursed:
        ctx.hero.creature.conditions.append(AppliedCondition(id="cursed", source="master:t1"))
    return ctx


def test_cure_removes_the_curse_and_spends_money(registry, cfg):
    ctx = cure_ctx(registry, cfg)
    d = buy(ctx, "uncurse_temple")
    assert d.status == "accepted"
    assert ctx.hero.creature.conditions == []
    assert ctx.hero.money_cp == 500
    assert d.result["cured"] == ["cursed"]
    assert d.result["service_id"] == "uncurse_temple"
    assert d.result["qty"] == 1
    assert d.result["price_cp"] == 2500
    assert d.result["total_cp"] == 2500
    assert d.result["money_cp"] == 500


def test_cure_log_says_curse_lifted_with_npc_and_price(registry, cfg):
    d = buy(cure_ctx(registry, cfg), "uncurse_temple")
    assert len(d.log) == 1
    assert d.log[0].startswith("Проклятие снято")
    assert "снятие проклятия" in d.log[0]
    assert "Грок" in d.log[0]
    assert "25 зм" in d.log[0]


def test_cure_emits_cured_event(registry, cfg):
    ctx = cure_ctx(registry, cfg)
    buy(ctx, "uncurse_temple")
    [event] = [e for e in ctx.events if e.type == "cured"]
    assert event.data == {"id": ctx.hero.id, "conditions": "cursed"}


def test_cure_keeps_other_conditions(registry, cfg):
    ctx = cure_ctx(registry, cfg)
    ctx.hero.creature.conditions.insert(0, AppliedCondition(id="poisoned"))
    buy(ctx, "uncurse_temple")
    assert [c.id for c in ctx.hero.creature.conditions] == ["poisoned"]


def test_cure_spends_scene_trade(registry, cfg):
    ctx = cure_ctx(registry, cfg)
    buy(ctx, "uncurse_temple")
    assert ctx.scene.trades == 1


def test_cure_with_qty_three_charges_once(registry, cfg):
    ctx = cure_ctx(registry, cfg)
    d = buy(ctx, "uncurse_temple", 3)
    assert d.status == "accepted"
    assert d.result["qty"] == 1
    assert ctx.hero.money_cp == 500


def test_cure_exact_money_leaves_zero(registry, cfg):
    ctx = cure_ctx(registry, cfg, money=2500)
    assert buy(ctx, "uncurse_temple").status == "accepted"
    assert ctx.hero.money_cp == 0


def test_cure_price_follows_attitude(registry, cfg):
    ctx = cure_ctx(registry, cfg)
    grok(ctx).attitude = 60
    d = buy(ctx, "uncurse_temple")
    assert d.result["price_cp"] == 2250
    assert ctx.hero.money_cp == 750


def test_cure_without_curse_is_rejected_without_charge(registry, cfg):
    ctx = cure_ctx(registry, cfg, cursed=False)
    before = dump(ctx)
    d = buy(ctx, "uncurse_temple")
    assert d.status == "rejected"
    assert d.report_tag == "nothing_to_cure"
    assert d.signal_to_master.endswith("Опиши по факту.")
    assert dump(ctx) == before
    assert ctx.events == []


def test_cure_with_only_other_condition_is_rejected(registry, cfg):
    ctx = cure_ctx(registry, cfg, cursed=False)
    ctx.hero.creature.conditions.append(AppliedCondition(id="poisoned"))
    d = buy(ctx, "uncurse_temple")
    assert d.report_tag == "nothing_to_cure"
    assert [c.id for c in ctx.hero.creature.conditions] == ["poisoned"]
    assert ctx.hero.money_cp == 3000


def test_rejected_cure_does_not_spend_scene_trade(registry, cfg):
    ctx = cure_ctx(registry, cfg, cursed=False)
    buy(ctx, "uncurse_temple")
    assert ctx.scene.trades == 0


def test_cure_without_money_is_short_of_money_and_keeps_curse(registry, cfg):
    ctx = cure_ctx(registry, cfg, money=2499)
    before = dump(ctx)
    d = buy(ctx, "uncurse_temple")
    assert d.status == "rejected"
    assert "на снятие проклятия" in d.signal_to_master
    assert d.report_tag != "nothing_to_cure"
    assert dump(ctx) == before
    assert ctx.events == []


def test_cure_nothing_to_cure_wins_over_no_money(registry, cfg):
    d = buy(cure_ctx(registry, cfg, money=0, cursed=False), "uncurse_temple")
    assert d.report_tag == "nothing_to_cure"


def test_cure_dead_hero_is_invalid(registry, cfg):
    ctx = cure_ctx(registry, cfg)
    ctx.hero.status = "dead"
    before = dump(ctx)
    d = buy(ctx, "uncurse_temple")
    assert isinstance(d, Invalid)
    assert d.code == "hero_dead"
    assert dump(ctx) == before


def test_cure_at_npc_without_the_service_is_unknown_service(registry, cfg):
    ctx = cure_ctx(registry, cfg, service="heal_temple")
    d = buy(ctx, "uncurse_temple")
    assert isinstance(d, Invalid)
    assert d.code == "unknown_service"
    assert [c.id for c in ctx.hero.creature.conditions] == ["cursed"]


def test_cure_at_npc_without_services_is_no_services(registry, cfg):
    ctx = service_ctx(registry, cfg, money=3000, services=[])
    ctx.hero.creature.conditions.append(AppliedCondition(id="cursed"))
    d = buy(ctx, "uncurse_temple")
    assert isinstance(d, Invalid)
    assert d.code == "no_services"


def test_cure_cures_every_listed_condition_for_one_price(registry, cfg):
    ctx = cure_ctx(registry, cfg)
    cfg_two = cfg.model_copy(deep=True)
    cfg_two.services.kinds["uncurse_temple"].cures = ["cursed", "poisoned"]
    ctx.cfg = cfg_two
    ctx.hero.creature.conditions.append(AppliedCondition(id="poisoned"))
    d = buy(ctx, "uncurse_temple")
    assert d.result["cured"] == ["cursed", "poisoned"]
    assert ctx.hero.creature.conditions == []
    assert ctx.hero.money_cp == 500
    [event] = [e for e in ctx.events if e.type == "cured"]
    assert event.data["conditions"] == "cursed,poisoned"


def test_cure_list_shows_uncurse_temple_price(registry, cfg):
    ctx = service_ctx(registry, cfg, services=["uncurse_temple"])
    assert prices(listing(ctx)) == {"uncurse_temple": 2500}


def test_cure_does_not_roll_dice(registry, cfg):
    ctx = cure_ctx(registry, cfg)
    ctx.rng = ScriptedRng()
    buy(ctx, "uncurse_temple")
    assert ctx.rng.calls == []


# haggle у NPC только с услугами

def haggle_ctx(registry, cfg, total, **fields):
    probe = service_ctx(registry, cfg)
    face = total - skill_bonus(probe.hero, registry, "persuasion")
    return service_ctx(registry, cfg, rng=ScriptedRng(d20=[face, face]), **fields)


def haggle(ctx, npc_id="grok"):
    return apply(ctx, req("haggle", npc_id=npc_id))


def test_haggle_with_services_only_npc_rolls_and_sets_percent(registry, cfg):
    ctx = haggle_ctx(registry, cfg, 15)
    d = haggle(ctx)
    assert d.status == "accepted"
    assert d.result["haggle_percent"] == -10
    assert ctx.rng.calls == ["d20"]


def test_haggle_with_services_only_npc_writes_flag(registry, cfg):
    ctx = haggle_ctx(registry, cfg, 15)
    haggle(ctx)
    assert ctx.bundle.world.flags["haggle:grok"] == "0:-10"
    assert grok(ctx).trade is None


def test_haggle_makes_list_prices_10_percent_cheaper(registry, cfg):
    ctx = haggle_ctx(registry, cfg, 15)
    before = prices(listing(ctx))
    haggle(ctx)
    after = prices(listing(ctx))
    assert before == {"room_modest": 50, "meal_modest": 10}
    assert after == {"room_modest": 45, "meal_modest": 9}


def test_haggle_makes_buy_cheaper_and_reports_percent(registry, cfg):
    ctx = haggle_ctx(registry, cfg, 15)
    haggle(ctx)
    d = buy(ctx, "room_modest")
    assert d.result["price_cp"] == 45
    assert d.result["haggle_percent"] == -10
    assert ctx.hero.money_cp == 955


def test_failed_haggle_makes_services_dearer(registry, cfg):
    ctx = haggle_ctx(registry, cfg, 14)
    haggle(ctx)
    assert buy(ctx, "room_modest").result["price_cp"] == 55


def test_second_haggle_same_day_is_rejected_without_roll(registry, cfg):
    ctx = haggle_ctx(registry, cfg, 15)
    haggle(ctx)
    before = dump(ctx)
    d = haggle(ctx)
    assert d.status == "rejected"
    assert d.signal_to_master
    assert ctx.rng.calls == ["d20"]
    assert dump(ctx) == before


def test_next_day_haggle_is_allowed_again_and_old_flag_is_ignored(registry, cfg):
    ctx = haggle_ctx(registry, cfg, 15)
    haggle(ctx)
    ctx.bundle.world.clock.advance(DAY_S)
    assert prices(listing(ctx))["room_modest"] == 50
    assert haggle(ctx).status == "accepted"
    assert ctx.bundle.world.flags["haggle:grok"] == "1:-10"


def test_haggle_does_not_spend_scene_trades_for_services_npc(registry, cfg):
    ctx = haggle_ctx(registry, cfg, 15)
    haggle(ctx)
    assert ctx.scene.trades == 0


def test_haggle_with_merchant_and_services_shares_one_haggle(registry, cfg):
    ctx = haggle_ctx(registry, cfg, 15)
    grok(ctx).trade = TradeProfile(kind="general", purse_cp=5000, restock_at_s=FAR)
    haggle(ctx)
    assert grok(ctx).trade.haggle_percent == -10
    assert "haggle:grok" not in ctx.bundle.world.flags
    assert prices(listing(ctx))["room_modest"] == 45
    assert haggle(ctx).status == "rejected"


def test_merchant_trade_haggle_applies_to_services(registry, cfg):
    ctx = haggle_ctx(registry, cfg, 20)
    grok(ctx).trade = TradeProfile(kind="general", purse_cp=5000, restock_at_s=FAR)
    haggle(ctx)
    assert buy(ctx, "room_modest").result["price_cp"] == 40


def test_haggle_with_npc_without_trade_or_services_is_not_merchant(registry, cfg):
    ctx = haggle_ctx(registry, cfg, 15)
    before = dump(ctx)
    d = haggle(ctx, npc_id="grakh")
    assert isinstance(d, Invalid)
    assert d.code == "not_merchant"
    assert dump(ctx) == before


def test_haggle_unknown_npc_hint_lists_merchants_and_providers(registry, cfg):
    ctx = haggle_ctx(registry, cfg, 15)
    d = haggle(ctx, npc_id="nobody")
    assert d.code == "unknown_npc"
    assert "grok" in d.message


def test_haggle_hostile_services_npc_refuses(registry, cfg):
    ctx = haggle_ctx(registry, cfg, 15, attitude=-50)
    assert haggle(ctx).status == "rejected"
    assert ctx.rng.calls == []


def test_trade_with_services_only_npc_is_not_merchant(registry, cfg):
    ctx = service_ctx(registry, cfg)
    d = apply(ctx, req(
        "trade", npc_id="grok", direction="buy", item_id="arrows", qty=1, quality="any"
    ))
    assert isinstance(d, Invalid)
    assert d.code == "not_merchant"


def test_set_flag_cannot_forge_haggle_flag(registry, cfg):
    ctx = service_ctx(registry, cfg)
    d = apply(ctx, req("set_flag", name="haggle:grok", value="0:-20"))
    assert isinstance(d, Invalid) or d.status == "rejected"
    assert "haggle:grok" not in ctx.bundle.world.flags


# У0 П2: ночлег (флаг lodging:<hero>), платный отдых

def test_buy_lodging_sets_flag_to_today(registry, cfg):
    ctx = service_ctx(registry, cfg)
    ctx.bundle.world.clock.advance(DAY_S * 2 + 10)
    buy(ctx, "room_modest")
    assert ctx.bundle.world.flags["lodging:hero"] == 2


def test_buy_lodging_spends_money(registry, cfg):
    ctx = service_ctx(registry, cfg)
    d = buy(ctx, "room_modest")
    assert d.status == "accepted"
    assert ctx.hero.money_cp == 950


def test_buy_lodging_log_is_one_line_with_total(registry, cfg):
    d = buy(service_ctx(registry, cfg), "room_modest")
    assert len(d.log) == 1
    assert d.log[0].startswith("Ночлег оплачен")
    assert "комната (скромная)" in d.log[0]
    assert "Грок" in d.log[0]
    assert "5 см" in d.log[0]


def test_buy_lodging_signal_points_to_rest_long(registry, cfg):
    d = buy(service_ctx(registry, cfg), "room_modest")
    assert d.signal_to_master == "Ночлег оплачен: теперь rest long в этом же ходу."


def test_buy_lodging_qty_is_forced_to_one(registry, cfg):
    ctx = service_ctx(registry, cfg)
    d = buy(ctx, "room_modest", qty=3)
    assert d.result["qty"] == 1
    assert d.result["total_cp"] == 50
    assert ctx.hero.money_cp == 950


def test_buy_lodging_twice_same_day_is_rejected(registry, cfg):
    ctx = service_ctx(registry, cfg)
    buy(ctx, "room_modest")
    d = buy(ctx, "room_modest")
    assert d.status == "rejected"
    assert d.reason == "ночлег уже оплачен"
    assert "rest long" in d.signal_to_master


def test_second_lodging_signal_text_tells_not_to_pay_again(registry, cfg):
    ctx = service_ctx(registry, cfg)
    buy(ctx, "room_modest")
    d = buy(ctx, "room_modest")
    assert d.signal_to_master == (
        "Ночлег на сегодня уже оплачен: повторно не плати, вызови rest long."
    )


def test_second_lodging_does_not_charge_or_spend_scene_trade(registry, cfg):
    ctx = service_ctx(registry, cfg)
    buy(ctx, "room_modest")
    money, trades = ctx.hero.money_cp, ctx.scene.trades
    buy(ctx, "room_modest")
    assert ctx.hero.money_cp == money
    assert ctx.scene.trades == trades


def test_other_room_same_day_is_also_rejected(registry, cfg):
    ctx = service_ctx(registry, cfg, services=["room_poor", "room_modest"])
    buy(ctx, "room_modest")
    assert buy(ctx, "room_poor").status == "rejected"
    assert ctx.hero.money_cp == 950


def test_lodging_next_day_can_be_paid_again(registry, cfg):
    ctx = service_ctx(registry, cfg)
    buy(ctx, "room_modest")
    ctx.bundle.world.clock.advance(DAY_S + 7 * 3600)
    d = buy(ctx, "room_modest")
    assert d.status == "accepted"
    assert ctx.bundle.world.flags["lodging:hero"] == 1


def test_lodging_after_midnight_before_morning_is_still_paid(registry, cfg):
    ctx = service_ctx(registry, cfg)
    ctx.bundle.world.clock.advance(20 * 3600)
    buy(ctx, "room_modest")
    ctx.bundle.world.clock.advance(8 * 3600)
    assert buy(ctx, "room_modest").reason == "ночлег уже оплачен"


def test_lodging_without_money_sets_no_flag(registry, cfg):
    ctx = service_ctx(registry, cfg, money=10)
    d = buy(ctx, "room_modest")
    assert d.status == "rejected"
    assert "lodging:hero" not in ctx.bundle.world.flags
    assert ctx.hero.money_cp == 10


def test_lodging_over_scene_limit_sets_no_flag(registry, cfg):
    ctx = service_ctx(registry, cfg)
    ctx.scene.trades = cfg.trade.ops_per_scene
    assert buy(ctx, "room_modest").status == "rejected"
    assert "lodging:hero" not in ctx.bundle.world.flags


def test_list_lodging_does_not_set_flag(registry, cfg):
    ctx = service_ctx(registry, cfg)
    listing(ctx)
    assert "lodging:hero" not in ctx.bundle.world.flags


def test_buy_meal_sets_no_lodging_flag_and_no_signal(registry, cfg):
    ctx = service_ctx(registry, cfg)
    d = buy(ctx, "meal_modest")
    assert "lodging:hero" not in ctx.bundle.world.flags
    assert d.signal_to_master is None


def test_buy_rest_short_signal_points_to_rest_short(registry, cfg):
    ctx = service_ctx(registry, cfg, services=["bed_hour"])
    d = buy(ctx, "bed_hour")
    assert d.status == "accepted"
    assert d.signal_to_master == "Платный отдых оплачен: теперь rest short в этом же ходу."
    assert "lodging:hero" not in ctx.bundle.world.flags


def test_buy_rest_short_keeps_requested_qty(registry, cfg):
    ctx = service_ctx(registry, cfg, services=["bed_hour"])
    assert buy(ctx, "bed_hour", qty=2).result["qty"] == 2
    assert ctx.hero.money_cp == 980


def test_set_flag_cannot_forge_lodging_flag(registry, cfg):
    ctx = service_ctx(registry, cfg)
    d = apply(ctx, req("set_flag", name="lodging:hero", value="0"))
    assert isinstance(d, Invalid)
    assert d.code == "reserved_flag"
    assert "lodging:hero" not in ctx.bundle.world.flags


# У1 П1: effect = "plain", бонусы услуг (boon), компания

def barber_ctx(registry, cfg, money=1000, rng=None, services=("haircut", "shave")):
    return service_ctx(registry, cfg, money=money, rng=rng, services=services)


def effects(ctx, effect_id="groomed"):
    return [e for e in ctx.hero.creature.active_effects if e.id == effect_id]


def test_plain_service_spends_money_without_signal_or_boon(registry, cfg):
    ctx = service_ctx(registry, cfg, services=["bard_song"])
    d = buy(ctx, "bard_song")
    assert d.status == "accepted"
    assert ctx.hero.money_cp == 990
    assert d.signal_to_master is None
    assert "boon" not in d.result
    assert d.log[0].startswith("Оплачено")
    assert ctx.hero.creature.active_effects == []


def test_plain_service_spends_scene_trade(registry, cfg):
    ctx = service_ctx(registry, cfg, services=["fortune"])
    buy(ctx, "fortune")
    assert ctx.scene.trades == 1


def test_haircut_spends_two_copper_and_grants_groomed(registry, cfg):
    ctx = barber_ctx(registry, cfg)
    d = buy(ctx, "haircut")
    assert ctx.hero.money_cp == 998
    [effect] = effects(ctx)
    assert effect.expires.kind == "seconds"
    assert effect.expires.value == ctx.bundle.world.clock.now_s + 86400
    assert d.result["boon"] == "groomed"


def test_haircut_log_names_the_boon(registry, cfg):
    d = buy(barber_ctx(registry, cfg), "haircut")
    assert d.log[0].startswith("Оплачено")
    assert "Бонус: ухожен" in d.log
    assert "уже действует" not in d.log[-1]


def test_haircut_signal_tells_master_about_boon(registry, cfg):
    d = buy(barber_ctx(registry, cfg), "haircut")
    assert "ухожен" in d.signal_to_master


def test_shave_costs_one_copper_and_grants_groomed(registry, cfg):
    ctx = barber_ctx(registry, cfg)
    buy(ctx, "shave")
    assert ctx.hero.money_cp == 999
    assert len(effects(ctx)) == 1


def test_second_haircut_charges_but_does_not_double_the_boon(registry, cfg):
    ctx = barber_ctx(registry, cfg)
    buy(ctx, "haircut")
    d = buy(ctx, "haircut")
    assert d.status == "accepted"
    assert ctx.hero.money_cp == 996
    assert len(effects(ctx)) == 1
    assert "уже действует" in d.log[-1]


def test_second_groomed_service_signal_has_no_new_boon_note(registry, cfg):
    ctx = barber_ctx(registry, cfg)
    buy(ctx, "haircut")
    d = buy(ctx, "shave")
    assert not d.signal_to_master or "достался" not in d.signal_to_master


def test_haircut_without_money_is_rejected_without_boon(registry, cfg):
    ctx = barber_ctx(registry, cfg, money=1)
    d = buy(ctx, "haircut")
    assert d.status == "rejected"
    assert effects(ctx) == []
    assert ctx.hero.money_cp == 1
    assert "boon" not in (d.result or {})


def test_haircut_boon_applies_to_next_persuasion_check(registry, cfg):
    ctx = barber_ctx(registry, cfg, rng=ScriptedRng(d20=[10], d4=[3]))
    buy(ctx, "haircut")
    d = apply(ctx, req("skill_check", skill="persuasion", category="medium"))
    assert "1d4 (3)" in d.log[0]
    assert "ухожен" in d.log[0]
    assert effects(ctx) == []


def test_haircut_boon_stays_after_athletics_check(registry, cfg):
    ctx = barber_ctx(registry, cfg, rng=ScriptedRng(d20=[10]))
    buy(ctx, "haircut")
    d = apply(ctx, req("skill_check", skill="athletics", category="medium"))
    assert "ухожен" not in d.log[0]
    assert len(effects(ctx)) == 1


def test_haircut_boon_is_gone_after_a_day(registry, cfg):
    ctx = barber_ctx(registry, cfg, rng=ScriptedRng(d20=[10]))
    buy(ctx, "haircut")
    ctx.bundle.world.clock.advance(86400 + 1)
    d = apply(ctx, req("skill_check", skill="persuasion", category="medium"))
    assert "ухожен" not in d.log[0]


def test_bath_marks_hero_washed_now(registry, cfg):
    ctx = service_ctx(registry, cfg, services=["bath"])
    ctx.bundle.world.clock.advance(5000)
    d = buy(ctx, "bath")
    assert ctx.bundle.world.flags[f"washed:{ctx.hero.id}"] == 5000
    assert ctx.hero.money_cp == 990
    assert d.result["boon"] == "washed"
    assert "Бонус: чист" in d.log


def test_bath_adds_no_active_effect(registry, cfg):
    ctx = service_ctx(registry, cfg, services=["bath"])
    buy(ctx, "bath")
    assert ctx.hero.creature.active_effects == []


def test_set_flag_cannot_forge_washed_flag(registry, cfg):
    ctx = service_ctx(registry, cfg)
    d = apply(ctx, req("set_flag", name="washed:hero", value="0"))
    assert isinstance(d, Invalid)
    assert d.code == "reserved_flag"


def companion_ctx(registry, cfg, kind="companion_common", money=10000):
    ctx = service_ctx(registry, cfg, money=money, services=[kind])
    ctx.hero.heroic_inspiration = False
    return ctx


def test_companion_gives_inspiration_and_rest_short_signal(registry, cfg):
    ctx = companion_ctx(registry, cfg)
    d = buy(ctx, "companion_common")
    assert d.status == "accepted"
    assert ctx.hero.heroic_inspiration is True
    assert "rest short" in d.signal_to_master
    assert d.result["boon"] == "inspired"
    assert "Бонус: вдохновение" in d.log


def test_companion_signal_joins_rest_short_and_boon_note_with_one_space(registry, cfg):
    d = buy(companion_ctx(registry, cfg), "companion_common")
    assert d.signal_to_master == (
        "Платный отдых оплачен: теперь rest short в этом же ходу. "
        "Герою достался бонус: вдохновение."
    )


def test_companion_prices_follow_the_classes(registry, cfg):
    classes = (("companion_cheap", 20), ("companion_common", 100), ("companion_fine", 500))
    for kind, price in classes:
        ctx = companion_ctx(registry, cfg, kind)
        buy(ctx, kind)
        assert ctx.hero.money_cp == 10000 - price


def test_companion_when_already_inspired_charges_and_says_so(registry, cfg):
    ctx = companion_ctx(registry, cfg)
    ctx.hero.heroic_inspiration = True
    d = buy(ctx, "companion_common")
    assert ctx.hero.money_cp == 10000 - 100
    assert ctx.hero.heroic_inspiration is True
    assert "уже воодушевлён" in d.log[-1]
    assert "rest short" in d.signal_to_master


def test_companion_clamped_by_money_still_grants_boon(registry, cfg):
    ctx = companion_ctx(registry, cfg, "companion_cheap", money=30)
    d = buy(ctx, "companion_cheap", qty=2)
    assert d.status == "clamped"
    assert d.result["qty"] == 1
    assert ctx.hero.heroic_inspiration is True


def test_companion_without_money_gives_no_inspiration(registry, cfg):
    ctx = companion_ctx(registry, cfg, "companion_common", money=99)
    d = buy(ctx, "companion_common")
    assert d.status == "rejected"
    assert ctx.hero.heroic_inspiration is False


def test_companion_over_scene_limit_gives_no_inspiration(registry, cfg):
    ctx = companion_ctx(registry, cfg)
    ctx.scene.trades = cfg.trade.ops_per_scene
    assert buy(ctx, "companion_common").status == "rejected"
    assert ctx.hero.heroic_inspiration is False


# npc_update services

def update(ctx, npc_id="grok", **fields):
    return apply(ctx, req("npc_update", npc_id=npc_id, **fields))


def create(ctx, npc_id="cook_1", **fields):
    data = {"name": "Повар Ганс", "means": ["кухня"], "named": True}
    data.update(fields)
    return apply(ctx, req("npc_create", id=npc_id, **data))


def test_update_adds_services_to_npc(registry, cfg):
    ctx = service_ctx(registry, cfg, services=[])
    d = update(ctx, services=["room_modest"])
    assert d.status == "accepted"
    assert grok(ctx).services == ["room_modest"]
    assert d.result["services"] == ["room_modest"]


def test_update_merges_without_duplicates_keeping_order(registry, cfg):
    ctx = service_ctx(registry, cfg, services=["room_modest"])
    update(ctx, services=["ale", "room_modest", "ale"])
    assert grok(ctx).services == ["room_modest", "ale"]


def test_update_repeat_of_same_id_does_not_duplicate(registry, cfg):
    ctx = service_ctx(registry, cfg, services=["room_modest"])
    update(ctx, services=["room_modest"])
    assert grok(ctx).services == ["room_modest"]


def test_update_never_removes_services(registry, cfg):
    ctx = service_ctx(registry, cfg, services=["room_modest", "ale"])
    update(ctx, services=["meal_modest"])
    assert grok(ctx).services == ["room_modest", "ale", "meal_modest"]


def test_update_logs_services(registry, cfg):
    d = update(service_ctx(registry, cfg, services=[]), services=["room_modest", "ale"])
    assert any("оказывает" in line and "room_modest, ale" in line for line in d.log)
    assert any("Грок" in line for line in d.log)


def test_update_unknown_service_is_invalid_and_changes_nothing(registry, cfg):
    ctx = service_ctx(registry, cfg, services=[])
    before = dump(ctx)
    d = update(ctx, services=["room_modest", "castle"])
    assert isinstance(d, Invalid)
    assert d.code == "unknown_service"
    assert "castle" in d.message
    assert "room_modest" in d.message
    assert dump(ctx) == before


def test_update_with_only_services_is_not_empty(registry, cfg):
    d = update(service_ctx(registry, cfg, services=[]), services=["ale"])
    assert not (isinstance(d, Invalid) and d.code == "empty_update")


def test_update_with_empty_services_alone_is_empty_update(registry, cfg):
    d = update(service_ctx(registry, cfg), services=[])
    assert isinstance(d, Invalid)
    assert d.code == "empty_update"


def test_update_allowed_for_key_npc(registry, cfg):
    ctx = service_ctx(registry, cfg)
    d = update(ctx, npc_id="grakh", services=["ale"])
    assert d.status == "accepted"
    assert ctx.bundle.world.npcs["grakh"].services == ["ale"]


def test_update_services_have_no_scene_limit(registry, cfg):
    ctx = service_ctx(registry, cfg, services=[])
    ctx.scene.merchants_created = 5
    assert update(ctx, services=["ale"]).status == "accepted"


def test_update_services_together_with_trade_kind(registry, cfg):
    ctx = service_ctx(registry, cfg, services=[])
    d = update(ctx, services=["ale"], trade_kind="general")
    assert d.status == "accepted"
    assert grok(ctx).trade.kind == "general"
    assert grok(ctx).services == ["ale"]


def test_updated_npc_becomes_a_provider(registry, cfg):
    ctx = service_ctx(registry, cfg, services=[])
    update(ctx, services=["ale"])
    assert prices(listing(ctx)) == {"ale": 4}


def test_create_with_services(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = create(ctx, services=["meal_modest", "ale"])
    assert d.status == "accepted"
    assert ctx.bundle.world.npcs["cook_1"].services == ["meal_modest", "ale"]
    assert any("оказывает" in line for line in d.log)


def test_create_dedups_services(registry, cfg):
    ctx = make_ctx(registry, cfg)
    create(ctx, services=["ale", "ale"])
    assert ctx.bundle.world.npcs["cook_1"].services == ["ale"]


def test_create_without_services_has_none(registry, cfg):
    ctx = make_ctx(registry, cfg)
    create(ctx)
    assert ctx.bundle.world.npcs["cook_1"].services == []


def test_create_with_unknown_service_is_invalid_and_changes_nothing(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    d = create(ctx, services=["castle"])
    assert isinstance(d, Invalid)
    assert d.code == "unknown_service"
    assert dump(ctx) == before


def test_create_key_npc_with_services_is_allowed(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = create(ctx, key=True, services=["room_modest"])
    assert d.status == "accepted"
    assert ctx.bundle.world.npcs["cook_1"].services == ["room_modest"]


def test_create_with_services_and_trade_kind(registry, cfg):
    ctx = make_ctx(registry, cfg)
    create(ctx, services=["ale"], trade_kind="general")
    npc = ctx.bundle.world.npcs["cook_1"]
    assert npc.trade.kind == "general"
    assert npc.services == ["ale"]
