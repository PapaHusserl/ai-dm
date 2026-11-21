# Шаг 255 П1 (docs/plan-255.md, «Тесты»): rules.creatures.purge_expired(bundle) -- после сдвига
# часов убирает из active_effects и conditions истёкшие seconds (value <= now_s; max_hp -- никогда:
# его снимает expire_max_hp) у героев бандла и NPC мира; из hero.minions -- истёкшие по until_s,
# но только когда session.active_combat is None (индекс в списке -- часть ref участника боя).
# Молча, без возврата.
from combat_kit import ScriptedRng, make_engine, make_wizard, mon
from protocol_kit import make_bundle, make_ctx, req

from ai_dm.combat import end, minions
from ai_dm.persistence.migrations import CURRENT_SCHEMA_VERSION
from ai_dm.persistence.store import load_slot, save_slot
from ai_dm.protocol.apply import apply
from ai_dm.rules.healing import expire_max_hp, grant_max_hp
from ai_dm.state.creature import (
    ActiveEffect,
    AppliedCondition,
    CreatureState,
    DeathSaves,
    Expiry,
)
from ai_dm.state.hero import Minion
from ai_dm.state.world import NPC, PendingEvent

NOW = 1000


def purge(bundle):
    from ai_dm.rules.creatures import purge_expired

    return purge_expired(bundle)


def bundle_at(registry, now_s=NOW):
    bundle = make_bundle(registry)
    bundle.world.clock.now_s = now_s
    return bundle


def eff(effect_id, kind="seconds", value=0, effect_kind="buff"):
    expires = None if kind is None else Expiry(kind=kind, value=value)
    return ActiveEffect(id=effect_id, source="x", kind=effect_kind, expires=expires)


def cond(cond_id, kind="seconds", value=0):
    expires = None if kind is None else Expiry(kind=kind, value=value)
    return AppliedCondition(id=cond_id, source="x", expires=expires)


def effect_ids(creature):
    return [e.id for e in creature.active_effects]


def condition_ids(creature):
    return [c.id for c in creature.conditions]


def skeleton(hp=13, until_s=None):
    return Minion(monster_id="skeleton", spell_id="animate_dead", hp_current=hp, until_s=until_s)


def with_npc(bundle, creature=True):
    npc = NPC(
        id="npc_c", name="Кот", means=["x"],
        creature=CreatureState(hp_current=5, hp_max=5) if creature else None,
    )
    bundle.world.npcs["npc_c"] = npc
    return npc


# эффекты героя

def test_hero_expired_effect_is_removed(registry):
    bundle = bundle_at(registry)
    bundle.heroes[0].creature.active_effects = [eff("old", value=NOW - 1)]
    purge(bundle)
    assert effect_ids(bundle.heroes[0].creature) == []


def test_hero_effect_with_time_left_stays(registry):
    bundle = bundle_at(registry)
    bundle.heroes[0].creature.active_effects = [eff("fresh", value=NOW + 1)]
    purge(bundle)
    assert effect_ids(bundle.heroes[0].creature) == ["fresh"]


def test_effect_expiring_exactly_now_is_removed(registry):
    bundle = bundle_at(registry)
    bundle.heroes[0].creature.active_effects = [eff("edge", value=NOW)]
    purge(bundle)
    assert effect_ids(bundle.heroes[0].creature) == []


def test_effects_without_seconds_stay_even_with_small_value(registry):
    bundle = bundle_at(registry)
    kept = [eff("none", kind=None)] + [
        eff(kind, kind=kind, value=1)
        for kind in ("rounds", "end_of_turn", "start_of_turn", "concentration")
    ]
    bundle.heroes[0].creature.active_effects = list(kept)
    purge(bundle)
    assert effect_ids(bundle.heroes[0].creature) == [e.id for e in kept]


def test_purge_keeps_order_of_survivors(registry):
    bundle = bundle_at(registry)
    bundle.heroes[0].creature.active_effects = [
        eff("a", value=NOW + 5), eff("dead", value=1), eff("b", value=NOW + 9),
    ]
    purge(bundle)
    assert effect_ids(bundle.heroes[0].creature) == ["a", "b"]


# инвариант max_hp (Помощь)

def aided_bundle(registry, until=NOW - 10):
    bundle = bundle_at(registry)
    creature = bundle.heroes[0].creature
    creature.hp_max, creature.hp_current = 12, 12
    grant_max_hp(creature, "aid", "hero", 5, until)
    return bundle


def test_expired_max_hp_effect_stays_after_purge(registry):
    bundle = aided_bundle(registry)
    purge(bundle)
    assert effect_ids(bundle.heroes[0].creature) == ["aid"]


def test_purge_does_not_touch_hp_of_expired_aid(registry):
    bundle = aided_bundle(registry)
    purge(bundle)
    creature = bundle.heroes[0].creature
    assert (creature.hp_max, creature.hp_current) == (17, 17)


def test_expire_max_hp_still_reverts_after_purge(registry):
    bundle = aided_bundle(registry)
    purge(bundle)
    lines = expire_max_hp(bundle.heroes[0], bundle.world)
    assert lines == [f"Помощь кончилась: {bundle.heroes[0].name} HP 12/12"]
    assert effect_ids(bundle.heroes[0].creature) == []


# состояния (решение 10)

def test_expired_condition_is_removed(registry):
    bundle = bundle_at(registry)
    bundle.heroes[0].creature.conditions = [cond("invisible", value=NOW - 1)]
    purge(bundle)
    assert condition_ids(bundle.heroes[0].creature) == []


def test_condition_expiring_exactly_now_is_removed(registry):
    bundle = bundle_at(registry)
    bundle.heroes[0].creature.conditions = [cond("invisible", value=NOW)]
    purge(bundle)
    assert condition_ids(bundle.heroes[0].creature) == []


def test_conditions_that_must_stay(registry):
    bundle = bundle_at(registry)
    kept = [
        cond("future", value=NOW + 1),
        cond("rounds", kind="rounds", value=1),
        cond("conc", kind="concentration", value=1),
        cond("unconscious", kind=None),
    ]
    bundle.heroes[0].creature.conditions = list(kept)
    purge(bundle)
    assert condition_ids(bundle.heroes[0].creature) == [c.id for c in kept]


def test_npc_expired_condition_and_effect_are_removed(registry):
    bundle = bundle_at(registry)
    npc = with_npc(bundle)
    npc.creature.conditions = [cond("gone", value=NOW - 1), cond("kept", value=NOW + 1)]
    npc.creature.active_effects = [eff("gone", value=NOW), eff("kept", value=NOW + 1)]
    purge(bundle)
    assert (condition_ids(npc.creature), effect_ids(npc.creature)) == (["kept"], ["kept"])


def test_npc_without_creature_is_skipped(registry):
    bundle = bundle_at(registry)
    npc = with_npc(bundle, creature=False)
    purge(bundle)
    assert npc.creature is None


def test_expired_max_hp_of_npc_stays(registry):
    bundle = bundle_at(registry)
    npc = with_npc(bundle)
    grant_max_hp(npc.creature, "aid", "hero", 5, NOW - 1)
    purge(bundle)
    assert effect_ids(npc.creature) == ["aid"]


# второй герой бандла

def test_second_hero_of_bundle_is_purged(registry):
    bundle = bundle_at(registry)
    second = bundle.heroes[0].model_copy(deep=True)
    second.id = "hero2"
    second.creature.active_effects = [eff("old", value=1)]
    second.creature.conditions = [cond("old", value=1)]
    second.minions = [skeleton(until_s=1)]
    bundle.heroes.append(second)
    purge(bundle)
    assert (
        effect_ids(second.creature), condition_ids(second.creature), second.minions
    ) == ([], [], [])


# призванные вне боя (решение 11)

def test_minion_past_until_is_removed(registry):
    bundle = bundle_at(registry)
    bundle.heroes[0].minions = [skeleton(until_s=NOW - 1)]
    purge(bundle)
    assert bundle.heroes[0].minions == []


def test_minion_with_until_exactly_now_is_removed_like_expired(registry):
    bundle = bundle_at(registry)
    minion = skeleton(until_s=NOW)
    assert minions.expired(minion, NOW)
    bundle.heroes[0].minions = [minion]
    purge(bundle)
    assert bundle.heroes[0].minions == []


def test_minion_with_time_left_stays_with_hp(registry):
    bundle = bundle_at(registry)
    bundle.heroes[0].minions = [skeleton(hp=4, until_s=NOW + 1)]
    purge(bundle)
    assert [m.hp_current for m in bundle.heroes[0].minions] == [4]


def test_unlimited_familiar_stays(registry):
    bundle = bundle_at(registry)
    bird = Minion(monster_id="hawk", spell_id="find_familiar", hp_current=1, until_s=None)
    bundle.heroes[0].minions = [bird]
    purge(bundle)
    assert bundle.heroes[0].minions == [bird]


def test_minion_survivors_keep_order(registry):
    bundle = bundle_at(registry)
    bundle.heroes[0].minions = [
        skeleton(hp=1, until_s=NOW + 5), skeleton(hp=2, until_s=1), skeleton(hp=3, until_s=None),
    ]
    purge(bundle)
    assert [m.hp_current for m in bundle.heroes[0].minions] == [1, 3]


# призванные в активном бою

def fight_with_minions(registry, cfg, *minion_list):
    hero = make_wizard(registry)
    hero.minions = list(minion_list)
    engine = make_engine(
        registry, cfg, heroes=[hero], monsters=[mon("goblin_1", "goblin_warrior", "hall")],
        rng=ScriptedRng(),
    )
    for i, p in enumerate(minions.participants(hero, registry, "hall")):
        p.initiative = 50 - i
        engine.state.participants.append(p)
        engine.state.initiative_order.append(p.ref)
    bundle = bundle_at(registry, engine.world.clock.now_s)
    bundle.heroes = [hero]
    bundle.world = engine.world
    bundle.session.active_combat = engine.state
    return engine, bundle, hero


def test_minions_untouched_during_active_combat(registry, cfg):
    _, bundle, hero = fight_with_minions(
        registry, cfg, skeleton(hp=1, until_s=None), skeleton(hp=2, until_s=None)
    )
    now = bundle.world.clock.now_s
    hero.minions[0].until_s = now - 1
    before = [m.model_copy() for m in hero.minions]
    purge(bundle)
    assert hero.minions == before


def test_minion_ref_in_active_combat_still_points_to_same_minion(registry, cfg):
    engine, bundle, hero = fight_with_minions(
        registry, cfg, skeleton(hp=1), skeleton(hp=2), skeleton(hp=3)
    )
    hero.minions[0].until_s = bundle.world.clock.now_s - 1
    purge(bundle)
    ref = next(p.ref for p in engine.state.participants if p.ref.startswith("minion:1:"))
    assert hero.minions[int(ref.split(":")[1])].hp_current == 2


def test_active_combat_still_purges_effects_of_heroes(registry, cfg):
    _, bundle, hero = fight_with_minions(registry, cfg, skeleton())
    hero.creature.active_effects = [eff("old", value=bundle.world.clock.now_s - 1)]
    purge(bundle)
    assert effect_ids(hero.creature) == []


# бой целиком

def test_conclude_after_combat_drops_expired_and_purge_changes_nothing(registry, cfg):
    engine, bundle, hero = fight_with_minions(
        registry, cfg, skeleton(hp=7), skeleton(hp=9), skeleton(hp=11)
    )
    now = engine.world.clock.now_s
    hero.minions[0].until_s = now + 1
    purge(bundle)
    assert len(hero.minions) == 3
    end.conclude(engine)
    assert [m.hp_current for m in hero.minions] == [9, 11]
    bundle.session.active_combat = None
    before = bundle.heroes[0].model_dump_json()
    purge(bundle)
    assert bundle.heroes[0].model_dump_json() == before


# на экране

def test_minion_screen_text_same_before_and_after_purge(registry):
    bundle = bundle_at(registry)
    hero = bundle.heroes[0]
    hero.minions = [
        skeleton(hp=3, until_s=NOW + 600), skeleton(hp=4, until_s=NOW - 5), skeleton(until_s=None),
    ]
    before = minions.texts(hero, registry, NOW)
    purge(bundle)
    assert minions.texts(hero, registry, NOW) == before


# идемпотентность, формат

def test_purge_is_idempotent(registry):
    bundle = bundle_at(registry)
    bundle.heroes[0].creature.active_effects = [eff("old", value=1), eff("new", value=NOW + 1)]
    bundle.heroes[0].creature.conditions = [cond("old", value=1)]
    bundle.heroes[0].minions = [skeleton(until_s=1)]
    npc = with_npc(bundle)
    npc.creature.conditions = [cond("old", value=1)]
    purge(bundle)
    once = bundle.model_dump_json()
    purge(bundle)
    assert bundle.model_dump_json() == once


def test_purged_bundle_saves_and_loads_without_migration(registry, tmp_path):
    bundle = bundle_at(registry)
    bundle.manifest.schema_version = CURRENT_SCHEMA_VERSION
    bundle.heroes[0].creature.active_effects = [eff("old", value=1)]
    purge(bundle)
    save_slot(tmp_path, bundle, "auto", saved_at="2026-01-01T12:00:00Z")
    loaded = load_slot(tmp_path, "w1", "auto")
    assert loaded.manifest.schema_version == bundle.manifest.schema_version
    assert loaded.model_dump_json() == bundle.model_dump_json()


# М0 П4 (docs/plan-m0.md, «Тесты» П4): purge_expired -- одна точка после любого сдвига часов для
# отложенных событий (world.pending) и пробуждения
# стабильного (wake_at_s). Состояние проверяется после purge (возврат не смотрим); строки ленты --
# через advance_time (concentration_note). Допущение доебы: событие
# PendingEvent(kind="condition", ref=<id состояния>, text=<строка ленты>), target -- id героя
# или NPC.

HOUR = 3600
DAY = 86400


def event(at_s, target="hero", text="Началась лихорадка"):
    return PendingEvent(at_s=at_s, target=target, kind="condition", ref="diseased", text=text)


def shift(ctx, **fields):
    return apply(ctx, req("advance_time", **fields))


def ctx_at(registry, cfg, now_s):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.clock.now_s = now_s
    return ctx


def make_stable(creature, wake_at_s):
    creature.hp_current = 0
    creature.death_saves = DeathSaves(stable=True)
    creature.conditions = [AppliedCondition(id="unconscious", source="0_hp")]
    creature.wake_at_s = wake_at_s


# отложенные события

def test_pending_event_not_yet_due_changes_nothing(registry):
    bundle = bundle_at(registry)
    bundle.world.pending = [event(NOW + 1)]
    purge(bundle)
    assert condition_ids(bundle.heroes[0].creature) == []
    assert len(bundle.world.pending) == 1


def test_due_pending_event_puts_the_condition_on_the_hero_and_is_removed(registry):
    bundle = bundle_at(registry)
    bundle.world.pending = [event(NOW - 1)]
    purge(bundle)
    assert condition_ids(bundle.heroes[0].creature) == ["diseased"]
    assert bundle.world.pending == []


def test_pending_event_due_exactly_now_fires(registry):
    bundle = bundle_at(registry)
    bundle.world.pending = [event(NOW)]
    purge(bundle)
    assert condition_ids(bundle.heroes[0].creature) == ["diseased"]


def test_pending_event_fires_once(registry):
    bundle = bundle_at(registry)
    bundle.world.pending = [event(NOW - 1)]
    purge(bundle)
    purge(bundle)
    assert condition_ids(bundle.heroes[0].creature) == ["diseased"]


def test_pending_event_on_npc_without_creature_is_dropped_and_creates_nothing(registry):
    bundle = bundle_at(registry)
    npc = with_npc(bundle, creature=False)
    bundle.world.pending = [event(NOW - 1, target="npc_c")]
    purge(bundle)
    assert npc.creature is None
    assert bundle.world.pending == []


def test_pending_event_on_a_dead_target_is_dropped_without_error(registry):
    bundle = bundle_at(registry)
    npc = with_npc(bundle)
    npc.status = "dead"
    bundle.world.pending = [event(NOW - 1, target="npc_c")]
    purge(bundle)
    assert condition_ids(npc.creature) == []
    assert bundle.world.pending == []


def test_pending_event_on_an_unknown_target_is_dropped_without_error(registry):
    bundle = bundle_at(registry)
    bundle.world.pending = [event(NOW - 1, target="nobody")]
    purge(bundle)
    assert bundle.world.pending == []
    assert condition_ids(bundle.heroes[0].creature) == []


def test_pending_event_on_a_dead_hero_is_dropped_and_gives_no_condition(registry):
    bundle = bundle_at(registry)
    hero = bundle.heroes[0]
    hero.status = "dead"
    bundle.world.pending = [event(NOW - 1)]
    assert purge(bundle) == []
    assert condition_ids(hero.creature) == []
    assert bundle.world.pending == []


def test_pending_event_due_exactly_now_is_removed(registry):
    bundle = bundle_at(registry)
    bundle.world.pending = [event(NOW)]
    purge(bundle)
    assert bundle.world.pending == []


def test_pending_event_skipped_by_a_dead_target_does_not_stop_the_next_one(registry):
    bundle = bundle_at(registry)
    npc = with_npc(bundle)
    npc.status = "dead"
    bundle.world.pending = [event(NOW - 2, target="npc_c"), event(NOW - 1)]
    assert purge(bundle) == ["Началась лихорадка"]
    assert condition_ids(bundle.heroes[0].creature) == ["diseased"]


def test_started_condition_has_the_pending_source(registry):
    bundle = bundle_at(registry)
    bundle.world.pending = [event(NOW - 1)]
    purge(bundle)
    assert [c.source for c in bundle.heroes[0].creature.conditions] == ["pending"]


# М0 П4, сверка кода (решения 132, 133): строка срока -- только если состояние вешается и цель
# на виду (герой или NPC в локации героя)

def test_hero_target_gets_the_text_line(registry):
    bundle = bundle_at(registry)
    bundle.world.pending = [event(NOW - 1)]
    assert purge(bundle) == ["Началась лихорадка"]


def test_target_already_carrying_the_condition_gets_it_once_and_no_line(registry):
    bundle = bundle_at(registry)
    bundle.heroes[0].creature.conditions = [AppliedCondition(id="diseased", source="other")]
    bundle.world.pending = [event(NOW - 1)]
    lines = purge(bundle)
    assert lines == []
    assert condition_ids(bundle.heroes[0].creature) == ["diseased"]
    assert bundle.world.pending == []


def test_npc_in_the_hero_location_gives_the_line(registry):
    bundle = bundle_at(registry)
    npc = with_npc(bundle)
    npc.location_id = bundle.heroes[0].location_id
    bundle.world.pending = [event(NOW - 1, target="npc_c")]
    assert purge(bundle) == ["Началась лихорадка"]
    assert condition_ids(npc.creature) == ["diseased"]


def test_npc_in_another_location_gets_the_condition_without_a_line(registry):
    bundle = bundle_at(registry)
    npc = with_npc(bundle)
    npc.location_id = "forest"
    assert bundle.heroes[0].location_id != "forest"
    bundle.world.pending = [event(NOW - 1, target="npc_c")]
    assert purge(bundle) == []
    assert condition_ids(npc.creature) == ["diseased"]
    assert bundle.world.pending == []


def test_only_the_due_event_fires(registry):
    bundle = bundle_at(registry)
    bundle.world.pending = [event(NOW - 1), event(NOW + 500, text="Позже")]
    purge(bundle)
    assert [e.text for e in bundle.world.pending] == ["Позже"]


def test_advance_until_morning_starts_the_event_with_a_log_line(registry, cfg):
    ctx = ctx_at(registry, cfg, DAY + 22 * HOUR + 1800)
    ctx.bundle.world.pending = [event(2 * DAY + 6 * HOUR)]
    assert condition_ids(ctx.hero.creature) == []
    d = shift(ctx, until="morning")
    assert d.status == "accepted"
    assert condition_ids(ctx.hero.creature) == ["diseased"]
    assert "Началась лихорадка" in d.log


def test_second_shift_does_not_repeat_the_event_line(registry, cfg):
    ctx = ctx_at(registry, cfg, DAY + 22 * HOUR + 1800)
    ctx.bundle.world.pending = [event(2 * DAY + 6 * HOUR)]
    shift(ctx, until="morning")
    d = shift(ctx, category="hour", purpose="wait")
    assert "Началась лихорадка" not in d.log
    assert condition_ids(ctx.hero.creature) == ["diseased"]


def test_event_before_its_time_gives_no_line(registry, cfg):
    ctx = ctx_at(registry, cfg, DAY + 10 * HOUR)
    ctx.bundle.world.pending = [event(DAY + 20 * HOUR)]
    d = shift(ctx, category="hour", purpose="wait")
    assert "Началась лихорадка" not in d.log
    assert condition_ids(ctx.hero.creature) == []


# пробуждение стабильного

def test_stable_hero_wakes_at_the_term_with_one_hp(registry):
    bundle = bundle_at(registry)
    creature = bundle.heroes[0].creature
    make_stable(creature, NOW)
    purge(bundle)
    assert creature.hp_current == 1
    assert "unconscious" not in condition_ids(creature)
    assert creature.wake_at_s is None


def test_stable_hero_before_the_term_stays_down(registry):
    bundle = bundle_at(registry)
    creature = bundle.heroes[0].creature
    make_stable(creature, NOW + 1)
    purge(bundle)
    assert creature.hp_current == 0
    assert "unconscious" in condition_ids(creature)
    assert creature.wake_at_s == NOW + 1


def test_waking_clears_the_stable_flag(registry):
    bundle = bundle_at(registry)
    creature = bundle.heroes[0].creature
    make_stable(creature, NOW - 1)
    purge(bundle)
    assert creature.death_saves.stable is False


def test_hero_hurt_after_stabilizing_does_not_wake_and_loses_the_term_silently(registry):
    # урон по стабильному снимает stable (death_saves.py:91): по сроку герой не встаёт
    bundle = bundle_at(registry)
    creature = bundle.heroes[0].creature
    make_stable(creature, NOW - 1)
    creature.death_saves = DeathSaves(stable=False, failures=1)
    lines = purge(bundle)
    assert lines == []
    assert creature.hp_current == 0
    assert "unconscious" in condition_ids(creature)
    assert creature.wake_at_s is None


def test_dead_hero_with_a_due_wake_term_does_not_wake(registry):
    bundle = bundle_at(registry)
    hero = bundle.heroes[0]
    make_stable(hero.creature, NOW - 1)
    hero.status = "dead"
    assert purge(bundle) == []
    assert hero.creature.hp_current == 0


def test_hero_not_due_does_not_stop_the_waking_of_the_next_one(registry):
    bundle = bundle_at(registry)
    second = bundle.heroes[0].model_copy(deep=True)
    second.id = "hero2"
    bundle.heroes.append(second)
    make_stable(bundle.heroes[0].creature, NOW + 100)
    make_stable(second.creature, NOW - 1)
    purge(bundle)
    assert (bundle.heroes[0].creature.hp_current, second.creature.hp_current) == (0, 1)


def test_waking_removes_only_the_zero_hp_unconscious_and_keeps_the_other_sources(registry):
    bundle = bundle_at(registry)
    creature = bundle.heroes[0].creature
    make_stable(creature, NOW - 1)
    creature.conditions.append(AppliedCondition(id="unconscious", source="sleep"))
    creature.conditions.append(AppliedCondition(id="prone", source="0_hp"))
    purge(bundle)
    assert [(c.id, c.source) for c in creature.conditions] == [
        ("unconscious", "sleep"), ("prone", "0_hp"),
    ]


def test_hero_without_wake_term_is_not_touched(registry):
    bundle = bundle_at(registry)
    creature = bundle.heroes[0].creature
    make_stable(creature, None)
    purge(bundle)
    assert creature.hp_current == 0
    assert "unconscious" in condition_ids(creature)


def test_waking_gives_the_log_line(registry, cfg):
    ctx = ctx_at(registry, cfg, DAY + 10 * HOUR)
    make_stable(ctx.hero.creature, DAY + 10 * HOUR + 1800)
    d = shift(ctx, category="hour", purpose="wait")
    assert f"{ctx.hero.name} приходит в себя: HP 1" in d.log
    assert ctx.hero.creature.hp_current == 1
