# Зоны (шаг 15, ТЗ 7). Ожидаемый API (модели -- см. шапку combat_kit.py):
#   ai_dm.combat.setup
#     validate_start(state: CombatState) -> list[str]   -- коды ошибок, [] = старт корректен;
#         все найденные ошибки, а не только первая (как validate_background):
#         zones_count (не 2..5 зон), zone_ids_duplicate, zone_names_duplicate,
#         graph_unknown_zone (adjacent ссылается на несуществующую зону),
#         graph_asymmetric (a видит b, а b не видит a), graph_disconnected,
#         participant_duplicate, participant_unplaced (zone_id None),
#         participant_zone_unknown, group_unknown (group_id нет в groups),
#         group_intent_missing (у группы врагов нет intent; у группы героев он не нужен),
#         group_leader_invalid (лидер не участник этой группы)
#     CombatSetupError(ValueError) с .codes; CombatEngine(...) бросает её при плохом старте
#   ai_dm.combat.zones
#     distance(zones: list[Zone], a_id, b_id) -> int
#         -- BFS по adjacent; неизвестная зона -> ValueError
#     range_band_ft(steps: int) -> int                     -- 0 -> 10, 1 -> 30, 2 и больше -> 120
#         (None не принимается, константы OUT_OF_FIELD_FT нет: расстояние всегда посчитано по графу)
#     cover_dc_bonus(zone: Zone) -> int
#         -- cover_half +2, cover_three_quarters +5 (больший, не сумма) -- dc_bonus конвейера (D1)
#     is_difficult(zone: Zone) -> bool
#   Механика зон в бою (через CombatEngine, броски -- ScriptedRng):
#     укрытие -- в КД цели при атаке из другой зоны (в логе "против КД 17");
#       в одной зоне укрытия нет;
#       то же укрытие (+2 / +5) прибавляется к спасброску ЛОВ существа в зоне укрытия против
#       источника (заклинание-площадь) из ДРУГОЙ зоны; Dodge даёт преимущество на спасброски ЛОВ;
#     difficult -- вход тратит всё перемещение хода (после рывка вторая зона недоступна);
#     hazard -- при входе в зону и в начале хода стоящего в ней: спасбросок save против dc,
#       при провале урон damage целиком, при успехе без урона.
import pytest
from combat_kit import (
    ScriptedRng,
    feature,
    give_weapon,
    hp,
    make_engine,
    make_fighter,
    make_zones,
    mon,
    option_ids,
    part,
    turn,
)
from pydantic import ValidationError

from ai_dm.combat.controllers import ScriptedController
from ai_dm.combat.engine import CombatEngine
from ai_dm.combat.setup import CombatSetupError, validate_start
from ai_dm.combat.zones import cover_dc_bonus, distance, is_difficult, range_band_ft
from ai_dm.state.combat import CombatState, Group, Participant, Zone, ZoneFeature


def zone(zone_id, adjacent, name=None):
    return Zone(id=zone_id, name=name or zone_id, adjacent=adjacent)


def make_state(zones=None, participants=None, groups=None):
    if zones is None:
        zones = make_zones()
    if participants is None:
        participants = [
            Participant(ref="hero", side="heroes", group_id="party", zone_id="door"),
            Participant(ref="goblin_1", side="enemies", group_id="goblins", zone_id="hall"),
            Participant(ref="goblin_2", side="enemies", group_id="goblins", zone_id="hall"),
        ]
    if groups is None:
        groups = {
            "party": Group(leader_id="hero"),
            "goblins": Group(leader_id="goblin_1", intent="kill"),
        }
    return CombatState(id="c1", zones=zones, participants=participants, groups=groups)


def ring():
    # a - b - c - d - a
    return [
        zone("a", ["b", "d"]), zone("b", ["a", "c"]), zone("c", ["b", "d"]), zone("d", ["c", "a"]),
    ]


# валидация старта

def test_valid_start_has_no_errors():
    assert validate_start(make_state()) == []


def test_one_zone_is_rejected():
    state = make_state(
        zones=[zone("only", [])],
        participants=[
            Participant(ref="hero", side="heroes", group_id="party", zone_id="only"),
            Participant(ref="goblin_1", side="enemies", group_id="goblins", zone_id="only"),
        ],
    )
    assert "zones_count" in validate_start(state)


def test_six_zones_are_rejected():
    names = ["z1", "z2", "z3", "z4", "z5", "z6"]
    zones = []
    for i, name in enumerate(names):
        near = [names[j] for j in (i - 1, i + 1) if 0 <= j < len(names)]
        zones.append(zone(name, near))
    state = make_state(
        zones=zones,
        participants=[
            Participant(ref="hero", side="heroes", group_id="party", zone_id="z1"),
            Participant(ref="goblin_1", side="enemies", group_id="goblins", zone_id="z6"),
        ],
    )
    assert "zones_count" in validate_start(state)


def test_two_and_five_zones_are_allowed():
    two = make_state(
        zones=[zone("a", ["b"]), zone("b", ["a"])],
        participants=[
            Participant(ref="hero", side="heroes", group_id="party", zone_id="a"),
            Participant(ref="goblin_1", side="enemies", group_id="goblins", zone_id="b"),
        ],
    )
    names = ["z1", "z2", "z3", "z4", "z5"]
    zones = []
    for i, name in enumerate(names):
        near = [names[j] for j in (i - 1, i + 1) if 0 <= j < len(names)]
        zones.append(zone(name, near))
    five = make_state(
        zones=zones,
        participants=[
            Participant(ref="hero", side="heroes", group_id="party", zone_id="z1"),
            Participant(ref="goblin_1", side="enemies", group_id="goblins", zone_id="z5"),
        ],
    )
    assert validate_start(two) == []
    assert validate_start(five) == []


def test_duplicate_zone_names_are_rejected():
    zones = [zone("a", ["b"], name="Зал"), zone("b", ["a"], name="Зал")]
    state = make_state(
        zones=zones,
        participants=[
            Participant(ref="hero", side="heroes", group_id="party", zone_id="a"),
            Participant(ref="goblin_1", side="enemies", group_id="goblins", zone_id="b"),
        ],
    )
    assert "zone_names_duplicate" in validate_start(state)


def test_duplicate_zone_ids_are_rejected():
    zones = [zone("a", ["a"], name="Один"), zone("a", ["a"], name="Два")]
    state = make_state(
        zones=zones,
        participants=[
            Participant(ref="hero", side="heroes", group_id="party", zone_id="a"),
            Participant(ref="goblin_1", side="enemies", group_id="goblins", zone_id="a"),
        ],
    )
    assert "zone_ids_duplicate" in validate_start(state)


def test_asymmetric_graph_is_rejected():
    zones = [zone("a", ["b"]), zone("b", []), zone("c", ["b"])]
    state = make_state(zones=zones, participants=[
        Participant(ref="hero", side="heroes", group_id="party", zone_id="a"),
        Participant(ref="goblin_1", side="enemies", group_id="goblins", zone_id="c"),
    ])
    assert "graph_asymmetric" in validate_start(state)


def test_adjacency_to_unknown_zone_is_rejected():
    zones = [zone("a", ["b", "ghost"]), zone("b", ["a"])]
    state = make_state(zones=zones, participants=[
        Participant(ref="hero", side="heroes", group_id="party", zone_id="a"),
        Participant(ref="goblin_1", side="enemies", group_id="goblins", zone_id="b"),
    ])
    assert "graph_unknown_zone" in validate_start(state)


def test_disconnected_graph_is_rejected():
    zones = [zone("a", ["b"]), zone("b", ["a"]), zone("c", ["d"]), zone("d", ["c"])]
    state = make_state(zones=zones, participants=[
        Participant(ref="hero", side="heroes", group_id="party", zone_id="a"),
        Participant(ref="goblin_1", side="enemies", group_id="goblins", zone_id="d"),
    ])
    assert "graph_disconnected" in validate_start(state)


def test_unplaced_participant_is_rejected():
    participants = [
        Participant(ref="hero", side="heroes", group_id="party", zone_id="door"),
        Participant(ref="goblin_1", side="enemies", group_id="goblins"),
    ]
    assert "participant_unplaced" in validate_start(make_state(participants=participants))


def test_participant_in_unknown_zone_is_rejected():
    participants = [
        Participant(ref="hero", side="heroes", group_id="party", zone_id="door"),
        Participant(ref="goblin_1", side="enemies", group_id="goblins", zone_id="roof"),
    ]
    assert "participant_zone_unknown" in validate_start(make_state(participants=participants))


def test_duplicate_participant_refs_are_rejected():
    participants = [
        Participant(ref="hero", side="heroes", group_id="party", zone_id="door"),
        Participant(ref="goblin_1", side="enemies", group_id="goblins", zone_id="hall"),
        Participant(ref="goblin_1", side="enemies", group_id="goblins", zone_id="hall"),
    ]
    assert "participant_duplicate" in validate_start(make_state(participants=participants))


def test_participant_with_unknown_group_is_rejected():
    participants = [
        Participant(ref="hero", side="heroes", group_id="party", zone_id="door"),
        Participant(ref="goblin_1", side="enemies", group_id="orcs", zone_id="hall"),
    ]
    assert "group_unknown" in validate_start(make_state(participants=participants))


def test_enemy_group_without_intent_is_rejected():
    groups = {"party": Group(leader_id="hero"), "goblins": Group(leader_id="goblin_1")}
    assert "group_intent_missing" in validate_start(make_state(groups=groups))


def test_hero_group_does_not_need_intent():
    assert "group_intent_missing" not in validate_start(make_state())


def test_leader_outside_the_group_is_rejected():
    groups = {
        "party": Group(leader_id="hero"),
        "goblins": Group(leader_id="hero", intent="kill"),
    }
    assert "group_leader_invalid" in validate_start(make_state(groups=groups))


def test_leader_who_is_not_a_participant_is_rejected():
    groups = {
        "party": Group(leader_id="hero"),
        "goblins": Group(leader_id="goblin_9", intent="kill"),
    }
    assert "group_leader_invalid" in validate_start(make_state(groups=groups))


def test_all_errors_are_reported_together():
    groups = {"party": Group(leader_id="hero"), "goblins": Group(leader_id="goblin_1")}
    state = make_state(zones=[zone("only", [])], groups=groups)
    codes = validate_start(state)
    assert "zones_count" in codes
    assert "group_intent_missing" in codes


def test_engine_refuses_to_start_on_invalid_state(registry, cfg):
    with pytest.raises(CombatSetupError) as error:
        make_engine(registry, cfg, heroes=[make_fighter(registry)], monsters=[
            mon("goblin_1", "goblin_warrior", "hall"),
        ], zones=[zone("only", [])])
    assert "zones_count" in error.value.codes


def test_engine_constructor_does_not_change_the_state(registry, cfg):
    engine = make_engine(registry, cfg, heroes=[make_fighter(registry)], monsters=[
        mon("goblin_1", "goblin_warrior", "hall"),
    ], started=False)
    before = engine.state.model_dump_json()
    again = CombatEngine(
        engine.state, engine.world, engine.heroes, registry, cfg, ScriptedRng()
    )
    assert again.state.model_dump_json() == before


# дистанции и полосы

def test_distance_in_same_zone_is_zero():
    assert distance(make_zones(), "hall", "hall") == 0


def test_distance_to_neighbour_is_one():
    assert distance(make_zones(), "door", "hall") == 1


def test_distance_across_one_zone_is_two():
    assert distance(make_zones(), "door", "balcony") == 2


def test_distance_is_symmetric():
    zones = make_zones()
    assert distance(zones, "balcony", "door") == distance(zones, "door", "balcony")


def test_distance_goes_around_the_ring():
    assert distance(ring(), "a", "c") == 2
    assert distance(ring(), "a", "d") == 1


def test_distance_with_unknown_zone_raises():
    with pytest.raises(ValueError):
        distance(make_zones(), "door", "roof")


def test_band_for_same_zone_is_10_ft():
    assert range_band_ft(0) == 10


def test_band_for_neighbour_is_30_ft():
    assert range_band_ft(1) == 30


def test_band_for_two_and_more_is_120_ft():
    assert range_band_ft(2) == 120
    assert range_band_ft(3) == 120


# особенности зон

def test_plain_zone_has_no_cover():
    assert cover_dc_bonus(make_zones()[1]) == 0


def test_half_cover_gives_plus_2():
    assert cover_dc_bonus(make_zones(balcony=[feature("cover_half")])[2]) == 2


def test_three_quarters_cover_gives_plus_5():
    zones = make_zones(balcony=[feature("cover_three_quarters")])
    assert cover_dc_bonus(zones[2]) == 5


def test_two_covers_do_not_add_up():
    zones = make_zones(balcony=[feature("cover_half"), feature("cover_three_quarters")])
    assert cover_dc_bonus(zones[2]) == 5


def test_difficult_zone_is_detected():
    zones = make_zones(hall=[feature("difficult")])
    assert is_difficult(zones[1])
    assert not is_difficult(zones[0])


def test_unknown_feature_kind_is_allowed_and_has_no_mechanics():
    zones = make_zones(hall=[feature("chandelier")])
    assert cover_dc_bonus(zones[1]) == 0
    assert not is_difficult(zones[1])


def test_hazard_needs_damage_and_save():
    with pytest.raises(ValidationError):
        ZoneFeature(kind="hazard")
    with pytest.raises(ValidationError):
        ZoneFeature(kind="hazard", damage="1d6")


def test_feature_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ZoneFeature(kind="cover_half", bogus=1)


# укрытие в бою: лучник-герой в зале стреляет по гоблинам из соседних зон

def archer_engine(registry, cfg, zones, rng):
    hero = make_fighter(registry)
    give_weapon(hero, registry, "shortbow")
    return make_engine(
        registry, cfg, heroes=[hero], zones=zones, rng=rng,
        monsters=[mon("goblin_door", "goblin_warrior", "door"),
                  mon("goblin_balcony", "goblin_warrior", "balcony")],
    )


def test_half_cover_adds_2_to_ac_in_the_log(registry, cfg):
    engine = archer_engine(
        registry, cfg, make_zones(balcony=[feature("cover_half")]), ScriptedRng(d20=[13])
    )
    engine.perform("hero", "attack:shortbow:goblin_balcony")
    assert any("против КД 17" in line for line in engine.state.log)


def test_half_cover_turns_a_hit_into_a_miss(registry, cfg):
    # 13 + 3 = 16: попадание по КД 15, промах по КД 17
    engine = archer_engine(
        registry, cfg, make_zones(balcony=[feature("cover_half")]), ScriptedRng(d20=[13])
    )
    engine.perform("hero", "attack:shortbow:goblin_balcony")
    assert hp(engine, "goblin_balcony") == 10


def test_same_roll_hits_a_target_without_cover(registry, cfg):
    engine = archer_engine(
        registry, cfg, make_zones(balcony=[feature("cover_half")]),
        ScriptedRng(d20=[13], d6=[4]),
    )
    engine.perform("hero", "attack:shortbow:goblin_door")
    assert hp(engine, "goblin_door") < 10


def test_three_quarters_cover_adds_5_to_ac(registry, cfg):
    engine = archer_engine(
        registry, cfg, make_zones(balcony=[feature("cover_three_quarters")]),
        ScriptedRng(d20=[10]),
    )
    engine.perform("hero", "attack:shortbow:goblin_balcony")
    assert any("против КД 20" in line for line in engine.state.log)


def test_cover_does_not_apply_in_the_same_zone(registry, cfg):
    hero = make_fighter(registry)
    engine = make_engine(
        registry, cfg, heroes=[(hero, "balcony")],
        zones=make_zones(balcony=[feature("cover_half")]), rng=ScriptedRng(d20=[10], d8=[4]),
        monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    engine.perform("hero", "attack:longsword:goblin_1")
    assert any("против КД 15" in line for line in engine.state.log)


# difficult

def test_difficult_zone_ends_the_movement(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "door")],
        zones=make_zones(hall=[feature("difficult")]),
        monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    engine.perform("hero", "dash")
    engine.perform("hero", "move:hall")
    assert not any(i.startswith("move:") for i in option_ids(engine, "hero"))
    assert turn(engine, "hero").move == 0


def test_dash_through_plain_zone_gives_two_zones(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "door")],
        monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    engine.perform("hero", "dash")
    engine.perform("hero", "move:hall")
    assert "move:balcony" in option_ids(engine, "hero")
    engine.perform("hero", "move:balcony")
    assert part(engine, "hero").zone_id == "balcony"


def test_difficult_zone_can_still_be_entered_with_one_move(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "door")],
        zones=make_zones(hall=[feature("difficult")]),
        monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    engine.perform("hero", "move:hall")
    assert part(engine, "hero").zone_id == "hall"


# hazard

def hazard_zones():
    return make_zones(hall=[feature("hazard", damage="1d6", damage_type="fire", save="dex", dc=12)])


def hazard_engine(registry, cfg, rng, zone_id="door"):
    return make_engine(
        registry, cfg, heroes=[(make_fighter(registry), zone_id)], zones=hazard_zones(), rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )


def test_failed_save_on_entering_hazard_deals_damage(registry, cfg):
    # d20 5 + ЛОВ 1 = 6 < 12
    engine = hazard_engine(registry, cfg, ScriptedRng(d20=[5], d6=[4]))
    engine.perform("hero", "move:hall")
    assert hp(engine, "hero") == 8


def test_passed_save_on_entering_hazard_deals_no_damage(registry, cfg):
    rng = ScriptedRng(d20=[15], d6=[4])
    engine = hazard_engine(registry, cfg, rng)
    engine.perform("hero", "move:hall")
    assert hp(engine, "hero") == 12
    assert rng.left("d6") == 1


def test_hazard_hits_at_the_start_of_the_turn(registry, cfg):
    controllers = {"hero": ScriptedController([])}
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "hall")], zones=hazard_zones(),
        rng=ScriptedRng(d20=[5], d6=[3]), controllers=controllers,
        monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    engine.step()
    assert hp(engine, "hero") == 9


def test_no_hazard_roll_for_participant_outside_the_zone(registry, cfg):
    controllers = {"hero": ScriptedController([])}
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "door")], zones=hazard_zones(),
        rng=ScriptedRng(), controllers=controllers,
        monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    engine.step()
    assert hp(engine, "hero") == 12


def test_hazard_hits_monsters_too(registry, cfg):
    # гоблин: ЛОВ +2, d20 3 + 2 = 5 < 12
    controllers = {"goblin_1": ScriptedController([])}
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "door")], zones=hazard_zones(),
        rng=ScriptedRng(d20=[3], d6=[5]), controllers=controllers,
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    engine.state.initiative_order = ["goblin_1", "hero"]
    engine.step()
    assert hp(engine, "goblin_1") == 5
