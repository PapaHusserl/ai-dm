# Б3 (B3-PLAN A5): ImportSession -- import пака без терминала. start() запускает прогон модели;
# сбой -- меню 2.2 («Повторить», «Сменить модель», «Выйти»); итог -- ctx (None при выходе).
# Мастер -- ScriptedAdapter, живых вызовов нет.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

from game_kit import FactorySpy  # noqa: E402
from import_kit import (  # noqa: E402
    bad_pack_call,
    import_deps,
    import_task,
    pack_call,
    staged,
    summary_text,
)
from master_kit import app_cfg, scripted, tools_step  # noqa: E402

from ai_dm.game.turn import REFUSAL_HINT  # noqa: E402
from ai_dm.ui.import_session import ImportSession  # noqa: E402


def make(registry, cfg, tmp_path, steps, **kw):
    _, folder = staged(tmp_path)
    adapter = scripted(steps)
    deps = import_deps(adapter, registry, cfg, folder, **kw)
    session = ImportSession(deps, import_task(), summary_text(), folder)
    return session, adapter, deps


def texts(step):
    parts = []
    for block in step.blocks:
        parts.append(block.text)
        parts.extend(block.items)
    return "\n".join(parts)


def menu_of(step):
    menus = [block for block in step.blocks if block.kind == "menu"]
    assert len(menus) == 1
    return list(menus[0].items)


def failing_steps():
    return [tools_step(bad_pack_call(f"p-{i}")) for i in range(app_cfg().retry.invalid_retries + 1)]


def failed(registry, cfg, tmp_path, steps=None, **kw):
    # сессия после сбоя TurnFailed: меню 2.2
    steps = failing_steps() if steps is None else steps
    session, adapter, deps = make(registry, cfg, tmp_path, steps, **kw)
    return session, adapter, deps, session.start()


# успех

def test_start_with_valid_pack_quits_with_ctx(registry, cfg, tmp_path):
    session, _, _ = make(registry, cfg, tmp_path, [tools_step(pack_call())])
    step = session.start()
    assert step.quit is True
    assert session.ctx is not None
    assert session.ctx.files is not None


def test_start_says_that_pack_is_assembled(registry, cfg, tmp_path):
    session, _, _ = make(registry, cfg, tmp_path, [tools_step(pack_call())])
    assert "Пак собран" in texts(session.start())


def test_start_makes_one_model_call_for_valid_pack(registry, cfg, tmp_path):
    session, adapter, _ = make(registry, cfg, tmp_path, [tools_step(pack_call())])
    session.start()
    assert len(adapter.requests) == 1


def test_run_id_is_import_stamp_and_counter(registry, cfg, tmp_path):
    session, _, _ = make(registry, cfg, tmp_path, [tools_step(pack_call())])
    session.start()
    assert session.run_ids == [f"import-{session.stamp}-1"]


def test_first_pack_error_is_retried_inside_master_session(registry, cfg, tmp_path):
    steps = [tools_step(bad_pack_call()), tools_step(pack_call("p-2"))]
    session, adapter, _ = make(registry, cfg, tmp_path, steps)
    step = session.start()
    assert step.quit is True
    assert len(adapter.requests) == 2
    assert session.run_ids == [f"import-{session.stamp}-1"]


def test_ctx_is_none_before_start(registry, cfg, tmp_path):
    session, _, _ = make(registry, cfg, tmp_path, [])
    assert session.ctx is None
    assert session.run_ids == []


# сбой: меню 2.2

def test_invalid_failure_gives_error_menu_with_three_items(registry, cfg, tmp_path):
    session, _, _, step = failed(registry, cfg, tmp_path)
    items = [item.lower() for item in menu_of(step)]
    assert len(items) == 3
    assert "повтор" in items[0]
    assert "модел" in items[1]
    assert "выйти" in items[2]
    assert session.ctx is None
    assert step.quit is False
    assert session.state == "error_menu"


def test_invalid_failure_does_not_write_pack_files(registry, cfg, tmp_path):
    _, _, deps, _ = failed(registry, cfg, tmp_path)
    folder = deps.journal.dir.parent.parent
    assert not (folder / "campaign.yaml").exists()


def test_refusal_shows_refusal_hint_and_error_menu(registry, cfg, tmp_path):
    _, _, _, step = failed(registry, cfg, tmp_path, [{"stop": "refusal"}])
    assert REFUSAL_HINT in texts(step)
    assert len(menu_of(step)) == 3


def test_invalid_failure_does_not_show_refusal_hint(registry, cfg, tmp_path):
    _, _, _, step = failed(registry, cfg, tmp_path)
    assert REFUSAL_HINT not in texts(step)


def test_retry_makes_new_run_with_new_run_id_and_finishes(registry, cfg, tmp_path):
    steps = [*failing_steps(), tools_step(pack_call("p-ok"))]
    session, adapter, _, _ = failed(registry, cfg, tmp_path, steps)
    step = session.submit("1")
    assert step.quit is True
    assert session.ctx.files is not None
    assert session.run_ids == [f"import-{session.stamp}-1", f"import-{session.stamp}-2"]
    assert len(adapter.requests) == app_cfg().retry.invalid_retries + 2


def test_retry_that_fails_again_gives_error_menu_again(registry, cfg, tmp_path):
    steps = [*failing_steps(), *failing_steps()]
    session, _, _, first = failed(registry, cfg, tmp_path, steps)
    step = session.submit("1")
    assert step.quit is False
    assert menu_of(step) == menu_of(first)
    assert session.ctx is None
    assert len(session.run_ids) == 2


def test_retry_after_refusal_works(registry, cfg, tmp_path):
    steps = [{"stop": "refusal"}, tools_step(pack_call())]
    session, _, _, _ = failed(registry, cfg, tmp_path, steps)
    assert session.submit("1").quit is True
    assert session.ctx is not None


def test_leave_ends_without_ctx(registry, cfg, tmp_path):
    session, _, _, _ = failed(registry, cfg, tmp_path)
    step = session.submit("3")
    assert step.quit is True
    assert session.ctx is None


def test_digit_outside_menu_is_refused_without_model_call(registry, cfg, tmp_path):
    session, adapter, _, _ = failed(registry, cfg, tmp_path)
    count = len(adapter.requests)
    step = session.submit("9")
    assert "Нет такого варианта" in texts(step)
    assert step.quit is False
    assert len(adapter.requests) == count
    assert len(session.run_ids) == 1


def test_text_instead_of_digit_is_refused(registry, cfg, tmp_path):
    session, adapter, _, _ = failed(registry, cfg, tmp_path)
    count = len(adapter.requests)
    step = session.submit("повторить")
    assert "Нет такого варианта" in texts(step)
    assert len(adapter.requests) == count


def test_zero_is_not_a_menu_item(registry, cfg, tmp_path):
    session, _, _, _ = failed(registry, cfg, tmp_path)
    assert "Нет такого варианта" in texts(session.submit("0"))


def test_menu_input_is_stripped(registry, cfg, tmp_path):
    session, _, _, _ = failed(registry, cfg, tmp_path)
    assert session.submit(" 3 ").quit is True


def test_end_of_input_quits_in_error_menu(registry, cfg, tmp_path):
    session, _, _, _ = failed(registry, cfg, tmp_path)
    assert session.submit(None).quit is True
    assert session.ctx is None


def test_end_of_input_before_start_quits(registry, cfg, tmp_path):
    session, adapter, _ = make(registry, cfg, tmp_path, [])
    assert session.submit(None).quit is True
    assert adapter.requests == []


# смена модели

def test_switch_model_shows_model_options(registry, cfg, tmp_path):
    session, _, _, _ = failed(registry, cfg, tmp_path, adapter_factory=FactorySpy())
    step = session.submit("2")
    items = menu_of(step)
    assert len(items) >= 2
    assert all(":" in item for item in items)
    assert session.state == "model_choice"


def test_switch_model_calls_factory_and_returns_to_error_menu(registry, cfg, tmp_path):
    spy = FactorySpy()
    session, _, deps, first = failed(registry, cfg, tmp_path, adapter_factory=spy)
    options = menu_of(session.submit("2"))
    step = session.submit("1")
    provider, _, model = options[0].partition(":")
    assert spy.calls == [(provider, model)]
    assert menu_of(step) == menu_of(first)
    assert deps.adapter is spy.made[0]
    assert deps.model == model
    assert session.state == "error_menu"


def test_switch_model_with_factory_error_shows_it_and_keeps_adapter(registry, cfg, tmp_path):
    spy = FactorySpy(error=ValueError("ключ не найден"))
    session, adapter, deps, first = failed(registry, cfg, tmp_path, adapter_factory=spy)
    session.submit("2")
    step = session.submit("1")
    assert "ключ не найден" in texts(step)
    assert menu_of(step) == menu_of(first)
    assert deps.adapter is adapter
    assert session.state == "error_menu"


def test_retry_after_model_switch_uses_new_adapter_and_model(registry, cfg, tmp_path):
    fresh = scripted([tools_step(pack_call("p-new"))])
    session, old, deps, _ = failed(
        registry, cfg, tmp_path, adapter_factory=lambda provider, model: fresh
    )
    options = menu_of(session.submit("2"))
    session.submit("1")
    count = len(old.requests)
    step = session.submit("1")
    assert step.quit is True
    assert session.ctx.files is not None
    assert len(old.requests) == count
    assert len(fresh.requests) == 1
    assert fresh.requests[0].model == options[0].partition(":")[2]


def test_model_choice_digit_outside_is_refused_without_factory_call(registry, cfg, tmp_path):
    spy = FactorySpy()
    session, _, _, _ = failed(registry, cfg, tmp_path, adapter_factory=spy)
    session.submit("2")
    step = session.submit("99")
    assert "Нет такого варианта" in texts(step)
    assert spy.calls == []
    assert session.state == "model_choice"


def test_end_of_input_in_model_choice_quits(registry, cfg, tmp_path):
    session, _, _, _ = failed(registry, cfg, tmp_path, adapter_factory=FactorySpy())
    session.submit("2")
    assert session.submit(None).quit is True
