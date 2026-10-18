# Ж2 коммит 1 (docs/plan-zh2.md, пп. 0.1, 0.3, 0.4, F2 в бою): цели NPC и триггер-спутник.
#   add_goal / add_npc_goal(npc, kind, target, text, now_s) -> NpcGoal | None: цель и
#     спутник Trigger id "goal:<kind>:<target>" (once, if = all[структурная часть, narrative]);
#     повтор активной цели -> None;
#   close_goal / mark_fired / sweep -- закрытие (done / dropped, спутник disabled);
#   due(sim, now_s, every_days) -- редкая проверка по WorldSim.goals_checked_s;
#   avengers / on_kill -- мстители за убитого героем: родня и отряд, revenge, kin_killed.
from types import SimpleNamespace

import pytest
from protocol_kit import make_bundle

from ai_dm.config.settings import load_rules_config
from ai_dm.rules.goals import (
    NARRATIVE,
    add_goal,
    add_npc_goal,
    avengers,
    close_goal,
    due,
    has_active_goal,
    mark_fired,
    on_kill,
    sweep,
    trigger_id,
)
from ai_dm.state.combat import Participant
from ai_dm.state.relations import FamilyLink
from ai_dm.state.world import NPC, WorldSim

CFG = load_rules_config()
DAY = 86400


def make_npc(npc_id="a", **fields):
    return NPC(**{"id": npc_id, "name": npc_id, "means": ["m"], **fields})


def companion_of(npc, kind="revenge", target="hero"):
    return next(t for t in npc.opportunity if t.id == f"goal:{kind}:{target}")


def world_bundle(registry, *npcs):
    bundle = make_bundle(registry)
    bundle.world.npcs = {n.id: n for n in npcs}
    return bundle


# конфиг по умолчанию

def test_config_defaults_for_goals():
    assert CFG.survivors.revenge_attitude_max == -40
    assert CFG.world.goals_check_every_days == 1


# add_goal и спутник

def test_add_goal_creates_active_goal():
    npc = make_npc()
    goal = add_goal(npc, "revenge", "hero", "мстит", 77)
    assert npc.goals == [goal]
    assert (goal.kind, goal.target, goal.text, goal.since_s, goal.status) == (
        "revenge", "hero", "мстит", 77, "active",
    )


def test_add_goal_creates_companion_trigger_with_goal_id():
    npc = make_npc()
    add_goal(npc, "revenge", "hero", "мстит", 0)
    [trigger] = npc.opportunity
    assert trigger.id == "goal:revenge:hero" == trigger_id("revenge", "hero")
    assert trigger.then == "мстит"
    assert trigger.once is True
    assert trigger.state == "active"


def test_hero_goal_companion_requires_hero_alive_and_narrative():
    npc = make_npc()
    add_goal(npc, "revenge", "hero", "мстит", 0)
    cond = companion_of(npc).if_.model_dump(by_alias=True, exclude_none=True)
    assert cond == {
        "type": "all",
        "items": [
            {"type": "not", "item": {"type": "hero_dead"}},
            {"type": "narrative", "text": NARRATIVE["revenge"]},
        ],
    }


def test_npc_target_companion_requires_target_alive():
    npc = make_npc()
    add_npc_goal(npc, "love", "mira", "ищет встречи", 0)
    cond = companion_of(npc, "love", "mira").if_.model_dump(by_alias=True, exclude_none=True)
    assert cond == {
        "type": "all",
        "items": [
            {"type": "npc_status", "id": "mira", "is": "alive"},
            {"type": "narrative", "text": NARRATIVE["love"]},
        ],
    }


def test_narrative_differs_by_kind():
    assert NARRATIVE["revenge"] != NARRATIVE["debt"]
    assert {"revenge", "life_debt", "debt", "gratitude"} <= set(NARRATIVE)


def test_repeat_of_active_goal_returns_none_and_changes_nothing():
    npc = make_npc()
    add_goal(npc, "revenge", "hero", "мстит", 0)
    assert add_goal(npc, "revenge", "hero", "иначе", 5) is None
    assert len(npc.goals) == 1
    assert len(npc.opportunity) == 1
    assert npc.goals[0].text == "мстит"


def test_other_kind_or_target_is_a_separate_goal():
    npc = make_npc()
    add_goal(npc, "revenge", "hero", "x", 0)
    assert add_goal(npc, "debt", "hero", "x", 0) is not None
    assert add_goal(npc, "revenge", "hero2", "x", 0) is not None
    assert len(npc.goals) == 3
    assert len(npc.opportunity) == 3


def test_new_goal_after_closed_replaces_old_companion():
    npc = make_npc()
    add_goal(npc, "revenge", "hero", "старая", 0)
    close_goal(npc, "revenge", "hero", "done")
    again = add_goal(npc, "revenge", "hero", "новая", 9)
    assert again is not None
    assert [g.status for g in npc.goals] == ["done", "active"]
    [trigger] = npc.opportunity
    assert (trigger.then, trigger.state, trigger.fired_count) == ("новая", "active", 0)


def test_closed_goals_stay_in_npc_goals():
    npc = make_npc()
    add_goal(npc, "revenge", "hero", "x", 0)
    close_goal(npc, "revenge", "hero", "dropped")
    assert len(npc.goals) == 1


def test_has_active_goal():
    npc = make_npc()
    assert has_active_goal(npc) is False
    add_goal(npc, "debt", "hero", "x", 0)
    assert has_active_goal(npc) is True
    close_goal(npc, "debt", "hero", "done")
    assert has_active_goal(npc) is False


# close_goal

def test_close_goal_sets_status_and_disables_companion():
    npc = make_npc()
    add_goal(npc, "revenge", "hero", "x", 0)
    goal = close_goal(npc, "revenge", "hero", "dropped")
    assert goal.status == "dropped"
    assert companion_of(npc).state == "disabled"


def test_close_goal_done_status():
    npc = make_npc()
    add_goal(npc, "revenge", "hero", "x", 0)
    assert close_goal(npc, "revenge", "hero", "done").status == "done"


def test_close_goal_without_active_goal_returns_none():
    npc = make_npc()
    assert close_goal(npc, "revenge", "hero", "done") is None


def test_close_goal_does_not_touch_other_goals():
    npc = make_npc()
    add_goal(npc, "revenge", "hero", "x", 0)
    add_goal(npc, "debt", "hero", "y", 0)
    close_goal(npc, "revenge", "hero", "done")
    assert companion_of(npc, "debt").state == "active"
    assert [g.status for g in npc.goals] == ["done", "active"]


def test_close_goal_twice_second_is_none():
    npc = make_npc()
    add_goal(npc, "revenge", "hero", "x", 0)
    close_goal(npc, "revenge", "hero", "done")
    assert close_goal(npc, "revenge", "hero", "dropped") is None
    assert npc.goals[0].status == "done"


# mark_fired

def test_mark_fired_closes_goal_as_done():
    npc = make_npc()
    add_goal(npc, "revenge", "hero", "x", 0)
    mark_fired(npc, companion_of(npc))
    assert npc.goals[0].status == "done"


def test_mark_fired_ignores_ordinary_trigger():
    from ai_dm.state.triggers import Trigger

    npc = make_npc()
    add_goal(npc, "revenge", "hero", "x", 0)
    mark_fired(npc, Trigger(id="steal", **{"if": {"flag": "f"}}, then="t"))
    assert npc.goals[0].status == "active"


def test_mark_fired_with_target_containing_colon():
    npc = make_npc()
    add_goal(npc, "love", "a:b", "x", 0)
    mark_fired(npc, companion_of(npc, "love", "a:b"))
    assert npc.goals[0].status == "done"


def test_mark_fired_without_matching_goal_is_silent():
    npc = make_npc()
    add_goal(npc, "revenge", "hero", "x", 0)
    trigger = companion_of(npc)
    npc.goals[0].status = "dropped"
    mark_fired(npc, trigger)
    assert npc.goals[0].status == "dropped"


# sweep

def test_sweep_drops_goal_of_dead_carrier(registry):
    npc = make_npc(status="dead")
    add_goal(npc, "revenge", "hero", "x", 0)
    bundle = world_bundle(registry, npc)
    sweep(bundle.world, bundle.heroes)
    assert npc.goals[0].status == "dropped"
    assert companion_of(npc).state == "disabled"


def test_sweep_drops_goal_of_departed_carrier(registry):
    npc = make_npc(status="gone")
    add_goal(npc, "revenge", "hero", "x", 0)
    bundle = world_bundle(registry, npc)
    sweep(bundle.world, bundle.heroes)
    assert npc.goals[0].status == "dropped"


def test_sweep_drops_goal_when_hero_target_is_dead(registry):
    npc = make_npc()
    add_goal(npc, "revenge", "hero", "x", 0)
    bundle = world_bundle(registry, npc)
    bundle.heroes[0].status = "dead"
    sweep(bundle.world, bundle.heroes)
    assert npc.goals[0].status == "dropped"
    assert companion_of(npc).state == "disabled"


def test_sweep_drops_goal_when_npc_target_is_dead(registry):
    npc = make_npc("a")
    target = make_npc("b", status="dead")
    add_npc_goal(npc, "love", "b", "x", 0)
    bundle = world_bundle(registry, npc, target)
    sweep(bundle.world, bundle.heroes)
    assert npc.goals[0].status == "dropped"


def test_sweep_keeps_goal_with_live_target(registry):
    npc = make_npc("a")
    target = make_npc("b")
    add_npc_goal(npc, "love", "b", "x", 0)
    add_goal(npc, "revenge", "hero", "y", 0)
    bundle = world_bundle(registry, npc, target)
    sweep(bundle.world, bundle.heroes)
    assert [g.status for g in npc.goals] == ["active", "active"]
    assert companion_of(npc, "love", "b").state == "active"


def test_sweep_keeps_goal_of_unknown_target(registry):
    npc = make_npc()
    add_goal(npc, "revenge", "ghost", "x", 0)
    bundle = world_bundle(registry, npc)
    sweep(bundle.world, bundle.heroes)
    assert npc.goals[0].status == "active"


def test_sweep_does_not_reopen_or_change_closed_goals(registry):
    npc = make_npc(status="dead")
    add_goal(npc, "revenge", "hero", "x", 0)
    close_goal(npc, "revenge", "hero", "done")
    bundle = world_bundle(registry, npc)
    sweep(bundle.world, bundle.heroes)
    assert npc.goals[0].status == "done"


# due

def test_due_first_check_is_immediate():
    assert due(WorldSim(), 0, 1) is True


def test_due_not_before_every_days():
    sim = WorldSim(goals_checked_s=1000)
    assert due(sim, 1000 + DAY - 1, 1) is False


def test_due_exactly_at_every_days():
    sim = WorldSim(goals_checked_s=1000)
    assert due(sim, 1000 + DAY, 1) is True


def test_due_scales_with_every_days():
    sim = WorldSim(goals_checked_s=0)
    assert due(sim, 2 * DAY, 3) is False
    assert due(sim, 3 * DAY, 3) is True


def test_due_does_not_change_sim():
    sim = WorldSim(goals_checked_s=5)
    due(sim, 10 * DAY, 1)
    assert sim.goals_checked_s == 5


# avengers

def avenger_world(registry, *npcs):
    bundle = world_bundle(registry, *npcs)
    return bundle


def test_avengers_include_kin_by_family_link(registry):
    kin = make_npc("son", family=[FamilyLink(kind="parent", ref="victim", ref_kind="npc")])
    bundle = avenger_world(registry, kin, make_npc("stranger"))
    found = avengers(bundle.world, bundle.heroes[0], "victim", [], set())
    assert [n.id for n in found] == ["son"]


def test_avengers_ignore_hero_family_link_with_same_ref(registry):
    npc = make_npc("n", family=[FamilyLink(kind="spouse", ref="victim", ref_kind="hero")])
    bundle = avenger_world(registry, npc)
    assert avengers(bundle.world, bundle.heroes[0], "victim", [], set()) == []


def test_avengers_include_squad_by_shared_group_with_nonpositive_attitude(registry):
    mate = make_npc("mate", groups=["goblins"], attitude=0)
    foe = make_npc("foe", groups=["goblins"], attitude=-30)
    friend = make_npc("friend", groups=["goblins"], attitude=1)
    bundle = avenger_world(registry, mate, foe, friend)
    found = avengers(bundle.world, bundle.heroes[0], "victim", ["goblins"], set())
    assert [n.id for n in found] == ["foe", "mate"]


def test_avengers_skip_other_group(registry):
    npc = make_npc("n", groups=["wolves"])
    bundle = avenger_world(registry, npc)
    assert avengers(bundle.world, bundle.heroes[0], "victim", ["goblins"], set()) == []


def test_avengers_skip_follower_of_hero(registry):
    hero_id = make_bundle(registry).heroes[0].id
    npc = make_npc("n", groups=["goblins"], follows=hero_id)
    bundle = avenger_world(registry, npc)
    assert avengers(bundle.world, bundle.heroes[0], "victim", ["goblins"], set()) == []


def test_avengers_skip_fight_participants(registry):
    npc = make_npc("n", groups=["goblins"])
    bundle = avenger_world(registry, npc)
    assert avengers(bundle.world, bundle.heroes[0], "victim", ["goblins"], {"n"}) == []


def test_avengers_skip_dead_and_departed(registry):
    dead = make_npc("d", groups=["goblins"], status="dead")
    left = make_npc("l", groups=["goblins"], status="gone")
    bundle = avenger_world(registry, dead, left)
    assert avengers(bundle.world, bundle.heroes[0], "victim", ["goblins"], set()) == []


def test_avengers_skip_the_victim_himself(registry):
    victim = make_npc("victim", groups=["goblins"])
    bundle = avenger_world(registry, victim)
    assert avengers(bundle.world, bundle.heroes[0], "victim", ["goblins"], set()) == []


def test_avengers_kin_counts_even_with_good_attitude(registry):
    kin = make_npc(
        "son", attitude=50, family=[FamilyLink(kind="parent", ref="victim", ref_kind="npc")]
    )
    bundle = avenger_world(registry, kin)
    assert [n.id for n in avengers(bundle.world, bundle.heroes[0], "victim", [], set())] == ["son"]


def test_avengers_without_groups_find_no_squad(registry):
    bundle = avenger_world(registry, make_npc("n", groups=["goblins"]))
    assert avengers(bundle.world, bundle.heroes[0], "victim", [], set()) == []


def test_avengers_are_sorted_by_id_and_not_duplicated(registry):
    link = FamilyLink(kind="child", ref="victim", ref_kind="npc")
    b = make_npc("b", groups=["g"], family=[link])
    a = make_npc("a", groups=["g"])
    bundle = avenger_world(registry, b, a)
    found = avengers(bundle.world, bundle.heroes[0], "victim", ["g"], set())
    assert [n.id for n in found] == ["a", "b"]


# on_kill

def kill(bundle, groups=("goblins",), fighters=(), by="hero"):
    hero = bundle.heroes[0]
    group = next(iter(groups), "")
    victim = Participant(
        ref="victim", side="enemies", group_id=group, status="dead", name="Гоблин 1",
        last_hit_by=hero.id if by == "hero" else by,
    )
    others = [Participant(ref=ref, side="enemies", group_id=group) for ref in fighters]
    state = SimpleNamespace(participants=[victim, *others])
    return on_kill(bundle, hero, victim, state, CFG)


def test_on_kill_gives_revenge_goal_to_avengers(registry):
    mate = make_npc("mate", groups=["goblins"])
    bundle = world_bundle(registry, mate, make_npc("stranger"))
    now_s = bundle.world.clock.now_s
    created = kill(bundle)
    assert [n.id for n in created] == ["mate"]
    [goal] = mate.goals
    assert (goal.kind, goal.target, goal.since_s) == ("revenge", bundle.heroes[0].id, now_s)
    assert "Гоблин 1" in goal.text
    assert companion_of(mate, "revenge", bundle.heroes[0].id).state == "active"
    assert world_goals(bundle, "stranger") == []


def world_goals(bundle, npc_id):
    return bundle.world.npcs[npc_id].goals


def test_on_kill_writes_kin_killed_memory(registry):
    mate = make_npc("mate", groups=["goblins"])
    bundle = world_bundle(registry, mate)
    kill(bundle)
    [event] = [e for m in mate.memory for e in m.events]
    assert event.kind == "kin_killed"
    assert event.turn_seq == bundle.session.turn_seq
    assert "Гоблин 1" in event.text
    assert mate.memory[0].scene_id == bundle.session.current_scene.id


def test_on_kill_without_scene_gives_goal_but_no_memory(registry):
    mate = make_npc("mate", groups=["goblins"])
    bundle = world_bundle(registry, mate)
    bundle.session.current_scene = None
    kill(bundle)
    assert len(mate.goals) == 1
    assert mate.memory == []


def test_on_kill_skips_npc_who_already_has_this_revenge(registry):
    mate = make_npc("mate", groups=["goblins"])
    bundle = world_bundle(registry, mate)
    hero_id = bundle.heroes[0].id
    add_goal(mate, "revenge", hero_id, "старое", 0)
    assert kill(bundle) == []
    assert len(mate.goals) == 1
    assert mate.memory == []


def test_on_kill_returns_empty_when_nobody_avenges(registry):
    bundle = world_bundle(registry, make_npc("n"))
    assert kill(bundle) == []


def test_on_kill_does_not_touch_fight_participants(registry):
    fighter = make_npc("f", groups=["goblins"])
    bundle = world_bundle(registry, fighter)
    kill(bundle, fighters={"f"})
    assert fighter.goals == []


def test_on_kill_kin_gets_goal(registry):
    kin = make_npc("son", family=[FamilyLink(kind="parent", ref="victim", ref_kind="npc")])
    bundle = world_bundle(registry, kin)
    kill(bundle, groups=())
    assert kin.goals[0].kind == "revenge"


# on_kill: кто убил (Participant.last_hit_by)

def test_on_kill_by_hero_gives_goal_and_kin_killed(registry):
    mate = make_npc("mate", groups=["goblins"])
    bundle = world_bundle(registry, mate)
    assert [n.id for n in kill(bundle, by="hero")] == ["mate"]
    assert [e.kind for m in mate.memory for e in m.events] == ["kin_killed"]


def test_on_kill_without_killer_counts_for_the_hero(registry):
    mate = make_npc("mate", groups=["goblins"])
    bundle = world_bundle(registry, mate)
    assert [n.id for n in kill(bundle, by=None)] == ["mate"]
    assert mate.goals[0].target == bundle.heroes[0].id


@pytest.mark.parametrize("killer", ["hero2", "goblin_2", "wolf_1"])
def test_on_kill_by_another_hero_participant_or_monster_does_nothing(registry, killer):
    mate = make_npc("mate", groups=["goblins"])
    bundle = world_bundle(registry, mate)
    assert kill(bundle, by=killer) == []
    assert mate.goals == []
    assert mate.opportunity == []
    assert mate.memory == []


# on_kill: жертва -- NPC мира (имя как его видит игрок)

def kill_world_npc(bundle, victim, groups=("goblins",), fighters=()):
    hero = bundle.heroes[0]
    part = Participant(
        ref=victim.id, side="enemies", group_id=next(iter(groups), ""), status="dead",
        name="Гоблин", last_hit_by=hero.id,
    )
    others = [Participant(ref=ref, side="enemies", group_id="goblins") for ref in fighters]
    state = SimpleNamespace(participants=[part, *others])
    return on_kill(bundle, hero, part, state, CFG)


def hidden_victim(**fields):
    return make_npc(
        "victim", name="Мурк", named=True, origin="engine",
        combat={"monster_id": "goblin_warrior", "label": "Воин-гоблин 1"}, **fields,
    )


def test_on_kill_names_world_victim_by_shown_name(registry):
    mate = make_npc("mate", groups=["goblins"])
    bundle = world_bundle(registry, hidden_victim(), mate)
    kill_world_npc(bundle, bundle.world.npcs["victim"])
    assert mate.goals[0].text == "мстит герою за гибель: Воин-гоблин 1"
    assert "Мурк" not in mate.memory[0].events[0].text


def test_on_kill_names_world_victim_by_known_name_once_opened(registry):
    mate = make_npc("mate", groups=["goblins"])
    bundle = world_bundle(registry, hidden_victim(known_name="Мурк"), mate)
    kill_world_npc(bundle, bundle.world.npcs["victim"])
    assert mate.goals[0].text == "мстит герою за гибель: Мурк"


# on_npc_killed и avenge: герой убил NPC мира вне боя

def killed(bundle, victim_id="victim"):
    from ai_dm.rules.goals import on_npc_killed

    return on_npc_killed(bundle, bundle.heroes[0], bundle.world.npcs[victim_id], CFG)


def test_on_npc_killed_gives_revenge_to_kin(registry):
    kin = make_npc("son", family=[FamilyLink(kind="parent", ref="victim", ref_kind="npc")])
    bundle = world_bundle(registry, make_npc("victim", name="Олдрик"), kin, make_npc("stranger"))
    now_s = bundle.world.clock.now_s
    assert [n.id for n in killed(bundle)] == ["son"]
    [goal] = kin.goals
    assert (goal.kind, goal.target, goal.since_s) == ("revenge", bundle.heroes[0].id, now_s)
    assert goal.text == "мстит герою за гибель: Олдрик"
    assert world_goals(bundle, "stranger") == []


def test_on_npc_killed_gives_revenge_to_squad_by_victim_groups(registry):
    mate = make_npc("mate", groups=["clan"], attitude=-5)
    friend = make_npc("friend", groups=["clan"], attitude=10)
    other = make_npc("other", groups=["wolves"])
    bundle = world_bundle(registry, make_npc("victim", groups=["clan"]), mate, friend, other)
    assert [n.id for n in killed(bundle)] == ["mate"]


def test_on_npc_killed_victim_without_groups_has_no_squad(registry):
    bundle = world_bundle(registry, make_npc("victim"), make_npc("n", groups=["clan"]))
    assert killed(bundle) == []


def test_on_npc_killed_victim_himself_never_avenges(registry):
    bundle = world_bundle(registry, make_npc("victim", groups=["clan"]))
    assert killed(bundle) == []


def test_on_npc_killed_dead_squad_member_does_not_avenge(registry):
    dead = make_npc("d", groups=["clan"], status="dead")
    bundle = world_bundle(registry, make_npc("victim", groups=["clan"]), dead)
    assert killed(bundle) == []


def test_on_npc_killed_names_victim_by_shown_name(registry):
    kin = make_npc("son", family=[FamilyLink(kind="parent", ref="victim", ref_kind="npc")])
    bundle = world_bundle(registry, hidden_victim(), kin)
    killed(bundle)
    assert kin.goals[0].text == "мстит герою за гибель: Воин-гоблин 1"


def test_on_npc_killed_writes_kin_killed_memory(registry):
    kin = make_npc("son", family=[FamilyLink(kind="parent", ref="victim", ref_kind="npc")])
    bundle = world_bundle(registry, make_npc("victim", name="Олдрик"), kin)
    killed(bundle)
    [event] = [e for m in kin.memory for e in m.events]
    assert event.kind == "kin_killed"
    assert event.text == "герой убил: Олдрик"
    assert event.turn_seq == bundle.session.turn_seq
    assert kin.memory[0].scene_id == bundle.session.current_scene.id


def test_on_npc_killed_memory_text_is_cut_to_limit(registry):
    from ai_dm.state.relations import NPC_EVENT_TEXT_MAX

    kin = make_npc("son", family=[FamilyLink(kind="parent", ref="victim", ref_kind="npc")])
    bundle = world_bundle(registry, make_npc("victim", name="Я" * 300), kin)
    killed(bundle)
    assert len(kin.memory[0].events[0].text) == NPC_EVENT_TEXT_MAX


def test_on_npc_killed_without_scene_gives_goal_but_no_memory(registry):
    kin = make_npc("son", family=[FamilyLink(kind="parent", ref="victim", ref_kind="npc")])
    bundle = world_bundle(registry, make_npc("victim"), kin)
    bundle.session.current_scene = None
    assert [n.id for n in killed(bundle)] == ["son"]
    assert kin.memory == []


def test_on_npc_killed_skips_npc_with_same_active_revenge(registry):
    kin = make_npc("son", family=[FamilyLink(kind="parent", ref="victim", ref_kind="npc")])
    bundle = world_bundle(registry, make_npc("victim"), kin)
    add_goal(kin, "revenge", bundle.heroes[0].id, "старое", 0)
    assert killed(bundle) == []
    assert len(kin.goals) == 1
    assert kin.memory == []


def test_on_npc_killed_creates_goal_companion(registry):
    kin = make_npc("son", family=[FamilyLink(kind="parent", ref="victim", ref_kind="npc")])
    bundle = world_bundle(registry, make_npc("victim"), kin)
    killed(bundle)
    assert companion_of(kin, "revenge", bundle.heroes[0].id).state == "active"


def test_on_npc_killed_returns_list_of_new_avengers_only(registry):
    link = FamilyLink(kind="parent", ref="victim", ref_kind="npc")
    old = make_npc("a_old", family=[link])
    new = make_npc("b_new", family=[link])
    bundle = world_bundle(registry, make_npc("victim"), old, new)
    add_goal(old, "revenge", bundle.heroes[0].id, "старое", 0)
    assert [n.id for n in killed(bundle)] == ["b_new"]


# skipped / put_goal

def test_skipped_only_for_goal_trigger_when_not_due():
    from ai_dm.rules.goals import skipped
    from ai_dm.state.triggers import Trigger

    npc = make_npc()
    add_goal(npc, "revenge", "hero", "x", 0)
    ordinary = Trigger(id="steal", **{"if": {"flag": "f"}}, then="t")
    goal_trigger = companion_of(npc)
    assert skipped(goal_trigger, False) is True
    assert skipped(goal_trigger, True) is False
    assert skipped(ordinary, False) is False
    assert skipped(ordinary, True) is False


def test_put_goal_appends_given_goal_and_companion_with_given_condition():
    from ai_dm.rules.goals import put_goal
    from ai_dm.state.relations import NpcGoal

    npc = make_npc()
    goal = NpcGoal(kind="rivalry", target="b", text="соперничает", since_s=4)
    alive = {"npc_status": {"id": "b", "is": "alive"}}
    assert put_goal(npc, goal, alive) is goal
    assert npc.goals == [goal]
    [trigger] = npc.opportunity
    assert trigger.id == "goal:rivalry:b"
    assert trigger.then == "соперничает"
    cond = trigger.if_.model_dump(by_alias=True, exclude_none=True)
    assert cond["items"][0] == {"type": "npc_status", "id": "b", "is": "alive"}


def test_add_npc_goal_keeps_text():
    npc = make_npc()
    goal = add_npc_goal(npc, "love", "mira", "ищет встречи", 3)
    assert goal.text == "ищет встречи"
    assert companion_of(npc, "love", "mira").then == "ищет встречи"


def test_sweep_after_closed_goal_still_drops_next_active_one(registry):
    npc = make_npc(status="dead")
    add_goal(npc, "revenge", "hero", "x", 0)
    close_goal(npc, "revenge", "hero", "done")
    add_goal(npc, "debt", "hero", "y", 0)
    bundle = world_bundle(registry, npc)
    sweep(bundle.world, bundle.heroes)
    assert [g.status for g in npc.goals] == ["done", "dropped"]


def test_avengers_after_dead_npc_still_find_alive_kin(registry):
    link = FamilyLink(kind="parent", ref="victim", ref_kind="npc")
    dead = make_npc("a", status="dead", family=[link])
    kin = make_npc("b", family=[link])
    bundle = avenger_world(registry, dead, kin)
    found = avengers(bundle.world, bundle.heroes[0], "victim", [], set())
    assert [n.id for n in found] == ["b"]


def test_on_kill_names_world_npc_victim_by_shown_name(registry):
    mate = make_npc("mate", groups=["goblins"])
    victim = make_npc(
        "victim", origin="engine", name="Секрет", combat={"label": "Разведчик 7"}, status="dead"
    )
    bundle = world_bundle(registry, mate, victim)
    kill(bundle)
    assert "Разведчик 7" in mate.goals[0].text
    assert "Секрет" not in mate.goals[0].text
    assert "Разведчик 7" in mate.memory[0].events[0].text


def test_on_kill_continues_after_avenger_who_already_has_revenge(registry):
    first = make_npc("a", groups=["goblins"])
    second = make_npc("b", groups=["goblins"])
    bundle = world_bundle(registry, first, second)
    add_goal(first, "revenge", bundle.heroes[0].id, "старое", 0)
    assert [n.id for n in kill(bundle)] == ["b"]


def test_put_goal_repeat_returns_none_and_appends_nothing():
    from ai_dm.rules.goals import put_goal
    from ai_dm.state.relations import NpcGoal

    npc = make_npc()
    add_goal(npc, "revenge", "hero", "x", 0)
    again = NpcGoal(kind="revenge", target="hero", text="y", since_s=1)
    assert put_goal(npc, again, {"not": {"hero_dead": True}}) is None
    assert len(npc.goals) == 1
    assert len(npc.opportunity) == 1
