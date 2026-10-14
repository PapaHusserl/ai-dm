from ai_dm.combat.disarm import weapon_ids
from ai_dm.state.creature import ActiveEffect


def assign_roles(engine) -> None:
    # enemy_chance: при старте боя вооружённый монстр без тега disarmer получает роль, раз за бой
    chance = engine.cfg.disarm.enemy_chance
    if chance == 0:
        return
    for p in engine.state.participants:
        armed = engine.monster_of(p.ref) and weapon_ids(engine, p.ref)
        if p.side != "enemies" or not armed or "disarmer" in engine.tags(p.ref):
            continue
        if engine.rng.randbelow(100) < chance:
            engine.creature(p.ref).active_effects.append(
                ActiveEffect(id="disarmer", source=p.ref, kind="flag")
            )
            engine.log(f"  {engine.name(p.ref)} метит выбить оружие")
