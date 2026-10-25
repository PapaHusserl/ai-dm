# Ожидаемый API: ai_dm.game.scene и закрытие сцены в TurnRunner -- контракт в game_kit.py.
# ТЗ 4.0: сцену закрывают end_scene, смена локации, скачок времени > 1 ч (hour -- нет), конец боя,
# 31-й ход игрока; +600 с, если время не сдвигалось; автосейв закрытой сцены; новая сцена.
import pytest
from game_kit import (
    advance_call,
    core_dump,
    end_scene_call,
    make_rig,
    scripted,
    start_combat_call,
    text_step,
    tools_step,
)
from protocol_kit import make_bundle
from slots_kit import list_slots, saved_close_reason

from ai_dm.persistence.store import load_slot

# game.scene напрямую

def test_start_scene_after_scene_1_is_scene_2(registry):
    from ai_dm.game.scene import start_scene

    bundle = make_bundle(registry)
    bundle.world.clock.advance(500)
    bundle.heroes[0].location_id = "forest"
    scene = start_scene(bundle)
    assert bundle.session.current_scene is scene
    assert scene.id == "scene_2"
    assert scene.started_at_s == 500
    assert scene.location_id == "forest"
    assert scene.player_turns == 0
    assert scene.closed_reason is None
    assert scene.attitude_spent == {}


def test_start_scene_without_scene_is_scene_1(registry):
    from ai_dm.game.scene import start_scene

    bundle = make_bundle(registry, with_scene=False)
    assert start_scene(bundle).id == "scene_1"


def test_scene_ids_keep_counting(registry):
    from ai_dm.game.scene import start_scene

    bundle = make_bundle(registry)
    start_scene(bundle)
    start_scene(bundle)
    assert bundle.session.current_scene.id == "scene_3"


# Фикс dusk П2 (173): scene_npc_ids и перенос метки scene_mood (npcs_before)

def moody(registry, mood="romance"):
    # сцена в «vale» с меткой; в локации героя живёт grakh
    bundle = make_bundle(registry)
    bundle.session.current_scene.scene_mood = mood
    return bundle


def test_scene_npc_ids_are_alive_npcs_in_hero_location(registry):
    from ai_dm.game.scene import scene_npc_ids

    assert scene_npc_ids(make_bundle(registry)) == {"grakh"}


def test_scene_npc_ids_skip_dead(registry):
    from ai_dm.game.scene import scene_npc_ids

    bundle = make_bundle(registry)
    bundle.world.npcs["grakh"].status = "dead"
    assert scene_npc_ids(bundle) == set()


def test_scene_npc_ids_skip_other_location(registry):
    from ai_dm.game.scene import scene_npc_ids

    bundle = make_bundle(registry)
    bundle.world.npcs["grakh"].location_id = "forest"
    assert scene_npc_ids(bundle) == set()


def test_scene_npc_ids_follow_hero_location(registry):
    from ai_dm.game.scene import scene_npc_ids

    bundle = make_bundle(registry)
    bundle.heroes[0].location_id = "forest"
    assert scene_npc_ids(bundle) == set()


def test_scene_npc_ids_do_not_change_bundle(registry):
    from ai_dm.game.scene import scene_npc_ids

    bundle = make_bundle(registry)
    before = bundle.model_dump_json()
    scene_npc_ids(bundle)
    assert bundle.model_dump_json() == before


def test_start_scene_carries_mood_when_place_and_npcs_same(registry):
    from ai_dm.game.scene import scene_npc_ids, start_scene

    bundle = moody(registry)
    assert start_scene(bundle, npcs_before=scene_npc_ids(bundle)).scene_mood == "romance"


def test_start_scene_carries_exact_mood_string(registry):
    from ai_dm.game.scene import start_scene

    bundle = moody(registry, mood="custom")
    assert start_scene(bundle, npcs_before={"grakh"}).scene_mood == "custom"


def test_start_scene_carries_mood_with_empty_npc_set(registry):
    from ai_dm.game.scene import start_scene

    bundle = moody(registry)
    bundle.world.npcs["grakh"].status = "dead"
    assert start_scene(bundle, npcs_before=set()).scene_mood == "romance"


def test_start_scene_without_npcs_before_does_not_carry(registry):
    from ai_dm.game.scene import start_scene

    assert start_scene(moody(registry)).scene_mood == ""


def test_start_scene_drops_mood_when_location_changed(registry):
    from ai_dm.game.scene import start_scene

    bundle = moody(registry)
    bundle.heroes[0].location_id = "forest"
    assert start_scene(bundle, npcs_before=set()).scene_mood == ""


def test_start_scene_drops_mood_when_scene_npc_left(registry):
    from ai_dm.game.scene import start_scene

    bundle = moody(registry)
    bundle.world.npcs["grakh"].location_id = "forest"
    assert start_scene(bundle, npcs_before={"grakh"}).scene_mood == ""


def test_start_scene_drops_mood_when_scene_npc_died(registry):
    from ai_dm.game.scene import start_scene

    bundle = moody(registry)
    bundle.world.npcs["grakh"].status = "dead"
    assert start_scene(bundle, npcs_before={"grakh"}).scene_mood == ""


def test_start_scene_drops_mood_when_scene_npc_vanished_from_world(registry):
    from ai_dm.game.scene import start_scene

    bundle = moody(registry)
    del bundle.world.npcs["grakh"]
    assert start_scene(bundle, npcs_before={"grakh"}).scene_mood == ""


def test_start_scene_keeps_mood_when_newcomer_arrived(registry):
    from ai_dm.game.scene import start_scene

    bundle = moody(registry)
    bundle.world.npcs["aldric"].location_id = "vale"
    assert start_scene(bundle, npcs_before={"grakh"}).scene_mood == "romance"


def test_start_scene_does_not_carry_empty_mood(registry):
    from ai_dm.game.scene import start_scene

    bundle = moody(registry, mood="")
    assert start_scene(bundle, npcs_before={"grakh"}).scene_mood == ""


def test_start_scene_first_scene_has_no_mood(registry):
    from ai_dm.game.scene import start_scene

    bundle = make_bundle(registry, with_scene=False)
    assert start_scene(bundle, npcs_before=set()).scene_mood == ""


def test_start_scene_carry_does_not_touch_old_scene_object(registry):
    from ai_dm.game.scene import start_scene

    bundle = moody(registry)
    old = bundle.session.current_scene
    new = start_scene(bundle, npcs_before={"grakh"})
    assert new is not old
    assert old.scene_mood == "romance"
    assert new.id == "scene_2"


def test_end_scene_keeps_romance_for_same_place_and_npc(registry, cfg, tmp_path):
    bundle = moody(registry)
    steps = [tools_step(end_scene_call()), text_step("Конец сцены.")]
    rig, _ = play(registry, cfg, tmp_path, steps, bundle=bundle)
    scene = rig.runner.bundle.session.current_scene
    assert scene.id == "scene_2"
    assert scene.scene_mood == "romance"


def test_travel_drops_mood_with_new_scene(registry, cfg, tmp_path):
    bundle = moody(registry)
    steps = [tools_step(advance_call(travel_to="forest")), text_step("Лес.")]
    rig, _ = play(registry, cfg, tmp_path, steps, bundle=bundle)
    scene = rig.runner.bundle.session.current_scene
    assert scene.id == "scene_2"
    assert scene.scene_mood == ""


def check(bundle, cfg, **kw):
    from ai_dm.game.scene import check_close

    kw.setdefault("time_before_s", bundle.world.clock.now_s)
    return check_close(bundle, cfg, **kw)


def test_no_reason_for_quiet_turn(registry, cfg):
    assert check(make_bundle(registry), cfg) is None


def test_check_close_keeps_end_scene_reason(registry, cfg):
    bundle = make_bundle(registry)
    bundle.session.current_scene.closed_reason = "end_scene"
    assert check(bundle, cfg) == "end_scene"


def test_check_close_location_changed(registry, cfg):
    bundle = make_bundle(registry)
    bundle.heroes[0].location_id = "forest"
    assert check(bundle, cfg) == "location_changed"


def test_check_close_time_jump_is_strictly_more_than_limit(registry, cfg):
    bundle = make_bundle(registry)
    limit = cfg.scene.max_time_jump_s
    bundle.world.clock.advance(limit)
    assert check(bundle, cfg, time_before_s=0) is None
    bundle.world.clock.advance(1)
    assert check(bundle, cfg, time_before_s=0) == "time_jump"


def test_check_close_combat_ended_flag(registry, cfg):
    assert check(make_bundle(registry), cfg, combat_ended=True) == "combat_ended"


def test_check_close_turn_limit_is_strictly_more_than_max(registry, cfg):
    bundle = make_bundle(registry)
    bundle.session.current_scene.player_turns = cfg.scene.max_player_turns
    assert check(bundle, cfg) is None
    bundle.session.current_scene.player_turns += 1
    assert check(bundle, cfg) == "turn_limit"


def test_check_close_time_jump_uses_difference_not_sum(registry, cfg):
    bundle = make_bundle(registry)
    start = cfg.scene.max_time_jump_s * 2
    bundle.world.clock.advance(start)
    assert check(bundle, cfg, time_before_s=start) is None
    bundle.world.clock.advance(cfg.scene.max_time_jump_s + 1)
    assert check(bundle, cfg, time_before_s=start) == "time_jump"


def test_check_close_does_not_change_bundle(registry, cfg):
    bundle = make_bundle(registry)
    bundle.heroes[0].location_id = "forest"
    before = bundle.model_dump_json()
    check(bundle, cfg)
    assert bundle.model_dump_json() == before


def test_check_close_priority_end_scene_then_location_then_time(registry, cfg):
    bundle = make_bundle(registry)
    bundle.heroes[0].location_id = "forest"
    bundle.world.clock.advance(cfg.scene.max_time_jump_s + 1)
    assert check(bundle, cfg, time_before_s=0) == "location_changed"
    bundle.session.current_scene.closed_reason = "end_scene"
    assert check(bundle, cfg, time_before_s=0) == "end_scene"


def test_check_close_time_jump_beats_combat_ended_and_turn_limit(registry, cfg):
    bundle = make_bundle(registry)
    bundle.world.clock.advance(cfg.scene.max_time_jump_s + 1)
    bundle.session.current_scene.player_turns = cfg.scene.max_player_turns + 1
    assert check(bundle, cfg, time_before_s=0, combat_ended=True) == "time_jump"


def test_check_close_combat_ended_beats_turn_limit(registry, cfg):
    bundle = make_bundle(registry)
    bundle.session.current_scene.player_turns = cfg.scene.max_player_turns + 1
    assert check(bundle, cfg, combat_ended=True) == "combat_ended"


def test_check_close_end_scene_beats_everything(registry, cfg):
    bundle = make_bundle(registry)
    bundle.session.current_scene.closed_reason = "end_scene"
    bundle.heroes[0].location_id = "forest"
    assert check(bundle, cfg, combat_ended=True) == "end_scene"


def test_close_scene_sets_reason_and_adds_min_advance(registry, cfg):
    from ai_dm.game.scene import close_scene

    bundle = make_bundle(registry)
    close_scene(bundle, "end_scene", cfg)
    assert bundle.session.current_scene.closed_reason == "end_scene"
    assert bundle.world.clock.now_s == cfg.time.min_advance_s == 600


def test_close_scene_does_not_add_time_if_time_moved(registry, cfg):
    from ai_dm.game.scene import close_scene

    bundle = make_bundle(registry)
    bundle.world.clock.advance(900)
    close_scene(bundle, "end_scene", cfg)
    assert bundle.world.clock.now_s == 900


# закрытие сцены в ходе

def play(registry, cfg, tmp_path, steps, bundle=None, text="Иду"):
    rig = make_rig(registry, cfg, tmp_path, scripted(steps), bundle=bundle)
    result = rig.runner.play(text)
    return rig, result


def test_end_scene_closes_scene_and_opens_new_one(registry, cfg, tmp_path):
    steps = [tools_step(end_scene_call()), text_step("Конец сцены.")]
    rig, _ = play(registry, cfg, tmp_path, steps)
    assert saved_close_reason(tmp_path, "w1") == "end_scene"
    scene = rig.runner.bundle.session.current_scene
    assert scene.id == "scene_2"
    assert scene.closed_reason is None
    assert scene.player_turns == 0


def test_end_scene_autosave_holds_closed_scene(registry, cfg, tmp_path):
    steps = [tools_step(end_scene_call()), text_step("Конец сцены.")]
    rig, _ = play(registry, cfg, tmp_path, steps)
    assert list_slots(tmp_path, "w1") == ["auto"]
    saved = load_slot(tmp_path, "w1", "auto")
    assert saved.session.current_scene.id == "scene_1"
    assert saved.session.current_scene.closed_reason == "end_scene"
    assert saved.session.turn_seq == 1
    assert saved.memory.recent_turns[-1].narration == "Конец сцены."


def test_end_scene_without_time_gets_turn_tick_and_no_min_advance(registry, cfg, tmp_path):
    steps = [tools_step(end_scene_call()), text_step()]
    rig, _ = play(registry, cfg, tmp_path, steps)
    assert rig.runner.bundle.world.clock.now_s == 900
    assert rig.runner.bundle.session.current_scene.started_at_s == 900


def test_end_scene_after_time_moved_has_no_extra_advance(registry, cfg, tmp_path):
    steps = [
        tools_step(advance_call(category="hour"), end_scene_call()), text_step(),
    ]
    rig, _ = play(registry, cfg, tmp_path, steps)
    assert rig.runner.bundle.world.clock.now_s == 3600


def test_autosave_is_written_at_scene_boundary_only(registry, cfg, tmp_path):
    rig, _ = play(registry, cfg, tmp_path, [text_step()])
    assert saved_close_reason(tmp_path, "w1") is None
    assert list_slots(tmp_path, "w1") == []


def test_two_scene_closures_rotate_autosaves(registry, cfg, tmp_path):
    steps = [
        tools_step(end_scene_call("e1")), text_step("Раз."),
        tools_step(end_scene_call("e2")), text_step("Два."),
    ]
    rig = make_rig(registry, cfg, tmp_path, scripted(steps))
    rig.runner.play("a")
    rig.runner.play("b")
    assert list_slots(tmp_path, "w1") == ["auto", "auto-1"]
    assert load_slot(tmp_path, "w1", "auto").session.current_scene.id == "scene_2"
    assert load_slot(tmp_path, "w1", "auto-1").session.current_scene.id == "scene_1"


def test_travel_to_closes_scene_by_location(registry, cfg, tmp_path):
    steps = [tools_step(advance_call(travel_to="forest")), text_step("Лес.")]
    rig, _ = play(registry, cfg, tmp_path, steps)
    bundle = rig.runner.bundle
    assert saved_close_reason(tmp_path, "w1") == "location_changed"
    assert bundle.heroes[0].location_id == "forest"
    assert bundle.world.flags["visited:forest"] is True
    assert bundle.session.current_scene.location_id == "forest"
    assert load_slot(tmp_path, "w1", "auto").session.current_scene.closed_reason == (
        "location_changed"
    )


def test_travel_time_follows_distance(registry, cfg, tmp_path):
    # 4800 м при шаге normal (4800 м/ч) -- ровно час, без добавки +600 с
    steps = [tools_step(advance_call(travel_to="forest")), text_step()]
    rig, _ = play(registry, cfg, tmp_path, steps)
    assert rig.runner.bundle.world.clock.now_s == 3600


@pytest.mark.parametrize("category", ["day", "week", "month"])
def test_time_jump_over_hour_closes_scene(registry, cfg, tmp_path, category):
    steps = [tools_step(advance_call(category=category)), text_step()]
    rig, _ = play(registry, cfg, tmp_path, steps)
    assert saved_close_reason(tmp_path, "w1") == "time_jump"
    assert rig.runner.bundle.session.current_scene.id == "scene_2"
    assert list_slots(tmp_path, "w1") == ["auto"]


def test_short_time_does_not_close_scene(registry, cfg, tmp_path):
    steps = [tools_step(advance_call(category="hour")), text_step()]
    rig, _ = play(registry, cfg, tmp_path, steps)
    assert saved_close_reason(tmp_path, "w1") is None
    assert rig.runner.bundle.session.current_scene.id == "scene_1"
    assert rig.runner.bundle.session.current_scene.closed_reason is None
    assert list_slots(tmp_path, "w1") == []


def test_turn_limit_closes_scene_on_31st_turn(registry, cfg, tmp_path):
    bundle = make_bundle(registry)
    bundle.session.current_scene.player_turns = cfg.scene.max_player_turns - 1
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step(), text_step()]), bundle=bundle)
    rig.runner.play("30-й")
    assert saved_close_reason(tmp_path, "w1") is None
    assert rig.runner.bundle.session.current_scene.player_turns == 30
    rig.runner.play("31-й")
    assert saved_close_reason(tmp_path, "w1") == "turn_limit"
    assert rig.runner.bundle.session.current_scene.id == "scene_2"
    assert load_slot(tmp_path, "w1", "auto").session.current_scene.closed_reason == "turn_limit"


def test_max_player_turns_comes_from_config(registry, cfg, tmp_path):
    cfg2 = cfg.model_copy(deep=True)
    cfg2.scene.max_player_turns = 2
    rig = make_rig(registry, cfg2, tmp_path, scripted([text_step(), text_step(), text_step()]))
    rig.runner.play("a")
    rig.runner.play("b")
    assert saved_close_reason(tmp_path, "w1") is None
    rig.runner.play("c")
    assert saved_close_reason(tmp_path, "w1") == "turn_limit"


def test_failed_turn_closes_nothing_and_saves_nothing(registry, cfg, tmp_path):
    steps = [tools_step(end_scene_call())] + [{"error": "fatal"}]
    rig, result = play(registry, cfg, tmp_path, steps)
    assert result.committed is False
    assert rig.runner.bundle.session.current_scene.id == "scene_1"
    assert rig.runner.bundle.session.current_scene.closed_reason is None
    assert list_slots(tmp_path, "w1") == []
    assert rig.runner.bundle.world.clock.now_s == 0


def test_combat_start_does_not_close_scene(registry, cfg, tmp_path):
    steps = [tools_step(start_combat_call()), text_step("Бой!")]
    rig, _ = play(registry, cfg, tmp_path, steps)
    assert saved_close_reason(tmp_path, "w1") is None
    assert rig.runner.bundle.session.current_scene.id == "scene_1"
    assert list_slots(tmp_path, "w1") == []


def test_autosave_equals_committed_state_of_closing_turn(registry, cfg, tmp_path):
    steps = [tools_step(end_scene_call()), text_step("Финал.")]
    rig, _ = play(registry, cfg, tmp_path, steps)
    saved = load_slot(tmp_path, "w1", "auto")
    live = rig.runner.bundle
    # sim исключён: тик границы (после сейва) инициализирует last_season/last_year у живого
    assert saved.world.model_dump_json(exclude={"sim"}) == live.world.model_dump_json(
        exclude={"sim"}
    )
    # выжимку сцены пишет шаг 1 границы после автосейва (этап 4)
    assert saved.memory.recent_turns == live.memory.recent_turns
    assert saved.memory.scenes == []
    assert saved.heroes[0].model_dump_json() == live.heroes[0].model_dump_json()
    # живой бандл уже в новой сцене, сейв -- в закрытой
    assert core_dump(saved) != core_dump(live)


# D5: одна hero_of в game.scene

def test_hero_of_returns_current_hero(registry):
    from ai_dm.game.scene import hero_of

    bundle = make_bundle(registry)
    assert hero_of(bundle) is bundle.heroes[0]


def test_hero_of_follows_current_hero_id(registry):
    from ai_dm.game.scene import hero_of

    bundle = make_bundle(registry)
    second = bundle.heroes[0].model_copy(deep=True)
    second.id = "hero2"
    bundle.heroes.append(second)
    bundle.manifest.current_hero_id = "hero2"
    assert hero_of(bundle) is second


def test_hero_of_has_no_fallback_to_first_hero(registry):
    from ai_dm.game.scene import hero_of

    bundle = make_bundle(registry)
    bundle.manifest.current_hero_id = "nobody"
    with pytest.raises(KeyError):
        hero_of(bundle)


def test_hero_of_is_defined_once_and_heroes_0_is_not_used_in_game():
    import ast
    from pathlib import Path

    import ai_dm.game

    folder = Path(ai_dm.game.__file__).parent
    defs = []
    for path in sorted(folder.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        assert "heroes[0]" not in source, path.name
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.FunctionDef) and node.name == "hero_of":
                defs.append(path.name)
    assert defs == ["scene.py"]
