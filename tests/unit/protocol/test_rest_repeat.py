# ТМ (docs/TM-PLAN.md, §1 п.2): защита длинного отдыха от повтора (кулдаун).
#   rests.long_rest после clock.advance пишет hero.long_rest_end_s = clock.now_s (короткий отдых и
#     неудавшийся длинный -- нет).
#   rest_redundant(ctx, request) (ai_dm.protocol.handlers.resources): kind long,
#     long_rest_end_s задан, now_s < long_rest_end_s + cfg.limits.long_rest_cooldown
#     (по умолчанию "12h") -> Decision rejected
#     (reason "отдых уже был", signal с временем конца и временем следующего отдыха и словом
#     advance_time, report_tag "rest_repeat"); ровно на границе -- можно. Часы, HP, ресурсы,
#     prepared_swap / prey_swap при отказе не меняются. Короткий отдых не затронут; long_rest_end_s
#     None (старый сейв) -- можно. Порядок проверок: rest_redundant, swap_invalid, prey_invalid;
#     герой с 0 HP пропускается -- прежний Invalid rest_impossible из long_rest.
from pathlib import Path

import pytest
from protocol_kit import dump, make_bundle, make_ctx, req

from ai_dm.campaign.loader import load_pack, pack_content_dir
from ai_dm.config.settings import load_rules_config
from ai_dm.content.loader import load_registry
from ai_dm.core.clock import GameClock
from ai_dm.game.starter import new_world_from_pack
from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.rules.derived import clock_text
from ai_dm.rules.rests import long_rest

DRAGON = Path(__file__).resolve().parents[3] / "campaigns" / "drunk_dragon"
HOUR = 3600
DAY = 86400


def long_req(**fields):
    return req("rest", kind="long", **fields)


def rested(registry, cfg, end_s=None, now_s=None, hp=None, cooldown=None):
    # герой, чей длинный отдых кончился в end_s; часы мира на now_s
    if cooldown is not None:
        cfg = load_rules_config(f'[limits]\nlong_rest_cooldown = "{cooldown}"\n')
    bundle = make_bundle(registry)
    bundle.heroes[0].long_rest_end_s = end_s
    if now_s is not None:
        bundle.world.clock.now_s = now_s
    if hp is not None:
        bundle.heroes[0].creature.hp_current = hp
    return make_ctx(registry, cfg, bundle=bundle)


# rests.long_rest пишет отметку

def test_long_rest_marks_the_end_time(registry, cfg):
    ctx = rested(registry, cfg, now_s=1000)
    apply(ctx, long_req())
    assert ctx.hero.long_rest_end_s == 1000 + cfg.time.long_rest_s


def test_mark_equals_clock_after_rest(registry, cfg):
    ctx = rested(registry, cfg, now_s=5000)
    apply(ctx, long_req())
    assert ctx.hero.long_rest_end_s == ctx.bundle.world.clock.now_s


def test_rules_long_rest_marks_hero(registry, cfg):
    ctx = rested(registry, cfg)
    clock = GameClock(now_s=200)
    long_rest(ctx.hero, registry, clock, cfg)
    assert ctx.hero.long_rest_end_s == 200 + cfg.time.long_rest_s


def test_rules_long_rest_overwrites_old_mark(registry, cfg):
    ctx = rested(registry, cfg, end_s=10)
    clock = GameClock(now_s=100_000)
    long_rest(ctx.hero, registry, clock, cfg)
    assert ctx.hero.long_rest_end_s == clock.now_s


def test_failed_long_rest_at_zero_hp_leaves_mark(registry, cfg):
    ctx = rested(registry, cfg, hp=0)
    with pytest.raises(ValueError):
        long_rest(ctx.hero, registry, GameClock(now_s=100), cfg)
    assert ctx.hero.long_rest_end_s is None


def test_short_rest_does_not_mark(registry, cfg):
    ctx = rested(registry, cfg)
    apply(ctx, req("rest", kind="short"))
    assert ctx.hero.long_rest_end_s is None


def test_hero_default_has_no_mark(registry, cfg):
    assert rested(registry, cfg).hero.long_rest_end_s is None


# сценарий vale: повторный отдых

def test_first_long_rest_is_accepted(registry, cfg):
    ctx = rested(registry, cfg)
    assert apply(ctx, long_req()).status == "accepted"


def test_repeat_right_after_rest_is_rejected(registry, cfg):
    ctx = rested(registry, cfg)
    apply(ctx, long_req())
    d = apply(ctx, long_req())
    assert isinstance(d, Decision)
    assert d.status == "rejected"


def test_repeat_has_report_tag_rest_repeat(registry, cfg):
    ctx = rested(registry, cfg)
    apply(ctx, long_req())
    assert apply(ctx, long_req()).report_tag == "rest_repeat"


def test_repeat_is_rejected_not_invalid(registry, cfg):
    ctx = rested(registry, cfg)
    apply(ctx, long_req())
    assert not isinstance(apply(ctx, long_req()), Invalid)


def test_repeat_does_not_move_the_clock(registry, cfg):
    ctx = rested(registry, cfg)
    apply(ctx, long_req())
    now = ctx.bundle.world.clock.now_s
    apply(ctx, long_req())
    assert ctx.bundle.world.clock.now_s == now


def test_repeat_does_not_change_the_bundle(registry, cfg):
    ctx = rested(registry, cfg)
    apply(ctx, long_req())
    before = dump(ctx)
    apply(ctx, long_req())
    assert dump(ctx) == before


def test_repeat_does_not_heal(registry, cfg):
    ctx = rested(registry, cfg, end_s=1000, now_s=2000, hp=5)
    apply(ctx, long_req())
    assert ctx.hero.creature.hp_current == 5


def test_repeat_keeps_the_mark(registry, cfg):
    ctx = rested(registry, cfg, end_s=1000, now_s=2000)
    apply(ctx, long_req())
    assert ctx.hero.long_rest_end_s == 1000


def test_repeat_has_no_log_lines(registry, cfg):
    ctx = rested(registry, cfg, end_s=1000, now_s=2000)
    assert apply(ctx, long_req()).log == []


def test_signal_names_end_and_next_time_and_advance_time(registry, cfg):
    end_s = 20 * HOUR
    ctx = rested(registry, cfg, end_s=end_s, now_s=end_s + HOUR)
    signal = apply(ctx, long_req()).signal_to_master
    assert clock_text(end_s) in signal
    assert clock_text(end_s + 12 * HOUR) in signal
    assert "advance_time" in signal


def test_signal_next_time_follows_configured_cooldown(registry, cfg):
    end_s = 20 * HOUR
    ctx = rested(registry, cfg, end_s=end_s, now_s=end_s, cooldown="16h")
    signal = apply(ctx, long_req()).signal_to_master
    assert clock_text(end_s + 16 * HOUR) in signal


# граница кулдауна

def test_one_second_before_the_boundary_is_rejected(registry, cfg):
    end_s = 100_000
    ctx = rested(registry, cfg, end_s=end_s, now_s=end_s + 12 * HOUR - 1)
    assert apply(ctx, long_req()).status == "rejected"


def test_exactly_on_the_boundary_is_accepted(registry, cfg):
    end_s = 100_000
    ctx = rested(registry, cfg, end_s=end_s, now_s=end_s + 12 * HOUR)
    assert apply(ctx, long_req()).status == "accepted"


def test_after_the_boundary_is_accepted(registry, cfg):
    end_s = 100_000
    ctx = rested(registry, cfg, end_s=end_s, now_s=end_s + 12 * HOUR + 1)
    assert apply(ctx, long_req()).status == "accepted"


def test_accepted_after_cooldown_moves_the_mark(registry, cfg):
    end_s = 100_000
    now = end_s + 13 * HOUR
    ctx = rested(registry, cfg, end_s=end_s, now_s=now)
    apply(ctx, long_req())
    assert ctx.hero.long_rest_end_s == now + cfg.time.long_rest_s


def test_rest_advance_twelve_hours_then_rest_again(registry, cfg):
    ctx = rested(registry, cfg)
    apply(ctx, long_req())
    ctx.bundle.world.clock.advance(12 * HOUR)
    assert apply(ctx, long_req()).status == "accepted"


def test_cooldown_zero_hours_never_blocks(registry, cfg):
    ctx = rested(registry, cfg, end_s=1000, now_s=1000, cooldown="0h")
    assert apply(ctx, long_req()).status == "accepted"


def test_cooldown_sixteen_hours_rejects_at_twelve(registry, cfg):
    end_s = 100_000
    ctx = rested(registry, cfg, end_s=end_s, now_s=end_s + 12 * HOUR, cooldown="16h")
    assert apply(ctx, long_req()).status == "rejected"


def test_cooldown_sixteen_hours_accepts_at_sixteen(registry, cfg):
    end_s = 100_000
    ctx = rested(registry, cfg, end_s=end_s, now_s=end_s + 16 * HOUR, cooldown="16h")
    assert apply(ctx, long_req()).status == "accepted"


def test_cooldown_in_days_is_parsed(registry, cfg):
    end_s = 100_000
    ctx = rested(registry, cfg, end_s=end_s, now_s=end_s + DAY - 1, cooldown="1d")
    assert apply(ctx, long_req()).status == "rejected"


def test_old_save_without_mark_is_accepted(registry, cfg):
    ctx = rested(registry, cfg, end_s=None, now_s=0)
    assert apply(ctx, long_req()).status == "accepted"


def test_mark_zero_is_a_real_mark(registry, cfg):
    # end_s == 0 не «нет отметки»: проверка по None, не по truthiness
    ctx = rested(registry, cfg, end_s=0, now_s=HOUR)
    assert apply(ctx, long_req()).status == "rejected"


# короткий отдых не затронут

def test_short_rest_inside_cooldown_is_accepted(registry, cfg):
    ctx = rested(registry, cfg, end_s=1000, now_s=2000)
    assert apply(ctx, req("rest", kind="short")).status == "accepted"


def test_short_rest_inside_cooldown_moves_clock(registry, cfg):
    ctx = rested(registry, cfg, end_s=1000, now_s=2000)
    apply(ctx, req("rest", kind="short"))
    assert ctx.bundle.world.clock.now_s == 2000 + cfg.time.short_rest_s


def test_short_rest_does_not_touch_the_mark(registry, cfg):
    ctx = rested(registry, cfg, end_s=1000, now_s=2000)
    apply(ctx, req("rest", kind="short"))
    assert ctx.hero.long_rest_end_s == 1000


# порядок проверок: 0 HP -- прежний Invalid rest_impossible

def test_zero_hp_inside_cooldown_keeps_invalid_rest_impossible(registry, cfg):
    ctx = rested(registry, cfg, end_s=1000, now_s=2000, hp=0)
    d = apply(ctx, long_req())
    assert isinstance(d, Invalid)
    assert d.code == "rest_impossible"


def test_zero_hp_inside_cooldown_changes_nothing(registry, cfg):
    ctx = rested(registry, cfg, end_s=1000, now_s=2000, hp=0)
    before = dump(ctx)
    apply(ctx, long_req())
    assert dump(ctx) == before


def test_zero_hp_after_cooldown_is_still_invalid(registry, cfg):
    ctx = rested(registry, cfg, end_s=1000, now_s=1000 + 13 * HOUR, hp=0)
    d = apply(ctx, long_req())
    assert isinstance(d, Invalid)
    assert d.code == "rest_impossible"


def test_zero_hp_without_mark_is_invalid_as_before(registry, cfg):
    ctx = rested(registry, cfg, hp=0)
    d = apply(ctx, long_req())
    assert isinstance(d, Invalid)
    assert d.code == "rest_impossible"


def test_one_hp_inside_cooldown_is_rejected(registry, cfg):
    ctx = rested(registry, cfg, end_s=1000, now_s=2000, hp=1)
    assert apply(ctx, long_req()).status == "rejected"


def test_dead_hero_inside_cooldown_keeps_invalid(registry, cfg):
    ctx = rested(registry, cfg, end_s=1000, now_s=2000, hp=0)
    ctx.hero.status = "dead"
    d = apply(ctx, long_req())
    assert isinstance(d, Invalid)
    assert d.code == "rest_impossible"


# swap'ы: при отказе не применяются, плохой swap -- Invalid раньше кулдауна

@pytest.fixture
def dragon(cfg):
    registry = load_registry([pack_content_dir(DRAGON)])
    bundle = new_world_from_pack(
        registry, cfg, load_pack(DRAGON, registry), hero="grey", seed=1, world_id="w1",
        saved_at="2026-01-01T00:00:00",
    )
    # Добыча (prey_swap) есть только у охотника
    sheet = bundle.heroes[0].sheet
    sheet.primary.subclass_id = "hunter"
    sheet.feature_choices = {"hunters_prey": ["colossus_slayer"]}
    return registry, bundle


def dragon_ctx(cfg, dragon, end_s, now_s):
    registry, bundle = dragon
    bundle.heroes[0].long_rest_end_s = end_s
    bundle.world.clock.now_s = now_s
    return make_ctx(registry, cfg, bundle=bundle)


def test_rejected_rest_does_not_apply_prepared_swap(cfg, dragon):
    ctx = dragon_ctx(cfg, dragon, 1000, 2000)
    before = list(ctx.hero.sheet.prepared_of())
    d = apply(ctx, long_req(prepared_swap={"drop": ["fog_cloud"], "take": ["longstrider"]}))
    assert d.status == "rejected"
    assert ctx.hero.sheet.prepared_of() == before


def test_rejected_rest_does_not_apply_prey_swap(cfg, dragon):
    ctx = dragon_ctx(cfg, dragon, 1000, 2000)
    d = apply(ctx, long_req(prey_swap="horde_breaker"))
    assert d.status == "rejected"
    assert ctx.hero.sheet.feature_choices["hunters_prey"] == ["colossus_slayer"]


def test_prey_swap_is_applied_when_rest_is_allowed(cfg, dragon):
    ctx = dragon_ctx(cfg, dragon, 1000, 1000 + 13 * HOUR)
    d = apply(ctx, long_req(prey_swap="horde_breaker"))
    assert d.status == "accepted"
    assert ctx.hero.sheet.feature_choices["hunters_prey"] == ["horde_breaker"]


def test_swap_is_applied_when_rest_is_allowed(cfg, dragon):
    ctx = dragon_ctx(cfg, dragon, 1000, 1000 + 13 * HOUR)
    d = apply(ctx, long_req(prepared_swap={"drop": ["fog_cloud"], "take": ["longstrider"]}))
    assert d.status == "accepted"
    assert "longstrider" in ctx.hero.sheet.prepared_of()


def test_bad_swap_inside_cooldown_is_rejected_not_invalid(cfg, dragon):
    # повтор проверяется первым: мягкий отказ, бюджет невалидных не тратится (ревью ТМ п.2)
    ctx = dragon_ctx(cfg, dragon, 1000, 2000)
    d = apply(ctx, long_req(prepared_swap={"drop": ["no_such_spell"], "take": ["longstrider"]}))
    assert not isinstance(d, Invalid)
    assert d.status == "rejected"
    assert d.report_tag == "rest_repeat"


def test_bad_prey_inside_cooldown_is_rejected_not_invalid(cfg, dragon):
    ctx = dragon_ctx(cfg, dragon, 1000, 2000)
    d = apply(ctx, long_req(prey_swap="no_such_prey"))
    assert not isinstance(d, Invalid)
    assert d.report_tag == "rest_repeat"


def test_bad_swap_after_cooldown_is_invalid(cfg, dragon):
    ctx = dragon_ctx(cfg, dragon, 1000, 1000 + 13 * HOUR)
    d = apply(ctx, long_req(prepared_swap={"drop": ["no_such_spell"], "take": ["longstrider"]}))
    assert isinstance(d, Invalid)


def test_bad_prey_after_cooldown_is_invalid(cfg, dragon):
    ctx = dragon_ctx(cfg, dragon, 1000, 1000 + 13 * HOUR)
    assert isinstance(apply(ctx, long_req(prey_swap="no_such_prey")), Invalid)


def test_short_rest_with_swap_inside_cooldown_is_still_swap_long_only(cfg, dragon):
    ctx = dragon_ctx(cfg, dragon, 1000, 2000)
    swap = {"drop": ["fog_cloud"], "take": ["longstrider"]}
    d = apply(ctx, req("rest", kind="short", prepared_swap=swap))
    assert isinstance(d, Invalid)
    assert d.code == "swap_long_only"
