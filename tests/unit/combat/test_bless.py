# Благословение по SRD (ревью партии 5, п. 4): общий механизм заклинания с targets > 1.
#   bless (YAML: два эффекта modifier -- attack_roll и saving_throw, 1d4, targets: 3):
#     id варианта cast:bless:1:<t1>[,<t2>[,<t3>]] -- от одной до targets целей-союзников в пределах
#       дальности, ref через запятую в порядке state.participants; одна ячейка, одна концентрация;
#     на КАЖДУЮ цель накладываются ВСЕ modifier-эффекты заклинания (ActiveEffect(id="bless",
#       source=<заклинатель>, kind="modifier", params={"target": "attack_roll"|"saving_throw",
#       "dice": "1d4"}, expires=Expiry(kind="concentration", owner=<заклинатель>))) -- две записи;
#     +1d4 к броску атаки, к спасброску и к спасброску от смерти цели;
#     повтор цели ("a,a") и больше targets целей -- Rejected, ячейка и концентрация не тратятся;
#     конец концентрации снимает эффекты со всех целей.
#   Бросок 1d4 -- по одному на бросок (атака и спасбросок -- разные броски).
from combat_kit import (
    ScriptedRng,
    creature,
    down_hero,
    hp,
    make_engine,
    make_fighter,
    make_wizard,
    mon,
    option_ids,
)

from ai_dm.combat.controllers import ScriptedController
from ai_dm.rules.results import Rejected


def party(registry, cfg, rng, controllers=None):
    caster = make_wizard(registry)
    caster.sheet.prepared_of().append("bless")
    allies = [make_fighter(registry, name) for name in ("ally", "ally2", "ally3")]
    return make_engine(
        registry, cfg, heroes=[caster] + allies, rng=rng, controllers=controllers,
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )


def slots(engine):
    return engine.heroes["wiz"].creature.resources["spell_slot:1"].current


def bless_effects(engine, ref):
    return [e for e in creature(engine, ref).active_effects if e.id == "bless"]


# варианты

def test_bless_can_be_cast_on_one_two_or_three_targets(registry, cfg):
    ids = option_ids(party(registry, cfg, ScriptedRng()), "wiz")
    assert "cast:bless:1:ally" in ids
    assert "cast:bless:1:ally,ally2" in ids
    assert "cast:bless:1:ally,ally2,ally3" in ids


def test_bless_cannot_be_cast_on_four_targets(registry, cfg):
    ids = option_ids(party(registry, cfg, ScriptedRng()), "wiz")
    bless = [i.split(":")[3] for i in ids if i.startswith("cast:bless:1:")]
    assert [t for t in bless if len(t.split(",")) > 3] == []


def test_bless_cannot_be_cast_on_the_same_target_twice(registry, cfg):
    ids = option_ids(party(registry, cfg, ScriptedRng()), "wiz")
    assert "cast:bless:1:ally,ally" not in ids


def test_bless_cannot_target_an_enemy(registry, cfg):
    ids = option_ids(party(registry, cfg, ScriptedRng()), "wiz")
    assert not [i for i in ids if i.startswith("cast:bless:1:") and "goblin_1" in i]


# отказы

def test_repeated_target_is_rejected_and_costs_nothing(registry, cfg):
    engine = party(registry, cfg, ScriptedRng())
    assert isinstance(engine.perform("wiz", "cast:bless:1:ally,ally"), Rejected)
    assert slots(engine) == 2
    assert engine.heroes["wiz"].creature.concentration is None
    assert bless_effects(engine, "ally") == []


def test_more_targets_than_the_spell_allows_is_rejected(registry, cfg):
    engine = party(registry, cfg, ScriptedRng())
    result = engine.perform("wiz", "cast:bless:1:ally,ally2,ally3,wiz")
    assert isinstance(result, Rejected)
    assert slots(engine) == 2
    assert engine.heroes["wiz"].creature.concentration is None


# эффекты

def test_three_targets_get_every_modifier_of_the_spell(registry, cfg):
    engine = party(registry, cfg, ScriptedRng())
    engine.perform("wiz", "cast:bless:1:ally,ally2,ally3")
    for ref in ("ally", "ally2", "ally3"):
        effects = bless_effects(engine, ref)
        assert sorted(e.params["target"] for e in effects) == ["attack_roll", "saving_throw"]
        assert all(e.source == "wiz" and e.params["dice"] == "1d4" for e in effects)
        assert all(e.expires.kind == "concentration" and e.expires.owner == "wiz" for e in effects)


def test_three_targets_cost_one_slot_and_one_concentration(registry, cfg):
    engine = party(registry, cfg, ScriptedRng())
    engine.perform("wiz", "cast:bless:1:ally,ally2,ally3")
    assert slots(engine) == 1
    assert engine.heroes["wiz"].creature.concentration.spell_id == "bless"


def test_a_target_outside_the_list_gets_nothing(registry, cfg):
    engine = party(registry, cfg, ScriptedRng())
    engine.perform("wiz", "cast:bless:1:ally,ally2")
    assert bless_effects(engine, "ally3") == []


def test_blessed_target_adds_1d4_to_the_attack(registry, cfg):
    # третья цель: 9 + 5 = 14 -- промах по КД 15; с 1d4 (3) -- 17, попадание (1d8 4 + 3 = 7)
    engine = party(registry, cfg, ScriptedRng(d20=[9], d4=[3], d8=[4]))
    engine.perform("wiz", "cast:bless:1:ally,ally2,ally3")
    engine.perform("ally3", "attack:longsword:goblin_1")
    assert hp(engine, "goblin_1") == 3


def test_blessed_target_adds_1d4_to_the_saving_throw(registry, cfg):
    # ЛОВ воина +1: 10 + 1 = 11 < 13; с 1d4 (3) -- 14, успех
    engine = party(registry, cfg, ScriptedRng(d20=[10], d4=[3]))
    engine.perform("wiz", "cast:bless:1:ally,ally2")
    assert engine.save("ally2", "dex", 13).outcome == "success"


def test_unblessed_target_saves_without_the_die(registry, cfg):
    rng = ScriptedRng(d20=[10], d4=[3])
    engine = party(registry, cfg, rng)
    engine.perform("wiz", "cast:bless:1:ally,ally2")
    assert engine.save("ally3", "dex", 13).outcome == "fail"
    assert rng.left("d4") == 1


def test_failed_concentration_drops_bless_from_every_target(registry, cfg):
    # гоблин попадает по волшебнику (19 + 4), урон 3 + 2 = 5, СЛ 10; ТЕЛ +2: 7 + 2 = 9 -- провал
    engine = party(registry, cfg, ScriptedRng(d20=[19, 7], d6=[3]))
    engine.perform("wiz", "cast:bless:1:ally,ally2,ally3")
    engine.perform("goblin_1", "attack:скимитар:wiz")
    assert engine.heroes["wiz"].creature.concentration is None
    for ref in ("ally", "ally2", "ally3"):
        assert bless_effects(engine, ref) == []


def test_new_concentration_spell_drops_the_old_bless_everywhere(registry, cfg):
    engine = party(registry, cfg, ScriptedRng())
    engine.perform("wiz", "cast:bless:1:ally,ally2")
    engine.state.participants[0].turn.action = True
    engine.perform("wiz", "cast:bless:1:ally3")
    assert bless_effects(engine, "ally") == []
    assert bless_effects(engine, "ally2") == []
    assert len(bless_effects(engine, "ally3")) == 2


# спасбросок от смерти

def blessed_dying_ally(registry, cfg, rng):
    controllers = {
        "wiz": ScriptedController([]), "ally": ScriptedController([]),
        "ally2": ScriptedController([]), "ally3": ScriptedController([]),
        "goblin_1": ScriptedController([]),
    }
    engine = party(registry, cfg, rng, controllers)
    engine.perform("wiz", "cast:bless:1:ally,ally2")
    down_hero(engine, "ally", by="goblin_1")
    return engine


def test_bless_adds_1d4_to_the_death_save(registry, cfg):
    # d20 8 + 1d4 (2) = 10 -- успех; без благословения 8 -- провал
    engine = blessed_dying_ally(registry, cfg, ScriptedRng(d20=[8], d4=[2]))
    engine.step()
    engine.step()
    saves = engine.heroes["ally"].creature.death_saves
    assert (saves.successes, saves.failures) == (1, 0)


def test_unblessed_dying_hero_fails_the_same_roll(registry, cfg):
    engine = blessed_dying_ally(registry, cfg, ScriptedRng(d20=[8], d4=[2]))
    down_hero(engine, "ally3", by="goblin_1")
    engine.state.initiative_order = ["ally3", "wiz", "ally", "ally2", "goblin_1"]
    engine.step()
    saves = engine.heroes["ally3"].creature.death_saves
    assert (saves.successes, saves.failures) == (0, 1)


def test_blessing_die_is_signed_in_the_attack_line(registry, cfg):
    engine = party(registry, cfg, ScriptedRng(d20=[9], d4=[3], d8=[4]))
    engine.perform("wiz", "cast:bless:1:ally,ally2,ally3")
    engine.perform("ally3", "attack:longsword:goblin_1")
    assert any("+ 1d4 (3) Благословение" in line for line in engine.state.log)


# К0а: концентрация на Благословении -- объект с кругом заклинания

def test_bless_concentration_object_has_spell_circle(registry, cfg):
    engine = party(registry, cfg, ScriptedRng())
    engine.perform("wiz", "cast:bless:1:ally")
    held = engine.heroes["wiz"].creature.concentration
    assert (held.spell_id, held.circle) == ("bless", registry.get("spell", "bless").level)
