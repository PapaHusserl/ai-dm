# К3 П4 (docs/plan-k3.md, «Тесты» П4): Божественный канал жреца в бою (combat/actions/cleric.py).
#   Группа пунктов kind="channel_divinity", id channel:<эффект>[:<цель>]; нужны умение Канала,
#   заряд пула channel_divinity, действие и благосклонность бога > -6
#   (divine.channel_divinity_blocked).
#   Божественная искра: цель -- другое существо (не сам жрец) в своей или соседней зоне; лежачего
#     можно поднять; исцеление 1d8 + Мдр; урон -- Тел, 1d8 + Мдр излучением, половина при успехе.
#   Изгнание нежити: нежить других сторон в своей и соседних зонах, Мдр; провал -- frightened +
#     incapacitated (source turn_undead, 10 раундов), любой урон по цели их снимает; 5 ур. --
#     Выжигание: один бросок Nd8 (N = max(1, Мдр)) на всех проваливших; урон Выжигания состояния
#     не снимает (SRD 5.2.1), убитый им состояний не получает.
#   Сохранение жизни (Домен жизни, 3 ур.): 5 x уровень HP самым раненым в своей зоне, каждому не
#     выше половины максимума, остаток -- следующему; нежить и конструкты мимо.
#   Жрец 2 ур.: Мдр 15 (+2), СЛ 12; 3 ур.: СЛ 12; 5 ур.: СЛ 13.
from combat_kit import (
    ScriptedRng,
    creature,
    down_hero,
    hp,
    make_cleric,
    make_engine,
    make_fighter,
    make_line,
    mon,
    option_ids,
    part,
    set_hp,
    turn,
)

from ai_dm.combat import downed
from ai_dm.rules.results import Rejected

GOBLIN = [mon("goblin_1", "goblin_warrior", "hall")]
SKELETON = [mon("skel", "skeleton", "hall")]


def engine_of(registry, cfg, hero, monsters=GOBLIN, allies=(), rng=None, **kwargs):
    engine = make_engine(
        registry, cfg, heroes=[hero, *allies], monsters=monsters, rng=rng or ScriptedRng(),
        **kwargs,
    )
    for spec in monsters:
        if spec["monster"] == "goblin_warrior":
            set_hp(engine, spec["ref"], 30)
    return engine


def ally_of(registry, ref, zone="hall", hp_current=None, hp_max=None):
    ally = make_fighter(registry, ref)
    if hp_max is not None:
        ally.creature.hp_max = hp_max
    if hp_current is not None:
        ally.creature.hp_current = hp_current
    return ally, zone


def channel(engine, ref="cler"):
    return [i for i in option_ids(engine, ref) if i.startswith("channel:")]


def conditions(engine, ref):
    return [c.id for c in creature(engine, ref).conditions]


def charges(engine):
    return engine.heroes["cler"].creature.resources["channel_divinity"].current


# меню: когда пункты есть

def test_cleric_with_ally_and_enemy_gets_both_spark_options(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry), allies=[ally_of(registry, "ally")])
    ids = channel(engine)
    assert {"channel:spark_heal:ally", "channel:spark_damage:goblin_1"} <= set(ids)


def test_spark_options_have_the_channel_kind(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry), allies=[ally_of(registry, "ally")])
    kinds = {o.kind for o in engine.available_actions("cler") if o.id.startswith("channel:")}
    assert kinds == {"channel_divinity"}


def test_no_channel_options_without_a_charge(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry, charges=0))
    assert channel(engine) == []


def test_no_channel_options_at_level_one(registry, cfg):
    # заряд в пуле есть, но умения Божественного канала у жреца 1 ур. нет
    engine = engine_of(registry, cfg, make_cleric(registry, level=1))
    assert channel(engine) == []


def test_no_channel_options_without_the_action(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry))
    turn(engine, "cler").action = False
    assert channel(engine) == []


def test_no_channel_options_at_favor_minus_six(registry, cfg):
    hero = make_cleric(registry)
    hero.deity_id = "sun"
    hero.favor["sun"] = -6
    engine = engine_of(registry, cfg, hero)
    assert channel(engine) == []


def test_channel_options_remain_at_favor_minus_five(registry, cfg):
    hero = make_cleric(registry)
    hero.deity_id = "sun"
    hero.favor["sun"] = -5
    engine = engine_of(registry, cfg, hero)
    assert channel(engine) != []


def test_fighter_has_no_channel_options(registry, cfg):
    engine = engine_of(registry, cfg, make_fighter(registry, "cler"))
    assert channel(engine) == []


# Божественная искра: кто может быть целью

def test_spark_cannot_heal_the_cleric_himself(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry), allies=[ally_of(registry, "ally")])
    assert "channel:spark_heal:cler" not in option_ids(engine, "cler")


def test_spark_heals_an_ally_in_the_adjacent_zone(registry, cfg):
    ally = ally_of(registry, "ally", zone="z1")
    engine = engine_of(
        registry, cfg, make_cleric(registry), allies=[ally], zones=make_line(4), hero_zone="z0",
        monsters=[mon("goblin_1", "goblin_warrior", "z3")],
    )
    assert "channel:spark_heal:ally" in option_ids(engine, "cler")


def test_spark_cannot_heal_an_ally_two_zones_away(registry, cfg):
    ally = ally_of(registry, "ally", zone="z2")
    engine = engine_of(
        registry, cfg, make_cleric(registry), allies=[ally], zones=make_line(4), hero_zone="z0",
        monsters=[mon("goblin_1", "goblin_warrior", "z3")],
    )
    assert "channel:spark_heal:ally" not in option_ids(engine, "cler")


def test_spark_cannot_hurt_an_enemy_two_zones_away(registry, cfg):
    engine = engine_of(
        registry, cfg, make_cleric(registry), zones=make_line(4), hero_zone="z0",
        monsters=[mon("goblin_1", "goblin_warrior", "z2")],
    )
    assert "channel:spark_damage:goblin_1" not in option_ids(engine, "cler")


def test_spark_heal_is_offered_for_a_downed_ally(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry), allies=[ally_of(registry, "ally")])
    down_hero(engine, "ally")
    assert "channel:spark_heal:ally" in option_ids(engine, "cler")


def test_spark_damage_is_not_offered_for_a_downed_enemy(registry, cfg):
    # решение 75: у героя лежачих врагов в меню нет (их добивает рассказчик), как у заклинаний
    engine = engine_of(registry, cfg, make_cleric(registry))
    set_hp(engine, "goblin_1", 0)
    part(engine, "goblin_1").status = "down"
    assert "channel:spark_damage:goblin_1" not in option_ids(engine, "cler")


def test_spark_damage_is_offered_for_a_surrendered_enemy(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry))
    part(engine, "goblin_1").status = "surrendered"
    assert "channel:spark_damage:goblin_1" in option_ids(engine, "cler")


def test_spark_damage_is_not_offered_for_a_fled_enemy(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry))
    part(engine, "goblin_1").status = "fled"
    assert "channel:spark_damage:goblin_1" not in option_ids(engine, "cler")


def test_spark_damage_is_not_offered_for_a_dead_enemy(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry))
    part(engine, "goblin_1").status = "dead"
    assert "channel:spark_damage:goblin_1" not in option_ids(engine, "cler")


# Божественная искра: исполнение

def test_spark_heal_restores_d8_plus_wisdom(registry, cfg):
    rng = ScriptedRng(d8=[5])
    engine = engine_of(
        registry, cfg, make_cleric(registry), allies=[ally_of(registry, "ally", hp_current=3)],
        rng=rng,
    )
    engine.perform("cler", "channel:spark_heal:ally")
    assert hp(engine, "ally") == 3 + 5 + 2


def test_spark_heal_never_goes_above_the_maximum(registry, cfg):
    engine = engine_of(
        registry, cfg, make_cleric(registry), allies=[ally_of(registry, "ally", hp_current=11)],
        rng=ScriptedRng(d8=[8]),
    )
    engine.perform("cler", "channel:spark_heal:ally")
    assert hp(engine, "ally") == 12


def test_spark_heal_raises_a_downed_ally(registry, cfg):
    engine = engine_of(
        registry, cfg, make_cleric(registry), allies=[ally_of(registry, "ally")],
        rng=ScriptedRng(d8=[4]),
    )
    down_hero(engine, "ally")
    engine.perform("cler", "channel:spark_heal:ally")
    assert part(engine, "ally").status == "active"


def test_spark_heal_writes_the_log_line(registry, cfg):
    engine = engine_of(
        registry, cfg, make_cleric(registry), allies=[ally_of(registry, "ally", hp_current=3)],
        rng=ScriptedRng(d8=[5]),
    )
    engine.perform("cler", "channel:spark_heal:ally")
    name = engine.name("ally")
    assert f"Божественная искра: Отец Марк лечит {name} на 7: HP 10/12" in engine.state.log


def test_spark_spends_a_charge(registry, cfg):
    engine = engine_of(
        registry, cfg, make_cleric(registry), allies=[ally_of(registry, "ally")],
        rng=ScriptedRng(d8=[4]),
    )
    engine.perform("cler", "channel:spark_heal:ally")
    assert charges(engine) == 1


def test_spark_spends_the_action(registry, cfg):
    engine = engine_of(
        registry, cfg, make_cleric(registry), allies=[ally_of(registry, "ally")],
        rng=ScriptedRng(d8=[4]),
    )
    engine.perform("cler", "channel:spark_heal:ally")
    assert turn(engine, "cler").action is False


def test_spark_is_rejected_without_a_charge(registry, cfg):
    engine = engine_of(
        registry, cfg, make_cleric(registry, charges=0), allies=[ally_of(registry, "ally")]
    )
    assert isinstance(engine.perform("cler", "channel:spark_heal:ally"), Rejected)


def test_spark_damage_failed_save_deals_full_radiant_damage(registry, cfg):
    # Тел гоблина 10 (+0): 5 < СЛ 12; 1d8 = 6, +2 Мдр
    engine = engine_of(registry, cfg, make_cleric(registry), rng=ScriptedRng(d20=[5], d8=[6]))
    engine.perform("cler", "channel:spark_damage:goblin_1")
    assert hp(engine, "goblin_1") == 30 - 8


def test_spark_damage_passed_save_halves_the_damage(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry), rng=ScriptedRng(d20=[18], d8=[6]))
    engine.perform("cler", "channel:spark_damage:goblin_1")
    assert hp(engine, "goblin_1") == 30 - 4


def test_spark_damage_writes_the_log_line(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry), rng=ScriptedRng(d20=[5], d8=[6]))
    engine.perform("cler", "channel:spark_damage:goblin_1")
    assert f"Отец Марк: Божественная искра → {engine.name('goblin_1')}" in engine.state.log


def test_spark_damage_returns_an_attack_event(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry), rng=ScriptedRng(d20=[5], d8=[6]))
    events = engine.perform("cler", "channel:spark_damage:goblin_1")
    assert events[0].type == "attack"
    assert events[0].data == {
        "attacker": "cler", "target": "goblin_1", "weapon": "divine_spark", "mode": "spell",
        "outcome": "auto", "damage": 8,
    }


def test_spark_damage_spends_a_charge_and_the_action(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry), rng=ScriptedRng(d20=[5], d8=[6]))
    engine.perform("cler", "channel:spark_damage:goblin_1")
    assert (charges(engine), turn(engine, "cler").action) == (1, False)


# Изгнание нежити

def test_turn_undead_is_offered_when_undead_is_in_the_zone(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry), monsters=SKELETON)
    assert "channel:turn_undead" in option_ids(engine, "cler")


def test_turn_undead_is_offered_for_undead_in_the_adjacent_zone(registry, cfg):
    engine = engine_of(
        registry, cfg, make_cleric(registry), zones=make_line(4), hero_zone="z0",
        monsters=[mon("skel", "skeleton", "z1")],
    )
    assert "channel:turn_undead" in option_ids(engine, "cler")


def test_turn_undead_is_not_offered_for_undead_two_zones_away(registry, cfg):
    engine = engine_of(
        registry, cfg, make_cleric(registry), zones=make_line(4), hero_zone="z0",
        monsters=[mon("skel", "skeleton", "z2")],
    )
    assert "channel:turn_undead" not in option_ids(engine, "cler")


def test_turn_undead_is_not_offered_against_living_enemies(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry))
    assert "channel:turn_undead" not in option_ids(engine, "cler")


def test_turn_undead_is_not_offered_for_a_downed_undead(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry), monsters=SKELETON)
    part(engine, "skel").status = "down"
    assert "channel:turn_undead" not in option_ids(engine, "cler")


def test_turn_undead_failed_save_frightens_and_incapacitates(registry, cfg):
    # Мдр скелета 8 (-1): 2 - 1 < СЛ 12
    engine = engine_of(registry, cfg, make_cleric(registry), monsters=SKELETON,
                       rng=ScriptedRng(d20=[2]))
    engine.perform("cler", "channel:turn_undead")
    assert sorted(conditions(engine, "skel")) == ["frightened", "incapacitated"]


def test_turn_undead_conditions_come_from_turn_undead_for_ten_rounds(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry), monsters=SKELETON,
                       rng=ScriptedRng(d20=[2]))
    engine.perform("cler", "channel:turn_undead")
    held = creature(engine, "skel").conditions
    found = {(c.source, c.expires.kind, c.expires.value) for c in held}
    assert found == {("turn_undead", "rounds", 10)}


def test_turn_undead_passed_save_does_nothing(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry), monsters=SKELETON,
                       rng=ScriptedRng(d20=[20]))
    engine.perform("cler", "channel:turn_undead")
    assert conditions(engine, "skel") == []


def test_turn_undead_does_not_touch_a_living_goblin(registry, cfg):
    monsters = [*SKELETON, mon("goblin_1", "goblin_warrior", "hall")]
    engine = engine_of(registry, cfg, make_cleric(registry), monsters=monsters,
                       rng=ScriptedRng(d20=[2]))
    engine.perform("cler", "channel:turn_undead")
    assert conditions(engine, "goblin_1") == []


def test_turn_undead_spends_a_charge_and_the_action(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry), monsters=SKELETON,
                       rng=ScriptedRng(d20=[2]))
    engine.perform("cler", "channel:turn_undead")
    assert (charges(engine), turn(engine, "cler").action) == (1, False)


def test_turn_undead_does_not_deal_damage_before_level_five(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry), monsters=SKELETON,
                       rng=ScriptedRng(d20=[2]))
    engine.perform("cler", "channel:turn_undead")
    assert hp(engine, "skel") == 13


def test_damage_after_turn_undead_ends_the_effect(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry), monsters=SKELETON,
                       rng=ScriptedRng(d20=[2]))
    engine.perform("cler", "channel:turn_undead")
    dealt = engine.damage("skel", 3, "bludgeoning")
    downed.after_damage(engine, "skel", dealt, "cler")
    assert conditions(engine, "skel") == []


# Выжигание нежити (5 ур.)

def test_sear_undead_deals_wisdom_d8_radiant_damage_to_the_failed(registry, cfg):
    # Мдр +2 -> 2d8 = 3 + 4
    hero = make_cleric(registry, level=5)
    engine = engine_of(registry, cfg, hero, monsters=SKELETON, rng=ScriptedRng(d20=[2], d8=[3, 4]))
    engine.perform("cler", "channel:turn_undead")
    assert hp(engine, "skel") == 13 - 7


def test_sear_undead_does_not_end_the_turn_effect(registry, cfg):
    hero = make_cleric(registry, level=5)
    engine = engine_of(registry, cfg, hero, monsters=SKELETON, rng=ScriptedRng(d20=[2], d8=[3, 4]))
    engine.perform("cler", "channel:turn_undead")
    assert sorted(conditions(engine, "skel")) == ["frightened", "incapacitated"]


def test_damage_after_sear_undead_ends_the_effect(registry, cfg):
    hero = make_cleric(registry, level=5)
    engine = engine_of(registry, cfg, hero, monsters=SKELETON, rng=ScriptedRng(d20=[2], d8=[3, 4]))
    engine.perform("cler", "channel:turn_undead")
    dealt = engine.damage("skel", 1, "bludgeoning")
    downed.after_damage(engine, "skel", dealt, "cler")
    assert conditions(engine, "skel") == []


def test_sear_undead_is_rolled_once_for_all_failed_undead(registry, cfg):
    # на два скелета ровно одна очередь 2d8: лишний бросок -- AssertionError ScriptedRng
    hero = make_cleric(registry, level=5)
    monsters = [mon("skel", "skeleton", "hall"), mon("skel2", "skeleton", "hall")]
    engine = engine_of(registry, cfg, hero, monsters=monsters,
                       rng=ScriptedRng(d20=[2, 2], d8=[3, 4]))
    engine.perform("cler", "channel:turn_undead")
    assert (hp(engine, "skel"), hp(engine, "skel2")) == (6, 6)


def test_sear_undead_spares_those_who_passed_the_save(registry, cfg):
    hero = make_cleric(registry, level=5)
    engine = engine_of(registry, cfg, hero, monsters=SKELETON,
                       rng=ScriptedRng(d20=[20], d8=[3, 4]))
    engine.perform("cler", "channel:turn_undead")
    assert hp(engine, "skel") == 13


def test_sear_undead_dice_count_is_at_least_one(registry, cfg):
    # Мдр 8 (-1) -> одна кость; в очереди одна грань
    hero = make_cleric(registry, level=5)
    hero.sheet.abilities["wis"] = 8
    engine = engine_of(registry, cfg, hero, monsters=SKELETON, rng=ScriptedRng(d20=[2], d8=[5]))
    engine.perform("cler", "channel:turn_undead")
    assert hp(engine, "skel") == 13 - 5


def test_undead_killed_by_sear_gets_no_conditions(registry, cfg):
    hero = make_cleric(registry, level=5)
    engine = engine_of(registry, cfg, hero, monsters=SKELETON, rng=ScriptedRng(d20=[2], d8=[3, 4]))
    set_hp(engine, "skel", 5)
    engine.perform("cler", "channel:turn_undead")
    assert conditions(engine, "skel") == []


# Сохранение жизни

def life_engine(registry, cfg, allies, level=3, monsters=GOBLIN, **kwargs):
    hero = make_cleric(registry, level=level, subclass="life_domain")
    return engine_of(registry, cfg, hero, monsters=monsters, allies=allies, **kwargs)


def test_preserve_life_is_offered_with_a_wounded_ally_in_the_zone(registry, cfg):
    engine = life_engine(registry, cfg, [ally_of(registry, "ally", hp_current=2, hp_max=10)])
    assert "channel:preserve_life" in option_ids(engine, "cler")


def test_preserve_life_is_not_offered_without_the_life_domain(registry, cfg):
    hero = make_cleric(registry, level=3)
    ally = ally_of(registry, "ally", hp_current=2, hp_max=10)
    engine = engine_of(registry, cfg, hero, allies=[ally])
    assert "channel:preserve_life" not in option_ids(engine, "cler")


def test_preserve_life_is_not_offered_when_everyone_is_above_half(registry, cfg):
    engine = life_engine(registry, cfg, [ally_of(registry, "ally", hp_current=6, hp_max=12)])
    assert "channel:preserve_life" not in option_ids(engine, "cler")


def test_preserve_life_is_not_offered_for_a_wounded_ally_in_another_zone(registry, cfg):
    ally = ally_of(registry, "ally", zone="balcony", hp_current=2, hp_max=10)
    engine = life_engine(registry, cfg, [ally])
    assert "channel:preserve_life" not in option_ids(engine, "cler")


def test_preserve_life_is_not_offered_for_a_wounded_undead_ally(registry, cfg):
    zombie = mon("zom", "zombie", "hall", side="heroes", group="allies")
    engine = life_engine(registry, cfg, [], monsters=[*GOBLIN, zombie])
    set_hp(engine, "zom", 1)
    assert "channel:preserve_life" not in option_ids(engine, "cler")


def test_preserve_life_heals_up_to_half_of_the_maximum_only(registry, cfg):
    # 15 HP на 3 ур.: союзник 2/10 -> 5 (+3); союзник 6/12 уже на половине -- ничего
    allies = [
        ally_of(registry, "a", hp_current=2, hp_max=10),
        ally_of(registry, "b", hp_current=6, hp_max=12),
    ]
    engine = life_engine(registry, cfg, allies)
    engine.perform("cler", "channel:preserve_life")
    assert (hp(engine, "a"), hp(engine, "b")) == (5, 6)


def test_preserve_life_leftover_goes_to_the_next_wounded(registry, cfg):
    # самый раненый c 1/30 берёт 14 (до 15), остаток 1 -- у a 2/10 -> 3
    allies = [
        ally_of(registry, "a", hp_current=2, hp_max=10),
        ally_of(registry, "c", hp_current=1, hp_max=30),
    ]
    engine = life_engine(registry, cfg, allies)
    engine.perform("cler", "channel:preserve_life")
    assert (hp(engine, "c"), hp(engine, "a")) == (15, 3)


def test_preserve_life_pool_is_five_per_cleric_level(registry, cfg):
    # 5 ур.: 25 HP; c 1/60 -> 25 + 1 = лечение ограничено половиной (30), берёт 25
    ally = ally_of(registry, "c", hp_current=1, hp_max=60)
    engine = life_engine(registry, cfg, [ally], level=5)
    engine.perform("cler", "channel:preserve_life")
    assert hp(engine, "c") == 26


def test_preserve_life_does_not_heal_the_cleric_above_half_either(registry, cfg):
    hero = make_cleric(registry, level=3, subclass="life_domain")
    hero.creature.hp_max, hero.creature.hp_current = 20, 3
    ally = ally_of(registry, "a", hp_current=1, hp_max=10)
    engine = engine_of(registry, cfg, hero, allies=[ally])
    engine.perform("cler", "channel:preserve_life")
    assert hp(engine, "cler") == 10


def test_preserve_life_logs_each_healed_ally(registry, cfg):
    engine = life_engine(registry, cfg, [ally_of(registry, "a", hp_current=2, hp_max=10)])
    engine.perform("cler", "channel:preserve_life")
    assert f"Сохранение жизни: {engine.name('a')} +3" in engine.state.log


def test_preserve_life_raises_a_downed_ally(registry, cfg):
    engine = life_engine(registry, cfg, [ally_of(registry, "a", hp_max=10)])
    down_hero(engine, "a")
    engine.perform("cler", "channel:preserve_life")
    assert (part(engine, "a").status, hp(engine, "a")) == ("active", 5)


def test_preserve_life_spends_a_charge_and_the_action(registry, cfg):
    engine = life_engine(registry, cfg, [ally_of(registry, "a", hp_current=2, hp_max=10)])
    engine.perform("cler", "channel:preserve_life")
    assert (charges(engine), turn(engine, "cler").action) == (1, False)


# добор по выжившим мутантам П4 (меню)

def option_of(engine, option_id, ref="cler"):
    return [o for o in engine.available_actions(ref) if o.id == option_id][0]


def test_one_charge_is_enough_for_the_channel_options(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry, charges=1))
    assert "channel:spark_damage:goblin_1" in channel(engine)


def test_spark_damage_is_offered_for_an_enemy_in_the_adjacent_zone(registry, cfg):
    engine = engine_of(
        registry, cfg, make_cleric(registry), zones=make_line(4), hero_zone="z0",
        monsters=[mon("goblin_1", "goblin_warrior", "z1")],
    )
    assert "channel:spark_damage:goblin_1" in option_ids(engine, "cler")


def test_spark_damage_option_names_the_effect_and_the_target(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry))
    option = option_of(engine, "channel:spark_damage:goblin_1")
    assert option.params == {"effect": "spark_damage", "target": "goblin_1"}


def test_turn_undead_option_label(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry), monsters=SKELETON)
    assert option_of(engine, "channel:turn_undead").label == "Изгнание нежити"


def test_preserve_life_option_label(registry, cfg):
    engine = life_engine(registry, cfg, [ally_of(registry, "a", hp_current=2, hp_max=10)])
    assert option_of(engine, "channel:preserve_life").label == "Сохранение жизни"


def test_preserve_life_looks_past_an_ally_in_another_zone(registry, cfg):
    # союзник другой зоны стоит в списке раньше раненого в зоне жреца
    allies = [
        ally_of(registry, "far", zone="balcony", hp_current=1, hp_max=10),
        ally_of(registry, "near", hp_current=2, hp_max=10),
    ]
    engine = life_engine(registry, cfg, allies)
    assert "channel:preserve_life" in option_ids(engine, "cler")


def test_preserve_life_is_not_offered_for_an_ally_at_the_rounded_down_half(registry, cfg):
    # 5/11: половина максимума с округлением вниз -- 5, добавить цели нечего
    engine = life_engine(registry, cfg, [ally_of(registry, "a", hp_current=5, hp_max=11)])
    assert "channel:preserve_life" not in option_ids(engine, "cler")


def test_preserve_life_heals_an_ally_just_below_half(registry, cfg):
    # 5/12 меньше половины (6): лечится на 1
    engine = life_engine(registry, cfg, [ally_of(registry, "a", hp_current=5, hp_max=12)])
    engine.perform("cler", "channel:preserve_life")
    assert hp(engine, "a") == 6


def test_preserve_life_stops_when_the_pool_is_spent_exactly(registry, cfg):
    # 15 HP целиком уходят первому (1/32 -> 16); второй раненый получает не «+0», а ничего
    allies = [
        ally_of(registry, "c", hp_current=1, hp_max=32),
        ally_of(registry, "a", hp_current=2, hp_max=10),
    ]
    engine = life_engine(registry, cfg, allies)
    engine.perform("cler", "channel:preserve_life")
    assert f"Сохранение жизни: {engine.name('a')} +0" not in engine.state.log


# добор по выжившим мутантам П4 (Искра: исцеление)

def test_the_last_charge_is_spent_by_the_spark(registry, cfg):
    engine = engine_of(
        registry, cfg, make_cleric(registry, charges=1), rng=ScriptedRng(d20=[5], d8=[6])
    )
    engine.perform("cler", "channel:spark_damage:goblin_1")
    assert charges(engine) == 0


def weak_wisdom_cleric(registry):
    # Мдр 8 (-1): исцеление 1d8 - 1
    hero = make_cleric(registry)
    hero.sheet.abilities["wis"] = 8
    return hero


def test_spark_heal_cannot_be_negative(registry, cfg):
    # 1d8 = 1, Мдр -1: лечение 0, а не 1
    engine = engine_of(
        registry, cfg, weak_wisdom_cleric(registry),
        allies=[ally_of(registry, "ally", hp_current=3)], rng=ScriptedRng(d8=[1]),
    )
    engine.perform("cler", "channel:spark_heal:ally")
    assert hp(engine, "ally") == 3


def test_spark_heal_of_zero_leaves_a_downed_ally_down(registry, cfg):
    engine = engine_of(
        registry, cfg, weak_wisdom_cleric(registry), allies=[ally_of(registry, "ally")],
        rng=ScriptedRng(d8=[1]),
    )
    down_hero(engine, "ally")
    engine.perform("cler", "channel:spark_heal:ally")
    assert (part(engine, "ally").status, hp(engine, "ally")) == ("down", 0)


def test_spark_heal_of_one_point_raises_a_downed_ally(registry, cfg):
    # 1d8 = 2, Мдр -1: ровно 1 HP, и этого достаточно
    engine = engine_of(
        registry, cfg, weak_wisdom_cleric(registry), allies=[ally_of(registry, "ally")],
        rng=ScriptedRng(d8=[2]),
    )
    down_hero(engine, "ally")
    engine.perform("cler", "channel:spark_heal:ally")
    assert (part(engine, "ally").status, hp(engine, "ally")) == ("active", 1)


# добор по выжившим мутантам П4 (Искра: урон)

def test_spark_damage_writes_the_damage_roll_line(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry), rng=ScriptedRng(d20=[5], d8=[6]))
    engine.perform("cler", "channel:spark_damage:goblin_1")
    assert "  Урон (Божественная искра): 1d8 (6) + 2 Мдр = 8 излучением" in engine.state.log


def test_spark_damage_writes_the_hit_points_line(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry), rng=ScriptedRng(d20=[5], d8=[6]))
    engine.perform("cler", "channel:spark_damage:goblin_1")
    assert f"  {engine.name('goblin_1')}: {engine.hp_text('goblin_1')}" in engine.state.log


def test_spark_damage_halves_an_odd_total_rounding_down(registry, cfg):
    # 1d8 = 5, +2 = 7; успех -- 3, целое число
    engine = engine_of(registry, cfg, make_cleric(registry), rng=ScriptedRng(d20=[18], d8=[5]))
    engine.perform("cler", "channel:spark_damage:goblin_1")
    assert hp(engine, "goblin_1") == 30 - 3


def test_spark_damage_kill_is_credited_to_the_cleric(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry), rng=ScriptedRng(d20=[5], d8=[6]))
    set_hp(engine, "goblin_1", 3)
    engine.perform("cler", "channel:spark_damage:goblin_1")
    assert (part(engine, "goblin_1").status, part(engine, "goblin_1").last_hit_by) == (
        "dead", "cler",
    )


def test_spark_damage_is_radiant_so_undead_fortitude_does_not_help(registry, cfg):
    # зомби на 1 HP: от излучения Стойкость нежити не спасает (в очереди нет d20 на её спасбросок)
    monsters = [mon("zom", "zombie", "hall")]
    engine = engine_of(registry, cfg, make_cleric(registry), monsters=monsters,
                       rng=ScriptedRng(d20=[2], d8=[6]))
    set_hp(engine, "zom", 1)
    engine.perform("cler", "channel:spark_damage:zom")
    assert part(engine, "zom").status == "dead"


# добор по выжившим мутантам П4 (Изгнание нежити)

def test_turn_undead_writes_the_cast_line(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry), monsters=SKELETON,
                       rng=ScriptedRng(d20=[2]))
    engine.perform("cler", "channel:turn_undead")
    assert "Отец Марк: Изгнание нежити" in engine.state.log


def test_turn_undead_writes_a_line_for_the_one_who_resisted(registry, cfg):
    engine = engine_of(registry, cfg, make_cleric(registry), monsters=SKELETON,
                       rng=ScriptedRng(d20=[20]))
    engine.perform("cler", "channel:turn_undead")
    assert f"Изгнание нежити: {engine.name('skel')} устоял" in engine.state.log


def test_turn_undead_goes_on_to_the_next_undead_after_one_resisted(registry, cfg):
    monsters = [mon("skel", "skeleton", "hall"), mon("skel2", "skeleton", "hall")]
    engine = engine_of(registry, cfg, make_cleric(registry), monsters=monsters,
                       rng=ScriptedRng(d20=[20, 2]))
    engine.perform("cler", "channel:turn_undead")
    assert sorted(conditions(engine, "skel2")) == ["frightened", "incapacitated"]


def sear_engine(registry, cfg, monsters=SKELETON, d20=(2,), d8=(3, 4)):
    hero = make_cleric(registry, level=5)
    rng = ScriptedRng(d20=list(d20), d8=list(d8))
    return engine_of(registry, cfg, hero, monsters=monsters, rng=rng)


def test_sear_undead_writes_the_dice_line(registry, cfg):
    # Мдр +2 -> 2d8 = 3 + 4
    engine = sear_engine(registry, cfg)
    engine.perform("cler", "channel:turn_undead")
    assert "Выжигание нежити: 2d8 = 7" in engine.state.log


def test_sear_undead_writes_the_hit_points_line(registry, cfg):
    engine = sear_engine(registry, cfg)
    engine.perform("cler", "channel:turn_undead")
    assert f"  {engine.name('skel')}: {engine.hp_text('skel')}" in engine.state.log


def test_sear_undead_is_radiant_so_undead_fortitude_does_not_help(registry, cfg):
    # зомби на 1 HP: в очереди нет d20 на Стойкость нежити, от излучения она не срабатывает
    engine = sear_engine(registry, cfg, monsters=[mon("zom", "zombie", "hall")])
    set_hp(engine, "zom", 1)
    engine.perform("cler", "channel:turn_undead")
    assert part(engine, "zom").status == "dead"


def test_sear_undead_kill_is_credited_to_the_cleric(registry, cfg):
    engine = sear_engine(registry, cfg)
    set_hp(engine, "skel", 5)
    engine.perform("cler", "channel:turn_undead")
    assert (part(engine, "skel").status, part(engine, "skel").last_hit_by) == ("dead", "cler")


def test_sear_undead_reports_every_undead_it_killed(registry, cfg):
    monsters = [mon("skel", "skeleton", "hall"), mon("skel2", "skeleton", "hall")]
    engine = sear_engine(registry, cfg, monsters=monsters, d20=(2, 2))
    set_hp(engine, "skel", 1)
    set_hp(engine, "skel2", 1)
    events = engine.perform("cler", "channel:turn_undead")
    assert [e.type for e in events].count("monster_died") == 2
