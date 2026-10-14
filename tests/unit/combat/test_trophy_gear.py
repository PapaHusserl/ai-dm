# Трофеи с тел врагов в бою (docs/CUSTOM-ITEMS-PLAN.md, разд. 7, партия В).
#   settle_ground (конец боя) при победе героя (victory / ended_by_master, герой жив) считает
#   state.gear -- оружие и квестовые вещи с тел:
#     * тело -- враг-монстр (side enemies) со статусом dead или down; fled, surrendered, active и
#       перебежчик (метка parley_defected) оружия не дают;
#     * оружие тела -- weapon_ids(engine, ref) ПОСЛЕ раздачи выбитого: выбитое уже у героя и в
#       gear не дублируется; оружие рядового -- вариант качества по ПО (гоблин-воин ПО 1/4 --
#       junk, цена 10% SRD); босс (лидер группы и именованный NPC [named или key], либо тег boss
#       у NPC/монстра) -- исходное оружие по полной цене, quality None;
#     * квестовый кастомный предмет с держателем kind "npc" -- поверженный NPC -- идёт в gear как
#       есть; держатель band/location -- нет;
#     * поражение, бегство героя, мёртвый герой -- gear пуст.
#   К7к: с тела берутся также доспех и щит статблока (test_trophy_armor.py); здесь settled()
#   возвращает gear без доспехов и щитов (ARMOR_IDS), тесты файла -- про оружие и квестовые вещи.
#   strip_weapon(engine, source, target, weapon_id) для монстра возвращает (цена, качество) трофея
#   по ПО тела (босс -- полная цена, None); для героя -- как раньше.
from combat_kit import ScriptedRng, make_engine, make_fighter, make_npc, mon, part

from ai_dm.combat.disarm import disarm_target, strip_weapon
from ai_dm.combat.end import settle_ground
from ai_dm.combat.trophies import is_boss
from ai_dm.rules.inventory import count_item
from ai_dm.state.combat import Participant
from ai_dm.state.creature import ActiveEffect, CreatureState
from ai_dm.state.world import CustomItem, ItemHolder


def fight(registry, cfg, goblins=3, named=False, hero=None):
    monsters = [
        mon(f"goblin_{i}", "goblin_warrior", "hall", named=named) for i in range(1, goblins + 1)
    ]
    return make_engine(
        registry, cfg, heroes=[hero or make_fighter(registry)], rng=ScriptedRng(),
        monsters=monsters,
    )


def won(engine, statuses="dead"):
    for p in engine.state.participants:
        if p.side == "enemies":
            p.status = statuses
    engine.state.outcome = "victory"


ARMOR_IDS = {"leather_armor", "chain_shirt", "shield"}


def settled(engine):
    settle_ground(engine)
    return [e for e in engine.state.gear if e.item_id not in ARMOR_IDS]


def as_tuples(gear):
    return sorted((e.item_id, e.qty, e.cost_cp, e.quality) for e in gear)


def creature_of(engine, ref):
    return engine.creature(ref)


def mark(engine, ref, effect_id, **params):
    creature_of(engine, ref).active_effects.append(
        ActiveEffect(id=effect_id, source="hero", kind="flag", params=params)
    )


def hold(engine, item_id, holder_kind, ref, qty=1, cost_cp=900, quest=True):
    engine.world.custom_items[item_id] = CustomItem(
        id=item_id, name="Ржавый ключ", quest=quest, created_s=0,
        holder=ItemHolder(
            kind=holder_kind, ref=ref, label="Клык", since_s=0, qty=qty, cost_cp=cost_cp
        ),
    )


# рядовые враги

def test_three_dead_goblins_give_stacks_of_junk_weapons(registry, cfg):
    engine = fight(registry, cfg)
    won(engine)
    assert as_tuples(settled(engine)) == [
        ("scimitar", 3, 250, "junk"), ("shortbow", 3, 250, "junk"),
    ]


def test_downed_goblin_gives_weapons(registry, cfg):
    engine = fight(registry, cfg, goblins=1)
    won(engine, "down")
    assert as_tuples(settled(engine)) == [
        ("scimitar", 1, 250, "junk"), ("shortbow", 1, 250, "junk"),
    ]


def test_fled_goblin_gives_nothing(registry, cfg):
    engine = fight(registry, cfg, goblins=1)
    won(engine, "fled")
    assert settled(engine) == []


def test_surrendered_goblin_gives_nothing(registry, cfg):
    engine = fight(registry, cfg, goblins=1)
    won(engine, "surrendered")
    assert settled(engine) == []


def test_standing_goblin_gives_nothing(registry, cfg):
    engine = fight(registry, cfg, goblins=1)
    won(engine, "active")
    engine.state.outcome = "ended_by_master"
    assert settled(engine) == []


def test_defector_gives_nothing(registry, cfg):
    engine = fight(registry, cfg, goblins=2)
    won(engine)
    mark(engine, "goblin_1", "parley_defected")
    assert as_tuples(settled(engine)) == [
        ("scimitar", 1, 250, "junk"), ("shortbow", 1, 250, "junk"),
    ]


def test_mixed_statuses_count_only_dead_and_down(registry, cfg):
    engine = fight(registry, cfg, goblins=4)
    won(engine)
    part(engine, "goblin_2").status = "fled"
    part(engine, "goblin_3").status = "surrendered"
    part(engine, "goblin_4").status = "down"
    assert as_tuples(settled(engine)) == [
        ("scimitar", 2, 250, "junk"), ("shortbow", 2, 250, "junk"),
    ]


def test_ally_of_the_hero_gives_nothing(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=ScriptedRng(),
        monsters=[mon("goblin_1", "goblin_warrior", "hall", side="heroes", group="allies")],
    )
    part(engine, "goblin_1").status = "dead"
    engine.state.outcome = "victory"
    assert settled(engine) == []


# выбитое оружие не дублируется

def test_disarmed_weapon_is_not_in_gear(registry, cfg):
    engine = fight(registry, cfg, goblins=1)
    won(engine)
    mark(engine, "goblin_1", "disarmed", weapon_id="scimitar")
    assert as_tuples(settled(engine)) == [("shortbow", 1, 250, "junk")]


def test_weapon_disarmed_in_the_fight_goes_to_the_hero_once(registry, cfg):
    hero = make_fighter(registry)
    engine = fight(registry, cfg, goblins=1, hero=hero)
    before = count_item(hero, "scimitar")
    disarm_target(engine, "hero", "goblin_1", "scimitar", False)
    won(engine)
    gear = settled(engine)
    assert count_item(hero, "scimitar") == before + 1
    assert [e.item_id for e in gear] == ["shortbow"]


def test_old_save_flag_without_weapon_id_leaves_no_weapons(registry, cfg):
    engine = fight(registry, cfg, goblins=1)
    won(engine)
    mark(engine, "goblin_1", "disarmed")
    assert settled(engine) == []


# цена выбитого оружия монстра

def test_strip_weapon_of_ordinary_goblin_gives_trophy_price(registry, cfg):
    engine = fight(registry, cfg, goblins=1)
    assert strip_weapon(engine, "hero", "goblin_1", "scimitar") == (250, "junk")


def test_strip_weapon_price_is_below_srd(registry, cfg):
    engine = fight(registry, cfg, goblins=1)
    cost_cp, _ = strip_weapon(engine, "hero", "goblin_1", "shortbow")
    assert cost_cp < registry.get("weapon", "shortbow").cost_cp


def test_knocked_out_weapon_lands_on_the_ground_with_trophy_price(registry, cfg):
    engine = fight(registry, cfg, goblins=1)
    disarm_target(engine, "hero", "goblin_1", "scimitar", False)
    item = engine.state.ground_items[0]
    assert (item.item_id, item.cost_cp, item.quality) == ("scimitar", 250, "junk")


def test_grabbed_weapon_goes_to_the_hero_with_trophy_price(registry, cfg):
    hero = make_fighter(registry)
    engine = fight(registry, cfg, goblins=1, hero=hero)
    disarm_target(engine, "hero", "goblin_1", "scimitar", True)
    got = [e for e in hero.inventory if e.item_id == "scimitar"]
    assert [(e.cost_cp, e.quality) for e in got] == [(250, "junk")]


def test_strip_weapon_of_boss_gives_full_price(registry, cfg):
    engine = fight(registry, cfg, goblins=2, named=True)
    engine.world.npcs["goblin_1"].named = True
    assert strip_weapon(engine, "hero", "goblin_1", "scimitar") == (
        registry.get("weapon", "scimitar").cost_cp, None
    )


def test_strip_weapon_of_hero_is_unchanged(registry, cfg):
    hero = make_fighter(registry)
    engine = fight(registry, cfg, goblins=1, hero=hero)
    held = [e for e in hero.inventory if e.item_id == "longsword"][0]
    assert strip_weapon(engine, "goblin_1", "hero", "longsword") == (held.cost_cp, held.quality)


# боссы

def test_named_group_leader_is_boss(registry, cfg):
    engine = fight(registry, cfg, goblins=2, named=True)
    engine.world.npcs["goblin_1"].named = True
    assert is_boss(engine, part(engine, "goblin_1")) is True


def test_key_group_leader_is_boss(registry, cfg):
    engine = fight(registry, cfg, goblins=2, named=True)
    engine.world.npcs["goblin_1"].key = True
    assert is_boss(engine, part(engine, "goblin_1")) is True


def test_named_but_not_leader_is_not_boss(registry, cfg):
    engine = fight(registry, cfg, goblins=2, named=True)
    engine.world.npcs["goblin_2"].named = True
    assert is_boss(engine, part(engine, "goblin_2")) is False


def test_leader_without_name_is_not_boss(registry, cfg):
    engine = fight(registry, cfg, goblins=2, named=True)
    assert is_boss(engine, part(engine, "goblin_1")) is False


def test_anonymous_leader_is_not_boss(registry, cfg):
    engine = fight(registry, cfg, goblins=2)
    assert is_boss(engine, part(engine, "goblin_1")) is False


def test_boss_tag_on_npc_makes_boss_without_leadership(registry, cfg):
    engine = fight(registry, cfg, goblins=2, named=True)
    engine.world.npcs["goblin_2"].tags = ["boss"]
    assert is_boss(engine, part(engine, "goblin_2")) is True


def test_named_leader_gives_original_weapons_at_full_price(registry, cfg):
    engine = fight(registry, cfg, goblins=1, named=True)
    engine.world.npcs["goblin_1"].named = True
    won(engine)
    scimitar = registry.get("weapon", "scimitar").cost_cp
    bow = registry.get("weapon", "shortbow").cost_cp
    assert as_tuples(settled(engine)) == [
        ("scimitar", 1, scimitar, None), ("shortbow", 1, bow, None),
    ]


def test_boss_tag_gives_original_weapons(registry, cfg):
    engine = fight(registry, cfg, goblins=2, named=True)
    engine.world.npcs["goblin_2"].tags = ["boss"]
    won(engine)
    part(engine, "goblin_1").status = "fled"
    assert {e.quality for e in settled(engine)} == {None}


def test_boss_and_henchmen_give_separate_stacks(registry, cfg):
    engine = fight(registry, cfg, goblins=1, named=True)
    engine.world.npcs["goblin_1"].named = True
    engine.state.participants.append(mon_part("goblin_9"))
    won(engine)
    qualities = sorted(str(e.quality) for e in settled(engine) if e.item_id == "scimitar")
    assert qualities == ["None", "junk"]


def mon_part(ref):
    # безымянный гоблин-воин той же группы в зоне hall
    return Participant(
        ref=ref, side="enemies", group_id="goblins", zone_id="hall",
        monster_id="goblin_warrior", name="Воин-гоблин",
        creature=CreatureState(hp_current=7, hp_max=7),
    )


# квестовые вещи

def test_quest_item_of_defeated_npc_goes_to_gear_as_is(registry, cfg):
    engine = fight(registry, cfg, goblins=1, named=True)
    hold(engine, "custom_1", "npc", "goblin_1", qty=1, cost_cp=900)
    won(engine)
    gear = [e for e in settled(engine) if e.item_id == "custom_1"]
    assert [(e.qty, e.cost_cp, e.quality) for e in gear] == [(1, 900, None)]


def test_quest_item_of_fled_npc_stays_with_him(registry, cfg):
    engine = fight(registry, cfg, goblins=1, named=True)
    hold(engine, "custom_1", "npc", "goblin_1")
    won(engine, "fled")
    assert settled(engine) == []


def test_quest_item_of_band_holder_is_not_in_gear(registry, cfg):
    engine = fight(registry, cfg, goblins=1, named=True)
    hold(engine, "custom_1", "band", "goblin_1")
    won(engine)
    assert all(e.item_id != "custom_1" for e in settled(engine))


def test_quest_item_of_another_npc_is_not_in_gear(registry, cfg):
    engine = fight(registry, cfg, goblins=1, named=True)
    hold(engine, "custom_1", "npc", "npc_far_away")
    won(engine)
    assert all(e.item_id != "custom_1" for e in settled(engine))


# не победа

def test_defeat_gives_no_gear(registry, cfg):
    engine = fight(registry, cfg)
    won(engine)
    engine.state.outcome = "defeat_pending"
    assert settled(engine) == []


def test_hero_fled_gives_no_gear(registry, cfg):
    engine = fight(registry, cfg)
    won(engine)
    engine.state.outcome = "fled"
    assert settled(engine) == []


def test_dead_hero_gives_no_gear(registry, cfg):
    hero = make_fighter(registry)
    engine = fight(registry, cfg, hero=hero)
    won(engine)
    hero.status = "dead"
    assert settled(engine) == []


def test_ended_by_master_with_dead_bodies_gives_gear(registry, cfg):
    engine = fight(registry, cfg, goblins=1)
    won(engine)
    engine.state.outcome = "ended_by_master"
    assert len(settled(engine)) == 2


def test_no_enemies_no_gear(registry, cfg):
    engine = fight(registry, cfg, goblins=0)
    engine.state.outcome = "victory"
    assert settled(engine) == []


# участник без monster_id и боссы без группы

def test_quest_item_of_dead_participant_without_monster_id_goes_to_gear(registry, cfg):
    engine = fight(registry, cfg, goblins=1)
    engine.world.npcs["npc_klyk"] = make_npc(registry, "npc_klyk", "goblin_warrior")
    engine.state.participants.append(
        Participant(ref="npc_klyk", side="enemies", group_id="goblins", zone_id="hall")
    )
    hold(engine, "custom_1", "npc", "npc_klyk")
    won(engine)
    gear = settled(engine)
    assert [e.item_id for e in gear if e.item_id == "custom_1"] == ["custom_1"]
    assert as_tuples([e for e in gear if e.item_id != "custom_1"]) == [
        ("scimitar", 1, 250, "junk"), ("shortbow", 1, 250, "junk"),
    ]


def test_participant_without_monster_id_gives_no_weapons(registry, cfg):
    engine = fight(registry, cfg, goblins=0)
    engine.world.npcs["npc_klyk"] = make_npc(registry, "npc_klyk", "goblin_warrior")
    engine.state.participants.append(
        Participant(ref="npc_klyk", side="enemies", group_id="goblins", zone_id="hall")
    )
    won(engine)
    assert settled(engine) == []


def test_is_boss_without_group_in_state_is_false(registry, cfg):
    engine = fight(registry, cfg, goblins=1, named=True)
    engine.world.npcs["goblin_1"].named = True
    del engine.state.groups["goblins"]
    assert is_boss(engine, part(engine, "goblin_1")) is False
