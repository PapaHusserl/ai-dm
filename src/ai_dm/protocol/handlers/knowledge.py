import re

from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.protocol.handlers.world import rejected
from ai_dm.protocol.hints import allowed
from ai_dm.rules.knowledge import remember_fact, shorten_text, spoils
from ai_dm.state.knowledge import KNOWLEDGE_TEXT_MAX, KnowledgeEntry

# вид -> словарь мира, ключи которого -- ref (creature -- реестр монстров, situation -- слаг)
WORLD_REFS = {"npc": "npcs", "location": "locations", "faction": "factions", "god": "pantheon"}
SLUG = re.compile(r"^[a-z0-9_]{2,40}$")


def known_refs(ctx, kind):
    if kind == "creature":
        return ctx.registry.ids("monster")
    return getattr(ctx.bundle.world, WORLD_REFS[kind])


def ref_problem(ctx, request):
    if request.kind == "situation":
        if SLUG.match(request.ref):
            return None
        return Invalid(
            code="bad_ref", message="ref ситуации: слаг латиницей a-z, 0-9, _ (2-40 знаков)"
        )
    refs = known_refs(ctx, request.kind)
    if request.ref in refs:
        return None
    return Invalid(
        code="unknown_ref", message=f"нет {request.kind} {request.ref!r}" + allowed(refs)
    )


def source_problem(ctx, request):
    if request.source == "told" and not request.from_ref:
        return Invalid(code="told_without_from", message="source told: нужен from_ref (id NPC)")
    npcs = ctx.bundle.world.npcs
    if request.from_ref and request.from_ref not in npcs:
        return Invalid(
            code="unknown_npc", message=f"нет NPC {request.from_ref!r}" + allowed(npcs)
        )
    return None


def unrevealed_texts(world):
    # тексты секретов, о которых герой ещё не знает
    return [
        s.text for npc in world.npcs.values() for s in npc.secrets
        if not s.revealed and s.id not in npc.known_to_player
    ]


def spoiler_problem(ctx, request):
    if not spoils(request.text, unrevealed_texts(ctx.bundle.world)):
        return None
    return rejected(
        "секрет ещё не раскрыт",
        "Секрет ещё не раскрыт: в журнал его не записать. Раскрой его через reveal_secret, "
        "когда условие выполнено.",
        report_tag="spoiler",
    )


def note_problem(ctx, request):
    # Invalid/rejected, если заметка не принимается, иначе None
    if not request.text.strip():
        return Invalid(code="empty_text", message="текст заметки пуст")
    return (
        ref_problem(ctx, request) or source_problem(ctx, request)
        or spoiler_problem(ctx, request)
    )


def ref_name(ctx, request):
    if request.kind in WORLD_REFS:
        return known_refs(ctx, request.kind)[request.ref].name
    return request.ref


def knowledge_note(ctx, request):
    problem = note_problem(ctx, request)
    if problem is not None:
        return problem
    text = request.text.strip()
    short = shorten_text(text, KNOWLEDGE_TEXT_MAX)
    entry = KnowledgeEntry(
        kind=request.kind, ref=request.ref, text=short, source=request.source,
        from_ref=request.from_ref, at_s=ctx.bundle.world.clock.now_s,
    )
    if not remember_fact(ctx.hero, entry, ctx.cfg.knowledge):
        return rejected("уже записано", "В журнале знаний это уже есть: не записывай повторно.")
    decision = Decision(
        status="accepted", log=[f"В журнал знаний (/lore): {ref_name(ctx, request)}"]
    )
    if short != text:
        note = f"текст укорочен до {KNOWLEDGE_TEXT_MAX}"
        decision.status = "clamped"
        decision.report_tag = "text-shortened"
        decision.reason = note
        decision.signal_to_master = f"Журнал знаний: {note} знаков."
        decision.log.append(f"Журнал: {note}")
    return decision


def scene_mood(ctx, request):
    scene = ctx.scene
    if scene is None:
        return Invalid(code="no_scene", message="настроение ставится в сцене, а сцены сейчас нет")
    scene.scene_mood = request.mood or ""
    if request.mood is None:
        return Decision(status="accepted", log=["Настроение сцены снято"])
    return Decision(status="accepted", log=[f"Настроение сцены: {request.mood}"])
