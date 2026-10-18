from ai_dm.world_sim.candidates import Candidate, sort_key
from ai_dm.world_sim.verdicts import find_owner

# потолок отложенных act-кандидатов (BACKLOG 46)
PENDING_MAX = 20


def load_acts(raw) -> list[Candidate]:
    # отложенные act из sim.pending_acts; битые записи отбрасываются молча
    acts = []
    for item in raw:
        try:
            acts.append(Candidate.model_validate_json(item))
        except ValueError:
            continue
    return acts


def stash_acts(bundle, candidates) -> None:
    # world пропущен: act-кандидаты откладываются до следующей границы (без дублей по ref)
    sim = bundle.world.sim
    kept = load_acts(sim.pending_acts)
    have = {c.ref for c in kept}
    for candidate in candidates:
        if candidate.kind == "act" and candidate.ref not in have:
            kept.append(candidate)
            have.add(candidate.ref)
    sim.pending_acts = [c.model_dump_json() for c in kept[-PENDING_MAX:]]


def stash_unapplied(bundle, candidates, applied) -> None:
    # мягкий сбой world: мир не откатывается, поэтому откладываются только act, по чьему
    # then_ref не прошёл ни один запрос (applied); остальные уже частично исполнены
    stash_acts(bundle, [c for c in candidates if c.ref not in applied])


def take_acts(bundle, candidates) -> list[Candidate]:
    # перед вызовом world: отложенные act (владелец жив) вместе с новыми кандидатами;
    # очередь пустеет
    sim = bundle.world.sim
    fresh = {c.ref for c in candidates}
    old = [
        a for a in load_acts(sim.pending_acts)
        if a.ref not in fresh and owner_present(bundle, a)
    ]
    sim.pending_acts = []
    return sorted(list(candidates) + old, key=sort_key)


def owner_present(bundle, act) -> bool:
    # владелец отложенного act ещё есть: бог и NPC -- alive, герой -- active; у фракции статуса нет
    owner = find_owner(bundle, act)
    return owner is not None and getattr(owner, "status", "alive") in ("alive", "active")
