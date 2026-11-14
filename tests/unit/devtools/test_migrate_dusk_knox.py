# scripts/migrate_dusk_knox.py <каталог мира> -- BACKLOG 231: проверка версии сейва в манифесте
# слота auto: версии 9 и новее принимаются, старше -- отказ без записи. Синтетический мир во
# tmp_path; запуск отдельным процессом.
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[3] / "scripts" / "migrate_dusk_knox.py"


def make_world(root, *, version=14):
    world_dir = root / "dusk_academy-d3de6c57"
    slot = world_dir / "slots" / "auto"
    (slot / "world").mkdir(parents=True)
    (slot / "heroes" / "h1").mkdir(parents=True)
    manifest = {"schema_version": version, "world_id": world_dir.name, "slot": "auto"}
    world = {
        "world_id": world_dir.name, "clock": {"now_s": 100},
        "npcs": {"knox": {"name": "Нокс Велар", "notes": "Старое.", "attitude": 10}},
    }
    (slot / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (slot / "world" / "world.json").write_text(
        json.dumps(world, ensure_ascii=False), encoding="utf-8")
    (slot / "heroes" / "h1" / "hero.json").write_text(
        json.dumps({"id": "h1", "name": "Мая Орлова"}, ensure_ascii=False), encoding="utf-8")
    return world_dir


def run(world_dir):
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), str(world_dir)], capture_output=True, text=True,
        encoding="utf-8", check=False,
    )


def world_bytes(world_dir):
    return (world_dir / "slots" / "auto" / "world" / "world.json").read_bytes()


@pytest.mark.parametrize("version", [9, 14, 15])
def test_supported_versions_are_applied(tmp_path, version):
    world_dir = make_world(tmp_path, version=version)
    before = world_bytes(world_dir)
    assert run(world_dir).returncode == 0
    assert world_bytes(world_dir) != before


def test_version_8_is_refused(tmp_path):
    world_dir = make_world(tmp_path, version=8)
    assert run(world_dir).returncode != 0


def test_version_8_leaves_world_untouched(tmp_path):
    world_dir = make_world(tmp_path, version=8)
    before = world_bytes(world_dir)
    run(world_dir)
    assert world_bytes(world_dir) == before
