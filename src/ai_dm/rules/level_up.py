from ai_dm.rules.builder import ValidationErrors
from ai_dm.rules.progression import (
    apply_level,
    apply_level_choices,
    choice_errors,
    choice_options,
    hp_gain,
    max_level,
    missing_choices,
    next_choice,
)
from ai_dm.state.hero import LevelChoices, PendingLevel


def begin_level_up(hero, registry, *, hp_method="average", rng=None) -> PendingLevel:
    # начинает повышение: HP считаются сразу, но уровень и HP применяются только в commit_level_up
    if hero.pending_level is not None:
        raise ValueError("повышение уровня уже начато")
    if hero.sheet.level >= max_level(registry):
        raise ValueError("максимальный уровень уже достигнут")
    gain = hp_gain(hero, registry, hp_method, rng)
    draft = LevelChoices(level=hero.sheet.level + 1)
    hero.pending_level = PendingLevel(class_id=hero.sheet.class_id, hp_gain=gain, draft=draft)
    return hero.pending_level


def preview_hero(hero, registry):
    # копия героя «как будто уже поднялся»: по ней считаются шаги и варианты меню
    copy = hero.model_copy(deep=True)
    apply_level(copy, registry, hero.pending_level.hp_gain)
    copy.pending_level = None
    return copy


def current_step(hero, registry) -> str | None:
    return next_choice(preview_hero(hero, registry), registry, hero.pending_level.draft)


def step_options(hero, registry) -> list[str]:
    draft = hero.pending_level.draft
    preview = preview_hero(hero, registry)
    return choice_options(preview, registry, next_choice(preview, registry, draft), draft)


def commit_level_up(hero, registry) -> ValidationErrors | None:
    # применяет уровень, HP и выборы; при ошибке герой не тронут
    draft = hero.pending_level.draft
    preview = preview_hero(hero, registry)
    errors = choice_errors(preview, registry, draft)
    codes = [code for code, _ in errors]
    messages = [text for _, text in errors]
    for text in missing_choices(preview, registry, draft):
        codes.append("choice_missing")
        messages.append(text)
    if codes:
        return ValidationErrors(codes, messages)
    apply_level(hero, registry, hero.pending_level.hp_gain)
    apply_level_choices(hero, registry, draft)
    hero.pending_level = None
    return None


def reset_draft(hero) -> None:
    pending = hero.pending_level
    pending.draft = LevelChoices(level=pending.draft.level)
