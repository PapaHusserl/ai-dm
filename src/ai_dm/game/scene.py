from ai_dm.rules.time_ops import ensure_min_advance
from ai_dm.state.scene import SceneState
from ai_dm.state.session import ChapterState


def hero_of(bundle):
    for hero in bundle.heroes:
        if hero.id == bundle.manifest.current_hero_id:
            return hero
    raise KeyError(bundle.manifest.current_hero_id)


def start_scene(bundle) -> SceneState:
    old = bundle.session.current_scene
    number = 1
    if old is not None:
        number = int(old.id.split("_")[1]) + 1
    location_id = hero_of(bundle).location_id
    scene = SceneState(
        id=f"scene_{number}", started_at_s=bundle.world.clock.now_s, location_id=location_id
    )
    bundle.session.current_scene = scene
    return scene


def check_close(bundle, cfg, *, time_before_s, combat_ended=False) -> str | None:
    # причина закрытия сцены по приоритету; бандл не меняет
    scene = bundle.session.current_scene
    if scene.closed_reason is not None:
        return scene.closed_reason
    checks = [
        ("location_changed", hero_of(bundle).location_id != scene.location_id),
        ("time_jump", bundle.world.clock.now_s - time_before_s > cfg.scene.max_time_jump_s),
        ("combat_ended", combat_ended),
        ("turn_limit", scene.player_turns > cfg.scene.max_player_turns),
    ]
    return next((reason for reason, hit in checks if hit), None)


def close_scene(bundle, reason, cfg) -> None:
    scene = bundle.session.current_scene
    scene.closed_reason = reason
    ensure_min_advance(bundle.world.clock, scene.started_at_s, cfg)


def ensure_chapter(bundle) -> ChapterState:
    # сейв без главы (старые миры): открываем главу 1
    if bundle.session.current_chapter is None:
        scene = bundle.session.current_scene
        started_at_s = scene.started_at_s if scene is not None else bundle.world.clock.now_s
        bundle.session.current_chapter = ChapterState(
            id="ch_1", number=1, started_at_s=started_at_s, scene_count=1
        )
    return bundle.session.current_chapter
