import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_dm.config.settings import DEFAULTS_PATH, RulesConfig, deep_merge

APP_DEFAULTS_PATH = Path(__file__).parent / "app_defaults.toml"


class ModelRole(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str
    model: str
    effort: str | None = None
    max_tokens: int


class RolesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    narrator: ModelRole
    world: ModelRole
    summarizer: ModelRole
    # необязательна: профиль без import берёт roles.import из defaults
    import_: ModelRole | None = Field(default=None, alias="import")


class AlternativesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    narrator: ModelRole


class ModelPrice(BaseModel):
    # микро-доллары за 1 млн токенов
    model_config = ConfigDict(extra="forbid", strict=True)
    input: int
    output: int
    cache_read: int
    cache_write: int
    # запись кэша с TTL 1h; не задана -- как cache_write
    cache_write_1h: int | None = None
    # хранение явного кэша, за 1 млн токенов в час (0 -- нет явного кэша)
    cache_storage_hour: int = 0

    @model_validator(mode="after")
    def default_cache_write_1h(self):
        if self.cache_write_1h is None:
            self.cache_write_1h = self.cache_write
        return self


class RetryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    delays: list[int]
    invalid_retries: int
    max_tool_rounds: int
    timeout_s: int


class JournalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_mb: int
    segment_mb: int


class CostLimitsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    warn_percent: int
    session_limit_micro: int = 0
    day_limit_micro: int = 0


class MasterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recent_turns: int
    recent_turns_keep: int = 50
    key_npc_consult_hp_percent: int
    # потолок входа нарратора в токенах (Д1); дальше min(80% окна, потолок)
    context_cap: int = Field(gt=0)
    # оценка токенов: символов в токене (кириллица)
    chars_per_token: float = Field(gt=0)
    # сколько последних ходов не вытесняется до ступени 2
    recent_turns_floor: int = Field(ge=0)

    @model_validator(mode="after")
    def check_floor(self):
        if self.recent_turns_floor > self.recent_turns:
            raise ValueError("master.recent_turns_floor больше master.recent_turns")
        return self


class LlmConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refusal_fallback: bool
    strict_tools: bool
    cache_ttl: Literal["5m", "1h"] = "1h"
    # явный кэш роли world, только Gemini (редкие вызовы, хранение дороже); по умолчанию выкл.
    gemini_cache_world: bool = False
    # safety_settings Gemini: block_none/off снимают фильтры, default не передаёт
    gemini_safety: Literal["default", "block_none", "off"] = "block_none"


class UiConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    width: int = 80


class WorldConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # потолок вызовов роли world в игровой день; 0 = выключено (лимиты 2.0 мягкие)
    max_calls_per_day: int = Field(default=0, ge=0)


class MemoryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # пределы длины выжимок (символы)
    scene_summary_max: int = Field(default=600, ge=1)
    chapter_summary_max: int = Field(default=1500, ge=1)
    game_summary_max: int = Field(default=3000, ge=1)


class ReportsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # сколько последних ходов (вместе с самим ходом) попадает в report.md
    recent_turns: int = Field(default=5, ge=1)


class PersistenceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # fsync файлов и каталогов сейва (F_FULLFSYNC на macOS)
    durable: bool = True


class ImportConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # предел длины текстовой выжимки для import пака (символы)
    max_chars: int = Field(default=60000, ge=1)


class AudioConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True
    # громкость, 0-100
    volume: int = Field(default=60, ge=0, le=100)
    ambient: bool = True
    # громкость эмбиента относительно музыки, %
    ambient_percent: int = Field(default=50, ge=0, le=100)
    crossfade_s: float = Field(default=2.0, ge=0)
    # смена темы не чаще раза в столько секунд (бой -- сразу)
    min_switch_s: float = Field(default=20.0, ge=0)
    # размер буфера звукового устройства, мс
    buffer_ms: int = Field(default=200, ge=20)


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    roles: RolesConfig
    alternatives: AlternativesConfig
    prices: dict[str, ModelPrice]
    context_windows: dict[str, int]
    retry: RetryConfig
    journal: JournalConfig
    cost_limits: CostLimitsConfig
    master: MasterConfig
    llm: LlmConfig
    ui: UiConfig = UiConfig()
    world: WorldConfig = WorldConfig()
    memory: MemoryConfig = MemoryConfig()
    reports: ReportsConfig = ReportsConfig()
    persistence: PersistenceConfig = PersistenceConfig()
    audio: AudioConfig = AudioConfig()
    import_: ImportConfig = Field(default_factory=ImportConfig, alias="import")
    profiles: dict[str, RolesConfig] = {}

    @model_validator(mode="after")
    def check_models_known(self):
        roles = [self.roles.narrator, self.roles.world, self.roles.summarizer]
        roles.append(self.roles.import_)
        roles.append(self.alternatives.narrator)
        for profile in self.profiles.values():
            roles += [profile.narrator, profile.world, profile.summarizer, profile.import_]
        for role in roles:
            if role is None:
                continue
            if role.model not in self.prices:
                raise ValueError(f"нет цены для модели {role.model}")
            if role.model not in self.context_windows:
                raise ValueError(f"нет окна контекста для модели {role.model}")
        return self


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rules: RulesConfig
    app: AppConfig

    @model_validator(mode="after")
    def check_turns_keep(self):
        # иначе summarizer не увидит начало длинной сцены
        # сцена закрывается при player_turns > max_player_turns, т.е. в ней max + 1 ходов
        if self.app.master.recent_turns_keep < self.rules.scene.max_player_turns + 1:
            raise ValueError(
                "master.recent_turns_keep меньше scene.max_player_turns + 1: "
                "summarizer не увидит начало длинной сцены"
            )
        return self


def load_settings(toml_text: str | None = None, path: Path | None = None) -> Settings:
    data = tomllib.loads(DEFAULTS_PATH.read_text(encoding="utf-8"))
    data = {"rules": data, **tomllib.loads(APP_DEFAULTS_PATH.read_text(encoding="utf-8"))}
    if toml_text is not None:
        data = deep_merge(data, tomllib.loads(toml_text))
    if path is not None:
        data = deep_merge(data, tomllib.loads(path.read_text(encoding="utf-8")))
    rules = data.pop("rules")
    return Settings(rules=RulesConfig.model_validate(rules), app=AppConfig.model_validate(data))
