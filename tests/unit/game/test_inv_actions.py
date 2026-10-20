# Экипировка и зелья из /inv (шаг 96а, П1): ai_dm.game.inv_actions через GameApp.handle.
#   /inv надеть <предмет> [левая] · /inv снять <слот|предмет> · /inv выпить <предмет>; без
#   аргумента -- список предметов (как было). Предмет ищется по id или названию (целиком, иначе
#   по части).
#   Вне боя: надеть/снять двигают часы мира -- доспех по ARMOR_MINUTES (SRD), щит 1 мин, оружие 0;
#   мешающее (щит при двуручном, оружие в левой при щите) снимается само, строка «Снято: ...»;
#   отказ equip возвращает слоты назад и часы не двигает; после действия -- автосейв.
#   Строка для рассказчика (inv_notes) уходит префиксом к player_input СЛЕДУЮЩЕГО словесного хода
#   ровно раз; номер варианта боя заметки не забирает.
#   Зелья: лечебное -- в лимит consumables_per_scene (за лимитом отказ, предмет цел), эликсир с
#   эффектом -- вне лимита, продлевается при повторе; в бою -- подсказка про меню.
#   В бою: оружие -- свободное взаимодействие, потом действие; щит -- действие; доспех нельзя;
#   мешающее -- отказ «Сначала сними»; выбор играется как номер варианта (ход с рассказчиком).
from pathlib import Path

import pytest
from combat_kit import make_wizard
from game_kit import (
    ReactiveAdapter,
    combat_of,
    make_app,
    number_of,
    script_then_react,
    start_combat_call,
    state_of,
    text_step,
    tools_step,
)
from protocol_kit import make_bundle

from ai_dm.campaign.loader import load_pack, pack_content_dir
from ai_dm.content.loader import load_registry
from ai_dm.game.starter import new_world_from_pack
from ai_dm.persistence.store import load_slot
from ai_dm.rules.derived import armor_class
from ai_dm.rules.inventory import add_item, count_item
from ai_dm.state.creature import Concentration

DRAGON = Path(__file__).resolve().parents[3] / "campaigns" / "drunk_dragon"
PREFIX = "Перед этим герой сам: "


def flat(reply):
    return " ".join(line.strip() for line in reply.lines)


def fighter_app(registry, tmp_path, *items, adapter=None):
    # воин: кольчуга, щит, длинный меч надеты; копьё в рюкзаке; items -- ещё в инвентарь
    bundle = make_bundle(registry)
    for item in items:
        add_item(bundle.heroes[0], item, cost_cp=0)
    return make_app(registry, tmp_path, adapter or ReactiveAdapter(), bundle=bundle)


def hero_of_app(app):
    return app.bundle.heroes[0]


def clock_s(app):
    return app.bundle.world.clock.now_s


def fight_app(registry, tmp_path, *items):
    steps = [tools_step(start_combat_call(intent="kill")), text_step("Гоблины бросаются на вас.")]
    bundle = make_bundle(registry)
    for item in items:
        add_item(bundle.heroes[0], item, cost_cp=0)
    app = make_app(registry, tmp_path, script_then_react(steps), bundle=bundle)
    assert app.handle("Бью ногой дверь").turn.committed is True
    assert app.bundle.session.active_combat is not None
    return app


def hero_turn(app):
    state = combat_of(app.runner)
    return next(p for p in state.participants if p.ref == "hero").turn


# разбор подкоманд

def test_help_text_mentions_the_subcommands():
    from ai_dm.game.commands import HELP

    for word in ("надеть", "снять", "выпить"):
        assert word in HELP["inv"]


def test_unknown_verb_gives_usage_and_changes_nothing(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    before = app.bundle.model_dump_json()
    reply = app.handle("/inv танцевать копьё")
    assert "/inv надеть" in flat(reply)
    assert app.bundle.model_dump_json() == before


@pytest.mark.parametrize("verb", ["надеть", "снять", "выпить"])
def test_verb_without_an_item_gives_usage(registry, tmp_path, verb):
    app = fighter_app(registry, tmp_path)
    assert "/inv надеть" in flat(app.handle(f"/inv {verb}"))


def test_verb_is_case_insensitive(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    app.handle("/inv НАДЕТЬ копьё")
    assert hero_of_app(app).equipped.main_hand == "spear"


def test_inv_without_arguments_still_lists_items(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    assert "Копьё" in flat(app.handle("/inv"))


def test_subcommand_waits_while_a_menu_choice_is_pending(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    app.pending = "hero_dead"
    reply = app.handle("/inv надеть копьё")
    assert reply.lines == ["Сначала нужно сделать выбор в меню."]
    assert hero_of_app(app).equipped.main_hand == "longsword"


# поиск предмета

def test_item_is_found_by_id(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    app.handle("/inv надеть spear")
    assert hero_of_app(app).equipped.main_hand == "spear"


def test_item_is_found_by_part_of_the_name(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    app.handle("/inv надеть копь")
    assert hero_of_app(app).equipped.main_hand == "spear"


def test_unknown_item_is_refused_and_nothing_changes(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    before = app.bundle.model_dump_json()
    reply = app.handle("/inv надеть алебарда")
    assert "В инвентаре нет подходящего предмета: алебарда." in flat(reply)
    assert app.bundle.model_dump_json() == before
    assert app.inv_notes == []


def test_ambiguous_name_asks_to_clarify(registry, tmp_path):
    app = fighter_app(registry, tmp_path, "shortsword")
    reply = app.handle("/inv надеть меч")
    assert "Уточните, какой: Длинный меч, Короткий меч." in flat(reply)
    assert hero_of_app(app).equipped.main_hand == "longsword"


def test_potion_cannot_be_put_on(registry, tmp_path):
    app = fighter_app(registry, tmp_path, "potion_of_healing")
    assert "нет подходящего предмета" in flat(app.handle("/inv надеть зелье"))


def test_armor_cannot_be_drunk(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    assert "нет подходящего предмета" in flat(app.handle("/inv выпить кольчуга"))


def test_item_without_a_use_effect_cannot_be_drunk(registry, tmp_path):
    app = fighter_app(registry, tmp_path, "crowbar")
    assert "нет подходящего предмета" in flat(app.handle("/inv выпить crowbar"))


# надеть вне боя

def test_putting_a_weapon_in_hand_costs_no_time(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    start = clock_s(app)
    reply = app.handle("/inv надеть копьё")
    assert hero_of_app(app).equipped.main_hand == "spear"
    assert "В руке: Копьё." in flat(reply)
    assert "Прошло минут" not in flat(reply)
    assert clock_s(app) == start


def test_equipping_what_is_already_worn_is_refused(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    start = clock_s(app)
    reply = app.handle("/inv надеть длинный меч")
    assert "Уже надето: Длинный меч." in flat(reply)
    assert clock_s(app) == start
    assert app.inv_notes == []


def test_off_hand_dagger_removes_the_shield_by_itself(registry, tmp_path):
    app = fighter_app(registry, tmp_path, "dagger")
    start = clock_s(app)
    reply = app.handle("/inv надеть кинжал левая")
    equipped = hero_of_app(app).equipped
    assert equipped.shield is None
    assert equipped.off_hand == "dagger"
    assert equipped.main_hand == "longsword"
    text = flat(reply)
    assert "Снято: Щит." in text
    assert "В левой руке: Кинжал." in text
    assert clock_s(app) == start + 60


def test_off_hand_notes_name_both_actions(registry, tmp_path):
    app = fighter_app(registry, tmp_path, "dagger")
    app.handle("/inv надеть кинжал левая")
    assert app.inv_notes == ["снял «Щит»", "взял в левую руку «Кинжал»"]


def test_left_word_variants_are_understood(registry, tmp_path):
    app = fighter_app(registry, tmp_path, "dagger")
    app.handle("/inv надеть dagger off_hand")
    assert hero_of_app(app).equipped.off_hand == "dagger"


def test_left_hand_takes_only_weapons(registry, tmp_path):
    app = fighter_app(registry, tmp_path, "leather_armor")
    reply = app.handle("/inv надеть leather_armor левая")
    assert "В левую руку берут только оружие." in flat(reply)
    assert hero_of_app(app).equipped.armor == "chain_mail"


def test_two_handed_weapon_removes_the_shield_by_itself(registry, tmp_path):
    app = fighter_app(registry, tmp_path, "greatsword")
    start = clock_s(app)
    reply = app.handle("/inv надеть двуручный меч")
    equipped = hero_of_app(app).equipped
    assert equipped.main_hand == "greatsword"
    assert equipped.shield is None
    assert "Снято: Щит." in flat(reply)
    assert clock_s(app) == start + 60
    assert count_item(hero_of_app(app), "shield") == 1


def test_shield_removes_a_two_handed_weapon_by_itself(registry, tmp_path):
    bundle = make_bundle(registry)
    hero = bundle.heroes[0]
    add_item(hero, "greatsword", cost_cp=0)
    hero.equipped.shield = None
    hero.equipped.main_hand = "greatsword"
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    start = clock_s(app)
    reply = app.handle("/inv надеть щит")
    assert hero.equipped.shield == "shield"
    assert hero.equipped.main_hand is None
    assert "Снято: Двуручный меч." in flat(reply)
    assert clock_s(app) == start + 60


def test_refused_equip_restores_the_slots_it_cleared(registry, tmp_path):
    bundle = make_bundle(registry)
    hero = bundle.heroes[0]
    add_item(hero, "dagger", cost_cp=0)
    hero.equipped.main_hand = "dagger"
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    start = clock_s(app)
    reply = app.handle("/inv надеть кинжал левая")
    assert "один предмет нельзя взять в обе руки: Кинжал" in flat(reply)
    assert "dagger" not in flat(reply)
    assert hero.equipped.shield == "shield"
    assert hero.equipped.off_hand is None
    assert clock_s(app) == start
    assert app.inv_notes == []


def test_one_dagger_cannot_go_into_both_hands(registry, tmp_path):
    bundle = make_bundle(registry)
    hero = bundle.heroes[0]
    add_item(hero, "dagger", cost_cp=0)
    hero.equipped.shield = None
    hero.equipped.main_hand = "dagger"
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    app.handle("/inv надеть кинжал левая")
    assert hero.equipped.off_hand is None


def test_two_daggers_go_into_both_hands(registry, tmp_path):
    bundle = make_bundle(registry)
    hero = bundle.heroes[0]
    add_item(hero, "dagger", 2, cost_cp=0)
    hero.equipped.shield = None
    hero.equipped.main_hand = "dagger"
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    app.handle("/inv надеть кинжал левая")
    assert hero.equipped.off_hand == "dagger"


# часы: доспехи и щит (SRD 5.2)

def bare_armor_app(registry, tmp_path, *items):
    bundle = make_bundle(registry)
    hero = bundle.heroes[0]
    for item in items:
        add_item(hero, item, cost_cp=0)
    hero.equipped.armor = None
    return make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)


def test_putting_on_heavy_armor_takes_ten_minutes(registry, tmp_path):
    app = bare_armor_app(registry, tmp_path)
    start = clock_s(app)
    reply = app.handle("/inv надеть кольчуга")
    assert hero_of_app(app).equipped.armor == "chain_mail"
    assert clock_s(app) == start + 600
    assert "Надето: Кольчуга." in flat(reply)
    assert "Прошло минут: 10." in flat(reply)


def test_taking_off_heavy_armor_takes_five_minutes(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    start = clock_s(app)
    reply = app.handle("/inv снять доспех")
    assert hero_of_app(app).equipped.armor is None
    assert clock_s(app) == start + 300
    assert "Снято: Кольчуга." in flat(reply)
    assert "Прошло минут: 5." in flat(reply)


def test_putting_on_medium_armor_takes_five_minutes(registry, tmp_path):
    app = bare_armor_app(registry, tmp_path, "chain_shirt")
    start = clock_s(app)
    app.handle("/inv надеть chain_shirt")
    assert clock_s(app) == start + 300


def test_taking_off_medium_armor_takes_one_minute(registry, tmp_path):
    bundle = make_bundle(registry)
    add_item(bundle.heroes[0], "chain_shirt", cost_cp=0)
    bundle.heroes[0].equipped.armor = "chain_shirt"
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    start = clock_s(app)
    app.handle("/inv снять доспех")
    assert clock_s(app) == start + 60


def test_light_armor_takes_one_minute_each_way(registry, tmp_path):
    app = bare_armor_app(registry, tmp_path, "leather_armor")
    start = clock_s(app)
    app.handle("/inv надеть leather_armor")
    assert clock_s(app) == start + 60
    app.handle("/inv снять доспех")
    assert clock_s(app) == start + 120


def test_changing_armor_is_taking_off_plus_putting_on(registry, tmp_path):
    app = fighter_app(registry, tmp_path, "leather_armor")
    start = clock_s(app)
    reply = app.handle("/inv надеть leather_armor")
    assert hero_of_app(app).equipped.armor == "leather_armor"
    assert clock_s(app) == start + (5 + 1) * 60
    assert "Прошло минут: 6." in flat(reply)
    assert count_item(hero_of_app(app), "chain_mail") == 1


def test_shield_takes_one_minute_to_put_on_and_to_take_off(registry, tmp_path):
    bundle = make_bundle(registry)
    bundle.heroes[0].equipped.shield = None
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    start = clock_s(app)
    app.handle("/inv надеть щит")
    assert bundle.heroes[0].equipped.shield == "shield"
    assert clock_s(app) == start + 60
    app.handle("/inv снять щит")
    assert bundle.heroes[0].equipped.shield is None
    assert clock_s(app) == start + 120


def test_armor_without_training_is_refused_and_the_clock_stays(registry, tmp_path):
    bundle = make_bundle(registry)
    bundle.heroes = [make_wizard(registry, "hero")]
    add_item(bundle.heroes[0], "chain_mail", cost_cp=0)
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    start = clock_s(app)
    reply = app.handle("/inv надеть кольчуга")
    assert bundle.heroes[0].equipped.armor is None
    assert clock_s(app) == start
    assert "Прошло минут" not in flat(reply)
    assert app.inv_notes == []


def test_time_shift_ends_an_expired_concentration(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    hero_of_app(app).creature.concentration = Concentration(
        spell_id="bless", circle=1, until_s=clock_s(app) + 30
    )
    reply = app.handle("/inv снять доспех")
    assert hero_of_app(app).creature.concentration is None
    assert f"Концентрация: {registry.get('spell', 'bless').name} кончилась." in flat(reply)


def test_concentration_survives_an_action_without_time(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    hero_of_app(app).creature.concentration = Concentration(
        spell_id="bless", circle=1, until_s=clock_s(app) + 30
    )
    app.handle("/inv надеть копьё")
    assert hero_of_app(app).creature.concentration is not None


# снять вне боя

@pytest.mark.parametrize(
    ("word", "slot"),
    [("доспех", "armor"), ("броня", "armor"), ("щит", "shield"), ("правая", "main_hand"),
     ("оружие", "main_hand"), ("armor", "armor"), ("shield", "shield"), ("main_hand", "main_hand")],
)
def test_unequip_slot_words(registry, tmp_path, word, slot):
    app = fighter_app(registry, tmp_path)
    app.handle(f"/inv снять {word}")
    assert getattr(hero_of_app(app).equipped, slot) is None


def test_unequip_by_item_name(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    app.handle("/inv снять Кольчуга")
    assert hero_of_app(app).equipped.armor is None


def test_unequip_by_item_id(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    app.handle("/inv снять longsword")
    assert hero_of_app(app).equipped.main_hand is None


def test_unequip_left_hand_weapon(registry, tmp_path):
    bundle = make_bundle(registry)
    hero = bundle.heroes[0]
    add_item(hero, "dagger", cost_cp=0)
    hero.equipped.shield = None
    hero.equipped.off_hand = "dagger"
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    app.handle("/inv снять левая")
    assert hero.equipped.off_hand is None
    assert count_item(hero, "dagger") == 1


def test_unequip_name_in_two_slots_takes_off_the_right_hand_first(registry, tmp_path):
    bundle = make_bundle(registry)
    hero = bundle.heroes[0]
    add_item(hero, "dagger", 2, cost_cp=0)
    hero.equipped.shield = None
    hero.equipped.main_hand = "dagger"
    hero.equipped.off_hand = "dagger"
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    app.handle("/inv снять кинжал")
    assert hero.equipped.main_hand is None
    assert hero.equipped.off_hand == "dagger"


def test_refusal_text_replaces_the_id_with_the_name(registry):
    from ai_dm.game.inv_lookup import refusal_text
    from ai_dm.rules.inventory import InventoryError

    error = InventoryError("один предмет нельзя взять в обе руки: dagger")
    assert refusal_text(error, registry) == "один предмет нельзя взять в обе руки: Кинжал"


def test_refusal_text_keeps_an_unknown_id_as_is(registry):
    from ai_dm.game.inv_lookup import refusal_text
    from ai_dm.rules.inventory import InventoryError

    assert refusal_text(InventoryError("неизвестный предмет: zzz"), registry) == (
        "неизвестный предмет: zzz"
    )


def test_refusal_text_without_a_reason_is_unchanged(registry):
    from ai_dm.game.inv_lookup import refusal_text
    from ai_dm.rules.inventory import InventoryError

    assert refusal_text(InventoryError("dagger"), registry) == "dagger"


def hero_with_dagger_hands(registry):
    bundle = make_bundle(registry)
    hero = bundle.heroes[0]
    add_item(hero, "dagger", 2, cost_cp=0)
    hero.equipped.main_hand = "dagger"
    hero.equipped.off_hand = "dagger"
    return hero


@pytest.mark.parametrize(
    ("word", "slot"),
    [("доспех", "armor"), ("БРОНЯ", "armor"), ("щит", "shield"), ("правую", "main_hand"),
     ("оружие", "main_hand"), ("левая", "off_hand"), ("левую", "off_hand"),
     ("off_hand", "off_hand")],
)
def test_worn_slot_by_slot_word(registry, word, slot):
    from ai_dm.game.inv_lookup import worn_slot

    assert worn_slot(make_bundle(registry).heroes[0], registry, word) == slot


def test_worn_slot_slot_word_wins_even_if_slot_is_empty(registry):
    from ai_dm.game.inv_lookup import worn_slot

    hero = make_bundle(registry).heroes[0]
    assert hero.equipped.off_hand is None
    assert worn_slot(hero, registry, "левая") == "off_hand"


def test_worn_slot_by_name_or_id_of_worn_item(registry):
    from ai_dm.game.inv_lookup import worn_slot

    hero = make_bundle(registry).heroes[0]
    assert worn_slot(hero, registry, "Кольчуга") == "armor"
    assert worn_slot(hero, registry, "longsword") == "main_hand"


def test_worn_slot_prefers_the_first_slot_in_slot_order(registry):
    from ai_dm.game.inv_lookup import worn_slot

    assert worn_slot(hero_with_dagger_hands(registry), registry, "кинжал") == "main_hand"


def test_worn_slot_ignores_items_not_worn(registry):
    from ai_dm.game.inv_lookup import worn_slot

    assert worn_slot(make_bundle(registry).heroes[0], registry, "копьё") is None


def test_worn_slot_unknown_text_is_none(registry):
    from ai_dm.game.inv_lookup import worn_slot

    assert worn_slot(make_bundle(registry).heroes[0], registry, "шляпа") is None


def test_slot_words_live_in_inv_lookup_only():
    from ai_dm.game import inv_actions, inv_lookup

    assert inv_lookup.SLOT_WORDS["щит"] == "shield"
    assert not hasattr(inv_actions, "SLOT_WORDS")


def test_unequip_in_combat_armor_is_refused_without_a_turn(registry, tmp_path):
    from ai_dm.game.inv_actions import unequip_in_combat

    app = fight_app(registry, tmp_path)
    seq = app.bundle.session.turn_seq
    assert flat(unequip_in_combat(app, "armor")) == "В бою доспех не снять."
    assert app.bundle.session.turn_seq == seq


def test_unequip_in_combat_plays_the_variant_as_a_turn_step(registry, tmp_path):
    from ai_dm.game.inv_actions import unequip_in_combat

    app = fight_app(registry, tmp_path)
    seq = app.bundle.session.turn_seq
    unequip_in_combat(app, "shield")
    assert hero_of_app(app).equipped.shield is None
    assert app.bundle.session.turn_seq == seq + 1


def test_unequip_in_combat_without_resources_gives_the_hint(registry, tmp_path):
    from ai_dm.game.inv_actions import unequip_in_combat

    app = fight_app(registry, tmp_path)
    app.handle(f"{number_of(app.runner, 'dodge')}")
    assert "Сейчас не получится" in flat(unequip_in_combat(app, "shield"))


def test_unequip_unknown_target(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    reply = app.handle("/inv снять шляпа")
    assert "Не понял, что снять: шляпа." in flat(reply)


def test_unequip_empty_slot(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    start = clock_s(app)
    reply = app.handle("/inv снять левая")
    assert "Там ничего нет: оружие из левой руки." in flat(reply)
    assert clock_s(app) == start
    assert app.inv_notes == []


def test_unequip_weapon_costs_no_time(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    start = clock_s(app)
    reply = app.handle("/inv снять оружие")
    assert "Снято: Длинный меч." in flat(reply)
    assert clock_s(app) == start


def test_unequip_keeps_the_item_in_the_inventory(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    app.handle("/inv снять щит")
    assert count_item(hero_of_app(app), "shield") == 1


def test_unequip_note_for_the_narrator(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    app.handle("/inv снять щит")
    assert app.inv_notes == ["снял «Щит»"]


def test_equip_notes_for_the_narrator(registry, tmp_path):
    app = fighter_app(registry, tmp_path, "leather_armor")
    app.handle("/inv надеть leather_armor")
    assert app.inv_notes == ["надел «Кожаный доспех»"]


def test_equip_outside_combat_saves_the_autosave(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    app.handle("/inv надеть копьё")
    saved = load_slot(tmp_path, "w1", "auto")
    assert saved.heroes[0].equipped.main_hand == "spear"


def test_unequip_outside_combat_saves_the_autosave(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    app.handle("/inv снять щит")
    assert load_slot(tmp_path, "w1", "auto").heroes[0].equipped.shield is None


# заметки для рассказчика

def test_next_turn_input_carries_the_note_exactly_once(registry, tmp_path):
    adapter = ReactiveAdapter()
    app = fighter_app(registry, tmp_path, adapter=adapter)
    app.handle("/inv надеть копьё")
    app.handle("Иду дальше")
    first = state_of(adapter.requests[0])["player_input"]
    assert first == f"({PREFIX}взял в руку «Копьё».) Иду дальше"
    assert app.inv_notes == []
    app.handle("Ещё шаг")
    assert state_of(adapter.requests[-1])["player_input"] == "Ещё шаг"
    assert sum(PREFIX in state_of(r)["player_input"] for r in adapter.requests) == 1


def test_turn_record_keeps_the_prefixed_input(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    app.handle("/inv снять щит")
    app.handle("Иду дальше")
    record = app.bundle.memory.recent_turns[-1]
    assert record.player_input == f"({PREFIX}снял «Щит».) Иду дальше"


def test_several_actions_join_into_one_prefix(registry, tmp_path):
    adapter = ReactiveAdapter()
    app = fighter_app(registry, tmp_path, adapter=adapter)
    app.handle("/inv снять щит")
    app.handle("/inv надеть копьё")
    app.handle("Иду")
    assert state_of(adapter.requests[0])["player_input"] == (
        f"({PREFIX}снял «Щит»; взял в руку «Копьё».) Иду"
    )


def test_with_notes_without_notes_returns_the_line(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    assert app.with_notes("Иду", False) == "Иду"
    assert app.with_notes("3", True) == "3"


def test_with_notes_in_combat_keeps_notes_for_a_menu_number(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    app.inv_notes = ["снял «Щит»"]
    assert app.with_notes("3", True) == "3"
    assert app.inv_notes == ["снял «Щит»"]


def test_with_notes_in_combat_prefixes_a_word_turn(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    app.inv_notes = ["снял «Щит»"]
    assert app.with_notes("Бью гоблина", True) == f"({PREFIX}снял «Щит».) Бью гоблина"
    assert app.inv_notes == []


def test_with_notes_outside_combat_prefixes_even_a_number(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    app.inv_notes = ["снял «Щит»"]
    assert app.with_notes("2", False) == f"({PREFIX}снял «Щит».) 2"


def test_loading_a_save_drops_the_notes(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    app.handle("/save s1")
    app.handle("/inv снять щит")
    assert app.inv_notes
    app.handle("/load s1")
    assert app.inv_notes == []


# зелья вне боя

def potion_app(registry, tmp_path, qty=2, hp=1):
    app = fighter_app(registry, tmp_path, adapter=ReactiveAdapter())
    add_item(hero_of_app(app), "potion_of_healing", qty, cost_cp=0)
    hero_of_app(app).creature.hp_current = hp
    return app


def test_drinking_a_healing_potion_heals_and_spends_it(registry, tmp_path):
    app = potion_app(registry, tmp_path)
    reply = app.handle("/inv выпить зелье лечения")
    hero = hero_of_app(app)
    assert hero.creature.hp_current > 1
    assert count_item(hero, "potion_of_healing") == 1
    text = flat(reply)
    assert "Зелье лечения" in text
    assert f"{hero.creature.hp_current}/{hero.creature.hp_max}" in text


def test_drinking_counts_toward_the_scene_limit(registry, tmp_path):
    app = potion_app(registry, tmp_path)
    app.handle("/inv выпить зелье")
    assert app.bundle.session.current_scene.consumables_used == 1


def test_drinking_moves_the_rng_and_adds_a_note(registry, tmp_path):
    app = potion_app(registry, tmp_path)
    before = app.bundle.world.rng
    app.handle("/inv выпить зелье")
    assert app.bundle.world.rng != before
    assert app.inv_notes == ["выпил «Зелье лечения»"]


def test_drinking_costs_no_time(registry, tmp_path):
    app = potion_app(registry, tmp_path)
    start = clock_s(app)
    app.handle("/inv выпить зелье")
    assert clock_s(app) == start


def test_potion_at_the_scene_limit_is_refused(registry, tmp_path):
    app = potion_app(registry, tmp_path)
    limit = app.settings.rules.limits.consumables_per_scene
    scene = app.bundle.session.current_scene
    scene.consumables_used = limit
    reply = app.handle("/inv выпить зелье")
    assert f"Лимит расходников за сцену: {limit}." in flat(reply)
    assert count_item(hero_of_app(app), "potion_of_healing") == 2
    assert hero_of_app(app).creature.hp_current == 1
    assert scene.consumables_used == limit
    assert app.inv_notes == []


def test_potion_below_the_limit_is_drunk_and_hits_it(registry, tmp_path):
    app = potion_app(registry, tmp_path)
    limit = app.settings.rules.limits.consumables_per_scene
    scene = app.bundle.session.current_scene
    scene.consumables_used = limit - 1
    app.handle("/inv выпить зелье")
    assert count_item(hero_of_app(app), "potion_of_healing") == 1
    assert scene.consumables_used == limit
    reply = app.handle("/inv выпить зелье")
    assert "Лимит расходников" in flat(reply)


def test_without_a_scene_there_is_no_limit(registry, tmp_path):
    app = potion_app(registry, tmp_path)
    app.bundle.session.current_scene = None
    app.handle("/inv выпить зелье")
    assert hero_of_app(app).creature.hp_current > 1
    assert count_item(hero_of_app(app), "potion_of_healing") == 1


def test_drinking_saves_the_autosave(registry, tmp_path):
    app = potion_app(registry, tmp_path)
    app.handle("/inv выпить зелье")
    assert count_item(load_slot(tmp_path, "w1", "auto").heroes[0], "potion_of_healing") == 1


def test_potion_matches_the_use_item_handler(registry, cfg, tmp_path):
    # то же число HP, что у обработчика use_item при том же состоянии rng
    from protocol_kit import make_ctx, req

    from ai_dm.core.rng import Rng
    from ai_dm.protocol.apply import apply

    app = potion_app(registry, tmp_path, qty=1)
    twin = make_bundle(registry)
    add_item(twin.heroes[0], "potion_of_healing", 1, cost_cp=0)
    twin.heroes[0].creature.hp_current = 1
    twin.world.rng = app.bundle.world.rng
    ctx = make_ctx(registry, cfg, rng=Rng.from_state(twin.world.rng), bundle=twin)
    apply(ctx, req("use_item", item_id="potion_of_healing", qty=1))
    app.handle("/inv выпить зелье")
    assert hero_of_app(app).creature.hp_current == twin.heroes[0].creature.hp_current


# эликсиры (кампания drunk_dragon)

@pytest.fixture
def dragon_app(tmp_path):
    registry = load_registry([pack_content_dir(DRAGON)])
    from game_kit import settings

    bundle = new_world_from_pack(
        registry, settings().rules, load_pack(DRAGON, registry), hero="grey", seed=1,
        world_id="w1", saved_at="2026-01-01T00:00:00",
    )
    return make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)


def ac_of(app):
    return armor_class(hero_of_app(app), app.registry, clock_s(app))


def test_elixir_gives_its_effect_and_is_spent(dragon_app):
    app = dragon_app
    before = ac_of(app)
    stock = count_item(hero_of_app(app), "stoneskin_elixir")
    reply = app.handle("/inv выпить эликсир")
    assert ac_of(app) == before + 2
    assert count_item(hero_of_app(app), "stoneskin_elixir") == stock - 1
    assert "+2 КД" in flat(reply)
    assert " до " in flat(reply)
    assert app.inv_notes == ["выпил «Эликсир «Каменная Кожа»»"]


def test_elixir_is_outside_the_scene_limit(dragon_app):
    app = dragon_app
    scene = app.bundle.session.current_scene
    limit = app.settings.rules.limits.consumables_per_scene
    scene.consumables_used = limit
    app.handle("/inv выпить stoneskin")
    assert scene.consumables_used == limit
    assert count_item(hero_of_app(app), "stoneskin_elixir") == 1


def test_elixir_costs_no_time(dragon_app):
    start = clock_s(dragon_app)
    dragon_app.handle("/inv выпить эликсир")
    assert clock_s(dragon_app) == start


def test_second_elixir_extends_the_first(dragon_app):
    dragon_app.handle("/inv выпить эликсир")
    reply = dragon_app.handle("/inv выпить эликсир")
    assert "продлена" in flat(reply)
    assert ac_of(dragon_app) == 17


# бой

def test_potion_in_combat_points_to_the_menu(registry, tmp_path):
    app = fight_app(registry, tmp_path, "potion_of_healing")
    reply = app.handle("/inv выпить зелье")
    assert flat(reply) == "В бою зелья — через меню хода, пункт «Использовать»."
    assert count_item(hero_of_app(app), "potion_of_healing") == 1


def test_weapon_swap_in_combat_is_played_as_a_turn_step(registry, tmp_path):
    app = fight_app(registry, tmp_path)
    seq = app.bundle.session.turn_seq
    app.handle("/inv надеть копьё")
    assert hero_of_app(app).equipped.main_hand == "spear"
    assert app.bundle.session.turn_seq == seq + 1


def test_first_weapon_swap_in_combat_is_free(registry, tmp_path):
    app = fight_app(registry, tmp_path)
    app.handle("/inv надеть копьё")
    turn = hero_turn(app)
    assert turn.free_interaction is False
    assert turn.action is True


def test_second_weapon_swap_in_combat_costs_the_action(registry, tmp_path):
    app = fight_app(registry, tmp_path)
    app.handle("/inv надеть копьё")
    app.handle("/inv надеть длинный меч")
    assert hero_of_app(app).equipped.main_hand == "longsword"
    assert hero_turn(app).action is False


def test_shield_off_in_combat_costs_the_action_not_the_interaction(registry, tmp_path):
    app = fight_app(registry, tmp_path)
    app.handle("/inv снять щит")
    assert hero_of_app(app).equipped.shield is None
    turn = hero_turn(app)
    assert turn.action is False
    assert turn.free_interaction is True


def test_shield_on_in_combat_costs_the_action(registry, tmp_path):
    app = fight_app(registry, tmp_path)
    hero_of_app(app).equipped.shield = None
    app.handle("/inv надеть щит")
    assert hero_of_app(app).equipped.shield == "shield"
    assert hero_turn(app).action is False


def test_weapon_off_in_combat_is_free(registry, tmp_path):
    app = fight_app(registry, tmp_path)
    app.handle("/inv снять оружие")
    assert hero_of_app(app).equipped.main_hand is None
    assert hero_turn(app).free_interaction is False
    assert hero_turn(app).action is True


def test_combat_swap_does_not_move_the_clock_or_take_notes(registry, tmp_path):
    app = fight_app(registry, tmp_path)
    start = clock_s(app)
    app.handle("/inv надеть копьё")
    assert app.inv_notes == []
    assert app.bundle.session.active_combat is not None
    assert clock_s(app) == start


def test_armor_cannot_be_put_on_in_combat(registry, tmp_path):
    app = fight_app(registry, tmp_path, "leather_armor")
    seq = app.bundle.session.turn_seq
    reply = app.handle("/inv надеть leather_armor")
    assert "В бою доспех не сменить." in flat(reply)
    assert hero_of_app(app).equipped.armor == "chain_mail"
    assert app.bundle.session.turn_seq == seq


def test_armor_cannot_be_taken_off_in_combat(registry, tmp_path):
    app = fight_app(registry, tmp_path)
    seq = app.bundle.session.turn_seq
    reply = app.handle("/inv снять доспех")
    assert "В бою доспех не снять." in flat(reply)
    assert hero_of_app(app).equipped.armor == "chain_mail"
    assert app.bundle.session.turn_seq == seq


def test_blocking_slot_in_combat_is_not_removed_by_itself(registry, tmp_path):
    app = fight_app(registry, tmp_path, "greatsword")
    seq = app.bundle.session.turn_seq
    reply = app.handle("/inv надеть двуручный меч")
    assert "Сначала сними: Щит." in flat(reply)
    assert hero_of_app(app).equipped.shield == "shield"
    assert hero_of_app(app).equipped.main_hand == "longsword"
    assert app.bundle.session.turn_seq == seq


def exhaust_swaps(app):
    # свободное взаимодействие и действие потрачены двумя сменами оружия
    app.handle("/inv надеть копьё")
    app.handle("/inv надеть длинный меч")
    turn = hero_turn(app)
    assert (turn.free_interaction, turn.action) == (False, False)


def test_swap_without_action_and_interaction_is_refused(registry, tmp_path):
    app = fight_app(registry, tmp_path)
    exhaust_swaps(app)
    seq = app.bundle.session.turn_seq
    reply = app.handle("/inv надеть копьё")
    assert "Сейчас не получится" in flat(reply)
    assert hero_of_app(app).equipped.main_hand == "longsword"
    assert app.bundle.session.turn_seq == seq


def test_shield_off_without_action_is_refused(registry, tmp_path):
    app = fight_app(registry, tmp_path)
    app.handle(f"{number_of(app.runner, 'dodge')}")
    assert hero_turn(app).action is False
    seq = app.bundle.session.turn_seq
    reply = app.handle("/inv снять щит")
    assert "Сейчас не получится" in flat(reply)
    assert hero_of_app(app).equipped.shield == "shield"
    assert app.bundle.session.turn_seq == seq


def test_weapon_swap_without_action_still_uses_the_free_interaction(registry, tmp_path):
    app = fight_app(registry, tmp_path)
    app.handle(f"{number_of(app.runner, 'dodge')}")
    app.handle("/inv надеть копьё")
    assert hero_of_app(app).equipped.main_hand == "spear"


def test_swap_that_equip_itself_forbids_gives_its_reason(registry, tmp_path):
    app = fight_app(registry, tmp_path, "dagger")
    exhaust_swaps(app)
    hero = hero_of_app(app)
    hero.equipped.shield = None
    hero.equipped.main_hand = "dagger"
    reply = app.handle("/inv надеть кинжал левая")
    assert "один предмет нельзя взять в обе руки: Кинжал" in flat(reply)
    assert "Так не получится" not in flat(reply)
    assert hero.equipped.off_hand is None


# добивка мутантов шага 96а: точные тексты и разбор аргумента

def test_lone_left_word_is_an_item_name_not_a_hand_mark(registry, tmp_path):
    app = fighter_app(registry, tmp_path)
    reply = app.handle("/inv надеть левая")
    assert reply.lines == ["В инвентаре нет подходящего предмета: левая."]


def test_multiword_name_with_left_mark_goes_to_the_off_hand(registry, tmp_path):
    app = fighter_app(registry, tmp_path, "shortsword", "shortbow")
    app.handle("/inv надеть короткий меч левая")
    assert hero_of_app(app).equipped.off_hand == "shortsword"
    assert hero_of_app(app).equipped.main_hand == "longsword"


def test_left_hand_refusal_is_the_whole_reply(registry, tmp_path):
    app = fighter_app(registry, tmp_path, "leather_armor")
    reply = app.handle("/inv надеть leather_armor левая")
    assert reply.lines == ["В левую руку берут только оружие."]


def test_shield_put_on_outside_combat_is_worn_not_held(registry, tmp_path):
    bundle = make_bundle(registry)
    bundle.heroes[0].equipped.shield = None
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    reply = app.handle("/inv надеть щит")
    assert "Надето: Щит." in flat(reply)
    assert app.inv_notes == ["надел «Щит»"]


def test_several_blockers_add_up_their_minutes(registry, tmp_path):
    app = fighter_app(registry, tmp_path, "greatsword", "dagger")
    hero_of_app(app).equipped.off_hand = "dagger"
    start = clock_s(app)
    reply = app.handle("/inv надеть двуручный меч")
    assert "Снято: Щит." in flat(reply)
    assert "Снято: Кинжал." in flat(reply)
    assert clock_s(app) == start + 60


def test_armor_refusal_in_combat_is_the_whole_reply(registry, tmp_path):
    app = fight_app(registry, tmp_path, "leather_armor")
    reply = app.handle("/inv надеть leather_armor")
    assert reply.lines == ["В бою доспех не сменить."]


def test_several_blockers_in_combat_are_listed_with_commas(registry, tmp_path):
    app = fight_app(registry, tmp_path, "greatsword", "dagger")
    hero_of_app(app).equipped.off_hand = "dagger"
    reply = app.handle("/inv надеть двуручный меч")
    assert reply.lines == ["Сначала сними: Щит, Кинжал."]


def test_combat_equip_picks_the_asked_item_among_candidates(registry, tmp_path):
    app = fight_app(registry, tmp_path, "shortsword")
    app.handle("/inv надеть короткий меч")
    assert hero_of_app(app).equipped.main_hand == "shortsword"


def test_combat_equip_picks_the_asked_hand(registry, tmp_path):
    app = fight_app(registry, tmp_path, "dagger")
    hero_of_app(app).equipped.shield = None
    app.handle("/inv надеть кинжал левая")
    assert hero_of_app(app).equipped.off_hand == "dagger"
    assert hero_of_app(app).equipped.main_hand == "longsword"


HINT = "Сейчас не получится: в этом ходу не осталось ни действия, ни свободного взаимодействия."


def test_equip_hint_in_combat_is_the_whole_reply(registry, tmp_path):
    app = fight_app(registry, tmp_path)
    exhaust_swaps(app)
    assert app.handle("/inv надеть копьё").lines == [HINT]


def test_unequip_hint_in_combat_is_the_whole_reply(registry, tmp_path):
    app = fight_app(registry, tmp_path)
    exhaust_swaps(app)
    assert app.handle("/inv снять оружие").lines == [HINT]


def test_refusal_text_splits_on_the_last_separator(registry):
    from ai_dm.game.inv_lookup import refusal_text
    from ai_dm.rules.inventory import InventoryError

    error = InventoryError("причина: подробность: dagger")
    assert refusal_text(error, registry) == "причина: подробность: Кинжал"


def fake_lookup(monkeypatch):
    # два расходника: у первого короткое имя совпадает с названием второго
    from types import SimpleNamespace as NS

    from ai_dm.game import inv_lookup

    items = {
        "a": ("item", NS(name="Эликсир Камня", short_name="Скала")),
        "b": ("item", NS(name="Скала", short_name="")),
    }
    monkeypatch.setattr(inv_lookup, "find_item", lambda registry, item_id: items.get(item_id))
    hero = NS(inventory=[NS(item_id="a", qty=1), NS(item_id="b", qty=1)])
    return inv_lookup, hero


def test_find_entry_matches_the_short_name_exactly(monkeypatch):
    inv_lookup, hero = fake_lookup(monkeypatch)
    item_id, error = inv_lookup.find_entry(hero, None, "скала", lambda found: True)
    assert item_id is None
    assert error == "Уточните, какой: Эликсир Камня, Скала."


def test_find_entry_matches_the_short_name_partially(monkeypatch):
    inv_lookup, hero = fake_lookup(monkeypatch)
    item_id, error = inv_lookup.find_entry(hero, None, "скал", lambda found: True)
    assert item_id is None
    assert error == "Уточните, какой: Эликсир Камня, Скала."
