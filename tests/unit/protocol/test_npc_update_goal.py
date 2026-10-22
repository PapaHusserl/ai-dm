# Ж2 коммит 2 (docs/plan-zh2.md, п. 0.5-0.6, F2 вне боя): цели NPC через npc_update.
#   NpcUpdateBase: goal_kind (none | GOAL_KINDS), goal_target ("" = герой), goal_text ("" =
#   goals.NARRATIVE[kind]), goal_status (none | done | dropped);
#   * goal_kind + нет goal_status -> цель (мишень NPC -> add_npc_goal, иначе add_goal);
#   * goal_kind + goal_status -> закрыть активную цель (done | dropped), спутник disabled;
#   * Invalid: goal_fields_without_kind (target/text/status без вида), unknown_goal_target,
#     goal_exists (повтор активной), no_such_goal (закрыть нечего); отказ ничего не меняет;
#   * цель одна -- допустимое изменение (не empty_update), и у рассказчика, и у роли world;
#   * status=dead + by=герой (рассказчик и world) -> goals.on_npc_killed: мстители у родни и отряда.
import pytest
from protocol_kit import ScriptedRng, dump, make_bundle, make_ctx, req

from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.protocol.requests import NpcUpdate, WorldNpcUpdate, parse_request
from ai_dm.protocol.schema import tool_defs
from ai_dm.rules import goals
from ai_dm.state.relations import GOAL_KINDS, FamilyLink
from ai_dm.state.world import NPC

HERO = "hero"


def update(ctx, **fields):
    return apply(ctx, req("npc_update", npc_id="aldric", **fields))


def aldric(ctx):
    return ctx.bundle.world.npcs["aldric"]


def active_goals(npc):
    return [g for g in npc.goals if g.status == "active"]


def companion(npc, kind="revenge", target=HERO):
    return next(t for t in npc.opportunity if t.id == f"goal:{kind}:{target}")


# запрос и схема

def test_goal_neutrals():
    assert NpcUpdate.NEUTRAL["goal_kind"] == "none"
    assert NpcUpdate.NEUTRAL["goal_target"] == ""
    assert NpcUpdate.NEUTRAL["goal_text"] == ""
    assert NpcUpdate.NEUTRAL["goal_status"] == "none"
    assert WorldNpcUpdate.NEUTRAL["goal_kind"] == "none"


def test_goal_fields_absent_in_parsed_request_are_none():
    request = req("npc_update", npc_id="aldric", attitude_delta=1)
    got = (request.goal_kind, request.goal_target, request.goal_text, request.goal_status)
    assert got == (None, None, None, None)


@pytest.mark.parametrize("kind", GOAL_KINDS)
def test_every_goal_kind_is_parsed(kind):
    assert req("npc_update", npc_id="aldric", goal_kind=kind).goal_kind == kind


def test_unknown_goal_kind_is_rejected_by_parser():
    with pytest.raises(ValueError):
        req("npc_update", npc_id="aldric", goal_kind="hobby")


def test_unknown_goal_status_is_rejected_by_parser():
    with pytest.raises(ValueError):
        req("npc_update", npc_id="aldric", goal_kind="revenge", goal_status="paused")


@pytest.mark.parametrize("role", [None, "world"])
def test_tool_schema_has_required_goal_fields(role):
    args = (["npc_update"], role) if role else (["npc_update"],)
    schema = tool_defs(*args)[0]["input_schema"]
    for name in ("goal_kind", "goal_target", "goal_text", "goal_status"):
        assert name in schema["properties"]
        assert name in schema["required"]
        assert schema["properties"][name]["description"]


def test_tool_schema_goal_kind_enum_has_all_kinds_and_none():
    schema = tool_defs(["npc_update"])[0]["input_schema"]
    assert set(schema["properties"]["goal_kind"]["enum"]) == {*GOAL_KINDS, "none"}


def test_tool_schema_goal_status_enum():
    schema = tool_defs(["npc_update"])[0]["input_schema"]
    assert set(schema["properties"]["goal_status"]["enum"]) == {"none", "done", "dropped"}


# постановка цели

def test_goal_on_hero_by_default(registry, cfg):
    ctx = make_ctx(registry, cfg)
    now_s = ctx.bundle.world.clock.now_s
    decision = update(ctx, goal_kind="revenge")
    assert isinstance(decision, Decision)
    assert decision.status == "accepted"
    [goal] = aldric(ctx).goals
    assert (goal.kind, goal.target, goal.status, goal.since_s) == ("revenge", HERO, "active", now_s)
    assert goal.text == goals.NARRATIVE["revenge"]


def test_goal_with_explicit_hero_target(registry, cfg):
    ctx = make_ctx(registry, cfg)
    update(ctx, goal_kind="debt", goal_target=HERO)
    assert [(g.kind, g.target) for g in aldric(ctx).goals] == [("debt", HERO)]


def test_goal_text_is_kept_when_given(registry, cfg):
    ctx = make_ctx(registry, cfg)
    update(ctx, goal_kind="love", goal_text="тайно влюблён в героя")
    assert aldric(ctx).goals[0].text == "тайно влюблён в героя"


@pytest.mark.parametrize("kind", GOAL_KINDS)
def test_empty_goal_text_is_narrative_of_kind(registry, cfg, kind):
    ctx = make_ctx(registry, cfg)
    update(ctx, goal_kind=kind)
    assert aldric(ctx).goals[0].text == goals.NARRATIVE[kind]


def test_goal_creates_companion_trigger_for_hero(registry, cfg):
    ctx = make_ctx(registry, cfg)
    update(ctx, goal_kind="revenge", goal_text="мстит")
    trigger = companion(aldric(ctx))
    assert trigger.then == "мстит"
    assert trigger.state == "active"
    assert "hero_dead" in str(trigger.if_)


def test_goal_on_npc_target_uses_npc_companion(registry, cfg):
    ctx = make_ctx(registry, cfg)
    update(ctx, goal_kind="rivalry", goal_target="grakh")
    [goal] = aldric(ctx).goals
    assert (goal.kind, goal.target) == ("rivalry", "grakh")
    trigger = companion(aldric(ctx), "rivalry", "grakh")
    assert "npc_status" in str(trigger.if_)
    assert "hero_dead" not in str(trigger.if_)


def test_goal_on_hero_target_uses_hero_companion_not_npc_one(registry, cfg):
    ctx = make_ctx(registry, cfg)
    update(ctx, goal_kind="revenge")
    assert "npc_status" not in str(companion(aldric(ctx)).if_)


def test_goal_log_line_names_the_kind(registry, cfg):
    ctx = make_ctx(registry, cfg)
    decision = update(ctx, goal_kind="gratitude")
    assert decision.log == ["Олдрик: новая цель gratitude"]


def test_goal_log_uses_label_for_hidden_name(registry, cfg):
    ctx = make_ctx(registry, cfg)
    npc = aldric(ctx)
    npc.origin, npc.combat = "engine", {"monster_id": "goblin_warrior", "label": "Воин-гоблин 1"}
    decision = update(ctx, goal_kind="gratitude")
    assert decision.log == ["Воин-гоблин 1: новая цель gratitude"]


def test_goal_alone_is_not_empty_update(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert not isinstance(update(ctx, goal_kind="love"), Invalid)


def test_update_without_any_change_is_still_empty(registry, cfg):
    ctx = make_ctx(registry, cfg)
    result = update(ctx, goal_kind="none")
    assert isinstance(result, Invalid)
    assert result.code == "empty_update"


def test_goal_goes_together_with_attitude(registry, cfg):
    ctx = make_ctx(registry, cfg)
    decision = update(ctx, goal_kind="revenge", attitude_delta=-5)
    assert decision.status == "accepted"
    assert aldric(ctx).attitude == -5
    assert len(aldric(ctx).goals) == 1


def test_two_goals_of_different_kind_on_same_target(registry, cfg):
    ctx = make_ctx(registry, cfg)
    update(ctx, goal_kind="revenge")
    update(ctx, goal_kind="debt")
    assert [g.kind for g in aldric(ctx).goals] == ["revenge", "debt"]


def test_same_kind_on_other_target_is_separate_goal(registry, cfg):
    ctx = make_ctx(registry, cfg)
    update(ctx, goal_kind="rivalry")
    update(ctx, goal_kind="rivalry", goal_target="grakh")
    assert [g.target for g in aldric(ctx).goals] == [HERO, "grakh"]


def test_goal_after_closed_same_goal_is_allowed_again(registry, cfg):
    ctx = make_ctx(registry, cfg)
    update(ctx, goal_kind="revenge")
    update(ctx, goal_kind="revenge", goal_status="done")
    again = update(ctx, goal_kind="revenge", goal_text="снова")
    assert again.status == "accepted"
    assert [g.status for g in aldric(ctx).goals] == ["done", "active"]
    assert companion(aldric(ctx)).state == "active"


# отказы при постановке

def test_unknown_goal_target_is_invalid_and_changes_nothing(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    result = update(ctx, goal_kind="revenge", goal_target="nobody", attitude_delta=3)
    assert isinstance(result, Invalid)
    assert result.code == "unknown_goal_target"
    assert "nobody" in result.message
    assert dump(ctx) == before


def test_unknown_goal_target_message_lists_known_npcs(registry, cfg):
    ctx = make_ctx(registry, cfg)
    result = update(ctx, goal_kind="revenge", goal_target="nobody")
    assert "grakh" in result.message


def test_goal_target_can_be_any_hero_of_bundle(registry, cfg):
    ctx = make_ctx(registry, cfg)
    second = ctx.bundle.heroes[0].model_copy(deep=True)
    second.id = "zed"
    ctx.bundle.heroes.append(second)
    assert update(ctx, goal_kind="revenge", goal_target="zed").status == "accepted"
    assert aldric(ctx).goals[0].target == "zed"


def test_goal_on_himself_is_allowed_target_check_only(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert not isinstance(update(ctx, goal_kind="love", goal_target="aldric"), Invalid)


def test_repeat_of_active_goal_is_goal_exists(registry, cfg):
    ctx = make_ctx(registry, cfg)
    update(ctx, goal_kind="revenge", goal_text="первое")
    before = dump(ctx)
    result = update(ctx, goal_kind="revenge", goal_text="второе", attitude_delta=4)
    assert isinstance(result, Invalid)
    assert result.code == "goal_exists"
    assert "revenge" in result.message and HERO in result.message
    assert dump(ctx) == before


def test_goal_exists_for_npc_target(registry, cfg):
    ctx = make_ctx(registry, cfg)
    update(ctx, goal_kind="rivalry", goal_target="grakh")
    assert update(ctx, goal_kind="rivalry", goal_target="grakh").code == "goal_exists"


def test_unknown_target_is_reported_before_goal_exists(registry, cfg):
    ctx = make_ctx(registry, cfg)
    update(ctx, goal_kind="revenge")
    assert update(ctx, goal_kind="revenge", goal_target="nobody").code == "unknown_goal_target"


@pytest.mark.parametrize(
    "fields",
    [{"goal_target": "grakh"}, {"goal_text": "текст"}, {"goal_status": "done"}],
    ids=["target", "text", "status"],
)
def test_goal_fields_without_kind_are_invalid(registry, cfg, fields):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    result = update(ctx, attitude_delta=2, **fields)
    assert isinstance(result, Invalid)
    assert result.code == "goal_fields_without_kind"
    assert dump(ctx) == before


@pytest.mark.parametrize(
    "fields",
    [{"goal_target": "grakh"}, {"goal_text": "текст"}, {"goal_status": "done"}],
    ids=["target", "text", "status"],
)
def test_goal_fields_alone_without_kind_are_goal_fields_without_kind(registry, cfg, fields):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    result = update(ctx, **fields)
    assert isinstance(result, Invalid)
    assert result.code == "goal_fields_without_kind"
    assert dump(ctx) == before


@pytest.mark.parametrize(
    "fields",
    [{"goal_target": "grakh"}, {"goal_text": "текст"}, {"goal_status": "done"}],
    ids=["target", "text", "status"],
)
def test_world_goal_fields_alone_without_kind_are_goal_fields_without_kind(
    registry, cfg, fields
):
    ctx = world_ctx(registry, cfg)
    before = dump(ctx)
    result = apply(ctx, world_update(**fields))
    assert isinstance(result, Invalid)
    assert result.code == "goal_fields_without_kind"
    assert dump(ctx) == before


def test_update_with_nothing_at_all_is_still_empty_update(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert update(ctx).code == "empty_update"


# npc_not_alive при постановке цели

@pytest.mark.parametrize("status", ["dead", "gone"])
def test_goal_for_departed_npc_is_npc_not_alive(registry, cfg, status):
    ctx = make_ctx(registry, cfg)
    aldric(ctx).status = status
    before = dump(ctx)
    result = update(ctx, goal_kind="revenge")
    assert isinstance(result, Invalid)
    assert result.code == "npc_not_alive"
    assert result.message == "Олдрик не жив: цель не ставится"
    assert dump(ctx) == before


@pytest.mark.parametrize("status", ["dead", "gone"])
def test_world_goal_for_departed_npc_is_npc_not_alive(registry, cfg, status):
    ctx = world_ctx(registry, cfg)
    aldric(ctx).status = status
    result = apply(ctx, world_update(goal_kind="revenge"))
    assert result.code == "npc_not_alive"
    assert aldric(ctx).goals == []


def test_goal_together_with_status_in_one_request_is_goal_kind_with_status(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1]))
    ref = apply(ctx, req("skill_check", skill="athletics", category="easy")).result["roll_ref"]
    before = dump(ctx)
    result = update(ctx, goal_kind="revenge", status="dead", cause="goal", evidence_ref=ref)
    assert isinstance(result, Invalid)
    assert result.code == "goal_kind_with_status"
    assert aldric(ctx).status == "alive"
    assert dump(ctx) == before


def test_world_goal_together_with_status_is_goal_kind_with_status(registry, cfg):
    ctx = world_ctx(registry, cfg)
    result = apply(ctx, world_update(goal_kind="revenge", status="gone", cause="goal"))
    assert result.code == "goal_kind_with_status"


def test_goal_with_status_on_dead_npc_reports_goal_kind_with_status_first(registry, cfg):
    ctx = make_ctx(registry, cfg)
    aldric(ctx).status = "dead"
    # death_problem идёт раньше (rejected); в world проверка цели первая
    ctx = world_ctx(registry, cfg)
    aldric(ctx).status = "dead"
    result = apply(ctx, world_update(goal_kind="revenge", status="gone", cause="goal"))
    assert result.code == "goal_kind_with_status"


def test_closing_goal_together_with_status_is_not_blocked_by_goal_check(registry, cfg):
    ctx = world_ctx(registry, cfg, ScriptedRng(d20=[1]))
    apply(ctx, world_update(goal_kind="revenge"))
    roll = apply(
        ctx,
        parse_request(
            {"type": "skill_check", "skill": "athletics", "category": "easy", "actor": "aldric"},
            "world",
        ),
    )
    decision = apply(
        ctx,
        world_update(
            goal_kind="revenge", goal_status="done", status="dead", cause="goal",
            evidence_ref=roll.result["roll_ref"],
        ),
    )
    assert decision.status == "accepted"
    assert aldric(ctx).status == "dead"
    assert aldric(ctx).goals[0].status == "done"


def test_closing_goal_of_dead_npc_is_allowed(registry, cfg):
    ctx = make_ctx(registry, cfg)
    update(ctx, goal_kind="revenge")
    aldric(ctx).status = "dead"
    decision = update(ctx, goal_kind="revenge", goal_status="done")
    assert decision.status == "accepted"
    assert aldric(ctx).goals[0].status == "done"


def test_world_closing_goal_of_dead_npc_is_allowed(registry, cfg):
    ctx = world_ctx(registry, cfg)
    apply(ctx, world_update(goal_kind="revenge"))
    aldric(ctx).status = "dead"
    decision = apply(ctx, world_update(goal_kind="revenge", goal_status="dropped"))
    assert decision.status == "accepted"
    assert aldric(ctx).goals[0].status == "dropped"


def test_close_of_missing_goal_of_dead_npc_is_no_such_goal(registry, cfg):
    ctx = make_ctx(registry, cfg)
    aldric(ctx).status = "dead"
    assert update(ctx, goal_kind="revenge", goal_status="done").code == "no_such_goal"


# goal_target_of

def test_goal_target_of_empty_is_current_hero(registry, cfg):
    from ai_dm.protocol.handlers.world import goal_target_of

    ctx = make_ctx(registry, cfg)
    assert goal_target_of(ctx, req("npc_update", npc_id="aldric", goal_kind="revenge")) == HERO


def test_goal_target_of_given_value_is_kept(registry, cfg):
    from ai_dm.protocol.handlers.world import goal_target_of

    ctx = make_ctx(registry, cfg)
    request = req("npc_update", npc_id="aldric", goal_kind="rivalry", goal_target="grakh")
    assert goal_target_of(ctx, request) == "grakh"


def test_goal_target_of_follows_current_hero_id(registry, cfg):
    from ai_dm.protocol.handlers.world import goal_target_of

    ctx = make_ctx(registry, cfg)
    ctx.bundle.heroes[0].id = "zed"
    ctx.bundle.manifest.current_hero_id = "zed"
    assert goal_target_of(ctx, req("npc_update", npc_id="aldric", goal_kind="debt")) == "zed"


def test_kind_with_all_fields_is_accepted(registry, cfg):
    ctx = make_ctx(registry, cfg)
    result = update(ctx, goal_kind="rivalry", goal_target="grakh", goal_text="соперничает")
    assert result.status == "accepted"


# закрытие цели

def test_goal_done_closes_active_goal_and_disables_companion(registry, cfg):
    ctx = make_ctx(registry, cfg)
    update(ctx, goal_kind="revenge")
    decision = update(ctx, goal_kind="revenge", goal_status="done")
    assert decision.status == "accepted"
    assert [g.status for g in aldric(ctx).goals] == ["done"]
    assert companion(aldric(ctx)).state == "disabled"


def test_goal_dropped_closes_goal(registry, cfg):
    ctx = make_ctx(registry, cfg)
    update(ctx, goal_kind="love")
    update(ctx, goal_kind="love", goal_status="dropped")
    assert [g.status for g in aldric(ctx).goals] == ["dropped"]


def test_close_log_line_names_kind_and_status(registry, cfg):
    ctx = make_ctx(registry, cfg)
    update(ctx, goal_kind="revenge")
    decision = update(ctx, goal_kind="revenge", goal_status="dropped")
    assert decision.log == ["Олдрик: цель revenge — dropped"]


def test_close_adds_no_new_goal(registry, cfg):
    ctx = make_ctx(registry, cfg)
    update(ctx, goal_kind="revenge")
    update(ctx, goal_kind="revenge", goal_status="done", goal_text="игнор")
    assert len(aldric(ctx).goals) == 1
    assert aldric(ctx).goals[0].text == goals.NARRATIVE["revenge"]


def test_close_only_the_named_goal(registry, cfg):
    ctx = make_ctx(registry, cfg)
    update(ctx, goal_kind="revenge")
    update(ctx, goal_kind="debt")
    update(ctx, goal_kind="revenge", goal_status="done")
    states = [(g.kind, g.status) for g in aldric(ctx).goals]
    assert states == [("revenge", "done"), ("debt", "active")]


def test_close_goal_on_npc_target(registry, cfg):
    ctx = make_ctx(registry, cfg)
    update(ctx, goal_kind="rivalry", goal_target="grakh")
    update(ctx, goal_kind="rivalry", goal_target="grakh", goal_status="done")
    assert [g.status for g in aldric(ctx).goals] == ["done"]
    assert companion(aldric(ctx), "rivalry", "grakh").state == "disabled"


def test_close_without_goal_is_no_such_goal(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    result = update(ctx, goal_kind="revenge", goal_status="done", attitude_delta=3)
    assert isinstance(result, Invalid)
    assert result.code == "no_such_goal"
    assert "revenge" in result.message and HERO in result.message
    assert dump(ctx) == before


def test_close_of_other_target_is_no_such_goal(registry, cfg):
    ctx = make_ctx(registry, cfg)
    update(ctx, goal_kind="revenge")
    result = update(ctx, goal_kind="revenge", goal_target="grakh", goal_status="done")
    assert result.code == "no_such_goal"
    assert active_goals(aldric(ctx))


def test_close_twice_is_no_such_goal(registry, cfg):
    ctx = make_ctx(registry, cfg)
    update(ctx, goal_kind="revenge")
    update(ctx, goal_kind="revenge", goal_status="done")
    assert update(ctx, goal_kind="revenge", goal_status="dropped").code == "no_such_goal"


def test_close_with_unknown_target_is_unknown_goal_target(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert update(ctx, goal_kind="revenge", goal_target="x", goal_status="done").code == (
        "unknown_goal_target"
    )


# порядок проверок

def test_goal_with_unconfirmed_death_is_rejected_before_goal_is_set(registry, cfg):
    ctx = make_ctx(registry, cfg)
    decision = update(ctx, goal_kind="revenge", status="dead")
    assert decision.status == "rejected"
    assert aldric(ctx).goals == []


def test_dead_trader_check_goes_before_goal_check(registry, cfg):
    ctx = make_ctx(registry, cfg)
    aldric(ctx).status = "dead"
    result = update(ctx, trade_kind="general", goal_kind="revenge", goal_target="nobody")
    assert result.code == "npc_not_alive"


def test_merchant_is_not_created_when_goal_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    result = update(ctx, trade_kind="general", goal_kind="revenge", goal_target="nobody")
    assert result.code == "unknown_goal_target"
    assert dump(ctx) == before


def test_merchant_and_goal_together(registry, cfg):
    ctx = make_ctx(registry, cfg)
    decision = update(ctx, trade_kind="general", goal_kind="debt")
    assert decision.status == "accepted"
    assert aldric(ctx).trade is not None
    assert aldric(ctx).goals[0].kind == "debt"


def test_valid_trade_alone_still_works(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert update(ctx, trade_kind="general").status == "accepted"


def test_goal_with_follows_hero_on_dead_npc_is_npc_not_alive(registry, cfg):
    ctx = make_ctx(registry, cfg)
    aldric(ctx).status = "dead"
    result = update(ctx, goal_kind="revenge", follows="hero")
    assert result.code == "npc_not_alive"


def test_goal_passes_other_checks_when_name_is_given(registry, cfg):
    ctx = make_ctx(registry, cfg)
    npc = aldric(ctx)
    npc.named, npc.origin = False, "engine"
    decision = update(ctx, goal_kind="revenge", name="Мурк")
    assert decision.status == "accepted"
    assert npc.name == "Мурк"
    assert len(npc.goals) == 1


# F2 вне боя: герой убил NPC

def kin_world(registry, cfg, **kin_fields):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1, 1]))
    kin = NPC(
        id="son", name="Сын", named=True, means=["m"],
        family=[FamilyLink(kind="parent", ref="aldric", ref_kind="npc")], **kin_fields,
    )
    ctx.bundle.world.npcs["son"] = kin
    return ctx, kin


def kill(ctx, **fields):
    ref = apply(ctx, req("skill_check", skill="athletics", category="easy")).result["roll_ref"]
    data = {"status": "dead", "cause": "goal", "evidence_ref": ref}
    data.update(fields)
    return update(ctx, **data)


def test_hero_kill_gives_revenge_goal_to_kin(registry, cfg):
    ctx, kin = kin_world(registry, cfg)
    now_s = ctx.bundle.world.clock.now_s
    assert kill(ctx, by=HERO).status == "accepted"
    [goal] = kin.goals
    assert (goal.kind, goal.target, goal.since_s) == ("revenge", HERO, now_s)
    assert goal.text == "мстит герою за гибель: Олдрик"
    assert companion(kin).state == "active"


def test_hero_kill_writes_kin_killed_memory(registry, cfg):
    ctx, kin = kin_world(registry, cfg)
    kill(ctx, by=HERO)
    [event] = [e for m in kin.memory for e in m.events]
    assert (event.kind, event.text) == ("kin_killed", "герой убил: Олдрик")


def test_hero_kill_gives_revenge_to_squad(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1]))
    aldric(ctx).groups = ["clan"]
    ctx.bundle.world.npcs["grakh"].groups = ["clan"]
    kill(ctx, by=HERO)
    assert [g.kind for g in ctx.bundle.world.npcs["grakh"].goals] == ["revenge"]


def test_hero_kill_by_unknown_killer_gives_no_revenge(registry, cfg):
    ctx, kin = kin_world(registry, cfg)
    kill(ctx, by="grakh")
    assert aldric(ctx).status == "dead"
    assert kin.goals == []


def test_kill_without_killer_gives_no_revenge(registry, cfg):
    ctx, kin = kin_world(registry, cfg)
    kill(ctx)
    assert aldric(ctx).status == "dead"
    assert kin.goals == []


def test_gone_by_hero_gives_no_revenge(registry, cfg):
    ctx, kin = kin_world(registry, cfg)
    kill(ctx, by=HERO, status="gone")
    assert aldric(ctx).status == "gone"
    assert kin.goals == []


def test_rejected_death_by_hero_gives_no_revenge(registry, cfg):
    ctx, kin = kin_world(registry, cfg)
    result = update(ctx, status="dead", by=HERO)
    assert result.status == "rejected"
    assert kin.goals == []


def test_second_kill_of_dead_npc_does_not_repeat_revenge(registry, cfg):
    ctx, kin = kin_world(registry, cfg)
    kill(ctx, by=HERO)
    kin.goals[0].status = "dropped"
    kill(ctx, by=HERO)
    assert [g.status for g in kin.goals] == ["dropped"]


def test_hero_kill_victim_name_in_goal_text_is_label_when_hidden(registry, cfg):
    ctx, kin = kin_world(registry, cfg)
    npc = aldric(ctx)
    npc.origin, npc.combat = "engine", {"monster_id": "goblin_warrior", "label": "Воин-гоблин 1"}
    kill(ctx, by=HERO)
    assert kin.goals[0].text == "мстит герою за гибель: Воин-гоблин 1"


def test_hero_kill_without_scene_still_gives_goal(registry, cfg):
    bundle = make_bundle(registry, with_scene=False)
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1]), bundle=bundle)
    son = NPC(
        id="son", name="Сын", named=True, means=["m"],
        family=[FamilyLink(kind="parent", ref="aldric", ref_kind="npc")],
    )
    ctx.bundle.world.npcs["son"] = son
    kill(ctx, by=HERO)
    assert len(son.goals) == 1
    assert son.memory == []


def test_hero_kill_log_keeps_death_line(registry, cfg):
    ctx, _ = kin_world(registry, cfg)
    decision = kill(ctx, by=HERO)
    assert "Олдрик: dead (goal)" in decision.log


# роль world (закадровый npc_update)

def world_ctx(registry, cfg, rng=None):
    ctx = make_ctx(registry, cfg, rng, mode="world")
    ctx.candidate_refs = ["cand-1"]
    ctx.verdict_refs = []
    return ctx


def world_update(**fields):
    data = {"type": "npc_update", "npc_id": "aldric", "then_ref": "cand-1"}
    data.update(fields)
    return parse_request(data, "world")


def test_world_goal_is_set(registry, cfg):
    ctx = world_ctx(registry, cfg)
    decision = apply(ctx, world_update(goal_kind="revenge", goal_text="мстит"))
    assert isinstance(decision, Decision)
    [goal] = aldric(ctx).goals
    assert (goal.kind, goal.target, goal.text) == ("revenge", HERO, "мстит")
    assert decision.log == ["Олдрик: новая цель revenge"]


def test_world_goal_on_npc_target(registry, cfg):
    ctx = world_ctx(registry, cfg)
    apply(ctx, world_update(goal_kind="rivalry", goal_target="grakh"))
    assert "npc_status" in str(companion(aldric(ctx), "rivalry", "grakh").if_)


def test_world_empty_goal_text_is_narrative(registry, cfg):
    ctx = world_ctx(registry, cfg)
    apply(ctx, world_update(goal_kind="life_debt"))
    assert aldric(ctx).goals[0].text == goals.NARRATIVE["life_debt"]


def test_world_goal_alone_is_not_empty_update(registry, cfg):
    ctx = world_ctx(registry, cfg)
    assert not isinstance(apply(ctx, world_update(goal_kind="love")), Invalid)


def test_world_update_without_changes_is_empty(registry, cfg):
    ctx = world_ctx(registry, cfg)
    assert apply(ctx, world_update()).code == "empty_update"


def test_world_goal_close(registry, cfg):
    ctx = world_ctx(registry, cfg)
    apply(ctx, world_update(goal_kind="revenge"))
    decision = apply(ctx, world_update(goal_kind="revenge", goal_status="done"))
    assert decision.log == ["Олдрик: цель revenge — done"]
    assert [g.status for g in aldric(ctx).goals] == ["done"]
    assert companion(aldric(ctx)).state == "disabled"


def test_world_goal_close_with_location_move(registry, cfg):
    ctx = world_ctx(registry, cfg)
    apply(ctx, world_update(goal_kind="revenge"))
    apply(ctx, world_update(goal_kind="revenge", goal_status="done", location_id="forest"))
    assert aldric(ctx).location_id == "forest"
    assert aldric(ctx).goals[0].status == "done"


@pytest.mark.parametrize(
    ("fields", "code"),
    [
        ({"goal_kind": "revenge", "goal_target": "nobody"}, "unknown_goal_target"),
        ({"goal_kind": "revenge", "goal_status": "done"}, "no_such_goal"),
        ({"goal_target": "grakh", "attitude_delta": 1}, "goal_fields_without_kind"),
        ({"goal_text": "x", "attitude_delta": 1}, "goal_fields_without_kind"),
        ({"goal_status": "dropped", "attitude_delta": 1}, "goal_fields_without_kind"),
    ],
)
def test_world_goal_problems_change_nothing(registry, cfg, fields, code):
    ctx = world_ctx(registry, cfg)
    before = dump(ctx)
    result = apply(ctx, world_update(**fields))
    assert isinstance(result, Invalid)
    assert result.code == code
    assert dump(ctx) == before


def test_world_repeat_of_goal_is_goal_exists(registry, cfg):
    ctx = world_ctx(registry, cfg)
    apply(ctx, world_update(goal_kind="revenge"))
    assert apply(ctx, world_update(goal_kind="revenge")).code == "goal_exists"


def test_world_goal_problem_does_not_move_npc(registry, cfg):
    ctx = world_ctx(registry, cfg)
    request = world_update(goal_kind="revenge", goal_target="nobody", location_id="forest")
    result = apply(ctx, request)
    assert result.code == "unknown_goal_target"
    assert aldric(ctx).location_id != "forest"


def test_world_follows_hero_of_dead_npc_is_still_npc_not_alive(registry, cfg):
    ctx = world_ctx(registry, cfg)
    aldric(ctx).status = "dead"
    assert apply(ctx, world_update(goal_kind="revenge", follows="hero")).code == "npc_not_alive"


def test_world_follows_hero_of_dead_npc_without_goal_has_exact_message(registry, cfg):
    ctx = world_ctx(registry, cfg)
    aldric(ctx).status = "dead"
    result = apply(ctx, world_update(follows="hero"))
    assert (result.code, result.message) == ("npc_not_alive", "Олдрик не жив: не идёт с героем")


def test_world_follows_none_of_dead_npc_is_not_blocked(registry, cfg):
    ctx = world_ctx(registry, cfg)
    aldric(ctx).status = "dead"
    assert not isinstance(apply(ctx, world_update(follows="none")), Invalid)


def test_world_wrong_then_ref_is_reported_before_goal_problem(registry, cfg):
    ctx = world_ctx(registry, cfg)
    result = apply(ctx, world_update(goal_kind="revenge", goal_target="nobody", then_ref="other"))
    assert result.code == "invalid_then_ref"


def test_world_unknown_npc_is_reported_before_goal_problem(registry, cfg):
    ctx = world_ctx(registry, cfg)
    result = apply(ctx, world_update(npc_id="nobody", goal_kind="revenge", goal_target="x"))
    assert result.code == "unknown_npc"


def test_world_goal_applies_before_unknown_location_is_checked(registry, cfg):
    ctx = world_ctx(registry, cfg)
    result = apply(ctx, world_update(goal_kind="revenge", location_id="nowhere"))
    assert isinstance(result, Invalid)
    assert aldric(ctx).goals == []


def test_world_unknown_location_is_invalid_with_code(registry, cfg):
    ctx = world_ctx(registry, cfg)
    result = apply(ctx, world_update(location_id="nowhere"))
    assert isinstance(result, Invalid)
    assert result.code == "unknown_location"
    assert "nowhere" in result.message and "forest" in result.message


def test_world_move_of_dead_npc_is_npc_not_alive(registry, cfg):
    ctx = world_ctx(registry, cfg)
    aldric(ctx).status = "dead"
    result = apply(ctx, world_update(location_id="forest"))
    assert result.code == "npc_not_alive"
    assert result.message == "Олдрик не жив: не перемещается"


def test_world_move_logs_new_location_name(registry, cfg):
    ctx = world_ctx(registry, cfg)
    decision = apply(ctx, world_update(location_id="forest"))
    assert decision.log == ["Олдрик: теперь в Лес"]


def test_world_death_without_own_roll_is_rejected_with_tag(registry, cfg):
    ctx = world_ctx(registry, cfg)
    decision = apply(ctx, world_update(status="dead", cause="goal", evidence_ref="r1"))
    assert decision.status == "rejected"
    assert decision.report_tag == "invalid-death"
    assert decision.reason == (
        "у смерти должна быть причина (goal или hazard) и не потраченный бросок этого вызова"
    )
    assert decision.signal_to_master == (
        "Олдрик остаётся жив: смерть или уход без причины goal/hazard и "
        "evidence_ref на не потраченный бросок этого вызова не принимаются."
    )
    assert "invalid-death" in ctx.marks
    assert aldric(ctx).status == "alive"


def test_world_death_with_roll_of_other_npc_is_rejected(registry, cfg):
    ctx = world_ctx(registry, cfg, ScriptedRng(d20=[1]))
    roll = apply(
        ctx,
        parse_request(
            {"type": "skill_check", "skill": "athletics", "category": "easy", "actor": "grakh"},
            "world",
        ),
    )
    decision = apply(
        ctx, world_update(status="dead", cause="goal", evidence_ref=roll.result["roll_ref"])
    )
    assert decision.status == "rejected"


def test_basic_problem_none_for_valid_goal_update(registry, cfg):
    from ai_dm.protocol.handlers.offscreen import basic_problem

    ctx = world_ctx(registry, cfg)
    assert basic_problem(ctx, aldric(ctx), world_update(goal_kind="revenge")) is None


def test_basic_problem_reports_empty_update(registry, cfg):
    from ai_dm.protocol.handlers.offscreen import basic_problem

    ctx = world_ctx(registry, cfg)
    assert basic_problem(ctx, aldric(ctx), world_update()).code == "empty_update"


def test_world_kill_by_hero_gives_revenge_to_kin(registry, cfg):
    ctx = world_ctx(registry, cfg, ScriptedRng(d20=[1]))
    kin = NPC(
        id="son", name="Сын", named=True, means=["m"],
        family=[FamilyLink(kind="parent", ref="aldric", ref_kind="npc")],
    )
    ctx.bundle.world.npcs["son"] = kin
    roll = apply(
        ctx,
        parse_request(
            {"type": "skill_check", "skill": "athletics", "category": "easy", "actor": "aldric"},
            "world",
        ),
    )
    decision = apply(
        ctx,
        world_update(status="dead", cause="goal", evidence_ref=roll.result["roll_ref"], by=HERO),
    )
    assert decision.status == "accepted"
    assert [g.kind for g in kin.goals] == ["revenge"]


# У1 П2: цель love на героя у NPC, которому платили, -- до порога романа отклоняется

def paid_ctx(registry, cfg, attitude=40, paid=True):
    ctx = make_ctx(registry, cfg)
    aldric(ctx).attitude = attitude
    if paid:
        ctx.bundle.world.flags["paid_company:hero:aldric"] = True
    return ctx


def test_love_goal_on_hero_after_payment_below_threshold_is_rejected(registry, cfg):
    ctx = paid_ctx(registry, cfg)
    d = update(ctx, goal_kind="love")
    assert d.status == "rejected"
    assert d.report_tag == "paid_not_romance"
    assert str(cfg.services.romance_from) in d.signal_to_master
    assert aldric(ctx).goals == []


def test_rejected_love_goal_changes_nothing(registry, cfg):
    ctx = paid_ctx(registry, cfg)
    before = dump(ctx)
    update(ctx, goal_kind="love")
    assert dump(ctx) == before


def test_love_goal_with_explicit_hero_target_is_rejected_too(registry, cfg):
    d = update(paid_ctx(registry, cfg), goal_kind="love", goal_target=HERO)
    assert d.report_tag == "paid_not_romance"


def test_love_goal_at_threshold_is_set(registry, cfg):
    ctx = paid_ctx(registry, cfg, cfg.services.romance_from)
    assert update(ctx, goal_kind="love").status == "accepted"
    assert [g.kind for g in aldric(ctx).goals] == ["love"]


def test_love_goal_without_payment_is_set_at_low_attitude(registry, cfg):
    ctx = paid_ctx(registry, cfg, 40, paid=False)
    assert update(ctx, goal_kind="love").status == "accepted"


def test_other_goal_kind_after_payment_is_set(registry, cfg):
    ctx = paid_ctx(registry, cfg)
    assert update(ctx, goal_kind="debt").status == "accepted"


def test_love_goal_on_another_npc_after_payment_is_set(registry, cfg):
    ctx = paid_ctx(registry, cfg)
    assert update(ctx, goal_kind="love", goal_target="grakh").status == "accepted"


def test_closing_love_goal_after_payment_is_not_gated(registry, cfg):
    ctx = paid_ctx(registry, cfg, 95)
    update(ctx, goal_kind="love")
    aldric(ctx).attitude = 40
    assert update(ctx, goal_kind="love", goal_status="done").status == "accepted"


def test_love_goal_gate_counts_attitude_delta_of_same_request(registry, cfg):
    # прогноз отношения: 80 + 10 = 90 -- порог пройден, цель ставится
    ctx = paid_ctx(registry, cfg, 80)
    d = update(ctx, goal_kind="love", attitude_delta=10)
    assert d.status == "accepted"
    assert aldric(ctx).attitude == 90
    assert [g.kind for g in aldric(ctx).goals] == ["love"]


def test_love_goal_forecast_below_threshold_is_rejected_and_attitude_untouched(registry, cfg):
    ctx = paid_ctx(registry, cfg, 79)
    d = update(ctx, goal_kind="love", attitude_delta=10)
    assert (d.status, d.report_tag) == ("rejected", "paid_not_romance")
    assert aldric(ctx).attitude == 79
    assert aldric(ctx).goals == []


def test_love_goal_forecast_clamps_delta_to_step(registry, cfg):
    # delta 50 урезается до step (10): 70 + 10 = 80 < 90
    ctx = paid_ctx(registry, cfg, 70)
    d = update(ctx, goal_kind="love", attitude_delta=50)
    assert d.report_tag == "paid_not_romance"


def test_love_goal_forecast_clamps_delta_to_scene_remainder(registry, cfg):
    # за сцену уже потрачено per_scene - 5: 85 + min(10, 5) = 90 -- проходит; при 84 -- нет
    ctx = paid_ctx(registry, cfg, 85)
    ctx.attitude_spent["aldric"] = cfg.attitude.per_scene - 5
    d = update(ctx, goal_kind="love", attitude_delta=10)
    assert d.status != "rejected"
    assert aldric(ctx).attitude == 90
    ctx = paid_ctx(registry, cfg, 84)
    ctx.attitude_spent["aldric"] = cfg.attitude.per_scene - 5
    assert update(ctx, goal_kind="love", attitude_delta=10).report_tag == "paid_not_romance"


def test_love_goal_forecast_with_exhausted_scene_limit_ignores_delta(registry, cfg):
    ctx = paid_ctx(registry, cfg, 85)
    ctx.attitude_spent["aldric"] = cfg.attitude.per_scene
    assert update(ctx, goal_kind="love", attitude_delta=10).report_tag == "paid_not_romance"


def test_love_goal_negative_delta_lowers_forecast(registry, cfg):
    ctx = paid_ctx(registry, cfg, 92)
    d = update(ctx, goal_kind="love", attitude_delta=-5)
    assert d.report_tag == "paid_not_romance"


def test_love_goal_without_delta_forecast_is_current_attitude(registry, cfg):
    ctx = paid_ctx(registry, cfg, cfg.services.romance_from - 1)
    assert update(ctx, goal_kind="love").report_tag == "paid_not_romance"


def test_rejected_love_goal_reason_names_the_cause(registry, cfg):
    assert update(paid_ctx(registry, cfg), goal_kind="love").reason == "платная близость не роман"


def test_love_goal_flag_of_another_hero_does_not_gate(registry, cfg):
    ctx = paid_ctx(registry, cfg, 40, paid=False)
    ctx.bundle.world.flags["paid_company:other_hero:aldric"] = True
    assert update(ctx, goal_kind="love").status == "accepted"


def test_world_role_love_goal_after_payment_is_rejected(registry, cfg):
    ctx = world_ctx(registry, cfg)
    ctx.bundle.world.flags["paid_company:hero:aldric"] = True
    aldric(ctx).attitude = 40
    d = apply(ctx, world_update(goal_kind="love"))
    assert d.report_tag == "paid_not_romance"
