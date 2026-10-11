# Ожидаемый API: ai_dm.core.rng
#   Rng(seed: int)                -- PCG32; сидирование pcg32_srandom_r(initstate=seed, initseq=54),
#                                    т.е. inc = (54 << 1) | 1 = 109
#   Rng.from_state(state: RngState) -> Rng
#   rng.state -> RngState         -- снимок (копия), не живая ссылка
#   rng.next_u32() -> int         -- сырой выход pcg32_random_r (XSH RR), каждый вызов draws += 1
#   rng.randbelow(n) -> int       -- [0, n), rejection sampling, n >= 1, иначе ValueError
#   rng.randint(a, b) -> int      -- включительно
#   rng.d(sides) -> int           -- 1..sides
#   rng.draws -> int              -- число вызовов next_u32
#   RngState(BaseModel): algo: str ("pcg32"), seed: int, state: int, inc: int, draws: int
import pytest
from pydantic import ValidationError

from ai_dm.core.rng import Rng, RngState

MULT = 6364136223846793005
MASK64 = (1 << 64) - 1


def reference_pcg32(initstate, initseq, count):
    # pcg32_srandom_r + pcg32_random_r из референсной реализации
    state = 0
    inc = ((initseq << 1) | 1) & MASK64
    state = (state * MULT + inc) & MASK64
    state = (state + initstate) & MASK64
    state = (state * MULT + inc) & MASK64
    out = []
    for _ in range(count):
        old = state
        state = (old * MULT + inc) & MASK64
        xorshifted = (((old >> 18) ^ old) >> 27) & 0xFFFFFFFF
        rot = old >> 59
        out.append(((xorshifted >> rot) | (xorshifted << ((-rot) & 31))) & 0xFFFFFFFF)
    return out


def test_first_values_match_reference_pcg32():
    rng = Rng(42)
    assert [rng.next_u32() for _ in range(5)] == reference_pcg32(42, 54, 5)


def test_initial_state_has_pcg32_algo_and_seed():
    state = Rng(42).state
    assert state.algo == "pcg32"
    assert state.seed == 42
    assert state.inc == 109
    assert state.draws == 0


def test_same_seed_same_sequence():
    a = Rng(7)
    b = Rng(7)
    assert [a.next_u32() for _ in range(50)] == [b.next_u32() for _ in range(50)]


def test_different_seeds_different_sequence():
    a = Rng(1)
    b = Rng(2)
    assert [a.next_u32() for _ in range(10)] != [b.next_u32() for _ in range(10)]


def test_from_state_repeats_sequence():
    rng = Rng(42)
    for _ in range(13):
        rng.next_u32()
    copy = Rng.from_state(rng.state)
    assert [rng.next_u32() for _ in range(20)] == [copy.next_u32() for _ in range(20)]


def test_state_survives_json_round_trip_mid_stream():
    rng = Rng(99)
    for _ in range(7):
        rng.d(20)
    restored = RngState.model_validate_json(rng.state.model_dump_json())
    copy = Rng.from_state(restored)
    assert [rng.d(20) for _ in range(30)] == [copy.d(20) for _ in range(30)]


def test_state_is_snapshot_not_live_reference():
    rng = Rng(5)
    snapshot = rng.state
    rng.next_u32()
    assert snapshot.draws == 0
    assert snapshot != rng.state


def test_draws_grows_with_every_u32():
    rng = Rng(1)
    rng.next_u32()
    rng.next_u32()
    assert rng.draws == 2
    assert rng.state.draws == 2


def test_draws_grows_on_d():
    rng = Rng(1)
    rng.d(20)
    assert rng.draws >= 1


def test_state_draws_restored():
    rng = Rng(1)
    for _ in range(4):
        rng.next_u32()
    assert Rng.from_state(rng.state).draws == 4


@pytest.mark.parametrize("n", [1, 2, 3, 5, 6, 7, 10, 20, 100, 1000, 2**31 + 1])
def test_randbelow_in_range(n):
    rng = Rng(123)
    for _ in range(2000):
        assert 0 <= rng.randbelow(n) < n


def test_randbelow_one_is_always_zero():
    rng = Rng(3)
    assert {rng.randbelow(1) for _ in range(100)} == {0}


def test_randbelow_zero_is_error():
    with pytest.raises(ValueError):
        Rng(1).randbelow(0)


def test_randint_inclusive_both_ends():
    rng = Rng(8)
    values = {rng.randint(3, 6) for _ in range(500)}
    assert values == {3, 4, 5, 6}


def test_randint_single_value():
    assert Rng(8).randint(4, 4) == 4


def test_d20_in_range():
    rng = Rng(11)
    for _ in range(2000):
        assert 1 <= rng.d(20) <= 20


def test_d20_distribution():
    rng = Rng(2024)
    counts = {face: 0 for face in range(1, 21)}
    for _ in range(100_000):
        counts[rng.d(20)] += 1
    for face, count in counts.items():
        assert abs(count - 5000) < 300, (face, count)


def test_first_values_match_official_pcg32_demo():
    rng = Rng(42)
    expected = [0xa15c02b7, 0x7b47f409, 0xba1d3330, 0x83d2f293, 0xbfa4784b, 0xcbed606e]
    assert [rng.next_u32() for _ in range(6)] == expected


class ScriptedRng(Rng):
    def __init__(self, values):
        super().__init__(1)
        self.values = list(values)
        self.calls = 0

    def next_u32(self):
        self.calls += 1
        return self.values.pop(0)


def test_randbelow_rejects_values_below_threshold():
    rng = ScriptedRng([0, 0, 5])
    assert rng.randbelow(3) == 2
    assert rng.calls == 3


def test_randbelow_above_u32_range_is_error():
    with pytest.raises(ValueError):
        Rng(1).randbelow(2**32 + 1)


def test_randbelow_full_u32_range_works():
    assert 0 <= Rng(1).randbelow(2**32) < 2**32


def test_rng_state_extra_field_is_error():
    with pytest.raises(ValidationError):
        RngState(algo="pcg32", seed=1, state=1, inc=109, draws=0, bogus=1)


def test_from_state_unknown_algo_is_error():
    state = RngState(algo="mt19937", seed=1, state=1, inc=109, draws=0)
    with pytest.raises(ValueError):
        Rng.from_state(state)
