# ТС #22 (docs/TS-PLAN.md §1 п.2): [memory] summary_trim_after = 2; 0 -- движок не режет; ge=0.
import pytest
from pydantic import ValidationError

from ai_dm.config.app import MemoryConfig, load_settings


def test_memory_config_default_trim_after_is_two():
    assert MemoryConfig().summary_trim_after == 2


def test_app_defaults_toml_has_trim_after_two():
    assert load_settings().app.memory.summary_trim_after == 2


def test_trim_after_is_read_from_memory_section():
    settings = load_settings("[memory]\nsummary_trim_after = 1\n")
    assert settings.app.memory.summary_trim_after == 1


def test_trim_after_override_keeps_other_memory_limits():
    memory = load_settings("[memory]\nsummary_trim_after = 1\n").app.memory
    assert memory.scene_summary_max == 600
    assert memory.chapter_summary_max == 1500
    assert memory.game_summary_max == 3000


def test_trim_after_zero_is_allowed():
    assert MemoryConfig(summary_trim_after=0).summary_trim_after == 0
    assert load_settings("[memory]\nsummary_trim_after = 0\n").app.memory.summary_trim_after == 0


def test_trim_after_rejects_negative():
    with pytest.raises(ValidationError):
        MemoryConfig(summary_trim_after=-1)


def test_trim_after_rejects_text():
    with pytest.raises(ValidationError):
        load_settings('[memory]\nsummary_trim_after = "два"\n')


def test_trim_after_not_above_invalid_retries_by_default():
    app = load_settings().app
    assert app.memory.summary_trim_after <= app.retry.invalid_retries
