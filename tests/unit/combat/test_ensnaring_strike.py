# Опутывающий удар (docs/plan-combat-extras.md, разд. 3, ответы проектировщика 3 и уточнение
# оркестратора по SRD 5.2). Ожидаемый API:
#   spell_kind(ensnaring_strike) == "rider" (hunters_mark остаётся "mark")
#   cast:ensnaring_strike:1:<герой> -- бонусное действие, цель -- сам заклинатель, ячейка 1 круга,
#       concentration == "ensnaring_strike"; старая концентрация снимается;
#       на герое ActiveEffect(id="ensnaring_strike", kind="weapon_rider", expires=concentration)
#   попадание ОРУЖИЕМ (в т.ч. improvised) при заряде -- спасбросок Силы цели против СЛ заклинателя;
#       безоружный удар заряд не тратит; промах -- заряд остаётся
#   провал -- AppliedCondition restrained (expires=concentration) и на цели
#       ActiveEffect(kind="ensnared", params={dice, damage_type, dc}); заряд снят
#   успех -- заряд снят, концентрация кончилась
#   SRD 5.2: цель Large и больше бросает спасбросок с ПРЕИМУЩЕСТВОМ (не иммунитет)
#   начало хода опутанного -- 1d6 колющего (dice из params), источник -- заклинатель
#   escape:ensnaring_strike -- действие опутанного: проверка Силы (Атлетика) против СЛ;
#       успех -- restrained и ensnared сняты, концентрация заклинателя кончена; провал -- ничего
#   потеря концентрации снимает restrained и ensnared; ИИ монстра в restrained выбирает escape
# Заклинатель -- следопыт 2 ур. (СЛ 12, ячеек 1 круга 2, скимитар +5 / 1d6+3). Гоблин: КД 15,
# СИЛ 8 (-1) -- спасбросок и проверка проходят от 13 на d20; он стоит в зоне героя.
import pytest
from combat_kit import (
    ScriptedRng,
    creature,
    hp,
    make_engine,
    make_fighter,
    mon,
    option_ids,
    part,
    turn,
)
from test_ranger_combat import make_ranger, marks, pool, ranger_engine

from ai_dm.rules.spellcasting import spell_kind
from ai_dm.state.combat import Participant
from ai_dm.state.creature import ActiveEffect, AppliedCondition, Concentration, Expiry

CHARGE = "cast:ensnaring_strike:1:hero"
HIT = "attack:scimitar:goblin_1"
ESCAPE = "escape:ensnaring_strike"
HELD = Expiry(kind="concentration", owner="hero")
GOBLIN = [mon("goblin_1", "goblin_warrior", "door")]


def engine_with(registry, cfg, rng, monsters=None):
    hero = make_ranger(registry)
    hero.sheet.prepared_of()[:] = ["ensnaring_strike"]
    engine = ranger_engine(registry, cfg, rng, hero=hero, monsters=monsters or GOBLIN)
    creature(engine, "goblin_1").hp_current = 40
    creature(engine, "goblin_1").hp_max = 40
    return engine


def charged(registry, cfg, rng, monsters=None):
    engine = engine_with(registry, cfg, rng, monsters)
    engine.perform("hero", CHARGE)
    return engine


def ensnared_goblin(registry, cfg, rng):
    # заряд, попадание, проваленный спасбросок; в очереди rng d20 -- с первой проверки врага
    engine = charged(registry, cfg, ScriptedRng(d20=[15, 12] + rng, d6=[3]))
    engine.perform("hero", HIT)
    return engine


def charges(engine):
    return [e for e in creature(engine, "hero").active_effects if e.id == "ensnaring_strike"]


def ensnares(engine, ref="goblin_1"):
    return [e for e in creature(engine, ref).active_effects if e.kind == "ensnared"]


def restrained(engine, ref="goblin_1"):
    return [c for c in creature(engine, ref).conditions if c.id == "restrained"]


# вид заклинания

def test_ensnaring_strike_is_a_rider(registry):
    assert spell_kind(registry.get("spell", "ensnaring_strike")) == "rider"


def test_hunters_mark_is_still_a_mark(registry):
    assert spell_kind(registry.get("spell", "hunters_mark")) == "mark"


# сотворение

def test_charge_is_offered_to_the_caster_himself(registry, cfg):
    engine = engine_with(registry, cfg, ScriptedRng())
    assert CHARGE in option_ids(engine, "hero")


def test_charge_has_no_enemy_targets(registry, cfg):
    ids = option_ids(engine_with(registry, cfg, ScriptedRng()), "hero")
    assert "cast:ensnaring_strike:1:goblin_1" not in ids


def test_charge_costs_the_bonus_action(registry, cfg):
    engine = engine_with(registry, cfg, ScriptedRng())
    option = next(o for o in engine.available_actions("hero") if o.id == CHARGE)
    assert option.cost == "bonus"
    assert "Опутывающий удар" in option.label


def test_charge_spends_bonus_action_and_keeps_the_action(registry, cfg):
    engine = charged(registry, cfg, ScriptedRng())
    assert turn(engine, "hero").bonus is False
    assert turn(engine, "hero").action is True


def test_charge_spends_a_slot(registry, cfg):
    engine = charged(registry, cfg, ScriptedRng())
    assert pool(engine, "spell_slot:1").current == 1


def test_charge_sets_concentration_and_the_rider_effect(registry, cfg):
    engine = charged(registry, cfg, ScriptedRng())
    assert creature(engine, "hero").concentration.spell_id == "ensnaring_strike"
    assert [e.kind for e in charges(engine)] == ["weapon_rider"]
    assert charges(engine)[0].expires == Expiry(kind="concentration", owner="hero")


def test_charge_is_not_offered_without_bonus_action(registry, cfg):
    engine = engine_with(registry, cfg, ScriptedRng())
    turn(engine, "hero").bonus = False
    assert CHARGE not in option_ids(engine, "hero")


def test_charge_is_not_offered_without_slots(registry, cfg):
    engine = engine_with(registry, cfg, ScriptedRng())
    pool(engine, "spell_slot:1").current = 0
    assert CHARGE not in option_ids(engine, "hero")


def test_charge_drops_the_old_concentration(registry, cfg):
    engine = engine_with(registry, cfg, ScriptedRng())
    engine.perform("hero", "cast:hunters_mark:1:goblin_1")
    turn(engine, "hero").bonus = True
    engine.perform("hero", CHARGE)
    assert marks(engine, "goblin_1") == []
    assert creature(engine, "hero").concentration.spell_id == "ensnaring_strike"


def test_hunters_mark_drops_the_charge(registry, cfg):
    engine = charged(registry, cfg, ScriptedRng())
    turn(engine, "hero").bonus = True
    engine.perform("hero", "cast:hunters_mark:1:goblin_1")
    assert charges(engine) == []


# попадание: провал спасброска

def test_hit_with_a_weapon_makes_a_strength_save(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [])
    assert any("спасбросок str" in line for line in engine.state.log)


def test_failed_save_restrains_the_target(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [])
    assert len(restrained(engine)) == 1
    assert restrained(engine)[0].expires == Expiry(kind="concentration", owner="hero")


def test_failed_save_puts_the_ensnared_effect_with_the_save_dc(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [])
    effect = ensnares(engine)[0]
    assert effect.source == "hero"
    assert effect.params["dice"] == "1d6"
    assert effect.params["damage_type"] == "piercing"
    assert effect.params["dc"] == 12
    assert effect.expires == Expiry(kind="concentration", owner="hero")


def test_failed_save_spends_the_charge_and_keeps_concentration(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [])
    assert charges(engine) == []
    assert creature(engine, "hero").concentration.spell_id == "ensnaring_strike"


def test_save_one_below_the_dc_fails(registry, cfg):
    # 12 + (-1) = 11 < 12
    engine = ensnared_goblin(registry, cfg, [])
    assert restrained(engine)


def test_the_hit_itself_still_deals_weapon_damage(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [])
    assert hp(engine, "goblin_1") == 40 - 6


# попадание: успех спасброска

def test_save_exactly_at_the_dc_succeeds(registry, cfg):
    engine = charged(registry, cfg, ScriptedRng(d20=[15, 13], d6=[3]))
    engine.perform("hero", HIT)
    assert restrained(engine) == []
    assert ensnares(engine) == []


def test_successful_save_still_spends_the_charge_and_ends_concentration(registry, cfg):
    engine = charged(registry, cfg, ScriptedRng(d20=[15, 13], d6=[3]))
    engine.perform("hero", HIT)
    assert charges(engine) == []
    assert creature(engine, "hero").concentration is None


# промах и не-оружие

def test_miss_keeps_the_charge_and_rolls_no_save(registry, cfg):
    rng = ScriptedRng(d20=[2])
    engine = charged(registry, cfg, rng)
    engine.perform("hero", HIT)
    assert len(charges(engine)) == 1
    assert creature(engine, "hero").concentration.spell_id == "ensnaring_strike"
    assert restrained(engine) == []


def test_unarmed_hit_does_not_use_the_charge(registry, cfg):
    engine = charged(registry, cfg, ScriptedRng(d20=[15]))
    engine.perform("hero", "attack:unarmed:goblin_1")
    assert len(charges(engine)) == 1
    assert restrained(engine) == []


def test_improvised_weapon_hit_uses_the_charge(registry, cfg):
    # бонус без мастерства: +1 (СИЛ 12); 14 + 1 = 15 = КД
    engine = charged(registry, cfg, ScriptedRng(d20=[14, 12], d4=[2]))
    engine.perform("hero", "attack:improvised:goblin_1")
    assert charges(engine) == []
    assert len(restrained(engine)) == 1


def test_hit_without_a_charge_makes_no_save(registry, cfg):
    # обычное попадание без заряда: никаких спасбросков
    engine = engine_with(registry, cfg, ScriptedRng(d20=[15], d6=[3]))
    engine.perform("hero", HIT)
    assert restrained(engine) == []


# размер цели: SRD 5.2 -- Large и больше бросают с преимуществом

def test_medium_target_saves_without_advantage(registry, cfg, monkeypatch):
    monkeypatch.setattr(registry.get("monster", "goblin_warrior"), "size", "medium")
    rng = ScriptedRng(d20=[15, 12, 18], d6=[3])
    engine = charged(registry, cfg, rng)
    engine.perform("hero", HIT)
    assert rng.left("d20") == 1
    assert len(restrained(engine)) == 1


@pytest.mark.parametrize("size", ["large", "huge", "gargantuan"])
def test_large_or_bigger_target_saves_with_advantage(registry, cfg, monkeypatch, size):
    monkeypatch.setattr(registry.get("monster", "goblin_warrior"), "size", size)
    rng = ScriptedRng(d20=[15, 5, 18], d6=[3])
    engine = charged(registry, cfg, rng)
    engine.perform("hero", HIT)
    assert rng.left("d20") == 0
    assert restrained(engine) == []


@pytest.mark.parametrize("size", ["large", "huge", "gargantuan"])
def test_large_target_is_not_immune_it_can_still_fail(registry, cfg, monkeypatch, size):
    monkeypatch.setattr(registry.get("monster", "goblin_warrior"), "size", size)
    engine = charged(registry, cfg, ScriptedRng(d20=[15, 5, 7], d6=[3]))
    engine.perform("hero", HIT)
    assert len(restrained(engine)) == 1
    assert charges(engine) == []


def test_small_target_saves_without_advantage(registry, cfg):
    rng = ScriptedRng(d20=[15, 5, 18], d6=[3])
    engine = charged(registry, cfg, rng)
    engine.perform("hero", HIT)
    assert rng.left("d20") == 1


# урон в начале хода

def test_ensnared_target_takes_piercing_damage_at_the_start_of_its_turn(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [])
    before = hp(engine, "goblin_1")
    engine.rng.queues["d6"] = [4]
    engine.start_turn("goblin_1")
    assert hp(engine, "goblin_1") == before - 4


def test_upcast_charge_deals_one_die_per_slot_level(registry, cfg):
    engine = engine_with(registry, cfg, ScriptedRng(d6=[3, 4]))
    creature(engine, "goblin_1").conditions.append(
        AppliedCondition(id="restrained", source="hero", expires=HELD)
    )
    creature(engine, "goblin_1").active_effects.append(
        ActiveEffect(
            id="ensnaring_strike", source="hero", kind="ensnared",
            params={"dice": "2d6", "damage_type": "piercing", "dc": 12},
            expires=HELD,
        )
    )
    engine.start_turn("goblin_1")
    assert hp(engine, "goblin_1") == 33


def test_ensnared_damage_can_drop_the_target(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [])
    creature(engine, "goblin_1").hp_current = 3
    engine.rng.queues["d6"] = [4]
    engine.start_turn("goblin_1")
    assert part(engine, "goblin_1").status != "active"


def test_no_damage_to_a_free_target(registry, cfg):
    engine = charged(registry, cfg, ScriptedRng())
    engine.start_turn("goblin_1")
    assert hp(engine, "goblin_1") == 40


# вырваться

def test_escape_is_offered_to_the_ensnared_target(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [])
    options = engine.available_actions("goblin_1")
    escape = [o for o in options if o.id == ESCAPE]
    assert [o.cost for o in escape] == ["action"]


def test_escape_is_not_offered_to_a_free_target(registry, cfg):
    engine = charged(registry, cfg, ScriptedRng())
    assert not [i for i in option_ids(engine, "goblin_1") if i.startswith("escape")]


def test_escape_is_not_offered_without_the_action(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [])
    turn(engine, "goblin_1").action = False
    assert ESCAPE not in option_ids(engine, "goblin_1")


def test_successful_escape_frees_the_target(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [13])
    engine.perform("goblin_1", ESCAPE)
    assert restrained(engine) == []
    assert ensnares(engine) == []


def test_successful_escape_ends_the_concentration_of_the_caster(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [13])
    engine.perform("goblin_1", ESCAPE)
    assert creature(engine, "hero").concentration is None


def test_escape_spends_the_action(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [13])
    engine.perform("goblin_1", ESCAPE)
    assert turn(engine, "goblin_1").action is False


def test_failed_escape_spends_the_action_and_changes_nothing(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [12])
    engine.perform("goblin_1", ESCAPE)
    assert turn(engine, "goblin_1").action is False
    assert len(restrained(engine)) == 1
    assert len(ensnares(engine)) == 1
    assert creature(engine, "hero").concentration.spell_id == "ensnaring_strike"


def test_freed_target_takes_no_more_damage(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [13])
    engine.perform("goblin_1", ESCAPE)
    before = hp(engine, "goblin_1")
    engine.start_turn("goblin_1")
    assert hp(engine, "goblin_1") == before


def test_hero_escapes_with_a_strength_check(registry, cfg):
    # воин (СИЛ +3) опутан следопытом-союзником: 15 + 3 против СЛ 12 -- успех
    hero = make_ranger(registry)
    hero.sheet.prepared_of()[:] = ["ensnaring_strike"]
    engine = ranger_engine(registry, cfg, ScriptedRng(d20=[15]), hero=hero)
    engine.heroes["fighter"] = make_fighter(registry, "fighter")
    engine.state.participants.append(
        Participant(ref="fighter", side="heroes", group_id="party", zone_id="door")
    )
    victim = engine.heroes["fighter"].creature
    victim.conditions.append(
        AppliedCondition(id="restrained", source="hero", expires=HELD)
    )
    victim.active_effects.append(
        ActiveEffect(
            id="ensnaring_strike", source="hero", kind="ensnared",
            params={"dice": "1d6", "damage_type": "piercing", "dc": 12},
            expires=HELD,
        )
    )
    creature(engine, "hero").concentration = Concentration(spell_id="ensnaring_strike", circle=1)
    engine.perform("fighter", ESCAPE)
    assert victim.conditions == []
    assert victim.active_effects == []


# ИИ

def test_monster_ai_escapes_when_restrained(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [13])
    engine.run_controller("goblin_1")
    assert restrained(engine) == []


def test_monster_ai_does_not_escape_when_free(registry, cfg):
    engine = charged(registry, cfg, ScriptedRng(d20=[10], d6=[3]))
    engine.run_controller("goblin_1")
    assert creature(engine, "hero").concentration.spell_id == "ensnaring_strike"


# потеря концентрации

def test_dropping_concentration_frees_the_target(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [])
    creature(engine, "hero").concentration = None
    engine.drop_concentration_effects("hero")
    assert restrained(engine) == []
    assert ensnares(engine) == []


def test_dropping_concentration_keeps_foreign_conditions(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [])
    creature(engine, "goblin_1").conditions.append(AppliedCondition(id="prone", source="hero"))
    creature(engine, "hero").concentration = None
    engine.drop_concentration_effects("hero")
    assert [c.id for c in creature(engine, "goblin_1").conditions] == ["prone"]


def test_dropping_another_casters_concentration_keeps_the_restraint(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [])
    engine.drop_concentration_effects("someone_else")
    assert len(restrained(engine)) == 1


def test_failed_concentration_save_frees_the_target(registry, cfg):
    # опутанный гоблин бьёт героя с помехой (19 и 19), урон 3 + 2; спасбросок концентрации -- провал
    engine = charged(registry, cfg, ScriptedRng(d20=[15, 12, 19, 19, 2], d6=[3, 3]))
    engine.perform("hero", HIT)
    assert len(restrained(engine)) == 1
    engine.perform("goblin_1", "attack:скимитар:hero")
    assert restrained(engine) == []
    assert ensnares(engine) == []
    assert creature(engine, "hero").concentration is None


def test_held_concentration_save_keeps_the_target_restrained(registry, cfg):
    engine = charged(registry, cfg, ScriptedRng(d20=[15, 12, 19, 19, 18], d6=[3, 3]))
    engine.perform("hero", HIT)
    engine.perform("goblin_1", "attack:скимитар:hero")
    assert len(restrained(engine)) == 1
    assert creature(engine, "hero").concentration.spell_id == "ensnaring_strike"


# решения кабана (docs/plan-combat-extras.md, п. 5-7)

def test_charge_is_kept_when_the_hit_drops_the_target(registry, cfg):
    second = mon("goblin_2", "goblin_warrior", "hall")
    engine = charged(registry, cfg, ScriptedRng(d20=[15], d6=[3]), GOBLIN + [second])
    creature(engine, "goblin_1").hp_current = 1
    engine.perform("hero", HIT)
    assert len(charges(engine)) == 1
    assert restrained(engine) == []


def test_ensnared_target_has_no_move_options(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [])
    assert not [i for i in option_ids(engine, "goblin_1") if i.startswith("move:")]


def test_free_target_keeps_move_options(registry, cfg):
    engine = charged(registry, cfg, ScriptedRng())
    assert [i for i in option_ids(engine, "goblin_1") if i.startswith("move:")]


def test_end_of_combat_frees_the_target_and_ends_the_concentration(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [])
    engine.end_combat()
    assert restrained(engine) == []
    assert ensnares(engine) == []
    assert creature(engine, "hero").concentration is None


# мутанты: подробности состояния, строки лога, размер цели героя

def test_target_size_of_a_monster_is_its_size(registry, cfg):
    from ai_dm.combat.actions.attack import target_size
    engine = engine_with(registry, cfg, ScriptedRng())
    assert target_size(engine, "goblin_1") == "small"


def test_target_size_of_a_hero_is_the_size_of_his_species(registry, cfg):
    from ai_dm.combat.actions.attack import target_size
    engine = engine_with(registry, cfg, ScriptedRng())
    species = engine.heroes["hero"].sheet.species_id
    assert target_size(engine, "hero") == registry.get("species", species).size


def test_charge_is_used_when_the_target_is_left_with_one_hit_point(registry, cfg):
    engine = charged(registry, cfg, ScriptedRng(d20=[15, 12], d6=[3]))
    creature(engine, "goblin_1").hp_current = 7
    engine.perform("hero", HIT)
    assert hp(engine, "goblin_1") == 1
    assert charges(engine) == []
    assert len(restrained(engine)) == 1


def test_restraint_is_laid_by_the_caster(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [])
    assert restrained(engine)[0].source == "hero"


def test_charge_remembers_the_circle(registry, cfg):
    engine = charged(registry, cfg, ScriptedRng())
    assert charges(engine)[0].params["circle"] == 1
    assert charges(engine)[0].params["ability"] == "str"


def test_log_says_the_target_is_ensnared(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [])
    assert any("опутан" in line for line in engine.state.log)


def test_log_says_the_target_shook_the_vines_off(registry, cfg):
    engine = charged(registry, cfg, ScriptedRng(d20=[15, 13], d6=[3]))
    engine.perform("hero", HIT)
    assert any("стряхивает лозы" in line for line in engine.state.log)


def test_escape_line_shows_the_strength_bonus_and_the_result(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [13])
    engine.perform("goblin_1", ESCAPE)
    line = next(line for line in engine.state.log if "вырывается" in line)
    assert "Проверка Сил: d20 (13) - 1 Сил = 12 против СЛ 12" in line
    assert any("свободен" in line for line in engine.state.log)


def test_poisoned_monster_escapes_with_disadvantage(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [18, 5])
    creature(engine, "goblin_1").conditions.append(AppliedCondition(id="poisoned", source="x"))
    engine.perform("goblin_1", ESCAPE)
    assert len(restrained(engine)) == 1
    assert engine.rng.left("d20") == 0


def test_poisoned_hero_escapes_with_disadvantage(registry, cfg):
    hero = make_ranger(registry)
    engine = ranger_engine(registry, cfg, ScriptedRng(d20=[18, 5]), hero=hero)
    victim = engine.heroes["hero"].creature
    victim.conditions.append(AppliedCondition(id="poisoned", source="x"))
    victim.conditions.append(AppliedCondition(id="restrained", source="goblin_1", expires=HELD))
    victim.active_effects.append(
        ActiveEffect(
            id="ensnaring_strike", source="goblin_1", kind="ensnared",
            params={"dice": "1d6", "damage_type": "piercing", "dc": 20}, expires=HELD,
        )
    )
    engine.perform("hero", ESCAPE)
    assert engine.rng.left("d20") == 0
    assert [c.id for c in victim.conditions if c.id == "restrained"] == ["restrained"]


def test_escape_option_is_found_after_other_effects_on_the_target(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [])
    effects = creature(engine, "goblin_1").active_effects
    effects.insert(0, ActiveEffect(id="dodge", source="goblin_1", kind="modifier"))
    assert ESCAPE in option_ids(engine, "goblin_1")


def test_escape_option_names_the_spell_and_the_dc(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [])
    option = next(o for o in engine.available_actions("goblin_1") if o.id == ESCAPE)
    assert option.params == {"spell": "ensnaring_strike"}
    assert "Опутывающий удар" in option.label
    assert "СЛ 12" in option.label


def test_shaking_the_vines_off_names_the_spell(registry, cfg):
    engine = charged(registry, cfg, ScriptedRng(d20=[15, 13], d6=[3]))
    engine.perform("hero", HIT)
    assert any("Опутывающий удар кончается" in line for line in engine.state.log)


# ревью mama-kaban: СЛ, урон, побег, конец боя, тактика

def strong_caster(registry, cfg, rng, wis=18):
    # Мдр 18 (+4): СЛ заклинателя 8 + 2 + 4 = 14
    hero = make_ranger(registry)
    hero.sheet.prepared_of()[:] = ["ensnaring_strike"]
    hero.sheet.abilities["wis"] = wis
    engine = ranger_engine(registry, cfg, rng, hero=hero, monsters=GOBLIN)
    creature(engine, "goblin_1").hp_current = 40
    creature(engine, "goblin_1").hp_max = 40
    engine.perform("hero", CHARGE)
    engine.perform("hero", HIT)
    return engine


def test_ensnared_dc_is_the_spell_save_dc_of_the_caster(registry, cfg):
    engine = strong_caster(registry, cfg, ScriptedRng(d20=[15, 12], d6=[3]))
    assert ensnares(engine)[0].params["dc"] == 14


def test_escape_success_threshold_follows_the_casters_dc(registry, cfg):
    # проверка гоблина: d20 - 1; СЛ 14 -> 15 проходит
    engine = strong_caster(registry, cfg, ScriptedRng(d20=[15, 12, 15], d6=[3]))
    engine.perform("goblin_1", ESCAPE)
    assert restrained(engine) == []


def test_escape_below_the_casters_dc_fails(registry, cfg):
    engine = strong_caster(registry, cfg, ScriptedRng(d20=[15, 12, 14], d6=[3]))
    engine.perform("goblin_1", ESCAPE)
    assert len(restrained(engine)) == 1


def test_escape_line_of_a_monster_shows_the_dc_and_the_failure(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [12])
    engine.perform("goblin_1", ESCAPE)
    line = next(line for line in engine.state.log if "вырывается" in line)
    assert "d20 (12) - 1 Сил = 11 против СЛ 12" in line
    assert "провал" in line


def test_ensnared_damage_line_is_piercing(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [])
    engine.rng.queues["d6"] = [4]
    engine.start_turn("goblin_1")
    assert "  Опутывающий удар: 1d6 (4) колющий" in engine.state.log


def test_successful_save_ends_every_effect_of_the_concentration(registry, cfg):
    # лоз на втором враге нет, но чужой эффект этой же концентрации снимается вместе с ней
    second = mon("goblin_2", "goblin_warrior", "hall")
    engine = charged(registry, cfg, ScriptedRng(d20=[15, 13], d6=[3]), GOBLIN + [second])
    creature(engine, "goblin_2").active_effects.append(
        ActiveEffect(id="ensnaring_strike", source="hero", kind="ensnared", expires=HELD)
    )
    engine.perform("hero", HIT)
    assert creature(engine, "goblin_2").active_effects == []


def test_flee_is_not_offered_to_an_ensnared_target(registry, cfg):
    engine = ensnared_goblin(registry, cfg, [])
    engine.state.zones[0].exit = True
    assert "flee" not in option_ids(engine, "goblin_1")


def test_flee_is_offered_to_a_free_target_in_the_exit_zone(registry, cfg):
    engine = charged(registry, cfg, ScriptedRng())
    engine.state.zones[0].exit = True
    assert "flee" in option_ids(engine, "goblin_1")


def test_victory_ends_an_unused_charge_and_the_concentration(registry, cfg):
    engine = charged(registry, cfg, ScriptedRng(d20=[15], d6=[3]))
    creature(engine, "goblin_1").hp_current = 1
    engine.perform("hero", HIT)
    assert engine.state.outcome == "victory"
    assert charges(engine) == []
    assert creature(engine, "hero").concentration is None


def test_victory_does_not_end_a_concentration_that_is_not_a_rider(registry, cfg):
    engine = engine_with(registry, cfg, ScriptedRng(d20=[15], d6=[3, 3]))
    engine.perform("hero", "cast:hunters_mark:1:goblin_1")
    creature(engine, "goblin_1").hp_current = 1
    engine.perform("hero", HIT)
    assert engine.state.outcome == "victory"
    assert creature(engine, "hero").concentration.spell_id == "hunters_mark"


def test_tactics_do_not_throw_improvised_items(registry, cfg):
    # враг на соседней зоне: бросок подручного доступен, но авто-герой его не берёт
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=ScriptedRng(),
        monsters=[mon("goblin_1", "goblin_warrior", "balcony")], hero_zone="hall",
    )
    options = engine.available_actions("hero")
    assert "attack:improvised_thrown:goblin_1" in [o.id for o in options]
    choice = engine.controllers["hero"].choose_turn(options, "hero")
    assert not choice.startswith("attack:improvised")


def test_tactics_do_not_swing_improvised_items_instead_of_the_weapon(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=ScriptedRng(),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    options = engine.available_actions("hero")
    assert engine.controllers["hero"].choose_turn(options, "hero") == "attack:longsword:goblin_1"
