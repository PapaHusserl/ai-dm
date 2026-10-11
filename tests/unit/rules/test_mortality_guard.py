# Ожидаемый API: ai_dm.rules.mortality_guard (страж 4.1 «у смерти есть причина»)
#   Rejected(BaseModel) -- определён в ai_dm.rules.results (D10), здесь реэкспортируется:
#       status == "rejected", reason: str, report_tag: str | None
#       (метка авто-репорта; для запроса без причины -- "invalid-death"; для уже мёртвого --
#       reason == "already_dead", report_tag None)
#   remove_creature(state: WorldState, creature_id: str, status: str, cause: str | None, *,
#                   by: str | None = None, text: str = "") -> list | Rejected
#       status: "dead" | "gone" (другое -> ValueError); cause: "goal" | "hazard" | "chance" |
#       "old_age" (то же, что DeathRecord.cause). Нет причины (None) или неизвестная -> возвращает
#       Rejected(report_tag="invalid-death"), состояние не меняется (NPC жив, death None).
#       Успех -> list[DomainEvent] (core.events; Rejected не возвращается): npc.status = status,
#       npc.death = DeathRecord(cause, by, at_s=state.clock.now_s,
#       location_id=npc.location_id, text)
#       -- запись и для "gone" (причина выбывания фиксируется всегда).
#       События (D3): "creature_removed" с data id / status / cause; при status == "dead" ещё
#       "npc_died" с data id / cause / by.
#       NPC уже со status == "dead" -> Rejected(reason="already_dead", report_tag=None), запись
#       смерти и состояние не меняются (B3). Неизвестный id -> KeyError (задокументировано, D8).
#       Авто-флаг "npc_dead:<id>" -- шаг 14 (партия 4), здесь не проверяется.
#   mark_dead(hero, cause, by, now_s) -> list[DomainEvent] | Rejected  (из rules.creatures, B3)
#       cause вне goal/hazard/chance/old_age -> Rejected(report_tag="invalid-death"), герой не
#       меняется (аудит 1 п. 2.9; ValidationError больше не бросается)
#   remove_hero(hero, status, cause, now_s, *, by=None, text="") -> list | Rejected
#       по тем же правилам, что remove_creature: status "dead" | "gone" (иначе ValueError);
#       нет/неизвестная причина -> Rejected("invalid-death"); уже dead -> Rejected("already_dead");
#       успех: hero.status = status, hero.death = DeathRecord(...), события creature_removed
#       (+ hero_died при "dead"); снимает концентрацию
#       hero.status = "dead", hero.death = DeathRecord(cause, by, at_s=now_s, location_id=
#       hero.location_id); событие "hero_died" с data id / cause / by; снимает концентрацию
#       (creature.concentration = None и эффекты expires.kind == "concentration", B4).
#       Герой уже мёртв -> no-op: DeathRecord не перезаписывается, возвращает [].
import pytest

from ai_dm.core.events import DomainEvent
from ai_dm.core.rng import Rng
from ai_dm.rules.mortality_guard import Rejected, mark_dead, remove_creature, remove_hero
from ai_dm.state.creature import ActiveEffect, Concentration, CreatureState, Expiry
from ai_dm.state.death import DeathRecord
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState
from ai_dm.state.world import NPC, WorldState


def make_world(now_s=0):
    npc = NPC(id="oldrik", name="Олдрик", means=["клинок"], location_id="tavern")
    world = WorldState(world_id="w1", rng=Rng(1).state, npcs={"oldrik": npc})
    world.clock.now_s = now_s
    return world


# без причины

def test_removal_without_cause_is_rejected():
    world = make_world()
    assert isinstance(remove_creature(world, "oldrik", "dead", None), Rejected)


def test_rejection_has_invalid_death_tag():
    result = remove_creature(make_world(), "oldrik", "dead", None)
    assert result.report_tag == "invalid-death"
    assert result.status == "rejected"


def test_rejected_removal_keeps_npc_alive():
    world = make_world()
    remove_creature(world, "oldrik", "dead", None)
    assert world.npcs["oldrik"].status == "alive"
    assert world.npcs["oldrik"].death is None


def test_unknown_cause_is_rejected():
    world = make_world()
    result = remove_creature(world, "oldrik", "dead", "boredom")
    assert isinstance(result, Rejected)
    assert world.npcs["oldrik"].status == "alive"


def test_gone_without_cause_is_rejected():
    world = make_world()
    result = remove_creature(world, "oldrik", "gone", None)
    assert isinstance(result, Rejected)
    assert world.npcs["oldrik"].status == "alive"


def test_unknown_status_is_error():
    with pytest.raises(ValueError):
        remove_creature(make_world(), "oldrik", "alive", "goal")


# с причиной

@pytest.mark.parametrize("cause", ["goal", "hazard", "chance", "old_age"])
def test_removal_with_each_cause_is_accepted(cause):
    world = make_world()
    result = remove_creature(world, "oldrik", "dead", cause)
    assert not isinstance(result, Rejected)
    assert world.npcs["oldrik"].status == "dead"


@pytest.mark.parametrize("cause", ["goal", "hazard", "chance", "old_age"])
def test_death_record_has_given_cause(cause):
    world = make_world()
    remove_creature(world, "oldrik", "dead", cause)
    assert world.npcs["oldrik"].death.cause == cause


def test_accepted_removal_returns_event_list():
    assert isinstance(remove_creature(make_world(), "oldrik", "dead", "goal"), list)


def test_death_record_is_written_with_time_place_and_killer():
    world = make_world(now_s=4000)
    remove_creature(world, "oldrik", "dead", "goal", by="hero1", text="убит в таверне")
    death = world.npcs["oldrik"].death
    assert isinstance(death, DeathRecord)
    assert death.by == "hero1"
    assert death.at_s == 4000
    assert death.location_id == "tavern"
    assert death.text == "убит в таверне"


def test_gone_with_cause_sets_status_and_record():
    world = make_world()
    result = remove_creature(world, "oldrik", "gone", "goal", by="hero1")
    assert not isinstance(result, Rejected)
    assert world.npcs["oldrik"].status == "gone"
    assert world.npcs["oldrik"].death.cause == "goal"


# события (D3)

def test_removal_events_are_domain_events():
    events = remove_creature(make_world(), "oldrik", "dead", "goal", by="hero1")
    assert events
    assert all(isinstance(e, DomainEvent) for e in events)


def test_removal_returns_creature_removed_event():
    events = remove_creature(make_world(), "oldrik", "dead", "goal", by="hero1")
    removed = [e for e in events if e.type == "creature_removed"]
    assert len(removed) == 1
    assert removed[0].data["id"] == "oldrik"
    assert removed[0].data["status"] == "dead"
    assert removed[0].data["cause"] == "goal"


def test_dead_removal_returns_npc_died_event():
    events = remove_creature(make_world(), "oldrik", "dead", "hazard", by="trap")
    died = [e for e in events if e.type == "npc_died"]
    assert len(died) == 1
    assert died[0].data["id"] == "oldrik"
    assert died[0].data["cause"] == "hazard"
    assert died[0].data["by"] == "trap"


def test_gone_removal_has_no_npc_died_event():
    events = remove_creature(make_world(), "oldrik", "gone", "goal")
    assert "npc_died" not in [e.type for e in events]


# уже мёртвый NPC и неизвестный id (B3, D8)

def test_removing_dead_npc_again_is_rejected():
    world = make_world()
    remove_creature(world, "oldrik", "dead", "goal")
    result = remove_creature(world, "oldrik", "dead", "hazard")
    assert isinstance(result, Rejected)
    assert result.reason == "already_dead"
    assert result.report_tag is None


def test_removing_dead_npc_again_keeps_death_record():
    world = make_world(now_s=100)
    remove_creature(world, "oldrik", "dead", "goal", by="hero1", text="первый удар")
    world.clock.now_s = 900
    remove_creature(world, "oldrik", "dead", "hazard", by="trap", text="второй")
    death = world.npcs["oldrik"].death
    assert (death.cause, death.by, death.at_s, death.text) == ("goal", "hero1", 100, "первый удар")
    assert world.npcs["oldrik"].status == "dead"


def test_removing_unknown_creature_is_key_error():
    with pytest.raises(KeyError):
        remove_creature(make_world(), "nobody", "dead", "goal")


# mark_dead (B3, B4, D3)

def make_hero(status="active"):
    sheet = CharacterSheet(
        species_id="human",
        classes=[ClassLevel(class_id="fighter")], level_history=["fighter"] * 1,
        background=BackgroundSpec(
            name="Солдат",
            abilities=["str", "dex", "con"],
            skills=["athletics", "intimidation"],
            tool="dice_set",
            feat="savage_attacker",
        ),
        abilities={"str": 17, "dex": 13, "con": 15, "int": 8, "wis": 10, "cha": 12},
    )
    return HeroState(
        id="h1", ordinal=1, name="Арн", sheet=sheet, location_id="hall",
        creature=CreatureState(hp_current=0, hp_max=12), status=status,
    )


def test_mark_dead_sets_status_and_record():
    hero = make_hero()
    mark_dead(hero, "goal", "g1", 500)
    assert hero.status == "dead"
    assert (hero.death.cause, hero.death.by) == ("goal", "g1")
    assert (hero.death.at_s, hero.death.location_id) == (500, "hall")


def test_mark_dead_returns_hero_died_event():
    events = mark_dead(make_hero(), "hazard", "trap", 500)
    assert [e.type for e in events] == ["hero_died"]
    assert isinstance(events[0], DomainEvent)
    assert events[0].data["id"] == "h1"
    assert events[0].data["cause"] == "hazard"
    assert events[0].data["by"] == "trap"


def test_mark_dead_event_without_killer_has_none_by():
    events = mark_dead(make_hero(), "hazard", None, 500)
    assert events[0].data["by"] is None


def test_mark_dead_on_dead_hero_returns_no_events():
    hero = make_hero()
    mark_dead(hero, "goal", "g1", 500)
    assert mark_dead(hero, "hazard", "trap", 900) == []


def test_mark_dead_on_dead_hero_keeps_death_record():
    hero = make_hero()
    mark_dead(hero, "goal", "g1", 500)
    mark_dead(hero, "hazard", "trap", 900)
    assert isinstance(hero.death, DeathRecord)
    assert (hero.death.cause, hero.death.by, hero.death.at_s) == ("goal", "g1", 500)


def test_mark_dead_ends_concentration_and_its_effects():
    hero = make_hero()
    hero.creature.concentration = Concentration(spell_id="bless", circle=1)
    hero.creature.active_effects = [
        ActiveEffect(
            id="bless", source="h1", kind="modifier",
            params={"target": "attack_roll", "dice": "1d4"}, expires=Expiry(kind="concentration"),
        ),
        ActiveEffect(
            id="sap", source="g1", kind="modifier",
            params={"target": "attack_roll", "mode": "disadvantage"},
            expires=Expiry(kind="start_of_turn", owner="g1"),
        ),
    ]
    mark_dead(hero, "goal", None, 500)
    assert hero.creature.concentration is None
    assert [e.id for e in hero.creature.active_effects] == ["sap"]


# mark_dead с невалидной причиной (аудит 1 п. 2.9)

@pytest.mark.parametrize("cause", [None, "boredom", ""])
def test_mark_dead_with_invalid_cause_is_rejected(cause):
    result = mark_dead(make_hero(), cause, None, 500)
    assert isinstance(result, Rejected)
    assert result.report_tag == "invalid-death"


def test_mark_dead_with_invalid_cause_keeps_hero_alive():
    hero = make_hero()
    mark_dead(hero, "boredom", None, 500)
    assert hero.status == "active"
    assert hero.death is None


def test_mark_dead_with_invalid_cause_keeps_concentration():
    hero = make_hero()
    hero.creature.concentration = Concentration(spell_id="bless", circle=1)
    mark_dead(hero, "boredom", None, 500)
    assert hero.creature.concentration.spell_id == "bless"


# remove_hero (аудит 1 п. 2.9)

def test_remove_hero_gone_sets_status_and_record():
    hero = make_hero()
    result = remove_hero(hero, "gone", "chance", 700, by="portal", text="исчез")
    assert not isinstance(result, Rejected)
    assert hero.status == "gone"
    assert isinstance(hero.death, DeathRecord)
    assert (hero.death.cause, hero.death.by, hero.death.at_s) == ("chance", "portal", 700)
    assert (hero.death.location_id, hero.death.text) == ("hall", "исчез")


def test_remove_hero_dead_sets_status_dead():
    hero = make_hero()
    remove_hero(hero, "dead", "goal", 700)
    assert hero.status == "dead"
    assert hero.death.cause == "goal"


def test_remove_hero_returns_creature_removed_event():
    events = remove_hero(make_hero(), "gone", "chance", 700)
    assert events[0].type == "creature_removed"
    assert events[0].data["id"] == "h1"
    assert events[0].data["status"] == "gone"
    assert events[0].data["cause"] == "chance"


def test_remove_hero_dead_adds_hero_died_event():
    events = remove_hero(make_hero(), "dead", "goal", 700, by="g1")
    assert [e.type for e in events] == ["creature_removed", "hero_died"]
    assert events[1].data == {"id": "h1", "cause": "goal", "by": "g1"}


def test_remove_hero_gone_has_no_hero_died_event():
    events = remove_hero(make_hero(), "gone", "chance", 700)
    assert [e.type for e in events] == ["creature_removed"]


@pytest.mark.parametrize("cause", [None, "boredom"])
def test_remove_hero_without_valid_cause_is_rejected(cause):
    hero = make_hero()
    result = remove_hero(hero, "gone", cause, 700)
    assert isinstance(result, Rejected)
    assert result.report_tag == "invalid-death"
    assert hero.status == "active"
    assert hero.death is None


def test_remove_hero_unknown_status_is_value_error():
    with pytest.raises(ValueError):
        remove_hero(make_hero(), "alive", "goal", 700)


def test_remove_dead_hero_again_is_rejected_and_keeps_record():
    hero = make_hero()
    mark_dead(hero, "goal", "g1", 500)
    result = remove_hero(hero, "gone", "chance", 900)
    assert isinstance(result, Rejected)
    assert result.reason == "already_dead"
    assert result.report_tag is None
    assert hero.status == "dead"
    assert (hero.death.cause, hero.death.at_s) == ("goal", 500)


def test_remove_hero_ends_concentration():
    hero = make_hero()
    hero.creature.concentration = Concentration(spell_id="bless", circle=1)
    remove_hero(hero, "gone", "chance", 700)
    assert hero.creature.concentration is None


def test_hero_status_gone_is_valid():
    hero = make_hero(status="gone")
    assert hero.status == "gone"
