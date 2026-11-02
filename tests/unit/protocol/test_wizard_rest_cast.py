# К3 П2 (docs/plan-k3.md, «Тесты» П2): волшебник в протоколе.
#   * cast_spell{ritual: true}: заклинание-ритуал из книги без подготовки -- ячейка не тратится,
#     часы +600 с (RITUAL_SECONDS), строка лога с «ритуал»; не ритуал -> Invalid not_ritual;
#     неподготовленный ритуал жреца -> not_prepared; другой круг -> bad_circle;
#   * rest{short}: Магическое восстановление возвращает ячейку (rest_apply), пул тратится, второй
#     короткий отдых без восстановления, длинный возвращает пул;
#   * rest{short, prepared_swap}: без Запоминания заклинания (до 5 ур.) -> swap_long_only; с ним
#     (5 ур.) одна замена из книги проходит, две -> swap_limit; замена не из книги -> Invalid.
import sys
from pathlib import Path

import game_kit  # noqa: F401  (добавляет в sys.path соседние kit-ы)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rules"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "content"))

import pytest  # noqa: E402
from protocol_kit import dump, make_bundle, make_ctx, req  # noqa: E402
from test_builder import wizard_choices  # noqa: E402
from test_class_kits import minimal_choices  # noqa: E402

from ai_dm.protocol.apply import apply  # noqa: E402
from ai_dm.protocol.decision import Invalid  # noqa: E402
from ai_dm.rules.builder import build_character  # noqa: E402
from ai_dm.rules.progression import level_up  # noqa: E402

BOOK = ["alarm", "burning_hands", "magic_missile", "shield", "sleep", "detect_magic"]
PREPARED = ["magic_missile", "shield", "sleep", "detect_magic"]


def bundle_with(registry, hero):
    bundle = make_bundle(registry)
    hero.location_id = "vale"
    bundle.heroes[0] = hero
    return bundle


def wizard_bundle(registry, level=1):
    choices = wizard_choices(
        spells=["fire_bolt", "light", "mage_hand", *BOOK], prepared=PREPARED, hero_id="hero",
    )
    hero = build_character(choices, registry)
    while hero.sheet.level < level:
        level_up(hero, registry, hp_method="average")
    return bundle_with(registry, hero)


def cleric_bundle(registry, prepared=()):
    choices = minimal_choices("cleric", "a").model_copy(update={"hero_id": "hero"})
    hero = build_character(choices, registry)
    hero.sheet.prepared_of()[:] = list(prepared)
    return bundle_with(registry, hero)


def cast(registry, cfg, bundle, spell_id, **fields):
    ctx = make_ctx(registry, cfg, bundle=bundle)
    spell = registry.get("spell", spell_id)
    data = {"spell_id": spell_id, "circle": spell.level, "target": "hero", "free": False} | fields
    return ctx, apply(ctx, req("cast_spell", **data))


def rest(registry, cfg, bundle, kind="short", **fields):
    ctx = make_ctx(registry, cfg, bundle=bundle)
    return ctx, apply(ctx, req("rest", kind=kind, **fields))


def slot(bundle, circle=1):
    return bundle.heroes[0].creature.resources[f"spell_slot:{circle}"]


# ритуал

def test_book_ritual_is_accepted_without_preparing(registry, cfg):
    bundle = wizard_bundle(registry)
    assert "alarm" not in bundle.heroes[0].sheet.prepared_of()
    _, d = cast(registry, cfg, bundle, "alarm", ritual=True)
    assert d.status == "accepted"


def test_ritual_does_not_spend_a_slot(registry, cfg):
    bundle = wizard_bundle(registry)
    before = slot(bundle).current
    cast(registry, cfg, bundle, "alarm", ritual=True)
    assert slot(bundle).current == before


def test_ritual_takes_ten_extra_minutes(registry, cfg):
    bundle = wizard_bundle(registry)
    start = bundle.world.clock.now_s
    cast(registry, cfg, bundle, "alarm", ritual=True)
    assert bundle.world.clock.now_s == start + 600


def test_ritual_log_names_the_ritual(registry, cfg):
    bundle = wizard_bundle(registry)
    _, d = cast(registry, cfg, bundle, "alarm", ritual=True)
    assert any("ритуал" in line for line in d.log)


def test_ordinary_cast_of_the_same_spell_still_needs_preparation(registry, cfg):
    bundle = wizard_bundle(registry)
    _, d = cast(registry, cfg, bundle, "alarm")
    assert isinstance(d, Invalid)
    assert d.code == "not_prepared"


def test_non_ritual_spell_as_ritual_is_invalid_and_changes_nothing(registry, cfg):
    bundle = wizard_bundle(registry)
    ctx = make_ctx(registry, cfg, bundle=bundle)
    before = dump(ctx)
    _, d = cast(registry, cfg, bundle, "magic_missile", ritual=True)
    assert isinstance(d, Invalid)
    assert d.code == "not_ritual"
    assert dump(ctx) == before


def test_ritual_with_a_higher_circle_is_bad_circle_and_free_of_cost(registry, cfg):
    bundle = wizard_bundle(registry, 3)
    start = bundle.world.clock.now_s
    before = slot(bundle, 2).current
    _, d = cast(registry, cfg, bundle, "alarm", ritual=True, circle=2)
    assert isinstance(d, Invalid)
    assert d.code == "bad_circle"
    assert slot(bundle, 2).current == before
    assert bundle.world.clock.now_s == start


def test_cleric_unprepared_ritual_is_not_prepared(registry, cfg):
    bundle = cleric_bundle(registry)
    start = bundle.world.clock.now_s
    _, d = cast(registry, cfg, bundle, "detect_magic", ritual=True)
    assert isinstance(d, Invalid)
    assert d.code == "not_prepared"
    assert bundle.world.clock.now_s == start


def test_cleric_prepared_ritual_is_accepted_and_free(registry, cfg):
    bundle = cleric_bundle(registry, ["detect_magic"])
    before = slot(bundle).current
    _, d = cast(registry, cfg, bundle, "detect_magic", ritual=True)
    assert d.status == "accepted"
    assert slot(bundle).current == before


def doubting_cleric(registry):
    # благосклонность -3: перед сотворением заклинания проверка Мудрости СЛ 10
    bundle = cleric_bundle(registry, ["detect_magic"])
    hero = bundle.heroes[0]
    hero.deity_id = "selune"
    hero.favor["selune"] = -3
    hero.sheet.abilities["wis"] = 10
    return bundle


def test_failed_ritual_check_says_the_ten_minutes_are_wasted(registry, cfg):
    from protocol_kit import ScriptedRng

    bundle = doubting_cleric(registry)
    ctx = make_ctx(registry, cfg, rng=ScriptedRng(d20=[2]), bundle=bundle)
    d = apply(ctx, req("cast_spell", spell_id="detect_magic", circle=1, target="hero",
                       free=False, ritual=True))
    assert d.status == "accepted"
    assert d.result["wasted"] is True
    assert any("ритуал не удался, десять минут потрачены впустую" in x for x in d.log)
    assert not any("ячейка потрачена впустую" in x for x in d.log)


def test_failed_ritual_check_does_not_spend_a_slot_but_takes_the_time(registry, cfg):
    from protocol_kit import ScriptedRng

    bundle = doubting_cleric(registry)
    before = slot(bundle).current
    start = bundle.world.clock.now_s
    ctx = make_ctx(registry, cfg, rng=ScriptedRng(d20=[2]), bundle=bundle)
    apply(ctx, req("cast_spell", spell_id="detect_magic", circle=1, target="hero",
                   free=False, ritual=True))
    assert slot(bundle).current == before
    assert bundle.world.clock.now_s == start + 600


def test_failed_ritual_line_is_exactly_the_wasted_text(registry, cfg):
    from protocol_kit import ScriptedRng

    bundle = doubting_cleric(registry)
    ctx = make_ctx(registry, cfg, rng=ScriptedRng(d20=[2]), bundle=bundle)
    d = apply(ctx, req("cast_spell", spell_id="detect_magic", circle=1, target="hero",
                       free=False, ritual=True))
    assert "  ритуал не удался, десять минут потрачены впустую" in d.log


def test_failed_ordinary_cast_line_is_exactly_the_wasted_text(registry, cfg):
    from protocol_kit import ScriptedRng

    bundle = doubting_cleric(registry)
    ctx = make_ctx(registry, cfg, rng=ScriptedRng(d20=[2]), bundle=bundle)
    d = apply(ctx, req("cast_spell", spell_id="detect_magic", circle=1, target="hero",
                       free=False))
    assert "  заклинание не удалось, ячейка потрачена впустую" in d.log


def test_ritual_ends_a_concentration_that_runs_out_during_the_ten_minutes(registry, cfg):
    from ai_dm.state.creature import Concentration

    bundle = wizard_bundle(registry)
    hero = bundle.heroes[0]
    now = bundle.world.clock.now_s
    hero.creature.concentration = Concentration(spell_id="shield", circle=1, until_s=now + 300)
    _, d = cast(registry, cfg, bundle, "alarm", ritual=True)
    assert hero.creature.concentration is None
    assert d.result["concentration_ended"] == "shield"
    assert f"Концентрация: {registry.get('spell', 'shield').name} кончилась" in d.log


def test_ritual_keeps_a_concentration_that_outlives_the_ten_minutes(registry, cfg):
    from ai_dm.state.creature import Concentration

    bundle = wizard_bundle(registry)
    hero = bundle.heroes[0]
    now = bundle.world.clock.now_s
    hero.creature.concentration = Concentration(spell_id="shield", circle=1, until_s=now + 3600)
    _, d = cast(registry, cfg, bundle, "alarm", ritual=True)
    assert hero.creature.concentration is not None
    assert "concentration_ended" not in d.result


def test_cantrip_log_says_cantrip_and_leveled_log_shows_slots(registry, cfg):
    bundle = wizard_bundle(registry)
    _, d = cast(registry, cfg, bundle, "fire_bolt")
    assert d.log[0].endswith("(заговор)")
    left = slot(bundle).current
    _, d = cast(registry, cfg, bundle, "shield")
    assert d.log[0].endswith(f"(1 круг, ячейки {left - 1}/{slot(bundle).max})")


def test_cantrip_spends_no_slot(registry, cfg):
    bundle = wizard_bundle(registry)
    before = slot(bundle).current
    cast(registry, cfg, bundle, "fire_bolt")
    assert slot(bundle).current == before


def test_failed_ordinary_cast_check_still_wastes_the_slot(registry, cfg):
    from protocol_kit import ScriptedRng

    bundle = doubting_cleric(registry)
    before = slot(bundle).current
    ctx = make_ctx(registry, cfg, rng=ScriptedRng(d20=[2]), bundle=bundle)
    d = apply(ctx, req("cast_spell", spell_id="detect_magic", circle=1, target="hero",
                       free=False))
    assert any("заклинание не удалось, ячейка потрачена впустую" in x for x in d.log)
    assert slot(bundle).current == before - 1


# Магическое восстановление

def empty(bundle):
    for name, pool in bundle.heroes[0].creature.resources.items():
        if name.startswith("spell_slot:"):
            pool.current = 0


def test_short_rest_returns_a_slot_by_arcane_recovery(registry, cfg):
    bundle = wizard_bundle(registry, 3)
    empty(bundle)
    _, d = rest(registry, cfg, bundle)
    assert d.status == "accepted"
    assert slot(bundle, 2).current == 1
    assert slot(bundle, 1).current == 0


def test_short_rest_log_keeps_the_rest_line_before_the_recovery_line(registry, cfg):
    bundle = wizard_bundle(registry, 3)
    empty(bundle)
    _, d = rest(registry, cfg, bundle)
    assert d.log[0].startswith("Короткий отдых: восстановлено")
    assert d.log[1] == "Магическое восстановление: ячейка 2 круга"


def test_short_rest_log_has_the_recovery_line(registry, cfg):
    bundle = wizard_bundle(registry, 3)
    empty(bundle)
    _, d = rest(registry, cfg, bundle)
    line = [x for x in d.log if x.startswith("Магическое восстановление")]
    assert line == ["Магическое восстановление: ячейка 2 круга"]


def test_second_short_rest_gives_no_recovery(registry, cfg):
    bundle = wizard_bundle(registry, 3)
    empty(bundle)
    rest(registry, cfg, bundle)
    _, d = rest(registry, cfg, bundle)
    assert not [x for x in d.log if x.startswith("Магическое восстановление")]
    assert slot(bundle, 2).current == 1


def test_recovery_pool_is_spent_and_long_rest_returns_it(registry, cfg):
    bundle = wizard_bundle(registry, 3)
    empty(bundle)
    rest(registry, cfg, bundle)
    pool = bundle.heroes[0].creature.resources["arcane_recovery"]
    assert pool.current == 0
    rest(registry, cfg, bundle, kind="long")
    assert pool.current == 1


def test_level_5_short_rest_returns_the_third_circle_slot(registry, cfg):
    bundle = wizard_bundle(registry, 5)
    empty(bundle)
    _, d = rest(registry, cfg, bundle)
    assert slot(bundle, 3).current == 1
    assert "Магическое восстановление: ячейка 3 круга" in d.log


def test_long_rest_has_no_recovery_line(registry, cfg):
    bundle = wizard_bundle(registry, 3)
    empty(bundle)
    _, d = rest(registry, cfg, bundle, kind="long")
    assert not [x for x in d.log if x.startswith("Магическое восстановление")]


def test_short_rest_of_a_cleric_has_no_recovery(registry, cfg):
    bundle = cleric_bundle(registry)
    slot(bundle).current = 0
    _, d = rest(registry, cfg, bundle)
    assert slot(bundle).current == 0
    assert not [x for x in d.log if x.startswith("Магическое восстановление")]


# Запоминание заклинания

def swap(drop, take):
    return {"drop": drop, "take": take}


def test_short_rest_swap_without_memorize_spell_is_swap_long_only(registry, cfg):
    bundle = wizard_bundle(registry, 4)
    ctx = make_ctx(registry, cfg, bundle=bundle)
    before = dump(ctx)
    _, d = rest(registry, cfg, bundle, prepared_swap=swap(["shield"], ["alarm"]))
    assert isinstance(d, Invalid)
    assert d.code == "swap_long_only"
    assert d.message == "подготовленные меняют после длинного отдыха"
    assert dump(ctx) == before


def test_short_rest_swap_with_memorize_spell_is_accepted(registry, cfg):
    bundle = wizard_bundle(registry, 5)
    _, d = rest(registry, cfg, bundle, prepared_swap=swap(["shield"], ["alarm"]))
    assert d.status == "accepted"
    prepared = bundle.heroes[0].sheet.prepared_of()
    assert "alarm" in prepared
    assert "shield" not in prepared


def test_short_rest_two_swaps_are_swap_limit(registry, cfg):
    bundle = wizard_bundle(registry, 5)
    _, d = rest(registry, cfg, bundle,
                prepared_swap=swap(["shield", "sleep"], ["alarm", "burning_hands"]))
    assert isinstance(d, Invalid)
    assert d.code == "swap_limit"


def test_short_rest_swap_to_a_spell_outside_the_book_is_invalid(registry, cfg):
    bundle = wizard_bundle(registry, 5)
    _, d = rest(registry, cfg, bundle, prepared_swap=swap(["shield"], ["grease"]))
    assert isinstance(d, Invalid)
    assert d.code == "not_in_book"


def test_long_rest_swap_of_several_book_spells_is_accepted(registry, cfg):
    bundle = wizard_bundle(registry, 5)
    _, d = rest(registry, cfg, bundle, kind="long",
                prepared_swap=swap(["shield", "sleep"], ["alarm", "burning_hands"]))
    assert d.status == "accepted"


def test_long_rest_swap_to_a_spell_outside_the_book_is_invalid(registry, cfg):
    bundle = wizard_bundle(registry, 5)
    _, d = rest(registry, cfg, bundle, kind="long", prepared_swap=swap(["shield"], ["grease"]))
    assert isinstance(d, Invalid)
    assert d.code == "not_in_book"


@pytest.mark.parametrize("level", [1, 2, 3, 4])
def test_memorize_spell_is_not_available_before_level_5(registry, cfg, level):
    bundle = wizard_bundle(registry, level)
    _, d = rest(registry, cfg, bundle, prepared_swap=swap(["shield"], ["alarm"]))
    assert isinstance(d, Invalid)
    assert d.code == "swap_long_only"
