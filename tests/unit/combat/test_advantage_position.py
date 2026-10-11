# Высота и скрытность (stage3-live-advantage V1-V4). Ожидаемый API:
#   Zone(..., elevation: int = 0) -- 0 земля, >0 выше, <0 ниже.
#   Атака (в т.ч. дальняя) из зоны выше цели -- преимущество «высота»; из зоны ниже -- помеха;
#     в одной по высоте зонах -- без эффекта. Для монстров так же.
#   Вариант боя "hide" (Спрятаться, действие): доступен при укрытии (cover_*) или ZoneFeature
#     "obscured" в зоне героя и без врагов в этой зоне. Скрытность (Лов) СЛ 15: успех -- состояние
#     "invisible" (source "hidden", dc = результат Скрытности) у героя, провал -- действие
#     потрачено, состояния нет.
#   Атака из "hidden" -- преимущество «скрытно»; после атаки скрытность снимается.
#   Враг на своём ходу (start_turn) бросает Внимательность (d20 + Мдр): >= результата Скрытности --
#     скрытность снимается.
#   Строка броска: «d20 (7, 15 → преим.: высота, скрытно)»; при отмене -- «преимущество и помеха
#     гасят друг друга (высота / яд)».
from combat_kit import (
    ScriptedRng,
    creature,
    feature,
    give_weapon,
    hp,
    make_engine,
    make_fighter,
    mon,
    option_ids,
)

from ai_dm.rules.derived import skill_bonus
from ai_dm.state.combat import Zone
from ai_dm.state.creature import AppliedCondition


def zones(balcony_elevation=0, hall_elevation=0, hall_features=()):
    return [
        Zone(id="door", name="У двери", adjacent=["hall"]),
        Zone(
            id="hall", name="Центр зала", adjacent=["door", "balcony"],
            features=list(hall_features), elevation=hall_elevation,
        ),
        Zone(
            id="balcony", name="Балкон", adjacent=["hall"], elevation=balcony_elevation
        ),
    ]


def scout(registry):
    # лучник без доспеха (помеха Скрытности от кольчуги не мешает)
    hero = make_fighter(registry)
    hero.equipped.armor = None
    give_weapon(hero, registry, "shortbow")
    return hero


def shoot(registry, cfg, rng, hero_zone="hall", goblin_zone="balcony", **zone_args):
    engine = make_engine(
        registry, cfg, heroes=[(scout(registry), hero_zone)], rng=rng,
        zones=zones(**zone_args), monsters=[mon("goblin_1", "goblin_warrior", goblin_zone)],
    )
    return engine


def has(engine, ref, condition_id):
    # скрытность -- состояние «невидимый» с source "hidden" (condition_id "hidden" -- сокращение)
    if condition_id == "hidden":
        return any(
            c.id == "invisible" and c.source == "hidden" for c in creature(engine, ref).conditions
        )
    return any(c.id == condition_id for c in creature(engine, ref).conditions)


def last_attack_line(engine):
    return [line for line in engine.state.log if "->" in line][0]


# высота

def test_attack_from_higher_zone_has_advantage(registry, cfg):
    # 3 и 18: берётся 18 (+3 = 21 против КД 15); без преимущества 3 + 3 = 6 -- промах
    engine = shoot(registry, cfg, ScriptedRng(d20=[3, 18], d6=[4]), hero_zone="balcony",
                   goblin_zone="hall", balcony_elevation=1)
    engine.perform("hero", "attack:shortbow:goblin_1")
    assert hp(engine, "goblin_1") == 10 - 5


def test_attack_from_lower_zone_has_disadvantage(registry, cfg):
    # 18 и 3: берётся 3 -- промах
    engine = shoot(registry, cfg, ScriptedRng(d20=[18, 3]), balcony_elevation=1)
    engine.perform("hero", "attack:shortbow:goblin_1")
    assert hp(engine, "goblin_1") == 10


def test_attack_from_pit_target_above_is_disadvantage_too(registry, cfg):
    # герой в яме (-1), цель на земле: ниже цели
    engine = shoot(registry, cfg, ScriptedRng(d20=[18, 3]), hall_elevation=-1,
                   goblin_zone="balcony")
    engine.perform("hero", "attack:shortbow:goblin_1")
    assert hp(engine, "goblin_1") == 10


def test_attack_at_same_elevation_rolls_one_die(registry, cfg):
    rng = ScriptedRng(d20=[12], d6=[4])
    engine = shoot(registry, cfg, rng, balcony_elevation=2, hall_elevation=2)
    engine.perform("hero", "attack:shortbow:goblin_1")
    assert rng.left("d20") == 0
    assert hp(engine, "goblin_1") == 10 - 5


def test_attack_on_flat_map_rolls_one_die(registry, cfg):
    rng = ScriptedRng(d20=[12], d6=[4])
    engine = shoot(registry, cfg, rng)
    engine.perform("hero", "attack:shortbow:goblin_1")
    assert rng.left("d20") == 0


def test_monster_on_high_ground_attacks_with_advantage(registry, cfg):
    # гоблин на балконе (выше) стреляет в героя без доспеха (КД 13); берётся 19
    engine = shoot(registry, cfg, ScriptedRng(d20=[2, 19], d6=[3], d4=[2]), balcony_elevation=1)
    hp_before = hp(engine, "hero")
    engine.perform("goblin_1", "attack:короткий_лук:hero")
    assert hp(engine, "hero") < hp_before


def test_monster_below_the_hero_attacks_with_disadvantage(registry, cfg):
    engine = shoot(registry, cfg, ScriptedRng(d20=[19, 2]), hall_elevation=1)
    hp_before = hp(engine, "hero")
    engine.perform("goblin_1", "attack:короткий_лук:hero")
    assert hp(engine, "hero") == hp_before


def test_height_is_named_in_the_roll_line(registry, cfg):
    engine = shoot(registry, cfg, ScriptedRng(d20=[7, 15], d6=[4]), hero_zone="balcony",
                   goblin_zone="hall", balcony_elevation=1)
    engine.perform("hero", "attack:shortbow:goblin_1")
    line = last_attack_line(engine)
    assert "преим.:" in line
    assert "высота" in line


def test_lower_zone_is_named_in_the_roll_line(registry, cfg):
    engine = shoot(registry, cfg, ScriptedRng(d20=[15, 7]), balcony_elevation=1)
    engine.perform("hero", "attack:shortbow:goblin_1")
    line = last_attack_line(engine)
    assert "помеха:" in line
    assert "ниже цели" in line


# Спрятаться

def covered(registry, cfg, rng, goblin_zone="balcony", kind="cover_half"):
    return shoot(registry, cfg, rng, goblin_zone=goblin_zone, hall_features=[feature(kind)])


def stealth_roll_for(registry, total):
    # грань d20, дающая общий результат Скрытности total
    return total - skill_bonus(scout(registry), registry, "stealth")


def test_hide_is_available_with_cover(registry, cfg):
    engine = covered(registry, cfg, ScriptedRng())
    assert "hide" in option_ids(engine, "hero")


def test_hide_is_available_in_obscured_zone(registry, cfg):
    engine = covered(registry, cfg, ScriptedRng(), kind="obscured")
    assert "hide" in option_ids(engine, "hero")


def test_hide_is_not_available_without_cover(registry, cfg):
    engine = shoot(registry, cfg, ScriptedRng())
    assert "hide" not in option_ids(engine, "hero")


def test_hide_is_not_available_with_enemy_in_the_zone(registry, cfg):
    engine = covered(registry, cfg, ScriptedRng(), goblin_zone="hall")
    assert "hide" not in option_ids(engine, "hero")


def test_hide_success_makes_the_hero_hidden(registry, cfg):
    face = stealth_roll_for(registry, 15)
    engine = covered(registry, cfg, ScriptedRng(d20=[face]))
    engine.perform("hero", "hide")
    assert has(engine, "hero", "hidden")


def test_hide_failure_leaves_the_hero_visible(registry, cfg):
    face = stealth_roll_for(registry, 14)
    engine = covered(registry, cfg, ScriptedRng(d20=[face]))
    engine.perform("hero", "hide")
    assert not has(engine, "hero", "hidden")


def test_hide_costs_the_action_even_on_failure(registry, cfg):
    face = stealth_roll_for(registry, 14)
    engine = covered(registry, cfg, ScriptedRng(d20=[face]))
    engine.perform("hero", "hide")
    assert "hide" not in option_ids(engine, "hero")


# атака из скрытности

def hidden_hero(registry, cfg, rng, **kwargs):
    engine = shoot(registry, cfg, rng, **kwargs)
    creature(engine, "hero").conditions.append(AppliedCondition(id="invisible", source="hidden"))
    return engine


def test_attack_from_hiding_has_advantage(registry, cfg):
    # 3 и 18: берётся 18; без преимущества промах
    engine = hidden_hero(registry, cfg, ScriptedRng(d20=[3, 18], d6=[4]))
    engine.perform("hero", "attack:shortbow:goblin_1")
    assert hp(engine, "goblin_1") == 10 - 5


def test_attack_removes_hiding_on_hit(registry, cfg):
    engine = hidden_hero(registry, cfg, ScriptedRng(d20=[18, 18], d6=[4]))
    engine.perform("hero", "attack:shortbow:goblin_1")
    assert not has(engine, "hero", "hidden")


def test_attack_removes_hiding_on_miss(registry, cfg):
    engine = hidden_hero(registry, cfg, ScriptedRng(d20=[1, 1]))
    engine.perform("hero", "attack:shortbow:goblin_1")
    assert not has(engine, "hero", "hidden")


def test_second_attack_after_hiding_rolls_one_die(registry, cfg):
    rng = ScriptedRng(d20=[18, 18, 12], d6=[4, 4])
    engine = hidden_hero(registry, cfg, rng)
    engine.perform("hero", "attack:shortbow:goblin_1")
    engine.part("hero").turn.action = True
    engine.perform("hero", "attack:shortbow:goblin_1")
    assert rng.left("d20") == 0


def test_hidden_is_named_in_the_roll_line(registry, cfg):
    engine = hidden_hero(registry, cfg, ScriptedRng(d20=[7, 15], d6=[4]))
    engine.perform("hero", "attack:shortbow:goblin_1")
    assert "преим.: скрытно" in last_attack_line(engine)


def test_height_and_hiding_are_both_named(registry, cfg):
    engine = hidden_hero(registry, cfg, ScriptedRng(d20=[7, 15], d6=[4]), hero_zone="balcony",
                         goblin_zone="hall", balcony_elevation=1)
    engine.perform("hero", "attack:shortbow:goblin_1")
    line = last_attack_line(engine)
    assert "преим.:" in line
    assert "высота" in line
    assert "скрытно" in line


# обнаружение врагом

def hidden_with_result(registry, cfg, rng, total):
    # герой спрятан с результатом Скрытности total: бросок делает движок через "hide"
    face = stealth_roll_for(registry, total)
    rng.queues["d20"].insert(0, face)
    engine = covered(registry, cfg, rng)
    engine.perform("hero", "hide")
    return engine


def test_enemy_notices_hero_when_perception_equals_stealth(registry, cfg):
    # Внимательность гоблина: d20 + Мдр (8 -> -1); 19 - 1 = 18 >= 18
    engine = hidden_with_result(registry, cfg, ScriptedRng(d20=[19]), 18)
    engine.start_turn("goblin_1")
    assert not has(engine, "hero", "hidden")


def test_enemy_does_not_notice_hero_when_perception_is_lower(registry, cfg):
    engine = hidden_with_result(registry, cfg, ScriptedRng(d20=[18]), 18)
    engine.start_turn("goblin_1")
    assert has(engine, "hero", "hidden")


# взаимная отмена

def test_height_and_poison_cancel_each_other(registry, cfg):
    # преимущество и помеха гасят друг друга: один d20
    rng = ScriptedRng(d20=[12], d6=[4])
    engine = shoot(registry, cfg, rng, hero_zone="balcony", goblin_zone="hall",
                   balcony_elevation=1)
    creature(engine, "hero").conditions.append(AppliedCondition(id="poisoned"))
    engine.perform("hero", "attack:shortbow:goblin_1")
    assert rng.left("d20") == 0


def test_cancel_line_names_both_sources(registry, cfg):
    engine = shoot(registry, cfg, ScriptedRng(d20=[12], d6=[4]), hero_zone="balcony",
                   goblin_zone="hall", balcony_elevation=1)
    creature(engine, "hero").conditions.append(AppliedCondition(id="poisoned"))
    engine.perform("hero", "attack:shortbow:goblin_1")
    assert "преимущество и помеха гасят друг друга (высота / яд)" in last_attack_line(engine)


def test_hiding_and_lower_zone_cancel_each_other(registry, cfg):
    rng = ScriptedRng(d20=[12], d6=[4])
    engine = hidden_hero(registry, cfg, rng, balcony_elevation=1)
    engine.perform("hero", "attack:shortbow:goblin_1")
    assert rng.left("d20") == 0
    assert not has(engine, "hero", "hidden")
