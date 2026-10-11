# К0а (docs/K0-PLAN.md, A1): схема v9 -- CharacterSheet.classes / level_history, адаптер чтения
# (class_id, level, subclass_id, primary, class_level, prepared_of, known_of), Concentration,
# TempForm, Equipment, GrantedSpell, PendingLevel, HeroState.companions / attuned / pending_level.
import pytest
from pydantic import ValidationError

from ai_dm.state.combat import Participant
from ai_dm.state.creature import Concentration, CreatureState, Equipment, TempForm
from ai_dm.state.hero import (
    BackgroundSpec,
    CharacterSheet,
    ClassLevel,
    Companion,
    GrantedSpell,
    HeroState,
    LevelChoices,
    PendingLevel,
)
from ai_dm.state.world import NPC

ABILITIES = {"str": 10, "dex": 14, "con": 12, "int": 10, "wis": 13, "cha": 8}


def background():
    return BackgroundSpec(
        name="Солдат", abilities=["str", "dex", "con"], skills=["athletics"], tool="dice_set",
        feat="savage_attacker",
    )


def make_sheet(**fields):
    base = {
        "species_id": "human",
        "classes": [ClassLevel(class_id="ranger", level=3, subclass_id="beast_master")],
        "level_history": ["ranger"] * 3,
        "background": background(),
        "abilities": ABILITIES,
    }
    base.update(fields)
    return CharacterSheet(**base)


def two_class_sheet():
    return make_sheet(
        classes=[ClassLevel(class_id="ranger", level=3), ClassLevel(class_id="wizard", level=2)],
        level_history=["ranger", "ranger", "ranger", "wizard", "wizard"],
    )


def make_hero(**fields):
    return HeroState(
        id="h1", ordinal=1, name="Грей", sheet=make_sheet(),
        creature=CreatureState(hp_current=20, hp_max=20), **fields,
    )


# адаптер чтения

def test_class_id_is_the_first_class():
    assert make_sheet().class_id == "ranger"


def test_level_of_one_class():
    assert make_sheet().level == 3


def test_subclass_id_is_the_first_class_subclass():
    assert make_sheet().subclass_id == "beast_master"


def test_subclass_id_is_none_without_subclass():
    sheet = make_sheet(classes=[ClassLevel(class_id="ranger", level=3)])
    assert sheet.subclass_id is None


def test_primary_is_the_first_class_entry():
    sheet = two_class_sheet()
    assert sheet.primary is sheet.classes[0]


def test_level_is_the_sum_for_two_classes():
    assert two_class_sheet().level == 5


def test_class_id_is_the_first_one_for_two_classes():
    assert two_class_sheet().class_id == "ranger"


def test_class_level_of_each_class():
    sheet = two_class_sheet()
    assert (sheet.class_level("ranger"), sheet.class_level("wizard")) == (3, 2)


def test_class_level_of_missing_class_is_zero():
    assert make_sheet().class_level("wizard") == 0


def test_class_level_default_is_one():
    assert ClassLevel(class_id="fighter").level == 1


def test_class_level_below_one_is_refused():
    with pytest.raises(ValidationError):
        ClassLevel(class_id="fighter", level=0)


# prepared_of / known_of

def test_prepared_of_returns_the_list_of_the_primary_class():
    sheet = make_sheet(spells_prepared={"ranger": ["hunters_mark"]})
    assert sheet.prepared_of() == ["hunters_mark"]


def test_prepared_of_other_class_by_id():
    sheet = two_class_sheet()
    sheet.spells_prepared = {"ranger": ["a"], "wizard": ["b"]}
    assert sheet.prepared_of("wizard") == ["b"]


def test_prepared_of_creates_the_key():
    sheet = make_sheet()
    assert sheet.prepared_of() == []
    assert sheet.spells_prepared == {"ranger": []}


def test_prepared_of_is_a_live_list():
    sheet = make_sheet()
    sheet.prepared_of().append("cure_wounds")
    assert sheet.spells_prepared == {"ranger": ["cure_wounds"]}


def test_prepared_of_without_arguments_equals_primary_class_key():
    sheet = make_sheet()
    assert sheet.prepared_of() is sheet.prepared_of("ranger")


def test_known_of_returns_the_list_of_the_primary_class():
    sheet = make_sheet(spells_known={"ranger": ["fog_cloud"]})
    assert sheet.known_of() == ["fog_cloud"]


def test_known_of_is_a_live_list():
    sheet = make_sheet()
    sheet.known_of().append("fog_cloud")
    assert sheet.spells_known == {"ranger": ["fog_cloud"]}


def test_known_of_other_class_by_id():
    sheet = two_class_sheet()
    sheet.known_of("wizard").append("light")
    assert sheet.spells_known == {"wizard": ["light"]}


def test_prepared_and_known_do_not_mix():
    sheet = make_sheet()
    sheet.prepared_of().append("a")
    assert sheet.known_of() == []


# валидатор

def test_empty_classes_is_refused():
    with pytest.raises(ValidationError):
        make_sheet(classes=[], level_history=[])


def test_repeated_class_id_is_refused():
    with pytest.raises(ValidationError):
        make_sheet(
            classes=[ClassLevel(class_id="ranger", level=1), ClassLevel(class_id="ranger",
                level=1)],
            level_history=["ranger", "ranger"],
        )


def test_level_history_shorter_than_level_is_refused():
    with pytest.raises(ValidationError):
        make_sheet(level_history=["ranger", "ranger"])


def test_level_history_longer_than_level_is_refused():
    with pytest.raises(ValidationError):
        make_sheet(level_history=["ranger"] * 4)


def test_level_history_is_required():
    with pytest.raises(ValidationError):
        CharacterSheet(
            species_id="human", classes=[ClassLevel(class_id="ranger")],
            background=background(), abilities=ABILITIES,
        )


@pytest.mark.parametrize(
    "old", [{"class_id": "ranger"}, {"level": 3}, {"subclass_id": "beast_master"},
            {"feature_options": {"hunters_prey": "colossus_slayer"}}],
)
def test_old_scalar_fields_are_refused_by_the_constructor(old):
    with pytest.raises(ValidationError):
        make_sheet(**old)


def test_old_hero_companion_field_is_refused():
    with pytest.raises(ValidationError):
        make_hero(companion=Companion(kind="волк", name="Акела"))


def test_dump_has_no_scalar_class_fields():
    dumped = make_sheet().model_dump()
    assert not {"class_id", "level", "subclass_id"} & set(dumped)


def test_dump_has_classes_and_level_history():
    dumped = make_sheet().model_dump()
    assert dumped["classes"] == [{"class_id": "ranger", "level": 3, "subclass_id": "beast_master"}]
    assert dumped["level_history"] == ["ranger", "ranger", "ranger"]


# новые модели v9

def test_concentration_round_trip():
    value = Concentration(spell_id="hunters_mark", circle=1)
    assert Concentration.model_validate_json(value.model_dump_json()) == value


def test_concentration_until_s_default_is_none():
    assert Concentration(spell_id="x", circle=0).until_s is None


def test_concentration_negative_circle_is_refused():
    with pytest.raises(ValidationError):
        Concentration(spell_id="x", circle=-1)


def test_creature_concentration_is_a_model_not_a_string():
    with pytest.raises(ValidationError):
        CreatureState(hp_current=1, hp_max=1, concentration="hunters_mark")


def test_creature_defaults_have_no_concentration_and_no_temp_form():
    creature = CreatureState(hp_current=1, hp_max=1)
    assert (creature.concentration, creature.temp_form) == (None, None)


def test_temp_form_defaults():
    form = TempForm(monster_id="wolf", source="wild_shape")
    assert (form.until_s, form.temp_hp_granted) == (None, 0)


def test_temp_form_round_trip():
    form = TempForm(monster_id="wolf", source="wild_shape", until_s=600, temp_hp_granted=11)
    assert TempForm.model_validate_json(form.model_dump_json()) == form


def test_equipment_defaults_are_empty():
    equipment = Equipment()
    assert (equipment.armor, equipment.shield, equipment.weapons) == (None, None, [])


def test_equipment_round_trip():
    equipment = Equipment(armor="chain_mail", shield="shield", weapons=["longsword"])
    assert Equipment.model_validate_json(equipment.model_dump_json()) == equipment


def test_equipment_weapons_lists_are_not_shared():
    first, second = Equipment(), Equipment()
    first.weapons.append("dagger")
    assert second.weapons == []


def test_granted_spell_minimum_fields():
    granted = GrantedSpell(spell_id="detect_magic", source="fey_touched")
    assert (granted.class_id, granted.ability, granted.pool) == (None, None, None)


def test_granted_spell_round_trip():
    granted = GrantedSpell(
        spell_id="misty_step", source="fey_touched", class_id="wizard", ability="int", pool="fey",
    )
    assert GrantedSpell.model_validate_json(granted.model_dump_json()) == granted


def test_sheet_spells_always_prepared_default_is_empty():
    assert make_sheet().spells_always_prepared == []


def test_sheet_keeps_granted_spells():
    granted = GrantedSpell(spell_id="detect_magic", source="fey_touched")
    assert make_sheet(spells_always_prepared=[granted]).spells_always_prepared == [granted]


def test_pending_level_round_trip():
    pending = PendingLevel(class_id="ranger", hp_gain=7, draft=LevelChoices(level=4,
        asi={"dex": 2}))
    assert PendingLevel.model_validate_json(pending.model_dump_json()) == pending


def test_pending_level_hp_gain_below_one_is_refused():
    with pytest.raises(ValidationError):
        PendingLevel(class_id="ranger", hp_gain=0, draft=LevelChoices(level=4))


def test_level_choices_feature_choices_are_lists():
    choices = LevelChoices(level=4, feature_choices={"hunters_prey": ["colossus_slayer"]})
    assert choices.feature_choices == {"hunters_prey": ["colossus_slayer"]}


def test_level_choices_refuse_old_feature_options():
    with pytest.raises(ValidationError):
        LevelChoices(level=4, feature_options={"hunters_prey": "colossus_slayer"})


def test_level_choices_one_to_list_still_works():
    assert LevelChoices(level=2, expertise="survival").expertise == ["survival"]


def test_sheet_feature_choices_round_trip():
    sheet = make_sheet(feature_choices={"hunters_prey": ["colossus_slayer"]})
    assert CharacterSheet.model_validate_json(sheet.model_dump_json()) == sheet


# HeroState

def test_hero_companions_default_is_empty_list():
    assert make_hero().companions == []


def test_hero_companions_lists_are_not_shared():
    first, second = make_hero(), make_hero()
    first.companions.append(Companion(kind="волк", name="Акела"))
    assert second.companions == []


def test_hero_keeps_two_companions():
    pets = [Companion(kind="волк", name="Акела"), Companion(kind="ворон", name="Мунин")]
    assert [c.name for c in make_hero(companions=pets).companions] == ["Акела", "Мунин"]


def test_hero_attuned_default_is_empty():
    assert make_hero().attuned == []


def test_hero_pending_level_default_is_none():
    assert make_hero().pending_level is None


def test_hero_with_pending_level_round_trip():
    pending = PendingLevel(class_id="ranger", hp_gain=5, draft=LevelChoices(level=4))
    hero = make_hero(pending_level=pending)
    assert HeroState.model_validate_json(hero.model_dump_json()).pending_level == pending


def test_hero_with_two_classes_round_trip():
    hero = make_hero()
    hero.sheet = two_class_sheet()
    again = HeroState.model_validate_json(hero.model_dump_json())
    assert again.sheet.level == 5
    assert again.sheet.class_level("wizard") == 2


# equipment у NPC и участника боя

def test_npc_equipment_default_is_none():
    assert NPC(id="n1", name="Олдрик", means=["нож"], motive="долг").equipment is None


def test_npc_equipment_round_trip():
    npc = NPC(id="n1", name="Олдрик", means=["нож"], motive="долг",
        equipment=Equipment(weapons=["dagger"]))
    assert NPC.model_validate_json(npc.model_dump_json()).equipment == Equipment(weapons=["dagger"])


def test_participant_equipment_default_is_none():
    assert Participant(ref="h1", side="heroes", group_id="g").equipment is None
