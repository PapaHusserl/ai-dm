# Спасброски ЛОВ от площади (ревью партии 5, п. 10): burning_hands (конус из своей зоны, СЛ 13,
# 3d6 -- гоблины в зале, заклинатель у двери).
#   Укрытие зоны цели (cover_half +2, cover_three_quarters +5, больший, не сумма) прибавляется к
#     спасброску ЛОВ существа, стоящего в зоне укрытия, если источник (заклинатель) в ДРУГОЙ зоне;
#     в одной зоне с источником укрытия нет; к спасброскам других характеристик не относится.
#   Dodge (вариант dodge, действие) даёт преимущество на спасброски ЛОВ: два d20, берётся больший.
# ЛОВ гоблина +2: d20 10 + 2 = 12 < 13 (провал); с укрытием 14 (успех, половина урона вниз).
# 3d6 = 2 + 3 + 4 = 9: провал -- 9, успех -- 4.
from combat_kit import ScriptedRng, feature, hp, make_engine, make_wizard, make_zones, mon, set_hp


def hands(registry, cfg, rng, hall=(), caster_zone="door"):
    engine = make_engine(
        registry, cfg, heroes=[(make_wizard(registry), caster_zone)], rng=rng,
        zones=make_zones(hall=hall),
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "hall")],
    )
    set_hp(engine, "goblin_1", 30)
    set_hp(engine, "goblin_2", 30)
    return engine


def test_without_cover_the_save_fails(registry, cfg):
    engine = hands(registry, cfg, ScriptedRng(d20=[10, 10], d6=[2, 3, 4]))
    engine.perform("wiz", "cast:burning_hands:1:hall")
    assert hp(engine, "goblin_1") == 21
    assert hp(engine, "goblin_2") == 21


def test_half_cover_adds_2_to_the_dex_save(registry, cfg):
    engine = hands(
        registry, cfg, ScriptedRng(d20=[10, 10], d6=[2, 3, 4]), hall=[feature("cover_half")]
    )
    engine.perform("wiz", "cast:burning_hands:1:hall")
    assert hp(engine, "goblin_1") == 26
    assert hp(engine, "goblin_2") == 26


def test_half_cover_is_not_enough_for_a_low_roll(registry, cfg):
    # 7 + 2 + 2 = 11 < 13
    engine = hands(
        registry, cfg, ScriptedRng(d20=[7, 7], d6=[2, 3, 4]), hall=[feature("cover_half")]
    )
    engine.perform("wiz", "cast:burning_hands:1:hall")
    assert hp(engine, "goblin_1") == 21


def test_three_quarters_cover_adds_5_to_the_dex_save(registry, cfg):
    # 7 + 2 + 5 = 14 >= 13
    engine = hands(
        registry, cfg, ScriptedRng(d20=[7, 7], d6=[2, 3, 4]),
        hall=[feature("cover_three_quarters")],
    )
    engine.perform("wiz", "cast:burning_hands:1:hall")
    assert hp(engine, "goblin_1") == 26


def test_the_larger_cover_counts_not_the_sum(registry, cfg):
    # +5, а не +7: 5 + 2 + 5 = 12 < 13
    engine = hands(
        registry, cfg, ScriptedRng(d20=[5, 5], d6=[2, 3, 4]),
        hall=[feature("cover_half"), feature("cover_three_quarters")],
    )
    engine.perform("wiz", "cast:burning_hands:1:hall")
    assert hp(engine, "goblin_1") == 21


def test_cover_does_not_help_against_a_source_in_the_same_zone(registry, cfg):
    engine = hands(
        registry, cfg, ScriptedRng(d20=[10, 10], d6=[2, 3, 4]), hall=[feature("cover_half")],
        caster_zone="hall",
    )
    engine.perform("wiz", "cast:burning_hands:1:hall")
    assert hp(engine, "goblin_1") == 21
    assert hp(engine, "goblin_2") == 21


# Dodge

def test_dodging_creature_saves_dex_with_advantage(registry, cfg):
    # goblin_1 уклоняется: d20 5 и 15 -> 15 + 2 = 17 успех; goblin_2 без уклонения: 5 + 2 = 7 провал
    engine = hands(registry, cfg, ScriptedRng(d20=[5, 15, 5], d6=[2, 3, 4]))
    engine.perform("goblin_1", "dodge")
    engine.perform("wiz", "cast:burning_hands:1:hall")
    assert hp(engine, "goblin_1") == 26
    assert hp(engine, "goblin_2") == 21


def test_dodge_advantage_takes_the_better_of_two_dice(registry, cfg):
    # 15 и 5: берётся 15; порядок бросков не должен иметь значения
    engine = hands(registry, cfg, ScriptedRng(d20=[15, 5, 5], d6=[2, 3, 4]))
    engine.perform("goblin_1", "dodge")
    engine.perform("wiz", "cast:burning_hands:1:hall")
    assert hp(engine, "goblin_1") == 26
