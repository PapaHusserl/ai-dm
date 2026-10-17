# К1 «Концентрация по часам» (docs/plan-k1.md, п. 2.1; В2а, В3а):
#   start_concentration(hero, world, spell, circle, now_s=None) -- until_s = now_s +
#     spell.duration_s, если заданы оба, иначе None (вызовы без now_s, заклинания без длительности);
#   expire_concentration(hero, world) -> spell_id | None -- концентрация с until_s <=
#     world.clock.now_s снимается целиком (drop_concentration: объект, эффекты героя и NPC мира),
#     возвращает spell_id;
#     until_s None (старый сейв) -- бессрочно, ничего не снимается; "ровно в срок" -- кончилась.
from combat_kit import make_wizard

from ai_dm.core.rng import Rng
from ai_dm.rules.spellcasting import expire_concentration, start_concentration
from ai_dm.state.creature import (
    ActiveEffect,
    AppliedCondition,
    Concentration,
    CreatureState,
    Expiry,
)
from ai_dm.state.world import NPC, WorldState


def make_world(now_s=0):
    world = WorldState(world_id="w1", rng=Rng(1).state)
    world.clock.advance(now_s)
    return world


def hold(hero, spell_id="hunters_mark", until_s=None, circle=1):
    hero.creature.concentration = Concentration(spell_id=spell_id, circle=circle, until_s=until_s)


def npc_with(world, npc_id, effects=(), conditions=()):
    npc = NPC(
        id=npc_id, name=npc_id, means=["x"],
        creature=CreatureState(hp_current=5, hp_max=5),
    )
    npc.creature.active_effects.extend(effects)
    npc.creature.conditions.extend(conditions)
    world.npcs[npc_id] = npc
    return npc


def concentration_effect(owner="wiz", effect_id="mark"):
    return ActiveEffect(
        id=effect_id, source=owner, kind="modifier",
        expires=Expiry(kind="concentration", owner=owner),
    )


# start_concentration

def test_start_sets_until_from_now_and_spell_duration(registry):
    hero = make_wizard(registry)
    spell = registry.get("spell", "hunters_mark")
    start_concentration(hero, make_world(), spell, 1, now_s=1000)
    assert hero.creature.concentration.until_s == 4600


def test_start_without_now_has_no_until(registry):
    hero = make_wizard(registry)
    start_concentration(hero, make_world(), registry.get("spell", "hunters_mark"), 1)
    assert hero.creature.concentration.until_s is None


def test_start_for_spell_without_duration_has_no_until(registry):
    hero = make_wizard(registry)
    spell = registry.get("spell", "cure_wounds")
    assert spell.duration_s is None
    start_concentration(hero, make_world(), spell, 1, now_s=1000)
    assert hero.creature.concentration.until_s is None


def test_start_for_one_minute_spell_ends_in_sixty_seconds(registry):
    hero = make_wizard(registry)
    start_concentration(hero, make_world(), registry.get("spell", "bless"), 1, now_s=500)
    assert hero.creature.concentration.until_s == 560


def test_start_keeps_spell_and_circle(registry):
    hero = make_wizard(registry)
    start_concentration(hero, make_world(), registry.get("spell", "bless"), 2, now_s=0)
    held_now = hero.creature.concentration
    assert (held_now.spell_id, held_now.circle) == ("bless", 2)


def test_start_drops_the_previous_concentration(registry):
    hero = make_wizard(registry)
    world = make_world()
    npc = npc_with(world, "n1", effects=[concentration_effect()])
    start_concentration(hero, world, registry.get("spell", "bless"), 1, now_s=0)
    start_concentration(hero, world, registry.get("spell", "hunters_mark"), 1, now_s=0)
    assert hero.creature.concentration.spell_id == "hunters_mark"
    assert npc.creature.active_effects == []


# expire_concentration

def test_expire_without_concentration_does_nothing(registry):
    hero = make_wizard(registry)
    assert expire_concentration(hero, make_world(5000)) is None


def test_expire_with_unlimited_concentration_keeps_it(registry):
    # старый сейв: until_s None -- бессрочно до следующего заклинания (В3а)
    hero = make_wizard(registry)
    hold(hero, until_s=None)
    world = make_world(10**6)
    assert expire_concentration(hero, world) is None
    assert hero.creature.concentration is not None


def test_expire_before_the_end_keeps_it(registry):
    hero = make_wizard(registry)
    hold(hero, until_s=1000)
    assert expire_concentration(hero, make_world(999)) is None
    assert hero.creature.concentration.until_s == 1000


def test_expire_exactly_at_the_end_drops_it(registry):
    hero = make_wizard(registry)
    hold(hero, "bless", until_s=1000)
    assert expire_concentration(hero, make_world(1000)) == "bless"
    assert hero.creature.concentration is None


def test_expire_after_the_end_drops_it_and_returns_spell_id(registry):
    hero = make_wizard(registry)
    hold(hero, "hunters_mark", until_s=1000)
    assert expire_concentration(hero, make_world(9000)) == "hunters_mark"
    assert hero.creature.concentration is None


def test_expire_twice_returns_none_the_second_time(registry):
    hero = make_wizard(registry)
    hold(hero, until_s=10)
    world = make_world(100)
    expire_concentration(hero, world)
    assert expire_concentration(hero, world) is None


def test_expire_removes_mark_pending_from_the_hero(registry):
    hero = make_wizard(registry)
    hold(hero, until_s=10)
    hero.creature.active_effects.append(
        ActiveEffect(
            id="hunters_mark", source="wiz", kind="mark_pending",
            params={"target": "n1", "dice": "1d6", "damage_type": "force"},
            expires=Expiry(kind="concentration", owner="wiz"),
        )
    )
    expire_concentration(hero, make_world(10))
    assert [e.kind for e in hero.creature.active_effects] == []


def test_expire_removes_the_spell_marker_effect_of_the_hero(registry):
    hero = make_wizard(registry)
    hold(hero, "hunters_mark", until_s=10)
    hero.creature.active_effects.append(
        ActiveEffect(
            id="hunters_mark", source="wiz", kind="spell",
            expires=Expiry(kind="seconds", value=3600),
        )
    )
    expire_concentration(hero, make_world(10))
    assert hero.creature.active_effects == []


def test_expire_removes_concentration_effects_of_this_hero_from_npcs(registry):
    hero = make_wizard(registry)
    hold(hero, until_s=10)
    world = make_world(10)
    npc = npc_with(world, "n1", effects=[concentration_effect()])
    expire_concentration(hero, world)
    assert npc.creature.active_effects == []


def test_expire_removes_concentration_conditions_of_this_hero_from_npcs(registry):
    hero = make_wizard(registry)
    hold(hero, until_s=10)
    world = make_world(10)
    npc = npc_with(
        world, "n1",
        conditions=[AppliedCondition(
            id="restrained", source="wiz", expires=Expiry(kind="concentration", owner="wiz")
        )],
    )
    expire_concentration(hero, world)
    assert npc.creature.conditions == []


def test_expire_keeps_foreign_effects_of_npcs(registry):
    hero = make_wizard(registry)
    hold(hero, until_s=10)
    world = make_world(10)
    other = concentration_effect(owner="someone_else", effect_id="theirs")
    plain = ActiveEffect(id="burning", source="x", kind="dot")
    timed = ActiveEffect(
        id="timed", source="wiz", kind="spell", expires=Expiry(kind="seconds", value=5000)
    )
    npc = npc_with(world, "n1", effects=[other, plain, timed])
    expire_concentration(hero, world)
    assert [e.id for e in npc.creature.active_effects] == ["theirs", "burning", "timed"]


def test_expire_skips_npcs_without_creature(registry):
    hero = make_wizard(registry)
    hold(hero, until_s=10)
    world = make_world(10)
    world.npcs["bare"] = NPC(id="bare", name="bare", means=["x"])
    assert expire_concentration(hero, world) == "hunters_mark"


def test_expire_keeps_non_concentration_effects_of_the_hero(registry):
    hero = make_wizard(registry)
    hold(hero, until_s=10)
    hero.creature.active_effects.append(ActiveEffect(id="dodge", source="wiz", kind="dodge"))
    expire_concentration(hero, make_world(10))
    assert [e.id for e in hero.creature.active_effects] == ["dodge"]
