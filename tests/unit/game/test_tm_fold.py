# ТМ (docs/TM-PLAN.md, §1 п.3): запись свёртки боя (fold_fight) -- outcomes пустые,
# money_delta_cp --
# сумма money_delta_cp свёрнутых ходов (чтобы защита золота видела добычу, взятую в бою).
from test_combat_fold import bundle_with, fight, finished_state

from ai_dm.game.combat_fold import fold_fight


def test_fold_record_has_empty_outcomes(registry):
    turns = fight(3)
    for turn in turns[2:]:
        turn.outcomes = ["Золото: +1 зм"]
    bundle = bundle_with(registry, turns)
    fold_fight(bundle, finished_state(), registry)
    assert bundle.memory.recent_turns[-1].outcomes == []


def test_fold_record_money_delta_is_sum_of_folded_turns(registry):
    turns = fight(3)
    for turn, delta in zip(turns[2:], [100, -30, 500], strict=True):
        turn.money_delta_cp = delta
    bundle = bundle_with(registry, turns)
    fold_fight(bundle, finished_state(), registry)
    assert bundle.memory.recent_turns[-1].money_delta_cp == 570


def test_fold_record_money_delta_is_zero_without_money_turns(registry):
    bundle = bundle_with(registry, fight(3))
    fold_fight(bundle, finished_state(), registry)
    assert bundle.memory.recent_turns[-1].money_delta_cp == 0


def test_fold_record_does_not_count_money_of_start_and_earlier_turns(registry):
    turns = fight(2)
    turns[0].money_delta_cp = 7000
    turns[1].money_delta_cp = 900
    turns[2].money_delta_cp = 20
    turns[3].money_delta_cp = 30
    bundle = bundle_with(registry, turns)
    fold_fight(bundle, finished_state(), registry)
    assert bundle.memory.recent_turns[-1].money_delta_cp == 50


def test_fold_keeps_money_of_kept_records(registry):
    turns = fight(3)
    turns[0].money_delta_cp = 7000
    turns[1].money_delta_cp = 900
    bundle = bundle_with(registry, turns)
    fold_fight(bundle, finished_state(), registry)
    assert [t.money_delta_cp for t in bundle.memory.recent_turns[:2]] == [7000, 900]


def test_fold_keeps_outcomes_of_kept_records(registry):
    turns = fight(3)
    turns[1].outcomes = ["Бой начался"]
    bundle = bundle_with(registry, turns)
    fold_fight(bundle, finished_state(), registry)
    assert bundle.memory.recent_turns[1].outcomes == ["Бой начался"]


def test_no_fold_keeps_money_untouched(registry):
    turns = fight(1)
    turns[2].money_delta_cp = 40
    bundle = bundle_with(registry, turns)
    assert fold_fight(bundle, finished_state(), registry) is False
    assert bundle.memory.recent_turns[2].money_delta_cp == 40


def test_second_fold_does_not_change_the_sum(registry):
    turns = fight(3)
    for turn in turns[2:]:
        turn.money_delta_cp = 10
    bundle = bundle_with(registry, turns)
    state = finished_state()
    fold_fight(bundle, state, registry)
    fold_fight(bundle, state, registry)
    assert bundle.memory.recent_turns[-1].money_delta_cp == 30
