# Контекст мастера: записи инвентаря несут цену экземпляра (docs/plan-custom-items.md, разд. 8).
#   hero.inventory[*] = {"item_id", "qty", "cost_cp"[, "quality" -- если есть]}; по записи на стек
#   (два стека одного id -- две записи, у каждой своя цена).
import json

from master_kit import app_cfg, make_ctx

from ai_dm.master.prompt import PromptBuilder
from ai_dm.rules.inventory import add_item


def inventory_of(ctx):
    request = PromptBuilder(app_cfg()).build(ctx, "Осматриваюсь.", "explore")
    return json.loads(request.messages[0].content[0].text)["hero"]["inventory"]


def test_inventory_entry_has_cost_and_quality(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_item(ctx.hero, "scimitar", cost_cp=150, quality="worn")
    entry = [e for e in inventory_of(ctx) if e["item_id"] == "scimitar"][0]
    assert entry["qty"] == 1
    assert entry["cost_cp"] == 150
    assert entry["quality"] == "worn"


def test_inventory_entry_without_quality_has_none(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_item(ctx.hero, "scimitar", cost_cp=2500)
    entry = [e for e in inventory_of(ctx) if e["item_id"] == "scimitar"][0]
    assert entry.get("quality") is None


def test_two_stacks_of_one_id_are_two_entries(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_item(ctx.hero, "scimitar", 2, cost_cp=150, quality="worn")
    add_item(ctx.hero, "scimitar", cost_cp=2500)
    entries = [e for e in inventory_of(ctx) if e["item_id"] == "scimitar"]
    assert sorted((e["cost_cp"], e["qty"]) for e in entries) == [(150, 2), (2500, 1)]
