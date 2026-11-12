from ai_dm.core.dice import roll_dice
from ai_dm.rules.creatures import live_effects
from ai_dm.state.creature import AppliedCondition, Expiry

# в Эфир уходят при 4-6 на d6 (SRD 5.2.1)
ETHER_FROM = 4


def blinked(engine, ref) -> bool:
    # существо в Эфирном плане: целью атак и заклинаний с обычного плана быть не может
    return any(c.id == "blinked" for c in engine.creature(ref).conditions)


def end_turn(engine, ref) -> None:
    # конец хода владельца Мерцания: d6, 4-6 -- в Эфире до начала своего следующего хода
    now_s = engine.world.clock.now_s
    if not engine.is_capable(ref):
        return
    if not any(e.kind == "blink" for e in live_effects(engine.creature(ref), now_s)):
        return
    if roll_dice("1d6", engine.rng).total < ETHER_FROM:
        return
    engine.creature(ref).conditions.append(
        AppliedCondition(
            id="blinked", source="blink", expires=Expiry(kind="start_of_turn", owner=ref)
        )
    )
    engine.log(f"Мерцание: {engine.name(ref)} в Эфире")


def start_turn(engine, ref) -> None:
    # возвращение: состояние снимает expire("start_of_turn"), здесь только строка лога
    if blinked(engine, ref):
        engine.log(f"{engine.name(ref)} возвращается")
