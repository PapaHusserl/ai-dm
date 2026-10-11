# Savage Attacker «раз за любой ход» и сейв (ревью партии 5, п. 3): список героев, уже бросавших
# кубики урона дважды в этом ходу, -- CombatState.savage_used (не TurnState, не память движка);
# сбрасывается в начале хода (start_turn). Сейв посреди хода -> загрузка (JSON) -> второй удар
# того же хода НЕ бросает кубики урона повторно. Движок атрибута savage_used больше не имеет.
# Герой здесь -- воин с чертой savage_attacker (в отличие от combat_kit.make_fighter, где её нет);
# 1d8 + 3 длинным мечом, КД гоблина 15, у гоблина 30 HP.
from combat_kit import ScriptedRng, creature, fighter_choices, hp, make_engine, mon

from ai_dm.combat.engine import CombatEngine
from ai_dm.rules.builder import build_character
from ai_dm.state.combat import CombatState
from ai_dm.state.hero import HeroState
from ai_dm.state.world import WorldState


def savage_engine(registry, cfg, rng):
    hero = build_character(fighter_choices("hero"), registry)
    assert "savage_attacker" in hero.sheet.feats
    engine = make_engine(
        registry, cfg, heroes=[hero], rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    creature(engine, "goblin_1").hp_current = 30
    creature(engine, "goblin_1").hp_max = 30
    return engine


def reloaded(engine, registry, cfg, rng):
    # сейв и загрузка: всё через JSON, новый движок над загруженным состоянием
    state = CombatState.model_validate_json(engine.state.model_dump_json())
    world = WorldState.model_validate_json(engine.world.model_dump_json())
    heroes = {
        ref: HeroState.model_validate_json(hero.model_dump_json())
        for ref, hero in engine.heroes.items()
    }
    return CombatEngine(state, world, heroes, registry, cfg, rng)


def test_first_weapon_hit_marks_the_hero_in_the_state(registry, cfg):
    engine = savage_engine(registry, cfg, ScriptedRng(d20=[15], d8=[3, 7]))
    engine.perform("hero", "attack:longsword:goblin_1")
    assert engine.state.savage_used == ["hero"]


def test_savage_takes_the_better_of_two_rolls_once(registry, cfg):
    engine = savage_engine(registry, cfg, ScriptedRng(d20=[15], d8=[3, 7]))
    engine.perform("hero", "attack:longsword:goblin_1")
    assert hp(engine, "goblin_1") == 30 - 7 - 3


def test_second_hit_in_the_same_turn_rolls_damage_once(registry, cfg):
    rng = ScriptedRng(d20=[15, 15], d8=[3, 7, 4])
    engine = savage_engine(registry, cfg, rng)
    engine.perform("hero", "attack:longsword:goblin_1")
    engine.state.participants[0].turn.action = True
    engine.perform("hero", "attack:longsword:goblin_1")
    assert rng.left("d8") == 0
    assert hp(engine, "goblin_1") == 30 - 10 - 7


def test_save_in_the_middle_of_the_turn_keeps_savage_spent(registry, cfg):
    rng = ScriptedRng(d20=[15, 15], d8=[3, 7, 4])
    engine = savage_engine(registry, cfg, rng)
    engine.perform("hero", "attack:longsword:goblin_1")
    loaded = reloaded(engine, registry, cfg, rng)
    assert loaded.state.savage_used == ["hero"]
    loaded.state.participants[0].turn.action = True
    loaded.perform("hero", "attack:longsword:goblin_1")
    assert rng.left("d8") == 0
    assert hp(loaded, "goblin_1") == 30 - 10 - 7


def test_savage_is_available_again_in_the_next_turn(registry, cfg):
    engine = savage_engine(registry, cfg, ScriptedRng(d20=[15, 15], d8=[3, 7, 2, 6]))
    engine.perform("hero", "attack:longsword:goblin_1")
    engine.start_turn("hero")
    assert engine.state.savage_used == []
    engine.perform("hero", "attack:longsword:goblin_1")
    assert hp(engine, "goblin_1") == 30 - 10 - 9


def test_turn_start_of_anyone_resets_the_list(registry, cfg):
    engine = savage_engine(registry, cfg, ScriptedRng(d20=[15], d8=[3, 7]))
    engine.perform("hero", "attack:longsword:goblin_1")
    engine.start_turn("goblin_1")
    assert engine.state.savage_used == []


def test_the_engine_keeps_no_savage_counter_of_its_own(registry, cfg):
    engine = savage_engine(registry, cfg, ScriptedRng())
    assert not hasattr(engine, "savage_used")

