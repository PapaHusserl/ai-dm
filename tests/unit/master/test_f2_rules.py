# 19ф Ф2 (docs/plan-19f.md п.1): правила рассказчика -- start_combat в том же ходу (раздел «Бой»),
# offer_choices на ходу, которым бой закончился (combat_narrate, «Выбор игроку»).
from importlib import resources


def rules_text():
    return (resources.files("ai_dm.master") / "prompts" / "narrator_rules.md").read_text(
        encoding="utf-8"
    )


def section(title):
    text = rules_text()
    start = text.index(f"## {title}")
    end = text.find("\n## ", start + 1)
    return text[start:] if end == -1 else text[start:end]


def line_with(marker):
    lines = [x for x in rules_text().splitlines() if marker in x]
    assert len(lines) == 1
    return lines[0]


def test_combat_section_asks_start_combat_in_same_turn():
    assert "в этом же ходу" in section("Бой")


def test_combat_section_says_text_without_call_is_error():
    text = section("Бой")
    assert "фраза «начинается бой» текстом без вызова — ошибка" in text


def test_combat_section_keeps_start_combat_rule():
    assert "Начинай бой через `start_combat`." in section("Бой")


def test_combat_narrate_paragraph_mentions_offer_choices_for_finished_combat():
    line = line_with("Рассказ о бое (режим combat_narrate)")
    assert "бой закончился" in line
    assert "`offer_choices`" in line


def test_choices_line_says_engine_gives_actions_while_combat_goes_on():
    line = line_with("`offer_choices` обязателен")
    assert "пока бой идёт" in line
    assert "на ходу, которым бой закончился, варианты снова за тобой" in line


def test_choices_line_has_no_old_in_combat_tail():
    assert "в бою список действий даёт движок" not in rules_text()
