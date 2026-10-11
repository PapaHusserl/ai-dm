from ai_dm.rules.derived import ability_modifier, initiative_bonus
from ai_dm.rules.roll_pipeline import RollRequest, roll


def dex_score(engine, ref) -> int:
    if engine.is_hero(ref):
        return engine.heroes[ref].sheet.abilities["dex"]
    return engine.monster(ref).abilities["dex"]


def roll_initiative(engine) -> None:
    # бросок на каждого в порядке участников, потом порядок хода
    for p in engine.state.participants:
        if engine.is_hero(p.ref):
            bonus = initiative_bonus(engine.heroes[p.ref], engine.registry)
        else:
            bonus = ability_modifier(dex_score(engine, p.ref))
        base_adv = "normal"
        if p.surprised:
            base_adv = "disadvantage"
        request = RollRequest(
            kind="initiative", actor=engine.actor(p.ref), actor_id=p.ref, ability="dex",
            bonus=bonus, base_adv=base_adv,
        )
        result = roll(request, engine.rng, engine.registry, modifiers=engine.modifiers)
        p.initiative = result.total
        engine.log(f"{engine.name(p.ref)}: инициатива {result.log.text}")
    # по убыванию инициативы; ничья -- выше ЛОВ, затем меньший id
    order = sorted(
        engine.state.participants,
        key=lambda p: (-p.initiative, -dex_score(engine, p.ref), p.ref),
    )
    engine.state.initiative_order = [p.ref for p in order]
