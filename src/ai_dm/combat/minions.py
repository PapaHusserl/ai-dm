from ai_dm.rules.derived import until_text
from ai_dm.rules.spellcasting import effect_of
from ai_dm.state.combat import Participant
from ai_dm.state.creature import ActiveEffect, CreatureState
from ai_dm.state.hero import Minion

PREFIX = "minion:"
FAMILIAR = "find_familiar"


def minion_ref(index: int, monster_id: str) -> str:
    return f"{PREFIX}{index}:{monster_id}"


def expired(minion, now_s) -> bool:
    return minion.until_s is not None and minion.until_s <= now_s


def participants(hero, registry, zone_id, now_s=None) -> list[Participant]:
    # призванные героя входят в бой на его стороне под управлением движка; индекс в ref — место в
    # hero.minions (по нему after_combat возвращает HP); истёкшие (now_s задан) в бой не встают
    result = []
    for index, minion in enumerate(hero.minions):
        if now_s is not None and expired(minion, now_s):
            continue
        monster = registry.get("monster", minion.monster_id)
        creature = CreatureState(hp_current=minion.hp_current, hp_max=monster.hp)
        if minion.spell_id == FAMILIAR:
            creature.active_effects.append(
                ActiveEffect(id=FAMILIAR, source=hero.id, kind="familiar")
            )
        result.append(
            Participant(
                ref=minion_ref(index, minion.monster_id), side="heroes", group_id="party",
                zone_id=zone_id, controller="engine", monster_id=minion.monster_id,
                name=monster.name, creature=creature,
            )
        )
    return result


def is_familiar(engine, ref) -> bool:
    return any(e.kind == "familiar" for e in engine.creature(ref).active_effects)


def pick_help(engine, options, ref):
    # фамильяр не атакует: помогает союзнику против врага в своей зоне
    if not is_familiar(engine, ref):
        return None
    for option in options:
        if option.kind == "help":
            return option.id
    return None


def texts(hero, registry, now_s) -> list[str]:
    # «Скелет (HP 5/13, до 07:00)», «Ястреб (HP 1/1)»; истёкшие не показываются
    result = []
    for minion in hero.minions:
        if expired(minion, now_s):
            continue
        monster = registry.get("monster", minion.monster_id)
        parts = [f"HP {minion.hp_current}/{monster.hp}"]
        if minion.until_s is not None:
            parts.append(until_text(minion.until_s, now_s))
        result.append(f"{monster.name} ({', '.join(parts)})")
    return result


def add(hero, spell, registry, now_s) -> None:
    # монстр — resource эффекта conjure (вариант уже подставлен); срок — длительность заклинания
    # (Оживление — сутки), фамильяр бессрочно и один: повтор заменяет
    if spell.id == FAMILIAR:
        hero.minions = [m for m in hero.minions if m.spell_id != FAMILIAR]
    monster_id = effect_of(spell, "conjure").resource
    until_s = None if spell.duration_s is None else now_s + spell.duration_s
    hit_points = registry.get("monster", monster_id).hp
    hero.minions.append(
        Minion(monster_id=monster_id, spell_id=spell.id, hp_current=hit_points, until_s=until_s)
    )


def after_combat(engine) -> None:
    # после сдвига часов: HP — назад в призванного, убитые и истёкшие — вон
    now_s = engine.world.clock.now_s
    for hero in engine.heroes.values():
        hp = {}
        for p in engine.state.participants:
            if p.ref.startswith(PREFIX):
                hp[int(p.ref.split(":")[1])] = (p.status, p.creature.hp_current)
        kept = []
        for index, minion in enumerate(hero.minions):
            status, current = hp.get(index, ("active", minion.hp_current))
            if status == "dead" or current <= 0 or expired(minion, now_s):
                continue
            minion.hp_current = current
            kept.append(minion)
        hero.minions = kept
