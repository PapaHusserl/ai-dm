# Партия К7х, п. 3.1-3.2: режим отбора оружия [disarm].mode = "save" (docs/K7X-PLAN.md, В3, Q2 (а)).
#   cfg.disarm.mode: Literal["check", "save"] = "check" (по умолчанию состязание DMG --
#     test_disarm.py,
#   логи и броски прежние); "foo" -> ValidationError. cfg.disarm.enemy_chance: 0..100, иначе
#     ValidationError.
#   save: после лога «обезоруживание» -- без проверки цели и без броска атаки:
#     * СЛ = 8 + лучший мод. из Сил/Лов атакующего + БМ (герой -- мастерство, монстр --
#       unarmed_proficiency 2);
#       в лог строка «  СЛ N (...)»;
#     * цель бросает спасбросок лучшей из Сил/Лов; преимущество -- двуручный хват или цель крупнее,
#       помеха -- цель мельче (те же подписи, что в режиме check);
#     * провал спасброска -- оружие выбито (общий исход disarm_target), успех -- оружие у цели;
#     * атака тратится в обоих исходах; у монстра ставится disarm_used.
#   Воин героя: Сил 17 (+3), Лов 13 (+1), мастерство +2, спас Сил +5 / Лов +1 -> СЛ героя 13.
#   Гоблин: Сил 8 (-1), Лов 15 (+2), small -> СЛ гоблина 12, спас Лов +2 (с помехой против героя).
import pytest
from combat_kit import (
    ScriptedRng,
    creature,
    give_weapon,
    make_engine,
    make_fighter,
    mon,
    part,
    turn,
)
from pydantic import ValidationError
from test_ranger_combat import make_ranger

from ai_dm.config.settings import load_rules_config
from ai_dm.rules.inventory import count_item, remove_item

SAVE = load_rules_config(toml_text='[disarm]\nmode = "save"\n')


def duel(registry, cfg, rng=None, hero=None):
    return make_engine(
        registry, cfg, heroes=[hero or make_fighter(registry)], rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )


def disarmed(engine, ref="goblin_1"):
    return [e for e in creature(engine, ref).active_effects if e.id == "disarmed"]


def log(engine):
    return "\n".join(engine.state.log)


def hero_disarms(engine, weapon="scimitar"):
    return engine.perform("hero", f"disarm:goblin_1:{weapon}")


def goblin_disarms(engine):
    return engine.perform("goblin_1", "disarm:hero:longsword")


def disarmer(registry, cfg, monkeypatch, rng):
    monkeypatch.setattr(registry.get("monster", "goblin_warrior"), "tags", ["disarmer"])
    return duel(registry, cfg, rng)


# --- конфиг ---

def test_default_mode_is_check(cfg):
    assert cfg.disarm.mode == "check"


def test_save_mode_is_read_from_the_config():
    assert SAVE.disarm.mode == "save"


def test_unknown_mode_is_rejected():
    with pytest.raises(ValidationError):
        load_rules_config(toml_text='[disarm]\nmode = "foo"\n')


def test_enemy_chance_over_a_hundred_is_rejected():
    with pytest.raises(ValidationError):
        load_rules_config(toml_text="[disarm]\nenemy_chance = 101\n")


def test_negative_enemy_chance_is_rejected():
    with pytest.raises(ValidationError):
        load_rules_config(toml_text="[disarm]\nenemy_chance = -1\n")


def test_enemy_chance_of_a_hundred_is_allowed():
    assert load_rules_config(toml_text="[disarm]\nenemy_chance = 100\n").disarm.enemy_chance == 100


def test_default_enemy_chance_is_zero(cfg):
    assert cfg.disarm.enemy_chance == 0


# --- герой выбивает у гоблина ---

def test_failed_save_takes_the_weapon(registry):
    # помеха: два d20, берётся меньший: 3 + 2 = 5 < 13
    engine = duel(registry, SAVE, ScriptedRng(d20=[3, 15]))
    hero_disarms(engine)
    assert [e.params for e in disarmed(engine)] == [{"weapon_id": "scimitar"}]


def test_failed_save_drops_the_weapon_on_the_ground(registry):
    engine = duel(registry, SAVE, ScriptedRng(d20=[3, 15]))
    hero_disarms(engine)
    assert [(i.item_id, i.zone_id, i.owner_ref) for i in engine.state.ground_items] == [
        ("scimitar", "hall", "goblin_1")
    ]


def test_passed_save_keeps_the_weapon(registry):
    engine = duel(registry, SAVE, ScriptedRng(d20=[18, 19]))
    hero_disarms(engine)
    assert disarmed(engine) == []
    assert engine.state.ground_items == []


def test_save_equal_to_the_dc_keeps_the_weapon(registry):
    # меньший из двух: 11 + 2 = 13 = СЛ
    engine = duel(registry, SAVE, ScriptedRng(d20=[11, 18]))
    hero_disarms(engine)
    assert disarmed(engine) == []


def test_save_one_below_the_dc_loses_the_weapon(registry):
    engine = duel(registry, SAVE, ScriptedRng(d20=[10, 18]))
    hero_disarms(engine)
    assert len(disarmed(engine)) == 1


def test_dc_line_shows_eight_plus_ability_plus_proficiency(registry):
    engine = duel(registry, SAVE, ScriptedRng(d20=[3, 15]))
    hero_disarms(engine)
    line = [x for x in engine.state.log if x.startswith("  СЛ ")][0]
    assert line.startswith("  СЛ 13 (")
    assert "8" in line
    assert "Сил" in line
    assert "мастерство" in line


def test_goblin_saves_with_dexterity(registry):
    engine = duel(registry, SAVE, ScriptedRng(d20=[3, 15]))
    hero_disarms(engine)
    assert any("спасбросок dex" in line for line in engine.state.log)


def test_goblin_save_uses_the_dexterity_modifier(registry):
    # d20 11 (меньший) + 2 = 13: хватает; с Силой (-1) не хватило бы
    engine = duel(registry, SAVE, ScriptedRng(d20=[11, 18]))
    hero_disarms(engine)
    assert disarmed(engine) == []


def test_smaller_target_saves_with_disadvantage(registry):
    engine = duel(registry, SAVE, ScriptedRng(d20=[18, 3]))
    hero_disarms(engine)
    # помеха: меньший из 18 и 3
    assert len(disarmed(engine)) == 1
    assert engine.rng.left("d20") == 0


def test_disadvantage_label_is_in_the_log(registry):
    engine = duel(registry, SAVE, ScriptedRng(d20=[3, 15]))
    hero_disarms(engine)
    assert "мельче" in log(engine)


def test_save_mode_has_no_check_and_no_attack_roll(registry):
    engine = duel(registry, SAVE, ScriptedRng(d20=[3, 15]))
    hero_disarms(engine)
    assert engine.rng.left("d20") == 0
    assert "удерживает оружие" not in log(engine)
    assert "проверка цели" not in log(engine)


def test_save_mode_spends_the_action_on_failure_of_the_save(registry):
    engine = duel(registry, SAVE, ScriptedRng(d20=[3, 15]))
    hero_disarms(engine)
    assert turn(engine, "hero").action is False


def test_save_mode_spends_the_action_on_success_of_the_save(registry):
    engine = duel(registry, SAVE, ScriptedRng(d20=[18, 19]))
    hero_disarms(engine)
    assert turn(engine, "hero").action is False


def test_save_mode_spends_the_extra_attack(registry):
    engine = duel(registry, SAVE, ScriptedRng(d20=[18, 19]))
    turn(engine, "hero").action = False
    turn(engine, "hero").attacks_left = 1
    hero_disarms(engine)
    assert turn(engine, "hero").attacks_left == 0


def test_save_mode_logs_the_outcome_line(registry):
    engine = duel(registry, SAVE, ScriptedRng(d20=[3, 15]))
    hero_disarms(engine)
    assert "выбивает скимитар" in log(engine)


def test_passed_save_has_no_outcome_line(registry):
    engine = duel(registry, SAVE, ScriptedRng(d20=[18, 19]))
    hero_disarms(engine)
    assert "выбивает" not in log(engine)


def test_unarmed_hero_grabs_the_weapon_in_save_mode(registry):
    hero = make_fighter(registry)
    for entry in list(hero.inventory):
        if registry.has("weapon", entry.item_id):
            remove_item(hero, entry.item_id, entry.qty)
    engine = duel(registry, SAVE, ScriptedRng(d20=[3, 15]), hero=hero)
    hero_disarms(engine)
    assert count_item(hero, "scimitar") == 1
    assert hero.equipped.main_hand == "scimitar"
    assert engine.state.ground_items == []


# --- двуручный хват и размер цели ---

def rival_duel(registry, rng, weapon="greatsword"):
    rival = make_fighter(registry, "rival")
    give_weapon(rival, registry, weapon)
    engine = make_engine(
        registry, SAVE, heroes=[make_fighter(registry), rival], rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    part(engine, "rival").side = "enemies"
    part(engine, "rival").group_id = "goblins"
    return engine


def test_two_handed_grip_gives_the_target_advantage(registry):
    # спас Сил +5 соперника: с преимуществом берётся больший d20 (18): 23 >= 13 -- удержал
    engine = rival_duel(registry, ScriptedRng(d20=[2, 18]))
    engine.perform("hero", "disarm:rival:greatsword")
    assert engine.heroes["rival"].equipped.main_hand == "greatsword"
    assert engine.rng.left("d20") == 0


def test_two_handed_grip_label_is_in_the_log(registry):
    engine = rival_duel(registry, ScriptedRng(d20=[2, 18]))
    engine.perform("hero", "disarm:rival:greatsword")
    assert "двуручный хват" in log(engine)


def test_two_handed_target_loses_the_weapon_when_both_dice_are_low(registry):
    engine = rival_duel(registry, ScriptedRng(d20=[2, 3]))
    engine.perform("hero", "disarm:rival:greatsword")
    assert engine.heroes["rival"].equipped.main_hand is None


def test_one_handed_equal_size_target_rolls_one_die(registry):
    engine = rival_duel(registry, ScriptedRng(d20=[2]), weapon="longsword")
    engine.perform("hero", "disarm:rival:longsword")
    assert engine.rng.left("d20") == 0
    assert engine.heroes["rival"].equipped.main_hand is None


def test_hero_target_saves_with_strength(registry):
    engine = rival_duel(registry, ScriptedRng(d20=[2]), weapon="longsword")
    engine.perform("hero", "disarm:rival:longsword")
    assert any("спасбросок str" in line for line in engine.state.log)


# --- гоблин-обезоруживающий против героя ---

def test_goblin_dc_is_twelve(registry, monkeypatch):
    engine = disarmer(registry, SAVE, monkeypatch, ScriptedRng(d20=[1, 1]))
    goblin_disarms(engine)
    assert any(x.startswith("  СЛ 12 (") for x in engine.state.log)


def test_hero_saves_with_strength_against_the_goblin(registry, monkeypatch):
    engine = disarmer(registry, SAVE, monkeypatch, ScriptedRng(d20=[1, 1]))
    goblin_disarms(engine)
    assert any("спасбросок str" in line for line in engine.state.log)


def test_hero_larger_than_the_goblin_saves_with_advantage(registry, monkeypatch):
    engine = disarmer(registry, SAVE, monkeypatch, ScriptedRng(d20=[1, 18]))
    goblin_disarms(engine)
    # преимущество: больший 18 + 5 >= 12
    assert engine.heroes["hero"].equipped.main_hand == "longsword"
    assert engine.rng.left("d20") == 0


def test_larger_label_is_in_the_log(registry, monkeypatch):
    engine = disarmer(registry, SAVE, monkeypatch, ScriptedRng(d20=[1, 18]))
    goblin_disarms(engine)
    assert "крупнее" in log(engine)


def test_hero_loses_the_sword_when_both_dice_are_low(registry, monkeypatch):
    # больший 6 + 5 = 11 < 12
    engine = disarmer(registry, SAVE, monkeypatch, ScriptedRng(d20=[2, 6]))
    goblin_disarms(engine)
    assert engine.heroes["hero"].equipped.main_hand is None


def test_hero_save_equal_to_the_dc_keeps_the_sword(registry, monkeypatch):
    # 7 + 5 = 12 = СЛ
    engine = disarmer(registry, SAVE, monkeypatch, ScriptedRng(d20=[2, 7]))
    goblin_disarms(engine)
    assert engine.heroes["hero"].equipped.main_hand == "longsword"


def test_goblin_gets_the_used_mark_in_save_mode(registry, monkeypatch):
    engine = disarmer(registry, SAVE, monkeypatch, ScriptedRng(d20=[1, 18]))
    goblin_disarms(engine)
    assert [e.id for e in creature(engine, "goblin_1").active_effects] == ["disarm_used"]


def test_hero_disarm_leaves_no_used_mark_in_save_mode(registry):
    engine = duel(registry, SAVE, ScriptedRng(d20=[18, 19]))
    hero_disarms(engine)
    assert creature(engine, "hero").active_effects == []


# --- check-режим не затронут ---

def test_check_mode_still_rolls_a_check_and_an_attack(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[5, 5, 15]))
    hero_disarms(engine)
    assert engine.rng.left("d20") == 0
    assert "удерживает оружие" in log(engine)
    assert "  СЛ " not in log(engine)
    assert len(disarmed(engine)) == 1


# --- improvise disarm не зависит от режима ---

def test_improvised_disarm_ignores_the_mode(registry):
    engine = duel(registry, SAVE, ScriptedRng(d20=[10]))
    engine.improvise("hero", skill="athletics", category="medium", effect="disarm",
                     target="goblin_1")
    assert len(disarmed(engine)) == 1
    assert "  СЛ " not in log(engine)


# --- check-режим: подробности состязания (переехали в disarm.contest) ---

def test_check_mode_attack_line_shows_the_bonus_parts_and_the_target_check(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[5, 5, 15]))
    hero_disarms(engine)
    line = [x for x in engine.state.log if "Атака (" in x][0]
    assert "+ 3 Сил + 2 мастерство" in line
    assert "(проверка цели)" in line


def test_check_mode_natural_twenty_is_a_critical_hit_that_disarms(registry, cfg):
    # проверка цели 20 + 2 = 22 -> КД 23; натуральная 20 героя -- критическое попадание
    engine = duel(registry, cfg, ScriptedRng(d20=[20, 20, 20]))
    hero_disarms(engine)
    assert len(disarmed(engine)) == 1
    assert "критическое попадание" in log(engine)


def test_check_mode_natural_one_never_disarms(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[1, 1, 1]))
    hero_disarms(engine)
    assert disarmed(engine) == []


def test_dc_line_is_exactly_eight_plus_ability_plus_proficiency(registry):
    engine = duel(registry, SAVE, ScriptedRng(d20=[3, 15]))
    hero_disarms(engine)
    assert "  СЛ 13 (8 + Сил 3 + мастерство 2); мельче" in engine.state.log


def test_goblin_dc_line_uses_the_dexterity_label(registry, monkeypatch):
    engine = disarmer(registry, SAVE, monkeypatch, ScriptedRng(d20=[1, 18]))
    goblin_disarms(engine)
    assert "  СЛ 12 (8 + Лов 2 + мастерство 2); крупнее" in engine.state.log


def test_used_mark_is_a_flag(registry, monkeypatch):
    engine = disarmer(registry, SAVE, monkeypatch, ScriptedRng(d20=[1, 18]))
    goblin_disarms(engine)
    mark = creature(engine, "goblin_1").active_effects[0]
    assert (mark.id, mark.kind, mark.source) == ("disarm_used", "flag", "goblin_1")


def test_hero_with_a_bow_in_hand_takes_out_the_sword_to_disarm(registry, cfg):
    hero = make_ranger(registry)
    assert hero.equipped.main_hand == "longbow"
    engine = duel(registry, cfg, ScriptedRng(d20=[5, 5, 15]), hero=hero)
    hero_disarms(engine)
    assert hero.equipped.main_hand == "scimitar"


# --- К7х ревью: пометка режима в строке СЛ ---

def dc_line(engine):
    return [x for x in engine.state.log if x.startswith("  СЛ ")][0]


def test_dc_line_ends_with_the_size_label(registry):
    engine = duel(registry, SAVE, ScriptedRng(d20=[3, 15]))
    hero_disarms(engine)
    assert dc_line(engine).endswith("); мельче")


def test_dc_line_has_no_label_tail_for_equal_sizes(registry, monkeypatch):
    monkeypatch.setattr(registry.get("monster", "goblin_warrior"), "size", "medium")
    engine = duel(registry, SAVE, ScriptedRng(d20=[3, 15]))
    hero_disarms(engine)
    assert dc_line(engine).endswith(")")
