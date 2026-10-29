from ai_dm.content.models.common import SKILLS
from ai_dm.core.clock import DAY
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.protocol.handlers import checks
from ai_dm.protocol.handlers.world import (
    GOAL_FIELDS,
    change_attitude,
    change_follows,
    change_goal,
    change_identity,
    change_location,
    change_status,
    death_refused,
    favor_change_for,
    goal_problem,
    location_problem,
    nothing_to_change,
    rejected,
)
from ai_dm.protocol.handlers.world import (
    set_flag as base_set_flag,
)
from ai_dm.protocol.hints import allowed
from ai_dm.rules.checks import dc_for_category
from ai_dm.rules.roll_pipeline import RollRequest, roll
from ai_dm.state.creature import CreatureState
from ai_dm.state.memory import add_entry
from ai_dm.state.world import Notice

DELAYS = {"none": 0, "day": DAY, "week": 7 * DAY}


def npc_actor(ctx, npc_id):
    # NPC без листа: бросок d20 без бонуса; состояние -- NPC.creature или временное
    npc = ctx.bundle.world.npcs.get(npc_id)
    if npc is None:
        return None, Invalid(
            code="unknown_npc",
            message=f"нет NPC {npc_id!r}" + allowed(ctx.bundle.world.npcs),
        )
    if npc.status != "alive":
        return None, Invalid(code="npc_not_alive", message=f"{npc.name} не жив")
    return npc, None


def actor_state(npc):
    if npc.creature is not None:
        return npc.creature
    return CreatureState(hp_current=1, hp_max=1)


def check_then_ref(ctx, then_ref):
    # then_ref -- ref кандидата вызова; на verdict -- только после world_verdict с holds=true
    if then_ref not in ctx.candidate_refs:
        return Invalid(
            code="invalid_then_ref",
            message=f"нет кандидата {then_ref!r}" + allowed(ctx.candidate_refs),
        )
    if then_ref in ctx.verdict_refs and not (ctx.verdicts or {}).get(then_ref, False):
        return Invalid(
            code="verdict_not_confirmed",
            message=f"{then_ref}: сначала world_verdict с holds=true по этому кандидату",
        )
    return None


def actor_required():
    return Invalid(
        code="actor_required", message="за кадром бросает NPC: укажи actor (id NPC)"
    )


def skill_check(ctx, request):
    if request.actor is None:
        return actor_required()
    npc, invalid = npc_actor(ctx, request.actor)
    if invalid is not None:
        return invalid
    result = roll(
        RollRequest(
            kind="check", actor=actor_state(npc), actor_id=npc.id, ability=SKILLS[request.skill],
            skill=request.skill, tags=checks.stakes_tags(request) or {}, bonus=0,
            dc=dc_for_category(request.category, ctx.registry),
        ),
        ctx.rng, ctx.registry,
    )
    return checks.roll_decision(ctx, result, npc.id)


def saving_throw(ctx, request):
    if request.actor is None:
        return actor_required()
    npc, invalid = npc_actor(ctx, request.actor)
    if invalid is not None:
        return invalid
    result = roll(
        RollRequest(
            kind="save", actor=actor_state(npc), actor_id=npc.id, ability=request.ability,
            tags=checks.stakes_tags(request) or {}, bonus=0,
            dc=dc_for_category(request.category, ctx.registry),
        ),
        ctx.rng, ctx.registry,
    )
    return checks.roll_decision(ctx, result, npc.id)


def basic_problem(ctx, npc, request):
    # Invalid для пустого запроса, не живого NPC, идущего с героем, и неверной цели, иначе None
    if nothing_to_change(
        request, "attitude_delta", "status", "location_id", "follows", "gender", "pronouns",
        *GOAL_FIELDS,
    ):
        return Invalid(code="empty_update", message="в npc_update нечего менять")
    if request.follows == "hero" and npc.status != "alive":
        return Invalid(code="npc_not_alive", message=f"{npc.name} не жив: не идёт с героем")
    return goal_problem(ctx, npc, request) or location_problem(ctx.bundle.world, npc, request)


def npc_update(ctx, request):
    world = ctx.bundle.world
    invalid = check_then_ref(ctx, request.then_ref)
    if invalid is not None:
        return invalid
    npc = world.npcs.get(request.npc_id)
    if npc is None:
        return Invalid(
            code="unknown_npc", message=f"нет NPC {request.npc_id!r}" + allowed(world.npcs)
        )
    invalid = basic_problem(ctx, npc, request)
    if invalid is not None:
        return invalid
    # смерть за кадром: бросок-доказательство должен быть броском этого же NPC
    own_roll = ctx.roll_actors.get(request.evidence_ref) == npc.id
    if request.status is not None and death_refused(ctx, npc, request, own_roll=own_roll):
        return rejected(
            "у смерти должна быть причина (goal или hazard) и не потраченный бросок этого вызова",
            f"{npc.name} остаётся жив: смерть без причины goal/hazard и "
            "evidence_ref на не потраченный бросок этого вызова не принимается.",
            report_tag="invalid-death",
        )
    decision = Decision(status="accepted")
    if request.location_id is not None:
        change_location(ctx, npc, request, decision)
    if request.follows is not None:
        change_follows(ctx, npc, request, decision)
    change_identity(npc, request, decision)
    if request.attitude_delta is not None:
        change_attitude(ctx, npc, request.attitude_delta, decision)
    if request.goal_kind is not None:
        change_goal(ctx, npc, request, decision)
    if request.status is not None:
        change_status(ctx, npc, request, decision, own_roll)
    return decision


def favor_change(ctx, request):
    # закадровое изменение благосклонности NPC (ТЗ 4.2): с теми же лимитами
    world = ctx.bundle.world
    npc = world.npcs.get(request.target)
    if npc is None:
        return Invalid(
            code="unknown_npc",
            message=f"нет NPC {request.target!r}; target — id NPC" + allowed(world.npcs),
        )
    return favor_change_for(ctx, npc, f"{npc.id}:{request.god_id}", request)


def set_flag(ctx, request):
    if request.then_ref is not None:
        invalid = check_then_ref(ctx, request.then_ref)
        if invalid is not None:
            return invalid
    return base_set_flag(ctx, request)


def world_verdict(ctx, request):
    if ctx.verdicts is not None:
        return Invalid(code="verdict_done", message="вердикты уже даны, повторять не нужно")
    refs = [item.ref for item in request.items]
    expected = set(ctx.verdict_refs)
    extra = sorted(set(refs) - expected)
    missing = sorted(expected - set(refs))
    if extra or missing or len(refs) != len(set(refs)):
        return Invalid(
            code="invalid_verdict_refs",
            message=f"лишние ref: {extra}; пропущенные ref: {missing}; "
            f"нужен ровно один элемент на каждый: {sorted(expected)}",
        )
    ctx.verdicts = {item.ref: item.holds for item in request.items}
    return Decision(status="accepted", log=[f"Вердиктов: {len(refs)}"])


def world_notice(ctx, request):
    if not request.text.strip():
        return Invalid(code="empty_text", message="у заметки нет текста")
    if request.then_ref is not None:
        invalid = check_then_ref(ctx, request.then_ref)
        if invalid is not None:
            return invalid
    world = ctx.bundle.world
    now_s = world.clock.now_s
    notice = Notice(
        id=f"ntc_{now_s}_{len(ctx.notice_ids) + 1}", at_s=now_s,
        deliver_at_s=now_s + DELAYS[request.delay], visibility=request.visibility,
        text=request.text, refs=list(request.refs),
    )
    world.notices.append(notice)
    ctx.notice_ids.append(notice.id)
    if notice.visibility == "hidden":
        add_entry(ctx.bundle, "event", notice.text, notice.refs)
    return Decision(status="accepted", result={"notice_id": notice.id}, log=["Заметка записана"])
