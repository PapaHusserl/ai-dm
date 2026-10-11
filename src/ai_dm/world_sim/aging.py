from ai_dm.state.creature import ActiveEffect
from ai_dm.state.memory import add_entry
from ai_dm.world_sim.mortality import remove, tracked


def lifespan(registry, species_id) -> tuple[int, int] | None:
    # (порог старости, предел) в годах; нет вида в таблице -- не стареет
    if species_id is None or not registry.has("table", "lifespan"):
        return None
    rows = registry.get("table", "lifespan").rows
    if f"{species_id}:threshold" not in rows:
        return None
    return rows[f"{species_id}:threshold"], rows[f"{species_id}:limit"]


def species_and_birth(kind, creature):
    if kind == "npc":
        return creature.species_id, creature.birth_s
    return creature.sheet.species_id, creature.birth_s


def old_age_effect(hero):
    for effect in hero.creature.active_effects:
        if effect.id == "old_age":
            return effect
    return None


def current_steps(kind, creature) -> int:
    if kind == "npc":
        return creature.aging_steps
    effect = old_age_effect(creature)
    return 0 if effect is None else int(effect.params["steps"])


def set_steps(kind, creature, steps) -> None:
    if kind == "npc":
        creature.aging_steps = steps
        return
    effect = old_age_effect(creature)
    if effect is None:
        creature.creature.active_effects.append(
            ActiveEffect(id="old_age", source="aging", kind="old_age", params={"steps": steps})
        )
    else:
        effect.params["steps"] = steps


def roll_year(bundle, rng, cfg, registry, at) -> list:
    # старость (ТЗ 4.1 п.4), раз в год: после порога шанс (возраст - порог) / (предел - порог)
    world = bundle.world
    year_s = world.clock.calendar.seconds_in_year
    events = []
    for kind, creature in tracked(bundle):
        species_id, birth_s = species_and_birth(kind, creature)
        span = lifespan(registry, species_id)
        if span is None or birth_s is None:
            continue
        threshold, limit = span
        age = (at - birth_s) // year_s
        if age <= threshold:
            continue
        if age >= limit or rng.randbelow(limit - threshold) < age - threshold:
            events += remove(bundle, kind, creature, "old_age", at)
            continue
        # минусы: шаг -- step_percent процентов предела жизни
        steps = (age - threshold) * 100 // (limit * cfg.world.aging.step_percent)
        if steps > current_steps(kind, creature):
            set_steps(kind, creature, steps)
            add_entry(
                bundle, "event", f"Старость: {creature.name}, возраст {age}, минусы: {steps}",
                [creature.id], at,
            )
    return events
