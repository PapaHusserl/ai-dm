# Му-б (MU-PLAN B2): MiniaudioPlayer на поддельном miniaudio (fake_miniaudio.py, фикстура
# fake_miniaudio). Настоящей библиотеки и устройства нет. Кадр = 2 сэмпла (стерео, 44100 Гц).
# Допущения контракта: pull(n) отдаёт n * 2 сэмплов; громкость по умолчанию не проверяется --
# тесты задают set_volume(1.0) явно; затухающий слой закрывает поток (stream.close()).
import threading
from pathlib import Path

import pytest
from audio_kit import audio_config

from ai_dm.audio.miniaudio_player import MiniaudioPlayer

CHUNK = 4410
A = Path("/music/a.ogg")
B = Path("/music/b.ogg")
AMB = Path("/music/amb.ogg")
LONG = 10**7


@pytest.fixture
def fake(fake_miniaudio):
    fake_miniaudio.sounds.update({
        "a.ogg": (10000, LONG),
        "b.ogg": (20000, LONG),
        "amb.ogg": (8000, LONG),
        "short.ogg": (7, 100),
    })
    return fake_miniaudio


def started(fake, **cfg):
    player = MiniaudioPlayer(audio_config(**cfg))
    assert player.start() is None
    player.set_volume(1.0)
    return player, fake.devices[0]


def pull_seconds(device, seconds):
    # колбэки по 0.1 с; -> последний чанк
    chunk = None
    for _ in range(round(seconds * 10)):
        chunk = device.pull(CHUNK)
    return list(chunk)


def test_start_returns_none_and_opens_one_device(fake):
    player = MiniaudioPlayer(audio_config())
    assert player.start() is None
    assert len(fake.devices) == 1
    assert fake.devices[0].starts == 1


def test_start_passes_buffer_ms_from_config(fake):
    MiniaudioPlayer(audio_config(buffer_ms=123)).start()
    assert fake.devices[0].kwargs["buffersize_msec"] == 123


def test_pull_without_layers_is_silence_of_stereo_frames(fake):
    _, device = started(fake)
    assert list(device.pull(100)) == [0] * 200


def test_pull_length_is_two_samples_per_frame(fake):
    player, device = started(fake)
    player.set_layer("music", A, 0.0)
    assert len(device.pull(300)) == 600


def test_stream_is_opened_as_signed16_stereo_44100(fake):
    player, _ = started(fake)
    player.set_layer("music", A, 0.0)
    assert fake.stream_calls[0] == (str(A), fake.SampleFormat.SIGNED16, 2, 44100)


def test_fade_in_rises_from_zero(fake):
    player, device = started(fake)
    player.set_layer("music", A, 2.0)
    first = list(device.pull(CHUNK))
    assert 0 <= first[0] <= 500
    assert all(a <= b for a, b in zip(first, first[1:], strict=False))
    assert 0 < first[-1] < 1500


def test_fade_in_is_half_way_after_one_second(fake):
    player, device = started(fake)
    player.set_layer("music", A, 2.0)
    last = pull_seconds(device, 1.0)
    assert last[-1] == pytest.approx(5000, abs=500)


def test_fade_in_ends_at_stream_value_times_gain(fake):
    player, device = started(fake)
    player.set_layer("music", A, 2.0)
    pull_seconds(device, 2.5)
    assert list(device.pull(CHUNK)) == [10000] * (CHUNK * 2)


def test_zero_fade_is_full_level_at_once(fake):
    player, device = started(fake)
    player.set_layer("music", A, 0.0)
    assert list(device.pull(100)) == [10000] * 200


def test_crossfade_starts_from_old_track(fake):
    player, device = started(fake)
    player.set_layer("music", A, 0.0)
    pull_seconds(device, 1.0)
    player.set_layer("music", B, 2.0)
    first = list(device.pull(CHUNK))
    assert 9900 <= first[0] <= 10500
    assert first[-1] > first[0]
    assert first[-1] < 12000


def test_crossfade_mixes_old_and_new_in_the_middle(fake):
    player, device = started(fake)
    player.set_layer("music", A, 0.0)
    pull_seconds(device, 1.0)
    player.set_layer("music", B, 2.0)
    last = pull_seconds(device, 1.0)
    assert last[-1] == pytest.approx(15000, abs=1500)


def test_crossfade_ends_with_only_new_track(fake):
    player, device = started(fake)
    player.set_layer("music", A, 0.0)
    pull_seconds(device, 1.0)
    player.set_layer("music", B, 2.0)
    pull_seconds(device, 2.5)
    assert list(device.pull(CHUNK)) == [20000] * (CHUNK * 2)


def test_crossfade_closes_old_stream(fake):
    player, device = started(fake)
    player.set_layer("music", A, 0.0)
    pull_seconds(device, 1.0)
    player.set_layer("music", B, 2.0)
    pull_seconds(device, 2.5)
    assert fake.streams[0].closed


def test_fade_out_goes_to_silence(fake):
    player, device = started(fake)
    player.set_layer("music", A, 0.0)
    pull_seconds(device, 1.0)
    player.set_layer("music", None, 2.0)
    first = list(device.pull(CHUNK))
    assert 9000 <= first[0] <= 10000
    assert all(a >= b for a, b in zip(first, first[1:], strict=False))
    last = pull_seconds(device, 2.5)
    assert last == [0] * (CHUNK * 2)


def test_fade_out_is_half_way_after_one_second(fake):
    player, device = started(fake)
    player.set_layer("music", A, 0.0)
    pull_seconds(device, 1.0)
    player.set_layer("music", None, 2.0)
    last = pull_seconds(device, 1.0)
    assert last[-1] == pytest.approx(5000, abs=500)


def test_fade_out_closes_stream(fake):
    player, device = started(fake)
    player.set_layer("music", A, 0.0)
    pull_seconds(device, 1.0)
    player.set_layer("music", None, 2.0)
    pull_seconds(device, 2.5)
    assert fake.streams[0].closed


def test_clearing_empty_layer_is_harmless(fake):
    player, device = started(fake)
    player.set_layer("music", None, 2.0)
    assert list(device.pull(10)) == [0] * 20


def test_short_file_loops_without_gap(fake):
    player, device = started(fake)
    player.set_layer("music", Path("/music/short.ogg"), 0.0)
    assert list(device.pull(250)) == [7] * 500


def test_loop_reopens_stream_from_start(fake):
    player, device = started(fake)
    player.set_layer("music", Path("/music/short.ogg"), 0.0)
    device.pull(250)
    assert len(fake.stream_calls) >= 3


def test_loop_over_many_chunks_never_breaks(fake):
    player, device = started(fake)
    player.set_layer("music", Path("/music/short.ogg"), 0.0)
    for _ in range(10):
        assert list(device.pull(75)) == [7] * 150


def test_volume_scales_output(fake):
    player, device = started(fake)
    player.set_layer("music", A, 0.0)
    player.set_volume(0.25)
    assert list(device.pull(50)) == [2500] * 100


def test_volume_zero_is_silence(fake):
    player, device = started(fake)
    player.set_layer("music", A, 0.0)
    player.set_volume(0.0)
    assert list(device.pull(50)) == [0] * 100


def test_ambient_is_scaled_by_ambient_percent(fake):
    player, device = started(fake, ambient_percent=50)
    player.set_layer("ambient", AMB, 0.0)
    assert list(device.pull(50)) == [4000] * 100


def test_ambient_percent_follows_config(fake):
    player, device = started(fake, ambient_percent=25)
    player.set_layer("ambient", AMB, 0.0)
    assert list(device.pull(50)) == [2000] * 100


def test_music_is_not_scaled_by_ambient_percent(fake):
    player, device = started(fake, ambient_percent=50)
    player.set_layer("music", A, 0.0)
    assert list(device.pull(50)) == [10000] * 100


def test_music_and_ambient_are_summed(fake):
    player, device = started(fake, ambient_percent=50)
    player.set_layer("music", A, 0.0)
    player.set_layer("ambient", AMB, 0.0)
    assert list(device.pull(50)) == [14000] * 100


def test_volume_scales_both_layers(fake):
    player, device = started(fake, ambient_percent=50)
    player.set_layer("music", A, 0.0)
    player.set_layer("ambient", AMB, 0.0)
    player.set_volume(0.5)
    assert list(device.pull(50)) == [7000] * 100


def test_layers_fade_independently(fake):
    player, device = started(fake, ambient_percent=50)
    player.set_layer("music", A, 0.0)
    player.set_layer("ambient", AMB, 0.0)
    player.set_layer("ambient", None, 0.0)
    device.pull(2000)
    assert list(device.pull(50)) == [10000] * 100


def test_sum_is_clipped(fake):
    fake.sounds["loud.ogg"] = (30000, LONG)
    player, device = started(fake, ambient_percent=100)
    player.set_layer("music", Path("/m/loud.ogg"), 0.0)
    player.set_layer("ambient", Path("/m/loud.ogg"), 0.0)
    assert list(device.pull(10)) == [32767] * 20


def test_decode_error_gives_empty_layer_without_exception(fake):
    fake.broken.add("bad.ogg")
    player, device = started(fake)
    player.set_layer("music", Path("/music/bad.ogg"), 2.0)
    assert list(device.pull(100)) == [0] * 200


def test_decode_error_does_not_break_next_layer(fake):
    fake.broken.add("bad.ogg")
    player, device = started(fake)
    player.set_layer("music", Path("/music/bad.ogg"), 0.0)
    player.set_layer("music", A, 0.0)
    assert list(device.pull(10)) == [10000] * 20


def test_missing_sound_is_silence_not_crash(fake):
    player, device = started(fake)
    player.set_layer("music", Path("/music/unknown.ogg"), 0.0)
    assert list(device.pull(10)) == [0] * 20


def test_device_error_is_returned_as_text(fake):
    fake.device_error = fake.MiniaudioError("No backend")
    reason = MiniaudioPlayer(audio_config()).start()
    assert reason is not None
    assert "No backend" in reason


def test_os_error_on_device_is_returned_as_text(fake):
    fake.device_error = OSError("no sound card")
    reason = MiniaudioPlayer(audio_config()).start()
    assert reason is not None
    assert "no sound card" in reason


def test_stop_stops_and_closes_device_once(fake):
    player, device = started(fake)
    player.stop()
    assert (device.stops, device.closes) == (1, 1)


def test_second_stop_does_nothing(fake):
    player, device = started(fake)
    player.stop()
    player.stop()
    assert (device.stops, device.closes) == (1, 1)


def test_stop_without_start_is_harmless(fake):
    MiniaudioPlayer(audio_config()).stop()
    assert fake.devices == []


def test_set_layer_after_stop_is_noop(fake):
    player, _ = started(fake)
    player.stop()
    player.set_layer("music", A, 0.0)
    assert all(s.closed for s in fake.streams)


def test_set_volume_after_stop_does_not_raise(fake):
    player, _ = started(fake)
    player.stop()
    assert player.set_volume(0.5) is None


def test_set_layer_from_another_thread_while_pulling(fake):
    player, device = started(fake)
    errors = []

    def switch():
        try:
            for i in range(200):
                player.set_layer("music", A if i % 2 else B, 0.01)
                player.set_layer("ambient", AMB if i % 3 else None, 0.01)
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=switch)
    thread.start()
    try:
        for _ in range(200):
            assert len(device.pull(64)) == 128
    except Exception as exc:
        errors.append(exc)
    thread.join()
    assert errors == []


def test_streams_are_opened_with_positive_frames_to_read(fake):
    player, device = started(fake)
    player.set_layer("music", Path("/music/short.ogg"), 0.0)
    device.pull(250)
    assert len(fake.frames_to_read) >= 3
    assert all(isinstance(n, int) and n > 0 for n in fake.frames_to_read)


def test_loop_restarts_from_the_beginning_of_file(fake):
    fake.sounds["ramp.ogg"] = (None, 100)
    player, device = started(fake)
    player.set_layer("music", Path("/music/ramp.ogg"), 0.0)
    out = list(device.pull(250))
    assert out[::2] == [i % 100 for i in range(250)]


def test_loop_keeps_position_between_pulls(fake):
    fake.sounds["ramp.ogg"] = (None, 100)
    player, device = started(fake)
    player.set_layer("music", Path("/music/ramp.ogg"), 0.0)
    out = []
    for _ in range(5):
        out += list(device.pull(60))[::2]
    assert out == [i % 100 for i in range(300)]


def test_empty_file_gives_silence_and_does_not_hang(fake):
    fake.sounds["empty.ogg"] = (5, 0)
    player, device = started(fake)
    player.set_layer("music", Path("/music/empty.ogg"), 0.0)
    assert list(device.pull(10)) == [0] * 20


def test_fade_in_ends_exactly_inside_a_chunk(fake):
    player, device = started(fake)
    # 0.15 c = 6615 кадров: рампа кончается внутри второго чанка по 4410
    player.set_layer("music", A, 0.15)
    device.pull(CHUNK)
    second = list(device.pull(CHUNK))
    assert second[-1] == 10000
    assert max(second) == 10000


def test_decoder_failure_mid_play_gives_silence_and_survives(fake):
    player, device = started(fake)
    player.set_layer("music", A, 0.0)
    fake.streams[0].crash = True
    assert list(device.pull(10)) == [0] * 20
    assert list(device.pull(10)) == [0] * 20


def test_layer_recovers_after_decoder_failure(fake):
    player, device = started(fake)
    player.set_layer("music", A, 0.0)
    fake.streams[0].crash = fake.DecodeError("bad frame")
    device.pull(10)
    device.pull(10)
    player.set_layer("music", B, 0.0)
    assert list(device.pull(10)) == [20000] * 20


def test_device_error_without_text_gives_error_type_name(fake):
    fake.device_error = fake.MiniaudioError("")
    assert MiniaudioPlayer(audio_config()).start() == "MiniaudioError"


def test_stop_closes_playing_stream(fake):
    player, _ = started(fake)
    player.set_layer("music", A, 0.0)
    player.stop()
    assert fake.streams[0].closed


def test_stop_closes_fading_out_stream(fake):
    player, _ = started(fake)
    player.set_layer("music", A, 0.0)
    player.set_layer("music", B, 2.0)
    player.stop()
    assert fake.streams[0].closed
    assert fake.streams[1].closed


# ревью Му-б: сбой start, нулевой fade, блокировка lock, узкий except

def test_device_start_failure_closes_device_once(fake):
    fake.start_error = fake.MiniaudioError("start failed")
    reason = MiniaudioPlayer(audio_config()).start()
    assert "start failed" in reason
    assert fake.devices[0].closes == 1


def test_device_start_failure_leaves_player_stoppable(fake):
    fake.start_error = fake.MiniaudioError("start failed")
    player = MiniaudioPlayer(audio_config())
    player.start()
    player.stop()
    assert fake.devices[0].closes == 1


def test_zero_fade_out_does_not_cut_old_stream_at_once(fake):
    player, device = started(fake)
    player.set_layer("music", A, 0.0)
    device.pull(100)
    player.set_layer("music", None, 0.0)
    first = list(device.pull(10))
    assert 5000 < first[0] <= 10000
    assert first[-1] < first[0]


def test_zero_fade_out_still_ends_in_silence_quickly(fake):
    player, device = started(fake)
    player.set_layer("music", A, 0.0)
    device.pull(100)
    player.set_layer("music", None, 0.0)
    device.pull(2000)
    assert list(device.pull(100)) == [0] * 200


def test_zero_crossfade_old_track_fades_under_new_one(fake):
    player, device = started(fake)
    player.set_layer("music", A, 0.0)
    device.pull(100)
    player.set_layer("music", B, 0.0)
    assert list(device.pull(10))[0] > 20000
    device.pull(2000)
    assert list(device.pull(10)) == [20000] * 20


def test_pull_is_not_blocked_while_file_is_opening(fake):
    opening = threading.Event()
    release = threading.Event()

    def on_open(path):
        if path.endswith("b.ogg"):
            opening.set()
            release.wait(5)

    player, device = started(fake)
    player.set_layer("music", A, 0.0)
    fake.on_open = on_open
    switch = threading.Thread(target=lambda: player.set_layer("music", B, 0.0))
    switch.start()
    try:
        assert opening.wait(5)
        done = []
        puller = threading.Thread(target=lambda: done.append(len(device.pull(10))))
        puller.start()
        puller.join(2)
        assert done == [20]
    finally:
        release.set()
        switch.join(5)
    fake.on_open = None
    device.pull(2000)
    assert list(device.pull(10)) == [20000] * 20


def test_decode_error_mid_play_gives_silence_and_recovers(fake):
    player, device = started(fake)
    player.set_layer("music", A, 0.0)
    fake.streams[0].crash = fake.DecodeError("bad frame")
    assert list(device.pull(10)) == [0] * 20
    assert list(device.pull(10)) == [0] * 20
    player.set_layer("music", B, 0.0)
    assert list(device.pull(10)) == [20000] * 20


def test_stream_read_does_not_swallow_unexpected_errors(fake):
    from ai_dm.audio.miniaudio_player import Stream, open_stream

    stream = Stream(A, 1.0)
    stream.gen = open_stream(A, 64)
    fake.streams[0].crash = RuntimeError("bug")
    with pytest.raises(RuntimeError):
        stream.read(10)


def test_stream_read_turns_decode_error_into_dead_stream(fake):
    from ai_dm.audio.miniaudio_player import Stream, open_stream

    stream = Stream(A, 1.0)
    stream.gen = open_stream(A, 64)
    fake.streams[0].crash = fake.DecodeError("bad frame")
    assert list(stream.read(10)) == []
    assert stream.dead()


def test_unexpected_error_in_callback_gives_silence_not_exception(fake):
    player, device = started(fake)
    player.set_layer("music", A, 0.0)
    fake.streams[0].crash = RuntimeError("bug")
    assert list(device.pull(10)) == [0] * 20


def test_set_layer_after_stop_gives_no_sound(fake):
    player, device = started(fake)
    player.stop()
    player.set_layer("music", A, 0.0)
    assert list(device.pull(10)) == [0] * 20


def test_set_layer_with_unopenable_file_keeps_old_track_fading(fake):
    fake.broken.add("bad.ogg")
    player, device = started(fake)
    player.set_layer("music", A, 0.0)
    player.set_layer("music", Path("/music/bad.ogg"), 2.0)
    first = list(device.pull(CHUNK))
    assert 9000 < first[0] <= 10000
    assert pull_seconds(device, 2.5) == [0] * (CHUNK * 2)


def test_short_fade_in_starts_from_silence(fake):
    player, device = started(fake)
    player.set_layer("music", A, 0.5)
    first = list(device.pull(CHUNK))
    assert 0 <= first[0] <= 500


# решение 4 ревью: сбой одного потока не валит слой и соседей

def test_unexpected_error_in_current_closes_stream(fake):
    player, device = started(fake)
    player.set_layer("music", A, 0.0)
    fake.streams[0].crash = RuntimeError("bug")
    assert list(device.pull(10)) == [0] * 20
    assert fake.streams[0].closed


def test_unexpected_error_in_current_next_set_layer_plays(fake):
    player, device = started(fake)
    player.set_layer("music", A, 0.0)
    fake.streams[0].crash = RuntimeError("bug")
    device.pull(10)
    player.set_layer("music", B, 0.0)
    assert list(device.pull(10)) == [20000] * 20


def test_unexpected_error_in_old_stream_new_track_plays(fake):
    player, device = started(fake)
    player.set_layer("music", A, 0.0)
    player.set_layer("music", B, 2.0)
    fake.streams[0].crash = RuntimeError("bug")
    first = list(device.pull(CHUNK))
    assert 0 <= first[0] <= 500
    assert fake.streams[0].closed
    pull_seconds(device, 2.5)
    assert list(device.pull(10)) == [20000] * 20


def test_unexpected_error_in_old_stream_does_not_silence_current(fake):
    player, device = started(fake)
    player.set_layer("music", A, 0.0)
    player.set_layer("music", B, 0.0)
    fake.streams[0].crash = RuntimeError("bug")
    device.pull(2000)
    assert list(device.pull(10)) == [20000] * 20


def test_unexpected_error_in_music_does_not_touch_ambient(fake):
    player, device = started(fake, ambient_percent=50)
    player.set_layer("music", A, 0.0)
    player.set_layer("ambient", AMB, 0.0)
    fake.streams[0].crash = RuntimeError("bug")
    assert list(device.pull(10)) == [4000] * 20
    assert not fake.streams[1].closed
