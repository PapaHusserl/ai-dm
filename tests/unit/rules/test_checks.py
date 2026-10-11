# Ожидаемый API: ai_dm.rules.checks (hero: HeroState; registry: ContentRegistry; rng: Rng)
#   dc_for_category(category: str, registry) -> int
#       таблица "dc" реестра: very_easy 5, easy 10, medium 15, hard 20, very_hard 25,
#       nearly_impossible 30; неизвестная категория -> ValueError
#   skill_check(hero, registry, rng, skill, category=None, *, dc=None, tags=None, decisions=None,
#               modifiers=None, rerollers=None)
#       -> RollResult (kind="check") -- через roll_pipeline.roll; бонус = derived.skill_bonus;
#       СЛ -- по категории либо явным dc (ровно одно из двух, иначе ValueError);
#       ошибка категории -- до броска (rng не трогается)
#   saving_throw(hero, registry, rng, ability, category=None, *, dc=None, tags=None, decisions=None,
#                modifiers=None, rerollers=None)
#       -> RollResult (kind="save"); бонус = derived.saving_throw_bonus
#       modifiers / rerollers (B7) пробрасываются в roll_pipeline.roll как есть
#   passive_check(hero, registry, skill) -> int   -- 10 + skill_bonus(hero, registry, skill)
# Состояния и черты (отравлен, истощение) подхватывает конвейер, здесь проверяется только стык.
import pytest

from ai_dm.core.rng import Rng
from ai_dm.rules.checks import dc_for_category, saving_throw, skill_check
from ai_dm.rules.derived import skill_bonus
from ai_dm.rules.modifiers import Modifier, ModifierRegistry
from ai_dm.state.creature import AppliedCondition, CreatureState
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState


class ScriptedRng(Rng):
    def __init__(self, *rolls):
        super().__init__(1)
        self.rolls = list(rolls)

    def randbelow(self, n):
        sides, face = self.rolls.pop(0)
        assert sides == n
        return face - 1


def make_hero(species="human", **creature):
    # человек-воин: СИЛ 17, ТЕЛ 15; атлетика с мастерством (+5), спасбросок ТЕЛ +4, ИНТ -1
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
        skill_proficiencies=["athletics", "intimidation", "perception", "survival"],
    )
    return HeroState(
        id="h1", ordinal=1, name="Арн", sheet=sheet,
        creature=CreatureState(hp_current=12, hp_max=12, **creature),
    )


# категории -> СЛ

@pytest.mark.parametrize(
    "category, dc",
    [
        ("very_easy", 5), ("easy", 10), ("medium", 15),
        ("hard", 20), ("very_hard", 25), ("nearly_impossible", 30),
    ],
)
def test_dc_for_category(registry, category, dc):
    assert dc_for_category(category, registry) == dc


def test_unknown_category_is_error(registry):
    with pytest.raises(ValueError):
        dc_for_category("trivial", registry)


# проверки навыков

def test_skill_check_adds_skill_bonus(registry):
    result = skill_check(make_hero(), registry, ScriptedRng((20, 10)), "athletics", "medium")
    assert result.kind == "check"
    assert result.total == 10 + skill_bonus(make_hero(), registry, "athletics")


def test_skill_check_success_when_total_equals_dc(registry):
    result = skill_check(make_hero(), registry, ScriptedRng((20, 10)), "athletics", "medium")
    assert result.dc == 15
    assert result.outcome == "success"


def test_skill_check_fail_below_dc(registry):
    result = skill_check(make_hero(), registry, ScriptedRng((20, 9)), "athletics", "medium")
    assert result.outcome == "fail"


def test_skill_check_dc_comes_from_category(registry):
    result = skill_check(make_hero(), registry, ScriptedRng((20, 10)), "athletics", "very_hard")
    assert result.dc == 25


def test_skill_check_with_explicit_dc(registry):
    result = skill_check(make_hero(), registry, ScriptedRng((20, 10)), "athletics", dc=12)
    assert result.dc == 12
    assert result.outcome == "success"


def test_skill_check_without_dc_and_category_is_error(registry):
    rng = ScriptedRng()
    with pytest.raises(ValueError):
        skill_check(make_hero(), registry, rng, "athletics")


def test_skill_check_with_both_dc_and_category_is_error(registry):
    with pytest.raises(ValueError):
        skill_check(make_hero(), registry, ScriptedRng(), "athletics", "easy", dc=12)


def test_skill_check_unknown_category_does_not_touch_rng(registry):
    rng = ScriptedRng()
    with pytest.raises(ValueError):
        skill_check(make_hero(), registry, rng, "athletics", "trivial")


def test_skill_check_log_has_dc(registry):
    result = skill_check(make_hero(), registry, ScriptedRng((20, 10)), "athletics", "medium")
    assert "d20 (10)" in result.log.text
    assert "СЛ 15" in result.log.text


def test_skill_check_is_affected_by_exhaustion(registry):
    hero = make_hero(exhaustion=1)
    result = skill_check(hero, registry, ScriptedRng((20, 10)), "athletics", "medium")
    assert result.total == 13
    assert result.outcome == "fail"


def test_skill_check_poisoned_has_disadvantage(registry):
    hero = make_hero(conditions=[AppliedCondition(id="poisoned")])
    rng = ScriptedRng((20, 15), (20, 4))
    result = skill_check(hero, registry, rng, "athletics", "medium")
    assert result.natural == 4


# спасброски

def test_saving_throw_adds_save_bonus_with_proficiency(registry):
    result = saving_throw(make_hero(), registry, ScriptedRng((20, 10)), "con", "medium")
    assert result.kind == "save"
    assert result.total == 10 + 4


def test_saving_throw_without_proficiency(registry):
    result = saving_throw(make_hero(), registry, ScriptedRng((20, 10)), "int", "easy")
    assert result.total == 10 - 1
    assert result.outcome == "fail"


def test_saving_throw_success(registry):
    result = saving_throw(make_hero(), registry, ScriptedRng((20, 11)), "con", "medium")
    assert result.outcome == "success"


def test_saving_throw_with_explicit_dc(registry):
    result = saving_throw(make_hero(), registry, ScriptedRng((20, 9)), "con", dc=13)
    assert result.dc == 13
    assert result.outcome == "success"


def test_saving_throw_unknown_category_is_error(registry):
    with pytest.raises(ValueError):
        saving_throw(make_hero(), registry, ScriptedRng(), "con", "trivial")


# modifiers= и rerollers= (B7)

class FlatSource:
    id = "flat"

    def modifiers(self, request, registry):
        return [Modifier(source="flat", flat=3)]


def flat_modifiers():
    modifiers = ModifierRegistry()
    modifiers.register(FlatSource())
    return modifiers


def test_skill_check_passes_modifiers_to_roll(registry):
    result = skill_check(
        make_hero(), registry, ScriptedRng((20, 10)), "athletics", "medium",
        modifiers=flat_modifiers(),
    )
    assert "flat" in [t.source for t in result.terms]
    assert result.total == 10 + skill_bonus(make_hero(), registry, "athletics") + 3


def test_saving_throw_passes_modifiers_to_roll(registry):
    result = saving_throw(
        make_hero(), registry, ScriptedRng((20, 10)), "con", "medium", modifiers=flat_modifiers()
    )
    assert result.total == 10 + 4 + 3


def test_skill_check_custom_modifiers_replace_default_sources(registry):
    # свой реестр без источников состояний: отравление не даёт помехи
    hero = make_hero(conditions=[AppliedCondition(id="poisoned")])
    result = skill_check(
        hero, registry, ScriptedRng((20, 10)), "athletics", "medium", modifiers=ModifierRegistry()
    )
    assert result.advantage == "normal"


def test_skill_check_passes_empty_rerollers_to_roll(registry):
    hero = make_hero("halfling")
    result = skill_check(
        hero, registry, ScriptedRng((20, 1)), "athletics", "medium", rerollers=[]
    )
    assert result.natural == 1
    assert result.rerolls == []


def test_saving_throw_passes_empty_rerollers_to_roll(registry):
    hero = make_hero("halfling")
    result = saving_throw(hero, registry, ScriptedRng((20, 1)), "con", "medium", rerollers=[])
    assert result.natural == 1
    assert result.rerolls == []


def test_skill_check_luck_works_by_default(registry):
    hero = make_hero("halfling")
    result = skill_check(hero, registry, ScriptedRng((20, 1), (20, 14)), "athletics", "medium")
    assert result.natural == 14
