from ai_dm.combat import available
from ai_dm.combat.actions import attack
from ai_dm.combat.controllers import EngineTactics
from ai_dm.core.events import DomainEvent


def perform(engine, ref, option) -> list[DomainEvent]:
    # одно действие: шаги multiattack монстра, цель каждой атаки -- по тактике
    engine.part(ref).turn.action = False
    engine.log(f"{engine.name(ref)}: мультиатака")
    tactics = EngineTactics(engine)
    events = []
    for step in engine.monster(ref).multiattack:
        weapon = attack.action_id(step.action)
        infos = [i for i in attack.attacks_of(engine, ref) if i.id == weapon]
        if not infos:
            # действие отключено (оружие отобрано): шаг пропускается
            continue
        info = infos[0]
        for _ in range(step.count):
            options = [
                o for o in available.attack_options(engine, ref) if o.params["weapon"] == weapon
            ]
            chosen = tactics.pick_attack(options, ref)
            if chosen is None:
                break
            target = [o for o in options if o.id == chosen][0].params["target"]
            events += attack.attack(engine, ref, target, info)
    return events
