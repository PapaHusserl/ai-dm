# После переговоров в бою (docs/plan-combat-parley.md, п. 6): combat_flow.settle_parley(bundle, cfg)
# зовётся до finish_combat(bundle, registry).
#   именованный NPC: сдался -- attitude +10, перешёл (метка parley_defected) -- +20, оскорблён
#   (parley_offended) -- -10; всё в пределах [attitude] per_scene (scene.attitude_spent);
#   безымянные участники (нет записи в world.npcs) не трогаются.
#   finish_combat: сдавшиеся и перебежчики дают опыт как побеждённые; метки переговоров
#   (parley.FLAG_IDS) с существ снимаются.
import game_kit  # noqa: F401  (путь к master_kit)
from master_kit import combat_ctx

from ai_dm.combat.actions.parley import FLAG_IDS
from ai_dm.config.settings import load_rules_config
from ai_dm.game.combat_flow import finish_combat, settle_parley
from ai_dm.rules.xp import combat_xp
from ai_dm.state.creature import ActiveEffect
from ai_dm.state.relations import NpcEvent, NpcSceneMemory
from ai_dm.state.scene import SceneState
from ai_dm.state.world import NPC


def fight(registry, cfg, outcome="victory", statuses=None, named=("g1",)):
    ctx = combat_ctx(registry, cfg)
    bundle = ctx.bundle
    state = bundle.session.active_combat
    state.outcome = outcome
    for ref, status in (statuses or {}).items():
        [p for p in state.participants if p.ref == ref][0].status = status
    for ref in named:
        bundle.world.npcs[ref] = NPC(id=ref, name=f"Гоблин {ref}", means=["бой"])
    return bundle


def flag(bundle, ref, flag_id):
    part = [p for p in bundle.session.active_combat.participants if p.ref == ref][0]
    part.creature.active_effects.append(ActiveEffect(id=flag_id, source="hero", kind="flag"))


def effect_ids(bundle, ref):
    part = [p for p in bundle.session.active_combat.participants if p.ref == ref][0]
    return [e.id for e in part.creature.active_effects]


def test_surrendered_npc_gets_plus_ten(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "surrendered"})
    settle_parley(bundle, cfg)
    assert bundle.world.npcs["g1"].attitude == 10


def test_surrendered_npc_stays_alive(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "surrendered"})
    settle_parley(bundle, cfg)
    finish_combat(bundle, registry)
    assert bundle.world.npcs["g1"].status == "alive"


def test_defected_npc_gets_plus_twenty(registry, cfg):
    bundle = fight(registry, cfg)
    flag(bundle, "g1", "parley_defected")
    settle_parley(bundle, cfg)
    assert bundle.world.npcs["g1"].attitude == 20


def test_offended_npc_gets_minus_ten(registry, cfg):
    bundle = fight(registry, cfg)
    flag(bundle, "g1", "parley_offended")
    settle_parley(bundle, cfg)
    assert bundle.world.npcs["g1"].attitude == -10


def test_npc_without_parley_result_keeps_attitude(registry, cfg):
    bundle = fight(registry, cfg)
    settle_parley(bundle, cfg)
    assert bundle.world.npcs["g1"].attitude == 0


def test_fled_npc_keeps_attitude(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "fled"})
    settle_parley(bundle, cfg)
    assert bundle.world.npcs["g1"].attitude == 0


def test_only_the_named_participant_changes(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "surrendered", "g2": "surrendered"})
    settle_parley(bundle, cfg)
    assert "g2" not in bundle.world.npcs


def test_attitude_is_capped_at_one_hundred(registry, cfg):
    bundle = fight(registry, cfg)
    bundle.world.npcs["g1"].attitude = 95
    flag(bundle, "g1", "parley_defected")
    settle_parley(bundle, cfg)
    assert bundle.world.npcs["g1"].attitude == 100


def test_attitude_gain_respects_the_scene_limit(registry):
    small = load_rules_config(toml_text="[attitude]\nper_scene = 15\n")
    bundle = fight(registry, small, statuses={"g1": "surrendered"})
    bundle.session.current_scene = SceneState.model_construct(attitude_spent={"g1": 10})
    settle_parley(bundle, small)
    assert bundle.world.npcs["g1"].attitude == 5
    assert bundle.session.current_scene.attitude_spent["g1"] == 15


def test_exhausted_scene_limit_blocks_the_change(registry):
    small = load_rules_config(toml_text="[attitude]\nper_scene = 15\n")
    bundle = fight(registry, small, statuses={"g1": "surrendered"})
    bundle.session.current_scene = SceneState.model_construct(attitude_spent={"g1": 15})
    settle_parley(bundle, small)
    assert bundle.world.npcs["g1"].attitude == 0


def test_surrendered_enemies_give_xp_like_defeated(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "surrendered", "g2": "surrendered"}, named=())
    finish_combat(bundle, registry)
    assert bundle.heroes[0].sheet.xp == combat_xp(["goblin_warrior", "goblin_warrior"], registry)


# Ж19: мораль группы даёт тем, кто сдался или ушёл следом, те же статусы, что у одиночной цели

def test_morale_surrendered_and_fled_enemies_are_all_defeated_for_loot(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "surrendered", "g2": "fled"}, named=())
    finish_combat(bundle, registry)
    assert bundle.session.last_combat.defeated == ["goblin_warrior", "goblin_warrior"]


def test_morale_surrendered_and_fled_enemies_give_xp(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "surrendered", "g2": "fled"}, named=())
    finish_combat(bundle, registry)
    assert bundle.heroes[0].sheet.xp == combat_xp(["goblin_warrior", "goblin_warrior"], registry)


def test_morale_followers_who_were_named_get_the_surrender_attitude(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "surrendered", "g2": "surrendered"},
                   named=("g1", "g2"))
    settle_parley(bundle, cfg)
    assert [bundle.world.npcs[r].attitude for r in ("g1", "g2")] == [10, 10]


def test_defector_gives_xp_like_defeated(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "dead"}, named=())
    part = [p for p in bundle.session.active_combat.participants if p.ref == "g2"][0]
    part.side = "heroes"
    flag(bundle, "g2", "parley_defected")
    finish_combat(bundle, registry)
    assert bundle.heroes[0].sheet.xp == combat_xp(["goblin_warrior", "goblin_warrior"], registry)


def test_defector_is_not_listed_as_defeated_for_loot(registry, cfg):
    # XP за перебежчика есть, а добычи с живого союзника нет
    bundle = fight(registry, cfg, statuses={"g1": "dead"}, named=())
    part = [p for p in bundle.session.active_combat.participants if p.ref == "g2"][0]
    part.side = "heroes"
    flag(bundle, "g2", "parley_defected")
    finish_combat(bundle, registry)
    assert bundle.session.last_combat.defeated == ["goblin_warrior"]


def test_ally_without_defect_flag_gives_no_xp(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "dead"}, named=())
    part = [p for p in bundle.session.active_combat.participants if p.ref == "g2"][0]
    part.side = "heroes"
    finish_combat(bundle, registry)
    assert bundle.heroes[0].sheet.xp == combat_xp(["goblin_warrior"], registry)


def test_parley_flags_are_removed_after_the_fight(registry, cfg):
    bundle = fight(registry, cfg, named=())
    state = bundle.session.active_combat
    for flag_id in FLAG_IDS:
        flag(bundle, "g1", flag_id)
    other = ActiveEffect(id="prone_marker", source="hero", kind="flag")
    [p for p in state.participants if p.ref == "g1"][0].creature.active_effects.append(other)
    creature = [p for p in state.participants if p.ref == "g1"][0].creature
    finish_combat(bundle, registry)
    assert [e.id for e in creature.active_effects] == ["prone_marker"]


def test_flags_of_a_named_npc_are_removed_too(registry, cfg):
    bundle = fight(registry, cfg)
    npc = bundle.world.npcs["g1"]
    part = [p for p in bundle.session.active_combat.participants if p.ref == "g1"][0]
    part.creature = None
    from ai_dm.state.creature import CreatureState

    npc.creature = CreatureState(hp_current=10, hp_max=10)
    npc.creature.active_effects.append(ActiveEffect(id="parley_tried", source="hero", kind="flag"))
    finish_combat(bundle, registry)
    assert npc.creature.active_effects == []


def test_settle_works_without_a_current_scene(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "surrendered"})
    bundle.session.current_scene = None
    settle_parley(bundle, cfg)
    assert bundle.world.npcs["g1"].attitude == 10


def test_attitude_is_floored_at_minus_one_hundred(registry, cfg):
    bundle = fight(registry, cfg)
    bundle.world.npcs["g1"].attitude = -95
    flag(bundle, "g1", "parley_offended")
    settle_parley(bundle, cfg)
    assert bundle.world.npcs["g1"].attitude == -100


def test_scene_limit_counts_the_applied_change_from_zero(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "surrendered"})
    bundle.world.npcs["g1"].attitude = 5
    bundle.session.current_scene = SceneState.model_construct(attitude_spent={})
    settle_parley(bundle, cfg)
    assert bundle.session.current_scene.attitude_spent == {"g1": 10}


# Ж0 подшаг 2 (п. 16): settle_parley обновляет вес памяти NPC за текущую сцену (refresh_weight)

def with_memory(bundle, weight=0):
    scene = SceneState(id="scene_9", started_at_s=900)
    bundle.session.current_scene = scene
    bundle.world.npcs["g1"].memory = [
        NpcSceneMemory(
            scene_id="scene_9", at_s=900, weight=weight,
            events=[NpcEvent(kind="threat", turn_seq=1, text="угрожал")],
        )
    ]
    return scene


def test_parley_refreshes_memory_weight_to_spent_attitude(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "surrendered"})
    with_memory(bundle)
    settle_parley(bundle, cfg)
    assert bundle.world.npcs["g1"].memory[0].weight == 10


def test_parley_defect_weight_is_twenty_capped_by_scene_limit(registry, cfg):
    bundle = fight(registry, cfg)
    with_memory(bundle)
    flag(bundle, "g1", "parley_defected")
    settle_parley(bundle, cfg)
    assert bundle.world.npcs["g1"].memory[0].weight == 20


def test_parley_offended_weight_is_absolute(registry, cfg):
    bundle = fight(registry, cfg)
    with_memory(bundle)
    flag(bundle, "g1", "parley_offended")
    settle_parley(bundle, cfg)
    assert bundle.world.npcs["g1"].memory[0].weight == 10


def test_parley_without_memory_for_scene_creates_none(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "surrendered"})
    bundle.session.current_scene = SceneState(id="scene_9", started_at_s=900)
    settle_parley(bundle, cfg)
    assert bundle.world.npcs["g1"].memory == []


def test_parley_keeps_memory_of_other_scenes(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "surrendered"})
    with_memory(bundle, weight=3)
    bundle.session.current_scene = SceneState(id="scene_10", started_at_s=1000)
    settle_parley(bundle, cfg)
    assert bundle.world.npcs["g1"].memory[0].weight == 3
