# Ожидаемый API: ai_dm.llm.cost (cost_nano, CostLedger, check_limit) -- контракт в llm_kit.py.
# Цены в конфиге -- микро-доллары за 1М токенов, деньги в нано-долларах (int, без float).
# Ручной расчёт: токены * цена(микро-$/1М) / 1000 = нано-$ (Opus вход: 4000 нано-$ за токен).
import json
from datetime import date

import pytest
from llm_kit import DAY, app_cfg
from pydantic import ValidationError

from ai_dm.config.app import CostLimitsConfig, load_settings
from ai_dm.llm.cost import CostLedger, check_limit, cost_nano, pick_price
from ai_dm.llm.types import Usage

OPUS = app_cfg().prices["claude-opus-5-5"]
HAIKU = app_cfg().prices["claude-haiku-4-5"]


def test_cost_nano_zero_usage_is_zero():
    assert cost_nano(Usage(), OPUS) == 0


def test_cost_nano_one_input_token():
    # 4 $ за 1М = 4e-6 $ = 4000 нано-$
    assert cost_nano(Usage(input=1), OPUS) == 4000


def test_cost_nano_one_output_token():
    assert cost_nano(Usage(output=1), OPUS) == 20000


def test_cost_nano_cache_write_token():
    # запись кэша 5m = 1.25× входа
    assert cost_nano(Usage(cache_write=1), OPUS) == 5000


def test_cost_nano_cache_write_1h_token():
    # запись кэша 1h = 2× входа
    assert cost_nano(Usage(cache_write_1h=1), OPUS) == 8000


def test_cost_nano_cache_writes_are_priced_separately():
    usage = Usage(cache_write=1000, cache_write_1h=2000)
    assert cost_nano(usage, OPUS) == 1000 * 5000 + 2000 * 8000


def test_cost_nano_sonnet_cache_writes_by_hand():
    sonnet = app_cfg().prices["claude-sonnet-5-5"]
    # 5m: 2.5 $ за 1М = 2500 нано-$; 1h: 4 $ за 1М = 4000 нано-$
    assert cost_nano(Usage(cache_write=10, cache_write_1h=10), sonnet) == 25_000 + 40_000


def test_cost_nano_haiku_cache_writes_by_hand():
    # 5m: 1.25 $ за 1М = 1250 нано-$; 1h: 2 $ за 1М = 2000 нано-$
    assert cost_nano(Usage(cache_write=8, cache_write_1h=8), HAIKU) == 10_000 + 16_000


def test_cost_nano_cache_read_token():
    assert cost_nano(Usage(cache_read=1), OPUS) == 200


def test_cost_nano_opus_all_four_fields_by_hand():
    usage = Usage(input=1200, output=800, cache_write=5000, cache_read=20000)
    # 1200*4000 + 800*20000 + 5000*5000 + 20000*200 (запись кэша TTL 5m = 1.25× входа)
    # = 4_800_000 + 16_000_000 + 25_000_000 + 4_000_000
    assert cost_nano(usage, OPUS) == 49_800_000


def test_cost_nano_million_input_tokens_is_four_dollars():
    assert cost_nano(Usage(input=1_000_000), OPUS) == 4_000_000_000


def test_cost_nano_haiku_by_hand():
    usage = Usage(input=2000, output=500, cache_write=1000, cache_read=10000)
    # 2000*1000 + 500*5000 + 1000*1250 + 10000*100 = 2_000_000 + 2_500_000 + 1_250_000 + 1_000_000
    assert cost_nano(usage, HAIKU) == 6_750_000


def test_cost_nano_is_int():
    assert type(cost_nano(Usage(input=3, output=7), OPUS)) is int


def read_lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def add(ledger, role="narrator", model="claude-opus-5-5", cost=1000, day=DAY, **kw):
    kw.setdefault("call_id", "c1")
    ledger.add(role=role, model=model, usage=Usage(input=1), cost_nano=cost, day=day, **kw)


def test_ledger_file_is_in_meta_outside_slots(tmp_path):
    ledger = CostLedger(tmp_path / "saves", "w1")
    add(ledger)
    assert (tmp_path / "saves" / "w1" / "meta" / "costs.jsonl").is_file()
    assert not (tmp_path / "saves" / "w1" / "slots").exists()


def test_ledger_writes_one_json_line_per_add(tmp_path):
    ledger = CostLedger(tmp_path / "saves", "w1")
    add(ledger, cost=10)
    add(ledger, role="world", model="claude-haiku-4-5", cost=20)
    lines = read_lines(tmp_path / "saves" / "w1" / "meta" / "costs.jsonl")
    assert [(r["role"], r["model"], r["cost_nano"]) for r in lines] == [
        ("narrator", "claude-opus-5-5", 10), ("world", "claude-haiku-4-5", 20),
    ]


def test_ledger_line_has_day_and_aborted_flag(tmp_path):
    ledger = CostLedger(tmp_path / "saves", "w1")
    add(ledger, aborted=True)
    line = read_lines(tmp_path / "saves" / "w1" / "meta" / "costs.jsonl")[0]
    assert (line["day"], line["aborted"]) == ("2026-10-03", True)


def test_ledger_line_has_call_id(tmp_path):
    ledger = CostLedger(tmp_path / "saves", "w1")
    add(ledger, call_id="call-42")
    line = read_lines(tmp_path / "saves" / "w1" / "meta" / "costs.jsonl")[0]
    assert line["call_id"] == "call-42"


def test_ledger_keeps_call_id_per_line(tmp_path):
    ledger = CostLedger(tmp_path / "saves", "w1")
    add(ledger, call_id="a")
    add(ledger, call_id="b")
    lines = read_lines(tmp_path / "saves" / "w1" / "meta" / "costs.jsonl")
    assert [line["call_id"] for line in lines] == ["a", "b"]


def test_report_of_empty_ledger_is_zero(tmp_path):
    report = CostLedger(tmp_path / "saves", "w1").report(DAY)
    assert (report.session.total_nano, report.day.total_nano, report.world.total_nano) == (0, 0, 0)


def test_report_totals_by_role_and_model(tmp_path):
    ledger = CostLedger(tmp_path / "saves", "w1")
    add(ledger, "narrator", "claude-opus-5-5", 100)
    add(ledger, "narrator", "claude-opus-5-5", 50)
    add(ledger, "world", "claude-haiku-4-5", 7)
    session = ledger.report(DAY).session
    assert session.total_nano == 157
    assert session.by_role == {"narrator": 150, "world": 7}
    assert session.by_model == {"claude-opus-5-5": 150, "claude-haiku-4-5": 7}


def test_report_new_session_starts_from_zero_but_world_keeps_history(tmp_path):
    first = CostLedger(tmp_path / "saves", "w1")
    add(first, cost=100)
    second = CostLedger(tmp_path / "saves", "w1")
    add(second, cost=40)
    report = second.report(DAY)
    assert (report.session.total_nano, report.world.total_nano) == (40, 140)


def test_report_day_covers_all_sessions_of_that_day(tmp_path):
    first = CostLedger(tmp_path / "saves", "w1")
    add(first, cost=100, day=DAY)
    second = CostLedger(tmp_path / "saves", "w1")
    add(second, cost=50, day=DAY)
    assert second.report(DAY).day.total_nano == 150


def test_report_day_excludes_other_days(tmp_path):
    ledger = CostLedger(tmp_path / "saves", "w1")
    add(ledger, cost=100, day=date(2026, 10, 2))
    add(ledger, cost=30, day=DAY)
    report = ledger.report(DAY)
    assert (report.day.total_nano, report.world.total_nano) == (30, 130)


def test_report_day_is_by_the_passed_parameter(tmp_path):
    ledger = CostLedger(tmp_path / "saves", "w1")
    add(ledger, cost=100, day=date(2026, 10, 2))
    assert ledger.report(date(2026, 10, 2)).day.total_nano == 100


def test_report_day_splits_by_role(tmp_path):
    ledger = CostLedger(tmp_path / "saves", "w1")
    add(ledger, "narrator", cost=100)
    add(ledger, "summarizer", "claude-haiku-4-5", 9)
    assert ledger.report(DAY).day.by_role == {"narrator": 100, "summarizer": 9}


def test_report_world_splits_by_model_across_days(tmp_path):
    ledger = CostLedger(tmp_path / "saves", "w1")
    add(ledger, model="claude-opus-5-5", cost=100, day=date(2026, 10, 1))
    add(ledger, model="claude-sonnet-5-5", cost=60, day=DAY)
    assert ledger.report(DAY).world.by_model == {"claude-opus-5-5": 100, "claude-sonnet-5-5": 60}


def test_report_day_sums_all_worlds(tmp_path):
    # P14: дневной лимит общий для всех миров
    add(CostLedger(tmp_path / "saves", "w1"), cost=100)
    other = CostLedger(tmp_path / "saves", "w2")
    add(other, cost=30)
    report = other.report(DAY)
    assert report.day.total_nano == 130
    assert report.world.total_nano == 30


def test_report_day_across_worlds_excludes_other_days(tmp_path):
    add(CostLedger(tmp_path / "saves", "w1"), cost=100, day=date(2026, 10, 2))
    other = CostLedger(tmp_path / "saves", "w2")
    add(other, cost=30)
    assert other.report(DAY).day.total_nano == 30


def test_report_day_splits_by_role_across_worlds(tmp_path):
    add(CostLedger(tmp_path / "saves", "w1"), "narrator", cost=100)
    other = CostLedger(tmp_path / "saves", "w2")
    add(other, "summarizer", "claude-haiku-4-5", 9)
    assert other.report(DAY).day.by_role == {"narrator": 100, "summarizer": 9}


def test_report_ignores_world_folders_without_costs(tmp_path):
    (tmp_path / "saves" / "empty" / "meta").mkdir(parents=True)
    ledger = CostLedger(tmp_path / "saves", "w1")
    add(ledger, cost=5)
    assert ledger.report(DAY).day.total_nano == 5


def test_worlds_are_separate(tmp_path):
    add(CostLedger(tmp_path / "saves", "w1"), cost=100)
    other = CostLedger(tmp_path / "saves", "w2")
    assert other.report(DAY).world.total_nano == 0


def test_aborted_call_cost_is_counted(tmp_path):
    ledger = CostLedger(tmp_path / "saves", "w1")
    add(ledger, cost=100)
    add(ledger, cost=40, aborted=True)
    report = ledger.report(DAY)
    assert (report.session.total_nano, report.day.total_nano, report.world.total_nano) == (
        140, 140, 140,
    )


def test_money_survives_reopening_after_abort(tmp_path):
    # откат хода / загрузка сейва деньги не возвращают: ledger лежит вне слотов и только растёт
    ledger = CostLedger(tmp_path / "saves", "w1")
    add(ledger, cost=40, aborted=True)
    assert CostLedger(tmp_path / "saves", "w1").report(DAY).world.total_nano == 40


def test_totals_are_int(tmp_path):
    ledger = CostLedger(tmp_path / "saves", "w1")
    add(ledger, cost=5)
    assert type(ledger.report(DAY).world.total_nano) is int


# лимит в конфиге -- микро-доллары (как цены), траты -- нано: 1000 микро-$ = 1_000_000 нано-$
LIMIT = 1000
ON = CostLimitsConfig(enabled=True, warn_percent=80)


def test_default_config_limit_is_disabled():
    assert app_cfg().cost_limits.enabled is False


def test_default_limit_amounts_are_zero():
    cfg = app_cfg().cost_limits
    assert (cfg.session_limit_micro, cfg.day_limit_micro) == (0, 0)


def test_limit_amounts_are_set_from_toml():
    text = "[cost_limits]\nsession_limit_micro = 5\nday_limit_micro = 9\n"
    cfg = load_settings(text).app.cost_limits
    assert (cfg.session_limit_micro, cfg.day_limit_micro) == (5, 9)


def test_old_nano_limit_keys_are_rejected():
    with pytest.raises(ValidationError):
        load_settings("[cost_limits]\nsession_limit_nano = 5\n")


def test_enabled_with_zero_limit_is_ok():
    # 0 = лимита нет
    assert check_limit(ON, 10**12, 0) == "ok"


def test_disabled_limit_is_always_ok_even_far_over():
    assert check_limit(app_cfg().cost_limits, LIMIT * 10_000, LIMIT) == "ok"


def test_enabled_below_warn_is_ok():
    assert check_limit(ON, 799_999, LIMIT) == "ok"


def test_enabled_at_80_percent_warns():
    assert check_limit(ON, 800_000, LIMIT) == "warn"


def test_enabled_between_80_and_100_warns():
    assert check_limit(ON, 999_999, LIMIT) == "warn"


def test_enabled_at_100_percent_pauses():
    assert check_limit(ON, 1_000_000, LIMIT) == "pause"


def test_enabled_over_limit_pauses():
    assert check_limit(ON, 1_500_000, LIMIT) == "pause"


def test_warn_percent_is_taken_from_config():
    cfg = CostLimitsConfig(enabled=True, warn_percent=50)
    assert check_limit(cfg, 500_000, LIMIT) == "warn"


@pytest.mark.parametrize("spent", [0, 1])
def test_enabled_zero_spend_is_ok(spent):
    assert check_limit(ON, spent, LIMIT) == "ok"


def test_limit_is_converted_from_micro_to_nano():
    # 1000 микро-$ = 1_000_000 нано-$: ровно на пороге пауза, на единицу ниже -- предупреждение
    assert check_limit(ON, 999_999, 1000) == "warn"
    assert check_limit(ON, 1_000_000, 1000) == "pause"


def test_nano_amount_is_not_taken_as_micro():
    # если бы 1_000_000 трактовалось как нано, 800_000 дало бы warn; в микро это 0.0008 лимита
    assert check_limit(ON, 800_000, 1_000_000) == "ok"


def test_one_micro_limit_is_a_thousand_nano():
    assert check_limit(ON, 999, 1) == "warn"
    assert check_limit(ON, 1000, 1) == "pause"


def test_zero_micro_limit_means_no_limit():
    assert check_limit(ON, 10**15, 0) == "ok"


# цена по фактической модели (ревью партии 3, D14)

def test_pick_price_takes_actual_model_when_priced():
    prices = app_cfg().prices
    model, price, note = pick_price(prices, "claude-opus-5-5", "claude-sonnet-5-5")
    assert (model, price, note) == ("claude-sonnet-5-5", prices["claude-sonnet-5-5"], None)


def test_pick_price_same_model_has_no_note():
    prices = app_cfg().prices
    assert pick_price(prices, "claude-opus-5-5", "claude-opus-5-5")[2] is None


def test_pick_price_falls_back_to_requested_with_note():
    prices = app_cfg().prices
    model, price, note = pick_price(prices, "claude-opus-5-5", "claude-opus-5-5-20261001")
    assert (model, price) == ("claude-opus-5-5", prices["claude-opus-5-5"])
    assert "claude-opus-5-5-20261001" in note
