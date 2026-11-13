from ai_dm.combat import downed, sanctuary
from ai_dm.combat.actions.attack import attack_event, reveal
from ai_dm.combat.actions.cast_guards import place
from ai_dm.combat.actions.cast_support import TARGETABLE, hold_concentration
from ai_dm.combat.area import affected_zones
from ai_dm.combat.zones import cover_dc_bonus
from ai_dm.core.dice import roll_dice
from ai_dm.core.events import DomainEvent
from ai_dm.rules.creatures import live_effects
from ai_dm.rules.derived import spell_save_dc
from ai_dm.rules.spellcasting import effect_of


def breath_effect(engine, ref):
    # эффект Дыхания дракона на существе: тип урона и кости; None -- выдыхать нечем
    now_s = engine.world.clock.now_s
    found = [e for e in live_effects(engine.creature(ref), now_s) if e.kind == "breath"]
    return found[0] if found else None


def cone_zones(engine, ref, cone) -> list:
    # своя и соседние зоны: конус 15 футов
    own = engine.part(ref).zone_id
    result = []
    for zone in engine.state.zones:
        try:
            affected_zones(engine.state.zones, own, cone.shape, cone.size_ft, zone.id)
        except ValueError:
            continue
        result.append(zone)
    return result


def breath_name(engine, effect) -> str:
    # «Дыхание дракона (огонь)»
    from ai_dm.combat.available import VARIANT_WORDS

    spell = engine.registry.get("spell", effect.id)
    return f"{spell.name} ({VARIANT_WORDS[effect.params['damage_type']]})"


def breath_options(engine, ref) -> list:
    # выдох действием: по пункту на зону конуса, пока держится концентрация
    from ai_dm.combat.available import ActionOption

    effect = breath_effect(engine, ref)
    if effect is None or not engine.part(ref).turn.action:
        return []
    cone = effect_of(engine.registry.get("spell", effect.id), "breath")
    return [
        ActionOption(
            id=f"breath:{zone.id}", kind="breath",
            label=f"{breath_name(engine, effect)} → {zone.name}",
            params={"zone": zone.id}, cost="action",
        )
        for zone in cone_zones(engine, ref, cone)
    ]


def cast_breath(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    # согласное существо получает выдох на время концентрации заклинателя
    hold_concentration(engine, ref, spell, circle)
    effect = effect_of(spell, "breath")
    params = {"damage_type": effect.damage_type, "dice": effect.dice}
    place(engine, ref, spell, target_ref, {"breath": params})
    return []


def perform(engine, ref, option) -> list[DomainEvent]:
    # один бросок 3d6 на всех в конусе; у каждого свой спасбросок, успех -- половина
    reveal(engine, ref)
    sanctuary.drop(engine, ref)
    effect = breath_effect(engine, ref)
    spell = engine.registry.get("spell", effect.id)
    cone = effect_of(spell, "breath")
    engine.part(ref).turn.action = False
    kind = effect.params["damage_type"]
    dc = spell_save_dc(engine.heroes[effect.source], engine.registry)
    total = roll_dice(effect.params["dice"], engine.rng).total
    covered = affected_zones(
        engine.state.zones, engine.part(ref).zone_id, cone.shape, cone.size_ft,
        option.params["zone"],
    )
    engine.log(f"{engine.name(ref)}: {breath_name(engine, effect)}: "
               f"{effect.params['dice']} = {total}")
    events = []
    for q in list(engine.state.participants):
        if q.ref == ref or q.zone_id not in covered or q.status not in TARGETABLE:
            continue
        cover = 0
        if q.zone_id != engine.part(ref).zone_id:
            cover = cover_dc_bonus([z for z in engine.state.zones if z.id == q.zone_id][0])
        saved = engine.save(q.ref, cone.ability, dc, cover).outcome == "success"
        dealt = engine.damage(q.ref, total // 2 if saved else total, kind)
        engine.log_notes(dealt)
        engine.log(f"  {engine.name(q.ref)}: {engine.hp_text(q.ref)}")
        events.append(attack_event(ref, q.ref, spell.id, "spell", "auto", dealt.final))
        events += downed.after_damage(engine, q.ref, dealt, ref)
    return events
