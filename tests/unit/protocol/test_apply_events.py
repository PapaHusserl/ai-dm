# Ожидаемый API: ai_dm.protocol.apply.apply -- event_start / event_end (ТЗ 4.1.2, П5 этапа 3).
# Контракт protocol_kit.py. Запросы доступны и нарратору (explore), и роли world.
#   * event_start war|plague: cause обязателен и должен быть ref сработавшего триггера
#     (world.fired); без cause или с несработавшим -> Decision rejected, мир не меняется;
#     сработавший -> accepted, событие в world.events (cause, regions, started_s = сейчас) и запись
#     хроники kind "event" с id события в refs; неизвестный регион -> Invalid unknown_location;
#     повторный id -> Invalid duplicate_event;
#   * event_end: неизвестное событие -> Invalid unknown_event; известное -> закрыто (event_active
#     FALSE), запись хроники.
import pytest
from protocol_kit import dump, make_ctx, req

from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.rules.triggers_eval import Truth, evaluate
from ai_dm.state.triggers import EventActive
from ai_dm.state.world import FiredTrigger

FIRED = "trigger:morrah:send_plague"
MODES = ["explore", "world"]


def fired_ctx(registry, cfg, mode):
    ctx = make_ctx(registry, cfg, mode=mode)
    ctx.bundle.world.fired.append(FiredTrigger(ref=FIRED, at_s=0))
    return ctx


def start(ctx, event_id="plague_1", event_type="plague", cause=FIRED, **fields):
    fields.setdefault("regions", ["vale"])
    return apply(
        ctx, req("event_start", id=event_id, event_type=event_type, cause=cause, **fields)
    )


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("event_type", ["war", "plague"])
def test_start_without_cause_is_rejected(mode, event_type, registry, cfg):
    ctx = fired_ctx(registry, cfg, mode)
    before = dump(ctx)
    d = start(ctx, "e1", event_type, cause="")
    assert isinstance(d, Decision)
    assert d.status == "rejected"
    assert d.signal_to_master
    assert dump(ctx) == before


@pytest.mark.parametrize("mode", MODES)
def test_start_with_unfired_trigger_is_rejected(mode, registry, cfg):
    ctx = fired_ctx(registry, cfg, mode)
    before = dump(ctx)
    d = start(ctx, "e1", "war", cause="trigger:morrah:never_fired")
    assert d.status == "rejected"
    assert d.signal_to_master
    assert dump(ctx) == before


@pytest.mark.parametrize("mode", MODES)
def test_start_with_free_text_cause_is_rejected(mode, registry, cfg):
    ctx = fired_ctx(registry, cfg, mode)
    d = start(ctx, "e1", "war", cause="так захотелось")
    assert d.status == "rejected"
    assert ctx.bundle.world.events == []


@pytest.mark.parametrize("mode", MODES)
def test_start_with_fired_trigger_is_accepted(mode, registry, cfg):
    ctx = fired_ctx(registry, cfg, mode)
    d = start(ctx, regions=["vale"])
    assert isinstance(d, Decision)
    assert d.status == "accepted"
    [event] = ctx.bundle.world.events
    assert event.id == "plague_1"
    assert event.type == "plague"
    assert event.cause == FIRED
    assert event.regions == ["vale"]
    assert event.started_s == ctx.bundle.world.clock.now_s


@pytest.mark.parametrize("mode", MODES)
def test_started_event_is_active_and_in_chronicle(mode, registry, cfg):
    ctx = fired_ctx(registry, cfg, mode)
    start(ctx)
    assert evaluate(EventActive(event="plague_1"), ctx.bundle.world).truth == Truth.TRUE
    entries = [e for e in ctx.bundle.chronicle.entries if e.kind == "event"]
    assert any("plague_1" in e.refs for e in entries)


@pytest.mark.parametrize("mode", MODES)
def test_rejected_start_leaves_no_chronicle_entry(mode, registry, cfg):
    ctx = fired_ctx(registry, cfg, mode)
    start(ctx, cause="")
    assert ctx.bundle.chronicle.entries == []


@pytest.mark.parametrize("mode", MODES)
def test_start_with_unknown_region_is_invalid(mode, registry, cfg):
    ctx = fired_ctx(registry, cfg, mode)
    d = start(ctx, regions=["atlantis"])
    assert isinstance(d, Invalid)
    assert d.code == "unknown_location"
    assert ctx.bundle.world.events == []


@pytest.mark.parametrize("mode", MODES)
def test_start_with_repeated_id_is_invalid(mode, registry, cfg):
    ctx = fired_ctx(registry, cfg, mode)
    start(ctx)
    d = start(ctx)
    assert isinstance(d, Invalid)
    assert d.code == "duplicate_event"
    assert len(ctx.bundle.world.events) == 1


@pytest.mark.parametrize("mode", MODES)
def test_event_start_does_not_roll_dice(mode, registry, cfg):
    ctx = fired_ctx(registry, cfg, mode)
    draws = ctx.rng.draws
    start(ctx)
    assert ctx.rng.draws == draws


# event_end

@pytest.mark.parametrize("mode", MODES)
def test_end_of_unknown_event_is_invalid(mode, registry, cfg):
    ctx = fired_ctx(registry, cfg, mode)
    before = dump(ctx)
    d = apply(ctx, req("event_end", id="nothing"))
    assert isinstance(d, Invalid)
    assert d.code == "unknown_event"
    assert dump(ctx) == before


@pytest.mark.parametrize("mode", MODES)
def test_end_closes_event(mode, registry, cfg):
    ctx = fired_ctx(registry, cfg, mode)
    start(ctx)
    ctx.bundle.world.clock.advance(3600)
    d = apply(ctx, req("event_end", id="plague_1"))
    assert d.status == "accepted"
    assert evaluate(EventActive(event="plague_1"), ctx.bundle.world).truth == Truth.FALSE


@pytest.mark.parametrize("mode", MODES)
def test_end_then_tick_writes_one_chronicle_entry_and_one_event(mode, registry, cfg):
    from ai_dm.core.clock import DAY
    from ai_dm.world_sim.tick import tick_days

    ctx = fired_ctx(registry, cfg, mode)
    ctx.bundle.world.mortality_per_day = 500000
    start(ctx)
    ctx.bundle.world.clock.advance(3600)
    apply(ctx, req("event_end", id="plague_1"))
    entries = [e for e in ctx.bundle.chronicle.entries if "plague_1" in e.refs]
    assert len(entries) == 1
    ctx.bundle.world.clock.advance(DAY)
    ctx.bundle.heroes[0].status = "in_afterlife"
    ctx.bundle.world.npcs.clear()
    done = tick_days(ctx.bundle, ctx.rng, cfg, registry)
    entries = [e for e in ctx.bundle.chronicle.entries if "plague_1" in e.refs]
    assert len(entries) == 2
    assert [e.type for e in done].count("event_ended") == 1


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("event_type, multiplier", [("plague", 20), ("war", 5)])
def test_model_event_gets_multiplier_from_config(mode, event_type, multiplier, registry, cfg):
    ctx = fired_ctx(registry, cfg, mode)
    start(ctx, event_type=event_type)
    assert ctx.bundle.world.events[0].mortality_multiplier == multiplier


@pytest.mark.parametrize("mode", MODES)
def test_model_event_multiplier_is_overridden_by_config(mode, registry, cfg):
    wide = cfg.model_copy(deep=True)
    wide.world.event_multipliers["plague"] = 3
    ctx = make_ctx(registry, wide, mode=mode)
    ctx.bundle.world.fired.append(FiredTrigger(ref=FIRED, at_s=0))
    start(ctx)
    assert ctx.bundle.world.events[0].mortality_multiplier == 3


@pytest.mark.parametrize("mode", MODES)
def test_unlisted_event_type_has_multiplier_one(mode, registry, cfg):
    ctx = fired_ctx(registry, cfg, mode)
    start(ctx, event_type="festival", cause="")
    assert ctx.bundle.world.events[0].mortality_multiplier == 1


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("event_type", ["war", "plague"])
def test_war_and_plague_without_regions_are_invalid(mode, event_type, registry, cfg):
    ctx = fired_ctx(registry, cfg, mode)
    d = start(ctx, event_type=event_type, regions=[])
    assert isinstance(d, Invalid)
    assert ctx.bundle.world.events == []
