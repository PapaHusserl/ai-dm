# Б3 (B3-PLAN A1): режим pack_import в MasterSession -- единственный вызов pack, подсказка на
# пустой ответ, бюджет повторов, журнал turn_seq=0 с ролью import.
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

from import_kit import bad_pack_call, import_task, pack_call, tone_input  # noqa: E402
from master_kit import app_cfg, make_session, scripted, text_step, tools_step  # noqa: E402

from ai_dm.master.importer import ImportPromptBuilder  # noqa: E402
from ai_dm.master.session import (  # noqa: E402
    EMPTY_NOTES,
    REQUIRED_BY_MODE,
    SINGLE_SHOT_MODES,
    MasterSession,
    TurnFailed,
)
from ai_dm.protocol.apply import apply  # noqa: E402
from ai_dm.protocol.context import CreationContext  # noqa: E402

NOTE_IMPORT = "Пустой ответ. Вызови инструмент pack."


def unparsable(call_id):
    return pack_call(call_id, tone=tone_input(violence="ужасно"))


def run(steps, tmp_path, registry, cfg, **kw):
    adapter = scripted(steps)
    session, journal, ledger, _ = make_session(
        adapter, tmp_path, role="import", builder=ImportPromptBuilder(app_cfg()), **kw,
    )
    ctx = CreationContext(registry, cfg, import_task())
    result = session.run(ctx, "выжимка", apply, "pack_import")
    return adapter, ctx, result, journal


def test_valid_pack_makes_one_model_call(tmp_path, registry, cfg):
    steps = [tools_step(pack_call()), text_step("Готово.")]
    adapter, ctx, _, _ = run(steps, tmp_path, registry, cfg)
    assert len(adapter.requests) == 1
    assert ctx.files is not None


def test_valid_pack_result_has_one_accepted_decision(tmp_path, registry, cfg):
    _, _, result, _ = run([tools_step(pack_call())], tmp_path, registry, cfg)
    assert [d.status for d in result.decisions] == ["accepted"]
    assert result.rounds == 1


def test_mode_constants_are_registered():
    assert REQUIRED_BY_MODE["pack_import"] == "pack"
    assert "pack_import" in SINGLE_SHOT_MODES
    assert EMPTY_NOTES["pack_import"] == NOTE_IMPORT


def test_required_tool_is_pack(registry, cfg):
    session = MasterSession(
        scripted([]), app_cfg(), role="import", builder=ImportPromptBuilder(app_cfg())
    )
    ctx = CreationContext(registry, cfg, import_task())
    assert not hasattr(ctx, "bundle")
    assert session.required_tool(ctx, "pack_import") == "pack"


def test_empty_answer_gets_pack_note(tmp_path, registry, cfg):
    adapter, ctx, _, _ = run(
        [{"text": " "}, tools_step(pack_call())], tmp_path, registry, cfg
    )
    assert adapter.requests[1].messages[-1].content[0].text == NOTE_IMPORT
    assert ctx.files is not None


def test_text_without_tool_names_the_tool(tmp_path, registry, cfg):
    adapter, _, _, _ = run(
        [text_step("Расскажу своими словами."), tools_step(pack_call())], tmp_path, registry, cfg
    )
    assert "pack" in adapter.requests[1].messages[-1].content[0].text


def test_invalid_pack_goes_back_as_error_then_valid_passes(tmp_path, registry, cfg):
    # неразбираемый ввод (значение оси вне списка) идёт назад модели ошибкой
    broken = unparsable("pack-1")
    adapter, ctx, _, _ = run([tools_step(broken), tools_step(pack_call("pack-2"))],
                             tmp_path, registry, cfg)
    assert len(adapter.requests) == 2
    block = adapter.requests[1].messages[-1].content[0]
    assert block.is_error is True
    assert ctx.files is not None


def test_three_invalid_answers_fail_as_invalid(tmp_path, registry, cfg):
    budget = app_cfg().retry.invalid_retries
    steps = [tools_step(unparsable(f"p-{i}")) for i in range(budget + 1)]
    with pytest.raises(TurnFailed) as info:
        run(steps, tmp_path, registry, cfg)
    assert info.value.reason == "invalid"
    assert budget == 2


def test_no_tool_three_times_fails_as_invalid(tmp_path, registry, cfg):
    budget = app_cfg().retry.invalid_retries
    with pytest.raises(TurnFailed) as info:
        run([text_step("Текст.")] * (budget + 1), tmp_path, registry, cfg)
    assert info.value.reason == "invalid"


def test_refusal_fails_with_tag(tmp_path, registry, cfg):
    with pytest.raises(TurnFailed) as info:
        run([{"stop": "refusal"}], tmp_path, registry, cfg)
    assert info.value.reason == "refusal"
    assert info.value.report_tags == ["refusal"]


def test_max_tokens_is_retried_with_shorter_hint(tmp_path, registry, cfg):
    steps = [{"stop": "max_tokens", "text": "Начало"}, tools_step(pack_call())]
    adapter, ctx, _, _ = run(steps, tmp_path, registry, cfg)
    assert "короче" in adapter.requests[1].messages[-1].content[0].text
    assert ctx.files is not None


def test_wrong_tool_in_import_mode_is_not_available(tmp_path, registry, cfg):
    flag = {"id": "f1", "name": "set_flag",
            "input": {"type": "set_flag", "name": "a", "value": "x"}}
    adapter, _, _, _ = run([tools_step(flag), tools_step(pack_call())], tmp_path, registry, cfg)
    block = adapter.requests[1].messages[-1].content[0]
    assert json.loads(block.content)["code"] == "not_available_in_mode"


def test_journal_records_have_role_import_and_turn_seq_zero(tmp_path, registry, cfg):
    steps = [tools_step(unparsable("p-1")), tools_step(pack_call("p-2"))]
    _, _, _, journal = run(steps, tmp_path, registry, cfg, run_id="import-1")
    records = journal.read_records()
    assert len(records) == 2
    assert {r["role"] for r in records} == {"import"}
    assert {r["turn_seq"] for r in records} == {0}
    assert {r["run_id"] for r in records} == {"import-1"}


def test_bad_pack_call_is_a_valid_request_for_apply(tmp_path, registry, cfg):
    # ссылки и 5.3 проверяет исполнитель слоя game, не protocol: apply пропускает такой пак
    _, ctx, _, _ = run([tools_step(bad_pack_call())], tmp_path, registry, cfg)
    assert ctx.files is not None
