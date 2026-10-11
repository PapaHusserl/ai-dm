# Му-а: NullPlayer -- всё no-op, start() не отказывает.
from pathlib import Path

from ai_dm.audio.player import NullPlayer


def test_null_player_start_returns_none():
    assert NullPlayer().start() is None


def test_null_player_methods_do_nothing():
    player = NullPlayer()
    assert player.set_layer("music", Path("a.ogg"), 2.0) is None
    assert player.set_volume(0.5) is None
    assert player.stop() is None
