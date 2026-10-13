# Р2 (R2-PLAN, В1б): правило затишья в narrator_rules.md -- по ключевым фразам.
from importlib import resources


def rules(name):
    return (resources.files("ai_dm.master") / "prompts" / name).read_text(encoding="utf-8")


def pace_section():
    text = rules("narrator_rules.md")
    start = text.index("## Темп")
    end = text.find("\n## ", start + 1)
    return text[start:] if end == -1 else text[start:end]


def test_narrator_rules_have_pace_section():
    assert "## Темп" in rules("narrator_rules.md")


def test_pace_section_mentions_breather():
    assert "передышк" in pace_section()


def test_pace_section_says_next_scene_without_new_threat():
    assert "без новой угрозы" in pace_section()


def test_pace_section_treats_nudge_as_background():
    assert "nudge" in pace_section()


def test_pace_section_is_short():
    body = pace_section().split("\n", 1)[1]
    assert len(body.strip()) <= 400


def test_pace_section_goes_after_nudge_and_before_plot_items():
    text = rules("narrator_rules.md")
    assert text.index("## Темп") > text.index("nudge")
    assert text.index("## Темп") < text.index("## Сюжетные предметы")


def test_narrator_rules_have_no_one_threat_at_a_time_rule():
    assert "одна угроза" not in rules("narrator_rules.md").lower()


def test_world_rules_are_untouched_by_pace():
    assert "передышк" not in rules("world_rules.md")
