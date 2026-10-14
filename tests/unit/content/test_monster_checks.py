# Партия К7д, п. 2.2: loader.check_monster_actions (content/monster_checks.py) при загрузке реестра.
#   Действие монстра: кубики damage_dice / advantage_damage_dice / extra_damage_dice -- настоящие
#   кубики, damage_type / extra_damage_type -- из DAMAGE_TYPE_WORDS;
#   on_hit.condition -- существующее
#   состояние, on_hit.dice -- кубики, on_hit.damage_type -- известный тип. death_burst: dice --
#   кубики, damage_type -- известный тип. Нарушение -- ContentError с названием поля и значением.
import pytest

from ai_dm.content.loader import ContentError, load_registry

MONSTER = """\
id: odd_orc
name: Странный орк
ac: 10
hp: 5
cr: 1/8
abilities: {{str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10}}
{extra}
"""
ACTION = """\
actions:
- name: Укус
  kind: melee
  attack_bonus: 3
  damage_dice: {dice}
  damage_type: {kind}
{more}"""


def load(tmp_path, extra):
    path = tmp_path / "monsters" / "odd_orc.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(MONSTER.format(extra=extra), encoding="utf-8")
    return load_registry([tmp_path]).get("monster", "odd_orc")


def action(dice="1d6", kind="piercing", more=""):
    return ACTION.format(dice=dice, kind=kind, more=more)


def test_valid_extra_and_rider_load(tmp_path):
    more = (
        "  extra_damage_dice: 2d8\n  extra_damage_type: poison\n  on_hit:\n"
        "    condition: paralyzed\n    save: con\n    dc: 10\n    dice: 1d4\n"
        "    damage_type: acid\n"
    )
    monster = load(tmp_path, action(more=more))
    assert monster.actions[0].on_hit.condition == "paralyzed"


def test_valid_death_burst_loads(tmp_path):
    monster = load(tmp_path, "death_burst: {dc: 11, dice: 2d6, damage_type: fire}")
    assert (monster.death_burst.save, monster.death_burst.dc) == ("dex", 11)


@pytest.mark.parametrize("dice", ["abc", "d", "1d"])
def test_bad_damage_dice_is_rejected(tmp_path, dice):
    with pytest.raises(ContentError) as exc:
        load(tmp_path, action(dice=dice))
    assert dice in str(exc.value)


def test_bad_advantage_dice_is_rejected(tmp_path):
    with pytest.raises(ContentError) as exc:
        load(tmp_path, action(more="  advantage_damage_dice: xx\n"))
    assert "xx" in str(exc.value)


def test_bad_extra_dice_is_rejected(tmp_path):
    more = "  extra_damage_dice: yy\n  extra_damage_type: poison\n"
    with pytest.raises(ContentError) as exc:
        load(tmp_path, action(more=more))
    assert "yy" in str(exc.value)


def test_unknown_damage_type_is_rejected(tmp_path):
    with pytest.raises(ContentError) as exc:
        load(tmp_path, action(kind="frost"))
    assert "frost" in str(exc.value)


def test_unknown_extra_damage_type_is_rejected(tmp_path):
    more = "  extra_damage_dice: 1d4\n  extra_damage_type: frost\n"
    with pytest.raises(ContentError) as exc:
        load(tmp_path, action(more=more))
    assert "frost" in str(exc.value)


def test_unknown_rider_condition_is_rejected(tmp_path):
    with pytest.raises(ContentError) as exc:
        load(tmp_path, action(more="  on_hit: {condition: sleepy}\n"))
    assert "sleepy" in str(exc.value) and "on_hit" in str(exc.value)


def test_bad_rider_dice_is_rejected(tmp_path):
    more = "  on_hit: {condition: prone, dice: zz, damage_type: acid}\n"
    with pytest.raises(ContentError) as exc:
        load(tmp_path, action(more=more))
    assert "zz" in str(exc.value)


def test_unknown_rider_damage_type_is_rejected(tmp_path):
    more = "  on_hit: {condition: prone, dice: 1d4, damage_type: frost}\n"
    with pytest.raises(ContentError) as exc:
        load(tmp_path, action(more=more))
    assert "frost" in str(exc.value)


def test_bad_burst_dice_is_rejected(tmp_path):
    with pytest.raises(ContentError) as exc:
        load(tmp_path, "death_burst: {dc: 11, dice: qq, damage_type: fire}")
    assert "death_burst" in str(exc.value) and "qq" in str(exc.value)


def test_unknown_burst_damage_type_is_rejected(tmp_path):
    with pytest.raises(ContentError) as exc:
        load(tmp_path, "death_burst: {dc: 11, dice: 1d4, damage_type: frost}")
    assert "frost" in str(exc.value)


def test_action_without_attack_fields_loads(tmp_path):
    monster = load(tmp_path, "actions:\n- name: Взгляд\n  description: Смотрит.")
    assert monster.actions[0].damage_dice is None
