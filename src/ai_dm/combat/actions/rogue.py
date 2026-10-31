from ai_dm.core.events import DomainEvent
from ai_dm.rules.derived import ability_mod, hero_feature_ids, proficiency
from ai_dm.rules.modifiers.conditions import with_implied
from ai_dm.state.creature import ActiveEffect, AppliedCondition, Expiry

# флаги хода: выбран Хитрый удар (params["effect"]), герой уже ходил по зонам
STRIKE = "cunning_strike"
# эффект Хитрого удара ждёт урона текущей атаки
PENDING = "cunning_strike_pending"
MOVED = "moved"
# варианты Хитрого удара в порядке меню и подписи
EFFECTS = {"trip": "Сбить с ног", "poison": "Отравить", "withdraw": "Отступить"}
# Отравить: «отравлен» на 1 минуту
POISON_ROUNDS = 10


def has(engine, ref, feature_id) -> bool:
    # герой с этим умением; монстр и NPC без листа -- нет
    return engine.is_hero(ref) and feature_id in hero_feature_ids(
        engine.heroes[ref], engine.registry
    )


def turn_flag(engine, ref, flag_id, params=None) -> None:
    # флаг до конца хода участника; прежний с тем же id заменяется
    effects = engine.creature(ref).active_effects
    effects[:] = [e for e in effects if e.id != flag_id]
    effects.append(
        ActiveEffect(
            id=flag_id, source=ref, kind="flag", params=params or {},
            expires=Expiry(kind="end_of_turn", value=0, owner=ref),
        )
    )


def mark_moved(engine, ref) -> None:
    # Верный прицел требует стоять на месте: ход по зонам плута запоминается
    if has(engine, ref, "steady_aim"):
        turn_flag(engine, ref, MOVED)


def can_aim(engine, ref) -> bool:
    # Верный прицел: ещё не ходил и не делал Рывок (перемещение хода целое)
    if not has(engine, ref, "steady_aim"):
        return False
    effects = engine.creature(ref).active_effects
    if any(e.id in (MOVED, "steady_aim") for e in effects):
        return False
    return engine.part(ref).turn.move == 1


def steady_aim(engine, ref, option) -> list[DomainEvent]:
    # следующая атака в этом ходу с преимуществом, до конца хода скорость 0
    turn = engine.part(ref).turn
    turn.bonus = False
    turn.move = 0
    engine.creature(ref).active_effects.append(
        ActiveEffect(
            id="steady_aim", source=ref, kind="modifier",
            params={"target": "attack_roll", "mode": "advantage", "consume": True},
            expires=Expiry(kind="end_of_turn", value=0, owner=ref),
        )
    )
    engine.log(f"{engine.name(ref)}: Верный прицел")
    return []


def cunning_strike(engine, ref, option) -> list[DomainEvent]:
    # выбор эффекта следующей Скрытой атаки; повторный выбор заменяет прежний
    effect = option.params["effect"]
    turn_flag(engine, ref, STRIKE, {"effect": effect})
    engine.log(f"{engine.name(ref)}: Хитрый удар — {EFFECTS[effect]}")
    return []


def strike_effect(engine, ref, target_ref) -> str | None:
    # выбранный эффект, если он действует на цель; флаг тратится вместе со Скрытой атакой
    # локальный импорт: цикл импортов attack <-> sneak <-> rogue
    from ai_dm.combat.actions.attack import SIZES, target_size

    flags = [e for e in engine.creature(ref).active_effects if e.id == STRIKE]
    if not flags:
        return None
    effect = flags[0].params["effect"]
    too_large = SIZES.index(target_size(engine, target_ref)) > SIZES.index("large")
    if effect == "trip" and too_large:
        engine.log(f"  Хитрый удар ({EFFECTS[effect]}): цель слишком велика, кость не потрачена")
        return None
    engine.creature(ref).active_effects.remove(flags[0])
    # сам эффект -- после урона (resolve_pending), как у мастерства «Опрокидывание»
    turn_flag(engine, ref, PENDING, {"effect": effect})
    return effect


def resolve_pending(engine, ref, target_ref, dealt) -> None:
    # после урона Скрытой атаки: эффект Хитрого удара; при нулевом уроне -- нет, «Сбить с ног» и
    # «Отравить» -- ещё и убитой цели (Отступить -- эффект на плуте, добитая цель не мешает)
    effects = engine.creature(ref).active_effects
    pending = [e for e in effects if e.id == PENDING]
    if not pending:
        return
    effects.remove(pending[0])
    effect = pending[0].params["effect"]
    alive = engine.creature(target_ref).hp_current > 0
    if dealt.final > 0 and (alive or effect == "withdraw"):
        resolve(engine, ref, target_ref, effect)


def resolve(engine, ref, target_ref, effect) -> None:
    # Хитрый удар: Сбить с ног (спас Лов), Отравить (спас Тел, 1 минута), Отступить (без провокаций)
    name = EFFECTS[effect]
    if effect == "withdraw":
        engine.part(ref).turn.disengaged = True
        engine.log(f"  Хитрый удар ({name}): ход не провоцирует атаки")
        return
    hero = engine.heroes[ref]
    dc = 8 + ability_mod(hero, "dex") + proficiency(hero, engine.registry)
    engine.log(f"  Хитрый удар ({name}): СЛ {dc}")
    ability, condition, word = ("dex", "prone", "сбит с ног")
    expires = None
    if effect == "poison":
        ability, condition, word = ("con", "poisoned", "отравлен")
        expires = Expiry(kind="rounds", value=POISON_ROUNDS)
    if engine.save(target_ref, ability, dc).outcome == "success":
        return
    if engine.impose(target_ref, AppliedCondition(id=condition, source=ref, expires=expires)):
        engine.log(f"  {engine.name(target_ref)} {word}")


def uncanny_dodge(engine, target_ref, total) -> int:
    # Невероятное уклонение: реакция героя-плута вдвое снижает урон попавшей атаки
    if total <= 0 or not has(engine, target_ref, "uncanny_dodge"):
        return total
    turn = engine.part(target_ref).turn
    conditions = {c.id for c in with_implied(engine.creature(target_ref))}
    if not turn.reaction or not engine.is_capable(target_ref):
        return total
    if conditions & {"incapacitated", "blinded"}:
        return total
    turn.reaction = False
    half = total // 2
    engine.log(f"  {engine.name(target_ref)}: Невероятное уклонение: {total} → {half}")
    return half
