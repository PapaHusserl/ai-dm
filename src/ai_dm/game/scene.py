from ai_dm.rules.spellcasting import expire_concentration
from ai_dm.rules.time_ops import ensure_min_advance
from ai_dm.state.scene import SceneState
from ai_dm.state.session import ChapterState


def hero_of(bundle):
    for hero in bundle.heroes:
        if hero.id == bundle.manifest.current_hero_id:
            return hero
    raise KeyError(bundle.manifest.current_hero_id)


def scene_npc_ids(bundle) -> set[str]:
    # живые NPC в локации героя (тот же отбор, что scene_npcs в промпте)
    location_id = hero_of(bundle).location_id
    return {
        npc.id for npc in bundle.world.npcs.values()
        if npc.status == "alive" and npc.location_id == location_id
    }


def mood_carries(bundle, old, npcs_before) -> bool:
    # метка старой сцены переносится: она есть, локация та же, все NPC сцены на месте
    if old is None or not old.scene_mood or npcs_before is None:
        return False
    if old.location_id != hero_of(bundle).location_id:
        return False
    return npcs_before <= scene_npc_ids(bundle)


def start_scene(bundle, npcs_before=None) -> SceneState:
    # npcs_before -- NPC сцены до границы: метка scene_mood переносится, если локация та же
    # и все они на месте
    old = bundle.session.current_scene
    number = 1
    if old is not None:
        number = int(old.id.split("_")[1]) + 1
    location_id = hero_of(bundle).location_id
    scene = SceneState(
        id=f"scene_{number}", started_at_s=bundle.world.clock.now_s, location_id=location_id
    )
    if mood_carries(bundle, old, npcs_before):
        scene.scene_mood = old.scene_mood
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
    expire_concentration(hero_of(bundle), bundle.world)


def ensure_chapter(bundle) -> ChapterState:
    # сейв без главы (старые миры): открываем главу 1
    if bundle.session.current_chapter is None:
        scene = bundle.session.current_scene
        started_at_s = scene.started_at_s if scene is not None else bundle.world.clock.now_s
        bundle.session.current_chapter = ChapterState(
            id="ch_1", number=1, started_at_s=started_at_s, scene_count=1
        )
    return bundle.session.current_chapter
