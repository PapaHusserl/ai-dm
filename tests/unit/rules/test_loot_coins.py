# Партия К7д, п. 6 (Q2а): монеты за побеждённых (docs/K7D-PLAN.md).
#   loot.defeated_treasure не даёт монет за существ типа beast, construct и elemental
#   (NO_COIN_TYPES): они не бросают кости клада, RNG не тронут. Остальные (humanoid, fey, undead...)
#   дают как раньше. hoard_treasure не меняется.
import pytest

from ai_dm.content.models.monsters import Monster
from ai_dm.core.rng import Rng
from ai_dm.rules import loot
from ai_dm.rules.loot import defeated_treasure, hoard_treasure, individual_treasure


@pytest.fixture
def typed(registry):
    base = registry.get("monster", "goblin_warrior").model_dump()
    types = ["beast", "construct", "elemental", "undead", "fey", "humanoid"]
    items = [Monster.model_validate({**base, "id": t, "creature_type": t}) for t in types]
    return registry.with_items({"monster": items})


def test_no_coin_types_are_beast_construct_elemental():
    assert sorted(loot.NO_COIN_TYPES) == ["beast", "construct", "elemental"]


@pytest.mark.parametrize("kind", ["beast", "construct", "elemental"])
def test_no_coins_for_the_type(typed, kind):
    rng = Rng(5)
    assert defeated_treasure([kind], rng, typed) == 0
    assert rng.draws == 0


@pytest.mark.parametrize("kind", ["undead", "fey", "humanoid"])
def test_coins_for_other_types(typed, kind):
    got = defeated_treasure([kind], Rng(5), typed)
    assert got == individual_treasure("1/8", Rng(5), typed)
    assert got > 0


def test_beasts_do_not_shift_the_rng_for_the_others(typed):
    rng = Rng(7)
    mixed = defeated_treasure(["beast", "undead", "construct", "fey"], rng, typed)
    clean = Rng(7)
    assert mixed == defeated_treasure(["undead", "fey"], clean, typed)
    assert rng.draws == clean.draws


def test_empty_list_gives_nothing(typed):
    assert defeated_treasure([], Rng(1), typed) == 0


def test_hoard_treasure_still_counts_beasts(typed):
    rng = Rng(3)
    assert hoard_treasure(["beast"], rng, typed) > 0


def test_coins_of_several_monsters_are_summed(typed):
    rng = Rng(9)
    first = individual_treasure("1/8", rng, typed)
    second = individual_treasure("1/8", rng, typed)
    assert defeated_treasure(["undead", "fey"], Rng(9), typed) == first + second
