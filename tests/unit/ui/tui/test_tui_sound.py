# Му-а (MU-PLAN B1): звук в TUI -- AiDmApp.show_step зовёт game.audio.update(sound_state(game)),
# tui.run_tui останавливает звук в finally. Pilot как в test_tui_art.py; только
# FakePlayer/FakeClock,
# настоящий miniaudio запрещён (sys.modules["miniaudio"] = None).
# Без mutmut (ui.tui -- Д1).
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "game"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "audio"))

from audio_kit import FakeClock, FakePlayer, RecordingPrefs, audio, audio_config  # noqa: E402
from ui_kit import DESCEND, TALK, scene_app  # noqa: E402

from ai_dm.audio.control import SoundController  # noqa: E402
from ai_dm.game.scene import hero_of  # noqa: E402
from ai_dm.ui.session import PlaySession  # noqa: E402
from ai_dm.ui.tui.app import AiDmApp  # noqa: E402


@pytest.fixture(autouse=True)
def no_real_miniaudio(monkeypatch):
    monkeypatch.setitem(sys.modules, "miniaudio", None)


def run(app, steps, size=(140, 40)):
    async def scenario():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            return await steps(app, pilot)

    return asyncio.run(scenario())


def tag_hero_place(game, *tags):
    world = game.bundle.world
    world.locations[hero_of(game.bundle).location_id].tags = list(tags)


def wire(game, tmp_path):
    player, prefs, clock = FakePlayer(), RecordingPrefs(), FakeClock()
    game.audio = SoundController(
        player, audio(tmp_path / "snd"), audio_config(), prefs, now=clock.now
    )
    return player, prefs, clock


def folder_of(tmp_path):
    return tmp_path / "snd" / "audio"


def test_mount_applies_theme_of_hero_location(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path / "game")
    tag_hero_place(game, "таверна")
    player, _, _ = wire(game, tmp_path)

    async def steps(app, pilot):
        return None

    run(app, steps)
    assert player.last_path("music") == folder_of(tmp_path) / "tavern.ogg"
    assert player.last_path("ambient") == folder_of(tmp_path) / "crowd.ogg"


def test_mount_without_tags_gives_default_theme(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path / "game")
    tag_hero_place(game)
    player, _, _ = wire(game, tmp_path)

    async def steps(app, pilot):
        return None

    run(app, steps)
    assert player.last_path("music") == folder_of(tmp_path) / "explore.ogg"


def test_turn_does_not_resend_same_theme(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path / "game")
    tag_hero_place(game, "таверна")
    player, _, clock = wire(game, tmp_path)

    async def steps(app, pilot):
        before = list(player.calls)
        clock.advance(100)
        await tui.submit(app, pilot)
        return before

    before = run(app, steps)
    assert player.calls == before


def test_fight_start_switches_to_combat_at_once(registry, tmp_path, tui):
    game, _ = scene_app(registry, tmp_path / "game", hp=200)
    tag_hero_place(game, "таверна")
    player, _, _ = wire(game, tmp_path)
    app = AiDmApp(PlaySession(game))

    async def steps(app, pilot):
        await tui.submit(app, pilot, TALK)
        await tui.submit(app, pilot, "1")
        await tui.submit(app, pilot, DESCEND)
        return game.bundle.session.active_combat is not None

    assert run(app, steps) is True
    assert player.last_path("music") == folder_of(tmp_path) / "combat.ogg"
    assert player.last_path("ambient") is None


def test_music_off_command_silences_layers_and_answers(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path / "game")
    tag_hero_place(game, "таверна")
    player, prefs, _ = wire(game, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/music off")
        return tui.text_of(app.query_one("#feed"))

    feed = run(app, steps)
    assert player.last_path("music") is None
    assert player.last_path("ambient") is None
    assert prefs.saves == [(False, 60, True)]
    assert "Звук" in feed


def test_music_on_command_plays_at_once(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path / "game")
    tag_hero_place(game, "таверна")
    player, _, clock = wire(game, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/music off")
        clock.advance(1)
        await tui.submit(app, pilot, "/music on")

    run(app, steps)
    assert player.last_path("music") == folder_of(tmp_path) / "tavern.ogg"


def test_music_volume_command_reaches_player(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path / "game")
    player, prefs, _ = wire(game, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/music 40")

    run(app, steps)
    assert ("volume", pytest.approx(0.4 ** 2)) in player.calls
    assert prefs.saves == [(True, 40, True)]


def test_default_silent_sound_answers_in_feed(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path / "game")

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/music")
        return tui.flat(tui.text_of(app.query_one("#feed")))

    assert "Звук выключен: звук только в TUI" in run(app, steps)


# остановка звука при выходе из TUI

def patch_run(monkeypatch, effect):
    def fake_run(self, *args, **kwargs):
        return effect()

    monkeypatch.setattr(AiDmApp, "run", fake_run)
    monkeypatch.setattr(AiDmApp, "after_exit", lambda self: 0)


def test_run_tui_stops_sound_once_on_exit(registry, tmp_path, tui, monkeypatch):
    import ai_dm.ui.tui as tui_pkg

    _, game = tui.app(registry, tmp_path / "game")
    player, _, _ = wire(game, tmp_path)
    patch_run(monkeypatch, lambda: None)
    assert tui_pkg.run_tui(game) == 0
    assert player.calls.count(("stop",)) == 1


def test_run_tui_stops_sound_when_run_raises(registry, tmp_path, tui, monkeypatch):
    import ai_dm.ui.tui as tui_pkg

    _, game = tui.app(registry, tmp_path / "game")
    player, _, _ = wire(game, tmp_path)

    def boom():
        raise RuntimeError("после первого кадра")

    patch_run(monkeypatch, boom)
    with pytest.raises(Exception):  # noqa: B017 -- TuiStartError или RuntimeError
        tui_pkg.run_tui(game)
    assert player.calls.count(("stop",)) == 1
