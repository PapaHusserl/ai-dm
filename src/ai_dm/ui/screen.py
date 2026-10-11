from dataclasses import dataclass

from ai_dm.art import PictureState
from ai_dm.audio import SoundState
from ai_dm.core.clock import DAY
from ai_dm.game.battle_map import battle_map_lines, part_hp, part_name
from ai_dm.game.boundary import boundary_lines
from ai_dm.game.scene import hero_of
from ai_dm.llm.cost import check_limit
from ai_dm.rules.derived import ac_summary
from ai_dm.rules.inventory import entry_name
from ai_dm.rules.money import format_cp
from ai_dm.ui.combat_menu import TargetChip
from ai_dm.ui.format import COMBAT_HINT

LABELS = {
    "retry": "Повторить ход",
    "switch_model": "Сменить модель",
    "save_and_quit": "Сохранить и выйти",
    "average": "Среднее значение HP",
    "roll": "Бросок кости HP",
    "load_last_save": "Загрузить последнее сохранение",
    "quit": "Выйти",
}
LIMIT_MENU = ["Продолжить", "Сохранить и выйти"]
SERVICE_PREFIXES = ("Действие игрока:", "Варианты ответа предложены")
LIMIT_ORDER = ["ok", "warn", "pause"]


@dataclass
class Block:
    # kind: narration, roll, note, boundary, raw, hint, menu, combat_map, turn_menu,
    # combat_hint, status, gains
    # text -- одна строка/абзац; items -- список строк (варианты меню, готовые строки raw/карты,
    # строки «Получено»); args -- параметры turn_menu:
    # (turn, concentration, ac, effects, inert, roster)
    kind: str
    text: str = ""
    items: tuple = ()
    title: str | None = None
    args: tuple = ()
    # строка лога боя (только для roll/note): простой режим не смотрит, TUI уводит в «Ход боя»
    combat: bool = False


def status_line(app):
    hero = hero_of(app.bundle)
    clock = app.bundle.world.clock
    minutes = clock.now_s % DAY // 60
    spent = app.ledger.report(app.now().astimezone().date()).session.total_nano / 1e9
    return (
        f"HP {hero.creature.hp_current}/{hero.creature.hp_max} · "
        f"{ac_summary(hero, app.registry, clock.now_s)} · "
        f"{clock.to_date()} {minutes // 60:02d}:{minutes % 60:02d} · сессия ${spent:.4f}"
    )


def limit_state(app):
    cfg = app.settings.app.cost_limits
    report = app.ledger.report(app.now().astimezone().date())
    by_session = check_limit(cfg, report.session.total_nano, cfg.session_limit_micro)
    by_day = check_limit(cfg, report.day.total_nano, cfg.day_limit_micro)
    return max(by_session, by_day, key=LIMIT_ORDER.index)


def limit_percent(app):
    # процент лимита трат (больший из сессии и дня); None, если лимит выключен
    cfg = app.settings.app.cost_limits
    if not cfg.enabled:
        return None
    report = app.ledger.report(app.now().astimezone().date())
    pairs = [
        (report.session.total_nano, cfg.session_limit_micro),
        (report.day.total_nano, cfg.day_limit_micro),
    ]
    percents = [spent * 100 // (limit * 1000) for spent, limit in pairs if limit]
    return max(percents, default=None)


def scene_mark(app):
    # (id, название) текущей сцены для разделителя в ленте TUI: название места, иначе номер сцены
    scene = app.bundle.session.current_scene
    if scene is None:
        return None, ""
    place = app.bundle.world.locations.get(scene.location_id)
    if place is not None:
        return scene.id, place.name
    return scene.id, "Сцена " + scene.id.removeprefix("scene_")


def picture_state(app):
    # что нужно pick_picture: локация героя, первый живой враг идущего боя
    location = app.bundle.world.locations.get(hero_of(app.bundle).location_id)
    combat = app.bundle.session.active_combat
    if combat is None:
        return PictureState(location)
    monster = None
    for part in combat.participants:
        if part.side == "enemies" and part.status == "active" and part.monster_id is not None:
            monster = app.registry.get("monster", part.monster_id)
            break
    return PictureState(location, monster, combat.id)


def location_tag_chain(world, location):
    # теги локации, затем родителя и дальше вверх по parent_id (свои первыми)
    tags = []
    seen = set()
    while location is not None and location.id not in seen:
        seen.add(location.id)
        tags += location.tags
        location = world.locations.get(location.parent_id)
    return tuple(tags)


def sound_state(app):
    # что нужно pick_theme: локация героя с тегами предков, идёт ли бой, оси тона мира
    world = app.bundle.world
    location = world.locations.get(hero_of(app.bundle).location_id)
    return SoundState(
        None if location is None else location.id,
        location_tag_chain(world, location),
        app.bundle.session.active_combat is not None,
        world.tone.horror,
        world.tone.romance,
    )


def note_block(text):
    return Block("note", text=text)


def menu_block(labels, title="Что делаешь?"):
    return Block("menu", items=tuple(labels), title=title)


def status_block(app):
    return Block("status", text=status_line(app))


def combat_map_lines(app, width=None):
    state = app.bundle.session.active_combat
    if width is None:
        width = app.settings.app.ui.width
    return battle_map_lines(state, app.bundle.world, hero_of(app.bundle), width, app.registry)


def roster_of(app):
    # живые враги боя для меню целей: ref, имя, HP, близость к герою (своя зона, соседняя, дальше)
    state = app.bundle.session.active_combat
    world = app.bundle.world
    hero = hero_of(app.bundle)
    zones = {zone.id: zone for zone in state.zones}
    own_zones = [part.zone_id for part in state.participants if part.ref == hero.id]
    own = zones.get(own_zones[0]) if own_zones else None
    if own is None:
        # героя нет на карте (выбыл, сбежал): целей нет
        return ()
    chips = []
    for part in state.participants:
        if part.side != "enemies" or part.status != "active":
            continue
        rank = 0 if part.zone_id == own.id else 1 if part.zone_id in own.adjacent else 2
        name = part_name(state, world, hero, part.ref)
        chips.append(TargetChip(part.ref, name, part_hp(world, part, hero)[0], rank))
    return tuple(chips)


def combat_blocks(app):
    # побочный эффект: ставит app.hinted_combat. Вызывать один раз за ход,
    # перерисовку экрана делать из сохранённых блоков, а не повторным screen_blocks
    blocks = [Block("combat_map", items=tuple(combat_map_lines(app)))]
    options, turn, inert = app.runner.preview_screen()
    concentration = app.runner.concentration_line()
    ac = app.runner.ac_text()
    effects = app.runner.effects_line()
    args = (turn, concentration, ac, effects, tuple(inert), roster_of(app))
    blocks.append(Block("turn_menu", items=tuple(options), args=args))
    combat_id = app.bundle.session.active_combat.id
    if app.hinted_combat != combat_id:
        # подсказка про ввод словами: один раз за бой
        app.hinted_combat = combat_id
        blocks.append(Block("combat_hint", text=COMBAT_HINT))
    return blocks


def screen_blocks(app):
    # один раз за ход (в бою меняет app.hinted_combat); перерисовка -- из сохранённых блоков
    if app.pending is not None:
        labels = [LABELS.get(key) or app.menu_label(key) for key in app.menu_for(app.pending)]
        return [menu_block(labels, "Выбери:")]
    if app.bundle.session.active_combat is not None:
        return combat_blocks(app)
    if app.bundle.session.offered_choices:
        return [menu_block(app.bundle.session.offered_choices)]
    return []


def turn_line_block(line, turn, combat=False):
    if line in turn.rolls:
        return Block("roll", text=line, combat=combat)
    return Block("note", text=line, combat=combat)


SPENT_PREFIX = "Потрачено: "


def loot_snapshot(app):
    hero = hero_of(app.bundle)
    items = {(e.item_id, e.cost_cp, e.quality): e.qty for e in hero.inventory}
    return hero.sheet.xp, items, hero.money_cp


def gains_lines(app, before, with_xp=True):
    xp_before, items_before, money_before = before
    hero = hero_of(app.bundle)
    lines = []
    if with_xp and hero.sheet.xp != xp_before:
        lines.append(f"Опыт: +{hero.sheet.xp - xp_before}")
    for entry in hero.inventory:
        added = entry.qty - items_before.get((entry.item_id, entry.cost_cp, entry.quality), 0)
        if added > 0:
            lines.append(f"{entry_name(entry, app.registry)} ×{added}")
    if hero.money_cp > money_before:
        lines.append(f"Деньги: +{format_cp(hero.money_cp - money_before)}")
    if hero.money_cp < money_before:
        lines.append(f"{SPENT_PREFIX}−{format_cp(money_before - hero.money_cp)}")
    return lines


def reply_blocks(app, reply, xp_before, before=None):
    blocks = []
    turn = reply.turn
    if turn is not None:
        # в бою (и на ходе, закончившем бой) броски идут в лог боя, а не в ленту
        in_fight = bool(turn.log) or app.bundle.session.active_combat is not None
        for line in turn.lines:
            if line in turn.log or line.startswith(SERVICE_PREFIXES):
                continue
            blocks.append(turn_line_block(line, turn, in_fight and line in turn.rolls))
        for line in turn.log:
            if not line.startswith(SERVICE_PREFIXES):
                blocks.append(turn_line_block(line, turn, True))
    if reply.narration:
        blocks.append(Block("narration", text=reply.narration))
    if turn is not None:
        for line in boundary_lines(turn.chapter_closed, turn.offscreen):
            blocks.append(Block("boundary", text=line))
    for line in reply.lines:
        blocks.append(note_block(line))
    if reply.raw:
        blocks.append(Block("raw", items=tuple(reply.raw)))
    if reply.hint:
        blocks.append(Block("hint", text=reply.hint))
    victory = turn is not None and turn.combat_outcome == "victory"
    if victory:
        blocks.append(note_block("Бой окончен: победа!"))
    if victory or before is not None:
        text = ""
        if victory:
            text = f"Получено опыта: {hero_of(app.bundle).sheet.xp - xp_before}"
        items = ()
        if before is not None:
            # при победе опыт уже в text, в items его не дублируем
            items = tuple(gains_lines(app, before, not victory))
        if text or items:
            blocks.append(Block("gains", text=text, items=items))
    return blocks
