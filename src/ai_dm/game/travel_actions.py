from ai_dm.game.inv_actions import SELECT_FIRST, finish
from ai_dm.game.scene import hero_of
from ai_dm.game.shop_actions import apply_shop, lines_of
from ai_dm.master.relevance import known_places, nearby_locations
from ai_dm.protocol.decision import Decision
from ai_dm.protocol.requests import AdvanceTime
from ai_dm.rules import time_ops
from ai_dm.rules.uniqueness import norm

USAGE = "Куда идти: /go <название места или номер из /where>"
IN_COMBAT = "В бою не до путешествий."


def place_of(app):
    hero = hero_of(app.bundle)
    return app.bundle.world.locations[hero.location_id]


def neighbours(app):
    # соседи текущей локации: (локация, расстояние в метрах) по id; порядок /where и /go N
    world = app.bundle.world
    near = nearby_locations(world, place_of(app))[1:]
    return [(world.locations[x["id"]], x["distance_m"]) for x in near]


def known(app):
    # посещённые дальние места с путём, по id; номера в /where продолжают соседей
    world = app.bundle.world
    here = place_of(app).id
    near_ids = {p.id for p, _ in neighbours(app)} | {here}
    return [
        p for p in known_places(world, near_ids)
        if time_ops.route_path(world, here, p.id) is not None
    ]


def minutes_text(app, distance_m):
    seconds = time_ops.travel_seconds(distance_m, "normal", app.settings.rules)
    return f"{max(1, -(-seconds // 60))} мин"


def where_lines(app):
    near = neighbours(app)
    lines = [f"Ты в «{place_of(app).name}»."]
    if near:
        lines.append("Рядом:")
        for number, (place, distance) in enumerate(near, start=1):
            lines.append(f"  {number}. {place.name} — {distance} м, {minutes_text(app, distance)}")
    far = known(app)
    if far:
        items = [f"{number}. {place.name}" for number, place in enumerate(far, len(near) + 1)]
        lines.append("Знакомые места: " + "; ".join(items))
    if not near and not far:
        lines.append("Отсюда некуда идти.")
    return lines


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
    candidates = [here, *places]
    exact = [p for p in candidates if norm(p.name) == wanted]
    found = exact or [p for p in candidates if wanted in norm(p.name)]
    if len(found) == 1:
        if found[0] is here:
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


def refusal(app, arg):
    # текст отказа до разбора места или None
    if not arg:
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
    target, problem = pick(app, arg)
    if target is None:
        return app.reply([problem])
    outcome = apply_shop(app, AdvanceTime(type="advance_time", travel_to=target))
    if not isinstance(outcome, Decision):
        return app.reply([outcome.message])
    return finish(app, lines_of(outcome), [arrival_note(app, outcome)])
