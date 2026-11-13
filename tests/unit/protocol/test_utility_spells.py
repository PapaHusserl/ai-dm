# К3 П3б (docs/plan-k3.md, «Тесты» П3; решения 26, 40, 63): заклинания вне боя в protocol/handlers/
# utility_spells.py и ветки cast_spell:
#   * Помощь (max_hp): +5 к максимуму и текущим HP на 8 ч, повтор не складывается, срок заново,
#     откат по часам мира (advance_time) со строкой «Помощь кончилась: <имя> HP a/b»; метки
#     kind="spell" нет; круг выше базового -- bad_circle;
#   * defense: Невидимость -- состояние invisible с Expiry(concentration), концентрация; час без боя
#     снимает оба; Доспехи мага +3 на 8 ч без концентрации, в доспехе -- bad_target, ячейка цела;
#     Дубовая кора -- КД не ниже 17; Защита от энергии -- variant обязателен (bad_variant), резист
#     кончается с концентрацией; вариант у заклинания без variants игнорируется;
#   * condition одной цели: Очарование личности (спасбросок NPC, провал -- charmed на 1 ч), Приказ
#     (prone на 1 раунд), Удержание личности (paralyzed до конца концентрации); Страх с областью --
#     только концентрация, состояния NPC не ставятся (решение 63, Р42);
#   * utility: Опознание предмета, Языки, Покой, Призрачный скакун (путь вдвое короче час).
from protocol_kit import ScriptedRng, make_ctx, req
from test_cast_p3a import idle
from test_wizard_rest_cast import cast, cleric_bundle, wizard_bundle

from ai_dm.core.rng import Rng
from ai_dm.protocol.apply import apply
from ai_dm.protocol.handlers.utility_spells import steed_seconds, travel_fast_left
from ai_dm.protocol.requests import CastSpell
from ai_dm.rules import time_ops
from ai_dm.rules.derived import armor_class, armor_class_parts
from ai_dm.rules.healing import grant_max_hp
from ai_dm.rules.inventory import add_item
from ai_dm.state.creature import ActiveEffect, CreatureState, Expiry, ResourcePool
from ai_dm.state.world import NPC

HOUR = 3600
EIGHT_HOURS = 8 * HOUR


def prep(bundle, *spell_ids):
    bundle.heroes[0].sheet.prepared_of().extend(spell_ids)


def wiz(registry, *spell_ids, level=5):
    bundle = wizard_bundle(registry, level=level)
    prep(bundle, *spell_ids)
    return bundle


def cleric(registry, *spell_ids):
    bundle = cleric_bundle(registry, prepared=spell_ids)
    bundle.heroes[0].creature.resources["spell_slot:2"] = ResourcePool(current=2, max=2)
    return bundle


def put_npc(bundle, npc_id="orc", hp=10, creature=True, status="alive", location="vale"):
    state = CreatureState(hp_current=hp, hp_max=hp) if creature else None
    npc = NPC(
        id=npc_id, name=f"Имя {npc_id}", means=["сила"], location_id=location, creature=state,
        status=status,
    )
    bundle.world.npcs[npc_id] = npc
    return npc


def hero_of(bundle):
    return bundle.heroes[0]


def now(bundle):
    return bundle.world.clock.now_s


def go(registry, cfg, bundle, type_name, rng=None, **fields):
    ctx = make_ctx(registry, cfg, rng=rng, bundle=bundle)
    return apply(ctx, req(type_name, **fields))


def effects_of(creature, kind):
    return [e for e in creature.active_effects if e.kind == kind]


# Помощь

def test_aid_adds_five_to_max_and_current_hp(registry, cfg):
    bundle = cleric(registry, "aid")
    hero = hero_of(bundle)
    hero.creature.hp_max = hero.creature.hp_current = 10
    cast(registry, cfg, bundle, "aid")
    assert (hero.creature.hp_max, hero.creature.hp_current) == (15, 15)


def test_aid_puts_a_max_hp_effect_for_eight_hours(registry, cfg):
    bundle = cleric(registry, "aid")
    start = now(bundle)
    cast(registry, cfg, bundle, "aid")
    effect = effects_of(hero_of(bundle).creature, "max_hp")[0]
    assert (effect.params["amount"], effect.expires.kind, effect.expires.value) == (
        5, "seconds", start + EIGHT_HOURS,
    )


def test_aid_leaves_no_spell_mark(registry, cfg):
    bundle = cleric(registry, "aid")
    cast(registry, cfg, bundle, "aid")
    assert effects_of(hero_of(bundle).creature, "spell") == []


def test_aid_spends_a_second_circle_slot(registry, cfg):
    bundle = cleric(registry, "aid")
    cast(registry, cfg, bundle, "aid")
    assert hero_of(bundle).creature.resources["spell_slot:2"].current == 1


def test_aid_has_no_concentration(registry, cfg):
    bundle = cleric(registry, "aid")
    cast(registry, cfg, bundle, "aid")
    assert hero_of(bundle).creature.concentration is None


def test_aid_repeat_does_not_stack(registry, cfg):
    bundle = cleric(registry, "aid")
    hero = hero_of(bundle)
    hero.creature.hp_max = hero.creature.hp_current = 10
    cast(registry, cfg, bundle, "aid")
    cast(registry, cfg, bundle, "aid")
    assert hero.creature.hp_max == 15
    assert len(effects_of(hero.creature, "max_hp")) == 1


def test_aid_repeat_renews_the_term(registry, cfg):
    bundle = cleric(registry, "aid")
    cast(registry, cfg, bundle, "aid")
    bundle.world.clock.advance(600)
    cast(registry, cfg, bundle, "aid")
    effect = effects_of(hero_of(bundle).creature, "max_hp")[0]
    assert effect.expires.value == now(bundle) + EIGHT_HOURS


def test_aid_at_a_higher_circle_outside_combat_is_bad_circle(registry, cfg):
    bundle = cleric(registry, "aid")
    bundle.heroes[0].creature.resources["spell_slot:3"] = ResourcePool(current=1, max=1)
    _, d = cast(registry, cfg, bundle, "aid", circle=3)
    assert d.code == "bad_circle"


def test_aid_on_an_npc_with_creature_raises_his_hp(registry, cfg):
    bundle = cleric(registry, "aid")
    npc = put_npc(bundle, hp=10)
    cast(registry, cfg, bundle, "aid", target="orc")
    assert (npc.creature.hp_max, npc.creature.hp_current) == (15, 15)


def test_aid_on_an_npc_without_creature_is_bad_target(registry, cfg):
    bundle = cleric(registry, "aid")
    put_npc(bundle, creature=False)
    _, d = cast(registry, cfg, bundle, "aid", target="orc")
    assert d.code == "bad_target"


def stronger_aid(bundle):
    # Помощь 3 круга (+10), наложенная ранее (в бою)
    hero = hero_of(bundle)
    hero.creature.hp_max = hero.creature.hp_current = 10
    grant_max_hp(hero.creature, "aid", hero.id, 10, now(bundle) + 1000)
    return hero


def test_weaker_aid_repeat_keeps_the_bonus_and_hp(registry, cfg):
    bundle = cleric(registry, "aid")
    hero = stronger_aid(bundle)
    cast(registry, cfg, bundle, "aid")
    assert (hero.creature.hp_max, hero.creature.hp_current) == (20, 20)
    assert [e.params["amount"] for e in effects_of(hero.creature, "max_hp")] == [10]


def test_weaker_aid_repeat_keeps_the_old_term(registry, cfg):
    bundle = cleric(registry, "aid")
    hero = stronger_aid(bundle)
    old = effects_of(hero.creature, "max_hp")[0].expires.value
    cast(registry, cfg, bundle, "aid")
    assert effects_of(hero.creature, "max_hp")[0].expires.value == old


def test_weaker_aid_repeat_still_spends_the_slot(registry, cfg):
    bundle = cleric(registry, "aid")
    hero = stronger_aid(bundle)
    cast(registry, cfg, bundle, "aid")
    assert hero.creature.resources["spell_slot:2"].current == 1


def test_weaker_aid_repeat_says_so_in_the_log(registry, cfg):
    bundle = cleric(registry, "aid")
    hero = stronger_aid(bundle)
    d = cast(registry, cfg, bundle, "aid")[1]
    assert any(
        hero.name in line and "уже под более сильной Помощью" in line for line in d.log
    )


def test_weaker_aid_repeat_on_an_npc_keeps_his_bonus(registry, cfg):
    bundle = cleric(registry, "aid")
    npc = put_npc(bundle, hp=10)
    grant_max_hp(npc.creature, "aid", "hero", 10, now(bundle) + 1000)
    cast(registry, cfg, bundle, "aid", target="orc")
    assert npc.creature.hp_max == 20


def test_equal_aid_repeat_has_no_stronger_line(registry, cfg):
    bundle = cleric(registry, "aid")
    cast(registry, cfg, bundle, "aid")
    d = cast(registry, cfg, bundle, "aid")[1]
    assert not any("более сильной" in line for line in d.log)


def test_aid_is_taken_back_after_eight_hours(registry, cfg):
    bundle = cleric(registry, "aid")
    hero = hero_of(bundle)
    hero.creature.hp_max = hero.creature.hp_current = 10
    cast(registry, cfg, bundle, "aid")
    bundle.world.clock.advance(EIGHT_HOURS)
    go(registry, cfg, bundle, "advance_time", category="hour")
    assert (hero.creature.hp_max, hero.creature.hp_current) == (10, 10)
    assert effects_of(hero.creature, "max_hp") == []


def test_aid_rollback_keeps_current_hp_below_the_old_max(registry, cfg):
    bundle = cleric(registry, "aid")
    hero = hero_of(bundle)
    hero.creature.hp_max = hero.creature.hp_current = 10
    cast(registry, cfg, bundle, "aid")
    hero.creature.hp_current = 8
    bundle.world.clock.advance(EIGHT_HOURS)
    go(registry, cfg, bundle, "advance_time", category="hour")
    assert (hero.creature.hp_max, hero.creature.hp_current) == (10, 8)


def test_aid_rollback_is_written_to_the_log(registry, cfg):
    bundle = cleric(registry, "aid")
    hero = hero_of(bundle)
    hero.creature.hp_max = hero.creature.hp_current = 10
    cast(registry, cfg, bundle, "aid")
    hero.creature.hp_current = 8
    bundle.world.clock.advance(EIGHT_HOURS)
    d = go(registry, cfg, bundle, "advance_time", category="hour")
    assert f"Помощь кончилась: {hero.name} HP 8/10" in d.log


def test_aid_is_kept_before_the_term(registry, cfg):
    bundle = cleric(registry, "aid")
    hero = hero_of(bundle)
    hero.creature.hp_max = hero.creature.hp_current = 10
    cast(registry, cfg, bundle, "aid")
    bundle.world.clock.advance(6 * HOUR)
    d = go(registry, cfg, bundle, "advance_time", category="hour")
    assert hero.creature.hp_max == 15
    assert not any("Помощь кончилась" in line for line in d.log)


def test_aid_rollback_skips_an_npc_without_creature(registry, cfg):
    bundle = cleric(registry, "aid")
    hero = hero_of(bundle)
    hero.creature.hp_max = hero.creature.hp_current = 10
    put_npc(bundle, "ghost", creature=False)
    cast(registry, cfg, bundle, "aid")
    bundle.world.clock.advance(EIGHT_HOURS)
    d = go(registry, cfg, bundle, "advance_time", category="hour")
    assert hero.creature.hp_max == 10
    assert d.log.count(f"Помощь кончилась: {hero.name} HP 10/10") == 1


def test_aid_rollback_takes_back_only_the_expired_one_of_hero_and_npc(registry, cfg):
    bundle = cleric(registry, "aid")
    hero = hero_of(bundle)
    hero.creature.hp_max = hero.creature.hp_current = 10
    npc = put_npc(bundle, hp=10)
    cast(registry, cfg, bundle, "aid")
    bundle.world.clock.advance(HOUR)
    cast(registry, cfg, bundle, "aid", target="orc")
    bundle.world.clock.advance(EIGHT_HOURS - 2 * HOUR)
    d = go(registry, cfg, bundle, "advance_time", category="hour")
    assert (hero.creature.hp_max, npc.creature.hp_max) == (10, 15)
    assert not any(npc.name in line for line in d.log)


def test_aid_on_an_npc_is_taken_back_through_the_world(registry, cfg):
    bundle = cleric(registry, "aid")
    npc = put_npc(bundle, hp=10)
    cast(registry, cfg, bundle, "aid", target="orc")
    bundle.world.clock.advance(EIGHT_HOURS)
    d = go(registry, cfg, bundle, "advance_time", category="hour")
    assert (npc.creature.hp_max, npc.creature.hp_current) == (10, 10)
    assert f"Помощь кончилась: {npc.name} HP 10/10" in d.log


# defense вне боя

def test_invisibility_puts_the_condition_with_concentration_expiry(registry, cfg):
    bundle = wiz(registry, "invisibility")
    cast(registry, cfg, bundle, "invisibility")
    hero = hero_of(bundle)
    condition = [c for c in hero.creature.conditions if c.id == "invisible"][0]
    assert (condition.source, condition.expires.kind, condition.expires.owner) == (
        "invisibility", "concentration", hero.id,
    )


def test_invisibility_holds_concentration(registry, cfg):
    bundle = wiz(registry, "invisibility")
    cast(registry, cfg, bundle, "invisibility")
    assert hero_of(bundle).creature.concentration.spell_id == "invisibility"


def test_an_hour_without_combat_ends_invisibility_and_concentration(registry, cfg):
    bundle = wiz(registry, "invisibility")
    cast(registry, cfg, bundle, "invisibility")
    go(registry, cfg, bundle, "advance_time", category="hour")
    hero = hero_of(bundle)
    assert hero.creature.concentration is None
    assert [c for c in hero.creature.conditions if c.id == "invisible"] == []


def invisible_in_combat(registry, cfg):
    # Невидимость, наложенная вне боя протоколом, и бой с гоблином, где герой знает Огненный снаряд
    bundle = wiz(registry, "invisibility")
    hero = hero_of(bundle)
    hero.sheet.known_of().append("fire_bolt")
    cast(registry, cfg, bundle, "invisibility")
    return idle(registry, cfg, hero, ScriptedRng(d20=[2]))


def test_attack_from_invisibility_cast_outside_combat_ends_the_spell(registry, cfg):
    engine = invisible_in_combat(registry, cfg)
    for _ in range(2):
        engine.step()
    engine.start_turn("hero")
    assert "invisible" in [c.id for c in engine.heroes["hero"].creature.conditions]
    engine.perform("hero", "cast:fire_bolt:0:goblin_1")
    hero = engine.heroes["hero"]
    assert "invisible" not in [c.id for c in hero.creature.conditions]
    assert hero.creature.concentration is None
    assert "  Невидимость кончается" in engine.state.log
    assert any("больше не скрыт" in line for line in engine.state.log)


def test_invisibility_at_a_higher_circle_outside_combat_is_bad_circle(registry, cfg):
    bundle = wiz(registry, "invisibility")
    _, d = cast(registry, cfg, bundle, "invisibility", circle=3)
    assert d.code == "bad_circle"


def test_mage_armor_adds_three_to_armor_class(registry, cfg):
    bundle = wiz(registry, "mage_armor")
    hero = hero_of(bundle)
    before = armor_class(hero, registry, now(bundle))
    cast(registry, cfg, bundle, "mage_armor")
    assert armor_class(hero, registry, now(bundle)) == before + 3
    assert "Доспехи мага" in [p[0] for p in armor_class_parts(hero, registry, now(bundle))]


def test_mage_armor_lasts_eight_hours_without_concentration(registry, cfg):
    bundle = wiz(registry, "mage_armor")
    start = now(bundle)
    cast(registry, cfg, bundle, "mage_armor")
    hero = hero_of(bundle)
    effect = effects_of(hero.creature, "ac")[0]
    assert effect.expires.kind == "seconds"
    assert effect.expires.value == start + EIGHT_HOURS
    assert hero.creature.concentration is None


def test_mage_armor_is_gone_after_eight_hours(registry, cfg):
    bundle = wiz(registry, "mage_armor")
    cast(registry, cfg, bundle, "mage_armor")
    bundle.world.clock.advance(EIGHT_HOURS)
    names = [p[0] for p in armor_class_parts(hero_of(bundle), registry, now(bundle))]
    assert "Доспехи мага" not in names


def worn(registry, bundle):
    hero = hero_of(bundle)
    add_item(hero, "chain_mail", cost_cp=0)
    hero.equipped.armor = "chain_mail"
    return hero


def test_mage_armor_on_a_hero_in_armor_is_bad_target(registry, cfg):
    bundle = wiz(registry, "mage_armor")
    worn(registry, bundle)
    _, d = cast(registry, cfg, bundle, "mage_armor")
    assert d.code == "bad_target"


def test_mage_armor_refusal_keeps_the_slot(registry, cfg):
    bundle = wiz(registry, "mage_armor")
    hero = worn(registry, bundle)
    before = hero.creature.resources["spell_slot:1"].current
    cast(registry, cfg, bundle, "mage_armor")
    assert hero.creature.resources["spell_slot:1"].current == before


def test_mage_armor_refusal_adds_no_armor_class_part(registry, cfg):
    bundle = wiz(registry, "mage_armor")
    hero = worn(registry, bundle)
    cast(registry, cfg, bundle, "mage_armor")
    assert effects_of(hero.creature, "ac") == []


def test_barkskin_lifts_armor_class_to_17(registry, cfg):
    bundle = wiz(registry, "barkskin")
    cast(registry, cfg, bundle, "barkskin")
    assert armor_class(hero_of(bundle), registry, now(bundle)) == 17


def test_barkskin_keeps_a_higher_armor_class(registry, cfg):
    bundle = wiz(registry, "barkskin")
    hero = worn(registry, bundle)
    hero.equipped.shield = "shield"
    base = armor_class(hero, registry, now(bundle))
    cast(registry, cfg, bundle, "barkskin")
    assert base == 18
    assert armor_class(hero, registry, now(bundle)) == 18


def test_blur_puts_a_disadvantage_modifier_on_the_hero(registry, cfg):
    bundle = wiz(registry, "blur")
    cast(registry, cfg, bundle, "blur")
    effect = effects_of(hero_of(bundle).creature, "modifier")[0]
    assert effect.params["mode"] == "disadvantage"
    assert effect.params["side"] == "target"


def test_shield_of_faith_holds_concentration_and_adds_two(registry, cfg):
    bundle = cleric(registry, "shield_of_faith")
    hero = hero_of(bundle)
    before = armor_class(hero, registry, now(bundle))
    cast(registry, cfg, bundle, "shield_of_faith")
    assert armor_class(hero, registry, now(bundle)) == before + 2
    assert hero.creature.concentration.spell_id == "shield_of_faith"


def test_defense_on_an_npc_without_creature_is_bad_target(registry, cfg):
    bundle = wiz(registry, "blur")
    put_npc(bundle, creature=False)
    _, d = cast(registry, cfg, bundle, "blur", target="orc")
    assert d.code == "bad_target"


def test_defense_on_an_npc_goes_to_his_creature(registry, cfg):
    bundle = wiz(registry, "mage_armor")
    npc = put_npc(bundle)
    cast(registry, cfg, bundle, "mage_armor", target="orc")
    assert len(effects_of(npc.creature, "ac")) == 1


def test_defense_repeat_replaces_the_old_effect(registry, cfg):
    bundle = wiz(registry, "mage_armor")
    cast(registry, cfg, bundle, "mage_armor")
    cast(registry, cfg, bundle, "mage_armor")
    assert len(effects_of(hero_of(bundle).creature, "ac")) == 1


# варианты

def test_protection_from_energy_without_variant_is_bad_variant(registry, cfg):
    bundle = wiz(registry, "protection_from_energy")
    _, d = cast(registry, cfg, bundle, "protection_from_energy", variant="")
    assert d.code == "bad_variant"
    assert "fire" in d.message


def test_bad_variant_does_not_spend_the_slot(registry, cfg):
    bundle = wiz(registry, "protection_from_energy")
    pool = hero_of(bundle).creature.resources["spell_slot:3"]
    before = pool.current
    cast(registry, cfg, bundle, "protection_from_energy", variant="")
    assert pool.current == before


def test_chromatic_orb_without_variant_is_bad_variant(registry, cfg):
    bundle = wiz(registry, "chromatic_orb")
    put_npc(bundle)
    _, d = cast(registry, cfg, bundle, "chromatic_orb", target="orc", variant="")
    assert d.code == "bad_variant"
    assert "fire" in d.message


def test_chromatic_orb_bad_variant_keeps_the_slot(registry, cfg):
    bundle = wiz(registry, "chromatic_orb")
    put_npc(bundle)
    pool = hero_of(bundle).creature.resources["spell_slot:1"]
    before = pool.current
    cast(registry, cfg, bundle, "chromatic_orb", target="orc", variant="")
    assert pool.current == before


def test_enhance_ability_without_variant_is_bad_variant(registry, cfg):
    bundle = wiz(registry, "enhance_ability", level=5)
    _, d = cast(registry, cfg, bundle, "enhance_ability", variant="")
    assert d.code == "bad_variant"


def test_a_foreign_variant_is_bad_variant(registry, cfg):
    bundle = wiz(registry, "protection_from_energy")
    _, d = cast(registry, cfg, bundle, "protection_from_energy", variant="poison")
    assert d.code == "bad_variant"


def test_protection_from_energy_with_variant_puts_a_resist(registry, cfg):
    bundle = wiz(registry, "protection_from_energy")
    cast(registry, cfg, bundle, "protection_from_energy", variant="fire")
    effect = effects_of(hero_of(bundle).creature, "resist")[0]
    assert effect.params["damage_type"] == "fire"
    assert hero_of(bundle).creature.concentration.spell_id == "protection_from_energy"


def test_variant_of_a_spell_without_variants_is_ignored(registry, cfg):
    bundle = wiz(registry, "mage_armor")
    _, d = cast(registry, cfg, bundle, "mage_armor", variant="fire")
    assert d.status == "accepted"


def fire_damage(registry, cfg, bundle):
    d = go(
        registry, cfg, bundle, "damage", rng=Rng(11), severity="dangerous", damage_type="fire",
    )
    return d.result["damage"]


def test_resist_halves_fire_damage_before_it_runs_out(registry, cfg):
    plain = fire_damage(registry, cfg, wiz(registry))
    bundle = wiz(registry, "protection_from_energy")
    cast(registry, cfg, bundle, "protection_from_energy", variant="fire")
    assert fire_damage(registry, cfg, bundle) == plain // 2


def test_resist_is_gone_two_hours_later(registry, cfg):
    plain = fire_damage(registry, cfg, wiz(registry))
    bundle = wiz(registry, "protection_from_energy")
    cast(registry, cfg, bundle, "protection_from_energy", variant="fire")
    bundle.world.clock.advance(2 * HOUR)
    go(registry, cfg, bundle, "advance_time", category="hour")
    assert fire_damage(registry, cfg, bundle) == plain


# condition вне боя

def test_charm_person_on_a_failed_save_charms_for_an_hour(registry, cfg):
    bundle = wiz(registry, "charm_person")
    npc = put_npc(bundle)
    start = now(bundle)
    ctx = make_ctx(registry, cfg, rng=ScriptedRng(d20=[1, 1]), bundle=bundle)
    apply(ctx, req("cast_spell", spell_id="charm_person", circle=1, target="orc"))
    condition = [c for c in npc.creature.conditions if c.id == "charmed"][0]
    assert condition.source == "charm_person"
    assert (condition.expires.kind, condition.expires.value) == ("seconds", start + HOUR)


def test_charm_person_on_a_passed_save_leaves_no_condition(registry, cfg):
    bundle = wiz(registry, "charm_person")
    npc = put_npc(bundle)
    ctx = make_ctx(registry, cfg, rng=ScriptedRng(d20=[20, 20]), bundle=bundle)
    apply(ctx, req("cast_spell", spell_id="charm_person", circle=1, target="orc"))
    assert npc.creature.conditions == []


def test_charm_person_spends_the_slot_even_on_a_passed_save(registry, cfg):
    bundle = wiz(registry, "charm_person")
    put_npc(bundle)
    pool = hero_of(bundle).creature.resources["spell_slot:1"]
    before = pool.current
    ctx = make_ctx(registry, cfg, rng=ScriptedRng(d20=[20, 20]), bundle=bundle)
    apply(ctx, req("cast_spell", spell_id="charm_person", circle=1, target="orc"))
    assert pool.current == before - 1


def test_charm_person_without_creature_is_bad_target(registry, cfg):
    bundle = wiz(registry, "charm_person")
    put_npc(bundle, creature=False)
    _, d = cast(registry, cfg, bundle, "charm_person", target="orc")
    assert d.code == "bad_target"


def test_charm_person_without_target_is_bad_target(registry, cfg):
    bundle = wiz(registry, "charm_person")
    _, d = cast(registry, cfg, bundle, "charm_person", target="hero")
    assert d.code == "bad_target"


def test_charm_person_at_a_higher_circle_outside_combat_is_bad_circle(registry, cfg):
    bundle = wiz(registry, "charm_person")
    put_npc(bundle)
    _, d = cast(registry, cfg, bundle, "charm_person", target="orc", circle=2)
    assert d.code == "bad_circle"


def test_command_on_a_failed_save_lays_the_target_prone_for_a_round(registry, cfg):
    bundle = cleric(registry, "command")
    npc = put_npc(bundle)
    start = now(bundle)
    ctx = make_ctx(registry, cfg, rng=ScriptedRng(d20=[1, 1]), bundle=bundle)
    apply(ctx, req("cast_spell", spell_id="command", circle=1, target="orc"))
    condition = [c for c in npc.creature.conditions if c.id == "prone"][0]
    assert (condition.expires.kind, condition.expires.value) == (
        "seconds", start + cfg.time.round_s,
    )


def test_command_on_a_passed_save_does_nothing(registry, cfg):
    bundle = cleric(registry, "command")
    npc = put_npc(bundle)
    ctx = make_ctx(registry, cfg, rng=ScriptedRng(d20=[20, 20]), bundle=bundle)
    apply(ctx, req("cast_spell", spell_id="command", circle=1, target="orc"))
    assert npc.creature.conditions == []


def test_hold_person_paralyzes_until_concentration_ends(registry, cfg):
    bundle = wiz(registry, "hold_person")
    npc = put_npc(bundle)
    ctx = make_ctx(registry, cfg, rng=ScriptedRng(d20=[1, 1]), bundle=bundle)
    apply(ctx, req("cast_spell", spell_id="hold_person", circle=2, target="orc"))
    condition = [c for c in npc.creature.conditions if c.id == "paralyzed"][0]
    hero = hero_of(bundle)
    assert (condition.expires.kind, condition.expires.owner) == ("concentration", hero.id)
    assert hero.creature.concentration.spell_id == "hold_person"


def test_fear_outside_combat_holds_concentration_and_leaves_npc_conditions(registry, cfg):
    bundle = wiz(registry, "fear")
    npc = put_npc(bundle)
    _, d = cast(registry, cfg, bundle, "fear", target="orc")
    assert d.status == "accepted"
    assert hero_of(bundle).creature.concentration.spell_id == "fear"
    assert npc.creature.conditions == []


# utility

def test_identify_on_an_inventory_item_returns_its_properties(registry, cfg):
    bundle = wiz(registry, "identify")
    add_item(hero_of(bundle), "potion_of_healing", cost_cp=0)
    _, d = cast(registry, cfg, bundle, "identify", target="potion_of_healing")
    assert d.result["item"] == {"effects": ["heal"], "magic": True, "rarity": "common"}


def test_identify_on_armor_has_no_effects_not_magic_and_no_rarity(registry, cfg):
    bundle = wiz(registry, "identify")
    add_item(hero_of(bundle), "chain_mail", cost_cp=0)
    _, d = cast(registry, cfg, bundle, "identify", target="chain_mail")
    assert d.result["item"] == {"effects": [], "magic": False, "rarity": None}


def test_identify_on_an_unknown_target_is_unknown_npc(registry, cfg):
    bundle = wiz(registry, "identify")
    _, d = cast(registry, cfg, bundle, "identify", target="nothing_here")
    assert d.code == "unknown_npc"


def test_identify_without_the_item_in_inventory_is_unknown_npc(registry, cfg):
    bundle = wiz(registry, "identify")
    _, d = cast(registry, cfg, bundle, "identify", target="potion_of_healing")
    assert d.code == "unknown_npc"


def test_tongues_spends_a_slot_and_marks_the_hero_for_an_hour(registry, cfg):
    bundle = wiz(registry, "tongues")
    start = now(bundle)
    pool = hero_of(bundle).creature.resources["spell_slot:3"]
    before = pool.current
    cast(registry, cfg, bundle, "tongues")
    assert pool.current == before - 1
    marks = effects_of(hero_of(bundle).creature, "spell")
    assert [(m.id, m.expires.value) for m in marks] == [("tongues", start + HOUR)]


def test_tongues_adds_a_languages_effect(registry, cfg):
    bundle = wiz(registry, "tongues")
    start = now(bundle)
    cast(registry, cfg, bundle, "tongues")
    effect = effects_of(hero_of(bundle).creature, "languages")[0]
    assert effect.params == {"all": True}
    assert effect.expires.value == start + HOUR


def test_tongues_returns_its_effect_text(registry, cfg):
    bundle = wiz(registry, "tongues")
    _, d = cast(registry, cfg, bundle, "tongues")
    assert d.result["effect"]


def test_tongues_repeat_does_not_duplicate_the_effects(registry, cfg):
    bundle = wiz(registry, "tongues")
    cast(registry, cfg, bundle, "tongues")
    cast(registry, cfg, bundle, "tongues")
    creature = hero_of(bundle).creature
    assert len(effects_of(creature, "languages")) == 1
    assert len(effects_of(creature, "spell")) == 1


def test_gentle_repose_on_a_dead_npc_with_creature_marks_the_body(registry, cfg):
    bundle = wiz(registry, "gentle_repose")
    npc = put_npc(bundle, status="dead")
    cast(registry, cfg, bundle, "gentle_repose", target="orc")
    assert len(effects_of(npc.creature, "gentle_repose")) == 1


def test_gentle_repose_on_a_dead_npc_without_creature_is_bad_target(registry, cfg):
    bundle = wiz(registry, "gentle_repose")
    put_npc(bundle, status="dead", creature=False)
    _, d = cast(registry, cfg, bundle, "gentle_repose", target="orc")
    assert d.code == "bad_target"


def test_gentle_repose_on_a_living_npc_is_bad_target(registry, cfg):
    bundle = wiz(registry, "gentle_repose")
    put_npc(bundle)
    _, d = cast(registry, cfg, bundle, "gentle_repose", target="orc")
    assert d.code == "bad_target"


def test_gentle_repose_on_a_body_elsewhere_is_bad_target(registry, cfg):
    bundle = wiz(registry, "gentle_repose")
    put_npc(bundle, status="dead", location="forest")
    _, d = cast(registry, cfg, bundle, "gentle_repose", target="orc")
    assert d.code == "bad_target"


def test_gentle_repose_on_an_unknown_npc_is_unknown_npc(registry, cfg):
    bundle = wiz(registry, "gentle_repose")
    _, d = cast(registry, cfg, bundle, "gentle_repose", target="ghost")
    assert d.code == "unknown_npc"


def trip_seconds(registry, cfg, bundle):
    before = now(bundle)
    go(registry, cfg, bundle, "advance_time", travel_to="forest", pace="normal")
    return now(bundle) - before


def test_phantom_steed_halves_the_next_trip(registry, cfg):
    full = time_ops.travel_seconds(4800, "normal", cfg)
    bundle = wiz(registry, "phantom_steed")
    cast(registry, cfg, bundle, "phantom_steed", ritual=True)
    assert trip_seconds(registry, cfg, bundle) == full // 2


def test_phantom_steed_is_gone_after_an_hour(registry, cfg):
    full = time_ops.travel_seconds(4800, "normal", cfg)
    bundle = wiz(registry, "phantom_steed")
    cast(registry, cfg, bundle, "phantom_steed", ritual=True)
    bundle.world.clock.advance(HOUR + 1)
    assert trip_seconds(registry, cfg, bundle) == full


def test_phantom_steed_with_twenty_minutes_left_speeds_only_that_part(registry, cfg):
    full = time_ops.travel_seconds(4800, "normal", cfg)
    assert full >= 2400  # путь не короче ускоренной части (20 мин скакуна = 40 мин пешком)
    bundle = wiz(registry, "phantom_steed")
    cast(registry, cfg, bundle, "phantom_steed", ritual=True)
    bundle.world.clock.advance(HOUR - 1200)
    # 20 минут скакуна дают 40 минут пути за 20: выигрыш ровно 1200 с
    assert trip_seconds(registry, cfg, bundle) == full - 1200


def steed_hero(registry, left):
    bundle = wiz(registry)
    hero = hero_of(bundle)
    hero.creature.active_effects.append(ActiveEffect(
        id="phantom_steed", source=hero.id, kind="travel_fast",
        expires=Expiry(kind="seconds", value=now(bundle) + left),
    ))
    return hero, now(bundle)


def test_steed_seconds_six_hours_on_foot_with_one_hour_left_take_five(registry):
    hero, start = steed_hero(registry, HOUR)
    assert steed_seconds(hero, start, 6 * HOUR) == 5 * HOUR


def test_steed_seconds_one_hour_trip_takes_half_an_hour(registry):
    hero, start = steed_hero(registry, HOUR)
    assert steed_seconds(hero, start, HOUR) == HOUR // 2


def test_steed_seconds_trip_of_exactly_double_the_term_takes_the_term(registry):
    hero, start = steed_hero(registry, HOUR)
    assert steed_seconds(hero, start, 2 * HOUR) == HOUR


def test_steed_seconds_partial_remainder_of_twenty_minutes(registry):
    hero, start = steed_hero(registry, 1200)
    assert steed_seconds(hero, start, HOUR) == 1200 + (HOUR - 2400)


def test_steed_seconds_without_a_steed_is_unchanged(registry):
    hero = hero_of(wiz(registry))
    assert steed_seconds(hero, 0, 6 * HOUR) == 6 * HOUR


def test_steed_seconds_with_an_expired_steed_is_unchanged(registry):
    hero, start = steed_hero(registry, HOUR)
    assert steed_seconds(hero, start + HOUR, 6 * HOUR) == 6 * HOUR


def test_travel_fast_left_is_the_time_to_the_end_of_the_mark(registry):
    hero, start = steed_hero(registry, HOUR)
    assert travel_fast_left(hero, start + 600) == HOUR - 600


def test_travel_fast_left_is_zero_without_a_steed_or_at_the_limit(registry):
    hero, start = steed_hero(registry, HOUR)
    assert travel_fast_left(hero, start + HOUR) == 0
    assert travel_fast_left(hero_of(wiz(registry)), 0) == 0


def test_travel_fast_left_takes_the_longest_mark(registry):
    hero, start = steed_hero(registry, HOUR)
    hero.creature.active_effects.append(ActiveEffect(
        id="phantom_steed", source=hero.id, kind="travel_fast",
        expires=Expiry(kind="seconds", value=start + 2 * HOUR),
    ))
    assert travel_fast_left(hero, start) == 2 * HOUR


def test_a_trip_without_the_steed_takes_the_full_time(registry, cfg):
    bundle = wiz(registry)
    assert trip_seconds(registry, cfg, bundle) == time_ops.travel_seconds(4800, "normal", cfg)


# запрос

def test_cast_spell_variant_defaults_to_none():
    request = req("cast_spell", spell_id="fire_bolt", circle=0, target="", free=False)
    assert request.variant is None


def test_cast_spell_variant_is_carried():
    request = req("cast_spell", spell_id="x", circle=1, target="", free=False, variant="fire")
    assert isinstance(request, CastSpell)
    assert request.variant == "fire"
