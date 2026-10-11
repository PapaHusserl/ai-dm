from importlib import resources

from ai_dm.content.models.common import ABILITIES, SKILLS
from ai_dm.llm.types import ChatRequest, Message, SystemBlock, Text, ToolSpec
from ai_dm.master.prompt import dump
from ai_dm.protocol.schema import tool_set
from ai_dm.rules.builder import (
    BACKGROUND_BUDGET_CP,
    BACKGROUND_DESCRIPTION_MAX,
    MEANS_ITEM_MAX,
    MEANS_MAX,
    MOTIVE_MAX,
    OPPORTUNITY_MAX,
    OPPORTUNITY_THEN_MAX,
    feat_choice_count,
    species_choice_keys,
)
from ai_dm.rules.hero_options import (
    class_spells,
    fighting_styles,
    has_fighting_style,
    mastery_weapons,
)


def kit_data(kit):
    return {"id": kit.id, "items": kit.items, "equip": kit.equip, "gold_cp": kit.gold_cp}


def spellcasting_data(char_class):
    casting = char_class.spellcasting
    if casting is None:
        return None
    return {"cantrips": casting.cantrips, "spells": casting.spells, "prepared": casting.prepared}


def class_data(registry, char_class):
    # справочник класса для листа героя: навыки, мастерство, стиль, наборы, заклинания 1 круга
    weapons = mastery_weapons(registry, char_class)
    styles = [f.id for f in fighting_styles(registry)]
    has_style = has_fighting_style(char_class)
    return {
        "id": char_class.id, "name": char_class.name,
        "skill_options": char_class.skill_choices.options,
        "skill_count": char_class.skill_choices.count,
        "mastery_count": char_class.weapon_mastery_count,
        "mastery_weapon_ids": [w.id for w in weapons],
        "fighting_style": has_style, "fighting_style_ids": styles if has_style else [],
        "kits": [kit_data(k) for k in char_class.starting_kits],
        "spellcasting": spellcasting_data(char_class),
        "cantrip_ids": [s.id for s in class_spells(registry, char_class.id, 0)],
        "spell_ids": [s.id for s in class_spells(registry, char_class.id, 1)],
    }


class HeroPromptBuilder:
    # запрос создания героя (роль narrator): system[0] -- правила, system[1] -- справочник
    # (оба в кэш), messages[0] -- вход игрока; режимы hero_background и hero_sheet
    def __init__(self, app_cfg, *, model=None):
        self.app_cfg = app_cfg
        self.role = "narrator"
        self.role_cfg = self.find_role_cfg(model)
        self.model = model or self.role_cfg.model
        prompts = resources.files("ai_dm.master") / "prompts"
        self.rules = (prompts / "background_rules.md").read_text(encoding="utf-8")
        self.sheet_rules = (prompts / "hero_sheet_rules.md").read_text(encoding="utf-8")

    def find_role_cfg(self, model):
        default = self.app_cfg.roles.narrator
        if model is None:
            return default
        candidates = [default, self.app_cfg.alternatives.narrator]
        candidates += [profile.narrator for profile in self.app_cfg.profiles.values()]
        for candidate in candidates:
            if candidate.model == model:
                return candidate
        return default

    def build(self, ctx, user_input, mode, *, world_text=""):
        # world_text не используется: интерфейс общий с PromptBuilder
        tools = [ToolSpec.model_validate(d) for d in tool_set(mode)]
        task = ctx.task
        if mode == "hero_sheet":
            rules = self.sheet_rules
            reference = self.sheet_reference_block(ctx)
            data = {
                "description": user_input, "feedback": task.feedback, "previous": task.previous,
            }
        else:
            rules = self.rules
            reference = self.reference_block(ctx)
            data = {
                "class": task.class_id, "class_skills": list(task.class_skills),
                "description": user_input,
            }
        system = [SystemBlock(text=rules, cache=True), SystemBlock(text=reference, cache=True)]
        return ChatRequest(
            role="narrator", model=self.model, system=system, tools=tools,
            messages=[Message(role="user", content=[Text(text=dump(data))], cache=True)],
            max_tokens=self.role_cfg.max_tokens, effort=self.role_cfg.effort,
        )

    def reference_block(self, ctx):
        return dump(self.reference_data(ctx))

    def sheet_reference_block(self, ctx):
        # справочник листа: предыстория + классы, виды, черты, таблицы, мир, пределы
        registry = ctx.registry
        task = ctx.task
        data = self.reference_data(ctx)
        data["classes"] = [class_data(registry, c) for c in registry.all("class")]
        data["species"] = [
            {"id": sp.id, "name": sp.name, "choices": species_choice_keys(sp, registry)}
            for sp in registry.all("species")
        ]
        data["origin_feats"] = [
            {"id": f.id, "picks": feat_choice_count(f)}
            for f in registry.all("feat") if f.category == "origin"
        ]
        point_buy = registry.get("table", "point_buy").rows
        data["standard_array"] = sorted(registry.get("table", "standard_array").rows.values())
        data["point_buy"] = {
            "cost": {k: v for k, v in point_buy.items() if k != "budget"},
            "budget": point_buy["budget"],
        }
        data["explicit"] = {"min": 3, "max": 20}
        data["world"] = {
            "npc_ids": sorted(task.known.npcs), "location_ids": sorted(task.known.locations),
            "god_ids": sorted(task.known.pantheon), "taken_names": sorted(task.taken_names),
        }
        data["limits"] = {
            "motive_max": MOTIVE_MAX, "means_max": MEANS_MAX, "means_item_max": MEANS_ITEM_MAX,
            "opportunity_max": OPPORTUNITY_MAX, "opportunity_then_max": OPPORTUNITY_THEN_MAX,
            "background_description_max": BACKGROUND_DESCRIPTION_MAX,
            "background_budget_cp": BACKGROUND_BUDGET_CP,
        }
        return dump(data)

    def reference_data(self, ctx):
        registry = ctx.registry
        items = [i for i in registry.all("item") if i.source != "world"]
        gear = [
            i for kind in ("weapon", "armor", "item") for i in registry.all(kind)
            if i.source != "world"
        ]
        data = {
            "examples": [
                {
                    "name": b.name, "abilities": b.abilities, "skills": b.skills, "tool": b.tool,
                    "feat": b.feat, "equipment": b.equipment, "gold_cp": b.gold_cp,
                }
                for b in registry.all("background")
            ],
            "origin_feat_ids": [f.id for f in registry.all("feat") if f.category == "origin"],
            "tool_ids": [i.id for i in items if i.tool],
            "item_ids": {i.id: i.cost_cp for i in gear},
            "abilities": list(ABILITIES),
            "skills": sorted(SKILLS),
            "budget_cp": BACKGROUND_BUDGET_CP,
        }
        return data
