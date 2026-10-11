from ai_dm.game.scene import hero_of
from ai_dm.game.sheet_text import spell_ids
from ai_dm.rules.spellcasting import free_cast_left, spell_kind
from ai_dm.ui.format import INERT_NOTE, wrap_block
from ai_dm.ui.screen import combat_map_lines
from ai_dm.ui.tui import strings


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
