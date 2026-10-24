# Правила рассказчика (narrator_rules.md), раздел «Журнал знаний и настроение сцены» (Ж3):
# блок knowledge в состоянии, запрос knowledge_note (source told + from_ref, до 160 знаков, не
# дублировать), встречи/места/бои/секреты/милость богов пишет движок, нераскрытый секрет не
# записывать (reveal_secret), scene_mood romance/none, метка слетает с новой сценой.
from importlib import resources


def rules_text():
    return (resources.files("ai_dm.master") / "prompts" / "narrator_rules.md").read_text(
        encoding="utf-8"
    )


def section():
    text = rules_text()
    head = "## Журнал знаний и настроение сцены"
    start = text.index(head)
    nxt = text.find("\n## ", start + len(head))
    return text[start:] if nxt == -1 else text[start:nxt]


def test_rules_have_knowledge_section():
    assert "## Журнал знаний и настроение сцены" in rules_text()


def test_section_describes_knowledge_state_block():
    assert "`knowledge`" in section()


def test_section_names_both_requests():
    text = section()
    assert "`knowledge_note`" in text
    assert "`scene_mood`" in text


def test_section_explains_told_with_from_ref():
    text = section()
    assert "`source: told`" in text
    assert "from_ref" in text


def test_section_sets_text_limit_160():
    assert "160" in section()


def test_section_forbids_duplicates():
    assert "не дублируй" in section()


def test_section_says_engine_writes_meetings_and_fights():
    text = section()
    assert "Встречи" in text
    assert "записывает движок сам" in text


def test_section_forbids_unrevealed_secret_note():
    text = section()
    assert "Секрет, который ещё не раскрыт, не записывай" in text
    assert "`reveal_secret`" in text


def test_section_describes_romance_and_none():
    text = section()
    assert "`romance`" in text
    assert "`none`" in text


def test_section_says_mood_drops_with_new_scene_on_place_or_npc_change():
    phrase = "С новой сценой метка слетает, если сменились место или кто-то из NPC сцены ушёл"
    assert phrase in section()


def test_section_says_mood_stays_with_same_place_and_npcs():
    assert "при тех же месте и NPC остаётся" in section()


def test_section_limits_requests_to_non_combat():
    assert "только вне боя" in section()


def test_section_is_not_bloated():
    # ≈ 1 300 знаков по плану; верхняя граница с запасом
    assert len(section()) < 2000
