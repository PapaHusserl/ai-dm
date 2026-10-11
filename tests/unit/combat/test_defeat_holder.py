# Сюжетные предметы, партия А (CUSTOM-ITEMS-PLAN, разд. 5; В3, В10, В12): держатель предмета
# при поражении. Реестр для apply_defeat_outcome -- наложенный (rules.custom_items.world_registry),
# как в игре; без него кастомный id реестру неизвестен.
#   rob     -- pick_valuables берёт и квестовые (по цене). Каждый взятый кастомный предмет (любой,
#              не только квестовый) получает world.custom_items[id].holder:
#                лидер группы defeat_group_id -- NPC из world.npcs -> kind "npc", ref = leader_id,
#                  label = имя NPC; иначе kind "band", ref = leader_id, label содержит имя лидера
#                  (Participant.name или имя монстра); location_id = логово группы или локация
#                  героя (hero.location_id); нет группы поражения -> kind "location",
#                  ref = hero.location_id, location_id = та же локация.
#              holder.since_s = world.clock.now_s, holder.qty = сколько взято, holder.cost_cp =
#              цена снятого стека. SRD-вещи держателя не получают, каталог не меняется.
#   capture -- любые кастомные (и квестовые, и нет; SRD очищаются): holder kind "location",
#              ref и location_id = логово, label
#              "тайник логова", qty/cost_cp стека; инвентарь и equipped очищены целиком.
#   Отклонённый запрос (check_request) не меняет и держателей.
from combat_kit import ScriptedRng, down_hero, make_engine, make_fighter, mon

from ai_dm.combat.defeat import DefeatParams, apply_defeat_outcome
from ai_dm.rules.custom_items import world_registry
from ai_dm.rules.inventory import add_item, count_item
from ai_dm.state.hero import Equipped
from ai_dm.state.world import CustomItem


def defeated(registry, cfg, named=True, group=True):
    # герой повержен группой гоблинов: логово goblin_den, лидер goblin_1 (NPC или безымянный)
    hero = make_fighter(registry)
    engine = make_engine(
        registry, cfg, heroes=[hero], intent="rob",
        monsters=[mon("goblin_1", "goblin_warrior", "hall", named=named),
                  mon("goblin_2", "goblin_warrior", "hall", named=named)],
    )
    hero.location_id = "vale"
    hero.inventory = []
    hero.equipped = Equipped()
    engine.state.groups["goblins"].lair_location_id = "goblin_den"
    if group:
        engine.state.defeat_group_id = "goblins"
    engine.state.outcome = "defeat_pending"
    down_hero(engine, "hero", by="goblin_1")
    return engine, hero


def custom(engine, item_id, name, quest=True):
    engine.world.custom_items[item_id] = CustomItem(
        id=item_id, name=name, quest=quest, created_s=0
    )


def apply(engine, hero, registry, cfg, consequences, params=None):
    overlay = world_registry(registry, engine.world)
    return apply_defeat_outcome(
        engine.state, consequences, params or DefeatParams(), world=engine.world, hero=hero,
        registry=overlay, cfg=cfg, rng=ScriptedRng(),
    )


def holder_of(engine, item_id="custom_1"):
    return engine.world.custom_items[item_id].holder


def with_key(registry, cfg, **kwargs):
    # у героя ржавый ключ (дороже всего остального) и копьё
    engine, hero = defeated(registry, cfg, **kwargs)
    custom(engine, "custom_1", "Ржавый ключ")
    add_item(hero, "custom_1", cost_cp=9000)
    add_item(hero, "spear", cost_cp=100)
    return engine, hero


# rob: именованный лидер

def test_rob_takes_the_quest_item_from_the_hero(registry, cfg):
    engine, hero = with_key(registry, cfg)
    apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=1))
    assert count_item(hero, "custom_1") == 0
    assert count_item(hero, "spear") == 1


def test_rob_by_a_named_leader_makes_an_npc_holder(registry, cfg):
    engine, hero = with_key(registry, cfg)
    apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=1))
    holder = holder_of(engine)
    assert holder.kind == "npc"
    assert holder.ref == "goblin_1"
    assert holder.location_id == "goblin_den"


def test_npc_holder_label_is_the_npc_name(registry, cfg):
    engine, hero = with_key(registry, cfg)
    apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=1))
    assert engine.world.npcs["goblin_1"].name in holder_of(engine).label


def test_holder_remembers_time_qty_and_price(registry, cfg):
    engine, hero = with_key(registry, cfg)
    engine.world.clock.advance(3600)
    apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=1))
    holder = holder_of(engine)
    assert holder.since_s == 3600
    assert holder.qty == 1
    assert holder.cost_cp == 9000


def test_rob_takes_a_stack_of_two_when_asked_for_two(registry, cfg):
    engine, hero = defeated(registry, cfg)
    custom(engine, "custom_1", "Ржавый ключ")
    add_item(hero, "custom_1", 2, cost_cp=9000)
    apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=2))
    assert count_item(hero, "custom_1") == 0
    assert holder_of(engine).qty == 2


def test_rob_holds_every_taken_custom_item(registry, cfg):
    engine, hero = defeated(registry, cfg)
    custom(engine, "custom_1", "Ржавый ключ")
    custom(engine, "custom_2", "Записка")
    add_item(hero, "custom_1", cost_cp=9000)
    add_item(hero, "custom_2", cost_cp=8000)
    apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=2))
    assert holder_of(engine, "custom_1").ref == "goblin_1"
    assert holder_of(engine, "custom_2").ref == "goblin_1"


def test_rob_leaves_the_untaken_custom_item_without_a_holder(registry, cfg):
    engine, hero = defeated(registry, cfg)
    custom(engine, "custom_1", "Ржавый ключ")
    custom(engine, "custom_2", "Записка")
    add_item(hero, "custom_1", cost_cp=9000)
    add_item(hero, "custom_2", cost_cp=8000)
    apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=1))
    assert holder_of(engine, "custom_1") is not None
    assert holder_of(engine, "custom_2") is None
    assert count_item(hero, "custom_2") == 1


def test_rob_of_a_plain_custom_item_also_gets_a_holder(registry, cfg):
    engine, hero = defeated(registry, cfg)
    custom(engine, "custom_1", "Ложка", quest=False)
    add_item(hero, "custom_1", cost_cp=9000)
    apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=1))
    assert holder_of(engine).kind == "npc"


# rob: безымянный лидер

def test_rob_by_an_unnamed_leader_makes_a_band_holder(registry, cfg):
    engine, hero = with_key(registry, cfg, named=False)
    apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=1))
    holder = holder_of(engine)
    assert holder.kind == "band"
    assert holder.ref == "goblin_1"


def test_band_holder_label_has_the_leader_name(registry, cfg):
    engine, hero = with_key(registry, cfg, named=False)
    apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=1))
    assert "Воин-гоблин" in holder_of(engine).label


def test_band_holder_label_falls_back_to_the_monster_name(registry, cfg):
    engine, hero = with_key(registry, cfg, named=False)
    leader = [p for p in engine.state.participants if p.ref == "goblin_1"][0]
    leader.name = ""
    apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=1))
    assert registry.get("monster", "goblin_warrior").name in holder_of(engine).label


def test_band_holder_looks_for_the_lair(registry, cfg):
    engine, hero = with_key(registry, cfg, named=False)
    apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=1))
    assert holder_of(engine).location_id == "goblin_den"


def test_band_holder_without_a_lair_looks_at_the_hero_location(registry, cfg):
    engine, hero = with_key(registry, cfg, named=False)
    engine.state.groups["goblins"].lair_location_id = None
    apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=1))
    assert holder_of(engine).location_id == "vale"


def test_npc_holder_without_a_lair_looks_at_the_hero_location(registry, cfg):
    engine, hero = with_key(registry, cfg)
    engine.state.groups["goblins"].lair_location_id = None
    apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=1))
    assert holder_of(engine).location_id == "vale"


# rob без группы поражения

def test_rob_without_a_defeat_group_makes_a_location_holder(registry, cfg):
    engine, hero = with_key(registry, cfg, group=False)
    apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=1))
    holder = holder_of(engine)
    assert holder.kind == "location"
    assert holder.ref == "vale"
    assert holder.location_id == "vale"
    assert count_item(hero, "custom_1") == 0


# rob: SRD-вещи

def test_rob_of_srd_valuables_makes_no_holder(registry, cfg):
    engine, hero = defeated(registry, cfg)
    add_item(hero, "spear", cost_cp=100)
    apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=1))
    assert count_item(hero, "spear") == 0
    assert engine.world.custom_items == {}


def test_rob_of_srd_beside_a_custom_item_does_not_touch_the_custom_one(registry, cfg):
    engine, hero = defeated(registry, cfg)
    custom(engine, "custom_1", "Ржавый ключ")
    add_item(hero, "custom_1", cost_cp=1)
    add_item(hero, "spear", cost_cp=100)
    apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=1))
    assert count_item(hero, "spear") == 0
    assert holder_of(engine) is None


def test_rob_of_money_only_makes_no_holder(registry, cfg):
    engine, hero = with_key(registry, cfg)
    hero.money_cp = 1000
    apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=0))
    assert holder_of(engine) is None


# capture

def test_capture_puts_a_quest_item_into_the_lair_stash(registry, cfg):
    engine, hero = with_key(registry, cfg)
    apply(engine, hero, registry, cfg, ["capture"])
    holder = holder_of(engine)
    assert holder.kind == "location"
    assert holder.ref == "goblin_den"
    assert holder.location_id == "goblin_den"
    assert holder.label == "тайник логова"


def test_capture_stash_keeps_time_qty_and_price(registry, cfg):
    engine, hero = defeated(registry, cfg)
    custom(engine, "custom_1", "Ржавый ключ")
    add_item(hero, "custom_1", 3, cost_cp=700)
    engine.world.clock.advance(120)
    apply(engine, hero, registry, cfg, ["capture"])
    holder = holder_of(engine)
    assert (holder.since_s, holder.qty, holder.cost_cp) == (120, 3, 700)


def test_capture_clears_the_inventory_and_equipment(registry, cfg):
    engine, hero = with_key(registry, cfg)
    add_item(hero, "longsword", cost_cp=1500)
    hero.equipped.main_hand = "longsword"
    apply(engine, hero, registry, cfg, ["capture"])
    assert hero.inventory == []
    assert hero.equipped == Equipped()


def test_capture_uses_the_lair_from_params(registry, cfg):
    engine, hero = with_key(registry, cfg)
    engine.state.groups["goblins"].lair_location_id = None
    apply(engine, hero, registry, cfg, ["capture"], DefeatParams(lair_location_id="goblin_den"))
    assert holder_of(engine).ref == "goblin_den"


def test_capture_puts_a_plain_custom_item_into_the_lair_stash(registry, cfg):
    engine, hero = defeated(registry, cfg)
    custom(engine, "custom_1", "Ложка", quest=False)
    add_item(hero, "custom_1", 2, cost_cp=50)
    apply(engine, hero, registry, cfg, ["capture"])
    assert hero.inventory == []
    holder = holder_of(engine)
    assert holder.kind == "location"
    assert holder.ref == "goblin_den"
    assert holder.location_id == "goblin_den"
    assert holder.label == "тайник логова"
    assert (holder.qty, holder.cost_cp) == (2, 50)


def test_capture_of_srd_gear_makes_no_holder(registry, cfg):
    engine, hero = defeated(registry, cfg)
    add_item(hero, "spear", cost_cp=100)
    apply(engine, hero, registry, cfg, ["capture"])
    assert hero.inventory == []
    assert engine.world.custom_items == {}


def test_capture_holds_every_quest_item(registry, cfg):
    engine, hero = defeated(registry, cfg)
    custom(engine, "custom_1", "Ржавый ключ")
    custom(engine, "custom_2", "Записка")
    add_item(hero, "custom_1", cost_cp=700)
    add_item(hero, "custom_2", cost_cp=10)
    apply(engine, hero, registry, cfg, ["capture"])
    assert holder_of(engine, "custom_1").label == "тайник логова"
    assert holder_of(engine, "custom_2").label == "тайник логова"


def test_capture_and_rob_together_do_not_lose_the_item(registry, cfg):
    engine, hero = with_key(registry, cfg)
    apply(engine, hero, registry, cfg, ["rob", "capture"], DefeatParams(rob_items=1))
    assert holder_of(engine) is not None
    assert hero.inventory == []


# атомарность

def test_rejected_request_leaves_the_holder_alone(registry, cfg):
    engine, hero = with_key(registry, cfg)
    before = hero.model_dump_json() + engine.world.model_dump_json()
    result = apply(engine, hero, registry, cfg, ["rob", "torture"], DefeatParams(rob_items=1))
    assert result.report_tag == "invalid-defeat"
    assert holder_of(engine) is None
    assert hero.model_dump_json() + engine.world.model_dump_json() == before


def test_rejected_capture_without_a_lair_leaves_the_holder_alone(registry, cfg):
    engine, hero = with_key(registry, cfg, group=False)
    before = hero.model_dump_json() + engine.world.model_dump_json()
    result = apply(engine, hero, registry, cfg, ["capture"])
    assert result.report_tag == "invalid-defeat"
    assert hero.model_dump_json() + engine.world.model_dump_json() == before


# notes: лог отобранного

def test_rob_note_names_the_item_and_the_npc_holder(registry, cfg):
    engine, hero = with_key(registry, cfg)
    result = apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=1))
    label = engine.world.npcs["goblin_1"].name
    assert f"Отобрано: Ржавый ключ — у {label}" in result.notes


def test_rob_note_names_the_band_holder(registry, cfg):
    engine, hero = with_key(registry, cfg, named=False)
    result = apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=1))
    assert f"Отобрано: Ржавый ключ — у {holder_of(engine).label}" in result.notes


def test_rob_note_for_a_lost_item_says_lost_on_the_way(registry, cfg):
    engine, hero = with_key(registry, cfg, group=False)
    result = apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=1))
    assert "Отобрано: Ржавый ключ — у потеряно в пути" in result.notes


def test_rob_has_no_note_for_srd_items(registry, cfg):
    engine, hero = defeated(registry, cfg)
    add_item(hero, "spear", cost_cp=100)
    result = apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=1))
    assert result.notes == []


def test_rob_has_a_note_per_custom_item(registry, cfg):
    engine, hero = defeated(registry, cfg)
    custom(engine, "custom_1", "Ржавый ключ")
    custom(engine, "custom_2", "Записка")
    add_item(hero, "custom_1", cost_cp=9000)
    add_item(hero, "custom_2", cost_cp=8000)
    result = apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=2))
    assert len(result.notes) == 2
    assert any("Ржавый ключ" in n for n in result.notes)
    assert any("Записка" in n for n in result.notes)


def test_capture_note_for_a_quest_item_is_the_lair_stash(registry, cfg):
    engine, hero = with_key(registry, cfg)
    result = apply(engine, hero, registry, cfg, ["capture"])
    assert result.notes == ["Отобрано: Ржавый ключ — тайник логова"]


def test_capture_note_for_a_plain_custom_item_is_the_lair_stash(registry, cfg):
    engine, hero = defeated(registry, cfg)
    custom(engine, "custom_1", "Ложка", quest=False)
    add_item(hero, "custom_1", cost_cp=50)
    result = apply(engine, hero, registry, cfg, ["capture"])
    assert result.notes == ["Отобрано: Ложка — тайник логова"]


def test_capture_srd_gear_next_to_custom_is_cleared_without_notes(registry, cfg):
    engine, hero = defeated(registry, cfg)
    custom(engine, "custom_1", "Ложка", quest=False)
    add_item(hero, "custom_1", cost_cp=50)
    add_item(hero, "spear", cost_cp=100)
    result = apply(engine, hero, registry, cfg, ["capture"])
    assert hero.inventory == []
    assert list(engine.world.custom_items) == ["custom_1"]
    assert len(result.notes) == 1


def test_defeat_without_custom_items_has_empty_notes(registry, cfg):
    engine, hero = defeated(registry, cfg)
    result = apply(engine, hero, registry, cfg, ["capture"])
    assert result.notes == []


# robber_of / do_capture: края

def test_rob_when_the_leader_is_not_among_participants_is_lost_on_the_way(registry, cfg):
    engine, hero = with_key(registry, cfg, named=False)
    engine.state.participants = [p for p in engine.state.participants if p.ref != "goblin_1"]
    apply(engine, hero, registry, cfg, ["rob"], DefeatParams(rob_items=1))
    holder = holder_of(engine)
    assert holder.kind == "location"
    assert holder.ref == "vale"
    assert holder.label == "потеряно в пути"
    assert count_item(hero, "custom_1") == 0


def test_capture_merges_two_stacks_of_one_item_into_one_holder(registry, cfg):
    engine, hero = defeated(registry, cfg)
    custom(engine, "custom_1", "Ржавый ключ")
    add_item(hero, "custom_1", 1, cost_cp=700)
    add_item(hero, "custom_1", 2, cost_cp=900)
    apply(engine, hero, registry, cfg, ["capture"])
    holder = holder_of(engine)
    assert holder.qty == 3
    assert holder.cost_cp == 700


def test_capture_merges_stacks_of_a_plain_custom_item(registry, cfg):
    engine, hero = defeated(registry, cfg)
    custom(engine, "custom_1", "Ложка", quest=False)
    add_item(hero, "custom_1", 1, cost_cp=50)
    add_item(hero, "custom_1", 4, cost_cp=70)
    result = apply(engine, hero, registry, cfg, ["capture"])
    assert holder_of(engine).qty == 5
    assert len(result.notes) == 1
