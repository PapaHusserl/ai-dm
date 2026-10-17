# «Получено» после добычи с тел (docs/plan-custom-items.md, разд. 7, партия В).
#   Ход мастера с gold loot_individual при last_combat.gear: gains_lines -- строка на каждый стек
#   трофея с качеством в имени и приростом («Ржавый скимитар ×3»), деньги -- отдельной строкой;
#   блок gains шага PlaySession содержит те же строки; лог хода -- «Добыча: Ржавый скимитар x3».
from ui_kit import text_app, text_step

from ai_dm.game.scene import hero_of
from ai_dm.state.hero import InventoryEntry
from ai_dm.state.session import LastCombat
from ai_dm.ui.screen import gains_lines, loot_snapshot
from ai_dm.ui.session import PlaySession

LOOT = {
    "tool_calls": [{
        "id": "gl-1", "name": "gold",
        "input": {"type": "gold", "direction": "gain", "kind": "loot_individual"},
    }]
}


def loot_app(registry, tmp_path, gear=None):
    app = text_app(registry, tmp_path, [LOOT, text_step("Вы обыскиваете тела.")])
    if gear is None:
        gear = [
            InventoryEntry(item_id="scimitar", qty=3, cost_cp=250, quality="junk"),
            InventoryEntry(item_id="shortbow", qty=1, cost_cp=625, quality="worn"),
        ]
    app.bundle.session.last_combat = LastCombat(defeated=[], gear=gear)
    return app


def test_gains_lines_show_each_trophy_stack_with_quality(registry, tmp_path):
    app = loot_app(registry, tmp_path)
    before = loot_snapshot(app)
    app.handle("Обыскиваю тела")
    lines = gains_lines(app, before)
    assert "Ржавый скимитар ×3" in lines
    assert "Поношенный короткий лук ×1" in lines


def test_trophy_stack_in_the_hero_inventory_keeps_price_and_quality(registry, tmp_path):
    app = loot_app(registry, tmp_path)
    app.handle("Обыскиваю тела")
    stacks = [
        (e.cost_cp, e.quality, e.qty) for e in hero_of(app.bundle).inventory
        if e.item_id == "scimitar"
    ]
    assert (250, "junk", 3) in stacks


def test_second_look_gives_no_new_gains(registry, tmp_path):
    app = loot_app(registry, tmp_path)
    app.handle("Обыскиваю тела")
    assert gains_lines(app, loot_snapshot(app)) == []


def test_session_step_has_a_gains_block_with_trophies(registry, tmp_path):
    session = PlaySession(loot_app(registry, tmp_path))
    step = session.submit("Обыскиваю тела")
    gains = [b for b in step.blocks if b.kind == "gains"]
    assert len(gains) == 1
    assert "Ржавый скимитар ×3" in gains[0].items


def test_turn_log_names_the_trophies(registry, tmp_path):
    session = PlaySession(loot_app(registry, tmp_path))
    step = session.submit("Обыскиваю тела")
    texts = [b.text for b in step.blocks]
    assert any("Добыча: Ржавый скимитар x3" in text for text in texts)
