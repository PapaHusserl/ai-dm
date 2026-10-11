# Ожидаемый API: ai_dm.core.dice
#   parse_dice(expr: str) -> DiceExpr   -- пробелы по краям допустимы; ошибка -> DiceParseError
#   DiceExpr(BaseModel): count: int, sides: int, modifier: int = 0,
#                        keep_highest: int | None = None, keep_lowest: int | None = None
#       "d20" -> count=1; "2d20kh1" -> keep_highest=1; "2d20kl1" -> keep_lowest=1
#   DiceParseError(ValueError)
#   roll_dice(expr: str | DiceExpr, rng: Rng) -> DiceRoll
#       кости бросаются по порядку через rng.d(sides)
#   DiceRoll(BaseModel): expr: str, rolls: list[int] (все выпавшие, в порядке броска),
#                        kept: list[int] (учтённые в сумме), modifier: int, total: int
#   roll_damage_dice(dice: str, bonus: int, rng, crit: bool = False) -> DiceRoll
#       кубики урона: rolls/kept -- грани, modifier == bonus, total == сумма + bonus; expr --
#       фактическое выражение без бонуса ("1d8"; при crit число кубиков удваивается: "2d8"),
#       бонус не удваивается
#   format_attack_log удалён (аудит 1 п. 2.12): строку атаки формирует rules/roll_pipeline
import pytest
from pydantic import ValidationError

from ai_dm.core.dice import (
    DiceExpr,
    DiceParseError,
    parse_dice,
    roll_damage_dice,
    roll_dice,
)
from ai_dm.core.rng import Rng


def test_parse_d20():
    e = parse_dice("d20")
    assert (e.count, e.sides, e.modifier) == (1, 20, 0)


def test_parse_2d6_plus_3():
    e = parse_dice("2d6+3")
    assert (e.count, e.sides, e.modifier) == (2, 6, 3)


def test_parse_1d8_minus_1():
    e = parse_dice("1d8-1")
    assert (e.count, e.sides, e.modifier) == (1, 8, -1)


def test_parse_keep_highest():
    e = parse_dice("2d20kh1")
    assert (e.count, e.sides, e.keep_highest) == (2, 20, 1)


def test_parse_keep_lowest():
    e = parse_dice("2d20kl1")
    assert e.keep_lowest == 1


@pytest.mark.parametrize("bad", ["2x6", "", "d0", "0d6", "d", "2d", "abc", "2d6+", "1d6kh3", "d-4"])
def test_parse_garbage_is_error(bad):
    with pytest.raises(DiceParseError):
        parse_dice(bad)


def test_dice_parse_error_is_value_error():
    assert issubclass(DiceParseError, ValueError)


def test_roll_is_deterministic_by_seed():
    a = roll_dice("2d6+3", Rng(5))
    b = roll_dice("2d6+3", Rng(5))
    assert a == b


def test_roll_uses_rng_d_in_order():
    r = roll_dice("2d6", Rng(5))
    ref = Rng(5)
    assert r.rolls == [ref.d(6), ref.d(6)]


def test_roll_total_is_sum_plus_modifier():
    r = roll_dice("3d6+2", Rng(9))
    assert len(r.rolls) == 3
    assert r.total == sum(r.rolls) + 2
    assert r.modifier == 2


def test_roll_negative_modifier():
    r = roll_dice("1d8-1", Rng(9))
    assert r.total == r.rolls[0] - 1


def test_roll_each_die_in_range():
    for seed in range(50):
        for v in roll_dice("4d8", Rng(seed)).rolls:
            assert 1 <= v <= 8


def test_roll_keep_highest():
    for seed in range(30):
        r = roll_dice("2d20kh1", Rng(seed))
        assert len(r.rolls) == 2
        assert r.kept == [max(r.rolls)]
        assert r.total == max(r.rolls)


def test_roll_keep_lowest():
    for seed in range(30):
        r = roll_dice("2d20kl1", Rng(seed))
        assert r.kept == [min(r.rolls)]


def test_roll_without_keep_keeps_all():
    r = roll_dice("2d6", Rng(1))
    assert sorted(r.kept) == sorted(r.rolls)


def test_roll_accepts_parsed_expr():
    assert roll_dice(parse_dice("d20"), Rng(3)) == roll_dice("d20", Rng(3))


def test_format_attack_log_is_removed_single_implementation_in_pipeline():
    # аудит 1 п. 2.12: строку атаки формирует конвейер бросков (rules/roll_pipeline)
    import ai_dm.core.dice as dice

    assert not hasattr(dice, "format_attack_log")


def test_keep_highest_and_keep_lowest_together_is_error():
    with pytest.raises(ValidationError):
        DiceExpr(count=2, sides=20, keep_highest=1, keep_lowest=1)


# кубики урона (B6)

class ScriptedRng(Rng):
    def __init__(self, *rolls):
        super().__init__(1)
        self.rolls = list(rolls)

    def randbelow(self, n):
        sides, face = self.rolls.pop(0)
        assert sides == n
        return face - 1


def test_roll_damage_dice_returns_faces_and_total_with_bonus():
    result = roll_damage_dice("1d8", 3, ScriptedRng((8, 5)))
    assert result.rolls == [5]
    assert result.kept == [5]
    assert result.modifier == 3
    assert result.total == 8


def test_roll_damage_dice_expr_has_no_bonus():
    assert roll_damage_dice("2d6", 3, ScriptedRng((6, 1), (6, 2))).expr == "2d6"


def test_roll_damage_dice_crit_doubles_dice_count():
    result = roll_damage_dice("1d8", 3, ScriptedRng((8, 3), (8, 7)), crit=True)
    assert result.rolls == [3, 7]
    assert result.expr == "2d8"


def test_roll_damage_dice_crit_does_not_double_bonus():
    result = roll_damage_dice("1d8", 3, ScriptedRng((8, 3), (8, 7)), crit=True)
    assert result.total == 3 + 7 + 3


def test_roll_damage_dice_crit_doubles_every_die_of_expression():
    rng = ScriptedRng((6, 1), (6, 2), (6, 3), (6, 4))
    assert roll_damage_dice("2d6", 0, rng, crit=True).rolls == [1, 2, 3, 4]


def test_roll_damage_dice_without_crit_rolls_only_given_dice():
    rng = ScriptedRng((8, 5))
    roll_damage_dice("1d8", 0, rng)
    assert rng.rolls == []


def test_roll_damage_dice_is_deterministic_by_seed():
    assert roll_damage_dice("2d6", 2, Rng(9)) == roll_damage_dice("2d6", 2, Rng(9))
