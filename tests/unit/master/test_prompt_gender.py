# К0-фикс-б (K0-FIX-PLAN, 7.5): пол и местоимения NPC и героя в состоянии промпта рассказчика
# (scene_npcs, known_npcs, hero) и роли world; без пола ключей нет.
import json

import pytest
from master_kit import app_cfg, make_ctx

from ai_dm.master.prompt import PromptBuilder
from ai_dm.master.world import WorldPromptBuilder


def state(ctx, mode="explore"):
    request = PromptBuilder(app_cfg()).build(ctx, "Осматриваюсь.", mode)
    return json.loads(request.messages[0].content[0].text)


def world_state(ctx):
    request = WorldPromptBuilder(app_cfg(), []).build(ctx, "", "world")
    return json.loads(request.messages[0].content[0].text)


def by_id(items):
    return {item["id"]: item for item in items}


@pytest.fixture
def ctx(registry, cfg):
    return make_ctx(registry, cfg)


# scene_npcs

def test_scene_npc_with_gender_has_key(ctx):
    ctx.bundle.world.npcs["grakh"].gender = "male"
    assert by_id(state(ctx)["scene_npcs"])["grakh"]["gender"] == "male"


def test_scene_npc_with_pronouns_has_key(ctx):
    ctx.bundle.world.npcs["grakh"].pronouns = "они"
    assert by_id(state(ctx)["scene_npcs"])["grakh"]["pronouns"] == "они"


def test_scene_npc_without_gender_has_no_keys(ctx):
    item = by_id(state(ctx)["scene_npcs"])["grakh"]
    assert "gender" not in item
    assert "pronouns" not in item


def test_scene_npc_keeps_its_other_keys_with_gender(ctx):
    ctx.bundle.world.npcs["grakh"].gender = "other"
    item = by_id(state(ctx)["scene_npcs"])["grakh"]
    assert item["name"] == "Гракх"
    assert item["attitude"] == 0


def test_scene_npc_gender_and_pronouns_together(ctx):
    npc = ctx.bundle.world.npcs["grakh"]
    npc.gender = "female"
    npc.pronouns = "она, госпожа"
    item = by_id(state(ctx)["scene_npcs"])["grakh"]
    assert (item["gender"], item["pronouns"]) == ("female", "она, госпожа")


# known_npcs

def test_known_npc_with_gender_has_key(ctx):
    ctx.bundle.world.npcs["grakh"].gender = "male"
    assert by_id(state(ctx)["known_npcs"])["grakh"]["gender"] == "male"


def test_known_npc_with_pronouns_has_key(ctx):
    ctx.bundle.world.npcs["grakh"].pronouns = "он"
    assert by_id(state(ctx)["known_npcs"])["grakh"]["pronouns"] == "он"


def test_known_npc_without_gender_has_no_keys(ctx):
    item = by_id(state(ctx)["known_npcs"])["grakh"]
    assert "gender" not in item
    assert "pronouns" not in item


def test_gender_of_one_npc_does_not_leak_to_another(ctx):
    ctx.bundle.world.npcs["aldric"].gender = "male"
    assert "gender" not in by_id(state(ctx)["scene_npcs"])["grakh"]


# hero

def test_hero_gender_is_in_hero_data(ctx):
    ctx.hero.gender = "female"
    assert state(ctx)["hero"]["gender"] == "female"


def test_hero_pronouns_are_in_hero_data(ctx):
    ctx.hero.pronouns = "они"
    assert state(ctx)["hero"]["pronouns"] == "они"


def test_hero_without_gender_has_no_keys(ctx):
    hero = state(ctx)["hero"]
    assert "gender" not in hero
    assert "pronouns" not in hero


def test_hero_gender_does_not_replace_name(ctx):
    ctx.hero.gender = "male"
    assert state(ctx)["hero"]["name"] == ctx.hero.name


# в других режимах герой тот же

@pytest.mark.parametrize("mode", ["explore", "combat_narrate"])
def test_hero_gender_in_modes(ctx, mode):
    ctx.hero.gender = "other"
    assert state(ctx, mode)["hero"]["gender"] == "other"


# роль world

def test_world_npc_with_gender_has_key(ctx):
    ctx.bundle.world.npcs["grakh"].gender = "male"
    assert by_id(world_state(ctx)["npcs"])["grakh"]["gender"] == "male"


def test_world_npc_with_pronouns_has_key(ctx):
    ctx.bundle.world.npcs["grakh"].pronouns = "он"
    assert by_id(world_state(ctx)["npcs"])["grakh"]["pronouns"] == "он"


def test_world_npc_without_gender_has_no_keys(ctx):
    item = by_id(world_state(ctx)["npcs"])["grakh"]
    assert "gender" not in item
    assert "pronouns" not in item


def test_world_npc_keeps_its_other_keys(ctx):
    ctx.bundle.world.npcs["grakh"].gender = "male"
    item = by_id(world_state(ctx)["npcs"])["grakh"]
    assert item["attitude"] == 0
    assert item["key"] is True
