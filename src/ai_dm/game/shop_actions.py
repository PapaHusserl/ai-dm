from ai_dm.core.rng import Rng
from ai_dm.game.inv_actions import SELECT_FIRST, finish
from ai_dm.protocol.apply import apply
from ai_dm.protocol.context import TurnContext
from ai_dm.protocol.decision import Decision
from ai_dm.protocol.requests import Service, Trade
from ai_dm.rules.inventory import find_item
from ai_dm.rules.money import format_cp

USAGE = (
    "Покупки: /shop услуга <NPC> <услуга> [кол-во] · /shop купить <NPC> <предмет> [кол-во] "
    "[junk|worn|used] · /shop продать <NPC> <предмет> [кол-во]"
)
QUALITIES = ("junk", "worn", "used")
# глагол команды -> вид сделки: service, buy или sell (direction запроса trade)
VERBS = {"услуга": "service", "купить": "buy", "продать": "sell"}


def parse(arg):
    # (глагол, npc_id, id, qty, качество) или None, если не разобрано
    words = arg.split()
    if len(words) < 3 or words[0].casefold() not in VERBS:
        return None
    verb = VERBS[words[0].casefold()]
    rest = words[3:]
    qty = 1
    if rest and rest[0].isdigit():
        qty = int(rest.pop(0))
    quality = None
    if verb == "buy" and rest and rest[0] in QUALITIES:
        quality = rest.pop(0)
    if rest:
        return None
    return verb, words[1], words[2], qty, quality


def shop_request(verb, npc_id, item_id, qty, quality):
    if verb == "service":
        return Service(
            type="service", npc_id=npc_id, direction="buy", service_id=item_id, qty=qty
        )
    return Trade(
        type="trade", npc_id=npc_id, direction=verb, item_id=item_id, qty=qty,
        quality=quality or "any",
    )


def apply_shop(app, request):
    # движок вне хода мастера: тот же apply, что у инструментов service/trade
    runner = app.runner
    world = app.bundle.world
    rng = Rng.from_state(world.rng)
    ctx = TurnContext(
        app.bundle, runner.registry, runner.cfg, rng, mode="explore",
        base_registry=runner.base_registry,
    )
    outcome = apply(ctx, request)
    world.rng = rng.state
    return outcome


def lines_of(decision):
    lines = list(decision.log)
    if decision.status == "clamped":
        lines.append(decision.reason)
    return lines


def title_of(app, request):
    if request.type == "service":
        return app.runner.cfg.services.kinds[request.service_id].name
    return find_item(app.registry, request.item_id)[1].name


def note_of(request, npc, decision, title):
    result = decision.result
    deal = f"«{title}» x{result['qty']}"
    cost = format_cp(result["total_cp"])
    if request.type == "service":
        return f"оплатил услугу {deal} у {npc.name} ({cost})"
    if request.direction == "buy":
        return f"купил {deal} у {npc.name} ({cost})"
    return f"продал {deal} {npc.name} ({cost})"


def run(app, arg):
    parsed = parse(arg)
    if parsed is None:
        return app.reply([USAGE])
    if app.pending is not None:
        return app.reply([SELECT_FIRST])
    request = shop_request(*parsed)
    outcome = apply_shop(app, request)
    if not isinstance(outcome, Decision):
        return app.reply([outcome.message])
    if outcome.status == "rejected":
        return app.reply([outcome.reason])
    npc = app.bundle.world.npcs[request.npc_id]
    note = note_of(request, npc, outcome, title_of(app, request))
    return finish(app, lines_of(outcome), [note])
