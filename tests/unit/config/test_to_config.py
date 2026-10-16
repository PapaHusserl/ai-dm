# ТО (docs/TO-PLAN.md §1 п.5, Q3а): [reports] max_mb = 200; 0 -- без лимита; ge=0.
import pytest
from pydantic import ValidationError

from ai_dm.config.app import ReportsConfig, load_settings


def test_reports_config_default_max_mb_is_200():
    assert ReportsConfig().max_mb == 200


def test_app_defaults_toml_has_max_mb_200():
    assert load_settings().app.reports.max_mb == 200


def test_max_mb_zero_is_allowed():
    assert ReportsConfig(max_mb=0).max_mb == 0


def test_max_mb_accepts_custom_value():
    assert ReportsConfig(max_mb=7).max_mb == 7


def test_max_mb_rejects_negative():
    with pytest.raises(ValidationError):
        ReportsConfig(max_mb=-1)


def test_recent_turns_still_defaults_to_five():
    assert ReportsConfig().recent_turns == 5
