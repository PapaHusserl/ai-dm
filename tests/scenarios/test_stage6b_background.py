# Критерий Б0 (B0-PLAN, Б0-П1): свободная предыстория на мок-модели.
# Валидная -> BackgroundSpec -> герой собирается build_character; три невалидные (бюджет,
# навык класса, черта не origin) -> ошибка модели и повтор; без инструмента N раз ->
# TurnFailed("invalid"); refusal; ручная правка даёт те же тексты. Живых вызовов нет.
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "master"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "rules"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "ui"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "game"))

from hero_kit import deps  # noqa: E402
from master_kit import app_cfg, scripted, text_step, tools_step  # noqa: E402
from test_builder import fighter_choices  # noqa: E402
from ui_kit import cli, write_script  # noqa: E402

from ai_dm.game.hero_create import propose_background  # noqa: E402
from ai_dm.master.session import TurnFailed  # noqa: E402
from ai_dm.protocol.context import BackgroundTask  # noqa: E402
from ai_dm.rules.builder import background_check, build_character  # noqa: E402
from ai_dm.state.hero import BackgroundSpec, HeroState  # noqa: E402

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
CLASS_SKILLS = ["perception", "survival"]


def spec_call(call_id, **changes):
    data = {
        "type": "background_spec", "name": "Бывший цирковой акробат",
        "abilities": ["dex", "con", "cha"], "skills": ["acrobatics", "performance"],
        "tool": "thieves_tools", "feat": "alert", "equipment": ["crowbar"], "gold_cp": 1000,
        "description": "Вырос в бродячем цирке.",
    }
    data.update(changes)
    return {"id": call_id, "name": "background_spec", "input": data}


def propose(registry, cfg, tmp_path, steps):
    adapter = scripted(steps)
    hero_deps = deps(adapter, registry, cfg, tmp_path)
    task = BackgroundTask("fighter", CLASS_SKILLS)
    spec = propose_background(hero_deps, task, "Бывший цирковой акробат", "hero-1")
    return adapter, spec, hero_deps.journal, hero_deps.ledger


def error_texts(request):
    # тексты tool_result is_error в последнем сообщении запроса
    blocks = request.messages[-1].content
    return [json.loads(b.content)["message"] for b in blocks if b.is_error]


def test_valid_background_builds_a_hero(registry, cfg, tmp_path):
    adapter, spec, _, _ = propose(registry, cfg, tmp_path, [tools_step(spec_call("bg-1"))])
    assert len(adapter.requests) == 1
    choices = fighter_choices(background=spec, background_bonus={"dex": 2, "cha": 1})
    hero = build_character(choices, registry)
    assert isinstance(hero, HeroState)
    assert "alert" in hero.sheet.feats
    assert {"acrobatics", "performance"} <= set(hero.sheet.skill_proficiencies)
    assert "thieves_tools" in hero.sheet.tool_proficiencies
    assert hero.sheet.background.name == "Бывший цирковой акробат"
    assert hero.money_cp >= 1000
    assert hero.sheet.background.description == "Вырос в бродячем цирке."


@pytest.mark.parametrize(
    "changes, fragment",
    [
        ({"equipment": [], "gold_cp": 6000}, "50 зм"),
        ({"skills": ["perception", "performance"]}, "навык класса уже даёт предыстория"),
        ({"feat": "defense"}, "origin"),
    ],
    ids=["budget", "class-skill", "feat-not-origin"],
)
def test_invalid_background_is_error_then_retry_is_accepted(
    registry, cfg, tmp_path, changes, fragment
):
    steps = [tools_step(spec_call("bg-1", **changes)), tools_step(spec_call("bg-2"))]
    adapter, spec, journal, ledger = propose(registry, cfg, tmp_path, steps)
    assert len(adapter.requests) == 2
    texts = error_texts(adapter.requests[1])
    assert len(texts) == 1
    assert fragment in texts[0]
    assert spec is not None
    records = journal.read_records()
    assert [r["role"] for r in records] == ["narrator", "narrator"]
    assert {r["run_id"] for r in records} == {"hero-1"}
    assert {r["turn_seq"] for r in records} == {0}
    assert [line["role"] for line in ledger.session_lines] == ["narrator", "narrator"]


def test_three_invalid_in_a_row_fail_as_invalid(registry, cfg, tmp_path):
    budget = app_cfg().retry.invalid_retries
    steps = [tools_step(spec_call(f"bg-{i}", gold_cp=9000)) for i in range(budget + 1)]
    with pytest.raises(TurnFailed) as info:
        propose(registry, cfg, tmp_path, steps)
    assert info.value.reason == "invalid"


def test_no_tool_n_times_fails_as_invalid(registry, cfg, tmp_path):
    budget = app_cfg().retry.invalid_retries
    steps = [text_step("Расскажу своими словами.")] * (budget + 1)
    with pytest.raises(TurnFailed) as info:
        propose(registry, cfg, tmp_path, steps)
    assert info.value.reason == "invalid"


def test_refusal_fails_with_refusal_tag(registry, cfg, tmp_path):
    with pytest.raises(TurnFailed) as info:
        propose(registry, cfg, tmp_path, [{"stop": "refusal"}])
    assert info.value.reason == "refusal"
    assert info.value.report_tags == ["refusal"]


def test_manual_edit_gives_same_texts_as_model_path(registry, cfg, tmp_path):
    changes = {"equipment": [], "gold_cp": 6000, "feat": "defense"}
    steps = [tools_step(spec_call("bg-1", **changes)), tools_step(spec_call("bg-2"))]
    adapter, _, _, _ = propose(registry, cfg, tmp_path, steps)
    from_model = error_texts(adapter.requests[1])[0].split("; ")
    data = spec_call("x", **changes)["input"]
    del data["type"]
    manual = background_check(BackgroundSpec.model_validate(data), registry, CLASS_SKILLS)[1]
    assert manual == from_model
    assert len(manual) == 2


def test_manual_edit_long_description_gives_same_code_and_text(registry, cfg, tmp_path):
    from ai_dm.rules.builder import background_check

    changes = {"description": "а" * 301}
    steps = [tools_step(spec_call("bg-1", **changes)), tools_step(spec_call("bg-2"))]
    adapter, _, _, _ = propose(registry, cfg, tmp_path, steps)
    model_text = error_texts(adapter.requests[1])[0]
    data = spec_call("x", **changes)["input"]
    del data["type"]
    codes, messages = background_check(BackgroundSpec.model_validate(data), registry, CLASS_SKILLS)
    assert codes == ["description_too_long"]
    assert "; ".join(messages) == model_text


def test_negative_gold_is_error_then_retry_is_accepted(registry, cfg, tmp_path):
    steps = [
        tools_step(spec_call("bg-1", equipment=[], gold_cp=-500)), tools_step(spec_call("bg-2")),
    ]
    adapter, spec, _, _ = propose(registry, cfg, tmp_path, steps)
    assert "отрицательным" in error_texts(adapter.requests[1])[0]
    assert spec is not None


def test_new_world_with_preset_heroic_starts_and_tone_shows_its_axes(tmp_path):
    script = write_script(tmp_path / "one.yaml", "Мир оживает.")
    argv = ["--new", "--hero", "arn", "--seed", "3", "--preset", "heroic", "--mock", str(script),
            "--saves", str(tmp_path / "saves")]
    code, out = cli(argv, ["/tone", "/quit"], env={})
    assert code == 0
    assert "пресет heroic" in out.text
    assert "реалистично" in out.text
    assert "намёки" in out.text
    assert "умеренно" in out.text
