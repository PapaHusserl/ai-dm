# Му-а (MU-PLAN, C «качество»): настоящий miniaudio в тестах запрещён -- ни устройства, ни
# нативного кода
# (Д1: segfault под mutmut). Автофикстура ставит sys.modules["miniaudio"] = None: любой
# `import miniaudio` падает ImportError. Тесту плеера Му-б fake-модуль ставится поверх явно.
import sys

import pytest


@pytest.fixture(autouse=True)
def no_real_miniaudio(monkeypatch):
    monkeypatch.setitem(sys.modules, "miniaudio", None)


@pytest.fixture
def fake_miniaudio(monkeypatch):
    # поддельный miniaudio (fake_miniaudio.py): sounds/broken/device_error правятся на модуле
    from fake_miniaudio import make_module

    module = make_module()
    monkeypatch.setitem(sys.modules, "miniaudio", module)
    return module
