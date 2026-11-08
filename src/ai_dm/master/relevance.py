import re

from ai_dm.rules import goals
from ai_dm.rules.knowledge import current_hero, is_adjective_word, is_noun_word
from ai_dm.rules.knowledge import mentions as name_mentioned
from ai_dm.rules.triggers_eval import is_ready


def mentions(bundle) -> str:
    # варианты ответа и ввод/рассказ последних ходов одним текстом, без регистра
    parts = list(bundle.session.offered_choices)
    for turn in bundle.memory.recent_turns:
        parts += [turn.player_input, turn.narration]
    return "\n".join(parts).lower()


def nearby_locations(world, place):
    # текущая локация и связанные с ней в любую сторону (для travel_to); расстояние в метрах
    result = [{"id": place.id, "name": place.name, "distance_m": 0}]
    distances = {c.to: c.distance_m for c in place.connections}
    for other in world.locations.values():
        for c in other.connections:
            if c.to == place.id and other.id not in distances:
                distances[other.id] = c.distance_m
    for location_id in sorted(distances):
        if location_id in world.locations:
            name = world.locations[location_id].name
            distance = distances[location_id]
            result.append({"id": location_id, "name": name, "distance_m": distance})
    return result


def known_places(world, near_ids):
    # посещённые места, не соседние текущей (цели travel_to по пути карты), по id
    return [
        p
        for p in sorted(world.locations.values(), key=lambda p: p.id)
        if (p.visited or world.flags.get(f"visited:{p.id}")) and p.id not in near_ids
    ]


def moved(player_input, outcomes) -> bool:
    # в ходе был переход: пометка «пришёл в «…» (/go, текст игрока) или travel_to рассказчика
    return "пришёл в «" in player_input or any(o.startswith("Путь в «") for o in outcomes)


def moved_last_turn(bundle) -> bool:
    # последний ход текущей сцены содержал переход
    scene = bundle.session.current_scene
    turns = bundle.memory.recent_turns
    if scene is None or not turns or turns[-1].scene_id != scene.id:
        return False
    return moved(turns[-1].player_input, turns[-1].outcomes)


def absent_location_mention(bundle, text) -> list[str]:
    # id мест (соседних и знакомых дальних), отличных от локации героя, чьё имя (с падежами) есть в
    # тексте; по id; пусто, если прошлый ход сцены был переходом (названо покинутое место)
    world = bundle.world
    here = world.locations.get(current_hero(bundle).location_id)
    if here is None or moved_last_turn(bundle):
        return []
    near = nearby_locations(world, here)
    places = [world.locations[x["id"]] for x in near[1:]]
    places += known_places(world, {x["id"] for x in near})
    return sorted(p.id for p in places if name_mentioned(p.name.lower(), text.lower()))


# стемы глаголов движения в тексте игрока («иду на причал»); одно место для travel_intent
MOVE_STEMS = (
    "ид", "пойд", "пойт", "отправ", "направ", "спуст", "подн", "верн", "едем", "поехал", "плыв",
    "шаг", "бег",
)


def travel_intent(places, text) -> str | None:
    # id единственного места из places, куда игрок идёт по тексту: глагол движения из MOVE_STEMS и
    # имя места целиком, первое слово-существительное имени или часть в «»/() как имя целиком
    # (с падежами); иначе None
    low = text.lower()
    if not any(w.startswith(MOVE_STEMS) for w in re.findall(r"\w+", low)):
        return None
    found = [p.id for p in places if any(name_mentioned(k, low) for k in place_keys(p.name))]
    return found[0] if len(found) == 1 else None


def place_keys(name) -> list[str]:
    # по каким строкам место узнают в тексте игрока (в нижнем регистре): имя целиком, первое
    # не-прилагательное вне «»/() (короткое главное слово -- без ключа), части в «»/() как имена
    name = name.lower()
    outside = re.sub(r"[«(][^»)]+[»)]", " ", name)
    noun = next((w for w in re.findall(r"\w+", outside) if not is_adjective_word(w)), "")
    return [name, *([noun] if is_noun_word(noun) else []), *re.findall(r"[«(]([^»)]+)[»)]", name)]


def npc_reason_set(bundle, npc, location_id, text, nearby_ids) -> set[str]:
    reasons = set()
    if npc.follows is not None and npc.follows == bundle.manifest.current_hero_id:
        reasons.add("with_hero")
    if location_id is not None and npc.location_id == location_id:
        reasons.add("here")
    if any(is_ready(t, bundle.world.clock.now_s) for t in npc.opportunity):
        reasons.add("active")
    if npc.key:
        reasons.add("key")
    if name_mentioned(npc.name.lower(), text):
        reasons.add("said")
    if npc.location_id in nearby_ids and npc.location_id != location_id:
        reasons.add("nearby")
    if npc.trade is not None or npc.services:
        reasons.add("merchant")
    return reasons


def previous_narration(bundle) -> str:
    # рассказ последнего хода, если он из текущей сцены; иначе пусто
    scene = bundle.session.current_scene
    turns = bundle.memory.recent_turns
    if scene is None or not turns or turns[-1].scene_id != scene.id:
        return ""
    return turns[-1].narration


def absent_mentions(bundle, text) -> list[str]:
    # id именованных живых NPC вне локации героя, чьё имя (с падежами) есть в тексте; по id
    here = current_hero(bundle).location_id
    if here is None:
        return []
    return sorted(
        npc.id for npc in bundle.world.npcs.values()
        if npc.named and npc.status == "alive" and npc.location_id != here
        and name_mentioned(npc.name.lower(), text.lower())
    )


def npc_reasons(bundle, nearby_ids=()) -> dict[str, set[str]]:
    # именованные живые NPC и причины релевантности: with_hero (идёт с героем), here (в локации
    # героя), active (активный триггер), key (ключевой), said (упомянут в offered_choices /
    # recent_turns по name), nearby (в соседней локации из nearby_ids), merchant (торговец: цель
    # визита, 132)
    location_id = None
    for hero in bundle.heroes:
        if hero.id == bundle.manifest.current_hero_id:
            location_id = hero.location_id
    text = mentions(bundle)
    result = {}
    for npc in bundle.world.npcs.values():
        if not (npc.named or goals.has_active_goal(npc)) or npc.status != "alive":
            continue
        reasons = npc_reason_set(bundle, npc, location_id, text, nearby_ids)
        if reasons:
            result[npc.id] = reasons
    return result


def relevant_npcs(bundle) -> list[str]:
    # то же без причины nearby: вход роли world; по id
    return sorted(npc_reasons(bundle))


def rank_npcs(reasons):
    # (неустранимые, вытесняемые): вытесняются said, затем key, затем nearby, затем merchant; id
    # по возрастанию. У NPC с несколькими причинами -- самая защищённая
    fixed = []
    order = {"said": 0, "key": 1, "nearby": 2, "merchant": 3}
    ranked = []
    for npc_id in sorted(reasons):
        found = reasons[npc_id]
        if found & {"with_hero", "here", "active"}:
            fixed.append(npc_id)
        else:
            ranked.append((max(order[r] for r in found), npc_id))
    return fixed, [npc_id for _, npc_id in sorted(ranked)]
