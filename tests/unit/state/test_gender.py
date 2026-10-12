# К0-фикс-б (K0-FIX-PLAN, шаг 7, BACKLOG 39): пол и местоимения NPC и героя -- тип Gender (Q9),
# поля NPC / HeroState / CharacterChoices с дефолтами "не задан" (старые сейвы без миграции).
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

from hero_kit import base_choices  # noqa: E402

from ai_dm.rules.builder import CharacterChoices  # noqa: E402
from ai_dm.state.creature import CreatureState  # noqa: E402
from ai_dm.state.gender import GENDER_WORDS, Gender  # noqa: E402
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState  # noqa: E402
from ai_dm.state.world import NPC  # noqa: E402


def make_hero(**fields):
    sheet = CharacterSheet(
        species_id="human", classes=[ClassLevel(class_id="fighter")], level_history=["fighter"],
        background=BackgroundSpec(
            name="Солдат", abilities=["str", "dex", "con"], skills=["athletics"],
            tool="dice_set", feat="savage_attacker",
        ),
        abilities={"str": 15, "dex": 13, "con": 14, "int": 8, "wis": 10, "cha": 12},
    )
    return HeroState(
        id="h1", ordinal=1, name="Грей", sheet=sheet,
        creature=CreatureState(hp_current=10, hp_max=10), **fields,
    )


def make_choices(**fields):
    return CharacterChoices.model_validate({**base_choices().model_dump(), **fields})


def test_gender_words_are_russian_for_every_gender():
    assert GENDER_WORDS == {"male": "мужской", "female": "женский", "other": "другой"}


def test_gender_literal_values():
    from typing import get_args

    assert set(get_args(Gender)) == {"male", "female", "other"}


# значения по умолчанию

def test_npc_has_no_gender_by_default():
    npc = NPC(id="a", name="А", means=["м"])
    assert npc.gender is None
    assert npc.pronouns == ""


def test_hero_has_no_gender_by_default():
    hero = make_hero()
    assert hero.gender is None
    assert hero.pronouns == ""


def test_choices_have_no_gender_by_default():
    choices = make_choices()
    assert choices.gender is None
    assert choices.pronouns == ""


# значения

def test_npc_keeps_gender_and_pronouns():
    npc = NPC(id="a", name="А", means=["м"], gender="female", pronouns="она, госпожа")
    assert npc.gender == "female"
    assert npc.pronouns == "она, госпожа"


def test_hero_keeps_gender_and_pronouns():
    hero = make_hero(gender="other", pronouns="они")
    assert (hero.gender, hero.pronouns) == ("other", "они")


def test_choices_keep_gender_and_pronouns():
    choices = make_choices(gender="male", pronouns="он")
    assert (choices.gender, choices.pronouns) == ("male", "он")


@pytest.mark.parametrize("value", ["x", "none", "", "мужской", "Male"])
def test_npc_rejects_unknown_gender(value):
    with pytest.raises(ValidationError):
        NPC(id="a", name="А", means=["м"], gender=value)


@pytest.mark.parametrize("value", ["x", "none", "", "female "])
def test_hero_rejects_unknown_gender(value):
    with pytest.raises(ValidationError):
        make_hero(gender=value)


@pytest.mark.parametrize("value", ["x", "none", ""])
def test_choices_reject_unknown_gender(value):
    with pytest.raises(ValidationError):
        make_choices(gender=value)


# старые данные без полей

def test_old_npc_dump_without_fields_loads():
    data = NPC(id="a", name="А", means=["м"]).model_dump()
    del data["gender"]
    del data["pronouns"]
    npc = NPC.model_validate(data)
    assert npc.gender is None
    assert npc.pronouns == ""


def test_old_hero_dump_without_fields_loads():
    data = make_hero().model_dump()
    del data["gender"]
    del data["pronouns"]
    hero = HeroState.model_validate(data)
    assert hero.gender is None
    assert hero.pronouns == ""


def test_old_choices_dump_without_fields_loads():
    data = make_choices().model_dump()
    del data["gender"]
    del data["pronouns"]
    assert CharacterChoices.model_validate(data).gender is None


def test_gender_survives_json_roundtrip():
    npc = NPC(id="a", name="А", means=["м"], gender="female", pronouns="она")
    assert NPC.model_validate_json(npc.model_dump_json()) == npc
