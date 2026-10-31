# Шаг К2, П2: бой воина (docs/plan-k2.md; combat/actions/fighter.py, features.py, mastery.py).
#   * Всплеск действий (воин 2+ ур., пул action_surge 1): когда действие потрачено, пункт
#     action_surge (free); выбор возвращает действие и тратит заряд; короткий отдых восстанавливает;
#   * Тактический сдвиг (5 ур.): Второе дыхание -> turn.disengaged; Выдающийся атлет (Чемпион):
#     критическое попадание -> turn.disengaged; Улучшенный крит: 19 -- крит;
#   * Рассечение (мастерство cleave, секира): попадание открывает пункт cleave:<другая цель в зоне>
#     (free, раз в ход); урон без модификатора характеристики, отрицательный вычитается
#     (решение 49);
#   * Толчок (мастерство push, боевой молот): попадание отбрасывает цель до Large в соседнюю зону
#     (ниже, если есть), лог «отброшен в зону <id>»; Huge и больше не сдвигаются.
from combat_kit import (
    ScriptedRng,
    creature,
    custom_registry,
    give_weapon,
    hp,
    make_engine,
    make_fighter,
    make_zones,
    mon,
    option_ids,
    part,
    set_hp,
    turn,
)

from ai_dm.rules.derived import attack_parts
from ai_dm.rules.inventory import add_item, count_item, remove_item
from ai_dm.rules.progression import sync_resources
from ai_dm.rules.rests import recover_pools

SURGE = "action_surge"


def fighter_at(registry, level=2, subclass=None, masteries=()):
    hero = make_fighter(registry)
    hero.sheet.primary.level = level
    hero.sheet.primary.subclass_id = subclass
    hero.sheet.weapon_masteries = list(masteries)
    sync_resources(hero, registry)
    return hero


def duel(registry, cfg, hero, rng=None, goblins=1, reg=None, monster="goblin_warrior"):
    monsters = [mon(f"goblin_{i}", monster, "hall") for i in range(1, goblins + 1)]
    engine = make_engine(reg or registry, cfg, heroes=[hero], rng=rng, monsters=monsters)
    for i in range(1, goblins + 1):
        creature(engine, f"goblin_{i}").hp_max = 40
        set_hp(engine, f"goblin_{i}", 40)
    return engine


def attack_outcome(events):
    return [e.data["outcome"] for e in events if e.type == "attack"][0]


def pool(engine, name="action_surge"):
    return engine.heroes["hero"].creature.resources[name]


# --- Всплеск действий ---

def test_no_surge_option_while_the_action_is_free(registry, cfg):
    engine = duel(registry, cfg, fighter_at(registry))
    assert SURGE not in option_ids(engine, "hero")


def test_surge_option_appears_when_the_action_is_spent(registry, cfg):
    engine = duel(registry, cfg, fighter_at(registry))
    turn(engine, "hero").action = False
    assert SURGE in option_ids(engine, "hero")


def test_surge_option_is_free_and_labelled(registry, cfg):
    engine = duel(registry, cfg, fighter_at(registry))
    turn(engine, "hero").action = False
    option = [o for o in engine.available_actions("hero") if o.id == SURGE][0]
    assert (option.cost, option.label) == ("free", "Всплеск действий")


def test_first_level_fighter_has_no_surge(registry, cfg):
    engine = duel(registry, cfg, fighter_at(registry, level=1))
    turn(engine, "hero").action = False
    assert SURGE not in option_ids(engine, "hero")


def test_surge_returns_the_action(registry, cfg):
    engine = duel(registry, cfg, fighter_at(registry))
    turn(engine, "hero").action = False
    engine.perform("hero", SURGE)
    assert turn(engine, "hero").action is True


def test_surge_spends_the_charge(registry, cfg):
    engine = duel(registry, cfg, fighter_at(registry))
    turn(engine, "hero").action = False
    engine.perform("hero", SURGE)
    assert pool(engine).current == 0


def test_surge_option_is_gone_after_use(registry, cfg):
    engine = duel(registry, cfg, fighter_at(registry))
    turn(engine, "hero").action = False
    engine.perform("hero", SURGE)
    turn(engine, "hero").action = False
    assert SURGE not in option_ids(engine, "hero")


def test_surge_is_logged(registry, cfg):
    engine = duel(registry, cfg, fighter_at(registry))
    turn(engine, "hero").action = False
    engine.perform("hero", SURGE)
    assert "Арн: Всплеск действий" in engine.state.log


def test_after_the_surge_the_hero_attacks_again(registry, cfg):
    engine = duel(registry, cfg, fighter_at(registry), ScriptedRng(d20=[15, 15], d8=[2, 2]))
    engine.perform("hero", "attack:longsword:goblin_1")
    engine.perform("hero", SURGE)
    engine.perform("hero", "attack:longsword:goblin_1")
    assert hp(engine, "goblin_1") == 40 - 5 - 5


def test_fighter_5_gets_four_attacks_with_the_surge(registry, cfg):
    # атака (действие потрачено, остаток 1) -> Всплеск -> остаток + две атаки нового действия
    rng = ScriptedRng(d20=[15] * 4, d8=[2] * 4)
    engine = duel(registry, cfg, fighter_at(registry, level=5), rng)
    engine.perform("hero", "attack:longsword:goblin_1")
    engine.perform("hero", SURGE)
    for _ in range(3):
        engine.perform("hero", "attack:longsword:goblin_1")
    assert hp(engine, "goblin_1") == 40 - 4 * 5
    assert "attack:longsword:goblin_1" not in option_ids(engine, "hero")


def test_short_rest_restores_the_surge(registry, cfg):
    engine = duel(registry, cfg, fighter_at(registry))
    turn(engine, "hero").action = False
    engine.perform("hero", SURGE)
    recover_pools(engine.heroes["hero"], registry, "short_rest")
    assert pool(engine).current == 1


# --- Тактический сдвиг, Выдающийся атлет, Улучшенный крит ---

def second_wind(registry, cfg, level):
    engine = duel(registry, cfg, fighter_at(registry, level=level), ScriptedRng(d10=[5]))
    set_hp(engine, "hero", 3)
    engine.perform("hero", "second_wind")
    return engine


def test_tactical_shift_makes_the_second_wind_disengage(registry, cfg):
    assert turn(second_wind(registry, cfg, 5), "hero").disengaged is True


def test_second_wind_before_level_5_does_not_disengage(registry, cfg):
    assert turn(second_wind(registry, cfg, 2), "hero").disengaged is False


def test_tactical_shift_is_logged(registry, cfg):
    engine = second_wind(registry, cfg, 5)
    assert any("Тактический сдвиг" in line for line in engine.state.log)


def champion_blow(registry, cfg, d20, subclass="champion", level=3):
    hero = fighter_at(registry, level=level, subclass=subclass)
    engine = duel(registry, cfg, hero, ScriptedRng(d20=[d20], d8=[2, 2, 2]))
    return engine, engine.perform("hero", "attack:longsword:goblin_1")


def test_champion_crits_on_a_19(registry, cfg):
    _, events = champion_blow(registry, cfg, 19)
    assert attack_outcome(events) == "crit"


def test_fighter_without_a_subclass_does_not_crit_on_a_19(registry, cfg):
    _, events = champion_blow(registry, cfg, 19, subclass=None)
    assert attack_outcome(events) == "hit"


def test_a_crit_makes_the_champion_disengage(registry, cfg):
    engine, _ = champion_blow(registry, cfg, 20)
    assert turn(engine, "hero").disengaged is True


def test_a_plain_hit_does_not_make_the_champion_disengage(registry, cfg):
    engine, _ = champion_blow(registry, cfg, 15)
    assert turn(engine, "hero").disengaged is False


def test_a_crit_without_the_feature_does_not_disengage(registry, cfg):
    engine, _ = champion_blow(registry, cfg, 20, subclass=None)
    assert turn(engine, "hero").disengaged is False


def test_a_champion_miss_does_not_disengage(registry, cfg):
    engine, _ = champion_blow(registry, cfg, 2)
    assert turn(engine, "hero").disengaged is False


# --- Рассечение ---

def cleaver(registry, cfg, rng, strength=None, goblins=2, mastery=True):
    hero = fighter_at(registry, level=1, masteries=["greataxe"] if mastery else [])
    give_weapon(hero, registry, "greataxe")
    if strength is not None:
        hero.sheet.abilities["str"] = strength
    return duel(registry, cfg, hero, rng, goblins=goblins)


def cleave_ids(engine):
    return [o.id for o in engine.available_actions("hero") if o.kind == "cleave"]


def test_no_cleave_option_before_the_attack(registry, cfg):
    assert cleave_ids(cleaver(registry, cfg, ScriptedRng())) == []


def test_a_hit_opens_cleave_on_the_other_goblin(registry, cfg):
    engine = cleaver(registry, cfg, ScriptedRng(d20=[15], d12=[5]))
    engine.perform("hero", "attack:greataxe:goblin_1")
    assert cleave_ids(engine) == ["cleave:goblin_2"]


def test_cleave_option_is_free_and_labelled(registry, cfg):
    engine = cleaver(registry, cfg, ScriptedRng(d20=[15], d12=[5]))
    engine.perform("hero", "attack:greataxe:goblin_1")
    option = [o for o in engine.available_actions("hero") if o.kind == "cleave"][0]
    assert option.cost == "free"
    assert option.label.startswith("Рассечение: секира → ")


def test_a_miss_does_not_open_cleave(registry, cfg):
    engine = cleaver(registry, cfg, ScriptedRng(d20=[2]))
    engine.perform("hero", "attack:greataxe:goblin_1")
    assert cleave_ids(engine) == []


def test_a_lone_target_gives_no_cleave(registry, cfg):
    engine = cleaver(registry, cfg, ScriptedRng(d20=[15], d12=[5]), goblins=1)
    engine.perform("hero", "attack:greataxe:goblin_1")
    assert cleave_ids(engine) == []


def test_cleave_needs_the_mastery(registry, cfg):
    engine = cleaver(registry, cfg, ScriptedRng(d20=[15], d12=[5]), mastery=False)
    engine.perform("hero", "attack:greataxe:goblin_1")
    assert cleave_ids(engine) == []


def test_cleave_damage_has_no_ability_modifier(registry, cfg):
    engine = cleaver(registry, cfg, ScriptedRng(d20=[15, 15], d12=[5, 7]))
    engine.perform("hero", "attack:greataxe:goblin_1")
    engine.perform("hero", "cleave:goblin_2")
    assert (hp(engine, "goblin_1"), hp(engine, "goblin_2")) == (40 - 5 - 3, 40 - 7)


def test_cleave_keeps_a_negative_modifier(registry, cfg):
    # решение 49: Сил 8 (-1) вычитается и в уроне Рассечения
    engine = cleaver(registry, cfg, ScriptedRng(d20=[15, 15], d12=[5, 7]), strength=8)
    engine.perform("hero", "attack:greataxe:goblin_1")
    engine.perform("hero", "cleave:goblin_2")
    assert (hp(engine, "goblin_1"), hp(engine, "goblin_2")) == (40 - 5 + 1, 40 - 7 + 1)


def test_cleave_is_once_per_turn(registry, cfg):
    engine = cleaver(registry, cfg, ScriptedRng(d20=[15, 15], d12=[5, 7]))
    engine.perform("hero", "attack:greataxe:goblin_1")
    engine.perform("hero", "cleave:goblin_2")
    assert cleave_ids(engine) == []


def test_cleave_spends_neither_the_action_nor_the_attacks(registry, cfg):
    engine = cleaver(registry, cfg, ScriptedRng(d20=[15, 15], d12=[5, 7]))
    engine.perform("hero", "attack:greataxe:goblin_1")
    engine.perform("hero", "cleave:goblin_2")
    state = turn(engine, "hero")
    assert (state.action, state.attacks_left) == (False, 0)


def test_cleave_flag_ends_with_the_turn(registry, cfg):
    engine = cleaver(registry, cfg, ScriptedRng(d20=[15], d12=[5]))
    engine.perform("hero", "attack:greataxe:goblin_1")
    engine.expire("end_of_turn", "hero")
    assert cleave_ids(engine) == []


# --- Толчок ---

def pusher(registry, cfg, rng, masteries=("warhammer",), size=None):
    hero = fighter_at(registry, level=1, masteries=list(masteries))
    give_weapon(hero, registry, "warhammer")
    reg = registry
    monster = "goblin_warrior"
    if size is not None:
        reg = custom_registry(registry, big={"size": size})
        monster = "big"
    return duel(registry, cfg, hero, rng, reg=reg, monster=monster)


def test_push_moves_the_target_to_the_neighbour_zone(registry, cfg):
    engine = pusher(registry, cfg, ScriptedRng(d20=[15], d8=[3]))
    engine.perform("hero", "attack:warhammer:goblin_1")
    assert part(engine, "goblin_1").zone_id == "door"


def test_push_prefers_the_lower_zone(registry, cfg):
    engine = pusher(registry, cfg, ScriptedRng(d20=[15], d8=[3], d6=[2]))
    engine.state.zones = make_zones()
    engine.state.zones[2].elevation = -1
    engine.perform("hero", "attack:warhammer:goblin_1")
    assert part(engine, "goblin_1").zone_id == "balcony"


def test_push_is_logged_with_the_zone(registry, cfg):
    engine = pusher(registry, cfg, ScriptedRng(d20=[15], d8=[3]))
    engine.perform("hero", "attack:warhammer:goblin_1")
    assert any("отброшен в зону door" in line for line in engine.state.log)


def test_push_does_not_work_on_a_miss(registry, cfg):
    engine = pusher(registry, cfg, ScriptedRng(d20=[2]))
    engine.perform("hero", "attack:warhammer:goblin_1")
    assert part(engine, "goblin_1").zone_id == "hall"


def test_push_needs_the_mastery(registry, cfg):
    engine = pusher(registry, cfg, ScriptedRng(d20=[15], d8=[3]), masteries=())
    engine.perform("hero", "attack:warhammer:goblin_1")
    assert part(engine, "goblin_1").zone_id == "hall"


def test_push_does_not_move_a_huge_target(registry, cfg):
    engine = pusher(registry, cfg, ScriptedRng(d20=[15], d8=[3]), size="huge")
    engine.perform("hero", "attack:warhammer:goblin_1")
    assert part(engine, "goblin_1").zone_id == "hall"


def test_push_moves_a_large_target(registry, cfg):
    engine = pusher(registry, cfg, ScriptedRng(d20=[15], d8=[3]), size="large")
    engine.perform("hero", "attack:warhammer:goblin_1")
    assert part(engine, "goblin_1").zone_id == "door"


# --- огнестрел (решения 31, 33) ---

MUSKET = "attack:musket:goblin_1"


def shooter(registry, cfg, rng, level=5, bullets=10, feats=(), weapon="musket"):
    hero = fighter_at(registry, level=level)
    hero.sheet.feats += list(feats)
    give_weapon(hero, registry, weapon)
    remove_item(hero, "firearm_bullets", count_item(hero, "firearm_bullets"))
    if bullets:
        add_item(hero, "firearm_bullets", bullets, cost_cp=0)
    engine = make_engine(
        registry, cfg, heroes=[(hero, "door")], rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    set_hp(engine, "goblin_1", 100)
    return engine


def bullets(engine):
    return count_item(engine.heroes["hero"], "firearm_bullets")


def test_fighter_5_fires_two_musket_shots_in_one_action(registry, cfg):
    engine = shooter(registry, cfg, ScriptedRng(d20=[15, 15], d12=[4, 4]))
    engine.perform("hero", MUSKET)
    assert turn(engine, "hero").attacks_left == 1
    engine.perform("hero", MUSKET)
    assert (turn(engine, "hero").attacks_left, turn(engine, "hero").action) == (0, False)


def test_two_musket_shots_spend_two_bullets(registry, cfg):
    engine = shooter(registry, cfg, ScriptedRng(d20=[15, 15], d12=[4, 4]))
    engine.perform("hero", MUSKET)
    engine.perform("hero", MUSKET)
    assert bullets(engine) == 8


def test_musket_hit_deals_its_die_and_the_dexterity(registry, cfg):
    engine = shooter(registry, cfg, ScriptedRng(d20=[15], d12=[9]))
    engine.perform("hero", MUSKET)
    # 1d12 (9) + Лов 1
    assert hp(engine, "goblin_1") == 100 - 10


def test_archery_adds_two_to_the_musket_attack(registry, cfg):
    # Лов 1 + мастерство 3 (5 ур.): d20 10 = 14 -- промах по КД 15; со стилем +2 -- 16 попадает
    plain = shooter(registry, cfg, ScriptedRng(d20=[10], d12=[4]))
    plain.perform("hero", MUSKET)
    styled = shooter(registry, cfg, ScriptedRng(d20=[10], d12=[4]), feats=["archery"])
    styled.perform("hero", MUSKET)
    assert (hp(plain, "goblin_1"), hp(styled, "goblin_1")) == (100, 100 - 5)


def test_pistol_without_bullets_is_not_offered(registry, cfg):
    engine = shooter(registry, cfg, ScriptedRng(), bullets=0, weapon="pistol")
    assert "attack:pistol:goblin_1" not in option_ids(engine, "hero")


def test_pistol_with_bullets_is_offered(registry, cfg):
    engine = shooter(registry, cfg, ScriptedRng(), bullets=5, weapon="pistol")
    assert "attack:pistol:goblin_1" in option_ids(engine, "hero")


def rogue_pistol_engine(registry, cfg, rng):
    # плут без владения огнестрелом: класс подменён у стенда воина, Лов +1
    engine = shooter(registry, cfg, rng, weapon="pistol")
    engine.heroes["hero"].sheet.classes[0].class_id = "rogue"
    return engine


def test_rogue_pistol_attack_has_no_proficiency_part(registry, cfg):
    engine = rogue_pistol_engine(registry, cfg, ScriptedRng())
    parts = attack_parts(engine.heroes["hero"], registry, "pistol")
    assert [name for name, _ in parts] == ["Лов"]


def test_rogue_misses_with_a_pistol_where_a_fighter_would_hit(registry, cfg):
    # d20 13 + Лов 1 = 14 < КД 15 (воин с мастерством +2 попал бы)
    engine = rogue_pistol_engine(registry, cfg, ScriptedRng(d20=[13]))
    engine.perform("hero", "attack:pistol:goblin_1")
    assert hp(engine, "goblin_1") == 100


def test_fighter_hits_with_a_pistol_on_the_same_roll(registry, cfg):
    engine = shooter(registry, cfg, ScriptedRng(d20=[13], d10=[5]), weapon="pistol")
    engine.perform("hero", "attack:pistol:goblin_1")
    assert hp(engine, "goblin_1") < 100
