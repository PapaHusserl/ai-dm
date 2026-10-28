from dataclasses import dataclass
from pathlib import Path

from ai_dm.llm.factory import verify_key
from ai_dm.llm.keys import KEY_VARS, parse_dotenv, write_dotenv_var
from ai_dm.ui.hero_session import menu_number
from ai_dm.ui.screen import menu_block, note_block
from ai_dm.ui.session import Step

# (провайдер, подпись, профиль для памяти мастера, где взять ключ); у OpenRouter профиль --
# deepseek: его рассказчик deepseek/deepseek-v4-flash
PROVIDERS = (
    ("openrouter", "OpenRouter", "deepseek", "https://openrouter.ai/keys"),
    ("gemini", "Gemini", "gemini", "https://aistudio.google.com/apikey"),
    ("anthropic", "Anthropic", "anthropic", "https://console.anthropic.com/settings/keys"),
    ("openai", "OpenAI", "openai", "https://platform.openai.com/api-keys"),
)
PROVIDER_VAR = "AI_DM_PROVIDER"
INTRO = "Для игры нужен ключ API. Выберите провайдера, ключ сохранится на этом компьютере."
PROVIDER_TITLE = "Провайдер:"
CONFIRM_TITLE = "Ключ {label} уже есть — заменить?"
CONFIRM_MENU = ["Да", "Нет"]
KEY_HINT = "Где взять ключ: {url}. Вставьте ключ (ввод скрыт); пустая строка — повтор подсказки."
INVALID = "Ключ не подошёл, ещё раз?"
UNVERIFIED = "Не проверил: {text}, проверю на первом ходу."
SAVED = "Ключ …{tail} сохранён в {path}."
SHADOWED = "Переменная {var} перекрывает .env: новый ключ заработает после её снятия."
NO_SUCH = "Нет такого варианта."


@dataclass
class KeyDeps:
    app_cfg: object
    env: object
    dotenv_path: object
    # ключи, которые маскируются в выводе; новый ключ добавляется сюда
    secrets: list
    verify: object = verify_key


@dataclass
class KeySession:
    # ввод ключа API без терминала: состояния provider, confirm, key; итог -- saved, provider,
    # tail (последние 4 символа ключа); remember -- запомнить провайдера как рассказчика
    deps: object
    remember: bool = False
    state: str = "provider"
    choice: tuple = None
    saved: bool = False
    provider: str = None
    tail: str = None

    def start(self):
        labels = [label for _, label, _, _ in PROVIDERS]
        return Step([note_block(INTRO), menu_block(labels, PROVIDER_TITLE)])

    def submit(self, line):
        if line is None:
            return Step(quit=True)
        line = line.strip()
        if self.state == "provider":
            return self.pick(line)
        if self.state == "confirm":
            return self.confirm(line)
        return self.enter(line)

    def var(self):
        provider = self.choice[0]
        host = self.deps.app_cfg.providers.get(provider)
        return KEY_VARS[provider] if host is None else host.key_env

    def has_key(self):
        try:
            values = parse_dotenv(Path(self.deps.dotenv_path).read_text(encoding="utf-8"))
        except OSError:
            return False
        return bool(values.get(self.var()))

    def key_step(self):
        self.state = "key"
        return Step([note_block(KEY_HINT.format(url=self.choice[3]))])

    def pick(self, line):
        number = menu_number(line, PROVIDERS)
        if number is None:
            return Step([note_block(NO_SUCH)])
        self.choice = PROVIDERS[number - 1]
        if not self.has_key():
            return self.key_step()
        self.state = "confirm"
        title = CONFIRM_TITLE.format(label=self.choice[1])
        return Step([menu_block(CONFIRM_MENU, title)])

    def confirm(self, line):
        number = menu_number(line, CONFIRM_MENU)
        if number is None:
            return Step([note_block(NO_SUCH)])
        if number == 2:
            return Step(quit=True)
        return self.key_step()

    def enter(self, key):
        if not key:
            return Step([note_block(KEY_HINT.format(url=self.choice[3]))])
        deps = self.deps
        provider, _, profile, _ = self.choice
        verdict = deps.verify(provider, key, deps.app_cfg)
        if verdict == "invalid":
            return Step([note_block(INVALID)])
        blocks = []
        if verdict != "ok":
            blocks.append(note_block(UNVERIFIED.format(text=verdict[1].rstrip("."))))
        write_dotenv_var(deps.dotenv_path, self.var(), key)
        deps.secrets.append(key)
        if self.remember:
            write_dotenv_var(deps.dotenv_path, PROVIDER_VAR, profile)
        self.saved = True
        self.provider = provider
        self.tail = key[-4:]
        blocks.append(note_block(SAVED.format(tail=self.tail, path=deps.dotenv_path)))
        if deps.env.get(self.var()):
            blocks.append(note_block(SHADOWED.format(var=self.var())))
        return Step(blocks, quit=True)
