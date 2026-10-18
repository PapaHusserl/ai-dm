from ai_dm.rules.creatures import is_hero
from ai_dm.state.creature import DeathSaves
from ai_dm.state.triggers import Favor, Flag, Trigger

DAY = 86400
FAVOR_MIN = -10
FAVOR_MAX = 10


def tier(favor) -> int:
    # -3..3: пороги ±3, ±6, ±9 (ТЗ 4.2)
    if favor < 0:
        return -(-favor // 3)
    return favor // 3


def approx_label(favor) -> str:
    # игроку благосклонность видна приблизительно
    if favor >= 3:
        return "благосклонна"
    if favor <= -3:
        return "гневается"
    return "равнодушна"


def best_favor(creature) -> tuple[str, int] | None:
    # самый благосклонный бог: (id, благосклонность); при равенстве -- меньший id
    best = None
    for god_id in sorted(creature.favor):
        if best is None or creature.favor[god_id] > best[1]:
            best = (god_id, creature.favor[god_id])
    return best


def hero_favors(hero) -> list[int]:
    return list(hero.favor.values())


# изменение благосклонности

def favor_limit_left(spent, key, per_scene) -> int:
    return max(0, per_scene - spent.get(key, 0))


def change_favor(owner, god_id, delta, spent, key, cfg) -> int:
    # применяет сдвиг с лимитами шага и сцены; возвращает фактический сдвиг
    left = favor_limit_left(spent, key, cfg.favor.per_scene)
    amount = min(abs(delta), cfg.favor.step, left)
    wanted = amount if delta > 0 else -amount
    before = owner.favor.get(god_id, 0)
    after = max(FAVOR_MIN, min(FAVOR_MAX, before + wanted))
    owner.favor[god_id] = after
    applied = after - before
    spent[key] = spent.get(key, 0) + abs(applied)
    return applied


def next_debt_number(world, hero) -> int:
    prefix = f"debt:{hero.id}:"
    count = 0
    for god in world.pantheon.values():
        count += len([t for t in god.opportunity if t.id.startswith(prefix)])
    return count + 1


def add_servant_trigger(world, hero, god_id, cfg) -> bool:
    # -9: у бога появляется триггер «послать слугу» (дальше работает world)
    god = world.pantheon.get(god_id)
    if god is None:
        return False
    trigger_id = f"servant:{hero.id}:{god_id}"
    if any(t.id == trigger_id for t in god.opportunity):
        return False
    god.opportunity.append(
        Trigger(
            id=trigger_id, if_=Favor(god=god_id, lte=-9), then="послать слугу",
            cooldown=cfg.favor.servant_cooldown,
        )
    )
    return True


# божественное вмешательство (+9)

def season_bonus(god, season) -> int:
    # поправка силы бога в текущем сезоне (God.season_power), 0 если не задана
    if god is None:
        return 0
    return god.season_power.get(season, 0)


def intervention_percent(favor, cfg, god=None, season="") -> int:
    percent = cfg.favor.intervention_percent_10 if favor >= 10 else cfg.favor.intervention_percent_9
    return max(0, min(100, percent + season_bonus(god, season)))


def try_intervention(hero, world, rng, cfg, chapter_id="", scene_id="") -> str | None:
    # неминуемая смерть героя: возвращает id вмешавшегося бога или None (герой умирает);
    # раз за главу: в intervention_chapter -- id главы, где бог уже вмешался
    if hero.divine.intervention_chapter == chapter_id:
        return None
    candidates = []
    for god_id in sorted(hero.favor):
        favor = hero.favor[god_id]
        if favor >= 9 and god_id in world.pantheon and god_id not in hero.divine.frozen:
            candidates.append((god_id, favor))
    if not candidates:
        return None
    god_id, favor = max(candidates, key=lambda item: item[1])
    season = world.clock.season()
    if rng.d(100) > intervention_percent(favor, cfg, world.pantheon[god_id], season):
        return None
    creature = hero.creature
    if creature.hp_current == 0:
        creature.hp_current = 1
        creature.death_saves = DeathSaves()
        creature.conditions = [c for c in creature.conditions if c.source != "0_hp"]
    hero.divine.intervention_chapter = chapter_id
    hero.divine.intervention_god = god_id
    god = world.pantheon[god_id]
    number = next_debt_number(world, hero)
    debt_id = f"debt:{hero.id}:{number}"
    god.opportunity.append(
        Trigger(
            id=debt_id, if_=Flag(name=f"debt_paid:{hero.id}:{number}", value=False),
            then=cfg.favor.debt_then.format(god=god.name, hero=hero.name), once=True,
        )
    )
    hero.divine.debts.append(debt_id)
    hero.divine.debt_scene[debt_id] = scene_id
    if god_id not in hero.divine.frozen:
        hero.divine.frozen.append(god_id)
    return god_id


def debt_in_scene(heroes, debt_key, scene_id) -> bool:
    # долг выставлен в этой же сцене: исполнить его ещё нельзя
    debt_id = f"debt:{debt_key}"
    for hero in heroes:
        if debt_id in hero.divine.debts and hero.divine.debt_scene.get(debt_id) == scene_id:
            return True
    return False


def pay_debt(world, heroes, debt_key) -> bool:
    # флаг debt_paid:<hero>:<n>: долг выплачен, благосклонность бога размораживается
    debt_id = f"debt:{debt_key}"
    paid = False
    for hero in heroes:
        if debt_id not in hero.divine.debts:
            continue
        hero.divine.debts.remove(debt_id)
        hero.divine.debt_scene.pop(debt_id, None)
        paid = True
        for god_id, god in world.pantheon.items():
            for trigger in god.opportunity:
                if trigger.id == debt_id:
                    trigger.state = "disabled"
            still = [
                d for d in hero.divine.debts
                if any(t.id == d for t in god.opportunity)
            ]
            if god_id in hero.divine.frozen and not still:
                hero.divine.frozen.remove(god_id)
    return paid


# молитва (+6) и помеха (-6)

def day_of(now_s) -> int:
    return now_s // DAY


def can_pray(hero, god_id, now_s) -> bool:
    # молитва раз в день: ни взведённая, ни уже потраченная сегодня
    day = day_of(now_s)
    if hero.favor.get(god_id, 0) < 6 or god_id in hero.divine.frozen:
        return False
    return hero.divine.prayer_day != day and hero.divine.prayer_used_day != day


def pray(hero, god_id, now_s) -> None:
    hero.divine.prayer_day = day_of(now_s)
    hero.divine.prayer_god = god_id


def prayer_armed(hero, now_s) -> bool:
    return hero.divine.prayer_day == day_of(now_s)


def hero_critical_modifier(request) -> tuple[bool, bool]:
    # (преимущество, помеха) от благосклонности для критического броска героя; тратит дневной запас
    actor = request.actor
    if request.now_s is None or not is_hero(actor):
        return False, False
    tags = request.tags
    if not tags.get("critical_moment") and tags.get("stakes") != "critical":
        return False, False
    day = day_of(request.now_s)
    favors = hero_favors(actor)
    advantage = False
    disadvantage = False
    god = actor.divine.prayer_god
    god_ok = god is not None and actor.favor.get(god, 0) >= 6 and god not in actor.divine.frozen
    if prayer_armed(actor, request.now_s) and god_ok:
        actor.divine.prayer_day = None
        actor.divine.prayer_used_day = day
        advantage = True
    if actor.divine.curse_day_used != day and any(f <= -6 for f in favors):
        actor.divine.curse_day_used = day
        disadvantage = True
    return advantage, disadvantage


# жрец

def own_favor(hero) -> int | None:
    # благосклонность своего бога; None -- не жрец или бога нет
    if not is_hero(hero) or hero.sheet.class_id != "cleric" or hero.deity_id is None:
        return None
    return hero.favor.get(hero.deity_id, 0)


def channel_divinity_blocked(hero) -> bool:
    favor = own_favor(hero)
    return favor is not None and favor <= -6


def locked_slot_pool(hero) -> str | None:
    # ≤ -6: ячейки высшего доступного круга не восстанавливаются длинным отдыхом
    if not channel_divinity_blocked(hero):
        return None
    circles = []
    for name, pool in hero.creature.resources.items():
        if name.startswith("spell_slot:") and pool.max > 0:
            circles.append(int(name.split(":")[1]))
    if not circles:
        return None
    return f"spell_slot:{max(circles)}"


def change_deity(hero, god_id) -> int:
    # смена бога: +1 только богу, с которым у героя ещё не было счёта (нет ключа в favor);
    # прежний бог запоминается ключом, возврат к нему без прибавки. Возвращает фактический сдвиг
    if hero.deity_id is not None:
        hero.favor.setdefault(hero.deity_id, 0)
    before = hero.favor.get(god_id)
    hero.deity_id = god_id
    if before is not None:
        return 0
    hero.favor[god_id] = 1
    return 1
