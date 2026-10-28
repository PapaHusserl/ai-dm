from ai_dm.art import art_for_event
from ai_dm.ui.format import (
    frame_lines,
    menu_lines,
    note_lines,
    roll_lines,
    status_lines,
    turn_menu_lines,
)
from ai_dm.ui.screen import SPENT_PREFIX, limit_state, note_block, reply_blocks, status_line
from ai_dm.ui.session import PlaySession

# limit_state и status_line реэкспортируются для совместимости старых импортов (тесты)
__all__ = ["limit_state", "render", "run", "show_reply", "status_line"]


def emit(sink, lines):
    for line in lines:
        sink.write(line)


def gains_lines_text(block, width):
    # опыт за победу, затем «Получено: предмет ×1, Деньги: +5 зм» одной заметкой
    lines = []
    if block.text:
        lines += note_lines(block.text, width)
    got = [x for x in block.items if not x.startswith(SPENT_PREFIX)]
    if got:
        lines += note_lines("Получено: " + ", ".join(got), width)
    for item in block.items:
        if item.startswith(SPENT_PREFIX):
            lines += note_lines(item, width)
    return lines


def render(block, width):
    kind = block.kind
    if kind == "narration":
        return frame_lines(block.text, width)
    if kind == "roll":
        return roll_lines(block.text, width)
    if kind in ("note", "boundary", "hint", "combat_hint"):
        return note_lines(block.text, width)
    if kind in ("raw", "combat_map"):
        return list(block.items)
    if kind == "menu":
        return menu_lines(block.title, list(block.items), width)
    if kind == "turn_menu":
        turn, concentration, ac, effects, inert = block.args[:5]
        return turn_menu_lines(list(block.items), turn, width, concentration, ac, effects, inert)
    if kind == "status":
        return status_lines(block.text, width)
    if kind == "gains":
        return gains_lines_text(block, width)
    raise ValueError(f"неизвестный блок: {kind}")


def emit_blocks(sink, blocks, width):
    for block in blocks:
        emit(sink, render(block, width))


def show_blocks(app, sink, blocks):
    emit_blocks(sink, blocks, app.settings.app.ui.width)


def show_reply(app, reply, sink, xp_before):
    show_blocks(app, sink, reply_blocks(app, reply, xp_before))


def enter_key_simple(stdin, stdout, session):
    # ввод ключа построчно; ключ читается без эха; возвращает сессию (saved -- ключ записан)
    width = session.deps.app_cfg.ui.width
    emit_blocks(stdout, session.start().blocks, width)
    while True:
        read = stdin.read_secret if session.state == "key" else stdin.read
        step = session.submit(read("> "))
        emit_blocks(stdout, step.blocks, width)
        if step.quit:
            return session


def key_command(app, source, sink, key_factory):
    # /key в игре: окно ввода ключа, затем новые адаптеры ролей этого провайдера
    if key_factory is None:
        show_blocks(app, sink, [note_block("Ввод ключа здесь недоступен.")])
        return
    session = enter_key_simple(source, sink, key_factory())
    if session.saved:
        show_blocks(app, sink, [note_block(app.rekey(session.provider))])


def run(app, source, sink, replay=False, secrets=(), opening=None, key_factory=None):
    session = PlaySession(app, replay=replay, secrets=secrets, opening=opening)
    title = art_for_event("title")
    if title is not None:
        # в простом режиме из рисунков только заставка при старте
        emit(sink, title.split("\n"))
    show_blocks(app, sink, session.start().blocks)
    while True:
        line = session.take_opening()
        if line is None:
            line = source.read("> ")
        step = session.submit(line)
        show_blocks(app, sink, step.blocks)
        if step.request == "key":
            key_command(app, source, sink, key_factory)
        if step.quit:
            return step.exit_code
