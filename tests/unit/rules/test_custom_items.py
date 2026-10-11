# Сюжетные предметы, партия А (CUSTOM-ITEMS-PLAN, разд. 1 и 5): ai_dm.rules.custom_items
#   as_item(custom: CustomItem) -> Item: id/name/description/cost_cp от предмета, category "quest"
#       для quest=True, иначе "valuable", source "world"
#   world_registry(base, world) -> ContentRegistry: base.with_items({"item": [as_item(c) ...]});
#       base не меняется; результат кэшируется по содержимому каталога (не по id мира):
#       тот же каталог (в т.ч. в копии мира) -> тот же объект, после добавления предмета -- новый
#   hand_over(world, item_id, holder: ItemHolder) -> None: custom_items[item_id].holder = holder
#   recover(world, item_id) -> None: holder = None (без держателя -- ничего не делает)
from ai_dm.core.rng import Rng
from ai_dm.rules.custom_items import as_item, hand_over, recover, world_registry
from ai_dm.rules.inventory import add_item, find_item, pick_valuables
from ai_dm.rules.triggers_eval import Truth, evaluate, validate_refs
from ai_dm.state.creature import CreatureState
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState
from ai_dm.state.triggers import HeroHas
from ai_dm.state.world import CustomItem, ItemHolder, WorldState


def world(*items):
    state = WorldState(world_id="w1", rng=Rng(1).state)
    for item in items:
        state.custom_items[item.id] = item
    return state


def key(**extra):
    return CustomItem(
        id="custom_1", name="Ржавый ключ", description="Открывает ворота", cost_cp=300,
        created_s=0, **extra,
    )


def ring():
    return CustomItem(id="custom_2", name="Перстень", created_s=5, quest=True)


def holder(ref="npc_klyk", **extra):
    fields = {"kind": "npc", "ref": ref, "label": "вожак Клык", "since_s": 10}
    fields.update(extra)
    return ItemHolder(**fields)


# as_item

def test_as_item_copies_id_name_description_and_price():
    item = as_item(key())
    assert item.id == "custom_1"
    assert item.name == "Ржавый ключ"
    assert item.description == "Открывает ворота"
    assert item.cost_cp == 300


def test_as_item_plain_is_valuable():
    assert as_item(key()).category == "valuable"


def test_as_item_quest_is_quest_category():
    assert as_item(key(quest=True)).category == "quest"


def test_as_item_comes_from_the_world():
    assert as_item(key()).source == "world"


def test_as_item_has_no_effects_or_magic():
    item = as_item(key(quest=True))
    assert item.effects == []
    assert item.magic is False


# world_registry

def test_world_registry_knows_the_custom_item(registry):
    overlay = world_registry(registry, world(key()))
    assert find_item(overlay, "custom_1") == ("item", overlay.get("item", "custom_1"))
    assert overlay.get("item", "custom_1").name == "Ржавый ключ"


def test_world_registry_keeps_the_srd(registry):
    overlay = world_registry(registry, world(key()))
    assert overlay.has("weapon", "longsword")
    assert overlay.has("item", "crowbar")
    assert overlay.has("monster", "goblin_warrior")


def test_world_registry_does_not_change_the_base(registry):
    ids_before = registry.ids("item")
    world_registry(registry, world(key()))
    assert registry.has("item", "custom_1") is False
    assert registry.ids("item") == ids_before


def test_world_registry_of_an_empty_catalog_equals_the_base_content(registry):
    overlay = world_registry(registry, world())
    assert overlay.ids("item") == registry.ids("item")


def test_world_registry_adds_every_item_of_the_catalog(registry):
    overlay = world_registry(registry, world(key(), ring()))
    assert overlay.has("item", "custom_1")
    assert overlay.has("item", "custom_2")
    assert overlay.get("item", "custom_2").category == "quest"


def test_world_registry_same_catalog_gives_the_same_object(registry):
    state = world(key())
    assert world_registry(registry, state) is world_registry(registry, state)


def test_world_registry_cache_works_on_a_copy_of_the_world(registry):
    state = world(key())
    copy = state.model_copy(deep=True)
    assert world_registry(registry, state) is world_registry(registry, copy)


def test_world_registry_gives_a_new_object_after_an_item_is_added(registry):
    state = world(key())
    before = world_registry(registry, state)
    state.custom_items["custom_2"] = ring()
    after = world_registry(registry, state)
    assert after is not before
    assert after.has("item", "custom_2")
    assert before.has("item", "custom_2") is False


def test_world_registry_cache_is_per_base(registry):
    state = world(key())
    other_base = registry.with_items({})
    assert world_registry(registry, state) is not world_registry(other_base, state)


def test_world_registry_holder_does_not_change_the_registry(registry):
    state = world(key())
    before = world_registry(registry, state)
    hand_over(state, "custom_1", holder())
    assert world_registry(registry, state) is before


def test_world_registry_cache_keeps_only_the_last_pair(registry):
    state = world(key())
    first = world_registry(registry, state)
    state.custom_items["custom_2"] = ring()
    second = world_registry(registry, state)
    assert registry.overlay is second
    state.custom_items.pop("custom_2")
    assert world_registry(registry, state) is not first
    assert registry.overlay is not second


def test_world_registry_overlay_is_not_built_on_top_of_an_overlay(registry):
    state = world(key())
    overlay = world_registry(registry, state)
    assert overlay.overlay is None
    assert overlay.overlay_key is None


# hand_over / recover

def test_hand_over_sets_the_holder():
    state = world(key())
    hand_over(state, "custom_1", holder(location_id="goblin_den"))
    got = state.custom_items["custom_1"].holder
    assert (got.kind, got.ref, got.label) == ("npc", "npc_klyk", "вожак Клык")
    assert got.location_id == "goblin_den"
    assert got.since_s == 10


def test_hand_over_replaces_the_previous_holder():
    state = world(key())
    hand_over(state, "custom_1", holder("npc_klyk"))
    hand_over(state, "custom_1", holder("npc_other", kind="band"))
    got = state.custom_items["custom_1"].holder
    assert (got.kind, got.ref) == ("band", "npc_other")


def test_hand_over_touches_only_that_item():
    state = world(key(), ring())
    hand_over(state, "custom_1", holder())
    assert state.custom_items["custom_2"].holder is None


def test_hand_over_keeps_the_rest_of_the_item():
    state = world(key(quest=True))
    hand_over(state, "custom_1", holder())
    item = state.custom_items["custom_1"]
    assert (item.name, item.cost_cp, item.quest) == ("Ржавый ключ", 300, True)


def test_recover_clears_the_holder():
    state = world(key(holder=holder()))
    recover(state, "custom_1")
    assert state.custom_items["custom_1"].holder is None


def test_recover_touches_only_that_item():
    state = world(key(holder=holder()), CustomItem(
        id="custom_2", name="Перстень", created_s=5, holder=holder("npc_other")
    ))
    recover(state, "custom_1")
    assert state.custom_items["custom_2"].holder.ref == "npc_other"


def test_recover_without_a_holder_is_fine():
    state = world(key())
    recover(state, "custom_1")
    assert state.custom_items["custom_1"].holder is None


def test_recover_keeps_the_rest_of_the_item():
    state = world(key(quest=True, holder=holder()))
    recover(state, "custom_1")
    item = state.custom_items["custom_1"]
    assert (item.name, item.cost_cp, item.quest) == ("Ржавый ключ", 300, True)


# предмет в игре: триггер и грабёж видят каталог через наложение

def make_hero():
    sheet = CharacterSheet(
        species_id="human",
        classes=[ClassLevel(class_id="fighter")], level_history=["fighter"] * 1,
        background=BackgroundSpec(
            name="Солдат",
            abilities=["str", "dex", "con"],
            skills=["athletics", "intimidation"],
            tool="dice_set",
            feat="savage_attacker",
        ),
        abilities={"str": 17, "dex": 13, "con": 15, "int": 8, "wis": 10, "cha": 12},
    )
    return HeroState(
        id="h1", ordinal=1, name="Арн", sheet=sheet,
        creature=CreatureState(hp_current=12, hp_max=12),
    )


def test_hero_has_trigger_fires_for_a_custom_id():
    hero = make_hero()
    add_item(hero, "custom_1", cost_cp=300)
    result = evaluate(HeroHas(item="custom_1"), world(key()), hero)
    assert result.truth == Truth.TRUE


def test_hero_has_trigger_is_false_without_the_custom_item():
    result = evaluate(HeroHas(item="custom_1"), world(key()), make_hero())
    assert result.truth == Truth.FALSE


def test_custom_id_is_a_valid_ref_in_the_world_registry(registry):
    state = world(key())
    overlay = world_registry(registry, state)
    assert validate_refs(HeroHas(item="custom_1"), state, overlay) == []


def test_custom_id_is_a_broken_ref_in_the_base_registry(registry):
    problems = validate_refs(HeroHas(item="custom_1"), world(key()), registry)
    assert len(problems) == 1
    assert "custom_1" in problems[0]


def test_pick_valuables_takes_a_custom_item_through_the_world_registry(registry):
    hero = make_hero()
    add_item(hero, "custom_1", cost_cp=9000)
    add_item(hero, "spear", cost_cp=100)
    overlay = world_registry(registry, world(key(quest=True)))
    picked = pick_valuables(hero, overlay, Rng(1), 1)
    assert [(e.item_id, e.cost_cp) for e in picked] == [("custom_1", 9000)]


def test_pick_valuables_skips_a_custom_item_the_registry_does_not_know(registry):
    hero = make_hero()
    add_item(hero, "custom_1", cost_cp=9000)
    add_item(hero, "spear", cost_cp=100)
    picked = pick_valuables(hero, registry, Rng(1), 2)
    assert [e.item_id for e in picked] == ["spear"]
