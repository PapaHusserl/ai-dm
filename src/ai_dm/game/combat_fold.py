from ai_dm.combat.end import OUTCOME_WORDS
from ai_dm.combat.engine import participant_name
from ai_dm.game.scene import hero_of
from ai_dm.rules.inventory import entry_name
from ai_dm.state.scene import TurnRecord

DEFEATED_WORDS = {"dead": "убит", "down": "без сознания", "fled": "бежал", "surrendered": "сдался"}


def fight_start(turns) -> int | None:
    # индекс последней записи со стартом боя
    found = [i for i, t in enumerate(turns) if "start_combat" in t.requests]
    return found[-1] if found else None


def fight_tail(turns, scene_id) -> int:
    # индекс первой сворачиваемой записи: после старта, а без старта -- вся текущая сцена
    start = fight_start(turns)
    if start is not None:
        return start + 1
    return next((i for i, t in enumerate(turns) if t.scene_id == scene_id), len(turns))


def enemy_names(state, hero) -> list[str]:
    heroes = {hero.id: hero}
    enemies = [p for p in state.participants if p.side == "enemies"]
    return [participant_name(state, heroes, p.ref) for p in enemies]


def defeated_text(state, hero) -> str:
    heroes = {hero.id: hero}
    parts = []
    for p in state.participants:
        if p.side != "enemies":
            continue
        status = p.status
        if state.outcome == "ended_by_master" and status == "active":
            status = "surrendered"
        if status in DEFEATED_WORDS:
            name = participant_name(state, heroes, p.ref)
            parts.append(f"{name} — {DEFEATED_WORDS[status]}")
    return ", ".join(parts)


def losses_text(state, hero) -> str:
    heroes = {hero.id: hero}
    parts = []
    if hero.creature.hp_current < hero.creature.hp_max:
        parts.append(f"{hero.name} HP {hero.creature.hp_current}/{hero.creature.hp_max}")
    for p in state.participants:
        if p.side == "heroes" and p.ref != hero.id and p.status in ("down", "dead"):
            word = "без сознания" if p.status == "down" else "погиб"
            parts.append(f"{participant_name(state, heroes, p.ref)} — {word}")
    return ", ".join(parts)


def trophies_text(last_combat, registry) -> str:
    if last_combat is None:
        return ""
    names = [
        entry_name(e, registry) + (f" ×{e.qty}" if e.qty > 1 else "") for e in last_combat.gear
    ]
    return ", ".join(names)


def part(label, text) -> str:
    return f"{label}: {text}" if text else ""


def fold_text(bundle, state, registry, folded) -> str:
    hero = hero_of(bundle)
    last_combat = bundle.session.last_combat
    first_seq = folded[0].turn_seq
    last_seq = folded[-1].turn_seq
    parts = [
        f"Бой: {', '.join(enemy_names(state, hero))} — {OUTCOME_WORDS[state.outcome]}, "
        f"раундов: {state.round}",
        part("побеждены", defeated_text(state, hero)),
        part("потери", losses_text(state, hero)),
        part("трофеи", trophies_text(last_combat, registry)),
    ]
    return f"Свёрнуты ходы {first_seq}–{last_seq}. " + "; ".join(p for p in parts if p)


def fold_fight(bundle, state, registry) -> bool:
    # промежуточные ходы боя -> одна запись; старт и финал остаются дословно
    turns = bundle.memory.recent_turns
    tail = fight_tail(turns, bundle.session.current_scene.id)
    folded = turns[tail:]
    if len(folded) < 2:
        return False
    last = folded[-1]
    text = fold_text(bundle, state, registry, folded)
    record = TurnRecord(
        turn_seq=last.turn_seq, at_s=last.at_s, scene_id=last.scene_id,
        player_input="", narration=text, requests=[], rolls=[],
    )
    bundle.memory.recent_turns = turns[:tail] + [record]
    return True
