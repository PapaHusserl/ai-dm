from ai_dm.protocol.context import owes_price
from ai_dm.protocol.decision import Decision
from ai_dm.rules import checks
from ai_dm.rules.roll_pipeline import spent_lines


def roll_decision(ctx, result, actor_id=None) -> Decision:
    ref = ctx.add_roll(result, actor_id)
    data = {"roll_ref": ref, "outcome": result.outcome, "dc": result.dc, "total": result.total}
    if "position" in result.tags:
        data["position"] = result.tags["position"]
    if owes_price(result):
        data["price_due"] = True
    return Decision(
        status="accepted",
        result=data,
        log=[result.log.text, *spent_lines(result)],
    )


def position_tags(request):
    tags = {"position": request.position}
    if request.position == "desperate":
        # критический момент для благосклонности богов (ТЗ 4.2)
        tags["critical_moment"] = True
    return tags


def skill_check(ctx, request):
    result = checks.skill_check(
        ctx.hero, ctx.registry, ctx.rng, request.skill, request.category,
        tags=position_tags(request), now_s=ctx.bundle.world.clock.now_s,
    )
    return roll_decision(ctx, result, ctx.hero.id)


def saving_throw(ctx, request):
    result = checks.saving_throw(
        ctx.hero, ctx.registry, ctx.rng, request.ability, request.category,
        tags=position_tags(request), now_s=ctx.bundle.world.clock.now_s,
    )
    return roll_decision(ctx, result, ctx.hero.id)
