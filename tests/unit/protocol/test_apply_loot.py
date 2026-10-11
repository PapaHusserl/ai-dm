# Ожидаемый API (П6б этапа 3, STAGE3-PLAN A9, ТЗ 2.3 «Добыча»): gold hoard и предел редкости.
#   gold hoard (direction gain): клад логова по таблице srd/data/tables/hoard.yaml на полосе ПО 0-4
#     (кости с rng, сумма -- деньги героя). Условие: last_combat с лидером-логовом -- у LastCombat
#     поле lair_location_id (id локации логова из Group.lair_location_id лидера). Нет last_combat
#     или он без логова -> Invalid; второй раз -> Decision rejected с signal_to_master (looted).
#   Item в контенте: rarity (common|uncommon|rare|very_rare|legendary|artifact | None), magic: bool.
#   give_item магического предмета выше предела уровня ([loot.rarity_cap_by_level]: ур. 1-4 --
#     uncommon, ур. 5 -- rare) -> не выдан, clamped, report_tag "limit-exceeded", signal_to_master.
#     Не выше предела и немагические -- accepted, как раньше.
from pathlib import Path

import pytest
from protocol_kit import ScriptedRng, dump, make_bundle, make_ctx, req

from ai_dm.content.loader import load_registry
from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.rules.inventory import count_item
from ai_dm.state.session import LastCombat

SIZES = (4, 6, 8, 10, 12, 20, 100)


def write_item(root, item_id, rarity, magic):
    path = root / "items" / f"{item_id}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"id: {item_id}", f"name: {item_id}", "cost_cp: 100"]
    if rarity is not None:
        lines.append(f"rarity: {rarity}")
    lines.append(f"magic: {'true' if magic else 'false'}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture(scope="module")
def magic_registry(tmp_path_factory):
    root = Path(tmp_path_factory.mktemp("magic"))
    write_item(root, "ring_common", "common", True)
    write_item(root, "cloak_uncommon", "uncommon", True)
    write_item(root, "ring_rare", "rare", True)
    write_item(root, "sword_very_rare", "very_rare", True)
    write_item(root, "plain_rope", None, False)
    return load_registry([root])


def full_queues(face):
    return {f"d{size}": [min(face, size)] * 100 for size in SIZES}


def low_rng():
    return ScriptedRng(**full_queues(1))


def high_rng():
    return ScriptedRng(**{f"d{size}": [size] * 100 for size in SIZES})


def hoard_ctx(registry, cfg, rng, lair="goblin_den"):
    ctx = make_ctx(registry, cfg, rng)
    ctx.bundle.session.last_combat = LastCombat(defeated=["goblin_boss"], lair_location_id=lair)
    return ctx


def hoard_req():
    return req("gold", direction="gain", kind="hoard")


# hoard

def test_hoard_after_lair_combat_gives_money(registry, cfg):
    ctx = hoard_ctx(registry, cfg, low_rng())
    start = ctx.hero.money_cp
    d = apply(ctx, hoard_req())
    assert isinstance(d, Decision)
    assert d.status == "accepted"
    assert d.result["amount_cp"] > 0
    assert ctx.hero.money_cp == start + d.result["amount_cp"]
    assert d.log


def test_hoard_is_driven_by_rng_dice(registry, cfg):
    low = hoard_ctx(registry, cfg, low_rng())
    high = hoard_ctx(registry, cfg, high_rng())
    apply(low, hoard_req())
    apply(high, hoard_req())
    assert 0 < low.hero.money_cp < high.hero.money_cp


def test_hoard_is_deterministic_for_same_rolls(registry, cfg):
    first = hoard_ctx(registry, cfg, low_rng())
    second = hoard_ctx(registry, cfg, low_rng())
    apply(first, hoard_req())
    apply(second, hoard_req())
    assert first.hero.money_cp == second.hero.money_cp


def test_hoard_second_time_is_rejected(registry, cfg):
    ctx = hoard_ctx(registry, cfg, low_rng())
    apply(ctx, hoard_req())
    money = ctx.hero.money_cp
    d = apply(ctx, hoard_req())
    assert d.status == "rejected"
    assert d.signal_to_master
    assert ctx.hero.money_cp == money


def test_hoard_without_lair_is_invalid(registry, cfg):
    ctx = hoard_ctx(registry, cfg, low_rng(), lair=None)
    before = dump(ctx)
    d = apply(ctx, hoard_req())
    assert isinstance(d, Invalid)
    assert dump(ctx) == before


def test_hoard_without_combat_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg, low_rng())
    before = dump(ctx)
    d = apply(ctx, hoard_req())
    assert isinstance(d, Invalid)
    assert dump(ctx) == before


def test_hoard_during_active_combat_is_invalid(registry, cfg):
    from protocol_kit import combat_request

    ctx = make_ctx(registry, cfg, low_rng())
    apply(ctx, combat_request())
    start = ctx.hero.money_cp
    d = apply(ctx, hoard_req())
    assert isinstance(d, Invalid)
    assert ctx.hero.money_cp == start


def test_hoard_lose_direction_is_invalid(registry, cfg):
    ctx = hoard_ctx(registry, cfg, low_rng())
    d = apply(ctx, req("gold", direction="lose", kind="hoard"))
    assert isinstance(d, Invalid)


def test_hoard_does_not_block_individual_loot(registry, cfg):
    rng = ScriptedRng(**full_queues(1))
    ctx = hoard_ctx(registry, cfg, rng)
    apply(ctx, hoard_req())
    money = ctx.hero.money_cp
    d = apply(ctx, req("gold", direction="gain", kind="loot_individual"))
    assert d.status == "accepted"
    assert ctx.hero.money_cp > money


# редкость

def give(registry, cfg, item_id, level):
    bundle = make_bundle(registry)
    bundle.heroes[0].sheet.primary.level = level
    ctx = make_ctx(registry, cfg, bundle=bundle)
    return ctx, apply(ctx, req("give_item", item_id=item_id, qty=1))


def test_rare_item_at_level_3_is_clamped(magic_registry, cfg):
    ctx, d = give(magic_registry, cfg, "ring_rare", 3)
    assert d.status == "clamped"
    assert d.report_tag == "limit-exceeded"
    assert d.signal_to_master
    assert count_item(ctx.hero, "ring_rare") == 0


def test_clamped_rare_item_does_not_set_item_gained_flag(magic_registry, cfg):
    ctx, _ = give(magic_registry, cfg, "ring_rare", 3)
    assert "item_gained:ring_rare" not in ctx.bundle.world.flags


def test_uncommon_item_at_level_3_is_accepted(magic_registry, cfg):
    ctx, d = give(magic_registry, cfg, "cloak_uncommon", 3)
    assert d.status == "accepted"
    assert count_item(ctx.hero, "cloak_uncommon") == 1


def test_common_item_at_level_1_is_accepted(magic_registry, cfg):
    ctx, d = give(magic_registry, cfg, "ring_common", 1)
    assert d.status == "accepted"


def test_non_magic_item_is_not_checked(magic_registry, cfg):
    ctx, d = give(magic_registry, cfg, "plain_rope", 1)
    assert d.status == "accepted"
    assert count_item(ctx.hero, "plain_rope") == 1


def test_rare_item_at_level_5_is_accepted(magic_registry, cfg):
    ctx, d = give(magic_registry, cfg, "ring_rare", 5)
    assert d.status == "accepted"
    assert count_item(ctx.hero, "ring_rare") == 1


def test_very_rare_item_at_level_5_is_clamped(magic_registry, cfg):
    ctx, d = give(magic_registry, cfg, "sword_very_rare", 5)
    assert d.status == "clamped"
    assert count_item(ctx.hero, "sword_very_rare") == 0


def test_srd_items_without_rarity_still_work(registry, cfg):
    ctx, d = give(registry, cfg, "crowbar", 1)
    assert d.status == "accepted"


# D5: клад по сцене в локации-логове и флаг hoard:<loc>
# Допущение: логово без боя -- локация героя (или её предок) с тегом "lair" в Location.tags.

def test_hoard_after_combat_sets_flag_for_lair(registry, cfg):
    ctx = hoard_ctx(registry, cfg, low_rng())
    apply(ctx, hoard_req())
    assert ctx.bundle.world.flags["hoard:goblin_den"] is True


def lair_scene_ctx(registry, cfg, rng, hero_at="goblin_den"):
    ctx = make_ctx(registry, cfg, rng)
    ctx.bundle.world.locations["goblin_den"].tags.append("lair")
    ctx.hero.location_id = hero_at
    return ctx


def test_hoard_in_lair_scene_without_combat_is_given_once(registry, cfg):
    ctx = lair_scene_ctx(registry, cfg, low_rng())
    start = ctx.hero.money_cp
    d = apply(ctx, hoard_req())
    assert d.status == "accepted"
    assert ctx.hero.money_cp > start
    assert ctx.bundle.world.flags["hoard:goblin_den"] is True
    money = ctx.hero.money_cp
    d = apply(ctx, hoard_req())
    assert d.status == "rejected"
    assert ctx.hero.money_cp == money


def test_hoard_in_not_lair_scene_without_combat_is_invalid(registry, cfg):
    ctx = lair_scene_ctx(registry, cfg, low_rng(), hero_at="forest")
    d = apply(ctx, hoard_req())
    assert isinstance(d, Invalid)


def test_hoard_after_scene_hoard_is_rejected_after_combat_in_same_lair(registry, cfg):
    ctx = lair_scene_ctx(registry, cfg, low_rng())
    apply(ctx, hoard_req())
    ctx.bundle.session.last_combat = LastCombat(
        defeated=["goblin_boss"], lair_location_id="goblin_den"
    )
    money = ctx.hero.money_cp
    d = apply(ctx, hoard_req())
    assert d.status == "rejected"
    assert ctx.hero.money_cp == money


def test_hoard_after_combat_then_new_combat_in_same_lair_is_rejected(registry, cfg):
    ctx = hoard_ctx(registry, cfg, low_rng())
    apply(ctx, hoard_req())
    ctx.bundle.session.last_combat = LastCombat(
        defeated=["goblin_warrior"], lair_location_id="goblin_den"
    )
    money = ctx.hero.money_cp
    d = apply(ctx, hoard_req())
    assert d.status == "rejected"
    assert ctx.hero.money_cp == money
