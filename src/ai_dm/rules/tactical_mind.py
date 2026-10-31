from ai_dm.core.dice import roll_dice
from ai_dm.rules.derived import hero_feature_ids
from ai_dm.rules.roll_pipeline import OUTCOME_WORDS, RollLogEntry

POOL = "second_wind"
DIE = "1d10"


def apply(hero, registry, rng, result):
    # Тактический ум: проваленная проверка навыка получает +1d10 за заряд Второго дыхания;
    # заряд уходит, только если проверка от этого удалась
    pool = hero.creature.resources.get(POOL)
    if result.outcome != "fail" or result.dc is None or pool is None or pool.current <= 0:
        return result
    if "tactical_mind" not in hero_feature_ids(hero, registry):
        return result
    rolled = roll_dice(DIE, rng)
    total = result.total + rolled.total
    note = f"Тактический ум: +{rolled.expr} ({rolled.total}) = {total}"
    if total < result.dc:
        note += f" → {OUTCOME_WORDS['fail']}, заряд не тратится"
        return result.model_copy(update={"log": RollLogEntry(text=f"{result.log.text}; {note}")})
    pool.current -= 1
    note += f" → {OUTCOME_WORDS['success']}, заряд Второго дыхания потрачен"
    return result.model_copy(
        update={
            "total": total, "outcome": "success",
            "log": RollLogEntry(text=f"{result.log.text}; {note}"),
        }
    )
