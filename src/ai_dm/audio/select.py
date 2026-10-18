from dataclasses import dataclass

from ai_dm.audio.catalog import theme_for_tags


@dataclass(frozen=True)
class SoundState:
    # tags -- теги локации героя, затем родителей вверх (свои первыми);
    # horror, romance -- оси тона мира
    location_id: str | None = None
    tags: tuple = ()
    in_combat: bool = False
    horror: str = ""
    romance: str = ""
    # настроение сцены от рассказчика ("" = нет); тема с таким именем в индексе перебивает локацию
    scene_mood: str = ""


def pick_theme(index, state):
    # бой > сцена (scene_mood) > локация (id, теги) > тон мира; вариант по тону
    # (horror_variants, romance_variants) применяется к любой выбранной теме
    if state.in_combat:
        return index.combat
    theme = state.scene_mood if state.scene_mood in index.themes else None
    if theme is None:
        theme = index.locations.get(state.location_id)
    if theme is None:
        theme = theme_for_tags(index, state.tags)
    if theme is None:
        theme = tone_theme(index, state)
    return tone_variant(index, state, theme)


def tone_theme(index, state):
    if state.horror == "сильно":
        return index.tone.horror_strong
    return index.tone.default


def tone_variant(index, state, theme):
    if state.horror == "сильно":
        theme = index.tone.horror_variants.get(theme, theme)
    return index.tone.romance_variants.get(state.romance, {}).get(theme, theme)
