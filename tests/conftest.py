import pytest

from ai_dm.persistence import durable


@pytest.fixture(autouse=True)
def durable_off():
    # fsync в тестах не нужен (ускорение); durable-путь включают отдельные тесты
    durable.set_durable(False)
    yield
    durable.set_durable(False)


@pytest.fixture(scope="session")
def app_defaults_zero_min(tmp_path_factory):
    # копия app_defaults.toml с min_narration_chars = 0: защита от короткого рассказа (B59)
    # выключена, иначе сценарии с text_step("Рассказ.") ломаются; тесты защиты включают порог явно
    from ai_dm.config import app as app_module

    text = app_module.APP_DEFAULTS_PATH.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if not ln.startswith("min_narration_chars")]
    at = lines.index("[master]") + 1
    lines.insert(at, "min_narration_chars = 0")
    path = tmp_path_factory.mktemp("app_defaults") / "app_defaults.toml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@pytest.fixture(scope="session", autouse=True)
def min_narration_off(app_defaults_zero_min):
    # session-scope: фикстуры уровня модуля/сессии (сценарии) тоже строят настройки под порогом 0
    from ai_dm.config import app as app_module

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(app_module, "APP_DEFAULTS_PATH", app_defaults_zero_min)
        yield
