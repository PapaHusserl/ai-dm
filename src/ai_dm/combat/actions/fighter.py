from ai_dm.combat.actions import attack
from ai_dm.core.events import DomainEvent


def action_surge(engine, ref, option) -> list[DomainEvent]:
    # Всплеск действий: заряд тратится, действие возвращается
    engine.creature(ref).resources["action_surge"].current -= 1
    engine.part(ref).turn.action = True
    engine.log(f"{engine.name(ref)}: Всплеск действий")
    return []


def cleave(engine, ref, option) -> list[DomainEvent]:
    # Рассечение: вторая атака тем же оружием по другой цели в зоне первой, без модификатора урона
    # (кроме отрицательного)
    flag = [e for e in engine.creature(ref).active_effects if e.id == "cleave_ready"][0]
    flag.params["used"] = True
    infos = [i for i in attack.attacks_of(engine, ref) if i.id == option.params["weapon"]]
    if not infos:
        return []
    info = infos[0]
    # неотрицательный модификатор обнуляется, отрицательный вычитается (SRD)
    if info.damage_bonus >= 0:
        info.damage_bonus = 0
        info.damage_parts = []
    return attack.attack(engine, ref, option.params["target"], info)
