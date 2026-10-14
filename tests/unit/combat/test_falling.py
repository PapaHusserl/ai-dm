# Партия К7х, п. 1: падение при толчке (docs/K7X-PLAN.md, В1, В2, В13, В14).
#   combat/falling.py:
#     drop_steps(zones, from_id, to_id) -> int      max(0, elevation(from) - elevation(to)); яма --
#       отрицательная
#     fall_dice(steps, cfg) -> str | None           steps * cfg.combat.fall_step_ft // 10 костей
#       d6, не больше 20;
#                                                   0 костей -- None
#     fall(engine, target, from_zone_id, by_ref)    лог «падает с высоты N фт», строка урона
#       «Падение», дробящий
#                                                   урон через engine.damage, prone (source "fall")
#                                                     при уроне > 0,
#                                                   хвост -- downed.after_damage (события)
#     push(engine, ref, target, zone)               перемещение (record_move, zone_id, лог) + fall
#   improvise push (apply_push) идёт через falling.push; вровень и вверх -- урона нет.
#   Зоны теста: balcony 1, hall 0, pit -1 (яма рядом с hall), door 0.
import pytest
from combat_kit import (
    ScriptedRng,
    creature,
    hp,
    make_engine,
    make_fighter,
    make_wizard,
    mon,
    part,
    set_hp,
)

from ai_dm.combat import falling
from ai_dm.config.settings import load_rules_config
from ai_dm.content.models.monsters import Monster
from ai_dm.state.combat import Zone
from ai_dm.state.creature import Concentration


def zones():
    return [
        Zone(id="door", name="У двери", adjacent=["hall"]),
        Zone(id="hall", name="Центр зала", adjacent=["door", "balcony", "pit"]),
        Zone(id="balcony", name="Балкон", adjacent=["hall"], elevation=1),
        Zone(id="pit", name="Яма", adjacent=["hall"], elevation=-1),
    ]


def tower(count):
    # башня: t0 -- земля, t<count> -- вершина, выше на ступень каждая
    return [
        Zone(id=f"t{i}", name=f"Ярус {i}", elevation=i,
             adjacent=[f"t{j}" for j in (i - 1, i + 1) if 0 <= j <= count])
        for i in range(count + 1)
    ]


def odd_registry(registry, **lists):
    data = registry.get("monster", "goblin_warrior").model_dump()
    data.update(lists)
    data["id"] = "odd_goblin"
    return registry.with_items({"monster": [Monster.model_validate(data)]})


def roof_duel(registry, cfg, rng, monster="goblin_warrior", reg=None, hero=None):
    # герой и гоблин на балконе (высота 1), зал внизу
    return make_engine(
        reg or registry, cfg, heroes=[(hero or make_fighter(registry), "balcony")], rng=rng,
        zones=zones(), monsters=[mon("goblin_1", monster, "balcony")],
    )


def log(engine):
    return "\n".join(engine.state.log)


def shove_down(engine, target="goblin_1", zone="hall"):
    return falling.push(engine, "hero", target, zone)


def conditions(engine, ref="goblin_1"):
    return [(c.id, c.source) for c in creature(engine, ref).conditions]


# --- drop_steps ---

def test_drop_from_balcony_to_hall_is_one_step():
    assert falling.drop_steps(zones(), "balcony", "hall") == 1


def test_drop_from_hall_into_the_pit_is_one_step():
    assert falling.drop_steps(zones(), "hall", "pit") == 1


def test_drop_up_is_zero_steps():
    assert falling.drop_steps(zones(), "hall", "balcony") == 0


def test_drop_to_the_same_height_is_zero_steps():
    assert falling.drop_steps(zones(), "hall", "door") == 0


def test_drop_from_balcony_into_the_pit_is_two_steps():
    assert falling.drop_steps(zones(), "balcony", "pit") == 2


def test_drop_of_two_floors():
    assert falling.drop_steps(tower(2), "t2", "t0") == 2


# --- fall_dice ---

def test_one_step_is_one_die(cfg):
    assert falling.fall_dice(1, cfg) == "1d6"


def test_three_steps_are_three_dice(cfg):
    assert falling.fall_dice(3, cfg) == "3d6"


def test_twenty_dice_ceiling_is_exact(cfg):
    assert falling.fall_dice(20, cfg) == "20d6"


def test_twenty_five_steps_are_capped_at_twenty_dice(cfg):
    assert falling.fall_dice(25, cfg) == "20d6"


def test_twenty_one_steps_are_capped_too(cfg):
    assert falling.fall_dice(21, cfg) == "20d6"


def test_zero_steps_give_no_dice(cfg):
    assert falling.fall_dice(0, cfg) is None


def test_half_step_config_two_steps_are_one_die():
    custom = load_rules_config(toml_text="[combat]\nfall_step_ft = 5\n")
    assert falling.fall_dice(2, custom) == "1d6"


def test_half_step_config_one_step_is_no_dice():
    custom = load_rules_config(toml_text="[combat]\nfall_step_ft = 5\n")
    assert falling.fall_dice(1, custom) is None


def test_double_step_config_one_step_is_two_dice():
    custom = load_rules_config(toml_text="[combat]\nfall_step_ft = 20\n")
    assert falling.fall_dice(1, custom) == "2d6"


def test_default_step_is_ten_feet(cfg):
    assert cfg.combat.fall_step_ft == 10


# --- fall: урон, лог, prone ---

def test_push_down_deals_fall_damage(registry, cfg):
    engine = roof_duel(registry, cfg, ScriptedRng(d6=[4]))
    shove_down(engine)
    assert hp(engine, "goblin_1") == 6


def test_push_down_moves_the_target_to_the_chosen_zone(registry, cfg):
    engine = roof_duel(registry, cfg, ScriptedRng(d6=[4]))
    shove_down(engine)
    assert part(engine, "goblin_1").zone_id == "hall"


def test_push_down_records_the_move(registry, cfg):
    engine = roof_duel(registry, cfg, ScriptedRng(d6=[4]))
    shove_down(engine)
    moves = [(m.ref, m.from_zone, m.to_zone) for m in engine.state.moves]
    assert moves == [("goblin_1", "balcony", "hall")]


def test_fall_log_names_the_height_in_feet(registry, cfg):
    engine = roof_duel(registry, cfg, ScriptedRng(d6=[4]))
    shove_down(engine)
    assert "  Воин-гоблин падает с высоты 10 фт" in engine.state.log


def test_fall_log_has_the_damage_line_with_the_label(registry, cfg):
    engine = roof_duel(registry, cfg, ScriptedRng(d6=[4]))
    shove_down(engine)
    assert any("Падение" in line for line in engine.state.log)


def test_fall_log_has_the_knocked_down_line(registry, cfg):
    engine = roof_duel(registry, cfg, ScriptedRng(d6=[4]))
    shove_down(engine)
    assert "  Воин-гоблин сбит с ног" in engine.state.log


def test_fall_damage_line_is_the_labelled_bludgeoning_roll(registry, cfg):
    engine = roof_duel(registry, cfg, ScriptedRng(d6=[4]))
    shove_down(engine)
    assert "  Падение: 1d6 (4) дробящий" in engine.state.log


def test_one_point_of_fall_damage_still_knocks_prone(registry, cfg):
    engine = roof_duel(registry, cfg, ScriptedRng(d6=[1]))
    shove_down(engine)
    assert hp(engine, "goblin_1") == 9
    assert conditions(engine) == [("prone", "fall")]


def test_fall_knocks_prone_with_the_fall_source(registry, cfg):
    engine = roof_duel(registry, cfg, ScriptedRng(d6=[4]))
    shove_down(engine)
    assert conditions(engine) == [("prone", "fall")]


def test_two_separate_falls_add_up(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "t2")], rng=ScriptedRng(d6=[2, 3]),
        zones=tower(2), monsters=[mon("goblin_1", "goblin_warrior", "t2")],
    )
    falling.push(engine, "hero", "goblin_1", "t1")
    falling.push(engine, "hero", "goblin_1", "t0")
    assert hp(engine, "goblin_1") == 5


def test_two_step_drop_rolls_two_dice_at_once(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "balcony")], rng=ScriptedRng(d6=[2, 3]),
        zones=zones(), monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    engine.state.zones[2].elevation = 2
    part(engine, "goblin_1").zone_id = "hall"
    falling.fall(engine, "goblin_1", "balcony", "hero")
    assert hp(engine, "goblin_1") == 5


def test_step_in_feet_follows_the_config(registry):
    custom = load_rules_config(toml_text="[combat]\nfall_step_ft = 20\n")
    engine = roof_duel(registry, custom, ScriptedRng(d6=[1, 1]))
    shove_down(engine)
    assert "  Воин-гоблин падает с высоты 20 фт" in engine.state.log


def test_step_of_five_feet_gives_no_fall_for_one_step(registry):
    custom = load_rules_config(toml_text="[combat]\nfall_step_ft = 5\n")
    engine = roof_duel(registry, custom, ScriptedRng())
    shove_down(engine)
    assert hp(engine, "goblin_1") == 10
    assert conditions(engine) == []


def test_fall_without_height_difference_returns_no_events_and_no_log(registry, cfg):
    engine = roof_duel(registry, cfg, ScriptedRng())
    part(engine, "goblin_1").zone_id = "hall"
    assert falling.fall(engine, "goblin_1", "door", "hero") == []
    assert not any("падает" in line for line in engine.state.log)


def test_ceiling_of_twenty_dice_on_a_huge_drop(registry, cfg):
    engine = roof_duel(registry, cfg, ScriptedRng(d6=[1] * 20))
    engine.state.zones[2].elevation = 25
    creature(engine, "goblin_1").hp_max = 100
    set_hp(engine, "goblin_1", 100)
    part(engine, "goblin_1").zone_id = "hall"
    falling.fall(engine, "goblin_1", "balcony", "hero")
    assert hp(engine, "goblin_1") == 80
    assert engine.rng.left("d6") == 0
    assert "  Воин-гоблин падает с высоты 250 фт" in engine.state.log


# --- иммунитет и сопротивление дробящему ---

def test_bludgeoning_immune_target_takes_nothing(registry, cfg):
    reg = odd_registry(registry, damage_immunities=["bludgeoning"])
    engine = roof_duel(registry, cfg, ScriptedRng(d6=[4]), monster="odd_goblin", reg=reg)
    shove_down(engine)
    assert hp(engine, "goblin_1") == 10


def test_bludgeoning_immune_target_is_not_knocked_prone(registry, cfg):
    reg = odd_registry(registry, damage_immunities=["bludgeoning"])
    engine = roof_duel(registry, cfg, ScriptedRng(d6=[4]), monster="odd_goblin", reg=reg)
    shove_down(engine)
    assert conditions(engine) == []


def test_bludgeoning_immune_target_still_lands_in_the_lower_zone(registry, cfg):
    reg = odd_registry(registry, damage_immunities=["bludgeoning"])
    engine = roof_duel(registry, cfg, ScriptedRng(d6=[4]), monster="odd_goblin", reg=reg)
    shove_down(engine)
    assert part(engine, "goblin_1").zone_id == "hall"


def test_bludgeoning_resistance_halves_the_fall(registry, cfg):
    reg = odd_registry(registry, damage_resistances=["bludgeoning"])
    engine = roof_duel(registry, cfg, ScriptedRng(d6=[4]), monster="odd_goblin", reg=reg)
    shove_down(engine)
    assert hp(engine, "goblin_1") == 8


def test_bludgeoning_resistance_still_knocks_prone(registry, cfg):
    reg = odd_registry(registry, damage_resistances=["bludgeoning"])
    engine = roof_duel(registry, cfg, ScriptedRng(d6=[4]), monster="odd_goblin", reg=reg)
    shove_down(engine)
    assert conditions(engine) == [("prone", "fall")]


def test_prone_immune_monster_takes_damage_without_lying(registry, cfg):
    reg = odd_registry(registry, condition_immunities=["prone"])
    engine = roof_duel(registry, cfg, ScriptedRng(d6=[4]), monster="odd_goblin", reg=reg)
    shove_down(engine)
    assert hp(engine, "goblin_1") == 6
    assert conditions(engine) == []


# --- after_damage: смерть, нокаут, концентрация ---

def test_goblin_with_two_hp_dies_from_the_fall(registry, cfg):
    engine = roof_duel(registry, cfg, ScriptedRng(d6=[5]))
    set_hp(engine, "goblin_1", 2)
    shove_down(engine)
    assert part(engine, "goblin_1").status == "dead"
    assert "  Воин-гоблин убит" in engine.state.log


def test_fall_death_returns_the_monster_died_event(registry, cfg):
    engine = roof_duel(registry, cfg, ScriptedRng(d6=[5]))
    set_hp(engine, "goblin_1", 2)
    events = shove_down(engine)
    assert [(e.type, e.data["id"], e.data["by"]) for e in events] == [
        ("monster_died", "goblin_1", "hero")
    ]


def test_fall_without_death_returns_no_events(registry, cfg):
    engine = roof_duel(registry, cfg, ScriptedRng(d6=[2]))
    assert shove_down(engine) == []


def test_hero_at_one_hp_goes_down_from_the_fall(registry, cfg):
    engine = roof_duel(registry, cfg, ScriptedRng(d6=[3]))
    set_hp(engine, "hero", 1)
    falling.push(engine, "goblin_1", "hero", "hall")
    assert hp(engine, "hero") == 0
    assert part(engine, "hero").status == "down"


def test_hero_falling_keeps_hp_above_zero_when_the_fall_is_light(registry, cfg):
    engine = roof_duel(registry, cfg, ScriptedRng(d6=[3]))
    falling.push(engine, "goblin_1", "hero", "hall")
    assert hp(engine, "hero") == 9
    assert part(engine, "hero").status == "active"


def test_hero_falls_prone_with_the_fall_source(registry, cfg):
    engine = roof_duel(registry, cfg, ScriptedRng(d6=[3]))
    falling.push(engine, "goblin_1", "hero", "hall")
    assert conditions(engine, "hero") == [("prone", "fall")]


def test_hero_concentration_is_checked_after_the_fall(registry, cfg):
    wizard = make_wizard(registry)
    engine = make_engine(
        registry, cfg, heroes=[(wizard, "balcony")], rng=ScriptedRng(d6=[1], d20=[20]),
        zones=zones(), monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    creature(engine, "wiz").concentration = Concentration(spell_id="bless", circle=1)
    falling.push(engine, "goblin_1", "wiz", "hall")
    assert any("Концентрация" in line for line in engine.state.log)
    assert creature(engine, "wiz").concentration is not None


# --- improvise push ---

def improvise_push(engine, zone, target="goblin_1"):
    return engine.improvise(
        "hero", skill="athletics", category="medium", effect="push", target=target, zone=zone
    )


def test_improvise_push_down_moves_and_hurts_in_one_action(registry, cfg):
    engine = roof_duel(registry, cfg, ScriptedRng(d20=[10], d6=[4]))
    improvise_push(engine, "hall")
    assert part(engine, "goblin_1").zone_id == "hall"
    assert hp(engine, "goblin_1") == 6
    assert part(engine, "hero").turn.action is False


def test_improvise_push_down_knocks_prone(registry, cfg):
    engine = roof_duel(registry, cfg, ScriptedRng(d20=[10], d6=[4]))
    improvise_push(engine, "hall")
    assert conditions(engine) == [("prone", "fall")]


def test_improvise_push_kills_the_goblin_and_ends_the_fight(registry, cfg):
    engine = roof_duel(registry, cfg, ScriptedRng(d20=[10], d6=[6]))
    set_hp(engine, "goblin_1", 3)
    improvise_push(engine, "hall")
    assert part(engine, "goblin_1").status == "dead"
    assert engine.state.outcome == "victory"


def test_failed_push_check_means_no_fall(registry, cfg):
    engine = roof_duel(registry, cfg, ScriptedRng(d20=[2]))
    improvise_push(engine, "hall")
    assert part(engine, "goblin_1").zone_id == "balcony"
    assert hp(engine, "goblin_1") == 10


def test_push_on_the_same_level_deals_no_damage(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "hall")], rng=ScriptedRng(d20=[10]),
        zones=zones(), monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    improvise_push(engine, "door")
    assert part(engine, "goblin_1").zone_id == "door"
    assert hp(engine, "goblin_1") == 10
    assert conditions(engine) == []


def test_push_up_deals_no_damage(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "hall")], rng=ScriptedRng(d20=[10]),
        zones=zones(), monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    improvise_push(engine, "balcony")
    assert part(engine, "goblin_1").zone_id == "balcony"
    assert hp(engine, "goblin_1") == 10
    assert conditions(engine) == []


def test_push_into_the_pit_is_a_fall_too(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "hall")],
        rng=ScriptedRng(d20=[10], d6=[3]),
        zones=zones(), monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    improvise_push(engine, "pit")
    assert hp(engine, "goblin_1") == 7
    assert "  Воин-гоблин падает с высоты 10 фт" in engine.state.log


def test_push_on_flat_ground_has_no_fall_line(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "hall")], rng=ScriptedRng(d20=[10]),
        zones=zones(), monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    improvise_push(engine, "door")
    assert not any("падает" in line for line in engine.state.log)


# --- встаёт и выходит из ямы (В14) ---

def test_fallen_goblin_stands_up_at_its_turn_and_loses_the_move(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "hall")],
        rng=ScriptedRng(d20=[10], d6=[3]),
        zones=zones(), monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    improvise_push(engine, "pit")
    engine.start_turn("goblin_1")
    assert conditions(engine) == []
    assert part(engine, "goblin_1").turn.move == 0
    assert "Воин-гоблин встаёт" in engine.state.log


def test_goblin_leaves_the_pit_by_a_normal_move_the_next_turn(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "hall")],
        rng=ScriptedRng(d20=[10], d6=[3]),
        zones=zones(), monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    improvise_push(engine, "pit")
    engine.start_turn("goblin_1")
    engine.start_turn("goblin_1")
    assert part(engine, "goblin_1").turn.move == 1
    ids = [o.id for o in engine.available_actions("goblin_1") if o.kind == "move"]
    assert "move:hall" in ids


def test_climbing_out_of_the_pit_costs_no_damage(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "hall")],
        rng=ScriptedRng(d20=[10], d6=[3]),
        zones=zones(), monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    improvise_push(engine, "pit")
    engine.start_turn("goblin_1")
    engine.start_turn("goblin_1")
    engine.perform("goblin_1", "move:hall")
    assert part(engine, "goblin_1").zone_id == "hall"
    assert hp(engine, "goblin_1") == 7


@pytest.mark.parametrize("steps", [1, 2, 3])
def test_fall_dice_match_steps_in_the_log(registry, cfg, steps):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), f"t{steps}")],
        rng=ScriptedRng(d6=[1] * steps),
        zones=tower(steps), monsters=[mon("goblin_1", "goblin_warrior", f"t{steps}")],
    )
    part(engine, "goblin_1").zone_id = "t0"
    falling.fall(engine, "goblin_1", f"t{steps}", "hero")
    assert f"  Воин-гоблин падает с высоты {steps * 10} фт" in engine.state.log
    assert hp(engine, "goblin_1") == 10 - steps
