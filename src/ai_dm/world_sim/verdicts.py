from ai_dm.rules import goals
from ai_dm.rules.triggers_eval import fire
from ai_dm.state.world import FiredTrigger
from ai_dm.world_sim.chronicle import add_entry


def find_owner(bundle, candidate):
    # владелец кандидата по виду и id; нет -- None
    world = bundle.world
    if candidate.owner_kind == "god":
        return world.pantheon.get(candidate.owner_id)
    if candidate.owner_kind == "faction":
        return world.factions.get(candidate.owner_id)
    if candidate.owner_kind == "npc":
        return world.npcs.get(candidate.owner_id)
    if candidate.owner_kind == "event":
        return next((e for e in world.events if e.id == candidate.owner_id), None)
    return next((h for h in bundle.heroes if h.id == candidate.owner_id), None)


def apply_verdicts(bundle, candidates, verdicts) -> list[str]:
    # verdicts {ref: holds}: holds=true -> триггер срабатывает (fire + world.fired + хроника),
    # секрет -> narrative_ok; holds=false -- ничего (кандидат вернётся на следующей границе).
    # Возвращает ref подтверждённых кандидатов.
    now_s = bundle.world.clock.now_s
    confirmed = []
    for candidate in candidates:
        if candidate.kind != "verdict" or not verdicts.get(candidate.ref, False):
            continue
        owner = find_owner(bundle, candidate)
        if owner is None:
            continue
        if candidate.ref.startswith("secret:"):
            secret = next((s for s in owner.secrets if s.id == candidate.item_id), None)
            if secret is None:
                continue
            secret.narrative_ok = True
        elif candidate.owner_kind == "event":
            # событие заканчивается; запись в хронику сделает тик следующего дня (close_events)
            owner.ends_at_s = now_s
        else:
            trigger = next((t for t in owner.opportunity if t.id == candidate.item_id), None)
            if trigger is None:
                continue
            fire(trigger, now_s)
            goals.mark_fired(owner, trigger)
            bundle.world.fired.append(FiredTrigger(ref=candidate.ref, at_s=now_s))
            add_entry(bundle, "trigger", f"{owner.name}: {trigger.then}", [candidate.ref])
        confirmed.append(candidate.ref)
    return confirmed
