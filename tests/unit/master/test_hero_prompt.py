# Б0-П1 (B0-PLAN A4), Б1а: HeroPromptBuilder (режим hero_background), роль narrator.
# system[0] -- background_rules.md, system[1] -- справочник, оба cache=True; messages[0] -- вход.
import json
from importlib import resources

from master_kit import app_cfg

from ai_dm.master.hero import HeroPromptBuilder
from ai_dm.protocol.context import BackgroundTask, CreationContext

SKILLS = ["perception", "survival"]


def creation(registry, cfg, class_skills=SKILLS):
    return CreationContext(registry, cfg, BackgroundTask("fighter", class_skills))


def build(registry, cfg, description="Бывший акробат", model=None, class_skills=SKILLS):
    ctx = creation(registry, cfg, class_skills)
    builder = HeroPromptBuilder(app_cfg(), model=model)
    return builder.build(ctx, description, "hero_background")


def reference(request):
    return json.loads(request.system[1].text)


def rules_file():
    path = resources.files("ai_dm.master") / "prompts" / "background_rules.md"
    return path.read_text(encoding="utf-8")


def test_role_is_narrator(registry, cfg):
    assert build(registry, cfg).role == "narrator"


def test_system_has_two_blocks_both_cached(registry, cfg):
    request = build(registry, cfg)
    assert len(request.system) == 2
    assert [b.cache for b in request.system] == [True, True]


def test_system0_is_rules_file(registry, cfg):
    assert build(registry, cfg).system[0].text == rules_file()


def test_rules_mention_the_tool(registry, cfg):
    assert "background_spec" in build(registry, cfg).system[0].text


def test_tools_are_the_hero_set(registry, cfg):
    request = build(registry, cfg)
    assert [t.name for t in request.tools] == ["background_spec"]


def test_reference_has_four_srd_backgrounds_by_registry_names(registry, cfg):
    names = [e["name"] for e in reference(build(registry, cfg))["examples"]]
    assert names == [b.name for b in registry.all("background")]
    assert len(names) == 4


def test_reference_examples_carry_the_set_fields(registry, cfg):
    soldier = [
        e for e in reference(build(registry, cfg))["examples"] if e["name"] == "Солдат"
    ][0]
    assert soldier["abilities"] == ["str", "dex", "con"]
    assert soldier["tool"] == "gaming_set"
    assert soldier["feat"] == "savage_attacker"
    assert soldier["gold_cp"] == 1400


def test_reference_feats_are_origin_only(registry, cfg):
    feats = reference(build(registry, cfg))["origin_feat_ids"]
    assert "alert" in feats
    assert "defense" not in feats
    assert sorted(feats) == sorted(
        f.id for f in registry.all("feat") if f.category == "origin"
    )


def test_reference_tools_are_only_tool_items(registry, cfg):
    tools = reference(build(registry, cfg))["tool_ids"]
    assert "thieves_tools" in tools
    assert "crowbar" not in tools
    assert sorted(tools) == sorted(i.id for i in registry.all("item") if i.tool)


def test_reference_items_have_prices(registry, cfg):
    items = reference(build(registry, cfg))["item_ids"]
    assert items["crowbar"] == registry.get("item", "crowbar").cost_cp
    assert "crowbar" in items


def test_reference_has_ability_and_skill_lists_and_budget(registry, cfg):
    data = reference(build(registry, cfg))
    assert set(data["abilities"]) == {"str", "dex", "con", "int", "wis", "cha"}
    assert "acrobatics" in data["skills"]
    assert len(data["skills"]) == 18
    assert data["budget_cp"] == 5000


def test_message_has_class_class_skills_and_description(registry, cfg):
    request = build(registry, cfg, description="Бывший акробат")
    assert len(request.messages) == 1
    assert request.messages[0].role == "user"
    data = json.loads(request.messages[0].content[0].text)
    assert data == {
        "class": "fighter", "class_skills": ["perception", "survival"],
        "description": "Бывший акробат",
    }


def test_message_without_class_skills_has_empty_list(registry, cfg):
    request = build(registry, cfg, class_skills=())
    assert json.loads(request.messages[0].content[0].text)["class_skills"] == []


def test_prefix_is_same_for_two_descriptions(registry, cfg):
    first = build(registry, cfg, description="Бывший акробат")
    second = build(registry, cfg, description="Вор-неудачник")
    assert first.system == second.system
    assert first.messages != second.messages


def test_prefix_is_same_for_two_classes_of_skills(registry, cfg):
    first = build(registry, cfg, class_skills=["perception"])
    second = build(registry, cfg, class_skills=["stealth"])
    assert first.system == second.system


def test_default_model_and_limits_are_narrator_role(registry, cfg):
    app = app_cfg()
    request = build(registry, cfg)
    assert request.model == app.roles.narrator.model
    assert request.max_tokens == app.roles.narrator.max_tokens
    assert request.effort == app.roles.narrator.effort


def test_gemini_model_takes_gemini_profile_limits(registry, cfg):
    profile = app_cfg().profiles["gemini"].narrator
    request = build(registry, cfg, model=profile.model)
    assert request.model == profile.model
    assert request.max_tokens == profile.max_tokens
    assert request.effort == profile.effort


def test_alternative_model_takes_alternative_limits(registry, cfg):
    alt = app_cfg().alternatives.narrator
    request = build(registry, cfg, model=alt.model)
    assert (request.max_tokens, request.effort) == (alt.max_tokens, alt.effort)


def test_unknown_model_takes_default_limits_but_keeps_model(registry, cfg):
    app = app_cfg()
    request = build(registry, cfg, model="some-other-model")
    assert request.model == "some-other-model"
    assert request.max_tokens == app.roles.narrator.max_tokens


def test_builder_does_not_need_a_bundle(registry, cfg):
    # CreationContext без bundle: сборка не должна к нему обращаться
    ctx = creation(registry, cfg)
    assert not hasattr(ctx, "bundle")
    HeroPromptBuilder(app_cfg()).build(ctx, "x", "hero_background")


def test_world_text_is_ignored(registry, cfg):
    ctx = creation(registry, cfg)
    builder = HeroPromptBuilder(app_cfg())
    plain = builder.build(ctx, "x", "hero_background")
    with_world = builder.build(ctx, "x", "hero_background", world_text="МИР")
    assert plain == with_world


def test_reference_examples_have_skills_and_equipment(registry, cfg):
    soldier = [
        e for e in reference(build(registry, cfg))["examples"] if e["name"] == "Солдат"
    ][0]
    assert soldier["skills"] == ["athletics", "intimidation"]
    assert "spear" in soldier["equipment"]


def test_reference_has_no_world_items(registry, cfg):
    from ai_dm.rules.custom_items import as_item
    from ai_dm.state.world import CustomItem

    custom = CustomItem(id="custom_1", name="Ключ", cost_cp=5, created_s=0)
    overlay = registry.with_items({"item": [as_item(custom)]})
    request = HeroPromptBuilder(app_cfg()).build(
        creation(overlay, cfg), "x", "hero_background"
    )
    data = reference(request)
    assert "custom_1" not in data["item_ids"]
    assert "custom_1" not in data["tool_ids"]


def test_reference_prices_include_weapons_and_armor(registry, cfg):
    items = reference(build(registry, cfg))["item_ids"]
    assert items["spear"] == registry.get("weapon", "spear").cost_cp
    assert items["dagger"] == registry.get("weapon", "dagger").cost_cp
    assert items["chain_mail"] == registry.get("armor", "chain_mail").cost_cp


def test_reference_has_every_srd_example_item_priced(registry, cfg):
    data = reference(build(registry, cfg))
    for example in data["examples"]:
        for item_id in example["equipment"]:
            assert item_id in data["item_ids"]


def test_reference_weapons_are_not_tools(registry, cfg):
    assert "spear" not in reference(build(registry, cfg))["tool_ids"]


def test_reference_has_no_world_weapons(registry, cfg):
    data = reference(build(registry, cfg))
    assert all(not k.startswith("custom_") for k in data["item_ids"])
