# К3б П1, решение 18 (Р-К3б-9 а): вне боя Защитные узы и Видение невидимого действуют на час;
# Святилище, Тьма, Тишина, Ледяной шторм и Дневной свет -- отказ combat_only «<заклинание>
# читается только в бою», ячейка не тратится.
import game_kit  # noqa: F401  (добавляет в sys.path соседние kit-ы)
import pytest
from test_wizard_rest_cast import cast, wizard_bundle

from ai_dm.protocol.decision import Invalid

HOUR = 3600
CIRCLES = {
    "warding_bond": 2, "see_invisibility": 2, "sanctuary": 1, "darkness": 2, "silence": 2,
    "sleet_storm": 3, "daylight": 3,
}


def bundle_with(registry, spell_id):
    bundle = wizard_bundle(registry, level=5)
    bundle.heroes[0].sheet.prepared_of().append(spell_id)
    return bundle


def slot(bundle, circle):
    return bundle.heroes[0].creature.resources[f"spell_slot:{circle}"].current


def effects_of(bundle, spell_id):
    return [e for e in bundle.heroes[0].creature.active_effects if e.id == spell_id]


@pytest.mark.parametrize("spell_id", ["warding_bond", "see_invisibility"])
def test_defense_outside_combat_is_accepted_and_spends_a_slot(registry, cfg, spell_id):
    bundle = bundle_with(registry, spell_id)
    before = slot(bundle, CIRCLES[spell_id])
    _, result = cast(registry, cfg, bundle, spell_id, circle=CIRCLES[spell_id])
    assert not isinstance(result, Invalid)
    assert slot(bundle, CIRCLES[spell_id]) == before - 1


@pytest.mark.parametrize("spell_id", ["warding_bond", "see_invisibility"])
def test_defense_outside_combat_lasts_an_hour(registry, cfg, spell_id):
    bundle = bundle_with(registry, spell_id)
    now = bundle.world.clock.now_s
    cast(registry, cfg, bundle, spell_id, circle=CIRCLES[spell_id])
    found = effects_of(bundle, spell_id)
    assert found
    assert all(e.expires.kind == "seconds" and e.expires.value == now + HOUR for e in found)


def test_see_invisibility_outside_combat_leaves_a_see_invisible_effect(registry, cfg):
    bundle = bundle_with(registry, "see_invisibility")
    cast(registry, cfg, bundle, "see_invisibility", circle=2)
    assert "see_invisible" in [e.kind for e in effects_of(bundle, "see_invisibility")]


def test_warding_bond_outside_combat_halves_all_damage(registry, cfg):
    bundle = bundle_with(registry, "warding_bond")
    cast(registry, cfg, bundle, "warding_bond", circle=2)
    kinds = [e.kind for e in effects_of(bundle, "warding_bond")]
    assert "resist" in kinds and "ac" in kinds


def test_warding_bond_outside_combat_keeps_effect_params(registry, cfg):
    bundle = bundle_with(registry, "warding_bond")
    cast(registry, cfg, bundle, "warding_bond", circle=2)
    found = {e.kind: e.params for e in effects_of(bundle, "warding_bond")}
    assert found["resist"] == {"damage_type": "all"}
    assert found["ac"]["amount"] == 1


COMBAT_ONLY = ["sanctuary", "darkness", "silence", "sleet_storm", "daylight"]


@pytest.mark.parametrize("spell_id", COMBAT_ONLY)
def test_combat_only_spell_outside_combat_is_refused(registry, cfg, spell_id):
    bundle = bundle_with(registry, spell_id)
    _, result = cast(registry, cfg, bundle, spell_id, circle=CIRCLES[spell_id])
    assert isinstance(result, Invalid)
    assert result.code == "combat_only"
    assert "читается только в бою" in result.message
    assert registry.get("spell", spell_id).name in result.message


@pytest.mark.parametrize("spell_id", COMBAT_ONLY)
def test_refused_combat_only_spell_keeps_slot_and_effects(registry, cfg, spell_id):
    bundle = bundle_with(registry, spell_id)
    before = slot(bundle, CIRCLES[spell_id])
    effects = list(bundle.heroes[0].creature.active_effects)
    cast(registry, cfg, bundle, spell_id, circle=CIRCLES[spell_id])
    assert slot(bundle, CIRCLES[spell_id]) == before
    assert bundle.heroes[0].creature.active_effects == effects
