# Му-б (MU-PLAN B2): чистые функции микшера ai_dm.audio.miniaudio_player -- mix_chunk и gain_ramp.
# miniaudio не нужен: функции чистые, модуль импортирует библиотеку лениво.
from array import array

import pytest

from ai_dm.audio.miniaudio_player import gain_ramp, mix_chunk, mix_total


def const(value, n):
    return array("h", [value] * n)


def test_mix_two_streams_with_gains():
    out = mix_chunk([(const(1000, 8), 1.0), (const(2000, 8), 0.5)], 8)
    assert list(out) == [2000] * 8


def test_mix_result_is_signed16_array_of_n():
    out = mix_chunk([(const(5, 6), 1.0)], 6)
    assert isinstance(out, array)
    assert out.typecode == "h"
    assert len(out) == 6


def test_mix_single_stream_with_gain():
    out = mix_chunk([(const(1000, 4), 0.25)], 4)
    assert list(out) == [250] * 4


def test_mix_zero_gain_is_silence():
    out = mix_chunk([(const(1000, 4), 0.0), (const(300, 4), 1.0)], 4)
    assert list(out) == [300] * 4


def test_mix_clips_positive():
    out = mix_chunk([(const(30000, 4), 1.0), (const(30000, 4), 1.0)], 4)
    assert list(out) == [32767] * 4


def test_mix_clips_negative():
    out = mix_chunk([(const(-30000, 4), 1.0), (const(-30000, 4), 1.0)], 4)
    assert list(out) == [out[0]] * 4
    assert out[0] in (-32768, -32767)


def test_mix_value_at_limit_is_not_changed():
    out = mix_chunk([(const(32767, 2), 1.0)], 2)
    assert list(out) == [32767, 32767]


def test_mix_empty_list_gives_zeros_of_n():
    out = mix_chunk([], 5)
    assert list(out) == [0] * 5


def test_mix_short_chunk_is_padded_with_zeros():
    out = mix_chunk([(const(1000, 3), 1.0)], 6)
    assert list(out) == [1000, 1000, 1000, 0, 0, 0]


def test_mix_short_chunk_does_not_hide_long_one():
    out = mix_chunk([(const(1000, 2), 1.0), (const(500, 4), 1.0)], 4)
    assert list(out) == [1500, 1500, 500, 500]


def test_mix_keeps_sample_order():
    out = mix_chunk([(array("h", [1, 2, 3, 4]), 1.0)], 4)
    assert list(out) == [1, 2, 3, 4]


def test_mix_mixes_signs():
    out = mix_chunk([(const(1000, 2), 1.0), (const(-400, 2), 1.0)], 2)
    assert list(out) == [600, 600]


def test_gain_ramp_up_is_monotonic_and_ends_at_target():
    ramp = gain_ramp(0.0, 1.0, 4)
    assert len(ramp) == 4
    assert ramp[-1] == pytest.approx(1.0)
    assert all(a < b for a, b in zip(ramp, ramp[1:], strict=False))
    assert all(0.0 <= g <= 1.0 for g in ramp)


def test_gain_ramp_down_ends_at_target():
    ramp = gain_ramp(1.0, 0.0, 4)
    assert len(ramp) == 4
    assert ramp[-1] == pytest.approx(0.0)
    assert all(a > b for a, b in zip(ramp, ramp[1:], strict=False))


def test_gain_ramp_is_linear():
    ramp = gain_ramp(0.0, 1.0, 4)
    steps = [b - a for a, b in zip(ramp, ramp[1:], strict=False)]
    assert steps == pytest.approx([steps[0]] * 3)


def test_gain_ramp_between_arbitrary_levels():
    ramp = gain_ramp(0.5, 0.25, 10)
    assert ramp[-1] == pytest.approx(0.25)
    assert all(0.25 <= g <= 0.5 for g in ramp)


def test_gain_ramp_single_step_is_target():
    assert gain_ramp(0.0, 0.7, 1) == [pytest.approx(0.7)]


def test_gain_ramp_zero_steps_is_empty():
    assert gain_ramp(0.0, 1.0, 0) == []


def test_mix_total_is_float_sum_without_rounding():
    total = mix_total([(const(3, 2), 0.5), (const(1, 2), 0.25)], 2)
    assert total == [1.75, 1.75]


def test_mix_total_pads_short_chunk_and_cuts_long_one():
    total = mix_total([(const(2, 5), 1.0), (const(4, 1), 1.0)], 3)
    assert total == [6.0, 2.0, 2.0]


def test_mix_total_empty_is_zeros():
    assert mix_total([], 3) == [0.0, 0.0, 0.0]
