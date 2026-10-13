from ai_dm.combat import disarm, downed, trophies
from ai_dm.core.events import DomainEvent
from ai_dm.rules.auto_flags import apply_events
from ai_dm.rules.creatures import end_concentration
from ai_dm.rules.death_saves import is_dying, is_stable
from ai_dm.rules.inventory import add_item
from ai_dm.rules.spellcasting import expire_concentration, spell_kind
from ai_dm.rules.time_ops import rounds_to_seconds

# подписи исходов боя в логе
OUTCOME_WORDS = {
    "victory": "победа", "fled": "бегство", "hero_dead": "герой погиб",
    "hero_dying": "герой умирает", "defeat_pending": "поражение",
    "ended_by_master": "завершён мастером",
}


def update_outcome(engine) -> None:
    # по состоянию участников ставит state.outcome (None -- бой идёт)
    set_outcome(engine)
    # смерть героя бой не обрывает; но если бой окончен -- итог hero_dead важнее любого другого
    parts = engine.state.participants
    hero_dead = any(p.status == "dead" and p.ref in engine.heroes for p in parts)
    if hero_dead and engine.state.outcome is not None:
        engine.state.outcome = "hero_dead"


def set_outcome(engine) -> None:
    state = engine.state
    heroes = [p for p in state.participants if p.side == "heroes"]
    enemies = [p for p in state.participants if p.side == "enemies"]
    # все герои сбежали: для героя бой закончен, судьба оставшихся союзников -- нарратив мастера
    hero_parts = [p for p in heroes if p.ref in engine.heroes]
    if hero_parts and all(p.status == "fled" for p in hero_parts):
        state.outcome = "fled"
        return
    heroes_fit = any(engine.is_capable(p.ref) for p in heroes)
    enemies_fit = any(engine.is_capable(p.ref) for p in enemies)
    # упавшие, но живые герои
    lying = [p for p in heroes if p.status == "down" and alive(engine, p.ref)]
    if not enemies_fit:
        if heroes_fit or any(stable(engine, p.ref) for p in lying):
            downed.stabilize_all(engine)
            state.outcome = "victory"
        elif lying:
            state.outcome = "hero_dying"
        else:
            state.outcome = "fled"
    elif not heroes_fit:
        if lying:
            group = state.groups.get(state.defeat_group_id)
            if group is None or group.intent == "kill":
                state.outcome = "hero_dying"
            else:
                state.outcome = "defeat_pending"
        else:
            state.outcome = "fled"
    else:
        # герой встал (nat 20 или лечение): бой продолжается
        state.outcome = None


def alive(engine, ref) -> bool:
    hero = engine.heroes.get(ref)
    if hero is None:
        return engine.part(ref).status != "dead"
    return hero.status == "active"


def stable(engine, ref) -> bool:
    hero = engine.heroes.get(ref)
    if hero is None:
        return True
    return is_stable(hero.creature) and not is_dying(hero.creature)


def check_end(engine) -> list[DomainEvent]:
    # после каждого действия и хода; при завершении -- события и время
    if engine.is_over:
        return []
    update_outcome(engine)
    if not engine.is_over:
        return []
    return conclude(engine)


def settle_ground(engine) -> None:
    # выбитое оружие: после победы достаётся героям (своё -- владельцу), иначе остаётся на поле;
    # метки disarmed на существах бой не переживают
    state = engine.state
    alive_heroes = [ref for ref, hero in engine.heroes.items() if hero.status == "active"]
    won = state.outcome in ("victory", "ended_by_master") and alive_heroes
    for item in state.ground_items:
        name = engine.registry.get("weapon", item.item_id).name.lower()
        if won:
            owner = alive_heroes[0]
            if item.owner_ref in alive_heroes:
                owner = item.owner_ref
            add_item(
                engine.heroes[owner], item.item_id, item.qty,
                cost_cp=item.cost_cp, quality=item.quality,
            )
            engine.log(f"{name}: достаётся {engine.name(owner)}")
        elif item.owner_ref in engine.heroes:
            engine.log(f"{name} ({engine.name(item.owner_ref)}) остался на поле боя")
    state.ground_items = []
    if won:
        state.gear = trophies.enemy_gear(engine, disarm.weapon_ids)
    for p in state.participants:
        if p.ref in engine.heroes:
            continue
        creature = engine.creature(p.ref)
        creature.active_effects = [
            e for e in creature.active_effects if e.id not in ("disarmed", "disarm_used")
        ]


def release_concentration(engine) -> None:
    # после сдвига часов: заряд Опутывающего удара не переживает бой (лозы и опутанные NPC
    # освобождаются); остальные концентрации кончаются по сроку
    for ref, hero in engine.heroes.items():
        held = hero.creature.concentration
        if held is None:
            continue
        spell = engine.registry.get("spell", held.spell_id)
        if spell_kind(spell) == "rider":
            end_concentration(hero.creature)
            engine.drop_concentration_effects(ref)
        elif expire_concentration(hero, engine.world) is not None:
            engine.drop_concentration_effects(ref)
            engine.log(f"{engine.name(ref)}: {spell.name} кончается")


def conclude(engine) -> list[DomainEvent]:
    # раунд, в котором бой закончился, считается целиком
    engine.world.clock.advance(rounds_to_seconds(engine.state.round, engine.cfg))
    release_concentration(engine)
    settle_ground(engine)
    # скрытность не переживает бой
    for hero in engine.heroes.values():
        hero.creature.conditions = [
            c for c in hero.creature.conditions
            if not (c.id == "invisible" and c.source == "hidden")
        ]
    event = DomainEvent(type="combat_ended", data={"id": engine.state.id})
    apply_events(engine.world, [event])
    outcome = OUTCOME_WORDS.get(engine.state.outcome, engine.state.outcome)
    engine.log(f"Бой окончен: {outcome}, раундов: {engine.state.round}")
    return [event]
