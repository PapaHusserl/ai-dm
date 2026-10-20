# Меню хода в бою, сгруппированное по ресурсу (stage3-live-combat-menu, M1, M2, M4, T).
# Заголовок «Твой ход — действие ✓ · бонусное ✓ · перемещение ✓ · реакция ✓», потраченное -- «—»;
# группы «Действие:» / «Бонусное действие:» / «Перемещение:» / «Без затрат:»; нумерация сквозная.
import re

from ui_kit import DESCEND, TALK, FightInput, PlainOutput, numbered_lines, play, scene_app

HINT = "Можно словами"
GROUPS = ("Действие:", "Бонусное действие:", "Перемещение:", "Без затрат:")


def fight_out(registry, tmp_path, lines=()):
    app, _ = scene_app(registry, tmp_path, hp=200)
    return app, play(app, [TALK, "1", DESCEND, *lines])


def last_menu(lines):
    # строки после последнего заголовка «Твой ход»
    start = max(i for i, line in enumerate(lines) if line.startswith("Твой ход"))
    return lines[start:]


def menu_blocks(lines):
    # тексты пунктов каждого меню (меню начинается с «Твой ход»)
    blocks = []
    for line in lines:
        if line.startswith("Твой ход"):
            blocks.append([])
        elif blocks and re.match(r"^\d+\. ", line):
            blocks[-1].append(re.sub(r"^\d+\. ", "", line))
    return blocks


def test_menu_starts_with_resource_header(registry, tmp_path):
    _, out = fight_out(registry, tmp_path)
    header = next(line for line in out.lines if line.startswith("Твой ход"))
    for word in ("действие", "бонусное", "перемещение", "реакция"):
        assert word in header
    assert not re.search(r"(действие|бонусное|перемещение|реакция) —", header)


def test_fresh_menu_has_action_move_and_free_groups(registry, tmp_path):
    _, out = fight_out(registry, tmp_path)
    menu = last_menu(out.lines)
    assert "Действие:" in menu
    assert "Перемещение:" in menu
    assert "Без затрат:" in menu


def test_end_turn_is_in_free_group(registry, tmp_path):
    _, out = fight_out(registry, tmp_path)
    menu = last_menu(out.lines)
    free = menu.index("Без затрат:")
    assert any(re.match(r"^\d+\. Закончить ход$", line) for line in menu[free:])


def test_groups_go_in_fixed_order(registry, tmp_path):
    _, out = fight_out(registry, tmp_path)
    menu = last_menu(out.lines)
    places = [menu.index(group) for group in GROUPS if group in menu]
    assert places == sorted(places)


def test_numbering_is_continuous_across_groups(registry, tmp_path):
    _, out = fight_out(registry, tmp_path)
    numbers = [n for n, _ in numbered_lines(last_menu(out.lines))]
    assert numbers == list(range(1, len(numbers) + 1))


def test_number_picks_the_shown_item(registry, tmp_path):
    app, out = fight_out(registry, tmp_path)
    labels = [
        option.label for option in app.runner.preview_turn()
        if option.kind not in ("equip", "unequip")
    ]
    shown = [text for _, text in numbered_lines(last_menu(out.lines))]
    assert labels == shown


def test_group_without_items_is_not_printed(registry, tmp_path):
    app, out = fight_out(registry, tmp_path)
    for block in split_menus(out.lines):
        for group in GROUPS:
            if group in block:
                after = block[block.index(group) + 1:]
                assert after and re.match(r"^\d+\. ", after[0])


def split_menus(lines):
    blocks = []
    for line in lines:
        if line.startswith("Твой ход"):
            blocks.append([])
        if blocks:
            blocks[-1].append(line)
    return blocks


def test_spent_resource_is_a_dash_in_header(registry, tmp_path):
    app, out = fight_out(registry, tmp_path)
    move = next(n for n, text in numbered_lines(last_menu(out.lines)) if text.startswith("Идти"))
    out = PlainOutput()
    from ai_dm.ui.simple import run

    run(app, FightInput(out, [str(move)], limit=0), out)
    header = last_menu(out.lines)[0]
    assert "перемещение —" in header


def test_spent_move_group_is_gone_after_the_step(registry, tmp_path):
    app, out = fight_out(registry, tmp_path)
    move = next(n for n, text in numbered_lines(last_menu(out.lines)) if text.startswith("Идти"))
    out = play(app, [str(move)])
    menu = last_menu(out.lines)
    assert "Перемещение:" not in menu
    assert "Действие:" in menu


def test_hint_is_printed_once_per_combat(registry, tmp_path):
    from ai_dm.ui.simple import run

    app, _ = scene_app(registry, tmp_path, hp=200)
    out = PlainOutput()
    run(app, FightInput(out, [TALK, "1", DESCEND], limit=3), out)
    assert len(menu_blocks(out.lines)) >= 2
    assert out.text.count(HINT) == 1


def test_hint_mentions_one_step_per_number(registry, tmp_path):
    _, out = fight_out(registry, tmp_path)
    assert "Номер — один шаг" in out.text


def test_help_prints_the_hint_again(registry, tmp_path):
    app, out = fight_out(registry, tmp_path)
    again = play(app, ["/help"])
    assert HINT in again.text


def test_menu_never_offers_only_end_turn(registry, tmp_path):
    from ai_dm.ui.simple import run

    app, _ = scene_app(registry, tmp_path, hp=200)
    out = PlainOutput()
    run(app, FightInput(out, [TALK, "1", DESCEND], limit=6), out)
    blocks = menu_blocks(out.lines)
    assert blocks
    for block in blocks:
        assert block != ["Закончить ход"]


def test_menu_lines_fit_into_80_columns(registry, tmp_path):
    _, out = fight_out(registry, tmp_path)
    assert out.raw
    for line in out.raw:
        assert len(line) <= 80


# H3 (stage3-live-mark): концентрация в заголовке хода и в /sheet

def hold_mark(app):
    from ai_dm.state.creature import ActiveEffect, Concentration, Expiry

    hero = app.bundle.heroes[0]
    hero.creature.concentration = Concentration(spell_id="hunters_mark", circle=1)
    enemy = next(p for p in app.bundle.session.active_combat.participants if p.side == "enemies")
    enemy.creature.active_effects.append(
        ActiveEffect(
            id="hunters_mark", source=hero.id, kind="mark",
            expires=Expiry(kind="concentration", owner=hero.id),
        )
    )
    return enemy


def test_sheet_shows_concentration_with_target(registry, tmp_path):
    app, out = fight_out(registry, tmp_path)
    enemy = hold_mark(app)
    text = "\n".join(app.handle("/sheet").lines)
    assert f"Концентрация: Метка охотника → {enemy.name}" in text


def test_turn_header_shows_concentration_with_target(registry, tmp_path):
    app, out = fight_out(registry, tmp_path)
    enemy = hold_mark(app)
    out = play(app, [])
    assert f"Концентрация: Метка охотника → {enemy.name}" in out.text


def test_sheet_has_no_concentration_line_without_it(registry, tmp_path):
    app, out = fight_out(registry, tmp_path)
    assert "Концентрация:" not in "\n".join(app.handle("/sheet").lines)


def number_of(out, start):
    return str(next(n for n, t in numbered_lines(last_menu(out.lines)) if t.startswith(start)))


def test_turn_ends_by_itself_when_nothing_is_left(registry, tmp_path):
    app, out = fight_out(registry, tmp_path)
    for start in ("Идти", "Второе дыхание", "Атака:"):
        out = play(app, [number_of(out, start)])
        assert [t for _, t in numbered_lines(last_menu(out.lines))] != ["Закончить ход"]
    # «Закончить ход» не выбирали, но враги уже ходили
    assert "--- раунд" in out.text


def test_sheet_shows_the_end_time_after_the_target(registry, tmp_path):
    app, out = fight_out(registry, tmp_path)
    hold_mark(app)
    app.bundle.heroes[0].creature.concentration.until_s = 14 * 3600 + 5 * 60
    text = "\n".join(app.handle("/sheet").lines)
    assert "Концентрация: Метка охотника → Воин-гоблин 1 до 14:05" in text
