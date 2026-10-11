# Б1а (B1-PLAN A3): HeroPromptBuilder в режиме hero_sheet -- запрос роли создания героя.
# system[0] -- hero_sheet_rules.md, system[1] -- справочник листа, оба cache=True; messages[0] --
# description, feedback, previous.
import json
import sys
from importlib import resources
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

from hero_kit import known  # noqa: E402
from master_kit import app_cfg  # noqa: E402

from ai_dm.master.hero import HeroPromptBuilder  # noqa: E402
from ai_dm.protocol.context import BackgroundTask, CreationContext, SheetTask  # noqa: E402

WORLD = {
    "npcs": ["innkeeper", "grakh"], "locations": ["vale", "lame_goose", "cellar"],
    "pantheon": ["sun"],
}


def creation(registry, cfg, **kw):
    kw.setdefault("known", known(**WORLD))
    kw.setdefault("taken_names", ["Гракх", "Гарт"])
    return CreationContext(registry, cfg, SheetTask(**kw))


def build(registry, cfg, description="Сирота-воин", model=None, **kw):
    ctx = creation(registry, cfg, **kw)
    return HeroPromptBuilder(app_cfg(), model=model).build(ctx, description, "hero_sheet")


def reference(request):
    return json.loads(request.system[1].text)


def classes(request):
    return {c["id"]: c for c in reference(request)["classes"]}


def rules_file():
    path = resources.files("ai_dm.master") / "prompts" / "hero_sheet_rules.md"
    return path.read_text(encoding="utf-8")


def test_role_is_narrator(registry, cfg):
    assert build(registry, cfg).role == "narrator"


def test_system_has_two_blocks_both_cached(registry, cfg):
    request = build(registry, cfg)
    assert len(request.system) == 2
    assert [b.cache for b in request.system] == [True, True]


def test_system0_is_sheet_rules_file(registry, cfg):
    request = build(registry, cfg)
    assert request.system[0].text == rules_file()
    assert "hero_sheet" in request.system[0].text


def test_tools_are_the_sheet_set(registry, cfg):
    assert [t.name for t in build(registry, cfg).tools] == ["hero_sheet"]


def test_reference_has_all_five_classes(registry, cfg):
    assert sorted(classes(build(registry, cfg))) == [
        "cleric", "fighter", "ranger", "rogue", "wizard",
    ]


def test_every_class_has_kits_and_skill_options(registry, cfg):
    for char_class in classes(build(registry, cfg)).values():
        assert len(char_class["kits"]) >= 1
        assert char_class["skill_options"]
        assert char_class["skill_count"] >= 1


def test_fighter_kits_are_listed_with_items_equip_and_gold(registry, cfg):
    kits = {k["id"]: k for k in classes(build(registry, cfg))["fighter"]["kits"]}
    assert sorted(kits) == ["a", "b", "c"]
    assert "chain_mail" in kits["a"]["items"]
    assert kits["a"]["equip"] == ["chain_mail", "greatsword"]
    assert kits["a"]["gold_cp"] == 400


def test_fighter_class_data(registry, cfg):
    fighter = classes(build(registry, cfg))["fighter"]
    char_class = registry.get("class", "fighter")
    assert fighter["skill_options"] == list(char_class.skill_choices.options)
    assert fighter["skill_count"] == char_class.skill_choices.count
    assert fighter["mastery_count"] == char_class.weapon_mastery_count
    assert fighter["fighting_style"] is True
    assert "defense" in fighter["fighting_style_ids"]
    assert fighter["spellcasting"] is None


def test_fighter_masteries_include_longsword_but_wizard_has_none(registry, cfg):
    by_class = classes(build(registry, cfg))
    assert "longsword" in by_class["fighter"]["mastery_weapon_ids"]
    assert "longsword" not in by_class["wizard"]["mastery_weapon_ids"]


def test_mastery_weapons_all_have_mastery_and_class_trains_them(registry, cfg):
    from ai_dm.rules.derived import weapon_proficient

    for class_id, data in classes(build(registry, cfg)).items():
        char_class = registry.get("class", class_id)
        for weapon_id in data["mastery_weapon_ids"]:
            weapon = registry.get("weapon", weapon_id)
            assert weapon.mastery is not None
            assert weapon_proficient(char_class, weapon)


def test_class_without_fighting_style_has_no_style_ids(registry, cfg):
    wizard = classes(build(registry, cfg))["wizard"]
    assert wizard["fighting_style"] is False
    assert wizard["fighting_style_ids"] == []


def test_wizard_spells_are_level_one_and_cantrips_level_zero(registry, cfg):
    wizard = classes(build(registry, cfg))["wizard"]
    assert wizard["spell_ids"]
    assert wizard["cantrip_ids"]
    for spell_id in wizard["spell_ids"]:
        spell = registry.get("spell", spell_id)
        assert spell.level == 1
        assert "wizard" in spell.classes
    for spell_id in wizard["cantrip_ids"]:
        assert registry.get("spell", spell_id).level == 0


def test_wizard_spellcasting_numbers_come_from_class(registry, cfg):
    wizard = classes(build(registry, cfg))["wizard"]
    casting = registry.get("class", "wizard").spellcasting
    assert wizard["spellcasting"] == {
        "cantrips": casting.cantrips, "spells": casting.spells, "prepared": casting.prepared,
    }


def test_fire_bolt_is_cantrip_of_wizard_not_fighter(registry, cfg):
    by_class = classes(build(registry, cfg))
    assert "fire_bolt" in by_class["wizard"]["cantrip_ids"]
    assert by_class["fighter"]["cantrip_ids"] == []
    assert by_class["fighter"]["spell_ids"] == []


def test_reference_has_four_species_with_choices(registry, cfg):
    species = {s["id"]: s for s in reference(build(registry, cfg))["species"]}
    assert sorted(species) == ["dwarf", "elf", "halfling", "human"]
    assert sorted(species["human"]["choices"]) == ["feat", "skill"]
    assert species["dwarf"]["choices"] == []


def test_origin_feats_have_picks(registry, cfg):
    feats = {f["id"]: f["picks"] for f in reference(build(registry, cfg))["origin_feats"]}
    assert feats["skilled"] == 3
    assert feats["alert"] == 0
    assert "defense" not in feats


def test_tables_are_in_reference(registry, cfg):
    data = reference(build(registry, cfg))
    assert sorted(data["standard_array"]) == [8, 10, 12, 13, 14, 15]
    assert data["point_buy"]["budget"] == 27
    assert data["point_buy"]["cost"]["15"] == 9
    assert data["explicit"] == {"min": 3, "max": 20}


def test_world_comes_from_the_task(registry, cfg):
    world = reference(build(registry, cfg))["world"]
    assert world["npc_ids"] == ["grakh", "innkeeper"]
    assert world["location_ids"] == ["cellar", "lame_goose", "vale"]
    assert world["god_ids"] == ["sun"]
    assert world["taken_names"] == ["Гарт", "Гракх"]


def test_limits_are_in_reference(registry, cfg):
    limits = reference(build(registry, cfg))["limits"]
    assert {2, 3, 200, 300, 5000} <= set(limits.values())


def test_reference_keeps_background_part(registry, cfg):
    data = reference(build(registry, cfg))
    assert len(data["examples"]) == 4
    assert "alert" in data["origin_feat_ids"]
    assert "thieves_tools" in data["tool_ids"]
    assert data["item_ids"]["spear"] == registry.get("weapon", "spear").cost_cp
    assert data["budget_cp"] == 5000


def test_reference_has_no_world_items(registry, cfg):
    from ai_dm.rules.custom_items import as_item
    from ai_dm.state.world import CustomItem

    custom = CustomItem(id="custom_1", name="Ключ", cost_cp=5, created_s=0)
    overlay = registry.with_items({"item": [as_item(custom)]})
    request = build(overlay, cfg)
    assert "custom_1" not in reference(request)["item_ids"]


def test_message_has_description_feedback_and_previous(registry, cfg):
    previous = {"name": "Старый", "class_id": "fighter"}
    request = build(registry, cfg, feedback="сделай мрачнее", previous=previous)
    assert len(request.messages) == 1
    assert request.messages[0].role == "user"
    data = json.loads(request.messages[0].content[0].text)
    assert data == {
        "description": "Сирота-воин", "feedback": "сделай мрачнее", "previous": previous,
    }


def test_message_defaults_have_empty_feedback_and_null_previous(registry, cfg):
    data = json.loads(build(registry, cfg).messages[0].content[0].text)
    assert data == {"description": "Сирота-воин", "feedback": "", "previous": None}


def test_prefix_is_same_for_two_descriptions(registry, cfg):
    first = build(registry, cfg, description="Сирота-воин")
    second = build(registry, cfg, description="Хитрая плутовка")
    assert first.system == second.system
    assert first.messages != second.messages


def test_prefix_is_same_with_feedback_and_previous(registry, cfg):
    first = build(registry, cfg)
    second = build(registry, cfg, feedback="мрачнее", previous={"name": "Старый"})
    assert first.system == second.system
    assert first.messages != second.messages


def test_other_world_changes_only_the_reference_block(registry, cfg):
    first = build(registry, cfg)
    second = build(registry, cfg, taken_names=["Другой"])
    assert first.system[0] == second.system[0]
    assert first.system[1] != second.system[1]


def test_reference_is_stable_between_builds(registry, cfg):
    assert build(registry, cfg).system == build(registry, cfg).system


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
    assert (request.max_tokens, request.effort) == (profile.max_tokens, profile.effort)


def test_builder_does_not_need_a_bundle(registry, cfg):
    ctx = creation(registry, cfg)
    assert not hasattr(ctx, "bundle")
    HeroPromptBuilder(app_cfg()).build(ctx, "x", "hero_sheet")


def test_world_text_is_ignored(registry, cfg):
    ctx = creation(registry, cfg)
    builder = HeroPromptBuilder(app_cfg())
    assert builder.build(ctx, "x", "hero_sheet") == builder.build(
        ctx, "x", "hero_sheet", world_text="МИР"
    )


def test_same_builder_serves_both_modes(registry, cfg):
    builder = HeroPromptBuilder(app_cfg())
    sheet = builder.build(creation(registry, cfg), "x", "hero_sheet")
    background_ctx = CreationContext(registry, cfg, BackgroundTask("fighter"))
    background = builder.build(background_ctx, "x", "hero_background")
    assert [t.name for t in sheet.tools] == ["hero_sheet"]
    assert [t.name for t in background.tools] == ["background_spec"]
    assert sheet.system[0] != background.system[0]
    assert "classes" not in json.loads(background.system[1].text)


def test_background_mode_message_is_class_and_description(registry, cfg):
    ctx = CreationContext(registry, cfg, BackgroundTask("fighter", ("perception",)))
    request = HeroPromptBuilder(app_cfg()).build(ctx, "акробат", "hero_background")
    data = json.loads(request.messages[0].content[0].text)
    assert data == {
        "class": "fighter", "class_skills": ["perception"], "description": "акробат",
    }


def test_class_data_has_name_from_registry(registry, cfg):
    by_class = classes(build(registry, cfg))
    assert by_class["fighter"]["name"] == registry.get("class", "fighter").name
    assert by_class["wizard"]["name"] == registry.get("class", "wizard").name


def test_ranger_fighting_style_comes_later_than_level_one(registry, cfg):
    ranger = classes(build(registry, cfg))["ranger"]
    assert ranger["fighting_style"] is False
    assert ranger["fighting_style_ids"] == []


def test_species_have_names_from_registry(registry, cfg):
    species = {s["id"]: s for s in reference(build(registry, cfg))["species"]}
    for species_id, data in species.items():
        assert data["name"] == registry.get("species", species_id).name


def test_point_buy_cost_table_has_no_budget_row(registry, cfg):
    cost = reference(build(registry, cfg))["point_buy"]["cost"]
    assert "budget" not in cost
    assert sorted(cost, key=int) == ["8", "9", "10", "11", "12", "13", "14", "15"]
    assert cost["8"] == 0


def test_limits_have_named_keys(registry, cfg):
    limits = reference(build(registry, cfg))["limits"]
    expected = {
        "motive_max": 200, "means_max": 3, "opportunity_max": 2,
        "background_description_max": 300, "background_budget_cp": 5000,
    }
    assert expected.items() <= limits.items()


def test_every_builder_limit_constant_is_in_limits(registry, cfg):
    from ai_dm.rules import builder

    limits = reference(build(registry, cfg))["limits"]
    constants = {
        name: getattr(builder, name) for name in dir(builder)
        if name.startswith(("MOTIVE_", "MEANS_", "OPPORTUNITY_", "BACKGROUND_"))
        and isinstance(getattr(builder, name), int)
    }
    assert constants
    for name, value in constants.items():
        assert value in limits.values(), name


# Б2а (A2): class_data переведён на rules.hero_options -- справочник листа байт-в-байт прежний
# (снимок снят с кода Б1 до правок Б2 на пак vale)

def test_sheet_reference_block_is_byte_identical_to_the_b1_snapshot(registry, cfg):
    from hero_kit import sheet_task, vale_pack

    ctx = CreationContext(registry, cfg, sheet_task(vale_pack(registry)))
    snapshots = Path(__file__).resolve().parents[2] / "fixtures" / "snapshots"
    snapshot = snapshots / "sheet_reference_vale.json"
    text = HeroPromptBuilder(app_cfg()).sheet_reference_block(ctx)
    assert text == snapshot.read_text(encoding="utf-8")
