# К3 П3а (docs/plan-k3.md, «Тесты» П3, решение 19, Р26): подгруппа вариантов одного заклинания в
# меню боя (ai_dm.ui.menu_variants + combat_menu), чистые функции на настоящих пунктах движка.
#   Цветной шар у волшебника 1 ур. -- в «Заклинания на цель ▸» одна строка «Цветной шар ▸»;
#     раскрыть -- «Назад» и шесть типов урона; при ≤ 2 заклинаниях на цель строка -- прямо в
#     блоке цели; «Назад» из подгруппы ведёт в группу «Заклинания на цель ▸», а не в корень;
#     Защита от энергии -- пять вариантов в «Заклинания без цели ▸» → «Защита от энергии ▸».
#   Группа variants:<родитель>:<заклинание>:<круг>:<цель>; parent_of возвращает родителя.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "combat"))

from combat_kit import ScriptedRng, make_engine, make_wizard, mon  # noqa: E402

from ai_dm.combat.available import ActionOption  # noqa: E402
from ai_dm.state.creature import ResourcePool  # noqa: E402
from ai_dm.ui.combat_menu import (  # noqa: E402
    BACK_LABEL,
    SPELLS_FREE_LABEL,
    SPELLS_TARGET_LABEL,
    MenuState,
    TargetChip,
    build_view,
)
from ai_dm.ui.menu_variants import (  # noqa: E402
    VARIANTS_GROUP,
    group_of,
    parent_of,
    spell_rows,
    variant_rows,
)

ORB_GROUP = "variants:spells_target:chromatic_orb:1:goblin_1"
CHIPS = [TargetChip("goblin_1", "Воин-гоблин", "10/10")]
TYPES = ["кислота", "холод", "огонь", "молния", "яд", "гром"]


def wizard_options(registry, cfg, prepared, known=()):
    hero = make_wizard(registry)
    hero.sheet.prepared_of()[:] = list(prepared)
    hero.sheet.known_of()[:] = list(known)
    for circle in (2, 3):
        hero.creature.resources[f"spell_slot:{circle}"] = ResourcePool(current=0, max=0)
    engine = make_engine(
        registry, cfg, heroes=[hero], rng=ScriptedRng(), hero_zone="door",
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    return engine, engine.available_actions("wiz")


def labels(rows):
    return [row.label for row in rows]


def variant_option(variant="fire", parent_circle=1):
    return ActionOption(
        id=f"cast:chromatic_orb:{parent_circle}:goblin_1:v:{variant}", kind="cast",
        label=f"Цветной шар ({variant}) → Воин-гоблин",
        params={"spell": "chromatic_orb", "circle": parent_circle, "target": "goblin_1",
                "variant": variant, "title": "Цветной шар"},
    )


# group_of / parent_of

def test_group_of_option_without_variant_is_none():
    plain = ActionOption(
        id="cast:magic_missile:1:goblin_1", kind="cast", label="Волшебная стрела → гоблин",
        params={"spell": "magic_missile", "circle": 1, "target": "goblin_1"},
    )
    assert group_of(plain, None) is None


def test_group_of_variant_option_in_the_root():
    assert group_of(variant_option(), None) == "variants::chromatic_orb:1:goblin_1"


def test_group_of_variant_option_names_its_parent_group():
    assert group_of(variant_option(), "spells_target") == ORB_GROUP


def test_group_is_the_same_for_every_variant_of_one_spell_circle_and_target():
    assert group_of(variant_option("fire"), "x") == group_of(variant_option("cold"), "x")


def test_group_differs_by_circle():
    assert group_of(variant_option(parent_circle=1), "x") != group_of(
        variant_option(parent_circle=2), "x"
    )


def test_parent_of_a_nested_group_is_the_group_it_was_opened_from():
    assert parent_of(ORB_GROUP) == "spells_target"


def test_parent_of_a_root_subgroup_is_none():
    assert parent_of("variants::chromatic_orb:1:goblin_1") is None


def test_parent_of_none_and_plain_groups_is_none():
    assert parent_of(None) is None
    assert parent_of("spells_target") is None
    assert parent_of("move") is None


def test_variants_prefix_is_stable():
    assert VARIANTS_GROUP == "variants:"


# движок: пункты и рассказчик

def test_engine_gives_six_options_with_variant_params(registry, cfg):
    _, options = wizard_options(registry, cfg, ["chromatic_orb"])
    orb = [o for o in options if o.params.get("spell") == "chromatic_orb"]
    assert [o.params["variant"] for o in orb] == [
        "acid", "cold", "fire", "lightning", "poison", "thunder",
    ]


# меню: цель

def test_orb_collapses_into_one_row_inside_the_spells_group(registry, cfg):
    _, options = wizard_options(
        registry, cfg, ["chromatic_orb", "magic_missile"], known=["fire_bolt"]
    )
    view = build_view(options, CHIPS, "goblin_1", expanded="spells_target")
    assert "Цветной шар ▸" in labels(view.target_rows)
    assert not [label for label in labels(view.target_rows) if "(огонь)" in label]


def test_spells_group_row_hides_the_orb_in_the_target_block(registry, cfg):
    _, options = wizard_options(
        registry, cfg, ["chromatic_orb", "magic_missile"], known=["fire_bolt"]
    )
    view = build_view(options, CHIPS, "goblin_1")
    assert SPELLS_TARGET_LABEL in labels(view.target_rows)
    assert "Цветной шар ▸" not in labels(view.target_rows)


def test_with_two_target_spells_or_fewer_the_orb_row_sits_in_the_target_block(registry, cfg):
    _, options = wizard_options(registry, cfg, ["chromatic_orb"])
    view = build_view(options, CHIPS, "goblin_1")
    assert "Цветной шар ▸" in labels(view.target_rows)
    assert SPELLS_TARGET_LABEL not in labels(view.target_rows)


def test_orb_row_expands_its_own_variant_group(registry, cfg):
    _, options = wizard_options(
        registry, cfg, ["chromatic_orb", "magic_missile"], known=["fire_bolt"]
    )
    view = build_view(options, CHIPS, "goblin_1", expanded="spells_target")
    row = next(r for r in view.target_rows if r.label == "Цветной шар ▸")
    assert (row.kind, row.group) == ("expand", ORB_GROUP)


def test_expanded_orb_group_lists_back_and_six_types(registry, cfg):
    _, options = wizard_options(
        registry, cfg, ["chromatic_orb", "magic_missile"], known=["fire_bolt"]
    )
    view = build_view(options, CHIPS, "goblin_1", expanded=ORB_GROUP)
    rows = view.target_rows
    assert rows[0].label == BACK_LABEL
    assert [r.label.split(" ")[0] for r in rows[1:]] == TYPES


def test_orb_variant_rows_are_options_with_their_ids(registry, cfg):
    _, options = wizard_options(
        registry, cfg, ["chromatic_orb", "magic_missile"], known=["fire_bolt"]
    )
    view = build_view(options, CHIPS, "goblin_1", expanded=ORB_GROUP)
    fire = next(r for r in view.target_rows if r.label.startswith("огонь"))
    assert fire.kind == "option"
    assert fire.option_id == "cast:chromatic_orb:1:goblin_1:v:fire"


def test_back_from_the_orb_group_leads_to_the_spells_group_not_the_root(registry, cfg):
    _, options = wizard_options(
        registry, cfg, ["chromatic_orb", "magic_missile"], known=["fire_bolt"]
    )
    view = build_view(options, CHIPS, "goblin_1", expanded=ORB_GROUP)
    back = view.target_rows[0]
    assert (back.kind, back.group) == ("back", "spells_target")
    assert parent_of(ORB_GROUP) == back.group


def test_back_from_an_inline_orb_group_leads_to_the_root(registry, cfg):
    _, options = wizard_options(registry, cfg, ["chromatic_orb"])
    group = "variants::chromatic_orb:1:goblin_1"
    view = build_view(options, CHIPS, "goblin_1", expanded=group)
    back = view.target_rows[0]
    assert (back.kind, back.group) == ("back", None)


def test_orb_variant_rows_are_numbered_from_one(registry, cfg):
    _, options = wizard_options(
        registry, cfg, ["chromatic_orb", "magic_missile"], known=["fire_bolt"]
    )
    view = build_view(options, CHIPS, "goblin_1", expanded=ORB_GROUP)
    assert [r.key for r in view.target_rows] == ["1", "2", "3", "4", "5", "6", "7"]


def test_orb_variant_rows_drop_the_target_name_when_the_target_is_chosen(registry, cfg):
    _, options = wizard_options(
        registry, cfg, ["chromatic_orb", "magic_missile"], known=["fire_bolt"]
    )
    view = build_view(options, CHIPS, "goblin_1", expanded=ORB_GROUP)
    assert [r.label for r in view.target_rows[1:]] == TYPES


def test_orb_variant_rows_stay_in_the_target_block(registry, cfg):
    _, options = wizard_options(
        registry, cfg, ["chromatic_orb", "magic_missile"], known=["fire_bolt"]
    )
    rows = variant_rows(options, "goblin_1", ORB_GROUP)
    assert {r.block for r in rows[1:]} == {"target"}


def test_variant_row_label_keeps_a_target_name_with_brackets_for_another_target():
    option = variant_option()
    option.label = "Цветной шар (огонь) → Гоблин (вожак)"
    rows = variant_rows([option], "goblin_2", ORB_GROUP)
    assert rows[1].label == "огонь → Гоблин (вожак)"


def test_spell_rows_collapse_variants_into_a_row_ranked_like_a_spell():
    rows = spell_rows([variant_option("fire"), variant_option("cold")], "goblin_1", "spells_target")
    assert [(r.label, r.rank) for r in rows] == [("Цветной шар ▸", 3)]


def test_menu_state_expanded_group_survives_until_target_changes(registry, cfg):
    _, options = wizard_options(registry, cfg, ["chromatic_orb"])
    state = MenuState()
    state.load("fight", options, CHIPS)
    state.expanded = "variants::chromatic_orb:1:goblin_1"
    assert state.view().target_rows[0].label == BACK_LABEL
    state.set_target("goblin_1")
    assert state.expanded is None


# меню: без цели

def test_protection_from_energy_is_one_row_in_the_free_spells_group(registry, cfg):
    hero = make_wizard(registry)
    hero.sheet.prepared_of()[:] = ["protection_from_energy"]
    hero.creature.resources["spell_slot:3"] = ResourcePool(current=2, max=2)
    engine = make_engine(
        registry, cfg, heroes=[hero], rng=ScriptedRng(), hero_zone="door",
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    options = engine.available_actions("wiz")
    root = build_view(options, CHIPS, "goblin_1")
    assert SPELLS_FREE_LABEL in labels(root.free_rows)
    group = build_view(options, CHIPS, "goblin_1", expanded="spells_free")
    assert "Защита от энергии ▸" in labels(group.target_rows)
    row = next(r for r in group.target_rows if r.label == "Защита от энергии ▸")
    energy = build_view(options, CHIPS, "goblin_1", expanded=row.group)
    assert energy.target_rows[0].label == BACK_LABEL
    assert energy.target_rows[0].group == "spells_free"
    assert len(energy.target_rows) == 1 + 5
