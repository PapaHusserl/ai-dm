# М0 П2 (docs/plan-m0.md, «Тесты» П2): правила рассказчика о пути и перевозке — по ключевым словам,
# в обоих файлах правил (образец — test_narrator_rules_pace.py): цель сдвига часов `purpose`,
# место перевозки `destination`, слово «перевозка».
from importlib import resources

import pytest

FILES = ["narrator_rules.md", "narrator_rules_openai.md"]


def rules(name):
    return (resources.files("ai_dm.master") / "prompts" / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", FILES)
def test_rules_mention_advance_time_purpose(name):
    assert "purpose" in rules(name)


@pytest.mark.parametrize("name", FILES)
def test_rules_mention_service_destination(name):
    assert "destination" in rules(name)


@pytest.mark.parametrize("name", FILES)
def test_rules_mention_passage(name):
    assert "перевозк" in rules(name).lower()


# М0 П3б: правила о пути отрезками -- блок состояния `journey` и поле `left_s`

@pytest.mark.parametrize("name", FILES)
def test_rules_mention_journey_block(name):
    assert "journey" in rules(name)


@pytest.mark.parametrize("name", FILES)
def test_rules_mention_journey_left_s(name):
    assert "left_s" in rules(name)


# решение 117: travel_to места, где герой стоит в пути, снимает путь

@pytest.mark.parametrize("name", FILES)
def test_rules_say_travel_to_the_own_place_in_a_journey_ends_it(name):
    assert "снимает путь" in rules(name)


@pytest.mark.parametrize("name", FILES)
def test_rules_point_to_journey_to_for_going_on(name):
    assert "journey.to" in rules(name)
