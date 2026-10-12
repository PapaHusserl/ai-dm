# К0-фикс-б (K0-FIX-PLAN, 7.6): правила про пол и местоимения -- по ключевым фразам и именам
# инструментов, не по точному тексту.
from importlib import resources


def rules(name):
    return (resources.files("ai_dm.master") / "prompts" / name).read_text(encoding="utf-8")


def tone_section():
    text = rules("narrator_rules.md")
    start = text.index("## Тон")
    end = text.find("\n## ", start + 1)
    return text[start:] if end == -1 else text[start:end]


def test_narrator_rules_mention_gender_and_pronouns():
    text = rules("narrator_rules.md")
    assert "gender" in text
    assert "pronouns" in text


def test_narrator_rules_say_to_decide_missing_gender_by_role():
    assert "по роли" in rules("narrator_rules.md")


def test_narrator_rules_say_to_fix_gender_with_npc_update():
    text = rules("narrator_rules.md")
    assert "npc_update" in text
    assert "`gender`" in text


def test_narrator_rules_say_new_npcs_get_gender_at_creation():
    text = rules("narrator_rules.md")
    assert "npc_create" in text
    assert "сразу" in text


def test_narrator_rules_say_gender_goes_before_the_name():
    assert "не по имени" in rules("narrator_rules.md")


def test_tone_section_ties_romance_to_gender():
    section = tone_section()
    assert "gender" in section


def test_hero_sheet_rules_mention_gender():
    text = rules("hero_sheet_rules.md")
    assert "gender" in text
    assert "pronouns" in text


def test_hero_sheet_rules_gender_comes_from_description_then_name():
    text = rules("hero_sheet_rules.md")
    assert "по описанию" in text
    assert "по имени" in text


def test_import_rules_mention_gender_with_none_for_unknown():
    text = rules("import_rules.md")
    assert "gender" in text
    assert "none" in text


def test_world_rules_mention_npc_create_with_gender():
    assert "gender" in rules("world_rules.md")


def test_narrator_rules_describe_gender_reset():
    text = rules("narrator_rules.md")
    assert "unset" in text
    assert '"-"' in text or "`-`" in text


def test_world_rules_describe_gender_reset():
    text = rules("world_rules.md")
    assert "unset" in text
    assert '"-"' in text
