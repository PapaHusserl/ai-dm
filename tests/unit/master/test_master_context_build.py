# Сборка контекста нарратора (этап 4, P3): PromptBuilder.build считает бюджет Д1, вытесняет по
# ступеням ТЗ 11 (ходы -> выжимки сцен -> NPC -> локации) и кладёт итог в builder.last_plan.
# Неустранимое: правила, мир, состояние героя, scene_npcs, NPC with_hero/here/active, текущая
# локация, floor-ходы, главы и game_summary.
import json

import pytest
from master_kit import app_cfg, make_bundle, make_ctx, turn_record

from ai_dm.master.context import ContextPlan, request_tokens
from ai_dm.master.prompt import PromptBuilder
from ai_dm.state.memory import SceneSummary
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
    + [("locations", i) for i in ("far", "forest", "tie_a", "tie_b", "rev", "mid")]
)


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
    request, builder = build(make_scenario(registry, cfg))
    return builder.last_plan.estimate


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
    assert plan.cap == 800_000
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
    assert builder.last_plan.cap == 8_000


def test_estimate_uses_chars_per_token_of_config(registry, cfg):
    _, loose = build(make_scenario(registry, cfg), app=app_with(chars_per_token=5.0))
    _, tight = build(make_scenario(registry, cfg), app=app_with(chars_per_token=2.5))
    assert tight.last_plan.estimate > loose.last_plan.estimate * 1.9


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
        assert plan.estimate <= cap
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


def test_far_locations_dropped_first_ties_by_id(registry, cfg):
    _, builder = build(make_scenario(registry, cfg), app=app_with(cap=1))
    order = [i for s, i in builder.last_plan.dropped if s == "locations"]
    assert order == ["far", "forest", "tie_a", "tie_b", "rev", "mid"]


def test_current_location_is_never_dropped(registry, cfg):
    request, builder = build(make_scenario(registry, cfg), app=app_with(cap=1))
    assert shown_locations(request) == ["vale"]
    assert ("locations", "vale") not in builder.last_plan.dropped
    assert data_of(request)["location"]["id"] == "vale"


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
    _, again = build(make_scenario(registry, cfg), app=app_with(cap=bare))
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
