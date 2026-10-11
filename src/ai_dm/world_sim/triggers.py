from pydantic import BaseModel, Field

from ai_dm.rules.triggers_eval import Truth, evaluate, fire, is_ready
from ai_dm.state.world import FiredTrigger
from ai_dm.world_sim.candidates import (
    Candidate,
    make_candidate,
    owners,
    sort_key,
    trigger_ref,
    verdict_candidates,
)
from ai_dm.world_sim.chronicle import add_entry


class CheckResult(BaseModel):
    # fired -- ref сработавших на этой границе триггеров; candidates -- для роли world
    fired: list[str] = Field(default_factory=list)
    candidates: list[Candidate] = Field(default_factory=list)


def check(bundle) -> CheckResult:
    # структурные триггеры NPC/фракций/богов/героев: TRUE -> fire + world.fired + хроника
    world = bundle.world
    now_s = world.clock.now_s
    result = CheckResult()
    acts = []
    owner_list = owners(bundle)
    for kind, owner, hero in owner_list:
        for trigger in owner.opportunity:
            if not is_ready(trigger, now_s):
                continue
            if evaluate(trigger.if_, world, hero).truth != Truth.TRUE:
                continue
            fire(trigger, now_s)
            ref = trigger_ref(owner.id, trigger.id)
            world.fired.append(FiredTrigger(ref=ref, at_s=now_s))
            add_entry(bundle, "trigger", f"{owner.name}: {trigger.then}", [ref])
            result.fired.append(ref)
            acts.append(make_candidate("act", kind, owner, trigger.id, ref, then=trigger.then))
    result.candidates = sorted(acts + verdict_candidates(bundle, owner_list), key=sort_key)
    for kind, owner, _ in owner_list:
        if kind == "god":
            world.sim.god_checked_s[owner.id] = now_s
    return result
