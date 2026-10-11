# Критерий 1 этапа 3 (STAGE3-PLAN, часть C, П3): «триггер NPC по флагу срабатывает на границе
# сцены». Мини-пак tests/fixtures/packs/mini/ (aldric: {flag: grail_seen}, once; mara:
# {flag: alarm}, cooldown 7d), мок-модель (ScriptedAdapter): ход ставит флаг и закрывает сцену
# (end_scene), TurnRunner делает границу. Критерий 2 (30 дней, роль world) -- партия 4.
# Контракт: tests/unit/world_sim/world_sim_kit.py, tests/unit/game/game_kit.py.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "game"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "world_sim"))

from game_kit import (  # noqa: E402
    advance_call,
    end_scene_call,
    flag_call,
    make_rig,
    scripted,
    text_step,
    tools_step,
)
from world_kit import ReactiveWorld  # noqa: E402
from world_sim_kit import mini_bundle  # noqa: E402

DAY = 86400


def play(registry, cfg, tmp_path, turns, bundle=None):
    # turns: список списков вызовов инструментов, по одному ходу на список; ход = вызовы + рассказ
    steps = []
    for calls in turns:
        steps += [tools_step(*calls), text_step("Конец сцены.")]
    if bundle is None:
        bundle = mini_bundle(registry, cfg)
    rig = make_rig(registry, cfg, tmp_path, scripted(steps), bundle=bundle)
    rig.runner.world_adapter = ReactiveWorld()
    for n in range(len(turns)):
        rig.runner.play(f"ход {n}")
    return rig


def flag_and_end(flag, n=1):
    return [flag_call(flag, f"f{n}"), end_scene_call(f"e{n}")]


def end_after(category, n):
    return [advance_call(f"a{n}", category=category), end_scene_call(f"e{n}")]


def trigger_of(bundle, npc_id, trigger_id):
    return next(t for t in bundle.world.npcs[npc_id].opportunity if t.id == trigger_id)


def test_criterion1_npc_trigger_fires_on_scene_boundary(registry, cfg, tmp_path):
    rig = play(registry, cfg, tmp_path, [flag_and_end("grail_seen")])
    trigger = trigger_of(rig.runner.bundle, "aldric", "steal_grail")
    assert trigger.fired_count == 1
    assert trigger.state == "fired"


def test_trigger_does_not_fire_without_flag(registry, cfg, tmp_path):
    rig = play(registry, cfg, tmp_path, [[end_scene_call("e1")]])
    assert trigger_of(rig.runner.bundle, "aldric", "steal_grail").fired_count == 0


def test_trigger_fire_is_in_chronicle_and_world_fired(registry, cfg, tmp_path):
    bundle = play(registry, cfg, tmp_path, [flag_and_end("grail_seen")]).runner.bundle
    kinds = [e.kind for e in bundle.chronicle.entries]
    assert kinds.count("trigger") == 1
    assert len(bundle.world.fired) == 1


def test_once_trigger_does_not_fire_on_next_boundary(registry, cfg, tmp_path):
    turns = [flag_and_end("grail_seen"), [end_scene_call("e2")]]
    bundle = play(registry, cfg, tmp_path, turns).runner.bundle
    assert trigger_of(bundle, "aldric", "steal_grail").fired_count == 1
    assert len(bundle.world.fired) == 1


def test_cooldown_trigger_fires_again_only_after_seven_days(registry, cfg, tmp_path):
    turns = [flag_and_end("alarm"), end_after("day", 2), end_after("week", 3)]
    rig = play(registry, cfg, tmp_path, turns[:2])
    assert trigger_of(rig.runner.bundle, "mara", "mara_shout").fired_count == 1
    rig = play(registry, cfg, tmp_path / "second", turns)
    assert trigger_of(rig.runner.bundle, "mara", "mara_shout").fired_count == 2


def test_dead_npc_trigger_does_not_fire_on_boundary(registry, cfg, tmp_path):
    bundle = mini_bundle(registry, cfg)
    bundle.world.npcs["aldric"].status = "dead"
    rig = play(registry, cfg, tmp_path, [flag_and_end("grail_seen")], bundle=bundle)
    assert trigger_of(rig.runner.bundle, "aldric", "steal_grail").fired_count == 0


def test_faction_trigger_fires_on_boundary_after_npc_death_flag(registry, cfg, tmp_path):
    bundle = mini_bundle(registry, cfg)
    bundle.world.npcs["mara"].status = "dead"
    rig = play(registry, cfg, tmp_path, [[end_scene_call("e1")]], bundle=bundle)
    assert rig.runner.bundle.world.factions["guild"].opportunity[0].fired_count == 1


def test_boundary_with_trigger_is_deterministic(registry, cfg, tmp_path):
    first = play(registry, cfg, tmp_path / "a", [flag_and_end("grail_seen")])
    second = play(registry, cfg, tmp_path / "b", [flag_and_end("grail_seen")])
    assert first.runner.bundle.model_dump_json() == second.runner.bundle.model_dump_json()


def test_fired_trigger_survives_save_and_load(registry, cfg, tmp_path):
    # автосейв второй границы (закрытая сцена, до её тика) уже содержит итог первой
    from ai_dm.persistence.store import load_slot

    play(registry, cfg, tmp_path, [flag_and_end("grail_seen"), [end_scene_call("e2")]])
    saved = load_slot(tmp_path, "w1", "auto")
    assert trigger_of(saved, "aldric", "steal_grail").fired_count == 1


# Критерий 2 этапа 3 (П4): «ход мира на 30 дней с мок-моделью world по сиду даёт идентичный
# результат». 30 границ по дню (advance_time day + end_scene), мини-пак, мок world без сети.
# Контракт devtools.world_run.run_world и ReactiveWorld -- tests/unit/game/world_kit.py.
def world_30_days(registry, cfg, root, seed=7, world=None):
    from world_kit import MINI_DIR, ReactiveWorld

    from ai_dm.devtools.world_run import run_world

    return run_world(
        registry, cfg, MINI_DIR, days=30, seed=seed, world_adapter=world or ReactiveWorld(),
        saves_root=root, flags={"met_brann": True}, mortality_per_day=30,
    )


def test_criterion2_thirty_days_with_mock_world_are_reproducible(registry, cfg, tmp_path):
    first = world_30_days(registry, cfg, tmp_path / "a")
    second = world_30_days(registry, cfg, tmp_path / "b")
    assert first.bundle.model_dump_json() == second.bundle.model_dump_json()
    assert first.chronicle.model_dump_json() == second.chronicle.model_dump_json()
    assert first.journal.read_records() != []


def test_criterion2_world_was_called_on_boundaries(registry, cfg, tmp_path):
    result = world_30_days(registry, cfg, tmp_path)
    runs = {r["run_id"] for r in result.journal.read_records() if r["role"] == "world"}
    assert 1 <= len(runs) <= 30


def test_criterion2_other_seed_gives_other_chronicle(registry, cfg, tmp_path):
    # смертность и сезон (П5): хроника зависит от сида
    first = world_30_days(registry, cfg, tmp_path / "a", seed=1)
    second = world_30_days(registry, cfg, tmp_path / "b", seed=2)
    assert first.chronicle.model_dump_json() != second.chronicle.model_dump_json()


def test_criterion2_replay_gives_same_bundle(registry, cfg, tmp_path):
    from ai_dm.llm.replay import ReplayAdapter

    first = world_30_days(registry, cfg, tmp_path / "a")
    replay = ReplayAdapter(first.journal.read_records(), role="world")
    second = world_30_days(registry, cfg, tmp_path / "b", world=replay)
    assert first.bundle.model_dump_json() == second.bundle.model_dump_json()


# П7: 30 дней world_run на реальном паке «Пьяный Дракон» с мок-world по сиду -- идентичный результат
def dragon_30_days(root, seed=7):
    from world_kit import ReactiveWorld

    from ai_dm.campaign.loader import load_pack, pack_content_dir
    from ai_dm.config.settings import load_rules_config
    from ai_dm.content.loader import load_registry
    from ai_dm.devtools.world_run import run_world

    pack_dir = Path(__file__).resolve().parents[2] / "campaigns" / "drunk_dragon"
    content = pack_content_dir(pack_dir)
    registry = load_registry([content] if content is not None else [])
    load_pack(pack_dir, registry)
    return run_world(
        registry, load_rules_config(), pack_dir, days=30, seed=seed,
        world_adapter=ReactiveWorld(), saves_root=root,
    )


def test_dragon_pack_thirty_days_with_mock_world_are_reproducible(tmp_path):
    first = dragon_30_days(tmp_path / "a")
    second = dragon_30_days(tmp_path / "b")
    assert first.bundle.model_dump_json() == second.bundle.model_dump_json()
    assert first.chronicle.model_dump_json() == second.chronicle.model_dump_json()
