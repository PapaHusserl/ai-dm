from importlib import resources
from typing import get_args

from ai_dm.core.clock import default_calendar
from ai_dm.llm.types import ChatRequest, Message, SystemBlock, Text, ToolSpec
from ai_dm.master.prompt import dump
from ai_dm.protocol.requests import IMPORT_MODE, tone_axis
from ai_dm.protocol.schema import tool_set

# виды условия триггера и секрета (как HeroTriggerSpec.kind) с подписью
CONDITION_KINDS = {
    "narrative": "ref -- текст условия словами",
    "flag": "ref -- имя флага",
    "hero_has": "ref -- id предмета из item_ids",
    "hero_at": "ref -- id своей локации",
    "npc_status": "ref -- id своего NPC, status -- нужный статус",
    "attitude": "ref -- id своего NPC, gte -- порог больше нуля",
    "favor": "ref -- id своего бога, gte -- порог больше нуля",
}


class ImportPromptBuilder:
    # запрос import пака (роль import): system[0] -- правила, system[1] -- справочник
    # (оба в кэш), messages[0] -- id кампании и текстовая выжимка
    def __init__(self, app_cfg, *, model=None):
        self.app_cfg = app_cfg
        self.role = "import"
        self.role_cfg = self.find_role_cfg(model)
        self.model = model or self.role_cfg.model
        prompts = resources.files("ai_dm.master") / "prompts"
        self.rules = (prompts / "import_rules.md").read_text(encoding="utf-8")

    def find_role_cfg(self, model):
        default = self.app_cfg.roles.import_
        if model is None:
            return default
        candidates = [default] + [profile.import_ for profile in self.app_cfg.profiles.values()]
        for candidate in candidates:
            if candidate is not None and candidate.model == model:
                return candidate
        return default

    def build(self, ctx, user_input, mode, *, world_text=""):
        # world_text не используется: интерфейс общий с PromptBuilder
        tools = [ToolSpec.model_validate(d) for d in tool_set(IMPORT_MODE)]
        data = {"campaign_id": ctx.task.campaign_id, "summary": user_input}
        # cache: повторы после pack_invalid в той же сессии читают префикс из кэша
        system = [
            SystemBlock(text=self.rules, cache=True),
            SystemBlock(text=self.reference_block(ctx), cache=True),
        ]
        return ChatRequest(
            role="import", model=self.model, system=system, tools=tools,
            messages=[Message(role="user", content=[Text(text=dump(data))], cache=True)],
            max_tokens=self.role_cfg.max_tokens, effort=self.role_cfg.effort,
        )

    def reference_block(self, ctx):
        registry = ctx.registry
        items = registry.all("item")
        axes = {
            name: list(get_args(tone_axis(name)))
            for name in ("violence", "horror", "romance", "language")
        }
        calendar = default_calendar()
        data = {
            "species_ids": sorted(sp.id for sp in registry.all("species")),
            "item_ids": sorted(i.id for i in items),
            "trade_kinds": sorted(ctx.cfg.trade.presets),
            "condition_kinds": CONDITION_KINDS,
            "tone_axes": axes,
            "calendar": {
                "months": len(calendar.months), "days_per_month": calendar.months[0].days,
                "date": "YYYY-MM-DD", "time": "HH:MM",
            },
            "limits": {"means_min": 1, "means_max": 3},
            "required": {"locations_min": 1, "hero_location": "id одной из своих локаций"},
        }
        return dump(data)
