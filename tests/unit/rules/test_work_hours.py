# М0 П4 (кабан-кволити, выжившие мутанты): rules/work_hours -- from_pair и hours_text.
import pytest

from ai_dm.rules.work_hours import from_pair, hours_text
from ai_dm.state.world import WorkHours


def test_from_pair_without_both_numbers_is_none():
    assert from_pair(None, None) is None


@pytest.mark.parametrize(("open_hour", "close_hour"), [(8, None), (None, 16)])
def test_from_pair_with_one_number_names_the_missing_pair(open_hour, close_hour):
    with pytest.raises(ValueError, match="нужны оба числа"):
        from_pair(open_hour, close_hour)


def test_from_pair_with_both_numbers_gives_work_hours():
    assert from_pair(8, 16) == WorkHours(open_hour=8, close_hour=16)


def test_hours_text_without_hours():
    assert hours_text(None) == "часы не заданы"


def test_hours_text_round_the_clock():
    assert hours_text(WorkHours(open_hour=0, close_hour=24)) == "круглосуточно"


def test_hours_text_range():
    assert hours_text(WorkHours(open_hour=8, close_hour=16)) == "8-16"
