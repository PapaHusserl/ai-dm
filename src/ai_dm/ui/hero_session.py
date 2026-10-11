from dataclasses import dataclass, field
from datetime import UTC, datetime

from ai_dm.game.app import check_model, model_options
from ai_dm.game.hero_create import (
    edit_sheet,
    preview_lines,
    propose_hero_sheet,
    sheet_fields_lines,
)
from ai_dm.game.turn import REFUSAL_HINT
from ai_dm.master.session import TurnFailed
from ai_dm.protocol.handlers.hero import request_from_sheet
from ai_dm.rules.builder import sheet_check
from ai_dm.ui.screen import Block, menu_block, note_block
from ai_dm.ui.session import Step

CREATE_HERO = "Создать героя на лету"
DESCRIBE_HINT = (
    "Опишите героя словами: кто он, чем занимался, чего хочет. Мастер соберёт лист героя."
)
SHEET_TITLE = "Лист героя:"
REVIEW_TITLE = "Что делаем с героем?"
REVIEW_MENU = ["Принять героя", "Переописать с замечанием", "Править поля вручную"]
REMARK_HINT = "Что изменить? Напишите замечание, остальное мастер оставит как есть."
EDIT_HINT = "Правка: «поле = значение». «поля» — список полей, «готово» — вернуться к листу."
EDIT_DONE = "Принято."
ACCEPTED = "Герой принят: {name}."
ERROR_TITLE = "Выбери:"
ERROR_MENU = ["Повторить", "Сменить модель", "Выйти"]
MODEL_TITLE = "Модель рассказчика:"
MODEL_CHANGED = "Модель рассказчика: {key}."
NO_SUCH = "Нет такого варианта."
RETRY = object()
LEAVE = object()


def menu_number(line, menu):
    # номер пункта меню с 1 или None
    if not line.isdigit() or not 1 <= int(line) <= len(menu):
        return None
    return int(line)


@dataclass
class RetryMenu:
    # меню 2.2 после сбоя ИИ: повторить, сменить модель, выйти (или иной выход); state --
    # error_menu или model_choice
    deps: object
    leave_label: str = ERROR_MENU[2]
    state: str = "error_menu"

    @property
    def menu(self):
        if self.state == "model_choice":
            return model_options(self.deps.app_cfg)
        return ERROR_MENU[:2] + [self.leave_label]

    def fail(self, failure):
        self.state = "error_menu"
        hint = REFUSAL_HINT if failure.reason == "refusal" else str(failure)
        return Step([note_block(hint), menu_block(self.menu, ERROR_TITLE)])

    def choose(self, number):
        if self.state == "model_choice":
            return self.choose_model(self.menu[number - 1])
        if number == 1:
            return RETRY
        if number == 2:
            self.state = "model_choice"
            return Step([menu_block(self.menu, MODEL_TITLE)])
        return LEAVE

    def choose_model(self, key):
        deps = self.deps
        provider, _, model = key.partition(":")
        adapter, error = check_model(deps.app_cfg, deps.adapter_factory, provider, model)
        self.state = "error_menu"
        if error is None:
            deps.adapter = adapter
            deps.model = model
            error = MODEL_CHANGED.format(key=key)
        return Step([note_block(error), menu_block(self.menu, ERROR_TITLE)])


@dataclass
class HeroSession:
    # создание героя на лету без терминала: состояния describe, review, remark, edit,
    # error_menu, model_choice; итог -- sheet (None, пока не принят или при выходе)
    deps: object
    task: object
    width: int
    sheet: object = None
    state: str = "describe"
    description: str = ""
    # лист, показанный на проверку
    proposal: object = None
    run_ids: list = field(default_factory=list)
    stamp: str = field(default_factory=lambda: f"{datetime.now(UTC):%Y%m%dT%H%M%S}")
    # пункты меню ревью; у пошагового пути -- свои (WIZARD_REVIEW_MENU)
    review_menu: tuple = tuple(REVIEW_MENU)
    retry: object = None

    def __post_init__(self):
        self.retry = RetryMenu(self.deps)

    def start(self):
        return Step([note_block(DESCRIBE_HINT)])

    def submit(self, line):
        if line is None:
            return Step(quit=True)
        line = line.strip()
        if self.state in ("review", "error_menu", "model_choice"):
            return self.choose(line)
        if self.state == "edit":
            return self.edit(line)
        if not line:
            return Step([note_block(DESCRIBE_HINT if self.state == "describe" else REMARK_HINT)])
        if self.state == "describe":
            self.description = line
        else:
            self.task.feedback = line
            self.task.previous = request_from_sheet(self.proposal)
        return self.propose()

    def propose(self):
        run_id = f"hero-{self.stamp}-{len(self.run_ids) + 1}"
        self.run_ids.append(run_id)
        try:
            self.proposal = propose_hero_sheet(self.deps, self.task, self.description, run_id)
        except TurnFailed as failure:
            self.state = "error_menu"
            return self.retry.fail(failure)
        return self.review()

    def review(self):
        self.state = "review"
        lines = preview_lines(self.proposal, self.deps.registry, self.width)
        return Step([
            note_block(SHEET_TITLE), Block("raw", items=tuple(lines)),
            menu_block(self.review_menu, REVIEW_TITLE),
        ])

    def choose(self, line):
        menu = self.review_menu if self.state == "review" else self.retry.menu
        number = menu_number(line, menu)
        if number is None:
            return Step([note_block(NO_SUCH)])
        if self.state == "review":
            return self.choose_review(number)
        result = self.retry.choose(number)
        if result is RETRY:
            return self.propose()
        if result is LEAVE:
            return Step(quit=True)
        self.state = self.retry.state
        return result

    def choose_review(self, number):
        if number == 1:
            self.sheet = self.proposal
            return Step([note_block(ACCEPTED.format(name=self.sheet.choices.name))], quit=True)
        if number == 2:
            self.state = "remark"
            return Step([note_block(REMARK_HINT)])
        self.state = "edit"
        return Step([note_block(EDIT_HINT)])

    def edit(self, line):
        if line.lower() == "готово":
            return self.review()
        if line.lower() == "поля":
            return Step([Block("raw", items=tuple(sheet_fields_lines(self.proposal)))])
        edited = edit_sheet(self.proposal, line)
        if isinstance(edited, str):
            return Step([note_block(edited)])
        codes, messages = sheet_check(
            edited, self.deps.registry, known=self.task.known, taken_names=self.task.taken_names
        )
        if codes:
            return Step([note_block("; ".join(messages))])
        self.proposal = edited
        return Step([note_block(EDIT_DONE)])
