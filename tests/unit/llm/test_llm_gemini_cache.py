# Явный кэш Gemini (docs/decisions/stage2-live-1.md, X1/X2/X4). Ожидаемый API (выбран здесь --
# ТРЕБОВАНИЕ к реализации, сверить с кабаном):
#   client.caches.create(model=<модель>, config=sdk.CreateCachedContentConfig(system_instruction=,
#     tools=, ttl="3600s" для cache_ttl 1h / "300s" для 5m)) -> объект с .name и
#     .usage_metadata.total_token_count
#   дальше generate_content(config=GenerateContentConfig(cached_content=<name>, ...)) БЕЗ
#   system_instruction и tools в config
#   создание -- один раз на (модель, system, tools); ответ на создании: usage.cache_write = число
#   токенов кэша; кэш истёк (ошибка с code 404) -> создать заново один раз и повторить запрос;
#   ошибка создания -> запрос без кэша (system_instruction и tools в config, как раньше)
from types import SimpleNamespace

import pytest
from llm_kit import app_cfg, make_request
from test_llm_gemini_adapter import (
    FAKE_SDK,
    MODEL,
    ApiError,
    FakeModels,
    api_response,
    meta,
    part,
    tools_req,
)

from ai_dm.llm.cost import cost_nano
from ai_dm.llm.errors import LlmError
from ai_dm.llm.gemini_adapter import GeminiAdapter
from ai_dm.llm.types import SystemBlock, Usage

SDK = FAKE_SDK


class FakeCaches:
    def __init__(self, tokens=5000, fail=None):
        self.calls = []
        self.tokens = tokens
        self.fail = fail

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail is not None:
            raise self.fail
        name = f"cachedContents/c{len(self.calls)}"
        usage = SimpleNamespace(total_token_count=self.tokens)
        return SimpleNamespace(name=name, usage_metadata=usage)


def make_cached(results=None, caches=None, ttl=None):
    ok = [api_response([part(text="ок")]) for _ in range(6)]
    models = FakeModels(results if results is not None else ok)
    caches = caches or FakeCaches()
    client = SimpleNamespace(models=models, caches=caches)
    cfg = app_cfg()
    if ttl:
        cfg.llm.cache_ttl = ttl
    return GeminiAdapter(MODEL, cfg, client=client, sdk=SDK), models, caches


def test_cache_is_created_with_system_and_tools():
    adapter, models, caches = make_cached()
    adapter.complete(tools_req())
    config = caches.calls[0]["config"]
    assert caches.calls[0]["model"] == MODEL
    assert config.system_instruction == "правила мастера"
    assert len(config.tools[0].function_declarations) > 0


def test_cache_ttl_follows_config():
    adapter, models, caches = make_cached(ttl="1h")
    adapter.complete(tools_req())
    assert caches.calls[0]["config"].ttl == "3600s"


def test_cache_ttl_5m():
    adapter, models, caches = make_cached(ttl="5m")
    adapter.complete(tools_req())
    assert caches.calls[0]["config"].ttl == "300s"


def test_request_uses_cached_content_name():
    adapter, models, caches = make_cached()
    adapter.complete(tools_req())
    assert models.calls[0]["config"].cached_content == "cachedContents/c1"


def test_request_with_cache_has_no_system_instruction():
    adapter, models, caches = make_cached()
    adapter.complete(tools_req())
    assert not hasattr(models.calls[0]["config"], "system_instruction")


def test_request_with_cache_has_no_tools():
    adapter, models, caches = make_cached()
    adapter.complete(tools_req())
    assert not hasattr(models.calls[0]["config"], "tools")


def test_cache_is_created_once_for_same_system_and_tools():
    adapter, models, caches = make_cached()
    adapter.complete(tools_req())
    adapter.complete(tools_req(text="другой ход"))
    assert len(caches.calls) == 1


def test_second_request_reuses_cache_name():
    adapter, models, caches = make_cached()
    adapter.complete(tools_req())
    adapter.complete(tools_req(text="другой ход"))
    assert models.calls[1]["config"].cached_content == "cachedContents/c1"


def test_other_tool_set_makes_own_cache():
    adapter, models, caches = make_cached()
    adapter.complete(tools_req("explore"))
    adapter.complete(tools_req("combat_classify"))
    assert len(caches.calls) == 2


def test_other_tool_set_uses_its_own_name():
    adapter, models, caches = make_cached()
    adapter.complete(tools_req("explore"))
    adapter.complete(tools_req("combat_classify"))
    assert models.calls[1]["config"].cached_content == "cachedContents/c2"


def test_returning_to_first_tool_set_reuses_first_cache():
    adapter, models, caches = make_cached()
    adapter.complete(tools_req("explore"))
    adapter.complete(tools_req("combat_classify"))
    adapter.complete(tools_req("explore"))
    assert len(caches.calls) == 2
    assert models.calls[2]["config"].cached_content == "cachedContents/c1"


def test_other_system_makes_own_cache():
    adapter, models, caches = make_cached()
    adapter.complete(tools_req())
    adapter.complete(tools_req(system=[SystemBlock(text="другие правила", cache=True)]))
    assert len(caches.calls) == 2


def test_other_model_makes_own_cache():
    adapter, models, caches = make_cached()
    adapter.complete(tools_req())
    adapter.complete(tools_req(model="gemini-3.8-pro"))
    assert len(caches.calls) == 2


def test_expired_cache_is_recreated_and_request_repeated():
    ok = api_response([part(text="ок")])
    adapter, models, caches = make_cached([ok, ApiError(404), ok])
    adapter.complete(tools_req())
    adapter.complete(tools_req())
    assert len(caches.calls) == 2
    assert len(models.calls) == 3
    assert models.calls[2]["config"].cached_content == "cachedContents/c2"


def test_expired_cache_is_recreated_only_once():
    adapter, models, caches = make_cached([ApiError(404), ApiError(404)])
    with pytest.raises(LlmError):
        adapter.complete(tools_req())
    assert len(caches.calls) == 2
    assert len(models.calls) == 2


def test_failed_cache_creation_falls_back_to_plain_request():
    adapter, models, caches = make_cached(caches=FakeCaches(fail=ApiError(400, "мало токенов")))
    response = adapter.complete(tools_req())
    config = models.calls[0]["config"]
    assert config.system_instruction == "правила мастера"
    assert len(config.tools) == 1
    assert not hasattr(config, "cached_content")
    assert response.content[0].text == "ок"


def test_creation_failure_with_network_error_falls_back_too():
    adapter, models, caches = make_cached(caches=FakeCaches(fail=ApiError(503)))
    adapter.complete(tools_req())
    assert not hasattr(models.calls[0]["config"], "cached_content")


def test_request_without_system_and_tools_makes_no_cache():
    adapter, models, caches = make_cached()
    adapter.complete(make_request(model=MODEL, system=[]))
    assert caches.calls == []


def test_cache_creation_tokens_go_to_cache_write():
    usage = meta(prompt=5200, candidates=10, cached=5000)
    adapter, models, caches = make_cached([api_response([part(text="ок")], usage=usage)])
    response = adapter.complete(tools_req())
    assert response.usage.cache_write == 5000


def test_cached_tokens_go_to_cache_read():
    usage = meta(prompt=5200, candidates=10, cached=5000)
    adapter, models, caches = make_cached([api_response([part(text="ок")], usage=usage)])
    response = adapter.complete(tools_req())
    assert response.usage.cache_read == 5000
    assert response.usage.input == 200


def test_cache_write_is_charged_once():
    usage = meta(prompt=5200, candidates=10, cached=5000)
    results = [api_response([part(text="ок")], usage=usage) for _ in range(2)]
    adapter, models, caches = make_cached(results)
    adapter.complete(tools_req())
    second = adapter.complete(tools_req())
    assert second.usage.cache_write == 0
    assert second.usage.cache_read == 5000


def test_no_cache_write_when_creation_failed():
    adapter, models, caches = make_cached(caches=FakeCaches(fail=ApiError(400)))
    response = adapter.complete(tools_req())
    assert response.usage.cache_write == 0


# X2: хранение -- токены × минуты TTL в usage.cache_storage_min

def test_storage_minutes_for_1h_ttl():
    adapter, models, caches = make_cached(ttl="1h")
    response = adapter.complete(tools_req())
    assert response.usage.cache_storage_min == 5000 * 60


def test_storage_minutes_for_5m_ttl():
    adapter, models, caches = make_cached(ttl="5m")
    response = adapter.complete(tools_req())
    assert response.usage.cache_storage_min == 5000 * 5


def test_storage_is_charged_once():
    adapter, models, caches = make_cached()
    adapter.complete(tools_req())
    second = adapter.complete(tools_req())
    assert second.usage.cache_storage_min == 0


def test_each_new_cache_charges_its_storage():
    adapter, models, caches = make_cached()
    adapter.complete(tools_req("explore"))
    second = adapter.complete(tools_req("combat_classify"))
    assert second.usage.cache_storage_min == 5000 * 60
    assert second.usage.cache_write == 5000


def test_storage_survives_failed_request_after_creation():
    ok = api_response([part(text="ок")])
    adapter, models, caches = make_cached([ApiError(503), ok])
    with pytest.raises(LlmError):
        adapter.complete(tools_req())
    response = adapter.complete(tools_req())
    assert len(caches.calls) == 1
    assert response.usage.cache_storage_min == 5000 * 60
    assert response.usage.cache_write == 5000


def test_recreated_cache_adds_second_storage():
    ok = api_response([part(text="ок")])
    adapter, models, caches = make_cached([ok, ApiError(404), ok])
    adapter.complete(tools_req())
    response = adapter.complete(tools_req())
    assert response.usage.cache_storage_min == 5000 * 60
    assert response.usage.cache_write == 5000


def test_no_storage_when_creation_failed():
    adapter, models, caches = make_cached(caches=FakeCaches(fail=ApiError(400)))
    response = adapter.complete(tools_req())
    assert response.usage.cache_storage_min == 0


def test_storage_price_is_per_token_hour():
    price = app_cfg().prices[MODEL]
    usage = Usage(cache_storage_min=1_000_000 * 60)
    assert cost_nano(usage, price) == price.cache_storage_hour * 1000


def test_half_hour_storage_costs_half():
    price = app_cfg().prices[MODEL]
    usage = Usage(cache_storage_min=1_000_000 * 30)
    assert cost_nano(usage, price) == price.cache_storage_hour * 500


# этап 4, P1+ (E1): блок памяти (system[2]) внутри явного кэша; смена памяти -- новый кэш
def memory_req(memory="память: глава I", **kw):
    system = [
        SystemBlock(text="правила мастера", cache=True),
        SystemBlock(text="мир", cache=True),
        SystemBlock(text=memory, cache=True, stable=False),
    ]
    return tools_req(system=system, **kw)


def test_cache_key_changes_with_memory():
    adapter, models, caches = make_cached()
    assert adapter.cache_key(memory_req("одна")) != adapter.cache_key(memory_req("другая"))


def test_cache_key_is_same_for_same_memory():
    adapter, models, caches = make_cached()
    assert adapter.cache_key(memory_req("одна")) == adapter.cache_key(memory_req("одна"))


def test_cache_system_instruction_has_memory():
    adapter, models, caches = make_cached()
    adapter.complete(memory_req("память: глава I"))
    assert "память: глава I" in caches.calls[0]["config"].system_instruction


def test_cache_system_instruction_still_has_rules_and_world():
    adapter, models, caches = make_cached()
    adapter.complete(memory_req())
    text = caches.calls[0]["config"].system_instruction
    assert "правила мастера" in text
    assert "мир" in text


def test_memory_change_creates_new_cache():
    adapter, models, caches = make_cached()
    adapter.complete(memory_req("одна"))
    adapter.complete(memory_req("другая"))
    assert len(caches.calls) == 2


def test_request_after_memory_change_uses_new_cache_name():
    adapter, models, caches = make_cached()
    adapter.complete(memory_req("одна"))
    adapter.complete(memory_req("другая"))
    assert models.calls[1]["config"].cached_content == "cachedContents/c2"


def test_same_memory_does_not_create_new_cache():
    adapter, models, caches = make_cached()
    adapter.complete(memory_req("одна", text="ход 1"))
    adapter.complete(memory_req("одна", text="ход 2"))
    assert len(caches.calls) == 1


def test_same_memory_reuses_cache_name():
    adapter, models, caches = make_cached()
    adapter.complete(memory_req("одна", text="ход 1"))
    adapter.complete(memory_req("одна", text="ход 2"))
    assert models.calls[1]["config"].cached_content == "cachedContents/c1"


def test_memory_is_not_in_contents():
    adapter, models, caches = make_cached()
    adapter.complete(memory_req("память: глава I", text="ход игрока"))
    parts = models.calls[0]["contents"][0].parts
    assert [p.text for p in parts] == ["ход игрока"]


def test_memory_is_not_in_config_of_request_with_cache():
    adapter, models, caches = make_cached()
    adapter.complete(memory_req())
    assert not hasattr(models.calls[0]["config"], "system_instruction")


def test_memory_goes_to_system_instruction_when_cache_failed():
    adapter, models, caches = make_cached(caches=FakeCaches(fail=ApiError(400, "мало токенов")))
    adapter.complete(memory_req("память: глава I"))
    assert "память: глава I" in models.calls[0]["config"].system_instruction


# этап 4, P1+ (E3): роль world -- без явного кэша по умолчанию; флаг конфига
# llm.gemini_cache_world (bool, по умолчанию False) включает
def world_req():
    return tools_req("world", role="world")


def test_world_role_does_not_create_cache_by_default():
    adapter, models, caches = make_cached()
    adapter.complete(world_req())
    assert caches.calls == []


def test_world_role_sends_system_instruction_and_tools_without_cache():
    adapter, models, caches = make_cached()
    adapter.complete(world_req())
    config = models.calls[0]["config"]
    assert config.system_instruction == "правила мастера"
    assert len(config.tools[0].function_declarations) > 0
    assert not hasattr(config, "cached_content")


def test_world_role_creates_cache_when_flag_is_on():
    adapter, models, caches = make_cached()
    adapter.cfg.llm.gemini_cache_world = True
    adapter.complete(world_req())
    assert len(caches.calls) == 1
    assert models.calls[0]["config"].cached_content == "cachedContents/c1"


def test_narrator_role_still_creates_cache_by_default():
    adapter, models, caches = make_cached()
    adapter.complete(tools_req())
    assert len(caches.calls) == 1


def test_summarizer_role_still_creates_cache_by_default():
    adapter, models, caches = make_cached()
    adapter.complete(tools_req("summarize_scene", role="summarizer"))
    assert len(caches.calls) == 1


def test_gemini_cache_world_is_off_in_default_config():
    assert app_cfg().llm.gemini_cache_world is False


# этап 4, P1+ (E1): старый кэш той же (model, tools, role) удаляется через
# client.caches.delete(name=<старое имя>) при смене памяти; ошибка delete игнорируется
class DeleteCaches(FakeCaches):
    def __init__(self, delete_fail=None, **kw):
        super().__init__(**kw)
        self.deleted = []
        self.delete_fail = delete_fail

    def delete(self, **kwargs):
        self.deleted.append(kwargs.get("name"))
        if self.delete_fail is not None:
            raise self.delete_fail


def test_memory_change_deletes_old_cache():
    adapter, models, caches = make_cached(caches=DeleteCaches())
    adapter.complete(memory_req("одна"))
    adapter.complete(memory_req("другая"))
    assert caches.deleted == ["cachedContents/c1"]


def test_same_memory_does_not_delete_cache():
    adapter, models, caches = make_cached(caches=DeleteCaches())
    adapter.complete(memory_req("одна", text="ход 1"))
    adapter.complete(memory_req("одна", text="ход 2"))
    assert caches.deleted == []


def test_cache_of_other_role_is_not_deleted():
    adapter, models, caches = make_cached(caches=DeleteCaches())
    adapter.complete(memory_req("одна", role="narrator"))
    adapter.complete(memory_req("другая", role="summarizer"))
    assert caches.deleted == []


def test_delete_error_does_not_fail_request():
    adapter, models, caches = make_cached(caches=DeleteCaches(delete_fail=ApiError(404)))
    adapter.complete(memory_req("одна"))
    result = adapter.complete(memory_req("другая"))
    assert result.content[0].text == "ок"
    assert models.calls[1]["config"].cached_content == "cachedContents/c2"
