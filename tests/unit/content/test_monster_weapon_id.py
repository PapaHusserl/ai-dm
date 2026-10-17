# Партия «Отбор оружия» (docs/plan-combat-disarm.md, п. 2): MonsterAction.weapon_id -- id оружия из
# srd/data/weapons (контент, не сейв); None -- естественная атака (Укус, Когти), её не отобрать.
# Размечены: guard «Копьё» -> spear; goblin_warrior и goblin_boss «Скимитар» -> scimitar,
# «Короткий лук» -> shortbow. Валидатор реестра: weapon_id обязан существовать среди weapon.
import pytest
from pydantic import ValidationError

from ai_dm.content.loader import ContentError, load_registry
from ai_dm.content.models.monsters import MonsterAction

MONSTER = """\
id: odd_orc
name: Странный орк
ac: 10
hp: 5
cr: 1/8
abilities: {{str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10}}
actions:
- name: Топор
  kind: melee
  attack_bonus: 3
  damage_dice: 1d6
  damage_type: slashing
  weapon_id: {weapon_id}
"""


def write_monster(tmp_path, weapon_id):
    path = tmp_path / "monsters" / "odd_orc.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(MONSTER.format(weapon_id=weapon_id), encoding="utf-8")


def action_of(registry, monster_id, name):
    return [a for a in registry.get("monster", monster_id).actions if a.name == name][0]


def test_weapon_id_is_none_by_default():
    assert MonsterAction(name="Укус").weapon_id is None


def test_weapon_id_is_accepted():
    assert MonsterAction(name="Копьё", weapon_id="spear").weapon_id == "spear"


def test_weapon_id_must_be_a_string():
    with pytest.raises(ValidationError):
        MonsterAction(name="Копьё", weapon_id=["spear"])


@pytest.mark.parametrize(
    "monster_id, name, weapon_id",
    [
        ("guard", "Копьё", "spear"),
        ("goblin_warrior", "Скимитар", "scimitar"),
        ("goblin_warrior", "Короткий лук", "shortbow"),
        ("goblin_boss", "Скимитар", "scimitar"),
        ("goblin_boss", "Короткий лук", "shortbow"),
    ],
)
def test_srd_monster_action_is_marked_with_its_weapon(registry, monster_id, name, weapon_id):
    assert action_of(registry, monster_id, name).weapon_id == weapon_id


def test_every_marked_weapon_exists_in_the_registry(registry):
    for monster in registry.all("monster"):
        for action in monster.actions:
            if action.weapon_id is not None:
                assert registry.has("weapon", action.weapon_id)


def test_humanoid_monsters_have_a_marked_weapon_action(registry):
    # R1 плана: гуманоид без weapon_id остался бы неотбираемым
    for monster in registry.all("monster"):
        if monster.creature_type == "humanoid" and monster.actions:
            assert [a for a in monster.actions if a.weapon_id is not None], monster.id


def test_unknown_weapon_id_raises_content_error(tmp_path):
    write_monster(tmp_path, "no_such_weapon")
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "no_such_weapon" in str(exc.value)


def test_known_weapon_id_loads(tmp_path):
    write_monster(tmp_path, "spear")
    registry = load_registry([tmp_path])
    assert registry.get("monster", "odd_orc").actions[0].weapon_id == "spear"
