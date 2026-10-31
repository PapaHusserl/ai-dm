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
from ai_dm.state.creature import AppliedCondition
from ai_dm.state.world import Connection, Location


def failed_ref(ctx):
    # проваленный бросок этого хода (d20 = 1 у неумелого в убеждении)
    return apply(ctx, req("skill_check", skill="persuasion", category="hard")).result["roll_ref"]


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
    ref = failed_ref(ctx)
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
    ref = failed_ref(ctx)
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
    d = apply(ctx, req("advance_time", category=category))
    assert d.status == "accepted"
    assert ctx.bundle.world.clock.now_s == seconds
    assert d.log


def test_advance_time_month_uses_calendar_month_length(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.clock.calendar.months[0].days = 31
    apply(ctx, req("advance_time", category="month"))
    assert ctx.bundle.world.clock.now_s == 31 * DAY


def test_advance_time_does_not_move_hero_by_category(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, req("advance_time", category="hour"))
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


def test_travel_to_unknown_location_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("advance_time", travel_to="atlantis"))
    assert isinstance(d, Invalid)


def test_advance_time_needs_exactly_one_of_category_and_travel(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    both = apply(ctx, req("advance_time", category="hour", travel_to="forest"))
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
    rng = ScriptedRng(d10=[10], d20=[15, 15, 15])
    ctx = weak_ctx(registry, cfg, rng)
    d = apply(ctx, req("damage", severity="nuisance", damage_type="fire"))
    assert d.status == "accepted"
    assert hp_of(ctx) == 0
    assert ctx.hero.creature.death_saves.stable is True
    assert ctx.hero.status == "active"
    assert rng.left("d20") == 0
    assert "hero_status" in d.result
    assert "hero_died" not in event_types(ctx)


def test_damage_down_logs_every_death_save_line(registry, cfg):
    rng = ScriptedRng(d10=[10], d20=[15, 15, 15])
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
    rng = ScriptedRng(d10=[3], d20=[15, 15, 15])
    ctx = weak_ctx(registry, cfg, rng)
    lay_down(ctx)
    d = apply(ctx, req("damage", severity="nuisance", damage_type="fire"))
    assert isinstance(d, Decision)
    assert rng.left("d20") == 0
    assert ctx.hero.creature.death_saves.stable is True
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
    ref = failed_ref(ctx)
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
        "damage", severity="deadly", damage_type="fire", failed_roll_ref=failed_ref(ctx)
    ))
    second = apply(ctx, req(
        "damage", severity="deadly", damage_type="fire", failed_roll_ref=failed_ref(ctx)
    ))
    assert first.status == "accepted"
    assert second.status == "accepted"


def test_clamped_deadly_does_not_spend_the_ref(registry, cfg):
    # урезанный (неверный) deadly без ref ничего не тратит: бросок ещё годится
    rng = ScriptedRng(d20=[1], d10=[1, 1, 1, 1, 1, 1])
    ctx = make_ctx(registry, cfg, rng)
    ref = failed_ref(ctx)
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
