from ai_dm.combat.actions.attack import (
    SIZES,
    attacks_of,
    lost_weapons,
    roll_attack,
    spend_attack,
    target_size,
)
from ai_dm.combat.trophies import weapon_price
from ai_dm.content.models.common import SKILLS
from ai_dm.core.events import DomainEvent
from ai_dm.rules.derived import ability_modifier, skill_bonus, skill_parts
from ai_dm.rules.inventory import add_item, dearest_cost, equip, remove_item
from ai_dm.rules.names import ABILITY_SHORT
from ai_dm.rules.roll_pipeline import RollRequest, roll
from ai_dm.state.combat import GroundItem
from ai_dm.state.creature import ActiveEffect


def may_disarm(engine, ref) -> bool:
    # героям можно всегда; монстру -- с тегом disarmer и один раз за бой (иначе только и выбивает)
    if engine.is_hero(ref):
        return True
    tried = any(e.id == "disarm_used" for e in engine.creature(ref).active_effects)
    return "disarmer" in engine.tags(ref) and not tried


def weapon_ids(engine, ref) -> list[str]:
    # оружие существа, которое можно выбить: у героя -- из руки, у монстра -- по действиям
    if engine.is_hero(ref):
        main_hand = engine.heroes[ref].equipped.main_hand
        if main_hand is None:
            return []
        return [main_hand]
    all_lost, lost = lost_weapons(engine, ref)
    result = []
    for action in engine.monster(ref).actions:
        if action.weapon_id is None or all_lost or action.weapon_id in lost:
            continue
        if action.weapon_id not in result:
            result.append(action.weapon_id)
    return result


def strike_info(engine, ref):
    # атака, которой выбивают: первая ближняя (оружие в руке первым); None -- бить нечем
    for info in attacks_of(engine, ref):
        if info.kind == "melee" and info.id != "improvised":
            return info
    return None


def weapon_name(engine, weapon_id) -> str:
    return engine.registry.get("weapon", weapon_id).name.lower()


def holds_two_hands(engine, target, weapon_id) -> bool:
    # цель держит оружие двумя руками: двуручное, а герой -- ещё и универсальное при пустой руке
    properties = engine.registry.get("weapon", weapon_id).properties
    if "two_handed" in properties:
        return True
    if not engine.is_hero(target) or "versatile" not in properties:
        return False
    equipped = engine.heroes[target].equipped
    return equipped.shield is None and equipped.off_hand is None


def target_mode(engine, ref, target, weapon_id) -> tuple[str, str]:
    # режим проверки цели и подпись: хват двумя руками и размер больше -- преимущество,
    # размер меньше -- помеха
    sizes = [SIZES.index(target_size(engine, r)) for r in (target, ref)]
    advantage = []
    if holds_two_hands(engine, target, weapon_id):
        advantage.append("двуручный хват")
    if sizes[0] > sizes[1]:
        advantage.append("крупнее")
    if advantage and sizes[0] >= sizes[1]:
        return "advantage", ", ".join(advantage)
    if sizes[0] < sizes[1] and not advantage:
        return "disadvantage", "мельче"
    return "normal", ""


def target_check(engine, target, mode, label):
    # проверка цели: герой -- лучшее из Атлетики и Акробатики, монстр -- лучший мод. Сил/Лов
    skill = None
    if engine.is_hero(target):
        hero = engine.heroes[target]
        skill = max(
            ("athletics", "acrobatics"), key=lambda s: skill_bonus(hero, engine.registry, s)
        )
        ability = SKILLS[skill]
        parts = skill_parts(hero, engine.registry, skill)
    else:
        abilities = engine.monster(target).abilities
        ability = max(("str", "dex"), key=lambda a: abilities[a])
        parts = [(ABILITY_SHORT[ability], ability_modifier(abilities[ability]))]
    request = RollRequest(
        kind="check", actor=engine.actor(target), actor_id=target, ability=ability, skill=skill,
        bonus=sum(value for _, value in parts), bonus_parts=parts, base_adv=mode,
        base_adv_label=label,
    )
    result = roll(request, engine.rng, engine.registry, modifiers=engine.modifiers)
    engine.log(f"  {engine.name(target)}: удерживает оружие: {result.log.text}")
    return result


def strip_weapon(engine, source, target, weapon_id) -> tuple[int, str | None]:
    # оружие больше не у цели: у героя уходит из инвентаря (самый дорогой стек), у монстра гаснет
    # оружейное действие. Возвращает (цена, качество) оружия -- с ними оно ляжет на землю
    if engine.is_hero(target):
        hero = engine.heroes[target]
        removed = remove_item(hero, weapon_id, cost_cp=dearest_cost(hero, weapon_id))[0]
        if hero.equipped.main_hand == weapon_id:
            hero.equipped.main_hand = None
        return removed.cost_cp, removed.quality
    engine.creature(target).active_effects.append(
        ActiveEffect(id="disarmed", source=source, kind="flag", params={"weapon_id": weapon_id})
    )
    return weapon_price(engine, target, weapon_id)


def can_hold(engine, hero, weapon_id) -> bool:
    # рука свободна и двуручное оружие не мешает щиту или оружию в левой руке
    if hero.equipped.main_hand is not None:
        return False
    properties = engine.registry.get("weapon", weapon_id).properties
    busy = hero.equipped.shield is not None or hero.equipped.off_hand is not None
    return not ("two_handed" in properties and busy)


def take(engine, ref, weapon_id, cost_cp, quality) -> None:
    # оружие у героя: в инвентарь (со своей ценой), и в руку, если она свободна
    hero = engine.heroes[ref]
    add_item(hero, weapon_id, cost_cp=cost_cp, quality=quality)
    if can_hold(engine, hero, weapon_id):
        equip(hero, weapon_id, engine.registry)


def disarm_target(engine, ref, target, weapon_id, grab) -> None:
    # общий исход: оружие падает в зоне цели; grab (рука героя свободна) -- сразу в руки
    cost_cp, quality = strip_weapon(engine, ref, target, weapon_id)
    name = weapon_name(engine, weapon_id)
    if grab:
        take(engine, ref, weapon_id, cost_cp, quality)
        engine.log(f"  {engine.name(ref)} выбивает {name} у {engine.name(target)} и подхватывает")
        return
    zone_id = engine.part(target).zone_id
    engine.state.ground_items.append(
        GroundItem(
            item_id=weapon_id, zone_id=zone_id, owner_ref=target, cost_cp=cost_cp, quality=quality
        )
    )
    engine.log(f"  {engine.name(ref)} выбивает {name} у {engine.name(target)}")


def surrender_drop(engine, target) -> None:
    # сдавшийся роняет всё оружие на землю
    weapons = weapon_ids(engine, target)
    for weapon_id in weapons:
        cost_cp, quality = strip_weapon(engine, target, target, weapon_id)
        zone_id = engine.part(target).zone_id
        engine.state.ground_items.append(
            GroundItem(
                item_id=weapon_id, zone_id=zone_id, owner_ref=target, cost_cp=cost_cp,
                quality=quality,
            )
        )
    if weapons:
        names = ", ".join(weapon_name(engine, w) for w in weapons)
        engine.log(f"  {engine.name(target)} бросает оружие: {names}")


def perform(engine, ref, option) -> list[DomainEvent]:
    # бросок атаки текущим ближним оружием против проверки цели (DMG); тратит одну атаку
    target = option.params["target"]
    weapon_id = option.params["weapon_id"]
    spend_attack(engine, ref)
    if not engine.is_hero(ref):
        engine.creature(ref).active_effects.append(
            ActiveEffect(id="disarm_used", source=ref, kind="flag")
        )
    info = strike_info(engine, ref)
    # достать оружие -- часть действия Атака
    holds_other = engine.is_hero(ref) and engine.heroes[ref].equipped.main_hand != info.id
    if holds_other and info.weapon_id is not None:
        equip(engine.heroes[ref], info.id, engine.registry)
    engine.log(
        f"{engine.name(ref)}: обезоруживание ({weapon_name(engine, weapon_id)}) "
        f"→ {engine.name(target)}"
    )
    mode, label = target_mode(engine, ref, target, weapon_id)
    check = target_check(engine, target, mode, label)
    # ничья -- оружие остаётся у цели: попадание от итога проверки + 1
    result = roll_attack(
        engine, ref, target, info.bonus, "normal", info.name, info.bonus_parts, check.total + 1,
        "проверка цели",
    )
    if result.outcome in ("hit", "crit"):
        disarm_target(engine, ref, target, weapon_id, info.id == "unarmed" and engine.is_hero(ref))
    return []


def can_pick(engine, ref, item) -> bool:
    # герой берёт любое оружие; монстр -- только то, чьё действие у него отобрано
    if engine.is_hero(ref):
        return True
    return item.item_id in lost_weapons(engine, ref)[1]


def pickup(engine, ref, option) -> list[DomainEvent]:
    # свободное взаимодействие, если не потрачено, иначе действие
    turn = engine.part(ref).turn
    if turn.free_interaction:
        turn.free_interaction = False
    else:
        turn.action = False
    item = engine.state.ground_items.pop(option.params["index"])
    if engine.is_hero(ref):
        take(engine, ref, item.item_id, item.cost_cp, item.quality)
    else:
        flags = engine.creature(ref).active_effects
        lost = [e for e in flags if e.params.get("weapon_id") == item.item_id]
        flags.remove(lost[0])
    engine.log(f"{engine.name(ref)} подбирает {weapon_name(engine, item.item_id)}")
    return []
