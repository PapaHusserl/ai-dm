# 19ф Ф1 (docs/19F-PLAN.md п.1.3): [retry] retry_timeouts -- повторять ли после таймаута/504.
import pytest
from pydantic import ValidationError

from ai_dm.config.app import load_settings


def app(toml=None):
    return load_settings(toml).app


def test_default_retry_timeouts_is_false():
    assert app().retry.retry_timeouts is False


def test_retry_timeouts_can_be_turned_on():
    assert app("[retry]\nretry_timeouts = true\n").retry.retry_timeouts is True


def test_retry_timeouts_other_retry_defaults_stay():
    cfg = app("[retry]\nretry_timeouts = true\n").retry
    assert (cfg.delays, cfg.gemini_timeout_s) == ([1, 3, 10], 90)


@pytest.mark.parametrize("value", ['"maybe"', "[1]", '"nope"'])
def test_retry_timeouts_non_bool_is_rejected(value):
    with pytest.raises(ValidationError):
        app(f"[retry]\nretry_timeouts = {value}\n")
