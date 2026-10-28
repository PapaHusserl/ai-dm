# Шаг 190, партия 1: ввод ключа в игре через cli.main (простой режим).
# Мастер при старте без ключа, память провайдера AI_DM_PROVIDER, /key в игре, страж: ключ-маркер
# не попадает ни в вывод, ни в файлы мира. verify_key и make_adapter подменены -- сети нет.
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest
from ui_kit import SEED, ReactiveAdapter, cli, write_script

from ai_dm.llm.chat_adapter import ChatCompletionsAdapter
from ai_dm.llm.keys import parse_dotenv, read_var

BASE = ["--new", "--hero", "arn", "--seed", str(SEED)]
KEY = "sk-or-v1-MARKER-abcdef-7777"
DEEPSEEK = ("openrouter", "deepseek/deepseek-v4-flash")


class Adapters:
    # подмена cli.make_adapter: запоминает вызовы, отдаёт ReactiveAdapter
    def __init__(self):
        self.calls = []

    def __call__(self, provider, model, app_cfg, **kwargs):
        self.calls.append((provider, model))
        return ReactiveAdapter(provider=provider, model=model)


class Verdicts:
    def __init__(self, *verdicts):
        self.verdicts = list(verdicts)
        self.calls = []

    def __call__(self, provider, key, app_cfg):
        self.calls.append((provider, key))
        return self.verdicts.pop(0)


@pytest.fixture
def adapters(monkeypatch):
    spy = Adapters()
    monkeypatch.setattr("ai_dm.ui.cli.make_adapter", spy)
    return spy


def verdicts(monkeypatch, *items):
    spy = Verdicts(*items)
    monkeypatch.setattr("ai_dm.ui.cli.verify_key", spy)
    return spy


def no_verify(monkeypatch):
    def forbidden(*args):
        raise AssertionError("verify_key не должен вызываться")

    monkeypatch.setattr("ai_dm.ui.cli.verify_key", forbidden)


def argv_of(tmp_path):
    return BASE + ["--saves", str(tmp_path / "saves")]


def dotenv_of(tmp_path):
    return tmp_path / "cfg" / ".env"


def dotenv_values(path):
    return parse_dotenv(path.read_text(encoding="utf-8"))


# мастер при старте без ключа

def test_wizard_saves_key_remembers_provider_and_game_uses_it(tmp_path, monkeypatch, adapters):
    verify = verdicts(monkeypatch, "ok")
    dotenv = dotenv_of(tmp_path)
    code, out = cli(argv_of(tmp_path), ["1", KEY, "/quit"], env={}, dotenv_path=dotenv)
    assert code == 0
    assert dotenv_values(dotenv) == {"OPENROUTER_API_KEY": KEY, "AI_DM_PROVIDER": "deepseek"}
    assert stat.S_IMODE(dotenv.stat().st_mode) == 0o600
    assert verify.calls == [("openrouter", KEY)]
    assert adapters.calls[0] == DEEPSEEK


def test_wizard_shows_tail_and_never_the_key(tmp_path, monkeypatch, adapters):
    verdicts(monkeypatch, "ok")
    _, out = cli(
        argv_of(tmp_path), ["1", KEY, "/quit"], env={}, dotenv_path=dotenv_of(tmp_path)
    )
    assert "…7777" in out.text
    assert KEY not in out.text
    assert KEY[:-4] not in out.text


def test_wizard_lists_providers_and_link(tmp_path, monkeypatch, adapters):
    verdicts(monkeypatch, "ok")
    _, out = cli(
        argv_of(tmp_path), ["1", KEY, "/quit"], env={}, dotenv_path=dotenv_of(tmp_path)
    )
    for label in ("OpenRouter", "Gemini", "Anthropic", "OpenAI"):
        assert label in out.text
    assert "https://openrouter.ai/keys" in out.text


def test_wizard_other_provider_is_remembered_as_same_named_profile(
    tmp_path, monkeypatch, adapters
):
    verdicts(monkeypatch, "ok")
    dotenv = dotenv_of(tmp_path)
    code, _ = cli(argv_of(tmp_path), ["2", "g-key-1234", "/quit"], env={}, dotenv_path=dotenv)
    assert code == 0
    assert dotenv_values(dotenv) == {"GEMINI_API_KEY": "g-key-1234", "AI_DM_PROVIDER": "gemini"}
    assert adapters.calls[0][0] == "gemini"


def test_wizard_writes_to_dotenv_here_when_it_exists(tmp_path, monkeypatch, adapters):
    verdicts(monkeypatch, "ok")
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("# мой\nOTHER=1\n", encoding="utf-8")
    env = {"XDG_CONFIG_HOME": str(tmp_path / "xdg"), "XDG_DATA_HOME": str(tmp_path / "data")}
    code, _ = cli(argv_of(tmp_path), ["1", KEY, "/quit"], env=env)
    assert code == 0
    assert (tmp_path / ".env").read_text(encoding="utf-8") == (
        f"# мой\nOTHER=1\nOPENROUTER_API_KEY={KEY}\nAI_DM_PROVIDER=deepseek\n"
    )
    assert not (tmp_path / "xdg").exists()


def test_wizard_writes_to_config_dir_when_no_dotenv_here(tmp_path, monkeypatch, adapters):
    verdicts(monkeypatch, "ok")
    monkeypatch.chdir(tmp_path)
    env = {"XDG_CONFIG_HOME": str(tmp_path / "xdg"), "XDG_DATA_HOME": str(tmp_path / "data")}
    code, _ = cli(argv_of(tmp_path), ["1", KEY, "/quit"], env=env)
    assert code == 0
    assert dotenv_values(tmp_path / "xdg" / "ai-dm" / ".env")["OPENROUTER_API_KEY"] == KEY
    assert not (tmp_path / ".env").exists()


def test_wizard_invalid_key_asks_again_then_saves(tmp_path, monkeypatch, adapters):
    verify = verdicts(monkeypatch, "invalid", "ok")
    dotenv = dotenv_of(tmp_path)
    code, out = cli(
        argv_of(tmp_path), ["1", "плохой", KEY, "/quit"], env={}, dotenv_path=dotenv
    )
    assert code == 0
    assert "Ключ не подошёл, ещё раз?" in out.text
    assert dotenv_values(dotenv)["OPENROUTER_API_KEY"] == KEY
    assert [key for _, key in verify.calls] == ["плохой", KEY]


def test_wizard_invalid_key_only_writes_nothing(tmp_path, monkeypatch):
    verdicts(monkeypatch, "invalid")
    dotenv = dotenv_of(tmp_path)
    code, out = cli(argv_of(tmp_path), ["1", "плохой"], env={}, dotenv_path=dotenv)
    assert code == 1
    assert not dotenv.exists()
    assert "нет ключа" in out.text


def test_wizard_unverified_key_is_saved_with_note(tmp_path, monkeypatch, adapters):
    verdicts(monkeypatch, ("unverified", "нет сети"))
    dotenv = dotenv_of(tmp_path)
    code, out = cli(argv_of(tmp_path), ["1", KEY, "/quit"], env={}, dotenv_path=dotenv)
    assert code == 0
    assert "Не проверил: нет сети, проверю на первом ходу." in out.text
    assert dotenv_values(dotenv)["OPENROUTER_API_KEY"] == KEY


def test_wizard_cancel_gives_old_missing_key_text_and_creates_nothing(tmp_path, monkeypatch):
    no_verify(monkeypatch)
    dotenv = dotenv_of(tmp_path)
    code, out = cli(argv_of(tmp_path), [], env={}, dotenv_path=dotenv)
    assert code == 1
    assert "нет ключа GEMINI_API_KEY" in out.text
    assert ".env" in out.text
    assert not dotenv.exists()
    assert not (tmp_path / "saves").exists()


def test_wizard_cancel_after_provider_choice_is_same(tmp_path, monkeypatch):
    no_verify(monkeypatch)
    dotenv = dotenv_of(tmp_path)
    code, out = cli(argv_of(tmp_path), ["1"], env={}, dotenv_path=dotenv)
    assert code == 1
    assert "нет ключа GEMINI_API_KEY" in out.text
    assert not dotenv.exists()


# мастера нет

@pytest.mark.parametrize(
    "env",
    [
        {"GEMINI_API_KEY": "g"}, {"ANTHROPIC_API_KEY": "a"}, {"OPENAI_API_KEY": "o"},
        {"OPENROUTER_API_KEY": "r"},
    ],
)
def test_key_in_env_means_no_wizard(tmp_path, monkeypatch, adapters, env):
    no_verify(monkeypatch)
    dotenv = dotenv_of(tmp_path)
    code, out = cli(argv_of(tmp_path), ["/quit"], env=env, dotenv_path=dotenv)
    assert code == 0
    assert "Провайдер" not in out.text
    assert not dotenv.exists()


def test_key_in_dotenv_means_no_wizard(tmp_path, monkeypatch, adapters):
    no_verify(monkeypatch)
    dotenv = dotenv_of(tmp_path)
    dotenv.parent.mkdir()
    dotenv.write_text("OPENAI_API_KEY=o-key\n", encoding="utf-8")
    before = dotenv.read_bytes()
    code, out = cli(argv_of(tmp_path), ["/quit"], env={}, dotenv_path=dotenv)
    assert code == 0
    assert "Провайдер" not in out.text
    assert dotenv.read_bytes() == before


def test_mock_without_keys_has_no_wizard(tmp_path, monkeypatch):
    no_verify(monkeypatch)
    script = write_script(tmp_path / "one.yaml")
    argv = BASE + ["--mock", str(script), "--saves", str(tmp_path / "saves")]
    dotenv = dotenv_of(tmp_path)
    code, out = cli(argv, ["/quit"], env={}, dotenv_path=dotenv)
    assert code == 0
    assert "Провайдер" not in out.text
    assert not dotenv.exists()


def test_replay_without_keys_has_no_wizard(tmp_path, monkeypatch):
    no_verify(monkeypatch)
    argv = ["--replay", "--world", "w1", "--saves", str(tmp_path / "saves")]
    dotenv = dotenv_of(tmp_path)
    cli(argv, [], env={}, dotenv_path=dotenv)
    assert not dotenv.exists()


# память провайдера (AI_DM_PROVIDER)

def test_remembered_provider_beats_roles_narrator(tmp_path, adapters):
    dotenv = dotenv_of(tmp_path)
    dotenv.parent.mkdir()
    dotenv.write_text("OPENROUTER_API_KEY=r\nAI_DM_PROVIDER=deepseek\n", encoding="utf-8")
    code, _ = cli(argv_of(tmp_path), ["/quit"], env={}, dotenv_path=dotenv)
    assert code == 0
    assert adapters.calls[0] == DEEPSEEK


def test_remembered_provider_beats_other_keys_autopick(tmp_path, adapters):
    dotenv = dotenv_of(tmp_path)
    dotenv.parent.mkdir()
    dotenv.write_text(
        "GEMINI_API_KEY=g\nOPENROUTER_API_KEY=r\nAI_DM_PROVIDER=deepseek\n", encoding="utf-8"
    )
    cli(argv_of(tmp_path), ["/quit"], env={}, dotenv_path=dotenv)
    assert adapters.calls[0] == DEEPSEEK


def test_remembered_provider_from_environment_overrides_dotenv(tmp_path, adapters):
    dotenv = dotenv_of(tmp_path)
    dotenv.parent.mkdir()
    dotenv.write_text("OPENROUTER_API_KEY=r\nAI_DM_PROVIDER=deepseek\n", encoding="utf-8")
    env = {"AI_DM_PROVIDER": "qwen"}
    cli(argv_of(tmp_path), ["/quit"], env=env, dotenv_path=dotenv)
    assert adapters.calls[0] == ("openrouter", "qwen/qwen3-235b-a22b-2507")


def test_explicit_provider_flag_beats_remembered(tmp_path, adapters):
    dotenv = dotenv_of(tmp_path)
    dotenv.parent.mkdir()
    dotenv.write_text("OPENROUTER_API_KEY=r\nAI_DM_PROVIDER=deepseek\n", encoding="utf-8")
    cli(argv_of(tmp_path) + ["--provider", "qwen"], ["/quit"], env={}, dotenv_path=dotenv)
    assert adapters.calls[0] == ("openrouter", "qwen/qwen3-235b-a22b-2507")


def test_unknown_remembered_profile_is_error_code_1(tmp_path, adapters):
    dotenv = dotenv_of(tmp_path)
    dotenv.parent.mkdir()
    dotenv.write_text("GEMINI_API_KEY=g\nAI_DM_PROVIDER=nope\n", encoding="utf-8")
    code, out = cli(argv_of(tmp_path), ["/quit"], env={}, dotenv_path=dotenv)
    assert code == 1
    assert "Ошибка: нет профиля nope" in out.text
    assert "deepseek" in out.text
    assert adapters.calls == []


def test_empty_remembered_provider_is_ignored(tmp_path, adapters):
    dotenv = dotenv_of(tmp_path)
    dotenv.parent.mkdir()
    dotenv.write_text("ANTHROPIC_API_KEY=a\nAI_DM_PROVIDER=\n", encoding="utf-8")
    code, _ = cli(argv_of(tmp_path), ["/quit"], env={}, dotenv_path=dotenv)
    assert code == 0
    assert adapters.calls[0][0] == "anthropic"


def test_no_remembered_provider_keeps_old_choice(tmp_path, adapters):
    cli(argv_of(tmp_path), ["/quit"], env={"GEMINI_API_KEY": "g"}, dotenv_path=dotenv_of(tmp_path))
    assert adapters.calls[0][0] == "gemini"


# /key в игре

def test_key_command_in_game_saves_key_and_rekeys(tmp_path, monkeypatch, adapters):
    verdicts(monkeypatch, "ok")
    dotenv = dotenv_of(tmp_path)
    dotenv.parent.mkdir()
    dotenv.write_text("# мои\nGEMINI_API_KEY=g\n", encoding="utf-8")
    lines = ["/key", "3", "sk-ant-new-ZZ99", "/quit"]
    code, out = cli(argv_of(tmp_path), lines, env={}, dotenv_path=dotenv)
    assert code == 0
    assert dotenv.read_text(encoding="utf-8") == (
        "# мои\nGEMINI_API_KEY=g\nANTHROPIC_API_KEY=sk-ant-new-ZZ99\n"
    )
    assert "…ZZ99" in out.text
    assert "sk-ant-new-ZZ99" not in out.text
    assert "сменить модель — /model" in out.text


def test_key_command_does_not_change_remembered_provider(tmp_path, monkeypatch, adapters):
    verdicts(monkeypatch, "ok")
    dotenv = dotenv_of(tmp_path)
    dotenv.parent.mkdir()
    dotenv.write_text("GEMINI_API_KEY=g\nAI_DM_PROVIDER=gemini\n", encoding="utf-8")
    cli(argv_of(tmp_path), ["/key", "3", "ant-key-0001", "/quit"], env={}, dotenv_path=dotenv)
    assert read_var("AI_DM_PROVIDER", env={}, dotenv_path=dotenv) == "gemini"


def test_key_command_existing_key_no_keeps_file_byte_identical(tmp_path, monkeypatch, adapters):
    no_verify(monkeypatch)
    dotenv = dotenv_of(tmp_path)
    dotenv.parent.mkdir()
    dotenv.write_text("# мои\nGEMINI_API_KEY=old\nX=1", encoding="utf-8")
    before = dotenv.read_bytes()
    cli(argv_of(tmp_path), ["/key", "2", "2", "/quit"], env={}, dotenv_path=dotenv)
    assert dotenv.read_bytes() == before


def test_key_command_existing_key_yes_replaces_only_that_line(tmp_path, monkeypatch, adapters):
    verdicts(monkeypatch, "ok")
    dotenv = dotenv_of(tmp_path)
    dotenv.parent.mkdir()
    dotenv.write_text("# мои\nGEMINI_API_KEY=old\nX=1\n", encoding="utf-8")
    lines = ["/key", "2", "1", "g-new-0042", "/quit"]
    code, out = cli(argv_of(tmp_path), lines, env={}, dotenv_path=dotenv)
    assert code == 0
    assert "Ключ Gemini уже есть — заменить?" in out.text
    assert dotenv.read_text(encoding="utf-8") == "# мои\nGEMINI_API_KEY=g-new-0042\nX=1\n"


def test_key_command_rekeys_current_provider_through_factory(tmp_path, monkeypatch, adapters):
    verdicts(monkeypatch, "ok")
    dotenv = dotenv_of(tmp_path)
    dotenv.parent.mkdir()
    dotenv.write_text("GEMINI_API_KEY=g\n", encoding="utf-8")
    before = len(adapters.calls)
    _, out = cli(
        argv_of(tmp_path), ["/key", "2", "1", "g-new-0042", "/quit"], env={}, dotenv_path=dotenv
    )
    assert "Ключ gemini подключён." in out.text
    assert len(adapters.calls) > before


# страж решения 14: ключ-маркер не утекает

def raising_client(key):
    class StatusError(Exception):
        def __init__(self):
            super().__init__(f"Incorrect API key provided: {key}")
            self.status_code = 401
            self.response = SimpleNamespace(headers={})

    def create(**kwargs):
        raise StatusError()

    completions = SimpleNamespace(create=create)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


def files_under(root):
    return [p for p in Path(root).rglob("*") if p.is_file()]


def test_guard_marker_key_is_not_in_world_files_or_output_after_401(tmp_path, monkeypatch):
    verdicts(monkeypatch, "ok")
    dotenv = dotenv_of(tmp_path)

    def failing_adapter(provider, model, app_cfg, *, env=None, dotenv_path=None):
        key = read_var("OPENROUTER_API_KEY", env=env, dotenv_path=dotenv_path)
        return ChatCompletionsAdapter(
            provider, model, app_cfg, client_factory=lambda **kw: raising_client(key),
            api_key=key,
        )

    monkeypatch.setattr("ai_dm.ui.cli.make_adapter", failing_adapter)
    lines = ["1", KEY, "Иду", "1", "/report ключ не принят", "/quit"]
    code, out = cli(argv_of(tmp_path), lines, env={}, dotenv_path=dotenv)
    assert "не принят" in out.text
    assert "/key" in out.text
    saved = files_under(tmp_path / "saves")
    assert saved
    prefix = KEY[:-4].encode()
    assert [p for p in saved if prefix in p.read_bytes()] == []
    assert KEY not in out.text
    assert KEY[:-4] not in out.text
    assert code == 0


def test_guard_world_has_failure_files_to_check(tmp_path, monkeypatch):
    # страж не пустой: после 401 в мире есть журнал вызовов
    verdicts(monkeypatch, "ok")
    dotenv = dotenv_of(tmp_path)

    def failing_adapter(provider, model, app_cfg, *, env=None, dotenv_path=None):
        key = read_var("OPENROUTER_API_KEY", env=env, dotenv_path=dotenv_path)
        return ChatCompletionsAdapter(
            provider, model, app_cfg, client_factory=lambda **kw: raising_client(key),
            api_key=key,
        )

    monkeypatch.setattr("ai_dm.ui.cli.make_adapter", failing_adapter)
    lines = ["1", KEY, "Иду", "/report ключ не принят", "/quit"]
    cli(argv_of(tmp_path), lines, env={}, dotenv_path=dotenv)
    names = {p.name for p in files_under(tmp_path / "saves")}
    assert any(name.startswith("calls-") for name in names)
    assert "report.md" in names
