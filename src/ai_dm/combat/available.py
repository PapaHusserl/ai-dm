from pydantic import BaseModel, Field

from ai_dm.combat import disarm
from ai_dm.combat.actions import cast, parley
from ai_dm.combat.actions.attack import action_id, attack_targets, attacks_of, base_advantage
from ai_dm.combat.stealth import HIDE_DC, can_hide
from ai_dm.rules.death_saves import is_dying
from ai_dm.rules.derived import clock_text, free_cast_pool
from ai_dm.rules.inventory import active_item_until, find_item, item_totals
from ai_dm.rules.modifiers.conditions import with_implied
from ai_dm.rules.names import SKILL_NAMES


class ActionOption(BaseModel):
    id: str
    kind: str
    label: str
    params: dict = Field(default_factory=dict)
    # чем платит: action | bonus | move | free | reaction
    cost: str = "action"


COST_ORDER = ["action", "bonus", "move", "reaction", "free"]


def target_text(engine, target) -> str:
    # цель заклинания: участник, зона (область) или несколько союзников через запятую
    names = []
    for one in target.split(","):
        zones = [z.name for z in engine.state.zones if z.id == one]
        names.append(zones[0] if zones else engine.name(one))
    return ", ".join(names)


def attack_options(engine, ref) -> list[ActionOption]:
    result = []
    for info in attacks_of(engine, ref):
        for target_ref in attack_targets(engine, ref):
            if base_advantage(engine, ref, target_ref, info) is None:
                continue
            params = {
                "weapon": info.id, "target": target_ref, "mode": info.kind, "nonlethal": False,
            }
            result.append(
                ActionOption(
                    id=f"attack:{info.id}:{target_ref}", kind="attack",
                    label=f"Атака: {info.name or info.id} → {engine.name(target_ref)}",
                    params=params,
                )
            )
            if info.kind == "melee" and engine.is_hero(ref):
                params = {**params, "nonlethal": True}
                result.append(
                    ActionOption(
                        id=f"attack:{info.id}:{target_ref}:nonlethal", kind="attack",
                        label="Оглушающая атака: "
                        f"{info.name or info.id} → {engine.name(target_ref)}",
                        params=params,
                    )
                )
    return result + ammo_options(engine, ref)


def special_ammo(engine, ref, weapon_id) -> list:
    # особые стрелы в инвентаре героя, которыми стреляется это оружие: [(предмет, сколько)]
    result = []
    for item_id, qty in item_totals(engine.heroes[ref]).items():
        found = find_item(engine.registry, item_id)
        if found is None or found[0] != "item" or weapon_id not in found[1].ammo_for:
            continue
        if qty > 0:
            result.append((found[1], qty))
    return result


def ammo_options(engine, ref) -> list[ActionOption]:
    # «Длинный лук -- зажигательная стрела (осталось 10)»: после обычных атак, чтобы
    # тактика авто-героя по умолчанию не тратила особые стрелы
    if not engine.is_hero(ref):
        return []
    result = []
    for info in attacks_of(engine, ref):
        if info.kind != "ranged" or info.weapon_id is None:
            continue
        weapon = engine.registry.get("weapon", info.id)
        for item, qty in special_ammo(engine, ref, info.id):
            for target_ref in attack_targets(engine, ref):
                if base_advantage(engine, ref, target_ref, info) is None:
                    continue
                params = {
                    "weapon": info.id, "target": target_ref, "mode": info.kind,
                    "nonlethal": False, "ammo": item.id,
                }
                label = (
                    f"Атака: {weapon.name.lower()} — {item.name.lower()} (осталось {qty}) "
                    f"→ {engine.name(target_ref)}"
                )
                result.append(
                    ActionOption(
                        id=f"attack:{info.id}:{target_ref}:ammo:{item.id}", kind="attack",
                        label=label, params=params,
                    )
                )
    return result


def multiattack_options(engine, ref) -> list[ActionOption]:
    # Мультиатака монстра: одно действие, предлагается, если хоть у одного шага есть цель
    if engine.is_hero(ref):
        return []
    steps = engine.monster(ref).multiattack
    weapons = [o.params["weapon"] for o in attack_options(engine, ref)]
    if any(action_id(step.action) in weapons for step in steps):
        return [ActionOption(id="multiattack", kind="multiattack", label="Мультиатака")]
    return []


def cast_options(engine, ref) -> list[ActionOption]:
    if not engine.is_hero(ref):
        return []
    result = []
    turn = engine.part(ref).turn
    for spell in cast.castable_spells(engine, ref):
        # бонусное действие -- бонусные заклинания, действие -- остальные
        cost = "action"
        if cast.uses_bonus_action(spell):
            cost = "bonus"
            if not turn.bonus:
                continue
        elif not turn.action:
            continue
        result += spell_entries(engine, ref, spell, cost)
    return result


def spell_entries(engine, ref, spell, cost) -> list[ActionOption]:
    # пункты заклинания: по кругу с ячейкой (базовый первым), бесплатное применение -- базовый круг
    hero = engine.heroes[ref]
    usable = cast.usable_circles(hero, spell)
    circles = usable
    free_pool = None
    if spell.level > 0 and cast.free_cast_left(engine, hero, spell):
        free_pool = hero.creature.resources[free_cast_pool(hero, engine.registry, spell.id)]
        if spell.level not in usable:
            circles = [spell.level] + usable
    result = []
    for circle in circles:
        for target in cast.cast_targets(engine, ref, spell, circle):
            params = {"spell": spell.id, "circle": circle, "target": target}
            # заряд ложится на самого заклинателя: цель в подписи не нужна
            where = f"→ {target_text(engine, target)}"
            if cast.spell_kind(spell) == "rider":
                where = "(заряд)"
            name = spell.name
            if circle > spell.level:
                name = f"{spell.name} ({circle} круг)"
            if circle in usable:
                result.append(
                    ActionOption(
                        id=f"cast:{spell.id}:{circle}:{target}", kind="cast",
                        label=f"{name} {where}", params=params,
                        cost=cost,
                    )
                )
            if circle == spell.level and free_pool is not None:
                label = f"{name} {where} "
                label += f"(без ячейки, {free_pool.current}/{free_pool.max})"
                result.append(
                    ActionOption(
                        id=f"cast:{spell.id}:{circle}:{target}:free", kind="cast",
                        label=label, params={**params, "free": True}, cost=cost,
                    )
                )
    return result


def move_options(engine, ref) -> list[ActionOption]:
    p = engine.part(ref)
    if p.turn.move <= 0:
        return []
    # опутанный стоит на месте: скорость 0
    if any(c.id == "restrained" for c in engine.creature(ref).conditions):
        return []
    own = [z for z in engine.state.zones if z.id == p.zone_id][0]
    return [
        ActionOption(
            id=f"move:{z.id}", kind="move", label=f"Идти: {z.name}", params={"zone": z.id},
            cost="move",
        )
        for z in engine.state.zones if z.id in own.adjacent
    ]


def help_options(engine, ref) -> list[ActionOption]:
    p = engine.part(ref)
    result = []
    for ally in engine.state.participants:
        if ally.ref == ref or ally.side != p.side or not engine.is_capable(ally.ref):
            continue
        for enemy in engine.state.participants:
            if enemy.side == p.side or not engine.is_capable(enemy.ref):
                continue
            if enemy.zone_id != p.zone_id:
                continue
            result.append(
                ActionOption(
                    id=f"help:{ally.ref}:{enemy.ref}", kind="help",
                    label=f"Помочь {engine.name(ally.ref)} против {engine.name(enemy.ref)}",
                    params={"ally": ally.ref, "enemy": enemy.ref},
                )
            )
    return result


def stabilize_options(engine, ref) -> list[ActionOption]:
    if not engine.is_hero(ref):
        return []
    p = engine.part(ref)
    result = []
    for q in engine.state.participants:
        hero = engine.heroes.get(q.ref)
        if hero is None or q.ref == ref or q.side != p.side or q.zone_id != p.zone_id:
            continue
        if q.status == "down" and hero.status == "active" and is_dying(hero.creature):
            result.append(
                ActionOption(
                    id=f"stabilize:{q.ref}", kind="stabilize",
                    label=f"Стабилизировать {engine.name(q.ref)}",
                    params={"target": q.ref},
                )
            )
    return result


def item_options(engine, ref) -> list[ActionOption]:
    if not engine.is_hero(ref):
        return []
    result = []
    for item_id, total_qty in item_totals(engine.heroes[ref]).items():
        found = find_item(engine.registry, item_id)
        if found is None or found[0] != "item":
            continue
        effects = found[1].effects
        if effects and effects[0].type == "heal":
            result.append(
                ActionOption(
                    id=f"use_item:{item_id}", kind="use_item",
                    label=f"Использовать {found[1].name}", params={"item": item_id},
                    cost="bonus",
                )
            )
        if effects and effects[0].type == "ac_bonus":
            # эликсир: «Выпить: Каменная Кожа (осталось 2)»
            name = found[1].short_name or found[1].name
            until = active_item_until(
                engine.heroes[ref], item_id, engine.world.clock.now_s
            )
            if until is None:
                note = f"осталось {total_qty}"
            else:
                note = f"уже действует до {clock_text(until)}"
            result.append(
                ActionOption(
                    id=f"use_item:{item_id}", kind="use_item",
                    label=f"Выпить: {name} ({note})",
                    params={"item": item_id}, cost="bonus",
                )
            )
    return result


def transfer_mark_options(engine, ref) -> list[ActionOption]:
    # метка осталась без цели (цель упала), концентрация держится: перенос без ячейки
    if not engine.is_hero(ref):
        return []
    held = engine.creature(ref).concentration
    if held is None or held.spell_id in engine.concentration_targets(ref):
        return []
    spell = engine.registry.get("spell", held.spell_id)
    if cast.spell_kind(spell) != "mark":
        return []
    result = []
    for target in cast.cast_targets(engine, ref, spell):
        if engine.part(target).status != "active":
            continue
        result.append(
            ActionOption(
                id=f"transfer_mark:{target}", kind="transfer_mark",
                label=f"Перенести {spell.name} → {engine.name(target)}", params={"target": target},
                cost="bonus",
            )
        )
    return result


def escape_options(engine, ref) -> list[ActionOption]:
    # опутанный лозами вырывается действием: проверка Силы против СЛ заклинателя
    result = []
    for effect in engine.creature(ref).active_effects:
        if effect.kind != "ensnared":
            continue
        spell = engine.registry.get("spell", effect.id)
        result.append(
            ActionOption(
                id=f"escape:{spell.id}", kind="escape",
                label=f"Вырваться: {spell.name} (Сила, Атлетика, СЛ {effect.params['dc']})",
                params={"spell": spell.id},
            )
        )
    return result


def parley_options(engine, ref) -> list[ActionOption]:
    # переговоры: по строке на навык и цель, пока они возможны (СЛ и помеха видны в подписи)
    result = []
    for skill, outcome, target, dc, mode in parley.menu_entries(engine, ref):
        note = f"СЛ {dc}"
        if mode == "disadvantage":
            note += ", помеха"
        label = f"Переговоры: {SKILL_NAMES[skill]}, {parley.OUTCOME_WORDS[outcome]} "
        label += f"→ {engine.name(target)} ({note})"
        result.append(
            ActionOption(
                id=f"parley:{target}:{skill}:{outcome}", kind="parley", label=label,
                params={"skill": skill, "outcome": outcome, "target": target},
            )
        )
    return result


def disarm_options(engine, ref) -> list[ActionOption]:
    # выбить оружие у врага в своей зоне: по строке на оружие цели
    if not disarm.may_disarm(engine, ref) or disarm.strike_info(engine, ref) is None:
        return []
    result = []
    for target in attack_targets(engine, ref):
        if not engine.is_capable(target) or engine.part(target).zone_id != engine.part(ref).zone_id:
            continue
        for weapon_id in disarm.weapon_ids(engine, target):
            name = disarm.weapon_name(engine, weapon_id)
            result.append(
                ActionOption(
                    id=f"disarm:{target}:{weapon_id}", kind="disarm",
                    label=f"Обезоружить: {name} → {engine.name(target)}",
                    params={"target": target, "weapon_id": weapon_id},
                )
            )
    return result


def pickup_options(engine, ref) -> list[ActionOption]:
    # подобрать оружие с земли в своей зоне: свободное взаимодействие, иначе действие
    turn = engine.part(ref).turn
    if not turn.free_interaction and not turn.action:
        return []
    cost = "free" if turn.free_interaction else "action"
    result = []
    for index, item in enumerate(engine.state.ground_items):
        if item.zone_id != engine.part(ref).zone_id or not disarm.can_pick(engine, ref, item):
            continue
        result.append(
            ActionOption(
                id=f"pickup:{index}", kind="pickup",
                label=f"Подобрать: {disarm.weapon_name(engine, item.item_id)}",
                params={"index": index}, cost=cost,
            )
        )
    return result


def has_second_wind(engine, ref) -> bool:
    if not engine.is_hero(ref):
        return False
    pool = engine.creature(ref).resources.get("second_wind")
    return pool is not None and pool.current > 0


def has_nimble_escape(engine, ref) -> bool:
    if engine.is_hero(ref):
        return False
    return "nimble_escape" in engine.monster(ref).traits


def list_options(engine, ref) -> list[ActionOption]:
    p = engine.part(ref)
    if p.status != "active":
        return []
    end_turn = ActionOption(id="end_turn", kind="end_turn", label="Закончить ход", cost="free")
    conditions = [c.id for c in with_implied(engine.creature(ref))]
    if "incapacitated" in conditions:
        return [end_turn]
    options = []
    if p.turn.action or p.turn.attacks_left > 0:
        options += attack_options(engine, ref)
        options += disarm_options(engine, ref)
    if p.turn.action:
        options += multiattack_options(engine, ref)
    options += cast_options(engine, ref)
    options += move_options(engine, ref)
    if p.turn.action:
        options.append(ActionOption(id="dash", kind="dash", label="Рывок"))
        options.append(ActionOption(id="disengage", kind="disengage", label="Отход"))
        options.append(ActionOption(id="dodge", kind="dodge", label="Уклонение"))
        if can_hide(engine, ref):
            label = f"Спрятаться (Скрытность СЛ {HIDE_DC})"
            options.append(ActionOption(id="hide", kind="hide", label=label))
        options += help_options(engine, ref)
        options += parley_options(engine, ref)
    if p.turn.bonus:
        if has_second_wind(engine, ref):
            options.append(
                ActionOption(
                    id="second_wind", kind="second_wind", label="Второе дыхание", cost="bonus"
                )
            )
        options += item_options(engine, ref)
        options += transfer_mark_options(engine, ref)
        if has_nimble_escape(engine, ref):
            options.append(
                ActionOption(
                    id="disengage_bonus", kind="disengage", label="Проворное бегство",
                    params={"bonus": True}, cost="bonus",
                )
            )
    if p.turn.action:
        options += stabilize_options(engine, ref)
        options += escape_options(engine, ref)
        zone = [z for z in engine.state.zones if z.id == p.zone_id][0]
        if zone.exit and "restrained" not in conditions:
            options.append(ActionOption(id="flee", kind="flee", label="Бежать"))
    options += pickup_options(engine, ref)
    options.append(end_turn)
    if p.turn.attacks_left > 0 and not p.turn.action:
        for option in options:
            if option.kind in ("attack", "disarm"):
                option.label += f" (ещё {p.turn.attacks_left} из 2)"
    return sorted(options, key=lambda o: COST_ORDER.index(o.cost))
