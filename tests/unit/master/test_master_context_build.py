# Сборка контекста нарратора (этап 4, P3): PromptBuilder.build считает бюджет Д1, вытесняет по
# ступеням ТЗ 11 (ходы -> выжимки сцен -> NPC -> локации) и кладёт итог в builder.last_plan.
# Неустранимое: правила, мир, состояние героя, scene_npcs, NPC with_hero/here/active, текущая
# локация, floor-ходы, главы и game_summary.
import json

import pytest
from master_kit import app_cfg, make_bundle, make_ctx, turn_record

from ai_dm.llm.types import ChatRequest, SystemBlock, ToolSpec
from ai_dm.master.context import Candidates, ContextPlan, request_tokens, window_budget
from ai_dm.master.prompt import PromptBuilder, draft_plan
from ai_dm.protocol.schema import tool_set
from ai_dm.state.memory import ChapterSummary, SceneSummary
from ai_dm.state.triggers import Trigger
from ai_dm.state.world import NPC, Connection, Location

OPUS = "claude-opus-5-5"
BIG = 10**9
LONG = "слово " * 50

FULL_ORDER = (
    [("turns", str(n)) for n in range(1, 8)]
    + [("scenes", f"sc{n}") for n in range(1, 5)]
    + [
        ("npcs", i)
        for i in ("said_a", "said_b", "keyer_a", "keyer_b", "keysaid", "near_a", "near_b")
    ]
)
# 129: соседние локации -- цели travel_to, у рассказчика не вытесняются
NEIGHBORS = ["vale", "far", "forest", "mid", "rev", "tie_a", "tie_b"]


def add_npc(world, npc_id, **fields):
    data = {"id": npc_id, "name": f"имя_{npc_id}", "named": True, "means": ["m"]}
    data.update(fields)
    world.npcs[npc_id] = NPC(**data)


def add_place(world, place_id, **fields):
    world.locations[place_id] = Location(id=place_id, name=place_id.upper(), **fields)


def make_scenario(registry, cfg, turns=8):
    bundle = make_bundle(registry)
    world = bundle.world
    vale = world.locations["vale"]
    for place_id, distance in (("mid", 100), ("far", 9000), ("tie_a", 700), ("tie_b", 700)):
        add_place(world, place_id)
        vale.connections.append(Connection(to=place_id, distance_m=distance))
    add_place(world, "rev", connections=[Connection(to="vale", distance_m=500)])
    trigger = Trigger(id="t1", **{"if": {"flag": "x"}}, then="что-то")
    # неустранимые
    add_npc(world, "squire", location_id="goblin_den", follows="hero")
    add_npc(world, "spy", location_id="goblin_den", opportunity=[trigger])
    # said: назван в offered_choices
    add_npc(world, "said_a", name="Зоя", location_id="goblin_den")
    add_npc(world, "said_b", name="Рюрик", location_id="goblin_den")
    # key
    add_npc(world, "keyer_a", key=True, location_id="goblin_den")
    add_npc(world, "keyer_b", key=True, location_id="goblin_den")
    add_npc(world, "keysaid", key=True, name="Мирон", location_id="goblin_den")
    # nearby
    add_npc(world, "near_a", location_id="forest")
    add_npc(world, "near_b", location_id="mid")
    bundle.session.offered_choices = ["Позвать Зоя, Рюрик и Мирон"]
    bundle.memory.recent_turns = [turn_record(n, narration=LONG) for n in range(1, turns + 1)]
    bundle.memory.scenes = [
        SceneSummary(id=f"sc{n}", chapter_id="", title=f"Сцена {n}", summary=f"{LONG}{n}")
        for n in range(1, 5)
    ] + [SceneSummary(id="old", chapter_id="ch_old", title="Старая", summary=f"{LONG}старая")]
    return make_ctx(registry, cfg, bundle=bundle)


def app_with(cap=BIG, **master):
    app = app_cfg().model_copy(deep=True)
    app.master.context_cap = cap
    # ТБ #15: оценка по провайдеру; перекрытия снимаем, чтобы chars_per_token работал для всех
    app.master.chars_per_token_by_provider = {}
    for key, value in master.items():
        setattr(app.master, key, value)
    return app


def build(ctx, app=None, model=None, mode="explore"):
    builder = PromptBuilder(app or app_with(), model=model)
    request = builder.build(ctx, "Осматриваюсь.", mode)
    return request, builder


def data_of(request):
    return json.loads(request.messages[0].content[0].text)


def memory_of(request):
    return json.loads(request.system[2].text)


def total(registry, cfg):
    # динамика полного запроса: context_cap не включает кэшируемую статику (Ж0 п.0)
    request, builder = build(make_scenario(registry, cfg))
    return builder.last_plan.estimate - builder.last_plan.static


# last_plan и форма плана

def test_last_plan_is_none_before_build():
    assert PromptBuilder(app_with()).last_plan is None


def test_build_sets_last_plan(registry, cfg):
    _, builder = build(make_scenario(registry, cfg))
    assert isinstance(builder.last_plan, ContextPlan)


def test_roomy_budget_drops_nothing(registry, cfg):
    request, builder = build(make_scenario(registry, cfg))
    plan = builder.last_plan
    assert plan.dropped == []
    assert plan.raised is False
    assert plan.overflow is False
    assert plan.static > 0
    assert plan.cap == 800_000 - plan.static
    assert len(data_of(request)["recent_turns"]) == 8


def test_last_plan_is_replaced_on_next_build(registry, cfg):
    ctx = make_scenario(registry, cfg)
    builder = PromptBuilder(app_with())
    builder.build(ctx, "а", "explore")
    first = builder.last_plan
    builder.build(ctx, "б", "explore")
    assert builder.last_plan is not first


def test_cap_comes_from_context_cap_and_model_window(registry, cfg):
    _, builder = build(make_scenario(registry, cfg), app=app_with(cap=12_345))
    assert builder.last_plan.cap == 12_345
    app = app_with(cap=BIG)
    app.context_windows[OPUS] = 10_000
    _, builder = build(make_scenario(registry, cfg), app=app)
    # окно 10 000 меньше статики: потолок динамики 0, бюджет поднят до 80 % окна
    assert builder.last_plan.cap == 0
    assert builder.last_plan.budget == 8_000


def test_estimate_uses_chars_per_token_of_config(registry, cfg):
    _, loose = build(make_scenario(registry, cfg), app=app_with(chars_per_token=5.0))
    _, tight = build(make_scenario(registry, cfg), app=app_with(chars_per_token=2.5))
    assert tight.last_plan.estimate > loose.last_plan.estimate * 1.9


# ТБ #15: chars_per_token по провайдеру роли (docs/plan-tb.md п.4)

def app_for(provider_cpt, provider="anthropic"):
    app = app_with()
    app.master.chars_per_token = 2.5
    app.master.chars_per_token_by_provider = provider_cpt
    app.roles = app.profiles[provider]
    return app


def test_estimate_of_anthropic_role_uses_its_own_cpt(registry, cfg):
    app = app_for({"anthropic": 2.0})
    request, builder = build(make_scenario(registry, cfg), app=app)
    assert builder.last_plan.estimate == request_tokens(request, 2.0)


def test_estimate_of_gemini_role_uses_common_cpt_when_not_overridden(registry, cfg):
    app = app_for({"anthropic": 2.0}, provider="gemini")
    request, builder = build(make_scenario(registry, cfg), app=app)
    assert builder.last_plan.estimate == request_tokens(request, 2.5)


def test_anthropic_estimate_is_larger_than_gemini_for_same_request(registry, cfg):
    _, anthropic = build(make_scenario(registry, cfg), app=app_for({"anthropic": 2.0}))
    gemini_app = app_for({"anthropic": 2.0}, provider="gemini")
    _, gemini = build(make_scenario(registry, cfg), app=gemini_app)
    assert anthropic.last_plan.estimate > gemini.last_plan.estimate


def test_cpt_override_changes_what_is_dropped(registry, cfg):
    # при cpt 2.5 запрос ровно влезает (ничего не вытеснено), при 2.0 оценка выше -- вытеснение
    cap = total(registry, cfg)
    fits = app_for({})
    fits.master.context_cap = cap
    tight = app_for({"anthropic": 2.0})
    tight.master.context_cap = cap
    _, fit_builder = build(make_scenario(registry, cfg), app=fits)
    _, tight_builder = build(make_scenario(registry, cfg), app=tight)
    assert fit_builder.last_plan.dropped == []
    assert tight_builder.last_plan.dropped


def test_default_config_anthropic_explore_empty_history_fits_without_drop(registry, cfg):
    # ТБ #15: дефолтный конфиг (cap 30000, общий cpt) -- статика anthropic влезает без вытеснения
    ctx = make_ctx(registry, cfg)
    builder = PromptBuilder(app_cfg())
    builder.build(ctx, "Осматриваюсь.", "explore")
    assert builder.last_plan.dropped == []
    assert builder.last_plan.overflow is False


# порядок вытеснения целиком

def test_full_drop_order_when_nothing_fits(registry, cfg):
    _, builder = build(make_scenario(registry, cfg), app=app_with(cap=1))
    assert builder.last_plan.dropped == FULL_ORDER


def test_scenes_of_other_chapters_are_not_in_plan_or_dropped(registry, cfg):
    request, builder = build(make_scenario(registry, cfg))
    assert "old" not in [i for _, i in FULL_ORDER]
    assert [s.id for s in builder.last_plan.scene_summaries] == ["sc1", "sc2", "sc3", "sc4"]
    assert "старая" not in request.system[2].text


def test_floor_turn_stays_when_everything_dropped(registry, cfg):
    request, _ = build(make_scenario(registry, cfg), app=app_with(cap=1))
    assert [t["turn_seq"] for t in data_of(request)["recent_turns"]] == [8]


def test_floor_from_config_is_respected(registry, cfg):
    request, _ = build(make_scenario(registry, cfg), app=app_with(cap=1, recent_turns_floor=3))
    assert [t["turn_seq"] for t in data_of(request)["recent_turns"]] == [6, 7, 8]


def test_floor_zero_allows_dropping_all_turns(registry, cfg):
    request, builder = build(
        make_scenario(registry, cfg), app=app_with(cap=1, recent_turns_floor=0)
    )
    assert data_of(request)["recent_turns"] == []
    assert builder.last_plan.dropped[:8] == [("turns", str(n)) for n in range(1, 9)]


def test_window_is_taken_from_recent_turns_config(registry, cfg):
    ctx = make_scenario(registry, cfg, turns=12)
    request, _ = build(ctx, app=app_with(recent_turns=5, recent_turns_floor=1))
    assert [t["turn_seq"] for t in data_of(request)["recent_turns"]] == [8, 9, 10, 11, 12]


def test_turns_older_than_window_are_not_reported_as_dropped(registry, cfg):
    _, builder = build(make_scenario(registry, cfg, turns=12), app=app_with(cap=1))
    assert ("turns", "1") not in builder.last_plan.dropped
    assert builder.last_plan.dropped[0] == ("turns", "5")


@pytest.mark.parametrize("share", [100, 99, 90, 80, 70, 60, 50, 40, 30, 20])
def test_dropped_is_prefix_of_full_order_and_fits(registry, cfg, share):
    cap = total(registry, cfg) * share // 100
    app = app_with(cap=cap)
    request, builder = build(make_scenario(registry, cfg), app=app)
    plan = builder.last_plan
    assert plan.dropped == FULL_ORDER[: len(plan.dropped)]
    if not plan.raised:
        assert plan.estimate <= cap + plan.static
    assert plan.estimate == request_tokens(request, app.master.chars_per_token)


@pytest.mark.parametrize("share", [100, 90, 70, 50, 35, 25])
def test_request_matches_plan(registry, cfg, share):
    cap = total(registry, cfg) * share // 100
    request, builder = build(make_scenario(registry, cfg), app=app_with(cap=cap))
    plan = builder.last_plan
    dropped = set(plan.dropped)
    data = data_of(request)
    assert [t["turn_seq"] for t in data["recent_turns"]] == [t.turn_seq for t in plan.turns]
    assert [s["title"] for s in memory_of(request)["scenes"]] == [
        s.title for s in plan.scene_summaries
    ]
    known = {n["id"] for n in data["known_npcs"]}
    for stage, item in dropped:
        if stage == "npcs":
            assert item not in known
    shown = [x["id"] for x in data["locations"]]
    for stage, item in dropped:
        if stage == "locations":
            assert item not in shown
    assert shown[0] == "vale"


def test_minimal_drop_one_below_total_drops_only_oldest_turn(registry, cfg):
    full = total(registry, cfg)
    _, builder = build(make_scenario(registry, cfg), app=app_with(cap=full - 1))
    assert builder.last_plan.dropped == [("turns", "1")]


def test_cap_equal_to_total_drops_nothing(registry, cfg):
    full = total(registry, cfg)
    _, builder = build(make_scenario(registry, cfg), app=app_with(cap=full))
    assert builder.last_plan.dropped == []


# ступень 3 в запросе: ранги NPC

def known_ids(request):
    return [n["id"] for n in data_of(request)["known_npcs"]]


def test_all_relevant_npcs_are_known_when_roomy(registry, cfg):
    request, _ = build(make_scenario(registry, cfg))
    assert known_ids(request) == sorted([
        "grakh", "squire", "spy", "said_a", "said_b", "keyer_a", "keyer_b", "keysaid",
        "near_a", "near_b",
    ])


def test_nearby_npc_is_known_but_not_in_relevant_npcs(registry, cfg):
    from ai_dm.master.relevance import relevant_npcs

    ctx = make_scenario(registry, cfg)
    request, _ = build(ctx)
    assert "near_a" in known_ids(request)
    assert "near_a" not in relevant_npcs(ctx.bundle)


def test_unrelated_far_npc_is_not_known(registry, cfg):
    ctx = make_scenario(registry, cfg)
    add_npc(ctx.bundle.world, "stranger", location_id="goblin_den")
    request, _ = build(ctx)
    assert "stranger" not in known_ids(request)


def test_dead_nearby_npc_is_not_known(registry, cfg):
    ctx = make_scenario(registry, cfg)
    ctx.bundle.world.npcs["near_a"].status = "dead"
    request, _ = build(ctx)
    assert "near_a" not in known_ids(request)


def test_known_npcs_keep_sorted_order_after_dropping(registry, cfg):
    request, _ = build(make_scenario(registry, cfg), app=app_with(cap=1))
    ids = known_ids(request)
    assert ids == sorted(ids)


def test_unremovable_npcs_survive_any_cap(registry, cfg):
    request, builder = build(make_scenario(registry, cfg), app=app_with(cap=1))
    assert known_ids(request) == ["grakh", "spy", "squire"]
    dropped_npcs = [i for s, i in builder.last_plan.dropped if s == "npcs"]
    assert not {"grakh", "spy", "squire"} & set(dropped_npcs)


def test_scene_npcs_are_never_dropped(registry, cfg):
    ctx = make_scenario(registry, cfg)
    add_npc(ctx.bundle.world, "clerk", location_id="vale", attitude=3)
    request, _ = build(ctx, app=app_with(cap=1))
    ids = [n["id"] for n in data_of(request)["scene_npcs"]]
    assert ids == ["clerk", "grakh"]


def test_said_npcs_are_dropped_before_key(registry, cfg):
    _, builder = build(make_scenario(registry, cfg), app=app_with(cap=1))
    order = [i for s, i in builder.last_plan.dropped if s == "npcs"]
    assert order.index("said_b") < order.index("keyer_a")


def test_key_npcs_are_dropped_before_nearby(registry, cfg):
    _, builder = build(make_scenario(registry, cfg), app=app_with(cap=1))
    order = [i for s, i in builder.last_plan.dropped if s == "npcs"]
    assert order.index("keysaid") < order.index("near_a")


def test_key_and_said_npc_counts_as_key(registry, cfg):
    _, builder = build(make_scenario(registry, cfg), app=app_with(cap=1))
    order = [i for s, i in builder.last_plan.dropped if s == "npcs"]
    assert order.index("keyer_b") < order.index("keysaid")
    assert order.index("said_b") < order.index("keysaid")


def test_key_npc_with_active_trigger_is_unremovable(registry, cfg):
    ctx = make_scenario(registry, cfg)
    trigger = Trigger(id="t2", **{"if": {"flag": "x"}}, then="что-то")
    ctx.bundle.world.npcs["keyer_a"].opportunity = [trigger]
    request, builder = build(ctx, app=app_with(cap=1))
    assert "keyer_a" in known_ids(request)
    assert ("npcs", "keyer_a") not in builder.last_plan.dropped


def test_key_npc_nearby_counts_as_key(registry, cfg):
    ctx = make_scenario(registry, cfg)
    ctx.bundle.world.npcs["near_a"].key = True
    _, builder = build(ctx, app=app_with(cap=1))
    order = [i for s, i in builder.last_plan.dropped if s == "npcs"]
    assert order == [
        "said_a", "said_b", "keyer_a", "keyer_b", "keysaid", "near_a", "near_b",
    ]


def test_ids_within_rank_ascend(registry, cfg):
    _, builder = build(make_scenario(registry, cfg), app=app_with(cap=1))
    order = [i for s, i in builder.last_plan.dropped if s == "npcs"]
    assert order[0:2] == ["said_a", "said_b"]
    assert order[-2:] == ["near_a", "near_b"]


# ступень 4: локации

def shown_locations(request):
    return [x["id"] for x in data_of(request)["locations"]]


def test_all_neighbor_locations_shown_when_roomy(registry, cfg):
    request, _ = build(make_scenario(registry, cfg))
    assert shown_locations(request) == ["vale", "far", "forest", "mid", "rev", "tie_a", "tie_b"]


def test_neighbor_locations_are_never_dropped(registry, cfg):
    _, builder = build(make_scenario(registry, cfg), app=app_with(cap=1))
    assert [i for s, i in builder.last_plan.dropped if s == "locations"] == []


def test_all_neighbors_shown_when_nothing_fits(registry, cfg):
    request, _ = build(make_scenario(registry, cfg), app=app_with(cap=1))
    assert shown_locations(request) == NEIGHBORS


def test_current_location_is_never_dropped(registry, cfg):
    request, builder = build(make_scenario(registry, cfg), app=app_with(cap=1))
    assert shown_locations(request)[0] == "vale"
    assert ("locations", "vale") not in builder.last_plan.dropped
    assert data_of(request)["location"]["id"] == "vale"


def test_candidates_fix_current_and_all_neighbors(registry, cfg):
    c = PromptBuilder(app_with()).candidates(make_scenario(registry, cfg))
    assert c.fixed_locations[0] == "vale"
    assert sorted(c.fixed_locations) == sorted(NEIGHBORS)


def test_candidates_have_no_removable_locations(registry, cfg):
    c = PromptBuilder(app_with()).candidates(make_scenario(registry, cfg))
    assert c.locations == []


def test_candidates_without_hero_location_fix_nothing(registry, cfg):
    ctx = make_scenario(registry, cfg)
    ctx.hero.location_id = None
    assert PromptBuilder(app_with()).candidates(ctx).fixed_locations == []


def test_hero_without_location_has_no_candidate_locations(registry, cfg):
    ctx = make_scenario(registry, cfg)
    ctx.hero.location_id = None
    request, builder = build(ctx, app=app_with(cap=1))
    assert data_of(request)["locations"] == []
    assert [s for s, _ in builder.last_plan.dropped if s == "locations"] == []


# G1: неустранимое > cap

def test_unavoidable_over_cap_raises_budget(registry, cfg):
    app = app_with(cap=1)
    request, builder = build(make_scenario(registry, cfg), app=app)
    plan = builder.last_plan
    assert plan.raised is True
    assert plan.overflow is True
    assert plan.budget == 800_000
    assert plan.cap == 1
    assert plan.estimate > 1
    assert request.messages


def test_raised_request_has_only_unavoidable_part(registry, cfg):
    request, _ = build(make_scenario(registry, cfg), app=app_with(cap=1))
    data = data_of(request)
    assert [t["turn_seq"] for t in data["recent_turns"]] == [8]
    assert memory_of(request)["scenes"] == []
    assert data["hero"]["name"] == "Арн"
    assert data["player_input"] == "Осматриваюсь."


def test_chapters_and_game_summary_stay_even_when_raised(registry, cfg):
    from ai_dm.state.memory import ChapterSummary

    ctx = make_scenario(registry, cfg)
    ctx.bundle.memory.game_summary = "Длинная история игры."
    ctx.bundle.memory.chapters = [
        ChapterSummary(id="ch_old", number=1, title="Глава один", summary="Итог главы.")
    ]
    request, _ = build(ctx, app=app_with(cap=1))
    memory = memory_of(request)
    assert memory["game_summary"] == "Длинная история игры."
    assert memory["chapters"] == [{"number": 1, "title": "Глава один", "summary": "Итог главы."}]


def test_not_raised_when_unavoidable_fits_cap(registry, cfg):
    request, builder = build(make_scenario(registry, cfg), app=app_with(cap=1))
    bare = builder.last_plan.estimate
    dynamic = bare - builder.last_plan.static
    _, again = build(make_scenario(registry, cfg), app=app_with(cap=dynamic))
    assert again.last_plan.raised is False
    assert again.last_plan.budget == bare
    assert again.last_plan.dropped == FULL_ORDER


def test_estimate_above_window_80_still_builds(registry, cfg):
    app = app_with(cap=1)
    app.context_windows[OPUS] = 10
    request, builder = build(make_scenario(registry, cfg), app=app)
    assert builder.last_plan.raised is True
    assert builder.last_plan.budget == 8
    assert request.messages


def test_not_raised_flags_are_false(registry, cfg):
    _, builder = build(make_scenario(registry, cfg))
    meta = builder.last_plan.meta()
    assert meta["raised"] is False
    assert meta["overflow"] is False


# смена модели: другое окно -- другой бюджет

def test_other_model_window_changes_budget_and_drops(registry, cfg):
    app = app_with(cap=BIG)
    app.context_windows["claude-sonnet-5-5"] = 10_000
    ctx = make_scenario(registry, cfg)
    _, roomy = build(ctx, app=app)
    _, small = build(ctx, app=app, model="claude-sonnet-5-5")
    assert roomy.last_plan.dropped == []
    assert small.last_plan.budget == 8_000
    assert small.last_plan.dropped


# идемпотентность и кэш-префикс

def test_two_builds_of_same_bundle_are_byte_equal(registry, cfg):
    ctx = make_scenario(registry, cfg)
    app = app_with(cap=total(registry, cfg) // 2)
    first, _ = build(ctx, app=app)
    second, _ = build(ctx, app=app)
    assert first.model_dump_json() == second.model_dump_json()


def test_build_does_not_change_bundle_when_dropping(registry, cfg):
    ctx = make_scenario(registry, cfg)
    before = ctx.bundle.model_dump_json()
    build(ctx, app=app_with(cap=1))
    assert ctx.bundle.model_dump_json() == before


def test_system_0_and_1_do_not_depend_on_eviction(registry, cfg):
    roomy, _ = build(make_scenario(registry, cfg))
    tight, _ = build(make_scenario(registry, cfg), app=app_with(cap=1))
    assert tight.system[0].text.encode() == roomy.system[0].text.encode()
    assert tight.system[1].text.encode() == roomy.system[1].text.encode()


def test_system_0_and_1_do_not_depend_on_memory(registry, cfg):
    first, _ = build(make_scenario(registry, cfg))
    ctx = make_scenario(registry, cfg)
    ctx.bundle.memory.game_summary = "Совсем другая память."
    ctx.bundle.memory.scenes = []
    second, _ = build(ctx, app=app_with(cap=1))
    assert second.system[0].text.encode() == first.system[0].text.encode()
    assert second.system[1].text.encode() == first.system[1].text.encode()


def test_scene_drop_changes_only_memory_block(registry, cfg):
    full = total(registry, cfg)
    roomy, _ = build(make_scenario(registry, cfg))
    tight, builder = build(make_scenario(registry, cfg), app=app_with(cap=full // 2))
    assert any(s == "scenes" for s, _ in builder.last_plan.dropped)
    assert tight.system[2].text != roomy.system[2].text
    assert tight.system[2].stable is False
    assert tight.system[2].cache is True


def test_tools_do_not_depend_on_eviction(registry, cfg):
    roomy, _ = build(make_scenario(registry, cfg))
    tight, _ = build(make_scenario(registry, cfg), app=app_with(cap=1))
    assert tight.tools == roomy.tools


@pytest.mark.parametrize("mode", ["explore", "combat_classify", "npc_choice"])
def test_budget_is_applied_in_every_mode(registry, cfg, mode):
    ctx = make_scenario(registry, cfg)
    request, builder = build(ctx, app=app_with(cap=1), mode=mode)
    assert builder.last_plan.dropped == FULL_ORDER
    assert request.messages


# Ж0 п.0: статика запроса (правила, мир, схемы инструментов) вне context_cap

def explore_tools():
    return [ToolSpec.model_validate(d) for d in tool_set("explore")]


def static_of(builder, ctx, cpt=2.5, tools=None, world_text=""):
    tools = explore_tools() if tools is None else tools
    return builder.static_estimate(ctx, tools, world_text, cpt)


def test_static_estimate_is_estimate_of_rules_world_and_tools_without_messages(registry, cfg):
    ctx = make_scenario(registry, cfg)
    builder = PromptBuilder(app_with())
    tools = explore_tools()
    request = ChatRequest(
        role="narrator", model=OPUS, tools=tools, messages=[],
        system=[
            SystemBlock(text=builder.rules, cache=True),
            SystemBlock(text=builder.world_block(ctx, ""), cache=True),
        ],
        max_tokens=builder.role_cfg.max_tokens,
    )
    assert static_of(builder, ctx, 2.5, tools) == request_tokens(request, 2.5)


def test_static_estimate_does_not_depend_on_history_and_memory(registry, cfg):
    builder = PromptBuilder(app_with())
    full = static_of(builder, make_scenario(registry, cfg))
    ctx = make_scenario(registry, cfg)
    ctx.bundle.memory.recent_turns = []
    ctx.bundle.memory.scenes = []
    ctx.bundle.memory.game_summary = "другая память"
    assert static_of(builder, ctx) == full


def test_static_estimate_grows_with_world_text(registry, cfg):
    ctx = make_scenario(registry, cfg)
    builder = PromptBuilder(app_with())
    plain = static_of(builder, ctx)
    assert static_of(builder, ctx, world_text="мир " * 500) - plain >= 700


def test_static_estimate_counts_tool_schemas(registry, cfg):
    ctx = make_scenario(registry, cfg)
    builder = PromptBuilder(app_with())
    assert static_of(builder, ctx) > static_of(builder, ctx, tools=[]) + 5000


def test_static_estimate_depends_on_chars_per_token(registry, cfg):
    ctx = make_scenario(registry, cfg)
    builder = PromptBuilder(app_with())
    fine = static_of(builder, ctx, 2.0)
    coarse = static_of(builder, ctx, 4.0)
    assert 2 * coarse - 1 <= fine <= 2 * coarse


def test_plan_static_is_static_estimate_of_the_request(registry, cfg):
    ctx = make_scenario(registry, cfg)
    _, builder = build(ctx)
    assert builder.last_plan.static == static_of(builder, ctx)


def test_plan_static_is_the_same_for_any_cap(registry, cfg):
    _, roomy = build(make_scenario(registry, cfg))
    _, tight = build(make_scenario(registry, cfg), app=app_with(cap=1))
    assert roomy.last_plan.static == tight.last_plan.static


def test_plan_static_follows_world_text(registry, cfg):
    ctx = make_scenario(registry, cfg)
    builder = PromptBuilder(app_with())
    builder.build(ctx, "а", "explore")
    plain = builder.last_plan.static
    builder.build(ctx, "а", "explore", world_text="мир " * 500)
    assert builder.last_plan.static - plain >= 700


def test_plan_static_follows_mode_tools(registry, cfg):
    ctx = make_scenario(registry, cfg)
    _, explore = build(ctx, mode="explore")
    _, classify = build(ctx, mode="combat_classify")
    assert explore.last_plan.static != classify.last_plan.static


def test_plan_static_of_anthropic_role_uses_its_cpt(registry, cfg):
    app = app_for({"anthropic": 2.2})
    ctx = make_scenario(registry, cfg)
    _, builder = build(ctx, app=app)
    assert builder.last_plan.static == static_of(builder, ctx, 2.2)


def test_plan_static_of_gemini_role_uses_common_cpt(registry, cfg):
    app = app_for({"anthropic": 2.2}, provider="gemini")
    ctx = make_scenario(registry, cfg)
    _, builder = build(ctx, app=app)
    assert builder.last_plan.static == static_of(builder, ctx, 2.5)


def test_estimate_counts_world_text_in_every_render(registry, cfg):
    app = app_with()
    request, builder = build_with_world(make_scenario(registry, cfg), app, "мир " * 500)
    assert builder.last_plan.estimate == request_tokens(request, app.master.chars_per_token)


def build_with_world(ctx, app, world_text):
    builder = PromptBuilder(app)
    return builder.build(ctx, "Осматриваюсь.", "explore", world_text=world_text), builder


def test_world_block_has_exact_keys_and_values(registry, cfg):
    ctx = make_scenario(registry, cfg)
    data = json.loads(PromptBuilder(app_with()).world_block(ctx, "Текст мира."))
    world = ctx.bundle.world
    assert set(data) == {"world_id", "tone", "settings", "world_text", "monster_ids", "item_ids"}
    assert data["world_id"] == world.world_id
    assert data["tone"] == world.tone.model_dump(mode="json")
    assert data["settings"] == world.settings
    assert data["world_text"] == "Текст мира."


def test_memory_block_scene_items_have_title_and_summary(registry, cfg):
    ctx = make_scenario(registry, cfg)
    scene = SceneSummary(id="s", chapter_id="", title="Сцена", summary="Выжимка.")
    block = PromptBuilder(app_with()).memory_block(ctx, draft_plan(Candidates(scenes=[scene])))
    assert json.loads(block)["scenes"] == [{"title": "Сцена", "summary": "Выжимка."}]


def test_meta_static_is_plan_static(registry, cfg):
    _, builder = build(make_scenario(registry, cfg))
    assert builder.last_plan.static > 0
    assert builder.last_plan.meta()["static"] == builder.last_plan.static


def test_budget_is_static_plus_context_cap(registry, cfg):
    _, builder = build(make_scenario(registry, cfg), app=app_with(cap=12_345))
    plan = builder.last_plan
    assert plan.raised is False
    assert plan.budget == plan.static + 12_345
    assert plan.cap == 12_345


def test_dynamic_part_fits_context_cap_without_static(registry, cfg):
    cap = total(registry, cfg) // 2
    _, builder = build(make_scenario(registry, cfg), app=app_with(cap=cap))
    plan = builder.last_plan
    assert plan.dropped
    assert plan.estimate - plan.static <= cap


def test_dynamic_cap_is_boundary_of_eviction(registry, cfg):
    full = total(registry, cfg)
    _, fits = build(make_scenario(registry, cfg), app=app_with(cap=full))
    _, over = build(make_scenario(registry, cfg), app=app_with(cap=full - 1))
    assert fits.last_plan.dropped == []
    assert over.last_plan.dropped == [("turns", "1")]


def test_window_below_static_plus_cap_limits_budget_to_window_80(registry, cfg):
    _, probe = build(make_scenario(registry, cfg))
    static = probe.last_plan.static
    app = app_with(cap=BIG)
    app.context_windows[OPUS] = (static + 6_000) * 5 // 4
    window80 = window_budget(app, OPUS)
    _, builder = build(make_scenario(registry, cfg), app=app)
    plan = builder.last_plan
    assert static < window80 < static + 6_001
    assert plan.budget == window80
    assert plan.cap == window80 - static
    assert plan.raised is False


def test_window_below_static_makes_cap_zero_and_raises_budget(registry, cfg):
    app = app_with(cap=BIG)
    app.context_windows[OPUS] = 10_000
    _, builder = build(make_scenario(registry, cfg), app=app)
    plan = builder.last_plan
    assert plan.static > 8_000
    assert plan.cap == 0
    assert plan.raised is True
    assert plan.budget == 8_000


def test_raised_when_dynamic_part_does_not_fit_cap_even_with_static(registry, cfg):
    _, builder = build(make_scenario(registry, cfg), app=app_with(cap=1))
    plan = builder.last_plan
    assert plan.raised is True
    assert plan.estimate > plan.static + plan.cap


# Ж0 п.0, BACKLOG 15: пятая ступень -- главы, свёрнутые в game_summary

CHAPTER_TAIL = [("chapters", "ch1"), ("chapters", "ch2")]


def chapters_scenario(registry, cfg, folded=2):
    ctx = make_scenario(registry, cfg)
    memory = ctx.bundle.memory
    memory.chapters = [
        ChapterSummary(id=f"ch{n}", number=n, title=f"Глава {n}", summary=f"{LONG}{n}")
        for n in range(1, 5)
    ]
    memory.game_summary = "Свёртка игры."
    memory.game_summary_chapter = folded
    return ctx


def chapter_numbers(request):
    return [c["number"] for c in memory_of(request)["chapters"]]


def test_candidates_split_chapters_by_game_summary_chapter(registry, cfg):
    ctx = chapters_scenario(registry, cfg, folded=2)
    c = PromptBuilder(app_with()).candidates(ctx)
    assert [x.number for x in c.chapters] == [1, 2]
    assert [x.number for x in c.fixed_chapters] == [3, 4]


def test_candidates_chapter_equal_to_game_summary_chapter_is_folded(registry, cfg):
    ctx = chapters_scenario(registry, cfg, folded=4)
    c = PromptBuilder(app_with()).candidates(ctx)
    assert [x.number for x in c.chapters] == [1, 2, 3, 4]
    assert c.fixed_chapters == []


def test_candidates_without_folded_chapters_are_all_fixed(registry, cfg):
    ctx = chapters_scenario(registry, cfg, folded=0)
    c = PromptBuilder(app_with()).candidates(ctx)
    assert c.chapters == []
    assert [x.number for x in c.fixed_chapters] == [1, 2, 3, 4]


def test_candidates_without_chapters_have_none(registry, cfg):
    c = PromptBuilder(app_with()).candidates(make_scenario(registry, cfg))
    assert c.chapters == []
    assert c.fixed_chapters == []


def test_draft_plan_carries_folded_then_fixed_chapters():
    one = ChapterSummary(id="a", number=1)
    two = ChapterSummary(id="b", number=2)
    assert draft_plan(Candidates(chapters=[one], fixed_chapters=[two])).chapters == [one, two]


def test_draft_plan_without_chapters_has_none():
    assert draft_plan(Candidates()).chapters == []


def test_memory_block_takes_chapters_from_plan_not_from_memory(registry, cfg):
    ctx = chapters_scenario(registry, cfg)
    only = ChapterSummary(id="x", number=9, title="Девятая", summary="Только она.")
    chapter_plan = draft_plan(Candidates(fixed_chapters=[only]))
    block = PromptBuilder(app_with()).memory_block(ctx, chapter_plan)
    assert json.loads(block)["chapters"] == [
        {"number": 9, "title": "Девятая", "summary": "Только она."}
    ]


def test_memory_block_game_summary_comes_from_memory(registry, cfg):
    ctx = chapters_scenario(registry, cfg)
    block = PromptBuilder(app_with()).memory_block(ctx, draft_plan(Candidates()))
    assert json.loads(block)["game_summary"] == "Свёртка игры."
    assert json.loads(block)["chapters"] == []


def test_roomy_request_has_all_chapters_in_order(registry, cfg):
    request, builder = build(chapters_scenario(registry, cfg))
    assert chapter_numbers(request) == [1, 2, 3, 4]
    assert [c.id for c in builder.last_plan.chapters] == ["ch1", "ch2", "ch3", "ch4"]


def test_chapters_are_dropped_last_after_locations(registry, cfg):
    _, builder = build(chapters_scenario(registry, cfg), app=app_with(cap=1))
    assert builder.last_plan.dropped == FULL_ORDER + CHAPTER_TAIL


def test_only_folded_chapters_leave_the_request(registry, cfg):
    request, builder = build(chapters_scenario(registry, cfg, folded=2), app=app_with(cap=1))
    assert chapter_numbers(request) == [3, 4]
    assert [c.id for c in builder.last_plan.chapters] == ["ch3", "ch4"]


def test_all_chapters_stay_when_none_is_folded(registry, cfg):
    request, builder = build(chapters_scenario(registry, cfg, folded=0), app=app_with(cap=1))
    assert chapter_numbers(request) == [1, 2, 3, 4]
    assert [s for s, _ in builder.last_plan.dropped if s == "chapters"] == []


def one_folded_cap(registry, cfg):
    # динамика запроса, где глава 1 уже вытеснена, а главы 2-4 остались (глава 2 -- как неподвижная)
    _, one = build(chapters_scenario(registry, cfg, folded=1), app=app_with(cap=1))
    return one.last_plan.estimate - one.last_plan.static


def test_chapter_drop_stops_when_dynamic_part_fits(registry, cfg):
    cap = one_folded_cap(registry, cfg)
    _, builder = build(chapters_scenario(registry, cfg, folded=2), app=app_with(cap=cap))
    assert builder.last_plan.dropped == FULL_ORDER + [("chapters", "ch1")]
    assert builder.last_plan.raised is False


def test_chapter_drop_goes_on_one_token_below(registry, cfg):
    cap = one_folded_cap(registry, cfg) - 1
    _, builder = build(chapters_scenario(registry, cfg, folded=2), app=app_with(cap=cap))
    assert builder.last_plan.dropped == FULL_ORDER + CHAPTER_TAIL


def test_dropped_chapters_leave_the_request_estimate_equal_to_final(registry, cfg):
    app = app_with(cap=1)
    request, builder = build(chapters_scenario(registry, cfg), app=app)
    assert builder.last_plan.estimate == request_tokens(request, app.master.chars_per_token)
