from ai_dm.protocol.decision import Invalid
from ai_dm.protocol.handlers import (
    checks,
    combat,
    hero,
    offscreen,
    pack,
    resources,
    summary,
    trade,
    world,
)
from ai_dm.protocol.requests import HERO_MODES, HIDDEN_TYPES, IMPORT_MODE

HANDLERS = {
    "skill_check": checks.skill_check,
    "saving_throw": checks.saving_throw,
    "start_combat": combat.start_combat,
    "player_action": combat.player_action,
    "npc_action": combat.npc_action,
    "defeat_outcome": combat.defeat_outcome,
    "end_combat": combat.end_combat,
    "damage": resources.damage,
    "give_item": resources.give_item,
    "give_custom_item": resources.give_custom_item,
    "use_item": resources.use_item,
    "cast_spell": resources.cast_spell,
    "take_item": resources.take_item,
    "trade": trade.trade,
    "haggle": trade.haggle,
    "gold": resources.gold,
    "award_xp": resources.award_xp,
    "advance_time": resources.advance_time,
    "rest": resources.rest,
    "set_flag": world.set_flag,
    "npc_create": world.npc_create,
    "location_create": world.location_create,
    "npc_update": world.npc_update,
    "favor_change": world.favor_change,
    "pray": world.pray,
    "companion_update": hero.companion_update,
    "offer_choices": world.offer_choices,
    "end_scene": world.end_scene,
    "end_chapter": world.end_chapter,
    "reveal_secret": world.reveal_secret,
    "event_start": world.event_start,
    "event_end": world.event_end,
    "warn_danger": world.warn_danger,
    "unsupported_action": world.unsupported_action,
}

# закрытый набор роли world: тот же движок, закадровые версии запросов
WORLD_HANDLERS = {
    "world_verdict": offscreen.world_verdict,
    "world_notice": offscreen.world_notice,
    "skill_check": offscreen.skill_check,
    "saving_throw": offscreen.saving_throw,
    "npc_update": offscreen.npc_update,
    "set_flag": offscreen.set_flag,
    "favor_change": offscreen.favor_change,
    "npc_create": world.npc_create,
    "location_create": world.location_create,
    "event_start": world.event_start,
    "event_end": world.event_end,
    "warn_danger": world.warn_danger,
}

# служебный набор роли summarizer
SUMMARY_HANDLERS = {
    "scene_summary": summary.scene_summary,
    "chapter_summary": summary.chapter_summary,
    "game_summary": summary.game_summary,
}

# служебный набор создания героя
HERO_HANDLERS = {
    "hero_background": {"background_spec": hero.background_spec},
    "hero_sheet": {"hero_sheet": hero.hero_sheet},
}

# служебный набор import пака
IMPORT_HANDLERS = {"pack": pack.pack_spec}


def apply(ctx, request):
    name = request.type
    service = None
    if ctx.mode in HERO_MODES:
        service = (HERO_HANDLERS[ctx.mode], "создания героя")
    elif ctx.mode == IMPORT_MODE:
        service = (IMPORT_HANDLERS, "import пака")
    elif ctx.mode.startswith("summarize_"):
        service = (SUMMARY_HANDLERS, "summarizer")
    elif ctx.mode == "world":
        service = (WORLD_HANDLERS, "world")
    if service is not None:
        handlers, label = service
        if name not in handlers:
            return Invalid(code="not_available_in_mode", message=f"запрос {name!r}: не для {label}")
        outcome = handlers[name](ctx, request)
    elif name in HIDDEN_TYPES:
        return Invalid(
            code="not_available_on_stage", message=f"запрос {name!r} пока недоступен"
        )
    else:
        outcome = HANDLERS[name](ctx, request)
    if not isinstance(outcome, Invalid) and outcome.report_tag is not None:
        ctx.marks.append(outcome.report_tag)
    return outcome
