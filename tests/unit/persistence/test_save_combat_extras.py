# Партия «Боевые дополнения» (docs/COMBAT-EXTRAS-PLAN.md, «Миграции сейва»): схема не меняется.
# Заряд/опутывание лежат в свободных полях ActiveEffect.kind/params
# и AppliedCondition.expires, поэтому сейв v5 без них грузится как раньше, а с ними -- без потерь.
import shutil
from pathlib import Path

from persist_kit import load_slot

from ai_dm.persistence.migrations import CURRENT_SCHEMA_VERSION
from ai_dm.persistence.store import save_slot
from ai_dm.state.creature import ActiveEffect, AppliedCondition, Concentration, Expiry

FIXTURE_V4_DRAGON = Path(__file__).resolve().parents[2] / "fixtures" / "saves" / "v4_dragon"
SAVED_AT = "2026-01-01T12:00:00Z"
HELD = Expiry(kind="concentration", owner="h1")


def test_schema_version_is_current_ten():
    assert CURRENT_SCHEMA_VERSION == 10


def test_v5_save_without_a_charge_loads_with_clean_hero_effects(saves):
    shutil.copytree(FIXTURE_V4_DRAGON, saves / "dd" / "slots" / "auto")
    first = load_slot(saves, "dd", "auto", backup_ts="20260101T000000Z")
    save_slot(saves, first, "manual-v5", saved_at=SAVED_AT)
    loaded = load_slot(saves, "dd", "manual-v5")
    assert loaded.heroes == first.heroes
    assert loaded.manifest.schema_version == CURRENT_SCHEMA_VERSION
    for hero in loaded.heroes:
        kinds = [e.kind for e in hero.creature.active_effects]
        assert "weapon_rider" not in kinds
        assert "ensnared" not in kinds


def test_charge_and_ensnared_target_survive_a_save_load_cycle(saves, bundle):
    hero = bundle.heroes[0]
    hero.creature.concentration = Concentration(spell_id="ensnaring_strike", circle=1)
    hero.creature.active_effects.append(
        ActiveEffect(
            id="ensnaring_strike", source="h1", kind="weapon_rider",
            params={"dice": "2d6", "damage_type": "piercing", "condition": "restrained",
                    "ability": "str", "dc": 13, "circle": 2},
            expires=HELD,
        )
    )
    victim = bundle.heroes[1].creature
    victim.conditions.append(AppliedCondition(id="restrained", source="h1", expires=HELD))
    victim.active_effects.append(
        ActiveEffect(
            id="ensnared", source="h1", kind="ensnared",
            params={"dice": "2d6", "damage_type": "piercing", "dc": 13}, expires=HELD,
        )
    )
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    loaded = load_slot(saves, "w1", "auto")
    assert loaded == bundle
    assert loaded.heroes[1].creature.conditions[0].expires == HELD
