# Шаг 190: KeySession -- ввод ключа API без терминала (мастер первого запуска и /key).
# Состояния provider -> (confirm ->) key -> готово; verify -- инъекция (KeyDeps.verify), сети нет.
import stat

import pytest

from ai_dm.config.app import load_settings
from ai_dm.llm.keys import parse_dotenv
from ai_dm.ui.key_session import PROVIDER_VAR, PROVIDERS, KeyDeps, KeySession

KEY = "sk-or-v1-abcdef1234"


class Verify:
    def __init__(self, *verdicts):
        self.verdicts = list(verdicts)
        self.calls = []

    def __call__(self, provider, key, app_cfg):
        self.calls.append((provider, key))
        return self.verdicts.pop(0)


def texts(step):
    parts = []
    for block in step.blocks:
        parts.extend([block.title or "", block.text])
        parts.extend(block.items)
    return "\n".join(parts)


def make(tmp_path, *verdicts, env=None, remember=False, dotenv_text=None):
    dotenv = tmp_path / "cfg" / ".env"
    if dotenv_text is not None:
        dotenv.parent.mkdir(parents=True)
        dotenv.write_text(dotenv_text, encoding="utf-8")
    verify = Verify(*(verdicts or ("ok",)))
    secrets = []
    deps = KeyDeps(load_settings().app, env if env is not None else {}, dotenv, secrets, verify)
    return KeySession(deps, remember=remember), verify, secrets, dotenv


def written(dotenv):
    return parse_dotenv(dotenv.read_text(encoding="utf-8"))


# старт и список провайдеров

def test_providers_order_is_openrouter_gemini_anthropic_openai():
    assert [p[0] for p in PROVIDERS] == ["openrouter", "gemini", "anthropic", "openai"]


def test_start_shows_four_providers_in_order(tmp_path):
    session, *_ = make(tmp_path)
    menus = [b for b in session.start().blocks if b.kind == "menu"]
    assert list(menus[0].items) == ["OpenRouter", "Gemini", "Anthropic", "OpenAI"]


def test_start_menu_has_provider_title(tmp_path):
    session, *_ = make(tmp_path)
    menus = [b for b in session.start().blocks if b.kind == "menu"]
    assert menus[0].title == "Провайдер:"


def test_start_does_not_finish(tmp_path):
    session, *_ = make(tmp_path)
    assert session.start().quit is False


def test_start_state_is_provider(tmp_path):
    session, *_ = make(tmp_path)
    assert session.state == "provider"


# выбор провайдера

def test_choosing_provider_asks_key_with_link(tmp_path):
    session, *_ = make(tmp_path)
    step = session.submit("1")
    assert "https://openrouter.ai/keys" in texts(step)
    assert session.state == "key"


@pytest.mark.parametrize(
    "number, url",
    [
        ("2", "https://aistudio.google.com/apikey"),
        ("3", "https://console.anthropic.com/settings/keys"),
        ("4", "https://platform.openai.com/api-keys"),
    ],
)
def test_each_provider_has_its_own_link(tmp_path, number, url):
    session, *_ = make(tmp_path)
    assert url in texts(session.submit(number))


@pytest.mark.parametrize("line", ["0", "5", "abc", "", "-1"])
def test_bad_provider_choice_repeats_without_state_change(tmp_path, line):
    session, *_ = make(tmp_path)
    step = session.submit(line)
    assert "Нет такого варианта" in texts(step)
    assert (session.state, step.quit) == ("provider", False)


def test_provider_choice_ignores_surrounding_spaces(tmp_path):
    session, *_ = make(tmp_path)
    session.submit(" 2 ")
    assert session.state == "key"


# выход

def test_none_at_provider_quits_without_writing(tmp_path):
    session, verify, _, dotenv = make(tmp_path)
    step = session.submit(None)
    assert step.quit is True
    assert not dotenv.exists()
    assert session.saved is False
    assert verify.calls == []


def test_none_at_key_quits_without_writing(tmp_path):
    session, verify, secrets, dotenv = make(tmp_path)
    session.submit("1")
    assert session.submit(None).quit is True
    assert not dotenv.exists()
    assert (session.saved, secrets, verify.calls) == (False, [], [])


# ввод ключа

def test_empty_key_repeats_hint_without_verify(tmp_path):
    session, verify, _, _ = make(tmp_path)
    session.submit("1")
    step = session.submit("   ")
    assert "https://openrouter.ai/keys" in texts(step)
    assert (verify.calls, session.state, step.quit) == ([], "key", False)


def test_key_is_verified_for_chosen_provider(tmp_path):
    session, verify, _, _ = make(tmp_path)
    session.submit("3")
    session.submit(f"  {KEY}  ")
    assert verify.calls == [("anthropic", KEY)]


def test_ok_key_is_saved_under_provider_variable(tmp_path):
    session, _, _, dotenv = make(tmp_path)
    session.submit("1")
    session.submit(KEY)
    assert written(dotenv) == {"OPENROUTER_API_KEY": KEY}


@pytest.mark.parametrize(
    "number, var",
    [("2", "GEMINI_API_KEY"), ("3", "ANTHROPIC_API_KEY"), ("4", "OPENAI_API_KEY")],
)
def test_each_provider_writes_its_variable(tmp_path, number, var):
    session, _, _, dotenv = make(tmp_path)
    session.submit(number)
    session.submit(KEY)
    assert written(dotenv) == {var: KEY}


def test_saved_file_has_mode_600(tmp_path):
    session, _, _, dotenv = make(tmp_path)
    session.submit("1")
    session.submit(KEY)
    assert stat.S_IMODE(dotenv.stat().st_mode) == 0o600


def test_ok_result_fields_and_finish(tmp_path):
    session, _, _, _ = make(tmp_path)
    session.submit("1")
    step = session.submit(KEY)
    assert step.quit is True
    assert (session.saved, session.provider, session.tail) == (True, "openrouter", KEY[-4:])


def test_saved_note_shows_tail_and_path_but_not_the_key(tmp_path):
    session, _, _, dotenv = make(tmp_path)
    session.submit("1")
    shown = texts(session.submit(KEY))
    assert f"…{KEY[-4:]}" in shown
    assert str(dotenv) in shown
    assert KEY not in shown


def test_ok_has_no_unverified_note(tmp_path):
    session, _, _, _ = make(tmp_path)
    session.submit("1")
    assert "Не проверил" not in texts(session.submit(KEY))


def test_key_is_added_to_secrets(tmp_path):
    session, _, secrets, _ = make(tmp_path)
    session.submit("1")
    session.submit(KEY)
    assert secrets == [KEY]


# неверный ключ

def test_invalid_key_asks_again_and_writes_nothing(tmp_path):
    session, _, secrets, dotenv = make(tmp_path, "invalid")
    session.submit("1")
    step = session.submit("плохой-ключ")
    assert "Ключ не подошёл, ещё раз?" in texts(step)
    assert (step.quit, session.state, session.saved, secrets) == (False, "key", False, [])
    assert not dotenv.exists()


def test_second_key_after_invalid_is_saved(tmp_path):
    session, verify, secrets, dotenv = make(tmp_path, "invalid", "ok")
    session.submit("1")
    session.submit("плохой-ключ")
    step = session.submit(KEY)
    assert step.quit is True
    assert written(dotenv) == {"OPENROUTER_API_KEY": KEY}
    assert secrets == [KEY]
    assert [key for _, key in verify.calls] == ["плохой-ключ", KEY]


def test_invalid_key_text_is_not_echoed(tmp_path):
    session, *_ = make(tmp_path, "invalid")
    session.submit("1")
    assert "плохой-ключ" not in texts(session.submit("плохой-ключ"))


# ключ не проверен

def test_unverified_key_is_saved_with_note(tmp_path):
    session, _, secrets, dotenv = make(tmp_path, ("unverified", "нет сети"))
    session.submit("1")
    step = session.submit(KEY)
    assert "Не проверил: нет сети, проверю на первом ходу." in texts(step)
    assert written(dotenv) == {"OPENROUTER_API_KEY": KEY}
    assert (step.quit, session.saved, secrets) == (True, True, [KEY])


def test_unverified_note_drops_trailing_dot_of_error_text(tmp_path):
    session, *_ = make(tmp_path, ("unverified", "404 not found."))
    session.submit("1")
    shown = texts(session.submit(KEY))
    assert "Не проверил: 404 not found, проверю на первом ходу." in shown


def test_unverified_note_comes_before_saved_note(tmp_path):
    session, *_ = make(tmp_path, ("unverified", "сбой"))
    session.submit("1")
    shown = texts(session.submit(KEY))
    assert shown.index("Не проверил") < shown.index("сохранён")


# память провайдера

def test_remember_writes_profile_for_openrouter_as_deepseek(tmp_path):
    session, _, _, dotenv = make(tmp_path, remember=True)
    session.submit("1")
    session.submit(KEY)
    assert written(dotenv) == {"OPENROUTER_API_KEY": KEY, PROVIDER_VAR: "deepseek"}


@pytest.mark.parametrize(
    "number, profile", [("2", "gemini"), ("3", "anthropic"), ("4", "openai")]
)
def test_remember_writes_same_named_profile(tmp_path, number, profile):
    session, _, _, dotenv = make(tmp_path, remember=True)
    session.submit(number)
    session.submit(KEY)
    assert written(dotenv)[PROVIDER_VAR] == profile


def test_without_remember_provider_variable_is_not_written(tmp_path):
    session, _, _, dotenv = make(tmp_path)
    session.submit("1")
    session.submit(KEY)
    assert PROVIDER_VAR not in written(dotenv)


def test_invalid_key_does_not_write_provider_variable(tmp_path):
    session, _, _, dotenv = make(tmp_path, "invalid", remember=True)
    session.submit("1")
    session.submit("плохой")
    assert not dotenv.exists()


# ключ уже есть

def test_existing_key_asks_to_replace(tmp_path):
    session, *_ = make(tmp_path, dotenv_text="OPENROUTER_API_KEY=old\n")
    step = session.submit("1")
    assert "Ключ OpenRouter уже есть — заменить?" in texts(step)
    menus = [b for b in step.blocks if b.kind == "menu"]
    assert list(menus[0].items) == ["Да", "Нет"]
    assert session.state == "confirm"


def test_other_provider_key_in_dotenv_does_not_ask(tmp_path):
    session, *_ = make(tmp_path, dotenv_text="GEMINI_API_KEY=old\n")
    session.submit("1")
    assert session.state == "key"


def test_empty_value_in_dotenv_does_not_ask(tmp_path):
    session, *_ = make(tmp_path, dotenv_text="OPENROUTER_API_KEY=\n")
    session.submit("1")
    assert session.state == "key"


def test_existing_key_in_env_only_does_not_ask(tmp_path):
    session, *_ = make(tmp_path, env={"OPENROUTER_API_KEY": "from-env"})
    session.submit("1")
    assert session.state == "key"


def test_confirm_no_quits_and_file_is_byte_identical(tmp_path):
    text = "# мои ключи\nOPENROUTER_API_KEY=old\nOTHER=1"
    session, verify, secrets, dotenv = make(tmp_path, dotenv_text=text)
    before = dotenv.read_bytes()
    session.submit("1")
    step = session.submit("2")
    assert step.quit is True
    assert dotenv.read_bytes() == before
    assert (session.saved, secrets, verify.calls) == (False, [], [])


def test_confirm_yes_asks_key_then_replaces_only_its_line(tmp_path):
    text = "# мои ключи\nOTHER=1\nOPENROUTER_API_KEY=old\n\nLAST=2\n"
    session, _, _, dotenv = make(tmp_path, dotenv_text=text)
    session.submit("1")
    step = session.submit("1")
    assert (session.state, step.quit) == ("key", False)
    session.submit(KEY)
    assert dotenv.read_text(encoding="utf-8") == (
        f"# мои ключи\nOTHER=1\nOPENROUTER_API_KEY={KEY}\n\nLAST=2\n"
    )


def test_confirm_yes_with_invalid_key_keeps_old_key(tmp_path):
    session, _, _, dotenv = make(
        tmp_path, "invalid", dotenv_text="OPENROUTER_API_KEY=old\n"
    )
    session.submit("1")
    session.submit("1")
    session.submit("плохой")
    assert written(dotenv) == {"OPENROUTER_API_KEY": "old"}


@pytest.mark.parametrize("line", ["0", "3", "да", ""])
def test_bad_confirm_choice_repeats(tmp_path, line):
    session, *_ = make(tmp_path, dotenv_text="OPENROUTER_API_KEY=old\n")
    session.submit("1")
    step = session.submit(line)
    assert "Нет такого варианта" in texts(step)
    assert (session.state, step.quit) == ("confirm", False)


def test_none_at_confirm_quits(tmp_path):
    session, _, _, dotenv = make(tmp_path, dotenv_text="OPENROUTER_API_KEY=old\n")
    session.submit("1")
    assert session.submit(None).quit is True
    assert written(dotenv) == {"OPENROUTER_API_KEY": "old"}


# переменная окружения перекрывает .env

def test_env_variable_shadowing_dotenv_gets_warning(tmp_path):
    session, *_ = make(tmp_path, env={"OPENROUTER_API_KEY": "from-env"})
    session.submit("1")
    shown = texts(session.submit(KEY))
    assert "OPENROUTER_API_KEY" in shown
    assert "перекрывает" in shown


def test_no_shadow_warning_without_env_variable(tmp_path):
    session, *_ = make(tmp_path)
    session.submit("1")
    assert "перекрывает" not in texts(session.submit(KEY))


def test_other_provider_env_variable_gives_no_warning(tmp_path):
    session, *_ = make(tmp_path, env={"GEMINI_API_KEY": "g"})
    session.submit("1")
    assert "перекрывает" not in texts(session.submit(KEY))
