# ТВ (мини-партия #18, T5): правило offer_choices в narrator_rules.md -- 2–3 варианта (как в
# хендлере), список вариантов текстом без вызова -- ошибка.
from importlib import resources


def rules_text():
    return (resources.files("ai_dm.master") / "prompts" / "narrator_rules.md").read_text(
        encoding="utf-8"
    )


def choices_line():
    lines = [x for x in rules_text().splitlines() if "`offer_choices` обязателен" in x]
    assert len(lines) == 1
    return lines[0]


def test_choices_rule_says_two_to_three_variants():
    assert "2–3 коротких варианта" in choices_line()


def test_choices_rule_has_no_two_to_four():
    assert "2–4" not in rules_text()


def test_choices_rule_says_text_list_without_call_is_error():
    line = choices_line()
    assert "Список вариантов текстом" in line
    assert "без вызова `offer_choices`" in line
    assert "ошибка" in line
