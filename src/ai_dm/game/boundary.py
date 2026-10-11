from ai_dm.core.clock import DAY
from ai_dm.core.rng import Rng
from ai_dm.game.scene import close_scene, ensure_chapter, start_scene
from ai_dm.llm.errors import LlmError
from ai_dm.master.session import TurnFailed
from ai_dm.persistence.store import save_auto
from ai_dm.state.memory import ChapterSummary, SceneSummary
from ai_dm.state.session import ChapterState
from ai_dm.world_sim import nudge, tick, triggers, verdicts


class BoundaryResult:
    def __init__(self, bundle):
        self.bundle = bundle
        # (номер, название) закрытой главы
        self.chapter_closed = None
        # тексты доставленных закадровых заметок
        self.notices = []
        self.error = None
        # run_id вызова world на границе (None -- вызова не было): по нему ход помечается в журнале
        self.world_run_id = None
        # run_id вызова summarizer на границе (None -- вызова не было)
        self.summary_run_id = None
        # роль, на которой оборвалась граница ("summarizer"), иначе None
        self.failed_role = None
        # метки репорта от запросов world на границе (limit-exceeded, invalid-death)
        self.report_tags = []


def close_boundary(bundle, cfg, reason) -> None:
    # шаг 1: закрытие сцены; граница не завершена (выжимку пишет summarize_scene)
    ensure_chapter(bundle)
    close_scene(bundle, reason, cfg)
    bundle.session.boundary_pending = True


def boundary_lines(chapter_closed, offscreen) -> list[str]:
    # строки для игрока: закрытая глава и закадровый блок (пусто, если доставлять нечего)
    lines = []
    if chapter_closed is not None:
        number, title = chapter_closed
        lines.append(f"Глава {number}: {title}" if title else f"Глава {number} закончена.")
    if offscreen:
        lines.append("За кадром:")
        lines += [f"— {text}" for text in offscreen]
    return lines


def fallback_summary(work, scene) -> str:
    # запасная выжимка без роли summarizer (тесты, инструменты): подсказка нарратора или строка
    if scene.summary:
        return scene.summary
    number = scene.id.removeprefix("scene_")
    place = work.world.locations.get(scene.location_id)
    name = scene.location_id if place is None else place.name
    return f"Сцена {number}: {name}, {work.world.clock.to_date()}"


def summarize_scene(work, cfg, registry, summarizer, run_id, result) -> None:
    # шаг 1 на копии: выжимка закрытой сцены в память; сбой summarizer -- исключение наверх
    chapter = ensure_chapter(work)
    scene = work.session.current_scene
    if any(s.id == scene.id for s in work.memory.scenes):
        # выжимка уже записана (граница, начатая до этапа 4)
        return
    if summarizer is None:
        title = scene.title
        text = fallback_summary(work, scene)
        source = "fallback"
    else:
        result.summary_run_id = run_id
        try:
            ctx = summarizer.run_scene(work, registry, cfg, run_id)
        except (TurnFailed, LlmError):
            result.failed_role = "summarizer"
            raise
        # название нарратора важнее
        title = scene.title or ctx.summary_title
        text = ctx.summary_text
        source = "summarizer"
    # world видит закрытую сцену с итоговой выжимкой
    scene.summary = text
    scene.title = title
    work.memory.scenes.append(
        SceneSummary(
            id=scene.id, chapter_id=chapter.id, title=title, summary=text,
            at_s=work.world.clock.now_s, source=source,
        )
    )


def tick_days(work, cfg, registry) -> None:
    # ход мира по дням: смертность, события, старость (rng бандла, состояние пишется обратно)
    rng = Rng.from_state(work.world.rng)
    tick.tick_days(work, rng, cfg, registry)
    work.world.rng = rng.state


def check_triggers(work, cfg, registry):
    # структурные триггеры: сработавшие и кандидаты для world
    return triggers.check(work)


def call_world(work, cfg, registry, check, world, run_id, result) -> None:
    # один пакетный вызов world по кандидатам; без кандидатов или без сессии world -- вызова нет
    if world is None:
        return
    candidates = list(check.candidates)
    sim = work.world.sim
    day = work.world.clock.now_s // DAY
    calls_today = sim.world_calls_today if sim.world_calls_day == day else 0
    limit = world.max_calls_per_day
    if limit > 0 and calls_today >= limit:
        # потолок: нарративные проверки откладываются до следующей границы, структурные then идут
        candidates = [c for c in candidates if c.kind == "act"]
    if not candidates:
        return
    sim.world_calls_day = day
    sim.world_calls_today = calls_today + 1
    result.world_run_id = run_id
    ctx = world.run(work, registry, cfg, candidates, run_id)
    verdicts.apply_verdicts(work, candidates, ctx.verdicts or {})
    result.report_tags += ctx.marks


def update_nudge(work, cfg, check) -> None:
    # подталкивание к основной линии; кандидаты ступени 3 и пометки идут в check.candidates
    nudge.step(work, check)


def close_chapter(work, cfg, registry, summarizer, run_id, result) -> tuple[int, str] | None:
    # шаг 3: глава закрыта -- свёртка summarizer (выжимка главы и новый game_summary);
    # без summarizer (тесты, инструменты) -- склейка выжимок сцен, game_summary не меняется
    chapter = ensure_chapter(work)
    if chapter.closed_reason is None and chapter.scene_count >= cfg.scene.max_per_chapter:
        chapter.closed_reason = "scene_limit"
    if chapter.closed_reason is None:
        return None
    if summarizer is None:
        texts = [s.summary for s in work.memory.scenes if s.chapter_id == chapter.id and s.summary]
        title = chapter.title
        text = " ".join(texts)
        source = "concat"
    else:
        result.summary_run_id = run_id
        try:
            ctx = summarizer.run_chapter(work, registry, cfg, run_id)
        except (TurnFailed, LlmError):
            result.failed_role = "summarizer"
            raise
        if not ctx.chapter_text or not ctx.game_text:
            result.failed_role = "summarizer"
            raise TurnFailed("invalid", "Summarizer не дал выжимку главы и game_summary.")
        # название нарратора важнее
        title = chapter.title or ctx.chapter_title_new
        text = ctx.chapter_text
        source = "summarizer"
        work.memory.game_summary = ctx.game_text
        work.memory.game_summary_chapter = chapter.number
    work.memory.chapters.append(
        ChapterSummary(
            id=chapter.id, number=chapter.number, title=title, summary=text, source=source,
            at_s=work.world.clock.now_s,
        )
    )
    for hero in work.heroes:
        hero.divine.intervention_chapter = None
    closed = (chapter.number, title)
    work.session.current_chapter = ChapterState(
        id=f"ch_{chapter.number + 1}", number=chapter.number + 1,
        started_at_s=work.world.clock.now_s,
    )
    return closed


def deliver_notices(work) -> list[str]:
    now = work.world.clock.now_s
    texts = []
    left = []
    for notice in work.world.notices:
        if notice.deliver_at_s <= now and notice.visibility != "hidden":
            texts.append(notice.text)
        else:
            left.append(notice)
    work.world.notices = left
    return texts


def finish_boundary(
    bundle, cfg, registry, world=None, run_id=None, summarizer=None
) -> BoundaryResult:
    # шаги 2-4: на копии; сбой -- бандл остаётся как был, boundary_pending=True;
    # world -- WorldSession (None: вызова роли world нет), summarizer -- SummarizerSession
    # (None: запасная выжимка), run_id -- id границы, общий для вызовов ролей
    work = bundle.model_copy(deep=True)
    result = BoundaryResult(bundle)
    try:
        summarize_scene(work, cfg, registry, summarizer, run_id, result)
        tick_days(work, cfg, registry)
        check = check_triggers(work, cfg, registry)
        # до вызова world: кандидат ступени 3 отдаётся ему в этом же вызове
        update_nudge(work, cfg, check)
        call_world(work, cfg, registry, check, world, run_id, result)
        result.chapter_closed = close_chapter(work, cfg, registry, summarizer, run_id, result)
        work.session.boundary_pending = False
        start_scene(work)
        # scene_count считает сцены главы, включая текущую
        work.session.current_chapter.scene_count += 1
        result.notices = deliver_notices(work)
    except (TurnFailed, LlmError) as error:
        result.chapter_closed = None
        result.notices = []
        result.error = f"{type(error).__name__}: {error}"
        return result
    result.bundle = work
    return result


def run(
    bundle, cfg, registry, reason, *, saves_root, saved_at, world=None, run_id=None,
    summarizer=None,
) -> BoundaryResult:
    close_boundary(bundle, cfg, reason)
    save_auto(saves_root, bundle, saved_at=saved_at, cfg=cfg)
    return finish_boundary(bundle, cfg, registry, world, run_id, summarizer)
