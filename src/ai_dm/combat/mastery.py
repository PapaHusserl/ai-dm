from ai_dm.combat import downed
from ai_dm.core.events import DomainEvent
from ai_dm.rules.derived import proficiency, weapon_ability_mod
from ai_dm.state.creature import ActiveEffect, AppliedCondition, Expiry


def mastery_of(engine, ref, info) -> str | None:
    # мастерство срабатывает, только если оружие выбрано в листе героя
    if info.weapon_id is None or not engine.is_hero(ref):
        return None
    hero = engine.heroes[ref]
    if info.weapon_id not in hero.sheet.weapon_masteries:
        return None
    return engine.registry.get("weapon", info.weapon_id).mastery


def on_hit(engine, ref, target_ref, info, damage, provoked=False) -> list[DomainEvent]:
    mastery = mastery_of(engine, ref, info)
    if mastery is None or engine.part(target_ref).status == "dead":
        return []
    target = engine.creature(target_ref)
    if mastery == "sap":
        target.active_effects.append(
            ActiveEffect(
                id="sap", source=ref, kind="modifier",
                params={"target": "attack_roll", "mode": "disadvantage", "consume": True},
                expires=Expiry(kind="start_of_turn", owner=ref),
            )
        )
        engine.log(f"  {engine.name(target_ref)}: Ослабление, следующая атака с помехой")
    if mastery == "vex" and damage > 0:
        # до конца следующего хода атакующего: попал в свой ход -- первый конец хода пропускается,
        # провоцированной атакой (чужой ход) -- до конца его ближайшего хода
        skip = 0
        if not provoked:
            skip = 1
        engine.creature(ref).active_effects.append(
            ActiveEffect(
                id="vex", source=ref, kind="modifier",
                params={
                    "target": "attack_roll", "mode": "advantage", "against": target_ref,
                    "consume": True,
                },
                expires=Expiry(kind="end_of_turn", value=skip, owner=ref),
            )
        )
        engine.log(
            f"  {engine.name(ref)}: Досада, следующая атака по {engine.name(target_ref)} "
            "с преимуществом"
        )
    if mastery == "topple":
        hero = engine.heroes[ref]
        weapon = engine.registry.get("weapon", info.weapon_id)
        dc = 8 + weapon_ability_mod(hero, weapon) + proficiency(hero, engine.registry)
        saved = engine.save(target_ref, "con", dc)
        prone = AppliedCondition(id="prone", source=ref)
        if saved.outcome == "fail" and engine.impose(target_ref, prone):
            engine.log(f"  {engine.name(target_ref)} сбит с ног")
    return []


def on_miss(engine, ref, target_ref, info) -> tuple[int, list[DomainEvent]]:
    # возвращает (урон, события)
    mastery = mastery_of(engine, ref, info)
    if mastery != "graze":
        return 0, []
    hero = engine.heroes[ref]
    weapon = engine.registry.get("weapon", info.weapon_id)
    amount = weapon_ability_mod(hero, weapon)
    if amount <= 0:
        return 0, []
    dealt = engine.damage(target_ref, amount, info.damage_type)
    engine.log_notes(dealt)
    engine.log(f"  Царапина: {amount} урона, {engine.hp_text(target_ref)}")
    events = downed.after_damage(engine, target_ref, dealt, ref)
    return dealt.final, events
