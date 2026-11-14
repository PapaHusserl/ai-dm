# К3б П4 (docs/plan-k3b.md, «Тесты» П4; решения 1-3, 9): призванные и Воскрешение вне боя и на
# старте боя (protocol/handlers/resources.py:cast_spell, handlers/combat.py:start_combat).
#   Оживление мёртвых (animate_dead, 1 минута): variant обязателен (skeleton | zombie) -- без него
#     bad_variant с перечнем «skeleton, zombie»; успех -- hero.minions == [Minion(monster_id,
#     "animate_dead", HP монстра, until_s = часы + 24 ч)].
#   Поиск фамильяра (find_familiar, ритуал): Minion(hawk, "find_familiar", 1, until_s=None);
#     повтор заменяет (фамильяр один).
#   Воскрешение (revivify, касание): цель -- убитый NPC с creature в локации героя, смерть не
#     раньше 60 с назад (с живым Покоем -- не раньше 10 дней); он встаёт alive с 1 HP, death None,
#     событие creature_revived, ячейка 3 круга тратится; иначе bad_target без изменений.
#   start_combat: призванные героя входят в бой участниками стороны героев в его зоне, истёкшие
#     (until_s <= часы) -- нет; в порядке инициативы они есть.
import sys
from pathlib import Path

import game_kit  # noqa: F401  (добавляет в sys.path соседние kit-ы)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "combat"))

from protocol_kit import combat_request, make_ctx, req  # noqa: E402
from test_utility_spells import put_npc, wiz  # noqa: E402
from test_wizard_rest_cast import cleric_bundle  # noqa: E402

from ai_dm.combat.engine import CombatEngine  # noqa: E402
from ai_dm.core.rng import Rng  # noqa: E402
from ai_dm.protocol.apply import apply  # noqa: E402
from ai_dm.protocol.decision import Invalid  # noqa: E402
from ai_dm.state.creature import ResourcePool  # noqa: E402
from ai_dm.state.death import DeathRecord  # noqa: E402
from ai_dm.state.hero import Minion  # noqa: E402

DAY = 86400
NOW = 10 * DAY


def cast_plain(registry, cfg, bundle, spell_id, circle, **fields):
    ctx = make_ctx(registry, cfg, bundle=bundle)
    return ctx, apply(ctx, req("cast_spell", spell_id=spell_id, circle=circle, **fields))


# Оживление мёртвых

def animator(registry):
    bundle = wiz(registry, "animate_dead")
    bundle.world.clock.now_s = NOW
    return bundle


def test_animate_dead_skeleton_becomes_a_minion(registry, cfg):
    bundle = animator(registry)
    cast_plain(registry, cfg, bundle, "animate_dead", 3, variant="skeleton")
    (minion,) = bundle.heroes[0].minions
    assert (minion.monster_id, minion.spell_id) == ("skeleton", "animate_dead")


def test_animate_dead_minion_starts_with_full_monster_hp(registry, cfg):
    bundle = animator(registry)
    cast_plain(registry, cfg, bundle, "animate_dead", 3, variant="skeleton")
    assert bundle.heroes[0].minions[0].hp_current == registry.get("monster", "skeleton").hp


def test_animate_dead_minion_lasts_twenty_four_hours(registry, cfg):
    bundle = animator(registry)
    cast_plain(registry, cfg, bundle, "animate_dead", 3, variant="skeleton")
    until = bundle.heroes[0].minions[0].until_s
    assert NOW + DAY <= until <= bundle.world.clock.now_s + DAY


def test_animate_dead_zombie_variant(registry, cfg):
    bundle = animator(registry)
    cast_plain(registry, cfg, bundle, "animate_dead", 3, variant="zombie")
    (minion,) = bundle.heroes[0].minions
    hit_points = registry.get("monster", "zombie").hp
    assert (minion.monster_id, minion.hp_current) == ("zombie", hit_points)


def test_animate_dead_spends_a_third_circle_slot(registry, cfg):
    bundle = animator(registry)
    pool = bundle.heroes[0].creature.resources["spell_slot:3"]
    before = pool.current
    cast_plain(registry, cfg, bundle, "animate_dead", 3, variant="skeleton")
    assert pool.current == before - 1


def test_animate_dead_without_variant_is_bad_variant(registry, cfg):
    bundle = animator(registry)
    _, d = cast_plain(registry, cfg, bundle, "animate_dead", 3)
    assert isinstance(d, Invalid)
    assert d.code == "bad_variant"


def test_bad_variant_lists_skeleton_and_zombie(registry, cfg):
    bundle = animator(registry)
    _, d = cast_plain(registry, cfg, bundle, "animate_dead", 3)
    assert "skeleton, zombie" in d.message


def test_unknown_variant_is_bad_variant(registry, cfg):
    bundle = animator(registry)
    _, d = cast_plain(registry, cfg, bundle, "animate_dead", 3, variant="dragon")
    assert d.code == "bad_variant"


def test_bad_variant_leaves_no_minion_and_keeps_the_slot(registry, cfg):
    bundle = animator(registry)
    pool = bundle.heroes[0].creature.resources["spell_slot:3"]
    before = pool.current
    cast_plain(registry, cfg, bundle, "animate_dead", 3)
    assert (bundle.heroes[0].minions, pool.current) == ([], before)


# Поиск фамильяра

def familiar_bundle(registry):
    bundle = wiz(registry, "find_familiar")
    bundle.world.clock.now_s = NOW
    return bundle


def test_find_familiar_ritual_gives_an_unlimited_hawk(registry, cfg):
    bundle = familiar_bundle(registry)
    _, d = cast_plain(registry, cfg, bundle, "find_familiar", 1, ritual=True)
    assert not isinstance(d, Invalid)
    assert bundle.heroes[0].minions == [
        Minion(monster_id="hawk", spell_id="find_familiar", hp_current=1, until_s=None)
    ]


def test_find_familiar_ritual_does_not_spend_a_slot(registry, cfg):
    bundle = familiar_bundle(registry)
    pool = bundle.heroes[0].creature.resources["spell_slot:1"]
    before = pool.current
    cast_plain(registry, cfg, bundle, "find_familiar", 1, ritual=True)
    assert pool.current == before


def test_repeated_find_familiar_replaces_the_hawk(registry, cfg):
    bundle = familiar_bundle(registry)
    cast_plain(registry, cfg, bundle, "find_familiar", 1, ritual=True)
    bundle.heroes[0].minions[0].hp_current = 0
    cast_plain(registry, cfg, bundle, "find_familiar", 1, ritual=True)
    assert [(m.monster_id, m.hp_current) for m in bundle.heroes[0].minions] == [("hawk", 1)]


def test_find_familiar_keeps_other_minions(registry, cfg):
    bundle = wiz(registry, "find_familiar", "animate_dead")
    cast_plain(registry, cfg, bundle, "animate_dead", 3, variant="skeleton")
    cast_plain(registry, cfg, bundle, "find_familiar", 1, ritual=True)
    assert sorted(m.monster_id for m in bundle.heroes[0].minions) == ["hawk", "skeleton"]


# Воскрешение вне боя

def reviver(registry, *spells):
    bundle = cleric_bundle(registry, prepared=("revivify", *spells))
    resources = bundle.heroes[0].creature.resources
    resources["spell_slot:2"] = ResourcePool(current=2, max=2)
    resources["spell_slot:3"] = ResourcePool(current=2, max=2)
    bundle.world.clock.now_s = NOW
    return bundle


def dead_npc(bundle, ago_s, **kwargs):
    npc = put_npc(bundle, status="dead", **kwargs)
    at_s = bundle.world.clock.now_s - ago_s
    npc.death = DeathRecord(cause="chance", at_s=at_s, location_id="vale")
    return npc


def revive(registry, cfg, bundle, target="orc"):
    return cast_plain(registry, cfg, bundle, "revivify", 3, target=target)


def test_revive_a_fresh_corpse_makes_the_npc_alive(registry, cfg):
    bundle = reviver(registry)
    npc = dead_npc(bundle, 50)
    revive(registry, cfg, bundle)
    assert npc.status == "alive"


def test_revived_npc_has_one_hit_point(registry, cfg):
    bundle = reviver(registry)
    npc = dead_npc(bundle, 50)
    revive(registry, cfg, bundle)
    assert npc.creature.hp_current == 1


def test_revived_npc_has_no_death_record(registry, cfg):
    bundle = reviver(registry)
    npc = dead_npc(bundle, 50)
    revive(registry, cfg, bundle)
    assert npc.death is None


def test_revive_emits_creature_revived(registry, cfg):
    bundle = reviver(registry)
    dead_npc(bundle, 50)
    ctx, _ = revive(registry, cfg, bundle)
    assert [e.type for e in ctx.events].count("creature_revived") == 1


def test_revive_spends_a_third_circle_slot_outside_combat(registry, cfg):
    bundle = reviver(registry)
    dead_npc(bundle, 50)
    revive(registry, cfg, bundle)
    assert bundle.heroes[0].creature.resources["spell_slot:3"].current == 1


def test_revive_at_the_sixty_second_limit_works(registry, cfg):
    bundle = reviver(registry)
    npc = dead_npc(bundle, 60)
    revive(registry, cfg, bundle)
    assert npc.status == "alive"


def test_revive_after_seventy_seconds_is_bad_target(registry, cfg):
    bundle = reviver(registry)
    dead_npc(bundle, 70)
    _, d = revive(registry, cfg, bundle)
    assert isinstance(d, Invalid)
    assert d.code == "bad_target"


def test_refused_revive_keeps_npc_dead_and_slot(registry, cfg):
    bundle = reviver(registry)
    npc = dead_npc(bundle, 70)
    revive(registry, cfg, bundle)
    assert (npc.status, bundle.heroes[0].creature.resources["spell_slot:3"].current) == ("dead", 2)


def test_revive_a_living_npc_is_bad_target(registry, cfg):
    bundle = reviver(registry)
    put_npc(bundle)
    _, d = revive(registry, cfg, bundle)
    assert d.code == "bad_target"


def test_revive_a_body_elsewhere_is_bad_target(registry, cfg):
    bundle = reviver(registry)
    dead_npc(bundle, 50, location="forest")
    _, d = revive(registry, cfg, bundle)
    assert d.code == "bad_target"


def test_revive_an_npc_without_creature_is_bad_target(registry, cfg):
    bundle = reviver(registry)
    dead_npc(bundle, 50, creature=False)
    _, d = revive(registry, cfg, bundle)
    assert d.code == "bad_target"


def test_revive_an_unknown_npc_is_unknown_npc(registry, cfg):
    bundle = reviver(registry)
    _, d = revive(registry, cfg, bundle, target="ghost")
    assert d.code == "unknown_npc"


def rested(registry, cfg, ago_s):
    # тело под Покоем: заклинание наложено на труп, срок возвращения идёт от смерти
    bundle = reviver(registry, "gentle_repose")
    npc = dead_npc(bundle, ago_s)
    _, d = cast_plain(registry, cfg, bundle, "gentle_repose", 2, target="orc")
    assert not isinstance(d, Invalid)
    return bundle, npc


def test_gentle_repose_extends_the_window_to_ten_days(registry, cfg):
    bundle, npc = rested(registry, cfg, 3 * DAY)
    revive(registry, cfg, bundle)
    assert npc.status == "alive"


def test_gentle_repose_window_ends_after_ten_days(registry, cfg):
    bundle, npc = rested(registry, cfg, 11 * DAY)
    _, d = revive(registry, cfg, bundle)
    assert (d.code, npc.status) == ("bad_target", "dead")


def test_three_days_without_repose_is_too_late(registry, cfg):
    bundle = reviver(registry)
    dead_npc(bundle, 3 * DAY)
    _, d = revive(registry, cfg, bundle)
    assert d.code == "bad_target"


# призванные на старте боя

def with_minions(registry, *minions):
    bundle = wiz(registry)
    bundle.world.clock.now_s = NOW
    bundle.heroes[0].minions = list(minions)
    return bundle


def start(registry, cfg, bundle, zone="hall"):
    ctx = make_ctx(registry, cfg, bundle=bundle)
    result = apply(ctx, combat_request(hero_zone=zone))
    assert not isinstance(result, Invalid)
    everyone = ctx.bundle.session.active_combat.participants
    return ctx, [p for p in everyone if p.ref.startswith("minion:")]


def skeleton(until_s=None, hp=13):
    return Minion(monster_id="skeleton", spell_id="animate_dead", hp_current=hp, until_s=until_s)


def test_start_combat_brings_the_minion_in(registry, cfg):
    _, found = start(registry, cfg, with_minions(registry, skeleton()))
    assert [p.monster_id for p in found] == ["skeleton"]


def test_start_combat_minion_is_on_the_heros_side_under_engine_control(registry, cfg):
    _, (p,) = start(registry, cfg, with_minions(registry, skeleton()))
    assert (p.side, p.group_id, p.controller) == ("heroes", "party", "engine")


def test_start_combat_minion_stands_in_the_heros_zone(registry, cfg):
    _, (p,) = start(registry, cfg, with_minions(registry, skeleton()), zone="balcony")
    assert p.zone_id == "balcony"


def test_start_combat_minion_keeps_saved_hp(registry, cfg):
    _, (p,) = start(registry, cfg, with_minions(registry, skeleton(hp=7)))
    assert p.creature.hp_current == 7


def test_start_combat_without_minions_adds_nobody(registry, cfg):
    _, found = start(registry, cfg, with_minions(registry))
    assert found == []


def test_start_combat_skips_an_expired_minion(registry, cfg):
    _, found = start(registry, cfg, with_minions(registry, skeleton(until_s=NOW - 1)))
    assert found == []


def test_start_combat_takes_a_minion_with_time_left(registry, cfg):
    _, found = start(registry, cfg, with_minions(registry, skeleton(until_s=NOW + 60)))
    assert len(found) == 1


def test_start_combat_takes_the_unlimited_familiar(registry, cfg):
    bird = Minion(monster_id="hawk", spell_id="find_familiar", hp_current=1, until_s=None)
    _, found = start(registry, cfg, with_minions(registry, bird))
    assert [p.monster_id for p in found] == ["hawk"]


def test_started_minion_gets_an_initiative_slot(registry, cfg):
    ctx, (p,) = start(registry, cfg, with_minions(registry, skeleton()))
    hero = ctx.bundle.heroes[0]
    engine = CombatEngine(
        ctx.bundle.session.active_combat, ctx.bundle.world, {hero.id: hero}, registry, cfg, Rng(5)
    )
    engine.start()
    assert p.ref in engine.state.initiative_order


# тексты лога (решения 14, 40) и сообщение отказа

def lines_of(d):
    return [line.strip() for line in d.log]


def test_animate_dead_skeleton_log_line(registry, cfg):
    _, d = cast_plain(registry, cfg, animator(registry), "animate_dead", 3, variant="skeleton")
    assert "Оживление мёртвых: Скелет поднимается" in lines_of(d)


def test_animate_dead_zombie_log_line_uses_the_data_name(registry, cfg):
    _, d = cast_plain(registry, cfg, animator(registry), "animate_dead", 3, variant="zombie")
    name = registry.get("monster", "zombie").name
    assert f"Оживление мёртвых: {name} поднимается" in lines_of(d)


def test_find_familiar_log_line(registry, cfg):
    _, d = cast_plain(registry, cfg, familiar_bundle(registry), "find_familiar", 1, ritual=True)
    assert "Поиск фамильяра: Ястреб" in lines_of(d)


def test_revive_log_line_outside_combat(registry, cfg):
    bundle = reviver(registry)
    npc = dead_npc(bundle, 50)
    _, d = revive(registry, cfg, bundle)
    assert f"Оживление: {npc.name} жив, 1 HP" in lines_of(d)


def test_start_combat_logs_the_minion_joining(registry, cfg):
    bundle = with_minions(registry, skeleton())
    ctx = make_ctx(registry, cfg, bundle=bundle)
    d = apply(ctx, combat_request(hero_zone="hall"))
    hero_name = bundle.heroes[0].name
    assert f"Скелет вступает в бой на стороне {hero_name}" in lines_of(d)


def test_start_combat_without_minions_has_no_joining_line(registry, cfg):
    ctx = make_ctx(registry, cfg, bundle=with_minions(registry))
    d = apply(ctx, combat_request(hero_zone="hall"))
    assert not [line for line in d.log if "вступает в бой" in line]


def test_revive_result_names_the_target(registry, cfg):
    bundle = reviver(registry)
    npc = dead_npc(bundle, 50)
    _, d = revive(registry, cfg, bundle)
    assert d.result["target"] == npc.name


def test_revive_keeps_the_cast_header_in_the_log(registry, cfg):
    bundle = reviver(registry)
    dead_npc(bundle, 50)
    _, d = revive(registry, cfg, bundle)
    assert "читает" in d.log[0]


def test_bad_target_message_mentions_the_repose_window(registry, cfg):
    bundle = reviver(registry)
    dead_npc(bundle, 70)
    _, d = revive(registry, cfg, bundle)
    assert "Покоем" in d.message and "10 дней" in d.message


# решение 37: воскрешённый встаёт чистым листом; решение 38: флага npc_dead нет

def stained(npc):
    from ai_dm.state.creature import ActiveEffect, AppliedCondition

    npc.creature.conditions += [
        AppliedCondition(id="unconscious", source="0_hp"), AppliedCondition(id="poisoned"),
    ]
    npc.creature.active_effects.append(
        ActiveEffect(id="bless", source="x", kind="spell", params={})
    )


def test_revived_npc_has_no_conditions(registry, cfg):
    bundle = reviver(registry)
    npc = dead_npc(bundle, 50)
    stained(npc)
    revive(registry, cfg, bundle)
    assert npc.creature.conditions == []


def test_revived_npc_has_no_effects(registry, cfg):
    bundle = reviver(registry)
    npc = dead_npc(bundle, 50)
    stained(npc)
    revive(registry, cfg, bundle)
    assert npc.creature.active_effects == []


def test_revived_npc_is_still_at_one_hit_point_after_cleaning(registry, cfg):
    bundle = reviver(registry)
    npc = dead_npc(bundle, 50)
    stained(npc)
    revive(registry, cfg, bundle)
    assert npc.creature.hp_current == 1


def test_revive_removes_the_npc_dead_flag(registry, cfg):
    bundle = reviver(registry)
    dead_npc(bundle, 50)
    bundle.world.flags["npc_dead:orc"] = True
    revive(registry, cfg, bundle)
    assert "npc_dead:orc" not in bundle.world.flags


def test_refused_revive_keeps_the_npc_dead_flag(registry, cfg):
    bundle = reviver(registry)
    dead_npc(bundle, 70)
    bundle.world.flags["npc_dead:orc"] = True
    revive(registry, cfg, bundle)
    assert bundle.world.flags.get("npc_dead:orc") is True


def test_revive_keeps_other_npc_dead_flags(registry, cfg):
    bundle = reviver(registry)
    dead_npc(bundle, 50)
    bundle.world.flags["npc_dead:orc"] = True
    bundle.world.flags["npc_dead:other"] = True
    revive(registry, cfg, bundle)
    assert bundle.world.flags.get("npc_dead:other") is True


# решение 39: призванные в /sheet-данных и в тексте животворящего заклинания

def test_animate_dead_leaves_no_spell_line_in_effects(registry, cfg):
    from ai_dm.game.sheet_text import effect_lines

    bundle = animator(registry)
    cast_plain(registry, cfg, bundle, "animate_dead", 3, variant="skeleton")
    now_s = bundle.world.clock.now_s
    lines = effect_lines(bundle.heroes[0], now_s, registry)
    assert not [line for line in lines if "Оживление мёртвых" in line]
