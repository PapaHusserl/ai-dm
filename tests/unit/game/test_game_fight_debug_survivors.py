# 19ф Ф4, добивка мутантов fight_debug: названия зон, точные тексты отказов, список монстров.
from game_kit import ReactiveAdapter, make_app
from protocol_kit import make_bundle

from ai_dm.game.fight_debug import fight_request
from ai_dm.state.world import NPC


def new_app(registry, tmp_path):
    return make_app(registry, tmp_path, ReactiveAdapter(), bundle=make_bundle(registry))


def test_fight_request_zone_names():
    zones = {z.id: z.name for z in fight_request([("skeleton", 1)]).zones}
    assert zones == {"here": "Здесь", "there": "Поодаль"}


def test_open_menu_refusal_text(registry, tmp_path):
    app = new_app(registry, tmp_path)
    app.pending = "error_menu"
    assert app.handle("/fight skeleton").lines == ["Сначала нужно сделать выбор в меню."]


def test_pending_boundary_refusal_text(registry, tmp_path):
    app = new_app(registry, tmp_path)
    app.bundle.session.boundary_pending = True
    assert app.handle("/fight skeleton").lines == [
        "Граница сцены не достроена: сначала сделайте ход."
    ]


def test_npc_ref_refusal_text(registry, tmp_path):
    app = new_app(registry, tmp_path)
    app.bundle.world.npcs["skeleton_1"] = NPC(
        id="skeleton_1", name="Скелет", key=True, means=["бой"],
    )
    assert app.handle("/fight skeleton").lines == [
        "Бой не начат: имя врага совпадает с NPC мира, NPC через /fight не поддерживаются."
    ]


def test_no_argument_lists_monsters_comma_separated(registry, tmp_path):
    app = new_app(registry, tmp_path)
    lines = app.handle("/fight").lines
    assert lines[1] == "Монстры: " + ", ".join(app.registry.ids("monster"))
