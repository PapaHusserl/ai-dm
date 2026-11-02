# К1 «Концентрация по часам» вне боя (docs/plan-k1.md, п. 2.4-2.5; В2а, В4а):
#   cast_spell Метки охотника вне боя: Concentration.until_s = now + 3600, в результате `until`,
#     эффект героя kind=spell с Expiry seconds = now + 3600, mark_pending с Expiry concentration;
#   после каждого сдвига часов (rest, advance_time по категории, travel) концентрация с
#     until_s <= now кончается ("ровно в срок" -- кончилась): снимается объект, mark_pending и
#     эффект spell; в log «Концентрация: <заклинание> кончилась»,
#     result["concentration_ended"] = spell_id;
#     пока срок не вышел -- держится и записей нет. Бессрочная (until_s None, старый сейв) держится.
#   Грей из campaigns/drunk_dragon (следопыт: Метка охотника, Избранный враг 2), как в
#   tests/unit/game/test_cast_explore.py.
from pathlib import Path

import game_kit  # noqa: F401  (добавляет в sys.path соседние kit-ы)
import pytest
from protocol_kit import make_ctx, req

from ai_dm.campaign.loader import load_pack, pack_content_dir
from ai_dm.content.loader import load_registry
from ai_dm.game.starter import new_world_from_pack
from ai_dm.protocol.apply import apply
from ai_dm.state.creature import ActiveEffect, Concentration, Expiry

DRAGON = Path(__file__).resolve().parents[3] / "campaigns" / "drunk_dragon"
HOUR = 3600


@pytest.fixture
def dragon(cfg):
    registry = load_registry([pack_content_dir(DRAGON)])
    bundle = new_world_from_pack(
        registry, cfg, load_pack(DRAGON, registry), hero="grey", seed=1, world_id="w1",
        saved_at="2026-01-01T00:00:00",
    )
    return registry, bundle


def cast_mark(registry, cfg, bundle):
    hero = bundle.heroes[0]
    npc = "jorgen"
    bundle.world.npcs[npc].location_id = hero.location_id
    ctx = make_ctx(registry, cfg, bundle=bundle)
    fields = {"spell_id": "hunters_mark", "circle": 1, "target": npc, "free": True}
    return ctx, apply(ctx, req("cast_spell", **fields))


def marked(registry, cfg, bundle):
    cast_mark(registry, cfg, bundle)
    return bundle.heroes[0]


def kinds(hero):
    return sorted(e.kind for e in hero.creature.active_effects)


def go(registry, cfg, bundle, type_name, **fields):
    ctx = make_ctx(registry, cfg, bundle=bundle)
    return apply(ctx, req(type_name, **fields))


def test_free_mark_spends_the_favored_enemy_pool_and_not_a_slot(dragon, cfg):
    registry, bundle = dragon
    hero = bundle.heroes[0]
    resources = hero.creature.resources
    resources["spell_slot:1"].current = 0
    before = resources["favored_enemy"].current
    _, d = cast_mark(registry, cfg, bundle)
    assert d.status == "accepted"
    assert resources["favored_enemy"].current == before - 1
    assert resources["spell_slot:1"].current == 0
    assert d.log[0].endswith("(1 круг, бесплатное применение)")


# Метка вне боя: срок 1 ч

def test_mark_outside_combat_sets_until_one_hour_ahead(dragon, cfg):
    registry, bundle = dragon
    start = bundle.world.clock.now_s
    hero = marked(registry, cfg, bundle)
    assert hero.creature.concentration.until_s == start + HOUR


def test_mark_outside_combat_reports_until(dragon, cfg):
    registry, bundle = dragon
    ctx, d = cast_mark(registry, cfg, bundle)
    assert d.result["until"]


def test_mark_outside_combat_puts_a_timed_spell_effect_on_the_hero(dragon, cfg):
    registry, bundle = dragon
    start = bundle.world.clock.now_s
    hero = marked(registry, cfg, bundle)
    spell = [e for e in hero.creature.active_effects if e.kind == "spell"][0]
    assert spell.expires == Expiry(kind="seconds", value=start + HOUR)


def test_mark_outside_combat_keeps_mark_pending_with_concentration_expiry(dragon, cfg):
    registry, bundle = dragon
    hero = marked(registry, cfg, bundle)
    pending = [e for e in hero.creature.active_effects if e.kind == "mark_pending"][0]
    assert pending.expires == Expiry(kind="concentration", owner=hero.id)


# advance_time по категории

def test_advance_an_hour_ends_the_mark_exactly_at_the_limit(dragon, cfg):
    registry, bundle = dragon
    hero = marked(registry, cfg, bundle)
    d = go(registry, cfg, bundle, "advance_time", category="hour")
    assert hero.creature.concentration is None
    assert d.result["concentration_ended"] == "hunters_mark"


def test_mark_ends_after_a_quarter_hour_and_then_an_hour_and_not_before(dragon, cfg):
    registry, bundle = dragon
    hero = marked(registry, cfg, bundle)
    bundle.world.clock.advance(900)
    assert hero.creature.concentration is not None
    d = go(registry, cfg, bundle, "advance_time", category="hour")
    assert hero.creature.concentration is None
    assert d.result["concentration_ended"] == "hunters_mark"


def test_expired_mark_log_names_the_spell(dragon, cfg):
    registry, bundle = dragon
    marked(registry, cfg, bundle)
    d = go(registry, cfg, bundle, "advance_time", category="day")
    assert "Концентрация: Метка охотника кончилась" in d.log


def test_expired_mark_removes_mark_pending_and_the_spell_effect(dragon, cfg):
    registry, bundle = dragon
    hero = marked(registry, cfg, bundle)
    go(registry, cfg, bundle, "advance_time", category="day")
    assert "mark_pending" not in kinds(hero)
    assert "spell" not in kinds(hero)


def test_second_note_does_not_repeat_after_the_first(dragon, cfg):
    registry, bundle = dragon
    marked(registry, cfg, bundle)
    go(registry, cfg, bundle, "advance_time", category="day")
    d = go(registry, cfg, bundle, "advance_time", category="day")
    assert "concentration_ended" not in d.result
    assert d.log == [f"Время идёт: {86400} с"]


def test_unlimited_concentration_survives_a_day(dragon, cfg):
    registry, bundle = dragon
    hero = bundle.heroes[0]
    hero.creature.concentration = Concentration(spell_id="fog_cloud", circle=1, until_s=None)
    d = go(registry, cfg, bundle, "advance_time", category="day")
    assert hero.creature.concentration is not None
    assert "concentration_ended" not in d.result


def test_advance_without_concentration_has_the_plain_result(dragon, cfg):
    registry, bundle = dragon
    d = go(registry, cfg, bundle, "advance_time", category="hour")
    assert set(d.result) == {"seconds", "now_s"}
    assert d.log == ["Время идёт: 3600 с"]


# rest

def test_long_rest_ends_the_mark(dragon, cfg):
    registry, bundle = dragon
    hero = marked(registry, cfg, bundle)
    d = go(registry, cfg, bundle, "rest", kind="long")
    assert hero.creature.concentration is None
    assert d.result["concentration_ended"] == "hunters_mark"
    assert "Концентрация: Метка охотника кончилась" in d.log


def test_short_rest_ends_the_mark_exactly_at_the_hour(dragon, cfg):
    registry, bundle = dragon
    hero = marked(registry, cfg, bundle)
    assert cfg.time.short_rest_s == HOUR
    d = go(registry, cfg, bundle, "rest", kind="short")
    assert hero.creature.concentration is None
    assert d.result["concentration_ended"] == "hunters_mark"


def test_short_rest_keeps_a_longer_concentration(dragon, cfg):
    registry, bundle = dragon
    hero = bundle.heroes[0]
    now = bundle.world.clock.now_s
    hero.creature.concentration = Concentration(
        spell_id="hunters_mark", circle=1, until_s=now + HOUR + 1
    )
    d = go(registry, cfg, bundle, "rest", kind="short")
    assert hero.creature.concentration is not None
    assert "concentration_ended" not in d.result


def test_rest_without_concentration_has_the_plain_result(dragon, cfg):
    registry, bundle = dragon
    d = go(registry, cfg, bundle, "rest", kind="long")
    assert set(d.result) == {"hp", "now_s"}


# travel

def put_hero_in_vale(registry, cfg):
    ctx = make_ctx(registry, cfg)
    hero = ctx.hero
    return ctx, hero


def test_travel_ends_a_concentration_that_ran_out_on_the_road(registry, cfg):
    ctx, hero = put_hero_in_vale(registry, cfg)
    hero.creature.concentration = Concentration(spell_id="bless", circle=1, until_s=60)
    hero.creature.active_effects.append(
        ActiveEffect(id="bless", source=hero.id, kind="spell",
                     expires=Expiry(kind="concentration", owner=hero.id))
    )
    d = apply(ctx, req("advance_time", travel_to="forest"))
    assert hero.creature.concentration is None
    assert d.result["concentration_ended"] == "bless"
    assert "Концентрация: Благословение кончилась" in d.log
    assert hero.creature.active_effects == []


def test_travel_keeps_a_concentration_that_outlives_the_road(registry, cfg):
    ctx, hero = put_hero_in_vale(registry, cfg)
    hero.creature.concentration = Concentration(spell_id="bless", circle=1, until_s=10**6)
    d = apply(ctx, req("advance_time", travel_to="forest"))
    assert hero.creature.concentration is not None
    assert "concentration_ended" not in d.result
    assert d.log[0].startswith("Путь в")


def test_travel_ends_exactly_when_the_road_takes_the_whole_time(registry, cfg):
    ctx, hero = put_hero_in_vale(registry, cfg)
    seconds = 4800 * 3600 // cfg.time.travel_pace["normal"]
    hero.creature.concentration = Concentration(
        spell_id="bless", circle=1, until_s=ctx.bundle.world.clock.now_s + seconds
    )
    d = apply(ctx, req("advance_time", travel_to="forest"))
    assert d.result["concentration_ended"] == "bless"


def test_invalid_travel_does_not_end_anything(registry, cfg):
    ctx, hero = put_hero_in_vale(registry, cfg)
    hero.creature.concentration = Concentration(spell_id="bless", circle=1, until_s=0)
    apply(ctx, req("advance_time", travel_to="nowhere"))
    assert hero.creature.concentration is not None


# К3 П3а: Бесследное передвижение (pass_without_trace) вне боя -- следопыт Грей (BACKLOG 11).
# До П3а у заклинания не было effects и cast_spell молча ставил концентрацию; с видом buff
# params эффекта обязаны пройти валидацию ActiveEffect (значения int | str | bool, без None).

@pytest.fixture
def tracer(dragon):
    # Грей 5 ур. со второй ячейкой (в живом мире он выше): Бесследное передвижение подготовлено
    from ai_dm.rules.progression import sync_resources

    registry, bundle = dragon
    hero = bundle.heroes[0]
    hero.sheet.primary.level = 5
    hero.sheet.prepared_of().append("pass_without_trace")
    sync_resources(hero, registry)
    return dragon


def cast_trace(registry, cfg, bundle, **fields):
    ctx = make_ctx(registry, cfg, bundle=bundle)
    data = {"spell_id": "pass_without_trace", "circle": 2, "target": "hero", "free": False}
    return ctx, apply(ctx, req("cast_spell", **(data | fields)))


def stealth_total(registry, cfg, bundle):
    from ai_dm.core.rng import Rng

    ctx = make_ctx(registry, cfg, rng=Rng(7), bundle=bundle)
    return apply(ctx, req("skill_check", skill="stealth", category="easy")).result["total"]


def test_pass_without_trace_outside_combat_is_accepted(tracer, cfg):
    registry, bundle = tracer
    _, d = cast_trace(registry, cfg, bundle)
    assert d.status == "accepted"


def test_pass_without_trace_puts_a_stealth_modifier_on_the_hero(tracer, cfg):
    registry, bundle = tracer
    cast_trace(registry, cfg, bundle)
    hero = bundle.heroes[0]
    modifiers = [e for e in hero.creature.active_effects if e.kind == "modifier"]
    assert [(e.id, e.params) for e in modifiers] == [
        ("pass_without_trace", {"target": "skill", "skill": "stealth", "amount": 10})
    ]
    assert modifiers[0].expires == Expiry(kind="concentration", owner=hero.id)


def test_pass_without_trace_holds_concentration_for_an_hour(tracer, cfg):
    registry, bundle = tracer
    start = bundle.world.clock.now_s
    _, d = cast_trace(registry, cfg, bundle)
    assert bundle.heroes[0].creature.concentration.spell_id == "pass_without_trace"
    assert bundle.heroes[0].creature.concentration.until_s == start + HOUR
    assert d.result["concentration"] == "pass_without_trace"


def test_pass_without_trace_spends_a_second_circle_slot(tracer, cfg):
    registry, bundle = tracer
    pool = bundle.heroes[0].creature.resources["spell_slot:2"]
    before = pool.current
    cast_trace(registry, cfg, bundle)
    assert pool.current == before - 1


def test_pass_without_trace_adds_10_to_a_stealth_check(tracer, cfg):
    registry, bundle = tracer
    plain = stealth_total(registry, cfg, bundle.model_copy(deep=True))
    cast_trace(registry, cfg, bundle)
    assert stealth_total(registry, cfg, bundle) == plain + 10


def test_pass_without_trace_does_not_change_other_skill_checks(tracer, cfg):
    from ai_dm.core.rng import Rng

    registry, bundle = tracer

    def total(current):
        ctx = make_ctx(registry, cfg, rng=Rng(7), bundle=current)
        return apply(ctx, req("skill_check", skill="athletics", category="easy")).result["total"]

    plain = total(bundle.model_copy(deep=True))
    cast_trace(registry, cfg, bundle)
    assert total(bundle) == plain


def test_pass_without_trace_cannot_be_cast_at_a_higher_circle_outside_combat(tracer, cfg):
    registry, bundle = tracer
    _, d = cast_trace(registry, cfg, bundle, circle=3)
    assert d.code == "bad_circle"


def test_pass_without_trace_ends_with_its_hour(tracer, cfg):
    registry, bundle = tracer
    cast_trace(registry, cfg, bundle)
    go(registry, cfg, bundle, "advance_time", category="hour")
    assert bundle.heroes[0].creature.concentration is None
    assert [e for e in bundle.heroes[0].creature.active_effects if e.kind == "modifier"] == []
