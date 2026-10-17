# К1 «Апкаст» в бою (docs/plan-k1.md, п. 3.2-3.3; В8а, В9а, В10):
#   пункт меню на каждый круг с ячейкой у заклинаний с upcast: cast:<id>:<круг>:<цель>, базовый круг
#   первым, подпись повышенного «Волшебная стрела (2 круг) → …», cost тот же, базовая подпись без
#   «круг»; без ячейки круга пункта нет (ячейка 1 круга пуста, 2 есть -- только :2:); заклинания
#   без upcast (Метка) -- только базовый круг; бесплатное применение (Метка, Избранный враг) --
#   только :1:...:free; заговор -- один пункт :0:. Авто-герой берёт базовый круг.
#   Эффект растёт по per_slot_level: Лечение ран 2 круг -- 4d8, Волшебная стрела -- 4 дротика,
#   Огненные руки -- 4d6 одним броском на всех, Благословение -- до 4 целей, Опутывающий удар --
#   заряд 2d6 и params["circle"] == 2; списывается ячейка круга запроса (в т.ч. при провале
#   проверки перед сотворением), ячейка базового круга цела; Concentration.circle -- фактический.
import pytest
from combat_kit import (
    ScriptedRng,
    creature,
    hp,
    make_engine,
    make_fighter,
    make_wizard,
    make_zones,
    mon,
    option_ids,
    set_hp,
)
from test_ranger_combat import make_ranger

from ai_dm.combat.actions import cast
from ai_dm.combat.controllers import AutoHeroController
from ai_dm.rules.cast_checks import CastCheck
from ai_dm.rules.results import Rejected
from ai_dm.state.creature import ResourcePool

GOBLIN = [mon("goblin_1", "goblin_warrior", "hall")]


def wizard(registry, slot1=2, slot2=2, extra=("cure_wounds", "bless", "ensnaring_strike")):
    hero = make_wizard(registry)
    hero.sheet.abilities["int"] = 10
    hero.sheet.prepared_of().extend(extra)
    hero.creature.resources["spell_slot:1"] = ResourcePool(current=slot1, max=2)
    hero.creature.resources["spell_slot:2"] = ResourcePool(current=slot2, max=2)
    return hero


def solo(registry, cfg, rng=None, hero=None, monsters=GOBLIN, **kwargs):
    return make_engine(
        registry, cfg, heroes=[hero or wizard(registry)], rng=rng, monsters=monsters, **kwargs
    )


def slot(engine, circle, ref="wiz"):
    return engine.heroes[ref].creature.resources[f"spell_slot:{circle}"].current


def option(engine, option_id, ref="wiz"):
    return [o for o in engine.available_actions(ref) if o.id == option_id][0]


# меню

def test_menu_has_both_circles_for_an_upcast_spell(registry, cfg):
    ids = option_ids(solo(registry, cfg), "wiz")
    assert "cast:magic_missile:1:goblin_1" in ids
    assert "cast:magic_missile:2:goblin_1" in ids


def test_menu_base_circle_comes_before_the_upcast(registry, cfg):
    ids = option_ids(solo(registry, cfg), "wiz")
    assert ids.index("cast:magic_missile:1:goblin_1") < ids.index("cast:magic_missile:2:goblin_1")


def test_menu_upcast_label_names_the_circle(registry, cfg):
    label = option(solo(registry, cfg), "cast:magic_missile:2:goblin_1").label
    assert label.startswith("Волшебная стрела (2 круг) →")


def test_menu_base_label_has_no_circle(registry, cfg):
    label = option(solo(registry, cfg), "cast:magic_missile:1:goblin_1").label
    assert "круг" not in label


def test_menu_upcast_has_the_same_cost_and_kind(registry, cfg):
    engine = solo(registry, cfg)
    base = option(engine, "cast:magic_missile:1:goblin_1")
    upper = option(engine, "cast:magic_missile:2:goblin_1")
    assert (upper.cost, upper.kind) == (base.cost, base.kind)


def test_menu_upcast_params_carry_the_circle(registry, cfg):
    upper = option(solo(registry, cfg), "cast:magic_missile:2:goblin_1")
    assert upper.params == {"spell": "magic_missile", "circle": 2, "target": "goblin_1"}


def test_menu_without_a_second_circle_slot_has_only_the_first(registry, cfg):
    ids = option_ids(solo(registry, cfg, hero=wizard(registry, slot2=0)), "wiz")
    assert "cast:magic_missile:1:goblin_1" in ids
    assert not [i for i in ids if i.startswith("cast:magic_missile:2:")]


def test_menu_with_an_empty_base_circle_offers_only_the_second(registry, cfg):
    ids = option_ids(solo(registry, cfg, hero=wizard(registry, slot1=0)), "wiz")
    assert "cast:magic_missile:2:goblin_1" in ids
    assert not [i for i in ids if i.startswith("cast:magic_missile:1:")]


def test_castable_spells_include_an_upcast_spell_with_only_a_higher_slot(registry, cfg):
    engine = solo(registry, cfg, hero=wizard(registry, slot1=0))
    assert "cure_wounds" in [s.id for s in cast.castable_spells(engine, "wiz")]


def test_castable_spells_skip_a_plain_spell_with_only_a_higher_slot(registry, cfg):
    hero = wizard(registry, slot1=0, extra=("fog_cloud",))
    engine = solo(registry, cfg, hero=hero)
    assert "fog_cloud" not in [s.id for s in cast.castable_spells(engine, "wiz")]


def test_castable_spells_empty_without_any_slot(registry, cfg):
    engine = solo(registry, cfg, hero=wizard(registry, slot1=0, slot2=0))
    assert [s.id for s in cast.castable_spells(engine, "wiz")] == ["fire_bolt"]


def test_cantrip_has_a_single_circle_zero_entry(registry, cfg):
    ids = option_ids(solo(registry, cfg), "wiz")
    bolts = [i for i in ids if i.startswith("cast:fire_bolt:")]
    assert bolts == ["cast:fire_bolt:0:goblin_1"]


def test_spell_without_upcast_is_offered_at_the_base_circle_only(registry, cfg):
    hero = make_ranger(registry)
    hero.creature.resources["spell_slot:2"] = ResourcePool(current=2, max=2)
    engine = make_engine(
        registry, cfg, heroes=[(hero, "door")], monsters=GOBLIN, rng=ScriptedRng(),
    )
    marks = [i for i in option_ids(engine, "hero") if i.startswith("cast:hunters_mark:")]
    assert marks == ["cast:hunters_mark:1:goblin_1", "cast:hunters_mark:1:goblin_1:free"]


def test_free_cast_is_offered_only_at_the_base_circle(registry, cfg):
    hero = make_ranger(registry)
    hero.sheet.prepared_of()[:] = ["cure_wounds"]
    hero.creature.resources["spell_slot:2"] = ResourcePool(current=2, max=2)
    engine = make_engine(
        registry, cfg, heroes=[(hero, "hall")], monsters=GOBLIN, rng=ScriptedRng(),
    )
    ids = option_ids(engine, "hero")
    assert "cast:cure_wounds:2:hero" in ids
    assert not [i for i in ids if i.startswith("cast:cure_wounds") and i.endswith(":free")]
    mark_free = [i for i in ids if i.startswith("cast:hunters_mark") and i.endswith(":free")]
    assert mark_free == ["cast:hunters_mark:1:goblin_1:free"]


def test_free_base_variant_stays_when_the_base_slot_is_empty(registry, cfg):
    hero = make_ranger(registry)
    hero.creature.resources["spell_slot:1"].current = 0
    engine = make_engine(
        registry, cfg, heroes=[(hero, "door")], monsters=GOBLIN, rng=ScriptedRng(),
    )
    ids = option_ids(engine, "hero")
    assert "cast:hunters_mark:1:goblin_1:free" in ids
    assert "cast:hunters_mark:1:goblin_1" not in ids


def test_auto_hero_casts_the_base_circle(registry, cfg):
    engine = solo(registry, cfg)
    chosen = AutoHeroController(engine).pick_spell(engine.available_actions("wiz"))
    assert chosen == "cast:magic_missile:1:goblin_1"


def test_upcast_option_with_a_spent_slot_is_rejected(registry, cfg):
    engine = solo(registry, cfg, hero=wizard(registry, slot2=0))
    assert isinstance(engine.perform("wiz", "cast:magic_missile:2:goblin_1"), Rejected)
    assert slot(engine, 1) == 2


def test_upcast_of_a_plain_spell_is_rejected(registry, cfg):
    hero = make_ranger(registry)
    hero.creature.resources["spell_slot:2"] = ResourcePool(current=2, max=2)
    engine = make_engine(
        registry, cfg, heroes=[(hero, "door")], monsters=GOBLIN, rng=ScriptedRng(),
    )
    assert isinstance(engine.perform("hero", "cast:hunters_mark:2:goblin_1"), Rejected)


# Лечение ран

def hurt(engine, ref="wiz"):
    creature(engine, ref).hp_max = 100
    set_hp(engine, ref, 1)


def test_cure_wounds_second_circle_heals_four_dice(registry, cfg):
    rng = ScriptedRng(d8=[3, 4, 5, 6])
    engine = solo(registry, cfg, rng)
    hurt(engine)
    engine.perform("wiz", "cast:cure_wounds:2:wiz")
    assert hp(engine, "wiz") == 1 + 18
    assert rng.left("d8") == 0


def test_cure_wounds_second_circle_spends_the_second_slot_only(registry, cfg):
    engine = solo(registry, cfg, ScriptedRng(d8=[1, 1, 1, 1]))
    hurt(engine)
    engine.perform("wiz", "cast:cure_wounds:2:wiz")
    assert (slot(engine, 1), slot(engine, 2)) == (2, 1)


def test_cure_wounds_base_circle_heals_two_dice(registry, cfg):
    rng = ScriptedRng(d8=[3, 4])
    engine = solo(registry, cfg, rng)
    hurt(engine)
    engine.perform("wiz", "cast:cure_wounds:1:wiz")
    assert hp(engine, "wiz") == 1 + 7
    assert (slot(engine, 1), slot(engine, 2)) == (1, 2)


def test_cast_log_names_the_circle_only_when_raised(registry, cfg):
    engine = solo(registry, cfg, ScriptedRng(d8=[1, 1, 1, 1, 1, 1]))
    hurt(engine)
    engine.perform("wiz", "cast:cure_wounds:2:wiz")
    engine.part("wiz").turn.action = True
    engine.perform("wiz", "cast:cure_wounds:1:wiz")
    reads = [line for line in engine.state.log if "читает Лечение ран" in line]
    assert "(2 круг)" in reads[0]
    assert "круг" not in reads[1]


# Волшебная стрела

def goblin_hp(engine, value=40):
    set_hp(engine, "goblin_1", value)
    creature(engine, "goblin_1").hp_max = value


def test_magic_missile_base_circle_throws_three_darts(registry, cfg):
    rng = ScriptedRng(d4=[2, 2, 2])
    engine = solo(registry, cfg, rng)
    goblin_hp(engine)
    engine.perform("wiz", "cast:magic_missile:1:goblin_1")
    assert hp(engine, "goblin_1") == 40 - 3 * 3
    assert rng.left("d4") == 0


def test_magic_missile_second_circle_throws_four_darts(registry, cfg):
    rng = ScriptedRng(d4=[2, 2, 2, 2])
    engine = solo(registry, cfg, rng)
    goblin_hp(engine)
    engine.perform("wiz", "cast:magic_missile:2:goblin_1")
    assert hp(engine, "goblin_1") == 40 - 4 * 3
    assert rng.left("d4") == 0


def test_magic_missile_second_circle_spends_the_second_slot(registry, cfg):
    engine = solo(registry, cfg, ScriptedRng(d4=[1, 1, 1, 1]))
    goblin_hp(engine)
    engine.perform("wiz", "cast:magic_missile:2:goblin_1")
    assert (slot(engine, 1), slot(engine, 2)) == (2, 1)


def test_magic_missile_third_circle_throws_five_darts(registry, cfg):
    hero = wizard(registry)
    hero.creature.resources["spell_slot:3"] = ResourcePool(current=1, max=1)
    rng = ScriptedRng(d4=[1] * 5)
    engine = solo(registry, cfg, rng, hero=hero)
    goblin_hp(engine)
    engine.perform("wiz", "cast:magic_missile:3:goblin_1")
    assert rng.left("d4") == 0


# Огненные руки

def hands(registry, cfg, rng):
    engine = make_engine(
        registry, cfg, heroes=[(wizard(registry), "door")], rng=rng, zones=make_zones(),
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "hall")],
    )
    set_hp(engine, "goblin_1", 40)
    set_hp(engine, "goblin_2", 40)
    return engine


def test_burning_hands_second_circle_rolls_four_dice_once_for_everyone(registry, cfg):
    rng = ScriptedRng(d20=[1, 1], d6=[1, 2, 3, 4])
    engine = hands(registry, cfg, rng)
    engine.perform("wiz", "cast:burning_hands:2:hall")
    assert hp(engine, "goblin_1") == 30
    assert hp(engine, "goblin_2") == 30
    assert rng.left("d6") == 0


def test_burning_hands_base_circle_rolls_three_dice(registry, cfg):
    rng = ScriptedRng(d20=[1, 1], d6=[1, 2, 3])
    engine = hands(registry, cfg, rng)
    engine.perform("wiz", "cast:burning_hands:1:hall")
    assert hp(engine, "goblin_1") == 34
    assert rng.left("d6") == 0


def test_burning_hands_second_circle_spends_the_second_slot(registry, cfg):
    engine = hands(registry, cfg, ScriptedRng(d20=[1, 1], d6=[1, 1, 1, 1]))
    engine.perform("wiz", "cast:burning_hands:2:hall")
    assert (slot(engine, 1), slot(engine, 2)) == (2, 1)


# Благословение

def party(registry, cfg, rng=None, slot2=2):
    caster = wizard(registry, slot2=slot2)
    allies = [make_fighter(registry, name) for name in ("ally", "ally2", "ally3")]
    return make_engine(
        registry, cfg, heroes=[caster] + allies, rng=rng, monsters=GOBLIN,
    )


def test_bless_second_circle_reaches_four_targets(registry, cfg):
    ids = option_ids(party(registry, cfg), "wiz")
    assert "cast:bless:2:wiz,ally,ally2,ally3" in ids
    assert "cast:bless:2:ally" in ids


def test_bless_base_circle_stops_at_three_targets(registry, cfg):
    ids = option_ids(party(registry, cfg), "wiz")
    assert "cast:bless:1:wiz,ally,ally2" in ids
    assert "cast:bless:1:wiz,ally,ally2,ally3" not in ids


def test_bless_without_a_second_slot_has_no_four_target_variant(registry, cfg):
    ids = option_ids(party(registry, cfg, slot2=0), "wiz")
    assert not [i for i in ids if i.startswith("cast:bless:2:")]


def test_bless_second_circle_blesses_all_four(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:bless:2:wiz,ally,ally2,ally3")
    for ref in ("wiz", "ally", "ally2", "ally3"):
        blessed = [e for e in creature(engine, ref).active_effects if e.id == "bless"]
        assert len(blessed) == 2


def test_bless_second_circle_concentration_has_the_actual_circle(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:bless:2:ally")
    assert engine.heroes["wiz"].creature.concentration.circle == 2


def test_bless_second_circle_spends_the_second_slot_only(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:bless:2:ally")
    assert (slot(engine, 1), slot(engine, 2)) == (2, 1)


def test_bless_base_circle_concentration_keeps_the_base_circle(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:bless:1:ally")
    assert engine.heroes["wiz"].creature.concentration.circle == 1


# Опутывающий удар

def ranger_engine(registry, cfg):
    hero = make_ranger(registry)
    hero.sheet.prepared_of()[:] = ["ensnaring_strike"]
    hero.creature.resources["spell_slot:2"] = ResourcePool(current=2, max=2)
    return make_engine(
        registry, cfg, heroes=[(hero, "door")], monsters=GOBLIN, rng=ScriptedRng(),
        hero_zone="door",
    )


def charge_of(engine):
    return [e for e in creature(engine, "hero").active_effects if e.kind == "weapon_rider"][0]


def test_ensnaring_second_circle_charge_is_two_dice(registry, cfg):
    engine = ranger_engine(registry, cfg)
    engine.perform("hero", "cast:ensnaring_strike:2:hero")
    assert charge_of(engine).params["dice"] == "2d6"
    assert charge_of(engine).params["circle"] == 2


def test_ensnaring_base_circle_charge_is_one_die(registry, cfg):
    engine = ranger_engine(registry, cfg)
    engine.perform("hero", "cast:ensnaring_strike:1:hero")
    assert charge_of(engine).params["dice"] == "1d6"
    assert charge_of(engine).params["circle"] == 1


def test_ensnaring_second_circle_keeps_the_same_save_dc(registry, cfg):
    first = ranger_engine(registry, cfg)
    first.perform("hero", "cast:ensnaring_strike:1:hero")
    second = ranger_engine(registry, cfg)
    second.perform("hero", "cast:ensnaring_strike:2:hero")
    assert charge_of(second).params["dc"] == charge_of(first).params["dc"]


def test_ensnaring_second_circle_spends_the_second_slot_and_holds_the_circle(registry, cfg):
    engine = ranger_engine(registry, cfg)
    engine.perform("hero", "cast:ensnaring_strike:2:hero")
    pools = creature(engine, "hero").resources
    assert (pools["spell_slot:1"].current, pools["spell_slot:2"].current) == (2, 1)
    assert creature(engine, "hero").concentration.circle == 2


# провал проверки перед сотворением тратит ячейку круга запроса

class HardCheck:
    def check(self, caster, spell_id, registry):
        return [CastCheck(kind="ability_check", ability="int", dc=30, reason="тест")]


def test_wasted_upcast_spends_the_second_slot(registry, cfg):
    engine = solo(registry, cfg, ScriptedRng(d20=[1]))
    engine.cast_checks.register(HardCheck())
    engine.perform("wiz", "cast:cure_wounds:2:wiz")
    assert (slot(engine, 1), slot(engine, 2)) == (2, 1)


def test_wasted_base_cast_spends_the_first_slot(registry, cfg):
    engine = solo(registry, cfg, ScriptedRng(d20=[1]))
    engine.cast_checks.register(HardCheck())
    engine.perform("wiz", "cast:cure_wounds:1:wiz")
    assert (slot(engine, 1), slot(engine, 2)) == (1, 2)


@pytest.mark.parametrize("circle", [1, 2])
def test_cast_log_for_wasted_spell_still_says_so(registry, cfg, circle):
    engine = solo(registry, cfg, ScriptedRng(d20=[1]))
    engine.cast_checks.register(HardCheck())
    engine.perform("wiz", f"cast:cure_wounds:{circle}:wiz")
    assert any("не удалось" in line for line in engine.state.log)


# мутанты К1: подписи и стоимость пунктов, события и лог, списание ячейки и бесплатного применения

def test_base_label_is_the_plain_spell_name_with_the_target(registry, cfg):
    label = option(solo(registry, cfg), "cast:magic_missile:1:goblin_1").label
    assert label.startswith("Волшебная стрела → ")
    assert "None" not in label


def test_rider_label_shows_the_charge(registry, cfg):
    engine = solo(registry, cfg)
    assert option(engine, "cast:ensnaring_strike:1:wiz").label == "Опутывающий удар (заряд)"
    assert option(engine, "cast:ensnaring_strike:2:wiz").label == (
        "Опутывающий удар (2 круг) (заряд)"
    )


def test_costs_are_action_and_bonus(registry, cfg):
    engine = solo(registry, cfg)
    assert option(engine, "cast:magic_missile:1:goblin_1").cost == "action"
    assert option(engine, "cast:magic_missile:2:goblin_1").cost == "action"
    assert option(engine, "cast:ensnaring_strike:2:wiz").cost == "bonus"


def test_spent_bonus_action_hides_only_bonus_spells(registry, cfg):
    hero = wizard(registry, extra=("ensnaring_strike", "cure_wounds"))
    engine = solo(registry, cfg, hero=hero)
    engine.part("wiz").turn.bonus = False
    ids = option_ids(engine, "wiz")
    assert not [i for i in ids if i.startswith("cast:ensnaring_strike:")]
    assert "cast:cure_wounds:1:wiz" in ids


def test_spent_action_hides_only_action_spells(registry, cfg):
    engine = solo(registry, cfg)
    engine.part("wiz").turn.action = False
    ids = option_ids(engine, "wiz")
    assert not [i for i in ids if i.startswith("cast:magic_missile:")]
    assert "cast:ensnaring_strike:1:wiz" in ids


def test_free_variant_label_params_and_kind(registry, cfg):
    hero = make_ranger(registry)
    engine = make_engine(
        registry, cfg, heroes=[(hero, "door")], monsters=GOBLIN, rng=ScriptedRng(),
        hero_zone="door",
    )
    free = option(engine, "cast:hunters_mark:1:goblin_1:free", "hero")
    assert free.kind == "cast"
    assert free.params["free"] is True
    assert free.label.endswith("(без ячейки, 2/2)")
    assert free.label.startswith("Метка охотника → ")
    assert free.cost == "bonus"


def test_free_mark_spends_favored_enemy_and_keeps_the_slot(registry, cfg):
    hero = make_ranger(registry)
    engine = make_engine(
        registry, cfg, heroes=[(hero, "door")], monsters=GOBLIN, rng=ScriptedRng(),
        hero_zone="door",
    )
    engine.perform("hero", "cast:hunters_mark:1:goblin_1:free")
    pools = creature(engine, "hero").resources
    assert (pools["favored_enemy"].current, pools["spell_slot:1"].current) == (1, 2)


def test_slot_is_decremented_not_set(registry, cfg):
    hero = wizard(registry)
    hero.creature.resources["spell_slot:2"] = ResourcePool(current=3, max=3)
    engine = solo(registry, cfg, ScriptedRng(d4=[1] * 4), hero=hero)
    goblin_hp(engine)
    engine.perform("wiz", "cast:magic_missile:2:goblin_1")
    assert slot(engine, 2) == 2


def test_cast_log_line_is_exact_for_base_and_raised_circle(registry, cfg):
    engine = solo(registry, cfg, ScriptedRng(d8=[1] * 6))
    hurt(engine)
    engine.perform("wiz", "cast:cure_wounds:2:wiz")
    engine.part("wiz").turn.action = True
    engine.perform("wiz", "cast:cure_wounds:1:wiz")
    reads = [line for line in engine.state.log if "читает" in line]
    assert reads == ["Лиэль читает Лечение ран (2 круг)", "Лиэль читает Лечение ран"]


def test_magic_missile_event_and_damage_lines(registry, cfg):
    engine = solo(registry, cfg, ScriptedRng(d4=[2, 2, 2, 2]))
    goblin_hp(engine)
    events = engine.perform("wiz", "cast:magic_missile:2:goblin_1")
    assert [e.type for e in events] == ["attack"]
    assert events[0].data == {
        "attacker": "wiz", "target": "goblin_1", "weapon": "magic_missile", "mode": "spell",
        "outcome": "auto", "damage": 12,
    }
    darts = [line for line in engine.state.log if line.startswith("  Урон (Волшебная стрела)")]
    assert len(darts) == 4
    assert "1d4 (2) + 1 Волшебная стрела = 3" in darts[0]
    assert engine.state.log[-1] == "  Воин-гоблин: HP 28/40"


def test_magic_missile_can_drop_the_target(registry, cfg):
    engine = solo(registry, cfg, ScriptedRng(d4=[4, 4, 4, 4]))
    goblin_hp(engine, 10)
    engine.perform("wiz", "cast:magic_missile:2:goblin_1")
    assert engine.part("goblin_1").status != "active"


# провал проверки: событие и лог; заговор проверку не бросает

def test_wasted_cast_event_and_line(registry, cfg):
    engine = solo(registry, cfg, ScriptedRng(d20=[1]))
    engine.cast_checks.register(HardCheck())
    events = engine.perform("wiz", "cast:cure_wounds:2:wiz")
    assert [e.type for e in events] == ["spell_wasted"]
    assert events[0].data == {"id": "wiz", "spell": "cure_wounds"}
    assert "  заклинание не удалось, ячейка потрачена впустую" in engine.state.log


def test_cantrip_is_not_subject_to_the_cast_check(registry, cfg):
    engine = solo(registry, cfg, ScriptedRng(d20=[15], d10=[3]), hero_zone="door")
    engine.cast_checks.register(HardCheck())
    engine.perform("wiz", "cast:fire_bolt:0:goblin_1")
    assert not any("не удалось" in line for line in engine.state.log)


class ForbidCure:
    def check(self, caster, spell_id, registry):
        assert caster.id == "wiz"
        assert registry is not None
        if spell_id == "cure_wounds":
            return [CastCheck(kind="forbidden", reason="тест")]
        return []


def test_forbidden_spell_is_not_castable(registry, cfg):
    engine = solo(registry, cfg)
    engine.cast_checks.register(ForbidCure())
    ids = [s.id for s in cast.castable_spells(engine, "wiz")]
    assert "cure_wounds" not in ids
    assert "magic_missile" in ids


def test_cantrip_damage_grows_at_the_scaling_level(registry, cfg):
    hero = wizard(registry)
    hero.sheet.primary.level = 5
    engine = solo(registry, cfg, ScriptedRng(d20=[15], d10=[3, 4]), hero=hero, hero_zone="door")
    goblin_hp(engine)
    engine.perform("wiz", "cast:fire_bolt:0:goblin_1")
    assert hp(engine, "goblin_1") == 40 - 7


def test_cantrip_damage_is_base_below_the_scaling_level(registry, cfg):
    hero = wizard(registry)
    hero.sheet.primary.level = 4
    engine = solo(registry, cfg, ScriptedRng(d20=[15], d10=[3]), hero=hero, hero_zone="door")
    goblin_hp(engine)
    engine.perform("wiz", "cast:fire_bolt:0:goblin_1")
    assert hp(engine, "goblin_1") == 40 - 3


def test_bless_log_names_all_targets(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:bless:1:wiz,ally")
    assert "Лиэль: Благословение на Лиэль, Арн" in engine.state.log


def test_free_mark_decrements_a_larger_pool_by_one(registry, cfg):
    hero = make_ranger(registry)
    hero.creature.resources["favored_enemy"] = ResourcePool(current=3, max=3)
    engine = make_engine(
        registry, cfg, heroes=[(hero, "door")], monsters=GOBLIN, rng=ScriptedRng(),
        hero_zone="door",
    )
    engine.perform("hero", "cast:hunters_mark:1:goblin_1:free")
    assert creature(engine, "hero").resources["favored_enemy"].current == 2
