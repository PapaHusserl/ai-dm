# Сквозной сценарий партии В: бой -> обыск тел -> трофеи (docs/plan-custom-items.md, разд. 7).
# Тот же бой, что в сценарии этапа 2 (два гоблина-воина и главарь Гракх, победа героя), затем ход
# мастера с gold loot_individual (ScriptedAdapter-шаги дописываются в сценарий после боя).
#   * в инвентаре героя «ржавый скимитар» x2 по 250 мм (ПО 1/4, 10% SRD) и «Скимитар» главаря по
#     полной цене (Гракх -- лидер группы и ключевой NPC, босс) отдельным стеком;
#   * блок «Получено» показывает трофеи, /inv -- «Ржавый скимитар x2»;
#   * повторный обыск отклонён, инвентарь не меняется; gear_looted = True.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "game"))

from test_stage2_flow import victory_story  # noqa: E402

from ai_dm.game.scene import hero_of  # noqa: E402
from ai_dm.game.sheet_text import inv_lines  # noqa: E402
from ai_dm.rules.inventory import count_item  # noqa: E402
from ai_dm.ui.screen import gains_lines, loot_snapshot  # noqa: E402

LOOT = {
    "tool_calls": [{
        "id": "gl-1", "name": "gold",
        "input": {"type": "gold", "direction": "gain", "kind": "loot_individual"},
    }]
}
LOOT_AGAIN = {
    "tool_calls": [{
        "id": "gl-2", "name": "gold",
        "input": {"type": "gold", "direction": "gain", "kind": "loot_individual"},
    }]
}


def looted_story(registry, root):
    story = victory_story(registry, root)
    story.app.choose("average")
    story.adapter.first.steps.extend([LOOT, {"text": "Вы обыскиваете тела."}])
    before = loot_snapshot(story.app)
    story.app.handle("Обыскиваю тела гоблинов")
    return story, before


def stacks(story, item_id):
    hero = hero_of(story.bundle)
    return sorted((e.cost_cp, e.quality, e.qty) for e in hero.inventory if e.item_id == item_id)


def test_victory_leaves_unlooted_gear_for_the_master(registry, tmp_path):
    story = victory_story(registry, tmp_path)
    last = story.bundle.session.last_combat
    assert last.gear_looted is False
    assert sum(e.qty for e in last.gear if e.item_id == "scimitar") == 3


def test_loot_gives_junk_stack_by_the_goblin_price(registry, tmp_path):
    story, _ = looted_story(registry, tmp_path)
    assert (250, "junk", 2) in stacks(story, "scimitar")


def test_boss_weapon_is_a_separate_full_price_stack(registry, tmp_path):
    story, _ = looted_story(registry, tmp_path)
    assert (registry.get("weapon", "scimitar").cost_cp, None, 1) in stacks(story, "scimitar")


def test_gains_show_the_trophies(registry, tmp_path):
    story, before = looted_story(registry, tmp_path)
    assert "Ржавый скимитар ×2" in gains_lines(story.app, before, with_xp=False)


def test_inventory_lists_the_junk_stack_separately(registry, tmp_path):
    story, _ = looted_story(registry, tmp_path)
    lines = inv_lines(hero_of(story.bundle), registry, "0 мм")
    assert any("Ржавый скимитар x2" in line for line in lines)


def test_gear_is_marked_looted_and_money_is_given(registry, tmp_path):
    story, _ = looted_story(registry, tmp_path)
    last = story.bundle.session.last_combat
    assert (last.looted, last.gear_looted) == (True, True)
    assert hero_of(story.bundle).money_cp > 0


def test_second_loot_changes_nothing(registry, tmp_path):
    story, _ = looted_story(registry, tmp_path)
    count = count_item(hero_of(story.bundle), "scimitar")
    money = hero_of(story.bundle).money_cp
    story.adapter.first.steps.extend([LOOT_AGAIN, {"text": "Больше ничего."}])
    story.app.handle("Обыскиваю ещё раз")
    assert count_item(hero_of(story.bundle), "scimitar") == count
    assert hero_of(story.bundle).money_cp == money
