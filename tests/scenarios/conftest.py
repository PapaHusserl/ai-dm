# Фикстуры сценариев: те же, что в tests/unit/conftest.py (registry и cfg живут только под unit/).
import pytest


@pytest.fixture(scope="session")
def registry():
    from ai_dm.content.loader import load_registry

    return load_registry()


@pytest.fixture(scope="session")
def cfg():
    from ai_dm.config.settings import load_rules_config

    return load_rules_config()


@pytest.fixture(autouse=True)
def isolated_user_config(tmp_path_factory, monkeypatch):
    # как в tests/unit/conftest.py: сценарии не читают пользовательский конфиг (~/.config/ai-dm)
    monkeypatch.setenv("HOME", str(tmp_path_factory.getbasetemp() / "home"))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("AI_DM_CONFIG_DIR", raising=False)
