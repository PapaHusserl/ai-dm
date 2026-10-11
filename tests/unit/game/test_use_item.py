# use_item (stage3-live-use-item, U1/U2/T): расходник из инвентаря применяется вне боя.
# Эликсир «Каменная Кожа» Грея из campaigns/drunk_dragon: ActiveEffect ac +2 и resist
# (рубящее, дробящее) на час по часам мира, предмет тратится; зелье лечения лечит;
# нет предмета -> Invalid no_item; эффект, начатый вне боя, живёт и в бою.
# Лимит лечебных расходников за сцену: cfg.limits.consumables_per_scene, лишнее -> rejected.
from pathlib import Path

import pytest
from game_kit import ReactiveAdapter, make_app
from protocol_kit import combat_request, make_ctx, req

from ai_dm.campaign.loader import load_pack, pack_content_dir
from ai_dm.content.loader import load_registry
from ai_dm.game.starter import new_world_from_pack
from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Invalid
from ai_dm.rules.creatures import live_effects
from ai_dm.rules.derived import armor_class
from ai_dm.rules.inventory import add_item, count_item
from ai_dm.state.scene import SceneState

DRAGON = Path(__file__).resolve().parents[3] / "campaigns" / "drunk_dragon"
ELIXIR = "stoneskin_elixir"
POTION = "potion_of_healing"


@pytest.fixture
def dragon(cfg):
    registry = load_registry([pack_content_dir(DRAGON)])
    bundle = new_world_from_pack(
        registry, cfg, load_pack(DRAGON, registry), hero="grey", seed=1, world_id="w1",
        saved_at="2026-01-01T00:00:00",
    )
    return registry, bundle


def drink(registry, cfg, bundle, item_id=ELIXIR):
    ctx = make_ctx(registry, cfg, bundle=bundle)
    return ctx, apply(ctx, req("use_item", item_id=item_id, qty=1))


def ac_now(registry, bundle):
    return armor_class(bundle.heroes[0], registry, bundle.world.clock.now_s)


def kinds(bundle):
    now_s = bundle.world.clock.now_s
    return [e.kind for e in live_effects(bundle.heroes[0].creature, now_s)]


def test_use_item_elixir_is_accepted(dragon, cfg):
    registry, bundle = dragon
    ctx, d = drink(registry, cfg, bundle)
    assert d.status == "accepted"


def test_use_item_elixir_spends_one_item(dragon, cfg):
    registry, bundle = dragon
    before = count_item(bundle.heroes[0], ELIXIR)
    drink(registry, cfg, bundle)
    assert count_item(bundle.heroes[0], ELIXIR) == before - 1


def test_use_item_elixir_gives_ac_17(dragon, cfg):
    registry, bundle = dragon
    assert ac_now(registry, bundle) == 15
    drink(registry, cfg, bundle)
    assert ac_now(registry, bundle) == 17


def test_use_item_elixir_adds_ac_and_resist_effects(dragon, cfg):
    registry, bundle = dragon
    drink(registry, cfg, bundle)
    assert kinds(bundle).count("ac") == 1
    assert kinds(bundle).count("resist") == 2


def test_use_item_elixir_writes_log_line(dragon, cfg):
    registry, bundle = dragon
    ctx, d = drink(registry, cfg, bundle)
    text = "\n".join(d.log)
    assert "Каменная Кожа" in text
    assert "+2 КД" in text


def test_sheet_shows_ac_17_after_use_item(dragon, cfg, tmp_path):
    registry, bundle = dragon
    drink(registry, cfg, bundle)
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    text = "\n".join(app.handle("/sheet").lines)
    assert "КД 17 = " in text
    assert "Каменная Кожа" in text


def test_effect_from_outside_combat_stays_in_combat(dragon, cfg):
    registry, bundle = dragon
    ctx, _ = drink(registry, cfg, bundle)
    d = apply(ctx, combat_request())
    assert d.status == "accepted"
    assert bundle.session.active_combat is not None
    assert ac_now(registry, bundle) == 17
    assert kinds(bundle).count("resist") == 2


def test_effect_is_gone_after_an_hour(dragon, cfg):
    registry, bundle = dragon
    drink(registry, cfg, bundle)
    bundle.world.clock.now_s += 3601
    assert ac_now(registry, bundle) == 15
    assert kinds(bundle) == []


def test_effect_is_alive_before_an_hour(dragon, cfg):
    registry, bundle = dragon
    drink(registry, cfg, bundle)
    bundle.world.clock.now_s += 3500
    assert ac_now(registry, bundle) == 17


def test_use_item_healing_potion_heals_outside_combat(dragon, cfg):
    registry, bundle = dragon
    hero = bundle.heroes[0]
    add_item(hero, POTION, 1, cost_cp=0)
    hero.creature.hp_current = 1
    ctx, d = drink(registry, cfg, bundle, POTION)
    assert d.status == "accepted"
    assert hero.creature.hp_current > 1
    assert count_item(hero, POTION) == 0


def test_use_item_without_item_is_invalid_no_item(dragon, cfg):
    registry, bundle = dragon
    ctx, d = drink(registry, cfg, bundle, POTION)
    assert isinstance(d, Invalid)
    assert d.code == "no_item"


def test_use_item_without_item_changes_nothing(dragon, cfg):
    registry, bundle = dragon
    before = bundle.model_dump_json()
    ctx, d = drink(registry, cfg, bundle, POTION)
    assert isinstance(d, Invalid)
    assert bundle.model_dump_json() == before


def test_use_item_without_use_effect_is_rejected(dragon, cfg):
    registry, bundle = dragon
    add_item(bundle.heroes[0], "crowbar", 1, cost_cp=0)
    ctx, d = drink(registry, cfg, bundle, "crowbar")
    assert d.status == "rejected"
    assert d.signal_to_master


def test_potions_over_scene_limit_are_rejected(dragon, cfg):
    registry, bundle = dragon
    small = cfg.model_copy(deep=True)
    small.limits.consumables_per_scene = 1
    bundle.session.current_scene = SceneState(id="scene_1", started_at_s=0, location_id="vale")
    hero = bundle.heroes[0]
    add_item(hero, POTION, 2, cost_cp=0)
    hero.creature.hp_current = 1
    ctx = make_ctx(registry, small, bundle=bundle)
    assert apply(ctx, req("use_item", item_id=POTION, qty=1)).status == "accepted"
    d = apply(ctx, req("use_item", item_id=POTION, qty=1))
    assert d.status == "rejected"
    assert count_item(hero, POTION) == 1


# E3 (stage3-live-effects-visible): take_item и эликсир -- применять только через use_item

def take(registry, cfg, bundle, why, item_id=ELIXIR):
    ctx = make_ctx(registry, cfg, bundle=bundle)
    return apply(ctx, req("take_item", item_id=item_id, qty=1, why=why))


def test_take_item_elixir_spent_is_rejected(dragon, cfg):
    registry, bundle = dragon
    d = take(registry, cfg, bundle, "spent")
    assert d.status == "rejected"


def test_take_item_elixir_spent_signals_use_item(dragon, cfg):
    registry, bundle = dragon
    d = take(registry, cfg, bundle, "spent")
    assert "use_item" in d.signal_to_master


def test_take_item_elixir_spent_changes_nothing(dragon, cfg):
    registry, bundle = dragon
    before = bundle.model_dump_json()
    take(registry, cfg, bundle, "spent")
    assert bundle.model_dump_json() == before


def test_take_item_elixir_given_is_accepted(dragon, cfg):
    registry, bundle = dragon
    before = count_item(bundle.heroes[0], ELIXIR)
    d = take(registry, cfg, bundle, "given")
    assert d.status == "accepted"
    assert count_item(bundle.heroes[0], ELIXIR) == before - 1


def test_take_item_elixir_stolen_is_accepted(dragon, cfg):
    registry, bundle = dragon
    assert take(registry, cfg, bundle, "stolen").status == "accepted"


def test_take_item_elixir_lost_is_accepted(dragon, cfg):
    registry, bundle = dragon
    assert take(registry, cfg, bundle, "lost").status == "accepted"


def test_take_item_potion_spent_is_rejected(dragon, cfg):
    registry, bundle = dragon
    add_item(bundle.heroes[0], POTION, 1, cost_cp=0)
    d = take(registry, cfg, bundle, "spent", POTION)
    assert d.status == "rejected"
    assert count_item(bundle.heroes[0], POTION) == 1


def test_take_item_item_without_use_effect_spent_is_accepted(dragon, cfg):
    registry, bundle = dragon
    add_item(bundle.heroes[0], "crowbar", 1, cost_cp=0)
    assert take(registry, cfg, bundle, "spent", "crowbar").status == "accepted"


# E2: повторный эликсир -- эффект один, продлён, лог «уже действовала — продлена»

def expiry_s(bundle):
    effects = live_effects(bundle.heroes[0].creature, bundle.world.clock.now_s)
    return max(e.expires.value for e in effects if e.kind == "ac")


def test_second_elixir_keeps_one_ac_effect(dragon, cfg):
    registry, bundle = dragon
    drink(registry, cfg, bundle)
    drink(registry, cfg, bundle)
    assert kinds(bundle).count("ac") == 1
    assert kinds(bundle).count("resist") == 2


def test_second_elixir_does_not_stack_ac(dragon, cfg):
    registry, bundle = dragon
    drink(registry, cfg, bundle)
    drink(registry, cfg, bundle)
    assert ac_now(registry, bundle) == 17


def test_second_elixir_is_still_spent(dragon, cfg):
    registry, bundle = dragon
    before = count_item(bundle.heroes[0], ELIXIR)
    drink(registry, cfg, bundle)
    drink(registry, cfg, bundle)
    assert count_item(bundle.heroes[0], ELIXIR) == before - 2


def test_second_elixir_extends_duration(dragon, cfg):
    registry, bundle = dragon
    drink(registry, cfg, bundle)
    first = expiry_s(bundle)
    bundle.world.clock.now_s += 1800
    drink(registry, cfg, bundle)
    assert expiry_s(bundle) == first + 1800
    assert expiry_s(bundle) == bundle.world.clock.now_s + 3600


def test_second_elixir_log_says_extended(dragon, cfg):
    registry, bundle = dragon
    drink(registry, cfg, bundle)
    ctx, d = drink(registry, cfg, bundle)
    text = "\n".join(d.log)
    assert "Каменная Кожа уже действовала — продлена до" in text


def test_first_elixir_log_has_no_extended_note(dragon, cfg):
    registry, bundle = dragon
    ctx, d = drink(registry, cfg, bundle)
    assert "продлена" not in "\n".join(d.log)
