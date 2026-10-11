# Ожидаемый API (П6б этапа 3, STAGE3-PLAN A9, решение G2а, ТЗ 2.3 «Бой»): start_combat и бюджет боя.
#   Бюджет -- уровень «Moderate» SRD 5.2 на героя (ур. 1 -- 75 ПО; гоблин-воин 1/4 -- 50 ПО).
#   Сверх бюджета без оснований -> убираются враги с конца списка, лидер группы остаётся:
#   Decision clamped, report_tag "limit-exceeded", signal_to_master, бой создаётся урезанным.
#   Основания без урезания (accepted, CombatState.budget_override_reason):
#     warn_danger по локации героя или её предку -> "warn_danger";
#     start_combat.initiated_by == "hero" (по умолчанию "enemies") -> "hero";
#     в world.fired триггер с kills_hero за последние сутки -> "kills_hero";
#     один лидер не влезает в бюджет -> бой без урезания, "leader".
#   max_enemies (6) остаётся вторым пределом. warn_danger{location_id, text} -> DangerMark и флаг
#   danger:<loc>; доступен нарратору (explore) и роли world; префикс danger: зарезервирован
#   для set_flag.
from protocol_kit import combat_request, dump, goblin, make_ctx, req, zone

from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.state.triggers import Trigger
from ai_dm.state.world import DangerMark, FiredTrigger

DAY = 86400


def four_goblins(**kwargs):
    enemies = [goblin(f"g{n}") for n in range(1, 5)]
    return combat_request(enemies=enemies, initiated_by="enemies", **kwargs)


def combat_with(registry, cfg, enemies, **fields):
    ctx = make_ctx(registry, cfg)
    zones = [zone("door", ["hall"]), zone("hall", ["door", "balcony"]), zone("balcony", ["hall"])]
    groups = [{"id": "goblins", "leader": "g1", "intent": "kill"}]
    request = req(
        "start_combat", zones=zones, enemies=enemies, groups=groups, hero_zone="door", **fields
    )
    return ctx, apply(ctx, request)


def refs_of(ctx):
    state = ctx.bundle.session.active_combat
    return [p.ref for p in state.participants if p.side == "enemies"]


def two_goblins():
    return [goblin("g1"), goblin("g2")]


# урезание

def test_four_goblins_level_1_are_clamped(registry, cfg):
    ctx, d = combat_with(registry, cfg, [goblin(f"g{n}") for n in range(1, 5)])
    assert isinstance(d, Decision)
    assert d.status == "clamped"
    assert d.report_tag == "limit-exceeded"
    assert d.signal_to_master
    assert len(refs_of(ctx)) < 4


def test_clamp_keeps_leader_and_cuts_from_the_end(registry, cfg):
    ctx, _ = combat_with(registry, cfg, [goblin(f"g{n}") for n in range(1, 5)])
    refs = refs_of(ctx)
    assert refs[0] == "g1"
    assert refs == [f"g{n}" for n in range(1, len(refs) + 1)]


def test_clamp_result_fits_moderate_budget_level_1(registry, cfg):
    ctx, _ = combat_with(registry, cfg, [goblin(f"g{n}") for n in range(1, 5)])
    assert len(refs_of(ctx)) == 1


def test_two_goblins_level_1_exceed_moderate_budget(registry, cfg):
    # G2а: потолок -- Moderate (75), а не High (100): 2 x 50 ПО урезаются до одного
    ctx, d = combat_with(registry, cfg, two_goblins())
    assert d.status == "clamped"
    assert refs_of(ctx) == ["g1"]


def test_one_goblin_level_1_fits_budget(registry, cfg):
    ctx, d = combat_with(registry, cfg, [goblin("g1")])
    assert d.status == "accepted"
    assert d.report_tag is None
    assert ctx.bundle.session.active_combat.budget_override_reason is None


def test_clamped_combat_has_no_override_reason(registry, cfg):
    ctx, _ = combat_with(registry, cfg, two_goblins())
    assert ctx.bundle.session.active_combat.budget_override_reason is None


def test_clamped_combat_marks_limit_exceeded(registry, cfg):
    ctx, _ = combat_with(registry, cfg, two_goblins())
    assert "limit-exceeded" in ctx.marks


def test_higher_level_has_bigger_budget(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.hero.sheet.primary.level = 5
    enemies = [goblin(f"g{n}") for n in range(1, 5)]
    d = apply(ctx, combat_request(enemies=enemies, initiated_by="enemies"))
    assert d.status == "accepted"
    assert len(refs_of(ctx)) == 4


def test_clamped_combat_group_keeps_leader(registry, cfg):
    ctx, _ = combat_with(registry, cfg, [goblin(f"g{n}") for n in range(1, 5)])
    assert ctx.bundle.session.active_combat.groups["goblins"].leader_id == "g1"


# лидер не влезает

def test_leaders_over_budget_stay_alone_and_rank_and_file_is_cut(registry, cfg):
    boss = {"ref": "boss", "monster_id": "goblin_boss", "zone": "hall", "group": "goblins"}
    ctx = make_ctx(registry, cfg)
    request = combat_request(
        enemies=[boss, goblin("g1")], initiated_by="enemies",
        groups=[{"id": "goblins", "leader": "boss", "intent": "kill"}],
    )
    d = apply(ctx, request)
    assert isinstance(d, Decision)
    state = ctx.bundle.session.active_combat
    assert state.budget_override_reason == "leader"
    assert refs_of(ctx) == ["boss"]


# основания без урезания

def test_initiated_by_hero_is_not_clamped(registry, cfg):
    ctx, d = combat_with(registry, cfg, [goblin(f"g{n}") for n in range(1, 5)], initiated_by="hero")
    assert d.status == "accepted"
    assert len(refs_of(ctx)) == 4
    assert ctx.bundle.session.active_combat.budget_override_reason == "hero"


def test_initiated_by_enemies_is_clamped(registry, cfg):
    ctx, d = combat_with(registry, cfg, two_goblins(), initiated_by="enemies")
    assert d.status == "clamped"


def test_warn_danger_on_hero_location_lifts_clamp(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.dangers.append(DangerMark(location_id="vale", text="кости", at_s=0))
    d = apply(ctx, four_goblins())
    assert d.status == "accepted"
    assert len(refs_of(ctx)) == 4
    assert ctx.bundle.session.active_combat.budget_override_reason == "warn_danger"


def test_warn_danger_on_parent_location_lifts_clamp(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.hero.location_id = "vale_tavern"
    ctx.bundle.world.dangers.append(DangerMark(location_id="vale", text="кости", at_s=0))
    d = apply(ctx, four_goblins())
    assert d.status == "accepted"
    assert ctx.bundle.session.active_combat.budget_override_reason == "warn_danger"


def test_warn_danger_on_other_location_does_not_lift_clamp(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.dangers.append(DangerMark(location_id="forest", text="кости", at_s=0))
    d = apply(ctx, four_goblins())
    assert d.status == "clamped"


def test_warn_danger_request_then_combat_is_not_clamped(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert apply(ctx, req("warn_danger", location_id="vale", text="следы")).status == "accepted"
    d = apply(ctx, four_goblins())
    assert d.status == "accepted"
    assert len(refs_of(ctx)) == 4


def add_kill_trigger(ctx, at_s):
    ctx.bundle.world.npcs["grakh"].opportunity.append(
        Trigger.model_validate(
            {"id": "hunt", "if": {"flag": "x"}, "then": "убить героя", "kills_hero": True}
        )
    )
    ctx.bundle.world.fired.append(FiredTrigger(ref="trigger:grakh:hunt", at_s=at_s))


def test_fired_kills_hero_trigger_lifts_clamp(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.clock.now_s = 5 * DAY
    add_kill_trigger(ctx, 5 * DAY - 3600)
    d = apply(ctx, four_goblins())
    assert d.status == "accepted"
    assert len(refs_of(ctx)) == 4
    assert ctx.bundle.session.active_combat.budget_override_reason == "kills_hero"


def test_old_kills_hero_trigger_does_not_lift_clamp(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.clock.now_s = 5 * DAY
    add_kill_trigger(ctx, 2 * DAY)
    d = apply(ctx, four_goblins())
    assert d.status == "clamped"


def test_max_enemies_limit_still_applies_with_override(registry, cfg):
    ctx = make_ctx(registry, cfg)
    enemies = [goblin(f"g{n}") for n in range(1, 8)]
    ctx.bundle.world.dangers.append(DangerMark(location_id="vale", text="кости", at_s=0))
    d = apply(ctx, combat_request(enemies=enemies, initiated_by="enemies"))
    assert d.status == "clamped"
    assert d.report_tag == "limit-exceeded"
    assert len(refs_of(ctx)) == cfg.limits.max_enemies


# warn_danger

def test_warn_danger_creates_mark_and_flag(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("warn_danger", location_id="goblin_den", text="кости у входа"))
    assert d.status == "accepted"
    marks = ctx.bundle.world.dangers
    assert [(m.location_id, m.text) for m in marks] == [("goblin_den", "кости у входа")]
    assert ctx.bundle.world.flags["danger:goblin_den"] is True


def test_warn_danger_unknown_location_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, req("warn_danger", location_id="nowhere", text="кости"))
    assert isinstance(d, Invalid)
    assert dump(ctx) == before


def test_warn_danger_in_world_mode_is_accepted(registry, cfg):
    ctx = make_ctx(registry, cfg, mode="world")
    d = apply(ctx, req("warn_danger", location_id="goblin_den", text="кости"))
    assert isinstance(d, Decision)
    assert d.status == "accepted"
    assert len(ctx.bundle.world.dangers) == 1


def test_set_flag_danger_prefix_is_reserved(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, req("set_flag", name="danger:vale", value="true"))
    assert isinstance(d, Invalid)
    assert d.code == "reserved_flag"
    assert dump(ctx) == before


# D1: основание сверх бюджета в логе

def test_override_reason_is_written_to_log(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.dangers.append(DangerMark(location_id="vale", text="кости", at_s=0))
    d = apply(ctx, four_goblins())
    assert "Бой сверх бюджета: было предупреждение об опасности" in d.log


def test_initiated_by_hero_reason_is_written_to_log(registry, cfg):
    ctx, d = combat_with(registry, cfg, two_goblins(), initiated_by="hero")
    assert any("Бой сверх бюджета" in line and "напал ты" in line for line in d.log)


def test_fitting_combat_has_no_override_line_in_log(registry, cfg):
    ctx, d = combat_with(registry, cfg, [goblin("g1")])
    assert not any("сверх бюджета" in line for line in d.log)


# M: двойное урезание (бюджет и max_enemies) -- оба сигнала

def test_double_clamp_mentions_both_budget_and_max_enemies(registry, cfg):
    ctx, d = combat_with(registry, cfg, [goblin(f"g{n}") for n in range(1, 9)])
    assert d.status == "clamped"
    assert d.report_tag == "limit-exceeded"
    assert "бюджет" in d.signal_to_master.lower()
    assert str(cfg.limits.max_enemies) in d.signal_to_master


# B1-B3: бюджет боя виден игроку

def test_start_line_has_budget_level_tier_and_enemy_cost(registry, cfg):
    ctx, d = combat_with(registry, cfg, [goblin("g1")])
    assert "Бюджет боя: 75 ПО (ур. 1, умеренный); враги: 50 ПО (Воин-гоблин 50 ×1)" in d.log


def test_start_line_counts_enemies_by_kind(registry, cfg):
    ctx, d = combat_with(registry, cfg, two_goblins(), initiated_by="hero")
    assert "Бюджет боя: 75 ПО (ур. 1, умеренный); враги: 100 ПО (Воин-гоблин 50 ×2)" in d.log


def test_start_line_goes_before_override_reason(registry, cfg):
    ctx, d = combat_with(registry, cfg, two_goblins(), initiated_by="hero")
    budget = [n for n, line in enumerate(d.log) if line.startswith("Бюджет боя")]
    reason = [n for n, line in enumerate(d.log) if line.startswith("Бой сверх бюджета")]
    assert budget and reason and budget[0] < reason[0]


def test_clamped_combat_lists_who_did_not_join(registry, cfg):
    ctx, d = combat_with(registry, cfg, two_goblins())
    assert "Не вступили в бой (сверх бюджета): Воин-гоблин ×1" in d.log


def test_clamped_combat_budget_line_counts_only_who_joined(registry, cfg):
    ctx, d = combat_with(registry, cfg, two_goblins())
    assert "Бюджет боя: 75 ПО (ур. 1, умеренный); враги: 50 ПО (Воин-гоблин 50 ×1)" in d.log


def test_clamped_combat_groups_dropped_by_kind(registry, cfg):
    ctx, d = combat_with(registry, cfg, [goblin(f"g{n}") for n in range(1, 5)])
    assert "Не вступили в бой (сверх бюджета): Воин-гоблин ×3" in d.log


def test_fitting_combat_has_no_did_not_join_line(registry, cfg):
    ctx, d = combat_with(registry, cfg, [goblin("g1")])
    assert not any("Не вступили" in line for line in d.log)


def test_override_reason_has_no_raw_code(registry, cfg):
    ctx, d = combat_with(registry, cfg, two_goblins(), initiated_by="hero")
    line = [x for x in d.log if x.startswith("Бой сверх бюджета")][0]
    assert line == "Бой сверх бюджета: напал ты"


def test_warn_danger_reason_is_in_words(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.dangers.append(DangerMark(location_id="vale", text="кости", at_s=0))
    d = apply(ctx, four_goblins())
    assert "Бой сверх бюджета: было предупреждение об опасности" in d.log


def test_kills_hero_reason_is_in_words(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.clock.now_s = 5 * DAY
    add_kill_trigger(ctx, 5 * DAY - 3600)
    d = apply(ctx, four_goblins())
    assert "Бой сверх бюджета: сюжетная угроза" in d.log


def test_leader_reason_is_in_words_and_cut_rank_and_file_is_listed(registry, cfg):
    boss = {"ref": "boss", "monster_id": "goblin_boss", "zone": "hall", "group": "goblins"}
    ctx = make_ctx(registry, cfg)
    request = combat_request(
        enemies=[boss, goblin("g1")], initiated_by="enemies",
        groups=[{"id": "goblins", "leader": "boss", "intent": "kill"}],
    )
    d = apply(ctx, request)
    assert "Бой сверх бюджета: лидеры сильнее бюджета" in d.log
    assert "Не вступили в бой (сверх бюджета): Воин-гоблин ×1" in d.log


def test_max_enemies_cut_is_listed_separately(registry, cfg):
    limit = cfg.limits.max_enemies
    enemies = [goblin(f"g{n}") for n in range(1, limit + 3)]
    ctx, d = combat_with(registry, cfg, enemies, initiated_by="hero")
    assert f"Не вступили в бой (больше {limit} врагов): Воин-гоблин ×2" in d.log
