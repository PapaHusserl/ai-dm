# Партия К7х: новые модули боя (falling, shove) и features, к которому добавился импорт attack,
# импортируются
# в чистом интерпретаторе по одному, без циклического импорта (attack и trophies в одиночку не
# импортируются и до К7х -- они сюда не входят).
import subprocess
import sys

import pytest


@pytest.mark.parametrize("module", [
    "ai_dm.combat.falling",
    "ai_dm.combat.shove",
    "ai_dm.combat.actions.features",
    "ai_dm.combat.actions.improvise",
    "ai_dm.combat.disarm",
    "ai_dm.combat.available",
    "ai_dm.combat.controllers",
    "ai_dm.combat.engine",
])
def test_module_imports_alone(module):
    result = subprocess.run(
        [sys.executable, "-I", "-c", f"import {module}"], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr[-600:]
