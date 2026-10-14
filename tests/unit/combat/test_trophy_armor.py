# Партия К7к, п. 2: доспех и щит с тел (docs/K7K-PLAN.md, В6 а+в, В11).
#   settle_ground при победе собирает state.gear с тел dead/down (как в test_trophy_gear.py), но
#   теперь кроме оружия -- доспех и щит: по умолчанию из статблока (Monster.armor / shield),
#   equipment существа переопределяет:
#     * Participant.equipment (безымянный) или NPC.equipment (именованный), если не None --
#       полная правда об экипировке: Equipment(armor, shield, weapons); weapons минус выбитое;
#       пустое Equipment() -- с тела ничего;
#     * None -- по статблоку: armor / shield монстра и текущее оружие (после раздачи выбитого);
#   цена по ПО тела как у оружия (кожаный доспех и щит гоблина-воина -- junk, 100 cp), босс --
#   полная цена (кольчужная рубаха 5000, щит 1000), одинаковые вещи -- стеки;
#   В11: после победы именованному NPC (он бой переживает) ставится equipment = Equipment()
#   ("снято"), второй бой с ним доспех/щит/оружие не даёт; квестовые вещи -- как раньше;
#   безымянному участнику ничего не пишется; не победа (поражение, бегство) NPC не трогает.
from combat_kit import ScriptedRng, make_engine, make_fighter, mon, part
from test_trophy_gear import as_tuples, fight, hold, mark, won

from ai_dm.combat.end import settle_ground
from ai_dm.combat.engine import CombatEngine
from ai_dm.state.combat import GroundItem
from ai_dm.state.creature import Equipment


def gear_of(engine):
    settle_ground(engine)
    return engine.state.gear


def boss_fight(registry, cfg):
    engine = fight(registry, cfg, goblins=1, named=True)
    engine.world.npcs["goblin_1"].named = True
    engine.state.participants[1].monster_id = "goblin_boss"
    return engine


def guard_fight(registry, cfg, statuses="down"):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=ScriptedRng(),
        monsters=[mon("guard_1", "guard", "hall", named=True)],
    )
    won(engine, statuses)
    return engine


# рядовые враги

def test_two_goblins_give_stacks_of_junk_armor_and_shields(registry, cfg):
    engine = fight(registry, cfg, goblins=2)
    won(engine)
    assert as_tuples(gear_of(engine)) == [
        ("leather_armor", 2, 100, "junk"), ("scimitar", 2, 250, "junk"),
        ("shield", 2, 100, "junk"), ("shortbow", 2, 250, "junk"),
    ]


def test_armor_trophy_is_below_srd_price(registry, cfg):
    engine = fight(registry, cfg, goblins=1)
    won(engine)
    armor = [e for e in gear_of(engine) if e.item_id == "leather_armor"][0]
    assert armor.cost_cp < registry.get("armor", "leather_armor").cost_cp


def test_downed_goblin_gives_armor_too(registry, cfg):
    engine = fight(registry, cfg, goblins=1)
    won(engine, "down")
    assert {e.item_id for e in gear_of(engine)} == {
        "scimitar", "shortbow", "leather_armor", "shield",
    }


def test_fled_goblin_gives_no_armor(registry, cfg):
    engine = fight(registry, cfg, goblins=1)
    won(engine, "fled")
    assert gear_of(engine) == []


def test_surrendered_goblin_gives_no_armor(registry, cfg):
    engine = fight(registry, cfg, goblins=1)
    won(engine, "surrendered")
    assert gear_of(engine) == []


def test_defector_gives_no_armor(registry, cfg):
    engine = fight(registry, cfg, goblins=2)
    won(engine)
    mark(engine, "goblin_1", "parley_defected")
    assert as_tuples([e for e in gear_of(engine) if e.item_id == "shield"]) == [
        ("shield", 1, 100, "junk")
    ]


def test_ally_gives_no_armor(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=ScriptedRng(),
        monsters=[mon("goblin_1", "goblin_warrior", "hall", side="heroes", group="allies")],
    )
    part(engine, "goblin_1").status = "dead"
    engine.state.outcome = "victory"
    assert gear_of(engine) == []


# выбитое оружие

def test_disarmed_weapon_is_not_duplicated_but_armor_is_there(registry, cfg):
    engine = fight(registry, cfg, goblins=1)
    won(engine)
    mark(engine, "goblin_1", "disarmed", weapon_id="scimitar")
    assert as_tuples(gear_of(engine)) == [
        ("leather_armor", 1, 100, "junk"), ("shield", 1, 100, "junk"),
        ("shortbow", 1, 250, "junk"),
    ]


def test_old_disarmed_flag_leaves_armor_and_no_weapons(registry, cfg):
    engine = fight(registry, cfg, goblins=1)
    won(engine)
    mark(engine, "goblin_1", "disarmed")
    assert as_tuples(gear_of(engine)) == [
        ("leather_armor", 1, 100, "junk"), ("shield", 1, 100, "junk"),
    ]


# боссы

def test_boss_gives_chain_shirt_and_shield_at_full_price(registry, cfg):
    engine = boss_fight(registry, cfg)
    won(engine)
    gear = [e for e in gear_of(engine) if e.item_id in ("chain_shirt", "shield")]
    assert as_tuples(gear) == [("chain_shirt", 1, 5000, None), ("shield", 1, 1000, None)]


def test_boss_also_gives_his_weapons(registry, cfg):
    engine = boss_fight(registry, cfg)
    won(engine)
    assert {e.item_id for e in gear_of(engine)} == {
        "scimitar", "shortbow", "chain_shirt", "shield",
    }


def test_guard_gives_chain_shirt_and_shield(registry, cfg):
    engine = guard_fight(registry, cfg)
    assert {e.item_id for e in gear_of(engine)} == {"spear", "chain_shirt", "shield"}


def test_named_non_boss_guard_gives_armor_by_cr_band(registry, cfg):
    # ПО 1/8 -- junk: 5000 * 10 % = 500
    engine = guard_fight(registry, cfg)
    shirt = [e for e in gear_of(engine) if e.item_id == "chain_shirt"][0]
    assert (shirt.cost_cp, shirt.quality) == (500, "junk")


# equipment переопределяет статблок

def test_participant_equipment_overrides_the_statblock(registry, cfg):
    engine = fight(registry, cfg, goblins=1)
    part(engine, "goblin_1").equipment = Equipment(
        armor=None, shield="shield", weapons=["scimitar"]
    )
    won(engine)
    assert as_tuples(gear_of(engine)) == [
        ("scimitar", 1, 250, "junk"), ("shield", 1, 100, "junk"),
    ]


def test_participant_equipment_may_hold_another_armor(registry, cfg):
    engine = fight(registry, cfg, goblins=1)
    part(engine, "goblin_1").equipment = Equipment(armor="chain_mail")
    won(engine)
    assert as_tuples(gear_of(engine)) == [("chain_mail", 1, 750, "junk")]


def test_empty_participant_equipment_gives_nothing(registry, cfg):
    engine = fight(registry, cfg, goblins=1)
    part(engine, "goblin_1").equipment = Equipment()
    won(engine)
    assert gear_of(engine) == []


def test_equipment_weapons_minus_disarmed(registry, cfg):
    engine = fight(registry, cfg, goblins=1)
    part(engine, "goblin_1").equipment = Equipment(
        armor="leather_armor", weapons=["scimitar", "shortbow"]
    )
    won(engine)
    mark(engine, "goblin_1", "disarmed", weapon_id="scimitar")
    assert [e.item_id for e in gear_of(engine)] == ["shortbow", "leather_armor"]


def test_equipment_with_old_disarmed_flag_keeps_armor_only(registry, cfg):
    engine = fight(registry, cfg, goblins=1)
    part(engine, "goblin_1").equipment = Equipment(
        armor="leather_armor", weapons=["scimitar", "shortbow"]
    )
    won(engine)
    mark(engine, "goblin_1", "disarmed")
    assert [e.item_id for e in gear_of(engine)] == ["leather_armor"]


def test_npc_equipment_overrides_the_statblock(registry, cfg):
    engine = guard_fight(registry, cfg)
    engine.world.npcs["guard_1"].equipment = Equipment(armor="leather_armor", weapons=[])
    assert [e.item_id for e in gear_of(engine)] == ["leather_armor"]


def test_participant_equipment_wins_over_npc_equipment(registry, cfg):
    engine = guard_fight(registry, cfg)
    engine.world.npcs["guard_1"].equipment = Equipment(armor="leather_armor")
    part(engine, "guard_1").equipment = Equipment(shield="shield")
    assert [e.item_id for e in gear_of(engine)] == ["shield"]


# В11: «снято» у именованного NPC

def test_named_npc_after_victory_is_marked_stripped(registry, cfg):
    engine = guard_fight(registry, cfg)
    settle_ground(engine)
    assert engine.world.npcs["guard_1"].equipment == Equipment()


def test_dead_named_npc_is_marked_stripped_too(registry, cfg):
    engine = guard_fight(registry, cfg, "dead")
    settle_ground(engine)
    assert engine.world.npcs["guard_1"].equipment == Equipment()


def test_anonymous_goblins_get_no_equipment_written(registry, cfg):
    engine = fight(registry, cfg, goblins=2)
    won(engine)
    settle_ground(engine)
    assert [p.equipment for p in engine.state.participants] == [None, None, None]


def test_second_fight_with_the_same_npc_gives_no_gear(registry, cfg):
    first = guard_fight(registry, cfg)
    assert gear_of(first)
    second = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=ScriptedRng(),
        monsters=[mon("guard_1", "guard", "hall", named=True)],
    )
    second.world = first.world
    won(second, "down")
    assert gear_of(second) == []


def test_second_fight_keeps_quest_items_of_the_npc(registry, cfg):
    first = guard_fight(registry, cfg)
    settle_ground(first)
    second = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=ScriptedRng(),
        monsters=[mon("guard_1", "guard", "hall", named=True)],
    )
    second.world = first.world
    hold(second, "custom_1", "npc", "guard_1")
    won(second, "down")
    assert [e.item_id for e in gear_of(second)] == ["custom_1"]


def test_stripped_npc_equipment_stays_empty_after_the_second_fight(registry, cfg):
    first = guard_fight(registry, cfg)
    settle_ground(first)
    second = CombatEngine(
        first.state, first.world, first.heroes, registry, cfg, ScriptedRng()
    )
    won(second, "down")
    settle_ground(second)
    assert second.world.npcs["guard_1"].equipment == Equipment()


def test_fled_named_npc_is_not_marked(registry, cfg):
    engine = guard_fight(registry, cfg, "fled")
    settle_ground(engine)
    assert engine.world.npcs["guard_1"].equipment is None


def test_surrendered_named_npc_is_not_marked(registry, cfg):
    engine = guard_fight(registry, cfg, "surrendered")
    settle_ground(engine)
    assert engine.world.npcs["guard_1"].equipment is None


def test_defector_named_npc_is_not_marked(registry, cfg):
    engine = guard_fight(registry, cfg)
    mark(engine, "guard_1", "parley_defected")
    settle_ground(engine)
    assert engine.world.npcs["guard_1"].equipment is None


def test_standing_named_npc_is_not_marked(registry, cfg):
    engine = guard_fight(registry, cfg, "active")
    engine.state.outcome = "ended_by_master"
    settle_ground(engine)
    assert engine.world.npcs["guard_1"].equipment is None


def test_ended_by_master_marks_the_fallen_npc(registry, cfg):
    engine = guard_fight(registry, cfg)
    engine.state.outcome = "ended_by_master"
    settle_ground(engine)
    assert engine.world.npcs["guard_1"].equipment == Equipment()


# не победа

def test_defeat_gives_no_armor_and_does_not_touch_the_npc(registry, cfg):
    engine = guard_fight(registry, cfg)
    engine.state.outcome = "defeat_pending"
    assert gear_of(engine) == []
    assert engine.world.npcs["guard_1"].equipment is None


def test_hero_fled_gives_no_armor_and_does_not_touch_the_npc(registry, cfg):
    engine = guard_fight(registry, cfg)
    engine.state.outcome = "fled"
    assert gear_of(engine) == []
    assert engine.world.npcs["guard_1"].equipment is None


def test_dead_hero_gives_no_armor_and_does_not_touch_the_npc(registry, cfg):
    engine = guard_fight(registry, cfg)
    engine.heroes["hero"].status = "dead"
    assert gear_of(engine) == []
    assert engine.world.npcs["guard_1"].equipment is None


# body_equipment / body_refs / mark_looted напрямую (body_equipment получает weapon_ids из disarm)

def test_body_equipment_from_the_statblock(registry, cfg):
    from ai_dm.combat import disarm
    from ai_dm.combat.trophies import body_equipment

    engine = fight(registry, cfg, goblins=1)
    worn = body_equipment(engine, "goblin_1", disarm.weapon_ids)
    assert (worn.armor, worn.shield) == ("leather_armor", "shield")
    assert sorted(worn.weapons) == ["scimitar", "shortbow"]


def test_body_equipment_statblock_weapons_exclude_the_disarmed(registry, cfg):
    from ai_dm.combat import disarm
    from ai_dm.combat.trophies import body_equipment

    engine = fight(registry, cfg, goblins=1)
    mark(engine, "goblin_1", "disarmed", weapon_id="scimitar")
    assert body_equipment(engine, "goblin_1", disarm.weapon_ids).weapons == ["shortbow"]


def test_body_equipment_of_set_equipment_is_that_equipment(registry, cfg):
    from ai_dm.combat import disarm
    from ai_dm.combat.trophies import body_equipment

    engine = fight(registry, cfg, goblins=1)
    part(engine, "goblin_1").equipment = Equipment(shield="shield", weapons=["scimitar"])
    assert body_equipment(engine, "goblin_1", disarm.weapon_ids) == Equipment(
        shield="shield", weapons=["scimitar"]
    )


def test_body_refs_are_dead_and_down_without_defectors(registry, cfg):
    from ai_dm.combat.trophies import body_refs

    engine = fight(registry, cfg, goblins=4)
    won(engine)
    part(engine, "goblin_2").status = "down"
    part(engine, "goblin_3").status = "fled"
    mark(engine, "goblin_4", "parley_defected")
    assert body_refs(engine) == ["goblin_1", "goblin_2"]


def test_mark_looted_strips_only_named_bodies(registry, cfg):
    from ai_dm.combat.trophies import mark_looted

    engine = guard_fight(registry, cfg)
    mark_looted(engine)
    assert engine.world.npcs["guard_1"].equipment == Equipment()


# --- К7х: body_equipment читает engine.equipment (копия участника, иначе NPC) ---

def test_gear_comes_from_the_participant_copy_of_an_unnamed_goblin(registry, cfg):
    engine = fight(registry, cfg, goblins=1)
    part(engine, "goblin_1").equipment = Equipment(armor="chain_mail", shield=None, weapons=[])
    won(engine)
    assert {e.item_id for e in gear_of(engine)} == {"chain_mail"}


def test_participant_copy_wins_over_the_npc_record(registry, cfg):
    engine = fight(registry, cfg, goblins=1, named=True)
    engine.world.npcs["goblin_1"].equipment = Equipment(armor="leather_armor")
    part(engine, "goblin_1").equipment = Equipment(shield="shield")
    won(engine)
    assert {e.item_id for e in gear_of(engine)} == {"shield"}


def test_picked_up_weapon_in_the_copy_goes_to_the_trophies(registry, cfg):
    engine = fight(registry, cfg, goblins=1)
    part(engine, "goblin_1").equipment = Equipment(weapons=["shortbow"])
    engine.state.ground_items.append(
        GroundItem(item_id="scimitar", zone_id="hall", owner_ref="goblin_1", cost_cp=0)
    )
    engine.perform("goblin_1", "pickup:0")
    won(engine)
    assert {e.item_id for e in gear_of(engine)} == {"shortbow", "scimitar"}
