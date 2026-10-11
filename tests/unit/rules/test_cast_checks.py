# Ожидаемый API: ai_dm.rules.cast_checks (точка расширения «проверки перед сотворением», B8)
#   CastCheckRegistry
#       register(source) -> None
#       check(caster, spell_id: str, registry) -> list   -- собранные результаты всех источников
#           в порядке регистрации (пустой реестр -> [])
#   CastCheckSource -- любой объект с атрибутом id: str и методом
#       check(caster, spell_id, registry) -> list   (по образцу ModifierSource; элементы списка --
#       на усмотрение источника, реестр их не разбирает)
#   default_cast_check_registry() -> CastCheckRegistry   -- новый ПУСТОЙ экземпляр (источники --
#       в партии 5); регистрация в одном экземпляре не влияет на другие
from ai_dm.rules.cast_checks import CastCheckRegistry, default_cast_check_registry
from ai_dm.state.creature import CreatureState


class FakeSource:
    id = "fake"

    def __init__(self, *results):
        self.results = list(results)
        self.seen = []

    def check(self, caster, spell_id, registry):
        self.seen.append((caster, spell_id, registry))
        return list(self.results)


def make_caster():
    return CreatureState(hp_current=7, hp_max=7)


def test_empty_registry_returns_empty_list(registry):
    assert CastCheckRegistry().check(make_caster(), "fireball", registry) == []


def test_default_registry_is_empty(registry):
    assert default_cast_check_registry().check(make_caster(), "fireball", registry) == []


def test_default_registry_returns_new_instance_each_time():
    assert default_cast_check_registry() is not default_cast_check_registry()


def test_registered_source_result_is_returned(registry):
    cast_checks = CastCheckRegistry()
    cast_checks.register(FakeSource("no_slots"))
    assert cast_checks.check(make_caster(), "fireball", registry) == ["no_slots"]


def test_source_gets_caster_spell_and_registry(registry):
    source = FakeSource()
    cast_checks = CastCheckRegistry()
    cast_checks.register(source)
    caster = make_caster()
    cast_checks.check(caster, "fireball", registry)
    assert source.seen == [(caster, "fireball", registry)]


def test_results_of_several_sources_are_joined_in_order(registry):
    cast_checks = CastCheckRegistry()
    cast_checks.register(FakeSource("a"))
    cast_checks.register(FakeSource("b", "c"))
    assert cast_checks.check(make_caster(), "fireball", registry) == ["a", "b", "c"]


def test_registration_in_default_registry_does_not_leak(registry):
    default_cast_check_registry().register(FakeSource("x"))
    assert default_cast_check_registry().check(make_caster(), "fireball", registry) == []
