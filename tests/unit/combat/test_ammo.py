# Боеприпасы в бою (docs/plan-bp.md, решения 1-5, 7): обычные стрелы тратятся поштучно
# (попал или промахнулся), при 0 пункта выстрела нет, остаток -- в подписи; после победы
# подбирается половина (вниз) потраченного каждого вида, бегство -- ничего.
# Герой -- Грей-следопыт (набор следопыта: 20 стрел), цель -- воин-гоблин, КД 15.
import pytest
from combat_kit import (
    ScriptedRng,
    creature,
    make_engine,
    make_fighter,
    mon,
    option_ids,
    set_hp,
)
from test_ranger_combat import SHOOT, make_ranger, ranger_engine, tough

from ai_dm.combat.controllers import AutoHeroController
from ai_dm.rules.inventory import add_item, count_item, remove_item
from ai_dm.state.creature import ActiveEffect

MISS = 1
HIT = 15


def arrows(engine):
    return count_item(engine.heroes["hero"], "arrows")


def set_arrows(engine, qty):
    hero = engine.heroes["hero"]
    remove_item(hero, "arrows", arrows(engine))
    if qty:
        add_item(hero, "arrows", qty, cost_cp=0)


def label_of(engine, option_id):
    return [o.label for o in engine.available_actions("hero") if o.id == option_id][0]


def shots(engine, count):
    # count выстрелов по очереди, каждый с новым ходом героя (броски -- в ScriptedRng движка)
    for _ in range(count):
        engine.start_turn("hero")
        engine.perform("hero", SHOOT)


# выстрел и подпись

def test_ranger_has_twenty_arrows_and_the_shot_is_offered(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng())
    assert arrows(engine) == 20
    assert SHOOT in option_ids(engine, "hero")


def test_label_shows_the_stock(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng())
    assert label_of(engine, SHOOT) == "Атака: длинный лук (осталось 20) → Воин-гоблин"


def test_hit_spends_one_arrow(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng(d20=[HIT], d8=[5]))
    tough(engine)
    engine.perform("hero", SHOOT)
    assert arrows(engine) == 19


def test_miss_spends_one_arrow(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng(d20=[MISS]))
    engine.perform("hero", SHOOT)
    assert arrows(engine) == 19


def test_label_after_a_shot_shows_the_new_stock(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng(d20=[MISS]))
    engine.perform("hero", SHOOT)
    engine.start_turn("hero")
    assert "(осталось 19)" in label_of(engine, SHOOT)


def test_extra_attack_spends_two_arrows_a_turn(registry, cfg):
    engine = ranger_engine(
        registry, cfg, ScriptedRng(d20=[MISS, MISS]), hero=make_ranger(registry, level=5)
    )
    engine.perform("hero", SHOOT)
    engine.perform("hero", SHOOT)
    assert arrows(engine) == 18


def test_shot_without_arrows_is_not_offered(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng())
    set_arrows(engine, 0)
    assert SHOOT not in option_ids(engine, "hero")


def test_last_arrow_leaves_no_shot_and_logs_it(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng(d20=[MISS]))
    set_arrows(engine, 1)
    engine.perform("hero", SHOOT)
    assert arrows(engine) == 0
    assert any("Грей: стрелы кончились" in line for line in engine.state.log)
    engine.start_turn("hero")
    assert SHOOT not in option_ids(engine, "hero")


def test_no_end_line_while_arrows_remain(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng(d20=[MISS]))
    set_arrows(engine, 2)
    engine.perform("hero", SHOOT)
    assert not any("кончились" in line for line in engine.state.log)


def test_melee_weapon_spends_no_arrows_and_has_no_stock_in_label(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_ranger(registry)], rng=ScriptedRng(d20=[MISS]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")], hero_zone="hall",
    )
    assert label_of(engine, "attack:scimitar:goblin_1") == "Атака: скимитар → Воин-гоблин"
    engine.perform("hero", "attack:scimitar:goblin_1")
    assert arrows(engine) == 20


def test_fighter_melee_label_has_no_stock(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=ScriptedRng(),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    labels = [o.label for o in engine.available_actions("hero") if o.kind == "attack"]
    assert labels
    assert not [lb for lb in labels if "осталось" in lb]


def test_monster_archer_shoots_without_limit(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=ScriptedRng(d20=[MISS] * 8),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")], hero_zone="door",
    )
    shoot = "attack:короткий_лук:hero"  # воин-гоблин: Короткий лук, weapon_id shortbow
    for _ in range(3):
        engine.start_turn("goblin_1")
        options = {o.id: o for o in engine.available_actions("goblin_1")}
        assert shoot in options
        assert "осталось" not in options[shoot].label
        engine.perform("goblin_1", shoot)


# истребитель орд

def horde_engine(registry, cfg, rng):
    hero = make_ranger(
        registry, level=3, subclass="hunter", options={"hunters_prey": "horde_breaker"}
    )
    monsters = [
        mon("goblin_1", "goblin_warrior", "hall"), mon("goblin_2", "goblin_warrior", "hall"),
    ]
    engine = make_engine(
        registry, cfg, heroes=[hero], rng=rng, monsters=monsters, hero_zone="door",
    )
    for ref in ("goblin_1", "goblin_2"):
        creature(engine, ref).hp_max = 40
        set_hp(engine, ref, 40)
    return engine


def horde_ids(engine):
    return [o.id for o in engine.available_actions("hero") if o.kind == "horde_breaker"]


def test_horde_breaker_shot_spends_an_arrow(registry, cfg):
    engine = horde_engine(registry, cfg, ScriptedRng(d20=[MISS, MISS]))
    engine.perform("hero", SHOOT)
    assert horde_ids(engine)
    engine.perform("hero", horde_ids(engine)[0])
    assert arrows(engine) == 18


def test_horde_breaker_option_is_gone_when_arrows_ran_out(registry, cfg):
    engine = horde_engine(registry, cfg, ScriptedRng(d20=[MISS]))
    set_arrows(engine, 1)
    engine.perform("hero", SHOOT)
    assert horde_ids(engine) == []


# особые стрелы и обычные

# (особые стрелы -- в test_dragon_arrows.py: их оружие и стрелы есть только в паке)

def test_thrown_improvised_weapon_is_not_ammunition(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng())
    set_arrows(engine, 0)
    thrown = [o for o in engine.available_actions("hero") if "improvised_thrown" in o.id]
    assert thrown
    assert all("осталось" not in o.label for o in thrown)


# подбор после боя

def win_with(engine):
    # добивающий выстрел: враг на 1 HP
    set_hp(engine, "goblin_1", 1)
    engine.start_turn("hero")
    engine.perform("hero", SHOOT)


def test_seven_shots_and_a_victory_return_three_arrows(registry, cfg):
    engine = ranger_engine(
        registry, cfg, ScriptedRng(d20=[MISS] * 6 + [HIT], d8=[5]), hero=make_ranger(registry),
    )
    tough(engine)
    shots(engine, 6)
    win_with(engine)
    assert engine.state.outcome == "victory"
    assert arrows(engine) == 13 + 3


def test_pickup_is_logged(registry, cfg):
    engine = ranger_engine(
        registry, cfg, ScriptedRng(d20=[MISS] * 6 + [HIT], d8=[5]), hero=make_ranger(registry),
    )
    tough(engine)
    shots(engine, 6)
    win_with(engine)
    assert any("Грей: подобрал стрелы ×3" in line for line in engine.state.log)


def test_one_shot_returns_nothing(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng(d20=[HIT], d8=[5]))
    set_hp(engine, "goblin_1", 1)
    engine.perform("hero", SHOOT)
    assert engine.state.outcome == "victory"
    assert arrows(engine) == 19
    assert not any("подобрал" in line for line in engine.state.log)


def test_flag_is_cleared_after_the_fight(registry, cfg):
    engine = ranger_engine(
        registry, cfg, ScriptedRng(d20=[MISS, HIT], d8=[5]), hero=make_ranger(registry),
    )
    tough(engine)
    shots(engine, 1)
    win_with(engine)
    flags = [e for e in creature(engine, "hero").active_effects if e.id == "ammo_spent"]
    assert flags == []


def test_fleeing_returns_nothing_and_clears_the_flag(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng(d20=[MISS] * 4))
    shots(engine, 4)
    engine.state.outcome = "fled"
    from ai_dm.combat import end

    end.settle_ground(engine)
    assert arrows(engine) == 16
    assert not [e for e in creature(engine, "hero").active_effects if e.id == "ammo_spent"]


def test_downed_hero_does_not_pick_up(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng(d20=[MISS] * 4))
    shots(engine, 4)
    engine.heroes["hero"].status = "down"
    engine.state.outcome = "victory"
    from ai_dm.combat import end

    end.settle_ground(engine)
    assert arrows(engine) == 16


def test_shot_records_the_spent_arrow(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng(d20=[MISS]))
    engine.perform("hero", SHOOT)
    flags = [e for e in creature(engine, "hero").active_effects if isinstance(e, ActiveEffect)
             and e.id == "ammo_spent"]
    assert [f.params for f in flags] == [{"arrows": 1}]


def test_spent_marker_is_a_flag_effect(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng(d20=[MISS]))
    engine.perform("hero", SHOOT)
    kinds = [e.kind for e in creature(engine, "hero").active_effects if e.id == "ammo_spent"]
    assert kinds == ["flag"]


def settle_victory(engine):
    from ai_dm.combat import end

    engine.state.outcome = "victory"
    end.settle_ground(engine)


@pytest.mark.parametrize(("spent", "back"), [(1, 0), (2, 1), (3, 1), (4, 2), (5, 2)])
def test_half_of_spent_rounded_down_comes_back(registry, cfg, spent, back):
    engine = ranger_engine(registry, cfg, ScriptedRng(d20=[MISS] * spent))
    shots(engine, spent)
    settle_victory(engine)
    assert arrows(engine) == 20 - spent + back


@pytest.mark.parametrize(("spent", "text"), [(2, "×1"), (4, "×2"), (5, "×2")])
def test_pickup_log_line_has_an_integer_count(registry, cfg, spent, text):
    engine = ranger_engine(registry, cfg, ScriptedRng(d20=[MISS] * spent))
    shots(engine, spent)
    settle_victory(engine)
    lines = [line for line in engine.state.log if "подобрал" in line]
    assert len(lines) == 1
    assert lines[0].endswith(f"стрелы {text}")


def test_downed_first_hero_does_not_stop_pickup_of_the_next(registry, cfg):
    ally = make_ranger(registry).model_copy(deep=True)
    ally.id = "ally"
    engine = make_engine(
        registry, cfg, heroes=[make_ranger(registry), ally], rng=ScriptedRng(d20=[MISS] * 4),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")], hero_zone="door",
    )
    for _ in range(4):
        engine.start_turn("ally")
        engine.perform("ally", SHOOT)
    engine.heroes["hero"].status = "down"
    settle_victory(engine)
    assert count_item(engine.heroes["ally"], "arrows") == 20 - 4 + 2


# без стрел

def test_no_arrows_and_far_enemy_leaves_only_improvised_throw(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng())
    set_arrows(engine, 0)
    ranged = [o.id for o in engine.available_actions("hero") if o.kind == "attack"]
    assert ranged == ["attack:improvised_thrown:goblin_1"]


def test_auto_hero_without_arrows_picks_a_melee_attack(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_ranger(registry)], rng=ScriptedRng(d20=[MISS]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")], hero_zone="hall",
    )
    set_arrows(engine, 0)
    options = engine.available_actions("hero")
    chosen = AutoHeroController(engine).choose_turn(options, "hero")
    assert chosen.startswith("attack:")
    assert "longbow" not in chosen
