# 212: правила рассказчика, раздел «Память»: сцены новее общей сводки, прошедшая в сценах нить
# сводки закрыта. Проверка по ключевым фразам, не по точному тексту.
from importlib import resources

FRASE = "новее `game_summary`"


def prompt_text(name):
    return (resources.files("ai_dm.master") / "prompts" / name).read_text(encoding="utf-8")


def rules_text():
    return prompt_text("narrator_rules.md")


def memory_section():
    text = rules_text()
    head = "## Память"
    start = text.index(head)
    nxt = text.find("\n## ", start + len(head))
    return text[start:] if nxt == -1 else text[start:nxt]


def test_phrase_is_in_rules_exactly_once():
    assert rules_text().count(FRASE) == 1


def test_memory_section_says_scenes_are_newer():
    assert "новее" in memory_section()


def test_memory_section_says_passed_thread_is_closed():
    assert "закрыта" in memory_section()


def test_phrase_goes_after_trust_state_and_before_npc_memory():
    text = memory_section()
    assert text.index("верь состоянию") < text.index(FRASE) < text.index("Память NPC о герое")


def test_rules_do_not_mention_summary_chapter_tool_field():
    assert rules_text().count("`game_summary_chapter`") == 0


def test_memory_section_is_short():
    body = memory_section().split("\n\n", 1)[1].strip()
    assert len(body) <= 600


def test_phrase_absent_from_other_prompts():
    for name in ("summarizer_rules.md", "world_rules.md", "narrator_rules_openai.md"):
        assert FRASE not in prompt_text(name), name
