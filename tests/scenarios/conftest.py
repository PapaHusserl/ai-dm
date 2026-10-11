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
