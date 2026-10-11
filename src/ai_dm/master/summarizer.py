import time
from datetime import UTC, datetime
from importlib import resources

from ai_dm.llm.types import ChatRequest, Message, SystemBlock, Text, ToolSpec
from ai_dm.master.prompt import dump
from ai_dm.master.session import MasterSession
from ai_dm.protocol.apply import apply
from ai_dm.protocol.context import TurnContext
from ai_dm.protocol.schema import tool_set


def scene_turns(bundle, scene):
    # ходы закрытой сцены: recent_turns с scene_id
    turns = [t for t in bundle.memory.recent_turns if t.scene_id == scene.id]
    if not turns and scene.player_turns > 0:
        # сейв до v5: у ходов нет scene_id, берём последние player_turns ходов без него
        old = [t for t in bundle.memory.recent_turns if t.scene_id == ""]
        turns = old[-scene.player_turns:]
    return turns


class SummarizerPromptBuilder:
    # запрос роли summarizer: system[0] -- правила, system[1] -- мир (оба в кэш),
    # messages[0] -- вход сцены
    def __init__(self, app_cfg, *, model=None):
        self.app_cfg = app_cfg
        self.role = "summarizer"
        self.role_cfg = self.find_role_cfg(model)
        self.model = model or self.role_cfg.model
        self.rules = (
            resources.files("ai_dm.master") / "prompts" / "summarizer_rules.md"
        ).read_text(encoding="utf-8")

    def find_role_cfg(self, model):
        default = self.app_cfg.roles.summarizer
        if model is None:
            return default
        for candidate in [default] + [p.summarizer for p in self.app_cfg.profiles.values()]:
            if candidate.model == model:
                return candidate
        return default

    def build(self, ctx, user_input, mode, *, world_text=""):
        # user_input и world_text не используются: интерфейс общий с PromptBuilder
        tools = [ToolSpec.model_validate(d) for d in tool_set(mode)]
        system = [
            SystemBlock(text=self.rules, cache=True),
            SystemBlock(text=self.world_block(ctx), cache=True),
        ]
        if mode == "summarize_chapter":
            text = dump(self.chapter_data(ctx))
        else:
            text = dump(self.state_data(ctx))
        return ChatRequest(
            role="summarizer", model=self.model, system=system, tools=tools,
            messages=[Message(role="user", content=[Text(text=text)], cache=True)],
            max_tokens=self.role_cfg.max_tokens, effort=self.role_cfg.effort,
        )

    def world_block(self, ctx):
        world = ctx.bundle.world
        data = {
            "world_id": world.world_id,
            "tone": world.tone.model_dump(mode="json"),
        }
        return dump(data)

    def chapter_data(self, ctx):
        # вход свёртки главы: выжимки сцен главы, прежний game_summary, номер и название главы
        bundle = ctx.bundle
        chapter = bundle.session.current_chapter
        scenes = [
            {"id": s.id, "title": s.title, "summary": s.summary}
            for s in bundle.memory.scenes if s.chapter_id == chapter.id
        ]
        return {
            "chapter": {
                "number": chapter.number, "title": chapter.title,
                "closed_reason": chapter.closed_reason, "date": bundle.world.clock.to_date(),
            },
            "scenes": scenes,
            "game_summary": bundle.memory.game_summary,
            "hero_name": ctx.hero.name,
            "chapter_limit": self.app_cfg.memory.chapter_summary_max,
            "game_limit": self.app_cfg.memory.game_summary_max,
        }

    def state_data(self, ctx):
        bundle = ctx.bundle
        world = bundle.world
        scene = bundle.session.current_scene
        place = world.locations.get(scene.location_id)
        scene_list = scene_turns(bundle, scene)
        # только известное герою: упомянутые в ходах сцены, из локации сцены, с известными
        # секретами, идущие с героем; мёртвые тоже -- их смерть может быть в сцене
        text = "\n".join(t.player_input + "\n" + t.narration for t in scene_list).lower()
        npcs = []
        for n in sorted(world.npcs.values(), key=lambda n: n.id):
            if not n.named:
                continue
            here = scene.location_id is not None and n.location_id == scene.location_id
            said = n.name != "" and n.name.lower() in text
            with_hero = n.follows is not None and n.follows == bundle.manifest.current_hero_id
            if n.known_to_player or here or said or with_hero:
                npcs.append({"id": n.id, "name": n.name})
        # посещённые локации и локация сцены
        locations = [
            {"id": p.id, "name": p.name}
            for p in sorted(world.locations.values(), key=lambda p: p.id)
            if p.visited or p.id == scene.location_id
        ]
        turns = [
            {
                "turn_seq": t.turn_seq, "player_input": t.player_input, "narration": t.narration,
                "requests": t.requests, "rolls": t.rolls,
            }
            for t in scene_list
        ]
        return {
            "scene": {
                "id": scene.id, "closed_reason": scene.closed_reason,
                "location": None if place is None else place.name,
                "date": world.clock.to_date(),
            },
            "hint": {"title": scene.title, "summary": scene.summary},
            "hero_name": ctx.hero.name,
            "turns": turns,
            "npcs": npcs,
            "locations": locations,
            "limit": self.app_cfg.memory.scene_summary_max,
        }


class SummarizerSession:
    """Роль summarizer: выжимка закрытой сцены поверх цикла MasterSession.

    adapter -- адаптер роли summarizer; model -- id его модели (по умолчанию roles.summarizer).
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

    def run_scene(self, bundle, registry, cfg, run_id) -> TurnContext:
        # bundle -- рабочая копия границы; результат -- контекст с summary_text и summary_title
        ctx = TurnContext(bundle, registry, cfg, mode="summarize_scene")
        ctx.summary_max = self.app_cfg.memory.scene_summary_max
        session = MasterSession(
            self.adapter, self.app_cfg, journal=self.journal, ledger=self.ledger, run_id=run_id,
            sleeper=self.sleeper, now=self.now, role="summarizer", call_numbers=self.call_numbers,
            builder=SummarizerPromptBuilder(self.app_cfg, model=self.model),
        )
        session.run(ctx, "", apply, "summarize_scene", run_id=run_id)
        return ctx

    def run_chapter(self, bundle, registry, cfg, run_id) -> TurnContext:
        # bundle -- рабочая копия границы; результат -- контекст с chapter_text, game_text
        ctx = TurnContext(bundle, registry, cfg, mode="summarize_chapter")
        ctx.chapter_summary_max = self.app_cfg.memory.chapter_summary_max
        ctx.game_summary_max = self.app_cfg.memory.game_summary_max
        session = MasterSession(
            self.adapter, self.app_cfg, journal=self.journal, ledger=self.ledger, run_id=run_id,
            sleeper=self.sleeper, now=self.now, role="summarizer", call_numbers=self.call_numbers,
            builder=SummarizerPromptBuilder(self.app_cfg, model=self.model),
        )
        session.run(ctx, "", apply, "summarize_chapter", run_id=run_id)
        return ctx
