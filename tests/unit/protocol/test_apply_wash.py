# 182 (docs/plan-182.md): инструмент рассказчика wash{} -- герой помылся без платной услуги.
#   hero.status == "dead" -> Invalid hero_dead; иначе accepted, result
#   {"washed": True, "smelly_removed": bool}; флаг washed:<hero> = now_s (отсчёт недели заново).
#   Лог: со вонью «Вонь смыта», без вони «Помылся» (Р1 а); повтор принимается молча (Р2 а).
#   Вонь снимается, другие состояния остаются; hygiene_days = 0 на приём не влияет.
from protocol_kit import make_ctx, req

from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.rules.hygiene import washed_at
from ai_dm.state.creature import AppliedCondition

NOW = 5000


def wash_ctx(registry, cfg, *conditions):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.clock.advance(NOW - ctx.bundle.world.clock.now_s)
    for cid in conditions:
        ctx.hero.creature.conditions.append(AppliedCondition(id=cid, source="test"))
    return ctx


def ids(ctx):
    return [c.id for c in ctx.hero.creature.conditions]


def test_wash_of_smelly_hero_is_accepted(registry, cfg):
    d = apply(wash_ctx(registry, cfg, "smelly"), req("wash"))
    assert isinstance(d, Decision)
    assert d.status == "accepted"


def test_wash_of_smelly_hero_reports_removal(registry, cfg):
    d = apply(wash_ctx(registry, cfg, "smelly"), req("wash"))
    assert d.result == {"washed": True, "smelly_removed": True}


def test_wash_of_smelly_hero_logs_stench_washed_off(registry, cfg):
    d = apply(wash_ctx(registry, cfg, "smelly"), req("wash"))
    assert d.log == ["Вонь смыта"]


def test_wash_removes_smelly_from_hero(registry, cfg):
    ctx = wash_ctx(registry, cfg, "smelly")
    apply(ctx, req("wash"))
    assert ids(ctx) == []


def test_wash_keeps_other_conditions(registry, cfg):
    ctx = wash_ctx(registry, cfg, "cursed", "smelly")
    apply(ctx, req("wash"))
    assert ids(ctx) == ["cursed"]


def test_wash_marks_the_flag_with_now(registry, cfg):
    ctx = wash_ctx(registry, cfg, "smelly")
    apply(ctx, req("wash"))
    assert ctx.bundle.world.flags[f"washed:{ctx.hero.id}"] == NOW


def test_wash_overwrites_old_flag(registry, cfg):
    ctx = wash_ctx(registry, cfg, "smelly")
    ctx.bundle.world.flags[f"washed:{ctx.hero.id}"] = 10
    apply(ctx, req("wash"))
    assert washed_at(ctx.bundle.world, ctx.hero.id) == NOW


def test_wash_of_clean_hero_is_accepted_without_removal(registry, cfg):
    d = apply(wash_ctx(registry, cfg), req("wash"))
    assert d.status == "accepted"
    assert d.result == {"washed": True, "smelly_removed": False}


def test_wash_of_clean_hero_logs_washed(registry, cfg):
    d = apply(wash_ctx(registry, cfg), req("wash"))
    assert d.log == ["Помылся"]


def test_wash_of_clean_hero_resets_the_countdown(registry, cfg):
    ctx = wash_ctx(registry, cfg)
    apply(ctx, req("wash"))
    assert washed_at(ctx.bundle.world, ctx.hero.id) == NOW


def test_repeated_wash_is_accepted(registry, cfg):
    ctx = wash_ctx(registry, cfg, "smelly")
    apply(ctx, req("wash"))
    d = apply(ctx, req("wash"))
    assert d.status == "accepted"
    assert d.result == {"washed": True, "smelly_removed": False}


def test_repeated_wash_keeps_the_flag(registry, cfg):
    ctx = wash_ctx(registry, cfg, "smelly")
    apply(ctx, req("wash"))
    apply(ctx, req("wash"))
    assert washed_at(ctx.bundle.world, ctx.hero.id) == NOW


def test_wash_of_dead_hero_is_invalid(registry, cfg):
    ctx = wash_ctx(registry, cfg, "smelly")
    ctx.hero.status = "dead"
    d = apply(ctx, req("wash"))
    assert isinstance(d, Invalid)
    assert d.code == "hero_dead"


def test_wash_of_dead_hero_message_names_the_reason(registry, cfg):
    ctx = wash_ctx(registry, cfg, "smelly")
    ctx.hero.status = "dead"
    d = apply(ctx, req("wash"))
    assert d.message == "герой мёртв, мыться некому"


def test_wash_of_dead_hero_changes_nothing(registry, cfg):
    ctx = wash_ctx(registry, cfg, "smelly")
    ctx.hero.status = "dead"
    apply(ctx, req("wash"))
    assert ids(ctx) == ["smelly"]
    assert ctx.bundle.world.flags == {}


def test_wash_with_hygiene_disabled_still_writes_the_flag(registry, cfg):
    cfg0 = cfg.model_copy(deep=True)
    cfg0.services.hygiene_days = 0
    ctx = make_ctx(registry, cfg0)
    ctx.bundle.world.clock.advance(NOW - ctx.bundle.world.clock.now_s)
    d = apply(ctx, req("wash"))
    assert d.status == "accepted"
    assert washed_at(ctx.bundle.world, ctx.hero.id) == NOW
