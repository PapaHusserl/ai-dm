# Ж1 (docs/plan-zh1.md, п. 0.7, коммит 2): выжившие боя в состоянии промпта рассказчика.
#   survivor_data(npc) -> {} у NPC не движка; у origin="engine": kind (monster_id из NPC.combat),
#     unnamed -- если named=False (имени ещё нет, надо дать его npc_update), name_hidden -- если
#     known_name не задан (игрок имени не слышал: звать по виду). Рассказчик настоящее имя видит.
#   state_data: те же ключи в scene_npcs и known_npcs; у прочих NPC их нет.
#   narrator_rules.md: раздел о выживших (npc_update name, unnamed, name_hidden).
import json
from importlib import resources

import pytest
from master_kit import app_cfg, make_ctx

from ai_dm.master.prompt import PromptBuilder, survivor_data
from ai_dm.state.world import NPC

SID = "goblin_warrior_t1_1"


def engine_npc(**fields):
    data = {
        "id": SID, "name": "Воин-гоблин 1", "named": False, "means": ["бой"], "origin": "engine",
        "location_id": "vale", "combat": {"monster_id": "goblin_warrior", "label": "Воин-гоблин 1"},
    }
    return NPC(**{**data, **fields})


def state(ctx, mode="explore"):
    request = PromptBuilder(app_cfg()).build(ctx, "Осматриваюсь.", mode)
    return json.loads(request.messages[0].content[0].text)


def by_id(items):
    return {item["id"]: item for item in items}


def rules_text():
    return (resources.files("ai_dm.master") / "prompts" / "narrator_rules.md").read_text(
        encoding="utf-8"
    )


# survivor_data

def test_survivor_data_of_pack_npc_is_empty():
    assert survivor_data(NPC(id="a", name="Олдрик", means=["x"])) == {}


def test_survivor_data_of_ai_npc_is_empty():
    assert survivor_data(NPC(id="a", name="Олдрик", means=["x"], origin="ai")) == {}


def test_survivor_data_unnamed_hidden():
    assert survivor_data(engine_npc()) == {
        "kind": "goblin_warrior", "unnamed": True, "name_hidden": True,
    }


def test_survivor_data_named_but_hidden():
    assert survivor_data(engine_npc(named=True, name="Мурк")) == {
        "kind": "goblin_warrior", "name_hidden": True,
    }


def test_survivor_data_named_and_opened_has_only_kind():
    data = survivor_data(engine_npc(named=True, name="Мурк", known_name="Мурк"))
    assert data == {"kind": "goblin_warrior"}


def test_survivor_data_without_combat_has_none_kind():
    assert survivor_data(engine_npc(combat=None))["kind"] is None


# scene_npcs

@pytest.fixture
def ctx(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.npcs[SID] = engine_npc()
    return ctx


def test_scene_survivor_has_kind_and_flags(ctx):
    item = by_id(state(ctx)["scene_npcs"])[SID]
    assert (item["kind"], item["unnamed"], item["name_hidden"]) == ("goblin_warrior", True, True)


def test_scene_survivor_named_shows_real_name_to_narrator(ctx):
    npc = ctx.bundle.world.npcs[SID]
    npc.name, npc.named = "Мурк", True
    item = by_id(state(ctx)["scene_npcs"])[SID]
    assert item["name"] == "Мурк"
    assert "unnamed" not in item
    assert item["name_hidden"] is True


def test_scene_survivor_opened_has_no_flags(ctx):
    npc = ctx.bundle.world.npcs[SID]
    npc.name, npc.named, npc.known_name = "Мурк", True, "Мурк"
    item = by_id(state(ctx)["scene_npcs"])[SID]
    assert "unnamed" not in item
    assert "name_hidden" not in item


def test_scene_pack_npc_has_no_survivor_keys(ctx):
    item = by_id(state(ctx)["scene_npcs"])["grakh"]
    assert not {"kind", "unnamed", "name_hidden"} & set(item)


# known_npcs

def test_known_survivor_has_kind_and_hidden_flag(ctx):
    # в known_npcs попадают только именованные NPC (relevance.npc_reasons): после назначения имени
    npc = ctx.bundle.world.npcs[SID]
    npc.name, npc.named = "Мурк", True
    item = by_id(state(ctx)["known_npcs"])[SID]
    assert item["kind"] == "goblin_warrior"
    assert item["name_hidden"] is True
    assert "unnamed" not in item


def test_known_survivor_with_opened_name_has_only_kind(ctx):
    npc = ctx.bundle.world.npcs[SID]
    npc.name, npc.named, npc.known_name = "Мурк", True, "Мурк"
    item = by_id(state(ctx)["known_npcs"])[SID]
    assert item["kind"] == "goblin_warrior"
    assert "name_hidden" not in item


def test_known_pack_npc_has_no_survivor_keys(ctx):
    item = by_id(state(ctx)["known_npcs"])["grakh"]
    assert not {"kind", "unnamed", "name_hidden"} & set(item)


# правила рассказчика

def test_rules_describe_survivor_flags_and_name_request():
    text = rules_text()
    for word in ("unnamed", "name_hidden", "npc_update", "`name`"):
        assert word in text


def test_rules_say_to_use_kind_until_name_is_spoken():
    text = rules_text()
    assert "по виду" in text
    assert "один раз" in text
