# Б0-П1 (B0-PLAN A4, три правки master/session.py): режим hero_background в MasterSession.
# Ранний выход после принятого background_spec, required_tool без бандла, журнал turn_seq=0.
import json

import pytest
from master_kit import app_cfg, make_session, scripted, text_step, tools_step

from ai_dm.master.hero import HeroPromptBuilder
from ai_dm.master.session import MasterSession, TurnFailed
from ai_dm.protocol.apply import apply
from ai_dm.protocol.context import BackgroundTask, CreationContext

CLASS_SKILLS = ["perception", "survival"]


def spec_call(call_id="bg-1", **changes):
    data = {
        "type": "background_spec", "name": "Бывший цирковой акробат",
        "abilities": ["dex", "con", "cha"], "skills": ["acrobatics", "performance"],
        "tool": "thieves_tools", "feat": "alert", "equipment": ["crowbar"], "gold_cp": 1000,
        "description": "Вырос в цирке.",
    }
    data.update(changes)
    return {"id": call_id, "name": "background_spec", "input": data}


def run(steps, tmp_path, registry, cfg, **kw):
    adapter = scripted(steps)
    session, journal, ledger, _ = make_session(
        adapter, tmp_path, role="narrator", builder=HeroPromptBuilder(app_cfg()), **kw,
    )
    ctx = CreationContext(registry, cfg, BackgroundTask("fighter", CLASS_SKILLS))
    result = session.run(ctx, "акробат", apply, "hero_background")
    return adapter, ctx, result, journal, ledger


# ранний выход

def test_accepted_background_makes_one_model_call(tmp_path, registry, cfg):
    steps = [tools_step(spec_call()), text_step("Готово.")]
    adapter, _, _, _, _ = run(steps, tmp_path, registry, cfg)
    assert len(adapter.requests) == 1


def test_accepted_background_is_written_to_ctx(tmp_path, registry, cfg):
    _, ctx, _, _, _ = run([tools_step(spec_call())], tmp_path, registry, cfg)
    assert ctx.background.name == "Бывший цирковой акробат"


def test_accepted_background_result_has_one_accepted_decision(tmp_path, registry, cfg):
    _, _, result, _, _ = run([tools_step(spec_call())], tmp_path, registry, cfg)
    assert [d.status for d in result.decisions] == ["accepted"]
    assert result.rounds == 1


def test_invalid_then_valid_makes_two_calls_and_error_is_shown(tmp_path, registry, cfg):
    steps = [
        tools_step(spec_call("bg-1", gold_cp=9000)),
        tools_step(spec_call("bg-2")),
    ]
    adapter, ctx, _, _, _ = run(steps, tmp_path, registry, cfg)
    assert len(adapter.requests) == 2
    block = adapter.requests[1].messages[-1].content[0]
    assert block.is_error is True
    assert block.call_id == "bg-1"
    assert "50 зм" in json.loads(block.content)["message"]
    assert ctx.background is not None


def test_valid_call_next_to_invalid_one_does_not_end_the_run(tmp_path, registry, cfg):
    steps = [
        tools_step(spec_call("bg-1"), spec_call("bg-2")),
        text_step("Готово."),
    ]
    adapter, ctx, _, _, _ = run(steps, tmp_path, registry, cfg)
    # второй вызов в том же ответе -- already_done (is_error): ответ невалидный, цикл идёт дальше
    assert len(adapter.requests) == 2
    assert ctx.background is not None


def test_wrong_tool_in_hero_mode_is_not_available(tmp_path, registry, cfg):
    flag_input = {"type": "set_flag", "name": "a", "value": "x"}
    flag = {"id": "f1", "name": "set_flag", "input": flag_input}
    adapter, _, _, _, _ = run([tools_step(flag), tools_step(spec_call())], tmp_path, registry, cfg)
    block = adapter.requests[1].messages[-1].content[0]
    assert block.is_error is True
    assert json.loads(block.content)["code"] == "not_available_in_mode"


def test_background_spec_in_explore_mode_is_not_available(tmp_path, registry, cfg):
    from master_kit import make_ctx

    adapter = scripted([tools_step(spec_call()), text_step("Рассказ.")])
    session, _, _, _ = make_session(adapter, tmp_path)
    session.run(make_ctx(registry, cfg), "Иду.", apply, "explore")
    block = adapter.requests[1].messages[-1].content[0]
    assert json.loads(block.content)["code"] == "not_available_in_mode"


# сбои

def test_no_tool_calls_fail_as_invalid(tmp_path, registry, cfg):
    budget = app_cfg().retry.invalid_retries
    steps = [text_step("Расскажу так.")] * (budget + 1)
    with pytest.raises(TurnFailed) as info:
        run(steps, tmp_path, registry, cfg)
    assert info.value.reason == "invalid"


def test_empty_answer_hint_names_the_tool(tmp_path, registry, cfg):
    adapter = scripted([{"text": " "}, tools_step(spec_call())])
    session, _, _, _ = make_session(
        adapter, tmp_path, role="narrator", builder=HeroPromptBuilder(app_cfg()),
    )
    ctx = CreationContext(registry, cfg, BackgroundTask("fighter"))
    session.run(ctx, "акробат", apply, "hero_background")
    hint = adapter.requests[1].messages[-1].content[0].text
    assert "background_spec" in hint


def test_refusal_fails_with_tag(tmp_path, registry, cfg):
    with pytest.raises(TurnFailed) as info:
        run([{"stop": "refusal"}], tmp_path, registry, cfg)
    assert info.value.reason == "refusal"
    assert info.value.report_tags == ["refusal"]


def test_max_tokens_is_retried_with_shorter_hint(tmp_path, registry, cfg):
    steps = [{"stop": "max_tokens", "text": "Начало"}, tools_step(spec_call())]
    adapter, ctx, _, _, _ = run(steps, tmp_path, registry, cfg)
    assert len(adapter.requests) == 2
    assert "короче" in adapter.requests[1].messages[-1].content[0].text
    assert ctx.background is not None


# required_tool и журнал

def test_required_tool_in_hero_mode_does_not_touch_bundle(tmp_path, registry, cfg):
    adapter = scripted([])
    session = MasterSession(adapter, app_cfg(), role="narrator")
    ctx = CreationContext(registry, cfg, BackgroundTask("fighter"))
    assert not hasattr(ctx, "bundle")
    assert session.required_tool(ctx, "hero_background") == "background_spec"


def test_journal_records_have_turn_seq_zero_role_narrator_and_hero_run_id(tmp_path, registry, cfg):
    steps = [tools_step(spec_call("bg-1", gold_cp=9000)), tools_step(spec_call("bg-2"))]
    _, _, _, journal, _ = run(steps, tmp_path, registry, cfg, run_id="hero-1")
    records = journal.read_records()
    assert len(records) == 2
    assert {r["role"] for r in records} == {"narrator"}
    assert {r["turn_seq"] for r in records} == {0}
    assert {r["run_id"] for r in records} == {"hero-1"}


def test_required_tool_in_combat_narrate_defeat_pending_is_defeat_outcome(registry, cfg):
    from master_kit import combat_ctx

    ctx = combat_ctx(registry, cfg, mode="combat_narrate", outcome="defeat_pending")
    session = MasterSession(scripted([]), app_cfg())
    assert session.required_tool(ctx, "combat_narrate") == "defeat_outcome"


def test_required_tool_defeat_pending_is_ignored_outside_combat_narrate(registry, cfg):
    from master_kit import combat_ctx

    ctx = combat_ctx(registry, cfg, mode="combat_classify", outcome="defeat_pending")
    session = MasterSession(scripted([]), app_cfg())
    assert session.required_tool(ctx, "combat_classify") == "player_action"


def test_journal_ts_uses_given_now(tmp_path, registry, cfg):
    from master_kit import NOW

    _, _, _, journal, _ = run([tools_step(spec_call())], tmp_path, registry, cfg)
    assert journal.read_records()[0]["ts"] == NOW.isoformat()


def test_required_tool_in_combat_narrate_without_combat_is_none(registry, cfg):
    from master_kit import make_ctx

    ctx = make_ctx(registry, cfg, mode="combat_narrate")
    session = MasterSession(scripted([]), app_cfg())
    assert session.required_tool(ctx, "combat_narrate") is None


# Б1а: режим hero_sheet

import sys  # noqa: E402
from pathlib import Path  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

from hero_kit import known, sheet_call  # noqa: E402

from ai_dm.protocol.context import SheetTask  # noqa: E402

NOTE_SHEET = "Пустой ответ. Вызови инструмент hero_sheet."


def sheet_ctx(registry, cfg):
    task = SheetTask(known=known(npcs=["innkeeper"], locations=["vale"]), taken_names=["Гарт"])
    return CreationContext(registry, cfg, task)


def run_sheet(steps, tmp_path, registry, cfg, **kw):
    adapter = scripted(steps)
    session, journal, ledger, _ = make_session(
        adapter, tmp_path, role="narrator", builder=HeroPromptBuilder(app_cfg()), **kw,
    )
    ctx = sheet_ctx(registry, cfg)
    result = session.run(ctx, "воин-сирота", apply, "hero_sheet")
    return adapter, ctx, result, journal, ledger


def test_accepted_sheet_makes_one_model_call(tmp_path, registry, cfg):
    steps = [tools_step(sheet_call()), text_step("Готово.")]
    adapter, ctx, _, _, _ = run_sheet(steps, tmp_path, registry, cfg)
    assert len(adapter.requests) == 1
    assert ctx.sheet is not None


def test_sheet_request_offers_only_hero_sheet(tmp_path, registry, cfg):
    adapter, _, _, _, _ = run_sheet([tools_step(sheet_call())], tmp_path, registry, cfg)
    assert [t.name for t in adapter.requests[0].tools] == ["hero_sheet"]


def test_sheet_request_carries_description(tmp_path, registry, cfg):
    adapter, _, _, _, _ = run_sheet([tools_step(sheet_call())], tmp_path, registry, cfg)
    data = json.loads(adapter.requests[0].messages[0].content[0].text)
    assert data["description"] == "воин-сирота"


def test_invalid_sheet_is_error_then_retry_is_accepted(tmp_path, registry, cfg):
    steps = [tools_step(sheet_call("s-1", motive="")), tools_step(sheet_call("s-2"))]
    adapter, ctx, _, _, _ = run_sheet(steps, tmp_path, registry, cfg)
    assert len(adapter.requests) == 2
    blocks = adapter.requests[1].messages[-1].content
    errors = [json.loads(b.content)["message"] for b in blocks if b.is_error]
    assert len(errors) == 1
    assert "мотив" in errors[0]
    assert ctx.sheet is not None


def test_three_invalid_sheets_fail_as_invalid(tmp_path, registry, cfg):
    budget = app_cfg().retry.invalid_retries
    steps = [tools_step(sheet_call(f"s-{i}", motive="")) for i in range(budget + 1)]
    with pytest.raises(TurnFailed) as info:
        run_sheet(steps, tmp_path, registry, cfg)
    assert info.value.reason == "invalid"


def test_sheet_empty_answer_hint_names_the_tool(tmp_path, registry, cfg):
    adapter = scripted([{"text": " "}, tools_step(sheet_call())])
    session, _, _, _ = make_session(
        adapter, tmp_path, role="narrator", builder=HeroPromptBuilder(app_cfg()),
    )
    session.run(sheet_ctx(registry, cfg), "воин", apply, "hero_sheet")
    assert adapter.requests[1].messages[-1].content[0].text == NOTE_SHEET


def test_sheet_without_tool_n_times_fails_as_invalid(tmp_path, registry, cfg):
    budget = app_cfg().retry.invalid_retries
    steps = [text_step("Расскажу так.")] * (budget + 1)
    with pytest.raises(TurnFailed) as info:
        run_sheet(steps, tmp_path, registry, cfg)
    assert info.value.reason == "invalid"


def test_sheet_refusal_fails_with_tag(tmp_path, registry, cfg):
    with pytest.raises(TurnFailed) as info:
        run_sheet([{"stop": "refusal"}], tmp_path, registry, cfg)
    assert info.value.reason == "refusal"
    assert info.value.report_tags == ["refusal"]


def test_required_tool_in_sheet_mode_is_hero_sheet(registry, cfg):
    session = MasterSession(scripted([]), app_cfg(), role="narrator")
    ctx = sheet_ctx(registry, cfg)
    assert not hasattr(ctx, "bundle")
    assert session.required_tool(ctx, "hero_sheet") == "hero_sheet"


def test_sheet_journal_records_are_turn_zero_narrator_hero_run(tmp_path, registry, cfg):
    steps = [tools_step(sheet_call("s-1", motive="")), tools_step(sheet_call("s-2"))]
    _, _, _, journal, _ = run_sheet(steps, tmp_path, registry, cfg, run_id="hero-7")
    records = journal.read_records()
    assert len(records) == 2
    assert {r["role"] for r in records} == {"narrator"}
    assert {r["turn_seq"] for r in records} == {0}
    assert {r["run_id"] for r in records} == {"hero-7"}
