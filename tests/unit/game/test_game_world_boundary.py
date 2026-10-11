# Ожидаемый API (П4 этапа 3, STAGE3-PLAN A4): роль world на шаге 3 границы сцены. Контракт и
# помощники -- world_kit.py. Мини-пак: brann_trust (флаг met_brann + нарратив), секрет oath,
# steal_grail (флаг grail_seen, once, act). Мок без сети: ScriptedAdapter на каждую роль.
import json

import pytest
from game_kit import NOW, damage_call, settings
from world_kit import (
    BRANN,
    GRAIL,
    MARA,
    OATH,
    ReactiveWorld,
    add_mara_trigger,
    bundle_with_brann,
    bundle_without_candidates,
    candidate_refs,
    day_turn,
    end_turn,
    make_world_rig,
    narrator_turns,
    notice_call,
    npc_update_call,
    set_flag_call,
    verdict_call,
    world_step,
)

from ai_dm.llm.types import Text, ToolCall, ToolResult


def trigger_of(bundle, owner_id, trigger_id):
    return next(t for t in bundle.world.npcs[owner_id].opportunity if t.id == trigger_id)


def tool_results_text(request):
    parts = []
    for message in request.messages:
        for block in message.content:
            if isinstance(block, ToolResult):
                parts.append(block.content)
    return "\n".join(parts)


# вызов и кандидаты

def test_no_candidates_means_no_world_call(registry, cfg, tmp_path):
    bundle = bundle_without_candidates(registry, cfg)
    rig = make_world_rig(
        registry, cfg, tmp_path, narrator_turns(end_turn()), [], bundle=bundle
    )
    rig.play()
    assert rig.world.requests == []
    assert rig.world_records() == []


def test_three_npc_candidates_make_one_call(registry, cfg, tmp_path):
    bundle = bundle_with_brann(registry, cfg)
    add_mara_trigger(bundle)
    steps = world_step(verdict_call([(BRANN, False), (MARA, False), (OATH, False)]))
    rig = make_world_rig(registry, cfg, tmp_path, narrator_turns(end_turn()), steps, bundle=bundle)
    rig.play()
    first = [r for r in rig.world.requests if len(r.messages) == 1]
    assert len(first) == 1
    assert set(candidate_refs(first[0])) == {BRANN, MARA, OATH}


def test_candidate_order_is_stable(registry, cfg, tmp_path):
    orders = []
    for name in ("a", "b"):
        bundle = bundle_with_brann(registry, cfg)
        add_mara_trigger(bundle)
        steps = world_step(verdict_call([(BRANN, False), (MARA, False), (OATH, False)]))
        rig = make_world_rig(
            registry, cfg, tmp_path / name, narrator_turns(end_turn()), steps, bundle=bundle
        )
        rig.play()
        orders.append(candidate_refs(rig.world.requests[0]))
    assert orders[0] == orders[1] == [BRANN, MARA, OATH]


def test_world_request_uses_world_role_and_tool_set(registry, cfg, tmp_path):
    bundle = bundle_with_brann(registry, cfg)
    steps = world_step(verdict_call([(BRANN, False), (OATH, False)]))
    rig = make_world_rig(registry, cfg, tmp_path, narrator_turns(end_turn()), steps, bundle=bundle)
    rig.play()
    request = rig.world.requests[0]
    names = {t.name for t in request.tools}
    assert request.role == "world"
    assert {"world_verdict", "world_notice", "npc_update"} <= names
    assert "damage" not in names


# вердикт

def test_verdict_with_missing_ref_is_invalid_and_retried(registry, cfg, tmp_path):
    bundle = bundle_with_brann(registry, cfg)
    steps = world_step(verdict_call([(BRANN, True)]))
    steps += world_step(verdict_call([(BRANN, True), (OATH, False)], "wv-2"))
    rig = make_world_rig(registry, cfg, tmp_path, narrator_turns(end_turn()), steps, bundle=bundle)
    rig.play()
    assert "invalid" in tool_results_text(rig.world.requests[1]).lower()
    assert trigger_of(rig.runner.bundle, "brann", "brann_trust").fired_count == 1


def test_verdict_with_extra_ref_is_invalid(registry, cfg, tmp_path):
    bundle = bundle_with_brann(registry, cfg)
    items = [(BRANN, False), (OATH, False), ("trigger:ghost:nothing", False)]
    steps = world_step(verdict_call(items)) + world_step(
        verdict_call([(BRANN, False), (OATH, False)], "wv-2")
    )
    rig = make_world_rig(registry, cfg, tmp_path, narrator_turns(end_turn()), steps, bundle=bundle)
    rig.play()
    assert "invalid" in tool_results_text(rig.world.requests[1]).lower()


def test_three_invalid_verdicts_roll_back_boundary(registry, cfg, tmp_path):
    bundle = bundle_with_brann(registry, cfg)
    steps = []
    for n in range(3):
        steps += world_step(verdict_call([(BRANN, True)], f"wv-{n}"))
    rig = make_world_rig(registry, cfg, tmp_path, narrator_turns(end_turn()), steps, bundle=bundle)
    result = rig.play()[0]
    after = rig.runner.bundle
    assert result.boundary_failed
    assert after.session.boundary_pending is True
    assert trigger_of(after, "brann", "brann_trust").fired_count == 0
    assert after.chronicle.entries == []
    statuses = {r["turn_status"] for r in rig.world_records()}
    assert statuses == {"aborted"}


def test_holds_true_fires_trigger(registry, cfg, tmp_path):
    bundle = bundle_with_brann(registry, cfg)
    steps = world_step(verdict_call([(BRANN, True), (OATH, False)]))
    rig = make_world_rig(registry, cfg, tmp_path, narrator_turns(end_turn()), steps, bundle=bundle)
    rig.play()
    after = rig.runner.bundle
    assert trigger_of(after, "brann", "brann_trust").fired_count == 1
    assert len(after.world.fired) == 1
    assert [e.kind for e in after.chronicle.entries].count("trigger") == 1


def test_holds_false_does_not_fire_and_asks_again(registry, cfg, tmp_path):
    bundle = bundle_with_brann(registry, cfg)
    steps = world_step(verdict_call([(BRANN, False), (OATH, False)]))
    steps += world_step(verdict_call([(BRANN, False), (OATH, False)], "wv-2"))
    turns = narrator_turns(end_turn(1), end_turn(2))
    rig = make_world_rig(registry, cfg, tmp_path, turns, steps, bundle=bundle)
    rig.play(2)
    assert trigger_of(rig.runner.bundle, "brann", "brann_trust").fired_count == 0
    firsts = [r for r in rig.world.requests if len(r.messages) == 1]
    assert len(firsts) == 2
    assert BRANN in candidate_refs(firsts[1])


def test_secret_verdict_true_sets_narrative_ok(registry, cfg, tmp_path):
    bundle = bundle_with_brann(registry, cfg)
    steps = world_step(verdict_call([(BRANN, False), (OATH, True)]))
    rig = make_world_rig(registry, cfg, tmp_path, narrator_turns(end_turn()), steps, bundle=bundle)
    rig.play()
    assert rig.runner.bundle.world.npcs["aldric"].secrets[1].narrative_ok is True


# act: then триггера исполняется запросами

def grail_bundle(registry, cfg):
    bundle = bundle_without_candidates(registry, cfg)
    return bundle


def grail_turn():
    return narrator_turns(end_turn(1, flag="grail_seen"))


def test_act_candidate_comes_with_then(registry, cfg, tmp_path):
    steps = world_step()
    rig = make_world_rig(
        registry, cfg, tmp_path, grail_turn(), steps, bundle=grail_bundle(registry, cfg)
    )
    rig.play()
    candidates = [c for c in json.loads(
        rig.world.requests[0].messages[0].content[0].text)["candidates"] if c["ref"] == GRAIL]
    assert candidates[0]["kind"] == "act"
    assert candidates[0]["then"] == "Олдрик крадёт чашу"


def test_npc_update_with_location_moves_npc(registry, cfg, tmp_path):
    steps = world_step(npc_update_call("aldric", GRAIL, location_id="town"))
    rig = make_world_rig(
        registry, cfg, tmp_path, grail_turn(), steps, bundle=grail_bundle(registry, cfg)
    )
    rig.play()
    assert rig.runner.bundle.world.npcs["aldric"].location_id == "town"


def test_npc_update_without_then_ref_is_invalid(registry, cfg, tmp_path):
    steps = world_step(npc_update_call("aldric", "", location_id="town"))
    steps += world_step()
    rig = make_world_rig(
        registry, cfg, tmp_path, grail_turn(), steps, bundle=grail_bundle(registry, cfg)
    )
    rig.play()
    assert rig.runner.bundle.world.npcs["aldric"].location_id == "tavern"
    assert "invalid" in tool_results_text(rig.world.requests[1]).lower()


def test_death_by_goal_without_evidence_is_rejected(registry, cfg, tmp_path):
    steps = world_step(
        npc_update_call("mara", GRAIL, status="dead", cause="goal", evidence_ref="r42")
    )
    rig = make_world_rig(
        registry, cfg, tmp_path, grail_turn(), steps, bundle=grail_bundle(registry, cfg)
    )
    rig.play()
    assert rig.runner.bundle.world.npcs["mara"].status == "alive"
    assert "invalid" in tool_results_text(rig.world.requests[1]).lower()


class SaveThenKill:
    # сначала спасбросок NPC (actor), потом npc_update(dead, goal) со ссылкой на его бросок
    provider = "anthropic"
    model = "claude-sonnet-5-5"

    def __init__(self, roller="mara"):
        self.requests = []
        self.roller = roller

    def info(self):
        from ai_dm.llm.adapter import AdapterInfo

        return AdapterInfo(provider=self.provider, model=self.model)

    def complete(self, request):
        from ai_dm.llm.types import ChatResponse

        self.requests.append(request)
        results = tool_results_text(request)
        n = len(self.requests)
        if n == 1:
            data = {
                "type": "saving_throw", "ability": "con", "category": "hard", "stakes": "normal",
                "actor": self.roller,
            }
            content = [ToolCall(id="st-1", name="saving_throw", input=data)]
        elif n == 2:
            ref = json.loads(results)["result"]["roll_ref"]
            call = npc_update_call(
                "mara", GRAIL, status="dead", cause="goal", evidence_ref=ref
            )
            content = [ToolCall(id="nu-1", name="npc_update", input=call["input"])]
        else:
            content = [Text(text="Готово.")]
        stop = "end_turn" if n > 2 else "tool_use"
        return ChatResponse(
            content=content, stop_reason=stop, request_id=f"sk-{n}", model=request.model
        )


def test_death_with_npc_saving_throw_evidence_is_accepted(registry, cfg, tmp_path):
    rig = make_world_rig(
        registry, cfg, tmp_path, grail_turn(), SaveThenKill(), bundle=grail_bundle(registry, cfg)
    )
    rig.play()
    assert rig.runner.bundle.world.npcs["mara"].status == "dead"


def test_request_outside_world_set_is_not_available(registry, cfg, tmp_path):
    steps = world_step(damage_call("dm-1")) + world_step()
    rig = make_world_rig(
        registry, cfg, tmp_path, grail_turn(), steps, bundle=grail_bundle(registry, cfg)
    )
    rig.play()
    assert "not_available_in_mode" in tool_results_text(rig.world.requests[1])


# закадровые заметки

def test_visible_notice_is_delivered_at_new_scene(registry, cfg, tmp_path):
    steps = world_step(
        verdict_call([(BRANN, False), (OATH, False)]), notice_call("Мара сбежала из города.")
    )
    rig = make_world_rig(
        registry, cfg, tmp_path, narrator_turns(end_turn()), steps,
        bundle=bundle_with_brann(registry, cfg),
    )
    result = rig.play()[0]
    assert "Мара сбежала из города." in result.offscreen


def test_rumor_with_day_delay_is_delivered_after_a_day(registry, cfg, tmp_path):
    first = world_step(
        verdict_call([(BRANN, False), (OATH, False)]),
        notice_call("Говорят, в городе пропала чаша.", "rumor", "day"),
    )
    first += world_step(verdict_call([(BRANN, False), (OATH, False)], "wv-2"))
    rig = make_world_rig(
        registry, cfg, tmp_path, narrator_turns(end_turn(1), day_turn(2)), first,
        bundle=bundle_with_brann(registry, cfg),
    )
    results = rig.play(2)
    assert results[0].offscreen == []
    assert "Говорят, в городе пропала чаша." in results[1].offscreen


def test_hidden_notice_goes_only_to_chronicle_or_notices(registry, cfg, tmp_path):
    steps = world_step(
        verdict_call([(BRANN, False), (OATH, False)]),
        notice_call("Тайный сговор гильдии.", "hidden"),
    )
    rig = make_world_rig(
        registry, cfg, tmp_path, narrator_turns(end_turn()), steps,
        bundle=bundle_with_brann(registry, cfg),
    )
    result = rig.play()[0]
    assert result.offscreen == []
    assert "Тайный сговор гильдии." not in "".join(result.lines)


# потолок вызовов

def test_daily_cap_defers_narrative_but_structural_then_goes(registry, cfg, tmp_path):
    bundle = bundle_with_brann(registry, cfg)
    steps = world_step(verdict_call([(BRANN, False), (OATH, False)]))
    steps += world_step()
    turns = narrator_turns(end_turn(1), end_turn(2, flag="grail_seen"))
    rig = make_world_rig(registry, cfg, tmp_path, turns, steps, bundle=bundle, max_calls_per_day=1)
    rig.play(2)
    firsts = [r for r in rig.world.requests if len(r.messages) == 1]
    assert len(firsts) == 2
    second = candidate_refs(firsts[1])
    assert GRAIL in second
    assert BRANN not in second
    assert OATH not in second


def test_without_cap_second_boundary_asks_narrative_again(registry, cfg, tmp_path):
    bundle = bundle_with_brann(registry, cfg)
    steps = world_step(verdict_call([(BRANN, False), (OATH, False)]))
    steps += world_step(verdict_call([(BRANN, False), (OATH, False)], "wv-2"))
    rig = make_world_rig(
        registry, cfg, tmp_path, narrator_turns(end_turn(1), end_turn(2)), steps, bundle=bundle
    )
    rig.play(2)
    firsts = [r for r in rig.world.requests if len(r.messages) == 1]
    assert BRANN in candidate_refs(firsts[1])


# журнал

def test_world_records_have_role_run_id_and_committed_status(registry, cfg, tmp_path):
    bundle = bundle_with_brann(registry, cfg)
    steps = world_step(verdict_call([(BRANN, False), (OATH, False)]))
    rig = make_world_rig(registry, cfg, tmp_path, narrator_turns(end_turn()), steps, bundle=bundle)
    rig.play()
    records = rig.world_records()
    assert records
    assert all(r["run_id"].startswith("bnd-") for r in records)
    assert len({r["run_id"] for r in records}) == 1
    assert {r["turn_status"] for r in records} == {"committed"}


def test_world_cost_is_recorded_under_world_role(registry, cfg, tmp_path):
    bundle = bundle_with_brann(registry, cfg)
    rig = make_world_rig(
        registry, cfg, tmp_path, narrator_turns(end_turn()), ReactiveWorld(), bundle=bundle
    )
    rig.play()
    assert "world" in rig.runner.ledger.report(NOW.date()).session.by_role


# ревью П4: B1 evidence -- бросок этого же NPC

def test_death_with_roll_of_another_npc_is_rejected(registry, cfg, tmp_path):
    rig = make_world_rig(
        registry, cfg, tmp_path, grail_turn(), SaveThenKill(roller="aldric"),
        bundle=grail_bundle(registry, cfg),
    )
    rig.play()
    assert rig.runner.bundle.world.npcs["mara"].status == "alive"
    assert "invalid-death" in tool_results_text(rig.world.requests[2]) or (
        "invalid" in tool_results_text(rig.world.requests[2]).lower()
    )


def test_death_with_own_saving_throw_kills(registry, cfg, tmp_path):
    rig = make_world_rig(
        registry, cfg, tmp_path, grail_turn(), SaveThenKill(roller="mara"),
        bundle=grail_bundle(registry, cfg),
    )
    rig.play()
    assert rig.runner.bundle.world.npcs["mara"].status == "dead"


# B2: then_ref на verdict -- только после world_verdict holds=true

def move_brann(call_id="nu-1"):
    return npc_update_call("brann", BRANN, call_id, location_id="town")


def brann_location(rig):
    return rig.runner.bundle.world.npcs["brann"].location_id


def run_brann(registry, cfg, tmp_path, steps):
    rig = make_world_rig(
        registry, cfg, tmp_path, narrator_turns(end_turn()), steps,
        bundle=bundle_with_brann(registry, cfg),
    )
    rig.play()
    return rig


def test_npc_update_before_verdict_is_not_confirmed(registry, cfg, tmp_path):
    steps = world_step(move_brann())
    steps += world_step(verdict_call([(BRANN, False), (OATH, False)]))
    rig = run_brann(registry, cfg, tmp_path, steps)
    assert brann_location(rig) == "cellar"
    assert "verdict_not_confirmed" in tool_results_text(rig.world.requests[1])


def test_npc_update_after_rejected_verdict_is_not_confirmed(registry, cfg, tmp_path):
    steps = world_step(verdict_call([(BRANN, False), (OATH, False)]))
    steps[0]["tool_calls"].append(move_brann())
    rig = run_brann(registry, cfg, tmp_path, steps)
    assert brann_location(rig) == "cellar"
    assert "verdict_not_confirmed" in tool_results_text(rig.world.requests[1])


def test_npc_update_after_confirmed_verdict_is_executed(registry, cfg, tmp_path):
    steps = world_step(verdict_call([(BRANN, True), (OATH, False)]), move_brann())
    rig = run_brann(registry, cfg, tmp_path, steps)
    assert brann_location(rig) == "town"


# D5: then_ref у set_flag и world_notice

def test_set_flag_with_then_ref_of_rejected_verdict_is_invalid(registry, cfg, tmp_path):
    steps = world_step(
        verdict_call([(BRANN, False), (OATH, False)]), set_flag_call("brann_opened", BRANN)
    )
    rig = run_brann(registry, cfg, tmp_path, steps)
    assert "brann_opened" not in rig.runner.bundle.world.flags
    assert "verdict_not_confirmed" in tool_results_text(rig.world.requests[1])


def test_notice_with_then_ref_of_rejected_verdict_is_invalid(registry, cfg, tmp_path):
    steps = world_step(
        verdict_call([(BRANN, False), (OATH, False)]),
        notice_call("Проход открыт.", refs=[BRANN]) | {},
    )
    steps[0]["tool_calls"][1]["input"]["then_ref"] = BRANN
    rig = run_brann(registry, cfg, tmp_path, steps)
    assert rig.runner.bundle.world.notices == []
    assert "verdict_not_confirmed" in tool_results_text(rig.world.requests[1])


def test_set_flag_without_then_ref_is_allowed(registry, cfg, tmp_path):
    steps = world_step(
        verdict_call([(BRANN, False), (OATH, False)]), set_flag_call("rumor_started")
    )
    rig = run_brann(registry, cfg, tmp_path, steps)
    assert rig.runner.bundle.world.flags.get("rumor_started") is True


# D3: actor обязателен у проверок в режиме world

@pytest.mark.parametrize("name", ["skill_check", "saving_throw"])
def test_world_check_without_actor_is_actor_required(name, registry, cfg, tmp_path):
    data = {"type": name, "category": "medium", "stakes": "normal"}
    data.update({"skill": "persuasion"} if name == "skill_check" else {"ability": "con"})
    steps = world_step({"id": "ck-1", "name": name, "input": data}) + world_step()
    rig = make_world_rig(
        registry, cfg, tmp_path, grail_turn(), steps, bundle=grail_bundle(registry, cfg)
    )
    rig.play()
    assert "actor_required" in tool_results_text(rig.world.requests[1])


# D4: модель world без отдельного адаптера -- профиль провайдера рассказчика

def test_world_model_without_world_adapter_is_narrator_provider_profile(registry, cfg, tmp_path):
    from game_kit import make_rig, scripted, text_step, tools_step

    app = settings().app
    steps = [tools_step(*end_turn()), text_step("Конец.")]
    steps += world_step(verdict_call([(BRANN, False), (OATH, False)]))
    rig = make_rig(
        registry, cfg, tmp_path, scripted(steps), bundle=bundle_with_brann(registry, cfg)
    )
    rig.runner.play("ход")
    world_requests = [r for r in rig.adapter.requests if r.role == "world"]
    assert world_requests
    assert world_requests[0].model == app.profiles["anthropic"].world.model


def test_model_command_switches_world_profile_with_narrator(registry, tmp_path):
    from game_kit import FactorySpy, ReactiveAdapter, make_app

    app = make_app(
        registry, tmp_path, ReactiveAdapter(provider="gemini", model="gemini-3.8-flash"),
        adapter_factory=FactorySpy(), use_stored_model=False,
    )
    gemini_world = settings().app.profiles["gemini"].world.model
    anthropic_world = settings().app.profiles["anthropic"].world.model
    assert app.runner.new_world_session().model == gemini_world
    app.handle("/model narrator anthropic:claude-sonnet-5-5")
    assert app.runner.new_world_session().model == anthropic_world


# M10: достройка границы после сбоя world

def failed_then_ok_world():
    steps = [{"error": "fatal", "message": "сбой сети"}]
    steps += world_step(verdict_call([(BRANN, False), (OATH, False)]))
    return steps


def play_failed_boundary(registry, cfg, tmp_path, world, world_model=None):
    rig = make_world_rig(
        registry, cfg, tmp_path, narrator_turns(end_turn()), world,
        bundle=bundle_with_brann(registry, cfg), world_model=world_model,
    )
    rig.runner.play("ход")
    assert rig.runner.bundle.session.boundary_pending is True
    rig.runner.retry()
    return rig


def test_boundary_retry_after_world_failure_logs_aborted_then_committed(registry, cfg, tmp_path):
    rig = play_failed_boundary(registry, cfg, tmp_path, failed_then_ok_world())
    records = rig.world_records()
    assert rig.runner.bundle.session.boundary_pending is False
    assert records[0]["turn_status"] == "aborted"
    assert {r["turn_status"] for r in records[1:]} == {"committed"}
    assert len({r["run_id"] for r in records}) == 2


def test_replay_of_boundary_retry_after_world_failure_gives_same_bundle(registry, cfg, tmp_path):
    from ai_dm.llm.replay import ReplayAdapter

    first = play_failed_boundary(registry, cfg, tmp_path / "a", failed_then_ok_world())
    replay = ReplayAdapter(first.journal.read_records(), role="world")
    model = first.world_records()[0]["requested_model"]
    second = play_failed_boundary(registry, cfg, tmp_path / "b", replay, world_model=model)
    one, two = first.runner.bundle.world, second.runner.bundle.world
    assert one.model_dump_json() == two.model_dump_json()
