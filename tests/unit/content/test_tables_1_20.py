# Таблицы SRD 5.2 на уровни 1-20 (К0б, K0-PLAN A8). Опорные значения и инварианты;
# уровни 1-5 старых таблиц проверяет test_srd_minimum.py.
# Ключи: spell_slots_*: "уровень:круг" -> ячейки; pact_slots: "уровень:count" и "уровень:circle";
# encounter_budget: "уровень:low|moderate|high"; damage_severity: "полоса:тяжесть:count|sides";
# hoard: "полоса:монета:count|sides|mult_cp".
import pytest

LEVELS = range(1, 21)
FULL = {
    6: [4, 3, 3], 7: [4, 3, 3, 1], 8: [4, 3, 3, 2], 9: [4, 3, 3, 3, 1], 10: [4, 3, 3, 3, 2],
    11: [4, 3, 3, 3, 2, 1], 12: [4, 3, 3, 3, 2, 1], 13: [4, 3, 3, 3, 2, 1, 1],
    14: [4, 3, 3, 3, 2, 1, 1], 15: [4, 3, 3, 3, 2, 1, 1, 1], 16: [4, 3, 3, 3, 2, 1, 1, 1],
    17: [4, 3, 3, 3, 2, 1, 1, 1, 1], 18: [4, 3, 3, 3, 3, 1, 1, 1, 1],
    19: [4, 3, 3, 3, 3, 2, 1, 1, 1], 20: [4, 3, 3, 3, 3, 2, 2, 1, 1],
}
HALF = {
    6: [4, 2], 7: [4, 3], 8: [4, 3], 9: [4, 3, 2], 10: [4, 3, 2], 11: [4, 3, 3], 12: [4, 3, 3],
    13: [4, 3, 3, 1], 14: [4, 3, 3, 1], 15: [4, 3, 3, 2], 16: [4, 3, 3, 2],
    17: [4, 3, 3, 3, 1], 18: [4, 3, 3, 3, 1], 19: [4, 3, 3, 3, 2], 20: [4, 3, 3, 3, 2],
}
PACT = {
    1: (1, 1), 2: (2, 1), 3: (2, 2), 4: (2, 2), 5: (2, 3), 6: (2, 3), 7: (2, 4), 8: (2, 4),
    9: (2, 5), 10: (2, 5), 11: (3, 5), 12: (3, 5), 13: (3, 5), 14: (3, 5), 15: (3, 5),
    16: (3, 5), 17: (4, 5), 18: (4, 5), 19: (4, 5), 20: (4, 5),
}
BUDGET = {
    6: (600, 1000, 1400), 7: (750, 1300, 1700), 8: (1000, 1700, 2100), 9: (1300, 2000, 2600),
    10: (1600, 2300, 3100), 11: (1900, 2900, 4100), 12: (2200, 3700, 4700),
    13: (2600, 4200, 5400), 14: (2900, 4900, 6200), 15: (3300, 5400, 7800),
    16: (3800, 6100, 9800), 17: (4500, 7200, 11700), 18: (5000, 8700, 14200),
    19: (5500, 10700, 17000), 20: (6400, 13200, 22000),
}
SEVERITY = {
    "1-4": (1, 2, 4), "5-10": (2, 4, 10), "11-16": (4, 10, 18), "17-20": (10, 18, 24),
}
TIERS = ("low", "moderate", "high")
KINDS = ("nuisance", "dangerous", "deadly")


def slots_at(registry, table_id, level):
    rows = registry.get("table", table_id).rows
    found = {}
    for key, count in rows.items():
        row_level, circle = key.split(":")
        if int(row_level) == level:
            found[int(circle)] = count
    return [found[circle] for circle in sorted(found)]


def rows_of(registry, table_id):
    return registry.get("table", table_id).rows


# ячейки полных заклинателей

@pytest.mark.parametrize("level", sorted(FULL))
def test_spell_slots_full_levels_6_to_20(level, registry):
    assert slots_at(registry, "spell_slots_full", level) == FULL[level]


@pytest.mark.parametrize("level", LEVELS)
def test_spell_slots_full_has_every_level(level, registry):
    assert slots_at(registry, "spell_slots_full", level)


def test_spell_slots_full_has_no_levels_above_20(registry):
    levels = {int(key.split(":")[0]) for key in rows_of(registry, "spell_slots_full")}
    assert levels == set(LEVELS)


@pytest.mark.parametrize("level", LEVELS)
def test_spell_slots_full_circles_are_continuous_from_1(level, registry):
    rows = rows_of(registry, "spell_slots_full")
    circles = sorted(int(k.split(":")[1]) for k in rows if k.startswith(f"{level}:"))
    assert circles == list(range(1, len(circles) + 1))


def test_spell_slots_full_counts_are_at_most_4(registry):
    assert max(rows_of(registry, "spell_slots_full").values()) == 4


def test_spell_slots_full_circles_are_at_most_9(registry):
    circles = {int(k.split(":")[1]) for k in rows_of(registry, "spell_slots_full")}
    assert max(circles) == 9


@pytest.mark.parametrize("circle", range(1, 10))
def test_spell_slots_full_per_circle_never_decrease_with_level(circle, registry):
    rows = rows_of(registry, "spell_slots_full")
    values = [rows.get(f"{level}:{circle}", 0) for level in LEVELS]
    assert values == sorted(values)


@pytest.mark.parametrize("key, count", [
    ("17:9", 1), ("18:5", 3), ("20:7", 2), ("20:6", 2), ("13:7", 1),
])
def test_spell_slots_full_anchor_values(key, count, registry):
    assert rows_of(registry, "spell_slots_full")[key] == count


def test_spell_slots_full_level_6_has_no_4th_circle(registry):
    assert "6:4" not in rows_of(registry, "spell_slots_full")


# ячейки получастичных заклинателей

@pytest.mark.parametrize("level", sorted(HALF))
def test_spell_slots_half_levels_6_to_20(level, registry):
    assert slots_at(registry, "spell_slots_half", level) == HALF[level]


@pytest.mark.parametrize("level", LEVELS)
def test_spell_slots_half_has_every_level(level, registry):
    assert slots_at(registry, "spell_slots_half", level)


def test_spell_slots_half_circles_are_at_most_5(registry):
    circles = {int(k.split(":")[1]) for k in rows_of(registry, "spell_slots_half")}
    assert max(circles) == 5


@pytest.mark.parametrize("circle", range(1, 6))
def test_spell_slots_half_per_circle_never_decrease_with_level(circle, registry):
    rows = rows_of(registry, "spell_slots_half")
    values = [rows.get(f"{level}:{circle}", 0) for level in LEVELS]
    assert values == sorted(values)


@pytest.mark.parametrize("key, count", [
    ("5:2", 2), ("9:3", 2), ("13:4", 1), ("17:5", 1), ("20:5", 2),
])
def test_spell_slots_half_anchor_values(key, count, registry):
    assert rows_of(registry, "spell_slots_half")[key] == count


def test_spell_slots_half_level_19_has_no_6th_circle(registry):
    assert "19:6" not in rows_of(registry, "spell_slots_half")


def test_there_is_no_third_caster_table(registry):
    assert not registry.has("table", "spell_slots_third")


# ячейки договора

def test_pact_slots_table_is_srd(registry):
    table = registry.get("table", "pact_slots")
    assert table.source == "srd-5.2"


@pytest.mark.parametrize("level", LEVELS)
def test_pact_slots_every_level(level, registry):
    rows = rows_of(registry, "pact_slots")
    assert (rows[f"{level}:count"], rows[f"{level}:circle"]) == PACT[level]


def test_pact_slots_has_only_count_and_circle_keys_for_20_levels(registry):
    assert len(rows_of(registry, "pact_slots")) == 40


@pytest.mark.parametrize("level, count", [(1, 1), (2, 2), (11, 3), (17, 4)])
def test_pact_slots_count_anchors(level, count, registry):
    assert rows_of(registry, "pact_slots")[f"{level}:count"] == count


@pytest.mark.parametrize("level, circle", [(1, 1), (3, 2), (5, 3), (7, 4), (9, 5), (20, 5)])
def test_pact_slots_circle_anchors(level, circle, registry):
    assert rows_of(registry, "pact_slots")[f"{level}:circle"] == circle


def test_pact_slots_never_decrease(registry):
    rows = rows_of(registry, "pact_slots")
    for field in ("count", "circle"):
        values = [rows[f"{level}:{field}"] for level in LEVELS]
        assert values == sorted(values)


# бюджет боя

def test_encounter_budget_has_60_keys(registry):
    assert len(rows_of(registry, "encounter_budget")) == 60


@pytest.mark.parametrize("level", LEVELS)
def test_encounter_budget_tiers_grow_inside_level(level, registry):
    rows = rows_of(registry, "encounter_budget")
    low, moderate, high = (rows[f"{level}:{tier}"] for tier in TIERS)
    assert low < moderate < high


@pytest.mark.parametrize("tier", TIERS)
def test_encounter_budget_does_not_decrease_with_level(tier, registry):
    rows = rows_of(registry, "encounter_budget")
    values = [rows[f"{level}:{tier}"] for level in LEVELS]
    assert values == sorted(values)


@pytest.mark.parametrize("level", sorted(BUDGET))
def test_encounter_budget_levels_6_to_20(level, registry):
    rows = rows_of(registry, "encounter_budget")
    assert tuple(rows[f"{level}:{tier}"] for tier in TIERS) == BUDGET[level]


@pytest.mark.parametrize("level, tier, value", [
    (1, "low", 50), (1, "moderate", 75), (20, "moderate", 13200), (11, "high", 4100),
])
def test_encounter_budget_anchor_values(level, tier, value, registry):
    assert rows_of(registry, "encounter_budget")[f"{level}:{tier}"] == value


# урон по тяжести

def test_damage_severity_is_srd(registry):
    assert registry.get("table", "damage_severity").source == "srd-5.2"


def test_damage_severity_is_4_bands_by_3_severities_by_2_fields(registry):
    assert len(rows_of(registry, "damage_severity")) == 24


@pytest.mark.parametrize("band", sorted(SEVERITY))
@pytest.mark.parametrize("number, kind", list(enumerate(KINDS)))
def test_damage_severity_dice(band, number, kind, registry):
    rows = rows_of(registry, "damage_severity")
    assert rows[f"{band}:{kind}:count"] == SEVERITY[band][number]
    assert rows[f"{band}:{kind}:sides"] == 10


def test_damage_severity_deadly_anchors(registry):
    rows = rows_of(registry, "damage_severity")
    assert (rows["17-20:deadly:count"], rows["17-20:deadly:sides"]) == (24, 10)
    assert (rows["5-10:deadly:count"], rows["5-10:deadly:sides"]) == (10, 10)


@pytest.mark.parametrize("band", sorted(SEVERITY))
def test_damage_severity_grows_inside_band(band, registry):
    rows = rows_of(registry, "damage_severity")
    counts = [rows[f"{band}:{kind}:count"] for kind in KINDS]
    assert counts == sorted(counts)
    assert len(set(counts)) == 3


# клад

def test_hoard_has_bands_11_16_and_17_plus(registry):
    keys = rows_of(registry, "hoard")
    assert any(key.startswith("11-16:") for key in keys)
    assert any(key.startswith("17+:") for key in keys)


def test_hoard_keeps_source_custom(registry):
    assert registry.get("table", "hoard").source == "custom"


@pytest.mark.parametrize("key, value", [
    ("11-16:sp:count", 2), ("11-16:sp:sides", 6), ("11-16:sp:mult_cp", 20_000),
    ("11-16:gp:count", 2), ("11-16:gp:sides", 6), ("11-16:gp:mult_cp", 100_000),
    ("11-16:pp:count", 1), ("11-16:pp:sides", 6), ("11-16:pp:mult_cp", 100_000),
    ("17+:gp:count", 2), ("17+:gp:sides", 6), ("17+:gp:mult_cp", 300_000),
    ("17+:pp:count", 2), ("17+:pp:sides", 6), ("17+:pp:mult_cp", 400_000),
])
def test_hoard_new_band_formula(key, value, registry):
    assert rows_of(registry, "hoard")[key] == value


def test_hoard_old_bands_are_unchanged(registry):
    rows = rows_of(registry, "hoard")
    assert (rows["0-4:cp:count"], rows["0-4:gp:mult_cp"]) == (3, 500)
    assert (rows["5-10:gp:count"], rows["5-10:pp:mult_cp"]) == (3, 10_000)


def test_individual_treasure_is_not_changed(registry):
    rows = rows_of(registry, "individual_treasure")
    assert {key.split(":")[0] for key in rows} == {"0-4", "5-10", "11-16", "17+"}
    assert len(rows) == 12
