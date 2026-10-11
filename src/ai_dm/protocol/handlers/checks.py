from ai_dm.protocol.decision import Decision
from ai_dm.rules import checks


def roll_decision(ctx, result, actor_id=None) -> Decision:
    ref = ctx.add_roll(result, actor_id)
    return Decision(
        status="accepted",
        result={"roll_ref": ref, "outcome": result.outcome, "dc": result.dc, "total": result.total},
        log=[result.log.text],
    )


def stakes_tags(request):
    if request.stakes is None:
        return None
    tags = {"stakes": request.stakes}
    if request.stakes == "critical":
        # критический момент для благосклонности богов (ТЗ 4.2)
        tags["critical_moment"] = True
    return tags


def skill_check(ctx, request):
    result = checks.skill_check(
        ctx.hero, ctx.registry, ctx.rng, request.skill, request.category,
        tags=stakes_tags(request), now_s=ctx.bundle.world.clock.now_s,
    )
    return roll_decision(ctx, result, ctx.hero.id)


def saving_throw(ctx, request):
    result = checks.saving_throw(
        ctx.hero, ctx.registry, ctx.rng, request.ability, request.category,
        tags=stakes_tags(request), now_s=ctx.bundle.world.clock.now_s,
    )
    return roll_decision(ctx, result, ctx.hero.id)
