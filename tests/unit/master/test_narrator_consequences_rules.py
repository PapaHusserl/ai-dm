# Шаг 270: рассказчик не отменяет и не смягчает последствий -- по ключевым фразам.
from importlib import resources


def rules(name):
    return (resources.files("ai_dm.master") / "prompts" / name).read_text(encoding="utf-8")


def who_does_what_section():
    text = rules("narrator_rules.md")
    start = text.index("## Кто что делает")
    end = text.find("\n## ", start + 1)
    return text[start:] if end == -1 else text[start:end]


def test_section_forbids_cancelling_and_softening_consequences():
    assert "Последствий не отменяй и не смягчай" in who_does_what_section()


def test_section_keeps_outcomes_as_engine_returned_them():
    assert "такими, какими их вернул движок" in who_does_what_section()


def test_section_forbids_turning_outcomes_in_heros_favour():
    assert "не выворачивай их в пользу героя" in who_does_what_section()


def test_consequences_phrase_goes_after_dont_argue_with_result():
    section = who_does_what_section()
    assert section.index("Последствий не отменяй") > section.index("не спорь с ним")


def test_rules_do_not_say_fact_is_born_before_players_question():
    # Сторож решения 5: в промпт эта часть придёт с шагом 262 или 264 -- тогда снять тест.
    assert "до вопроса игрока" not in rules("narrator_rules.md")
