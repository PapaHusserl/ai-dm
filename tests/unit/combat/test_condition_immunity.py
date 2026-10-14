# Партия К7к, п. 1.3: иммунитет монстра к состояниям (docs/K7K-PLAN.md, В5а, Q4а).
#   Monster.condition_immunities -- id состояний (loader: должны быть в реестре condition);
#   CombatEngine.impose(ref, condition) -> bool: монстр с condition.id в списке состояния не
#   получает -- в лог «  <имя>: иммунитет к состоянию <название>», False; иначе состояние
#   добавляется существу, True (герою -- всегда).
#   Через impose идут три места, где движок кладёт состояние на цель: Topple (prone), импровизация
#   prone, Опутывающий удар (условие restrained). Спасбросок при этом бросается как обычно; при
#   отказе Опутывающий удар не кладёт ensnared-эффект и снимает концентрацию, как при успешном
#   спасброске. Состояние «на себя» и unconscious при 0 HP (downed.add_unconscious) -- не через
#   impose: ложатся и на «иммунного» (Q4а).
from combat_kit import (
    ScriptedRng,
    creature,
    give_weapon,
    hp,
    make_engine,
    make_fighter,
    mon,
    part,
    set_hp,
)
from test_damage_types import odd_registry
from test_ensnaring_strike import HIT, charged, charges, ensnares, restrained

from ai_dm.state.creature import AppliedCondition


def condition_ids(engine, ref):
    return [c.id for c in creature(engine, ref).conditions]


def lines(engine):
    return "\n".join(engine.state.log)


def staff_engine(registry, cfg, rng, **lists):
    # боевой посох героя с мастерством Topple (СЛ 13)
    hero = make_fighter(registry)
    give_weapon(hero, registry, "quarterstaff")
    hero.sheet.weapon_masteries = ["quarterstaff"]
    return make_engine(
        odd_registry(registry, **lists), cfg, heroes=[hero], rng=rng,
        monsters=[mon("goblin_1", "odd_goblin", "hall")],
    )


def duel(registry, cfg, rng, **lists):
    return make_engine(
        odd_registry(registry, **lists), cfg, heroes=[make_fighter(registry)], rng=rng,
        monsters=[mon("goblin_1", "odd_goblin", "hall")],
    )


def improvise(engine, effect):
    return engine.improvise(
        "hero", skill="athletics", category="medium", effect=effect, target="goblin_1"
    )


# impose

def test_impose_puts_the_condition_on_a_plain_monster(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng())
    assert engine.impose("goblin_1", AppliedCondition(id="prone", source="hero")) is True
    assert condition_ids(engine, "goblin_1") == ["prone"]


def test_impose_refuses_an_immune_monster(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(), condition_immunities=["prone"])
    assert engine.impose("goblin_1", AppliedCondition(id="prone", source="hero")) is False
    assert condition_ids(engine, "goblin_1") == []


def test_impose_logs_the_refusal_with_the_condition_name(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(), condition_immunities=["prone"])
    engine.impose("goblin_1", AppliedCondition(id="prone", source="hero"))
    assert "  Воин-гоблин: иммунитет к состоянию Лежит" in engine.state.log


def test_impose_of_another_condition_passes_an_immune_monster(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(), condition_immunities=["prone"])
    assert engine.impose("goblin_1", AppliedCondition(id="restrained", source="hero")) is True
    assert condition_ids(engine, "goblin_1") == ["restrained"]


def test_impose_keeps_the_condition_object_as_is(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng())
    condition = AppliedCondition(id="prone", source="hero")
    engine.impose("goblin_1", condition)
    assert creature(engine, "goblin_1").conditions == [condition]


def test_impose_on_a_named_npc_uses_the_statblock(registry, cfg):
    engine = make_engine(
        odd_registry(registry, condition_immunities=["prone"]), cfg,
        heroes=[make_fighter(registry)], rng=ScriptedRng(),
        monsters=[mon("goblin_1", "odd_goblin", "hall", named=True)],
    )
    assert engine.impose("goblin_1", AppliedCondition(id="prone", source="hero")) is False


def test_impose_on_a_hero_always_succeeds(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(), condition_immunities=["prone"])
    assert engine.impose("hero", AppliedCondition(id="prone", source="goblin_1")) is True
    assert condition_ids(engine, "hero") == ["prone"]


# Topple

def test_topple_knocks_down_a_monster_without_immunity(registry, cfg):
    engine = staff_engine(registry, cfg, ScriptedRng(d20=[15, 12], d6=[1]))
    engine.perform("hero", "attack:quarterstaff:goblin_1")
    assert condition_ids(engine, "goblin_1") == ["prone"]


def test_topple_prone_remembers_who_knocked_down(registry, cfg):
    engine = staff_engine(registry, cfg, ScriptedRng(d20=[15, 12], d6=[1]))
    engine.perform("hero", "attack:quarterstaff:goblin_1")
    assert [(c.id, c.source) for c in creature(engine, "goblin_1").conditions] == [
        ("prone", "hero")
    ]
    assert "Воин-гоблин сбит с ног" in lines(engine)


def test_topple_is_refused_by_immunity(registry, cfg):
    engine = staff_engine(
        registry, cfg, ScriptedRng(d20=[15, 12], d6=[1]), condition_immunities=["prone"]
    )
    engine.perform("hero", "attack:quarterstaff:goblin_1")
    assert condition_ids(engine, "goblin_1") == []
    assert "иммунитет к состоянию Лежит" in lines(engine)


def test_topple_refusal_does_not_log_the_knockdown(registry, cfg):
    engine = staff_engine(
        registry, cfg, ScriptedRng(d20=[15, 12], d6=[1]), condition_immunities=["prone"]
    )
    engine.perform("hero", "attack:quarterstaff:goblin_1")
    assert "сбит с ног" not in lines(engine)


def test_topple_against_an_immune_monster_still_deals_damage(registry, cfg):
    engine = staff_engine(
        registry, cfg, ScriptedRng(d20=[15, 12], d6=[1]), condition_immunities=["prone"]
    )
    engine.perform("hero", "attack:quarterstaff:goblin_1")
    assert hp(engine, "goblin_1") == 10 - 4


def test_topple_still_rolls_the_save_against_an_immune_monster(registry, cfg):
    rng = ScriptedRng(d20=[15, 12], d6=[1])
    engine = staff_engine(registry, cfg, rng, condition_immunities=["prone"])
    engine.perform("hero", "attack:quarterstaff:goblin_1")
    assert rng.left("d20") == 0


def test_topple_with_a_passed_save_does_not_log_the_immunity(registry, cfg):
    engine = staff_engine(
        registry, cfg, ScriptedRng(d20=[15, 13], d6=[1]), condition_immunities=["prone"]
    )
    engine.perform("hero", "attack:quarterstaff:goblin_1")
    assert "иммунитет к состоянию" not in lines(engine)


def test_topple_ignores_immunity_to_another_condition(registry, cfg):
    engine = staff_engine(
        registry, cfg, ScriptedRng(d20=[15, 12], d6=[1]), condition_immunities=["restrained"]
    )
    engine.perform("hero", "attack:quarterstaff:goblin_1")
    assert condition_ids(engine, "goblin_1") == ["prone"]


# импровизация prone

def test_improvised_prone_lands_on_a_monster_without_immunity(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10]))
    improvise(engine, "prone")
    assert condition_ids(engine, "goblin_1") == ["prone"]
    assert "Воин-гоблин сбит с ног" in lines(engine)


def test_improvised_prone_succeeds_but_the_condition_is_refused(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10]), condition_immunities=["prone"])
    improvise(engine, "prone")
    assert condition_ids(engine, "goblin_1") == []
    assert "иммунитет к состоянию Лежит" in lines(engine)
    assert "импровизация" in lines(engine)


def test_improvised_prone_refusal_does_not_log_the_knockdown(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10]), condition_immunities=["prone"])
    improvise(engine, "prone")
    assert "сбит с ног" not in lines(engine)


# Опутывающий удар

def ensnaring_registry_goblin(registry, **lists):
    return odd_registry(registry, **lists), [mon("goblin_1", "odd_goblin", "door")]


def strike(registry, cfg, **lists):
    reg, monsters = ensnaring_registry_goblin(registry, **lists)
    engine = charged(reg, cfg, ScriptedRng(d20=[15, 12], d6=[3]), monsters)
    engine.perform("hero", HIT)
    return engine


def test_ensnaring_strike_still_restrains_without_immunity(registry, cfg):
    engine = strike(registry, cfg)
    assert len(restrained(engine)) == 1
    assert len(ensnares(engine)) == 1


def test_ensnaring_strike_does_not_restrain_an_immune_monster(registry, cfg):
    engine = strike(registry, cfg, condition_immunities=["restrained"])
    assert restrained(engine) == []


def test_ensnaring_strike_puts_no_ensnared_effect_on_an_immune_monster(registry, cfg):
    engine = strike(registry, cfg, condition_immunities=["restrained"])
    assert ensnares(engine) == []


def test_ensnaring_strike_refusal_drops_the_concentration(registry, cfg):
    engine = strike(registry, cfg, condition_immunities=["restrained"])
    assert creature(engine, "hero").concentration is None


def test_ensnaring_strike_refusal_spends_the_charge(registry, cfg):
    engine = strike(registry, cfg, condition_immunities=["restrained"])
    assert charges(engine) == []


def test_ensnaring_strike_refusal_is_logged(registry, cfg):
    engine = strike(registry, cfg, condition_immunities=["restrained"])
    assert "иммунитет к состоянию Опутан" in lines(engine)


def test_ensnaring_strike_refusal_keeps_the_weapon_damage(registry, cfg):
    engine = strike(registry, cfg, condition_immunities=["restrained"])
    assert hp(engine, "goblin_1") == 40 - 6


def test_ensnaring_strike_ignores_immunity_to_another_condition(registry, cfg):
    engine = strike(registry, cfg, condition_immunities=["prone"])
    assert len(restrained(engine)) == 1


def test_ensnaring_strike_vines_do_not_hurt_after_refusal(registry, cfg):
    engine = strike(registry, cfg, condition_immunities=["restrained"])
    before = hp(engine, "goblin_1")
    engine.burn("goblin_1")
    assert hp(engine, "goblin_1") == before


# unconscious при 0 HP не проверяется (Q4а)

def test_unconscious_still_lands_on_an_immune_monster_at_zero_hp(registry, cfg):
    engine = duel(
        registry, cfg, ScriptedRng(d20=[15], d8=[4]), condition_immunities=["unconscious"]
    )
    set_hp(engine, "goblin_1", 1)
    engine.perform("hero", "attack:longsword:goblin_1:nonlethal")
    assert part(engine, "goblin_1").status == "down"
    assert condition_ids(engine, "goblin_1") == ["unconscious"]
