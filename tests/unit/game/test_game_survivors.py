# Ж1 (docs/plan-zh1.md, пп. 0.1, 0.3, 0.8): выжившие боя в игре.
#   TurnRunner.end_fight (оба пути fold): classify -> settle_parley -> finish_combat ->
#     note_combat -> materialize -> fold_fight; выжившие попадают в world.npcs после записи
#     бестиария;
#   TurnRunner.commit: reveal_names по рассказу хода открывает имя выжившего (known_name),
#     ввод игрока имя не открывает.
from types import SimpleNamespace

import pytest
from game_kit import (
    combat_of,
    end_turn_number,
    enemies_surrender,
    make_rig,
    script_then_react,
    scripted,
    start_combat_call,
    text_step,
    tools_step,
)

from ai_dm.rules.survivors import LIFE_DEBT_TEXT
from ai_dm.state.creature import ActiveEffect
from ai_dm.state.world import NPC

# ход, на котором завершается бой в fight_rig (после одного play): turn_seq == 1
PREFIX = "goblin_warrior_t1_"


def fight_rig(registry, cfg, tmp_path, **reactive):
    steps = [tools_step(start_combat_call()), text_step("Гоблины бросаются на вас.")]
    rig = make_rig(registry, cfg, tmp_path, script_then_react(steps, **reactive))
    assert rig.runner.play("Бью ногой дверь").committed is True
    return rig


def part_of(rig, ref):
    return [p for p in combat_of(rig.runner).participants if p.ref == ref][0]


def finish(rig, outcome, statuses=None, fold=True):
    # бой завершён с исходом: end_fight зовётся напрямую на bundle раннера
    state = combat_of(rig.runner)
    state.outcome = outcome
    for ref, status in (statuses or {}).items():
        part_of(rig, ref).status = status
    rig.runner.end_fight(rig.runner.bundle, SimpleNamespace(), fold)
    return rig.runner.bundle


def survivors(bundle):
    return {i: n for i, n in bundle.world.npcs.items() if n.origin == "engine"}


@pytest.mark.parametrize("fold", [True, False])
def test_spared_enemies_become_npcs_on_both_paths(registry, cfg, tmp_path, fold):
    rig = fight_rig(registry, cfg, tmp_path)
    bundle = finish(rig, "victory", {"g1": "down", "g2": "down"}, fold=fold)
    assert sorted(survivors(bundle)) == [f"{PREFIX}1", f"{PREFIX}2"]


def test_dead_enemies_leave_no_survivors(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path)
    bundle = finish(rig, "victory", {"g1": "dead", "g2": "dead"})
    assert survivors(bundle) == {}


def test_survivor_has_hidden_name_and_hero_location(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path)
    bundle = finish(rig, "victory", {"g1": "down", "g2": "dead"})
    npc = bundle.world.npcs[f"{PREFIX}1"]
    assert (npc.name, npc.named, npc.known_name, npc.location_id) == (
        "Воин-гоблин 1", False, None, bundle.heroes[0].location_id,
    )


def test_bestiary_and_meeting_entries_are_both_written(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path)
    bundle = finish(rig, "victory", {"g1": "down", "g2": "dead"})
    texts = {(e.kind, e.ref): e.text for e in bundle.heroes[0].knowledge}
    assert texts[("creature", "goblin_warrior")] == "Бой: Воин-гоблин — победа"
    assert texts[("npc", f"{PREFIX}1")] == "Знакомство: Воин-гоблин 1"


def test_survivor_is_not_added_to_the_bestiary_as_named_npc(registry, cfg, tmp_path):
    # note_combat идёт до materialize: бестиарий пишется, а не пропускается как «NPC мира»
    rig = fight_rig(registry, cfg, tmp_path)
    bundle = finish(rig, "victory", {"g1": "down", "g2": "down"})
    assert [e.ref for e in bundle.heroes[0].knowledge if e.kind == "creature"] == [
        "goblin_warrior"
    ]


def test_surrendered_enemy_gets_neutral_attitude_and_memory(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path)
    bundle = finish(rig, "victory", {"g1": "surrendered", "g2": "dead"})
    npc = bundle.world.npcs[f"{PREFIX}1"]
    assert npc.attitude == cfg.survivors.surrendered
    assert [e.text for m in npc.memory for e in m.events] == ["сдался герою в бою"]


def test_fled_enemy_goes_to_neighbour_and_is_hostile(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path)
    bundle = finish(rig, "victory", {"g1": "fled", "g2": "dead"})
    npc = bundle.world.npcs[f"{PREFIX}1"]
    assert (npc.location_id, npc.attitude) == ("forest", cfg.survivors.fled)


def test_spared_enemy_attitude_is_plus_twenty(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path)
    bundle = finish(rig, "victory", {"g1": "down", "g2": "dead"})
    assert bundle.world.npcs[f"{PREFIX}1"].attitude == 20


def defect(rig, ref="g1", group="goblins"):
    part = part_of(rig, ref)
    part.creature.active_effects.append(
        ActiveEffect(id="parley_defected", source="hero", kind="flag", params={"group": group})
    )
    part.side = "heroes"
    part.group_id = "party"


def test_defector_is_friendly_with_life_debt(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path)
    defect(rig)
    bundle = finish(rig, "victory", {"g2": "dead"})
    npc = bundle.world.npcs[f"{PREFIX}1"]
    assert npc.attitude == cfg.survivors.defected
    assert [(g.kind, g.target, g.text) for g in npc.goals] == [
        ("life_debt", "hero", LIFE_DEBT_TEXT)
    ]


def test_defector_keeps_original_group(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path)
    defect(rig)
    bundle = finish(rig, "victory", {"g2": "dead"})
    assert bundle.world.npcs[f"{PREFIX}1"].groups == ["goblins"]


def test_defector_is_in_bestiary_and_met(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path)
    defect(rig)
    bundle = finish(rig, "victory", {"g2": "dead"})
    texts = {(e.kind, e.ref): e.text for e in bundle.heroes[0].knowledge}
    assert texts[("creature", "goblin_warrior")] == "Бой: Воин-гоблин — победа"
    assert texts[("npc", f"{PREFIX}1")] == "Знакомство: Воин-гоблин 1"


def test_lone_defector_kind_is_in_bestiary(registry, cfg, tmp_path):
    # перебежчик попадает в note_combat (turned), даже когда других гоблинов в бою нет
    rig = fight_rig(registry, cfg, tmp_path)
    defect(rig)
    state = combat_of(rig.runner)
    state.participants = [p for p in state.participants if p.ref != "g2"]
    bundle = finish(rig, "victory")
    assert [e.ref for e in bundle.heroes[0].knowledge if e.kind == "creature"] == [
        "goblin_warrior"
    ]


def test_survivor_id_has_turn_and_number_format(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path)
    turn = rig.runner.bundle.session.turn_seq
    bundle = finish(rig, "victory", {"g1": "down", "g2": "dead"})
    assert list(survivors(bundle)) == [f"goblin_warrior_t{turn}_1"]


def test_ended_by_master_spares_active_enemies(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path, end_combat=True)
    enemies_surrender(rig.runner)
    result = rig.runner.play(str(end_turn_number(rig.runner)))
    assert result.combat_outcome == "ended_by_master"
    assert len(survivors(rig.runner.bundle)) == 2


def test_victory_by_fight_leaves_no_survivors(registry, cfg, tmp_path):
    from game_kit import attack_or_move_number, drive

    rig = fight_rig(registry, cfg, tmp_path)
    drive(rig.runner, attack_or_move_number)
    assert survivors(rig.runner.bundle) == {}


def test_hero_defeat_leaves_no_survivors(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path)
    bundle = finish(rig, "defeat", {"g1": "down", "g2": "down"})
    assert survivors(bundle) == {}


def test_active_enemies_are_not_materialized_when_hero_flees(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path)
    bundle = finish(rig, "fled", {"g1": "down"})
    assert sorted(survivors(bundle)) == [f"{PREFIX}1"]


def test_survivor_id_skips_taken_id(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path)
    rig.runner.bundle.world.npcs[f"{PREFIX}1"] = NPC(
        id=f"{PREFIX}1", name="Прежний", means=["бой"], origin="engine",
    )
    bundle = finish(rig, "victory", {"g1": "down", "g2": "dead"})
    assert sorted(survivors(bundle)) == [f"{PREFIX}1", f"{PREFIX}2"]
    assert bundle.world.npcs[f"{PREFIX}1"].name == "Прежний"


# commit: имя открывается рассказом хода

def name_rig(registry, cfg, tmp_path, narration, **fields):
    from game_kit import make_bundle

    bundle = make_bundle(registry)
    data = {
        "id": "goblin_warrior_1", "name": "Мурк", "means": ["бой"], "origin": "engine",
        "location_id": bundle.heroes[0].location_id, "named": False,
        "combat": {"monster_id": "goblin_warrior", "label": "Воин-гоблин 1"},
    }
    bundle.world.npcs["goblin_warrior_1"] = NPC(**{**data, **fields})
    return make_rig(registry, cfg, tmp_path, scripted([text_step(narration)]), bundle=bundle)


def test_name_in_narration_opens_known_name(registry, cfg, tmp_path):
    rig = name_rig(registry, cfg, tmp_path, "Гоблин шепчет: меня зовут Мурк.")
    rig.runner.play("Спрашиваю имя")
    assert rig.runner.bundle.world.npcs["goblin_warrior_1"].known_name == "Мурк"


def test_name_only_in_player_input_stays_hidden(registry, cfg, tmp_path):
    rig = name_rig(registry, cfg, tmp_path, "Гоблин молчит.")
    rig.runner.play("Зову Мурк")
    assert rig.runner.bundle.world.npcs["goblin_warrior_1"].known_name is None


def test_unspoken_name_is_not_in_journal(registry, cfg, tmp_path):
    rig = name_rig(registry, cfg, tmp_path, "Гоблин молчит.")
    rig.runner.play("Смотрю")
    texts = [e.text for e in rig.runner.bundle.heroes[0].knowledge]
    assert all("Мурк" not in t for t in texts)


def test_opened_name_renames_meeting_entry_in_journal(registry, cfg, tmp_path):
    rig = name_rig(registry, cfg, tmp_path, "Гоблин шепчет: меня зовут Мурк.")
    hero = rig.runner.bundle.heroes[0]
    from ai_dm.rules.knowledge import MET, fact

    hero.knowledge.append(fact("npc", "goblin_warrior_1", MET + "Воин-гоблин 1", "seen", 0))
    rig.runner.play("Спрашиваю имя")
    assert "Знакомство: Мурк" in [e.text for e in rig.runner.bundle.heroes[0].knowledge]


def test_name_of_survivor_elsewhere_is_not_opened_by_narration(registry, cfg, tmp_path):
    rig = name_rig(registry, cfg, tmp_path, "Кто-то вспомнил Мурк.", location_id="forest")
    rig.runner.play("Слушаю")
    assert rig.runner.bundle.world.npcs["goblin_warrior_1"].known_name is None


# Ж2 (docs/plan-zh2.md, F2 в бою): end_fight до materialize зовёт on_kill по убитым врагам --
# родня (FamilyLink.ref = убитый) и отряд (общая группа, отношение <= 0, не идёт с героем)
# получают цель revenge и память kin_killed

def add_mate(rig, npc_id="mate", **fields):
    npc = NPC(**{"id": npc_id, "name": npc_id, "means": ["m"], "groups": ["goblins"], **fields})
    rig.runner.bundle.world.npcs[npc_id] = npc
    return npc


def revenge_of(npc):
    return [g for g in npc.goals if g.kind == "revenge"]


@pytest.mark.parametrize("fold", [True, False])
def test_squad_mate_of_killed_enemy_gets_revenge_on_both_paths(registry, cfg, tmp_path, fold):
    rig = fight_rig(registry, cfg, tmp_path)
    mate = add_mate(rig)
    finish(rig, "victory", {"g1": "dead", "g2": "dead"}, fold=fold)
    [goal] = revenge_of(mate)
    assert (goal.target, goal.status) == ("hero", "active")
    assert [t.id for t in mate.opportunity] == ["goal:revenge:hero"]


def test_revenge_goal_text_names_the_killed(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path)
    mate = add_mate(rig)
    finish(rig, "victory", {"g1": "dead", "g2": "down"})
    [goal] = revenge_of(mate)
    assert goal.text.endswith("Воин-гоблин 1")


def test_kin_killed_memory_is_written_for_the_avenger(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path)
    mate = add_mate(rig)
    finish(rig, "victory", {"g1": "dead", "g2": "down"})
    kinds = [e.kind for m in mate.memory for e in m.events]
    assert kinds == ["kin_killed"]


def test_every_killed_enemy_is_avenged_but_goal_is_one(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path)
    mate = add_mate(rig)
    finish(rig, "victory", {"g1": "dead", "g2": "dead"})
    assert len(revenge_of(mate)) == 1
    assert len(mate.opportunity) == 1


def test_kin_of_killed_enemy_gets_revenge(registry, cfg, tmp_path):
    from ai_dm.state.relations import FamilyLink

    rig = fight_rig(registry, cfg, tmp_path)
    link = FamilyLink(kind="parent", ref="g1", ref_kind="npc")
    kin = add_mate(rig, "son", groups=[], family=[link])
    finish(rig, "victory", {"g1": "dead", "g2": "down"})
    assert len(revenge_of(kin)) == 1


def test_no_revenge_when_nobody_died(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path)
    mate = add_mate(rig)
    finish(rig, "victory", {"g1": "down", "g2": "down"})
    assert mate.goals == []
    assert mate.memory == []


def test_follower_of_hero_does_not_avenge(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path)
    mate = add_mate(rig, follows=rig.runner.bundle.heroes[0].id)
    finish(rig, "victory", {"g1": "dead", "g2": "dead"})
    assert mate.goals == []


def test_friendly_squad_mate_does_not_avenge(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path)
    mate = add_mate(rig, attitude=30)
    finish(rig, "victory", {"g1": "dead", "g2": "dead"})
    assert mate.goals == []


def test_other_group_npc_does_not_avenge(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path)
    stranger = add_mate(rig, "wolf", groups=["wolves"])
    finish(rig, "victory", {"g1": "dead", "g2": "dead"})
    assert stranger.goals == []


def test_dead_npc_does_not_avenge(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path)
    ghost = add_mate(rig, "ghost", status="dead")
    finish(rig, "victory", {"g1": "dead", "g2": "dead"})
    assert ghost.goals == []


def test_survivor_of_the_same_fight_is_not_an_avenger(registry, cfg, tmp_path):
    # выжившие в мир попадают после on_kill: мстителем за павшего они не становятся
    rig = fight_rig(registry, cfg, tmp_path)
    bundle = finish(rig, "victory", {"g1": "dead", "g2": "fled"})
    [fled] = survivors(bundle).values()
    assert [g.kind for g in fled.goals] == ["revenge"]
    assert "за поражение в бою" in fled.goals[0].text


def kill_by(rig, killers, names):
    # killers: ref -> id убийцы (last_hit_by); names: ref -> имя участника
    for ref, killer in killers.items():
        part_of(rig, ref).last_hit_by = killer
        part_of(rig, ref).name = names[ref]


def test_only_the_kill_by_the_hero_is_avenged(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path)
    mate = add_mate(rig)
    kill_by(rig, {"g1": "hero", "g2": "hero2"}, {"g1": "Убитый героем", "g2": "Убитый напарником"})
    finish(rig, "victory", {"g1": "dead", "g2": "dead"})
    [goal] = revenge_of(mate)
    assert goal.text.endswith("Убитый героем")
    assert "Убитый напарником" not in goal.text
    assert [e.text for m in mate.memory for e in m.events] == ["герой убил: Убитый героем"]


def test_kill_by_another_hero_alone_gives_no_revenge(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path)
    mate = add_mate(rig)
    kill_by(rig, {"g1": "hero2", "g2": "hero2"}, {"g1": "А", "g2": "Б"})
    finish(rig, "victory", {"g1": "dead", "g2": "dead"})
    assert mate.goals == []
    assert mate.memory == []


def test_kill_without_killer_is_counted_for_the_hero(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path)
    mate = add_mate(rig)
    kill_by(rig, {"g1": None, "g2": "hero2"}, {"g1": "Взорвавшийся", "g2": "Б"})
    finish(rig, "victory", {"g1": "dead", "g2": "dead"})
    [goal] = revenge_of(mate)
    assert goal.text.endswith("Взорвавшийся")
