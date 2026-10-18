from ai_dm.game import difficulty, tone
from ai_dm.game.battle_map import battle_map_lines
from ai_dm.game.fight_debug import HELP_TEXT, cmd_fight
from ai_dm.game.lore_text import lore_lines
from ai_dm.game.scene import hero_of
from ai_dm.game.sheet_text import (
    ABILITY_HINT,
    SPELL_HINT,
    abilities_lines,
    fit,
    hooks_lines,
    inv_lines,
    rows,
    sheet_stat_lines,
    slots_lines,
    spell_names,
    spells_lines,
    title_line,
)
from ai_dm.game.shop_text import shop_lines
from ai_dm.rules import divine
from ai_dm.rules.derived import armor_class, armor_class_parts
from ai_dm.rules.inventory import effects_line, find_item
from ai_dm.rules.money import format_cp

NANO = 1_000_000_000
TOTAL = "итого"
COMBAT_HINT = (
    "  Можно словами: «стреляю в гоблина и отхожу на уступ» — ход соберётся из нескольких "
    "шагов. Номер — один шаг; после него меню покажет, что осталось."
)

HELP = {
    "help": "список команд",
    "save": "[имя] сохранить игру",
    "load": "[имя] загрузить игру (без имени — последнее автосохранение)",
    "model": "[роль провайдер:модель] показать или сменить модель",
    "cost": "расходы на модель",
    "sheet": "лист героя: характеристики, навыки, черты",
    "inv": "инвентарь по группам",
    "shop": "торговцы здесь: что купить и что продать",
    "lore": "[имя] журнал знаний героя: кто, что, откуда",
    "spells": "заклинания и ячейки",
    "abilities": "умения класса, подкласса, вида и черт",
    "map": "карта зон боя",
    "quit": "сохранить (auto) и выйти",
    "report": "<что не так> записать репорт об ошибке",
    "tone": "настроить тон мира",
    "difficulty": "[easy|normal|hard] сложность боёв (бюджет врагов)",
    "fight": HELP_TEXT,
    "music": "[on|off|0–100|ambient on|off] музыка и эмбиент (только в TUI)",
    "retire": "завершить героя",
}


def cmd_help(app, arg):
    lines = [f"/{name} — {text}" for name, text in HELP.items()]
    return app.reply(fit(lines + ["", "В бою:", COMBAT_HINT], app.settings.app.ui.width))


def cmd_save(app, arg):
    if app.pending == "hero_dead":
        return app.reply(["Герой погиб: сохранять нельзя. Загрузите последнее сохранение."])
    slot = "manual-" + (arg or "quick")
    try:
        app.save_current(slot)
    except ValueError as error:
        return app.reply([f"Не удалось сохранить: {error}"])
    return app.reply([f"Сохранено: {slot}."])


def cmd_load(app, arg):
    slot = "manual-" + arg if arg else "auto"
    return app.reply(app.load(slot))


def cmd_model(app, arg):
    if not arg:
        info = app.adapter.info()
        lines = [f"narrator: {info.provider}:{info.model}"]
        for role in ("world", "summarizer"):
            config = getattr(app.settings.app.roles, role)
            lines.append(f"{role}: {config.provider}:{config.model}")
        lines.append("Доступно: " + ", ".join(app.model_options()))
        lines.append("Сменить: /model narrator <провайдер:модель>")
        return app.reply(lines)
    role, _, key = arg.partition(" ")
    if role != "narrator":
        return app.reply([f"Неизвестная роль {role!r}. Сейчас меняется только narrator."])
    error = app.set_narrator(key.strip())
    if error is not None:
        return app.reply([error])
    return app.reply([f"Модель рассказчика: {key.strip()}."])


def money_text(nano):
    return f"${nano / NANO:.4f}"


def calls_cost_line(journal, run_ids, label) -> str:
    records = journal.records_for(run_ids)
    total = sum(r["cost_nano"] for r in records)
    return f"{label}: {money_text(total)} ({len(records)} вызовов)"


def cost_report(app):
    return app.ledger.report(app.now().astimezone().date())


def cost_rows(report):
    # плоская таблица: (период, роль, модель, нано-доллары); итог периода -- строка с ролью TOTAL
    rows = []
    for title, totals in (("Сессия", report.session), ("День", report.day), ("Мир", report.world)):
        for (role, model), cost in sorted(totals.by_role_model.items()):
            rows.append((title, role, model, cost))
        rows.append((title, TOTAL, "", totals.total_nano))
    return rows


def cost_lines(report):
    lines = []
    for title, role, model, cost in cost_rows(report):
        if role == TOTAL:
            lines.append(f"{title}: {money_text(cost)}")
        else:
            lines.append(f"  {role} / {model}: {money_text(cost)}")
    return lines


def cmd_cost(app, arg):
    return app.reply(cost_lines(cost_report(app)))


def ac_text(hero, registry, now_s) -> str:
    # «КД 15 = Мифриловая кольчужная рубаха 13 + Лов 2 (предел средн. доспеха 2)»
    parts = armor_class_parts(hero, registry, now_s)
    text = ""
    for label, value, note in parts:
        if value == 0:
            continue
        if text:
            text += " - " if value < 0 else " + "
        text += f"{label} {abs(value)}"
        if note:
            text += f" ({note})"
    return f"КД {sum(value for _, value, _ in parts)} = {text}"


def equipment_text(hero, registry) -> str:
    # что надето и что в руках
    slots = [
        ("доспех", hero.equipped.armor), ("щит", hero.equipped.shield),
        ("в руках", hero.equipped.main_hand), ("в левой руке", hero.equipped.off_hand),
    ]
    shown = []
    for title, item_id in slots:
        if item_id is None:
            continue
        shown.append(f"{title}: {find_item(registry, item_id)[1].name}")
    if not shown:
        return "Экипировка: ничего"
    return "Экипировка: " + "; ".join(shown)


# подпись игроку без рода (бог может быть и богом, и богиней)
GOD_ATTITUDE = {"благосклонна": "милость", "равнодушна": "безразличие", "гневается": "гнев"}


def cmd_sheet(app, arg):
    hero = hero_of(app.bundle)
    creature = hero.creature
    now_s = app.bundle.world.clock.now_s
    lines = [
        title_line(hero, app.registry),
        f"HP {creature.hp_current}/{creature.hp_max}, КД {armor_class(hero, app.registry, now_s)}",
        ac_text(hero, app.registry, now_s),
    ]
    width = app.settings.app.ui.width
    equipment = equipment_text(hero, app.registry)
    lines += rows("Экипировка:", equipment[len("Экипировка: "):].split("; "), width, "; ")
    lines += sheet_stat_lines(hero, app.registry, width)
    effects = effects_line(hero, app.registry, now_s)
    if effects:
        lines.append(effects)
    concentration = app.runner.concentration_line()
    if concentration:
        lines.append(concentration)
    if app.registry.get("class", hero.sheet.class_id).spellcasting is not None:
        slots = "; ".join(slots_lines(hero, app.registry))
        lines.append(f"Заклинания (ячейки {slots}): " + ", ".join(spell_names(hero, app.registry)))
    lines += hooks_lines(hero)
    if hero.scars:
        lines.append("Шрамы: " + ", ".join(hero.scars))
    # отношение всех богов пантеона -- приблизительно, без чисел; не тронутый бог -- безразличие
    pantheon = app.bundle.world.pantheon
    gods = sorted(set(pantheon) | set(hero.favor))
    if gods:
        lines.append("Боги:")
    for god_id in gods:
        god = pantheon.get(god_id)
        name = god_id if god is None else god.name
        lines.append(f"  {name}: {GOD_ATTITUDE[divine.approx_label(hero.favor.get(god_id, 0))]}")
    return app.reply(fit(lines, app.settings.app.ui.width))


def cmd_tone(app, arg):
    world_tone = app.bundle.world.tone
    if not arg:
        return app.reply(tone.show_lines(world_tone))
    change, error = tone.parse(world_tone, arg)
    if error is not None:
        return app.reply([error])
    scale, value, weakening = change
    if weakening:
        # ослабление hard_limits -- только с подтверждением
        app.tone_change = (scale, value)
        app.pending = "tone_confirm"
        return app.reply([f"Ослабить жёсткое ограничение ({value[1:]})? Выберите да или нет."])
    line = tone.apply(app.bundle, scale, value)
    app.save_current("auto")
    return app.reply([line])


def cmd_difficulty(app, arg):
    if not arg:
        return app.reply([difficulty.show_line(app.bundle.world, app.settings.rules)])
    value, error = difficulty.parse(arg)
    if error is not None:
        return app.reply([error])
    line = difficulty.apply(app.bundle, value)
    app.save_current("auto")
    return app.reply([line])


def cmd_inv(app, arg):
    hero = hero_of(app.bundle)
    lines = inv_lines(hero, app.registry, format_cp(hero.money_cp))
    return app.reply(fit(lines, app.settings.app.ui.width))


def cmd_shop(app, arg):
    hero = hero_of(app.bundle)
    lines = shop_lines(hero, app.bundle.world, app.registry, app.settings.rules)
    return app.reply(fit(lines, app.settings.app.ui.width))


def cmd_lore(app, arg):
    lines = lore_lines(hero_of(app.bundle), app.bundle.world, app.registry, arg)
    return app.reply(fit(lines, app.settings.app.ui.width))


def cmd_spells(app, arg):
    hero = hero_of(app.bundle)
    lines = spells_lines(hero, app.registry, app.settings.app.ui.width) + ["", SPELL_HINT]
    return app.reply(fit(lines, app.settings.app.ui.width))


def cmd_abilities(app, arg):
    hero = hero_of(app.bundle)
    lines = abilities_lines(hero, app.registry, app.settings.app.ui.width) + ["", ABILITY_HINT]
    return app.reply(fit(lines, app.settings.app.ui.width))


def cmd_map(app, arg):
    state = app.bundle.session.active_combat
    if state is None:
        return app.reply(["Сейчас не бой."])
    width = app.settings.app.ui.width
    hero = hero_of(app.bundle)
    return app.reply(raw=battle_map_lines(state, app.bundle.world, hero, width, app.registry))


def cmd_quit(app, arg):
    if app.pending == "hero_dead":
        return app.reply(["До встречи."], quit=True)
    try:
        app.save_current("auto")
    except ValueError as error:
        return app.reply([f"Не удалось сохранить: {error}"])
    return app.reply(["Сохранено: auto.", "До встречи."], quit=True)


def cmd_report(app, arg):
    if not arg:
        return app.reply(["Напишите, что не так: /report <что не так>"])
    return app.reply(app.report(arg))


def cmd_music(app, arg):
    return app.reply(app.audio.command(arg.strip()))


def stub(stage):
    def command(app, arg):
        return app.reply([f"Команда появится на этапе {stage}."])

    return command


COMMANDS = {
    "help": cmd_help,
    "save": cmd_save,
    "load": cmd_load,
    "model": cmd_model,
    "cost": cmd_cost,
    "sheet": cmd_sheet,
    "inv": cmd_inv,
    "shop": cmd_shop,
    "lore": cmd_lore,
    "spells": cmd_spells,
    "abilities": cmd_abilities,
    "map": cmd_map,
    "quit": cmd_quit,
    "report": cmd_report,
    "tone": cmd_tone,
    "difficulty": cmd_difficulty,
    "fight": cmd_fight,
    "music": cmd_music,
    "retire": stub(9),
}
