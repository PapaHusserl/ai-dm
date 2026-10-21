# Фикс Э10а П1 (docs/plan-fix-e10a.md): добавка правил narrator_rules_openai.md для провайдера
# openai живёт внутри system[0] (правила + добавка), в замер static_tokens не входит;
# narrator_rules.md даёт ориентир длины вместо «Обычно 3–6 абзацев».
from importlib import resources

import pytest
from master_kit import app_cfg, make_bundle

from ai_dm.master.context import estimate_tokens
from ai_dm.master.prompt import PromptBuilder
from ai_dm.protocol.context import TurnContext


def prompt_text(name):
    return (resources.files("ai_dm.master") / "prompts" / name).read_text(encoding="utf-8")


def system_of(builder, registry, cfg):
    ctx = TurnContext(make_bundle(registry), registry, cfg)
    return builder.build(ctx, "ход", "explore").system


def test_openai_provider_has_non_empty_rules_extra():
    builder = PromptBuilder(app_cfg(), provider="openai")
    assert builder.rules_extra == prompt_text("narrator_rules_openai.md")
    assert builder.rules_extra


def test_openai_system_first_block_ends_with_extra(registry, cfg):
    builder = PromptBuilder(app_cfg(), provider="openai")
    system = system_of(builder, registry, cfg)
    assert system[0].text.startswith(prompt_text("narrator_rules.md"))
    assert system[0].text.endswith(builder.rules_extra)


def test_openai_system_has_same_block_count_as_gemini(registry, cfg):
    openai = system_of(PromptBuilder(app_cfg(), provider="openai"), registry, cfg)
    gemini = system_of(PromptBuilder(app_cfg(), provider="gemini"), registry, cfg)
    assert len(openai) == len(gemini)


@pytest.mark.parametrize("provider", ["gemini", "anthropic", None])
def test_other_providers_have_no_rules_extra(provider, registry, cfg):
    builder = PromptBuilder(app_cfg(), provider=provider)
    assert builder.rules_extra == ""
    assert system_of(builder, registry, cfg)[0].text == prompt_text("narrator_rules.md")


def test_static_tokens_of_openai_equal_gemini():
    openai = PromptBuilder(app_cfg(), provider="openai").static_tokens("explore")
    gemini = PromptBuilder(app_cfg(), provider="gemini").static_tokens("explore")
    assert openai == gemini


def test_rules_extra_is_within_300_tokens():
    app = app_cfg()
    extra = PromptBuilder(app, provider="openai").rules_extra
    assert estimate_tokens(extra, app.master.chars_per_token) <= 300


def test_rules_extra_mentions_offer_choices_and_fork():
    text = prompt_text("narrator_rules_openai.md")
    assert "offer_choices" in text
    assert "развилк" in text.lower()


def test_narrator_rules_give_length_guideline():
    text = prompt_text("narrator_rules.md")
    assert "1500–2500 знаков" in text
    assert "250–400 слов" in text


def test_narrator_rules_have_no_old_paragraph_guideline():
    assert "Обычно 3–6 абзацев" not in prompt_text("narrator_rules.md")
