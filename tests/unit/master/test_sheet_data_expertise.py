# К2 П1: экспертиза героя видна рассказчику полем expertise в sheet_data (умение с эффектом скрыто).
from master_kit import app_cfg

from ai_dm.devtools.grid_heroes import build_hero
from ai_dm.master.prompt import PromptBuilder


def sheet_data(class_id, registry):
    return PromptBuilder(app_cfg()).sheet_data(build_hero(class_id, 1, registry), registry)


def test_rogue_with_expertise_has_the_field(registry):
    assert sheet_data("rogue", registry)["expertise"] == ["stealth", "perception"]


def test_fighter_has_no_expertise_field(registry):
    assert "expertise" not in sheet_data("fighter", registry)
