# Ожидаемый API: ai_dm.config.app (+ ai_dm/config/app_defaults.toml в пакете), этап 2, партия 1
#   AppConfig(BaseModel, extra="forbid" на всех уровнях) -- настройки приложения (не правила игры):
#     .roles.narrator / .roles.world / .roles.summarizer: ModelRole(provider: str, model: str,
#         effort: str | None, max_tokens: int)
#         narrator: provider "anthropic", model "claude-opus-5-5", effort "low" (C3),
#         max_tokens 16000;
#         world и summarizer: provider "anthropic", model "claude-haiku-4-5" (на этапе 2 описаны,
#         не вызываются)
#     .alternatives.narrator: ModelRole -- профиль-альтернатива narrator (по выбору игрока):
#         provider "anthropic", model "claude-sonnet-5-5"
#     .prices: dict[str, ModelPrice] -- ключ model id; ModelPrice(input, output, cache_read,
#         cache_write): int, МИКРО-ДОЛЛАРЫ за 1 млн токенов (1 $ = 1_000_000), без float
#         claude-opus-5-5:   вход 4_000_000, выход 20_000_000, чтение кэша 200_000
#         claude-sonnet-5-5: вход 2_000_000, выход 10_000_000, чтение кэша 200_000
#         claude-haiku-4-5:  вход 1_000_000, выход 5_000_000
#         запись кэша (cache_write) = 1.25 x вход у всех трёх: 5_000_000 / 2_500_000 / 1_250_000
#         (чтение кэша у Haiku в ТЗ не названо -- проверяем только 0 < cache_read < input)
#     .context_windows: dict[str, int] -- токены: opus и sonnet 1_000_000, haiku 200_000
#     .retry: delays=[1, 3, 10] (list[int], секунды), invalid_retries=2, max_tool_rounds=8,
#         timeout_s=180
#     .journal: max_mb=50, segment_mb=5
#     .cost_limits: enabled=False, warn_percent=80
#     .master: recent_turns=8, context_cap=30000, chars_per_token=2.5, recent_turns_floor=1,
#         key_npc_consult_hp_percent=50
#     .llm: refusal_fallback=False (решение проектировщика 1), strict_tools=True
#   load_settings(toml_text: str | None = None, path: Path | None = None) -> Settings
#     Settings: .rules: RulesConfig, .app: AppConfig. Те же правила, что load_rules_config:
#     defaults (defaults.toml + app_defaults.toml) + пользовательский ai-dm.toml (строка и/или
#     файл; файл поверх строки) с deep merge. Секции [rules.*] идут в RulesConfig (без префикса
#     "rules": [rules.scene] -> rules.scene), остальные -- в AppConfig. Неизвестный ключ в любом
#     месте (в т.ч. неизвестная секция верхнего уровня и [rules.bogus]) -> pydantic.ValidationError.
#     Глобального состояния нет: каждый вызов возвращает новые объекты.
import pytest
from pydantic import ValidationError

from ai_dm.config.app import AppConfig, ModelPrice, load_settings
from ai_dm.config.settings import RulesConfig

OPUS = "claude-opus-5-5"
SONNET = "claude-sonnet-5-5"
HAIKU = "claude-haiku-4-5"


def app():
    return load_settings().app


def test_defaults_load():
    settings = load_settings()
    assert isinstance(settings.app, AppConfig)
    assert isinstance(settings.rules, RulesConfig)


def test_narrator_role_is_gemini_by_default():
    narrator = app().roles.narrator
    assert narrator.provider == "gemini"
    assert narrator.model == GEMINI_FLASH
    assert narrator.max_tokens == 16000


def test_anthropic_profile_narrator_is_opus():
    narrator = app().profiles["anthropic"].narrator
    assert narrator.provider == "anthropic"
    assert narrator.model == OPUS
    assert narrator.effort == "low"
    assert narrator.max_tokens == 16000


@pytest.mark.parametrize("name", ["world", "summarizer"])
def test_helper_roles_use_haiku(name):
    role = getattr(app().profiles["anthropic"], name)
    assert role.provider == "anthropic"
    assert role.model == HAIKU


def test_narrator_alternative_is_sonnet():
    alt = app().alternatives.narrator
    assert alt.provider == "anthropic"
    assert alt.model == SONNET


def test_opus_prices():
    price = app().prices[OPUS]
    assert (price.input, price.output, price.cache_read) == (4_000_000, 20_000_000, 200_000)


def test_sonnet_prices():
    price = app().prices[SONNET]
    assert (price.input, price.output, price.cache_read) == (2_000_000, 10_000_000, 200_000)


def test_haiku_prices():
    price = app().prices[HAIKU]
    assert (price.input, price.output) == (1_000_000, 5_000_000)
    assert 0 < price.cache_read < price.input


@pytest.mark.parametrize(
    "model, cache_write", [(OPUS, 5_000_000), (SONNET, 2_500_000), (HAIKU, 1_250_000)]
)
def test_cache_write_is_1_25_input_for_5m_ttl(model, cache_write):
    price = app().prices[model]
    assert price.cache_write == cache_write
    assert price.cache_write * 4 == price.input * 5


@pytest.mark.parametrize(
    "model, cache_write_1h", [(OPUS, 8_000_000), (SONNET, 4_000_000), (HAIKU, 2_000_000)]
)
def test_cache_write_1h_is_double_input(model, cache_write_1h):
    price = app().prices[model]
    assert price.cache_write_1h == cache_write_1h
    assert price.cache_write_1h == price.input * 2


def test_prices_are_integers():
    for price in app().prices.values():
        for value in (price.input, price.output, price.cache_read, price.cache_write):
            assert type(value) is int


def test_every_role_model_has_price_and_context_window():
    config = app()
    models = {role.model for role in (
        config.roles.narrator, config.roles.world, config.roles.summarizer,
        config.alternatives.narrator,
    )}
    assert models <= set(config.prices)
    assert models <= set(config.context_windows)


def test_context_windows():
    windows = app().context_windows
    assert windows[OPUS] == 1_000_000
    assert windows[SONNET] == 1_000_000
    assert windows[HAIKU] == 200_000


def test_retry_defaults():
    retry = app().retry
    assert retry.delays == [1, 3, 10]
    assert retry.invalid_retries == 2
    assert retry.max_tool_rounds == 8
    assert retry.timeout_s == 180


def test_journal_defaults():
    journal = app().journal
    assert journal.max_mb == 50
    assert journal.segment_mb == 5


def test_cost_limits_are_off_by_default():
    limits = app().cost_limits
    assert limits.enabled is False
    assert limits.warn_percent == 80


def test_master_defaults():
    master = app().master
    assert master.recent_turns == 8
    assert master.key_npc_consult_hp_percent == 50
    assert master.context_cap == 30000
    assert master.chars_per_token == 2.5
    assert master.recent_turns_floor == 1


def test_llm_defaults():
    llm = app().llm
    assert llm.refusal_fallback is False
    assert llm.strict_tools is True


# load_settings: пользовательский ai-dm.toml

def test_user_toml_overrides_app_value():
    settings = load_settings("[master]\nrecent_turns = 12\n")
    assert settings.app.master.recent_turns == 12
    assert settings.app.master.key_npc_consult_hp_percent == 50


def test_user_toml_deep_merge_keeps_other_role_keys():
    settings = load_settings('[roles.narrator]\neffort = "high"\n')
    narrator = settings.app.roles.narrator
    assert narrator.effort == "high"
    assert narrator.model == GEMINI_FLASH
    assert narrator.max_tokens == 16000
    assert settings.app.roles.world.model == GEMINI_LITE


def test_user_toml_can_enable_refusal_fallback():
    assert load_settings("[llm]\nrefusal_fallback = true\n").app.llm.refusal_fallback is True


def test_rules_section_goes_to_rules_config():
    settings = load_settings("[rules.combat]\nmax_rounds = 50\n")
    assert settings.rules.combat.max_rounds == 50
    assert settings.rules.combat.improvise_damage_dice == "1d6"


def test_rules_and_app_sections_in_one_file():
    text = "[rules.scene]\nmax_player_turns = 10\n\n[master]\nrecent_turns = 4\n"
    settings = load_settings(text)
    assert settings.rules.scene.max_player_turns == 10
    assert settings.app.master.recent_turns == 4


def test_rules_section_does_not_leak_into_app():
    settings = load_settings("[rules.combat]\nmax_rounds = 50\n")
    assert not hasattr(settings.app, "combat")
    assert not hasattr(settings.app, "rules")


def test_user_file_is_read_from_path(tmp_path):
    path = tmp_path / "ai-dm.toml"
    text = "[journal]\nmax_mb = 10\n\n[rules.xp]\nquest_minor_percent = 5\n"
    path.write_text(text, encoding="utf-8")
    settings = load_settings(path=path)
    assert settings.app.journal.max_mb == 10
    assert settings.app.journal.segment_mb == 5
    assert settings.rules.xp.quest_minor_percent == 5


def test_path_overrides_text(tmp_path):
    path = tmp_path / "ai-dm.toml"
    path.write_text("[master]\nrecent_turns = 3\n", encoding="utf-8")
    settings = load_settings("[master]\nrecent_turns = 9\n", path=path)
    assert settings.app.master.recent_turns == 3


def test_unknown_top_level_section_is_rejected():
    with pytest.raises(ValidationError):
        load_settings("[bogus]\nx = 1\n")


def test_unknown_key_in_app_section_is_rejected():
    with pytest.raises(ValidationError):
        load_settings("[master]\nbogus = 1\n")


def test_unknown_key_in_nested_role_is_rejected():
    with pytest.raises(ValidationError):
        load_settings("[roles.narrator]\nbogus = 1\n")


def test_unknown_rules_section_is_rejected():
    with pytest.raises(ValidationError):
        load_settings("[rules.bogus]\nx = 1\n")


def test_unknown_key_in_rules_section_is_rejected():
    with pytest.raises(ValidationError):
        load_settings("[rules.scene]\nbogus = 1\n")


def test_app_config_rejects_extra_key():
    data = app().model_dump()
    data["bogus"] = 1
    with pytest.raises(ValidationError):
        AppConfig.model_validate(data)


def test_each_call_returns_new_objects():
    first = load_settings()
    second = load_settings()
    assert first.app is not second.app
    assert first.rules is not second.rules
    first.app.master.recent_turns = 1
    assert load_settings().app.master.recent_turns == 8


# пользовательский TOML: модель роли без цены или окна (ревью партии 1, п.3)

@pytest.mark.parametrize("role", ["narrator", "world", "summarizer", "import"])
def test_role_model_without_price_is_rejected(role):
    text = f'[roles.{role}]\nmodel = "claude-new-9"\n'
    text += "\n[context_windows]\nclaude-new-9 = 100000\n"
    with pytest.raises(ValidationError):
        load_settings(text)


@pytest.mark.parametrize("role", ["narrator", "world", "summarizer", "import"])
def test_role_model_without_context_window_is_rejected(role):
    text = f'[roles.{role}]\nmodel = "claude-new-9"\n'
    text += "\n[prices.claude-new-9]\ninput = 1\noutput = 1\ncache_read = 1\n"
    text += "cache_write = 1\ncache_write_1h = 1\n"
    with pytest.raises(ValidationError):
        load_settings(text)


def test_alternative_model_without_price_is_rejected():
    text = '[alternatives.narrator]\nmodel = "claude-new-9"\n'
    text += "\n[context_windows]\nclaude-new-9 = 100000\n"
    with pytest.raises(ValidationError):
        load_settings(text)


def test_alternative_model_without_context_window_is_rejected():
    text = '[alternatives.narrator]\nmodel = "claude-new-9"\n'
    text += "\n[prices.claude-new-9]\ninput = 1\noutput = 1\ncache_read = 1\n"
    text += "cache_write = 1\ncache_write_1h = 1\n"
    with pytest.raises(ValidationError):
        load_settings(text)


def test_new_model_with_price_and_window_is_accepted():
    text = '[roles.world]\nmodel = "claude-new-9"\n'
    text += "\n[prices.claude-new-9]\ninput = 1\noutput = 1\ncache_read = 1\n"
    text += "cache_write = 1\ncache_write_1h = 1\n"
    text += "\n[context_windows]\nclaude-new-9 = 100000\n"
    assert load_settings(text).app.roles.world.model == "claude-new-9"


# цена только целая (ревью партии 1, п.4)

def test_float_price_in_user_toml_is_rejected():
    with pytest.raises(ValidationError):
        load_settings(f"[prices.{OPUS}]\ninput = 4000000.0\n")


def test_fractional_price_in_user_toml_is_rejected():
    with pytest.raises(ValidationError):
        load_settings(f"[prices.{OPUS}]\ncache_read = 200000.5\n")


def test_model_price_rejects_float():
    with pytest.raises(ValidationError):
        ModelPrice(input=1.0, output=1, cache_read=1, cache_write=1)


# ревью партии 3: Gemini в конфиге (B2)

GEMINI_FLASH = "gemini-3.8-flash"
GEMINI_LITE = "gemini-3.5-flash-lite"
PRICE_FIELDS = ("input", "output", "cache_read", "cache_write")


def test_gemini_flash_prices():
    price = app().prices[GEMINI_FLASH]
    assert (price.input, price.output, price.cache_read) == (750_000, 3_750_000, 75_000)


def test_gemini_lite_prices():
    price = app().prices[GEMINI_LITE]
    assert (price.input, price.output, price.cache_read) == (300_000, 2_500_000, 30_000)


@pytest.mark.parametrize("model", [GEMINI_FLASH, GEMINI_LITE])
def test_gemini_cache_write_equals_input(model):
    price = app().prices[model]
    assert price.cache_write == price.input


@pytest.mark.parametrize("model", [GEMINI_FLASH, GEMINI_LITE])
def test_gemini_context_window(model):
    assert app().context_windows[model] == 1_000_000


def test_profiles_is_a_dict():
    assert isinstance(app().profiles, dict)


def test_gemini_profile_roles():
    profile = app().profiles["gemini"]
    assert (profile.narrator.provider, profile.narrator.model) == ("gemini", GEMINI_FLASH)
    assert (profile.world.provider, profile.world.model) == ("gemini", GEMINI_LITE)
    assert (profile.summarizer.provider, profile.summarizer.model) == ("gemini", GEMINI_LITE)


@pytest.mark.parametrize("name", ["narrator", "world", "summarizer"])
def test_gemini_profile_roles_have_max_tokens(name):
    assert getattr(app().profiles["gemini"], name).max_tokens > 0


def test_gemini_profile_models_have_price_and_window():
    config = app()
    profile = config.profiles["gemini"]
    for role in (profile.narrator, profile.world, profile.summarizer):
        assert role.model in config.prices
        assert role.model in config.context_windows


def test_gemini_profile_model_is_rejected_without_price():
    text = '[profiles.gemini.narrator]\nmodel = "gemini-new-9"\n'
    text += "\n[context_windows]\ngemini-new-9 = 100000\n"
    with pytest.raises(ValidationError):
        load_settings(text)


def test_gemini_profile_model_is_rejected_without_context_window():
    text = '[profiles.gemini.world]\nmodel = "gemini-new-9"\n'
    text += "\n[prices.gemini-new-9]\ninput = 1\noutput = 1\ncache_read = 1\n"
    text += "cache_write = 1\ncache_write_1h = 1\n"
    with pytest.raises(ValidationError):
        load_settings(text)


@pytest.mark.parametrize("name", ["narrator", "world", "summarizer"])
def test_unknown_model_in_profile_role_is_rejected(name):
    text = f'[profiles.gemini.{name}]\nmodel = "gemini-unknown"\n'
    with pytest.raises(ValidationError, match="gemini-unknown"):
        load_settings(text)


def test_new_profile_with_known_models_is_accepted():
    roles = "".join(
        f'\n[profiles.mixed.{name}]\nprovider = "gemini"\n'
        f'model = "{GEMINI_LITE}"\nmax_tokens = 100\n'
        for name in ("narrator", "world", "summarizer", "import")
    )
    assert load_settings(roles).app.profiles["mixed"].world.model == GEMINI_LITE


def test_gemini_prices_are_integers():
    for model in (GEMINI_FLASH, GEMINI_LITE):
        for field in PRICE_FIELDS:
            assert type(getattr(app().prices[model], field)) is int


def test_master_recent_turns_keep_defaults_to_50():
    assert app().master.recent_turns_keep == 50


def test_master_recent_turns_keep_can_be_overridden():
    settings = load_settings("[master]\nrecent_turns_keep = 40\n")
    assert settings.app.master.recent_turns_keep == 40
    assert settings.app.master.recent_turns == 8


def test_narrator_effort_is_low_by_default():
    assert app().profiles["anthropic"].narrator.effort == "low"


def test_narrator_alternative_effort_is_low_by_default():
    assert app().alternatives.narrator.effort == "low"


def test_cache_ttl_is_one_hour_by_default():
    assert app().llm.cache_ttl == "1h"


def test_user_toml_can_set_cache_ttl_five_minutes():
    assert load_settings('[llm]\ncache_ttl = "5m"\n').app.llm.cache_ttl == "5m"


def test_cache_ttl_rejects_unknown_value():
    with pytest.raises(ValidationError):
        load_settings('[llm]\ncache_ttl = "2h"\n')


def test_ui_width_is_80_by_default():
    assert app().ui.width == 80


def test_default_roles_equal_gemini_profile():
    config = app()
    assert config.roles == config.profiles["gemini"]


def test_cache_write_1h_defaults_to_cache_write():
    from ai_dm.config.app import ModelPrice
    price = ModelPrice(input=1, output=2, cache_read=3, cache_write=4)
    assert price.cache_write_1h == 4


# этап 4, P1: recent_turns_keep >= scene.max_player_turns (иначе summarizer не увидит начало сцены)

def test_recent_turns_keep_below_scene_turn_limit_is_rejected():
    with pytest.raises(ValidationError):
        load_settings("[master]\nrecent_turns_keep = 10\n")


def test_recent_turns_keep_equal_to_scene_turn_limit_is_rejected():
    # сцена закрывается при player_turns > max, то есть в ней бывает max + 1 ход
    text = "[rules.scene]\nmax_player_turns = 30\n\n[master]\nrecent_turns_keep = 30\n"
    with pytest.raises(ValidationError):
        load_settings(text)


def test_recent_turns_keep_one_above_scene_turn_limit_is_allowed():
    text = "[rules.scene]\nmax_player_turns = 30\n\n[master]\nrecent_turns_keep = 31\n"
    assert load_settings(text).app.master.recent_turns_keep == 31


def test_raising_scene_turn_limit_above_keep_is_rejected():
    with pytest.raises(ValidationError):
        load_settings("[rules.scene]\nmax_player_turns = 80\n")


def test_default_settings_keep_covers_scene_turn_limit():
    settings = load_settings()
    assert settings.app.master.recent_turns_keep >= settings.rules.scene.max_player_turns + 1


def test_memory_limits_defaults():
    memory = app().memory
    assert memory.scene_summary_max == 600
    assert memory.chapter_summary_max == 1500
    assert memory.game_summary_max == 3000


def test_raising_scene_turn_limit_to_keep_is_rejected():
    with pytest.raises(ValidationError):
        load_settings("[rules.scene]\nmax_player_turns = 50\n\n[master]\nrecent_turns_keep = 50\n")


def test_gemini_cache_world_flag_can_be_enabled():
    settings = load_settings("[llm]\ngemini_cache_world = true\n")
    assert settings.app.llm.gemini_cache_world is True


# P3: бюджет контекста

@pytest.mark.parametrize(
    "text",
    [
        "[master]\ncontext_cap = 0\n",
        "[master]\ncontext_cap = -1\n",
        "[master]\nchars_per_token = 0\n",
        "[master]\nchars_per_token = -2.5\n",
        "[master]\nrecent_turns_floor = -1\n",
        "[master]\nrecent_turns = 4\nrecent_turns_floor = 5\n",
        "[master]\nrecent_turns_floor = 9\n",
    ],
)
def test_master_context_settings_are_validated(text):
    with pytest.raises(ValidationError):
        load_settings(text)


def test_master_floor_equal_to_recent_turns_is_ok():
    settings = load_settings("[master]\nrecent_turns = 3\nrecent_turns_floor = 3\n")
    assert settings.app.master.recent_turns_floor == 3


def test_master_floor_zero_is_ok():
    assert load_settings("[master]\nrecent_turns_floor = 0\n").app.master.recent_turns_floor == 0


def test_master_context_cap_and_cpt_can_be_overridden():
    settings = load_settings("[master]\ncontext_cap = 12000\nchars_per_token = 3.0\n")
    assert settings.app.master.context_cap == 12000
    assert settings.app.master.chars_per_token == 3.0


# AD1: [persistence] durable

def test_persistence_durable_is_on_by_default():
    assert load_settings().app.persistence.durable is True


def test_persistence_durable_can_be_turned_off():
    settings = load_settings("[persistence]\ndurable = false\n")
    assert settings.app.persistence.durable is False


def test_persistence_unknown_key_is_rejected():
    with pytest.raises(ValidationError):
        load_settings("[persistence]\nbogus = 1\n")


def test_persistence_durable_must_be_bool():
    with pytest.raises(ValidationError):
        load_settings('[persistence]\ndurable = "maybe"\n')


# Б3: роль import и секция [import] (B3-PLAN A6)

def test_import_role_exists_in_default_roles_and_in_both_profiles():
    app = load_settings().app
    assert app.roles.import_.max_tokens == 32000
    assert app.profiles["gemini"].import_.max_tokens == 32000
    assert app.profiles["anthropic"].import_.model == SONNET
    assert app.profiles["anthropic"].import_.effort == "low"


def test_profile_without_import_role_is_valid_and_has_none():
    roles = "".join(
        f'\n[profiles.mixed.{name}]\nprovider = "gemini"\n'
        f'model = "{GEMINI_LITE}"\nmax_tokens = 100\n'
        for name in ("narrator", "world", "summarizer")
    )
    assert load_settings(roles).app.profiles["mixed"].import_ is None


def test_import_max_chars_default_is_60000():
    assert load_settings().app.import_.max_chars == 60000


def test_import_max_chars_can_be_overridden():
    assert load_settings("[import]\nmax_chars = 10\n").app.import_.max_chars == 10


def test_import_max_chars_zero_is_rejected():
    with pytest.raises(ValidationError):
        load_settings("[import]\nmax_chars = 0\n")


def test_unknown_key_in_import_section_is_rejected():
    with pytest.raises(ValidationError):
        load_settings("[import]\nbogus = 1\n")


def test_profile_import_model_without_price_is_rejected():
    text = '[profiles.anthropic.import]\nmodel = "claude-new-9"\n'
    text += "\n[context_windows]\nclaude-new-9 = 100000\n"
    with pytest.raises(ValidationError):
        load_settings(text)


def test_profile_import_model_without_context_window_is_rejected():
    text = '[profiles.anthropic.import]\nmodel = "claude-new-9"\n'
    text += "\n[prices.claude-new-9]\ninput = 1\noutput = 1\ncache_read = 1\n"
    text += "cache_write = 1\ncache_write_1h = 1\n"
    with pytest.raises(ValidationError):
        load_settings(text)


# Му-а (MU-PLAN A2): секция [audio]

def test_audio_defaults():
    audio = load_settings().app.audio
    assert audio.enabled is True
    assert audio.volume == 60
    assert audio.ambient is True
    assert audio.ambient_percent == 50
    assert audio.crossfade_s == 2.0
    assert audio.min_switch_s == 20


def test_audio_volume_can_be_overridden():
    assert load_settings("[audio]\nvolume = 30\n").app.audio.volume == 30


@pytest.mark.parametrize("value", [0, 100])
def test_audio_volume_bounds_are_accepted(value):
    assert load_settings(f"[audio]\nvolume = {value}\n").app.audio.volume == value


@pytest.mark.parametrize("line", ["volume = 101", "volume = -1", "ambient_percent = 101",
                                  "ambient_percent = -1", "crossfade_s = -0.5",
                                  "min_switch_s = -1"])
def test_audio_out_of_range_is_rejected(line):
    with pytest.raises(ValidationError):
        load_settings(f"[audio]\n{line}\n")


def test_audio_zero_crossfade_and_switch_are_accepted():
    audio = load_settings("[audio]\ncrossfade_s = 0\nmin_switch_s = 0\n").app.audio
    assert (audio.crossfade_s, audio.min_switch_s) == (0, 0)


def test_unknown_key_in_audio_section_is_rejected():
    with pytest.raises(ValidationError):
        load_settings("[audio]\nbogus = 1\n")
