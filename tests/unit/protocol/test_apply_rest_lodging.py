# У0 П2 (docs/plan-u0.md): длинный отдых там, где NPC сдаёт комнаты
# (handlers.resources:lodging_unpaid).
#   rest long при cfg.services.paid_rest и живом NPC с lodging в локации героя принимается только
#       после оплаченного ночлега (флаг lodging:<hero> == сегодня); без оплаты -- rejected
#       "ночлег платный" (report_tag rest_unpaid, подсказка service). Нет денег даже на самую
#       дешёвую комнату -- отдых свободен. Принятый rest long снимает флаг.
#   Не затронуты: короткий отдых, paid_rest = false, локация без lodging-NPC, мёртвый NPC.
#   Оплата действует до morning_hour следующего дня. Учитываются только комнаты по карману;
#       если все такие хозяева отказывают по отношению -- rejected "комнату не сдадут".
#   Порядок проверок: rest_redundant (кулдаун) раньше оплаты.
from protocol_kit import dump, make_ctx, req

from ai_dm.config.settings import load_rules_config
from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision
from ai_dm.rules.trade import DAY_S
from ai_dm.state.world import NPC


def inn_ctx(registry, cfg, money=100, services=("room_modest",), location_id="vale", **fields):
    ctx = make_ctx(registry, cfg)
    ctx.hero.money_cp = money
    ctx.bundle.world.npcs["grok"] = NPC(
        id="grok", name="Грок", means=["трактир"], services=list(services),
        location_id=location_id, **fields,
    )
    return ctx


def long_rest(ctx):
    return apply(ctx, req("rest", kind="long"))


def pay(ctx, service_id="room_modest"):
    return apply(
        ctx, req("service", npc_id="grok", direction="buy", service_id=service_id, qty=1)
    )


def flags(ctx):
    return ctx.bundle.world.flags


# без оплаты

def test_unpaid_long_rest_is_rejected(registry, cfg):
    d = long_rest(inn_ctx(registry, cfg))
    assert isinstance(d, Decision)
    assert d.status == "rejected"
    assert d.reason == "ночлег платный"
    assert d.report_tag == "rest_unpaid"


def test_unpaid_signal_names_service_buy_and_npc(registry, cfg):
    d = long_rest(inn_ctx(registry, cfg))
    assert "service buy room_modest у grok" in d.signal_to_master
    assert "rest long" in d.signal_to_master


def test_unpaid_rejection_changes_nothing(registry, cfg):
    ctx = inn_ctx(registry, cfg)
    before = dump(ctx)
    long_rest(ctx)
    assert dump(ctx) == before
    assert ctx.hero.long_rest_end_s is None


def test_unpaid_hint_names_the_cheapest_room(registry, cfg):
    ctx = inn_ctx(registry, cfg, services=["room_wealthy", "room_modest", "room_poor"])
    assert "service buy room_poor у grok" in long_rest(ctx).signal_to_master


def test_unpaid_with_money_exactly_for_cheapest_is_rejected(registry, cfg):
    assert long_rest(inn_ctx(registry, cfg, money=50)).status == "rejected"


def test_unpaid_cheapest_uses_attitude_price(registry, cfg):
    # скромная комната при хорошем отношении: 45; денег 45 -- хватает, значит отказ
    assert long_rest(inn_ctx(registry, cfg, money=45, attitude=60)).status == "rejected"


def test_unpaid_money_one_short_of_cheapest_is_allowed(registry, cfg):
    assert long_rest(inn_ctx(registry, cfg, money=49)).status == "accepted"


def test_no_money_for_cheapest_room_rest_is_free(registry, cfg):
    ctx = inn_ctx(registry, cfg, money=5, services=["room_poor", "room_modest"])
    d = long_rest(ctx)
    assert d.status == "accepted"
    assert ctx.hero.money_cp == 5


def test_money_enough_for_cheapest_but_not_for_dearer_is_rejected(registry, cfg):
    ctx = inn_ctx(registry, cfg, money=10, services=["room_wealthy", "room_poor"])
    assert long_rest(ctx).status == "rejected"


# оплата -> отдых

def test_pay_then_rest_is_accepted(registry, cfg):
    ctx = inn_ctx(registry, cfg)
    pay(ctx)
    assert long_rest(ctx).status == "accepted"
    assert ctx.hero.long_rest_end_s is not None


def test_pay_sets_flag_and_spends_money(registry, cfg):
    ctx = inn_ctx(registry, cfg)
    pay(ctx)
    assert flags(ctx)["lodging:hero"] == 0
    assert ctx.hero.money_cp == 50


def test_accepted_long_rest_clears_the_flag(registry, cfg):
    ctx = inn_ctx(registry, cfg)
    pay(ctx)
    long_rest(ctx)
    assert "lodging:hero" not in flags(ctx)


def test_rest_does_not_charge_money_itself(registry, cfg):
    ctx = inn_ctx(registry, cfg)
    pay(ctx)
    long_rest(ctx)
    assert ctx.hero.money_cp == 50


def test_clearing_flag_keeps_other_flags(registry, cfg):
    ctx = inn_ctx(registry, cfg)
    flags(ctx)["met_aldric"] = True
    flags(ctx)["lodging:other"] = 0
    pay(ctx)
    long_rest(ctx)
    assert flags(ctx)["met_aldric"] is True
    assert flags(ctx)["lodging:other"] == 0


def test_second_long_rest_after_cooldown_needs_new_payment(registry, cfg):
    ctx = inn_ctx(registry, cfg)
    pay(ctx)
    long_rest(ctx)
    ctx.bundle.world.clock.advance(DAY_S)
    assert long_rest(ctx).status == "rejected"


def test_old_flag_does_not_count(registry, cfg):
    ctx = inn_ctx(registry, cfg)
    flags(ctx)["lodging:hero"] = -2
    assert long_rest(ctx).status == "rejected"


def test_payment_in_evening_covers_rest_after_midnight(registry, cfg):
    ctx = inn_ctx(registry, cfg)
    ctx.bundle.world.clock.advance(20 * 3600)
    pay(ctx)
    ctx.bundle.world.clock.advance(7 * 3600)  # 03:00 следующих суток
    assert long_rest(ctx).status == "accepted"


def test_payment_does_not_cover_rest_after_morning(registry, cfg):
    ctx = inn_ctx(registry, cfg)
    ctx.bundle.world.clock.advance(20 * 3600)
    pay(ctx)
    ctx.bundle.world.clock.advance(11 * 3600)  # 07:00 следующих суток
    d = long_rest(ctx)
    assert d.status == "rejected"
    assert d.report_tag == "rest_unpaid"


def test_payment_at_2am_covers_rest_until_morning_of_next_day(registry, cfg):
    # текущее поведение: флаг -- день оплаты, оплата в 02:00 действует до 06:00 следующих суток
    ctx = inn_ctx(registry, cfg)
    ctx.bundle.world.clock.advance(2 * 3600)
    pay(ctx)
    ctx.bundle.world.clock.advance(DAY_S + 3 * 3600)  # 05:00 следующих суток
    assert long_rest(ctx).status == "accepted"


def test_non_int_flag_means_unpaid(registry, cfg):
    ctx = inn_ctx(registry, cfg)
    flags(ctx)["lodging:hero"] = "0"
    assert long_rest(ctx).status == "rejected"


# хозяин отказывает по отношению

def test_only_provider_refuses_with_money_is_rejected_not_sold(registry, cfg):
    d = long_rest(inn_ctx(registry, cfg, attitude=-60))
    assert d.status == "rejected"
    assert d.reason == "комнату не сдадут"
    assert d.report_tag == "rest_unpaid"
    assert "в другом месте" in d.signal_to_master
    assert "service buy" not in d.signal_to_master


def test_refusal_signal_text_is_full(registry, cfg):
    d = long_rest(inn_ctx(registry, cfg, attitude=-60))
    assert d.signal_to_master == (
        "Здесь герою комнату не сдадут (хозяин отказывает): скажи игроку, что отдыхать "
        "нужно в другом месте."
    )


def test_unpaid_signal_mentions_service_list_alternative(registry, cfg):
    d = long_rest(inn_ctx(registry, cfg))
    assert d.signal_to_master.startswith("Ночлег платный: сначала service buy")
    assert d.signal_to_master.endswith(
        "(или другая комната из service list), затем rest long в этом же ходу."
    )


def test_refusing_provider_without_money_rest_is_free(registry, cfg):
    assert long_rest(inn_ctx(registry, cfg, money=5, attitude=-60)).status == "accepted"


def test_hint_names_second_provider_when_cheapest_refuses(registry, cfg):
    ctx = inn_ctx(registry, cfg, services=["room_poor"], attitude=-60)
    ctx.bundle.world.npcs["mara"] = NPC(
        id="mara", name="Мара", means=["трактир"], services=["room_modest"],
        location_id="vale",
    )
    d = long_rest(ctx)
    assert d.reason == "ночлег платный"
    assert "service buy room_modest у mara" in d.signal_to_master


def test_unaffordable_room_is_not_suggested(registry, cfg):
    ctx = inn_ctx(registry, cfg, money=60, services=["room_wealthy", "room_modest"])
    assert "service buy room_modest у grok" in long_rest(ctx).signal_to_master


def test_refusing_provider_unaffordable_second_does_not_hide_refusal(registry, cfg):
    # отказывает единственный, кого можно оплатить; дорогой другой NPC не по карману
    ctx = inn_ctx(registry, cfg, money=60, services=["room_modest"], attitude=-60)
    ctx.bundle.world.npcs["mara"] = NPC(
        id="mara", name="Мара", means=["трактир"], services=["room_wealthy"],
        location_id="vale",
    )
    assert long_rest(ctx).reason == "комнату не сдадут"


def test_failed_rest_keeps_the_paid_flag(registry, cfg):
    # герой с 0 HP: long_rest бросает ValueError -> Invalid, ночлег остаётся оплаченным
    ctx = inn_ctx(registry, cfg)
    pay(ctx)
    ctx.hero.creature.hp_current = 0
    assert long_rest(ctx).code == "rest_impossible"
    assert flags(ctx)["lodging:hero"] == 0


# где ночлег не платный

def test_short_rest_needs_no_lodging(registry, cfg):
    assert apply(inn_ctx(registry, cfg), req("rest", kind="short")).status == "accepted"


def test_paid_rest_off_keeps_old_behaviour(registry):
    cfg = load_rules_config("[services]\npaid_rest = false\n")
    ctx = inn_ctx(registry, cfg)
    assert long_rest(ctx).status == "accepted"


def test_location_without_lodging_npc_rest_is_free(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.hero.money_cp = 100
    assert long_rest(ctx).status == "accepted"


def test_lodging_npc_in_another_location_rest_is_free(registry, cfg):
    assert long_rest(inn_ctx(registry, cfg, location_id="forest")).status == "accepted"


def test_dead_lodging_npc_rest_is_free(registry, cfg):
    assert long_rest(inn_ctx(registry, cfg, status="dead")).status == "accepted"


def test_npc_with_only_meals_rest_is_free(registry, cfg):
    ctx = inn_ctx(registry, cfg, services=["meal_modest", "bed_hour"])
    assert long_rest(ctx).status == "accepted"


# порядок проверок

def test_cooldown_beats_payment_and_charges_nothing(registry, cfg):
    ctx = inn_ctx(registry, cfg)
    pay(ctx)
    long_rest(ctx)
    ctx.bundle.world.clock.now_s = ctx.hero.long_rest_end_s + 60
    pay(ctx)
    money = ctx.hero.money_cp
    d = long_rest(ctx)
    assert d.report_tag == "rest_repeat"
    assert ctx.hero.money_cp == money


def test_cooldown_rejection_without_payment_is_rest_repeat_not_unpaid(registry, cfg):
    ctx = inn_ctx(registry, cfg)
    ctx.hero.long_rest_end_s = 1000
    ctx.bundle.world.clock.now_s = 1000
    assert long_rest(ctx).report_tag == "rest_repeat"
