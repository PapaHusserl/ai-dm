# Ожидаемый API: ai_dm.rules.death_saves (hero: HeroState, мутируется на месте)
#   is_dying(creature: CreatureState) -> bool   -- hp_current == 0 и не стабилен
#   is_stable(creature: CreatureState) -> bool  -- hp == 0 и death_saves.stable (B2)
#       DeathSaves(successes, failures, stable: bool = False): 3-й успех -> stable=True и счётчики
#       обнуляются (0/0); урон на 0 HP -> stable=False, провал +1 (крит +2), успехи СОХРАНЯЮТСЯ
#       (стабильный с прежними провалами после урона -- один провал, не смерть);
#       heal -> DeathSaves()
#   roll_death_save(hero, registry, rng, *, now_s, cause, by=None, modifiers=None,
#                   rerollers=None) -> str
#       modifiers / rerollers пробрасываются в roll (B7); спасбросок -- и d20-тест, и спасбросок:
#       Luck, Bless и т.п. действуют (B5); запросу конвейера ставится tags["critical_moment"]=True
#       (виден источникам модификаторов в request.tags) (B8). Мёртвый герой (status == "dead") ->
#       ValueError (rng не трогается) (B3)
#       один d20 без бонусов (через roll_pipeline, kind="death_save"). Итог -- строка:
#       ">= 10" -> "success"; "< 10" -> "failure"; 3-й успех -> "stable" (hp 0, is_stable);
#       3-й провал -> "dead"; nat 20 -> "revived" (hp 1, death_saves 0/0, "unconscious" с
#       source "0_hp" снят); nat 1 -> два провала (результат "failure" или "dead").
#       hp > 0 или уже стабилен -> ValueError (rng не трогается).
#       Смерть: hero.status = "dead", hero.death = DeathRecord(cause=cause, by=by, at_s=now_s,
#       location_id=hero.location_id). Причина обязательна (4.1): нет причины -- TypeError.
#   after_damage(hero, result: DamageResult, *, crit=False, cause, by=None, now_s=0) -> str
#       вызывается после damage.apply_damage; результат:
#       "none"    -- HP остались > 0;
#       "down"    -- упал на 0 HP: ставится AppliedCondition("unconscious", source="0_hp"),
#                    death_saves 0/0, is_dying;
#       "failure" -- урон при 0 HP: +1 провал (крит -- +2);
#       "dead"    -- 3 провала, либо массивный урон: при падении overkill >= hp_max, при уроне на
#                    0 HP -- result.final >= hp_max; запись DeathRecord как выше
#       урон при 0 HP, целиком съеденный временными HP (hp_lost + overkill == 0) -- "none", без
#       провала (D8); на мёртвом герое -> "dead" без записи и изменений (B3);
#       падение на 0 HP (ветка "down") и смерть снимают концентрацию (creature.concentration = None
#       и эффекты с expires.kind == "concentration") (B4)
#   resolve_out_of_combat(hero, registry, rng, *, now_s, cause, by=None) -> (исход, строки бросков)
#       (этап 2, партия 1; кортеж -- B6 ревью партии 2: по строке ТЗ 6 на каждый спасбросок)
#       спасброски вне боя: бросает roll_death_save, пока не будет исход, и возвращает его:
#       "stable" (3 успеха), "dead" (3 провала; запись смерти как у roll_death_save: cause, by,
#       at_s=now_s, location_id), "revived" (nat 20: hp 1, счётчики 0/0, unconscious снят).
#       После исхода rng не трогается. Герой не умирающий (hp > 0, стабилен, мёртв) ->
#       ValueError до броска. now_s и cause обязательны (TypeError). Детерминирован по сиду.
import pytest

from ai_dm.core.rng import Rng
from ai_dm.rules.damage import apply_damage
from ai_dm.rules.death_saves import (
    after_damage,
    is_dying,
    is_stable,
    resolve_out_of_combat,
    roll_death_save,
)
from ai_dm.rules.modifiers import Modifier, ModifierRegistry
from ai_dm.state.creature import (
    ActiveEffect,
    AppliedCondition,
    Concentration,
    CreatureState,
    DeathSaves,
    Expiry,
)
from ai_dm.state.death import DeathRecord
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState


class ScriptedRng(Rng):
    def __init__(self, *rolls):
        super().__init__(1)
        self.rolls = list(rolls)

    def randbelow(self, n):
        sides, face = self.rolls.pop(0)
        assert sides == n
        return face - 1


def make_hero(hp_current=0, successes=0, failures=0, species="human"):
    sheet = CharacterSheet(
        species_id=species,
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
    hero = HeroState(
        id="h1", ordinal=1, name="Арн", sheet=sheet, location_id="hall",
        creature=CreatureState(hp_current=hp_current, hp_max=12),
    )
    hero.creature.death_saves = DeathSaves(successes=successes, failures=failures)
    if hp_current == 0:
        hero.creature.conditions = [AppliedCondition(id="unconscious", source="0_hp")]
    return hero


def save(hero, registry, face):
    return roll_death_save(hero, registry, ScriptedRng((20, face)), now_s=0, cause="goal")


def hit(hero, registry, amount, **kwargs):
    result = apply_damage(hero, amount, "slashing", registry)
    kwargs.setdefault("cause", "goal")
    return after_damage(hero, result, **kwargs)


# спасброски от смерти

def test_roll_10_is_success(registry):
    hero = make_hero()
    assert save(hero, registry, 10) == "success"
    assert hero.creature.death_saves.successes == 1


def test_roll_9_is_failure(registry):
    hero = make_hero()
    assert save(hero, registry, 9) == "failure"
    assert hero.creature.death_saves.failures == 1


def test_roll_2_is_single_failure(registry):
    hero = make_hero()
    save(hero, registry, 2)
    assert hero.creature.death_saves.failures == 1


def test_three_successes_make_hero_stable(registry):
    hero = make_hero(successes=2)
    assert save(hero, registry, 15) == "stable"
    assert is_stable(hero.creature)
    assert not is_dying(hero.creature)
    assert hero.creature.hp_current == 0
    assert hero.status == "active"


def test_three_failures_kill_hero(registry):
    hero = make_hero(failures=2)
    rng = ScriptedRng((20, 5))
    assert roll_death_save(hero, registry, rng, now_s=500, cause="goal", by="g1") == "dead"
    assert hero.status == "dead"


def test_death_by_saves_writes_death_record(registry):
    hero = make_hero(failures=2)
    roll_death_save(hero, registry, ScriptedRng((20, 5)), now_s=500, cause="hazard", by="trap")
    assert isinstance(hero.death, DeathRecord)
    assert (hero.death.cause, hero.death.by) == ("hazard", "trap")
    assert (hero.death.at_s, hero.death.location_id) == (500, "hall")


def test_nat_20_revives_with_1_hp(registry):
    hero = make_hero(successes=1, failures=2)
    assert save(hero, registry, 20) == "revived"
    assert hero.creature.hp_current == 1
    assert hero.creature.death_saves == DeathSaves(successes=0, failures=0)
    assert not is_dying(hero.creature)
    assert hero.creature.conditions == []


def test_nat_1_counts_as_two_failures(registry):
    hero = make_hero()
    save(hero, registry, 1)
    assert hero.creature.death_saves.failures == 2


def test_nat_1_with_one_failure_kills(registry):
    hero = make_hero(failures=1)
    assert save(hero, registry, 1) == "dead"
    assert hero.status == "dead"


def test_death_save_at_positive_hp_is_error(registry):
    hero = make_hero(hp_current=5)
    rng = ScriptedRng()
    with pytest.raises(ValueError):
        roll_death_save(hero, registry, rng, now_s=0, cause="goal")


def test_death_save_when_stable_is_error(registry):
    hero = make_hero(successes=2)
    save(hero, registry, 15)
    with pytest.raises(ValueError):
        save(hero, registry, 15)


def test_death_save_requires_cause(registry):
    with pytest.raises(TypeError):
        roll_death_save(make_hero(), registry, ScriptedRng((20, 5)), now_s=0)


def test_death_saves_are_deterministic_by_seed(registry):
    a, b = make_hero(), make_hero()
    outcomes = []
    for hero in (a, b):
        outcomes.append(roll_death_save(hero, registry, Rng(21), now_s=0, cause="goal"))
    assert outcomes[0] == outcomes[1]
    assert a.creature.death_saves == b.creature.death_saves


# урон

def test_damage_above_zero_changes_no_saves(registry):
    hero = make_hero(hp_current=12)
    assert hit(hero, registry, 3) == "none"
    assert hero.creature.hp_current == 9
    assert hero.creature.death_saves == DeathSaves()


def test_drop_to_zero_makes_hero_dying_and_unconscious(registry):
    hero = make_hero(hp_current=5)
    hero.creature.conditions = []
    assert hit(hero, registry, 8) == "down"
    assert is_dying(hero.creature)
    assert [(c.id, c.source) for c in hero.creature.conditions] == [("unconscious", "0_hp")]
    assert hero.status == "active"


def test_massive_damage_on_drop_kills_instantly(registry):
    # 5 HP, 17 урона: остаток 12 >= hp_max 12
    hero = make_hero(hp_current=5)
    assert hit(hero, registry, 17, now_s=90, by="g1") == "dead"
    assert hero.status == "dead"
    assert hero.death.cause == "goal"
    assert hero.death.at_s == 90


def test_damage_just_below_massive_threshold_does_not_kill(registry):
    hero = make_hero(hp_current=5)
    assert hit(hero, registry, 16) == "down"


def test_damage_at_zero_hp_is_one_failure(registry):
    hero = make_hero()
    assert hit(hero, registry, 3) == "failure"
    assert hero.creature.death_saves.failures == 1


def test_crit_damage_at_zero_hp_is_two_failures(registry):
    hero = make_hero()
    assert hit(hero, registry, 3, crit=True) == "failure"
    assert hero.creature.death_saves.failures == 2


def test_third_failure_from_damage_kills(registry):
    hero = make_hero(failures=2)
    assert hit(hero, registry, 3) == "dead"
    assert hero.status == "dead"
    assert hero.death.cause == "goal"


def test_crit_at_one_failure_kills(registry):
    hero = make_hero(failures=1)
    assert hit(hero, registry, 3, crit=True) == "dead"


def test_massive_damage_at_zero_hp_kills_instantly(registry):
    hero = make_hero()
    assert hit(hero, registry, 12) == "dead"


def test_death_from_damage_keeps_given_cause(registry):
    hero = make_hero(failures=2)
    hit(hero, registry, 3, cause="hazard", by="lava")
    assert hero.death.cause == "hazard"
    assert hero.death.by == "lava"


def test_after_damage_requires_cause(registry):
    hero = make_hero()
    result = apply_damage(hero, 3, "slashing", registry)
    with pytest.raises(TypeError):
        after_damage(hero, result)


# стабильность полем (B2)

def stabilize(hero, registry):
    # три успеха подряд: последний бросок -- 15
    return save(hero, registry, 15)


def test_third_success_sets_stable_flag_and_resets_counters(registry):
    hero = make_hero(successes=2, failures=1)
    assert stabilize(hero, registry) == "stable"
    assert hero.creature.death_saves == DeathSaves(successes=0, failures=0, stable=True)


def test_stable_is_false_by_default():
    assert DeathSaves().stable is False


def test_is_stable_needs_zero_hp():
    creature = CreatureState(hp_current=3, hp_max=12)
    creature.death_saves.stable = True
    assert not is_stable(creature)


def test_is_stable_by_flag_without_three_successes():
    creature = CreatureState(hp_current=0, hp_max=12)
    creature.death_saves = DeathSaves(stable=True)
    assert is_stable(creature)
    assert not is_dying(creature)


def test_three_successes_counter_without_flag_is_not_stable():
    creature = CreatureState(hp_current=0, hp_max=12)
    creature.death_saves = DeathSaves(successes=3)
    assert not is_stable(creature)


def test_damage_on_stable_hero_with_old_failures_is_one_failure_not_death(registry):
    hero = make_hero(successes=2, failures=2)
    stabilize(hero, registry)
    assert hit(hero, registry, 3) == "failure"
    assert hero.creature.death_saves.failures == 1
    assert hero.status == "active"


def test_damage_on_stable_hero_clears_stable_flag(registry):
    hero = make_hero(successes=2)
    stabilize(hero, registry)
    hit(hero, registry, 3)
    assert hero.creature.death_saves.stable is False
    assert is_dying(hero.creature)


def test_crit_on_stable_hero_is_two_failures(registry):
    hero = make_hero(successes=2)
    stabilize(hero, registry)
    assert hit(hero, registry, 3, crit=True) == "failure"
    assert hero.creature.death_saves.failures == 2


def test_damage_at_zero_hp_keeps_successes(registry):
    hero = make_hero(successes=2, failures=0)
    assert hit(hero, registry, 3) == "failure"
    assert hero.creature.death_saves.successes == 2
    assert hero.creature.death_saves.failures == 1


def test_unstable_hero_can_be_stabilized_again_after_damage(registry):
    hero = make_hero(successes=2)
    stabilize(hero, registry)
    hit(hero, registry, 3)
    assert save(hero, registry, 15) == "success"
    assert hero.creature.death_saves.successes == 1


# мёртвый герой (B3)

def dead_hero(registry):
    hero = make_hero(failures=2)
    roll_death_save(hero, registry, ScriptedRng((20, 5)), now_s=500, cause="hazard", by="trap")
    assert hero.status == "dead"
    return hero


def test_death_save_of_dead_hero_is_error(registry):
    hero = dead_hero(registry)
    rng = ScriptedRng()
    with pytest.raises(ValueError):
        roll_death_save(hero, registry, rng, now_s=900, cause="goal")


def test_death_save_of_dead_hero_keeps_death_record(registry):
    hero = dead_hero(registry)
    with pytest.raises(ValueError):
        roll_death_save(hero, registry, ScriptedRng(), now_s=900, cause="goal")
    assert (hero.death.cause, hero.death.by, hero.death.at_s) == ("hazard", "trap", 500)


def test_damage_to_dead_hero_returns_dead(registry):
    hero = dead_hero(registry)
    assert hit(hero, registry, 3, now_s=900, cause="goal") == "dead"


def test_damage_to_dead_hero_does_not_rewrite_death_record(registry):
    hero = dead_hero(registry)
    hit(hero, registry, 3, now_s=900, cause="goal", by="g1")
    assert (hero.death.cause, hero.death.by, hero.death.at_s) == ("hazard", "trap", 500)


def test_damage_to_dead_hero_does_not_touch_death_saves(registry):
    hero = dead_hero(registry)
    before = hero.creature.death_saves.model_copy()
    hit(hero, registry, 3, cause="goal")
    assert hero.creature.death_saves == before


def test_damage_to_dead_hero_with_hp_does_not_add_conditions(registry):
    hero = dead_hero(registry)
    hero.creature.hp_current = 5
    hero.creature.conditions = []
    assert hit(hero, registry, 9, cause="goal") == "dead"
    assert hero.creature.conditions == []


# временные HP при 0 HP (D8)

def test_temp_hp_absorbing_all_damage_at_zero_hp_is_no_failure(registry):
    hero = make_hero()
    hero.creature.hp_temp = 5
    assert hit(hero, registry, 3) == "none"
    assert hero.creature.death_saves.failures == 0
    assert hero.creature.hp_temp == 2


def test_temp_hp_absorbing_exactly_all_damage_at_zero_hp_is_no_failure(registry):
    hero = make_hero()
    hero.creature.hp_temp = 3
    assert hit(hero, registry, 3) == "none"
    assert hero.creature.death_saves.failures == 0


def test_temp_hp_not_enough_at_zero_hp_still_counts_failure(registry):
    hero = make_hero()
    hero.creature.hp_temp = 2
    assert hit(hero, registry, 3) == "failure"
    assert hero.creature.death_saves.failures == 1


# концентрация (B4)

def concentrate(hero):
    hero.creature.concentration = Concentration(spell_id="bless", circle=1)
    hero.creature.active_effects = [
        ActiveEffect(
            id="bless", source="h1", kind="modifier",
            params={"target": "attack_roll", "dice": "1d4"}, expires=Expiry(kind="concentration"),
        ),
        ActiveEffect(
            id="sap", source="g1", kind="modifier",
            params={"target": "attack_roll", "mode": "disadvantage"},
            expires=Expiry(kind="start_of_turn", owner="g1"),
        ),
    ]


def test_dropping_to_zero_hp_ends_concentration(registry):
    hero = make_hero(hp_current=5)
    concentrate(hero)
    assert hit(hero, registry, 8) == "down"
    assert hero.creature.concentration is None
    assert [e.id for e in hero.creature.active_effects] == ["sap"]


def test_damage_above_zero_keeps_concentration(registry):
    hero = make_hero(hp_current=12)
    concentrate(hero)
    hit(hero, registry, 3)
    assert hero.creature.concentration.spell_id == "bless"
    assert len(hero.creature.active_effects) == 2


def test_instant_death_on_drop_ends_concentration(registry):
    hero = make_hero(hp_current=5)
    concentrate(hero)
    assert hit(hero, registry, 17) == "dead"
    assert hero.creature.concentration is None
    assert [e.id for e in hero.creature.active_effects] == ["sap"]


def test_death_by_failed_saves_ends_concentration(registry):
    hero = make_hero(failures=2)
    concentrate(hero)
    assert save(hero, registry, 5) == "dead"
    assert hero.creature.concentration is None
    assert [e.id for e in hero.creature.active_effects] == ["sap"]


# спасбросок от смерти -- спасбросок и d20-тест (B5, B7, B8)

def test_luck_rerolls_natural_1_on_death_save(registry):
    hero = make_hero(species="halfling")
    rng = ScriptedRng((20, 1), (20, 12))
    assert roll_death_save(hero, registry, rng, now_s=0, cause="goal") == "success"
    assert hero.creature.death_saves.failures == 0


def test_luck_reroll_to_20_revives(registry):
    hero = make_hero(species="halfling")
    rng = ScriptedRng((20, 1), (20, 20))
    assert roll_death_save(hero, registry, rng, now_s=0, cause="goal") == "revived"


def test_nat_1_without_luck_is_still_double_failure(registry):
    hero = make_hero(species="human")
    save(hero, registry, 1)
    assert hero.creature.death_saves.failures == 2


def test_bless_helps_death_save(registry):
    # 7 без Bless -- провал; 7 + 1d4 (3) = 10 -- успех
    hero = make_hero()
    hero.creature.active_effects.append(ActiveEffect(
        id="bless", source="c1", kind="modifier",
        params={"target": "saving_throw", "dice": "1d4"}, expires=Expiry(kind="concentration"),
    ))
    rng = ScriptedRng((20, 7), (4, 3))
    assert roll_death_save(hero, registry, rng, now_s=0, cause="goal") == "success"


def test_bless_for_attack_does_not_help_death_save(registry):
    hero = make_hero()
    hero.creature.active_effects.append(ActiveEffect(
        id="bless", source="c1", kind="modifier",
        params={"target": "attack_roll", "dice": "1d4"}, expires=Expiry(kind="concentration"),
    ))
    assert save(hero, registry, 7) == "failure"


class SpySource:
    id = "spy"

    def __init__(self, flat=0):
        self.flat = flat
        self.seen_tags = []
        self.seen_kinds = []

    def modifiers(self, request, registry):
        self.seen_tags.append(dict(request.tags))
        self.seen_kinds.append(request.kind)
        return [Modifier(source="spy", flat=self.flat)]


def spy_registry(source):
    modifiers = ModifierRegistry()
    modifiers.register(source)
    return modifiers


def test_death_save_sets_critical_moment_tag(registry):
    source = SpySource()
    roll_death_save(
        make_hero(), registry, ScriptedRng((20, 12)), now_s=0, cause="goal",
        modifiers=spy_registry(source),
    )
    assert source.seen_kinds == ["death_save"]
    assert source.seen_tags[0]["critical_moment"] is True


def test_death_save_passes_modifiers_to_roll(registry):
    # 7 + 3 = 10 -- успех (без источника был бы провал)
    hero = make_hero()
    outcome = roll_death_save(
        hero, registry, ScriptedRng((20, 7)), now_s=0, cause="goal",
        modifiers=spy_registry(SpySource(flat=3)),
    )
    assert outcome == "success"


def test_death_save_custom_modifiers_replace_default_sources(registry):
    # свой реестр без источников истощения: уровень 2 не вычитает 4
    hero = make_hero()
    hero.creature.exhaustion = 2
    outcome = roll_death_save(
        hero, registry, ScriptedRng((20, 10)), now_s=0, cause="goal", modifiers=ModifierRegistry()
    )
    assert outcome == "success"


def test_death_save_exhaustion_applies_by_default(registry):
    hero = make_hero()
    hero.creature.exhaustion = 2
    assert save(hero, registry, 10) == "failure"


def test_death_save_passes_empty_rerollers_to_roll(registry):
    hero = make_hero(species="halfling")
    rng = ScriptedRng((20, 1))
    roll_death_save(hero, registry, rng, now_s=0, cause="goal", rerollers=[])
    assert hero.creature.death_saves.failures == 2


# спасброски вне боя (resolve_out_of_combat)

def resolve(hero, registry, *faces, **kwargs):
    rng = ScriptedRng(*[(20, face) for face in faces])
    kwargs.setdefault("now_s", 500)
    kwargs.setdefault("cause", "goal")
    result, _ = resolve_out_of_combat(hero, registry, rng, **kwargs)
    return result, rng


def test_resolve_three_successes_make_hero_stable(registry):
    hero = make_hero()
    result, rng = resolve(hero, registry, 10, 12, 15)
    assert result == "stable"
    assert is_stable(hero.creature)
    assert hero.creature.hp_current == 0
    assert hero.status == "active"
    assert rng.rolls == []


def test_resolve_three_failures_kill_hero(registry):
    hero = make_hero()
    result, rng = resolve(hero, registry, 5, 5, 5, cause="goal", by="g1")
    assert result == "dead"
    assert hero.status == "dead"
    assert rng.rolls == []


def test_resolve_death_record_has_cause_by_time_and_place(registry):
    hero = make_hero()
    resolve(hero, registry, 2, 3, 4, now_s=777, cause="hazard", by="trap")
    assert hero.death == DeathRecord(
        cause="hazard", by="trap", at_s=777, location_id="hall", text=hero.death.text,
    )


def test_resolve_mixed_rolls_end_when_third_success_comes(registry):
    hero = make_hero()
    result, rng = resolve(hero, registry, 10, 5, 10, 5, 10)
    assert result == "stable"
    assert rng.rolls == []


def test_resolve_stops_rolling_after_outcome(registry):
    hero = make_hero(successes=2)
    result, rng = resolve(hero, registry, 15, 5, 5)
    assert result == "stable"
    assert rng.rolls == [(20, 5), (20, 5)]


def test_resolve_two_failures_then_three_successes_is_stable(registry):
    hero = make_hero()
    result, _ = resolve(hero, registry, 5, 5, 10, 10, 10)
    assert result == "stable"
    assert hero.creature.death_saves.successes == 0
    assert hero.creature.death_saves.failures == 0


def test_resolve_natural_20_revives_with_one_hp(registry):
    hero = make_hero()
    result, rng = resolve(hero, registry, 20, 5, 5)
    assert result == "revived"
    assert hero.creature.hp_current == 1
    assert hero.creature.death_saves == DeathSaves()
    assert hero.status == "active"
    assert not any(c.id == "unconscious" for c in hero.creature.conditions)
    assert rng.rolls == [(20, 5), (20, 5)]


def test_resolve_natural_20_after_some_saves_still_revives(registry):
    hero = make_hero()
    result, _ = resolve(hero, registry, 10, 5, 20)
    assert result == "revived"
    assert hero.creature.hp_current == 1


def test_resolve_natural_1_counts_two_failures(registry):
    hero = make_hero()
    result, rng = resolve(hero, registry, 1, 5)
    assert result == "dead"
    assert rng.rolls == []


def test_resolve_continues_from_existing_counters(registry):
    hero = make_hero(successes=1, failures=2)
    result, _ = resolve(hero, registry, 4)
    assert result == "dead"


def test_resolve_hero_with_hp_raises_and_keeps_rng(registry):
    hero = make_hero(hp_current=5)
    rng = ScriptedRng((20, 10))
    with pytest.raises(ValueError):
        resolve_out_of_combat(hero, registry, rng, now_s=0, cause="goal")
    assert rng.rolls == [(20, 10)]


def test_resolve_stable_hero_raises_and_keeps_rng(registry):
    hero = make_hero()
    hero.creature.death_saves.stable = True
    rng = ScriptedRng((20, 10))
    with pytest.raises(ValueError):
        resolve_out_of_combat(hero, registry, rng, now_s=0, cause="goal")
    assert rng.rolls == [(20, 10)]


def test_resolve_dead_hero_raises_and_keeps_rng(registry):
    hero = make_hero()
    hero.status = "dead"
    rng = ScriptedRng((20, 10))
    with pytest.raises(ValueError):
        resolve_out_of_combat(hero, registry, rng, now_s=0, cause="goal")
    assert rng.rolls == [(20, 10)]


def test_resolve_requires_cause_and_now_s(registry):
    with pytest.raises(TypeError):
        resolve_out_of_combat(make_hero(), registry, ScriptedRng((20, 10)), now_s=0)
    with pytest.raises(TypeError):
        resolve_out_of_combat(make_hero(), registry, ScriptedRng((20, 10)), cause="goal")


def test_resolve_is_deterministic_by_seed(registry):
    for seed in range(30):
        first, second = make_hero(), make_hero()
        rng1, rng2 = Rng(seed), Rng(seed)
        result1 = resolve_out_of_combat(first, registry, rng1, now_s=10, cause="goal")
        result2 = resolve_out_of_combat(second, registry, rng2, now_s=10, cause="goal")
        assert result1 == result2
        assert rng1.state == rng2.state
        assert first == second


def test_resolve_by_seed_gives_all_three_outcomes_and_nothing_else(registry):
    outcomes = set()
    for seed in range(200):
        outcome, _ = resolve_out_of_combat(make_hero(), registry, Rng(seed), now_s=0, cause="goal")
        outcomes.add(outcome)
    assert outcomes == {"stable", "dead", "revived"}


def test_resolve_by_seed_matches_manual_death_saves(registry):
    for seed in range(20):
        manual_hero, auto_hero = make_hero(), make_hero()
        manual_rng = Rng(seed)
        outcome = "success"
        while outcome in ("success", "failure"):
            outcome = roll_death_save(manual_hero, registry, manual_rng, now_s=0, cause="goal")
        auto, _ = resolve_out_of_combat(auto_hero, registry, Rng(seed), now_s=0, cause="goal")
        assert auto == outcome
        assert auto_hero == manual_hero


def resolve_with_logs(hero, registry, *faces):
    rng = ScriptedRng(*[(20, face) for face in faces])
    return resolve_out_of_combat(hero, registry, rng, now_s=0, cause="goal")


def test_resolve_returns_outcome_and_log_lines(registry):
    outcome, logs = resolve_with_logs(make_hero(), registry, 10, 12, 15)
    assert outcome == "stable"
    assert isinstance(logs, list)


def test_resolve_gives_one_log_line_per_save(registry):
    _, logs = resolve_with_logs(make_hero(), registry, 10, 5, 10, 5, 10)
    assert len(logs) == 5
    assert all(isinstance(line, str) and line for line in logs)


def test_resolve_log_lines_have_rolled_faces(registry):
    _, logs = resolve_with_logs(make_hero(), registry, 12, 3, 17, 10)
    assert "12" in logs[0]
    assert "3" in logs[1]
    assert "17" in logs[2]


def test_resolve_natural_20_gives_single_log_line(registry):
    outcome, logs = resolve_with_logs(make_hero(), registry, 20)
    assert outcome == "revived"
    assert len(logs) == 1
