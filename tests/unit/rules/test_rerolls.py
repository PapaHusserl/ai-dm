# Ожидаемый API: перебросы в ai_dm.rules.roll_pipeline.roll (контракт RollRequest/RollResult --
# в test_roll_pipeline.py). Reroller-ы идут после броска и бонусных кубиков в фиксированном
# порядке:
#   1. Luck (черта вида halfling): на d20-тесте (attack/save/check/initiative) оставленная
#      кость = 1 -> один переброс, новое значение обязательно; повторная 1 не перебрасывается
#   2. героическое вдохновение: hero.heroic_inspiration == True, d20-тест, передан decisions:
#      decisions.choose(options, ctx) -> str; options == ["reroll", "keep"],
#      ctx["natural"] -- оставленная кость на момент вопроса. "reroll" -> новая кость заменяет
#      прежнюю (даже если хуже), флаг героя снят; "keep" -> без переброса, флаг остаётся.
#      Флаг False, decisions=None или актёр -- CreatureState: вопрос не задаётся
#   3. Savage Attacker (черта "savage_attacker" в sheet.feats): kind="damage" с tags["weapon"]=True:
#      кубики урона бросаются дважды (весь набор), берётся больший набор. Раз в ход:
#      tags["savage_attacker_used"]=True -- бросок один. Не оружие -- один бросок
#   result.rerolls -- список сработавших перебросов по порядку; result.d20_rolls -- все d20,
#   включая перебросы; в строке лога видны оба значения.
#   Переброс при adv/dis (B1): хранится пара костей; переброс заменяет ОДНУ кость пары (ту, что дала
#   natural), natural пересчитывается тем же max/min (при adv -- max, при dis -- min).
#   d20_rolls по-прежнему содержит все выпавшие по порядку (пара + новые кости).
#   Спасбросок от смерти (kind="death_save") -- тоже d20-тест: Luck и вдохновение работают (B5).
#   Лог перебросов (D8): "d20 (1 → удача 12)", "d20 (4 → вдохновение 15)";
#   при adv/dis: "d20 (1, 5 → удача 18 → 5)".
#   Лог урона (B6): "Урон: 1d8 (5) + 3 = 8"; крит -- "Урон: 2d8 (3, 7) + 3 = 13 (крит, кубики ×2)";
#   Savage Attacker -- "Урон: 1d8 (2 | 6 → 6) + 3 = 9 [Свирепый атакующий]" (набор кубиков
#   до | и после, затем выбранный).
#   rerollers=None (D1): список перебросов (по умолчанию [luck, heroic_inspiration]), функции
#   (request, kept_pair, rng, registry, decisions) -> reroll_id | None; rerollers=[] -- без них.
from ai_dm.core.rng import Rng
from ai_dm.rules.roll_pipeline import RollRequest, roll
from ai_dm.state.creature import CreatureState
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState


class ScriptedRng(Rng):
    def __init__(self, *rolls):
        super().__init__(1)
        self.rolls = list(rolls)

    def randbelow(self, n):
        sides, face = self.rolls.pop(0)
        assert sides == n
        return face - 1


class ScriptedProvider:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.asked = []

    def choose(self, options, ctx):
        self.asked.append((list(options), dict(ctx)))
        return self.answers.pop(0)


def make_hero(species="human", feats=(), heroic_inspiration=False):
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
        feats=list(feats),
    )
    return HeroState(
        id="h1", ordinal=1, name="Арн", sheet=sheet,
        creature=CreatureState(hp_current=12, hp_max=12),
        heroic_inspiration=heroic_inspiration,
    )


def make_request(hero, kind="attack", **kwargs):
    fields = {"kind": kind, "actor": hero, "bonus": 5, "dc": 15}
    fields.update(kwargs)
    return RollRequest(**fields)


def damage_request(hero, dice="1d8", **tags):
    return make_request(hero, "damage", dc=None, bonus=3, dice=dice, tags={"weapon": True, **tags})


# Luck

def test_luck_rerolls_natural_1(registry):
    request = make_request(make_hero("halfling"))
    result = roll(request, ScriptedRng((20, 1), (20, 12)), registry)
    assert result.natural == 12
    assert result.total == 17
    assert result.rerolls == ["luck"]


def test_luck_log_shows_both_values(registry):
    request = make_request(make_hero("halfling"))
    result = roll(request, ScriptedRng((20, 1), (20, 12)), registry)
    assert result.d20_rolls == [1, 12]
    assert "1" in result.log.text
    assert "12" in result.log.text


def test_luck_new_roll_is_used_even_if_one_again(registry):
    request = make_request(make_hero("halfling"))
    result = roll(request, ScriptedRng((20, 1), (20, 1)), registry)
    assert result.natural == 1
    assert result.d20_rolls == [1, 1]


def test_luck_does_not_trigger_on_2(registry):
    rng = ScriptedRng((20, 2))
    result = roll(make_request(make_hero("halfling")), rng, registry)
    assert result.rerolls == []
    assert result.natural == 2


def test_luck_works_on_save(registry):
    request = make_request(make_hero("halfling"), "save", ability="wis")
    result = roll(request, ScriptedRng((20, 1), (20, 14)), registry)
    assert result.natural == 14


def test_luck_works_on_check(registry):
    request = make_request(make_hero("halfling"), "check", skill="athletics")
    result = roll(request, ScriptedRng((20, 1), (20, 14)), registry)
    assert result.natural == 14


def test_human_does_not_get_luck(registry):
    result = roll(make_request(make_hero("human")), ScriptedRng((20, 1)), registry)
    assert result.natural == 1
    assert result.rerolls == []


def test_luck_does_not_reroll_damage_die(registry):
    hero = make_hero("halfling")
    request = make_request(hero, "damage", dc=None, bonus=0, dice="1d8", tags={"weapon": True})
    result = roll(request, ScriptedRng((8, 1)), registry)
    assert result.rerolls == []


# Savage Attacker

def test_savage_attacker_takes_higher_of_two_damage_rolls(registry):
    hero = make_hero(feats=["savage_attacker"])
    result = roll(damage_request(hero), ScriptedRng((8, 2), (8, 6)), registry)
    assert result.total == 6 + 3
    assert result.rerolls == ["savage_attacker"]


def test_savage_attacker_keeps_first_roll_when_it_is_higher(registry):
    hero = make_hero(feats=["savage_attacker"])
    result = roll(damage_request(hero), ScriptedRng((8, 7), (8, 1)), registry)
    assert result.total == 7 + 3


def test_savage_attacker_compares_whole_dice_sets(registry):
    hero = make_hero(feats=["savage_attacker"])
    rng = ScriptedRng((6, 1), (6, 2), (6, 5), (6, 6))
    result = roll(damage_request(hero, dice="2d6"), rng, registry)
    assert result.total == 11 + 3


def test_savage_attacker_once_per_turn(registry):
    hero = make_hero(feats=["savage_attacker"])
    rng = ScriptedRng((8, 2))
    result = roll(damage_request(hero, savage_attacker_used=True), rng, registry)
    assert result.total == 2 + 3
    assert result.rerolls == []


def test_savage_attacker_not_for_spell_damage(registry):
    hero = make_hero(feats=["savage_attacker"])
    request = make_request(hero, "damage", dc=None, bonus=0, dice="1d8", tags={"weapon": False})
    result = roll(request, ScriptedRng((8, 2)), registry)
    assert result.rerolls == []


def test_no_savage_attacker_without_feat(registry):
    result = roll(damage_request(make_hero()), ScriptedRng((8, 2)), registry)
    assert result.total == 2 + 3
    assert result.rerolls == []


# героическое вдохновение

def test_inspiration_refused_keeps_roll_and_flag(registry):
    hero = make_hero(heroic_inspiration=True)
    provider = ScriptedProvider("keep")
    result = roll(make_request(hero), ScriptedRng((20, 5)), registry, decisions=provider)
    assert result.natural == 5
    assert result.rerolls == []
    assert hero.heroic_inspiration is True


def test_inspiration_accepted_rerolls_and_clears_flag(registry):
    hero = make_hero(heroic_inspiration=True)
    provider = ScriptedProvider("reroll")
    result = roll(make_request(hero), ScriptedRng((20, 5), (20, 17)), registry, decisions=provider)
    assert result.natural == 17
    assert result.rerolls == ["heroic_inspiration"]
    assert hero.heroic_inspiration is False


def test_inspiration_new_roll_is_used_even_if_worse(registry):
    hero = make_hero(heroic_inspiration=True)
    provider = ScriptedProvider("reroll")
    result = roll(make_request(hero), ScriptedRng((20, 15), (20, 2)), registry, decisions=provider)
    assert result.natural == 2


def test_inspiration_log_shows_both_values(registry):
    hero = make_hero(heroic_inspiration=True)
    provider = ScriptedProvider("reroll")
    result = roll(make_request(hero), ScriptedRng((20, 5), (20, 17)), registry, decisions=provider)
    assert result.d20_rolls == [5, 17]
    assert "5" in result.log.text
    assert "17" in result.log.text


def test_inspiration_question_offers_reroll_or_keep(registry):
    hero = make_hero(heroic_inspiration=True)
    provider = ScriptedProvider("keep")
    roll(make_request(hero), ScriptedRng((20, 5)), registry, decisions=provider)
    assert provider.asked[0][0] == ["reroll", "keep"]
    assert provider.asked[0][1]["natural"] == 5


def test_inspiration_not_asked_without_flag(registry):
    provider = ScriptedProvider()
    roll(make_request(make_hero()), ScriptedRng((20, 5)), registry, decisions=provider)
    assert provider.asked == []


def test_inspiration_without_provider_is_not_used(registry):
    hero = make_hero(heroic_inspiration=True)
    result = roll(make_request(hero), ScriptedRng((20, 5)), registry)
    assert result.rerolls == []
    assert hero.heroic_inspiration is True


def test_inspiration_works_on_save_and_check(registry):
    for kind, extra in [("save", {"ability": "wis"}), ("check", {"skill": "athletics"})]:
        hero = make_hero(heroic_inspiration=True)
        provider = ScriptedProvider("reroll")
        request = make_request(hero, kind, **extra)
        result = roll(request, ScriptedRng((20, 5), (20, 17)), registry, decisions=provider)
        assert result.natural == 17


def test_npc_actor_is_never_offered_inspiration(registry):
    provider = ScriptedProvider()
    request = make_request(CreatureState(hp_current=7, hp_max=7))
    roll(request, ScriptedRng((20, 5)), registry, decisions=provider)
    assert provider.asked == []


# порядок

def test_luck_goes_before_inspiration(registry):
    hero = make_hero("halfling", heroic_inspiration=True)
    provider = ScriptedProvider("reroll")
    rng = ScriptedRng((20, 1), (20, 2), (20, 18))
    result = roll(make_request(hero), rng, registry, decisions=provider)
    assert provider.asked[0][1]["natural"] == 2
    assert result.rerolls == ["luck", "heroic_inspiration"]
    assert result.d20_rolls == [1, 2, 18]
    assert result.natural == 18


def test_inspiration_refused_after_luck_keeps_luck_roll(registry):
    hero = make_hero("halfling", heroic_inspiration=True)
    provider = ScriptedProvider("keep")
    result = roll(make_request(hero), ScriptedRng((20, 1), (20, 9)), registry, decisions=provider)
    assert result.natural == 9
    assert result.rerolls == ["luck"]
    assert hero.heroic_inspiration is True


# детерминизм

def test_rerolls_are_deterministic_by_seed(registry):
    results = []
    for _ in range(2):
        hero = make_hero("halfling", heroic_inspiration=True)
        provider = ScriptedProvider("reroll")
        results.append(roll(make_request(hero), Rng(3), registry, decisions=provider))
    assert results[0] == results[1]


# Luck при преимуществе и помехе (B1)

def test_luck_with_advantage_replaces_one_die_of_pair(registry):
    request = make_request(make_hero("halfling"), base_adv="advantage")
    result = roll(request, ScriptedRng((20, 1), (20, 1), (20, 18)), registry)
    assert result.natural == 18
    assert result.d20_rolls == [1, 1, 18]
    assert result.rerolls == ["luck"]


def test_luck_with_advantage_new_one_stays_one(registry):
    request = make_request(make_hero("halfling"), base_adv="advantage")
    result = roll(request, ScriptedRng((20, 1), (20, 1), (20, 1)), registry)
    assert result.natural == 1


def test_luck_with_advantage_not_triggered_when_other_die_is_higher(registry):
    request = make_request(make_hero("halfling"), base_adv="advantage")
    result = roll(request, ScriptedRng((20, 1), (20, 9)), registry)
    assert result.natural == 9
    assert result.rerolls == []


def test_luck_with_disadvantage_keeps_other_die_when_reroll_is_higher(registry):
    request = make_request(make_hero("halfling"), base_adv="disadvantage")
    result = roll(request, ScriptedRng((20, 1), (20, 5), (20, 18)), registry)
    assert result.natural == 5
    assert result.d20_rolls == [1, 5, 18]
    assert result.total == 5 + 5
    assert result.rerolls == ["luck"]


def test_luck_with_disadvantage_takes_new_die_when_it_is_lower_than_other(registry):
    request = make_request(make_hero("halfling"), base_adv="disadvantage")
    result = roll(request, ScriptedRng((20, 1), (20, 5), (20, 3)), registry)
    assert result.natural == 3


def test_luck_with_disadvantage_log_shows_pair_reroll_and_kept(registry):
    request = make_request(make_hero("halfling"), base_adv="disadvantage")
    result = roll(request, ScriptedRng((20, 1), (20, 5), (20, 18)), registry)
    assert "d20 (1, 5 → удача 18 → 5)" in result.log.text


# вдохновение при преимуществе и помехе (B1)

def test_inspiration_with_advantage_replaces_the_kept_die(registry):
    hero = make_hero(heroic_inspiration=True)
    provider = ScriptedProvider("reroll")
    request = make_request(hero, base_adv="advantage")
    result = roll(request, ScriptedRng((20, 4), (20, 9), (20, 3)), registry, decisions=provider)
    assert provider.asked[0][1]["natural"] == 9
    assert result.natural == 4
    assert result.d20_rolls == [4, 9, 3]
    assert result.rerolls == ["heroic_inspiration"]
    assert hero.heroic_inspiration is False


def test_inspiration_with_advantage_new_die_can_be_higher(registry):
    hero = make_hero(heroic_inspiration=True)
    provider = ScriptedProvider("reroll")
    request = make_request(hero, base_adv="advantage")
    result = roll(request, ScriptedRng((20, 4), (20, 9), (20, 15)), registry, decisions=provider)
    assert result.natural == 15


def test_inspiration_with_advantage_refused_keeps_pair(registry):
    hero = make_hero(heroic_inspiration=True)
    provider = ScriptedProvider("keep")
    request = make_request(hero, base_adv="advantage")
    result = roll(request, ScriptedRng((20, 4), (20, 9)), registry, decisions=provider)
    assert result.natural == 9
    assert hero.heroic_inspiration is True


def test_inspiration_with_disadvantage_replaces_the_kept_die(registry):
    hero = make_hero(heroic_inspiration=True)
    provider = ScriptedProvider("reroll")
    request = make_request(hero, base_adv="disadvantage")
    result = roll(request, ScriptedRng((20, 4), (20, 9), (20, 15)), registry, decisions=provider)
    assert provider.asked[0][1]["natural"] == 4
    assert result.natural == 9
    assert result.d20_rolls == [4, 9, 15]
    assert result.rerolls == ["heroic_inspiration"]


def test_inspiration_with_disadvantage_new_die_can_be_lower(registry):
    hero = make_hero(heroic_inspiration=True)
    provider = ScriptedProvider("reroll")
    request = make_request(hero, base_adv="disadvantage")
    result = roll(request, ScriptedRng((20, 4), (20, 9), (20, 2)), registry, decisions=provider)
    assert result.natural == 2


# логи перебросов (D8)

def test_luck_log_format(registry):
    request = make_request(make_hero("halfling"))
    result = roll(request, ScriptedRng((20, 1), (20, 12)), registry)
    assert "d20 (1 → удача 12)" in result.log.text


def test_inspiration_log_format(registry):
    hero = make_hero(heroic_inspiration=True)
    provider = ScriptedProvider("reroll")
    result = roll(make_request(hero), ScriptedRng((20, 4), (20, 15)), registry, decisions=provider)
    assert "d20 (4 → вдохновение 15)" in result.log.text


# спасбросок от смерти -- d20-тест (B5)

def test_luck_works_on_death_save(registry):
    request = make_request(make_hero("halfling"), "death_save", dc=None, bonus=0)
    result = roll(request, ScriptedRng((20, 1), (20, 12)), registry)
    assert result.natural == 12
    assert result.rerolls == ["luck"]


def test_inspiration_works_on_death_save(registry):
    hero = make_hero(heroic_inspiration=True)
    provider = ScriptedProvider("reroll")
    request = make_request(hero, "death_save", dc=None, bonus=0)
    result = roll(request, ScriptedRng((20, 4), (20, 15)), registry, decisions=provider)
    assert result.natural == 15
    assert result.rerolls == ["heroic_inspiration"]


# rerollers= (D1)

def test_empty_rerollers_disables_luck(registry):
    request = make_request(make_hero("halfling"))
    result = roll(request, ScriptedRng((20, 1)), registry, rerollers=[])
    assert result.natural == 1
    assert result.rerolls == []


def test_empty_rerollers_disables_inspiration(registry):
    hero = make_hero(heroic_inspiration=True)
    provider = ScriptedProvider()
    request = make_request(hero)
    result = roll(request, ScriptedRng((20, 4)), registry, decisions=provider, rerollers=[])
    assert provider.asked == []
    assert result.rerolls == []


def test_custom_reroller_is_called_and_its_id_is_recorded(registry):
    seen = []

    def custom(request, kept_pair, rng, registry, decisions):
        seen.append(request.kind)
        return "custom"

    result = roll(make_request(make_hero()), ScriptedRng((20, 7)), registry, rerollers=[custom])
    assert seen == ["attack"]
    assert result.rerolls == ["custom"]


def test_custom_reroller_returning_none_records_nothing(registry):
    def custom(request, kept_pair, rng, registry, decisions):
        return None

    result = roll(make_request(make_hero()), ScriptedRng((20, 7)), registry, rerollers=[custom])
    assert result.rerolls == []


# лог урона (B6)

def test_damage_log_shows_dice_faces(registry):
    result = roll(damage_request(make_hero()), ScriptedRng((8, 5)), registry)
    assert result.log.text == "Урон: 1d8 (5) + 3 = 8"


def test_damage_log_crit_shows_doubled_dice(registry):
    request = damage_request(make_hero(), crit=True)
    result = roll(request, ScriptedRng((8, 3), (8, 7)), registry)
    assert result.total == 13
    assert result.log.text == "Урон: 2d8 (3, 7) + 3 = 13 (крит, кубики ×2)"


def test_damage_log_savage_attacker_shows_both_sets_and_marker(registry):
    hero = make_hero(feats=["savage_attacker"])
    result = roll(damage_request(hero), ScriptedRng((8, 2), (8, 6)), registry)
    assert result.log.text == "Урон: 1d8 (2 | 6 → 6) + 3 = 9 [Свирепый атакующий]"
