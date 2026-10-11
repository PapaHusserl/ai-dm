# Ожидаемый API (П5 этапа 3): ход мира по дням на границе сцены (game.boundary.tick_days).
# Помощники -- world_kit.py. Смерть героя за кадром при тике -> TurnResult.hero_dead.
from world_kit import (
    ReactiveWorld,
    bundle_without_candidates,
    day_turn,
    make_world_rig,
    narrator_turns,
)


def play_day(registry, cfg, tmp_path, per_day):
    bundle = bundle_without_candidates(registry, cfg)
    bundle.world.mortality_per_day = per_day
    rig = make_world_rig(
        registry, cfg, tmp_path, narrator_turns(day_turn()), ReactiveWorld(),
        bundle=bundle
    )
    return rig, rig.play()[0]


def test_hero_dies_offscreen_on_tick_sets_hero_dead(registry, cfg, tmp_path):
    # 1/1 в день: бросок выпадает всегда
    rig, result = play_day(registry, cfg, tmp_path, 1)
    assert result.hero_dead is True
    assert rig.runner.bundle.heroes[0].status == "dead"
    assert rig.runner.bundle.heroes[0].death.cause == "chance"
    assert rig.runner.bundle.world.flags["hero_dead:hero"] is True


def test_calm_day_boundary_keeps_hero_alive(registry, cfg, tmp_path):
    rig, result = play_day(registry, cfg, tmp_path, 500000)
    assert result.hero_dead is False
    assert rig.runner.bundle.heroes[0].status == "active"


def test_tick_moves_last_day_to_current_day(registry, cfg, tmp_path):
    rig, _ = play_day(registry, cfg, tmp_path, 500000)
    world = rig.runner.bundle.world
    assert world.sim.last_day == world.clock.now_s // 86400
