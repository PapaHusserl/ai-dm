from ai_dm.core.dice import roll_dice
from ai_dm.core.events import DomainEvent
from ai_dm.rules import money
from ai_dm.rules.checks import saving_throw
from ai_dm.rules.npc_memory import has_kind, remember
from ai_dm.state.creature import AppliedCondition
from ai_dm.state.relations import NPC_EVENT_TEXT_MAX, NpcEvent

DISEASED = "diseased"
# потолок потери при краже (решение 29): 10 зм
THEFT_CAP_CP = 1000
THEFT_PERCENT_STEP = 10


# Каждое последствие платной близости возвращает None (проверки нет) или кортеж
# (id последствия или None, если не случилось; строки лога; сигнал мастеру или None;
# roll_ref спасброска или None).


def disease_check(ctx, kind, npc):
    # спасбросок Телосложения от болезни; провал -- состояние «болен»
    dc = kind.risks.disease_dc
    if dc == 0:
        return None
    hero = ctx.hero
    result = saving_throw(
        hero, ctx.registry, ctx.rng, "con", dc=dc, now_s=ctx.bundle.world.clock.now_s
    )
    lines = [result.log.text]
    ref = ctx.add_roll(result, hero.id, engine=True)
    if result.outcome != "fail":
        return (None, lines, None, ref)
    conditions = hero.creature.conditions
    if not any(c.id == DISEASED for c in conditions):
        conditions.append(AppliedCondition(id=DISEASED, source=f"service:{npc.id}"))
    ctx.events.append(DomainEvent(type="diseased", data={"id": hero.id, "source": npc.id}))
    lines.append(f"{hero.name}: болезнь")
    return ("diseased", lines, "Герой подхватил болезнь: опиши недомогание по факту.", ref)


def theft_check(ctx, kind, npc):
    # спасбросок Мудрости от кражи; провал -- 1к4 x 10 % кошелька, не больше 10 зм
    dc = kind.risks.theft_dc
    if dc == 0:
        return None
    hero = ctx.hero
    result = saving_throw(
        hero, ctx.registry, ctx.rng, "wis", dc=dc, now_s=ctx.bundle.world.clock.now_s
    )
    lines = [result.log.text]
    ref = ctx.add_roll(result, hero.id, engine=True)
    if result.outcome != "fail":
        return (None, lines, None, ref)
    percent = roll_dice("1d4", ctx.rng).total * THEFT_PERCENT_STEP
    lost = min(hero.money_cp * percent // 100, THEFT_CAP_CP)
    if lost == 0:
        return (None, lines, None, ref)
    money.spend_money(hero, lost)
    ctx.events.append(DomainEvent(type="robbed", data={"id": hero.id, "by": npc.id}))
    lines.append(f"Кошелёк полегчал на {money.format_cp(lost)}")
    return (
        "robbed", lines,
        "Кошелёк героя полегчал: он замечает пропажу сразу или позже — решай по рассказу.",
        ref,
    )


def loves_hero(npc, hero) -> bool:
    # активная цель love на героя или romance в памяти NPC
    goal = any(g.kind == "love" and g.target == hero.id and g.status == "active" for g in npc.goals)
    return goal or any(e.kind == "romance" for s in npc.memory for e in s.events)


def jealous_companion(other, npc, hero) -> bool:
    # живой влюблённый спутник героя в его локации, не сам поставщик услуги
    if other.id == npc.id or other.status != "alive":
        return False
    if other.follows != hero.id or other.location_id != hero.location_id:
        return False
    return loves_hero(other, hero)


def jealousy(ctx, npc):
    # влюблённые спутники героя в его локации: отношение вниз на шаг, в памяти измена
    hero = ctx.hero
    step = ctx.cfg.attitude.step
    lines = []
    for other in ctx.bundle.world.npcs.values():
        if not jealous_companion(other, npc, hero):
            continue
        before = other.attitude
        other.attitude = max(-100, before - step)
        applied = other.attitude - before
        scene = ctx.scene
        if scene is not None and not has_kind(other, scene, "betrayal"):
            text = f"измена: платная близость с {npc.name}"[:NPC_EVENT_TEXT_MAX]
            entry = remember(
                other, scene, NpcEvent(kind="betrayal", turn_seq=ctx.turn_seq, text=text),
                ctx.cfg.npc_memory,
            )
            if entry is not None:
                # лимит сцены не тратим (решение 35), но запись не должна вытесняться первой
                entry.weight = max(entry.weight, abs(applied))
        ctx.events.append(
            DomainEvent(type="betrayal", data={"id": other.id, "hero": hero.id, "with": npc.id})
        )
        lines.append(f"{other.name}: измена раскрыта, отношение {applied:+d}")
    if not lines:
        return None
    return (
        "jealousy", lines,
        "Спутник, любящий героя, узнал о платной близости: опиши реакцию.", None,
    )
