# Партия К7д, п. 2.4-2.5: механические черты монстров (docs/plan-k7d.md).
#   Тактика стаи (pack_tactics в Monster.traits): атака монстра с этой чертой по цели имеет
#   преимущество «тактика стаи», если в зоне ЦЕЛИ есть боеспособный союзник атакующего (той же
#   стороны, не он сам; не мёртвый, не лежащий, не недееспособный). Работает и для дальних атак:
#   преимущество и помеха «дальность» гасят друг друга. Без черты и у героев -- нет.
#   Стойкость нежити (undead_fortitude): урон довёл монстра до 0 HP -- спасбросок Тел СЛ 5 + урон;
#   успех -- 1 HP и жив; провал -- смерть (monster_died). Не срабатывает: урон излучением (в том
#   числе в составе сложенного урона), критическое попадание, урон не довёл до 0, герой.
#   DamageResult.damage_types: list[str] -- типы урона, apply_damage пишет свой, merge_damage
#   склеивает списки.
# Волк-копия: КД 8 у цели-монстра, +5 к атаке; герой-воин: КД 19, d20 15+5 -- попадание.
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
    move_to,
    part,
    set_hp,
)

from ai_dm.combat import downed
from ai_dm.combat.actions.attack import merge_damage
from ai_dm.rules.damage import apply_damage
from ai_dm.state.combat import Zone
from ai_dm.state.creature import AppliedCondition

ZONES = [
    Zone(id="hall", name="Зал", adjacent=["yard"]),
    Zone(id="yard", name="Двор", adjacent=["hall", "far"]),
    Zone(id="far", name="Даль", adjacent=["yard"]),
]
SHOOT = bite(name="Spit", kind="ranged", range_normal_ft=20, range_long_ft=60, reach_ft=None)


def pack(registry, cfg, rng, allies=("hall",), trait=True, action=None, zones=ZONES):
    # герой в hall; волки wolf_1.. в зонах allies (первый -- атакующий, если не задан иной)
    traits = ["pack_tactics"] if trait else []
    reg = custom_registry(registry, wolf={"traits": traits, "actions": [action or bite()]})
    monsters = [mon(f"wolf_{i + 1}", "wolf", zone) for i, zone in enumerate(allies)]
    return make_engine(
        reg, cfg, heroes=[(make_fighter(registry), "hall")], rng=rng, monsters=monsters,
        zones=zones,
    )


def strike(engine, ref="wolf_1", action="bite"):
    return engine.perform(ref, f"attack:{action}:hero")


def test_ally_in_target_zone_gives_advantage(registry, cfg):
    # d20 [2, 15]: с преимуществом берётся 15 + 5 = 20 >= КД 19; без -- 2 мимо
    rng = ScriptedRng(d20=[2, 15], d6=[1])
    engine = pack(registry, cfg, rng, allies=("hall", "hall"))
    strike(engine)
    assert hp(engine, "hero") == 12 - 1


def test_advantage_is_named_in_the_log(registry, cfg):
    engine = pack(registry, cfg, ScriptedRng(d20=[2, 15], d6=[1]), allies=("hall", "hall"))
    strike(engine)
    assert "тактика стаи" in "\n".join(engine.state.log)


def test_no_ally_means_one_die(registry, cfg):
    rng = ScriptedRng(d20=[15], d6=[1])
    engine = pack(registry, cfg, rng, allies=("hall",))
    strike(engine)
    assert rng.left("d20") == 0


def test_no_ally_no_advantage(registry, cfg):
    engine = pack(registry, cfg, ScriptedRng(d20=[2]), allies=("hall",))
    strike(engine)
    assert hp(engine, "hero") == 12


def test_ally_in_another_zone_gives_nothing(registry, cfg):
    engine = pack(registry, cfg, ScriptedRng(d20=[2]), allies=("hall", "yard"))
    strike(engine)
    assert hp(engine, "hero") == 12


def test_monster_without_the_trait_gets_no_advantage(registry, cfg):
    rng = ScriptedRng(d20=[2])
    engine = pack(registry, cfg, rng, allies=("hall", "hall"), trait=False)
    strike(engine)
    assert hp(engine, "hero") == 12


def test_dead_ally_does_not_count(registry, cfg):
    engine = pack(registry, cfg, ScriptedRng(d20=[2]), allies=("hall", "hall"))
    part(engine, "wolf_2").status = "dead"
    set_hp(engine, "wolf_2", 0)
    strike(engine)
    assert hp(engine, "hero") == 12


def test_downed_ally_does_not_count(registry, cfg):
    engine = pack(registry, cfg, ScriptedRng(d20=[2]), allies=("hall", "hall"))
    part(engine, "wolf_2").status = "down"
    set_hp(engine, "wolf_2", 0)
    strike(engine)
    assert hp(engine, "hero") == 12


def test_ally_on_zero_hp_does_not_count(registry, cfg):
    engine = pack(registry, cfg, ScriptedRng(d20=[2]), allies=("hall", "hall"))
    set_hp(engine, "wolf_2", 0)
    strike(engine)
    assert hp(engine, "hero") == 12


@pytest.mark.parametrize("condition", ["incapacitated", "paralyzed", "stunned", "unconscious"])
def test_incapacitated_ally_does_not_count(registry, cfg, condition):
    engine = pack(registry, cfg, ScriptedRng(d20=[2]), allies=("hall", "hall"))
    creature(engine, "wolf_2").conditions.append(AppliedCondition(id=condition, source="x"))
    strike(engine)
    assert hp(engine, "hero") == 12


def test_the_attacker_is_not_its_own_ally(registry, cfg):
    rng = ScriptedRng(d20=[2])
    engine = pack(registry, cfg, rng, allies=("hall",))
    strike(engine)
    assert rng.left("d20") == 0


def test_ally_of_the_target_does_not_count(registry, cfg):
    # второй герой в зоне цели -- союзник цели, не атакующего
    second = make_fighter(registry, "hero2")
    reg = custom_registry(registry, wolf={"traits": ["pack_tactics"], "actions": [bite()]})
    engine = make_engine(
        reg, cfg, heroes=[(make_fighter(registry), "hall"), (second, "hall")],
        monsters=[mon("wolf_1", "wolf", "hall")], rng=ScriptedRng(d20=[2]),
    )
    strike(engine)
    assert hp(engine, "hero") == 12


def test_ally_moved_away_stops_counting(registry, cfg):
    engine = pack(registry, cfg, ScriptedRng(d20=[2]), allies=("hall", "hall"))
    move_to(engine, "wolf_2", "yard")
    strike(engine)
    assert hp(engine, "hero") == 12


def test_pack_advantage_cancels_range_disadvantage(registry, cfg):
    # стреляет из соседней зоны (дальность -- помеха), союзник у цели -- одна кость
    rng = ScriptedRng(d20=[15], d6=[1])
    engine = pack(registry, cfg, rng, allies=("yard", "hall"), action=SHOOT)
    strike(engine, action="spit")
    assert (rng.left("d20"), hp(engine, "hero")) == (0, 12 - 1)


def test_range_disadvantage_without_ally_takes_two_dice(registry, cfg):
    rng = ScriptedRng(d20=[15, 2])
    engine = pack(registry, cfg, rng, allies=("yard", "yard"), action=SHOOT)
    strike(engine, action="spit")
    assert (rng.left("d20"), hp(engine, "hero")) == (0, 12)


# Стойкость нежити

def zombie(registry, cfg, rng, monster_hp=4, **fields):
    data = {"hp": monster_hp, "ac": 8, "traits": ["undead_fortitude"], "creature_type": "undead"}
    data["abilities"] = {"str": 10, "dex": 10, "con": 16, "int": 10, "wis": 10, "cha": 10}
    data.update(fields)
    reg = custom_registry(registry, zombie=data)
    return make_engine(
        reg, cfg, heroes=[make_fighter(registry)], rng=rng,
        monsters=[mon("zombie_1", "zombie", "hall")],
    )


def hit_zombie(engine):
    return engine.perform("hero", "attack:longsword:zombie_1")


def kinds(events):
    return [e.type for e in events]


def test_fortitude_save_success_leaves_one_hp(registry, cfg):
    # урон 1d8 + 3 = 4 до 0; СЛ 5 + 4 = 9; Тел +3: d20 6 -> 9 -- успех
    engine = zombie(registry, cfg, ScriptedRng(d20=[15, 6], d8=[1]))
    hit_zombie(engine)
    assert (hp(engine, "zombie_1"), part(engine, "zombie_1").status) == (1, "active")


def test_fortitude_success_no_death_event(registry, cfg):
    engine = zombie(registry, cfg, ScriptedRng(d20=[15, 6], d8=[1]))
    assert "monster_died" not in kinds(hit_zombie(engine))


def test_fortitude_save_failure_kills(registry, cfg):
    # d20 5 -> 8 < 9
    engine = zombie(registry, cfg, ScriptedRng(d20=[15, 5], d8=[1]))
    events = hit_zombie(engine)
    assert ("monster_died" in kinds(events), part(engine, "zombie_1").status) == (True, "dead")


def test_fortitude_dc_grows_with_damage(registry, cfg):
    # урон 1d8 + 3 = 8 -> СЛ 13; d20 10 -> 13 -- успех
    engine = zombie(registry, cfg, ScriptedRng(d20=[15, 10], d8=[5]), monster_hp=8)
    hit_zombie(engine)
    assert hp(engine, "zombie_1") == 1


def test_fortitude_dc_boundary_fails_one_below(registry, cfg):
    engine = zombie(registry, cfg, ScriptedRng(d20=[15, 9], d8=[5]), monster_hp=8)
    hit_zombie(engine)
    assert part(engine, "zombie_1").status == "dead"


def test_fortitude_is_logged(registry, cfg):
    engine = zombie(registry, cfg, ScriptedRng(d20=[15, 6], d8=[1]))
    hit_zombie(engine)
    assert "Стойкость нежити" in "\n".join(engine.state.log)


def test_fortitude_not_triggered_if_not_dropped(registry, cfg):
    rng = ScriptedRng(d20=[15], d8=[1])
    engine = zombie(registry, cfg, rng, monster_hp=10)
    hit_zombie(engine)
    assert (hp(engine, "zombie_1"), rng.left("d20")) == (6, 0)


def test_critical_hit_skips_fortitude(registry, cfg):
    rng = ScriptedRng(d20=[20], d8=[1, 1])
    engine = zombie(registry, cfg, rng)
    events = hit_zombie(engine)
    assert ("monster_died" in kinds(events), rng.left("d20")) == (True, 0)


def test_nonlethal_hit_still_rolls_the_save_and_success_keeps_one_hp(registry, cfg):
    engine = zombie(registry, cfg, ScriptedRng(d20=[15, 6], d8=[1]))
    engine.perform("hero", "attack:longsword:zombie_1:nonlethal")
    assert (hp(engine, "zombie_1"), part(engine, "zombie_1").status) == (1, "active")


def test_nonlethal_hit_with_a_failed_save_knocks_out(registry, cfg):
    engine = zombie(registry, cfg, ScriptedRng(d20=[15, 5], d8=[1]))
    engine.perform("hero", "attack:longsword:zombie_1:nonlethal")
    assert (hp(engine, "zombie_1"), part(engine, "zombie_1").status) == (0, "down")


def test_monster_without_the_trait_dies_without_a_save(registry, cfg):
    rng = ScriptedRng(d20=[15], d8=[1])
    engine = zombie(registry, cfg, rng, traits=[])
    events = hit_zombie(engine)
    assert "monster_died" in kinds(events)


def test_radiant_skips_fortitude(registry, cfg):
    engine = zombie(registry, cfg, ScriptedRng())
    dealt = engine.damage("zombie_1", 4, "radiant")
    events = downed.after_damage(engine, "zombie_1", dealt, "hero")
    assert ("monster_died" in kinds(events), hp(engine, "zombie_1")) == (True, 0)


def test_non_radiant_damage_triggers_the_save(registry, cfg):
    engine = zombie(registry, cfg, ScriptedRng(d20=[20]))
    dealt = engine.damage("zombie_1", 4, "necrotic")
    downed.after_damage(engine, "zombie_1", dealt, "hero")
    assert hp(engine, "zombie_1") == 1


def test_merged_radiant_part_skips_fortitude(registry, cfg):
    engine = zombie(registry, cfg, ScriptedRng(), monster_hp=6)
    first = engine.damage("zombie_1", 3, "slashing")
    second = engine.damage("zombie_1", 3, "radiant")
    events = downed.after_damage(engine, "zombie_1", merge_damage(first, second), "hero")
    assert "monster_died" in kinds(events)


def test_hero_has_no_fortitude(registry, cfg):
    # трюк не у героя: герой на 0 HP падает как обычно, без спасброска Тел
    engine = zombie(registry, cfg, ScriptedRng())
    set_hp(engine, "hero", 1)
    dealt = engine.damage("hero", 5, "slashing")
    downed.after_damage(engine, "hero", dealt, "zombie_1")
    assert part(engine, "hero").status == "down"


# DamageResult.damage_types

def test_apply_damage_records_the_type(registry):
    hero = make_fighter(registry)
    assert apply_damage(hero, 1, "fire", registry).damage_types == ["fire"]


def test_apply_damage_records_the_type_even_if_immune(registry):
    hero = make_fighter(registry)
    result = apply_damage(hero, 1, "fire", registry, immunities=["fire"])
    assert (result.final, result.damage_types) == (0, ["fire"])


def test_merge_damage_concatenates_types(registry):
    hero = make_fighter(registry)
    one = apply_damage(hero, 1, "fire", registry)
    two = apply_damage(hero, 1, "cold", registry)
    assert merge_damage(one, two).damage_types == ["fire", "cold"]


def test_damage_types_default_is_empty():
    from ai_dm.rules.damage import DamageResult

    result = DamageResult(
        final=0, temp_absorbed=0, hp_lost=0, was_down=False, dropped=False, overkill=0
    )
    assert result.damage_types == []


def test_has_trait_returns_a_bool(registry, cfg):
    from ai_dm.combat.monster_traits import has_trait

    engine = zombie(registry, cfg, ScriptedRng())
    assert has_trait(engine, "zombie_1", "undead_fortitude") is True
    assert has_trait(engine, "zombie_1", "pack_tactics") is False
    assert has_trait(engine, "hero", "pack_tactics") is False


def test_merge_damage_adds_every_field():
    from ai_dm.rules.damage import DamageResult

    one = DamageResult(
        final=3, temp_absorbed=1, hp_lost=2, was_down=False, dropped=False, overkill=1, raw=4,
        notes=["a"], damage_types=["fire"],
    )
    two = DamageResult(
        final=5, temp_absorbed=2, hp_lost=3, was_down=True, dropped=True, overkill=2, raw=6,
        notes=["b"], damage_types=["cold"],
    )
    merged = merge_damage(one, two)
    assert (merged.final, merged.temp_absorbed, merged.hp_lost) == (8, 3, 5)
    assert (merged.overkill, merged.raw, merged.notes) == (3, 10, ["a", "b"])
    assert (merged.was_down, merged.dropped) == (False, True)


def test_merge_damage_dropped_if_either_dropped():
    from ai_dm.rules.damage import DamageResult

    base = {"final": 1, "temp_absorbed": 0, "hp_lost": 1, "was_down": False, "overkill": 0}
    no = DamageResult(dropped=False, **base)
    yes = DamageResult(dropped=True, **base)
    assert merge_damage(no, yes).dropped is True
    assert merge_damage(yes, no).dropped is True


def test_hero_on_the_attackers_side_is_not_a_pack_ally(registry, cfg):
    # волк-союзник героя бьёт гоблина; второй герой в зоне цели -- не стая
    reg = custom_registry(registry, wolf={"traits": ["pack_tactics"], "actions": [bite()]})
    engine = make_engine(
        reg, cfg, heroes=[(make_fighter(registry), "hall")], rng=ScriptedRng(d20=[2]),
        monsters=[mon("wolf_1", "wolf", "hall", side="heroes", group="allies"),
                  mon("goblin_1", "goblin_warrior", "hall")],
    )
    engine.perform("wolf_1", "attack:bite:goblin_1")
    assert hp(engine, "goblin_1") == 10


def test_pack_advantage_is_named_exactly(registry, cfg):
    engine = pack(registry, cfg, ScriptedRng(d20=[2, 15], d6=[1]), allies=("hall", "hall"))
    strike(engine)
    assert "преим.: тактика стаи)" in "\n".join(engine.state.log)
