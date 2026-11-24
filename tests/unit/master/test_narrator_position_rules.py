# Шаг 265, П1: рассказчик ставит позицию проверки (position) вместо stakes -- по ключевым фразам.
from importlib import resources


def rules(name):
    return (resources.files("ai_dm.master") / "prompts" / name).read_text(encoding="utf-8")


def section(title):
    text = rules("narrator_rules.md")
    start = text.index(f"## {title}")
    end = text.find("\n## ", start + 1)
    return text[start:] if end == -1 else text[start:end]


def test_checks_section_names_position_field():
    assert "position" in section("Проверки и сложность")


def test_checks_section_names_all_three_positions():
    checks = section("Проверки и сложность")
    for value in ("controlled", "risky", "desperate"):
        assert value in checks


def test_checks_section_says_risky_fail_costs_something():
    assert "провал чего-то стоит" in section("Проверки и сложность")


def test_checks_section_says_desperate_fail_may_cost_life_or_change_story():
    assert "провал может стоить жизни или изменить ход истории" in section("Проверки и сложность")


def test_checks_section_says_controlled_fail_threatens_nothing():
    assert "провал герою ничем не грозит" in section("Проверки и сложность")


def test_rules_do_not_mention_stakes():
    assert "stakes" not in rules("narrator_rules.md")


def test_choices_section_asks_to_mark_risky_variant():
    choices = section("Выбор игроку")
    assert "(рискованно)" in choices
    assert "(отчаянно)" in choices
