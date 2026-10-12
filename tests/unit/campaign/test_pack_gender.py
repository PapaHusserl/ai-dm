# К0-фикс-б (K0-FIX-PLAN, шаг 7, Q10): пол NPC и готовых героев в паках -- загрузка, сборка мира,
# данные трёх паков (именованные NPC и готовые герои с полом).
from pathlib import Path

import pytest
from campaign_kit import SAVED_AT, default_files, load, write_pack

ROOT = Path(__file__).resolve().parents[3]
PACKS = ["drunk_dragon", "dusk_academy", "vale", "test"]


def files_with_gender():
    files = default_files()
    files["npcs.yaml"][0]["gender"] = "female"
    files["npcs.yaml"][0]["pronouns"] = "она, госпожа"
    return files


def test_npc_gender_is_loaded_from_yaml(tmp_path, registry):
    pack = load(write_pack(tmp_path, files_with_gender()), registry)
    aldric = next(n for n in pack.npcs if n.id == "aldric")
    assert (aldric.gender, aldric.pronouns) == ("female", "она, госпожа")


def test_npc_without_gender_in_yaml_is_unset(tmp_path, registry):
    pack = load(write_pack(tmp_path, files_with_gender()), registry)
    guard = next(n for n in pack.npcs if n.id == "guard")
    assert guard.gender is None
    assert guard.pronouns == ""


def test_pack_without_any_gender_still_loads(tmp_path, registry):
    pack = load(write_pack(tmp_path), registry)
    assert all(n.gender is None for n in pack.npcs)


def test_unknown_npc_gender_in_yaml_is_a_pack_error(tmp_path, registry):
    from campaign_kit import pack_errors

    files = default_files()
    files["npcs.yaml"][0]["gender"] = "x"
    errors = pack_errors(write_pack(tmp_path, files), registry)
    assert errors


def test_hero_preset_gender_reaches_the_hero(tmp_path, registry, cfg):
    from ai_dm.game.starter import new_world_from_pack

    files = default_files()
    files["heroes/arn.yaml"]["choices"]["gender"] = "male"
    files["heroes/arn.yaml"]["choices"]["pronouns"] = "он"
    pack = load(write_pack(tmp_path, files), registry)
    bundle = new_world_from_pack(
        registry, cfg, pack, hero="arn", seed=1, world_id="w1", saved_at=SAVED_AT
    )
    assert (bundle.heroes[0].gender, bundle.heroes[0].pronouns) == ("male", "он")


def test_hero_preset_without_gender_gives_unset_hero(tmp_path, registry, cfg):
    from ai_dm.game.starter import new_world_from_pack

    pack = load(write_pack(tmp_path), registry)
    bundle = new_world_from_pack(
        registry, cfg, pack, hero="arn", seed=1, world_id="w1", saved_at=SAVED_AT
    )
    assert bundle.heroes[0].gender is None


def test_npc_gender_reaches_the_world(tmp_path, registry, cfg):
    from ai_dm.game.starter import new_world_from_pack

    pack = load(write_pack(tmp_path, files_with_gender()), registry)
    bundle = new_world_from_pack(
        registry, cfg, pack, hero="arn", seed=1, world_id="w1", saved_at=SAVED_AT
    )
    assert bundle.world.npcs["aldric"].gender == "female"


# данные паков (Q10 (а)): пол всем именованным NPC и готовым героям

def real_pack(name, registry):
    from ai_dm.campaign.loader import load_pack, pack_content_dir
    from ai_dm.content.loader import load_registry

    path = ROOT / "campaigns" / name
    if not path.is_dir():
        pytest.skip(f"нет пака {name}")
    content = pack_content_dir(path)
    return load_pack(path, load_registry([content]) if content else registry)


@pytest.mark.parametrize("name", PACKS)
def test_real_pack_loads(name, registry):
    assert real_pack(name, registry).npcs


@pytest.mark.parametrize("name", PACKS)
def test_every_named_npc_of_real_pack_has_gender(name, registry):
    pack = real_pack(name, registry)
    missing = [n.id for n in pack.npcs if n.named and n.gender is None]
    assert missing == []


@pytest.mark.parametrize("name", PACKS)
def test_every_preset_hero_of_real_pack_has_gender(name, registry):
    pack = real_pack(name, registry)
    missing = [h.id for h in pack.heroes if h.choices.gender is None]
    assert missing == []


def test_dusk_academy_npcs_all_have_gender(registry):
    pack = real_pack("dusk_academy", registry)
    assert [n.id for n in pack.npcs if n.gender is None] == []
