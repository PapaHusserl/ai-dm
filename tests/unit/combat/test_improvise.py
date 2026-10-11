# Импровизация (шаг 17, ТЗ 7): CombatEngine.improvise(ref, *, skill, category, effect,
#   target=None, zone=None) -> list[DomainEvent] | Rejected
#   Тратит действие; проверка навыка героя (derived.skill_bonus) против СЛ категории
#   (checks.dc_for_category: medium = 15); при успехе -- эффект из ФИКСИРОВАННОГО набора:
#     advantage    -- на героя ActiveEffect(id="improvised_advantage", kind="modifier",
#                     params={"target": "attack_roll", "mode": "advantage", "consume": True}):
#                     следующая атака героя с преимуществом; срок (ревью партии 5, п. 6, как у Vex;
#                     Expiry выбирает кабан, тесты проверяют поведение через step()): до конца
#                     СЛЕДУЮЩЕГО хода героя -- атака в следующем ходу с преимуществом, после конца
#                     того хода эффекта нет, атака его тратит (consume)
#     prone        -- цели AppliedCondition(id="prone", source=<ref>); нужна target
#     extra_damage -- цели урон cfg.combat.improvise_damage_dice (по умолчанию "1d6"); нужна target
#     push         -- цель перемещается в соседнюю зону zone (должна быть соседней с зоной цели);
#                     нужны target и zone
#     disarm       -- цель теряет оружие (общая логика combat/disarm.py, подробности --
#                     test_disarm.py): у героя оружие уходит из main_hand и инвентаря, у монстра
#                     ActiveEffect(id="disarmed", params={"weapon_id": ...}) и пропадает это
#                     оружейное действие (естественные атаки и другое оружие остаются), предмет
#                     лежит на земле; нужна target
#   Провал проверки -- эффекта нет, действие потрачено.
#   Неизвестный effect / нет нужных target, zone / действие уже потрачено -> Rejected
#   (проверка не бросается, действие не тратится). Неизвестная категория -> ValueError.
#   Конфиг: RulesConfig.combat.improvise_damage_dice: str = "1d6" (кубики проверяются как у
#   DefeatConfig.left_to_die_hours_dice).
import pytest
from combat_kit import (
    ScriptedRng,
    creature,
    hp,
    make_engine,
    make_fighter,
    mon,
    option_ids,
    part,
    turn,
)
from pydantic import ValidationError

from ai_dm.combat.actions.improvise import spec_problem
from ai_dm.combat.controllers import ScriptedController
from ai_dm.config.settings import load_rules_config
from ai_dm.rules.results import Rejected


def duel(registry, cfg, rng, goblin_zone="hall"):
    return make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", goblin_zone)],
    )


def improvise(engine, effect, **kwargs):
    kwargs.setdefault("skill", "athletics")
    kwargs.setdefault("category", "medium")
    return engine.improvise("hero", effect=effect, **kwargs)


# Атлетика героя: СИЛ +3 и мастерство +2 = +5; СЛ 15 -> успех от 10

def test_advantage_effect_goes_to_the_hero(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10]))
    improvise(engine, "advantage")
    assert [e.id for e in creature(engine, "hero").active_effects] == ["improvised_advantage"]


def test_improvised_advantage_gives_advantage_on_the_next_attack(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10, 3, 17], d8=[4]))
    improvise(engine, "advantage", target="goblin_1")
    # следующий ход героя: действие снова доступно
    part(engine, "hero").turn.action = True
    engine.perform("hero", "attack:longsword:goblin_1")
    assert hp(engine, "goblin_1") == 3
    assert creature(engine, "hero").active_effects == []


def test_prone_effect_knocks_the_target_down(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10]))
    improvise(engine, "prone", target="goblin_1")
    conditions = creature(engine, "goblin_1").conditions
    assert [(c.id, c.source) for c in conditions] == [("prone", "hero")]


def test_extra_damage_uses_the_configured_dice(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10], d6=[4]))
    improvise(engine, "extra_damage", target="goblin_1")
    assert hp(engine, "goblin_1") == 6


def test_extra_damage_follows_the_config(registry):
    custom = load_rules_config(toml_text='[combat]\nimprovise_damage_dice = "1d8"\n')
    engine = duel(registry, custom, ScriptedRng(d20=[10], d8=[7]))
    improvise(engine, "extra_damage", target="goblin_1")
    assert hp(engine, "goblin_1") == 3


def test_push_moves_the_target_to_the_chosen_neighbour_zone(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10]))
    improvise(engine, "push", target="goblin_1", zone="balcony")
    assert part(engine, "goblin_1").zone_id == "balcony"


def test_push_to_a_far_zone_is_rejected(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng())
    engine.state.participants[0].zone_id = "door"
    engine.state.participants[1].zone_id = "door"
    result = improvise(engine, "push", target="goblin_1", zone="balcony")
    assert isinstance(result, Rejected)


def test_push_without_zone_is_rejected(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng())
    assert isinstance(improvise(engine, "push", target="goblin_1"), Rejected)


def test_disarm_removes_the_monster_weapon_attack(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10]))
    improvise(engine, "disarm", target="goblin_1")
    assert [e.id for e in creature(engine, "goblin_1").active_effects] == ["disarmed"]
    assert "attack:скимитар:hero" not in option_ids(engine, "goblin_1")


def test_disarm_takes_the_weapon_from_a_hero(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry), make_fighter(registry, "rival")],
        rng=ScriptedRng(d20=[10]), monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    part(engine, "rival").side = "enemies"
    part(engine, "rival").group_id = "goblins"
    improvise(engine, "disarm", target="rival")
    rival = engine.heroes["rival"]
    assert rival.equipped.main_hand is None
    assert [e.item_id for e in rival.inventory if e.item_id == "longsword"] == []


def test_failed_check_has_no_effect_but_spends_the_action(registry, cfg):
    # 9 + 5 = 14 < 15
    engine = duel(registry, cfg, ScriptedRng(d20=[9], d6=[4]))
    improvise(engine, "extra_damage", target="goblin_1")
    assert hp(engine, "goblin_1") == 10
    assert turn(engine, "hero").action is False


def test_check_roll_is_written_to_the_log(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10]))
    improvise(engine, "advantage")
    expected = "Атлетика (Сил): d20 (10) + 3 Сил + 2 мастерство = 15 против СЛ 15"
    assert any(expected in line for line in engine.state.log)


def test_category_sets_the_dc(registry, cfg):
    # 'hard' = СЛ 20: 10 + 5 = 15 не хватает
    engine = duel(registry, cfg, ScriptedRng(d20=[10], d6=[4]))
    improvise(engine, "extra_damage", target="goblin_1", category="hard")
    assert hp(engine, "goblin_1") == 10


def test_skill_is_a_free_choice(registry, cfg):
    # Запугивание: ХАР +1 и мастерство +2 = +3: 12 + 3 = 15
    engine = duel(registry, cfg, ScriptedRng(d20=[12], d6=[4]))
    improvise(engine, "extra_damage", target="goblin_1", skill="intimidation")
    assert hp(engine, "goblin_1") == 6


def test_unknown_effect_is_rejected_without_a_roll(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng())
    result = improvise(engine, "grapple", target="goblin_1")
    assert isinstance(result, Rejected)
    assert turn(engine, "hero").action is True


def test_effect_that_needs_a_target_is_rejected_without_one(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng())
    for effect in ("prone", "extra_damage", "disarm"):
        assert isinstance(improvise(engine, effect), Rejected)


def test_improvisation_spends_the_action_once(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10, 10]))
    improvise(engine, "advantage")
    assert isinstance(improvise(engine, "advantage"), Rejected)


def test_unknown_category_raises(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng())
    with pytest.raises(ValueError):
        improvise(engine, "advantage", category="trivial")


# конфиг

def test_default_improvise_damage_is_1d6(cfg):
    assert cfg.combat.improvise_damage_dice == "1d6"


def test_bad_improvise_dice_in_config_is_an_error():
    with pytest.raises(ValidationError):
        load_rules_config(toml_text='[combat]\nimprovise_damage_dice = "много"\n')


# срок преимущества (ревью партии 5, п. 6): ходы раунда -- hero, goblin_1

class ImproviseThen:
    # контроллер героя: в первом ходу импровизирует advantage и кончает ход, дальше по списку
    def __init__(self, later):
        self.later = list(later)
        self.engine = None
        self.improvised = False

    def choose(self, options, ctx):
        if not self.improvised:
            self.improvised = True
            self.engine.improvise("hero", skill="athletics", category="medium", effect="advantage")
            return "end_turn"
        if self.later:
            return self.later.pop(0)
        return "end_turn"


def advantage_rounds(registry, cfg, rng, later):
    hero = ImproviseThen(later)
    controllers = {"hero": hero, "goblin_1": ScriptedController([])}
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=rng, controllers=controllers,
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    hero.engine = engine
    return engine


def test_advantage_survives_the_enemy_turn(registry, cfg):
    engine = advantage_rounds(registry, cfg, ScriptedRng(d20=[10]), [])
    engine.step()
    engine.step()
    assert [e.id for e in creature(engine, "hero").active_effects] == ["improvised_advantage"]


def test_advantage_works_on_the_attack_of_the_next_turn(registry, cfg):
    # проверка 10 + 5 = 15; атака раунда 2: два d20 (3 и 17), берётся 17; 1d8 4 + 3 = 7
    rng = ScriptedRng(d20=[10, 3, 17], d8=[4])
    engine = advantage_rounds(registry, cfg, rng, ["attack:longsword:goblin_1"])
    for _ in range(3):
        engine.step()
    assert hp(engine, "goblin_1") == 3
    assert rng.left("d20") == 0
    assert creature(engine, "hero").active_effects == []


def test_advantage_ends_with_the_next_turn(registry, cfg):
    # в раунде 2 герой не атакует, эффект снят; в раунде 3 атака обычная -- один d20 (3 -- промах)
    rng = ScriptedRng(d20=[10, 3])
    engine = advantage_rounds(registry, cfg, rng, ["end_turn", "attack:longsword:goblin_1"])
    for _ in range(3):
        engine.step()
    assert creature(engine, "hero").active_effects == []
    engine.step()
    engine.step()
    assert hp(engine, "goblin_1") == 10
    assert rng.left("d20") == 0


def test_improvise_log_line_names_the_skill_in_russian(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10]))
    improvise(engine, "advantage", skill="athletics")
    line = [x for x in engine.state.log if "импровизация" in x][0]
    assert line.startswith("Арн: импровизация (")
    assert "), Атлетика: Атлетика (Сил): d20" in line


def test_improvise_log_line_translates_another_skill(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10]))
    improvise(engine, "advantage", skill="acrobatics")
    line = [x for x in engine.state.log if "импровизация" in x][0]
    assert "), Акробатика: Акробатика (Лов): d20" in line


# 38 а: spec_problem -- чистая проверка спека по состоянию боя
# (зоны door-hall-balcony, гоблин в hall)

def test_spec_problem_is_none_for_a_valid_push(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng())
    assert spec_problem(engine.state, "push", "goblin_1", "balcony") is None


def test_spec_problem_is_none_for_advantage_without_target(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng())
    assert spec_problem(engine.state, "advantage", None, None) is None


def test_spec_problem_unknown_effect(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng())
    assert spec_problem(engine.state, "grapple", "goblin_1", None) == "unknown_effect"


@pytest.mark.parametrize("effect", ["prone", "extra_damage", "push", "disarm"])
def test_spec_problem_target_required(registry, cfg, effect):
    engine = duel(registry, cfg, ScriptedRng())
    assert spec_problem(engine.state, effect, None, "balcony") == "target_required"


def test_spec_problem_unknown_target_is_target_required(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng())
    assert spec_problem(engine.state, "prone", "ghost", None) == "target_required"


def test_spec_problem_push_without_zone(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng())
    assert spec_problem(engine.state, "push", "goblin_1", None) == "zone_required"


def test_spec_problem_push_into_the_own_zone_of_the_target(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng())
    assert spec_problem(engine.state, "push", "goblin_1", "hall") == "zone_not_adjacent"


def test_spec_problem_push_into_a_far_zone(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng())
    engine.state.participants[1].zone_id = "door"
    assert spec_problem(engine.state, "push", "goblin_1", "balcony") == "zone_not_adjacent"


def test_spec_problem_does_not_touch_the_state(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng())
    before = engine.state.model_dump_json()
    spec_problem(engine.state, "push", "goblin_1", "balcony")
    assert engine.state.model_dump_json() == before


def test_check_request_not_a_hero_comes_before_spec_problems(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng())
    result = engine.improvise("goblin_1", skill="athletics", category="medium", effect="grapple")
    assert result.reason == "not_a_hero"


def test_check_request_not_available_after_the_action_is_spent(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10, 10]))
    improvise(engine, "advantage")
    assert improvise(engine, "advantage").reason == "not_available"


@pytest.mark.parametrize(
    ("effect", "target", "zone", "reason"),
    [
        ("grapple", "goblin_1", None, "unknown_effect"),
        ("prone", None, None, "target_required"),
        ("push", "goblin_1", None, "zone_required"),
        ("push", "goblin_1", "hall", "zone_not_adjacent"),
    ],
)
def test_check_request_keeps_engine_codes(registry, cfg, effect, target, zone, reason):
    engine = duel(registry, cfg, ScriptedRng())
    result = improvise(engine, effect, target=target, zone=zone)
    assert result.reason == reason
    assert turn(engine, "hero").action is True
