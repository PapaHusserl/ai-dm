# Б2а (B2-PLAN, A2): rules.hero_options -- допустимые множества шагов пошагового создания героя.
# Ожидаемый API (ТРЕБОВАНИЕ к коду Б2а): species_options/class_options/background_options(registry),
#   class_skill_options(char_class, taken), mastery_weapons(registry, char_class),
#   has_fighting_style(char_class), fighting_styles(registry), class_spells(registry, class_id,
#   level), spell_counts(char_class) -> (заговоры, заклинания, подготовленные),
#   origin_feats(registry, exclude_feat), feat_pick_options(registry, taken_skills, taken_tools),
#   species_skill_options(taken_skills), standard_array(registry), point_buy_table(registry) ->
#   (стоимость, бюджет), kit_options(char_class), kit_label(registry, kit).
from ai_dm.content.models.common import SKILLS


def ids(items):
    return [item.id for item in items]


def test_species_options_are_the_four_srd_species(registry):
    from ai_dm.rules.hero_options import species_options

    assert sorted(ids(species_options(registry))) == ["dwarf", "elf", "halfling", "human"]


def test_class_options_are_the_five_classes(registry):
    from ai_dm.rules.hero_options import class_options

    assert sorted(ids(class_options(registry))) == [
        "cleric", "fighter", "ranger", "rogue", "wizard",
    ]


def test_background_options_are_the_four_srd_backgrounds(registry):
    from ai_dm.rules.hero_options import background_options

    assert sorted(ids(background_options(registry))) == [
        "acolyte", "criminal", "sage", "soldier",
    ]


def test_fighter_mastery_weapons_contain_longsword(registry):
    from ai_dm.rules.hero_options import mastery_weapons

    weapons = mastery_weapons(registry, registry.get("class", "fighter"))
    assert "longsword" in ids(weapons)
    assert all(w.mastery is not None for w in weapons)


def test_mastery_weapons_skip_world_items(registry):
    from ai_dm.rules.hero_options import mastery_weapons

    weapons = mastery_weapons(registry, registry.get("class", "fighter"))
    assert all(w.source != "world" for w in weapons)


def test_wizard_mastery_weapons_have_no_martial_longsword(registry):
    from ai_dm.rules.hero_options import mastery_weapons

    wizard = registry.get("class", "wizard")
    assert wizard.weapon_mastery_count == 0
    assert "longsword" not in ids(mastery_weapons(registry, wizard))


def test_mastery_weapons_are_the_weapons_class_data_listed(registry):
    from ai_dm.master.hero import class_data
    from ai_dm.rules.hero_options import mastery_weapons

    for char_class in registry.all("class"):
        weapons = mastery_weapons(registry, char_class)
        assert ids(weapons) == class_data(registry, char_class)["mastery_weapon_ids"]


def test_has_fighting_style_for_fighter(registry):
    from ai_dm.rules.hero_options import has_fighting_style

    assert has_fighting_style(registry.get("class", "fighter")) is True


def test_has_no_fighting_style_at_level_1_for_ranger_rogue_cleric_wizard(registry):
    # план B2 (A0.5) считает, что у следопыта стиль на 1 уровне; в контенте он со 2-го
    from ai_dm.rules.hero_options import has_fighting_style

    for class_id in ("ranger", "rogue", "cleric", "wizard"):
        assert has_fighting_style(registry.get("class", class_id)) is False


def test_fighting_styles_are_feats_of_that_category(registry):
    from ai_dm.rules.hero_options import fighting_styles

    styles = fighting_styles(registry)
    assert sorted(ids(styles)) == [
        "archery", "defense", "great_weapon_fighting", "two_weapon_fighting",
    ]
    assert all(f.category == "fighting_style" for f in styles)


def test_wizard_cantrips_are_only_wizard_level_0_spells(registry):
    from ai_dm.rules.hero_options import class_spells

    spells = class_spells(registry, "wizard", 0)
    assert ids(spells)
    assert all(s.level == 0 and "wizard" in s.classes for s in spells)
    assert "fire_bolt" in ids(spells)


def test_wizard_first_circle_spells_are_level_1(registry):
    from ai_dm.rules.hero_options import class_spells

    spells = class_spells(registry, "wizard", 1)
    assert "magic_missile" in ids(spells)
    assert all(s.level == 1 and "wizard" in s.classes for s in spells)


def test_class_spells_match_class_data_lists(registry):
    from ai_dm.master.hero import class_data
    from ai_dm.rules.hero_options import class_spells

    for char_class in registry.all("class"):
        data = class_data(registry, char_class)
        assert ids(class_spells(registry, char_class.id, 0)) == data["cantrip_ids"]
        assert ids(class_spells(registry, char_class.id, 1)) == data["spell_ids"]


def test_fighter_has_no_spells(registry):
    from ai_dm.rules.hero_options import class_spells

    assert class_spells(registry, "fighter", 0) == []
    assert class_spells(registry, "fighter", 1) == []


def test_spell_counts_per_class(registry):
    from ai_dm.rules.hero_options import spell_counts

    assert spell_counts(registry.get("class", "wizard")) == (3, 6, 4)
    assert spell_counts(registry.get("class", "cleric")) == (3, 4, 4)
    assert spell_counts(registry.get("class", "ranger")) == (0, 2, 2)


def test_spell_counts_of_non_caster_are_zeros(registry):
    from ai_dm.rules.hero_options import spell_counts

    assert spell_counts(registry.get("class", "fighter")) == (0, 0, 0)


def test_origin_feats_without_exclusion_are_all_four(registry):
    from ai_dm.rules.hero_options import origin_feats

    assert sorted(ids(origin_feats(registry, None))) == [
        "alert", "magic_initiate", "savage_attacker", "skilled",
    ]


def test_origin_feats_exclude_background_feat_when_not_repeatable(registry):
    from ai_dm.rules.hero_options import origin_feats

    assert "alert" not in ids(origin_feats(registry, "alert"))
    assert "savage_attacker" not in ids(origin_feats(registry, "savage_attacker"))


def test_origin_feats_keep_repeatable_background_feat(registry):
    from ai_dm.rules.hero_options import origin_feats

    assert "skilled" in ids(origin_feats(registry, "skilled"))
    assert "magic_initiate" in ids(origin_feats(registry, "magic_initiate"))


def test_origin_feats_exclusion_keeps_the_others(registry):
    from ai_dm.rules.hero_options import origin_feats

    assert sorted(ids(origin_feats(registry, "alert"))) == [
        "magic_initiate", "savage_attacker", "skilled",
    ]


def pick_values(options):
    return [value for value, _ in options]


def test_feat_pick_options_without_taken_have_all_skills_and_tools(registry):
    from ai_dm.rules.hero_options import feat_pick_options

    values = pick_values(feat_pick_options(registry, set(), set()))
    assert set(SKILLS) <= set(values)
    assert {"thieves_tools", "gaming_set", "calligraphers_supplies"} <= set(values)


def test_feat_pick_options_drop_taken_skills_and_tool(registry):
    from ai_dm.rules.hero_options import feat_pick_options

    values = pick_values(feat_pick_options(registry, {"athletics", "stealth"}, {"gaming_set"}))
    assert "athletics" not in values
    assert "stealth" not in values
    assert "gaming_set" not in values
    assert "perception" in values
    assert "thieves_tools" in values


def test_feat_pick_options_have_russian_labels(registry):
    from ai_dm.rules.hero_options import feat_pick_options

    options = feat_pick_options(registry, set(), set())
    labels = dict(options)
    assert labels["athletics"] == "Атлетика"
    assert all(label.strip() for _, label in options)


def test_class_skill_options_drop_taken_skills(registry):
    from ai_dm.rules.hero_options import class_skill_options

    fighter = registry.get("class", "fighter")
    options = class_skill_options(fighter, {"athletics", "intimidation"})
    assert "athletics" not in options
    assert "intimidation" not in options
    assert "perception" in options
    assert set(options) <= set(fighter.skill_choices.options)


def test_class_skill_options_without_taken_are_class_options(registry):
    from ai_dm.rules.hero_options import class_skill_options

    fighter = registry.get("class", "fighter")
    assert class_skill_options(fighter, set()) == list(fighter.skill_choices.options)


def test_species_skill_options_drop_taken_skills(registry):
    from ai_dm.rules.hero_options import species_skill_options

    options = species_skill_options({"stealth", "athletics"})
    assert "stealth" not in options
    assert "athletics" not in options
    assert "perception" in options
    assert len(options) == len(SKILLS) - 2


def test_standard_array_is_the_registry_table(registry):
    from ai_dm.rules.hero_options import standard_array

    assert sorted(standard_array(registry)) == [8, 10, 12, 13, 14, 15]


def test_point_buy_table_has_8_to_15_and_budget_27(registry):
    from ai_dm.rules.hero_options import point_buy_table

    cost, budget = point_buy_table(registry)
    assert sorted(cost) == list(range(8, 16))
    assert cost[8] == 0
    assert cost[15] == 9
    assert budget == 27


def test_kit_options_are_the_class_starting_kits(registry):
    from ai_dm.rules.hero_options import kit_options

    fighter = registry.get("class", "fighter")
    assert [k.id for k in kit_options(fighter)] == ["a", "b", "c"]


def test_kit_label_names_items_in_russian_and_money(registry):
    from ai_dm.rules.hero_options import kit_label

    kit = registry.get("class", "fighter").starting_kits[0]
    label = kit_label(registry, kit)
    assert "кольчуга" in label.lower()
    assert "зм" in label
    assert "chain_mail" not in label


def test_kit_label_of_gold_only_kit_shows_gold(registry):
    from ai_dm.rules.hero_options import kit_label

    kit = registry.get("class", "fighter").starting_kits[2]
    label = kit_label(registry, kit)
    assert "155" in label
    assert "зм" in label


# добивка по выжившим мутантам mutmut (Б2а)

def test_kit_label_exact_texts(registry):
    from ai_dm.rules.hero_options import kit_label

    fighter = registry.get("class", "fighter").starting_kits
    assert kit_label(registry, fighter[0]) == (
        "Кольчуга, Двуручный меч, Копьё, Набор путешественника; +4 зм"
    )
    assert kit_label(registry, fighter[2]) == "155 зм золотом"


def test_kit_label_counts_repeated_items(registry):
    from ai_dm.rules.hero_options import kit_label

    kit = registry.get("class", "wizard").starting_kits[0]
    assert kit_label(registry, kit) == (
        "Кинжал ×2, Боевой посох, Ряса, Набор путешественника; +5 зм"
    )


def test_kit_label_folds_twenty_arrows_of_ranger_kit(registry):
    from ai_dm.rules.hero_options import kit_label

    kit = registry.get("class", "ranger").starting_kits[0]
    assert kit_label(registry, kit) == (
        "Проклёпанная кожа, Скимитар, Короткий меч, Длинный лук, Стрелы ×20, Колчан, "
        "Фокусировка друидов, Набор путешественника; +7 зм"
    )


def test_kit_label_shows_id_of_unknown_item(registry):
    from types import SimpleNamespace

    from ai_dm.rules.hero_options import kit_label

    kit = SimpleNamespace(items=["no_such_item", "no_such_item"], gold_cp=0)
    assert kit_label(registry, kit) == "no_such_item ×2"


def test_spell_counts_without_numbers_are_zeros():
    from types import SimpleNamespace

    from ai_dm.rules.hero_options import spell_counts

    casting = SimpleNamespace(cantrips=None, spells=None, prepared=None)
    assert spell_counts(SimpleNamespace(spellcasting=casting)) == (0, 0, 0)


def test_mastery_weapons_skip_world_source_weapons(registry):
    from ai_dm.rules.hero_options import mastery_weapons

    fighter = registry.get("class", "fighter")
    sword = registry.get("weapon", "longsword")
    world = sword.model_copy(update={"id": "world_sword", "source": "world"})
    other = ContentRegistryStub(registry, world)
    assert "world_sword" not in ids(mastery_weapons(other, fighter))
    assert "longsword" in ids(mastery_weapons(other, fighter))


class ContentRegistryStub:
    # реестр с одним добавленным оружием; остальное берёт у настоящего
    def __init__(self, registry, weapon):
        self.registry = registry
        self.weapon = weapon

    def all(self, kind):
        items = self.registry.all(kind)
        return [*items, self.weapon] if kind == "weapon" else items
