# Ж0 подшаг 2 (docs/plan-zh0.md, п. 13): секция [npc_memory] конфига правил.
# Ожидаемый API: RulesConfig.npc_memory: NpcMemoryConfig (extra="forbid"):
#   max_scenes = 20 (ge=1), max_events_per_scene = 5 (ge=1).
import pytest
from pydantic import ValidationError

from ai_dm.config.settings import load_rules_config


def memory():
    return load_rules_config().npc_memory


def test_default_max_scenes_is_twenty():
    assert memory().max_scenes == 20


def test_default_max_events_per_scene_is_five():
    assert memory().max_events_per_scene == 5


def test_override_max_scenes_keeps_events_limit():
    cfg = load_rules_config(toml_text="[npc_memory]\nmax_scenes = 3\n").npc_memory
    assert (cfg.max_scenes, cfg.max_events_per_scene) == (3, 5)


def test_override_max_events_per_scene_keeps_scenes_limit():
    cfg = load_rules_config(toml_text="[npc_memory]\nmax_events_per_scene = 2\n").npc_memory
    assert (cfg.max_scenes, cfg.max_events_per_scene) == (20, 2)


@pytest.mark.parametrize("key", ["max_scenes", "max_events_per_scene"])
def test_zero_limit_is_error(key):
    with pytest.raises(ValidationError):
        load_rules_config(toml_text=f"[npc_memory]\n{key} = 0\n")


def test_unknown_key_is_error():
    with pytest.raises(ValidationError):
        load_rules_config(toml_text="[npc_memory]\nmax_scene = 5\n")
