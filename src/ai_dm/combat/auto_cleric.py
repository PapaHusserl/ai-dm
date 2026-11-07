from ai_dm.rules.death_saves import is_dying

# Лечащие заклинания авто-героя по порядку; базовый круг раньше повышенного
HEAL_SPELLS = ("healing_word", "cure_wounds")


def needy_allies(engine, ref) -> list[str]:
    # кого лечить: умирающие в своей зоне, затем боеспособные с половиной HP и меньше,
    # от самого раненого
    p = engine.part(ref)
    friends = [q for q in engine.state.participants if q.side == p.side]
    dying = [
        q.ref for q in friends
        if q.status == "down" and q.zone_id == p.zone_id and dying_hero(engine, q.ref)
    ]
    hurt = []
    for q in [q for q in friends if engine.is_capable(q.ref)]:
        creature = engine.creature(q.ref)
        if creature.hp_current <= creature.hp_max // 2:
            hurt.append((creature.hp_current / creature.hp_max, q.ref))
    return sorted(dying) + [one for _, one in sorted(hurt)]


def dying_hero(engine, ref) -> bool:
    return ref in engine.heroes and is_dying(engine.heroes[ref].creature)


def cheapest(casts) -> str:
    # пункт самого низкого круга; при равенстве -- первый в меню
    return min(casts, key=lambda o: o.params["circle"]).id


def spark_of(options, target):
    for option in options:
        if option.kind == "channel_divinity" and option.params["effect"] == "spark_heal" \
                and option.params["target"] == target:
            return option.id
    return None


def pick_heal(engine, ref, options):
    # лечение нуждающегося (только жрец; решение 14): заклинание, а когда подходящего пункта
    # нет -- Божественная искра
    if engine.heroes[ref].sheet.class_id != "cleric":
        return None
    for target in needy_allies(engine, ref):
        for spell_id in HEAL_SPELLS:
            casts = [
                o for o in options
                if o.kind == "cast" and o.params["spell"] == spell_id
                and o.params["target"] == target
            ]
            if casts:
                return cheapest(casts)
        spark = spark_of(options, target)
        if spark is not None:
            return spark
    return None


def pick_bless(engine, ref, options):
    # первый раунд боя при двух и более боеспособных союзниках: Благословение на самую большую
    # группу целей
    if engine.state.round != 1 or engine.creature(ref).concentration is not None:
        return None
    side = engine.part(ref).side
    allies = [
        q for q in engine.state.participants
        if q.side == side and q.ref != ref and engine.is_capable(q.ref)
    ]
    casts = [o for o in options if o.kind == "cast" and o.params["spell"] == "bless"]
    if len(allies) < 2 or not casts:
        return None
    lowest = min(o.params["circle"] for o in casts)
    base = [o for o in casts if o.params["circle"] == lowest]
    return max(base, key=lambda o: len(o.params["target"].split(","))).id
