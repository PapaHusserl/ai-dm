# Ожидаемый API: пакетный файл ai_dm/master/prompts/narrator_rules.md -- контракт в master_kit.py.
# Проверяем наличие ключевых правил по фразам и именам инструментов, не по точному тексту.
import re
from importlib import resources

import pytest

from ai_dm.protocol.requests import REQUEST_MODELS


def rules_text():
    return (resources.files("ai_dm.master") / "prompts" / "narrator_rules.md").read_text(
        encoding="utf-8"
    )


def test_rules_file_exists_and_is_not_empty():
    assert len(rules_text().strip()) > 500


def test_rules_are_in_russian():
    text = rules_text()
    cyrillic = len(re.findall("[а-яА-ЯёЁ]", text))
    latin = len(re.findall("[a-zA-Z]", text))
    assert cyrillic > latin


def test_rules_say_ai_narrates_and_code_counts():
    text = rules_text().lower()
    assert "рассказ" in text
    assert "движок" in text or "код" in text
    assert "бросок" in text or "броск" in text


def test_rules_say_narrate_after_tool_results():
    text = rules_text().lower()
    assert "результат" in text
    assert "повествован" in text


def test_rules_say_use_difficulty_categories_not_numbers():
    text = rules_text().lower()
    assert "категори" in text
    assert "сл" in text or "сложност" in text


def test_rules_mention_unsupported_action():
    assert "unsupported_action" in rules_text()


def test_rules_forbid_healing_without_mechanics():
    text = rules_text().lower()
    assert "леч" in text
    assert "механик" in text


@pytest.mark.parametrize("name", ["skill_check", "start_combat", "offer_choices"])
def test_rules_mention_key_tools(name):
    assert name in rules_text()


def test_rules_mention_only_known_tools():
    # всё, что похоже на имя инструмента в обратных кавычках, должно существовать в протоколе
    names = re.findall(r"`([a-z_]+)`", rules_text())
    tools = [n for n in names if "_" in n]
    fields = (
        "tool_use", "tool_result", "monster_ids", "item_ids", "player_input", "distance_m",
        "known_npcs", "location_id", "scene_npcs", "loot_individual", "npc_id",
        "can_pray", "god_id", "hero_hidden", "spell_id", "game_summary", "improvised_thrown",
        "lost_items", "gear_looted", "purse_cp", "sell_factor", "min_cp", "max_cp", "total_cp",
        "cost_cp", "price_cp", "item_id", "trade_kind", "holder_npc_id", "haggle_percent",
            "bad_circle", "prepared_swap", "recent_turns",
        "memory_kind", "memory_text", "memory_last",
        "goal_kind", "goal_target", "goal_text", "goal_status",
        "hit_dice",
    )
    unknown = [n for n in tools if n not in REQUEST_MODELS and n not in fields]
    assert unknown == []


# D8

@pytest.mark.parametrize(
    "name", ["player_action", "defeat_outcome", "npc_action", "rest", "monster_ids", "item_ids"]
)
def test_rules_mention_mode_tools_and_id_lists(name):
    assert name in rules_text()


def test_rules_say_player_input_is_json_field():
    text = rules_text()
    assert "player_input" in text
    assert "JSON" in text


def test_rules_do_not_forbid_naming_ids_in_tools():
    assert "Нельзя называть id" not in rules_text()


def test_rules_say_healing_only_via_rest():
    text = rules_text()
    assert "rest" in text
    assert "unsupported_action" in text


def test_rules_say_npc_death_needs_cause_goal_or_hazard():
    text = rules_text()
    assert "cause" in text
    assert "goal" in text
    assert "hazard" in text


def test_rules_say_to_mark_followers_by_npc_update():
    text = rules_text()
    assert "follows" in text


# Б0-П0: раздел «Тон» перечисляет все значения шкалы романтики (из Literal модели)

def tone_section():
    text = rules_text()
    start = text.index("## Тон")
    end = text.find("\n## ", start + 1)
    return text[start:] if end == -1 else text[start:end]


def test_rules_tone_section_lists_every_romance_value():
    from typing import get_args

    from ai_dm.state.world import Tone

    values = [v for v in get_args(Tone.model_fields["romance"].annotation) if v]
    assert len(values) == 4
    for value in values:
        assert value in tone_section()


def test_rules_tone_section_has_no_old_value_yes():
    assert "`есть`" not in tone_section()


# Б1а: hero_sheet_rules.md -- правила роли создания героя (режим hero_sheet)

def sheet_rules_text():
    path = resources.files("ai_dm.master") / "prompts" / "hero_sheet_rules.md"
    return path.read_text(encoding="utf-8")


def test_sheet_rules_name_the_tool():
    assert "hero_sheet" in sheet_rules_text()


@pytest.mark.parametrize("method", ["standard_array", "point_buy", "explicit"])
def test_sheet_rules_name_every_ability_method(method):
    assert method in sheet_rules_text()


def test_sheet_rules_name_class_kit():
    assert "class_kit" in sheet_rules_text()


def test_sheet_rules_are_in_russian():
    text = sheet_rules_text()
    assert len(re.findall("[а-яА-ЯёЁ]", text)) > len(re.findall("[a-zA-Z]", text))


@pytest.mark.parametrize("word", ["feedback", "previous", "taken_names", "opportunity", "motive"])
def test_sheet_rules_mention_input_fields(word):
    assert word in sheet_rules_text()


# Б1-фикс пп.3-4

def test_rules_say_text_next_to_tool_call_is_shown_as_narration():
    text = rules_text().lower()
    assert "рассужден" in text
    assert "думай молча" in text


def test_rules_say_thing_given_only_by_story_is_not_in_inventory():
    text = rules_text()
    assert "в инвентаре не появляется" in text


def test_rules_say_usable_item_is_not_a_trifle_and_use_give_custom_item():
    text = rules_text()
    index = text.index("не мелочь")
    assert "give_custom_item" in text[index : index + 400]


def test_rules_say_do_not_describe_use_of_missing_item():
    assert "её у него нет" in rules_text()


# Б3: import_rules.md -- правила роли import пака (режим pack_import)

def import_rules_text():
    path = resources.files("ai_dm.master") / "prompts" / "import_rules.md"
    return path.read_text(encoding="utf-8")


def test_import_rules_file_exists_and_names_the_tool():
    assert "pack" in import_rules_text()


def test_import_rules_are_in_russian():
    text = import_rules_text()
    assert len(re.findall("[а-яА-ЯёЁ]", text)) > len(re.findall("[a-zA-Z]", text))


# К0-фикс (38 а-в): effect импровизации, обязательный offer_choices, смысл scene_npcs

def section(title):
    text = rules_text()
    start = text.index(title)
    end = text.find("\n## ", start + 1)
    return text[start:] if end == -1 else text[start:end]


def test_rules_list_improvise_effects():
    assert "advantage, prone, extra_damage, push, disarm" in rules_text()


def test_rules_say_push_zone_is_adjacent():
    text = rules_text()
    at = text.index("push: zone")
    assert "соседняя" in text[at:at + 200]


def test_rules_forbid_free_text_effect():
    assert "своими словами движок не принимает" in rules_text()


def test_rules_choices_section_makes_offer_choices_mandatory():
    text = section("## Выбор игроку")
    assert "offer_choices" in text
    assert "обязателен" in text
    assert "вопрос" in text.lower()


def test_rules_choices_section_has_no_when_appropriate():
    assert "когда уместно" not in section("## Выбор игроку").lower()


def test_rules_explain_scene_npcs_and_leaving_npc():
    text = rules_text()
    at = text.index("`scene_npcs` — живые NPC")
    assert "не вводи" in text[at:at + 700]


def test_rules_say_staying_companion_gets_follows_none():
    assert 'follows: "none"' in rules_text()


def test_rules_explain_upcast_and_prepared_swap():
    text = rules_text()
    assert "prepared_swap" in text
    assert "bad_circle" in text
    assert "drop" in text and "take" in text


# B59 (В1): сцена пишется текстом ответа, offer_choices -- после текста сцены

def test_rules_say_scene_is_written_in_text_not_in_thinking():
    text = rules_text()
    assert "Сцену пиши текстом ответа" in text
    assert "размышлений не видит" in text


def test_rules_say_offer_choices_goes_in_last_answer_after_scene_text():
    text = rules_text()
    assert "`offer_choices` вызывай в последнем ответе, после результатов механики и текста сцены" in text


def test_rules_say_offer_choices_without_scene_is_not_end_of_turn():
    assert "не конец хода" in rules_text()


def test_offer_choices_tool_description_has_no_last_answer_phrase():
    # ЖП3 П1: фраза утекала в рассказ; порядок вызова описан в narrator_rules
    from ai_dm.protocol.schema import tool_set

    tools = {d["name"]: d for d in tool_set("explore")}
    description = tools["offer_choices"]["description"]
    assert "последнем ответе" not in description
    assert "два-три варианта" in description


# ТМ (#20): recent_turns -- прошлое, вызовы не повторять

def test_rules_say_recent_turns_are_past_and_calls_not_repeated():
    text = rules_text()
    at = text.index("`recent_turns`")
    assert "outcomes" in text[at:at + 400]
    assert "не повторяй" in text[at:at + 400]


# ТХ: раздел «Опыт и время» согласован с логами движка

def xp_time_section():
    text = rules_text()
    return text[text.index("## Опыт и время"):].split("\n## ", 1)[0]


def test_rules_xp_section_says_once_per_scene():
    assert "одного раза за сцену" in xp_time_section()


def test_rules_time_section_mentions_travel_to():
    assert "`advance_time.travel_to`" in xp_time_section()


@pytest.mark.parametrize("word", ["friendship", "joke", "shared_deed", "battle", "Мелочи", "notes"])
def test_rules_mention_warm_memory_kinds_and_trifles(word):
    assert word in rules_text()


def test_rules_say_master_does_not_change_notes():
    assert "`notes` ты не меняешь" in rules_text()


def test_rules_quote_xp_log_prefix():
    from ai_dm.protocol.handlers.resources import XP_LOG

    assert XP_LOG in xp_time_section()


def test_rules_quote_time_log_prefix_before_placeholder():
    from ai_dm.protocol.handlers.resources import TIME_LOG

    prefix = TIME_LOG.split("{}")[0]
    assert prefix and prefix in xp_time_section()
