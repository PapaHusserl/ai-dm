# Общие помощники тестов world_sim (этап 3, партия 3). Не фикстуры pytest, а функции.
# Бандл собирается из статического мини-пака tests/fixtures/packs/mini/ (3 локации, 4 NPC, фракция
# guild, боги selune/morrah). Импорты ai_dm.world_sim.* -- внутри функций: пока слоя нет, тесты
# падают по одному (red), а не весь сбор.
#
# КОНТРАКТ (STAGE3-PLAN A6, A4 «Кандидаты», П3). Где план не даёт имён, они выбраны здесь --
# это ТРЕБОВАНИЕ к реализации:
#   ai_dm.world_sim.triggers.check(bundle) -> CheckResult  (меняет бандл: fire + world.fired +
#       хроника). Время -- bundle.world.clock.now_s, герой -- bundle с current_hero_id.
#     CheckResult.fired: list[str] -- ref сработавших на этой проверке триггеров (ref содержит id
#       владельца и id триггера); CheckResult.candidates: list -- кандидаты для роли world.
#     Кандидат (атрибуты или ключи словаря): ref ("trigger:<owner>:<id>" / "secret:<npc>:<id>"),
#       kind ("verdict" | "act"), then (для act --
#       текст then триггера), residual (для verdict с триггером -- остаток условия, не None).
#       Секретный verdict: ref содержит id секрета.
#     Порядок кандидатов: вид владельца god, faction, npc; затем id владельца; затем id триггера.
#     Сработавший триггер: fired_count += 1, last_fired_at = now_s, once -> state "fired";
#       world.fired += FiredTrigger(ref, at_s); bundle.chronicle.entries += запись kind "trigger"
#       (refs содержат ref или id триггера).
#     Мёртвый NPC (status != "alive") не срабатывает и не даёт кандидатов.
#     Бог проверяется не чаще раза в god.check_every_days игровых дней: первая проверка идёт
#       сразу, следующая -- не раньше, чем через N дней после ПРЕДЫДУЩЕЙ ПРОВЕРКИ (а не после
#       срабатывания; проверка без срабатывания тоже считается).
#     Секреты: verdict-кандидат -- секрет NPC в локации сцены (current_scene.location_id), условие
#       NEEDS_NARRATIVE, narrative_ok False, revealed False; структурно истинный секрет
#       движок сам не раскрывает (раскрывает мастер запросом reveal_secret).
#   ai_dm.world_sim.candidates / chronicle -- внутренние модули; тестируются через check().
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MINI_DIR = ROOT / "tests" / "fixtures" / "packs" / "mini"
SAVED_AT = "2026-10-03T12:00:00Z"
DAY = 86400


def mini_bundle(registry, cfg, seed=1):
    from ai_dm.campaign.loader import load_pack
    from ai_dm.game.starter import new_world_from_pack

    pack = load_pack(MINI_DIR, registry)
    return new_world_from_pack(
        registry, cfg, pack, hero="arn", seed=seed, world_id="w1", saved_at=SAVED_AT
    )


def run_check(bundle):
    from ai_dm.world_sim.triggers import check

    return check(bundle)


def field(candidate, name):
    # кандидат -- объект или словарь
    if isinstance(candidate, dict):
        return candidate[name]
    return getattr(candidate, name)


def refs_of(result, kind=None):
    return [
        field(c, "ref") for c in result.candidates if kind is None or field(c, "kind") == kind
    ]


def has_ref(refs, *parts):
    return any(all(part in ref for part in parts) for ref in refs)


def trigger_of(bundle, owner_id, trigger_id):
    world = bundle.world
    for group in (world.npcs, world.factions, world.pantheon):
        if owner_id in group:
            return next(t for t in group[owner_id].opportunity if t.id == trigger_id)
    raise KeyError(owner_id)
