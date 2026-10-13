import copy

from ai_dm.protocol.requests import (
    HERO_MODELS,
    HERO_MODES,
    IMPORT_MODE,
    IMPORT_MODELS,
    REQUEST_MODELS,
    SUMMARY_MODELS,
    WORLD_MODELS,
)

# ключи, которые strict-режим не принимает или которые не нужны модели
DROPPED = ("title", "default", "$defs")

# наборы инструментов по режимам хода (каждый не больше 16 strict-инструментов)
MODE_TOOLS = {
    "explore": (
        "skill_check", "saving_throw", "start_combat", "damage", "give_item", "give_custom_item",
        "use_item", "cast_spell", "take_item", "trade", "haggle", "gold", "award_xp",
        "advance_time", "rest", "set_flag", "npc_create", "location_create", "npc_update",
        "favor_change", "pray", "companion_update",
        "offer_choices", "end_scene", "end_chapter", "reveal_secret", "event_start", "event_end",
        "warn_danger", "unsupported_action",
    ),
    "combat_classify": ("player_action", "unsupported_action"),
    "combat_narrate": ("offer_choices", "end_combat", "defeat_outcome"),
    "npc_choice": ("npc_action",),
    # закрытый набор закадровых запросов роли world (STAGE3-PLAN A4)
    "world": (
        "world_verdict", "world_notice", "skill_check", "saving_throw", "set_flag", "npc_create",
        "location_create", "npc_update", "favor_change", "event_start", "event_end", "warn_danger",
    ),
    # служебный набор роли summarizer: выжимка закрытой сцены
    "summarize_scene": ("scene_summary",),
    # свёртка закрытой главы: оба инструмента в одном ответе
    "summarize_chapter": ("chapter_summary", "game_summary"),
    # свободная предыстория героя (создание героя, Б0)
    "hero_background": ("background_spec",),
    # лист героя на лету: один инструмент, предыстория вложена (Б1)
    "hero_sheet": ("hero_sheet",),
    # пак кампании по текстовой выжимке: один инструмент pack (Б3)
    IMPORT_MODE: ("pack",),
}

# редкие инструменты в режиме без strict: форму всё равно проверяет Pydantic
# strict-грамматика Anthropic имеет внутренний предел размера («compiled grammar is too large»):
# в explore строгими остаются только малые частые инструменты, крупные схемы — без strict
# (их всё равно валидирует Pydantic; невалидный ответ → повтор с пояснением).
STRICT_IN_EXPLORE = (
    "skill_check", "saving_throw", "damage", "advance_time", "offer_choices", "unsupported_action",
)
NON_STRICT = {
    "explore": tuple(name for name in MODE_TOOLS["explore"] if name not in STRICT_IN_EXPLORE),
    "world": (
        "npc_create", "location_create", "npc_update", "favor_change", "event_start", "event_end",
        "warn_danger",
    ),
}

# группа кэша схем режимов со своими версиями запросов (кроме героя и summarizer)
TOOL_GROUPS = {"world": "world", IMPORT_MODE: "import"}

_cache = {}


def strictify(node, defs):
    # Pydantic-схема -> strict: инлайн $ref, все свойства required, const -> enum
    if isinstance(node, list):
        return [strictify(item, defs) for item in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        merged = dict(defs[node["$ref"].split("/")[-1]])
        merged.update({key: value for key, value in node.items() if key != "$ref"})
        return strictify(merged, defs)
    result = {}
    for key, value in node.items():
        if key in DROPPED:
            continue
        if key == "const":
            result["enum"] = [value]
        elif key == "properties":
            result["properties"] = {name: strictify(sub, defs) for name, sub in value.items()}
        else:
            result[key] = strictify(value, defs)
    if "properties" in result:
        result["required"] = list(result["properties"])
        result["additionalProperties"] = False
    return result


def own_models(mode) -> dict:
    # своя версия запроса у режима: закадровые (world) и служебные (summarize_*)
    if mode == "world":
        return WORLD_MODELS
    if mode.startswith("summarize_"):
        return SUMMARY_MODELS
    if mode in HERO_MODES:
        return HERO_MODELS[mode]
    if mode == IMPORT_MODE:
        return IMPORT_MODELS
    return {}


def model_for(name, mode):
    own = own_models(mode)
    if name in own:
        return own[name]
    return REQUEST_MODELS[name]


def build_tool(name, mode="explore"):
    model = model_for(name, mode)
    raw = model.model_json_schema()
    schema = strictify(raw, raw.get("$defs", {}))
    description = schema.pop("description")
    return {"name": name, "description": description, "strict": True, "input_schema": schema}


def tool_defs(exposed, mode="explore") -> list[dict]:
    names = sorted(set(exposed))
    for name in names:
        if name not in REQUEST_MODELS and name not in own_models(mode):
            raise ValueError(f"неизвестный запрос: {name!r}")
    tools = []
    for name in names:
        # свой вариант схемы у запроса только в режимах с own_models; ключ -- группа режимов
        group = ""
        if name in own_models(mode):
            group = "hero" if mode in HERO_MODES else TOOL_GROUPS.get(mode, "summarize")
        if (name, group) not in _cache:
            _cache[(name, group)] = build_tool(name, mode)
        tools.append(copy.deepcopy(_cache[(name, group)]))
    return tools


def tool_set(mode) -> list[dict]:
    if mode not in MODE_TOOLS:
        raise ValueError(f"неизвестный режим: {mode!r}")
    tools = tool_defs(MODE_TOOLS[mode], mode)
    for tool in tools:
        if tool["name"] in NON_STRICT.get(mode, ()):
            tool["strict"] = False
    return tools
