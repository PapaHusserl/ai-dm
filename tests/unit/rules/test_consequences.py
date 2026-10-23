# У1 П3 (docs/plan-u1.md, решения 16-19, 29): rules/consequences.py -- последствия платной близости.
#   Каждая проверка возвращает None (проверки нет: СЛ в risks = 0) или кортеж
#   (id последствия | None, строки лога, сигнал мастеру | None).
#   disease_check(ctx, kind, npc) -- спасбросок Телосложения СЛ risks.disease_dc; провал (< СЛ):
#     AppliedCondition("diseased", source="service:<npc>"), событие diseased {id, source},
#     строка «<герой>: болезнь».
#   Кортеж из 4 элементов: последний -- roll_ref спасброска (ctx.rolls и ctx.engine_rolls), у
#   jealousy None. Ревность: штраф вне per_scene, событие betrayal, вес записи памяти > 0.
#   theft_check(ctx, kind, npc) -- спасбросок Мудрости СЛ risks.theft_dc; провал: spend_money на
#     1к4 x 10 % кошелька, не больше 10 зм (1000 мм), событие robbed {id, by}, строка
#     «Кошелёк полегчал на ...»; потеря 0 -- только строка броска.
#   loves_hero(npc, hero) -- активная цель love на героя или romance в памяти.
#   jealousy(ctx, npc) -- спутники героя (follows == hero.id, живые, в его локации), любящие героя:
#     отношение -attitude.step (нижняя граница -100), в памяти сцены один betrayal
#     «измена: платная близость с <имя>»; None, если никого.
from protocol_kit import ScriptedRng, make_ctx

from ai_dm.rules.checks import saving_throw
from ai_dm.rules.consequences import disease_check, jealousy, loves_hero, theft_check
from ai_dm.rules.derived import saving_throw_bonus
from ai_dm.state.creature import ActiveEffect, AppliedCondition, Expiry
from ai_dm.state.relations import NpcEvent, NpcGoal, NpcSceneMemory
from ai_dm.state.world import NPC


def provider(**fields):
    fields.setdefault("location_id", "vale")
    return NPC(id="grok", name="Грок", means=["компания"], **fields)


def make(registry, cfg, rng=None, money=1000):
    ctx = make_ctx(registry, cfg, rng)
    ctx.hero.money_cp = money
    return ctx


def kind_of(cfg, name="companion_cheap"):
    return cfg.services.kinds[name]


def fail_face(ctx, ability, dc):
    return dc - saving_throw_bonus(ctx.hero, ctx.registry, ability) - 1


def pass_face(ctx, ability, dc):
    return dc - saving_throw_bonus(ctx.hero, ctx.registry, ability)


def disease_ctx(registry, cfg, face_for):
    # face_for: fail_face / pass_face; companion_cheap: болезнь СЛ 10
    probe = make(registry, cfg)
    face = face_for(probe, "con", kind_of(cfg).risks.disease_dc)
    return make(registry, cfg, ScriptedRng(d20=[face]))


def theft_ctx(registry, cfg, face_for, d4=(1,), money=1000):
    # companion_cheap: кража СЛ 12
    probe = make(registry, cfg)
    face = face_for(probe, "wis", kind_of(cfg).risks.theft_dc)
    return make(registry, cfg, ScriptedRng(d20=[face], d4=list(d4)), money=money)


def sick(ctx):
    return [c for c in ctx.hero.creature.conditions if c.id == "diseased"]


# disease_check

def test_disease_check_without_dc_is_none_and_rolls_nothing(registry, cfg):
    ctx = make(registry, cfg, ScriptedRng())
    assert disease_check(ctx, kind_of(cfg, "companion_fine"), provider()) is None
    assert ctx.rng.calls == []


def test_disease_check_rolls_one_d20(registry, cfg):
    ctx = disease_ctx(registry, cfg, fail_face)
    disease_check(ctx, kind_of(cfg), provider())
    assert ctx.rng.calls == ["d20"]


def test_disease_check_success_returns_only_the_roll_line(registry, cfg):
    ctx = disease_ctx(registry, cfg, pass_face)
    key, lines, signal, _ref =disease_check(ctx, kind_of(cfg), provider())
    assert key is None
    assert signal is None
    assert len(lines) == 1


def test_disease_check_roll_line_is_constitution_save_against_dc(registry, cfg):
    ctx = disease_ctx(registry, cfg, pass_face)
    _key, lines, _signal, _ref =disease_check(ctx, kind_of(cfg), provider())
    assert "Тел" in lines[0]
    assert "10" in lines[0]


def test_disease_check_success_applies_nothing(registry, cfg):
    ctx = disease_ctx(registry, cfg, pass_face)
    disease_check(ctx, kind_of(cfg), provider())
    assert sick(ctx) == []
    assert ctx.events == []


def test_disease_check_total_equal_to_dc_is_success(registry, cfg):
    ctx = disease_ctx(registry, cfg, pass_face)
    key, _lines, _signal, _ref =disease_check(ctx, kind_of(cfg), provider())
    assert key is None


def test_disease_check_fail_applies_diseased_from_the_provider(registry, cfg):
    ctx = disease_ctx(registry, cfg, fail_face)
    disease_check(ctx, kind_of(cfg), provider())
    [condition] = sick(ctx)
    assert condition.source == "service:grok"


def test_disease_check_fail_returns_key_lines_and_signal(registry, cfg):
    ctx = disease_ctx(registry, cfg, fail_face)
    key, lines, signal, _ref =disease_check(ctx, kind_of(cfg), provider())
    assert key == "diseased"
    assert len(lines) == 2
    assert lines[1] == f"{ctx.hero.name}: болезнь"
    assert "болезнь" in signal


def test_disease_check_fail_emits_diseased_event(registry, cfg):
    ctx = disease_ctx(registry, cfg, fail_face)
    disease_check(ctx, kind_of(cfg), provider())
    [event] = ctx.events
    assert event.type == "diseased"
    assert event.data == {"id": ctx.hero.id, "source": "grok"}


def test_disease_check_fail_keeps_other_conditions(registry, cfg):
    ctx = disease_ctx(registry, cfg, fail_face)
    ctx.hero.creature.conditions.append(AppliedCondition(id="poisoned"))
    disease_check(ctx, kind_of(cfg), provider())
    assert [c.id for c in ctx.hero.creature.conditions] == ["poisoned", "diseased"]


def test_disease_check_fail_when_already_sick_does_not_duplicate(registry, cfg):
    ctx = disease_ctx(registry, cfg, fail_face)
    ctx.hero.creature.conditions.append(AppliedCondition(id="diseased", source="service:old"))
    key, _lines, _signal, _ref =disease_check(ctx, kind_of(cfg), provider())
    [condition] = sick(ctx)
    assert condition.source == "service:old"
    assert key == "diseased"


def test_disease_check_fail_signal_text(registry, cfg):
    ctx = disease_ctx(registry, cfg, fail_face)
    _key, _lines, signal, _ref = disease_check(ctx, kind_of(cfg), provider())
    assert signal == "Герой подхватил болезнь: опиши недомогание по факту."


def expired_advantage_save():
    # эффект с адвантажем на спасброски, истёкший к текущему моменту мира
    return ActiveEffect(
        id="blessed", source="service:x", kind="modifier",
        params={"target": "saving_throw", "mode": "advantage"},
        expires=Expiry(kind="seconds", value=0),
    )


def test_disease_check_passes_world_time_to_the_roll(registry, cfg):
    ctx = disease_ctx(registry, cfg, fail_face)
    ctx.bundle.world.clock.advance(100)
    ctx.hero.creature.active_effects.append(expired_advantage_save())
    disease_check(ctx, kind_of(cfg), provider())
    assert ctx.rng.calls == ["d20"]


def test_theft_check_passes_world_time_to_the_roll(registry, cfg):
    ctx = theft_ctx(registry, cfg, fail_face)
    ctx.bundle.world.clock.advance(100)
    ctx.hero.creature.active_effects.append(expired_advantage_save())
    theft_check(ctx, kind_of(cfg), provider())
    assert ctx.rng.calls[0] == "d20"
    assert ctx.rng.calls.count("d20") == 1


def test_theft_ref_is_attributed_to_the_hero(registry, cfg):
    ctx = theft_ctx(registry, cfg, fail_face)
    *_head, ref = theft_check(ctx, kind_of(cfg), provider())
    assert ctx.roll_actors[ref] == ctx.hero.id


def test_disease_check_does_not_touch_money(registry, cfg):
    ctx = disease_ctx(registry, cfg, fail_face)
    disease_check(ctx, kind_of(cfg), provider())
    assert ctx.hero.money_cp == 1000


def test_disease_check_uses_the_dc_of_the_kind(registry, cfg):
    # у companion_common СЛ 5: на грани companion_cheap (СЛ 10) тот же бросок проходит
    probe = make(registry, cfg)
    face = fail_face(probe, "con", kind_of(cfg).risks.disease_dc)
    ctx = make(registry, cfg, ScriptedRng(d20=[face]))
    key, _lines, _signal, _ref =disease_check(ctx, kind_of(cfg, "companion_common"), provider())
    assert key is None


# theft_check

def test_theft_check_without_dc_is_none_and_rolls_nothing(registry, cfg):
    ctx = make(registry, cfg, ScriptedRng())
    assert theft_check(ctx, kind_of(cfg, "companion_fine"), provider()) is None
    assert ctx.rng.calls == []


def test_theft_check_success_keeps_money_and_rolls_no_d4(registry, cfg):
    ctx = theft_ctx(registry, cfg, pass_face)
    key, lines, signal, _ref =theft_check(ctx, kind_of(cfg), provider())
    assert (key, signal) == (None, None)
    assert len(lines) == 1
    assert ctx.hero.money_cp == 1000
    assert ctx.rng.calls == ["d20"]
    assert ctx.events == []


def test_theft_check_roll_line_is_wisdom_save(registry, cfg):
    ctx = theft_ctx(registry, cfg, pass_face)
    _key, lines, _signal, _ref =theft_check(ctx, kind_of(cfg), provider())
    assert "Мдр" in lines[0]
    assert "12" in lines[0]


def test_theft_check_total_equal_to_dc_is_success(registry, cfg):
    ctx = theft_ctx(registry, cfg, pass_face)
    key, _lines, _signal, _ref =theft_check(ctx, kind_of(cfg), provider())
    assert key is None


def test_theft_check_fail_takes_d4_times_ten_percent(registry, cfg):
    ctx = theft_ctx(registry, cfg, fail_face, d4=(3,), money=1000)
    theft_check(ctx, kind_of(cfg), provider())
    assert ctx.hero.money_cp == 700
    assert ctx.rng.calls == ["d20", "d4"]


def test_theft_check_minimum_roll_takes_ten_percent(registry, cfg):
    ctx = theft_ctx(registry, cfg, fail_face, d4=(1,), money=500)
    theft_check(ctx, kind_of(cfg), provider())
    assert ctx.hero.money_cp == 450


def test_theft_check_maximum_roll_takes_forty_percent(registry, cfg):
    ctx = theft_ctx(registry, cfg, fail_face, d4=(4,), money=500)
    theft_check(ctx, kind_of(cfg), provider())
    assert ctx.hero.money_cp == 300


def test_theft_check_loss_is_capped_at_ten_gold(registry, cfg):
    ctx = theft_ctx(registry, cfg, fail_face, d4=(4,), money=10000)
    theft_check(ctx, kind_of(cfg), provider())
    assert ctx.hero.money_cp == 9000


def test_theft_check_loss_exactly_at_the_cap_is_taken_whole(registry, cfg):
    ctx = theft_ctx(registry, cfg, fail_face, d4=(1,), money=10000)
    theft_check(ctx, kind_of(cfg), provider())
    assert ctx.hero.money_cp == 9000


def test_theft_check_loss_just_below_the_cap_is_not_rounded_up(registry, cfg):
    ctx = theft_ctx(registry, cfg, fail_face, d4=(1,), money=9990)
    theft_check(ctx, kind_of(cfg), provider())
    assert ctx.hero.money_cp == 9990 - 999


def test_theft_check_percent_is_rounded_down(registry, cfg):
    ctx = theft_ctx(registry, cfg, fail_face, d4=(2,), money=17)
    theft_check(ctx, kind_of(cfg), provider())
    assert ctx.hero.money_cp == 17 - 3


def test_theft_check_fail_returns_key_log_line_and_signal(registry, cfg):
    ctx = theft_ctx(registry, cfg, fail_face, d4=(3,), money=1000)
    key, lines, signal, _ref =theft_check(ctx, kind_of(cfg), provider())
    assert key == "robbed"
    assert len(lines) == 2
    assert lines[1] == "Кошелёк полегчал на 3 зм"
    assert "Кошелёк" in signal


def test_theft_check_fail_emits_robbed_event(registry, cfg):
    ctx = theft_ctx(registry, cfg, fail_face, d4=(2,))
    theft_check(ctx, kind_of(cfg), provider())
    [event] = ctx.events
    assert event.type == "robbed"
    assert event.data == {"id": ctx.hero.id, "by": "grok"}


def test_theft_check_fail_with_empty_purse_loses_nothing(registry, cfg):
    ctx = theft_ctx(registry, cfg, fail_face, d4=(4,), money=0)
    key, lines, signal, _ref =theft_check(ctx, kind_of(cfg), provider())
    assert (key, signal) == (None, None)
    assert len(lines) == 1
    assert ctx.hero.money_cp == 0
    assert ctx.events == []


def test_theft_check_fail_with_loss_rounding_to_zero_has_no_event(registry, cfg):
    ctx = theft_ctx(registry, cfg, fail_face, d4=(1,), money=5)
    key, _lines, _signal, _ref =theft_check(ctx, kind_of(cfg), provider())
    assert key is None
    assert ctx.hero.money_cp == 5
    assert ctx.events == []


def test_theft_check_fail_leaves_conditions_alone(registry, cfg):
    ctx = theft_ctx(registry, cfg, fail_face)
    theft_check(ctx, kind_of(cfg), provider())
    assert ctx.hero.creature.conditions == []


# loves_hero

def goal(kind="love", target="hero", status="active"):
    return NpcGoal(kind=kind, target=target, since_s=0, status=status)


def memory_of(*kinds):
    events = [NpcEvent(kind=k, turn_seq=1, text="x") for k in kinds]
    return NpcSceneMemory(scene_id="s0", at_s=0, weight=0, events=events)


def lover(**fields):
    fields.setdefault("location_id", "vale")
    return NPC(id="lira", name="Лира", means=["спутница"], **fields)


def test_loves_hero_with_active_love_goal(registry, cfg):
    ctx = make(registry, cfg)
    assert loves_hero(lover(goals=[goal()]), ctx.hero) is True


def test_loves_hero_with_romance_in_memory(registry, cfg):
    ctx = make(registry, cfg)
    assert loves_hero(lover(memory=[memory_of("helped", "romance")]), ctx.hero) is True


def test_loves_hero_false_for_done_love_goal(registry, cfg):
    ctx = make(registry, cfg)
    assert loves_hero(lover(goals=[goal(status="done")]), ctx.hero) is False


def test_loves_hero_false_for_dropped_love_goal(registry, cfg):
    ctx = make(registry, cfg)
    assert loves_hero(lover(goals=[goal(status="dropped")]), ctx.hero) is False


def test_loves_hero_false_for_love_goal_on_someone_else(registry, cfg):
    ctx = make(registry, cfg)
    assert loves_hero(lover(goals=[goal(target="grok")]), ctx.hero) is False


def test_loves_hero_false_for_other_goal_kind(registry, cfg):
    ctx = make(registry, cfg)
    assert loves_hero(lover(goals=[goal(kind="gratitude")]), ctx.hero) is False


def test_loves_hero_false_for_deal_memory_only(registry, cfg):
    ctx = make(registry, cfg)
    assert loves_hero(lover(memory=[memory_of("deal")]), ctx.hero) is False


def test_loves_hero_false_for_stranger(registry, cfg):
    ctx = make(registry, cfg)
    assert loves_hero(lover(), ctx.hero) is False


# jealousy

def jealous_ctx(registry, cfg, attitude=50, **fields):
    ctx = make(registry, cfg)
    fields.setdefault("follows", ctx.hero.id)
    fields.setdefault("goals", [goal(target=ctx.hero.id)])
    ctx.bundle.world.npcs["lira"] = lover(attitude=attitude, **fields)
    ctx.bundle.world.npcs["grok"] = provider()
    return ctx


def lira(ctx):
    return ctx.bundle.world.npcs["lira"]


def betrayals(npc):
    return [e for m in npc.memory for e in m.events if e.kind == "betrayal"]


def test_jealousy_lowers_attitude_by_one_step(registry, cfg):
    ctx = jealous_ctx(registry, cfg, attitude=50)
    jealousy(ctx, ctx.bundle.world.npcs["grok"])
    assert lira(ctx).attitude == 40


def test_jealousy_returns_key_log_line_and_signal(registry, cfg):
    ctx = jealous_ctx(registry, cfg, attitude=50)
    key, lines, signal, _ref =jealousy(ctx, ctx.bundle.world.npcs["grok"])
    assert key == "jealousy"
    assert lines == ["Лира: измена раскрыта, отношение -10"]
    assert signal == "Спутник, любящий героя, узнал о платной близости: опиши реакцию."


def test_jealousy_writes_betrayal_into_scene_memory(registry, cfg):
    ctx = jealous_ctx(registry, cfg)
    jealousy(ctx, ctx.bundle.world.npcs["grok"])
    [event] = betrayals(lira(ctx))
    assert event.text == "измена: платная близость с Грок"
    assert event.turn_seq == ctx.turn_seq


def test_jealousy_step_follows_config(registry, cfg):
    ctx = jealous_ctx(registry, cfg, attitude=50)
    ctx.cfg = cfg.model_copy(deep=True)
    ctx.cfg.attitude.step = 4
    jealousy(ctx, ctx.bundle.world.npcs["grok"])
    assert lira(ctx).attitude == 46


def test_jealousy_attitude_is_clamped_at_minus_100(registry, cfg):
    ctx = jealous_ctx(registry, cfg, attitude=-95)
    _key, lines, _signal, _ref =jealousy(ctx, ctx.bundle.world.npcs["grok"])
    assert lira(ctx).attitude == -100
    assert lines == ["Лира: измена раскрыта, отношение -5"]


def test_jealousy_romance_in_memory_is_enough(registry, cfg):
    ctx = jealous_ctx(registry, cfg, goals=[], memory=[memory_of("romance")])
    key, _lines, _signal, _ref =jealousy(ctx, ctx.bundle.world.npcs["grok"])
    assert key == "jealousy"
    assert lira(ctx).attitude == 40


def test_jealousy_second_time_in_scene_lowers_attitude_but_keeps_one_betrayal(registry, cfg):
    ctx = jealous_ctx(registry, cfg, attitude=50)
    jealousy(ctx, ctx.bundle.world.npcs["grok"])
    jealousy(ctx, ctx.bundle.world.npcs["grok"])
    assert lira(ctx).attitude == 30
    assert len(betrayals(lira(ctx))) == 1


def test_jealousy_without_scene_lowers_attitude_without_memory(registry, cfg):
    ctx = jealous_ctx(registry, cfg, attitude=50)
    ctx.bundle.session.current_scene = None
    key, _lines, _signal, _ref =jealousy(ctx, ctx.bundle.world.npcs["grok"])
    assert key == "jealousy"
    assert lira(ctx).attitude == 40
    assert lira(ctx).memory == []


def test_jealousy_two_lovers_both_react(registry, cfg):
    ctx = jealous_ctx(registry, cfg, attitude=50)
    ctx.bundle.world.npcs["mara"] = NPC(
        id="mara", name="Мара", means=["спутница"], location_id="vale", follows=ctx.hero.id,
        attitude=20, goals=[goal(target=ctx.hero.id)],
    )
    _key, lines, _signal, _ref =jealousy(ctx, ctx.bundle.world.npcs["grok"])
    assert len(lines) == 2
    assert ctx.bundle.world.npcs["mara"].attitude == 10
    assert lira(ctx).attitude == 40


def test_jealousy_none_when_nobody_follows_the_hero(registry, cfg):
    ctx = jealous_ctx(registry, cfg, follows=None)
    assert jealousy(ctx, ctx.bundle.world.npcs["grok"]) is None
    assert lira(ctx).attitude == 50


def test_jealousy_none_when_npc_follows_someone_else(registry, cfg):
    ctx = jealous_ctx(registry, cfg, follows="other_hero")
    assert jealousy(ctx, ctx.bundle.world.npcs["grok"]) is None
    assert lira(ctx).attitude == 50


def test_jealousy_none_when_lover_is_in_another_location(registry, cfg):
    ctx = jealous_ctx(registry, cfg, location_id="forest")
    assert jealousy(ctx, ctx.bundle.world.npcs["grok"]) is None
    assert lira(ctx).attitude == 50


def test_jealousy_none_when_lover_is_dead(registry, cfg):
    ctx = jealous_ctx(registry, cfg, status="dead")
    assert jealousy(ctx, ctx.bundle.world.npcs["grok"]) is None
    assert lira(ctx).attitude == 50


def test_jealousy_none_when_follower_does_not_love_the_hero(registry, cfg):
    ctx = jealous_ctx(registry, cfg, goals=[])
    assert jealousy(ctx, ctx.bundle.world.npcs["grok"]) is None
    assert lira(ctx).attitude == 50
    assert lira(ctx).memory == []


def test_jealousy_does_not_hit_the_provider_itself(registry, cfg):
    ctx = jealous_ctx(registry, cfg, attitude=50)
    grok = ctx.bundle.world.npcs["grok"]
    grok.follows = ctx.hero.id
    grok.goals = [goal(target=ctx.hero.id)]
    grok.attitude = 50
    jealousy(ctx, grok)
    assert grok.attitude == 50
    assert lira(ctx).attitude == 40


def test_jealousy_has_no_roll_ref(registry, cfg):
    ctx = jealous_ctx(registry, cfg)
    *_head, ref = jealousy(ctx, ctx.bundle.world.npcs["grok"])
    assert ref is None
    assert ctx.rolls == {}


def test_jealousy_does_not_spend_scene_attitude_limit(registry, cfg):
    ctx = jealous_ctx(registry, cfg)
    jealousy(ctx, ctx.bundle.world.npcs["grok"])
    assert ctx.scene.attitude_spent == {}


def test_jealousy_betrayal_entry_has_positive_weight(registry, cfg):
    ctx = jealous_ctx(registry, cfg, attitude=50)
    jealousy(ctx, ctx.bundle.world.npcs["grok"])
    [entry] = lira(ctx).memory
    assert entry.weight == 10


def test_jealousy_clamped_weight_is_the_applied_change(registry, cfg):
    ctx = jealous_ctx(registry, cfg, attitude=-95)
    jealousy(ctx, ctx.bundle.world.npcs["grok"])
    [entry] = lira(ctx).memory
    assert entry.weight == 5


def test_jealousy_emits_betrayal_event(registry, cfg):
    ctx = jealous_ctx(registry, cfg)
    jealousy(ctx, ctx.bundle.world.npcs["grok"])
    [event] = ctx.events
    assert event.type == "betrayal"
    assert event.data == {"id": "lira", "hero": ctx.hero.id, "with": "grok"}


def test_jealousy_emits_event_for_each_lover(registry, cfg):
    ctx = jealous_ctx(registry, cfg)
    ctx.bundle.world.npcs["mara"] = NPC(
        id="mara", name="Мара", means=["спутница"], location_id="vale", follows=ctx.hero.id,
        goals=[goal(target=ctx.hero.id)],
    )
    jealousy(ctx, ctx.bundle.world.npcs["grok"])
    assert sorted(e.data["id"] for e in ctx.events) == ["lira", "mara"]


def test_jealousy_without_lovers_emits_no_event(registry, cfg):
    ctx = jealous_ctx(registry, cfg, goals=[])
    jealousy(ctx, ctx.bundle.world.npcs["grok"])
    assert ctx.events == []


# roll_ref спасбросков: в ctx.rolls и ctx.engine_rolls

def test_disease_ref_is_in_rolls_and_engine_rolls_on_success(registry, cfg):
    ctx = disease_ctx(registry, cfg, pass_face)
    *_head, ref = disease_check(ctx, kind_of(cfg), provider())
    assert ref in ctx.rolls
    assert ref in ctx.engine_rolls
    assert ctx.rolls[ref].outcome == "success"


def test_disease_ref_is_in_engine_rolls_on_fail(registry, cfg):
    ctx = disease_ctx(registry, cfg, fail_face)
    *_head, ref = disease_check(ctx, kind_of(cfg), provider())
    assert ctx.rolls[ref].outcome == "fail"
    assert ref in ctx.engine_rolls
    assert ctx.roll_actors[ref] == ctx.hero.id


def test_theft_ref_is_in_rolls_and_engine_rolls(registry, cfg):
    ctx = theft_ctx(registry, cfg, fail_face)
    *_head, ref = theft_check(ctx, kind_of(cfg), provider())
    assert ctx.rolls[ref].outcome == "fail"
    assert ref in ctx.engine_rolls


def test_theft_ref_is_returned_even_when_loss_is_zero(registry, cfg):
    ctx = theft_ctx(registry, cfg, fail_face, d4=(1,), money=5)
    *_head, ref = theft_check(ctx, kind_of(cfg), provider())
    assert ref in ctx.engine_rolls


def test_two_checks_get_distinct_refs(registry, cfg):
    probe = make(registry, cfg)
    faces = [fail_face(probe, "wis", 12), fail_face(probe, "con", 10)]
    ctx = make(registry, cfg, ScriptedRng(d20=faces, d4=[1]))
    *_a, theft_ref = theft_check(ctx, kind_of(cfg), provider())
    *_b, disease_ref = disease_check(ctx, kind_of(cfg), provider())
    assert theft_ref != disease_ref
    assert ctx.engine_rolls == {theft_ref, disease_ref}


def test_add_roll_engine_flag_marks_ref_and_plain_call_does_not(registry, cfg):
    ctx = make(registry, cfg, ScriptedRng(d20=[1, 1]))
    result = saving_throw(ctx.hero, registry, ctx.rng, "wis", dc=30)
    plain = ctx.add_roll(result, ctx.hero.id)
    engine = ctx.add_roll(result, ctx.hero.id, engine=True)
    assert plain in ctx.rolls and engine in ctx.rolls
    assert ctx.engine_rolls == {engine}
