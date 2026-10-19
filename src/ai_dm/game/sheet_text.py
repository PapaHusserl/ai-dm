import textwrap

from ai_dm.content.models.common import ABILITIES, SKILLS
from ai_dm.rules.derived import (
    ability_mod,
    always_prepared,
    free_cast_pool,
    hero_effects,
    passive_perception,
    proficiency,
    resource_maxes,
    saving_throw_bonus,
    skill_bonus,
    spell_slots,
)
from ai_dm.rules.inventory import RESIST_WORDS, dearest_cost, entry_name, find_item
from ai_dm.rules.money import format_cp
from ai_dm.rules.names import ABILITY_SHORT, SKILL_NAMES
from ai_dm.rules.progression import max_level, xp_for_level

INV_GROUPS = [
    ("quest", "Сюжетное"),
    ("weapon", "Оружие"),
    ("armor", "Доспехи и одежда"),
    ("ammo", "Боеприпасы"),
    ("consumable", "Зелья и расходники"),
    ("gear", "Снаряжение и инструменты"),
    ("valuable", "Ценности и прочее"),
]
CATEGORY_GROUP = {
    "consumable": "consumable", "clothing": "armor", "valuable": "valuable", "quest": "quest",
}
DAMAGE_SHORT = {
    "fire": "огонь", "cold": "холод", "piercing": "колющий", "slashing": "рубящий",
    "bludgeoning": "дробящий", "force": "силовое поле", "poison": "яд",
}
TAG_WORDS = {"undead": "нежити", "mor": "тварей Мора"}
CASTING_WORDS = {"action": "действие", "bonus_action": "бонусное", "reaction": "реакция"}
RANGE_WORDS = {"self": "на себя", "touch": "касание"}
ACTIVATION_WORDS = {
    "passive": "пассивно", "action": "действие", "bonus_action": "бонусное действие",
    "reaction": "реакция",
}
REST_UNTIL = {"short_rest": "до короткого отдыха", "long_rest": "до долгого отдыха"}
REST_FOR = {"short_rest": "за короткий", "long_rest": "за долгий"}
TIME_UNITS = (("h", "ч"), ("m", "мин"), ("s", "с"))
SPELL_HINT = (
    "В бою — пункт меню; вне боя — скажи мастеру «читаю Лечение ран на себя»."
)
ABILITY_HINT = (
    "В бою — пункт меню; вне боя — скажи мастеру, что применяешь умение."
)


def fit(lines, width):
    # перенос по ширине с висячим отступом (UI добавит ещё два пробела слева)
    result = []
    for line in lines:
        indent = len(line) - len(line.lstrip())
        result += textwrap.wrap(line, width - 2, subsequent_indent=" " * (indent + 2)) or [""]
    return result


def rows(title, items, width, sep=" · "):
    # «Навыки: a · b · c» с переносом только между элементами
    result = []
    line = title
    for item in items:
        piece = item if line == title else sep + item
        if line != title and len(line) + len(piece) > width - 2:
            result.append(line)
            line = "  " + item
        elif line == title:
            line = f"{title} {item}" if title else item
        else:
            line += piece
    result.append(line)
    return result


def signed(number):
    return f"+{number}" if number >= 0 else f"{number}"


def description_lines(text, width):
    # полное описание: абзацы по строкам, перенос по ширине с отступом в 4 пробела
    lines = []
    for part in text.strip().split("\n"):
        lines += textwrap.wrap(part, width - 2, initial_indent="    ", subsequent_indent="    ")
    return lines


def seconds_text(seconds):
    if seconds % 3600 == 0:
        return f"{seconds // 3600} ч"
    if seconds % 60 == 0:
        return f"{seconds // 60} мин"
    return f"{seconds} с"


def effect_texts(effects):
    # эффекты предмета кратко: «+1d8 холод», «замедл. 10 фт», «+2 КД, сопр. рубящему/дробящему 1 ч»
    texts = []
    resists = []
    duration = None
    for effect in effects:
        if effect.duration_s is not None:
            duration = effect.duration_s
        damage = DAMAGE_SHORT.get(effect.damage_type, effect.damage_type)
        if effect.type == "pierce_armor":
            texts.append("пробивает доспех")
        elif effect.type == "extra_damage":
            text = f"+{effect.dice} {damage}"
            if effect.vs:
                text += " против " + "/".join(TAG_WORDS.get(tag, tag) for tag in effect.vs)
            texts.append(text)
        elif effect.type == "burn":
            texts.append(f"поджог {effect.dice} {damage}")
        elif effect.type == "slow":
            texts.append(f"замедл. {effect.value} фт")
        elif effect.type == "sleep":
            texts.append(f"сон: СЛ {effect.dc} Тел")
        elif effect.type == "silvered":
            texts.append("серебро")
        elif effect.type == "ac_bonus":
            texts.append(f"+{effect.value} КД")
        elif effect.type == "resist":
            resists.append(RESIST_WORDS.get(effect.damage_type, effect.damage_type))
        elif effect.type == "heal":
            texts.append(f"лечит {effect.dice}" + (f"+{effect.value}" if effect.value else ""))
    if resists:
        texts.append("сопр. " + "/".join(resists))
    text = ", ".join(texts)
    if duration is not None and text:
        text += f" {seconds_text(duration)}"
    return text


def weight_text(centilb):
    # 150 -> «1,5 фнт»
    return f"{centilb / 100:g}".replace(".", ",") + " фнт"


def world_item_text(item, cost_cp):
    # сюжетный предмет: описание и в скобках вес/цена, если заданы
    parts = []
    if item.weight_centilb:
        parts.append(weight_text(item.weight_centilb))
    if cost_cp:
        parts.append(format_cp(cost_cp))
    tail = f"({', '.join(parts)})" if parts else ""
    return " ".join(x for x in (item.description, tail) if x)


def inv_group(kind, item):
    if kind == "weapon":
        return "weapon"
    if kind == "armor":
        return "armor"
    if item.ammo_for:
        return "ammo"
    if item.effects:
        return "consumable"
    return CATEGORY_GROUP.get(item.category, "gear")


def inv_lines(hero, registry, money_text):
    worn = [
        hero.equipped.armor, hero.equipped.shield, hero.equipped.main_hand, hero.equipped.off_hand,
    ]
    groups = {key: [] for key, _ in INV_GROUPS}
    marked = set()
    for entry in hero.inventory:
        found = find_item(registry, entry.item_id)
        # надета вещь из самого дорогого стека этого id
        is_worn = entry.item_id in worn and entry.cost_cp == dearest_cost(hero, entry.item_id)
        is_worn = is_worn and entry.item_id not in marked
        if is_worn:
            marked.add(entry.item_id)
        name = entry_name(entry, registry)
        if found is None:
            groups["gear"].append((name, is_worn, entry.qty, ""))
            continue
        kind, item = found
        text = ""
        if item.source == "world":
            text = world_item_text(item, entry.cost_cp)
        elif kind != "armor":
            text = effect_texts(item.effects)
        if item.source != "world" and entry.cost_cp > 0:
            text = ", ".join(x for x in (text, format_cp(entry.cost_cp)) if x)
        groups[inv_group(kind, item)].append((name, is_worn, entry.qty, text))
    lines = []
    for key, title in INV_GROUPS:
        if not groups[key]:
            continue
        lines.append(f"{title}:")
        for name, is_worn, qty, text in sorted(groups[key]):
            mark = "★ " if is_worn else "  "
            line = f"  {mark}{name}"
            if qty > 1:
                line += f" x{qty}"
            if text:
                line += f" — {text}"
            lines.append(line)
    lines.append(f"Деньги: {money_text}")
    return lines


def title_line(hero, registry):
    sheet = hero.sheet
    species = registry.get("species", sheet.species_id).name.lower()
    char_class = registry.get("class", sheet.class_id).name.lower()
    text = f"{hero.name} — {species}, {char_class} {sheet.level} ур."
    if sheet.subclass_id is not None:
        text += f" ({registry.get('subclass', sheet.subclass_id).name})"
    text += f", опыт {sheet.xp}"
    if sheet.level < max_level(registry):
        text += f"/{xp_for_level(sheet.level + 1, registry)}"
    return text


def hooks_lines(hero) -> list[str]:
    # предыстория (если с описанием), мотив, средства, возможности героя
    lines = []
    background = hero.sheet.background
    if background.description:
        lines.append(f"Предыстория: {background.name} — {background.description}")
    if hero.motive:
        lines.append(f"Мотив: {hero.motive}")
    if hero.means:
        lines.append("Средства: " + "; ".join(hero.means))
    if hero.opportunity:
        lines.append("Возможности: " + "; ".join(f"{t.id} — {t.then}" for t in hero.opportunity))
    return lines


def sheet_stat_lines(hero, registry, width):
    sheet = hero.sheet
    lines = []
    scores = [
        f"{ABILITY_SHORT[a]} {sheet.abilities[a]} ({signed(ability_mod(hero, a))})"
        for a in ABILITIES
    ]
    lines += rows("", scores, width)
    lines.append(f"Бонус мастерства {signed(proficiency(hero, registry))}")
    char_class = registry.get("class", sheet.class_id)
    saves = []
    for a in ABILITIES:
        star = "★" if a in char_class.saving_throws else ""
        saves.append(f"{star}{ABILITY_SHORT[a]} {signed(saving_throw_bonus(hero, registry, a))}")
    lines += rows("Спасброски:", saves, width)
    skills = []
    for skill in SKILLS:
        star = ""
        if skill in sheet.skill_proficiencies:
            star = "★★" if skill in sheet.skill_expertise else "★"
        skills.append(f"{star}{SKILL_NAMES[skill]} {signed(skill_bonus(hero, registry, skill))}")
    lines += rows("Навыки:", skills, width)
    feats = []
    styles = []
    for feat_id in sheet.feats:
        if not registry.has("feat", feat_id):
            feats.append(feat_id)
            continue
        feat = registry.get("feat", feat_id)
        if feat.category == "fighting_style":
            styles.append(feat.name)
        else:
            feats.append(feat.name)
    if feats:
        lines.append("Черты: " + ", ".join(feats))
    if styles:
        lines.append("Боевой стиль: " + ", ".join(styles))
    speed = registry.get("species", sheet.species_id).speed_ft
    passive = passive_perception(hero, registry)
    lines.append(f"Скорость {speed} фт. · Пассивная Внимательность {passive}")
    for companion in hero.companions:
        lines.append(f"Зверь-спутник: {companion.name} ({companion.kind})")
    if hero.attuned:
        lines.append("Настроено: " + ", ".join(hero.attuned))
    return lines


def pool_now(hero, registry, pool):
    # (текущее, максимум) пула ресурса героя
    maximum = resource_maxes(hero, registry).get(pool, 0)
    state = hero.creature.resources.get(pool)
    if state is None:
        return maximum, maximum
    return state.current, state.max


def recover_text(registry_effects, pool):
    # «до долгого отдыха» / «1 за короткий, все за долгий отдых»
    for effect in registry_effects:
        if effect.type != "resource" or effect.pool != pool:
            continue
        rows = effect.recover
        if len(rows) == 1 and rows[0].amount == "all":
            return REST_UNTIL[rows[0].on]
        parts = []
        for row in rows:
            amount = "все" if row.amount == "all" else str(row.amount)
            parts.append(f"{amount} за {REST_FOR[row.on]}")
        return ", ".join(parts) + " отдых"
    return ""


def slots_lines(hero, registry):
    lines = []
    for circle, maximum in sorted(spell_slots(hero, registry).items()):
        current, _ = pool_now(hero, registry, f"spell_slot:{circle}")
        dots = "●" * current + "○" * (maximum - current)
        lines.append(f"{circle} круг: {dots} ({current}/{maximum})")
    return lines


def casting_text(spell):
    time = CASTING_WORDS.get(spell.casting_time)
    if time is None:
        digits = "".join(c for c in spell.casting_time if c.isdigit())
        unit = dict(TIME_UNITS).get(spell.casting_time[len(digits):], "")
        time = f"{digits} {unit}"
    if spell.range_kind == "ranged":
        range_text = f"{spell.range_ft} фт."
    else:
        range_text = RANGE_WORDS[spell.range_kind]
    parts = [time]
    if spell.concentration:
        parts.append("К")
    parts.append(range_text)
    return ", ".join(parts)


def spell_names(hero, registry):
    names = []
    for spell_id in spell_ids(hero, registry):
        if registry.has("spell", spell_id):
            names.append(registry.get("spell", spell_id).name)
        else:
            names.append(spell_id)
    return sorted(names)


def spell_ids(hero, registry):
    ids = []
    sheet = hero.sheet
    for spell_id in always_prepared(hero, registry) + sheet.prepared_of() + sheet.known_of():
        if spell_id not in ids:
            ids.append(spell_id)
    return ids


def spells_lines(hero, registry, width, with_description=True):
    if registry.get("class", hero.sheet.class_id).spellcasting is None:
        return ["Заклинаний нет."]
    lines = ["Ячейки:"]
    lines += ["  " + text for text in slots_lines(hero, registry)]
    by_level = {}
    for spell_id in spell_ids(hero, registry):
        if not registry.has("spell", spell_id):
            by_level.setdefault(0, []).append((spell_id, None))
            continue
        spell = registry.get("spell", spell_id)
        by_level.setdefault(spell.level, []).append((spell.name, spell))
    for level in sorted(by_level):
        lines.append("Заговоры:" if level == 0 else f"Заклинания, {level} круг:")
        for name, spell in sorted(by_level[level], key=lambda pair: pair[0]):
            if spell is None:
                lines.append(f"  {name}")
                continue
            lines.append(f"  {name} ({casting_text(spell)})")
            if with_description and spell.description:
                lines += description_lines(spell.description, width)
    free = []
    effects = hero_effects(hero, registry)
    for spell_id in always_prepared(hero, registry):
        pool = free_cast_pool(hero, registry, spell_id)
        if pool is None or not registry.has("spell", spell_id):
            continue
        current, maximum = pool_now(hero, registry, pool)
        text = f"{registry.get('spell', spell_id).name} без ячейки: {current}/{maximum}"
        recover = recover_text(effects, pool)
        if recover:
            text += f" {recover}"
        free.append(text)
    if free:
        lines.append("Бесплатные применения:")
        lines += ["  " + text for text in free]
    return lines


def feature_groups(hero, registry):
    # [(заголовок, [id умений])]: класс, подкласс, вид, выбранные варианты идут за своим умением
    sheet = hero.sheet
    options = sheet.feature_choices

    def with_options(feature_ids):
        result = []
        for feature_id in feature_ids:
            result.append(feature_id)
            if feature_id in options:
                result += options[feature_id]
        return result

    char_class = registry.get("class", sheet.class_id)
    groups = [(char_class.name, with_options(
        [r.feature for r in char_class.features if r.level <= sheet.level]
    ))]
    if sheet.subclass_id is not None and registry.has("subclass", sheet.subclass_id):
        subclass = registry.get("subclass", sheet.subclass_id)
        groups.append((subclass.name, with_options(
            [r.feature for r in subclass.features if r.level <= sheet.level]
        )))
    if registry.has("species", sheet.species_id):
        species = registry.get("species", sheet.species_id)
        groups.append((species.name, with_options(species.traits)))
    return groups


def ability_line(hero, registry, feature_id, width):
    # «Имя — когда работает; остаток», вторая строка — суть
    feature = registry.get("feature", feature_id)
    text = f"  {feature.name} — {ACTIVATION_WORDS[feature.activation]}"
    for effect in feature.effects:
        if effect.type == "resource" and effect.pool is not None:
            current, maximum = pool_now(hero, registry, effect.pool)
            text += f"; {current}/{maximum}"
            recover = recover_text(feature.effects, effect.pool)
            if recover:
                text += f" {recover}"
    lines = [text]
    if feature.description:
        lines += description_lines(feature.description, width)
    return lines


def abilities_lines(hero, registry, width):
    lines = []
    for title, feature_ids in feature_groups(hero, registry):
        if not feature_ids:
            continue
        lines.append(f"{title}:")
        for feature_id in feature_ids:
            lines += ability_line(hero, registry, feature_id, width)
    if hero.sheet.feats:
        lines.append("Черты:")
    for feat_id in hero.sheet.feats:
        if not registry.has("feat", feat_id):
            lines.append(f"  {feat_id}")
            continue
        feat = registry.get("feat", feat_id)
        lines.append(f"  {feat.name} — пассивно")
        if feat.description:
            lines += description_lines(feat.description, width)
    return lines
