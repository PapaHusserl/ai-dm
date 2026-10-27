# B59: [master] min_narration_chars, [llm] thinking / thinking_display. Autouse-фикстура conftest
# подменяет APP_DEFAULTS_PATH копией с min_narration_chars = 0; настоящий файл читается явно.
from pathlib import Path

import pytest
from pydantic import ValidationError

import ai_dm.config.app as app_module
from ai_dm.config.app import load_settings

REAL = Path(app_module.__file__).parent / "app_defaults.toml"


@pytest.fixture
def real_defaults(monkeypatch):
    monkeypatch.setattr(app_module, "APP_DEFAULTS_PATH", REAL)


def test_real_defaults_min_narration_chars_is_80(real_defaults):
    assert load_settings().app.master.min_narration_chars == 80


def test_test_defaults_have_the_check_off():
    assert load_settings().app.master.min_narration_chars == 0


def test_min_narration_chars_can_be_set_by_user(real_defaults):
    settings = load_settings("[master]\nmin_narration_chars = 120\n")
    assert settings.app.master.min_narration_chars == 120


def test_min_narration_chars_zero_is_valid(real_defaults):
    assert load_settings("[master]\nmin_narration_chars = 0\n").app.master.min_narration_chars == 0


def test_min_narration_chars_negative_is_error():
    with pytest.raises(ValidationError):
        load_settings("[master]\nmin_narration_chars = -1\n")


def test_real_defaults_thinking_narrator_adaptive_summarized(real_defaults):
    llm = load_settings().app.llm
    assert llm.thinking == {"narrator": "adaptive"}
    assert llm.thinking_display == "summarized"


def test_thinking_display_omitted_is_valid():
    assert load_settings('[llm]\nthinking_display = "omitted"\n').app.llm.thinking_display == (
        "omitted"
    )


@pytest.mark.parametrize("text", [
    '[llm]\nthinking = { narrator = "enabled" }\n',
    '[llm]\nthinking = { narrator = "disabled" }\n',
    '[llm]\nthinking = { world = "adaptive" }\n',
    '[llm]\nthinking = { foo = "adaptive" }\n',
    '[llm]\nthinking_display = "full"\n',
    '[master]\nmin_narration_chars = "много"\n',
])
def test_bad_values_are_errors(text):
    with pytest.raises(ValidationError):
        load_settings(text)
