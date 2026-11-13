from ai_dm.combat.actions.cast_support import condition_expiry, hold_concentration, spell_expiry
from ai_dm.combat.area import affected_zones
from ai_dm.combat.zones import cover_dc_bonus
from ai_dm.core.events import DomainEvent
from ai_dm.rules.derived import spell_save_dc
from ai_dm.rules.spellcasting import effect_of, modifier_params
from ai_dm.state.creature import ActiveEffect, AppliedCondition

# вторая стадия двухстадийного заклинания (Усыпление): «недееспособен» сразу, «без сознания»
# при провале повтора
STAGED = "unconscious"
# Усмирение чувств: состояния врага, проигравшего спасбросок
CALMED = ("charmed", "incapacitated")


def condition_names(engine, ids) -> str:
    return ", ".join(engine.registry.get("condition", i).name for i in ids)


def condition_targets(engine, ref, spell, target) -> list[str]:
    # цели условия: участники зоны (область) или перечисленные через запятую
    area = effect_of(spell, "area")
    if area is None:
        return target.split(",")
    covered = affected_zones(
        engine.state.zones, engine.part(ref).zone_id, area.shape, area.size_ft, target
    )
    return [
        q.ref for q in engine.state.participants
        if q.ref != ref and q.zone_id in covered and engine.targetable(q.ref)
    ]


def impose_effects(engine, ref, spell, target_ref, dc) -> None:
    # провал спасброска: состояния, штрафы и повтор спасброска (held)
    conditions = [e.condition for e in spell.effects if e.type == "apply_condition"]
    staged = len(conditions) > 1 and conditions[-1] == STAGED
    now = conditions[:-1] if staged else conditions
    name = engine.name(target_ref)
    applied = []
    for condition in now:
        expires = condition_expiry(engine, ref, spell)
        imposed = AppliedCondition(id=condition, source=spell.id, expires=expires)
        if engine.impose(target_ref, imposed):
            applied.append(condition)
    if applied:
        engine.log(f"  {name}: {condition_names(engine, applied)}")
    creature = engine.creature(target_ref)
    for effect in [e for e in spell.effects if e.type == "modifier"]:
        creature.active_effects.append(
            ActiveEffect(
                id=spell.id, source=ref, kind="modifier", params=modifier_params(effect),
                expires=condition_expiry(engine, ref, spell),
            )
        )
        engine.log(f"  {name}: {spell.name}")
    burn = effect_of(spell, "burn")
    if burn is not None:
        params = {"dice": burn.dice, "damage_type": burn.damage_type}
        creature.active_effects.append(
            ActiveEffect(
                id=spell.id, source=ref, kind="burn", params=params,
                expires=condition_expiry(engine, ref, spell),
            )
        )
    save = effect_of(spell, "save_effect")
    if save.repeat:
        params = {"ability": save.ability, "dc": dc, "condition": ",".join(now)}
        if staged:
            params["next"] = conditions[-1]
        creature.active_effects.append(
            ActiveEffect(
                id=spell.id, source=ref, kind="held", params=params,
                expires=condition_expiry(engine, ref, spell),
            )
        )


def cast_condition(engine, ref, spell, target, circle) -> list[DomainEvent]:
    hero = engine.heroes[ref]
    save = effect_of(spell, "save_effect")
    if spell.concentration:
        hold_concentration(engine, ref, spell, circle)
    dc = spell_save_dc(hero, engine.registry)
    area = effect_of(spell, "area") is not None
    for one in condition_targets(engine, ref, spell, target):
        cover = 0
        if area and engine.part(one).zone_id != engine.part(ref).zone_id:
            zone = [z for z in engine.state.zones if z.id == engine.part(one).zone_id][0]
            cover = cover_dc_bonus(zone)
        if engine.save(one, save.ability, dc, cover).outcome != "success":
            impose_effects(engine, ref, spell, one, dc)
    return []


def release_held(engine, target_ref, effect) -> None:
    # заклинание с повтором спасброска кончилось на цели: состояния и все его эффекты (held,
    # штрафы, КД и метка Замедления)
    creature = engine.creature(target_ref)
    creature.conditions = [c for c in creature.conditions if c.source != effect.id]
    creature.active_effects = [
        e for e in creature.active_effects
        if not (e.id == effect.id and e.source == effect.source)
    ]


def repeat_saves(engine, ref) -> None:
    # конец хода цели: повторный спасбросок удержанного (Р10); успех снимает заклинание,
    # провал у двухстадийного (Усыпление) -- «без сознания»
    if not engine.is_capable(ref):
        return
    for effect in [e for e in engine.creature(ref).active_effects if e.kind == "held"]:
        spell = engine.registry.get("spell", effect.id)
        if engine.save(ref, effect.params["ability"], effect.params["dc"]).outcome == "success":
            release_held(engine, ref, effect)
            engine.log(f"  {engine.name(ref)}: {spell.name} кончается")
        elif "next" in effect.params:
            following = AppliedCondition(
                id=effect.params["next"], source=spell.id, expires=effect.expires.model_copy()
            )
            engine.impose(ref, following)
            engine.creature(ref).active_effects.remove(effect)
            engine.log(f"  {engine.name(ref)}: {condition_names(engine, [following.id])}")


def cast_calm(engine, ref, spell, zone_id, circle) -> list[DomainEvent]:
    # Усмирение чувств: союзникам в зоне (и заклинателю) снимаются очарование и страх, каждый враг
    # бросает Харизму, провал -- очарован и недееспособен до урона (downed.UNTIL_DAMAGE)
    calm = effect_of(spell, "calm")
    hold_concentration(engine, ref, spell, circle)
    side = engine.part(ref).side
    inside = condition_targets(engine, ref, spell, zone_id)
    area = effect_of(spell, "area")
    covered = affected_zones(
        engine.state.zones, engine.part(ref).zone_id, area.shape, area.size_ft, zone_id
    )
    own = [ref] if engine.part(ref).zone_id in covered else []
    for one in own + [q for q in inside if engine.part(q).side == side]:
        creature = engine.creature(one)
        gone = [c.id for c in creature.conditions if c.id in calm.conditions]
        creature.conditions = [c for c in creature.conditions if c.id not in calm.conditions]
        if gone:
            engine.log(f"{engine.name(ref)}: {spell.name} снимает с {engine.name(one)}: "
                       f"{condition_names(engine, gone)}")
    dc = spell_save_dc(engine.heroes[ref], engine.registry)
    for one in [q for q in inside if engine.part(q).side != side]:
        if engine.save(one, calm.ability, dc).outcome != "success":
            for condition in CALMED:
                expires = condition_expiry(engine, ref, spell)
                engine.impose(one, AppliedCondition(id=condition, source=spell.id, expires=expires))
            engine.log(f"  {engine.name(one)}: {condition_names(engine, CALMED)}")
    return []


def cast_cure(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    # снимает первое по порядку данных состояние; Защита от яда ещё даёт сопротивление
    effect = effect_of(spell, "remove_condition")
    creature = engine.creature(target_ref)
    present = {c.id for c in creature.conditions}
    name = engine.name(target_ref)
    for condition in effect.conditions:
        if condition in present:
            creature.conditions = [c for c in creature.conditions if c.id != condition]
            engine.log(f"{engine.name(ref)}: {spell.name} снимает с {name}: "
                       f"{condition_names(engine, [condition])}")
            break
    resist = effect_of(spell, "resist")
    if resist is not None:
        creature.active_effects.append(
            ActiveEffect(
                id=spell.id, source=ref, kind="resist", params={"damage_type": resist.damage_type},
                expires=spell_expiry(engine, ref, spell),
            )
        )
        engine.log(f"{engine.name(ref)}: {spell.name} на {name}")
    return []
