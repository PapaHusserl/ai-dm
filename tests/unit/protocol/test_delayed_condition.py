# М0 П4а (docs/plan-m0.md, «Умолчания» п. 26, решения 125, 126): запрос delayed_condition --
# мастер откладывает состояние «Болен» (diseased; список -- ключ конфига [time] delayed_conditions).
#   Запись в world.pending(at_s, target, kind="condition", ref=<состояние>, text=<текст мастера>),
#   ответ accepted, log пуст, в result -- at_s; состояния на цели ещё нет.
#   Герою -- только по проваленному броску этого хода (как curse); NPC -- без броска.
#   Повтор и цель с состоянием -- rejected; неизвестные цель/состояние, мёртвая цель,
#   hours < 1 -- Invalid.
#   NPC без creature получает его при постановке.
import pytest
from protocol_kit import ScriptedRng, dump, make_ctx, req

from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.state.creature import AppliedCondition
from ai_dm.state.world import PendingEvent

HOUR = 3600
DAY = 86400
NOW = DAY + 22 * HOUR + 1800  # 22:30
TEXT = "Началась лихорадка"


def delayed_ctx(registry, cfg, **queues):
    queues.setdefault("d20", [1])
    ctx = make_ctx(registry, cfg, ScriptedRng(**queues))
    ctx.bundle.world.clock.now_s = NOW
    return ctx


def delay(ctx, **fields):
    fields.setdefault("target", "aldric")
    fields.setdefault("condition", "diseased")
    fields.setdefault("when", "morning")
    fields.setdefault("text", TEXT)
    return apply(ctx, req("delayed_condition", **fields))


def failed_save(ctx):
    return apply(ctx, req("saving_throw", ability="wis", category="very_hard")).result["roll_ref"]


def pending(ctx):
    return ctx.bundle.world.pending


# постановка на NPC (без броска)

def test_morning_event_is_queued_for_six_next_day(registry, cfg):
    ctx = delayed_ctx(registry, cfg)
    d = delay(ctx)
    assert isinstance(d, Decision)
    assert d.status == "accepted"
    assert [(e.at_s, e.target, e.kind, e.ref) for e in pending(ctx)] == [
        (2 * DAY + 6 * HOUR, "aldric", "condition", "diseased")
    ]
    assert d.result["at_s"] == 2 * DAY + 6 * HOUR


def test_accepted_request_gives_no_log_line_and_no_condition_yet(registry, cfg):
    ctx = delayed_ctx(registry, cfg)
    d = delay(ctx)
    assert d.log == []
    assert [c.id for c in ctx.bundle.world.npcs["aldric"].creature.conditions] == []


def test_master_text_is_stored_as_is(registry, cfg):
    ctx = delayed_ctx(registry, cfg)
    delay(ctx)
    assert pending(ctx)[0].text == TEXT


def test_master_text_is_cut_to_80_characters(registry, cfg):
    ctx = delayed_ctx(registry, cfg)
    delay(ctx, text="я" * 120)
    assert pending(ctx)[0].text == "я" * 80


def test_master_text_is_stripped_before_it_is_stored(registry, cfg):
    ctx = delayed_ctx(registry, cfg)
    delay(ctx, text=f"  {TEXT}  ")
    assert pending(ctx)[0].text == TEXT


def test_master_text_is_stripped_before_the_cut_to_80(registry, cfg):
    ctx = delayed_ctx(registry, cfg)
    delay(ctx, text="   " + "я" * 80 + "   ")
    assert pending(ctx)[0].text == "я" * 80


@pytest.mark.parametrize("text", ["", "   ", " \n\t "], ids=["empty", "spaces", "whitespace"])
def test_empty_text_is_invalid_and_changes_nothing(registry, cfg, text):
    ctx = delayed_ctx(registry, cfg)
    before = dump(ctx)
    d = delay(ctx, text=text)
    assert isinstance(d, Invalid)
    assert d.code == "empty_text"
    assert dump(ctx) == before


def test_hours_event_is_queued_after_that_many_hours(registry, cfg):
    ctx = delayed_ctx(registry, cfg)
    d = delay(ctx, when="hours", hours=3)
    assert d.status == "accepted"
    assert pending(ctx)[0].at_s == NOW + 10800


def test_morning_before_six_is_the_same_day(registry, cfg):
    ctx = delayed_ctx(registry, cfg)
    ctx.bundle.world.clock.now_s = DAY + 3 * HOUR
    delay(ctx)
    assert pending(ctx)[0].at_s == DAY + 6 * HOUR


def test_npc_without_creature_gets_one_and_no_condition(registry, cfg):
    ctx = delayed_ctx(registry, cfg)
    npc = ctx.bundle.world.npcs["aldric"]
    assert npc.creature is None
    delay(ctx)
    assert npc.creature is not None
    assert npc.creature.conditions == []


# повтор и состояние уже есть

def test_repeat_while_the_record_lies_is_rejected_and_record_stays_single(registry, cfg):
    ctx = delayed_ctx(registry, cfg)
    delay(ctx)
    d = delay(ctx)
    assert d.status == "rejected"
    assert d.signal_to_master
    assert len(pending(ctx)) == 1


def test_target_already_carrying_the_condition_is_rejected(registry, cfg):
    ctx = delayed_ctx(registry, cfg)
    delay(ctx)
    ctx.bundle.world.pending = []
    ctx.bundle.world.npcs["aldric"].creature.conditions = [
        AppliedCondition(id="diseased", source="x")
    ]
    d = delay(ctx)
    assert d.status == "rejected"
    assert pending(ctx) == []


# Invalid: dump не меняется

@pytest.mark.parametrize(
    "fields",
    [
        {"target": "nobody"},
        {"condition": "no_such_condition"},
        {"when": "hours", "hours": 0},
        {"when": "hours", "hours": -5},
        {"when": "hours"},
    ],
    ids=["unknown_target", "unknown_condition", "hours_zero", "hours_negative", "hours_missing"],
)
def test_bad_request_is_invalid_and_changes_nothing(registry, cfg, fields):
    ctx = delayed_ctx(registry, cfg)
    before = dump(ctx)
    d = delay(ctx, **fields)
    assert isinstance(d, Invalid)
    assert dump(ctx) == before


@pytest.mark.parametrize(
    ("fields", "code"),
    [
        ({"target": "nobody"}, "unknown_target"),
        ({"condition": "no_such_condition"}, "unknown_condition"),
        ({"when": "hours", "hours": 0}, "bad_hours"),
        ({"when": "hours"}, "bad_hours"),
    ],
    ids=["unknown_target", "unknown_condition", "hours_zero", "hours_missing"],
)
def test_bad_request_has_its_code(registry, cfg, fields, code):
    d = delay(delayed_ctx(registry, cfg), **fields)
    assert d.code == code


def test_dead_npc_has_the_target_dead_code(registry, cfg):
    ctx = delayed_ctx(registry, cfg)
    ctx.bundle.world.npcs["aldric"].status = "dead"
    assert delay(ctx).code == "target_dead"


def test_one_hour_is_the_smallest_accepted_delay(registry, cfg):
    ctx = delayed_ctx(registry, cfg)
    d = delay(ctx, when="hours", hours=1)
    assert d.status == "accepted"
    assert pending(ctx)[0].at_s == NOW + HOUR


def test_record_of_another_target_with_the_same_condition_is_no_repeat(registry, cfg):
    ctx = delayed_ctx(registry, cfg)
    ctx.bundle.world.pending = [
        PendingEvent(at_s=NOW + 1, target="hero", kind="condition", ref="diseased", text="x")
    ]
    assert delay(ctx).status == "accepted"
    assert len(pending(ctx)) == 2


def test_record_of_the_same_target_with_another_condition_is_no_repeat(registry, cfg):
    ctx = delayed_ctx(registry, cfg)
    ctx.bundle.world.pending = [
        PendingEvent(at_s=NOW + 1, target="aldric", kind="condition", ref="other", text="x")
    ]
    assert delay(ctx).status == "accepted"
    assert len(pending(ctx)) == 2


def test_npc_with_a_monster_gets_its_hp_not_one(registry, cfg):
    ctx = delayed_ctx(registry, cfg)
    npc = ctx.bundle.world.npcs["aldric"]
    npc.combat = {"monster_id": "goblin_warrior", "label": "Воин-гоблин 1"}
    delay(ctx)
    assert (npc.creature.hp_current, npc.creature.hp_max) == (10, 10)


def test_npc_without_a_monster_gets_one_hp(registry, cfg):
    ctx = delayed_ctx(registry, cfg)
    npc = ctx.bundle.world.npcs["aldric"]
    delay(ctx)
    assert (npc.creature.hp_current, npc.creature.hp_max) == (1, 1)


def test_dead_npc_is_invalid_and_changes_nothing(registry, cfg):
    ctx = delayed_ctx(registry, cfg)
    ctx.bundle.world.npcs["aldric"].status = "dead"
    before = dump(ctx)
    assert isinstance(delay(ctx), Invalid)
    assert dump(ctx) == before


def test_dead_hero_is_invalid_and_changes_nothing(registry, cfg):
    ctx = delayed_ctx(registry, cfg)
    ref = failed_save(ctx)
    ctx.hero.status = "dead"
    before = dump(ctx)
    assert isinstance(delay(ctx, target="hero", failed_roll_ref=ref), Invalid)
    assert dump(ctx) == before


# герой: только после проваленного броска этого хода

def test_hero_without_roll_ref_is_rejected(registry, cfg):
    ctx = delayed_ctx(registry, cfg)
    d = delay(ctx, target="hero")
    assert d.status == "rejected"
    assert d.signal_to_master
    assert pending(ctx) == []


def test_hero_with_unknown_ref_is_rejected(registry, cfg):
    ctx = delayed_ctx(registry, cfg)
    d = delay(ctx, target="hero", failed_roll_ref="r99")
    assert d.status == "rejected"
    assert pending(ctx) == []


def test_hero_with_ref_to_successful_roll_is_rejected(registry, cfg):
    ctx = delayed_ctx(registry, cfg, d20=[20])
    ok = apply(ctx, req("saving_throw", ability="wis", category="very_easy"))
    assert ok.result["outcome"] == "success"
    d = delay(ctx, target="hero", failed_roll_ref=ok.result["roll_ref"])
    assert d.status == "rejected"
    assert pending(ctx) == []


def test_hero_with_failed_roll_is_queued_and_spends_the_ref(registry, cfg):
    ctx = delayed_ctx(registry, cfg)
    ref = failed_save(ctx)
    d = delay(ctx, target="hero", failed_roll_ref=ref)
    assert d.status == "accepted"
    assert [(e.target, e.ref) for e in pending(ctx)] == [("hero", "diseased")]
    assert ref in ctx.used_rolls
    assert [c.id for c in ctx.hero.creature.conditions] == []


def test_hero_empty_text_is_invalid_and_does_not_spend_the_ref(registry, cfg):
    ctx = delayed_ctx(registry, cfg)
    ref = failed_save(ctx)
    d = delay(ctx, target="hero", failed_roll_ref=ref, text="  ")
    assert isinstance(d, Invalid)
    assert ref not in ctx.used_rolls
    again = delay(ctx, target="hero", failed_roll_ref=ref)
    assert again.status == "accepted"
    assert [(e.target, e.text) for e in pending(ctx)] == [("hero", TEXT)]


def test_npc_needs_no_roll(registry, cfg):
    ctx = delayed_ctx(registry, cfg)
    assert delay(ctx, target="aldric").status == "accepted"
