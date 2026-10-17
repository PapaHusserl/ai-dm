# ТО (docs/plan-to.md §1 п.4, T9): один авто-репорт на попытку хода и модель. Ключ
# (turn_seq, теги, failure_reason, модель) оборванной попытки; повтор с тем же ключом -- без
# репорта и без строки; committed-ходы (gold_repeat) пишутся всегда; load() сбрасывает память.
import json

from game_kit import FactorySpy, make_app, scripted, text_step, tools_step
from test_tm_auto_reports import gold_call

from ai_dm.llm.errors import MissingKey
from ai_dm.llm.mock import ScriptedAdapter

HARD = {"stop": "refusal", "stop_detail": "PROHIBITED_CONTENT"}
FLASH = "gemini-3.8-flash"
ARGON = "gemini-4-argon"
PREVIEW = "gemini-3-flash-preview"


def issues(tmp_path, world_id="w1"):
    folder = tmp_path / world_id / "issues"
    if not folder.exists():
        return []
    return sorted(folder.iterdir())


def meta_of(path):
    return json.loads((path / "meta.json").read_text(encoding="utf-8"))


def text_of(reply):
    return "\n".join(reply.lines)


class Factory:
    def __init__(self, steps=None):
        self.steps = steps or {}

    def __call__(self, provider, model):
        steps = list(self.steps.get(model, [text_step("Дошли.")]))
        return ScriptedAdapter(steps, provider=provider, model=model)


def failed_app(registry, tmp_path, steps, model=FLASH, factory=None, **kw):
    adapter = ScriptedAdapter(steps, provider="gemini", model=model)
    app = make_app(
        registry, tmp_path, adapter, adapter_factory=factory or Factory(), auto_reports=True, **kw,
    )
    app.refusal_chain = False
    reply = app.handle("Иду")
    assert app.pending == "error_menu"
    return app, reply


# повтор на той же модели

def test_hard_refusal_writes_report(registry, tmp_path):
    _, reply = failed_app(registry, tmp_path, [HARD])
    assert len(issues(tmp_path)) == 1
    assert issues(tmp_path)[0].name.endswith("-refusal")
    assert "Записан репорт" in text_of(reply)


def test_retry_on_same_model_writes_no_new_report(registry, tmp_path):
    app, _ = failed_app(registry, tmp_path, [HARD, HARD])
    reply = app.choose("retry")
    assert len(issues(tmp_path)) == 1
    assert "Записан репорт" not in text_of(reply)


def test_third_retry_on_same_model_still_no_new_report(registry, tmp_path):
    app, _ = failed_app(registry, tmp_path, [HARD, HARD, HARD])
    app.choose("retry")
    app.choose("retry")
    assert len(issues(tmp_path)) == 1


def test_retry_after_switch_model_writes_report_with_new_model(registry, tmp_path):
    app, _ = failed_app(registry, tmp_path, [HARD], factory=Factory({ARGON: [HARD]}))
    app.choose("switch_model")
    app.choose(f"gemini:{ARGON}")
    reply = app.choose("retry")
    found = issues(tmp_path)
    assert len(found) == 2
    assert "Записан репорт" in text_of(reply)
    assert [meta_of(p)["model"] for p in found] == [FLASH, ARGON] or {
        meta_of(p)["model"] for p in found
    } == {FLASH, ARGON}


def test_next_turn_with_same_refusal_writes_report(registry, tmp_path):
    steps = [HARD, text_step("Дошли."), HARD]
    adapter = ScriptedAdapter(steps, provider="gemini", model=FLASH)
    app = make_app(registry, tmp_path, adapter, auto_reports=True)
    app.refusal_chain = False
    app.handle("Иду")
    app.choose("retry")
    app.handle("Дальше")
    assert len(issues(tmp_path)) == 2


def test_auto_reports_off_writes_nothing(registry, tmp_path):
    adapter = ScriptedAdapter([HARD, HARD], provider="gemini", model=FLASH)
    app = make_app(registry, tmp_path, adapter, auto_reports=False)
    app.refusal_chain = False
    app.handle("Иду")
    app.choose("retry")
    assert issues(tmp_path) == []


# load() сбрасывает память

def test_load_resets_reported_memory(registry, tmp_path):
    app, _ = failed_app(registry, tmp_path, [HARD, HARD])
    app.handle("/save a")
    app.handle("/load a")
    assert app.reported is None
    app.handle("Иду")
    assert len(issues(tmp_path)) == 2


def test_reported_is_none_in_fresh_app(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([text_step()]), auto_reports=True)
    assert app.reported is None


# committed-ходы пишутся всегда

def test_two_gold_repeat_turns_in_a_row_write_two_reports(registry, tmp_path):
    steps = []
    for i in range(3):
        steps += [tools_step(gold_call(2000, f"g{i}")), text_step(f"Кошель {i}.")]
    app = make_app(registry, tmp_path, scripted(steps), auto_reports=True)
    app.handle("Обыскать тела")
    app.handle("Перевязать раны")
    app.handle("Ещё раз")
    found = issues(tmp_path)
    assert len(found) == 2
    assert all(p.name.endswith("gold_repeat") for p in found)


# цепочка: каждая модель -- свой каталог

def test_chain_writes_one_report_per_refusing_model(registry, tmp_path):
    factory = Factory({ARGON: [HARD], PREVIEW: [text_step("Дошли.")]})
    adapter = ScriptedAdapter([HARD], provider="gemini", model=FLASH)
    app = make_app(registry, tmp_path, adapter, adapter_factory=factory, auto_reports=True)
    app.refusal_chain = True
    app.handle("Иду")
    found = issues(tmp_path)
    assert len(found) == 2
    assert {meta_of(p)["model"] for p in found} == {FLASH, ARGON}


def test_chain_all_refuse_each_model_has_exactly_one_report(registry, tmp_path):
    lite = "gemini-3.5-flash-lite"
    factory = Factory({ARGON: [HARD], PREVIEW: [HARD], lite: [HARD]})
    adapter = ScriptedAdapter([HARD], provider="gemini", model=FLASH)
    app = make_app(registry, tmp_path, adapter, adapter_factory=factory, auto_reports=True)
    app.refusal_chain = True
    app.handle("Иду")
    models = sorted(meta_of(p)["model"] for p in issues(tmp_path))
    assert models == sorted([FLASH, ARGON, PREVIEW, lite])


# trim в write_report_lines

def test_report_trims_old_issues_over_limit(registry, tmp_path):
    old = tmp_path / "w1" / "issues" / "20200101T000000-t1-old"
    old.mkdir(parents=True)
    (old / "f").write_bytes(b"x" * 1_500_000)
    adapter = ScriptedAdapter([HARD], provider="gemini", model=FLASH)
    app = make_app(registry, tmp_path, adapter, auto_reports=True)
    app.refusal_chain = False
    app.settings.app.reports.max_mb = 1
    app.handle("Иду")
    assert not old.exists()
    assert len(issues(tmp_path)) == 1


def test_report_with_zero_limit_keeps_old_issues(registry, tmp_path):
    old = tmp_path / "w1" / "issues" / "20200101T000000-t1-old"
    old.mkdir(parents=True)
    (old / "f").write_bytes(b"x" * 1_500_000)
    adapter = ScriptedAdapter([HARD], provider="gemini", model=FLASH)
    app = make_app(registry, tmp_path, adapter, auto_reports=True)
    app.refusal_chain = False
    app.settings.app.reports.max_mb = 0
    app.handle("Иду")
    assert old.exists()


def test_trim_oserror_does_not_change_report_line(registry, tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("диск")

    monkeypatch.setattr("ai_dm.game.app.trim_issues", boom)
    _, reply = failed_app(registry, tmp_path, [HARD])
    text = text_of(reply)
    assert "Записан репорт" in text
    assert "Репорт не записан" not in text


def test_chain_factory_error_writes_exactly_one_report(registry, tmp_path):
    factory = FactorySpy(error=MissingKey("нет ключа"))
    adapter = ScriptedAdapter([HARD], provider="gemini", model=FLASH)
    app = make_app(registry, tmp_path, adapter, adapter_factory=factory, auto_reports=True)
    app.refusal_chain = True
    reply = app.handle("Иду")
    assert app.pending == "error_menu"
    assert len(issues(tmp_path)) == 1
    assert text_of(reply).count("Записан репорт") == 1
