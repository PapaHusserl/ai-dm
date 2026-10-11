# Торговля, партия Т2 (TRADE-PLAN, разд. 4, В-Т6): take_item.holder_npc_id -- сюжетный предмет
# отдан NPC. Поле необязательное (пусто = нет, внутри None). Для сюжетного предмета герой теряет
# qty штук, держателем становится NPC: ItemHolder(kind="npc", ref=id, label=имя NPC,
# location_id=локация NPC, since_s=время мира, qty=отдано, cost_cp=цена стека героя).
# Неизвестный NPC -> Invalid unknown_npc; NPC не alive или не в локации героя -> Invalid npc_absent.
# Сюжетный предмет без holder_npc_id -> Invalid (держатель обязателен); обычный -- как раньше.
from protocol_kit import dump, make_ctx, req

from ai_dm.master.prompt import lost_items_data
from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.rules.inventory import count_item
from ai_dm.state.world import NPC


def give(ctx, qty=1, cost_cp=700, quest=True):
    return apply(
        ctx, req(
            "give_custom_item", name="Ржавый ключ", description="", qty=qty, weight_lb=0,
            cost_cp=cost_cp, quest=quest,
        )
    )


def take(ctx, qty=1, why="given", **fields):
    return apply(ctx, req("take_item", item_id="custom_1", qty=qty, why=why, **fields))


def holder_ctx(registry, cfg, qty=1, cost_cp=700):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.npcs["mara"] = NPC(
        id="mara", name="Мара", means=["товары"], location_id="vale"
    )
    give(ctx, qty=qty, cost_cp=cost_cp)
    return ctx


def npc(ctx):
    return ctx.bundle.world.npcs["mara"]


def holder(ctx):
    return ctx.bundle.world.custom_items["custom_1"].holder


def test_request_without_holder_npc_id_has_none(registry, cfg):
    request = req("take_item", item_id="custom_1", qty=1, why="given")
    assert request.holder_npc_id is None


def test_request_with_holder_npc_id_keeps_it(registry, cfg):
    request = req("take_item", item_id="custom_1", qty=1, why="given", holder_npc_id="mara")
    assert request.holder_npc_id == "mara"


def test_given_to_npc_makes_the_npc_the_holder(registry, cfg):
    ctx = holder_ctx(registry, cfg)
    d = take(ctx, holder_npc_id="mara")
    assert isinstance(d, Decision)
    assert d.status == "accepted"
    held = holder(ctx)
    assert held.kind == "npc"
    assert held.ref == "mara"
    assert held.label == "Мара"
    assert held.location_id == "vale"
    assert held.qty == 1
    assert held.cost_cp == 700


def test_given_to_npc_takes_the_item_from_the_hero(registry, cfg):
    ctx = holder_ctx(registry, cfg)
    take(ctx, holder_npc_id="mara")
    assert count_item(ctx.hero, "custom_1") == 0


def test_holder_remembers_the_world_time(registry, cfg):
    ctx = holder_ctx(registry, cfg)
    ctx.bundle.world.clock.advance(5400)
    take(ctx, holder_npc_id="mara")
    assert holder(ctx).since_s == 5400


def test_holder_gets_the_taken_qty_only(registry, cfg):
    ctx = holder_ctx(registry, cfg, qty=3)
    take(ctx, qty=2, holder_npc_id="mara")
    assert holder(ctx).qty == 2
    assert count_item(ctx.hero, "custom_1") == 1


def test_holder_qty_is_clamped_to_what_the_hero_has(registry, cfg):
    ctx = holder_ctx(registry, cfg, qty=2)
    d = take(ctx, qty=5, holder_npc_id="mara")
    assert d.status == "clamped"
    assert holder(ctx).qty == 2


def test_given_item_shows_in_lost_items_with_the_npc(registry, cfg):
    ctx = holder_ctx(registry, cfg)
    take(ctx, holder_npc_id="mara")
    lost = lost_items_data(ctx.bundle.world)
    assert [(i["item_id"], i["holder"]["label"]) for i in lost] == [("custom_1", "Мара")]


def test_unknown_holder_npc_is_invalid_and_changes_nothing(registry, cfg):
    ctx = holder_ctx(registry, cfg)
    before = dump(ctx)
    d = take(ctx, holder_npc_id="nobody")
    assert isinstance(d, Invalid)
    assert d.code == "unknown_npc"
    assert dump(ctx) == before


def test_custom_item_without_holder_npc_id_is_invalid_and_changes_nothing(registry, cfg):
    ctx = holder_ctx(registry, cfg)
    before = dump(ctx)
    d = take(ctx)
    assert isinstance(d, Invalid)
    assert dump(ctx) == before


def test_custom_item_without_holder_is_invalid_for_any_reason(registry, cfg):
    ctx = holder_ctx(registry, cfg)
    for why in ("given", "lost", "stolen", "spent"):
        assert isinstance(take(ctx, why=why), Invalid)
    assert count_item(ctx.hero, "custom_1") == 1


def test_holder_npc_in_another_location_is_absent(registry, cfg):
    ctx = holder_ctx(registry, cfg)
    npc(ctx).location_id = "forest"
    before = dump(ctx)
    d = take(ctx, holder_npc_id="mara")
    assert isinstance(d, Invalid)
    assert d.code == "npc_absent"
    assert dump(ctx) == before


def test_holder_npc_without_location_is_absent(registry, cfg):
    ctx = holder_ctx(registry, cfg)
    npc(ctx).location_id = None
    d = take(ctx, holder_npc_id="mara")
    assert isinstance(d, Invalid)
    assert d.code == "npc_absent"


def test_dead_holder_npc_is_absent(registry, cfg):
    ctx = holder_ctx(registry, cfg)
    npc(ctx).status = "dead"
    before = dump(ctx)
    d = take(ctx, holder_npc_id="mara")
    assert isinstance(d, Invalid)
    assert d.code == "npc_absent"
    assert dump(ctx) == before


def test_holder_npc_id_with_a_plain_srd_item_does_not_touch_the_catalog(registry, cfg):
    ctx = holder_ctx(registry, cfg)
    d = apply(
        ctx, req("take_item", item_id="healers_kit", qty=1, why="given", holder_npc_id="mara")
    )
    assert d.status == "accepted"
    assert ctx.bundle.world.custom_items["custom_1"].holder is None
