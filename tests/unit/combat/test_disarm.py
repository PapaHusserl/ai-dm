# Отбор оружия (docs/COMBAT-DISARM-PLAN.md, В1-В11 по рекомендациям): действие движка "disarm".
#   Опция: kind "disarm" (id "disarm:<цель>:<оружие>"), params {"target": ref, "weapon_id": id
#     оружия цели}; ближний бой (одна зона); цель боеспособна и держит оружие; одна опция на
#     оружие цели (оружейное действие монстра / оружие в руке героя). Тратит атаку: действие
#     или attacks_left (Дополнительная атака). Монстру опция доступна только с тегом "disarmer".
#   Состязание: цель бросает проверку (монстр -- d20 + лучший мод Силы/Ловкости), ПОТОМ герой --
#     бросок атаки текущим ближним оружием (безоружный удар, если оружия нет) против её итога;
#     ничья -- попадание, 1 на d20 -- промах (как у любой атаки). Порядок бросков в ScriptedRng:
#     сначала d20 цели (два при преимуществе/помехе), потом d20 героя.
#     Преимущество цели: оружие two_handed; цель крупнее героя. Помеха цели: цель мельче.
#     Преимущество и помеха гасятся. Гоблин (small) мельче героя (medium): его проверка с помехой.
#   Успех: монстру ActiveEffect(id="disarmed", params={"weapon_id": X}) + GroundItem в зоне цели
#     (owner_ref -- у кого выбили); герою оружие уходит из инвентаря (1 шт.) и из main_hand.
#     Если герой бил безоружным -- оружие сразу в инвентарь и main_hand ("выхватил"), GroundItem
#     нет. Провал -- ничего, атака потрачена.
#   improvise "disarm" идёт через ту же логику (СЛ задаёт категория, не состязание).
#   Враги по умолчанию (нет тега disarmer) героя не обезоруживают.
from combat_kit import (
    ScriptedRng,
    creature,
    make_engine,
    make_fighter,
    mon,
    option_ids,
    part,
    turn,
)

from ai_dm.combat import available
from ai_dm.content.models.monsters import MonsterAction
from ai_dm.rules.inventory import add_item, count_item, remove_item
from ai_dm.state.combat import GroundItem
from ai_dm.state.creature import ActiveEffect

# скимитар гоблина: проверка цели с помехой (два d20), потом бросок героя
WIN = [5, 5, 15]
LOSE = [15, 15, 2]


def duel(registry, cfg, rng=None, monster="goblin_warrior", zone="hall", hero=None):
    return make_engine(
        registry, cfg, heroes=[hero or make_fighter(registry)], rng=rng,
        monsters=[mon("goblin_1", monster, zone)],
    )


def disarm_options(engine, ref="hero"):
    return [o for o in engine.available_actions(ref) if o.kind == "disarm"]


def disarm_id(engine, target="goblin_1", weapon="scimitar", ref="hero"):
    found = [
        o for o in disarm_options(engine, ref)
        if o.params["target"] == target and o.params["weapon_id"] == weapon
    ]
    return found[0].id


def do_disarm(engine, target="goblin_1", weapon="scimitar"):
    return engine.perform("hero", disarm_id(engine, target, weapon))


def flags(engine, ref="goblin_1"):
    return [(e.id, e.params) for e in creature(engine, ref).active_effects]


def unarmed_hero(registry):
    hero = make_fighter(registry)
    for entry in list(hero.inventory):
        if registry.has("weapon", entry.item_id):
            remove_item(hero, entry.item_id, entry.qty)
    return hero


def improvise_disarm(engine, target="goblin_1"):
    engine.improvise("hero", skill="athletics", category="medium", effect="disarm", target=target)


# --- опции ---

def test_hero_next_to_the_goblin_can_disarm_each_weapon(registry, cfg):
    engine = duel(registry, cfg)
    weapons = sorted(o.params["weapon_id"] for o in disarm_options(engine))
    assert weapons == ["scimitar", "shortbow"]


def test_disarm_option_targets_the_goblin(registry, cfg):
    engine = duel(registry, cfg)
    assert {o.params["target"] for o in disarm_options(engine)} == {"goblin_1"}


def test_disarm_option_id_names_the_target_and_the_weapon(registry, cfg):
    engine = duel(registry, cfg, monster="guard")
    assert [o.id for o in disarm_options(engine)] == ["disarm:goblin_1:spear"]


def test_guard_offers_only_the_spear(registry, cfg):
    engine = duel(registry, cfg, monster="guard")
    assert [o.params["weapon_id"] for o in disarm_options(engine)] == ["spear"]


def test_no_disarm_option_against_a_target_in_another_zone(registry, cfg):
    engine = duel(registry, cfg, zone="balcony")
    assert disarm_options(engine) == []


def test_no_disarm_option_against_a_target_without_weapon_actions(registry, cfg, monkeypatch):
    bite = MonsterAction(
        name="Укус", kind="melee", attack_bonus=4, damage_dice="1d4", damage_type="piercing"
    )
    monkeypatch.setattr(registry.get("monster", "goblin_warrior"), "actions", [bite])
    engine = duel(registry, cfg)
    assert disarm_options(engine) == []


def test_no_disarm_option_without_an_action(registry, cfg):
    engine = duel(registry, cfg)
    turn(engine, "hero").action = False
    assert disarm_options(engine) == []


def test_disarm_is_offered_by_the_extra_attack(registry, cfg):
    engine = duel(registry, cfg)
    turn(engine, "hero").action = False
    turn(engine, "hero").attacks_left = 1
    assert disarm_options(engine) != []


def test_extra_attack_disarm_spends_the_attack_not_the_action(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10, 10, 10]))
    turn(engine, "hero").action = False
    turn(engine, "hero").attacks_left = 1
    do_disarm(engine)
    assert (turn(engine, "hero").attacks_left, turn(engine, "hero").action) == (0, False)


def test_extra_attack_disarm_label_shows_the_attacks_left(registry, cfg):
    engine = duel(registry, cfg)
    turn(engine, "hero").action = False
    turn(engine, "hero").attacks_left = 1
    assert all(o.label.endswith("(ещё 1 из 2)") for o in disarm_options(engine))


def test_already_taken_weapon_is_not_offered_again(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[3, 3, 19]))
    do_disarm(engine)
    turn(engine, "hero").action = True
    assert [o.params["weapon_id"] for o in disarm_options(engine)] == ["shortbow"]


def test_target_that_is_down_is_not_a_disarm_target(registry, cfg):
    engine = duel(registry, cfg)
    part(engine, "goblin_1").status = "down"
    assert disarm_options(engine) == []


def test_monster_has_no_disarm_option_by_default(registry, cfg):
    engine = duel(registry, cfg)
    assert not [i for i in option_ids(engine, "goblin_1") if i.startswith("disarm")]


# --- состязание ---

def test_success_marks_the_weapon_as_taken(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=WIN))
    do_disarm(engine)
    assert flags(engine) == [("disarmed", {"weapon_id": "scimitar"})]


def test_success_drops_the_weapon_in_the_target_zone(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=WIN))
    do_disarm(engine)
    assert engine.state.ground_items == [
        GroundItem(
            item_id="scimitar", zone_id="hall", owner_ref="goblin_1", cost_cp=250, quality="junk"
        )
    ]


def test_success_is_logged(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=WIN))
    do_disarm(engine)
    assert any("выбивает скимитар" in line for line in engine.state.log)


def test_success_spends_the_action(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=WIN))
    do_disarm(engine)
    assert turn(engine, "hero").action is False


def test_success_does_not_hurt_the_target(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=WIN))
    do_disarm(engine)
    assert creature(engine, "goblin_1").hp_current == 10


def test_failure_changes_nothing_but_spends_the_action(registry, cfg):
    # 2 + 5 = 7 против 15 + 2 = 17
    engine = duel(registry, cfg, ScriptedRng(d20=LOSE))
    do_disarm(engine)
    assert (flags(engine), engine.state.ground_items) == ([], [])
    assert turn(engine, "hero").action is False


def test_target_wins_the_tie_and_keeps_the_weapon(registry, cfg):
    # проверка 13 + 2 = 15; атака 10 + 5 = 15 -- ничья, оружие остаётся
    engine = duel(registry, cfg, ScriptedRng(d20=[13, 13, 10]))
    do_disarm(engine)
    assert flags(engine) == []
    assert engine.state.ground_items == []


def test_one_more_than_the_check_wins(registry, cfg):
    # проверка 13 + 2 = 15; атака 11 + 5 = 16
    engine = duel(registry, cfg, ScriptedRng(d20=[13, 13, 11]))
    do_disarm(engine)
    assert len(flags(engine)) == 1


def test_one_less_than_the_check_loses(registry, cfg):
    # проверка 13 + 2 = 15; атака 9 + 5 = 14
    engine = duel(registry, cfg, ScriptedRng(d20=[13, 13, 9]))
    do_disarm(engine)
    assert flags(engine) == []


def test_natural_one_always_misses(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[1, 1, 1]))
    do_disarm(engine)
    assert flags(engine) == []


def test_target_uses_the_better_of_strength_and_dexterity(registry, cfg, monkeypatch):
    # у гоблина Сил 8 (-1), Лов 15 (+2); с Силой 18 (+4): проверка 11 + 4 = 15, атака 9 + 5 = 14
    # (с Лов +2 проверка была бы 13 и герой выиграл)
    monkeypatch.setitem(registry.get("monster", "goblin_warrior").abilities, "str", 18)
    engine = duel(registry, cfg, ScriptedRng(d20=[11, 11, 9]))
    do_disarm(engine)
    assert flags(engine) == []


def test_smaller_target_rolls_with_disadvantage(registry, cfg):
    # гоблин (small) мельче героя (medium): берётся меньшая из 18 и 3 -> 5; атака 12 + 5 = 17
    engine = duel(registry, cfg, ScriptedRng(d20=[18, 3, 12]))
    do_disarm(engine)
    assert len(flags(engine)) == 1


def test_smaller_target_without_the_low_die_would_have_won(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[18, 18, 12]))
    do_disarm(engine)
    assert flags(engine) == []


def test_two_handed_weapon_gives_the_target_advantage(registry, cfg, monkeypatch):
    # короткий лук двуручный; цель среднего роста, как герой: берётся больший из 5 и 16 -> 18
    monkeypatch.setattr(registry.get("monster", "goblin_warrior"), "size", "medium")
    engine = duel(registry, cfg, ScriptedRng(d20=[5, 16, 12]))
    do_disarm(engine, weapon="shortbow")
    assert flags(engine) == []


def test_two_handed_advantage_is_not_needed_when_the_first_die_is_enough(
    registry, cfg, monkeypatch
):
    monkeypatch.setattr(registry.get("monster", "goblin_warrior"), "size", "medium")
    engine = duel(registry, cfg, ScriptedRng(d20=[5, 3, 12]))
    do_disarm(engine, weapon="shortbow")
    assert len(flags(engine)) == 1


def test_one_handed_weapon_of_an_equal_size_target_rolls_one_die(registry, cfg, monkeypatch):
    monkeypatch.setattr(registry.get("monster", "goblin_warrior"), "size", "medium")
    rng = ScriptedRng(d20=[5, 12])
    engine = duel(registry, cfg, rng)
    do_disarm(engine, weapon="scimitar")
    assert rng.left("d20") == 0
    assert len(flags(engine)) == 1


def test_larger_target_rolls_with_advantage(registry, cfg, monkeypatch):
    monkeypatch.setattr(registry.get("monster", "goblin_warrior"), "size", "large")
    engine = duel(registry, cfg, ScriptedRng(d20=[5, 16, 12]))
    do_disarm(engine)
    assert flags(engine) == []


def test_two_handed_weapon_of_a_smaller_target_cancels_out(registry, cfg):
    # гоблин мельче (помеха), лук двуручный (преимущество): один d20 у цели
    rng = ScriptedRng(d20=[5, 12])
    engine = duel(registry, cfg, rng)
    do_disarm(engine, weapon="shortbow")
    assert (rng.left("d20"), len(flags(engine))) == (0, 1)


def test_equal_size_one_handed_target_rolls_one_die(registry, cfg):
    rng = ScriptedRng(d20=[5, 12])
    engine = duel(registry, cfg, rng, monster="guard")
    do_disarm(engine, weapon="spear")
    assert (rng.left("d20"), len(flags(engine))) == (0, 1)


# --- «выхватил»: бьёт безоружным ---

def test_unarmed_hero_grabs_the_weapon(registry, cfg):
    hero = unarmed_hero(registry)
    engine = duel(registry, cfg, ScriptedRng(d20=WIN), hero=hero)
    do_disarm(engine)
    assert (hero.equipped.main_hand, count_item(hero, "scimitar")) == ("scimitar", 1)


def test_grabbed_weapon_does_not_lie_on_the_ground(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=WIN), hero=unarmed_hero(registry))
    do_disarm(engine)
    assert engine.state.ground_items == []


def test_grabbed_weapon_is_still_taken_from_the_target(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=WIN), hero=unarmed_hero(registry))
    do_disarm(engine)
    assert flags(engine) == [("disarmed", {"weapon_id": "scimitar"})]


def test_hero_with_a_weapon_in_hand_does_not_grab(registry, cfg):
    hero = make_fighter(registry)
    engine = duel(registry, cfg, ScriptedRng(d20=WIN), hero=hero)
    do_disarm(engine)
    assert (hero.equipped.main_hand, count_item(hero, "scimitar")) == ("longsword", 0)


def test_two_handed_trophy_is_not_taken_in_hand_with_a_shield(registry, cfg):
    hero = unarmed_hero(registry)
    engine = duel(registry, cfg, ScriptedRng(d20=[5, 12]), hero=hero)
    do_disarm(engine, weapon="shortbow")
    assert hero.equipped.main_hand is None
    assert count_item(hero, "shortbow") == 1


# --- герой обезоружен ---

def rival_duel(registry, cfg, rng):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry), make_fighter(registry, "rival")],
        rng=rng, monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    part(engine, "rival").side = "enemies"
    part(engine, "rival").group_id = "goblins"
    return engine


def test_disarmed_hero_loses_the_main_hand_weapon(registry, cfg):
    engine = rival_duel(registry, cfg, ScriptedRng(d20=[10]))
    improvise_disarm(engine, "rival")
    assert engine.heroes["rival"].equipped.main_hand is None


def test_disarmed_hero_loses_the_weapon_from_the_inventory(registry, cfg):
    engine = rival_duel(registry, cfg, ScriptedRng(d20=[10]))
    improvise_disarm(engine, "rival")
    assert count_item(engine.heroes["rival"], "longsword") == 0


def test_disarmed_hero_weapon_lies_on_the_ground_with_its_owner(registry, cfg):
    engine = rival_duel(registry, cfg, ScriptedRng(d20=[10]))
    improvise_disarm(engine, "rival")
    assert engine.state.ground_items == [
        GroundItem(item_id="longsword", zone_id="hall", owner_ref="rival", cost_cp=1500)
    ]


def test_disarmed_hero_gives_up_only_one_of_several_copies(registry, cfg):
    engine = rival_duel(registry, cfg, ScriptedRng(d20=[10]))
    add_item(engine.heroes["rival"], "longsword", cost_cp=0)
    improvise_disarm(engine, "rival")
    assert count_item(engine.heroes["rival"], "longsword") == 1


def test_disarmed_hero_still_has_unarmed_and_improvised_attacks(registry, cfg):
    engine = rival_duel(registry, cfg, ScriptedRng(d20=[10]))
    improvise_disarm(engine, "rival")
    # (available_actions героя на стороне врагов падает в переговорах, поэтому напрямую)
    ids = [o.id for o in available.attack_options(engine, "rival")]
    assert "attack:longsword:hero" not in ids
    assert {"attack:unarmed:hero", "attack:improvised:hero"} <= set(ids)
    assert "attack:improvised_thrown:hero" in ids


def test_hero_disarmed_by_the_action_does_not_get_his_sword_back_in_attacks(registry, cfg):
    engine = rival_duel(registry, cfg, ScriptedRng(d20=[10]))
    improvise_disarm(engine, "rival")
    assert "attack:longsword:hero" not in [o.id for o in available.attack_options(engine, "rival")]


def test_hero_without_a_weapon_in_hand_has_nothing_to_take(registry, cfg):
    engine = rival_duel(registry, cfg, ScriptedRng())
    engine.heroes["rival"].equipped.main_hand = None
    assert [
        o for o in available.disarm_options(engine, "hero") if o.params["target"] == "rival"
    ] == []


def test_hero_with_a_weapon_in_hand_can_be_disarmed_by_the_action(registry, cfg):
    engine = rival_duel(registry, cfg, ScriptedRng())
    assert [
        o.id for o in available.disarm_options(engine, "hero") if o.params["target"] == "rival"
    ] == ["disarm:rival:longsword"]


# --- improvise «disarm» идёт через общую логику ---

def test_improvise_disarm_of_a_monster_takes_a_concrete_weapon(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10]))
    improvise_disarm(engine)
    assert flags(engine) == [("disarmed", {"weapon_id": "scimitar"})]


def test_improvise_disarm_puts_the_monster_weapon_on_the_ground(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10]))
    improvise_disarm(engine)
    assert engine.state.ground_items == [
        GroundItem(
            item_id="scimitar", zone_id="hall", owner_ref="goblin_1", cost_cp=250, quality="junk"
        )
    ]


def test_improvise_disarm_leaves_the_other_weapon_of_the_monster(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10]))
    improvise_disarm(engine)
    ids = option_ids(engine, "goblin_1")
    assert "attack:короткий_лук:hero" in ids
    assert "attack:скимитар:hero" not in ids


def test_improvise_disarm_with_an_empty_hand_grabs_the_weapon(registry, cfg):
    hero = unarmed_hero(registry)
    engine = duel(registry, cfg, ScriptedRng(d20=[10]), hero=hero)
    improvise_disarm(engine)
    assert hero.equipped.main_hand == "scimitar"
    assert engine.state.ground_items == []


def test_improvise_disarm_of_a_naturally_armed_target_does_nothing(registry, cfg, monkeypatch):
    bite = MonsterAction(
        name="Укус", kind="melee", attack_bonus=4, damage_dice="1d4", damage_type="piercing"
    )
    monkeypatch.setattr(registry.get("monster", "goblin_warrior"), "actions", [bite])
    engine = duel(registry, cfg, ScriptedRng(d20=[10]))
    improvise_disarm(engine)
    assert (flags(engine), engine.state.ground_items) == ([], [])


def test_improvise_disarm_of_a_naturally_armed_target_says_there_is_nothing_to_take(
    registry, cfg, monkeypatch
):
    bite = MonsterAction(
        name="Укус", kind="melee", attack_bonus=4, damage_dice="1d4", damage_type="piercing"
    )
    monkeypatch.setattr(registry.get("monster", "goblin_warrior"), "actions", [bite])
    engine = duel(registry, cfg, ScriptedRng(d20=[10]))
    improvise_disarm(engine)
    assert any("нечего выбивать" in line for line in engine.state.log)


def test_failed_improvise_disarm_takes_nothing(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[2]))
    improvise_disarm(engine)
    assert (flags(engine), engine.state.ground_items) == ([], [])


# --- враги: только с тегом disarmer ---

def test_default_enemy_never_disarms_the_hero(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[2, 2, 2], d6=[1]))
    engine.state.turn_index = 1
    engine.step()
    assert engine.state.ground_items == []
    assert engine.heroes["hero"].equipped.main_hand == "longsword"


def test_monster_with_the_disarmer_tag_can_disarm_the_hero(registry, cfg, monkeypatch):
    monkeypatch.setattr(registry.get("monster", "goblin_warrior"), "tags", ["disarmer"])
    engine = duel(registry, cfg)
    assert [o.id for o in disarm_options(engine, "goblin_1")] == ["disarm:hero:longsword"]


def test_disarmer_monster_tries_to_disarm_on_its_turn(registry, cfg, monkeypatch):
    monkeypatch.setattr(registry.get("monster", "goblin_warrior"), "tags", ["disarmer"])
    # проверка героя (преимущество: гоблин мельче -- у героя помехи нет, крупнее -- два d20)
    engine = duel(registry, cfg, ScriptedRng(d20=[20, 20, 2]))
    engine.state.turn_index = 1
    engine.step()
    assert any("обезоруживание" in line for line in engine.state.log)
    assert engine.heroes["hero"].equipped.main_hand == "longsword"


def test_active_effect_with_another_id_is_not_a_taken_weapon(registry, cfg):
    engine = duel(registry, cfg)
    creature(engine, "goblin_1").active_effects.append(
        ActiveEffect(id="parley_tried", source="hero", kind="flag")
    )
    assert sorted(o.params["weapon_id"] for o in disarm_options(engine)) == [
        "scimitar", "shortbow",
    ]
