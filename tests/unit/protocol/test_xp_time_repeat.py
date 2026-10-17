# ТХ (docs/plan-tx.md): защиты от повтора award_xp и часа.
#   xp_awarded_in_scene(ctx) -> list[int]: turn_seq записей recent_turns текущей сцены, где в
#     outcomes есть строка с префиксом «Опыт: +»; нет сцены -- [].
#   award_xp: если таких записей >= cfg.limits.xp_awards_per_scene (0 -- выкл.) -> Decision
#     rejected (reason "повтор награды", report_tag "xp_repeat"), герой и бандл не меняются.
#   time_repeated(ctx, seconds) -> int | None: в последних cfg.limits.time_repeat_turns записях
#     есть outcome «Время идёт: <seconds> с» и requests хода только из {advance_time,
#     offer_choices} -> turn_seq.
#   advance_time hour при повторе -> rejected (report_tag "time_repeat"), часы и концентрация
#     не меняются.
from protocol_kit import dump, make_bundle, make_ctx, req

from ai_dm.config.settings import load_rules_config
from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.protocol.handlers.resources import time_repeated, xp_awarded_in_scene
from ai_dm.state.creature import Concentration
from ai_dm.state.scene import TurnRecord

HOUR_LOG = "Время идёт: 3600 с"


def turn(seq, outcomes=(), requests=(), scene_id="scene_1"):
    return TurnRecord(
        turn_seq=seq, at_s=seq * 60, player_input=f"ввод {seq}", narration=f"рассказ {seq}",
        outcomes=list(outcomes), requests=list(requests), scene_id=scene_id,
    )


def xp_turn(seq, scene_id="scene_1"):
    return turn(seq, ["Опыт: +30 (цель)"], ["award_xp"], scene_id)


def hour_turn(seq, requests=("advance_time",)):
    return turn(seq, [HOUR_LOG], requests)


def make_ctx_with(registry, cfg, turns, with_scene=True):
    bundle = make_bundle(registry, with_scene=with_scene)
    bundle.memory.recent_turns = list(turns)
    return make_ctx(registry, cfg, bundle=bundle)


def limits_cfg(**kw):
    body = "".join(f"{k} = {v}\n" for k, v in kw.items())
    return load_rules_config(f"[limits]\n{body}")


def award(scale="minor", reason="цель"):
    return req("award_xp", scale=scale, reason=reason)


def hour():
    return req("advance_time", category="hour")


# xp_awarded_in_scene

def test_xp_in_scene_empty_without_records(registry, cfg):
    assert xp_awarded_in_scene(make_ctx_with(registry, cfg, [])) == []


def test_xp_in_scene_lists_own_scene_records(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [xp_turn(3), turn(4), xp_turn(5)])
    assert xp_awarded_in_scene(ctx) == [3, 5]


def test_xp_in_scene_ignores_other_scene(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [xp_turn(3, scene_id="scene_0")])
    assert xp_awarded_in_scene(ctx) == []


def test_xp_in_scene_ignores_other_prefix(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [turn(3, ["Золото: +20", "Награда Опыт: +5"])])
    assert xp_awarded_in_scene(ctx) == []


def test_xp_in_scene_finds_line_among_several_outcomes(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [turn(3, ["Золото: +20", "Опыт: +5 (x)"])])
    assert xp_awarded_in_scene(ctx) == [3]


def test_xp_in_scene_empty_without_scene(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [xp_turn(3, scene_id="")], with_scene=False)
    assert xp_awarded_in_scene(ctx) == []


# award_xp

def test_first_award_is_accepted(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    d = apply(ctx, award())
    assert d.status == "accepted"
    assert ctx.hero.sheet.xp == d.result["xp"] > 0


def test_log_line_keeps_prefix_and_reason(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    d = apply(ctx, award(reason="спас деревню"))
    assert d.log == [f"Опыт: +{d.result['xp']} (спас деревню)"]


def test_second_award_in_scene_is_rejected(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [xp_turn(7)])
    d = apply(ctx, award())
    assert isinstance(d, Decision)
    assert d.status == "rejected"
    assert d.report_tag == "xp_repeat"


def test_xp_repeat_signal_names_the_turn(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [xp_turn(7)])
    assert "ход 7" in apply(ctx, award()).signal_to_master


def test_xp_repeat_reason_and_signal_text(registry, cfg):
    d = apply(make_ctx_with(registry, cfg, [xp_turn(7)]), award())
    assert d.reason == "повтор награды"
    assert "новая награда — за новую цель в следующей сцене." in d.signal_to_master


def test_accepted_award_result_has_total_xp(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    ctx.hero.sheet.xp = 10
    d = apply(ctx, award())
    assert d.result["total_xp"] == 10 + d.result["xp"]


def test_xp_repeat_is_not_invalid_and_has_no_log(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [xp_turn(7)])
    d = apply(ctx, award())
    assert not isinstance(d, Invalid)
    assert d.log == []


def test_xp_repeat_leaves_bundle_unchanged(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [xp_turn(7)])
    before = dump(ctx)
    apply(ctx, award())
    assert dump(ctx) == before


def test_award_in_new_scene_is_accepted(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [xp_turn(7, scene_id="scene_0")])
    assert apply(ctx, award()).status == "accepted"


def test_limit_zero_is_off(registry):
    cfg = limits_cfg(xp_awards_per_scene=0)
    ctx = make_ctx_with(registry, cfg, [xp_turn(7), xp_turn(8)])
    assert apply(ctx, award()).status == "accepted"


def test_limit_two_allows_second_award(registry):
    cfg = limits_cfg(xp_awards_per_scene=2)
    ctx = make_ctx_with(registry, cfg, [xp_turn(7)])
    assert apply(ctx, award()).status == "accepted"


def test_limit_two_rejects_third_award(registry):
    cfg = limits_cfg(xp_awards_per_scene=2)
    ctx = make_ctx_with(registry, cfg, [xp_turn(7), xp_turn(8)])
    d = apply(ctx, award())
    assert d.status == "rejected"
    assert "ход 8" in d.signal_to_master


def test_max_level_hero_first_award_gives_zero_and_is_accepted(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    ctx.hero.sheet.classes[0].level = 20
    d = apply(ctx, award())
    assert d.status == "accepted"
    assert d.result["xp"] == 0


def test_known_limitation_two_awards_in_one_turn_are_not_caught(registry, cfg):
    # известное ограничение (решение проектировщика: оставить): защита смотрит только
    # recent_turns, запись хода пишется на commit
    ctx = make_ctx_with(registry, cfg, [])
    first = apply(ctx, award())
    second = apply(ctx, award())
    assert (first.status, second.status) == ("accepted", "accepted")
    assert ctx.hero.sheet.xp == first.result["xp"] * 2


# time_repeated

def test_time_repeated_returns_seq_of_idle_hour(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(4)])
    assert time_repeated(ctx, 3600) == 4


def test_time_repeated_window_two_sees_second_from_end(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(1), turn(2), turn(3)])
    assert cfg.limits.time_repeat_turns == 2
    assert time_repeated(ctx, 3600) is None
    ctx = make_ctx_with(registry, cfg, [turn(1), hour_turn(2), turn(3)])
    assert time_repeated(ctx, 3600) == 2


def test_time_repeated_window_zero_is_none(registry):
    cfg = limits_cfg(time_repeat_turns=0)
    ctx = make_ctx_with(registry, cfg, [hour_turn(4)])
    assert time_repeated(ctx, 3600) is None


def test_time_repeated_window_from_config(registry):
    cfg = limits_cfg(time_repeat_turns=1)
    ctx = make_ctx_with(registry, cfg, [hour_turn(1), turn(2)])
    assert time_repeated(ctx, 3600) is None


def test_time_repeated_none_without_records(registry, cfg):
    assert time_repeated(make_ctx_with(registry, cfg, []), 3600) is None


def test_time_repeated_none_when_hour_came_with_skill_check(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(4, ("advance_time", "skill_check"))])
    assert time_repeated(ctx, 3600) is None


def test_time_repeated_idle_with_offer_choices_counts(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(4, ("advance_time", "offer_choices"))])
    assert time_repeated(ctx, 3600) == 4


def test_time_repeated_other_seconds_is_none(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [turn(4, ["Время идёт: 900 с"], ["advance_time"])])
    assert time_repeated(ctx, 3600) is None


def test_time_repeated_none_for_travel_turn(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [turn(4, ["Путь: до леса"], ["advance_time"])])
    assert time_repeated(ctx, 3600) is None


def test_time_repeated_none_for_folded_combat_record(registry, cfg):
    folded = TurnRecord(
        turn_seq=12, at_s=900, player_input="", narration="Бой окончен.", requests=[], outcomes=[],
    )
    assert time_repeated(make_ctx_with(registry, cfg, [folded]), 3600) is None


# advance_time

def test_repeated_hour_is_rejected(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(4)])
    d = apply(ctx, hour())
    assert isinstance(d, Decision)
    assert d.status == "rejected"
    assert d.report_tag == "time_repeat"
    assert "ходу 4" in d.signal_to_master


def test_repeated_hour_reason_and_signal_text(registry, cfg):
    d = apply(make_ctx_with(registry, cfg, [hour_turn(4)]), hour())
    assert d.reason == "повтор часа"
    assert "сцену по факту, а ожидание продолжай только по просьбе героя." in d.signal_to_master


def test_hour_rhythm_on_real_turn_records(registry, cfg):
    # 1-й час принят, 2-й и 3-й отклонены (окно 2 хода), 4-й принят: ходы пишутся как на commit
    ctx = make_ctx_with(registry, cfg, [])
    statuses = []
    for seq in range(1, 5):
        d = apply(ctx, hour())
        statuses.append(d.status)
        ctx.bundle.memory.recent_turns.append(
            turn(seq, d.log, ["advance_time"])
        )
    assert statuses == ["accepted", "rejected", "rejected", "accepted"]


def test_repeated_hour_keeps_clock_and_bundle(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(4)])
    before = dump(ctx)
    apply(ctx, hour())
    assert dump(ctx) == before


def test_repeated_hour_has_no_log_and_no_concentration_note(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(4)])
    ctx.hero.creature.concentration = Concentration(spell_id="bless", circle=1, until_s=0)
    ctx.bundle.world.clock.now_s = 7200
    d = apply(ctx, hour())
    assert d.log == []
    assert ctx.hero.creature.concentration is not None


def test_first_hour_is_accepted_with_old_log_text(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    start = ctx.bundle.world.clock.now_s
    d = apply(ctx, hour())
    assert d.status == "accepted"
    assert d.log == [HOUR_LOG]
    assert d.result == {"seconds": 3600, "now_s": start + 3600}


def test_minute_after_hour_is_accepted(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(4)])
    d = apply(ctx, req("advance_time", category="minute"))
    assert d.status == "accepted"
    assert d.log == ["Время идёт: 900 с"]


def test_day_after_hour_is_accepted(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(4)])
    d = apply(ctx, req("advance_time", category="day"))
    assert d.status == "accepted"
    assert d.log == ["Время идёт: 86400 с"]


def test_hour_after_hour_with_action_is_accepted(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(4, ("advance_time", "skill_check"))])
    assert apply(ctx, hour()).status == "accepted"


def test_hour_outside_window_is_accepted(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(1), turn(2), turn(3)])
    assert apply(ctx, hour()).status == "accepted"


def test_window_zero_accepts_repeated_hour(registry):
    cfg = limits_cfg(time_repeat_turns=0)
    ctx = make_ctx_with(registry, cfg, [hour_turn(4)])
    assert apply(ctx, hour()).status == "accepted"


def test_travel_is_not_affected_by_hour_record(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(4)])
    d = apply(ctx, req("advance_time", travel_to="forest"))
    assert d.status != "rejected"
    assert not isinstance(d, Invalid)


def test_both_category_and_travel_is_invalid(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    d = apply(ctx, req("advance_time", category="hour", travel_to="forest"))
    assert isinstance(d, Invalid)
    assert d.code == "category_or_travel_to"
    assert "нужно ровно одно из category и travel_to" in d.message


def test_neither_category_nor_travel_is_invalid(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    d = apply(ctx, req("advance_time"))
    assert isinstance(d, Invalid)
    assert d.code == "category_or_travel_to"


def test_known_limitation_two_hours_in_one_turn_are_not_caught(registry, cfg):
    # известное ограничение (решение проектировщика: оставить): защита смотрит только
    # recent_turns, запись хода пишется на commit
    ctx = make_ctx_with(registry, cfg, [])
    start = ctx.bundle.world.clock.now_s
    assert apply(ctx, hour()).status == "accepted"
    assert apply(ctx, hour()).status == "accepted"
    assert ctx.bundle.world.clock.now_s == start + 7200
