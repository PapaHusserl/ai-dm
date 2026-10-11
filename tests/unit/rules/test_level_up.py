# К0а (docs/K0-PLAN.md, A4): меню уровня через HeroState.pending_level. Ожидаемый API
# ai_dm.rules.level_up (плоские функции):
#   begin_level_up(hero, registry, *, hp_method="average", rng=None) -> PendingLevel -- ставит
#       hero.pending_level (class_id, hp_gain, draft=LevelChoices(level=уровень+1)); уровень, HP и
#       пулы НЕ меняются; повтор / потолок -> ValueError;
#   preview_hero(hero, registry) -> HeroState -- копия «как будто уже поднялся», pending_level None,
#       исходный герой не тронут;
#   current_step(hero, registry) -> str | None; step_options(hero, registry) -> list[str];
#   commit_level_up(hero, registry) -> ValidationErrors | None -- применяет уровень, HP и выборы;
#       при ошибке герой не тронут; reset_draft(hero) -- новый пустой черновик того же уровня.
import pytest
from ranger_kit import ranger_at

from ai_dm.core.rng import Rng
from ai_dm.rules import progression
from ai_dm.rules.builder import ValidationErrors
from ai_dm.rules.level_up import (
    begin_level_up,
    commit_level_up,
    current_step,
    preview_hero,
    reset_draft,
    step_options,
)


def top_level(registry):
    if hasattr(progression, "MAX_LEVEL"):
        return progression.MAX_LEVEL
    return progression.max_level(registry)


def set_level(hero, level):
    hero.sheet.primary.level = level
    hero.sheet.level_history = [hero.sheet.class_id] * level


def snapshot(hero):
    return hero.model_dump_json()


def ranger3(registry):
    return ranger_at(registry, 3)


def started(registry, **kwargs):
    hero = ranger3(registry)
    begin_level_up(hero, registry, **kwargs)
    return hero


# begin_level_up

def test_begin_sets_pending_level_with_class_and_next_level(registry):
    hero = ranger3(registry)
    pending = begin_level_up(hero, registry)
    assert hero.pending_level is pending
    assert pending.class_id == "ranger"
    assert pending.draft.level == 4


def test_begin_average_hp_gain_is_die_half_plus_con(registry):
    # d10: 6 + мод. ТЕЛ (+1)
    assert begin_level_up(ranger3(registry), registry).hp_gain == 7


def test_begin_does_not_change_level_hp_or_pools(registry):
    hero = ranger3(registry)
    before = (hero.sheet.level, hero.creature.hp_max, hero.creature.hp_current)
    pools = {key: pool.model_copy() for key, pool in hero.creature.resources.items()}
    begin_level_up(hero, registry)
    assert (hero.sheet.level, hero.creature.hp_max, hero.creature.hp_current) == before
    assert hero.creature.resources == pools
    assert hero.sheet.level_history == ["ranger"] * 3


def test_begin_draft_is_empty(registry):
    draft = begin_level_up(ranger3(registry), registry).draft
    assert (draft.asi, draft.feat, draft.spells_add, draft.feature_choices) == (None, None, [], {})


def test_begin_twice_is_refused_and_keeps_first_pending(registry):
    hero = started(registry)
    first = hero.pending_level
    with pytest.raises(ValueError):
        begin_level_up(hero, registry)
    assert hero.pending_level is first


def test_begin_at_top_level_is_refused(registry):
    hero = ranger3(registry)
    set_level(hero, top_level(registry))
    with pytest.raises(ValueError):
        begin_level_up(hero, registry)
    assert hero.pending_level is None


def test_begin_roll_uses_rng_and_keeps_the_roll(registry):
    hero = ranger3(registry)
    pending = begin_level_up(hero, registry, hp_method="roll", rng=Rng(5))
    expected = max(1, Rng(5).d(10) + 1)
    assert pending.hp_gain == expected


def test_begin_roll_without_rng_is_refused_and_leaves_no_pending(registry):
    hero = ranger3(registry)
    with pytest.raises(ValueError):
        begin_level_up(hero, registry, hp_method="roll")
    assert hero.pending_level is None


def test_begin_unknown_method_is_refused(registry):
    hero = ranger3(registry)
    with pytest.raises(ValueError):
        begin_level_up(hero, registry, hp_method="max")
    assert hero.pending_level is None


# preview_hero

def test_preview_has_next_level_and_hp(registry):
    hero = started(registry)
    preview = preview_hero(hero, registry)
    assert preview.sheet.level == 4
    assert preview.creature.hp_max == hero.creature.hp_max + 7
    assert preview.creature.hp_current == hero.creature.hp_current + 7


def test_preview_has_no_pending_level(registry):
    assert preview_hero(started(registry), registry).pending_level is None


def test_preview_does_not_touch_the_original(registry):
    hero = started(registry)
    before = snapshot(hero)
    preview_hero(hero, registry)
    assert snapshot(hero) == before


def test_preview_is_a_deep_copy(registry):
    hero = started(registry)
    preview = preview_hero(hero, registry)
    preview.sheet.feats.append("marker_feat")
    preview.creature.resources.clear()
    assert "marker_feat" not in hero.sheet.feats
    assert hero.creature.resources


def test_preview_syncs_resources_for_the_new_level(registry):
    hero = ranger_at(registry, 4)
    begin_level_up(hero, registry)
    assert preview_hero(hero, registry).creature.resources["hit_dice:d10"].max == 5
    assert hero.creature.resources["hit_dice:d10"].max == 4


def test_preview_appends_level_history(registry):
    preview = preview_hero(started(registry), registry)
    assert preview.sheet.level_history == ["ranger"] * 4


# current_step / step_options

def test_first_step_for_ranger_3_to_4_is_asi_or_feat(registry):
    assert current_step(started(registry), registry) == "asi_or_feat"


def test_asi_options_have_dexterity_pairs(registry):
    options = step_options(started(registry), registry)
    assert "dex+2" in options
    assert "dex+wis" in options
    assert "ability_score_improvement" not in options


def test_asi_options_skip_abilities_that_would_exceed_20(registry):
    hero = ranger3(registry)
    hero.sheet.abilities["dex"] = 20
    begin_level_up(hero, registry)
    options = step_options(hero, registry)
    assert "dex+2" not in options
    assert "dex+wis" not in options


def test_step_does_not_change_the_hero(registry):
    hero = started(registry)
    before = snapshot(hero)
    current_step(hero, registry)
    step_options(hero, registry)
    assert snapshot(hero) == before


def test_step_follows_the_draft(registry):
    hero = started(registry)
    hero.pending_level.draft.asi = {"dex": 2}
    assert current_step(hero, registry) == "spells"


def test_spells_step_options_exclude_already_chosen(registry):
    hero = started(registry)
    hero.pending_level.draft.asi = {"dex": 2}
    first = step_options(hero, registry)[0]
    hero.pending_level.draft.spells_add.append(first)
    assert first not in step_options(hero, registry)


def test_step_is_none_when_nothing_is_left(registry):
    hero = started(registry)
    draft = hero.pending_level.draft
    draft.asi = {"dex": 2}
    for _ in range(10):
        step = current_step(hero, registry)
        if step is None:
            break
        draft.spells_add.append(step_options(hero, registry)[0])
    assert current_step(hero, registry) is None


# commit_level_up

def test_commit_without_choices_returns_errors_and_does_not_touch_hero(registry):
    hero = started(registry)
    before = snapshot(hero)
    result = commit_level_up(hero, registry)
    assert isinstance(result, ValidationErrors)
    assert snapshot(hero) == before


def test_commit_without_choices_names_the_missing_asi(registry):
    result = commit_level_up(started(registry), registry)
    assert "choice_missing" in result.codes


def test_commit_with_bad_asi_returns_errors_and_does_not_touch_hero(registry):
    hero = started(registry)
    hero.pending_level.draft.asi = {"dex": 5}
    before = snapshot(hero)
    assert isinstance(commit_level_up(hero, registry), ValidationErrors)
    assert snapshot(hero) == before


def test_commit_with_asi_raises_level_and_hp(registry):
    hero = started(registry)
    hp = hero.creature.hp_max
    hero.pending_level.draft.asi = {"dex": 2}
    assert commit_level_up(hero, registry) is None
    assert hero.sheet.level == 4
    assert hero.creature.hp_max == hp + 7
    assert hero.creature.hp_current == hp + 7


def test_commit_with_asi_raises_dexterity_and_adds_feat(registry):
    hero = started(registry)
    dex = hero.sheet.abilities["dex"]
    hero.pending_level.draft.asi = {"dex": 2}
    commit_level_up(hero, registry)
    assert hero.sheet.abilities["dex"] == dex + 2
    assert hero.sheet.feats[-1] == "ability_score_improvement"


def test_commit_clears_pending_level(registry):
    hero = started(registry)
    hero.pending_level.draft.asi = {"dex": 2}
    commit_level_up(hero, registry)
    assert hero.pending_level is None


def test_commit_appends_level_history(registry):
    hero = started(registry)
    hero.pending_level.draft.asi = {"dex": 2}
    commit_level_up(hero, registry)
    assert hero.sheet.level_history == ["ranger"] * 4


def test_commit_syncs_hit_dice_pool_of_the_class_die(registry):
    hero = ranger_at(registry, 3)
    begin_level_up(hero, registry)
    hero.pending_level.draft.asi = {"dex": 2}
    commit_level_up(hero, registry)
    assert hero.creature.resources["hit_dice:d10"].max == 4
    assert "hit_dice" not in hero.creature.resources


def test_commit_adds_chosen_spells_to_the_class_lists(registry):
    hero = started(registry)
    draft = hero.pending_level.draft
    draft.asi = {"dex": 2}
    spell = step_options_after_asi(hero, registry)
    draft.spells_add.append(spell)
    assert commit_level_up(hero, registry) is None
    assert spell in hero.sheet.spells_prepared["ranger"]
    assert spell in hero.sheet.spells_known["ranger"]


def step_options_after_asi(hero, registry):
    return step_options(hero, registry)[0]


def test_commit_uses_hp_gain_rolled_at_begin(registry):
    hero = ranger3(registry)
    hp = hero.creature.hp_max
    pending = begin_level_up(hero, registry, hp_method="roll", rng=Rng(11))
    gain = pending.hp_gain
    pending.draft.asi = {"dex": 2}
    commit_level_up(hero, registry)
    assert hero.creature.hp_max == hp + gain


def test_commit_does_not_roll_again(registry):
    hero = ranger3(registry)
    rng = Rng(11)
    begin_level_up(hero, registry, hp_method="roll", rng=rng)
    state = rng.state
    hero.pending_level.draft.asi = {"dex": 2}
    commit_level_up(hero, registry)
    assert rng.state == state


def test_hero_plays_at_old_level_until_commit(registry):
    hero = started(registry)
    hero.pending_level.draft.asi = {"dex": 2}
    assert hero.sheet.level == 3
    assert hero.creature.hp_max == ranger3(registry).creature.hp_max


# reset_draft

def test_reset_draft_clears_choices_and_keeps_level(registry):
    hero = started(registry)
    hero.pending_level.draft.asi = {"dex": 2}
    hero.pending_level.draft.spells_add.append("cure_wounds")
    reset_draft(hero)
    draft = hero.pending_level.draft
    assert (draft.asi, draft.spells_add, draft.level) == (None, [], 4)


def test_reset_draft_keeps_hp_gain_and_class(registry):
    hero = started(registry)
    reset_draft(hero)
    assert (hero.pending_level.hp_gain, hero.pending_level.class_id) == (7, "ranger")


def test_reset_draft_makes_a_new_object(registry):
    hero = started(registry)
    old = hero.pending_level.draft
    reset_draft(hero)
    assert hero.pending_level.draft is not old


# сохранение посреди меню

def test_pending_level_survives_json_round_trip(registry):
    hero = started(registry)
    hero.pending_level.draft.asi = {"dex": 2}
    again = type(hero).model_validate_json(hero.model_dump_json())
    assert again.pending_level == hero.pending_level
    assert current_step(again, registry) == current_step(hero, registry)


def test_begin_one_level_below_the_top_is_allowed(registry):
    hero = ranger3(registry)
    set_level(hero, top_level(registry) - 1)
    assert begin_level_up(hero, registry).draft.level == top_level(registry)
