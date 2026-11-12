from ai_dm.combat.actions.cast_support import spell_expiry
from ai_dm.core.events import DomainEvent
from ai_dm.rules.derived import spell_save_dc
from ai_dm.rules.spellcasting import effect_of, has_effect
from ai_dm.state.creature import ActiveEffect


def place(engine, ref, spell, target_ref, kinds) -> None:
    # эффекты заклинания на цель: {вид: параметры}; прежние того же заклинания заменяются
    place_pairs(engine, ref, spell, target_ref, list(kinds.items()))


def place_pairs(engine, ref, spell, target_ref, pairs) -> None:
    # то же, что place, но [(вид, параметры)]: вид может повторяться (Газообразная форма)
    creature = engine.creature(target_ref)
    creature.active_effects = [e for e in creature.active_effects if e.id != spell.id]
    for kind, params in pairs:
        creature.active_effects.append(
            ActiveEffect(
                id=spell.id, source=ref, kind=kind, params=params,
                expires=spell_expiry(engine, ref, spell),
            )
        )
    engine.log(f"{engine.name(ref)}: {spell.name} на {engine.name(target_ref)}")


def cast_sanctuary(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    # враг, выбравший цель, бросает Мудрость против СЛ заклинателя (sanctuary.blocks)
    dc = spell_save_dc(engine.heroes[ref], engine.registry)
    place(engine, ref, spell, target_ref, {"sanctuary": {"dc": dc}})
    return []


def guard_kinds(spell) -> dict:
    # эффекты Защитных уз и Видения невидимого: {вид: параметры}; у прочих заклинаний пусто
    if has_effect(spell, "see_invisible"):
        return {"see_invisible": {}}
    if not has_effect(spell, "bond"):
        return {}
    # +1 к КД и спасброскам, сопротивление всему урону; урон цели делит bond.share
    amount = effect_of(spell, "bond").value
    return {
        "ac": {"label": spell.name, "amount": amount, "magic": True},
        "modifier": {"target": "saving_throw", "amount": amount},
        "resist": {"damage_type": "all"},
        "bond": {},
    }


def cast_guard(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    place(engine, ref, spell, target_ref, guard_kinds(spell))
    return []
