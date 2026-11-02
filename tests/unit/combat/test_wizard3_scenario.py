# К3 П3, «Проверка руками» (docs/plan-k3.md): волшебник 3 ур. в бою -- сценарный тест вместо
# ручного прогона TUI. Один бой: Удержание личности на гоблина, Щит при попадании второго,
# Палящий луч, пункт «Цветной шар ▸» в меню. Ожидания -- из «Тестов» П3, не из кода.
#   Удержание личности (2 круг, ячейка 2 круга): гоблин 1 проваливает Мдр -- paralyzed, в конце его
#     хода повтор (провал -- держится), концентрация на заклинателе;
#   Щит: гоблин 2 бросает 8 + 4 = 12 против КД 11 -- попадание; с +5 (16) -- промах, ячейка 1 круга
#     и реакция потрачены, лог «Щит — КД 16, промах», HP целы;
#   Палящий луч (2 круг): три атаки +5 по гоблину 2 -- по 2d6, ячейка 2 круга;
#   меню игрока: у цели есть «Цветной шар ▸» (шесть типов).
from combat_kit import (
    ScriptedRng,
    creature,
    hp,
    make_engine,
    mon,
    part,
    set_hp,
    wizard_choices,
)

from ai_dm.combat.controllers import ScriptedController
from ai_dm.rules.builder import build_character
from ai_dm.rules.progression import level_up
from ai_dm.ui.combat_menu import SPELLS_TARGET_LABEL, TargetChip, build_view

SPELLS = ["hold_person", "scorching_ray", "shield", "chromatic_orb"]
CHIPS = [TargetChip("goblin_2", "Воин-гоблин", "30/30")]


def wizard3(registry):
    hero = build_character(wizard_choices("wiz"), registry)
    while hero.sheet.level < 3:
        level_up(hero, registry, hp_method="average")
    hero.sheet.prepared_of().extend(SPELLS)
    return hero


def battle(registry, cfg, rng):
    monsters = [
        mon("goblin_1", "goblin_warrior", "hall"), mon("goblin_2", "goblin_warrior", "door"),
    ]
    controllers = {ref: ScriptedController([]) for ref in ("wiz", "goblin_1", "goblin_2")}
    engine = make_engine(
        registry, cfg, heroes=[wizard3(registry)], rng=rng, monsters=monsters,
        hero_zone="door", controllers=controllers,
    )
    for ref in ("goblin_1", "goblin_2"):
        set_hp(engine, ref, 30)
    return engine


def slot(engine, circle):
    return engine.heroes["wiz"].creature.resources[f"spell_slot:{circle}"].current


def test_wizard_of_level_3_has_four_first_and_two_second_circle_slots(registry, cfg):
    engine = battle(registry, cfg, ScriptedRng())
    assert (slot(engine, 1), slot(engine, 2)) == (4, 2)


def test_scenario_hold_person_then_shield_then_scorching_ray(registry, cfg):
    # d20: Мдр гоблина 1 -- 5 (провал); атака гоблина 2 -- 8; повтор Мдр в конце хода
    # гоблина 1 -- 5; три луча -- по два d20 (дальняя атака при враге рядом -- помеха) 12 и 12:
    # +5 попадает в КД 15; урон 2d6 = 3 + 4 трижды
    rng = ScriptedRng(d20=[5, 8, 5] + [12] * 6, d6=[3, 4] * 3)
    engine = battle(registry, cfg, rng)

    engine.perform("wiz", "cast:hold_person:2:goblin_1")
    assert "paralyzed" in [c.id for c in creature(engine, "goblin_1").conditions]
    assert engine.heroes["wiz"].creature.concentration.spell_id == "hold_person"
    assert slot(engine, 2) == 1

    engine.perform("goblin_2", "attack:скимитар:wiz")
    assert "Щит — КД 16, промах" in "\n".join(engine.state.log)
    assert hp(engine, "wiz") == creature(engine, "wiz").hp_max
    assert slot(engine, 1) == 3
    assert part(engine, "wiz").turn.reaction is False

    engine.step()
    engine.step()
    engine.step()
    assert "paralyzed" in [c.id for c in creature(engine, "goblin_1").conditions]
    engine.start_turn("wiz")
    engine.perform("wiz", "cast:scorching_ray:2:goblin_2")
    assert hp(engine, "goblin_2") == 30 - 21
    assert slot(engine, 2) == 0


# Меню-тест К3 (решение 44): весь репертуар кругов 0-3 в известных и подготовленных

def full_repertoire_engine(registry, cfg, seed):
    from ai_dm.core.rng import Rng
    from ai_dm.state.creature import ResourcePool

    hero = build_character(wizard_choices("wiz"), registry)
    spells = [
        s for s in registry.all("spell") if s.level <= 3 and {"wizard", "cleric"} & set(s.classes)
    ]
    hero.sheet.known_of()[:] = [s.id for s in spells if s.level == 0]
    hero.sheet.prepared_of()[:] = [s.id for s in spells if s.level > 0]
    for circle in (1, 2, 3):
        hero.creature.resources[f"spell_slot:{circle}"] = ResourcePool(current=3, max=3)
    monsters = [mon(f"goblin_{i}", "goblin_warrior", zone) for i, zone in
                ((1, "hall"), (2, "hall"), (3, "door"))]
    engine = make_engine(
        registry, cfg, heroes=[hero], rng=Rng(seed), monsters=monsters, hero_zone="door",
    )
    for spec in monsters:
        set_hp(engine, spec["ref"], 30)
    return engine


def test_full_repertoire_menu_builds_without_errors(registry, cfg):
    engine = full_repertoire_engine(registry, cfg, 1)
    options = engine.available_actions("wiz")
    chips = [TargetChip(f"goblin_{i}", "Воин-гоблин", "30/30") for i in (1, 2, 3)]
    view = build_view(options, chips, "goblin_1")
    assert len([o for o in options if o.kind == "cast"]) > 100
    assert view.rows


def test_full_repertoire_every_cast_option_can_be_performed(registry, cfg):
    import copy

    from ai_dm.rules.results import Rejected

    engine = full_repertoire_engine(registry, cfg, 2)
    cast_ids = [o.id for o in engine.available_actions("wiz") if o.kind == "cast"]
    rejected = []
    for option_id in cast_ids:
        trial = copy.deepcopy(engine)
        if isinstance(trial.perform("wiz", option_id), Rejected):
            rejected.append(option_id)
    assert rejected == []


def test_full_repertoire_touch_spells_never_target_other_zones(registry, cfg):
    engine = full_repertoire_engine(registry, cfg, 3)
    ids = [o.id for o in engine.available_actions("wiz")]
    for spell in ("shocking_grasp", "inflict_wounds", "chill_touch", "vampiric_touch"):
        targets = {i.split(":")[3] for i in ids if i.startswith(f"cast:{spell}:")}
        assert targets == {"goblin_3"}, spell


def test_scenario_menu_has_the_orb_variants_row(registry, cfg):
    engine = battle(registry, cfg, ScriptedRng())
    options = engine.available_actions("wiz")
    view = build_view(options, CHIPS, "goblin_2", expanded="spells_target")
    assert SPELLS_TARGET_LABEL in [
        row.label for row in build_view(options, CHIPS, "goblin_2").target_rows
    ]
    assert "Цветной шар ▸" in [row.label for row in view.target_rows]
