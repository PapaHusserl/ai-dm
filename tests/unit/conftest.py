# Общая фикстура: встроенный SRD-слой, загружается один раз на сессию.
# Ожидаемый API: ai_dm.content.loader.load_registry() -> ContentRegistry (test_content_loader.py)
# Импорт внутри фикстуры: пока loader не написан, падают только тесты с registry, а не весь сбор.
import pytest


@pytest.fixture(scope="session")
def registry():
    from ai_dm.content.loader import load_registry

    return load_registry()


@pytest.fixture(scope="session")
def cfg():
    # правила по умолчанию (defaults.toml) -- в коде cfg теперь передаётся явно, без fallback
    from ai_dm.config.settings import load_rules_config

    return load_rules_config()


@pytest.fixture(autouse=True)
def isolated_user_config(tmp_path_factory, monkeypatch):
    # Му-а (MU-PLAN A2): ни один тест не читает пользовательский конфиг разработчика
    # (~/.config/ai-dm): HOME -- пустой временный каталог, явные переменные конфига сняты
    monkeypatch.setenv("HOME", str(tmp_path_factory.getbasetemp() / "home"))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("AI_DM_CONFIG_DIR", raising=False)
