import contextlib
import time
from datetime import UTC, datetime
from pathlib import Path

from ai_dm.audio import SilentSound
from ai_dm.campaign.loader import CAMPAIGNS_DIR, PackError, load_pack, pack_dir, pack_npc_trade
from ai_dm.campaign.merge import merge_new
from ai_dm.config.app import profile_for
from ai_dm.core.rng import Rng
from ai_dm.game import tone
from ai_dm.game.boundary import boundary_lines
from ai_dm.game.commands import COMMANDS
from ai_dm.game.models import (
    check_model,
    model_options,
    next_in_chain,
    read_models,
    write_models,
)
from ai_dm.game.scene import ensure_chapter, hero_of, start_scene
from ai_dm.game.turn import ERROR_MENU, TurnResult, TurnRunner, hard_refusal
from ai_dm.llm.cost import CostLedger
from ai_dm.llm.errors import MissingKey
from ai_dm.llm.factory import make_adapter
from ai_dm.llm.journal import Journal
from ai_dm.llm.keys import redact
from ai_dm.persistence.migrations import MigrationContext, SaveTooNew
from ai_dm.persistence.store import load_slot, save_auto, save_slot
from ai_dm.reports.writer import trim_issues, write_report
from ai_dm.rules.derived import companion_due
from ai_dm.rules.knowledge import ensure_journal
from ai_dm.rules.level_up import (
    begin_level_up,
    commit_level_up,
    current_step,
    reset_draft,
    step_options,
)
from ai_dm.rules.names import ABILITY_NAMES, SKILL_NAMES  # noqa: F401
from ai_dm.rules.progression import can_level_up

LOADED_PREFIX = "Загружено: "
SIMPLE_REASON = "звук только в TUI"
INV_NOTES_PREFIX = "Перед этим герой сам: "
LEVEL_MENU = ["average", "roll"]
DEAD_MENU = ["load_last_save", "quit"]
CHOICE_TITLES = {
    "fighting_style": "боевой стиль",
    "expertise": "навык для экспертизы",
    "subclass": "подкласс",
    "asi_or_feat": "повышение характеристик или черту",
    "spells": "заклинание для подготовки",
}


def merge_pack(bundle, registry, campaigns_dir) -> list[str]:
    # догрузка новых сущностей пака в идущий мир; возвращает строки для игрока
    campaign_id = bundle.world.campaign_id
    if campaign_id is None:
        return []
    path = pack_dir(campaigns_dir, campaign_id)
    if not path.is_dir():
        return [
            f"Пака {campaign_id} нет ни в {campaigns_dir}, ни в поставке: игра идёт без догрузки."
        ]
    try:
        pack = load_pack(path, registry)
    except PackError as error:
        return [f"Пак {campaign_id} не догружен:"] + error.lines
    report = merge_new(bundle, pack)
    lines = []
    if report.added:
        lines.append(f"Из пака добавлено: {', '.join(report.added)}.")
    if report.conflicts:
        lines.append("Не загружено из пака (конфликты):")
        lines += [conflict.line() for conflict in report.conflicts]
    return lines


class Reply:
    def __init__(
        self, lines=None, narration="", turn=None, pending=None, menu=None, hint=None, quit=False,
        raw=None, request=None,
    ):
        self.lines = lines or []
        # просьба к UI открыть окно (сейчас только "key" -- ввод ключа API)
        self.request = request
        # готовые строки (карта боя): выводятся как есть, без переноса
        self.raw = raw or []
        self.narration = narration
        self.turn = turn
        self.pending = pending
        self.menu = menu
        self.hint = hint
        self.quit = quit


class GameApp:
    def __init__(
        self, settings, registry, bundle, adapter, *, saves_root, adapter_factory=None,
        world_text="", sleeper=time.sleep, now=None, model=None,
        use_stored_model=True, run_tag=None, campaigns_dir=CAMPAIGNS_DIR, world_adapter=None,
        world_model=None, summarizer_adapter=None, summarizer_model=None, auto_reports=True,
        secrets=(), summarizer_backup=None, refusal_chain=True,
    ):
        self.settings = settings
        self.auto_reports = auto_reports
        self.refusal_chain = refusal_chain
        # ключ последнего записанного репорта оборванной попытки хода (T9)
        self.reported = None
        self.secrets = secrets
        self.base_registry = registry
        self.saves_root = Path(saves_root)
        self.campaigns_dir = Path(campaigns_dir)
        self.now = now or (lambda: datetime.now(UTC))
        if adapter_factory is None:
            def adapter_factory(provider, model_id):
                return make_adapter(provider, model_id, settings.app)
        self.adapter_factory = adapter_factory
        self.world_id = bundle.world.world_id
        self.journal = Journal(self.saves_root, self.world_id, settings.app.journal)
        self.ledger = CostLedger(self.saves_root, self.world_id)
        self.startup_lines = []
        self.hinted_combat = None
        self.checked_adapter = None
        if use_stored_model:
            error = self.restore_model()
            if error is not None:
                self.startup_lines.append(f"Сохранённая модель не подключена: {error}")
            elif self.checked_adapter is not None:
                adapter = self.checked_adapter
                model = None
        ensure_journal(bundle, settings.rules.knowledge)
        self.runner = TurnRunner(
            bundle, registry, settings.rules, settings.app, adapter, saves_root=self.saves_root,
            journal=self.journal, ledger=self.ledger, world_text=world_text, sleeper=sleeper,
            now=self.now, model=model, run_tag=run_tag, world_adapter=world_adapter,
            world_model=world_model, summarizer_adapter=summarizer_adapter,
            summarizer_model=summarizer_model, summarizer_backup=summarizer_backup,
        )
        self.pending = None
        if hero_of(bundle).pending_level is not None:
            self.pending = "level_up"
        # роль, чью модель меняет меню 2.2 ("narrator", "summarizer" или "both")
        self.switch_role = "narrator"
        # причина сбоя последнего хода ("network", "refusal", ...) или None
        self.failed_reason = None
        # (шкала, значение) изменения тона, ждущего подтверждения (pending tone_confirm)
        self.tone_change = None
        # действия героя из окна inv, о которых рассказчик узнает в следующем ходе (не в сейве)
        self.inv_notes = []
        # звук: cli подменяет на настоящий контроллер только в TUI
        self.audio = SilentSound(SIMPLE_REASON)

    @property
    def registry(self):
        return self.runner.registry

    @property
    def bundle(self):
        return self.runner.bundle

    @property
    def adapter(self):
        return self.runner.adapter

    # ответы

    def menu_for(self, pending):
        if pending == "level_up":
            if hero_of(self.bundle).pending_level is not None:
                return step_options(hero_of(self.bundle), self.registry)
            return list(LEVEL_MENU)
        if pending == "model_choice":
            return self.model_options()
        fixed = {
            "error_menu": list(ERROR_MENU), "hero_dead": list(DEAD_MENU),
            "tone_confirm": ["да", "нет"],
        }
        return fixed.get(pending)

    def reply(self, lines=None, **fields):
        return Reply(lines, pending=self.pending, menu=self.menu_for(self.pending), **fields)

    def model_options(self):
        return model_options(self.settings.app, self.current_key())

    def current_key(self):
        # ключ модели меняемой роли (для порядка меню по цепочке)
        adapter = self.adapter
        if self.switch_role == "summarizer" and self.runner.summarizer_adapter is not None:
            adapter = self.runner.summarizer_adapter
        info = adapter.info()
        return f"{info.provider}:{info.model}"

    # ввод игрока

    def handle(self, line) -> Reply:
        line = line.strip()
        if line.startswith("/"):
            name, _, arg = line[1:].partition(" ")
            if name not in COMMANDS:
                return self.reply([f"Неизвестная команда /{name}. Список команд: /help"])
            return COMMANDS[name](self, arg.strip())
        if not line:
            return self.reply()
        if self.pending is not None:
            return self.reply(["Сначала нужно сделать выбор в меню."])
        in_combat = self.bundle.session.active_combat is not None
        if in_combat and line.isdigit() and not 1 <= int(line) <= len(self.runner.preview_turn()):
            return self.reply(["Нет такого варианта."])
        return self.after_turn(self.runner.play(self.with_notes(line, in_combat)))

    def with_notes(self, line, in_combat) -> str:
        # что герой сделал из окна inv (надел, снял, выпил) -- рассказчику в начале следующего хода;
        # номер варианта боя остаётся числом, заметки ждут словесного хода
        if not self.inv_notes or (in_combat and line.isdigit()):
            return line
        notes, self.inv_notes = self.inv_notes, []
        return f"({INV_NOTES_PREFIX}{'; '.join(notes)}.) {line}"

    def after_turn(self, turn) -> Reply:
        turn, lines = self.chain_turn(turn)
        lines += self.auto_report(turn)
        self.failed_reason = None if turn.failure is None else turn.failure.reason
        if not turn.committed or turn.boundary_failed:
            self.pending = "error_menu"
            return self.reply(lines, turn=turn, narration=turn.narration, hint=turn.hint)
        self.pending = None
        if turn.hero_dead:
            self.pending = "hero_dead"
            lines.append("Герой погиб. Можно загрузить последнее сохранение.")
        elif can_level_up(hero_of(self.bundle), self.registry):
            self.pending = "level_up"
            hero = hero_of(self.bundle)
            if hero.pending_level is not None:
                lines.append(f"Выберите: {self.step_title(current_step(hero, self.registry))}.")
            else:
                lines.append("Опыта хватает на новый уровень: выберите, как прибавить HP.")
        return self.reply(lines, narration=turn.narration, turn=turn)

    def chain_turn(self, turn):
        # жёсткий отказ модели: переход к следующей по цепочке и повтор хода; (ход, строки игроку)
        lines = []
        while self.refusal_chain and turn.failure is not None and hard_refusal(turn.failure):
            following = next_in_chain(self.settings.app, self.current_key())
            if following is None:
                break
            lines += self.auto_report(turn)
            old = self.current_key().partition(":")[2]
            error = self.set_narrator(following)
            if error is not None:
                lines.append(error)
                break
            detail = turn.failure.detail
            new = following.partition(":")[2]
            lines.append(f"Модель {old} отказала ({detail}) — переключаюсь на {new}.")
            turn = self.runner.retry()
        return turn, lines

    # репорты

    def already_reported(self, capture) -> bool:
        # оборванная попытка с теми же ходом, тегами, причиной и моделью уже записана
        if capture.status != "aborted":
            return False
        key = (capture.turn_seq, tuple(capture.tags), capture.failure_reason, capture.model)
        if key == self.reported:
            return True
        self.reported = key
        return False

    def auto_report(self, turn) -> list[str]:
        capture = self.runner.last_capture
        if not self.auto_reports or not turn.report_tags or capture is None:
            return []
        if self.already_reported(capture):
            return []
        return self.write_report_lines(capture, "")

    def report(self, text) -> list[str]:
        capture = self.runner.last_capture
        if capture is None:
            capture = self.runner.empty_capture()
        return self.write_report_lines(capture, text)

    def write_report_lines(self, capture, text) -> list[str]:
        try:
            path = write_report(
                self.saves_root, self.world_id, capture, text, self.now(), journal=self.journal,
                recent_turns=self.settings.app.reports.recent_turns,
            )
        except OSError as error:
            return [redact(f"Репорт не записан: {error}", self.secrets)]
        with contextlib.suppress(OSError):
            trim_issues(self.saves_root, self.world_id, self.settings.app.reports.max_mb)
        return [f"Записан репорт: {path}"]

    # ответ на меню

    def choose(self, key) -> Reply:
        if self.pending is None:
            return self.reply(["Сейчас выбирать нечего."])
        if key not in self.menu_for(self.pending):
            return self.reply(["Нет такого варианта."])
        if self.pending == "level_up":
            return self.choose_level_up(key)
        if self.pending == "error_menu":
            return self.choose_error(key)
        if self.pending == "model_choice":
            return self.choose_model(key)
        if self.pending == "tone_confirm":
            return self.choose_tone(key)
        return self.choose_dead(key)

    def menu_label(self, key) -> str:
        # подпись пункта меню выбора уровня: название из контента, навыка или характеристики
        for kind in ("feat", "subclass", "feature", "spell"):
            if self.registry.has(kind, key):
                return self.registry.get(kind, key).name
        if key in SKILL_NAMES:
            return SKILL_NAMES[key]
        first, _, second = key.partition("+")
        if first in ABILITY_NAMES:
            if second == "2":
                return f"{ABILITY_NAMES[first]} +2"
            return f"{ABILITY_NAMES[first]} +1, {ABILITY_NAMES[second]} +1"
        return key

    def record_choice(self, step, key) -> None:
        draft = hero_of(self.bundle).pending_level.draft
        if step == "fighting_style":
            draft.fighting_style = key
        elif step == "expertise":
            draft.expertise = [key]
        elif step == "subclass":
            draft.subclass_id = key
        elif step == "spells":
            draft.spells_add.append(key)
        elif step == "asi_or_feat":
            first, _, second = key.partition("+")
            if second == "2":
                draft.asi = {first: 2}
            elif second:
                draft.asi = {first: 1, second: 1}
            else:
                draft.feat = key
        else:
            draft.feature_choices[step] = [key]

    def choose_level_up(self, key) -> Reply:
        hero = hero_of(self.bundle)
        if hero.pending_level is not None:
            return self.choose_level_choice(hero, key)
        if key == "roll":
            rng = Rng.from_state(self.bundle.world.rng)
            begin_level_up(hero, self.registry, hp_method="roll", rng=rng)
            self.bundle.world.rng = rng.state
        else:
            begin_level_up(hero, self.registry, hp_method="average")
        step = current_step(hero, self.registry)
        if step is None:
            commit_level_up(hero, self.registry)
            return self.finish_level_up(hero)
        level = hero.sheet.level + 1
        return self.reply([f"Опыта хватает на уровень {level}: выберите {self.step_title(step)}."])

    def step_title(self, step) -> str:
        if step in CHOICE_TITLES:
            return CHOICE_TITLES[step]
        return self.registry.get("feature", step).name

    def choose_level_choice(self, hero, key) -> Reply:
        self.record_choice(current_step(hero, self.registry), key)
        step = current_step(hero, self.registry)
        if step is not None:
            return self.reply([f"Выберите: {self.step_title(step)}."])
        refused = commit_level_up(hero, self.registry)
        if refused is not None:
            # выборы не применились: начинаем заново с первого шага, pending остаётся
            reset_draft(hero)
            first = current_step(hero, self.registry)
            return self.reply(
                refused.messages + ["Выборы начаты заново.", f"Выберите: {self.step_title(first)}."]
            )
        return self.finish_level_up(hero)

    def finish_level_up(self, hero) -> Reply:
        if not can_level_up(hero, self.registry):
            self.pending = None
        lines = [f"{hero.name}: уровень {hero.sheet.level}."]
        if companion_due(hero, self.registry):
            lines.append(
                "Повелитель зверей: зверь-спутник появится по сюжету — "
                "скажи рассказчику, кого и как зовут."
            )
        return self.reply(lines)

    def choose_error(self, key) -> Reply:
        if key == "retry":
            self.pending = None
            return self.after_turn(self.runner.retry())
        if key == "switch_model":
            self.pending = "model_choice"
            # сбой summarizer на границе -- меняем модель summarizer, не рассказчика
            self.switch_role = "narrator"
            if self.runner.failed_role == "summarizer":
                self.switch_role = "summarizer"
            elif self.failed_reason == "network":
                # сеть: упасть могла любая из ролей -- выбранная модель ставится обеим
                self.switch_role = "both"
            return self.reply(["Выберите модель."])
        self.save_current("auto")
        return self.reply(["Сохранено."], quit=True)

    def choose_model(self, key) -> Reply:
        if self.switch_role == "summarizer":
            error = self.set_summarizer(key)
            title = "Модель summarizer"
        elif self.switch_role == "both":
            error = self.set_narrator(key) or self.set_summarizer(key)
            if error is None:
                # одна модель у обеих ролей: общий адаптер, запасной summarizer на ней не нужен
                self.runner.summarizer_adapter = self.runner.adapter
            title = "Модели рассказчика и summarizer"
        else:
            error = self.set_narrator(key)
            title = "Модель рассказчика"
        if error is not None:
            return self.reply([error])
        self.pending = "error_menu"
        self.switch_role = "narrator"
        return self.reply([f"{title}: {key}."])

    def choose_tone(self, key) -> Reply:
        scale, value = self.tone_change
        self.tone_change = None
        self.pending = None
        if key != "да":
            return self.reply(["Ограничение не снято."])
        line = tone.apply(self.bundle, scale, value)
        self.save_current("auto")
        return self.reply([line])

    def choose_dead(self, key) -> Reply:
        if key == "quit":
            return self.reply(quit=True)
        return self.reply(self.load("auto"))

    # сейвы и модель (общие для меню и команд)

    def save_current(self, slot):
        if slot == "auto":
            save_auto(
                self.saves_root, self.bundle, saved_at=self.now().isoformat(),
                cfg=self.settings.rules,
            )
        else:
            save_slot(self.saves_root, self.bundle, slot, saved_at=self.now().isoformat())

    def load(self, slot) -> list[str]:
        try:
            campaign_id = self.bundle.world.campaign_id
            folder = None if campaign_id is None else pack_dir(self.campaigns_dir, campaign_id)
            context = MigrationContext.from_registry(self.base_registry)
            context.npc_trade = pack_npc_trade(folder, self.base_registry)
            bundle = load_slot(self.saves_root, self.world_id, slot, context=context)
        except FileNotFoundError:
            return [f"нет сохранений в слоте {slot}."]
        except (ValueError, SaveTooNew) as error:
            return [f"Не удалось загрузить {slot}: {error}"]
        ensure_chapter(bundle)
        self.runner.deferred_input = None
        self.runner.last_capture = None
        self.reported = None
        self.failed_reason = None
        self.inv_notes = []
        scene = bundle.session.current_scene
        pending_boundary = bundle.session.boundary_pending and hero_of(bundle).status != "dead"
        if not pending_boundary and (scene is None or scene.closed_reason is not None):
            start_scene(bundle)
        ensure_journal(bundle, self.settings.rules.knowledge)
        self.runner.bundle = bundle
        self.pending = None
        if hero_of(bundle).pending_level is not None:
            self.pending = "level_up"
        lines = [f"{LOADED_PREFIX}{slot}."]
        if context.report:
            lines.append(context.warning())
        if pending_boundary:
            # граница сцены не была завершена: достраиваем до первого хода
            result = TurnResult("")
            self.runner.resume_boundary(result)
            if result.boundary_failed:
                self.pending = "error_menu"
                lines.append(result.hint)
                return lines
            lines += boundary_lines(result.chapter_closed, result.offscreen)
            bundle = self.bundle
        lines += merge_pack(bundle, self.base_registry, self.campaigns_dir)
        if hero_of(bundle).status == "dead":
            self.pending = "hero_dead"
            lines.append("Герой погиб. Можно загрузить другое сохранение.")
        return lines

    def restore_model(self) -> str | None:
        # сохранённая модель рассказчика; при успехе адаптер в checked_adapter, иначе текст ошибки
        try:
            stored = read_models(self.saves_root, self.world_id).get("narrator")
            if stored is None:
                return None
            provider = stored["provider"]
            model = stored["model"]
        except (ValueError, KeyError, OSError) as error:
            return f"{type(error).__name__}: {error}"
        return self.check_model(provider, model)

    def check_model(self, provider, model) -> str | None:
        # проверяет цену, окно и фабрику; годный адаптер оставляет в checked_adapter
        self.checked_adapter, error = check_model(
            self.settings.app, self.adapter_factory, provider, model
        )
        return error

    def set_summarizer(self, key) -> str | None:
        # меняет модель summarizer на сессию (рассказчик и models.json не трогаются)
        provider, _, model = key.partition(":")
        error = self.check_model(provider, model)
        if error is not None:
            return error
        self.runner.summarizer_adapter = self.checked_adapter
        self.runner.summarizer_model = model
        return None

    def set_narrator(self, key) -> str | None:
        # меняет адаптер рассказчика; возвращает текст ошибки или None
        provider, _, model = key.partition(":")
        error = self.check_model(provider, model)
        if error is not None:
            return error
        narrator_adapter = self.checked_adapter
        runner = self.runner
        for role in ("world", "summarizer"):
            error = self.follow_provider(role, provider, model)
            if error is not None:
                return error
        runner.set_adapter(narrator_adapter)
        write_models(self.saves_root, self.world_id, provider, model)
        return None

    def rekey(self, provider) -> str:
        # после нового ключа: адаптеры ролей этого провайдера пересоздаются (ключ читается заново)
        runner = self.runner
        count = 0
        if runner.adapter.info().provider == provider:
            runner.set_adapter(self.adapter_factory(provider, runner.model), runner.model)
            count += 1
        for role in ("world", "summarizer"):
            adapter = getattr(runner, f"{role}_adapter")
            if adapter is None or adapter.info().provider != provider:
                continue
            model = getattr(runner, f"{role}_model") or adapter.info().model
            setattr(runner, f"{role}_adapter", self.adapter_factory(provider, model))
            count += 1
        if count:
            return f"Ключ {provider} подключён."
        return f"Ключ {provider} сохранён: сменить модель — /model."

    def follow_provider(self, role, provider, narrator_model) -> str | None:
        # роль world/summarizer следует за рассказчиком: профиль его провайдера и модели
        runner = self.runner
        app_cfg = self.settings.app
        adapter = getattr(runner, f"{role}_adapter")
        if adapter is None:
            return None
        current = profile_for(app_cfg, adapter.info().provider, runner.model)
        target = profile_for(app_cfg, provider, narrator_model)
        if current is None or target is None or current is target:
            return None
        provider = getattr(target, role).provider
        model = getattr(target, role).model
        try:
            setattr(runner, f"{role}_adapter", self.adapter_factory(provider, model))
        except (MissingKey, ValueError) as error:
            return str(error)
        setattr(runner, f"{role}_model", model)
        return None
