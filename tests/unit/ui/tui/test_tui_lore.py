# Ж3 (docs/plan-zh3.md, пп. 0.9, 14): окно журнала знаний LoreModal по /lore.
#   Любая форма /lore открывает окно (аргумент -- предвыбор сущности), пустой журнал -- обычное
#   текстовое окно с LORE_EMPTY; слева OptionList #lore-list с заголовками видов (disabled) и
#   сущностями «Имя (число записей)», справа #lore-body с записями выбранной; Esc и кнопка
#   закрывают; цифры в окне не выбирают ход; отдельной клавиши для журнала нет.
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "game"))

from ai_dm.game.lore_text import LORE_EMPTY  # noqa: E402
from ai_dm.game.scene import hero_of  # noqa: E402
from ai_dm.state.knowledge import KnowledgeEntry  # noqa: E402
from ai_dm.ui.tui.app import AiDmApp  # noqa: E402
from ai_dm.ui.tui.modals import LoreModal, TextModal  # noqa: E402


def run(app, steps, size=(140, 40)):
    async def scenario():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            return await steps(app, pilot)

    return asyncio.run(scenario())


def fill(game):
    hero_of(game.bundle).knowledge += [
        KnowledgeEntry(
            kind="npc", ref="innkeeper", text="Знает про подвал", source="told",
            from_ref="grakh", at_s=0,
        ),
        KnowledgeEntry(kind="npc", ref="innkeeper", text="Любит эль", source="rumor", at_s=0),
        KnowledgeEntry(kind="npc", ref="grakh", text="Ищет брата", source="rumor", at_s=0),
        KnowledgeEntry(
            kind="situation", ref="plague", text="В деревне мор", source="rumor", at_s=0
        ),
    ]


def options(app):
    menu = app.screen.query_one("#lore-list")
    return [menu.get_option_at_index(i) for i in range(menu.option_count)]


def option_texts(app):
    return [str(option.prompt) for option in options(app)]


def body(tui, app):
    return tui.flat(str(app.screen.query_one("#lore-text").content))


def highlighted(app):
    return app.screen.query_one("#lore-list").highlighted


# открытие

def test_lore_opens_lore_modal(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)
    fill(game)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/lore")
        return isinstance(app.screen, LoreModal)

    assert run(app, steps) is True


def test_lore_with_empty_journal_opens_text_modal(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/lore")
        return (
            isinstance(app.screen, TextModal), isinstance(app.screen, LoreModal),
            LORE_EMPTY in tui.flat(tui.visible_text(app)),
        )

    assert run(app, steps) == (True, False, True)


def test_lore_with_query_and_empty_journal_opens_text_modal(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/lore Гракх")
        return isinstance(app.screen, TextModal) and not isinstance(app.screen, LoreModal)

    assert run(app, steps) is True


def test_lore_modal_has_title(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)
    fill(game)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/lore")
        return app.screen.query_one("#modal").border_title

    assert run(app, steps) == "Журнал знаний"


# содержимое

def test_list_has_disabled_kind_headers_and_entities(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)
    fill(game)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/lore")
        return option_texts(app), [o.disabled for o in options(app)]

    texts, disabled = run(app, steps)
    assert [t.strip() for t in texts] == [
        "Люди:", "Гарт (2)", "Гракх (1)", "Ситуации:", "plague (1)",
    ]
    assert disabled == [True, False, False, True, False]


def test_first_entity_is_highlighted_by_default(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)
    fill(game)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/lore")
        return highlighted(app)

    assert run(app, steps) == 1


def test_body_shows_entries_of_highlighted_entity(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)
    fill(game)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/lore")
        return body(tui, app)

    text = run(app, steps)
    assert "Знает про подвал" in text
    assert "Любит эль" in text
    assert "Ищет брата" not in text


def test_body_names_teller_by_npc_name(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)
    fill(game)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/lore")
        return body(tui, app)

    assert "рассказали: Гракх" in run(app, steps)


def test_arrow_down_switches_body_to_next_entity(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)
    fill(game)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/lore")
        await pilot.press("down")
        await pilot.pause()
        return highlighted(app), body(tui, app)

    index, text = run(app, steps)
    assert index == 2
    assert "Ищет брата" in text
    assert "Любит эль" not in text


def test_arrow_down_skips_disabled_header(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)
    fill(game)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/lore")
        await pilot.press("down", "down")
        await pilot.pause()
        return highlighted(app), body(tui, app)

    index, text = run(app, steps)
    assert index == 4
    assert "В деревне мор" in text


# предвыбор

def test_query_preselects_entity(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)
    fill(game)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/lore Гракх")
        return highlighted(app), body(tui, app)

    index, text = run(app, steps)
    assert index == 2
    assert "Ищет брата" in text


def test_query_by_ref_preselects_entity(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)
    fill(game)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/lore plague")
        return highlighted(app)

    assert run(app, steps) == 4


def test_query_selects_entity_by_name_order_inside_group(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)
    fill(game)
    hero_of(game.bundle).knowledge.append(
        KnowledgeEntry(kind="situation", ref="old_war", text="Давняя война", source="read", at_s=0)
    )

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/lore old_war")
        return option_texts(app)[highlighted(app)].strip()

    # old_war стоит в группе выше plague (порядок по имени), строка 4
    assert run(app, steps) == "old_war (1)"


def test_unknown_query_still_opens_modal_on_first_entity(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)
    fill(game)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/lore дракон")
        return isinstance(app.screen, LoreModal), highlighted(app)

    assert run(app, steps) == (True, 1)


# закрытие, ввод

def test_escape_closes_modal_and_returns_focus_to_input(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)
    fill(game)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/lore")
        await pilot.press("escape")
        await pilot.pause()
        return isinstance(app.screen, LoreModal), app.focused is app.query_one("#input")

    assert run(app, steps) == (False, True)


def test_close_button_closes_modal(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)
    fill(game)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/lore")
        await pilot.click("#modal-close")
        await pilot.pause()
        return isinstance(app.screen, LoreModal)

    assert run(app, steps) is False


def test_digit_in_modal_does_not_pick_a_turn(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)
    fill(game)
    game.bundle.session.offered_choices = ["Идти", "Ждать"]

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/lore")
        await pilot.press("1")
        await app.workers.wait_for_complete()
        await pilot.pause()
        return isinstance(app.screen, LoreModal), game.bundle.session.turn_seq

    assert run(app, steps) == (True, 0)


def test_lore_costs_no_turn_or_time(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)
    fill(game)
    now = game.bundle.world.clock.now_s

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/lore")
        await pilot.press("escape")
        await pilot.pause()

    run(app, steps)
    assert game.bundle.world.clock.now_s == now
    assert game.bundle.session.turn_seq == 0
    assert game.adapter.requests == []


def test_lore_can_be_opened_twice(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)
    fill(game)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/lore")
        await pilot.press("escape")
        await pilot.pause()
        await tui.submit(app, pilot, "/lore Гракх")
        return isinstance(app.screen, LoreModal), highlighted(app)

    assert run(app, steps) == (True, 2)


# клавиш нет

def test_no_key_binding_opens_the_journal():
    actions = [getattr(b, "action", "") for b in AiDmApp.BINDINGS]
    assert not [a for a in actions if "lore" in a]


def test_lore_modal_escape_binding():
    keys = {b.key: b.action for b in LoreModal.BINDINGS}
    assert keys == {"escape": "close"}


def test_lore_is_suggested_in_command_hints():
    from ai_dm.ui.tui.app import COMMAND_SUGGESTER

    assert "/lore" in COMMAND_SUGGESTER._suggestions
