# Единственный модуль с miniaudio. Библиотека импортируется внутри функций: без extra audio
# модуль всё равно импортируется, а start() отвечает причиной отказа.
import threading
from array import array

RATE = 44100
CHANNELS = 2
SAMPLE_MIN = -32768
SAMPLE_MAX = 32767


def gain_ramp(start, end, steps):
    # steps значений гейна от start (не включая) до end (включая)
    return [start + (end - start) * (i + 1) / steps for i in range(steps)]


def mix_total(parts, n):
    # parts: [(сэмплы, гейн)]; сумма без округления, ровно n значений (короткий чанк -- нули)
    total = [0.0] * n
    for chunk, gain in parts:
        for i, value in enumerate(chunk[:n]):
            total[i] += value * gain
    return total


def mix_chunk(parts, n):
    # n -- число сэмплов (кадры x 2); сумма с клиппингом в 16 бит;
    # округление один раз в конце (рампа не дребезжит)
    total = mix_total(parts, n)
    return array("h", (max(SAMPLE_MIN, min(SAMPLE_MAX, int(value))) for value in total))


def open_stream(path, frames):
    import miniaudio

    try:
        return miniaudio.stream_file(
            str(path), miniaudio.SampleFormat.SIGNED16, CHANNELS, RATE, frames_to_read=frames
        )
    except (miniaudio.DecodeError, miniaudio.MiniaudioError, OSError):
        return None


class Stream:
    # один файл по кругу с линейной рампой гейна к target за fade_frames кадров
    def __init__(self, path, gain):
        self.path = path
        self.gain = gain
        self.target = gain
        self.left = 0
        self.step = 0.0
        self.gen = None

    def fade(self, target, fade_frames):
        self.target = target
        self.left = fade_frames
        if fade_frames == 0:
            self.gain = target
        else:
            self.step = (target - self.gain) / fade_frames

    def read(self, frames):
        # frames кадров с зацикливанием; меньше -- только если файл не открылся.
        # Шов лупа: файл переоткрывается прямо в колбэке (известное ограничение)
        import miniaudio

        out = array("h")
        restarts = 0
        while len(out) < frames * CHANNELS and restarts < 2 and self.gen is not None:
            try:
                part = self.gen.send(frames - len(out) // CHANNELS)
            except StopIteration:
                part = []
            except (miniaudio.DecodeError, miniaudio.MiniaudioError):
                self.gen = None
                break
            if len(part) == 0:
                restarts += 1
                self.gen = open_stream(self.path, frames)
            else:
                out.extend(part)
                restarts = 0
        return out

    def chunk(self, frames):
        data = self.read(frames)
        if self.left == 0:
            if self.gain == 1.0:
                return data
            return [value * self.gain for value in data]
        k = min(frames, self.left)
        end = self.target if k == self.left else self.gain + self.step * k
        gains = gain_ramp(self.gain, end, k) + [end] * (frames - k)
        self.gain = end
        self.left -= k
        return [value * gains[i // CHANNELS] for i, value in enumerate(data)]

    def dead(self):
        return self.gen is None or (self.target == 0 and self.left == 0)

    def close(self):
        if self.gen is not None:
            self.gen.close()
            self.gen = None


class Layer:
    # слой (музыка или эмбиент): текущий поток и уходящие, которые затухают
    def __init__(self, name):
        self.name = name
        self.current = None
        self.old = []

    def make_stream(self, path, fade_s):
        # открывает файл; зовётся вне lock плеера. None -- пути нет или файл не открылся
        if path is None:
            return None
        stream = Stream(path, 0.0 if fade_s > 0 else 1.0)
        stream.gen = open_stream(path, 2048)
        if stream.gen is None:
            return None
        stream.fade(1.0, int(fade_s * RATE))
        return stream

    def set(self, stream, fade_s):
        # stream -- готовый поток из make_stream или None; здесь только перестановка ссылок
        if self.current is not None:
            # даже при нулевом кроссфейде уходящий гаснет ~10 мс, иначе щелчок
            self.current.fade(0.0, max(int(fade_s * RATE), RATE // 100))
            self.old.append(self.current)
            self.current = None
        self.current = stream
        self.drop_dead()

    def drop_dead(self):
        alive = []
        for stream in self.old:
            if stream.dead():
                stream.close()
            else:
                alive.append(stream)
        self.old = alive

    def chunk(self, frames):
        # смесь потоков слоя или None, если слой пуст
        streams = self.old + ([self.current] if self.current is not None else [])
        if not streams:
            return None
        parts = []
        for stream in streams:
            try:
                parts.append((stream.chunk(frames), 1.0))
            except Exception:
                # неожиданный сбой потока: закрыть, ниже он вылетает из слоя; остальные играют
                stream.close()
        if self.current is not None and self.current.gen is None:
            # поток сломан -- слой молчит до следующего set
            self.current = None
        self.drop_dead()
        return mix_total(parts, frames * CHANNELS)

    def close(self):
        for stream in self.old + ([self.current] if self.current is not None else []):
            stream.close()
        self.old = []
        self.current = None


class MiniaudioPlayer:
    def __init__(self, cfg):
        self.cfg = cfg
        self.lock = threading.Lock()
        self.layers = {"music": Layer("music"), "ambient": Layer("ambient")}
        self.gain = (cfg.volume / 100) ** 2
        self.device = None
        self.stopped = False

    def start(self):
        # None -- играет; иначе причина отказа (нет библиотеки, нет устройства)
        try:
            import miniaudio

            device = miniaudio.PlaybackDevice(buffersize_msec=self.cfg.buffer_ms)
            generator = self.generator()
            next(generator)
            try:
                device.start(generator)
            except (miniaudio.MiniaudioError, OSError):
                device.close()
                raise
        except ImportError:
            from ai_dm.audio.control import MISSING

            return MISSING
        except (miniaudio.MiniaudioError, OSError) as error:
            return str(error) or type(error).__name__
        self.device = device
        return None

    def generator(self):
        # колбэк устройства: первый next() -- запуск, дальше send(кадров) -> чанк
        frames = yield array("h")
        while True:
            try:
                chunk = self.render(frames)
            except Exception:
                # колбэк исключения не переживает: при сбое -- тишина
                chunk = array("h", [0] * (frames * CHANNELS))
            frames = yield chunk

    def render(self, frames):
        with self.lock:
            parts = []
            music = self.layers["music"].chunk(frames)
            if music is not None:
                parts.append((music, self.gain))
            ambient = self.layers["ambient"].chunk(frames)
            if ambient is not None:
                parts.append((ambient, self.gain * self.cfg.ambient_percent / 100))
            return mix_chunk(parts, frames * CHANNELS)

    def set_layer(self, layer, path, fade_s):
        # файл открываем вне lock: колбэк не должен ждать декодера
        stream = self.layers[layer].make_stream(path, fade_s)
        with self.lock:
            if self.stopped:
                if stream is not None:
                    stream.close()
            else:
                self.layers[layer].set(stream, fade_s)

    def set_volume(self, gain):
        with self.lock:
            self.gain = gain

    def stop(self):
        with self.lock:
            if self.stopped:
                return
            self.stopped = True
            for layer in self.layers.values():
                layer.close()
        # устройство останавливаем без lock: колбэк может ждать его
        if self.device is not None:
            self.device.stop()
            self.device.close()
