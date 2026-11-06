# scripts/set_context_cap.py [путь] [значение] -- правка [master] context_cap в config.toml
# текстом: файла нет / секции нет / ключ есть / секция без ключа; бэкап, идемпотентность,
# отказы. Запуск отдельным процессом, каталог конфигурации -- tmp_path.
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[3] / "scripts" / "set_context_cap.py"


def run(*args, env=None):
    skipped = ("AI_DM_CONFIG_DIR", "XDG_CONFIG_HOME")
    full_env = {k: v for k, v in os.environ.items() if k not in skipped}
    full_env.update(env or {})
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), *map(str, args)], capture_output=True, text=True,
        encoding="utf-8", check=False, env=full_env,
    )


def cfg(tmp_path, text=None):
    path = tmp_path / "config.toml"
    if text is not None:
        path.write_text(text, encoding="utf-8")
    return path


def cap_of(path):
    return tomllib.loads(path.read_text(encoding="utf-8"))["master"]["context_cap"]


def baks(tmp_path):
    return sorted(tmp_path.glob("config.toml.bak-*"))


def test_creates_missing_file_with_default(tmp_path):
    path = cfg(tmp_path)
    result = run(path)
    assert result.returncode == 0
    assert result.stdout.startswith("Готово.")
    assert path.read_text(encoding="utf-8") == "[master]\ncontext_cap = 80000\n"
    assert baks(tmp_path) == []


def test_creates_missing_directory(tmp_path):
    path = tmp_path / "new" / "config.toml"
    assert run(path).returncode == 0
    assert cap_of(path) == 80000


def test_custom_value(tmp_path):
    path = cfg(tmp_path)
    run(path, 12000)
    assert cap_of(path) == 12000


def test_value_may_come_before_path(tmp_path):
    path = cfg(tmp_path)
    run(12000, path)
    assert cap_of(path) == 12000


def test_directory_argument(tmp_path):
    assert run(tmp_path).returncode == 0
    assert cap_of(tmp_path / "config.toml") == 80000


def test_env_ai_dm_config_dir(tmp_path):
    assert run(env={"AI_DM_CONFIG_DIR": str(tmp_path)}).returncode == 0
    assert cap_of(tmp_path / "config.toml") == 80000


def test_env_xdg_config_home(tmp_path):
    assert run(env={"XDG_CONFIG_HOME": str(tmp_path)}).returncode == 0
    assert cap_of(tmp_path / "ai-dm" / "config.toml") == 80000


def test_appends_section_keeping_content(tmp_path):
    original = "# мой конфиг\n[ui]\ntheme = 'dark'\n"
    path = cfg(tmp_path, original)
    run(path)
    text = path.read_text(encoding="utf-8")
    assert text.startswith(original)
    assert text.endswith("[master]\ncontext_cap = 80000\n")
    assert cap_of(path) == 80000


def test_appends_section_to_file_without_trailing_newline(tmp_path):
    path = cfg(tmp_path, "[ui]\ntheme = 'dark'")
    run(path)
    assert cap_of(path) == 80000
    assert tomllib.loads(path.read_text(encoding="utf-8"))["ui"]["theme"] == "dark"


def test_replaces_existing_value_keeping_comment_and_neighbours(tmp_path):
    original = (
        "[master]\nmodel = 'x'\ncontext_cap = 32000  # старое\nother = 1\n[ui]\ncontext_cap = 5\n"
    )
    path = cfg(tmp_path, original)
    run(path)
    assert path.read_text(encoding="utf-8") == original.replace(
        "context_cap = 32000  # старое", "context_cap = 80000  # старое"
    )


def test_inserts_key_right_under_header(tmp_path):
    path = cfg(tmp_path, "[master]  # блок\nmodel = 'x'\n[ui]\nt = 1\n")
    run(path)
    assert path.read_text(encoding="utf-8") == (
        "[master]  # блок\ncontext_cap = 80000\nmodel = 'x'\n[ui]\nt = 1\n"
    )


def test_key_in_other_section_is_not_replaced(tmp_path):
    path = cfg(tmp_path, "[ui]\ncontext_cap = 5\n[master]\n")
    run(path)
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["ui"]["context_cap"] == 5
    assert data["master"]["context_cap"] == 80000


def test_backup_has_original_bytes(tmp_path):
    original = "[master]\ncontext_cap = 32000\n"
    path = cfg(tmp_path, original)
    run(path)
    found = baks(tmp_path)
    assert len(found) == 1
    assert found[0].read_text(encoding="utf-8") == original


def test_no_tmp_file_left(tmp_path):
    run(cfg(tmp_path, "[ui]\n"))
    assert not list(tmp_path.glob("*.tmp"))


def test_second_run_says_already_applied(tmp_path):
    path = cfg(tmp_path, "[master]\ncontext_cap = 32000\n")
    run(path)
    before = path.read_bytes()
    result = run(path)
    assert result.returncode == 0
    assert "Уже применено: изменений нет." in result.stdout
    assert path.read_bytes() == before
    assert len(baks(tmp_path)) == 1


@pytest.mark.parametrize("value", ["7999", "100"])
def test_value_below_minimum_is_refused(tmp_path, value):
    path = cfg(tmp_path, "[ui]\n")
    result = run(path, value)
    assert result.returncode == 1
    assert "Отказ" in result.stdout
    assert path.read_text(encoding="utf-8") == "[ui]\n"


def test_minimum_value_is_accepted(tmp_path):
    path = cfg(tmp_path)
    run(path, 8000)
    assert cap_of(path) == 8000


def test_broken_toml_is_refused_untouched(tmp_path):
    path = cfg(tmp_path, "[master\n")
    result = run(path)
    assert result.returncode == 1
    assert path.read_text(encoding="utf-8") == "[master\n"
    assert baks(tmp_path) == []


def test_too_many_arguments_exits_two(tmp_path):
    assert run(tmp_path, 9000, "extra").returncode == 2


def test_non_ascii_digit_is_not_a_number(tmp_path):
    # «²» -- не значение: второй путь -> код 2, без трейсбека
    result = run(cfg(tmp_path, "[ui]\n"), "²")
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


# подтаблицы, inline-таблица, массив таблиц

def test_subtable_right_after_master_keeps_it_and_gets_key_under_master(tmp_path):
    path = cfg(tmp_path, "[master]\n[master.x]\na = 1\n")
    run(path)
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["master"]["context_cap"] == 80000
    assert data["master"]["x"] == {"a": 1}
    assert path.read_text(encoding="utf-8").startswith("[master]\ncontext_cap = 80000\n")


def test_subtable_without_master_appends_master_section(tmp_path):
    path = cfg(tmp_path, "[master.x]\na = 1\n")
    run(path)
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["master"] == {"x": {"a": 1}, "context_cap": 80000}


def test_context_cap_in_other_section_only(tmp_path):
    path = cfg(tmp_path, "[ui]\ncontext_cap = 5\n")
    run(path)
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["ui"]["context_cap"] == 5
    assert data["master"]["context_cap"] == 80000


@pytest.mark.parametrize("text", ["master = {a = 1}\n", "[[master]]\na = 1\n"])
def test_inline_table_and_array_of_tables_are_refused_untouched(tmp_path, text):
    path = cfg(tmp_path, text)
    result = run(path)
    assert result.returncode == 1
    assert "Отказ" in result.stdout
    assert "Traceback" not in result.stderr
    assert path.read_text(encoding="utf-8") == text
    assert baks(tmp_path) == []
