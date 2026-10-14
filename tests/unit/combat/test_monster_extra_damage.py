# Партия К7д, п. 2.2, 2.6: доп. урон второго типа в действии монстра (docs/K7D-PLAN.md, В3в).
#   MonsterAction.extra_damage_dice / extra_damage_type -- оба или ни одного (иначе
#   ValidationError).
#   При попадании после основного урона бросается доп. урон отдельной строкой лога (свой тип,
#   свои сопротивления и иммунитеты цели), крит удваивает кости обеих частей; оба куска складываются
#   в один DamageResult до downed.after_damage: смерть от второй части -- monster_died.
# Паук-копия: Bite +5, 1d6 колющего + 2d8 ядом; герой-воин КД 19 (d20 15 -- попадание).
import pytest
from combat_kit import ScriptedRng, bite, custom_registry, hp, make_engine, make_fighter, mon
from pydantic import ValidationError

from ai_dm.content.models.monsters import MonsterAction

SPIDER = bite(extra_damage_dice="2d8", extra_damage_type="poison")


def duel(registry, cfg, rng, target="hero", target_fields=None, action=SPIDER):
    reg = custom_registry(
        registry, spider={"actions": [action]}, skeleton=target_fields or {"damage_immunities": []},
    )
    return make_engine(
        reg, cfg, heroes=[make_fighter(registry)], rng=rng,
        monsters=[
            mon("spider", "spider", "hall"),
            mon("skel", "skeleton", "hall", side="heroes", group="allies"),
        ],
    )


def test_both_damage_parts_are_dealt(registry, cfg):
    # 1d6 = 3 колющего + 2d8 = 4 + 5 ядом
    engine = duel(registry, cfg, ScriptedRng(d20=[15], d6=[3], d8=[4, 5]))
    engine.perform("spider", "attack:bite:hero")
    assert hp(engine, "hero") == 12 - 3 - 9


def test_extra_damage_has_its_own_log_line(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[15], d6=[3], d8=[4, 5]))
    engine.perform("spider", "attack:bite:hero")
    lines = [line for line in engine.state.log if "2d8" in line]
    assert len(lines) == 1 and "яд" in lines[0]
    assert any("Урон (bite, доп.)" in line for line in engine.state.log)


def test_miss_deals_no_extra_damage(registry, cfg):
    rng = ScriptedRng(d20=[2])
    engine = duel(registry, cfg, rng)
    engine.perform("spider", "attack:bite:hero")
    assert hp(engine, "hero") == 12


def test_critical_doubles_both_dice(registry, cfg):
    # крит: 2d6 = 1 + 1, 4d8 = 1 + 1 + 1 + 1
    rng = ScriptedRng(d20=[20], d6=[1, 1], d8=[1, 1, 1, 1])
    engine = duel(registry, cfg, rng)
    engine.perform("spider", "attack:bite:hero")
    assert (hp(engine, "hero"), rng.left("d8")) == (12 - 2 - 4, 0)


def test_target_immune_to_the_second_type_takes_only_the_first(registry, cfg):
    fields = {"damage_immunities": ["poison"], "hp": 20}
    engine = duel(registry, cfg, ScriptedRng(d20=[15], d6=[3], d8=[4, 5]), target_fields=fields)
    engine.perform("spider", "attack:bite:skel")
    assert hp(engine, "skel") == 20 - 3


def test_target_resistant_to_the_second_type_halves_it(registry, cfg):
    fields = {"damage_resistances": ["poison"], "hp": 20}
    engine = duel(registry, cfg, ScriptedRng(d20=[15], d6=[3], d8=[4, 5]), target_fields=fields)
    engine.perform("spider", "attack:bite:skel")
    assert hp(engine, "skel") == 20 - 3 - 4


def test_death_from_the_second_part_is_reported(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[15], d6=[2], d8=[4, 4]),
                  target_fields={"hp": 6})
    events = engine.perform("spider", "attack:bite:skel")
    assert [e.type for e in events if e.type == "monster_died"] == ["monster_died"]


def test_attack_event_damage_is_the_sum(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[15], d6=[3], d8=[4, 5]))
    events = engine.perform("spider", "attack:bite:hero")
    assert [e.data["damage"] for e in events if e.type == "attack"] == [12]


def test_action_without_extra_damage_rolls_no_d8(registry, cfg):
    rng = ScriptedRng(d20=[15], d6=[3])
    engine = duel(registry, cfg, rng, action=bite())
    engine.perform("spider", "attack:bite:hero")
    assert hp(engine, "hero") == 12 - 3


def test_hero_attack_is_not_affected(registry, cfg):
    rng = ScriptedRng(d20=[15], d8=[4])
    engine = duel(registry, cfg, rng)
    engine.perform("hero", "attack:longsword:spider")
    assert rng.left("d8") == 0


def test_extra_damage_fields_default_to_none():
    action = MonsterAction(name="Bite")
    assert (action.extra_damage_dice, action.extra_damage_type) == (None, None)


def test_dice_without_type_is_rejected():
    with pytest.raises(ValidationError):
        MonsterAction(name="Bite", extra_damage_dice="1d4")


def test_type_without_dice_is_rejected():
    with pytest.raises(ValidationError):
        MonsterAction(name="Bite", extra_damage_type="poison")


def test_both_fields_are_accepted():
    action = MonsterAction(name="Bite", extra_damage_dice="1d4", extra_damage_type="poison")
    assert action.extra_damage_type == "poison"
