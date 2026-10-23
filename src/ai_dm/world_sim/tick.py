from ai_dm.core.clock import DAY, GameClock
from ai_dm.state.memory import add_entry
from ai_dm.world_sim import aging, events, hazard, hygiene, mortality


def at_day(world, day) -> GameClock:
    return GameClock(now_s=day * DAY, calendar=world.clock.calendar)


def tick_days(bundle, rng, cfg, registry) -> list:
    # шаг мира -- игровой день (ТЗ 4.1): от sim.last_day + 1 до текущего дня включительно;
    # на день: смертность, hazard событий (герою), истечение событий, смена сезона (природное
    # событие), смена года (старость)
    world = bundle.world
    sim = world.sim
    if sim.last_season == "" and sim.last_year == 0:
        # первый тик: m0003 ставит только last_day, сезон и год берутся на этот день
        start = at_day(world, sim.last_day)
        sim.last_season = start.season()
        sim.last_year = sim.last_day // world.clock.calendar.days_in_year
    today = world.clock.now_s // DAY
    count = today - sim.last_day
    if count <= 0:
        return []
    result = []
    first = sim.last_day + 1
    if count > cfg.world.max_tick_days:
        # потолок: прокручиваются только последние max_tick_days дней, остальные -- без подробностей
        first = today - cfg.world.max_tick_days + 1
        add_entry(
            bundle, "event", f"Мир прожит без подробностей: {first - sim.last_day - 1} дн."
        )
    for day in range(first, today + 1):
        at = day * DAY
        result += mortality.roll_day(bundle, rng, at)
        result += hazard.roll_hazards(bundle, rng, cfg, registry, at)
        result += hygiene.roll_day(bundle, cfg, at)
        result += events.close_events(bundle, at)
        season = at_day(world, day).season()
        if season != sim.last_season:
            sim.last_season = season
            result += events.natural_event(bundle, rng, season, at)
        year = day // world.clock.calendar.days_in_year
        if year != sim.last_year:
            sim.last_year = year
            result += aging.roll_year(bundle, rng, cfg, registry, at)
    sim.last_day = today
    return result
