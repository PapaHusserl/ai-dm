# Му-а (MU-PLAN B1): помощники тестов ai_dm.audio. Не фикстуры pytest, а обычные функции.
# Только FakePlayer / FakeClock: настоящего плеера и miniaudio здесь нет.
# Импорты ai_dm.audio.* -- ВНУТРИ функций: пока пакета нет, тесты падают по одному (red).
#
# Допущения о контракте (MU-PLAN A1): load_audio(folder) -> Audio(index, folder);
# SoundController(player, audio, cfg, prefs, *, now): второй параметр -- Audio (индекс + папка),
# потому что theme_files(index, folder, theme) нужна папка.
from pathlib import Path

import yaml

COMBAT = "combat"


def index_dict():
    # тема -> (музыка, эмбиент); теги и тон -- как в плане, но с собственным набором для теста
    return {
        "themes": {
            "combat": {"music": "combat.ogg"},
            "tavern": {"music": "tavern.ogg", "ambient": "crowd.ogg"},
            "town": {"music": "town.ogg", "ambient": "street.ogg"},
            "nature": {"music": "nature.ogg", "ambient": "wind_birds.ogg"},
            "dungeon": {"music": "dungeon.ogg", "ambient": "drips.ogg"},
            "dark": {"music": "dark.ogg", "ambient": "night.ogg"},
            "explore": {"music": "explore.ogg"},
            "romance": {"music": "romance.ogg"},
        },
        "location_tags": {
            "таверна": "tavern", "город": "town", "лес": "nature", "руины": "dungeon",
            "святилище": "dark",
        },
        "locations": {"vault": "dungeon"},
        "tone": {"horror_strong": "dark", "default": "explore"},
        "combat": "combat",
    }


def index(**overrides):
    from ai_dm.audio.catalog import AudioIndex

    return AudioIndex.model_validate({**index_dict(), **overrides})


def file_names(data=None):
    data = index_dict() if data is None else data
    names = set()
    for theme in data["themes"].values():
        names.add(theme["music"])
        if theme.get("ambient"):
            names.add(theme["ambient"])
    return sorted(names)


def audio_dir(tmp_path, files=None, data=None):
    # каталог с index.yaml и пустыми *.ogg; files=None -- все файлы из индекса
    data = index_dict() if data is None else data
    folder = Path(tmp_path) / "audio"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "index.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True), encoding="utf-8"
    )
    for name in file_names(data) if files is None else files:
        (folder / name).write_bytes(b"")
    return folder


def audio(tmp_path, files=None, data=None):
    from ai_dm.audio.catalog import load_audio

    return load_audio(audio_dir(tmp_path, files, data))


def state(**kw):
    from ai_dm.audio.select import SoundState

    fields = {"location_id": "place", "tags": (), "in_combat": False, "horror": "", "romance": ""}
    return SoundState(**{**fields, **kw})


class FakeClock:
    def __init__(self, start=0.0):
        self.t = float(start)

    def now(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


class FakePlayer:
    # calls: ("layer", имя, путь|None, fade_s), ("volume", gain), ("stop",)
    def __init__(self, start_reason=None):
        self.calls = []
        self.started = 0
        self.start_reason = start_reason

    def start(self):
        self.started += 1
        return self.start_reason

    def set_layer(self, layer, path, fade_s):
        self.calls.append(("layer", layer, path, fade_s))

    def set_volume(self, gain):
        self.calls.append(("volume", gain))

    def stop(self):
        self.calls.append(("stop",))

    def layer_calls(self, name):
        return [c for c in self.calls if c[0] == "layer" and c[1] == name]

    def last_path(self, name):
        return self.layer_calls(name)[-1][2]


class RecordingPrefs:
    # вместо AudioPrefs: запоминает save(enabled, volume, ambient)
    def __init__(self, enabled=True, volume=60, ambient=True):
        self.enabled = enabled
        self.volume = volume
        self.ambient = ambient
        self.saves = []

    def save(self, enabled, volume, ambient):
        self.saves.append((enabled, volume, ambient))


def audio_config(**kw):
    from ai_dm.config.app import AudioConfig

    return AudioConfig(**kw)


def controller(tmp_path, prefs=None, **cfg):
    # -> (SoundController, FakePlayer, RecordingPrefs, FakeClock, Audio)
    from ai_dm.audio.control import SoundController

    player, clock = FakePlayer(), FakeClock()
    prefs = RecordingPrefs() if prefs is None else prefs
    data = audio(tmp_path)
    sound = SoundController(player, data, audio_config(**cfg), prefs, now=clock.now)
    return sound, player, prefs, clock, data
