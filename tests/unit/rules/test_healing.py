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
from ai_dm.rules.healing import expire_max_hp, grant_max_hp, heal, revert_max_hp
from ai_dm.rules.inventory import add_item, use_item
from ai_dm.rules.progression import apply_level
from ai_dm.state.creature import (
    ActiveEffect,
    AppliedCondition,
    CreatureState,
    DeathSaves,
    Expiry,
)
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState
from ai_dm.state.world import NPC, WorldState


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


# К3 П3б: Помощь (grant_max_hp / revert_max_hp / expire_max_hp)

def aided(hp_current=12, hp_max=12, until=100):
    hero = make_hero(hp_current=hp_current)
    hero.creature.hp_max = hp_max
    grant_max_hp(hero.creature, "aid", "h1", 5, until)
    return hero


def aid_effect(creature):
    return [e for e in creature.active_effects if e.kind == "max_hp"]


def world_at(now_s):
    world = WorldState(world_id="w1", rng=Rng(1).state)
    world.clock.advance(now_s)
    return world


def test_grant_max_hp_raises_max_and_current():
    hero = aided()
    assert (hero.creature.hp_max, hero.creature.hp_current) == (17, 17)


def test_grant_max_hp_keeps_the_wound():
    hero = aided(hp_current=7)
    assert (hero.creature.hp_max, hero.creature.hp_current) == (17, 12)


def test_grant_max_hp_records_the_effect():
    effect = aid_effect(aided(until=500).creature)[0]
    assert (effect.id, effect.source, effect.params) == ("aid", "h1", {"amount": 5})
    assert (effect.expires.kind, effect.expires.value) == ("seconds", 500)


def test_grant_max_hp_twice_does_not_stack():
    hero = aided()
    grant_max_hp(hero.creature, "aid", "h1", 5, 900)
    assert (hero.creature.hp_max, hero.creature.hp_current) == (17, 17)
    assert [e.expires.value for e in aid_effect(hero.creature)] == [900]


def test_grant_max_hp_repeat_after_damage_keeps_the_damage_but_not_the_bonus_twice():
    hero = aided()
    hero.creature.hp_current = 8
    grant_max_hp(hero.creature, "aid", "h1", 5, 900)
    assert (hero.creature.hp_max, hero.creature.hp_current) == (17, 13)


def test_grant_max_hp_returns_true_for_a_fresh_grant():
    hero = make_hero()
    assert grant_max_hp(hero.creature, "aid", "h1", 5, 100) is True


def test_grant_max_hp_weaker_than_active_changes_nothing_and_returns_false():
    hero = aided()
    grant_max_hp(hero.creature, "aid", "h1", 10, 200)
    before = (hero.creature.hp_max, hero.creature.hp_current)
    assert grant_max_hp(hero.creature, "aid", "h1", 5, 900) is False
    assert (hero.creature.hp_max, hero.creature.hp_current) == before == (22, 22)
    assert [(e.params["amount"], e.expires.value) for e in aid_effect(hero.creature)] == [
        (10, 200)
    ]


def test_grant_max_hp_stronger_replaces_and_renews_the_term():
    hero = aided()
    assert grant_max_hp(hero.creature, "aid", "h1", 10, 900) is True
    assert (hero.creature.hp_max, hero.creature.hp_current) == (22, 22)
    assert [(e.params["amount"], e.expires.value) for e in aid_effect(hero.creature)] == [
        (10, 900)
    ]


def test_grant_max_hp_equal_renews_the_term_and_returns_true():
    hero = aided(until=100)
    assert grant_max_hp(hero.creature, "aid", "h1", 5, 900) is True
    assert [e.expires.value for e in aid_effect(hero.creature)] == [900]


def test_grant_max_hp_of_another_spell_adds_up():
    hero = aided()
    grant_max_hp(hero.creature, "heroes_feast", "h1", 10, 900)
    assert hero.creature.hp_max == 27


def test_revert_max_hp_lowers_max_and_removes_the_effect():
    hero = aided()
    revert_max_hp(hero.creature, aid_effect(hero.creature)[0])
    assert hero.creature.hp_max == 12
    assert aid_effect(hero.creature) == []


def test_revert_max_hp_clamps_current_to_the_new_max():
    hero = aided()
    revert_max_hp(hero.creature, aid_effect(hero.creature)[0])
    assert hero.creature.hp_current == 12


def test_revert_max_hp_keeps_lower_current():
    hero = aided()
    hero.creature.hp_current = 8
    revert_max_hp(hero.creature, aid_effect(hero.creature)[0])
    assert hero.creature.hp_current == 8


def test_expire_max_hp_at_the_limit_reverts_and_logs():
    hero = aided(until=100)
    hero.creature.hp_current = 8
    lines = expire_max_hp(hero, world_at(100))
    assert lines == ["Помощь кончилась: Арн HP 8/12"]
    assert aid_effect(hero.creature) == []


def test_expire_max_hp_reverts_an_expired_effect_that_follows_a_live_one():
    hero = make_hero(hp_current=12)
    hero.creature.hp_max = 12
    grant_max_hp(hero.creature, "later", "h1", 3, 500)
    grant_max_hp(hero.creature, "aid", "h1", 5, 100)
    lines = expire_max_hp(hero, world_at(200))
    assert lines == ["Помощь кончилась: Арн HP 15/15"]
    assert [e.id for e in aid_effect(hero.creature)] == ["later"]


def test_expire_max_hp_before_the_limit_does_nothing():
    hero = aided(until=100)
    assert expire_max_hp(hero, world_at(99)) == []
    assert hero.creature.hp_max == 17


def test_expire_max_hp_full_hp_goes_back_to_full():
    hero = aided(until=100)
    lines = expire_max_hp(hero, world_at(200))
    assert lines == ["Помощь кончилась: Арн HP 12/12"]


def npc_aided(world, npc_id, until):
    npc = NPC(
        id=npc_id, name=f"Имя {npc_id}", means=["x"],
        creature=CreatureState(hp_current=6, hp_max=6),
    )
    grant_max_hp(npc.creature, "aid", "h1", 5, until)
    world.npcs[npc_id] = npc
    return npc


def test_expire_max_hp_reverts_npcs_of_the_world():
    world = world_at(200)
    npc = npc_aided(world, "n1", 100)
    lines = expire_max_hp(make_hero(), world)
    assert lines == ["Помощь кончилась: Имя n1 HP 6/6"]
    assert npc.creature.hp_max == 6


def test_expire_max_hp_keeps_npcs_with_time_left():
    world = world_at(50)
    npc = npc_aided(world, "n1", 100)
    expire_max_hp(make_hero(), world)
    assert npc.creature.hp_max == 11


def test_expire_max_hp_skips_npcs_without_creature():
    world = world_at(200)
    world.npcs["bare"] = NPC(id="bare", name="bare", means=["x"])
    assert expire_max_hp(make_hero(), world) == []


def test_expire_max_hp_lists_hero_before_npcs():
    hero = aided(until=100)
    world = world_at(200)
    npc_aided(world, "n1", 100)
    lines = expire_max_hp(hero, world)
    assert [line.split(":")[1].split(" HP")[0].strip() for line in lines] == ["Арн", "Имя n1"]


def test_expire_max_hp_ignores_other_effect_kinds():
    hero = make_hero()
    hero.creature.active_effects.append(ActiveEffect(
        id="x", source="h1", kind="spell", expires=Expiry(kind="seconds", value=10),
    ))
    assert expire_max_hp(hero, world_at(200)) == []
    assert len(hero.creature.active_effects) == 1


def test_level_up_during_aid_adds_the_gain_on_top(registry):
    hero = aided()
    apply_level(hero, registry, 6)
    assert (hero.creature.hp_max, hero.creature.hp_current) == (23, 23)


def test_aid_rollback_after_level_up_takes_only_its_five(registry):
    hero = aided()
    apply_level(hero, registry, 6)
    revert_max_hp(hero.creature, aid_effect(hero.creature)[0])
    assert (hero.creature.hp_max, hero.creature.hp_current) == (18, 18)


def test_expire_max_hp_twice_logs_once():
    hero = aided(until=100)
    world = world_at(200)
    expire_max_hp(hero, world)
    assert expire_max_hp(hero, world) == []
