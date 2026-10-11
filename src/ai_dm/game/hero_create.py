import json
from dataclasses import dataclass
from types import SimpleNamespace

from ai_dm.campaign.build import apply_hooks
from ai_dm.content.models.common import ABILITIES
from ai_dm.game.commands import ac_text, calls_cost_line, equipment_text
from ai_dm.game.sheet_text import (
    fit,
    hooks_lines,
    inv_lines,
    rows,
    sheet_stat_lines,
    slots_lines,
    spell_names,
    title_line,
)
from ai_dm.master.hero import HeroPromptBuilder
from ai_dm.master.session import MasterSession
from ai_dm.persistence.store import write_text
from ai_dm.protocol.apply import apply
from ai_dm.protocol.context import CreationContext
from ai_dm.rules.builder import HeroSheet, build_character, origin_feat_keys
from ai_dm.rules.derived import armor_class
from ai_dm.rules.money import format_cp


@dataclass
class HeroCreateDeps:
    # зависимости создания героя; adapter_factory -- смена модели в меню 2.2 (Б1б)
    adapter: object
    app_cfg: object
    registry: object
    cfg: object
    journal: object = None
    ledger: object = None
    now: object = None
    model: object = None
    adapter_factory: object = None


def run_creation(deps, task, description, run_id):
    # общий прогон создания героя; сбои -- TurnFailed наверх (меню 2.2 у вызывающего)
    ctx = CreationContext(deps.registry, deps.cfg, task)
    session = MasterSession(
        deps.adapter, deps.app_cfg, journal=deps.journal, ledger=deps.ledger, run_id=run_id,
        now=deps.now, role="narrator", builder=HeroPromptBuilder(deps.app_cfg, model=deps.model),
    )
    session.run(ctx, description, apply, task.mode, run_id=run_id)
    return ctx


def propose_background(deps, task, description, run_id):
    # предыстория по описанию игрока (режим hero_background, пошаговый путь Б2)
    return run_creation(deps, task, description, run_id).background


def propose_hero_sheet(deps, task, description, run_id) -> HeroSheet:
    # лист героя по описанию игрока
    return run_creation(deps, task, description, run_id).sheet


def preview_lines(sheet, registry, width) -> list[str]:
    # показ листа «как /sheet»; лист уже прошёл sheet_check
    hero = build_character(sheet.choices, registry)
    apply_hooks(hero, sheet)
    lines = [
        title_line(hero, registry),
        f"HP {hero.creature.hp_current}/{hero.creature.hp_max}, "
        f"КД {armor_class(hero, registry, 0)}",
        ac_text(hero, registry, 0),
    ]
    equipment = equipment_text(hero, registry)
    lines += rows("Экипировка:", equipment[len("Экипировка: "):].split("; "), width, "; ")
    lines += sheet_stat_lines(hero, registry, width)
    if registry.get("class", hero.sheet.class_id).spellcasting is not None:
        slots = "; ".join(slots_lines(hero, registry))
        lines.append(f"Заклинания (ячейки {slots}): " + ", ".join(spell_names(hero, registry)))
    lines += inv_lines(hero, registry, format_cp(hero.money_cp))
    lines += hooks_lines(hero)
    return fit(lines, width)


def split_list(value) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def scalar_field(path):
    def put(data, value):
        node = data
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value

    def get(data):
        node = data
        for key in path:
            node = node[key]
        return "" if node is None else str(node)

    return put, get


def list_field(path):
    put_scalar, _ = scalar_field(path)

    def put(data, value):
        put_scalar(data, split_list(value))

    def get(data):
        node = data
        for key in path:
            node = node[key]
        return ", ".join(node)

    return put, get


def number_field(path):
    put_scalar, get_scalar = scalar_field(path)

    def put(data, value):
        if not value.lstrip("-").isdigit():
            raise ValueError(f"нужно целое число, получено: {value!r}")
        put_scalar(data, int(value))

    return put, get_scalar


def free_background(data):
    # правка предыстории возможна только у свободной (словарь), не у id из справочника
    background = data["choices"]["background"]
    if not isinstance(background, dict):
        raise ValueError("предыстория задана id справочника: поля bg_* недоступны")
    return background


def background_field(key, kind):
    maker = {"text": scalar_field, "list": list_field, "number": number_field}[kind]
    put_inner, get_inner = maker(("background", key))

    def put(data, value):
        free_background(data)
        put_inner(data["choices"], value)

    def get(data):
        free_background(data)
        return get_inner(data["choices"])

    return put, get


def put_bonus(data, value):
    bonus = {}
    for part in split_list(value):
        ability, sign, number = part.partition("+")
        if not sign or not number.isdigit():
            raise ValueError(f"бонус: формат «str+2, con+1», получено: {part!r}")
        bonus[ability.strip()] = int(number)
    data["choices"]["background_bonus"] = bonus


def get_bonus(data):
    return ", ".join(f"{a}+{n}" for a, n in data["choices"]["background_bonus"].items())


def put_style(data, value):
    data["choices"]["fighting_style"] = value or None


def get_style(data):
    return data["choices"]["fighting_style"] or ""


def species_field(key):
    def put(data, value):
        choices = data["choices"]["species_choices"]
        if value in ("", "none"):
            choices.pop(key, None)
        else:
            choices[key] = value

    def get(data):
        return data["choices"]["species_choices"].get(key, "")

    return put, get


def feat_key(data, index):
    # ключ feat_choices: 0 -- черта предыстории, 1 -- черта вида (Универсальность)
    choices = data["choices"]
    spec = SimpleNamespace(feat=free_background(data)["feat"])
    keys = origin_feat_keys(spec, choices["species_choices"])
    if index >= len(keys):
        raise ValueError("у вида нет выбора черты (species_feat)")
    return keys[index][0]


def feat_skills_field(index):
    def put(data, value):
        picks = split_list(value)
        key = feat_key(data, index)
        if picks:
            data["choices"]["feat_choices"][key] = picks
        else:
            data["choices"]["feat_choices"].pop(key, None)

    def get(data):
        return ", ".join(data["choices"]["feat_choices"].get(feat_key(data, index), []))

    return put, get


def put_opportunity(data, value):
    # пусто -- очистить; «id: условие словами -> намерение» -- narrative-триггер
    if not value:
        data["opportunity"] = []
        return
    head, arrow, then = value.partition("->")
    trigger_id, colon, condition = head.partition(":")
    if not arrow or not colon or not trigger_id.strip() or not condition.strip():
        raise ValueError("возможность: формат «id: условие словами -> намерение»")
    data["opportunity"] = [
        {"id": trigger_id.strip(), "if": {"narrative": condition.strip()},
         "then": then.strip(), "once": True}
    ]


def get_opportunity(data):
    text = "; ".join(f"{t['id']} -> {t['then']}" for t in data["opportunity"])
    return f"{text} (правка заменяет весь список)"


# поле правки -> (запись в словарь листа, чтение для подсказки)
SHEET_FIELDS = {
    "name": scalar_field(("choices", "name")),
    "species": scalar_field(("choices", "species_id")),
    "class": scalar_field(("choices", "class_id")),
    "method": scalar_field(("choices", "ability_method")),
    **{a: number_field(("choices", "ability_scores", a)) for a in ABILITIES},
    "bonus": (put_bonus, get_bonus),
    "class_skills": list_field(("choices", "class_skills")),
    "masteries": list_field(("choices", "weapon_masteries")),
    "style": (put_style, get_style),
    "kit": scalar_field(("choices", "class_kit")),
    "spells": list_field(("choices", "spells")),
    "prepared": list_field(("choices", "prepared")),
    "species_skill": species_field("skill"),
    "species_feat": species_field("feat"),
    "feat_skills": feat_skills_field(0),
    "species_feat_skills": feat_skills_field(1),
    "gear": scalar_field(("choices", "background_gear")),
    "bg_name": background_field("name", "text"),
    "bg_abilities": background_field("abilities", "list"),
    "bg_skills": background_field("skills", "list"),
    "bg_tool": background_field("tool", "text"),
    "bg_feat": background_field("feat", "text"),
    "bg_equipment": background_field("equipment", "list"),
    "bg_gold": background_field("gold_cp", "number"),
    "bg_description": background_field("description", "text"),
    "motive": scalar_field(("motive",)),
    "means": list_field(("means",)),
    "opportunity": (put_opportunity, get_opportunity),
}


def edit_sheet(sheet, line) -> HeroSheet | str:
    # ручная правка «поле = значение»: новый лист или текст ошибки; содержимое проверяет sheet_check
    name, sep, value = line.partition("=")
    key = name.strip().lower()
    if not sep or key not in SHEET_FIELDS:
        return "Неизвестное поле. Поля: " + ", ".join(SHEET_FIELDS)
    data = sheet.model_dump(mode="json", by_alias=True)
    try:
        SHEET_FIELDS[key][0](data, value.strip())
        return HeroSheet.model_validate(data)
    except (ValueError, KeyError, TypeError) as err:
        return str(err)


def sheet_fields_lines(sheet) -> list[str]:
    # «поле = значение» для подсказки при правке
    data = sheet.model_dump(mode="json", by_alias=True)
    lines = []
    for key, (_, get) in SHEET_FIELDS.items():
        try:
            lines.append(f"{key} = {get(data)}")
        except (ValueError, KeyError, TypeError):
            lines.append(f"{key} = —")
    return lines


def sheet_path(saves_root, world_id):
    return saves_root / world_id / "meta" / "hero_sheet.json"


def write_hero_sheet(saves_root, world_id, sheet) -> None:
    text = json.dumps(sheet.model_dump(mode="json", by_alias=True), ensure_ascii=False, indent=2)
    write_text(sheet_path(saves_root, world_id), text)


def read_hero_sheet(saves_root, world_id) -> HeroSheet | None:
    path = sheet_path(saves_root, world_id)
    if not path.is_file():
        return None
    return HeroSheet.model_validate_json(path.read_text(encoding="utf-8"))


def creation_cost_line(journal, run_ids) -> str:
    return calls_cost_line(journal, run_ids, "Создание героя")
