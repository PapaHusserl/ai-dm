# Ожидаемый API: ai_dm.state.* (только данные, без логики; extra="forbid" везде)
#
# ai_dm.state.creature
#   DeathSaves(successes=0, failures=0)
#   ResourcePool(current: int, max: int)
#   Expiry(kind: "rounds"|"end_of_turn"|"start_of_turn"|"seconds"|"concentration", value=0,
#          owner: str | None = None)
#   ActiveEffect(id, source, kind, params: dict[str, int|str|bool]={}, expires: Expiry | None=None)
#   AppliedCondition(id, source: str | None = None, expires: Expiry | None = None)
#   CreatureState(hp_current: int, hp_max: int, hp_temp=0, conditions: list[AppliedCondition]=[],
#                 exhaustion=0, active_effects: list[ActiveEffect]=[],
#                 death_saves=DeathSaves(), resources: dict[str, ResourcePool]={},
#                 concentration: str | None = None)
# ai_dm.state.death
#   DeathRecord(cause: "goal"|"hazard"|"chance"|"old_age", by: str | None=None, at_s: int,
#               location_id: str | None=None, text="")
# ai_dm.state.hero
#   BackgroundSpec(name: str, abilities: list[str], skills: list[str], tool: str, feat: str,
#                  equipment: list[str]=[], gold_cp=0)     -- длины списков НЕ проверяются
#                  на уровне модели (их проверяет rules.builder)
#   CharacterSheet(species_id, class_id, background: BackgroundSpec, abilities: dict[str, int],
#                  subclass_id=None, level=1, skill_proficiencies: list[str]=[],
#                  tool_proficiencies: list[str]=[], feats: list[str]=[],
#                  weapon_masteries: list[str]=[], spells_known: list[str]=[],
#                  spells_prepared: list[str]=[], xp=0)
#   InventoryEntry(item_id: str, qty: int = 1)
#   Equipped(armor, shield, main_hand, off_hand: str | None)  -- все None по умолчанию
#   HeroState(id, ordinal: int, name, sheet, creature, status="active" (active|dead|retired|
#             in_afterlife|ascended), fate=None, death: DeathRecord | None = None,
#             inventory: list[InventoryEntry]=[], equipped=Equipped(), money_cp=0, motive="",
#             means: list[str]=[], opportunity: list=[],
#             favor: dict[str, int]={} (бог -> -10..10, вне диапазона = ошибка),
#             scars: list[str]=[], heroic_inspiration=False, location_id=None,
#             afterlife=None, legacy_links: list[str]=[])
# ai_dm.state.world
#   Tone(mood="", violence="", horror="", romance="", language="", hard_limits=[], soft_limits=[])
#   EventHazard(save: Ability, dc_category: DcCategory)
#   GlobalEvent(id, type, regions=[], affects=[], mortality_multiplier: int = 1 (ge=0, не float),
#               hazard: EventHazard | None=None, started_s: int | None=None,
#               ends_at_s: int | None=None, ends_when: Condition | None=None, cause=None)
#   NPC(id, name, named=False, key=False, status="alive" (alive|dead|gone|changed),
#       death: DeathRecord | None = None, motive="",
#       means: list[str] (длина 1..3 -> 0 и 4 = ошибка), opportunity: list[Trigger]=[],
#       attitude: int = 0 (-100..100 включительно), known_to_player: list[str]=[],
#       secrets: list[Secret]=[], combat: dict | None = None, creature=None, location_id=None,
#       species_id=None, birth_s: int | None = None, favor: dict[str, int]={} (-10..10),
#       relations_text="", origin="pack" (pack|ai|engine))
#   Faction(id, name, motive="", means=[], opportunity=[], members: list[str]=[], regions=[])
#   God(id, name, domains=[], role="", motive="", pleased_by=[], angered_by=[], rivals=[],
#       means=[], opportunity=[], realm="", status="alive", origin="pack" (pack|ascended))
#   Connection(to: str, distance_m: int (ge=0))
#   Location(id, name, parent_id=None, description="", tags=[], connections: list[Connection]=[],
#            visited=False, origin="pack")
#   WorldState(world_id: str, rng: RngState, campaign_id=None, campaign_version=None,
#              clock: GameClock = GameClock(), npcs: dict[str, NPC]={}, factions: dict={},
#              pantheon: dict[str, God]={}, locations: dict={}, flags: dict[str, bool|int|str]={},
#              events: list[GlobalEvent]=[], tone: Tone=Tone(),
#              settings: dict[str, int|str|bool]={})
#     ключ словаря npcs/factions/pantheon/locations должен совпадать с id объекта -> иначе ошибка
import pytest
from pydantic import ValidationError

from ai_dm.core.rng import Rng
from ai_dm.state.creature import (
    ActiveEffect,
    AppliedCondition,
    CreatureState,
    Expiry,
)
from ai_dm.state.death import DeathRecord
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, Equipped, HeroState
from ai_dm.state.world import (
    NPC,
    Connection,
    Faction,
    GlobalEvent,
    God,
    Location,
    WorldState,
)


def make_world():
    return WorldState(world_id="w1", rng=Rng(1).state)


def make_npc(**kwargs):
    return NPC(id="aldric", name="Олдрик", means=["магия крови"], **kwargs)


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


# WorldState

def test_empty_world_has_empty_npcs():
    assert make_world().npcs == {}


def test_empty_world_has_empty_factions():
    assert make_world().factions == {}


def test_empty_world_has_empty_pantheon_not_none():
    assert make_world().pantheon == {}


def test_empty_world_has_empty_locations():
    assert make_world().locations == {}


def test_empty_world_has_empty_flags_not_none():
    assert make_world().flags == {}


def test_empty_world_has_empty_events_not_none():
    assert make_world().events == []


def test_empty_world_clock_starts_at_zero():
    assert make_world().clock.now_s == 0


def test_world_keeps_rng_state():
    assert make_world().rng == Rng(1).state


def test_world_requires_world_id():
    with pytest.raises(ValidationError):
        WorldState(rng=Rng(1).state)


def test_world_rejects_extra_field():
    with pytest.raises(ValidationError):
        WorldState(world_id="w1", rng=Rng(1).state, bogus=1)


def test_world_collections_are_not_shared_between_instances():
    first = make_world()
    first.flags["met"] = True
    assert make_world().flags == {}


def test_world_stores_npc_flag_and_event():
    world = make_world()
    world.npcs["aldric"] = make_npc()
    world.flags["met_aldric"] = True
    world.events.append(GlobalEvent(id="grey_plague", type="plague"))
    assert world.npcs["aldric"].name == "Олдрик"
    assert world.flags == {"met_aldric": True}
    assert world.events[0].id == "grey_plague"


# NPC

def test_npc_defaults():
    npc = make_npc()
    assert npc.status == "alive"
    assert npc.attitude == 0
    assert npc.opportunity == []
    assert npc.secrets == []
    assert npc.known_to_player == []
    assert npc.origin == "pack"


def test_npc_with_short_trigger_equals_npc_with_full_trigger():
    short = {
        "id": "steal_grail",
        "if": {"hero_has": "blood_grail"},
        "then": "выкрадет",
        "once": True,
    }
    full = {
        "id": "steal_grail",
        "if": {"type": "hero_has", "item": "blood_grail"},
        "then": "выкрадет",
        "once": True,
    }
    npc_short = NPC.model_validate(
        {"id": "aldric", "name": "Олдрик", "means": ["магия"], "opportunity": [short]}
    )
    npc_full = NPC.model_validate(
        {"id": "aldric", "name": "Олдрик", "means": ["магия"], "opportunity": [full]}
    )
    assert npc_short == npc_full


def test_npc_unknown_condition_kind_raises_validation_error():
    data = {
        "id": "aldric",
        "name": "Олдрик",
        "means": ["магия"],
        "opportunity": [{"id": "t", "if": {"banana": 1}, "then": "x"}],
    }
    with pytest.raises(ValidationError) as exc:
        NPC.model_validate(data)
    assert "banana" in str(exc.value)


def test_npc_unknown_condition_kind_error_path_contains_opportunity():
    data = {
        "id": "aldric",
        "name": "Олдрик",
        "means": ["магия"],
        "opportunity": [{"id": "t", "if": {"banana": 1}, "then": "x"}],
    }
    with pytest.raises(ValidationError) as exc:
        NPC.model_validate(data)
    locs = [item["loc"] for item in exc.value.errors()]
    assert any("opportunity" in loc for loc in locs)


def test_npc_attitude_100_is_ok():
    assert make_npc(attitude=100).attitude == 100


def test_npc_attitude_minus_100_is_ok():
    assert make_npc(attitude=-100).attitude == -100


def test_npc_attitude_above_100_raises_validation_error():
    with pytest.raises(ValidationError):
        make_npc(attitude=101)


def test_npc_attitude_below_minus_100_raises_validation_error():
    with pytest.raises(ValidationError):
        make_npc(attitude=-101)


def test_npc_with_four_means_raises_validation_error():
    with pytest.raises(ValidationError):
        NPC(id="aldric", name="Олдрик", means=["a", "b", "c", "d"])


def test_npc_with_three_means_is_ok():
    assert len(NPC(id="aldric", name="Олдрик", means=["a", "b", "c"]).means) == 3


def test_npc_invalid_status_raises_validation_error():
    with pytest.raises(ValidationError):
        make_npc(status="sleeping")


def test_npc_extra_field_raises_validation_error():
    with pytest.raises(ValidationError):
        make_npc(bogus=1)


def test_npc_secret_with_short_reveal_condition():
    npc = NPC.model_validate(
        {
            "id": "aldric",
            "name": "Олдрик",
            "means": ["магия"],
            "secrets": [{"id": "s1", "text": "сестра-вампир", "reveal_if": {"flag": "found"}}],
        }
    )
    assert npc.secrets[0].reveal_if.type == "flag"


# герой и существо

def test_creature_defaults_are_empty_collections():
    creature = CreatureState(hp_current=5, hp_max=10)
    assert creature.conditions == []
    assert creature.active_effects == []
    assert creature.resources == {}
    assert creature.hp_temp == 0
    assert creature.exhaustion == 0
    assert creature.concentration is None


def test_creature_death_saves_start_at_zero():
    creature = CreatureState(hp_current=5, hp_max=10)
    assert creature.death_saves.successes == 0
    assert creature.death_saves.failures == 0


def test_hero_defaults():
    hero = make_hero()
    assert hero.status == "active"
    assert hero.inventory == []
    assert hero.money_cp == 0
    assert hero.afterlife is None
    assert hero.legacy_links == []
    assert hero.scars == []
    assert hero.heroic_inspiration is False


def test_hero_equipped_slots_are_empty_by_default():
    equipped = make_hero().equipped
    assert equipped == Equipped()
    assert equipped.armor is None
    assert equipped.shield is None
    assert equipped.main_hand is None


def test_hero_invalid_status_raises_validation_error():
    data = make_hero().model_dump()
    data["status"] = "sleeping"
    with pytest.raises(ValidationError):
        HeroState.model_validate(data)


def test_hero_extra_field_raises_validation_error():
    data = make_hero().model_dump()
    data["bogus"] = 1
    with pytest.raises(ValidationError):
        HeroState.model_validate(data)


def test_sheet_defaults_to_level_1_without_subclass():
    sheet = make_hero().sheet
    assert sheet.level == 1
    assert sheet.subclass_id is None
    assert sheet.xp == 0
    assert sheet.feats == []


def test_background_spec_does_not_check_list_lengths():
    spec = BackgroundSpec(
        name="Кривая", abilities=["str"], skills=["a", "b", "c"], tool="x", feat="alert"
    )
    assert len(spec.skills) == 3


# благосклонность по богам

def test_hero_favor_is_empty_dict_by_default():
    assert make_hero().favor == {}


def test_hero_favor_by_god_is_kept():
    data = make_hero().model_dump()
    data["favor"] = {"morrah": 3, "ilvar": -2}
    assert HeroState.model_validate(data).favor == {"morrah": 3, "ilvar": -2}


@pytest.mark.parametrize("value", [-10, 0, 10])
def test_hero_favor_inside_range_is_ok(value):
    data = make_hero().model_dump()
    data["favor"] = {"morrah": value}
    assert HeroState.model_validate(data).favor["morrah"] == value


@pytest.mark.parametrize("value", [-11, 11, 100])
def test_hero_favor_outside_range_raises_validation_error(value):
    data = make_hero().model_dump()
    data["favor"] = {"morrah": value}
    with pytest.raises(ValidationError):
        HeroState.model_validate(data)


def test_hero_favor_as_plain_int_raises_validation_error():
    data = make_hero().model_dump()
    data["favor"] = 3
    with pytest.raises(ValidationError):
        HeroState.model_validate(data)


def test_npc_favor_is_empty_dict_by_default():
    assert make_npc().favor == {}


def test_npc_favor_by_god_is_kept():
    assert make_npc(favor={"morrah": 5}).favor == {"morrah": 5}


@pytest.mark.parametrize("value", [-10, 10])
def test_npc_favor_at_range_edge_is_ok(value):
    assert make_npc(favor={"morrah": value}).favor["morrah"] == value


@pytest.mark.parametrize("value", [-11, 11])
def test_npc_favor_outside_range_raises_validation_error(value):
    with pytest.raises(ValidationError):
        make_npc(favor={"morrah": value})


def test_npc_favor_as_plain_int_raises_validation_error():
    with pytest.raises(ValidationError):
        make_npc(favor=3)


# NPC: means, birth_s, death

def test_npc_with_empty_means_raises_validation_error():
    with pytest.raises(ValidationError):
        NPC(id="aldric", name="Олдрик", means=[])


def test_npc_with_one_mean_is_ok():
    assert len(NPC(id="aldric", name="Олдрик", means=["a"]).means) == 1


def test_npc_without_means_raises_validation_error():
    with pytest.raises(ValidationError):
        NPC(id="aldric", name="Олдрик")


def test_npc_birth_s_is_none_by_default():
    assert make_npc().birth_s is None


def test_npc_birth_s_is_int_seconds():
    assert make_npc(birth_s=-3600).birth_s == -3600


def test_npc_birth_date_field_is_gone():
    with pytest.raises(ValidationError):
        make_npc(birth_date="1200-01-01")


def test_npc_death_is_none_by_default():
    assert make_npc().death is None


def test_npc_death_record_from_dict():
    npc = make_npc(death={"cause": "hazard", "at_s": 500, "by": "grey_plague"})
    assert isinstance(npc.death, DeathRecord)
    assert npc.death.by == "grey_plague"


def test_npc_death_with_unknown_cause_raises_validation_error():
    with pytest.raises(ValidationError):
        make_npc(death={"cause": "boredom", "at_s": 1})


# DeathRecord

def test_death_record_defaults():
    record = DeathRecord(cause="goal", at_s=100)
    assert record.by is None
    assert record.location_id is None
    assert record.text == ""


@pytest.mark.parametrize("cause", ["goal", "hazard", "chance", "old_age"])
def test_death_record_accepts_known_cause(cause):
    assert DeathRecord(cause=cause, at_s=0).cause == cause


def test_death_record_unknown_cause_raises_validation_error():
    with pytest.raises(ValidationError):
        DeathRecord(cause="boredom", at_s=0)


def test_death_record_requires_at_s():
    with pytest.raises(ValidationError):
        DeathRecord(cause="goal")


def test_death_record_rejects_extra_field():
    with pytest.raises(ValidationError):
        DeathRecord(cause="goal", at_s=0, bogus=1)


def test_hero_death_is_none_by_default():
    assert make_hero().death is None


def test_hero_death_record_from_dict():
    data = make_hero().model_dump()
    data["death"] = {"cause": "chance", "at_s": 42, "location_id": "port_vale", "text": "упал"}
    hero = HeroState.model_validate(data)
    assert hero.death.cause == "chance"
    assert hero.death.location_id == "port_vale"


def test_hero_death_as_free_dict_raises_validation_error():
    data = make_hero().model_dump()
    data["death"] = {"how": "badly"}
    with pytest.raises(ValidationError):
        HeroState.model_validate(data)


# GlobalEvent

def test_global_event_defaults():
    event = GlobalEvent(id="grey_plague", type="plague")
    assert event.mortality_multiplier == 1
    assert event.hazard is None
    assert event.started_s is None
    assert event.ends_at_s is None
    assert event.ends_when is None


def test_global_event_mortality_multiplier_is_int():
    event = GlobalEvent(id="grey_plague", type="plague", mortality_multiplier=3)
    assert event.mortality_multiplier == 3


def test_global_event_float_multiplier_raises_validation_error():
    with pytest.raises(ValidationError):
        GlobalEvent(id="grey_plague", type="plague", mortality_multiplier=1.5)


def test_global_event_negative_multiplier_raises_validation_error():
    with pytest.raises(ValidationError):
        GlobalEvent(id="grey_plague", type="plague", mortality_multiplier=-1)


def test_global_event_zero_multiplier_is_ok():
    assert GlobalEvent(id="e", type="calm", mortality_multiplier=0).mortality_multiplier == 0


def test_global_event_hazard_from_dict():
    event = GlobalEvent(
        id="grey_plague", type="plague", hazard={"save": "con", "dc_category": "hard"}
    )
    assert event.hazard.save == "con"
    assert event.hazard.dc_category == "hard"


def test_global_event_hazard_unknown_ability_raises_validation_error():
    with pytest.raises(ValidationError):
        GlobalEvent(id="e", type="t", hazard={"save": "luck", "dc_category": "hard"})


def test_global_event_hazard_unknown_dc_category_raises_validation_error():
    with pytest.raises(ValidationError):
        GlobalEvent(id="e", type="t", hazard={"save": "con", "dc_category": "brutal"})


def test_global_event_hazard_requires_both_fields():
    with pytest.raises(ValidationError):
        GlobalEvent(id="e", type="t", hazard={"save": "con"})


def test_global_event_times_are_seconds():
    event = GlobalEvent(id="e", type="t", started_s=100, ends_at_s=5000)
    assert (event.started_s, event.ends_at_s) == (100, 5000)


def test_global_event_started_text_field_is_gone():
    with pytest.raises(ValidationError):
        GlobalEvent(id="e", type="t", started="1200-01-01")


def test_global_event_started_s_as_text_raises_validation_error():
    with pytest.raises(ValidationError):
        GlobalEvent(id="e", type="t", started_s="вчера")


def test_global_event_ends_when_accepts_short_condition():
    event = GlobalEvent.model_validate(
        {"id": "e", "type": "t", "ends_when": {"flag": "cure_found"}}
    )
    assert event.ends_when.type == "flag"


def test_global_event_ends_when_unknown_condition_raises_validation_error():
    with pytest.raises(ValidationError) as exc:
        GlobalEvent.model_validate({"id": "e", "type": "t", "ends_when": {"banana": 1}})
    assert "banana" in str(exc.value)


# Connection / Location

def test_connection_keeps_target_and_distance():
    connection = Connection(to="tavern", distance_m=1500)
    assert (connection.to, connection.distance_m) == ("tavern", 1500)


def test_connection_zero_distance_is_ok():
    assert Connection(to="tavern", distance_m=0).distance_m == 0


def test_connection_negative_distance_raises_validation_error():
    with pytest.raises(ValidationError):
        Connection(to="tavern", distance_m=-1)


def test_connection_requires_distance():
    with pytest.raises(ValidationError):
        Connection(to="tavern")


def test_connection_in_kilometers_is_not_accepted():
    with pytest.raises(ValidationError):
        Connection(to="tavern", distance_km=2)


def test_location_connections_are_built_from_dicts():
    location = Location.model_validate(
        {"id": "port_vale", "name": "Порт", "connections": [{"to": "tavern", "distance_m": 300}]}
    )
    assert isinstance(location.connections[0], Connection)
    assert location.connections[0].distance_m == 300


def test_location_connection_without_distance_raises_validation_error():
    with pytest.raises(ValidationError):
        Location.model_validate(
            {"id": "port_vale", "name": "Порт", "connections": [{"to": "tavern"}]}
        )


# ключ словаря мира == id объекта

def test_world_accepts_npc_under_its_own_id():
    world = WorldState(world_id="w1", rng=Rng(1).state, npcs={"aldric": make_npc()})
    assert "aldric" in world.npcs


def test_world_npc_under_wrong_key_raises_validation_error():
    with pytest.raises(ValidationError):
        WorldState(world_id="w1", rng=Rng(1).state, npcs={"other": make_npc()})


def test_world_faction_under_wrong_key_raises_validation_error():
    faction = Faction(id="guild", name="Гильдия")
    with pytest.raises(ValidationError):
        WorldState(world_id="w1", rng=Rng(1).state, factions={"other": faction})


def test_world_faction_under_own_id_is_ok():
    faction = Faction(id="guild", name="Гильдия")
    world = WorldState(world_id="w1", rng=Rng(1).state, factions={"guild": faction})
    assert world.factions["guild"].name == "Гильдия"


def test_world_god_under_wrong_key_raises_validation_error():
    god = God(id="morrah", name="Моррах")
    with pytest.raises(ValidationError):
        WorldState(world_id="w1", rng=Rng(1).state, pantheon={"other": god})


def test_world_god_under_own_id_is_ok():
    god = God(id="morrah", name="Моррах")
    world = WorldState(world_id="w1", rng=Rng(1).state, pantheon={"morrah": god})
    assert world.pantheon["morrah"].name == "Моррах"


def test_world_location_under_wrong_key_raises_validation_error():
    location = Location(id="port_vale", name="Порт")
    with pytest.raises(ValidationError):
        WorldState(world_id="w1", rng=Rng(1).state, locations={"other": location})


def test_world_location_under_own_id_is_ok():
    location = Location(id="port_vale", name="Порт")
    world = WorldState(world_id="w1", rng=Rng(1).state, locations={"port_vale": location})
    assert world.locations["port_vale"].name == "Порт"


def test_world_key_check_works_for_json_input_too():
    data = make_world().model_dump(mode="json")
    data["npcs"] = {"other": make_npc().model_dump(mode="json")}
    with pytest.raises(ValidationError):
        WorldState.model_validate(data)


# settings

def test_world_settings_accept_int_str_bool():
    world = WorldState(
        world_id="w1", rng=Rng(1).state, settings={"difficulty": 2, "mode": "hard", "perma": True}
    )
    assert world.settings == {"difficulty": 2, "mode": "hard", "perma": True}


def test_world_settings_reject_nested_value():
    with pytest.raises(ValidationError):
        WorldState(world_id="w1", rng=Rng(1).state, settings={"x": {"y": 1}})


def test_world_settings_reject_list_value():
    with pytest.raises(ValidationError):
        WorldState(world_id="w1", rng=Rng(1).state, settings={"x": [1]})


# ActiveEffect / Expiry / AppliedCondition

def test_expiry_defaults():
    expiry = Expiry(kind="rounds")
    assert expiry.value == 0
    assert expiry.owner is None


@pytest.mark.parametrize(
    "kind", ["rounds", "end_of_turn", "start_of_turn", "seconds", "concentration"]
)
def test_expiry_accepts_known_kind(kind):
    assert Expiry(kind=kind, value=3, owner="h1").kind == kind


def test_expiry_unknown_kind_raises_validation_error():
    with pytest.raises(ValidationError):
        Expiry(kind="forever")


def test_active_effect_defaults():
    effect = ActiveEffect(id="e1", source="bless", kind="modifier")
    assert effect.params == {}
    assert effect.expires is None


def test_active_effect_keeps_params_and_expiry():
    effect = ActiveEffect(
        id="e1", source="bless", kind="modifier",
        params={"dice": "1d4", "stacks": 2, "on": True},
        expires={"kind": "concentration", "owner": "h1"},
    )
    assert effect.params == {"dice": "1d4", "stacks": 2, "on": True}
    assert effect.expires.kind == "concentration"
    assert effect.expires.owner == "h1"


def test_active_effect_rejects_nested_params():
    with pytest.raises(ValidationError):
        ActiveEffect(id="e1", source="bless", kind="modifier", params={"x": [1]})


def test_active_effect_requires_source_and_kind():
    with pytest.raises(ValidationError):
        ActiveEffect(id="e1")


def test_active_effect_rejects_extra_field():
    with pytest.raises(ValidationError):
        ActiveEffect(id="e1", source="s", kind="k", bogus=1)


def test_applied_condition_defaults():
    condition = AppliedCondition(id="poisoned")
    assert condition.source is None
    assert condition.expires is None


def test_applied_condition_keeps_source_and_expiry():
    condition = AppliedCondition(
        id="frightened", source="goblin_boss", expires={"kind": "end_of_turn", "owner": "h1"}
    )
    assert condition.source == "goblin_boss"
    assert condition.expires.kind == "end_of_turn"


def test_creature_conditions_are_applied_conditions():
    creature = CreatureState(hp_current=5, hp_max=10, conditions=[{"id": "prone"}])
    assert isinstance(creature.conditions[0], AppliedCondition)
    assert creature.conditions[0].id == "prone"


def test_creature_conditions_as_plain_strings_raise_validation_error():
    with pytest.raises(ValidationError):
        CreatureState(hp_current=5, hp_max=10, conditions=["prone"])


def test_creature_active_effects_are_typed():
    creature = CreatureState(
        hp_current=5, hp_max=10,
        active_effects=[{"id": "e1", "source": "bless", "kind": "modifier"}],
    )
    assert isinstance(creature.active_effects[0], ActiveEffect)


def test_creature_active_effect_as_free_dict_raises_validation_error():
    with pytest.raises(ValidationError):
        CreatureState(hp_current=5, hp_max=10, active_effects=[{"whatever": 1}])


# прочие поля героя

def test_equipped_off_hand_is_empty_by_default():
    assert make_hero().equipped.off_hand is None


def test_equipped_off_hand_can_be_set():
    assert Equipped(off_hand="shield").off_hand == "shield"


def test_sheet_spells_prepared_is_empty_by_default():
    assert make_hero().sheet.spells_prepared == {}


def test_sheet_keeps_known_and_prepared_spells_separately():
    data = make_hero().model_dump()
    data["sheet"]["spells_known"] = {"fighter": ["fire_bolt", "magic_missile"]}
    data["sheet"]["spells_prepared"] = {"fighter": ["magic_missile"]}
    sheet = HeroState.model_validate(data).sheet
    assert sheet.known_of() == ["fire_bolt", "magic_missile"]
    assert sheet.prepared_of() == ["magic_missile"]
