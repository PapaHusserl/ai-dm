# К8с П2 (docs/plan-k8s.md, «Тесты» П2; Р-К8с-5, Р-К8с-6): заклинания следопыта в бою.
#   Метка охотника: бесплатно и 1 кругом -- Concentration.until_s = now + 3600; 3 кругом -- + 28800
#     (8 ч), ячейка 3 круга тратится; 5 кругом -- + 86400; концентрация хранит круг ячейки.
#   Меню Метки у следопыта 10: базовые пункты и «Метка охотника (3 круг) → цель»; 2 и 4 круг не
#     предлагаются даже с ячейкой; у следопыта 5 -- пункты как до К8с (только 1 круг).
#   Призыв животных (аура, как Духовные стражи): враг в зоне следопыта в конце хода -- спасбросок
#     Лов (СЛ 14), провал -- 3d10 рубящего, успех -- 0 (не половина); 4 кругом 4d10.
from combat_kit import ScriptedRng, creature, hp, mon, option_ids
from test_ranger_combat import make_ranger, pool, ranger_engine, tough
from test_summons_aura import end_turn

from ai_dm.state.creature import ResourcePool

HOUR = 3600
GOBLIN = [mon("goblin_1", "goblin_warrior", "hall")]
IN_ZONE = [mon("goblin_1", "goblin_warrior", "door")]


def engine_at(registry, cfg, level, rng=None, monsters=GOBLIN, slots=(), spells=()):
    hero = make_ranger(registry, level=level)
    hero.sheet.prepared_of().extend(spells)
    for circle in slots:
        hero.creature.resources[f"spell_slot:{circle}"] = ResourcePool(current=1, max=1)
    return ranger_engine(registry, cfg, rng or ScriptedRng(), hero=hero, monsters=monsters)


def until_after(engine, option):
    start = engine.world.clock.now_s
    engine.perform("hero", option)
    return creature(engine, "hero").concentration.until_s - start


def mark_ids(engine):
    return [i for i in option_ids(engine, "hero") if i.startswith("cast:hunters_mark:")]


# срок Метки по кругу

def test_free_mark_lasts_an_hour(registry, cfg):
    engine = engine_at(registry, cfg, 10)
    assert until_after(engine, "cast:hunters_mark:1:goblin_1:free") == HOUR


def test_first_circle_slot_mark_lasts_an_hour(registry, cfg):
    engine = engine_at(registry, cfg, 10)
    pool(engine, "favored_enemy").current = 0
    assert until_after(engine, "cast:hunters_mark:1:goblin_1") == HOUR


def test_third_circle_mark_lasts_eight_hours(registry, cfg):
    engine = engine_at(registry, cfg, 10)
    assert until_after(engine, "cast:hunters_mark:3:goblin_1") == 8 * HOUR


def test_third_circle_mark_spends_a_third_circle_slot(registry, cfg):
    engine = engine_at(registry, cfg, 10)
    before = pool(engine, "spell_slot:3").current
    first = pool(engine, "spell_slot:1").current
    engine.perform("hero", "cast:hunters_mark:3:goblin_1")
    assert pool(engine, "spell_slot:3").current == before - 1
    assert pool(engine, "spell_slot:1").current == first


def test_third_circle_mark_keeps_the_circle_in_concentration(registry, cfg):
    engine = engine_at(registry, cfg, 10)
    engine.perform("hero", "cast:hunters_mark:3:goblin_1")
    assert creature(engine, "hero").concentration.circle == 3


def test_fifth_circle_mark_lasts_a_day(registry, cfg):
    engine = engine_at(registry, cfg, 10, slots=(5,))
    assert until_after(engine, "cast:hunters_mark:5:goblin_1") == 24 * HOUR


def test_third_circle_mark_still_marks_the_target(registry, cfg):
    engine = engine_at(registry, cfg, 10)
    engine.perform("hero", "cast:hunters_mark:3:goblin_1")
    assert creature(engine, "goblin_1").active_effects[0].kind == "mark"


# меню боя

def test_ranger_ten_menu_offers_the_third_circle_mark(registry, cfg):
    engine = engine_at(registry, cfg, 10)
    assert "cast:hunters_mark:3:goblin_1" in mark_ids(engine)


def test_third_circle_mark_label_names_the_circle(registry, cfg):
    engine = engine_at(registry, cfg, 10)
    wanted = "cast:hunters_mark:3:goblin_1"
    (option,) = [o for o in engine.available_actions("hero") if o.id == wanted]
    assert "(3 круг)" in option.label


def test_ranger_ten_menu_keeps_the_base_mark(registry, cfg):
    engine = engine_at(registry, cfg, 10)
    assert "cast:hunters_mark:1:goblin_1" in mark_ids(engine)


def test_ranger_ten_menu_has_no_second_circle_mark(registry, cfg):
    engine = engine_at(registry, cfg, 10)
    assert pool(engine, "spell_slot:2").current > 0
    assert "cast:hunters_mark:2:goblin_1" not in mark_ids(engine)


def test_ranger_ten_menu_has_no_fourth_circle_mark(registry, cfg):
    engine = engine_at(registry, cfg, 10, slots=(4,))
    assert "cast:hunters_mark:4:goblin_1" not in mark_ids(engine)


def test_ranger_ten_menu_offers_the_fifth_circle_mark_with_a_slot(registry, cfg):
    engine = engine_at(registry, cfg, 10, slots=(5,))
    assert "cast:hunters_mark:5:goblin_1" in mark_ids(engine)


def test_ranger_five_menu_has_only_the_base_mark(registry, cfg):
    engine = engine_at(registry, cfg, 5)
    assert pool(engine, "spell_slot:2").current > 0
    assert set(mark_ids(engine)) == {
        "cast:hunters_mark:1:goblin_1", "cast:hunters_mark:1:goblin_1:free",
    }


# Призыв животных

def conjure(registry, cfg, rng, slots=()):
    engine = engine_at(
        registry, cfg, 10, rng=rng, monsters=IN_ZONE, slots=slots, spells=("conjure_animals",),
    )
    tough(engine)
    return engine


def test_conjure_animals_failed_save_deals_three_d10_slashing(registry, cfg):
    engine = conjure(registry, cfg, ScriptedRng(d20=[5], d10=[4, 5, 6]))
    engine.perform("hero", "cast:conjure_animals:3:")
    end_turn(engine, "goblin_1")
    assert hp(engine, "goblin_1") == 30 - 15


def test_conjure_animals_passed_save_deals_nothing(registry, cfg):
    engine = conjure(registry, cfg, ScriptedRng(d20=[19], d10=[4, 5, 6]))
    engine.perform("hero", "cast:conjure_animals:3:")
    end_turn(engine, "goblin_1")
    assert hp(engine, "goblin_1") == 30


def test_conjure_animals_fourth_circle_rolls_four_d10(registry, cfg):
    engine = conjure(registry, cfg, ScriptedRng(d20=[5], d10=[1, 2, 3, 4]), slots=(4,))
    engine.perform("hero", "cast:conjure_animals:4:")
    end_turn(engine, "goblin_1")
    assert hp(engine, "goblin_1") == 30 - 10


def test_conjure_animals_concentration_lasts_ten_minutes(registry, cfg):
    engine = conjure(registry, cfg, ScriptedRng())
    assert until_after(engine, "cast:conjure_animals:3:") == 600


def test_wind_wall_is_offered_on_a_zone_two_steps_away(registry, cfg):
    from combat_kit import make_engine, make_line

    hero = make_ranger(registry, level=10)
    hero.sheet.prepared_of().append("wind_wall")
    engine = make_engine(
        registry, cfg, heroes=[hero], zones=make_line(4), hero_zone="z0",
        monsters=[mon("goblin_1", "goblin_warrior", "z3")],
    )
    assert any(i.startswith("cast:wind_wall:3:z2") for i in option_ids(engine, "hero"))


def test_conjure_animals_holds_concentration_and_a_third_circle_slot(registry, cfg):
    engine = conjure(registry, cfg, ScriptedRng())
    before = pool(engine, "spell_slot:3").current
    engine.perform("hero", "cast:conjure_animals:3:")
    assert creature(engine, "hero").concentration.spell_id == "conjure_animals"
    assert pool(engine, "spell_slot:3").current == before - 1


def test_spirit_guardians_aura_without_mode_defaults_to_half(registry, cfg):
    from test_summons_aura import guardians

    engine = guardians(registry, cfg)
    (effect,) = [e for e in creature(engine, "cler").active_effects if e.kind == "aura"]
    assert effect.params["mode"] == "half"
