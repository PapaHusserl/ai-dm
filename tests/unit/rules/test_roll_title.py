# Заголовок броска в строке лога: проверка навыка, характеристики, спасбросок;
# в бою -- без заголовка (строку подписывает лог боя).
import pytest
from test_roll_pipeline import ScriptedRng, make_request

from ai_dm.rules.roll_pipeline import RollRequest, roll, roll_title


def test_skill_check_title():
    r = RollRequest.model_construct(kind="check", ability="wis", skill="survival")
    assert roll_title(r) == "Выживание (Мдр)"


def test_ability_check_title():
    r = RollRequest.model_construct(kind="check", ability="str", skill=None)
    assert roll_title(r) == "Проверка Сил"


def test_skill_title_without_ability_has_no_brackets():
    r = RollRequest.model_construct(kind="check", ability=None, skill="stealth")
    assert roll_title(r) == "Скрытность"


def test_check_title_without_ability_is_plain_word():
    r = RollRequest.model_construct(kind="check", ability=None, skill=None)
    assert roll_title(r) == "Проверка"


def test_save_title():
    r = RollRequest.model_construct(kind="save", ability="con", skill=None)
    assert roll_title(r) == "Спасбросок Тел"


def test_combat_attack_has_no_title():
    r = RollRequest.model_construct(kind="attack", ability="dex", skill=None)
    assert roll_title(r) == ""


# слово позиции после названия через запятую (решение 15, вариант 1)

WORDS = [("controlled", "спокойно"), ("risky", "рискованно"), ("desperate", "отчаянно")]


@pytest.mark.parametrize("position, word", WORDS)
def test_skill_title_has_position_word(position, word):
    r = RollRequest.model_construct(
        kind="check", ability="dex", skill="stealth", tags={"position": position}
    )
    assert roll_title(r) == f"Скрытность (Лов), {word}"


def test_ability_check_title_has_position_word():
    r = RollRequest.model_construct(
        kind="check", ability="str", skill=None, tags={"position": "risky"}
    )
    assert roll_title(r) == "Проверка Сил, рискованно"


def test_save_title_has_position_word():
    r = RollRequest.model_construct(
        kind="save", ability="con", skill=None, tags={"position": "desperate"}
    )
    assert roll_title(r) == "Спасбросок Тел, отчаянно"


def test_title_without_position_tag_has_no_word():
    r = RollRequest.model_construct(kind="check", ability="dex", skill="stealth", tags={})
    assert roll_title(r) == "Скрытность (Лов)"


def test_combat_attack_with_other_tags_has_no_title():
    r = RollRequest.model_construct(
        kind="attack", ability="dex", skill=None, tags={"melee": True}
    )
    assert roll_title(r) == ""


@pytest.mark.parametrize("position, word", WORDS)
def test_roll_line_has_position_word(registry, position, word):
    request = make_request(
        "check", skill="stealth", ability="dex", dc=15, bonus=4, bonus_parts=[("Лов", 4)],
        tags={"position": position},
    )
    result = roll(request, ScriptedRng((20, 7)), registry)
    assert result.log.text == (
        f"Скрытность (Лов), {word}: d20 (7) + 4 Лов = 11 против СЛ 15 → провал"
    )


def test_roll_line_without_position_has_no_word(registry):
    request = make_request(
        "check", skill="stealth", ability="dex", dc=15, bonus=4, bonus_parts=[("Лов", 4)],
    )
    result = roll(request, ScriptedRng((20, 7)), registry)
    assert result.log.text == "Скрытность (Лов): d20 (7) + 4 Лов = 11 против СЛ 15 → провал"
