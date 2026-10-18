# Ожидаемый API (STAGE3-PLAN A8, П6а, ТЗ 4.2): ai_dm.rules.divine
#   tier(favor: int) -> int  -- -3..3: favor // 3 к нулю (|favor| < 3 -> 0, 3..5 -> 1, 6..8 -> 2,
#     9..10 -> 3,
#       зеркально для отрицательных)
#   change_deity(hero, god_id) -> int -- hero.deity_id = god_id; новый бог без ключа в favor
#       получает 1 (возврат 1); бог с ключом (в т.ч. 0) не меняется (возврат 0);
#       прежний бог получает ключ favor (0, если не было), его значение не трогается
#   approx_label(favor: int) -> str -- «благосклонна» (>= 3) / «равнодушна» (-2..2) / «гневается»
#     (<= -3)
# Жрец (источник cast_checks): default_cast_check_registry().check(hero, spell_id, registry) -> list
#   hero.deity_id = бог, favor = hero.favor[бог]; пусто -- нет ограничений;
#   favor <= -3: заклинание 1+ круга даёт непустой результат (проверка МДР СЛ 10, ячейка потрачена
#     при провале);
#   favor <= -9: заклинание 1+ круга -- непустой результат (запрет); заговор (fire_bolt) -- пусто;
#   у героя без deity_id источник ничего не возвращает.
# Отдых: rests.long_rest при favor <= -6 не восстанавливает ячейки высшего доступного круга
#   (пул spell_slot:N с наибольшим max > 0), прочие ячейки восстанавливаются; при favor > -6 -- все.
import pytest

from ai_dm.core.clock import GameClock
from ai_dm.rules.cast_checks import default_cast_check_registry
from ai_dm.rules.rests import long_rest
from ai_dm.state.creature import CreatureState, ResourcePool
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState


def make_priest(favor=None, deity="selune"):
    sheet = CharacterSheet(
        species_id="human", classes=[ClassLevel(class_id="cleric")], level_history=["cleric"] * 1,
        background=BackgroundSpec(
            name="Служка", abilities=["str", "wis", "cha"], skills=["insight", "religion"],
            tool="dice_set", feat="savage_attacker",
        ),
        abilities={"str": 10, "dex": 10, "con": 14, "int": 10, "wis": 16, "cha": 12},
    )
    hero = HeroState(
        id="h1", ordinal=1, name="Брат Ано", sheet=sheet,
        creature=CreatureState(
            hp_current=5, hp_max=20,
            resources={
                "spell_slot:1": ResourcePool(current=0, max=4),
                "spell_slot:2": ResourcePool(current=0, max=2),
            },
        ),
        deity_id=deity,
    )
    if favor is not None:
        hero.favor = {deity: favor}
    return hero


def test_tier_zero_in_the_middle():
    from ai_dm.rules.divine import tier

    assert [tier(n) for n in (-2, -1, 0, 1, 2)] == [0, 0, 0, 0, 0]


@pytest.mark.parametrize(
    "favor, expected",
    [(3, 1), (5, 1), (6, 2), (8, 2), (9, 3), (10, 3),
     (-3, -1), (-5, -1), (-6, -2), (-8, -2), (-9, -3), (-10, -3)],
)
def test_tier_boundaries(favor, expected):
    from ai_dm.rules.divine import tier

    assert tier(favor) == expected


@pytest.mark.parametrize(
    "favor, label",
    [(3, "благосклонна"), (10, "благосклонна"), (2, "равнодушна"), (0, "равнодушна"),
     (-2, "равнодушна"), (-3, "гневается"), (-10, "гневается")],
)
def test_approx_label(favor, label):
    from ai_dm.rules.divine import approx_label

    assert approx_label(favor) == label


def test_change_deity_sets_new_god_with_plus_one():
    from ai_dm.rules.divine import change_deity

    hero = make_priest(favor=-4)
    change_deity(hero, "morrah")
    assert hero.deity_id == "morrah"
    assert hero.favor["morrah"] == 1


def test_change_deity_keeps_old_favor():
    from ai_dm.rules.divine import change_deity

    hero = make_priest(favor=-4)
    change_deity(hero, "morrah")
    assert hero.favor["selune"] == -4


def test_change_deity_returns_plus_one_for_new_god():
    from ai_dm.rules.divine import change_deity

    assert change_deity(make_priest(favor=-4), "morrah") == 1


def test_change_deity_back_to_known_god_returns_zero_and_keeps_favor():
    from ai_dm.rules.divine import change_deity

    hero = make_priest(favor=-4)
    hero.favor["morrah"] = 5
    assert change_deity(hero, "morrah") == 0
    assert hero.favor["morrah"] == 5
    assert hero.deity_id == "morrah"


def test_change_deity_to_god_with_zero_key_gives_no_bonus():
    from ai_dm.rules.divine import change_deity

    hero = make_priest(favor=-4)
    hero.favor["morrah"] = 0
    assert change_deity(hero, "morrah") == 0
    assert hero.favor["morrah"] == 0


def test_change_deity_old_god_without_key_gets_zero():
    from ai_dm.rules.divine import change_deity

    hero = make_priest()
    hero.favor.pop("selune", None)
    change_deity(hero, "morrah")
    assert hero.favor["selune"] == 0


def test_change_deity_round_trip_gives_plus_one_only_once():
    from ai_dm.rules.divine import change_deity

    hero = make_priest()
    hero.favor.pop("selune", None)
    change_deity(hero, "morrah")
    assert change_deity(hero, "selune") == 0
    assert hero.favor["selune"] == 0
    assert change_deity(hero, "morrah") == 0
    assert hero.favor["morrah"] == 1


def test_change_deity_from_no_god_adds_no_phantom_key():
    from ai_dm.rules.divine import change_deity

    hero = make_priest(deity=None)
    before = set(hero.favor)
    change_deity(hero, "morrah")
    assert set(hero.favor) == before | {"morrah"}


# жрец: проверки перед сотворением

@pytest.mark.parametrize("favor", [None, 0, 6, -2])
def test_priest_above_minus_three_casts_normally(registry, favor):
    hero = make_priest(favor)
    assert default_cast_check_registry().check(hero, "cure_wounds", registry) == []


@pytest.mark.parametrize("favor", [-3, -4, -6, -8])
def test_priest_at_minus_three_or_less_gets_wisdom_check(registry, favor):
    hero = make_priest(favor)
    assert default_cast_check_registry().check(hero, "cure_wounds", registry) != []


def test_priest_doubt_does_not_affect_cantrips(registry):
    hero = make_priest(-4)
    assert default_cast_check_registry().check(hero, "fire_bolt", registry) == []


def test_priest_excommunicated_cannot_cast_leveled_spell(registry):
    hero = make_priest(-9)
    assert default_cast_check_registry().check(hero, "cure_wounds", registry) != []


def test_priest_excommunicated_can_cast_cantrip(registry):
    hero = make_priest(-9)
    assert default_cast_check_registry().check(hero, "fire_bolt", registry) == []


def test_hero_without_deity_is_not_restricted(registry):
    hero = make_priest(None, deity=None)
    hero.favor = {"selune": -9}
    assert default_cast_check_registry().check(hero, "cure_wounds", registry) == []


# жрец: длинный отдых

def rest(hero, cfg, registry):
    long_rest(hero, registry, GameClock(), cfg)


def test_long_rest_restores_all_slots_without_estrangement(registry, cfg):
    hero = make_priest(-5)
    rest(hero, cfg, registry)
    pools = hero.creature.resources
    assert (pools["spell_slot:1"].current, pools["spell_slot:2"].current) == (4, 2)


def test_long_rest_at_minus_six_does_not_restore_highest_slots(registry, cfg):
    hero = make_priest(-6)
    rest(hero, cfg, registry)
    assert hero.creature.resources["spell_slot:2"].current == 0


def test_long_rest_at_minus_six_restores_lower_slots(registry, cfg):
    hero = make_priest(-6)
    rest(hero, cfg, registry)
    assert hero.creature.resources["spell_slot:1"].current == 4


def test_long_rest_at_minus_nine_does_not_restore_highest_slots(registry, cfg):
    hero = make_priest(-9)
    rest(hero, cfg, registry)
    assert hero.creature.resources["spell_slot:2"].current == 0


def test_long_rest_estrangement_ignored_for_hero_without_deity(registry, cfg):
    hero = make_priest(None, deity=None)
    hero.favor = {"selune": -6}
    rest(hero, cfg, registry)
    assert hero.creature.resources["spell_slot:2"].current == 2
