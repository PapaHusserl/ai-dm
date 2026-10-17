# Партия К7х, п. 2: толчок монстров (docs/plan-k7x.md, В2, Q3 (а), Q4 (а)).
#   combat/shove.py:
#     contest_dc(engine, ref, abilities) -> (СЛ, слагаемые)   СЛ = 8 + лучший мод. из abilities +
#       БМ атакующего
#                                                             (герой -- derived.proficiency, монстр
#                                                               --
#                                                             cfg.disarm.unarmed_proficiency = 2)
#     best_save_ability(engine, target) -> "str" | "dex"      с большим бонусом спасброска (герой
#       -- с
#                                                             мастерством спасброска, монстр --
#                                                               мод.)
#     may_shove(engine, ref)                                  не герой, боеспособен, creature_type
#       из
#                                                             cfg.disarm.unarmed_types (fey у
#                                                               гоблина)
#     perform(engine, ref, option)                            тратит атаку, флаг shove_used, лог
#       «толчок → цель
#                                                             (СЛ N)», спасбросок цели (Сил: СЛ 8 +
#                                                               Сил + БМ);
#                                                             провал -- falling.push, успех --
#                                                               «устоял»
#   available.shove_options: пункт shove:<цель>:<зона> (kind "shove", params target / zone) на
#     каждую соседнюю
#     зону для каждой боеспособной цели в зоне монстра; у героя (Q3) пунктов нет; нужно действие
#       или attacks_left.
#   settle_ground снимает shove_used.
#   Гоблин: Сил 8 (-1), БМ 2 -> СЛ 9. Воин героя: Сил 17 (спас +5), Лов 13 (+1). Следопыт Грей: Лов
#     17.
from combat_kit import (
    ScriptedRng,
    creature,
    hp,
    make_engine,
    make_fighter,
    mon,
    option_ids,
    part,
    set_hp,
)
from test_ranger_combat import make_ranger

from ai_dm.combat import shove
from ai_dm.combat.end import settle_ground
from ai_dm.content.models.monsters import Monster
from ai_dm.state.combat import Zone
from ai_dm.state.creature import ActiveEffect


def zones():
    return [
        Zone(id="hall", name="Центр зала", adjacent=["balcony", "pit"]),
        Zone(id="balcony", name="Балкон", adjacent=["hall"], elevation=1),
        Zone(id="pit", name="Яма", adjacent=["hall"], elevation=-1),
    ]


def odd_registry(registry, **fields):
    data = registry.get("monster", "goblin_warrior").model_dump()
    data.update(fields)
    data["id"] = "odd_goblin"
    return registry.with_items({"monster": [Monster.model_validate(data)]})


def roof(registry, cfg, rng=None, hero=None, zone="balcony", **kwargs):
    # герой и гоблин на балконе (высота 1); внизу зал
    return make_engine(
        registry, cfg, heroes=[(hero or make_fighter(registry), zone)], rng=rng, zones=zones(),
        monsters=[mon("goblin_1", "goblin_warrior", zone)], **kwargs,
    )


def shoves(engine, ref="goblin_1"):
    return [o for o in engine.available_actions(ref) if o.kind == "shove"]


def flags(engine, ref="goblin_1", flag_id="shove_used"):
    return [e for e in creature(engine, ref).active_effects if e.id == flag_id]


def log(engine):
    return "\n".join(engine.state.log)


# --- shove_options ---

def test_goblin_has_a_shove_option_for_each_neighbour_zone_of_the_hero(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=ScriptedRng(),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    assert sorted(o.id for o in shoves(engine)) == ["shove:hero:balcony", "shove:hero:door"]


def test_shove_option_params_and_kind(registry, cfg):
    engine = roof(registry, cfg)
    option = shoves(engine)[0]
    assert option.kind == "shove"
    assert option.id == "shove:hero:hall"
    assert option.params == {"target": "hero", "zone": "hall"}


def test_shove_option_label_names_the_target_and_the_zone(registry, cfg):
    engine = roof(registry, cfg)
    assert [o.label for o in shoves(engine) if o.params["zone"] == "hall"] == [
        "Толкнуть: Арн → Центр зала"
    ]


def test_shove_options_cover_both_neighbours_of_the_zone(registry, cfg):
    engine = roof(registry, cfg, zone="hall")
    assert sorted(o.id for o in shoves(engine)) == ["shove:hero:balcony", "shove:hero:pit"]


def test_hero_has_no_shove_option(registry, cfg):
    engine = roof(registry, cfg)
    assert shoves(engine, "hero") == []


def test_monster_outside_unarmed_types_has_no_shove(registry, cfg):
    reg = odd_registry(registry, creature_type="beast")
    engine = make_engine(
        reg, cfg, heroes=[(make_fighter(registry), "balcony")], rng=ScriptedRng(),
        zones=zones(), monsters=[mon("goblin_1", "odd_goblin", "balcony")],
    )
    assert shoves(engine) == []


def test_monster_without_action_and_extra_attacks_has_no_shove(registry, cfg):
    engine = roof(registry, cfg)
    part(engine, "goblin_1").turn.action = False
    assert shoves(engine) == []


def test_monster_with_an_extra_attack_left_can_shove(registry, cfg):
    engine = roof(registry, cfg)
    part(engine, "goblin_1").turn.action = False
    part(engine, "goblin_1").turn.attacks_left = 1
    assert shoves(engine)


def test_no_shove_for_a_target_in_another_zone(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "hall")], rng=ScriptedRng(),
        zones=zones(), monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    assert shoves(engine) == []


def test_no_shove_for_a_downed_target(registry, cfg):
    engine = roof(registry, cfg)
    part(engine, "hero").status = "down"
    assert shoves(engine) == []


def test_shove_option_per_target_in_the_zone(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "balcony"),
                               (make_fighter(registry, "ally"), "balcony")],
        rng=ScriptedRng(), zones=zones(), monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    assert sorted(o.id for o in shoves(engine)) == ["shove:ally:hall", "shove:hero:hall"]


def test_incapacitated_monster_has_no_shove(registry, cfg):
    engine = roof(registry, cfg)
    part(engine, "goblin_1").status = "down"
    assert shoves(engine) == []


def test_shove_option_is_in_the_menu_ids(registry, cfg):
    engine = roof(registry, cfg)
    assert "shove:hero:hall" in option_ids(engine, "goblin_1")


# --- may_shove ---

def test_goblin_may_shove(registry, cfg):
    assert shove.may_shove(roof(registry, cfg), "goblin_1") is True


def test_hero_may_not_shove(registry, cfg):
    assert shove.may_shove(roof(registry, cfg), "hero") is False


def test_downed_goblin_may_not_shove(registry, cfg):
    engine = roof(registry, cfg)
    part(engine, "goblin_1").status = "down"
    assert shove.may_shove(engine, "goblin_1") is False


def test_goblin_at_zero_hp_may_not_shove(registry, cfg):
    engine = roof(registry, cfg)
    set_hp(engine, "goblin_1", 0)
    assert shove.may_shove(engine, "goblin_1") is False


def test_beast_may_not_shove(registry, cfg):
    reg = odd_registry(registry, creature_type="beast")
    engine = make_engine(
        reg, cfg, heroes=[(make_fighter(registry), "balcony")], rng=ScriptedRng(),
        zones=zones(), monsters=[mon("goblin_1", "odd_goblin", "balcony")],
    )
    assert shove.may_shove(engine, "goblin_1") is False


def test_humanoid_may_shove(registry, cfg):
    reg = odd_registry(registry, creature_type="humanoid")
    engine = make_engine(
        reg, cfg, heroes=[(make_fighter(registry), "balcony")], rng=ScriptedRng(),
        zones=zones(), monsters=[mon("goblin_1", "odd_goblin", "balcony")],
    )
    assert shove.may_shove(engine, "goblin_1") is True


# --- contest_dc ---

def test_goblin_dc_by_strength_is_nine(registry, cfg):
    dc, parts = shove.contest_dc(roof(registry, cfg), "goblin_1", ("str",))
    assert dc == 9
    assert sum(value for _, value in parts) == 9


def test_goblin_dc_by_strength_or_dexterity_takes_the_best(registry, cfg):
    # Лов 15 (+2): 8 + 2 + 2
    dc, parts = shove.contest_dc(roof(registry, cfg), "goblin_1", ("str", "dex"))
    assert dc == 12
    assert sum(value for _, value in parts) == 12


def test_hero_dc_by_strength(registry, cfg):
    # Сил 17 (+3), мастерство героя +2
    dc, _ = shove.contest_dc(roof(registry, cfg), "hero", ("str",))
    assert dc == 13


def test_hero_dc_by_dexterity_only_uses_dexterity(registry, cfg):
    # Лов 13 (+1)
    dc, _ = shove.contest_dc(roof(registry, cfg), "hero", ("dex",))
    assert dc == 11


def test_hero_dc_takes_the_best_of_two(registry, cfg):
    dc, _ = shove.contest_dc(roof(registry, cfg), "hero", ("str", "dex"))
    assert dc == 13


def test_dc_parts_name_the_ability_and_the_proficiency(registry, cfg):
    _, parts = shove.contest_dc(roof(registry, cfg), "goblin_1", ("str",))
    labels = [label for label, _ in parts]
    assert "Сил" in labels
    assert "мастерство" in labels
    assert dict(parts)["Сил"] == -1
    assert dict(parts)["мастерство"] == 2


def test_dc_parts_name_the_better_ability(registry, cfg):
    _, parts = shove.contest_dc(roof(registry, cfg), "goblin_1", ("str", "dex"))
    assert dict(parts)["Лов"] == 2
    assert "Сил" not in dict(parts)


def test_monster_proficiency_follows_the_config(registry):
    from ai_dm.config.settings import load_rules_config
    custom = load_rules_config(toml_text="[disarm]\nunarmed_proficiency = 4\n")
    dc, _ = shove.contest_dc(roof(registry, custom), "goblin_1", ("str",))
    assert dc == 11


# --- best_save_ability ---

def test_goblin_saves_by_dexterity(registry, cfg):
    assert shove.best_save_ability(roof(registry, cfg), "goblin_1") == "dex"


def test_fighter_saves_by_strength(registry, cfg):
    assert shove.best_save_ability(roof(registry, cfg), "hero") == "str"


def test_ranger_saves_by_dexterity(registry, cfg):
    engine = roof(registry, cfg, hero=make_ranger(registry))
    assert shove.best_save_ability(engine, "hero") == "dex"


def test_strong_monster_saves_by_strength(registry, cfg):
    reg = odd_registry(registry, abilities={
        "str": 18, "dex": 8, "con": 10, "int": 10, "wis": 8, "cha": 8,
    })
    engine = make_engine(
        reg, cfg, heroes=[(make_fighter(registry), "balcony")], rng=ScriptedRng(),
        zones=zones(), monsters=[mon("goblin_1", "odd_goblin", "balcony")],
    )
    assert shove.best_save_ability(engine, "goblin_1") == "str"


# --- perform: провал спасброска ---

def test_shove_failed_save_pushes_the_hero_down(registry, cfg):
    # СЛ 9; Сил героя +5: d20 2 -> 7 < 9
    engine = roof(registry, cfg, ScriptedRng(d20=[2], d6=[3]))
    engine.perform("goblin_1", "shove:hero:hall")
    assert part(engine, "hero").zone_id == "hall"


def test_shove_fall_hurts_the_hero_and_lays_him_prone(registry, cfg):
    engine = roof(registry, cfg, ScriptedRng(d20=[2], d6=[3]))
    engine.perform("goblin_1", "shove:hero:hall")
    assert hp(engine, "hero") == 9
    assert [(c.id, c.source) for c in creature(engine, "hero").conditions] == [("prone", "fall")]


def test_shove_log_names_the_dc(registry, cfg):
    engine = roof(registry, cfg, ScriptedRng(d20=[2], d6=[3]))
    engine.perform("goblin_1", "shove:hero:hall")
    assert "Воин-гоблин: толчок → Арн (СЛ 9)" in engine.state.log


def test_shove_log_has_the_fall_line(registry, cfg):
    engine = roof(registry, cfg, ScriptedRng(d20=[2], d6=[3]))
    engine.perform("goblin_1", "shove:hero:hall")
    assert "  Арн падает с высоты 10 фт" in engine.state.log


def test_shove_saves_by_the_better_ability_in_the_log(registry, cfg):
    engine = roof(registry, cfg, ScriptedRng(d20=[2], d6=[3]))
    engine.perform("goblin_1", "shove:hero:hall")
    assert any("спасбросок str" in line for line in engine.state.log)


def test_ranger_saves_by_dexterity_against_a_shove(registry, cfg):
    engine = roof(registry, cfg, ScriptedRng(d20=[2], d6=[3]), hero=make_ranger(registry))
    engine.perform("goblin_1", "shove:hero:hall")
    assert any("спасбросок dex" in line for line in engine.state.log)


def test_dc_is_the_save_target(registry, cfg):
    # Сил героя +5: d20 4 -> 9 = СЛ 9 -- успех
    engine = roof(registry, cfg, ScriptedRng(d20=[4]))
    engine.perform("goblin_1", "shove:hero:hall")
    assert part(engine, "hero").zone_id == "balcony"


def test_save_one_below_the_dc_fails(registry, cfg):
    engine = roof(registry, cfg, ScriptedRng(d20=[3], d6=[1]))
    engine.perform("goblin_1", "shove:hero:hall")
    assert part(engine, "hero").zone_id == "hall"


def test_shove_to_the_same_level_deals_no_damage(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "hall")], rng=ScriptedRng(d20=[2]),
        zones=zones(), monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    engine.state.zones[2].elevation = 0
    engine.perform("goblin_1", "shove:hero:pit")
    assert part(engine, "hero").zone_id == "pit"
    assert hp(engine, "hero") == 12


def test_shove_into_the_pit_is_a_fall(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "hall")],
        rng=ScriptedRng(d20=[2], d6=[4]),
        zones=zones(), monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    engine.perform("goblin_1", "shove:hero:pit")
    assert hp(engine, "hero") == 8


def test_shove_can_kill_a_hero_at_one_hp(registry, cfg):
    engine = roof(registry, cfg, ScriptedRng(d20=[2], d6=[3]))
    set_hp(engine, "hero", 1)
    engine.perform("goblin_1", "shove:hero:hall")
    assert hp(engine, "hero") == 0
    assert part(engine, "hero").status == "down"


# --- perform: успех спасброска ---

def test_shove_resisted_leaves_the_hero_in_place(registry, cfg):
    engine = roof(registry, cfg, ScriptedRng(d20=[10]))
    engine.perform("goblin_1", "shove:hero:hall")
    assert part(engine, "hero").zone_id == "balcony"
    assert hp(engine, "hero") == 12
    assert creature(engine, "hero").conditions == []


def test_shove_resisted_logs_that_the_hero_held(registry, cfg):
    engine = roof(registry, cfg, ScriptedRng(d20=[10]))
    engine.perform("goblin_1", "shove:hero:hall")
    assert "  Арн устоял" in engine.state.log


def test_failed_shove_has_no_held_line(registry, cfg):
    engine = roof(registry, cfg, ScriptedRng(d20=[2], d6=[3]))
    engine.perform("goblin_1", "shove:hero:hall")
    assert "  Арн устоял" not in engine.state.log


def test_resisted_shove_has_no_fall_line(registry, cfg):
    engine = roof(registry, cfg, ScriptedRng(d20=[10]))
    engine.perform("goblin_1", "shove:hero:hall")
    assert "падает" not in log(engine)


# --- perform: экономия и флаг ---

def test_shove_spends_the_action(registry, cfg):
    engine = roof(registry, cfg, ScriptedRng(d20=[10]))
    engine.perform("goblin_1", "shove:hero:hall")
    assert part(engine, "goblin_1").turn.action is False


def test_shove_spends_an_extra_attack_not_the_action(registry, cfg):
    engine = roof(registry, cfg, ScriptedRng(d20=[10]))
    part(engine, "goblin_1").turn.action = False
    part(engine, "goblin_1").turn.attacks_left = 1
    engine.perform("goblin_1", "shove:hero:hall")
    assert part(engine, "goblin_1").turn.attacks_left == 0


def test_shove_marks_the_monster_with_the_used_flag(registry, cfg):
    engine = roof(registry, cfg, ScriptedRng(d20=[10]))
    engine.perform("goblin_1", "shove:hero:hall")
    assert len(flags(engine)) == 1
    assert flags(engine)[0].kind == "flag"
    assert flags(engine)[0].source == "goblin_1"


def test_resisted_shove_marks_too(registry, cfg):
    engine = roof(registry, cfg, ScriptedRng(d20=[2], d6=[3]))
    engine.perform("goblin_1", "shove:hero:hall")
    assert len(flags(engine)) == 1


def test_target_gets_no_flag(registry, cfg):
    engine = roof(registry, cfg, ScriptedRng(d20=[10]))
    engine.perform("goblin_1", "shove:hero:hall")
    assert flags(engine, "hero") == []


def test_shove_option_stays_in_the_menu_after_use(registry, cfg):
    # меню не прячет пункт: один толчок за бой -- политика ИИ (ключевой NPC выбирает сам)
    engine = roof(registry, cfg, ScriptedRng(d20=[10]))
    engine.perform("goblin_1", "shove:hero:hall")
    part(engine, "goblin_1").turn.action = True
    assert shoves(engine)


def test_shove_is_rejected_for_a_far_zone(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "hall")], rng=ScriptedRng(),
        zones=zones(), monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    result = engine.perform("goblin_1", "shove:hero:nowhere")
    assert result.reason == "not_available"


# --- settle_ground ---

def test_settle_ground_removes_the_shove_flag(registry, cfg):
    engine = roof(registry, cfg)
    creature(engine, "goblin_1").active_effects.append(
        ActiveEffect(id="shove_used", source="goblin_1", kind="flag")
    )
    settle_ground(engine)
    assert flags(engine) == []


def test_settle_ground_keeps_other_effects(registry, cfg):
    engine = roof(registry, cfg)
    creature(engine, "goblin_1").active_effects.append(
        ActiveEffect(id="shove_used", source="goblin_1", kind="flag")
    )
    creature(engine, "goblin_1").active_effects.append(
        ActiveEffect(id="other", source="goblin_1", kind="flag")
    )
    settle_ground(engine)
    assert [e.id for e in creature(engine, "goblin_1").active_effects] == ["other"]


def test_shove_options_skip_an_ineligible_first_target_but_keep_the_next(registry, cfg):
    # первая цель в другой зоне, вторая рядом
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry, "far"), "hall"),
                               (make_fighter(registry, "near"), "balcony")],
        rng=ScriptedRng(), zones=zones(), monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    assert [o.id for o in shoves(engine)] == ["shove:near:hall"]


def test_shove_options_skip_a_downed_first_target_but_keep_the_next(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry, "down"), "balcony"),
                               (make_fighter(registry, "near"), "balcony")],
        rng=ScriptedRng(), zones=zones(), monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    part(engine, "down").status = "down"
    assert [o.id for o in shoves(engine)] == ["shove:near:hall"]


def test_shove_fall_names_the_goblin_as_the_one_who_hit_the_hero(registry, cfg):
    engine = roof(registry, cfg, ScriptedRng(d20=[2], d6=[3]))
    engine.perform("goblin_1", "shove:hero:hall")
    assert part(engine, "hero").last_hit_by == "goblin_1"


def test_dc_parts_start_with_the_plain_eight(registry, cfg):
    _, parts = shove.contest_dc(roof(registry, cfg), "goblin_1", ("str",))
    assert parts[0] == ("", 8)
