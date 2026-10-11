# Заголовок броска в строке лога: проверка навыка, характеристики, спасбросок;
# в бою -- без заголовка (строку подписывает лог боя).
from ai_dm.rules.roll_pipeline import RollRequest, roll_title


def test_skill_check_title():
    r = RollRequest.model_construct(kind="check", ability="wis", skill="survival")
    assert roll_title(r) == "Выживание (Мдр)"


def test_ability_check_title():
    r = RollRequest.model_construct(kind="check", ability="str", skill=None)
    assert roll_title(r) == "Проверка Сил"


def test_save_title():
    r = RollRequest.model_construct(kind="save", ability="con", skill=None)
    assert roll_title(r) == "Спасбросок Тел"


def test_combat_attack_has_no_title():
    r = RollRequest.model_construct(kind="attack", ability="dex", skill=None)
    assert roll_title(r) == ""
