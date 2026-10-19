# Шаг 93 (BACKLOG 93): эффект стрелы «усыпление» (docs/plan-93.md, решения В1-В11).
#   EffectSpec(type="sleep", dc, duration_s): dc и duration_s обязательны.
#   Сонная стрела пака (arrow_sleep): попадание -> спасбросок Тел СЛ 12; провал -- poisoned и
#   unconscious (source = стрелок, Expiry rounds 10, объекты срока раздельные); успех -- лог
#   «стряхивает сонный яд». Промах и цель на 0 HP -- броска нет. Иммунные к яду (poisoned в
#   condition_immunities или poison в damage_immunities) -- броска нет, лог «иммунитет к яду».
#   Любой урон > 0 снимает unconscious не от 0 HP (poisoned остаётся, лог «просыпается»,
#   цель prone, встаёт в начале хода). Спящий ходит только end_turn и не ищет скрытых героев.
#   Бой со спящим единственным врагом не кончается (В11). conclude снимает у не-героев состояния
#   со сроком в раундах (В10).
# Спасбросок goblin_warrior: Тел 10 (+0), СЛ 12: d20 11 -- провал, 12 -- успех.
from types import SimpleNamespace

import pytest
from combat_kit import (
    ScriptedRng,
    creature,
    custom_registry,
    give_weapon,
    hp,
    make_engine,
    mon,
    move_to,
    option_ids,
    part,
    set_hp,
)
from pydantic import ValidationError
from test_dragon_arrows import arrow_option, build_dragon, fresh_hero, hit_roll

from ai_dm.combat import end
from ai_dm.combat.downed import wake_sleeping
from ai_dm.content.models.common import EffectSpec
from ai_dm.rules.inventory import add_item
from ai_dm.state.creature import AppliedCondition, Expiry

FAIL = 11
PASS = 12
MARK = "Воин-гоблин"


@pytest.fixture
def dragon(cfg, tmp_path):
    return build_dragon(cfg, tmp_path, {"skeleton_x": ("undead", "")})


def sleep_engine(dragon, cfg, d20, registry=None, monster="goblin_warrior", miss=False):
    # первый d20 -- попадание стрелой (или 1 при miss), дальше d20 из списка
    base, hero = dragon
    registry = registry or base
    first = 1 if miss else hit_roll(dragon, 3)
    rng = ScriptedRng(d20=[first, *d20], d8=[5] * 12, d4=[2, 2, 2, 2])
    # в пресете Грея сонных стрел нет (в живом сейве они выданы сюжетом) -- кладём 10 штук
    archer = fresh_hero(hero, base)
    add_item(archer, "arrow_sleep", 10, cost_cp=0)
    engine = make_engine(
        registry, cfg, heroes=[archer], rng=rng,
        monsters=[mon("goblin_1", monster, "hall")], hero_zone="door",
    )
    creature(engine, "goblin_1").hp_max = 100
    set_hp(engine, "goblin_1", 100)
    return engine


def fire_sleep(engine):
    return engine.perform("hero", arrow_option(engine, "arrow_sleep").id)


def slept(dragon, cfg, **kwargs):
    engine = sleep_engine(dragon, cfg, [FAIL], **kwargs)
    fire_sleep(engine)
    return engine


def attack_again(engine, option="attack:composite_longbow:goblin_1"):
    # новый ход героя: действие первого выстрела потрачено, Extra Attack нет
    engine.start_turn("hero")
    engine.perform("hero", option)


def conds(engine, ref="goblin_1"):
    return {c.id: c for c in creature(engine, ref).conditions}


def lines(engine, word):
    return [line for line in engine.state.log if word in line]


def immune_registry(dragon, **fields):
    return custom_registry(dragon[0], sleeper=fields), "sleeper"


# модель и пак

def test_sleep_effect_requires_dc():
    with pytest.raises(ValidationError):
        EffectSpec(type="sleep", duration_s=60)


def test_sleep_effect_requires_duration():
    with pytest.raises(ValidationError):
        EffectSpec(type="sleep", dc=12)


def test_sleep_effect_with_dc_and_duration_is_valid():
    effect = EffectSpec(type="sleep", dc=12, duration_s=60)
    assert (effect.dc, effect.duration_s) == (12, 60)


def test_pack_arrow_sleep_is_a_sleep_effect(dragon):
    effects = dragon[0].get("item", "arrow_sleep").effects
    sleep = [(e.dc, e.duration_s) for e in effects if e.type == "sleep"]
    assert sleep == [(12, 60)]


def test_pack_arrow_sleep_keeps_poison_damage_and_drops_slow(dragon):
    # В4: урон 1d4 ядом остаётся, замедление убрано
    effects = dragon[0].get("item", "arrow_sleep").effects
    assert sorted(e.type for e in effects) == ["extra_damage", "sleep"]
    damage = [e for e in effects if e.type == "extra_damage"][0]
    assert (damage.dice, damage.damage_type) == ("1d4", "poison")


# провал спасброска

def test_failed_save_poisons_and_puts_to_sleep(dragon, cfg):
    assert set(conds(slept(dragon, cfg))) == {"poisoned", "unconscious"}


def test_sleep_conditions_come_from_the_archer(dragon, cfg):
    found = conds(slept(dragon, cfg))
    assert (found["poisoned"].source, found["unconscious"].source) == ("hero", "hero")


def test_sleep_lasts_10_rounds(dragon, cfg):
    found = conds(slept(dragon, cfg))
    assert [(c.expires.kind, c.expires.value) for c in found.values()] == [("rounds", 10)] * 2


def test_sleep_expiry_objects_are_independent(dragon, cfg):
    found = conds(slept(dragon, cfg))
    assert found["poisoned"].expires is not found["unconscious"].expires


def test_sleep_log_has_save_and_falling_asleep(dragon, cfg):
    engine = slept(dragon, cfg)
    assert lines(engine, "спасбросок con")
    assert lines(engine, "отравлен, засыпает")


def test_sleep_arrow_is_spent(dragon, cfg):
    from ai_dm.rules.inventory import count_item

    assert count_item(slept(dragon, cfg).heroes["hero"], "arrow_sleep") == 9


def melee_again(engine, registry):
    # дальняя атака по лежащему цели идёт с помехой (гасит преимущество), поэтому бьём вблизи
    give_weapon(engine.heroes["hero"], registry, "longsword")
    move_to(engine, "hero", "hall")
    attack_again(engine, "attack:longsword:goblin_1")


def test_sleeping_target_is_hit_with_advantage(dragon, cfg):
    engine = sleep_engine(dragon, cfg, [FAIL, 1, 20])
    fire_sleep(engine)
    before = hp(engine, "goblin_1")
    melee_again(engine, dragon[0])
    # преимущество: берётся лучший из 1 и 20 -- попадание, хотя первый бросок промах
    assert hp(engine, "goblin_1") < before


def test_attack_log_names_the_unconscious_state(dragon, cfg):
    engine = sleep_engine(dragon, cfg, [FAIL, 20, 20])
    fire_sleep(engine)
    melee_again(engine, dragon[0])
    assert lines(engine, "без сознания")


def test_melee_hit_on_sleeper_is_critical(dragon, cfg):
    engine = sleep_engine(dragon, cfg, [FAIL, 15, 15])
    fire_sleep(engine)
    melee_again(engine, dragon[0])
    assert lines(engine, "критическое попадание")


# успех, промах, упавшая цель

def test_passed_save_leaves_no_conditions(dragon, cfg):
    engine = sleep_engine(dragon, cfg, [PASS])
    fire_sleep(engine)
    assert conds(engine) == {}


def test_passed_save_logs_shaking_off(dragon, cfg):
    engine = sleep_engine(dragon, cfg, [PASS])
    fire_sleep(engine)
    assert lines(engine, "стряхивает сонный яд")


def test_miss_has_no_save(dragon, cfg):
    engine = sleep_engine(dragon, cfg, [], miss=True)
    fire_sleep(engine)
    assert (conds(engine), lines(engine, "спасбросок")) == ({}, [])


def test_target_downed_by_the_arrow_gets_no_save(dragon, cfg):
    engine = sleep_engine(dragon, cfg, [])
    set_hp(engine, "goblin_1", 1)
    fire_sleep(engine)
    assert (conds(engine), lines(engine, "спасбросок")) == ({}, [])


# иммунитет к яду

def test_condition_immunity_to_poisoned_means_no_save(dragon, cfg):
    registry, monster = immune_registry(dragon, condition_immunities=["poisoned"])
    engine = sleep_engine(dragon, cfg, [], registry=registry, monster=monster)
    fire_sleep(engine)
    assert (conds(engine), lines(engine, "спасбросок")) == ({}, [])


def test_poison_immunity_logs_the_reason(dragon, cfg):
    registry, monster = immune_registry(dragon, condition_immunities=["poisoned"])
    engine = sleep_engine(dragon, cfg, [], registry=registry, monster=monster)
    fire_sleep(engine)
    assert lines(engine, "иммунитет к яду")


def test_poison_damage_immunity_alone_means_no_save(dragon, cfg):
    registry, monster = immune_registry(dragon, damage_immunities=["poison"])
    engine = sleep_engine(dragon, cfg, [], registry=registry, monster=monster)
    fire_sleep(engine)
    assert (conds(engine), lines(engine, "иммунитет к яду") != []) == ({}, True)


# пробуждение уроном

def test_damage_wakes_the_sleeper_but_keeps_poison(dragon, cfg):
    engine = sleep_engine(dragon, cfg, [FAIL, 15, 15])
    fire_sleep(engine)
    attack_again(engine)
    assert "unconscious" not in conds(engine)
    assert "poisoned" in conds(engine)


def test_waking_is_logged(dragon, cfg):
    engine = sleep_engine(dragon, cfg, [FAIL, 15, 15])
    fire_sleep(engine)
    attack_again(engine)
    assert lines(engine, "просыпается")


def test_woken_target_is_prone(dragon, cfg):
    engine = sleep_engine(dragon, cfg, [FAIL, 15, 15])
    fire_sleep(engine)
    attack_again(engine)
    assert "prone" in conds(engine)


def test_woken_target_prone_comes_from_the_archer(dragon, cfg):
    engine = sleep_engine(dragon, cfg, [FAIL, 15, 15])
    fire_sleep(engine)
    attack_again(engine)
    assert conds(engine)["prone"].source == "hero"


def test_one_point_of_damage_wakes_the_sleeper(dragon, cfg):
    engine = slept(dragon, cfg)
    wake_sleeping(engine, "goblin_1", SimpleNamespace(final=1))
    assert "unconscious" not in conds(engine)


def test_woken_target_stands_up_in_its_turn_spending_move(dragon, cfg):
    engine = sleep_engine(dragon, cfg, [FAIL, 15, 15])
    fire_sleep(engine)
    attack_again(engine)
    engine.start_turn("goblin_1")
    assert ("prone" in conds(engine), part(engine, "goblin_1").turn.move) == (False, 0)


def test_zero_damage_does_not_wake(dragon, cfg):
    registry, monster = immune_registry(dragon, damage_immunities=["piercing"])
    engine = sleep_engine(dragon, cfg, [15, 15], registry=registry, monster=monster)
    creature(engine, "goblin_1").conditions.append(
        AppliedCondition(id="unconscious", source="hero", expires=Expiry(kind="rounds", value=10))
    )
    engine.perform("hero", "attack:composite_longbow:goblin_1")
    assert "unconscious" in conds(engine)


def test_unconscious_from_zero_hp_is_not_woken_by_damage(dragon, cfg):
    engine = sleep_engine(dragon, cfg, [15, 15])
    creature(engine, "goblin_1").conditions.append(
        AppliedCondition(id="unconscious", source="0_hp")
    )
    engine.perform("hero", "attack:composite_longbow:goblin_1")
    assert not lines(engine, "просыпается")


# срок

def test_conditions_end_after_ten_rounds(dragon, cfg):
    engine = slept(dragon, cfg)
    for _ in range(10):
        engine.tick_rounds()
    assert conds(engine) == {}


def test_conditions_stay_before_ten_rounds(dragon, cfg):
    engine = slept(dragon, cfg)
    for _ in range(9):
        engine.tick_rounds()
    assert set(conds(engine)) == {"poisoned", "unconscious"}


# ход спящего

def test_sleeper_only_ends_turn(dragon, cfg):
    engine = slept(dragon, cfg)
    assert option_ids(engine, "goblin_1") == ["end_turn"]


def test_sleeper_turn_steps_without_error(dragon, cfg):
    engine = slept(dragon, cfg)
    engine.state.turn_index = 1
    engine.step()
    assert engine.state.turn_index == 0


def test_sleeper_does_not_search_for_hidden_hero(dragon, cfg):
    # d20 в очереди нет: попытка поиска упала бы на «неожиданный бросок»
    engine = slept(dragon, cfg)
    hero = creature(engine, "hero")
    hero.conditions.append(AppliedCondition(id="invisible", source="hidden", dc=15))
    engine.start_turn("goblin_1")
    assert any(c.id == "invisible" and c.source == "hidden" for c in hero.conditions)


def test_awake_enemy_still_searches_for_hidden_hero(dragon, cfg):
    engine = sleep_engine(dragon, cfg, [])
    hero = creature(engine, "hero")
    hero.conditions.append(AppliedCondition(id="invisible", source="hidden", dc=15))
    engine.start_turn("goblin_1")
    assert lines(engine, "ищет")


# бой и конец боя

def test_fight_with_only_sleeping_enemy_goes_on(dragon, cfg):
    engine = slept(dragon, cfg)
    assert engine.state.outcome is None


def test_conclude_clears_round_conditions_of_npcs(dragon, cfg):
    engine = slept(dragon, cfg)
    engine.state.outcome = "ended_by_master"
    end.conclude(engine)
    assert conds(engine) == {}


def test_conclude_keeps_conditions_without_round_expiry(dragon, cfg):
    engine = sleep_engine(dragon, cfg, [])
    creature(engine, "goblin_1").conditions.append(AppliedCondition(id="poisoned", source="hero"))
    engine.state.outcome = "ended_by_master"
    end.conclude(engine)
    assert "poisoned" in conds(engine)


# условия стрелы кладутся после урона

def test_fire_arrow_burns_target_that_endures_at_one_hp(dragon, cfg):
    # Стойкость нежити: урон довёл до 0, спасбросок успешен (d20 20) -- цель на 1 HP и горит
    registry = custom_registry(
        dragon[0], tough={"traits": ["undead_fortitude"], "creature_type": "undead"}
    )
    engine = sleep_engine(dragon, cfg, [20], registry=registry, monster="tough")
    engine.rng.queues["d6"] = [4]
    set_hp(engine, "goblin_1", 5)
    engine.perform("hero", arrow_option(engine, "arrow_fire").id)
    kinds = [e.kind for e in creature(engine, "goblin_1").active_effects]
    assert (hp(engine, "goblin_1"), kinds) == (1, ["burning"])
