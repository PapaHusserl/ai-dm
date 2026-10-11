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
