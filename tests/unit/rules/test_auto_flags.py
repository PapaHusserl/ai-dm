# Ожидаемый API: ai_dm.rules.auto_flags (шаг 14, ТЗ 4.01 «Флаги ставит движок автоматически»)
#   apply_events(world: WorldState, events: list[DomainEvent]) -> None
#       по событиям ставит в world.flags значение True (идемпотентно, события других видов
#       игнорируются, порядок событий не важен, флаги не снимаются):
#         npc_died      data id           -> "npc_dead:<id>"
#         hero_died     data id           -> "hero_dead:<id>"   (id героя)
#         location_visited  data id       -> "visited:<id>"     (id локации; НОВОЕ событие
#                                            партии 4, шлёт будущая перемещалка героя)
#         combat_ended  data id           -> "combat_ended:<id>" (id боя / столкновения;
#                                            НОВОЕ событие, шлёт шаг 21 «конец боя»)
#         item_gained   data hero, item   -> "item_gained:<item>" (id предмета; НОВОЕ событие,
#                                            шлёт инвентарь; hero -- id героя, в имя флага
#                                            не входит)
#       Остальные поля data (cause, by и т.п.) на флаги не влияют.
#   Условие flag по этим именам вычисляется обычным evaluate(): {flag: "npc_dead:<id>"}.
#   Состояние героя (hero.status) apply_events не трогает -- условие hero_dead считается по
#   hero.status, а флаг hero_dead:<id> нужен для историй и паков.
from ai_dm.core.events import DomainEvent
from ai_dm.core.rng import Rng
from ai_dm.rules.auto_flags import apply_events
from ai_dm.rules.mortality_guard import remove_creature
from ai_dm.rules.triggers_eval import Truth, evaluate
from ai_dm.state.creature import CreatureState
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState
from ai_dm.state.triggers import Flag
from ai_dm.state.world import NPC, WorldState


def npc_died():
    return DomainEvent(type="npc_died", data={"id": "mentor_aldric", "cause": "goal"})


def make_world():
    world = WorldState(world_id="w1", rng=Rng(1).state)
    world.npcs["mentor_aldric"] = NPC(id="mentor_aldric", name="Олдрик", means=["магия крови"])
    return world


def make_hero():
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
        id="h1", ordinal=1, name="Арн", sheet=sheet,
        creature=CreatureState(hp_current=12, hp_max=12),
    )


def test_npc_died_sets_npc_dead_flag():
    world = make_world()
    apply_events(world, [npc_died()])
    assert world.flags["npc_dead:mentor_aldric"] is True


def test_hero_died_sets_hero_dead_flag_with_hero_id():
    world = make_world()
    apply_events(world, [DomainEvent(type="hero_died", data={"id": "h1", "cause": "goal"})])
    assert world.flags["hero_dead:h1"] is True


def test_location_visited_sets_visited_flag():
    world = make_world()
    apply_events(world, [DomainEvent(type="location_visited", data={"id": "crypt"})])
    assert world.flags["visited:crypt"] is True


def test_combat_ended_sets_combat_ended_flag():
    world = make_world()
    apply_events(world, [DomainEvent(type="combat_ended", data={"id": "goblins3"})])
    assert world.flags["combat_ended:goblins3"] is True


def test_item_gained_sets_item_flag_without_hero_in_name():
    world = make_world()
    event = DomainEvent(type="item_gained", data={"hero": "h1", "item": "blood_grail"})
    apply_events(world, [event])
    assert world.flags["item_gained:blood_grail"] is True
    assert "item_gained:h1" not in world.flags


def test_several_events_set_all_flags():
    world = make_world()
    apply_events(
        world,
        [
            DomainEvent(type="location_visited", data={"id": "crypt"}),
            npc_died(),
            DomainEvent(type="combat_ended", data={"id": "goblins3"}),
        ],
    )
    assert sorted(world.flags) == [
        "combat_ended:goblins3", "npc_dead:mentor_aldric", "visited:crypt",
    ]


def test_unknown_event_type_changes_nothing():
    world = make_world()
    apply_events(world, [DomainEvent(type="creature_removed", data={"id": "mentor_aldric"})])
    assert world.flags == {}


def test_empty_event_list_changes_nothing():
    world = make_world()
    apply_events(world, [])
    assert world.flags == {}


def test_apply_twice_is_idempotent():
    world = make_world()
    events = [npc_died()]
    apply_events(world, events)
    apply_events(world, events)
    assert world.flags == {"npc_dead:mentor_aldric": True}


def test_existing_flags_are_kept():
    world = make_world()
    world.flags["met_aldric"] = True
    apply_events(world, [DomainEvent(type="location_visited", data={"id": "crypt"})])
    assert world.flags["met_aldric"] is True


def test_flag_condition_true_after_npc_died_event():
    world = make_world()
    apply_events(world, [npc_died()])
    condition = Flag(name="npc_dead:mentor_aldric")
    assert evaluate(condition, world, make_hero()).truth == Truth.TRUE


def test_flag_condition_false_before_event():
    condition = Flag(name="npc_dead:mentor_aldric")
    assert evaluate(condition, make_world(), make_hero()).truth == Truth.FALSE


def test_events_from_remove_creature_set_npc_dead_flag():
    # стык со стражем 4.1: события remove_creature -> авто-флаг
    world = make_world()
    events = remove_creature(world, "mentor_aldric", "dead", "goal")
    apply_events(world, events)
    assert world.flags["npc_dead:mentor_aldric"] is True


def test_gone_npc_does_not_get_npc_dead_flag():
    world = make_world()
    events = remove_creature(world, "mentor_aldric", "gone", "chance")
    apply_events(world, events)
    assert "npc_dead:mentor_aldric" not in world.flags


def test_apply_events_does_not_touch_npc_status():
    world = make_world()
    apply_events(world, [npc_died()])
    assert world.npcs["mentor_aldric"].status == "alive"
