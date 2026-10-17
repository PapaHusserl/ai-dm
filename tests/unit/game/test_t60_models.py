# Т60 «Сеть» (docs/plan-t60.md п.1.3, раздел 10): ai_dm.game.models.
#   next_in_chain(app_cfg, current_key) -- ключ "провайдер:модель", следующий в llm.narrator_chain;
#   нет в цепочке / последняя / пустая цепочка -> None. (В плане была сигнатура
#   (app_cfg, provider, model); kaban реализовал ключом -- тесты следуют коду, см. отчёт.)
#   model_options(app_cfg, current=None): roles + alternatives + профили + цепочка без повторов;
#   следующая после current по цепочке -- первой.
#   check_model, read_models, write_models переехали из game.app (app реэкспортирует check_model и
#   model_options).
import json

import pytest
from game_kit import settings

from ai_dm.game.models import (
    check_model,
    model_options,
    models_path,
    next_in_chain,
    read_models,
    write_models,
)
from ai_dm.llm.errors import MissingKey

FLASH = "gemini:gemini-3.8-flash"
ARGON = "gemini:gemini-4-argon"
PREVIEW = "gemini:gemini-3-flash-preview"
LITE = "gemini:gemini-3.5-flash-lite"
OPUS = "anthropic:claude-opus-5-5"


def app():
    return settings().app


# next_in_chain

@pytest.mark.parametrize(
    ("current", "expected"),
    [(FLASH, ARGON), (ARGON, PREVIEW), (PREVIEW, LITE)],
)
def test_next_in_chain_gives_the_following_key(current, expected):
    assert next_in_chain(app(), current) == expected


def test_next_in_chain_of_last_is_none():
    assert next_in_chain(app(), LITE) is None


@pytest.mark.parametrize("current", [OPUS, "mock:mock", "gemini:unknown", "", None])
def test_next_in_chain_of_model_outside_chain_is_none(current):
    assert next_in_chain(app(), current) is None


def test_next_in_chain_with_empty_chain_is_none():
    cfg = app()
    cfg.llm.narrator_chain = []
    assert next_in_chain(cfg, FLASH) is None


def test_next_in_chain_follows_the_configured_order():
    cfg = app()
    cfg.llm.narrator_chain = [LITE, FLASH, ARGON]
    assert next_in_chain(cfg, LITE) == FLASH
    assert next_in_chain(cfg, FLASH) == ARGON
    assert next_in_chain(cfg, ARGON) is None


def test_next_in_chain_does_not_mutate_the_chain():
    cfg = app()
    before = list(cfg.llm.narrator_chain)
    next_in_chain(cfg, FLASH)
    assert cfg.llm.narrator_chain == before


# model_options

def test_options_start_with_narrator_role_then_alternative():
    cfg = app()
    options = model_options(cfg)
    assert options[0] == f"{cfg.roles.narrator.provider}:{cfg.roles.narrator.model}"
    assert options[1] == f"{cfg.alternatives.narrator.provider}:{cfg.alternatives.narrator.model}"


def test_options_contain_every_chain_key():
    options = model_options(app())
    for key in (FLASH, ARGON, PREVIEW, LITE):
        assert key in options


def test_options_have_no_duplicates():
    options = model_options(app())
    assert len(options) == len(set(options))


def test_options_keep_old_ones_and_keys_of_profiles():
    options = model_options(app())
    for key in (FLASH, "anthropic:claude-sonnet-5-5", OPUS):
        assert key in options


def test_options_chain_key_already_present_is_not_repeated():
    cfg = app()
    cfg.llm.narrator_chain = [OPUS, FLASH]
    assert model_options(cfg).count(OPUS) == 1
    assert model_options(cfg).count(FLASH) == 1


def test_options_with_empty_chain_are_the_old_list():
    cfg = app()
    cfg.llm.narrator_chain = []
    options = model_options(cfg)
    assert ARGON not in options
    assert options[0] == FLASH


def test_options_put_following_model_first():
    assert model_options(app(), FLASH)[0] == ARGON
    assert model_options(app(), ARGON)[0] == PREVIEW
    assert model_options(app(), PREVIEW)[0] == LITE


def test_options_with_current_are_a_permutation_of_options_without():
    cfg = app()
    assert sorted(model_options(cfg, FLASH)) == sorted(model_options(cfg))
    assert len(model_options(cfg, FLASH)) == len(model_options(cfg))


def test_options_keep_the_order_of_the_rest():
    cfg = app()
    plain = model_options(cfg)
    moved = model_options(cfg, FLASH)
    plain.remove(ARGON)
    assert moved[1:] == plain


@pytest.mark.parametrize("current", [LITE, OPUS, "mock:mock", None])
def test_options_are_plain_when_nothing_follows(current):
    assert model_options(app(), current) == model_options(app())


def test_options_are_plain_when_chain_is_empty():
    cfg = app()
    cfg.llm.narrator_chain = []
    assert model_options(cfg, FLASH) == model_options(cfg)


def test_app_reexports_model_helpers():
    from ai_dm.game import app as game_app
    from ai_dm.game import models

    assert game_app.model_options is models.model_options
    assert game_app.check_model is models.check_model


# check_model

def test_check_model_unknown_price_gives_error_without_factory_call():
    calls = []
    adapter, error = check_model(app(), lambda p, m: calls.append((p, m)), "gemini", "no-such")
    assert adapter is None
    assert "no-such" in error
    assert calls == []


def test_check_model_without_window_gives_error():
    cfg = app()
    del cfg.context_windows["gemini-4-argon"]
    adapter, error = check_model(cfg, lambda p, m: object(), "gemini", "gemini-4-argon")
    assert adapter is None
    assert error


def test_check_model_ok_returns_factory_adapter():
    marker = object()
    seen = []
    adapter, error = check_model(
        app(), lambda p, m: seen.append((p, m)) or marker, "gemini", "gemini-4-argon"
    )
    assert adapter is marker
    assert error is None
    assert seen == [("gemini", "gemini-4-argon")]


@pytest.mark.parametrize("exc", [MissingKey("нет ключа"), ValueError("плохая модель")])
def test_check_model_factory_error_becomes_text(exc):
    def factory(provider, model):
        raise exc

    adapter, error = check_model(app(), factory, "gemini", "gemini-4-argon")
    assert adapter is None
    assert error == str(exc)


# models.json

def test_models_path_is_meta_models_json(tmp_path):
    assert models_path(tmp_path, "w1") == tmp_path / "w1" / "meta" / "models.json"


def test_read_models_without_file_is_empty(tmp_path):
    assert read_models(tmp_path, "w1") == {}


def test_write_then_read_models(tmp_path):
    write_models(tmp_path, "w1", "gemini", "gemini-4-argon")
    assert read_models(tmp_path, "w1") == {
        "narrator": {"provider": "gemini", "model": "gemini-4-argon"}
    }


def test_write_models_keeps_other_keys(tmp_path):
    path = models_path(tmp_path, "w1")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"other": {"x": 1}, "narrator": {"provider": "a", "model": "b"}}))
    write_models(tmp_path, "w1", "gemini", "m")
    stored = read_models(tmp_path, "w1")
    assert stored["other"] == {"x": 1}
    assert stored["narrator"] == {"provider": "gemini", "model": "m"}


def test_write_models_rewrites_broken_file(tmp_path):
    path = models_path(tmp_path, "w1")
    path.parent.mkdir(parents=True)
    path.write_text("{не json")
    write_models(tmp_path, "w1", "gemini", "m")
    assert read_models(tmp_path, "w1") == {"narrator": {"provider": "gemini", "model": "m"}}


def test_write_models_leaves_no_tmp_file(tmp_path):
    write_models(tmp_path, "w1", "gemini", "m")
    assert [p.name for p in models_path(tmp_path, "w1").parent.iterdir()] == ["models.json"]


def test_write_models_is_utf8_and_indented(tmp_path):
    write_models(tmp_path, "w1", "gemini", "m")
    text = models_path(tmp_path, "w1").read_text(encoding="utf-8")
    assert text == json.dumps(
        {"narrator": {"provider": "gemini", "model": "m"}}, ensure_ascii=False, indent=2
    )


def test_write_models_keeps_non_ascii_as_is(tmp_path):
    write_models(tmp_path, "w1", "gemini", "модель-ё")
    text = models_path(tmp_path, "w1").read_text(encoding="utf-8")
    assert "модель-ё" in text
    assert "\\u" not in text
