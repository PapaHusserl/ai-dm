# Ожидаемый API: ai_dm.rules.loot (этап 2, партия 1; ТЗ 2.3 «Добыча, золото»)
#   individual_treasure(cr: str, rng: Rng, registry) -> int
#       «Individual Treasure» SRD 5.2 для одного побеждённого: сумма в МЕДНЫХ (мм, как money_cp).
#       cr -- уровень опасности строкой, как в monster.cr: "0", "1/8", "1/4", "1/2", "1" ... "30".
#       Таблица -- srd/data/tables/individual_treasure.yaml (вид "table", id "individual_treasure");
#       числа таблицы сверяет кабан по SRD 5.2, здесь проверяются структура и свойства:
#         * результат -- int > 0; бросает только переданный rng (draws растёт), вся случайность
#           через него: один сид -- одна и та же последовательность;
#         * полосы по CR: 0-4, 5-10, 11-16, 17+ -- чем выше полоса, тем в среднем больше;
#           для полосы 0-4 потолок 10_000 мм (100 зм; в SRD максимум там 60 зм);
#         * CR, которого нет в таблице cr_xp (мусор, "99") -> ValueError до броска (rng не тронут).
#       Предметов и магии функция не выдаёт -- только деньги.
from types import SimpleNamespace

import pytest

from ai_dm.core.rng import Rng
from ai_dm.rules.loot import (
    hoard_band,
    hoard_treasure,
    individual_treasure,
    level_band,
    rarity_exceeds_cap,
    treasure_band,
)

BANDS = {
    "0-4": ["0", "1/8", "1/4", "1/2", "1", "2", "3", "4"],
    "5-10": ["5", "6", "7", "8", "9", "10"],
    "11-16": ["11", "12", "13", "14", "15", "16"],
    "17+": ["17", "18", "20", "25", "30"],
}
SAMPLES = 300


def samples(cr, registry, seed=1, n=SAMPLES):
    rng = Rng(seed)
    return [individual_treasure(cr, rng, registry) for _ in range(n)]


def mean(values):
    return sum(values) / len(values)


def test_table_exists_in_registry(registry):
    assert registry.has("table", "individual_treasure")
    assert registry.get("table", "individual_treasure").rows


@pytest.mark.parametrize("cr", [cr for crs in BANDS.values() for cr in crs])
def test_result_is_positive_int_for_every_cr(cr, registry):
    for value in samples(cr, registry, n=20):
        assert type(value) is int
        assert value > 0


def test_same_seed_gives_same_sequence(registry):
    assert samples("3", registry, seed=42) == samples("3", registry, seed=42)


def test_different_seeds_give_different_sequences(registry):
    assert samples("3", registry, seed=1) != samples("3", registry, seed=2)


def test_treasure_uses_only_given_rng(registry):
    rng = Rng(5)
    before = rng.draws
    individual_treasure("5", rng, registry)
    assert rng.draws > before


def test_continuing_rng_state_gives_next_result(registry):
    rng = Rng(9)
    first = individual_treasure("2", rng, registry)
    again = Rng(9)
    assert individual_treasure("2", again, registry) == first
    assert rng.state == again.state


def test_results_vary_within_a_band(registry):
    assert len(set(samples("2", registry))) > 5


def test_lowest_band_has_ceiling(registry):
    for cr in BANDS["0-4"]:
        assert max(samples(cr, registry, n=100)) <= 10_000


def test_bands_grow_on_average(registry):
    means = [mean(samples(crs[0], registry)) for crs in BANDS.values()]
    assert means == sorted(means)
    assert len(set(means)) == 4


def test_cr_inside_one_band_uses_same_scale(registry):
    low = mean(samples("5", registry))
    high = mean(samples("10", registry))
    assert 0.3 < low / high < 3


def test_top_band_exceeds_lowest_band_maximum(registry):
    assert min(samples("17", registry)) > 0
    assert max(samples("17", registry)) > max(samples("1", registry))


@pytest.mark.parametrize("cr", ["99", "abc", ""])
def test_unknown_cr_raises_value_error_and_keeps_rng(cr, registry):
    rng = Rng(3)
    with pytest.raises(ValueError):
        individual_treasure(cr, rng, registry)
    assert rng.draws == 0


# К0б: клад и редкость по уровням 1-20 (A8)



class MonstersByCr:
    # реестр-обёртка: монстры с заданным CR (в SRD-слое только CR до 1), таблицы - настоящие
    def __init__(self, registry, crs):
        self.registry = registry
        self.crs = crs

    def get(self, kind, item_id):
        if kind == "monster":
            return SimpleNamespace(cr=self.crs[item_id])
        return self.registry.get(kind, item_id)


class FixedDice(Rng):
    # каждая кость выпадает на одну грань: low -- на 1, иначе на максимум
    def __init__(self, high):
        super().__init__(1)
        self.high = high

    def randbelow(self, n):
        return n - 1 if self.high else 0


def hoard_rows(registry, band):
    rows = registry.get("table", "hoard").rows
    coins = [
        key.split(":")[1] for key in rows if key.startswith(f"{band}:") and key.endswith(":count")
    ]
    return [
        (rows[f"{band}:{coin}:count"], rows[f"{band}:{coin}:sides"], rows[f"{band}:{coin}:mult_cp"])
        for coin in coins
    ]


def hoard_min(registry, band):
    return sum(count * mult for count, _, mult in hoard_rows(registry, band))


def hoard_max(registry, band):
    return sum(count * sides * mult for count, sides, mult in hoard_rows(registry, band))


def hoard_mean(registry, band):
    return sum(count * (sides + 1) / 2 * mult for count, sides, mult in hoard_rows(registry, band))


@pytest.mark.parametrize(
    "level, band",
    [
        (1, "0-4"), (4, "0-4"), (5, "5-10"), (10, "5-10"),
        (11, "11-16"), (16, "11-16"), (17, "17+"), (20, "17+"),
    ],
)
def test_level_band_edges(level, band):
    assert level_band(level) == band


@pytest.mark.parametrize("level", [2, 3, 6, 7, 8, 9, 12, 13, 14, 15, 18, 19])
def test_level_band_matches_treasure_band_of_same_number(level):
    assert level_band(level) == treasure_band(str(level))


@pytest.mark.parametrize(
    "crs, band",
    [
        (["1/4"], "0-4"), (["1"], "0-4"), (["5"], "5-10"), (["10"], "5-10"),
        (["12"], "11-16"), (["16"], "11-16"), (["20"], "17+"), (["17"], "17+"),
        (["1/4", "12"], "11-16"), (["12", "1/4"], "11-16"), (["1", "5"], "5-10"),
        (["12", "20", "1"], "17+"), (["20", "12"], "17+"),
        (["5", "12"], "11-16"), (["12", "5"], "11-16"), (["5", "20"], "17+"), (["20", "10"], "17+"),
        (["10", "16"], "11-16"), (["1", "10"], "5-10"),
    ],
)
def test_hoard_band_is_the_highest_band_among_defeated(crs, band, registry):
    stub = MonstersByCr(registry, {f"m{i}": cr for i, cr in enumerate(crs)})
    assert hoard_band([f"m{i}" for i in range(len(crs))], stub) == band


@pytest.mark.parametrize("band", ["11-16", "17+"])
def test_hoard_table_has_the_new_bands(band, registry):
    assert hoard_rows(registry, band)


def test_hoard_table_stays_custom(registry):
    assert registry.get("table", "hoard").source == "custom"


def test_hoard_means_grow_with_band(registry):
    means = [hoard_mean(registry, b) for b in ("0-4", "5-10", "11-16", "17+")]
    assert means == sorted(means)
    assert len(set(means)) == 4


def test_hoard_mean_of_band_11_16_is_about_ten_thousand_gold(registry):
    # Q8: 2d6x20000 sp + 2d6x100000 gp + 1d6x100000 pp, мм; по плану около 10 640 зм
    assert 1_000_000 <= hoard_mean(registry, "11-16") <= 1_250_000


def test_hoard_mean_of_band_17_plus_is_about_fifty_thousand_gold(registry):
    # Q8: 2d6x300000 gp + 2d6x400000 pp, мм; по плану около 49 000 зм
    assert 4_500_000 <= hoard_mean(registry, "17+") <= 5_300_000


def test_hoard_means_of_old_bands_are_unchanged(registry):
    assert 9_000 <= hoard_mean(registry, "0-4") <= 11_000
    assert 95_000 <= hoard_mean(registry, "5-10") <= 108_000


@pytest.mark.parametrize(
    "level, band",
    [(1, "0-4"), (4, "0-4"), (5, "5-10"), (10, "5-10"), (11, "11-16"), (15, "11-16"),
     (16, "11-16"), (17, "17+"), (20, "17+")],
)
@pytest.mark.parametrize("high", [False, True])
def test_hoard_treasure_without_defeated_uses_level_band(level, band, high, registry):
    expected = hoard_max(registry, band) if high else hoard_min(registry, band)
    assert hoard_treasure([], FixedDice(high), registry, level) == expected


def test_hoard_treasure_level_15_is_inside_formula(registry):
    for seed in range(30):
        total = hoard_treasure([], Rng(seed), registry, 15)
        assert hoard_min(registry, "11-16") <= total <= hoard_max(registry, "11-16")


def test_hoard_treasure_level_15_rolls_five_dice(registry):
    rng = Rng(4)
    hoard_treasure([], rng, registry, 15)
    assert rng.draws == 5


def test_hoard_treasure_level_20_rolls_four_dice(registry):
    rng = Rng(4)
    hoard_treasure([], rng, registry, 20)
    assert rng.draws == 4


def test_hoard_treasure_defeated_cr_wins_over_level(registry):
    stub = MonstersByCr(registry, {"boss": "20"})
    assert hoard_treasure(["boss"], FixedDice(False), stub, 3) == hoard_min(registry, "17+")


def test_hoard_treasure_defeated_low_cr_wins_over_high_level(registry):
    assert hoard_treasure(["guard"], FixedDice(False), registry, 20) == hoard_min(registry, "0-4")


def test_hoard_treasure_without_level_and_defeated_uses_lowest_band(registry):
    assert hoard_treasure([], FixedDice(False), registry) == hoard_min(registry, "0-4")


def item_of(rarity, magic=True):
    return SimpleNamespace(magic=magic, rarity=rarity)


@pytest.mark.parametrize(
    "level, rarity, exceeds",
    [
        (1, "uncommon", False), (1, "rare", True), (4, "rare", True),
        (5, "rare", False), (6, "rare", False), (6, "very_rare", True), (10, "very_rare", True),
        (11, "very_rare", False), (16, "very_rare", False), (11, "legendary", True),
        (17, "legendary", False), (20, "legendary", False), (17, "artifact", True),
        (20, "artifact", True),
    ],
)
def test_rarity_cap_by_level_1_20(level, rarity, exceeds, cfg):
    assert rarity_exceeds_cap(item_of(rarity), level, cfg) is exceeds


@pytest.mark.parametrize("level", [1, 6, 11, 17, 20])
def test_non_magic_item_never_exceeds_cap(level, cfg):
    assert rarity_exceeds_cap(item_of("artifact", magic=False), level, cfg) is False


@pytest.mark.parametrize("level", [1, 12, 20])
def test_common_item_never_exceeds_cap(level, cfg):
    assert rarity_exceeds_cap(item_of("common"), level, cfg) is False
