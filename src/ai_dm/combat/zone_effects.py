from ai_dm.rules.creatures import end_concentration, live_effects
from ai_dm.rules.spellcasting import effect_of
from ai_dm.state.creature import ActiveEffect, AppliedCondition, Expiry

# зоны, скрывающие обзор: вид -> слово в строке броска
OBSCURING = {"fog": "туман", "darkness": "Тьма", "sleet": "Ледяной шторм"}


def zone_effects(engine, zone_id, kind) -> list:
    # эффекты заклинаний на зоне (лежат на заклинателе): ActiveEffect(kind="zone",
    # params={"zone", "kind"}); истёкшие по часам мира не считаются
    now_s = engine.world.clock.now_s
    return [
        effect for _, creature in engine.all_creatures() for effect in live_effects(creature, now_s)
        if effect.kind == "zone" and effect.params["zone"] == zone_id
        and effect.params["kind"] == kind
    ]


def obscured(engine, zone_id, kinds=tuple(OBSCURING)) -> bool:
    # зона скрыта (Туманное облако, Тьма, Ледяной шторм): атаки в неё и из неё с помехой
    return any(zone_effects(engine, zone_id, kind) for kind in kinds)


def silenced(engine, ref) -> bool:
    # участник в зоне Тишины: не творит заклинаний, звуковой урон его не берёт
    return bool(zone_effects(engine, engine.part(ref).zone_id, "silence"))


def extra_immunities(engine, ref) -> list:
    if silenced(engine, ref):
        return ["thunder"]
    return []


def barred(engine, ref, zone_id) -> bool:
    # Магический круг: существо с одним из тегов круга не входит в зону и бьёт в неё с помехой
    tags = engine.tags(ref)
    return any(
        tags & set(effect.params["tags"].split(","))
        for effect in zone_effects(engine, zone_id, "circle")
    )


def zone_notes(engine, ref, target_ref) -> list[str]:
    # помеха атаки от зон: слова для строки броска
    zones = {engine.part(ref).zone_id, engine.part(target_ref).zone_id}
    notes = [
        word for kind, word in OBSCURING.items()
        if any(obscured(engine, zone_id, (kind,)) for zone_id in zones)
    ]
    if barred(engine, ref, engine.part(target_ref).zone_id):
        notes.append("Магический круг")
    return notes


def sleet_prone(engine, ref) -> None:
    # начало хода в зоне Ледяного шторма: Ловкость, провал -- лежит
    for effect in zone_effects(engine, engine.part(ref).zone_id, "sleet"):
        if engine.save(ref, "dex", effect.params["dc"]).outcome != "success":
            engine.impose(ref, AppliedCondition(id="prone", source=effect.id))
            engine.log(f"Ледяной шторм: {engine.name(ref)} падает")


def lights_out(engine, zone_id) -> None:
    # Дневной свет снимает Тьму своей зоны (решение 10)
    gone = zone_effects(engine, zone_id, "darkness")
    for _, creature in engine.all_creatures():
        creature.active_effects = [e for e in creature.active_effects if e not in gone]
    # заклинание кончилось: концентрация заклинателя снята
    for effect in gone:
        if effect.expires.kind == "concentration":
            end_concentration(engine.creature(effect.expires.owner))
            engine.drop_concentration_effects(effect.expires.owner)


def place_circle(hero, spell, now_s) -> None:
    # Магический круг вне боя (SRD: минута, час): эффект на герое, зона "" -- не привязан;
    # прежний круг заменяется
    effect = effect_of(spell, "zone")
    creature = hero.creature
    creature.active_effects = [e for e in creature.active_effects if e.id != spell.id]
    creature.active_effects.append(
        ActiveEffect(
            id=spell.id, source=hero.id, kind="zone",
            params={"zone": "", "kind": "circle", "tags": ",".join(effect.conditions)},
            expires=Expiry(kind="seconds", value=now_s + spell.duration_s),
        )
    )


def bind_circle(hero, zone_id, now_s) -> None:
    # старт боя: круг героя встаёт вокруг его стартовой зоны
    for effect in live_effects(hero.creature, now_s):
        if effect.kind == "zone" and effect.params["kind"] == "circle":
            effect.params["zone"] = zone_id
