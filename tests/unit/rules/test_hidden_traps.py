# Шаг 262, П2: расстановка и обнаружение скрытого (docs/plan-262.md, «Тесты» П2).
# Ожидаемый API (предположение доебы, вопрос к папе/кабану):
#   ai_dm.rules.hidden.is_hostile(world, location_id) -> bool
#       поле hostile у самой локации или у предка по parent_id (любая глубина).
#   ai_dm.rules.hidden.enter(ctx, location_id)
#       первый вход: у враждебной локации с hidden is None ставит Location.hidden (Hidden с level
#       героя, traps: PlacedTrap t1, t2...); traps локации (пак) -- ровно они, иначе бросок к6:
#       < cfg.traps.one_from -- ни одной, [one_from, two_from) -- одна, >= two_from -- две, ловушки
#       из реестра по уровню (levels). Пассивная Внимательность героя против detect.dc: не ниже СЛ
#       -- found, иначе hidden; Анализ -- всегда hidden. Повторный вход и невраждебная локация --
#       без изменений. Число ловушек -- броском rng.randbelow(6).
#   cfg.traps.one_from = 4, cfg.traps.two_from = 6 (раздел [traps] defaults.toml).
import pytest
from protocol_kit import make_ctx

from ai_dm.core.rng import Rng
from ai_dm.rules import hidden
from ai_dm.rules.derived import passive_perception
from ai_dm.state.world import Location


class D6Rng(Rng):
    # бросок к6 -- по сценарию (пустая очередь -- IndexError: бросать не должны), прочее --
    # настоящее
    def __init__(self, seed=1, d6=()):
        super().__init__(seed)
        self.d6 = list(d6)

    def randbelow(self, n):
        if n == 6:
            return self.d6.pop(0) - 1
        return super().randbelow(n)


def hostile_ctx(registry, cfg, rng=None, level=1, traps=(), wis=None):
    ctx = make_ctx(registry, cfg, rng)
    ctx.hero.sheet.primary.level = level
    if wis is not None:
        ctx.hero.sheet.abilities["wis"] = wis
    place = ctx.bundle.world.locations["forest"]
    place.hostile = True
    place.traps = list(traps)
    return ctx


def forest(ctx):
    return ctx.bundle.world.locations["forest"]


def trap_ids(ctx):
    return [t.trap_id for t in forest(ctx).hidden.traps]


def states(ctx):
    return {t.trap_id: t.state for t in forest(ctx).hidden.traps}


# is_hostile

def test_is_hostile_own_flag(registry, cfg):
    ctx = hostile_ctx(registry, cfg)
    assert hidden.is_hostile(ctx.bundle.world, "forest") is True


def test_is_not_hostile_by_default(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert hidden.is_hostile(ctx.bundle.world, "vale") is False


def test_is_hostile_inherited_from_parent(registry, cfg):
    ctx = hostile_ctx(registry, cfg)
    world = ctx.bundle.world
    world.locations["cave"] = Location(id="cave", name="Пещера", parent_id="forest")
    assert hidden.is_hostile(world, "cave") is True


def test_is_hostile_inherited_through_two_levels(registry, cfg):
    ctx = hostile_ctx(registry, cfg)
    world = ctx.bundle.world
    world.locations["cave"] = Location(id="cave", name="Пещера", parent_id="forest")
    world.locations["grotto"] = Location(id="grotto", name="Грот", parent_id="cave")
    assert hidden.is_hostile(world, "grotto") is True


def cycle_world(registry, cfg):
    world = make_ctx(registry, cfg).bundle.world
    world.locations["a"] = Location(id="a", name="А", parent_id="b")
    world.locations["b"] = Location(id="b", name="Б", parent_id="a")
    return world


def test_is_hostile_with_parent_cycle_is_false_and_returns(registry, cfg):
    # осторожно: без сторожа цикла вызов зависает
    world = cycle_world(registry, cfg)
    assert hidden.is_hostile(world, "a") is False


def test_is_hostile_with_parent_cycle_and_one_hostile_is_true(registry, cfg):
    world = cycle_world(registry, cfg)
    world.locations["b"].hostile = True
    assert hidden.is_hostile(world, "a") is True


def test_enter_places_in_child_of_hostile_location(registry, cfg):
    ctx = hostile_ctx(registry, cfg, D6Rng(d6=[5]))
    ctx.bundle.world.locations["cave"] = Location(id="cave", name="Пещера", parent_id="forest")
    hidden.enter(ctx, "cave")
    assert ctx.bundle.world.locations["cave"].hidden is not None


# расстановка

def test_first_entry_fills_hidden_with_registry_traps(registry, cfg):
    ctx = hostile_ctx(registry, cfg, D6Rng(d6=[5]), level=1)
    hidden.enter(ctx, "forest")
    assert forest(ctx).hidden.level == 1
    assert len(forest(ctx).hidden.traps) == 1
    assert forest(ctx).hidden.traps[0].id == "t1"
    assert registry.has("trap", trap_ids(ctx)[0])


def test_traps_fit_hero_level(registry, cfg):
    ctx = hostile_ctx(registry, cfg, D6Rng(d6=[6]), level=5)
    hidden.enter(ctx, "forest")
    for trap_id in trap_ids(ctx):
        low, high = registry.get("trap", trap_id).levels
        assert low <= 5 <= high


def test_same_seed_gives_same_traps(registry, cfg):
    first = hostile_ctx(registry, cfg, D6Rng(seed=3, d6=[6]))
    second = hostile_ctx(registry, cfg, D6Rng(seed=3, d6=[6]))
    hidden.enter(first, "forest")
    hidden.enter(second, "forest")
    assert trap_ids(first) == trap_ids(second)


@pytest.mark.parametrize("level", [1, 10])
def test_rolling_stone_never_below_level_11(registry, cfg, level):
    for seed in range(60):
        ctx = hostile_ctx(registry, cfg, D6Rng(seed=seed, d6=[6]), level=level)
        hidden.enter(ctx, "forest")
        assert "rolling_stone" not in trap_ids(ctx)


@pytest.mark.parametrize("level", [11, 17])
def test_rolling_stone_can_drop_from_level_11(registry, cfg, level):
    seen = set()
    for seed in range(80):
        ctx = hostile_ctx(registry, cfg, D6Rng(seed=seed, d6=[6]), level=level)
        hidden.enter(ctx, "forest")
        seen.update(trap_ids(ctx))
    assert "rolling_stone" in seen


def test_level_20_hero_gets_traps_from_table(registry, cfg):
    # верхняя граница levels включена: на 20-м уровне пул не пуст
    ctx = hostile_ctx(registry, cfg, D6Rng(d6=[6]), level=20)
    hidden.enter(ctx, "forest")
    assert len(forest(ctx).hidden.traps) == 2
    assert len(set(trap_ids(ctx))) == 2


def test_enter_returns_empty_for_repeat_peaceful_and_unnoticed(registry, cfg):
    ctx = hostile_ctx(registry, cfg, D6Rng(d6=[]), traps=["hidden_pit"], wis=1)
    assert hidden.enter(ctx, "forest") == ""
    assert hidden.enter(ctx, "forest") == ""
    peaceful = make_ctx(registry, cfg, D6Rng(d6=[]))
    assert hidden.enter(peaceful, "forest") == ""


def test_enter_signal_text_names_found_traps(registry, cfg):
    ctx = hostile_ctx(registry, cfg, D6Rng(d6=[]), traps=["falling_net", "fire_casting_statue"],
                      wis=30)
    names = [registry.get("trap", t).name for t in ("falling_net", "fire_casting_statue")]
    assert hidden.enter(ctx, "forest") == (
        f"Герой сразу заметил ловушки: {names[0]}, {names[1]}. Опиши, как он их заметил."
    )


@pytest.mark.parametrize("roll, count", [(1, 0), (2, 0), (3, 0), (4, 1), (5, 1), (6, 2)])
def test_trap_count_by_d6(registry, cfg, roll, count):
    ctx = hostile_ctx(registry, cfg, D6Rng(d6=[roll]))
    hidden.enter(ctx, "forest")
    assert len(forest(ctx).hidden.traps) == count


@pytest.mark.parametrize("roll, count", [(1, 0), (2, 1), (3, 2)])
def test_trap_count_thresholds_come_from_config(registry, cfg, roll, count):
    tuned = cfg.model_copy(deep=True)
    tuned.traps.one_from = 2
    tuned.traps.two_from = 3
    ctx = hostile_ctx(registry, tuned, D6Rng(d6=[roll]))
    hidden.enter(ctx, "forest")
    assert len(forest(ctx).hidden.traps) == count


def test_thresholds_one_from_above_two_from_is_config_error():
    from pydantic import ValidationError

    from ai_dm.config.settings import TrapsConfig

    with pytest.raises(ValidationError):
        TrapsConfig(one_from=6, two_from=4)


def test_thresholds_equal_load():
    # одной ловушки не бывает: меньше порога -- ни одной, от порога -- две
    from ai_dm.config.settings import TrapsConfig

    assert TrapsConfig(one_from=5, two_from=5).two_from == 5


def test_default_thresholds(cfg):
    assert (cfg.traps.one_from, cfg.traps.two_from) == (4, 6)


def test_pack_traps_stand_exactly_without_roll(registry, cfg):
    ctx = hostile_ctx(registry, cfg, D6Rng(d6=[]), traps=["falling_net", "spiked_pit"])
    hidden.enter(ctx, "forest")
    assert trap_ids(ctx) == ["falling_net", "spiked_pit"]
    assert [t.id for t in forest(ctx).hidden.traps] == ["t1", "t2"]


def test_repeat_entry_keeps_hidden(registry, cfg):
    ctx = hostile_ctx(registry, cfg, D6Rng(d6=[6]))
    hidden.enter(ctx, "forest")
    before = forest(ctx).hidden.model_dump()
    hidden.enter(ctx, "forest")
    assert forest(ctx).hidden.model_dump() == before


def test_repeat_entry_does_not_reroll(registry, cfg):
    ctx = hostile_ctx(registry, cfg, D6Rng(d6=[6]))
    hidden.enter(ctx, "forest")
    draws = ctx.rng.draws
    hidden.enter(ctx, "forest")
    assert ctx.rng.draws == draws


def test_not_hostile_location_stays_without_hidden(registry, cfg):
    ctx = make_ctx(registry, cfg, D6Rng(d6=[]))
    hidden.enter(ctx, "forest")
    assert forest(ctx).hidden is None


# обнаружение пассивной Внимательностью

@pytest.mark.parametrize("trap_id", ["fire_casting_statue", "poisoned_darts"])
@pytest.mark.parametrize("wis, state", [(14, "hidden"), (16, "found")])
def test_passive_perception_against_perception_dc_15(registry, cfg, trap_id, wis, state):
    ctx = hostile_ctx(registry, cfg, D6Rng(d6=[]), traps=[trap_id], wis=wis)
    assert passive_perception(ctx.hero, registry) == {14: 14, 16: 15}[wis]
    hidden.enter(ctx, "forest")
    assert states(ctx) == {trap_id: state}


def test_investigation_trap_stays_hidden_at_any_passive(registry, cfg):
    ctx = hostile_ctx(registry, cfg, D6Rng(d6=[]), traps=["hidden_pit"], wis=30)
    assert passive_perception(ctx.hero, registry) >= 20
    hidden.enter(ctx, "forest")
    assert states(ctx) == {"hidden_pit": "hidden"}
