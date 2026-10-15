# 19ф Ф4 (docs/19F-PLAN.md п.1 Ф4): отладочная команда /fight <монстр>[ xN][, <монстр>[ xN]] --
# бой с заданным составом без вызова модели. game/fight_debug.py: parse_fight, fight_request,
# run_fight; cmd_fight в реестре команд.
import pytest
from game_kit import (
    ReactiveAdapter,
    attack_or_move_number,
    core_dump,
    make_app,
)
from protocol_kit import make_bundle

from ai_dm.game.fight_debug import fight_request, parse_fight
from ai_dm.protocol.requests import StartCombat
from ai_dm.state.world import NPC

LIMIT = 6


def text_of(reply):
    return "\n".join(reply.lines)


def new_app(registry, tmp_path, **settings):
    bundle = make_bundle(registry)
    bundle.world.settings.update(settings)
    adapter = ReactiveAdapter()
    return make_app(registry, tmp_path, adapter, bundle=bundle), adapter


def enemies_of(app):
    state = app.bundle.session.active_combat
    return [p for p in state.participants if p.side == "enemies"]


# parse_fight

def test_parse_single_with_count():
    assert parse_fight("goblin_warrior x3", LIMIT) == ([("goblin_warrior", 3)], None)


def test_parse_two_entries():
    monsters, error = parse_fight("goblin_warrior x2, skeleton", LIMIT)
    assert (monsters, error) == ([("goblin_warrior", 2), ("skeleton", 1)], None)


def test_parse_bare_name_is_one():
    assert parse_fight("skeleton", LIMIT) == ([("skeleton", 1)], None)


def test_parse_ignores_case_and_spaces_around_commas():
    monsters, error = parse_fight("  Goblin_Warrior   x2 ,skeleton  ,  ZOMBIE x1 ", LIMIT)
    assert error is None
    assert monsters == [("goblin_warrior", 2), ("skeleton", 1), ("zombie", 1)]


def test_parse_total_equal_to_limit_is_ok():
    assert parse_fight("goblin_warrior x4, skeleton x2", LIMIT)[1] is None


@pytest.mark.parametrize("arg", [
    "goblin_warrior x0",
    "goblin_warrior x7",
    "goblin_warrior x4, skeleton x3",
    "goblin_warrior x3 x4",
    "",
    "   ",
    ",",
    "goblin_warrior,",
    "goblin warrior",
])
def test_parse_bad_input_gives_error_with_syntax(arg):
    monsters, error = parse_fight(arg, LIMIT)
    assert monsters == []
    assert "/fight" in error


def test_parse_limit_is_taken_from_argument():
    assert parse_fight("skeleton x3", 2)[1] is not None
    assert parse_fight("skeleton x2", 2)[1] is None


# fight_request

def test_fight_request_is_valid_start_combat():
    request = fight_request([("goblin_warrior", 3), ("skeleton", 1)])
    assert isinstance(request, StartCombat)
    assert StartCombat.model_validate(request.model_dump(exclude_none=True)) == request


def test_fight_request_zones():
    request = fight_request([("goblin_warrior", 1)])
    zones = {z.id: z for z in request.zones}
    assert set(zones) == {"here", "there"}
    assert zones["here"].exit is True
    assert zones["here"].adjacent == ["there"]
    assert zones["there"].adjacent == ["here"]
    assert request.hero_zone == "here"


def test_fight_request_enemies_in_there_with_numbered_refs():
    request = fight_request([("goblin_warrior", 3), ("skeleton", 1)])
    assert [e.ref for e in request.enemies] == [
        "goblin_warrior_1", "goblin_warrior_2", "goblin_warrior_3", "skeleton_1",
    ]
    assert {e.zone for e in request.enemies} == {"there"}
    assert [e.monster_id for e in request.enemies] == ["goblin_warrior"] * 3 + ["skeleton"]


def test_fight_request_one_debug_group_led_by_first_enemy():
    request = fight_request([("skeleton", 2), ("zombie", 1)])
    assert {e.group for e in request.enemies} == {"debug"}
    assert len(request.groups) == 1
    group = request.groups[0]
    assert (group.id, group.leader, group.intent) == ("debug", "skeleton_1", "kill")


def test_fight_request_hero_initiates():
    assert fight_request([("skeleton", 1)]).initiated_by == "hero"


# /fight через GameApp

def test_fight_starts_combat_without_model(registry, tmp_path):
    app, adapter = new_app(registry, tmp_path)
    reply = app.handle("/fight goblin_warrior x2")
    assert app.bundle.session.active_combat is not None
    assert len(enemies_of(app)) == 2
    assert {p.monster_id for p in enemies_of(app)} == {"goblin_warrior"}
    assert adapter.requests == []
    assert reply.turn is None
    assert reply.quit is False


def test_fight_reply_has_combat_header_and_initiative(registry, tmp_path):
    app, _ = new_app(registry, tmp_path)
    text = text_of(app.handle("/fight goblin_warrior x2"))
    assert "Бой: врагов 2, зон 2" in text
    assert "инициатив" in text.lower()


def test_fight_changes_rng_and_leaves_journal_and_recent_turns_alone(registry, tmp_path):
    app, _ = new_app(registry, tmp_path)
    rng_before = app.bundle.world.rng
    turns_before = len(app.bundle.memory.recent_turns)
    seq_before = app.bundle.session.turn_seq
    app.handle("/fight goblin_warrior")
    assert app.bundle.world.rng != rng_before
    assert len(app.bundle.memory.recent_turns) == turns_before
    assert app.bundle.session.turn_seq == seq_before
    assert app.runner.journal.read_records() == []


def test_fight_enemies_are_named_from_registry(registry, tmp_path):
    app, _ = new_app(registry, tmp_path)
    app.handle("/fight goblin_warrior")
    assert enemies_of(app)[0].name == registry.get("monster", "goblin_warrior").name


def test_fight_marks_scene_hero_initiated(registry, tmp_path):
    app, _ = new_app(registry, tmp_path)
    app.handle("/fight goblin_warrior")
    assert app.bundle.session.current_scene.hero_initiated_combat is True


def test_next_player_line_goes_to_combat_turn(registry, tmp_path):
    app, adapter = new_app(registry, tmp_path)
    app.handle("/fight goblin_warrior x2")
    reply = app.handle(str(attack_or_move_number(app.runner)))
    assert reply.turn is not None
    assert reply.turn.committed is True
    assert app.bundle.session.active_combat is not None or reply.turn.combat_outcome


def test_three_goblins_on_easy_all_enter_with_over_budget_note(registry, tmp_path):
    app, _ = new_app(registry, tmp_path, difficulty="easy")
    text = text_of(app.handle("/fight goblin_warrior x3"))
    assert len(enemies_of(app)) == 3
    assert "Бой сверх бюджета" in text
    assert "Не вступили" not in text


def test_fight_does_not_autosave(registry, tmp_path):
    from slots_kit import list_slots

    app, _ = new_app(registry, tmp_path)
    app.handle("/fight goblin_warrior")
    assert list_slots(tmp_path, "w1") == []


def test_fight_during_combat_is_refused_and_state_untouched(registry, tmp_path):
    app, _ = new_app(registry, tmp_path)
    app.handle("/fight goblin_warrior")
    before = core_dump(app.bundle)
    reply = app.handle("/fight skeleton")
    assert "бой уже идёт" in text_of(reply)
    assert "Бой не начат" in text_of(reply)
    assert core_dump(app.bundle) == before


def test_unknown_monster_is_refused_with_known_ids(registry, tmp_path):
    app, _ = new_app(registry, tmp_path)
    before = core_dump(app.bundle)
    text = text_of(app.handle("/fight dragon_of_doom"))
    assert "нет монстра" in text
    assert "goblin_warrior" in text
    assert app.bundle.session.active_combat is None
    assert core_dump(app.bundle) == before


def test_fight_with_open_menu_is_refused(registry, tmp_path):
    app, _ = new_app(registry, tmp_path)
    app.pending = "error_menu"
    text = text_of(app.handle("/fight goblin_warrior"))
    assert "выбор в меню" in text
    assert app.bundle.session.active_combat is None


def test_fight_ref_matching_world_npc_is_refused(registry, tmp_path):
    # ревью 19ф п.6: ref = id ключевого NPC сделал бы врага external без сессии
    app, _ = new_app(registry, tmp_path)
    app.bundle.world.npcs["goblin_warrior_1"] = NPC(
        id="goblin_warrior_1", name="Гоблин", key=True, means=["бой"],
    )
    before = core_dump(app.bundle)
    text = text_of(app.handle("/fight goblin_warrior"))
    assert "NPC через /fight не поддерживаются" in text
    assert app.bundle.session.active_combat is None
    assert core_dump(app.bundle) == before


def test_fight_with_pending_boundary_is_refused(registry, tmp_path):
    app, _ = new_app(registry, tmp_path)
    app.bundle.session.boundary_pending = True
    text = text_of(app.handle("/fight goblin_warrior"))
    assert "Граница сцены" in text
    assert app.bundle.session.active_combat is None


def test_fight_without_argument_shows_syntax_and_monsters(registry, tmp_path):
    app, adapter = new_app(registry, tmp_path)
    before = core_dump(app.bundle)
    text = text_of(app.handle("/fight"))
    assert "/fight" in text
    for monster_id in ("goblin_warrior", "skeleton", "zombie"):
        assert monster_id in text
    assert core_dump(app.bundle) == before
    assert adapter.requests == []


@pytest.mark.parametrize(
    "arg", ["goblin_warrior x7", "goblin_warrior x0", "x3", "goblin_warrior x4, skeleton x3"]
)
def test_bad_arguments_do_not_start_combat(registry, tmp_path, arg):
    app, _ = new_app(registry, tmp_path)
    before = core_dump(app.bundle)
    reply = app.handle(f"/fight {arg}")
    assert reply.lines
    assert app.bundle.session.active_combat is None
    assert core_dump(app.bundle) == before


def test_fight_respects_max_enemies_from_settings(registry, tmp_path):
    app, _ = new_app(registry, tmp_path)
    app.settings.rules.limits.max_enemies = 2
    reply = app.handle("/fight goblin_warrior x3")
    assert app.bundle.session.active_combat is None
    assert reply.lines


# /help и таблица команд

def test_help_lists_fight_marked_as_debug(registry, tmp_path):
    app, _ = new_app(registry, tmp_path)
    text = text_of(app.handle("/help"))
    assert "/fight" in text
    assert "отладка" in text


def test_fight_is_in_commands_table():
    from ai_dm.game.commands import COMMANDS, HELP

    assert "fight" in COMMANDS
    assert "fight" in HELP
