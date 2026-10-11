from ai_dm.ui.session import PlaySession
from ai_dm.ui.tui import strings
from ai_dm.ui.tui.app import AiDmApp
from ai_dm.ui.tui.create import HeroCreateApp
from ai_dm.ui.tui.modals import PickerApp

__all__ = ["AiDmApp", "TuiStartError", "create_hero", "pick", "run_tui"]


class TuiStartError(Exception):
    # ошибка до первого кадра: cli уходит в простой режим
    pass


def run_tui(game, notes=(), replay=False, secrets=(), opening=None):
    session = PlaySession(game, replay=replay, secrets=secrets, opening=opening)
    app = AiDmApp(session, notes)
    try:
        app.run()
    except Exception as error:
        if not app.shown:
            raise TuiStartError(str(error)) from error
        raise
    finally:
        game.audio.stop()
    return app.after_exit()


def pick(title, names, splash=False):
    # экран выбора пункта до игры: номер с 1 или None (отмена); ошибка запуска -- TuiStartError
    picker = PickerApp(title, names, splash)
    try:
        return picker.run()
    except Exception as error:
        raise TuiStartError(str(error)) from error


def create_hero(session, placeholder=strings.CREATE_PLACEHOLDER):
    # экран создания героя на лету до игры: HeroSheet или None (отмена); сбой -- TuiStartError
    app = HeroCreateApp(session, placeholder)
    try:
        return app.run()
    except Exception as error:
        if not app.shown:
            raise TuiStartError(str(error)) from error
        raise
