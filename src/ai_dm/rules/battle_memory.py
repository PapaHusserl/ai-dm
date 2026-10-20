from ai_dm.combat.engine import participant_name
from ai_dm.rules.knowledge import shorten_text
from ai_dm.rules.npc_memory import has_kind, remember
from ai_dm.state.relations import NPC_EVENT_TEXT_MAX, NpcEvent

FALLEN = "герой пал"
# исход боя -> слово в тексте события; прочие (defeat_pending, hero_dying) -- FALLEN
OUTCOME_TEXT = {"victory": "победа", "fled": "бегство", "ended_by_master": "бой прерван"}


def nearby_companions(world, hero):
    # то же условие, что combat.companions_nearby в промпте мастера
    return [n for n in world.npcs.values() if n.status == "alive" and n.follows == hero.id]


def battle_text(state, heroes, outcome) -> str:
    names = []
    for part in state.participants:
        if part.side == "enemies":
            name = participant_name(state, heroes, part.ref)
            if name not in names:
                names.append(name)
    text = f"в бою рядом с героем против {', '.join(names)} ({OUTCOME_TEXT.get(outcome, FALLEN)})"
    return shorten_text(text, NPC_EVENT_TEXT_MAX)


def remember_battle(bundle, hero, state, outcome, cfg) -> None:
    # общий бой записывает движок каждому спутнику (П4 Ж8); нет сцены, герой мёртв -- без памяти
    scene = bundle.session.current_scene
    if scene is None or hero.status == "dead":
        return
    text = battle_text(state, {hero.id: hero}, outcome)
    for npc in nearby_companions(bundle.world, hero):
        if has_kind(npc, scene, "battle"):
            continue
        event = NpcEvent(kind="battle", turn_seq=bundle.session.turn_seq, text=text)
        remember(npc, scene, event, cfg.npc_memory)
