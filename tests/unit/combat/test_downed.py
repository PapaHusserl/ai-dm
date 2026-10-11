# 0 HP и намерения (шаг 19, ТЗ 5.1): ai_dm.combat.downed (вызывается движком при уроне).
#   Безымянный монстр (состояние в Participant.creature, в world.npcs его нет) на 0 HP:
#     обычная атака -- гибнет: Participant.status = "dead", событие
#       monster_died {id: <ref>, monster_id, by}; mortality_guard и мир не трогаются, флага нет;
#     nonlethal (только ближний бой) -- без сознания: участник status "down", у его creature
#       unconscious (source "0_hp"), смерти нет.
#   Именованный NPC из мира (mon(..., named=True)): смерть через mortality_guard.remove_creature
#     (Goal): npc_died {id, cause, by}, флаг npc_dead:<id> (см. test_monsters_in_world.py).
#   Герой на 0 HP: решает намерение ГРУППЫ атакующего (state.groups[group_id].intent); перед
#     применением лидеру группы (если он боеспособен) уходит DecisionPoint(kind="intent_reconsider",
#     actor=<лидер>, subject=<герой>, attacker=<атакующий>,
#     options=["keep", "intent:kill", "intent:capture", "intent:rob", "intent:drive_off",
#     "intent:spare"]) через его контроллер; "keep" (по умолчанию у EngineTactics) -- без изменений,
#     "intent:<x>" меняет groups[...].intent. state.defeat_group_id = группа атакующего.
#     Личное Participant.intent рядового на исход не влияет -- решает лидер.
#     kill (и падение без атакующего -- опасность): герой умирает по правилам 5e: unconscious 0_hp,
#       death_saves 0/0, status участника "down", спасбросок от смерти в НАЧАЛЕ его хода (контроллер
#       не спрашивается), cause = "goal" и by = Participant.last_hit_by (если удара не было --
#       cause "hazard", by None); 3 успеха -- стабилен (status остаётся "down"), nat 20 -- 1 HP,
#       status "active" и герой ДЕЙСТВУЕТ В ЭТОТ ЖЕ ХОД (контроллер спрашивается как обычно),
#       3 провала -- mark_dead; бой кончается сразу, если героев/союзников больше нет (outcome
#       "hero_dead"), иначе идёт дальше, пока стоят союзники (test_end.py).
#       Атаки по лежащему вблизи -- автокрит (провал +2), издали обычные (провал +1);
#       last_hit_by обновляется каждым ударом.
#     Группа последнего удара: падение от опасности (attacker_ref is None, hazard) сбрасывает
#       state.defeat_group_id в None; удар по уже лежащему герою обновляет defeat_group_id группой
#       ударившего (как и первое падение).
#   Именованный NPC, которого мир уже считает мёртвым (NPC.status "dead"), при смерти в бою:
#     remove_creature -> Rejected -- это ошибка программы, kill_monster бросает ValueError.
#     не kill: герой выбывает БЕЗ спасбросков: death_saves.stable = True, status участника "down",
#       его ход пропускается без бросков; бой идёт, пока у стороны героя есть боеспособные.
#   Исход при отсутствии боеспособных на стороне героев (если они не ушли):
#     намерение группы defeat_group_id == kill (или группы нет) -- outcome "hero_dying"
#       (не терминальный; "hero_dead" -- когда герой умер и бой кончился, test_end.py);
#     иначе -- "defeat_pending" (терминальный, бой завершён).
#   Победа союзников, пока герой умирает: герой стабилизируется (is_stable, death_saves 0/0).
#   Событие death_save {id, result: success|failure|stable|revived|dead} -- результат
#   rules.death_saves.roll_death_save на каждый спасбросок в начале хода.
import pytest
from combat_kit import (
    ScriptedRng,
    creature,
    down_hero,
    feature,
    hp,
    make_engine,
    make_fighter,
    make_zones,
    mon,
    part,
    set_hp,
)

from ai_dm.combat.controllers import ScriptedController
from ai_dm.rules.death_saves import is_dying, is_stable
from ai_dm.state.combat import Group

INTENT_OPTIONS = [
    "keep", "intent:kill", "intent:capture", "intent:rob", "intent:drive_off", "intent:spare",
]


class Forbidden:
    # контроллер, который не должны спрашивать
    def choose(self, options, ctx):
        raise AssertionError("контроллер не должен вызываться")


def goblins(registry, cfg, rng=None, intent="kill", controllers=None, hero_hp=3, **kwargs):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=rng, intent=intent,
        controllers=controllers,
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "hall")],
        **kwargs,
    )
    if hero_hp is not None:
        set_hp(engine, "hero", hero_hp)
    return engine


# в бою 19 КД героя, +4 у гоблина: d20 19 всегда попадает; 1d6 + 2 с 6 -> 8 урона

def drop_hero(engine, attacker="goblin_2"):
    return engine.perform(attacker, "attack:скимитар:hero")


def types(events):
    return [e.type for e in events]


# монстры

def test_monster_at_zero_hp_dies(registry, cfg):
    engine = goblins(registry, cfg, ScriptedRng(d20=[15], d8=[4]))
    set_hp(engine, "goblin_1", 3)
    engine.perform("hero", "attack:longsword:goblin_1")
    assert part(engine, "goblin_1").status == "dead"
    assert hp(engine, "goblin_1") == 0


def test_monster_death_event_and_no_world_trace(registry, cfg):
    engine = goblins(registry, cfg, ScriptedRng(d20=[15], d8=[4]))
    set_hp(engine, "goblin_1", 3)
    events = engine.perform("hero", "attack:longsword:goblin_1")
    died = [e for e in events if e.type == "monster_died"]
    assert [e.data for e in died] == [
        {"id": "goblin_1", "monster_id": "goblin_warrior", "by": "hero"}
    ]
    assert "npc_died" not in types(events)
    assert engine.world.flags == {}
    assert engine.world.npcs == {}


def test_dead_monster_leaves_the_fight(registry, cfg):
    engine = goblins(registry, cfg, ScriptedRng(d20=[15], d8=[4]))
    set_hp(engine, "goblin_1", 3)
    engine.perform("hero", "attack:longsword:goblin_1")
    assert part(engine, "goblin_1").status == "dead"
    assert engine.state.outcome is None


def test_nonlethal_blow_knocks_the_monster_out(registry, cfg):
    engine = goblins(registry, cfg, ScriptedRng(d20=[15], d8=[4]))
    set_hp(engine, "goblin_1", 3)
    events = engine.perform("hero", "attack:longsword:goblin_1:nonlethal")
    own = creature(engine, "goblin_1")
    assert own.hp_current == 0
    assert part(engine, "goblin_1").status == "down"
    assert "monster_died" not in types(events)
    assert [c.source for c in own.conditions if c.id == "unconscious"] == ["0_hp"]


def test_nonlethal_knockout_leaves_the_world_alone(registry, cfg):
    engine = goblins(registry, cfg, ScriptedRng(d20=[15], d8=[4]))
    set_hp(engine, "goblin_1", 3)
    engine.perform("hero", "attack:longsword:goblin_1:nonlethal")
    assert engine.world.flags == {}


def test_downed_monster_is_finished_by_a_normal_attack(registry, cfg):
    # лежащий: преимущество (два d20) и автокрит вблизи -> 2d8
    engine = goblins(registry, cfg, ScriptedRng(d20=[15, 15], d8=[1, 1]))
    set_hp(engine, "goblin_1", 0)
    part(engine, "goblin_1").status = "down"
    engine.perform("hero", "attack:longsword:goblin_1")
    assert part(engine, "goblin_1").status == "dead"


def test_downed_monster_is_not_a_fit_fighter(registry, cfg):
    engine = goblins(registry, cfg, ScriptedRng(d20=[15], d8=[4]))
    set_hp(engine, "goblin_2", 0)
    part(engine, "goblin_2").status = "down"
    set_hp(engine, "goblin_1", 3)
    engine.perform("hero", "attack:longsword:goblin_1")
    assert engine.state.outcome == "victory"


# герой падает: намерение группы атакующего

def test_kill_intent_makes_the_hero_dying(registry, cfg):
    engine = goblins(registry, cfg, ScriptedRng(d20=[19], d6=[6]))
    drop_hero(engine)
    hero = engine.heroes["hero"]
    assert hero.creature.hp_current == 0
    assert is_dying(hero.creature)
    assert hero.creature.death_saves.failures == 0
    assert hero.creature.death_saves.successes == 0
    assert [c.source for c in hero.creature.conditions if c.id == "unconscious"] == ["0_hp"]
    assert part(engine, "hero").status == "down"


def test_capture_intent_knocks_the_hero_out_without_death_saves(registry, cfg):
    engine = goblins(registry, cfg, ScriptedRng(d20=[19], d6=[6]), intent="capture")
    drop_hero(engine)
    hero = engine.heroes["hero"]
    assert hero.creature.hp_current == 0
    assert is_stable(hero.creature)
    assert hero.creature.death_saves.failures == 0
    assert hero.status == "active"
    assert part(engine, "hero").status == "down"


@pytest.mark.parametrize("intent", ["rob", "drive_off", "spare"])
def test_every_non_kill_intent_knocks_the_hero_out(registry, cfg, intent):
    engine = goblins(registry, cfg, ScriptedRng(d20=[19], d6=[6]), intent=intent)
    drop_hero(engine)
    assert is_stable(engine.heroes["hero"].creature)


def test_defeat_group_is_the_group_of_the_attacker(registry, cfg):
    engine = goblins(registry, cfg, ScriptedRng(d20=[19], d6=[6]))
    drop_hero(engine)
    assert engine.state.defeat_group_id == "goblins"


def test_leader_gets_an_intent_reconsider_decision(registry, cfg):
    leader = ScriptedController(["keep"])
    controllers = {"goblin_1": leader, "goblin_2": ScriptedController([])}
    engine = goblins(registry, cfg, ScriptedRng(d20=[19], d6=[6]), controllers=controllers)
    drop_hero(engine, attacker="goblin_2")
    point = leader.seen[0]
    assert point.kind == "intent_reconsider"
    assert point.actor == "goblin_1"
    assert point.subject == "hero"
    assert point.attacker == "goblin_2"
    assert point.options == INTENT_OPTIONS


def test_the_leader_is_asked_only_once_per_fall(registry, cfg):
    leader = ScriptedController(["keep"])
    controllers = {"goblin_1": leader, "goblin_2": ScriptedController([])}
    engine = goblins(registry, cfg, ScriptedRng(d20=[19], d6=[6]), controllers=controllers)
    drop_hero(engine)
    assert len(leader.seen) == 1


def test_keep_leaves_the_intent_unchanged(registry, cfg):
    controllers = {"goblin_1": ScriptedController(["keep"]), "goblin_2": ScriptedController([])}
    engine = goblins(registry, cfg, ScriptedRng(d20=[19], d6=[6]), controllers=controllers)
    drop_hero(engine)
    assert engine.state.groups["goblins"].intent == "kill"


def test_default_tactics_leader_keeps_the_intent(registry, cfg):
    engine = goblins(registry, cfg, ScriptedRng(d20=[19], d6=[6]), intent="capture")
    drop_hero(engine)
    assert engine.state.groups["goblins"].intent == "capture"


def test_leader_can_change_kill_to_capture(registry, cfg):
    controllers = {
        "goblin_1": ScriptedController(["intent:capture"]), "goblin_2": ScriptedController([]),
    }
    engine = goblins(registry, cfg, ScriptedRng(d20=[19], d6=[6]), controllers=controllers)
    drop_hero(engine)
    assert engine.state.groups["goblins"].intent == "capture"
    assert is_stable(engine.heroes["hero"].creature)


def test_leader_can_change_capture_to_kill(registry, cfg):
    controllers = {
        "goblin_1": ScriptedController(["intent:kill"]), "goblin_2": ScriptedController([]),
    }
    engine = goblins(
        registry, cfg, ScriptedRng(d20=[19], d6=[6]), intent="capture", controllers=controllers
    )
    drop_hero(engine)
    assert is_dying(engine.heroes["hero"].creature)


def test_dead_leader_is_not_asked(registry, cfg):
    leader = Forbidden()
    controllers = {"goblin_1": leader, "goblin_2": ScriptedController([])}
    engine = goblins(registry, cfg, ScriptedRng(d20=[19], d6=[6]), controllers=controllers)
    part(engine, "goblin_1").status = "dead"
    drop_hero(engine)
    assert engine.state.groups["goblins"].intent == "kill"
    assert is_dying(engine.heroes["hero"].creature)


def test_mixed_group_follows_the_leader_intent(registry, cfg):
    # лидер -- capture, рядовой лично настроен на kill: решает лидер
    engine = goblins(registry, cfg, ScriptedRng(d20=[19], d6=[6]), intent="capture")
    part(engine, "goblin_2").intent = "kill"
    drop_hero(engine, attacker="goblin_2")
    assert is_stable(engine.heroes["hero"].creature)
    assert engine.state.outcome == "defeat_pending"


def two_groups(registry, cfg, rng):
    return make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=rng, hero_zone="hall",
        monsters=[mon("goblin_1", "goblin_warrior", "hall", group="goblins"),
                  mon("goblin_2", "goblin_warrior", "hall", group="archers")],
        groups={
            "goblins": Group(leader_id="goblin_1", intent="capture"),
            "archers": Group(leader_id="goblin_2", intent="kill"),
        },
    )


def test_two_groups_the_last_blow_decides_kill(registry, cfg):
    engine = two_groups(registry, cfg, ScriptedRng(d20=[19], d6=[6]))
    set_hp(engine, "hero", 3)
    engine.perform("goblin_2", "attack:скимитар:hero")
    assert engine.state.defeat_group_id == "archers"
    assert is_dying(engine.heroes["hero"].creature)
    assert engine.state.outcome == "hero_dying"


def test_two_groups_the_last_blow_decides_capture(registry, cfg):
    engine = two_groups(registry, cfg, ScriptedRng(d20=[19], d6=[6]))
    set_hp(engine, "hero", 3)
    engine.perform("goblin_1", "attack:скимитар:hero")
    assert engine.state.defeat_group_id == "goblins"
    assert is_stable(engine.heroes["hero"].creature)
    assert engine.state.outcome == "defeat_pending"


def test_two_groups_earlier_blow_of_the_other_group_does_not_matter(registry, cfg):
    # goblin_2 (kill) ранит героя, добивает goblin_1 (capture) -> capture
    engine = two_groups(registry, cfg, ScriptedRng(d20=[19, 19], d6=[1, 6]))
    set_hp(engine, "hero", 10)
    engine.perform("goblin_2", "attack:скимитар:hero")
    assert hp(engine, "hero") == 7
    engine.perform("goblin_1", "attack:скимитар:hero")
    assert engine.state.defeat_group_id == "goblins"
    assert engine.state.outcome == "defeat_pending"


# исходы

def test_lone_hero_knocked_out_ends_the_fight_with_defeat_pending(registry, cfg):
    engine = goblins(registry, cfg, ScriptedRng(d20=[19], d6=[6]), intent="capture")
    events = drop_hero(engine)
    assert engine.state.outcome == "defeat_pending"
    assert engine.is_over
    assert types(events)[-1] == "combat_ended"


def test_lone_hero_dying_does_not_end_the_fight(registry, cfg):
    engine = goblins(registry, cfg, ScriptedRng(d20=[19], d6=[6]))
    events = drop_hero(engine)
    assert engine.state.outcome == "hero_dying"
    assert not engine.is_over
    assert "combat_ended" not in types(events)


def ally_party(registry, cfg, rng, intent="capture"):
    return make_engine(
        registry, cfg, heroes=[make_fighter(registry), make_fighter(registry, "ally")],
        rng=rng, intent=intent,
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )


def test_fight_goes_on_while_an_ally_is_still_standing(registry, cfg):
    engine = ally_party(registry, cfg, ScriptedRng(d20=[19], d6=[6]))
    set_hp(engine, "hero", 3)
    engine.perform("goblin_1", "attack:скимитар:hero")
    assert engine.state.outcome is None
    assert not engine.is_over


def test_defeat_pending_when_the_last_ally_falls_too(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry), make_fighter(registry, "ally")],
        rng=ScriptedRng(d20=[19, 19], d6=[6, 6]), intent="capture",
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "hall")],
    )
    set_hp(engine, "hero", 3)
    set_hp(engine, "ally", 3)
    engine.perform("goblin_1", "attack:скимитар:hero")
    engine.perform("goblin_2", "attack:скимитар:ally")
    assert engine.state.outcome == "defeat_pending"


def test_knocked_out_hero_skips_the_turn_without_rolls(registry, cfg):
    controllers = {
        "hero": Forbidden(), "ally": ScriptedController([]), "goblin_1": ScriptedController([]),
    }
    engine = ally_party(registry, cfg, ScriptedRng(d20=[19], d6=[6]))
    engine.controllers.update(controllers)
    set_hp(engine, "hero", 3)
    engine.perform("goblin_1", "attack:скимитар:hero")
    engine.step()
    assert engine.heroes["hero"].creature.death_saves.failures == 0


def test_allies_win_and_the_dying_hero_is_stabilized(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry, "ally"), make_fighter(registry)],
        monsters=[mon("goblin_1", "goblin_warrior", "hall")], rng=ScriptedRng(d20=[15], d8=[4]),
    )
    down_hero(engine, "hero", by="goblin_1")
    set_hp(engine, "goblin_1", 1)
    engine.perform("ally", "attack:longsword:goblin_1")
    hero = engine.heroes["hero"]
    assert engine.state.outcome == "victory"
    assert is_stable(hero.creature)
    assert hero.creature.hp_current == 0
    assert hero.status == "active"
    assert hero.creature.death_saves.failures == 0


# спасброски от смерти в бою

def dying_engine(registry, cfg, rng, by="goblin_1", hero_controller=None):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
        controllers={"hero": hero_controller or Forbidden(), "goblin_1": ScriptedController([])},
    )
    down_hero(engine, "hero", by=by)
    return engine


def full_round(engine):
    engine.step()
    engine.step()


def test_dying_hero_rolls_a_death_save_at_turn_start(registry, cfg):
    engine = dying_engine(registry, cfg, ScriptedRng(d20=[12]))
    engine.step()
    assert engine.heroes["hero"].creature.death_saves.successes == 1


def test_three_successes_stabilize_the_hero(registry, cfg):
    engine = dying_engine(registry, cfg, ScriptedRng(d20=[12, 12, 12]))
    for _ in range(3):
        full_round(engine)
    hero = engine.heroes["hero"]
    assert is_stable(hero.creature)
    assert hero.creature.hp_current == 0
    assert hero.status == "active"
    assert not engine.is_over


def test_natural_20_brings_the_hero_back_with_1_hp(registry, cfg):
    engine = dying_engine(
        registry, cfg, ScriptedRng(d20=[20]), hero_controller=ScriptedController([])
    )
    engine.step()
    hero = engine.heroes["hero"]
    assert hero.creature.hp_current == 1
    assert part(engine, "hero").status == "active"
    assert not [c for c in hero.creature.conditions if c.id == "unconscious"]
    assert engine.state.outcome is None


def test_natural_20_hero_acts_in_the_same_turn(registry, cfg):
    # спасбросок 20, затем атака: 15 + 5 = 20 попадает, 1d8 4 + 3 = 7 против 10 HP
    hero = ScriptedController(["attack:longsword:goblin_1"])
    engine = dying_engine(registry, cfg, ScriptedRng(d20=[20, 15], d8=[4]), hero_controller=hero)
    engine.step()
    assert hp(engine, "goblin_1") == 3
    assert hp(engine, "hero") == 1


def test_natural_20_hero_is_asked_for_a_turn_action(registry, cfg):
    hero = ScriptedController([])
    engine = dying_engine(registry, cfg, ScriptedRng(d20=[20]), hero_controller=hero)
    engine.step()
    assert [point.kind for point in hero.seen] == ["turn_action"]
    assert hero.seen[0].actor == "hero"


def test_hero_who_stays_down_does_not_act(registry, cfg):
    engine = dying_engine(registry, cfg, ScriptedRng(d20=[12]))
    engine.step()
    assert part(engine, "hero").status == "down"


def test_natural_1_counts_as_two_failures(registry, cfg):
    engine = dying_engine(registry, cfg, ScriptedRng(d20=[1]))
    engine.step()
    assert engine.heroes["hero"].creature.death_saves.failures == 2


def test_three_failures_kill_the_hero_with_a_goal_cause(registry, cfg):
    engine = dying_engine(registry, cfg, ScriptedRng(d20=[5, 5, 5]))
    for _ in range(2):
        full_round(engine)
    events = engine.step()
    hero = engine.heroes["hero"]
    assert hero.status == "dead"
    assert hero.death.cause == "goal"
    assert hero.death.by == "goblin_1"
    assert "hero_died" in types(events)
    assert engine.state.outcome == "hero_dead"
    assert engine.is_over
    assert engine.world.flags["hero_dead:hero"] is True


def test_hero_dying_outcome_while_saves_go_on(registry, cfg):
    engine = dying_engine(registry, cfg, ScriptedRng(d20=[5]))
    engine.step()
    assert engine.state.outcome == "hero_dying"
    assert not engine.is_over


def test_death_without_an_attacker_is_a_hazard(registry, cfg):
    engine = dying_engine(registry, cfg, ScriptedRng(d20=[2, 2, 2]), by=None)
    for _ in range(2):
        full_round(engine)
    engine.step()
    hero = engine.heroes["hero"]
    assert hero.death.cause == "hazard"
    assert hero.death.by is None


def test_two_natural_ones_kill_the_hero(registry, cfg):
    engine = dying_engine(registry, cfg, ScriptedRng(d20=[1, 1]))
    engine.step()
    engine.step()
    engine.step()
    assert engine.heroes["hero"].status == "dead"
    assert engine.is_over


def test_death_save_is_reported_as_an_event(registry, cfg):
    engine = dying_engine(registry, cfg, ScriptedRng(d20=[12]))
    events = engine.step()
    saves = [e.data for e in events if e.type == "death_save"]
    assert saves == [{"id": "hero", "result": "success"}]


def test_failed_death_save_event(registry, cfg):
    engine = dying_engine(registry, cfg, ScriptedRng(d20=[5]))
    saves = [e.data["result"] for e in engine.step() if e.type == "death_save"]
    assert saves == ["failure"]


# атаки по лежащему герою

def lying_hero_engine(registry, cfg, rng, goblin_zone="hall"):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", goblin_zone)],
    )
    down_hero(engine, "hero")
    return engine


def test_melee_hit_on_a_lying_hero_is_a_crit_and_two_failures(registry, cfg):
    # преимущество: два d20; крит: 2d6 + 2 и advantage_damage_dice 2d4 = 7 < 12 (не массовый урон)
    engine = lying_hero_engine(registry, cfg, ScriptedRng(d20=[15, 16], d6=[1, 2], d4=[1, 1]))
    events = engine.perform("goblin_1", "attack:скимитар:hero")
    attack = [e for e in events if e.type == "attack"][0]
    assert attack.data["outcome"] == "crit"
    assert engine.heroes["hero"].creature.death_saves.failures == 2


def test_ranged_hit_on_a_lying_hero_is_a_plain_hit_and_one_failure(registry, cfg):
    # преимущество и помеха (лежит, издали) гасятся: один d20
    engine = lying_hero_engine(
        registry, cfg, ScriptedRng(d20=[16], d6=[3]), goblin_zone="balcony"
    )
    events = engine.perform("goblin_1", "attack:короткий_лук:hero")
    attack = [e for e in events if e.type == "attack"][0]
    assert attack.data["outcome"] == "hit"
    assert engine.heroes["hero"].creature.death_saves.failures == 1


def test_blow_on_a_lying_hero_updates_last_hit_by(registry, cfg):
    engine = lying_hero_engine(registry, cfg, ScriptedRng(d20=[15, 16], d6=[1, 2], d4=[1, 1]))
    engine.perform("goblin_1", "attack:скимитар:hero")
    assert part(engine, "hero").last_hit_by == "goblin_1"


# группа последнего удара (ревью партии 5, п. 7)

def test_fall_from_a_hazard_resets_the_defeat_group(registry, cfg):
    # герой в зале с опасностью: спасбросок ЛОВ 5 + 1 < 12, урон 1d6 = 6 против 3 HP
    zones = make_zones(hall=[feature("hazard", damage="1d6", save="dex", dc=12)])
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], zones=zones,
        rng=ScriptedRng(d20=[5], d6=[6]),
        controllers={"hero": ScriptedController([]), "goblin_1": ScriptedController([])},
        monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    set_hp(engine, "hero", 3)
    engine.state.defeat_group_id = "goblins"
    engine.step()
    assert part(engine, "hero").status == "down"
    assert engine.state.defeat_group_id is None
    assert engine.state.outcome == "hero_dying"


def test_blow_on_a_lying_hero_updates_the_defeat_group(registry, cfg):
    # лежащего добивает goblin_2 из группы archers (преимущество, крит: 2 d20, 2d6, 2d4)
    engine = two_groups(registry, cfg, ScriptedRng(d20=[15, 16], d6=[1, 2], d4=[1, 1]))
    down_hero(engine, "hero")
    engine.state.defeat_group_id = "goblins"
    engine.perform("goblin_2", "attack:скимитар:hero")
    assert engine.state.defeat_group_id == "archers"


def test_blow_on_a_lying_hero_sets_the_group_when_there_was_none(registry, cfg):
    engine = lying_hero_engine(registry, cfg, ScriptedRng(d20=[15, 16], d6=[1, 2], d4=[1, 1]))
    assert engine.state.defeat_group_id is None
    engine.perform("goblin_1", "attack:скимитар:hero")
    assert engine.state.defeat_group_id == "goblins"


# смерть именованного NPC, уже мёртвого в мире (ревью партии 5, п. 8)

def test_kill_of_an_npc_the_world_already_buried_is_a_program_error(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=ScriptedRng(d20=[15], d8=[4]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall", named=True)],
    )
    engine.world.npcs["goblin_1"].status = "dead"
    set_hp(engine, "goblin_1", 3)
    with pytest.raises(ValueError):
        engine.perform("hero", "attack:longsword:goblin_1")
