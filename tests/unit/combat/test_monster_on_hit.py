# Партия К7д, п. 2.2, 2.7: эффект при попадании у действия монстра (docs/plan-k7d.md, В3в).
#   MonsterAction.on_hit: HitRider | None; HitRider(condition, save: Ability | None, dc: int | None,
#     max_size, duration: target_turn | source_turn | minute | None, dice, damage_type): save и dc
#     только вместе, dice и damage_type только вместе (иначе ValidationError).
#   При попадании: нет HP у цели (упала от основного урона) или цель крупнее max_size -- эффекта
#   нет,
#   броска нет; иначе спасбросок save СЛ dc; успех -- ничего; провал -- урон dice (если задан;
#   сливается в тот же DamageResult до downed.after_damage, смерть от него -- monster_died) и
#   состояние condition (иммунитет цели его отбивает, в лог -- «иммунитет»). Срок: target_turn --
#   до конца следующего хода цели (Expiry end_of_turn, owner цель), source_turn -- до конца
#   следующего хода бьющего (owner бьющий, value 1: конец текущего хода пропускается), minute --
#   Expiry rounds 10, None -- без срока. Без save эффект применяется сразу.
# Герой-воин: КД 19, Тел +4 (спасбросок с мастерством), Сил +5; атака монстра +5, d20 15 --
# попадание.
import pytest
from combat_kit import (
    ScriptedRng,
    bite,
    creature,
    custom_registry,
    hp,
    make_engine,
    make_fighter,
    make_wizard,
    mon,
    set_hp,
)
from pydantic import ValidationError

from ai_dm.content.models.monsters import HitRider
from ai_dm.rules.roll_pipeline import DAMAGE_TYPE_WORDS

PARALYZE = {"condition": "paralyzed", "save": "con", "dc": 10, "duration": "target_turn"}
POISON = {"condition": "poisoned", "save": "con", "dc": 11, "damage_type": "poison"}
KNOCK = {"condition": "prone", "save": "str", "dc": 11, "max_size": "large"}


def fight(registry, cfg, rng, rider, target="hero", target_fields=None, **action):
    reg = custom_registry(
        registry, ghoul={"actions": [bite(on_hit=rider, **action)]},
        ally=target_fields or {},
    )
    return make_engine(
        reg, cfg, heroes=[make_fighter(registry)], rng=rng,
        monsters=[
            mon("ghoul", "ghoul", "hall"),
            mon("ally", "ally", "hall", side="heroes", group="allies"),
        ],
    )


def conds(engine, ref="hero"):
    return [(c.id, c.source) for c in creature(engine, ref).conditions]


def strike(engine, target="hero"):
    return engine.perform("ghoul", f"attack:bite:{target}")


def test_failed_save_imposes_the_condition(registry, cfg):
    # Тел +4: d20 5 -> 9 < СЛ 10
    engine = fight(registry, cfg, ScriptedRng(d20=[15, 5], d6=[1]), PARALYZE)
    strike(engine)
    assert conds(engine) == [("paralyzed", "ghoul")]


def test_save_at_the_dc_resists(registry, cfg):
    # d20 6 -> 10 >= СЛ 10
    engine = fight(registry, cfg, ScriptedRng(d20=[15, 6], d6=[1]), PARALYZE)
    strike(engine)
    assert conds(engine) == []


def test_miss_has_no_effect_and_no_save(registry, cfg):
    rng = ScriptedRng(d20=[2])
    engine = fight(registry, cfg, rng, PARALYZE)
    strike(engine)
    assert conds(engine) == []


def test_effect_is_logged(registry, cfg):
    engine = fight(registry, cfg, ScriptedRng(d20=[15, 5], d6=[1]), PARALYZE)
    strike(engine)
    assert any(line.endswith(": парализован") for line in engine.state.log)


def test_target_left_on_one_hp_still_gets_the_effect(registry, cfg):
    engine = fight(registry, cfg, ScriptedRng(d20=[15, 5], d6=[1]), PARALYZE)
    set_hp(engine, "hero", 2)
    strike(engine)
    assert (hp(engine, "hero"), conds(engine)) == (1, [("paralyzed", "ghoul")])


def test_rider_damage_line_is_labelled(registry, cfg):
    rider = {**POISON, "dice": "1d4"}
    engine = fight(registry, cfg, ScriptedRng(d20=[15, 1], d6=[1], d4=[2]), rider)
    strike(engine)
    assert any("Урон (bite, эффект)" in line for line in engine.state.log)
    assert any(line.endswith("1d4 (2) " + DAMAGE_TYPE_WORDS["poison"]) for line in engine.state.log)


def test_on_hit_without_provoked_is_a_turn_of_the_attacker(registry, cfg):
    from ai_dm.combat.actions.attack import attacks_of
    from ai_dm.combat.monster_traits import on_hit

    engine = fight(registry, cfg, ScriptedRng(d20=[5]), PARALYZE)
    info = attacks_of(engine, "ghoul")[0]
    dealt = engine.damage("hero", 1, "piercing")
    on_hit(engine, ("ghoul", "hero"), info, dealt)
    assert creature(engine, "hero").conditions[0].expires.value == 0


def test_target_turn_expiry(registry, cfg):
    engine = fight(registry, cfg, ScriptedRng(d20=[15, 5], d6=[1]), PARALYZE)
    strike(engine)
    expires = creature(engine, "hero").conditions[0].expires
    assert (expires.kind, expires.owner, expires.value) == ("end_of_turn", "hero", 0)


def test_target_turn_condition_ends_with_the_target_turn(registry, cfg):
    engine = fight(registry, cfg, ScriptedRng(d20=[15, 5], d6=[1]), PARALYZE)
    strike(engine)
    engine.expire("end_of_turn", "ghoul")
    assert conds(engine) != []
    engine.expire("end_of_turn", "hero")
    assert conds(engine) == []


def test_paralyzed_hero_has_only_end_turn(registry, cfg):
    engine = fight(registry, cfg, ScriptedRng(d20=[15, 5], d6=[1]), PARALYZE)
    strike(engine)
    assert [o.id for o in engine.available_actions("hero")] == ["end_turn"]


def test_source_turn_expiry_skips_the_current_end(registry, cfg):
    rider = {**PARALYZE, "duration": "source_turn"}
    engine = fight(registry, cfg, ScriptedRng(d20=[15, 5], d6=[1]), rider)
    strike(engine)
    expires = creature(engine, "hero").conditions[0].expires
    assert (expires.kind, expires.owner, expires.value) == ("end_of_turn", "ghoul", 1)
    engine.expire("end_of_turn", "ghoul")
    assert conds(engine) != []
    engine.expire("end_of_turn", "ghoul")
    assert conds(engine) == []


def test_minute_expiry_is_ten_rounds(registry, cfg):
    rider = {**PARALYZE, "duration": "minute"}
    engine = fight(registry, cfg, ScriptedRng(d20=[15, 5], d6=[1]), rider)
    strike(engine)
    expires = creature(engine, "hero").conditions[0].expires
    assert (expires.kind, expires.value) == ("rounds", 10)
    for _ in range(9):
        engine.tick_rounds()
    assert conds(engine) != []
    engine.tick_rounds()
    assert conds(engine) == []


def test_no_duration_means_no_expiry(registry, cfg):
    rider = {"condition": "prone", "save": "str", "dc": 11}
    engine = fight(registry, cfg, ScriptedRng(d20=[15, 1], d6=[1]), rider)
    strike(engine)
    assert creature(engine, "hero").conditions[0].expires is None


def test_effect_without_a_save_applies_at_once(registry, cfg):
    rng = ScriptedRng(d20=[15], d6=[1])
    engine = fight(registry, cfg, rng, {"condition": "prone"})
    strike(engine)
    assert conds(engine) == [("prone", "ghoul")]


def test_huge_target_is_not_knocked_down_and_rolls_no_save(registry, cfg):
    rng = ScriptedRng(d20=[15], d6=[1])
    engine = fight(registry, cfg, rng, KNOCK, target_fields={"size": "huge", "hp": 30})
    strike(engine, "ally")
    assert conds(engine, "ally") == []
    assert hp(engine, "ally") == 29


def test_large_target_is_still_knocked_down(registry, cfg):
    engine = fight(registry, cfg, ScriptedRng(d20=[15, 1], d6=[1]), KNOCK,
                   target_fields={"size": "large", "hp": 30})
    strike(engine, "ally")
    assert conds(engine, "ally") == [("prone", "ghoul")]


def test_medium_hero_is_knocked_down(registry, cfg):
    engine = fight(registry, cfg, ScriptedRng(d20=[15, 1], d6=[1]), KNOCK)
    strike(engine)
    assert conds(engine) == [("prone", "ghoul")]


def test_target_with_the_condition_immunity_keeps_clear(registry, cfg):
    fields = {"condition_immunities": ["paralyzed"], "hp": 30}
    engine = fight(registry, cfg, ScriptedRng(d20=[15, 1], d6=[1]), PARALYZE, target_fields=fields)
    strike(engine, "ally")
    assert conds(engine, "ally") == []
    assert any("иммунитет" in line for line in engine.state.log)


def test_target_dropped_by_the_hit_gets_no_effect(registry, cfg):
    rng = ScriptedRng(d20=[15], d6=[6])
    engine = fight(registry, cfg, rng, PARALYZE)
    set_hp(engine, "hero", 3)
    strike(engine)
    assert conds(engine) == [("unconscious", "0_hp")]


def test_failed_save_deals_the_rider_damage(registry, cfg):
    rider = {**POISON, "dice": "2d4"}
    engine = fight(registry, cfg, ScriptedRng(d20=[15, 1], d6=[1], d4=[2, 3]), rider)
    strike(engine)
    assert hp(engine, "hero") == 12 - 1 - 5
    assert conds(engine) == [("poisoned", "ghoul")]


def test_passed_save_deals_no_rider_damage(registry, cfg):
    rider = {**POISON, "dice": "2d4"}
    rng = ScriptedRng(d20=[15, 20], d6=[1])
    engine = fight(registry, cfg, rng, rider)
    strike(engine)
    assert hp(engine, "hero") == 12 - 1


def test_death_from_the_rider_damage_is_reported(registry, cfg):
    rider = {**POISON, "dc": 30, "dice": "1d4"}
    engine = fight(
        registry, cfg, ScriptedRng(d20=[15, 1], d6=[1], d4=[4]), rider,
        target_fields={"hp": 5, "ac": 8},
    )
    events = strike(engine, "ally")
    assert "monster_died" in [e.type for e in events]


def test_rider_damage_is_in_the_attack_event(registry, cfg):
    rider = {**POISON, "dice": "1d4"}
    engine = fight(registry, cfg, ScriptedRng(d20=[15, 1], d6=[2], d4=[3]), rider)
    events = strike(engine)
    assert [e.data["damage"] for e in events if e.type == "attack"] == [5]


# провоцированная атака идёт в чужой ход: пропуски концов хода меняются местами

@pytest.mark.parametrize(
    "duration, provoked, owner, value",
    [
        ("target_turn", False, "hero", 0), ("target_turn", True, "hero", 1),
        ("source_turn", False, "ghoul", 1), ("source_turn", True, "ghoul", 0),
    ],
)
def test_provoked_attack_shifts_the_skipped_ends(registry, cfg, duration, provoked, owner, value):
    from ai_dm.combat.actions.attack import attack, attacks_of

    engine = fight(
        registry, cfg, ScriptedRng(d20=[15, 5], d6=[1]), {**PARALYZE, "duration": duration}
    )
    info = attacks_of(engine, "ghoul")[0]
    attack(engine, "ghoul", "hero", info, provoked=provoked)
    expires = creature(engine, "hero").conditions[0].expires
    assert (expires.kind, expires.owner, expires.value) == ("end_of_turn", owner, value)


# exempt: типы существ (и виды героев), на которых эффект не действует

def test_exempt_monster_type_resists_without_a_save(registry, cfg):
    rider = {**PARALYZE, "exempt": ["undead"]}
    engine = fight(registry, cfg, ScriptedRng(d20=[15], d6=[1]), rider,
                   target_fields={"creature_type": "undead", "hp": 30})
    strike(engine, "ally")
    assert conds(engine, "ally") == []


def test_exempt_hero_species_resists_without_a_save(registry, cfg):
    # маг-эльф: вид elf в exempt -- спасброска нет, состояния нет
    rider = {**PARALYZE, "exempt": ["elf"]}
    reg = custom_registry(registry, ghoul={"actions": [bite(on_hit=rider)]})
    engine = make_engine(
        reg, cfg, heroes=[make_wizard(registry)], rng=ScriptedRng(d20=[15], d6=[1]),
        monsters=[mon("ghoul", "ghoul", "hall")],
    )
    strike(engine, "wiz")
    assert conds(engine, "wiz") == []


def test_other_species_is_not_exempt(registry, cfg):
    rider = {**PARALYZE, "exempt": ["elf"]}
    engine = fight(registry, cfg, ScriptedRng(d20=[15, 5], d6=[1]), rider)
    strike(engine)
    assert conds(engine) == [("paralyzed", "ghoul")]


def test_exempt_defaults_to_empty():
    assert HitRider(condition="prone").exempt == []


# модель

def test_rider_needs_save_and_dc_together():
    with pytest.raises(ValidationError):
        HitRider(condition="prone", save="str")
    with pytest.raises(ValidationError):
        HitRider(condition="prone", dc=10)


def test_rider_needs_dice_and_type_together():
    with pytest.raises(ValidationError):
        HitRider(condition="prone", dice="1d4")
    with pytest.raises(ValidationError):
        HitRider(condition="prone", damage_type="poison")


def test_rider_rejects_unknown_duration_and_size():
    with pytest.raises(ValidationError):
        HitRider(condition="prone", duration="forever")
    with pytest.raises(ValidationError):
        HitRider(condition="prone", max_size="colossal")


def test_rider_accepts_a_full_description():
    rider = HitRider(**PARALYZE, dice="1d4", damage_type="poison", max_size="large")
    assert (rider.save, rider.dc, rider.duration) == ("con", 10, "target_turn")


def test_rider_condition_is_required():
    with pytest.raises(ValidationError):
        HitRider(save="con", dc=10)
