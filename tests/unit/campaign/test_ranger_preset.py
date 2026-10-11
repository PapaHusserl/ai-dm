# Пресет следопыта 3 ур. в паке: выборы уровней и спутник (docs/decisions/ranger-2-5-plan.md,
# разд. 4 п. 4, разд. 5 п. 8, решения 1-4). Ожидаемый API:
#   HeroPreset.level_choices: list[LevelChoices] (YAML: список словарей с полем level и выборами)
#   HeroPreset.companion: {name, kind, notes} -> HeroState.companion после сборки
#   build_hero: после каждого level_up применяются выборы этого уровня; ошибка выбора или нет
#       обязательного выбора (подкласс на 3 ур., стиль и экспертиза на 2) -> StartRefused
import pytest
import yaml
from campaign_kit import ROOT, SAVED_AT, VALE_DIR, default_files, load, pack_errors, write_pack
from test_dragon_pack import dragon_world

SPELLS = ["cure_wounds", "ensnaring_strike", "speak_with_animals", "fog_cloud"]
CHOICES = [
    {"level": 2, "fighting_style": "archery", "expertise": ["survival"]},
    {"level": 3, "subclass_id": "beast_master", "spells_add": SPELLS},
]
COMPANION = {"name": "Акела", "kind": "волк", "notes": "доверен Йоргеном-зверолов"}


def grey_files(level=3, level_choices=CHOICES, companion=COMPANION):
    files = default_files()
    preset = yaml.safe_load((VALE_DIR / "heroes" / "grey.yaml").read_text(encoding="utf-8"))
    preset["level"] = level
    preset["xp"] = 900
    preset["location_id"] = "tavern"
    if level_choices is not None:
        preset["level_choices"] = level_choices
    if companion is not None:
        preset["companion"] = companion
    files["heroes/grey.yaml"] = preset
    files["campaign.yaml"]["start"]["heroes"] = ["arn", "grey"]
    return files


def build(tmp_path, registry, cfg, files, hero="grey"):
    from ai_dm.game.starter import new_world_from_pack

    pack = load(write_pack(tmp_path, files), registry)
    return new_world_from_pack(
        registry, cfg, pack, hero=hero, seed=1, world_id="w1", saved_at=SAVED_AT
    )


def grey(tmp_path, registry, cfg, **kwargs):
    return build(tmp_path, registry, cfg, grey_files(**kwargs)).heroes[0]


def test_preset_keeps_level_choices_in_order(tmp_path, registry):
    pack = load(write_pack(tmp_path, grey_files()), registry)
    preset = [p for p in pack.heroes if p.id == "grey"][0]
    assert [c.level for c in preset.level_choices] == [2, 3]
    assert preset.level_choices[1].subclass_id == "beast_master"


def test_preset_with_unknown_level_choice_key_is_pack_error(tmp_path, registry):
    files = grey_files(level_choices=[{"level": 2, "no_such_field": 1}])
    assert pack_errors(write_pack(tmp_path, files), registry) is not None


def test_ranger_preset_is_built_at_level_3_with_xp(tmp_path, registry, cfg):
    hero = grey(tmp_path, registry, cfg)
    assert hero.sheet.level == 3
    assert hero.sheet.xp == 900


def test_ranger_preset_gets_subclass_style_and_expertise(tmp_path, registry, cfg):
    hero = grey(tmp_path, registry, cfg)
    assert hero.sheet.subclass_id == "beast_master"
    assert "archery" in hero.sheet.feats
    assert hero.sheet.skill_expertise == ["survival"]


def test_ranger_preset_gets_four_prepared_spells(tmp_path, registry, cfg):
    hero = grey(tmp_path, registry, cfg)
    assert set(SPELLS) <= set(hero.sheet.prepared_of())


def test_ranger_preset_has_level_3_resources(tmp_path, registry, cfg):
    resources = grey(tmp_path, registry, cfg).creature.resources
    assert resources["spell_slot:1"].max == 3
    assert resources["favored_enemy"].max == 2


def test_companion_is_carried_to_the_hero(tmp_path, registry, cfg):
    companion = grey(tmp_path, registry, cfg).companions[0]
    assert companion.name == "Акела"
    assert companion.kind == "волк"
    assert companion.notes == "доверен Йоргеном-зверолов"


def test_hero_without_companion_has_none(tmp_path, registry, cfg):
    hero = build(tmp_path, registry, cfg, default_files(), hero="arn").heroes[0]
    assert hero.companions == []


def test_level_3_without_subclass_choice_refuses_start(tmp_path, registry, cfg):
    from ai_dm.campaign.build import StartRefused

    files = grey_files(level_choices=[CHOICES[0]])
    with pytest.raises(StartRefused) as err:
        build(tmp_path, registry, cfg, files)
    text = str(err.value).lower()
    assert "подкласс" in text or "subclass" in text


def test_level_3_without_any_choices_refuses_start(tmp_path, registry, cfg):
    from ai_dm.campaign.build import StartRefused

    with pytest.raises(StartRefused):
        build(tmp_path, registry, cfg, grey_files(level_choices=None))


def test_missing_expertise_refuses_start(tmp_path, registry, cfg):
    from ai_dm.campaign.build import StartRefused

    files = grey_files(level_choices=[{"level": 2, "fighting_style": "archery"}, CHOICES[1]])
    with pytest.raises(StartRefused):
        build(tmp_path, registry, cfg, files)


def test_wrong_fighting_style_refuses_start(tmp_path, registry, cfg):
    from ai_dm.campaign.build import StartRefused

    wrong = [{"level": 2, "fighting_style": "alert", "expertise": ["survival"]}, CHOICES[1]]
    with pytest.raises(StartRefused):
        build(tmp_path, registry, cfg, grey_files(level_choices=wrong))


def test_level_1_ranger_preset_needs_no_choices(tmp_path, registry, cfg):
    hero = grey(tmp_path, registry, cfg, level=1, level_choices=None, companion=None)
    assert hero.sheet.level == 1


# регрессия: воин и плут без выборов собираются как раньше

def test_fighter_preset_at_level_3_builds_without_choices(tmp_path, registry, cfg):
    files = default_files()
    files["heroes/arn.yaml"]["level"] = 3
    files["heroes/arn.yaml"]["xp"] = 900
    hero = build(tmp_path, registry, cfg, files, hero="arn").heroes[0]
    assert hero.sheet.level == 3
    assert hero.sheet.class_id == "fighter"
    assert hero.creature.resources["second_wind"].max == 2


def test_fighter_preset_at_level_5_without_asi_choice_refuses_start(tmp_path, registry, cfg):
    from ai_dm.campaign.build import StartRefused

    files = default_files()
    files["heroes/arn.yaml"]["level"] = 5
    with pytest.raises(StartRefused):
        build(tmp_path, registry, cfg, files, hero="arn")


def test_fighter_preset_at_level_5_with_asi_choice_builds(tmp_path, registry, cfg):
    files = default_files()
    files["heroes/arn.yaml"]["level"] = 5
    files["heroes/arn.yaml"]["level_choices"] = [{"level": 4, "asi": {"str": 2}}]
    hero = build(tmp_path, registry, cfg, files, hero="arn").heroes[0]
    assert hero.sheet.level == 5


def test_fighter_preset_at_level_5_with_asi_choice_raises_ability(tmp_path, registry, cfg):
    files = default_files()
    files["heroes/arn.yaml"]["level"] = 5
    files["heroes/arn.yaml"]["level_choices"] = [{"level": 4, "asi": {"str": 2}}]
    plain = build(tmp_path, registry, cfg, default_files(), hero="arn").heroes[0]
    hero = build(tmp_path, registry, cfg, files, hero="arn").heroes[0]
    assert hero.sheet.abilities["str"] == plain.sheet.abilities["str"] + 2


# реальный пак Дракона: Грей 3 ур., Повелитель зверей, волк Акела

def test_dragon_grey_is_level_3_ranger_with_xp_900(cfg):
    hero = dragon_world(cfg).heroes[0]
    assert hero.sheet.class_id == "ranger"
    assert hero.sheet.level == 3
    assert hero.sheet.xp == 900


def test_dragon_grey_is_beast_master_with_archery_and_survival_expertise(cfg):
    sheet = dragon_world(cfg).heroes[0].sheet
    assert sheet.subclass_id == "beast_master"
    assert "archery" in sheet.feats
    assert sheet.skill_expertise == ["survival"]


def test_dragon_grey_has_four_prepared_spells_and_the_mark(cfg, registry):
    from ai_dm.rules.derived import always_prepared

    hero = dragon_world(cfg).heroes[0]
    assert set(SPELLS) <= set(hero.sheet.prepared_of())
    assert len([s for s in hero.sheet.prepared_of() if s != "hunters_mark"]) == 4
    assert "hunters_mark" in always_prepared(hero, registry)


def test_dragon_grey_has_wolf_akela(cfg):
    assert dragon_world(cfg).heroes[0].companions[0].name == "Акела"


def test_dragon_grey_preset_file_is_level_3():
    path = ROOT / "campaigns" / "drunk_dragon" / "heroes" / "grey.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["level"] == 3
    assert data["xp"] == 900
    assert data["companion"]["name"] == "Акела"


# К0а: пресет собирается атомарно -- level_history по числу уровней, companions списком, без
# pending_level

def test_preset_hero_has_level_history_of_its_level(tmp_path, registry, cfg):
    hero = grey(tmp_path, registry, cfg)
    assert hero.sheet.level == 3
    assert hero.sheet.level_history == ["ranger"] * 3


def test_preset_hero_has_one_class_entry_with_subclass(tmp_path, registry, cfg):
    hero = grey(tmp_path, registry, cfg)
    assert [(c.class_id, c.level, c.subclass_id) for c in hero.sheet.classes] == [
        ("ranger", 3, hero.sheet.subclass_id)
    ]


def test_preset_hero_has_no_pending_level(tmp_path, registry, cfg):
    assert grey(tmp_path, registry, cfg).pending_level is None


def test_preset_companion_becomes_a_list_of_one(tmp_path, registry, cfg):
    hero = grey(tmp_path, registry, cfg)
    assert len(hero.companions) == 1
    assert hero.companions[0].name == "Акела"


def test_preset_hero_hit_dice_pool_is_by_class_die(tmp_path, registry, cfg):
    resources = grey(tmp_path, registry, cfg).creature.resources
    assert resources["hit_dice:d10"].max == 3
    assert "hit_dice" not in resources


def test_preset_hero_spells_are_stored_under_the_class(tmp_path, registry, cfg):
    hero = grey(tmp_path, registry, cfg)
    assert set(hero.sheet.spells_prepared) == {"ranger"}
