# Торговля, партия Т2 (TRADE-PLAN, разд. 1): мастер назначает торговцев через trade_kind.
#   npc_create / npc_update получают trade_kind: пресет из [trade.presets]; "none" = не торговец /
#       не менять. Новый торговец получает TradeProfile(kind, purse_cp = пресет, stock []).
#   Лимит [trade].new_merchants_per_scene (1), счётчик SceneState.merchants_created;
#       сверх -> rejected.
#   Ключевого NPC мастер в торговцы не превращает -> rejected (NPC при npc_create не создаётся).
#   Неизвестный пресет -> Invalid unknown_trade_kind. npc_update только с trade_kind -- не пустой.
#   Уже торговец -> rejected; не alive -> Invalid npc_not_alive.
from protocol_kit import dump, make_ctx, req

from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid


def create(ctx, npc_id="smith_1", **fields):
    data = {"name": "Кузнец Борин", "means": ["молот"], "named": True}
    data.update(fields)
    return apply(ctx, req("npc_create", id=npc_id, **data))


def update(ctx, npc_id="aldric", **fields):
    return apply(ctx, req("npc_update", npc_id=npc_id, **fields))


def npc(ctx, npc_id):
    return ctx.bundle.world.npcs[npc_id]


# npc_create

def test_create_with_trade_kind_makes_a_merchant(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = create(ctx, trade_kind="smith")
    assert isinstance(d, Decision)
    assert d.status == "accepted"
    assert npc(ctx, "smith_1").trade.kind == "smith"


def test_created_merchant_has_the_preset_purse_and_empty_stock(registry, cfg):
    ctx = make_ctx(registry, cfg)
    create(ctx, trade_kind="smith")
    profile = npc(ctx, "smith_1").trade
    assert profile.purse_cp == cfg.trade.presets["smith"].purse_cp
    assert profile.stock == []


def test_created_merchant_restocks_after_the_period(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.clock.advance(1000)
    create(ctx, trade_kind="smith")
    assert npc(ctx, "smith_1").trade.restock_at_s == 1000 + cfg.trade.restock_days * 86400


def test_created_merchant_is_counted_in_the_scene(registry, cfg):
    ctx = make_ctx(registry, cfg)
    create(ctx, trade_kind="general")
    assert ctx.scene.merchants_created == 1


def test_create_with_none_is_not_a_merchant(registry, cfg):
    ctx = make_ctx(registry, cfg)
    create(ctx, trade_kind="none")
    assert npc(ctx, "smith_1").trade is None
    assert ctx.scene.merchants_created == 0


def test_create_without_trade_kind_is_not_a_merchant(registry, cfg):
    ctx = make_ctx(registry, cfg)
    create(ctx)
    assert npc(ctx, "smith_1").trade is None


def test_create_with_unknown_kind_is_invalid_and_changes_nothing(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    d = create(ctx, trade_kind="wizard_bazaar")
    assert isinstance(d, Invalid)
    assert d.code == "unknown_trade_kind"
    assert dump(ctx) == before


def test_second_new_merchant_in_a_scene_is_rejected(registry, cfg):
    ctx = make_ctx(registry, cfg)
    create(ctx, "smith_1", trade_kind="smith")
    before = dump(ctx)
    d = create(ctx, "smith_2", name="Кузнец Торин", trade_kind="smith")
    assert d.status == "rejected"
    assert d.signal_to_master
    assert dump(ctx) == before


def test_new_scene_allows_a_new_merchant_again(registry, cfg):
    ctx = make_ctx(registry, cfg)
    create(ctx, "smith_1", trade_kind="smith")
    ctx.scene.merchants_created = 0
    d = create(ctx, "smith_2", name="Кузнец Торин", trade_kind="smith")
    assert d.status == "accepted"


def test_plain_npc_after_the_limit_is_still_created(registry, cfg):
    ctx = make_ctx(registry, cfg)
    create(ctx, "smith_1", trade_kind="smith")
    d = create(ctx, "cook_1", name="Повар Ганс")
    assert d.status == "accepted"


def test_key_npc_cannot_be_created_as_a_merchant(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    d = create(ctx, key=True, trade_kind="general")
    assert d.status == "rejected"
    assert d.signal_to_master
    assert dump(ctx) == before


def test_limit_is_taken_from_the_config(registry, cfg):
    changed = cfg.model_copy(deep=True)
    changed.trade.new_merchants_per_scene = 2
    ctx = make_ctx(registry, changed)
    create(ctx, "smith_1", trade_kind="smith")
    d = create(ctx, "smith_2", name="Кузнец Торин", trade_kind="smith")
    assert d.status == "accepted"
    d = create(ctx, "smith_3", name="Кузнец Хельга", trade_kind="smith")
    assert d.status == "rejected"


# npc_update

def test_update_trade_kind_makes_a_merchant(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = update(ctx, trade_kind="general")
    assert d.status == "accepted"
    assert npc(ctx, "aldric").trade.kind == "general"
    assert npc(ctx, "aldric").trade.purse_cp == cfg.trade.presets["general"].purse_cp
    assert ctx.scene.merchants_created == 1


def test_update_with_trade_kind_only_is_not_an_empty_update(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert not isinstance(update(ctx, trade_kind="general"), Invalid)


def test_update_none_alone_is_still_empty(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = update(ctx, trade_kind="none")
    assert isinstance(d, Invalid)
    assert d.code == "empty_update"


def test_update_none_with_attitude_does_not_touch_the_trade(registry, cfg):
    ctx = make_ctx(registry, cfg)
    update(ctx, trade_kind="general")
    d = update(ctx, attitude_delta=5, trade_kind="none")
    assert d.status == "accepted"
    assert npc(ctx, "aldric").trade.kind == "general"


def test_update_makes_a_merchant_together_with_attitude(registry, cfg):
    ctx = make_ctx(registry, cfg)
    update(ctx, attitude_delta=5, trade_kind="smith")
    assert npc(ctx, "aldric").attitude == 5
    assert npc(ctx, "aldric").trade.kind == "smith"


def test_update_key_npc_is_rejected(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    d = update(ctx, "grakh", trade_kind="general")
    assert d.status == "rejected"
    assert d.signal_to_master
    assert dump(ctx) == before


def test_update_unknown_kind_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    d = update(ctx, trade_kind="wizard_bazaar")
    assert isinstance(d, Invalid)
    assert d.code == "unknown_trade_kind"
    assert dump(ctx) == before


def test_update_second_merchant_in_a_scene_is_rejected(registry, cfg):
    ctx = make_ctx(registry, cfg)
    create(ctx, "smith_1", trade_kind="smith")
    before = dump(ctx)
    d = update(ctx, trade_kind="general")
    assert d.status == "rejected"
    assert dump(ctx) == before


def test_update_attitude_alone_is_not_blocked_by_the_limit(registry, cfg):
    ctx = make_ctx(registry, cfg)
    create(ctx, "smith_1", trade_kind="smith")
    assert update(ctx, attitude_delta=3).status == "accepted"


def test_update_existing_merchant_does_not_change_its_kind(registry, cfg):
    ctx = make_ctx(registry, cfg)
    update(ctx, trade_kind="general")
    ctx.scene.merchants_created = 0
    d = update(ctx, trade_kind="smith")
    assert d.status == "rejected"
    assert npc(ctx, "aldric").trade.kind == "general"


def test_update_dead_npc_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    npc(ctx, "aldric").status = "dead"
    before = dump(ctx)
    d = update(ctx, trade_kind="general")
    assert isinstance(d, Invalid)
    assert dump(ctx) == before


def test_update_trade_kind_with_death_in_one_request_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    d = update(ctx, status="dead", cause="goal", evidence_ref="r1", trade_kind="general")
    assert isinstance(d, Invalid)
    assert dump(ctx) == before


def test_update_trade_kind_with_gone_in_one_request_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = update(ctx, status="gone", cause="goal", evidence_ref="r1", trade_kind="general")
    assert isinstance(d, Invalid)
    assert npc(ctx, "aldric").trade is None
