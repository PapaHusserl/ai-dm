# Ожидаемый API: ai_dm.game.commands через GameApp.handle("/...") -- контракт в game_kit.py.
# Служебные команды ТЗ 10: /help /save /load /model /cost /sheet /inv /quit; заглушки
# /report (этап 6), /tone (этап 3), /retire (этап 9).
import json
import time

import pytest
from game_kit import (
    NOW,
    OPUS,
    SONNET,
    FactorySpy,
    ReactiveAdapter,
    core_dump,
    damage_call,
    end_scene_call,
    make_app,
    scripted,
    text_step,
    tools_step,
)
from protocol_kit import make_bundle
from slots_kit import list_slots

from ai_dm.persistence.store import load_slot

ALL_COMMANDS = [
    "help", "save", "load", "model", "cost", "sheet", "inv", "shop", "lore", "spells", "abilities",
    "map", "quit", "report", "tone", "retire", "music", "difficulty", "fight",
]


def text_of(reply):
    return "\n".join(reply.lines)


def models_path(tmp_path):
    return tmp_path / "w1" / "meta" / "models.json"


def new_app(registry, tmp_path, adapter=None, **kw):
    return make_app(registry, tmp_path, adapter or ReactiveAdapter(), **kw)


def test_commands_table_names():
    from ai_dm.game.commands import COMMANDS

    assert sorted(COMMANDS) == sorted(ALL_COMMANDS)


# /help и неизвестные

def test_help_lists_every_command(registry, tmp_path):
    reply = new_app(registry, tmp_path).handle("/help")
    text = text_of(reply)
    for name in ALL_COMMANDS:
        assert f"/{name}" in text


def test_unknown_command_points_to_help(registry, tmp_path):
    adapter = ReactiveAdapter()
    app = new_app(registry, tmp_path, adapter)
    reply = app.handle("/dance")
    assert "/help" in text_of(reply)
    assert reply.turn is None
    assert adapter.requests == []


@pytest.mark.parametrize("line", [
    "/help", "/sheet", "/inv", "/spells", "/abilities", "/cost", "/model", "/report", "/tone",
    "/difficulty",
    "/retire", "/dance",
    "/save alpha", "/load nope",
])
def test_commands_do_not_call_model_or_touch_state(registry, tmp_path, line):
    adapter = ReactiveAdapter()
    app = new_app(registry, tmp_path, adapter)
    before = core_dump(app.bundle)
    reply = app.handle(line)
    assert reply.lines
    assert reply.turn is None
    assert reply.quit is False
    assert adapter.requests == []
    assert core_dump(app.bundle) == before


# /save и /load

def test_save_with_name_writes_manual_slot(registry, tmp_path):
    app = new_app(registry, tmp_path)
    app.handle("/save alpha")
    assert list_slots(tmp_path, "w1") == ["manual-alpha"]
    assert core_dump(load_slot(tmp_path, "w1", "manual-alpha")) == core_dump(app.bundle)


def test_save_without_name_uses_quick_slot(registry, tmp_path):
    app = new_app(registry, tmp_path)
    app.handle("/save")
    assert list_slots(tmp_path, "w1") == ["manual-quick"]


def test_save_with_bad_name_says_so_and_writes_nothing(registry, tmp_path):
    app = new_app(registry, tmp_path)
    reply = app.handle("/save ../evil")
    assert reply.lines
    assert list_slots(tmp_path, "w1") == []


def test_load_restores_state_after_last_completed_turn(registry, tmp_path):
    from ai_dm.state.session import ChapterState

    bundle = make_bundle(registry)
    bundle.session.current_chapter = ChapterState(id="ch_1", number=1, scene_count=1)
    app = new_app(
        registry, tmp_path, scripted([text_step("Раз."), text_step("Два.")]), bundle=bundle
    )
    app.handle("первый")
    app.handle("/save a")
    saved = core_dump(app.bundle)
    app.handle("второй")
    assert app.bundle.session.turn_seq == 2
    app.handle("/load a")
    assert app.bundle.session.turn_seq == 1
    assert core_dump(app.bundle) == saved


def test_load_without_name_takes_latest_autosave(registry, tmp_path):
    steps = [tools_step(end_scene_call()), text_step("Конец."), text_step("Ещё ход.")]
    app = new_app(registry, tmp_path, scripted(steps))
    app.handle("закончим")
    app.handle("ещё")
    assert app.bundle.session.turn_seq == 2
    app.handle("/load")
    assert app.bundle.session.turn_seq == 1
    assert [t.narration for t in app.bundle.memory.recent_turns] == ["Конец."]


def test_load_of_closed_scene_starts_a_new_one(registry, tmp_path):
    steps = [tools_step(end_scene_call()), text_step("Конец.")]
    app = new_app(registry, tmp_path, scripted(steps))
    app.handle("закончим")
    assert load_slot(tmp_path, "w1", "auto").session.current_scene.closed_reason == "end_scene"
    app.handle("/load")
    scene = app.bundle.session.current_scene
    assert scene.closed_reason is None
    assert scene.id == "scene_2"


def test_load_unknown_slot_keeps_state(registry, tmp_path):
    app = new_app(registry, tmp_path)
    before = core_dump(app.bundle)
    reply = app.handle("/load nope")
    assert reply.lines
    assert core_dump(app.bundle) == before


def test_load_without_any_autosave_keeps_state(registry, tmp_path):
    app = new_app(registry, tmp_path)
    before = core_dump(app.bundle)
    reply = app.handle("/load")
    assert reply.lines
    assert core_dump(app.bundle) == before


def test_play_continues_after_load(registry, tmp_path):
    app = new_app(registry, tmp_path, scripted([text_step("Раз."), text_step("Два.")]))
    app.handle("/save a")
    app.handle("/load a")
    reply = app.handle("ход")
    assert reply.turn.committed is True
    assert reply.narration == "Раз."


# /model

def test_model_without_args_lists_roles_and_models(registry, tmp_path):
    reply = new_app(registry, tmp_path).handle("/model")
    text = text_of(reply)
    assert "narrator" in text
    assert OPUS in text


def test_model_switches_narrator_adapter_and_requests(registry, tmp_path):
    factory = FactorySpy()
    old = ReactiveAdapter()
    app = new_app(registry, tmp_path, old, adapter_factory=factory)
    app.handle(f"/model narrator anthropic:{SONNET}")
    assert factory.calls == [("anthropic", SONNET)]
    assert app.adapter is factory.made[0]
    app.handle("Иду")
    assert old.requests == []
    assert factory.made[0].requests[0].model == SONNET


def test_model_choice_is_stored_outside_slots(registry, tmp_path):
    app = new_app(registry, tmp_path, adapter_factory=FactorySpy())
    app.handle(f"/model narrator anthropic:{SONNET}")
    stored = json.loads(models_path(tmp_path).read_text(encoding="utf-8"))
    assert stored["narrator"] == {"provider": "anthropic", "model": SONNET}
    app.handle("/save a")
    assert list((tmp_path / "w1" / "slots").rglob("models.json")) == []


def test_model_choice_survives_restart(registry, tmp_path):
    first = new_app(registry, tmp_path, adapter_factory=FactorySpy())
    first.handle(f"/model narrator anthropic:{SONNET}")
    factory = FactorySpy()
    second = new_app(registry, tmp_path, adapter_factory=factory)
    assert factory.calls == [("anthropic", SONNET)]
    assert second.adapter is factory.made[0]


def test_model_choice_is_not_part_of_the_save(registry, tmp_path):
    app = new_app(registry, tmp_path, adapter_factory=FactorySpy())
    before = core_dump(app.bundle)
    app.handle(f"/model narrator anthropic:{SONNET}")
    assert core_dump(app.bundle) == before


def test_model_accepts_gemini_profile_model(registry, tmp_path):
    factory = FactorySpy()
    app = new_app(registry, tmp_path, adapter_factory=factory)
    app.handle("/model narrator gemini:gemini-3.8-flash")
    assert factory.calls == [("gemini", "gemini-3.8-flash")]


def test_model_unknown_role_changes_nothing(registry, tmp_path):
    factory = FactorySpy()
    old = ReactiveAdapter()
    app = new_app(registry, tmp_path, old, adapter_factory=factory)
    reply = app.handle(f"/model wizard anthropic:{SONNET}")
    assert reply.lines
    assert factory.calls == []
    assert app.adapter is old
    assert not models_path(tmp_path).exists()


def test_model_without_price_in_config_changes_nothing(registry, tmp_path):
    factory = FactorySpy()
    old = ReactiveAdapter()
    app = new_app(registry, tmp_path, old, adapter_factory=factory)
    app.handle("/model narrator anthropic:no-such-model")
    assert factory.calls == []
    assert app.adapter is old
    assert not models_path(tmp_path).exists()


def test_model_factory_error_is_reported_and_changes_nothing(registry, tmp_path):
    from ai_dm.llm.errors import MissingKey

    factory = FactorySpy(error=MissingKey("нет ключа ANTHROPIC_API_KEY"))
    old = ReactiveAdapter()
    app = new_app(registry, tmp_path, old, adapter_factory=factory)
    reply = app.handle(f"/model narrator anthropic:{SONNET}")
    assert "ANTHROPIC_API_KEY" in text_of(reply)
    assert app.adapter is old
    assert not models_path(tmp_path).exists()


# /cost, /sheet, /inv

def test_cost_report_has_session_day_world_and_roles(registry, tmp_path):
    steps = [{"text": "Рассказ.", "usage": {"input": 1000, "output": 100}}]
    app = new_app(registry, tmp_path, scripted(steps))
    app.handle("Иду")
    reply = app.handle("/cost")
    text = text_of(reply).lower()
    for word in ("сессия", "день", "мир", "narrator", OPUS):
        assert word in text


def test_cost_report_survives_aborted_turn(registry, tmp_path):
    # ход упал после ответа модели: деньги потрачены, откат их не возвращает
    steps = [
        {"text": "x", "usage": {"input": 1000, "output": 100}, "tool_calls": [
            {"name": "skill_check", "input": {"type": "skill_check", "skill": "nope"}}
        ]},
        {"error": "fatal"},
    ]
    app = new_app(registry, tmp_path, scripted(steps))
    app.handle("Иду")
    assert app.ledger.report(NOW.date()).session.total_nano > 0
    assert "narrator" in text_of(app.handle("/cost"))


def test_sheet_shows_hero_name_and_hp(registry, tmp_path):
    app = new_app(registry, tmp_path)
    hero = app.bundle.heroes[0]
    text = text_of(app.handle("/sheet"))
    assert hero.name in text
    assert f"{hero.creature.hp_current}/{hero.creature.hp_max}" in text


def test_inv_lists_hero_items(registry, tmp_path):
    from ai_dm.rules.inventory import find_item

    app = new_app(registry, tmp_path)
    text = text_of(app.handle("/inv"))
    assert app.bundle.heroes[0].inventory
    for entry in app.bundle.heroes[0].inventory:
        name = find_item(registry, entry.item_id)[1].name
        assert name in text or entry.item_id in text


# /quit и заглушки

def test_quit_sets_quit_flag_and_saves_auto(registry, tmp_path):
    # P13: /quit сохраняет auto
    app = new_app(registry, tmp_path)
    reply = app.handle("/quit")
    assert reply.quit is True
    assert list_slots(tmp_path, "w1") == ["auto"]


def test_quit_says_saved_auto(registry, tmp_path):
    reply = new_app(registry, tmp_path).handle("/quit")
    assert "Сохранено: auto" in text_of(reply)


def test_quit_saves_current_state(registry, tmp_path):
    app = new_app(registry, tmp_path, scripted([text_step("Рассказ.")]))
    app.handle("Иду")
    app.handle("/quit")
    assert load_slot(tmp_path, "w1", "auto").session.turn_seq == 1


def test_quit_after_hero_death_does_not_save(registry, tmp_path):
    app = new_app(registry, tmp_path)
    app.bundle.heroes[0].status = "dead"
    app.pending = "hero_dead"
    reply = app.handle("/quit")
    assert reply.quit is True
    assert list_slots(tmp_path, "w1") == []


@pytest.mark.parametrize(("line", "phrase"), [
    ("/retire", "появится на этапе 9"),
])
def test_stage_stubs_name_their_stage(registry, tmp_path, line, phrase):
    assert phrase in text_of(new_app(registry, tmp_path).handle(line))


# D11: /save при погибшем герое запрещён

def test_save_is_refused_while_hero_is_dead(registry, tmp_path):
    bundle = make_bundle(registry)
    bundle.heroes[0].creature.hp_max = 1
    bundle.heroes[0].creature.hp_current = 1
    steps = [tools_step(damage_call()), text_step("Огонь поглотил вас.")]
    app = new_app(registry, tmp_path, scripted(steps), bundle=bundle)
    app.handle("Прыгаю в огонь")
    assert app.pending == "hero_dead"
    reply = app.handle("/save a")
    assert reply.lines
    assert list_slots(tmp_path, "w1") == []
    reply = app.handle("/save")
    assert reply.lines
    assert list_slots(tmp_path, "w1") == []
    assert app.pending == "hero_dead"


# P14: /cost -- «день» общий для миров и по местному времени

def test_cost_day_sums_all_worlds(registry, tmp_path):
    from ai_dm.llm.cost import CostLedger
    from ai_dm.llm.types import Usage

    other = CostLedger(tmp_path, "other-world")
    other.add(
        call_id="o-1", role="narrator", model=OPUS, usage=Usage(input=1, output=1),
        cost_nano=5_000_000_000, day=NOW.astimezone().date(),
    )
    app = new_app(registry, tmp_path)
    lines = text_of(app.handle("/cost")).splitlines()
    day = lines.index(next(line for line in lines if line.startswith("День")))
    world = lines.index(next(line for line in lines if line.startswith("Мир")))
    assert "$5.0000" in lines[day]
    assert "$5.0000" not in lines[world]


def test_cost_uses_local_date_for_day(registry, tmp_path, monkeypatch):
    from datetime import UTC, datetime

    from ai_dm.llm.cost import CostLedger
    from ai_dm.llm.types import Usage

    # 23:30 UTC 3 октября -- в Окленде (UTC+13 осенью) уже 4 октября
    monkeypatch.setenv("TZ", "Pacific/Auckland")
    time.tzset()
    try:
        moment = datetime(2026, 10, 3, 23, 30, tzinfo=UTC)
        local_day = moment.astimezone().date()
        assert local_day.isoformat() == "2026-10-04"
        ledger = CostLedger(tmp_path, "w1")
        ledger.add(
            call_id="c-1", role="narrator", model=OPUS, usage=Usage(input=1, output=1),
            cost_nano=2_000_000_000, day=local_day,
        )
        app = new_app(registry, tmp_path)
        app.now = lambda: moment
        lines = text_of(app.handle("/cost")).splitlines()
        assert "$2.0000" in next(line for line in lines if line.startswith("День"))
    finally:
        monkeypatch.undo()
        time.tzset()


# P3: /model и бюджет контекста

def big_turns_bundle(registry):
    from master_kit import turn_record

    bundle = make_bundle(registry)
    bundle.memory.recent_turns = [turn_record(n, narration="слово " * 500) for n in range(1, 9)]
    return bundle


def test_model_with_small_window_gives_smaller_budget_and_drops(registry, tmp_path):
    factory = FactorySpy()
    app = new_app(
        registry, tmp_path, adapter_factory=factory, bundle=big_turns_bundle(registry)
    )
    app.settings.app.context_windows[SONNET] = 10_000
    app.settings.app.master.context_cap = 10**9
    app.handle(f"/model narrator anthropic:{SONNET}")
    app.handle("Иду")
    records = [r for r in app.journal.read_records() if r["role"] == "narrator"]
    context = records[0]["meta"]["context"]
    assert records[0]["requested_model"] == SONNET
    # окно 10 000 меньше статики: потолок динамики 0, бюджет поднят до 80 % окна
    assert context["budget"] == 8_000
    assert context["cap"] == 0
    assert context["static"] > 8_000
    assert context["dropped"]


def test_model_keeps_big_window_budget_before_switch(registry, tmp_path):
    app = new_app(registry, tmp_path, bundle=big_turns_bundle(registry))
    app.settings.app.context_windows[SONNET] = 10_000
    app.handle("Иду")
    records = [r for r in app.journal.read_records() if r["role"] == "narrator"]
    assert records[0]["meta"]["context"]["cap"] == 16_000
    assert records[0]["meta"]["context"]["dropped"] == []


def test_model_without_window_changes_nothing(registry, tmp_path):
    factory = FactorySpy()
    old = ReactiveAdapter()
    app = new_app(registry, tmp_path, old, adapter_factory=factory)
    del app.settings.app.context_windows[SONNET]
    reply = app.handle(f"/model narrator anthropic:{SONNET}")
    assert reply.lines
    assert factory.calls == []
    assert app.adapter is old
    assert not models_path(tmp_path).exists()


# Б1а (B1-PLAN A4): /sheet показывает описание предыстории, мотив, средства, возможности

def sheet_app(tmp_path, registry, **hero_fields):
    bundle = make_bundle(registry)
    hero = bundle.heroes[0]
    for key, value in hero_fields.items():
        setattr(hero, key, value)
    return make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)


def test_sheet_shows_background_description(tmp_path, registry):
    app = sheet_app(tmp_path, registry)
    app.bundle.heroes[0].sheet.background.description = "Вырос в бродячем цирке."
    text = text_of(app.handle("/sheet"))
    assert "Предыстория: " in text
    assert "Вырос в бродячем цирке." in text


def test_sheet_shows_motive_means_and_opportunity(tmp_path, registry):
    from ai_dm.state.triggers import Trigger

    trigger = Trigger.model_validate({"id": "o1", "if": {"narrative": "x"}, "then": "отомстить"})
    app = sheet_app(
        tmp_path, registry, motive="Найти сестру.", means=["острый ум", "связи"],
        opportunity=[trigger],
    )
    lines = app.handle("/sheet").lines
    assert "Мотив: Найти сестру." in lines
    assert "Средства: острый ум; связи" in lines
    assert "Возможности: o1 — отомстить" in lines


def test_sheet_without_hooks_has_no_hook_lines(tmp_path, registry):
    app = sheet_app(tmp_path, registry)
    app.bundle.heroes[0].sheet.background.description = ""
    text = text_of(app.handle("/sheet"))
    assert "Мотив:" not in text
    assert "Средства:" not in text
    assert "Возможности:" not in text
    assert "Предыстория:" not in text
