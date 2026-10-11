# Правила рассказчика (narrator_rules.md), раздел «Торговля»: торговать только инструментом trade,
# торговец -- NPC с полем merchant, ключ trade в состоянии, обход через gold запрещён,
# сюжетное: выкуп у торговца и holder_npc_id в take_item.
from importlib import resources


def rules_text():
    return (resources.files("ai_dm.master") / "prompts" / "narrator_rules.md").read_text(
        encoding="utf-8"
    )


def test_rules_have_trade_section():
    assert "## Торговля" in rules_text()


def test_rules_send_deals_to_the_trade_tool():
    assert "только инструментом `trade`" in rules_text()


def test_rules_forbid_gold_give_item_workaround():
    assert "Нельзя заменять торговлю связкой `gold`" in rules_text()


def test_rules_say_price_is_the_engines():
    assert "цену считает движок" in rules_text()


def test_rules_tell_merchant_is_scene_npc_with_merchant_field():
    assert "NPC из `scene_npcs` с полем `merchant`" in rules_text()


def test_rules_describe_trade_state_key():
    assert "В ключе `trade` состояния" in rules_text()


def test_rules_send_to_npc_update_trade_kind():
    assert "`npc_update` с `trade_kind`" in rules_text()


def test_rules_forbid_key_npcs_as_merchants():
    assert "Ключевых NPC пака торговцами не делай" in rules_text()


def test_rules_tell_quest_item_is_redeemable():
    assert "`lost_items`" in rules_text().split("## Торговля")[1].split("\n## ")[0]


def test_rules_require_holder_npc_id_for_quest_items():
    assert "`holder_npc_id`, он обязателен" in rules_text()


def test_rules_describe_two_step_buying_with_list():
    text = rules_text().split("## Торговля")[1]
    assert "`direction` list" in text
    assert "`categories`" in text


def test_rules_send_haggling_to_the_haggle_tool():
    assert "только инструментом `haggle`" in rules_text()


def test_rules_forbid_changing_price_without_haggle():
    assert "без `haggle` цену не меняй" in rules_text()


def test_rules_say_roll_and_dc_are_the_engines():
    assert "Бросок и СЛ — движка" in rules_text().split("## Торговля")[1]


def test_rules_describe_haggle_percent_result():
    assert "`haggle_percent`" in rules_text().split("## Торговля")[1]


def test_rules_say_second_haggle_is_refused():
    assert "второй раз движок откажет" in rules_text()


def test_haggle_paragraph_is_inside_the_trade_section():
    section = rules_text().split("## Торговля")[1].split("\n## ")[0]
    assert "`haggle`" in section
