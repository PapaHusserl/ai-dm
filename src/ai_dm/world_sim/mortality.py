from ai_dm.rules.auto_flags import apply_events
from ai_dm.rules.divine import best_favor
from ai_dm.rules.mortality_guard import remove_creature, remove_hero
from ai_dm.rules.triggers_eval import event_active
from ai_dm.state.memory import add_entry

CAUSE_TEXTS = {"chance": "случайность", "old_age": "старость"}


def tracked(bundle) -> list[tuple]:
    # (вид, существо): именованные живые NPC по id, затем активные герои по id
    result = []
    for npc in sorted(bundle.world.npcs.values(), key=lambda n: n.id):
        if npc.named and npc.status == "alive":
            result.append(("npc", npc))
    for hero in sorted(bundle.heroes, key=lambda h: h.id):
        if hero.status == "active":
            result.append(("hero", hero))
    return result


def remove(bundle, kind, creature, cause, at) -> list:
    # смерть с причиной в момент at: статус, флаг, запись в хронику
    world = bundle.world
    if kind == "npc":
        done = remove_creature(world, creature.id, "dead", cause)
    else:
        done = remove_hero(creature, "dead", cause, world.clock.now_s)
    if not isinstance(done, list):
        return []
    creature.death.at_s = at
    apply_events(world, done)
    add_entry(
        bundle, "death", f"Смерть: {creature.name} ({CAUSE_TEXTS[cause]})", [creature.id], at
    )
    return done


def location_chain(world, location_id) -> list[str]:
    # локация и её родители по parent_id
    chain = []
    while location_id is not None and location_id not in chain:
        chain.append(location_id)
        location = world.locations.get(location_id)
        location_id = None if location is None else location.parent_id
    return chain


def affected(event, chain, groups) -> bool:
    # существо (цепочка его локаций и группы) в регионе и группе риска события
    in_region = not event.regions or any(region in chain for region in event.regions)
    in_group = (
        not event.affects or "все" in event.affects
        or any(group in event.affects for group in groups)
    )
    return in_region and in_group


def multiplier(world, kind, creature, at) -> int:
    # максимум mortality_multiplier активных событий, в регионе и группе риска которых существо
    chain = location_chain(world, creature.location_id)
    groups = creature.groups if kind == "npc" else []
    result = 1
    for event in world.events:
        if event_active(event, at) and affected(event, chain, groups):
            result = max(result, event.mortality_multiplier)
    return result


def roll_day(bundle, rng, at) -> list:
    # смертность за игровой день (ТЗ 4.1 п.3): 1/N на существо, N делится на множитель событий
    world = bundle.world
    events = []
    for kind, creature in tracked(bundle):
        per_day = max(1, world.mortality_per_day // multiplier(world, kind, creature, at))
        if rng.randbelow(per_day) != 0:
            continue
        # отвести беду (4.2): d10 <= благосклонность лучшего бога
        best = best_favor(creature)
        if best is not None and best[1] > 0 and rng.d(10) <= best[1]:
            add_entry(
                bundle, "favor", f"{best[0]} отвёл беду от {creature.name}",
                [creature.id, best[0]], at,
            )
            continue
        events += remove(bundle, kind, creature, "chance", at)
    return events
