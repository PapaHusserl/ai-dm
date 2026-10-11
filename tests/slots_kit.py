# Общие помощники тестов, которых больше нет в production (AD1, решение 1а): list_slots,
# ScriptedInput, WORLD_TEXT. tests/ попадает в sys.path через tests/conftest.py.
from ai_dm.game.starter import VALE_DIR
from ai_dm.persistence.layout import slots_dir, visible_dirs
from ai_dm.persistence.store import load_slot, recover_slots

WORLD_TEXT = (VALE_DIR / "world.md").read_text(encoding="utf-8").strip()


def list_slots(root, world_id):
    # имена слотов мира (скрытые .tmp-*/.old-* не показываются), как прежний store.list_slots
    recover_slots(root, world_id)
    slots = slots_dir(root, world_id)
    if not slots.is_dir():
        return []
    return sorted(p.name for p in visible_dirs(slots))


class ScriptedInput:
    # ввод из списка строк; кончились -- None
    def __init__(self, lines):
        self.remaining = list(lines)

    def read(self, prompt=""):
        if not self.remaining:
            return None
        return self.remaining.pop(0)


def saved_close_reason(root, world_id):
    # причина закрытия сцены в автосейве границы (он хранит закрытую сцену); нет автосейва -- None
    if "auto" not in list_slots(root, world_id):
        return None
    return load_slot(root, world_id, "auto").session.current_scene.closed_reason
