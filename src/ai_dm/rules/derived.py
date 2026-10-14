from ai_dm.content.models.common import SKILLS
from ai_dm.core.clock import DAY
from ai_dm.rules.creatures import live_effects
from ai_dm.rules.names import ABILITY_SHORT


def ability_modifier(score: int) -> int:
    return (score - 10) // 2


def ability_mod(hero, ability: str) -> int:
    return ability_modifier(hero.sheet.abilities[ability])


def table_value(registry, table_id: str, key) -> int:
    return registry.get("table", table_id).rows[str(key)]


def proficiency(hero, registry) -> int:
    return table_value(registry, "proficiency", hero.sheet.level)


def add_amount(hero, registry, add, class_id) -> int:
    # значения add / max_add: proficiency_bonus, class_level (+ class_id), spellcasting_modifier
    if add is None:
        return 0
    if add == "proficiency_bonus":
        return proficiency(hero, registry)
    if add == "class_level":
        return hero.sheet.class_level(class_id)
    if add == "spellcasting_modifier":
        return ability_mod(hero, spellcasting_ability(hero, registry))
    raise ValueError(f"неизвестный вычисляемый бонус: {add!r}")


def effect_amount(effect, hero, registry) -> int:
    # число эффекта: value + вычисляемая добавка add (КД, инициатива, лечение и пр.)
    return (effect.value or 0) + add_amount(hero, registry, effect.add, effect.class_id)


def spellcasting_ability(hero, registry) -> str:
    spellcasting = registry.get("class", hero.sheet.class_id).spellcasting
    if spellcasting is None:
        raise ValueError("класс не заклинатель")
    return spellcasting.ability


def ability_part(hero, ability: str) -> tuple[str, int]:
    # слагаемое бонуса: («Лов», +4)
    return (ABILITY_SHORT[ability], ability_mod(hero, ability))


def saving_throw_parts(hero, registry, ability: str) -> list[tuple[str, int]]:
    parts = [ability_part(hero, ability)]
    if ability in registry.get("class", hero.sheet.class_id).saving_throws:
        parts.append(("мастерство", proficiency(hero, registry)))
    return parts


def saving_throw_bonus(hero, registry, ability: str) -> int:
    return sum(value for _, value in saving_throw_parts(hero, registry, ability))


def skill_parts(hero, registry, skill: str) -> list[tuple[str, int]]:
    if skill not in SKILLS:
        raise ValueError(f"неизвестный навык: {skill!r}")
    parts = [ability_part(hero, SKILLS[skill])]
    if skill in hero.sheet.skill_proficiencies:
        parts.append(("мастерство", proficiency(hero, registry)))
        if skill in hero.sheet.skill_expertise:
            parts.append(("компетентность", proficiency(hero, registry)))
    return parts


def skill_bonus(hero, registry, skill: str) -> int:
    return sum(value for _, value in skill_parts(hero, registry, skill))


def passive_perception(hero, registry) -> int:
    return 10 + skill_bonus(hero, registry, "perception")


def feat_effects(hero, registry, target: str):
    # эффекты-модификаторы черт героя для данной цели
    result = []
    for feat_id in hero.sheet.feats:
        if not registry.has("feat", feat_id):
            continue
        for effect in registry.get("feat", feat_id).effects:
            if effect.type == "modifier" and effect.target == target:
                result.append(effect)
    return result


def initiative_bonus(hero, registry) -> int:
    bonus = ability_mod(hero, "dex")
    for effect in feat_effects(hero, registry, "initiative"):
        bonus += effect_amount(effect, hero, registry)
    return bonus


DEX_CAP_WORDS = {"light": "лёгкого", "medium": "средн.", "heavy": "тяжёлого"}


def clock_text(seconds: int) -> str:
    # время суток: 14:05
    return f"{seconds % DAY // 3600:02d}:{seconds % 3600 // 60:02d}"


def ac_summary(hero, registry, now_s=None) -> str:
    # «КД 17 (Каменная Кожа до 03:12)»; в скобках только эффекты со сроком
    parts = armor_class_parts(hero, registry, now_s)
    text = f"КД {sum(value for _, value, _ in parts)}"
    timed = [f"{label} {note}" for label, _, note in parts if note.startswith("до ")]
    if timed:
        text += f" ({', '.join(timed)})"
    return text


def armor_dex(armor, dex) -> int:
    # Лов в КД с учётом предела доспеха (dex_cap 0 -- без Лов)
    if armor.dex_cap == 0:
        return 0
    if armor.dex_cap is not None and dex > armor.dex_cap:
        return armor.dex_cap
    return dex


def gear_ac(registry, armor_id, shield_id, dex) -> int:
    # КД по доспеху и щиту (id или None) и Лов: без доспеха 10 + Лов
    if armor_id is None:
        total = 10 + dex
    else:
        armor = registry.get("armor", armor_id)
        total = armor.ac + armor_dex(armor, dex)
    if shield_id is not None:
        total += registry.get("armor", shield_id).ac
    return total


def armor_class_parts(
    hero, registry, now_s=None, pierce=False, ignore_magic=False
) -> list[tuple[str, int, str]]:
    # слагаемые КД: (подпись, значение, пояснение); сумма = КД.
    # pierce: бронебойная стрела -- без щита, доспех не выше 12 (если КД больше 12)
    # ignore_magic: Клинок Северного Ветра -- без магических бонусов КД цели
    dex = ability_mod(hero, "dex")
    armor_id = hero.equipped.armor
    parts = []
    if armor_id is None:
        parts.append(("Без доспеха", 10, ""))
        parts.append(("Лов", dex, ""))
    else:
        armor = registry.get("armor", armor_id)
        capped = armor_dex(armor, dex)
        note = ""
        if capped != dex:
            note = f"предел {DEX_CAP_WORDS[armor.category]} доспеха {armor.dex_cap}"
        parts.append((armor.name, armor.ac, ""))
        parts.append(("Лов", capped, note))
    if hero.equipped.shield is not None:
        shield = registry.get("armor", hero.equipped.shield)
        parts.append((shield.name, shield.ac, ""))
    for feat_id in hero.sheet.feats:
        if not registry.has("feat", feat_id):
            continue
        feat = registry.get("feat", feat_id)
        for effect in feat.effects:
            if effect.type != "modifier" or effect.target != "ac":
                continue
            if effect.when == "wearing_armor" and armor_id is None:
                continue
            parts.append((feat.name, effect_amount(effect, hero, registry), ""))
    for effect in live_effects(hero.creature, now_s):
        if effect.kind != "ac":
            continue
        if ignore_magic and effect.params.get("magic"):
            continue
        note = ""
        if effect.expires is not None and effect.expires.kind == "seconds":
            note = f"до {clock_text(effect.expires.value)}"
        parts.append((effect.params["label"], effect.params["amount"], note))
    if pierce and sum(value for _, value, _ in parts) > 12:
        parts = [p for p in parts if hero.equipped.shield is None or p[0] != shield.name]
        parts[0] = (parts[0][0], min(parts[0][1], 12), parts[0][2])
    return parts


def armor_class(hero, registry, now_s=None, pierce=False, ignore_magic=False) -> int:
    parts = armor_class_parts(hero, registry, now_s, pierce, ignore_magic)
    return sum(value for _, value, _ in parts)


def weapon_ability_mod(hero, weapon) -> int:
    str_mod = ability_mod(hero, "str")
    dex_mod = ability_mod(hero, "dex")
    if "finesse" in weapon.properties:
        return max(str_mod, dex_mod)
    if weapon.kind == "ranged":
        return dex_mod
    return str_mod


def weapon_proficient(char_class, weapon) -> bool:
    if weapon.category in char_class.weapon_training:
        return True
    # воинское оружие с любым из свойств (плут)
    return weapon.category == "martial" and any(
        p in weapon.properties for p in char_class.weapon_training_properties
    )


def weapon_ability(hero, weapon) -> str:
    # характеристика оружия: та, чей модификатор берёт weapon_ability_mod
    if "finesse" in weapon.properties:
        if ability_mod(hero, "str") >= ability_mod(hero, "dex"):
            return "str"
        return "dex"
    if weapon.kind == "ranged":
        return "dex"
    return "str"


def attack_parts(hero, registry, weapon_id: str) -> list[tuple[str, int]]:
    weapon = registry.get("weapon", weapon_id)
    parts = [ability_part(hero, weapon_ability(hero, weapon))]
    if weapon_proficient(registry.get("class", hero.sheet.class_id), weapon):
        parts.append(("мастерство", proficiency(hero, registry)))
    for feat_id in hero.sheet.feats:
        if not registry.has("feat", feat_id):
            continue
        feat = registry.get("feat", feat_id)
        for effect in feat.effects:
            if effect.type != "modifier" or effect.target != "attack_roll":
                continue
            if effect.when == "ranged_weapon" and weapon.kind != "ranged":
                continue
            parts.append((feat.name, effect_amount(effect, hero, registry)))
    return parts


def attack_bonus(hero, registry, weapon_id: str) -> int:
    return sum(value for _, value in attack_parts(hero, registry, weapon_id))


def damage_parts(hero, registry, weapon_id: str) -> list[tuple[str, int]]:
    weapon = registry.get("weapon", weapon_id)
    return [ability_part(hero, weapon_ability(hero, weapon))]


def damage_bonus(hero, registry, weapon_id: str) -> int:
    return weapon_ability_mod(hero, registry.get("weapon", weapon_id))


def unarmed_attack(hero, registry) -> tuple[int, list, int, list]:
    # безоружный удар: (бонус атаки, слагаемые бонуса, урон, слагаемые урона); урон фиксированный,
    # 1 + Сила, не ниже 0; мастерство всегда
    parts = [ability_part(hero, "str"), ("мастерство", proficiency(hero, registry))]
    damage_parts = [("", 1), ability_part(hero, "str")]
    return sum(v for _, v in parts), parts, max(0, 1 + ability_mod(hero, "str")), damage_parts


def improvised_attack(hero) -> tuple[int, list]:
    # импровизированное оружие: Сила без мастерства; (бонус атаки и урона, слагаемые)
    part = ability_part(hero, "str")
    return part[1], [part]


def spell_save_dc(hero, registry) -> int:
    ability = spellcasting_ability(hero, registry)
    return 8 + proficiency(hero, registry) + ability_mod(hero, ability)


def spell_attack_parts(hero, registry) -> list[tuple[str, int]]:
    ability = spellcasting_ability(hero, registry)
    return [ability_part(hero, ability), ("мастерство", proficiency(hero, registry))]


def spell_attack_bonus(hero, registry) -> int:
    ability = spellcasting_ability(hero, registry)
    return proficiency(hero, registry) + ability_mod(hero, ability)


def spell_slots_for(registry, progression: str, level: int) -> dict[int, int]:
    # таблицы spell_slots_full / spell_slots_half: ключ "уровень:круг" -> ячейки
    rows = registry.get("table", f"spell_slots_{progression}").rows
    result = {}
    for key, count in rows.items():
        row_level, circle = key.split(":")
        if int(row_level) == level:
            result[int(circle)] = count
    return result


def spell_slots(hero, registry) -> dict[int, int]:
    spellcasting = registry.get("class", hero.sheet.class_id).spellcasting
    if spellcasting is None:
        return {}
    return spell_slots_for(registry, spellcasting.progression, hero.sheet.level)


def companion_due(hero, registry) -> bool:
    # герой с умением Зверь-спутник, у которого зверя нет
    return "beast_companion" in hero_feature_ids(hero, registry) and not hero.companions


def hero_feature_ids(hero, registry) -> list[str]:
    # умения класса/подкласса/вида по уровню героя и выбранные варианты умений
    char_class = registry.get("class", hero.sheet.class_id)
    feature_ids = [r.feature for r in char_class.features if r.level <= hero.sheet.level]
    if hero.sheet.subclass_id is not None and registry.has("subclass", hero.sheet.subclass_id):
        subclass = registry.get("subclass", hero.sheet.subclass_id)
        feature_ids += [r.feature for r in subclass.features if r.level <= hero.sheet.level]
    if registry.has("species", hero.sheet.species_id):
        feature_ids += registry.get("species", hero.sheet.species_id).traits
    for options in hero.sheet.feature_choices.values():
        for option_id in options:
            if registry.has("feature", option_id):
                feature_ids.append(option_id)
    return feature_ids


def hero_effects(hero, registry) -> list:
    # эффекты умений класса/подкласса/вида и черт героя
    feature_ids = hero_feature_ids(hero, registry)
    effects = []
    for feature_id in feature_ids:
        effects += registry.get("feature", feature_id).effects
    for feat_id in hero.sheet.feats:
        if registry.has("feat", feat_id):
            effects += registry.get("feat", feat_id).effects
    return effects


def by_level(table: dict[int, int], level: int) -> int:
    # значение по уровню героя: ближайший ключ не выше уровня (0, если такого нет)
    keys = [k for k in table if k <= level]
    if not keys:
        return 0
    return table[max(keys)]


def prepared_limit(hero, registry) -> int | None:
    # сколько заклинаний можно подготовить на уровне героя; None = без ограничения
    spellcasting = registry.get("class", hero.sheet.class_id).spellcasting
    if spellcasting is None:
        return None
    if spellcasting.prepared_by_level is not None:
        return by_level(spellcasting.prepared_by_level, hero.sheet.level)
    return spellcasting.prepared


def spell_access_effects(hero, registry) -> list:
    return [e for e in hero_effects(hero, registry) if e.type == "spell_access"]


def always_prepared(hero, registry) -> list[str]:
    # заклинания, подготовленные всегда (Метка охотника у следопыта); в лимит не входят
    result = [e.spell for e in spell_access_effects(hero, registry) if e.spell is not None]
    return result + [g.spell_id for g in hero.sheet.spells_always_prepared]


def free_cast_pool(hero, registry, spell_id: str) -> str | None:
    # пул бесплатных использований заклинания (favored_enemy для Метки охотника)
    for effect in spell_access_effects(hero, registry):
        if effect.spell == spell_id and effect.pool is not None:
            return effect.pool
    return None


# пулы длинного отдыха, восстанавливаемые полностью (по имени или префиксу)
LONG_REST_FULL = ("hit_dice:", "spell_slot:")


def resource_maxes(hero, registry) -> dict[str, int]:
    # максимумы пулов ресурсов героя: кости хитов, умения класса/вида/черт и ячейки заклинаний
    result = {}
    for entry in hero.sheet.classes:
        key = f"hit_dice:d{registry.get('class', entry.class_id).hit_die}"
        result[key] = result.get(key, 0) + entry.level
    for effect in hero_effects(hero, registry):
        if effect.type == "resource" and effect.pool is not None:
            result[effect.pool] = (effect.max or 0) + add_amount(
                hero, registry, effect.max_add, effect.class_id
            )
            if effect.max_by_level is not None:
                result[effect.pool] = by_level(effect.max_by_level, hero.sheet.level)
    for circle, count in spell_slots(hero, registry).items():
        result[f"spell_slot:{circle}"] = count
    return result
