# ТХ (docs/plan-tx.md): защиты от повтора award_xp и часа.
#   xp_awarded_in_scene(ctx) -> list[int]: turn_seq записей recent_turns текущей сцены, где в
#     outcomes есть строка с префиксом «Опыт: +»; нет сцены -- [].
#   award_xp: если таких записей >= cfg.limits.xp_awards_per_scene (0 -- выкл.) -> Decision
#     rejected (reason "повтор награды", report_tag "xp_repeat"), герой и бандл не меняются.
#   time_repeated(ctx, seconds) -> list[int]: если ВСЕ последние cfg.limits.time_repeat_turns
#     записей (их ровно окно) -- праздные часы (outcome «Время идёт: <кратно seconds> с», requests
#     только из {advance_time, offer_choices}) -> их turn_seq; иначе [].
#   advance_time hour при повторе (два праздных часа подряд при окне 2) -> rejected
#     (report_tag "time_repeat"), часы и концентрация не меняются.
import pytest
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

def test_time_repeated_returns_seqs_of_two_idle_hours(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(3), hour_turn(4)])
    assert time_repeated(ctx, 3600) == [3, 4]


def test_time_repeated_single_idle_hour_is_empty(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(4)])
    assert time_repeated(ctx, 3600) == []


def test_time_repeated_idle_hour_between_other_turns_is_empty(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [turn(1), hour_turn(2), turn(3)])
    assert cfg.limits.time_repeat_turns == 2
    assert time_repeated(ctx, 3600) == []


def test_time_repeated_looks_only_at_last_window(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(1), turn(2), hour_turn(3), hour_turn(4)])
    assert time_repeated(ctx, 3600) == [3, 4]


def test_time_repeated_window_zero_is_empty(registry):
    cfg = limits_cfg(time_repeat_turns=0)
    ctx = make_ctx_with(registry, cfg, [hour_turn(3), hour_turn(4)])
    assert time_repeated(ctx, 3600) == []


def test_time_repeated_window_from_config(registry):
    cfg = limits_cfg(time_repeat_turns=1)
    ctx = make_ctx_with(registry, cfg, [hour_turn(1), turn(2)])
    assert time_repeated(ctx, 3600) == []
    ctx = make_ctx_with(registry, cfg, [turn(1), hour_turn(2)])
    assert time_repeated(ctx, 3600) == [2]


def test_time_repeated_empty_without_records(registry, cfg):
    assert time_repeated(make_ctx_with(registry, cfg, []), 3600) == []


def test_time_repeated_empty_when_hour_came_with_skill_check(registry, cfg):
    ctx = make_ctx_with(
        registry, cfg, [hour_turn(3), hour_turn(4, ("advance_time", "skill_check"))],
    )
    assert time_repeated(ctx, 3600) == []


def test_time_repeated_idle_with_offer_choices_counts(registry, cfg):
    ctx = make_ctx_with(
        registry, cfg, [hour_turn(3), hour_turn(4, ("advance_time", "offer_choices"))],
    )
    assert time_repeated(ctx, 3600) == [3, 4]


def test_time_repeated_other_seconds_is_empty(registry, cfg):
    ctx = make_ctx_with(
        registry, cfg, [hour_turn(3), turn(4, ["Время идёт: 900 с"], ["advance_time"])],
    )
    assert time_repeated(ctx, 3600) == []


def test_time_repeated_empty_for_travel_turn(registry, cfg):
    ctx = make_ctx_with(
        registry, cfg, [hour_turn(3), turn(4, ["Путь: до леса"], ["advance_time"])],
    )
    assert time_repeated(ctx, 3600) == []


def test_time_repeated_empty_for_folded_combat_record(registry, cfg):
    folded = TurnRecord(
        turn_seq=12, at_s=900, player_input="", narration="Бой окончен.", requests=[], outcomes=[],
    )
    ctx = make_ctx_with(registry, cfg, [hour_turn(11), folded])
    assert time_repeated(ctx, 3600) == []


def test_time_repeated_multiple_shift_counts_as_idle(registry, cfg):
    day = turn(3, ["Время идёт: 86400 с"], ["advance_time"])
    ctx = make_ctx_with(registry, cfg, [day, hour_turn(4)])
    assert time_repeated(ctx, 3600) == [3, 4]


# advance_time

def test_repeated_hour_is_rejected(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(3), hour_turn(4)])
    d = apply(ctx, hour())
    assert isinstance(d, Decision)
    assert d.status == "rejected"
    assert d.report_tag == "time_repeat"
    assert "ходах 3, 4" in d.signal_to_master
    assert d.signal_to_master.startswith("Два часа подряд уже прошли")


def test_repeated_hour_reason_and_signal_text(registry, cfg):
    d = apply(make_ctx_with(registry, cfg, [hour_turn(3), hour_turn(4)]), hour())
    assert d.reason == "повтор часа"
    assert "сцену по факту, а ожидание продолжай только по просьбе героя." in d.signal_to_master


def test_repeated_hour_signal_full_text(registry, cfg):
    d = apply(make_ctx_with(registry, cfg, [hour_turn(3), hour_turn(4)]), hour())
    assert d.signal_to_master.endswith(
        "без пути и дела. Время не двигай: "
        "опиши сцену по факту, а ожидание продолжай только по просьбе героя."
    )


def test_single_idle_hour_after_other_turn_is_accepted_t1364(registry, cfg):
    gold = turn(3, ["Золото: +5"], ["take_item"])
    ctx = make_ctx_with(registry, cfg, [gold, hour_turn(4)])
    start = ctx.bundle.world.clock.now_s
    d = apply(ctx, hour())
    assert d.status == "accepted"
    assert d.log == [HOUR_LOG]
    assert ctx.bundle.world.clock.now_s == start + 3600


def test_hour_after_idle_hour_with_action_before_is_accepted_t1367(registry, cfg):
    ctx = make_ctx_with(
        registry, cfg, [hour_turn(3, ("advance_time", "skill_check")), hour_turn(4)],
    )
    assert apply(ctx, hour()).status == "accepted"


def test_hour_rhythm_on_real_turn_records(registry, cfg):
    # принят, принят, отклонён (два праздных часа), принят, принят, отклонён; ходы как на commit
    ctx = make_ctx_with(registry, cfg, [])
    statuses = []
    for seq in range(1, 7):
        d = apply(ctx, hour())
        statuses.append(d.status)
        outcomes = d.log or ["advance_time: отклонено (повтор часа)"]
        ctx.bundle.memory.recent_turns.append(turn(seq, outcomes, ["advance_time"]))
    assert statuses == ["accepted", "accepted", "rejected", "accepted", "accepted", "rejected"]


def test_repeated_hour_keeps_clock_and_bundle(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(3), hour_turn(4)])
    before = dump(ctx)
    apply(ctx, hour())
    assert dump(ctx) == before


def test_repeated_hour_has_no_log_and_no_concentration_note(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(3), hour_turn(4)])
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


def test_day_after_hour_is_accepted(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(4)])
    d = apply(ctx, req("advance_time", category="day"))
    assert d.status == "accepted"
    assert d.log == ["Время идёт: 86400 с"]


def test_hour_after_hour_with_action_is_accepted(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(4, ("advance_time", "skill_check"))])
    assert apply(ctx, hour()).status == "accepted"


def test_hour_outside_window_is_accepted(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(1), hour_turn(2), turn(3)])
    assert apply(ctx, hour()).status == "accepted"


def test_window_zero_accepts_repeated_hour(registry):
    cfg = limits_cfg(time_repeat_turns=0)
    ctx = make_ctx_with(registry, cfg, [hour_turn(3), hour_turn(4)])
    assert apply(ctx, hour()).status == "accepted"


def test_window_one_rejects_single_idle_hour(registry):
    cfg = limits_cfg(time_repeat_turns=1)
    ctx = make_ctx_with(registry, cfg, [hour_turn(4)])
    assert apply(ctx, hour()).status == "rejected"


def test_window_one_signal_names_single_turn(registry):
    cfg = limits_cfg(time_repeat_turns=1)
    ctx = make_ctx_with(registry, cfg, [hour_turn(4)])
    signal = apply(ctx, hour()).signal_to_master
    assert signal.startswith("Час уже прошёл на ходу 4 без пути и дела.")


def test_window_three_accepts_two_idle_hours(registry):
    cfg = limits_cfg(time_repeat_turns=3)
    ctx = make_ctx_with(registry, cfg, [turn(2), hour_turn(3), hour_turn(4)])
    assert apply(ctx, hour()).status == "accepted"


def test_window_three_rejects_three_idle_hours(registry):
    cfg = limits_cfg(time_repeat_turns=3)
    ctx = make_ctx_with(registry, cfg, [hour_turn(2), hour_turn(3), hour_turn(4)])
    d = apply(ctx, hour())
    assert d.status == "rejected"
    assert d.report_tag == "time_repeat"
    assert "ходах 2, 3, 4" in d.signal_to_master
    assert d.signal_to_master.startswith("Часы уже прошли")


def test_sleep_check_goes_before_repeat(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(3), hour_turn(4)])
    d = apply(ctx, counted("hour", 8))
    assert d.status == "rejected"
    assert d.report_tag == "sleep_not_rest"


def test_day_after_two_idle_hours_is_accepted(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(3), hour_turn(4)])
    assert apply(ctx, req("advance_time", category="day")).status == "accepted"


def test_until_after_two_idle_hours_is_accepted(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(3), hour_turn(4)])
    ctx.bundle.world.clock.now_s = 5 * 3600
    d = apply(ctx, req("advance_time", until="hour", until_hour=6))
    assert d.status == "accepted"


def test_travel_is_not_affected_by_hour_record(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(4)])
    d = apply(ctx, req("advance_time", travel_to="forest"))
    assert d.status != "rejected"
    assert not isinstance(d, Invalid)


def test_both_category_and_travel_is_invalid(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    d = apply(ctx, req("advance_time", category="hour", travel_to="forest"))
    assert isinstance(d, Invalid)
    assert d.code == "category_travel_to_or_until"
    assert "нужно ровно одно из category, travel_to и until" in d.message


def test_neither_category_nor_travel_is_invalid(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    d = apply(ctx, req("advance_time"))
    assert isinstance(d, Invalid)
    assert d.code == "category_travel_to_or_until"


def test_until_is_not_affected_by_hour_record(registry, cfg):
    # time_repeated для until не применяется
    ctx = make_ctx_with(registry, cfg, [hour_turn(4)])
    ctx.bundle.world.clock.now_s = 5 * 3600
    d = apply(ctx, req("advance_time", until="hour", until_hour=6))
    assert d.status == "accepted"
    assert d.log == [HOUR_LOG]


# advance_time count (ДН)

def counted(category, count):
    return req("advance_time", category=category, count=count)


def test_count_eight_days_moves_clock_eight_days(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    start = ctx.bundle.world.clock.now_s
    d = apply(ctx, counted("day", 8))
    assert d.status == "accepted"
    assert d.result == {"seconds": 8 * 86400, "now_s": start + 8 * 86400}
    assert ctx.bundle.world.clock.now_s == start + 8 * 86400


def test_count_eight_days_log_has_passed_and_time_lines(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    assert apply(ctx, counted("day", 8)).log == ["Прошло 8 дней", "Время идёт: 691200 с"]


def test_count_two_days_log_uses_genitive_singular(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    assert apply(ctx, counted("day", 2)).log[0] == "Прошло 2 дня"


def test_count_three_hours_log(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    d = apply(ctx, counted("hour", 3))
    assert d.log == ["Прошло 3 часа", "Время идёт: 10800 с"]


def test_count_two_weeks_log(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    d = apply(ctx, counted("week", 2))
    assert d.log == ["Прошло 2 недели", "Время идёт: 1209600 с"]


def test_count_two_months_log(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    assert apply(ctx, counted("month", 2)).log[0] == "Прошло 2 месяца"


def test_minute_is_not_an_advance_time_category():
    from pydantic import ValidationError

    from ai_dm.protocol.requests import AdvanceTime

    with pytest.raises(ValidationError):
        AdvanceTime(type="advance_time", category="minute")


def test_count_two_months_sums_calendar_months(registry, cfg):
    from ai_dm.core.clock import Calendar, GameClock, Month

    ctx = make_ctx_with(registry, cfg, [])
    cal = Calendar(months=[
        Month(name="А", days=30), Month(name="Б", days=31), Month(name="В", days=20),
    ])
    ctx.bundle.world.clock = GameClock.from_date("0001-01-01", cal)
    d = apply(ctx, counted("month", 2))
    assert d.result["seconds"] == (30 + 31) * 86400
    assert ctx.bundle.world.clock.to_date() == "0001-03-01"


def test_count_over_year_is_invalid_and_clock_stays(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    year_days = ctx.bundle.world.clock.calendar.days_in_year
    start = ctx.bundle.world.clock.now_s
    d = apply(ctx, counted("day", year_days + 1))
    assert isinstance(d, Invalid)
    assert d.code == "count_over_year"
    assert ctx.bundle.world.clock.now_s == start


def test_count_over_year_message_text(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    year_days = ctx.bundle.world.clock.calendar.days_in_year
    d = apply(ctx, counted("day", year_days + 1))
    assert d.message == "за раз можно сдвинуть время не больше чем на год: уменьши count"


def test_until_long_rest_already_possible_is_rejected_with_text(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    now_s = 2 * 3600 + 900
    ctx.bundle.world.clock.now_s = now_s
    ctx.hero.long_rest_end_s = None
    d = apply(ctx, req("advance_time", until="long_rest"))
    assert d.status == "rejected"
    assert d.reason == "отдых уже можно"
    assert d.signal_to_master == "Длинный отдых уже возможен: вызови rest long, время не двигай."
    assert ctx.bundle.world.clock.now_s == now_s


def test_count_exactly_one_year_is_accepted(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    year_days = ctx.bundle.world.clock.calendar.days_in_year
    d = apply(ctx, counted("day", year_days))
    assert d.status == "accepted"
    assert d.result["seconds"] == year_days * 86400


def test_count_over_year_in_months_is_invalid(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    months = len(ctx.bundle.world.clock.calendar.months)
    assert apply(ctx, counted("month", months + 1)).code == "count_over_year"


def test_count_one_gives_old_log_only(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    assert apply(ctx, counted("day", 1)).log == ["Время идёт: 86400 с"]


def test_count_absent_gives_old_log_only(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    assert apply(ctx, req("advance_time", category="day")).log == ["Время идёт: 86400 с"]


def test_count_with_travel_to_is_invalid(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    d = apply(ctx, req("advance_time", travel_to="forest", count=3))
    assert isinstance(d, Invalid)
    assert d.code == "count_only_with_category"


def test_count_with_until_is_invalid(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    d = apply(ctx, req("advance_time", until="morning", count=3))
    assert isinstance(d, Invalid)
    assert d.code == "count_only_with_category"


def test_count_two_with_travel_to_is_invalid(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    d = apply(ctx, req("advance_time", travel_to="forest", count=2))
    assert isinstance(d, Invalid)
    assert d.code == "count_only_with_category"


def test_count_one_with_travel_to_is_not_invalid(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    d = apply(ctx, req("advance_time", travel_to="forest", count=1))
    assert not isinstance(d, Invalid)


def test_count_hour_after_same_total_record_is_rejected_as_repeat(registry, cfg):
    three = turn(3, ["Время идёт: 10800 с"], ["advance_time"])
    ctx = make_ctx_with(registry, cfg, [three, hour_turn(4)])
    d = apply(ctx, counted("hour", 3))
    assert d.status == "rejected"
    assert d.report_tag == "time_repeat"


def test_count_hour_after_single_same_total_record_is_accepted(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [turn(4, ["Время идёт: 10800 с"], ["advance_time"])])
    assert apply(ctx, counted("hour", 3)).status == "accepted"


def test_count_hour_after_two_hour_records_is_rejected(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(3), hour_turn(4)])
    d = apply(ctx, counted("hour", 2))
    assert d.status == "rejected"
    assert d.report_tag == "time_repeat"


def test_hour_after_three_hours_record_and_hour_is_rejected(registry, cfg):
    three = turn(3, ["Время идёт: 10800 с"], ["advance_time"])
    ctx = make_ctx_with(registry, cfg, [three, hour_turn(4)])
    assert apply(ctx, hour()).status == "rejected"


def test_hour_after_single_three_hours_record_is_accepted(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [turn(4, ["Время идёт: 10800 с"], ["advance_time"])])
    assert apply(ctx, hour()).status == "accepted"


def test_count_hour_after_three_hours_record_other_request_is_not_repeat(registry, cfg):
    ctx = make_ctx_with(
        registry, cfg, [turn(4, ["Время идёт: 10800 с"], ["advance_time", "skill_check"])],
    )
    assert apply(ctx, counted("hour", 3)).status == "accepted"


def test_hour_after_900_seconds_record_is_accepted(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [turn(4, ["Время идёт: 900 с"], ["advance_time"])])
    assert apply(ctx, hour()).status == "accepted"


def test_hour_after_day_record_and_hour_is_rejected_as_repeat(registry, cfg):
    day = turn(3, ["Время идёт: 86400 с"], ["advance_time"])
    ctx = make_ctx_with(registry, cfg, [day, hour_turn(4)])
    d = apply(ctx, hour())
    assert d.status == "rejected"
    assert d.report_tag == "time_repeat"


def test_hour_after_until_giving_whole_hours_and_hour_is_rejected(registry, cfg):
    until = turn(3, ["Время идёт: 28800 с"], ["advance_time"])
    ctx = make_ctx_with(registry, cfg, [until, hour_turn(4)])
    assert apply(ctx, hour()).status == "rejected"


def test_time_log_seconds_parses_number_and_ignores_other_lines():
    from ai_dm.protocol.handlers.resources import time_log_seconds

    assert time_log_seconds("Время идёт: 10800 с") == 10800
    assert time_log_seconds("Путь: до леса") is None
    assert time_log_seconds("Время идёт: много с") is None


def test_hour_without_count_after_two_hour_records_is_still_rejected(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(3), hour_turn(4)])
    assert apply(ctx, hour()).status == "rejected"


def test_hour_after_single_day_shift_is_accepted(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [turn(4, ["Время идёт: 86400 с"], ["advance_time"])])
    assert apply(ctx, hour()).status == "accepted"


def test_count_day_after_hour_record_is_accepted(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [hour_turn(4)])
    assert apply(ctx, counted("day", 2)).status == "accepted"


# until и rest в одном ходе (ctx.rested / ctx.until_done)

def until_morning():
    return req("advance_time", until="morning")


def test_until_after_accepted_rest_is_invalid_and_clock_stays(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    ctx.bundle.world.clock.now_s = 2 * 3600 + 900
    assert apply(ctx, req("rest", kind="long")).status == "accepted"
    after_rest = ctx.bundle.world.clock.now_s
    d = apply(ctx, until_morning())
    assert isinstance(d, Invalid)
    assert d.code == "until_with_rest"
    assert ctx.bundle.world.clock.now_s == after_rest


def test_until_without_rest_still_moves_to_morning(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    ctx.bundle.world.clock.now_s = 2 * 3600 + 900
    d = apply(ctx, until_morning())
    assert d.status == "accepted"
    assert ctx.bundle.world.clock.now_s == 6 * 3600


def test_category_after_rest_is_not_blocked(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    assert apply(ctx, req("rest", kind="long")).status == "accepted"
    assert apply(ctx, req("advance_time", category="hour")).status == "accepted"


def test_rest_after_accepted_until_gets_report_tag(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    ctx.bundle.world.clock.now_s = 2 * 3600 + 900
    assert apply(ctx, until_morning()).status == "accepted"
    d = apply(ctx, req("rest", kind="long"))
    assert d.status == "accepted"
    assert d.report_tag == "until_then_rest"


def test_until_after_rejected_rest_is_not_blocked(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    now_s = 2 * 3600 + 900
    ctx.bundle.world.clock.now_s = now_s
    ctx.hero.long_rest_end_s = now_s
    assert apply(ctx, req("rest", kind="long")).status == "rejected"
    assert ctx.rested is False
    assert apply(ctx, until_morning()).status == "accepted"
    assert ctx.bundle.world.clock.now_s == 6 * 3600


def test_until_then_rest_does_not_overwrite_existing_report_tag(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    ctx.bundle.world.clock.now_s = 2 * 3600 + 900
    assert apply(ctx, until_morning()).status == "accepted"
    d = apply(ctx, req("rest", kind="short", hit_dice=99))
    assert d.status == "clamped"
    assert d.report_tag == "limit-exceeded"


def test_rest_without_until_has_no_report_tag(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    assert apply(ctx, req("rest", kind="long")).report_tag is None


# plural_form, passed_text

@pytest.mark.parametrize(
    ("n", "word"),
    [
        (1, "день"), (2, "дня"), (3, "дня"), (4, "дня"), (5, "дней"), (10, "дней"),
        (11, "дней"), (12, "дней"), (13, "дней"), (14, "дней"), (15, "дней"),
        (20, "дней"), (21, "день"), (22, "дня"), (25, "дней"), (100, "дней"),
        (101, "день"), (111, "дней"), (112, "дней"), (114, "дней"), (121, "день"),
        (110, "дней"), (115, "дней"), (211, "дней"), (213, "дней"), (203, "дня"),
        (6, "дней"), (7, "дней"), (8, "дней"), (9, "дней"), (19, "дней"), (27, "дней"),
    ],
)
def test_plural_form_for_days(n, word):
    from ai_dm.protocol.handlers.resources import plural_form

    assert plural_form(n, ("день", "дня", "дней")) == word


def test_passed_text_hours_five():
    from ai_dm.protocol.handlers.resources import passed_text

    assert passed_text("hour", 5) == "Прошло 5 часов"


def test_passed_text_months_five():
    from ai_dm.protocol.handlers.resources import passed_text

    assert passed_text("month", 5) == "Прошло 5 месяцев"


def test_passed_text_weeks_and_days():
    from ai_dm.protocol.handlers.resources import passed_text

    assert passed_text("week", 3) == "Прошло 3 недели"
    assert passed_text("day", 21) == "Прошло 21 день"


def test_passed_text_has_no_minute_unit():
    from ai_dm.protocol.handlers.resources import passed_text

    with pytest.raises(KeyError):
        passed_text("minute", 2)


def test_known_limitation_two_hours_in_one_turn_are_not_caught(registry, cfg):
    # известное ограничение (решение проектировщика: оставить): защита смотрит только
    # recent_turns, запись хода пишется на commit
    ctx = make_ctx_with(registry, cfg, [])
    start = ctx.bundle.world.clock.now_s
    assert apply(ctx, hour()).status == "accepted"
    assert apply(ctx, hour()).status == "accepted"
    assert ctx.bundle.world.clock.now_s == start + 7200
