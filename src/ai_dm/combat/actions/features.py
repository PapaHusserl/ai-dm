from ai_dm.core.dice import roll_dice
from ai_dm.core.events import DomainEvent
from ai_dm.rules.derived import effect_amount
from ai_dm.rules.healing import heal


def second_wind(engine, ref, option) -> list[DomainEvent]:
    hero = engine.heroes[ref]
    engine.part(ref).turn.bonus = False
    hero.creature.resources["second_wind"].current -= 1
    # кубики и добавка берутся из данных умения
    effects = engine.registry.get("feature", "second_wind").effects
    effect = [e for e in effects if e.type == "heal"][0]
    amount = roll_dice(effect.dice, engine.rng).total
    amount += effect_amount(effect, hero, engine.registry)
    healed = heal(hero, amount)
    engine.log(f"{engine.name(ref)}: Второе дыхание +{healed}, {engine.hp_text(ref)}")
    return []
