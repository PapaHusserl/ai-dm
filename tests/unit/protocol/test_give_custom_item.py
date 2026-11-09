# Сюжетные предметы, партия А (CUSTOM-ITEMS-PLAN, разд. 2 и 5; В2, В4, В6): give_custom_item.
#   give_custom_item{name, description, qty, weight_lb, cost_cp, quest} (все поля обязательны для
#       модели; description "" и weight_lb 0 -- «не задано», внутри None;
#       вес в сейве -- CustomItem.weight_centilb (сотые доли фунта, int; None -- не задан)):
#     пустое имя / длиннее [custom_items].name_max (40) -> Invalid bad_name; qty < 1 -> Invalid
#     bad_amount; cost_cp < 0 -> Invalid; имя (casefold) совпало с предметом SRD -> rejected
#     с подсказкой give_item; имя совпало с кастомным (casefold, trim) -> тот же id, created=false,
#     seq и счётчик сцены не растут; иначе id custom_<seq+1>, запись в world.custom_items;
#     qty > give_item_max_qty -> clamped; cost_cp выше капа (5000 мм до 4 уровня, 50000 с 5-го) ->
#     clamped, цена = кап; новых за сцену не больше [custom_items].per_scene (15): 16-й ->
#     clamped, не выдан. Результат {item_id, qty, created}; запись инвентаря с cost_cp предмета.
#   Поле npc_id (ФД2 П2, решение 10): id торговца сцены -- вещь не герою, а в его trade.stock
#       (результат + npc_id; лог «Товар у <имя>: <вещь> xN»); не торговец -> Invalid not_merchant,
#       NPC не здесь -> Invalid npc_absent, нет такого -> Invalid unknown_npc;
#       лимит per_scene общий; выдача того же имени герою без npc_id ->
#       rejected «товар у <имя>»; покупка -- trade buy.
#   Следующий запрос того же хода видит новый предмет (ctx.registry обновлён).
#   Предмет с держателем (world.custom_items[id].holder): give_item <id> и give_custom_item с тем же
#       именем -> accepted, holder None, предмет у героя с ценой из holder.cost_cp, лог
#       «Возвращён предмет: ...».
import pytest
from protocol_kit import make_bundle, make_ctx, req

from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.protocol.hints import item_ids
from ai_dm.rules.custom_items import hand_over
from ai_dm.rules.inventory import count_item
from ai_dm.state.world import ItemHolder


def give(ctx, name="Ржавый ключ", **fields):
    data = {
        "description": "", "qty": 1, "weight_lb": 0, "cost_cp": 0, "quest": False,
    }
    data.update(fields)
    return apply(ctx, req("give_custom_item", name=name, **data))


def dump(ctx):
    return ctx.bundle.model_dump_json()


def catalog(ctx):
    return ctx.bundle.world.custom_items


def key_in(ctx):
    return catalog(ctx)["custom_1"]


def entries(ctx, item_id):
    return [(e.cost_cp, e.quality, e.qty) for e in ctx.hero.inventory if e.item_id == item_id]


def take(ctx, item_id="custom_1", qty=1, why="given", holder_npc_id="grakh"):
    # сюжетный предмет уходит к держателю: по умолчанию к Гракху (он в локации героя)
    return apply(
        ctx, req("take_item", item_id=item_id, qty=qty, why=why, holder_npc_id=holder_npc_id)
    )


def small(cfg, **fields):
    changed = cfg.model_copy(deep=True)
    for name, value in fields.items():
        setattr(changed.custom_items, name, value)
    return changed


def held_key(registry, cfg):
    # ключ выдан, отдан и ушёл к NPC (cost 700): так выглядит предмет после грабежа
    ctx = make_ctx(registry, cfg)
    give(ctx, quest=True, cost_cp=700)
    take(ctx, why="stolen")
    hand_over(
        ctx.bundle.world, "custom_1",
        ItemHolder(kind="npc", ref="aldric", label="Олдрик", location_id="vale", since_s=0,
                   qty=1, cost_cp=700),
    )
    return ctx


# создание

def test_new_item_is_accepted_with_the_first_id(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = give(ctx, description="Ключ от ворот", quest=True)
    assert isinstance(d, Decision)
    assert d.status == "accepted"
    assert d.report_tag is None
    assert d.result == {"item_id": "custom_1", "qty": 1, "created": True}


def test_new_item_lands_in_the_world_catalog(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx, description="Ключ от ворот", quest=True, cost_cp=300, weight_lb=0.5)
    item = key_in(ctx)
    assert item.id == "custom_1"
    assert item.name == "Ржавый ключ"
    assert item.description == "Ключ от ворот"
    assert item.quest is True
    assert item.cost_cp == 300
    assert item.weight_centilb == 50
    assert item.holder is None


def test_new_item_remembers_the_world_time(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.clock.advance(7200)
    give(ctx)
    assert key_in(ctx).created_s == 7200


def test_new_item_goes_to_the_hero_inventory(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx)
    assert count_item(ctx.hero, "custom_1") == 1


def test_item_entry_has_the_price_of_the_item(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx, cost_cp=700, qty=2)
    assert entries(ctx, "custom_1") == [(700, None, 2)]


def test_seq_grows_with_every_new_item(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx, "Ржавый ключ")
    d = give(ctx, "Записка")
    assert ctx.bundle.world.custom_item_seq == 2
    assert d.result["item_id"] == "custom_2"
    assert set(catalog(ctx)) == {"custom_1", "custom_2"}


def test_log_names_the_item_and_qty(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = give(ctx, qty=2)
    assert d.log == ["Получен предмет: Ржавый ключ x2"]


def test_new_item_raises_the_item_gained_event_and_flag(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx, qty=2)
    assert [(e.type, e.data) for e in ctx.events] == [
        ("item_gained", {"item": "custom_1", "qty": 2})
    ]
    assert ctx.bundle.world.flags["item_gained:custom_1"] is True


def test_item_ids_hint_lists_the_srd_only(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx)
    ids = item_ids(ctx.registry)
    assert "custom_1" not in ids
    assert "longsword" in ids
    assert "chain_mail" in ids
    assert "crowbar" in ids


def test_name_is_trimmed(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx, "  Ржавый ключ ")
    assert key_in(ctx).name == "Ржавый ключ"


def test_weight_is_stored_in_hundredths_of_a_pound(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx, weight_lb=0.1)
    assert key_in(ctx).weight_centilb == 10


def test_weight_is_rounded_to_hundredths(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx, weight_lb=1.236)
    assert key_in(ctx).weight_centilb == 124


def test_empty_weight_and_description_are_not_set(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx)
    assert key_in(ctx).weight_centilb is None
    assert key_in(ctx).description == ""


def test_quest_flag_defaults_to_false_when_not_asked(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx, quest=False)
    assert key_in(ctx).quest is False


def test_new_item_raises_the_scene_counter(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx)
    give(ctx, "Записка")
    assert ctx.scene.custom_created == 2


def test_new_item_works_without_a_scene(registry, cfg):
    ctx = make_ctx(registry, cfg, bundle=make_bundle(registry, with_scene=False))
    d = give(ctx)
    assert d.status == "accepted"
    assert count_item(ctx.hero, "custom_1") == 1


def test_context_registry_sees_the_new_item(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx)
    assert ctx.registry.has("item", "custom_1")
    assert registry.has("item", "custom_1") is False


# дедуп

def test_same_name_reuses_the_id(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx)
    d = give(ctx)
    assert d.status == "accepted"
    assert d.result == {"item_id": "custom_1", "qty": 1, "created": False}
    assert count_item(ctx.hero, "custom_1") == 2
    assert len(catalog(ctx)) == 1


def test_same_name_ignores_case_and_spaces(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx)
    d = give(ctx, "  ржавый КЛЮЧ  ")
    assert d.result["item_id"] == "custom_1"
    assert d.result["created"] is False
    assert count_item(ctx.hero, "custom_1") == 2


def test_same_name_does_not_grow_seq(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx)
    give(ctx)
    assert ctx.bundle.world.custom_item_seq == 1


def test_same_name_does_not_count_against_the_scene_limit(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx)
    give(ctx)
    assert ctx.scene.custom_created == 1


def test_same_name_keeps_the_stored_item_as_it_was(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx, description="Ключ от ворот", quest=False, cost_cp=300)
    give(ctx, description="другое", quest=True, cost_cp=900)
    item = key_in(ctx)
    assert (item.description, item.quest, item.cost_cp) == ("Ключ от ворот", False, 300)
    assert entries(ctx, "custom_1") == [(300, None, 2)]


def test_quest_item_already_in_hand_is_rejected(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx, quest=True)
    d = give(ctx, quest=True)
    assert isinstance(d, Decision)
    assert d.status == "rejected"
    assert "уже у героя" in d.signal_to_master


def test_quest_item_rejected_by_the_stored_flag_not_the_request(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx, quest=True)
    assert give(ctx, quest=False).status == "rejected"


def test_rejected_quest_reissue_changes_nothing(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx, quest=True)
    before = dump(ctx)
    give(ctx, quest=True, qty=3)
    assert dump(ctx) == before


def test_rejected_quest_reissue_keeps_the_scene_counter(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx, quest=True)
    give(ctx, quest=True)
    assert ctx.scene.custom_created == 1
    assert count_item(ctx.hero, "custom_1") == 1


def test_plain_custom_item_in_hand_gets_more_copies(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx, quest=False)
    d = give(ctx, quest=False, qty=2)
    assert d.status == "accepted"
    assert count_item(ctx.hero, "custom_1") == 3


def test_quest_item_not_in_hero_hands_can_be_given_again(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx, quest=True)
    take(ctx)
    d = give(ctx, quest=True)
    assert d.status == "accepted"
    assert count_item(ctx.hero, "custom_1") == 1


def test_different_names_are_different_items(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx, "Ключ")
    d = give(ctx, "Ключи")
    assert d.result["item_id"] == "custom_2"


# имя из SRD

@pytest.mark.parametrize("name", ["Лом", "лом", "  ЛОМ ", "Кинжал"])
def test_srd_name_is_rejected_with_a_give_item_hint(registry, cfg, name):
    ctx = make_ctx(registry, cfg)
    d = give(ctx, name)
    assert isinstance(d, Decision)
    assert d.status == "rejected"
    assert "give_item" in d.signal_to_master


def test_srd_name_hint_names_the_id(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = give(ctx, "Лом")
    assert "crowbar" in d.signal_to_master


def test_srd_name_changes_nothing(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    give(ctx, "Лом")
    assert dump(ctx) == before


def test_custom_name_equal_to_an_older_custom_is_not_an_srd_clash(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx)
    d = give(ctx)
    assert d.status == "accepted"


# невалидное

@pytest.mark.parametrize("name", ["", "   "])
def test_empty_name_is_invalid(registry, cfg, name):
    ctx = make_ctx(registry, cfg)
    d = give(ctx, name)
    assert isinstance(d, Invalid)
    assert d.code == "bad_name"


def test_name_of_40_chars_is_fine(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = give(ctx, "я" * 40)
    assert d.status == "accepted"


def test_name_of_41_chars_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = give(ctx, "я" * 41)
    assert isinstance(d, Invalid)
    assert d.code == "bad_name"


def test_name_limit_comes_from_the_config(registry, cfg):
    ctx = make_ctx(registry, small(cfg, name_max=5))
    assert give(ctx, "ключик").code == "bad_name"
    assert give(ctx, "ключи").status == "accepted"


def test_description_of_200_chars_is_fine(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = give(ctx, description="я" * 200)
    assert d.status == "accepted"
    assert len(key_in(ctx).description) == 200


def test_description_of_201_chars_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = give(ctx, description="я" * 201)
    assert isinstance(d, Invalid)
    assert d.code == "bad_description"


def test_description_limit_comes_from_the_config(registry, cfg):
    ctx = make_ctx(registry, small(cfg, description_max=3))
    assert give(ctx, description="four").code == "bad_description"
    assert give(ctx, description="one").status == "accepted"


def test_zero_qty_is_bad_amount(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = give(ctx, qty=0)
    assert isinstance(d, Invalid)
    assert d.code == "bad_amount"


def test_negative_qty_is_bad_amount(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert give(ctx, qty=-3).code == "bad_amount"


def test_negative_cost_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = give(ctx, cost_cp=-1)
    assert isinstance(d, Invalid)


def test_negative_weight_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = give(ctx, weight_lb=-1.0)
    assert isinstance(d, Invalid)


@pytest.mark.parametrize(
    "fields", [{"name": ""}, {"name": "я" * 41}, {"qty": 0}, {"cost_cp": -1}, {"weight_lb": -2.0},
            {"description": "я" * 201}]
)
def test_invalid_request_changes_nothing(registry, cfg, fields):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    d = give(ctx, **{"name": "Ржавый ключ", **fields})
    assert isinstance(d, Invalid)
    assert dump(ctx) == before


# клэмпы

def test_qty_over_the_limit_is_clamped(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = give(ctx, qty=500)
    assert d.status == "clamped"
    assert d.report_tag == "limit-exceeded"
    assert d.signal_to_master
    assert count_item(ctx.hero, "custom_1") == cfg.limits.give_item_max_qty == 20
    assert ctx.marks == ["limit-exceeded"]


def test_qty_exactly_at_the_limit_is_accepted(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = give(ctx, qty=20)
    assert d.status == "accepted"
    assert count_item(ctx.hero, "custom_1") == 20


def test_cost_over_the_level_cap_is_clamped_to_the_cap(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = give(ctx, cost_cp=5001)
    assert d.status == "clamped"
    assert d.report_tag == "limit-exceeded"
    assert d.signal_to_master
    assert key_in(ctx).cost_cp == 5000
    assert entries(ctx, "custom_1") == [(5000, None, 1)]
    assert ctx.marks == ["limit-exceeded"]


def test_clamped_cost_still_gives_the_item(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = give(ctx, cost_cp=999999)
    assert d.result == {"item_id": "custom_1", "qty": 1, "created": True}
    assert count_item(ctx.hero, "custom_1") == 1


def test_cost_exactly_at_the_cap_is_accepted(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = give(ctx, cost_cp=5000)
    assert d.status == "accepted"
    assert key_in(ctx).cost_cp == 5000


def test_cap_holds_up_to_the_fourth_level(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.hero.sheet.primary.level = 4
    give(ctx, cost_cp=6000)
    assert key_in(ctx).cost_cp == 5000


def test_cap_is_higher_from_the_fifth_level(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.hero.sheet.primary.level = 5
    d = give(ctx, cost_cp=6000)
    assert d.status == "accepted"
    assert key_in(ctx).cost_cp == 6000


def test_fifth_level_cost_over_its_cap_is_clamped(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.hero.sheet.primary.level = 5
    d = give(ctx, cost_cp=50001)
    assert d.status == "clamped"
    assert key_in(ctx).cost_cp == 50000


def test_fifth_level_cost_exactly_at_its_cap_is_accepted(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.hero.sheet.primary.level = 5
    d = give(ctx, cost_cp=50000)
    assert d.status == "accepted"


def test_cost_and_qty_clamps_both_show_in_the_signal(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = give(ctx, cost_cp=9999, qty=99)
    assert d.status == "clamped"
    assert count_item(ctx.hero, "custom_1") == 20
    assert key_in(ctx).cost_cp == 5000


# лимит за сцену

def fill_scene(ctx, count):
    for number in range(count):
        d = give(ctx, f"Вещь {number}")
        assert d.status == "accepted"


def test_default_scene_limit_is_fifteen(cfg):
    assert cfg.custom_items.per_scene == 15


def test_sixteenth_new_item_in_a_scene_is_clamped(registry, cfg):
    ctx = make_ctx(registry, cfg)
    fill_scene(ctx, 15)
    d = give(ctx, "Шестая вещь")
    assert d.status == "clamped"
    assert d.report_tag == "limit-exceeded"
    assert d.signal_to_master
    assert ctx.marks == ["limit-exceeded"]


def test_sixteenth_new_item_result_says_nothing_was_given(registry, cfg):
    ctx = make_ctx(registry, cfg)
    fill_scene(ctx, 15)
    d = give(ctx, "Шестая вещь")
    assert d.result == {"item_id": None, "qty": 0, "created": False}
    assert d.log == []
    assert all(e.data["item"] != "custom_16" for e in ctx.events)


def test_sixteenth_new_item_is_not_given_nor_created(registry, cfg):
    ctx = make_ctx(registry, cfg)
    fill_scene(ctx, 15)
    give(ctx, "Шестая вещь")
    assert len(catalog(ctx)) == 15
    assert ctx.bundle.world.custom_item_seq == 15
    assert ctx.scene.custom_created == 15
    assert [e.item_id for e in ctx.hero.inventory if e.item_id.startswith("custom_")] == [
        f"custom_{n}" for n in range(1, 16)
    ]


def test_fifteenth_new_item_in_a_scene_is_fine(registry, cfg):
    ctx = make_ctx(registry, cfg)
    fill_scene(ctx, 14)
    assert give(ctx, "Пятая вещь").status == "accepted"


def test_reissue_of_an_existing_item_ignores_the_scene_limit(registry, cfg):
    ctx = make_ctx(registry, cfg)
    fill_scene(ctx, 15)
    d = give(ctx, "Вещь 0")
    assert d.status == "accepted"
    assert d.result == {"item_id": "custom_1", "qty": 1, "created": False}
    assert ctx.scene.custom_created == 15


def test_scene_limit_comes_from_the_config(registry, cfg):
    ctx = make_ctx(registry, small(cfg, per_scene=2))
    fill_scene(ctx, 2)
    assert give(ctx, "Третья").status == "clamped"


def test_new_scene_starts_the_count_again(registry, cfg):
    ctx = make_ctx(registry, cfg)
    fill_scene(ctx, 15)
    ctx.scene.custom_created = 0
    assert give(ctx, "Шестая вещь").status == "accepted"


# один ход: выдать, потом забрать / выдать по id

def test_give_then_take_in_one_turn_are_both_accepted(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert give(ctx).status == "accepted"
    d = take(ctx)
    assert isinstance(d, Decision)
    assert d.status == "accepted"
    assert count_item(ctx.hero, "custom_1") == 0


def test_take_log_names_the_custom_item(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx)
    d = take(ctx)
    assert "Ржавый ключ" in d.log[0]


def test_take_does_not_remove_the_item_from_the_catalog(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx)
    take(ctx)
    assert "custom_1" in catalog(ctx)


def test_take_of_a_quest_item_is_allowed_for_any_reason(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx, quest=True, qty=4)
    for why in ("given", "lost", "stolen", "spent"):
        assert take(ctx, why=why).status == "accepted"
    assert count_item(ctx.hero, "custom_1") == 0


def test_take_when_the_hero_has_none_is_not_in_inventory(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx)
    take(ctx)
    before = dump(ctx)
    d = take(ctx)
    assert isinstance(d, Invalid)
    assert d.code == "not_in_inventory"
    assert dump(ctx) == before


def test_take_of_a_never_created_custom_id_is_unknown(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = take(ctx, "custom_7")
    assert isinstance(d, Invalid)
    assert d.code == "unknown_item"


def test_give_item_by_a_custom_id_is_accepted(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx)
    d = apply(ctx, req("give_item", item_id="custom_1", qty=2))
    assert d.status == "accepted"
    assert count_item(ctx.hero, "custom_1") == 3


def test_give_item_by_a_custom_id_uses_the_item_price(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx, cost_cp=300)
    take(ctx)
    apply(ctx, req("give_item", item_id="custom_1", qty=1))
    assert entries(ctx, "custom_1") == [(300, None, 1)]


def test_give_item_by_a_custom_id_log_has_the_name(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx)
    d = apply(ctx, req("give_item", item_id="custom_1", qty=1))
    assert "Ржавый ключ" in d.log[0]


def test_give_item_by_an_uncreated_custom_id_is_unknown(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("give_item", item_id="custom_1", qty=1))
    assert isinstance(d, Invalid)
    assert d.code == "unknown_item"


def test_give_item_hint_does_not_list_custom_ids(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx)
    d = apply(ctx, req("give_item", item_id="nope", qty=1))
    assert "custom_1" not in d.message


# возврат предмета с держателем

def test_give_item_returns_a_held_item(registry, cfg):
    ctx = held_key(registry, cfg)
    d = apply(ctx, req("give_item", item_id="custom_1", qty=1))
    assert d.status == "accepted"
    assert count_item(ctx.hero, "custom_1") == 1
    assert key_in(ctx).holder is None


def test_give_item_return_logs_the_recovery(registry, cfg):
    ctx = held_key(registry, cfg)
    d = apply(ctx, req("give_item", item_id="custom_1", qty=1))
    assert "Возвращён предмет" in d.log[0]
    assert "Ржавый ключ" in d.log[0]


def test_give_item_return_is_clamped_to_the_holder_qty(registry, cfg):
    ctx = held_key(registry, cfg)
    apply(ctx, req("give_item", item_id="custom_1", qty=3))
    assert entries(ctx, "custom_1") == [(700, None, 1)]


def test_give_item_return_gives_the_asked_qty_when_the_holder_has_enough(registry, cfg):
    ctx = held_key(registry, cfg)
    key_in(ctx).holder.qty = 3
    apply(ctx, req("give_item", item_id="custom_1", qty=3))
    assert entries(ctx, "custom_1") == [(700, None, 3)]


def test_give_item_return_log_shows_the_clamped_qty(registry, cfg):
    ctx = held_key(registry, cfg)
    key_in(ctx).holder.qty = 2
    d = apply(ctx, req("give_item", item_id="custom_1", qty=5))
    assert d.log == ["Возвращён предмет: Ржавый ключ x2"]
    assert d.result["qty"] == 2


def test_give_item_return_log_is_exact(registry, cfg):
    ctx = held_key(registry, cfg)
    d = apply(ctx, req("give_item", item_id="custom_1", qty=1))
    assert d.log == ["Возвращён предмет: Ржавый ключ x1"]


def test_give_item_return_keeps_the_price_of_the_holder(registry, cfg):
    ctx = held_key(registry, cfg)
    apply(ctx, req("give_item", item_id="custom_1", qty=1))
    assert entries(ctx, "custom_1") == [(700, None, 1)]


def test_give_item_without_a_holder_is_a_plain_receive(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx)
    d = apply(ctx, req("give_item", item_id="custom_1", qty=1))
    assert "Возвращён" not in d.log[0]


def test_give_item_return_touches_only_that_item(registry, cfg):
    ctx = held_key(registry, cfg)
    give(ctx, "Записка", quest=True)
    take(ctx, "custom_2", why="stolen")
    hand_over(
        ctx.bundle.world, "custom_2",
        ItemHolder(kind="band", ref="goblin_1", label="банда Клыка", since_s=0),
    )
    apply(ctx, req("give_item", item_id="custom_1", qty=1))
    assert catalog(ctx)["custom_2"].holder.ref == "goblin_1"


def test_same_name_give_custom_item_returns_a_held_item(registry, cfg):
    ctx = held_key(registry, cfg)
    d = give(ctx, quest=True)
    assert d.status == "accepted"
    assert d.result == {"item_id": "custom_1", "qty": 1, "created": False}
    assert key_in(ctx).holder is None
    assert count_item(ctx.hero, "custom_1") == 1


def test_same_name_return_does_not_make_a_duplicate(registry, cfg):
    ctx = held_key(registry, cfg)
    give(ctx, quest=True)
    assert len(catalog(ctx)) == 1
    assert ctx.bundle.world.custom_item_seq == 1


def test_same_name_return_does_not_grow_the_scene_counter(registry, cfg):
    ctx = held_key(registry, cfg)
    before = ctx.scene.custom_created
    give(ctx, quest=True)
    assert ctx.scene.custom_created == before


def test_same_name_return_logs_the_recovery_and_keeps_the_price(registry, cfg):
    ctx = held_key(registry, cfg)
    d = give(ctx, quest=True)
    assert d.log == ["Возвращён предмет: Ржавый ключ x1"]
    assert entries(ctx, "custom_1") == [(700, None, 1)]


def test_same_name_return_works_when_the_scene_limit_is_used_up(registry, cfg):
    ctx = held_key(registry, cfg)
    ctx.scene.custom_created = 15
    d = give(ctx, quest=True)
    assert d.status == "accepted"
    assert key_in(ctx).holder is None


# сводка доработок партии А

def test_explicit_zero_weight_is_not_set(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx, weight_lb=0)
    assert key_in(ctx).weight_centilb is None


def test_explicit_zero_float_weight_is_not_set(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx, weight_lb=0.0)
    assert key_in(ctx).weight_centilb is None


def test_give_custom_item_log_uses_a_latin_x(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = give(ctx, qty=2)
    assert d.log == ["Получен предмет: Ржавый ключ x2"]


def test_give_custom_item_return_log_uses_a_latin_x(registry, cfg):
    ctx = held_key(registry, cfg)
    d = give(ctx, quest=True)
    assert d.log == ["Возвращён предмет: Ржавый ключ x1"]


def test_same_name_takes_the_first_match(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx, cost_cp=300)
    catalog(ctx)["custom_2"] = catalog(ctx)["custom_1"].model_copy(
        update={"id": "custom_2", "cost_cp": 900},
    )
    d = give(ctx)
    assert d.result["item_id"] == "custom_1"
    assert entries(ctx, "custom_2") == []


def test_two_creations_in_one_turn_do_not_stack_overlays(registry, cfg):
    ctx = make_ctx(registry, cfg)
    give(ctx, "Ключ")
    give(ctx, "Записка")
    assert ctx.registry.has("item", "custom_1")
    assert ctx.registry.has("item", "custom_2")
    assert ctx.registry.overlay is None
    assert registry.overlay is ctx.registry


def test_give_item_return_result_has_item_and_qty(registry, cfg):
    ctx = held_key(registry, cfg)
    d = apply(ctx, req("give_item", item_id="custom_1", qty=1))
    assert d.result == {"item_id": "custom_1", "qty": 1}


def test_give_item_of_an_srd_item_is_a_plain_receive(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = count_item(ctx.hero, "spear")
    d = apply(ctx, req("give_item", item_id="spear", qty=1))
    assert d.status == "accepted"
    assert d.log[0].startswith("Получено:")
    assert count_item(ctx.hero, "spear") == before + 1


# npc_id: прилавок на лету (ФД2 П2, решение 10)

def make_merchant(ctx, npc_id="aldric"):
    d = apply(ctx, req("npc_update", npc_id=npc_id, trade_kind="general"))
    assert d.status == "accepted"
    ctx.bundle.world.npcs[npc_id].location_id = "vale"
    return ctx.bundle.world.npcs[npc_id]


def stock_give(ctx, name="Флакон духов", npc_id="aldric", **fields):
    return give(ctx, name, npc_id=npc_id, **fields)


def stock_of(ctx, npc_id="aldric"):
    return [(e.item_id, e.qty, e.cost_cp) for e in ctx.bundle.world.npcs[npc_id].trade.stock]


def test_npc_id_of_a_non_merchant_is_invalid_not_merchant(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.npcs["aldric"].location_id = "vale"
    before = dump(ctx)
    d = stock_give(ctx)
    assert isinstance(d, Invalid)
    assert d.code == "not_merchant"
    assert "trade_kind" in d.message
    assert dump(ctx) == before


def test_npc_id_of_an_absent_npc_is_invalid_npc_absent(registry, cfg):
    ctx = make_ctx(registry, cfg)
    make_merchant(ctx)
    ctx.bundle.world.npcs["aldric"].location_id = "goblin_den"
    before = dump(ctx)
    d = stock_give(ctx)
    assert isinstance(d, Invalid)
    assert d.code == "npc_absent"
    assert dump(ctx) == before


def test_unknown_npc_id_is_invalid_unknown_npc(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = stock_give(ctx, npc_id="nobody")
    assert isinstance(d, Invalid)
    assert d.code == "unknown_npc"


def test_npc_id_puts_the_item_into_the_merchant_stock(registry, cfg):
    ctx = make_ctx(registry, cfg)
    make_merchant(ctx)
    d = stock_give(ctx, qty=2, cost_cp=180)
    assert d.status == "accepted"
    assert stock_of(ctx) == [("custom_1", 2, 180)]
    assert d.result == {"item_id": "custom_1", "qty": 2, "created": True, "npc_id": "aldric"}


def test_npc_id_does_not_touch_the_hero_inventory(registry, cfg):
    ctx = make_ctx(registry, cfg)
    make_merchant(ctx)
    before = list(ctx.hero.inventory)
    stock_give(ctx, cost_cp=180)
    assert ctx.hero.inventory == before


def test_npc_id_creates_the_item_and_counts_it_in_the_scene(registry, cfg):
    ctx = make_ctx(registry, cfg)
    make_merchant(ctx)
    stock_give(ctx, cost_cp=180)
    assert key_in(ctx).name == "Флакон духов"
    assert ctx.scene.custom_created == 1


def test_npc_id_log_names_the_merchant_and_the_item(registry, cfg):
    ctx = make_ctx(registry, cfg)
    make_merchant(ctx)
    d = stock_give(ctx, qty=2, cost_cp=180)
    assert d.log == ["Товар у Олдрик: Флакон духов x2"]


def test_npc_id_item_counts_toward_the_scene_limit(registry, cfg):
    ctx = make_ctx(registry, cfg)
    make_merchant(ctx)
    fill_scene(ctx, 15)
    d = stock_give(ctx, "Шестнадцатая", cost_cp=180)
    assert d.status == "clamped"
    assert stock_of(ctx) == []


def test_item_in_stock_is_not_given_to_the_hero_by_name(registry, cfg):
    ctx = make_ctx(registry, cfg)
    make_merchant(ctx)
    stock_give(ctx, cost_cp=180)
    d = give(ctx, "Флакон духов", cost_cp=180)
    assert d.status == "rejected"
    assert "Олдрик" in d.signal_to_master
    assert count_item(ctx.hero, "custom_1") == 0


def test_trade_buy_moves_the_stock_item_to_the_hero_for_money(registry, cfg):
    ctx = make_ctx(registry, cfg)
    make_merchant(ctx)
    stock_give(ctx, cost_cp=180)
    ctx.hero.money_cp = 1000
    d = apply(ctx, req(
        "trade", npc_id="aldric", direction="buy", item_id="custom_1", qty=1, quality="any",
    ))
    assert d.status == "accepted"
    assert count_item(ctx.hero, "custom_1") == 1
    assert d.result["total_cp"] == 180
    assert ctx.hero.money_cp == 820
    assert sum(qty for _, qty, _ in stock_of(ctx)) == 0


def test_item_in_stock_is_not_given_to_the_hero_by_item_id(registry, cfg):
    ctx = make_ctx(registry, cfg)
    make_merchant(ctx)
    stock_give(ctx, cost_cp=180)
    ctx.hero.money_cp = 1000
    d = apply(ctx, req("give_item", item_id="custom_1", qty=1))
    assert d.status == "rejected"
    assert "Олдрик" in d.signal_to_master
    assert count_item(ctx.hero, "custom_1") == 0
    assert stock_of(ctx) == [("custom_1", 1, 180)]
    assert ctx.hero.money_cp == 1000


def test_catalog_item_in_stock_is_still_given_by_give_item(registry, cfg):
    from ai_dm.state.world import InventoryEntry

    ctx = make_ctx(registry, cfg)
    npc = make_merchant(ctx)
    npc.trade.stock.append(InventoryEntry(item_id="longsword", qty=1, cost_cp=1500))
    had = count_item(ctx.hero, "longsword")
    d = apply(ctx, req("give_item", item_id="longsword", qty=1))
    assert d.status == "accepted"
    assert count_item(ctx.hero, "longsword") == had + 1


def test_stock_item_with_zero_cost_is_invalid_bad_cost(registry, cfg):
    ctx = make_ctx(registry, cfg)
    make_merchant(ctx)
    before = dump(ctx)
    d = stock_give(ctx, cost_cp=0)
    assert isinstance(d, Invalid)
    assert d.code == "bad_cost"
    assert stock_of(ctx) == []
    assert dump(ctx) == before


def test_stock_item_with_cost_one_is_accepted(registry, cfg):
    ctx = make_ctx(registry, cfg)
    make_merchant(ctx)
    d = stock_give(ctx, cost_cp=1)
    assert d.status == "accepted"
    assert stock_of(ctx) == [("custom_1", 1, 1)]


def test_restock_of_an_existing_zero_cost_item_takes_the_new_price(registry, cfg):
    ctx = make_ctx(registry, cfg)
    make_merchant(ctx)
    give(ctx, "Флакон духов", cost_cp=0)
    d = stock_give(ctx, cost_cp=180)
    assert d.status == "accepted"
    assert stock_of(ctx) == [("custom_1", 1, 180)]


STOCKED_SIGNAL = (
    "Предмет 'Флакон духов' — товар у Олдрик: герою он достаётся только покупкой "
    "(trade buy), не выдачей."
)


def test_stocked_refusal_by_name_tells_the_name_and_trade_buy(registry, cfg):
    ctx = make_ctx(registry, cfg)
    make_merchant(ctx)
    stock_give(ctx, cost_cp=180)
    d = give(ctx, "Флакон духов", cost_cp=180)
    assert d.signal_to_master == STOCKED_SIGNAL


def test_stocked_refusal_by_item_id_tells_the_name_and_trade_buy(registry, cfg):
    ctx = make_ctx(registry, cfg)
    make_merchant(ctx)
    stock_give(ctx, cost_cp=180)
    d = apply(ctx, req("give_item", item_id="custom_1", qty=1))
    assert d.signal_to_master == STOCKED_SIGNAL


def test_stock_price_below_one_tells_the_minimum(registry, cfg):
    ctx = make_ctx(registry, cfg)
    make_merchant(ctx)
    d = stock_give(ctx, cost_cp=0)
    assert d.message == "цена товара на прилавке: не меньше 1 медной монеты"


def test_scene_limit_signal_tells_to_describe_by_fact(registry, cfg):
    ctx = make_ctx(registry, cfg)
    fill_scene(ctx, 15)
    d = give(ctx, "Шестнадцатая")
    assert d.signal_to_master == (
        "В этой сцене больше нельзя создавать новые предметы вне каталога: предмет не выдан, "
        "опиши по факту."
    )


def test_clamp_reasons_are_joined_with_semicolon(registry, cfg):
    ctx = make_ctx(registry, cfg)
    cap = cfg.custom_items.cost_cap_cp
    top = cfg.limits.give_item_max_qty
    d = give(ctx, cost_cp=cap + 1, qty=top + 1)
    assert d.reason == (
        f"цена {cap + 1} выше предела {cap}, взято {cap}; запрошено {top + 1}, выдано {top}"
    )


def test_stock_of_a_quest_item_the_hero_holds_is_rejected(registry, cfg):
    ctx = make_ctx(registry, cfg)
    make_merchant(ctx)
    give(ctx, "Флакон духов", quest=True, cost_cp=180)
    d = stock_give(ctx, cost_cp=180)
    assert d.status == "rejected"
    assert stock_of(ctx) == []


def test_stock_price_over_the_cap_is_clamped_to_the_cap(registry, cfg):
    ctx = make_ctx(registry, cfg)
    make_merchant(ctx)
    cap = cfg.custom_items.cost_cap_cp
    d = stock_give(ctx, cost_cp=cap + 1)
    assert d.status == "clamped"
    assert stock_of(ctx) == [("custom_1", 1, cap)]


def test_stock_qty_over_the_limit_is_clamped(registry, cfg):
    ctx = make_ctx(registry, cfg)
    make_merchant(ctx)
    top = cfg.limits.give_item_max_qty
    d = stock_give(ctx, cost_cp=180, qty=top + 1)
    assert d.status == "clamped"
    assert stock_of(ctx) == [("custom_1", top, 180)]


def test_npc_with_services_but_no_trade_is_not_merchant_and_not_listed(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.npcs["aldric"].location_id = "vale"
    ctx.bundle.world.npcs["aldric"].services = ["лечение"]
    d = stock_give(ctx, cost_cp=180)
    assert isinstance(d, Invalid)
    assert d.code == "not_merchant"
    assert "aldric" not in d.message
