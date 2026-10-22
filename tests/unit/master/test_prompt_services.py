# Реестр услуг, партия П1 (docs/plan-u0.md, У6): контекст мастера.
#   scene_npcs[i]["services"] = id услуг NPC -- только у NPC с услугами (живые, в сцене);
#   data["services"] -- список поставщиков сцены по порядку scene_npcs (по id):
#       {"npc_id", "items": [{"id", "name", "price_cp", "unit", "description"?}], "haggle"?};
#       ключа нет, если в сцене нет NPC с услугами (другая локация, мёртвые -- нет);
#   items: не больше 8 позиций, цена с отношением и торгом, description только если он есть;
#   haggle ({"percent"}) у поставщика без лавки, если сегодня торговались (состояние во флаге);
#       у NPC с лавкой торг виден в ключе trade, в services его нет.
import json

from master_kit import app_cfg, make_ctx

from ai_dm.master.prompt import SERVICE_ITEMS_MAX, PromptBuilder
from ai_dm.rules.trade import DAY_S
from ai_dm.state.world import NPC, TradeProfile

ALL_KINDS = [
    "room_poor", "room_modest", "room_comfortable", "room_wealthy", "meal_poor", "meal_modest",
    "meal_comfortable", "ale", "wine_common", "heal_barber",
]


def add_provider(ctx, npc_id="grok", services=("room_modest", "ale"), **fields):
    fields.setdefault("location_id", "vale")
    ctx.bundle.world.npcs[npc_id] = NPC(
        id=npc_id, name=npc_id.capitalize(), means=["трактир"], services=list(services), **fields
    )


def data_of(ctx):
    request = PromptBuilder(app_cfg()).build(ctx, "Осматриваюсь.", "explore")
    return json.loads(request.messages[0].content[0].text)


def services_of(ctx):
    return data_of(ctx)["services"]


def scene_npc(ctx, npc_id):
    return {n["id"]: n for n in data_of(ctx)["scene_npcs"]}[npc_id]


# scene_npcs.services

def test_scene_npc_lists_its_service_ids(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_provider(ctx)
    assert scene_npc(ctx, "grok")["services"] == ["room_modest", "ale"]


def test_scene_npc_without_services_has_no_services_field(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_provider(ctx)
    assert "services" not in scene_npc(ctx, "grakh")


def test_scene_npc_with_empty_services_has_no_services_field(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_provider(ctx, services=[])
    assert "services" not in scene_npc(ctx, "grok")


def test_dead_provider_is_not_in_scene_npcs(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_provider(ctx, status="dead")
    assert "grok" not in [n["id"] for n in data_of(ctx)["scene_npcs"]]


def test_merchant_with_services_has_both_fields(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_provider(ctx, trade=TradeProfile(kind="smith", purse_cp=100))
    npc = scene_npc(ctx, "grok")
    assert npc["merchant"] == "smith"
    assert npc["services"] == ["room_modest", "ale"]


# ключ services: когда есть

def test_no_provider_no_services_key(registry, cfg):
    assert "services" not in data_of(make_ctx(registry, cfg))


def test_services_key_with_provider_in_scene(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_provider(ctx)
    assert [s["npc_id"] for s in services_of(ctx)] == ["grok"]


def test_provider_in_other_location_gives_no_services_key(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_provider(ctx, location_id="forest")
    assert "services" not in data_of(ctx)


def test_provider_without_location_gives_no_services_key(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_provider(ctx, location_id=None)
    assert "services" not in data_of(ctx)


def test_dead_provider_gives_no_services_key(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_provider(ctx, status="dead")
    assert "services" not in data_of(ctx)


def test_services_key_has_only_scene_providers(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_provider(ctx, "far", location_id="forest")
    add_provider(ctx, "grok")
    assert [s["npc_id"] for s in services_of(ctx)] == ["grok"]


def test_providers_are_sorted_by_id(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_provider(ctx, "zed")
    add_provider(ctx, "abe")
    assert [s["npc_id"] for s in services_of(ctx)] == ["abe", "zed"]


def test_services_do_not_create_trade_key(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_provider(ctx)
    assert "trade" not in data_of(ctx)


def test_merchant_with_services_is_in_both_keys(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_provider(ctx, trade=TradeProfile(kind="general", purse_cp=100))
    data = data_of(ctx)
    assert [t["npc_id"] for t in data["trade"]] == ["grok"]
    assert [s["npc_id"] for s in data["services"]] == ["grok"]


# позиции

def test_item_fields(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_provider(ctx, services=["room_modest"])
    assert services_of(ctx)[0]["items"] == [{
        "id": "room_modest", "name": "комната (скромная)", "price_cp": 50, "unit": "night",
        "description": cfg.services.kinds["room_modest"].description,
    }]


def test_item_without_description_has_no_description_key(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_provider(ctx, services=["ale"])
    assert services_of(ctx)[0]["items"] == [
        {"id": "ale", "name": "эль (кружка)", "price_cp": 4, "unit": "meal"}
    ]


def test_items_keep_npc_order(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_provider(ctx, services=["ale", "room_modest", "meal_poor"])
    assert [i["id"] for i in services_of(ctx)[0]["items"]] == ["ale", "room_modest", "meal_poor"]


def test_unknown_service_id_is_skipped(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_provider(ctx, services=["castle", "ale"])
    assert [i["id"] for i in services_of(ctx)[0]["items"]] == ["ale"]


def test_items_are_capped_at_eight(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_provider(ctx, services=ALL_KINDS)
    items = services_of(ctx)[0]["items"]
    assert SERVICE_ITEMS_MAX == 8
    assert [i["id"] for i in items] == ALL_KINDS[:8]


def test_exactly_eight_items_are_all_kept(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_provider(ctx, services=ALL_KINDS[:8])
    assert len(services_of(ctx)[0]["items"]) == 8


def test_entry_has_exactly_the_documented_keys(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_provider(ctx)
    assert set(services_of(ctx)[0]) == {"npc_id", "items"}


# цены: отношение и торг

def test_prices_follow_good_attitude(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_provider(ctx, services=["room_modest"], attitude=60)
    assert services_of(ctx)[0]["items"][0]["price_cp"] == 45


def test_no_haggle_key_without_haggle(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_provider(ctx)
    assert "haggle" not in services_of(ctx)[0]


def test_flag_haggle_changes_prices_and_shows_percent(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_provider(ctx, services=["room_modest"])
    ctx.bundle.world.flags["haggle:grok"] = "0:-10"
    entry = services_of(ctx)[0]
    assert entry["items"][0]["price_cp"] == 45
    assert entry["haggle"] == {"percent": -10}


def test_failed_flag_haggle_shows_plus(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_provider(ctx, services=["room_modest"])
    ctx.bundle.world.flags["haggle:grok"] = "0:10"
    entry = services_of(ctx)[0]
    assert entry["items"][0]["price_cp"] == 55
    assert entry["haggle"] == {"percent": 10}


def test_yesterdays_flag_haggle_is_ignored(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_provider(ctx, services=["room_modest"])
    ctx.bundle.world.flags["haggle:grok"] = "0:-20"
    ctx.bundle.world.clock.advance(DAY_S)
    entry = services_of(ctx)[0]
    assert entry["items"][0]["price_cp"] == 50
    assert "haggle" not in entry


def test_other_npc_flag_does_not_affect_prices(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_provider(ctx, services=["room_modest"])
    ctx.bundle.world.flags["haggle:other"] = "0:-20"
    assert services_of(ctx)[0]["items"][0]["price_cp"] == 50


def test_shop_profile_haggle_prices_services_but_key_stays_in_trade(registry, cfg):
    ctx = make_ctx(registry, cfg)
    profile = TradeProfile(kind="general", purse_cp=100, haggle_percent=-20, haggle_day=0)
    add_provider(ctx, services=["room_modest"], trade=profile)
    entry = services_of(ctx)[0]
    assert entry["items"][0]["price_cp"] == 40
    assert "haggle" not in entry
    assert data_of(ctx)["trade"][0]["haggle"] == {"percent": -20}
