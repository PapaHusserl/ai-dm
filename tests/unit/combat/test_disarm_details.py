# Отбор оружия: детали (разбор мутантов combat/disarm.py, combat/end.py::settle_ground).
# Герой как цель проверяется вызовами combat.disarm напрямую: действие героя против героя
# другой стороны в меню упирается в переговоры (участник без monster_id), это вне партии.
from combat_kit import ScriptedRng, creature, make_engine, make_fighter, mon

from ai_dm.combat import disarm
from ai_dm.rules.inventory import add_item, count_item, equip, remove_item
from ai_dm.state.combat import GroundItem
from ai_dm.state.creature import AppliedCondition


def duel(registry, cfg, rng=None, monster="goblin_warrior", hero=None):
    return make_engine(
        registry, cfg, heroes=[hero or make_fighter(registry)], rng=rng,
        monsters=[mon("goblin_1", monster, "hall")],
    )


def rival_duel(registry, cfg, rng=None):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry), make_fighter(registry, "rival")],
        rng=rng, monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    engine.part("rival").side = "enemies"
    engine.part("rival").group_id = "goblins"
    return engine


def log_has(engine, text):
    return any(text in line for line in engine.state.log)


def run(engine, target="goblin_1", weapon="scimitar"):
    return engine.perform("hero", f"disarm:{target}:{weapon}")


# --- хват двумя руками у героя-цели ---

def test_hero_with_a_versatile_weapon_and_free_hands_holds_it_with_two_hands(registry, cfg):
    engine = rival_duel(registry, cfg)
    rival = engine.heroes["rival"]
    rival.equipped.shield = None
    equip(rival, "spear", registry)
    assert disarm.target_mode(engine, "hero", "rival", "spear") == ("advantage", "двуручный хват")


def test_hero_with_a_shield_holds_a_versatile_weapon_with_one_hand(registry, cfg):
    engine = rival_duel(registry, cfg)
    rival = engine.heroes["rival"]
    equip(rival, "spear", registry)
    assert rival.equipped.shield is not None
    assert disarm.target_mode(engine, "hero", "rival", "spear") == ("normal", "")


def test_hero_with_an_off_hand_weapon_holds_a_versatile_weapon_with_one_hand(registry, cfg):
    engine = rival_duel(registry, cfg)
    rival = engine.heroes["rival"]
    rival.equipped.shield = None
    add_item(rival, "dagger", cost_cp=0)
    equip(rival, "dagger", registry, "off_hand")
    equip(rival, "spear", registry)
    assert disarm.target_mode(engine, "hero", "rival", "spear") == ("normal", "")


def test_monster_with_a_versatile_weapon_holds_it_with_one_hand(registry, cfg):
    engine = duel(registry, cfg, monster="guard")
    assert disarm.target_mode(engine, "hero", "goblin_1", "spear") == ("normal", "")


def test_hero_with_a_one_handed_weapon_gets_no_advantage(registry, cfg):
    engine = rival_duel(registry, cfg)
    engine.heroes["rival"].equipped.shield = None
    assert disarm.target_mode(engine, "hero", "rival", "scimitar") == ("normal", "")


# --- подписи режима ---

def test_mode_labels_are_joined_with_a_comma(registry, cfg, monkeypatch):
    monkeypatch.setattr(registry.get("monster", "goblin_warrior"), "size", "large")
    engine = duel(registry, cfg)
    assert disarm.target_mode(engine, "hero", "goblin_1", "shortbow") == (
        "advantage", "двуручный хват, крупнее"
    )


def test_larger_target_label(registry, cfg, monkeypatch):
    monkeypatch.setattr(registry.get("monster", "goblin_warrior"), "size", "large")
    engine = duel(registry, cfg)
    assert disarm.target_mode(engine, "hero", "goblin_1", "scimitar") == ("advantage", "крупнее")


def test_smaller_target_label(registry, cfg):
    engine = duel(registry, cfg)
    assert disarm.target_mode(engine, "hero", "goblin_1", "scimitar") == ("disadvantage", "мельче")


def test_mode_label_reaches_the_check_line(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[5, 5, 15]))
    run(engine)
    assert log_has(engine, "преим.: мельче") or log_has(engine, "помеха: мельче")


def test_attack_line_names_the_target_check(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[5, 5, 15]))
    run(engine)
    assert log_has(engine, "(проверка цели)")


def test_attack_line_shows_the_attack_bonus_parts(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[5, 5, 15]))
    run(engine)
    assert log_has(engine, "+ 3 Сил + 2 мастерство")


# --- проверка цели-героя ---

def test_hero_target_checks_with_the_better_of_athletics_and_acrobatics(registry, cfg):
    engine = rival_duel(registry, cfg, ScriptedRng(d20=[10]))
    # Сил 17 (+3) и мастерство Атлетики +2 = +5, Акробатика +1
    assert disarm.target_check(engine, "rival", "normal", "").total == 15


def test_hero_target_prefers_acrobatics_when_it_is_better(registry, cfg):
    engine = rival_duel(registry, cfg, ScriptedRng(d20=[10]))
    rival = engine.heroes["rival"]
    rival.sheet.abilities["dex"] = 20
    rival.sheet.abilities["str"] = 8
    assert disarm.target_check(engine, "rival", "normal", "").total == 15


def test_hero_target_check_line_names_the_skill(registry, cfg):
    engine = rival_duel(registry, cfg, ScriptedRng(d20=[10]))
    disarm.target_check(engine, "rival", "normal", "")
    assert log_has(engine, "Атлетика (Сил): d20 (10) + 3 Сил + 2 мастерство = 15")


def test_monster_target_check_line_names_the_ability(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10]))
    disarm.target_check(engine, "goblin_1", "normal", "")
    assert log_has(engine, "Проверка Лов: d20 (10) + 2 Лов = 12")


def test_conditions_of_the_target_apply_to_its_check(registry, cfg):
    # отравленный проверяет с помехой: два d20 даже у цели того же размера
    rng = ScriptedRng(d20=[5, 5, 12])
    engine = duel(registry, cfg, rng, monster="guard")
    creature(engine, "goblin_1").conditions.append(AppliedCondition(id="poisoned", source="x"))
    run(engine, weapon="spear")
    assert rng.left("d20") == 0


# --- исходы ---

def test_natural_twenty_disarms_even_against_a_huge_check(registry, cfg, monkeypatch):
    monkeypatch.setitem(registry.get("monster", "goblin_warrior").abilities, "dex", 40)
    engine = duel(registry, cfg, ScriptedRng(d20=[20, 20, 20]))
    run(engine)
    assert len(creature(engine, "goblin_1").active_effects) == 1


def test_disarmed_flag_is_a_flag(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[5, 5, 15]))
    run(engine)
    assert [e.kind for e in creature(engine, "goblin_1").active_effects] == ["flag"]


def test_disarmed_hero_with_two_copies_loses_the_one_in_hand(registry, cfg):
    engine = rival_duel(registry, cfg)
    rival = engine.heroes["rival"]
    add_item(rival, "longsword", cost_cp=0)
    disarm.strip_weapon(engine, "hero", "rival", "longsword")
    assert rival.equipped.main_hand is None
    assert count_item(rival, "longsword") == 1


def test_disarmed_hero_keeps_another_weapon_in_hand(registry, cfg):
    engine = rival_duel(registry, cfg)
    rival = engine.heroes["rival"]
    add_item(rival, "spear", cost_cp=0)
    disarm.strip_weapon(engine, "hero", "rival", "spear")
    assert rival.equipped.main_hand == "longsword"


def test_grab_is_logged(registry, cfg):
    hero = make_fighter(registry)
    for entry in list(hero.inventory):
        if registry.has("weapon", entry.item_id):
            remove_item(hero, entry.item_id, entry.qty)
    engine = duel(registry, cfg, ScriptedRng(d20=[5, 5, 15]), hero=hero)
    run(engine)
    assert log_has(engine, "выбивает скимитар у Воин-гоблин и подхватывает")


def test_unarmed_hero_without_a_shield_takes_a_two_handed_weapon_in_hand(registry, cfg):
    hero = make_fighter(registry)
    for entry in list(hero.inventory):
        if registry.has("weapon", entry.item_id):
            remove_item(hero, entry.item_id, entry.qty)
    hero.equipped.shield = None
    engine = duel(registry, cfg, ScriptedRng(d20=[5, 12]), hero=hero)
    run(engine, weapon="shortbow")
    assert hero.equipped.main_hand == "shortbow"


def test_hero_with_a_spare_weapon_but_empty_hand_draws_it_for_the_strike(registry, cfg):
    hero = make_fighter(registry)
    hero.equipped.main_hand = None
    engine = duel(registry, cfg, ScriptedRng(d20=[5, 5, 15]), hero=hero)
    run(engine)
    assert hero.equipped.main_hand is not None


def test_hero_with_the_weapon_in_hand_keeps_it_for_the_strike(registry, cfg):
    hero = make_fighter(registry)
    engine = duel(registry, cfg, ScriptedRng(d20=[5, 5, 15]), hero=hero)
    run(engine)
    assert hero.equipped.main_hand == "longsword"


# --- конец боя ---

def test_master_ending_gives_the_trophy_to_the_hero(registry, cfg):
    hero = make_fighter(registry)
    engine = duel(registry, cfg, hero=hero)
    engine.state.ground_items.append(GroundItem(item_id="scimitar", zone_id="hall", cost_cp=0))
    engine.end_combat()
    assert count_item(hero, "scimitar") == 1


def test_trophy_quantity_is_kept(registry, cfg):
    hero = make_fighter(registry)
    engine = duel(registry, cfg, hero=hero)
    engine.state.ground_items.append(
        GroundItem(item_id="scimitar", zone_id="hall", qty=2, cost_cp=0)
    )
    engine.end_combat()
    assert count_item(hero, "scimitar") == 2
