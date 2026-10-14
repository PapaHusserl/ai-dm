# Партия К7д, п. 1: 27 монстров SRD 5.2 с ПО 0-5 (docs/K7D-PLAN.md, В4, В8, В9, В10).
#   Данные -- srd/data/monsters/*.yaml (source srd-5.2, license CC-BY-4.0, русские имена);
#   КД -- число из статблока; armor / shield стоят только у монстров с названным снаряжением, и
#   тогда
#   gear_ac(armor, shield, Лов) == ac; traits ссылаются на features реестра; множитель XP и клад --
#   по ПО из таблиц; иммунитеты, сопротивления и уязвимости -- по SRD 5.2 (без "nonmagical").
#   Тег disarmer -- у wight и goblin_boss (Q6а), у прочих нет.
import pytest

from ai_dm.core.dice import parse_dice
from ai_dm.core.rng import Rng
from ai_dm.rules.derived import ability_modifier, gear_ac
from ai_dm.rules.loot import individual_treasure
from ai_dm.rules.roll_pipeline import DAMAGE_TYPE_WORDS

IDS = [
    "skeleton", "zombie", "shadow", "ghoul", "specter", "ghast", "ogre_zombie", "wight",
    "steam_mephit", "dust_mephit", "magmin", "gargoyle", "fire_elemental", "earth_elemental",
    "homunculus", "animated_flying_sword", "animated_armor",
    "hawk", "giant_rat", "mastiff", "wolf", "swarm_of_rats", "boar", "panther", "black_bear",
    "dire_wolf", "giant_spider",
]
TYPES = {
    "undead": ["skeleton", "zombie", "shadow", "ghoul", "specter", "ghast", "ogre_zombie", "wight"],
    "elemental": ["steam_mephit", "dust_mephit", "magmin", "gargoyle", "fire_elemental",
                  "earth_elemental"],
    "construct": ["homunculus", "animated_flying_sword", "animated_armor"],
    "beast": ["hawk", "giant_rat", "mastiff", "wolf", "swarm_of_rats", "boar", "panther",
              "black_bear", "dire_wolf", "giant_spider"],
}
FLYERS = ["steam_mephit", "dust_mephit", "gargoyle", "homunculus", "animated_flying_sword",
          "hawk", "specter"]
CHECKED = {
    # id: (ac, hp, cr) -- сверено с официальным SRD 5.2
    "skeleton": (14, 13, "1/4"), "zombie": (8, 15, "1/4"), "ghoul": (12, 22, "1"),
    "wight": (14, 82, "3"), "wolf": (12, 11, "1/4"), "giant_spider": (14, 26, "1"),
    "fire_elemental": (13, 93, "5"), "animated_armor": (18, 33, "1"),
}


def get(registry, monster_id):
    return registry.get("monster", monster_id)


def test_the_list_has_27_ids():
    assert len(IDS) == len(set(IDS)) == 27


def test_every_group_is_covered():
    assert sorted(i for ids in TYPES.values() for i in ids) == sorted(IDS)


@pytest.mark.parametrize("monster_id", IDS)
def test_monster_is_loaded(registry, monster_id):
    assert registry.has("monster", monster_id)


@pytest.mark.parametrize("monster_id", IDS)
def test_source_and_license(registry, monster_id):
    monster = get(registry, monster_id)
    assert (monster.source, monster.license) == ("srd-5.2", "CC-BY-4.0")


@pytest.mark.parametrize("monster_id", IDS)
def test_name_is_russian(registry, monster_id):
    name = get(registry, monster_id).name
    assert any("а" <= c.lower() <= "я" or c.lower() == "ё" for c in name)


@pytest.mark.parametrize("kind, ids", sorted(TYPES.items()))
def test_creature_type(registry, kind, ids):
    assert [get(registry, i).creature_type for i in ids] == [kind] * len(ids)


@pytest.mark.parametrize("monster_id", IDS)
def test_cr_is_between_zero_and_five(registry, monster_id):
    cr = get(registry, monster_id).cr
    assert cr in ["0", "1/8", "1/4", "1/2", "1", "2", "3", "4", "5"]


@pytest.mark.parametrize("monster_id", IDS)
def test_cr_has_xp_and_treasure(registry, monster_id):
    cr = get(registry, monster_id).cr
    assert registry.get("table", "cr_xp").rows[cr] >= 0
    assert individual_treasure(cr, Rng(1), registry) > 0


@pytest.mark.parametrize("monster_id, stats", sorted(CHECKED.items()))
def test_checked_stats(registry, monster_id, stats):
    monster = get(registry, monster_id)
    assert (monster.ac, monster.hp, monster.cr) == stats


@pytest.mark.parametrize("monster_id", IDS)
def test_stats_are_positive(registry, monster_id):
    monster = get(registry, monster_id)
    assert monster.hp > 0 and monster.ac >= 5


@pytest.mark.parametrize("monster_id", IDS)
def test_gear_matches_the_stat_block_ac(registry, monster_id):
    # В9в: armor / shield заданы только вместе с совпадающим КД
    monster = get(registry, monster_id)
    if monster.armor is None and monster.shield is None:
        return
    dex = ability_modifier(monster.abilities["dex"])
    assert gear_ac(registry, monster.armor, monster.shield, dex) == monster.ac


@pytest.mark.parametrize("monster_id", IDS)
def test_traits_exist_in_the_registry(registry, monster_id):
    for trait in get(registry, monster_id).traits:
        assert registry.has("feature", trait)


@pytest.mark.parametrize("monster_id", IDS)
def test_attacks_are_parsable(registry, monster_id):
    for action in get(registry, monster_id).actions:
        if action.attack_bonus is None:
            continue
        assert action.damage_dice is not None
        parse_dice(action.damage_dice)
        assert action.damage_type in DAMAGE_TYPE_WORDS
        if action.extra_damage_dice is not None:
            parse_dice(action.extra_damage_dice)
            assert action.extra_damage_type in DAMAGE_TYPE_WORDS
        if action.kind == "ranged":
            assert action.range_normal_ft
        else:
            assert action.reach_ft


@pytest.mark.parametrize("monster_id", IDS)
def test_multiattack_steps_name_real_actions(registry, monster_id):
    monster = get(registry, monster_id)
    names = [a.name for a in monster.actions]
    assert all(step.action in names and step.count >= 1 for step in monster.multiattack)


@pytest.mark.parametrize("monster_id", IDS)
def test_immunity_types_are_known(registry, monster_id):
    monster = get(registry, monster_id)
    for kind in (monster.damage_immunities, monster.damage_resistances,
                 monster.damage_vulnerabilities):
        assert set(kind) <= set(DAMAGE_TYPE_WORDS)
    for condition in monster.condition_immunities:
        assert registry.has("condition", condition)


# защиты по SRD 5.2

def test_skeleton_defenses(registry):
    monster = get(registry, "skeleton")
    assert monster.damage_vulnerabilities == ["bludgeoning"]
    assert "poison" in monster.damage_immunities
    assert {"exhaustion", "poisoned"} <= set(monster.condition_immunities)


def test_shadow_defenses(registry):
    monster = get(registry, "shadow")
    assert monster.damage_vulnerabilities == ["radiant"]
    assert {"necrotic", "poison"} <= set(monster.damage_immunities)
    assert {"acid", "cold", "fire", "lightning", "thunder"} <= set(monster.damage_resistances)
    assert {"frightened", "grappled", "paralyzed", "prone"} <= set(monster.condition_immunities)


def test_fire_elemental_defenses(registry):
    monster = get(registry, "fire_elemental")
    assert {"fire", "poison"} <= set(monster.damage_immunities)
    assert {"grappled", "paralyzed", "petrified", "prone", "restrained"} <= set(
        monster.condition_immunities
    )


def test_animated_armor_defenses(registry):
    monster = get(registry, "animated_armor")
    assert {"poison", "psychic"} <= set(monster.damage_immunities)
    assert {"charmed", "deafened", "frightened", "paralyzed", "poisoned"} <= set(
        monster.condition_immunities
    )


def test_zombie_is_immune_to_poison(registry):
    assert "poison" in get(registry, "zombie").damage_immunities


# черты

@pytest.mark.parametrize("monster_id", ["wolf", "dire_wolf"])
def test_pack_tactics_holders(registry, monster_id):
    assert "pack_tactics" in get(registry, monster_id).traits


@pytest.mark.parametrize("monster_id", ["zombie", "ogre_zombie"])
def test_undead_fortitude_holders(registry, monster_id):
    assert "undead_fortitude" in get(registry, monster_id).traits


@pytest.mark.parametrize("monster_id", ["skeleton", "ghoul", "hawk", "fire_elemental"])
def test_no_mechanical_traits_for_the_others(registry, monster_id):
    traits = get(registry, monster_id).traits
    assert "pack_tactics" not in traits and "undead_fortitude" not in traits


def test_giant_spider_bite_has_poison_extra_damage(registry):
    actions = get(registry, "giant_spider").actions
    assert "poison" in [a.extra_damage_type for a in actions]


@pytest.mark.parametrize("monster_id", FLYERS)
def test_flyers_have_fly_speed(registry, monster_id):
    assert get(registry, monster_id).fly_ft > 0


@pytest.mark.parametrize("monster_id", ["wolf", "zombie", "skeleton", "black_bear"])
def test_walkers_have_no_fly_speed(registry, monster_id):
    assert get(registry, monster_id).fly_ft == 0


@pytest.mark.parametrize("monster_id", ["wight", "goblin_boss"])
def test_disarmer_holders(registry, monster_id):
    assert "disarmer" in get(registry, monster_id).tags


@pytest.mark.parametrize("monster_id", [i for i in IDS if i != "wight"])
def test_no_other_disarmers(registry, monster_id):
    assert "disarmer" not in get(registry, monster_id).tags


# природная броня и снаряжение

@pytest.mark.parametrize("monster_id", ["goblin_warrior", "goblin_boss", "guard"])
def test_old_monsters_keep_their_gear(registry, monster_id):
    monster = get(registry, monster_id)
    dex = ability_modifier(monster.abilities["dex"])
    assert gear_ac(registry, monster.armor, monster.shield, dex) == monster.ac


# эффекты при попадании и предсмертный взрыв

@pytest.mark.parametrize("monster_id", ["ghoul", "ghast"])
def test_ghoul_claws_paralyze(registry, monster_id):
    riders = [a.on_hit for a in get(registry, monster_id).actions if a.on_hit is not None]
    assert [(r.condition, r.save, r.dc, r.duration) for r in riders] == [
        ("paralyzed", "con", 10, "target_turn"),
    ]
    assert "undead" in riders[0].exempt


def test_ghoul_does_not_paralyze_elves(registry):
    rider = [a.on_hit for a in get(registry, "ghoul").actions if a.on_hit is not None][0]
    assert "elf" in rider.exempt


@pytest.mark.parametrize("monster_id", ["wolf", "dire_wolf", "mastiff"])
def test_dogs_bite_knocks_down_without_a_save(registry, monster_id):
    riders = [a.on_hit for a in get(registry, monster_id).actions if a.on_hit is not None]
    assert [(r.condition, r.save) for r in riders] == [("prone", None)]
    assert riders[0].max_size in ("medium", "large")


@pytest.mark.parametrize("monster_id", ["steam_mephit", "dust_mephit", "magmin"])
def test_burst_monsters(registry, monster_id):
    monster = get(registry, monster_id)
    assert monster.death_burst is not None
    assert (monster.death_burst.save, monster.death_burst.dc > 0) == ("dex", True)
    assert "death_burst" in monster.traits


@pytest.mark.parametrize("monster_id", ["wolf", "zombie", "gargoyle", "fire_elemental"])
def test_other_monsters_do_not_burst(registry, monster_id):
    assert get(registry, monster_id).death_burst is None


@pytest.mark.parametrize("monster_id", ["hawk", "homunculus"])
def test_tiny_monsters(registry, monster_id):
    assert get(registry, monster_id).size == "tiny"
