# Му-б (MU-PLAN B2): подделка модуля miniaudio без нативного кода и устройства.
# Контракт: PlaybackDevice(..., buffersize_msec=...) -> start(generator) (генератор не запускает) /
# stop() / close();
# device.pull(n) -- один колбэк устройства: generator.send(n), вернёт массив сэмплов.
# stream_file(path, fmt, nchannels, rate, frames_to_read=...) -- поток по синтетическим данным
# SOUNDS[path] = (значение сэмпла, число кадров): .send(n) отдаёт до n кадров (n * nchannels
# сэмплов), в конце -- короткий остаток, потом StopIteration. DecodeError -- для имён из BROKEN.
import types
from array import array
from pathlib import Path

CHANNELS = 2
RATE = 44100


class MiniaudioError(Exception):
    pass


class DecodeError(MiniaudioError):
    pass


class FakeStream:
    # next() -- «прайминг» (ничего не отдаёт); send(n) -- n кадров
    def __init__(self, value, frames, nchannels):
        self.value = value
        self.left = frames
        self.nchannels = nchannels
        self.closed = False
        self.pos = 0
        self.crash = False

    def __iter__(self):
        return self

    def __next__(self):
        return array("h")

    def send(self, frames):
        if self.crash:
            raise self.crash if isinstance(self.crash, Exception) else RuntimeError("decoder broke")
        if self.closed or self.left <= 0:
            raise StopIteration
        count = min(frames, self.left)
        self.left -= count
        if self.value is None:
            # value None: сэмпл = номер кадра (для проверки позиции при зацикливании)
            ramp = [self.pos + i for i in range(count) for _ in range(self.nchannels)]
            self.pos += count
            return array("h", ramp)
        return array("h", [self.value] * (count * self.nchannels))

    def close(self):
        self.closed = True


class FakeDevice:
    def __init__(self, module, **kwargs):
        self.module = module
        self.kwargs = kwargs
        self.generator = None
        self.starts = 0
        self.stops = 0
        self.closes = 0
        module.devices.append(self)

    def start(self, generator):
        self.starts += 1
        if self.module.start_error is not None:
            raise self.module.start_error
        self.generator = generator
        # генератор уже запущен (next) тем, кто его создал -- как в README miniaudio

    def pull(self, frames):
        return self.generator.send(frames)

    def stop(self):
        self.stops += 1

    def close(self):
        self.closes += 1


def make_module(sounds=None, broken=(), device_error=None):
    module = types.ModuleType("miniaudio")
    module.sounds = {} if sounds is None else sounds
    module.broken = set(str(p) for p in broken)
    module.device_error = device_error
    module.devices = []
    module.streams = []
    module.stream_calls = []
    module.frames_to_read = []
    module.crash_all = False
    module.start_error = None
    module.on_open = None
    module.MiniaudioError = MiniaudioError
    module.DecodeError = DecodeError
    module.SampleFormat = types.SimpleNamespace(SIGNED16="s16")

    def playback_device(*args, **kwargs):
        if module.device_error is not None:
            raise module.device_error
        return FakeDevice(module, **kwargs)

    def stream_file(filename, output_format="s16", nchannels=None, sample_rate=None,
                    frames_to_read=None, **kwargs):
        key = str(filename)
        if module.on_open is not None:
            module.on_open(key)
        module.stream_calls.append((key, output_format, nchannels, sample_rate))
        module.frames_to_read.append(frames_to_read)
        if key in module.broken or Path(key).name in module.broken:
            raise DecodeError(f"cannot decode {key}")
        found = module.sounds.get(key) or module.sounds.get(Path(key).name)
        if found is None:
            raise DecodeError(f"no such file {key}")
        value, frames = found
        stream = FakeStream(value, frames, nchannels or CHANNELS)
        stream.crash = module.crash_all
        module.streams.append(stream)
        return stream

    module.PlaybackDevice = playback_device
    module.stream_file = stream_file
    return module
