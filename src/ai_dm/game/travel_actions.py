from ai_dm.game.inv_actions import SELECT_FIRST, finish
from ai_dm.game.scene import hero_of
from ai_dm.game.shop_actions import apply_shop, lines_of
from ai_dm.master.relevance import known_places, nearby_locations, travel_intent
from ai_dm.protocol.decision import Decision
from ai_dm.protocol.requests import AdvanceTime
from ai_dm.rules import time_ops
from ai_dm.rules.journey import hero_route, road_ends
from ai_dm.rules.time_ops import minutes_text
from ai_dm.rules.uniqueness import norm

USAGE = "Куда идти: /go <название места или номер из /where>"
JOURNEY_HINT = "В пути: /go — дальше к «{}»; /go <место> — свернуть"
IN_COMBAT = "В бою не до путешествий."


def place_of(app):
    hero = hero_of(app.bundle)
    return app.bundle.world.locations[hero.location_id]


def in_road(hero):
    return hero.journey is not None and hero.location_id == hero.journey.road_id


def near_entries(app):
    # соседи текущей локации: (локация, запись nearby_locations) по id; порядок /where и /go N;
    # в «дороге» -- два конца ребра: запись {"way": «назад»|«вперёд», "seconds"}
    world = app.bundle.world
    hero = hero_of(app.bundle)
    transport = time_ops.hero_transport(hero)
    if in_road(hero):
        ends = road_ends(world, hero.journey, app.settings.rules, transport)
        return [
            (world.locations[end], {"way": way, "seconds": seconds})
            for (end, seconds), way in zip(ends, ("назад", "вперёд"), strict=False)
        ]
    near = nearby_locations(world, place_of(app), app.settings.rules, transport)[1:]
    return [(world.locations[x["id"]], x) for x in near]


def neighbours(app):
    # соседи текущей локации: (локация, расстояние в метрах; у концов «дороги» None) по id
    return [(place, entry.get("distance_m")) for place, entry in near_entries(app)]


def known(app):
    # посещённые дальние места с путём, по id; номера в /where продолжают соседей
    world = app.bundle.world
    hero = hero_of(app.bundle)
    near_ids = {p.id for p, _ in neighbours(app)} | {hero.location_id}
    return [
        p for p in known_places(world, near_ids)
        if hero_route(world, hero, p.id, app.settings.rules, "normal") is not None
    ]


def neighbour_line(app, number, place, entry):
    # «1. Лес — 20 м, 1 мин»; род пути словом, кроме дороги; закрытый -- «нужен транспорт»
    if "way" in entry:
        return f"  {number}. {place.name} — {entry['way']}, {minutes_text(entry['seconds'])}"
    kinds = app.settings.rules.time.route_kinds
    line = f"  {number}. {place.name} — {entry['distance_m']} м"
    if entry["closed"]:
        return f"{line}, {kinds[entry['kind']].name} — нужен транспорт"
    if entry["kind"] != "road":
        line += f", {kinds[entry['kind']].name}"
    return f"{line}, {minutes_text(entry['seconds'])}"


def where_lines(app):
    near = near_entries(app)
    hero = hero_of(app.bundle)
    lines = [f"Ты в «{place_of(app).name}»."]
    if near and not in_road(hero):
        lines.append("Рядом:")
    for number, (place, entry) in enumerate(near, start=1):
        lines.append(neighbour_line(app, number, place, entry))
    far = known(app)
    if far:
        items = [f"{number}. {place.name}" for number, place in enumerate(far, len(near) + 1)]
        lines.append("Знакомые места: " + "; ".join(items))
    if not near and not far:
        lines.append("Отсюда некуда идти.")
    if hero.journey is not None:
        lines.append(journey_hint(app, hero))
    return lines


def journey_hint(app, hero):
    # последняя строка /where в пути; в узле маршрута -- ещё «остаться» (путь снимается)
    world = app.bundle.world
    hint = JOURNEY_HINT.format(world.locations[hero.journey.to].name)
    if in_road(hero):
        return hint
    return f"{hint}; /go {place_of(app).name} — остаться"


def with_journey_goal(app, places):
    # цель пути -- всегда среди мест по имени (в номера /where не входит, если не знакома)
    hero = hero_of(app.bundle)
    if hero.journey is None or hero.journey.to == hero.location_id:
        return places
    goal = app.bundle.world.locations[hero.journey.to]
    return places if goal in places else [*places, goal]


def pick_number(places, number):
    if 1 <= number <= len(places):
        return places[number - 1].id, None
    return None, f"Нет места с номером {number}. Список: /where"


def pick(app, arg):
    # (id, None) или (None, текст отказа); число — номер из /where, иначе имя или его часть
    here = place_of(app)
    places = [p for p, _ in neighbours(app)] + known(app)
    if arg.isdecimal():
        return pick_number(places, int(arg))
    wanted = norm(arg)
    hero = hero_of(app.bundle)
    # в «дороге» её имя не место (содержит имена концов): в выбор не входит
    named = with_journey_goal(app, places)
    candidates = named if in_road(hero) else [here, *named]
    exact = [p for p in candidates if norm(p.name) == wanted]
    found = exact or [p for p in candidates if wanted in norm(p.name)]
    if len(found) == 1:
        if found[0] is here and hero.journey is None:
            return None, f"Ты уже в «{here.name}»."
        return found[0].id, None
    if found:
        names = ", ".join(f"«{p.name}»" for p in found)
        return None, f"Уточни, куда: {names}"
    names = ", ".join(f"«{p.name}»" for p, _ in neighbours(app))
    if names:
        hint = f" Рядом: {names}. Остальное — /where"
    else:
        hint = " Рядом ничего нет. Знакомые места — /where"
    return None, f"Не знаю такого места: {arg}.{hint}"


def arrival_note(app, outcome):
    result = outcome.result
    world = app.bundle.world
    name = world.locations[result["location_id"]].name
    note = f"пришёл в «{name}» ({result['seconds']} с"
    path = result["path"]
    if len(path) > 1:
        note += ", через " + ", ".join(world.locations[i].name for i in path[:-1])
    return note + ")"


def go_by_text(app, line):
    # «иду в X» в тексте игрока (вне боя): герой идёт до хода рассказчика, пометка уходит в ход
    if hero_of(app.bundle).location_id not in app.bundle.world.locations:
        return []
    places = with_journey_goal(app, [p for p, _ in neighbours(app)] + known(app))
    target = travel_intent(places, line)
    if target is None:
        return []
    outcome = apply_shop(app, AdvanceTime(type="advance_time", travel_to=target))
    if isinstance(outcome, Decision) and outcome.status == "accepted":
        app.inv_notes.append(arrival_note(app, outcome))
        return lines_of(outcome)
    return []


def refusal(app, arg):
    # текст отказа до разбора места или None
    if not arg and hero_of(app.bundle).journey is None:
        return USAGE
    if app.pending is not None:
        return SELECT_FIRST
    if app.bundle.session.active_combat is not None:
        return IN_COMBAT
    return None


def run(app, arg):
    text = refusal(app, arg)
    if text is not None:
        return app.reply([text])
    # голый /go (в пути, иначе отказ выше) -- следующий отрезок к цели пути
    target, problem = pick(app, arg) if arg else (hero_of(app.bundle).journey.to, None)
    if target is None:
        return app.reply([problem])
    outcome = apply_shop(app, AdvanceTime(type="advance_time", travel_to=target))
    if not isinstance(outcome, Decision):
        return app.reply([outcome.message])
    # «остаюсь» (путь снят): пометки мастеру нет (решение 116)
    notes = [] if outcome.result.get("stayed") else [arrival_note(app, outcome)]
    return finish(app, lines_of(outcome), notes)
