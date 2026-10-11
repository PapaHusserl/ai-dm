import threading
import time

from ai_dm.audio.catalog import theme_files
from ai_dm.audio.player import NullPlayer, Player
from ai_dm.audio.select import pick_theme

COMBAT = "combat"
USAGE = "Использование: /music [on|off|0–100|ambient on|off]"
MISSING = "библиотека miniaudio не установлена (uv sync --extra audio)"


def next_switch(current, wanted, last_switch_s, now_s, min_s):
    # менять ли тему: бой (вход и выход) -- сразу, остальное -- не чаще раза в min_s секунд
    if wanted == current:
        return False
    if COMBAT in (wanted, current):
        return True
    return now_s - last_switch_s >= min_s


def sound_line(reason):
    return f"Звук выключен: {reason}"


def parse_volume(arg):
    if arg.isascii() and arg.isdigit() and int(arg) <= 100:
        return int(arg)
    return None


class SoundController:
    # музыка и эмбиент TUI: выбор темы по состоянию, гистерезис, команда /music
    def __init__(self, player: Player, audio, cfg, prefs, now=time.monotonic):
        self.player = player
        self.audio = audio
        self.cfg = cfg
        self.prefs = prefs
        self.now = now
        self.enabled = cfg.enabled
        # что уходит в audio.toml: --mute и тишина запуска сюда не попадают, только /music on|off
        self.saved_enabled = cfg.enabled
        self.volume = cfg.volume
        self.ambient = cfg.ambient
        # играющая тема, желаемая тема (при выключенном звуке копится для /music on)
        self.theme = None
        self.wanted = None
        self.last_switch_s = float("-inf")
        # причина тишины (нет библиотеки, нет устройства) или None
        self.reason = None
        # плеер ещё не открывали (звук выключен при старте): /music on откроет его
        self.deferred = False
        self.lock = threading.Lock()
        self.handlers = {
            "on": self.turn_on,
            "off": self.turn_off,
            "ambient on": lambda: self.set_ambient(True),
            "ambient off": lambda: self.set_ambient(False),
        }

    def update(self, state):
        with self.lock:
            self.wanted = pick_theme(self.audio.index, state)
            if not self.enabled:
                return
            if next_switch(
                self.theme, self.wanted, self.last_switch_s, self.now(), self.cfg.min_switch_s
            ):
                self.apply(self.wanted)

    def apply(self, theme):
        music, ambient = theme_files(self.audio.index, self.audio.folder, theme)
        fade_s = self.cfg.crossfade_s
        self.player.set_layer("music", music, fade_s)
        self.player.set_layer("ambient", ambient if self.ambient else None, fade_s)
        self.theme = theme
        self.last_switch_s = self.now()

    def turn_on(self):
        self.enabled = True
        self.saved_enabled = True
        if self.deferred:
            self.deferred = False
            self.start_player()
        if self.theme != self.wanted:
            self.apply(self.wanted)

    def start_player(self):
        # открывает настоящий плеер (нет библиотеки или устройства -- NullPlayer и причина)
        # и отдаёт ему громкость
        self.player, self.reason = open_player(self.cfg)
        self.player.set_volume((self.volume / 100) ** 2)

    def turn_off(self):
        self.enabled = False
        self.saved_enabled = False
        self.player.set_layer("music", None, self.cfg.crossfade_s)
        self.player.set_layer("ambient", None, self.cfg.crossfade_s)
        self.theme = None

    def set_ambient(self, on):
        self.ambient = on
        if self.enabled:
            ambient = theme_files(self.audio.index, self.audio.folder, self.theme)[1]
            self.player.set_layer("ambient", ambient if on else None, self.cfg.crossfade_s)

    def set_volume(self, volume):
        self.volume = volume
        self.player.set_volume((volume / 100) ** 2)

    def status(self):
        lines = []
        if self.reason is not None:
            lines.append(sound_line(self.reason))
        state = "вкл" if self.enabled else "выкл"
        ambient = "вкл" if self.ambient else "выкл"
        lines.append(f"Звук: {state}, громкость {self.volume}, эмбиент: {ambient}")
        if self.theme is not None:
            music, ambient_file = theme_files(self.audio.index, self.audio.folder, self.theme)
            files = (music, ambient_file if self.ambient else None)
            names = [path.name for path in files if path is not None]
            lines.append(f"Тема: {self.theme}" + (f" ({' + '.join(names)})" if names else ""))
        return lines

    def command(self, arg):
        arg = " ".join(arg.split())
        with self.lock:
            if arg == "":
                return self.status()
            handler = self.handlers.get(arg)
            volume = parse_volume(arg)
            if handler is None and volume is None:
                return [USAGE]
            if handler is not None:
                handler()
            else:
                self.set_volume(volume)
            self.prefs.save(self.saved_enabled, self.volume, self.ambient)
            return self.status()

    def stop(self):
        with self.lock:
            self.player.stop()


class SilentSound:
    # звука нет в этом запуске (простой режим, replay, mock): команды отвечают причиной
    def __init__(self, reason):
        self.reason = reason

    def update(self, state):
        pass

    def command(self, arg):
        return [sound_line(self.reason)]

    def stop(self):
        pass


def open_player(cfg):
    # (плеер, причина отказа); библиотека лениво: без extra модуля с ней нет
    try:
        from ai_dm.audio.miniaudio_player import MiniaudioPlayer
    except ImportError:
        return NullPlayer(), MISSING
    player = MiniaudioPlayer(cfg)
    reason = player.start()
    if reason is not None:
        return NullPlayer(), reason
    return player, None


def make_sound(cfg, prefs, audio, *, mute):
    # (звук, строка для ленты или None); строка -- одна, только при сбое включённого звука
    sound = SoundController(NullPlayer(), audio, cfg, prefs)
    if mute or not cfg.enabled:
        sound.enabled = False
        sound.deferred = True
        return sound, None
    sound.start_player()
    return sound, None if sound.reason is None else sound_line(sound.reason)
