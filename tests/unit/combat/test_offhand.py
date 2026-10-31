# Шаг К2, П2: удар второй рукой (docs/plan-k2.md, решения 3, 9, 15; combat/offhand.py).
#   * пункт offhand_attack:<цель> появляется только после Атаки лёгким оружием (флаг light_attack)
#     и только если в левой руке лёгкое оружие (не то же самое, если предмет один);
#   * цена -- бонусное действие; подпись «Удар второй рукой: <оружие> → <цель>»;
#   * Проворство (Nick в мастерствах героя): цена free, подпись «Удар второй рукой (Проворство):
#     ...»,
#     бонусное действие остаётся; раз за ход (флаг offhand_used);
#   * урон без модификатора характеристики, если он неотрицательный; отрицательный вычитается; со
#     стилем «Бой двумя оружиями» модификатор прибавляется.
from combat_kit import (
    ScriptedRng,
    creature,
    give_weapon,
    hp,
    make_engine,
    make_fighter,
    mon,
    option_ids,
    set_hp,
    turn,
)

from ai_dm.rules.inventory import add_item, equip

OFF = "offhand_attack:goblin_1"


def dual(registry, cfg, rng, main="shortsword", off="dagger", masteries=(), feats=(), copies=1):
    # Лов 16 (+3), Сил 8 (-1); оба оружия в руках, щита нет; у гоблина 40 HP
    hero = make_fighter(registry)
    hero.sheet.abilities["dex"] = 16
    hero.sheet.abilities["str"] = 8
    hero.equipped.shield = None
    hero.sheet.weapon_masteries = list(masteries)
    hero.sheet.feats += list(feats)
    give_weapon(hero, registry, main)
    add_item(hero, off, copies, cost_cp=0)
    equip(hero, off, registry, "off_hand")
    engine = make_engine(
        registry, cfg, heroes=[hero], rng=rng, monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    creature(engine, "goblin_1").hp_max = 40
    set_hp(engine, "goblin_1", 40)
    return engine


def main_attack(engine, weapon="shortsword"):
    engine.perform("hero", f"attack:{weapon}:goblin_1")


def offhand(engine):
    return [o for o in engine.available_actions("hero") if o.kind == "offhand_attack"]


def rng_hits(**dice):
    return ScriptedRng(d20=[15, 15], **dice)


# --- когда пункт есть ---

def test_no_offhand_option_before_the_attack(registry, cfg):
    engine = dual(registry, cfg, ScriptedRng())
    assert offhand(engine) == []


def test_offhand_option_appears_after_a_light_attack(registry, cfg):
    engine = dual(registry, cfg, rng_hits(d6=[3]))
    main_attack(engine)
    assert option_ids(engine, "hero").count(OFF) == 1


def test_offhand_option_costs_the_bonus_action(registry, cfg):
    engine = dual(registry, cfg, rng_hits(d6=[3]))
    main_attack(engine)
    assert offhand(engine)[0].cost == "bonus"


def test_offhand_option_label_names_the_weapon_and_the_target(registry, cfg):
    engine = dual(registry, cfg, rng_hits(d6=[3]))
    main_attack(engine)
    assert offhand(engine)[0].label == "Удар второй рукой: кинжал → Воин-гоблин"


def test_attack_with_a_non_light_weapon_gives_no_option(registry, cfg):
    engine = dual(registry, cfg, rng_hits(d8=[3]), main="longsword")
    main_attack(engine, "longsword")
    assert offhand(engine) == []


def test_attack_with_a_heavy_weapon_gives_no_option(registry, cfg):
    hero = make_fighter(registry)
    give_weapon(hero, registry, "greatsword")
    engine = make_engine(
        registry, cfg, heroes=[hero], rng=rng_hits(d6=[3, 3]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    engine.perform("hero", "attack:greatsword:goblin_1")
    assert offhand(engine) == []


def test_empty_left_hand_gives_no_option(registry, cfg):
    engine = dual(registry, cfg, rng_hits(d6=[3]))
    engine.heroes["hero"].equipped.off_hand = None
    main_attack(engine)
    assert offhand(engine) == []


def test_the_same_single_item_is_not_offered_for_both_hands(registry, cfg):
    # кинжал в правой руке атаковал; кинжал в левой -- тот же единственный предмет: удара нет
    engine = dual(registry, cfg, rng_hits(d4=[3]))
    engine.heroes["hero"].equipped.main_hand = "dagger"
    main_attack(engine, "dagger")
    assert offhand(engine) == []


def test_two_copies_of_one_weapon_allow_the_offhand_blow(registry, cfg):
    engine = dual(registry, cfg, rng_hits(d4=[3]), main="dagger", off="dagger", copies=1)
    main_attack(engine, "dagger")
    assert len(offhand(engine)) == 1


def test_no_option_without_the_bonus_action(registry, cfg):
    engine = dual(registry, cfg, rng_hits(d6=[3]))
    main_attack(engine)
    turn(engine, "hero").bonus = False
    assert offhand(engine) == []


# --- урон ---

def test_offhand_blow_adds_no_nonnegative_modifier(registry, cfg):
    # кинжал 1d4 без Лов +3
    engine = dual(registry, cfg, rng_hits(d6=[3], d4=[2]))
    main_attack(engine)
    before = hp(engine, "goblin_1")
    engine.perform("hero", OFF)
    assert before - hp(engine, "goblin_1") == 2


def test_offhand_blow_keeps_a_negative_modifier(registry, cfg):
    # ручной топор (Сил, без финесса): 1d6 - 1
    engine = dual(registry, cfg, rng_hits(d6=[3, 4]), off="handaxe")
    main_attack(engine)
    before = hp(engine, "goblin_1")
    engine.perform("hero", OFF)
    assert before - hp(engine, "goblin_1") == 3


def test_two_weapon_fighting_adds_the_modifier(registry, cfg):
    engine = dual(registry, cfg, rng_hits(d6=[3], d4=[2]), feats=["two_weapon_fighting"])
    main_attack(engine)
    before = hp(engine, "goblin_1")
    engine.perform("hero", OFF)
    assert before - hp(engine, "goblin_1") == 2 + 3


def test_the_main_hand_blow_still_adds_the_modifier(registry, cfg):
    engine = dual(registry, cfg, rng_hits(d6=[3]))
    main_attack(engine)
    assert 40 - hp(engine, "goblin_1") == 3 + 3


# --- расход ---

def test_offhand_blow_spends_the_bonus_action(registry, cfg):
    engine = dual(registry, cfg, rng_hits(d6=[3], d4=[2]))
    main_attack(engine)
    engine.perform("hero", OFF)
    assert turn(engine, "hero").bonus is False


def test_offhand_blow_is_once_per_turn(registry, cfg):
    engine = dual(registry, cfg, rng_hits(d6=[3], d4=[2]))
    main_attack(engine)
    engine.perform("hero", OFF)
    turn(engine, "hero").bonus = True
    assert offhand(engine) == []


def test_offhand_blow_does_not_spend_the_action_or_attacks(registry, cfg):
    engine = dual(registry, cfg, rng_hits(d6=[3], d4=[2]))
    main_attack(engine)
    turn(engine, "hero").action = True
    engine.perform("hero", OFF)
    assert turn(engine, "hero").action is True


# --- Проворство ---

def test_nick_makes_the_blow_free(registry, cfg):
    engine = dual(registry, cfg, rng_hits(d6=[3], d4=[2]), masteries=["dagger"])
    main_attack(engine)
    assert offhand(engine)[0].cost == "free"


def test_nick_label_has_the_mastery_note(registry, cfg):
    engine = dual(registry, cfg, rng_hits(d6=[3], d4=[2]), masteries=["dagger"])
    main_attack(engine)
    assert offhand(engine)[0].label == "Удар второй рукой (Проворство): кинжал → Воин-гоблин"


def test_nick_blow_keeps_the_bonus_action(registry, cfg):
    engine = dual(registry, cfg, rng_hits(d6=[3], d4=[2]), masteries=["dagger"])
    main_attack(engine)
    engine.perform("hero", OFF)
    assert turn(engine, "hero").bonus is True


def test_nick_blow_is_once_per_turn(registry, cfg):
    engine = dual(registry, cfg, rng_hits(d6=[3], d4=[2]), masteries=["dagger"])
    main_attack(engine)
    engine.perform("hero", OFF)
    assert offhand(engine) == []


def test_bonus_blow_blocks_the_nick_blow_in_the_same_turn(registry, cfg):
    # раз за ход на оба способа (SRD: Проворство лишь переносит лишнюю атаку Light в Атаку)
    engine = dual(registry, cfg, rng_hits(d6=[3], d4=[2]))
    main_attack(engine)
    engine.perform("hero", OFF)
    engine.heroes["hero"].sheet.weapon_masteries = ["dagger"]
    assert offhand(engine) == []


def test_without_the_mastery_choice_the_blow_costs_the_bonus_action(registry, cfg):
    engine = dual(registry, cfg, rng_hits(d6=[3], d4=[2]), masteries=["shortsword"])
    main_attack(engine)
    assert offhand(engine)[0].cost == "bonus"


def test_the_mark_goes_away_in_the_next_turn(registry, cfg):
    engine = dual(registry, cfg, rng_hits(d6=[3]))
    main_attack(engine)
    engine.expire("end_of_turn", "hero")
    flags = [e.id for e in creature(engine, "hero").active_effects]
    assert "light_attack" not in flags
