# ТБ #45 (docs/plan-tb.md п.3, Q2а): devtools/prompt_budget.py (make prompt-budget) -- печатает
# замер статики запроса по режимам (правила, инструменты, итог) и длину monster_ids паков;
# без сети и живых вызовов. Допущения контракта (выбраны здесь, это требование к реализации):
# ai_dm.devtools.prompt_budget.main(argv=None) -> int (0 -- успех); вывод -- в stdout, в нём имена
# режимов MODE_TOOLS, имена паков dusk_academy, drunk_dragon и слово monster_ids.
# ТБ #76: [tool.mutmut] also_copy тянет README.md и Makefile -- тесты читают их из корня репо.
import re
import tomllib
from pathlib import Path

import pytest

from ai_dm.protocol.schema import MODE_TOOLS

ROOT = Path(__file__).resolve().parents[3]


def makefile_text():
    return (ROOT / "Makefile").read_text(encoding="utf-8")


def run_main(capsys):
    from ai_dm.devtools.prompt_budget import main

    code = main([])
    return code, capsys.readouterr().out


def test_main_returns_zero(capsys):
    assert run_main(capsys)[0] == 0


@pytest.mark.parametrize("mode", sorted(MODE_TOOLS))
def test_output_mentions_every_mode(capsys, mode):
    assert mode in run_main(capsys)[1]


def test_output_has_numbers(capsys):
    assert re.search(r"\d{3,}", run_main(capsys)[1])


@pytest.mark.parametrize("pack", ["dusk_academy", "drunk_dragon"])
def test_output_mentions_packs_with_monsters_list(capsys, pack):
    assert pack in run_main(capsys)[1]


def test_output_mentions_monster_ids(capsys):
    assert "monster_ids" in run_main(capsys)[1]


# Makefile

def test_makefile_has_prompt_budget_target():
    assert re.search(r"^prompt-budget:", makefile_text(), re.MULTILINE)


def test_prompt_budget_target_runs_the_module():
    text = makefile_text()
    body = text.split("prompt-budget:", 1)[1].split("\n\n", 1)[0]
    assert "prompt_budget" in body


def test_prompt_budget_is_phony():
    line = next(x for x in makefile_text().splitlines() if x.startswith(".PHONY"))
    assert "prompt-budget" in line.split()


def test_prompt_budget_is_not_part_of_quality():
    line = next(x for x in makefile_text().splitlines() if x.startswith("quality:"))
    assert "prompt-budget" not in line


# ТБ #76: mutmut в mutants/ видит README.md и Makefile

def mutmut_config():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["tool"]["mutmut"]


@pytest.mark.parametrize("name", ["README.md", "Makefile"])
def test_mutmut_also_copy_has_file(name):
    assert name in mutmut_config()["also_copy"]


@pytest.mark.parametrize("name", ["campaigns/", "content/", "devtools/", "pyproject.toml"])
def test_mutmut_also_copy_keeps_previous_entries(name):
    assert name in mutmut_config()["also_copy"]


@pytest.mark.parametrize("name", ["README.md", "Makefile"])
def test_mutmut_also_copy_files_exist_in_repo(name):
    assert (ROOT / name).is_file()
