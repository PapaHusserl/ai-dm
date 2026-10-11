import time
from datetime import UTC, datetime
from importlib import resources

from ai_dm.core.rng import Rng
from ai_dm.llm.types import ChatRequest, Message, SystemBlock, Text, ToolSpec
from ai_dm.master.prompt import dump
from ai_dm.master.relevance import relevant_npcs
from ai_dm.master.session import MasterSession
from ai_dm.protocol.apply import apply
from ai_dm.protocol.context import TurnContext
from ai_dm.protocol.schema import tool_set
from ai_dm.rules.triggers_eval import event_active


class WorldPromptBuilder:
    # запрос роли world: system[0] -- правила, system[1] -- мир (оба в кэш), messages[0] -- вызов
    def __init__(self, app_cfg, candidates, *, model=None):
        self.app_cfg = app_cfg
        self.candidates = list(candidates)
        self.role = "world"
        self.role_cfg = self.find_role_cfg(model)
        self.model = model or self.role_cfg.model
        self.rules = (resources.files("ai_dm.master") / "prompts" / "world_rules.md").read_text(
            encoding="utf-8"
        )

    def find_role_cfg(self, model):
        default = self.app_cfg.roles.world
        if model is None:
            return default
        for candidate in [default] + [p.world for p in self.app_cfg.profiles.values()]:
            if candidate.model == model:
                return candidate
        return default

    def build(self, ctx, user_input, mode, *, world_text=""):
        # user_input и world_text не используются: интерфейс общий с PromptBuilder, вход вызова
        # (кандидаты) и текст мира берутся из ctx и самого builder
        tools = [ToolSpec.model_validate(d) for d in tool_set(mode)]
        system = [
            SystemBlock(text=self.rules, cache=True),
            SystemBlock(text=self.world_block(ctx), cache=True),
        ]
        # messages[0] с cache=True -- осознанно (повтор в раундах вызова)
        text = dump(self.state_data(ctx))
        return ChatRequest(
            role="world", model=self.model, system=system, tools=tools,
            messages=[Message(role="user", content=[Text(text=text)], cache=True)],
            max_tokens=self.role_cfg.max_tokens, effort=self.role_cfg.effort,
        )

    def world_block(self, ctx):
        world = ctx.bundle.world
        gods = [
            {"id": g.id, "name": g.name, "domains": g.domains, "role": g.role, "motive": g.motive}
            for g in sorted(world.pantheon.values(), key=lambda g: g.id)
        ]
        data = {
            "world_id": world.world_id,
            "tone": world.tone.model_dump(mode="json"),
            "world_text": world.lore.world_text,
            "truths": world.lore.truths,
            "pantheon": gods,
        }
        return dump(data)

    def candidate_data(self, c):
        return {
            "ref": c.ref,
            "kind": c.kind,
            "owner": {"id": c.owner_id, "kind": c.owner_kind, "name": c.owner_name,
                      "motive": c.motive, "means": c.means},
            "condition_text": c.condition_text,
            "then": c.then,
            "residual": None if c.residual is None else c.residual.model_dump(mode="json"),
        }

    def state_data(self, ctx):
        bundle = ctx.bundle
        world = bundle.world
        now_s = world.clock.now_s
        scene = bundle.session.current_scene
        hero = ctx.hero
        npcs = []
        place_ids = {hero.location_id}
        if scene is not None:
            place_ids.add(scene.location_id)
        for npc_id in relevant_npcs(bundle):
            n = world.npcs[npc_id]
            npcs.append(
                {"id": n.id, "name": n.name, "location_id": n.location_id, "key": n.key,
                 "attitude": n.attitude}
            )
            place_ids.add(n.location_id)
        locations = [
            {"id": p.id, "name": p.name, "parent_id": p.parent_id}
            for p in sorted(world.locations.values(), key=lambda p: p.id)
            if p.id in place_ids
        ]
        events = [
            {"id": e.id, "type": e.type, "regions": e.regions, "kind": e.kind, "cause": e.cause}
            for e in world.events if event_active(e, now_s)
        ]
        closed = None
        if scene is not None:
            closed = {
                "id": scene.id, "title": scene.title, "summary": scene.summary,
                "location_id": scene.location_id, "closed_reason": scene.closed_reason,
            }
        holiday = world.clock.holiday()
        return {
            "time": {
                "date": world.clock.to_date(), "now_s": now_s, "season": world.clock.season(),
                "holiday": None if holiday is None else holiday.name,
            },
            "closed_scene": closed,
            "hero": {"id": hero.id, "name": hero.name, "location_id": hero.location_id},
            "candidates": [self.candidate_data(c) for c in self.candidates],
            "npcs": npcs,
            "locations": locations,
            "location_ids": sorted(world.locations),
            "events": events,
            "dangers": [d.model_dump(mode="json") for d in world.dangers],
        }


class WorldSession:
    """Роль world: один пакетный вызов на границе сцены поверх цикла MasterSession.

    adapter -- адаптер роли world; model -- id его модели (по умолчанию roles.world);
    кандидаты -- объекты с полями ref, kind, owner_*, motive, means, condition_text, then, residual
    (их готовит game из world_sim; сам слой master world_sim не знает).
    """

    def __init__(
        self, adapter, app_cfg, *, journal=None, ledger=None, sleeper=time.sleep, now=None,
        model=None, call_numbers=None,
    ):
        self.adapter = adapter
        self.app_cfg = app_cfg
        self.journal = journal
        self.ledger = ledger
        self.sleeper = sleeper
        self.now = now or (lambda: datetime.now(UTC))
        self.model = model
        self.call_numbers = call_numbers

    @property
    def max_calls_per_day(self) -> int:
        return self.app_cfg.world.max_calls_per_day

    def run(self, bundle, registry, cfg, candidates, run_id) -> TurnContext:
        # bundle -- рабочая копия границы; результат -- контекст с вердиктами и заметками
        rng = Rng.from_state(bundle.world.rng)
        ctx = TurnContext(bundle, registry, cfg, rng, mode="world")
        ctx.candidate_refs = [c.ref for c in candidates]
        ctx.verdict_refs = [c.ref for c in candidates if c.kind == "verdict"]
        session = MasterSession(
            self.adapter, self.app_cfg, journal=self.journal, ledger=self.ledger, run_id=run_id,
            sleeper=self.sleeper, now=self.now, role="world", call_numbers=self.call_numbers,
            builder=WorldPromptBuilder(self.app_cfg, candidates, model=self.model),
        )
        session.run(ctx, "", apply, "world", run_id=run_id)
        bundle.world.rng = rng.state
        return ctx
