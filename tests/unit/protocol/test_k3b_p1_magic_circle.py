# К3б П1, решение 16 (Р-К3б-7 б): Магический круг по SRD -- читается вне боя (cast_spell, 1 минута),
# эффект ложится на героя; start_combat привязывает его к стартовой зоне героя; в бою нежить (теги
# круга) не входит в зону и бьёт по находящимся внутри с помехой, зверь входит свободно.
import sys
from pathlib import Path

import game_kit  # noqa: F401  (добавляет в sys.path соседние kit-ы)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "combat"))

from combat_kit import ScriptedRng  # noqa: E402
from protocol_kit import combat_request  # noqa: E402
from test_wizard_rest_cast import cast, wizard_bundle  # noqa: E402

from ai_dm.combat.engine import CombatEngine  # noqa: E402
from ai_dm.protocol.apply import apply  # noqa: E402
from ai_dm.protocol.decision import Invalid  # noqa: E402

ENEMIES = [
    {"ref": "skel_1", "monster_id": "skeleton", "zone": "door", "group": "undead"},
    {"ref": "wolf_1", "monster_id": "wolf", "zone": "balcony", "group": "undead"},
]
GROUPS = [{"id": "undead", "leader": "skel_1", "intent": "kill"}]


def circle_effects(bundle):
    return [e for e in bundle.heroes[0].creature.active_effects if e.id == "magic_circle"]


def cast_circle(registry, cfg):
    bundle = wizard_bundle(registry, level=5)
    bundle.heroes[0].sheet.prepared_of().append("magic_circle")
    ctx, result = cast(registry, cfg, bundle, "magic_circle")
    assert not isinstance(result, Invalid)
    return ctx


def fight(registry, cfg, rng=None, wait_s=0):
    ctx = cast_circle(registry, cfg)
    if wait_s:
        ctx.bundle.world.clock.advance(wait_s)
    result = apply(ctx, combat_request(enemies=ENEMIES, groups=GROUPS, hero_zone="hall"))
    assert not isinstance(result, Invalid)
    state = ctx.bundle.session.active_combat
    state.round = 1
    state.initiative_order = [p.ref for p in state.participants]
    for i, p in enumerate(state.participants):
        p.initiative = 100 - i
    hero = ctx.bundle.heroes[0]
    engine = CombatEngine(
        state, ctx.bundle.world, {hero.id: hero}, registry, cfg, rng or ScriptedRng()
    )
    return ctx, engine


def test_cast_outside_combat_puts_the_circle_on_the_hero(registry, cfg):
    ctx = cast_circle(registry, cfg)
    assert len(circle_effects(ctx.bundle)) == 1


def test_circle_outside_combat_shows_in_sheet_effects_with_its_end(registry, cfg):
    # решение 19: «Эффекты:» -- «Магический круг (до HH:MM)»
    from ai_dm.game.sheet_text import effect_lines

    ctx = cast_circle(registry, cfg)
    hero = ctx.bundle.heroes[0]
    lines = effect_lines(hero, ctx.bundle.world.clock.now_s, registry)
    assert [x for x in lines if x.startswith("Магический круг")]
    assert [x for x in lines if x.startswith("Магический круг")][0].startswith(
        "Магический круг (до "
    )


def test_circle_cast_log_names_the_hero(registry, cfg):
    bundle = wizard_bundle(registry, level=5)
    bundle.heroes[0].sheet.prepared_of().append("magic_circle")
    _, result = cast(registry, cfg, bundle, "magic_circle")
    assert f"  Магический круг: вокруг {bundle.heroes[0].name}" in result.log


def test_recasting_the_circle_does_not_duplicate_the_effect(registry, cfg):
    from ai_dm.game.sheet_text import effect_lines

    bundle = wizard_bundle(registry, level=5)
    bundle.heroes[0].sheet.prepared_of().append("magic_circle")
    cast(registry, cfg, bundle, "magic_circle")
    cast(registry, cfg, bundle, "magic_circle")
    assert len(circle_effects(bundle)) == 1
    lines = effect_lines(bundle.heroes[0], bundle.world.clock.now_s, registry)
    assert len([x for x in lines if x.startswith("Магический круг")]) == 1


def test_cast_outside_combat_spends_a_third_circle_slot(registry, cfg):
    bundle = wizard_bundle(registry, level=5)
    bundle.heroes[0].sheet.prepared_of().append("magic_circle")
    before = bundle.heroes[0].creature.resources["spell_slot:3"].current
    cast(registry, cfg, bundle, "magic_circle")
    assert bundle.heroes[0].creature.resources["spell_slot:3"].current == before - 1


def test_start_combat_binds_the_circle_to_the_hero_start_zone(registry, cfg):
    ctx, _ = fight(registry, cfg)
    (effect,) = circle_effects(ctx.bundle)
    assert effect.params["zone"] == "hall"


def test_undead_cannot_enter_the_circle_zone(registry, cfg):
    _, engine = fight(registry, cfg)
    assert "move:hall" not in [o.id for o in engine.available_actions("skel_1")]


def test_expired_circle_is_not_a_zone_effect_in_the_next_combat(registry, cfg):
    # круг на час: через час и секунду он не действует (zone_effects читает только живые эффекты)
    from ai_dm.combat.zone_effects import zone_effects

    _, engine = fight(registry, cfg, wait_s=3601)
    assert zone_effects(engine, "hall", "circle") == []


def test_expired_circle_is_left_unbound_by_start_combat(registry, cfg):
    ctx, _ = fight(registry, cfg, wait_s=3601)
    (effect,) = circle_effects(ctx.bundle)
    assert effect.params["zone"] == ""


def test_undead_enters_the_zone_of_an_expired_circle(registry, cfg):
    _, engine = fight(registry, cfg, wait_s=3601)
    assert "move:hall" in [o.id for o in engine.available_actions("skel_1")]


def test_beast_enters_the_circle_zone(registry, cfg):
    _, engine = fight(registry, cfg)
    assert "move:hall" in [o.id for o in engine.available_actions("wolf_1")]


def test_undead_attack_into_the_circle_has_disadvantage(registry, cfg):
    # d20 19 и 3: худший 3 + 4 = 7 < КД волшебника
    rng = ScriptedRng(d20=[19, 3])
    ctx, engine = fight(registry, cfg, rng)
    before = ctx.bundle.heroes[0].creature.hp_current
    engine.perform("skel_1", "attack:короткий_лук:hero")
    assert rng.left("d20") == 0
    assert ctx.bundle.heroes[0].creature.hp_current == before
