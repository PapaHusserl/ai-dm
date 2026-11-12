from ai_dm.combat import zone_effects
from ai_dm.rules.derived import always_prepared
from ai_dm.rules.modifiers.conditions import with_implied
from ai_dm.rules.spellcasting import usable_circles


def react(engine, target_ref, from_zone_id) -> bool:
    # Падение пером (Р-К3б-6 а): падает сам герой с подготовленным заклинанием и ячейкой --
    # реакция читается сама, ячейка 1 круга и реакция тратятся, урон от падения 0; в зоне
    # Тишины (откуда падает герой) заклинаний не читают
    hero = engine.heroes.get(target_ref)
    if hero is None or not engine.part(target_ref).turn.reaction:
        return False
    conditions = {c.id for c in with_implied(engine.creature(target_ref))}
    mute = zone_effects.zone_effects(engine, from_zone_id, "silence")
    if not engine.is_capable(target_ref) or "incapacitated" in conditions or mute:
        return False
    prepared = list(hero.sheet.prepared_of()) + always_prepared(hero, engine.registry)
    spell = engine.registry.get("spell", "feather_fall")
    circles = usable_circles(hero, spell)
    if "feather_fall" not in prepared or not circles:
        return False
    hero.creature.resources[f"spell_slot:{circles[0]}"].current -= 1
    engine.part(target_ref).turn.reaction = False
    engine.log(f"  {spell.name}: {engine.name(target_ref)} опускается мягко")
    return True
