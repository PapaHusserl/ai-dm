# событие -> (префикс флага, поле data с id)
FLAG_BY_EVENT = {
    "npc_died": ("npc_dead", "id"),
    "hero_died": ("hero_dead", "id"),
    "location_visited": ("visited", "id"),
    "combat_ended": ("combat_ended", "id"),
    "item_gained": ("item_gained", "item"),
}

# префиксы флагов, которые ставит только движок (set_flag их отклоняет): автофлаги событий,
# danger: (warn_danger), hoard: (клад логова взят), haggle: (торг с NPC без лавки, услуги),
# lodging: (ночлег героя оплачен, день)
RESERVED_FLAG_PREFIXES = [prefix for prefix, _ in FLAG_BY_EVENT.values()] + [
    "danger", "hoard", "haggle", "lodging"
]


def apply_events(world, events) -> None:
    for event in events:
        if event.type in FLAG_BY_EVENT:
            prefix, field = FLAG_BY_EVENT[event.type]
            world.flags[f"{prefix}:{event.data[field]}"] = True
