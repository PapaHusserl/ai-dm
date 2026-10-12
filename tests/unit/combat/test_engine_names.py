# Р1: participant_name(state, heroes, ref) -- имя участника без движка (нужно свёртке боя, когда
# CombatEngine уже нет). Должно совпадать с CombatEngine.name на любом состоянии.
from combat_kit import make_engine, make_fighter, mon

from ai_dm.combat.engine import participant_name


def engine_with(registry, cfg, monsters):
    return make_engine(registry, cfg, heroes=[make_fighter(registry)], monsters=monsters)


def name_of(engine, ref):
    return participant_name(engine.state, engine.heroes, ref)


def test_hero_name_comes_from_the_sheet(registry, cfg):
    engine = engine_with(registry, cfg, [mon("goblin_1", "goblin_warrior", "hall")])
    assert name_of(engine, "hero") == "Арн"


def test_unique_monster_name_has_no_number(registry, cfg):
    engine = engine_with(registry, cfg, [mon("goblin_1", "goblin_warrior", "hall")])
    assert name_of(engine, "goblin_1") == "Воин-гоблин"


def test_same_names_get_numbers_by_participant_order(registry, cfg):
    engine = engine_with(registry, cfg, [
        mon("goblin_1", "goblin_warrior", "hall"), mon("goblin_2", "goblin_warrior", "hall"),
    ])
    assert name_of(engine, "goblin_1") == "Воин-гоблин 1"
    assert name_of(engine, "goblin_2") == "Воин-гоблин 2"


def test_named_npc_among_nameless_keeps_own_name(registry, cfg):
    engine = engine_with(registry, cfg, [
        mon("goblin_1", "goblin_warrior", "hall"), mon("goblin_2", "goblin_warrior", "hall"),
    ])
    engine.state.participants[2].name = "Гракх"
    assert name_of(engine, "goblin_1") == "Воин-гоблин"
    assert name_of(engine, "goblin_2") == "Гракх"


def test_empty_name_falls_back_to_ref(registry, cfg):
    engine = engine_with(registry, cfg, [mon("goblin_1", "goblin_warrior", "hall")])
    engine.state.participants[1].name = ""
    assert name_of(engine, "goblin_1") == "goblin_1"


def test_two_empty_names_are_not_numbered(registry, cfg):
    engine = engine_with(registry, cfg, [
        mon("goblin_1", "goblin_warrior", "hall"), mon("goblin_2", "goblin_warrior", "hall"),
    ])
    for part in engine.state.participants[1:]:
        part.name = ""
    assert name_of(engine, "goblin_1") == "goblin_1"
    assert name_of(engine, "goblin_2") == "goblin_2"


def test_hero_with_monster_name_is_not_counted_in_numbering(registry, cfg):
    engine = engine_with(registry, cfg, [
        mon("goblin_1", "goblin_warrior", "hall"), mon("goblin_2", "goblin_warrior", "hall"),
    ])
    engine.state.participants[0].name = "Воин-гоблин"
    assert name_of(engine, "goblin_2") == "Воин-гоблин 2"


def test_matches_engine_name_for_every_participant(registry, cfg):
    engine = engine_with(registry, cfg, [
        mon("goblin_1", "goblin_warrior", "hall"), mon("goblin_2", "goblin_warrior", "hall"),
        mon("guard_1", "guard", "hall"),
    ])
    engine.state.participants[3].name = ""
    for part in engine.state.participants:
        assert name_of(engine, part.ref) == engine.name(part.ref)
