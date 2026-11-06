#!/usr/bin/env python3
"""Выставляет [master] context_cap в пользовательском config.toml ai-dm.

Только стандартная библиотека Python 3.11+ (tomllib — лишь чтение). Правка текстом: остальное
содержимое и комментарии сохраняются. Нет файла — создаётся с секцией; нет секции [master] —
дописывается в конец; есть ключ — меняется значение; есть секция без ключа — строка вставляется
сразу под заголовком. Перед записью существующий файл копируется в config.toml.bak-<метка времени>.
После записи tomllib перечитывает файл и сверяет значение.

Запуск: python3 set_context_cap.py [путь к config.toml или каталогу] [значение]
Значение — целое не меньше 8000, по умолчанию 80000. Путь по умолчанию — как в игре:
$AI_DM_CONFIG_DIR, иначе $XDG_CONFIG_HOME/ai-dm, иначе ~/.config/ai-dm.
"""
import os
import re
import shutil
import sys
import tomllib
from datetime import datetime
from pathlib import Path

DEFAULT_CAP = 80000
MIN_CAP = 8000
SECTION_RE = re.compile(r"^\s*\[master\]\s*(#.*)?$")
ANY_SECTION_RE = re.compile(r"^\s*\[")
KEY_RE = re.compile(r"^(\s*context_cap\s*=\s*)[^#\n]*?(\s*(#.*)?)$")


def fail(message):
    print(f"Отказ: {message}. Ничего не записано.")
    sys.exit(1)


def config_dir(env):
    if env.get("AI_DM_CONFIG_DIR"):
        return Path(env["AI_DM_CONFIG_DIR"])
    if env.get("XDG_CONFIG_HOME"):
        return Path(env["XDG_CONFIG_HOME"]) / "ai-dm"
    return Path.home() / ".config" / "ai-dm"


def cap_in(text):
    # значение [master] context_cap или None; [[master]] и не-таблица дают None
    master = tomllib.loads(text).get("master")
    return master.get("context_cap") if isinstance(master, dict) else None


def parse_args(args):
    path, cap = None, DEFAULT_CAP
    for arg in args:
        if re.fullmatch(r"\d+", arg, re.ASCII):
            cap = int(arg)
        elif path is None:
            path = Path(arg).expanduser()
        else:
            print(__doc__)
            sys.exit(2)
    if cap < MIN_CAP:
        fail(f"значение {cap} меньше {MIN_CAP}")
    if path is None:
        return config_dir(os.environ) / "config.toml", cap
    return (path / "config.toml" if path.is_dir() else path), cap


def edit_lines(lines, cap):
    line = f"context_cap = {cap}"
    start = next((i for i, text in enumerate(lines) if SECTION_RE.match(text.rstrip("\n"))), None)
    if start is None:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        if lines and lines[-1].strip():
            lines.append("\n")
        return lines + ["[master]\n", line + "\n"]
    end = next(
        (i for i in range(start + 1, len(lines)) if ANY_SECTION_RE.match(lines[i])), len(lines)
    )
    for i in range(start + 1, end):
        match = KEY_RE.match(lines[i].rstrip("\n"))
        if match:
            lines[i] = f"{match.group(1)}{cap}{match.group(2)}\n"
            return lines
    lines.insert(start + 1, line + "\n")
    return lines


def main():
    if len(sys.argv) > 3:
        print(__doc__)
        sys.exit(2)
    path, cap = parse_args(sys.argv[1:])
    exists = path.is_file()
    text = path.read_text(encoding="utf-8") if exists else ""
    if exists:
        try:
            current = cap_in(text)
        except tomllib.TOMLDecodeError as error:
            fail(f"{path} не читается как TOML ({error})")
        if current == cap:
            print("Уже применено: изменений нет.")
            return
    new_text = "".join(edit_lines(text.splitlines(keepends=True), cap))
    try:
        if cap_in(new_text) != cap:
            fail("после правки значение не читается")
    except tomllib.TOMLDecodeError as error:
        fail(f"после правки файл не читается как TOML ({error})")
    backup = None
    if exists:
        backup = path.with_name(f"{path.name}.bak-{datetime.now():%Y%m%dT%H%M%S}")
        shutil.copy2(path, backup)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(new_text, encoding="utf-8")
    tmp.replace(path)
    check = cap_in(path.read_text(encoding="utf-8"))
    if check != cap:
        print(f"Ошибка: файл {path} уже заменён, но значение {check}, ждали {cap}. Бэкап: {backup}")
        sys.exit(1)
    note = f" Бэкап: {backup}" if backup else ""
    print(f"Готово. {path}: [master] context_cap = {cap}.{note}")


if __name__ == "__main__":
    main()
