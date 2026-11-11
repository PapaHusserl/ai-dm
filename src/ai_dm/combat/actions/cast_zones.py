from ai_dm.combat import zone_effects
from ai_dm.combat.actions.cast_effects import cast_zone
from ai_dm.combat.actions.cast_support import hold_concentration
from ai_dm.core.events import DomainEvent
from ai_dm.rules.derived import spell_save_dc
from ai_dm.rules.spellcasting import effect_of


def zone_params(engine, ref, mode) -> dict:
    # метки зоны на заклинателе; Ледяной шторм несёт СЛ спасброска Ловкости
    params = {"kind": mode}
    if mode == "sleet":
        params["dc"] = spell_save_dc(engine.heroes[ref], engine.registry)
    return params


def cast_zone_spell(engine, ref, spell, zone_id, circle) -> list[DomainEvent]:
    # Тьма, Тишина, Ледяной шторм -- зона на концентрации; Дневной свет не держится: снимает
    # Тьму своей зоны. Магический круг в бою не читается (минута), его место -- вне боя
    mode = effect_of(spell, "zone").mode
    if mode == "light":
        zone_effects.lights_out(engine, zone_id)
        name = [z.name for z in engine.state.zones if z.id == zone_id][0]
        engine.log(f"{engine.name(ref)}: {spell.name} — {name}")
        return []
    hold_concentration(engine, ref, spell, circle)
    cast_zone(engine, ref, spell, zone_id, zone_params(engine, ref, mode))
    return []
