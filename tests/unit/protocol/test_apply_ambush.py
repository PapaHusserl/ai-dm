# Засада (stage3-live-advantage V2): start_combat с hero_hidden=true -- герой начинает бой
# в состоянии "hidden" (первая атака с преимуществом), без флага -- нет.
from protocol_kit import combat_request, goblin, make_ctx, req, zone

from ai_dm.protocol.apply import apply


def request(**extra):
    return req(
        "start_combat",
        zones=[zone("door", ["hall"]), zone("hall", ["door", "balcony"]),
               zone("balcony", ["hall"])],
        enemies=[goblin("g1")], groups=[{"id": "goblins", "leader": "g1", "intent": "kill"}],
        hero_zone="door", initiated_by="hero", **extra,
    )


def hero_conditions(ctx):
    state = ctx.bundle.session.active_combat
    return [(c.id, c.source) for c in ctx.hero.creature.conditions] if state else []


def test_hero_hidden_start_makes_hero_hidden(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, request(hero_hidden=True))
    assert ("invisible", "hidden") in hero_conditions(ctx)


def test_default_start_leaves_hero_visible(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, request())
    assert ("invisible", "hidden") not in hero_conditions(ctx)


def test_hero_hidden_is_false_by_default(registry, cfg):
    assert combat_request().hero_hidden is False
