# Ожидаемый API: ai_dm.config.app.ReportsConfig(recent_turns: int = 5) в AppConfig.reports
# (этап 6а, P1): сколько последних ходов попадает в report.md; extra запрещён; recent_turns >= 1.
import pytest
from pydantic import ValidationError

from ai_dm.config.app import ReportsConfig, load_settings


def test_reports_config_default_is_five():
    assert ReportsConfig().recent_turns == 5


def test_app_config_has_reports_with_default_five():
    assert load_settings().app.reports.recent_turns == 5


def test_reports_config_accepts_custom_value():
    assert ReportsConfig(recent_turns=12).recent_turns == 12


def test_reports_config_rejects_zero():
    with pytest.raises(ValidationError):
        ReportsConfig(recent_turns=0)


def test_reports_config_rejects_negative():
    with pytest.raises(ValidationError):
        ReportsConfig(recent_turns=-1)


def test_reports_config_rejects_extra_key():
    with pytest.raises(ValidationError):
        ReportsConfig(recent_turns=5, limit=1)
