# Меню боя «сначала цель» (docs/plan-combat-menu.md, раздел 2 и 8; ответ В7: всё доступное
# оружие на виду, вытесняется в «Ещё…» последним). Чистые функции ai_dm.ui.combat_menu
# на голых ActionOption, без Textual.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "tui"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

from game_kit import script_then_react, start_combat_call, text_step, tools_step  # noqa: E402

from ai_dm.combat.available import ActionOption  # noqa: E402
from ai_dm.game import combat_flow  # noqa: E402
from ai_dm.ui.combat_menu import (  # noqa: E402
    BACK_LABEL,
    MAX_ROWS,
    MORE_LABEL,
    MenuRow,
    MenuState,
    TargetChip,
    build_view,
    clip,
    default_target,
    fit,
    header_of,
    number,
    short_label,
    target_of,
    targets,
)

NAMES = {"g1": "Гоблин 1", "g2": "Гоблин 2", "g3": "Гоблин 3", "g4": "Гоблин 4", "g5": "Гоблин 5"}


def roster(count=5, near=()):
    # враги g1..gN; g1.. в своей зоне (rank 0), refs из near -- в соседней (rank 1)
    return [
        TargetChip(ref, NAMES[ref], "7/7", 1 if ref in near else 0)
        for ref in list(NAMES)[:count]
    ]


def attack(weapon, ref, mode="ranged", name=None, ammo=None):
    name = name or weapon
    oid = f"attack:{weapon}:{ref}" + (f":ammo:{ammo}" if ammo else "")
    params = {"weapon": weapon, "target": ref, "mode": mode, "nonlethal": False}
    if ammo:
        params["ammo"] = ammo
    return ActionOption(id=oid, kind="attack", label=f"Атака: {name} → {NAMES[ref]}", params=params)


def stun(weapon, ref, name=None):
    name = name or weapon
    return ActionOption(
        id=f"attack:{weapon}:{ref}:nonlethal", kind="attack",
        label=f"Оглушающая атака: {name} → {NAMES[ref]}",
        params={"weapon": weapon, "target": ref, "mode": "melee", "nonlethal": True},
    )


def cast(spell, target, name=None):
    return ActionOption(
        id=f"cast:{spell}:1:{target}", kind="cast", label=f"{name or spell} → {target}",
        params={"spell": spell, "circle": 1, "target": target},
    )


def parley(ref, skill="persuasion", outcome="surrender"):
    return ActionOption(
        id=f"parley:{ref}:{skill}:{outcome}", kind="parley",
        label=f"Переговоры: {skill}, {outcome} → {NAMES[ref]} (СЛ 15)",
        params={"skill": skill, "outcome": outcome, "target": ref},
        )


def move(zone):
    return ActionOption(
        id=f"move:{zone}", kind="move", label=f"Идти: {zone}", params={"zone": zone}, cost="move"
    )


def plain(oid, kind=None, label=None, cost="action", **params):
    return ActionOption(id=oid, kind=kind or oid, label=label or oid, params=params, cost=cost)


def free_block_options(zones=("hall", "yard", "cellar")):
    return [
        plain("dash", label="Рывок"),
        plain("disengage", label="Отход"),
        plain("dodge", label="Уклонение"),
        plain("second_wind", label="Второе дыхание", cost="bonus"),
        *[move(z) for z in zones],
        plain("end_turn", label="Закончить ход", cost="free"),
    ]


def big_fight(enemies=5):
    # 5 врагов x 3 оружия (меч, лук, кинжал) + оглушающие + 4 заклинания на цель + переговоры
    # + 3 зоны
    options = []
    for ref in list(NAMES)[:enemies]:
        options += [attack("sword", ref, "melee", "меч"), stun("sword", ref, "меч")]
        options += [attack("bow", ref, "ranged", "лук")]
        options += [attack("dagger", ref, "melee", "кинжал"), stun("dagger", ref, "кинжал")]
        options += [cast(s, ref) for s in ("mark", "bolt", "fire", "hex")]
        options += [parley(ref, "persuasion"), parley(ref, "intimidation")]
    options.append(cast("heal", "hero", "Лечение"))
    return options + free_block_options()


def ids(rows):
    return [row.option_id for row in rows]


def labels(rows):
    return [row.label for row in rows]


# target_of

def test_target_of_attack_is_params_target():
    assert target_of(attack("sword", "g2", "melee")) == "g2"


def test_target_of_parley_is_params_target():
    assert target_of(parley("g3")) == "g3"


def test_target_of_cast_is_params_target():
    assert target_of(cast("mark", "g4")) == "g4"


def test_target_of_transfer_mark_is_params_target():
    option = plain("transfer_mark:g2", "transfer_mark", target="g2", cost="bonus")
    assert target_of(option) == "g2"


def test_target_of_disarm_is_params_target():
    assert target_of(plain("disarm:g1", "disarm", target="g1")) == "g1"


def test_target_of_help_is_enemy_not_ally():
    option = plain("help:ally:g5", "help", ally="ally", enemy="g5")
    assert target_of(option) == "g5"


def test_target_of_untargeted_options_is_none():
    assert target_of(plain("dodge")) is None
    assert target_of(move("hall")) is None
    assert target_of(plain("end_turn", cost="free")) is None


# targets

def test_targets_are_unique_targets_of_options():
    chips = targets(big_fight(3), roster(5))
    assert [chip.ref for chip in chips] == ["g1", "g2", "g3"]


def test_targets_own_zone_first_then_adjacent():
    chips = targets(big_fight(4), roster(4, near=("g1", "g2")))
    assert [chip.ref for chip in chips] == ["g3", "g4", "g1", "g2"]


def test_targets_without_enemy_options_is_empty():
    assert targets(free_block_options(), roster()) == []


def test_targets_ignore_zone_or_ally_cast_targets():
    options = [cast("heal", "hero"), cast("fog", "yard")] + free_block_options()
    assert targets(options, roster()) == []


def test_targets_keep_name_and_hp_text():
    chips = targets([attack("bow", "g2")], roster())
    assert (chips[0].name, chips[0].hp_text) == ("Гоблин 2", "7/7")


# default_target

def test_default_target_is_last_target_if_still_in_list():
    chips = targets(big_fight(4), roster(4))
    assert default_target(chips, "g3") == "g3"


def test_default_target_without_last_is_first():
    chips = targets(big_fight(4), roster(4))
    assert default_target(chips, None) == "g1"


def test_default_target_when_last_gone_is_first_in_own_zone():
    chips = targets(big_fight(4), roster(4, near=("g1", "g2")))
    assert default_target(chips, "g9") == "g3"


def test_default_target_when_own_zone_empty_is_adjacent():
    chips = targets(big_fight(2), roster(2, near=("g1", "g2")))
    assert default_target(chips, "gone") == "g1"


def test_default_target_without_chips_is_none():
    assert default_target([], "g1") is None


# short_label

def test_short_label_drops_target_name_when_it_is_the_selected_target():
    option = attack("bow", "g1", name="лук")
    assert short_label(option, "g1") == "Атака: лук"


def test_short_label_keeps_name_of_other_target():
    option = attack("bow", "g2", name="лук")
    assert short_label(option, "g1") == "Атака: лук → Гоблин 2"


def test_short_label_drops_remaining_attacks_suffix():
    option = attack("bow", "g1", name="лук")
    option.label += " (ещё 1 из 2)"
    assert short_label(option, "g1") == "Атака: лук"


def test_short_label_keeps_parenthesis_after_name():
    option = parley("g1")
    assert short_label(option, "g1").endswith("(СЛ 15)")
    assert "→" not in short_label(option, "g1")


def test_short_label_of_untargeted_option_is_label():
    assert short_label(plain("dodge", label="Уклонение"), "g1") == "Уклонение"


def test_header_contains_remaining_attacks():
    option = attack("bow", "g1", name="лук")
    option.label += " (ещё 1 из 2)"
    view = build_view([option, plain("end_turn", cost="free")], roster(1), "g1")
    assert "ещё 1 из 2" in view.header
    assert "ещё 1 из 2" not in labels(view.rows)[0]


def test_header_has_no_remaining_attacks_by_default():
    view = build_view(big_fight(2), roster(2), "g1")
    assert "из 2" not in view.header


# build_view: лимит

def test_big_fight_has_at_most_max_rows_and_more_is_last():
    view = build_view(big_fight(5), roster(5), "g1")
    assert len(view.rows) <= MAX_ROWS
    assert view.rows[-1].kind == "more"
    assert view.rows[-1].label == MORE_LABEL
    assert [row.kind for row in view.rows].count("more") == 1


def test_limit_holds_for_every_enemy_count():
    for count in range(1, 6):
        view = build_view(big_fight(count), roster(count), "g1")
        assert len(view.rows) <= MAX_ROWS


# скрытые варианты смены экипировки (шаг 96а): ни в строках, ни в «Ещё…»

def swap_options():
    return [
        plain("equip:spear", kind="equip", label="Взять в руку: Копьё", cost="free",
              item="spear", slot="main_hand"),
        plain("unequip:shield", kind="unequip", label="Снять щит: Щит", slot="shield"),
    ]


def test_build_view_rows_have_no_equipment_swap_options():
    options = big_fight(2) + swap_options()
    view = build_view(options, roster(2), "g1")
    assert not [i for i in ids(view.rows) if (i or "").startswith(("equip:", "unequip:"))]


def test_build_view_more_list_has_no_equipment_swap_options():
    view = build_view(big_fight(2) + swap_options(), roster(2), "g1")
    assert not [o for o in view.more if o.kind in ("equip", "unequip")]


def test_build_view_with_swap_options_equals_view_without_them():
    plain_view = build_view(big_fight(2), roster(2), "g1")
    view = build_view(big_fight(2) + swap_options(), roster(2), "g1")
    assert ids(view.rows) == ids(plain_view.rows)
    assert [o.id for o in view.more] == [o.id for o in plain_view.more]


def test_build_view_expanded_has_no_equipment_swap_options():
    view = build_view(big_fight(2) + swap_options(), roster(2), "g1", expanded="move")
    assert not [i for i in ids(view.rows) if (i or "").startswith(("equip:", "unequip:"))]


def test_rows_have_keys_1_to_9_then_0():
    view = build_view(big_fight(5), roster(5), "g1")
    keys = [row.key for row in view.rows]
    assert keys == (list("1234567890"))[:len(view.rows)]


def test_end_turn_is_kept_when_space_is_short():
    view = build_view(big_fight(5), roster(5), "g1")
    assert "end_turn" in ids(view.rows)


def test_weapons_are_pushed_out_last():
    # В7: оружие по цели на виду; при нехватке места сначала уезжают переговоры/заклинания
    view = build_view(big_fight(5), roster(5), "g1")
    shown = ids(view.rows)
    for weapon in ("sword", "bow", "dagger"):
        assert f"attack:{weapon}:g1" in shown


def test_all_weapons_for_target_are_visible_without_other_weapon_group():
    view = build_view(big_fight(5), roster(5), "g1")
    assert not any(row.kind == "expand" and "оруж" in row.label.lower() for row in view.rows)


def test_parley_is_pushed_out_before_weapons():
    view = build_view(big_fight(5), roster(5), "g1")
    shown = ids(view.rows)
    parleys = [i for i in shown if i and i.startswith("parley:")]
    weapons = [i for i in shown if i and i.startswith("attack:")]
    assert len(weapons) == 3
    assert len(parleys) < 2


def test_parley_of_target_is_in_target_block_when_there_is_room():
    options = [attack("bow", "g1"), parley("g1"), parley("g2")] + free_block_options(("hall",))
    view = build_view(options, roster(2), "g1")
    assert ids(view.target_rows) == ["attack:bow:g1", "parley:g1:persuasion:surrender"]


def test_disarm_of_target_is_in_target_block():
    options = [attack("bow", "g1"), plain("disarm:g1", "disarm", target="g1")]
    view = build_view(options + free_block_options(("hall",)), roster(1), "g1")
    assert "disarm:g1" in ids(view.target_rows)


# build_view: блок цели только по выбранной цели

def test_target_block_has_only_selected_target_variants():
    view = build_view(big_fight(3), roster(3), "g2")
    assert not any(":g1" in (i or "") or ":g3" in (i or "") for i in ids(view.target_rows))
    assert "attack:sword:g2" in ids(view.target_rows)


def test_target_block_includes_unarmed_improvised_and_special_ammo_only_for_target():
    options = [
        attack("sword", "g1", "melee"), attack("unarmed", "g1", "melee"),
        attack("improvised_melee", "g1", "melee"),
        attack("bow", "g1"), attack("bow", "g1", ammo="fire"),
        attack("sword", "g2", "melee"), attack("unarmed", "g2", "melee"),
        attack("bow", "g2"), attack("bow", "g2", ammo="fire"),
    ] + free_block_options(("hall",))
    view = build_view(options, roster(2), "g1")
    assert ids(view.target_rows) == [
        "attack:sword:g1", "attack:unarmed:g1", "attack:improvised_melee:g1",
        "attack:bow:g1", "attack:bow:g1:ammo:fire",
    ]


def test_target_rows_do_not_repeat_target_name():
    options = [attack("bow", "g1", name="лук")] + free_block_options(("hall",))
    view = build_view(options, roster(1), "g1")
    assert labels(view.target_rows) == ["Атака: лук"]


def test_switching_target_switches_target_rows():
    options = big_fight(2)
    first = build_view(options, roster(2), "g1")
    second = build_view(options, roster(2), "g2")
    assert ids(first.target_rows) != ids(second.target_rows)
    assert all(i.endswith(":g2") for i in ids(second.target_rows) if i)


def test_free_block_is_same_for_every_target():
    options = big_fight(2)
    first = build_view(options, roster(2), "g1")
    second = build_view(options, roster(2), "g2")
    assert ids(first.free_rows) == ids(second.free_rows)


# nonlethal

def test_nonlethal_melee_row_points_to_nonlethal_id():
    options = [attack("sword", "g1", "melee", "меч"), stun("sword", "g1", "меч")]
    view = build_view(options + free_block_options(("hall",)), roster(1), "g1", nonlethal=True)
    assert ids(view.target_rows) == ["attack:sword:g1:nonlethal"]


def test_nonlethal_off_melee_row_points_to_ordinary_id():
    options = [attack("sword", "g1", "melee", "меч"), stun("sword", "g1", "меч")]
    view = build_view(options + free_block_options(("hall",)), roster(1), "g1", nonlethal=False)
    assert ids(view.target_rows) == ["attack:sword:g1"]


def test_nonlethal_ranged_row_keeps_ordinary_id_with_note():
    options = [attack("bow", "g1", "ranged", "лук")]
    view = build_view(options + free_block_options(("hall",)), roster(1), "g1", nonlethal=True)
    assert ids(view.target_rows) == ["attack:bow:g1"]
    assert "дальнобойным — не оглушить" in view.target_rows[0].label


def test_ordinary_ranged_row_has_no_note_without_nonlethal():
    options = [attack("bow", "g1", "ranged", "лук")]
    view = build_view(options + free_block_options(("hall",)), roster(1), "g1")
    assert "оглуш" not in view.target_rows[0].label


def test_nonlethal_does_not_duplicate_rows():
    options = [attack("sword", "g1", "melee"), stun("sword", "g1"), attack("bow", "g1")]
    view = build_view(options + free_block_options(("hall",)), roster(1), "g1", nonlethal=True)
    assert len(view.target_rows) == 2


# особые стрелы: «Стрелы ▸» под строкой своего лука

def two_bows(*arrows):
    options = [attack("bow", "g1", "ranged", "лук"), attack("sword", "g1", "melee", "меч")]
    options += [attack("bow", "g1", "ranged", "лук", ammo=a) for a in arrows]
    options += [attack("bow", "g2", "ranged", "лук", ammo=a) for a in arrows]
    for option in options:
        if option.params.get("ammo"):
            option.label = option.label.replace(
                "лук", f"лук — {option.params['ammo']} (осталось 9)", 1
            )
    return options + free_block_options(("hall",))


def test_two_arrow_kinds_collapse_into_group_row_after_own_bow():
    view = build_view(two_bows("sleep", "fire"), roster(2), "g1")
    assert labels(view.target_rows) == ["Атака: лук", "Стрелы ▸", "Атака: меч"]
    group = view.target_rows[1]
    assert (group.kind, group.group, group.rank) == ("expand", "ammo:bow", 0)


def test_group_row_has_no_nonlethal_note_with_nonlethal_on():
    view = build_view(two_bows("sleep", "fire"), roster(2), "g1", True)
    assert view.target_rows[1].label == "Стрелы ▸"


def test_one_arrow_kind_stays_a_row_after_own_bow():
    view = build_view(two_bows("sleep"), roster(2), "g1")
    assert ids(view.target_rows) == ["attack:bow:g1", "attack:bow:g1:ammo:sleep", "attack:sword:g1"]


def test_ammo_group_lists_short_labels_for_chosen_target_only():
    view = build_view(two_bows("sleep", "fire"), roster(2), "g1", expanded="ammo:bow")
    assert labels(view.rows[:3]) == [BACK_LABEL, "Sleep (осталось 9)", "Fire (осталось 9)"]
    assert len(view.rows) == 3
    assert ids(view.rows[:3]) == [None, "attack:bow:g1:ammo:sleep", "attack:bow:g1:ammo:fire"]


def test_ammo_group_rows_keep_nonlethal_note():
    view = build_view(two_bows("sleep", "fire"), roster(2), "g1", True, "ammo:bow")
    assert "дальнобойным — не оглушить" in view.rows[1].label
    plain_view = build_view(two_bows("sleep", "fire"), roster(2), "g1", False, "ammo:bow")
    assert "оглуш" not in plain_view.rows[1].label


def bows_fight(bows, arrows, enemies=1, melee=()):
    options = []
    for ref in list(NAMES)[:enemies]:
        options += [attack(w, ref, "melee", w) for w in melee]
        for bow in bows:
            options.append(attack(bow, ref, "ranged", bow))
            options += [
                attack(bow, ref, "ranged", f"{bow} — {a} (осталось 9)", ammo=a) for a in arrows
            ]
    return options + free_block_options(("hall",))


def test_group_view_has_no_ammo_ids_in_target_rows_but_more_lists_them():
    view = build_view(two_bows("sleep", "fire"), roster(2), "g1")
    assert not any(":ammo:" in (i or "") for i in ids(view.target_rows))
    assert {"attack:bow:g1:ammo:sleep", "attack:bow:g1:ammo:fire"} <= {o.id for o in view.more}


def test_two_bows_each_get_group_right_after_own_row():
    view = build_view(bows_fight(["bow1", "bow2"], ["a", "b", "c"]), roster(1), "g1")
    rows = view.target_rows
    assert labels(rows) == ["Атака: bow1", "Стрелы ▸", "Атака: bow2", "Стрелы ▸"]
    assert [r.group for r in rows] == [None, "ammo:bow1", None, "ammo:bow2"]


def test_bow_without_special_arrows_has_no_group_row():
    view = build_view(bows_fight(["bow"], []), roster(1), "g1")
    assert labels(view.target_rows) == ["Атака: bow"]


def test_ammo_group_is_limited_to_chosen_bow():
    options = bows_fight(["bow1", "bow2"], ["a", "b"])
    view = build_view(options, roster(1), "g1", expanded="ammo:bow2")
    assert ids(view.rows[1:3]) == ["attack:bow2:g1:ammo:a", "attack:bow2:g1:ammo:b"]
    assert len(view.rows) == 3


def test_state_set_target_collapses_ammo_group():
    state = state_with()
    state.expanded = "ammo:bow"
    state.set_target("g2")
    assert state.expanded is None


def test_long_ammo_group_keeps_limit_and_ends_with_more_row():
    arrows = [f"a{i}" for i in range(12)]
    view = build_view(bows_fight(["bow"], arrows), roster(1), "g1", expanded="ammo:bow")
    assert len(view.rows) == MAX_ROWS
    assert view.rows[0].kind == "back"
    assert view.rows[-1].kind == "more"
    assert {f"attack:bow:g1:ammo:a{i}" for i in range(12)} <= {o.id for o in view.more}


def test_two_bows_six_arrows_five_targets_fit_limit():
    options = bows_fight(["bow1", "bow2"], [f"a{i}" for i in range(6)], 5, ("sword",))
    view = build_view(options, roster(5), "g1")
    assert len(view.rows) <= MAX_ROWS
    assert view.rows[-1].kind == "more"


def test_nine_weapons_and_two_bows_keep_groups_visible():
    arrows = [f"a{i}" for i in range(6)]
    tail = len(free_block_options(("hall",)))

    def part(bows, melee):
        return bows_fight(bows, arrows, 1, melee)[:-tail]

    # порядок как в замере t446: лук, три клинка, второй лук, остальные клинки
    options = (
        part(["bow1"], ()) + part([], ("w0", "w1", "w2")) + part(["bow2"], ())
        + part([], ("w3", "w4", "w5", "w6")) + free_block_options(("hall",))
    )
    view = build_view(options, roster(1), "g1")
    shown = labels(view.rows)
    assert len(view.rows) <= MAX_ROWS
    assert shown.count("Стрелы ▸") == 2
    assert shown[shown.index("Атака: bow1") + 1] == "Стрелы ▸"
    assert shown[-1] == MORE_LABEL


# заклинания, зоны, неизвестное, пустые случаи

def test_two_target_spells_are_rows_three_are_group():
    two = [cast("mark", "g1"), cast("bolt", "g1")]
    three = two + [cast("fire", "g1")]
    view2 = build_view(two + free_block_options(("hall",)), roster(1), "g1")
    view3 = build_view(three + free_block_options(("hall",)), roster(1), "g1")
    assert ids(view2.target_rows) == ["cast:mark:1:g1", "cast:bolt:1:g1"]
    assert [row.kind for row in view3.target_rows] == ["expand"]
    assert view3.target_rows[0].group == "spells_target"


def test_heal_ally_and_zone_spells_are_not_in_target_block():
    options = [attack("bow", "g1"), cast("heal", "hero"), cast("fog", "yard")]
    view = build_view(options + free_block_options(("hall",)), roster(1), "g1")
    assert ids(view.target_rows) == ["attack:bow:g1"]
    assert any(row.kind == "expand" and row.group == "spells_free" for row in view.free_rows)


def test_spells_free_group_lists_ally_and_zone_spells():
    options = [attack("bow", "g1"), cast("heal", "hero"), cast("fog", "yard")]
    options += free_block_options(("hall",))
    view = build_view(options, roster(1), "g1", expanded="spells_free")
    assert view.rows[0].kind == "back"
    assert set(ids(view.rows[1:])) == {"cast:heal:1:hero", "cast:fog:1:yard"}


def test_no_free_spells_row_without_such_spells():
    view = build_view([attack("bow", "g1")] + free_block_options(("hall",)), roster(1), "g1")
    assert not any(row.group == "spells_free" for row in view.rows)


def test_unknown_kind_goes_to_more_and_limit_holds():
    options = big_fight(5) + [plain("weird", "brand_new_kind", label="Новое")]
    view = build_view(options, roster(5), "g1")
    assert "weird" not in ids(view.rows)
    assert "weird" in [o.id for o in view.more]
    assert len(view.rows) <= MAX_ROWS


def test_help_hide_items_flee_pickup_are_not_rows_but_in_more():
    rare = [
        plain("help:a:g1", "help", label="Помочь", ally="a", enemy="g1"),
        plain("hide", label="Спрятаться"),
        plain("use_item:potion", "use_item", label="Использовать зелье", cost="bonus"),
        plain("flee", label="Бежать"),
        plain("pickup:sword", "pickup", label="Подобрать меч"),
    ]
    view = build_view([attack("bow", "g1")] + rare + free_block_options(("hall",)), roster(1), "g1")
    shown = ids(view.rows)
    for option in rare:
        assert option.id not in shown
        assert option.id in [o.id for o in view.more]


def test_no_targets_in_reach_hides_target_block():
    view = build_view(free_block_options(), roster(), None)
    assert view.target is None
    assert view.targets == []
    assert view.target_rows == []
    assert "end_turn" in ids(view.rows)
    assert view.rows[-1].kind == "more"


def test_free_block_is_present_without_target():
    view = build_view(free_block_options(("hall",)), roster(), None)
    expected = {"dash", "disengage", "dodge", "second_wind", "move:hall", "end_turn"}
    assert expected <= set(ids(view.rows))


def test_single_zone_move_is_a_plain_row_many_zones_a_group():
    one = build_view(free_block_options(("hall",)), roster(), None)
    many = build_view(free_block_options(("hall", "yard", "cellar")), roster(), None)
    assert "move:hall" in ids(one.rows)
    assert not any(row.group == "move" for row in one.rows)
    assert [row.group for row in many.rows if row.kind == "expand"] == ["move"]
    assert "move:hall" not in ids(many.rows)


def test_stabilize_is_not_hidden():
    options = free_block_options(("hall",)) + [plain("stabilize:ally", "stabilize", target="ally")]
    view = build_view([attack("bow", "g1")] + options, roster(1), "g1")
    assert "stabilize:ally" in ids(view.rows)


def test_second_wind_and_nimble_escape_are_in_free_block():
    options = free_block_options(("hall",)) + [
        plain("disengage_bonus", "disengage", label="Проворное бегство", cost="bonus", bonus=True)
    ]
    view = build_view(options, roster(), None)
    assert {"second_wind", "disengage_bonus"} <= set(ids(view.free_rows))


# Р-1: «Вырваться» (опутанный герой) -- в основном меню, первая строка бесцелевого блока

def restrained_fight(enemies=5):
    # опутан: ходить нельзя (нет move), есть «Вырваться»
    options = [o for o in big_fight(enemies) if o.kind != "move"]
    escape = plain("escape:vines", "escape", label="Вырваться: Лозы (Сила, СЛ 13)")
    return options + [escape]


def test_escape_is_first_row_of_free_block():
    view = build_view(restrained_fight(), roster(5), "g1")
    assert view.free_rows[0].option_id == "escape:vines"


def test_escape_is_visible_with_many_enemies_and_weapons():
    view = build_view(restrained_fight(5), roster(5), "g1")
    assert "escape:vines" in ids(view.rows)
    assert len(view.rows) <= MAX_ROWS
    assert view.rows[-1].kind == "more"


def test_escape_is_not_pushed_out_by_fit():
    view = build_view(restrained_fight(5), roster(5), "g3")
    assert "escape:vines" in ids(view.rows)
    assert "end_turn" in ids(view.rows)
    for weapon in ("sword", "bow", "dagger"):
        assert f"attack:{weapon}:g3" in ids(view.rows)


def test_escape_is_visible_without_target():
    view = build_view(
        free_block_options(()) + [plain("escape:vines", "escape", label="Вырваться")],
        roster(), None,
    )
    assert "escape:vines" in ids(view.rows)


def test_escape_stays_in_more_too():
    view = build_view(restrained_fight(), roster(5), "g1")
    assert "escape:vines" in [o.id for o in view.more]


# «Ещё…»: страховка

def test_more_contains_every_option_not_shown_as_a_row():
    options = big_fight(5)
    view = build_view(options, roster(5), "g1")
    shown = set(ids(view.rows))
    more = set([o.id for o in view.more])
    for option in options:
        assert option.id in shown or option.id in more, option.id


def test_more_contains_the_full_flat_list():
    options = big_fight(5)
    view = build_view(options, roster(5), "g1")
    assert set([o.id for o in view.more]) >= {o.id for o in options}


def test_every_option_is_reachable_by_choosing_its_target_or_more():
    # любой вариант: либо виден после выбора его цели, либо есть в «Ещё…» -- не больше 2 нажатий
    options = big_fight(5)
    for option in options:
        ref = target_of(option) if target_of(option) in NAMES else "g1"
        view = build_view(options, roster(5), ref)
        assert option.id in ids(view.rows) or option.id in [o.id for o in view.more]


# раскрытие

def test_expanded_move_starts_with_back_and_lists_zones():
    view = build_view(big_fight(2), roster(2), "g1", expanded="move")
    assert view.rows[0].kind == "back"
    assert view.rows[0].label == BACK_LABEL
    assert ids(view.rows[1:]) == ["move:hall", "move:yard", "move:cellar"]
    assert len(view.rows) <= MAX_ROWS


def test_expanded_spells_target_lists_only_target_spells():
    view = build_view(big_fight(2), roster(2), "g2", expanded="spells_target")
    assert view.rows[0].kind == "back"
    assert ids(view.rows[1:]) == [f"cast:{s}:1:g2" for s in ("mark", "bolt", "fire", "hex")]


def test_expanded_replaces_both_blocks_and_has_no_more_row():
    view = build_view(big_fight(2), roster(2), "g1", expanded="move")
    assert not any(row.kind == "more" for row in view.rows)
    assert not any(i and i.startswith("attack:") for i in ids(view.rows))


def test_expanded_rows_are_numbered_from_one():
    view = build_view(big_fight(2), roster(2), "g1", expanded="move")
    assert [row.key for row in view.rows][:3] == ["1", "2", "3"]


# fit

def row(label, rank):
    return MenuRow(label, label, rank=rank)


def test_fit_keeps_rows_when_they_fit():
    rows = [row("a", 0), row("b", 5)]
    assert fit(rows, 2) == rows


def test_fit_drops_lowest_priority_first():
    rows = [row("a", 0), row("b", 5), row("c", 1)]
    assert labels(fit(rows, 2)) == ["a", "c"]


def test_fit_drops_last_among_equal_ranks():
    rows = [row("a", 3), row("b", 3), row("c", 3)]
    assert labels(fit(rows, 2)) == ["a", "b"]


def test_fit_keeps_order_of_survivors():
    rows = [row("a", 1), row("b", 9), row("c", 0), row("d", 2)]
    assert labels(fit(rows, 3)) == ["a", "c", "d"]


def test_fit_to_zero_drops_everything():
    assert fit([row("a", 0)], 0) == []


def test_fit_does_not_change_input():
    rows = [row("a", 0), row("b", 5)]
    fit(rows, 1)
    assert len(rows) == 2


# MenuState

def state_with(options=None, count=4, near=(), combat_id="c1"):
    state = MenuState()
    state.load(combat_id, options or big_fight(count), roster(count, near))
    return state


def test_state_default_target_is_first_chip():
    assert state_with().target == "g1"


def test_state_shift_goes_around_the_circle_both_ways():
    state = state_with()
    state.shift(1)
    assert state.target == "g2"
    state.shift(-1)
    state.shift(-1)
    assert state.target == "g4"
    state.shift(1)
    assert state.target == "g1"


def test_state_set_target_ignores_unknown_ref():
    state = state_with()
    state.set_target("nobody")
    assert state.target == "g1"


def test_state_target_survives_next_step_of_same_combat():
    state = state_with()
    state.set_target("g3")
    state.load("c1", big_fight(4), roster(4))
    assert state.target == "g3"


def test_state_target_falls_back_when_target_dropped():
    state = state_with()
    state.set_target("g3")
    state.load("c1", big_fight(2), roster(4))
    assert state.target == "g1"


def test_state_target_and_nonlethal_reset_on_new_combat():
    state = state_with()
    state.set_target("g3")
    state.nonlethal = True
    state.load("c2", big_fight(4), roster(4))
    assert (state.target, state.nonlethal) == ("g1", False)


def test_state_nonlethal_survives_next_step_of_same_combat():
    state = state_with()
    state.nonlethal = True
    state.load("c1", big_fight(4), roster(4))
    assert state.nonlethal is True


def test_state_expanded_is_reset_on_load():
    state = state_with()
    state.expanded = "move"
    state.load("c1", big_fight(4), roster(4))
    assert state.expanded is None


def test_state_set_target_collapses_expansion():
    state = state_with()
    state.expanded = "move"
    state.set_target("g2")
    assert state.expanded is None


def test_state_row_by_visible_number():
    state = state_with()
    assert state.row(1).option_id == "attack:sword:g1"
    assert state.row(0) is None
    assert state.row(len(state.view().rows) + 1) is None


def test_state_find_returns_flat_number_by_id():
    state = state_with()
    option = state.options[7]
    assert state.find(option.id) == (8, option)
    assert state.find("gone") is None


def test_state_row_follows_selected_target():
    state = state_with()
    state.set_target("g2")
    assert state.row(1).option_id == "attack:sword:g2"


# регрессия: движок и протокол не изменились

def goblins_game(cfg, tmp_path, count):
    from test_tui_spells import grey_game

    call = start_combat_call()
    call["input"]["enemies"] = [
        {"ref": f"g{i}", "monster_id": "goblin_warrior", "zone": "hall", "group": "goblins"}
        for i in range(1, count + 1)
    ]
    steps = [tools_step(call), text_step("Гоблины.")]
    game = grey_game(cfg, tmp_path, script_then_react(steps))
    from ai_dm.ui.session import PlaySession

    PlaySession(game).submit("Бью ногой дверь")
    assert game.bundle.session.active_combat is not None
    return game


FLAT_IDS_3_GOBLINS = [
    "attack:composite_longbow:g1", "attack:composite_longbow:g2", "attack:composite_longbow:g3",
    "attack:harpoon_dart:g1", "attack:harpoon_dart:g2", "attack:harpoon_dart:g3",
    "attack:improvised_thrown:g1", "attack:improvised_thrown:g2", "attack:improvised_thrown:g3",
    "attack:composite_longbow:g1:ammo:arrow_armor_piercing",
    "attack:composite_longbow:g2:ammo:arrow_armor_piercing",
    "attack:composite_longbow:g3:ammo:arrow_armor_piercing",
    "attack:composite_longbow:g1:ammo:arrow_frost", "attack:composite_longbow:g2:ammo:arrow_frost",
    "attack:composite_longbow:g3:ammo:arrow_frost",
    "attack:composite_longbow:g1:ammo:arrow_fire", "attack:composite_longbow:g2:ammo:arrow_fire",
    "attack:composite_longbow:g3:ammo:arrow_fire",
    "attack:composite_longbow:g1:ammo:arrow_silver",
    "attack:composite_longbow:g2:ammo:arrow_silver",
    "attack:composite_longbow:g3:ammo:arrow_silver",
    "cast:cure_wounds:1:hero",
    "dash", "disengage", "dodge",
    "parley:g1:intimidation:surrender", "parley:g1:persuasion:defect", "parley:g1:deception:flee",
    "parley:g2:intimidation:surrender", "parley:g2:persuasion:defect", "parley:g2:deception:flee",
    "parley:g3:intimidation:surrender", "parley:g3:persuasion:defect", "parley:g3:deception:flee",
    "cast:ensnaring_strike:1:hero",
    "cast:hunters_mark:1:g1", "cast:hunters_mark:1:g1:free",
    "cast:hunters_mark:1:g2", "cast:hunters_mark:1:g2:free",
    "cast:hunters_mark:1:g3", "cast:hunters_mark:1:g3:free",
    "use_item:stoneskin_elixir", "move:hall", "end_turn",
]


def test_list_options_ids_are_unchanged_in_fight_with_three_goblins(cfg, tmp_path):
    game = goblins_game(cfg, tmp_path, 3)
    flat = [o.id for o in game.runner.preview_turn()]
    # смена экипировки идёт после end_turn и видимые номера не сдвигает
    assert flat[: len(FLAT_IDS_3_GOBLINS)] == FLAT_IDS_3_GOBLINS
    assert all(i.startswith(("equip:", "unequip:")) for i in flat[len(FLAT_IDS_3_GOBLINS):])


def test_option_list_for_narrator_is_the_full_flat_list(cfg, tmp_path):
    game = goblins_game(cfg, tmp_path, 3)
    shown = combat_flow.option_list(game.bundle, game.registry, cfg)
    flat = [o for o in game.runner.preview_turn() if o.kind not in ("equip", "unequip")]
    assert [item["id"] for item in shown] == FLAT_IDS_3_GOBLINS
    assert shown == [{"id": o.id, "label": o.label, "cost": o.cost} for o in flat]


def test_option_list_for_narrator_hides_the_equipment_swap_options(cfg, tmp_path):
    game = goblins_game(cfg, tmp_path, 3)
    flat = game.runner.preview_turn()
    assert any(o.kind in ("equip", "unequip") for o in flat)
    shown = combat_flow.option_list(game.bundle, game.registry, cfg)
    assert not [i for i in shown if i["id"].startswith(("equip:", "unequip:"))]


def test_view_does_not_change_the_flat_options(cfg, tmp_path):
    game = goblins_game(cfg, tmp_path, 3)
    options = game.runner.preview_turn()
    before = [(o.id, o.label, dict(o.params)) for o in options]
    chips = [TargetChip(f"g{i}", f"Воин-гоблин {i}", "7/7") for i in (1, 2, 3)]
    build_view(options, chips, "g1", nonlethal=True)
    assert [(o.id, o.label, dict(o.params)) for o in options] == before


def test_real_fight_view_fits_and_has_all_three_weapons(cfg, tmp_path):
    game = goblins_game(cfg, tmp_path, 3)
    options = game.runner.preview_turn()
    chips = [TargetChip(f"g{i}", f"Воин-гоблин {i}", "7/7") for i in (1, 2, 3)]
    view = build_view(options, chips, "g2")
    shown = ids(view.rows)
    assert len(view.rows) <= MAX_ROWS
    for weapon in ("composite_longbow", "harpoon_dart", "improvised_thrown"):
        assert f"attack:{weapon}:g2" in shown
    assert not any(i and i.endswith(":g1") for i in shown)


def test_real_fight_folds_arrows_of_longbow_into_group(cfg, tmp_path):
    game = goblins_game(cfg, tmp_path, 3)
    options = game.runner.preview_turn()
    chips = [TargetChip(f"g{i}", f"Воин-гоблин {i}", "7/7") for i in (1, 2, 3)]
    view = build_view(options, chips, "g2")
    assert ids(view.target_rows)[:2] == ["attack:composite_longbow:g2", None]
    assert labels(view.target_rows)[1] == "Стрелы ▸"
    opened = build_view(options, chips, "g2", expanded="ammo:composite_longbow")
    assert len(opened.rows) == 5
    assert all(i.startswith("attack:composite_longbow:g2:ammo:") for i in ids(opened.rows[1:]))
    assert all(" — " not in label and "→" not in label for label in labels(opened.rows[1:]))


# fit в build_view: стабилизация и мультиатака вытесняются раньше атаки по цели

def test_stabilize_and_multiattack_are_pushed_out_before_target_attacks():
    options = [attack(f"w{i}", "g1") for i in range(8)]
    options += [
        plain("stabilize:ally", "stabilize", target="ally"),
        plain("multiattack", "multiattack", label="Мультиатака"),
        plain("end_turn", label="Закончить ход", cost="free"),
    ]
    view = build_view(options, roster(1), "g1")
    shown = ids(view.rows)
    assert all(f"attack:w{i}:g1" in shown for i in range(8))
    assert "stabilize:ally" not in shown
    assert "multiattack" not in shown
    assert "end_turn" in shown


# roster_of

def test_roster_of_ranks_own_adjacent_and_far_zones(cfg, tmp_path):
    from ai_dm.ui.screen import roster_of

    game = goblins_game(cfg, tmp_path, 3)
    parts = {p.ref: p for p in game.bundle.session.active_combat.participants}
    parts["g1"].zone_id = "door"
    parts["g2"].zone_id = "hall"
    parts["g3"].zone_id = "balcony"
    chips = {chip.ref: chip for chip in roster_of(game)}
    assert [chips[r].rank for r in ("g1", "g2", "g3")] == [0, 1, 2]


def test_roster_of_has_name_and_hp(cfg, tmp_path):
    from ai_dm.ui.screen import roster_of

    chip = roster_of(goblins_game(cfg, tmp_path, 1))[0]
    assert (chip.ref, chip.name, chip.hp_text) == ("g1", "Воин-гоблин", "10/10")


def test_roster_of_skips_surrendered_and_down_enemies(cfg, tmp_path):
    from ai_dm.ui.screen import roster_of

    game = goblins_game(cfg, tmp_path, 3)
    parts = {p.ref: p for p in game.bundle.session.active_combat.participants}
    parts["g1"].status = "surrendered"
    parts["g2"].status = "down"
    assert [chip.ref for chip in roster_of(game)] == ["g3"]


def test_roster_of_does_not_list_allies(cfg, tmp_path):
    from ai_dm.ui.screen import roster_of

    assert "hero" not in [chip.ref for chip in roster_of(goblins_game(cfg, tmp_path, 2))]


def test_roster_of_does_not_fail_when_hero_is_out_of_combat(cfg, tmp_path):
    from ai_dm.ui.screen import roster_of

    game = goblins_game(cfg, tmp_path, 2)
    state = game.bundle.session.active_combat
    state.participants = [p for p in state.participants if p.ref != "hero"]
    assert isinstance(roster_of(game), tuple)


def test_long_expanded_group_keeps_limit_and_ends_with_more_row():
    spells = [cast(f"s{i}", "g1") for i in range(15)]
    options = [attack("bow", "g1")] + spells + free_block_options(("hall",))
    view = build_view(options, roster(1), "g1", expanded="spells_target")
    assert len(view.rows) <= MAX_ROWS
    assert view.rows[0].kind == "back"
    assert view.rows[-1].kind == "more"
    assert {f"cast:s{i}:1:g1" for i in range(15)} <= {o.id for o in view.more}


# мутанты: подписи, ранги вытеснения, нумерация, начальное состояние

def test_short_label_without_target_still_drops_remaining_attacks_suffix():
    option = attack("bow", "g1", name="лук")
    option.label += " (ещё 1 из 2)"
    assert short_label(option) == "Атака: лук → Гоблин 1"


def test_header_of_without_suffix_is_empty_string():
    assert header_of([attack("bow", "g1")]) == ""


def test_clip_keeps_text_that_fits_exactly():
    assert clip("abcdef", 6) == "abcdef"


def test_clip_cuts_with_ellipsis_to_width():
    assert clip("abcdefg", 6) == "abcde…"


def test_clip_shorter_text_is_unchanged():
    assert clip("abc", 6) == "abc"


def test_nonlethal_row_label_has_no_target_name():
    options = [attack("sword", "g1", "melee", "меч"), stun("sword", "g1", "меч")]
    view = build_view(options + free_block_options(("hall",)), roster(1), "g1", nonlethal=True)
    assert labels(view.target_rows) == ["Оглушающая атака: меч"]


def test_ranged_nonlethal_row_label_is_exact():
    options = [attack("bow", "g1", "ranged", "лук")] + free_block_options(("hall",))
    view = build_view(options, roster(1), "g1", nonlethal=True)
    assert labels(view.target_rows) == ["Атака: лук (дальнобойным — не оглушить)"]


def test_parley_and_spell_rows_have_no_target_name():
    options = [parley("g1"), cast("mark", "g1"), cast("bolt", "g1")]
    view = build_view(options + free_block_options(("hall",)), roster(1), "g1")
    assert labels(view.target_rows) == [
        "Переговоры: persuasion, surrender (СЛ 15)", "mark", "bolt",
    ]


def test_expanded_group_rows_have_no_target_name():
    options = [cast("a", "g1"), cast("b", "g1")] + free_block_options(("hall",))
    view = build_view(options, roster(1), "g1", expanded="spells_target")
    assert labels(view.rows) == [BACK_LABEL, "a", "b"]


def test_two_moves_are_a_group_not_rows():
    view = build_view(free_block_options(("hall", "yard")), roster(), None)
    assert [row.group for row in view.rows if row.kind == "expand"] == ["move"]


def test_number_gives_no_key_after_tenth_row():
    rows = [MenuRow(str(i)) for i in range(12)]
    number(rows)
    assert [row.key for row in rows] == list("1234567890") + ["", ""]


def test_expanded_group_of_exactly_ten_rows_is_not_truncated():
    spells = [cast(f"s{i}", "g1") for i in range(9)]
    options = spells + free_block_options(("hall",))
    view = build_view(options, roster(1), "g1", expanded="spells_target")
    assert len(view.rows) == 10
    assert not any(row.kind == "more" for row in view.rows)
    assert view.rows[-1].key == "0"


def test_long_expanded_group_has_exactly_ten_rows_and_more_label():
    spells = [cast(f"s{i}", "g1") for i in range(15)]
    options = spells + free_block_options(("hall",))
    view = build_view(options, roster(1), "g1", expanded="spells_target")
    assert len(view.rows) == 10
    assert view.rows[-1].label == MORE_LABEL
    assert view.rows[-1].key == "0"
    assert ids(view.rows[1:-1]) == [f"cast:s{i}:1:g1" for i in range(8)]


def test_spells_group_row_is_pushed_out_after_dash_when_one_row_too_many():
    # ранг «Заклинания на цель ▸» равен рангу рывка; из равных уезжает последний (рывок)
    options = [attack(f"w{i}", "g1") for i in range(6)]
    options += [cast(f"s{i}", "g1") for i in range(3)]
    options += [plain("dodge"), plain("dash"), plain("end_turn", cost="free")]
    view = build_view(options, roster(1), "g1")
    assert len(view.rows) == 10
    assert any(row.group == "spells_target" for row in view.rows)
    assert "dash" not in ids(view.rows)


def test_spells_group_row_is_pushed_out_before_second_wind():
    options = [attack(f"w{i}", "g1") for i in range(6)]
    options += [cast(f"s{i}", "g1") for i in range(3)]
    options += [plain("dodge"), plain("second_wind"), plain("dash"), plain("end_turn", cost="free")]
    view = build_view(options, roster(1), "g1")
    assert not any(row.group == "spells_target" for row in view.rows)
    assert {"dodge", "second_wind"} <= set(ids(view.rows))


def test_move_group_is_pushed_out_before_stabilize():
    options = [attack(f"w{i}", "g1") for i in range(7)]
    options += [move("hall"), move("yard"), plain("stabilize:ally", "stabilize", target="ally")]
    options += [plain("end_turn", cost="free")]
    view = build_view(options, roster(1), "g1")
    assert "stabilize:ally" in ids(view.rows)
    assert not any(row.group == "move" for row in view.rows)


def test_free_spells_group_is_pushed_out_before_dash():
    options = [attack(f"w{i}", "g1") for i in range(6)]
    options += [plain("dodge"), plain("dash"), cast("heal", "hero"), plain("end_turn", cost="free")]
    view = build_view(options, roster(1), "g1")
    assert "dash" in ids(view.rows)
    assert not any(row.group == "spells_free" for row in view.rows)


def test_parley_is_pushed_out_before_free_spells_group():
    options = [attack(f"w{i}", "g1") for i in range(6)]
    options += [parley("g1"), plain("dodge"), cast("heal", "hero"), plain("end_turn", cost="free")]
    view = build_view(options, roster(1), "g1")
    assert any(row.group == "spells_free" for row in view.rows)
    assert not any(i and i.startswith("parley:") for i in ids(view.rows))


def test_fresh_state_is_empty():
    state = MenuState()
    assert state.active is False
    assert state.options == []
    assert state.roster == ()
    assert state.chips == []
    assert state.target is None
    assert state.nonlethal is False
    assert state.expanded is None
    assert state.combat_id is None


def test_state_load_activates_and_keeps_roster_and_options():
    state = MenuState()
    chips = roster(2)
    options = big_fight(2)
    state.load("c1", options, chips)
    assert state.active is True
    assert state.options == options
    assert state.roster == chips
    assert state.combat_id == "c1"


def test_state_view_follows_expanded_and_nonlethal():
    state = state_with()
    state.expanded = "move"
    assert state.view().rows[0].kind == "back"
    state.expanded = None
    state.nonlethal = True
    assert state.view().rows[0].option_id == "attack:sword:g1:nonlethal"
