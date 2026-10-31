from ai_dm.content.models.common import SKILLS
from ai_dm.rules.derived import weapon_proficient
from ai_dm.rules.inventory import find_item
from ai_dm.rules.money import format_cp
from ai_dm.rules.names import SKILL_NAMES

# допустимые множества создания героя: один источник для справочника модели и шагов мастера


def species_options(registry):
    return registry.all("species")


def class_options(registry):
    return registry.all("class")


def background_options(registry):
    return registry.all("background")


def class_skill_options(char_class, taken) -> list[str]:
    return [s for s in char_class.skill_choices.options if s not in taken]


def mastery_weapons(registry, char_class):
    # оружие с мастерством, которым класс владеет; огнестрел (world_only) при создании не выбирается
    return [
        w for w in registry.all("weapon")
        if w.source != "world" and not w.world_only and w.mastery is not None
        and weapon_proficient(char_class, w)
    ]


def has_fighting_style(char_class) -> bool:
    return any(r.feature == "fighting_style" and r.level <= 1 for r in char_class.features)


def fighting_styles(registry):
    return [f for f in registry.all("feat") if f.category == "fighting_style"]


def class_spells(registry, class_id, level):
    return [s for s in registry.all("spell") if class_id in s.classes and s.level == level]


def spell_counts(char_class) -> tuple[int, int, int]:
    # (заговоры, заклинания 1 круга, подготовленные); None или нет заклинаний -- 0
    casting = char_class.spellcasting
    if casting is None:
        return 0, 0, 0
    return casting.cantrips or 0, casting.spells or 0, casting.prepared or 0


def origin_feats(registry, exclude_feat):
    # черты происхождения; черта предыстории не повторяется, если она не repeatable
    feats = [f for f in registry.all("feat") if f.category == "origin"]
    return [f for f in feats if f.id != exclude_feat or f.repeatable]


def feat_pick_options(registry, taken_skills, taken_tools) -> list[tuple[str, str]]:
    # (id, подпись): навыки и инструменты, которые ещё не освоены
    picks = [(s, SKILL_NAMES[s]) for s in SKILLS if s not in taken_skills]
    tools = [i for i in registry.all("item") if i.tool and i.id not in taken_tools]
    return picks + [(i.id, i.name) for i in tools]


def species_skill_options(taken_skills) -> list[str]:
    return [s for s in SKILLS if s not in taken_skills]


def standard_array(registry) -> list[int]:
    return sorted(registry.get("table", "standard_array").rows.values(), reverse=True)


def point_buy_table(registry):
    # ({значение: очки}, бюджет)
    rows = registry.get("table", "point_buy").rows
    return {int(k): v for k, v in rows.items() if k != "budget"}, rows["budget"]


def kit_options(char_class):
    return list(char_class.starting_kits)


def item_name(registry, item_id) -> str:
    found = find_item(registry, item_id)
    return item_id if found is None else found[1].name


def kit_label(registry, kit) -> str:
    counts = {}
    for item_id in kit.items:
        counts[item_id] = counts.get(item_id, 0) + 1
    names = []
    for item_id, count in counts.items():
        name = item_name(registry, item_id)
        names.append(name if count == 1 else f"{name} ×{count}")
    label = ", ".join(names)
    if not kit.gold_cp:
        return label
    if not label:
        return f"{format_cp(kit.gold_cp)} золотом"
    return f"{label}; +{format_cp(kit.gold_cp)}"
