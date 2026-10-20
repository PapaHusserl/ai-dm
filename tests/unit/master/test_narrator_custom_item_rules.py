# Правила рассказчика (narrator_rules.md), партия Б сюжетных предметов
# (CUSTOM-ITEMS-PLAN, разд. 4, 5, 7): сюжетная вещь вне item_ids -- give_custom_item; вещь из
# item_ids -- только give_item; lost_items -- вещи героя у других (holder.label, location_id),
# не выдавать просто так и не дублировать; last_combat.gear -- что на телах; id предметов из
# инвентаря и lost_items разрешены в инструментах.
from importlib import resources


def rules_text():
    return (resources.files("ai_dm.master") / "prompts" / "narrator_rules.md").read_text(
        encoding="utf-8"
    )


def test_rules_send_story_things_to_give_custom_item():
    assert "`give_custom_item`" in rules_text()
    assert "которой нет в `item_ids`" in rules_text()


def test_rules_keep_srd_things_for_give_item():
    assert "Вещь из `item_ids` — только `give_item`" in rules_text()


def test_rules_mark_important_things_as_quest():
    assert "`quest: true`" in rules_text()


def test_rules_say_story_items_have_no_mechanics():
    assert "механики нет" in rules_text()


def test_rules_explain_lost_items_holder_and_place():
    text = rules_text()
    assert "`lost_items`" in text
    assert "`holder.label`" in text
    assert "`holder.location_id`" in text


def test_rules_forbid_duplicating_a_lost_item():
    assert "Не создавай дубль через `give_custom_item`" in rules_text()


def test_rules_return_lost_item_by_give_item_with_its_id():
    assert "`give_item` с id из `lost_items`" in rules_text()


def test_rules_point_at_gear_on_the_bodies():
    text = rules_text()
    assert "`last_combat.gear`" in text


def test_rules_allow_ids_from_inventory_and_lost_items_in_tools():
    assert "id предметов из инвентаря героя и `lost_items`" in rules_text()


# Фикс ЖП3 П3 (103): уничтоженная сюжетная вещь -- spent без держателя
def test_rules_send_destroyed_story_item_to_spent_without_holder():
    text = rules_text()
    assert "`take_item` `why: spent` без держателя" in text
    assert "вернуть её потом нельзя" in text


def test_rules_require_holder_for_lost_stolen_given():
    assert "`lost`/`stolen`/`given` — только с `holder_npc_id`" in rules_text()


# Фикс ЖП3 П3 (101): вещь от NPC -- только вызовом
def test_rules_forbid_npc_giving_an_item_by_text_only():
    line = next(
        ln for ln in rules_text().splitlines() if ln.startswith("- NPC дал, протянул")
    )
    assert "`give_item`" in line
    assert "`give_custom_item`" in line
    assert "одного текста мало" in line


# Фикс ЖП3 П3 (108): зелье от спутника или NPC -- give_item и use_item
def test_rules_use_item_paragraph_covers_potion_from_companion_or_npc():
    para = next(p for p in rules_text().split("\n\n") if p.startswith("`use_item` —"))
    assert "спутник или NPC" in para
    assert "`give_item`" in para
    assert "сразу `use_item`" in para


def test_use_item_description_mentions_being_given():
    from ai_dm.protocol.requests import UseItem

    assert "ему его дают" in UseItem.__doc__


def test_take_item_fields_describe_spent_without_holder():
    from ai_dm.protocol.requests import TakeItem

    fields = TakeItem.model_fields
    assert "вылит, сожжён, сломан, уничтожен" in fields["why"].description
    assert "при spent" in fields["holder_npc_id"].description
