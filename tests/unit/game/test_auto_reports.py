# Ожидаемый API: авто-репорты в GameApp (этап 6а, P0): ход с метками (missing-mechanic,
# limit-exceeded, invalid-death, refusal, invalid-defeat, context_overflow, метки границы сцены)
# при auto_reports=True пишет saves/<world>/issues/<имя>/ и добавляет строку «Записан репорт: ...»;
# две метки -- один каталог; ход без меток -- файла нет; auto_reports=False -- метка в журнале,
# файла нет; ошибка записи не роняет ход; ключи API в файлы репорта не попадают.
import json

import pytest
from game_kit import (
    NOW,
    ReactiveAdapter,
    ScriptThenReactive,
    make_app,
    scripted,
    settings,
    start_combat_call,
    text_step,
    tools_step,
)
from master_kit import flag_call
from world_kit import (
    GRAIL,
    bundle_without_candidates,
    end_turn,
    narrator_turns,
    npc_update_call,
    world_step,
)

from ai_dm.llm.mock import ScriptedAdapter
from ai_dm.llm.types import ChatResponse, ToolCall, Usage


def issues(tmp_path, world_id="w1"):
    folder = tmp_path / world_id / "issues"
    if not folder.exists():
        return []
    return sorted(folder.iterdir())


def text_of(reply):
    return "\n".join(reply.lines)


def meta_of(path):
    return json.loads((path / "meta.json").read_text(encoding="utf-8"))


def unsupported_call(call_id="us-1"):
    return {
        "id": call_id, "name": "unsupported_action",
        "input": {"type": "unsupported_action", "description": "верхом на медведе"},
    }


def too_friendly_call(call_id="nu-1"):
    # сдвиг отношения сверх шага -- урезается с меткой limit-exceeded
    return {
        "id": call_id, "name": "npc_update",
        "input": {"type": "npc_update", "npc_id": "aldric", "attitude_delta": 50},
    }


def groundless_death_call(call_id="nu-2"):
    return {
        "id": call_id, "name": "npc_update",
        "input": {
            "type": "npc_update", "npc_id": "aldric", "status": "dead", "cause": "goal",
            "evidence_ref": "r42",
        },
    }


def play_with(registry, tmp_path, steps, **kw):
    app = make_app(registry, tmp_path, scripted(steps), **kw)
    return app, app.handle("Иду")


# метки хода -- по одной

def test_missing_mechanic_writes_report(registry, tmp_path):
    steps = [tools_step(unsupported_call()), text_step("Медведя нет.")]
    _, reply = play_with(registry, tmp_path, steps, auto_reports=True)
    assert "missing-mechanic" in reply.turn.report_tags
    assert len(issues(tmp_path)) == 1
    assert issues(tmp_path)[0].name.endswith("-t1-missing-mechanic")


def test_limit_exceeded_writes_report(registry, tmp_path):
    steps = [tools_step(too_friendly_call()), text_step("Олдрик хмыкает.")]
    _, reply = play_with(registry, tmp_path, steps, auto_reports=True)
    assert reply.turn.report_tags == ["limit-exceeded"]
    assert issues(tmp_path)[0].name.endswith("-t1-limit-exceeded")


def test_invalid_death_writes_report(registry, tmp_path):
    steps = [tools_step(groundless_death_call()), text_step("Олдрик жив.")]
    _, reply = play_with(registry, tmp_path, steps, auto_reports=True)
    assert reply.turn.report_tags == ["invalid-death"]
    assert issues(tmp_path)[0].name.endswith("-t1-invalid-death")


def test_refusal_writes_report_of_aborted_turn(registry, tmp_path):
    app, reply = play_with(registry, tmp_path, [{"stop": "refusal"}] * 2, auto_reports=True)
    assert reply.turn.committed is False
    assert len(issues(tmp_path)) == 1
    path = issues(tmp_path)[0]
    assert path.name.endswith("-refusal_retry+refusal")
    meta = meta_of(path)
    assert meta["tags"] == ["refusal_retry", "refusal"]
    assert meta["status"] == "aborted"
    assert meta["failure_reason"] == "refusal"
    assert meta["run_ids"] == [reply.turn.run_id]


def test_refusal_report_turn_is_rolled_back(registry, tmp_path):
    app, _ = play_with(registry, tmp_path, [{"stop": "refusal"}] * 2, auto_reports=True)
    assert app.bundle.session.turn_seq == 0
    assert app.pending == "error_menu"
    assert len(issues(tmp_path)) == 1


def test_context_overflow_writes_report(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([text_step()]), auto_reports=True)
    app.runner.app_cfg.master.context_cap = 1
    reply = app.handle("Иду")
    assert reply.turn.report_tags == ["context_overflow"]
    assert issues(tmp_path)[0].name.endswith("-t1-context_overflow")


class BadThenGoodDefeat(ReactiveAdapter):
    # первый defeat_outcome мастера невалиден по смыслу (повтор последствия), второй верный
    def __init__(self):
        super().__init__(defeat="call")
        self.sent = 0

    def complete(self, request):
        response = super().complete(request)
        names = {t.name for t in request.tools}
        called = {
            b.name for m in request.messages for b in m.content if isinstance(b, ToolCall)
        }
        for block in response.content:
            if isinstance(block, ToolCall) and block.name == "defeat_outcome":
                self.sent += 1
                if self.sent == 1:
                    block.input = {"type": "defeat_outcome", "consequences": ["scar", "scar"]}
                return response
        if self.sent == 1 and "defeat_outcome" in names and "defeat_outcome" in called:
            self.sent = 2
            good = ToolCall(
                id="react-fix", name="defeat_outcome",
                input={
                    "type": "defeat_outcome", "consequences": ["scar"], "scar_ability": "str",
                    "scar_text": "Шрам на плече",
                },
            )
            return ChatResponse(
                content=[good], stop_reason="tool_use", usage=Usage(input=100, output=20),
                request_id="react-fix", model=request.model,
            )
        return response


def test_invalid_defeat_writes_report(registry, tmp_path):
    steps = [tools_step(start_combat_call(intent="capture")), text_step("Гоблины рядом.")]
    first = ScriptedAdapter(steps, provider="anthropic", model="claude-opus-5-5")
    adapter = ScriptThenReactive(first, BadThenGoodDefeat())
    app = make_app(registry, tmp_path, adapter, auto_reports=True)
    app.handle("Бью ногой дверь")
    app.bundle.heroes[0].creature.hp_current = 1
    tags = []
    for _ in range(60):
        if app.bundle.session.active_combat is None:
            break
        last = len(app.runner.preview_turn())
        reply = app.handle(str(last))
        tags += reply.turn.report_tags
        if not reply.turn.committed:
            break
    assert tags == ["invalid-defeat"]
    assert len(issues(tmp_path)) == 1
    assert issues(tmp_path)[0].name.endswith("-invalid-defeat")


# несколько меток, нет меток

def test_two_tags_make_one_report_with_both(registry, tmp_path):
    steps = [
        tools_step(too_friendly_call(), unsupported_call()), text_step("Олдрик хмыкает."),
    ]
    _, reply = play_with(registry, tmp_path, steps, auto_reports=True)
    assert set(reply.turn.report_tags) == {"limit-exceeded", "missing-mechanic"}
    assert len(issues(tmp_path)) == 1
    text = (issues(tmp_path)[0] / "report.md").read_text(encoding="utf-8")
    assert "limit-exceeded" in text
    assert "missing-mechanic" in text
    assert set(meta_of(issues(tmp_path)[0])["tags"]) == {"limit-exceeded", "missing-mechanic"}


def test_same_tag_twice_is_listed_once(registry, tmp_path):
    steps = [
        tools_step(unsupported_call("u1"), unsupported_call("u2")), text_step("Медведя нет."),
    ]
    _, reply = play_with(registry, tmp_path, steps, auto_reports=True)
    assert meta_of(issues(tmp_path)[0])["tags"] == ["missing-mechanic"]


def test_turn_without_tags_writes_no_report(registry, tmp_path):
    steps = [tools_step(flag_call("met_guard")), text_step("Стражник кивает.")]
    _, reply = play_with(registry, tmp_path, steps, auto_reports=True)
    assert reply.turn.report_tags == []
    assert issues(tmp_path) == []
    assert "Записан репорт" not in text_of(reply)


def test_report_line_has_path_of_dir(registry, tmp_path):
    steps = [tools_step(unsupported_call()), text_step("Медведя нет.")]
    _, reply = play_with(registry, tmp_path, steps, auto_reports=True)
    assert f"Записан репорт: {issues(tmp_path)[0]}" in text_of(reply)


def test_auto_reports_are_on_by_default(registry, tmp_path):
    steps = [tools_step(unsupported_call()), text_step("Медведя нет.")]
    _, reply = play_with(registry, tmp_path, steps)
    assert len(issues(tmp_path)) == 1


def test_auto_report_meta_is_not_manual(registry, tmp_path):
    steps = [tools_step(unsupported_call()), text_step("Медведя нет.")]
    play_with(registry, tmp_path, steps, auto_reports=True)
    meta = meta_of(issues(tmp_path)[0])
    assert meta["manual"] is False
    assert meta["status"] == "committed"
    assert meta["turn_seq"] == 1


def test_error_menu_reply_has_report_line_and_menu(registry, tmp_path):
    _, reply = play_with(registry, tmp_path, [{"stop": "refusal"}] * 2, auto_reports=True)
    assert "Записан репорт" in text_of(reply)
    assert reply.menu == ["retry", "switch_model", "save_and_quit"]


# auto_reports=False

def test_auto_reports_off_has_tag_in_result_but_no_file(registry, tmp_path):
    steps = [tools_step(unsupported_call()), text_step("Медведя нет.")]
    _, reply = play_with(registry, tmp_path, steps, auto_reports=False)
    assert "missing-mechanic" in reply.turn.report_tags
    assert issues(tmp_path) == []
    assert "Записан репорт" not in text_of(reply)


def test_auto_reports_off_has_tag_in_journal_but_no_file(registry, tmp_path):
    # в журнал вызова попадает метка context_overflow
    app = make_app(registry, tmp_path, scripted([text_step()]), auto_reports=False)
    app.runner.app_cfg.master.context_cap = 1
    reply = app.handle("Иду")
    assert reply.turn.report_tags == ["context_overflow"]
    assert issues(tmp_path) == []
    records = [r for r in app.journal.read_records() if r["role"] == "narrator"]
    assert any("context_overflow" in r["report_tags"] for r in records)


# метка от границы сцены

def test_world_boundary_tag_is_in_report_of_the_turn(registry, tmp_path):
    from ai_dm.game.app import GameApp

    bundle = bundle_without_candidates(registry, cfg_of(registry))
    world_id = bundle.world.world_id
    steps = world_step(
        npc_update_call(
            "aldric", GRAIL, status="dead", cause="goal", evidence_ref="r42"
        )
    )
    world = scripted(steps)
    narrator = scripted(narrator_turns(end_turn(1, flag="grail_seen")))
    app = GameApp(
        settings(), registry, bundle, narrator, saves_root=tmp_path, sleeper=lambda s: None,
        now=lambda: NOW, run_tag="t", world_adapter=world, auto_reports=True,
    )
    app.runner.new_summarizer_session = lambda: None
    reply = app.handle("Иду")
    assert reply.turn.committed is True
    assert "invalid-death" in reply.turn.report_tags
    assert len(issues(tmp_path, world_id)) == 1
    path = issues(tmp_path, world_id)[0]
    assert path.name.endswith("-invalid-death")
    meta = meta_of(path)
    assert meta["tags"] == ["invalid-death"]
    # run_id границы -- в списке вызовов хода
    assert any(run_id.startswith("bnd-") for run_id in meta["run_ids"])


def cfg_of(registry):
    return settings().rules


# ошибка записи не роняет ход

def test_write_error_does_not_lose_turn(registry, tmp_path):
    (tmp_path / "w1").mkdir()
    (tmp_path / "w1" / "issues").write_text("не каталог", encoding="utf-8")
    steps = [tools_step(unsupported_call()), text_step("Медведя нет.")]
    app, reply = play_with(registry, tmp_path, steps, auto_reports=True)
    assert reply.turn.committed is True
    assert reply.narration == "Медведя нет."
    assert app.bundle.session.turn_seq == 1
    assert "Репорт не записан" in text_of(reply)
    assert app.pending is None


def test_write_error_line_hides_api_key(registry, tmp_path):
    # строка из secrets в сообщении OSError маскируется через redact
    (tmp_path / "w1").mkdir()
    (tmp_path / "w1" / "issues").write_text("не каталог", encoding="utf-8")
    steps = [tools_step(unsupported_call()), text_step("Медведя нет.")]
    app = make_app(registry, tmp_path, scripted(steps), auto_reports=True)
    app.secrets = (str(tmp_path),)
    reply = app.handle("Иду")
    assert "Репорт не записан" in text_of(reply)
    assert str(tmp_path) not in text_of(reply)


# ключи API не попадают в файлы репорта

@pytest.mark.parametrize("manual", [False, True])
def test_report_files_have_no_api_keys(registry, tmp_path, monkeypatch, manual):
    anthropic = "sk-ant-MARKER-anthropic-9f3a1c"
    gemini = "AIza-MARKER-gemini-7d2b5e"
    monkeypatch.setenv("ANTHROPIC_API_KEY", anthropic)
    monkeypatch.setenv("GEMINI_API_KEY", gemini)
    steps = [tools_step(unsupported_call()), text_step("Медведя нет.")]
    app, _ = play_with(registry, tmp_path, steps, auto_reports=True)
    if manual:
        app.handle("/report баг")
    assert issues(tmp_path)
    for path in issues(tmp_path):
        for file in path.rglob("*"):
            if file.is_file():
                content = file.read_text(encoding="utf-8")
                assert anthropic not in content
                assert gemini not in content
