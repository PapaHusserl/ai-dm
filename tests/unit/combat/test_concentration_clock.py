# К1 «Концентрация по часам» в бою (docs/plan-k1.md, п. 2.2-2.3; В2а, В3а, Q1а):
#   часы в бою стоят; при касте Concentration.until_s = clock.now_s + duration_s заклинания
#   (Благословение +60, Метка охотника +3600, Опутывающий удар +60); после боя (end.conclude: часы
#   += round * round_s) каждая концентрация героя кончается по сроку: ровно в срок -- кончилась;
#   снимаются эффекты у заклинателя и целей (в т.ч. безымянных монстров), в лог идёт
#   «<имя>: <заклинание> кончается»; заряд Опутывающего удара снимается как раньше; концентрация
#   со старого сейва (until_s None) держится.
from combat_kit import ScriptedRng, creature, make_engine, make_fighter, make_wizard, mon, part
from test_ranger_combat import make_ranger

from ai_dm.state.creature import ActiveEffect, Concentration, Expiry

GOBLIN = [mon("goblin_1", "goblin_warrior", "hall")]
MARK = "cast:hunters_mark:1:goblin_1"


def party(registry, cfg, rng=None):
    caster = make_wizard(registry)
    caster.sheet.prepared_of().append("bless")
    ally = make_fighter(registry, "ally")
    return make_engine(registry, cfg, heroes=[caster, ally], rng=rng, monsters=GOBLIN)


def ranger_in_door(registry, cfg, prepared=None):
    hero = make_ranger(registry)
    if prepared is not None:
        hero.sheet.prepared_of()[:] = prepared
    return make_engine(
        registry, cfg, heroes=[(hero, "door")], monsters=GOBLIN, rng=ScriptedRng(),
        hero_zone="door",
    )


def held(engine, ref):
    return creature(engine, ref).concentration


def finish(engine, rounds):
    engine.state.round = rounds
    engine.end_combat()


def bless_effects(engine, ref):
    return [e for e in creature(engine, ref).active_effects if e.id == "bless"]


# until_s при касте

def test_bless_sets_until_to_now_plus_a_minute(registry, cfg):
    engine = party(registry, cfg)
    engine.world.clock.advance(1000)
    engine.perform("wiz", "cast:bless:1:ally")
    assert held(engine, "wiz").until_s == 1060


def test_hunters_mark_sets_until_to_now_plus_an_hour(registry, cfg):
    engine = ranger_in_door(registry, cfg)
    engine.world.clock.advance(1000)
    engine.perform("hero", MARK)
    assert held(engine, "hero").until_s == 4600


def test_free_hunters_mark_sets_until_too(registry, cfg):
    engine = ranger_in_door(registry, cfg)
    engine.perform("hero", MARK + ":free")
    assert held(engine, "hero").until_s == 3600


def test_ensnaring_strike_sets_until_to_now_plus_a_minute(registry, cfg):
    engine = ranger_in_door(registry, cfg, ["ensnaring_strike"])
    engine.world.clock.advance(500)
    engine.perform("hero", "cast:ensnaring_strike:1:hero")
    assert held(engine, "hero").until_s == 560


def test_new_concentration_in_combat_replaces_the_object_with_its_own_until(registry, cfg):
    engine = ranger_in_door(registry, cfg, ["ensnaring_strike"])
    engine.perform("hero", MARK)
    engine.part("hero").turn.bonus = True
    engine.perform("hero", "cast:ensnaring_strike:1:hero")
    assert (held(engine, "hero").spell_id, held(engine, "hero").until_s) == (
        "ensnaring_strike", 60,
    )


# после боя

def test_bless_ends_after_an_eleven_round_fight(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:bless:1:ally")
    finish(engine, 11)
    assert held(engine, "wiz") is None


def test_bless_effects_are_removed_from_caster_and_targets(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:bless:1:wiz,ally")
    finish(engine, 11)
    assert bless_effects(engine, "wiz") == []
    assert bless_effects(engine, "ally") == []


def test_bless_end_is_logged(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:bless:1:ally")
    finish(engine, 11)
    assert any("Благословение кончается" in line for line in engine.state.log)


def test_bless_ends_exactly_at_the_limit(registry, cfg):
    # 10 раундов x 6 с = 60 с = срок
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:bless:1:ally")
    finish(engine, 10)
    assert held(engine, "wiz") is None


def test_bless_holds_one_second_before_the_limit(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:bless:1:ally")
    finish(engine, 9)
    assert held(engine, "wiz") is not None
    assert len(bless_effects(engine, "ally")) == 2


def test_no_end_line_while_the_concentration_holds(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:bless:1:ally")
    finish(engine, 3)
    assert not any("кончается" in line for line in engine.state.log)


def test_hunters_mark_survives_the_same_fight(registry, cfg):
    engine = ranger_in_door(registry, cfg)
    engine.perform("hero", MARK)
    finish(engine, 11)
    assert held(engine, "hero").spell_id == "hunters_mark"
    assert [e.kind for e in creature(engine, "goblin_1").active_effects] == ["mark"]


def test_hunters_mark_ends_when_the_hour_is_up(registry, cfg):
    engine = ranger_in_door(registry, cfg)
    engine.perform("hero", MARK)
    engine.world.clock.advance(3600)
    finish(engine, 1)
    assert held(engine, "hero") is None
    assert creature(engine, "goblin_1").active_effects == []
    assert any("Метка охотника кончается" in line for line in engine.state.log)


def test_ensnaring_charge_is_removed_after_the_fight_as_before(registry, cfg):
    engine = ranger_in_door(registry, cfg, ["ensnaring_strike"])
    engine.perform("hero", "cast:ensnaring_strike:1:hero")
    finish(engine, 1)
    assert held(engine, "hero") is None
    assert [e for e in creature(engine, "hero").active_effects if e.kind == "weapon_rider"] == []


def test_ensnaring_charge_removal_is_not_logged_as_an_expiry(registry, cfg):
    engine = ranger_in_door(registry, cfg, ["ensnaring_strike"])
    engine.perform("hero", "cast:ensnaring_strike:1:hero")
    finish(engine, 1)
    assert not any("кончается" in line for line in engine.state.log)


def test_old_save_concentration_without_until_holds_after_the_fight(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:bless:1:ally")
    held(engine, "wiz").until_s = None
    finish(engine, 11)
    assert held(engine, "wiz") is not None
    assert len(bless_effects(engine, "ally")) == 2


def test_fight_without_concentration_ends_quietly(registry, cfg):
    engine = party(registry, cfg)
    finish(engine, 11)
    assert held(engine, "wiz") is None
    assert not any("кончается" in line for line in engine.state.log)


def test_concentration_of_the_second_hero_is_checked_too(registry, cfg):
    engine = party(registry, cfg)
    creature(engine, "ally").concentration = Concentration(
        spell_id="bless", circle=1, until_s=30
    )
    creature(engine, "ally").active_effects.append(
        ActiveEffect(id="bless", source="ally", kind="modifier",
                     expires=Expiry(kind="concentration", owner="ally"))
    )
    finish(engine, 11)
    assert held(engine, "ally") is None
    assert creature(engine, "ally").active_effects == []


def test_pending_status_of_the_fight_does_not_change_the_expiry(registry, cfg):
    # исход боя не важен: сдвиг часов один, срок проверяется после него
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:bless:1:ally")
    part(engine, "goblin_1").status = "dead"
    creature(engine, "goblin_1").hp_current = 0
    finish(engine, 11)
    assert held(engine, "wiz") is None
