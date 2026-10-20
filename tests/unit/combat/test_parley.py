# Переговоры в бою (партия «parley», docs/plan-combat-parley.md + ответы проектировщика):
#   CombatEngine.parley(ref, *, skill, outcome, target) -> list[DomainEvent] | Rejected
#   combat.actions.parley.parley_dc(engine, ref, target, skill, outcome) -> (dc, mode, parts)
#     mode -- "disadvantage" (безымянный монстр, NPC с отношением <= -30) или "normal"
#   Навык: intimidation (surrender, flee) / persuasion (surrender, flee, defect) /
#   deception (flee, waver, quarrel).
#   СЛ: 15 или Инт цели; -2 при HP <= 50%, -5 при <= 25%; -3 выбыла половина группы, ещё -3 выбыл
#   лидер; -2 перевес героев (только Запугивание); defect +5; waver -2;
#   ключевой NPC +5, defect запрещён;
#   NPC с отношением >= 30 -- -5. Исходы: surrender -- status "surrendered", flee -- "fled",
#   defect -- side "heroes", waver -- пропуск одного хода. Одна попытка на цель
#   (ActiveEffect id "parley_tried"). Все числа -- cfg.parley (defaults.toml).
# Бонусы героя-воина: Убеждение +1, Запугивание +3, Обман +1.
import pytest
from combat_kit import (
    ScriptedRng,
    bite,
    creature,
    custom_registry,
    hp,
    make_engine,
    make_fighter,
    mon,
    option_ids,
    part,
    set_hp,
    turn,
)

from ai_dm.combat.actions.parley import FLAG_IDS, parley_dc
from ai_dm.config.settings import load_rules_config
from ai_dm.rules.names import SKILL_NAMES
from ai_dm.rules.results import Rejected
from ai_dm.state.combat import CombatState, Zone
from ai_dm.state.creature import ActiveEffect

# две кости при помехе: оба d20 берутся из очереди
PASS = [19, 19]
FAIL = [2, 2]


def duel(registry, cfg, rng=None, goblins=1, named=False, hero_zone="hall", goblin_zone="hall"):
    monsters = [mon(f"goblin_{i}", "goblin_warrior", goblin_zone, named=named)
                for i in range(1, goblins + 1)]
    return make_engine(
        registry, cfg, heroes=[(make_fighter(registry), hero_zone)], monsters=monsters,
        rng=rng or ScriptedRng(),
    )


def talk(engine, skill="persuasion", outcome="surrender", target="goblin_1"):
    return engine.parley("hero", skill=skill, outcome=outcome, target=target)


def dc_of(engine, skill="persuasion", outcome="surrender", target="goblin_1"):
    return parley_dc(engine, "hero", target, skill, outcome)


def effect_ids(engine, ref):
    return [e.id for e in creature(engine, ref).active_effects]


# --- СЛ ---

def test_base_dc_is_fifteen(registry, cfg):
    assert dc_of(duel(registry, cfg))[0] == 15


def test_high_intelligence_of_target_becomes_the_dc(registry, cfg, monkeypatch):
    monkeypatch.setitem(registry.get("monster", "goblin_warrior").abilities, "int", 18)
    assert dc_of(duel(registry, cfg))[0] == 18


def test_intelligence_below_base_does_not_lower_the_dc(registry, cfg, monkeypatch):
    monkeypatch.setitem(registry.get("monster", "goblin_warrior").abilities, "int", 15)
    assert dc_of(duel(registry, cfg))[0] == 15


def test_half_hp_lowers_the_dc_by_two(registry, cfg):
    engine = duel(registry, cfg)
    set_hp(engine, "goblin_1", 5)
    assert dc_of(engine)[0] == 13


def test_more_than_half_hp_does_not_lower_the_dc(registry, cfg):
    engine = duel(registry, cfg)
    set_hp(engine, "goblin_1", 6)
    assert dc_of(engine)[0] == 15


def test_quarter_hp_lowers_the_dc_by_five(registry, cfg):
    engine = duel(registry, cfg)
    set_hp(engine, "goblin_1", 2)
    assert dc_of(engine)[0] == 10


def test_just_over_quarter_hp_lowers_the_dc_by_two_only(registry, cfg):
    engine = duel(registry, cfg)
    set_hp(engine, "goblin_1", 3)
    assert dc_of(engine)[0] == 13


def test_half_of_the_group_out_lowers_the_dc_by_three(registry, cfg):
    # лидер -- goblin_1, выбывает второй из двух (половина группы); лидер на ногах
    engine = duel(registry, cfg, goblins=2)
    part(engine, "goblin_2").status = "dead"
    assert dc_of(engine)[0] == 12


def test_less_than_half_of_the_group_out_keeps_the_dc(registry, cfg):
    engine = duel(registry, cfg, goblins=3)
    part(engine, "goblin_3").status = "dead"
    assert dc_of(engine, target="goblin_2")[0] == 15


def test_fled_and_down_also_count_as_losses(registry, cfg):
    engine = duel(registry, cfg, goblins=4)
    part(engine, "goblin_3").status = "fled"
    part(engine, "goblin_4").status = "down"
    assert dc_of(engine, target="goblin_2")[0] == 12


def test_group_leader_out_lowers_the_dc_by_three_more(registry, cfg):
    engine = duel(registry, cfg, goblins=2)
    part(engine, "goblin_1").status = "dead"
    assert dc_of(engine, target="goblin_2")[0] == 9


def test_leader_out_in_a_big_group_lowers_the_dc_by_three_only(registry, cfg):
    engine = duel(registry, cfg, goblins=4)
    part(engine, "goblin_1").status = "dead"
    assert dc_of(engine, target="goblin_2")[0] == 12


def test_unnamed_monster_is_hostile_and_rolls_with_disadvantage(registry, cfg):
    assert dc_of(duel(registry, cfg))[1] == "disadvantage"


def test_friendly_named_npc_gets_minus_five_without_disadvantage(registry, cfg):
    engine = duel(registry, cfg, named=True)
    engine.world.npcs["goblin_1"].attitude = 40
    dc, mode, _ = dc_of(engine)
    assert (dc, mode) == (10, "normal")


def test_friendly_threshold_is_included(registry, cfg):
    engine = duel(registry, cfg, named=True)
    engine.world.npcs["goblin_1"].attitude = 30
    assert dc_of(engine)[0] == 10


def test_indifferent_named_npc_has_plain_dc_and_no_disadvantage(registry, cfg):
    engine = duel(registry, cfg, named=True)
    engine.world.npcs["goblin_1"].attitude = 29
    dc, mode, _ = dc_of(engine)
    assert (dc, mode) == (15, "normal")


def test_hostile_threshold_is_included(registry, cfg):
    engine = duel(registry, cfg, named=True)
    engine.world.npcs["goblin_1"].attitude = -30
    assert dc_of(engine)[1] == "disadvantage"


def test_just_above_hostile_threshold_is_normal(registry, cfg):
    engine = duel(registry, cfg, named=True)
    engine.world.npcs["goblin_1"].attitude = -29
    assert dc_of(engine)[1] == "normal"


def test_hostile_named_npc_rolls_with_disadvantage(registry, cfg):
    engine = duel(registry, cfg, named=True)
    engine.world.npcs["goblin_1"].attitude = -50
    dc, mode, _ = dc_of(engine)
    assert (dc, mode) == (15, "disadvantage")


def test_defect_adds_five(registry, cfg):
    assert dc_of(duel(registry, cfg), outcome="defect")[0] == 20


def test_waver_subtracts_two(registry, cfg):
    assert dc_of(duel(registry, cfg), skill="deception", outcome="waver")[0] == 13


def test_key_npc_adds_five_to_surrender(registry, cfg):
    engine = duel(registry, cfg, named=True)
    engine.world.npcs["goblin_1"].key = True
    assert dc_of(engine)[0] == 20


def test_key_npc_adds_five_to_flee(registry, cfg):
    engine = duel(registry, cfg, named=True)
    engine.world.npcs["goblin_1"].key = True
    assert dc_of(engine, skill="deception", outcome="flee")[0] == 20


def test_non_key_named_npc_has_no_key_bonus(registry, cfg):
    engine = duel(registry, cfg, named=True)
    assert dc_of(engine)[0] == 15


def test_key_npc_cannot_be_talked_into_defecting(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(), named=True)
    engine.world.npcs["goblin_1"].key = True
    result = talk(engine, outcome="defect")
    assert isinstance(result, Rejected)
    assert turn(engine, "hero").action is True


def test_overwhelming_heroes_lower_intimidation_dc_by_two(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry), make_fighter(registry, "ally")],
        monsters=[mon("goblin_1", "goblin_warrior", "hall")], rng=ScriptedRng(),
    )
    assert dc_of(engine, skill="intimidation")[0] == 13


def test_overwhelm_does_not_help_persuasion(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry), make_fighter(registry, "ally")],
        monsters=[mon("goblin_1", "goblin_warrior", "hall")], rng=ScriptedRng(),
    )
    assert dc_of(engine, skill="persuasion")[0] == 15


def test_equal_numbers_do_not_lower_intimidation_dc(registry, cfg):
    assert dc_of(duel(registry, cfg), skill="intimidation")[0] == 15


def test_two_heroes_against_two_enemies_do_not_lower_intimidation_dc(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry), make_fighter(registry, "ally")],
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "hall")], rng=ScriptedRng(),
    )
    assert dc_of(engine, skill="intimidation")[0] == 15


def test_dc_parts_are_returned_for_the_log(registry, cfg):
    engine = duel(registry, cfg)
    set_hp(engine, "goblin_1", 2)
    assert len(dc_of(engine)[2]) >= 2


# --- ограничения: отказ без траты действия ---

def assert_refused(engine, result):
    assert isinstance(result, Rejected)
    assert turn(engine, "hero").action is True
    assert engine.rng.calls == []


def test_mindless_target_is_refused(registry, cfg, monkeypatch):
    monkeypatch.setitem(registry.get("monster", "goblin_warrior").abilities, "int", 3)
    engine = duel(registry, cfg)
    result = talk(engine)
    assert_refused(engine, result)
    assert result.reason == "not_sentient"


def test_int_four_is_sentient(registry, cfg, monkeypatch):
    monkeypatch.setitem(registry.get("monster", "goblin_warrior").abilities, "int", 4)
    engine = duel(registry, cfg, ScriptedRng(d20=PASS))
    assert not isinstance(talk(engine), Rejected)


@pytest.mark.parametrize("kind", ["construct", "ooze", "plant"])
def test_immune_creature_type_is_refused(registry, cfg, monkeypatch, kind):
    monkeypatch.setattr(registry.get("monster", "goblin_warrior"), "creature_type", kind)
    engine = duel(registry, cfg)
    result = talk(engine)
    assert_refused(engine, result)
    assert result.reason == "not_sentient"


def test_sentient_undead_can_be_talked_to(registry, cfg, monkeypatch):
    monkeypatch.setattr(registry.get("monster", "goblin_warrior"), "creature_type", "undead")
    engine = duel(registry, cfg, ScriptedRng(d20=PASS))
    assert not isinstance(talk(engine), Rejected)


@pytest.mark.parametrize("status", ["down", "dead", "fled", "surrendered"])
def test_inactive_target_is_refused(registry, cfg, status):
    engine = duel(registry, cfg)
    part(engine, "goblin_1").status = status
    assert_refused(engine, talk(engine))


def test_target_in_a_far_zone_is_refused(registry, cfg):
    engine = duel(registry, cfg, hero_zone="door", goblin_zone="balcony")
    assert_refused(engine, talk(engine))


def test_target_in_a_neighbour_zone_can_hear(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS), hero_zone="door", goblin_zone="hall")
    assert not isinstance(talk(engine), Rejected)


def test_second_attempt_on_the_same_target_is_refused(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=FAIL))
    talk(engine)
    turn(engine, "hero").action = True
    result = talk(engine)
    assert isinstance(result, Rejected)
    assert turn(engine, "hero").action is True


def test_attempt_flag_stays_on_the_target_after_a_failure(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=FAIL))
    talk(engine)
    assert "parley_tried" in effect_ids(engine, "goblin_1")


def test_another_target_is_not_blocked_by_the_first_attempt(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=FAIL + FAIL), goblins=2)
    talk(engine)
    turn(engine, "hero").action = True
    assert not isinstance(talk(engine, target="goblin_2"), Rejected)


def test_no_action_left_is_refused(registry, cfg):
    engine = duel(registry, cfg)
    turn(engine, "hero").action = False
    assert isinstance(talk(engine), Rejected)
    assert engine.rng.calls == []


def test_unknown_target_is_refused(registry, cfg):
    engine = duel(registry, cfg)
    assert_refused(engine, talk(engine, target="nobody"))


def test_ally_target_is_refused(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry), make_fighter(registry, "ally")],
        monsters=[mon("goblin_1", "goblin_warrior", "hall")], rng=ScriptedRng(),
    )
    assert_refused(engine, talk(engine, target="ally"))


def test_intimidation_cannot_make_a_defector(registry, cfg):
    engine = duel(registry, cfg)
    result = talk(engine, skill="intimidation", outcome="defect")
    assert_refused(engine, result)
    assert result.reason == "outcome_not_allowed"


def test_deception_cannot_make_a_target_surrender(registry, cfg):
    engine = duel(registry, cfg)
    result = talk(engine, skill="deception", outcome="surrender")
    assert_refused(engine, result)
    assert result.reason == "outcome_not_allowed"


def test_persuasion_cannot_make_a_target_waver(registry, cfg):
    engine = duel(registry, cfg)
    assert talk(engine, skill="persuasion", outcome="waver").reason == "outcome_not_allowed"


def test_deception_cannot_make_a_defector(registry, cfg):
    engine = duel(registry, cfg)
    assert talk(engine, skill="deception", outcome="defect").reason == "outcome_not_allowed"


def test_intimidation_cannot_make_a_target_waver(registry, cfg):
    engine = duel(registry, cfg)
    assert talk(engine, skill="intimidation", outcome="waver").reason == "outcome_not_allowed"


def test_deception_can_make_a_target_quarrel(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS), goblins=2)
    assert not isinstance(talk(engine, skill="deception", outcome="quarrel"), Rejected)


@pytest.mark.parametrize("skill", ["intimidation", "persuasion"])
def test_other_skills_cannot_make_a_target_quarrel(registry, cfg, skill):
    engine = duel(registry, cfg, goblins=2)
    result = talk(engine, skill=skill, outcome="quarrel")
    assert_refused(engine, result)
    assert result.reason == "outcome_not_allowed"


def test_unknown_skill_is_refused(registry, cfg):
    engine = duel(registry, cfg)
    assert isinstance(talk(engine, skill="athletics"), Rejected)


def test_only_a_hero_can_parley(registry, cfg):
    engine = duel(registry, cfg)
    result = engine.parley("goblin_1", skill="persuasion", outcome="surrender", target="hero")
    assert isinstance(result, Rejected)


# --- исходы ---

def test_surrender_sets_the_status(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS), goblins=2)
    talk(engine, skill="intimidation")
    assert part(engine, "goblin_1").status == "surrendered"


def test_surrendered_target_is_not_capable(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS), goblins=2)
    talk(engine, skill="intimidation")
    assert engine.is_capable("goblin_1") is False


def test_surrendered_target_can_still_be_attacked_by_the_hero(registry, cfg):
    # решение проектировщика (R5): бить сдавшегося можно, выбор игрока
    engine = duel(registry, cfg, ScriptedRng(d20=PASS), goblins=2)
    talk(engine, skill="intimidation")
    turn(engine, "hero").action = True
    assert "attack:longsword:goblin_1" in option_ids(engine, "hero")


def test_surrendered_target_gets_no_parley_option(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS), goblins=2)
    talk(engine, skill="intimidation")
    turn(engine, "hero").action = True
    assert not [i for i in option_ids(engine, "hero") if i.startswith("parley:goblin_1")]


def test_surrendered_target_skips_its_turn(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS), goblins=2)
    talk(engine, skill="intimidation")
    engine.state.turn_index = 1
    engine.step()
    assert hp(engine, "hero") == 12
    assert engine.state.turn_index == 2


def test_surrendered_target_stays_surrendered_when_hit(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS + [15], d8=[4]), goblins=2)
    talk(engine, skill="intimidation")
    turn(engine, "hero").action = True
    engine.perform("hero", "attack:longsword:goblin_1")
    assert part(engine, "goblin_1").status == "surrendered"


def test_surrender_of_the_last_enemy_wins_the_fight(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS))
    talk(engine, skill="intimidation")
    assert engine.state.outcome == "victory"


def test_surrender_with_a_living_enemy_left_does_not_end_the_fight(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS), goblins=2)
    talk(engine, skill="intimidation")
    assert engine.state.outcome is None


def test_flee_sets_the_status(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS), goblins=2)
    talk(engine, skill="deception", outcome="flee")
    assert part(engine, "goblin_1").status == "fled"


def test_flee_works_for_intimidation_and_persuasion_too(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS + PASS), goblins=2)
    talk(engine, skill="intimidation", outcome="flee")
    turn(engine, "hero").action = True
    talk(engine, skill="persuasion", outcome="flee", target="goblin_2")
    assert [part(engine, "goblin_1").status, part(engine, "goblin_2").status] == ["fled", "fled"]


def test_fled_and_surrendered_enemies_end_the_fight_with_victory(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS + PASS), goblins=2)
    talk(engine, skill="intimidation", outcome="flee")
    assert engine.state.outcome is None
    turn(engine, "hero").action = True
    talk(engine, skill="intimidation", target="goblin_2")
    assert engine.state.outcome == "victory"


def test_defect_moves_the_target_to_the_heroes(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[19, 19]), goblins=2)
    talk(engine, outcome="defect")
    p = part(engine, "goblin_1")
    assert (p.side, p.group_id, p.status) == ("heroes", "party", "active")


def defect_flag_of(engine, ref):
    return [e for e in part(engine, ref).creature.active_effects if e.id == "parley_defected"]


def test_defect_flag_keeps_original_group_in_params(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[19, 19]), goblins=2)
    talk(engine, outcome="defect")
    [flag] = defect_flag_of(engine, "goblin_1")
    assert flag.params == {"group": "goblins"}


def test_defect_flag_source_is_the_speaker_and_kind_is_flag(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[19, 19]), goblins=2)
    talk(engine, outcome="defect")
    [flag] = defect_flag_of(engine, "goblin_1")
    assert (flag.source, flag.kind) == ("hero", "flag")


def test_failed_defect_leaves_no_flag(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[18, 18]), goblins=2)
    talk(engine, outcome="defect")
    assert defect_flag_of(engine, "goblin_1") == []


def test_defect_succeeds_exactly_on_the_dc(registry, cfg):
    # 19 + 1 = 20 = СЛ 15 + 5
    engine = duel(registry, cfg, ScriptedRng(d20=[19, 19]), goblins=2)
    talk(engine, outcome="defect")
    assert part(engine, "goblin_1").side == "heroes"


def test_defect_fails_one_below_the_dc(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[18, 18]), goblins=2)
    talk(engine, outcome="defect")
    assert part(engine, "goblin_1").side == "enemies"


def test_defector_stays_capable_and_leaves_the_hero_targets(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[19, 19]), goblins=2)
    talk(engine, outcome="defect")
    assert engine.is_capable("goblin_1") is True
    assert not [i for i in option_ids(engine, "hero") if i.endswith(":goblin_1")]


def test_defector_attacks_its_former_allies(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[19, 19, 15], d6=[3]), goblins=2)
    talk(engine, outcome="defect")
    engine.state.turn_index = 1
    engine.step()
    assert hp(engine, "goblin_2") == 5
    assert hp(engine, "hero") == 12


def test_former_allies_attack_the_defector_not_only_the_hero(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[19, 19, 15], d6=[3]), goblins=2)
    talk(engine, outcome="defect")
    option = [i for i in option_ids(engine, "goblin_2") if i.startswith("attack:")]
    assert "attack:скимитар:goblin_1" in option


def test_last_enemy_defecting_wins_the_fight(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[19, 19]))
    talk(engine, outcome="defect")
    assert engine.state.outcome == "victory"


def test_waver_skips_exactly_one_turn(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS + [15], d6=[3]))
    talk(engine, skill="deception", outcome="waver")
    engine.state.turn_index = 1
    engine.step()
    assert hp(engine, "hero") == 12
    engine.state.turn_index = 1
    engine.step()
    assert hp(engine, "hero") == 7


def test_waver_does_not_change_side_or_status(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS), goblins=2)
    talk(engine, skill="deception", outcome="waver")
    p = part(engine, "goblin_1")
    assert (p.side, p.status) == ("enemies", "active")


def test_failed_check_changes_nothing_but_spends_the_action(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=FAIL), goblins=2)
    talk(engine, skill="intimidation")
    p = part(engine, "goblin_1")
    assert (p.side, p.status) == ("enemies", "active")
    assert turn(engine, "hero").action is False


def test_successful_parley_spends_the_action(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS), goblins=2)
    talk(engine, skill="intimidation")
    assert turn(engine, "hero").action is False


def test_disadvantage_takes_the_lower_die(registry, cfg):
    # 2 и 19 при помехе -> 2 + 3 = 5 < 15
    engine = duel(registry, cfg, ScriptedRng(d20=[19, 2]), goblins=2)
    talk(engine, skill="intimidation")
    assert part(engine, "goblin_1").status == "active"


def test_named_npc_rolls_a_single_die(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[12]), goblins=2, named=True)
    talk(engine, skill="intimidation")
    assert engine.rng.left("d20") == 0
    assert part(engine, "goblin_1").status == "surrendered"


def test_log_names_skill_dc_and_outcome(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS), goblins=2)
    talk(engine, skill="intimidation")
    text = "\n".join(engine.state.log)
    assert SKILL_NAMES["intimidation"] in text
    assert "15" in text


def test_log_shows_dc_parts_of_a_modified_dc(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=FAIL))
    set_hp(engine, "goblin_1", 2)
    talk(engine)
    text = "\n".join(engine.state.log)
    assert "10" in text


# --- провал «переходит» на 5+ ---

def test_big_failure_of_defect_offends_the_target(registry, cfg):
    # 2 + 1 = 3 против 20: провал на 17
    engine = duel(registry, cfg, ScriptedRng(d20=FAIL), goblins=2)
    talk(engine, outcome="defect")
    offended = [e for e in creature(engine, "goblin_1").active_effects if e.kind == "modifier"]
    assert [(e.params["target"], e.params["mode"], e.params["consume"]) for e in offended] == [
        ("attack_roll", "advantage", True)
    ]


def test_small_failure_of_defect_does_not_offend(registry, cfg):
    # 17 + 1 = 18 против 20: провал на 2
    engine = duel(registry, cfg, ScriptedRng(d20=[17, 17]), goblins=2)
    talk(engine, outcome="defect")
    assert effect_ids(engine, "goblin_1") == ["parley_tried"]


def test_failure_by_exactly_five_offends(registry, cfg):
    # 14 + 1 = 15 против 20: провал ровно на 5
    engine = duel(registry, cfg, ScriptedRng(d20=[14, 14]), goblins=2)
    talk(engine, outcome="defect")
    assert "parley_offended" in effect_ids(engine, "goblin_1")


def test_failure_by_four_does_not_offend(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[15, 15]), goblins=2)
    talk(engine, outcome="defect")
    assert effect_ids(engine, "goblin_1") == ["parley_tried"]


def test_big_failure_of_other_outcomes_does_not_offend(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=FAIL), goblins=2)
    talk(engine, outcome="surrender")
    assert effect_ids(engine, "goblin_1") == ["parley_tried"]


def test_offended_target_attacks_the_hero_with_advantage_once(registry, cfg):
    # d20: два на проверку, затем два на атаку с преимуществом (3 и 15 -> 15 попадает);
    # преимущество даёт скимитару доп. 1d4 урона
    engine = duel(registry, cfg, ScriptedRng(d20=FAIL + [3, 15], d6=[3], d4=[2]))
    talk(engine, outcome="defect")
    engine.state.turn_index = 1
    engine.step()
    assert hp(engine, "hero") == 5
    assert "parley_tried" in effect_ids(engine, "goblin_1")
    assert [e for e in creature(engine, "goblin_1").active_effects if e.kind == "modifier"] == []


def test_unnamed_defector_does_not_enter_the_world(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[19, 19]))
    talk(engine, outcome="defect")
    assert engine.world.npcs == {}


def test_unnamed_surrendered_does_not_enter_the_world(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS))
    talk(engine, skill="intimidation")
    assert engine.world.npcs == {}


# --- сейв ---

def test_combat_state_with_a_surrendered_participant_roundtrips(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS), goblins=2)
    talk(engine, skill="intimidation")
    restored = CombatState.model_validate(engine.state.model_dump(mode="json"))
    assert part_status(restored, "goblin_1") == "surrendered"


def part_status(state, ref):
    return [p.status for p in state.participants if p.ref == ref][0]


def test_combat_state_with_a_defector_roundtrips(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[19, 19]), goblins=2)
    talk(engine, outcome="defect")
    restored = CombatState.model_validate(engine.state.model_dump(mode="json"))
    assert [p.side for p in restored.participants if p.ref == "goblin_1"] == ["heroes"]


# --- меню и конфиг ---

def parley_ids(engine):
    return [i for i in option_ids(engine, "hero") if i.startswith("parley:")]


def test_menu_has_one_row_per_skill_and_target(registry, cfg):
    engine = duel(registry, cfg, goblins=2)
    assert parley_ids(engine) == [
        "parley:goblin_1:intimidation:surrender", "parley:goblin_1:persuasion:defect",
        "parley:goblin_1:deception:flee", "parley:goblin_2:intimidation:surrender",
        "parley:goblin_2:persuasion:defect", "parley:goblin_2:deception:flee",
    ]


def test_menu_label_shows_dc_and_disadvantage(registry, cfg):
    engine = duel(registry, cfg)
    label = [o.label for o in engine.available_actions("hero") if o.id.endswith("surrender")][0]
    assert "СЛ 15" in label
    assert "помеха" in label


def test_menu_label_of_a_named_neutral_npc_has_no_disadvantage(registry, cfg):
    engine = duel(registry, cfg, named=True)
    label = [o.label for o in engine.available_actions("hero") if o.id.endswith("surrender")][0]
    assert "СЛ 15" in label
    assert "помеха" not in label


def test_menu_is_empty_without_an_action(registry, cfg):
    engine = duel(registry, cfg)
    turn(engine, "hero").action = False
    assert parley_ids(engine) == []


def test_menu_skips_targets_out_of_hearing(registry, cfg):
    engine = duel(registry, cfg, hero_zone="door", goblin_zone="balcony")
    assert parley_ids(engine) == []


def test_menu_skips_mindless_targets(registry, cfg, monkeypatch):
    monkeypatch.setattr(registry.get("monster", "goblin_warrior"), "creature_type", "ooze")
    assert parley_ids(duel(registry, cfg)) == []


def test_menu_has_no_parley_for_enemies_turn(registry, cfg):
    engine = duel(registry, cfg)
    assert [i for i in option_ids(engine, "goblin_1") if i.startswith("parley:")] == []


def test_perform_menu_option_runs_the_parley(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS), goblins=2)
    engine.perform("hero", "parley:goblin_1:intimidation:surrender")
    assert part(engine, "goblin_1").status == "surrendered"
    assert turn(engine, "hero").action is False


def test_perform_menu_option_defect(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[19, 19]), goblins=2)
    engine.perform("hero", "parley:goblin_1:persuasion:defect")
    assert part(engine, "goblin_1").side == "heroes"


def test_default_parley_config(cfg):
    p = cfg.parley
    assert (p.base_dc, p.friendly_attitude, p.hostile_attitude) == (15, 30, -30)
    assert (p.friendly_bonus, p.hp_half_bonus, p.hp_quarter_bonus) == (5, 2, 5)
    assert (p.losses_bonus, p.leader_down_bonus) == (3, 3)
    assert (p.overwhelm_bonus, p.defect_penalty, p.waver_bonus, p.key_penalty) == (2, 5, 2, 5)
    assert (p.min_int, p.offended_margin, p.spread_morale) == (3, 5, True)
    assert (p.quarrel_penalty, p.strong_margin) == (2, 10)
    assert list(p.immune_types) == ["construct", "ooze", "plant"]
    assert (p.surrender_attitude, p.defect_attitude, p.offended_attitude) == (10, 20, -10)


def test_parley_dc_follows_the_config(registry):
    custom = load_rules_config(toml_text="[parley]\nbase_dc = 12\ndefect_penalty = 1\n")
    engine = duel(registry, custom)
    assert dc_of(engine)[0] == 12
    assert dc_of(engine, outcome="defect")[0] == 13


# --- детали лога, событий и меток ---

def test_exact_quarter_hp_lowers_the_dc_by_five(registry, cfg):
    engine = duel(registry, cfg)
    creature(engine, "goblin_1").hp_max = 20
    set_hp(engine, "goblin_1", 5)
    assert dc_of(engine)[0] == 10


def test_log_shows_dc_parts(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=FAIL))
    set_hp(engine, "goblin_1", 2)
    talk(engine)
    assert "СЛ 10 [база 15, HP ≤ 25% -5]" in "\n".join(engine.state.log)


def test_log_marks_a_hostile_roll_only_for_hostile_targets(registry, cfg):
    hostile = duel(registry, cfg, ScriptedRng(d20=FAIL))
    talk(hostile)
    assert "враждебен" in "\n".join(hostile.state.log)
    neutral = duel(registry, cfg, ScriptedRng(d20=[5]), named=True)
    talk(neutral)
    assert "враждебен" not in "\n".join(neutral.state.log)


def test_overwhelm_is_counted_in_the_rolled_dc(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry), make_fighter(registry, "ally")],
        monsters=[mon("goblin_1", "goblin_warrior", "hall")], rng=ScriptedRng(d20=FAIL),
    )
    talk(engine, skill="intimidation")
    assert "СЛ 13 " in "\n".join(engine.state.log)


def event_types(result):
    return [e.type for e in result]


def test_outcome_events(registry, cfg):
    surrender = duel(registry, cfg, ScriptedRng(d20=PASS), goblins=2)
    assert event_types(talk(surrender, skill="intimidation")) == ["participant_surrendered"]
    flee = duel(registry, cfg, ScriptedRng(d20=PASS), goblins=2)
    assert event_types(talk(flee, skill="deception", outcome="flee")) == ["participant_fled"]
    defect = duel(registry, cfg, ScriptedRng(d20=[19, 19]), goblins=2)
    assert event_types(talk(defect, outcome="defect")) == ["participant_defected"]


def test_defector_gets_a_mark_for_the_after_fight(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[19, 19]), goblins=2)
    talk(engine, outcome="defect")
    assert "parley_defected" in effect_ids(engine, "goblin_1")


def test_offended_advantage_is_aimed_at_the_hero_and_ends_with_the_targets_turn(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=FAIL), goblins=2)
    talk(engine, outcome="defect")
    effect = [e for e in creature(engine, "goblin_1").active_effects if e.kind == "modifier"][0]
    assert effect.params["against"] == "hero"
    assert (effect.expires.kind, effect.expires.owner) == ("end_of_turn", "goblin_1")


def test_log_lines_of_outcomes(registry, cfg):
    flee = duel(registry, cfg, ScriptedRng(d20=PASS), goblins=2)
    talk(flee, skill="deception", outcome="flee")
    assert "  Воин-гоблин 1 уходит" in "\n".join(flee.state.log)
    offended = duel(registry, cfg, ScriptedRng(d20=FAIL), goblins=2)
    talk(offended, outcome="defect")
    assert "оскорблён" in "\n".join(offended.state.log)


def test_waver_log_line_on_the_lost_turn(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS))
    talk(engine, skill="deception", outcome="waver")
    engine.state.turn_index = 1
    engine.step()
    assert "колеблется и теряет ход" in "\n".join(engine.state.log)


# --- ревью mama-kaban, п. 5 ---

@pytest.mark.parametrize("status", ["down", "dead", "fled", "surrendered"])
def test_inactive_target_reason_is_target_not_active(registry, cfg, status):
    engine = duel(registry, cfg)
    part(engine, "goblin_1").status = status
    assert talk(engine).reason == "target_not_active"


def test_second_attempt_reason_is_already_tried(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=FAIL))
    talk(engine)
    turn(engine, "hero").action = True
    assert talk(engine).reason == "already_tried"


def test_far_target_reason_is_out_of_hearing(registry, cfg):
    engine = duel(registry, cfg, hero_zone="door", goblin_zone="balcony")
    assert talk(engine).reason == "out_of_hearing"


def test_other_refusal_reasons(registry, cfg):
    engine = duel(registry, cfg)
    assert talk(engine, target="nobody").reason == "target_required"
    assert talk(engine, skill="athletics").reason == "unknown_skill"
    assert talk(engine, outcome="mutiny").reason == "unknown_outcome"
    assert engine.parley("goblin_1", skill="persuasion", outcome="surrender",
                         target="hero").reason == "not_a_hero"
    turn(engine, "hero").action = False
    assert talk(engine).reason == "not_available"


def test_key_npc_defect_reason(registry, cfg):
    engine = duel(registry, cfg, named=True)
    engine.world.npcs["goblin_1"].key = True
    assert talk(engine, outcome="defect").reason == "key_npc_cannot_defect"


def test_immune_type_with_high_intelligence_reason_is_not_sentient(registry, cfg, monkeypatch):
    monkeypatch.setattr(registry.get("monster", "goblin_warrior"), "creature_type", "construct")
    monkeypatch.setitem(registry.get("monster", "goblin_warrior").abilities, "int", 12)
    assert talk(duel(registry, cfg)).reason == "not_sentient"


def test_intelligence_equal_to_min_int_is_refused_and_one_above_passes(
    registry, cfg, monkeypatch
):
    abilities = registry.get("monster", "goblin_warrior").abilities
    monkeypatch.setitem(abilities, "int", 3)
    assert talk(duel(registry, cfg)).reason == "not_sentient"
    monkeypatch.setitem(abilities, "int", 4)
    assert not isinstance(talk(duel(registry, cfg, ScriptedRng(d20=PASS))), Rejected)


@pytest.mark.parametrize("skill,outcome,expected", [
    ("deception", "waver", 18), ("persuasion", "flee", 20), ("deception", "flee", 20),
])
def test_key_penalty_applies_to_every_outcome_but_defect(registry, cfg, skill, outcome, expected):
    engine = duel(registry, cfg, named=True)
    engine.world.npcs["goblin_1"].key = True
    assert dc_of(engine, skill=skill, outcome=outcome)[0] == expected


def test_defector_is_not_a_loss_of_its_former_group(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[19, 19]), goblins=3)
    talk(engine, outcome="defect", target="goblin_3")
    turn(engine, "hero").action = True
    assert dc_of(engine, target="goblin_2")[0] == 15


def test_leader_defector_counts_as_a_down_leader_for_his_former_group(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[19, 19]), goblins=3)
    talk(engine, outcome="defect", target="goblin_1")
    assert dc_of(engine, target="goblin_2")[0] == 12


def test_menu_entry_params_and_exactly_three_pairs(registry, cfg):
    engine = duel(registry, cfg)
    options = [o for o in engine.available_actions("hero") if o.kind == "parley"]
    assert [(o.id, o.params) for o in options] == [
        ("parley:goblin_1:intimidation:surrender",
         {"skill": "intimidation", "outcome": "surrender", "target": "goblin_1"}),
        ("parley:goblin_1:persuasion:defect",
         {"skill": "persuasion", "outcome": "defect", "target": "goblin_1"}),
        ("parley:goblin_1:deception:flee",
         {"skill": "deception", "outcome": "flee", "target": "goblin_1"}),
    ]


def test_rejected_parley_writes_no_log_and_keeps_the_action(registry, cfg):
    engine = duel(registry, cfg)
    before = list(engine.state.log)
    assert isinstance(talk(engine, target="nobody"), Rejected)
    assert engine.state.log == before
    assert turn(engine, "hero").action is True


def test_surrendered_enemy_does_not_provoke_when_the_hero_leaves(registry, cfg):
    engine = duel(registry, cfg)
    part(engine, "goblin_1").status = "surrendered"
    engine.perform("hero", "move:door")
    assert engine.rng.calls == []
    assert "провоцированная атака" not in "\n".join(engine.state.log)


def test_wavering_target_still_takes_start_of_turn_damage_but_loses_the_action(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS, d6=[4]), goblins=2)
    talk(engine, skill="deception", outcome="waver")
    creature(engine, "goblin_1").active_effects.append(
        ActiveEffect(id="ensnaring_strike", source="hero", kind="ensnared",
                     params={"dice": "1d6", "damage_type": "piercing", "dc": 12})
    )
    engine.state.turn_index = 1
    engine.step()
    assert hp(engine, "goblin_1") == 6
    assert hp(engine, "hero") == 12


# --- шаг 19: «ссорится» (deception + quarrel) ---

def quarrel(engine, target="goblin_1"):
    return talk(engine, skill="deception", outcome="quarrel", target=target)


def mark_quarrel(engine, ref="goblin_1"):
    creature(engine, ref).active_effects.append(
        ActiveEffect(id="quarreling", source="hero", kind="flag")
    )


def run_turn(engine, ref):
    engine.state.turn_index = [p.ref for p in engine.state.participants].index(ref)
    return engine.step()


def test_quarrel_is_a_known_flag_cleared_after_the_fight():
    assert "quarreling" in FLAG_IDS


def test_quarrel_dc_is_the_plain_dc_plus_two(registry, cfg):
    assert dc_of(duel(registry, cfg, goblins=2), skill="deception", outcome="quarrel")[0] == 17


def test_quarrel_dc_parts_name_the_quarrel_penalty(registry, cfg):
    parts = dc_of(duel(registry, cfg, goblins=2), skill="deception", outcome="quarrel")[2]
    assert ("ссора", 2) in parts


def test_quarrel_penalty_follows_the_config(registry):
    custom = load_rules_config(toml_text="[parley]\nquarrel_penalty = 4\n")
    assert dc_of(duel(registry, custom, goblins=2), skill="deception", outcome="quarrel")[0] == 19


def test_quarrel_log_shows_the_penalty(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=FAIL), goblins=2)
    quarrel(engine)
    assert "СЛ 17 [база 15, ссора +2]" in "\n".join(engine.state.log)


def test_quarrel_log_names_the_outcome(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=FAIL), goblins=2)
    quarrel(engine)
    assert "поссориться со своими" in "\n".join(engine.state.log)


def test_quarrel_succeeds_exactly_on_the_dc(registry, cfg):
    # 16 + 1 = 17
    engine = duel(registry, cfg, ScriptedRng(d20=[16, 16]), goblins=2)
    quarrel(engine)
    assert "quarreling" in effect_ids(engine, "goblin_1")


def test_quarrel_fails_one_below_the_dc(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[15, 15]), goblins=2)
    quarrel(engine)
    assert "quarreling" not in effect_ids(engine, "goblin_1")


def test_quarrel_flag_lasts_until_the_end_of_the_targets_turn(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS), goblins=2)
    quarrel(engine)
    [flag] = [e for e in creature(engine, "goblin_1").active_effects if e.id == "quarreling"]
    assert (flag.kind, flag.source) == ("flag", "hero")
    assert (flag.expires.kind, flag.expires.owner) == ("end_of_turn", "goblin_1")


def test_quarrel_changes_neither_side_nor_status(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS), goblins=2)
    quarrel(engine)
    p = part(engine, "goblin_1")
    assert (p.side, p.status) == ("enemies", "active")


def test_quarrel_gives_no_events_and_logs_the_quarrel(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS), goblins=2)
    assert event_types(quarrel(engine)) == []
    assert "  Воин-гоблин 1 ссорится со своими" in "\n".join(engine.state.log)


def test_quarrel_spends_the_action_and_marks_the_attempt(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS), goblins=2)
    quarrel(engine)
    assert turn(engine, "hero").action is False
    assert "parley_tried" in effect_ids(engine, "goblin_1")


def test_quarrel_without_anyone_to_quarrel_with_is_refused(registry, cfg):
    engine = duel(registry, cfg)
    result = quarrel(engine)
    assert_refused(engine, result)
    assert result.reason == "no_one_to_quarrel"


def test_refused_quarrel_leaves_no_attempt_flag_and_no_log(registry, cfg):
    engine = duel(registry, cfg)
    before = list(engine.state.log)
    quarrel(engine)
    assert effect_ids(engine, "goblin_1") == []
    assert engine.state.log == before


def test_quarrel_with_only_a_downed_mate_is_refused(registry, cfg):
    engine = duel(registry, cfg, goblins=2)
    part(engine, "goblin_2").status = "down"
    set_hp(engine, "goblin_2", 0)
    assert quarrel(engine).reason == "no_one_to_quarrel"


def test_quarrel_with_a_mate_from_another_group_is_allowed(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "hall")], rng=ScriptedRng(d20=PASS),
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("raider_1", "goblin_warrior", "hall", group="raiders")],
    )
    assert not isinstance(quarrel(engine), Rejected)


def test_other_outcomes_do_not_need_a_mate(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS))
    assert not isinstance(talk(engine, skill="deception", outcome="waver"), Rejected)


def test_quarrel_is_not_in_the_menu(registry, cfg):
    engine = duel(registry, cfg, goblins=2)
    assert not [i for i in parley_ids(engine) if i.endswith(":quarrel")]


def test_quarreling_goblin_hits_a_group_mate_not_the_hero(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS + [15], d6=[3]), goblins=2)
    quarrel(engine)
    run_turn(engine, "goblin_1")
    assert (hp(engine, "goblin_2"), hp(engine, "hero")) == (5, 12)


def test_quarreling_goblin_hits_the_weakest_mate(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS + [15], d6=[3]), goblins=3)
    set_hp(engine, "goblin_2", 8)
    set_hp(engine, "goblin_3", 6)
    quarrel(engine)
    run_turn(engine, "goblin_1")
    assert (hp(engine, "goblin_2"), hp(engine, "goblin_3")) == (8, 1)


def test_quarreling_goblin_prefers_its_group_to_other_groups(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "hall")],
        rng=ScriptedRng(d20=PASS + [15], d6=[3]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "hall"),
                  mon("raider_1", "goblin_warrior", "hall", group="raiders")],
    )
    set_hp(engine, "raider_1", 3)
    quarrel(engine)
    run_turn(engine, "goblin_1")
    assert (hp(engine, "goblin_2"), hp(engine, "raider_1")) == (5, 3)


def test_quarreling_goblin_without_group_mates_hits_another_group(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "hall")],
        rng=ScriptedRng(d20=PASS + [15], d6=[3]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("raider_1", "goblin_warrior", "hall", group="raiders")],
    )
    quarrel(engine)
    run_turn(engine, "goblin_1")
    assert (hp(engine, "raider_1"), hp(engine, "hero")) == (5, 12)


def test_quarrel_ends_with_the_turn_and_the_next_one_hits_the_hero(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS + [15, 15], d6=[3, 3]), goblins=2)
    quarrel(engine)
    run_turn(engine, "goblin_1")
    assert "quarreling" not in effect_ids(engine, "goblin_1")
    run_turn(engine, "goblin_1")
    assert hp(engine, "hero") == 7


def test_the_hurt_mate_hits_the_hero_on_its_own_turn(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS + [15, 15], d6=[3, 3]), goblins=2)
    quarrel(engine)
    run_turn(engine, "goblin_1")
    run_turn(engine, "goblin_2")
    assert (hp(engine, "hero"), hp(engine, "goblin_1")) == (7, 10)


def test_quarreling_goblin_has_no_attack_options_against_the_hero(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS), goblins=2)
    quarrel(engine)
    ids = option_ids(engine, "goblin_1")
    hostile = [i for i in ids if i.split(":")[0] in ("attack", "shove", "disarm") and ":hero" in i]
    assert hostile == []
    assert "attack:скимитар:goblin_2" in ids


def test_the_quarrel_does_not_change_the_hero_options(registry, cfg):
    engine = duel(registry, cfg, goblins=2)
    before = option_ids(engine, "hero")
    mark_quarrel(engine)
    assert option_ids(engine, "hero") == before


def spread_out(registry, cfg, rng, reg=None):
    # герой у двери, ссорящийся в зале, его союзник на балконе (нужны дальность или шаг)
    monster = "goblin_warrior" if reg is None else "brute"
    reg = reg or registry
    return make_engine(
        reg, cfg, heroes=[(make_fighter(reg), "door")], rng=rng,
        monsters=[mon("goblin_1", monster, "hall"), mon("goblin_2", monster, "balcony")],
    )


def melee_only(registry):
    return custom_registry(registry, brute={"actions": [bite()]})


def test_quarreling_melee_monster_walks_to_a_mate_in_another_zone(registry, cfg):
    engine = spread_out(
        registry, cfg, ScriptedRng(d20=PASS + [15], d6=[3]), reg=melee_only(registry),
    )
    quarrel(engine)
    run_turn(engine, "goblin_1")
    assert part(engine, "goblin_1").zone_id == "balcony"


def test_quarreling_melee_monster_hits_the_mate_it_walked_to(registry, cfg):
    engine = spread_out(
        registry, cfg, ScriptedRng(d20=PASS + [15], d6=[3]), reg=melee_only(registry),
    )
    quarrel(engine)
    run_turn(engine, "goblin_1")
    assert (hp(engine, "goblin_2"), hp(engine, "hero")) == (7, 12)


def test_quarreling_archer_shoots_a_mate_in_another_zone(registry, cfg):
    engine = spread_out(registry, cfg, ScriptedRng(d20=PASS + [15], d6=[3]))
    quarrel(engine)
    events = run_turn(engine, "goblin_1")
    assert [(e.data["mode"], e.data["target"]) for e in events if e.type == "attack"] == [
        ("ranged", "goblin_2"),
    ]


def test_quarreling_goblin_whose_mates_are_gone_ends_the_turn(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=PASS), goblins=2)
    quarrel(engine)
    part(engine, "goblin_2").status = "dead"
    set_hp(engine, "goblin_2", 0)
    events = run_turn(engine, "goblin_1")
    assert (hp(engine, "hero"), [e.type for e in events if e.type == "attack"]) == (12, [])


def roof(registry, cfg, rng=None, monster="goblin_warrior", reg=None):
    zones = [
        Zone(id="door", name="У двери", adjacent=["hall"]),
        Zone(id="hall", name="Центр зала", adjacent=["door", "balcony"]),
        Zone(id="balcony", name="Балкон", adjacent=["hall"], elevation=1),
    ]
    reg = reg or registry
    return make_engine(
        reg, cfg, heroes=[(make_fighter(reg), "balcony")], rng=rng, zones=zones,
        monsters=[mon("goblin_1", monster, "balcony"), mon("goblin_2", monster, "balcony")],
    )


def choose(engine, ref="goblin_1"):
    return engine.controllers[ref].choose_turn(engine.available_actions(ref), ref)


def test_goblin_on_a_roof_shoves_the_hero_when_not_quarreling(registry, cfg):
    assert choose(roof(registry, cfg)) == "shove:hero:hall"


def test_quarreling_goblin_does_not_shove(registry, cfg):
    engine = roof(registry, cfg)
    mark_quarrel(engine)
    assert choose(engine).startswith("attack:")


def entangle(engine, ref="goblin_1"):
    creature(engine, ref).active_effects.append(
        ActiveEffect(id="ensnaring_strike", source="hero", kind="ensnared",
                     params={"dice": "1d6", "damage_type": "piercing", "dc": 12})
    )


def test_ensnared_goblin_tries_to_escape_when_not_quarreling(registry, cfg):
    engine = duel(registry, cfg, goblins=2)
    entangle(engine)
    assert choose(engine).startswith("escape")


def test_quarreling_ensnared_goblin_attacks_instead_of_escaping(registry, cfg):
    engine = duel(registry, cfg, goblins=2)
    entangle(engine)
    mark_quarrel(engine)
    assert choose(engine).startswith("attack:")


def test_quarreling_boss_multiattacks_only_its_mates(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "hall")],
        rng=ScriptedRng(d20=[15, 15], d6=[1, 1]),
        monsters=[mon("boss", "goblin_boss", "hall"), mon("goblin_1", "goblin_warrior", "hall")],
    )
    mark_quarrel(engine, "boss")
    events = engine.perform("boss", "multiattack")
    assert [(e.data["target"], e.data["outcome"]) for e in events if e.type == "attack"] == [
        ("goblin_1", "hit"), ("goblin_1", "hit"),
    ]


def test_quarreling_boss_prefers_multiattack_to_a_disarm(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "hall")],
        monsters=[mon("boss", "goblin_boss", "hall"), mon("goblin_1", "goblin_warrior", "hall")],
    )
    mark_quarrel(engine, "boss")
    assert choose(engine, "boss") == "multiattack"


# --- шаг 19: мораль группы (spread_morale) ---

# Воин-гоблин: 10 HP, Инт 10 (СЛ 15); Запугивание героя +3, при помехе берётся меньшая кость.
# Цель goblin_1 на 2 HP (≤ 25 %): СЛ 10, значит СЛ + 10 = 20 -- кость 17.
STRONG = [17, 17]
SHORT = [16, 16]


def hurt_band(registry, cfg, d20, goblins=3):
    # goblin_1 -- цель; goblin_2 ровно на половине HP, goblin_3 чуть выше половины
    engine = duel(registry, cfg, ScriptedRng(d20=d20), goblins=goblins)
    set_hp(engine, "goblin_1", 2)
    set_hp(engine, "goblin_2", 5)
    if goblins > 2:
        set_hp(engine, "goblin_3", 6)
    return engine


def status_of(engine, ref):
    return part(engine, ref).status


def test_strong_success_makes_a_wounded_group_mate_surrender_too(registry, cfg):
    engine = hurt_band(registry, cfg, STRONG)
    talk(engine, skill="intimidation")
    assert [status_of(engine, r) for r in ("goblin_1", "goblin_2")] == ["surrendered"] * 2


def test_strong_success_leaves_a_mate_above_half_hp_fighting(registry, cfg):
    engine = hurt_band(registry, cfg, STRONG)
    talk(engine, skill="intimidation")
    assert status_of(engine, "goblin_3") == "active"


def test_strong_success_does_not_touch_a_wounded_member_of_another_group(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "hall")], rng=ScriptedRng(d20=STRONG),
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "hall"),
                  mon("raider_1", "goblin_warrior", "hall", group="raiders")],
    )
    for ref, value in (("goblin_1", 2), ("goblin_2", 5), ("raider_1", 3)):
        set_hp(engine, ref, value)
    talk(engine, skill="intimidation")
    assert status_of(engine, "raider_1") == "active"


def test_one_short_of_the_strong_margin_spreads_nothing(registry, cfg):
    engine = hurt_band(registry, cfg, SHORT)
    talk(engine, skill="intimidation")
    assert [status_of(engine, r) for r in ("goblin_1", "goblin_2")] == ["surrendered", "active"]


def test_natural_twenty_on_a_success_spreads_the_morale(registry, cfg):
    # 20 + 3 = 23 против СЛ 15: запас 8, но натуральная 20
    engine = duel(registry, cfg, ScriptedRng(d20=[20, 20]), goblins=3)
    set_hp(engine, "goblin_2", 5)
    talk(engine, skill="intimidation")
    assert status_of(engine, "goblin_2") == "surrendered"


def test_natural_twenty_on_a_failure_does_nothing(registry, cfg, monkeypatch):
    # Инт 22: СЛ 22, а 20 + 1 = 21
    monkeypatch.setitem(registry.get("monster", "goblin_warrior").abilities, "int", 22)
    engine = duel(registry, cfg, ScriptedRng(d20=[20, 20]), goblins=3)
    set_hp(engine, "goblin_2", 5)
    talk(engine, skill="persuasion")
    assert [status_of(engine, r) for r in ("goblin_1", "goblin_2")] == ["active", "active"]


def test_flee_spreads_the_morale_too(registry, cfg):
    engine = hurt_band(registry, cfg, STRONG)
    talk(engine, skill="intimidation", outcome="flee")
    assert [status_of(engine, r) for r in ("goblin_1", "goblin_2")] == ["fled", "fled"]


@pytest.mark.parametrize("skill,outcome,d20", [
    ("persuasion", "defect", [20, 20]),
    ("deception", "waver", [19, 19]),
    ("deception", "quarrel", [20, 20]),
])
def test_other_outcomes_do_not_spread(registry, cfg, skill, outcome, d20):
    engine = hurt_band(registry, cfg, d20)
    talk(engine, skill=skill, outcome=outcome)
    p = part(engine, "goblin_2")
    assert (p.side, p.status, effect_ids(engine, "goblin_2")) == ("enemies", "active", [])


def test_morale_can_be_switched_off(registry):
    off = load_rules_config(toml_text="[parley]\nspread_morale = false\n")
    engine = hurt_band(registry, off, STRONG)
    talk(engine, skill="intimidation")
    assert [status_of(engine, r) for r in ("goblin_1", "goblin_2")] == ["surrendered", "active"]


def test_strong_margin_follows_the_config(registry):
    wide = load_rules_config(toml_text="[parley]\nstrong_margin = 5\n")
    engine = hurt_band(registry, wide, SHORT)
    talk(engine, skill="intimidation")
    assert status_of(engine, "goblin_2") == "surrendered"


def test_morale_gives_an_event_for_every_one_who_gave_up(registry, cfg):
    engine = hurt_band(registry, cfg, STRONG)
    events = talk(engine, skill="intimidation")
    assert [(e.type, e.data["id"]) for e in events] == [
        ("participant_surrendered", "goblin_1"), ("participant_surrendered", "goblin_2"),
    ]


def test_morale_writes_a_log_line_for_each_follower(registry, cfg):
    engine = hurt_band(registry, cfg, STRONG)
    talk(engine, skill="intimidation")
    assert "  Воин-гоблин 2 тоже сдаётся" in "\n".join(engine.state.log)


def test_fleeing_follower_is_logged(registry, cfg):
    engine = hurt_band(registry, cfg, STRONG)
    talk(engine, skill="intimidation", outcome="flee")
    assert "  Воин-гоблин 2 тоже уходит" in "\n".join(engine.state.log)


def test_single_target_log_has_no_also(registry, cfg):
    engine = hurt_band(registry, cfg, SHORT)
    talk(engine, skill="intimidation")
    log = "\n".join(engine.state.log)
    assert "  Воин-гоблин 1 сдаётся" in log
    assert "тоже" not in log


def test_target_of_a_strong_success_has_no_also(registry, cfg):
    engine = hurt_band(registry, cfg, STRONG)
    talk(engine, skill="intimidation")
    assert "  Воин-гоблин 1 сдаётся" in "\n".join(engine.state.log)


def test_morale_takes_no_extra_roll(registry, cfg):
    engine = hurt_band(registry, cfg, STRONG)
    talk(engine, skill="intimidation")
    assert engine.rng.calls == ["d20", "d20"]


def test_surrendered_follower_drops_its_weapons(registry, cfg):
    engine = hurt_band(registry, cfg, STRONG)
    talk(engine, skill="intimidation")
    assert {i.owner_ref for i in engine.state.ground_items} == {"goblin_1", "goblin_2"}


def test_morale_skips_a_member_who_is_down(registry, cfg):
    engine = hurt_band(registry, cfg, STRONG)
    part(engine, "goblin_2").status = "down"
    set_hp(engine, "goblin_2", 0)
    set_hp(engine, "goblin_3", 5)
    talk(engine, skill="intimidation")
    assert [status_of(engine, r) for r in ("goblin_2", "goblin_3")] == ["down", "surrendered"]


def test_morale_that_removes_every_enemy_wins_the_fight(registry, cfg):
    engine = hurt_band(registry, cfg, STRONG, goblins=2)
    talk(engine, skill="intimidation")
    assert engine.state.outcome == "victory"


def test_without_morale_the_fight_goes_on(registry, cfg):
    engine = hurt_band(registry, cfg, SHORT, goblins=2)
    talk(engine, skill="intimidation")
    assert engine.state.outcome is None


@pytest.mark.parametrize("fields", [
    {"creature_type": "construct"},
    {"abilities": {"str": 8, "dex": 15, "con": 10, "int": 3, "wis": 8, "cha": 8}},
])
def test_morale_does_not_reach_a_wounded_member_who_cannot_hear(registry, cfg, fields):
    reg = custom_registry(registry, dummy=fields)
    engine = make_engine(
        reg, cfg, heroes=[(make_fighter(reg), "hall")], rng=ScriptedRng(d20=STRONG),
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("dummy_1", "dummy", "hall"),
                  mon("goblin_3", "goblin_warrior", "hall")],
    )
    for ref, value in (("goblin_1", 2), ("dummy_1", 5), ("goblin_3", 5)):
        set_hp(engine, ref, value)
    talk(engine, skill="intimidation")
    assert [status_of(engine, r) for r in ("dummy_1", "goblin_3")] == ["active", "surrendered"]
