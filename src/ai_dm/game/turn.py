import time
import uuid
from datetime import UTC, datetime

from ai_dm.combat.engine import CombatRoundLimit
from ai_dm.config.app import profile_for
from ai_dm.core.rng import Rng
from ai_dm.game import boundary, combat_flow, combat_fold
from ai_dm.game.controllers import PlayerController
from ai_dm.game.scene import check_close, hero_of
from ai_dm.master.prompt import PromptBuilder
from ai_dm.master.session import MasterSession, TurnFailed
from ai_dm.master.summarizer import SummarizerSession
from ai_dm.master.world import WorldSession
from ai_dm.protocol.apply import apply
from ai_dm.protocol.context import TurnContext
from ai_dm.protocol.decision import Decision
from ai_dm.reports.capture import TurnCapture
from ai_dm.rules.battle_memory import remember_battle
from ai_dm.rules.custom_items import world_registry
from ai_dm.rules.goals import on_kill
from ai_dm.rules.knowledge import note_combat, note_presence
from ai_dm.rules.spellcasting import expire_concentration
from ai_dm.rules.survivors import classify, materialize, reveal_names
from ai_dm.rules.time_ops import turn_tick
from ai_dm.state.scene import TurnRecord

ERROR_MENU = ["retry", "switch_model", "save_and_quit"]
REFUSAL_HINT = (
    "Модель отказалась отвечать. Если так повторяется, смягчите tone мира или смените модель."
)
SOFTEN_NOTE = (
    "Системная приписка: опиши эту сцену сдержанно, без натурализма; "
    "насилие и откровенность — за кадром или намёком."
)
TEXT_NOTE = (
    "Системная приписка: напиши сцену текстом ответа — "
    "игрок видит только текст, размышления ему не показываются."
)
AUTH_HINT = "Ключ {provider} не принят — введите новый: /key, затем «1. повтор»."
RETRY_NOTES = {"refusal": SOFTEN_NOTE, "short": TEXT_NOTE}
HARD_REFUSALS = ("PROHIBITED_CONTENT", "BLOCKLIST", "SPII")


def hard_refusal(failure):
    return failure.reason == "refusal" and failure.detail in HARD_REFUSALS


def failure_hint(failure):
    # что видит игрок вместо сырого текста сбоя
    if failure.reason == "refusal":
        return REFUSAL_HINT
    if failure.reason == "auth":
        return AUTH_HINT.format(provider=failure.detail)
    return str(failure)


class TurnResult:
    def __init__(self, run_id):
        self.committed = False
        self.run_id = run_id
        # основной run_id и run_id границы сцены, сработавшей в этом ходе
        self.run_ids = [run_id]
        # бандл до хода (для репорта)
        self.before = None
        self.narration = ""
        self.lines = []
        self.log = []
        self.requests = []
        # итог инструментов хода для памяти рассказчика (в lines и UI не попадает)
        self.outcomes = []
        self.rolls = []
        self.report_tags = []
        self.failure = None
        self.menu = None
        self.hint = None
        self.combat_outcome = None
        self.hero_dead = False
        self.scene_summary = None
        self.chapter_title = None
        # граница сцены: (номер, название) закрытой главы, закадровые заметки, текст сбоя
        self.chapter_closed = None
        self.offscreen = []
        self.boundary_failed = False


class TurnRunner:
    def __init__(
        self, bundle, registry, cfg, app_cfg, adapter, *, saves_root, journal=None, ledger=None,
        world_text="", sleeper=time.sleep, now=None, model=None, run_tag=None,
        world_adapter=None, world_model=None, summarizer_adapter=None, summarizer_model=None,
        summarizer_backup=None,
    ):
        self.bundle = bundle
        self.base_registry = registry
        self.cfg = cfg
        self.app_cfg = app_cfg
        self.saves_root = saves_root
        self.journal = journal
        self.ledger = ledger
        self.world_text = world_text
        self.sleeper = sleeper
        self.now = now or (lambda: datetime.now(UTC))
        # метка уникальна между перезапусками на одном журнале
        tag = run_tag or uuid.uuid4().hex[:6]
        self.stamp = f"{self.now():%Y%m%dT%H%M%S}-{tag}"
        self.run_count = 0
        self.boundary_count = 0
        # адаптер роли world (None -- адаптер нарратора) и id его модели (None -- roles.world)
        self.world_adapter = world_adapter
        self.world_model = world_model
        # адаптер роли summarizer (None -- запасная выжимка без модели) и id его модели
        # (None -- профиль)
        self.summarizer_adapter = summarizer_adapter
        self.summarizer_model = summarizer_model
        # адаптер вызова запасного summarizer (None -- адаптер рассказчика); нужен replay
        self.summarizer_backup = summarizer_backup
        # приписка к запросам рассказчика на время повтора хода после отказа или короткого рассказа
        self.note = None
        # роль, на которой оборвалась граница ("summarizer" или None): кого менять в меню 2.2
        self.failed_role = None
        # номера вызовов по run_id: общий у ролей одной границы (world и summarizer)
        self.call_numbers = {}
        self.last_input = None
        # строка игрока, пришедшая при недостроенной границе: играется после достройки
        self.deferred_input = None
        # итог последнего хода для /report
        self.last_capture = None
        self.set_adapter(adapter, model)

    @property
    def registry(self):
        # реестр пака и SRD плюс сюжетные предметы мира
        return world_registry(self.base_registry, self.bundle.world)

    def set_adapter(self, adapter, model=None):
        if model is None:
            model = adapter.info().model
        self.adapter = adapter
        self.model = model
        self.builder = PromptBuilder(self.app_cfg, model=model, provider=adapter.info().provider)

    def play(self, player_input) -> TurnResult:
        self.last_input = player_input
        return self.run_turn(player_input)

    def retry(self) -> TurnResult:
        if self.bundle.session.boundary_pending:
            # сбой был на границе сцены: достраиваем её; отложенную строку игрока играем как ход
            if self.deferred_input is not None:
                player_input, self.deferred_input = self.deferred_input, None
                return self.play(player_input)
            self.run_count += 1
            run_id = f"run-{self.stamp}-{self.run_count}"
            result = TurnResult(run_id)
            result.before = self.bundle
            result.committed = True
            done = self.resume_boundary(result)
            self.mark_journal(run_id, "committed" if done else "aborted")
            self.last_capture = self.capture_of(result, None)
            return result
        return self.run_turn(self.last_input)

    def preview_turn(self):
        return combat_flow.preview_options(self.bundle, self.registry, self.cfg)

    def preview_screen(self):
        return combat_flow.preview_screen(self.bundle, self.registry, self.cfg)

    def inert_spells(self):
        return combat_flow.inert_spell_names(self.bundle, self.registry, self.cfg)

    def concentration_line(self):
        return combat_flow.concentration_line(self.bundle, self.registry, self.cfg)

    def ac_text(self):
        return combat_flow.hero_ac_text(self.bundle, self.registry)

    def effects_line(self):
        return combat_flow.hero_effects_line(self.bundle, self.registry)

    def capture_of(self, result, player_input) -> TurnCapture:
        status = "committed"
        # снимки копией: бандл живёт дальше и меняется (выбор уровня, тон), /report бывает позже
        after = self.bundle.model_copy(deep=True)
        before = result.before
        turn_seq = after.session.turn_seq
        if not result.committed:
            status = "aborted"
            after = None
            before = before.model_copy(deep=True)
            turn_seq = before.session.turn_seq + 1
        reason = None
        if result.failure is not None:
            reason = result.failure.reason
        return TurnCapture(
            turn_seq=turn_seq, run_ids=list(result.run_ids), player_input=player_input,
            tags=list(dict.fromkeys(result.report_tags)), status=status, failure_reason=reason,
            before=before, after=after, now_iso=self.now().isoformat(), model=self.model,
        )

    def empty_capture(self) -> TurnCapture:
        # снимок текущего состояния, когда ходов в сессии ещё не было
        return TurnCapture(
            turn_seq=self.bundle.session.turn_seq, run_ids=[], player_input=None, tags=[],
            status="none", failure_reason=None, before=self.bundle, after=None,
            now_iso=self.now().isoformat(), model=self.model,
        )

    def run_turn(self, player_input) -> TurnResult:
        result = self.play_turn(player_input)
        self.last_capture = self.capture_of(result, player_input)
        return result

    def play_turn(self, player_input) -> TurnResult:
        self.run_count += 1
        run_id = f"run-{self.stamp}-{self.run_count}"
        result = TurnResult(run_id)
        result.before = self.bundle
        if self.bundle.session.boundary_pending and not self.resume_boundary(result):
            self.mark_journal(run_id, "aborted")
            self.deferred_input = player_input
            return result
        time_before_s = self.bundle.world.clock.now_s
        try:
            work, rng, narration = self.attempt(player_input, run_id, result)
        except TurnFailed as failure:
            note = None if hard_refusal(failure) else RETRY_NOTES.get(failure.reason)
            if note is None:
                return self.failed(result, failure)
            # один автоповтор хода на той же модели с припиской, с новой копии
            result = self.retry_result(result, failure.reason)
            self.note = note
            try:
                work, rng, narration = self.attempt(player_input, run_id, result)
            except TurnFailed as again:
                return self.failed(result, again)
            finally:
                self.note = None
        self.commit(work, rng, player_input, narration, result)
        self.mark_journal(run_id, "committed")
        self.close_scene_if_needed(result, time_before_s)
        return result

    def attempt(self, player_input, run_id, result):
        # ход идёт на копии: откат -- выбросить копию
        work = self.bundle.model_copy(deep=True)
        rng = Rng.from_state(work.world.rng)
        start_s = work.world.clock.now_s
        try:
            if work.session.active_combat is None:
                narration = self.explore_turn(work, rng, player_input, run_id, result)
                if "start_combat" not in result.requests:
                    turn_tick(work.world.clock, start_s, self.cfg)
            else:
                narration = self.combat_turn(work, rng, player_input, run_id, result)
        except CombatRoundLimit as error:
            raise TurnFailed("round_limit", str(error)) from error
        except TurnFailed:
            raise
        except Exception:
            self.mark_journal(run_id, "aborted")
            raise
        # страховка: любой сдвиг часов в ходе (в т.ч. left_to_die) мог закончить концентрацию
        expire_concentration(hero_of(work), work.world)
        return work, rng, narration

    def retry_result(self, started, reason) -> TurnResult:
        result = TurnResult(started.run_id)
        result.run_ids = started.run_ids
        result.before = started.before
        result.report_tags = [f"{reason}_retry"]
        return result

    def failed(self, started, failure) -> TurnResult:
        self.mark_journal(started.run_id, "aborted")
        result = TurnResult(started.run_id)
        result.run_ids = started.run_ids
        result.before = started.before
        result.failure = failure
        result.report_tags = list(dict.fromkeys(started.report_tags + failure.report_tags))
        result.menu = list(ERROR_MENU)
        result.hint = failure_hint(failure)
        return result

    def mark_journal(self, run_id, status, role=None):
        if self.journal is not None:
            self.journal.mark_turn(run_id, status, role)
        self.call_numbers.pop(run_id, None)

    def commit(self, work, rng, player_input, narration, result):
        work.world.rng = rng.state
        work.session.turn_seq += 1
        money_delta = hero_of(work).money_cp - hero_of(self.bundle).money_cp
        work.memory.recent_turns.append(
            TurnRecord(
                turn_seq=work.session.turn_seq, at_s=work.world.clock.now_s,
                player_input=player_input, narration=narration, requests=list(result.requests),
                rolls=list(result.rolls), scene_id=work.session.current_scene.id,
                outcomes=list(result.outcomes), money_delta_cp=money_delta,
            )
        )
        keep = self.app_cfg.master.recent_turns_keep
        work.memory.recent_turns = work.memory.recent_turns[-keep:]
        work.session.current_scene.player_turns += 1
        reveal_names(hero_of(work), work.world, narration)
        note_presence(
            hero_of(work), work.world, f"{player_input}\n{narration}", self.cfg.knowledge
        )
        result.committed = True
        result.narration = narration
        result.hero_dead = hero_of(work).status == "dead"
        self.bundle = work

    def close_scene_if_needed(self, result, time_before_s):
        if result.hero_dead:
            # временное правило: смерть в бою не закрывает сцену и не пишет автосейв,
            # чтобы "загрузить последнее" вернуло состояние до боя
            return
        bundle = self.bundle
        reason = check_close(
            bundle, self.cfg, time_before_s=time_before_s,
            combat_ended=result.combat_outcome is not None,
        )
        if reason is None:
            return
        done = boundary.run(
            bundle, self.cfg, self.registry, reason, saves_root=self.saves_root,
            saved_at=self.now().isoformat(), world=self.new_world_session(),
            run_id=self.next_boundary_id(), summarizer=self.new_summarizer_session(),
        )
        self.take_boundary(done, result)

    def resume_boundary(self, result) -> bool:
        # достройка границы после сбоя или загрузки; True -- граница завершена
        done = boundary.finish_boundary(
            self.bundle, self.cfg, self.registry, self.new_world_session(),
            self.next_boundary_id(), self.new_summarizer_session(),
        )
        self.take_boundary(done, result)
        return done.error is None

    def next_boundary_id(self) -> str:
        self.boundary_count += 1
        return f"bnd-{self.stamp}-{self.boundary_count}"

    def new_world_session(self):
        adapter = self.world_adapter or self.adapter
        model = self.world_model
        if model is None:
            # модель world -- профиль провайдера адаптера и модели рассказчика;
            # нет профиля (мок) -- roles.world
            profile = profile_for(self.app_cfg, adapter.info().provider, self.model)
            if profile is not None:
                model = profile.world.model
        return WorldSession(
            adapter, self.app_cfg, journal=self.journal, ledger=self.ledger,
            sleeper=self.sleeper, now=self.now, model=model, call_numbers=self.call_numbers,
        )

    def new_summarizer_session(self):
        adapter = self.summarizer_adapter
        if adapter is None:
            # нет адаптера summarizer: запасная выжимка без вызова модели (A5)
            return None
        model = self.summarizer_model
        if model is None:
            # модель summarizer -- профиль провайдера адаптера и модели рассказчика;
            # нет профиля (мок) -- roles
            profile = profile_for(self.app_cfg, adapter.info().provider, self.model)
            if profile is not None:
                model = profile.summarizer.model
        backup = None
        if adapter is not self.adapter or model != self.model:
            # запасной на модели рассказчика; если summarizer и так на ней -- повтор бесполезен
            backup = SummarizerSession(
                self.summarizer_backup or self.adapter, self.app_cfg, journal=self.journal,
                ledger=self.ledger, sleeper=self.sleeper, now=self.now, model=self.model,
                call_numbers=self.call_numbers,
            )
        policy = None
        if backup is not None:
            # есть запасной: primary без долгих повторов, к запасному сразу
            retry = self.app_cfg.retry
            policy = retry.model_copy(update={"delays": retry.chain_delays})
        return SummarizerSession(
            adapter, self.app_cfg, journal=self.journal, ledger=self.ledger,
            sleeper=self.sleeper, now=self.now, model=model, call_numbers=self.call_numbers,
            backup=backup, policy=policy,
        )

    def take_boundary(self, done, result):
        status = "aborted" if done.error else "committed"
        world_skipped = done.error is None and "world_skipped" in done.report_tags
        for run_id in sorted({done.summary_run_id, done.world_run_id} - {None}):
            if world_skipped and run_id == done.world_run_id:
                # мягкий сбой world: его записи не вошли в итог границы, остальное закоммичено
                self.mark_journal(run_id, "aborted", role="world")
            self.mark_journal(run_id, status)
            self.call_numbers.pop(run_id, None)
            if run_id not in result.run_ids:
                result.run_ids.append(run_id)
        self.take_tags(done.report_tags, result)
        self.bundle = done.bundle
        self.failed_role = done.failed_role
        if done.error is not None:
            result.boundary_failed = True
            result.menu = list(ERROR_MENU)
            result.hint = f"Не удалось завершить границу сцены: {done.error}"
            return
        result.chapter_closed = done.chapter_closed
        result.offscreen = done.notices
        # герой мог умереть за кадром при тике дней
        result.hero_dead = hero_of(self.bundle).status == "dead"

    # сессия мастера и учёт результатов хода

    def new_session(self, run_id):
        return MasterSession(
            self.adapter, self.app_cfg, journal=self.journal, ledger=self.ledger, run_id=run_id,
            sleeper=self.sleeper, now=self.now, builder=self.builder, note=self.note,
            call_numbers=self.call_numbers,
        )

    def take_scene_fields(self, ctx, result):
        if ctx.scene_summary is not None:
            result.scene_summary = ctx.scene_summary
        if ctx.chapter_title is not None:
            result.chapter_title = ctx.chapter_title

    def take_master_tags(self, master, result):
        # теги сессии мастера, которых ещё нет в итоге хода (context_overflow)
        self.take_tags(master.report_tags, result)

    def take_tags(self, tags, result):
        for tag in tags:
            if tag not in result.report_tags:
                result.report_tags.append(tag)

    def recording(self, result, inner):
        # исполнитель запросов, который копит итоги хода в result
        def execute(ctx, request):
            outcome = inner(ctx, request)
            if isinstance(outcome, Decision):
                result.lines += outcome.log
                if outcome.status in ("accepted", "clamped"):
                    result.requests.append(request.type)
                    result.outcomes += outcome.log
                else:
                    result.outcomes.append(f"{request.type}: отклонено ({outcome.reason})")
                if "roll_ref" in outcome.result:
                    result.rolls.append(outcome.log[0])
                if outcome.report_tag is not None:
                    result.report_tags.append(outcome.report_tag)
            return outcome

        return execute

    # ход вне боя

    def explore_turn(self, work, rng, text, run_id, result) -> str:
        session = self.new_session(run_id)
        ctx = TurnContext(
            work, self.registry, self.cfg, rng, mode="explore", base_registry=self.base_registry
        )

        def execute(ctx, request):
            outcome = apply(ctx, request)
            if request.type == "start_combat" and isinstance(outcome, Decision):
                outcome.log += combat_flow.start_fight(ctx, session, run_id, self.world_text)
            return outcome

        master = session.run(
            ctx, text, self.recording(result, execute), "explore", run_id=run_id,
            world_text=self.world_text,
        )
        self.take_scene_fields(ctx, result)
        self.take_master_tags(master, result)
        narration = master.narration
        state = work.session.active_combat
        if state is None:
            self.check_told(master)
            return narration
        result.log = list(state.log)
        if combat_flow.is_finished(state):
            # герой упал ещё до своего первого решения: тот же ход доходит до итога боя
            narration += "\n\n" + self.narrate_combat(
                work, rng, "", result.log, session, run_id, result
            )
            self.end_fight(work, result, fold=False)
        return narration

    def check_told(self, master):
        # инструменты были, а рассказа почти нет (сцену модель написала в мышлении)
        # при повторе (note) не проверяем: failed("short") недостижим, короткий рассказ принимается
        if self.note is not None or master.rounds == 0:
            return
        if len(master.narration) < self.app_cfg.master.min_narration_chars:
            raise TurnFailed("short", "Рассказ слишком короткий.")

    # ход героя в бою

    def combat_turn(self, work, rng, text, run_id, result) -> str:
        session = self.new_session(run_id)
        ctx = TurnContext(
            work, self.registry, self.cfg, rng, mode="combat_classify",
            combat_options=combat_flow.option_list(work, self.registry, self.cfg),
        )
        steps = []
        improvise = None
        parley = None
        said = ""
        hold = False
        if text.strip().isdigit():
            options = combat_flow.preview_options(work, self.registry, self.cfg)
            number = int(text)
            if not 1 <= number <= len(options):
                raise ValueError(f"нет такого варианта: {number}")
            steps = [options[number - 1].id]
            hold = True
        else:
            plans = []

            def execute(ctx, request):
                outcome = apply(ctx, request)
                accepted = isinstance(outcome, Decision) and outcome.status != "rejected"
                if request.type == "player_action" and accepted:
                    plans.append(request)
                return outcome

            master = session.run(
                ctx, text, self.recording(result, execute), "combat_classify", run_id=run_id,
                world_text=self.world_text,
            )
            self.take_scene_fields(ctx, result)
            self.take_master_tags(master, result)
            steps = plans[-1].steps
            improvise = plans[-1].improvise
            parley = plans[-1].parley
            said = text
        state = work.session.active_combat
        log_start = len(state.log)
        engine = combat_flow.make_engine(
            ctx, session, run_id, self.world_text, PlayerController(steps, improvise, hold, parley)
        )
        engine.step()
        if not engine.is_over:
            combat_flow.advance_until_player(engine, hero_of(work).id)
        result.log = state.log[log_start:]
        narration = self.narrate_combat(work, rng, said, result.log, session, run_id, result)
        if combat_flow.is_finished(state):
            self.end_fight(work, result, fold=True)
        return narration

    def end_fight(self, work, result, fold) -> None:
        state = work.session.active_combat
        hero = hero_of(work)
        # выжившие определяются до finish_combat: он снимает метки переговоров
        survivors = classify(work, hero)
        combat_flow.settle_parley(work, self.cfg)
        result.combat_outcome = combat_flow.finish_combat(work, self.registry)
        turned = [s.part.ref for s in survivors if s.kind == "defected"]
        note_combat(hero, work.world, state, self.registry, self.cfg.knowledge, turned)
        self.avenge_killed(work, hero, state)
        materialize(work, hero, survivors, self.cfg)
        remember_battle(work, hero, state, state.outcome, self.cfg)
        if fold:
            combat_fold.fold_fight(work, state, self.registry)

    def avenge_killed(self, work, hero, state) -> None:
        # убитые героем враги боя: их родня и отряд (живые NPC вне боя) получают цель мести;
        # выжившие ещё не в мире -- зовётся до materialize
        for part in state.participants:
            if part.side == "enemies" and part.status == "dead":
                on_kill(work, hero, part, state, self.cfg)

    def narrate_combat(self, work, rng, said, log_lines, session, run_id, result) -> str:
        ctx = TurnContext(
            work, self.registry, self.cfg, rng, mode="combat_narrate",
        )
        parts = ([said] if said else []) + list(log_lines)
        master = session.run(
            ctx, "\n".join(parts), self.recording(result, apply), "combat_narrate",
            run_id=run_id, world_text=self.world_text,
        )
        self.take_scene_fields(ctx, result)
        self.take_master_tags(master, result)
        return master.narration
