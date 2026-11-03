# К3 П3б (docs/plan-k3.md, «Тесты» П3, решения 26, 40): Помощь в бою (вид max_hp).
#   id пункта: cast:aid:<круг>:<цель>[,<цель>[,<цель>]] -- от одной до трёх союзников (targets: 3),
#     цели в пределах дальности 30 фт. (своя и соседняя зона); одна ячейка, концентрации нет;
#   на каждую цель: hp_max и hp_current +5 (круг выше 2-го -- +5 за круг),
#     ActiveEffect(kind="max_hp", params amount, expires seconds = now + 8 ч);
#     повтор на той же цели не складывается;
#   откат: combat.end.release_concentration снимает прибавку по часам мира и пишет в лог боя
#     «Помощь кончилась: <имя> HP a/b»; до срока -- ничего.
#   inert_spells: Помощь больше не «без механики».
from combat_kit import (
    ScriptedRng,
    creature,
    hp,
    make_fighter,
    option_ids,
    part,
)
from test_cast_p3a import cast_ids, effects, engine_of, mage, pass_turns, slot

from ai_dm.combat.actions.cast import inert_spells
from ai_dm.combat.actions.cast_effects import cast_max_hp
from ai_dm.combat.controllers import ScriptedController
from ai_dm.combat.end import release_concentration
from ai_dm.rules.results import Rejected
from ai_dm.rules.spellcasting import spell_kind

EIGHT_HOURS = 8 * 3600


def party(registry, cfg, hp_max=10):
    caster = mage(registry, "aid")
    allies = []
    for name in ("ally", "ally2"):
        ally = make_fighter(registry, name)
        ally.creature.hp_max = ally.creature.hp_current = hp_max
        allies.append((ally, "hall"))
    caster.creature.hp_max = caster.creature.hp_current = hp_max
    refs = ["wiz", "ally", "ally2", "goblin_1"]
    controllers = {ref: ScriptedController([]) for ref in refs}
    return engine_of(
        registry, cfg, caster, ScriptedRng(), extra=allies, controllers=controllers
    )


def next_turn(engine):
    # круг пассивных ходов и новый ход заклинателя: действие снова доступно
    pass_turns(engine, 3)
    engine.start_turn("wiz")


def max_of(engine, ref):
    return creature(engine, ref).hp_max


def test_aid_is_not_inert_for_a_caster(registry, cfg):
    engine = party(registry, cfg)
    assert "aid" not in [s.id for s in inert_spells(engine, "wiz")]


def test_cleric_full_list_has_thirteen_inert_spells_after_p3b(registry, cfg):
    # 11 К3б + spiritual_weapon + spirit_guardians; aid -- уже с механикой (после П4 останется 11)
    cleric = [
        s for s in registry.all("spell") if "cleric" in s.classes and s.level <= 3
    ]
    hero = mage(registry)
    hero.sheet.known_of()[:] = [s.id for s in cleric if s.level == 0]
    hero.sheet.prepared_of()[:] = [s.id for s in cleric if s.level > 0]
    engine = engine_of(registry, cfg, hero)
    inert = [s.id for s in inert_spells(engine, "wiz")]
    assert "aid" not in inert
    assert len(inert) == 13


def test_aid_has_the_max_hp_kind(registry):
    assert spell_kind(registry.get("spell", "aid")) == "max_hp"


def test_aid_offers_one_two_and_three_targets(registry, cfg):
    ids = cast_ids(party(registry, cfg), "aid")
    assert "cast:aid:2:ally" in ids
    assert "cast:aid:2:ally,ally2" in ids
    assert "cast:aid:2:wiz,ally,ally2" in ids


def test_aid_offers_no_more_than_three_targets(registry, cfg):
    ids = cast_ids(party(registry, cfg), "aid")
    assert [i for i in ids if len(i.split(":")[3].split(",")) > 3] == []


def test_aid_cannot_target_an_enemy(registry, cfg):
    ids = cast_ids(party(registry, cfg), "aid")
    assert not [i for i in ids if "goblin_1" in i]


def test_aid_is_offered_at_the_base_and_a_higher_circle(registry, cfg):
    ids = option_ids(party(registry, cfg), "wiz")
    assert "cast:aid:2:ally" in ids
    assert "cast:aid:3:ally" in ids


def test_aid_on_a_distant_ally_is_not_offered(registry, cfg):
    engine = party(registry, cfg)
    part(engine, "ally2").zone_id = "balcony"
    ids = cast_ids(engine, "aid")
    assert "cast:aid:2:ally" in ids
    assert not [i for i in ids if "ally2" in i]


def test_aid_raises_max_and_current_hp_of_every_target(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:aid:2:ally,ally2")
    for ref in ("ally", "ally2"):
        assert (max_of(engine, ref), hp(engine, ref)) == (15, 15)


def test_aid_leaves_the_untargeted_caster_alone(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:aid:2:ally,ally2")
    assert (max_of(engine, "wiz"), hp(engine, "wiz")) == (10, 10)


def test_aid_records_an_effect_for_eight_hours(registry, cfg):
    engine = party(registry, cfg)
    start = engine.world.clock.now_s
    engine.perform("wiz", "cast:aid:2:ally")
    [effect] = effects(engine, "ally", "aid")
    assert (effect.kind, effect.source, effect.params["amount"]) == ("max_hp", "wiz", 5)
    assert (effect.expires.kind, effect.expires.value) == ("seconds", start + EIGHT_HOURS)


def test_aid_costs_one_slot_and_no_concentration(registry, cfg):
    engine = party(registry, cfg)
    before = slot(engine, 2)
    engine.perform("wiz", "cast:aid:2:ally,ally2")
    assert slot(engine, 2) == before - 1
    assert engine.heroes["wiz"].creature.concentration is None


def test_aid_at_the_third_circle_gives_ten(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:aid:3:ally")
    assert (max_of(engine, "ally"), hp(engine, "ally")) == (20, 20)
    assert effects(engine, "ally", "aid")[0].params["amount"] == 10


def test_aid_repeat_on_the_same_target_does_not_stack(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:aid:2:ally")
    next_turn(engine)
    engine.perform("wiz", "cast:aid:2:ally")
    assert max_of(engine, "ally") == 15
    assert len(effects(engine, "ally", "aid")) == 1


def test_aid_with_a_repeated_target_is_rejected(registry, cfg):
    engine = party(registry, cfg)
    before = slot(engine, 2)
    assert isinstance(engine.perform("wiz", "cast:aid:2:ally,ally"), Rejected)
    assert slot(engine, 2) == before


def test_aid_with_four_targets_is_rejected(registry, cfg):
    engine = party(registry, cfg)
    result = engine.perform("wiz", "cast:aid:2:ally,ally2,wiz,goblin_1")
    assert isinstance(result, Rejected)


def test_aid_writes_a_log_line_with_the_bonus_and_targets(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:aid:2:ally")
    [line] = [x for x in engine.state.log if "Помощь (+5 HP)" in x]
    assert engine.name("ally") in line


def test_aid_log_line_lists_every_target_with_hp(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:aid:2:ally,ally2")
    [line] = [x for x in engine.state.log if "Помощь (+5 HP)" in x]
    expected = ", ".join(f"{engine.name(r)} {engine.hp_text(r)}" for r in ("ally", "ally2"))
    assert line.endswith(f"на {expected}")


def test_upcast_without_a_per_circle_value_adds_nothing(registry, cfg):
    engine = party(registry, cfg)
    spell = registry.get("spell", "aid").model_copy(deep=True)
    spell.upcast.per_slot_level.value = None
    cast_max_hp(engine, "wiz", spell, "ally", 3)
    assert effects(engine, "ally", "aid")[0].params["amount"] == 5


def test_aid_with_only_weaker_targets_has_no_cast_line(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:aid:3:ally")
    next_turn(engine)
    engine.perform("wiz", "cast:aid:2:ally")
    assert [x for x in engine.state.log if "Помощь (+5 HP)" in x] == []


# Р43 (решение 64): повтор слабее действующей Помощи ничего не меняет, равная или сильнее заменяет

STRONGER = "уже под более сильной Помощью"


def test_weaker_repeat_keeps_the_stronger_bonus(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:aid:3:ally")
    next_turn(engine)
    engine.perform("wiz", "cast:aid:2:ally")
    assert (max_of(engine, "ally"), hp(engine, "ally")) == (20, 20)
    assert [e.params["amount"] for e in effects(engine, "ally", "aid")] == [10]


def test_weaker_repeat_keeps_the_old_term(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:aid:3:ally")
    old = effects(engine, "ally", "aid")[0].expires.value
    engine.world.clock.advance(600)
    next_turn(engine)
    engine.perform("wiz", "cast:aid:2:ally")
    assert effects(engine, "ally", "aid")[0].expires.value == old


def test_weaker_repeat_still_spends_the_slot(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:aid:3:ally")
    next_turn(engine)
    before = slot(engine, 2)
    engine.perform("wiz", "cast:aid:2:ally")
    assert slot(engine, 2) == before - 1


def test_weaker_repeat_says_the_target_is_under_a_stronger_aid(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:aid:3:ally")
    next_turn(engine)
    engine.perform("wiz", "cast:aid:2:ally")
    assert any(STRONGER in line and engine.name("ally") in line for line in engine.state.log)


def test_weaker_repeat_on_two_targets_changes_only_the_new_one(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:aid:3:ally")
    next_turn(engine)
    engine.perform("wiz", "cast:aid:2:ally,ally2")
    assert max_of(engine, "ally") == 20
    assert max_of(engine, "ally2") == 15


def test_stronger_repeat_replaces_the_weaker_one(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:aid:2:ally")
    next_turn(engine)
    engine.perform("wiz", "cast:aid:3:ally")
    assert (max_of(engine, "ally"), hp(engine, "ally")) == (20, 20)
    assert [e.params["amount"] for e in effects(engine, "ally", "aid")] == [10]


def test_equal_repeat_renews_the_term_without_the_stronger_line(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:aid:2:ally")
    engine.world.clock.advance(600)
    next_turn(engine)
    engine.perform("wiz", "cast:aid:2:ally")
    assert effects(engine, "ally", "aid")[0].expires.value == (
        engine.world.clock.now_s + EIGHT_HOURS
    )
    assert not any(STRONGER in line for line in engine.state.log)


def test_release_reverts_aid_after_eight_hours_and_logs_it(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:aid:2:ally")
    engine.world.clock.advance(EIGHT_HOURS)
    release_concentration(engine)
    assert (max_of(engine, "ally"), hp(engine, "ally")) == (10, 10)
    assert effects(engine, "ally", "aid") == []
    assert f"Помощь кончилась: {engine.heroes['ally'].name} HP 10/10" in engine.state.log


def test_release_keeps_the_wound_of_a_reverted_aid(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:aid:2:ally")
    creature(engine, "ally").hp_current = 8
    engine.world.clock.advance(EIGHT_HOURS)
    release_concentration(engine)
    assert hp(engine, "ally") == 8


def test_release_keeps_aid_before_the_term(registry, cfg):
    engine = party(registry, cfg)
    engine.perform("wiz", "cast:aid:2:ally")
    engine.world.clock.advance(EIGHT_HOURS - 1)
    release_concentration(engine)
    assert max_of(engine, "ally") == 15
    assert not any("Помощь кончилась" in line for line in engine.state.log)
