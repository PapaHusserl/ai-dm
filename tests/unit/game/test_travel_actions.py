# Л1, П1 (docs/plan-l1.md): команды /go и /where (ai_dm.game.travel_actions).
# Мир ui_kit.text_app: герой в таверне «Хромой гусь» (lame_goose); соседи по id -- подвал таверны
# (cellar, 20 м) и Вейл (vale, 150 м); Старая крипта (old_crypt) -- за подвалом, 15 м от него.
# Движок тот же, что у travel_to рассказчика: время, спутники, лента «Путь в …»; пометка
# «пришёл в …» уходит рассказчику префиксом следующего словесного хода.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ui"))

from game_kit import script_then_react, start_combat_call, tools_step  # noqa: E402
from ui_kit import build_app, state_of, text_app, text_step  # noqa: E402

from ai_dm.game import travel_actions  # noqa: E402
from ai_dm.game.scene import hero_of  # noqa: E402
from ai_dm.protocol.decision import Invalid  # noqa: E402
from ai_dm.state.world import NPC, Connection, Location  # noqa: E402

PREFIX = "Перед этим герой сам: "
HERE = "Таверна «Хромой гусь»"


def make_app(registry, tmp_path, steps=None):
    return text_app(registry, tmp_path, steps or [text_step()])


def location_of(app):
    return hero_of(app.bundle).location_id


def now_s(app):
    return app.bundle.world.clock.now_s


def visit(app, *location_ids):
    for location_id in location_ids:
        app.bundle.world.locations[location_id].visited = True


def add_place(app, place_id, name, near="lame_goose", distance=100):
    world = app.bundle.world
    world.locations[place_id] = Location(id=place_id, name=name)
    world.locations[near].connections.append(Connection(to=place_id, distance_m=distance))


# neighbours / known

def test_neighbours_are_sorted_by_id_with_distance(registry, tmp_path):
    app = make_app(registry, tmp_path)
    near = travel_actions.neighbours(app)
    assert [(p.id, d) for p, d in near] == [("cellar", 20), ("vale", 150)]


def test_neighbours_exclude_the_current_place(registry, tmp_path):
    app = make_app(registry, tmp_path)
    assert "lame_goose" not in [p.id for p, _ in travel_actions.neighbours(app)]


def test_known_is_empty_when_nothing_is_visited(registry, tmp_path):
    app = make_app(registry, tmp_path)
    assert travel_actions.known(app) == []


def test_known_lists_visited_places_beyond_the_neighbours(registry, tmp_path):
    app = make_app(registry, tmp_path)
    visit(app, "old_crypt")
    assert [p.id for p in travel_actions.known(app)] == ["old_crypt"]


def test_known_skips_visited_neighbours_and_the_current_place(registry, tmp_path):
    app = make_app(registry, tmp_path)
    visit(app, "cellar", "lame_goose")
    assert travel_actions.known(app) == []


def test_known_counts_visited_flag(registry, tmp_path):
    app = make_app(registry, tmp_path)
    app.bundle.world.flags["visited:old_crypt"] = True
    assert [p.id for p in travel_actions.known(app)] == ["old_crypt"]


# where_lines

def test_where_shows_here_and_numbered_neighbours_with_meters_and_minutes(registry, tmp_path):
    app = make_app(registry, tmp_path)
    assert travel_actions.where_lines(app) == [
        f"Ты в «{HERE}».",
        "Рядом:",
        "  1. Подвал таверны — 20 м, 1 мин",
        "  2. Вейл — 150 м, 2 мин",
    ]


def test_where_known_places_continue_numbering_without_minutes(registry, tmp_path):
    app = make_app(registry, tmp_path)
    visit(app, "old_crypt")
    lines = travel_actions.where_lines(app)
    assert lines[-1] == "Знакомые места: 3. Старая крипта"


def test_where_without_known_places_has_no_known_header(registry, tmp_path):
    app = make_app(registry, tmp_path)
    assert "Знакомые места:" not in travel_actions.where_lines(app)


def test_where_in_a_dead_end_says_nowhere_to_go(registry, tmp_path):
    app = make_app(registry, tmp_path)
    for place in app.bundle.world.locations.values():
        place.connections.clear()
    assert travel_actions.where_lines(app) == [f"Ты в «{HERE}».", "Отсюда некуда идти."]


def test_where_hides_a_visited_place_without_a_route(registry, tmp_path):
    app = make_app(registry, tmp_path)
    for place in app.bundle.world.locations.values():
        place.connections.clear()
    visit(app, "old_crypt")
    assert travel_actions.where_lines(app) == [f"Ты в «{HERE}».", "Отсюда некуда идти."]


def test_where_hides_an_unreachable_visited_place_but_shows_a_reachable_one(registry, tmp_path):
    app = make_app(registry, tmp_path)
    app.bundle.world.locations["island"] = Location(id="island", name="Остров")
    visit(app, "island", "old_crypt")
    lines = travel_actions.where_lines(app)
    assert lines[-1] == "Знакомые места: 3. Старая крипта"


def test_where_never_prints_the_go_hint(registry, tmp_path):
    app = make_app(registry, tmp_path)
    visit(app, "old_crypt")
    assert not any("Идти:" in line or "/go" in line for line in travel_actions.where_lines(app))


def test_where_known_places_are_one_paragraph_joined_by_semicolons(registry, tmp_path):
    app = make_app(registry, tmp_path)
    add_place(app, "mill", "Мельница", near="cellar")
    visit(app, "old_crypt", "mill")
    lines = travel_actions.where_lines(app)
    assert lines[-1] == "Знакомые места: 3. Мельница; 4. Старая крипта"
    assert sum(line.startswith("Знакомые места") for line in lines) == 1


def test_go_to_visited_place_without_route_says_unknown_place(registry, tmp_path):
    app = make_app(registry, tmp_path)
    for place in app.bundle.world.locations.values():
        place.connections.clear()
    visit(app, "old_crypt")
    before = app.bundle.world.model_dump()
    reply = app.handle("/go Старая крипта")
    assert reply.lines[0].startswith("Не знаю такого места: Старая крипта.")
    assert app.bundle.world.model_dump() == before


def test_known_skips_visited_place_without_route(registry, tmp_path):
    app = make_app(registry, tmp_path)
    app.bundle.world.locations["island"] = Location(id="island", name="Остров")
    visit(app, "island")
    assert travel_actions.known(app) == []


def test_where_command_does_not_spend_time_or_change_state(registry, tmp_path):
    app = make_app(registry, tmp_path)
    before = app.bundle.world.model_dump()
    reply = app.handle("/where")
    assert reply.turn is None
    assert app.bundle.world.model_dump() == before
    assert app.inv_notes == []
    assert app.adapter.requests == []


def test_where_command_prints_the_lines(registry, tmp_path):
    app = make_app(registry, tmp_path)
    assert app.handle("/where").lines == travel_actions.where_lines(app)


# pick

def test_pick_by_number_follows_where_order(registry, tmp_path):
    app = make_app(registry, tmp_path)
    assert travel_actions.pick(app, "1") == ("cellar", None)
    assert travel_actions.pick(app, "2") == ("vale", None)


def test_pick_known_place_by_its_number(registry, tmp_path):
    app = make_app(registry, tmp_path)
    visit(app, "old_crypt")
    assert travel_actions.pick(app, "3") == ("old_crypt", None)


def test_pick_number_out_of_range_is_refused(registry, tmp_path):
    app = make_app(registry, tmp_path)
    assert travel_actions.pick(app, "3") == (None, "Нет места с номером 3. Список: /where")


def test_pick_zero_is_refused(registry, tmp_path):
    app = make_app(registry, tmp_path)
    assert travel_actions.pick(app, "0") == (None, "Нет места с номером 0. Список: /where")


def test_pick_by_exact_name_ignores_case(registry, tmp_path):
    app = make_app(registry, tmp_path)
    assert travel_actions.pick(app, "вейл") == ("vale", None)


def test_pick_by_single_part_of_the_name(registry, tmp_path):
    app = make_app(registry, tmp_path)
    assert travel_actions.pick(app, "подвал") == ("cellar", None)


def test_pick_exact_name_wins_over_longer_names_containing_it(registry, tmp_path):
    app = make_app(registry, tmp_path)
    add_place(app, "vale_north", "Вейл-Север")
    assert travel_actions.pick(app, "Вейл") == ("vale", None)


def test_pick_part_matching_several_places_asks_to_clarify(registry, tmp_path):
    app = make_app(registry, tmp_path)
    add_place(app, "cellar_two", "Подвал мельницы")
    target, problem = travel_actions.pick(app, "подвал")
    assert target is None
    assert problem == "Уточни, куда: «Подвал таверны», «Подвал мельницы»"


def test_pick_current_place_by_name_says_already_here(registry, tmp_path):
    app = make_app(registry, tmp_path)
    assert travel_actions.pick(app, "хромой гусь") == (None, f"Ты уже в «{HERE}».")


def test_pick_current_place_by_part_of_the_name_says_already_here(registry, tmp_path):
    app = make_app(registry, tmp_path)
    assert travel_actions.pick(app, "гусь") == (None, f"Ты уже в «{HERE}».")


def test_pick_unknown_place_names_only_neighbours(registry, tmp_path):
    app = make_app(registry, tmp_path)
    visit(app, "old_crypt")
    target, problem = travel_actions.pick(app, "Атлантида")
    assert target is None
    assert problem == (
        "Не знаю такого места: Атлантида. Рядом: «Подвал таверны», «Вейл». Остальное — /where"
    )
    assert "Старая крипта" not in problem


def test_pick_unknown_place_without_neighbours_says_nothing_is_near(registry, tmp_path):
    app = make_app(registry, tmp_path)
    for place in app.bundle.world.locations.values():
        place.connections.clear()
    assert travel_actions.pick(app, "Атлантида") == (
        None, "Не знаю такого места: Атлантида. Рядом ничего нет. Знакомые места — /where"
    )


def test_pick_superscript_digit_is_not_a_number(registry, tmp_path):
    app = make_app(registry, tmp_path)
    target, problem = travel_actions.pick(app, "²")
    assert target is None
    assert problem.startswith("Не знаю такого места: ².")


def test_go_superscript_digit_does_not_crash(registry, tmp_path):
    app = make_app(registry, tmp_path)
    reply = app.handle("/go ²")
    assert reply.lines[0].startswith("Не знаю такого места: ².")
    assert location_of(app) == "lame_goose"


def test_pick_does_not_offer_a_place_never_seen_beyond_the_neighbours(registry, tmp_path):
    app = make_app(registry, tmp_path)
    assert travel_actions.pick(app, "крипта")[0] is None


# run: /go

def test_go_to_neighbour_moves_hero_and_spends_travel_time(registry, tmp_path):
    app = make_app(registry, tmp_path)
    start = now_s(app)
    reply = app.handle("/go подвал")
    assert location_of(app) == "cellar"
    assert now_s(app) == start + 15
    assert reply.lines == ["Путь в «Подвал таверны»: 15 с"]


def test_go_by_number_after_where(registry, tmp_path):
    app = make_app(registry, tmp_path)
    app.handle("/where")
    app.handle("/go 2")
    assert location_of(app) == "vale"


def test_go_to_known_far_place_goes_by_the_map(registry, tmp_path):
    app = make_app(registry, tmp_path)
    visit(app, "old_crypt")
    start = now_s(app)
    reply = app.handle("/go Старая крипта")
    assert location_of(app) == "old_crypt"
    # 35 м: 20 м -- 15 с, 15 м -- 12 с; сумма по рёбрам
    assert now_s(app) == start + 27
    assert reply.lines == ["Путь в «Старая крипта»: 27 с (через Подвал таверны)"]


def test_go_moves_the_follower_along(registry, tmp_path):
    app = make_app(registry, tmp_path)
    app.bundle.world.npcs["bran"] = NPC(
        id="bran", name="Бран", named=True, means=["m"], location_id="lame_goose",
        follows=app.bundle.manifest.current_hero_id,
    )
    app.handle("/go подвал")
    assert app.bundle.world.npcs["bran"].location_id == "cellar"


def test_go_marks_the_place_visited(registry, tmp_path):
    app = make_app(registry, tmp_path)
    app.handle("/go подвал")
    assert app.bundle.world.flags["visited:cellar"] is True


def test_go_leaves_a_note_for_the_narrator(registry, tmp_path):
    app = make_app(registry, tmp_path)
    app.handle("/go подвал")
    assert app.inv_notes == ["пришёл в «Подвал таверны» (15 с)"]


def test_go_note_names_the_stops_on_the_way(registry, tmp_path):
    app = make_app(registry, tmp_path)
    visit(app, "old_crypt")
    app.handle("/go Старая крипта")
    assert app.inv_notes == ["пришёл в «Старая крипта» (27 с, через Подвал таверны)"]


def test_go_note_lists_all_stops_on_the_way_separated_by_commas(registry, tmp_path):
    app = make_app(registry, tmp_path)
    add_place(app, "mill", "Мельница", near="cellar")
    add_place(app, "farm", "Ферма", near="mill")
    visit(app, "farm")
    app.handle("/go Ферма")
    assert app.inv_notes[0].endswith(", через Подвал таверны, Мельница)")


def test_go_shows_the_engine_refusal_when_travel_is_not_accepted(registry, tmp_path, monkeypatch):
    app = make_app(registry, tmp_path)
    refusal = Invalid(code="x", message="нет пути")
    monkeypatch.setattr(travel_actions, "apply_shop", lambda app, request: refusal)
    assert app.handle("/go подвал").lines == ["нет пути"]


def test_go_note_reaches_the_narrator_input_of_the_next_turn(registry, tmp_path):
    app = make_app(registry, tmp_path, [text_step("В подвале сыро.")])
    app.handle("/go подвал")
    app.handle("Осматриваюсь")
    assert state_of(app.adapter.requests[0])["player_input"] == (
        f"({PREFIX}пришёл в «Подвал таверны» (15 с).) Осматриваюсь"
    )
    assert app.inv_notes == []


def test_go_note_is_given_to_the_narrator_once(registry, tmp_path):
    app = make_app(registry, tmp_path, [text_step("Раз."), text_step("Два.")])
    app.handle("/go подвал")
    app.handle("Осматриваюсь")
    app.handle("Иду дальше")
    assert sum(PREFIX in state_of(r)["player_input"] for r in app.adapter.requests) == 1


def test_go_without_argument_shows_usage(registry, tmp_path):
    app = make_app(registry, tmp_path)
    start = now_s(app)
    assert app.handle("/go").lines == [travel_actions.USAGE]
    assert location_of(app) == "lame_goose"
    assert now_s(app) == start


def test_go_to_unknown_place_is_refused_and_nothing_changes(registry, tmp_path):
    app = make_app(registry, tmp_path)
    before = app.bundle.world.model_dump()
    reply = app.handle("/go Атлантида")
    assert reply.lines[0].startswith("Не знаю такого места: Атлантида.")
    assert "«Подвал таверны»" in reply.lines[0]
    assert app.bundle.world.model_dump() == before
    assert app.inv_notes == []


def test_go_to_current_place_says_hero_is_already_there(registry, tmp_path):
    app = make_app(registry, tmp_path)
    start = now_s(app)
    reply = app.handle("/go хромой гусь")
    assert reply.lines == [f"Ты уже в «{HERE}»."]
    assert location_of(app) == "lame_goose"
    assert now_s(app) == start
    assert app.inv_notes == []


def test_go_is_refused_while_a_menu_is_pending(registry, tmp_path):
    app = make_app(registry, tmp_path)
    app.pending = "error_menu"
    reply = app.handle("/go подвал")
    assert reply.lines == ["Сначала нужно сделать выбор в меню."]
    assert location_of(app) == "lame_goose"


def test_go_is_refused_in_combat(registry, tmp_path):
    steps = [tools_step(start_combat_call(intent="kill")), text_step("Гоблины бросаются на вас.")]
    app = build_app(registry, tmp_path, script_then_react(steps))
    assert app.handle("Бью ногой дверь").turn.committed is True
    assert app.bundle.session.active_combat is not None
    where = location_of(app)
    reply = app.handle("/go подвал")
    assert reply.lines == [travel_actions.IN_COMBAT]
    assert location_of(app) == where
