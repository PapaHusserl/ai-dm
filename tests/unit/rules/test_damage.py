# Ожидаемый API: ai_dm.rules.damage (target: HeroState | CreatureState, мутируется на месте)
#   apply_damage(target, amount: int, damage_type: str, registry, *,
#                resistances=(), vulnerabilities=(), immunities=()) -> DamageResult
#       порядок: иммунитет (0) -> сопротивление (// 2, вниз) -> уязвимость (* 2); сопротивление и
#       уязвимость к одному типу вместе: сначала половина, потом x2 (SRD 5.2); затем временные HP
#       поглощают первыми, остаток -- в hp_current, не ниже 0; всё целочисленно.
#       У героя к явным спискам добавляются черты вида через registry (дварф: сопротивление яду).
#       amount < 0 -> ValueError. Состояния и death saves НЕ трогает (это death_saves.after_damage)
#   DamageResult(BaseModel): final: int (после сопротивлений), temp_absorbed: int, hp_lost: int,
#       was_down: bool (hp был 0 до удара), dropped: bool (было > 0, стало 0),
#       overkill: int (сколько урона не поместилось ниже 0 HP; при was_down -- весь final)
#   roll_damage удалён (аудит 1 п. 2.12): кубики урона -- core.dice.roll_damage_dice
#       (крит удваивает ЧИСЛО кубиков, бонус не удваивается -- тесты в core/test_dice.py)
#   hazard_dice(level: int, severity: str, registry) -> str  -- ТЗ 2.3, severity: "nuisance" |
#       "dangerous" | "deadly"; таблица damage_severity (К0б, SRD 5.2) по полосам 1-4 / 5-10 / 11-16 /
#       17-20: 1d10 2d10 4d10 / 2d10 4d10 10d10 / 4d10 10d10 18d10 / 10d10 18d10 24d10;
#       уровень вне 1..20 или неизвестная тяжесть -> ValueError
#   HazardError(ValueError)
#   roll_hazard(hero, severity, damage_type, registry, rng, *, failed_save=False) -> HazardResult
#       HazardResult(BaseModel): damage: DamageResult (итог apply_damage), log: RollLogEntry
#       (B6; строка с гранями: "урон 2d10 (4, 7) + 0 = 11", текст по формату урона конвейера)
#       кубики по hero.sheet.level; "deadly" без failed_save=True -> HazardError до броска
#       (rng и HP не тронуты); урон применяется через apply_damage
#   concentration_check(hero, damage: int, registry, rng, *, modifiers=None, rerollers=None)
#       -> RollResult | None   (modifiers / rerollers пробрасываются в спасбросок, B7)
#       нет creature.concentration -> None (rng не трогается); иначе спасбросок ТЕЛ (через checks.
#       saving_throw) с СЛ min(30, max(10, damage // 2)); провал: concentration = None и снимаются
#       ActiveEffect-ы с expires.kind == "concentration" (остальные остаются)
#       (общий помощник end_concentration, он же вызывается при падении на 0 HP и смерти --
#       тесты в test_death_saves.py и test_mortality_guard.py)
import pytest

from ai_dm.core.rng import Rng
from ai_dm.rules.damage import (
    HazardError,
    apply_damage,
    concentration_check,
    hazard_dice,
    roll_hazard,
)
from ai_dm.rules.modifiers import Modifier, ModifierRegistry
from ai_dm.rules.roll_pipeline import RollLogEntry
from ai_dm.state.creature import ActiveEffect, Concentration, CreatureState, Expiry
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState


class ScriptedRng(Rng):
    def __init__(self, *rolls):
        super().__init__(1)
        self.rolls = list(rolls)

    def randbelow(self, n):
        sides, face = self.rolls.pop(0)
        assert sides == n
        return face - 1


def make_creature(hp=10, hp_max=10, temp=0):
    return CreatureState(hp_current=hp, hp_max=hp_max, hp_temp=temp)


def make_hero(species="human", level=1, hp=12):
    sheet = CharacterSheet(
        species_id=species,
        classes=[ClassLevel(class_id="fighter", level=level)], level_history=["fighter"] * level,
        background=BackgroundSpec(
            name="Солдат",
            abilities=["str", "dex", "con"],
            skills=["athletics", "intimidation"],
            tool="dice_set",
            feat="savage_attacker",
        ),
        abilities={"str": 17, "dex": 13, "con": 15, "int": 8, "wis": 10, "cha": 12},
    )
    return HeroState(
        id="h1", ordinal=1, name="Арн", sheet=sheet,
        creature=CreatureState(hp_current=hp, hp_max=hp),
    )


# применение урона

def test_damage_reduces_hp(registry):
    target = make_creature()
    result = apply_damage(target, 4, "slashing", registry)
    assert target.hp_current == 6
    assert result.final == 4
    assert result.hp_lost == 4


def test_zero_damage_changes_nothing(registry):
    target = make_creature()
    apply_damage(target, 0, "slashing", registry)
    assert target.hp_current == 10


def test_negative_damage_is_error(registry):
    with pytest.raises(ValueError):
        apply_damage(make_creature(), -1, "slashing", registry)


def test_hero_target_is_mutated_through_creature(registry):
    hero = make_hero()
    apply_damage(hero, 5, "slashing", registry)
    assert hero.creature.hp_current == 7


def test_hp_never_goes_below_zero(registry):
    target = make_creature()
    result = apply_damage(target, 25, "slashing", registry)
    assert target.hp_current == 0
    assert result.overkill == 15
    assert result.dropped is True


def test_exact_lethal_damage_drops_without_overkill(registry):
    result = apply_damage(make_creature(), 10, "slashing", registry)
    assert result.dropped is True
    assert result.overkill == 0


def test_non_lethal_damage_does_not_drop(registry):
    result = apply_damage(make_creature(), 9, "slashing", registry)
    assert result.dropped is False
    assert result.was_down is False


def test_damage_at_zero_hp_is_was_down_and_not_dropped(registry):
    target = make_creature(hp=0)
    result = apply_damage(target, 3, "slashing", registry)
    assert result.was_down is True
    assert result.dropped is False
    assert result.overkill == 3
    assert target.hp_current == 0


# сопротивление, уязвимость, иммунитет

def test_resistance_halves_rounding_down(registry):
    target = make_creature()
    result = apply_damage(target, 7, "fire", registry, resistances=["fire"])
    assert result.final == 3
    assert target.hp_current == 7


def test_vulnerability_doubles(registry):
    result = apply_damage(make_creature(30, 30), 7, "fire", registry, vulnerabilities=["fire"])
    assert result.final == 14


def test_immunity_blocks_all_damage(registry):
    target = make_creature()
    result = apply_damage(target, 9, "fire", registry, immunities=["fire"])
    assert result.final == 0
    assert target.hp_current == 10


def test_resistance_and_vulnerability_halve_first_then_double(registry):
    result = apply_damage(
        make_creature(30, 30), 7, "fire", registry, resistances=["fire"], vulnerabilities=["fire"]
    )
    assert result.final == 6


def test_resistance_to_other_type_does_not_apply(registry):
    result = apply_damage(make_creature(), 7, "slashing", registry, resistances=["fire"])
    assert result.final == 7


def test_dwarf_hero_resists_poison(registry):
    hero = make_hero("dwarf")
    result = apply_damage(hero, 9, "poison", registry)
    assert result.final == 4


def test_dwarf_hero_takes_full_fire_damage(registry):
    result = apply_damage(make_hero("dwarf"), 9, "fire", registry)
    assert result.final == 9


def test_human_hero_takes_full_poison_damage(registry):
    result = apply_damage(make_hero("human"), 9, "poison", registry)
    assert result.final == 9


# временные HP

def test_temp_hp_absorbs_first(registry):
    target = make_creature(temp=5)
    result = apply_damage(target, 3, "slashing", registry)
    assert target.hp_temp == 2
    assert target.hp_current == 10
    assert result.temp_absorbed == 3
    assert result.hp_lost == 0


def test_damage_over_temp_hp_goes_to_hp(registry):
    target = make_creature(temp=5)
    result = apply_damage(target, 8, "slashing", registry)
    assert target.hp_temp == 0
    assert target.hp_current == 7
    assert result.temp_absorbed == 5
    assert result.hp_lost == 3


def test_resistance_applies_before_temp_hp(registry):
    target = make_creature(temp=5)
    apply_damage(target, 8, "fire", registry, resistances=["fire"])
    assert target.hp_temp == 1
    assert target.hp_current == 10


def test_damage_values_are_ints(registry):
    target = make_creature()
    result = apply_damage(target, 7, "fire", registry, resistances=["fire"])
    assert type(result.final) is int
    assert type(target.hp_current) is int


# кубики урона и крит

def test_roll_damage_is_removed_in_favor_of_roll_damage_dice():
    # аудит 1 п. 2.12: единственная реализация -- core.dice.roll_damage_dice
    import ai_dm.rules.damage as damage

    assert not hasattr(damage, "roll_damage")


# урон вне боя

BANDS_DICE = {
    (1, 4): {"nuisance": "1d10", "dangerous": "2d10", "deadly": "4d10"},
    (5, 10): {"nuisance": "2d10", "dangerous": "4d10", "deadly": "10d10"},
    (11, 16): {"nuisance": "4d10", "dangerous": "10d10", "deadly": "18d10"},
    (17, 20): {"nuisance": "10d10", "dangerous": "18d10", "deadly": "24d10"},
}
HAZARD_CASES = [
    (level, severity, dice)
    for (low, high), by_severity in BANDS_DICE.items()
    for level in sorted({low, high})
    for severity, dice in by_severity.items()
]


@pytest.mark.parametrize("level, severity, dice", HAZARD_CASES)
def test_hazard_dice_by_level_band(level, severity, dice, registry):
    assert hazard_dice(level, severity, registry) == dice


@pytest.mark.parametrize("level", [2, 3])
def test_hazard_dice_inside_first_band(level, registry):
    assert hazard_dice(level, "deadly", registry) == "4d10"


@pytest.mark.parametrize("level", [6, 7, 8, 9])
def test_hazard_dice_inside_second_band(level, registry):
    assert hazard_dice(level, "dangerous", registry) == "4d10"


@pytest.mark.parametrize("level", [12, 13, 14, 15])
def test_hazard_dice_inside_third_band(level, registry):
    assert hazard_dice(level, "nuisance", registry) == "4d10"


@pytest.mark.parametrize("level", [18, 19])
def test_hazard_dice_inside_last_band(level, registry):
    assert hazard_dice(level, "deadly", registry) == "24d10"


@pytest.mark.parametrize("level", [0, -1, 21, 100])
def test_hazard_dice_level_out_of_range_is_error(level, registry):
    with pytest.raises(ValueError):
        hazard_dice(level, "nuisance", registry)


def test_hazard_dice_unknown_severity_is_error(registry):
    with pytest.raises(ValueError):
        hazard_dice(1, "apocalypse", registry)


def test_hazard_dice_unknown_severity_is_error_on_high_level(registry):
    with pytest.raises(ValueError):
        hazard_dice(20, "apocalypse", registry)


def test_hazard_constants_are_removed_in_favor_of_table():
    import ai_dm.rules.damage as damage

    assert not hasattr(damage, "HAZARD_DICE")
    assert not hasattr(damage, "HAZARD_DICE_LEVEL_5")


def test_roll_hazard_nuisance_applies_damage(registry):
    hero = make_hero()
    result = roll_hazard(hero, "nuisance", "fire", registry, ScriptedRng((10, 6)))
    assert result.damage.final == 6
    assert hero.creature.hp_current == 6


def test_roll_hazard_level_5_uses_bigger_dice(registry):
    hero = make_hero(level=5, hp=50)
    rng = ScriptedRng((10, 3), (10, 4))
    result = roll_hazard(hero, "nuisance", "fire", registry, rng)
    assert result.damage.final == 7


def test_roll_hazard_deadly_without_failed_save_is_refused(registry):
    hero = make_hero()
    rng = ScriptedRng()
    with pytest.raises(HazardError):
        roll_hazard(hero, "deadly", "fire", registry, rng)
    assert hero.creature.hp_current == 12


def test_roll_hazard_deadly_after_failed_save_works(registry):
    hero = make_hero(hp=50)
    rng = ScriptedRng((10, 5), (10, 5), (10, 5), (10, 5))
    result = roll_hazard(hero, "deadly", "fire", registry, rng, failed_save=True)
    assert result.damage.final == 20
    assert hero.creature.hp_current == 30


@pytest.mark.parametrize(
    "severity, count", [("nuisance", 4), ("dangerous", 10), ("deadly", 18)]
)
def test_roll_hazard_level_12_uses_dice_of_third_band(severity, count, registry):
    hero = make_hero(level=12, hp=500)
    rng = ScriptedRng(*[(10, 1)] * count)
    result = roll_hazard(hero, severity, "fire", registry, rng, failed_save=True)
    assert result.damage.final == count


def test_roll_hazard_level_20_deadly_rolls_24_dice(registry):
    hero = make_hero(level=20, hp=500)
    rng = ScriptedRng(*[(10, 2)] * 24)
    result = roll_hazard(hero, "deadly", "fire", registry, rng, failed_save=True)
    assert result.damage.final == 48
    assert hero.creature.hp_current == 452


def test_roll_hazard_level_20_without_failed_save_is_refused(registry):
    hero = make_hero(level=20, hp=500)
    with pytest.raises(HazardError):
        roll_hazard(hero, "deadly", "fire", registry, ScriptedRng())


def test_roll_hazard_respects_resistance_of_species(registry):
    hero = make_hero("dwarf")
    result = roll_hazard(hero, "nuisance", "poison", registry, ScriptedRng((10, 8)))
    assert result.damage.final == 4


def test_roll_hazard_returns_log_with_dice_faces(registry):
    hero = make_hero(level=1, hp=50)
    result = roll_hazard(hero, "dangerous", "fire", registry, ScriptedRng((10, 4), (10, 7)))
    assert isinstance(result.log, RollLogEntry)
    assert "2d10 (4, 7)" in result.log.text
    assert "огненный" in result.log.text


def test_roll_hazard_log_is_a_damage_line(registry):
    hero = make_hero()
    result = roll_hazard(hero, "nuisance", "fire", registry, ScriptedRng((10, 6)))
    assert result.log.text.startswith("Урон (опасность): 1d10 (6)")


# концентрация

def concentrating_hero():
    hero = make_hero()
    hero.creature.concentration = Concentration(spell_id="bless", circle=1)
    hero.creature.active_effects = [
        ActiveEffect(
            id="bless", source="h1", kind="modifier",
            params={"target": "attack_roll", "dice": "1d4"}, expires=Expiry(kind="concentration"),
        ),
        ActiveEffect(
            id="sap", source="g1", kind="modifier",
            params={"target": "attack_roll", "mode": "disadvantage"},
            expires=Expiry(kind="start_of_turn", owner="g1"),
        ),
    ]
    return hero


def test_no_concentration_means_no_check(registry):
    hero = make_hero()
    assert concentration_check(hero, 20, registry, ScriptedRng()) is None


@pytest.mark.parametrize(
    "damage, dc",
    [(1, 10), (19, 10), (20, 10), (22, 11), (40, 20), (60, 30), (100, 30)],
)
def test_concentration_dc(registry, damage, dc):
    result = concentration_check(concentrating_hero(), damage, registry, ScriptedRng((20, 10)))
    assert result.dc == dc


def test_concentration_is_con_save(registry):
    # ТЕЛ 15 (+2) и мастерство спасброска воина (+2)
    result = concentration_check(concentrating_hero(), 10, registry, ScriptedRng((20, 10)))
    assert result.kind == "save"
    assert result.total == 14


def test_concentration_success_keeps_spell(registry):
    hero = concentrating_hero()
    concentration_check(hero, 10, registry, ScriptedRng((20, 15)))
    assert hero.creature.concentration.spell_id == "bless"
    assert len(hero.creature.active_effects) == 2


def test_concentration_fail_drops_spell_and_its_effects(registry):
    hero = concentrating_hero()
    concentration_check(hero, 10, registry, ScriptedRng((20, 2)))
    assert hero.creature.concentration is None
    assert [e.id for e in hero.creature.active_effects] == ["sap"]


class FlatSource:
    id = "flat"

    def modifiers(self, request, registry):
        return [Modifier(source="flat", flat=5)]


def test_concentration_check_passes_modifiers_to_save(registry):
    # d20 5 + 4 = 9 < СЛ 10, а с источником +5 -- 14: концентрация держится
    modifiers = ModifierRegistry()
    modifiers.register(FlatSource())
    hero = concentrating_hero()
    result = concentration_check(hero, 10, registry, ScriptedRng((20, 5)), modifiers=modifiers)
    assert result.total == 14
    assert hero.creature.concentration.spell_id == "bless"


def test_concentration_check_passes_empty_rerollers_to_save(registry):
    hero = concentrating_hero()
    hero.sheet.species_id = "halfling"
    result = concentration_check(hero, 10, registry, ScriptedRng((20, 1)), rerollers=[])
    assert result.natural == 1
    assert result.rerolls == []
    assert hero.creature.concentration is None


def test_concentration_check_halfling_luck_saves_spell_by_default(registry):
    hero = concentrating_hero()
    hero.sheet.species_id = "halfling"
    result = concentration_check(hero, 10, registry, ScriptedRng((20, 1), (20, 15)))
    assert result.rerolls == ["luck"]
    assert hero.creature.concentration.spell_id == "bless"
