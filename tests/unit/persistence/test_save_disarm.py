# Партия «Отбор оружия» (docs/plan-combat-disarm.md, «Миграции сейва»): версия схемы остаётся 5.
# Новые поля с умолчаниями: CombatState.ground_items = [], TurnState.free_interaction = True;
# флаг "disarmed" лежит в свободном ActiveEffect.params. Бой, сохранённый без новых полей,
# грузится как раньше; с ними -- без потерь.
import shutil
from pathlib import Path

from persist_kit import load_slot

from ai_dm.persistence.migrations import CURRENT_SCHEMA_VERSION
from ai_dm.persistence.store import save_slot
from ai_dm.state.combat import CombatState, GroundItem, TurnState
from ai_dm.state.creature import ActiveEffect

FIXTURE_V4_DRAGON = Path(__file__).resolve().parents[2] / "fixtures" / "saves" / "v4_dragon"
SAVED_AT = "2026-01-01T12:00:00Z"

OLD_COMBAT = {
    "id": "fight_1",
    "zones": [{"id": "hall", "name": "Зал", "adjacent": []}],
    "participants": [
        {"ref": "h1", "side": "heroes", "group_id": "party", "zone_id": "hall",
         "turn": {"action": True, "bonus": True, "reaction": True, "move": 1}},
        {"ref": "g1", "side": "enemies", "group_id": "goblins", "zone_id": "hall",
         "monster_id": "goblin_warrior", "name": "Воин-гоблин",
         "creature": {"hp_current": 10, "hp_max": 10, "active_effects": [
             {"id": "disarmed", "source": "h1", "kind": "flag"}]}},
    ],
    "groups": {"party": {"leader_id": "h1"}, "goblins": {"leader_id": "g1", "intent": "kill"}},
}


def test_schema_version_is_current_twelve():
    assert CURRENT_SCHEMA_VERSION == 12


def test_old_combat_without_new_fields_loads():
    combat = CombatState.model_validate(OLD_COMBAT)
    assert combat.ground_items == []
    assert combat.participants[0].turn.free_interaction is True


def test_old_disarmed_flag_without_params_loads():
    combat = CombatState.model_validate(OLD_COMBAT)
    flag = combat.participants[1].creature.active_effects[0]
    assert (flag.id, flag.params) == ("disarmed", {})


def test_turn_state_without_the_new_field_is_free():
    assert TurnState.model_validate({"action": False}).free_interaction is True


def test_ground_item_defaults():
    item = GroundItem(item_id="scimitar", zone_id="hall", cost_cp=0)
    assert (item.owner_ref, item.qty) == (None, 1)


def test_v4_save_loads_without_ground_items(saves):
    shutil.copytree(FIXTURE_V4_DRAGON, saves / "dd" / "slots" / "auto")
    first = load_slot(saves, "dd", "auto", backup_ts="20260101T000000Z")
    assert first.session.active_combat is None
    assert first.manifest.schema_version == CURRENT_SCHEMA_VERSION


def test_combat_with_ground_items_survives_a_save_load_cycle(saves, bundle):
    combat = CombatState.model_validate(OLD_COMBAT)
    combat.ground_items.append(
        GroundItem(item_id="scimitar", zone_id="hall", owner_ref="g1", cost_cp=0)
    )
    combat.participants[1].creature.active_effects = [
        ActiveEffect(id="disarmed", source="h1", kind="flag", params={"weapon_id": "scimitar"})
    ]
    combat.participants[0].turn.free_interaction = False
    bundle.session.active_combat = combat
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    loaded = load_slot(saves, "w1", "auto")
    assert loaded.session.active_combat == combat
    assert loaded.session.active_combat.ground_items[0].owner_ref == "g1"
    assert loaded.session.active_combat.participants[0].turn.free_interaction is False


def test_old_combat_in_a_v5_save_loads_with_defaults(saves, bundle):
    bundle.session.active_combat = CombatState.model_validate(OLD_COMBAT)
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    loaded = load_slot(saves, "w1", "auto")
    assert loaded.session.active_combat.ground_items == []
