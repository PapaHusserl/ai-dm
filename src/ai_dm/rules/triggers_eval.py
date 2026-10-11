from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, Field

from ai_dm.core.duration import Duration
from ai_dm.rules.inventory import find_item
from ai_dm.state.triggers import (
    AllOf,
    AnyOf,
    Attitude,
    Condition,
    EventActive,
    Favor,
    Flag,
    HeroAt,
    HeroDead,
    HeroHas,
    Narrative,
    NotOf,
    NpcAt,
    NpcStatus,
    TimeAfter,
)


class Truth(str, Enum):  # noqa: UP042
    TRUE = "TRUE"
    FALSE = "FALSE"
    NEEDS_NARRATIVE = "NEEDS_NARRATIVE"


class Evaluation(BaseModel):
    truth: Truth
    narrative: list[str] = Field(default_factory=list)
    # остаток дерева условия для модели world: только нарративные листья и not/all/any над ними
    residual: Condition | None = None


def from_bool(value: bool) -> Evaluation:
    return Evaluation(truth=Truth.TRUE if value else Truth.FALSE)


def in_range(number: int, gte: int | None, lte: int | None) -> bool:
    if gte is not None and number < gte:
        return False
    return not (lte is not None and number > lte)


def pack(kind, residuals):
    # один остаток -- он сам; несколько -- под all/any
    if len(residuals) == 1:
        return residuals[0]
    if kind == "all":
        return AllOf(items=residuals)
    return AnyOf(items=residuals)


def event_active(event, now_s: int) -> bool:
    started = event.started_s is None or event.started_s <= now_s
    return started and (event.ends_at_s is None or now_s < event.ends_at_s)


def evaluate(condition, world, hero=None) -> Evaluation:
    # чистая функция: состояние не меняет; неизвестный id -> FALSE;
    # без героя условия о герое -> FALSE
    if isinstance(condition, AllOf):
        results = [evaluate(item, world, hero) for item in condition.items]
        if any(r.truth == Truth.FALSE for r in results):
            return Evaluation(truth=Truth.FALSE)
        open_results = [r for r in results if r.truth == Truth.NEEDS_NARRATIVE]
        if open_results:
            texts = [t for r in open_results for t in r.narrative]
            residual = pack("all", [r.residual for r in open_results])
            return Evaluation(truth=Truth.NEEDS_NARRATIVE, narrative=texts, residual=residual)
        return Evaluation(truth=Truth.TRUE)
    if isinstance(condition, AnyOf):
        results = [evaluate(item, world, hero) for item in condition.items]
        if any(r.truth == Truth.TRUE for r in results):
            return Evaluation(truth=Truth.TRUE)
        open_results = [r for r in results if r.truth == Truth.NEEDS_NARRATIVE]
        if open_results:
            texts = [t for r in open_results for t in r.narrative]
            residual = pack("any", [r.residual for r in open_results])
            return Evaluation(truth=Truth.NEEDS_NARRATIVE, narrative=texts, residual=residual)
        return Evaluation(truth=Truth.FALSE)
    if isinstance(condition, NotOf):
        result = evaluate(condition.item, world, hero)
        if result.truth == Truth.TRUE:
            return Evaluation(truth=Truth.FALSE)
        if result.truth == Truth.FALSE:
            return Evaluation(truth=Truth.TRUE)
        return Evaluation(
            truth=Truth.NEEDS_NARRATIVE,
            narrative=result.narrative,
            residual=NotOf(item=result.residual),
        )
    if isinstance(condition, Narrative):
        return Evaluation(
            truth=Truth.NEEDS_NARRATIVE, narrative=[condition.text], residual=condition
        )
    if isinstance(condition, Flag):
        value = world.flags.get(condition.name, False)
        return from_bool(isinstance(value, bool) and value == condition.value)
    if hero is None and isinstance(condition, (HeroHas, HeroAt, Favor, HeroDead)):
        return Evaluation(truth=Truth.FALSE)
    if isinstance(condition, HeroHas):
        return from_bool(any(e.item_id == condition.item and e.qty > 0 for e in hero.inventory))
    if isinstance(condition, NpcStatus):
        npc = world.npcs.get(condition.id)
        return from_bool(npc is not None and npc.status == condition.is_)
    if isinstance(condition, HeroAt):
        return from_bool(hero.location_id == condition.location)
    if isinstance(condition, NpcAt):
        npc = world.npcs.get(condition.id)
        return from_bool(npc is not None and npc.location_id == condition.at)
    if isinstance(condition, TimeAfter):
        return from_bool(world.clock.now_s >= condition.seconds)
    if isinstance(condition, Attitude):
        npc = world.npcs.get(condition.npc)
        return from_bool(npc is not None and in_range(npc.attitude, condition.gte, condition.lte))
    if isinstance(condition, Favor):
        number = hero.favor.get(condition.god, 0)
        return from_bool(in_range(number, condition.gte, condition.lte))
    if isinstance(condition, EventActive):
        now_s = world.clock.now_s
        events = [e for e in world.events if e.id == condition.event]
        return from_bool(any(event_active(e, now_s) for e in events))
    if isinstance(condition, HeroDead):
        return from_bool(hero.status == "dead")
    raise ValueError(f"неизвестное условие: {condition!r}")


@dataclass
class KnownIds:
    # id, на которые можно ссылаться из условий: NPC, локации, боги
    npcs: set[str]
    locations: set[str]
    pantheon: set[str]

def validate_refs(condition, known, registry=None) -> list[str]:
    # known -- объект с npcs/locations/pantheon (KnownIds или WorldState)
    # по строке на каждую битую ссылку; event_active не проверяется (события возникают позже)
    refs = []
    if isinstance(condition, (AllOf, AnyOf)):
        for item in condition.items:
            refs += validate_refs(item, known, registry)
    elif isinstance(condition, NotOf):
        refs += validate_refs(condition.item, known, registry)
    elif isinstance(condition, NpcStatus):
        if condition.id not in known.npcs:
            refs.append(f"npc_status: неизвестный NPC {condition.id!r}")
    elif isinstance(condition, NpcAt):
        if condition.id not in known.npcs:
            refs.append(f"npc_at: неизвестный NPC {condition.id!r}")
        if condition.at not in known.locations:
            refs.append(f"npc_at: неизвестная локация {condition.at!r}")
    elif isinstance(condition, Attitude):
        if condition.npc not in known.npcs:
            refs.append(f"attitude: неизвестный NPC {condition.npc!r}")
    elif isinstance(condition, HeroAt):
        if condition.location not in known.locations:
            refs.append(f"hero_at: неизвестная локация {condition.location!r}")
    elif isinstance(condition, Favor):
        if condition.god not in known.pantheon:
            refs.append(f"favor: неизвестный бог {condition.god!r}")
    elif (
        isinstance(condition, HeroHas)
        and registry is not None
        and find_item(registry, condition.item) is None
    ):
        refs.append(f"hero_has: неизвестный предмет {condition.item!r}")
    return refs


def is_ready(trigger, now_s: int) -> bool:
    # только счётчики и время; условие if не проверяется
    if trigger.state != "active":
        return False
    if trigger.once and trigger.fired_count > 0:
        return False
    if trigger.cooldown is not None and trigger.last_fired_at is not None:
        return now_s - trigger.last_fired_at >= Duration.parse(trigger.cooldown).seconds
    return True


def fire(trigger, now_s: int) -> None:
    trigger.fired_count += 1
    trigger.last_fired_at = now_s
    if trigger.once:
        trigger.state = "fired"
