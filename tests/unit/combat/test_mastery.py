# Мастерство оружия (шаг 17, TZ 6, ARCHITECTURE «Мастерство оружия»): Graze, Sap, Vex, Topple.
#   Срабатывает только если id оружия в hero.sheet.weapon_masteries (у героя) и оружие имеет
#   это mastery (Weapon.mastery). Nick и Slow -- данные без механики: атака с таким оружием
#   работает как обычная, эффектов не добавляет.
#   graze  -- при ПРОМАХЕ цель теряет урон, равный модификатору характеристики атаки (без кубиков)
#   sap    -- при попадании на цель ActiveEffect(id="sap", kind="modifier",
#             params={"target": "attack_roll", "mode": "disadvantage", "consume": True},
#             expires=Expiry(kind="start_of_turn", owner=<атакующий>)): её следующая атака с помехой
#   vex    -- при попадании, нанёсшем урон, на атакующего ActiveEffect(id="vex",
#             params={"target": "attack_roll", "mode": "advantage", "against": <цель>,
#             "consume": True}): следующая атака по этой цели с преимуществом. Срок (ревью
#             партии 5, п. 5; как выразить его через Expiry, решает кабан -- тесты проверяют
#             поведение через step()): попал В СВОЙ ХОД -- до конца его СЛЕДУЮЩЕГО хода (атака в
#             следующем ходу с преимуществом, после конца того хода эффекта нет); попал ВНЕ своего
#             хода (провоцированная атака в ход врага) -- до конца его БЛИЖАЙШЕГО хода
#   topple -- при попадании цель: спасбросок ТЕЛ СЛ 8 + мод. хар-ки атаки + мастерство;
#             провал -- prone
#             Сбитый (prone, source != "0_hp") в начале СВОЕГО хода встаёт (состояние снято), а
#             оставшееся перемещение хода = 0 (встать -- половина скорости = всё перемещение в
#             зонах); prone с source "0_hp" (лежащий без сознания) не снимается.
#   Порядок бросков: атака, затем (топл) спасбросок цели.
from combat_kit import (
    ScriptedRng,
    creature,
    down_hero,
    give_weapon,
    hp,
    make_engine,
    make_fighter,
    mon,
    option_ids,
    part,
    turn,
)

from ai_dm.combat.controllers import ScriptedController
from ai_dm.state.creature import AppliedCondition


def mastery_duel(registry, cfg, rng, weapon, masteries=None, goblin_hp=None, goblin_zone="hall"):
    hero = make_fighter(registry)
    give_weapon(hero, registry, weapon)
    hero.sheet.weapon_masteries = [weapon] if masteries is None else masteries
    engine = make_engine(
        registry, cfg, heroes=[hero], rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", goblin_zone)],
    )
    if goblin_hp is not None:
        creature(engine, "goblin_1").hp_current = goblin_hp
        creature(engine, "goblin_1").hp_max = goblin_hp
    return engine


def effect_ids(engine, ref):
    # расход боеприпасов (ammo_spent) -- не эффект мастерства
    return [e.id for e in creature(engine, ref).active_effects if e.id != "ammo_spent"]


# Graze: двуручный меч (СИЛ +3)

def test_graze_damages_on_a_miss(registry, cfg):
    engine = mastery_duel(registry, cfg, ScriptedRng(d20=[1]), "greatsword")
    engine.perform("hero", "attack:greatsword:goblin_1")
    assert hp(engine, "goblin_1") == 7


def test_graze_rolls_no_dice(registry, cfg):
    rng = ScriptedRng(d20=[1])
    engine = mastery_duel(registry, cfg, rng, "greatsword")
    engine.perform("hero", "attack:greatsword:goblin_1")
    assert rng.calls == ["d20"]


def test_graze_does_nothing_on_a_hit(registry, cfg):
    # 2d6 + 3 = 4 + 3 + 3 = 10 -- ровно урон попадания, без добавки
    engine = mastery_duel(
        registry, cfg, ScriptedRng(d20=[15], d6=[4, 3]), "greatsword", goblin_hp=30
    )
    engine.perform("hero", "attack:greatsword:goblin_1")
    assert hp(engine, "goblin_1") == 30 - 10


def test_graze_needs_the_mastery_in_the_sheet(registry, cfg):
    engine = mastery_duel(registry, cfg, ScriptedRng(d20=[1]), "greatsword", masteries=[])
    engine.perform("hero", "attack:greatsword:goblin_1")
    assert hp(engine, "goblin_1") == 10


# Sap: длинный меч

def test_sap_puts_an_effect_on_the_target(registry, cfg):
    engine = mastery_duel(registry, cfg, ScriptedRng(d20=[15], d8=[1]), "longsword")
    engine.perform("hero", "attack:longsword:goblin_1")
    assert effect_ids(engine, "goblin_1") == ["sap"]


def test_sap_lasts_until_the_attacker_next_turn(registry, cfg):
    engine = mastery_duel(registry, cfg, ScriptedRng(d20=[15], d8=[1]), "longsword")
    engine.perform("hero", "attack:longsword:goblin_1")
    expires = creature(engine, "goblin_1").active_effects[0].expires
    assert (expires.kind, expires.owner) == ("start_of_turn", "hero")


def test_sapped_creature_attacks_with_disadvantage(registry, cfg):
    # помеха: берётся меньшее (3 + 4 = 7 < КД 19)
    engine = mastery_duel(registry, cfg, ScriptedRng(d20=[15, 18, 3], d8=[1]), "longsword")
    engine.perform("hero", "attack:longsword:goblin_1")
    engine.perform("goblin_1", "attack:скимитар:hero")
    assert hp(engine, "hero") == 12


def test_sap_is_spent_by_the_next_attack(registry, cfg):
    engine = mastery_duel(
        registry, cfg, ScriptedRng(d20=[15, 18, 3], d8=[1]), "longsword"
    )
    engine.perform("hero", "attack:longsword:goblin_1")
    engine.perform("goblin_1", "attack:скимитар:hero")
    assert effect_ids(engine, "goblin_1") == []


def test_no_sap_on_a_miss(registry, cfg):
    engine = mastery_duel(registry, cfg, ScriptedRng(d20=[2]), "longsword")
    engine.perform("hero", "attack:longsword:goblin_1")
    assert effect_ids(engine, "goblin_1") == []


def test_no_sap_without_the_mastery(registry, cfg):
    engine = mastery_duel(
        registry, cfg, ScriptedRng(d20=[15], d8=[1]), "longsword", masteries=[]
    )
    engine.perform("hero", "attack:longsword:goblin_1")
    assert effect_ids(engine, "goblin_1") == []


# Vex: короткий лук (цель в соседней зоне, чтобы не было помехи от врага рядом)

def vex_duel(registry, cfg, rng, goblin_hp=None):
    return mastery_duel(
        registry, cfg, rng, "shortbow", goblin_hp=goblin_hp, goblin_zone="balcony"
    )


def test_vex_gives_the_attacker_an_effect_against_the_target(registry, cfg):
    engine = vex_duel(registry, cfg, ScriptedRng(d20=[15], d6=[1]))
    engine.perform("hero", "attack:shortbow:goblin_1")
    effects = [e for e in creature(engine, "hero").active_effects if e.id != "ammo_spent"]
    assert [e.id for e in effects] == ["vex"]
    assert effects[0].params["against"] == "goblin_1"


def test_vexed_next_attack_has_advantage(registry, cfg):
    # второй выстрел: два d20, берётся 17; сам по себе 3 + 3 = 6 был бы промахом
    engine = vex_duel(registry, cfg, ScriptedRng(d20=[15, 3, 17], d6=[1, 1]), goblin_hp=30)
    engine.perform("hero", "attack:shortbow:goblin_1")
    engine.state.participants[0].turn.action = True  # следующий ход героя
    engine.perform("hero", "attack:shortbow:goblin_1")
    assert hp(engine, "goblin_1") == 30 - 2 - 2


def test_vex_is_spent_by_the_next_attack(registry, cfg):
    # второй выстрел -- промах (2 и 1), нового vex нет, старый потрачен
    engine = vex_duel(registry, cfg, ScriptedRng(d20=[15, 2, 1], d6=[1]), goblin_hp=30)
    engine.perform("hero", "attack:shortbow:goblin_1")
    engine.state.participants[0].turn.action = True  # следующий ход героя
    engine.perform("hero", "attack:shortbow:goblin_1")
    assert effect_ids(engine, "hero") == []


def test_no_vex_on_a_miss(registry, cfg):
    engine = vex_duel(registry, cfg, ScriptedRng(d20=[2]))
    engine.perform("hero", "attack:shortbow:goblin_1")
    assert effect_ids(engine, "hero") == []


# Topple: боевой посох (СИЛ +3, мастерство +2 -> СЛ 13)

def test_topple_knocks_down_on_a_failed_save(registry, cfg):
    # атака 15 попадает; спасбросок ТЕЛ гоблина +0: 12 < 13
    engine = mastery_duel(registry, cfg, ScriptedRng(d20=[15, 12], d6=[1]), "quarterstaff")
    engine.perform("hero", "attack:quarterstaff:goblin_1")
    assert [c.id for c in creature(engine, "goblin_1").conditions] == ["prone"]


def test_topple_does_nothing_on_a_passed_save(registry, cfg):
    engine = mastery_duel(registry, cfg, ScriptedRng(d20=[15, 13], d6=[1]), "quarterstaff")
    engine.perform("hero", "attack:quarterstaff:goblin_1")
    assert creature(engine, "goblin_1").conditions == []


def test_no_topple_save_on_a_miss(registry, cfg):
    rng = ScriptedRng(d20=[2])
    engine = mastery_duel(registry, cfg, rng, "quarterstaff")
    engine.perform("hero", "attack:quarterstaff:goblin_1")
    assert rng.calls == ["d20"]


def test_topple_needs_the_mastery(registry, cfg):
    rng = ScriptedRng(d20=[15], d6=[1])
    engine = mastery_duel(registry, cfg, rng, "quarterstaff", masteries=[])
    engine.perform("hero", "attack:quarterstaff:goblin_1")
    assert creature(engine, "goblin_1").conditions == []


# Nick и Slow: данные без механики

def test_nick_weapon_attacks_normally(registry, cfg):
    # кинжал: финесс, СИЛ +3 / ЛОВ +1 -> +3 + 2; 1d4 + 3
    engine = mastery_duel(registry, cfg, ScriptedRng(d20=[10], d4=[2]), "dagger")
    engine.perform("hero", "attack:dagger:goblin_1")
    assert hp(engine, "goblin_1") == 10 - 5
    assert effect_ids(engine, "goblin_1") == []
    assert effect_ids(engine, "hero") == []


def test_slow_weapon_attacks_normally(registry, cfg):
    # лёгкий арбалет: +3 (ЛОВ 1 + мастерство 2); 1d8 + 1
    engine = mastery_duel(
        registry, cfg, ScriptedRng(d20=[12], d8=[4]), "light_crossbow", goblin_zone="balcony"
    )
    engine.perform("hero", "attack:light_crossbow:goblin_1")
    assert hp(engine, "goblin_1") == 10 - 5
    assert effect_ids(engine, "goblin_1") == []


def test_nick_and_slow_do_not_add_conditions(registry, cfg):
    engine = mastery_duel(registry, cfg, ScriptedRng(d20=[10], d4=[2]), "dagger")
    engine.perform("hero", "attack:dagger:goblin_1")
    assert creature(engine, "goblin_1").conditions == []


# Vex по SRD: срок эффекта (ревью партии 5, п. 5). Ходы: раунд 1 -- hero, goblin_1; и так далее.

def vex_rounds(registry, cfg, rng, hero_script, goblin_script=()):
    hero = make_fighter(registry)
    give_weapon(hero, registry, "shortbow")
    hero.sheet.weapon_masteries = ["shortbow"]
    controllers = {
        "hero": ScriptedController(hero_script), "goblin_1": ScriptedController(goblin_script),
    }
    engine = make_engine(
        registry, cfg, heroes=[hero], rng=rng, controllers=controllers,
        monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    creature(engine, "goblin_1").hp_current = 30
    creature(engine, "goblin_1").hp_max = 30
    return engine


def test_vex_from_own_turn_survives_the_enemy_turn(registry, cfg):
    engine = vex_rounds(registry, cfg, ScriptedRng(d20=[15], d6=[1]), ["attack:shortbow:goblin_1"])
    engine.step()
    engine.step()
    assert effect_ids(engine, "hero") == ["vex"]


def test_vex_from_own_turn_gives_advantage_in_the_next_turn(registry, cfg):
    # раунд 2: два d20 (3 и 17), берётся 17 -- попадание; по одному 3 + 3 = 6 был бы промах
    rng = ScriptedRng(d20=[15, 3, 17], d6=[1, 1])
    engine = vex_rounds(
        registry, cfg, rng, ["attack:shortbow:goblin_1", "end_turn", "attack:shortbow:goblin_1"]
    )
    for _ in range(3):
        engine.step()
    assert hp(engine, "goblin_1") == 30 - 2 - 2
    assert rng.left("d20") == 0


def test_vex_from_own_turn_ends_with_the_next_turn(registry, cfg):
    # в раунде 2 герой не атакует; в раунде 3 атака обычная: один d20 (3 -- промах)
    rng = ScriptedRng(d20=[15, 3], d6=[1])
    engine = vex_rounds(
        registry, cfg, rng,
        ["attack:shortbow:goblin_1", "end_turn", "end_turn", "attack:shortbow:goblin_1"],
    )
    for _ in range(3):
        engine.step()
    assert effect_ids(engine, "hero") == []
    engine.step()
    engine.step()
    assert hp(engine, "goblin_1") == 30 - 2
    assert rng.left("d20") == 0


def provoked_vex(registry, cfg, rng, hero_script):
    # герой с коротким мечом (Vex) и гоблин в зале; гоблин в свой ход уходит -> атака героя
    # по возможности (провоцированная)
    hero = make_fighter(registry)
    give_weapon(hero, registry, "shortsword")
    hero.sheet.weapon_masteries = ["shortsword"]
    controllers = {
        "hero": ScriptedController(hero_script),
        "goblin_1": ScriptedController(["move:balcony"]),
    }
    engine = make_engine(
        registry, cfg, heroes=[hero], rng=rng, controllers=controllers,
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    creature(engine, "goblin_1").hp_current = 30
    creature(engine, "goblin_1").hp_max = 30
    return engine


def test_provoked_attack_gives_vex(registry, cfg):
    engine = provoked_vex(registry, cfg, ScriptedRng(d20=[15], d6=[1]), [])
    engine.step()
    engine.step()
    assert part(engine, "goblin_1").zone_id == "balcony"
    assert effect_ids(engine, "hero") == ["vex"]


def test_provoked_vex_works_in_the_nearest_own_turn(registry, cfg):
    # раунд 2: герой идёт на балкон и атакует с преимуществом (3 и 17)
    rng = ScriptedRng(d20=[15, 3, 17], d6=[1, 1])
    engine = provoked_vex(
        registry, cfg, rng, ["end_turn", "move:balcony", "attack:shortsword:goblin_1"]
    )
    for _ in range(3):
        engine.step()
    assert rng.left("d20") == 0
    assert hp(engine, "goblin_1") < 30 - 4


def test_provoked_vex_ends_with_the_nearest_own_turn(registry, cfg):
    engine = provoked_vex(registry, cfg, ScriptedRng(d20=[15], d6=[1]), [])
    for _ in range(3):
        engine.step()
    assert effect_ids(engine, "hero") == []


# Topple: сбитый встаёт в начале своего хода (ревью партии 5, п. 2)

def toppled_goblin(registry, cfg, rng):
    engine = mastery_duel(registry, cfg, rng, "quarterstaff")
    engine.perform("hero", "attack:quarterstaff:goblin_1")
    assert [c.id for c in creature(engine, "goblin_1").conditions] == ["prone"]
    return engine


def test_toppled_monster_stands_up_at_the_start_of_its_turn(registry, cfg):
    engine = toppled_goblin(registry, cfg, ScriptedRng(d20=[15, 12], d6=[1]))
    engine.start_turn("goblin_1")
    assert creature(engine, "goblin_1").conditions == []


def test_standing_up_takes_all_the_movement(registry, cfg):
    engine = toppled_goblin(registry, cfg, ScriptedRng(d20=[15, 12], d6=[1]))
    engine.start_turn("goblin_1")
    assert turn(engine, "goblin_1").move == 0
    assert not [i for i in option_ids(engine, "goblin_1") if i.startswith("move:")]


def test_standing_up_leaves_the_action(registry, cfg):
    engine = toppled_goblin(registry, cfg, ScriptedRng(d20=[15, 12], d6=[1]))
    engine.start_turn("goblin_1")
    assert turn(engine, "goblin_1").action is True


def test_prone_stays_until_the_victim_turn(registry, cfg):
    engine = toppled_goblin(registry, cfg, ScriptedRng(d20=[15, 12], d6=[1]))
    engine.start_turn("hero")
    assert [c.id for c in creature(engine, "goblin_1").conditions] == ["prone"]


def test_a_turn_without_prone_keeps_the_movement(registry, cfg):
    engine = mastery_duel(registry, cfg, ScriptedRng(), "quarterstaff")
    engine.start_turn("goblin_1")
    assert turn(engine, "goblin_1").move == 1


def test_prone_of_zero_hp_is_not_removed_at_turn_start(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=ScriptedRng(d20=[12]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    down_hero(engine, "hero", by="goblin_1")
    engine.heroes["hero"].creature.conditions.append(AppliedCondition(id="prone", source="0_hp"))
    engine.start_turn("hero")
    ids = [c.id for c in engine.heroes["hero"].creature.conditions]
    assert "prone" in ids
    assert "unconscious" in ids
