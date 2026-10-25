# devtools/mutants_in_diff.py (make mutate-diff): отсев выживших мутантов:
# «в диффе» / «старые» / «не распознано».
# Шаг 202 П1: синтетические строки, без запуска mutmut и git; run() подменён.
# Формат `mutmut show` проверен на mutmut 3.8.0: hunk идёт от первого комментария над def.
import importlib.util
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parents[3] / "devtools" / "mutants_in_diff.py"

PROMPT_KEY = "ai_dm.master.prompt.xǁPromptBuilderǁstate_data__mutmut_3"
MONEY_KEY = "ai_dm.rules.money.x_to_cp__mutmut_1"
PROMPT_PATH = Path("src/ai_dm/master/prompt.py")

SOURCE = """\
X = 1


def top(a):
    return a


class Box:
    def inner(self):
        return 1

    async def waiter(self):
        return 2
"""

DECORATED = """\
X = 1


# комментарий над функцией
# второй комментарий

def commented(a):
    return a


class Box:
    # комментарий над методом

    @staticmethod
    def sm(a):
        return a


@deco
def decorated(a):
    return a


# комментарий над декоратором
@deco
def both(a):
    return a


def plain(a):
    return a
"""


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("mutants_in_diff", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def show(hunk, *body):
    return "\n".join(["--- a/x.py", "+++ b/x.py", hunk, *body])


def test_key_to_target_method(mod):
    assert mod.key_to_target(PROMPT_KEY) == (PROMPT_PATH, "PromptBuilder.state_data")


def test_key_to_target_function(mod):
    assert mod.key_to_target(MONEY_KEY) == (Path("src/ai_dm/rules/money.py"), "to_cp")


def test_parse_results_skips_not_checked(mod):
    text = f"    {MONEY_KEY}: not checked\n    {PROMPT_KEY}: survived\n"
    assert mod.parse_results(text) == [(PROMPT_KEY, "survived")]


def test_parse_results_keeps_other_statuses(mod):
    text = f"    {MONEY_KEY}: timeout\n    {PROMPT_KEY}: no tests\n"
    assert mod.parse_results(text) == [(MONEY_KEY, "timeout"), (PROMPT_KEY, "no tests")]


def test_parse_results_ignores_noise_lines(mod):
    text = "Running stats\nResults:\nai_dm.m.x_f__mutmut_1: survived\n"
    text += "    ai_dm.m.x_f__mutmut_2: survived\n"
    assert mod.parse_results(text) == [("ai_dm.m.x_f__mutmut_2", "survived")]


def test_parse_results_empty(mod):
    assert mod.parse_results("") == []


def test_function_start_top_level(mod):
    assert mod.function_start(SOURCE, "top") == 4


def test_function_start_method(mod):
    assert mod.function_start(SOURCE, "Box.inner") == 9


def test_function_start_async_method(mod):
    assert mod.function_start(SOURCE, "Box.waiter") == 12


def test_function_start_missing_function(mod):
    assert mod.function_start(SOURCE, "nope") is None


def test_function_start_missing_class(mod):
    assert mod.function_start(SOURCE, "Ghost.inner") is None


def test_function_start_includes_comments_above_def(mod):
    # комментарии на строках 4–5, пустая строка 6, def на 7; show начинается с первого комментария
    assert mod.function_start(DECORATED, "commented") == 4


def test_function_start_includes_comment_above_method_decorator(mod):
    assert mod.function_start(DECORATED, "Box.sm") == 12


def test_function_start_includes_decorator(mod):
    assert mod.function_start(DECORATED, "decorated") == 19


def test_function_start_comment_above_decorator(mod):
    assert mod.function_start(DECORATED, "both") == 24


def test_function_start_skips_blank_lines_without_comment(mod):
    assert mod.function_start(DECORATED, "plain") == 30


def test_function_start_does_not_swallow_previous_code(mod):
    # над `top` только пустые строки и код X = 1 — начало остаётся на def
    assert mod.function_start(SOURCE, "top") == 4


def test_mutant_lines_shift_from_function_start(mod):
    assert mod.mutant_lines(show("@@ -5 +5 @@", "-    a", "+    b"), 529) == {533}


def test_mutant_lines_first_line_is_def(mod):
    assert mod.mutant_lines(show("@@ -1 +1 @@", "-def f():", "+def g():"), 10) == {10}


def test_mutant_lines_context_advances_line(mod):
    text = show("@@ -2,3 +2,3 @@", " ctx", "-old", "+new", " ctx2")
    assert mod.mutant_lines(text, 100) == {102}


def test_mutant_lines_pure_removal(mod):
    assert mod.mutant_lines(show("@@ -3,2 +3 @@", "-a", "-b"), 10) == {12, 13}


def test_mutant_lines_pure_insertion_marks_following_line(mod):
    text = show("@@ -4,0 +5 @@", "+new")
    assert mod.mutant_lines(text, 10) == {13}


def test_mutant_lines_empty_text(mod):
    assert mod.mutant_lines("", 10) == set()


def test_mutant_lines_header_lines_not_counted(mod):
    assert mod.mutant_lines("--- a/x.py\n+++ b/x.py\n", 10) == set()


def test_mutant_lines_real_mutmut_show_with_comment_above_def(mod):
    # дословный вывод mutmut 3.8.0 для функции из DECORATED с комментариями над def (строка 4)
    text = show(
        "@@ -2,5 +2,5 @@",
        " # второй комментарий",
        " ",
        " def commented(a):",
        "-    return a",
        "+    return None",
    )
    start = mod.function_start(DECORATED, "commented")
    assert mod.mutant_lines(text, start) == {8}


def test_diff_ranges_added_lines(mod):
    diff = "+++ b/src/a.py\n@@ -530,0 +531,2 @@ def f\n+x\n+y\n"
    assert mod.diff_ranges(diff) == {"src/a.py": {531, 532}}


def test_diff_ranges_single_line_without_count(mod):
    diff = "+++ b/src/a.py\n@@ -7 +7 @@\n-a\n+b\n"
    assert mod.diff_ranges(diff) == {"src/a.py": {7}}


def test_diff_ranges_pure_deletion_adds_nothing(mod):
    diff = "+++ b/src/a.py\n@@ -7,2 +6,0 @@\n-a\n-b\n"
    assert mod.diff_ranges(diff) == {"src/a.py": set()}


def test_diff_ranges_several_hunks_and_files(mod):
    diff = "+++ b/src/a.py\n@@ -1 +1 @@\n@@ -9,0 +10,2 @@\n+++ b/src/b.py\n@@ -3 +3 @@\n"
    assert mod.diff_ranges(diff) == {"src/a.py": {1, 10, 11}, "src/b.py": {3}}


def test_diff_ranges_empty(mod):
    assert mod.diff_ranges("") == {}


def split(mod, shows, changed):
    results = [(PROMPT_KEY, "survived")]
    code = "class PromptBuilder:\n    def state_data(self):\n        pass\n"
    sources = {PROMPT_PATH: "\n" * 528 + code}
    return mod.split_mutants(results, shows, changed, sources)


def test_split_mutant_in_diff(mod):
    # def state_data на строке 530; hunk -2 -> строка 531
    shows = {PROMPT_KEY: show("@@ -2 +2 @@", "-a", "+b")}
    result = split(mod, shows, {PROMPT_PATH.as_posix(): {531}})
    assert result == ([f"{PROMPT_KEY}: survived"], [], [])


def test_split_mutant_outside_diff_is_old(mod):
    shows = {PROMPT_KEY: show("@@ -2 +2 @@", "-a", "+b")}
    result = split(mod, shows, {PROMPT_PATH.as_posix(): {600}})
    assert result == ([], [f"{PROMPT_KEY}: survived"], [])


def test_split_mutant_on_removed_line_does_not_fail(mod):
    shows = {PROMPT_KEY: show("@@ -2,2 +2 @@", "-a", "-b")}
    result = split(mod, shows, {PROMPT_PATH.as_posix(): {531}})
    assert result == ([f"{PROMPT_KEY}: survived"], [], [])


def test_split_file_not_in_diff_is_old(mod):
    shows = {PROMPT_KEY: show("@@ -2 +2 @@", "-a", "+b")}
    result = split(mod, shows, {})
    assert result == ([], [f"{PROMPT_KEY}: survived"], [])


def test_split_missing_source_is_unknown(mod):
    changed = {"src/ai_dm/rules/money.py": {1}}
    shows = {MONEY_KEY: show("@@ -2 +2 @@", "-a", "+b")}
    result = mod.split_mutants([(MONEY_KEY, "survived")], shows, changed, {})
    assert result == ([], [], [f"{MONEY_KEY}: survived"])


def test_split_missing_show_is_unknown(mod):
    result = split(mod, {}, {PROMPT_PATH.as_posix(): {531}})
    assert result == ([], [], [f"{PROMPT_KEY}: survived"])


def test_split_show_without_hunks_is_unknown(mod):
    shows = {PROMPT_KEY: "# ключ: survived\n--- a/x.py\n+++ b/x.py\n"}
    result = split(mod, shows, {PROMPT_PATH.as_posix(): {531}})
    assert result == ([], [], [f"{PROMPT_KEY}: survived"])


def test_split_function_not_found_is_unknown(mod):
    results = [(PROMPT_KEY, "survived")]
    shows = {PROMPT_KEY: show("@@ -2 +2 @@", "-a", "+b")}
    sources = {PROMPT_PATH: "X = 1\n"}
    changed = {PROMPT_PATH.as_posix(): {2}}
    result = mod.split_mutants(results, shows, changed, sources)
    assert result == ([], [], [f"{PROMPT_KEY}: survived"])


def test_split_three_lists_at_once(mod):
    other = "ai_dm.master.prompt.xǁPromptBuilderǁstate_data__mutmut_4"
    lost = "ai_dm.master.prompt.xǁPromptBuilderǁstate_data__mutmut_5"
    results = [(PROMPT_KEY, "survived"), (other, "survived"), (lost, "timeout")]
    shows = {
        PROMPT_KEY: show("@@ -2 +2 @@", "-a", "+b"),
        other: show("@@ -3 +3 @@", "-a", "+b"),
    }
    code = "class PromptBuilder:\n    def state_data(self):\n        pass\n"
    sources = {PROMPT_PATH: "\n" * 528 + code}
    changed = {PROMPT_PATH.as_posix(): {531}}
    result = mod.split_mutants(results, shows, changed, sources)
    assert result == (
        [f"{PROMPT_KEY}: survived"],
        [f"{other}: survived"],
        [f"{lost}: timeout"],
    )


def test_main_empty_results_returns_zero(mod, monkeypatch, capsys):
    monkeypatch.setattr(mod, "run", lambda cmd: "")
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert "в диффе (0):" in out
    assert "старые строки (0):" in out
    assert "не распознано (0):" in out


def test_main_diffs_against_head(mod, monkeypatch):
    sent = []
    monkeypatch.setattr(mod, "run", lambda cmd: sent.append(list(cmd)) or "")
    mod.main()
    assert ["git", "diff", "-U0", "HEAD", "--", "src"] in sent


def test_main_prints_all_three_lists(mod, monkeypatch, capsys, tmp_path):
    src = tmp_path / "src" / "ai_dm"
    src.mkdir(parents=True)
    (src / "m.py").write_text("def f():\n    return 1\n    return 2\n")
    key = "ai_dm.m.x_f__mutmut_1"
    old_key = "ai_dm.m.x_f__mutmut_2"
    lost_key = "ai_dm.gone.x_g__mutmut_1"

    def fake_run(cmd):
        if cmd[:4] == ["uv", "run", "mutmut", "results"]:
            return f"    {key}: survived\n    {old_key}: survived\n    {lost_key}: survived\n"
        if cmd[:4] == ["uv", "run", "mutmut", "show"]:
            line = "@@ -2 +2 @@" if cmd[4] == key else "@@ -3 +3 @@"
            return show(line, "-a", "+b")
        if cmd[:2] == ["git", "ls-files"]:
            return ""
        return "+++ b/src/ai_dm/m.py\n@@ -2 +2 @@\n"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "run", fake_run)
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert f"в диффе (1):\n  {key}: survived\n" in out
    assert f"старые строки (1):\n  {old_key}: survived\n" in out
    assert f"не распознано (1):\n  {lost_key}: survived" in out


def test_main_untracked_file_counts_as_new(mod, monkeypatch, capsys, tmp_path):
    src = tmp_path / "src" / "ai_dm"
    src.mkdir(parents=True)
    (src / "fresh.py").write_text("def f():\n    return 1\n    return 2\n")
    key = "ai_dm.fresh.x_f__mutmut_1"
    asked = []

    def fake_run(cmd):
        asked.append(list(cmd))
        if cmd[:4] == ["uv", "run", "mutmut", "results"]:
            return f"    {key}: survived\n"
        if cmd[:4] == ["uv", "run", "mutmut", "show"]:
            return show("@@ -3 +3 @@", "-a", "+b")
        if cmd[:2] == ["git", "ls-files"]:
            return "src/ai_dm/fresh.py\n"
        return ""  # git diff: пусто, файл не отслеживается

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "run", fake_run)
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert f"в диффе (1):\n  {key}: survived\n" in out
    assert ["git", "ls-files", "--others", "--exclude-standard", "--", "src"] in asked


def test_main_untracked_file_not_in_results_is_ignored(mod, monkeypatch, capsys, tmp_path):
    src = tmp_path / "src" / "ai_dm"
    src.mkdir(parents=True)
    (src / "fresh.py").write_text("def f():\n    return 1\n")

    def fake_run(cmd):
        return "src/ai_dm/fresh.py\n" if cmd[:2] == ["git", "ls-files"] else ""

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "run", fake_run)
    assert mod.main() == 0
    assert "в диффе (0):" in capsys.readouterr().out
