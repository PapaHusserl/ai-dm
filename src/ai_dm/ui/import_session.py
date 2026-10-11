from dataclasses import dataclass, field
from datetime import UTC, datetime

from ai_dm.game.pack_import import run_import
from ai_dm.master.session import TurnFailed
from ai_dm.ui.hero_session import LEAVE, NO_SUCH, RETRY, RetryMenu, menu_number
from ai_dm.ui.screen import note_block
from ai_dm.ui.session import Step

IMPORT_DONE = "Пак собран."


@dataclass
class ImportSession:
    # import пака без терминала: прогон модели, при сбое -- меню 2.2 (повторить, сменить модель,
    # выйти); state -- run, error_menu или model_choice; итог -- ctx (None при выходе)
    deps: object
    task: object
    text: str
    folder: object
    state: str = "run"
    run_ids: list = field(default_factory=list)
    stamp: str = field(default_factory=lambda: f"{datetime.now(UTC):%Y%m%dT%H%M%S}")
    retry: object = None
    ctx: object = None

    def __post_init__(self):
        self.retry = RetryMenu(self.deps)

    def start(self):
        return self.attempt()

    def attempt(self):
        run_id = f"import-{self.stamp}-{len(self.run_ids) + 1}"
        self.run_ids.append(run_id)
        try:
            self.ctx = run_import(self.deps, self.task, self.text, run_id, self.folder)
        except TurnFailed as failure:
            self.state = "error_menu"
            return self.retry.fail(failure)
        return Step([note_block(IMPORT_DONE)], quit=True)

    def submit(self, line):
        if line is None:
            return Step(quit=True)
        number = menu_number(line.strip(), self.retry.menu)
        if number is None:
            return Step([note_block(NO_SUCH)])
        result = self.retry.choose(number)
        if result is RETRY:
            return self.attempt()
        if result is LEAVE:
            return Step(quit=True)
        self.state = self.retry.state
        return result
