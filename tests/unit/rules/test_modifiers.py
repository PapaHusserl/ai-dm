# Ожидаемый API: ai_dm.rules.modifiers (источники модификаторов конвейера бросков)
#   Modifier(BaseModel): source: str, advantage: bool = False, disadvantage: bool = False,
#       flat: int = 0, dice: str | None = None, auto_fail: bool = False, auto_crit: bool = False,
#       dc_bonus: int = 0, crit_min: int | None = None
#       dc_bonus прибавляется к цели броска (КД атаки / СЛ) и в исходе, и в логе (укрытие +2:
#       "против КД 17" при КД 15); суммируется по источникам. crit_min -- нижняя граница крита атаки
#       (natural >= crit_min -- крит); итоговая -- минимальная из источников, по умолчанию 20
#   ModifierSource -- любой объект с атрибутом id: str и методом
#       modifiers(request: RollRequest, registry) -> list[Modifier]
#   ModifierRegistry.register(source) -> None
#   default_modifier_registry() -> ModifierRegistry -- новый экземпляр со встроенными источниками
#       (состояния, черты видов, ActiveEffect-ы); регистрация во внешнем экземпляре
#       не влияет на другие. Передаётся в roll(..., modifiers=...).
# Встроенные источники (rules/roll_pipeline.roll, контракт RollRequest -- в test_roll_pipeline.py):
#   Состояния -- AppliedCondition в creature.conditions у actor / target (SRD 5.2):
#     poisoned: помеха на атаки и проверки актёра, не на спасброски
#     prone: актёр -- помеха на свои атаки; цель -- атака с tags["melee"]=True идёт с
#            преимуществом, иначе (melee=False) с помехой. Зон ещё нет, дистанцию несёт запрос
#     paralyzed / unconscious: цель -- атаки с преимуществом; если tags["melee"] и бросок попал --
#            исход "crit". Актёр -- спасброски ability str/dex: автопровал (d20 не бросается,
#            natural None, outcome "fail"); con и другие бросаются как обычно
#     blinded: актёр -- помеха на атаки; цель -- преимущество на атаки по ней
#     restrained: актёр -- помеха на атаки, помеха на спасбросок dex; цель -- преимущество на атаки
#     invisible: актёр -- преимущество на атаки; цель -- помеха на атаки по ней
#     frightened: актёр -- помеха на атаки и проверки (линия видимости источника не моделируется)
#     Истощение 2024: creature.exhaustion = N -> терм "exhaustion" = -2 * N во всех d20-тестах
#   Черты вида (по species_id героя через registry; применяются к kind="save" при
#     tags["vs_condition"] == id состояния): halfling Brave -> frightened, dwarf Dwarven
#     Resilience -> poisoned, elf Fey Ancestry -> charmed; все дают преимущество
#   ActiveEffect(kind="modifier", params={"target": "attack_roll" | "saving_throw", ...}) у актёра:
#     params["dice"] -- бонусный кубик (терм с source = effect.id, кубик после d20);
#     params["mode"] -- "advantage" | "disadvantage"; params["consume"]=True -- эффект снимается
#     после первого же броска того target; params["against"] -- id цели (сверяется с
#     request.target_id), для чужой цели эффект не действует и не снимается;
#     params["side"] -- "actor" (по умолчанию: эффект лежит у бросающего) | "target" (эффект лежит
#     в active_effects цели request.target и действует на броски по ней, напр. Dodge: помеха на
#     атаки по цели; у самого бросающего с side="target" эффект не действует). target "saving_throw"
#     действует и на kind="death_save" (спасбросок от смерти -- тоже спасбросок)
#   Вложенные состояния (D5): unconscious => incapacitated + prone; paralyzed, stunned, petrified
#     => incapacitated. Дальняя атака (melee=False) по unconscious: преимущество (бессознательный) +
#     помеха (prone, дальняя) = обычный бросок. incapacitated: помеха на инициативу актёра.
#     invisible: преимущество на инициативу актёра.
#     grappled: помеха на атаки актёра по всем целям, кроме схватившего (AppliedCondition.source --
#     id схватившего, сверяется с request.target_id)
#   RollRequest.now_s: int | None = None -- текущее время для источников «раз в день»
#   critical_moment и остальные tags доступны внешним источникам в request.tags
import pytest

from ai_dm.core.rng import Rng
from ai_dm.rules.modifiers import Modifier, default_modifier_registry
from ai_dm.rules.roll_pipeline import RollRequest, roll
from ai_dm.state.creature import ActiveEffect, AppliedCondition, CreatureState, Expiry
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState


class ScriptedRng(Rng):
    def __init__(self, *rolls):
        super().__init__(1)
        self.rolls = list(rolls)

    def randbelow(self, n):
        sides, face = self.rolls.pop(0)
        assert sides == n
        return face - 1


def make_creature(*conditions, **fields):
    return CreatureState(
        hp_current=7, hp_max=7, conditions=[AppliedCondition(id=c) for c in conditions], **fields
    )


def make_hero(species="human"):
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
    return HeroState(
        id="h1", ordinal=1, name="Арн", sheet=sheet,
        creature=CreatureState(hp_current=12, hp_max=12),
    )


def make_request(kind="attack", **kwargs):
    fields = {"kind": kind, "actor": make_creature(), "bonus": 5, "dc": 15}
    fields.update(kwargs)
    return RollRequest(**fields)


def two_dice(first=14, second=3):
    return ScriptedRng((20, first), (20, second))


def modifier_effect(id, **params):
    return ActiveEffect(id=id, source="x", kind="modifier", params=params)


# отравлен

def test_poisoned_gives_disadvantage_on_attack(registry):
    result = roll(make_request(actor=make_creature("poisoned")), two_dice(), registry)
    assert result.advantage == "disadvantage"
    assert result.natural == 3


def test_poisoned_gives_disadvantage_on_check(registry):
    request = make_request("check", actor=make_creature("poisoned"), skill="athletics")
    assert roll(request, two_dice(), registry).advantage == "disadvantage"


def test_poisoned_does_not_affect_save(registry):
    request = make_request("save", actor=make_creature("poisoned"), ability="con")
    assert roll(request, ScriptedRng((20, 12)), registry).advantage == "normal"


# лежит

def test_prone_actor_attacks_with_disadvantage(registry):
    result = roll(make_request(actor=make_creature("prone")), two_dice(), registry)
    assert result.advantage == "disadvantage"


def test_attack_on_prone_target_in_melee_has_advantage(registry):
    request = make_request(target=make_creature("prone"), tags={"melee": True})
    assert roll(request, two_dice(), registry).advantage == "advantage"


def test_attack_on_prone_target_at_range_has_disadvantage(registry):
    request = make_request(target=make_creature("prone"), tags={"melee": False})
    assert roll(request, two_dice(), registry).advantage == "disadvantage"


# парализован / без сознания

def test_ranged_attack_on_paralyzed_target_has_advantage(registry):
    request = make_request(target=make_creature("paralyzed"), tags={"melee": False})
    assert roll(request, two_dice(), registry).advantage == "advantage"


def test_melee_attack_on_unconscious_target_has_advantage(registry):
    request = make_request(target=make_creature("unconscious"), tags={"melee": True})
    assert roll(request, two_dice(), registry).advantage == "advantage"


@pytest.mark.parametrize("condition", ["paralyzed", "unconscious"])
def test_melee_hit_on_helpless_target_is_crit(registry, condition):
    request = make_request(target=make_creature(condition), tags={"melee": True})
    result = roll(request, two_dice(10, 10), registry)
    assert result.outcome == "crit"


@pytest.mark.parametrize("condition", ["paralyzed", "unconscious"])
def test_ranged_hit_on_helpless_target_is_plain_hit(registry, condition):
    request = make_request(target=make_creature(condition), tags={"melee": False})
    result = roll(request, two_dice(10, 10), registry)
    assert result.outcome == "hit"


@pytest.mark.parametrize("condition", ["paralyzed", "unconscious"])
def test_melee_miss_on_helpless_target_stays_miss(registry, condition):
    request = make_request(target=make_creature(condition), tags={"melee": True})
    result = roll(request, two_dice(3, 3), registry)
    assert result.outcome == "miss"


@pytest.mark.parametrize("condition", ["paralyzed", "unconscious"])
@pytest.mark.parametrize("ability", ["str", "dex"])
def test_helpless_actor_auto_fails_str_and_dex_saves(registry, condition, ability):
    request = make_request("save", actor=make_creature(condition), ability=ability)
    result = roll(request, ScriptedRng(), registry)
    assert result.outcome == "fail"
    assert result.natural is None


@pytest.mark.parametrize("condition", ["paralyzed", "unconscious"])
def test_helpless_actor_still_rolls_con_save(registry, condition):
    request = make_request("save", actor=make_creature(condition), ability="con")
    result = roll(request, ScriptedRng((20, 18)), registry)
    assert result.outcome == "success"


# слепота, путы, невидимость, испуг

def test_blinded_actor_attacks_with_disadvantage(registry):
    result = roll(make_request(actor=make_creature("blinded")), two_dice(), registry)
    assert result.advantage == "disadvantage"


def test_attack_on_blinded_target_has_advantage(registry):
    result = roll(make_request(target=make_creature("blinded")), two_dice(), registry)
    assert result.advantage == "advantage"


def test_restrained_actor_attacks_with_disadvantage(registry):
    result = roll(make_request(actor=make_creature("restrained")), two_dice(), registry)
    assert result.advantage == "disadvantage"


def test_restrained_actor_has_disadvantage_on_dex_save(registry):
    request = make_request("save", actor=make_creature("restrained"), ability="dex")
    assert roll(request, two_dice(), registry).advantage == "disadvantage"


def test_restrained_actor_normal_on_str_save(registry):
    request = make_request("save", actor=make_creature("restrained"), ability="str")
    assert roll(request, ScriptedRng((20, 12)), registry).advantage == "normal"


def test_attack_on_restrained_target_has_advantage(registry):
    result = roll(make_request(target=make_creature("restrained")), two_dice(), registry)
    assert result.advantage == "advantage"


def test_invisible_actor_attacks_with_advantage(registry):
    result = roll(make_request(actor=make_creature("invisible")), two_dice(), registry)
    assert result.advantage == "advantage"


def test_attack_on_invisible_target_has_disadvantage(registry):
    result = roll(make_request(target=make_creature("invisible")), two_dice(), registry)
    assert result.advantage == "disadvantage"


def test_frightened_actor_attacks_with_disadvantage(registry):
    result = roll(make_request(actor=make_creature("frightened")), two_dice(), registry)
    assert result.advantage == "disadvantage"


def test_frightened_actor_checks_with_disadvantage(registry):
    request = make_request("check", actor=make_creature("frightened"), skill="athletics")
    assert roll(request, two_dice(), registry).advantage == "disadvantage"


def test_frightened_does_not_affect_save(registry):
    request = make_request("save", actor=make_creature("frightened"), ability="wis")
    assert roll(request, ScriptedRng((20, 12)), registry).advantage == "normal"


# проклят (не SRD, У0 П3): помеха на проверки и спасброски, не на атаки

def test_cursed_actor_checks_with_disadvantage(registry):
    request = make_request("check", actor=make_creature("cursed"), skill="athletics")
    result = roll(request, two_dice(), registry)
    assert result.advantage == "disadvantage"
    assert result.natural == 3


def test_cursed_actor_saves_with_disadvantage(registry):
    request = make_request("save", actor=make_creature("cursed"), ability="wis")
    result = roll(request, two_dice(), registry)
    assert result.advantage == "disadvantage"
    assert result.natural == 3


def test_cursed_does_not_affect_attack(registry):
    result = roll(make_request(actor=make_creature("cursed")), ScriptedRng((20, 12)), registry)
    assert result.advantage == "normal"


def test_cursed_label_on_check_is_cursed_word(registry):
    request = make_request("check", actor=make_creature("cursed"), skill="athletics")
    assert roll(request, two_dice(), registry).disadvantage_from == ["проклят"]


def test_cursed_label_on_save_is_cursed_word(registry):
    request = make_request("save", actor=make_creature("cursed"), ability="wis")
    assert roll(request, two_dice(), registry).disadvantage_from == ["проклят"]


def test_cursed_target_does_not_change_attack_on_it(registry):
    request = make_request(target=make_creature("cursed"))
    assert roll(request, ScriptedRng((20, 12)), registry).advantage == "normal"


# болен (не SRD, У1 П3): как отравление -- помеха на атаки и проверки, не на спасброски

def test_diseased_actor_attacks_with_disadvantage(registry):
    result = roll(make_request(actor=make_creature("diseased")), two_dice(), registry)
    assert result.advantage == "disadvantage"
    assert result.natural == 3


def test_diseased_actor_checks_with_disadvantage(registry):
    request = make_request("check", actor=make_creature("diseased"), skill="athletics")
    assert roll(request, two_dice(), registry).advantage == "disadvantage"


def test_diseased_does_not_affect_save(registry):
    request = make_request("save", actor=make_creature("diseased"), ability="con")
    assert roll(request, ScriptedRng((20, 12)), registry).advantage == "normal"


def test_diseased_label_is_sick_word(registry):
    request = make_request("check", actor=make_creature("diseased"), skill="athletics")
    assert roll(request, two_dice(), registry).disadvantage_from == ["болен"]


# вонь (не SRD, У1 П3): помеха только на проверки Харизмы

def test_smelly_actor_charisma_check_has_disadvantage(registry):
    request = make_request(
        "check", actor=make_creature("smelly"), skill="persuasion", ability="cha"
    )
    result = roll(request, two_dice(), registry)
    assert result.advantage == "disadvantage"
    assert result.natural == 3


def test_smelly_label_on_charisma_check_is_stench_word(registry):
    request = make_request(
        "check", actor=make_creature("smelly"), skill="persuasion", ability="cha"
    )
    assert roll(request, two_dice(), registry).disadvantage_from == ["вонь"]


def test_smelly_does_not_affect_strength_check(registry):
    request = make_request(
        "check", actor=make_creature("smelly"), skill="athletics", ability="str"
    )
    assert roll(request, ScriptedRng((20, 12)), registry).advantage == "normal"


def test_smelly_does_not_affect_charisma_save(registry):
    request = make_request("save", actor=make_creature("smelly"), ability="cha")
    assert roll(request, ScriptedRng((20, 12)), registry).advantage == "normal"


def test_smelly_does_not_affect_attack(registry):
    result = roll(make_request(actor=make_creature("smelly")), ScriptedRng((20, 12)), registry)
    assert result.advantage == "normal"


def test_cursed_and_advantage_effect_cancel_out(registry):
    actor = make_creature("cursed")
    actor.active_effects.append(modifier_effect("bless", target="saving_throw", mode="advantage"))
    request = make_request("save", actor=actor, ability="wis")
    assert roll(request, ScriptedRng((20, 12)), registry).advantage == "normal"


def test_invisible_actor_and_poisoned_cancel_out(registry):
    actor = make_creature("invisible", "poisoned")
    result = roll(make_request(actor=actor), ScriptedRng((20, 12)), registry)
    assert result.advantage == "normal"


# истощение

@pytest.mark.parametrize("kind", ["attack", "save", "check"])
def test_exhaustion_subtracts_two_per_level(registry, kind):
    actor = make_creature(exhaustion=2)
    result = roll(make_request(kind, actor=actor), ScriptedRng((20, 14)), registry)
    assert {t.source: t.value for t in result.terms}["exhaustion"] == -4
    assert result.total == 14 + 5 - 4


def test_no_exhaustion_term_at_level_zero(registry):
    result = roll(make_request(), ScriptedRng((20, 14)), registry)
    assert "exhaustion" not in [t.source for t in result.terms]


def test_exhaustion_can_turn_hit_into_miss(registry):
    actor = make_creature(exhaustion=3)
    result = roll(make_request(actor=actor), ScriptedRng((20, 14)), registry)
    assert result.total == 13
    assert result.outcome == "miss"


# черты видов

def test_brave_halfling_has_advantage_vs_frightened_save(registry):
    request = make_request(
        "save", actor=make_hero("halfling"), ability="wis", tags={"vs_condition": "frightened"}
    )
    assert roll(request, two_dice(), registry).advantage == "advantage"


def test_brave_does_not_help_vs_poisoned(registry):
    request = make_request(
        "save", actor=make_hero("halfling"), ability="con", tags={"vs_condition": "poisoned"}
    )
    assert roll(request, ScriptedRng((20, 12)), registry).advantage == "normal"


def test_human_has_no_advantage_vs_frightened_save(registry):
    request = make_request(
        "save", actor=make_hero("human"), ability="wis", tags={"vs_condition": "frightened"}
    )
    assert roll(request, ScriptedRng((20, 12)), registry).advantage == "normal"


def test_dwarven_resilience_has_advantage_vs_poisoned_save(registry):
    request = make_request(
        "save", actor=make_hero("dwarf"), ability="con", tags={"vs_condition": "poisoned"}
    )
    assert roll(request, two_dice(), registry).advantage == "advantage"


def test_fey_ancestry_has_advantage_vs_charmed_save(registry):
    request = make_request(
        "save", actor=make_hero("elf"), ability="wis", tags={"vs_condition": "charmed"}
    )
    assert roll(request, two_dice(), registry).advantage == "advantage"


def test_fey_ancestry_does_not_help_without_condition_tag(registry):
    request = make_request("save", actor=make_hero("elf"), ability="wis")
    assert roll(request, ScriptedRng((20, 12)), registry).advantage == "normal"


# Bless

def bless(target):
    return ActiveEffect(
        id="bless", source="cleric1", kind="modifier",
        params={"target": target, "dice": "1d4"}, expires=Expiry(kind="concentration"),
    )


def test_bless_adds_d4_to_attack(registry):
    actor = make_creature()
    actor.active_effects.append(bless("attack_roll"))
    result = roll(make_request(actor=actor), ScriptedRng((20, 10), (4, 3)), registry)
    assert {t.source: t.value for t in result.terms}["bless"] == 3
    assert result.total == 10 + 5 + 3


def test_bless_adds_d4_to_save(registry):
    actor = make_creature()
    actor.active_effects.append(bless("saving_throw"))
    request = make_request("save", actor=actor, ability="wis")
    result = roll(request, ScriptedRng((20, 10), (4, 4)), registry)
    assert result.total == 10 + 5 + 4


def test_bless_for_attack_does_not_apply_to_save(registry):
    actor = make_creature()
    actor.active_effects.append(bless("attack_roll"))
    request = make_request("save", actor=actor, ability="wis")
    result = roll(request, ScriptedRng((20, 10)), registry)
    assert result.total == 15


def test_bless_does_not_apply_to_check(registry):
    actor = make_creature()
    actor.active_effects.append(bless("attack_roll"))
    actor.active_effects.append(bless("saving_throw"))
    request = make_request("check", actor=actor, skill="athletics")
    result = roll(request, ScriptedRng((20, 10)), registry)
    assert result.total == 15


def test_bless_die_is_visible_in_log(registry):
    actor = make_creature()
    actor.active_effects.append(bless("attack_roll"))
    result = roll(make_request(actor=actor), ScriptedRng((20, 10), (4, 3)), registry)
    assert "1d4 (3)" in result.log.text


def test_bless_stays_after_roll(registry):
    actor = make_creature()
    actor.active_effects.append(bless("attack_roll"))
    roll(make_request(actor=actor), ScriptedRng((20, 10), (4, 3)), registry)
    assert [e.id for e in actor.active_effects] == ["bless"]


# Sap и Vex

def test_sap_gives_disadvantage_on_next_attack(registry):
    actor = make_creature()
    actor.active_effects.append(
        modifier_effect("sap", target="attack_roll", mode="disadvantage", consume=True)
    )
    result = roll(make_request(actor=actor), two_dice(), registry)
    assert result.advantage == "disadvantage"


def test_sap_is_consumed_by_attack(registry):
    actor = make_creature()
    actor.active_effects.append(
        modifier_effect("sap", target="attack_roll", mode="disadvantage", consume=True)
    )
    roll(make_request(actor=actor), two_dice(), registry)
    assert actor.active_effects == []


def test_second_attack_after_sap_is_normal(registry):
    actor = make_creature()
    actor.active_effects.append(
        modifier_effect("sap", target="attack_roll", mode="disadvantage", consume=True)
    )
    roll(make_request(actor=actor), two_dice(), registry)
    result = roll(make_request(actor=actor), ScriptedRng((20, 12)), registry)
    assert result.advantage == "normal"


def test_sap_is_not_consumed_by_save(registry):
    actor = make_creature()
    actor.active_effects.append(
        modifier_effect("sap", target="attack_roll", mode="disadvantage", consume=True)
    )
    roll(make_request("save", actor=actor, ability="wis"), ScriptedRng((20, 12)), registry)
    assert len(actor.active_effects) == 1


def test_vex_gives_advantage_on_next_attack_against_same_target(registry):
    actor = make_creature()
    actor.active_effects.append(modifier_effect(
        "vex", target="attack_roll", mode="advantage", consume=True, against="g1"
    ))
    request = make_request(actor=actor, target_id="g1")
    assert roll(request, two_dice(), registry).advantage == "advantage"
    assert actor.active_effects == []


def test_vex_does_not_apply_to_another_target(registry):
    actor = make_creature()
    actor.active_effects.append(modifier_effect(
        "vex", target="attack_roll", mode="advantage", consume=True, against="g1"
    ))
    request = make_request(actor=actor, target_id="g2")
    assert roll(request, ScriptedRng((20, 12)), registry).advantage == "normal"
    assert len(actor.active_effects) == 1


# точка расширения

class FakeSource:
    id = "fake"

    def __init__(self):
        self.seen_tags = []

    def modifiers(self, request, registry):
        self.seen_tags.append(dict(request.tags))
        return [Modifier(source="fake", flat=2)]


def test_external_source_adds_flat_bonus_without_core_changes(registry):
    modifiers = default_modifier_registry()
    modifiers.register(FakeSource())
    result = roll(make_request(), ScriptedRng((20, 10)), registry, modifiers=modifiers)
    assert {t.source: t.value for t in result.terms}["fake"] == 2
    assert result.total == 10 + 5 + 2


def test_external_source_can_give_advantage(registry):
    class AdvSource:
        id = "adv"

        def modifiers(self, request, registry):
            return [Modifier(source="adv", advantage=True)]

    modifiers = default_modifier_registry()
    modifiers.register(AdvSource())
    result = roll(make_request(), two_dice(), registry, modifiers=modifiers)
    assert result.advantage == "advantage"


def test_external_source_can_force_auto_fail(registry):
    class FailSource:
        id = "fail"

        def modifiers(self, request, registry):
            return [Modifier(source="fail", auto_fail=True)]

    modifiers = default_modifier_registry()
    modifiers.register(FailSource())
    request = make_request("save", ability="wis")
    result = roll(request, ScriptedRng(), registry, modifiers=modifiers)
    assert result.outcome == "fail"


def test_external_source_does_not_leak_into_default_registry(registry):
    modifiers = default_modifier_registry()
    modifiers.register(FakeSource())
    result = roll(make_request(), ScriptedRng((20, 10)), registry)
    assert "fake" not in [t.source for t in result.terms]


def test_external_source_sees_critical_moment_tag(registry):
    source = FakeSource()
    modifiers = default_modifier_registry()
    modifiers.register(source)
    request = make_request(tags={"critical_moment": True})
    roll(request, ScriptedRng((20, 10)), registry, modifiers=modifiers)
    assert source.seen_tags[0]["critical_moment"] is True


# вложенные состояния (D5)

def test_ranged_attack_on_unconscious_target_is_normal(registry):
    # без сознания: преимущество, но лежит и атака дальняя: помеха -- вместе обычный бросок
    request = make_request(target=make_creature("unconscious"), tags={"melee": False})
    rng = ScriptedRng((20, 12))
    result = roll(request, rng, registry)
    assert result.advantage == "normal"
    assert rng.rolls == []


@pytest.mark.parametrize("condition", ["unconscious", "paralyzed", "stunned", "petrified"])
def test_incapacitating_condition_gives_disadvantage_on_initiative(registry, condition):
    request = make_request("initiative", actor=make_creature(condition), dc=None, bonus=2)
    assert roll(request, two_dice(), registry).advantage == "disadvantage"


def test_incapacitated_gives_disadvantage_on_initiative(registry):
    request = make_request("initiative", actor=make_creature("incapacitated"), dc=None)
    assert roll(request, two_dice(), registry).advantage == "disadvantage"


def test_invisible_gives_advantage_on_initiative(registry):
    request = make_request("initiative", actor=make_creature("invisible"), dc=None)
    assert roll(request, two_dice(), registry).advantage == "advantage"


def test_incapacitated_and_invisible_cancel_out_on_initiative(registry):
    request = make_request(
        "initiative", actor=make_creature("invisible", "incapacitated"), dc=None
    )
    assert roll(request, ScriptedRng((20, 12)), registry).advantage == "normal"


def test_incapacitated_does_not_affect_attack(registry):
    request = make_request(actor=make_creature("incapacitated"))
    assert roll(request, ScriptedRng((20, 12)), registry).advantage == "normal"


# схваченный (D5)

def make_grappled(grappler="g1"):
    return CreatureState(
        hp_current=7, hp_max=7, conditions=[AppliedCondition(id="grappled", source=grappler)]
    )


def test_grappled_actor_attacks_other_target_with_disadvantage(registry):
    request = make_request(actor=make_grappled("g1"), target_id="g2")
    assert roll(request, two_dice(), registry).advantage == "disadvantage"


def test_grappled_actor_attacks_grappler_normally(registry):
    request = make_request(actor=make_grappled("g1"), target_id="g1")
    assert roll(request, ScriptedRng((20, 12)), registry).advantage == "normal"


def test_grappled_does_not_affect_save(registry):
    request = make_request("save", actor=make_grappled("g1"), ability="wis")
    assert roll(request, ScriptedRng((20, 12)), registry).advantage == "normal"


# эффект со стороны цели (D1)

def test_target_side_effect_applies_to_attack_against_holder(registry):
    # Dodge: помеха на атаки по цели
    target = make_creature()
    target.active_effects.append(
        modifier_effect("dodge", target="attack_roll", mode="disadvantage", side="target")
    )
    result = roll(make_request(target=target), two_dice(), registry)
    assert result.advantage == "disadvantage"


def test_target_side_effect_does_not_apply_to_holders_own_attack(registry):
    holder = make_creature()
    holder.active_effects.append(
        modifier_effect("dodge", target="attack_roll", mode="disadvantage", side="target")
    )
    result = roll(make_request(actor=holder), ScriptedRng((20, 12)), registry)
    assert result.advantage == "normal"


def test_actor_side_effect_on_target_does_not_apply_to_attacker(registry):
    target = make_creature()
    target.active_effects.append(
        modifier_effect("bless", target="attack_roll", mode="advantage")
    )
    result = roll(make_request(target=target), ScriptedRng((20, 12)), registry)
    assert result.advantage == "normal"


def test_target_side_effect_without_target_is_ignored(registry):
    result = roll(make_request(), ScriptedRng((20, 12)), registry)
    assert result.advantage == "normal"


# Bless на спасбросок от смерти (B5)

def test_bless_adds_d4_to_death_save(registry):
    actor = make_creature()
    actor.active_effects.append(bless("saving_throw"))
    request = make_request("death_save", actor=actor, dc=None, bonus=0)
    result = roll(request, ScriptedRng((20, 7), (4, 3)), registry)
    assert result.total == 7 + 3


def test_bless_for_attack_does_not_apply_to_death_save(registry):
    actor = make_creature()
    actor.active_effects.append(bless("attack_roll"))
    request = make_request("death_save", actor=actor, dc=None, bonus=0)
    assert roll(request, ScriptedRng((20, 7)), registry).total == 7


# dc_bonus и crit_min (D1)

class CoverSource:
    id = "cover"

    def modifiers(self, request, registry):
        return [Modifier(source="cover", dc_bonus=2)]


def cover_modifiers():
    modifiers = default_modifier_registry()
    modifiers.register(CoverSource())
    return modifiers


def test_dc_bonus_is_shown_in_log(registry):
    result = roll(make_request(), ScriptedRng((20, 12)), registry, modifiers=cover_modifiers())
    assert "против КД 17" in result.log.text


def test_dc_bonus_makes_hit_a_miss(registry):
    # 12 + 5 = 17 против КД 15 + 2 = 17 -- попадание; 11 + 5 = 16 < 17 -- промах
    hit = roll(make_request(), ScriptedRng((20, 12)), registry, modifiers=cover_modifiers())
    miss = roll(make_request(), ScriptedRng((20, 11)), registry, modifiers=cover_modifiers())
    assert hit.outcome == "hit"
    assert miss.outcome == "miss"


def test_dc_bonus_applies_to_save_dc(registry):
    request = make_request("save", ability="dex")
    result = roll(request, ScriptedRng((20, 10)), registry, modifiers=cover_modifiers())
    assert result.outcome == "fail"
    assert "СЛ 17" in result.log.text


def test_dc_bonus_sums_over_sources(registry):
    modifiers = cover_modifiers()
    modifiers.register(CoverSource())
    result = roll(make_request(), ScriptedRng((20, 12)), registry, modifiers=modifiers)
    assert "против КД 19" in result.log.text


def test_no_dc_bonus_by_default(registry):
    result = roll(make_request(), ScriptedRng((20, 12)), registry)
    assert "против КД 15" in result.log.text


def crit_modifiers(*values):
    class CritSource:
        id = "crit"

        def modifiers(self, request, registry):
            return [Modifier(source=f"crit{v}", crit_min=v) for v in values]

    modifiers = default_modifier_registry()
    modifiers.register(CritSource())
    return modifiers


def test_crit_min_19_makes_natural_19_a_crit(registry):
    request = make_request(bonus=-10)
    result = roll(request, ScriptedRng((20, 19)), registry, modifiers=crit_modifiers(19))
    assert result.outcome == "crit"


def test_natural_19_is_not_crit_by_default(registry):
    result = roll(make_request(bonus=0), ScriptedRng((20, 19)), registry)
    assert result.outcome == "hit"


def test_crit_min_does_not_make_lower_natural_a_crit(registry):
    result = roll(make_request(), ScriptedRng((20, 18)), registry, modifiers=crit_modifiers(19))
    assert result.outcome == "hit"


def test_crit_min_takes_lowest_of_sources(registry):
    result = roll(
        make_request(), ScriptedRng((20, 18)), registry, modifiers=crit_modifiers(19, 18)
    )
    assert result.outcome == "crit"


def test_crit_min_does_not_affect_save_outcome(registry):
    request = make_request("save", ability="dex")
    result = roll(request, ScriptedRng((20, 19)), registry, modifiers=crit_modifiers(19))
    assert result.outcome == "success"


# now_s (D1)

def test_now_s_is_none_by_default():
    assert make_request().now_s is None


def test_external_source_sees_now_s(registry):
    seen = []

    class TimeSource:
        id = "time"

        def modifiers(self, request, registry):
            seen.append(request.now_s)
            return []

    modifiers = default_modifier_registry()
    modifiers.register(TimeSource())
    roll(make_request(now_s=1234), ScriptedRng((20, 10)), registry, modifiers=modifiers)
    assert seen == [1234]


# У1 П1: target "ability_check", фильтр по часам, подпись «ухожен»

def groomed(expires_at=None, ability="cha"):
    params = {"target": "ability_check", "dice": "1d4", "consume": True}
    if ability is not None:
        params["ability"] = ability
    expires = None if expires_at is None else Expiry(kind="seconds", value=expires_at)
    return ActiveEffect(id="groomed", source="service:tobb", kind="modifier", params=params,
                        expires=expires)


def check_request(actor, ability="cha", **kwargs):
    return make_request("check", actor=actor, ability=ability, skill="persuasion", **kwargs)


def test_ability_check_effect_adds_die_to_check_of_that_ability(registry):
    actor = make_creature()
    actor.active_effects.append(groomed())
    result = roll(check_request(actor), ScriptedRng((20, 10), (4, 3)), registry)
    assert result.total == 10 + 5 + 3


def test_ability_check_effect_label_is_groomed_word(registry):
    actor = make_creature()
    actor.active_effects.append(groomed())
    result = roll(check_request(actor), ScriptedRng((20, 10), (4, 3)), registry)
    assert "1d4 (3)" in result.log.text
    assert "ухожен" in result.log.text


def test_ability_check_effect_is_consumed_by_the_check(registry):
    actor = make_creature()
    actor.active_effects.append(groomed())
    roll(check_request(actor), ScriptedRng((20, 10), (4, 3)), registry)
    assert actor.active_effects == []


def test_ability_check_effect_ignores_other_ability(registry):
    actor = make_creature()
    actor.active_effects.append(groomed())
    result = roll(check_request(actor, ability="str"), ScriptedRng((20, 10)), registry)
    assert result.total == 15
    assert len(actor.active_effects) == 1


def test_ability_check_effect_ignores_attack_and_save(registry):
    actor = make_creature()
    actor.active_effects.append(groomed())
    roll(make_request(actor=actor), ScriptedRng((20, 10)), registry)
    roll(make_request("save", actor=actor, ability="cha"), ScriptedRng((20, 10)), registry)
    assert len(actor.active_effects) == 1


def test_ability_check_effect_without_ability_param_applies_to_any_check(registry):
    actor = make_creature()
    actor.active_effects.append(groomed(ability=None))
    result = roll(check_request(actor, ability="str"), ScriptedRng((20, 10), (4, 2)), registry)
    assert result.total == 10 + 5 + 2


def test_expired_seconds_effect_gives_no_modifier(registry):
    actor = make_creature()
    actor.active_effects.append(groomed(expires_at=1000))
    result = roll(check_request(actor, now_s=1000), ScriptedRng((20, 10)), registry)
    assert result.total == 15
    assert len(actor.active_effects) == 1


def test_not_yet_expired_seconds_effect_applies(registry):
    actor = make_creature()
    actor.active_effects.append(groomed(expires_at=1000))
    result = roll(check_request(actor, now_s=999), ScriptedRng((20, 10), (4, 3)), registry)
    assert result.total == 18


def test_seconds_effect_without_now_s_applies_as_before(registry):
    actor = make_creature()
    actor.active_effects.append(groomed(expires_at=1000))
    result = roll(check_request(actor), ScriptedRng((20, 10), (4, 3)), registry)
    assert result.total == 18


def test_expired_effect_on_target_gives_no_modifier(registry):
    target = make_creature()
    target.active_effects.append(
        ActiveEffect(
            id="dodge", source="x", kind="modifier",
            params={"target": "attack_roll", "mode": "disadvantage", "side": "target"},
            expires=Expiry(kind="seconds", value=50),
        )
    )
    result = roll(make_request(target=target, now_s=60), two_dice(), registry)
    assert result.advantage == "normal"


def test_effect_without_expiry_applies_with_now_s(registry):
    actor = make_creature()
    actor.active_effects.append(
        modifier_effect("sap", target="attack_roll", mode="disadvantage", consume=True)
    )
    result = roll(make_request(actor=actor, now_s=10**6), two_dice(), registry)
    assert result.advantage == "disadvantage"
