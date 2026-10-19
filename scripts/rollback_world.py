#!/usr/bin/env python3
"""Откат мира к последнему снимку до заданного момента (по умолчанию — до начала сегодняшнего дня).

Только стандартная библиотека Python 3. Игру перед запуском закрыть.

Снимки ищутся везде, где они лежат в каталоге мира: slots/* (auto, auto-N, manual-*), backups/*
(бэкапы миграций) и issues/*/before|after (копии из репортов). Берётся снимок с самым поздним
manifest.saved_at раньше границы. С --apply:
  1. весь каталог мира копируется в <saves>/<мир>.bak-rollback-<метка времени>;
  2. слоты, сохранённые после границы, удаляются (более старые остаются);
  3. выбранный снимок становится слотом auto — «Продолжить» загрузит его.
journal/, meta/costs.jsonl и issues/ не трогаются (история вызовов и деньги не откатываются).

Запуск:
  python3 rollback_world.py saves/<мир>                      # показать, что будет сделано
  python3 rollback_world.py saves/<мир> --list               # все снимки по времени
  python3 rollback_world.py saves/<мир> --apply              # откатить к началу сегодняшнего дня
  python3 rollback_world.py saves/<мир> --before "2026-10-19 14:00" --apply
Граница --before — местное время компьютера.
"""
import argparse
import json
import os
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def is_snapshot(folder: Path) -> bool:
    has_hero = (folder / "heroes").is_dir() or (folder / "hero.json").is_file()
    return (
        (folder / "manifest.json").is_file()
        and (folder / "session.json").is_file()
        and (folder / "world" / "world.json").is_file()
        and has_hero
    )


def saved_at(folder: Path):
    try:
        stamp = read_json(folder / "manifest.json")["saved_at"]
        return datetime.fromisoformat(stamp).astimezone()
    except (OSError, ValueError, KeyError, TypeError):
        return None


def candidates(world: Path):
    found = []
    slots = world / "slots"
    if slots.is_dir():
        visible = [p for p in sorted(slots.iterdir()) if not p.name.startswith(".")]
        found += [(f"слот {p.name}", p) for p in visible]
    backups = world / "backups"
    if backups.is_dir():
        found += [(f"бэкап {p.name}", p) for p in sorted(backups.iterdir())]
    issues = world / "issues"
    if issues.is_dir():
        for report in sorted(issues.iterdir()):
            for side in ("before", "after"):
                # внутри — каталог с id мира; имя каталога мира может отличаться (копия, бэкап)
                for inner in sorted((report / side).glob("*/slots/auto")):
                    found.append((f"репорт {report.name} ({side})", inner))
    result = []
    for label, folder in found:
        if folder.is_dir() and is_snapshot(folder):
            stamp = saved_at(folder)
            if stamp is not None:
                result.append((stamp, label, folder))
    return sorted(result, key=lambda item: item[0])


def parse_before(text):
    if text is None:
        return datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    return datetime.fromisoformat(text).astimezone()


def describe(folder: Path) -> str:
    session = read_json(folder / "session.json")
    turn = session.get("turn") or session.get("turn_seq") or "?"
    version = read_json(folder / "manifest.json").get("schema_version", "?")
    return f"ход {turn}, схема v{version}"


def apply(world: Path, chosen: Path, newer_slots) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = world.parent / f"{world.name}.bak-rollback-{stamp}"
    shutil.copytree(world, backup)
    slots = world / "slots"
    staged = slots / f".rollback-{uuid.uuid4().hex}"
    # снимок может лежать в удаляемом слоте — сначала копия, потом удаление
    shutil.copytree(chosen, staged)
    for folder in newer_slots:
        shutil.rmtree(folder)
    manifest_path = staged / "manifest.json"
    manifest = read_json(manifest_path)
    manifest["slot"] = "auto"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    target = slots / "auto"
    if target.exists():
        shutil.rmtree(target)
    os.replace(staged, target)
    return backup


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Откат мира к последнему снимку до границы.")
    parser.add_argument("world", type=Path, help="каталог мира: saves/<мир>")
    parser.add_argument("--before", help="граница, местное время: 'YYYY-MM-DD [HH:MM]'")
    parser.add_argument("--apply", action="store_true", help="выполнить откат (иначе показать)")
    parser.add_argument("--list", action="store_true", help="показать все снимки по времени")
    args = parser.parse_args(argv)

    world = args.world.resolve()
    if not (world / "slots").is_dir():
        print(f"Не каталог мира (нет slots/): {world}", file=sys.stderr)
        return 2
    border = parse_before(args.before)
    snapshots = candidates(world)
    if args.list:
        for stamp, label, folder in snapshots:
            mark = "  " if stamp < border else "* "
            print(f"{mark}{stamp:%Y-%m-%d %H:%M:%S}  {describe(folder):<18}  {label}")
        print("(* — после границы)\n")
    older = [item for item in snapshots if item[0] < border]
    if not older:
        print(f"Нет снимков раньше {border:%Y-%m-%d %H:%M}.", file=sys.stderr)
        return 1
    stamp, label, chosen = older[-1]
    slots = world / "slots"
    newer_slots = [
        folder for _, _, folder in snapshots
        if folder.parent == slots and saved_at(folder) >= border
    ]

    print(f"Мир: {world.name}")
    print(f"Граница: {border:%Y-%m-%d %H:%M} (местное время)")
    print(f"Откат к: {label} — сохранён {stamp:%Y-%m-%d %H:%M:%S}, {describe(chosen)}")
    if snapshots[-1][0] >= border:
        last = snapshots[-1]
        print(f"Сейчас последнее: {last[1]} — {last[0]:%Y-%m-%d %H:%M:%S}, {describe(last[2])}")
    print("Удалятся слоты после границы: " + (", ".join(p.name for p in newer_slots) or "нет"))
    if not args.apply:
        print("\nЭто проверка. Для отката — тот же запуск с --apply (игра должна быть закрыта).")
        return 0
    backup = apply(world, chosen, newer_slots)
    print(f"\nГотово. Полная копия мира до отката: {backup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
