from dataclasses import dataclass

from ai_dm.core.rng import Rng
from ai_dm.protocol.requests import IMPORT_MODE


class TurnContext:
    def __init__(
        self, bundle, registry, cfg, rng=None, *, mode="explore", npc_options=None,
        combat_options=None, base_registry=None,
    ):
        # bundle -- рабочая копия: копию на ход делает вызывающий
        self.bundle = bundle
        self.registry = registry
        # реестр без сюжетных предметов мира: от него строится реестр после новых предметов
        self.base_registry = registry if base_registry is None else base_registry
        self.cfg = cfg
        if rng is None:
            rng = Rng.from_state(bundle.world.rng)
        self.rng = rng
        self.mode = mode
        self.npc_options = npc_options
        # варианты героя в бою [{id, label}]: заполняет слой game
        self.combat_options = combat_options
        self.rolls = {}
        # roll_ref -> id того, кто бросал (герой или NPC)
        self.roll_actors = {}
        # roll_ref, уже потраченные на смертельное последствие: один бросок -- одно последствие
        self.used_rolls = set()
        self.events = []
        self.marks = []
        self.chapter_title = None
        self.scene_summary = None
        # запасной накопитель, если сцены нет
        self.own_attitude_spent = {}
        self.own_favor_spent = {}
        # роль world: ref всех кандидатов вызова, из них verdict; вердикты {ref: holds}
        # (None -- ещё не даны), id созданных заметок
        self.candidate_refs = []
        self.verdict_refs = []
        self.verdicts = None
        self.notice_ids = []
        # then_ref запросов world, по которым что-то применилось
        self.applied_refs = set()
        # роль summarizer: принятая выжимка (None -- ещё нет), название, предел длины
        self.summary_text = None
        self.summary_title = ""
        self.summary_max = 0
        # режим summarize_chapter: принятые выжимка главы, её название, новый game_summary, пределы
        self.chapter_text = None
        self.chapter_title_new = ""
        self.game_text = None
        self.chapter_summary_max = 0
        self.game_summary_max = 0
        # после скольких переполнений движок режет выжимку сам (0 -- не режет)
        self.summary_overflows = {}
        self.summary_trim_after = 0

    @property
    def turn_seq(self):
        return self.bundle.session.turn_seq

    @property
    def hero(self):
        for hero in self.bundle.heroes:
            if hero.id == self.bundle.manifest.current_hero_id:
                return hero
        raise KeyError(self.bundle.manifest.current_hero_id)

    @property
    def scene(self):
        return self.bundle.session.current_scene

    @property
    def attitude_spent(self):
        if self.scene is None:
            return self.own_attitude_spent
        return self.scene.attitude_spent

    @property
    def favor_spent(self):
        if self.scene is None:
            return self.own_favor_spent
        return self.scene.favor_spent

    def add_roll(self, result, actor_id=None) -> str:
        ref = f"r{len(self.rolls) + 1}"
        self.rolls[ref] = result
        self.roll_actors[ref] = actor_id
        return ref


@dataclass
class BackgroundTask:
    # задача создания: только предыстория под выбранный класс
    class_id: str
    class_skills: tuple = ()
    mode = "hero_background"


@dataclass
class SheetTask:
    # задача создания: лист героя целиком; feedback/previous -- переописание с замечанием
    known: object
    taken_names: list
    feedback: str = ""
    previous: dict | None = None
    mode = "hero_sheet"


@dataclass
class ImportTask:
    # задача import пака: id кампании, под которым пак ляжет в campaigns/
    campaign_id: str
    mode = IMPORT_MODE


class CreationContext:
    # контекст без бандла: создание героя (режимы hero_background, hero_sheet) и import пака
    def __init__(self, registry, cfg, task):
        self.registry = registry
        self.cfg = cfg
        self.task = task
        self.mode = task.mode
        self.background = None
        self.sheet = None
        self.files = None
        self.marks = []
        self.turn_seq = 0
