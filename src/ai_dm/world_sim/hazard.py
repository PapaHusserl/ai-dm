from ai_dm.core.events import DomainEvent
from ai_dm.rules.auto_flags import apply_events
from ai_dm.rules.checks import saving_throw
from ai_dm.rules.divine import try_intervention
from ai_dm.rules.exhaustion import add_exhaustion
from ai_dm.rules.roll_pipeline import luck
from ai_dm.rules.triggers_eval import event_active
from ai_dm.state.memory import add_entry
from ai_dm.world_sim.mortality import affected, location_chain


def intervener(bundle, rng, cfg):
    # божественное вмешательство (ТЗ 4.2) на шестом уровне истощения
    chapter = bundle.session.current_chapter
    chapter_id = "" if chapter is None else chapter.id
    return lambda target: try_intervention(target, bundle.world, rng, cfg, chapter_id)


def zone_events(world, hero, at) -> list:
    # активные события с hazard, в зоне которых стоит герой
    chain = location_chain(world, hero.location_id)
    return [
        e for e in world.events
        if e.hazard is not None and event_active(e, at) and affected(e, chain, [])
    ]


def failed_save(hero, event, registry, rng, at) -> bool:
    spec = event.hazard
    # без вдохновения: строка броска не печатается, трата была бы немой
    result = saving_throw(
        hero, registry, rng, spec.save, spec.dc_category, now_s=at, rerollers=[luck]
    )
    return result.outcome == "fail"


def hit(bundle, hero, event, at, intervene) -> list:
    # провал спасброска от hazard = +1 истощение (В2); шестой уровень убивает, если бог не спас
    level = add_exhaustion(hero, 1, now_s=at, cause="hazard", intervene=intervene)
    text = f"{hero.name}: {event.type}, истощение {level}"
    add_entry(bundle, "event", text, [event.id, hero.id], at)
    if hero.status != "dead":
        return []
    done = [DomainEvent(type="hero_died", data={"id": hero.id, "cause": "hazard", "by": None})]
    apply_events(bundle.world, done)
    add_entry(bundle, "death", f"Смерть: {hero.name} (опасность)", [hero.id], at)
    return done


def roll_hazards(bundle, rng, cfg, registry, at) -> list:
    # раз в день: активный герой в зоне события с hazard бросает спасбросок (П9б)
    intervene = intervener(bundle, rng, cfg)
    result = []
    for hero in sorted(bundle.heroes, key=lambda h: h.id):
        for event in zone_events(bundle.world, hero, at):
            if hero.status == "active" and failed_save(hero, event, registry, rng, at):
                result += hit(bundle, hero, event, at, intervene)
    return result
