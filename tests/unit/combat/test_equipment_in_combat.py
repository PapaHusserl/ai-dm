# Партия К7х, п. 5: снаряжение монстра в бою (docs/K7X-PLAN.md, В9, В10).
#   engine.start(): если у участника equipment None, а у NPC задан -- участнику копия (model_copy
#     deep);
#     свой equipment участника не затирается; безымянному и NPC без equipment ничего не пишется.
#   CombatEngine.equipment(ref) -> Equipment | None: equipment участника, иначе NPC.equipment,
#     иначе None.
#   КД монстра (monster_armor_class): ac статблока + gear_ac(надето) - gear_ac(доспех и щит
#     статблока);
#     gear_ac(доспех, щит, Лов) = (доспех.ac + Лов до dex_cap | 10 + Лов) + щит.ac;
#     equipment None -- ac статблока (регресс); pierce и эффекты kind="ac" считаются поверх.
#     Гоблин (Лов +2, ac 15 = кожаный 11 + 2 + щит 2): Equipment() -> 12; без доспеха, со щитом ->
#       14;
#     кожаный без щита -> 13; кольчуга (dex_cap 0) без щита -> 16; кольчуга со щитом -> 18.
#   Оружие: lost_weapons к флагам disarmed добавляет оружие действий монстра, которого нет в
#     equipment.weapons (equipment задан); порядок без повторов; героя и equipment None не касается.
#     Через это: attacks_of (нет оружия -- безоружный удар у fey), disarm.weapon_ids, мультиатака,
#     can_pick, body_equipment.
#   disarm.pickup монстра: оружие потеряно по equipment (флага disarmed нет) -- добавляется в
#     equipment.weapons участника.
from combat_kit import (
    ScriptedRng,
    creature,
    make_engine,
    make_fighter,
    mon,
    option_ids,
    part,
)

from ai_dm.combat import disarm, trophies
from ai_dm.combat.actions.attack import attacks_of, lost_weapons
from ai_dm.content.models.monsters import Monster
from ai_dm.state.combat import GroundItem
from ai_dm.state.creature import ActiveEffect, Equipment, Expiry


def odd_registry(registry, **fields):
    data = registry.get("monster", "goblin_warrior").model_dump()
    data.update(fields)
    data["id"] = "odd_goblin"
    return registry.with_items({"monster": [Monster.model_validate(data)]})


def duel(registry, cfg, rng=None, monster="goblin_warrior", worn=None, reg=None, **kwargs):
    engine = make_engine(
        reg or registry, cfg, heroes=[make_fighter(registry)], rng=rng,
        monsters=[mon("goblin_1", monster, "hall")], **kwargs,
    )
    part(engine, "goblin_1").equipment = worn
    return engine


def named(registry, cfg, rng=None, worn=None, started=True):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", "hall", named=True)], started=started,
    )
    engine.world.npcs["goblin_1"].equipment = worn
    return engine


def ac(engine, **kwargs):
    return engine.armor_class("goblin_1", **kwargs)


def attack_ids(engine, ref="goblin_1"):
    return [o.id for o in engine.available_actions(ref) if o.kind == "attack"]


# --- перенос при старте ---

def test_start_copies_the_npc_equipment_to_the_participant(registry, cfg):
    engine = named(registry, cfg, ScriptedRng(d20=[10, 10]), Equipment(), started=False)
    engine.start()
    assert part(engine, "goblin_1").equipment == Equipment()


def test_start_copy_is_not_the_same_object(registry, cfg):
    worn = Equipment(armor="chain_mail", weapons=["scimitar"])
    engine = named(registry, cfg, ScriptedRng(d20=[10, 10]), worn, started=False)
    engine.start()
    assert part(engine, "goblin_1").equipment == worn
    assert part(engine, "goblin_1").equipment is not worn
    assert part(engine, "goblin_1").equipment is not engine.world.npcs["goblin_1"].equipment


def test_changing_the_copy_leaves_the_npc_alone(registry, cfg):
    engine = named(registry, cfg, ScriptedRng(d20=[10, 10]), Equipment(weapons=["scimitar"]),
                   started=False)
    engine.start()
    part(engine, "goblin_1").equipment.weapons.append("shortbow")
    assert engine.world.npcs["goblin_1"].equipment.weapons == ["scimitar"]


def test_start_keeps_the_own_equipment_of_the_participant(registry, cfg):
    engine = named(registry, cfg, ScriptedRng(d20=[10, 10]), Equipment(armor="chain_mail"),
                   started=False)
    part(engine, "goblin_1").equipment = Equipment(armor="leather_armor")
    engine.start()
    assert part(engine, "goblin_1").equipment == Equipment(armor="leather_armor")


def test_start_without_npc_equipment_leaves_none(registry, cfg):
    engine = named(registry, cfg, ScriptedRng(d20=[10, 10]), None, started=False)
    engine.start()
    assert part(engine, "goblin_1").equipment is None


def test_start_does_not_give_equipment_to_an_unnamed_monster(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=ScriptedRng(d20=[10, 10]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")], started=False,
    )
    engine.start()
    assert part(engine, "goblin_1").equipment is None


# --- engine.equipment ---

def test_equipment_of_the_participant(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment(armor="chain_mail"))
    assert engine.equipment("goblin_1") == Equipment(armor="chain_mail")


def test_equipment_falls_back_to_the_npc(registry, cfg):
    engine = named(registry, cfg, worn=Equipment(shield="shield"))
    assert engine.equipment("goblin_1") == Equipment(shield="shield")


def test_equipment_of_the_participant_wins_over_the_npc(registry, cfg):
    engine = named(registry, cfg, worn=Equipment(shield="shield"))
    part(engine, "goblin_1").equipment = Equipment(armor="chain_mail")
    assert engine.equipment("goblin_1") == Equipment(armor="chain_mail")


def test_equipment_is_none_by_default(registry, cfg):
    assert duel(registry, cfg).equipment("goblin_1") is None


def test_equipment_is_none_for_a_named_npc_without_it(registry, cfg):
    assert named(registry, cfg).equipment("goblin_1") is None


def test_equipment_of_an_unnamed_participant_is_readable(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment(armor="leather_armor"))
    assert engine.equipment("goblin_1").armor == "leather_armor"


# --- КД ---

def test_no_equipment_keeps_the_statblock_ac_of_the_goblin(registry, cfg):
    assert ac(duel(registry, cfg)) == 15


def test_no_equipment_keeps_the_statblock_ac_of_the_boss(registry, cfg):
    assert ac(duel(registry, cfg, monster="goblin_boss")) == 17


def test_no_equipment_keeps_the_statblock_ac_of_the_guard(registry, cfg):
    assert ac(duel(registry, cfg, monster="guard")) == 16


def test_stripped_goblin_has_ac_twelve(registry, cfg):
    assert ac(duel(registry, cfg, worn=Equipment())) == 12


def test_stripped_boss_has_ac_twelve(registry, cfg):
    assert ac(duel(registry, cfg, monster="goblin_boss", worn=Equipment())) == 12


def test_stripped_guard_has_ac_eleven(registry, cfg):
    assert ac(duel(registry, cfg, monster="guard", worn=Equipment())) == 11


def test_shield_only_goblin_has_ac_fourteen(registry, cfg):
    assert ac(duel(registry, cfg, worn=Equipment(shield="shield"))) == 14


def test_leather_without_a_shield_gives_thirteen(registry, cfg):
    assert ac(duel(registry, cfg, worn=Equipment(armor="leather_armor"))) == 13


def test_statblock_gear_in_equipment_gives_the_statblock_ac(registry, cfg):
    worn = Equipment(armor="leather_armor", shield="shield")
    assert ac(duel(registry, cfg, worn=worn)) == 15


def test_chain_mail_ignores_dexterity(registry, cfg):
    assert ac(duel(registry, cfg, worn=Equipment(armor="chain_mail"))) == 16


def test_chain_mail_with_a_shield_adds_two(registry, cfg):
    assert ac(duel(registry, cfg, worn=Equipment(armor="chain_mail", shield="shield"))) == 18


def test_dexterity_cap_of_the_chain_shirt(registry, cfg):
    # Лов +2 -- предел 2 не режет: 13 + 2
    assert ac(duel(registry, cfg, worn=Equipment(armor="chain_shirt"))) == 15


def test_dexterity_cap_cuts_a_nimble_monster(registry, cfg):
    reg = odd_registry(registry, abilities={
        "str": 8, "dex": 20, "con": 10, "int": 10, "wis": 8, "cha": 8,
    })
    engine = duel(registry, cfg, monster="odd_goblin", reg=reg, worn=Equipment(armor="chain_shirt"))
    # Лов +5, предел 2: 13 + 2 = 15; щит статблока 2 снят, доспех статблока: 11 + 5 + 2 = 18 -> 15
    #   - 18
    expected = 15 + (13 + 2) - (11 + 5 + 2)
    assert ac(engine) == expected


def test_natural_armor_keeps_its_base(registry, cfg):
    reg = odd_registry(registry, ac=17, armor=None, shield=None)
    worn = Equipment(armor="leather_armor")
    engine = duel(registry, cfg, monster="odd_goblin", reg=reg, worn=worn)
    # 17 - (10 + 2) + (11 + 2)
    assert ac(engine) == 18


def test_natural_armor_is_unchanged_by_empty_equipment(registry, cfg):
    reg = odd_registry(registry, ac=17, armor=None, shield=None)
    assert ac(duel(registry, cfg, monster="odd_goblin", reg=reg, worn=Equipment())) == 17


def test_natural_armor_with_a_shield_gets_plus_two(registry, cfg):
    reg = odd_registry(registry, ac=17, armor=None, shield=None)
    engine = duel(registry, cfg, monster="odd_goblin", reg=reg, worn=Equipment(shield="shield"))
    assert ac(engine) == 19


def test_pierce_is_applied_after_the_gear_recalculation(registry, cfg):
    # кольчуга: 16 > 12 -> min(16, 12 + 2) = 14
    engine = duel(registry, cfg, worn=Equipment(armor="chain_mail"))
    assert ac(engine, pierce=True) == 14


def test_pierce_does_not_change_a_stripped_goblin(registry, cfg):
    assert ac(duel(registry, cfg, worn=Equipment()), pierce=True) == 12


def test_pierce_of_the_unequipped_goblin_is_as_before(registry, cfg):
    assert ac(duel(registry, cfg), pierce=True) == 14


def test_magic_ac_effect_is_added_on_top(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment())
    creature(engine, "goblin_1").active_effects.append(
        ActiveEffect(id="shield", source="goblin_1", kind="ac",
                     params={"label": "Щит", "amount": 5, "magic": True})
    )
    assert ac(engine) == 17
    assert ac(engine, ignore_magic=True) == 12


def test_named_npc_ac_uses_the_npc_equipment_without_a_copy(registry, cfg):
    assert ac(named(registry, cfg, worn=Equipment())) == 12


def test_named_npc_ac_after_start_uses_the_copy(registry, cfg):
    engine = named(registry, cfg, ScriptedRng(d20=[10, 10]), Equipment(), started=False)
    engine.start()
    assert ac(engine) == 12


def test_hero_ac_is_not_touched_by_monster_equipment(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment())
    assert engine.armor_class("hero") == 19


# --- оружие: потерянное по equipment ---

def test_stripped_goblin_attacks_only_with_fists(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment())
    assert [i.id for i in attacks_of(engine, "goblin_1")] == ["unarmed"]


def test_stripped_goblin_has_no_weapon_attack_options(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment())
    ids = attack_ids(engine)
    assert ids
    assert not any("скимитар" in i or "лук" in i for i in ids)


def test_equipment_with_a_scimitar_keeps_the_scimitar_and_loses_the_bow(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment(weapons=["scimitar"]))
    ids = attack_ids(engine)
    assert "attack:скимитар:hero" in ids
    assert not any("лук" in i for i in ids)


def test_equipment_with_both_weapons_keeps_both(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment(weapons=["scimitar", "shortbow"]))
    ids = attack_ids(engine)
    assert "attack:скимитар:hero" in ids
    assert "attack:короткий_лук:hero" in ids


def test_armor_only_equipment_leaves_no_weapons(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment(armor=None, shield="shield", weapons=[]))
    assert [i.id for i in attacks_of(engine, "goblin_1")] == ["unarmed"]


def test_equipment_with_a_shield_and_a_scimitar(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment(armor=None, shield="shield", weapons=["scimitar"]))
    assert ac(engine) == 14
    assert "attack:скимитар:hero" in attack_ids(engine)


def test_lost_weapons_lists_the_missing_weapon(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment(weapons=["scimitar"]))
    assert lost_weapons(engine, "goblin_1") == (False, ["shortbow"])


def test_lost_weapons_lists_both_for_empty_equipment(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment())
    assert lost_weapons(engine, "goblin_1") == (False, ["scimitar", "shortbow"])


def test_lost_weapons_has_no_repeats_with_a_disarmed_flag(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment(weapons=["scimitar"]))
    creature(engine, "goblin_1").active_effects.append(
        ActiveEffect(id="disarmed", source="hero", kind="flag", params={"weapon_id": "shortbow"})
    )
    assert lost_weapons(engine, "goblin_1") == (False, ["shortbow"])


def test_lost_weapons_adds_equipment_losses_after_the_flags(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment(weapons=["shortbow"]))
    creature(engine, "goblin_1").active_effects.append(
        ActiveEffect(id="disarmed", source="hero", kind="flag", params={"weapon_id": "shortbow"})
    )
    assert lost_weapons(engine, "goblin_1") == (False, ["shortbow", "scimitar"])


def test_lost_weapons_is_empty_without_equipment(registry, cfg):
    assert lost_weapons(duel(registry, cfg), "goblin_1") == (False, [])


def test_lost_weapons_of_a_hero_ignores_equipment(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment())
    assert lost_weapons(engine, "hero") == (False, [])


def test_all_lost_flag_survives_the_equipment_merge(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment(weapons=["scimitar"]))
    creature(engine, "goblin_1").active_effects.append(
        ActiveEffect(id="disarmed", source="hero", kind="flag")
    )
    assert lost_weapons(engine, "goblin_1")[0] is True


def test_hero_cannot_disarm_a_stripped_goblin(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment())
    assert not [i for i in option_ids(engine, "hero") if i.startswith("disarm")]


def test_hero_disarms_only_the_weapon_left_in_equipment(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment(weapons=["scimitar"]))
    assert [i for i in option_ids(engine, "hero") if i.startswith("disarm")] == [
        "disarm:goblin_1:scimitar"
    ]


def test_weapon_ids_follow_the_equipment(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment(weapons=["shortbow"]))
    assert disarm.weapon_ids(engine, "goblin_1") == ["shortbow"]


def test_boss_without_a_scimitar_has_no_multiattack(registry, cfg):
    engine = duel(registry, cfg, monster="goblin_boss", worn=Equipment())
    assert "multiattack" not in option_ids(engine, "goblin_1")


def test_boss_with_a_scimitar_keeps_the_multiattack(registry, cfg):
    engine = duel(registry, cfg, monster="goblin_boss", worn=Equipment(weapons=["scimitar"]))
    assert "multiattack" in option_ids(engine, "goblin_1")


def test_stripped_goblin_hits_with_a_fist(registry, cfg):
    # кулак: 1 + Сил(-1) = 0 урона; попадание не бросаем -- проверяем, что удар вообще идёт
    engine = duel(registry, cfg, ScriptedRng(d20=[20]), worn=Equipment())
    result = engine.perform("goblin_1", "attack:unarmed:hero")
    assert isinstance(result, list)
    assert any("безоружный удар" in line for line in engine.state.log)


# --- подбор потерянного по equipment ---

def drop(engine, item_id, owner="goblin_1", zone="hall"):
    engine.state.ground_items.append(
        GroundItem(item_id=item_id, zone_id=zone, owner_ref=owner, cost_cp=0)
    )


def test_goblin_may_pick_a_scimitar_lost_by_equipment(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment(weapons=["shortbow"]))
    drop(engine, "scimitar")
    assert [o.id for o in engine.available_actions("goblin_1") if o.kind == "pickup"] == [
        "pickup:0"
    ]


def test_goblin_may_not_pick_a_weapon_it_still_holds(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment(weapons=["scimitar"]))
    drop(engine, "scimitar")
    assert [o for o in engine.available_actions("goblin_1") if o.kind == "pickup"] == []


def test_pickup_returns_the_weapon_to_the_equipment(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment(weapons=["shortbow"]))
    drop(engine, "scimitar")
    engine.perform("goblin_1", "pickup:0")
    assert part(engine, "goblin_1").equipment.weapons == ["shortbow", "scimitar"]
    assert engine.state.ground_items == []


def test_pickup_restores_the_attack(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment(weapons=["shortbow"]))
    drop(engine, "scimitar")
    engine.perform("goblin_1", "pickup:0")
    assert "attack:скимитар:hero" in attack_ids(engine)


def test_pickup_after_stripping_brings_back_the_weapon_action(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment())
    drop(engine, "scimitar")
    engine.perform("goblin_1", "pickup:0")
    assert [i.id for i in attacks_of(engine, "goblin_1")] == ["скимитар"]


def test_pickup_logs_the_weapon(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment(weapons=["shortbow"]))
    drop(engine, "scimitar")
    engine.perform("goblin_1", "pickup:0")
    assert "Воин-гоблин подбирает скимитар" in engine.state.log


def test_pickup_of_a_disarmed_flag_still_removes_the_flag(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment(weapons=["scimitar", "shortbow"]))
    creature(engine, "goblin_1").active_effects.append(
        ActiveEffect(id="disarmed", source="hero", kind="flag", params={"weapon_id": "scimitar"})
    )
    drop(engine, "scimitar")
    engine.perform("goblin_1", "pickup:0")
    assert creature(engine, "goblin_1").active_effects == []
    assert part(engine, "goblin_1").equipment.weapons == ["scimitar", "shortbow"]


def test_pickup_after_start_leaves_the_npc_equipment_alone(registry, cfg):
    engine = named(registry, cfg, ScriptedRng(d20=[10, 10]), Equipment(weapons=["shortbow"]),
                   started=False)
    engine.start()
    drop(engine, "scimitar")
    engine.perform("goblin_1", "pickup:0")
    assert part(engine, "goblin_1").equipment.weapons == ["shortbow", "scimitar"]
    assert engine.world.npcs["goblin_1"].equipment.weapons == ["shortbow"]


# --- body_equipment ---

def test_body_equipment_reads_the_participant_equipment(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment(armor="chain_mail", weapons=["scimitar"]))
    body = trophies.body_equipment(engine, "goblin_1", disarm.weapon_ids)
    assert body == Equipment(armor="chain_mail", shield=None, weapons=["scimitar"])


def test_body_equipment_reads_the_npc_equipment_without_a_copy(registry, cfg):
    engine = named(registry, cfg, worn=Equipment(shield="shield"))
    body = trophies.body_equipment(engine, "goblin_1", disarm.weapon_ids)
    assert body == Equipment(armor=None, shield="shield", weapons=[])


def test_body_equipment_prefers_the_participant_over_the_npc(registry, cfg):
    engine = named(registry, cfg, worn=Equipment(shield="shield"))
    part(engine, "goblin_1").equipment = Equipment(armor="chain_mail")
    body = trophies.body_equipment(engine, "goblin_1", disarm.weapon_ids)
    assert body.armor == "chain_mail"
    assert body.shield is None


def test_body_equipment_follows_the_statblock_without_equipment(registry, cfg):
    engine = duel(registry, cfg)
    body = trophies.body_equipment(engine, "goblin_1", disarm.weapon_ids)
    assert body == Equipment(
        armor="leather_armor", shield="shield", weapons=["scimitar", "shortbow"]
    )


def test_body_equipment_drops_disarmed_weapons(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment(weapons=["scimitar", "shortbow"]))
    creature(engine, "goblin_1").active_effects.append(
        ActiveEffect(id="disarmed", source="hero", kind="flag", params={"weapon_id": "scimitar"})
    )
    body = trophies.body_equipment(engine, "goblin_1", disarm.weapon_ids)
    assert body.weapons == ["shortbow"]


# --- engine.start: заведение состояния и бой ---

def test_start_creates_the_npc_state_from_the_statblock(registry, cfg):
    engine = named(registry, cfg, ScriptedRng(d20=[10, 10]), started=False)
    engine.world.npcs["goblin_1"].creature = None
    engine.start()
    state = engine.world.npcs["goblin_1"].creature
    assert (state.hp_current, state.hp_max) == (10, 10)


def test_start_keeps_the_existing_npc_state(registry, cfg):
    engine = named(registry, cfg, ScriptedRng(d20=[10, 10]), started=False)
    engine.world.npcs["goblin_1"].creature.hp_current = 3
    engine.start()
    assert engine.world.npcs["goblin_1"].creature.hp_current == 3


def test_start_does_not_touch_the_state_of_an_unnamed_participant(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=ScriptedRng(d20=[10, 10]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")], started=False,
    )
    part(engine, "goblin_1").creature.hp_current = 4
    engine.start()
    assert part(engine, "goblin_1").creature.hp_current == 4
    assert "goblin_1" not in engine.world.npcs


def test_start_opens_round_one_with_the_first_turn(registry, cfg):
    engine = named(registry, cfg, ScriptedRng(d20=[10, 10]), started=False)
    engine.start()
    assert (engine.state.round, engine.state.turn_index) == (1, 0)
    assert engine.state.log[-1] == "Бой начался"


def test_start_twice_is_an_error(registry, cfg):
    import pytest

    engine = named(registry, cfg, ScriptedRng(d20=[10, 10]), started=False)
    engine.start()
    with pytest.raises(ValueError, match="бой уже начат"):
        engine.start()


# --- КД: сроки эффектов и бронебойная стрела по низкой Лов ---

def timed_ac(engine, until):
    creature(engine, "goblin_1").active_effects.append(
        ActiveEffect(
            id="shield", source="goblin_1", kind="ac", params={"label": "Щит", "amount": 5},
            expires=Expiry(kind="seconds", value=until),
        )
    )


def test_expired_ac_effect_is_not_counted(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment())
    engine.world.clock.now_s = 1000
    timed_ac(engine, 999)
    assert ac(engine) == 12


def test_live_ac_effect_is_counted(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment())
    engine.world.clock.now_s = 1000
    timed_ac(engine, 1001)
    assert ac(engine) == 17


def plain_dex_registry(registry, armor_class):
    return odd_registry(registry, ac=armor_class, armor=None, shield=None, abilities={
        "str": 8, "dex": 10, "con": 10, "int": 10, "wis": 8, "cha": 8,
    })


def test_pierce_cuts_a_plain_dexterity_monster_to_twelve(registry, cfg):
    reg = plain_dex_registry(registry, 15)
    engine = duel(registry, cfg, monster="odd_goblin", reg=reg)
    assert ac(engine, pierce=True) == 12


def test_pierce_cuts_a_thirteen_to_twelve(registry, cfg):
    reg = plain_dex_registry(registry, 13)
    engine = duel(registry, cfg, monster="odd_goblin", reg=reg)
    assert ac(engine, pierce=True) == 12


def test_pierce_leaves_a_twelve_alone(registry, cfg):
    reg = plain_dex_registry(registry, 12)
    engine = duel(registry, cfg, monster="odd_goblin", reg=reg)
    assert ac(engine, pierce=True) == 12


def test_lost_weapons_of_a_hero_with_a_participant_equipment(registry, cfg):
    engine = duel(registry, cfg, worn=Equipment())
    part(engine, "hero").equipment = Equipment()
    assert lost_weapons(engine, "hero") == (False, [])
