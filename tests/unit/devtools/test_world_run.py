# Ожидаемый API (П4 этапа 3, критерий 2): ai_dm.devtools.world_run.run_world -- 30 границ мини-пака
# по дню с моком роли world. Контракт run_world и main -- в tests/unit/game/world_kit.py.
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "world_sim"))

import pytest  # noqa: E402
from world_kit import MINI_DIR, ReactiveWorld  # noqa: E402

from ai_dm.llm.mock import ScriptedAdapter  # noqa: E402
from ai_dm.llm.replay import ReplayAdapter, ReplayDivergence  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[2] / "fixtures" / "scripts" / "world_30d.yaml"
FLAGS = {"met_brann": True}


def run(registry, cfg, tmp_path, *, seed=7, world=None, pack=MINI_DIR, mortality=30):
    from ai_dm.devtools.world_run import run_world

    return run_world(
        registry, cfg, pack, days=30, seed=seed, world_adapter=world or ReactiveWorld(),
        saves_root=tmp_path, flags=FLAGS, mortality_per_day=mortality,
    )


def requests_dump(run_result):
    return [
        (r["role"], r["request"]["fingerprint"]) for r in run_result.journal.read_records()
    ]


def chronicle_dump(run_result):
    return run_result.chronicle.model_dump_json()


def test_thirty_days_pass_one_day_per_boundary(registry, cfg, tmp_path):
    result = run(registry, cfg, tmp_path)
    assert result.bundle.world.clock.now_s >= 30 * 86400


def test_two_runs_give_identical_bundles(registry, cfg, tmp_path):
    first = run(registry, cfg, tmp_path / "a")
    second = run(registry, cfg, tmp_path / "b")
    assert first.bundle.world.model_dump_json() == second.bundle.world.model_dump_json()
    assert first.bundle.model_dump_json() == second.bundle.model_dump_json()


def test_two_runs_give_identical_chronicle_and_request_log(registry, cfg, tmp_path):
    first = run(registry, cfg, tmp_path / "a")
    second = run(registry, cfg, tmp_path / "b")
    assert chronicle_dump(first) == chronicle_dump(second)
    assert requests_dump(first) == requests_dump(second)


def test_world_journal_has_only_world_role_calls_with_boundary_run_ids(registry, cfg, tmp_path):
    records = run(registry, cfg, tmp_path).journal.read_records()
    assert records
    assert {r["role"] for r in records} == {"world"}
    assert all(r["run_id"].startswith("bnd-") for r in records)


def test_other_seed_gives_other_chronicle(registry, cfg, tmp_path):
    # смертность «Жестокий» и события сезона (П5): хроника зависит от сида
    first = run(registry, cfg, tmp_path / "a", seed=1)
    second = run(registry, cfg, tmp_path / "b", seed=2)
    assert chronicle_dump(first) != chronicle_dump(second)


def test_replay_of_recorded_world_gives_same_bundle(registry, cfg, tmp_path):
    first = run(registry, cfg, tmp_path / "a")
    records = first.journal.read_records()
    replay = ReplayAdapter(records, role="world")
    second = run(registry, cfg, tmp_path / "b", world=replay)
    assert first.bundle.model_dump_json() == second.bundle.model_dump_json()


def test_replay_on_changed_pack_diverges(registry, cfg, tmp_path):
    first = run(registry, cfg, tmp_path / "a")
    records = first.journal.read_records()
    pack = tmp_path / "pack"
    shutil.copytree(MINI_DIR, pack)
    npcs = pack / "npcs.yaml"
    text = npcs.read_text(encoding="utf-8")
    npcs.write_text(
        text.replace("Бранн открывает проход", "Бранн закрывает проход"), encoding="utf-8"
    )
    with pytest.raises(ReplayDivergence):
        run(registry, cfg, tmp_path / "b", world=ReplayAdapter(records, role="world"), pack=pack)


def test_scripted_yaml_mock_runs_without_mortality(registry, cfg, tmp_path):
    # world_30d.yaml: 30 вердиктов (день 3 -- Бранн доверяет) + видимая заметка
    world = ScriptedAdapter.from_yaml(SCRIPT)
    result = run(registry, cfg, tmp_path, world=world, mortality=None)
    assert world.steps == []
    assert any(e.kind == "trigger" for e in result.bundle.chronicle.entries)


def test_cli_main_runs_and_returns_zero(registry, cfg, tmp_path, capsys):
    from ai_dm.devtools.world_run import main

    code = main(
        ["--pack", str(MINI_DIR), "--days", "30", "--seed", "7", "--mock", str(SCRIPT),
         "--flag", "met_brann", "--out", str(tmp_path)]
    )
    assert code == 0
    assert capsys.readouterr().out
