# ТМ (docs/plan-tm.md, §1 п.1): защита gold explicit gain от повтора.
#   gold_repeated(ctx, amount_cp) -> int | None (ai_dm.protocol.handlers.resources):
#   смотрит последние
#     cfg.limits.gold_repeat_turns записей bundle.memory.recent_turns; возвращает turn_seq записи с
#     money_delta_cp == amount_cp; 0 -- защита выключена; нет совпадения -- None.
#   gold explicit gain: сумма сначала урезается потолком уровня, потом сравнивается;
#     повтор -> Decision rejected (не Invalid: Invalid жжёт бюджет), reason "повтор начисления",
#     signal с суммой, номером
#     хода и кошельком, report_tag "gold_repeat"; деньги и бандл не меняются.
#   Не затронуты: gold lose, loot_individual, hoard (у них свои «один раз»).
from protocol_kit import ScriptedRng, dump, make_bundle, make_ctx, req

from ai_dm.config.settings import load_rules_config
from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.protocol.handlers.resources import gold_repeated
from ai_dm.rules import money
from ai_dm.state.scene import TurnRecord
from ai_dm.state.session import LastCombat


def turn(seq, delta=0):
    return TurnRecord(
        turn_seq=seq, at_s=seq * 60, player_input=f"ввод {seq}", narration=f"рассказ {seq}",
        money_delta_cp=delta,
    )


def make_ctx_with(registry, cfg, turns, money_cp=16800, rng=None):
    bundle = make_bundle(registry)
    bundle.heroes[0].money_cp = money_cp
    bundle.memory.recent_turns = list(turns)
    return make_ctx(registry, cfg, rng, bundle=bundle)


def gain(amount):
    return req("gold", direction="gain", kind="explicit", amount_cp=amount)


def lose(amount):
    return req("gold", direction="lose", kind="explicit", amount_cp=amount)


def window(n):
    return load_rules_config(f"[limits]\ngold_repeat_turns = {n}\n")


# gold_repeated

def test_repeated_returns_turn_seq_of_matching_record(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [turn(7, 2000)])
    assert gold_repeated(ctx, 2000) == 7


def test_repeated_is_none_without_records(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [])
    assert gold_repeated(ctx, 2000) is None


def test_repeated_is_none_for_another_amount(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [turn(7, 2000)])
    assert gold_repeated(ctx, 2001) is None


def test_repeated_sees_the_last_three_turns_by_default(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [turn(1, 2000), turn(2), turn(3), turn(4)])
    assert cfg.limits.gold_repeat_turns == 3
    assert gold_repeated(ctx, 2000) is None


def test_repeated_sees_the_third_turn_from_the_end(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [turn(1), turn(2, 2000), turn(3), turn(4)])
    assert gold_repeated(ctx, 2000) == 2


def test_repeated_window_comes_from_config(registry):
    cfg = window(1)
    ctx = make_ctx_with(registry, cfg, [turn(1, 2000), turn(2)])
    assert gold_repeated(ctx, 2000) is None


def test_repeated_window_one_sees_the_last_turn(registry):
    cfg = window(1)
    ctx = make_ctx_with(registry, cfg, [turn(1), turn(2, 2000)])
    assert gold_repeated(ctx, 2000) == 2


def test_repeated_window_zero_is_off(registry):
    cfg = window(0)
    ctx = make_ctx_with(registry, cfg, [turn(1, 2000)])
    assert gold_repeated(ctx, 2000) is None


def test_repeated_ignores_negative_delta_of_same_size(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [turn(1, -2000)])
    assert gold_repeated(ctx, 2000) is None


# сценарий дракона: ходы 129-131, одна сумма 2000 мм подряд

def test_second_equal_gain_is_rejected(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [turn(129, 2000)], money_cp=18800)
    d = apply(ctx, gain(2000))
    assert isinstance(d, Decision)
    assert d.status == "rejected"


def test_repeat_does_not_change_money(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [turn(129, 2000)], money_cp=18800)
    apply(ctx, gain(2000))
    assert ctx.hero.money_cp == 18800


def test_repeat_does_not_change_the_bundle(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [turn(129, 2000)], money_cp=18800)
    before = dump(ctx)
    apply(ctx, gain(2000))
    assert dump(ctx) == before


def test_repeat_is_rejected_not_invalid(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [turn(129, 2000)])
    assert not isinstance(apply(ctx, gain(2000)), Invalid)


def test_repeat_has_report_tag_gold_repeat(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [turn(129, 2000)])
    assert apply(ctx, gain(2000)).report_tag == "gold_repeat"


def test_repeat_signal_names_amount_turn_and_purse(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [turn(129, 2000)], money_cp=18800)
    signal = apply(ctx, gain(2000)).signal_to_master
    assert money.format_cp(2000) in signal
    assert "ходу 129" in signal
    assert money.format_cp(18800) in signal


def test_repeat_has_no_log_lines(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [turn(129, 2000)])
    assert apply(ctx, gain(2000)).log == []


def test_repeat_after_two_quiet_turns_is_still_rejected(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [turn(129, 2000), turn(130), turn(131)])
    assert apply(ctx, gain(2000)).status == "rejected"


# вне защиты

def test_gain_with_empty_memory_is_accepted(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [], money_cp=100)
    d = apply(ctx, gain(2000))
    assert d.status == "accepted"
    assert ctx.hero.money_cp == 2100


def test_gain_of_another_amount_is_accepted(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [turn(129, 2000)], money_cp=100)
    assert apply(ctx, gain(1500)).status == "accepted"
    assert ctx.hero.money_cp == 1600


def test_repeat_outside_the_window_is_accepted(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [turn(1, 2000), turn(2), turn(3), turn(4)], money_cp=100)
    assert apply(ctx, gain(2000)).status == "accepted"
    assert ctx.hero.money_cp == 2100


def test_window_zero_accepts_repeat(registry):
    cfg = window(0)
    ctx = make_ctx_with(registry, cfg, [turn(129, 2000)], money_cp=100)
    assert apply(ctx, gain(2000)).status == "accepted"
    assert ctx.hero.money_cp == 2100


def test_negative_delta_of_same_size_does_not_block_gain(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [turn(129, -2000)], money_cp=100)
    assert apply(ctx, gain(2000)).status == "accepted"


def test_lose_of_same_amount_is_not_blocked(registry, cfg):
    ctx = make_ctx_with(registry, cfg, [turn(129, 2000)], money_cp=5000)
    d = apply(ctx, lose(2000))
    assert d.status == "accepted"
    assert ctx.hero.money_cp == 3000


def test_comparison_is_after_the_level_cap(registry, cfg):
    # потолок 1 уровня 5000: запрос 99999 урезается до 5000 и совпадает с записью
    cap = cfg.limits.gold_explicit_max_cp_by_level[1]
    ctx = make_ctx_with(registry, cfg, [turn(9, cap)], money_cp=0)
    d = apply(ctx, gain(99_999))
    assert d.status == "rejected"
    assert ctx.hero.money_cp == 0


def test_requested_amount_equal_to_record_but_above_cap_is_not_repeat(registry, cfg):
    # запись 99999 (не равна потолку 5000): урезанная сумма с ней не совпадает
    ctx = make_ctx_with(registry, cfg, [turn(9, 99_999)], money_cp=0)
    d = apply(ctx, gain(99_999))
    assert d.status == "clamped"
    assert ctx.hero.money_cp == cfg.limits.gold_explicit_max_cp_by_level[1]


def test_loot_individual_is_not_blocked_by_equal_record(registry, cfg):
    rng = ScriptedRng(d6=[1, 1, 1, 1])
    ctx = make_ctx_with(registry, cfg, [turn(5, 400)], money_cp=0, rng=rng)
    ctx.bundle.session.last_combat = LastCombat(defeated=["goblin_warrior"])
    d = apply(ctx, req("gold", direction="gain", kind="loot_individual"))
    assert d.status == "accepted"
    assert ctx.hero.money_cp == 400


def test_hoard_is_not_blocked_by_equal_record(registry, cfg):
    from test_apply_loot import hoard_ctx, hoard_req, low_rng

    first = hoard_ctx(registry, cfg, low_rng())
    amount = apply(first, hoard_req()).result["amount_cp"]
    second = hoard_ctx(registry, cfg, low_rng())
    second.bundle.memory.recent_turns = [turn(5, amount)]
    d = apply(second, hoard_req())
    assert d.status == "accepted"
    assert d.result["amount_cp"] == amount


def test_folded_combat_record_is_seen_by_the_guard(registry, cfg):
    # запись свёртки боя: пустой ввод, без requests, money_delta_cp -- сумма свёрнутых ходов
    folded = TurnRecord(
        turn_seq=12, at_s=900, player_input="", narration="Бой окончен.", requests=[],
        rolls=[], outcomes=[], money_delta_cp=2000,
    )
    ctx = make_ctx_with(registry, cfg, [folded], money_cp=2000)
    d = apply(ctx, gain(2000))
    assert d.status == "rejected"
    assert "ходу 12" in d.signal_to_master


def test_second_gain_after_accepted_one_in_same_turn_is_not_caught(registry, cfg):
    # известное ограничение (TM-PLAN §7): запись хода пишется на commit, два gold в одном
    # ответе защита не видит
    ctx = make_ctx_with(registry, cfg, [], money_cp=0)
    assert apply(ctx, gain(2000)).status == "accepted"
    assert apply(ctx, gain(2000)).status == "accepted"
    assert ctx.hero.money_cp == 4000
