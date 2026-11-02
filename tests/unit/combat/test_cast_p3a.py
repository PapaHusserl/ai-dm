# К3 П3а (docs/plan-k3.md, «Тесты» П3, решения 19, 55): заклинания жреца и волшебника в бою --
# вид по эффектам (spell_kind), цели в меню, исполнение через engine.perform.
#   id пункта: cast:<заклинание>:<круг>:<цель>[:free][:v:<вариант>].
#   Лежачие (решение 55): по цели status == "down" нет пунктов вредящих видов (attack, darts, mark,
#     save, rays, condition) -- их добивает рассказчик; лечение/Пощада союзников -- есть.
#   save: Священное пламя -- спасбросок Лов, провал -- 1d8 излучением, успех -- 0.
#   condition: Удержание личности -- спасбросок Мдр, провал -- paralyzed на концентрации, повтор
#     спасброска в конце хода цели; Усыпление -- недееспособен, провал повтора -- без сознания.
#   cure: Малое восстановление снимает ПЕРВОЕ по порядку состояние из списка заклинания.
#   temp_hp: Ложная жизнь -- 1d4+4, второе применение не складывается (максимум).
#   rays: Палящий луч -- 3 броска атаки заклинанием по 2d6; 3 круг -- 4 луча.
#   Заклинатель -- волшебник 1 ур. из combat_kit (СЛ 13, атака заклинанием +5), ячейки 1-3 круга.
from combat_kit import (
    ScriptedRng,
    creature,
    down_hero,
    hp,
    make_engine,
    make_fighter,
    make_wizard,
    mon,
    option_ids,
    part,
    set_hp,
)

from ai_dm.combat.controllers import ScriptedController
from ai_dm.rules.results import Rejected
from ai_dm.state.creature import AppliedCondition, ResourcePool

GOBLIN = [mon("goblin_1", "goblin_warrior", "hall")]
TWO_GOBLINS = [*GOBLIN, mon("goblin_2", "goblin_warrior", "hall")]


def mage(registry, *spells, cantrips=()):
    hero = make_wizard(registry)
    hero.sheet.prepared_of().extend(spells)
    hero.sheet.known_of().extend(cantrips)
    for circle, size in ((1, 4), (2, 3), (3, 3)):
        hero.creature.resources[f"spell_slot:{circle}"] = ResourcePool(current=size, max=size)
    return hero


def engine_of(registry, cfg, hero, rng=None, monsters=GOBLIN, extra=(), **kwargs):
    kwargs.setdefault("hero_zone", "door")
    engine = make_engine(
        registry, cfg, heroes=[hero, *extra], rng=rng or ScriptedRng(), monsters=monsters,
        **kwargs,
    )
    for spec in monsters:
        set_hp(engine, spec["ref"], 30)
    return engine


def idle(registry, cfg, hero, rng=None, monsters=GOBLIN, extra=(), **kwargs):
    # все участники пассивны: engine.step() только проходит ход (end_turn)
    refs = [hero.id, *[h.id for h in extra], *[m["ref"] for m in monsters]]
    controllers = {ref: ScriptedController([]) for ref in refs}
    return engine_of(registry, cfg, hero, rng, monsters, extra, controllers=controllers, **kwargs)


def pass_turns(engine, count):
    for _ in range(count):
        engine.step()


def slot(engine, circle, ref="wiz"):
    return engine.heroes[ref].creature.resources[f"spell_slot:{circle}"].current


def conditions(engine, ref):
    return [c.id for c in creature(engine, ref).conditions]


def effects(engine, ref, spell_id):
    return [e for e in creature(engine, ref).active_effects if e.id == spell_id]


def cast_ids(engine, spell_id, ref="wiz"):
    return [i for i in option_ids(engine, ref) if i.startswith(f"cast:{spell_id}:")]


def lay_down(engine, ref):
    set_hp(engine, ref, 0)
    part(engine, ref).status = "down"


# лежачие (решение 55)

def test_downed_enemy_gets_no_hostile_spell_options(registry, cfg):
    hero = mage(
        registry, "hold_person", "scorching_ray", "sleep", "chromatic_orb", "bestow_curse",
        cantrips=["sacred_flame", "fire_bolt"],
    )
    engine = engine_of(registry, cfg, hero)
    lay_down(engine, "goblin_1")
    spells = {i.split(":")[1] for i in option_ids(engine, "wiz") if i.startswith("cast:")}
    assert not spells & {
        "sacred_flame", "fire_bolt", "scorching_ray", "chromatic_orb", "hold_person", "sleep",
        "bestow_curse",
    }


def test_standing_enemy_gets_hostile_spell_options(registry, cfg):
    hero = mage(registry, "hold_person", "scorching_ray", cantrips=["sacred_flame"])
    engine = engine_of(registry, cfg, hero)
    assert cast_ids(engine, "sacred_flame") == ["cast:sacred_flame:0:goblin_1"]
    assert "cast:hold_person:2:goblin_1" in cast_ids(engine, "hold_person")
    assert "cast:scorching_ray:2:goblin_1" in cast_ids(engine, "scorching_ray")


def test_downed_ally_still_gets_healing_options(registry, cfg):
    hero = mage(registry, "healing_word")
    ally = make_fighter(registry, "ally")
    engine = engine_of(registry, cfg, hero, extra=[ally])
    down_hero(engine, "ally")
    assert "cast:healing_word:1:ally" in option_ids(engine, "wiz")


def test_one_downed_goblin_of_two_leaves_the_other_targetable(registry, cfg):
    hero = mage(registry, cantrips=["sacred_flame"])
    engine = engine_of(registry, cfg, hero, monsters=TWO_GOBLINS)
    lay_down(engine, "goblin_1")
    assert cast_ids(engine, "sacred_flame") == ["cast:sacred_flame:0:goblin_2"]


# save (Священное пламя)

def test_sacred_flame_failed_dex_save_deals_radiant_damage(registry, cfg):
    # Лов гоблина +2: 5 + 2 = 7 < СЛ 13
    engine = engine_of(
        registry, cfg, mage(registry, cantrips=["sacred_flame"]), ScriptedRng(d20=[5], d8=[6])
    )
    engine.perform("wiz", "cast:sacred_flame:0:goblin_1")
    assert hp(engine, "goblin_1") == 24


def test_sacred_flame_passed_save_deals_nothing(registry, cfg):
    # 15 + 2 = 17 >= 13
    engine = engine_of(
        registry, cfg, mage(registry, cantrips=["sacred_flame"]), ScriptedRng(d20=[15], d8=[6])
    )
    engine.perform("wiz", "cast:sacred_flame:0:goblin_1")
    assert hp(engine, "goblin_1") == 30


def test_sacred_flame_costs_no_slot(registry, cfg):
    engine = engine_of(
        registry, cfg, mage(registry, cantrips=["sacred_flame"]), ScriptedRng(d20=[15], d8=[6])
    )
    engine.perform("wiz", "cast:sacred_flame:0:goblin_1")
    assert slot(engine, 1) == 4


def test_sacred_flame_logs_the_targets_hp_line(registry, cfg):
    engine = engine_of(
        registry, cfg, mage(registry, cantrips=["sacred_flame"]), ScriptedRng(d20=[5], d8=[6])
    )
    engine.perform("wiz", "cast:sacred_flame:0:goblin_1")
    assert f"  {engine.name('goblin_1')}: {engine.hp_text('goblin_1')}" in engine.state.log


def test_sacred_flame_reports_one_automatic_spell_hit_event(registry, cfg):
    engine = engine_of(
        registry, cfg, mage(registry, cantrips=["sacred_flame"]), ScriptedRng(d20=[5], d8=[6])
    )
    events = engine.perform("wiz", "cast:sacred_flame:0:goblin_1")
    assert [e.data for e in events if e.type == "attack"] == [{
        "attacker": "wiz", "target": "goblin_1", "weapon": "sacred_flame", "mode": "spell",
        "outcome": "auto", "damage": 6,
    }]


# condition

def held_of(engine, ref="goblin_1"):
    return [e for e in creature(engine, ref).active_effects if e.kind == "held"]


def with_conditions(registry, spell_id, base_id, conditions):
    # копия заклинания base_id с другим набором apply_condition (после save_effect)
    base = registry.get("spell", base_id)
    first = next(e for e in base.effects if e.type == "apply_condition")
    rest = [e for e in base.effects if e.type != "apply_condition"]
    staged = [first.model_copy(update={"condition": name}) for name in conditions]
    spell = base.model_copy(update={"id": spell_id, "effects": rest + staged})
    return registry.with_items({"spell": [spell]})


def test_hold_person_failed_save_logs_the_condition_on_the_target(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "hold_person"), ScriptedRng(d20=[5]))
    engine.perform("wiz", "cast:hold_person:2:goblin_1")
    paralyzed = registry.get("condition", "paralyzed").name
    assert f"  {engine.name('goblin_1')}: {paralyzed}" in engine.state.log


def test_hold_person_failed_save_leaves_a_repeat_save_bound_to_concentration(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "hold_person"), ScriptedRng(d20=[5]))
    engine.perform("wiz", "cast:hold_person:2:goblin_1")
    (held,) = held_of(engine)
    assert held.params == {"ability": "wis", "dc": 13, "condition": "paralyzed"}
    assert (held.expires.kind, held.expires.owner) == ("concentration", "wiz")


def test_hold_person_held_effect_goes_with_the_concentration(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "hold_person"), ScriptedRng(d20=[5]))
    engine.perform("wiz", "cast:hold_person:2:goblin_1")
    engine.drop_concentration_effects("wiz")
    assert held_of(engine) == []
    assert conditions(engine, "goblin_1") == []


def test_sleep_repeat_save_remembers_the_second_stage(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "sleep"), ScriptedRng(d20=[5]))
    engine.perform("wiz", "cast:sleep:1:goblin_1")
    (held,) = held_of(engine)
    assert held.params["condition"] == "incapacitated"
    assert held.params["next"] == "unconscious"


def test_three_stage_spell_imposes_all_but_the_last_and_joins_them_in_the_repeat(registry, cfg):
    stages = ["blinded", "restrained", "unconscious"]
    custom = with_conditions(registry, "deep_sleep", "sleep", stages)
    engine = engine_of(custom, cfg, mage(custom, "deep_sleep"), ScriptedRng(d20=[5]))
    engine.perform("wiz", "cast:deep_sleep:1:goblin_1")
    assert conditions(engine, "goblin_1") == ["blinded", "restrained"]
    (held,) = held_of(engine)
    assert held.params["condition"] == "blinded,restrained"
    assert held.params["next"] == "unconscious"


def test_lone_unconscious_condition_is_imposed_at_once(registry, cfg):
    custom = with_conditions(registry, "swoon", "sleep", ["unconscious"])
    engine = engine_of(custom, cfg, mage(custom, "swoon"), ScriptedRng(d20=[5]))
    engine.perform("wiz", "cast:swoon:1:goblin_1")
    assert conditions(engine, "goblin_1") == ["unconscious"]
    assert "next" not in held_of(engine)[0].params


def test_enfeeblement_penalties_are_logged_and_bound_to_concentration(registry, cfg):
    engine = engine_of(
        registry, cfg, mage(registry, "ray_of_enfeeblement"), ScriptedRng(d20=[5]),
    )
    engine.perform("wiz", "cast:ray_of_enfeeblement:2:goblin_1")
    name = registry.get("spell", "ray_of_enfeeblement").name
    assert f"  {engine.name('goblin_1')}: {name}" in engine.state.log
    penalties = [e for e in creature(engine, "goblin_1").active_effects if e.kind == "modifier"]
    assert penalties
    assert {(e.expires.kind, e.expires.owner) for e in penalties} == {("concentration", "wiz")}


def test_enfeeblement_goes_away_with_the_casters_concentration(registry, cfg):
    engine = engine_of(
        registry, cfg, mage(registry, "ray_of_enfeeblement"), ScriptedRng(d20=[5]),
    )
    engine.perform("wiz", "cast:ray_of_enfeeblement:2:goblin_1")
    engine.drop_concentration_effects("wiz")
    assert creature(engine, "goblin_1").active_effects == []


def test_hold_person_failed_wis_save_paralyzes_on_concentration(registry, cfg):
    # Мдр гоблина -1: 5 - 1 = 4 < 13
    engine = engine_of(registry, cfg, mage(registry, "hold_person"), ScriptedRng(d20=[5]))
    engine.perform("wiz", "cast:hold_person:2:goblin_1")
    assert "paralyzed" in conditions(engine, "goblin_1")
    assert engine.heroes["wiz"].creature.concentration.spell_id == "hold_person"
    assert slot(engine, 2) == 2


def test_hold_person_passed_save_leaves_the_target_free_but_spends_the_slot(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "hold_person"), ScriptedRng(d20=[19]))
    engine.perform("wiz", "cast:hold_person:2:goblin_1")
    assert "paralyzed" not in conditions(engine, "goblin_1")
    assert slot(engine, 2) == 2


def test_hold_person_target_repeats_the_save_at_the_end_of_its_turn(registry, cfg):
    # первый спасбросок провален, в конце хода гоблина повтор 19 - 1 = 18 >= 13 -- снимает
    engine = idle(registry, cfg, mage(registry, "hold_person"), ScriptedRng(d20=[5, 19]))
    engine.perform("wiz", "cast:hold_person:2:goblin_1")
    pass_turns(engine, 2)
    assert "paralyzed" not in conditions(engine, "goblin_1")


def test_hold_person_repeat_save_is_not_made_before_the_end_of_the_targets_turn(registry, cfg):
    rng = ScriptedRng(d20=[5, 19])
    engine = idle(registry, cfg, mage(registry, "hold_person"), rng)
    engine.perform("wiz", "cast:hold_person:2:goblin_1")
    pass_turns(engine, 1)
    assert "paralyzed" in conditions(engine, "goblin_1")
    assert rng.left("d20") == 1


def test_hold_person_failed_repeat_keeps_the_target_paralyzed(registry, cfg):
    engine = idle(registry, cfg, mage(registry, "hold_person"), ScriptedRng(d20=[5, 5]))
    engine.perform("wiz", "cast:hold_person:2:goblin_1")
    pass_turns(engine, 2)
    assert "paralyzed" in conditions(engine, "goblin_1")


def test_hold_person_third_circle_offers_two_targets(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "hold_person"), monsters=TWO_GOBLINS)
    ids = cast_ids(engine, "hold_person")
    assert "cast:hold_person:3:goblin_1,goblin_2" in ids
    assert "cast:hold_person:2:goblin_1,goblin_2" not in ids


def test_hold_person_third_circle_paralyzes_both_on_failed_saves(registry, cfg):
    engine = engine_of(
        registry, cfg, mage(registry, "hold_person"), ScriptedRng(d20=[5, 5]), monsters=TWO_GOBLINS
    )
    engine.perform("wiz", "cast:hold_person:3:goblin_1,goblin_2")
    assert "paralyzed" in conditions(engine, "goblin_1")
    assert "paralyzed" in conditions(engine, "goblin_2")


def test_hold_person_ends_with_lost_concentration(registry, cfg):
    # гоблин 1 парализован (5 - 1 < 13); гоблин 2 попадает по волшебнику (19), урон 3 + 2 = 5,
    # СЛ 10, Тел +2: 7 + 2 = 9 -- концентрация сорвана
    monsters = [*GOBLIN, mon("goblin_2", "goblin_warrior", "door")]
    engine = engine_of(
        registry, cfg, mage(registry, "hold_person"), ScriptedRng(d20=[5, 19, 7], d6=[3]),
        monsters=monsters,
    )
    engine.perform("wiz", "cast:hold_person:2:goblin_1")
    engine.perform("goblin_2", "attack:скимитар:wiz")
    assert engine.heroes["wiz"].creature.concentration is None
    assert "paralyzed" not in conditions(engine, "goblin_1")


def test_sleep_failed_save_makes_the_target_incapacitated_only(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "sleep"), ScriptedRng(d20=[5]))
    engine.perform("wiz", "cast:sleep:1:goblin_1")
    assert "incapacitated" in conditions(engine, "goblin_1")
    assert "unconscious" not in conditions(engine, "goblin_1")


def test_sleep_failed_repeat_puts_the_target_to_sleep(registry, cfg):
    engine = idle(registry, cfg, mage(registry, "sleep"), ScriptedRng(d20=[5, 5]))
    engine.perform("wiz", "cast:sleep:1:goblin_1")
    pass_turns(engine, 2)
    assert "unconscious" in conditions(engine, "goblin_1")


def test_sleep_passed_repeat_removes_incapacitated(registry, cfg):
    engine = idle(registry, cfg, mage(registry, "sleep"), ScriptedRng(d20=[5, 19]))
    engine.perform("wiz", "cast:sleep:1:goblin_1")
    pass_turns(engine, 2)
    assert conditions(engine, "goblin_1") == []


def test_hold_person_has_no_second_stage(registry, cfg):
    # одно состояние -- без «следующей стадии»: провал повтора оставляет paralyzed
    engine = idle(registry, cfg, mage(registry, "hold_person"), ScriptedRng(d20=[5, 5, 5]))
    engine.perform("wiz", "cast:hold_person:2:goblin_1")
    pass_turns(engine, 4)
    assert conditions(engine, "goblin_1") == ["paralyzed"]


# cure

def test_lesser_restoration_removes_the_first_listed_condition(registry, cfg):
    # порядок списка заклинания: blinded раньше poisoned (Р16)
    ally = make_fighter(registry, "ally")
    hero = mage(registry, "lesser_restoration")
    engine = engine_of(registry, cfg, hero, extra=[ally])
    for cond in ("poisoned", "blinded"):
        creature(engine, "ally").conditions.append(AppliedCondition(id=cond, source="x"))
    engine.perform("wiz", "cast:lesser_restoration:2:ally")
    assert conditions(engine, "ally") == ["poisoned"]


def test_lesser_restoration_is_not_offered_without_a_condition(registry, cfg):
    ally = make_fighter(registry, "ally")
    engine = engine_of(registry, cfg, mage(registry, "lesser_restoration"), extra=[ally])
    assert cast_ids(engine, "lesser_restoration") == []


def test_lesser_restoration_is_offered_with_a_curable_condition(registry, cfg):
    ally = make_fighter(registry, "ally")
    engine = engine_of(registry, cfg, mage(registry, "lesser_restoration"), extra=[ally])
    creature(engine, "ally").conditions.append(AppliedCondition(id="poisoned", source="x"))
    assert "cast:lesser_restoration:2:ally" in option_ids(engine, "wiz")


def test_lesser_restoration_ignores_a_condition_not_in_its_list(registry, cfg):
    ally = make_fighter(registry, "ally")
    engine = engine_of(registry, cfg, mage(registry, "lesser_restoration"), extra=[ally])
    creature(engine, "ally").conditions.append(AppliedCondition(id="prone", source="x"))
    assert cast_ids(engine, "lesser_restoration") == []


def test_remove_curse_removes_cursed(registry, cfg):
    ally = make_fighter(registry, "ally")
    engine = engine_of(registry, cfg, mage(registry, "remove_curse"), extra=[ally])
    creature(engine, "ally").conditions.append(AppliedCondition(id="cursed", source="x"))
    part(engine, "ally").zone_id = "door"
    engine.perform("wiz", "cast:remove_curse:3:ally")
    assert conditions(engine, "ally") == []


# temp_hp

def test_false_life_gives_1d4_plus_4_temporary_hp(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "false_life"), ScriptedRng(d4=[3]))
    engine.perform("wiz", "cast:false_life:1:")
    assert creature(engine, "wiz").hp_temp == 7


def test_false_life_does_not_stack_it_takes_the_maximum(registry, cfg):
    engine = idle(registry, cfg, mage(registry, "false_life"), ScriptedRng(d4=[3, 1]))
    engine.perform("wiz", "cast:false_life:1:")
    pass_turns(engine, 2)
    engine.perform("wiz", "cast:false_life:1:")
    assert creature(engine, "wiz").hp_temp == 7
    assert slot(engine, 1) == 2


def test_false_life_higher_roll_replaces_the_lower_temporary_hp(registry, cfg):
    engine = idle(registry, cfg, mage(registry, "false_life"), ScriptedRng(d4=[1, 4]))
    engine.perform("wiz", "cast:false_life:1:")
    pass_turns(engine, 2)
    engine.perform("wiz", "cast:false_life:1:")
    assert creature(engine, "wiz").hp_temp == 8


# rays

def test_scorching_ray_makes_three_attacks_of_2d6_fire(registry, cfg):
    # три броска атаки +5 против КД гоблина-воина 15: 12 + 5 = 17 -- попадания; три раза 2d6 = 7
    engine = engine_of(
        registry, cfg, mage(registry, "scorching_ray"),
        ScriptedRng(d20=[12, 12, 12], d6=[3, 4] * 3),
    )
    engine.perform("wiz", "cast:scorching_ray:2:goblin_1")
    assert hp(engine, "goblin_1") == 30 - 21


def test_scorching_ray_only_hits_damage(registry, cfg):
    # первый луч мимо (2 + 5 = 7 < 15), два попадают
    engine = engine_of(
        registry, cfg, mage(registry, "scorching_ray"),
        ScriptedRng(d20=[2, 12, 12], d6=[3, 4] * 2),
    )
    engine.perform("wiz", "cast:scorching_ray:2:goblin_1")
    assert hp(engine, "goblin_1") == 30 - 14


def test_scorching_ray_third_circle_makes_four_attacks(registry, cfg):
    engine = engine_of(
        registry, cfg, mage(registry, "scorching_ray"),
        ScriptedRng(d20=[12] * 4, d6=[3, 4] * 4),
    )
    engine.perform("wiz", "cast:scorching_ray:3:goblin_1")
    assert hp(engine, "goblin_1") == 30 - 28


def test_scorching_ray_spends_the_slot_of_its_circle(registry, cfg):
    engine = engine_of(
        registry, cfg, mage(registry, "scorching_ray"), ScriptedRng(d20=[2] * 3)
    )
    engine.perform("wiz", "cast:scorching_ray:2:goblin_1")
    assert (slot(engine, 2), slot(engine, 3)) == (2, 3)


def test_rejected_spell_without_a_prepared_entry(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry))
    assert isinstance(engine.perform("wiz", "cast:scorching_ray:2:goblin_1"), Rejected)
