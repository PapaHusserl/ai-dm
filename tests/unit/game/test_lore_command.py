# Ж3 (docs/plan-zh3.md, пп. 0.9, 13): команда /lore. Тонкая обёртка над game/lore_text.lore_lines:
#   без записей -- «Журнал пуст», без аргумента -- перечень сущностей по видам, с аргументом --
#   записи найденной сущности, нет такой -- «Не найдено». Команда вне хода: время и ход не тратит,
#   журнал модели не двигает, состояние не меняет; в бою доступна.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ui"))

from ui_kit import text_app, text_step  # noqa: E402

from ai_dm.game.commands import HELP  # noqa: E402
from ai_dm.game.lore_text import LORE_EMPTY, LORE_HINT  # noqa: E402
from ai_dm.game.scene import hero_of  # noqa: E402
from ai_dm.state.knowledge import KnowledgeEntry  # noqa: E402


def make_lore(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    hero_of(app.bundle).knowledge += [
        KnowledgeEntry(
            kind="npc", ref="innkeeper", text="Знает про подвал", source="told",
            from_ref="grakh", at_s=0,
        ),
        KnowledgeEntry(kind="npc", ref="innkeeper", text="Любит эль", source="rumor", at_s=0),
        KnowledgeEntry(
            kind="situation", ref="plague", text="В деревне мор", source="rumor", at_s=0
        ),
    ]
    return app


def lore(app, arg=""):
    return app.handle(f"/lore {arg}".strip()).lines


def test_lore_is_in_help():
    assert HELP["lore"]


def test_lore_works_during_combat(registry, tmp_path):
    from game_kit import make_app, script_then_react, start_combat_call, tools_step

    steps = [tools_step(start_combat_call()), text_step("Гоблины бросаются на вас.")]
    app = make_app(registry, tmp_path, script_then_react(steps))
    app.handle("Бью ногой дверь")
    assert app.bundle.session.active_combat is not None
    hero_of(app.bundle).knowledge.append(
        KnowledgeEntry(kind="situation", ref="plague", text="Мор", source="rumor", at_s=0)
    )
    reply = app.handle("/lore")
    assert reply.turn is None
    assert "  plague — 1 зап." in reply.lines
    assert app.bundle.session.active_combat is not None


def test_creature_name_comes_from_registry(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    hero_of(app.bundle).knowledge.append(
        KnowledgeEntry(
            kind="creature", ref="goblin_warrior", text="Бой: Воин-гоблин — победа",
            source="seen", at_s=0,
        )
    )
    assert "  Воин-гоблин — 1 зап." in lore(app)


def test_empty_journal_says_so(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    assert lore(app) == [LORE_EMPTY]


def test_overview_lists_entities_with_counts(registry, tmp_path):
    lines = lore(make_lore(registry, tmp_path))
    assert "Люди:" in lines
    assert "  Гарт — 2 зап." in lines
    assert "Ситуации:" in lines
    assert "  plague — 1 зап." in lines


def test_overview_ends_with_hint(registry, tmp_path):
    lines = lore(make_lore(registry, tmp_path))
    assert lines[-2:] == ["", LORE_HINT]


def test_query_shows_entries_of_entity(registry, tmp_path):
    text = "\n".join(lore(make_lore(registry, tmp_path), "гарт"))
    assert "Гарт (Люди):" in text
    assert "Знает про подвал" in text
    assert "Любит эль" in text
    assert "В деревне мор" not in text


def test_query_names_teller(registry, tmp_path):
    text = "\n".join(lore(make_lore(registry, tmp_path), "гарт"))
    assert "рассказали: Гракх" in text


def test_query_by_ref(registry, tmp_path):
    text = "\n".join(lore(make_lore(registry, tmp_path), "plague"))
    assert "В деревне мор" in text


def test_query_not_found(registry, tmp_path):
    assert lore(make_lore(registry, tmp_path), "дракон") == ["Не найдено: дракон.", LORE_HINT]


def test_lore_does_not_spend_time_or_a_turn(registry, tmp_path):
    app = make_lore(registry, tmp_path)
    now = app.bundle.world.clock.now_s
    reply = app.handle("/lore")
    assert reply.turn is None
    assert app.bundle.world.clock.now_s == now
    assert app.adapter.requests == []


def test_lore_does_not_change_the_state(registry, tmp_path):
    app = make_lore(registry, tmp_path)
    before = app.bundle.model_dump_json()
    app.handle("/lore")
    app.handle("/lore гарт")
    assert app.bundle.model_dump_json() == before


def test_lines_fit_ui_width(registry, tmp_path):
    app = make_lore(registry, tmp_path)
    hero_of(app.bundle).knowledge.append(
        KnowledgeEntry(kind="npc", ref="innkeeper", text="слово " * 25, source="rumor", at_s=9)
    )
    width = app.settings.app.ui.width
    assert all(len(line) <= width for line in lore(app, "гарт"))
