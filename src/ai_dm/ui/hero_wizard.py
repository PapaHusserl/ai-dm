from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime

from ai_dm.game.hero_create import propose_background
from ai_dm.game.hero_steps import (
    STEPS,
    WORDS,
    Draft,
    apply_put,
    background_summary_lines,
    clear_from,
    is_text_step,
    next_pos,
    step_done,
    step_for_code,
    step_index,
    step_options,
    to_sheet,
)
from ai_dm.master.session import TurnFailed
from ai_dm.protocol.context import BackgroundTask
from ai_dm.rules.builder import sheet_check
from ai_dm.ui.hero_session import (
    LEAVE,
    NO_SUCH,
    RETRY,
    HeroSession,
    RetryMenu,
    menu_number,
)
from ai_dm.ui.screen import Block, menu_block, note_block
from ai_dm.ui.session import Step

CREATE_HERO_STEPS = "Создать пошагово"
WIZARD_HINT = (
    "Собираем героя по шагам. Цифра — выбор, «назад» — шаг назад, «отмена» — выйти."
)
REVIEW_HINT = "«Вернуться к шагам» откатывает последний шаг: средства придётся ввести заново."
WIZARD_REVIEW_MENU = ("Принять героя", "Вернуться к шагам", "Править поля вручную")
BACK_TO_LIST = "Выбрать из списка"
AT_START = "Это первый шаг: назад некуда."
WORDS_HINT = (
    "Опишите предысторию словами: кем был герой, чем занимался. "
    "Мастер подберёт характеристики, навыки, инструмент, черту и снаряжение."
)
BACKGROUND_TITLE = "Предыстория принята:"
RETRY_STATES = ("error_menu", "model_choice")


@dataclass
class HeroWizard:
    # пошаговое создание героя без терминала: шаги STEPS, итог -- лист, который принимает
    # HeroSession (ревью, ручная правка); состояния step, words, error_menu, model_choice, review;
    # sheet -- None, пока не принят или при отмене
    deps: object
    task: object
    width: int
    draft: object = None
    pos: int = 0
    # снимки (pos, draft) перед каждым принятым значением: «назад»
    history: list = field(default_factory=list)
    state: str = "step"
    words: str = ""
    run_ids: list = field(default_factory=list)
    stamp: str = field(default_factory=lambda: f"{datetime.now(UTC):%Y%m%dT%H%M%S}")
    review: object = None
    retry: object = None

    def __post_init__(self):
        self.draft = Draft(taken_names=list(self.task.taken_names))
        self.review = HeroSession(
            self.deps, self.task, self.width, review_menu=WIZARD_REVIEW_MENU
        )
        self.retry = RetryMenu(self.deps, leave_label=BACK_TO_LIST)

    @property
    def sheet(self):
        return self.review.sheet

    def start(self):
        return Step([note_block(WIZARD_HINT)] + self.show().blocks)

    def show(self):
        step = STEPS[self.pos]
        registry = self.deps.registry
        title = step.label(self.draft, registry) if step.label else step.title
        if step.kind == "multi":
            done = len(getattr(self.draft, step.attr)) + 1
            title += f" ({done} из {step.count(self.draft, registry)})"
        options = step_options(self.draft, registry, self.pos)
        if not options:
            return Step([note_block(title + ":")])
        return Step([menu_block([o.label for o in options], title + ":")])

    def submit(self, line):
        if line is None:
            return Step(quit=True)
        line = line.strip()
        if line.lower() == "отмена":
            return self.cancel()
        if self.state == "review":
            return self.on_review(line)
        if self.state in RETRY_STATES:
            return self.on_retry(line)
        return self.on_input(line)

    def cancel(self):
        # в ручной правке «отмена» возвращает к ревью, иначе выход без героя
        if self.state == "review" and self.review.state == "edit":
            return self.review.edit("готово")
        return Step(quit=True)

    def on_review(self, line):
        if line == "2" and self.review.state == "review":
            return self.back()
        return self.review.submit(line)

    def on_retry(self, line):
        if line.lower() == "назад":
            self.state = "step"
            return self.show()
        number = menu_number(line, self.retry.menu)
        if number is None:
            return Step([note_block(NO_SUCH)])
        result = self.retry.choose(number)
        if result is RETRY:
            return self.call_background()
        if result is LEAVE:
            self.state = "step"
            return self.show()
        self.state = self.retry.state
        return result

    def on_input(self, line):
        if line.lower() == "назад":
            return self.back()
        if self.state == "words":
            return self.background_call(line)
        return self.pick(line)

    def pick(self, line):
        if is_text_step(self.draft, self.pos):
            return self.accept(line) if line else self.show()
        options = step_options(self.draft, self.deps.registry, self.pos)
        number = menu_number(line, options)
        if number is None:
            return Step([note_block(NO_SUCH)])
        value = options[number - 1].value
        if value == WORDS:
            self.state = "words"
            return Step([note_block(WORDS_HINT)])
        return self.accept(value)

    def accept(self, value):
        before = (self.pos, deepcopy(self.draft))
        error = apply_put(self.draft, self.deps.registry, self.pos, value)
        if error is not None:
            return self.reject(error)
        self.history.append(before)
        return self.advance()

    def reject(self, error):
        target = STEPS[self.pos].on_error
        if target:
            self.jump(target)
        return Step([note_block(error)] + self.show().blocks)

    def jump(self, key):
        # вернуться к шагу key (или первому применимому после него), сбросив его и следующие
        clear_from(self.draft, key)
        self.pos = next_pos(self.draft, self.deps.registry, step_index(key))
        while self.history and self.history[-1][0] >= self.pos:
            self.history.pop()

    def advance(self):
        registry = self.deps.registry
        if step_done(self.draft, registry, self.pos):
            self.pos = next_pos(self.draft, registry, self.pos + 1)
        if self.pos == len(STEPS):
            return self.finish()
        return self.show()

    def back(self):
        if self.state == "words":
            self.state = "step"
            return self.show()
        if not self.history:
            return Step([note_block(AT_START)])
        self.state = "step"
        self.pos, self.draft = self.history.pop()
        return self.show()

    def background_call(self, text):
        if not text:
            return Step([note_block(WORDS_HINT)])
        self.words = text
        return self.call_background()

    def call_background(self):
        run_id = f"hero-{self.stamp}-{len(self.run_ids) + 1}"
        self.run_ids.append(run_id)
        task = BackgroundTask(self.draft.class_id)
        try:
            spec = propose_background(self.deps, task, self.words, run_id)
        except TurnFailed as failure:
            self.state = "error_menu"
            return self.retry.fail(failure)
        self.history.append((self.pos, deepcopy(self.draft)))
        self.draft.background = spec
        self.state = "step"
        lines = background_summary_lines(spec, self.deps.registry)
        blocks = [note_block(BACKGROUND_TITLE), Block("raw", items=tuple(lines))]
        return Step(blocks + self.advance().blocks)

    def finish(self):
        registry = self.deps.registry
        sheet = to_sheet(self.draft, registry)
        codes, messages = sheet_check(
            sheet, registry, known=self.task.known, taken_names=self.task.taken_names
        )
        if codes:
            self.jump(step_for_code(codes[0]))
            return Step([note_block("; ".join(messages))] + self.show().blocks)
        self.state = "review"
        self.review.proposal = sheet
        step = self.review.review()
        return Step([note_block(REVIEW_HINT)] + step.blocks)
