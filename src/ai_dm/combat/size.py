from ai_dm.rules.creatures import live_effects


def step(engine, ref) -> int:
    # сдвиг размера по списку размеров: Увеличение +1, Уменьшение −1
    now_s = engine.world.clock.now_s
    return sum(
        e.params["step"] for e in live_effects(engine.creature(ref), now_s) if e.kind == "size"
    )
