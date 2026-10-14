# Партия К7к, п. 1: иммунитеты, сопротивления и уязвимости монстра в бою (docs/K7K-PLAN.md).
#   Monster.damage_immunities / damage_resistances / damage_vulnerabilities -- списки типов урона;
#   CombatEngine.damage(ref, amount, damage_type) -> DamageResult -- единственный путь урона в бою:
#     * для монстра берёт три списка статблока и передаёт в rules.damage.apply_damage;
#     * для героя списков нет (вид, как дварф-яд, и эффекты resist apply_damage считает сам);
#     * иммунитет: итог 0, строка лога «Иммунитет: N → 0 <тип>»; сопротивление: N // 2;
#       уязвимость: ×2; сопротивление + уязвимость к одному типу: (N // 2) * 2.
#   Девять путей урона в бою (царапина, горение, лозы, cast_attack, cast_darts, cast_area, опасная
#   зона, метка охотника, особый урон оружия, основной удар, импровизация) идут через engine.damage;
#   по тесту на каждый путь: иммунный к типу пути монстр не теряет HP.
#   В src/ai_dm/combat/ `apply_damage(` встречается только в engine.py.
import re
from pathlib import Path

from combat_kit import (
    ScriptedRng,
    creature,
    feature,
    give_weapon,
    hp,
    make_engine,
    make_fighter,
    make_wizard,
    make_zones,
    mon,
    set_hp,
)
from test_ranger_combat import SHOOT, make_ranger, ranger_engine, tough

from ai_dm.combat.actions.attack import mark_damage, special_damage
from ai_dm.combat.actions.move import hazard_check
from ai_dm.content.models.common import EffectSpec
from ai_dm.content.models.monsters import Monster
from ai_dm.state.creature import ActiveEffect

COMBAT_DIR = Path(__file__).resolve().parents[3] / "src" / "ai_dm" / "combat"


def odd_registry(registry, **lists):
    # воин-гоблин (10 HP, КД 15) с заданными списками защиты под id odd_goblin
    data = registry.get("monster", "goblin_warrior").model_dump()
    data.update(lists)
    data["id"] = "odd_goblin"
    return registry.with_items({"monster": [Monster.model_validate(data)]})


def odd_engine(registry, cfg, rng, hero=None, zone="hall", **lists):
    return make_engine(
        odd_registry(registry, **lists), cfg, heroes=[hero or make_fighter(registry)], rng=rng,
        monsters=[mon("goblin_1", "odd_goblin", zone)],
    )


def lines(engine):
    return "\n".join(engine.state.log)


# engine.damage: матрица защит монстра

def test_immunity_gives_zero_final(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(), damage_immunities=["slashing"])
    assert engine.damage("goblin_1", 7, "slashing").final == 0


def test_immunity_keeps_hit_points(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(), damage_immunities=["slashing"])
    engine.damage("goblin_1", 7, "slashing")
    assert hp(engine, "goblin_1") == 10


def test_immunity_note_names_the_amount_and_the_type(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(), damage_immunities=["slashing"])
    assert engine.damage("goblin_1", 7, "slashing").notes == ["Иммунитет: 7 → 0 рубящий"]


def test_immunity_is_only_for_the_listed_type(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(), damage_immunities=["slashing"])
    assert engine.damage("goblin_1", 4, "piercing").final == 4


def test_resistance_halves_rounding_down(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(), damage_resistances=["piercing"])
    assert engine.damage("goblin_1", 7, "piercing").final == 3


def test_resistance_note(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(), damage_resistances=["piercing"])
    assert engine.damage("goblin_1", 7, "piercing").notes == ["Сопротивление: 7 → 3 колющий"]


def test_resistance_is_only_for_the_listed_type(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(), damage_resistances=["piercing"])
    assert engine.damage("goblin_1", 7, "slashing").final == 7


def test_vulnerability_doubles(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(), damage_vulnerabilities=["fire"])
    assert engine.damage("goblin_1", 4, "fire").final == 8


def test_vulnerability_note(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(), damage_vulnerabilities=["fire"])
    assert engine.damage("goblin_1", 4, "fire").notes == ["Уязвимость: 4 → 8 огненный"]


def test_vulnerability_is_only_for_the_listed_type(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(), damage_vulnerabilities=["fire"])
    assert engine.damage("goblin_1", 4, "cold").final == 4


def test_resistance_and_vulnerability_to_one_type_halve_then_double(registry, cfg):
    engine = odd_engine(
        registry, cfg, ScriptedRng(), damage_resistances=["fire"],
        damage_vulnerabilities=["fire"],
    )
    assert engine.damage("goblin_1", 7, "fire").final == 6


def test_immunity_wins_over_vulnerability(registry, cfg):
    engine = odd_engine(
        registry, cfg, ScriptedRng(), damage_immunities=["fire"],
        damage_vulnerabilities=["fire"],
    )
    assert engine.damage("goblin_1", 7, "fire").final == 0


def test_plain_monster_takes_full_damage(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng())
    assert engine.damage("goblin_1", 7, "fire").final == 7


def test_damage_result_reports_hp_lost_and_drop(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng())
    dealt = engine.damage("goblin_1", 15, "fire")
    assert (dealt.hp_lost, dealt.overkill, dealt.dropped) == (10, 5, True)


def test_damage_of_a_named_npc_uses_the_statblock_lists(registry, cfg):
    engine = make_engine(
        odd_registry(registry, damage_immunities=["fire"]), cfg, heroes=[make_fighter(registry)],
        rng=ScriptedRng(), monsters=[mon("goblin_1", "odd_goblin", "hall", named=True)],
    )
    assert engine.damage("goblin_1", 7, "fire").final == 0


def test_monster_lists_do_not_touch_the_hero(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(), damage_immunities=["fire"])
    assert engine.damage("hero", 5, "fire").final == 5
    assert hp(engine, "hero") == 7


def test_hero_takes_full_damage_without_species_resistance(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng())
    assert engine.damage("hero", 6, "poison").final == 6


def test_hero_species_resistance_still_works(registry, cfg):
    hero = make_fighter(registry)
    hero.sheet.species_id = "dwarf"
    engine = odd_engine(registry, cfg, ScriptedRng(), hero=hero)
    assert engine.damage("hero", 6, "poison").final == 3


def test_hero_effect_resistance_follows_the_world_clock(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng())
    creature(engine, "hero").active_effects.append(
        ActiveEffect(id="stone_skin", source="hero", kind="resist",
                     params={"damage_type": "slashing"})
    )
    assert engine.damage("hero", 6, "slashing").final == 3


# пути урона: иммунный к типу пути монстр HP не теряет

def test_main_strike_is_stopped_by_immunity(registry, cfg):
    # длинный меч: 4 + 3 = 7 рубящего
    engine = odd_engine(
        registry, cfg, ScriptedRng(d20=[15], d8=[4]), damage_immunities=["slashing"]
    )
    engine.perform("hero", "attack:longsword:goblin_1")
    assert hp(engine, "goblin_1") == 10
    assert "Иммунитет: 7 → 0 рубящий" in lines(engine)


def test_main_strike_without_immunity_hurts(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(d20=[15], d8=[4]))
    engine.perform("hero", "attack:longsword:goblin_1")
    assert hp(engine, "goblin_1") == 3


def test_main_strike_resistance_halves(registry, cfg):
    engine = odd_engine(
        registry, cfg, ScriptedRng(d20=[15], d8=[4]), damage_resistances=["slashing"]
    )
    engine.perform("hero", "attack:longsword:goblin_1")
    assert hp(engine, "goblin_1") == 7


def test_main_strike_vulnerability_doubles(registry, cfg):
    engine = odd_engine(
        registry, cfg, ScriptedRng(d20=[15], d8=[2]), damage_vulnerabilities=["slashing"]
    )
    set_hp(engine, "goblin_1", 20)
    engine.perform("hero", "attack:longsword:goblin_1")
    assert hp(engine, "goblin_1") == 20 - 10


def test_immune_target_does_not_drop(registry, cfg):
    engine = odd_engine(
        registry, cfg, ScriptedRng(d20=[15], d8=[4]), damage_immunities=["slashing"]
    )
    set_hp(engine, "goblin_1", 1)
    engine.perform("hero", "attack:longsword:goblin_1")
    assert engine.part("goblin_1").status == "active"
    assert hp(engine, "goblin_1") == 1


def test_attack_event_of_an_immune_target_has_zero_damage(registry, cfg):
    engine = odd_engine(
        registry, cfg, ScriptedRng(d20=[15], d8=[4]), damage_immunities=["slashing"]
    )
    events = engine.perform("hero", "attack:longsword:goblin_1")
    attacks = [e for e in events if e.type == "attack"]
    assert [(e.data["outcome"], e.data["damage"]) for e in attacks] == [("hit", 0)]


def test_graze_is_stopped_by_immunity(registry, cfg):
    hero = make_fighter(registry)
    hero.sheet.weapon_masteries = ["longsword", "greatsword"]
    give_weapon(hero, registry, "greatsword")
    engine = odd_engine(
        registry, cfg, ScriptedRng(d20=[1]), hero=hero, damage_immunities=["slashing"]
    )
    engine.perform("hero", "attack:greatsword:goblin_1")
    assert hp(engine, "goblin_1") == 10
    assert "Иммунитет: 3 → 0 рубящий" in lines(engine)


def test_graze_without_immunity_scratches(registry, cfg):
    hero = make_fighter(registry)
    hero.sheet.weapon_masteries = ["greatsword"]
    give_weapon(hero, registry, "greatsword")
    engine = odd_engine(registry, cfg, ScriptedRng(d20=[1]), hero=hero)
    engine.perform("hero", "attack:greatsword:goblin_1")
    assert hp(engine, "goblin_1") == 7


def test_burning_is_stopped_by_immunity(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(d4=[3]), damage_immunities=["fire"])
    creature(engine, "goblin_1").active_effects.append(
        ActiveEffect(
            id="arrow_fire", source="hero", kind="burning",
            params={"dice": "1d4", "damage_type": "fire"},
        )
    )
    engine.burn("goblin_1")
    assert hp(engine, "goblin_1") == 10
    assert "Иммунитет: 3 → 0 огненный" in lines(engine)


def test_burning_without_immunity_burns(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(d4=[3]))
    creature(engine, "goblin_1").active_effects.append(
        ActiveEffect(
            id="arrow_fire", source="hero", kind="burning",
            params={"dice": "1d4", "damage_type": "fire"},
        )
    )
    engine.burn("goblin_1")
    assert hp(engine, "goblin_1") == 7


def test_vines_are_stopped_by_immunity(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(d6=[4]), damage_immunities=["piercing"])
    creature(engine, "goblin_1").active_effects.append(
        ActiveEffect(
            id="ensnaring_strike", source="hero", kind="ensnared",
            params={"dice": "1d6", "damage_type": "piercing", "dc": 12},
        )
    )
    engine.burn("goblin_1")
    assert hp(engine, "goblin_1") == 10
    assert "Иммунитет: 4 → 0 колющий" in lines(engine)


def test_vines_without_immunity_hurt(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(d6=[4]))
    creature(engine, "goblin_1").active_effects.append(
        ActiveEffect(
            id="ensnaring_strike", source="hero", kind="ensnared",
            params={"dice": "1d6", "damage_type": "piercing", "dc": 12},
        )
    )
    engine.burn("goblin_1")
    assert hp(engine, "goblin_1") == 6


def wizard_engine(registry, cfg, rng, monsters, reg=None):
    return make_engine(
        reg or registry, cfg, heroes=[(make_wizard(registry), "door")], rng=rng,
        monsters=monsters,
    )


def test_cast_attack_is_stopped_by_immunity(registry, cfg):
    engine = wizard_engine(
        registry, cfg, ScriptedRng(d20=[10], d10=[7]), [mon("goblin_1", "odd_goblin", "hall")],
        odd_registry(registry, damage_immunities=["fire"]),
    )
    engine.perform("wiz", "cast:fire_bolt:0:goblin_1")
    assert hp(engine, "goblin_1") == 10
    assert "Иммунитет: 7 → 0 огненный" in lines(engine)


def test_cast_attack_with_resistance_halves(registry, cfg):
    engine = wizard_engine(
        registry, cfg, ScriptedRng(d20=[10], d10=[7]), [mon("goblin_1", "odd_goblin", "hall")],
        odd_registry(registry, damage_resistances=["fire"]),
    )
    engine.perform("wiz", "cast:fire_bolt:0:goblin_1")
    assert hp(engine, "goblin_1") == 7


def test_cast_darts_are_stopped_by_immunity(registry, cfg):
    engine = wizard_engine(
        registry, cfg, ScriptedRng(d4=[1, 2, 3]), [mon("goblin_1", "odd_goblin", "hall")],
        odd_registry(registry, damage_immunities=["force"]),
    )
    engine.perform("wiz", "cast:magic_missile:1:goblin_1")
    assert hp(engine, "goblin_1") == 10
    assert "Иммунитет: 9 → 0 силовой" in lines(engine)


def test_cast_darts_with_vulnerability_double(registry, cfg):
    engine = wizard_engine(
        registry, cfg, ScriptedRng(d4=[1, 2, 3]), [mon("goblin_1", "odd_goblin", "hall")],
        odd_registry(registry, damage_vulnerabilities=["force"]),
    )
    set_hp(engine, "goblin_1", 30)
    engine.perform("wiz", "cast:magic_missile:1:goblin_1")
    assert hp(engine, "goblin_1") == 30 - 18


def test_area_spares_only_the_immune_one(registry, cfg):
    engine = wizard_engine(
        registry, cfg, ScriptedRng(d20=[5, 5], d6=[2, 3, 4]),
        [mon("goblin_1", "odd_goblin", "hall"), mon("goblin_2", "goblin_warrior", "hall")],
        odd_registry(registry, damage_immunities=["fire"]),
    )
    set_hp(engine, "goblin_1", 30)
    set_hp(engine, "goblin_2", 30)
    engine.perform("wiz", "cast:burning_hands:1:hall")
    assert hp(engine, "goblin_1") == 30
    assert hp(engine, "goblin_2") == 21


def test_area_resistance_halves_after_half_on_a_passed_save(registry, cfg):
    # успех спасброска: 9 // 2 = 4; сопротивление: 4 // 2 = 2
    engine = wizard_engine(
        registry, cfg, ScriptedRng(d20=[15], d6=[2, 3, 4]),
        [mon("goblin_1", "odd_goblin", "hall")],
        odd_registry(registry, damage_resistances=["fire"]),
    )
    set_hp(engine, "goblin_1", 30)
    engine.perform("wiz", "cast:burning_hands:1:hall")
    assert hp(engine, "goblin_1") == 28


def test_hazard_zone_is_stopped_by_immunity(registry, cfg):
    zones = make_zones(
        hall=[feature("hazard", damage="1d6", damage_type="fire", save="dex", dc=12)]
    )
    engine = make_engine(
        odd_registry(registry, damage_immunities=["fire"]), cfg, heroes=[make_fighter(registry)],
        zones=zones, rng=ScriptedRng(d20=[5], d6=[4]),
        monsters=[mon("goblin_1", "odd_goblin", "hall")], hero_zone="door",
    )
    hazard_check(engine, "goblin_1")
    assert hp(engine, "goblin_1") == 10
    assert "Иммунитет: 4 → 0 огненный" in lines(engine)


def test_hazard_zone_without_immunity_hurts_the_monster(registry, cfg):
    zones = make_zones(
        hall=[feature("hazard", damage="1d6", damage_type="fire", save="dex", dc=12)]
    )
    engine = make_engine(
        odd_registry(registry), cfg, heroes=[make_fighter(registry)],
        zones=zones, rng=ScriptedRng(d20=[5], d6=[4]),
        monsters=[mon("goblin_1", "odd_goblin", "hall")], hero_zone="door",
    )
    hazard_check(engine, "goblin_1")
    assert hp(engine, "goblin_1") == 6


def marked_shot(registry, cfg, **lists):
    # Метка охотника (1d6 силовым) и выстрел: 15 + 5 попадает; 1d8 (5) + 3 колющим, метка 4
    hero = make_ranger(registry)
    engine = ranger_engine(
        odd_registry(registry, **lists), cfg, ScriptedRng(d20=[15], d8=[5], d6=[4]), hero=hero,
        monsters=[mon("goblin_1", "odd_goblin", "hall")],
    )
    tough(engine)
    engine.perform("hero", "cast:hunters_mark:1:goblin_1")
    engine.perform("hero", SHOOT)
    return engine


def test_mark_damage_without_immunity_is_added(registry, cfg):
    assert hp(marked_shot(registry, cfg), "goblin_1") == 30 - 8 - 4


def test_mark_damage_is_stopped_by_force_immunity(registry, cfg):
    engine = marked_shot(registry, cfg, damage_immunities=["force"])
    assert hp(engine, "goblin_1") == 30 - 8
    assert "Иммунитет: 4 → 0 силовой" in lines(engine)


def test_force_immunity_keeps_the_main_damage_of_the_marked_shot(registry, cfg):
    engine = marked_shot(registry, cfg, damage_immunities=["force"])
    assert hp(engine, "goblin_1") < 30


def test_mark_main_damage_immunity_keeps_the_mark_damage(registry, cfg):
    engine = marked_shot(registry, cfg, damage_immunities=["piercing"])
    assert hp(engine, "goblin_1") == 30 - 4


def special_effects_list():
    return [
        ("Зажигательная стрела", EffectSpec(type="extra_damage", dice="1d6", damage_type="fire"))
    ]


def test_special_damage_is_stopped_by_immunity(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(d6=[4]), damage_immunities=["fire"])
    base = engine.damage("goblin_1", 0, "piercing")
    dealt = special_damage(engine, "hero", "goblin_1", False, base, special_effects_list())
    assert dealt.final == 0
    assert hp(engine, "goblin_1") == 10
    assert dealt.notes == ["Иммунитет: 4 → 0 огненный"]


def test_special_damage_without_immunity_is_added(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(d6=[4]))
    base = engine.damage("goblin_1", 0, "piercing")
    dealt = special_damage(engine, "hero", "goblin_1", False, base, special_effects_list())
    assert dealt.final == 4
    assert hp(engine, "goblin_1") == 6


def test_special_damage_vulnerability_doubles(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(d6=[4]), damage_vulnerabilities=["fire"])
    base = engine.damage("goblin_1", 0, "piercing")
    dealt = special_damage(engine, "hero", "goblin_1", False, base, special_effects_list())
    assert dealt.final == 8


def test_improvised_damage_is_stopped_by_immunity(registry, cfg):
    engine = odd_engine(
        registry, cfg, ScriptedRng(d20=[10], d6=[4]), damage_immunities=["bludgeoning"]
    )
    engine.improvise("hero", skill="athletics", category="medium", effect="extra_damage",
                     target="goblin_1")
    assert hp(engine, "goblin_1") == 10
    assert "Иммунитет: 4 → 0 дробящий" in lines(engine)


def test_improvised_damage_without_immunity_hurts(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(d20=[10], d6=[4]))
    engine.improvise("hero", skill="athletics", category="medium", effect="extra_damage",
                     target="goblin_1")
    assert hp(engine, "goblin_1") == 6


# единственный путь урона

def test_apply_damage_is_called_only_from_the_engine():
    callers = []
    for path in sorted(COMBAT_DIR.rglob("*.py")):
        if re.search(r"\bapply_damage\(", path.read_text(encoding="utf-8")):
            callers.append(path.relative_to(COMBAT_DIR).as_posix())
    assert callers == ["engine.py"]


# смертельный урон по каждому пути: цель убита, убийца записан в событии

def killed_by(events, ref="goblin_1"):
    return [e.data["by"] for e in events if e.type == "monster_died" and e.data["id"] == ref]


def test_burning_kills_and_credits_the_source(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(d4=[3]))
    set_hp(engine, "goblin_1", 1)
    creature(engine, "goblin_1").active_effects.append(
        ActiveEffect(
            id="arrow_fire", source="hero", kind="burning",
            params={"dice": "1d4", "damage_type": "fire"},
        )
    )
    events = engine.burn("goblin_1")
    assert engine.part("goblin_1").status == "dead"
    assert killed_by(events) == ["hero"]


def test_cast_attack_kills_and_credits_the_caster(registry, cfg):
    engine = wizard_engine(
        registry, cfg, ScriptedRng(d20=[10], d10=[7]), [mon("goblin_1", "odd_goblin", "hall")],
        odd_registry(registry),
    )
    set_hp(engine, "goblin_1", 1)
    events = engine.perform("wiz", "cast:fire_bolt:0:goblin_1")
    assert engine.part("goblin_1").status == "dead"
    assert killed_by(events) == ["wiz"]


def test_cast_darts_kill_and_credit_the_caster(registry, cfg):
    engine = wizard_engine(
        registry, cfg, ScriptedRng(d4=[1, 2, 3]), [mon("goblin_1", "odd_goblin", "hall")],
        odd_registry(registry),
    )
    set_hp(engine, "goblin_1", 1)
    events = engine.perform("wiz", "cast:magic_missile:1:goblin_1")
    assert engine.part("goblin_1").status == "dead"
    assert killed_by(events) == ["wiz"]


def test_area_kills_and_credits_the_caster(registry, cfg):
    engine = wizard_engine(
        registry, cfg, ScriptedRng(d20=[5], d6=[2, 3, 4]), [mon("goblin_1", "odd_goblin", "hall")],
        odd_registry(registry),
    )
    set_hp(engine, "goblin_1", 1)
    events = engine.perform("wiz", "cast:burning_hands:1:hall")
    assert engine.part("goblin_1").status == "dead"
    assert killed_by(events) == ["wiz"]


def test_hazard_kills_without_a_killer(registry, cfg):
    zones = make_zones(
        hall=[feature("hazard", damage="1d6", damage_type="fire", save="dex", dc=12)]
    )
    engine = make_engine(
        odd_registry(registry), cfg, heroes=[make_fighter(registry)], zones=zones,
        rng=ScriptedRng(d20=[5], d6=[4]), monsters=[mon("goblin_1", "odd_goblin", "hall")],
        hero_zone="door",
    )
    set_hp(engine, "goblin_1", 1)
    events = hazard_check(engine, "goblin_1")
    assert engine.part("goblin_1").status == "dead"
    assert killed_by(events) == [None]


def test_improvised_damage_kills_and_credits_the_hero(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(d20=[10], d6=[4]))
    set_hp(engine, "goblin_1", 1)
    engine.improvise("hero", skill="athletics", category="medium", effect="extra_damage",
                     target="goblin_1")
    assert engine.part("goblin_1").status == "dead"


def test_graze_kills_and_credits_the_attacker(registry, cfg):
    hero = make_fighter(registry)
    hero.sheet.weapon_masteries = ["greatsword"]
    give_weapon(hero, registry, "greatsword")
    engine = odd_engine(registry, cfg, ScriptedRng(d20=[1]), hero=hero)
    set_hp(engine, "goblin_1", 1)
    events = engine.perform("hero", "attack:greatsword:goblin_1")
    assert engine.part("goblin_1").status == "dead"
    assert killed_by(events) == ["hero"]


# часы мира: истёкшее сопротивление эффекта не действует

def resist_engine(registry, cfg, ends_s, now_s):
    from ai_dm.state.creature import Expiry

    engine = odd_engine(registry, cfg, ScriptedRng())
    engine.world.clock.now_s = now_s
    creature(engine, "hero").active_effects.append(
        ActiveEffect(
            id="stone_skin", source="hero", kind="resist", params={"damage_type": "slashing"},
            expires=Expiry(kind="seconds", value=ends_s),
        )
    )
    return engine


def test_live_effect_resistance_works_by_the_world_clock(registry, cfg):
    assert resist_engine(registry, cfg, 1000, 500).damage("hero", 6, "slashing").final == 3


def test_expired_effect_resistance_does_not_work(registry, cfg):
    assert resist_engine(registry, cfg, 1000, 2000).damage("hero", 6, "slashing").final == 6


# слияние урона метки и особого урона; пропуск чужих эффектов

def mark_effect(source="hero"):
    return ActiveEffect(
        id="hunters_mark", source=source, kind="mark",
        params={"dice": "1d6", "damage_type": "force"},
    )


def test_mark_damage_merges_all_fields_of_both_hits(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(d6=[4]))
    creature(engine, "goblin_1").active_effects.append(mark_effect())
    base = engine.damage("goblin_1", 3, "piercing")
    merged = mark_damage(engine, "hero", "goblin_1", False, base)
    assert (merged.final, merged.hp_lost, merged.raw) == (7, 7, 7)
    assert (merged.temp_absorbed, merged.overkill, merged.dropped) == (0, 0, False)


def test_mark_damage_merges_overkill_and_drop(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(d6=[6]))
    set_hp(engine, "goblin_1", 5)
    creature(engine, "goblin_1").active_effects.append(mark_effect())
    base = engine.damage("goblin_1", 3, "piercing")
    merged = mark_damage(engine, "hero", "goblin_1", False, base)
    assert (merged.hp_lost, merged.overkill, merged.dropped) == (5, 4, True)


def test_mark_damage_merges_temp_hp_absorption(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(d6=[4]))
    creature(engine, "goblin_1").hp_temp = 5
    creature(engine, "goblin_1").active_effects.append(mark_effect())
    base = engine.damage("goblin_1", 3, "piercing")
    merged = mark_damage(engine, "hero", "goblin_1", False, base)
    assert merged.temp_absorbed == 5


def test_mark_damage_skips_foreign_marks_and_other_effects(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(d6=[4]))
    effects = creature(engine, "goblin_1").active_effects
    effects.append(ActiveEffect(id="sap", source="hero", kind="modifier", params={}))
    effects.append(mark_effect("someone"))
    effects.append(mark_effect())
    base = engine.damage("goblin_1", 3, "piercing")
    merged = mark_damage(engine, "hero", "goblin_1", False, base)
    assert merged.final == 7


def test_special_damage_skips_effects_of_other_types(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(d6=[4]))
    base = engine.damage("goblin_1", 0, "piercing")
    effects = [("Огниво", EffectSpec(type="burn", dice="1d4", damage_type="fire"))]
    effects += special_effects_list()
    assert special_damage(engine, "hero", "goblin_1", False, base, effects).final == 4


def test_special_damage_skips_effects_aimed_at_other_tags(registry, cfg):
    engine = odd_engine(registry, cfg, ScriptedRng(d6=[4]))
    base = engine.damage("goblin_1", 0, "piercing")
    effects = [
        ("Серебро", EffectSpec(type="extra_damage", dice="1d4", damage_type="radiant",
                               vs=["undead"])),
    ]
    effects += special_effects_list()
    assert special_damage(engine, "hero", "goblin_1", False, base, effects).final == 4
