# Ожидаемый API: ai_dm.game.app (GameApp, Reply) -- контракт в game_kit.py.
# Главный цикл: ход, повышение уровня на границе хода, меню ошибки хода, временное правило
# смерти (ТЗ 5.1: смерть героя -> предложение загрузить последний сейв).
import contextlib
import copy

from game_kit import (
    BAD_CHECK,
    SAVED_AT,
    SONNET,
    FactorySpy,
    ReactiveAdapter,
    core_dump,
    damage_call,
    make_app,
    scripted,
    settings,
    text_step,
    tools_step,
)
from protocol_kit import make_bundle
from slots_kit import list_slots

from ai_dm.core.rng import Rng
from ai_dm.persistence.store import load_slot, save_auto
from ai_dm.rules.progression import level_up, xp_for_level

ERROR_MENU = ["retry", "switch_model", "save_and_quit"]
FATAL = [{"error": "fatal", "message": "ключ отозван"}]


def leveled_bundle(registry, xp):
    bundle = make_bundle(registry)
    bundle.heroes[0].sheet.xp = xp
    return bundle


# обычный ход

def test_text_turn_replies_with_narration(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([text_step("Стражник кивает.")]))
    reply = app.handle("Здороваюсь")
    assert reply.narration == "Стражник кивает."
    assert reply.turn.committed is True
    assert reply.pending is None
    assert reply.menu is None
    assert reply.quit is False
    assert app.bundle.session.turn_seq == 1


def test_app_creates_journal_and_ledger_for_the_world(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([text_step("Раз.")]))
    app.handle("a")
    assert app.journal.dir == tmp_path / "w1" / "journal"
    assert app.ledger.path == tmp_path / "w1" / "meta" / "costs.jsonl"
    assert len(app.journal.read_records()) == 1


def test_numbers_are_plain_text_outside_combat(registry, tmp_path):
    adapter = ReactiveAdapter()
    app = make_app(registry, tmp_path, adapter)
    reply = app.handle("2")
    assert reply.turn.committed is True
    assert len(adapter.requests) == 1


# повышение уровня

def test_level_up_is_offered_after_turn_when_xp_is_enough(registry, tmp_path):
    bundle = leveled_bundle(registry, xp_for_level(2, registry))
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    reply = app.handle("Осматриваюсь")
    assert reply.turn.committed is True
    assert reply.pending == "level_up"
    assert reply.menu == ["average", "roll"]
    assert app.pending == "level_up"


def test_no_level_up_without_enough_xp(registry, tmp_path):
    bundle = leveled_bundle(registry, xp_for_level(2, registry) - 1)
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    assert app.handle("Осматриваюсь").pending is None


def test_level_up_average_applies_progression(registry, tmp_path):
    bundle = leveled_bundle(registry, xp_for_level(2, registry))
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    app.handle("Осматриваюсь")
    expected = copy.deepcopy(app.bundle.heroes[0])
    level_up(expected, registry, hp_method="average")
    reply = app.choose("average")
    assert app.bundle.heroes[0].sheet.level == 2
    assert app.bundle.heroes[0].model_dump_json() == expected.model_dump_json()
    assert reply.pending is None
    assert app.pending is None


def test_level_up_roll_uses_and_syncs_rng(registry, tmp_path):
    bundle = leveled_bundle(registry, xp_for_level(2, registry))
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    app.handle("Осматриваюсь")
    expected = copy.deepcopy(app.bundle.heroes[0])
    rng = Rng.from_state(app.bundle.world.rng)
    level_up(expected, registry, hp_method="roll", rng=rng)
    app.choose("roll")
    assert app.bundle.heroes[0].model_dump_json() == expected.model_dump_json()
    assert app.bundle.world.rng == rng.state


def test_level_up_repeats_while_xp_is_enough(registry, tmp_path):
    bundle = leveled_bundle(registry, xp_for_level(3, registry))
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    app.handle("Осматриваюсь")
    first = app.choose("average")
    assert first.pending == "level_up"
    assert app.bundle.heroes[0].sheet.level == 2
    second = app.choose("average")
    assert second.pending is None
    assert app.bundle.heroes[0].sheet.level == 3


def test_turn_is_not_played_while_level_up_is_pending(registry, tmp_path):
    bundle = leveled_bundle(registry, xp_for_level(2, registry))
    adapter = ReactiveAdapter()
    app = make_app(registry, tmp_path, adapter, bundle=bundle)
    app.handle("Осматриваюсь")
    asked = len(adapter.requests)
    reply = app.handle("Иду дальше")
    assert reply.pending == "level_up"
    assert reply.turn is None
    assert len(adapter.requests) == asked
    assert app.bundle.session.turn_seq == 1


def test_commands_work_while_level_up_is_pending(registry, tmp_path):
    bundle = leveled_bundle(registry, xp_for_level(2, registry))
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    app.handle("Осматриваюсь")
    reply = app.handle("/sheet")
    assert reply.lines
    assert app.pending == "level_up"


# меню ошибки хода

def test_failed_turn_opens_error_menu(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted(FATAL))
    before = core_dump(app.bundle)
    reply = app.handle("Иду")
    assert reply.pending == "error_menu"
    assert reply.menu == ERROR_MENU
    assert reply.turn.committed is False
    assert core_dump(app.bundle) == before
    assert reply.turn.failure.reason == "fatal"


def test_refusal_menu_has_model_and_tone_hint(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([{"stop": "refusal"}] * 2))
    reply = app.handle("Иду")
    assert "tone" in reply.hint
    assert "модел" in reply.hint


def test_turn_is_not_played_while_error_menu_is_open(registry, tmp_path):
    adapter = scripted(FATAL + [text_step("Не должно быть.")])
    app = make_app(registry, tmp_path, adapter)
    app.handle("Иду")
    reply = app.handle("Другое")
    assert reply.pending == "error_menu"
    assert reply.turn is None
    assert len(adapter.requests) == 1


def test_retry_repeats_the_input_and_closes_menu(registry, tmp_path):
    adapter = scripted(FATAL + [text_step("Дошли.")])
    app = make_app(registry, tmp_path, adapter)
    app.handle("Иду в лес")
    reply = app.choose("retry")
    assert reply.narration == "Дошли."
    assert reply.pending is None
    assert app.pending is None
    assert app.bundle.session.turn_seq == 1
    assert app.bundle.memory.recent_turns[0].player_input == "Иду в лес"


def test_retry_that_fails_again_returns_to_menu(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted(FATAL + FATAL))
    app.handle("Иду")
    reply = app.choose("retry")
    assert reply.pending == "error_menu"
    assert reply.menu == ERROR_MENU


def test_invalid_budget_exhausted_opens_error_menu(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([tools_step(BAD_CHECK)] * 3))
    assert app.handle("Иду").pending == "error_menu"


def test_save_and_quit_saves_state_before_failed_turn(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted(FATAL))
    app.handle("Иду")
    reply = app.choose("save_and_quit")
    assert reply.quit is True
    assert "auto" in list_slots(tmp_path, "w1")
    assert core_dump(load_slot(tmp_path, "w1", "auto")) == core_dump(app.bundle)


def test_switch_model_offers_models_and_returns_to_menu(registry, tmp_path):
    factory = FactorySpy()
    app = make_app(registry, tmp_path, scripted(FATAL), adapter_factory=factory)
    app.handle("Иду")
    reply = app.choose("switch_model")
    assert reply.pending == "model_choice"
    for option in (
        "anthropic:claude-opus-5-5", f"anthropic:{SONNET}", "gemini:gemini-3.8-flash",
    ):
        assert option in reply.menu
    back = app.choose(f"anthropic:{SONNET}")
    assert factory.calls == [("anthropic", SONNET)]
    assert back.pending == "error_menu"
    assert back.menu == ERROR_MENU


def test_retry_after_model_switch_uses_new_model(registry, tmp_path):
    factory = FactorySpy()
    app = make_app(registry, tmp_path, scripted([{"stop": "refusal"}] * 2), adapter_factory=factory)
    app.handle("Иду")
    app.choose("switch_model")
    app.choose(f"anthropic:{SONNET}")
    reply = app.choose("retry")
    assert reply.turn.committed is True
    assert factory.made[0].requests[0].model == SONNET


def test_model_switch_from_menu_is_remembered_outside_slots(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted(FATAL), adapter_factory=FactorySpy())
    app.handle("Иду")
    app.choose("switch_model")
    app.choose(f"anthropic:{SONNET}")
    assert (tmp_path / "w1" / "meta" / "models.json").is_file()


# временное правило смерти

def doomed_bundle(registry):
    bundle = make_bundle(registry)
    hero = bundle.heroes[0]
    hero.creature.hp_max = 1
    hero.creature.hp_current = 1
    return bundle


def death_steps():
    return [tools_step(damage_call()), text_step("Огонь поглотил вас.")]


def test_hero_death_offers_loading_last_save(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted(death_steps()), bundle=doomed_bundle(registry))
    reply = app.handle("Прыгаю в огонь")
    assert reply.turn.committed is True
    assert reply.turn.hero_dead is True
    assert reply.pending == "hero_dead"
    assert reply.menu == ["load_last_save", "quit"]
    assert app.bundle.heroes[0].status == "dead"


def test_turn_is_not_played_after_hero_death(registry, tmp_path):
    adapter = scripted(death_steps() + [text_step("Призрак.")])
    app = make_app(registry, tmp_path, adapter, bundle=doomed_bundle(registry))
    app.handle("Прыгаю в огонь")
    reply = app.handle("Встаю")
    assert reply.pending == "hero_dead"
    assert reply.turn is None
    assert len(adapter.requests) == 2


def test_load_last_save_after_death_restores_living_hero(registry, tmp_path):
    bundle = doomed_bundle(registry)
    save_auto(tmp_path, bundle, saved_at=SAVED_AT, cfg=settings().rules)
    app = make_app(registry, tmp_path, scripted(death_steps()), bundle=bundle)
    app.handle("Прыгаю в огонь")
    reply = app.choose("load_last_save")
    assert reply.pending is None
    assert app.pending is None
    assert app.bundle.heroes[0].status == "active"
    assert app.bundle.session.turn_seq == 0


def test_load_last_save_without_save_says_so_and_keeps_menu(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted(death_steps()), bundle=doomed_bundle(registry))
    app.handle("Прыгаю в огонь")
    reply = app.choose("load_last_save")
    assert "нет сохранений" in "\n".join(reply.lines)
    assert reply.pending == "hero_dead"
    assert app.bundle.heroes[0].status == "dead"


def test_quit_after_death(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted(death_steps()), bundle=doomed_bundle(registry))
    app.handle("Прыгаю в огонь")
    assert app.choose("quit").quit is True


def test_slash_load_also_works_after_death(registry, tmp_path):
    bundle = doomed_bundle(registry)
    save_auto(tmp_path, bundle, saved_at=SAVED_AT, cfg=settings().rules)
    app = make_app(registry, tmp_path, scripted(death_steps()), bundle=bundle)
    app.handle("Прыгаю в огонь")
    app.handle("/load")
    assert app.bundle.heroes[0].status == "active"
    assert app.pending is None


# B1: смерть в бою и загрузка слота с мёртвым героем

def fight_app(registry, tmp_path):
    from game_kit import script_then_react, start_combat_call

    steps = [tools_step(start_combat_call(intent="kill")), text_step("Гоблины бросаются на вас.")]
    app = make_app(registry, tmp_path, script_then_react(steps))
    save_auto(tmp_path, app.bundle, saved_at=SAVED_AT, cfg=settings().rules)
    assert app.handle("Бью ногой дверь").turn.committed is True
    return app


def die_in_fight(app):
    from game_kit import end_turn_number

    app.bundle.heroes[0].creature.hp_current = 1
    for _ in range(60):
        reply = app.handle(str(end_turn_number(app.runner)))
        if app.pending == "hero_dead":
            return reply
    raise AssertionError("герой не погиб")


def test_death_in_combat_keeps_autosave_from_before_the_fight(registry, tmp_path):
    app = fight_app(registry, tmp_path)
    before = core_dump(load_slot(tmp_path, "w1", "auto"))
    reply = die_in_fight(app)
    assert reply.menu == ["load_last_save", "quit"]
    assert app.bundle.session.current_scene.closed_reason is None
    assert core_dump(load_slot(tmp_path, "w1", "auto")) == before


def test_load_last_save_after_death_in_combat_gives_living_hero(registry, tmp_path):
    app = fight_app(registry, tmp_path)
    die_in_fight(app)
    app.choose("load_last_save")
    assert app.pending is None
    assert app.bundle.heroes[0].status == "active"
    assert app.bundle.session.active_combat is None


def test_loading_slot_with_dead_hero_sets_hero_dead_pending(registry, tmp_path):
    from ai_dm.persistence.store import save_slot

    bundle = make_bundle(registry)
    bundle.heroes[0].status = "dead"
    save_slot(tmp_path, bundle, "manual-dead", saved_at=SAVED_AT)
    app = make_app(registry, tmp_path, ReactiveAdapter())
    app.handle("/load dead")
    assert app.pending == "hero_dead"
    assert app.bundle.heroes[0].status == "dead"
    assert app.handle("Встаю").turn is None


def test_load_last_save_with_dead_hero_in_autosave_keeps_hero_dead_menu(registry, tmp_path):
    bundle = make_bundle(registry)
    bundle.heroes[0].status = "dead"
    save_auto(tmp_path, bundle, saved_at=SAVED_AT, cfg=settings().rules)
    app = make_app(registry, tmp_path, scripted(death_steps()), bundle=doomed_bundle(registry))
    app.handle("Прыгаю в огонь")
    app.choose("load_last_save")
    assert app.pending == "hero_dead"


# B2: битый models.json и сохранённая модель

def write_models(tmp_path, text):
    path = tmp_path / "w1" / "meta" / "models.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def start_with_stored(registry, tmp_path, text, factory=None):
    write_models(tmp_path, text)
    adapter = ReactiveAdapter()
    factory = factory or FactorySpy()
    app = make_app(registry, tmp_path, adapter, adapter_factory=factory)
    return app, adapter, factory


def test_broken_models_json_starts_with_given_adapter(registry, tmp_path):
    app, adapter, factory = start_with_stored(registry, tmp_path, "{не json")
    assert app.adapter is adapter
    assert factory.calls == []
    assert len(app.startup_lines) == 1
    assert "Сохранённая модель не подключена" in app.startup_lines[0]


def test_models_json_without_model_key_starts_with_given_adapter(registry, tmp_path):
    app, adapter, _ = start_with_stored(
        registry, tmp_path, '{"narrator": {"provider": "anthropic"}}'
    )
    assert app.adapter is adapter
    assert "Сохранённая модель не подключена" in app.startup_lines[0]


def test_stored_model_without_keys_starts_with_given_adapter(registry, tmp_path):
    from ai_dm.llm.errors import MissingKey

    text = f'{{"narrator": {{"provider": "anthropic", "model": "{SONNET}"}}}}'
    factory = FactorySpy(error=MissingKey("нет ключа ANTHROPIC_API_KEY"))
    app, adapter, _ = start_with_stored(registry, tmp_path, text, factory)
    assert app.adapter is adapter
    assert "Сохранённая модель не подключена" in app.startup_lines[0]
    assert "ANTHROPIC_API_KEY" in app.startup_lines[0]


def test_stored_model_without_price_starts_with_given_adapter(registry, tmp_path):
    text = '{"narrator": {"provider": "anthropic", "model": "no-such-model"}}'
    app, adapter, factory = start_with_stored(registry, tmp_path, text)
    assert app.adapter is adapter
    assert factory.calls == []
    assert "Сохранённая модель не подключена" in app.startup_lines[0]


def test_game_is_playable_after_broken_models_json(registry, tmp_path):
    app, _, _ = start_with_stored(registry, tmp_path, "{не json")
    assert app.handle("Осматриваюсь").turn.committed is True


def test_valid_stored_model_has_no_startup_lines(registry, tmp_path):
    text = f'{{"narrator": {{"provider": "anthropic", "model": "{SONNET}"}}}}'
    app, _, factory = start_with_stored(registry, tmp_path, text)
    assert factory.calls == [("anthropic", SONNET)]
    assert app.startup_lines == []


def test_models_json_is_written_atomically(registry, tmp_path):
    import json

    app = make_app(registry, tmp_path, ReactiveAdapter(), adapter_factory=FactorySpy())
    app.handle(f"/model narrator anthropic:{SONNET}")
    folder = tmp_path / "w1" / "meta"
    assert [p.name for p in folder.iterdir() if p.name.startswith("models")] == ["models.json"]
    stored = json.loads((folder / "models.json").read_text(encoding="utf-8"))
    assert stored["narrator"]["model"] == SONNET


def test_failed_replace_leaves_old_models_json_intact(registry, tmp_path, monkeypatch):
    import os

    old = f'{{"narrator": {{"provider": "anthropic", "model": "{SONNET}"}}}}'
    path = write_models(tmp_path, old)
    app = make_app(
        registry, tmp_path, ReactiveAdapter(), adapter_factory=FactorySpy(), use_stored_model=False
    )

    def boom(src, dst):
        raise OSError("диск отвалился")

    monkeypatch.setattr(os, "replace", boom)
    with contextlib.suppress(OSError):
        app.handle("/model narrator gemini:gemini-3.8-flash")
    assert path.read_text(encoding="utf-8") == old


# D4: use_stored_model

def test_use_stored_model_false_ignores_models_json(registry, tmp_path):
    text = f'{{"narrator": {{"provider": "anthropic", "model": "{SONNET}"}}}}'
    write_models(tmp_path, text)
    adapter = ReactiveAdapter()
    factory = FactorySpy()
    app = make_app(
        registry, tmp_path, adapter, adapter_factory=factory, use_stored_model=False
    )
    assert app.adapter is adapter
    assert factory.calls == []
    assert app.startup_lines == []


def test_use_stored_model_is_true_by_default(registry, tmp_path):
    text = f'{{"narrator": {{"provider": "anthropic", "model": "{SONNET}"}}}}'
    write_models(tmp_path, text)
    factory = FactorySpy()
    app = make_app(registry, tmp_path, ReactiveAdapter(), adapter_factory=factory)
    assert factory.calls == [("anthropic", SONNET)]
    assert app.adapter is factory.made[0]


# D1: лимит раундов -- обычное меню ошибки

def test_round_limit_opens_error_menu(registry, tmp_path):
    from game_kit import end_turn_number

    app = fight_app(registry, tmp_path)
    app.runner.cfg = app.runner.cfg.model_copy(deep=True)
    app.runner.cfg.combat.max_rounds = 0
    before = core_dump(app.bundle)
    reply = app.handle(str(end_turn_number(app.runner)))
    assert reply.pending == "error_menu"
    assert reply.menu == ERROR_MENU
    assert reply.turn.failure.reason == "round_limit"
    assert core_dump(app.bundle) == before
