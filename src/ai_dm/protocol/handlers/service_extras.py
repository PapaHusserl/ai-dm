from ai_dm.protocol.handlers.world import npc_label
from ai_dm.rules import services as service_rules
from ai_dm.rules.boons import BOONS, grant_boon
from ai_dm.rules.consequences import disease_check, jealousy, theft_check
from ai_dm.rules.npc_memory import has_kind, remember
from ai_dm.state.relations import MEMORY_KIND_TITLES, NpcEvent


def remember_deal(ctx, npc, kind, decision) -> None:
    # платная близость: флаг для romance_gate и сделка в памяти NPC (одна на сцену)
    ctx.bundle.world.flags[f"{service_rules.PAID_COMPANY_FLAG}:{ctx.hero.id}:{npc.id}"] = True
    scene = ctx.scene
    if scene is None or has_kind(npc, scene, "deal"):
        return
    event = NpcEvent(kind="deal", turn_seq=ctx.turn_seq, text=f"купил(а) услугу: {kind.name}")
    if remember(npc, scene, event, ctx.cfg.npc_memory) is not None:
        decision.log.append(f"{npc_label(npc)} запомнит это: {MEMORY_KIND_TITLES['deal']}")


def boon_and_risks(ctx, npc, kind, decision) -> None:
    # бонус услуги после принятой оплаты: result, строка лога, сигнал мастеру
    if kind.boon:
        line, granted = grant_boon(ctx, kind.boon, npc)
        decision.result["boon"] = kind.boon
        decision.log.append(line)
        if granted:
            add_signal(decision, f"Герою достался бонус: {BOONS[kind.boon][0]}.")
    if kind.intimate:
        add_consequences(ctx, npc, kind, decision)


def add_signal(decision, note) -> None:
    decision.signal_to_master = " ".join(x for x in (decision.signal_to_master, note) if x)


def add_consequences(ctx, npc, kind, decision) -> None:
    # последствия платной близости (один раз за покупку): ревность, кража, болезнь
    happened = []
    refs = []
    outcomes = (jealousy(ctx, npc), theft_check(ctx, kind, npc), disease_check(ctx, kind, npc))
    for outcome in outcomes:
        if outcome is None:
            continue
        key, lines, signal, ref = outcome
        decision.log.extend(lines)
        if ref is not None:
            refs.append(ref)
        if key is not None:
            happened.append(key)
            add_signal(decision, signal)
    if happened:
        decision.result["consequences"] = happened
    if refs:
        decision.result["consequence_rolls"] = refs
