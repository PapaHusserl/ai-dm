# Шаг 217 (docs/plan-217.md): сон перемоткой времени -- отказ, подсказка «rest long».
#   sleep_without_rest(ctx, seconds) (ai_dm.protocol.handlers.resources):
#     seconds >= cfg.time.long_rest_s,
#     в ходу не было rest, long_rest_available(ctx) -> rejected "сон без отдыха" (report_tag
#     "sleep_not_rest"); часы и ctx.until_done не меняются.
#   long_rest_available: герой жив, HP > 0, кулдаун кончился или ждать <= limits.long_rest_wait_max;
#     оплата ночлега не учитывается.
#   Охват: advance_time until=morning/hour и category=hour (count * час); day/week/month,
#     travel_to и until=long_rest не затронуты.
from protocol_kit import dump, make_ctx, req

from ai_dm.config.settings import load_rules_config
from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Invalid
from ai_dm.protocol.handlers.resources import long_rest_available, sleep_without_rest

HOUR = 3600


def ctx_at(registry, cfg, hours, minutes=0, day=1):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.clock.now_s = day * 86400 + hours * HOUR + minutes * 60
    return ctx


def until_morning():
    return req("advance_time", until="morning")


def hours(count):
    return req("advance_time", category="hour", count=count)


def long_req():
    return req("rest", kind="long")


# t1341

def test_until_morning_in_evening_is_rejected_with_tag(registry, cfg):
    ctx = ctx_at(registry, cfg, 20)
    before = dump(ctx)
    d = apply(ctx, until_morning())
    assert d.status == "rejected"
    assert d.report_tag == "sleep_not_rest"
    assert "rest long" in d.signal_to_master
    assert dump(ctx) == before
    assert ctx.until_done is False


def test_until_morning_below_threshold_is_accepted(registry, cfg):
    ctx = ctx_at(registry, cfg, 22, 30)
    assert apply(ctx, until_morning()).status == "accepted"


def test_until_morning_exactly_at_threshold_is_rejected(registry, cfg):
    ctx = ctx_at(registry, cfg, 22)
    assert apply(ctx, until_morning()).status == "rejected"


def test_until_hour_over_threshold_is_rejected(registry, cfg):
    ctx = ctx_at(registry, cfg, 7, 30)
    d = apply(ctx, req("advance_time", until="hour", until_hour=18))
    assert d.status == "rejected"
    assert d.report_tag == "sleep_not_rest"


# category=hour

def test_eight_hours_rejected_with_tag(registry, cfg):
    ctx = ctx_at(registry, cfg, 12)
    before = dump(ctx)
    d = apply(ctx, hours(8))
    assert d.status == "rejected"
    assert d.report_tag == "sleep_not_rest"
    assert dump(ctx) == before


def test_seven_hours_accepted(registry, cfg):
    assert apply(ctx_at(registry, cfg, 12), hours(7)).status == "accepted"


def test_eight_hours_after_rest_in_same_turn_accepted(registry, cfg):
    ctx = ctx_at(registry, cfg, 12)
    assert apply(ctx, long_req()).status == "accepted"
    assert apply(ctx, hours(8)).status == "accepted"


def test_eight_hours_after_idle_hour_record_is_sleep_not_time_repeat(registry, cfg):
    from test_xp_time_repeat import hour_turn, make_ctx_with

    ctx = make_ctx_with(registry, cfg, [hour_turn(4)])
    d = apply(ctx, hours(8))
    assert d.status == "rejected"
    assert d.report_tag == "sleep_not_rest"


# не затронуто

def test_day_is_accepted(registry, cfg):
    d = apply(ctx_at(registry, cfg, 12), req("advance_time", category="day", count=1))
    assert d.status == "accepted"


def test_travel_over_threshold_is_accepted(registry, cfg):
    ctx = ctx_at(registry, cfg, 12)
    ctx.bundle.world.locations["vale"].connections[0].distance_m = 200_000
    d = apply(ctx, req("advance_time", travel_to="forest"))
    assert d.status == "accepted"
    assert d.result["seconds"] >= cfg.time.long_rest_s


def test_until_after_rest_is_still_invalid(registry, cfg):
    ctx = ctx_at(registry, cfg, 20)
    assert apply(ctx, long_req()).status == "accepted"
    d = apply(ctx, until_morning())
    assert isinstance(d, Invalid)
    assert d.code == "until_with_rest"


def test_until_long_rest_with_cooldown_wait_is_accepted(registry, cfg):
    ctx = ctx_at(registry, cfg, 12)
    ctx.hero.long_rest_end_s = ctx.bundle.world.clock.now_s - 2 * HOUR
    d = apply(ctx, req("advance_time", until="long_rest"))
    assert d.status == "accepted"


# until, затем rest

def test_rest_after_rejected_sleep_has_no_tag(registry, cfg):
    ctx = ctx_at(registry, cfg, 20)
    assert apply(ctx, until_morning()).status == "rejected"
    d = apply(ctx, long_req())
    assert d.status == "accepted"
    assert d.report_tag is None


def test_short_until_then_rest_keeps_until_then_rest_tag(registry, cfg):
    ctx = ctx_at(registry, cfg, 2, 15)
    assert apply(ctx, until_morning()).status == "accepted"
    assert apply(ctx, long_req()).report_tag == "until_then_rest"


# отдых недоступен

def test_cooldown_over_wait_max_lets_shift_through(registry, cfg):
    ctx = ctx_at(registry, cfg, 20)
    ctx.hero.long_rest_end_s = ctx.bundle.world.clock.now_s
    assert apply(ctx, until_morning()).status == "accepted"


def test_zero_hp_lets_shift_through(registry, cfg):
    ctx = ctx_at(registry, cfg, 20)
    ctx.hero.creature.hp_current = 0
    assert apply(ctx, until_morning()).status == "accepted"


def test_dead_hero_lets_shift_through(registry, cfg):
    ctx = ctx_at(registry, cfg, 20)
    ctx.hero.status = "dead"
    assert apply(ctx, until_morning()).status == "accepted"


def test_cooldown_wait_within_max_is_rejected(registry, cfg):
    ctx = ctx_at(registry, cfg, 20)
    ctx.hero.long_rest_end_s = ctx.bundle.world.clock.now_s - 4 * HOUR
    assert apply(ctx, until_morning()).status == "rejected"


def test_cooldown_wait_just_over_max_lets_shift_through(registry, cfg):
    ctx = ctx_at(registry, cfg, 20)
    ctx.hero.long_rest_end_s = ctx.bundle.world.clock.now_s - 4 * HOUR + 1
    assert apply(ctx, until_morning()).status == "accepted"


def test_long_rest_available_is_false_for_dead_and_true_for_fresh(registry, cfg):
    ctx = ctx_at(registry, cfg, 20)
    assert long_rest_available(ctx) is True
    ctx.hero.status = "dead"
    assert long_rest_available(ctx) is False


def test_sleep_without_rest_none_below_threshold(registry, cfg):
    ctx = ctx_at(registry, cfg, 20)
    assert sleep_without_rest(ctx, cfg.time.long_rest_s - 1) is None
    assert sleep_without_rest(ctx, cfg.time.long_rest_s).status == "rejected"


# трактир: ночлег не оплачен -- отдых считается доступным

def test_unpaid_inn_rejects_sleep_then_rest_says_lodging_paid(registry, cfg):
    from test_apply_rest_lodging import inn_ctx

    ctx = inn_ctx(registry, cfg)
    ctx.bundle.world.clock.now_s = 86400 + 20 * HOUR
    first = apply(ctx, until_morning())
    assert first.report_tag == "sleep_not_rest"
    second = apply(ctx, long_req())
    assert second.status == "rejected"
    assert second.report_tag == "rest_unpaid"
    assert "Ночлег платный" in second.signal_to_master


# тексты отказа

def test_sleep_rejection_reason_and_signal_text(registry, cfg):
    d = sleep_without_rest(ctx_at(registry, cfg, 20), cfg.time.long_rest_s)
    assert d.reason == "сон без отдыха"
    assert d.signal_to_master == (
        "Это сон: время не двигай, вызови rest long в этом же ходу — отдых сам сдвинет "
        "часы и восстановит HP и ресурсы."
    )


# until=long_rest не считается сном, даже если ждать >= порога сна

def test_until_long_rest_with_wait_over_threshold_is_accepted(registry, cfg):
    ctx = ctx_at(registry, cfg, 20)
    ctx.hero.long_rest_end_s = ctx.bundle.world.clock.now_s - 4 * HOUR
    d = apply(ctx, req("advance_time", until="long_rest"))
    assert d.status == "accepted"
    assert d.result["seconds"] >= cfg.time.long_rest_s


# порог из конфига

def test_threshold_comes_from_config(registry):
    cfg = load_rules_config("[time]\nlong_rest_s = 36000\n")
    assert apply(ctx_at(registry, cfg, 21), until_morning()).status == "accepted"
    assert apply(ctx_at(registry, cfg, 20), until_morning()).status == "rejected"
