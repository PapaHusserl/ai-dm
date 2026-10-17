# Партия К7д, п. 5 (Q4а): летающие монстры не падают (docs/plan-k7d.md).
#   Monster.fly_ft: int = 0 -- скорость полёта. falling.fall: монстр с fly_ft > 0, который не лежит
#   (нет prone), дееспособен (боеспособен, без недееспособности) -- не падает: урона и броска нет,
#   prone не ставится, в логе «парит». Лежащий, потерявший сознание, парализованный или на 0 HP
#   летун падает как обычно; без fly_ft и у героев -- без изменений.
import pytest
from combat_kit import ScriptedRng, creature, custom_registry, hp, part, set_hp
from test_falling import conditions, log, roof_duel, shove_down

from ai_dm.content.models.monsters import Monster
from ai_dm.state.creature import AppliedCondition


def flyer(registry, cfg, rng, fly=30):
    reg = custom_registry(registry, mephit={"fly_ft": fly})
    return roof_duel(registry, cfg, rng, monster="mephit", reg=reg)


def test_fly_ft_defaults_to_zero(registry):
    assert registry.get("monster", "goblin_warrior").fly_ft == 0


def test_fly_ft_is_a_plain_field(registry):
    data = registry.get("monster", "goblin_warrior").model_dump()
    data["fly_ft"] = 40
    assert Monster.model_validate(data).fly_ft == 40


def test_flyer_hovers_without_damage(registry, cfg):
    engine = flyer(registry, cfg, ScriptedRng())
    shove_down(engine)
    assert hp(engine, "goblin_1") == 10
    assert conditions(engine) == []


def test_flyer_still_changes_zone(registry, cfg):
    engine = flyer(registry, cfg, ScriptedRng())
    shove_down(engine)
    assert part(engine, "goblin_1").zone_id == "hall"


def test_hovering_is_logged(registry, cfg):
    engine = flyer(registry, cfg, ScriptedRng())
    shove_down(engine)
    assert "парит" in log(engine)
    assert "падает" not in log(engine)


def test_walker_falls_as_before(registry, cfg):
    engine = roof_duel(registry, cfg, ScriptedRng(d6=[4]))
    shove_down(engine)
    assert hp(engine, "goblin_1") == 6


def test_prone_flyer_falls(registry, cfg):
    engine = flyer(registry, cfg, ScriptedRng(d6=[4]))
    creature(engine, "goblin_1").conditions.append(AppliedCondition(id="prone", source="x"))
    shove_down(engine)
    assert hp(engine, "goblin_1") == 6


@pytest.mark.parametrize("condition", ["incapacitated", "paralyzed", "stunned", "unconscious"])
def test_incapacitated_flyer_falls(registry, cfg, condition):
    engine = flyer(registry, cfg, ScriptedRng(d6=[4]))
    creature(engine, "goblin_1").conditions.append(AppliedCondition(id=condition, source="x"))
    shove_down(engine)
    assert hp(engine, "goblin_1") == 6


def test_downed_flyer_falls(registry, cfg):
    engine = flyer(registry, cfg, ScriptedRng(d6=[1]))
    part(engine, "goblin_1").status = "down"
    set_hp(engine, "goblin_1", 3)
    shove_down(engine)
    assert hp(engine, "goblin_1") == 2


def test_hero_falls_as_before(registry, cfg):
    engine = roof_duel(registry, cfg, ScriptedRng(d6=[3]))
    assert engine.heroes["hero"].creature.hp_current == 12
    from ai_dm.combat import falling

    falling.push(engine, "goblin_1", "hero", "hall")
    assert hp(engine, "hero") == 9


def test_one_foot_of_flight_is_enough_to_hover(registry, cfg):
    engine = flyer(registry, cfg, ScriptedRng(), fly=1)
    shove_down(engine)
    assert hp(engine, "goblin_1") == 10
