# К8с П2 (docs/plan-k8s.md, «Тесты» П2): Метка охотника вне боя ячейкой 3 круга -- срок 8 часов.
#   cast_spell{circle: 3}: Concentration.until_s = now + 28800, метка kind="spell" -- до того же
#   часа, `until` в результате -- на 8 ч вперёд, ячейка 3 круга тратится; короткий отдых (час мира)
#   восьмичасовую Метку не снимает; круг 1 -- как до К8с (час).
from pathlib import Path

import game_kit  # noqa: F401  (добавляет в sys.path соседние kit-ы)
import pytest
from protocol_kit import make_ctx, req

from ai_dm.campaign.loader import load_pack, pack_content_dir
from ai_dm.content.loader import load_registry
from ai_dm.game.starter import new_world_from_pack
from ai_dm.protocol.apply import apply
from ai_dm.rules.derived import clock_text
from ai_dm.state.creature import Expiry, ResourcePool

DRAGON = Path(__file__).resolve().parents[3] / "campaigns" / "drunk_dragon"
HOUR = 3600


@pytest.fixture
def dragon(cfg):
    registry = load_registry([pack_content_dir(DRAGON)])
    bundle = new_world_from_pack(
        registry, cfg, load_pack(DRAGON, registry), hero="grey", seed=1, world_id="w1",
        saved_at="2026-01-01T00:00:00",
    )
    bundle.heroes[0].creature.resources["spell_slot:3"] = ResourcePool(current=2, max=2)
    return registry, bundle


def cast_mark(registry, cfg, bundle, circle):
    hero = bundle.heroes[0]
    bundle.world.npcs["jorgen"].location_id = hero.location_id
    ctx = make_ctx(registry, cfg, bundle=bundle)
    fields = {"spell_id": "hunters_mark", "circle": circle, "target": "jorgen", "free": False}
    return apply(ctx, req("cast_spell", **fields))


def test_third_circle_mark_is_accepted(dragon, cfg):
    registry, bundle = dragon
    assert cast_mark(registry, cfg, bundle, 3).status == "accepted"


def test_third_circle_mark_holds_concentration_for_eight_hours(dragon, cfg):
    registry, bundle = dragon
    start = bundle.world.clock.now_s
    cast_mark(registry, cfg, bundle, 3)
    assert bundle.heroes[0].creature.concentration.until_s == start + 8 * HOUR


def test_third_circle_mark_reports_the_eight_hour_end(dragon, cfg):
    registry, bundle = dragon
    start = bundle.world.clock.now_s
    d = cast_mark(registry, cfg, bundle, 3)
    assert d.result["until"] == clock_text(start + 8 * HOUR)


def test_third_circle_mark_puts_a_spell_effect_for_eight_hours(dragon, cfg):
    registry, bundle = dragon
    start = bundle.world.clock.now_s
    cast_mark(registry, cfg, bundle, 3)
    effect = [e for e in bundle.heroes[0].creature.active_effects if e.kind == "spell"][0]
    assert effect.expires == Expiry(kind="seconds", value=start + 8 * HOUR)


def test_third_circle_mark_spends_a_third_circle_slot(dragon, cfg):
    registry, bundle = dragon
    cast_mark(registry, cfg, bundle, 3)
    assert bundle.heroes[0].creature.resources["spell_slot:3"].current == 1


@pytest.mark.parametrize("circle", [2, 4])
def test_second_and_fourth_circle_mark_is_refused_outside_combat(dragon, cfg, circle):
    registry, bundle = dragon
    bundle.heroes[0].creature.resources[f"spell_slot:{circle}"] = ResourcePool(current=2, max=2)
    d = cast_mark(registry, cfg, bundle, circle)
    assert d.code == "bad_circle"


@pytest.mark.parametrize("circle", [2, 4])
def test_refused_mark_keeps_the_slot_and_concentration(dragon, cfg, circle):
    registry, bundle = dragon
    hero = bundle.heroes[0]
    hero.creature.resources[f"spell_slot:{circle}"] = ResourcePool(current=2, max=2)
    cast_mark(registry, cfg, bundle, circle)
    assert hero.creature.resources[f"spell_slot:{circle}"].current == 2
    assert hero.creature.concentration is None


def test_first_circle_mark_still_lasts_an_hour(dragon, cfg):
    registry, bundle = dragon
    start = bundle.world.clock.now_s
    cast_mark(registry, cfg, bundle, 1)
    assert bundle.heroes[0].creature.concentration.until_s == start + HOUR


def test_short_rest_keeps_the_eight_hour_mark(dragon, cfg):
    registry, bundle = dragon
    cast_mark(registry, cfg, bundle, 3)
    d = apply(make_ctx(registry, cfg, bundle=bundle), req("rest", kind="short"))
    assert bundle.heroes[0].creature.concentration is not None
    assert "concentration_ended" not in d.result


def test_long_rest_ends_the_eight_hour_mark(dragon, cfg):
    registry, bundle = dragon
    cast_mark(registry, cfg, bundle, 3)
    d = apply(make_ctx(registry, cfg, bundle=bundle), req("rest", kind="long"))
    assert bundle.heroes[0].creature.concentration is None
    assert d.result["concentration_ended"] == "hunters_mark"


# каждое из 24 заклинаний вне боя, базовым кругом (К8с П2, «Ответы папы П2», п. 2)

HERO = {"target": "hero"}
TABLE = (
    [(s, "accepted", HERO) for s in (
        "aid", "darkvision", "detect_magic", "detect_poison_and_disease", "find_traps",
        "gust_of_wind", "jump", "locate_object", "magic_weapon", "meld_into_stone", "nondetection",
        "protection_from_poison", "water_breathing", "water_walk", "conjure_animals", "wind_wall",
        "plant_growth", "speak_with_plants")]
    + [("enhance_ability", "accepted", {"target": "hero", "variant": "str"}),
       ("protection_from_energy", "accepted", {"target": "hero", "variant": "fire"})]
    + [(s, "combat_only", HERO) for s in ("daylight", "silence")]
    + [(s, "bad_target", {"target": "jorgen"}) for s in ("dispel_magic", "revivify")]
)


def cast_base(registry, cfg, bundle, spell_id, fields):
    hero = bundle.heroes[0]
    for circle in (1, 2, 3):
        hero.creature.resources[f"spell_slot:{circle}"] = ResourcePool(current=2, max=2)
    hero.sheet.prepared_of().append(spell_id)
    bundle.world.npcs["jorgen"].location_id = hero.location_id
    level = registry.get("spell", spell_id).level
    data = {"spell_id": spell_id, "circle": level, "free": False} | fields
    return apply(make_ctx(registry, cfg, bundle=bundle), req("cast_spell", **data))


@pytest.mark.parametrize("spell_id, outcome, fields", TABLE)
def test_ranger_spell_outside_combat(dragon, cfg, spell_id, outcome, fields):
    registry, bundle = dragon
    d = cast_base(registry, cfg, bundle, spell_id, fields)
    assert (d.status if outcome == "accepted" else d.code) == outcome


def test_conjure_animals_outside_combat_holds_concentration(dragon, cfg):
    registry, bundle = dragon
    d = cast_base(registry, cfg, bundle, "conjure_animals", HERO)
    assert d.result["concentration"] == "conjure_animals"


def test_conjure_animals_outside_combat_ends_in_ten_minutes(dragon, cfg):
    registry, bundle = dragon
    start = bundle.world.clock.now_s
    d = cast_base(registry, cfg, bundle, "conjure_animals", HERO)
    assert d.result["until"] == clock_text(start + 600)


@pytest.mark.parametrize("spell_id, text", [
    ("plant_growth", "Растения в выбранном месте буйно разрастаются: идти там вчетверо труднее."),
    ("speak_with_plants", "Растения в 30 фт. десять минут отвечают на вопросы о последних сутках "
                          "и слушаются простых просьб."),
])
def test_plant_spell_outside_combat_reports_the_effect_text(dragon, cfg, spell_id, text):
    registry, bundle = dragon
    d = cast_base(registry, cfg, bundle, spell_id, HERO)
    assert d.result["effect"] == text
