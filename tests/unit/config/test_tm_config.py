# ТМ (docs/plan-tm.md, §1 п.6): [limits] gold_repeat_turns (int >= 0, по умолчанию 3; 0 -- выкл.)
# и long_rest_cooldown (строка Duration, по умолчанию "12h"; мусор -- ошибка валидации).
import pytest
from pydantic import ValidationError

from ai_dm.config.settings import LimitsConfig, load_rules_config


def limits(toml=None):
    return load_rules_config(toml).limits


def test_default_gold_repeat_turns_is_three():
    assert limits().gold_repeat_turns == 3


def test_default_long_rest_cooldown_is_twelve_hours():
    assert limits().long_rest_cooldown == "12h"


def test_override_gold_repeat_turns():
    assert limits("[limits]\ngold_repeat_turns = 5\n").gold_repeat_turns == 5


def test_gold_repeat_turns_zero_is_allowed():
    assert limits("[limits]\ngold_repeat_turns = 0\n").gold_repeat_turns == 0


def test_gold_repeat_turns_negative_is_rejected():
    with pytest.raises(ValidationError):
        limits("[limits]\ngold_repeat_turns = -1\n")


def test_gold_repeat_turns_text_is_rejected():
    with pytest.raises(ValidationError):
        limits('[limits]\ngold_repeat_turns = "три"\n')


@pytest.mark.parametrize("value", ["16h", "90m", "1d", "0h"])
def test_override_long_rest_cooldown(value):
    assert limits(f'[limits]\nlong_rest_cooldown = "{value}"\n').long_rest_cooldown == value


@pytest.mark.parametrize("value", ["", "12", "часов", "12 h", "1.5h", "-1h", "h12", "12H"])
def test_garbage_long_rest_cooldown_is_rejected(value):
    with pytest.raises(ValidationError):
        limits(f'[limits]\nlong_rest_cooldown = "{value}"\n')


def test_long_rest_cooldown_number_is_rejected():
    with pytest.raises(ValidationError):
        limits("[limits]\nlong_rest_cooldown = 12\n")


def test_other_limits_stay_with_override():
    result = limits("[limits]\ngold_repeat_turns = 1\n")
    assert result.give_item_max_qty == 20
    assert result.max_enemies == 6


def test_model_defaults_without_the_keys():
    data = load_rules_config().limits.model_dump()
    del data["gold_repeat_turns"]
    del data["long_rest_cooldown"]
    model = LimitsConfig.model_validate(data)
    assert (model.gold_repeat_turns, model.long_rest_cooldown) == (3, "12h")
