# К7х «Смена Добычи охотника» в протоколе (docs/plan-k7x.md, п. 7, В8; образец --
# test_apply_rest_swap.py):
#   rest{kind: short | long, prey_swap: <id варианта>} -- смена Добычи (hunters_prey) после отдыха:
#     отдых применён, sheet.feature_choices["hunters_prey"] == [новый вариант], log «Добыча
#       охотника:
#     <новое> (было: <старое>)», result["prey"] == id нового варианта;
#     prey_swap "" -- без смены (поле None), в result нет ключа prey;
#   проверки до отдыха (Invalid, бандл байт-в-байт прежний, часы не сдвинуты):
#     same_option -- вариант уже выбран; unknown_option -- нет такого варианта (в message
#       допустимые);
#     no_feature -- у героя нет Добычи охотника (Грей-зверовод из drunk_dragon);
#     герой на 0 HP -- rest_impossible, Добыча не меняется;
#   prepared_swap и prey_swap вместе на длинном отдыхе -- применяются оба; плохая prepared_swap или
#   короткий отдых с prepared_swap (swap_long_only) отменяют и смену Добычи.
#   Грей: следопыт 3 ур.; тест делает его охотником (subclass hunter) с Убийцей колоссов.
from pathlib import Path

import game_kit  # noqa: F401  (добавляет в sys.path соседние kit-ы)
import pytest
from protocol_kit import dump, make_ctx, req

from ai_dm.campaign.loader import load_pack, pack_content_dir
from ai_dm.content.loader import load_registry
from ai_dm.game.starter import new_world_from_pack
from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Invalid
from ai_dm.rules.derived import hero_feature_ids

DRAGON = Path(__file__).resolve().parents[3] / "campaigns" / "drunk_dragon"


@pytest.fixture
def dragon(cfg):
    registry = load_registry([pack_content_dir(DRAGON)])
    bundle = new_world_from_pack(
        registry, cfg, load_pack(DRAGON, registry), hero="grey", seed=1, world_id="w1",
        saved_at="2026-01-01T00:00:00",
    )
    return registry, bundle


def hunter(bundle, prey="colossus_slayer"):
    sheet = bundle.heroes[0].sheet
    sheet.primary.subclass_id = "hunter"
    sheet.feature_choices = {"hunters_prey": [prey]}
    return bundle.heroes[0]


def rest(registry, cfg, bundle, kind="long", **fields):
    ctx = make_ctx(registry, cfg, bundle=bundle)
    return ctx, apply(ctx, req("rest", kind=kind, **fields))


def prey(bundle):
    return bundle.heroes[0].sheet.feature_choices["hunters_prey"]


def tired(bundle):
    hero = bundle.heroes[0]
    hero.creature.hp_current = 5
    return hero


# --- успех ---

@pytest.mark.parametrize("kind", ["short", "long"])
def test_rest_with_prey_swap_is_accepted(dragon, cfg, kind):
    registry, bundle = dragon
    hunter(bundle)
    ctx, d = rest(registry, cfg, bundle, kind=kind, prey_swap="horde_breaker")
    assert d.status == "accepted"


@pytest.mark.parametrize("kind", ["short", "long"])
def test_prey_choice_is_replaced(dragon, cfg, kind):
    registry, bundle = dragon
    hunter(bundle)
    rest(registry, cfg, bundle, kind=kind, prey_swap="horde_breaker")
    assert prey(bundle) == ["horde_breaker"]


def test_swap_back_to_colossus_slayer(dragon, cfg):
    registry, bundle = dragon
    hunter(bundle, "horde_breaker")
    rest(registry, cfg, bundle, kind="short", prey_swap="colossus_slayer")
    assert prey(bundle) == ["colossus_slayer"]


@pytest.mark.parametrize("kind", ["short", "long"])
def test_prey_log_line_names_new_and_old(dragon, cfg, kind):
    registry, bundle = dragon
    hunter(bundle)
    ctx, d = rest(registry, cfg, bundle, kind=kind, prey_swap="horde_breaker")
    assert "Добыча охотника: Истребитель орд (было: Убийца колоссов)" in d.log


def test_prey_log_line_for_the_reverse_swap(dragon, cfg):
    registry, bundle = dragon
    hunter(bundle, "horde_breaker")
    ctx, d = rest(registry, cfg, bundle, prey_swap="colossus_slayer")
    assert "Добыча охотника: Убийца колоссов (было: Истребитель орд)" in d.log


@pytest.mark.parametrize("kind", ["short", "long"])
def test_prey_result_has_the_new_option(dragon, cfg, kind):
    registry, bundle = dragon
    hunter(bundle)
    ctx, d = rest(registry, cfg, bundle, kind=kind, prey_swap="horde_breaker")
    assert d.result["prey"] == "horde_breaker"


def test_prey_swap_still_restores_hp_on_a_long_rest(dragon, cfg):
    registry, bundle = dragon
    hero = hunter(bundle)
    tired(bundle)
    rest(registry, cfg, bundle, prey_swap="horde_breaker")
    assert hero.creature.hp_current == hero.creature.hp_max


def test_prey_swap_still_advances_the_clock_on_a_long_rest(dragon, cfg):
    registry, bundle = dragon
    hunter(bundle)
    start = bundle.world.clock.now_s
    rest(registry, cfg, bundle, prey_swap="horde_breaker")
    assert bundle.world.clock.now_s == start + cfg.time.long_rest_s


def test_prey_swap_still_advances_the_clock_on_a_short_rest(dragon, cfg):
    registry, bundle = dragon
    hunter(bundle)
    start = bundle.world.clock.now_s
    rest(registry, cfg, bundle, kind="short", prey_swap="horde_breaker")
    assert bundle.world.clock.now_s == start + cfg.time.short_rest_s


def test_new_option_is_in_hero_features_after_the_swap(dragon, cfg):
    registry, bundle = dragon
    hero = hunter(bundle)
    assert "colossus_slayer" in hero_feature_ids(hero, registry)
    rest(registry, cfg, bundle, kind="short", prey_swap="horde_breaker")
    ids = hero_feature_ids(hero, registry)
    assert "horde_breaker" in ids
    assert "colossus_slayer" not in ids


# --- без смены ---

def test_empty_prey_swap_is_the_same_as_none(dragon, cfg):
    registry, bundle = dragon
    hunter(bundle)
    ctx, d = rest(registry, cfg, bundle, prey_swap="")
    assert "prey" not in d.result
    assert prey(bundle) == ["colossus_slayer"]
    assert not any("Добыча охотника" in line for line in d.log)


def test_rest_without_prey_swap_changes_nothing_in_prey(dragon, cfg):
    registry, bundle = dragon
    hunter(bundle)
    ctx, d = rest(registry, cfg, bundle, kind="short")
    assert "prey" not in d.result
    assert prey(bundle) == ["colossus_slayer"]


def test_rest_without_prey_swap_works_for_a_non_hunter(dragon, cfg):
    registry, bundle = dragon
    ctx, d = rest(registry, cfg, bundle)
    assert d.status == "accepted"
    assert "prey" not in d.result


# --- отказы до отдыха ---

def test_same_option_is_invalid(dragon, cfg):
    registry, bundle = dragon
    hunter(bundle)
    ctx, d = rest(registry, cfg, bundle, prey_swap="colossus_slayer")
    assert isinstance(d, Invalid)
    assert d.code == "same_option"


def test_same_option_leaves_the_bundle_byte_for_byte_unchanged(dragon, cfg):
    registry, bundle = dragon
    hunter(bundle)
    tired(bundle)
    before = bundle.model_dump_json()
    ctx, d = rest(registry, cfg, bundle, prey_swap="colossus_slayer")
    assert dump(ctx) == before


def test_unknown_option_is_invalid_with_the_allowed_ids(dragon, cfg):
    registry, bundle = dragon
    hunter(bundle)
    ctx, d = rest(registry, cfg, bundle, prey_swap="foo")
    assert isinstance(d, Invalid)
    assert d.code == "unknown_option"
    assert "colossus_slayer" in d.message
    assert "horde_breaker" in d.message


def test_unknown_option_leaves_the_bundle_unchanged(dragon, cfg):
    registry, bundle = dragon
    hunter(bundle)
    tired(bundle)
    before = bundle.model_dump_json()
    ctx, d = rest(registry, cfg, bundle, kind="short", prey_swap="foo")
    assert dump(ctx) == before


def test_unknown_option_does_not_move_the_clock(dragon, cfg):
    registry, bundle = dragon
    hunter(bundle)
    start = bundle.world.clock.now_s
    rest(registry, cfg, bundle, prey_swap="foo")
    assert bundle.world.clock.now_s == start


def test_hero_without_the_feature_is_invalid_no_feature(dragon, cfg):
    registry, bundle = dragon
    before = bundle.model_dump_json()
    ctx, d = rest(registry, cfg, bundle, prey_swap="horde_breaker")
    assert isinstance(d, Invalid)
    assert d.code == "no_feature"
    assert dump(ctx) == before


def test_option_of_another_feature_is_unknown(dragon, cfg):
    registry, bundle = dragon
    hunter(bundle)
    ctx, d = rest(registry, cfg, bundle, prey_swap="second_wind")
    assert isinstance(d, Invalid)
    assert d.code == "unknown_option"


def test_swap_at_zero_hp_is_rest_impossible_and_prey_stays(dragon, cfg):
    registry, bundle = dragon
    hunter(bundle)
    bundle.heroes[0].creature.hp_current = 0
    before = bundle.model_dump_json()
    ctx, d = rest(registry, cfg, bundle, prey_swap="horde_breaker")
    assert isinstance(d, Invalid)
    assert d.code == "rest_impossible"
    assert dump(ctx) == before
    assert prey(bundle) == ["colossus_slayer"]


# --- вместе с prepared_swap ---

def test_prey_and_prepared_swaps_work_together_on_a_long_rest(dragon, cfg):
    registry, bundle = dragon
    hunter(bundle)
    ctx, d = rest(
        registry, cfg, bundle, prey_swap="horde_breaker",
        prepared_swap={"drop": ["fog_cloud"], "take": ["longstrider"]},
    )
    assert d.status == "accepted"
    assert prey(bundle) == ["horde_breaker"]
    assert "longstrider" in bundle.heroes[0].sheet.prepared_of()
    assert "prepared" in d.result
    assert d.result["prey"] == "horde_breaker"


def test_both_log_lines_are_present(dragon, cfg):
    registry, bundle = dragon
    hunter(bundle)
    ctx, d = rest(
        registry, cfg, bundle, prey_swap="horde_breaker",
        prepared_swap={"drop": ["fog_cloud"], "take": ["longstrider"]},
    )
    assert any(line.startswith("Подготовлено:") for line in d.log)
    assert any(line.startswith("Добыча охотника:") for line in d.log)


def test_bad_prepared_swap_cancels_the_prey_swap(dragon, cfg):
    registry, bundle = dragon
    hunter(bundle)
    before = bundle.model_dump_json()
    ctx, d = rest(
        registry, cfg, bundle, prey_swap="horde_breaker",
        prepared_swap={"drop": ["fog_cloud"], "take": ["no_such_spell"]},
    )
    assert isinstance(d, Invalid)
    assert d.code == "unknown_spell"
    assert dump(ctx) == before
    assert prey(bundle) == ["colossus_slayer"]


def test_bad_prey_swap_cancels_the_prepared_swap(dragon, cfg):
    registry, bundle = dragon
    hunter(bundle)
    before = bundle.model_dump_json()
    ctx, d = rest(
        registry, cfg, bundle, prey_swap="foo",
        prepared_swap={"drop": ["fog_cloud"], "take": ["longstrider"]},
    )
    assert isinstance(d, Invalid)
    assert d.code == "unknown_option"
    assert dump(ctx) == before


def test_short_rest_with_prepared_swap_cancels_the_prey_swap(dragon, cfg):
    registry, bundle = dragon
    hunter(bundle)
    before = bundle.model_dump_json()
    ctx, d = rest(
        registry, cfg, bundle, kind="short", prey_swap="horde_breaker",
        prepared_swap={"drop": ["fog_cloud"], "take": ["longstrider"]},
    )
    assert isinstance(d, Invalid)
    assert d.code == "swap_long_only"
    assert dump(ctx) == before
    assert prey(bundle) == ["colossus_slayer"]


# --- ревью К7х: у героя hunters_prey, но нет записи в feature_choices ---

@pytest.mark.parametrize("kind", ["short", "long"])
def test_swap_without_a_recorded_choice_is_invalid_not_a_key_error(dragon, cfg, kind):
    registry, bundle = dragon
    hunter(bundle)
    bundle.heroes[0].sheet.feature_choices = {}
    ctx, d = rest(registry, cfg, bundle, kind=kind, prey_swap="horde_breaker")
    assert isinstance(d, Invalid)
    assert d.code == "no_choice"


def test_swap_without_a_recorded_choice_leaves_the_bundle_unchanged(dragon, cfg):
    registry, bundle = dragon
    hunter(bundle)
    bundle.heroes[0].sheet.feature_choices = {}
    tired(bundle)
    before = bundle.model_dump_json()
    ctx, d = rest(registry, cfg, bundle, prey_swap="horde_breaker")
    assert dump(ctx) == before
