from ai_dm.game.inv_actions import option_number
from ai_dm.game.inv_lookup import drinkable, equippable, slot_of
from ai_dm.game.scene import hero_of
from ai_dm.game.sheet_text import effect_texts, spell_ids
from ai_dm.rules.inventory import SLOTS, find_item, item_totals
from ai_dm.rules.spellcasting import free_cast_left, spell_kind
from ai_dm.ui.format import INERT_NOTE, wrap_block
from ai_dm.ui.screen import combat_map_lines
from ai_dm.ui.tui import strings
from ai_dm.ui.tui.inv_sections import inv_section


def pickable(game, session, choices):
    # что PlaySession.submit сопоставит цифре: меню лимита, меню pending, вне боя -- варианты
    if session.limit_menu:
        return choices.items
    if game.pending is not None:
        return game.menu_for(game.pending)
    if game.bundle.session.active_combat is not None:
        return []
    return game.bundle.session.offered_choices


def modal_lines(blocks):
    lines = []
    for block in blocks:
        if block.kind == "note":
            lines.append(block.text)
        elif block.kind == "raw":
            lines.extend(block.items)
    return lines


def map_lines(game, width):
    # карта боя под ширину панели; легенда шире панели -- переносится, рамки зон влезают сами
    lines = []
    for line in combat_map_lines(game, width):
        if len(line) > width:
            lines.extend(wrap_block(line, width, "  ", "    "))
        else:
            lines.append(line)
    return lines


UNEQUIP_KEYS = {"off_hand": ("r", strings.INV_UNEQUIP_LEFT)}


def inv_actions_of(game, item_id, found, worn):
    # действия предмета: (клавиша, подсказка, строка подкоманды /inv, эхо в ленте);
    # в бою -- только те, на которые есть скрытый вариант equip/unequip (то же, что ищет /inv)
    name = found[1].name
    in_combat = game.bundle.session.active_combat is not None
    if drinkable(found):
        drink = ("d", strings.INV_DRINK, f"/inv выпить {item_id}", f"{strings.INV_DRINK}: {name}")
        return [] if in_combat else [drink]
    if not equippable(found):
        return []
    # (вариант боя, действие); вне боя годятся все
    candidates = [
        (("unequip", {"slot": slot}),
         *UNEQUIP_KEYS.get(slot, ("u", strings.INV_UNEQUIP)),
         f"/inv снять {strings.INV_SLOT_WORDS[slot]}", f"{strings.INV_UNEQUIP}: {name}")
        for slot in worn
    ]
    if found[0] == "weapon":
        targets = (("main_hand", "e", strings.INV_EQUIP, ""),
                   ("off_hand", "l", strings.INV_EQUIP_LEFT, " левая"))
    else:
        targets = ((slot_of(found, False), "e", strings.INV_EQUIP, ""),)
    candidates += [
        (("equip", {"item": item_id, "slot": slot}), key, hint,
         f"/inv надеть {item_id}{suffix}", f"{hint}: {name}")
        for slot, key, hint, suffix in targets if slot not in worn
    ]
    return [
        tuple(action) for (kind, params), *action in candidates
        if not in_combat or option_number(game, kind, **params) is not None
    ]


def inv_rows(game):
    # строки окна /inv: (подпись, описание, действия, вкладка);
    # действия -- подкоманды /inv, второго пути нет
    hero = hero_of(game.bundle)
    registry = game.registry
    in_combat = game.bundle.session.active_combat is not None
    rows = []
    no_actions = strings.INV_NO_ACTIONS
    for item_id, qty in item_totals(hero).items():
        found = find_item(registry, item_id)
        if found is None:
            rows.append((item_id, "", [], inv_section(None, [])))
            continue
        item = found[1]
        worn = [slot for slot in SLOTS if getattr(hero.equipped, slot) == item_id]
        label = ("★ " if worn else "") + item.name + (f" x{qty}" if qty > 1 else "")
        description = item.description or effect_texts(getattr(item, "effects", []))
        actions = inv_actions_of(game, item_id, found, worn)
        if not actions:
            # зелье в бою -- через меню хода (решение 20)
            note = strings.INV_COMBAT_POTION if in_combat and drinkable(found) else no_actions
            description = "\n\n".join(part for part in (description, note) if part)
        rows.append((label, description, actions, inv_section(found, worn)))
    return rows


def spell_rows(game):
    # строки окна /spells: (подпись, описание, можно ли выбрать, строка хода, эхо в ленте)
    hero = hero_of(game.bundle)
    registry = game.registry
    spells = [
        registry.get("spell", spell_id) for spell_id in spell_ids(hero, registry)
        if registry.has("spell", spell_id)
    ]
    rows = []
    if game.bundle.session.active_combat is None:
        for spell in spells:
            line = strings.SPELL_CAST.format(name=spell.name)
            # ячейка своего или более высокого круга годится (апкаст)
            no_slot = not any(
                hero.creature.resources.get(f"spell_slot:{circle}") is not None
                and hero.creature.resources[f"spell_slot:{circle}"].current > 0
                for circle in range(spell.level, 10)
            )
            if spell.level > 0 and no_slot and not free_cast_left(hero, registry, spell):
                label = f"{spell.name} — {strings.SPELL_NO_SLOT}"
                rows.append((label, spell.description, False, "", ""))
            else:
                rows.append((spell.name, spell.description, True, line, line))
        return rows
    # в бою выбор -- пункт меню хода: тот же номер, что ввёл бы игрок
    used = set()
    for number, option in enumerate(game.runner.preview_turn(), start=1):
        if option.kind == "cast":
            spell = registry.get("spell", option.params["spell"])
            used.add(spell.id)
            echo = f"{number}. {option.label}"
            rows.append((option.label, spell.description, True, str(number), echo))
    for spell in spells:
        if spell.id not in used:
            note = INERT_NOTE if spell_kind(spell) is None else strings.SPELL_BUSY
            rows.append((f"{spell.name} — {note}", spell.description, False, "", ""))
    return rows
