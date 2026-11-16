# К8с П1: строка лога короткого отдыха о снятом истощении (Неутомимость, ранг 10).
# «Неутомимость: истощение снижено до N»; без истощения или без умения строки нет.
import game_kit  # noqa: F401  (добавляет в sys.path соседние kit-ы)
from protocol_kit import make_bundle, make_ctx, req
from ranger_kit import ranger_at

from ai_dm.protocol.apply import apply


def short_rest_log(registry, cfg, level, exhaustion):
    bundle = make_bundle(registry)
    hero = ranger_at(registry, level)
    hero.location_id = bundle.heroes[0].location_id
    hero.creature.hp_current = 5
    hero.creature.exhaustion = exhaustion
    bundle.heroes[0] = hero
    ctx = make_ctx(registry, cfg, bundle=bundle)
    return apply(ctx, req("rest", kind="short")).log


def test_short_rest_logs_lowered_exhaustion(registry, cfg):
    log = short_rest_log(registry, cfg, 10, 2)
    assert "Неутомимость: истощение снижено до 1" in log


def test_short_rest_without_exhaustion_has_no_tireless_line(registry, cfg):
    log = short_rest_log(registry, cfg, 10, 0)
    assert not any("Неутомимость" in line for line in log)


def test_short_rest_of_ranger_9_has_no_tireless_line(registry, cfg):
    log = short_rest_log(registry, cfg, 9, 2)
    assert not any("Неутомимость" in line for line in log)
