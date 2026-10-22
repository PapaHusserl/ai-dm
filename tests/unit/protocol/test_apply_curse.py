# У0 П3 (docs/plan-u0.md, «Дополнение: проклятие», Р7–Р8): инструмент curse{failed_roll_ref, cause}.
#   Гейт -- как у damage(deadly): failed_roll_ref должен быть ещё не потраченным ПРОВАЛОМ этого
#       хода; иначе rejected, report_tag curse_needs_fail, состояний нет (clamped нет: частичного
#       исполнения у проклятия нет).
#   Успех: герою добавляется AppliedCondition(id="cursed", source="master:t<turn_seq>"), ref
#       тратится (ctx.used_rolls), лог «Проклятие: <cause>», событие cursed в ctx.events.
#   Уже проклят -> rejected already_cursed (ref не тратится); мёртв -> Invalid hero_dead.
#   cause: strip и не больше 80 знаков. Один бросок -- одно последствие (общий с damage deadly).
import pytest
from protocol_kit import ScriptedRng, dump, make_ctx, req

from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.state.creature import AppliedCondition

CAUSE = "проклятый оберег на алтаре"


def failed_save(ctx):
    # проваленный спасбросок этого хода (d20 = 1, помеха на проклятом даст второй d20)
    return apply(ctx, req("saving_throw", ability="wis", category="very_hard")).result["roll_ref"]


def curse_ctx(registry, cfg, **queues):
    queues.setdefault("d20", [1])
    ctx = make_ctx(registry, cfg, ScriptedRng(**queues))
    ctx.bundle.session.turn_seq = 7
    return ctx


def curse(ctx, ref, cause=CAUSE):
    return apply(ctx, req("curse", failed_roll_ref=ref, cause=cause))


def ids(ctx):
    return [c.id for c in ctx.hero.creature.conditions]


# гейт: нет провала -> отказ

def test_curse_without_ref_is_rejected(registry, cfg):
    ctx = curse_ctx(registry, cfg)
    d = curse(ctx, "")
    assert isinstance(d, Decision)
    assert d.status == "rejected"
    assert d.report_tag == "curse_needs_fail"
    assert d.signal_to_master
    assert ids(ctx) == []


def test_curse_with_unknown_ref_is_rejected(registry, cfg):
    ctx = curse_ctx(registry, cfg)
    d = curse(ctx, "r99")
    assert d.status == "rejected"
    assert d.report_tag == "curse_needs_fail"
    assert ids(ctx) == []


def test_curse_with_ref_to_successful_roll_is_rejected(registry, cfg):
    ctx = curse_ctx(registry, cfg, d20=[20])
    ok = apply(ctx, req("saving_throw", ability="wis", category="very_easy"))
    assert ok.result["outcome"] == "success"
    d = curse(ctx, ok.result["roll_ref"])
    assert d.status == "rejected"
    assert d.report_tag == "curse_needs_fail"
    assert ids(ctx) == []


def test_curse_with_ref_to_failed_skill_check_is_accepted(registry, cfg):
    ctx = curse_ctx(registry, cfg)
    ref = apply(ctx, req("skill_check", skill="persuasion", category="hard")).result["roll_ref"]
    assert curse(ctx, ref).status == "accepted"
    assert ids(ctx) == ["cursed"]


def test_curse_with_ref_spent_by_deadly_damage_is_rejected(registry, cfg):
    ctx = curse_ctx(registry, cfg, d10=[5, 5, 5, 5])
    ref = failed_save(ctx)
    hit = apply(ctx, req("damage", severity="deadly", damage_type="fire", failed_roll_ref=ref))
    assert hit.status == "accepted"
    d = curse(ctx, ref)
    assert d.status == "rejected"
    assert d.report_tag == "curse_needs_fail"
    assert ids(ctx) == []


def test_deadly_damage_with_ref_spent_by_curse_is_clamped(registry, cfg):
    ctx = curse_ctx(registry, cfg, d10=[5, 5])
    ref = failed_save(ctx)
    assert curse(ctx, ref).status == "accepted"
    hit = apply(ctx, req("damage", severity="deadly", damage_type="fire", failed_roll_ref=ref))
    assert hit.status == "clamped"
    assert hit.report_tag == "limit-exceeded"


def test_ref_from_other_turn_does_not_curse(registry, cfg):
    old = curse_ctx(registry, cfg)
    ref = failed_save(old)
    ctx = curse_ctx(registry, cfg)
    assert curse(ctx, ref).status == "rejected"
    assert ids(ctx) == []


def test_rejected_curse_changes_nothing(registry, cfg):
    ctx = curse_ctx(registry, cfg)
    before = dump(ctx)
    curse(ctx, "")
    assert dump(ctx) == before
    assert ctx.events == []
    assert ctx.used_rolls == set()


# успех

def test_curse_adds_cursed_condition_with_master_source(registry, cfg):
    ctx = curse_ctx(registry, cfg)
    d = curse(ctx, failed_save(ctx))
    assert d.status == "accepted"
    assert d.report_tag is None
    assert d.signal_to_master is None
    assert ctx.hero.creature.conditions == [AppliedCondition(id="cursed", source="master:t7")]


def test_curse_spends_the_roll_ref(registry, cfg):
    ctx = curse_ctx(registry, cfg)
    ref = failed_save(ctx)
    curse(ctx, ref)
    assert ref in ctx.used_rolls


def test_curse_log_names_the_cause(registry, cfg):
    ctx = curse_ctx(registry, cfg)
    d = curse(ctx, failed_save(ctx))
    assert d.log == [f"Проклятие: {CAUSE}"]


def test_curse_result_reports_cursed_and_cause(registry, cfg):
    ctx = curse_ctx(registry, cfg)
    d = curse(ctx, failed_save(ctx))
    assert d.result == {"cursed": True, "cause": CAUSE}


def test_curse_emits_cursed_event_for_the_hero(registry, cfg):
    ctx = curse_ctx(registry, cfg)
    curse(ctx, failed_save(ctx))
    events = [e for e in ctx.events if e.type == "cursed"]
    assert len(events) == 1
    assert events[0].data == {"id": ctx.hero.id, "cause": CAUSE}


def test_curse_keeps_other_conditions(registry, cfg):
    ctx = curse_ctx(registry, cfg)
    ctx.hero.creature.conditions.append(AppliedCondition(id="poisoned"))
    curse(ctx, failed_save(ctx))
    assert ids(ctx) == ["poisoned", "cursed"]


def test_curse_cause_is_stripped(registry, cfg):
    ctx = curse_ctx(registry, cfg)
    d = curse(ctx, failed_save(ctx), cause="  оберег \n")
    assert d.result["cause"] == "оберег"
    assert d.log == ["Проклятие: оберег"]


def test_curse_cause_is_cut_to_80_chars(registry, cfg):
    ctx = curse_ctx(registry, cfg)
    d = curse(ctx, failed_save(ctx), cause="а" * 100)
    assert d.result["cause"] == "а" * 80
    assert d.log == ["Проклятие: " + "а" * 80]
    [event] = [e for e in ctx.events if e.type == "cursed"]
    assert event.data["cause"] == "а" * 80


def test_curse_cause_of_exactly_80_chars_is_kept(registry, cfg):
    ctx = curse_ctx(registry, cfg)
    d = curse(ctx, failed_save(ctx), cause="б" * 80)
    assert d.result["cause"] == "б" * 80


# уже проклят / мёртв

def test_second_curse_is_rejected_as_already_cursed(registry, cfg):
    ctx = curse_ctx(registry, cfg, d20=[1, 1, 1])
    assert curse(ctx, failed_save(ctx)).status == "accepted"
    d = curse(ctx, failed_save(ctx))
    assert d.status == "rejected"
    assert d.report_tag == "already_cursed"
    assert d.signal_to_master
    assert ids(ctx) == ["cursed"]


def test_already_cursed_does_not_spend_the_ref(registry, cfg):
    ctx = curse_ctx(registry, cfg, d20=[1, 1, 1])
    curse(ctx, failed_save(ctx))
    spent = set(ctx.used_rolls)
    ref = failed_save(ctx)
    curse(ctx, ref)
    assert ctx.used_rolls == spent
    assert ref not in ctx.used_rolls


def test_already_cursed_adds_no_event(registry, cfg):
    ctx = curse_ctx(registry, cfg, d20=[1, 1, 1])
    curse(ctx, failed_save(ctx))
    curse(ctx, failed_save(ctx))
    assert len([e for e in ctx.events if e.type == "cursed"]) == 1


def test_already_cursed_wins_over_missing_ref(registry, cfg):
    ctx = curse_ctx(registry, cfg)
    ctx.hero.creature.conditions.append(AppliedCondition(id="cursed"))
    assert curse(ctx, "").report_tag == "already_cursed"


def test_curse_dead_hero_is_invalid(registry, cfg):
    ctx = curse_ctx(registry, cfg)
    ref = failed_save(ctx)
    ctx.hero.status = "dead"
    before = dump(ctx)
    d = curse(ctx, ref)
    assert isinstance(d, Invalid)
    assert d.code == "hero_dead"
    assert dump(ctx) == before
    assert ctx.events == []


# последствия: помеха на следующих проверках

def test_cursed_hero_rolls_next_check_with_disadvantage(registry, cfg):
    ctx = curse_ctx(registry, cfg, d20=[1, 15, 4])
    curse(ctx, failed_save(ctx))
    apply(ctx, req("skill_check", skill="athletics", category="easy"))
    assert ctx.rng.calls == ["d20", "d20", "d20"]


def test_cursed_hero_rolls_saving_throw_with_two_dice(registry, cfg):
    ctx = curse_ctx(registry, cfg, d20=[10, 12])
    ctx.hero.creature.conditions.append(AppliedCondition(id="cursed"))
    d = apply(ctx, req("saving_throw", ability="con", category="easy"))
    assert d.status == "accepted"
    assert ctx.rng.calls == ["d20", "d20"]


# отдых, 0 HP и смена дня проклятие не снимают

def cursed_ctx(registry, cfg, **queues):
    ctx = curse_ctx(registry, cfg, **queues)
    ctx.hero.creature.conditions.append(AppliedCondition(id="cursed", source="master:t7"))
    return ctx


@pytest.mark.parametrize("kind", ["short", "long"])
def test_rest_keeps_the_curse(registry, cfg, kind):
    ctx = cursed_ctx(registry, cfg)
    ctx.hero.creature.hp_current = 1
    d = apply(ctx, req("rest", kind=kind))
    assert d.status == "accepted"
    assert ids(ctx) == ["cursed"]


def test_new_day_keeps_the_curse(registry, cfg):
    ctx = cursed_ctx(registry, cfg)
    assert apply(ctx, req("advance_time", category="week")).status == "accepted"
    assert ids(ctx) == ["cursed"]


def test_dropping_to_zero_hp_and_waking_keeps_the_curse(registry, cfg):
    from ai_dm.rules.healing import heal, remove_zero_hp_unconscious

    ctx = cursed_ctx(registry, cfg)
    ctx.hero.creature.hp_current = 0
    ctx.hero.creature.conditions.append(AppliedCondition(id="unconscious", source="0_hp"))
    heal(ctx.hero, 3)
    remove_zero_hp_unconscious(ctx.hero.creature)
    assert ids(ctx) == ["cursed"]


@pytest.mark.parametrize("severity", ["nuisance", "dangerous"])
def test_non_deadly_damage_ignores_the_gate_and_curse_state(registry, cfg, severity):
    ctx = curse_ctx(registry, cfg, d10=[3, 3])
    ctx.hero.creature.conditions.append(AppliedCondition(id="cursed"))
    d = apply(ctx, req("damage", severity=severity, damage_type="fire"))
    assert d.status == "accepted"
    assert ids(ctx) == ["cursed"]
