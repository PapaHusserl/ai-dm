# К1 «Смена подготовленных» в протоколе (docs/plan-k1.md, п. 4.2, 4.4; В6а, Q3а):
#   rest{kind: long, prepared_swap: {drop, take}} -- смена после длинного отдыха: отдых применён
#     (HP/ячейки восстановлены, часы +8 ч), prepared_of обновлён, log «Подготовлено: X; снято: Y»,
#     result["prepared"] -- новый список;
#   kind short со сменой -- Invalid swap_long_only, ничего не изменилось (часы тоже);
#   плохая смена (swap_limit, unknown_spell, ...) -- Invalid до отдыха, бандл байт-в-байт прежний;
#   герой на 0 HP -- rest_impossible, подготовленные не меняются;
#   после смены новое заклинание проходит cast_problem, снятое -- not_prepared.
#   Грей из campaigns/drunk_dragon: следопыт 3 ур., подготовлено cure_wounds, ensnaring_strike,
#   speak_with_animals, fog_cloud (лимит 4, полон), смена одного (prepared_swap 1).
from pathlib import Path

import game_kit  # noqa: F401  (добавляет в sys.path соседние kit-ы)
import pytest
from protocol_kit import dump, make_ctx, req

from ai_dm.campaign.loader import load_pack, pack_content_dir
from ai_dm.content.loader import load_registry
from ai_dm.game.starter import new_world_from_pack
from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Invalid

DRAGON = Path(__file__).resolve().parents[3] / "campaigns" / "drunk_dragon"
OLD = ["cure_wounds", "ensnaring_strike", "speak_with_animals", "fog_cloud"]


@pytest.fixture
def dragon(cfg):
    registry = load_registry([pack_content_dir(DRAGON)])
    bundle = new_world_from_pack(
        registry, cfg, load_pack(DRAGON, registry), hero="grey", seed=1, world_id="w1",
        saved_at="2026-01-01T00:00:00",
    )
    return registry, bundle


def swap(drop, take):
    return {"drop": drop, "take": take}


def rest(registry, cfg, bundle, kind="long", **fields):
    ctx = make_ctx(registry, cfg, bundle=bundle)
    return ctx, apply(ctx, req("rest", kind=kind, **fields))


def tired(bundle):
    hero = bundle.heroes[0]
    hero.creature.hp_current = 5
    hero.creature.resources["spell_slot:1"].current = 0
    return hero


# успех

def test_long_rest_with_swap_is_accepted(dragon, cfg):
    registry, bundle = dragon
    ctx, d = rest(registry, cfg, bundle, prepared_swap=swap(["fog_cloud"], ["longstrider"]))
    assert d.status == "accepted"


def test_swap_replaces_the_prepared_spell(dragon, cfg):
    registry, bundle = dragon
    rest(registry, cfg, bundle, prepared_swap=swap(["fog_cloud"], ["longstrider"]))
    prepared = bundle.heroes[0].sheet.prepared_of()
    assert "longstrider" in prepared
    assert "fog_cloud" not in prepared
    assert prepared[:3] == OLD[:3]


def test_swap_still_restores_hp_and_slots(dragon, cfg):
    registry, bundle = dragon
    hero = tired(bundle)
    rest(registry, cfg, bundle, prepared_swap=swap(["fog_cloud"], ["longstrider"]))
    assert hero.creature.hp_current == hero.creature.hp_max
    assert hero.creature.resources["spell_slot:1"].current == 3


def test_swap_still_advances_the_clock_by_eight_hours(dragon, cfg):
    registry, bundle = dragon
    start = bundle.world.clock.now_s
    rest(registry, cfg, bundle, prepared_swap=swap(["fog_cloud"], ["longstrider"]))
    assert bundle.world.clock.now_s == start + cfg.time.long_rest_s


def test_swap_log_line_names_taken_and_dropped(dragon, cfg):
    registry, bundle = dragon
    ctx, d = rest(registry, cfg, bundle, prepared_swap=swap(["fog_cloud"], ["longstrider"]))
    assert "Подготовлено: longstrider; снято: fog_cloud" in d.log


def test_swap_result_has_the_new_prepared_list(dragon, cfg):
    registry, bundle = dragon
    ctx, d = rest(registry, cfg, bundle, prepared_swap=swap(["fog_cloud"], ["longstrider"]))
    assert d.result["prepared"] == bundle.heroes[0].sheet.prepared_of()
    assert "longstrider" in d.result["prepared"]


def test_swap_with_only_drop_logs_nothing_taken(dragon, cfg):
    registry, bundle = dragon
    ctx, d = rest(registry, cfg, bundle, prepared_swap=swap(["fog_cloud"], []))
    assert "Подготовлено: ничего; снято: fog_cloud" in d.log


def test_swap_with_only_take_logs_nothing_dropped(dragon, cfg):
    registry, bundle = dragon
    bundle.heroes[0].sheet.prepared_of().remove("fog_cloud")
    ctx, d = rest(registry, cfg, bundle, prepared_swap=swap([], ["longstrider"]))
    assert "Подготовлено: longstrider; снято: ничего" in d.log


def test_long_rest_without_swap_has_no_prepared_in_result(dragon, cfg):
    registry, bundle = dragon
    ctx, d = rest(registry, cfg, bundle)
    assert "prepared" not in d.result
    assert bundle.heroes[0].sheet.prepared_of() == OLD


def test_empty_swap_is_the_same_as_none(dragon, cfg):
    registry, bundle = dragon
    ctx, d = rest(registry, cfg, bundle, prepared_swap=swap([], []))
    assert "prepared" not in d.result
    assert bundle.heroes[0].sheet.prepared_of() == OLD


# отказы

def test_short_rest_with_swap_is_invalid_swap_long_only(dragon, cfg):
    registry, bundle = dragon
    ctx, d = rest(
        registry, cfg, bundle, kind="short", prepared_swap=swap(["fog_cloud"], ["longstrider"])
    )
    assert isinstance(d, Invalid)
    assert d.code == "swap_long_only"


def test_short_rest_with_swap_changes_nothing(dragon, cfg):
    registry, bundle = dragon
    before = bundle.model_dump_json()
    start = bundle.world.clock.now_s
    rest(registry, cfg, bundle, kind="short", prepared_swap=swap(["fog_cloud"], ["longstrider"]))
    assert bundle.model_dump_json() == before
    assert bundle.world.clock.now_s == start


def test_two_swaps_for_a_ranger_are_invalid_swap_limit(dragon, cfg):
    registry, bundle = dragon
    ctx, d = rest(
        registry, cfg, bundle,
        prepared_swap=swap(["fog_cloud", "cure_wounds"], ["longstrider", "alarm"]),
    )
    assert isinstance(d, Invalid)
    assert d.code == "swap_limit"


def test_bad_swap_leaves_the_bundle_byte_for_byte_unchanged(dragon, cfg):
    registry, bundle = dragon
    tired(bundle)
    before = bundle.model_dump_json()
    ctx, d = rest(
        registry, cfg, bundle, prepared_swap=swap(["fog_cloud", "cure_wounds"], ["longstrider"])
    )
    assert isinstance(d, Invalid)
    assert dump(ctx) == before


def test_unknown_spell_swap_is_invalid_with_allowed_ids(dragon, cfg):
    registry, bundle = dragon
    before = bundle.model_dump_json()
    ctx, d = rest(registry, cfg, bundle, prepared_swap=swap(["fog_cloud"], ["no_such_spell"]))
    assert isinstance(d, Invalid)
    assert d.code == "unknown_spell"
    assert "допустимые id" in d.message
    assert dump(ctx) == before


def test_swap_over_the_prepared_limit_is_invalid(dragon, cfg):
    registry, bundle = dragon
    before = bundle.model_dump_json()
    ctx, d = rest(registry, cfg, bundle, prepared_swap=swap([], ["longstrider"]))
    assert isinstance(d, Invalid)
    assert d.code == "prepared_limit"
    assert dump(ctx) == before


def test_swap_taking_an_already_prepared_spell_is_invalid(dragon, cfg):
    registry, bundle = dragon
    ctx, d = rest(registry, cfg, bundle, prepared_swap=swap(["fog_cloud"], ["cure_wounds"]))
    assert isinstance(d, Invalid)
    assert d.code == "already_prepared"


def test_swap_dropping_the_always_prepared_mark_is_invalid(dragon, cfg):
    registry, bundle = dragon
    ctx, d = rest(registry, cfg, bundle, prepared_swap=swap(["hunters_mark"], ["longstrider"]))
    assert isinstance(d, Invalid)
    assert d.code == "not_prepared"


def test_swap_at_zero_hp_is_rest_impossible_and_changes_nothing(dragon, cfg):
    registry, bundle = dragon
    bundle.heroes[0].creature.hp_current = 0
    before = bundle.model_dump_json()
    ctx, d = rest(registry, cfg, bundle, prepared_swap=swap(["fog_cloud"], ["longstrider"]))
    assert isinstance(d, Invalid)
    assert d.code == "rest_impossible"
    assert dump(ctx) == before


# после смены

def cast(registry, cfg, bundle, spell_id, **fields):
    ctx = make_ctx(registry, cfg, bundle=bundle)
    data = {"spell_id": spell_id, "circle": 1, "target": "hero", "free": False} | fields
    return apply(ctx, req("cast_spell", **data))


def test_new_spell_is_castable_after_the_swap(dragon, cfg):
    registry, bundle = dragon
    rest(registry, cfg, bundle, prepared_swap=swap(["fog_cloud"], ["longstrider"]))
    d = cast(registry, cfg, bundle, "longstrider")
    assert not isinstance(d, Invalid)


def test_dropped_spell_is_not_prepared_after_the_swap(dragon, cfg):
    registry, bundle = dragon
    rest(registry, cfg, bundle, prepared_swap=swap(["fog_cloud"], ["longstrider"]))
    d = cast(registry, cfg, bundle, "fog_cloud")
    assert isinstance(d, Invalid)
    assert d.code == "not_prepared"


def test_new_spell_is_not_castable_before_the_swap(dragon, cfg):
    registry, bundle = dragon
    d = cast(registry, cfg, bundle, "longstrider")
    assert isinstance(d, Invalid)
    assert d.code == "not_prepared"
