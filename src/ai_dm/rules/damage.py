from pydantic import BaseModel

from ai_dm.core.dice import roll_damage_dice
from ai_dm.rules.checks import saving_throw
from ai_dm.rules.creatures import creature_of, end_concentration, live_effects
from ai_dm.rules.inventory import find_item
from ai_dm.rules.modifiers.species import species_effects
from ai_dm.rules.roll_pipeline import DAMAGE_TYPE_WORDS, RollLogEntry, damage_log_text

# ТЗ 2.3: кубики урона вне боя берутся из таблицы damage_severity по полосе уровня героя
HAZARD_BANDS = ("1-4", "5-10", "11-16", "17-20")


class HazardError(ValueError):
    pass


class DamageResult(BaseModel):
    final: int
    temp_absorbed: int
    hp_lost: int
    was_down: bool
    dropped: bool
    overkill: int
    raw: int = 0
    # строки лога: «Сопротивление (Каменная Кожа): 3 → 1 рубящий», «Временные HP поглотили 2»
    notes: list[str] = []


def source_name(registry, kind, source_id) -> str:
    # имя эффекта предмета или черты; для явно переданного сопротивления источника нет
    if source_id is None:
        return ""
    if kind == "feature" and registry.has("feature", source_id):
        return registry.get("feature", source_id).name
    found = find_item(registry, source_id)
    if kind == "item" and found is not None:
        return found[1].short_name or found[1].name
    return source_id


def adjust_note(title, source, before, after, damage_type) -> str:
    text = title
    if source:
        text += f" ({source})"
    return f"{text}: {before} → {after} {DAMAGE_TYPE_WORDS.get(damage_type, damage_type)}"


class HazardResult(BaseModel):
    damage: DamageResult
    log: RollLogEntry


def apply_damage(
    target, amount: int, damage_type: str, registry, *,
    resistances=(), vulnerabilities=(), immunities=(), now_s=None,
) -> DamageResult:
    if amount < 0:
        raise ValueError("урон не может быть отрицательным")
    resistances = list(resistances)
    # источник сопротивления: тип урона -> имя (первый найденный)
    sources = {}
    for trait_id, effect in species_effects(target, registry):
        if effect.type == "modifier" and effect.target == "damage" and effect.mode == "resistance":
            resistances.append(effect.damage_type)
            sources.setdefault(effect.damage_type, source_name(registry, "feature", trait_id))
    # сопротивления от эффектов (эликсир «Каменная Кожа»); now_s -- чтобы не считать истёкшие
    for effect in live_effects(creature_of(target), now_s):
        if effect.kind == "resist":
            resistances.append(effect.params["damage_type"])
            sources.setdefault(
                effect.params["damage_type"], source_name(registry, "item", effect.id)
            )
    final = amount
    notes = []
    if damage_type in immunities:
        final = 0
        notes.append(adjust_note("Иммунитет", "", amount, 0, damage_type))
    else:
        if damage_type in resistances:
            half = final // 2
            notes.append(adjust_note(
                "Сопротивление", sources.get(damage_type, ""), final, half, damage_type
            ))
            final = half
        if damage_type in vulnerabilities:
            notes.append(adjust_note("Уязвимость", "", final, final * 2, damage_type))
            final *= 2
    creature = creature_of(target)
    was_down = creature.hp_current == 0
    hp_before = creature.hp_current
    temp_absorbed = min(creature.hp_temp, final)
    creature.hp_temp -= temp_absorbed
    if temp_absorbed > 0:
        notes.append(f"Временные HP поглотили {temp_absorbed}")
    rest = final - temp_absorbed
    hp_lost = min(creature.hp_current, rest)
    creature.hp_current -= hp_lost
    return DamageResult(
        final=final,
        temp_absorbed=temp_absorbed,
        hp_lost=hp_lost,
        was_down=was_down,
        dropped=hp_before > 0 and creature.hp_current == 0,
        overkill=rest - hp_lost,
        raw=amount,
        notes=notes,
    )


def hazard_dice(level: int, severity: str, registry) -> str:
    rows = registry.get("table", "damage_severity").rows
    for band in HAZARD_BANDS:
        low, high = band.split("-")
        if int(low) <= level <= int(high):
            break
    else:
        raise ValueError(f"уровень вне 1..20: {level}")
    if f"{band}:{severity}:count" not in rows:
        raise ValueError(f"неизвестная тяжесть: {severity!r}")
    return f"{rows[f'{band}:{severity}:count']}d{rows[f'{band}:{severity}:sides']}"


def roll_hazard(
    hero, severity: str, damage_type: str, registry, rng, *, failed_save: bool = False
) -> HazardResult:
    dice = hazard_dice(hero.sheet.level, severity, registry)
    if severity == "deadly" and not failed_save:
        raise HazardError("смертельный урон только после проваленного спасброска")
    rolled = roll_damage_dice(dice, 0, rng)
    applied = apply_damage(hero, rolled.total, damage_type, registry)
    log = RollLogEntry(text=damage_log_text(
        rolled, 0, False, label="Урон (опасность)", damage_type=damage_type
    ))
    return HazardResult(damage=applied, log=log)


def concentration_check(hero, damage: int, registry, rng, *, modifiers=None, rerollers=None):
    creature = hero.creature
    if creature.concentration is None:
        return None
    dc = min(30, max(10, damage // 2))
    result = saving_throw(
        hero, registry, rng, "con", dc=dc, modifiers=modifiers, rerollers=rerollers
    )
    if result.outcome == "fail":
        end_concentration(creature)
    return result
