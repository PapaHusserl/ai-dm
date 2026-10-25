"""Отсев выживших мутантов: «в диффе» (строка изменена относительно HEAD), «старые строки»
и «не распознано». Вход — `mutmut results` и `mutmut show`; запуск: make mutate-diff."""

import ast
import re
import subprocess
import sys
from pathlib import Path

RESULT_RE = re.compile(r"^\s+(\S+__mutmut_\d+): (.+?)\s*$")
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
DIFF_FILE_RE = re.compile(r"^\+\+\+ b/(.+)$")


def parse_results(text):
    """Ключи и статусы не-killed мутантов из вывода `mutmut results`."""
    matches = map(RESULT_RE.match, text.splitlines())
    return [(m[1], m[2]) for m in matches if m and m[2] != "not checked"]


def key_to_target(key):
    """`ai_dm.m.xǁClsǁmeth__mutmut_3` -> (src/ai_dm/m.py, Cls.meth); `ai_dm.m.x_f__mutmut_1` -> f"""
    base = key.rsplit("__mutmut_", 1)[0]
    parts = base.split("ǁ")
    if len(parts) == 3:
        module, name = parts[0].rsplit(".", 1)[0], f"{parts[1]}.{parts[2]}"
    else:
        module, name = base.rsplit(".x_", 1)
    return Path("src") / (module.replace(".", "/") + ".py"), name


def function_start(source, name):
    """Строка `def` функции (или Класс.метод) в исходнике; None, если нет."""
    scope = ast.parse(source).body
    *classes, func = name.split(".")
    for cls in classes:
        scope = next((n.body for n in scope if isinstance(n, ast.ClassDef) and n.name == cls), [])
    node = next(
        (
            n
            for n in scope
            if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name == func
        ),
        None,
    )
    if node is None:
        return None
    # mutmut показывает функцию вместе с декораторами и комментариями над ней
    start = min([node.lineno] + [d.lineno for d in node.decorator_list])
    source_lines = source.splitlines()
    for n in range(start - 1, 0, -1):
        text = source_lines[n - 1].strip()
        if text.startswith("#"):
            start = n
        elif text:
            break
    return start


def mutant_lines(show_text, start):
    """Строки файла, затронутые мутантом; номера hunk в `mutmut show` — от `def` (строка 1)."""
    lines = set()
    old = None
    removed = False
    for line in show_text.splitlines():
        m = HUNK_RE.match(line)
        if m:
            old = int(m.group(1))
            removed = False
            continue
        if old is None:
            continue
        if line.startswith("-"):
            lines.add(start + old - 1)
            old += 1
            removed = True
        elif line.startswith("+"):
            if not removed:
                lines.add(start + old - 1)
        else:
            old += 1
            removed = False
    return lines


def diff_ranges(diff_text):
    """Из `git diff -U0`: {путь: множество изменённых строк новой версии}."""
    changed = {}
    path = None
    for line in diff_text.splitlines():
        m = DIFF_FILE_RE.match(line)
        if m:
            path = m.group(1)
            changed.setdefault(path, set())
            continue
        m = HUNK_RE.match(line)
        if m and path:
            first = int(m.group(3))
            count = int(m.group(4) or "1")
            changed[path].update(range(first, first + count))
    return changed


def split_mutants(results, shows, changed, sources):
    """results [(ключ, статус)], shows {ключ: show}, sources {путь: текст}
    -> (в диффе, старые, не распознано): нет исходника, функции или строк мутанта в show."""
    in_diff, old, unknown = [], [], []
    for key, status in results:
        path, name = key_to_target(key)
        start = function_start(sources[path], name) if path in sources else None
        lines = mutant_lines(shows.get(key, ""), start) if start else set()
        if not lines:
            unknown.append(f"{key}: {status}")
        elif lines & changed.get(path.as_posix(), set()):
            in_diff.append(f"{key}: {status}")
        else:
            old.append(f"{key}: {status}")
    return in_diff, old, unknown


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def main():
    results = parse_results(run(["uv", "run", "mutmut", "results"]))
    changed = diff_ranges(run(["git", "diff", "-U0", "HEAD", "--", "src"]))
    # неотслеживаемые файлы src в git diff не попадают: в них все строки новые
    for name in run(["git", "ls-files", "--others", "--exclude-standard", "--", "src"]).split():
        changed[name] = set(range(1, len(Path(name).read_text().splitlines()) + 1))
    sources, shows = {}, {}
    for key, _ in results:
        path, _name = key_to_target(key)
        if path.exists():
            sources[path] = path.read_text()
        shows[key] = run(["uv", "run", "mutmut", "show", key])
    in_diff, old, unknown = split_mutants(results, shows, changed, sources)
    for title, items in (("в диффе", in_diff), ("старые строки", old), ("не распознано", unknown)):
        print(f"{title} ({len(items)}):")
        print("\n".join(f"  {x}" for x in items))
    return 0


if __name__ == "__main__":
    sys.exit(main())
