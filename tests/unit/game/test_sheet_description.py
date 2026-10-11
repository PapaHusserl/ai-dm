# Живой прогон 1, п. 4: /abilities и /spells выводят полное описание (description_lines),
# а не первое предложение: абзацы по строкам, перенос по ширине width-2, отступ 4 пробела.
from pathlib import Path

import pytest
from game_kit import ReactiveAdapter, make_app

from ai_dm.campaign.loader import load_pack, pack_content_dir
from ai_dm.content.loader import load_registry
from ai_dm.game.scene import hero_of
from ai_dm.game.sheet_text import description_lines, feature_groups, spell_ids
from ai_dm.game.starter import new_world_from_pack

DRAGON = Path(__file__).resolve().parents[3] / "campaigns" / "drunk_dragon"
LONG = (
    "Первое длинное предложение про охотника и его добычу. Второе предложение тоже длинное и "
    "не должно пропасть. Третье предложение замыкает абзац."
)


def flat(text):
    return " ".join(text.split())


@pytest.fixture
def dragon_app(cfg, tmp_path):
    registry = load_registry([pack_content_dir(DRAGON)])
    bundle = new_world_from_pack(
        registry, cfg, load_pack(DRAGON, registry), hero="grey", seed=1, world_id="w1",
        saved_at="2026-01-01T00:00:00",
    )
    return make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)


def feature_descriptions(app):
    hero = hero_of(app.bundle)
    registry = app.registry
    ids = [fid for _, group in feature_groups(hero, registry) for fid in group]
    texts = [registry.get("feature", fid).description for fid in ids]
    texts += [registry.get("feat", fid).description for fid in hero.sheet.feats]
    return [text for text in texts if text]


# description_lines

def test_description_lines_keeps_every_sentence():
    assert flat(" ".join(description_lines(LONG, 40))) == flat(LONG)


def test_description_lines_wrap_within_width_minus_two():
    lines = description_lines(LONG, 40)
    assert len(lines) > 1
    assert all(len(line) <= 38 for line in lines)


def test_description_lines_indent_is_four_spaces_on_every_line():
    lines = description_lines(LONG, 40)
    assert all(line.startswith("    ") and not line.startswith("     ") for line in lines)


def test_description_lines_paragraphs_start_on_new_lines():
    lines = description_lines("Первый абзац.\nВторой абзац.", 80)
    assert lines == ["    Первый абзац.", "    Второй абзац."]


def test_description_lines_short_text_is_one_line():
    assert description_lines("  Коротко.  ", 80) == ["    Коротко."]


# команды

def test_abilities_prints_full_descriptions_with_wrap(dragon_app):
    width = dragon_app.settings.app.ui.width
    lines = [x for text in dragon_app.handle("/abilities").lines for x in text.split("\n")]
    text = flat(" ".join(lines))
    descriptions = feature_descriptions(dragon_app)
    assert any(". " in flat(d) for d in descriptions)
    for description in descriptions:
        assert flat(description) in text
    assert "…" not in text
    assert all(len(line) <= width for line in lines)


def test_abilities_description_lines_are_indented_by_four(dragon_app):
    lines = [x for t in dragon_app.handle("/abilities").lines for x in t.split("\n")]
    first = flat(feature_descriptions(dragon_app)[0]).split()[0]
    assert any(line.startswith("    " + first) for line in lines)


def test_spells_prints_full_descriptions_with_wrap(dragon_app):
    width = dragon_app.settings.app.ui.width
    lines = [x for text in dragon_app.handle("/spells").lines for x in text.split("\n")]
    text = flat(" ".join(lines))
    registry = dragon_app.registry
    hero = hero_of(dragon_app.bundle)
    spells = [registry.get("spell", sid) for sid in spell_ids(hero, registry)]
    described = [s for s in spells if s.description and s.name in text]
    assert described
    for spell in described:
        assert flat(spell.description) in text
    assert "…" not in text
    assert all(len(line) <= width for line in lines)


def test_simple_mode_abilities_has_full_descriptions(dragon_app):
    from slots_kit import ScriptedInput

    from ai_dm.ui.io import CaptureOutput
    from ai_dm.ui.simple import run

    out = CaptureOutput()
    run(dragon_app, ScriptedInput(["/abilities"]), out)
    text = flat(out.text)
    for description in feature_descriptions(dragon_app):
        assert flat(description) in text


def test_tui_modal_abilities_has_full_descriptions(dragon_app):
    import asyncio

    from ai_dm.ui.session import PlaySession
    from ai_dm.ui.tui.app import AiDmApp

    app = AiDmApp(PlaySession(dragon_app))

    async def scenario():
        async with app.run_test(size=(140, 60)) as pilot:
            await pilot.pause()
            app.query_one("#input").value = "/abilities"
            await pilot.press("enter")
            await app.workers.wait_for_complete()
            await pilot.pause()
            return flat(str(app.screen.query_one("#modal-text").render()))

    text = asyncio.run(scenario())
    for description in feature_descriptions(dragon_app):
        assert flat(description) in text


def test_description_lines_line_of_exactly_width_minus_two_fits():
    assert description_lines("а" * 34, 40) == ["    " + "а" * 34]
