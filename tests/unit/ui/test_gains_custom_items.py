# «Получено» и лента при give_custom_item (CUSTOM-ITEMS-PLAN, разд. 3, партия Б).
#   gains_lines(app, loot_snapshot) после хода, где мастер выдал сюжетный предмет: «Ржавый ключ ×1»
#   (имя через реестр мира -- app.registry с наложением, не базовый);
#   TUI (панель #gains) -- в tui/test_tui_custom_items.py; простой режим: лента с названием предмета
#   (там «Получено» -- только опыт, предмет идёт строкой лога хода); квестовый и обычный предмет --
#   одинаково; повторная выдача того же предмета -- прирост на выданное количество.
from ui_kit import text_app, text_step

from ai_dm.game.scene import hero_of
from ai_dm.rules.inventory import remove_item
from ai_dm.ui.screen import gains_lines, loot_snapshot
from ai_dm.ui.session import PlaySession


def give_step(call_id="gc-1", name="Ржавый ключ", **fields):
    data = {
        "type": "give_custom_item", "name": name, "description": "Ключ от ворот", "qty": 1,
        "weight_lb": 0, "cost_cp": 0, "quest": True,
    }
    data.update(fields)
    return {"tool_calls": [{"id": call_id, "name": "give_custom_item", "input": data}]}


def key_app(registry, tmp_path, **fields):
    return text_app(registry, tmp_path, [give_step(**fields), text_step("Вам вручают ключ.")])


def test_gains_lines_show_the_new_custom_item(registry, tmp_path):
    app = key_app(registry, tmp_path)
    before = loot_snapshot(app)
    app.handle("Беру ключ")
    assert gains_lines(app, before) == ["Ржавый ключ ×1"]


def test_gains_lines_show_a_plain_custom_item(registry, tmp_path):
    app = key_app(registry, tmp_path, name="Тряпичная кукла", quest=False)
    before = loot_snapshot(app)
    app.handle("Беру куклу")
    assert gains_lines(app, before) == ["Тряпичная кукла ×1"]


def test_gains_lines_show_the_given_quantity(registry, tmp_path):
    app = key_app(registry, tmp_path, name="Факел", quest=False, qty=3)
    before = loot_snapshot(app)
    app.handle("Беру факелы")
    assert gains_lines(app, before) == ["Факел ×3"]


def test_gains_lines_are_empty_when_the_item_was_already_there(registry, tmp_path):
    app = key_app(registry, tmp_path)
    app.handle("Беру ключ")
    assert gains_lines(app, loot_snapshot(app)) == []


def test_removed_custom_item_is_not_a_gain(registry, tmp_path):
    app = key_app(registry, tmp_path)
    app.handle("Беру ключ")
    hero = hero_of(app.bundle)
    before = loot_snapshot(app)
    remove_item(hero, "custom_1")
    assert gains_lines(app, before) == []


def test_session_step_has_a_gains_block_with_the_item(registry, tmp_path):
    session = PlaySession(key_app(registry, tmp_path))
    step = session.submit("Беру ключ")
    gains = [b for b in step.blocks if b.kind == "gains"]
    assert len(gains) == 1
    assert "Ржавый ключ ×1" in gains[0].items


def test_simple_mode_has_a_gains_note_with_the_item(registry, tmp_path):
    from ui_kit import play

    out = play(key_app(registry, tmp_path), ["Беру ключ"])
    assert any("Получено: Ржавый ключ ×1" in line for line in out.lines)


def test_simple_gains_text_joins_items_with_a_comma():
    from ai_dm.ui.screen import Block
    from ai_dm.ui.simple import gains_lines_text

    block = Block("gains", items=("Ржавый ключ ×1", "Деньги: +5 зм"))
    text = " ".join(gains_lines_text(block, 80))
    assert "Получено: Ржавый ключ ×1, Деньги: +5 зм" in text


def test_simple_gains_text_keeps_xp_line_and_adds_items_note():
    from ai_dm.ui.screen import Block
    from ai_dm.ui.simple import gains_lines_text

    block = Block("gains", text="Получено опыта: 75", items=("Ржавый ключ ×1",))
    lines = gains_lines_text(block, 80)
    assert len(lines) == 2
    assert "Получено опыта: 75" in lines[0]
    assert "Получено: Ржавый ключ ×1" in lines[1]


def test_simple_gains_text_xp_only_has_no_items_note():
    from ai_dm.ui.screen import Block
    from ai_dm.ui.simple import gains_lines_text

    lines = gains_lines_text(Block("gains", text="Получено опыта: 75"), 80)
    assert len(lines) == 1
    assert "Получено опыта: 75" in lines[0]


def test_simple_gains_text_empty_block_has_no_lines():
    from ai_dm.ui.screen import Block
    from ai_dm.ui.simple import gains_lines_text

    assert gains_lines_text(Block("gains"), 80) == []


def test_simple_gains_text_wraps_by_width():
    from ai_dm.ui.screen import Block
    from ai_dm.ui.simple import gains_lines_text

    items = ("Ржавый ключ ×1", "Тряпичная кукла ×2", "Факел ×3")
    block = Block("gains", text="Получено опыта: 75 и ещё немного опыта за победу", items=items)
    lines = gains_lines_text(block, 30)
    assert len(lines) > 2
    assert all(len(line) <= 30 for line in lines)
