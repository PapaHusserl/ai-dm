from pydantic import BaseModel, Field

from ai_dm.rules import goals
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


def fire_trigger(bundle, kind, owner, trigger):
    # сработавший триггер: fire + world.fired + хроника; возвращает ref и act-кандидата
    now_s = bundle.world.clock.now_s
    fire(trigger, now_s)
    goals.mark_fired(owner, trigger)
    ref = trigger_ref(owner.id, trigger.id)
    bundle.world.fired.append(FiredTrigger(ref=ref, at_s=now_s))
    add_entry(bundle, "trigger", f"{owner.name}: {trigger.then}", [ref])
    return ref, make_candidate("act", kind, owner, trigger.id, ref, then=trigger.then)


def check(bundle, cfg) -> CheckResult:
    # структурные триггеры NPC/фракций/богов/героев: TRUE -> fire + world.fired + хроника;
    # триггеры целей NPC проверяются реже (goals_check_every_days)
    world = bundle.world
    now_s = world.clock.now_s
    goals.sweep(world, bundle.heroes)
    goals_due = goals.due(world.sim, now_s, cfg.world.goals_check_every_days)
    result = CheckResult()
    acts = []
    owner_list = owners(bundle)
    for kind, owner, hero in owner_list:
        for trigger in owner.opportunity:
            if goals.skipped(trigger, goals_due) or not is_ready(trigger, now_s):
                continue
            if evaluate(trigger.if_, world, hero).truth != Truth.TRUE:
                continue
            ref, act = fire_trigger(bundle, kind, owner, trigger)
            result.fired.append(ref)
            acts.append(act)
    verdicts = verdict_candidates(bundle, owner_list, skip_goals=not goals_due)
    result.candidates = sorted(acts + verdicts, key=sort_key)
    for kind, owner, _ in owner_list:
        if kind == "god":
            world.sim.god_checked_s[owner.id] = now_s
    if goals_due:
        world.sim.goals_checked_s = now_s
    return result
