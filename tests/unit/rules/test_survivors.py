# Ж1 (docs/plan-zh1.md, пп. 0.1, 0.3, 0.5, 0.6, 0.8): выжившие боя становятся NPC мира.
#   kind_of / classify -- кто выжил и каким видом (defected / surrendered / spared / fled); зовутся
#     до finish_combat; исходы victory / fled / ended_by_master, герой жив;
#   free_id / landing / make_npc -- id <monster_id>_<n>, локация (бежавший -- в соседнюю), поля NPC;
#   remember_fight -- события памяти и цель life_debt пишет движок;
#   materialize / note_met -- запись в world.npcs и знакомство по виду в журнале героя;
#   reveal_names -- имя открывается, когда прозвучало в тексте хода.
import game_kit  # noqa: F401  (путь к master_kit)
from master_kit import combat_ctx

from ai_dm.rules.survivors import (
    LIFE_DEBT_TEXT,
    classify,
    free_id,
    group_of,
    kind_of,
    landing,
    make_npc,
    materialize,
    note_met,
    remember_fight,
    reveal_names,
)
from ai_dm.state.creature import ActiveEffect
from ai_dm.state.world import NPC, Connection


def fight(registry, cfg, outcome="victory", statuses=None, flags=()):
    bundle = combat_ctx(registry, cfg).bundle
    state = bundle.session.active_combat
    state.outcome = outcome
    for ref, status in (statuses or {}).items():
        part_of(bundle, ref).status = status
    for ref, flag_id in flags:
        part_of(bundle, ref).creature.active_effects.append(
            ActiveEffect(id=flag_id, source="hero", kind="flag")
        )
    return bundle


def part_of(bundle, ref):
    return [p for p in bundle.session.active_combat.participants if p.ref == ref][0]


def hero_of(bundle):
    return bundle.heroes[0]


def survivor_of(bundle, ref, cfg=None):
    found = [s for s in classify(bundle, hero_of(bundle)) if s.part.ref == ref]
    return found[0]


def name_in_memory(npc):
    return [e.text for m in npc.memory for e in m.events]


# kind_of

def test_defect_flag_gives_defected(registry, cfg):
    bundle = fight(registry, cfg, flags=[("g1", "parley_defected")])
    assert kind_of(part_of(bundle, "g1"), "victory") == "defected"


def test_defector_on_heroes_side_is_defected(registry, cfg):
    bundle = fight(registry, cfg, flags=[("g1", "parley_defected")])
    part_of(bundle, "g1").side = "heroes"
    assert kind_of(part_of(bundle, "g1"), "victory") == "defected"


def test_dead_defector_is_not_a_survivor(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "dead"}, flags=[("g1", "parley_defected")])
    assert kind_of(part_of(bundle, "g1"), "victory") is None


def test_surrendered_enemy_is_surrendered(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "surrendered"})
    assert kind_of(part_of(bundle, "g1"), "victory") == "surrendered"


def test_fled_enemy_is_fled(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "fled"})
    assert kind_of(part_of(bundle, "g1"), "victory") == "fled"


def test_down_enemy_is_spared(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "down"})
    assert kind_of(part_of(bundle, "g1"), "victory") == "spared"


def test_dead_enemy_is_not_a_survivor(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "dead"})
    assert kind_of(part_of(bundle, "g1"), "victory") is None


def test_active_enemy_after_victory_is_not_a_survivor(registry, cfg):
    bundle = fight(registry, cfg)
    assert kind_of(part_of(bundle, "g1"), "victory") is None


def test_active_enemy_when_master_ends_fight_is_spared(registry, cfg):
    bundle = fight(registry, cfg, outcome="ended_by_master")
    assert kind_of(part_of(bundle, "g1"), "ended_by_master") == "spared"


def test_hero_side_without_flag_is_not_a_survivor(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "down"})
    part_of(bundle, "g1").side = "heroes"
    assert kind_of(part_of(bundle, "g1"), "victory") is None


# classify

def test_classify_lists_survivors_in_participant_order(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "down", "g2": "fled"})
    got = [(s.part.ref, s.kind) for s in classify(bundle, hero_of(bundle))]
    assert got == [("g1", "spared"), ("g2", "fled")]


def test_classify_label_is_the_numbered_creature_name(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "down", "g2": "down"})
    assert [s.label for s in classify(bundle, hero_of(bundle))] == [
        "Воин-гоблин 1", "Воин-гоблин 2",
    ]


def test_classify_after_hero_defeat_is_empty(registry, cfg):
    bundle = fight(registry, cfg, outcome="defeat", statuses={"g1": "down"})
    assert classify(bundle, hero_of(bundle)) == []


def test_classify_with_dead_hero_is_empty(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "down"})
    hero_of(bundle).status = "dead"
    assert classify(bundle, hero_of(bundle)) == []


def test_classify_after_fled_outcome_keeps_survivors(registry, cfg):
    bundle = fight(registry, cfg, outcome="fled", statuses={"g1": "surrendered"})
    assert [s.kind for s in classify(bundle, hero_of(bundle))] == ["surrendered"]


def test_classify_skips_participant_already_in_world(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "down", "g2": "down"})
    bundle.world.npcs["g1"] = NPC(id="g1", name="Гракх", means=["бой"])
    assert [s.part.ref for s in classify(bundle, hero_of(bundle))] == ["g2"]


def test_classify_skips_participant_without_monster_id(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "down"})
    part_of(bundle, "g1").monster_id = None
    assert classify(bundle, hero_of(bundle)) == []


def test_classify_skips_participant_without_creature(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "down"})
    part_of(bundle, "g1").creature = None
    assert classify(bundle, hero_of(bundle)) == []


def test_classify_never_lists_the_hero(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "down", "g2": "down"})
    assert "hero" not in [s.part.ref for s in classify(bundle, hero_of(bundle))]


# free_id

def taken(bundle, npc_id):
    bundle.world.npcs[npc_id] = NPC(id=npc_id, name="X", means=["бой"])


def test_free_id_has_turn_in_format(registry, cfg):
    bundle = fight(registry, cfg)
    bundle.session.turn_seq = 7
    assert free_id(bundle, "goblin_warrior") == "goblin_warrior_t7_1"


def test_free_id_skips_taken_numbers(registry, cfg):
    bundle = fight(registry, cfg)
    for n in (1, 2):
        taken(bundle, f"goblin_warrior_t0_{n}")
    assert free_id(bundle, "goblin_warrior") == "goblin_warrior_t0_3"


def test_free_id_fills_the_first_gap(registry, cfg):
    bundle = fight(registry, cfg)
    taken(bundle, "goblin_warrior_t0_2")
    assert free_id(bundle, "goblin_warrior") == "goblin_warrior_t0_1"


def test_free_id_ignores_taken_id_of_other_turn(registry, cfg):
    bundle = fight(registry, cfg)
    bundle.session.turn_seq = 5
    taken(bundle, "goblin_warrior_t4_1")
    assert free_id(bundle, "goblin_warrior") == "goblin_warrior_t5_1"


def test_free_id_skips_id_taken_by_location(registry, cfg):
    bundle = fight(registry, cfg)
    bundle.world.locations["goblin_warrior_t0_1"] = bundle.world.locations["forest"]
    assert free_id(bundle, "goblin_warrior") == "goblin_warrior_t0_2"


def test_free_id_skips_id_taken_by_hero(registry, cfg):
    bundle = fight(registry, cfg)
    hero_of(bundle).id = "goblin_warrior_t0_1"
    assert free_id(bundle, "goblin_warrior") == "goblin_warrior_t0_2"


def test_free_id_skips_id_taken_by_faction(registry, cfg):
    from ai_dm.state.world import Faction

    bundle = fight(registry, cfg)
    bundle.world.factions["goblin_warrior_t0_1"] = Faction(id="goblin_warrior_t0_1", name="F")
    assert free_id(bundle, "goblin_warrior") == "goblin_warrior_t0_2"


# landing

def test_spared_stays_in_hero_location(registry, cfg):
    bundle = fight(registry, cfg)
    assert landing(bundle.world, hero_of(bundle), "spared") == "vale"


def test_surrendered_and_defected_stay_in_hero_location(registry, cfg):
    bundle = fight(registry, cfg)
    got = {landing(bundle.world, hero_of(bundle), k) for k in ("surrendered", "defected")}
    assert got == {"vale"}


def test_fled_goes_to_neighbour_location(registry, cfg):
    bundle = fight(registry, cfg)
    assert landing(bundle.world, hero_of(bundle), "fled") == "forest"


def test_fled_uses_incoming_connection_too(registry, cfg):
    # из леса связей нет, но vale ведёт в лес -- сосед в обратную сторону
    bundle = fight(registry, cfg)
    hero_of(bundle).location_id = "forest"
    assert landing(bundle.world, hero_of(bundle), "fled") == "vale"


def test_fled_without_neighbours_stays(registry, cfg):
    bundle = fight(registry, cfg)
    hero_of(bundle).location_id = "goblin_den"
    assert landing(bundle.world, hero_of(bundle), "fled") == "goblin_den"


def test_fled_picks_neighbour_with_minimal_id(registry, cfg):
    bundle = fight(registry, cfg)
    bundle.world.locations["vale"].connections.append(Connection(to="goblin_den", distance_m=5))
    assert landing(bundle.world, hero_of(bundle), "fled") == "forest"


def test_fled_ignores_connection_to_unknown_location(registry, cfg):
    bundle = fight(registry, cfg)
    bundle.world.locations["vale"].connections[:] = [Connection(to="nowhere", distance_m=5)]
    assert landing(bundle.world, hero_of(bundle), "fled") == "vale"


def test_fled_from_unknown_location_stays(registry, cfg):
    bundle = fight(registry, cfg)
    hero_of(bundle).location_id = "nowhere"
    assert landing(bundle.world, hero_of(bundle), "fled") == "nowhere"


# make_npc

def test_make_npc_hides_name_behind_label(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "down"})
    npc = make_npc(bundle, hero_of(bundle), survivor_of(bundle, "g1"), cfg)
    assert (npc.id, npc.name, npc.named, npc.means) == (
        "goblin_warrior_t0_1", "Воин-гоблин 1", False, ["Воин-гоблин 1"],
    )


def test_make_npc_remembers_kind_and_label(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "down"})
    npc = make_npc(bundle, hero_of(bundle), survivor_of(bundle, "g1"), cfg)
    assert npc.combat == {"monster_id": "goblin_warrior", "label": "Воин-гоблин 1"}
    assert npc.origin == "engine"


def test_make_npc_takes_creature_equipment_and_group_from_participant(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "down"})
    part = part_of(bundle, "g1")
    npc = make_npc(bundle, hero_of(bundle), survivor_of(bundle, "g1"), cfg)
    assert npc.creature == part.creature
    assert npc.equipment == part.equipment
    assert npc.groups == [part.group_id]


def test_make_npc_creature_is_an_independent_copy(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "down"})
    part = part_of(bundle, "g1")
    npc = make_npc(bundle, hero_of(bundle), survivor_of(bundle, "g1"), cfg)
    assert npc.creature is not part.creature
    before = part.creature.hp_current
    npc.creature.hp_current = before + 5
    assert part.creature.hp_current == before


def test_make_npc_equipment_is_an_independent_copy(registry, cfg):
    from ai_dm.state.creature import Equipment

    bundle = fight(registry, cfg, statuses={"g1": "down"})
    part = part_of(bundle, "g1")
    part.equipment = Equipment()
    npc = make_npc(bundle, hero_of(bundle), survivor_of(bundle, "g1"), cfg)
    assert npc.equipment == part.equipment
    assert npc.equipment is not part.equipment


def test_make_npc_creature_nested_data_is_not_shared(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "down"})
    part = part_of(bundle, "g1")
    npc = make_npc(bundle, hero_of(bundle), survivor_of(bundle, "g1"), cfg)
    npc.creature.active_effects.append(ActiveEffect(id="x", source="hero", kind="flag"))
    assert [e.id for e in part.creature.active_effects] == []


def test_make_npc_equipment_nested_data_is_not_shared(registry, cfg):
    from ai_dm.state.creature import Equipment

    bundle = fight(registry, cfg, statuses={"g1": "down"})
    part = part_of(bundle, "g1")
    part.equipment = Equipment()
    npc = make_npc(bundle, hero_of(bundle), survivor_of(bundle, "g1"), cfg)
    npc.equipment.weapons.append("club")
    assert part.equipment.weapons == []


def test_make_npc_without_equipment_keeps_none(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "down"})
    part_of(bundle, "g1").equipment = None
    npc = make_npc(bundle, hero_of(bundle), survivor_of(bundle, "g1"), cfg)
    assert npc.equipment is None


def test_make_npc_is_placed_with_the_hero_and_does_not_follow(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "down"})
    npc = make_npc(bundle, hero_of(bundle), survivor_of(bundle, "g1"), cfg)
    assert (npc.location_id, npc.follows) == ("vale", None)


def test_make_npc_attitude_by_kind(registry, cfg):
    bundle = fight(
        registry, cfg, statuses={"g1": "surrendered", "g2": "fled"},
        flags=[("g1", "parley_defected")],
    )
    part_of(bundle, "g1").side = "heroes"
    got = {s.part.ref: make_npc(bundle, hero_of(bundle), s, cfg).attitude
           for s in classify(bundle, hero_of(bundle))}
    assert got == {"g1": cfg.survivors.defected, "g2": cfg.survivors.fled}


def test_make_npc_spared_and_surrendered_attitude(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "down", "g2": "surrendered"})
    got = {s.kind: make_npc(bundle, hero_of(bundle), s, cfg).attitude
           for s in classify(bundle, hero_of(bundle))}
    assert got == {"spared": 20, "surrendered": 0}


def test_make_npc_fled_lands_in_neighbour(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "fled"})
    npc = make_npc(bundle, hero_of(bundle), survivor_of(bundle, "g1"), cfg)
    assert npc.location_id == "forest"


# remember_fight

def remembered(registry, cfg, status="down", flags=(), scene=True):
    bundle = fight(registry, cfg, statuses={"g1": status}, flags=flags)
    if not scene:
        bundle.session.current_scene = None
    survivor = survivor_of(bundle, "g1")
    npc = make_npc(bundle, hero_of(bundle), survivor, cfg)
    remember_fight(bundle, hero_of(bundle), npc, survivor, cfg)
    return bundle, npc


def test_spared_gets_spared_event(registry, cfg):
    _, npc = remembered(registry, cfg)
    assert name_in_memory(npc) == ["герой пощадил в бою"]
    assert npc.memory[0].events[0].kind == "spared"


def test_surrendered_gets_spared_event(registry, cfg):
    _, npc = remembered(registry, cfg, status="surrendered")
    assert (npc.memory[0].events[0].kind, name_in_memory(npc)) == ("spared", ["сдался герою в бою"])


def test_fled_gets_other_event(registry, cfg):
    _, npc = remembered(registry, cfg, status="fled")
    assert (npc.memory[0].events[0].kind, name_in_memory(npc)) == ("other", ["бежал из боя"])


def test_defected_gets_spared_event_and_life_debt(registry, cfg):
    bundle, npc = remembered(registry, cfg, status="active", flags=[("g1", "parley_defected")])
    assert name_in_memory(npc) == ["перешёл на сторону героя в бою"]
    [goal] = npc.goals
    assert (goal.kind, goal.target, goal.since_s) == (
        "life_debt", "hero", bundle.world.clock.now_s,
    )


def test_non_defected_get_no_goal(registry, cfg):
    for status in ("down", "surrendered", "fled"):
        _, npc = remembered(registry, cfg, status=status)
        assert npc.goals == []


def test_event_belongs_to_current_scene_and_turn(registry, cfg):
    bundle, npc = remembered(registry, cfg)
    assert npc.memory[0].scene_id == bundle.session.current_scene.id
    assert npc.memory[0].events[0].turn_seq == bundle.session.turn_seq


def test_no_scene_means_no_memory(registry, cfg):
    _, npc = remembered(registry, cfg, scene=False)
    assert npc.memory == []


def test_no_scene_still_gives_life_debt_to_defector(registry, cfg):
    _, npc = remembered(
        registry, cfg, status="active", flags=[("g1", "parley_defected")], scene=False,
    )
    assert npc.memory == []
    assert [g.kind for g in npc.goals] == ["life_debt"]


# materialize / note_met

def test_materialize_adds_survivors_to_world(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "down", "g2": "surrendered"})
    created = materialize(bundle, hero_of(bundle), classify(bundle, hero_of(bundle)), cfg)
    assert [n.id for n in created] == ["goblin_warrior_t0_1", "goblin_warrior_t0_2"]
    assert bundle.world.npcs["goblin_warrior_t0_2"] is created[1]


def test_materialize_empty_list_changes_nothing(registry, cfg):
    bundle = fight(registry, cfg)
    before = set(bundle.world.npcs)
    assert materialize(bundle, hero_of(bundle), [], cfg) == []
    assert set(bundle.world.npcs) == before


def test_materialize_numbers_ids_after_existing_survivors(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "down"})
    taken(bundle, "goblin_warrior_t0_1")
    [npc] = materialize(bundle, hero_of(bundle), classify(bundle, hero_of(bundle)), cfg)
    assert npc.id == "goblin_warrior_t0_2"


def test_materialized_id_does_not_collide_with_later_enemy_ref(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "down"})
    [npc] = materialize(bundle, hero_of(bundle), classify(bundle, hero_of(bundle)), cfg)
    assert npc.id not in {"goblin_1", "g1", "g2"}


# группа перебежчика и текст цели

def defected_fight(registry, cfg, group=None):
    bundle = fight(registry, cfg, flags=[("g1", "parley_defected")])
    flag = part_of(bundle, "g1").creature.active_effects[0]
    if group is not None:
        flag.params = {"group": group}
    part_of(bundle, "g1").side = "heroes"
    part_of(bundle, "g1").group_id = "party"
    return bundle


def test_defector_keeps_original_group_from_flag(registry, cfg):
    bundle = defected_fight(registry, cfg, group="goblins")
    [s] = classify(bundle, hero_of(bundle))
    assert s.group == "goblins"
    assert make_npc(bundle, hero_of(bundle), s, cfg).groups == ["goblins"]


def test_defector_group_is_not_the_party_group(registry, cfg):
    bundle = defected_fight(registry, cfg, group="bandits")
    [s] = classify(bundle, hero_of(bundle))
    assert make_npc(bundle, hero_of(bundle), s, cfg).groups == ["bandits"]


def test_defector_without_group_param_falls_back_to_group_id(registry, cfg):
    bundle = defected_fight(registry, cfg)
    [s] = classify(bundle, hero_of(bundle))
    assert s.group == "party"


def test_non_defector_group_is_participant_group(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "down"})
    assert survivor_of(bundle, "g1").group == "goblins"


def test_life_debt_goal_has_engine_text(registry, cfg):
    _, npc = remembered(registry, cfg, status="active", flags=[("g1", "parley_defected")])
    assert npc.goals[0].text == LIFE_DEBT_TEXT


def test_group_of_function_uses_flag_only_for_defected(registry, cfg):
    bundle = defected_fight(registry, cfg, group="goblins")
    part = part_of(bundle, "g1")
    assert group_of(part, "defected") == "goblins"
    assert group_of(part, "spared") == "party"


def test_materialize_writes_memory(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "down"})
    [npc] = materialize(bundle, hero_of(bundle), classify(bundle, hero_of(bundle)), cfg)
    assert name_in_memory(npc) == ["герой пощадил в бою"]


def test_materialize_writes_meeting_by_label(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "down"})
    [npc] = materialize(bundle, hero_of(bundle), classify(bundle, hero_of(bundle)), cfg)
    [entry] = [e for e in hero_of(bundle).knowledge if e.kind == "npc"]
    assert (entry.ref, entry.text, entry.source) == (npc.id, "Знакомство: Воин-гоблин 1", "seen")
    assert entry.at_s == bundle.world.clock.now_s


def test_note_met_does_not_duplicate(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "down"})
    [npc] = materialize(bundle, hero_of(bundle), classify(bundle, hero_of(bundle)), cfg)
    note_met(bundle, hero_of(bundle), npc, cfg)
    assert len([e for e in hero_of(bundle).knowledge if e.kind == "npc"]) == 1


def test_note_met_never_writes_the_real_name(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "down"})
    [npc] = materialize(bundle, hero_of(bundle), classify(bundle, hero_of(bundle)), cfg)
    npc.name = "Гракх"
    other = NPC(
        id="x", name="Гракх", means=["бой"], origin="engine", combat={"label": "Воин-гоблин 1"}
    )
    note_met(bundle, hero_of(bundle), other, cfg)
    assert all("Гракх" not in e.text for e in hero_of(bundle).knowledge)


# reveal_names

def hidden_npc(name="Гракх", **kwargs):
    base = {
        "id": "goblin_warrior_1", "name": name, "origin": "engine", "location_id": "vale",
        "means": ["бой"],
        "combat": {"monster_id": "goblin_warrior", "label": "Воин-гоблин 1"},
    }
    return NPC(**{**base, **kwargs})


def world_with(registry, cfg, npc):
    bundle = fight(registry, cfg)
    bundle.world.npcs[npc.id] = npc
    return bundle


def test_spoken_name_opens_known_name(registry, cfg):
    npc = hidden_npc()
    bundle = world_with(registry, cfg, npc)
    reveal_names(hero_of(bundle), bundle.world, "Гракх опускает взгляд.")
    assert npc.known_name == "Гракх"


def test_name_is_found_case_insensitively_with_ending(registry, cfg):
    npc = hidden_npc()
    bundle = world_with(registry, cfg, npc)
    reveal_names(hero_of(bundle), bundle.world, "Ты слышишь, как ГРАКХу страшно.")
    assert npc.known_name == "Гракх"


def test_unspoken_name_stays_hidden(registry, cfg):
    npc = hidden_npc()
    bundle = world_with(registry, cfg, npc)
    reveal_names(hero_of(bundle), bundle.world, "Гоблин опускает взгляд.")
    assert npc.known_name is None


def test_name_of_npc_elsewhere_is_not_opened(registry, cfg):
    npc = hidden_npc(location_id="forest")
    bundle = world_with(registry, cfg, npc)
    reveal_names(hero_of(bundle), bundle.world, "Гракх далеко.")
    assert npc.known_name is None


def test_following_npc_elsewhere_is_opened(registry, cfg):
    npc = hidden_npc(location_id="forest", follows="hero")
    bundle = world_with(registry, cfg, npc)
    reveal_names(hero_of(bundle), bundle.world, "Гракх идёт рядом.")
    assert npc.known_name == "Гракх"


def test_dead_npc_name_is_not_opened(registry, cfg):
    npc = hidden_npc(status="dead")
    bundle = world_with(registry, cfg, npc)
    reveal_names(hero_of(bundle), bundle.world, "Гракх лежит.")
    assert npc.known_name is None


def test_name_equal_to_label_is_not_a_reveal(registry, cfg):
    npc = hidden_npc(name="Воин-гоблин 1")
    bundle = world_with(registry, cfg, npc)
    reveal_names(hero_of(bundle), bundle.world, "Воин-гоблин 1 молчит.")
    assert npc.known_name is None


def test_pack_npc_is_not_touched(registry, cfg):
    npc = hidden_npc(origin="pack")
    bundle = world_with(registry, cfg, npc)
    reveal_names(hero_of(bundle), bundle.world, "Гракх кивает.")
    assert npc.known_name is None


def test_already_known_name_is_kept(registry, cfg):
    npc = hidden_npc(known_name="Старое")
    bundle = world_with(registry, cfg, npc)
    reveal_names(hero_of(bundle), bundle.world, "Гракх кивает.")
    assert npc.known_name == "Старое"


def test_short_name_is_not_found_inside_longer_word(registry, cfg):
    npc = hidden_npc(name="Ян")
    bundle = world_with(registry, cfg, npc)
    reveal_names(hero_of(bundle), bundle.world, "Яндекс молчит.")
    assert npc.known_name is None


def test_reveal_renames_meeting_entry(registry, cfg):
    bundle = fight(registry, cfg, statuses={"g1": "down"})
    [npc] = materialize(bundle, hero_of(bundle), classify(bundle, hero_of(bundle)), cfg)
    npc.name = "Гракх"
    reveal_names(hero_of(bundle), bundle.world, "Гракх опускает взгляд.")
    [entry] = [e for e in hero_of(bundle).knowledge if e.kind == "npc"]
    assert entry.text == "Знакомство: Гракх"


def test_reveal_opens_each_spoken_name_only(registry, cfg):
    first = hidden_npc()
    second = hidden_npc(name="Мурк", id="goblin_warrior_2")
    bundle = world_with(registry, cfg, first)
    bundle.world.npcs[second.id] = second
    reveal_names(hero_of(bundle), bundle.world, "Мурк смотрит.")
    assert (first.known_name, second.known_name) == (None, "Мурк")
