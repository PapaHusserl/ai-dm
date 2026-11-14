from ai_dm.core.clock import DAY
from ai_dm.rules.creatures import live_effects

# Оживление: тело мёртвого не старше минуты; под Покоем срок возвращения не идёт — до 10 дней
WINDOW_S = 60
REPOSE_WINDOW_S = 10 * DAY


def revivable(npc, now_s) -> bool:
    # мёртвый именованный NPC с состоянием, смерть которого внутри окна (now_s — часы мира; в бою
    # проекция по раундам)
    if npc.status != "dead" or npc.creature is None or npc.death is None:
        return False
    window = WINDOW_S
    if any(e.kind == "gentle_repose" for e in live_effects(npc.creature, now_s)):
        window = REPOSE_WINDOW_S
    return npc.death.at_s >= now_s - window


def raise_npc(npc) -> None:
    npc.status = "alive"
    npc.creature.hp_current = 1
    # чистый лист: ни состояний, ни эффектов
    npc.creature.conditions = []
    npc.creature.active_effects = []
    npc.death = None
