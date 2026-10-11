# Трофеи с тел, выдача (docs/CUSTOM-ITEMS-PLAN.md, разд. 7, партия В; В16).
#   gold loot_individual выдаёт деньги И снаряжение с тел (last_combat.gear -- записи инвентаря):
#     * результат {amount_cp, money_cp, items: [{item_id, qty, name}]}, name -- с качеством
#       («Ржавый скимитар»); в лог строка «Добыча: Ржавый скимитар x3» после строки с деньгами;
#     * предметы попадают в инвентарь героя со своей ценой и качеством (стеки: тот же
#       (id, цена, качество) -- qty растёт), событие item_gained на каждую запись;
#     * флаги раздельные: looted -- деньги, gear_looted -- снаряжение; отклоняется (rejected с
#       signal_to_master), только когда выданы оба; один выдан -- второй выдаётся, выданное
#       повторно не выдаётся;
#     * старый сейв (миграция: gear [], gear_looted True) -- предметов нет, деньги по looted;
#     * квестовый кастомный предмет в gear -- возвращается герою, держатель снимается (holder None);
#     * каталог мира для обычных трофеев не меняется.
from protocol_kit import ScriptedRng, dump, make_bundle, make_ctx, req

from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.rules.custom_items import hand_over
from ai_dm.rules.inventory import count_item, equip
from ai_dm.state.hero import InventoryEntry
from ai_dm.state.session import LastCombat
from ai_dm.state.world import CustomItem, ItemHolder


def junk(item_id="scimitar", qty=3, cost_cp=250):
    return InventoryEntry(item_id=item_id, qty=qty, cost_cp=cost_cp, quality="junk")


def loot_ctx(registry, cfg, gear, defeated=(), rng=None, **flags):
    bundle = make_bundle(registry)
    bundle.heroes[0].money_cp = 0
    bundle.session.last_combat = LastCombat(defeated=list(defeated), gear=gear, **flags)
    return make_ctx(registry, cfg, rng, bundle=bundle)


def loot_req():
    return req("gold", direction="gain", kind="loot_individual")


def stacks(ctx, item_id):
    return sorted(
        (e.cost_cp, e.quality, e.qty) for e in ctx.hero.inventory if e.item_id == item_id
    )


def last(ctx):
    return ctx.bundle.session.last_combat


# первая выдача

def test_first_loot_gives_the_gear_to_the_hero(registry, cfg):
    ctx = loot_ctx(registry, cfg, [junk()])
    before = count_item(ctx.hero, "scimitar")
    d = apply(ctx, loot_req())
    assert d.status == "accepted"
    assert count_item(ctx.hero, "scimitar") == before + 3
    assert (250, "junk", 3) in stacks(ctx, "scimitar")


def test_first_loot_marks_gear_looted(registry, cfg):
    ctx = loot_ctx(registry, cfg, [junk()])
    apply(ctx, loot_req())
    assert last(ctx).gear_looted is True
    assert last(ctx).looted is True


def test_result_items_carry_id_qty_and_name_with_quality(registry, cfg):
    ctx = loot_ctx(registry, cfg, [junk()])
    d = apply(ctx, loot_req())
    assert d.result["items"] == [{"item_id": "scimitar", "qty": 3, "name": "Ржавый скимитар"}]


def test_result_keeps_money_fields(registry, cfg):
    ctx = loot_ctx(registry, cfg, [junk()])
    d = apply(ctx, loot_req())
    assert d.result["amount_cp"] == 0
    assert d.result["money_cp"] == ctx.hero.money_cp


def test_log_names_the_items(registry, cfg):
    ctx = loot_ctx(registry, cfg, [junk(), junk("shortbow", 1)])
    d = apply(ctx, loot_req())
    assert d.log == ["Добыча: Ржавый скимитар x3, Ржавый короткий лук"]


def test_money_and_gear_come_together(registry, cfg):
    ctx = loot_ctx(registry, cfg, [junk()], ["goblin_warrior"], ScriptedRng(d6=[1, 1, 1, 1]))
    d = apply(ctx, loot_req())
    assert d.result["amount_cp"] == 400
    assert ctx.hero.money_cp == 400
    assert d.result["items"][0]["item_id"] == "scimitar"


def test_empty_gear_gives_empty_items(registry, cfg):
    ctx = loot_ctx(registry, cfg, [])
    d = apply(ctx, loot_req())
    assert d.status == "accepted"
    assert d.result["items"] == []
    assert d.log == []


def test_item_gained_event_per_entry(registry, cfg):
    ctx = loot_ctx(registry, cfg, [junk(), junk("shortbow", 1)])
    apply(ctx, loot_req())
    gained = [(e.data["item"], e.data["qty"]) for e in ctx.events if e.type == "item_gained"]
    assert gained == [("scimitar", 3), ("shortbow", 1)]


def test_trophy_does_not_change_the_world_catalog(registry, cfg):
    ctx = loot_ctx(registry, cfg, [junk()])
    apply(ctx, loot_req())
    assert ctx.bundle.world.custom_items == {}


def test_trophy_can_be_equipped_as_a_usual_weapon(registry, cfg):
    ctx = loot_ctx(registry, cfg, [junk()])
    ctx.hero.inventory = []
    ctx.hero.equipped.main_hand = None
    apply(ctx, loot_req())
    equip(ctx.hero, "scimitar", registry)
    assert ctx.hero.equipped.main_hand == "scimitar"


# стеки

def test_second_combat_with_same_price_grows_the_stack(registry, cfg):
    ctx = loot_ctx(registry, cfg, [junk(qty=3)])
    apply(ctx, loot_req())
    ctx.bundle.session.last_combat = LastCombat(gear=[junk(qty=2)])
    apply(ctx, loot_req())
    assert (250, "junk", 5) in stacks(ctx, "scimitar")


def test_trophy_stack_is_separate_from_srd_weapon(registry, cfg):
    ctx = loot_ctx(registry, cfg, [junk(qty=1)])
    ctx.hero.inventory = []
    srd = registry.get("weapon", "scimitar").cost_cp
    ctx.hero.inventory.append(InventoryEntry(item_id="scimitar", cost_cp=srd))
    apply(ctx, loot_req())
    assert stacks(ctx, "scimitar") == [(250, "junk", 1), (srd, None, 1)]


# повтор и флаги

def test_second_loot_is_rejected_and_changes_nothing(registry, cfg):
    ctx = loot_ctx(registry, cfg, [junk()])
    apply(ctx, loot_req())
    before = dump(ctx)
    d = apply(ctx, loot_req())
    assert isinstance(d, Decision)
    assert d.status == "rejected"
    assert d.signal_to_master
    assert dump(ctx) == before


def test_old_save_gives_neither_money_twice_nor_items(registry, cfg):
    ctx = loot_ctx(registry, cfg, [], looted=True, gear_looted=True)
    before = dump(ctx)
    d = apply(ctx, loot_req())
    assert d.status == "rejected"
    assert dump(ctx) == before


def test_money_taken_gear_not_yet_gives_only_the_gear(registry, cfg):
    ctx = loot_ctx(registry, cfg, [junk()], ["goblin_warrior"], looted=True)
    d = apply(ctx, loot_req())
    assert d.status == "accepted"
    assert d.result["amount_cp"] == 0
    assert ctx.hero.money_cp == 0
    assert d.result["items"][0]["qty"] == 3
    assert last(ctx).gear_looted is True


def test_gear_taken_money_not_yet_gives_only_the_money(registry, cfg):
    ctx = loot_ctx(
        registry, cfg, [junk()], ["goblin_warrior"], ScriptedRng(d6=[1, 1, 1, 1]),
        gear_looted=True,
    )
    before = count_item(ctx.hero, "scimitar")
    d = apply(ctx, loot_req())
    assert d.status == "accepted"
    assert d.result["amount_cp"] == 400
    assert d.result["items"] == []
    assert count_item(ctx.hero, "scimitar") == before
    assert last(ctx).looted is True


def test_money_and_gear_give_two_log_lines(registry, cfg):
    ctx = loot_ctx(registry, cfg, [junk()], ["goblin_warrior"], ScriptedRng(d6=[1, 1, 1, 1]))
    d = apply(ctx, loot_req())
    assert d.log[0].startswith("Добыча: +")
    assert d.log[1] == "Добыча: Ржавый скимитар x3"


def test_money_taken_and_no_gear_is_rejected(registry, cfg):
    ctx = loot_ctx(registry, cfg, [], looted=True)
    assert apply(ctx, loot_req()).status == "rejected"


def test_quest_item_return_line_uses_the_catalog_name(registry, cfg):
    from ai_dm.rules.custom_items import world_registry

    ctx = quest_ctx(registry, cfg)
    ctx.registry = world_registry(registry, ctx.bundle.world)
    d = apply(ctx, loot_req())
    assert "Возвращён предмет: Ржавый ключ x1" in d.log


def test_only_money_loot_adds_no_extra_log_line(registry, cfg):
    ctx = loot_ctx(
        registry, cfg, [junk()], ["goblin_warrior"], ScriptedRng(d6=[1, 1, 1, 1]),
        gear_looted=True,
    )
    d = apply(ctx, loot_req())
    assert len(d.log) == 1


def test_no_combat_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert isinstance(apply(ctx, loot_req()), Invalid)


# квестовые предметы с тел

def quest_ctx(registry, cfg):
    ctx = loot_ctx(registry, cfg, [InventoryEntry(item_id="custom_1", cost_cp=900)])
    ctx.bundle.world.custom_items["custom_1"] = CustomItem(
        id="custom_1", name="Ржавый ключ", quest=True, created_s=0
    )
    hand_over(
        ctx.bundle.world, "custom_1",
        ItemHolder(kind="npc", ref="aldric", label="Олдрик", since_s=0, cost_cp=900),
    )
    return ctx


def test_quest_item_returns_to_the_hero_and_holder_is_cleared(registry, cfg):
    ctx = quest_ctx(registry, cfg)
    apply(ctx, loot_req())
    assert (900, None, 1) in stacks(ctx, "custom_1")
    assert ctx.bundle.world.custom_items["custom_1"].holder is None


def test_quest_item_is_listed_in_result_items(registry, cfg):
    ctx = quest_ctx(registry, cfg)
    d = apply(ctx, loot_req())
    assert [i["item_id"] for i in d.result["items"]] == ["custom_1"]


def test_quest_item_name_comes_from_the_world_catalog(registry, cfg):
    from ai_dm.rules.custom_items import world_registry

    ctx = quest_ctx(registry, cfg)
    ctx.registry = world_registry(registry, ctx.bundle.world)
    d = apply(ctx, loot_req())
    assert d.result["items"][0]["name"] == "Ржавый ключ"


def test_loose_direction_is_invalid_with_code(registry, cfg):
    ctx = loot_ctx(registry, cfg, [junk()])
    d = apply(ctx, req("gold", direction="lose", kind="loot_individual"))
    assert isinstance(d, Invalid)
    assert d.code == "bad_amount"


def test_no_combat_invalid_has_its_code(registry, cfg):
    d = apply(make_ctx(registry, cfg), loot_req())
    assert d.code == "no_combat_loot"


def test_rejection_carries_a_reason(registry, cfg):
    ctx = loot_ctx(registry, cfg, [junk()])
    apply(ctx, loot_req())
    assert apply(ctx, loot_req()).reason
