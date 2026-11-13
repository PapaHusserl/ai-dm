# К3б П3 (docs/plan-k3b.md, «Тесты» П3, решения 6, 7, 12): состояния, дыхание, развеивание в бою.
#   Внушение (решение 6): Мдр провал -- charmed и incapacitated, ход цели -- только «Закончить ход»;
#     урон снимает («боль прерывает»); концентрация кончилась -- состояния сняты.
#   Успокоение чувств: в зоне союзнику снимаются charmed и frightened, врагу Хар провал --
#     charmed и incapacitated до урона.
#   Призрачная сила: Инт провал -- эффект burn, в начале хода цели 1d6 психического (engine.burn),
#     в логе имя заклинания; конец концентрации -- урона нет.
#   Дыхание дракона (решение 12): на себя с вариантом из пяти типов (кислота, холод, огонь,
#     электричество, яд) -- у носителя пункт «Дыхание дракона (<тип>) → <зона>» на свою и соседнюю
#     зону, тратит действие; у каждого в конусе Лов СЛ, 3d6 выбранного типа, при успехе половина;
#     концентрация кончилась -- пункта нет.
#   Верный удар: атака оружием с бонусом заклинаний (Инт, не Сил); на 5 уровне +1d6 излучением.
#   Развеивание (решение 7): эффекты и состояния заклинаний ≤ 3 круга на цели или в зоне снимаются
#     сами, концентрация источника кончается; выше -- проверка Инт против СЛ 10 + круг.
#   Герой -- волшебник из test_cast_p3a.mage (ячейки 1-3 круга, СЛ 13, Инт +3, атака +5).
import pytest
from combat_kit import (
    ScriptedRng,
    creature,
    custom_registry,
    feature,
    give_weapon,
    hp,
    make_fighter,
    make_line,
    make_zones,
    mon,
    option_ids,
    set_hp,
)
from test_cast_p3a import (
    GOBLIN,
    TWO_GOBLINS,
    cast_ids,
    conditions,
    effects,
    engine_of,
    idle,
    mage,
    pass_turns,
    slot,
)
from test_k3b_p1_zones_defense import dark_engine, do_cast, log_has
from test_k3b_p2_tempo_images_motion import cast_variant, hall_engine, turn

from ai_dm.combat import downed
from ai_dm.combat.zone_effects import zone_effects
from ai_dm.rules.inventory import count_item, remove_item
from ai_dm.rules.modifiers.base import Modifier
from ai_dm.rules.results import Rejected
from ai_dm.state.creature import ActiveEffect, AppliedCondition, Concentration, Expiry

STAFF = "attack:quarterstaff:goblin_1"
BREATH_TYPES = ["acid", "cold", "fire", "lightning", "poison"]


def hurt(engine, ref, amount=3):
    # урон по цели, как после удара: снимает заклинания «до урона»
    dealt = engine.damage(ref, amount, "fire")
    downed.after_damage(engine, ref, dealt, "wiz")


# Внушение

def suggested(registry, cfg, d20):
    engine = hall_engine(registry, cfg, ScriptedRng(d20=d20), "suggestion")
    do_cast(engine, "wiz", "suggestion", "goblin_1")
    return engine


def test_suggestion_failed_save_charms_the_target(registry, cfg):
    engine = suggested(registry, cfg, [3])
    assert "charmed" in conditions(engine, "goblin_1")


def test_suggestion_failed_save_makes_the_target_incapacitated(registry, cfg):
    engine = suggested(registry, cfg, [3])
    assert "incapacitated" in conditions(engine, "goblin_1")


def test_suggestion_passed_save_leaves_the_target_free(registry, cfg):
    engine = suggested(registry, cfg, [18])
    assert conditions(engine, "goblin_1") == []


def test_suggestion_spends_the_slot_and_holds_the_concentration(registry, cfg):
    engine = suggested(registry, cfg, [18])
    assert slot(engine, 2) == 2
    assert creature(engine, "wiz").concentration.spell_id == "suggestion"


def test_suggested_monster_has_only_end_turn(registry, cfg):
    engine = suggested(registry, cfg, [3])
    engine.start_turn("goblin_1")
    assert option_ids(engine, "goblin_1") == ["end_turn"]


def test_damage_ends_the_suggestion_charm(registry, cfg):
    engine = suggested(registry, cfg, [3])
    hurt(engine, "goblin_1")
    assert "charmed" not in conditions(engine, "goblin_1")


def test_damage_ends_the_suggestion_incapacitation(registry, cfg):
    engine = suggested(registry, cfg, [3])
    hurt(engine, "goblin_1")
    assert "incapacitated" not in conditions(engine, "goblin_1")


def test_suggestion_ends_with_the_concentration(registry, cfg):
    engine = suggested(registry, cfg, [3])
    engine.drop_concentration_effects("wiz")
    assert conditions(engine, "goblin_1") == []


# Успокоение чувств

def calm_engine(registry, cfg, d20):
    ally = make_fighter(registry, "ally")
    engine = hall_engine(registry, cfg, ScriptedRng(d20=d20), "calm_emotions", extra=[ally])
    return engine


def afflict(engine, ref, *ids):
    for condition in ids:
        creature(engine, ref).conditions.append(AppliedCondition(id=condition, source="goblin_1"))


def test_calm_emotions_removes_fear_from_an_ally_in_the_zone(registry, cfg):
    # враг в зале тоже бросает Хар (SRD: режим на каждое существо) -- d20 18, он прошёл
    engine = calm_engine(registry, cfg, [18])
    afflict(engine, "ally", "frightened")
    do_cast(engine, "wiz", "calm_emotions", "hall")
    assert "frightened" not in conditions(engine, "ally")


def test_calm_emotions_removes_charm_from_an_ally_in_the_zone(registry, cfg):
    engine = calm_engine(registry, cfg, [18])
    afflict(engine, "ally", "charmed")
    do_cast(engine, "wiz", "calm_emotions", "hall")
    assert "charmed" not in conditions(engine, "ally")


def test_calm_emotions_leaves_other_conditions_of_an_ally(registry, cfg):
    engine = calm_engine(registry, cfg, [18])
    afflict(engine, "ally", "frightened", "prone")
    do_cast(engine, "wiz", "calm_emotions", "hall")
    assert conditions(engine, "ally") == ["prone"]


def test_calm_emotions_frees_the_frightened_ally_while_the_enemy_fails_its_save(registry, cfg):
    engine = calm_engine(registry, cfg, [3])
    afflict(engine, "ally", "frightened")
    do_cast(engine, "wiz", "calm_emotions", "hall")
    assert "frightened" not in conditions(engine, "ally")


def test_calm_emotions_makes_the_enemy_incapacitated_beside_a_frightened_ally(registry, cfg):
    engine = calm_engine(registry, cfg, [3])
    afflict(engine, "ally", "frightened")
    do_cast(engine, "wiz", "calm_emotions", "hall")
    assert "incapacitated" in conditions(engine, "goblin_1")


def test_calm_emotions_makes_the_enemy_roll_beside_a_frightened_ally(registry, cfg):
    rng = ScriptedRng(d20=[18])
    ally = make_fighter(registry, "ally")
    engine = hall_engine(registry, cfg, rng, "calm_emotions", extra=[ally])
    afflict(engine, "ally", "frightened")
    do_cast(engine, "wiz", "calm_emotions", "hall")
    assert rng.left("d20") == 0


def test_calm_emotions_frees_the_caster_in_the_zone(registry, cfg):
    engine = calm_engine(registry, cfg, [18])
    afflict(engine, "wiz", "frightened")
    do_cast(engine, "wiz", "calm_emotions", "hall")
    assert "frightened" not in conditions(engine, "wiz")


def test_calm_emotions_logs_what_it_removed_from_an_ally(registry, cfg):
    # решение 33: строка как у лечащих -- «<заклинатель>: <заклинание> снимает с <имя>: …»
    engine = calm_engine(registry, cfg, [18])
    afflict(engine, "ally", "frightened")
    do_cast(engine, "wiz", "calm_emotions", "hall")
    assert log_has(engine, "Усмирение чувств снимает с", engine.name("ally"))


def test_calm_emotions_failed_charisma_save_charms_the_enemy(registry, cfg):
    engine = calm_engine(registry, cfg, [3])
    do_cast(engine, "wiz", "calm_emotions", "hall")
    assert "charmed" in conditions(engine, "goblin_1")


def test_calm_emotions_failed_charisma_save_makes_the_enemy_incapacitated(registry, cfg):
    engine = calm_engine(registry, cfg, [3])
    do_cast(engine, "wiz", "calm_emotions", "hall")
    assert "incapacitated" in conditions(engine, "goblin_1")


def test_calm_emotions_passed_save_leaves_the_enemy_alone(registry, cfg):
    engine = calm_engine(registry, cfg, [18])
    do_cast(engine, "wiz", "calm_emotions", "hall")
    assert conditions(engine, "goblin_1") == []


def test_calmed_enemy_wakes_from_damage(registry, cfg):
    engine = calm_engine(registry, cfg, [3])
    do_cast(engine, "wiz", "calm_emotions", "hall")
    hurt(engine, "goblin_1")
    assert conditions(engine, "goblin_1") == []


def test_calm_emotions_holds_the_concentration(registry, cfg):
    engine = calm_engine(registry, cfg, [18])
    do_cast(engine, "wiz", "calm_emotions", "hall")
    assert creature(engine, "wiz").concentration.spell_id == "calm_emotions"


# Призрачная сила

def phantom_engine(registry, cfg, rng):
    engine = hall_engine(registry, cfg, rng, "phantasmal_force")
    do_cast(engine, "wiz", "phantasmal_force", "goblin_1")
    return engine


def test_phantasmal_force_failed_save_leaves_a_burn_effect(registry, cfg):
    engine = phantom_engine(registry, cfg, ScriptedRng(d20=[3]))
    assert [e.kind for e in effects(engine, "goblin_1", "phantasmal_force")] == ["burn"]


def test_phantasmal_force_passed_save_leaves_no_effect(registry, cfg):
    engine = phantom_engine(registry, cfg, ScriptedRng(d20=[18]))
    assert effects(engine, "goblin_1", "phantasmal_force") == []


def test_phantasmal_force_burns_at_the_start_of_the_targets_turn(registry, cfg):
    engine = phantom_engine(registry, cfg, ScriptedRng(d20=[3], d6=[4]))
    engine.start_turn("goblin_1")
    assert hp(engine, "goblin_1") == 26


def test_phantasmal_force_burns_every_turn(registry, cfg):
    engine = phantom_engine(registry, cfg, ScriptedRng(d20=[3], d6=[4, 2]))
    engine.start_turn("goblin_1")
    engine.start_turn("goblin_1")
    assert hp(engine, "goblin_1") == 24


def test_phantasmal_force_log_names_the_spell_and_the_damage_type(registry, cfg):
    engine = phantom_engine(registry, cfg, ScriptedRng(d20=[3], d6=[4]))
    engine.start_turn("goblin_1")
    assert log_has(engine, "Призрачная сила", "психическ")


def test_phantasmal_force_passed_save_does_not_burn(registry, cfg):
    # d6 в очереди нет: бросок урона уронил бы тест
    engine = phantom_engine(registry, cfg, ScriptedRng(d20=[18]))
    engine.start_turn("goblin_1")
    assert hp(engine, "goblin_1") == 30


def test_phantasmal_force_stops_when_the_concentration_ends(registry, cfg):
    engine = phantom_engine(registry, cfg, ScriptedRng(d20=[3]))
    engine.drop_concentration_effects("wiz")
    engine.start_turn("goblin_1")
    assert hp(engine, "goblin_1") == 30


# Дыхание дракона

def breath_engine(registry, cfg, rng, monsters=GOBLIN, reg=None, variant="fire", **kwargs):
    reg = reg or registry
    engine = engine_of(reg, cfg, mage(reg, "dragons_breath"), rng, monsters=monsters, **kwargs)
    cast_variant(engine, "wiz", "dragons_breath", "wiz", variant)
    return engine


def breath_items(engine):
    return [
        o for o in engine.available_actions("wiz")
        if o.id.startswith("breath:") and "Дыхание дракона" in o.label
    ]


def exhale(engine, zone_name="Центр зала"):
    found = [o for o in breath_items(engine) if zone_name in o.label]
    assert found, f"нет пункта выдоха в «{zone_name}»: {[o.label for o in breath_items(engine)]}"
    assert not isinstance(engine.perform("wiz", found[0].id), Rejected)


def test_dragons_breath_offers_five_types_to_the_caster(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "dragons_breath"))
    ids = cast_ids(engine, "dragons_breath")
    assert sorted(i.rsplit(":", 1)[1] for i in ids) == BREATH_TYPES
    assert all(":wiz:v:" in i for i in ids)


def test_dragons_breath_spends_the_slot_and_holds_the_concentration(registry, cfg):
    engine = breath_engine(registry, cfg, ScriptedRng())
    assert slot(engine, 2) == 2
    assert creature(engine, "wiz").concentration.spell_id == "dragons_breath"


def test_breath_option_is_absent_before_the_spell(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "dragons_breath"))
    assert breath_items(engine) == []


def test_breath_option_names_the_type_and_the_neighbour_zone(registry, cfg):
    engine = breath_engine(registry, cfg, ScriptedRng())
    labels = [o.label for o in breath_items(engine) if "Центр зала" in o.label]
    assert len(labels) == 1
    assert "огонь" in labels[0]


def test_breath_option_covers_the_own_zone_too(registry, cfg):
    engine = breath_engine(registry, cfg, ScriptedRng())
    assert [o for o in breath_items(engine) if "У двери" in o.label]


def test_breath_option_is_absent_for_a_far_zone(registry, cfg):
    engine = breath_engine(registry, cfg, ScriptedRng())
    assert not [o for o in breath_items(engine) if "Балкон" in o.label]


def test_breath_option_goes_away_with_the_concentration(registry, cfg):
    engine = breath_engine(registry, cfg, ScriptedRng())
    engine.drop_concentration_effects("wiz")
    assert breath_items(engine) == []


def test_breath_failed_save_deals_full_3d6(registry, cfg):
    engine = breath_engine(registry, cfg, ScriptedRng(d20=[3], d6=[4, 4, 4]))
    exhale(engine)
    assert hp(engine, "goblin_1") == 18


def test_breath_passed_save_deals_half(registry, cfg):
    engine = breath_engine(registry, cfg, ScriptedRng(d20=[18], d6=[4, 4, 4]))
    exhale(engine)
    assert hp(engine, "goblin_1") == 24


def test_breath_gives_every_target_in_the_cone_its_own_save(registry, cfg):
    # первый гоблин провалил (12), второй прошёл (6): один бросок 3d6 на всех
    engine = breath_engine(
        registry, cfg, ScriptedRng(d20=[3, 18], d6=[4, 4, 4]), monsters=TWO_GOBLINS,
    )
    exhale(engine)
    assert (hp(engine, "goblin_1"), hp(engine, "goblin_2")) == (18, 24)


def test_breath_spares_a_target_outside_the_cone(registry, cfg):
    engine = breath_engine(
        registry, cfg, ScriptedRng(d20=[3], d6=[4, 4, 4]),
        monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    exhale(engine)
    assert hp(engine, "goblin_1") == 30


def test_breath_spends_the_action(registry, cfg):
    engine = breath_engine(registry, cfg, ScriptedRng(d20=[3], d6=[4, 4, 4]))
    assert turn(engine, "wiz").action is True
    exhale(engine)
    assert turn(engine, "wiz").action is False


def test_breath_option_is_absent_when_the_action_is_spent(registry, cfg):
    engine = breath_engine(registry, cfg, ScriptedRng())
    turn(engine, "wiz").action = False
    assert breath_items(engine) == []


def test_breath_log_names_the_type_and_the_roll(registry, cfg):
    engine = breath_engine(registry, cfg, ScriptedRng(d20=[3], d6=[4, 4, 4]))
    exhale(engine)
    assert log_has(engine, "Дыхание дракона (огонь)", "3d6 = 12")


@pytest.mark.parametrize("kind", BREATH_TYPES)
def test_breath_deals_the_chosen_damage_type(registry, cfg, kind):
    # гоблин невосприимчив к выбранному типу: при провале спасброска урона нет
    custom = custom_registry(registry, odd_goblin={"damage_immunities": [kind]})
    engine = breath_engine(
        registry=custom, cfg=cfg, rng=ScriptedRng(d20=[3], d6=[4, 4, 4]),
        monsters=[mon("goblin_1", "odd_goblin", "hall")], variant=kind,
    )
    exhale(engine)
    assert hp(engine, "goblin_1") == 30


def test_breath_of_another_type_ignores_the_immunity(registry, cfg):
    custom = custom_registry(registry, odd_goblin={"damage_immunities": ["cold"]})
    engine = breath_engine(
        registry=custom, cfg=cfg, rng=ScriptedRng(d20=[3], d6=[4, 4, 4]),
        monsters=[mon("goblin_1", "odd_goblin", "hall")], variant="fire",
    )
    exhale(engine)
    assert hp(engine, "goblin_1") == 18


# Верный удар

def strike_engine(registry, cfg, rng, level=1):
    engine = hall_engine(registry, cfg, rng, cantrips=["true_strike"])
    engine.heroes["wiz"].sheet.classes[0].level = level
    return engine


def test_true_strike_targets_enemies_only(registry, cfg):
    engine = strike_engine(registry, cfg, ScriptedRng())
    assert cast_ids(engine, "true_strike") == ["cast:true_strike:0:goblin_1"]


def archer_engine(registry, cfg, rng, goblin_zone="balcony", hero_zone="door", arrows=True, **kw):
    # волшебник с луком в руке (решение 34: цели Верного удара -- как у «Атаки» этим оружием)
    hero = mage(registry, cantrips=["true_strike"])
    give_weapon(hero, registry, "shortbow")
    if not arrows:
        remove_item(hero, "arrows", count_item(hero, "arrows"))
    return engine_of(
        registry, cfg, hero, rng, monsters=[mon("goblin_1", "goblin_warrior", goblin_zone)],
        hero_zone=hero_zone, **kw,
    )


def test_true_strike_with_a_bow_offers_a_goblin_across_a_zone(registry, cfg):
    engine = archer_engine(registry, cfg, ScriptedRng())
    assert cast_ids(engine, "true_strike") == ["cast:true_strike:0:goblin_1"]


def test_true_strike_with_a_bow_at_long_range_rolls_with_disadvantage(registry, cfg):
    # через три шага 120 фт > 80 фт: d20 18 и 2, берётся худший -- 2 + 5 < КД 15, промах
    engine = archer_engine(
        registry, cfg, ScriptedRng(d20=[18, 2]), goblin_zone="z3", hero_zone="z0",
        zones=make_line(4),
    )
    do_cast(engine, "wiz", "true_strike", "goblin_1")
    assert hp(engine, "goblin_1") == 30


def test_true_strike_with_a_bow_spends_an_arrow(registry, cfg):
    engine = archer_engine(registry, cfg, ScriptedRng(d20=[18, 2]), goblin_zone="z3",
                           hero_zone="z0", zones=make_line(4))
    before = count_item(engine.heroes["wiz"], "arrows")
    do_cast(engine, "wiz", "true_strike", "goblin_1")
    assert count_item(engine.heroes["wiz"], "arrows") == before - 1


def test_true_strike_with_a_melee_weapon_has_no_far_goblin(registry, cfg):
    engine = engine_of(
        registry, cfg, mage(registry, cantrips=["true_strike"]),
        monsters=[mon("goblin_1", "goblin_warrior", "balcony")], hero_zone="door",
    )
    assert cast_ids(engine, "true_strike") == []


def test_true_strike_with_a_bow_without_arrows_has_no_targets(registry, cfg):
    # гоблин в своей зоне: старые цели (enemy_refs) его предложили бы, стрелять нечем
    engine = archer_engine(
        registry, cfg, ScriptedRng(), goblin_zone="hall", hero_zone="hall", arrows=False,
    )
    assert cast_ids(engine, "true_strike") == []


def test_true_strike_with_a_sword_does_not_offer_a_levitated_goblin_in_the_own_zone(registry, cfg):
    engine = hall_engine(
        registry, cfg, ScriptedRng(d20=[3]), "levitate", cantrips=["true_strike"],
    )
    do_cast(engine, "wiz", "levitate", "goblin_1")
    next_hero_turn(engine, 1)
    assert cast_ids(engine, "true_strike") == []


def test_true_strike_attacks_with_the_spell_attack_bonus(registry, cfg):
    # d20 11 + Инт 3 + мастерство 2 = 16 >= КД 15; Сил −1 + 2 дали бы 12 -- промах
    engine = strike_engine(registry, cfg, ScriptedRng(d20=[11], d8=[3]))
    do_cast(engine, "wiz", "true_strike", "goblin_1")
    assert hp(engine, "goblin_1") < 30


def test_true_strike_roll_shows_the_spellcasting_ability(registry, cfg):
    engine = strike_engine(registry, cfg, ScriptedRng(d20=[11], d8=[3]))
    do_cast(engine, "wiz", "true_strike", "goblin_1")
    assert log_has(engine, "+ 3 Инт + 2 мастерство")
    assert not log_has(engine, "Сил")


def test_true_strike_costs_no_slot(registry, cfg):
    engine = strike_engine(registry, cfg, ScriptedRng(d20=[11], d8=[3]))
    do_cast(engine, "wiz", "true_strike", "goblin_1")
    assert (slot(engine, 1), slot(engine, 2)) == (4, 3)


def test_true_strike_at_the_fifth_level_adds_radiant_damage(registry, cfg):
    engine = strike_engine(registry, cfg, ScriptedRng(d20=[11], d8=[3], d6=[4]), level=5)
    do_cast(engine, "wiz", "true_strike", "goblin_1")
    assert log_has(engine, "излучением")


def test_true_strike_damage_uses_the_spellcasting_ability(registry, cfg):
    engine = strike_engine(registry, cfg, ScriptedRng(d20=[11], d8=[3]))
    do_cast(engine, "wiz", "true_strike", "goblin_1")
    assert log_has(engine, "Урон", "Инт")


def test_true_strike_damage_adds_the_spellcasting_modifier(registry, cfg):
    # d8 3 + Инт 3 = 6
    engine = strike_engine(registry, cfg, ScriptedRng(d20=[11], d8=[3]))
    do_cast(engine, "wiz", "true_strike", "goblin_1")
    assert hp(engine, "goblin_1") == 24


def test_true_strike_logs_the_weapon_and_the_spell_bonus(registry, cfg):
    engine = strike_engine(registry, cfg, ScriptedRng(d20=[11], d8=[3]))
    do_cast(engine, "wiz", "true_strike", "goblin_1")
    assert log_has(engine, "Верный удар", "бонус заклинаний")


def test_true_strike_event_damage_includes_the_radiant_die(registry, cfg):
    # оружие 3 + 3, излучение 4 -- одним событием атаки
    engine = strike_engine(registry, cfg, ScriptedRng(d20=[11], d8=[3], d6=[4]), level=5)
    events = do_cast(engine, "wiz", "true_strike", "goblin_1")
    assert events[0].data["damage"] == 10


def test_true_strike_kill_logs_the_target_hp_once(registry, cfg):
    engine = strike_engine(registry, cfg, ScriptedRng(d20=[11], d8=[3], d6=[4]), level=5)
    creature(engine, "goblin_1").hp_current = 4
    do_cast(engine, "wiz", "true_strike", "goblin_1")
    name = engine.name("goblin_1")
    assert len([x for x in engine.state.log if x.strip().startswith(f"{name}:")]) == 1


def test_radiant_resistance_halves_only_the_radiant_die(registry, cfg):
    # оружие 6 целиком, излучение 4 -> 2
    custom = custom_registry(registry, odd_goblin={"damage_resistances": ["radiant"]})
    engine = hall_engine(
        custom, cfg, ScriptedRng(d20=[11], d8=[3], d6=[4]), cantrips=["true_strike"],
        monsters=[mon("goblin_1", "odd_goblin", "hall")],
    )
    engine.heroes["wiz"].sheet.classes[0].level = 5
    do_cast(engine, "wiz", "true_strike", "goblin_1")
    assert hp(engine, "goblin_1") == 22


def test_true_strike_at_the_first_level_adds_no_radiant_damage(registry, cfg):
    engine = strike_engine(registry, cfg, ScriptedRng(d20=[11], d8=[3]))
    do_cast(engine, "wiz", "true_strike", "goblin_1")
    assert not log_has(engine, "излучением")


# Развеивание

def next_hero_turn(engine, others):
    # Паутина и Рассеивание не читаются в один ход: круг вокруг стола -- и снова ход героя
    pass_turns(engine, 1 + others)
    engine.start_turn("wiz")


def web_engine(registry, cfg, d20, monsters=GOBLIN):
    # d20: спасброски гоблинов при касте; за круг каждый гоблин ещё дважды бросает Лов
    # (начало хода в паутине и повтор в конце хода, оба провал), поэтому очередь утроена
    engine = idle(
        registry, cfg, mage(registry, "web", "dispel_magic"), ScriptedRng(d20=[*d20] * 3),
        monsters=monsters,
    )
    do_cast(engine, "wiz", "web", "hall")
    next_hero_turn(engine, len(monsters))
    return engine


def test_dispel_removes_a_circle_two_spell_from_a_target(registry, cfg):
    engine = web_engine(registry, cfg, [3])
    assert "restrained" in conditions(engine, "goblin_1")
    do_cast(engine, "wiz", "dispel_magic", "goblin_1")
    assert "restrained" not in conditions(engine, "goblin_1")


def test_dispel_ends_the_sources_concentration(registry, cfg):
    engine = web_engine(registry, cfg, [3])
    do_cast(engine, "wiz", "dispel_magic", "goblin_1")
    assert creature(engine, "wiz").concentration is None


def test_dispel_of_a_concentration_spell_frees_the_other_targets_too(registry, cfg):
    engine = web_engine(registry, cfg, [3, 3], TWO_GOBLINS)
    do_cast(engine, "wiz", "dispel_magic", "goblin_1")
    assert "restrained" not in conditions(engine, "goblin_2")


def test_dispel_logs_what_it_removed(registry, cfg):
    engine = web_engine(registry, cfg, [3])
    do_cast(engine, "wiz", "dispel_magic", "goblin_1")
    assert log_has(engine, "Рассеивание магии: снято Паутина с", engine.name("goblin_1"))


def test_dispel_removes_a_foreign_spell_from_an_ally(registry, cfg):
    # Паутина чужого источника (гоблин держит концентрацию) на союзнике
    ally = make_fighter(registry, "ally")
    engine = hall_engine(registry, cfg, ScriptedRng(), "dispel_magic", extra=[ally])
    creature(engine, "goblin_1").concentration = Concentration(spell_id="web", circle=2)
    creature(engine, "ally").conditions.append(
        AppliedCondition(
            id="restrained", source="web", expires=Expiry(kind="concentration", owner="goblin_1"),
        )
    )
    do_cast(engine, "wiz", "dispel_magic", "ally")
    assert "restrained" not in conditions(engine, "ally")
    assert creature(engine, "goblin_1").concentration is None


def test_dispel_on_a_zone_removes_the_darkness(registry, cfg):
    engine = dark_engine(registry, cfg, ScriptedRng(), "dispel_magic")
    do_cast(engine, "wiz", "darkness", "hall")
    next_hero_turn(engine, 1)
    do_cast(engine, "wiz", "dispel_magic", "hall")
    assert zone_effects(engine, "hall", "darkness") == []


def test_dispel_on_a_zone_ends_the_concentration_on_the_darkness(registry, cfg):
    engine = dark_engine(registry, cfg, ScriptedRng(), "dispel_magic")
    do_cast(engine, "wiz", "darkness", "hall")
    next_hero_turn(engine, 1)
    do_cast(engine, "wiz", "dispel_magic", "hall")
    assert creature(engine, "wiz").concentration is None


def test_dispel_on_another_zone_leaves_the_darkness(registry, cfg):
    engine = dark_engine(registry, cfg, ScriptedRng(), "dispel_magic")
    do_cast(engine, "wiz", "darkness", "hall")
    next_hero_turn(engine, 1)
    do_cast(engine, "wiz", "dispel_magic", "door")
    assert len(zone_effects(engine, "hall", "darkness")) == 1


def test_dispel_spends_the_third_circle_slot(registry, cfg):
    engine = web_engine(registry, cfg, [3])
    do_cast(engine, "wiz", "dispel_magic", "goblin_1")
    assert slot(engine, 3) == 2


def high_spell_engine(registry, cfg, d20, before=None):
    # заклинание 4 круга на гоблине (копия Удержания личности): Инт против СЛ 10 + 4 = 14;
    # before(engine) -- правка движка до каста
    base = registry.get("spell", "hold_person")
    big = base.model_copy(update={"id": "big_hold", "level": 4})
    custom = registry.with_items({"spell": [big]})
    engine = engine_of(custom, cfg, mage(custom, "dispel_magic"), ScriptedRng(d20=d20))
    if before is not None:
        before(engine)
    held = AppliedCondition(id="paralyzed", source="big_hold")
    creature(engine, "goblin_1").conditions.append(held)
    do_cast(engine, "wiz", "dispel_magic", "goblin_1")
    return engine


def test_dispel_failed_check_leaves_a_high_spell(registry, cfg):
    engine = high_spell_engine(registry, cfg, [2])
    assert "paralyzed" in conditions(engine, "goblin_1")


def test_dispel_passed_check_removes_a_high_spell(registry, cfg):
    engine = high_spell_engine(registry, cfg, [20])
    assert "paralyzed" not in conditions(engine, "goblin_1")


def test_dispel_check_just_below_the_dc_fails(registry, cfg):
    # 10 + Инт 3 = 13 < СЛ 14
    engine = high_spell_engine(registry, cfg, [10])
    assert "paralyzed" in conditions(engine, "goblin_1")


def test_dispel_check_equal_to_the_dc_passes(registry, cfg):
    # 11 + Инт 3 = 14 = СЛ 14
    engine = high_spell_engine(registry, cfg, [11])
    assert "paralyzed" not in conditions(engine, "goblin_1")


def test_dispel_failed_check_logs_the_dc(registry, cfg):
    engine = high_spell_engine(registry, cfg, [2])
    assert log_has(engine, "Рассеивание магии", "держится", "Инт", "против СЛ 14")


def test_dispel_on_a_target_without_spells_says_so(registry, cfg):
    # решение 32: строка «Рассеивание магии: на <цель> нет заклинаний», ячейка тратится
    engine = idle(registry, cfg, mage(registry, "dispel_magic"), ScriptedRng())
    do_cast(engine, "wiz", "dispel_magic", "goblin_1")
    assert log_has(engine, "Рассеивание магии: на", engine.name("goblin_1"), "нет заклинаний")


def test_dispel_on_a_target_without_spells_still_spends_the_slot(registry, cfg):
    engine = idle(registry, cfg, mage(registry, "dispel_magic"), ScriptedRng())
    do_cast(engine, "wiz", "dispel_magic", "goblin_1")
    assert slot(engine, 3) == 2


# выдох и защита носителя (SRD: Святилище и Невидимость кончаются от урона)

def test_breath_under_sanctuary_ends_the_sanctuary(registry, cfg):
    engine = hall_engine(
        registry, cfg, ScriptedRng(d20=[3], d6=[4, 4, 4]), "sanctuary", "dragons_breath",
    )
    do_cast(engine, "wiz", "sanctuary", "wiz")
    next_hero_turn(engine, 1)
    cast_variant(engine, "wiz", "dragons_breath", "wiz", "fire")
    exhale(engine)
    assert effects(engine, "wiz", "sanctuary") == []


def test_breath_of_an_invisible_bearer_reveals_him(registry, cfg):
    engine = breath_engine(registry, cfg, ScriptedRng(d20=[3], d6=[4, 4, 4]))
    creature(engine, "wiz").conditions.append(
        AppliedCondition(id="invisible", source="invisibility")
    )
    exhale(engine)
    assert "invisible" not in conditions(engine, "wiz")


# добор по выжившим мутантам: Рассеивание

class FlatCheck:
    # источник конвейера: +1 ко всякой проверке
    id = "flat_check"

    def modifiers(self, request, registry):
        return [Modifier(source="flat_check", flat=1)] if request.kind == "check" else []


def foreign_web_engine(registry, cfg, held, d20=()):
    # Паутина на союзнике, источник -- гоблин с концентрацией held; Рассеивание на союзника
    ally = make_fighter(registry, "ally")
    engine = hall_engine(registry, cfg, ScriptedRng(d20=list(d20)), "dispel_magic", extra=[ally])
    creature(engine, "goblin_1").concentration = held
    creature(engine, "ally").conditions.append(
        AppliedCondition(
            id="restrained", source="web", expires=Expiry(kind="concentration", owner="goblin_1"),
        )
    )
    do_cast(engine, "wiz", "dispel_magic", "ally")
    return engine


def test_dispel_of_a_spell_whose_owner_holds_nothing_still_removes_it(registry, cfg):
    engine = foreign_web_engine(registry, cfg, None)
    assert "restrained" not in conditions(engine, "ally")


def test_dispel_of_a_spell_whose_owner_holds_another_spell_removes_it_without_a_check(
    registry, cfg
):
    # концентрация владельца на другом заклинании 5 круга не поднимает круг Паутины
    engine = foreign_web_engine(
        registry, cfg, Concentration(spell_id="hold_person", circle=5), d20=[1],
    )
    assert "restrained" not in conditions(engine, "ally")


def test_dispel_keeps_the_owners_concentration_on_another_spell(registry, cfg):
    engine = foreign_web_engine(registry, cfg, Concentration(spell_id="hold_person", circle=2))
    assert creature(engine, "goblin_1").concentration.spell_id == "hold_person"


def test_dispel_of_a_spell_held_at_a_higher_circle_needs_a_check(registry, cfg):
    # Паутина на концентрации 5 круга: СЛ 15, d20 1 + Инт 3 -- не хватает
    engine = foreign_web_engine(
        registry, cfg, Concentration(spell_id="web", circle=5), d20=[1],
    )
    assert "restrained" in conditions(engine, "ally")


def test_dispel_logs_the_end_of_the_sources_concentration(registry, cfg):
    engine = web_engine(registry, cfg, [3])
    do_cast(engine, "wiz", "dispel_magic", "goblin_1")
    assert log_has(engine, engine.name("wiz"), "Паутина кончается")


def test_dispel_on_a_creature_leaves_the_zone_effect_of_the_caster(registry, cfg):
    engine = dark_engine(registry, cfg, ScriptedRng(), "dispel_magic")
    do_cast(engine, "wiz", "darkness", "hall")
    next_hero_turn(engine, 1)
    do_cast(engine, "wiz", "dispel_magic", "wiz")
    assert len(zone_effects(engine, "hall", "darkness")) == 1


def test_dispel_on_a_zone_logs_the_zone_name(registry, cfg):
    engine = dark_engine(registry, cfg, ScriptedRng(), "dispel_magic")
    do_cast(engine, "wiz", "darkness", "hall")
    next_hero_turn(engine, 1)
    do_cast(engine, "wiz", "dispel_magic", "hall")
    assert log_has(engine, "Рассеивание магии: снято Тьма с Центр зала")


def test_dispel_offers_no_dead_target(registry, cfg):
    engine = idle(registry, cfg, mage(registry, "dispel_magic"), ScriptedRng())
    engine.part("goblin_1").status = "dead"
    assert not [i for i in cast_ids(engine, "dispel_magic") if i.endswith(":goblin_1")]


def level_three_engine(registry, cfg, d20):
    # заклинание 3 круга (копия Удержания личности) на гоблине; Рассеивание ячейкой 3 круга
    base = registry.get("spell", "hold_person")
    mid = base.model_copy(update={"id": "mid_hold", "level": 3})
    custom = registry.with_items({"spell": [mid]})
    engine = engine_of(custom, cfg, mage(custom, "dispel_magic"), ScriptedRng(d20=d20))
    creature(engine, "goblin_1").conditions.append(
        AppliedCondition(id="paralyzed", source="mid_hold")
    )
    do_cast(engine, "wiz", "dispel_magic", "goblin_1")
    return engine


def test_dispel_of_a_spell_of_the_slot_circle_needs_no_check(registry, cfg):
    # d20 1 провалил бы проверку: заклинание круга ячейки снимается само
    engine = level_three_engine(registry, cfg, [1])
    assert "paralyzed" not in conditions(engine, "goblin_1")


def two_spells_engine(registry, cfg):
    engine = idle(registry, cfg, mage(registry, "dispel_magic"), ScriptedRng())
    goblin = creature(engine, "goblin_1")
    goblin.conditions.append(AppliedCondition(id="restrained", source="web"))
    goblin.conditions.append(AppliedCondition(id="paralyzed", source="hold_person"))
    do_cast(engine, "wiz", "dispel_magic", "goblin_1")
    return engine


def test_dispel_removes_every_spell_from_a_target(registry, cfg):
    engine = two_spells_engine(registry, cfg)
    assert conditions(engine, "goblin_1") == []


def test_dispel_log_lists_every_removed_spell(registry, cfg):
    engine = two_spells_engine(registry, cfg)
    names = [registry.get("spell", s).name for s in ("web", "hold_person")]
    assert log_has(engine, f"снято {', '.join(names)} с")


def test_dispel_removes_an_effect_of_a_spell_from_a_target(registry, cfg):
    # эффект не на концентрации: конец концентрации его не снимет, только Рассеивание
    engine = idle(registry, cfg, mage(registry, "dispel_magic"), ScriptedRng())
    creature(engine, "goblin_1").active_effects.append(
        ActiveEffect(
            id="phantasmal_force", source="wiz", kind="burn",
            params={"dice": "1d6", "damage_type": "psychic"},
            expires=Expiry(kind="rounds", value=5),
        )
    )
    do_cast(engine, "wiz", "dispel_magic", "goblin_1")
    assert effects(engine, "goblin_1", "phantasmal_force") == []


def test_dispel_ignores_an_effect_that_has_already_expired(registry, cfg):
    engine = idle(registry, cfg, mage(registry, "dispel_magic"), ScriptedRng())
    creature(engine, "goblin_1").active_effects.append(
        ActiveEffect(
            id="phantasmal_force", source="wiz", kind="burn",
            params={"dice": "1d6", "damage_type": "psychic"},
            expires=Expiry(kind="seconds", value=engine.world.clock.now_s),
        )
    )
    do_cast(engine, "wiz", "dispel_magic", "goblin_1")
    assert log_has(engine, "на", engine.name("goblin_1"), "нет заклинаний")


def test_dispel_failed_check_names_the_held_spell(registry, cfg):
    engine = high_spell_engine(registry, cfg, [2])
    assert log_has(engine, "Удержание личности держится")


def test_dispel_check_goes_through_the_engine_modifiers(registry, cfg):
    # 10 + Инт 3 + 1 от источника движка = 14 = СЛ 14
    def add_source(engine):
        engine.modifiers.register(FlatCheck())

    engine = high_spell_engine(registry, cfg, [10], before=add_source)
    assert "paralyzed" not in conditions(engine, "goblin_1")


def test_dispel_check_uses_the_ability_of_the_check(registry, cfg):
    # эффект героя +1 к проверкам Инт: 10 + 3 + 1 = 14 = СЛ 14
    def add_effect(engine):
        creature(engine, "wiz").active_effects.append(
            ActiveEffect(
                id="focus", source="wiz", kind="modifier",
                params={"target": "ability_check", "ability": "int", "amount": 1},
            )
        )

    engine = high_spell_engine(registry, cfg, [10], before=add_effect)
    assert "paralyzed" not in conditions(engine, "goblin_1")


def test_dispel_check_that_already_passes_keeps_the_heroic_inspiration(registry, cfg):
    # 11 + Инт 3 = 14 = СЛ 14: переброса не нужно, d20 в очереди один
    def inspire(engine):
        engine.heroes["wiz"].heroic_inspiration = True

    engine = high_spell_engine(registry, cfg, [11], before=inspire)
    assert engine.heroes["wiz"].heroic_inspiration is True


# добор по выжившим мутантам: Успокоение чувств

def test_calm_emotions_does_not_free_a_caster_outside_the_zone(registry, cfg):
    engine = hall_engine(
        registry, cfg, ScriptedRng(d20=[18]), "calm_emotions", zone="door",
    )
    afflict(engine, "wiz", "frightened")
    do_cast(engine, "wiz", "calm_emotions", "hall")
    assert "frightened" in conditions(engine, "wiz")


def test_calmed_enemy_conditions_end_with_the_concentration(registry, cfg):
    engine = calm_engine(registry, cfg, [3])
    do_cast(engine, "wiz", "calm_emotions", "hall")
    engine.drop_concentration_effects("wiz")
    assert conditions(engine, "goblin_1") == []


def test_calm_emotions_logs_the_conditions_of_a_failed_enemy(registry, cfg):
    engine = calm_engine(registry, cfg, [3])
    do_cast(engine, "wiz", "calm_emotions", "hall")
    names = [registry.get("condition", c).name for c in ("charmed", "incapacitated")]
    assert log_has(engine, engine.name("goblin_1"), ", ".join(names))


def test_burn_of_a_non_concentration_spell_lasts_by_the_spells_rounds(registry, cfg):
    base = registry.get("spell", "phantasmal_force")
    short = base.model_copy(update={"id": "short_force", "concentration": False})
    custom = registry.with_items({"spell": [short]})
    engine = hall_engine(custom, cfg, ScriptedRng(d20=[3]), "short_force")
    do_cast(engine, "wiz", "short_force", "goblin_1")
    burn = effects(engine, "goblin_1", "short_force")[0]
    assert burn.expires == Expiry(kind="rounds", value=10)


# добор по выжившим мутантам: Дыхание дракона

def test_breath_event_names_the_caster_target_spell_and_damage(registry, cfg):
    engine = breath_engine(registry, cfg, ScriptedRng(d20=[3], d6=[4, 4, 4]))
    set_hp(engine, "goblin_1", 5)
    items = [o for o in breath_items(engine) if "Центр зала" in o.label]
    events = engine.perform("wiz", items[0].id)
    attacks = [e.data for e in events if e.type == "attack"]
    assert attacks == [{
        "attacker": "wiz", "target": "goblin_1", "weapon": "dragons_breath", "mode": "spell",
        "outcome": "auto", "damage": 12,
    }]


def test_breath_kill_credits_the_caster(registry, cfg):
    engine = breath_engine(registry, cfg, ScriptedRng(d20=[3], d6=[4, 4, 4]))
    set_hp(engine, "goblin_1", 5)
    items = [o for o in breath_items(engine) if "Центр зала" in o.label]
    events = engine.perform("wiz", items[0].id)
    assert [e.data["by"] for e in events if e.type == "monster_died"] == ["wiz"]


def test_breath_log_shows_the_hp_of_every_target(registry, cfg):
    engine = breath_engine(registry, cfg, ScriptedRng(d20=[3], d6=[4, 4, 4]))
    exhale(engine)
    assert log_has(engine, engine.name("goblin_1"), engine.hp_text("goblin_1"))


def test_breath_halves_an_odd_total_rounding_down(registry, cfg):
    # 4 + 4 + 5 = 13, успех: 6
    engine = breath_engine(registry, cfg, ScriptedRng(d20=[18], d6=[4, 4, 5]))
    exhale(engine)
    assert hp(engine, "goblin_1") == 24


def test_breath_target_behind_cover_adds_it_to_the_dex_save(registry, cfg):
    # 10 + Лов 2 + укрытие 2 = 14 >= СЛ 13: половина от 12
    engine = breath_engine(
        registry, cfg, ScriptedRng(d20=[10], d6=[4, 4, 4]),
        zones=make_zones(hall=[feature("cover_half")]),
    )
    exhale(engine)
    assert hp(engine, "goblin_1") == 24


def test_breath_target_in_the_own_zone_gets_no_cover_bonus(registry, cfg):
    # 10 + Лов 2 = 12 < СЛ 13: укрытие своей зоны не считается
    engine = breath_engine(
        registry, cfg, ScriptedRng(d20=[10], d6=[4, 4, 4]),
        monsters=[mon("goblin_1", "goblin_warrior", "door")],
        zones=make_zones(door=[feature("cover_half")]),
    )
    exhale(engine, "У двери")
    assert hp(engine, "goblin_1") == 18
