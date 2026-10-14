from ai_dm.rules.modifiers.base import Modifier
from ai_dm.rules.modifiers.conditions import with_implied
from ai_dm.state.creature import AppliedCondition, Expiry

# ходовых раундов в минуте
MINUTE_ROUNDS = 10


def has_trait(engine, ref, trait) -> bool:
    return bool(engine.monster_of(ref) and trait in engine.monster(ref).traits)


def pack_ally(engine, ref, target_ref) -> str | None:
    # Тактика стаи: боеспособный союзник-монстр в зоне цели (не сам бьющий)
    if not has_trait(engine, ref, "pack_tactics"):
        return None
    side = engine.part(ref).side
    zone = engine.part(target_ref).zone_id
    for q in engine.state.participants:
        if q.ref == ref or q.side != side or q.zone_id != zone or engine.is_hero(q.ref):
            continue
        conditions = [c.id for c in with_implied(engine.creature(q.ref))]
        if engine.is_capable(q.ref) and "incapacitated" not in conditions:
            return q.ref
    return None


class PackTacticsSource:
    # источник конвейера: tags["pack"] -- у цели в зоне есть союзник стаи, атака с преимуществом
    id = "pack_tactics"

    def modifiers(self, request, registry) -> list[Modifier]:
        if request.kind != "attack" or not request.tags.get("pack"):
            return []
        return [Modifier(source="pack_tactics", label="тактика стаи", advantage=True)]


def endures(engine, ref, dealt, crit) -> bool:
    # Стойкость нежити: урон довёл до 0 -- спасбросок Тел СЛ 5 + урон, кроме излучения
    # и крита
    if not has_trait(engine, ref, "undead_fortitude") or not dealt.dropped:
        return False
    if crit or "radiant" in dealt.damage_types:
        return False
    if engine.save(ref, "con", 5 + dealt.final).outcome != "success":
        return False
    engine.creature(ref).hp_current = 1
    engine.log(f"  {engine.name(ref)} держится на ногах: Стойкость нежити, 1 HP")
    return True


def extra_damage(engine, pair, crit, dealt, info):
    # pair = (бьющий, цель); доп. урон другого типа с каждым попаданием (укус паука, упыря)
    # локальный импорт: цикл импортов с attack
    from ai_dm.combat.actions.attack import merge_damage, roll_damage, split_dice

    ref, target_ref = pair
    action = info.action
    if action is None or action.extra_damage_dice is None:
        return dealt
    dice, bonus = split_dice(action.extra_damage_dice)
    rolled = roll_damage(
        engine, ref, dice, bonus, crit, label=f"Урон ({info.name}, доп.)",
        damage_type=action.extra_damage_type,
    )
    extra = engine.damage(target_ref, rolled.total, action.extra_damage_type)
    return merge_damage(dealt, extra)


def rider_expiry(rider, pair, provoked) -> Expiry | None:
    # pair = (бьющий, цель); провоцированная атака идёт в чужой ход: пропуски меняются местами
    ref, target_ref = pair
    if rider.duration == "target_turn":
        return Expiry(kind="end_of_turn", owner=target_ref, value=int(provoked))
    if rider.duration == "source_turn":
        # конец следующего хода бьющего: в свой ход конец текущего пропускается
        return Expiry(kind="end_of_turn", owner=ref, value=int(not provoked))
    if rider.duration == "minute":
        return Expiry(kind="rounds", value=MINUTE_ROUNDS)
    return None


def kind_of(engine, ref) -> str:
    # тип существа монстра или id вида героя
    if engine.is_hero(ref):
        return engine.heroes[ref].sheet.species_id
    return engine.monster(ref).creature_type


def rider_blocked(engine, target_ref, rider) -> bool:
    # цель на 0 HP, из exempt или крупнее max_size -- эффекта нет
    # локальный импорт: цикл импортов с attack
    from ai_dm.combat.actions.attack import SIZES, target_size

    if engine.creature(target_ref).hp_current <= 0 or kind_of(engine, target_ref) in rider.exempt:
        return True
    if rider.max_size is None:
        return False
    return SIZES.index(target_size(engine, target_ref)) > SIZES.index(rider.max_size)


def rider_saved(engine, target_ref, rider) -> bool:
    if rider.save is None:
        return False
    return engine.save(target_ref, rider.save, rider.dc).outcome == "success"


def on_hit(engine, pair, info, dealt, provoked=False):
    # эффект при попадании: спасбросок цели, урон и состояние при провале
    # локальный импорт: цикл импортов с attack
    from ai_dm.combat.actions.attack import merge_damage, roll_damage, split_dice

    ref, target_ref = pair
    action = info.action
    if action is None or action.on_hit is None:
        return dealt
    rider = action.on_hit
    if rider_blocked(engine, target_ref, rider) or rider_saved(engine, target_ref, rider):
        return dealt
    if rider.dice is not None:
        dice, bonus = split_dice(rider.dice)
        rolled = roll_damage(
            engine, ref, dice, bonus, False, label=f"Урон ({info.name}, эффект)",
            damage_type=rider.damage_type,
        )
        dealt = merge_damage(dealt, engine.damage(target_ref, rolled.total, rider.damage_type))
    condition = AppliedCondition(
        id=rider.condition, source=ref, expires=rider_expiry(rider, pair, provoked)
    )
    if engine.impose(target_ref, condition):
        word = engine.registry.get("condition", rider.condition).name
        engine.log(f"  {engine.name(target_ref)}: {word.lower()}")
    return dealt
