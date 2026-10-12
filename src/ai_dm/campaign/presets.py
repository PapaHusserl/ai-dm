from importlib import resources
from pathlib import Path

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


def preset_packs(campaigns_dir) -> dict[str, list[tuple[str, str]]]:
    # пресет -> [(id пака, имя)] по campaign.yaml в каталоге; чужие и битые паки молча пропускаются
    root = Path(campaigns_dir)
    result = {}
    if not root.is_dir():
        return result
    for folder in sorted(root.iterdir()):
        manifest = folder / "campaign.yaml"
        if folder.name.startswith(".") or not manifest.is_file():
            continue
        try:
            data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, yaml.YAMLError):
            continue
        if not isinstance(data, dict) or not data.get("preset") or data["preset"] == PACK_TONE:
            continue
        pack_id = data.get("id") or folder.name
        result.setdefault(data["preset"], []).append((pack_id, data.get("name") or pack_id))
    return result
