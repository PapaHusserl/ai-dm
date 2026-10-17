# Отбор оружия: что остаётся у обезоруженного (docs/plan-combat-disarm.md, п. 2, 3, 5).
#   Флаг ActiveEffect(id="disarmed", params={"weapon_id": X}) отключает только действия монстра с
#   этим MonsterAction.weapon_id; естественные атаки (без weapon_id) остаются.
#   Остались без оружейных действий и тип существа в [disarm].unarmed_types (humanoid) --
#   «безоружный удар» (id "unarmed": атака ближнего боя, урон 1 + мод. Силы, без костей).
#   Флаг без params (старый сейв посреди боя) = все оружейные действия отключены.
#   Мультиатака: шаги с отключённым действием пропускаются; не осталось шагов -- варианта нет.
import pytest
from combat_kit import ScriptedRng, hp, make_engine, make_fighter, mon, option_ids

from ai_dm.content.models.monsters import MonsterAction, MultiattackStep
from ai_dm.state.creature import ActiveEffect


def fight(registry, cfg, monster, rng=None):
    return make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=rng,
        monsters=[mon("m1", monster, "hall")],
    )


def take(engine, weapon_id, ref="m1"):
    params = {} if weapon_id is None else {"weapon_id": weapon_id}
    effect = ActiveEffect(id="disarmed", source="hero", kind="flag", params=params)
    engine.part(ref).creature.active_effects.append(effect)


def attack_ids(engine, ref="m1"):
    return [i for i in option_ids(engine, ref) if i.startswith("attack:")]


BITE = MonsterAction(
    name="Укус", kind="melee", attack_bonus=4, damage_dice="1d4", damage_type="piercing"
)


def test_goblin_without_the_scimitar_keeps_only_the_bow(registry, cfg):
    engine = fight(registry, cfg, "goblin_warrior")
    take(engine, "scimitar")
    assert attack_ids(engine) == ["attack:короткий_лук:hero"]


def test_goblin_without_the_bow_keeps_only_the_scimitar(registry, cfg):
    engine = fight(registry, cfg, "goblin_warrior")
    take(engine, "shortbow")
    assert attack_ids(engine) == ["attack:скимитар:hero"]


def test_goblin_without_both_weapons_gets_an_unarmed_strike(registry, cfg):
    # гоблин -- fey, а fey в [disarm].unarmed_types по умолчанию
    engine = fight(registry, cfg, "goblin_warrior")
    take(engine, "scimitar")
    take(engine, "shortbow")
    assert attack_ids(engine) == ["attack:unarmed:hero"]


def test_goblin_with_one_weapon_left_gets_no_unarmed_strike(registry, cfg):
    engine = fight(registry, cfg, "goblin_warrior")
    take(engine, "scimitar")
    assert "attack:unarmed:hero" not in attack_ids(engine)


def test_guard_without_the_spear_gets_an_unarmed_strike(registry, cfg):
    engine = fight(registry, cfg, "guard")
    take(engine, "spear")
    assert attack_ids(engine) == ["attack:unarmed:hero"]


def test_guard_with_the_spear_has_no_unarmed_strike(registry, cfg):
    engine = fight(registry, cfg, "guard")
    assert attack_ids(engine) == ["attack:копьё:hero"]


def test_unarmed_strike_of_a_monster_deals_one_plus_strength(registry, cfg):
    # Сила стражника 13 (+1): урон 2, без костей; 20 на d20 попадает наверняка
    engine = fight(registry, cfg, "guard", ScriptedRng(d20=[20]))
    take(engine, "spear")
    engine.perform("m1", "attack:unarmed:hero")
    assert hp(engine, "hero") == 12 - 2


def test_unarmed_strike_is_melee_only(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)],
        monsters=[mon("m1", "guard", "balcony")],
    )
    take(engine, "spear")
    assert attack_ids(engine) == []


def test_unarmed_types_come_from_the_config(registry, cfg, monkeypatch):
    monkeypatch.setattr(cfg.disarm, "unarmed_types", ["humanoid"])
    engine = fight(registry, cfg, "goblin_warrior")
    take(engine, "scimitar")
    take(engine, "shortbow")
    assert attack_ids(engine) == []


def test_unarmed_strike_bonus_is_strength_plus_the_configured_proficiency(
    registry, cfg, monkeypatch
):
    # Сила гоблина 8 (-1); мастерство 2 -> +1
    monkeypatch.setattr(cfg.disarm, "unarmed_proficiency", 5)
    engine = fight(registry, cfg, "goblin_warrior", ScriptedRng(d20=[15]))
    take(engine, "scimitar")
    take(engine, "shortbow")
    events = engine.perform("m1", "attack:unarmed:hero")
    # -1 + 5 = +4: 15 + 4 = 19 попадает в КД 19; урон 1 - 1 = 0
    assert [e.data["outcome"] for e in events if e.type == "attack"] == ["hit"]


def test_unarmed_strike_bonus_with_the_default_proficiency_misses_the_same_roll(registry, cfg):
    # -1 + 2 = +1: 15 + 1 = 16 < 19
    engine = fight(registry, cfg, "goblin_warrior", ScriptedRng(d20=[15]))
    take(engine, "scimitar")
    take(engine, "shortbow")
    events = engine.perform("m1", "attack:unarmed:hero")
    assert [e.data["outcome"] for e in events if e.type == "attack"] == ["miss"]


def test_unarmed_strike_never_deals_negative_damage(registry, cfg):
    # Сила 8: 1 - 1 = 0
    engine = fight(registry, cfg, "goblin_warrior", ScriptedRng(d20=[20]))
    take(engine, "scimitar")
    take(engine, "shortbow")
    engine.perform("m1", "attack:unarmed:hero")
    assert hp(engine, "hero") == 12


def test_humanoid_is_in_the_default_unarmed_types(cfg):
    assert "humanoid" in cfg.disarm.unarmed_types


def test_natural_attack_stays_when_the_weapon_is_taken(registry, cfg, monkeypatch):
    spear = [a for a in registry.get("monster", "guard").actions if a.weapon_id == "spear"][0]
    monkeypatch.setattr(registry.get("monster", "guard"), "actions", [spear, BITE])
    engine = fight(registry, cfg, "guard")
    take(engine, "spear")
    assert "attack:укус:hero" in attack_ids(engine)


# --- старый флаг без params ---

def test_old_flag_disables_all_weapon_actions(registry, cfg):
    # скимитар и лук отключены, остался безоружный удар (fey в unarmed_types)
    engine = fight(registry, cfg, "goblin_warrior")
    take(engine, None)
    assert attack_ids(engine) == ["attack:unarmed:hero"]


def test_old_flag_keeps_natural_attacks(registry, cfg, monkeypatch):
    scimitar = registry.get("monster", "goblin_warrior").actions[0]
    monkeypatch.setattr(registry.get("monster", "goblin_warrior"), "actions", [scimitar, BITE])
    engine = fight(registry, cfg, "goblin_warrior")
    take(engine, None)
    assert "attack:укус:hero" in attack_ids(engine)
    assert "attack:скимитар:hero" not in attack_ids(engine)


def test_old_flag_on_a_humanoid_gives_the_unarmed_strike(registry, cfg):
    engine = fight(registry, cfg, "guard")
    take(engine, None)
    assert attack_ids(engine) == ["attack:unarmed:hero"]


# --- мультиатака ---

def test_multiattack_is_hidden_when_all_its_steps_are_taken(registry, cfg):
    engine = fight(registry, cfg, "goblin_boss")
    take(engine, "scimitar")
    assert "multiattack" not in option_ids(engine, "m1")


def test_multiattack_stays_when_an_unrelated_weapon_is_taken(registry, cfg):
    engine = fight(registry, cfg, "goblin_boss")
    take(engine, "shortbow")
    assert "multiattack" in option_ids(engine, "m1")


def test_multiattack_skips_the_taken_step(registry, cfg, monkeypatch):
    boss = registry.get("monster", "goblin_boss")
    steps = [MultiattackStep(action="Скимитар", count=1),
             MultiattackStep(action="Короткий лук", count=1)]
    monkeypatch.setattr(boss, "multiattack", steps)
    # лук в одной зоне с врагом -- помеха, два d20; 15 + 4 = 19 попадает в КД 19
    engine = fight(registry, cfg, "goblin_boss", ScriptedRng(d20=[15, 15], d6=[3]))
    take(engine, "scimitar")
    events = engine.perform("m1", "multiattack")
    assert [e.data["weapon"] for e in events if e.type == "attack"] == ["короткий_лук"]


def test_multiattack_keeps_the_remaining_steps_when_the_boss_is_disarmed_of_a_bow(
    registry, cfg
):
    engine = fight(registry, cfg, "goblin_boss", ScriptedRng(d20=[15, 15], d6=[1, 1]))
    take(engine, "shortbow")
    events = engine.perform("m1", "multiattack")
    assert [e.data["weapon"] for e in events if e.type == "attack"] == ["скимитар", "скимитар"]


# --- герой ---

def test_hero_without_a_weapon_in_hand_but_with_one_in_the_pack_keeps_the_rule(registry, cfg):
    # оружие в рюкзаке остаётся доступным (ограничение касается только отобранного)
    hero = make_fighter(registry)
    hero.equipped.main_hand = None
    engine = make_engine(
        registry, cfg, heroes=[hero], monsters=[mon("m1", "goblin_warrior", "hall")]
    )
    assert "attack:longsword:m1" in option_ids(engine, "hero")


@pytest.mark.parametrize("count", [1, 2])
def test_taking_a_monster_weapon_twice_is_harmless(registry, cfg, count):
    engine = fight(registry, cfg, "goblin_warrior")
    for _ in range(count):
        take(engine, "scimitar")
    assert attack_ids(engine) == ["attack:короткий_лук:hero"]
