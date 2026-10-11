from ai_dm.combat.controllers import EngineTactics
from ai_dm.protocol.apply import apply
from ai_dm.protocol.context import TurnContext
from ai_dm.protocol.decision import Decision
from ai_dm.rules.results import Rejected


class PlayerController:
    # ход героя: сначала импровизация и переговоры (если есть), потом шаги, потом конец хода
    def __init__(self, steps=None, improvise=None, hold=False, parley=None):
        # hold: выбран один пункт меню -- после него ход не кончается, если есть что делать
        self.hold = hold
        self.steps = list(steps or [])
        # был план (шаги или импровизация) -- свободный текст
        self.planned = bool(steps) or improvise is not None or parley is not None
        self.improvise = improvise
        self.parley = parley
        self.engine = None

    def attach(self, engine):
        self.engine = engine

    def act(self, point) -> None:
        # импровизация и переговоры героя до шагов; отказ движка попадает в лог
        engine = self.engine
        name = engine.name(point.actor)
        if self.improvise is not None:
            spec = self.improvise
            self.improvise = None
            done = engine.improvise(
                point.actor, skill=spec.skill, category=spec.category, effect=spec.effect,
                target=spec.target, zone=spec.zone,
            )
            if isinstance(done, Rejected):
                engine.log(f"{name}: импровизация невозможна ({done.reason})")
        if self.parley is not None and not engine.is_over and engine.is_capable(point.actor):
            spec = self.parley
            self.parley = None
            done = engine.parley(
                point.actor, skill=spec.skill, outcome=spec.outcome, target=spec.target
            )
            if isinstance(done, Rejected):
                engine.log(f"{name}: переговоры невозможны ({done.reason})")

    def choose(self, options, point) -> str:
        engine = self.engine
        if self.improvise is not None or self.parley is not None:
            self.act(point)
            if engine.is_over or not engine.is_capable(point.actor):
                return "end_turn"
            # действие потрачено: список вариантов уже другой
            options = engine.available_actions(point.actor)
        ids = [o.id for o in options]
        while self.steps:
            step = self.steps.pop(0)
            if step in ids:
                return step
            engine.log(f"шаг {step} недоступен — пропущен")
        if self.hold and len(ids) > 1:
            return "hold"
        # свободный текст: ход открыт, пока не потрачено основное действие
        if self.planned and any(o.cost == "action" for o in options):
            return "hold"
        return "end_turn"


class MasterChoiceController:
    # ключевой NPC: намерение группы и (раз за бой, при малом HP) ход решает модель
    def __init__(self, ctx, session, *, run_id, world_text=""):
        self.ctx = ctx
        self.session = session
        self.run_id = run_id
        self.world_text = world_text
        self.engine = None

    def attach(self, engine):
        self.engine = engine

    def choose(self, options, point) -> str:
        engine = self.engine
        ref = point.actor
        name = engine.name(ref)
        if point.kind == "intent_reconsider":
            text = (
                f"{name} — ключевой NPC. Герой упал, надо решить, менять ли намерение группы. "
                "Выбери вариант вызовом npc_action."
            )
            return self.ask(point.options, text)
        creature = engine.creature(ref)
        percent = self.session.app_cfg.master.key_npc_consult_hp_percent
        wounded = creature.hp_current * 100 <= creature.hp_max * percent
        # модель выбирает только первое действие раненого хода (раз за бой),
        # остальное делает EngineTactics
        if wounded and ref not in engine.state.consulted:
            engine.state.consulted.append(ref)
            text = (
                f"{name} — ключевой NPC, его ход. HP {creature.hp_current}/{creature.hp_max}. "
                "Выбери действие вызовом npc_action."
            )
            return self.ask([o.id for o in options], text)
        return EngineTactics(engine).choose(options, point)

    def ask(self, choices, text) -> str:
        ctx = self.ctx
        npc_ctx = TurnContext(
            ctx.bundle, ctx.registry, ctx.cfg, ctx.rng, mode="npc_choice",
            npc_options=list(choices),
        )
        picked = []

        def execute(npc_ctx, request):
            outcome = apply(npc_ctx, request)
            if isinstance(outcome, Decision) and outcome.status == "accepted":
                picked.append(request.choice)
            return outcome

        lines = [text, "Варианты:"] + [f"- {choice}" for choice in choices]
        self.session.run(
            npc_ctx, "\n".join(lines), execute, "npc_choice", run_id=self.run_id,
            world_text=self.world_text,
        )
        return picked[-1]
