# Ожидаемый API: ai_dm.rules.healing (target: HeroState | CreatureState, мутируется на месте)
#   heal(target, amount: int) -> int
#       hp_current = min(hp_max, hp_current + amount); возвращает фактически восстановленные HP;
#       amount < 0 -> ValueError; временные HP не трогает.
#       Если до лечения было 0 HP и amount > 0: death_saves -> 0/0, снимается "стабилен",
#       (DeathSaves() целиком, включая stable: bool, B2);
#       из conditions убирается "unconscious" с source "0_hp" (его ставит death_saves.after_damage;
#       "unconscious" с другим source, например от сна, остаётся) -- существо не умирает и не лежит
#   Мёртвый (hero.status == "dead") -> ValueError, HP не меняются (B3).
#   Через healing идёт и inventory.use_item (зелье лечения): тест на герое с 0 HP.
# Состояния death_saves: is_dying / is_stable -- см. test_death_saves.py
import pytest

from ai_dm.core.rng import Rng
from ai_dm.rules.death_saves import is_dying, is_stable, roll_death_save
from ai_dm.rules.healing import heal
from ai_dm.rules.inventory import add_item, use_item
from ai_dm.state.creature import AppliedCondition, CreatureState, DeathSaves
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState


class ScriptedRng(Rng):
    def __init__(self, *rolls):
        super().__init__(1)
        self.rolls = list(rolls)

    def randbelow(self, n):
        sides, face = self.rolls.pop(0)
        assert sides == n
        return face - 1


def make_hero(hp_current=12, status="active"):
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
        creature=CreatureState(hp_current=hp_current, hp_max=12),
        status=status,
    )


def make_dying_hero():
    hero = make_hero(hp_current=0)
    hero.creature.death_saves = DeathSaves(successes=1, failures=2)
    hero.creature.conditions = [AppliedCondition(id="unconscious", source="0_hp")]
    return hero


def condition_ids(hero):
    return [c.id for c in hero.creature.conditions]


# обычное лечение

def test_heal_restores_hp():
    hero = make_hero(hp_current=5)
    assert heal(hero, 4) == 4
    assert hero.creature.hp_current == 9


def test_heal_is_capped_at_max_and_returns_actual():
    hero = make_hero(hp_current=10)
    assert heal(hero, 10) == 2
    assert hero.creature.hp_current == 12


def test_heal_at_full_hp_restores_nothing():
    assert heal(make_hero(), 5) == 0


def test_heal_negative_is_error():
    with pytest.raises(ValueError):
        heal(make_hero(), -1)


def test_heal_works_on_creature_state():
    creature = CreatureState(hp_current=2, hp_max=7)
    heal(creature, 3)
    assert creature.hp_current == 5


def test_heal_does_not_touch_temp_hp():
    hero = make_hero(hp_current=5)
    hero.creature.hp_temp = 4
    heal(hero, 3)
    assert hero.creature.hp_temp == 4


# лечение с 0 HP

def test_heal_from_zero_hp_raises_hp():
    hero = make_dying_hero()
    heal(hero, 3)
    assert hero.creature.hp_current == 3


def test_heal_from_zero_hp_resets_death_saves():
    hero = make_dying_hero()
    heal(hero, 3)
    assert hero.creature.death_saves == DeathSaves(successes=0, failures=0)


def test_heal_from_zero_hp_ends_dying():
    hero = make_dying_hero()
    assert is_dying(hero.creature)
    heal(hero, 3)
    assert not is_dying(hero.creature)


def test_heal_from_zero_hp_removes_unconscious_from_zero_hp():
    hero = make_dying_hero()
    heal(hero, 3)
    assert "unconscious" not in condition_ids(hero)


def test_heal_from_zero_hp_keeps_unconscious_from_other_source():
    hero = make_dying_hero()
    hero.creature.conditions.append(AppliedCondition(id="unconscious", source="sleep"))
    heal(hero, 3)
    assert [c.source for c in hero.creature.conditions] == ["sleep"]


def test_heal_stable_creature_clears_stable(registry):
    hero = make_hero(hp_current=0)
    hero.creature.death_saves = DeathSaves(successes=2, failures=0)
    roll_death_save(hero, registry, ScriptedRng((20, 12)), now_s=0, cause="goal")
    assert is_stable(hero.creature)
    heal(hero, 2)
    assert not is_stable(hero.creature)
    assert hero.creature.hp_current == 2
    assert hero.creature.death_saves == DeathSaves()


def test_heal_resets_stable_flag_and_all_counters():
    hero = make_hero(hp_current=0)
    hero.creature.death_saves = DeathSaves(successes=0, failures=0, stable=True)
    heal(hero, 1)
    assert hero.creature.death_saves == DeathSaves()
    assert hero.creature.death_saves.stable is False


# мёртвый герой (B3)

def test_heal_dead_hero_is_error():
    hero = make_hero(hp_current=0, status="dead")
    with pytest.raises(ValueError):
        heal(hero, 5)
    assert hero.creature.hp_current == 0


def test_heal_dead_hero_with_hp_is_error():
    hero = make_hero(hp_current=4, status="dead")
    with pytest.raises(ValueError):
        heal(hero, 5)
    assert hero.creature.hp_current == 4


def test_heal_zero_amount_on_dead_hero_is_error():
    with pytest.raises(ValueError):
        heal(make_hero(hp_current=0, status="dead"), 0)


# зелье через healing

def test_potion_at_zero_hp_raises_hero(registry):
    hero = make_dying_hero()
    add_item(hero, "potion_of_healing", cost_cp=0)
    use_item(hero, "potion_of_healing", registry, ScriptedRng((4, 1), (4, 1)))
    assert hero.creature.hp_current == 4


def test_potion_at_zero_hp_resets_death_saves(registry):
    hero = make_dying_hero()
    add_item(hero, "potion_of_healing", cost_cp=0)
    use_item(hero, "potion_of_healing", registry, ScriptedRng((4, 1), (4, 1)))
    assert hero.creature.death_saves == DeathSaves(successes=0, failures=0)
    assert not is_dying(hero.creature)
