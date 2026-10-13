# game.app.merge_pack(bundle, registry, campaigns_dir) -> list[str] (этап 3, партия 1, ревью R4):
# строки для игрока о догрузке пака; GameApp.load вызывает её после загрузки слота
# (GameApp(..., campaigns_dir=...)).
import sys
from pathlib import Path

from game_kit import SAVED_AT, make_app, scripted, settings
from protocol_kit import make_bundle

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "campaign"))
from campaign_kit import (  # noqa: E402
    bundle_from_world,
    default_files,
    load,
    world_from_pack,
    write_pack,
)

from ai_dm.game.app import merge_pack  # noqa: E402
from ai_dm.persistence.store import save_auto  # noqa: E402

NEW_NPC = {"id": "brana", "name": "Бранка", "named": True, "means": ["топор"]}


def mini_bundle(tmp_path, registry):
    root = tmp_path / "packs"
    pack = load(write_pack(root), registry)
    return bundle_from_world(world_from_pack(pack)), root


def test_world_without_campaign_gives_no_lines(tmp_path, registry):
    bundle, root = mini_bundle(tmp_path, registry)
    bundle.world.campaign_id = None
    assert merge_pack(bundle, registry, root) == []


def test_missing_pack_dir_gives_warning_and_world_is_untouched(tmp_path, registry):
    bundle, _ = mini_bundle(tmp_path, registry)
    before = bundle.model_dump()
    lines = merge_pack(bundle, registry, tmp_path / "no_packs")
    assert len(lines) == 1
    assert "mini" in lines[0]
    assert bundle.model_dump() == before


def test_broken_pack_gives_warning_with_error_lines(tmp_path, registry):
    bundle, root = mini_bundle(tmp_path, registry)
    files = default_files()
    files["locations.yaml"][2]["parent_id"] = "nowhere"
    write_pack(root, files)
    before = bundle.model_dump()
    lines = merge_pack(bundle, registry, root)
    assert "не догружен" in lines[0]
    assert "nowhere" in "\n".join(lines)
    assert bundle.model_dump() == before


def test_nothing_new_gives_no_lines(tmp_path, registry):
    bundle, root = mini_bundle(tmp_path, registry)
    assert merge_pack(bundle, registry, root) == []


def test_added_entity_is_reported_and_added(tmp_path, registry):
    bundle, root = mini_bundle(tmp_path, registry)
    files = default_files()
    files["npcs.yaml"].append(NEW_NPC)
    write_pack(root, files)
    lines = merge_pack(bundle, registry, root)
    assert "Из пака добавлено" in "\n".join(lines)
    assert "brana" in "\n".join(lines)
    assert "brana" in bundle.world.npcs


def test_conflicts_are_reported_and_entity_is_not_added(tmp_path, registry):
    bundle, root = mini_bundle(tmp_path, registry)
    files = default_files()
    files["npcs.yaml"].append({"id": "twin", "name": "Олдрик", "named": True, "means": ["меч"]})
    write_pack(root, files)
    text = "\n".join(merge_pack(bundle, registry, root))
    assert "конфликты" in text
    assert "twin" in text
    assert "twin" not in bundle.world.npcs


def test_second_call_gives_no_lines(tmp_path, registry):
    bundle, root = mini_bundle(tmp_path, registry)
    files = default_files()
    files["npcs.yaml"].append(NEW_NPC)
    write_pack(root, files)
    merge_pack(bundle, registry, root)
    assert merge_pack(bundle, registry, root) == []


def test_load_slot_merges_pack_and_prints_lines(tmp_path, registry):
    bundle = make_bundle(registry)
    pack = load(write_pack(tmp_path / "packs"), registry)
    bundle.world.campaign_id = "mini"
    bundle.world.campaign_version = pack.manifest.version
    save_auto(tmp_path, bundle, saved_at=SAVED_AT, cfg=settings().rules)
    files = default_files()
    files["npcs.yaml"].append(NEW_NPC)
    write_pack(tmp_path / "packs", files)
    app = make_app(registry, tmp_path, scripted([]), bundle=bundle)
    app.campaigns_dir = tmp_path / "packs"
    lines = app.load("auto")
    assert "Загружено: auto." in lines
    assert "brana" in "\n".join(lines)
    assert "brana" in app.bundle.world.npcs


def test_load_slot_without_pack_dir_still_loads(tmp_path, registry):
    bundle = make_bundle(registry)
    bundle.world.campaign_id = "mini"
    save_auto(tmp_path, bundle, saved_at=SAVED_AT, cfg=settings().rules)
    app = make_app(registry, tmp_path, scripted([]), bundle=bundle)
    app.campaigns_dir = tmp_path / "no_packs"
    lines = app.load("auto")
    assert lines[0] == "Загружено: auto."
    assert "mini" in "\n".join(lines[1:])


def gender_files():
    files = default_files()
    files["npcs.yaml"][0]["gender"] = "female"
    files["npcs.yaml"][0]["pronouns"] = "она"
    return files


def test_gender_fill_is_reported_to_player(tmp_path, registry):
    bundle, root = mini_bundle(tmp_path, registry)
    write_pack(root, gender_files())
    text = "\n".join(merge_pack(bundle, registry, root))
    assert "Из пака добавлено" in text
    assert "gender:aldric" in text
    assert bundle.world.npcs["aldric"].gender == "female"


def test_gender_fill_is_reported_once(tmp_path, registry):
    bundle, root = mini_bundle(tmp_path, registry)
    write_pack(root, gender_files())
    merge_pack(bundle, registry, root)
    assert merge_pack(bundle, registry, root) == []


def test_no_gender_in_pack_gives_no_gender_line(tmp_path, registry):
    bundle, root = mini_bundle(tmp_path, registry)
    assert "gender:" not in "\n".join(merge_pack(bundle, registry, root))


def test_load_slot_fills_gender_of_pack_npc(tmp_path, registry):
    bundle = make_bundle(registry)
    pack = load(write_pack(tmp_path / "packs"), registry)
    bundle.world.campaign_id = "mini"
    bundle.world.campaign_version = pack.manifest.version
    bundle.world.npcs["aldric"].origin = "pack"
    save_auto(tmp_path, bundle, saved_at=SAVED_AT, cfg=settings().rules)
    write_pack(tmp_path / "packs", gender_files())
    app = make_app(registry, tmp_path, scripted([]), bundle=bundle)
    app.campaigns_dir = tmp_path / "packs"
    lines = app.load("auto")
    assert "gender:aldric" in "\n".join(lines)
    assert app.bundle.world.npcs["aldric"].gender == "female"
    assert app.bundle.world.npcs["aldric"].pronouns == "она"
