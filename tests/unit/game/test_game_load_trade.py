# Торговля, партия Т0: GameApp.load старого (v6) слота подставляет в миграцию торговцев пака
# кампании мира (campaign_id мира -> campaigns_dir/<id>/npcs.yaml, поле trade).
import shutil
import sys
from pathlib import Path

from game_kit import make_app, scripted

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "campaign"))
from campaign_kit import default_files, write_pack  # noqa: E402

FIXTURE_V6 = Path(__file__).resolve().parents[2] / "fixtures" / "saves" / "v6"


def app_with_v6_slot(registry, tmp_path, trade):
    files = default_files()
    files["npcs.yaml"].append({
        "id": "innkeeper", "name": "Трактирщик", "named": True, "location_id": "town",
        "means": ["пиво"], **({"trade": trade} if trade is not None else {}),
    })
    root = tmp_path / "packs"
    write_pack(root, files)
    app = make_app(registry, tmp_path / "saves", scripted([]))
    app.campaigns_dir = root
    app.bundle.world.campaign_id = "mini"
    app.world_id = "old_world"
    shutil.copytree(FIXTURE_V6, tmp_path / "saves" / "old_world" / "slots" / "auto")
    return app


def test_load_v6_slot_gives_pack_merchant_a_profile(registry, tmp_path):
    app = app_with_v6_slot(registry, tmp_path, {"kind": "general"})
    lines = app.load("auto")
    assert lines[0] == "Загружено: auto.", lines
    assert app.bundle.world.npcs["innkeeper"].trade.kind == "general"


def test_load_v6_slot_keeps_other_npc_without_trade(registry, tmp_path):
    app = app_with_v6_slot(registry, tmp_path, {"kind": "general"})
    lines = app.load("auto")
    assert lines[0] == "Загружено: auto.", lines
    assert app.bundle.world.npcs["grakh"].trade is None


def test_load_v6_slot_with_pack_without_trade_gives_no_profile(registry, tmp_path):
    app = app_with_v6_slot(registry, tmp_path, None)
    lines = app.load("auto")
    assert lines[0] == "Загружено: auto.", lines
    assert app.bundle.world.npcs["innkeeper"].trade is None


def test_load_v6_slot_without_campaign_gives_no_profile(registry, tmp_path):
    app = app_with_v6_slot(registry, tmp_path, {"kind": "general"})
    app.bundle.world.campaign_id = None
    lines = app.load("auto")
    assert lines[0] == "Загружено: auto.", lines
    assert app.bundle.world.npcs["innkeeper"].trade is None


def test_load_v6_slot_with_missing_pack_warns_and_gives_no_profile(registry, tmp_path):
    app = app_with_v6_slot(registry, tmp_path, {"kind": "general"})
    app.campaigns_dir = tmp_path / "no_packs"
    lines = app.load("auto")
    assert "торговцы пака не проставлены" in "\n".join(lines)
    assert app.bundle.world.npcs["innkeeper"].trade is None
