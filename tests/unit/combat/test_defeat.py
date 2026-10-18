# Последствия поражения (шаг 20, ТЗ 5.1): ai_dm.combat.defeat
#   apply_defeat_outcome(state: CombatState, consequences: list[str], params: DefeatParams, *,
#       world, hero, registry, cfg, rng) -> DefeatResult | Rejected
#     consequences -- 1..2 из: capture, rob, left_to_die, scar, exhaustion, debt (таблица 5.1);
#     0, >2 или неизвестный вид -> Rejected(report_tag="invalid-defeat"), ничего не меняется
#     (атомарно: ошибка во втором -- первое тоже не применяется);
#     последствия применяются по порядку; result.status "applied" ("clamped", если брать нечего);
#     result.events -- события (по одному defeat_applied {consequence} на последствие и
#     специальные ниже); флаги auto_flags применяются к world.
#     DefeatParams(lair_location_id=None, rob_items=None, scar_ability=None, scar_skill=None,
#       scar_text="", debt_to=None, debt_text="") -- Pydantic, extra="forbid".
#     capture    -- hero.location_id = группа defeat_group_id .lair_location_id (иначе
#                   params.lair_location_id); снаряжение изъято: inventory пуст, equipped очищен;
#                   событие location_visited {id: <логово>} -> флаг visited:<логово>
#     rob        -- money_cp -= money_cp * cfg.defeat.robbery_gold_percent // 100; плюс rob_items
#                   (None -> rng.randint(1, 2)) самых дорогих предметов КРОМЕ надетого
#                   (inventory.pick_valuables); нечего брать (0 монет и нет ненадетого) -> "clamped"
#     left_to_die-- hp_current = cfg.defeat.left_to_die_hp, unconscious 0_hp снят, спасброски
#                   сброшены; часы: бросок cfg.defeat.left_to_die_hours_dice, clock += часы * 3600
#     scar       -- ровно одно из scar_ability (-1 к sheet.abilities[x]) / scar_skill; в обоих
#                   случаях scar_text добавляется в hero.scars; ни одного или оба -> Rejected
#     exhaustion -- creature.exhaustion + 1 (причина "defeat")
#     debt       -- флаг debt:<hero.id> = кредитор (params.debt_to, иначе лидер defeat_group_id),
#                   у NPC-кредитора цель debt (rules.goals.add_goal) и триггер-спутник
#                   id "goal:debt:<hero.id>" (Ж2; старого "debt_<hero.id>" нет)
import pytest
from combat_kit import ScriptedRng, down_hero, make_engine, make_fighter, mon

from ai_dm.combat.defeat import DefeatParams, apply_defeat_outcome
from ai_dm.config.settings import load_rules_config
from ai_dm.rules.inventory import add_catalog_item, count_item
from ai_dm.rules.results import Rejected
from ai_dm.state.hero import InventoryEntry


def defeated(registry, cfg, money=1235):
    hero = make_fighter(registry)
    engine = make_engine(
        registry, cfg, heroes=[hero], intent="capture",
        monsters=[mon("goblin_1", "goblin_warrior", "hall", named=True),
                  mon("goblin_2", "goblin_warrior", "hall", named=True)],
    )
    hero.money_cp = money
    hero.inventory = [
        InventoryEntry(item_id="longsword", cost_cp=0),
        InventoryEntry(item_id="chain_mail", cost_cp=0),
        InventoryEntry(item_id="shield", cost_cp=0),
    ]
    engine.state.groups["goblins"].lair_location_id = "goblin_den"
    engine.state.defeat_group_id = "goblins"
    engine.state.outcome = "defeat_pending"
    down_hero(engine, "hero", by="goblin_1")
    return engine, hero


def apply(engine, hero, registry, cfg, consequences, params=None, rng=None):
    return apply_defeat_outcome(
        engine.state, consequences, params or DefeatParams(), world=engine.world, hero=hero,
        registry=registry, cfg=cfg, rng=rng or ScriptedRng(),
    )


def snapshot(engine, hero):
    return hero.model_dump_json() + engine.world.model_dump_json() + engine.state.model_dump_json()


# плен

def test_capture_moves_the_hero_to_the_lair(registry, cfg):
    engine, hero = defeated(registry, cfg)
    apply(engine, hero, registry, cfg, ["capture"])
    assert hero.location_id == "goblin_den"


def test_capture_takes_all_gear(registry, cfg):
    engine, hero = defeated(registry, cfg)
    apply(engine, hero, registry, cfg, ["capture"])
    assert hero.inventory == []
    assert hero.equipped.armor is None
    assert hero.equipped.shield is None
    assert hero.equipped.main_hand is None


def test_capture_reports_the_visit(registry, cfg):
    engine, hero = defeated(registry, cfg)
    result = apply(engine, hero, registry, cfg, ["capture"])
    visited = [e for e in result.events if e.type == "location_visited"]
    assert [e.data for e in visited] == [{"id": "goblin_den"}]
    assert engine.world.flags["visited:goblin_den"] is True


def test_capture_uses_the_lair_from_params_when_the_group_has_none(registry, cfg):
    engine, hero = defeated(registry, cfg)
    engine.state.groups["goblins"].lair_location_id = None
    apply(engine, hero, registry, cfg, ["capture"], DefeatParams(lair_location_id="goblin_den"))
    assert hero.location_id == "goblin_den"


# ограбление

def rich_hero(engine, hero):
    add_catalog_item(hero, engine.registry, "potion_of_healing")
    add_catalog_item(hero, engine.registry, "shortbow")


def test_rob_takes_half_of_the_gold_rounding_the_taken_part_down(registry, cfg):
    engine, hero = defeated(registry, cfg, money=1235)
    apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=1))
    assert hero.money_cp == 1235 - 617


def test_rob_percent_comes_from_the_config(registry):
    custom = load_rules_config(toml_text="[defeat]\nrobbery_gold_percent = 25\n")
    engine, hero = defeated(registry, custom, money=1000)
    apply(engine, hero, registry, custom, ["rob"], DefeatParams(rob_items=1))
    assert hero.money_cp == 750


def test_rob_takes_the_most_valuable_unworn_item(registry, cfg):
    engine, hero = defeated(registry, cfg)
    rich_hero(engine, hero)
    apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=1))
    assert count_item(hero, "potion_of_healing") == 0
    assert count_item(hero, "shortbow") == 1


def test_rob_takes_two_items_when_asked(registry, cfg):
    engine, hero = defeated(registry, cfg)
    rich_hero(engine, hero)
    apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=2))
    assert count_item(hero, "potion_of_healing") == 0
    assert count_item(hero, "shortbow") == 0


def test_rob_never_takes_worn_gear(registry, cfg):
    engine, hero = defeated(registry, cfg)
    rich_hero(engine, hero)
    apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=2))
    assert count_item(hero, "longsword") == 1
    assert count_item(hero, "chain_mail") == 1
    assert count_item(hero, "shield") == 1
    assert hero.equipped.main_hand == "longsword"


def test_rob_count_is_rolled_when_not_given(registry, cfg):
    engine, hero = defeated(registry, cfg)
    rich_hero(engine, hero)
    rng = ScriptedRng(d2=[2])
    apply(engine, hero, registry, cfg, ["rob"], rng=rng)
    assert count_item(hero, "potion_of_healing") == 0
    assert count_item(hero, "shortbow") == 0


def test_rob_count_roll_of_one_takes_one_item(registry, cfg):
    engine, hero = defeated(registry, cfg)
    rich_hero(engine, hero)
    apply(engine, hero, registry, cfg, ["rob"], rng=ScriptedRng(d2=[1]))
    assert count_item(hero, "shortbow") == 1


def test_rob_with_empty_pockets_is_clamped(registry, cfg):
    engine, hero = defeated(registry, cfg, money=0)
    before = snapshot(engine, hero)
    result = apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=2))
    assert result.status == "clamped"
    assert snapshot(engine, hero) == before


def test_rob_with_loot_is_applied(registry, cfg):
    engine, hero = defeated(registry, cfg)
    result = apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=1))
    assert result.status == "applied"


# брошен умирать

def test_left_to_die_wakes_the_hero_with_1_hp(registry, cfg):
    engine, hero = defeated(registry, cfg)
    apply(engine, hero, registry, cfg, ["left_to_die"], rng=ScriptedRng(d8=[3]))
    assert hero.creature.hp_current == 1
    assert not [c for c in hero.creature.conditions if c.id == "unconscious"]
    assert hero.creature.death_saves.failures == 0
    assert hero.status == "active"


def test_left_to_die_passes_1d8_hours(registry, cfg):
    engine, hero = defeated(registry, cfg)
    start = engine.world.clock.now_s
    apply(engine, hero, registry, cfg, ["left_to_die"], rng=ScriptedRng(d8=[5]))
    assert engine.world.clock.now_s == start + 5 * 3600


def test_left_to_die_follows_the_config(registry):
    custom = load_rules_config(
        toml_text='[defeat]\nleft_to_die_hp = 2\nleft_to_die_hours_dice = "1d4"\n'
    )
    engine, hero = defeated(registry, custom)
    start = engine.world.clock.now_s
    apply(engine, hero, registry, custom, ["left_to_die"], rng=ScriptedRng(d4=[3]))
    assert hero.creature.hp_current == 2
    assert engine.world.clock.now_s == start + 3 * 3600


# шрам, истощение, долг

def test_scar_on_ability_lowers_it_by_one(registry, cfg):
    engine, hero = defeated(registry, cfg)
    strength = hero.sheet.abilities["str"]
    params = DefeatParams(scar_ability="str", scar_text="Шрам через всё лицо")
    apply(engine, hero, registry, cfg, ["scar"], params)
    assert hero.sheet.abilities["str"] == strength - 1
    assert hero.scars == ["Шрам через всё лицо"]


def test_scar_on_skill_keeps_the_description(registry, cfg):
    engine, hero = defeated(registry, cfg)
    params = DefeatParams(scar_skill="stealth", scar_text="Хромота")
    apply(engine, hero, registry, cfg, ["scar"], params)
    assert hero.scars == ["Хромота"]


def test_scar_without_a_target_is_rejected(registry, cfg):
    engine, hero = defeated(registry, cfg)
    result = apply(engine, hero, registry, cfg, ["scar"], DefeatParams(scar_text="Шрам"))
    assert isinstance(result, Rejected)
    assert result.report_tag == "invalid-defeat"


def test_scar_with_both_targets_is_rejected(registry, cfg):
    engine, hero = defeated(registry, cfg)
    params = DefeatParams(scar_ability="str", scar_skill="stealth", scar_text="Шрам")
    assert isinstance(apply(engine, hero, registry, cfg, ["scar"], params), Rejected)


def test_exhaustion_adds_one_level(registry, cfg):
    engine, hero = defeated(registry, cfg)
    apply(engine, hero, registry, cfg, ["exhaustion"])
    assert hero.creature.exhaustion == 1


def test_debt_sets_a_flag_and_a_trigger_on_the_leader(registry, cfg):
    engine, hero = defeated(registry, cfg)
    apply(engine, hero, registry, cfg, ["debt"], DefeatParams(debt_text="Принести вождю золото"))
    assert engine.world.flags["debt:hero"] == "goblin_1"
    triggers = engine.world.npcs["goblin_1"].opportunity
    assert [t.id for t in triggers] == ["goal:debt:hero"]


def test_debt_creates_debt_goal_with_text_on_the_creditor(registry, cfg):
    engine, hero = defeated(registry, cfg)
    apply(engine, hero, registry, cfg, ["debt"], DefeatParams(debt_text="Принести вождю золото"))
    [goal] = engine.world.npcs["goblin_1"].goals
    assert (goal.kind, goal.target, goal.text, goal.status) == (
        "debt", "hero", "Принести вождю золото", "active",
    )
    assert goal.since_s == engine.world.clock.now_s


def test_debt_goal_has_default_text_with_hero_name(registry, cfg):
    engine, hero = defeated(registry, cfg)
    apply(engine, hero, registry, cfg, ["debt"])
    [goal] = engine.world.npcs["goblin_1"].goals
    assert hero.name in goal.text


def test_debt_does_not_create_the_old_debt_trigger(registry, cfg):
    engine, hero = defeated(registry, cfg)
    apply(engine, hero, registry, cfg, ["debt"])
    ids = [t.id for npc in engine.world.npcs.values() for t in npc.opportunity]
    assert "debt_hero" not in ids


def test_debt_goal_is_only_on_the_creditor(registry, cfg):
    engine, hero = defeated(registry, cfg)
    apply(engine, hero, registry, cfg, ["debt"])
    assert engine.world.npcs["goblin_2"].goals == []
    assert engine.world.npcs["goblin_2"].opportunity == []


def test_debt_to_a_chosen_creditor(registry, cfg):
    engine, hero = defeated(registry, cfg)
    apply(engine, hero, registry, cfg, ["debt"], DefeatParams(debt_to="goblin_2"))
    assert engine.world.flags["debt:hero"] == "goblin_2"
    assert [t.id for t in engine.world.npcs["goblin_2"].opportunity] == ["goal:debt:hero"]


# две последствия, порядок, события

def test_rob_and_left_to_die_both_apply(registry, cfg):
    engine, hero = defeated(registry, cfg, money=1000)
    start = engine.world.clock.now_s
    rng = ScriptedRng(d8=[2])
    apply(engine, hero, registry, cfg, ["rob", "left_to_die"], DefeatParams(rob_items=1), rng)
    assert hero.money_cp == 500
    assert hero.creature.hp_current == 1
    assert engine.world.clock.now_s == start + 2 * 3600


def test_every_consequence_is_reported(registry, cfg):
    engine, hero = defeated(registry, cfg)
    result = apply(
        engine, hero, registry, cfg, ["rob", "left_to_die"], DefeatParams(rob_items=1),
        ScriptedRng(d8=[2]),
    )
    applied = [e.data["consequence"] for e in result.events if e.type == "defeat_applied"]
    assert applied == ["rob", "left_to_die"]


def test_capture_and_exhaustion_combine(registry, cfg):
    engine, hero = defeated(registry, cfg)
    apply(engine, hero, registry, cfg, ["capture", "exhaustion"])
    assert hero.location_id == "goblin_den"
    assert hero.creature.exhaustion == 1


# отказы

@pytest.mark.parametrize("consequences", [[], ["rob", "left_to_die", "debt"], ["torture"]])
def test_bad_consequence_list_is_rejected(registry, cfg, consequences):
    engine, hero = defeated(registry, cfg)
    result = apply(engine, hero, registry, cfg, consequences)
    assert isinstance(result, Rejected)
    assert result.report_tag == "invalid-defeat"


@pytest.mark.parametrize("consequences", [[], ["rob", "left_to_die", "debt"], ["torture"]])
def test_rejection_changes_nothing(registry, cfg, consequences):
    engine, hero = defeated(registry, cfg)
    before = snapshot(engine, hero)
    apply(engine, hero, registry, cfg, consequences)
    assert snapshot(engine, hero) == before


def test_invalid_second_consequence_cancels_the_first(registry, cfg):
    engine, hero = defeated(registry, cfg)
    before = snapshot(engine, hero)
    result = apply(engine, hero, registry, cfg, ["rob", "torture"], DefeatParams(rob_items=1))
    assert isinstance(result, Rejected)
    assert snapshot(engine, hero) == before


def test_params_reject_unknown_fields():
    with pytest.raises(ValueError):
        DefeatParams(bogus=1)
