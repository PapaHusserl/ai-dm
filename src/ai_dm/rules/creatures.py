from ai_dm.state.creature import AppliedCondition, CreatureState, DeathSaves

# к20-тесты: единственное объявление
D20_KINDS = ("attack", "save", "check", "initiative", "death_save")


def is_hero(target) -> bool:
    return hasattr(target, "sheet")


def creature_of(target):
    # у героя состояние лежит в .creature, у существа цель и есть состояние
    if hasattr(target, "creature"):
        return target.creature
    return target


def end_concentration(creature) -> None:
    # снимает эффекты концентрации и саму концентрацию
    creature.concentration = None
    creature.active_effects = [
        e for e in creature.active_effects
        if e.expires is None or e.expires.kind != "concentration"
    ]


def live_effects(creature, now_s=None) -> list:
    # эффекты, не истёкшие по часам мира (seconds: value -- момент окончания); now_s None -- все
    return [
        e for e in creature.active_effects
        if now_s is None or e.expires is None or e.expires.kind != "seconds"
        or e.expires.value > now_s
    ]


def _alive(item, now_s) -> bool:
    return item.expires is None or item.expires.kind != "seconds" or item.expires.value > now_s


def ensure_creature(npc, registry) -> None:
    # NPC без состояния получает его: HP из монстра combat.monster_id, нет — 1/1
    if npc.creature is not None:
        return
    monster_id = (npc.combat or {}).get("monster_id")
    hit_points = registry.get("monster", monster_id).hp if monster_id else 1
    npc.creature = CreatureState(hp_current=hit_points, hp_max=hit_points)


def pending_creature(bundle, target):
    # состояние цели отложенного события; None -- цель мёртвая, неизвестная или NPC без creature
    for hero in bundle.heroes:
        if hero.id == target:
            return None if hero.status == "dead" else hero.creature
    npc = bundle.world.npcs.get(target)
    return None if npc is None or npc.status == "dead" else npc.creature


def fire_pending(bundle, now_s) -> list[str]:
    # сработавшие отложенные события мира: состояние на цель и строка ленты; запись снимается
    # всегда (второй раз то же состояние не вешается и строки не даёт)
    world = bundle.world
    due = [event for event in world.pending if event.at_s <= now_s]
    world.pending = [event for event in world.pending if event.at_s > now_s]
    lines = []
    for event in due:
        creature = pending_creature(bundle, event.target)
        if creature is None or any(c.id == event.ref for c in creature.conditions):
            continue
        creature.conditions.append(AppliedCondition(id=event.ref, source="pending"))
        npc = world.npcs.get(event.target)
        # строка — если цель герой или NPC в локации героя; иначе состояние молча
        if npc is None or npc.location_id == bundle.heroes[0].location_id:
            lines.append(event.text)
    return lines


def wake_stable(bundle, now_s) -> list[str]:
    # стабильный герой на 0 HP приходит в себя в срок wake_at_s: HP 1, без сознания снято
    lines = []
    for hero in bundle.heroes:
        creature = hero.creature
        if hero.status == "dead" or creature.wake_at_s is None or creature.wake_at_s > now_s:
            continue
        creature.wake_at_s = None
        if creature.hp_current == 0 and creature.death_saves.stable:
            creature.hp_current = 1
            creature.death_saves = DeathSaves()
            creature.conditions = [
                c for c in creature.conditions if not (c.id == "unconscious" and c.source == "0_hp")
            ]
            lines.append(f"{hero.name} приходит в себя: HP 1")
    return lines


def purge_expired(bundle) -> list[str]:
    # после сдвига часов: убирает истёкшие seconds из эффектов и состояний героев и NPC мира
    # (max_hp снимает expire_max_hp), вне боя -- и истёкших призванных (индекс в бою -- часть ref);
    # возвращает строки ленты: начатые отложенные состояния и пробуждения
    now_s = bundle.world.clock.now_s
    creatures = [h.creature for h in bundle.heroes]
    creatures += [n.creature for n in bundle.world.npcs.values() if n.creature is not None]
    for creature in creatures:
        creature.active_effects = [
            e for e in creature.active_effects
            if e.kind == "max_hp" or _alive(e, now_s)
        ]
        creature.conditions = [c for c in creature.conditions if _alive(c, now_s)]
    if bundle.session.active_combat is None:
        for hero in bundle.heroes:
            hero.minions = [m for m in hero.minions if m.until_s is None or m.until_s > now_s]
    return fire_pending(bundle, now_s) + wake_stable(bundle, now_s)
