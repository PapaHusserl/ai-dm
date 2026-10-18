# Ж3 (docs/plan-zh3.md, пп. 0.4, 0.7): секция [knowledge] правил и [master] knowledge_max.
#   RulesConfig.knowledge: KnowledgeConfig (extra="forbid"): max_per_ref = 5 (gt=0).
#   MasterConfig.knowledge_max = 30 (ge=0; 0 = блок журнала в промпте выключен).
import pytest
from pydantic import ValidationError

from ai_dm.config.app import load_settings
from ai_dm.config.settings import KnowledgeConfig, load_rules_config


def test_default_max_per_ref_is_five():
    assert load_rules_config().knowledge.max_per_ref == 5


def test_model_default_matches_toml():
    assert KnowledgeConfig().max_per_ref == load_rules_config().knowledge.max_per_ref


def test_override_max_per_ref():
    cfg = load_rules_config(toml_text="[knowledge]\nmax_per_ref = 2\n").knowledge
    assert cfg.max_per_ref == 2


@pytest.mark.parametrize("value", [0, -1])
def test_non_positive_max_per_ref_is_error(value):
    with pytest.raises(ValidationError):
        load_rules_config(toml_text=f"[knowledge]\nmax_per_ref = {value}\n")


def test_unknown_knowledge_key_is_error():
    with pytest.raises(ValidationError):
        load_rules_config(toml_text="[knowledge]\nmax_per_refs = 5\n")


def test_default_knowledge_max_is_thirty():
    assert load_settings().app.master.knowledge_max == 30


def test_override_knowledge_max():
    assert load_settings("[master]\nknowledge_max = 7\n").app.master.knowledge_max == 7


def test_zero_knowledge_max_is_allowed():
    assert load_settings("[master]\nknowledge_max = 0\n").app.master.knowledge_max == 0


def test_negative_knowledge_max_is_error():
    with pytest.raises(ValidationError):
        load_settings("[master]\nknowledge_max = -1\n")
