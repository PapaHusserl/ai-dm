from ai_dm.combat.available import equip_problem
from ai_dm.core.rng import Rng
from ai_dm.game.inv_lookup import (
    drinkable,
    equippable,
    find_entry,
    minutes_for,
    name_of,
    refusal_text,
    slot_of,
    worn_slot,
)
from ai_dm.game.scene import hero_of
from ai_dm.game.sheet_text import fit
from ai_dm.protocol.handlers.resources import consumables_left, drink_once, heal_once
from ai_dm.rules.inventory import InventoryError, blocking_slots, equip, find_item, unequip
from ai_dm.rules.spellcasting import expire_concentration

USAGE = (
    "Экипировка и зелья: /inv надеть <предмет> [левая] · /inv снять <слот: доспех, щит, "
    "правая, левая> · /inv выпить <предмет>"
)
SELECT_FIRST = "Сначала нужно сделать выбор в меню."
COMBAT_POTION = "В бою зелья — через меню хода, пункт «Использовать»."
LEFT_WORDS = ("левая", "левую", "левой", "left", "off_hand")
SLOT_TITLES = {
    "armor": "доспех", "shield": "щит", "main_hand": "оружие из правой руки",
    "off_hand": "оружие из левой руки",
}


def option_number(app, kind, **params):
    # номер варианта смены экипировки в списке боя или None
    for number, option in enumerate(app.runner.preview_turn(), start=1):
        if option.kind == kind and all(option.params.get(k) == v for k, v in params.items()):
            return number
    return None


def finish(app, lines, notes):
    # вне боя: заметки для рассказчика следующего хода, автосохранение
    app.inv_notes += notes
    app.save_current("auto")
    return app.reply(fit(lines, app.settings.app.ui.width))


def shift_clock(app, hero, minutes, lines):
    if minutes <= 0:
        return
    world = app.bundle.world
    world.clock.advance(minutes * 60)
    lines.append(f"Прошло минут: {minutes}.")
    ended = expire_concentration(hero, world)
    if ended is not None:
        lines.append(f"Концентрация: {app.registry.get('spell', ended).name} кончилась.")


def equip_cmd(app, hero, text):
    registry = app.registry
    words = text.split()
    left = len(words) > 1 and words[-1].casefold() in LEFT_WORDS
    if left:
        text = " ".join(words[:-1])
    item_id, error = find_entry(hero, registry, text, equippable)
    if error is not None:
        return app.reply([error])
    found = find_item(registry, item_id)
    if left and found[0] != "weapon":
        return app.reply(["В левую руку берут только оружие."])
    slot = slot_of(found, left)
    name = found[1].name
    if getattr(hero.equipped, slot) == item_id:
        return app.reply([f"Уже надето: {name}."])
    blockers = blocking_slots(hero, item_id, registry, slot)
    if app.bundle.session.active_combat is not None:
        return equip_in_combat(app, hero, item_id, slot, blockers)
    return equip_outside(app, hero, item_id, slot, blockers)


def equip_in_combat(app, hero, item_id, slot, blockers):
    registry = app.registry
    if slot == "armor":
        return app.reply(["В бою доспех не сменить."])
    if blockers:
        mine = ", ".join(name_of(registry, getattr(hero.equipped, s)) for s in blockers)
        return app.reply([f"Сначала сними: {mine}."])
    number = option_number(app, "equip", item=item_id, slot=slot)
    if number is None:
        problem = equip_problem(hero, item_id, registry, slot)
        if problem is not None:
            return app.reply([refusal_text(problem, registry)])
        return app.reply(["Сейчас не получится: в этом ходу не осталось ни действия, ни свободного"
                          " взаимодействия."])
    return app.handle(str(number))


def equip_outside(app, hero, item_id, slot, blockers):
    registry = app.registry
    saved = hero.equipped.model_copy()
    old = getattr(hero.equipped, slot) if slot in ("armor", "shield") else None
    lines = []
    notes = []
    minutes = 0
    try:
        for blocker in blockers:
            removed = unequip(hero, blocker)
            minutes += minutes_for(registry, removed, True)
            lines.append(f"Снято: {name_of(registry, removed)}.")
            notes.append(f"снял «{name_of(registry, removed)}»")
        if old is not None:
            minutes += minutes_for(registry, old, True)
        equip(hero, item_id, registry, slot)
    except InventoryError as error:
        hero.equipped = saved
        return app.reply([refusal_text(error, registry)])
    minutes += minutes_for(registry, item_id, False)
    name = name_of(registry, item_id)
    if slot in ("armor", "shield"):
        lines.append(f"Надето: {name}.")
        notes.append(f"надел «{name}»")
    else:
        where = "левой руке" if slot == "off_hand" else "руке"
        lines.append(f"В {where}: {name}.")
        notes.append(f"взял в {'левую ' if slot == 'off_hand' else ''}руку «{name}»")
    shift_clock(app, hero, minutes, lines)
    return finish(app, lines, notes)


def unequip_in_combat(app, slot):
    if slot == "armor":
        return app.reply(["В бою доспех не снять."])
    number = option_number(app, "unequip", slot=slot)
    if number is None:
        return app.reply(["Сейчас не получится: в этом ходу не осталось ни действия, ни "
                          "свободного взаимодействия."])
    return app.handle(str(number))


def unequip_cmd(app, hero, text):
    registry = app.registry
    slot = worn_slot(hero, registry, text)
    if slot is None:
        return app.reply([f"Не понял, что снять: {text}. Слоты: доспех, щит, правая, левая."])
    item_id = getattr(hero.equipped, slot)
    if item_id is None:
        return app.reply([f"Там ничего нет: {SLOT_TITLES[slot]}."])
    if app.bundle.session.active_combat is not None:
        return unequip_in_combat(app, slot)
    name = name_of(registry, item_id)
    unequip(hero, slot)
    lines = [f"Снято: {name}."]
    shift_clock(app, hero, minutes_for(registry, item_id, True), lines)
    return finish(app, lines, [f"снял «{name}»"])


def drink_cmd(app, hero, text):
    registry = app.registry
    item_id, error = find_entry(hero, registry, text, drinkable)
    if error is not None:
        return app.reply([error])
    if app.bundle.session.active_combat is not None:
        return app.reply([COMBAT_POTION])
    item = find_item(registry, item_id)[1]
    world = app.bundle.world
    if item.effects[0].type == "heal":
        scene = app.bundle.session.current_scene
        limit = app.settings.rules.limits
        left = consumables_left(scene, limit)
        if left is not None:
            if left < 1:
                return app.reply([f"Лимит расходников за сцену: {limit.consumables_per_scene}."])
            scene.consumables_used += 1
        rng = Rng.from_state(world.rng)
        line = heal_once(hero, item, registry, rng)
        world.rng = rng.state
    else:
        line = drink_once(hero, item, registry, world.clock.now_s)[0]
    return finish(app, [line], [f"выпил «{item.name}»"])


VERBS = {"надеть": equip_cmd, "снять": unequip_cmd, "выпить": drink_cmd}


def run(app, arg):
    verb, _, text = arg.partition(" ")
    handler = VERBS.get(verb.casefold())
    text = text.strip()
    if handler is None or not text:
        return app.reply([USAGE])
    if app.pending is not None:
        return app.reply([SELECT_FIRST])
    return handler(app, hero_of(app.bundle), text)
