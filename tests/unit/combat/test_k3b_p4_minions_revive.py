# К3б П4 (docs/plan-k3b.md, «Тесты» П4; решения 1-3, 9): призванные существа и Воскрешение в бою.
#   Призванные (HeroState.minions: list[Minion(monster_id, spell_id, hp_current, until_s)],
#   combat/minions.py): participants(hero, registry, zone_id) -- участники side="heroes",
#     group_id="party", controller="engine", ref «minion:<n>:<monster_id>», creature с HP из
#     Minion.hp_current, у ястреба (фамильяр, find_familiar) -- эффект kind="familiar"; фамильяр без
#     пунктов атаки и выбирает «Помочь» (EngineTactics), скелет бьёт ближайшего врага;
#     after_combat(engine) -- вызывается из end.conclude: HP назад в Minion, убитые и истёкшие
#     (until_s <= now после сдвига часов) -- вон из hero.minions.
#   Воскрешение (решение 1, 2): в бою «cast:revivify:3:<ref>» -- цель: убитый именованный NPC
#     (ref в world.npcs), не позже 10 раундов от смерти (kill_monster пишет death.at_s = часы +
#     rounds_to_seconds(раунд смерти)); цель встаёт active с 1 HP, death = None, ячейка и действие
#     тратятся, в логе строка с именем цели.
import re

from combat_kit import (
    ScriptedRng,
    creature,
    make_engine,
    make_wizard,
    mon,
    option_ids,
    part,
    turn,
)
from test_summons_aura import priest

from ai_dm.combat import downed, end
from ai_dm.combat.controllers import EngineTactics
from ai_dm.rules.time_ops import rounds_to_seconds
from ai_dm.state.hero import Minion

REVIVE = "revivify"
NPC_GOBLIN = [
    mon("npc_1", "goblin_warrior", "hall", named=True),
    mon("goblin_1", "goblin_warrior", "balcony"),
]


def skeleton(hp=13, until_s=None):
    return Minion(monster_id="skeleton", spell_id="animate_dead", hp_current=hp, until_s=until_s)


def zombie(hp=15):
    return Minion(monster_id="zombie", spell_id="animate_dead", hp_current=hp, until_s=None)


def hawk():
    return Minion(monster_id="hawk", spell_id="find_familiar", hp_current=1, until_s=None)


def minion_fight(registry, cfg, *minion_list, zone="hall"):
    from ai_dm.combat import minions

    hero = make_wizard(registry)
    hero.minions = list(minion_list)
    engine = make_engine(
        registry, cfg, heroes=[hero], monsters=[mon("goblin_1", "goblin_warrior", "hall")],
        rng=ScriptedRng(),
    )
    new = minions.participants(hero, registry, zone)
    for i, p in enumerate(new):
        p.initiative = 50 - i
        engine.state.participants.append(p)
        engine.state.initiative_order.append(p.ref)
    return engine, hero, new


# призванные: участники боя

def test_minion_participant_is_one_per_minion(registry, cfg):
    _, _, new = minion_fight(registry, cfg, skeleton(), zombie())
    assert len(new) == 2


def test_minion_participant_stands_with_the_heroes(registry, cfg):
    _, _, (p,) = minion_fight(registry, cfg, skeleton())
    assert (p.side, p.group_id) == ("heroes", "party")


def test_minion_participant_is_driven_by_the_engine(registry, cfg):
    _, _, (p,) = minion_fight(registry, cfg, skeleton())
    assert p.controller == "engine"


def test_minion_participant_knows_its_monster(registry, cfg):
    _, _, (p,) = minion_fight(registry, cfg, skeleton())
    assert p.monster_id == "skeleton"


def test_minion_participant_stands_in_the_given_zone(registry, cfg):
    _, _, (p,) = minion_fight(registry, cfg, skeleton(), zone="balcony")
    assert p.zone_id == "balcony"


def test_minion_ref_has_index_and_monster_id(registry, cfg):
    _, _, (p,) = minion_fight(registry, cfg, skeleton())
    assert re.fullmatch(r"minion:\d+:skeleton", p.ref)


def test_minion_refs_are_unique(registry, cfg):
    _, _, new = minion_fight(registry, cfg, skeleton(), skeleton())
    assert new[0].ref != new[1].ref


def test_minion_participant_has_a_display_name(registry, cfg):
    _, _, (p,) = minion_fight(registry, cfg, skeleton())
    assert p.name != ""


def test_minion_participant_carries_its_saved_hp(registry, cfg):
    _, _, (p,) = minion_fight(registry, cfg, skeleton(hp=6))
    assert p.creature.hp_current == 6


def test_minion_participant_hp_max_is_the_monsters(registry, cfg):
    _, _, (p,) = minion_fight(registry, cfg, skeleton(hp=6))
    assert p.creature.hp_max == 13


def test_skeleton_is_not_a_familiar(registry, cfg):
    _, _, (p,) = minion_fight(registry, cfg, skeleton())
    assert [e for e in p.creature.active_effects if e.kind == "familiar"] == []


def test_hawk_carries_the_familiar_flag(registry, cfg):
    _, _, (p,) = minion_fight(registry, cfg, hawk())
    assert [e.id for e in p.creature.active_effects if e.kind == "familiar"] == ["find_familiar"]


def test_minion_takes_a_turn_in_the_order(registry, cfg):
    engine, _, (p,) = minion_fight(registry, cfg, skeleton())
    assert p.ref in engine.state.initiative_order


# призванные: поведение

def kinds(engine, ref):
    return [o.kind for o in engine.available_actions(ref)]


def test_skeleton_has_attack_options(registry, cfg):
    engine, _, (p,) = minion_fight(registry, cfg, skeleton())
    assert "attack" in kinds(engine, p.ref)


def test_skeleton_chooses_to_attack_the_nearest_enemy(registry, cfg):
    engine, _, (p,) = minion_fight(registry, cfg, skeleton())
    choice = EngineTactics(engine).choose_turn(engine.available_actions(p.ref), p.ref)
    assert choice.startswith("attack:") and choice.endswith(":goblin_1")


def test_familiar_has_no_attack_options(registry, cfg):
    engine, _, (p,) = minion_fight(registry, cfg, hawk())
    assert "attack" not in kinds(engine, p.ref)


def test_familiar_chooses_help(registry, cfg):
    engine, hero, (p,) = minion_fight(registry, cfg, hawk())
    choice = EngineTactics(engine).choose_turn(engine.available_actions(p.ref), p.ref)
    assert choice == f"help:{hero.id}:goblin_1"


# после боя

def test_conclude_returns_hp_to_the_minion(registry, cfg):
    engine, hero, (p,) = minion_fight(registry, cfg, skeleton())
    p.creature.hp_current = 5
    end.conclude(engine)
    assert hero.minions[0].hp_current == 5


def test_conclude_maps_hp_to_the_right_minion(registry, cfg):
    engine, hero, new = minion_fight(registry, cfg, skeleton(), zombie())
    new[1].creature.hp_current = 4
    end.conclude(engine)
    assert [m.hp_current for m in hero.minions] == [13, 4]


def test_conclude_drops_a_killed_minion(registry, cfg):
    engine, hero, (p,) = minion_fight(registry, cfg, skeleton())
    p.status = "dead"
    p.creature.hp_current = 0
    end.conclude(engine)
    assert hero.minions == []


def test_conclude_keeps_the_survivor_when_another_died(registry, cfg):
    engine, hero, new = minion_fight(registry, cfg, skeleton(), zombie())
    new[0].status = "dead"
    new[0].creature.hp_current = 0
    end.conclude(engine)
    assert [m.monster_id for m in hero.minions] == ["zombie"]


def test_conclude_drops_a_minion_whose_time_ran_out_during_the_fight(registry, cfg):
    engine, hero, _ = minion_fight(registry, cfg, skeleton())
    now = engine.world.clock.now_s
    hero.minions[0].until_s = now + 1
    end.conclude(engine)
    assert hero.minions == []


def test_conclude_keeps_a_minion_with_time_left(registry, cfg):
    engine, hero, _ = minion_fight(registry, cfg, skeleton())
    now = engine.world.clock.now_s
    hero.minions[0].until_s = now + 86400
    end.conclude(engine)
    assert len(hero.minions) == 1


def test_conclude_keeps_an_unlimited_familiar(registry, cfg):
    engine, hero, _ = minion_fight(registry, cfg, hawk())
    end.conclude(engine)
    assert [m.monster_id for m in hero.minions] == ["hawk"]


def test_conclude_drops_a_minion_marked_dead_even_with_hp_left(registry, cfg):
    engine, hero, (p,) = minion_fight(registry, cfg, skeleton())
    p.status = "dead"
    p.creature.hp_current = 5
    end.conclude(engine)
    assert hero.minions == []


def test_conclude_drops_a_minion_at_zero_hp_even_if_active(registry, cfg):
    engine, hero, (p,) = minion_fight(registry, cfg, skeleton())
    p.creature.hp_current = 0
    end.conclude(engine)
    assert hero.minions == []


def test_conclude_keeps_a_minion_that_had_no_participant(registry, cfg):
    engine, hero, new = minion_fight(registry, cfg, skeleton(hp=7))
    engine.state.participants = [q for q in engine.state.participants if q not in new]
    end.conclude(engine)
    assert [m.hp_current for m in hero.minions] == [7]


def test_participants_skip_an_expired_minion_but_take_the_next(registry, cfg):
    from ai_dm.combat import minions

    hero = make_wizard(registry)
    hero.minions = [skeleton(until_s=100), hawk()]
    found = minions.participants(hero, registry, "hall", now_s=200)
    assert [p.monster_id for p in found] == ["hawk"]


# Воскрешение в бою

def revive_engine(registry, cfg, monsters=NPC_GOBLIN, death_round=2, now_round=5):
    engine = make_engine(
        registry, cfg, heroes=[priest(registry, REVIVE)], monsters=monsters, rng=ScriptedRng(),
    )
    engine.state.round = death_round
    downed.kill_monster(engine, monsters[0]["ref"], "cler")
    engine.state.round = now_round
    engine.start_turn("cler")
    return engine


def revive_id(ref="npc_1"):
    return f"cast:{REVIVE}:3:{ref}"


def test_kill_records_the_death_time_at_the_projected_second(registry, cfg):
    engine = revive_engine(registry, cfg)
    assert engine.world.npcs["npc_1"].death.at_s == rounds_to_seconds(2, cfg)


def test_revive_is_offered_for_a_dead_npc_three_rounds_after_death(registry, cfg):
    engine = revive_engine(registry, cfg, now_round=5)
    assert revive_id() in option_ids(engine, "cler")


def test_revive_is_offered_at_the_ten_round_limit(registry, cfg):
    engine = revive_engine(registry, cfg, now_round=12)
    assert revive_id() in option_ids(engine, "cler")


def test_revive_is_not_offered_eleven_rounds_after_death(registry, cfg):
    engine = revive_engine(registry, cfg, now_round=13)
    assert revive_id() not in option_ids(engine, "cler")


def test_revive_is_not_offered_for_an_unnamed_dead_monster(registry, cfg):
    monsters = [
        mon("goblin_1", "goblin_warrior", "hall"), mon("goblin_2", "goblin_warrior", "balcony"),
    ]
    engine = revive_engine(registry, cfg, monsters=monsters)
    assert revive_id("goblin_1") not in option_ids(engine, "cler")


def test_revive_is_not_offered_for_a_living_npc(registry, cfg):
    monsters = [
        mon("npc_1", "goblin_warrior", "hall", named=True),
        mon("npc_2", "goblin_warrior", "hall", named=True),
        mon("goblin_1", "goblin_warrior", "balcony"),
    ]
    engine = revive_engine(registry, cfg, monsters=monsters)
    assert revive_id("npc_2") not in option_ids(engine, "cler")


def test_revive_makes_the_participant_active(registry, cfg):
    engine = revive_engine(registry, cfg)
    engine.perform("cler", revive_id())
    assert part(engine, "npc_1").status == "active"


def test_revive_leaves_one_hit_point(registry, cfg):
    engine = revive_engine(registry, cfg)
    engine.perform("cler", revive_id())
    assert creature(engine, "npc_1").hp_current == 1


def test_revive_makes_the_world_npc_alive(registry, cfg):
    engine = revive_engine(registry, cfg)
    engine.perform("cler", revive_id())
    assert engine.world.npcs["npc_1"].status == "alive"


def test_revive_clears_the_death_record(registry, cfg):
    engine = revive_engine(registry, cfg)
    engine.perform("cler", revive_id())
    assert engine.world.npcs["npc_1"].death is None


def test_revive_spends_a_third_circle_slot(registry, cfg):
    engine = revive_engine(registry, cfg)
    engine.perform("cler", revive_id())
    assert engine.heroes["cler"].creature.resources["spell_slot:3"].current == 1


def test_revive_spends_the_action(registry, cfg):
    engine = revive_engine(registry, cfg)
    engine.perform("cler", revive_id())
    assert turn(engine, "cler").action is False


def test_revive_writes_a_log_line_with_the_name(registry, cfg):
    engine = revive_engine(registry, cfg)
    before = len(engine.state.log)
    engine.perform("cler", revive_id())
    name = engine.name("npc_1")
    assert any(name in line for line in engine.state.log[before:])


def test_revived_npc_keeps_its_place_in_the_initiative(registry, cfg):
    engine = revive_engine(registry, cfg)
    engine.perform("cler", revive_id())
    assert "npc_1" in engine.state.initiative_order


def test_revive_log_line_has_spell_name_and_hp(registry, cfg):
    engine = revive_engine(registry, cfg)
    engine.perform("cler", revive_id())
    expected = f"Оживление: {engine.name('npc_1')} жив, 1 HP"
    assert expected in [line.strip() for line in engine.state.log]


# решение 37: воскрешённый -- чистый лист; решение 38: флага npc_dead нет

def stain(engine):
    from ai_dm.state.creature import ActiveEffect, AppliedCondition

    c = creature(engine, "npc_1")
    c.conditions += [
        AppliedCondition(id="unconscious", source="0_hp"), AppliedCondition(id="poisoned"),
    ]
    c.active_effects.append(ActiveEffect(id="bless", source="x", kind="spell", params={}))


def test_revived_participant_has_no_conditions(registry, cfg):
    engine = revive_engine(registry, cfg)
    stain(engine)
    engine.perform("cler", revive_id())
    assert creature(engine, "npc_1").conditions == []


def test_revived_participant_has_no_effects(registry, cfg):
    engine = revive_engine(registry, cfg)
    stain(engine)
    engine.perform("cler", revive_id())
    assert creature(engine, "npc_1").active_effects == []


def test_revived_participant_keeps_one_hit_point_after_cleaning(registry, cfg):
    engine = revive_engine(registry, cfg)
    stain(engine)
    engine.perform("cler", revive_id())
    assert creature(engine, "npc_1").hp_current == 1


def test_revive_removes_the_npc_dead_flag(registry, cfg):
    engine = revive_engine(registry, cfg)
    engine.world.flags["npc_dead:npc_1"] = True
    engine.perform("cler", revive_id())
    assert "npc_dead:npc_1" not in engine.world.flags


def test_revive_keeps_other_dead_flags(registry, cfg):
    engine = revive_engine(registry, cfg)
    engine.world.flags["npc_dead:npc_1"] = True
    engine.world.flags["npc_dead:other"] = True
    engine.perform("cler", revive_id())
    assert engine.world.flags.get("npc_dead:other") is True


def test_death_sets_the_flag_through_finish(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[priest(registry, REVIVE)], monsters=NPC_GOBLIN, rng=ScriptedRng(),
    )
    engine.finish(downed.kill_monster(engine, "npc_1", "cler"))
    assert engine.world.flags.get("npc_dead:npc_1") is True


# оба призыва подготовлены -- в бою пунктов нет и исключения нет

def test_conjure_spells_are_absent_from_the_combat_menu(registry, cfg):
    from test_cast_p3a import engine_of, mage

    hero = mage(registry, "animate_dead", "find_familiar")
    engine = engine_of(registry, cfg, hero)
    ids = option_ids(engine, "wiz")
    assert not [i for i in ids if i.startswith(("cast:animate_dead", "cast:find_familiar"))]
