from ai_dm.core.dice import roll_dice
from ai_dm.core.events import DomainEvent
from ai_dm.rules.derived import effect_amount, hero_feature_ids
from ai_dm.rules.healing import heal
from ai_dm.state.creature import ActiveEffect, Expiry


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


def horde_mark(engine, ref, info, target_ref) -> None:
    # Истребитель орд: первая атака оружием за ход открывает вторую (флаг до конца хода героя)
    if not engine.is_hero(ref) or info.weapon_id is None:
        return
    if "horde_breaker" not in hero_feature_ids(engine.heroes[ref], engine.registry):
        return
    if any(e.id == "horde_breaker" for e in engine.creature(ref).active_effects):
        return
    engine.creature(ref).active_effects.append(
        ActiveEffect(
            id="horde_breaker", source=ref, kind="flag",
            params={
                "weapon": info.id, "target": target_ref,
                "zone": engine.part(target_ref).zone_id, "used": False,
            },
            expires=Expiry(kind="end_of_turn", value=0, owner=ref),
        )
    )


def horde_breaker(engine, ref, option) -> list[DomainEvent]:
    # вторая атака тем же оружием без траты действия и атак
    # локальный импорт: цикл импортов attack <-> features
    from ai_dm.combat.actions import attack

    flag = [e for e in engine.creature(ref).active_effects if e.id == "horde_breaker"][0]
    flag.params["used"] = True
    infos = [i for i in attack.attacks_of(engine, ref) if i.id == option.params["weapon"]]
    if not infos:
        return []
    return attack.attack(engine, ref, option.params["target"], infos[0])
