# Безымянные монстры и именованные NPC в одном бою (A2, ТЗ 4.1 и 5.3).
#   Безымянный монстр: Participant.creature + monster_id, в world.npcs его нет; несколько
#   участников могут иметь одинаковое name -- ошибок уникальности нет, мир боем не меняется.
#   Смерть безымянного -- monster_died {id, monster_id, by}, без флага в мире.
#   Именованный NPC (mon(..., named=True)): ref = id в world.npcs, Participant.creature None,
#   смерть -- mortality_guard.remove_creature (Goal): npc_died {id, cause, by} и флаг npc_dead:<id>.
#   Если у NPC нет своего creature, движок заводит его при start() из monster_id.
from combat_kit import ScriptedRng, creature, hp, make_engine, make_fighter, mon, part, set_hp

from ai_dm.core.rng import Rng


def three_goblins(registry, cfg, rng):
    return make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=rng, started=False,
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "hall"),
                  mon("goblin_3", "goblin_warrior", "balcony")],
    )


def test_three_goblins_with_one_name_start_without_errors(registry, cfg):
    engine = three_goblins(registry, cfg, Rng(5))
    assert {p.name for p in engine.state.participants if p.side == "enemies"} == {"Воин-гоблин"}
    engine.start()
    assert len(engine.state.initiative_order) == 4


def test_the_world_npcs_are_untouched_after_a_fight(registry, cfg):
    engine = three_goblins(registry, cfg, Rng(5))
    engine.start()
    engine.run_to_end()
    assert engine.world.npcs == {}
    assert [k for k in engine.world.flags if k.startswith("npc_dead:")] == []


def test_goblins_keep_separate_hit_points(registry, cfg):
    engine = three_goblins(registry, cfg, Rng(5))
    set_hp(engine, "goblin_1", 4)
    assert [hp(engine, ref) for ref in ("goblin_1", "goblin_2", "goblin_3")] == [4, 10, 10]


def mixed(registry, cfg, rng, started=True):
    return make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=rng, started=started,
        monsters=[mon("boss", "goblin_boss", "hall", named=True),
                  mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "hall")],
    )


def test_named_npc_keeps_its_state_in_the_world(registry, cfg):
    engine = mixed(registry, cfg, ScriptedRng())
    assert part(engine, "boss").creature is None
    assert creature(engine, "boss") is engine.world.npcs["boss"].creature
    assert part(engine, "goblin_1").creature is not None


def test_named_npc_death_is_npc_died_with_a_flag(registry, cfg):
    engine = mixed(registry, cfg, ScriptedRng(d20=[15], d8=[4]))
    set_hp(engine, "boss", 3)
    events = engine.perform("hero", "attack:longsword:boss")
    died = [e for e in events if e.type == "npc_died"]
    assert [e.data for e in died] == [{"id": "boss", "cause": "goal", "by": "hero"}]
    assert engine.world.flags["npc_dead:boss"] is True
    assert engine.world.npcs["boss"].status == "dead"
    assert engine.world.npcs["boss"].death.cause == "goal"


def test_anonymous_death_in_a_mixed_fight_is_monster_died_without_a_flag(registry, cfg):
    engine = mixed(registry, cfg, ScriptedRng(d20=[15], d8=[4]))
    set_hp(engine, "goblin_1", 3)
    events = engine.perform("hero", "attack:longsword:goblin_1")
    assert "monster_died" in [e.type for e in events]
    assert "npc_died" not in [e.type for e in events]
    assert "npc_dead:goblin_1" not in engine.world.flags
    assert "goblin_1" not in engine.world.npcs


def test_missing_npc_creature_is_created_at_start(registry, cfg):
    engine = mixed(registry, cfg, ScriptedRng(d20=[10, 10, 10, 10]), started=False)
    engine.world.npcs["boss"].creature = None
    engine.start()
    boss = engine.world.npcs["boss"].creature
    assert boss is not None
    assert boss.hp_max == 21
