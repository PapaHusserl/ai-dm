from ai_dm.combat import downed
from ai_dm.combat.actions.attack import attack_event, roll_damage
from ai_dm.combat.zones import distance
from ai_dm.core.dice import roll_dice
from ai_dm.core.events import DomainEvent
from ai_dm.rules import divine
from ai_dm.rules.derived import ability_mod, ability_part, hero_feature_ids, spell_save_dc
from ai_dm.rules.healing import heal
from ai_dm.state.creature import AppliedCondition, Expiry

# Божественный канал: пул channel_divinity, пункты меню «Божественная искра», «Изгнание нежити»,
# «Сохранение жизни» (Домен жизни); всё стоит действие и одно использование
POOL = "channel_divinity"
# Изгнание нежити: испуг и недееспособность на 1 минуту (10 раундов) или до урона
TURN_ROUNDS = 10
# Сохранение жизни не лечит нежить и конструктов
NOT_HEALED = {"undead", "construct"}


def zones_apart(engine, ref, other) -> int:
    return distance(engine.state.zones, engine.part(ref).zone_id, engine.part(other).zone_id)


def spark_allies(engine, ref) -> list[str]:
    # другое существо в пределах 30 фт (не сам жрец): своя зона и соседние; лежачего можно поднять
    p = engine.part(ref)
    return [
        q.ref for q in engine.state.participants
        if q.ref != ref and q.side == p.side and q.status in ("active", "down")
        and zones_apart(engine, ref, q.ref) <= 1
    ]


def spark_enemies(engine, ref) -> list[str]:
    p = engine.part(ref)
    return [
        q.ref for q in engine.state.participants
        if q.side != p.side and q.status in ("active", "surrendered")
        and zones_apart(engine, ref, q.ref) <= 1
    ]


def undead_targets(engine, ref) -> list[str]:
    # нежить других сторон в своей и соседних зонах, боеспособная
    p = engine.part(ref)
    return [
        q.ref for q in engine.state.participants
        if q.side != p.side and engine.is_capable(q.ref) and "undead" in engine.tags(q.ref)
        and zones_apart(engine, ref, q.ref) <= 1
    ]


def wounded_allies(engine, ref) -> list[str]:
    # раненые союзники в своей зоне (хит-пойнтов меньше половины максимума), от самого раненого
    p = engine.part(ref)
    found = []
    for q in engine.state.participants:
        creature = engine.creature(q.ref)
        if q.side != p.side or q.zone_id != p.zone_id or q.status not in ("active", "down"):
            continue
        if engine.tags(q.ref) & NOT_HEALED or creature.hp_current >= creature.hp_max // 2:
            continue
        found.append((creature.hp_current / creature.hp_max, q.ref))
    return [one for _, one in sorted(found)]


def channel_options(engine, ref) -> list:
    # пункты группы «Божественный канал ▸»: нужны умение, заряд, действие и благосклонность бога
    from ai_dm.combat.available import ActionOption

    if not engine.is_hero(ref):
        return []
    hero = engine.heroes[ref]
    pool = engine.creature(ref).resources.get(POOL)
    if pool is None or pool.current <= 0 or not engine.part(ref).turn.action:
        return []
    if divine.channel_divinity_blocked(hero):
        return []
    features = hero_feature_ids(hero, engine.registry)
    if POOL not in features:
        return []
    result = []
    for target in spark_allies(engine, ref):
        result.append(
            ActionOption(
                id=f"channel:spark_heal:{target}", kind=POOL,
                label=f"Божественная искра: исцелить → {engine.name(target)}",
                params={"effect": "spark_heal", "target": target},
            )
        )
    for target in spark_enemies(engine, ref):
        result.append(
            ActionOption(
                id=f"channel:spark_damage:{target}", kind=POOL,
                label=f"Божественная искра: урон → {engine.name(target)}",
                params={"effect": "spark_damage", "target": target},
            )
        )
    if undead_targets(engine, ref):
        result.append(
            ActionOption(
                id="channel:turn_undead", kind=POOL, label="Изгнание нежити",
                params={"effect": "turn_undead"},
            )
        )
    if "preserve_life" in features and wounded_allies(engine, ref):
        result.append(
            ActionOption(
                id="channel:preserve_life", kind=POOL, label="Сохранение жизни",
                params={"effect": "preserve_life"},
            )
        )
    return result


def spend(engine, ref) -> None:
    # использование Канала и действие
    engine.creature(ref).resources[POOL].current -= 1
    engine.part(ref).turn.action = False


def perform(engine, ref, option) -> list[DomainEvent]:
    effect = option.params["effect"]
    spend(engine, ref)
    if effect == "turn_undead":
        return turn_undead(engine, ref)
    if effect == "preserve_life":
        return preserve_life(engine, ref)
    return divine_spark(engine, ref, option.params["target"], effect == "spark_heal")


def restore(engine, target_ref, amount) -> int:
    # лечение хит-пойнтами; из 0 HP участник встаёт
    healed = heal(engine.actor(target_ref), amount)
    p = engine.part(target_ref)
    if p.status == "down" and engine.creature(target_ref).hp_current > 0:
        p.status = "active"
    return healed


def divine_spark(engine, ref, target_ref, healing) -> list[DomainEvent]:
    # Божественная искра: 1d8 + Мудрость — исцеление или излучение (спасбросок Тел, половина)
    hero = engine.heroes[ref]
    mod = ability_mod(hero, "wis")
    if healing:
        amount = max(0, roll_dice("1d8", engine.rng).total + mod)
        healed = restore(engine, target_ref, amount)
        engine.log(
            f"Божественная искра: {engine.name(ref)} лечит {engine.name(target_ref)} на {healed}: "
            f"{engine.hp_text(target_ref)}"
        )
        return []
    engine.log(f"{engine.name(ref)}: Божественная искра → {engine.name(target_ref)}")
    rolled = roll_damage(
        engine, ref, "1d8", mod, False, label="Урон (Божественная искра)",
        parts=[ability_part(hero, "wis")], damage_type="radiant",
    )
    dc = spell_save_dc(hero, engine.registry)
    saved = engine.save(target_ref, "con", dc).outcome == "success"
    dealt = engine.damage(target_ref, rolled.total // 2 if saved else rolled.total, "radiant")
    engine.log_notes(dealt)
    engine.log(f"  {engine.name(target_ref)}: {engine.hp_text(target_ref)}")
    events = [attack_event(ref, target_ref, "divine_spark", "spell", "auto", dealt.final)]
    return events + downed.after_damage(engine, target_ref, dealt, ref)


def turn_undead(engine, ref) -> list[DomainEvent]:
    # Изгнание нежити: спасбросок Мудрости, провал — испуг и недееспособность; на 5 уровне
    # Выжигание нежити — (Мдр, не меньше 1) d8 излучением каждой провалившей, бросок один
    hero = engine.heroes[ref]
    dc = spell_save_dc(hero, engine.registry)
    sear = "sear_undead" in hero_feature_ids(hero, engine.registry)
    burn = None
    events = []
    engine.log(f"{engine.name(ref)}: Изгнание нежити")
    for target_ref in undead_targets(engine, ref):
        name = engine.name(target_ref)
        if engine.save(target_ref, "wis", dc).outcome == "success":
            engine.log(f"Изгнание нежити: {name} устоял")
            continue
        # урон Выжигания раньше состояний: он эффект не снимает (SRD), убитый состояний не получает
        if sear:
            if burn is None:
                count = max(1, ability_mod(hero, "wis"))
                burn = (count, roll_dice(f"{count}d8", engine.rng).total)
                engine.log(f"Выжигание нежити: {burn[0]}d8 = {burn[1]}")
            dealt = engine.damage(target_ref, burn[1], "radiant")
            engine.log_notes(dealt)
            engine.log(f"  {name}: {engine.hp_text(target_ref)}")
            events += downed.after_damage(engine, target_ref, dealt, ref)
        if engine.is_capable(target_ref):
            scare(engine, target_ref)
    return events


def scare(engine, target_ref) -> None:
    # испуг и недееспособность на 10 раундов; урон по цели снимает (downed.UNTIL_DAMAGE)
    fled = False
    for condition in ("frightened", "incapacitated"):
        imposed = AppliedCondition(
            id=condition, source="turn_undead", expires=Expiry(kind="rounds", value=TURN_ROUNDS),
        )
        if engine.impose(target_ref, imposed) and condition == "frightened":
            fled = True
    if fled:
        engine.log(f"Изгнание нежити: {engine.name(target_ref)} бежит в страхе")


def preserve_life(engine, ref) -> list[DomainEvent]:
    # Сохранение жизни: 5 × уровень хит-пойнтов самым раненым в своей зоне, каждому не выше
    # половины максимума; остаток переходит к следующему
    left = 5 * engine.heroes[ref].sheet.level
    for target_ref in wounded_allies(engine, ref):
        if left <= 0:
            break
        creature = engine.creature(target_ref)
        healed = restore(engine, target_ref, min(left, creature.hp_max // 2 - creature.hp_current))
        left -= healed
        engine.log(f"Сохранение жизни: {engine.name(target_ref)} +{healed}")
    return []
