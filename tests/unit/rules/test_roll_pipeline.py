# Ожидаемый API: ai_dm.rules.roll_pipeline (конвейер бросков, ARCHITECTURE A4)
#   RollRequest(BaseModel)
#       kind: str                  -- "attack" | "save" | "check" | "initiative" | "death_save"
#                                     | "damage"; неизвестный -> ValueError при roll()
#       actor: HeroState | CreatureState          -- у героя состояние берётся из .creature
#       actor_id: str = ""
#       target: HeroState | CreatureState | None = None
#       target_id: str | None = None
#       ability: str | None = None, skill: str | None = None
#       tags: dict[str, bool | int | str] = {}    -- critical_moment, stakes_critical, melee, ...
#       base_adv: "normal" | "advantage" | "disadvantage" = "normal"
#       bonus: int = 0             -- плоский бонус (из derived), уже посчитанный вызывающим
#       dc: int | None = None      -- КД для атаки, СЛ для остальных; None -- исхода нет
#       dice: str | None = None    -- только для kind="damage", например "1d8"
#       now_s: int | None = None   -- текущее время для источников «раз в день» (D1)
#   roll(request, rng, registry, *, modifiers=None, rerollers=None) -> RollResult
#       modifiers -- ModifierRegistry (по умолчанию встроенный),
#       rerollers -- список перебросов (по умолчанию [luck, heroic_inspiration]); [] -- без них
#       (переброс при adv/dis и логи перебросов -- в test_rerolls.py; dc_bonus/crit_min -- в
#       test_modifiers.py). Урон (kind="damage") -- грани кубиков в логе, см. test_rerolls.py
#   RollResult(BaseModel)
#       kind: str
#       terms: list[RollTerm]      -- RollTerm(source: str, value: int); источники: "d20"
#                                     кость), "bonus", "exhaustion" (-2 * уровень), id эффекта
#                                     ("bless"), id внешнего ModifierSource
#       total: int                 -- сумма значений термов
#       natural: int | None        -- оставленный d20; None, если d20 не бросали (автопровал)
#       d20_rolls: list[int]       -- все выпавшие d20 по порядку (обе кости при adv/dis, перебросы)
#       advantage: "normal" | "advantage" | "disadvantage"
#       dc: int | None
#       outcome: str | None        -- attack: "hit" | "miss" | "crit"; прочие: "success" | "fail";
#                                     без dc -- None. На атаке nat 20 = "crit", nat 1 = "miss"
#       rerolls: list[str]         -- "luck", "heroic_inspiration", "savage_attacker"
#       tags: dict                 -- копия tags запроса
#       log: RollLogEntry          -- .text -- строка лога по ТЗ 6
#   Порядок бросков из rng: d20 (обе при adv/dis), кубики бонусов (по источникам), перебросы.
#   Любое adv + любая помеха = обычный бросок; несколько adv = всё равно одно adv.
#   Строка лога атаки без доп. термов: "d20 (14) + 5 бонус атаки = 19 против КД 15 → попадание"
#   (единственная реализация -- конвейер, core.dice.format_attack_log удалён, аудит 1 п. 2.12).
import pytest

from ai_dm.core.rng import Rng
from ai_dm.rules.roll_pipeline import RollRequest, roll
from ai_dm.state.creature import AppliedCondition, CreatureState


class ScriptedRng(Rng):
    # rolls: пары (граней, выпало); порядок и размер костей проверяются
    def __init__(self, *rolls):
        super().__init__(1)
        self.rolls = list(rolls)

    def randbelow(self, n):
        sides, face = self.rolls.pop(0)
        assert sides == n
        return face - 1


def make_creature(*conditions):
    return CreatureState(
        hp_current=7, hp_max=7, conditions=[AppliedCondition(id=c) for c in conditions]
    )


def make_request(kind="attack", **kwargs):
    fields = {"kind": kind, "actor": make_creature(), "bonus": 5, "dc": 15}
    fields.update(kwargs)
    return RollRequest(**fields)


# базовый бросок

def test_attack_hit_total_and_outcome(registry):
    result = roll(make_request(), ScriptedRng((20, 14)), registry)
    assert result.total == 19
    assert result.natural == 14
    assert result.outcome == "hit"


def test_attack_hit_log_text(registry):
    result = roll(make_request(), ScriptedRng((20, 14)), registry)
    assert result.log.text == "d20 (14) + 5 бонус атаки = 19 против КД 15 → попадание"


def test_attack_miss_log_text(registry):
    result = roll(make_request(), ScriptedRng((20, 3)), registry)
    assert result.outcome == "miss"
    assert result.log.text == "d20 (3) + 5 бонус атаки = 8 против КД 15 → промах"


def test_attack_total_equal_to_ac_is_hit(registry):
    result = roll(make_request(), ScriptedRng((20, 10)), registry)
    assert result.outcome == "hit"


def test_natural_20_is_crit_even_below_ac(registry):
    result = roll(make_request(bonus=-5), ScriptedRng((20, 20)), registry)
    assert result.outcome == "crit"


def test_natural_1_is_miss_even_above_ac(registry):
    result = roll(make_request(bonus=30), ScriptedRng((20, 1)), registry)
    assert result.outcome == "miss"


def test_terms_are_d20_and_bonus(registry):
    result = roll(make_request(), ScriptedRng((20, 14)), registry)
    assert [(t.source, t.value) for t in result.terms] == [("d20", 14), ("bonus", 5)]


def test_d20_rolls_has_single_value_without_adv(registry):
    result = roll(make_request(), ScriptedRng((20, 14)), registry)
    assert result.d20_rolls == [14]


def test_save_success_when_total_equals_dc(registry):
    result = roll(make_request("save", ability="dex"), ScriptedRng((20, 10)), registry)
    assert result.outcome == "success"


def test_save_fail_below_dc(registry):
    result = roll(make_request("save", ability="dex"), ScriptedRng((20, 9)), registry)
    assert result.outcome == "fail"


def test_save_log_has_dc_and_result(registry):
    result = roll(make_request("save", ability="dex"), ScriptedRng((20, 12)), registry)
    assert "d20 (12)" in result.log.text
    assert "СЛ 15" in result.log.text
    assert "успех" in result.log.text


def test_check_without_dc_has_no_outcome(registry):
    request = make_request("check", dc=None, skill="athletics")
    result = roll(request, ScriptedRng((20, 12)), registry)
    assert result.outcome is None
    assert result.total == 17


def test_initiative_is_plain_d20_plus_bonus(registry):
    result = roll(make_request("initiative", dc=None, bonus=2), ScriptedRng((20, 11)), registry)
    assert result.total == 13


def test_death_save_rolls_single_d20(registry):
    result = roll(make_request("death_save", dc=None, bonus=0), ScriptedRng((20, 7)), registry)
    assert result.natural == 7


def test_damage_rolls_dice_plus_bonus(registry):
    request = make_request("damage", dc=None, bonus=3, dice="1d8")
    result = roll(request, ScriptedRng((8, 5)), registry)
    assert result.total == 8
    assert result.d20_rolls == []


def test_unknown_kind_is_error(registry):
    with pytest.raises(ValueError):
        roll(make_request("dance"), ScriptedRng((20, 5)), registry)


# преимущество и помеха

def test_advantage_takes_higher_of_two(registry):
    request = make_request(base_adv="advantage")
    result = roll(request, ScriptedRng((20, 14), (20, 3)), registry)
    assert result.natural == 14
    assert result.advantage == "advantage"


def test_advantage_takes_higher_when_second_is_higher(registry):
    request = make_request(base_adv="advantage")
    result = roll(request, ScriptedRng((20, 3), (20, 14)), registry)
    assert result.natural == 14


def test_disadvantage_takes_lower_of_two(registry):
    request = make_request(base_adv="disadvantage")
    result = roll(request, ScriptedRng((20, 14), (20, 3)), registry)
    assert result.natural == 3
    assert result.advantage == "disadvantage"


def test_advantage_keeps_both_rolls_in_d20_rolls(registry):
    request = make_request(base_adv="advantage")
    result = roll(request, ScriptedRng((20, 14), (20, 3)), registry)
    assert result.d20_rolls == [14, 3]


def test_advantage_log_shows_both_dice(registry):
    request = make_request(base_adv="advantage")
    result = roll(request, ScriptedRng((20, 14), (20, 3)), registry)
    assert "14" in result.log.text
    assert "3" in result.log.text


def test_advantage_plus_disadvantage_is_normal_single_d20(registry):
    request = make_request(base_adv="advantage", actor=make_creature("poisoned"))
    rng = ScriptedRng((20, 14))
    result = roll(request, rng, registry)
    assert result.advantage == "normal"
    assert result.natural == 14
    assert rng.rolls == []


def test_many_advantage_sources_still_one_advantage(registry):
    # base_adv + невидимый атакующий + скованная цель: три источника adv
    request = make_request(
        base_adv="advantage", actor=make_creature("invisible"), target=make_creature("restrained")
    )
    rng = ScriptedRng((20, 14), (20, 3))
    result = roll(request, rng, registry)
    assert result.advantage == "advantage"
    assert rng.rolls == []


def test_many_disadvantage_sources_and_one_advantage_is_normal(registry):
    # отравлен + испуган (помеха x2) против одного преимущества
    request = make_request(base_adv="advantage", actor=make_creature("poisoned", "frightened"))
    result = roll(request, ScriptedRng((20, 14)), registry)
    assert result.advantage == "normal"


# теги и детерминизм

def test_critical_moment_tag_goes_to_result(registry):
    request = make_request(tags={"critical_moment": True})
    result = roll(request, ScriptedRng((20, 14)), registry)
    assert result.tags["critical_moment"] is True


def test_critical_moment_is_not_set_by_default(registry):
    result = roll(make_request(), ScriptedRng((20, 14)), registry)
    assert not result.tags.get("critical_moment", False)


def test_same_seed_gives_same_result(registry):
    a = roll(make_request(base_adv="advantage"), Rng(11), registry)
    b = roll(make_request(base_adv="advantage"), Rng(11), registry)
    assert a == b


def test_roll_draws_from_given_rng(registry):
    rng = Rng(11)
    roll(make_request(), rng, registry)
    assert rng.draws >= 1


# вид броска и урон

def test_death_save_has_no_dc_and_no_outcome(registry):
    result = roll(make_request("death_save", dc=None, bonus=0), ScriptedRng((20, 7)), registry)
    assert result.outcome is None


def test_damage_log_has_dice_faces(registry):
    request = make_request("damage", dc=None, bonus=3, dice="1d8")
    result = roll(request, ScriptedRng((8, 5)), registry)
    assert result.log.text == "Урон: 1d8 (5) + 3 = 8"


def test_damage_crit_log_has_doubled_dice(registry):
    request = make_request("damage", dc=None, bonus=3, dice="1d8", tags={"crit": True})
    result = roll(request, ScriptedRng((8, 3), (8, 7)), registry)
    assert result.total == 13
    assert result.log.text == "Урон: 2d8 (3, 7) + 3 = 13 (крит, кубики ×2)"


def test_rerollers_empty_list_is_accepted_for_damage(registry):
    request = make_request("damage", dc=None, bonus=3, dice="1d8")
    result = roll(request, ScriptedRng((8, 5)), registry, rerollers=[])
    assert result.total == 8
