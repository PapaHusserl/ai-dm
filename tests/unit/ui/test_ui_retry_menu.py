# Б2а (B2-PLAN, A4): RetryMenu -- меню 2.2 (повторить / сменить модель / <выход>), вынесенное из
# HeroSession. Ожидаемый API (ТРЕБОВАНИЕ к коду): ai_dm.ui.hero_session.RetryMenu(deps,
# leave_label=ERROR_MENU[2]) с fail(failure) -> Step, menu, choose(number) -> RETRY | LEAVE | Step,
# state ("error_menu" / "model_choice"); константы RETRY, LEAVE.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

from game_kit import FactorySpy  # noqa: E402
from hero_kit import deps  # noqa: E402
from master_kit import app_cfg  # noqa: E402

from ai_dm.game.turn import REFUSAL_HINT  # noqa: E402
from ai_dm.master.session import TurnFailed  # noqa: E402

BACK = "Выбрать из списка"


def make(registry, cfg, **kw):
    from ai_dm.ui.hero_session import RetryMenu

    leave = kw.pop("leave_label", None)
    hero_deps = deps(None, registry, cfg, **kw)
    menu = RetryMenu(hero_deps) if leave is None else RetryMenu(hero_deps, leave_label=leave)
    return menu, hero_deps


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


def invalid():
    return TurnFailed("invalid", "мастер не уложился в правила")


def refusal():
    return TurnFailed("refusal", "отказ")


def test_fail_shows_failure_text_and_three_item_menu(registry, cfg):
    menu, _ = make(registry, cfg)
    step = menu.fail(invalid())
    assert "мастер не уложился в правила" in texts(step)
    assert len(menu_of(step)) == 3
    assert step.quit is False


def test_fail_with_refusal_shows_refusal_hint_not_the_text(registry, cfg):
    menu, _ = make(registry, cfg)
    text = texts(menu.fail(refusal()))
    assert REFUSAL_HINT in text
    assert "отказ" not in text.replace(REFUSAL_HINT, "")


def test_fail_with_invalid_does_not_show_refusal_hint(registry, cfg):
    menu, _ = make(registry, cfg)
    assert REFUSAL_HINT not in texts(menu.fail(invalid()))


def test_default_menu_items_are_the_error_menu(registry, cfg):
    from ai_dm.ui.hero_session import ERROR_MENU

    menu, _ = make(registry, cfg)
    assert menu_of(menu.fail(invalid())) == list(ERROR_MENU)


def test_leave_label_replaces_the_third_item(registry, cfg):
    menu, _ = make(registry, cfg, leave_label=BACK)
    items = menu_of(menu.fail(invalid()))
    assert items[2] == BACK
    assert "повтор" in items[0].lower()
    assert "модел" in items[1].lower()


def test_state_is_error_menu_after_fail(registry, cfg):
    menu, _ = make(registry, cfg)
    menu.fail(invalid())
    assert menu.state == "error_menu"


def test_menu_property_is_the_current_menu(registry, cfg):
    from ai_dm.ui.hero_session import ERROR_MENU

    menu, _ = make(registry, cfg, adapter_factory=FactorySpy())
    menu.fail(invalid())
    assert list(menu.menu) == list(ERROR_MENU)
    menu.choose(2)
    assert menu.state == "model_choice"
    assert len(menu.menu) >= 2
    assert all(":" in item for item in menu.menu)


def test_choose_one_is_retry(registry, cfg):
    from ai_dm.ui.hero_session import RETRY

    menu, _ = make(registry, cfg)
    menu.fail(invalid())
    assert menu.choose(1) is RETRY


def test_choose_three_is_leave(registry, cfg):
    from ai_dm.ui.hero_session import LEAVE

    menu, _ = make(registry, cfg, leave_label=BACK)
    menu.fail(invalid())
    assert menu.choose(3) is LEAVE


def test_choose_two_lists_model_options(registry, cfg):
    from ai_dm.game.app import model_options
    from ai_dm.ui.hero_session import MODEL_TITLE

    menu, _ = make(registry, cfg, adapter_factory=FactorySpy())
    menu.fail(invalid())
    step = menu.choose(2)
    assert menu_of(step) == model_options(app_cfg())
    assert [b.title for b in step.blocks if b.kind == "menu"] == [MODEL_TITLE]
    assert menu.state == "model_choice"


def test_model_choice_calls_factory_and_updates_deps(registry, cfg):
    spy = FactorySpy()
    menu, hero_deps = make(registry, cfg, adapter_factory=spy)
    menu.fail(invalid())
    options = menu_of(menu.choose(2))
    step = menu.choose(2)
    key = options[1]
    provider, _, model = key.partition(":")
    assert spy.calls == [(provider, model)]
    assert hero_deps.adapter is spy.made[0]
    assert hero_deps.model == model
    assert f"Модель рассказчика: {key}." in texts(step)


def test_model_choice_returns_to_error_menu(registry, cfg):
    from ai_dm.ui.hero_session import ERROR_MENU

    menu, _ = make(registry, cfg, adapter_factory=FactorySpy())
    first = menu.fail(invalid())
    menu.choose(2)
    step = menu.choose(1)
    assert menu_of(step) == menu_of(first) == list(ERROR_MENU)
    assert menu.state == "error_menu"


def test_model_choice_keeps_leave_label(registry, cfg):
    menu, _ = make(registry, cfg, leave_label=BACK, adapter_factory=FactorySpy())
    menu.fail(invalid())
    menu.choose(2)
    assert menu_of(menu.choose(1))[2] == BACK


def test_bad_model_shows_check_model_text_and_error_menu(registry, cfg):
    spy = FactorySpy(error=ValueError("ключ не найден"))
    menu, hero_deps = make(registry, cfg, adapter_factory=spy)
    first = menu.fail(invalid())
    menu.choose(2)
    step = menu.choose(1)
    assert "ключ не найден" in texts(step)
    assert menu_of(step) == menu_of(first)
    assert hero_deps.adapter is None
    assert menu.state == "error_menu"


def test_model_without_price_shows_its_name(registry, cfg, monkeypatch):
    menu, _ = make(registry, cfg, adapter_factory=FactorySpy())
    menu.fail(invalid())
    monkeypatch.setattr(
        "ai_dm.ui.hero_session.model_options", lambda app_cfg: ["anthropic:no-such-model"]
    )
    menu.choose(2)
    step = menu.choose(1)
    assert "no-such-model" in texts(step)
