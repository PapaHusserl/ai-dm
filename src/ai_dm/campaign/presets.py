from importlib import resources

import yaml
from pydantic import BaseModel, ConfigDict

from ai_dm.state.world import Tone

# служебное значение «как в паке»: не пресет каталога
PACK_TONE = "pack"


class WorldPreset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    # кодовое имя-ориентир только для меню выбора; в промпт и тон не попадает
    codename: str = ""
    # одна строка для экрана выбора
    description: str
    tone: Tone


def load_presets() -> dict[str, WorldPreset]:
    text = (resources.files("ai_dm.campaign") / "presets.yaml").read_text(encoding="utf-8")
    presets = {}
    for item in yaml.safe_load(text):
        preset = WorldPreset.model_validate(item)
        if preset.id in presets:
            raise ValueError(f"пресет {preset.id!r} повторяется")
        if not preset.tone.notes:
            raise ValueError(f"у пресета {preset.id!r} нет голоса")
        presets[preset.id] = preset
    return presets


def merge_limits(first, second) -> list[str]:
    # объединение без дублей, порядок: сначала first
    return list(dict.fromkeys([*first, *second]))


def apply_preset(pack_tone: Tone, preset: WorldPreset) -> Tone:
    # оси, mood и голос -- из пресета; ограничения пака пресет не снимает
    return preset.tone.model_copy(
        update={
            "hard_limits": merge_limits(pack_tone.hard_limits, preset.tone.hard_limits),
            "soft_limits": merge_limits(pack_tone.soft_limits, preset.tone.soft_limits),
        },
    )
