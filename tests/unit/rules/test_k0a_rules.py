# К0а (docs/K0-PLAN.md, A3): правила на списке классов -- hp_gain / apply_level, apply_level_choices
# по primary и feature_choices, кости хитов по граням (hit_dice:dN), always_prepared с
# spells_always_prepared, start/drop_concentration с кругом.
import pytest
from ranger_kit import make_class_hero, make_ranger, ranger_at

from ai_dm.config.settings import load_rules_config
from ai_dm.core.clock import GameClock
from ai_dm.core.rng import Rng
from ai_dm.rules import progression
from ai_dm.rules.derived import always_prepared, hero_feature_ids, resource_maxes
from ai_dm.rules.progression import (
    apply_level,
    apply_level_choices,
    choice_errors,
    hp_gain,
    level_up,
    next_choice,
    spell_candidates,
    spells_left,
    sync_resources,
)
from ai_dm.rules.rests import hit_dice_pools, long_rest, short_rest
from ai_dm.rules.spellcasting import drop_concentration, start_concentration
from ai_dm.state.creature import (
    ActiveEffect,
    AppliedCondition,
    Concentration,
    CreatureState,
    Expiry,
    ResourcePool,
)
from ai_dm.state.hero import ClassLevel, GrantedSpell, LevelChoices
from ai_dm.state.world import NPC, WorldState

SCORES = {"str": 12, "dex": 14, "con": 14, "int": 10, "wis": 13, "cha": 8}


class FixedRng(Rng):
    def __init__(self, *faces):
        super().__init__(1)
        self.faces = list(faces)
        self.sides = []

    def randbelow(self, n):
        self.sides.append(n)
        return self.faces.pop(0) - 1


def top_level(registry):
    if hasattr(progression, "MAX_LEVEL"):
        return progression.MAX_LEVEL
    return progression.max_level(registry)


def fighter():
    return make_class_hero("fighter", SCORES)


def two_class_hero(registry):
    hero = fighter()
    hero.sheet.classes = [ClassLevel(class_id="fighter", level=3), ClassLevel(class_id="wizard",
        level=2)]
    hero.sheet.level_history = ["fighter"] * 3 + ["wizard"] * 2
    return hero


# hp_gain

def test_hp_gain_average_is_half_die_plus_one_plus_con(registry):
    # d10: 6 + мод. ТЕЛ (+2)
    assert hp_gain(fighter(), registry, "average", None) == 8


def test_hp_gain_roll_uses_class_die_and_con(registry):
    rng = FixedRng(7)
    assert hp_gain(fighter(), registry, "roll", rng) == 9
    assert rng.sides == [10]


def test_hp_gain_is_at_least_one(registry):
    hero = fighter()
    hero.sheet.abilities["con"] = 1
    assert hp_gain(hero, registry, "roll", FixedRng(1)) == 1


def test_hp_gain_roll_without_rng_is_refused(registry):
    with pytest.raises(ValueError):
        hp_gain(fighter(), registry, "roll", None)


def test_hp_gain_unknown_method_is_refused(registry):
    with pytest.raises(ValueError):
        hp_gain(fighter(), registry, "max", None)


def test_hp_gain_does_not_change_the_hero(registry):
    hero = fighter()
    before = hero.model_dump_json()
    hp_gain(hero, registry, "average", None)
    assert hero.model_dump_json() == before


# apply_level

def test_apply_level_raises_primary_level(registry):
    hero = fighter()
    apply_level(hero, registry, 5)
    assert hero.sheet.primary.level == 2
    assert hero.sheet.level == 2


def test_apply_level_appends_class_to_history(registry):
    hero = fighter()
    apply_level(hero, registry, 5)
    assert hero.sheet.level_history == ["fighter", "fighter"]


def test_apply_level_adds_the_given_gain_to_max_and_current(registry):
    hero = fighter()
    hp = hero.creature.hp_max
    apply_level(hero, registry, 9)
    assert hero.creature.hp_max == hp + 9
    assert hero.creature.hp_current == 10 + 9


def test_apply_level_syncs_hit_dice_pool(registry):
    hero = fighter()
    sync_resources(hero, registry)
    apply_level(hero, registry, 5)
    assert hero.creature.resources["hit_dice:d10"].max == 2


def test_level_up_equals_hp_gain_plus_apply_level(registry):
    first, second = fighter(), fighter()
    level_up(first, registry, hp_method="average")
    apply_level(second, registry, hp_gain(second, registry, "average", None))
    assert first.model_dump() == second.model_dump()


def test_level_up_at_the_top_is_refused_before_any_change(registry):
    hero = fighter()
    top = top_level(registry)
    hero.sheet.primary.level = top
    hero.sheet.level_history = ["fighter"] * top
    before = hero.model_dump_json()
    with pytest.raises(ValueError):
        level_up(hero, registry)
    assert hero.model_dump_json() == before


# apply_level_choices

def test_choices_write_subclass_into_primary_class(registry):
    hero = ranger_at(registry, 3)
    assert apply_level_choices(hero, registry, LevelChoices(level=3, subclass_id="hunter")) is None
    assert hero.sheet.primary.subclass_id == "hunter"
    assert hero.sheet.subclass_id == "hunter"


def test_choices_write_feature_choice_as_list(registry):
    hero = ranger_at(registry, 3)
    choices = LevelChoices(
        level=3, subclass_id="hunter", feature_choices={"hunters_prey": ["colossus_slayer"]},
    )
    apply_level_choices(hero, registry, choices)
    assert hero.sheet.feature_choices == {"hunters_prey": ["colossus_slayer"]}


def test_feature_choices_are_copied_not_shared_with_the_draft(registry):
    hero = ranger_at(registry, 3)
    choices = LevelChoices(
        level=3, subclass_id="hunter", feature_choices={"hunters_prey": ["colossus_slayer"]},
    )
    apply_level_choices(hero, registry, choices)
    choices.feature_choices["hunters_prey"].append("horde_breaker")
    assert hero.sheet.feature_choices["hunters_prey"] == ["colossus_slayer"]


def test_choices_add_spells_to_known_and_prepared_of_the_class(registry):
    hero = ranger_at(registry, 3)
    apply_level_choices(hero, registry, LevelChoices(level=3, subclass_id="hunter",
        spells_add=["goodberry"]))
    assert hero.sheet.spells_prepared["ranger"] == ["goodberry"]
    assert hero.sheet.spells_known["ranger"] == ["goodberry"]


def test_choices_asi_raises_ability_and_adds_asi_feat(registry):
    hero = ranger_at(registry, 4)
    apply_level_choices(hero, registry, LevelChoices(level=4, asi={"dex": 2}))
    assert hero.sheet.feats[-1] == "ability_score_improvement"


def test_choice_errors_for_unknown_option_is_option_invalid(registry):
    hero = ranger_at(registry, 3)
    hero.sheet.primary.subclass_id = "hunter"
    choices = LevelChoices(level=3, feature_choices={"hunters_prey": ["nope"]})
    assert "option_invalid" in [code for code, _ in choice_errors(hero, registry, choices)]


def test_choice_errors_checks_every_element_of_the_option_list(registry):
    hero = ranger_at(registry, 3)
    hero.sheet.primary.subclass_id = "hunter"
    choices = LevelChoices(level=3, feature_choices={"hunters_prey": ["colossus_slayer", "nope"]})
    assert [code for code, _ in choice_errors(hero, registry, choices)].count("option_invalid") == 1


def test_choice_errors_valid_option_is_fine(registry):
    hero = ranger_at(registry, 3)
    hero.sheet.primary.subclass_id = "hunter"
    choices = LevelChoices(level=3, feature_choices={"hunters_prey": ["horde_breaker"]})
    assert "option_invalid" not in [code for code, _ in choice_errors(hero, registry, choices)]


def test_next_choice_skips_the_option_already_in_feature_choices(registry):
    hero = ranger_at(registry, 3)
    hero.sheet.primary.subclass_id = "hunter"
    choices = LevelChoices(level=3, feature_choices={"hunters_prey": ["horde_breaker"]})
    assert next_choice(hero, registry, choices) != "hunters_prey"


def test_spell_candidates_exclude_already_prepared(registry):
    hero = ranger_at(registry, 3)
    first = spell_candidates(hero, registry, LevelChoices(level=3))[0]
    hero.sheet.prepared_of().append(first)
    assert first not in spell_candidates(hero, registry, LevelChoices(level=3))


def test_spell_candidates_exclude_spells_of_the_draft(registry):
    hero = ranger_at(registry, 3)
    first = spell_candidates(hero, registry, LevelChoices(level=3))[0]
    assert first not in spell_candidates(hero, registry, LevelChoices(level=3, spells_add=[first]))


def test_spells_left_counts_prepared_of_the_class_and_draft(registry):
    hero = ranger_at(registry, 3)
    empty = spells_left(hero, registry, LevelChoices(level=3))
    hero.sheet.prepared_of().append("goodberry")
    assert spells_left(hero, registry, LevelChoices(level=3)) == empty - 1
    assert spells_left(hero, registry, LevelChoices(level=3, spells_add=["alarm"])) == empty - 2


# resource_maxes / кости хитов

def test_resource_maxes_hit_dice_by_class_die(registry):
    maxes = resource_maxes(two_class_hero(registry), registry)
    assert maxes["hit_dice:d10"] == 3
    assert maxes["hit_dice:d6"] == 2
    assert "hit_dice" not in maxes


def test_resource_maxes_same_die_classes_are_summed(registry):
    hero = fighter()
    hero.sheet.classes = [ClassLevel(class_id="fighter", level=2), ClassLevel(class_id="ranger",
        level=3)]
    hero.sheet.level_history = ["fighter"] * 2 + ["ranger"] * 3
    assert resource_maxes(hero, registry)["hit_dice:d10"] == 5


def test_resource_maxes_one_class_has_one_hit_dice_pool(registry):
    keys = [k for k in resource_maxes(fighter(), registry) if k.startswith("hit_dice")]
    assert keys == ["hit_dice:d10"]


def test_sync_resources_creates_pool_with_full_value(registry):
    hero = fighter()
    sync_resources(hero, registry)
    assert hero.creature.resources["hit_dice:d10"] == ResourcePool(current=1, max=1)


def test_sync_resources_twice_does_not_add_a_second_pool(registry):
    hero = fighter()
    sync_resources(hero, registry)
    sync_resources(hero, registry)
    assert [k for k in hero.creature.resources if k.startswith("hit_dice")] == ["hit_dice:d10"]


# hero_feature_ids / always_prepared

def test_feature_ids_include_every_chosen_option(registry):
    hero = ranger_at(registry, 3)
    hero.sheet.primary.subclass_id = "hunter"
    hero.sheet.feature_choices = {"hunters_prey": ["colossus_slayer"]}
    assert "colossus_slayer" in hero_feature_ids(hero, registry)


def test_feature_ids_ignore_choice_without_such_feature(registry):
    hero = ranger_at(registry, 3)
    hero.sheet.feature_choices = {"hunters_prey": ["no_such_option"]}
    assert "no_such_option" not in hero_feature_ids(hero, registry)


def test_always_prepared_adds_granted_spells_after_feature_spells(registry):
    hero = ranger_at(registry, 3)
    base = always_prepared(hero, registry)
    hero.sheet.spells_always_prepared = [GrantedSpell(spell_id="detect_magic", source="x")]
    assert always_prepared(hero, registry) == base + ["detect_magic"]


def test_always_prepared_without_granted_spells_is_unchanged(registry):
    hero = ranger_at(registry, 3)
    assert always_prepared(hero, registry) == always_prepared(ranger_at(registry, 3), registry)


# rests

def hero_with_pools(registry, **pools):
    hero = fighter()
    hero.creature.hp_max = 40
    hero.creature.hp_current = 5
    hero.creature.resources = {k: ResourcePool(current=c, max=m) for k, (c, m) in pools.items()}
    return hero


def test_hit_dice_pools_sorted_by_faces_descending(registry):
    hero = hero_with_pools(registry, **{"hit_dice:d6": (1, 1), "hit_dice:d10": (2, 2),
        "hit_dice:d8": (1, 1)})
    assert [(k, f) for k, _, f in hit_dice_pools(hero.creature)] == [
        ("hit_dice:d10", 10), ("hit_dice:d8", 8), ("hit_dice:d6", 6),
    ]


def test_hit_dice_pools_ignore_other_pools(registry):
    hero = hero_with_pools(registry, **{"hit_dice:d10": (1, 1), "second_wind": (1, 2),
        "hit_dice_x": (1, 1)})
    assert [k for k, _, _ in hit_dice_pools(hero.creature)] == ["hit_dice:d10"]


def test_hit_dice_pools_old_key_is_not_a_pool(registry):
    hero = hero_with_pools(registry, hit_dice=(1, 1))
    assert hit_dice_pools(hero.creature) == []


def test_short_rest_spends_the_bigger_die_first(registry):
    cfg = load_rules_config()
    hero = hero_with_pools(registry, **{"hit_dice:d10": (1, 1), "hit_dice:d8": (2, 2)})
    rng = FixedRng(6)
    short_rest(hero, registry, rng, GameClock(), cfg=cfg, hit_dice=1)
    assert rng.sides == [10]
    assert hero.creature.resources["hit_dice:d10"].current == 0
    assert hero.creature.resources["hit_dice:d8"].current == 2


def test_short_rest_moves_to_the_next_pool_when_the_first_is_empty(registry):
    cfg = load_rules_config()
    hero = hero_with_pools(registry, **{"hit_dice:d10": (1, 1), "hit_dice:d8": (2, 2)})
    rng = FixedRng(6, 5)
    short_rest(hero, registry, rng, GameClock(), cfg=cfg, hit_dice=2)
    assert rng.sides == [10, 8]
    assert hero.creature.resources["hit_dice:d8"].current == 1


def test_short_rest_heals_by_the_die_of_the_spent_pool(registry):
    cfg = load_rules_config()
    hero = hero_with_pools(registry, **{"hit_dice:d8": (1, 1)})
    healed = short_rest(hero, registry, FixedRng(5), GameClock(), cfg=cfg, hit_dice=1)
    assert healed == 5 + 2


def test_short_rest_fails_when_the_sum_of_pools_is_short(registry):
    cfg = load_rules_config()
    hero = hero_with_pools(registry, **{"hit_dice:d10": (1, 1), "hit_dice:d8": (1, 1)})
    with pytest.raises(ValueError):
        short_rest(hero, registry, FixedRng(), GameClock(), cfg=cfg, hit_dice=3)
    assert hero.creature.hp_current == 5


def test_short_rest_accepts_exactly_the_sum_of_pools(registry):
    cfg = load_rules_config()
    hero = hero_with_pools(registry, **{"hit_dice:d10": (1, 1), "hit_dice:d8": (1, 1)})
    short_rest(hero, registry, FixedRng(1, 1), GameClock(), cfg=cfg, hit_dice=2)
    assert all(pool.current == 0 for pool in hero.creature.resources.values())


def test_long_rest_restores_every_hit_dice_pool(registry):
    cfg = load_rules_config()
    hero = hero_with_pools(registry, **{"hit_dice:d10": (0, 3), "hit_dice:d6": (0, 2)})
    long_rest(hero, registry, GameClock(), cfg=cfg)
    assert hero.creature.resources["hit_dice:d10"].current == 3
    assert hero.creature.resources["hit_dice:d6"].current == 2


# concentration

def spell_of(registry, spell_id):
    return registry.get("spell", spell_id)


def test_start_concentration_stores_spell_and_circle(registry):
    hero = fighter()
    start_concentration(hero, WorldState(world_id="w", campaign_id=None, rng=Rng(1).state),
        spell_of(registry, "bless"), 2)
    assert hero.creature.concentration == Concentration(spell_id="bless", circle=2)


def test_start_concentration_drops_the_old_spell_effects(registry):
    world = WorldState(world_id="w", campaign_id=None, rng=Rng(1).state)
    hero = fighter()
    hero.creature.concentration = Concentration(spell_id="bless", circle=1)
    hero.creature.active_effects = [
        ActiveEffect(id="bless", source=hero.id, kind="spell",
            expires=Expiry(kind="concentration", owner=hero.id)),
    ]
    start_concentration(hero, world, spell_of(registry, "fog_cloud"), 1)
    assert [e.id for e in hero.creature.active_effects] == []
    assert hero.creature.concentration.spell_id == "fog_cloud"


def test_drop_concentration_clears_the_field(registry):
    world = WorldState(world_id="w", campaign_id=None, rng=Rng(1).state)
    hero = fighter()
    hero.creature.concentration = Concentration(spell_id="bless", circle=1)
    drop_concentration(hero, world)
    assert hero.creature.concentration is None


def test_drop_concentration_removes_only_the_effect_of_the_old_spell_id(registry):
    world = WorldState(world_id="w", campaign_id=None, rng=Rng(1).state)
    hero = fighter()
    hero.creature.concentration = Concentration(spell_id="bless", circle=1)
    hero.creature.active_effects = [
        ActiveEffect(id="bless", source=hero.id, kind="spell"),
        ActiveEffect(id="shield_of_faith", source=hero.id, kind="spell"),
    ]
    drop_concentration(hero, world)
    assert [e.id for e in hero.creature.active_effects] == ["shield_of_faith"]


def test_drop_concentration_removes_npc_effects_held_by_the_hero(registry):
    world = WorldState(world_id="w", campaign_id=None, rng=Rng(1).state)
    hero = fighter()
    hero.creature.concentration = Concentration(spell_id="bless", circle=1)
    npc = NPC(id="n", name="N", means=["x"], motive="y", creature=CreatureState(hp_current=5,
        hp_max=5))
    npc.creature.active_effects = [
        ActiveEffect(id="e", source=hero.id, kind="spell", expires=Expiry(kind="concentration",
            owner=hero.id)),
        ActiveEffect(id="k", source="x", kind="spell", expires=Expiry(kind="concentration",
            owner="other")),
    ]
    world.npcs["n"] = npc
    drop_concentration(hero, world)
    assert [e.id for e in npc.creature.active_effects] == ["k"]


def test_make_ranger_is_one_class_level_one(registry):
    sheet = make_ranger(registry).sheet
    assert (sheet.class_id, sheet.level, sheet.level_history) == ("ranger", 1, ["ranger"])


def test_drop_concentration_skips_npc_without_creature_and_goes_on(registry):
    world = WorldState(world_id="w", campaign_id=None, rng=Rng(1).state)
    hero = fighter()
    hero.creature.concentration = Concentration(spell_id="bless", circle=1)
    world.npcs["empty"] = NPC(id="empty", name="E", means=["x"], motive="y")
    npc = NPC(id="n", name="N", means=["x"], motive="y", creature=CreatureState(hp_current=5,
        hp_max=5))
    npc.creature.active_effects = [
        ActiveEffect(id="e", source=hero.id, kind="spell", expires=Expiry(kind="concentration",
            owner=hero.id)),
    ]
    world.npcs["n"] = npc
    drop_concentration(hero, world)
    assert npc.creature.active_effects == []


def conditions_after_drop(registry, conditions):
    world = WorldState(world_id="w", campaign_id=None, rng=Rng(1).state)
    hero = fighter()
    hero.creature.concentration = Concentration(spell_id="bless", circle=1)
    npc = NPC(id="n", name="N", means=["x"], motive="y", creature=CreatureState(hp_current=5,
        hp_max=5))
    npc.creature.conditions = conditions
    world.npcs["n"] = npc
    drop_concentration(hero, world)
    return [c.source for c in npc.creature.conditions]


def test_drop_concentration_removes_conditions_held_by_the_hero(registry):
    held = AppliedCondition(id="restrained", source="held", expires=Expiry(kind="concentration",
        owner="h1"))
    assert conditions_after_drop(registry, [held]) == []


def test_drop_concentration_keeps_conditions_of_other_owner(registry):
    other = AppliedCondition(id="restrained", source="other", expires=Expiry(kind="concentration",
        owner="x"))
    assert conditions_after_drop(registry, [other]) == ["other"]


def test_drop_concentration_keeps_conditions_with_other_expiry_kind(registry):
    timed = AppliedCondition(id="restrained", source="timed", expires=Expiry(kind="seconds",
        value=10))
    assert conditions_after_drop(registry, [timed]) == ["timed"]


def test_drop_concentration_keeps_conditions_without_expiry(registry):
    plain = AppliedCondition(id="restrained", source="plain")
    assert conditions_after_drop(registry, [plain]) == ["plain"]


# short_rest: отрицательный мод. ТЕЛ не лечит ниже нуля

def test_short_rest_never_heals_below_zero(registry):
    cfg = load_rules_config()
    hero = hero_with_pools(registry, **{"hit_dice:d10": (1, 1)})
    hero.sheet.abilities["con"] = 6
    assert short_rest(hero, registry, FixedRng(1), GameClock(), cfg=cfg, hit_dice=1) == 0


# hero_feature_ids: умения подкласса по уровню

def test_feature_ids_include_subclass_features_up_to_the_level(registry):
    hero = ranger_at(registry, 3)
    hero.sheet.primary.subclass_id = "beast_master"
    subclass = registry.get("subclass", "beast_master")
    ids = hero_feature_ids(hero, registry)
    assert all(r.feature in ids for r in subclass.features if r.level <= 3)


def test_feature_ids_skip_subclass_features_of_higher_levels(registry):
    hero = ranger_at(registry, 3)
    hero.sheet.primary.subclass_id = "beast_master"
    subclass = registry.get("subclass", "beast_master")
    higher = [r.feature for r in subclass.features if r.level > 3]
    ids = hero_feature_ids(hero, registry)
    assert not [f for f in higher if f in ids]


def test_feature_ids_keep_class_features_when_subclass_is_added(registry):
    hero = ranger_at(registry, 3)
    base = hero_feature_ids(hero, registry)
    hero.sheet.primary.subclass_id = "hunter"
    assert all(f in hero_feature_ids(hero, registry) for f in base)


def test_feature_ids_with_unknown_subclass_are_the_class_ones(registry):
    hero = ranger_at(registry, 3)
    base = hero_feature_ids(hero, registry)
    hero.sheet.primary.subclass_id = "no_such_subclass"
    assert hero_feature_ids(hero, registry) == base


# commit: сообщения о недостающих выборах доходят до игрока

def test_commit_errors_carry_the_missing_choice_text(registry):
    from ai_dm.rules.level_up import begin_level_up, commit_level_up

    hero = ranger_at(registry, 3)
    begin_level_up(hero, registry)
    result = commit_level_up(hero, registry)
    assert "нужно выбрать повышение характеристик или черту" in result.messages


# apply_level_choices: экспертиза накапливается

def test_expertise_choices_accumulate(registry):
    hero = ranger_at(registry, 2)
    hero.sheet.skill_expertise = ["stealth"]
    hero.sheet.skill_proficiencies += ["survival"]
    apply_level_choices(hero, registry, LevelChoices(level=2, fighting_style="archery",
        expertise=["survival"]))
    assert hero.sheet.skill_expertise == ["stealth", "survival"]


# choice_errors: ошибка в одном умении не прячет остальные

def test_choice_errors_keep_going_after_a_feature_not_chosen_at_this_level(registry):
    hero = ranger_at(registry, 3)
    hero.sheet.primary.subclass_id = "hunter"
    choices = LevelChoices(
        level=3, feature_choices={"second_wind": ["x"], "hunters_prey": ["nope"]},
    )
    codes = [code for code, _ in choice_errors(hero, registry, choices)]
    assert codes.count("option_invalid") == 2


# next_choice / spell_candidates

def test_next_choice_offers_spells_while_exactly_one_is_left(registry):
    hero = ranger_at(registry, 3)
    hero.sheet.primary.subclass_id = "beast_master"
    choices = LevelChoices(level=3)
    left = spells_left(hero, registry, choices)
    hero.sheet.prepared_of().extend(spell_candidates(hero, registry, choices)[: left - 1])
    assert spells_left(hero, registry, choices) == 1
    assert next_choice(hero, registry, choices) == "spells"


def test_spell_candidates_of_a_class_without_spellcasting_are_empty(registry):
    assert spell_candidates(fighter(), registry, LevelChoices(level=1)) == []
