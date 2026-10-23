# ТБ #45 (docs/plan-tb.md п.3): замер статики запроса рассказчика -- правила (narrator_rules.md)
# и схемы инструментов режима -- с порогом STATIC_MAX (ratchet). Замер:
# PromptBuilder.static_tokens(mode) -> {rules, tools, total} по общему chars_per_token (не по
# провайдеру); реестр пака не участвует (monster_ids и world.md паков в статику не входят).
#
# STATIC_MAX = текущий explore.total после ТБ #56 + ~3 %. Поднимать порог только с причиной здесь:
#   ТБ (2026-10-17): порог введён, 28900 = 28022 + 3 %.
#   Ж0 п.0 (2026-10-17): static_tokens считает схемы с ensure_ascii=False (раньше кириллица в
#   \uXXXX удваивала tools): explore.total 28022 -> 17666 (rules 8167, tools 9499);
#   18200 = 17666 + 3 %.
#   Ж0 п.18 (2026-10-18): правило записи памяти NPC и поля memory_kind/memory_text в npc_update;
#   explore.total 17666 -> 18185; 18700 = 18185 + 3 %.
#   Ж3 п.9 (2026-10-18): запросы knowledge_note и scene_mood, раздел правил «Журнал знаний и
#   настроение сцены»; explore.total 18458 -> 19462; 20050 = 19462 + 3 %.
#   Ж1 коммит 2 (2026-10-18): поле name в npc_update и правило о выживших; замер 19736, порог
#   20050 не менялся.
#   Ж2 коммит 2 (2026-10-18): поля goal_* в npc_update, правило «Цели NPC»; explore.total
#   19736 -> 20344; 20960 = 20344 + 3 %.
#   Фикс ЖП3 П3 (2026-10-20): правила (103 spent без держателя, 99 hit_dice, 101 вещь от NPC,
#   108 зелье от спутника) и описания TakeItem/UseItem; порог 20960 превышен,
#   замер 20988; 21620 = 20988 + 3 %.
#   Фикс Э10а П1 (2026-10-21): ориентир длины в «Стиле повествования» (narrator_rules.md);
#   explore.total 20988 -> 21307 (rules 10530, tools 10777); порог 21620 не менялся.
#   Фикс ЖП4 П2 (2026-10-22): поля until/until_hour в advance_time (131), фраза про until в
#   «Время двигай…» и known_locations П1; порог 21620 превышен, замер 21663;
#   22310 = 21663 + 3 %.
#   У0 П2 (2026-10-22): абзац про ночлег (два шага: service, затем rest long) в narrator_rules.md,
#   цена фичи принята в П1; порог 22310 превышен, замер 22418; 23090 = 22418 + 3 %.
#   Добавка narrator_rules_openai.md в замер не входит (она внутри system[0] только у openai).
import json
from importlib import resources

import pytest
from master_kit import app_cfg

from ai_dm.config.app import load_settings
from ai_dm.llm.types import ToolSpec
from ai_dm.master.context import estimate_tokens
from ai_dm.master.prompt import PromptBuilder
from ai_dm.protocol.schema import MODE_TOOLS, tool_set

# У0 П2: замер explore.total 22418 + 3 %.
# У1 П2: фраза о платной близости, решение 30 (23090 -> 23150).
# У1 П3: абзац «Услуги» -- последствия компании и «вонь», решение 33 (замер 23235; 23150 -> 23240).
# 164: пометка о покупке из окна /shop, services без цен (замер 23325; 23240 -> 23340).
STATIC_MAX = 23340

MODES = sorted(MODE_TOOLS)


def builder(app=None):
    return PromptBuilder(app or load_settings().app)


def rules_text():
    return (resources.files("ai_dm.master") / "prompts" / "narrator_rules.md").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("mode", MODES)
def test_static_total_is_within_threshold(mode):
    assert builder().static_tokens(mode)["total"] <= STATIC_MAX


@pytest.mark.parametrize("mode", MODES)
def test_static_total_is_rules_plus_tools(mode):
    tokens = builder().static_tokens(mode)
    assert tokens["total"] == tokens["rules"] + tokens["tools"]


@pytest.mark.parametrize("mode", MODES)
def test_static_parts_are_positive(mode):
    tokens = builder().static_tokens(mode)
    assert tokens["rules"] > 0
    assert tokens["tools"] > 0


@pytest.mark.parametrize("mode", MODES)
def test_static_result_has_exactly_three_keys(mode):
    assert set(builder().static_tokens(mode)) == {"rules", "tools", "total"}


def test_explore_is_the_largest_static_mode():
    totals = {mode: builder().static_tokens(mode)["total"] for mode in MODES}
    assert totals["explore"] == max(totals.values())


def test_rules_tokens_are_the_same_in_every_mode():
    rules = {builder().static_tokens(mode)["rules"] for mode in MODES}
    assert len(rules) == 1


def test_rules_tokens_are_estimate_of_rules_file_by_common_cpt():
    app = load_settings().app
    expected = estimate_tokens(rules_text(), app.master.chars_per_token)
    assert builder(app).static_tokens("explore")["rules"] == expected


@pytest.mark.parametrize("mode", MODES)
def test_tools_tokens_are_estimate_of_serialized_tool_schemas(mode):
    app = load_settings().app
    specs = [ToolSpec.model_validate(d) for d in tool_set(mode)]
    dumped = json.dumps([s.model_dump(mode="json") for s in specs], ensure_ascii=False)
    expected = estimate_tokens(dumped, app.master.chars_per_token)
    assert builder(app).static_tokens(mode)["tools"] == expected


def test_static_tokens_follow_common_chars_per_token():
    loose = load_settings().app
    loose.master.chars_per_token = 5.0
    tight = load_settings().app
    tight.master.chars_per_token = 2.5
    for part in ("rules", "tools"):
        fine = builder(tight).static_tokens("explore")[part]
        coarse = builder(loose).static_tokens("explore")[part]
        assert 2 * coarse - 1 <= fine <= 2 * coarse


def test_static_tokens_do_not_depend_on_role_provider():
    anthropic = app_cfg()
    gemini = app_cfg()
    gemini.roles = gemini.profiles["gemini"]
    assert builder(anthropic).static_tokens("explore") == builder(gemini).static_tokens("explore")


def narrator_models(app):
    roles = [app.roles.narrator, app.alternatives.narrator]
    roles += [profile.narrator for profile in app.profiles.values()]
    models = {role.model for role in roles}
    models |= {key.partition(":")[2] for key in app.llm.narrator_chain}
    return sorted(models)


def test_narrator_models_are_found_in_default_config():
    models = narrator_models(load_settings().app)
    assert {"gemini-3.8-flash", "claude-opus-5-5", "claude-sonnet-5-5"} <= set(models)


def test_context_cap_is_at_least_8000():
    # Ж0 п.0 (решение 1): запас под динамику не меньше 8k
    assert load_settings().app.master.context_cap >= 8000


def test_static_max_plus_context_cap_fits_window_80_of_every_narrator_model():
    # иначе потолок динамики сжимается окном, а вытеснение режет память на ровном месте
    app = load_settings().app
    for model in narrator_models(app):
        window80 = app.context_windows[model] * 80 // 100
        assert STATIC_MAX + app.master.context_cap <= window80, model


def test_static_tokens_ignore_per_provider_cpt():
    app = app_cfg()
    base = builder(app).static_tokens("explore")
    app.master.chars_per_token_by_provider = {"anthropic": 1.0, "gemini": 9.0}
    assert builder(app).static_tokens("explore") == base
