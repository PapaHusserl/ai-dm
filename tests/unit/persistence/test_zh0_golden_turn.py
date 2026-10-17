# Ж0 (docs/plan-zh0.md, п. 12, риск 6): золотой ход на фикстуре сейва v10.
# Снимок tests/golden/zh0_turn.json снят движком main ДО правок Ж0 (схема v10): ход со skill_check
# через ScriptedAdapter на слоте tests/fixtures/saves/v10 (мир zh0_world: герой Арн, NPC с
# relations_text, сцена, world.sim). После Ж0 слот v10 мигрирует в v11 при загрузке (load_slot) --
# тот же ход обязан дать тот же снимок: тест не меняется, меняется только то, что load_slot делает
# внутри. Чтобы сравнить именно мигрированный бандл, достаточно добавить значение в FIXTURES.
#
# В снимок входят только наблюдаемые следствия хода, не зависящие от формы сейва: строки хода и
# броска, запись памяти хода, состояние rng, часы, герой (hp, деньги, инвентарь), id/отношение/
# место NPC, счётчики сцены. Исключены: run_id и метки времени журнала (недетерминированы или
# привязаны к now), saved_at/slot/schema_version манифеста, полные дампы моделей NPC/сцены/мира
# (новые поля v11 их меняют по замыслу), текст запросов к модели (промпт меняет и Ж0).
import json
import shutil
from pathlib import Path

import pytest
from game_kit import make_rig, scripted, skill_check_call, text_step, tools_step
from persist_kit import load_slot

TESTS = Path(__file__).resolve().parents[2]
FIXTURE_V10 = TESTS / "fixtures" / "saves" / "v10"
GOLDEN = TESTS / "golden" / "zh0_turn.json"
BACKUP_TS = "20260101T000000Z"
WORLD_ID = "zh0_world"
FIXTURES = [FIXTURE_V10]
PLAYER_INPUT = "Убеждаю Гарта открыть подвал"
NARRATION = "Гарт хмурится, но кивает и достаёт ключ."


def load_fixture(saves, fixture):
    target = saves / WORLD_ID / "slots" / "auto"
    shutil.copytree(fixture, target)
    return load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS)


def snapshot(bundle, result):
    hero = bundle.heroes[0]
    world = bundle.world
    scene = bundle.session.current_scene
    record = bundle.memory.recent_turns[-1]
    data = {
        "lines": result.lines,
        "requests": result.requests,
        "committed": result.committed,
        "record": {
            "turn_seq": record.turn_seq,
            "at_s": record.at_s,
            "player_input": record.player_input,
            "narration": record.narration,
            "requests": record.requests,
            "rolls": record.rolls,
            "outcomes": record.outcomes,
            "money_delta_cp": record.money_delta_cp,
        },
        "rng": json.loads(world.rng.model_dump_json()),
        "now_s": world.clock.now_s,
        "turn_seq": bundle.session.turn_seq,
        "scene": {
            "id": scene.id,
            "location_id": scene.location_id,
            "player_turns": scene.player_turns,
        },
        "hero": {
            "hp_current": hero.creature.hp_current,
            "money_cp": hero.money_cp,
            "location_id": hero.location_id,
            "inventory": [[i.item_id, i.qty] for i in hero.inventory],
        },
        "npcs": {
            npc_id: {
                "attitude": npc.attitude,
                "location_id": npc.location_id,
                "status": npc.status,
            }
            for npc_id, npc in sorted(world.npcs.items())
        },
        "recent_turns": len(bundle.memory.recent_turns),
    }
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def play_turn(registry, cfg, tmp_path, fixture):
    bundle = load_fixture(tmp_path / "saves", fixture)
    steps = [tools_step(skill_check_call()), text_step(NARRATION)]
    rig = make_rig(registry, cfg, tmp_path / "run", scripted(steps), bundle=bundle)
    result = rig.runner.play(PLAYER_INPUT)
    return snapshot(rig.runner.bundle, result)


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda p: p.name)
def test_golden_turn_matches_snapshot(registry, cfg, tmp_path, fixture):
    assert play_turn(registry, cfg, tmp_path, fixture) == GOLDEN.read_text(encoding="utf-8")


def test_golden_turn_is_deterministic(registry, cfg, tmp_path):
    first = play_turn(registry, cfg, tmp_path / "a", FIXTURE_V10)
    second = play_turn(registry, cfg, tmp_path / "b", FIXTURE_V10)
    assert first == second


def test_golden_turn_rolled_a_check(registry, cfg, tmp_path):
    data = json.loads(play_turn(registry, cfg, tmp_path, FIXTURE_V10))
    assert data["requests"] == ["skill_check"]
    assert len(data["record"]["rolls"]) == 1
    assert data["rng"]["draws"] > 35
