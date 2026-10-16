# ТМ (docs/TM-PLAN.md, §1 п.3): итог инструментов в памяти хода.
#   TurnResult.outcomes: accepted / clamped -> Decision.log запроса; rejected -> строка
#     "<type>: отклонено (<reason>)" (в result.lines и UI не попадает); Invalid -- ничего.
#   TurnRunner.commit пишет в TurnRecord outcomes=list(result.outcomes) и
#     money_delta_cp = деньги героя после хода - деньги до хода (ловит gold, trade, hoard).
#   combat_fold.fold_fight: запись свёртки с outcomes=[] и money_delta_cp = сумма свёрнутых ходов.
#   recent_turns_keep по-прежнему режет сохранённое окно.
import pytest
from game_kit import make_rig, scripted, text_step, tools_step
from protocol_kit import make_bundle

from ai_dm.rules import money
from ai_dm.state.scene import TurnRecord


def gold_call(amount, direction="gain", call_id="g1"):
    return {
        "id": call_id, "name": "gold",
        "input": {
            "type": "gold", "direction": direction, "kind": "explicit", "amount_cp": amount,
            "cr": "",
        },
    }


def rest_call(kind="long", call_id="r1"):
    return {"id": call_id, "name": "rest", "input": {"type": "rest", "kind": kind}}


def flag_call(name="f1"):
    return {"id": "f", "name": "set_flag",
            "input": {"type": "set_flag", "name": name, "value": "true"}}


def rig_of(registry, cfg, tmp_path, steps, money_cp=None):
    bundle = make_bundle(registry)
    if money_cp is not None:
        bundle.heroes[0].money_cp = money_cp
    return make_rig(registry, cfg, tmp_path, scripted(steps), bundle=bundle)


def last(rig):
    return rig.runner.bundle.memory.recent_turns[-1]


# поля записи по умолчанию

def test_turn_without_tools_has_empty_outcomes(registry, cfg, tmp_path):
    rig = rig_of(registry, cfg, tmp_path, [text_step("Тихо.")])
    rig.runner.play("Смотрю")
    assert last(rig).outcomes == []


def test_turn_without_tools_has_zero_money_delta(registry, cfg, tmp_path):
    rig = rig_of(registry, cfg, tmp_path, [text_step("Тихо.")])
    rig.runner.play("Смотрю")
    assert last(rig).money_delta_cp == 0


def test_result_outcomes_start_empty(registry, cfg, tmp_path):
    rig = rig_of(registry, cfg, tmp_path, [text_step("Тихо.")])
    assert rig.runner.play("Смотрю").outcomes == []


# accepted

def test_accepted_gold_puts_log_into_outcomes(registry, cfg, tmp_path):
    rig = rig_of(registry, cfg, tmp_path, [tools_step(gold_call(2000)), text_step("Кошель.")])
    result = rig.runner.play("Обыскать")
    assert result.outcomes == [f"Золото: +{money.format_cp(2000)}"]
    assert last(rig).outcomes == result.outcomes


def test_accepted_gold_gives_positive_money_delta(registry, cfg, tmp_path):
    rig = rig_of(registry, cfg, tmp_path, [tools_step(gold_call(2000)), text_step("Кошель.")])
    rig.runner.play("Обыскать")
    assert last(rig).money_delta_cp == 2000


def test_money_delta_is_measured_from_turn_start_purse(registry, cfg, tmp_path):
    rig = rig_of(
        registry, cfg, tmp_path, [tools_step(gold_call(300)), text_step("Кошель.")], money_cp=5000
    )
    rig.runner.play("Обыскать")
    assert last(rig).money_delta_cp == 300


def test_accepted_outcomes_also_stay_in_lines(registry, cfg, tmp_path):
    rig = rig_of(registry, cfg, tmp_path, [tools_step(gold_call(2000)), text_step("Кошель.")])
    result = rig.runner.play("Обыскать")
    assert f"Золото: +{money.format_cp(2000)}" in result.lines


def test_outcomes_keep_request_order(registry, cfg, tmp_path):
    steps = [tools_step(gold_call(2000), rest_call()), text_step("Итог.")]
    rig = rig_of(registry, cfg, tmp_path, steps)
    result = rig.runner.play("Обыскать и отдохнуть")
    assert result.outcomes == [
        f"Золото: +{money.format_cp(2000)}", "Длинный отдых: HP и ресурсы восстановлены",
    ]


def test_record_requests_still_list_accepted_types(registry, cfg, tmp_path):
    steps = [tools_step(gold_call(2000), rest_call()), text_step("Итог.")]
    rig = rig_of(registry, cfg, tmp_path, steps)
    rig.runner.play("Обыскать и отдохнуть")
    assert last(rig).requests == ["gold", "rest"]


def test_gain_and_loss_in_one_turn_give_net_delta(registry, cfg, tmp_path):
    steps = [tools_step(gold_call(2000), gold_call(500, "lose", "g2")), text_step("Итог.")]
    rig = rig_of(registry, cfg, tmp_path, steps)
    rig.runner.play("Торг")
    assert last(rig).money_delta_cp == 1500


# отрицательная дельта: lose и trade

def test_gold_lose_gives_negative_money_delta(registry, cfg, tmp_path):
    steps = [tools_step(gold_call(300, "lose")), text_step("Потеря.")]
    rig = rig_of(registry, cfg, tmp_path, steps, money_cp=1000)
    rig.runner.play("Теряю")
    assert last(rig).money_delta_cp == -300


def test_trade_purchase_gives_negative_money_delta(registry, cfg, tmp_path):
    from protocol_kit import make_ctx  # noqa: F401

    from ai_dm.state.world import NPC, TradeProfile

    bundle = make_bundle(registry)
    bundle.heroes[0].money_cp = 1000
    bundle.world.npcs["mara"] = NPC(
        id="mara", name="Мара", means=["товары"], location_id="vale",
        trade=TradeProfile(kind="general", purse_cp=5000, restock_at_s=10**9),
    )
    call = {
        "id": "t1", "name": "trade",
        "input": {
            "type": "trade", "npc_id": "mara", "direction": "buy", "item_id": "arrows", "qty": 1,
            "quality": "any", "category": "",
        },
    }
    rig = make_rig(
        registry, cfg, tmp_path, scripted([tools_step(call), text_step("Куплено.")]),
        bundle=bundle,
    )
    rig.runner.play("Покупаю кинжал")
    assert last(rig).money_delta_cp < 0
    assert last(rig).money_delta_cp == rig.runner.bundle.heroes[0].money_cp - 1000


# clamped

def test_clamped_gold_is_in_outcomes_with_cut_amount(registry, cfg, tmp_path):
    cap = cfg.limits.gold_explicit_max_cp_by_level[1]
    rig = rig_of(registry, cfg, tmp_path, [tools_step(gold_call(99_999)), text_step("Клад.")])
    result = rig.runner.play("Клад")
    assert result.outcomes == [f"Золото: +{money.format_cp(cap)}"]
    assert result.requests == ["gold"]
    assert last(rig).money_delta_cp == cap


# rejected

def test_rejected_request_goes_to_outcomes_as_refusal(registry, cfg, tmp_path):
    steps = [
        tools_step(gold_call(2000)), text_step("Кошель."),
        tools_step(gold_call(2000)), text_step("Опять."),
    ]
    rig = rig_of(registry, cfg, tmp_path, steps)
    rig.runner.play("Обыскать")
    result = rig.runner.play("Ещё раз")
    assert result.outcomes == ["gold: отклонено (повтор начисления)"]


def test_rejected_outcome_is_not_in_ui_lines(registry, cfg, tmp_path):
    steps = [
        tools_step(gold_call(2000)), text_step("Кошель."),
        tools_step(gold_call(2000)), text_step("Опять."),
    ]
    rig = rig_of(registry, cfg, tmp_path, steps)
    rig.runner.play("Обыскать")
    result = rig.runner.play("Ещё раз")
    assert not [line for line in result.lines if "отклонено" in line]


def test_rejected_request_is_not_in_requests(registry, cfg, tmp_path):
    steps = [
        tools_step(gold_call(2000)), text_step("Кошель."),
        tools_step(gold_call(2000)), text_step("Опять."),
    ]
    rig = rig_of(registry, cfg, tmp_path, steps)
    rig.runner.play("Обыскать")
    result = rig.runner.play("Ещё раз")
    assert result.requests == []
    assert last(rig).requests == []


def test_rejected_gold_gives_zero_money_delta_and_keeps_purse(registry, cfg, tmp_path):
    steps = [
        tools_step(gold_call(2000)), text_step("Кошель."),
        tools_step(gold_call(2000)), text_step("Опять."),
    ]
    rig = rig_of(registry, cfg, tmp_path, steps)
    rig.runner.play("Обыскать")
    purse = rig.runner.bundle.heroes[0].money_cp
    rig.runner.play("Ещё раз")
    assert last(rig).money_delta_cp == 0
    assert rig.runner.bundle.heroes[0].money_cp == purse


def test_rejected_rest_goes_to_outcomes(registry, cfg, tmp_path):
    steps = [
        tools_step(rest_call()), text_step("Спишь."), tools_step(rest_call()), text_step("Снова."),
    ]
    rig = rig_of(registry, cfg, tmp_path, steps)
    rig.runner.play("Отдыхаю")
    result = rig.runner.play("Снова отдыхаю")
    assert result.outcomes == ["rest: отклонено (отдых уже был)"]
    assert last(rig).outcomes == ["rest: отклонено (отдых уже был)"]


def test_rejected_and_accepted_outcomes_keep_order(registry, cfg, tmp_path):
    steps = [
        tools_step(gold_call(2000)), text_step("Кошель."),
        tools_step(gold_call(2000, call_id="g2"), gold_call(700, call_id="g3")),
        text_step("Опять."),
    ]
    rig = rig_of(registry, cfg, tmp_path, steps)
    rig.runner.play("Обыскать")
    result = rig.runner.play("Ещё раз")
    assert result.outcomes == [
        "gold: отклонено (повтор начисления)", f"Золото: +{money.format_cp(700)}",
    ]


# Invalid

def test_invalid_request_is_not_in_outcomes(registry, cfg, tmp_path):
    steps = [tools_step(gold_call(0)), text_step("Ничего.")]
    rig = rig_of(registry, cfg, tmp_path, steps)
    result = rig.runner.play("Золото?")
    assert result.outcomes == []
    assert last(rig).outcomes == []


def test_invalid_request_is_not_in_requests(registry, cfg, tmp_path):
    steps = [tools_step(gold_call(0)), text_step("Ничего.")]
    rig = rig_of(registry, cfg, tmp_path, steps)
    assert rig.runner.play("Золото?").requests == []


# report tags

def test_rejected_gold_repeat_adds_report_tag(registry, cfg, tmp_path):
    steps = [
        tools_step(gold_call(2000)), text_step("Кошель."),
        tools_step(gold_call(2000)), text_step("Опять."),
    ]
    rig = rig_of(registry, cfg, tmp_path, steps)
    first = rig.runner.play("Обыскать")
    second = rig.runner.play("Ещё раз")
    assert first.report_tags == []
    assert second.report_tags == ["gold_repeat"]


def test_rejected_rest_repeat_adds_report_tag(registry, cfg, tmp_path):
    steps = [
        tools_step(rest_call()), text_step("Спишь."), tools_step(rest_call()), text_step("Снова."),
    ]
    rig = rig_of(registry, cfg, tmp_path, steps)
    rig.runner.play("Отдыхаю")
    assert rig.runner.play("Снова отдыхаю").report_tags == ["rest_repeat"]


# следующий ход видит итоги в запросе

def test_next_request_has_outcomes_and_no_requests(registry, cfg, tmp_path):
    from game_kit import state_of

    adapter = scripted([tools_step(gold_call(2000)), text_step("Кошель."), text_step("Дальше.")])
    bundle = make_bundle(registry)
    rig = make_rig(registry, cfg, tmp_path, adapter, bundle=bundle)
    rig.runner.play("Обыскать")
    rig.runner.play("Иду")
    turn = state_of(adapter.requests[-1])["recent_turns"][0]
    assert turn["outcomes"] == [f"Золото: +{money.format_cp(2000)}"]
    assert "requests" not in turn


# recent_turns_keep

def test_recent_turns_keep_cuts_records_with_new_fields(registry, cfg, tmp_path):
    steps = [
        tools_step(gold_call(100)), text_step("Один."), text_step("Два."),
        tools_step(gold_call(300, call_id="g3")), text_step("Три."), text_step("Четыре."),
    ]
    rig = rig_of(registry, cfg, tmp_path, steps)
    rig.runner.app_cfg.master.recent_turns_keep = 2
    for n in range(4):
        rig.runner.play(f"ход {n}")
    records = rig.runner.bundle.memory.recent_turns
    assert [r.turn_seq for r in records] == [3, 4]
    assert [r.money_delta_cp for r in records] == [300, 0]


def test_abort_leaves_no_record(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([{"stop": "refusal"}] * 2))
    result = rig.runner.play("Иду")
    assert result.committed is False
    assert rig.runner.bundle.memory.recent_turns == []


# старые записи грузятся с дефолтами

def test_turn_record_defaults():
    record = TurnRecord(turn_seq=1, at_s=0, player_input="a", narration="b")
    assert (record.outcomes, record.money_delta_cp) == ([], 0)


def test_turn_record_outcomes_lists_are_independent():
    first = TurnRecord(turn_seq=1, at_s=0, player_input="a", narration="b")
    second = TurnRecord(turn_seq=2, at_s=0, player_input="a", narration="b")
    first.outcomes.append("x")
    assert second.outcomes == []


@pytest.mark.parametrize("field", ["outcomes", "money_delta_cp"])
def test_turn_record_dump_has_new_fields(field):
    record = TurnRecord(turn_seq=1, at_s=0, player_input="a", narration="b")
    assert field in record.model_dump()
