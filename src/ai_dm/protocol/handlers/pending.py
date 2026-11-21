from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.protocol.handlers.resources import spent_fail_ref
from ai_dm.protocol.handlers.world import rejected
from ai_dm.protocol.hints import allowed
from ai_dm.rules.creatures import creature_of, ensure_creature, is_hero
from ai_dm.rules.work_hours import next_hour_s
from ai_dm.state.world import PendingEvent

# строка ленты в момент начала: не длиннее
TEXT_MAX = 80


def target_of(ctx, target_id):
    # герой или NPC по id; None, если такого нет
    if target_id == ctx.hero.id:
        return ctx.hero
    return ctx.bundle.world.npcs.get(target_id)


def request_problem(ctx, request):
    # Invalid: состояния нет в списке конфига, hours < 1, цель неизвестна или мертва; иначе None
    conditions = ctx.cfg.time.delayed_conditions
    if request.condition not in conditions:
        return Invalid(
            code="unknown_condition",
            message=f"состояние {request.condition!r} отложить нельзя" + allowed(conditions),
        )
    if request.when == "hours" and (request.hours is None or request.hours < 1):
        return Invalid(code="bad_hours", message="when=hours: hours — целое число от 1")
    target = target_of(ctx, request.target)
    if target is None:
        return Invalid(
            code="unknown_target",
            message=f"нет цели {request.target!r}"
            + allowed([ctx.hero.id, *ctx.bundle.world.npcs]),
        )
    if target.status == "dead":
        return Invalid(code="target_dead", message=f"цель {request.target!r} мертва")
    return None


def repeat_problem(ctx, request, target):
    # rejected, если запись уже лежит в world.pending или цель уже несёт состояние; иначе None
    creature = creature_of(target)
    carries = creature is not None and any(
        c.id == request.condition for c in creature.conditions
    )
    queued = any(
        e.target == request.target and e.ref == request.condition
        for e in ctx.bundle.world.pending
    )
    if not carries and not queued:
        return None
    return rejected(
        "состояние уже отложено или есть",
        f"{request.target}: «{request.condition}» уже есть или отложено — повтор не нужен. "
        "Опиши по факту.",
    )


def delayed_condition(ctx, request):
    problem = request_problem(ctx, request)
    if problem is not None:
        return problem
    # до траты failed_roll_ref: пустой текст бросок не сжигает
    text = request.text.strip()[:TEXT_MAX]
    if not text:
        return Invalid(code="empty_text", message="text: строка ленты не может быть пустой")
    target = target_of(ctx, request.target)
    problem = repeat_problem(ctx, request, target)
    if problem is not None:
        return problem
    # герою — только после проваленного броска этого хода (как проклятие); NPC — без броска
    if is_hero(target) and not spent_fail_ref(ctx, request.failed_roll_ref):
        return rejected(
            "отложенное состояние героя без проваленного броска этого хода",
            "Герою отложенное состояние — только после его проваленного броска этого хода: "
            "вызови saving_throw или skill_check и передай roll_ref в failed_roll_ref.",
        )
    world = ctx.bundle.world
    now_s = world.clock.now_s
    if request.when == "morning":
        at_s = next_hour_s(now_s, ctx.cfg.time.morning_hour)
    else:
        at_s = now_s + request.hours * 3600
    if not is_hero(target):
        ensure_creature(target, ctx.registry)
    world.pending.append(
        PendingEvent(
            at_s=at_s, target=request.target, kind="condition", ref=request.condition,
            text=text,
        )
    )
    return Decision(status="accepted", result={"at_s": at_s})
