# Ожидаемый API (П6б этапа 3, STAGE3-PLAN A6 «nudge», Т-14, решения C/F): подталкивание к основной
# линии через game.boundary.finish_boundary(bundle, cfg, registry, world, run_id) -> результат
# (.bundle, .notices). Основная линия -- активные триггеры key: true владельцев key: true.
#   Касание сцены: ключевой NPC в локации закрытой сцены, либо изменение флага, на который
#   ссылается условие ключевого триггера (между двумя границами). Касание -> счётчик и ступень 0.
#   Каждые world.nudge_scenes сцен подряд без касания -- ступень +1 (sim.nudge.scenes_off_main,
#   sim.nudge.stage):
#     1 -- слух: world.notices / result.notices получает запись visibility "rumor";
#     2 -- контакт: состояние хода нарратора (PromptBuilder.state_data) получает поле "nudge" с
#          текстом "contact <npc_id>" (сигнал, как сигналы 2.3; без нового инструмента);
#     3 -- событие находит героя: кандидат kind "act" на ключевой триггер уходит в роль world.
#   После ступени 3: sim.nudge.waiting == False; ключевой триггер отдаётся world с пометкой
#   «герой не участвует» (в данных кандидата).
#   Без ключевых триггеров подталкивания нет.
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "master"))

from master_kit import app_cfg  # noqa: E402
from world_sim_kit import mini_bundle  # noqa: E402

from ai_dm.game import boundary  # noqa: E402
from ai_dm.master.prompt import PromptBuilder  # noqa: E402
from ai_dm.protocol.context import TurnContext  # noqa: E402

KEY_REF = "aldric:steal_grail"
EVERY = 8


class Done:
    verdicts = {}
    marks = []


class FakeWorld:
    max_calls_per_day = 0

    def __init__(self):
        self.calls = []

    def run(self, work, registry, cfg, candidates, run_id):
        self.calls.append([c.model_copy(deep=True) for c in candidates])
        return Done()


def away_bundle(registry, cfg):
    # герой в подвале, ключевой Олдрик в таверне: сцена ключевой линии не касается
    bundle = mini_bundle(registry, cfg)
    bundle.world.nudge_scenes = EVERY
    bundle.world.npcs["aldric"].opportunity[0].key = True
    bundle.heroes[0].location_id = "cellar"
    if bundle.session.current_scene is not None:
        bundle.session.current_scene.location_id = "cellar"
    return bundle


def boundaries(bundle, registry, cfg, count, world=None):
    # count границ подряд; возвращает бандл, список результатов
    results = []
    for number in range(count):
        scene = bundle.session.current_scene
        scene.closed_reason = "end_scene"
        result = boundary.finish_boundary(bundle, cfg, registry, world, f"bnd-{number}")
        assert result.error is None
        bundle = result.bundle
        results.append(result)
    return bundle, results


def nudge_of(bundle):
    return bundle.world.sim.nudge


def rumors(bundle, results):
    texts = [n.text for n in bundle.world.notices if n.visibility == "rumor"]
    return texts + [t for r in results for t in r.notices]


def state_of(bundle, registry, cfg):
    ctx = TurnContext(bundle, registry, cfg, mode="explore")
    request = PromptBuilder(app_cfg()).build(ctx, "осматриваюсь", "explore")
    return json.loads(request.messages[0].content[0].text)


# счётчик и ступени

def test_scenes_without_touch_count_up(registry, cfg):
    bundle, _ = boundaries(away_bundle(registry, cfg), registry, cfg, 3)
    assert nudge_of(bundle).scenes_off_main == 3
    assert nudge_of(bundle).stage == 0


def test_eighth_scene_gives_stage_1_rumor(registry, cfg):
    bundle, results = boundaries(away_bundle(registry, cfg), registry, cfg, EVERY)
    assert nudge_of(bundle).stage == 1
    assert rumors(bundle, results)


def test_seventh_scene_gives_no_stage(registry, cfg):
    bundle, results = boundaries(away_bundle(registry, cfg), registry, cfg, EVERY - 1)
    assert nudge_of(bundle).stage == 0
    assert not rumors(bundle, results)


def test_rumor_is_only_given_once_per_stage(registry, cfg):
    bundle, results = boundaries(away_bundle(registry, cfg), registry, cfg, EVERY + 3)
    assert len(rumors(bundle, results)) == 1


def test_sixteenth_scene_gives_stage_2_contact_signal(registry, cfg):
    bundle, _ = boundaries(away_bundle(registry, cfg), registry, cfg, 2 * EVERY)
    assert nudge_of(bundle).stage == 2
    signal = state_of(bundle, registry, cfg)["nudge"]
    assert "contact" in signal
    assert "aldric" in signal


def test_no_nudge_signal_before_stage_2(registry, cfg):
    bundle, _ = boundaries(away_bundle(registry, cfg), registry, cfg, EVERY)
    assert not state_of(bundle, registry, cfg).get("nudge")


def test_no_nudge_signal_on_fresh_world(registry, cfg):
    assert not state_of(away_bundle(registry, cfg), registry, cfg).get("nudge")


def test_stage_3_hands_key_trigger_to_world_as_act(registry, cfg):
    world = FakeWorld()
    bundle, _ = boundaries(away_bundle(registry, cfg), registry, cfg, 3 * EVERY, world)
    assert nudge_of(bundle).stage == 3
    acts = [c for calls in world.calls for c in calls if c.kind == "act"]
    assert len(acts) == 1
    assert acts[0].ref.endswith(KEY_REF)


def test_no_act_candidate_before_stage_3(registry, cfg):
    world = FakeWorld()
    boundaries(away_bundle(registry, cfg), registry, cfg, 3 * EVERY - 1, world)
    assert [c for calls in world.calls for c in calls if c.kind == "act"] == []


def test_after_stage_3_main_line_stops_waiting(registry, cfg):
    bundle, _ = boundaries(away_bundle(registry, cfg), registry, cfg, 3 * EVERY)
    assert nudge_of(bundle).waiting is False


def test_waiting_is_true_before_stage_3(registry, cfg):
    bundle, _ = boundaries(away_bundle(registry, cfg), registry, cfg, 2 * EVERY)
    assert nudge_of(bundle).waiting is True


def test_after_stage_3_key_trigger_goes_to_world_with_note(registry, cfg):
    world = FakeWorld()
    boundaries(away_bundle(registry, cfg), registry, cfg, 3 * EVERY, world)
    acts = [c for calls in world.calls for c in calls if c.kind == "act"]
    assert "не участвует" in acts[0].model_dump_json()


def test_stage_does_not_go_above_3(registry, cfg):
    bundle, _ = boundaries(away_bundle(registry, cfg), registry, cfg, 4 * EVERY)
    assert nudge_of(bundle).stage == 3


def test_nudge_scenes_is_taken_from_world(registry, cfg):
    bundle = away_bundle(registry, cfg)
    bundle.world.nudge_scenes = 2
    bundle, results = boundaries(bundle, registry, cfg, 2)
    assert nudge_of(bundle).stage == 1
    assert rumors(bundle, results)


# касание

def test_key_npc_in_scene_resets_counter(registry, cfg):
    bundle, _ = boundaries(away_bundle(registry, cfg), registry, cfg, 5)
    assert nudge_of(bundle).scenes_off_main == 5
    bundle.heroes[0].location_id = "tavern"
    bundle.session.current_scene.location_id = "tavern"
    bundle, _ = boundaries(bundle, registry, cfg, 1)
    assert nudge_of(bundle).scenes_off_main == 0
    assert nudge_of(bundle).stage == 0


def test_touch_resets_stage(registry, cfg):
    bundle, _ = boundaries(away_bundle(registry, cfg), registry, cfg, 2 * EVERY)
    assert nudge_of(bundle).stage == 2
    bundle.heroes[0].location_id = "tavern"
    bundle.session.current_scene.location_id = "tavern"
    bundle, _ = boundaries(bundle, registry, cfg, 1)
    assert nudge_of(bundle).stage == 0
    assert not state_of(bundle, registry, cfg).get("nudge")


def test_touch_after_stage_3_restores_waiting(registry, cfg):
    bundle, _ = boundaries(away_bundle(registry, cfg), registry, cfg, 3 * EVERY)
    bundle.heroes[0].location_id = "tavern"
    bundle.session.current_scene.location_id = "tavern"
    bundle, _ = boundaries(bundle, registry, cfg, 1)
    assert nudge_of(bundle).waiting is True


def test_flag_of_key_trigger_condition_resets_counter(registry, cfg):
    bundle, _ = boundaries(away_bundle(registry, cfg), registry, cfg, 3)
    assert nudge_of(bundle).scenes_off_main == 3
    bundle.world.flags["grail_seen"] = True
    bundle.world.npcs["aldric"].opportunity[0].state = "active"
    bundle, _ = boundaries(bundle, registry, cfg, 1)
    assert nudge_of(bundle).scenes_off_main == 0


def test_unrelated_flag_does_not_reset_counter(registry, cfg):
    bundle, _ = boundaries(away_bundle(registry, cfg), registry, cfg, 3)
    bundle.world.flags["weather"] = "rain"
    bundle, _ = boundaries(bundle, registry, cfg, 1)
    assert nudge_of(bundle).scenes_off_main == 4


def test_dead_key_npc_is_not_main_line(registry, cfg):
    bundle = away_bundle(registry, cfg)
    bundle.world.npcs["aldric"].status = "dead"
    bundle, results = boundaries(bundle, registry, cfg, EVERY)
    assert nudge_of(bundle).stage == 0
    assert not rumors(bundle, results)


def test_no_key_triggers_no_nudge(registry, cfg):
    bundle = away_bundle(registry, cfg)
    bundle.world.npcs["aldric"].opportunity[0].key = False
    bundle, results = boundaries(bundle, registry, cfg, 3 * EVERY)
    assert nudge_of(bundle).stage == 0
    assert not rumors(bundle, results)


def test_fired_key_trigger_is_not_main_line(registry, cfg):
    bundle = away_bundle(registry, cfg)
    bundle.world.npcs["aldric"].opportunity[0].state = "fired"
    bundle, _ = boundaries(bundle, registry, cfg, EVERY)
    assert nudge_of(bundle).stage == 0


def test_key_trigger_of_non_key_owner_is_not_main_line(registry, cfg):
    bundle = away_bundle(registry, cfg)
    bundle.world.npcs["aldric"].key = False
    bundle, _ = boundaries(bundle, registry, cfg, EVERY)
    assert nudge_of(bundle).stage == 0


def test_hero_only_main_line_gives_no_nudge(registry, cfg):
    from ai_dm.state.triggers import Trigger

    bundle = away_bundle(registry, cfg)
    bundle.world.npcs["aldric"].opportunity[0].key = False
    bundle.heroes[0].opportunity.append(
        Trigger.model_validate(
            {"id": "quest", "if": {"flag": "never"}, "then": "герой берётся за поиски", "key": True}
        )
    )
    bundle, results = boundaries(bundle, registry, cfg, EVERY)
    assert nudge_of(bundle).stage == 0
    assert not rumors(bundle, results)


def test_hero_only_main_line_gives_no_act_candidate(registry, cfg):
    from ai_dm.state.triggers import Trigger

    bundle = away_bundle(registry, cfg)
    bundle.world.npcs["aldric"].opportunity[0].key = False
    bundle.heroes[0].opportunity.append(
        Trigger.model_validate(
            {"id": "quest", "if": {"flag": "never"}, "then": "поиски", "key": True}
        )
    )
    world = FakeWorld()
    boundaries(bundle, registry, cfg, 3 * EVERY, world)
    assert [c for calls in world.calls for c in calls if c.kind == "act"] == []


def test_rumor_does_not_name_the_owner(registry, cfg):
    bundle, results = boundaries(away_bundle(registry, cfg), registry, cfg, EVERY)
    texts = rumors(bundle, results)
    assert texts
    for text in texts:
        assert "Олдрик" not in text
        assert "aldric" not in text


# D3: флаги на первой границе

def test_flag_already_set_on_first_boundary_is_not_a_touch(registry, cfg):
    bundle = away_bundle(registry, cfg)
    bundle.world.flags["grail_seen"] = True
    bundle, _ = boundaries(bundle, registry, cfg, 1)
    assert nudge_of(bundle).scenes_off_main == 1


def test_flags_are_remembered_while_main_line_is_empty(registry, cfg):
    bundle = away_bundle(registry, cfg)
    bundle.world.npcs["aldric"].opportunity[0].key = False
    bundle.world.flags["grail_seen"] = True
    bundle, _ = boundaries(bundle, registry, cfg, 2)
    bundle.world.npcs["aldric"].opportunity[0].key = True
    bundle, _ = boundaries(bundle, registry, cfg, 1)
    assert nudge_of(bundle).scenes_off_main == 1


# Ж2: verdict по событию (ref event:<id>) не получает пометку «герой не участвует»

def event_verdict(owner_id="plague"):
    from ai_dm.world_sim.candidates import Candidate, event_ref

    return Candidate(
        ref=event_ref(owner_id), kind="verdict", owner_kind="event", owner_id=owner_id,
        owner_name="чума", item_id=owner_id, condition_text="чума отступила",
    )


def test_mark_not_participating_skips_event_candidate(registry, cfg):
    from types import SimpleNamespace

    from ai_dm.state.world import GlobalEvent
    from ai_dm.world_sim.nudge import mark_not_participating

    bundle = away_bundle(registry, cfg)
    bundle.world.events.append(GlobalEvent(id="plague", type="чума"))
    check = SimpleNamespace(candidates=[event_verdict()])
    mark_not_participating(bundle, check)
    assert check.candidates[0].condition_text == "чума отступила"


def test_mark_not_participating_still_marks_key_trigger_next_to_event(registry, cfg):
    from types import SimpleNamespace

    from ai_dm.state.world import GlobalEvent
    from ai_dm.world_sim.candidates import Candidate
    from ai_dm.world_sim.nudge import NOT_PARTICIPATING, mark_not_participating

    bundle = away_bundle(registry, cfg)
    bundle.world.events.append(GlobalEvent(id="plague", type="чума"))
    key = Candidate(
        ref="trigger:aldric:steal_grail", kind="verdict", owner_kind="npc", owner_id="aldric",
        owner_name="Олдрик", item_id="steal_grail", condition_text="украл",
    )
    check = SimpleNamespace(candidates=[event_verdict(), key])
    mark_not_participating(bundle, check)
    assert check.candidates[0].condition_text == "чума отступила"
    assert check.candidates[1].condition_text.startswith(NOT_PARTICIPATING)


# mark_not_participating: кого помечают, кого нет

def cand(ref, owner_kind="npc", owner_id="aldric", item_id="steal_grail", kind="verdict"):
    from ai_dm.world_sim.candidates import Candidate

    return Candidate(
        ref=ref, kind=kind, owner_kind=owner_kind, owner_id=owner_id, owner_name="x",
        item_id=item_id, condition_text="условие",
    )


def marked(bundle, *candidates):
    from types import SimpleNamespace

    from ai_dm.world_sim.nudge import NOT_PARTICIPATING, mark_not_participating

    check = SimpleNamespace(candidates=list(candidates))
    mark_not_participating(bundle, check)
    return [c.condition_text.startswith(NOT_PARTICIPATING) for c in check.candidates]


def test_key_trigger_verdict_is_marked(registry, cfg):
    bundle = away_bundle(registry, cfg)
    assert marked(bundle, cand("trigger:aldric:steal_grail")) == [True]


def test_mark_keeps_original_condition_text_after_prefix(registry, cfg):
    from types import SimpleNamespace

    from ai_dm.world_sim.nudge import NOT_PARTICIPATING, mark_not_participating

    bundle = away_bundle(registry, cfg)
    check = SimpleNamespace(candidates=[cand("trigger:aldric:steal_grail")])
    mark_not_participating(bundle, check)
    assert check.candidates[0].condition_text == NOT_PARTICIPATING + "условие"


def test_already_marked_candidate_is_not_marked_twice(registry, cfg):
    from types import SimpleNamespace

    from ai_dm.world_sim.nudge import NOT_PARTICIPATING, mark_not_participating

    bundle = away_bundle(registry, cfg)
    first = cand("trigger:aldric:steal_grail")
    first.condition_text = NOT_PARTICIPATING + "условие"
    check = SimpleNamespace(candidates=[first])
    mark_not_participating(bundle, check)
    assert check.candidates[0].condition_text == NOT_PARTICIPATING + "условие"


def test_secret_verdict_is_not_marked_even_with_key_trigger_of_same_id(registry, cfg):
    bundle = away_bundle(registry, cfg)
    assert marked(bundle, cand("secret:aldric:steal_grail")) == [False]


def test_act_candidate_is_not_marked_and_does_not_stop_the_rest(registry, cfg):
    bundle = away_bundle(registry, cfg)
    act = cand("nudge:aldric:steal_grail", kind="act")
    assert marked(bundle, act, cand("trigger:aldric:steal_grail")) == [False, True]


def test_already_marked_candidate_does_not_stop_the_rest(registry, cfg):
    from ai_dm.world_sim.nudge import NOT_PARTICIPATING

    bundle = away_bundle(registry, cfg)
    first = cand("trigger:aldric:steal_grail")
    first.condition_text = NOT_PARTICIPATING + "условие"
    second = cand("trigger:aldric:other", item_id="other")
    bundle.world.npcs["aldric"].opportunity[0].id = "other"
    assert marked(bundle, first, second)[1] is True


def test_unknown_owner_is_skipped_without_error(registry, cfg):
    bundle = away_bundle(registry, cfg)
    ghost = cand("trigger:ghost:t", owner_id="ghost", item_id="t")
    assert marked(bundle, ghost, cand("trigger:aldric:steal_grail")) == [False, True]


def test_non_key_owner_is_not_marked_and_does_not_stop_the_rest(registry, cfg):
    bundle = away_bundle(registry, cfg)
    bundle.world.npcs["brann"].key = False
    bundle.world.npcs["brann"].opportunity[0].key = True
    brann = cand("trigger:brann:brann_trust", owner_id="brann", item_id="brann_trust")
    assert marked(bundle, brann, cand("trigger:aldric:steal_grail")) == [False, True]


def test_owner_without_key_attribute_counts_as_key(registry, cfg):
    bundle = away_bundle(registry, cfg)
    bundle.world.factions["guild"].opportunity[0].key = True
    guild = cand("trigger:guild:g", owner_kind="faction", owner_id="guild", item_id="guild_hunt")
    assert marked(bundle, guild) == [True]


def test_candidate_without_trigger_is_skipped_and_does_not_stop_the_rest(registry, cfg):
    bundle = away_bundle(registry, cfg)
    broken = cand("trigger:aldric:nope", item_id="nope")
    assert marked(bundle, broken, cand("trigger:aldric:steal_grail")) == [False, True]


def test_non_key_trigger_of_key_owner_is_not_marked(registry, cfg):
    bundle = away_bundle(registry, cfg)
    bundle.world.npcs["aldric"].opportunity[0].key = False
    assert marked(bundle, cand("trigger:aldric:steal_grail")) == [False]


def test_event_verdict_reaches_world_unmarked_after_stage_3(registry, cfg):
    from ai_dm.state.world import GlobalEvent

    bundle = away_bundle(registry, cfg)
    bundle.world.events.append(
        GlobalEvent(id="plague", type="чума", ends_when={"narrative": "чума отступила"})
    )
    world = FakeWorld()
    boundaries(bundle, registry, cfg, 3 * EVERY, world)
    texts = [c.condition_text for calls in world.calls for c in calls if c.ref == "event:plague"]
    assert texts
    assert set(texts) == {"чума отступила"}
