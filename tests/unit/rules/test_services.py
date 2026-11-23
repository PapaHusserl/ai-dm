# Реестр услуг (docs/plan-u0.md, П1): чистые функции rules/services.py.
#   kinds_of(npc, cfg) -- [(id, ServiceKind)] в порядке NPC, неизвестные конфигу пропускаются.
#   quote(kind, npc, world, cfg) -- цена за единицу: отношение и торг как у buy_quote.
#   providers_here(world, location_id) -- живые NPC с услугами в локации.
#   haggle_slot(npc, world) -- профиль лавки, если он есть, иначе FlagHaggle по флагу haggle:<npc>.
#   FlagHaggle: состояние "<день>:<процент>" во флаге мира; save_haggle пишет только FlagHaggle.
#   lodging_here(world, location_id, cfg) -- [(NPC, id, ServiceKind)] ночлега у живых NPC локации,
#       по цене (quote), дешёвый первым. lodging_paid(world, hero_id, cfg) -- флаг lodging:<hero_id>
#       (день оплаты, int) действует до morning_hour следующего дня (У0 П2).
import pytest

from ai_dm.core.rng import Rng
from ai_dm.rules.services import (
    LODGING_FLAG,
    FlagHaggle,
    haggle_slot,
    kinds_of,
    lodging_here,
    lodging_paid,
    providers_here,
    quote,
    save_haggle,
)
from ai_dm.rules.trade import DAY_S, apply_haggle
from ai_dm.state.world import NPC, TradeProfile, WorldState


def make_world():
    return WorldState(world_id="w", rng=Rng(1).state)


def provider(npc_id="grok", services=("room_modest", "meal_modest"), **fields):
    return NPC(
        id=npc_id, name=npc_id.capitalize(), means=["услуги"], services=list(services), **fields
    )


# kinds_of

def test_kinds_of_keeps_npc_order(cfg):
    npc = provider(services=["meal_modest", "room_modest"])
    assert [kind_id for kind_id, _ in kinds_of(npc, cfg)] == ["meal_modest", "room_modest"]


def test_kinds_of_returns_registry_kinds(cfg):
    kinds = kinds_of(provider(services=["ale"]), cfg)
    assert kinds == [("ale", cfg.services.kinds["ale"])]


def test_kinds_of_skips_unknown_ids(cfg):
    npc = provider(services=["no_such", "ale"])
    assert [kind_id for kind_id, _ in kinds_of(npc, cfg)] == ["ale"]


def test_kinds_of_npc_without_services_is_empty(cfg):
    assert kinds_of(provider(services=[]), cfg) == []


# quote

def test_quote_neutral_attitude_is_base_price(cfg):
    kind = cfg.services.kinds["room_modest"]
    assert quote(kind, provider(), make_world(), cfg, "room_modest") == 50


def test_quote_taken_free_service_at_good_attitude_is_cheaper(cfg):
    # даровая room_modest сегодня уже взята: 50 * 0.9 = 45 (М0 П6б, решение 149)
    world = make_world()
    world.flags["free_service:grok:room_modest"] = 0
    npc = provider(attitude=60)
    assert quote(cfg.services.kinds["room_modest"], npc, world, cfg, "room_modest") == 45


def test_quote_rounds_up(cfg):
    # 1 * 0.9 = 0.9 -> 1 (в пользу поставщика); даровая сегодня уже взята
    world = make_world()
    world.flags["free_service:grok:shave"] = 0
    npc = provider(attitude=60)
    assert quote(cfg.services.kinds["shave"], npc, world, cfg, "shave") == 1


def test_quote_bed_hour_costs_ten_copper_and_nine_with_good_attitude_after_the_free_one(cfg):
    kind = cfg.services.kinds["bed_hour"]
    world = make_world()
    world.flags["free_service:grok:bed_hour"] = 0
    assert quote(kind, provider(), make_world(), cfg, "bed_hour") == 10
    assert quote(kind, provider(attitude=60), world, cfg, "bed_hour") == 9


def test_quote_uses_flag_haggle_today(cfg):
    world = make_world()
    world.flags["haggle:grok"] = "0:-10"
    assert quote(cfg.services.kinds["room_modest"], provider(), world, cfg, "room_modest") == 45


def test_quote_ignores_yesterdays_flag_haggle(cfg):
    world = make_world()
    world.flags["haggle:grok"] = "0:-20"
    world.clock.advance(DAY_S)
    assert quote(cfg.services.kinds["room_modest"], provider(), world, cfg, "room_modest") == 50


def test_quote_fail_haggle_makes_dearer(cfg):
    world = make_world()
    world.flags["haggle:grok"] = "0:10"
    assert quote(cfg.services.kinds["room_modest"], provider(), world, cfg, "room_modest") == 55


def test_quote_uses_shop_profile_haggle_when_npc_has_trade(cfg):
    world = make_world()
    profile = TradeProfile(kind="general", purse_cp=100, restock_at_s=10**9)
    apply_haggle(profile, -20, 0)
    npc = provider(trade=profile)
    assert quote(cfg.services.kinds["room_modest"], npc, world, cfg, "room_modest") == 40


def test_quote_zero_price_stays_zero(cfg):
    free = cfg.services.kinds["ale"].model_copy(update={"price_cp": 0})
    assert quote(free, provider(), make_world(), cfg, "ale") == 0


# М0 П6б (решения 141-143, 148, 149, 155): услуги друга даром, раз в день на вид и NPC.
# Имена free_today / mark_free и порядок параметров quote -- из плана (имена -- кабан).

def test_quote_friend_is_free_for_every_default_kind(cfg):
    world = make_world()
    npc = provider(attitude=50)
    assert {kind_id: quote(kind, npc, world, cfg, kind_id)
            for kind_id, kind in cfg.services.kinds.items()} == dict.fromkeys(cfg.services.kinds, 0)


def test_quote_close_tier_is_free_too(cfg):
    assert quote(cfg.services.kinds["room_modest"], provider(attitude=90), make_world(), cfg,
                 "room_modest") == 0


def test_quote_just_below_friend_is_full_price(cfg):
    assert quote(cfg.services.kinds["room_modest"], provider(attitude=49), make_world(), cfg,
                 "room_modest") == 50


def test_quote_intimate_and_cure_kinds_are_free_for_a_friend(cfg):
    npc = provider(attitude=50)
    world = make_world()
    assert quote(cfg.services.kinds["uncurse_temple"], npc, world, cfg, "uncurse_temple") == 0
    assert quote(cfg.services.kinds["companion_common"], npc, world, cfg, "companion_common") == 0


def test_quote_free_ignores_haggle(cfg):
    world = make_world()
    world.flags["haggle:grok"] = "0:10"
    assert quote(cfg.services.kinds["room_modest"], provider(attitude=60), world, cfg,
                 "room_modest") == 0


def test_quote_after_taken_free_pays_friend_price_with_haggle(cfg):
    # 50 с торгом -10% = 45, скидка друга 0,9 -> 40.5 -> 41 (вверх); купленная даровая сегодня
    world = make_world()
    world.flags["free_service:grok:room_modest"] = 0
    world.flags["haggle:grok"] = "0:-10"
    npc = provider(attitude=60)
    assert quote(cfg.services.kinds["room_modest"], npc, world, cfg, "room_modest") == 41


def test_quote_other_kind_of_the_same_npc_stays_free(cfg):
    world = make_world()
    world.flags["free_service:grok:meal_modest"] = 0
    assert quote(cfg.services.kinds["room_modest"], provider(attitude=60), world, cfg,
                 "room_modest") == 0


def test_quote_same_kind_of_another_npc_stays_free(cfg):
    world = make_world()
    world.flags["free_service:grok:meal_modest"] = 0
    other = provider("mara", attitude=60)
    assert quote(cfg.services.kinds["meal_modest"], other, world, cfg, "meal_modest") == 0


def test_quote_free_again_next_day(cfg):
    world = make_world()
    world.flags["free_service:grok:meal_modest"] = 0
    world.clock.advance(DAY_S)
    assert quote(cfg.services.kinds["meal_modest"], provider(attitude=60), world, cfg,
                 "meal_modest") == 0


def test_quote_custom_free_tier_in_user_config(cfg):
    from ai_dm.config.settings import load_rules_config
    toml = "".join(
        f'[[attitude.tiers]]\nid = "{tid}"\nname = "{tid}"\nfrom = {low}\n'
        for tid, low in (("enemy", -100), ("foe", -49), ("neutral", -29), ("buddy", 30),
                         ("friend", 40), ("close", 90))
    )
    custom = load_rules_config(toml_text=toml)
    ale = custom.services.kinds["ale"]
    assert quote(ale, provider(attitude=40), make_world(), custom, "ale") == 0
    assert quote(ale, provider(attitude=39), make_world(), custom, "ale") == 4


# free_today(kind_id, npc, world, cfg): ступень не ниже free_tier и флаг не равен сегодняшнему дню

def test_free_today_friend_without_flag_is_true(cfg):
    from ai_dm.rules.services import free_today
    assert free_today("ale", provider(attitude=50), make_world(), cfg) is True


def test_free_today_below_friend_is_false(cfg):
    from ai_dm.rules.services import free_today
    assert free_today("ale", provider(attitude=49), make_world(), cfg) is False


def test_free_today_todays_flag_is_false(cfg):
    from ai_dm.rules.services import free_today
    world = make_world()
    world.flags["free_service:grok:ale"] = 0
    assert free_today("ale", provider(attitude=50), world, cfg) is False


def test_free_today_yesterdays_flag_is_true(cfg):
    from ai_dm.rules.services import free_today
    world = make_world()
    world.flags["free_service:grok:ale"] = 0
    world.clock.advance(DAY_S)
    assert free_today("ale", provider(attitude=50), world, cfg) is True


def test_free_today_day_changes_at_midnight_not_morning(cfg):
    # решение 155: граница суток -- полночь, как у торга (day_of)
    from ai_dm.rules.services import free_today
    world = make_world()
    world.clock.advance(DAY_S - 600)
    world.flags["free_service:grok:ale"] = 0
    assert free_today("ale", provider(attitude=50), world, cfg) is False
    world.clock.advance(1200)
    assert free_today("ale", provider(attitude=50), world, cfg) is True


def test_free_today_flag_is_per_npc_and_kind(cfg):
    from ai_dm.rules.services import free_today
    world = make_world()
    world.flags["free_service:grok:ale"] = 0
    assert free_today("meal_modest", provider(attitude=50), world, cfg) is True
    assert free_today("ale", provider("mara", attitude=50), world, cfg) is True


def test_mark_free_makes_free_today_false_and_writes_the_day(cfg):
    from ai_dm.rules.services import free_today, mark_free
    world = make_world()
    world.clock.advance(DAY_S * 2 + 5)
    npc = provider(attitude=50)
    mark_free("ale", npc, world)
    assert world.flags["free_service:grok:ale"] == 2
    assert free_today("ale", npc, world, cfg) is False


def test_is_free_passage_stays_free_for_a_friend_after_taken_flag(cfg):
    from ai_dm.rules.services import is_free
    world = make_world()
    world.flags["free_service:grok:ferry"] = 0
    npc = provider(services=["ferry"], attitude=50)
    assert is_free("ferry", cfg.services.kinds["ferry"], npc, world, cfg) is True


# providers_here

def test_providers_here_lists_alive_providers_in_location():
    world = make_world()
    world.npcs["grok"] = provider("grok", location_id="inn")
    assert [n.id for n in providers_here(world, "inn")] == ["grok"]


def test_providers_here_skips_other_location():
    world = make_world()
    world.npcs["grok"] = provider("grok", location_id="forest")
    assert providers_here(world, "inn") == []


def test_providers_here_skips_not_alive():
    world = make_world()
    world.npcs["dead"] = provider("dead", location_id="inn", status="dead")
    world.npcs["gone"] = provider("gone", location_id="inn", status="gone")
    assert providers_here(world, "inn") == []


def test_providers_here_skips_npc_without_services():
    world = make_world()
    world.npcs["bob"] = provider("bob", services=[], location_id="inn")
    assert providers_here(world, "inn") == []


def test_providers_here_includes_merchant_with_services():
    world = make_world()
    profile = TradeProfile(kind="general", purse_cp=100, restock_at_s=10**9)
    world.npcs["mara"] = provider("mara", location_id="inn", trade=profile)
    assert [n.id for n in providers_here(world, "inn")] == ["mara"]


# haggle_slot / FlagHaggle

def test_haggle_slot_is_shop_profile_when_npc_has_trade():
    profile = TradeProfile(kind="general", purse_cp=100, restock_at_s=10**9)
    npc = provider(trade=profile)
    assert haggle_slot(npc, make_world()) is profile


def test_haggle_slot_is_flag_haggle_without_trade():
    assert isinstance(haggle_slot(provider(), make_world()), FlagHaggle)


def test_flag_haggle_without_flag_has_no_haggle_state():
    slot = FlagHaggle({}, "grok")
    assert (slot.haggle_day, slot.haggle_percent) == (None, 0)


def test_flag_haggle_reads_day_and_percent():
    slot = FlagHaggle({"haggle:grok": "3:-20"}, "grok")
    assert (slot.haggle_day, slot.haggle_percent) == (3, -20)


def test_flag_haggle_reads_only_its_own_npc():
    slot = FlagHaggle({"haggle:other": "3:-20"}, "grok")
    assert slot.haggle_day is None


def test_flag_haggle_save_writes_flag():
    flags = {}
    slot = FlagHaggle(flags, "grok")
    apply_haggle(slot, 10, DAY_S * 2 + 5)
    slot.save()
    assert flags == {"haggle:grok": "2:10"}


def test_flag_haggle_roundtrip_through_flags():
    flags = {}
    slot = FlagHaggle(flags, "grok")
    apply_haggle(slot, -20, 0)
    slot.save()
    again = FlagHaggle(flags, "grok")
    assert (again.haggle_day, again.haggle_percent) == (0, -20)


def test_save_haggle_persists_flag_haggle():
    world = make_world()
    slot = haggle_slot(provider(), world)
    apply_haggle(slot, -10, 0)
    save_haggle(slot)
    assert world.flags["haggle:grok"] == "0:-10"


def test_save_haggle_leaves_flags_alone_for_shop_profile():
    world = make_world()
    profile = TradeProfile(kind="general", purse_cp=100, restock_at_s=10**9)
    apply_haggle(profile, -10, 0)
    save_haggle(haggle_slot(provider(trade=profile), world))
    assert world.flags == {}


# lodging_here (У0 П2): [(NPC, id, kind)] ночлега у живых NPC локации, дешёвый первым

def test_lodging_here_returns_npc_id_and_kind(cfg):
    world = make_world()
    npc = provider("grok", services=["room_modest"], location_id="inn")
    world.npcs["grok"] = npc
    assert lodging_here(world, "inn", cfg) == [
        (npc, "room_modest", cfg.services.kinds["room_modest"])
    ]


def test_lodging_here_skips_non_lodging_services(cfg):
    world = make_world()
    world.npcs["grok"] = provider("grok", services=["meal_modest", "ale"], location_id="inn")
    assert lodging_here(world, "inn", cfg) == []


def test_lodging_here_sorted_by_price_cheapest_first(cfg):
    world = make_world()
    world.npcs["grok"] = provider(
        "grok", services=["room_wealthy", "room_modest", "room_poor"], location_id="inn"
    )
    assert [kind_id for _, kind_id, _ in lodging_here(world, "inn", cfg)] == [
        "room_poor", "room_modest", "room_wealthy"
    ]


def test_lodging_here_sorts_across_npcs_by_their_own_quote(cfg):
    # у Дока отношение хорошее: 50 * 0.9 = 45 дешевле 50 у Грока
    world = make_world()
    world.npcs["grok"] = provider("grok", services=["room_modest"], location_id="inn")
    world.npcs["doc"] = provider("doc", services=["room_modest"], location_id="inn", attitude=60)
    assert [npc.id for npc, _, _ in lodging_here(world, "inn", cfg)] == ["doc", "grok"]


def test_lodging_here_sorts_by_per_kind_free_flag_for_a_friend(cfg):
    # room_poor у друга уже взят сегодня (платная), room_modest ещё даром: даровая первой
    world = make_world()
    world.flags["free_service:grok:room_poor"] = 0
    world.npcs["grok"] = provider(
        "grok", services=["room_poor", "room_modest"], location_id="inn", attitude=50
    )
    assert [kind_id for _, kind_id, _ in lodging_here(world, "inn", cfg)] == [
        "room_modest", "room_poor"
    ]


def test_lodging_here_skips_other_location(cfg):
    world = make_world()
    world.npcs["grok"] = provider("grok", services=["room_modest"], location_id="forest")
    assert lodging_here(world, "inn", cfg) == []


def test_lodging_here_skips_dead_provider(cfg):
    world = make_world()
    world.npcs["grok"] = provider(
        "grok", services=["room_modest"], location_id="inn", status="dead"
    )
    assert lodging_here(world, "inn", cfg) == []


def test_lodging_here_skips_unknown_service_ids(cfg):
    world = make_world()
    world.npcs["grok"] = provider("grok", services=["no_such"], location_id="inn")
    assert lodging_here(world, "inn", cfg) == []


# lodging_paid: флаг lodging:<hero_id> = день оплаты; действует до morning_hour следующего дня

MORNING_S = 6 * 3600


def test_lodging_paid_false_without_flag(cfg):
    assert lodging_paid(make_world(), "hero", cfg) is False


def test_lodging_paid_true_for_todays_flag(cfg):
    world = make_world()
    world.flags["lodging:hero"] = 0
    assert lodging_paid(world, "hero", cfg) is True


def test_lodging_paid_true_after_midnight_before_morning(cfg):
    world = make_world()
    world.flags["lodging:hero"] = 0
    world.clock.advance(DAY_S + MORNING_S - 1)
    assert lodging_paid(world, "hero", cfg) is True


def test_lodging_paid_false_exactly_at_morning(cfg):
    world = make_world()
    world.flags["lodging:hero"] = 0
    world.clock.advance(DAY_S + MORNING_S)
    assert lodging_paid(world, "hero", cfg) is False


def test_lodging_paid_false_for_old_flag(cfg):
    world = make_world()
    world.flags["lodging:hero"] = 0
    world.clock.advance(DAY_S * 3)
    assert lodging_paid(world, "hero", cfg) is False


def test_lodging_paid_true_on_second_day_with_that_days_flag(cfg):
    world = make_world()
    world.clock.advance(DAY_S + 5)
    world.flags["lodging:hero"] = 1
    assert lodging_paid(world, "hero", cfg) is True


def test_lodging_paid_payment_at_2am_lasts_until_next_days_morning(cfg):
    # текущее поведение: флаг -- день оплаты, оплата в 02:00 действует до 06:00 следующих суток
    world = make_world()
    world.clock.advance(2 * 3600)
    world.flags["lodging:hero"] = 0
    world.clock.advance(DAY_S + MORNING_S - 2 * 3600 - 1)
    assert lodging_paid(world, "hero", cfg) is True


def test_lodging_paid_is_per_hero(cfg):
    world = make_world()
    world.flags["lodging:hero"] = 0
    assert lodging_paid(world, "other", cfg) is False


@pytest.mark.parametrize("value", ["0", 0.0, True, None, "x"])
def test_lodging_paid_non_int_flag_is_unpaid(cfg, value):
    world = make_world()
    world.flags["lodging:hero"] = value
    assert lodging_paid(world, "hero", cfg) is False


@pytest.mark.parametrize(
    ("location", "means", "hint"),
    [
        ("Таверна", ["трактир"], "services (например room_poor, meal_modest, ale)"),
        ("Лавка", ["лавка"], "trade_kind (например general)"),
        ("Кузница", ["кузница"], "trade_kind smith"),
        ("Храм", ["жрец"], "services (например heal_temple, uncurse_temple)"),
    ],
)
def test_keeper_hint_each_family(location, means, hint):
    from ai_dm.rules.services import keeper_hint
    assert keeper_hint(location, means) == hint


def test_keeper_hint_craft_word_is_separate_from_next_means():
    from ai_dm.rules.services import keeper_hint
    assert keeper_hint("Таверна", ["стойка", "бар"]) is not None


def test_keeper_hint_ignores_case():
    from ai_dm.rules.services import keeper_hint
    assert keeper_hint("ТАВЕРНА «Пьяный Дракон»", ["ТРАКТИР"]) is not None


def test_keeper_hint_empty_means_is_none():
    from ai_dm.rules.services import keeper_hint
    assert keeper_hint("Таверна", []) is None


def test_keeper_hint_location_not_an_establishment_is_none():
    from ai_dm.rules.services import keeper_hint
    assert keeper_hint("Лес", ["трактир"]) is None


def test_keeper_hint_means_not_a_craft_is_none():
    from ai_dm.rules.services import keeper_hint
    assert keeper_hint("Таверна", ["связи"]) is None


def test_keeper_hint_orcs_in_forge_is_none():
    from ai_dm.rules.services import keeper_hint
    assert keeper_hint("Кузница Пепла", ["горных орков"]) is None


def test_keeper_hint_tavern_and_fortitude_is_none():
    from ai_dm.rules.services import keeper_hint
    assert keeper_hint("Таверна", ["стойкость"]) is None


def test_keeper_hint_shop_and_loyal_comrades_is_none():
    from ai_dm.rules.services import keeper_hint
    assert keeper_hint("Лавка", ["верные товарищи"]) is None


def test_keeper_hint_temple_square_and_sacred_symbol_is_none():
    from ai_dm.rules.services import keeper_hint
    assert keeper_hint("Храмовая площадь", ["священный символ"]) is None


def test_keeper_hint_innkeeper_street_is_none():
    from ai_dm.rules.services import keeper_hint
    assert keeper_hint("Трактирная улица", ["трактир"]) is None


def test_lodging_flag_name():
    assert LODGING_FLAG == "lodging"
