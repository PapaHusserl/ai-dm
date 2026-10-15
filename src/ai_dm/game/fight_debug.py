import re

from ai_dm.core.rng import Rng
from ai_dm.game import combat_flow
from ai_dm.protocol.apply import apply
from ai_dm.protocol.context import TurnContext
from ai_dm.protocol.decision import Decision
from ai_dm.protocol.requests import EnemySpec, GroupSpec, StartCombat, ZoneSpec

SYNTAX = "Синтаксис: /fight <монстр>[ xN][, <монстр>[ xN]] — например, /fight goblin_warrior x3"
HELP_TEXT = "<монстр xN, …> отладка: бой с заданным составом"
ENTRY = re.compile(r"^([a-z0-9_]+)(?:\s+x(\d+))?$")


def parse_fight(arg, limit):
    # ([(monster_id, count)], ошибка): ошибка -- строка игроку
    monsters = []
    for part in arg.lower().split(","):
        found = ENTRY.match(part.strip())
        if found is None:
            return [], f"Не разобрано {part.strip()!r}. {SYNTAX}"
        monsters.append((found.group(1), int(found.group(2) or 1)))
    if any(count < 1 for _, count in monsters) or sum(count for _, count in monsters) > limit:
        return [], f"Врагов должно быть от 1 до {limit} суммарно. {SYNTAX}"
    return monsters, None


def fight_request(monsters) -> StartCombat:
    # две зоны: герой в «Здесь», враги в «Поодаль»; initiated_by=hero -- без урезания по бюджету
    enemies = []
    for monster_id, count in monsters:
        for i in range(1, count + 1):
            enemies.append(EnemySpec(
                ref=f"{monster_id}_{i}", monster_id=monster_id, zone="there", group="debug",
            ))
    return StartCombat(
        type="start_combat",
        zones=[
            ZoneSpec(id="here", name="Здесь", adjacent=["there"], exit=True),
            ZoneSpec(id="there", name="Поодаль", adjacent=["here"]),
        ],
        enemies=enemies,
        groups=[GroupSpec(id="debug", leader=enemies[0].ref, intent="kill")],
        hero_zone="here",
        initiated_by="hero",
    )


def run_fight(app, request) -> list[str]:
    if app.pending is not None:
        return ["Сначала нужно сделать выбор в меню."]
    bundle = app.bundle
    if bundle.session.boundary_pending:
        return ["Граница сцены не достроена: сначала сделайте ход."]
    # ref, совпавший с NPC мира, делает врага этим NPC (ключевой -- external без сессии)
    if any(enemy.ref in bundle.world.npcs for enemy in request.enemies):
        return ["Бой не начат: имя врага совпадает с NPC мира, NPC через /fight не поддерживаются."]
    runner = app.runner
    rng = Rng.from_state(bundle.world.rng)
    ctx = TurnContext(
        bundle, runner.registry, runner.cfg, rng, mode="explore",
        base_registry=runner.base_registry,
    )
    outcome = apply(ctx, request)
    if not isinstance(outcome, Decision):
        return [f"Бой не начат: {outcome.message}"]
    lines = outcome.log + combat_flow.start_fight(ctx, None, "", "")
    bundle.world.rng = rng.state
    return lines


def cmd_fight(app, arg):
    if not arg:
        ids = ", ".join(app.registry.ids("monster"))
        return app.reply([SYNTAX, f"Монстры: {ids}"])
    monsters, error = parse_fight(arg, app.settings.rules.limits.max_enemies)
    if error is not None:
        return app.reply([error])
    return app.reply(run_fight(app, fight_request(monsters)))
