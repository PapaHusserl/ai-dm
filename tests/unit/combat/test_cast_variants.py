# К3 П3а (docs/plan-k3.md, «Тесты» П3, решение 19, Р26): варианты заклинаний, площадь, метка,
# баффы, утилита.
#   Варианты (Цветной шар -- тип урона, Защита от энергии -- тип, Усиление способности --
#     характеристика): по пункту на значение, id cast:<заклинание>:<круг>:<цель>:v:<значение>,
#     params["variant"] и params["title"]; выбор «огонь» -- урон огнём (сопротивление режет вдвое).
#   Площадь: Громовая волна -- все в своей зоне, спасбросок Тел, толчок в соседнюю зону при провале,
#     заклинатель цел; Кислотный плевок -- все в зоне цели, кроме заклинателя; Смазка -- Лов,
#     «Лежит»; Страх -- конус как Огненные руки, Мдр, испуг.
#   Мощный заговор (Воплотитель): Священное пламя -- половина при успехе спасброска.
#   mark: Проклятие -- Мдр, провал -- метка (+1d8 некротического к попаданиям заклинателя).
#   buff: Магическое оружие -- +1 к броску и урону оружием; Луч ослабления -- помеха атакам цели
#     и -1d8 к урону; Усиление способности -- преимущество на проверки выбранной характеристики;
#     Маяк надежды -- Лечащее слово лечит максимум костей.
#   utility: Фокусы -- действие и без эффекта в листе; Опутывание -- restrained, повтор Сил.
from combat_kit import (
    ScriptedRng,
    creature,
    custom_registry,
    down_hero,
    hp,
    make_fighter,
    mon,
    option_ids,
    part,
    set_hp,
)
from test_cast_p3a import (
    TWO_GOBLINS,
    cast_ids,
    conditions,
    engine_of,
    idle,
    mage,
    pass_turns,
    slot,
)

from ai_dm.combat.actions.cast_support import with_variant
from ai_dm.state.combat import Zone
from ai_dm.state.creature import AppliedCondition


def options_of(engine, spell_id, ref="wiz"):
    return [o for o in engine.available_actions(ref) if o.id.startswith(f"cast:{spell_id}:")]


# варианты: меню

def test_chromatic_orb_has_one_option_per_damage_type(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "chromatic_orb"))
    first_circle = [o for o in options_of(engine, "chromatic_orb") if o.params["circle"] == 1]
    assert [o.params["variant"] for o in first_circle] == [
        "acid", "cold", "fire", "lightning", "poison", "thunder",
    ]


def test_chromatic_orb_option_ids_carry_the_variant(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "chromatic_orb"))
    assert "cast:chromatic_orb:1:goblin_1:v:fire" in option_ids(engine, "wiz")
    assert "cast:chromatic_orb:1:goblin_1" not in option_ids(engine, "wiz")


def test_chromatic_orb_option_params_have_title_and_variant(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "chromatic_orb"))
    option = next(o for o in options_of(engine, "chromatic_orb") if o.params["variant"] == "fire")
    assert option.params["title"] == "Цветной шар"
    assert option.params["spell"] == "chromatic_orb"
    assert option.label.startswith("Цветной шар (огонь) →")


def test_spell_without_variants_has_no_variant_param(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "magic_missile"))
    option = options_of(engine, "magic_missile")[0]
    assert "variant" not in option.params


def test_protection_from_energy_offers_five_variants_to_self(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "protection_from_energy"))
    ids = cast_ids(engine, "protection_from_energy")
    assert sorted(i.rsplit(":", 1)[1] for i in ids) == [
        "acid", "cold", "fire", "lightning", "thunder",
    ]
    assert all(":wiz:v:" in i for i in ids)


def test_enhance_ability_offers_six_abilities(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "enhance_ability"))
    ids = cast_ids(engine, "enhance_ability")
    assert sorted(i.rsplit(":", 1)[1] for i in ids) == ["cha", "con", "dex", "int", "str", "wis"]


# варианты: исполнение

def resistant_engine(registry, cfg, rng, resist):
    custom = custom_registry(registry, odd_goblin={"damage_resistances": resist})
    monsters = [mon("goblin_1", "odd_goblin", "hall")]
    return engine_of(custom, cfg, mage(custom, "chromatic_orb"), rng, monsters=monsters)


def test_chromatic_orb_fire_variant_is_halved_by_fire_resistance(registry, cfg):
    # попадание, 3d8 = 12; сопротивление огню: 6
    engine = resistant_engine(registry, cfg, ScriptedRng(d20=[12], d8=[4, 4, 4]), ["fire"])
    engine.perform("wiz", "cast:chromatic_orb:1:goblin_1:v:fire")
    assert hp(engine, "goblin_1") == 24


def test_chromatic_orb_cold_variant_ignores_fire_resistance(registry, cfg):
    engine = resistant_engine(registry, cfg, ScriptedRng(d20=[12], d8=[4, 4, 4]), ["fire"])
    engine.perform("wiz", "cast:chromatic_orb:1:goblin_1:v:cold")
    assert hp(engine, "goblin_1") == 18


def test_chromatic_orb_second_circle_adds_a_die(registry, cfg):
    engine = engine_of(
        registry, cfg, mage(registry, "chromatic_orb"), ScriptedRng(d20=[12], d8=[4, 4, 4, 4]),
    )
    engine.perform("wiz", "cast:chromatic_orb:2:goblin_1:v:acid")
    assert hp(engine, "goblin_1") == 30 - 16
    assert slot(engine, 2) == 2


def test_protection_from_energy_fire_resists_fire_only(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "protection_from_energy"))
    engine.perform("wiz", "cast:protection_from_energy:3:wiz:v:fire")
    resist = [e for e in creature(engine, "wiz").active_effects if e.kind == "resist"]
    assert [e.params["damage_type"] for e in resist] == ["fire"]
    assert engine.heroes["wiz"].creature.concentration.spell_id == "protection_from_energy"


def test_enhance_ability_gives_advantage_to_the_chosen_ability_only(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "enhance_ability"))
    engine.perform("wiz", "cast:enhance_ability:2:wiz:v:con")
    effect = next(e for e in creature(engine, "wiz").active_effects if e.id == "enhance_ability")
    assert effect.params["ability"] == "con"
    assert effect.params["mode"] == "advantage"


# площадь

def test_thunderwave_fails_con_save_damages_and_pushes_the_target(registry, cfg):
    # гоблин у двери (зона заклинателя): Тел +0, 5 < 13; 2d8 = 8; толчок в соседнюю зону
    engine = engine_of(
        registry, cfg, mage(registry, "thunderwave"), ScriptedRng(d20=[5], d8=[4, 4]),
        monsters=[mon("goblin_1", "goblin_warrior", "door")],
    )
    engine.perform("wiz", "cast:thunderwave:1:door")
    assert hp(engine, "goblin_1") == 22
    assert part(engine, "goblin_1").zone_id == "hall"


def uphill_hall():
    # зал на высоте 1: дверь на той же высоте стоит в списке раньше, балкон ниже
    return [
        Zone(id="door", name="У двери", adjacent=["hall"], elevation=1),
        Zone(id="hall", name="Центр зала", adjacent=["door", "balcony"], elevation=1),
        Zone(id="balcony", name="Балкон", adjacent=["hall"], elevation=0),
    ]


def push_engine(registry, cfg, rng):
    engine = engine_of(
        registry, cfg, mage(registry, "thunderwave"), rng, zones=uphill_hall(), hero_zone="hall",
    )
    set_hp(engine, "goblin_1", 10)
    return engine


def test_thunderwave_pushes_the_target_down_rather_than_to_a_level_zone(registry, cfg):
    engine = push_engine(registry, cfg, ScriptedRng(d20=[5], d8=[4, 4], d6=[1]))
    engine.perform("wiz", "cast:thunderwave:1:hall")
    assert part(engine, "goblin_1").zone_id == "balcony"


def test_thunderwave_push_into_a_pit_credits_the_fall_to_the_caster(registry, cfg):
    # 10 - 8 = 2 HP, падение 1d6 = 6 добивает
    engine = push_engine(registry, cfg, ScriptedRng(d20=[5], d8=[4, 4], d6=[6]))
    events = engine.perform("wiz", "cast:thunderwave:1:hall")
    assert [e.data["by"] for e in events if e.type == "monster_died"] == ["wiz"]
    assert part(engine, "goblin_1").last_hit_by == "wiz"


def test_with_variant_substitutes_the_damage_type_and_clears_the_variants(registry):
    spell = with_variant(registry.get("spell", "chromatic_orb"), "fire")
    damage = next(e for e in spell.effects if e.type == "damage")
    assert damage.damage_type == "fire"
    assert all(e.variants == [] for e in spell.effects)


def test_with_variant_substitutes_the_ability_of_a_modifier(registry):
    spell = with_variant(registry.get("spell", "enhance_ability"), "con")
    modifier = next(e for e in spell.effects if e.type == "modifier")
    assert modifier.ability == "con"
    assert all(e.variants == [] for e in spell.effects)


def test_thunderwave_passed_save_halves_and_does_not_push(registry, cfg):
    engine = engine_of(
        registry, cfg, mage(registry, "thunderwave"), ScriptedRng(d20=[15], d8=[4, 4]),
        monsters=[mon("goblin_1", "goblin_warrior", "door")],
    )
    engine.perform("wiz", "cast:thunderwave:1:door")
    assert hp(engine, "goblin_1") == 26
    assert part(engine, "goblin_1").zone_id == "door"


def test_thunderwave_spares_the_caster(registry, cfg):
    engine = engine_of(
        registry, cfg, mage(registry, "thunderwave"), ScriptedRng(d20=[5], d8=[4, 4]),
        monsters=[mon("goblin_1", "goblin_warrior", "door")],
    )
    engine.perform("wiz", "cast:thunderwave:1:door")
    assert hp(engine, "wiz") == 8


def test_acid_splash_hits_everyone_in_the_target_zone_except_the_caster(registry, cfg):
    # заговор у двери: гоблин и союзник в зоне заклинателя, оба Лов 5 + 2 < 13; 1d6 = 3
    ally = make_fighter(registry, "ally")
    monsters = [mon("goblin_1", "goblin_warrior", "door")]
    engine = engine_of(
        registry, cfg, mage(registry, cantrips=["acid_splash"]), ScriptedRng(d20=[5, 5], d6=[3]),
        monsters=monsters, extra=[ally],
    )
    ally_before = hp(engine, "ally")
    engine.perform("wiz", "cast:acid_splash:0:door")
    assert hp(engine, "goblin_1") == 27
    assert hp(engine, "ally") == ally_before - 3
    assert hp(engine, "wiz") == 8


def test_acid_splash_hits_every_goblin_of_the_zone(registry, cfg):
    engine = engine_of(
        registry, cfg, mage(registry, cantrips=["acid_splash"]), ScriptedRng(d20=[5, 5], d6=[3]),
        monsters=TWO_GOBLINS,
    )
    engine.perform("wiz", "cast:acid_splash:0:hall")
    assert (hp(engine, "goblin_1"), hp(engine, "goblin_2")) == (27, 27)


def test_grease_failed_dex_save_knocks_everyone_in_the_zone_prone(registry, cfg):
    engine = engine_of(
        registry, cfg, mage(registry, "grease"), ScriptedRng(d20=[5, 5]), monsters=TWO_GOBLINS,
    )
    engine.perform("wiz", "cast:grease:1:hall")
    assert conditions(engine, "goblin_1") == ["prone"]
    assert conditions(engine, "goblin_2") == ["prone"]


def test_grease_passed_save_leaves_standing(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "grease"), ScriptedRng(d20=[15]))
    engine.perform("wiz", "cast:grease:1:hall")
    assert conditions(engine, "goblin_1") == []


def test_fear_is_a_cone_like_burning_hands(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "fear"))
    ids = cast_ids(engine, "fear")
    assert "cast:fear:3:door" in ids
    assert "cast:fear:3:hall" in ids
    assert "cast:fear:3:balcony" not in ids


def test_fear_failed_wis_save_frightens(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "fear"), ScriptedRng(d20=[5]))
    engine.perform("wiz", "cast:fear:3:hall")
    assert "frightened" in conditions(engine, "goblin_1")


def test_entangle_failed_str_save_restrains_the_zone(registry, cfg):
    engine = engine_of(
        registry, cfg, mage(registry, "entangle"), ScriptedRng(d20=[5, 15]), monsters=TWO_GOBLINS,
    )
    engine.perform("wiz", "cast:entangle:1:hall")
    assert conditions(engine, "goblin_1") == ["restrained"]
    assert conditions(engine, "goblin_2") == []


def test_entangle_target_repeats_the_str_save(registry, cfg):
    engine = idle(registry, cfg, mage(registry, "entangle"), ScriptedRng(d20=[5, 15]))
    engine.perform("wiz", "cast:entangle:1:hall")
    pass_turns(engine, 2)
    assert conditions(engine, "goblin_1") == []


def test_sacred_flame_passed_save_deals_half_to_an_evoker(registry, cfg):
    # Мощный заговор (Воплотитель 3 ур.): 1d8 = 6, спасбросок успешен -- половина
    hero = mage(registry, cantrips=["sacred_flame"])
    hero.sheet.primary.subclass_id = "evoker"
    hero.sheet.primary.level = 3
    engine = engine_of(registry, cfg, hero, ScriptedRng(d20=[15], d8=[6]))
    engine.perform("wiz", "cast:sacred_flame:0:goblin_1")
    assert hp(engine, "goblin_1") == 27


def test_sacred_flame_passed_save_deals_nothing_to_a_plain_caster(registry, cfg):
    hero = mage(registry, cantrips=["sacred_flame"])
    engine = engine_of(registry, cfg, hero, ScriptedRng(d20=[15], d8=[6]))
    engine.perform("wiz", "cast:sacred_flame:0:goblin_1")
    assert hp(engine, "goblin_1") == 30


# mark

def test_bestow_curse_failed_wis_save_marks_the_target(registry, cfg):
    engine = engine_of(
        registry, cfg, mage(registry, "bestow_curse"), ScriptedRng(d20=[5]),
        monsters=[mon("goblin_1", "goblin_warrior", "door")],
    )
    engine.perform("wiz", "cast:bestow_curse:3:goblin_1")
    marks = [e for e in creature(engine, "goblin_1").active_effects if e.kind == "mark"]
    assert [e.params["dice"] for e in marks] == ["1d8"]
    assert engine.heroes["wiz"].creature.concentration.spell_id == "bestow_curse"


def test_bestow_curse_passed_save_places_no_mark(registry, cfg):
    engine = engine_of(
        registry, cfg, mage(registry, "bestow_curse"), ScriptedRng(d20=[19]),
        monsters=[mon("goblin_1", "goblin_warrior", "door")],
    )
    engine.perform("wiz", "cast:bestow_curse:3:goblin_1")
    assert [e for e in creature(engine, "goblin_1").active_effects if e.kind == "mark"] == []
    assert slot(engine, 3) == 2


def test_cursed_target_takes_extra_necrotic_damage_from_the_casters_hit(registry, cfg):
    # проклятие, на следующем ходе Огненная стрела: 1d10 = 5 + 1d8 = 3 некротического
    hero = mage(registry, "bestow_curse", cantrips=["fire_bolt"])
    engine = idle(
        registry, cfg, hero, ScriptedRng(d20=[5, 12, 12], d10=[5], d8=[3]),
        monsters=[mon("goblin_1", "goblin_warrior", "door")],
    )
    engine.perform("wiz", "cast:bestow_curse:3:goblin_1")
    pass_turns(engine, 2)
    engine.start_turn("wiz")
    engine.perform("wiz", "cast:fire_bolt:0:goblin_1")
    assert hp(engine, "goblin_1") == 30 - 5 - 3


# buff

def test_magic_weapon_adds_1_to_attack_and_damage_of_the_ally(registry, cfg):
    # меч союзника +5: 9 + 5 = 14 < КД 15 -- без заклинания промах, с ним 15 -- попадание;
    # урон 1d8 (4) + 3 + 1 = 8
    ally = make_fighter(registry, "ally")
    monsters = [mon("goblin_1", "goblin_warrior", "door")]
    engine = engine_of(
        registry, cfg, mage(registry, "magic_weapon"), ScriptedRng(d20=[9], d8=[4]),
        monsters=monsters, extra=[ally],
    )
    engine.perform("wiz", "cast:magic_weapon:2:ally")
    engine.perform("ally", "attack:longsword:goblin_1")
    assert hp(engine, "goblin_1") == 30 - 8


def test_without_magic_weapon_the_same_roll_misses(registry, cfg):
    ally = make_fighter(registry, "ally")
    monsters = [mon("goblin_1", "goblin_warrior", "door")]
    engine = engine_of(
        registry, cfg, mage(registry), ScriptedRng(d20=[9]), monsters=monsters, extra=[ally],
    )
    engine.perform("ally", "attack:longsword:goblin_1")
    assert hp(engine, "goblin_1") == 30


def test_magic_weapon_is_a_bonus_action(registry, cfg):
    ally = make_fighter(registry, "ally")
    monsters = [mon("goblin_1", "goblin_warrior", "door")]
    hero = mage(registry, "magic_weapon")
    engine = engine_of(registry, cfg, hero, monsters=monsters, extra=[ally])
    engine.perform("wiz", "cast:magic_weapon:2:ally")
    turn = part(engine, "wiz").turn
    assert (turn.bonus, turn.action) == (False, True)


def test_ray_of_enfeeblement_failed_save_weakens_the_targets_attacks(registry, cfg):
    # Тел 5 < 13 -- провал; гоблин бьёт с помехой (19, 18 -> 18 + 4 попадает), урон
    # 1d6 (5) + 2 - 1d8 (3) = 4, затем проверка концентрации волшебника (15)
    engine = engine_of(
        registry, cfg, mage(registry, "ray_of_enfeeblement"),
        ScriptedRng(d20=[5, 19, 18, 15], d6=[5], d8=[3]),
        monsters=[mon("goblin_1", "goblin_warrior", "door")],
    )
    engine.perform("wiz", "cast:ray_of_enfeeblement:2:goblin_1")
    engine.perform("goblin_1", "attack:скимитар:wiz")
    assert hp(engine, "wiz") == 8 - 4


def test_ray_of_enfeeblement_disadvantage_makes_a_low_roll_miss(registry, cfg):
    rng = ScriptedRng(d20=[5, 19, 3])
    engine = engine_of(
        registry, cfg, mage(registry, "ray_of_enfeeblement"), rng,
        monsters=[mon("goblin_1", "goblin_warrior", "door")],
    )
    engine.perform("wiz", "cast:ray_of_enfeeblement:2:goblin_1")
    engine.perform("goblin_1", "attack:скимитар:wiz")
    assert rng.left("d20") == 0
    assert hp(engine, "wiz") == 8


def test_beacon_of_hope_makes_healing_word_roll_maximum(registry, cfg):
    # Лечащее слово 2d4: максимум 8 + Инт +3, без бросков (пустой ScriptedRng)
    ally = make_fighter(registry, "ally")
    hero = mage(registry, "beacon_of_hope", "healing_word")
    engine = idle(registry, cfg, hero, extra=[ally])
    engine.heroes["ally"].creature.hp_max = 40
    set_hp(engine, "ally", 1)
    engine.perform("wiz", "cast:beacon_of_hope:3:ally")
    pass_turns(engine, 3)
    engine.start_turn("wiz")
    engine.perform("wiz", "cast:healing_word:1:ally")
    assert hp(engine, "ally") == 1 + 8 + 3


def test_healing_word_without_beacon_rolls_dice(registry, cfg):
    ally = make_fighter(registry, "ally")
    engine = engine_of(
        registry, cfg, mage(registry, "healing_word"), ScriptedRng(d4=[1, 1]), extra=[ally],
    )
    set_hp(engine, "ally", 1)
    engine.perform("wiz", "cast:healing_word:1:ally")
    assert hp(engine, "ally") == 1 + 2 + 3


# utility

def test_utility_cantrip_spends_the_action_but_not_a_slot(registry, cfg):
    hero = mage(registry, cantrips=["prestidigitation"])
    engine = engine_of(registry, cfg, hero)
    assert "cast:prestidigitation:0:" in option_ids(engine, "wiz")
    engine.perform("wiz", "cast:prestidigitation:0:")
    assert part(engine, "wiz").turn.action is False
    assert slot(engine, 1) == 4


def test_instant_utility_spell_leaves_no_effect_on_the_caster(registry, cfg):
    # Послание (message) без срока: ActiveEffect(kind="spell") не нужен
    hero = mage(registry, cantrips=["message"])
    engine = engine_of(registry, cfg, hero)
    engine.perform("wiz", "cast:message:0:")
    assert part(engine, "wiz").turn.action is False
    assert [e for e in creature(engine, "wiz").active_effects if e.kind == "spell"] == []


def test_utility_spell_logs_its_text(registry, cfg):
    hero = mage(registry, cantrips=["prestidigitation"])
    engine = engine_of(registry, cfg, hero)
    engine.perform("wiz", "cast:prestidigitation:0:")
    name = registry.get("spell", "prestidigitation").name
    assert f"Лиэль читает {name}" in engine.state.log
    assert any("Маг творит мелкие чудеса" in line for line in engine.state.log)


def test_spell_with_a_long_casting_time_is_not_offered_in_combat(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "alarm", "prayer_of_healing"))
    assert cast_ids(engine, "alarm") == []
    assert cast_ids(engine, "prayer_of_healing") == []


# Пощада умирающих, Нанесение ран, Лечащее слово по лежачему

def test_spare_the_dying_is_offered_for_a_dying_ally_in_reach_only(registry, cfg):
    ally = make_fighter(registry, "ally")
    engine = engine_of(registry, cfg, mage(registry, cantrips=["spare_the_dying"]), extra=[ally])
    assert cast_ids(engine, "spare_the_dying") == []
    down_hero(engine, "ally")
    assert cast_ids(engine, "spare_the_dying") == ["cast:spare_the_dying:0:ally"]


def test_spare_the_dying_is_not_offered_beyond_15_feet(registry, cfg):
    ally = make_fighter(registry, "ally")
    engine = engine_of(
        registry, cfg, mage(registry, cantrips=["spare_the_dying"]), extra=[(ally, "hall")],
    )
    down_hero(engine, "ally")
    assert cast_ids(engine, "spare_the_dying") == []


def test_spare_the_dying_stabilizes_and_clears_the_death_saves(registry, cfg):
    ally = make_fighter(registry, "ally")
    engine = engine_of(registry, cfg, mage(registry, cantrips=["spare_the_dying"]), extra=[ally])
    down_hero(engine, "ally")
    saves = engine.heroes["ally"].creature.death_saves
    saves.failures = 2
    engine.perform("wiz", "cast:spare_the_dying:0:ally")
    assert (saves.stable, saves.failures, saves.successes) == (True, 0, 0)
    assert hp(engine, "ally") == 0


def test_spare_the_dying_is_not_offered_for_a_dead_ally(registry, cfg):
    ally = make_fighter(registry, "ally")
    engine = engine_of(registry, cfg, mage(registry, cantrips=["spare_the_dying"]), extra=[ally])
    down_hero(engine, "ally")
    part(engine, "ally").status = "dead"
    assert cast_ids(engine, "spare_the_dying") == []


def test_spare_the_dying_ignores_a_downed_enemy(registry, cfg):
    ally = make_fighter(registry, "ally")
    engine = engine_of(
        registry, cfg, mage(registry, cantrips=["spare_the_dying"]), extra=[ally],
        monsters=[mon("goblin_1", "goblin_warrior", "door")],
    )
    down_hero(engine, "ally")
    part(engine, "goblin_1").status = "down"
    assert cast_ids(engine, "spare_the_dying") == ["cast:spare_the_dying:0:ally"]


def test_healing_word_lifts_a_downed_ally(registry, cfg):
    ally = make_fighter(registry, "ally")
    engine = engine_of(
        registry, cfg, mage(registry, "healing_word"), ScriptedRng(d4=[2, 2]), extra=[ally],
    )
    down_hero(engine, "ally")
    engine.perform("wiz", "cast:healing_word:1:ally")
    assert hp(engine, "ally") == 2 + 2 + 3
    assert part(engine, "ally").status == "active"


def test_inflict_wounds_failed_con_save_deals_full_necrotic_damage(registry, cfg):
    engine = engine_of(
        registry, cfg, mage(registry, "inflict_wounds"), ScriptedRng(d20=[5], d10=[6, 7]),
        monsters=[mon("goblin_1", "goblin_warrior", "door")],
    )
    engine.perform("wiz", "cast:inflict_wounds:1:goblin_1")
    assert hp(engine, "goblin_1") == 30 - 13


def test_inflict_wounds_passed_con_save_deals_half(registry, cfg):
    engine = engine_of(
        registry, cfg, mage(registry, "inflict_wounds"), ScriptedRng(d20=[15], d10=[6, 7]),
        monsters=[mon("goblin_1", "goblin_warrior", "door")],
    )
    engine.perform("wiz", "cast:inflict_wounds:1:goblin_1")
    assert hp(engine, "goblin_1") == 30 - 13 // 2


def test_thunderwave_second_circle_rolls_a_die_more(registry, cfg):
    engine = engine_of(
        registry, cfg, mage(registry, "thunderwave"), ScriptedRng(d20=[15], d8=[4, 4, 4]),
        monsters=[mon("goblin_1", "goblin_warrior", "door")],
    )
    engine.perform("wiz", "cast:thunderwave:2:door")
    assert hp(engine, "goblin_1") == 30 - 12 // 2
    assert slot(engine, 2) == 2


# Ледяной нож, Порыв ветра

def test_ice_knife_hit_deals_piercing_and_a_cold_burst_to_the_zone(registry, cfg):
    # попадание 1d10 = 5; взрыв 2d6 = 6: гоблин 1 проваливает Лов (6), гоблин 2 проходит (3)
    engine = engine_of(
        registry, cfg, mage(registry, "ice_knife"),
        ScriptedRng(d20=[12, 5, 15], d10=[5], d6=[3, 3]), monsters=TWO_GOBLINS,
    )
    engine.perform("wiz", "cast:ice_knife:1:goblin_1")
    assert hp(engine, "goblin_1") == 30 - 5 - 6
    assert hp(engine, "goblin_2") == 30 - 3


def test_ice_knife_miss_still_bursts(registry, cfg):
    engine = engine_of(
        registry, cfg, mage(registry, "ice_knife"), ScriptedRng(d20=[2, 5], d6=[3, 3]),
    )
    engine.perform("wiz", "cast:ice_knife:1:goblin_1")
    assert hp(engine, "goblin_1") == 30 - 6


def test_gust_of_wind_failed_str_save_pushes_without_damage(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "gust_of_wind"), ScriptedRng(d20=[5]))
    engine.perform("wiz", "cast:gust_of_wind:2:hall")
    assert part(engine, "goblin_1").zone_id != "hall"
    assert hp(engine, "goblin_1") == 30


def test_gust_of_wind_passed_save_does_not_push(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "gust_of_wind"), ScriptedRng(d20=[15]))
    engine.perform("wiz", "cast:gust_of_wind:2:hall")
    assert part(engine, "goblin_1").zone_id == "hall"


# Усыпление и урон

def test_damage_wakes_a_sleeping_target_and_ends_the_spell(registry, cfg):
    # Усыпление: провал, провал повтора -- без сознания; союзник бьёт гоблина (преимущество и
    # крит по бессознательному в ближнем бою: два d20, две кости урона на каждую d8)
    ally = make_fighter(registry, "ally")
    engine = idle(
        registry, cfg, mage(registry, "sleep"), ScriptedRng(d20=[5, 5, 10, 10], d8=[4, 4]),
        monsters=[mon("goblin_1", "goblin_warrior", "door")], extra=[ally],
    )
    engine.perform("wiz", "cast:sleep:1:goblin_1")
    pass_turns(engine, 3)
    assert "unconscious" in conditions(engine, "goblin_1")
    engine.perform("ally", "attack:longsword:goblin_1")
    assert "unconscious" not in conditions(engine, "goblin_1")
    assert "incapacitated" not in conditions(engine, "goblin_1")
    assert "prone" in conditions(engine, "goblin_1")
    assert not [e for e in creature(engine, "goblin_1").active_effects if e.kind == "held"]
    assert any("боль" in line or "просыпается" in line for line in engine.state.log)


def test_target_woken_from_sleep_stands_up_in_its_turn_spending_move(registry, cfg):
    ally = make_fighter(registry, "ally")
    engine = idle(
        registry, cfg, mage(registry, "sleep"), ScriptedRng(d20=[5, 5, 10, 10], d8=[4, 4]),
        monsters=[mon("goblin_1", "goblin_warrior", "door")], extra=[ally],
    )
    engine.perform("wiz", "cast:sleep:1:goblin_1")
    pass_turns(engine, 3)
    engine.perform("ally", "attack:longsword:goblin_1")
    assert "prone" in conditions(engine, "goblin_1")
    engine.start_turn("goblin_1")
    assert "prone" not in conditions(engine, "goblin_1")
    assert part(engine, "goblin_1").turn.move == 0


def test_magic_weapon_damage_log_names_the_spell(registry, cfg):
    ally = make_fighter(registry, "ally")
    monsters = [mon("goblin_1", "goblin_warrior", "door")]
    engine = engine_of(
        registry, cfg, mage(registry, "magic_weapon"), ScriptedRng(d20=[9], d8=[4]),
        monsters=monsters, extra=[ally],
    )
    engine.perform("wiz", "cast:magic_weapon:2:ally")
    engine.perform("ally", "attack:longsword:goblin_1")
    name = registry.get("spell", "magic_weapon").name
    assert any(f"+1 к урону ({name})" in line for line in engine.state.log)
    assert not any("(magic_weapon)" in line for line in engine.state.log)


# Защита от яда (решение 61, Р40 а): сопротивление и здоровому союзнику

def poison_ward_engine(registry, cfg):
    ally = make_fighter(registry, "ally")
    return engine_of(registry, cfg, mage(registry, "protection_from_poison"), extra=[ally])


def test_protection_from_poison_is_offered_for_a_healthy_ally(registry, cfg):
    engine = poison_ward_engine(registry, cfg)
    assert "cast:protection_from_poison:2:ally" in option_ids(engine, "wiz")


def test_protection_from_poison_gives_poison_resistance_for_an_hour(registry, cfg):
    engine = poison_ward_engine(registry, cfg)
    start = engine.world.clock.now_s
    engine.perform("wiz", "cast:protection_from_poison:2:ally")
    resist = [e for e in creature(engine, "ally").active_effects if e.kind == "resist"]
    assert [e.params["damage_type"] for e in resist] == ["poison"]
    assert resist[0].expires.value == start + 3600


def test_protection_from_poison_on_a_healthy_ally_logs_no_removal(registry, cfg):
    engine = poison_ward_engine(registry, cfg)
    engine.perform("wiz", "cast:protection_from_poison:2:ally")
    assert not any("снимает" in line for line in engine.state.log)


# Фокусы: метка до now+3600, при повторе одна

def test_prestidigitation_puts_a_one_hour_spell_mark(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, cantrips=["prestidigitation"]))
    start = engine.world.clock.now_s
    engine.perform("wiz", "cast:prestidigitation:0:")
    marks = [e for e in creature(engine, "wiz").active_effects if e.kind == "spell"]
    assert [(e.id, e.expires.value) for e in marks] == [("prestidigitation", start + 3600)]


def test_repeated_prestidigitation_keeps_a_single_mark(registry, cfg):
    engine = idle(registry, cfg, mage(registry, cantrips=["prestidigitation"]))
    engine.perform("wiz", "cast:prestidigitation:0:")
    pass_turns(engine, 2)
    engine.start_turn("wiz")
    engine.perform("wiz", "cast:prestidigitation:0:")
    marks = [e for e in creature(engine, "wiz").active_effects if e.kind == "spell"]
    assert len(marks) == 1


# Порыв ветра держит концентрацию (решение 60)

def test_gust_of_wind_takes_concentration_for_a_minute(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "gust_of_wind"), ScriptedRng(d20=[15]))
    engine.perform("wiz", "cast:gust_of_wind:2:hall")
    assert engine.heroes["wiz"].creature.concentration.spell_id == "gust_of_wind"


def test_gust_of_wind_drops_the_previous_concentration(registry, cfg):
    ally = make_fighter(registry, "ally")
    engine = idle(
        registry, cfg, mage(registry, "bless", "gust_of_wind"), ScriptedRng(d20=[15]),
        extra=[ally],
    )
    engine.perform("wiz", "cast:bless:1:ally")
    assert [e for e in creature(engine, "ally").active_effects if e.id == "bless"]
    pass_turns(engine, 3)
    engine.start_turn("wiz")
    engine.perform("wiz", "cast:gust_of_wind:2:hall")
    assert engine.heroes["wiz"].creature.concentration.spell_id == "gust_of_wind"
    assert not [e for e in creature(engine, "ally").active_effects if e.id == "bless"]


# Р36 (а): Волшебное оружие даёт +1 и к броску атаки заклинанием

def test_magic_weapon_adds_1_to_the_casters_own_spell_attack(registry, cfg):
    # Огненная стрела +5: 9 + 5 = 14 < КД 15; с Волшебным оружием 15 -- попадание
    hero = mage(registry, "magic_weapon", cantrips=["fire_bolt"])
    engine = engine_of(registry, cfg, hero, ScriptedRng(d20=[9], d10=[5]))
    engine.perform("wiz", "cast:magic_weapon:2:wiz")
    engine.perform("wiz", "cast:fire_bolt:0:goblin_1")
    assert hp(engine, "goblin_1") == 25


def test_the_same_spell_attack_misses_without_magic_weapon(registry, cfg):
    hero = mage(registry, cantrips=["fire_bolt"])
    engine = engine_of(registry, cfg, hero, ScriptedRng(d20=[9]))
    engine.perform("wiz", "cast:fire_bolt:0:goblin_1")
    assert hp(engine, "goblin_1") == 30


# Р37 (а): «читает» -> «больше не скрыт» -> эффект; Невидимость остаётся

def test_invisibility_cast_from_hiding_keeps_the_spell_invisibility(registry, cfg):
    engine = engine_of(registry, cfg, mage(registry, "invisibility"))
    creature(engine, "wiz").conditions.append(AppliedCondition(id="invisible", source="hidden"))
    engine.perform("wiz", "cast:invisibility:2:wiz")
    sources = [c.source for c in creature(engine, "wiz").conditions if c.id == "invisible"]
    assert sources == ["invisibility"]
    log = engine.state.log
    cast_at = next(i for i, line in enumerate(log) if "читает" in line)
    hidden_at = next(i for i, line in enumerate(log) if "больше не скрыт" in line)
    effect_at = next(i for i, line in enumerate(log) if "Невидимость на" in line)
    assert cast_at < hidden_at < effect_at
