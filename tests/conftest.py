import pytest

from ai_dm.persistence import durable


@pytest.fixture(autouse=True)
def durable_off():
    # fsync в тестах не нужен (ускорение); durable-путь включают отдельные тесты
    durable.set_durable(False)
    yield
    durable.set_durable(False)
