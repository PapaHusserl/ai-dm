# Инициатива (шаг 16): CombatEngine.start() (контракт -- в шапке combat_kit.py).
#   Бросок на каждого участника в порядке state.participants: d20 + бонус инициативы через
#   конвейер (kind="initiative"): у героя initiative_bonus (ЛОВ + Бдительность), у монстра --
#   модификатор ЛОВ; invisible -- преимущество, incapacitated -- помеха (уже в конвейере);
#   внезапность (Participant.surprised) -- помеха.
#   Порядок: по убыванию инициативы; ничья -- у кого выше значение ЛОВ, затем меньший id.
#   После start(): state.initiative_order -- ref по порядку, round == 1, turn_index == 0,
#   у каждого участника заполнен initiative; повторный start() -> ValueError.
import pytest
from combat_kit import ScriptedRng, make_engine, make_fighter, mon, part

from ai_dm.core.rng import Rng
from ai_dm.state.creature import AppliedCondition


def new_engine(registry, cfg, rng, hero=None, monsters=None, **kwargs):
    hero = hero or make_fighter(registry)
    if monsters is None:
        monsters = [mon("goblin_1", "goblin_warrior", "hall")]
    return make_engine(
        registry, cfg, heroes=[hero], monsters=monsters, rng=rng, started=False, **kwargs
    )


def test_hero_initiative_is_d20_plus_dex(registry, cfg):
    engine = new_engine(registry, cfg, ScriptedRng(d20=[10, 10]))
    engine.start()
    assert part(engine, "hero").initiative == 11


def test_monster_initiative_is_d20_plus_dex(registry, cfg):
    engine = new_engine(registry, cfg, ScriptedRng(d20=[10, 10]))
    engine.start()
    assert part(engine, "goblin_1").initiative == 12


def test_alert_adds_proficiency_to_initiative(registry, cfg):
    hero = make_fighter(registry)
    hero.sheet.feats.append("alert")
    engine = new_engine(registry, cfg, ScriptedRng(d20=[10, 10]), hero=hero)
    engine.start()
    assert part(engine, "hero").initiative == 13


def test_rolls_go_in_participant_order(registry, cfg):
    engine = new_engine(registry, cfg, ScriptedRng(d20=[3, 18]))
    engine.start()
    assert part(engine, "hero").initiative == 4
    assert part(engine, "goblin_1").initiative == 20


def test_order_is_by_initiative_descending(registry, cfg):
    engine = new_engine(registry, cfg, ScriptedRng(d20=[3, 18]))
    engine.start()
    assert engine.state.initiative_order == ["goblin_1", "hero"]


def test_start_sets_round_and_turn_index(registry, cfg):
    engine = new_engine(registry, cfg, ScriptedRng(d20=[3, 18]))
    assert engine.state.round == 0
    engine.start()
    assert engine.state.round == 1
    assert engine.state.turn_index == 0


def test_tie_goes_to_higher_dex(registry, cfg):
    # герой 11 + 1 = 12, гоблин 10 + 2 = 12; ЛОВ 15 у гоблина против 13 у героя
    engine = new_engine(registry, cfg, ScriptedRng(d20=[11, 10]))
    engine.start()
    assert engine.state.initiative_order == ["goblin_1", "hero"]


def test_tie_with_equal_dex_goes_to_smaller_id(registry, cfg):
    monsters = [
        mon("goblin_b", "goblin_warrior", "hall"),
        mon("goblin_a", "goblin_warrior", "hall"),
    ]
    engine = new_engine(registry, cfg, ScriptedRng(d20=[1, 10, 10]), monsters=monsters)
    engine.start()
    assert engine.state.initiative_order == ["goblin_a", "goblin_b", "hero"]


def test_surprised_participant_rolls_with_disadvantage(registry, cfg):
    monsters = [mon("goblin_1", "goblin_warrior", "hall")]
    engine = new_engine(registry, cfg, ScriptedRng(d20=[10, 18, 3]), monsters=monsters)
    part(engine, "goblin_1").surprised = True
    engine.start()
    assert part(engine, "goblin_1").initiative == 5


def test_not_surprised_participant_rolls_one_die(registry, cfg):
    rng = ScriptedRng(d20=[10, 18])
    new_engine(registry, cfg, rng).start()
    assert rng.left("d20") == 0


def test_invisible_participant_rolls_with_advantage(registry, cfg):
    hero = make_fighter(registry)
    hero.creature.conditions.append(AppliedCondition(id="invisible"))
    engine = new_engine(registry, cfg, ScriptedRng(d20=[3, 15, 10]), hero=hero)
    engine.start()
    assert part(engine, "hero").initiative == 16


def test_incapacitated_participant_rolls_with_disadvantage(registry, cfg):
    hero = make_fighter(registry)
    hero.creature.conditions.append(AppliedCondition(id="incapacitated"))
    engine = new_engine(registry, cfg, ScriptedRng(d20=[15, 3, 10]), hero=hero)
    engine.start()
    assert part(engine, "hero").initiative == 4


def test_start_twice_is_an_error(registry, cfg):
    engine = new_engine(registry, cfg, ScriptedRng(d20=[3, 18]))
    engine.start()
    with pytest.raises(ValueError):
        engine.start()


def test_initiative_is_deterministic_for_the_same_seed(registry, cfg):
    orders = []
    for _ in range(2):
        engine = new_engine(registry, cfg, Rng(42))
        engine.start()
        orders.append(engine.state.initiative_order)
    assert orders[0] == orders[1]
