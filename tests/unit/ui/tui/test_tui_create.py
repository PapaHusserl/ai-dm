# Б1б (B1-PLAN, A6, «Тесты Б1б»): HeroCreateApp -- создание героя на лету экраном TUI до игры.
# Ожидаемый API: ai_dm.ui.tui.create.HeroCreateApp(session: HeroSession); виджеты #feed #choices
# #input #status; описание/цифра/текст -> session.submit в thread-worker (#input disabled, в
# #status «Мастер думает…»); App.return_value -- HeroSheet | None; Esc / Ctrl+C -- отмена.
# Pilot через asyncio.run, без сна; барьер GateAdapter держит вызов модели. Живых вызовов нет.
import asyncio
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "game"))

from hero_kit import deps, sheet_call, sheet_task, vale_pack  # noqa: E402
from master_kit import tools_step  # noqa: E402

from ai_dm.game.turn import REFUSAL_HINT  # noqa: E402
from ai_dm.llm.mock import ScriptedAdapter  # noqa: E402
from ai_dm.rules.builder import HeroSheet  # noqa: E402
from ai_dm.ui.hero_session import HeroSession  # noqa: E402
from ai_dm.ui.tui import strings  # noqa: E402
from ai_dm.ui.tui.create import HeroCreateApp  # noqa: E402

DESCRIPTION = "воин-сирота ищет сестру"


class GateAdapter(ScriptedAdapter):
    # барьер: первый вызов модели сообщает «вошёл» и ждёт release (с потолком, чтобы тест не завис)
    def __init__(self, steps):
        super().__init__(steps)
        self.entered = threading.Event()
        self.release = threading.Event()

    def complete(self, req):
        self.entered.set()
        assert self.release.wait(10)
        return super().complete(req)


def run(app, steps, size=(140, 40)):
    async def scenario():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            return await steps(app, pilot)

    return asyncio.run(scenario())


def create_app(registry, cfg, tmp_path, steps=None, adapter=None):
    if adapter is None:
        adapter = ScriptedAdapter([tools_step(sheet_call())] if steps is None else steps)
    hero_deps = deps(adapter, registry, cfg, tmp_path)
    session = HeroSession(hero_deps, sheet_task(vale_pack(registry)), 80)
    return HeroCreateApp(session)


async def submit(tui, app, pilot, line):
    app.query_one("#input").value = line
    await pilot.press("enter")
    await app.workers.wait_for_complete()
    await pilot.pause()


def feed(tui, app):
    return tui.flat(tui.text_of(app.query_one("#feed")))


def choices(tui, app):
    return tui.flat(tui.text_of(app.query_one("#choices")))


# старт

def test_start_shows_describe_hint_in_feed(registry, cfg, tmp_path, tui):
    app = create_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        return feed(tui, app)

    assert "Опишите героя" in run(app, steps)


def test_start_input_is_enabled_and_no_menu(registry, cfg, tmp_path, tui):
    app = create_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        return app.query_one("#input").disabled, choices(tui, app)

    disabled, menu = run(app, steps)
    assert disabled is False
    assert "Принять" not in menu


# описание: ход идёт

def test_input_is_disabled_and_status_says_thinking_while_model_works(
    registry, cfg, tmp_path, tui
):
    gate = GateAdapter([tools_step(sheet_call())])
    app = create_app(registry, cfg, tmp_path, adapter=gate)

    async def steps(app, pilot):
        entry = app.query_one("#input")
        entry.value = DESCRIPTION
        await pilot.press("enter")
        await asyncio.to_thread(gate.entered.wait, 10)
        await pilot.pause()
        busy = entry.disabled, strings.THINKING in tui.text_of(app.query_one("#status"))
        gate.release.set()
        await app.workers.wait_for_complete()
        await pilot.pause()
        return busy, entry.disabled, strings.THINKING in tui.text_of(app.query_one("#status"))

    busy, disabled, thinking = run(app, steps)
    assert busy == (True, True)
    assert disabled is False
    assert thinking is False


def test_sheet_and_review_menu_appear_after_the_answer(registry, cfg, tmp_path, tui):
    app = create_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        await submit(tui, app, pilot, DESCRIPTION)
        return feed(tui, app), choices(tui, app)

    text, menu = run(app, steps)
    assert "Борин" in text
    assert "Мотив: Найти сестру." in text
    assert "1. Принять героя" in menu
    assert "3. Править поля вручную" in menu


def test_describe_text_is_echoed_in_feed(registry, cfg, tmp_path, tui):
    app = create_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        await submit(tui, app, pilot, DESCRIPTION)
        return feed(tui, app)

    assert DESCRIPTION in run(app, steps)


# принять и отмена

def test_accept_by_typed_digit_returns_the_sheet(registry, cfg, tmp_path, tui):
    app = create_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        await submit(tui, app, pilot, DESCRIPTION)
        await submit(tui, app, pilot, "1")

    run(app, steps)
    assert isinstance(app.return_value, HeroSheet)
    assert app.return_value.choices.name == "Борин"


def test_accept_by_digit_key_returns_the_sheet(registry, cfg, tmp_path, tui):
    app = create_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        await submit(tui, app, pilot, DESCRIPTION)
        await pilot.press("1")
        await app.workers.wait_for_complete()
        await pilot.pause()

    run(app, steps)
    assert isinstance(app.return_value, HeroSheet)


def test_manual_edit_in_tui_returns_edited_sheet(registry, cfg, tmp_path, tui):
    app = create_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        await submit(tui, app, pilot, DESCRIPTION)
        for line in ("3", "name = Ило", "готово", "1"):
            await submit(tui, app, pilot, line)

    run(app, steps)
    assert app.return_value.choices.name == "Ило"


def test_edit_defect_is_shown_in_feed(registry, cfg, tmp_path, tui):
    from ai_dm.rules.builder import SKILL_CONFLICT_MESSAGE

    app = create_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        await submit(tui, app, pilot, DESCRIPTION)
        await submit(tui, app, pilot, "3")
        await submit(tui, app, pilot, "class_skills = perception, acrobatics")
        return feed(tui, app)

    assert tui.flat(SKILL_CONFLICT_MESSAGE) in run(app, steps)


def test_escape_at_start_returns_none(registry, cfg, tmp_path, tui):
    app = create_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        await pilot.press("escape")
        await pilot.pause()

    run(app, steps)
    assert app.return_value is None


def test_ctrl_c_at_start_returns_none(registry, cfg, tmp_path, tui):
    app = create_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        await pilot.press("ctrl+c")
        await pilot.pause()

    run(app, steps)
    assert app.return_value is None


def test_escape_at_review_returns_none_not_the_sheet(registry, cfg, tmp_path, tui):
    app = create_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        await submit(tui, app, pilot, DESCRIPTION)
        await pilot.press("escape")
        await pilot.pause()

    run(app, steps)
    assert app.return_value is None


# сбой: меню 2.2

def test_refusal_shows_hint_and_error_menu(registry, cfg, tmp_path, tui):
    app = create_app(registry, cfg, tmp_path, steps=[{"stop": "refusal"}])

    async def steps(app, pilot):
        await submit(tui, app, pilot, DESCRIPTION)
        return feed(tui, app), choices(tui, app)

    text, menu = run(app, steps)
    assert tui.flat(REFUSAL_HINT) in text
    assert "1. Повторить" in menu
    assert "3. Выйти" in menu


def test_error_menu_retry_leads_to_review(registry, cfg, tmp_path, tui):
    app = create_app(registry, cfg, tmp_path, steps=[{"stop": "refusal"}, tools_step(sheet_call())])

    async def steps(app, pilot):
        await submit(tui, app, pilot, DESCRIPTION)
        await submit(tui, app, pilot, "1")
        return choices(tui, app)

    assert "Принять героя" in run(app, steps)


def test_error_menu_quit_returns_none(registry, cfg, tmp_path, tui):
    app = create_app(registry, cfg, tmp_path, steps=[{"stop": "refusal"}])

    async def steps(app, pilot):
        await submit(tui, app, pilot, DESCRIPTION)
        await submit(tui, app, pilot, "3")

    run(app, steps)
    assert app.return_value is None


# русский

def test_no_latin_in_create_screen_after_start_and_answer(registry, cfg, tmp_path, tui):
    app = create_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        start = tui.visible_text(app)
        await submit(tui, app, pilot, DESCRIPTION)
        return start, tui.visible_text(app)

    start, after = run(app, steps)
    assert "Принять героя" in after
    # «Esc» в подсказке поля -- название клавиши, как F2 и ^q в белом списке A7
    assert [w for w in tui.latin_words(start) if w != "Esc"] == []
    # id триггера «o1» из листа -- данные героя, не строка интерфейса; «x8» -- количество в строке
    # инвентаря (набор воина A: метательные копья ×8, К2)
    assert [w for w in tui.latin_words(after) if w not in ("Esc", "o", "x")] == []


# цифра при непустом поле ввода уходит в поле, а не выбирает пункт меню

def test_digit_key_with_text_in_input_goes_to_the_field_not_to_menu(registry, cfg, tmp_path, tui):
    app = create_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        await submit(tui, app, pilot, DESCRIPTION)
        entry = app.query_one("#input")
        entry.value = "замечание "
        await pilot.press("1")
        await pilot.pause()
        return entry.value, app.return_value, choices(tui, app)

    value, result, menu = run(app, steps)
    assert sorted(value) == sorted("замечание 1")
    assert result is None
    assert "Принять героя" in menu


def test_digit_key_with_empty_input_still_picks_menu_item(registry, cfg, tmp_path, tui):
    app = create_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        await submit(tui, app, pilot, DESCRIPTION)
        assert app.query_one("#input").value == ""
        await pilot.press("1")
        await app.workers.wait_for_complete()
        await pilot.pause()

    run(app, steps)
    assert isinstance(app.return_value, HeroSheet)


# Б2б: HeroCreateApp(HeroWizard, placeholder=STEPS_PLACEHOLDER) -- пошаговое создание, заставка

def steps_app(registry, cfg, tmp_path, steps=None, adapter=None):
    from ai_dm.ui.hero_wizard import HeroWizard

    if adapter is None:
        adapter = ScriptedAdapter([] if steps is None else steps)
    wizard = HeroWizard(deps(adapter, registry, cfg, tmp_path), sheet_task(vale_pack(registry)), 80)
    return HeroCreateApp(wizard, placeholder=strings.STEPS_PLACEHOLDER)


def title_rows():
    from ai_dm.art import art_for_event

    return [line.rstrip() for line in art_for_event("title").splitlines() if line.strip()]


def feed_lines(tui, app):
    return [strip.text.rstrip() for strip in app.query_one("#feed").lines]


def test_steps_start_shows_title_art_in_feed(registry, cfg, tmp_path, tui):
    app = steps_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        return feed_lines(tui, app)

    lines = run(app, steps)
    assert len(title_rows()) == 16
    assert [row for row in title_rows() if row not in lines] == []


def test_steps_title_art_comes_before_the_hint(registry, cfg, tmp_path, tui):
    from ai_dm.ui.hero_wizard import WIZARD_HINT

    app = steps_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        return feed(tui, app)

    text = run(app, steps)
    assert tui.flat(WIZARD_HINT) in text
    assert text.index(tui.flat(title_rows()[0])) < text.index(tui.flat(WIZARD_HINT))


def test_describe_app_has_title_art_in_feed_too(registry, cfg, tmp_path, tui):
    app = create_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        return feed_lines(tui, app)

    lines = run(app, steps)
    assert [row for row in title_rows() if row not in lines] == []


def test_steps_start_shows_species_menu(registry, cfg, tmp_path, tui):
    from ai_dm.rules import hero_options as opts

    app = steps_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        return choices(tui, app), list(app.query_one("#choices").items)

    text, items = run(app, steps)
    assert "1. " in text
    assert len(items) == len(opts.species_options(registry))


def test_steps_placeholder_is_shown_in_input_and_is_russian(registry, cfg, tmp_path, tui):
    app = steps_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        return app.query_one("#input").placeholder

    placeholder = run(app, steps)
    assert placeholder == strings.STEPS_PLACEHOLDER
    assert "«назад»" in placeholder
    assert [w for w in tui.latin_words(placeholder) if w != "Esc"] == []


def test_default_placeholder_is_create_placeholder(registry, cfg, tmp_path, tui):
    app = create_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        return app.query_one("#input").placeholder

    assert run(app, steps) == strings.CREATE_PLACEHOLDER


def test_digit_one_with_empty_input_goes_to_next_step(registry, cfg, tmp_path, tui):
    app = steps_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        before = choices(tui, app)
        await pilot.press("1")
        await app.workers.wait_for_complete()
        await pilot.pause()
        return before, choices(tui, app), app.session.pos

    before, after, pos = run(app, steps)
    assert pos == 1
    assert after != before


def test_typed_digit_goes_to_next_step(registry, cfg, tmp_path, tui):
    app = steps_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        await submit(tui, app, pilot, "1")
        return app.session.pos

    assert run(app, steps) == 1


def test_back_word_returns_to_previous_menu(registry, cfg, tmp_path, tui):
    app = steps_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        first = list(app.query_one("#choices").items)
        await submit(tui, app, pilot, "1")
        await submit(tui, app, pilot, "назад")
        return first, list(app.query_one("#choices").items), app.session.pos

    first, again, pos = run(app, steps)
    assert pos == 0
    assert again == first


def test_back_at_first_step_says_nowhere_to_go(registry, cfg, tmp_path, tui):
    from ai_dm.ui.hero_wizard import AT_START

    app = steps_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        await submit(tui, app, pilot, "назад")
        return feed(tui, app)

    assert tui.flat(AT_START) in run(app, steps)


def test_name_typed_as_text_is_accepted(registry, cfg, tmp_path, tui):
    from hero_kit import wizard_script

    script = wizard_script()
    app = steps_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        for key, line in script:
            if key == "name":
                break
            await submit(tui, app, pilot, line)
        await submit(tui, app, pilot, "Ило")
        return app.session.draft.name

    assert run(app, steps) == "Ило"


def test_escape_in_steps_returns_none(registry, cfg, tmp_path, tui):
    app = steps_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        await submit(tui, app, pilot, "1")
        await pilot.press("escape")
        await pilot.pause()

    run(app, steps)
    assert app.return_value is None


def test_cancel_word_in_steps_returns_none(registry, cfg, tmp_path, tui):
    app = steps_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        await submit(tui, app, pilot, "отмена")

    run(app, steps)
    assert app.return_value is None


def test_full_picks_then_accept_returns_hero_sheet(registry, cfg, tmp_path, tui):
    from hero_kit import wizard_picks, wizard_sheet

    app = steps_app(registry, cfg, tmp_path)

    async def steps(app, pilot):
        for line in wizard_picks():
            await submit(tui, app, pilot, line)
        review = choices(tui, app)
        await submit(tui, app, pilot, "1")
        return review

    review = run(app, steps)
    assert "1. Принять героя" in review
    assert isinstance(app.return_value, HeroSheet)
    assert app.return_value == wizard_sheet()


def test_words_step_blocks_input_and_shows_thinking_then_raw_background(
    registry, cfg, tmp_path, tui
):
    WORDS = "акробат из бродячего цирка"
    spec = {
        "type": "background_spec", "name": "Бывший цирковой акробат",
        "abilities": ["dex", "con", "cha"], "skills": ["acrobatics", "performance"],
        "tool": "thieves_tools", "feat": "alert", "equipment": ["crowbar"], "gold_cp": 1000,
        "description": "Вырос в цирке.",
    }

    from ai_dm.game.hero_steps import WORDS_LABEL

    gate = GateAdapter([tools_step({"id": "bg-1", "name": "background_spec", "input": spec})])
    app = steps_app(registry, cfg, tmp_path, adapter=gate)

    async def steps(app, pilot):
        await submit(tui, app, pilot, "1")
        await submit(tui, app, pilot, "1")
        items = app.query_one("#choices").items
        number = next(i for i, item in enumerate(items, 1) if WORDS_LABEL in item)
        await submit(tui, app, pilot, str(number))
        entry = app.query_one("#input")
        entry.value = WORDS
        await pilot.press("enter")
        await asyncio.to_thread(gate.entered.wait, 10)
        await pilot.pause()
        busy = entry.disabled, strings.THINKING in tui.text_of(app.query_one("#status"))
        gate.release.set()
        await app.workers.wait_for_complete()
        await pilot.pause()
        return busy, entry.disabled, feed(tui, app)

    busy, disabled, text = run(app, steps)
    assert busy == (True, True)
    assert disabled is False
    assert "Бывший цирковой акробат" in text
