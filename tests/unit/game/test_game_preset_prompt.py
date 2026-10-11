# Б0-П2: стабильность префикса промпта у мира с пресетом (кэш). Два хода -> system[0] и system[1]
# запросов нарратора побайтно равны; голос пресета (tone.notes) лежит в system[1]; после
# /tone romance ... меняется system[1] (ожидаемо), system[0] -- нет.
import sys
from pathlib import Path

from game_kit import ReactiveAdapter, make_app

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "campaign"))
from campaign_kit import SAVED_AT, load, write_pack  # noqa: E402


def preset_app(registry, cfg, tmp_path, preset_id="grim"):
    from ai_dm.campaign.presets import load_presets
    from ai_dm.game.starter import new_world_from_pack

    pack = load(write_pack(tmp_path / "packs"), registry)
    bundle = new_world_from_pack(
        registry, cfg, pack, hero="arn", seed=1, world_id="w1", saved_at=SAVED_AT,
        preset_id=preset_id,
    )
    adapter = ReactiveAdapter()
    app = make_app(registry, tmp_path / "saves", adapter, bundle=bundle)
    return app, adapter, load_presets()[preset_id]


def text_of(block):
    return getattr(block, "text", None) or str(block)


def two_turns(app):
    app.handle("осматриваюсь")
    app.handle("иду дальше")


def test_system_blocks_are_byte_equal_between_turns(registry, cfg, tmp_path):
    app, adapter, _ = preset_app(registry, cfg, tmp_path)
    two_turns(app)
    first, second = adapter.requests[0], adapter.requests[-1]
    assert first is not second
    assert text_of(first.system[0]) == text_of(second.system[0])
    assert text_of(first.system[1]) == text_of(second.system[1])


def test_preset_voice_is_inside_system_1(registry, cfg, tmp_path):
    app, adapter, preset = preset_app(registry, cfg, tmp_path)
    app.handle("осматриваюсь")
    assert preset.tone.notes in text_of(adapter.requests[-1].system[1])
    assert preset.tone.notes not in text_of(adapter.requests[-1].system[0])


def test_tone_command_changes_system_1_but_not_system_0(registry, cfg, tmp_path):
    app, adapter, _ = preset_app(registry, cfg, tmp_path)
    app.handle("осматриваюсь")
    before = adapter.requests[-1]
    app.handle("/tone romance намёки")
    app.handle("иду дальше")
    after = adapter.requests[-1]
    assert text_of(before.system[0]) == text_of(after.system[0])
    assert text_of(before.system[1]) != text_of(after.system[1])
    assert "намёки" in text_of(after.system[1])


def test_different_presets_give_different_system_1(registry, cfg, tmp_path):
    grim_app, grim, _ = preset_app(registry, cfg, tmp_path / "a", "grim")
    tale_app, tale, _ = preset_app(registry, cfg, tmp_path / "b", "fairytale")
    grim_app.handle("осматриваюсь")
    tale_app.handle("осматриваюсь")
    assert text_of(grim.requests[-1].system[1]) != text_of(tale.requests[-1].system[1])
    assert text_of(grim.requests[-1].system[0]) == text_of(tale.requests[-1].system[0])
