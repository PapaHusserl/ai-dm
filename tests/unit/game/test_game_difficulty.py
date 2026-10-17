# Партия К7к, п. 3.2-3.3: сложность боёв, команда /difficulty (docs/plan-k7k.md, В3а, Q1).
#   ai_dm.game.difficulty: DIFFICULTIES = ("easy", "normal", "hard"); WORDS = лёгкая / обычная /
#     тяжёлая;
#     current(world, cfg) -> значение (из settings или обратное отображение cfg.encounter.tier);
#     show_line(world, cfg) -> «Сложность: обычная (по умолчанию, бюджет боя умеренный)» без явной
#       настройки, «Сложность: лёгкая (бюджет боя лёгкий)» с явной;
#     parse(arg) -> (значение, ошибка), ошибка -- строка со списком сложностей;
#     apply(bundle, value) -> строка «Сложность: лёгкая»: пишет world.settings["difficulty"] и
#       запись хроники kind "event" (схема сейва не меняется) с текстом «Сложность: ...».
#   /difficulty без аргумента -- показать; /difficulty easy -- применить, хроника, автосейв;
#   /difficulty epic -- ошибка со списком, состояние не меняется; /help содержит строку команды.
import pytest
from game_kit import ReactiveAdapter, make_app
from protocol_kit import make_bundle

from ai_dm.config.settings import load_rules_config
from ai_dm.game import difficulty
from ai_dm.persistence.store import load_slot


def text_of(reply):
    return "\n".join(reply.lines)


def diff_app(registry, tmp_path, **settings):
    bundle = make_bundle(registry)
    bundle.world.settings.update(settings)
    adapter = ReactiveAdapter()
    return make_app(registry, tmp_path, adapter, bundle=bundle), adapter


def entries(app):
    found = [e for e in app.bundle.chronicle.entries if e.kind == "event"]
    return [e for e in found if e.text.startswith("Сложность")]


def high_cfg():
    return load_rules_config(toml_text='[encounter]\ntier = "high"\n')


# модуль

def test_constants():
    assert difficulty.DIFFICULTIES == ("easy", "normal", "hard")
    assert difficulty.WORDS == {"easy": "лёгкая", "normal": "обычная", "hard": "тяжёлая"}


def test_current_defaults_to_the_config_tier(registry, cfg):
    world = make_bundle(registry).world
    assert difficulty.current(world, cfg) == "normal"


def test_current_follows_a_high_config(registry):
    world = make_bundle(registry).world
    assert difficulty.current(world, high_cfg()) == "hard"


@pytest.mark.parametrize("value", ["easy", "normal", "hard"])
def test_current_returns_the_setting(registry, cfg, value):
    world = make_bundle(registry).world
    world.settings["difficulty"] = value
    assert difficulty.current(world, cfg) == value


def test_current_ignores_garbage(registry):
    world = make_bundle(registry).world
    world.settings["difficulty"] = "epic"
    assert difficulty.current(world, high_cfg()) == "hard"


def test_show_line_default(registry, cfg):
    world = make_bundle(registry).world
    assert difficulty.show_line(world, cfg) == (
        "Сложность: обычная (по умолчанию, бюджет боя умеренный)"
    )


def test_show_line_default_with_a_high_config(registry):
    world = make_bundle(registry).world
    assert difficulty.show_line(world, high_cfg()) == (
        "Сложность: тяжёлая (по умолчанию, бюджет боя тяжёлый)"
    )


@pytest.mark.parametrize(
    "value, line",
    [
        ("easy", "Сложность: лёгкая (бюджет боя лёгкий)"),
        ("normal", "Сложность: обычная (бюджет боя умеренный)"),
        ("hard", "Сложность: тяжёлая (бюджет боя тяжёлый)"),
    ],
)
def test_show_line_explicit(registry, cfg, value, line):
    world = make_bundle(registry).world
    world.settings["difficulty"] = value
    assert difficulty.show_line(world, cfg) == line


def test_show_line_with_garbage_is_default(registry, cfg):
    world = make_bundle(registry).world
    world.settings["difficulty"] = "epic"
    assert "по умолчанию" in difficulty.show_line(world, cfg)


@pytest.mark.parametrize("arg", ["easy", "normal", "hard"])
def test_parse_accepts_values(arg):
    assert difficulty.parse(arg) == (arg, None)


def test_parse_strips_spaces():
    assert difficulty.parse("  hard ") == ("hard", None)


@pytest.mark.parametrize("arg", ["epic", "Easy", "лёгкая", "easy hard"])
def test_parse_rejects_others_with_the_list(arg):
    value, error = difficulty.parse(arg)
    assert value is None
    assert "easy, normal, hard" in error
    assert repr(arg.strip()) in error


def test_apply_writes_the_setting_the_entry_and_returns_the_line(registry):
    bundle = make_bundle(registry)
    line = difficulty.apply(bundle, "easy")
    assert line == "Сложность: лёгкая"
    assert bundle.world.settings["difficulty"] == "easy"
    assert [(e.kind, e.text) for e in bundle.chronicle.entries][-1] == (
        "event", "Сложность: лёгкая"
    )


def test_apply_overwrites_the_previous_value(registry):
    bundle = make_bundle(registry)
    difficulty.apply(bundle, "easy")
    difficulty.apply(bundle, "hard")
    assert bundle.world.settings["difficulty"] == "hard"


# команда

def test_command_without_argument_shows_the_default(registry, tmp_path):
    app, _ = diff_app(registry, tmp_path)
    assert text_of(app.handle("/difficulty")) == (
        "Сложность: обычная (по умолчанию, бюджет боя умеренный)"
    )


def test_command_without_argument_shows_the_setting(registry, tmp_path):
    app, _ = diff_app(registry, tmp_path, difficulty="hard")
    assert text_of(app.handle("/difficulty")) == "Сложность: тяжёлая (бюджет боя тяжёлый)"


def test_show_changes_nothing(registry, tmp_path):
    app, _ = diff_app(registry, tmp_path)
    before = app.bundle.model_dump_json()
    app.handle("/difficulty")
    assert app.bundle.model_dump_json() == before


def test_show_does_not_call_the_model(registry, tmp_path):
    app, adapter = diff_app(registry, tmp_path)
    reply = app.handle("/difficulty")
    assert reply.turn is None
    assert adapter.requests == []


def test_command_sets_the_difficulty(registry, tmp_path):
    app, _ = diff_app(registry, tmp_path)
    reply = app.handle("/difficulty easy")
    assert app.bundle.world.settings["difficulty"] == "easy"
    assert text_of(reply) == "Сложность: лёгкая"


def test_command_writes_a_chronicle_entry(registry, tmp_path):
    app, _ = diff_app(registry, tmp_path)
    app.handle("/difficulty easy")
    assert [e.text for e in entries(app)] == ["Сложность: лёгкая"]


def test_command_autosaves(registry, tmp_path):
    app, _ = diff_app(registry, tmp_path)
    app.handle("/difficulty hard")
    saved = load_slot(tmp_path, "w1", "auto")
    assert saved.world.settings["difficulty"] == "hard"
    assert [e.text for e in saved.chronicle.entries if e.kind == "event"] == ["Сложность: тяжёлая"]


def test_show_then_set_then_show(registry, tmp_path):
    app, _ = diff_app(registry, tmp_path)
    app.handle("/difficulty easy")
    assert text_of(app.handle("/difficulty")) == "Сложность: лёгкая (бюджет боя лёгкий)"


def test_command_does_not_call_the_model(registry, tmp_path):
    app, adapter = diff_app(registry, tmp_path)
    reply = app.handle("/difficulty easy")
    assert reply.turn is None
    assert adapter.requests == []


def test_unknown_value_gives_an_error_with_the_list(registry, tmp_path):
    app, _ = diff_app(registry, tmp_path)
    text = text_of(app.handle("/difficulty epic"))
    assert "epic" in text
    assert "easy, normal, hard" in text


def test_unknown_value_changes_nothing(registry, tmp_path):
    app, _ = diff_app(registry, tmp_path)
    before = app.bundle.model_dump_json()
    app.handle("/difficulty epic")
    assert app.bundle.model_dump_json() == before


def test_unknown_value_does_not_autosave_or_write_the_chronicle(registry, tmp_path):
    app, _ = diff_app(registry, tmp_path)
    app.handle("/difficulty epic")
    assert entries(app) == []
    assert not list((tmp_path).rglob("auto*"))


def test_help_lists_the_command(registry, tmp_path):
    app, _ = diff_app(registry, tmp_path)
    text = text_of(app.handle("/help"))
    assert "/difficulty — [easy|normal|hard] сложность боёв (бюджет врагов)" in text


def test_command_is_in_the_commands_table():
    from ai_dm.game.commands import COMMANDS, HELP

    assert "difficulty" in COMMANDS
    assert "difficulty" in HELP


def test_changed_difficulty_is_seen_by_start_combat(registry, tmp_path):
    from ai_dm.rules.encounter import tier_of

    app, _ = diff_app(registry, tmp_path)
    app.handle("/difficulty hard")
    assert tier_of(app.bundle.world, app.settings.rules) == "high"
