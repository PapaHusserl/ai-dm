# Ж2 (docs/plan-zh2.md, п. 0.7, BACKLOG 46, коммит 2): world_sim/pending.py -- act-кандидаты,
# которые не дошли до world из-за мягкого сбоя, лежат в sim.pending_acts (JSON-строки) до
# следующей границы.
#   stash_acts: только kind act, без дублей по ref, потолок PENDING_MAX (остаются последние);
#   take_acts: старые act (владелец жив) + новые кандидаты по sort_key, очередь пустеет, свежий
#   кандидат с тем же ref вытесняет старый; load_acts: битые записи отбрасываются молча.
import pytest
from world_sim_kit import mini_bundle

from ai_dm.world_sim import pending
from ai_dm.world_sim.candidates import Candidate


def cand(ref, kind="act", owner_kind="npc", owner_id="aldric", item_id=None, **fields):
    return Candidate(
        ref=ref, kind=kind, owner_kind=owner_kind, owner_id=owner_id, owner_name="x",
        item_id=item_id or ref, **fields,
    )


def act(n, **fields):
    return cand(f"trigger:aldric:t{n}", item_id=f"t{n}", **fields)


def queue_refs(bundle):
    return [c.ref for c in pending.load_acts(bundle.world.sim.pending_acts)]


def bundle_of(registry, cfg):
    return mini_bundle(registry, cfg)


# load_acts

def test_load_acts_reads_json_records():
    raw = [act(1, then="a").model_dump_json(), act(2).model_dump_json()]
    loaded = pending.load_acts(raw)
    assert [c.ref for c in loaded] == ["trigger:aldric:t1", "trigger:aldric:t2"]
    assert loaded[0].then == "a"


def test_load_acts_skips_broken_json():
    raw = ["не json", act(1).model_dump_json()]
    assert [c.ref for c in pending.load_acts(raw)] == ["trigger:aldric:t1"]


def test_load_acts_skips_json_of_wrong_shape():
    raw = ['{"ref": "x"}', "[]", act(1).model_dump_json()]
    assert [c.ref for c in pending.load_acts(raw)] == ["trigger:aldric:t1"]


def test_load_acts_of_empty_is_empty():
    assert pending.load_acts([]) == []


def test_load_acts_keeps_order_after_broken_record():
    raw = [act(2).model_dump_json(), "{", act(1).model_dump_json()]
    assert [c.item_id for c in pending.load_acts(raw)] == ["t2", "t1"]


# stash_acts

def test_stash_keeps_act_candidates(registry, cfg):
    bundle = bundle_of(registry, cfg)
    pending.stash_acts(bundle, [act(1, then="пришёл")])
    stored = pending.load_acts(bundle.world.sim.pending_acts)
    assert [(c.ref, c.then) for c in stored] == [("trigger:aldric:t1", "пришёл")]
    assert all(isinstance(s, str) for s in bundle.world.sim.pending_acts)


def test_stash_ignores_verdict_candidates(registry, cfg):
    bundle = bundle_of(registry, cfg)
    pending.stash_acts(bundle, [cand("trigger:aldric:v", kind="verdict"), act(1)])
    assert queue_refs(bundle) == ["trigger:aldric:t1"]


def test_stash_of_only_verdicts_leaves_queue_empty(registry, cfg):
    bundle = bundle_of(registry, cfg)
    pending.stash_acts(bundle, [cand("secret:aldric:oath", kind="verdict")])
    assert bundle.world.sim.pending_acts == []


def test_stash_appends_to_existing_queue_in_order(registry, cfg):
    bundle = bundle_of(registry, cfg)
    pending.stash_acts(bundle, [act(1)])
    pending.stash_acts(bundle, [act(2), act(3)])
    assert queue_refs(bundle) == ["trigger:aldric:t1", "trigger:aldric:t2", "trigger:aldric:t3"]


def test_stash_skips_ref_already_in_queue(registry, cfg):
    bundle = bundle_of(registry, cfg)
    pending.stash_acts(bundle, [act(1, then="старый")])
    pending.stash_acts(bundle, [act(1, then="новый")])
    stored = pending.load_acts(bundle.world.sim.pending_acts)
    assert [(c.ref, c.then) for c in stored] == [("trigger:aldric:t1", "старый")]


def test_stash_skips_duplicate_ref_inside_one_call(registry, cfg):
    bundle = bundle_of(registry, cfg)
    pending.stash_acts(bundle, [act(1, then="первый"), act(1, then="второй")])
    stored = pending.load_acts(bundle.world.sim.pending_acts)
    assert [c.then for c in stored] == ["первый"]


def test_stash_drops_broken_records_of_queue(registry, cfg):
    bundle = bundle_of(registry, cfg)
    bundle.world.sim.pending_acts = ["мусор", act(1).model_dump_json()]
    pending.stash_acts(bundle, [act(2)])
    assert queue_refs(bundle) == ["trigger:aldric:t1", "trigger:aldric:t2"]
    assert "мусор" not in bundle.world.sim.pending_acts


def test_pending_max_is_twenty():
    assert pending.PENDING_MAX == 20


def test_stash_keeps_exactly_max_acts(registry, cfg):
    bundle = bundle_of(registry, cfg)
    pending.stash_acts(bundle, [act(n) for n in range(pending.PENDING_MAX)])
    assert len(bundle.world.sim.pending_acts) == pending.PENDING_MAX
    assert queue_refs(bundle)[0] == "trigger:aldric:t0"


def test_stash_over_max_keeps_the_latest(registry, cfg):
    bundle = bundle_of(registry, cfg)
    pending.stash_acts(bundle, [act(n) for n in range(pending.PENDING_MAX + 3)])
    refs = queue_refs(bundle)
    assert len(refs) == pending.PENDING_MAX
    assert refs[0] == "trigger:aldric:t3"
    assert refs[-1] == f"trigger:aldric:t{pending.PENDING_MAX + 2}"


def test_stash_over_max_across_calls_drops_the_oldest(registry, cfg):
    bundle = bundle_of(registry, cfg)
    pending.stash_acts(bundle, [act(n) for n in range(pending.PENDING_MAX)])
    pending.stash_acts(bundle, [act(100)])
    refs = queue_refs(bundle)
    assert len(refs) == pending.PENDING_MAX
    assert "trigger:aldric:t0" not in refs
    assert refs[-1] == "trigger:aldric:t100"


# stash_unapplied

def test_stash_unapplied_stashes_all_acts_when_nothing_applied(registry, cfg):
    bundle = bundle_of(registry, cfg)
    pending.stash_unapplied(
        bundle, [act(1), act(2), cand("trigger:aldric:v", kind="verdict")], frozenset()
    )
    assert queue_refs(bundle) == ["trigger:aldric:t1", "trigger:aldric:t2"]


def test_stash_unapplied_skips_act_with_applied_request(registry, cfg):
    bundle = bundle_of(registry, cfg)
    pending.stash_unapplied(bundle, [act(1)], frozenset({"trigger:aldric:t1"}))
    assert bundle.world.sim.pending_acts == []


def test_stash_unapplied_stashes_only_the_untouched_act(registry, cfg):
    bundle = bundle_of(registry, cfg)
    pending.stash_unapplied(bundle, [act(1), act(2)], {"trigger:aldric:t1"})
    assert queue_refs(bundle) == ["trigger:aldric:t2"]


def test_stash_unapplied_ignores_foreign_applied_refs(registry, cfg):
    bundle = bundle_of(registry, cfg)
    pending.stash_unapplied(bundle, [act(1)], {"other"})
    assert queue_refs(bundle) == ["trigger:aldric:t1"]


def test_stash_unapplied_keeps_existing_queue(registry, cfg):
    bundle = bundle_of(registry, cfg)
    pending.stash_acts(bundle, [act(1)])
    pending.stash_unapplied(bundle, [act(2)], {"trigger:aldric:t2"})
    assert queue_refs(bundle) == ["trigger:aldric:t1"]


# take_acts

def test_take_returns_new_candidates_when_queue_empty(registry, cfg):
    bundle = bundle_of(registry, cfg)
    fresh = [act(1)]
    taken = pending.take_acts(bundle, fresh)
    assert [c.ref for c in taken] == ["trigger:aldric:t1"]
    assert isinstance(taken, list)


def test_take_adds_pending_acts_to_new_candidates(registry, cfg):
    bundle = bundle_of(registry, cfg)
    pending.stash_acts(bundle, [act(1)])
    taken = pending.take_acts(bundle, [act(2)])
    assert [c.ref for c in taken] == ["trigger:aldric:t1", "trigger:aldric:t2"]


def test_take_empties_the_queue(registry, cfg):
    bundle = bundle_of(registry, cfg)
    pending.stash_acts(bundle, [act(1)])
    pending.take_acts(bundle, [])
    assert bundle.world.sim.pending_acts == []


def test_take_with_nothing_returns_old_acts_only(registry, cfg):
    bundle = bundle_of(registry, cfg)
    pending.stash_acts(bundle, [act(1)])
    assert [c.ref for c in pending.take_acts(bundle, [])] == ["trigger:aldric:t1"]


def test_take_fresh_candidate_replaces_old_with_same_ref(registry, cfg):
    bundle = bundle_of(registry, cfg)
    pending.stash_acts(bundle, [act(1, then="старый")])
    taken = pending.take_acts(bundle, [act(1, then="новый")])
    assert [(c.ref, c.then) for c in taken] == [("trigger:aldric:t1", "новый")]


def test_take_does_not_change_the_input_list(registry, cfg):
    bundle = bundle_of(registry, cfg)
    pending.stash_acts(bundle, [act(1)])
    fresh = [act(2)]
    pending.take_acts(bundle, fresh)
    assert [c.ref for c in fresh] == ["trigger:aldric:t2"]


def test_take_sorts_by_group_then_owner_then_item(registry, cfg):
    bundle = bundle_of(registry, cfg)
    pending.stash_acts(bundle, [act(1)])
    verdict = cand("trigger:brann:v", kind="verdict", owner_id="brann")
    taken = pending.take_acts(bundle, [act(2), verdict])
    # verdict раньше act; act -- по id триггера
    assert [c.ref for c in taken] == [verdict.ref, "trigger:aldric:t1", "trigger:aldric:t2"]


def test_take_sorts_old_act_before_new_by_item_id(registry, cfg):
    bundle = bundle_of(registry, cfg)
    pending.stash_acts(bundle, [act(9)])
    taken = pending.take_acts(bundle, [act(1)])
    assert [c.item_id for c in taken] == ["t1", "t9"]


def test_take_drops_broken_records(registry, cfg):
    bundle = bundle_of(registry, cfg)
    bundle.world.sim.pending_acts = ["{{{"]
    assert pending.take_acts(bundle, []) == []
    assert bundle.world.sim.pending_acts == []


@pytest.mark.parametrize("status", ["dead", "gone"])
def test_take_drops_act_of_departed_npc(registry, cfg, status):
    bundle = bundle_of(registry, cfg)
    pending.stash_acts(bundle, [act(1)])
    bundle.world.npcs["aldric"].status = status
    assert pending.take_acts(bundle, []) == []


def test_take_drops_act_of_missing_owner(registry, cfg):
    bundle = bundle_of(registry, cfg)
    pending.stash_acts(bundle, [cand("trigger:ghost:t", owner_id="ghost", item_id="t")])
    assert pending.take_acts(bundle, []) == []


def test_take_keeps_fresh_candidate_of_dead_owner(registry, cfg):
    # проверка владельца -- только у отложенных; свежие кандидаты уже отфильтрованы check
    bundle = bundle_of(registry, cfg)
    bundle.world.npcs["aldric"].status = "dead"
    assert [c.ref for c in pending.take_acts(bundle, [act(1)])] == ["trigger:aldric:t1"]


# owner_present

def test_owner_present_for_alive_npc(registry, cfg):
    bundle = bundle_of(registry, cfg)
    assert pending.owner_present(bundle, act(1)) is True


def test_owner_present_false_for_dead_npc(registry, cfg):
    bundle = bundle_of(registry, cfg)
    bundle.world.npcs["aldric"].status = "dead"
    assert pending.owner_present(bundle, act(1)) is False


def test_owner_present_false_for_unknown_owner(registry, cfg):
    bundle = bundle_of(registry, cfg)
    assert pending.owner_present(bundle, act(1, owner_id="ghost")) is False


def test_owner_present_true_for_faction_without_status(registry, cfg):
    bundle = bundle_of(registry, cfg)
    guild = cand("trigger:guild:t", owner_kind="faction", owner_id="guild", item_id="t")
    assert pending.owner_present(bundle, guild) is True


def test_owner_present_for_god_by_status(registry, cfg):
    bundle = bundle_of(registry, cfg)
    god = cand("trigger:morrah:t", owner_kind="god", owner_id="morrah", item_id="t")
    assert pending.owner_present(bundle, god) is True
    bundle.world.pantheon["morrah"].status = "dead"
    assert pending.owner_present(bundle, god) is False


def test_owner_present_for_hero_only_when_active(registry, cfg):
    bundle = bundle_of(registry, cfg)
    hero = bundle.heroes[0]
    cnd = cand("trigger:hero:t", owner_kind="hero", owner_id=hero.id, item_id="t")
    assert pending.owner_present(bundle, cnd) is True
    for status in ("dead", "in_afterlife"):
        hero.status = status
        assert pending.owner_present(bundle, cnd) is False
