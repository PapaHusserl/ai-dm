# К3б П1 (docs/plan-k3b.md, «Тесты» П1, решения 10, 14): зоны и защита в бою.
#   Тьма (концентрация): атаки в зону и из неё с помехой; Дневной свет (не концентрация) снимает
#     Тьму зоны; Тьма гаснет с концентрацией.
#   Тишина: герой в зоне тишины не колдует (cast_options пусто), урон громом по участнику зоны --
#     иммунитет; герой вне зоны колдует.
#   Ледяной шторм: в начале хода участника зоны -- спасбросок Лов, провал -- prone; атаки в зону
#     с помехой.
#   Подвал меню: cast.foot_notes -- при Тишине [SILENCE_NOTE], иначе «<имя> — пока недоступно в
#     бою» по заклинаниям без механики.
#   Магический круг (решение 16, Р-К3б-7 б): в бою пункта нет; каст вне боя и привязка к зоне на
#     start_combat -- tests/unit/protocol/test_k3b_p1_magic_circle.py.
#   Видение невидимого: атака по невидимой цели без помехи.
#   Святилище: монстр при выборе цели бросает Мдр (СЛ заклинателя); провал -- атака потеряна,
#     действие потрачено, лог «Святилище: … не решается»; успех -- атака идёт; защищаемый атакует
#     (оружием или заклинанием) -- эффект снят.
#   Защитные узы: КД +1, спасбросок +1, урон по цели делится: цель получает половину (сопротивление
#     всему), заклинатель -- столько же (dealt.final, SRD «same amount»; урон 10 → 5 и 5);
#     заклинатель на 0 HP -- эффект снят.
from combat_kit import (
    ScriptedRng,
    creature,
    hp,
    make_cleric,
    make_fighter,
    mon,
    option_ids,
    part,
    set_hp,
)
from test_cast_p3a import GOBLIN, cast_ids, conditions, effects, engine_of, idle, mage, pass_turns

from ai_dm.combat import bond, downed
from ai_dm.combat.actions import cast_guards
from ai_dm.combat.zone_effects import (
    bind_circle,
    obscured,
    place_circle,
    zone_effects,
    zone_notes,
)
from ai_dm.rules.results import Rejected
from ai_dm.state.creature import ActiveEffect, AppliedCondition, Expiry

SHOOT_WIZ = "attack:короткий_лук:wiz"
SHOOT_CLER = "attack:короткий_лук:cler"


def priest(registry, *spells, cantrips=()):
    hero = make_cleric(registry)
    hero.sheet.prepared_of().extend(spells)
    hero.sheet.known_of().extend(cantrips)
    return hero


def do_cast(engine, ref, spell_id, target=""):
    # цель без выбора (на себя) в id — либо ref заклинателя, либо пусто
    found = cast_ids(engine, spell_id, ref)
    ids = [i for i in found if i.endswith(f":{target}")] or [i for i in found if i.endswith(":")]
    assert ids, f"нет пункта {spell_id} → {target!r}: {found}"
    result = engine.perform(ref, ids[0])
    assert not isinstance(result, Rejected)
    return result


def cast_any(engine, ref="wiz"):
    return [i for i in option_ids(engine, ref) if i.startswith("cast:")]


def log_has(engine, *words):
    return any(all(w in line for w in words) for line in engine.state.log)


# Тьма

def dark_engine(registry, cfg, rng, *spells):
    return idle(
        registry, cfg, mage(registry, "darkness", *spells, cantrips=["fire_bolt"]), rng,
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )


def test_darkness_marks_the_zone(registry, cfg):
    engine = dark_engine(registry, cfg, ScriptedRng())
    do_cast(engine, "wiz", "darkness", "hall")
    assert len(zone_effects(engine, "hall", "darkness")) == 1
    assert obscured(engine, "hall") is True
    assert obscured(engine, "door") is False


def test_attack_from_a_dark_zone_has_disadvantage(registry, cfg):
    # d20 19 и 3: худший 3 + 4 = 7 < КД 11
    rng = ScriptedRng(d20=[19, 3])
    engine = dark_engine(registry, cfg, rng)
    do_cast(engine, "wiz", "darkness", "hall")
    engine.perform("goblin_1", SHOOT_WIZ)
    assert rng.left("d20") == 0
    assert hp(engine, "wiz") == 8


def test_attack_into_a_dark_zone_has_disadvantage(registry, cfg):
    # d20 19 и 2: худший 2 + 5 = 7 < КД гоблина 15
    rng = ScriptedRng(d20=[19, 2])
    engine = dark_engine(registry, cfg, rng)
    do_cast(engine, "wiz", "darkness", "hall")
    pass_turns(engine, 2)
    engine.start_turn("wiz")
    engine.perform("wiz", "cast:fire_bolt:0:goblin_1")
    assert rng.left("d20") == 0
    assert hp(engine, "goblin_1") == 30


def test_darkness_in_another_zone_changes_nothing(registry, cfg):
    # один d20 атаки: 19 + 4 попадает, затем проверка концентрации
    rng = ScriptedRng(d20=[19, 18], d6=[3])
    engine = dark_engine(registry, cfg, rng)
    do_cast(engine, "wiz", "darkness", "balcony")
    engine.perform("goblin_1", SHOOT_WIZ)
    assert rng.left("d20") == 0
    assert hp(engine, "wiz") < 8


def test_darkness_ends_with_concentration(registry, cfg):
    engine = dark_engine(registry, cfg, ScriptedRng())
    do_cast(engine, "wiz", "darkness", "hall")
    engine.drop_concentration_effects("wiz")
    assert obscured(engine, "hall") is False


def test_daylight_removes_darkness_from_its_zone(registry, cfg):
    # Дневной свет -- не концентрация: Тьма снята эффектом, а не сменой концентрации; концентрация
    # на Тьме кончилась вместе с ней, поэтому после попадания проверки Тел нет (один d20 -- атака)
    rng = ScriptedRng(d20=[19], d6=[3])
    engine = dark_engine(registry, cfg, rng, "daylight")
    do_cast(engine, "wiz", "darkness", "hall")
    pass_turns(engine, 2)
    engine.start_turn("wiz")
    do_cast(engine, "wiz", "daylight", "hall")
    assert zone_effects(engine, "hall", "darkness") == []
    assert obscured(engine, "hall") is False
    engine.perform("goblin_1", SHOOT_WIZ)
    assert rng.left("d20") == 0
    assert hp(engine, "wiz") < 8


def test_daylight_in_another_zone_keeps_darkness(registry, cfg):
    engine = dark_engine(registry, cfg, ScriptedRng(), "daylight")
    do_cast(engine, "wiz", "darkness", "hall")
    pass_turns(engine, 2)
    engine.start_turn("wiz")
    do_cast(engine, "wiz", "daylight", "balcony")
    assert obscured(engine, "hall") is True
    assert creature(engine, "wiz").concentration.spell_id == "darkness"


def test_daylight_ends_the_concentration_on_the_darkness_it_removed(registry, cfg):
    # ответ на ревью мамы 3: Тьма рассеяна -- заклинание кончилось, концентрации нет
    engine = dark_engine(registry, cfg, ScriptedRng(), "daylight")
    do_cast(engine, "wiz", "darkness", "hall")
    pass_turns(engine, 2)
    engine.start_turn("wiz")
    do_cast(engine, "wiz", "daylight", "hall")
    assert creature(engine, "wiz").concentration is None
    assert zone_effects(engine, "hall", "darkness") == []


# Тишина

def silence_engine(registry, cfg, rng=None):
    return idle(
        registry, cfg, mage(registry, "silence", cantrips=["fire_bolt"]), rng or ScriptedRng(),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )


def test_hero_in_the_silenced_zone_has_no_cast_options(registry, cfg):
    engine = silence_engine(registry, cfg)
    do_cast(engine, "wiz", "silence", "door")
    pass_turns(engine, 2)
    engine.start_turn("wiz")
    assert cast_any(engine) == []


def test_hero_outside_the_silenced_zone_still_casts(registry, cfg):
    engine = silence_engine(registry, cfg)
    do_cast(engine, "wiz", "silence", "hall")
    pass_turns(engine, 2)
    engine.start_turn("wiz")
    assert "cast:fire_bolt:0:goblin_1" in cast_any(engine)


def test_thunder_damage_in_the_silenced_zone_is_nothing(registry, cfg):
    engine = silence_engine(registry, cfg)
    do_cast(engine, "wiz", "silence", "hall")
    dealt = engine.damage("goblin_1", 8, "thunder")
    assert dealt.final == 0
    assert any("Иммунитет" in note for note in dealt.notes)
    assert hp(engine, "goblin_1") == 30


def test_thunder_damage_outside_the_silenced_zone_is_full(registry, cfg):
    engine = silence_engine(registry, cfg)
    do_cast(engine, "wiz", "silence", "balcony")
    assert engine.damage("goblin_1", 8, "thunder").final == 8


def test_other_damage_in_the_silenced_zone_is_full(registry, cfg):
    engine = silence_engine(registry, cfg)
    do_cast(engine, "wiz", "silence", "hall")
    assert engine.damage("goblin_1", 8, "fire").final == 8


def test_silence_ends_with_concentration(registry, cfg):
    engine = silence_engine(registry, cfg)
    do_cast(engine, "wiz", "silence", "hall")
    engine.drop_concentration_effects("wiz")
    assert engine.damage("goblin_1", 8, "thunder").final == 8


# Ледяной шторм

def sleet_engine(registry, cfg, rng):
    return idle(
        registry, cfg, mage(registry, "sleet_storm", cantrips=["fire_bolt"]), rng,
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )


def test_failed_dex_save_in_the_sleet_zone_knocks_prone(registry, cfg):
    # Лов гоблина +2: 3 + 2 = 5 < СЛ 13
    engine = sleet_engine(registry, cfg, ScriptedRng(d20=[3]))
    do_cast(engine, "wiz", "sleet_storm", "hall")
    engine.start_turn("goblin_1")
    assert "prone" in conditions(engine, "goblin_1")


def test_passed_dex_save_in_the_sleet_zone_keeps_standing(registry, cfg):
    engine = sleet_engine(registry, cfg, ScriptedRng(d20=[18]))
    do_cast(engine, "wiz", "sleet_storm", "hall")
    engine.start_turn("goblin_1")
    assert "prone" not in conditions(engine, "goblin_1")


def test_no_sleet_save_outside_the_zone(registry, cfg):
    engine = sleet_engine(registry, cfg, ScriptedRng())
    do_cast(engine, "wiz", "sleet_storm", "balcony")
    engine.start_turn("goblin_1")
    assert "prone" not in conditions(engine, "goblin_1")


def test_attack_into_the_sleet_zone_has_disadvantage(registry, cfg):
    rng = ScriptedRng(d20=[19, 2])
    engine = sleet_engine(registry, cfg, rng)
    do_cast(engine, "wiz", "sleet_storm", "hall")
    engine.start_turn("wiz")
    engine.perform("wiz", "cast:fire_bolt:0:goblin_1")
    assert rng.left("d20") == 0
    assert hp(engine, "goblin_1") == 30


# Магический круг

# Решение 16 (Р-К3б-7 б): круг читается вне боя, поведение в бою -- test_k3b_p1_magic_circle.py
# (tests/unit/protocol); здесь -- в бою пункта круга нет (время сотворения 1 минута).

def test_magic_circle_has_no_option_in_combat(registry, cfg):
    engine = idle(
        registry, cfg, mage(registry, "magic_circle"), ScriptedRng(), hero_zone="hall",
        monsters=[mon("skel_1", "skeleton", "door")],
    )
    assert cast_ids(engine, "magic_circle") == []


# Подвал меню (cast.foot_notes -- готовые строки)

def test_silenced_hero_gets_only_the_silence_footer(registry, cfg):
    from ai_dm.combat.actions import cast

    engine = silence_engine(registry, cfg)
    do_cast(engine, "wiz", "silence", "door")
    pass_turns(engine, 2)
    engine.start_turn("wiz")
    assert cast.foot_notes(engine, "wiz") == [cast.SILENCE_NOTE]
    assert cast.SILENCE_NOTE == "Тишина — заклинания недоступны"


def test_silence_footer_replaces_inert_lines(registry, cfg):
    from ai_dm.combat.actions import cast

    hero = mage(registry, "silence", "speak_with_animals", cantrips=["fire_bolt"])
    engine = idle(registry, cfg, hero, ScriptedRng(), monsters=GOBLIN)
    do_cast(engine, "wiz", "silence", "door")
    pass_turns(engine, 2)
    engine.start_turn("wiz")
    assert cast.foot_notes(engine, "wiz") == [cast.SILENCE_NOTE]


def test_footer_lists_inert_spells_as_ready_lines_outside_silence(registry, cfg):
    from ai_dm.combat.actions import cast

    hero = mage(registry, "speak_with_animals", cantrips=["fire_bolt"])
    engine = idle(registry, cfg, hero, ScriptedRng(), monsters=GOBLIN)
    name = registry.get("spell", "speak_with_animals").name
    assert cast.foot_notes(engine, "wiz") == [f"{name} — пока недоступно в бою"]


def test_footer_is_empty_without_inert_spells_and_silence(registry, cfg):
    from ai_dm.combat.actions import cast

    engine = idle(
        registry, cfg, mage(registry, cantrips=["fire_bolt"]), ScriptedRng(), monsters=GOBLIN
    )
    assert cast.foot_notes(engine, "wiz") == []


# Видение невидимого

def test_see_invisibility_removes_disadvantage_against_an_invisible_target(registry, cfg):
    rng = ScriptedRng(d20=[19], d10=[5])
    engine = idle(
        registry, cfg, mage(registry, "see_invisibility", cantrips=["fire_bolt"]), rng,
        monsters=GOBLIN,
    )
    do_cast(engine, "wiz", "see_invisibility", "wiz")
    engine.start_turn("wiz")
    creature(engine, "goblin_1").conditions.append(
        AppliedCondition(id="invisible", source="invisibility")
    )
    engine.perform("wiz", "cast:fire_bolt:0:goblin_1")
    assert rng.left("d20") == 0
    assert hp(engine, "goblin_1") == 25


# Святилище

def sanctuary_engine(registry, cfg, rng, monsters=GOBLIN, cantrips=()):
    engine = idle(
        registry, cfg, priest(registry, "sanctuary", cantrips=cantrips), rng, monsters=monsters,
    )
    do_cast(engine, "cler", "sanctuary", "cler")
    return engine


def test_failed_wisdom_save_loses_the_attack_on_the_sanctuary_hero(registry, cfg):
    # Мдр гоблина -1: 5 - 1 = 4 < СЛ 12; других бросков d20 нет -- атака потеряна
    rng = ScriptedRng(d20=[5])
    engine = sanctuary_engine(registry, cfg, rng)
    before = hp(engine, "cler")
    engine.perform("goblin_1", SHOOT_CLER)
    assert rng.left("d20") == 0
    assert hp(engine, "cler") == before
    assert part(engine, "goblin_1").turn.action is False
    assert log_has(engine, "Святилище", "не решается")


def test_passed_wisdom_save_lets_the_attack_through(registry, cfg):
    # Мдр: 18 - 1 = 17 >= 12; атака 19 + 4 попадает
    rng = ScriptedRng(d20=[18, 19], d6=[3])
    engine = sanctuary_engine(registry, cfg, rng)
    before = hp(engine, "cler")
    engine.perform("goblin_1", SHOOT_CLER)
    assert rng.left("d20") == 0
    assert hp(engine, "cler") < before


def test_sanctuary_does_not_protect_the_other_hero(registry, cfg):
    # защищён жрец, а волшебника гоблин бьёт без спасброска
    rng = ScriptedRng(d20=[19], d6=[3])
    cleric = priest(registry, "sanctuary")
    wizard = mage(registry)
    engine = idle(registry, cfg, cleric, rng, monsters=GOBLIN, extra=[wizard])
    do_cast(engine, "cler", "sanctuary", "cler")
    engine.perform("goblin_1", SHOOT_WIZ)
    assert rng.left("d20") == 0
    assert hp(engine, "wiz") < 8


def test_attacking_with_a_weapon_ends_sanctuary(registry, cfg):
    # жрец-солдат с Savage Attacker бросает кубики урона дважды
    rng = ScriptedRng(d20=[19], d6=[3, 3])
    engine = sanctuary_engine(
        registry, cfg, rng, monsters=[mon("goblin_1", "goblin_warrior", "door")]
    )
    assert effects(engine, "cler", "sanctuary")
    attack = [
        i for i in option_ids(engine, "cler")
        if i.startswith("attack:") and i.endswith(":goblin_1")
    ]
    engine.perform("cler", attack[0])
    assert effects(engine, "cler", "sanctuary") == []
    assert log_has(engine, "Святилище спадает")


def boss_sanctuary(registry, cfg, rng):
    return sanctuary_engine(
        registry, cfg, rng, monsters=[mon("boss_1", "goblin_boss", "door")]
    )


def test_sanctuary_rolls_for_every_attack_of_a_multiattack(registry, cfg):
    # Мдр провал оба раза: обе атаки потеряны, действие потрачено
    rng = ScriptedRng(d20=[1, 1])
    engine = boss_sanctuary(registry, cfg, rng)
    before = hp(engine, "cler")
    engine.perform("boss_1", "multiattack")
    assert rng.left("d20") == 0
    assert hp(engine, "cler") == before
    assert len([x for x in engine.state.log if "Святилище" in x and "не решается" in x]) == 2
    assert part(engine, "boss_1").turn.action is False


def test_multiattack_under_sanctuary_lets_one_attack_through(registry, cfg):
    # первая атака: Мдр провал; вторая: Мдр успех и попадание 19 + 4
    rng = ScriptedRng(d20=[1, 18, 19], d6=[3])
    engine = boss_sanctuary(registry, cfg, rng)
    before = hp(engine, "cler")
    engine.perform("boss_1", "multiattack")
    assert rng.left("d20") == 0
    assert hp(engine, "cler") < before
    assert len([x for x in engine.state.log if "Святилище" in x and "не решается" in x]) == 1


def test_sanctuary_hero_leaving_is_not_hit_by_the_opportunity_attack(registry, cfg):
    rng = ScriptedRng(d20=[1])
    engine = sanctuary_engine(registry, cfg, rng)
    engine.state.participants[1].zone_id = "door"
    before = hp(engine, "cler")
    engine.perform("cler", "move:hall")
    assert rng.left("d20") == 0
    assert hp(engine, "cler") == before
    assert part(engine, "goblin_1").turn.reaction is False
    assert log_has(engine, "провоцированная атака")
    assert log_has(engine, "Святилище", "не решается")


def test_sanctuary_hero_making_an_opportunity_attack_loses_sanctuary(registry, cfg):
    rng = ScriptedRng(d20=[19], d6=[3, 3])
    engine = sanctuary_engine(
        registry, cfg, rng, monsters=[mon("goblin_1", "goblin_warrior", "door")]
    )
    engine.perform("goblin_1", "move:hall")
    assert effects(engine, "cler", "sanctuary") == []
    assert log_has(engine, "Святилище спадает")


def test_hostile_spell_ends_sanctuary(registry, cfg):
    rng = ScriptedRng(d20=[5], d8=[4])
    engine = sanctuary_engine(
        registry, cfg, rng, monsters=[mon("goblin_1", "goblin_warrior", "door")],
        cantrips=["sacred_flame"],
    )
    engine.start_turn("cler")
    do_cast(engine, "cler", "sacred_flame", "goblin_1")
    assert effects(engine, "cler", "sanctuary") == []


# Защитные узы

def bond_engine(registry, cfg, rng=None):
    ally = make_fighter(registry, "ally")
    engine = engine_of(
        registry, cfg, mage(registry, "warding_bond"), rng or ScriptedRng(d20=[10, 10]),
        extra=[ally],
    )
    return engine


def test_warding_bond_adds_one_to_armor_class(registry, cfg):
    engine = bond_engine(registry, cfg)
    before = engine.armor_class("ally")
    do_cast(engine, "wiz", "warding_bond", "ally")
    assert engine.armor_class("ally") == before + 1


def test_warding_bond_adds_one_to_saving_throws(registry, cfg):
    engine = bond_engine(registry, cfg)
    before = engine.save("ally", "dex", 15).total
    do_cast(engine, "wiz", "warding_bond", "ally")
    assert engine.save("ally", "dex", 15).total == before + 1


def test_warding_bond_halves_damage_to_the_target_and_shares_it_with_the_caster(registry, cfg):
    engine = bond_engine(registry, cfg)
    set_hp(engine, "wiz", 30)
    do_cast(engine, "wiz", "warding_bond", "ally")
    before = hp(engine, "ally")
    dealt = engine.damage("ally", 10, "slashing")
    downed.after_damage(engine, "ally", dealt, "goblin_1")
    assert hp(engine, "ally") == before - 5
    assert hp(engine, "wiz") == 25
    assert log_has(engine, "Защитные узы", "тоже получает")


def test_damage_to_the_caster_is_not_shared_back(registry, cfg):
    engine = bond_engine(registry, cfg)
    set_hp(engine, "wiz", 30)
    do_cast(engine, "wiz", "warding_bond", "ally")
    before = hp(engine, "ally")
    dealt = engine.damage("wiz", 6, "slashing")
    downed.after_damage(engine, "wiz", dealt, "goblin_1")
    assert hp(engine, "wiz") == 24
    assert hp(engine, "ally") == before


def test_bond_damage_to_the_caster_is_credited_to_the_original_attacker(registry, cfg):
    # «Ответы кабану П1» п. 6: last_hit_by заклинателя -- гоблин, а не подопечный
    engine = bond_engine(registry, cfg)
    set_hp(engine, "wiz", 30)
    do_cast(engine, "wiz", "warding_bond", "ally")
    dealt = engine.damage("ally", 10, "slashing")
    downed.after_damage(engine, "ally", dealt, "goblin_1")
    assert part(engine, "wiz").last_hit_by == "goblin_1"


def test_caster_dropped_by_the_bond_is_defeated_by_the_attackers_group(registry, cfg):
    engine = bond_engine(registry, cfg)
    set_hp(engine, "wiz", 4)
    do_cast(engine, "wiz", "warding_bond", "ally")
    dealt = engine.damage("ally", 10, "slashing")
    downed.after_damage(engine, "ally", dealt, "goblin_1")
    assert part(engine, "wiz").last_hit_by == "goblin_1"
    assert engine.state.defeat_group_id == "goblins"


def test_caster_at_zero_hp_loses_the_bond(registry, cfg):
    engine = bond_engine(registry, cfg)
    set_hp(engine, "wiz", 4)
    do_cast(engine, "wiz", "warding_bond", "ally")
    dealt = engine.damage("ally", 10, "slashing")
    downed.after_damage(engine, "ally", dealt, "goblin_1")
    assert hp(engine, "wiz") == 0
    assert effects(engine, "ally", "warding_bond") == []


# Разбор выживших мутантов П1

def ended(engine):
    return Expiry(kind="seconds", value=engine.world.clock.now_s)


def marker(source="wiz", expires=None):
    return ActiveEffect(
        id="marker", source=source, kind="resist", params={"damage_type": "fire"},
        expires=expires,
    )


def test_expired_darkness_effect_is_not_a_zone_effect(registry, cfg):
    engine = dark_engine(registry, cfg, ScriptedRng())
    creature(engine, "wiz").active_effects.append(
        ActiveEffect(
            id="darkness", source="wiz", kind="zone",
            params={"zone": "hall", "kind": "darkness"}, expires=ended(engine),
        )
    )
    assert zone_effects(engine, "hall", "darkness") == []


def test_zone_notes_name_only_the_obscuring_kind_present(registry, cfg):
    engine = dark_engine(registry, cfg, ScriptedRng())
    do_cast(engine, "wiz", "darkness", "hall")
    assert zone_notes(engine, "goblin_1", "wiz") == ["Тьма"]


def circle_engine(registry, cfg):
    engine = idle(
        registry, cfg, mage(registry, "magic_circle"), ScriptedRng(), hero_zone="hall",
        monsters=[mon("skel_1", "skeleton", "door")],
    )
    spell = registry.get("spell", "magic_circle")
    return engine, engine.heroes["wiz"], spell


def test_zone_notes_name_the_magic_circle(registry, cfg):
    engine, hero, spell = circle_engine(registry, cfg)
    now_s = engine.world.clock.now_s
    place_circle(hero, spell, now_s)
    bind_circle(hero, "hall", now_s)
    assert zone_notes(engine, "skel_1", "wiz") == ["Магический круг"]


def test_placed_circle_is_not_bound_to_a_zone(registry, cfg):
    engine, hero, spell = circle_engine(registry, cfg)
    place_circle(hero, spell, engine.world.clock.now_s)
    (effect,) = [e for e in hero.creature.active_effects if e.id == "magic_circle"]
    assert effect.params["zone"] == ""
    assert effect.params["kind"] == "circle"


def test_expired_circle_is_not_bound_to_a_zone(registry, cfg):
    engine, hero, spell = circle_engine(registry, cfg)
    now_s = engine.world.clock.now_s
    place_circle(hero, spell, now_s)
    bind_circle(hero, "hall", now_s + spell.duration_s)
    (effect,) = [e for e in hero.creature.active_effects if e.id == "magic_circle"]
    assert effect.params["zone"] == ""


def test_prone_from_the_sleet_remembers_the_spell(registry, cfg):
    engine = sleet_engine(registry, cfg, ScriptedRng(d20=[3]))
    do_cast(engine, "wiz", "sleet_storm", "hall")
    engine.start_turn("goblin_1")
    (prone,) = [c for c in creature(engine, "goblin_1").conditions if c.id == "prone"]
    assert prone.source == "sleet_storm"


def test_falling_in_the_sleet_is_logged(registry, cfg):
    engine = sleet_engine(registry, cfg, ScriptedRng(d20=[3]))
    do_cast(engine, "wiz", "sleet_storm", "hall")
    engine.start_turn("goblin_1")
    assert f"Ледяной шторм: {engine.name('goblin_1')} падает" in engine.state.log


def test_daylight_ends_other_effects_held_by_the_darkness_concentration(registry, cfg):
    engine = dark_engine(registry, cfg, ScriptedRng(), "daylight")
    do_cast(engine, "wiz", "darkness", "hall")
    pass_turns(engine, 2)
    engine.start_turn("wiz")
    creature(engine, "goblin_1").active_effects.append(
        marker(expires=Expiry(kind="concentration", owner="wiz"))
    )
    do_cast(engine, "wiz", "daylight", "hall")
    assert [e for e in creature(engine, "goblin_1").active_effects if e.id == "marker"] == []


def test_daylight_logs_the_zone_name(registry, cfg):
    engine = dark_engine(registry, cfg, ScriptedRng(), "daylight")
    do_cast(engine, "wiz", "darkness", "hall")
    pass_turns(engine, 2)
    engine.start_turn("wiz")
    do_cast(engine, "wiz", "daylight", "hall")
    name = registry.get("spell", "daylight").name
    assert f"{engine.name('wiz')}: {name} — Центр зала" in engine.state.log


def test_place_keeps_other_effects_of_the_target(registry, cfg):
    engine = bond_engine(registry, cfg)
    creature(engine, "ally").active_effects.append(marker())
    do_cast(engine, "wiz", "warding_bond", "ally")
    assert len(effects(engine, "ally", "marker")) == 1


def test_bond_effects_last_an_hour_of_world_time(registry, cfg):
    engine = bond_engine(registry, cfg)
    now_s = engine.world.clock.now_s
    do_cast(engine, "wiz", "warding_bond", "ally")
    found = effects(engine, "ally", "warding_bond")
    assert found
    assert all(e.expires == Expiry(kind="seconds", value=now_s + 3600) for e in found)


def test_place_ties_a_concentration_spell_to_its_caster(registry, cfg):
    engine = bond_engine(registry, cfg)
    spell = registry.get("spell", "darkness")
    cast_guards.place(engine, "wiz", spell, "ally", {"marker": {}})
    (effect,) = effects(engine, "ally", "darkness")
    assert effect.expires == Expiry(kind="concentration", owner="wiz")


def test_bond_armor_bonus_counts_as_magical(registry, cfg):
    engine = bond_engine(registry, cfg)
    do_cast(engine, "wiz", "warding_bond", "ally")
    (ac,) = [e for e in effects(engine, "ally", "warding_bond") if e.kind == "ac"]
    assert ac.params["magic"] is True


def test_sanctuary_ignores_an_expired_effect(registry, cfg):
    rng = ScriptedRng(d20=[19], d6=[3])
    engine = sanctuary_engine(registry, cfg, rng)
    for e in effects(engine, "cler", "sanctuary"):
        e.expires = ended(engine)
    before = hp(engine, "cler")
    engine.perform("goblin_1", SHOOT_CLER)
    assert rng.left("d20") == 0
    assert hp(engine, "cler") < before


def test_sanctuary_is_found_behind_another_effect(registry, cfg):
    rng = ScriptedRng(d20=[5])
    engine = sanctuary_engine(registry, cfg, rng)
    creature(engine, "cler").active_effects.insert(0, marker(source="x"))
    before = hp(engine, "cler")
    engine.perform("goblin_1", SHOOT_CLER)
    assert rng.left("d20") == 0
    assert hp(engine, "cler") == before
    assert log_has(engine, "Святилище", "не решается")


def test_sanctuary_log_names_both_sides(registry, cfg):
    engine = sanctuary_engine(registry, cfg, ScriptedRng(d20=[5]))
    engine.perform("goblin_1", SHOOT_CLER)
    line = f"Святилище: {engine.name('goblin_1')} не решается напасть на {engine.name('cler')}"
    assert line in engine.state.log


def test_every_enemy_in_the_zone_rolls_against_the_sanctuary(registry, cfg):
    rng = ScriptedRng(d20=[1, 1])
    engine = sanctuary_engine(
        registry, cfg, rng,
        monsters=[mon("g1", "goblin_warrior", "door"), mon("g2", "goblin_warrior", "door")],
    )
    engine.perform("cler", "move:hall")
    assert rng.left("d20") == 0
    assert part(engine, "g1").turn.reaction is False
    assert part(engine, "g2").turn.reaction is False


def test_bond_shares_even_a_single_point(registry, cfg):
    engine = bond_engine(registry, cfg)
    set_hp(engine, "wiz", 30)
    do_cast(engine, "wiz", "warding_bond", "ally")
    dealt = engine.damage("ally", 2, "slashing")
    assert dealt.final == 1
    downed.after_damage(engine, "ally", dealt, "goblin_1")
    assert hp(engine, "wiz") == 29


def test_expired_bond_shares_nothing(registry, cfg):
    engine = bond_engine(registry, cfg)
    set_hp(engine, "wiz", 30)
    do_cast(engine, "wiz", "warding_bond", "ally")
    for e in effects(engine, "ally", "warding_bond"):
        if e.kind == "bond":
            e.expires = ended(engine)
    dealt = engine.damage("ally", 10, "slashing")
    downed.after_damage(engine, "ally", dealt, "goblin_1")
    assert hp(engine, "wiz") == 30


def test_bond_is_found_behind_another_effect(registry, cfg):
    engine = bond_engine(registry, cfg)
    set_hp(engine, "wiz", 30)
    do_cast(engine, "wiz", "warding_bond", "ally")
    creature(engine, "ally").active_effects.insert(0, marker(source="x"))
    dealt = engine.damage("ally", 10, "slashing")
    downed.after_damage(engine, "ally", dealt, "goblin_1")
    assert hp(engine, "wiz") == 25


def two_bonds_engine(registry, cfg, first="ally2"):
    # на подопечном узы двух заклинателей: first (вручную, первым) и wiz
    ally2 = make_fighter(registry, "ally2")
    engine = engine_of(
        registry, cfg, mage(registry, "warding_bond"), ScriptedRng(d20=[10, 10]),
        extra=[make_fighter(registry, "ally"), ally2],
    )
    set_hp(engine, "wiz", 30)
    do_cast(engine, "wiz", "warding_bond", "ally")
    creature(engine, "ally").active_effects.insert(
        0, ActiveEffect(id="warding_bond", source=first, kind="bond")
    )
    return engine


def test_downed_caster_does_not_stop_other_bonds(registry, cfg):
    engine = two_bonds_engine(registry, cfg)
    part(engine, "ally2").status = "down"
    dealt = engine.damage("ally", 10, "slashing")
    downed.after_damage(engine, "ally", dealt, "goblin_1")
    assert hp(engine, "wiz") == 25


def test_events_of_every_bond_are_kept(registry, cfg):
    # первый заклинатель -- гоблин на 3 HP: узы убивают его (monster_died), второй -- здоровый wiz
    engine = two_bonds_engine(registry, cfg, first="goblin_1")
    set_hp(engine, "goblin_1", 3)
    dealt = engine.damage("ally", 10, "slashing")
    events = bond.share(engine, "ally", dealt, "ally")
    assert hp(engine, "wiz") == 25
    assert [e.type for e in events] == ["monster_died"]


def test_caster_left_with_one_hp_keeps_the_bond(registry, cfg):
    engine = bond_engine(registry, cfg)
    set_hp(engine, "wiz", 6)
    do_cast(engine, "wiz", "warding_bond", "ally")
    dealt = engine.damage("ally", 10, "slashing")
    downed.after_damage(engine, "ally", dealt, "goblin_1")
    assert hp(engine, "wiz") == 1
    assert effects(engine, "ally", "warding_bond") != []


def test_dropped_bond_leaves_foreign_bonds_and_own_other_effects(registry, cfg):
    engine = bond_engine(registry, cfg)
    ally = creature(engine, "ally")
    ally.active_effects += [
        ActiveEffect(id="warding_bond", source="wiz", kind="bond"),
        ActiveEffect(id="warding_bond", source="other", kind="bond"),
    ]
    creature(engine, "wiz").active_effects.append(marker(source="wiz"))
    bond.drop(engine, "wiz")
    assert [e.source for e in ally.active_effects] == ["other"]
    assert len(effects(engine, "wiz", "marker")) == 1


def test_expired_see_invisible_does_not_remove_the_disadvantage(registry, cfg):
    rng = ScriptedRng(d20=[19, 2])
    engine = idle(
        registry, cfg, mage(registry, cantrips=["fire_bolt"]), rng, monsters=GOBLIN,
    )
    creature(engine, "wiz").active_effects.append(
        ActiveEffect(id="see_invisibility", source="wiz", kind="see_invisible",
                     expires=ended(engine))
    )
    engine.start_turn("wiz")
    creature(engine, "goblin_1").conditions.append(
        AppliedCondition(id="invisible", source="invisibility")
    )
    engine.perform("wiz", "cast:fire_bolt:0:goblin_1")
    assert rng.left("d20") == 0
    assert hp(engine, "goblin_1") == 30
