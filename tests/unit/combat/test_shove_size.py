# Партия К7д, п. 3 (BACKLOG 52): толчок не действует на цель больше чем на одну категорию крупнее.
#   shove.size_ok(engine, ref, target) -> bool: индекс размера цели <= индекс размера толкающего + 1
#     (SIZES: tiny small medium large huge gargantuan; размер героя -- по виду, монстра -- из
#     статблока);
#   available.shove_options: пункты shove:<цель>:<зона> только для подходящих по размеру целей
#     (и для именованных NPC тоже);
#   improvise.check_request: effect "push" по слишком большой цели -> Rejected("target_too_large")
#     ДО броска: действие не тратится, RNG не тронут, цель не двигается; по подходящей
#     цели -- бросок
#     как раньше; prone и другие эффекты размером не ограничены.
import pytest
from combat_kit import (
    ScriptedRng,
    custom_registry,
    make_engine,
    make_fighter,
    mon,
    part,
    turn,
)

from ai_dm.combat import shove
from ai_dm.rules.results import Rejected

SIZES = ["tiny", "small", "medium", "large", "huge", "gargantuan"]
CASES = [
    (own, other, SIZES.index(other) <= SIZES.index(own) + 1)
    for own in ("tiny", "small", "medium", "large")
    for other in SIZES
]


def sized(registry, cfg, own, other, named=False):
    # толкающий shover (fey, в hall) и цель victim стороны героев там же; герой -- на балконе
    reg = custom_registry(registry, shover={"size": own}, victim={"size": other})
    return make_engine(
        reg, cfg, heroes=[(make_fighter(registry), "balcony")], rng=ScriptedRng(),
        monsters=[
            mon("shover", "shover", "hall"),
            mon("victim", "victim", "hall", side="heroes", group="allies", named=named),
        ],
    )


def offered(engine):
    return [o.id for o in engine.available_actions("shover") if o.id.startswith("shove:victim")]


@pytest.mark.parametrize("own, other, allowed", CASES)
def test_size_ok_matrix(registry, cfg, own, other, allowed):
    engine = sized(registry, cfg, own, other)
    assert shove.size_ok(engine, "shover", "victim") is allowed


@pytest.mark.parametrize("own, other, allowed", CASES)
def test_shove_options_follow_the_size(registry, cfg, own, other, allowed):
    assert bool(offered(sized(registry, cfg, own, other))) is allowed


def test_named_npc_too_large_is_not_offered(registry, cfg):
    assert offered(sized(registry, cfg, "small", "huge", named=True)) == []


def test_named_npc_of_fitting_size_is_offered(registry, cfg):
    assert offered(sized(registry, cfg, "small", "medium", named=True)) != []


@pytest.mark.parametrize("own, allowed", [("tiny", False), ("small", True)])
def test_size_ok_uses_the_species_size_for_a_hero_target(registry, cfg, own, allowed):
    # герой-человек -- medium: толкающий small может, tiny -- нет
    reg = custom_registry(registry, shover={"size": own})
    engine = make_engine(
        reg, cfg, heroes=[make_fighter(registry)], rng=ScriptedRng(),
        monsters=[mon("shover", "shover", "hall")],
    )
    assert shove.size_ok(engine, "shover", "hero") is allowed


# импровизация героя

def push_engine(registry, cfg, size, rng=None):
    reg = custom_registry(registry, thing={"size": size})
    return make_engine(
        reg, cfg, heroes=[make_fighter(registry)], rng=rng or ScriptedRng(),
        monsters=[mon("thing_1", "thing", "hall")],
    )


def push(engine, effect="push", **kwargs):
    kwargs.setdefault("zone", "balcony")
    return engine.improvise(
        "hero", skill="athletics", category="medium", effect=effect, target="thing_1", **kwargs
    )


@pytest.mark.parametrize("size", ["huge", "gargantuan"])
def test_push_of_a_too_large_target_is_rejected(registry, cfg, size):
    result = push(push_engine(registry, cfg, size))
    assert (type(result), result.reason) == (Rejected, "target_too_large")


def test_rejected_push_keeps_the_action(registry, cfg):
    engine = push_engine(registry, cfg, "huge")
    push(engine)
    assert turn(engine, "hero").action is True


def test_rejected_push_makes_no_rolls(registry, cfg):
    rng = ScriptedRng(d20=[10])
    engine = push_engine(registry, cfg, "huge", rng)
    push(engine)
    assert rng.left("d20") == 1


def test_rejected_push_leaves_the_target_in_place(registry, cfg):
    engine = push_engine(registry, cfg, "huge")
    push(engine)
    assert part(engine, "thing_1").zone_id == "hall"


def test_push_of_a_large_target_rolls_as_before(registry, cfg):
    engine = push_engine(registry, cfg, "large", ScriptedRng(d20=[10]))
    push(engine)
    assert (turn(engine, "hero").action, part(engine, "thing_1").zone_id) == (False, "balcony")


def test_push_of_a_small_target_works(registry, cfg):
    engine = push_engine(registry, cfg, "tiny", ScriptedRng(d20=[10]))
    push(engine)
    assert part(engine, "thing_1").zone_id == "balcony"


def test_prone_of_a_huge_target_is_still_allowed(registry, cfg):
    engine = push_engine(registry, cfg, "huge", ScriptedRng(d20=[10]))
    result = push(engine, "prone", zone=None)
    assert not isinstance(result, Rejected)
    assert turn(engine, "hero").action is False


def test_a_too_large_first_target_does_not_hide_the_next(registry, cfg):
    reg = custom_registry(registry, shover={"size": "small"}, big={"size": "huge"}, fit={})
    engine = make_engine(
        reg, cfg, heroes=[(make_fighter(registry), "balcony")], rng=ScriptedRng(),
        monsters=[
            mon("shover", "shover", "hall"),
            mon("big", "big", "hall", side="heroes", group="allies"),
            mon("fit", "fit", "hall", side="heroes", group="allies"),
        ],
    )
    ids = [o.id for o in engine.available_actions("shover") if o.kind == "shove"]
    assert ids and all(i.startswith("shove:fit:") for i in ids)
