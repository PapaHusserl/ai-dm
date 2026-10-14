# Отбор оружия после боя и пересечения с «Переговорами» (docs/COMBAT-DISARM-PLAN.md, п. 5, 7).
#   conclude (бой окончен победой героев -- victory, враги бежали/сдались):
#     * предметы на земле: «свои» (owner_ref -- живой герой) -- владельцу, остальные (выбитые
#       у врагов) -- в инвентарь первого героя, не мёртвого; ground_items пуст;
#     * флаги "disarmed" у участников сняты;
#     * выхваченное в бою оружие уже в инвентаре -- остаётся.
#   Поражение героев (defeat_pending, hero_dying, hero_dead, fled): предметы героев на земле
#     теряются (в лог -- «остался на поле боя»), у героев не появляются, ground_items пуст.
#   Переговоры: сдавшийся враг роняет оружейные действия на землю (disarmed + GroundItem с
#     owner_ref = он); цель с флагом disarmed -- СЛ переговоров ниже на [parley].disarmed_bonus (2).
from combat_kit import (
    ScriptedRng,
    creature,
    down_hero,
    make_engine,
    make_fighter,
    mon,
    set_hp,
)

from ai_dm.combat.actions.parley import parley_dc
from ai_dm.combat.end import check_end
from ai_dm.rules.inventory import count_item, remove_item
from ai_dm.state.combat import GroundItem
from ai_dm.state.creature import ActiveEffect


def duel(registry, cfg, rng=None, goblins=1, hero=None, **kwargs):
    monsters = [mon(f"goblin_{i}", "goblin_warrior", "hall") for i in range(1, goblins + 1)]
    return make_engine(
        registry, cfg, heroes=[hero or make_fighter(registry)], rng=rng, monsters=monsters,
        **kwargs,
    )


def take(engine, weapon_id, ref="goblin_1"):
    creature(engine, ref).active_effects.append(
        ActiveEffect(id="disarmed", source="hero", kind="flag", params={"weapon_id": weapon_id})
    )


def drop(engine, item_id, owner=None, zone="hall"):
    engine.state.ground_items.append(
        GroundItem(item_id=item_id, zone_id=zone, owner_ref=owner, cost_cp=0)
    )


def finish_by_a_blow(registry, cfg, **kwargs):
    # у гоблина 1 HP, единственный удар героя убивает
    engine = duel(registry, cfg, ScriptedRng(d20=[15], d8=[4]), **kwargs)
    set_hp(engine, "goblin_1", 1)
    return engine


def disarmed_flags(engine, ref):
    return [e for e in creature(engine, ref).active_effects if e.id == "disarmed"]


def without_weapons(registry):
    hero = make_fighter(registry)
    for entry in list(hero.inventory):
        if registry.has("weapon", entry.item_id):
            remove_item(hero, entry.item_id, entry.qty)
    return hero


# --- победа ---

def test_victory_gives_the_trophy_to_the_hero(registry, cfg):
    hero = make_fighter(registry)
    engine = finish_by_a_blow(registry, cfg, hero=hero)
    take(engine, "scimitar")
    drop(engine, "scimitar", owner="goblin_1")
    engine.perform("hero", "attack:longsword:goblin_1")
    assert engine.state.outcome == "victory"
    assert count_item(hero, "scimitar") == 1


def test_victory_empties_the_ground(registry, cfg):
    engine = finish_by_a_blow(registry, cfg)
    drop(engine, "scimitar", owner="goblin_1")
    engine.perform("hero", "attack:longsword:goblin_1")
    assert engine.state.ground_items == []


def test_victory_logs_who_gets_the_trophy(registry, cfg):
    engine = finish_by_a_blow(registry, cfg)
    drop(engine, "scimitar", owner="goblin_1")
    engine.perform("hero", "attack:longsword:goblin_1")
    assert any("скимитар: достаётся Арн" in line for line in engine.state.log)


def test_victory_returns_the_own_weapon_to_its_owner(registry, cfg):
    first = make_fighter(registry, "h1")
    second = make_fighter(registry, "h2")
    engine = make_engine(
        registry, cfg, heroes=[first, second], rng=ScriptedRng(d20=[15], d8=[4]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    set_hp(engine, "goblin_1", 1)
    before = count_item(second, "longsword")
    drop(engine, "longsword", owner="h2")
    engine.perform("h1", "attack:longsword:goblin_1")
    assert count_item(second, "longsword") == before + 1
    assert count_item(first, "longsword") == 1


def test_victory_trophy_of_an_enemy_goes_to_the_first_living_hero(registry, cfg):
    first = make_fighter(registry, "h1")
    second = make_fighter(registry, "h2")
    engine = make_engine(
        registry, cfg, heroes=[first, second], rng=ScriptedRng(d20=[15], d8=[4]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    set_hp(engine, "goblin_1", 1)
    first.status = "dead"
    drop(engine, "scimitar", owner="goblin_1")
    engine.perform("h2", "attack:longsword:goblin_1")
    assert (count_item(first, "scimitar"), count_item(second, "scimitar")) == (0, 1)


def test_victory_clears_the_disarmed_flags_of_the_survivors(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[19, 19]))
    take(engine, "scimitar")
    drop(engine, "scimitar", owner="goblin_1")
    engine.parley("hero", skill="intimidation", outcome="flee", target="goblin_1")
    assert engine.state.outcome == "victory"
    assert disarmed_flags(engine, "goblin_1") == []
    assert engine.state.ground_items == []


def test_trophy_after_enemies_fled_goes_to_the_hero(registry, cfg):
    hero = make_fighter(registry)
    engine = duel(registry, cfg, ScriptedRng(d20=[19, 19]), hero=hero)
    take(engine, "scimitar")
    drop(engine, "scimitar", owner="goblin_1")
    engine.parley("hero", skill="intimidation", outcome="flee", target="goblin_1")
    assert count_item(hero, "scimitar") == 1


def test_weapon_grabbed_during_the_fight_stays_in_the_inventory(registry, cfg):
    hero = without_weapons(registry)
    # проверка гоблина (помеха: два d20), удар героя безоружным; затем скимитаром 15 + 5
    engine = duel(registry, cfg, ScriptedRng(d20=[5, 5, 15, 15], d6=[3]), hero=hero)
    set_hp(engine, "goblin_1", 1)
    engine.perform("hero", "disarm:goblin_1:scimitar")
    assert hero.equipped.main_hand == "scimitar"
    engine.state.participants[0].turn.action = True
    engine.perform("hero", "attack:scimitar:goblin_1")
    assert engine.state.outcome == "victory"
    assert count_item(hero, "scimitar") == 1


def test_fight_without_ground_items_does_not_touch_the_inventory(registry, cfg):
    hero = make_fighter(registry)
    engine = finish_by_a_blow(registry, cfg, hero=hero)
    before = [(e.item_id, e.qty) for e in hero.inventory]
    engine.perform("hero", "attack:longsword:goblin_1")
    assert [(e.item_id, e.qty) for e in hero.inventory] == before


# --- поражение ---

def lost_fight(registry, cfg):
    hero = without_weapons(registry)
    engine = duel(registry, cfg, hero=hero, intent="capture")
    engine.state.defeat_group_id = "goblins"
    return engine, hero


def test_defeat_loses_the_weapon_left_on_the_ground(registry, cfg):
    engine, hero = lost_fight(registry, cfg)
    drop(engine, "longsword", owner="hero")
    down_hero(engine, "hero", by="goblin_1")
    check_end(engine)
    assert engine.state.outcome == "defeat_pending"
    assert count_item(hero, "longsword") == 0


def test_defeat_empties_the_ground(registry, cfg):
    engine, _ = lost_fight(registry, cfg)
    drop(engine, "longsword", owner="hero")
    down_hero(engine, "hero", by="goblin_1")
    check_end(engine)
    assert engine.state.ground_items == []


def test_defeat_logs_that_the_weapon_stayed_on_the_field(registry, cfg):
    engine, _ = lost_fight(registry, cfg)
    drop(engine, "longsword", owner="hero")
    down_hero(engine, "hero", by="goblin_1")
    check_end(engine)
    assert any("длинный меч (Арн) остался на поле боя" in line for line in engine.state.log)


def test_defeat_does_not_log_the_enemy_weapons(registry, cfg):
    engine, _ = lost_fight(registry, cfg)
    drop(engine, "scimitar", owner="goblin_1")
    down_hero(engine, "hero", by="goblin_1")
    check_end(engine)
    assert not any("остался на поле боя" in line for line in engine.state.log)


def test_defeat_does_not_give_the_enemy_weapons_to_the_hero(registry, cfg):
    engine, hero = lost_fight(registry, cfg)
    drop(engine, "scimitar", owner="goblin_1")
    down_hero(engine, "hero", by="goblin_1")
    check_end(engine)
    assert count_item(hero, "scimitar") == 0


def test_defeat_clears_the_disarmed_flags(registry, cfg):
    engine, _ = lost_fight(registry, cfg)
    take(engine, "scimitar")
    down_hero(engine, "hero", by="goblin_1")
    check_end(engine)
    assert disarmed_flags(engine, "goblin_1") == []


def test_ground_items_stay_while_the_fight_goes_on(registry, cfg):
    engine = duel(registry, cfg)
    drop(engine, "scimitar", owner="goblin_1")
    check_end(engine)
    assert len(engine.state.ground_items) == 1


# --- переговоры ---

def dc_before_and_after(registry, cfg, flagged):
    engine = duel(registry, cfg, goblins=2)
    base = parley_dc(engine, "hero", "goblin_1", "persuasion", "surrender")[0]
    for weapon in flagged:
        take(engine, weapon)
    return base, parley_dc(engine, "hero", "goblin_1", "persuasion", "surrender")[0]


def test_disarmed_target_is_easier_to_persuade_by_two(registry, cfg):
    base, now = dc_before_and_after(registry, cfg, ["scimitar", "shortbow"])
    assert now == base - 2


def test_one_taken_weapon_is_enough_for_the_discount(registry, cfg):
    base, now = dc_before_and_after(registry, cfg, ["scimitar"])
    assert now == base - 2


def test_two_taken_weapons_give_the_discount_once(registry, cfg):
    base, now = dc_before_and_after(registry, cfg, ["scimitar", "shortbow"])
    assert base - now == 2


def test_parley_dc_bonus_comes_from_the_config(registry, cfg, monkeypatch):
    monkeypatch.setattr(cfg.parley, "disarmed_bonus", 4)
    base, now = dc_before_and_after(registry, cfg, ["scimitar"])
    assert now == base - 4


def test_armed_target_has_no_disarm_discount(registry, cfg):
    base, now = dc_before_and_after(registry, cfg, [])
    assert now == base


def test_disarmed_discount_is_named_in_the_dc_parts(registry, cfg):
    engine = duel(registry, cfg, goblins=2)
    take(engine, "scimitar")
    parts = parley_dc(engine, "hero", "goblin_1", "persuasion", "surrender")[2]
    assert ("обезоружен", -2) in parts


def test_other_goblin_keeps_its_dc(registry, cfg):
    engine = duel(registry, cfg, goblins=2)
    before = parley_dc(engine, "hero", "goblin_2", "persuasion", "surrender")[0]
    take(engine, "scimitar")
    assert parley_dc(engine, "hero", "goblin_2", "persuasion", "surrender")[0] == before


def test_surrendered_enemy_drops_its_weapons(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[19, 19]), goblins=2)
    engine.parley("hero", skill="intimidation", outcome="surrender", target="goblin_1")
    dropped = sorted((g.item_id, g.zone_id, g.owner_ref) for g in engine.state.ground_items)
    assert dropped == [("scimitar", "hall", "goblin_1"), ("shortbow", "hall", "goblin_1")]


def test_surrendered_enemy_is_marked_as_disarmed_of_each_weapon(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[19, 19]), goblins=2)
    engine.parley("hero", skill="intimidation", outcome="surrender", target="goblin_1")
    taken = sorted(e.params["weapon_id"] for e in disarmed_flags(engine, "goblin_1"))
    assert taken == ["scimitar", "shortbow"]


def test_surrender_is_logged_with_the_weapons(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[19, 19]), goblins=2)
    engine.parley("hero", skill="intimidation", outcome="surrender", target="goblin_1")
    assert any("бросает оружие: скимитар, короткий лук" in line for line in engine.state.log)


def test_surrender_does_not_disarm_the_other_goblin(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[19, 19]), goblins=2)
    engine.parley("hero", skill="intimidation", outcome="surrender", target="goblin_1")
    assert disarmed_flags(engine, "goblin_2") == []


def test_flee_by_parley_does_not_drop_weapons(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[19, 19]), goblins=2)
    engine.parley("hero", skill="intimidation", outcome="flee", target="goblin_1")
    assert engine.state.ground_items == []


def test_weapon_dropped_by_a_surrender_goes_to_the_hero_after_the_fight(registry, cfg):
    hero = make_fighter(registry)
    engine = duel(registry, cfg, ScriptedRng(d20=[19, 19]), hero=hero)
    bows = count_item(hero, "shortbow")
    engine.parley("hero", skill="intimidation", outcome="surrender", target="goblin_1")
    assert engine.state.outcome == "victory"
    assert count_item(hero, "scimitar") == 1
    assert count_item(hero, "shortbow") == bows + 1


def test_surrender_of_an_already_disarmed_enemy_drops_only_the_rest(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[19, 19]), goblins=2)
    take(engine, "scimitar")
    drop(engine, "scimitar", owner="goblin_1")
    engine.parley("hero", skill="intimidation", outcome="surrender", target="goblin_1")
    assert sorted(g.item_id for g in engine.state.ground_items) == ["scimitar", "shortbow"]


# --- К7х: выбитое возвращается героям вместе с ценой, качеством и числом ---

def test_ground_stack_reaches_the_hero_with_price_quality_and_quantity(registry, cfg):
    from ai_dm.combat.end import settle_ground

    hero = without_weapons(registry)
    engine = duel(registry, cfg, hero=hero)
    engine.state.ground_items.append(
        GroundItem(item_id="scimitar", zone_id="hall", owner_ref="hero", cost_cp=250,
                   quality="junk", qty=2)
    )
    engine.state.outcome = "victory"
    settle_ground(engine)
    entry = [e for e in hero.inventory if e.item_id == "scimitar"][0]
    assert (entry.qty, entry.cost_cp, entry.quality) == (2, 250, "junk")
