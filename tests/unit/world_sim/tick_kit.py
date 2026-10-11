# Помощники тестов тика мира (этап 3, партия 5). Не фикстуры pytest, а функции.
#
# КОНТРАКТ (STAGE3-PLAN A6, П5, ТЗ 4.1). Где план не даёт имён, они выбраны здесь -- это ТРЕБОВАНИЕ:
#   ai_dm.world_sim.tick.tick_days(bundle, rng, cfg, registry) -> list[DomainEvent]
#     часы мира (bundle.world.clock) двигает вызывающий; тик обрабатывает дни
#     sim.last_day + 1 .. clock.now_s // DAY по одному (порядок: смертность, истечение событий,
#     смена сезона, смена года) и ставит sim.last_day = clock.now_s // DAY.
#     Дней больше cfg.world.max_tick_days -> ValueError (бандл не проверяется).
#   Смертность: rng.randbelow(per_day_eff) == 0,
#     per_day_eff = mortality_per_day // max(1, множитель);
#     «отвести беду»: rng.randbelow(10) + 1 <= максимальная благосклонность существа;
#     смерть -> remove_creature/remove_hero(cause="chance"), события npc_died/hero_died в
#     результате, флаги npc_dead:/hero_dead:, запись хроники kind "death" с id в refs.
#   Старость: раз в игровой год (смена sim.last_year, год = now_s // calendar.seconds_in_year),
#     возраст = (now_s - birth_s) // seconds_in_year, таблица lifespan.yaml; бросок
#     rng.randbelow(100) < процент; cause="old_age". Минусы: NPC.aging_steps и строка хроники
#     (id в refs или в text), у героя один ActiveEffect(id="old_age", kind="old_age",
#     params={"steps": n}) в hero.creature.active_effects (нет шагов -- нет эффекта).
#   Сезон: смена имени clock.season() относительно sim.last_season -> ровно один
#     rng.randbelow(100) < world.natural.chance_percent_per_season; попадание -> GlobalEvent
#     kind="natural", cause="season:<новый сезон>", started_s -- день тика, ends_at_s = started_s +
#     duration вида, regions из вида; запись хроники kind "event". sim.last_season/last_year пустые
#     (last_season == "") -> первый тик только инициализирует их, без броска и без старости.
#   Событие закрывается тиком по ends_at_s (запись хроники kind "event" с id события в refs).
#   protocol (режим world): event_start / event_end -- WORLD_HANDLERS; нарратору недоступны.
from pathlib import Path

from ai_dm.core.clock import DAY
from ai_dm.core.rng import Rng

ROOT = Path(__file__).resolve().parents[3]
YEAR = 360 * DAY
# конец года 200 (по календарю мира 12 x 30): тики идут через границу года внутри одного сезона
LAST_DAY_OF_YEAR = 200 * 360 - 1
NEW_YEAR_NOW = 200 * YEAR + 3600


class QueueRng(Rng):
    # очереди граней по размеру кости; пустая очередь -> AssertionError, кроме default="high"
    # (последняя грань: ничего не выпадает) и n == 1
    def __init__(self, default=None, **queues):
        super().__init__(1)
        self.default = default
        self.queues = {name: list(faces) for name, faces in queues.items()}
        self.asked = []

    def randbelow(self, n):
        self.asked.append(n)
        if n == 1:
            return 0
        queue = self.queues.get(f"d{n}")
        if queue:
            return queue.pop(0) - 1
        assert self.default == "high", f"неожиданный бросок d{n}"
        return n - 1


def solo_hero(bundle):
    # в мире только герой: NPC и события убраны
    bundle.world.npcs.clear()
    bundle.world.events.clear()
    return bundle.heroes[0]


def solo_npc(bundle, npc_id="aldric"):
    # в мире только один NPC (герой в посмертии не бросает), события убраны
    npc = bundle.world.npcs[npc_id]
    bundle.world.npcs.clear()
    bundle.world.npcs[npc_id] = npc
    bundle.world.events.clear()
    bundle.heroes[0].status = "in_afterlife"
    return npc


def nobody(bundle):
    bundle.world.npcs.clear()
    bundle.world.events.clear()
    bundle.heroes[0].status = "in_afterlife"


def new_npc(npc_id, **fields):
    from ai_dm.state.world import NPC

    fields.setdefault("location_id", "town")
    return NPC(id=npc_id, name=npc_id, named=True, means=["связи"], **fields)


def run_tick(bundle, rng, registry, cfg, days=1):
    from ai_dm.world_sim.tick import tick_days

    bundle.world.clock.advance(days * DAY)
    return tick_days(bundle, rng, cfg, registry)


def at_year_end(bundle):
    # последний день года, тик уже сделан: следующий день -- новый год того же сезона (зима)
    bundle.world.clock.now_s = LAST_DAY_OF_YEAR * DAY + 3600
    bundle.world.sim.last_day = LAST_DAY_OF_YEAR
    bundle.world.sim.last_season = bundle.world.clock.season()
    bundle.world.sim.last_year = bundle.world.clock.now_s // YEAR


def birth_for_age(age):
    # возраст на день нового года; половина года запаса, чтобы год считался целым
    return NEW_YEAR_NOW - age * YEAR - YEAR // 2


def deaths_by(bundle, cause):
    return [
        n for n in bundle.world.npcs.values()
        if n.status == "dead" and n.death.cause == cause
    ]


def entries_with(bundle, ref, kind=None):
    return [
        e for e in bundle.chronicle.entries
        if (ref in e.refs or ref in e.text) and (kind is None or e.kind == kind)
    ]
