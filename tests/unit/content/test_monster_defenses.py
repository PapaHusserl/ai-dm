# Партия К7к, п. 1.1: защиты монстра (docs/plan-k7k.md, В2а, В5а).
#   Monster.damage_immunities / damage_resistances / damage_vulnerabilities: list[str] = [] --
#   типы урона из DAMAGE_TYPE_WORDS; неизвестный тип ("frost") -- ContentError загрузчика,
#   повтор в списке -- ValidationError;
#   Monster.condition_immunities: list[str] = [] -- id состояний, загрузчик реестра проверяет их
#   по реестру condition (неизвестное -> ContentError). Данные трёх монстров SRD без защит (К7д).
import pytest
from pydantic import ValidationError

from ai_dm.content.loader import ContentError, load_registry
from ai_dm.content.models.monsters import Monster
from ai_dm.rules.roll_pipeline import DAMAGE_TYPE_WORDS

BASE = {
    "id": "odd_orc", "name": "Странный орк", "ac": 10, "hp": 5, "cr": "1/8",
    "abilities": {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
}
LISTS = ["damage_immunities", "damage_resistances", "damage_vulnerabilities"]

MONSTER = """\
id: odd_orc
name: Странный орк
ac: 10
hp: 5
cr: 1/8
abilities: {{str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10}}
{extra}
"""


def monster(**fields):
    return Monster.model_validate({**BASE, **fields})


def write_monster(tmp_path, extra):
    path = tmp_path / "monsters" / "odd_orc.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(MONSTER.format(extra=extra), encoding="utf-8")


@pytest.mark.parametrize("field", LISTS + ["condition_immunities"])
def test_lists_are_empty_by_default(field):
    assert getattr(monster(), field) == []


@pytest.mark.parametrize("field", LISTS)
def test_known_damage_types_are_accepted(field):
    assert getattr(monster(**{field: ["fire", "slashing"]}), field) == ["fire", "slashing"]


@pytest.mark.parametrize("field", LISTS)
def test_repeated_damage_type_is_rejected(field):
    with pytest.raises(ValidationError):
        monster(**{field: ["fire", "fire"]})


@pytest.mark.parametrize("damage_type", sorted(DAMAGE_TYPE_WORDS))
def test_every_word_type_is_a_valid_damage_type(damage_type):
    assert monster(damage_immunities=[damage_type]).damage_immunities == [damage_type]


def test_same_type_in_different_lists_is_allowed():
    one = monster(damage_resistances=["fire"], damage_vulnerabilities=["fire"])
    assert one.damage_resistances == one.damage_vulnerabilities == ["fire"]


def test_condition_immunities_are_a_plain_list():
    assert monster(condition_immunities=["prone", "restrained"]).condition_immunities == [
        "prone", "restrained",
    ]


def test_first_three_srd_monsters_have_no_protections(registry):
    for one in [registry.get("monster", i) for i in ("goblin_warrior", "goblin_boss", "guard")]:
        assert one.damage_immunities == [] and one.damage_resistances == []
        assert one.damage_vulnerabilities == [] and one.condition_immunities == []


def test_known_condition_immunity_loads(tmp_path):
    write_monster(tmp_path, "condition_immunities: [prone, poisoned]")
    loaded = load_registry([tmp_path]).get("monster", "odd_orc")
    assert loaded.condition_immunities == ["prone", "poisoned"]


def test_unknown_condition_immunity_raises_content_error(tmp_path):
    write_monster(tmp_path, "condition_immunities: [sleepy]")
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "sleepy" in str(exc.value)
    assert "condition_immunities" in str(exc.value)


def test_damage_types_load_from_yaml(tmp_path):
    write_monster(tmp_path, "damage_immunities: [poison]\ndamage_vulnerabilities: [radiant]")
    loaded = load_registry([tmp_path]).get("monster", "odd_orc")
    assert (loaded.damage_immunities, loaded.damage_vulnerabilities) == (["poison"], ["radiant"])


@pytest.mark.parametrize("field", LISTS)
@pytest.mark.parametrize("value", ["[frost]", "[fire, frost]"])
def test_unknown_damage_type_in_yaml_raises_content_error(tmp_path, field, value):
    write_monster(tmp_path, f"{field}: {value}")
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert field in str(exc.value)
    assert "frost" in str(exc.value)
