from ai_dm.core.events import DomainEvent
from ai_dm.rules.results import Rejected
from ai_dm.rules.triggers_eval import Truth, evaluate


def check_reveal(secret, world, hero):
    return evaluate(secret.reveal_if, world, hero)


def reveal(
    npc, secret_id: str, world, hero, narrative_confirmed: bool = False,
) -> list[DomainEvent] | Rejected:
    secret = next((s for s in npc.secrets if s.id == secret_id), None)
    if secret is None:
        raise KeyError(secret_id)
    if secret.revealed:
        return []
    truth = check_reveal(secret, world, hero).truth
    if truth == Truth.FALSE:
        return Rejected(reason="too_early", report_tag=None)
    if truth == Truth.NEEDS_NARRATIVE and not narrative_confirmed:
        return Rejected(reason="needs_narrative", report_tag=None)
    secret.revealed = True
    if secret.id not in npc.known_to_player:
        npc.known_to_player.append(secret.id)
    return [DomainEvent(type="secret_revealed", data={"npc": npc.id, "secret": secret.id})]


def hidden_secrets(world, location_id) -> list[tuple]:
    # нераскрытые секреты живых NPC в локации: [(npc, secret)], по id NPC и порядку в списке
    if location_id is None:
        return []
    result = []
    for npc in sorted(world.npcs.values(), key=lambda n: n.id):
        if npc.status != "alive" or npc.location_id != location_id:
            continue
        for secret in npc.secrets:
            if not secret.revealed:
                result.append((npc, secret))
    return result
