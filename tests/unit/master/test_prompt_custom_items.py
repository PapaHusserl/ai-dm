# Сюжетные предметы, партия Б (CUSTOM-ITEMS-PLAN, разд. 4, 5, 7): контекст мастера.
#   hero.inventory[*] = {"item_id", "qty", "cost_cp", "name"[, "quality"]}; у кастомного предмета
#       + "description" (обрезка до 119 знаков + «…», итог не длиннее 120) и "quest": true
#       для квестового (у SRD-вещей их нет);
#   item_ids в system[1] -- только SRD, без custom_*;
#   lost_items -- сюжетные (quest) предметы мира с держателем (holder), которых нет у героя:
#       у каждого item_id, name, label держателя и location_id (где искать); обычные
#       кастомные и предметы без держателя сюда не попадают (ключ ищется в JSON контекста
#       на любом уровне -- точное место решает реализация, форма записи -- плоская или с holder);
#   last_combat.gear -- имена снаряжения с тел последнего боя (строки или записи с name).
import json

from master_kit import app_cfg, make_ctx

from ai_dm.master.prompt import PromptBuilder
from ai_dm.rules.custom_items import world_registry
from ai_dm.rules.inventory import add_item
from ai_dm.state.hero import InventoryEntry
from ai_dm.state.session import LastCombat
from ai_dm.state.world import CustomItem, ItemHolder

LONG = "Старый, тяжёлый, с зубчатой бородкой. " * 6


def make_custom_ctx(registry, cfg, held=None, lost=None, plain=None):
    ctx = make_ctx(registry, cfg)
    world = ctx.bundle.world
    if held is not None:
        world.custom_items["custom_1"] = held
        add_item(ctx.hero, "custom_1", cost_cp=held.cost_cp)
    if plain is not None:
        world.custom_items["custom_2"] = plain
        add_item(ctx.hero, "custom_2", cost_cp=plain.cost_cp)
    if lost is not None:
        world.custom_items["custom_3"] = lost
    ctx.registry = world_registry(registry, world)
    return ctx


def key(**fields):
    data = {"id": "custom_1", "name": "Ржавый ключ", "created_s": 0, "quest": True,
            "description": "Ключ от ворот"}
    data.update(fields)
    return CustomItem(**data)


def ring(holder=None):
    return CustomItem(
        id="custom_3", name="Перстень графа", description="Печатка", quest=True, created_s=0,
        holder=holder,
    )


def klyk_holder():
    return ItemHolder(
        kind="band", ref="g1", label="вожак гоблинов Клык", location_id="cellar", since_s=5
    )


def request_of(ctx):
    return PromptBuilder(app_cfg()).build(ctx, "Осматриваюсь.", "explore")


def data_of(ctx):
    return json.loads(request_of(ctx).messages[0].content[0].text)


def entry_of(ctx, item_id):
    return [e for e in data_of(ctx)["hero"]["inventory"] if e["item_id"] == item_id][0]


def find_key(node, name):
    if isinstance(node, dict):
        if name in node:
            return node[name]
        for value in node.values():
            found = find_key(value, name)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = find_key(value, name)
            if found is not None:
                return found
    return None


# inventory: name / description / quest

def test_custom_entry_has_name(registry, cfg):
    ctx = make_custom_ctx(registry, cfg, held=key())
    assert entry_of(ctx, "custom_1")["name"] == "Ржавый ключ"


def test_custom_entry_has_description(registry, cfg):
    ctx = make_custom_ctx(registry, cfg, held=key())
    assert entry_of(ctx, "custom_1")["description"] == "Ключ от ворот"


def test_long_description_is_cut_to_120(registry, cfg):
    ctx = make_custom_ctx(registry, cfg, held=key(description=LONG))
    description = entry_of(ctx, "custom_1")["description"]
    assert description.startswith("Старый, тяжёлый")
    assert len(description) == 120
    assert description.endswith("…")
    assert description == LONG[:119] + "…"


def test_description_of_exactly_120_is_not_cut(registry, cfg):
    text = LONG[:120]
    ctx = make_custom_ctx(registry, cfg, held=key(description=text))
    assert entry_of(ctx, "custom_1")["description"] == text


def test_description_of_121_is_cut_with_ellipsis(registry, cfg):
    ctx = make_custom_ctx(registry, cfg, held=key(description=LONG[:121]))
    assert entry_of(ctx, "custom_1")["description"] == LONG[:119] + "…"


def test_clip_keeps_short_text():
    from ai_dm.master.prompt import clip

    assert clip("Ключ от ворот", 120) == "Ключ от ворот"


def test_clip_keeps_text_of_exactly_limit():
    from ai_dm.master.prompt import clip

    assert clip("abcde", 5) == "abcde"


def test_clip_cuts_longer_text_to_limit_with_ellipsis():
    from ai_dm.master.prompt import clip

    assert clip("abcdef", 5) == "abcd…"


def test_clip_of_empty_text_is_empty():
    from ai_dm.master.prompt import clip

    assert clip("", 5) == ""


def test_quest_custom_entry_is_marked_quest(registry, cfg):
    ctx = make_custom_ctx(registry, cfg, held=key())
    assert entry_of(ctx, "custom_1")["quest"] is True


def test_plain_custom_entry_is_not_marked_quest(registry, cfg):
    plain = key(id="custom_2", name="Тряпичная кукла", quest=False, description="Игрушка")
    ctx = make_custom_ctx(registry, cfg, plain=plain)
    entry = entry_of(ctx, "custom_2")
    assert entry["name"] == "Тряпичная кукла"
    assert not entry.get("quest")


def test_srd_entry_has_name(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_item(ctx.hero, "scimitar", cost_cp=2500)
    assert entry_of(ctx, "scimitar")["name"] == "Скимитар"


def test_srd_entry_has_no_description_and_no_quest(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_item(ctx.hero, "scimitar", cost_cp=2500)
    entry = entry_of(ctx, "scimitar")
    assert "description" not in entry
    assert not entry.get("quest")


def test_custom_entry_keeps_qty_and_cost(registry, cfg):
    ctx = make_custom_ctx(registry, cfg, held=key(cost_cp=300))
    entry = entry_of(ctx, "custom_1")
    assert (entry["qty"], entry["cost_cp"]) == (1, 300)


# item_ids

def test_item_ids_have_no_custom_ids(registry, cfg):
    ctx = make_custom_ctx(registry, cfg, held=key(), lost=ring(klyk_holder()))
    ids = json.loads(request_of(ctx).system[1].text)["item_ids"]
    assert not [x for x in ids if x.startswith("custom_")]


def test_item_ids_still_list_the_srd(registry, cfg):
    ctx = make_custom_ctx(registry, cfg, held=key())
    ids = json.loads(request_of(ctx).system[1].text)["item_ids"]
    assert "arrows" in ids


def test_system_world_block_does_not_name_custom_items(registry, cfg):
    ctx = make_custom_ctx(registry, cfg, held=key())
    assert "Ржавый ключ" not in request_of(ctx).system[1].text


# lost_items

def test_lost_item_lists_holder_label_and_place(registry, cfg):
    ctx = make_custom_ctx(registry, cfg, lost=ring(klyk_holder()))
    lost = find_key(data_of(ctx), "lost_items")
    text = json.dumps(lost, ensure_ascii=False)
    assert "custom_3" in text
    assert "Перстень графа" in text
    assert "вожак гоблинов Клык" in text
    assert "cellar" in text


def test_lost_items_has_one_record_for_one_item(registry, cfg):
    ctx = make_custom_ctx(registry, cfg, lost=ring(klyk_holder()))
    assert len(find_key(data_of(ctx), "lost_items")) == 1


def test_lost_items_skips_a_plain_custom_item_with_holder(registry, cfg):
    toy = ring(klyk_holder()).model_copy(update={"quest": False, "name": "Деревянная ложка"})
    ctx = make_custom_ctx(registry, cfg, lost=toy)
    lost = find_key(data_of(ctx), "lost_items")
    assert "Деревянная ложка" not in json.dumps(lost or [], ensure_ascii=False)


def test_lost_items_skips_a_quest_item_without_holder(registry, cfg):
    ctx = make_custom_ctx(registry, cfg, lost=ring(None))
    lost = find_key(data_of(ctx), "lost_items")
    assert "Перстень графа" not in json.dumps(lost or [], ensure_ascii=False)


def test_lost_items_skips_items_in_hero_inventory(registry, cfg):
    ctx = make_custom_ctx(registry, cfg, held=key())
    lost = find_key(data_of(ctx), "lost_items")
    assert "Ржавый ключ" not in json.dumps(lost or [], ensure_ascii=False)


def test_lost_items_is_empty_without_custom_items(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert not find_key(data_of(ctx), "lost_items")


def test_lost_item_after_recover_leaves_the_list(registry, cfg):
    ctx = make_custom_ctx(registry, cfg, lost=ring(klyk_holder()))
    ctx.bundle.world.custom_items["custom_3"].holder = None
    lost = find_key(data_of(ctx), "lost_items")
    assert "Перстень графа" not in json.dumps(lost or [], ensure_ascii=False)


# last_combat.gear

def gear_names(ctx):
    gear = find_key(data_of(ctx), "gear")
    return [g if isinstance(g, str) else g["name"] for g in gear]


def test_last_combat_gear_lists_names(registry, cfg):
    ctx = make_ctx(registry, cfg)
    gear = [InventoryEntry(item_id="scimitar", qty=3, cost_cp=15, quality="junk")]
    ctx.bundle.session.last_combat = LastCombat(defeated=["goblin_warrior"], gear=gear)
    names = gear_names(ctx)
    assert len(names) == 1
    assert "скимитар" in names[0].casefold()


def test_last_combat_is_absent_when_nothing_on_bodies(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.session.last_combat = LastCombat(defeated=["goblin_warrior"])
    assert "last_combat" not in data_of(ctx)


def test_no_last_combat_means_no_gear_in_context(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert find_key(data_of(ctx), "gear") is None


def test_last_combat_is_absent_when_gear_is_looted(registry, cfg):
    ctx = make_ctx(registry, cfg)
    gear = [InventoryEntry(item_id="dagger", qty=1, cost_cp=20, quality="junk")]
    ctx.bundle.session.last_combat = LastCombat(
        defeated=["goblin_warrior"], gear=gear, gear_looted=True
    )
    assert "last_combat" not in data_of(ctx)


def test_lost_items_is_absent_when_empty(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert "lost_items" not in data_of(ctx)


def test_lost_items_is_present_when_not_empty(registry, cfg):
    ctx = make_custom_ctx(registry, cfg, lost=ring(klyk_holder()))
    assert len(data_of(ctx)["lost_items"]) == 1


# форма записи lost_items (правила рассказчика называют holder.label / holder.location_id /
# holder.since_s и «id из lost_items»)

def lost_of(ctx):
    return find_key(data_of(ctx), "lost_items")


def test_lost_item_record_fields(registry, cfg):
    holder = ItemHolder(
        kind="band", ref="g1", label="вожак гоблинов Клык", location_id="cellar", since_s=77,
        qty=2,
    )
    ctx = make_custom_ctx(registry, cfg, lost=ring(holder))
    record = lost_of(ctx)[0]
    assert record["item_id"] == "custom_3"
    assert record["name"] == "Перстень графа"
    assert record["qty"] == 2
    assert record["holder"]["label"] == "вожак гоблинов Клык"
    assert record["holder"]["location_id"] == "cellar"
    assert record["holder"]["since_s"] == 77


def test_lost_items_freshest_first(registry, cfg):
    ctx = make_custom_ctx(registry, cfg, lost=ring(klyk_holder()))
    newer = ItemHolder(kind="location", ref="cellar", label="тайник", since_s=90)
    older = ItemHolder(kind="location", ref="cellar", label="тайник", since_s=10)
    world = ctx.bundle.world
    world.custom_items["custom_4"] = ring(newer).model_copy(update={"id": "custom_4"})
    world.custom_items["custom_5"] = ring(older).model_copy(update={"id": "custom_5"})
    ctx.registry = world_registry(registry, world)
    assert [r["item_id"] for r in lost_of(ctx)] == ["custom_4", "custom_5", "custom_3"]


def test_lost_items_with_the_same_time_go_by_id(registry, cfg):
    ctx = make_custom_ctx(registry, cfg, lost=ring(klyk_holder()))
    world = ctx.bundle.world
    world.custom_items["custom_2"] = ring(klyk_holder()).model_copy(update={"id": "custom_2"})
    ctx.registry = world_registry(registry, world)
    assert [r["item_id"] for r in lost_of(ctx)] == ["custom_2", "custom_3"]


def test_gear_stack_shows_quantity_only_above_one(registry, cfg):
    ctx = make_ctx(registry, cfg)
    gear = [
        InventoryEntry(item_id="scimitar", qty=3, cost_cp=15, quality="junk"),
        InventoryEntry(item_id="dagger", qty=1, cost_cp=20, quality="junk"),
    ]
    ctx.bundle.session.last_combat = LastCombat(defeated=["goblin_warrior"], gear=gear)
    many, one = gear_names(ctx)
    assert many.endswith("×3")
    assert "×" not in one


def test_gear_stack_of_two_shows_quantity(registry, cfg):
    ctx = make_ctx(registry, cfg)
    gear = [InventoryEntry(item_id="dagger", qty=2, cost_cp=20, quality="junk")]
    ctx.bundle.session.last_combat = LastCombat(defeated=["goblin_warrior"], gear=gear)
    assert gear_names(ctx)[0].endswith("×2")


def test_gear_lives_under_last_combat_key(registry, cfg):
    ctx = make_ctx(registry, cfg)
    gear = [InventoryEntry(item_id="dagger", qty=1, cost_cp=20, quality="junk")]
    ctx.bundle.session.last_combat = LastCombat(defeated=["goblin_warrior"], gear=gear)
    last = data_of(ctx)["last_combat"]
    assert len(last["gear"]) == 1
    assert "gear_looted" not in last
