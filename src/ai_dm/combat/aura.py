from ai_dm.combat import downed
from ai_dm.combat.actions.attack import attack_event, roll_damage, split_dice
from ai_dm.core.dice import parse_dice
from ai_dm.core.events import DomainEvent
from ai_dm.rules.derived import spell_save_dc
from ai_dm.state.creature import ActiveEffect

# Аура заклинателя (Духовные стражи, SRD 5.2.1): спасбросок и урон врагу, который входит в область
# или заканчивает в ней ход, и врагу, к которому подходит заклинатель; раз в ход существа


def auras_of(engine, ref) -> list[ActiveEffect]:
    return [e for e in engine.creature(ref).active_effects if e.kind == "aura"]


def tick(engine, ref) -> list[DomainEvent]:
    # враг ref стоит в зоне заклинателя с аурой: конец его хода или вход в зону
    if not engine.is_capable(ref):
        return []
    here = engine.part(ref)
    # одно заклинание от нескольких жрецов не складывается: бьёт сильнейшая аура (больше кубов),
    # при равенстве — первая по порядку участников (SRD 5.2.1, Combining Spell Effects)
    best = {}
    for caster in engine.state.participants:
        if caster.side == here.side or caster.zone_id != here.zone_id:
            continue
        for effect in auras_of(engine, caster.ref):
            current = best.get(effect.id)
            if current is None or dice_count(effect) > dice_count(current[1]):
                best[effect.id] = (caster.ref, effect)
    events = []
    for caster_ref, effect in best.values():
        if engine.is_capable(ref):
            events += hit_by_aura(engine, (caster_ref, ref), effect)
    return events


def dice_count(effect) -> int:
    return parse_dice(effect.params["dice"]).count


def on_enter(engine, ref) -> list[DomainEvent]:
    # ref вошёл в зону: если он враг заклинателя в ней — тик; если он сам заклинатель с аурой —
    # все враги в этой зоне
    events = tick(engine, ref)
    if not auras_of(engine, ref):
        return events
    # вошедший уже стоит в зоне: tick каждого врага сам находит все ауры зоны и берёт сильнейшую
    here = engine.part(ref)
    for q in engine.state.participants:
        if q.side != here.side and q.zone_id == here.zone_id:
            events += tick(engine, q.ref)
    return events


def clear_marks(engine) -> None:
    # конец хода любого участника: метки «уже бит в этот ход» снимаются у всех (SRD 5.2.1)
    for _, creature in engine.all_creatures():
        creature.active_effects = [
            e for e in creature.active_effects if not e.id.startswith("aura_hit:")
        ]


def hit_by_aura(engine, pair, effect) -> list[DomainEvent]:
    caster_ref, ref = pair
    creature = engine.creature(ref)
    flag_id = f"aura_hit:{effect.id}"
    if any(e.id == flag_id for e in creature.active_effects):
        return []
    # метка «уже бит в этот ход» — до конца хода любого участника (clear_marks)
    creature.active_effects.append(ActiveEffect(id=flag_id, source=caster_ref, kind="flag"))
    name = engine.registry.get("spell", effect.params["spell"]).name
    params = effect.params
    dice, bonus = split_dice(params["dice"])
    engine.log(f"{engine.name(ref)} в зоне: {name}")
    rolled = roll_damage(
        engine, caster_ref, dice, bonus, False, label=f"Урон ({name})",
        parts=[(name, bonus)], damage_type=params["damage_type"],
    )
    dc = spell_save_dc(engine.heroes[caster_ref], engine.registry)
    saved = engine.save(ref, params["ability"], dc).outcome == "success"
    amount = rolled.total // 2 if saved else rolled.total
    dealt = engine.damage(ref, amount, params["damage_type"])
    engine.log_notes(dealt)
    engine.log(f"  {engine.name(ref)}: {engine.hp_text(ref)}")
    events = [attack_event(caster_ref, ref, effect.id, "spell", "auto", dealt.final)]
    return events + downed.after_damage(engine, ref, dealt, caster_ref)
