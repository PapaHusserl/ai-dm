# Живой прогон 1, п. 5: заклинания героя без механики в бою -- runner.inert_spells() (названия),
# в нумерацию вариантов боя не входят.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_game_grey_combat import grey_rig  # noqa: E402

SEED = 5


def test_inert_spells_empty_when_hero_knows_only_mechanical_spells(registry, cfg, tmp_path):
    rig = grey_rig(registry, cfg, tmp_path, SEED)
    assert rig.runner.inert_spells() == []


def test_inert_spells_lists_known_spell_without_battle_mechanics(registry, cfg, tmp_path):
    rig = grey_rig(registry, cfg, tmp_path, SEED)
    rig.runner.bundle.heroes[0].sheet.known_of().append("speak_with_animals")
    assert rig.runner.inert_spells() == [registry.get("spell", "speak_with_animals").name]


def test_inert_spells_have_no_duplicates(registry, cfg, tmp_path):
    rig = grey_rig(registry, cfg, tmp_path, SEED)
    sheet = rig.runner.bundle.heroes[0].sheet
    sheet.known_of().append("speak_with_animals")
    sheet.prepared_of().append("speak_with_animals")
    assert len(rig.runner.inert_spells()) == 1


def test_alarm_and_fog_cloud_are_no_longer_inert(registry, cfg, tmp_path):
    # К3 П3а: Тревога (utility) и Туманное облако (fog) получили боевой вид
    rig = grey_rig(registry, cfg, tmp_path, SEED)
    sheet = rig.runner.bundle.heroes[0].sheet
    sheet.known_of().extend(["alarm", "fog_cloud"])
    assert rig.runner.inert_spells() == []


def test_inert_spell_does_not_change_battle_options(registry, cfg, tmp_path):
    rig = grey_rig(registry, cfg, tmp_path, SEED)
    before = [o.id for o in rig.runner.preview_turn()]
    rig.runner.bundle.heroes[0].sheet.known_of().append("alarm")
    assert [o.id for o in rig.runner.preview_turn()] == before
