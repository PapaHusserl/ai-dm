from ai_dm.rules.creatures import end_concentration
from ai_dm.rules.healing import heal
from ai_dm.rules.mortality_guard import mark_dead
from ai_dm.rules.roll_pipeline import RollRequest, roll
from ai_dm.state.creature import AppliedCondition, DeathSaves


def is_stable(creature) -> bool:
    # стабилен: 0 HP и три успеха (флаг stable)
    return creature.hp_current == 0 and creature.death_saves.stable


def is_dying(creature) -> bool:
    return creature.hp_current == 0 and not is_stable(creature)


def divine_save(hero, intervene) -> bool:
    # божественное вмешательство (ТЗ 4.2) перед окончательной смертью: intervene(hero) -> id бога
    return intervene is not None and intervene(hero) is not None


def check_three(hero, cause, by, now_s, intervene=None) -> str | None:
    saves = hero.creature.death_saves
    if saves.failures >= 3:
        if divine_save(hero, intervene):
            return "saved"
        mark_dead(hero, cause, by, now_s)
        return "dead"
    if saves.successes >= 3:
        saves.stable = True
        saves.successes = 0
        saves.failures = 0
        return "stable"
    return None


def roll_death_save(
    hero, registry, rng, *, now_s: int, cause: str, by: str | None = None,
    modifiers=None, rerollers=None, decisions=None, logs=None, intervene=None,
) -> str:
    if hero.status == "dead":
        raise ValueError("герой мёртв")
    creature = hero.creature
    if creature.hp_current > 0 or is_stable(creature):
        raise ValueError("спасбросок от смерти только у умирающего")
    request = RollRequest(
        kind="death_save", actor=hero, actor_id=hero.id, tags={"critical_moment": True},
        now_s=now_s,
    )
    result = roll(
        request, rng, registry, modifiers=modifiers, decisions=decisions, rerollers=rerollers
    )
    if logs is not None:
        # строка броска (ТЗ 6) для вызывающего
        logs.append(result.log.text)
    saves = creature.death_saves
    if result.natural == 20:
        heal(hero, 1)
        return "revived"
    if result.natural == 1:
        saves.failures += 2
        outcome = "failure"
    elif result.total >= 10:
        saves.successes += 1
        outcome = "success"
    else:
        saves.failures += 1
        outcome = "failure"
    return check_three(hero, cause, by, now_s, intervene) or outcome


def after_damage(
    hero, result, *, crit: bool = False, cause: str, by: str | None = None, now_s: int = 0,
    intervene=None,
) -> str:
    if hero.status == "dead":
        return "dead"
    creature = hero.creature
    if result.was_down:
        if result.final == 0:
            return "none"
        if result.hp_lost + result.overkill == 0:
            # временные HP съели весь урон
            return "none"
        if result.final >= creature.hp_max:
            if divine_save(hero, intervene):
                return "saved"
            mark_dead(hero, cause, by, now_s)
            return "dead"
        # урон на 0 HP снимает стабильность и даёт провал (крит -- два), успехи сохраняются
        creature.death_saves.stable = False
        creature.death_saves.failures += 2 if crit else 1
        if creature.death_saves.failures >= 3:
            if divine_save(hero, intervene):
                return "saved"
            mark_dead(hero, cause, by, now_s)
            return "dead"
        return "failure"
    if result.dropped:
        if result.overkill >= creature.hp_max:
            if divine_save(hero, intervene):
                return "saved"
            mark_dead(hero, cause, by, now_s)
            return "dead"
        end_concentration(creature)
        creature.death_saves = DeathSaves()
        creature.conditions.append(AppliedCondition(id="unconscious", source="0_hp"))
        return "down"
    return "none"


def resolve_out_of_combat(
    hero, registry, rng, *, now_s: int, cause: str, by: str | None = None, intervene=None
) -> tuple[str, list[str]]:
    # спасброски вне боя: бросает, пока не будет исход ("stable" / "dead" / "revived");
    # возвращает (исход, строки бросков -- по строке на каждый спасбросок)
    logs = []
    outcome = roll_death_save(
        hero, registry, rng, now_s=now_s, cause=cause, by=by, logs=logs, intervene=intervene
    )
    while outcome in ("success", "failure"):
        outcome = roll_death_save(
            hero, registry, rng, now_s=now_s, cause=cause, by=by, logs=logs, intervene=intervene
        )
    return outcome, logs
