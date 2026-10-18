# К0-фикс-б (K0-FIX-PLAN, шаг 7): сейв со старыми NPC и героем без пола грузится без миграции
# и без предупреждения (пол = не задан); заданный пол переживает сохранение и загрузку.
import json

from persist_kit import load_slot

from ai_dm.persistence.migrations import CURRENT_SCHEMA_VERSION
from ai_dm.persistence.store import save_slot


def strip_gender(folder):
    for path in [folder / "world" / "world.json", *(folder / "heroes").glob("*/hero.json")]:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        targets = list(data["npcs"].values()) if "npcs" in data else [data]
        for target in targets:
            target.pop("gender", None)
            target.pop("pronouns", None)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_schema_version_is_twelve():
    assert CURRENT_SCHEMA_VERSION == 12


def test_slot_without_gender_keys_loads_with_unset_gender(saves, bundle):
    folder = save_slot(saves, bundle, "auto", saved_at=bundle.manifest.saved_at)
    strip_gender(folder)
    loaded = load_slot(saves, "w1", "auto")
    assert all(h.gender is None and h.pronouns == "" for h in loaded.heroes)
    assert all(n.gender is None and n.pronouns == "" for n in loaded.world.npcs.values())


def test_slot_without_gender_keys_keeps_schema_version(saves, bundle):
    folder = save_slot(saves, bundle, "auto", saved_at=bundle.manifest.saved_at)
    strip_gender(folder)
    assert load_slot(saves, "w1", "auto").manifest.schema_version == CURRENT_SCHEMA_VERSION


def test_gender_roundtrips_through_a_slot(saves, bundle):
    bundle.heroes[0].gender = "female"
    bundle.heroes[0].pronouns = "она"
    npc = next(iter(bundle.world.npcs.values()))
    npc.gender = "male"
    npc.pronouns = "он"
    save_slot(saves, bundle, "auto", saved_at=bundle.manifest.saved_at)
    loaded = load_slot(saves, "w1", "auto")
    assert (loaded.heroes[0].gender, loaded.heroes[0].pronouns) == ("female", "она")
    again = loaded.world.npcs[npc.id]
    assert (again.gender, again.pronouns) == ("male", "он")
