# Трофеи в сейве (docs/CUSTOM-ITEMS-PLAN.md, разд. 6-7): LastCombat.gear / gear_looted и
# CombatState.gear переживают сериализацию бандла без потерь (цена и качество записей).
from protocol_kit import make_bundle

from ai_dm.state.hero import InventoryEntry
from ai_dm.state.save import SaveBundle
from ai_dm.state.session import LastCombat


def gear():
    return [
        InventoryEntry(item_id="scimitar", qty=2, cost_cp=250, quality="junk"),
        InventoryEntry(item_id="custom_1", qty=1, cost_cp=900),
    ]


def reloaded(bundle):
    return SaveBundle.model_validate_json(bundle.model_dump_json())


def test_last_combat_gear_survives_the_round_trip(registry):
    bundle = make_bundle(registry)
    bundle.session.last_combat = LastCombat(defeated=["goblin_warrior"], gear=gear())
    last = reloaded(bundle).session.last_combat
    assert last.gear == gear()
    assert last.gear_looted is False


def test_gear_looted_flag_survives_the_round_trip(registry):
    bundle = make_bundle(registry)
    bundle.session.last_combat = LastCombat(gear=gear(), gear_looted=True)
    assert reloaded(bundle).session.last_combat.gear_looted is True


def test_new_last_combat_starts_with_unlooted_empty_gear():
    last = LastCombat()
    assert (last.gear, last.gear_looted) == ([], False)
