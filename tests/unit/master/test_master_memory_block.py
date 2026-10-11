# Память в контексте нарратора (этап 4, P0, STAGE4-PLAN A2): system[2] = game_summary, выжимки глав,
# выжимки сцен ТЕКУЩЕЙ главы; stable=False, cache=True; system[0], system[1] от памяти не зависят.
from pathlib import Path

import pytest
from master_kit import app_cfg, make_bundle, make_ctx
from protocol_kit import make_ctx as make_proto_ctx

from ai_dm.campaign.loader import load_pack, pack_content_dir
from ai_dm.content.loader import load_registry
from ai_dm.game.starter import new_world_from_pack
from ai_dm.master.prompt import PromptBuilder
from ai_dm.state.memory import SceneSummary

ROOT = Path(__file__).resolve().parents[3]
DRAGON = ROOT / "campaigns" / "drunk_dragon"


def build(ctx, text="Осматриваюсь."):
    return PromptBuilder(app_cfg()).build(ctx, text, "explore")


@pytest.fixture
def dragon_ctx(cfg):
    registry = load_registry([pack_content_dir(DRAGON)])
    pack = load_pack(DRAGON, registry)
    bundle = new_world_from_pack(
        registry, cfg, pack, hero="grey", seed=1, world_id="dd", saved_at="2026-01-01T00:00:00",
    )
    return make_proto_ctx(registry, cfg, bundle=bundle)


def test_system_has_three_blocks(registry, cfg):
    assert len(build(make_ctx(registry, cfg)).system) == 3


def test_memory_block_is_cached_but_not_stable(dragon_ctx):
    block = build(dragon_ctx).system[2]
    assert block.cache is True
    assert block.stable is False


def test_rules_and_world_blocks_are_stable(dragon_ctx):
    system = build(dragon_ctx).system
    assert system[0].stable is True
    assert system[1].stable is True


def test_memory_contains_game_summary(dragon_ctx):
    text = build(dragon_ctx).system[2].text
    assert dragon_ctx.bundle.memory.game_summary[:80] in text


def test_memory_contains_chapter_titles_and_summaries(dragon_ctx):
    text = build(dragon_ctx).system[2].text
    for chapter in dragon_ctx.bundle.memory.chapters:
        assert chapter.title in text
        assert chapter.summary[:80] in text


def test_memory_has_scene_summaries_of_current_chapter(dragon_ctx):
    memory = dragon_ctx.bundle.memory
    current = [s for s in memory.scenes if s.chapter_id == "ch_2"]
    assert current
    text = build(dragon_ctx).system[2].text
    for scene in current:
        assert scene.summary[:60] in text


def test_memory_has_no_scene_summaries_of_other_chapters(dragon_ctx):
    memory = dragon_ctx.bundle.memory
    old = [s for s in memory.scenes if s.chapter_id == "ch_1"]
    assert old
    text = build(dragon_ctx).system[2].text
    for scene in old:
        assert scene.summary not in text


def test_memory_is_not_in_state_message(dragon_ctx):
    request = build(dragon_ctx)
    assert dragon_ctx.bundle.memory.game_summary[:80] not in request.messages[0].content[0].text


def test_prefix_blocks_do_not_change_when_scene_summary_added(dragon_ctx):
    before = build(dragon_ctx).system
    dragon_ctx.bundle.memory.scenes.append(
        SceneSummary(id="sc_new", chapter_id="ch_2", title="Новая", summary="Совсем новая выжимка.")
    )
    after = build(dragon_ctx).system
    assert after[0].text.encode() == before[0].text.encode()
    assert after[1].text.encode() == before[1].text.encode()


def test_new_scene_summary_appears_in_memory_block(dragon_ctx):
    dragon_ctx.bundle.memory.scenes.append(
        SceneSummary(id="sc_new", chapter_id="ch_2", title="Новая", summary="Совсем новая выжимка.")
    )
    assert "Совсем новая выжимка." in build(dragon_ctx).system[2].text


def test_empty_memory_still_has_memory_block(registry, cfg):
    system = build(make_ctx(registry, cfg)).system
    assert len(system) == 3
    assert system[2].text != ""
    assert system[2].stable is False
    assert system[2].cache is True


def test_empty_memory_block_does_not_leak_dragon_text(registry, cfg):
    assert "Тайна таверны" not in build(make_ctx(registry, cfg)).system[2].text


def test_memory_block_is_same_for_same_memory(dragon_ctx):
    assert build(dragon_ctx).system[2].text == build(dragon_ctx).system[2].text


def test_narrator_rules_mention_memory(registry, cfg):
    text = build(make_ctx(registry, cfg)).system[0].text
    assert "память" in text.lower()


def test_make_bundle_still_builds(registry):
    assert make_bundle(registry).memory.scenes == []
