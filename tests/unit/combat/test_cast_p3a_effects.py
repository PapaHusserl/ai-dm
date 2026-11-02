# К3 П3а (docs/plan-k3.md, «Тесты» П3): defense, всадники атак заклинанием, лечение, Щит (Р5),
# Туманный шаг, туман (Р18 а), Шипастая поросль, ward, Чудо-ягоды.
#   defense: Доспехи мага без доспеха -- КД +3, с доспехом пункта нет; Щит веры +2 с концентрацией;
#     Дубовая кора -- КД не ниже 17; Размытие -- атаки по цели с помехой; Невидимость --
#     состояние invisible.
#   всадники: Направленный снаряд -- следующая атака по цели с преимуществом, затем флаг снят;
#     Луч холода -- скорость -10 (одна строка); Кислотная стрела -- горение 2d4 в начале хода цели;
#     Луч болезни -- Тел, poisoned; Вампирское касание -- лечит заклинателя на половину урона;
#     Нанесение ран/Удар электричеством/Вампирское касание -- цель только в своей зоне.
#   лечение: Лечащее слово -- бонусное действие, цель в соседней зоне (60 фт = две), 2d4 + мод;
#     Множественное лечащее слово -- до 6 целей через запятую.
#   Щит: попадание, которое +5 к КД превращает в промах, -- «Щит — КД N, промах», ячейка и реакция
#     потрачены, эффект +5 до начала хода; перебор или нет реакции/ячейки/подготовки -- попадание.
#   Туманный шаг -- бонусное, в соседнюю зону, без провоцированных атак; Стремительное
#     отступление -- Рывок бонусным каждый ход, пока держится концентрация.
#   Туман: атаки в зону и из зоны -- с помехой. Шипастая поросль: вход и выход -- 2d4 колющего,
#     в начале хода без движения урона нет. Чудо-ягоды -- goodberries ×10, съесть -- бонусное,
#     +1 HP.
#   ward: Защита от зла и добра -- атаки существ нужного типа с помехой, остальных -- нет.
import pytest
from combat_kit import (
    ScriptedRng,
    creature,
    feature,
    hp,
    make_engine,
    make_fighter,
    make_zones,
    mon,
    option_ids,
    part,
    set_hp,
)
from test_cast_p3a import (
    GOBLIN,
    cast_ids,
    conditions,
    effects,
    engine_of,
    idle,
    mage,
    pass_turns,
    slot,
)
from test_ranger_combat import make_ranger, ranger_engine

from ai_dm.combat.actions.attack import roll_attack, spell_disadvantage
from ai_dm.combat.actions.move import thorns
from ai_dm.combat.controllers import ScriptedController
from ai_dm.combat.zone_effects import obscured, zone_effects
from ai_dm.rules.inventory import count_item
from ai_dm.state.creature import AppliedCondition

AT_WIZ = "attack:скимитар:wiz"


def at_door(ref="goblin_1"):
    return mon(ref, "goblin_warrior", "door")


def log_text(engine):
    return "\n".join(engine.state.log)


# defense

def test_mage_armor_is_offered_to_an_unarmored_hero_only(registry, cfg):
    ally = make_fighter(registry, "ally")
    engine = engine_of(registry, cfg, mage(registry, "mage_armor"), extra=[ally])
    ids = option_ids(engine, "wiz")
    assert "cast:mage_armor:1:wiz" in ids
    assert "cast:mage_armor:1:ally" not in ids


def test_mage_armor_adds_3_to_armor_class(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "mage_armor"))
    before = engine.armor_class("wiz")
    engine.perform("wiz", "cast:mage_armor:1:wiz")
    assert engine.armor_class("wiz") == before + 3
    assert slot(engine, 1) == 3


def test_shield_of_faith_adds_2_and_holds_concentration(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "shield_of_faith"))
    before = engine.armor_class("wiz")
    engine.perform("wiz", "cast:shield_of_faith:1:wiz")
    assert engine.armor_class("wiz") == before + 2
    assert engine.heroes["wiz"].creature.concentration.spell_id == "shield_of_faith"


def test_shield_of_faith_is_bonus_action(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "shield_of_faith"))
    engine.perform("wiz", "cast:shield_of_faith:1:wiz")
    turn = part(engine, "wiz").turn
    assert (turn.bonus, turn.action) == (False, True)


def test_barkskin_raises_low_armor_class_to_17(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "barkskin"))
    engine.perform("wiz", "cast:barkskin:2:wiz")
    assert engine.armor_class("wiz") == 17


def test_barkskin_does_not_lower_better_armor_class(registry, cfg):
    ally = make_fighter(registry, "ally")
    engine = engine_of(registry, cfg, mage(registry, "barkskin"), extra=[ally])
    before = engine.armor_class("ally")
    assert before > 17
    engine.perform("wiz", "cast:barkskin:2:ally")
    assert engine.armor_class("ally") == before


def test_recasting_a_defense_spell_replaces_only_its_own_effect(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "mage_armor", "shield_of_faith"))
    before = engine.armor_class("wiz")
    engine.perform("wiz", "cast:shield_of_faith:1:wiz")
    engine.perform("wiz", "cast:mage_armor:1:wiz")
    part(engine, "wiz").turn.action = True
    engine.perform("wiz", "cast:mage_armor:1:wiz")
    assert len(effects(engine, "wiz", "mage_armor")) == 1
    assert len(effects(engine, "wiz", "shield_of_faith")) == 1
    assert engine.armor_class("wiz") == before + 3 + 2


@pytest.mark.parametrize(
    ("spell", "circle"), [("mage_armor", 1), ("shield_of_faith", 1), ("barkskin", 2)]
)
def test_defense_armor_class_bonus_counts_as_magic(registry, cfg, spell, circle):
    engine = engine_of(registry, cfg, mage(registry, spell))
    before = engine.armor_class("wiz")
    engine.perform("wiz", f"cast:{spell}:{circle}:wiz")
    assert engine.armor_class("wiz") > before
    assert engine.armor_class("wiz", ignore_magic=True) == before


def test_concentration_defense_effect_is_bound_to_the_casters_concentration(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "shield_of_faith"))
    engine.perform("wiz", "cast:shield_of_faith:1:wiz")
    expires = effects(engine, "wiz", "shield_of_faith")[0].expires
    assert (expires.kind, expires.owner) == ("concentration", "wiz")
    engine.drop_concentration_effects("wiz")
    assert effects(engine, "wiz", "shield_of_faith") == []


def test_timed_defense_effect_runs_on_the_world_clock(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "mage_armor"))
    engine.perform("wiz", "cast:mage_armor:1:wiz")
    expires = effects(engine, "wiz", "mage_armor")[0].expires
    spell = registry.get("spell", "mage_armor")
    assert (expires.kind, expires.value) == ("seconds", engine.world.clock.now_s + spell.duration_s)


def test_defense_spell_with_several_effects_applies_each_of_them(registry, cfg):
    base = registry.get("spell", "mage_armor")
    invisible = registry.get("spell", "invisibility").effects[0]
    filler = base.effects[0].model_copy(update={"type": "utility", "value": None})
    veil = base.model_copy(
        update={"id": "veil_of_armor", "effects": [filler, invisible, base.effects[0]]}
    )
    custom = registry.with_items({"spell": [veil]})
    engine = engine_of(custom, cfg, mage(custom, "veil_of_armor"))
    before = engine.armor_class("wiz")
    engine.perform("wiz", "cast:veil_of_armor:1:wiz")
    assert "invisible" in conditions(engine, "wiz")
    assert engine.armor_class("wiz") == before + 3


def test_blur_is_offered_to_the_caster_only(registry, cfg):
    ally = make_fighter(registry, "ally")
    engine = engine_of(registry, cfg, mage(registry, "blur"), extra=[ally])
    ids = cast_ids(engine, "blur")
    assert ids
    assert all(i.endswith(":wiz") for i in ids)


@pytest.mark.parametrize(
    ("source", "effect_type"),
    [("mage_armor", "ac_bonus"), ("protection_from_energy", "resist"),
     ("invisibility", "invisible"), ("blur", "blur")],
)
def test_defense_target_count_follows_the_targets_of_its_effect(registry, cfg, source, effect_type):
    base = registry.get("spell", source)
    effect = base.effects[0].model_copy(update={"targets": 3})
    group = base.model_copy(update={
        "id": "group_ward", "level": 1, "range_kind": "ranged", "range_ft": 30,
        "effects": [effect],
    })
    custom = registry.with_items({"spell": [group]})
    ally = make_fighter(custom, "ally")
    engine = engine_of(custom, cfg, mage(custom, "group_ward"), extra=[ally])
    assert any(i.startswith("cast:group_ward:1:wiz,ally") for i in cast_ids(engine, "group_ward"))


def test_blur_gives_disadvantage_to_attacks_against_the_caster(registry, cfg):
    # два d20: 19 и 3, берётся худший: 3 + 4 = 7 < КД 11 -- промах
    engine = engine_of(
        registry, cfg, mage(registry, "blur"), ScriptedRng(d20=[19, 3]),
        monsters=[at_door()],
    )
    engine.perform("wiz", "cast:blur:2:wiz")
    engine.perform("goblin_1", AT_WIZ)
    assert hp(engine, "wiz") == 8


def test_without_blur_the_same_roll_hits(registry, cfg):
    engine = engine_of(
        registry, cfg, mage(registry), ScriptedRng(d20=[19], d6=[3]), monsters=[at_door()],
    )
    engine.perform("goblin_1", AT_WIZ)
    assert hp(engine, "wiz") < 8


def test_invisibility_makes_the_target_invisible_and_holds_concentration(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "invisibility"))
    engine.perform("wiz", "cast:invisibility:2:wiz")
    assert "invisible" in conditions(engine, "wiz")
    assert engine.heroes["wiz"].creature.concentration.spell_id == "invisibility"


def test_attack_ends_invisibility(registry, cfg):
    hero = mage(registry, "invisibility", cantrips=["fire_bolt"])
    rng = ScriptedRng(d20=[2])
    engine = idle(registry, cfg, hero, rng)
    engine.perform("wiz", "cast:invisibility:2:wiz")
    pass_turns(engine, 2)
    engine.start_turn("wiz")
    assert "invisible" in conditions(engine, "wiz")
    engine.perform("wiz", "cast:fire_bolt:0:goblin_1")
    assert rng.left("d20") == 0
    assert "invisible" not in conditions(engine, "wiz")
    # решение 62 (Р41 б): заклинание кончается целиком -- и концентрация, и строка лога
    assert engine.heroes["wiz"].creature.concentration is None
    assert "  Невидимость кончается" in engine.state.log


def test_invisibility_line_follows_the_hidden_line(registry, cfg):
    hero = mage(registry, "invisibility", cantrips=["fire_bolt"])
    engine = idle(registry, cfg, hero, ScriptedRng(d20=[2]))
    engine.perform("wiz", "cast:invisibility:2:wiz")
    pass_turns(engine, 2)
    engine.start_turn("wiz")
    engine.perform("wiz", "cast:fire_bolt:0:goblin_1")
    log = engine.state.log
    hidden_at = next(i for i, line in enumerate(log) if "больше не скрыт" in line)
    assert log[hidden_at + 1] == "  Невидимость кончается"


def test_ally_attack_under_invisibility_ends_the_casters_concentration(registry, cfg):
    ally = make_fighter(registry, "ally")
    monsters = [mon("goblin_1", "goblin_warrior", "door")]
    rng = ScriptedRng(d20=[2, 2])
    engine = engine_of(
        registry, cfg, mage(registry, "invisibility"), rng, monsters=monsters, extra=[ally],
    )
    engine.perform("wiz", "cast:invisibility:2:ally")
    assert "invisible" in conditions(engine, "ally")
    assert engine.heroes["wiz"].creature.concentration.spell_id == "invisibility"
    engine.perform("ally", "attack:longsword:goblin_1")
    assert "invisible" not in conditions(engine, "ally")
    assert engine.heroes["wiz"].creature.concentration is None


def test_attack_ends_invisibility_of_every_target_of_the_spell(registry, cfg):
    ally = make_fighter(registry, "ally")
    monsters = [mon("goblin_1", "goblin_warrior", "door")]
    engine = engine_of(
        registry, cfg, mage(registry, "invisibility"), ScriptedRng(d20=[2, 2]),
        monsters=monsters, extra=[ally],
    )
    engine.perform("wiz", "cast:invisibility:3:wiz,ally")
    assert "invisible" in conditions(engine, "wiz")
    assert "invisible" in conditions(engine, "ally")
    engine.perform("ally", "attack:longsword:goblin_1")
    assert "invisible" not in conditions(engine, "wiz")
    assert "invisible" not in conditions(engine, "ally")


def invisibility_party(registry, cfg, *spells):
    ally = make_fighter(registry, "ally")
    return engine_of(registry, cfg, mage(registry, *spells), extra=[ally])


def test_invisibility_third_circle_offers_pairs_of_targets(registry, cfg):
    ids = cast_ids(invisibility_party(registry, cfg, "invisibility"), "invisibility")
    assert "cast:invisibility:3:wiz,ally" in ids
    assert "cast:invisibility:3:wiz" in ids
    assert "cast:invisibility:3:ally" in ids


def test_invisibility_second_circle_stays_single_target(registry, cfg):
    ids = cast_ids(invisibility_party(registry, cfg, "invisibility"), "invisibility")
    assert not [i for i in ids if ":2:" in i and "," in i]


def test_invisibility_on_two_targets_makes_both_invisible_with_one_slot(registry, cfg):
    engine = invisibility_party(registry, cfg, "invisibility")
    engine.perform("wiz", "cast:invisibility:3:wiz,ally")
    assert "invisible" in conditions(engine, "wiz")
    assert "invisible" in conditions(engine, "ally")
    assert slot(engine, 3) == 2
    assert engine.heroes["wiz"].creature.concentration.spell_id == "invisibility"


def test_invisibility_on_two_targets_logs_one_line(registry, cfg):
    engine = invisibility_party(registry, cfg, "invisibility")
    engine.perform("wiz", "cast:invisibility:3:wiz,ally")
    name = registry.get("spell", "invisibility").name
    lines = [line for line in engine.state.log if f"{name} на" in line]
    assert len(lines) == 1
    assert "Лиэль" in lines[0] and "Арн" in lines[0]


def test_single_target_defense_spells_have_no_target_pairs(registry, cfg):
    engine = invisibility_party(
        registry, cfg, "barkskin", "blur", "mage_armor", "shield_of_faith",
    )
    for spell in ("barkskin", "blur", "mage_armor", "shield_of_faith"):
        assert not [i for i in cast_ids(engine, spell) if "," in i], spell


def test_hiding_without_a_spell_keeps_the_casters_concentration(registry, cfg):
    ally = make_fighter(registry, "ally")
    monsters = [mon("goblin_1", "goblin_warrior", "door")]
    engine = engine_of(
        registry, cfg, mage(registry, "bless"), ScriptedRng(d20=[2, 2], d4=[1, 1]),
        monsters=monsters, extra=[ally],
    )
    engine.perform("wiz", "cast:bless:1:ally")
    creature(engine, "ally").conditions.append(AppliedCondition(id="invisible", source="hidden"))
    engine.perform("ally", "attack:longsword:goblin_1")
    assert "invisible" not in conditions(engine, "ally")
    assert engine.heroes["wiz"].creature.concentration.spell_id == "bless"
    assert "  Невидимость кончается" not in engine.state.log


# всадники

def test_guiding_bolt_gives_advantage_to_the_next_attack_then_it_is_spent(registry, cfg):
    # попадание (12 + 5 >= 15); союзник 1: d20 3 и 15 с преимуществом -> 15 + 5 = 20 -- попадает;
    # союзник 2: единственный d20 3 + 5 = 8 -- промах (флаг снят)
    allies = [(make_fighter(registry, name), "hall") for name in ("ally", "ally2")]
    rng = ScriptedRng(d20=[12, 3, 15, 3], d6=[1, 1, 1, 1], d8=[4])
    engine = engine_of(registry, cfg, mage(registry, "guiding_bolt"), rng, extra=allies)
    engine.perform("wiz", "cast:guiding_bolt:1:goblin_1")
    after_bolt = hp(engine, "goblin_1")
    engine.perform("ally", "attack:longsword:goblin_1")
    after_first = hp(engine, "goblin_1")
    engine.perform("ally2", "attack:longsword:goblin_1")
    assert rng.left("d20") == 0
    assert after_first < after_bolt
    assert hp(engine, "goblin_1") == after_first


def test_guiding_bolt_miss_gives_no_advantage(registry, cfg):
    # промах заклинания (2 + 5 < 15) -- союзник бросает один d20: 3 + 5 = 8, промах
    allies = [(make_fighter(registry, "ally"), "hall")]
    rng = ScriptedRng(d20=[2, 3])
    engine = engine_of(registry, cfg, mage(registry, "guiding_bolt"), rng, extra=allies)
    engine.perform("wiz", "cast:guiding_bolt:1:goblin_1")
    engine.perform("ally", "attack:longsword:goblin_1")
    assert rng.left("d20") == 0
    assert hp(engine, "goblin_1") == 30


def test_ray_of_frost_hit_slows_the_target_by_10(registry, cfg):
    hero = mage(registry, cantrips=["ray_of_frost"])
    engine = engine_of(registry, cfg, hero, ScriptedRng(d20=[12], d8=[4]))
    engine.perform("wiz", "cast:ray_of_frost:0:goblin_1")
    speed = [e for e in creature(engine, "goblin_1").active_effects if e.kind == "speed"]
    assert [e.params["amount"] for e in speed] == [-10]
    assert hp(engine, "goblin_1") == 26


def test_ray_of_frost_miss_does_not_slow(registry, cfg):
    hero = mage(registry, cantrips=["ray_of_frost"])
    engine = engine_of(registry, cfg, hero, ScriptedRng(d20=[2]))
    engine.perform("wiz", "cast:ray_of_frost:0:goblin_1")
    assert [e for e in creature(engine, "goblin_1").active_effects if e.kind == "speed"] == []


def test_acid_arrow_hit_sets_the_target_burning_for_2d4_at_its_turn_start(registry, cfg):
    # попадание 4d4 = 4, в начале хода гоблина горение 2d4 = 4
    engine = idle(
        registry, cfg, mage(registry, "acid_arrow"), ScriptedRng(d20=[12], d4=[1, 1, 1, 1, 2, 2]),
    )
    engine.perform("wiz", "cast:acid_arrow:2:goblin_1")
    burning = [e for e in creature(engine, "goblin_1").active_effects if e.kind == "burning"]
    assert [e.params["dice"] for e in burning] == ["2d4"]
    pass_turns(engine, 2)
    assert hp(engine, "goblin_1") == 30 - 4 - 4


def test_ray_of_sickness_failed_con_save_poisons(registry, cfg):
    # попадание, 2d8 = 8; Тел гоблина +0: 5 < 13 -- провал
    engine = engine_of(
        registry, cfg, mage(registry, "ray_of_sickness"), ScriptedRng(d20=[12, 5], d8=[4, 4]),
    )
    engine.perform("wiz", "cast:ray_of_sickness:1:goblin_1")
    assert "poisoned" in conditions(engine, "goblin_1")
    assert hp(engine, "goblin_1") == 22


def test_ray_of_sickness_passed_con_save_does_not_poison(registry, cfg):
    engine = engine_of(
        registry, cfg, mage(registry, "ray_of_sickness"), ScriptedRng(d20=[12, 15], d8=[4, 4]),
    )
    engine.perform("wiz", "cast:ray_of_sickness:1:goblin_1")
    assert "poisoned" not in conditions(engine, "goblin_1")
    assert hp(engine, "goblin_1") == 22


def test_vampiric_touch_heals_the_caster_by_half_the_damage(registry, cfg):
    # 3d6 = 12, лечение 6: 2 -> 8 (максимум 20)
    engine = engine_of(
        registry, cfg, mage(registry, "vampiric_touch"), ScriptedRng(d20=[12], d6=[4, 4, 4]),
        monsters=[at_door()],
    )
    engine.heroes["wiz"].creature.hp_max = 20
    set_hp(engine, "wiz", 2)
    engine.perform("wiz", "cast:vampiric_touch:3:goblin_1")
    assert hp(engine, "goblin_1") == 18
    assert hp(engine, "wiz") == 8


def test_touch_spells_target_only_the_casters_zone(registry, cfg):
    hero = mage(registry, "vampiric_touch", "inflict_wounds", cantrips=["shocking_grasp"])
    far = engine_of(registry, cfg, hero)
    assert cast_ids(far, "vampiric_touch") == []
    assert cast_ids(far, "inflict_wounds") == []
    assert cast_ids(far, "shocking_grasp") == []


def test_touch_spells_are_offered_for_a_target_in_the_casters_zone(registry, cfg):
    hero = mage(registry, "vampiric_touch", "inflict_wounds", cantrips=["shocking_grasp"])
    near = engine_of(registry, cfg, hero, monsters=[at_door()])
    assert cast_ids(near, "vampiric_touch") == ["cast:vampiric_touch:3:goblin_1"]
    assert "cast:inflict_wounds:1:goblin_1" in cast_ids(near, "inflict_wounds")
    assert cast_ids(near, "shocking_grasp") == ["cast:shocking_grasp:0:goblin_1"]


# лечение

def hurt_ally(engine, ref="ally", value=1):
    set_hp(engine, ref, value)


def test_healing_word_is_a_bonus_action_for_an_ally_two_zones_away(registry, cfg):
    ally = make_fighter(registry, "ally")
    engine = engine_of(
        registry, cfg, mage(registry, "healing_word"), ScriptedRng(d4=[2, 3]),
        extra=[(ally, "balcony")],
    )
    hurt_ally(engine)
    assert "cast:healing_word:1:ally" in option_ids(engine, "wiz")
    engine.perform("wiz", "cast:healing_word:1:ally")
    assert hp(engine, "ally") == 1 + 2 + 3 + 3
    turn = part(engine, "wiz").turn
    assert (turn.bonus, turn.action) == (False, True)


def test_healing_word_third_circle_rolls_more_dice(registry, cfg):
    ally = make_fighter(registry, "ally")
    # 2 круг выше базового: 2d4 + 2 * 2d4 = 6d4 = 14, + Инт +3
    engine = engine_of(
        registry, cfg, mage(registry, "healing_word"), ScriptedRng(d4=[2, 3, 1, 4, 2, 2]),
        extra=[(ally, "hall")],
    )
    engine.heroes["ally"].creature.hp_max = 40
    hurt_ally(engine)
    engine.perform("wiz", "cast:healing_word:3:ally")
    assert hp(engine, "ally") == 1 + 14 + 3


def test_mass_healing_word_offers_several_targets_and_heals_each(registry, cfg):
    allies = [make_fighter(registry, name) for name in ("ally", "ally2")]
    engine = engine_of(
        registry, cfg, mage(registry, "mass_healing_word"), ScriptedRng(d4=[2] * 8), extra=allies,
    )
    for name in ("ally", "ally2"):
        hurt_ally(engine, name)
    assert "cast:mass_healing_word:3:ally,ally2" in option_ids(engine, "wiz")
    engine.perform("wiz", "cast:mass_healing_word:3:ally,ally2")
    assert hp(engine, "ally") > 1
    assert hp(engine, "ally2") > 1


# Щит (Р5 а)

def shield_engine(registry, cfg, rng, *spells, **kwargs):
    hero = mage(registry, *spells)
    return engine_of(registry, cfg, hero, rng, monsters=[at_door()], **kwargs)


def test_shield_turns_a_barely_hitting_attack_into_a_miss(registry, cfg):
    # КД 11, бросок 8 + 4 = 12 -- попадание, с +5 (16) -- промах; кубика урона нет
    engine = shield_engine(registry, cfg, ScriptedRng(d20=[8]), "shield")
    engine.perform("goblin_1", AT_WIZ)
    assert hp(engine, "wiz") == 8
    assert "Щит — КД 16, промах" in log_text(engine)


def test_shield_spends_the_slot_and_the_reaction(registry, cfg):
    engine = shield_engine(registry, cfg, ScriptedRng(d20=[8]), "shield")
    engine.perform("goblin_1", AT_WIZ)
    assert slot(engine, 1) == 3
    assert part(engine, "wiz").turn.reaction is False


def test_shield_adds_5_to_armor_class_until_the_casters_next_turn(registry, cfg):
    engine = shield_engine(registry, cfg, ScriptedRng(d20=[8]), "shield")
    before = engine.armor_class("wiz")
    engine.perform("goblin_1", AT_WIZ)
    assert engine.armor_class("wiz") == before + 5
    shield = effects(engine, "wiz", "shield")
    assert [e.expires.kind for e in shield] == ["start_of_turn"]


def test_shield_is_read_when_the_attack_total_equals_armor_class(registry, cfg):
    # КД 11, бросок 7 + 4 = 11 -- попадание ровно в КД
    engine = shield_engine(registry, cfg, ScriptedRng(d20=[7]), "shield")
    engine.perform("goblin_1", AT_WIZ)
    assert slot(engine, 1) == 3
    assert hp(engine, "wiz") == 8


def test_shield_rewrites_the_roll_result_to_a_miss(registry, cfg):
    engine = shield_engine(registry, cfg, ScriptedRng(d20=[8]), "shield")
    result = roll_attack(engine, "goblin_1", "wiz", 4, "normal", "Скимитар")
    assert result.outcome == "miss"


def test_shield_bonus_is_magic(registry, cfg):
    engine = shield_engine(registry, cfg, ScriptedRng(d20=[8]), "shield")
    before = engine.armor_class("wiz")
    engine.perform("goblin_1", AT_WIZ)
    assert engine.armor_class("wiz") == before + 5
    assert engine.armor_class("wiz", ignore_magic=True) == before


def test_shield_ends_when_the_casters_own_turn_starts(registry, cfg):
    engine = shield_engine(registry, cfg, ScriptedRng(d20=[8]), "shield")
    engine.perform("goblin_1", AT_WIZ)
    expires = effects(engine, "wiz", "shield")[0].expires
    assert (expires.kind, expires.owner) == ("start_of_turn", "wiz")
    engine.start_turn("wiz")
    assert effects(engine, "wiz", "shield") == []


def test_shield_is_not_read_when_the_attack_beats_armor_class_plus_5(registry, cfg):
    # 12 + 4 = 16 >= 16: Щит не помог бы
    engine = shield_engine(registry, cfg, ScriptedRng(d20=[12], d6=[3]), "shield")
    engine.perform("goblin_1", AT_WIZ)
    assert slot(engine, 1) == 4
    assert hp(engine, "wiz") < 8


def test_shield_is_not_read_on_a_miss(registry, cfg):
    engine = shield_engine(registry, cfg, ScriptedRng(d20=[2]), "shield")
    engine.perform("goblin_1", AT_WIZ)
    assert slot(engine, 1) == 4
    assert part(engine, "wiz").turn.reaction is True


def test_shield_is_not_read_without_a_reaction(registry, cfg):
    engine = shield_engine(registry, cfg, ScriptedRng(d20=[8], d6=[3]), "shield")
    part(engine, "wiz").turn.reaction = False
    engine.perform("goblin_1", AT_WIZ)
    assert slot(engine, 1) == 4
    assert hp(engine, "wiz") < 8


def test_shield_is_not_read_without_a_slot(registry, cfg):
    engine = shield_engine(registry, cfg, ScriptedRng(d20=[8], d6=[3]), "shield")
    for circle in (1, 2, 3):
        engine.heroes["wiz"].creature.resources[f"spell_slot:{circle}"].current = 0
    engine.perform("goblin_1", AT_WIZ)
    assert hp(engine, "wiz") < 8


def test_shield_is_not_read_by_a_paralyzed_hero(registry, cfg):
    # по парализованному в ближнем бою: преимущество (два d20) и крит (кости урона дважды)
    engine = shield_engine(registry, cfg, ScriptedRng(d20=[8, 8], d6=[3, 3], d4=[2, 2]), "shield")
    creature(engine, "wiz").conditions.append(AppliedCondition(id="paralyzed", source="x"))
    creature(engine, "wiz").hp_max = 40
    set_hp(engine, "wiz", 40)
    engine.perform("goblin_1", AT_WIZ)
    assert slot(engine, 1) == 4
    assert part(engine, "wiz").turn.reaction is True
    assert hp(engine, "wiz") < 40


def test_shield_is_not_read_by_an_incapacitated_hero(registry, cfg):
    engine = shield_engine(registry, cfg, ScriptedRng(d20=[8], d6=[3]), "shield")
    creature(engine, "wiz").conditions.append(AppliedCondition(id="incapacitated", source="x"))
    engine.perform("goblin_1", AT_WIZ)
    assert slot(engine, 1) == 4
    assert hp(engine, "wiz") < 8


def test_shield_is_not_read_when_not_prepared(registry, cfg):
    engine = shield_engine(registry, cfg, ScriptedRng(d20=[8], d6=[3]))
    engine.perform("goblin_1", AT_WIZ)
    assert hp(engine, "wiz") < 8


# Туманный шаг, Стремительное отступление

def test_misty_step_moves_to_an_adjacent_zone_without_opportunity_attacks(registry, cfg):
    # пустой ScriptedRng: бросок провоцированной атаки сорвал бы тест
    engine = engine_of(registry, cfg, mage(registry, "misty_step"), monsters=[at_door()])
    assert "cast:misty_step:2:hall" in option_ids(engine, "wiz")
    engine.perform("wiz", "cast:misty_step:2:hall")
    assert part(engine, "wiz").zone_id == "hall"
    assert slot(engine, 2) == 2
    assert part(engine, "wiz").turn.bonus is False


def test_misty_step_does_not_reach_a_far_zone(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "misty_step"))
    assert "cast:misty_step:2:balcony" not in option_ids(engine, "wiz")


def test_expeditious_retreat_gives_a_bonus_dash_on_later_turns(registry, cfg):
    engine = idle(registry, cfg, mage(registry, "expeditious_retreat"))
    assert "dash_bonus" not in option_ids(engine, "wiz")
    engine.perform("wiz", "cast:expeditious_retreat:1:")
    pass_turns(engine, 2)
    engine.start_turn("wiz")
    assert "dash_bonus" in option_ids(engine, "wiz")


# туман

def fog_engine(registry, cfg, rng):
    return idle(
        registry, cfg, mage(registry, "fog_cloud", cantrips=["fire_bolt"]), rng,
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )


def test_fog_cloud_marks_the_zone(registry, cfg):
    engine = fog_engine(registry, cfg, ScriptedRng())
    engine.perform("wiz", "cast:fog_cloud:1:hall")
    assert len(zone_effects(engine, "hall", "fog")) == 1
    assert obscured(engine, "hall") is True
    assert obscured(engine, "door") is False


SHOOT_WIZ = "attack:короткий_лук:wiz"


def test_attack_from_a_fogged_zone_has_disadvantage(registry, cfg):
    # гоблин в тумане стреляет по волшебнику: d20 19 и 3 -- худший 3 + 4 = 7 < 11
    rng = ScriptedRng(d20=[19, 3])
    engine = fog_engine(registry, cfg, rng)
    engine.perform("wiz", "cast:fog_cloud:1:hall")
    engine.perform("goblin_1", SHOOT_WIZ)
    assert rng.left("d20") == 0
    assert hp(engine, "wiz") == 8


def test_attack_at_a_fogged_zone_has_disadvantage(registry, cfg):
    # туман у цели (у двери), стрелок снаружи
    rng = ScriptedRng(d20=[19, 3])
    engine = fog_engine(registry, cfg, rng)
    engine.perform("wiz", "cast:fog_cloud:1:door")
    engine.perform("goblin_1", SHOOT_WIZ)
    assert rng.left("d20") == 0
    assert hp(engine, "wiz") == 8


def test_attack_into_a_fogged_zone_has_disadvantage(registry, cfg):
    # колдуем туман, на следующем ходе бьём в него: d20 19 и 2, худший 2 + 5 = 7 < КД 15
    rng = ScriptedRng(d20=[19, 2])
    engine = fog_engine(registry, cfg, rng)
    engine.perform("wiz", "cast:fog_cloud:1:hall")
    pass_turns(engine, 2)
    engine.start_turn("wiz")
    engine.perform("wiz", "cast:fire_bolt:0:goblin_1")
    assert rng.left("d20") == 0
    assert hp(engine, "goblin_1") == 30


def test_fog_in_another_zone_changes_nothing(registry, cfg):
    # один d20 атаки: без помехи 19 + 4 попадает (кубик урона 3 + 2), затем проверка концентрации
    rng = ScriptedRng(d20=[19, 18], d6=[3])
    engine = fog_engine(registry, cfg, rng)
    engine.perform("wiz", "cast:fog_cloud:1:balcony")
    engine.perform("goblin_1", SHOOT_WIZ)
    assert rng.left("d20") == 0
    assert hp(engine, "wiz") < 8


def test_fog_ends_with_concentration(registry, cfg):
    engine = fog_engine(registry, cfg, ScriptedRng())
    engine.perform("wiz", "cast:fog_cloud:1:hall")
    engine.drop_concentration_effects("wiz")
    assert obscured(engine, "hall") is False


# Шипастая поросль

def thorn_engine(registry, cfg, rng, monsters, zone="hall"):
    engine = engine_of(registry, cfg, mage(registry, "spike_growth"), rng, monsters=monsters)
    engine.perform("wiz", f"cast:spike_growth:2:{zone}")
    return engine


def test_leaving_the_spiked_zone_deals_2d4_piercing(registry, cfg):
    engine = thorn_engine(registry, cfg, ScriptedRng(d4=[2, 3]), GOBLIN)
    engine.perform("goblin_1", "move:balcony")
    assert hp(engine, "goblin_1") == 25


def test_entering_the_spiked_zone_deals_2d4_piercing(registry, cfg):
    engine = thorn_engine(registry, cfg, ScriptedRng(d4=[1, 4]), [at_door()])
    engine.perform("goblin_1", "move:hall")
    assert hp(engine, "goblin_1") == 25


def test_moving_outside_the_spiked_zone_costs_nothing(registry, cfg):
    # колючки на балконе, гоблин идёт из зала к двери: бросков нет (пустой ScriptedRng)
    engine = thorn_engine(registry, cfg, ScriptedRng(), GOBLIN, zone="balcony")
    engine.perform("goblin_1", "move:door")
    assert hp(engine, "goblin_1") == 30


def test_spiked_zone_damage_line_names_the_spell_and_the_damage_type(registry, cfg):
    engine = thorn_engine(registry, cfg, ScriptedRng(d4=[2, 3]), GOBLIN)
    engine.perform("goblin_1", "move:balcony")
    name = registry.get("spell", "spike_growth").name
    assert f"  {name}: 2d4 (2, 3) = 5 колющий" in engine.state.log


def test_spiked_zone_logs_the_hp_of_the_hurt_creature(registry, cfg):
    engine = thorn_engine(registry, cfg, ScriptedRng(d4=[2, 3]), GOBLIN)
    engine.perform("goblin_1", "move:balcony")
    assert f"  {engine.name('goblin_1')}: {engine.hp_text('goblin_1')}" in engine.state.log


def test_spiked_zone_kill_is_credited_to_the_caster(registry, cfg):
    engine = thorn_engine(registry, cfg, ScriptedRng(d4=[4, 4]), GOBLIN)
    set_hp(engine, "goblin_1", 5)
    events = thorns(engine, "goblin_1", "hall")
    assert [(e.type, e.data["by"]) for e in events] == [("monster_died", "wiz")]
    assert part(engine, "goblin_1").last_hit_by == "wiz"


def test_two_spiked_effects_stop_once_the_creature_has_dropped(registry, cfg):
    # второй эффект на той же зоне не бьёт упавшего: кубиков на него нет, события первого целы
    rng = ScriptedRng(d4=[4, 4])
    engine = thorn_engine(registry, cfg, rng, GOBLIN)
    effect = zone_effects(engine, "hall", "hazard")[0]
    creature(engine, "wiz").active_effects.append(effect.model_copy(deep=True))
    set_hp(engine, "goblin_1", 5)
    events = thorns(engine, "goblin_1", "hall")
    assert [e.type for e in events] == ["monster_died"]
    assert rng.left("d4") == 0


def test_standing_in_the_spiked_zone_at_turn_start_costs_nothing(registry, cfg):
    # пустой ScriptedRng: бросок 2d4 в начале хода сорвал бы тест
    engine = idle(registry, cfg, mage(registry, "spike_growth"), ScriptedRng())
    engine.perform("wiz", "cast:spike_growth:2:hall")
    pass_turns(engine, 2)
    assert hp(engine, "goblin_1") == 30


# Чудо-ягоды, Сотворение пищи

def test_goodberry_creates_ten_goodberries(registry, cfg):
    hero = mage(registry, "goodberry")
    engine = engine_of(registry, cfg, hero)
    assert count_item(hero, "goodberries") == 0
    engine.perform("wiz", "cast:goodberry:1:")
    assert count_item(hero, "goodberries") == 10
    assert slot(engine, 1) == 3


def test_goodberry_can_be_eaten_as_a_bonus_action_for_1_hp(registry, cfg):
    hero = mage(registry, "goodberry")
    engine = idle(registry, cfg, hero)
    engine.perform("wiz", "cast:goodberry:1:")
    pass_turns(engine, 2)
    engine.start_turn("wiz")
    set_hp(engine, "wiz", 3)
    engine.perform("wiz", "use_item:goodberries")
    assert hp(engine, "wiz") == 4
    assert count_item(hero, "goodberries") == 9
    assert part(engine, "wiz").turn.bonus is False


def test_create_food_and_water_creates_fifteen_rations(registry, cfg):
    hero = mage(registry, "create_food_and_water")
    engine = engine_of(registry, cfg, hero)
    engine.perform("wiz", "cast:create_food_and_water:3:")
    assert count_item(hero, "rations") == 15


# ward

def ward_engine(registry, cfg, rng, monster):
    engine = engine_of(
        registry, cfg, mage(registry, "protection_from_evil_and_good"), rng,
        monsters=[mon("foe", monster, "door")],
    )
    engine.perform("wiz", "cast:protection_from_evil_and_good:1:wiz")
    return engine


# Тип «человекоподобный» (guard) в списке заклинания не стоит; гоблин -- фея (fey), а fey в
# списке есть (в плане «гоблин — нет» -- расхождение с данными SRD).

def ward_name(registry):
    return registry.get("spell", "protection_from_evil_and_good").name


def test_ward_gives_disadvantage_against_a_skeleton(registry, cfg):
    engine = ward_engine(registry, cfg, ScriptedRng(), "skeleton")
    assert spell_disadvantage(engine, "foe", "wiz") == [ward_name(registry)]


def test_ward_gives_disadvantage_against_an_elemental(registry, cfg):
    # engine.tags берёт тип существа монстра (мини дежурного 63e1ef9: Воздушный элементаль)
    engine = ward_engine(registry, cfg, ScriptedRng(), "air_elemental")
    assert spell_disadvantage(engine, "foe", "wiz") == [ward_name(registry)]


def test_ward_gives_disadvantage_against_a_fey_goblin(registry, cfg):
    engine = ward_engine(registry, cfg, ScriptedRng(), "goblin_warrior")
    assert spell_disadvantage(engine, "foe", "wiz") == [ward_name(registry)]


def test_ward_does_not_affect_a_humanoid(registry, cfg):
    engine = ward_engine(registry, cfg, ScriptedRng(), "guard")
    assert spell_disadvantage(engine, "foe", "wiz") == []


def test_skeleton_attack_on_a_warded_hero_rolls_with_disadvantage(registry, cfg):
    # d20 19 и 2, худший 2 + бонус скелета < КД 11: промах
    rng = ScriptedRng(d20=[19, 2])
    engine = ward_engine(registry, cfg, rng, "skeleton")
    engine.perform("foe", "attack:короткий_меч:wiz")
    assert rng.left("d20") == 0
    assert hp(engine, "wiz") == 8


def test_ward_stops_fear_from_a_warded_creature_type(registry, cfg):
    engine = ward_engine(registry, cfg, ScriptedRng(), "skeleton")
    assert engine.impose("wiz", AppliedCondition(id="frightened", source="foe")) is False
    assert "frightened" not in conditions(engine, "wiz")
    assert any("защита" in line for line in engine.state.log)


def test_ward_stops_charm_from_a_warded_creature_type(registry, cfg):
    engine = ward_engine(registry, cfg, ScriptedRng(), "skeleton")
    assert engine.impose("wiz", AppliedCondition(id="charmed", source="foe")) is False


def test_ward_log_names_the_condition_in_russian(registry, cfg):
    engine = ward_engine(registry, cfg, ScriptedRng(), "skeleton")
    engine.impose("wiz", AppliedCondition(id="frightened", source="foe"))
    word = registry.get("condition", "frightened").name
    assert any(f"защита не даёт наложить состояние {word}" in line for line in engine.state.log)
    assert not any("frightened" in line for line in engine.state.log)


def test_ward_lets_a_humanoid_frighten(registry, cfg):
    engine = ward_engine(registry, cfg, ScriptedRng(), "guard")
    assert engine.impose("wiz", AppliedCondition(id="frightened", source="foe")) is True
    assert "frightened" in conditions(engine, "wiz")


def test_ward_does_not_stop_other_conditions_from_a_skeleton(registry, cfg):
    engine = ward_engine(registry, cfg, ScriptedRng(), "skeleton")
    assert engine.impose("wiz", AppliedCondition(id="prone", source="foe")) is True


# Бесследное передвижение следопыта в бою (BACKLOG 11)

def tracker_engine(registry, cfg, rng, spells=("pass_without_trace",)):
    hero = make_ranger(registry, level=5)
    hero.sheet.prepared_of()[:] = list(spells)
    controllers = {"hero": ScriptedController([]), "goblin_1": ScriptedController([])}
    return ranger_engine(
        registry, cfg, rng, hero=hero, controllers=controllers,
        zones=make_zones(door=[feature("cover_half")]),
    )


def hidden_after_hide(engine):
    engine.start_turn("hero")
    engine.perform("hero", "hide")
    return any(c.id == "invisible" and c.source == "hidden" for c in conditions_of(engine, "hero"))


def conditions_of(engine, ref):
    return creature(engine, ref).conditions


def test_ranger_is_offered_pass_without_trace_in_combat(registry, cfg):
    engine = tracker_engine(registry, cfg, ScriptedRng())
    assert "cast:pass_without_trace:2:hero" in option_ids(engine, "hero")


def test_pass_without_trace_cast_in_combat_puts_a_stealth_modifier(registry, cfg):
    engine = tracker_engine(registry, cfg, ScriptedRng())
    engine.perform("hero", "cast:pass_without_trace:2:hero")
    modifiers = [e for e in creature(engine, "hero").active_effects if e.kind == "modifier"]
    assert [e.params for e in modifiers] == [{"target": "skill", "skill": "stealth", "amount": 10}]
    assert engine.heroes["hero"].creature.concentration.spell_id == "pass_without_trace"


def test_hide_under_pass_without_trace_gets_plus_10(registry, cfg):
    # бросок 2 не дотягивает до СЛ 15 без заклинания, с ним (+10) -- прячется
    engine = tracker_engine(registry, cfg, ScriptedRng(d20=[2]))
    engine.perform("hero", "cast:pass_without_trace:2:hero")
    pass_turns(engine, 2)
    assert hidden_after_hide(engine) is True


def test_pass_without_trace_offers_up_to_three_targets_within_30_feet(registry, cfg):
    # решение 59: до 3 целей через запятую; союзник в 60 фт (балкон) вне списка
    hero = make_ranger(registry, level=5)
    hero.sheet.prepared_of()[:] = ["pass_without_trace"]
    near = [(make_fighter(registry, name), "hall") for name in ("a", "b")]
    far = (make_fighter(registry, "c"), "balcony")
    engine = make_engine(
        registry, cfg, heroes=[(hero, "door"), *near, far], rng=ScriptedRng(),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    ids = [i for i in option_ids(engine, "hero") if i.startswith("cast:pass_without_trace:2:")]
    targets = [i.rsplit(":", 1)[1].split(",") for i in ids]
    assert "hero,a,b" in [",".join(t) for t in targets]
    assert max(len(t) for t in targets) == 3
    assert not [t for t in targets if "c" in t]


def test_hide_without_pass_without_trace_fails_on_the_same_roll(registry, cfg):
    engine = tracker_engine(registry, cfg, ScriptedRng(d20=[2]), spells=())
    assert hidden_after_hide(engine) is False
