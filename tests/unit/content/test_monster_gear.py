# Партия К7к, п. 2.1-2.2: доспех и щит монстра (docs/plan-k7k.md, В6 а+в).
#   Monster.armor / Monster.shield: str | None = None -- что надето по SRD (трофеи с тел);
#   КД монстра -- число ac, по снаряжению не пересчитывается (пересчёт -- К7х).
#   Загрузчик: armor -- id из armor с category != "shield"; shield -- id из armor с category ==
#   "shield"; иначе ContentError. srd/data/armor/chain_shirt: medium, КД 13, dex_cap 2, 5000 cp.
#   Данные: goblin_warrior -- leather_armor + shield; goblin_boss и guard -- chain_shirt + shield.
import pytest

from ai_dm.content.loader import ContentError, load_registry
from ai_dm.content.models.monsters import Monster
from ai_dm.rules.derived import ability_modifier

MONSTER = """\
id: odd_orc
name: Странный орк
ac: 10
hp: 5
cr: 1/8
abilities: {{str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10}}
{extra}
"""


def write_monster(tmp_path, extra):
    path = tmp_path / "monsters" / "odd_orc.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(MONSTER.format(extra=extra), encoding="utf-8")


def test_armor_and_shield_are_none_by_default():
    one = Monster.model_validate({
        "id": "x", "name": "X", "ac": 10, "hp": 5, "cr": "1/8",
        "abilities": {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
    })
    assert (one.armor, one.shield) == (None, None)


def test_chain_shirt_is_in_the_registry(registry):
    assert registry.has("armor", "chain_shirt")


def test_chain_shirt_stats(registry):
    shirt = registry.get("armor", "chain_shirt")
    assert (shirt.name, shirt.category, shirt.ac) == ("Кольчужная рубаха", "medium", 13)
    assert (shirt.dex_cap, shirt.cost_cp, shirt.strength_min) == (2, 5000, 0)


def test_chain_shirt_has_source_and_license(registry):
    shirt = registry.get("armor", "chain_shirt")
    assert (shirt.source, shirt.license) == ("srd-5.2", "CC-BY-4.0")


@pytest.mark.parametrize(
    "monster_id, armor, shield",
    [
        ("goblin_warrior", "leather_armor", "shield"),
        ("goblin_boss", "chain_shirt", "shield"),
        ("guard", "chain_shirt", "shield"),
    ],
)
def test_srd_monster_gear(registry, monster_id, armor, shield):
    one = registry.get("monster", monster_id)
    assert (one.armor, one.shield) == (armor, shield)


@pytest.mark.parametrize("monster_id", ["goblin_warrior", "goblin_boss", "guard"])
def test_ac_matches_the_gear(registry, monster_id):
    # документирует согласие КД и снаряжения; движок КД по снаряжению не пересчитывает
    one = registry.get("monster", monster_id)
    armor = registry.get("armor", one.armor)
    shield = registry.get("armor", one.shield)
    dex = ability_modifier(one.abilities["dex"])
    cap = armor.dex_cap if armor.dex_cap is not None else 99
    assert one.ac == armor.ac + min(dex, cap) + shield.ac


def test_every_monster_armor_is_a_body_armor_and_shield_a_shield(registry):
    for one in registry.all("monster"):
        if one.armor is not None:
            assert registry.get("armor", one.armor).category != "shield"
        if one.shield is not None:
            assert registry.get("armor", one.shield).category == "shield"


def test_known_gear_loads(tmp_path):
    write_monster(tmp_path, "armor: studded_leather\nshield: shield")
    loaded = load_registry([tmp_path]).get("monster", "odd_orc")
    assert (loaded.armor, loaded.shield) == ("studded_leather", "shield")


def test_armor_may_be_given_without_shield(tmp_path):
    write_monster(tmp_path, "armor: chain_mail")
    loaded = load_registry([tmp_path]).get("monster", "odd_orc")
    assert (loaded.armor, loaded.shield) == ("chain_mail", None)


def test_shield_in_armor_slot_raises_content_error(tmp_path):
    write_monster(tmp_path, "armor: shield")
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "armor" in str(exc.value)


def test_body_armor_in_shield_slot_raises_content_error(tmp_path):
    write_monster(tmp_path, "shield: leather_armor")
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "shield" in str(exc.value)


def test_unknown_armor_raises_content_error(tmp_path):
    write_monster(tmp_path, "armor: nope")
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "nope" in str(exc.value)


def test_unknown_shield_raises_content_error(tmp_path):
    write_monster(tmp_path, "shield: nope")
    with pytest.raises(ContentError) as exc:
        load_registry([tmp_path])
    assert "nope" in str(exc.value)


def test_weapon_id_in_armor_slot_raises_content_error(tmp_path):
    write_monster(tmp_path, "armor: scimitar")
    with pytest.raises(ContentError):
        load_registry([tmp_path])
