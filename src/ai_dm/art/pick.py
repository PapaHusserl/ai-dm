from dataclasses import dataclass

from ai_dm.art.catalog import art_for_event, art_for_location, art_for_monster

# приоритет событий: смерть важнее победы, победа важнее нового уровня
EVENT_ORDER = ("death", "victory", "level_up")


@dataclass(frozen=True)
class PictureState:
    # location -- Location героя или None; monster -- первый живой враг боя (Monster) или None;
    # combat_id -- id идущего боя или None
    location: object = None
    monster: object = None
    combat_id: str | None = None


@dataclass(frozen=True)
class Picture:
    # kind: event, monster (временные -- после следующего хода сворачиваются), location
    kind: str
    text: str


def combat_started(prev_state, state):
    # бой начался на этом ходу (на старте игры не считается: там показываем локацию)
    return (
        prev_state is not None
        and state.combat_id is not None
        and state.combat_id != prev_state.combat_id
        and state.monster is not None
    )


def location_changed(prev_state, state):
    if state.location is None:
        return False
    return (
        prev_state is None
        or prev_state.location is None
        or prev_state.location.id != state.location.id
    )


def pick_picture(prev_state, state, events):
    # что показать после хода: Picture или None (оставить как есть); prev_state None -- старт игры
    for name in EVENT_ORDER:
        if name in events:
            text = art_for_event(name)
            if text is not None:
                return Picture("event", text)
    if combat_started(prev_state, state):
        text = art_for_monster(state.monster)
        if text is not None:
            return Picture("monster", text)
    if location_changed(prev_state, state):
        text = art_for_location(state.location)
        if text is not None:
            return Picture("location", text)
    return None
