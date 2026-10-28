# Миграция сейва v5 -> v6 при запуске (CUSTOM-ITEMS-PLAN, разд. 8; ревью партии 0, п. 1, 3):
#   --world <мир> грузит слот через реестр пака (цены), неизвестный id предмета получает цену 0 и
#   попадает в видимое предупреждение (в выводе есть id); незавершённая запись слота
#   (manifest лежит в .old-*) не мешает продолжить игру.
import shutil
from pathlib import Path

from ui_kit import cli, write_script

FIXTURE_V5 = Path(__file__).resolve().parents[2] / "fixtures" / "saves" / "v5"


def run(tmp_path, slots_name):
    root = tmp_path / "saves"
    shutil.copytree(FIXTURE_V5, root / "old_world" / "slots" / slots_name)
    argv = ["--world", "old_world", "--mock", str(write_script(tmp_path / "s.yaml")),
            "--saves", str(root)]
    return cli(argv, ["/inv"], env={})


def test_continue_of_v5_world_warns_about_unknown_item(tmp_path):
    code, out = run(tmp_path, "auto")
    assert code == 0
    assert "ghost_relic" in out.text


def test_continue_of_v5_world_shows_the_inventory(tmp_path):
    _, out = run(tmp_path, "auto")
    assert "Скимитар" in out.text


def test_continue_with_an_interrupted_write_still_loads(tmp_path):
    code, out = run(tmp_path, ".old-abc")
    assert code == 0
    assert "Скимитар" in out.text


# BACKLOG 30 (Б3): сейв v2 без campaign_id с world_id «vale-*»: m0003 (v2 -> v3) ставит campaign_id
# vale при миграции -- ветка cli: campaign_registry(peeked=None) -> загрузка слота -> реестр пака
# по campaign_id мира; пак campaign_id без каталога -- pack_npc_trade -> None (предупреждение
# миграции). Фикстуры v3 и новее campaign_id не получают: m0003 для них не запускается.

import json  # noqa: E402

from ai_dm.persistence.store import load_slot, peek_campaign_id  # noqa: E402

CAMPAIGNS = Path(__file__).resolve().parents[3] / "campaigns"
FIXTURE_V2 = FIXTURE_V5.parent / "v2"


def make_world(tmp_path, world_id, campaign_id=None, fixture=FIXTURE_V5):
    # копия фикстуры под другим world_id (и campaign_id, если задан) в slots/auto
    root = tmp_path / "saves"
    slot = root / world_id / "slots" / "auto"
    shutil.copytree(fixture, slot)
    for name in ("manifest.json", "world/world.json"):
        path = slot / name
        data = json.loads(path.read_text(encoding="utf-8"))
        data["world_id"] = world_id
        data["campaign_id"] = campaign_id
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return root


def run_world(tmp_path, root, world_id, campaigns_dir, lines=("/quit",)):
    argv = ["--world", world_id, "--mock", str(write_script(tmp_path / "s.yaml")),
            "--saves", str(root)]
    return cli(argv, list(lines), env={}, campaigns_dir=campaigns_dir)


def test_vale_prefixed_world_without_campaign_id_has_none_peeked_campaign(tmp_path):
    root = make_world(tmp_path, "vale-old", fixture=FIXTURE_V2)
    assert peek_campaign_id(root, "vale-old", "auto") is None


def test_vale_prefixed_old_world_gets_vale_campaign_after_migration(tmp_path):
    root = make_world(tmp_path, "vale-old", fixture=FIXTURE_V2)
    code, _ = run_world(tmp_path, root, "vale-old", CAMPAIGNS, lines=["Осматриваюсь", "/quit"])
    assert code == 0
    assert load_slot(root, "vale-old", "auto").world.campaign_id == "vale"


def test_vale_prefixed_old_world_finds_the_vale_pack(tmp_path):
    root = make_world(tmp_path, "vale-old", fixture=FIXTURE_V2)
    code, out = run_world(tmp_path, root, "vale-old", CAMPAIGNS)
    assert code == 0
    assert "Пака vale нет" not in out.text
    assert "не догружен" not in out.text
    assert "Предупреждение: миграция сейва" not in out.text


def test_vale_prefixed_old_world_with_empty_campaigns_dir_merges_the_shipped_pack(tmp_path):
    root = make_world(tmp_path, "vale-old", fixture=FIXTURE_V2)
    empty = tmp_path / "no_packs"
    empty.mkdir()
    code, out = run_world(tmp_path, root, "vale-old", empty)
    assert code == 0
    assert "Из пака добавлено" in out.text
    assert "Пака vale нет" not in out.text


def test_old_world_without_vale_prefix_stays_without_campaign(tmp_path):
    root = make_world(tmp_path, "old_world")
    code, out = run_world(tmp_path, root, "old_world", CAMPAIGNS, lines=["Осматриваюсь", "/quit"])
    assert code == 0
    assert load_slot(root, "old_world", "auto").world.campaign_id is None
    assert "Пака" not in out.text


def test_world_with_missing_pack_dir_warns_and_plays_without_merge(tmp_path):
    root = make_world(tmp_path, "ghost-world", campaign_id="ghost")
    empty = tmp_path / "no_packs"
    empty.mkdir()
    code, out = run_world(tmp_path, root, "ghost-world", empty)
    assert code == 0
    assert "Предупреждение: миграция сейва" in out.text
    squashed = "".join(out.text.split())
    assert f"Пакаghostнетнив{empty},нивпоставке" in squashed
    assert "бездогрузки" in squashed


def test_world_with_missing_pack_dir_keeps_its_campaign_id(tmp_path):
    root = make_world(tmp_path, "ghost-world", campaign_id="ghost")
    empty = tmp_path / "no_packs"
    empty.mkdir()
    run_world(tmp_path, root, "ghost-world", empty, lines=["Осматриваюсь", "/quit"])
    assert load_slot(root, "ghost-world", "auto").world.campaign_id == "ghost"


def test_campaign_registry_without_campaign_has_no_pack_dir_and_base_content():
    from ai_dm.content.loader import load_registry
    from ai_dm.ui.cli import campaign_registry

    pack_dir, registry = campaign_registry(None, CAMPAIGNS)
    assert pack_dir is None
    assert registry.ids("item") == load_registry([]).ids("item")


def test_campaign_registry_returns_pack_dir_and_pack_content():
    from ai_dm.content.loader import load_registry
    from ai_dm.ui.cli import campaign_registry

    pack_dir, registry = campaign_registry("drunk_dragon", CAMPAIGNS)
    assert pack_dir == CAMPAIGNS / "drunk_dragon"
    base = load_registry([])
    extra = [
        kind for kind in ("item", "monster", "weapon", "armor", "spell")
        if len(registry.ids(kind)) > len(base.ids(kind))
    ]
    assert extra


def test_campaign_registry_of_pack_without_content_dir_is_base_content(tmp_path):
    from ai_dm.content.loader import load_registry
    from ai_dm.ui.cli import campaign_registry

    (tmp_path / "plain").mkdir()
    pack_dir, registry = campaign_registry("plain", tmp_path)
    assert pack_dir == tmp_path / "plain"
    assert registry.ids("item") == load_registry([]).ids("item")


def test_campaign_registry_of_missing_pack_points_into_the_shipped_dir(tmp_path):
    from ai_dm.campaign.loader import SHIPPED_DIR
    from ai_dm.ui.cli import campaign_registry

    pack_dir, _ = campaign_registry("ghost", tmp_path)
    assert pack_dir == SHIPPED_DIR / "ghost"


def test_campaign_registry_prefers_the_local_pack_over_the_shipped_one(tmp_path):
    from ai_dm.ui.cli import campaign_registry

    (tmp_path / "vale").mkdir()
    pack_dir, _ = campaign_registry("vale", tmp_path)
    assert pack_dir == tmp_path / "vale"


# ТБ #56 (docs/plan-tb.md п.2): campaign_registry ставит monster_scope пака

def test_campaign_registry_sets_scope_of_pack_with_monsters_list():
    from ai_dm.campaign.loader import pack_monster_scope
    from ai_dm.ui.cli import campaign_registry

    _, registry = campaign_registry("dusk_academy", CAMPAIGNS)
    scope = pack_monster_scope(CAMPAIGNS / "dusk_academy")
    assert registry.narrator_monster_ids() == sorted(scope)


def test_campaign_registry_keeps_full_monster_ids_with_scope():
    from ai_dm.content.loader import load_registry
    from ai_dm.ui.cli import campaign_registry

    _, registry = campaign_registry("dusk_academy", CAMPAIGNS)
    assert registry.ids("monster") == load_registry([]).ids("monster")


def test_campaign_registry_of_pack_without_list_shows_all_monsters():
    from ai_dm.ui.cli import campaign_registry

    _, registry = campaign_registry("vale", CAMPAIGNS)
    assert registry.narrator_monster_ids() == registry.ids("monster")


def test_campaign_registry_without_campaign_shows_all_monsters():
    from ai_dm.ui.cli import campaign_registry

    _, registry = campaign_registry(None, CAMPAIGNS)
    assert registry.narrator_monster_ids() == registry.ids("monster")


def test_campaign_registry_of_missing_pack_shows_all_monsters(tmp_path):
    from ai_dm.ui.cli import campaign_registry

    _, registry = campaign_registry("ghost", tmp_path)
    assert registry.narrator_monster_ids() == registry.ids("monster")
