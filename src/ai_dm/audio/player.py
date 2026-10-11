from pathlib import Path
from typing import Protocol


class Player(Protocol):
    # слои: "music" и "ambient"; path None -- слой затихает; fade_s -- кроссфейд
    def start(self) -> str | None:
        # None -- играть можно; иначе причина отказа (нет устройства)
        ...

    def set_layer(self, layer: str, path: Path | None, fade_s: float) -> None: ...

    def set_volume(self, gain: float) -> None: ...

    def stop(self) -> None: ...


class NullPlayer:
    def start(self):
        return None

    def set_layer(self, layer, path, fade_s):
        pass

    def set_volume(self, gain):
        pass

    def stop(self):
        pass
