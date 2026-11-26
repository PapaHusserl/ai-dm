# Ожидаемый API: ai_dm.protocol.apply.apply(ctx, request) -- см. контракт в protocol_kit.py.
# Ресурсы и время (ТЗ 2.1, 2.3, 4.00): damage вне боя, give_item / take_item, gold, award_xp,
# rest, advance_time. Для каждого -- accepted-путь с проверкой состояния и строки лога, лимиты 2.3:
#   * damage(deadly) без failed_roll_ref на ПРОВАЛЕННЫЙ бросок этого хода -> dangerous, clamped,
#     report_tag "limit-exceeded"; с таким ref -> accepted, 4d10 (уровень 5 -- 10d10);
#   * give_item: id в реестре (иначе Invalid unknown_item), qty > cfg.limits.give_item_max_qty ->
#     clamped до лимита; take_item: нет предмета -> Invalid not_in_inventory;
#   * gold: explicit gain > cfg.limits.gold_explicit_max_cp_by_level[уровень] -> clamped до потолка;
#     lose > остатка -> clamped до остатка; loot_individual -- rules.loot.individual_treasure(cr);
#     неизвестный cr -> Invalid unknown_cr;
#   * award_xp: rules.xp.quest_xp (minor/medium/major = 10/25/50% размера уровня из cfg);
#   * rest: rules.rests.short_rest / long_rest (время 1 ч / 8 ч из cfg);
#   * advance_time: category -> секунды из cfg (month -- длина месяца календаря); travel_to --
#     Connection.distance_m из локации героя и темп (по умолчанию normal) -> rules.time_ops;
#     герой переезжает, флаг visited:<loc>; нет связи -> Invalid no_route.
import pytest
from protocol_kit import ScriptedRng, dump, make_bundle, make_ctx, req

from ai_dm.core.clock import DAY
from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.rules.inventory import count_item
from ai_dm.state.creature import ActiveEffect, AppliedCondition, Expiry
from ai_dm.state.world import Connection, Location


def failed_ref(ctx):
    # проваленный бросок этого хода (d20 = 1 у неумелого в убеждении)
    return apply(ctx, req("skill_check", skill="persuasion", category="hard")).result["roll_ref"]


def desperate_ref(ctx):
    # проваленный бросок в позиции desperate: только после него deadly не урезается (шаг 265)
    d = apply(ctx, req("skill_check", skill="persuasion", category="hard", position="desperate"))
    return d.result["roll_ref"]


def hp_of(ctx):
    return ctx.hero.creature.hp_current


# damage

def test_damage_nuisance_rolls_1d10(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d10=[7]))
    d = apply(ctx, req("damage", severity="nuisance", damage_type="fire"))
    assert isinstance(d, Decision)
    assert d.status == "accepted"
    assert hp_of(ctx) == 193
    assert d.report_tag is None


def stoneskin_ctx(registry, cfg, expires_s):
    ctx = make_ctx(registry, cfg, ScriptedRng(d10=[8]))
    ctx.bundle.world.clock.now_s = 500
    ctx.hero.creature.active_effects = [ActiveEffect(
        id="stoneskin_elixir", source="h1", kind="resist",
        params={"damage_type": "bludgeoning"}, expires=Expiry(kind="seconds", value=expires_s),
    )]
    return ctx


def test_damage_expired_resistance_effect_does_not_halve(registry, cfg):
    ctx = stoneskin_ctx(registry, cfg, 100)
    apply(ctx, req("damage", severity="nuisance", damage_type="bludgeoning"))
    assert hp_of(ctx) == 192


def test_damage_live_resistance_effect_halves(registry, cfg):
    ctx = stoneskin_ctx(registry, cfg, 1000)
    apply(ctx, req("damage", severity="nuisance", damage_type="bludgeoning"))
    assert hp_of(ctx) == 196


def test_damage_dangerous_rolls_2d10(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d10=[3, 4]))
    d = apply(ctx, req("damage", severity="dangerous", damage_type="poison"))
    assert d.status == "accepted"
    assert hp_of(ctx) == 193


def test_damage_log_line_has_dice(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d10=[7]))
    d = apply(ctx, req("damage", severity="nuisance", damage_type="fire"))
    assert "Урон (опасность): 1d10 (7) огненный" in d.log[-1]


def test_damage_level_5_uses_bigger_dice(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d10=[1, 2]))
    ctx.hero.sheet.primary.level = 5
    apply(ctx, req("damage", severity="nuisance", damage_type="fire"))
    assert hp_of(ctx) == 197


def test_deadly_without_ref_is_clamped_to_dangerous(registry, cfg):
    rng = ScriptedRng(d10=[5, 5, 5, 5])
    ctx = make_ctx(registry, cfg, rng)
    d = apply(ctx, req("damage", severity="deadly", damage_type="fire"))
    assert d.status == "clamped"
    assert d.report_tag == "limit-exceeded"
    assert d.signal_to_master
    assert rng.calls == ["d10", "d10"]
    assert hp_of(ctx) == 190
    assert ctx.marks == ["limit-exceeded"]


def test_deadly_with_unknown_ref_is_clamped(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d10=[5, 5]))
    d = apply(ctx, req("damage", severity="deadly", damage_type="fire", failed_roll_ref="r99"))
    assert d.status == "clamped"
    assert hp_of(ctx) == 190


def test_deadly_with_ref_to_successful_roll_is_clamped(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[20], d10=[5, 5]))
    ok = apply(ctx, req("skill_check", skill="athletics", category="easy"))
    assert ok.result["outcome"] == "success"
    ref = ok.result["roll_ref"]
    d = apply(ctx, req("damage", severity="deadly", damage_type="fire", failed_roll_ref=ref))
    assert d.status == "clamped"
    assert hp_of(ctx) == 190


def test_deadly_with_ref_to_failed_roll_is_accepted(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1], d10=[5, 6, 7, 8]))
    ref = desperate_ref(ctx)
    d = apply(ctx, req("damage", severity="deadly", damage_type="fire", failed_roll_ref=ref))
    assert d.status == "accepted"
    assert d.report_tag is None
    assert hp_of(ctx) == 200 - 26
    assert ctx.marks == []


def test_deadly_level_5_with_failed_ref_rolls_10d10(registry, cfg):
    # воин 5 ур.: провал проверки добирает +1d10 Тактического ума (К2) -- первый d10 в очереди
    rng = ScriptedRng(d20=[1], d10=[1] * 11)
    ctx = make_ctx(registry, cfg, rng)
    ctx.hero.sheet.primary.level = 5
    ref = desperate_ref(ctx)
    assert rng.calls.count("d10") == 1
    d = apply(ctx, req("damage", severity="deadly", damage_type="fire", failed_roll_ref=ref))
    assert d.status == "accepted"
    assert rng.calls.count("d10") == 11


def test_clamped_deadly_level_5_becomes_dangerous_4d10(registry, cfg):
    rng = ScriptedRng(d10=[1] * 4)
    ctx = make_ctx(registry, cfg, rng)
    ctx.hero.sheet.primary.level = 5
    d = apply(ctx, req("damage", severity="deadly", damage_type="fire"))
    assert d.status == "clamped"
    assert rng.calls == ["d10"] * 4


def test_ref_from_other_turn_does_not_count(registry, cfg):
    # журнал бросков -- только этого хода: новый контекст ссылку "r1" не знает
    old = make_ctx(registry, cfg, ScriptedRng(d20=[1]))
    ref = failed_ref(old)
    ctx = make_ctx(registry, cfg, ScriptedRng(d10=[5, 5]))
    d = apply(ctx, req("damage", severity="deadly", damage_type="fire", failed_roll_ref=ref))
    assert d.status == "clamped"


def test_deadly_without_ref_signal_names_missing_failed_roll(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d10=[5, 5]))
    d = apply(ctx, req("damage", severity="deadly", damage_type="fire"))
    assert d.signal_to_master.startswith("Смертельный урон возможен только после")
    assert "позиция броска" not in d.signal_to_master


def test_deadly_after_risky_fail_signal_names_position_band(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1], d10=[5, 5]))
    ref = apply(
        ctx, req("skill_check", skill="persuasion", category="hard", position="risky")
    ).result["roll_ref"]
    d = apply(ctx, req("damage", severity="deadly", damage_type="fire", failed_roll_ref=ref))
    assert d.status == "clamped"
    assert d.signal_to_master.startswith(
        "Тяжесть вреда после провала задаёт позиция броска (risky: nuisance или dangerous, "
    )
    assert "desperate: dangerous или deadly): применён dangerous." in d.signal_to_master


# give_item / take_item

def test_give_item_adds_to_inventory(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("give_item", item_id="crowbar", qty=3))
    assert d.status == "accepted"
    assert count_item(ctx.hero, "crowbar") == 3
    assert d.log


def test_give_item_sets_item_gained_flag(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, req("give_item", item_id="crowbar", qty=1))
    assert ctx.bundle.world.flags["item_gained:crowbar"] is True


def test_give_item_adds_to_existing_stack(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, req("give_item", item_id="longsword", qty=1))
    assert count_item(ctx.hero, "longsword") == 2


def test_give_item_over_limit_is_clamped(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("give_item", item_id="crowbar", qty=500))
    assert d.status == "clamped"
    assert d.report_tag == "limit-exceeded"
    assert d.signal_to_master
    assert count_item(ctx.hero, "crowbar") == cfg.limits.give_item_max_qty == 20
    assert ctx.marks == ["limit-exceeded"]


def test_give_item_limit_comes_from_config(registry, cfg):
    small = cfg.model_copy(deep=True)
    small.limits.give_item_max_qty = 5
    ctx = make_ctx(registry, small)
    d = apply(ctx, req("give_item", item_id="crowbar", qty=9))
    assert d.status == "clamped"
    assert count_item(ctx.hero, "crowbar") == 5


def test_give_item_exactly_at_limit_is_accepted(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("give_item", item_id="crowbar", qty=20))
    assert d.status == "accepted"
    assert count_item(ctx.hero, "crowbar") == 20


def test_give_item_unknown_id_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, req("give_item", item_id="vorpal_sword_of_doom", qty=1))
    assert isinstance(d, Invalid)
    assert d.code == "unknown_item"
    assert dump(ctx) == before


def test_take_item_removes_from_inventory(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, req("give_item", item_id="crowbar", qty=3))
    d = apply(ctx, req("take_item", item_id="crowbar", qty=2, why="lost"))
    assert d.status == "accepted"
    assert count_item(ctx.hero, "crowbar") == 1
    assert d.log


def test_give_item_limit_is_per_request_not_per_stack(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, req("give_item", item_id="crowbar", qty=20))
    d = apply(ctx, req("give_item", item_id="crowbar", qty=20))
    assert d.status == "accepted"
    assert count_item(ctx.hero, "crowbar") == 40


def test_take_item_more_than_owned_is_clamped_to_owned(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, req("give_item", item_id="crowbar", qty=3))
    d = apply(ctx, req("take_item", item_id="crowbar", qty=10, why="lost"))
    assert isinstance(d, Decision)
    assert d.status == "clamped"
    assert d.report_tag == "limit-exceeded"
    assert d.signal_to_master
    assert count_item(ctx.hero, "crowbar") == 0
    assert ctx.marks == ["limit-exceeded"]


def test_take_item_exactly_owned_is_accepted(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, req("give_item", item_id="crowbar", qty=3))
    d = apply(ctx, req("take_item", item_id="crowbar", qty=3, why="lost"))
    assert d.status == "accepted"
    assert count_item(ctx.hero, "crowbar") == 0


def test_take_item_not_in_inventory_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, req("take_item", item_id="crowbar", qty=1, why="lost"))
    assert isinstance(d, Invalid)
    assert d.code == "not_in_inventory"
    assert dump(ctx) == before


def test_take_item_unknown_id_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("take_item", item_id="nonexistent_thing", qty=1, why="lost"))
    assert isinstance(d, Invalid)


# gold

def make_rich_ctx(registry, cfg, money, rng=None, level=1):
    bundle = make_bundle(registry)
    bundle.heroes[0].money_cp = money
    bundle.heroes[0].sheet.primary.level = level
    return make_ctx(registry, cfg, rng, bundle=bundle)


def test_gold_explicit_gain(registry, cfg):
    ctx = make_rich_ctx(registry, cfg, 100)
    d = apply(ctx, req("gold", direction="gain", kind="explicit", amount_cp=300))
    assert d.status == "accepted"
    assert ctx.hero.money_cp == 400
    assert d.log


def test_gold_explicit_gain_over_level_cap_is_clamped(registry, cfg):
    ctx = make_rich_ctx(registry, cfg, 0)
    d = apply(ctx, req("gold", direction="gain", kind="explicit", amount_cp=99_999))
    assert d.status == "clamped"
    assert d.report_tag == "limit-exceeded"
    assert ctx.hero.money_cp == cfg.limits.gold_explicit_max_cp_by_level[1] == 5000


def test_gold_cap_depends_on_level(registry, cfg):
    ctx = make_rich_ctx(registry, cfg, 0, level=3)
    apply(ctx, req("gold", direction="gain", kind="explicit", amount_cp=99_999))
    assert ctx.hero.money_cp == cfg.limits.gold_explicit_max_cp_by_level[3] == 25_000


def test_gold_explicit_at_cap_is_accepted(registry, cfg):
    ctx = make_rich_ctx(registry, cfg, 0)
    d = apply(ctx, req("gold", direction="gain", kind="explicit", amount_cp=5000))
    assert d.status == "accepted"


def test_gold_lose(registry, cfg):
    ctx = make_rich_ctx(registry, cfg, 500)
    d = apply(ctx, req("gold", direction="lose", kind="explicit", amount_cp=200))
    assert d.status == "accepted"
    assert ctx.hero.money_cp == 300


def test_gold_lose_more_than_balance_is_clamped(registry, cfg):
    ctx = make_rich_ctx(registry, cfg, 500)
    d = apply(ctx, req("gold", direction="lose", kind="explicit", amount_cp=900))
    assert d.status == "clamped"
    assert d.report_tag == "limit-exceeded"
    assert ctx.hero.money_cp == 0


def test_gold_lose_is_not_limited_by_level_cap(registry, cfg):
    ctx = make_rich_ctx(registry, cfg, 20_000)
    d = apply(ctx, req("gold", direction="lose", kind="explicit", amount_cp=10_000))
    assert d.status == "accepted"
    assert ctx.hero.money_cp == 10_000


def loot_ctx(registry, cfg, defeated, rng=None):
    from ai_dm.state.session import LastCombat

    ctx = make_rich_ctx(registry, cfg, 0, rng)
    ctx.bundle.session.last_combat = LastCombat(defeated=defeated)
    return ctx


def loot_req():
    return req("gold", direction="gain", kind="loot_individual")


def test_gold_loot_individual_uses_defeated_enemies_of_last_combat(registry, cfg):
    # P16: гоблин-воин (ПО 1/4) -> полоса 0-4: 4d6 x 100 мм
    rng = ScriptedRng(d6=[1, 2, 3, 4])
    ctx = loot_ctx(registry, cfg, ["goblin_warrior"], rng)
    d = apply(ctx, loot_req())
    assert d.status == "accepted"
    assert ctx.hero.money_cp == 1000
    assert rng.left("d6") == 0


def test_gold_loot_individual_sums_all_defeated(registry, cfg):
    rng = ScriptedRng(d6=[1, 1, 1, 1, 2, 2, 2, 2])
    ctx = loot_ctx(registry, cfg, ["goblin_warrior", "goblin_boss"], rng)
    apply(ctx, loot_req())
    assert ctx.hero.money_cp == 400 + 800
    assert rng.left("d6") == 0


def test_gold_loot_individual_ignores_cr_from_model(registry, cfg):
    # cr от модели не влияет: добыча по врагам боя
    rng = ScriptedRng(d6=[1, 1, 1, 1])
    ctx = loot_ctx(registry, cfg, ["goblin_warrior"], rng)
    apply(ctx, req("gold", direction="gain", kind="loot_individual", cr="17"))
    assert ctx.hero.money_cp == 400


def test_gold_loot_individual_is_not_clamped_for_amount_field(registry, cfg):
    # таблица сама определяет сумму; потолок explicit тут не применяется
    rng = ScriptedRng(d6=[6, 6, 6, 6])
    ctx = loot_ctx(registry, cfg, ["goblin_warrior"], rng)
    d = apply(ctx, loot_req())
    assert d.status == "accepted"
    assert ctx.hero.money_cp == 2400


def test_gold_loot_individual_second_time_is_rejected(registry, cfg):
    rng = ScriptedRng(d6=[1, 1, 1, 1])
    ctx = loot_ctx(registry, cfg, ["goblin_warrior"], rng)
    apply(ctx, loot_req())
    d = apply(ctx, loot_req())
    assert d.status == "rejected"
    assert d.signal_to_master
    assert ctx.hero.money_cp == 400


def test_gold_loot_individual_without_combat_is_invalid(registry, cfg):
    ctx = make_rich_ctx(registry, cfg, 0)
    before = dump(ctx)
    d = apply(ctx, loot_req())
    assert isinstance(d, Invalid)
    assert dump(ctx) == before


def test_gold_loot_individual_during_active_combat_is_invalid(registry, cfg):
    from protocol_kit import combat_request

    ctx = make_rich_ctx(registry, cfg, 0)
    apply(ctx, combat_request())
    d = apply(ctx, loot_req())
    assert isinstance(d, Invalid)
    assert ctx.hero.money_cp == 0


def test_gold_loot_individual_after_empty_defeated_gives_nothing(registry, cfg):
    ctx = loot_ctx(registry, cfg, [])
    d = apply(ctx, loot_req())
    assert ctx.hero.money_cp == 0
    assert getattr(d, "status", "accepted") != "clamped"


def test_gold_loot_after_new_combat_can_be_taken_again(registry, cfg):
    from ai_dm.state.session import LastCombat

    rng = ScriptedRng(d6=[1, 1, 1, 1, 2, 2, 2, 2])
    ctx = loot_ctx(registry, cfg, ["goblin_warrior"], rng)
    apply(ctx, loot_req())
    ctx.bundle.session.last_combat = LastCombat(defeated=["goblin_warrior"])
    d = apply(ctx, loot_req())
    assert d.status == "accepted"
    assert ctx.hero.money_cp == 400 + 800


# give_item: расходники за сцену (P16)

def test_fourth_healing_potion_in_scene_is_clamped(registry, cfg):
    ctx = make_ctx(registry, cfg)
    for _ in range(3):
        assert apply(ctx, req("give_item", item_id="potion_of_healing", qty=1)).status == "accepted"
    d = apply(ctx, req("give_item", item_id="potion_of_healing", qty=1))
    assert d.status == "clamped"
    assert d.signal_to_master
    assert count_item(ctx.hero, "potion_of_healing") == 3


def test_potions_in_one_request_are_cut_to_scene_limit(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("give_item", item_id="potion_of_healing", qty=5))
    assert d.status == "clamped"
    assert count_item(ctx.hero, "potion_of_healing") == cfg.limits.consumables_per_scene == 3


def test_consumable_limit_comes_from_config(registry, cfg):
    small = cfg.model_copy(deep=True)
    small.limits.consumables_per_scene = 1
    ctx = make_ctx(registry, small)
    apply(ctx, req("give_item", item_id="potion_of_healing", qty=1))
    d = apply(ctx, req("give_item", item_id="potion_of_healing", qty=1))
    assert d.status == "clamped"


def test_non_consumables_do_not_use_consumable_limit(registry, cfg):
    ctx = make_ctx(registry, cfg)
    for _ in range(5):
        assert apply(ctx, req("give_item", item_id="crowbar", qty=1)).status == "accepted"
    assert count_item(ctx.hero, "crowbar") == 5


def test_consumable_limit_resets_in_new_scene(registry, cfg):
    from ai_dm.state.scene import SceneState

    ctx = make_ctx(registry, cfg)
    apply(ctx, req("give_item", item_id="potion_of_healing", qty=3))
    ctx.bundle.session.current_scene = SceneState(id="scene_2", started_at_s=0, location_id="vale")
    d = apply(ctx, req("give_item", item_id="potion_of_healing", qty=1))
    assert d.status == "accepted"


# Invalid перечисляет допустимые id (E2)

def test_unknown_item_invalid_lists_allowed_ids(registry, cfg):
    d = apply(make_ctx(registry, cfg), req("give_item", item_id="nope", qty=1))
    assert "crowbar" in d.message
    # подсказка показывает первые 20 id по алфавиту; пять новых id боеприпасов (arrows, bolts, …)
    # вытеснили potion_of_healing за обрезку, поэтому проверяем предмет из начала списка
    assert "arrows" in d.message


def test_no_route_invalid_lists_reachable_locations(registry, cfg):
    d = apply(make_ctx(registry, cfg), req("advance_time", travel_to="goblin_den"))
    assert d.code == "no_route"
    assert "forest" in d.message


def test_unknown_location_invalid_lists_ids(registry, cfg):
    d = apply(make_ctx(registry, cfg), req("advance_time", travel_to="nowhere"))
    assert d.code in ("unknown_location", "no_route")
    assert "forest" in d.message


def test_unknown_npc_invalid_lists_ids(registry, cfg):
    d = apply(
        make_ctx(registry, cfg),
        req("npc_update", npc_id="nobody", attitude_delta=5),
    )
    assert d.code == "unknown_npc"
    assert "aldric" in d.message
    assert "grakh" in d.message


def test_unknown_monster_invalid_lists_ids(registry, cfg):
    from protocol_kit import combat_request

    request = combat_request(
        enemies=[{"ref": "g1", "monster_id": "tarrasque_9", "zone": "hall", "group": "goblins"}]
    )
    d = apply(make_ctx(registry, cfg), request)
    assert d.code == "unknown_monster"
    assert "goblin_warrior" in d.message


def test_allowed_ids_list_is_capped_at_about_twenty(registry, cfg):
    ctx = make_ctx(registry, cfg)
    for i in range(40):
        ctx.bundle.world.locations[f"loc_{i:02d}"] = Location(id=f"loc_{i:02d}", name="X")
    d = apply(ctx, req("npc_create", id="n1", name="Н", means=["м"], location_id="nowhere"))
    assert d.code == "unknown_location"
    assert d.message.count("loc_") <= 20


# award_xp

@pytest.mark.parametrize("scale, xp", [("minor", 30), ("medium", 75), ("major", 150)])
def test_award_xp_level_1(scale, xp, registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("award_xp", scale=scale, reason="нашёл тайник"))
    assert d.status == "accepted"
    assert ctx.hero.sheet.xp == xp
    assert d.log


def test_award_xp_medium_is_quarter_of_level_size(registry, cfg):
    # уровень 2: размер уровня 600 (до 3-го), 25% = 150
    ctx = make_ctx(registry, cfg)
    ctx.hero.sheet.primary.level = 2
    apply(ctx, req("award_xp", scale="medium", reason="квест"))
    assert ctx.hero.sheet.xp == 150


def test_award_xp_percent_comes_from_config(registry, cfg):
    changed = cfg.model_copy(deep=True)
    changed.xp.quest_medium_percent = 50
    ctx = make_ctx(registry, changed)
    apply(ctx, req("award_xp", scale="medium", reason="квест"))
    assert ctx.hero.sheet.xp == 150


def test_award_xp_adds_to_existing(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.hero.sheet.xp = 100
    apply(ctx, req("award_xp", scale="minor", reason="находка"))
    assert ctx.hero.sheet.xp == 130


# rest

def test_long_rest_restores_hp_and_takes_8_hours(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.hero.creature.hp_current = 50
    d = apply(ctx, req("rest", kind="long"))
    assert d.status == "accepted"
    assert hp_of(ctx) == 200
    assert ctx.bundle.world.clock.now_s == cfg.time.long_rest_s == 28800


def test_short_rest_takes_one_hour(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("rest", kind="short"))
    assert d.status == "accepted"
    assert ctx.bundle.world.clock.now_s == 3600


def test_short_rest_with_hit_die_heals_by_roll(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d10=[5]))
    ctx.hero.creature.hp_current = 100
    apply(ctx, req("rest", kind="short", hit_dice=1))
    assert hp_of(ctx) == 107
    assert ctx.hero.creature.resources["hit_dice:d10"].current == 0


def test_short_rest_log_line_exists(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert apply(ctx, req("rest", kind="short")).log


# advance_time

@pytest.mark.parametrize(
    "category, seconds",
    [("hour", 3600), ("day", DAY), ("week", 7 * DAY), ("month", 30 * DAY)],
)
def test_advance_time_by_category(category, seconds, registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("advance_time", category=category, purpose="wait"))
    assert d.status == "accepted"
    assert ctx.bundle.world.clock.now_s == seconds
    assert d.log


def test_advance_time_month_uses_calendar_month_length(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.clock.calendar.months[0].days = 31
    apply(ctx, req("advance_time", category="month", purpose="wait"))
    assert ctx.bundle.world.clock.now_s == 31 * DAY


def test_advance_time_does_not_move_hero_by_category(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, req("advance_time", category="hour", purpose="wait"))
    assert ctx.hero.location_id == "vale"


def test_travel_takes_time_by_distance(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("advance_time", travel_to="forest"))
    assert d.status == "accepted"
    # 4800 м, темп normal 4800 м/ч
    assert ctx.bundle.world.clock.now_s == 3600
    assert ctx.hero.location_id == "forest"


def test_travel_pace_changes_time(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, req("advance_time", travel_to="forest", pace="slow"))
    assert ctx.bundle.world.clock.now_s == 5400


def test_fast_pace_is_quicker(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, req("advance_time", travel_to="forest", pace="fast"))
    assert ctx.bundle.world.clock.now_s == 2700


def test_travel_sets_visited_flag_and_event(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, req("advance_time", travel_to="forest"))
    assert ctx.bundle.world.flags["visited:forest"] is True
    assert "location_visited" in [e.type for e in ctx.events]


# шаг 262, П2: вход во враждебную локацию расставляет скрытое; путь обрывается на первой
# враждебной нерасставленной локации; найденная ловушка -- в signal_to_master, не в ленте.

def deep_ctx(registry, cfg):
    # Вейл -> Лес (враждебный, ловушка от пака) -> Чаща (не враждебная)
    ctx = make_ctx(registry, cfg)
    world = ctx.bundle.world
    world.locations["forest"].connections.append(Connection(to="deep", distance_m=1000))
    world.locations["deep"] = Location(id="deep", name="Чаща")
    world.locations["forest"].hostile = True
    world.locations["forest"].traps = ["falling_net"]
    return ctx


def test_travel_into_hostile_location_places_hidden(registry, cfg):
    ctx = deep_ctx(registry, cfg)
    apply(ctx, req("advance_time", travel_to="forest"))
    hidden = ctx.bundle.world.locations["forest"].hidden
    assert [t.trap_id for t in hidden.traps] == ["falling_net"]


def test_travel_into_peaceful_location_leaves_hidden_empty(registry, cfg):
    ctx = deep_ctx(registry, cfg)
    ctx.bundle.world.locations["forest"].hostile = False
    apply(ctx, req("advance_time", travel_to="forest"))
    assert ctx.bundle.world.locations["forest"].hidden is None


def test_travel_stops_at_first_hostile_unplaced_location(registry, cfg):
    ctx = deep_ctx(registry, cfg)
    apply(ctx, req("advance_time", travel_to="deep"))
    world = ctx.bundle.world
    assert ctx.hero.location_id == "forest"
    assert world.locations["forest"].hidden is not None
    assert "visited:deep" not in world.flags


def test_travel_through_placed_hostile_location_reaches_target(registry, cfg):
    ctx = deep_ctx(registry, cfg)
    apply(ctx, req("advance_time", travel_to="deep"))
    ctx.hero.location_id = "vale"
    apply(ctx, req("advance_time", travel_to="deep"))
    assert ctx.hero.location_id == "deep"


def test_found_trap_name_goes_to_signal_not_to_log_or_dc(registry, cfg):
    ctx = deep_ctx(registry, cfg)
    d = apply(ctx, req("advance_time", travel_to="forest"))
    assert ctx.bundle.world.locations["forest"].hidden.traps[0].state == "found"
    assert "Падающая сеть" in d.signal_to_master
    assert "СЛ" not in d.signal_to_master
    assert all("Падающая сеть" not in line and "ловуш" not in line.lower() for line in d.log)


def test_cut_route_signal_names_stop_and_target(registry, cfg):
    ctx = deep_ctx(registry, cfg)
    d = apply(ctx, req("advance_time", travel_to="deep"))
    assert "Лес" in d.signal_to_master
    assert "Чаща" in d.signal_to_master


def test_route_without_cut_has_no_cut_signal(registry, cfg):
    ctx = deep_ctx(registry, cfg)
    d = apply(ctx, req("advance_time", travel_to="forest"))
    assert "Чаща" not in (d.signal_to_master or "")


def test_repeat_route_through_placed_location_has_no_signal(registry, cfg):
    ctx = deep_ctx(registry, cfg)
    apply(ctx, req("advance_time", travel_to="deep"))
    ctx.hero.location_id = "vale"
    d = apply(ctx, req("advance_time", travel_to="deep"))
    assert not d.signal_to_master


def test_cut_arrival_line_names_target_and_stop_with_via(registry, cfg):
    # Р20 (а): «Путь к «<цель>» прерван в «<место>»: N с» + хвост «(через ...)» как у обычной строки
    ctx = deep_ctx(registry, cfg)
    world = ctx.bundle.world
    world.locations["mid"] = Location(id="mid", name="Брод")
    world.locations["vale"].connections = [Connection(to="mid", distance_m=1000)]
    world.locations["mid"].connections.append(Connection(to="forest", distance_m=4800))
    d = apply(ctx, req("advance_time", travel_to="deep"))
    assert d.log[0] == f"Путь к «Чаща» прерван в «Лес»: {d.result['seconds']} с (через Брод)"


def test_cut_arrival_line_without_via(registry, cfg):
    ctx = deep_ctx(registry, cfg)
    d = apply(ctx, req("advance_time", travel_to="deep"))
    assert d.log[0] == f"Путь к «Чаща» прерван в «Лес»: {d.result['seconds']} с"


def test_uncut_arrival_line_is_unchanged(registry, cfg):
    ctx = deep_ctx(registry, cfg)
    d = apply(ctx, req("advance_time", travel_to="forest"))
    assert d.log[0] == f"Путь в «Лес»: {d.result['seconds']} с"


def test_leg_line_on_cut_route_keeps_target_and_counts_left_to_it(registry, cfg):
    # Р20 (б): отрезок долгого пути -- прежняя цель, «осталось» до неё
    # (15000 м = 11250 с, прошло 7200)
    from ai_dm.rules import time_ops

    ctx = deep_ctx(registry, cfg)
    ctx.bundle.world.locations["vale"].connections[0].distance_m = 14000
    d = apply(ctx, req("advance_time", travel_to="deep"))
    assert d.result["left_s"] == 4050
    assert d.log[0] == (
        f"В пути к «Чаща»: прошло {time_ops.minutes_text(7200)}, "
        f"осталось {time_ops.minutes_text(4050)}"
    )


def test_cut_signal_joins_found_traps_and_cut_note_with_space(registry, cfg):
    ctx = deep_ctx(registry, cfg)
    d = apply(ctx, req("advance_time", travel_to="deep"))
    assert "Опиши, как он их заметил. Герой встал в «Лес», не дойдя до «Чаща»" in d.signal_to_master


def test_cut_at_exact_journey_limit_is_arrival_not_leg(registry, cfg):
    # путь до Леса ровно в один отрезок (total == journey_from_s): прибытие с обрывом, не отрезок
    ctx = deep_ctx(registry, cfg)
    ctx.bundle.world.locations["vale"].connections[0].distance_m = 9600
    d = apply(ctx, req("advance_time", travel_to="deep"))
    assert d.result["seconds"] == cfg.time.journey_from_s
    assert d.log[0] == f"Путь к «Чаща» прерван в «Лес»: {d.result['seconds']} с"
    assert ctx.hero.journey is None
    assert ctx.hero.location_id == "forest"


def test_cut_on_long_route_waits_for_the_next_leg(registry, cfg):
    # до Леса дальше одного отрезка: первый отрезок -- на дороге, расстановки и сигнала нет
    ctx = deep_ctx(registry, cfg)
    world = ctx.bundle.world
    world.locations["vale"].connections[0].distance_m = 14000
    first = apply(ctx, req("advance_time", travel_to="deep"))
    assert world.locations[ctx.hero.location_id].temporary
    assert world.locations["forest"].hidden is None
    assert not first.signal_to_master
    assert ctx.hero.journey.to == "deep"
    apply(ctx, req("advance_time", travel_to="deep"))
    assert ctx.hero.location_id == "forest"
    assert ctx.hero.journey is None
    assert world.locations["forest"].hidden is not None
    assert "visited:deep" not in world.flags


def test_travel_without_route_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, req("advance_time", travel_to="goblin_den"))
    assert isinstance(d, Invalid)
    assert d.code == "no_route"
    assert dump(ctx) == before


def test_travel_uses_connection_recorded_only_in_target(registry, cfg):
    ctx = make_ctx(registry, cfg)
    den = ctx.bundle.world.locations["goblin_den"]
    den.connections.append(Connection(to="vale", distance_m=4800))
    d = apply(ctx, req("advance_time", travel_to="goblin_den"))
    assert d.status == "accepted"
    assert ctx.hero.location_id == "goblin_den"
    assert ctx.bundle.world.clock.now_s == 3600


def test_travel_to_current_location_is_rejected_as_already_here(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, req("advance_time", travel_to="vale"))
    assert isinstance(d, Decision)
    assert d.status == "rejected"
    assert d.reason == "герой уже в «Вейл»"
    assert dump(ctx) == before


def test_travel_already_here_signal_tells_narrator_not_to_repeat(registry, cfg):
    d = apply(make_ctx(registry, cfg), req("advance_time", travel_to="vale"))
    assert "Герой уже в «Вейл»" in d.signal_to_master
    assert "travel_to не повторяй" in d.signal_to_master


def test_travel_to_unknown_location_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("advance_time", travel_to="atlantis"))
    assert isinstance(d, Invalid)


def test_advance_time_needs_exactly_one_of_category_and_travel(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    both = apply(ctx, req("advance_time", category="hour", purpose="wait", travel_to="forest"))
    none = apply(ctx, req("advance_time"))
    assert isinstance(both, Invalid) and both.code == "category_travel_to_or_until"
    assert isinstance(none, Invalid) and none.code == "category_travel_to_or_until"
    assert dump(ctx) == before


# Фикс ЖП4 П2 (131): advance_time until -- до утра, до часа, до длинного отдыха

def clock_at(registry, cfg, now_s):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.clock.now_s = now_s
    # кулдаун 12 ч: долгий отдых недоступен, сдвиг на ≥ 8 ч -- не сон (шаг 217)
    ctx.hero.long_rest_end_s = now_s
    return ctx


def hm(hours, minutes=0, day=1):
    return day * DAY + hours * 3600 + minutes * 60


def until(**fields):
    return req("advance_time", **fields)


@pytest.mark.parametrize(
    "fields",
    [
        {"category": "hour", "until": "morning"},
        {"travel_to": "forest", "until": "morning"},
        {"category": "hour", "travel_to": "forest", "until": "morning"},
    ],
)
def test_until_with_other_field_is_invalid(fields, registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, until(**fields))
    assert isinstance(d, Invalid)
    assert d.code == "category_travel_to_or_until"
    assert "category, travel_to и until" in d.message
    assert dump(ctx) == before


def test_until_neutral_values_are_none():
    request = until(category="hour", until="none", until_hour=-1)
    assert (request.until, request.until_hour) == (None, None)


def test_until_neutral_in_schema_constant():
    from ai_dm.protocol.requests import AdvanceTime

    assert (AdvanceTime.NEUTRAL["until"], AdvanceTime.NEUTRAL["until_hour"]) == ("none", -1)


def test_until_hour_above_23_is_schema_error():
    with pytest.raises(ValueError):
        until(until="hour", until_hour=25)


def test_until_unknown_target_is_schema_error():
    with pytest.raises(ValueError):
        until(until="noon")


def test_morning_hour_default_is_six(cfg):
    assert cfg.time.morning_hour == 6


@pytest.mark.parametrize("hour", [-1, 24])
def test_morning_hour_out_of_range_is_config_error(hour):
    from ai_dm.config.settings import load_rules_config

    with pytest.raises(ValueError):
        load_rules_config(f"[time]\nmorning_hour = {hour}\n")


def test_morning_hour_follows_config(registry):
    from ai_dm.config.settings import load_rules_config

    ctx = clock_at(registry, load_rules_config("[time]\nmorning_hour = 8\n"), hm(5))
    apply(ctx, until(until="morning"))
    assert ctx.bundle.world.clock.now_s == hm(8)


def test_until_morning_in_evening_goes_to_next_morning(registry, cfg):
    ctx = clock_at(registry, cfg, hm(20, 6))
    d = apply(ctx, until(until="morning"))
    assert d.status == "accepted"
    assert d.result == {"seconds": 35640, "now_s": hm(6, day=2)}
    assert ctx.bundle.world.clock.now_s == hm(6, day=2)


def test_until_morning_log_is_time_line(registry, cfg):
    ctx = clock_at(registry, cfg, hm(20, 6))
    assert apply(ctx, until(until="morning")).log == ["Время идёт: 35640 с"]


def test_until_morning_before_dawn_is_same_day(registry, cfg):
    ctx = clock_at(registry, cfg, hm(5))
    d = apply(ctx, until(until="morning"))
    assert d.result["seconds"] == 3600
    assert ctx.bundle.world.clock.now_s == hm(6)


def test_until_morning_exactly_at_dawn_goes_to_tomorrow(registry, cfg):
    ctx = clock_at(registry, cfg, hm(6))
    d = apply(ctx, until(until="morning"))
    assert d.result["seconds"] == DAY
    assert ctx.bundle.world.clock.now_s == hm(6, day=2)


def test_until_morning_one_second_before_dawn(registry, cfg):
    ctx = clock_at(registry, cfg, hm(6) - 1)
    assert apply(ctx, until(until="morning")).result["seconds"] == 1


def test_until_morning_on_day_zero(registry, cfg):
    ctx = clock_at(registry, cfg, 3600)
    apply(ctx, until(until="morning"))
    assert ctx.bundle.world.clock.now_s == 6 * 3600


def test_until_hour_after_it_goes_to_tomorrow(registry, cfg):
    ctx = clock_at(registry, cfg, hm(7))
    d = apply(ctx, until(until="hour", until_hour=6))
    assert d.status == "accepted"
    assert ctx.bundle.world.clock.now_s == hm(6, day=2)


def test_until_hour_later_today(registry, cfg):
    ctx = clock_at(registry, cfg, hm(7, 30))
    apply(ctx, until(until="hour", until_hour=18))
    assert ctx.bundle.world.clock.now_s == hm(18)


def test_until_hour_midnight(registry, cfg):
    ctx = clock_at(registry, cfg, hm(23))
    apply(ctx, until(until="hour", until_hour=0))
    assert ctx.bundle.world.clock.now_s == hm(0, day=2)


def test_until_hour_ignores_morning_hour(registry, cfg):
    ctx = clock_at(registry, cfg, hm(5))
    apply(ctx, until(until="hour", until_hour=9))
    assert ctx.bundle.world.clock.now_s == hm(9)


def test_until_hour_without_hour_is_invalid(registry, cfg):
    ctx = clock_at(registry, cfg, hm(7))
    before = dump(ctx)
    d = apply(ctx, until(until="hour"))
    assert isinstance(d, Invalid)
    assert d.code == "until_hour_required"
    assert dump(ctx) == before


@pytest.mark.parametrize("target", ["morning", "long_rest"])
def test_until_hour_with_other_target_is_invalid(target, registry, cfg):
    ctx = clock_at(registry, cfg, hm(7))
    before = dump(ctx)
    d = apply(ctx, until(until=target, until_hour=9))
    assert isinstance(d, Invalid)
    assert d.code == "until_hour_only_with_hour"
    assert dump(ctx) == before


def test_until_hour_zero_is_a_real_hour(registry, cfg):
    # until_hour=0 не «нет часа»: проверка по None, не по truthiness
    ctx = clock_at(registry, cfg, hm(7))
    assert apply(ctx, until(until="hour", until_hour=0)).status == "accepted"


def test_until_ends_expired_concentration(registry, cfg):
    from ai_dm.state.creature import Concentration

    ctx = clock_at(registry, cfg, hm(20))
    ctx.hero.creature.concentration = Concentration(spell_id="bless", circle=1, until_s=hm(21))
    d = apply(ctx, until(until="morning"))
    assert d.result["concentration_ended"] == "bless"
    assert ctx.hero.creature.concentration is None
    assert d.log[-1].startswith("Концентрация:")


# Фикс ЖП4 (132): travel_to -- путь по карте через промежуточные локации

def hill_ctx(registry, cfg):
    # vale -> forest 4800 (кит), forest -> hill 2400
    ctx = make_ctx(registry, cfg)
    world = ctx.bundle.world
    world.locations["hill"] = Location(id="hill", name="Холм")
    world.locations["forest"].connections.append(Connection(to="hill", distance_m=2400))
    return ctx


def test_travel_through_two_hops_is_accepted(registry, cfg):
    ctx = hill_ctx(registry, cfg)
    d = apply(ctx, req("advance_time", travel_to="hill"))
    assert d.status == "accepted"
    assert ctx.hero.location_id == "hill"


def test_travel_through_two_hops_sums_time(registry, cfg):
    ctx = hill_ctx(registry, cfg)
    d = apply(ctx, req("advance_time", travel_to="hill"))
    assert ctx.bundle.world.clock.now_s == 5400
    assert d.result["seconds"] == 5400


def test_travel_through_two_hops_fast_pace_sums_by_pace(registry, cfg):
    ctx = hill_ctx(registry, cfg)
    apply(ctx, req("advance_time", travel_to="hill", pace="fast"))
    # 4800 м и 2400 м при 6400 м/ч: 2700 + 1350
    assert ctx.bundle.world.clock.now_s == 4050


def test_travel_marks_every_hop_visited(registry, cfg):
    ctx = hill_ctx(registry, cfg)
    apply(ctx, req("advance_time", travel_to="hill"))
    flags = ctx.bundle.world.flags
    assert flags["visited:forest"] is True
    assert flags["visited:hill"] is True


def test_travel_emits_location_visited_per_hop_in_order(registry, cfg):
    ctx = hill_ctx(registry, cfg)
    apply(ctx, req("advance_time", travel_to="hill"))
    visited = [e.data["id"] for e in ctx.events if e.type == "location_visited"]
    assert visited == ["forest", "hill"]


def test_travel_result_has_path(registry, cfg):
    ctx = hill_ctx(registry, cfg)
    d = apply(ctx, req("advance_time", travel_to="hill"))
    assert d.result["path"] == ["forest", "hill"]


def test_travel_result_has_now_s_and_location_id(registry, cfg):
    ctx = hill_ctx(registry, cfg)
    d = apply(ctx, req("advance_time", travel_to="hill"))
    assert d.result["now_s"] == 5400
    assert d.result["location_id"] == "hill"


def test_travel_neighbor_result_path_is_target_only(registry, cfg):
    d = apply(make_ctx(registry, cfg), req("advance_time", travel_to="forest"))
    assert d.result["path"] == ["forest"]


def test_travel_log_names_intermediate_places(registry, cfg):
    ctx = hill_ctx(registry, cfg)
    d = apply(ctx, req("advance_time", travel_to="hill"))
    assert d.log[0] == "Путь в «Холм»: 5400 с (через Лес)"


def test_travel_log_lists_all_intermediate_places_in_order(registry, cfg):
    ctx = hill_ctx(registry, cfg)
    world = ctx.bundle.world
    world.locations["peak"] = Location(id="peak", name="Пик")
    world.locations["hill"].connections.append(Connection(to="peak", distance_m=1200))
    d = apply(ctx, req("advance_time", travel_to="peak"))
    assert d.log[0] == "Путь в «Пик»: 6300 с (через Лес, Холм)"


def test_travel_log_to_neighbor_has_no_via(registry, cfg):
    d = apply(make_ctx(registry, cfg), req("advance_time", travel_to="forest"))
    assert d.log[0] == "Путь в «Лес»: 3600 с"


def test_travel_moves_companion_to_final_target(registry, cfg):
    from ai_dm.state.world import NPC

    ctx = hill_ctx(registry, cfg)
    ctx.bundle.world.npcs["bran"] = NPC(
        id="bran", name="Бран", named=True, means=["m"], location_id="vale",
        follows=ctx.hero.id,
    )
    d = apply(ctx, req("advance_time", travel_to="hill"))
    assert ctx.bundle.world.npcs["bran"].location_id == "hill"
    assert "С тобой: Бран" in d.log


def test_travel_takes_shorter_of_two_routes(registry, cfg):
    ctx = hill_ctx(registry, cfg)
    ctx.bundle.world.locations["vale"].connections.append(Connection(to="hill", distance_m=9000))
    d = apply(ctx, req("advance_time", travel_to="hill"))
    assert d.result["path"] == ["forest", "hill"]
    assert ctx.bundle.world.clock.now_s == 5400


def test_travel_to_isolated_place_lists_neighbors(registry, cfg):
    ctx = hill_ctx(registry, cfg)
    d = apply(ctx, req("advance_time", travel_to="goblin_den"))
    assert d.code == "no_route"
    assert "forest" in d.message
    assert "hill" not in d.message


# М0 П2: род пути, закрытые транспортом рёбра, причина в no_route (решения 15, 33, 34, 35)
# Ожидаемый API (имена — предположение доебы, вопрос к папе): роды пути trail/offroad/water/mine
# (ключи config time.route_kinds); услуга перевозки — ServiceKind(effect="passage",
# transport="water"); цель сдвига — поле AdvanceTime.purpose: wait | work | travel (при category
# обязательно).

def ferry_cfg(cfg):
    from ai_dm.config.settings import ServiceKind

    ferry = cfg.model_copy(deep=True)
    ferry.services.kinds["ferry"] = ServiceKind(
        name="перевозка", price_cp=50, unit="once", effect="passage", transport="water"
    )
    return ferry


def island_ctx(registry, cfg, needs_transport=True, kind="water"):
    # Вейл -> Остров (4800 м), ребро записано у Вейла; Остров — сосед Леса не по суше
    ctx = make_ctx(registry, cfg)
    world = ctx.bundle.world
    world.locations["island"] = Location(id="island", name="Остров")
    world.locations["vale"].connections.append(
        Connection(to="island", distance_m=4800, kind=kind, needs_transport=needs_transport)
    )
    return ctx


def add_ferryman(ctx, name="Финн", services=("ferry",), location_id="vale"):
    from ai_dm.state.world import NPC

    ctx.bundle.world.npcs["finn"] = NPC(
        id="finn", name=name, named=True, means=["лодка"], services=list(services),
        location_id=location_id,
    )


def test_travel_trail_edge_takes_longer_than_road(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.locations["vale"].connections[0].kind = "trail"
    apply(ctx, req("advance_time", travel_to="forest"))
    assert ctx.bundle.world.clock.now_s == 5400


def test_travel_water_edge_without_transport_is_no_route_with_reason(registry, cfg):
    ctx = island_ctx(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, req("advance_time", travel_to="island"))
    assert isinstance(d, Invalid)
    assert d.code == "no_route"
    assert "только по воде" in d.message
    assert dump(ctx) == before


@pytest.mark.parametrize(("kind", "only", "need"), [
    ("water", "только по воде", "нужен водный транспорт"),
    ("air", "только по воздуху", "нужен воздушный транспорт"),
    ("mine", "только по шахте", "нужен шахтный транспорт"),
])
def test_travel_closed_edge_reason_names_the_transport(registry, cfg, kind, only, need):
    # М0 П2, решение 87: причины воздуха и шахты
    ctx = island_ctx(registry, cfg, kind=kind)
    d = apply(ctx, req("advance_time", travel_to="island"))
    assert d.code == "no_route"
    assert only in d.message
    assert need in d.message


def test_travel_no_route_with_reason_has_no_list_of_ids(registry, cfg):
    ctx = island_ctx(registry, cfg)
    d = apply(ctx, req("advance_time", travel_to="island"))
    assert "forest" not in d.message


def test_travel_trail_with_fast_pace_takes_4050_s(registry, cfg):
    ctx = island_ctx(registry, cfg, needs_transport=False, kind="trail")
    d = apply(ctx, req("advance_time", travel_to="island", pace="fast"))
    assert d.status == "accepted"
    assert ctx.bundle.world.clock.now_s == 4050


def test_travel_water_edge_no_route_names_ferrymen_here(registry, cfg):
    ferry = ferry_cfg(cfg)
    ctx = island_ctx(registry, ferry)
    add_ferryman(ctx)
    d = apply(ctx, req("advance_time", travel_to="island"))
    assert d.code == "no_route"
    assert "Финн" in d.message


def test_travel_water_edge_no_route_lists_ferrymen_comma_separated(registry, cfg):
    from ai_dm.state.world import NPC

    ctx = island_ctx(registry, ferry_cfg(cfg))
    add_ferryman(ctx)
    ctx.bundle.world.npcs["gus"] = NPC(
        id="gus", name="Гус", named=True, means=["лодка"], services=["ferry"], location_id="vale"
    )
    d = apply(ctx, req("advance_time", travel_to="island"))
    assert d.message.endswith("; перевозят: Финн, Гус")


def test_travel_water_edge_no_route_skips_ferryman_elsewhere(registry, cfg):
    ferry = ferry_cfg(cfg)
    ctx = island_ctx(registry, ferry)
    add_ferryman(ctx, location_id="forest")
    d = apply(ctx, req("advance_time", travel_to="island"))
    assert "Финн" not in d.message
    assert "только по воде" in d.message


def test_travel_water_edge_no_route_skips_npc_with_other_services(registry, cfg):
    ferry = ferry_cfg(cfg)
    ctx = island_ctx(registry, ferry)
    add_ferryman(ctx, services=("meal_modest",))
    d = apply(ctx, req("advance_time", travel_to="island"))
    assert "Финн" not in d.message


def test_travel_goes_by_land_when_water_edge_is_closed(registry, cfg):
    ctx = island_ctx(registry, cfg)
    world = ctx.bundle.world
    # 4800 + 2400 м по суше -- 5400 с, один вызов; закрытая вода (1800 с) всё равно короче
    world.locations["forest"].connections.append(Connection(to="island", distance_m=2400))
    d = apply(ctx, req("advance_time", travel_to="island"))
    assert d.status == "accepted"
    assert d.result["path"] == ["forest", "island"]


def test_travel_water_transport_opens_water_edge(registry, cfg):
    from ai_dm.state.hero import Transport

    ctx = island_ctx(registry, cfg)
    ctx.hero.transport = Transport(kind="water", name="ялик")
    d = apply(ctx, req("advance_time", travel_to="island"))
    assert d.status == "accepted"
    assert ctx.hero.location_id == "island"
    # 4800 м водой: 50 % от часа
    assert ctx.bundle.world.clock.now_s == 1800


def test_travel_mine_edge_without_needs_transport_is_open(registry, cfg):
    ctx = island_ctx(registry, cfg, needs_transport=False, kind="mine")
    d = apply(ctx, req("advance_time", travel_to="island"))
    assert d.status == "accepted"
    assert ctx.bundle.world.clock.now_s == 5400


def test_travel_steed_still_halves_the_walk_on_a_trail(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.locations["vale"].connections[0].kind = "trail"
    ctx.hero.creature.active_effects = [ActiveEffect(
        id="phantom_steed", source="h1", kind="travel_fast", params={},
        expires=Expiry(kind="seconds", value=3600),
    )]
    apply(ctx, req("advance_time", travel_to="forest"))
    assert ctx.bundle.world.clock.now_s == 2700


def test_advance_time_category_with_travel_purpose_is_rejected(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, req("advance_time", category="hour", purpose="travel"))
    assert isinstance(d, Decision)
    assert d.status == "rejected"
    assert ctx.bundle.world.clock.now_s == 0
    assert d.reason == "путь категорией времени"
    assert d.signal_to_master == (
        "Время не сдвинуто: путь не идёт категорией. Для пути между местами ставь "
        "travel_to; места нет на карте — сначала location_create."
    )
    assert dump(ctx) == before


@pytest.mark.parametrize("purpose", ["wait", "work"])
def test_advance_time_category_with_wait_or_work_purpose_passes(registry, cfg, purpose):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("advance_time", category="hour", purpose=purpose))
    assert d.status == "accepted"
    assert ctx.bundle.world.clock.now_s == 3600


def test_advance_time_category_without_purpose_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, req("advance_time", category="hour"))
    assert isinstance(d, Invalid)
    assert d.code == "purpose_required"
    assert d.message == "с category нужна цель purpose: wait (ждём) или work (герой занят делом)"
    assert dump(ctx) == before


# B6: damage -- спасброски вне боя при падении и при уроне уже лежащему герою

def weak_ctx(registry, cfg, rng, hp=10):
    return make_ctx(registry, cfg, rng, bundle=make_bundle(registry, hp=hp))


def lay_down(ctx):
    # герой уже без сознания на 0 HP, умирает (спасброски обнулены)
    ctx.hero.creature.hp_current = 0
    ctx.hero.creature.conditions.append(AppliedCondition(id="unconscious", source="0_hp"))


def event_types(ctx):
    return [e.type for e in ctx.events]


def test_damage_down_then_three_successes_makes_hero_stable(registry, cfg):
    rng = ScriptedRng(d10=[10], d20=[15, 15, 15], d4=[2])
    ctx = weak_ctx(registry, cfg, rng)
    now = ctx.bundle.world.clock.now_s
    d = apply(ctx, req("damage", severity="nuisance", damage_type="fire"))
    assert d.status == "accepted"
    assert hp_of(ctx) == 0
    assert ctx.hero.creature.death_saves.stable is True
    assert ctx.hero.status == "active"
    assert rng.left("d20") == 0
    assert rng.left("d4") == 0
    assert now + 3600 <= ctx.hero.creature.wake_at_s <= now + 4 * 3600
    assert "hero_status" in d.result
    assert "hero_died" not in event_types(ctx)


def test_damage_down_logs_every_death_save_line(registry, cfg):
    rng = ScriptedRng(d10=[10], d20=[15, 15, 15], d4=[2])
    ctx = weak_ctx(registry, cfg, rng)
    d = apply(ctx, req("damage", severity="nuisance", damage_type="fire"))
    # строка урона, «падает» и по строке на каждый из трёх спасбросков
    assert len(d.log) >= 5


def test_damage_down_then_natural_20_revives_with_1_hp(registry, cfg):
    rng = ScriptedRng(d10=[10], d20=[20])
    ctx = weak_ctx(registry, cfg, rng)
    d = apply(ctx, req("damage", severity="nuisance", damage_type="fire"))
    assert hp_of(ctx) == 1
    assert ctx.hero.status == "active"
    assert "hero_status" in d.result
    assert "hero_died" not in event_types(ctx)


def test_damage_down_then_three_failures_kills_hero(registry, cfg):
    rng = ScriptedRng(d10=[10], d20=[2, 2, 2])
    ctx = weak_ctx(registry, cfg, rng)
    d = apply(ctx, req("damage", severity="nuisance", damage_type="fire"))
    assert ctx.hero.status == "dead"
    assert d.result["hero_status"] == "dead"
    assert event_types(ctx).count("hero_died") == 1
    assert ctx.bundle.world.flags["hero_dead:hero"] is True


def test_damage_to_hero_already_down_triggers_out_of_combat_saves(registry, cfg):
    rng = ScriptedRng(d10=[3], d20=[15, 15, 15], d4=[2])
    ctx = weak_ctx(registry, cfg, rng)
    lay_down(ctx)
    now = ctx.bundle.world.clock.now_s
    d = apply(ctx, req("damage", severity="nuisance", damage_type="fire"))
    assert isinstance(d, Decision)
    assert rng.left("d20") == 0
    assert rng.left("d4") == 0
    assert ctx.hero.creature.death_saves.stable is True
    assert now + 3600 <= ctx.hero.creature.wake_at_s <= now + 4 * 3600
    assert ctx.hero.status == "active"
    assert "hero_status" in d.result


def test_damage_to_hero_already_down_can_kill_by_saves(registry, cfg):
    rng = ScriptedRng(d10=[3], d20=[2, 2, 2])
    ctx = weak_ctx(registry, cfg, rng)
    lay_down(ctx)
    d = apply(ctx, req("damage", severity="nuisance", damage_type="fire"))
    assert ctx.hero.status == "dead"
    assert d.result["hero_status"] == "dead"
    assert event_types(ctx).count("hero_died") == 1


def test_massive_damage_kills_instantly_without_saves(registry, cfg):
    rng = ScriptedRng(d10=[10, 10])
    ctx = weak_ctx(registry, cfg, rng)
    d = apply(ctx, req("damage", severity="dangerous", damage_type="fire"))
    assert ctx.hero.status == "dead"
    assert d.result["hero_status"] == "dead"
    assert rng.calls == ["d10", "d10"]
    assert event_types(ctx).count("hero_died") == 1
    assert ctx.bundle.world.flags["hero_dead:hero"] is True


def test_damage_to_dead_hero_is_invalid_hero_dead(registry, cfg):
    ctx = weak_ctx(registry, cfg, ScriptedRng(d10=[10, 10, 5]))
    apply(ctx, req("damage", severity="dangerous", damage_type="fire"))
    before = dump(ctx)
    d = apply(ctx, req("damage", severity="nuisance", damage_type="fire"))
    assert isinstance(d, Invalid)
    assert d.code == "hero_dead"
    assert dump(ctx) == before
    assert event_types(ctx).count("hero_died") == 1


def test_damage_to_dead_hero_does_not_roll_dice(registry, cfg):
    rng = ScriptedRng(d10=[10, 10])
    ctx = weak_ctx(registry, cfg, rng)
    apply(ctx, req("damage", severity="dangerous", damage_type="fire"))
    apply(ctx, req("damage", severity="nuisance", damage_type="fire"))
    assert rng.calls == ["d10", "d10"]


def test_damage_result_has_hero_status_when_hero_stays_up(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d10=[7]))
    d = apply(ctx, req("damage", severity="nuisance", damage_type="fire"))
    assert d.result["hero_status"] not in ("dead", "")


# D1: rest(short) -- костей хитов больше доступных урезаются

def test_short_rest_hit_dice_above_available_is_clamped(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d10=[5]))
    ctx.hero.creature.hp_current = 100
    d = apply(ctx, req("rest", kind="short", hit_dice=3))
    assert isinstance(d, Decision)
    assert d.status == "clamped"
    assert d.report_tag == "limit-exceeded"
    assert d.signal_to_master
    assert ctx.hero.creature.resources["hit_dice:d10"].current == 0
    assert hp_of(ctx) == 107
    assert ctx.marks == ["limit-exceeded"]
    assert ctx.bundle.world.clock.now_s == 3600


def test_short_rest_with_no_dice_left_is_clamped_to_zero(registry, cfg):
    rng = ScriptedRng()
    ctx = make_ctx(registry, cfg, rng)
    ctx.hero.creature.resources["hit_dice:d10"].current = 0
    ctx.hero.creature.hp_current = 100
    d = apply(ctx, req("rest", kind="short", hit_dice=2))
    assert d.status == "clamped"
    assert d.report_tag == "limit-exceeded"
    assert rng.calls == []
    assert hp_of(ctx) == 100


def test_short_rest_hit_dice_exactly_available_is_accepted(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d10=[5]))
    d = apply(ctx, req("rest", kind="short", hit_dice=1))
    assert d.status == "accepted"
    assert ctx.marks == []


# К0а: rest(short) считает кости по сумме пулов hit_dice:dN

def test_short_rest_limit_is_the_sum_of_hit_dice_pools(registry, cfg):
    from ai_dm.state.creature import ResourcePool

    ctx = make_ctx(registry, cfg, ScriptedRng(d10=[5], d8=[4]))
    ctx.hero.creature.resources["hit_dice:d8"] = ResourcePool(current=1, max=1)
    ctx.hero.creature.hp_current = 100
    d = apply(ctx, req("rest", kind="short", hit_dice=2))
    assert d.status == "accepted"
    assert ctx.hero.creature.resources["hit_dice:d10"].current == 0
    assert ctx.hero.creature.resources["hit_dice:d8"].current == 0


def test_short_rest_above_the_sum_of_pools_is_clamped(registry, cfg):
    from ai_dm.state.creature import ResourcePool

    ctx = make_ctx(registry, cfg, ScriptedRng(d10=[5], d8=[4]))
    ctx.hero.creature.resources["hit_dice:d8"] = ResourcePool(current=1, max=1)
    d = apply(ctx, req("rest", kind="short", hit_dice=3))
    assert d.status == "clamped"


# D2: roll_ref тратится -- повторное использование для deadly урезается

def test_deadly_damage_cannot_reuse_the_same_failed_roll(registry, cfg):
    rng = ScriptedRng(d20=[1], d10=[5, 5, 5, 5, 5, 5])
    ctx = make_ctx(registry, cfg, rng)
    ref = desperate_ref(ctx)
    first = apply(ctx, req("damage", severity="deadly", damage_type="fire", failed_roll_ref=ref))
    second = apply(ctx, req("damage", severity="deadly", damage_type="fire", failed_roll_ref=ref))
    assert first.status == "accepted"
    assert second.status == "clamped"
    assert second.report_tag == "limit-exceeded"
    assert second.signal_to_master
    assert rng.calls.count("d10") == 4 + 2
    assert hp_of(ctx) == 200 - 20 - 10


def test_two_failed_rolls_allow_two_deadly_hits(registry, cfg):
    rng = ScriptedRng(d20=[1, 1], d10=[1] * 8)
    ctx = make_ctx(registry, cfg, rng)
    first = apply(ctx, req(
        "damage", severity="deadly", damage_type="fire", failed_roll_ref=desperate_ref(ctx)
    ))
    second = apply(ctx, req(
        "damage", severity="deadly", damage_type="fire", failed_roll_ref=desperate_ref(ctx)
    ))
    assert first.status == "accepted"
    assert second.status == "accepted"


def test_clamped_deadly_does_not_spend_the_ref(registry, cfg):
    # урезанный (неверный) deadly без ref ничего не тратит: бросок ещё годится
    rng = ScriptedRng(d20=[1], d10=[1, 1, 1, 1, 1, 1])
    ctx = make_ctx(registry, cfg, rng)
    ref = desperate_ref(ctx)
    apply(ctx, req("damage", severity="deadly", damage_type="fire"))
    d = apply(ctx, req("damage", severity="deadly", damage_type="fire", failed_roll_ref=ref))
    assert d.status == "accepted"


# К0а: rest(short) без костей хитов ничего не тратит и не режет; результат несёт hp и время

def test_short_rest_without_hit_dice_spends_none(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("rest", kind="short"))
    assert d.status == "accepted"
    assert ctx.marks == []
    assert ctx.hero.creature.resources["hit_dice:d10"].current == 1


def test_rest_result_has_hp_and_time(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.hero.creature.hp_current = 100
    d = apply(ctx, req("rest", kind="short"))
    assert d.result["hp"] == 100
    assert d.result["now_s"] == 3600


def test_long_rest_log_says_so(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("rest", kind="long"))
    assert d.log[0] == "Длинный отдых: HP и ресурсы восстановлены"


# М0 П2б, решения 96, 98, 100, 102: перевозчик возвращается на свой берег, когда герой без него
# пришёл туда travel_to. Финн стоит на острове, его берег — vale, герой — в сухом соседе Вейла.

def home_ctx(registry, cfg):
    ctx = island_ctx(registry, ferry_cfg(cfg))
    add_ferryman(ctx, location_id="island")
    ctx.bundle.world.flags["ferry_home:finn"] = "vale"
    ctx.hero.location_id = "forest"
    return ctx


def go_vale(ctx):
    return apply(ctx, req("advance_time", travel_to="vale"))


def test_travel_to_home_shore_returns_the_ferryman(registry, cfg):
    ctx = home_ctx(registry, cfg)
    go_vale(ctx)
    assert ctx.bundle.world.npcs["finn"].location_id == "vale"
    assert "ferry_home:finn" not in ctx.bundle.world.flags


def test_travel_home_signals_the_master_about_the_return(registry, cfg):
    ctx = home_ctx(registry, cfg)
    assert go_vale(ctx).signal_to_master == "Финн вернулся на свой берег — «Вейл»"


def test_travel_home_adds_no_feed_line_about_the_ferryman(registry, cfg):
    ctx = home_ctx(registry, cfg)
    d = go_vale(ctx)
    assert len(d.log) == 1
    assert d.log[0].startswith("Путь в «Вейл»")
    assert "Финн" not in " ".join(d.log)


def test_after_return_no_route_names_the_ferryman_again(registry, cfg):
    ctx = home_ctx(registry, cfg)
    go_vale(ctx)
    d = apply(ctx, req("advance_time", travel_to="island"))
    assert d.code == "no_route"
    assert d.message.endswith("перевозят: Финн")


def test_travel_without_records_has_no_signal(registry, cfg):
    ctx = home_ctx(registry, cfg)
    del ctx.bundle.world.flags["ferry_home:finn"]
    assert go_vale(ctx).signal_to_master is None


def test_ferryman_stays_when_hero_walks_to_a_dry_neighbour_of_the_island(registry, cfg):
    ctx = home_ctx(registry, cfg)
    world = ctx.bundle.world
    world.locations["cove"] = Location(id="cove", name="Бухта")
    world.locations["island"].connections.append(Connection(to="cove", distance_m=1000))
    ctx.hero.location_id = "island"
    d = apply(ctx, req("advance_time", travel_to="cove"))
    assert d.status == "accepted"
    assert d.signal_to_master is None
    assert world.npcs["finn"].location_id == "island"
    assert world.flags["ferry_home:finn"] == "vale"


def test_ferryman_stays_when_home_shore_is_only_a_waypoint(registry, cfg):
    ctx = home_ctx(registry, cfg)
    world = ctx.bundle.world
    world.locations["farm"] = Location(id="farm", name="Ферма")
    world.locations["vale"].connections.append(Connection(to="farm", distance_m=2400))
    d = apply(ctx, req("advance_time", travel_to="farm"))
    assert d.result["path"] == ["vale", "farm"]
    assert d.signal_to_master is None
    assert world.npcs["finn"].location_id == "island"
    assert world.flags["ferry_home:finn"] == "vale"


def test_ferryman_stays_when_the_move_has_no_path(registry, cfg):
    ctx = home_ctx(registry, cfg)
    ctx.hero.location_id = "vale"
    d = apply(ctx, req("advance_time", travel_to="vale"))
    assert d.status == "rejected"
    assert ctx.bundle.world.npcs["finn"].location_id == "island"
    assert ctx.bundle.world.flags["ferry_home:finn"] == "vale"


def test_other_home_shore_is_not_read_on_arrival_at_vale(registry, cfg):
    ctx = home_ctx(registry, cfg)
    ctx.bundle.world.flags["ferry_home:finn"] = "forest"
    d = go_vale(ctx)
    assert d.signal_to_master is None
    assert ctx.bundle.world.npcs["finn"].location_id == "island"
    assert ctx.bundle.world.flags["ferry_home:finn"] == "forest"


@pytest.mark.parametrize("status", ["dead", "gone", "changed"])
def test_not_alive_ferryman_is_not_moved_and_record_is_dropped(registry, cfg, status):
    ctx = home_ctx(registry, cfg)
    ctx.bundle.world.npcs["finn"].status = status
    d = go_vale(ctx)
    assert d.status == "accepted"
    assert d.signal_to_master is None
    assert ctx.bundle.world.npcs["finn"].location_id == "island"
    assert "ferry_home:finn" not in ctx.bundle.world.flags


def test_removed_ferryman_record_is_dropped_without_error(registry, cfg):
    ctx = home_ctx(registry, cfg)
    del ctx.bundle.world.npcs["finn"]
    d = go_vale(ctx)
    assert d.status == "accepted"
    assert d.signal_to_master is None
    assert "ferry_home:finn" not in ctx.bundle.world.flags


def test_following_ferryman_arriving_with_the_hero_drops_the_record_silently(registry, cfg):
    ctx = home_ctx(registry, cfg)
    finn = ctx.bundle.world.npcs["finn"]
    finn.location_id = "forest"
    finn.follows = ctx.hero.id
    d = go_vale(ctx)
    assert finn.location_id == "vale"
    assert d.signal_to_master is None
    assert "ferry_home:finn" not in ctx.bundle.world.flags


def test_two_ferrymen_of_one_shore_both_return(registry, cfg):
    from ai_dm.state.world import NPC

    ctx = home_ctx(registry, cfg)
    world = ctx.bundle.world
    world.npcs["gus"] = NPC(
        id="gus", name="Гус", named=True, means=["лодка"], services=["ferry"],
        location_id="island",
    )
    world.flags["ferry_home:gus"] = "vale"
    d = go_vale(ctx)
    assert world.npcs["finn"].location_id == world.npcs["gus"].location_id == "vale"
    assert d.signal_to_master == (
        "Финн вернулся на свой берег — «Вейл»; Гус вернулся на свой берег — «Вейл»"
    )


def test_travel_failure_does_not_return_the_ferryman(registry, cfg):
    ctx = home_ctx(registry, cfg)
    d = apply(ctx, req("advance_time", travel_to="atlantis"))
    assert isinstance(d, Invalid)
    assert ctx.bundle.world.npcs["finn"].location_id == "island"
    assert ctx.bundle.world.flags["ferry_home:finn"] == "vale"


# М0 П3: «в пути» и временная локация «дорога» (решения 36–40, 50–53, 63–65).
# Ожидаемый API (по плану): путь дольше time.journey_from_s (7200 с) идёт отрезками до 2 ч за
# вызов travel_to; между узлами hero.location_id == hero.journey.road_id (Location с temporary=True
# и без связей), hero.journey = Journey(to, pace, start_id, road_id, from_id, edge_to, edge_done_s);
# по прибытии hero.journey = None, запись «дороги» убрана из world.locations.
# Темп normal: 4800 м -- 3600 с.

def long_ctx(registry, cfg):
    # Вейл -> Старая башня одним ребром 24000 м: 5 ч, три вызова (2 ч, 2 ч, 1 ч)
    ctx = make_ctx(registry, cfg)
    world = ctx.bundle.world
    world.locations["tower"] = Location(id="tower", name="Старая башня")
    world.locations["vale"].connections.append(Connection(to="tower", distance_m=24000))
    return ctx


def chain_ctx(registry, cfg):
    # Вейл -7200 м- Брод -4800- Ключ -7200- Чернолесье -12000- Старая башня: 5400+3600+5400+9000 с;
    # отрезки по 7200 с: между Бродом и Ключом, ровно в Чернолесье, дальше к башне, финиш
    ctx = make_ctx(registry, cfg)
    world = ctx.bundle.world
    for place_id, name in (
        ("ford", "Брод"), ("spring", "Ключ"), ("blackwood", "Чернолесье"), ("tower", "Старая башня")
    ):
        world.locations[place_id] = Location(id=place_id, name=name)
    world.locations["vale"].connections.append(Connection(to="ford", distance_m=7200))
    world.locations["ford"].connections.append(Connection(to="spring", distance_m=4800))
    world.locations["spring"].connections.append(Connection(to="blackwood", distance_m=7200))
    world.locations["blackwood"].connections.append(Connection(to="tower", distance_m=12000))
    return ctx


def go(ctx, to="tower", **fields):
    return apply(ctx, req("advance_time", travel_to=to, **fields))


def legs(ctx, count, to="tower"):
    for _ in range(count):
        go(ctx, to)


def in_road(ctx):
    # герой в «дороге»: id записи; проверка предусловия теста
    journey = ctx.hero.journey
    assert journey is not None
    assert journey.road_id
    assert ctx.hero.location_id == journey.road_id
    return journey.road_id


def temporary_places(ctx):
    return [p.id for p in ctx.bundle.world.locations.values() if p.temporary]


def test_long_travel_first_leg_takes_two_hours(registry, cfg):
    ctx = long_ctx(registry, cfg)
    d = go(ctx)
    assert d.status == "accepted"
    assert ctx.bundle.world.clock.now_s == 7200


def test_long_travel_first_leg_keeps_the_target_in_journey(registry, cfg):
    ctx = long_ctx(registry, cfg)
    go(ctx)
    assert ctx.hero.journey.to == "tower"


def test_long_travel_first_leg_puts_hero_in_the_road_record(registry, cfg):
    ctx = long_ctx(registry, cfg)
    go(ctx)
    road_id = in_road(ctx)
    assert road_id in ctx.bundle.world.locations


def test_long_travel_road_record_is_temporary(registry, cfg):
    ctx = long_ctx(registry, cfg)
    go(ctx)
    assert ctx.bundle.world.locations[in_road(ctx)].temporary is True


def test_long_travel_road_record_has_no_connections(registry, cfg):
    ctx = long_ctx(registry, cfg)
    go(ctx)
    assert ctx.bundle.world.locations[in_road(ctx)].connections == []


def test_long_travel_road_record_is_made_by_the_engine(registry, cfg):
    ctx = long_ctx(registry, cfg)
    go(ctx)
    assert ctx.bundle.world.locations[in_road(ctx)].origin == "engine"


def test_long_travel_journey_remembers_the_point_on_the_edge(registry, cfg):
    ctx = long_ctx(registry, cfg)
    go(ctx)
    journey = ctx.hero.journey
    assert (journey.start_id, journey.from_id, journey.edge_to, journey.edge_done_s) == (
        "vale", "vale", "tower", 7200
    )


def test_long_travel_first_leg_log_line(registry, cfg):
    ctx = long_ctx(registry, cfg)
    d = go(ctx)
    assert "В пути к «Старая башня»: прошло 2 ч, осталось 3 ч" in d.log


def test_long_travel_first_leg_takes_the_follower_into_the_road(registry, cfg):
    from ai_dm.state.world import NPC

    ctx = long_ctx(registry, cfg)
    ctx.bundle.world.npcs["bran"] = NPC(
        id="bran", name="Бран", named=True, means=["m"], location_id="vale", follows=ctx.hero.id
    )
    go(ctx)
    assert ctx.bundle.world.npcs["bran"].location_id == in_road(ctx)


def test_long_travel_second_leg_keeps_the_hero_in_the_same_road(registry, cfg):
    ctx = long_ctx(registry, cfg)
    go(ctx)
    road_id = in_road(ctx)
    go(ctx)
    assert in_road(ctx) == road_id
    assert ctx.bundle.world.clock.now_s == 14400


def test_long_travel_third_leg_arrives_and_drops_the_journey(registry, cfg):
    ctx = long_ctx(registry, cfg)
    legs(ctx, 3)
    assert ctx.hero.location_id == "tower"
    assert ctx.hero.journey is None


def test_long_travel_arrival_removes_the_road_record(registry, cfg):
    ctx = long_ctx(registry, cfg)
    go(ctx)
    road_id = in_road(ctx)
    legs(ctx, 2)
    assert road_id not in ctx.bundle.world.locations
    assert temporary_places(ctx) == []


def test_long_travel_in_three_legs_takes_the_time_of_one_call(registry, cfg):
    ctx = long_ctx(registry, cfg)
    go(ctx)
    in_road(ctx)
    legs(ctx, 2)
    assert ctx.bundle.world.clock.now_s == 18000


def test_travel_under_two_hours_goes_in_one_call(registry, cfg):
    # 9520 м -- 7140 с, 1 ч 59 мин
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.locations["tower"] = Location(id="tower", name="Старая башня")
    ctx.bundle.world.locations["vale"].connections.append(Connection(to="tower", distance_m=9520))
    go(ctx)
    assert ctx.hero.location_id == "tower"
    assert ctx.hero.journey is None
    assert ctx.bundle.world.clock.now_s == 7140


def test_travel_under_two_hours_creates_no_road_record(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.locations["tower"] = Location(id="tower", name="Старая башня")
    ctx.bundle.world.locations["vale"].connections.append(Connection(to="tower", distance_m=9520))
    go(ctx)
    assert temporary_places(ctx) == []


def test_leg_ending_exactly_in_a_node_leaves_the_hero_there_with_the_journey(registry, cfg):
    ctx = chain_ctx(registry, cfg)
    go(ctx)
    in_road(ctx)
    go(ctx)
    assert ctx.hero.location_id == "blackwood"
    assert ctx.hero.journey is not None
    assert ctx.bundle.world.clock.now_s == 14400


def test_road_record_made_earlier_survives_a_stop_in_a_node(registry, cfg):
    ctx = chain_ctx(registry, cfg)
    go(ctx)
    road_id = in_road(ctx)
    go(ctx)
    assert ctx.hero.journey.road_id == road_id
    assert road_id in ctx.bundle.world.locations


def test_trade_works_in_an_intermediate_node(registry, cfg):
    from ai_dm.state.world import NPC, TradeProfile

    ctx = chain_ctx(registry, cfg)
    ctx.bundle.world.npcs["mara"] = NPC(
        id="mara", name="Мара", means=["товары"], location_id="blackwood",
        trade=TradeProfile(kind="general", purse_cp=5000, restock_at_s=10**9, stock=[]),
    )
    go(ctx)
    in_road(ctx)
    go(ctx)
    d = apply(
        ctx, req("trade", npc_id="mara", direction="list", item_id="", qty=0, category="gear")
    )
    assert d.status == "accepted"


def test_next_stop_between_nodes_reuses_the_same_road_record(registry, cfg):
    ctx = chain_ctx(registry, cfg)
    go(ctx)
    road_id = in_road(ctx)
    go(ctx)
    go(ctx)
    assert in_road(ctx) == road_id
    assert temporary_places(ctx) == [road_id]


def test_chain_last_leg_arrives_and_removes_the_road(registry, cfg):
    ctx = chain_ctx(registry, cfg)
    legs(ctx, 4)
    assert ctx.hero.location_id == "tower"
    assert ctx.hero.journey is None
    assert temporary_places(ctx) == []
    assert ctx.bundle.world.clock.now_s == 23400


def test_second_journey_gets_its_own_road_record(registry, cfg):
    ctx = long_ctx(registry, cfg)
    go(ctx)
    first = in_road(ctx)
    legs(ctx, 2)
    go(ctx, "vale")
    assert in_road(ctx) != first


def test_first_road_id_is_nowhere_in_the_save_after_the_second_journey(registry, cfg):
    ctx = long_ctx(registry, cfg)
    go(ctx)
    first = in_road(ctx)
    legs(ctx, 2)
    go(ctx, "vale")
    in_road(ctx)
    legs(ctx, 2, "vale")
    assert dump(ctx).count(f'"{first}"') == 0


def test_trade_in_the_road_is_refused_as_npc_absent(registry, cfg):
    from ai_dm.state.world import NPC, TradeProfile

    ctx = long_ctx(registry, cfg)
    ctx.bundle.world.npcs["mara"] = NPC(
        id="mara", name="Мара", means=["товары"], location_id="vale",
        trade=TradeProfile(kind="general", purse_cp=5000, restock_at_s=10**9, stock=[]),
    )
    go(ctx)
    in_road(ctx)
    d = apply(
        ctx, req("trade", npc_id="mara", direction="list", item_id="", qty=0, category="gear")
    )
    assert isinstance(d, Invalid)
    assert d.code == "npc_absent"


def inn_in_vale(ctx):
    from ai_dm.state.world import NPC

    ctx.hero.money_cp = 100
    ctx.bundle.world.npcs["grok"] = NPC(
        id="grok", name="Грок", means=["трактир"], services=["room_modest"], location_id="vale"
    )


def test_service_in_the_road_is_refused_as_npc_absent(registry, cfg):
    ctx = long_ctx(registry, cfg)
    inn_in_vale(ctx)
    go(ctx)
    in_road(ctx)
    d = apply(
        ctx, req("service", npc_id="grok", direction="buy", service_id="room_modest", qty=1)
    )
    assert isinstance(d, Invalid)
    assert d.code == "npc_absent"


def test_long_rest_in_the_road_needs_no_paid_lodging(registry, cfg):
    ctx = long_ctx(registry, cfg)
    inn_in_vale(ctx)
    ctx.hero.creature.hp_current = 50
    go(ctx)
    in_road(ctx)
    d = apply(ctx, req("rest", kind="long"))
    assert d.status == "accepted"


def test_short_rest_in_the_road_is_accepted(registry, cfg):
    ctx = long_ctx(registry, cfg)
    ctx.hero.creature.hp_current = 50
    go(ctx)
    in_road(ctx)
    d = apply(ctx, req("rest", kind="short"))
    assert d.status == "accepted"


def test_npc_made_in_the_road_without_follows_has_no_location_after_arrival(registry, cfg):
    ctx = long_ctx(registry, cfg)
    go(ctx)
    in_road(ctx)
    apply(ctx, req("npc_create", id="brana", name="Бранка", means=["кузница"], named=True))
    legs(ctx, 2)
    npc = ctx.bundle.world.npcs["brana"]
    assert npc.location_id is None
    assert npc.status == "alive"


def test_npc_made_in_the_road_with_follows_arrives_with_the_hero(registry, cfg):
    ctx = long_ctx(registry, cfg)
    go(ctx)
    in_road(ctx)
    apply(ctx, req("npc_create", id="brana", name="Бранка", means=["кузница"], named=True))
    ctx.bundle.world.npcs["brana"].follows = ctx.hero.id
    legs(ctx, 2)
    assert ctx.bundle.world.npcs["brana"].location_id == "tower"


def test_danger_mark_on_the_road_is_removed_after_arrival(registry, cfg):
    from ai_dm.state.world import DangerMark

    ctx = long_ctx(registry, cfg)
    go(ctx)
    road_id = in_road(ctx)
    ctx.bundle.world.dangers.append(DangerMark(location_id=road_id, text="волки", at_s=0))
    legs(ctx, 2)
    assert ctx.bundle.world.dangers == []


def test_npc_death_record_on_the_road_loses_the_location_but_stays(registry, cfg):
    from ai_dm.state.death import DeathRecord
    from ai_dm.state.world import NPC

    ctx = long_ctx(registry, cfg)
    go(ctx)
    road_id = in_road(ctx)
    ctx.bundle.world.npcs["lost"] = NPC(
        id="lost", name="Путник", means=["посох"], status="dead",
        death=DeathRecord(cause="chance", at_s=100, location_id=road_id),
    )
    legs(ctx, 2)
    death = ctx.bundle.world.npcs["lost"].death
    assert death is not None
    assert death.location_id is None


def robbed_in_the_road(ctx, road_id):
    from ai_dm.state.world import CustomItem, ItemHolder

    ctx.bundle.world.custom_items["lost_ring"] = CustomItem(
        id="lost_ring", name="Кольцо", created_s=0,
        holder=ItemHolder(
            kind="location", ref=road_id, label="потеряно в пути", location_id=road_id,
            since_s=0, qty=2, cost_cp=30,
        ),
    )
    return ctx.bundle.world.custom_items["lost_ring"]


def test_things_lost_in_the_road_move_to_the_node_where_the_hero_got_off(registry, cfg):
    ctx = long_ctx(registry, cfg)
    go(ctx)
    item = robbed_in_the_road(ctx, in_road(ctx))
    legs(ctx, 2)
    assert (item.holder.kind, item.holder.ref, item.holder.location_id) == (
        "location", "tower", "tower"
    )


def test_things_lost_in_the_road_keep_quantity_and_cost(registry, cfg):
    ctx = long_ctx(registry, cfg)
    go(ctx)
    item = robbed_in_the_road(ctx, in_road(ctx))
    legs(ctx, 2)
    assert (item.holder.qty, item.holder.cost_cp, item.holder.label) == (2, 30, "потеряно в пути")


def test_road_id_is_nowhere_in_the_save_after_things_moved(registry, cfg):
    ctx = long_ctx(registry, cfg)
    go(ctx)
    road_id = in_road(ctx)
    robbed_in_the_road(ctx, road_id)
    legs(ctx, 2)
    assert dump(ctx).count(f'"{road_id}"') == 0


def test_turning_back_to_the_start_takes_the_time_already_walked(registry, cfg):
    ctx = chain_ctx(registry, cfg)
    go(ctx)
    in_road(ctx)
    go(ctx, "ford")
    assert ctx.bundle.world.clock.now_s == 7200 + 1800
    assert ctx.hero.location_id == "ford"
    assert ctx.hero.journey is None


def test_turning_to_the_far_end_of_the_edge_takes_the_rest_of_the_edge(registry, cfg):
    ctx = chain_ctx(registry, cfg)
    go(ctx)
    in_road(ctx)
    go(ctx, "spring")
    assert ctx.bundle.world.clock.now_s == 7200 + 1800
    assert ctx.hero.location_id == "spring"


def test_turning_to_a_third_place_takes_way_back_plus_its_path(registry, cfg):
    # назад к Броду 1800 с, от Брода до хутора 1200 м -- 900 с
    ctx = chain_ctx(registry, cfg)
    ctx.bundle.world.locations["spur"] = Location(id="spur", name="Хутор")
    ctx.bundle.world.locations["ford"].connections.append(Connection(to="spur", distance_m=1200))
    go(ctx)
    in_road(ctx)
    go(ctx, "spur")
    assert ctx.bundle.world.clock.now_s == 7200 + 1800 + 900
    assert ctx.hero.location_id == "spur"


def far_hamlet_after_first_leg(registry, cfg):
    # от Брода до Дальнего хутора 20000 м -- 15000 с: ещё один отрезок не доводит
    ctx = chain_ctx(registry, cfg)
    ctx.bundle.world.locations["far"] = Location(id="far", name="Дальний хутор")
    ctx.bundle.world.locations["ford"].connections.append(Connection(to="far", distance_m=20000))
    go(ctx)
    return ctx, in_road(ctx)


def test_new_target_in_the_road_keeps_the_record_and_changes_the_target(registry, cfg):
    ctx, road_id = far_hamlet_after_first_leg(registry, cfg)
    go(ctx, "far")
    assert in_road(ctx) == road_id
    assert ctx.hero.journey.to == "far"


def test_new_target_in_the_road_walks_back_then_forward_within_one_leg(registry, cfg):
    ctx, _ = far_hamlet_after_first_leg(registry, cfg)
    go(ctx, "far")
    journey = ctx.hero.journey
    assert (journey.from_id, journey.edge_to, journey.edge_done_s) == ("ford", "far", 5400)
    assert ctx.bundle.world.clock.now_s == 14400


def test_road_record_is_named_after_start_and_target(registry, cfg):
    ctx = long_ctx(registry, cfg)
    go(ctx)
    assert ctx.bundle.world.locations[in_road(ctx)].name == "Дорога: Вейл — Старая башня"


def test_road_record_is_renamed_to_the_new_target(registry, cfg):
    ctx, road_id = far_hamlet_after_first_leg(registry, cfg)
    assert ctx.bundle.world.locations[road_id].name == "Дорога: Вейл — Старая башня"
    go(ctx, "far")
    assert ctx.bundle.world.locations[road_id].name == "Дорога: Вейл — Дальний хутор"


def test_travel_to_the_road_record_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    world = ctx.bundle.world
    world.locations["road_x"] = Location(
        id="road_x", name="Дорога: Вейл — Лес", temporary=True, origin="engine"
    )
    world.locations["vale"].connections.append(Connection(to="road_x", distance_m=100))
    d = go(ctx, "road_x")
    assert isinstance(d, Invalid)
    assert d.code == "temporary_location"
    assert ctx.hero.location_id == "vale"


def test_travel_to_the_road_record_from_the_road_lists_both_ends_and_not_the_road(registry, cfg):
    ctx = long_ctx(registry, cfg)
    go(ctx)
    road_id = in_road(ctx)
    d = go(ctx, road_id)
    assert isinstance(d, Invalid)
    assert d.code == "temporary_location"
    assert "допустимые id: vale, tower" in d.message
    assert d.message.count(road_id) == 1


def test_turn_without_travel_to_keeps_the_journey(registry, cfg):
    ctx = long_ctx(registry, cfg)
    go(ctx)
    road_id = in_road(ctx)
    apply(ctx, req("advance_time", category="hour", purpose="wait"))
    assert in_road(ctx) == road_id


def test_journey_continues_from_the_same_place_after_save_and_load(registry, cfg):
    from ai_dm.state.save import SaveBundle

    ctx = chain_ctx(registry, cfg)
    go(ctx)
    road_id = in_road(ctx)
    loaded = SaveBundle.model_validate_json(ctx.bundle.model_dump_json())
    ctx2 = make_ctx(registry, cfg, bundle=loaded)
    go(ctx2)
    assert ctx2.hero.location_id == "blackwood"
    assert ctx2.hero.journey.road_id == road_id
    assert ctx2.bundle.world.clock.now_s == 14400


def test_same_seed_gives_the_same_road_id(registry, cfg):
    first = long_ctx(registry, cfg)
    second = long_ctx(registry, cfg)
    go(first)
    go(second)
    assert in_road(first) == in_road(second)


# М0 П3а, решения 108–111 (при Р43 (а), (б), (в) = (1)): «прошло» -- с начала пути, поле
# Journey.walked_s (схема v17): каждый отрезок прибавляет секунды, на которые сдвинуты часы;
# привал и ход без travel_to в сумму не входят, смена цели её не обнуляет.

def test_long_travel_first_leg_counts_two_hours_as_walked(registry, cfg):
    ctx = long_ctx(registry, cfg)
    go(ctx)
    assert ctx.hero.journey.walked_s == 7200


def test_long_travel_second_leg_log_line_counts_from_the_start(registry, cfg):
    ctx = long_ctx(registry, cfg)
    go(ctx)
    d = go(ctx)
    assert "В пути к «Старая башня»: прошло 4 ч, осталось 1 ч" in d.log
    assert ctx.hero.journey.walked_s == 14400


def test_long_travel_arrival_line_has_the_time_of_the_last_call(registry, cfg):
    ctx = long_ctx(registry, cfg)
    legs(ctx, 2)
    d = go(ctx)
    assert "Путь в «Старая башня»: 3600 с" in d.log
    assert ctx.hero.journey is None


def test_halt_between_legs_is_not_counted_as_walked(registry, cfg):
    ctx = long_ctx(registry, cfg)
    go(ctx)
    ctx.bundle.world.clock.advance(900)
    d = go(ctx)
    assert "В пути к «Старая башня»: прошло 4 ч, осталось 1 ч" in d.log
    assert ctx.hero.journey.walked_s == 14400


def test_turn_without_travel_to_does_not_change_walked_s(registry, cfg):
    ctx = long_ctx(registry, cfg)
    go(ctx)
    apply(ctx, req("advance_time", category="hour", purpose="wait"))
    assert ctx.hero.journey.walked_s == 7200


def test_new_target_in_the_road_continues_the_walked_count(registry, cfg):
    # от Брода до Дальнего хутора 15000 с, пройдено по ребру 5400 -- осталось 9600 с
    ctx, _ = far_hamlet_after_first_leg(registry, cfg)
    d = go(ctx, "far")
    assert "В пути к «Дальний хутор»: прошло 4 ч, осталось 2 ч 40 мин" in d.log
    assert ctx.hero.journey.walked_s == 14400


def test_steed_leg_adds_the_seconds_the_clock_moved_to_walked_s(registry, cfg):
    ctx = long_ctx(registry, cfg)
    ctx.hero.creature.active_effects = [ActiveEffect(
        id="phantom_steed", source="h1", kind="travel_fast", params={},
        expires=Expiry(kind="seconds", value=10**6),
    )]
    go(ctx)
    assert ctx.bundle.world.clock.now_s == 3600
    assert ctx.hero.journey.walked_s == ctx.bundle.world.clock.now_s


def test_walked_s_survives_save_and_load_and_the_next_line_continues_it(registry, cfg):
    from ai_dm.state.save import SaveBundle

    ctx = long_ctx(registry, cfg)
    go(ctx)
    loaded = SaveBundle.model_validate_json(ctx.bundle.model_dump_json())
    ctx2 = make_ctx(registry, cfg, bundle=loaded)
    assert ctx2.hero.journey.walked_s == 7200
    d = go(ctx2)
    assert "В пути к «Старая башня»: прошло 4 ч, осталось 1 ч" in d.log


# М0 П3а: порог и длина отрезка -- один ключ time.journey_from_s (по умолчанию 7200)

def journey_from(cfg, seconds):
    custom = cfg.model_copy(deep=True)
    custom.time.journey_from_s = seconds
    return custom


def test_journey_from_s_from_config_sets_the_leg_length(registry, cfg):
    ctx = long_ctx(registry, journey_from(cfg, 3600))
    go(ctx)
    assert ctx.bundle.world.clock.now_s == 3600
    in_road(ctx)


def test_path_exactly_at_the_threshold_goes_in_one_call(registry, cfg):
    # 9600 м -- ровно 7200 с
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.locations["tower"] = Location(id="tower", name="Старая башня")
    ctx.bundle.world.locations["vale"].connections.append(Connection(to="tower", distance_m=9600))
    go(ctx)
    assert ctx.hero.location_id == "tower"
    assert ctx.hero.journey is None


def test_path_one_second_over_the_threshold_goes_by_legs(registry, cfg):
    # 9601 м -- 7201 с: отрезок 7200 с, герой в «дороге»
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.locations["tower"] = Location(id="tower", name="Старая башня")
    ctx.bundle.world.locations["vale"].connections.append(Connection(to="tower", distance_m=9601))
    go(ctx)
    assert ctx.bundle.world.clock.now_s == 7200
    in_road(ctx)


# М0 П3а, умолчания п. 18: перевозчик возвращается, когда отрезок кончился ровно в его берегу

def finn_homeward(ctx):
    from ai_dm.state.world import NPC

    ctx.bundle.world.npcs["finn"] = NPC(
        id="finn", name="Финн", named=True, means=["лодка"], location_id="forest"
    )
    ctx.bundle.world.flags["ferry_home:finn"] = "blackwood"


def test_leg_ending_in_the_ferryman_home_node_brings_him_back(registry, cfg):
    ctx = chain_ctx(registry, cfg)
    finn_homeward(ctx)
    legs(ctx, 2)
    assert ctx.hero.location_id == "blackwood"
    assert ctx.bundle.world.npcs["finn"].location_id == "blackwood"
    assert "ferry_home:finn" not in ctx.bundle.world.flags


def test_leg_ending_in_the_road_leaves_the_ferryman_where_he_is(registry, cfg):
    ctx = chain_ctx(registry, cfg)
    finn_homeward(ctx)
    go(ctx)
    in_road(ctx)
    assert ctx.bundle.world.npcs["finn"].location_id == "forest"
    assert ctx.bundle.world.flags["ferry_home:finn"] == "blackwood"


# М0 П3а: подсказка «допустимые id» из «дороги» -- концы ребра первыми, id дороги нет

def test_unknown_location_from_the_road_lists_both_ends_first(registry, cfg):
    ctx = long_ctx(registry, cfg)
    go(ctx)
    road_id = in_road(ctx)
    d = go(ctx, "nowhere")
    assert d.code == "unknown_location"
    assert "допустимые id: vale, tower" in d.message
    assert road_id not in d.message


def test_no_route_from_the_road_names_both_ends(registry, cfg):
    ctx = long_ctx(registry, cfg)
    ctx.bundle.world.locations["lost"] = Location(id="lost", name="Потерянное")
    go(ctx)
    road_id = in_road(ctx)
    d = go(ctx, "lost")
    assert d.code == "no_route"
    assert "vale" in d.message
    assert "tower" in d.message
    assert road_id not in d.message


def test_no_route_from_the_road_behind_water_has_reason_and_no_ferrymen(registry, cfg):
    ctx = long_ctx(registry, ferry_cfg(cfg))
    world = ctx.bundle.world
    world.locations["isle"] = Location(id="isle", name="Остров")
    world.locations["vale"].connections.append(
        Connection(to="isle", distance_m=4800, kind="water", needs_transport=True)
    )
    add_ferryman(ctx, location_id="vale")
    go(ctx)
    in_road(ctx)
    d = go(ctx, "isle")
    assert d.code == "no_route"
    assert "только по воде — нужен водный транспорт" in d.message
    assert "перевозят" not in d.message


# М0 П3а, правка 3: занятый id «дороги» -- следующий свободный, локация мастера цела

def test_road_takes_another_id_when_the_first_one_is_taken_by_a_master_location(registry, cfg):
    ctx = long_ctx(registry, cfg)
    taken = Location(
        id="road_7200", name="Тракт", connections=[Connection(to="vale", distance_m=100)]
    )
    ctx.bundle.world.locations["road_7200"] = taken
    go(ctx)
    road_id = in_road(ctx)
    world = ctx.bundle.world
    assert road_id != "road_7200"
    assert world.locations[road_id].temporary is True
    assert world.locations["road_7200"] is taken
    assert (taken.name, taken.temporary, len(taken.connections)) == ("Тракт", False, 1)


# решение 113: после плена спутник в логове идёт с героем дальше

def test_companion_in_the_lair_goes_with_the_hero_on_the_next_travel(registry, cfg):
    from ai_dm.state.world import NPC

    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.npcs["lira"] = NPC(
        id="lira", name="Лира", means=["меч"], location_id="forest", follows=ctx.hero.id
    )
    ctx.hero.location_id = "forest"
    d = go(ctx, "vale")
    assert ctx.bundle.world.npcs["lira"].location_id == "vale"
    assert "С тобой: Лира" in d.log


# решение 114, правка 6: travel_to в узел, где герой стоит с незаконченным путём -- «остаюсь»

STAY_LINE = "Путь к «Старая башня» прерван: остаёшься в «Чернолесье»"


def staying_ctx(registry, cfg):
    # два отрезка по цепочке: герой ровно в «Чернолесье», путь к башне не окончен
    ctx = chain_ctx(registry, cfg)
    legs(ctx, 2)
    assert ctx.hero.location_id == "blackwood"
    assert ctx.hero.journey is not None
    return ctx


def test_stay_in_the_route_node_is_accepted_and_ends_the_journey(registry, cfg):
    ctx = staying_ctx(registry, cfg)
    d = go(ctx, "blackwood")
    assert isinstance(d, Decision)
    assert d.status == "accepted"
    assert ctx.hero.journey is None
    assert ctx.hero.location_id == "blackwood"


def test_stay_does_not_move_the_clock_and_result_is_the_stay_dict(registry, cfg):
    ctx = staying_ctx(registry, cfg)
    now_s = ctx.bundle.world.clock.now_s
    d = go(ctx, "blackwood")
    assert ctx.bundle.world.clock.now_s == now_s
    assert d.result == {
        "seconds": 0, "now_s": now_s, "location_id": "blackwood", "path": [], "stayed": True,
    }


def test_stay_log_is_one_line_with_the_target_and_the_node(registry, cfg):
    ctx = staying_ctx(registry, cfg)
    d = go(ctx, "blackwood")
    assert d.log == [STAY_LINE]


def test_stay_has_no_companions_line_events_or_signal(registry, cfg):
    from ai_dm.state.world import NPC

    ctx = staying_ctx(registry, cfg)
    ctx.bundle.world.npcs["lira"] = NPC(
        id="lira", name="Лира", means=["меч"], location_id="blackwood", follows=ctx.hero.id
    )
    events = len(ctx.events)
    d = go(ctx, "blackwood")
    assert not any(line.startswith("С тобой") for line in d.log)
    assert [e for e in ctx.events[events:] if e.type == "location_visited"] == []
    assert not d.signal_to_master


def test_stay_removes_the_road_record_and_its_id_from_the_save(registry, cfg):
    ctx = staying_ctx(registry, cfg)
    road_id = ctx.hero.journey.road_id
    assert road_id in ctx.bundle.world.locations
    go(ctx, "blackwood")
    assert road_id not in ctx.bundle.world.locations
    assert dump(ctx).count(f'"{road_id}"') == 0


def test_stay_moves_the_things_lost_on_the_road_to_the_node(registry, cfg):
    ctx = staying_ctx(registry, cfg)
    item = robbed_in_the_road(ctx, ctx.hero.journey.road_id)
    go(ctx, "blackwood")
    assert (item.holder.ref, item.holder.location_id) == ("blackwood", "blackwood")


def test_stay_without_a_road_record_ends_the_journey_and_keeps_locations(registry, cfg):
    from ai_dm.state.hero import Journey

    ctx = chain_ctx(registry, cfg)
    ctx.hero.location_id = "blackwood"
    ctx.hero.journey = Journey(to="tower", pace="normal", start_id="vale")
    before = set(ctx.bundle.world.locations)
    d = go(ctx, "blackwood")
    assert d.status == "accepted"
    assert ctx.hero.journey is None
    assert set(ctx.bundle.world.locations) == before


def test_new_path_after_a_stay_counts_from_zero_in_a_new_road(registry, cfg):
    ctx = staying_ctx(registry, cfg)
    old_road = ctx.hero.journey.road_id
    go(ctx, "blackwood")
    go(ctx)
    assert ctx.hero.journey.walked_s == 7200
    assert in_road(ctx) != old_road


# М0 П3а, мутанты: поля journey, направление на ребре, путь отрезка, темп, left_s, подсказка

def test_leg_ending_in_a_node_clears_the_edge_fields_of_the_journey(registry, cfg):
    ctx = staying_ctx(registry, cfg)
    journey = ctx.hero.journey
    assert (journey.from_id, journey.edge_to, journey.edge_done_s) == ("", "", 0)


def test_turning_back_on_a_long_edge_walks_back_along_it(registry, cfg):
    ctx = long_ctx(registry, cfg)
    legs(ctx, 2)
    road_id = in_road(ctx)
    go(ctx, "vale")
    journey = ctx.hero.journey
    assert in_road(ctx) == road_id
    assert (journey.from_id, journey.edge_to, journey.edge_done_s) == ("vale", "tower", 7200)


def test_leg_result_path_has_only_the_nodes_passed(registry, cfg):
    ctx = chain_ctx(registry, cfg)
    d = go(ctx)
    assert d.result["path"] == ["ford"]


def test_leg_result_has_the_time_left(registry, cfg):
    ctx = long_ctx(registry, cfg)
    d = go(ctx)
    assert d.result["left_s"] == 10800


def test_arrival_result_has_no_time_left(registry, cfg):
    ctx = long_ctx(registry, cfg)
    legs(ctx, 2)
    d = go(ctx)
    assert "left_s" not in d.result


def test_next_call_from_a_node_keeps_the_journey_pace(registry, cfg):
    # быстрый темп: 12800 м -- 7200 с (ровно в «mid»), 12000 м -- 6750 с; обычный -- 9000 с
    ctx = make_ctx(registry, cfg)
    world = ctx.bundle.world
    world.locations["mid"] = Location(id="mid", name="Середина")
    world.locations["tower"] = Location(id="tower", name="Старая башня")
    world.locations["vale"].connections.append(Connection(to="mid", distance_m=12800))
    world.locations["mid"].connections.append(Connection(to="tower", distance_m=12000))
    go(ctx, "tower", pace="fast")
    assert ctx.hero.location_id == "mid"
    go(ctx, "tower")
    assert ctx.hero.location_id == "tower"
    assert world.clock.now_s == 7200 + 6750


def test_unknown_location_from_the_road_lists_places_behind_both_ends(registry, cfg):
    ctx = long_ctx(registry, cfg)
    world = ctx.bundle.world
    world.locations["vspur"] = Location(id="vspur", name="В")
    world.locations["tspur"] = Location(id="tspur", name="Т")
    world.locations["vale"].connections.append(Connection(to="vspur", distance_m=100))
    world.locations["tower"].connections.append(Connection(to="tspur", distance_m=100))
    go(ctx)
    in_road(ctx)
    d = go(ctx, "nowhere")
    assert "допустимые id: vale, tower, forest, tspur, vspur" in d.message


def test_stay_repeated_is_the_old_already_here_rejection(registry, cfg):
    ctx = staying_ctx(registry, cfg)
    go(ctx, "blackwood")
    d = go(ctx, "blackwood")
    assert d.status == "rejected"
    assert d.reason == "герой уже в «Чернолесье»"
    assert "Герой уже в «Чернолесье»" in d.signal_to_master
