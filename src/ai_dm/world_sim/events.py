from ai_dm.core.clock import DAY
from ai_dm.core.duration import Duration
from ai_dm.core.events import DomainEvent
from ai_dm.rules.triggers_eval import Truth, evaluate, event_active
from ai_dm.state.memory import add_entry
from ai_dm.state.world import GlobalEvent
from ai_dm.world_sim.candidates import current_hero


def close_events(bundle, at) -> list:
    # истечение событий (A6): по сроку ends_at_s в сутках, закончившихся на at; затем по ends_when
    # (структурная часть -- evaluate; нарративная сюда не входит)
    world = bundle.world
    events = []
    for event in world.events:
        if event.ends_at_s is not None and at - DAY < event.ends_at_s <= at:
            add_entry(bundle, "event", f"Событие закончилось: {event.type}", [event.id], at)
            events.append(DomainEvent(type="event_ended", data={"id": event.id}))
    hero = current_hero(bundle)
    for event in world.events:
        if event.ends_when is None or not event_active(event, at):
            continue
        if evaluate(event.ends_when, world, hero).truth == Truth.TRUE:
            event.ends_at_s = at
            add_entry(bundle, "event", f"Событие закончилось: {event.type}", [event.id], at)
            events.append(DomainEvent(type="event_ended", data={"id": event.id}))
    return events


def natural_event(bundle, rng, season, at) -> list:
    # раз в сезон один бросок: chance_percent_per_season; выпало -- вид из пака (rng по порядку)
    spec = bundle.world.natural
    hit = rng.randbelow(100) < spec.chance_percent_per_season
    if not hit or not spec.kinds:
        return []
    kind = spec.kinds[rng.randbelow(len(spec.kinds))]
    event_id = f"natural:{kind.type}:{at // DAY}"
    while any(e.id == event_id for e in bundle.world.events):
        event_id += "_"
    event = GlobalEvent(
        id=event_id, type=kind.type, regions=list(kind.regions),
        mortality_multiplier=kind.mortality_multiplier,
        hazard=None if kind.hazard is None else kind.hazard.model_copy(),
        started_s=at, ends_at_s=at + Duration.parse(kind.duration).seconds,
        cause=f"season:{season}", kind="natural",
    )
    bundle.world.events.append(event)
    add_entry(bundle, "event", f"Началось событие: {kind.type} ({season})", [event.id], at)
    return [DomainEvent(type="event_started", data={"id": event.id, "type": event.type})]
