# Б3 (B3-PLAN A4): game/pack_import.py -- прогон import пака, исполнитель со staging-каталогом и
# проверкой настоящим загрузчиком, перенос в campaigns/<id>, проверка выжимки, строка цены.
import json
from pathlib import Path

import pytest
from import_kit import (
    PACK_ID,
    STAGE_NAME,
    bad_pack_call,
    conflict_pack_call,
    import_deps,
    import_task,
    npc_input,
    pack_call,
    pack_files,
    pack_input,
    staged,
    start_input,
    summary_text,
)
from master_kit import scripted, tools_step
from protocol_kit import req

from ai_dm.campaign.importer import PACK_FILES, check_pack_dir
from ai_dm.game.commands import calls_cost_line
from ai_dm.game.hero_create import creation_cost_line
from ai_dm.game.pack_import import (
    ImportExecutor,
    check_summary,
    discard_import,
    finish_import,
    pack_report_lines,
    run_import,
    stage_dir,
)
from ai_dm.master.session import TurnFailed
from ai_dm.protocol.context import CreationContext
from ai_dm.protocol.decision import Invalid
from ai_dm.protocol.requests import parse_request


def run(registry, cfg, tmp_path, steps, run_id="import-t-1"):
    campaigns, folder = staged(tmp_path)
    adapter = scripted(steps)
    deps = import_deps(adapter, registry, cfg, folder)
    ctx = run_import(deps, import_task(), summary_text(), run_id, folder)
    return adapter, ctx, deps, folder


def pack_names(folder):
    return sorted(p.name for p in Path(folder).iterdir() if p.name in PACK_FILES)


def error_payloads(request):
    blocks = request.messages[-1].content
    return [json.loads(b.content) for b in blocks if b.is_error]


# run_import

def test_run_import_fills_ctx_files(registry, cfg, tmp_path):
    _, ctx, _, _ = run(registry, cfg, tmp_path, [tools_step(pack_call())])
    assert ctx.files is not None
    assert ctx.files["campaign.yaml"]["id"] == PACK_ID


def test_run_import_leaves_checked_pack_in_staging(registry, cfg, tmp_path):
    _, _, _, folder = run(registry, cfg, tmp_path, [tools_step(pack_call())])
    assert pack_names(folder) == sorted(PACK_FILES)
    assert check_pack_dir(folder, registry) == []


def test_run_import_makes_one_model_call_for_valid_pack(registry, cfg, tmp_path):
    adapter, _, _, _ = run(registry, cfg, tmp_path, [tools_step(pack_call())])
    assert len(adapter.requests) == 1


def test_run_import_sends_summary_and_campaign_id(registry, cfg, tmp_path):
    adapter, _, _, _ = run(registry, cfg, tmp_path, [tools_step(pack_call())])
    data = json.loads(adapter.requests[0].messages[0].content[0].text)
    assert data == {"campaign_id": PACK_ID, "summary": summary_text()}


def test_run_import_uses_role_import_and_its_model(registry, cfg, tmp_path):
    adapter, _, deps, _ = run(registry, cfg, tmp_path, [tools_step(pack_call())])
    assert adapter.requests[0].role == "import"
    assert adapter.requests[0].model == deps.app_cfg.roles.import_.model


def test_run_import_uses_model_from_deps(registry, cfg, tmp_path):
    campaigns, folder = staged(tmp_path)
    deps = import_deps(scripted([tools_step(pack_call())]), registry, cfg, folder,
                       model="gemini-3.8-flash")
    run_import(deps, import_task(), "текст", "import-t-1", folder)
    assert deps.adapter.requests[0].model == "gemini-3.8-flash"


def test_journal_records_have_import_role_run_id_and_turn_seq_zero(registry, cfg, tmp_path):
    _, _, deps, _ = run(registry, cfg, tmp_path, [tools_step(pack_call())], run_id="import-x-1")
    [record] = deps.journal.read_records()
    assert record["role"] == "import"
    assert record["run_id"] == "import-x-1"
    assert record["turn_seq"] == 0
    assert record["ts"] == "2026-10-08T12:00:00+00:00"


def test_journal_lives_in_staging_import_dir(registry, cfg, tmp_path):
    _, _, _, folder = run(registry, cfg, tmp_path, [tools_step(pack_call())])
    journal_dir = folder / ".import" / "journal"
    assert journal_dir.is_dir()
    assert [p.name for p in journal_dir.glob("calls-*.jsonl")] == ["calls-001.jsonl"]


def test_run_import_writes_no_ledger(registry, cfg, tmp_path):
    _, _, deps, folder = run(registry, cfg, tmp_path, [tools_step(pack_call())])
    assert deps.ledger is None
    assert not list(folder.glob("**/cost*"))


def test_invalid_pack_returns_both_loader_lines_to_the_model(registry, cfg, tmp_path):
    steps = [tools_step(bad_pack_call()), tools_step(pack_call("pack-2"))]
    adapter, ctx, _, _ = run(registry, cfg, tmp_path, steps)
    [payload] = error_payloads(adapter.requests[1])
    assert payload["code"] == "pack_invalid"
    lines = payload["message"].split("\n")
    assert len(lines) == 2
    assert all(line.startswith(f"{PACK_ID}/") for line in lines)
    assert any("start.hero_location" in line for line in lines)
    assert any("ghost" in line for line in lines)
    assert ctx.files is not None


def test_error_lines_have_campaign_id_instead_of_staging_path(registry, cfg, tmp_path):
    steps = [tools_step(bad_pack_call()), tools_step(pack_call("pack-2"))]
    adapter, _, _, folder = run(registry, cfg, tmp_path, steps)
    [payload] = error_payloads(adapter.requests[1])
    assert STAGE_NAME not in payload["message"]
    assert str(folder) not in payload["message"]
    assert f"{PACK_ID}/campaign.yaml" in payload["message"]


def test_staging_has_no_pack_files_after_a_refused_attempt(registry, cfg, tmp_path):
    campaigns, folder = staged(tmp_path)
    adapter = scripted([tools_step(bad_pack_call()), tools_step(bad_pack_call("pack-2")),
                        tools_step(bad_pack_call("pack-3"))])
    deps = import_deps(adapter, registry, cfg, folder)
    with pytest.raises(TurnFailed) as info:
        run_import(deps, import_task(), "текст", "import-t-1", folder)
    assert info.value.reason == "invalid"
    assert pack_names(folder) == []


def test_conflict_5_3_is_refused_with_its_line_then_valid_pack_passes(registry, cfg, tmp_path):
    steps = [tools_step(conflict_pack_call()), tools_step(pack_call("pack-2"))]
    adapter, ctx, _, folder = run(registry, cfg, tmp_path, steps)
    [payload] = error_payloads(adapter.requests[1])
    assert payload["code"] == "pack_invalid"
    assert payload["message"].startswith("npcs.yaml: npc ")
    assert "Мара" in payload["message"]
    assert ctx.files is not None
    assert check_pack_dir(folder, registry) == []


def test_second_attempt_overwrites_files_of_the_first(registry, cfg, tmp_path):
    steps = [tools_step(conflict_pack_call()), tools_step(pack_call("pack-2", name="Второй"))]
    _, _, _, folder = run(registry, cfg, tmp_path, steps)
    assert "Второй" in (folder / "campaign.yaml").read_text(encoding="utf-8")


def test_run_import_refusal_goes_up_as_turn_failed(registry, cfg, tmp_path):
    with pytest.raises(TurnFailed) as info:
        run(registry, cfg, tmp_path, [{"stop": "refusal"}])
    assert info.value.reason == "refusal"


def test_run_import_refusal_leaves_no_pack_files(registry, cfg, tmp_path):
    campaigns, folder = staged(tmp_path)
    deps = import_deps(scripted([{"stop": "refusal"}]), registry, cfg, folder)
    with pytest.raises(TurnFailed):
        run_import(deps, import_task(), "текст", "import-t-1", folder)
    assert pack_names(folder) == []


# ImportExecutor

def test_executor_on_invalid_from_apply_writes_nothing(registry, cfg, tmp_path):
    _, folder = staged(tmp_path)
    ctx = CreationContext(registry, cfg, import_task())
    executor = ImportExecutor(folder, registry, PACK_ID)
    result = executor(ctx, req("set_flag", name="a", value="true"))
    assert isinstance(result, Invalid)
    assert result.code == "not_available_in_mode"
    assert pack_names(folder) == []


def test_executor_accepts_valid_request_and_keeps_files_on_disk(registry, cfg, tmp_path):


    _, folder = staged(tmp_path)
    ctx = CreationContext(registry, cfg, import_task())
    request = parse_request(pack_input(), "pack_import")
    result = ImportExecutor(folder, registry, PACK_ID)(ctx, request)
    assert result.status == "accepted"
    assert ctx.files is not None
    assert pack_names(folder) == sorted(PACK_FILES)


def test_executor_on_broken_pack_returns_pack_invalid_and_clears(registry, cfg, tmp_path):


    _, folder = staged(tmp_path)
    ctx = CreationContext(registry, cfg, import_task())
    request = parse_request(pack_input(start=start_input(hero_location="nowhere")), "pack_import")
    result = ImportExecutor(folder, registry, PACK_ID)(ctx, request)
    assert isinstance(result, Invalid)
    assert result.code == "pack_invalid"
    assert ctx.files is None
    assert pack_names(folder) == []


def test_executor_error_message_uses_campaign_id(registry, cfg, tmp_path):


    _, folder = staged(tmp_path)
    ctx = CreationContext(registry, cfg, import_task())
    request = parse_request(pack_input(start=start_input(hero_location="nowhere")), "pack_import")
    result = ImportExecutor(folder, registry, "my_pack")(ctx, request)
    assert result.message.startswith("my_pack/campaign.yaml")


def test_executor_allows_the_next_attempt_after_a_broken_one(registry, cfg, tmp_path):


    _, folder = staged(tmp_path)
    ctx = CreationContext(registry, cfg, import_task())
    executor = ImportExecutor(folder, registry, PACK_ID)
    bad = parse_request(pack_input(start=start_input(hero_location="nowhere")), "pack_import")
    assert isinstance(executor(ctx, bad), Invalid)
    assert executor(ctx, parse_request(pack_input(), "pack_import")).status == "accepted"


# stage_dir, finish_import, discard_import

def test_stage_dir_is_created_inside_campaigns_dir(tmp_path):
    campaigns = tmp_path / "campaigns"
    campaigns.mkdir()
    folder = stage_dir(campaigns, "my_pack")
    assert folder.is_dir()
    assert folder.parent == campaigns
    assert folder.name.startswith(".import-my_pack-")


def test_stage_dirs_of_two_calls_differ(tmp_path):
    campaigns = tmp_path / "campaigns"
    campaigns.mkdir()
    assert stage_dir(campaigns, "a") != stage_dir(campaigns, "a")


def test_finish_import_renames_staging_to_campaign_id(registry, cfg, tmp_path):
    campaigns, folder = staged(tmp_path)
    run_deps = import_deps(scripted([tools_step(pack_call())]), registry, cfg, folder)
    run_import(run_deps, import_task(), "текст", "import-t-1", folder)
    finish_import(folder, campaigns, PACK_ID)
    assert not folder.exists()
    final = campaigns / PACK_ID
    assert (final / "campaign.yaml").is_file()
    assert (final / ".import" / "journal" / "calls-001.jsonl").is_file()
    assert sorted(p.name for p in campaigns.iterdir()) == [PACK_ID]


def test_discard_import_removes_staging_with_content(registry, cfg, tmp_path):
    campaigns, folder = staged(tmp_path)
    run_deps = import_deps(scripted([tools_step(pack_call())]), registry, cfg, folder)
    run_import(run_deps, import_task(), "текст", "import-t-1", folder)
    discard_import(folder)
    assert not folder.exists()
    assert list(campaigns.iterdir()) == []


def test_discard_import_of_missing_folder_is_silent(tmp_path):
    discard_import(tmp_path / "no_such_dir")


# check_summary

def test_check_summary_empty_text():
    assert check_summary("", 100) == "Выжимка пуста."


def test_check_summary_whitespace_only_is_empty():
    assert check_summary(" \n\t ", 100) == "Выжимка пуста."


def test_check_summary_exactly_max_is_fine():
    assert check_summary("а" * 10, 10) is None


def test_check_summary_over_max_names_limit_and_length():
    assert check_summary("а" * 11, 10) == "Выжимка длиннее 10 символов (11)."


def test_check_summary_normal_text_is_fine():
    assert check_summary(summary_text(), 60000) is None


# calls_cost_line, creation_cost_line

class FakeJournal:
    def __init__(self, records):
        self.records = records
        self.asked = None

    def records_for(self, run_ids):
        self.asked = list(run_ids)
        return self.records


def test_calls_cost_line_sums_cost_and_counts_calls():
    journal = FakeJournal([{"cost_nano": 1_500_000_000}, {"cost_nano": 500_000_000}])
    assert calls_cost_line(journal, ["r1"], "Импорт пака") == "Импорт пака: $2.0000 (2 вызовов)"
    assert journal.asked == ["r1"]


def test_calls_cost_line_without_records_is_zero():
    assert calls_cost_line(FakeJournal([]), [], "Импорт пака") == "Импорт пака: $0.0000 (0 вызовов)"


def test_creation_cost_line_keeps_its_old_text():
    journal = FakeJournal([{"cost_nano": 250_000_000}])
    assert creation_cost_line(journal, ["h"]) == "Создание героя: $0.2500 (1 вызовов)"


def test_calls_cost_line_counts_only_given_runs(registry, cfg, tmp_path):
    campaigns, folder = staged(tmp_path)
    steps = [tools_step(conflict_pack_call()), tools_step(pack_call("pack-2"))]
    deps = import_deps(scripted(steps), registry, cfg, folder)
    run_import(deps, import_task(), "текст", "import-a-1", folder)
    other = import_deps(scripted([tools_step(pack_call())]), registry, cfg, folder)
    other.journal = deps.journal
    run_import(other, import_task(), "текст", "import-b-1", folder)
    assert calls_cost_line(deps.journal, ["import-a-1"], "Импорт пака").endswith("(2 вызовов)")
    assert calls_cost_line(deps.journal, ["import-b-1"], "Импорт пака").endswith("(1 вызовов)")


# pack_report_lines

def test_report_names_pack_folder_files_and_counts():
    lines = pack_report_lines(pack_files())
    assert lines[0].startswith(f"Пак {PACK_ID} записан: campaigns/{PACK_ID}/ — ")
    for name in PACK_FILES:
        assert name in lines[0]
    assert "локаций 2, NPC 2, фракций 1, богов 1" in lines[0]


def test_report_tells_what_to_do_next():
    lines = pack_report_lines(pack_files())
    assert len(lines) == 2
    assert "правьте файлы руками" in lines[1]
    assert f"ai-dm --new --campaign {PACK_ID}" in lines[1]


def test_report_skips_files_that_are_not_written():
    lines = pack_report_lines(pack_files(factions=[], pantheon=[], truths=""))
    assert "factions.yaml" not in lines[0]
    assert "pantheon.yaml" not in lines[0]
    assert "truths.md" not in lines[0]
    assert "фракций 0, богов 0" in lines[0]
    assert "campaign.yaml, world.md, locations.yaml, npcs.yaml" in lines[0]


# пак, который не должен роняться: ошибки загрузчика уходят модели как pack_invalid

def means_of(count):
    return [f"средство {i}" for i in range(count)]


@pytest.mark.parametrize("changes", [
    {"locations": []},
    {"npcs": [npc_input(means=[])]},
    {"npcs": [npc_input(means=means_of(4))]},
], ids=["no-locations", "npc-0-means", "npc-4-means"])
def test_broken_shape_goes_back_to_the_model_as_pack_invalid(registry, cfg, tmp_path, changes):
    steps = [tools_step(pack_call("bad", **changes)), tools_step(pack_call("ok"))]
    adapter, ctx, _, folder = run(registry, cfg, tmp_path, steps)
    [payload] = error_payloads(adapter.requests[1])
    assert payload["code"] == "pack_invalid"
    assert payload["message"].strip()
    assert ctx.files is not None
    assert check_pack_dir(folder, registry) == []


@pytest.mark.parametrize("changes", [
    {"locations": []},
    {"npcs": [npc_input(means=[])]},
    {"npcs": [npc_input(means=means_of(4))]},
])
def test_broken_shape_three_times_fails_as_invalid_without_pack_files(
    registry, cfg, tmp_path, changes
):
    campaigns, folder = staged(tmp_path)
    steps = [tools_step(pack_call(f"bad-{i}", **changes)) for i in range(3)]
    deps = import_deps(scripted(steps), registry, cfg, folder)
    with pytest.raises(TurnFailed) as info:
        run_import(deps, import_task(), "текст", "import-t-1", folder)
    assert info.value.reason == "invalid"
    assert pack_names(folder) == []
