from ai_dm.rules.hygiene import SMELLY, is_stale, mark_washed, washed_at
from ai_dm.state.creature import AppliedCondition
from ai_dm.state.memory import add_entry


def roll_day(bundle, cfg, at) -> list:
    # раз в день: активному герою без мытья неделю -- состояние «вонь»; нет флага -- отсчёт
    # с этого дня (старые миры без ретро-вони); hygiene_days = 0 -- гигиена выключена
    if cfg.services.hygiene_days == 0:
        return []
    world = bundle.world
    for hero in sorted(bundle.heroes, key=lambda h: h.id):
        if hero.status != "active":
            continue
        if washed_at(world, hero.id) is None:
            mark_washed(world, hero, at)
            continue
        conditions = hero.creature.conditions
        if is_stale(world, hero, cfg, at) and not any(c.id == SMELLY for c in conditions):
            conditions.append(AppliedCondition(id=SMELLY, source="hygiene"))
            add_entry(bundle, "event", f"От {hero.name} несёт: давно без мытья", [hero.id], at)
    return []
