# К3 П4 (docs/plan-k3.md, «Тесты» П4; решение 14): авто-жрец (combat/auto_cleric.py и
#   AutoHeroController.choose_turn). Порядок: свои действия (в том числе лечение), Благословение,
#   атакующее заклинание, оружие.
#   Лечение (pick_heal) -- только у class_id == "cleric": нуждающиеся -- умирающие герои в своей
#     зоне, затем боеспособные с половиной HP и меньше (от самого раненого); жрец тоже союзник;
#     заклинание Лечащее слово, потом Лечение ран (низший круг), нет пункта -- Божественная искра
#     (на другое существо).
#   Благословение (pick_bless): только раунд 1, без концентрации, при >= 2 других боеспособных
#     союзниках; пункт базового круга с наибольшим числом целей.
from combat_kit import (
    ScriptedRng,
    down_hero,
    make_cleric,
    make_engine,
    make_fighter,
    make_wizard,
    mon,
    set_hp,
)

from ai_dm.combat import auto_cleric
from ai_dm.combat.controllers import AutoHeroController
from ai_dm.state.combat import DecisionPoint
from ai_dm.state.creature import ResourcePool

GOBLIN = [mon("goblin_1", "goblin_warrior", "hall")]


def decide(engine, ref="cler"):
    options = engine.available_actions(ref)
    point = DecisionPoint(kind="turn_action", actor=ref, options=[o.id for o in options])
    return AutoHeroController(engine).choose(options, point)


def hp_of(engine, ref, current, maximum):
    creature = engine.creature(ref)
    creature.hp_max, creature.hp_current = maximum, current


def party(registry, cfg, *spells, allies=("ally",), monsters=GOBLIN, level=3, cantrips=()):
    hero = make_cleric(registry, level=level)
    hero.sheet.prepared_of().extend(spells)
    hero.sheet.known_of().extend(cantrips)
    friends = [make_fighter(registry, name) for name in allies]
    engine = make_engine(
        registry, cfg, heroes=[hero, *friends], monsters=monsters, rng=ScriptedRng(),
    )
    for spec in monsters:
        set_hp(engine, spec["ref"], 30)
    return engine


def options_of(engine, ref="cler"):
    return engine.available_actions(ref)


# лечение: кого

def test_dying_ally_is_healed_with_healing_word_first(registry, cfg):
    engine = party(registry, cfg, "healing_word", "cure_wounds")
    down_hero(engine, "ally")
    assert decide(engine) == "cast:healing_word:1:ally"


def test_cure_wounds_heals_when_healing_word_is_not_prepared(registry, cfg):
    engine = party(registry, cfg, "cure_wounds")
    down_hero(engine, "ally")
    assert decide(engine) == "cast:cure_wounds:1:ally"


def test_lowest_circle_of_the_healing_spell_is_chosen(registry, cfg):
    engine = party(registry, cfg, "cure_wounds")
    down_hero(engine, "ally")
    chosen = auto_cleric.pick_heal(engine, "cler", options_of(engine))
    assert chosen.startswith("cast:cure_wounds:1:")


def test_ally_at_half_hit_points_is_healed(registry, cfg):
    engine = party(registry, cfg, "healing_word")
    hp_of(engine, "ally", 6, 12)
    assert decide(engine) == "cast:healing_word:1:ally"


def test_ally_above_half_hit_points_is_not_healed(registry, cfg):
    engine = party(registry, cfg, "healing_word")
    hp_of(engine, "ally", 7, 12)
    assert auto_cleric.pick_heal(engine, "cler", options_of(engine)) is None


def test_dying_ally_goes_before_a_wounded_one(registry, cfg):
    engine = party(registry, cfg, "healing_word", allies=("ally", "ally2"))
    hp_of(engine, "ally", 1, 10)
    down_hero(engine, "ally2")
    assert decide(engine) == "cast:healing_word:1:ally2"


def test_most_wounded_ally_is_healed_first(registry, cfg):
    engine = party(registry, cfg, "healing_word", allies=("ally", "ally2"))
    hp_of(engine, "ally", 4, 10)
    hp_of(engine, "ally2", 1, 10)
    assert decide(engine) == "cast:healing_word:1:ally2"


def test_wounded_cleric_heals_himself(registry, cfg):
    engine = party(registry, cfg, "healing_word")
    hp_of(engine, "cler", 4, 10)
    assert decide(engine) == "cast:healing_word:1:cler"


def test_dying_ally_in_another_zone_is_not_needy(registry, cfg):
    engine = party(registry, cfg, "healing_word")
    down_hero(engine, "ally")
    engine.part("ally").zone_id = "balcony"
    assert auto_cleric.needy_allies(engine, "cler") == []


def test_enemies_are_never_needy(registry, cfg):
    engine = party(registry, cfg, "healing_word")
    set_hp(engine, "goblin_1", 1)
    assert auto_cleric.needy_allies(engine, "cler") == []


def test_needy_allies_list_dying_before_wounded_and_wounded_by_ratio(registry, cfg):
    engine = party(registry, cfg, allies=("a", "b", "c"))
    hp_of(engine, "a", 4, 10)
    hp_of(engine, "b", 1, 10)
    down_hero(engine, "c")
    assert auto_cleric.needy_allies(engine, "cler") == ["c", "b", "a"]


# лечение: чем

def test_divine_spark_heals_when_no_healing_spell_is_prepared(registry, cfg):
    engine = party(registry, cfg, level=2)
    hp_of(engine, "ally", 3, 12)
    assert decide(engine) == "channel:spark_heal:ally"


def test_no_spark_without_a_charge_goes_on_to_the_attack(registry, cfg):
    engine = party(registry, cfg, level=2)
    engine.heroes["cler"].creature.resources["channel_divinity"].current = 0
    hp_of(engine, "ally", 3, 12)
    assert decide(engine).startswith("attack:")


def test_healing_spell_goes_before_the_spark(registry, cfg):
    engine = party(registry, cfg, "healing_word", level=2)
    hp_of(engine, "ally", 3, 12)
    assert decide(engine) == "cast:healing_word:1:ally"


def test_cleric_without_slots_heals_with_the_spark(registry, cfg):
    engine = party(registry, cfg, "healing_word", level=2)
    for circle in (1, 2, 3):
        engine.heroes["cler"].creature.resources[f"spell_slot:{circle}"] = ResourcePool(
            current=0, max=4
        )
    down_hero(engine, "ally")
    assert decide(engine) == "channel:spark_heal:ally"


def test_wounded_cleric_alone_does_not_use_the_spark_on_himself(registry, cfg):
    engine = party(registry, cfg, allies=(), level=2)
    hp_of(engine, "cler", 3, 10)
    assert auto_cleric.pick_heal(engine, "cler", options_of(engine)) is None


def test_wizard_does_not_heal_allies_automatically(registry, cfg):
    hero = make_wizard(registry)
    hero.sheet.prepared_of().append("healing_word")
    hero.creature.resources["spell_slot:1"] = ResourcePool(current=2, max=2)
    engine = make_engine(
        registry, cfg, heroes=[hero, make_fighter(registry, "ally")], monsters=GOBLIN,
        rng=ScriptedRng(),
    )
    down_hero(engine, "ally")
    assert auto_cleric.pick_heal(engine, "wiz", options_of(engine, "wiz")) is None


def test_cheapest_picks_the_lowest_circle_and_first_on_a_tie(registry, cfg):
    engine = party(registry, cfg, "cure_wounds")
    down_hero(engine, "ally")
    casts = [
        o for o in options_of(engine)
        if o.params.get("spell") == "cure_wounds" and o.params["target"] == "ally"
    ]
    assert auto_cleric.cheapest(casts[::-1]) == "cast:cure_wounds:1:ally"


def test_cheapest_takes_the_first_option_on_a_tie(registry, cfg):
    engine = party(registry, cfg, "cure_wounds")
    down_hero(engine, "ally")
    casts = [o for o in options_of(engine) if o.params.get("spell") == "cure_wounds"]
    first, second = [o for o in casts if o.params["circle"] == 1]
    assert auto_cleric.cheapest([first, second]) == first.id


# Благословение

def bless_targets(option_id):
    return set(option_id.split(":")[3].split(","))


def test_bless_is_cast_in_round_one_on_the_whole_group(registry, cfg):
    engine = party(registry, cfg, "bless", allies=("a", "b"))
    chosen = auto_cleric.pick_bless(engine, "cler", options_of(engine))
    assert chosen.startswith("cast:bless:1:") and bless_targets(chosen) == {"cler", "a", "b"}


def test_bless_is_the_first_move_of_the_turn(registry, cfg):
    engine = party(registry, cfg, "bless", allies=("a", "b"))
    assert decide(engine).startswith("cast:bless:1:")


def test_bless_is_not_cast_with_one_other_ally(registry, cfg):
    engine = party(registry, cfg, "bless", allies=("a",))
    assert auto_cleric.pick_bless(engine, "cler", options_of(engine)) is None


def test_bless_is_not_cast_in_round_two(registry, cfg):
    engine = party(registry, cfg, "bless", allies=("a", "b"))
    engine.state.round = 2
    assert auto_cleric.pick_bless(engine, "cler", options_of(engine)) is None


def test_bless_is_not_cast_while_concentrating(registry, cfg):
    engine = party(registry, cfg, "bless", allies=("a", "b"))
    engine.perform("cler", "cast:bless:1:cler")
    engine.start_turn("cler")
    assert auto_cleric.pick_bless(engine, "cler", options_of(engine)) is None


def test_bless_does_not_count_a_downed_ally(registry, cfg):
    engine = party(registry, cfg, "bless", allies=("a", "b"))
    down_hero(engine, "b")
    assert auto_cleric.pick_bless(engine, "cler", options_of(engine)) is None


def test_bless_is_not_available_without_the_spell(registry, cfg):
    engine = party(registry, cfg, allies=("a", "b"))
    assert auto_cleric.pick_bless(engine, "cler", options_of(engine)) is None


def test_bless_uses_the_base_circle_not_the_upcast(registry, cfg):
    engine = party(registry, cfg, "bless", allies=("a", "b"))
    circles = {o.params["circle"] for o in options_of(engine) if o.params.get("spell") == "bless"}
    assert len(circles) > 1 and auto_cleric.pick_bless(
        engine, "cler", options_of(engine)
    ).startswith("cast:bless:1:")


def test_bless_picks_the_option_with_the_most_targets(registry, cfg):
    engine = party(registry, cfg, "bless", allies=("a", "b", "c"))
    chosen = auto_cleric.pick_bless(engine, "cler", options_of(engine))
    assert len(bless_targets(chosen)) == 3


def test_healing_the_dying_goes_before_bless(registry, cfg):
    engine = party(registry, cfg, "bless", "healing_word", allies=("a", "b"))
    down_hero(engine, "a")
    assert decide(engine) == "cast:healing_word:1:a"


# атака

def test_without_allies_to_bless_the_cleric_casts_sacred_flame_at_the_weakest(registry, cfg):
    monsters = [*GOBLIN, mon("goblin_2", "goblin_warrior", "hall")]
    engine = party(
        registry, cfg, "bless", allies=("a",), monsters=monsters, cantrips=["sacred_flame"]
    )
    set_hp(engine, "goblin_2", 5)
    assert decide(engine) == "cast:sacred_flame:0:goblin_2"


def test_without_spells_or_charges_the_cleric_attacks_with_a_weapon(registry, cfg):
    engine = party(registry, cfg, level=1)
    assert decide(engine).startswith("attack:") and decide(engine).endswith(":goblin_1")


# добор по выжившим мутантам П4

def test_the_lower_hit_point_ratio_is_healed_first_whatever_the_maximum(registry, cfg):
    # 4/10 = 0.4 и 5/30 = 0.17: второй раненее, хотя у него больше хит-пойнтов
    engine = party(registry, cfg, "healing_word", allies=("a", "b"))
    hp_of(engine, "a", 4, 10)
    hp_of(engine, "b", 5, 30)
    assert decide(engine) == "cast:healing_word:1:b"


def test_a_downed_monster_ally_in_the_zone_is_not_needy(registry, cfg):
    # лежачий союзник-монстр не герой: его не лечат и разбор не падает
    zombie = mon("zom", "zombie", "hall", side="heroes", group="allies")
    engine = party(registry, cfg, "healing_word", allies=(), monsters=[*GOBLIN, zombie])
    engine.part("zom").status = "down"
    assert auto_cleric.needy_allies(engine, "cler") == []
