from ai_dm.core.events import DomainEvent
from ai_dm.rules.creatures import end_concentration
from ai_dm.rules.results import Rejected
from ai_dm.state.death import DeathRecord

CAUSES = ("goal", "hazard", "chance", "old_age")
# left -- уход NPC без причины (npc_update status=gone), только для remove_creature
NPC_CAUSES = (*CAUSES, "left")
STATUSES = ("dead", "gone")


def mark_dead(hero, cause: str, by: str | None, now_s: int) -> list[DomainEvent] | Rejected:
    # причина смерти обязательна (ТЗ 4.1); мёртвый -- окончательно: повторный вызов ничего не делает
    if hero.status == "dead":
        return []
    if cause not in CAUSES:
        return Rejected(
            reason=f"у смерти должна быть причина (goal/hazard/chance/old_age), дано: {cause!r}",
            report_tag="invalid-death",
        )
    hero.status = "dead"
    hero.death = DeathRecord(cause=cause, by=by, at_s=now_s, location_id=hero.location_id)
    end_concentration(hero.creature)
    return [DomainEvent(type="hero_died", data={"id": hero.id, "cause": cause, "by": by})]


def remove_hero(
    hero, status: str, cause: str | None, now_s: int, *, by: str | None = None, text: str = "",
) -> list[DomainEvent] | Rejected:
    # те же правила, что у remove_creature; status: "dead" или "gone"
    if status not in STATUSES:
        raise ValueError(f"неизвестный статус: {status!r}")
    if hero.status == "dead":
        return Rejected(reason="already_dead", report_tag=None)
    if cause not in CAUSES:
        return Rejected(
            reason=f"у смерти должна быть причина (goal/hazard/chance/old_age), дано: {cause!r}",
            report_tag="invalid-death",
        )
    hero.status = status
    hero.death = DeathRecord(
        cause=cause, by=by, at_s=now_s, location_id=hero.location_id, text=text
    )
    end_concentration(hero.creature)
    events = [
        DomainEvent(
            type="creature_removed",
            data={"id": hero.id, "status": status, "cause": cause, "by": by},
        )
    ]
    if status == "dead":
        events.append(
            DomainEvent(type="hero_died", data={"id": hero.id, "cause": cause, "by": by})
        )
    return events


def remove_creature(
    state, creature_id: str, status: str, cause: str | None, *, by: str | None = None,
    text: str = "",
) -> list[DomainEvent] | Rejected:
    # неизвестный creature_id -- KeyError
    if status not in STATUSES:
        raise ValueError(f"неизвестный статус: {status!r}")
    npc = state.npcs[creature_id]
    if npc.status == "dead":
        return Rejected(reason="already_dead", report_tag=None)
    if cause not in NPC_CAUSES or (cause == "left" and status != "gone"):
        return Rejected(
            reason=f"у смерти должна быть причина (goal/hazard/chance/old_age), дано: {cause!r}",
            report_tag="invalid-death",
        )
    npc.status = status
    npc.follows = None
    npc.death = DeathRecord(
        cause=cause, by=by, at_s=state.clock.now_s, location_id=npc.location_id, text=text
    )
    events = [
        DomainEvent(
            type="creature_removed",
            data={"id": creature_id, "status": status, "cause": cause, "by": by},
        )
    ]
    if status == "dead":
        data = {"id": creature_id, "cause": cause, "by": by}
        events.append(DomainEvent(type="npc_died", data=data))
    return events
