# Ожидаемый API: ai_dm.protocol.apply.apply(ctx, request) -- см. контракт в protocol_kit.py.
# Бой (ТЗ 2.1, 2.3, 7; STAGE2-PLAN A2/A5): start_combat, player_action, npc_action, defeat_outcome,
# end_combat.
#   * start_combat строит CombatState в session.active_combat (НЕ запускает инициативу: round 0,
#     rng не трогается -- это делает game). Герой -- Participant(side heroes, controller "external",
#     zone = hero_zone); безымянные монстры -- Participant.creature из registry, controller
#     "engine";
#     ref из world.npcs -- именованный NPC: creature None, controller "external" у ключевого
#     (npc.key), "engine" у обычного. Группа "party" (лидер -- герой, intent None) добавляется;
#     группы врагов -- из запроса. Проверка -- combat.setup.validate_start: ошибка -> Invalid
#     с code = первый код (graph_disconnected, group_unknown, participant_zone_unknown,
#     participant_duplicate ...; сообщение по-русски с id сущностей), бой
#     не создаётся. Врагов > cfg.limits.max_enemies -> первые
#     max_enemies, clamped, report_tag "limit-exceeded". Неизвестный monster_id -> Invalid
#     unknown_monster; бой уже идёт -> Invalid combat_already_active.
#   * player_action: нет боя -> Invalid no_active_combat; иначе accepted, result["steps"] -- шаги
#     как есть (выполняет их game через Controller.choose).
#   * npc_action: только в ctx.mode == "npc_choice" и choice из ctx.npc_options; иначе Invalid
#     not_available_in_mode / unknown_option; result["choice"].
#   * defeat_outcome: нет боя -> Invalid no_active_combat; outcome != "defeat_pending" -> Invalid
#     no_defeat_pending; иначе combat.defeat.apply_defeat_outcome; его Rejected -> Decision
#     rejected с тем же report_tag ("invalid-defeat"), успех -> accepted.
#   * end_combat: нет боя -> Invalid no_active_combat; иначе outcome "ended_by_master" и флаг
#     combat_ended:<id> (CombatEngine.end_combat); сброс active_combat -- дело game.
import pytest
from protocol_kit import combat_request, dump, goblin, make_bundle, make_ctx, req, zone

from ai_dm.protocol.apply import HANDLERS, apply
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.protocol.requests import VISIBLE_TYPES
from ai_dm.rules.inventory import add_item
from ai_dm.state.combat import CombatState


def start(registry, cfg, request=None, bundle=None, **kwargs):
    ctx = make_ctx(registry, cfg, bundle=bundle, **kwargs)
    d = apply(ctx, request if request is not None else combat_request())
    return ctx, d


def participant(ctx, ref):
    for p in ctx.bundle.session.active_combat.participants:
        if p.ref == ref:
            return p
    raise KeyError(ref)


def enemies_of(ctx):
    return [p for p in ctx.bundle.session.active_combat.participants if p.side == "enemies"]


# start_combat: принят

def test_start_combat_creates_combat_state(registry, cfg):
    ctx, d = start(registry, cfg)
    assert isinstance(d, Decision)
    assert d.status == "accepted"
    state = ctx.bundle.session.active_combat
    assert isinstance(state, CombatState)
    assert d.result["combat_id"] == state.id
    assert d.log


def test_start_combat_zones_and_groups(registry, cfg):
    ctx, _ = start(registry, cfg)
    state = ctx.bundle.session.active_combat
    assert [z.id for z in state.zones] == ["door", "hall", "balcony"]
    assert state.zones[1].adjacent == ["door", "balcony"]
    assert state.groups["goblins"].leader_id == "g1"
    assert state.groups["goblins"].intent == "kill"
    assert state.groups["party"].leader_id == "hero"
    assert state.groups["party"].intent is None


def test_start_combat_does_not_start_initiative_or_roll(registry, cfg):
    ctx, _ = start(registry, cfg)
    state = ctx.bundle.session.active_combat
    assert state.round == 0
    assert state.initiative_order == []
    assert ctx.rng.draws == 0


def test_start_combat_hero_is_external_in_given_zone(registry, cfg):
    ctx, _ = start(registry, cfg)
    hero = participant(ctx, "hero")
    assert hero.side == "heroes"
    assert hero.group_id == "party"
    assert hero.controller == "external"
    assert hero.zone_id == "door"
    assert hero.creature is None


def test_start_combat_unnamed_monsters_keep_state_in_participant(registry, cfg):
    ctx, _ = start(registry, cfg)
    hit_points = registry.get("monster", "goblin_warrior").hp
    for ref in ("g1", "g2"):
        p = participant(ctx, ref)
        assert p.side == "enemies"
        assert p.group_id == "goblins"
        assert p.monster_id == "goblin_warrior"
        assert p.zone_id == "hall"
        assert p.controller == "engine"
        assert p.creature.hp_current == p.creature.hp_max == hit_points
    assert "g1" not in ctx.bundle.world.npcs


def test_start_combat_unnamed_monsters_do_not_share_state(registry, cfg):
    ctx, _ = start(registry, cfg)
    participant(ctx, "g1").creature.hp_current = 1
    assert participant(ctx, "g2").creature.hp_current != 1


def test_start_combat_key_npc_is_external(registry, cfg):
    request = combat_request(
        enemies=[
            goblin("g1"), goblin("g2"),
            {"ref": "grakh", "monster_id": "goblin_boss", "zone": "hall", "group": "goblins"},
        ],
        groups=[{
            "id": "goblins", "leader": "grakh", "intent": "capture",
            "lair_location_id": "goblin_den",
        }],
    )
    ctx, d = start(registry, cfg, request)
    assert d.status == "accepted"
    boss = participant(ctx, "grakh")
    assert boss.controller == "external"
    assert boss.creature is None
    assert boss.monster_id == "goblin_boss"
    state = ctx.bundle.session.active_combat
    assert state.groups["goblins"].intent == "capture"
    assert state.groups["goblins"].lair_location_id == "goblin_den"


def test_start_combat_non_key_named_npc_is_engine_controlled(registry, cfg):
    request = combat_request(
        enemies=[{"ref": "aldric", "monster_id": "guard", "zone": "hall", "group": "goblins"}],
        groups=[{"id": "goblins", "leader": "aldric", "intent": "drive_off"}],
    )
    ctx, d = start(registry, cfg, request)
    assert d.status == "accepted"
    assert participant(ctx, "aldric").controller == "engine"
    assert participant(ctx, "aldric").creature is None


def test_start_combat_sets_no_flags_by_itself(registry, cfg):
    ctx, _ = start(registry, cfg)
    assert not [k for k in ctx.bundle.world.flags if k.startswith("combat_ended:")]


# start_combat: Invalid

def disconnected_request():
    zones = [zone("a", ["b"]), zone("b", ["a"]), zone("c", [])]
    return combat_request(
        zones=zones, enemies=[goblin("g1", zone_id="a"), goblin("g2", zone_id="b")],
        hero_zone="a",
    )


def test_start_combat_disconnected_zones_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, disconnected_request())
    assert isinstance(d, Invalid)
    assert d.code == "graph_disconnected"
    assert ctx.bundle.session.active_combat is None
    assert dump(ctx) == before


def test_start_combat_unknown_group_is_invalid(registry, cfg):
    request = combat_request(enemies=[goblin("g1", group="ghosts")])
    ctx, d = start(registry, cfg, request)
    assert isinstance(d, Invalid)
    assert d.code == "group_unknown"
    assert ctx.bundle.session.active_combat is None


def test_start_combat_unknown_enemy_zone_is_invalid(registry, cfg):
    request = combat_request(enemies=[goblin("g1", zone_id="moon")])
    ctx, d = start(registry, cfg, request)
    assert isinstance(d, Invalid)
    assert d.code == "participant_zone_unknown"


def test_start_combat_duplicate_refs_is_invalid(registry, cfg):
    request = combat_request(enemies=[goblin("g1"), goblin("g1")])
    ctx, d = start(registry, cfg, request)
    assert isinstance(d, Invalid)
    assert d.code == "participant_duplicate"


def test_start_combat_unknown_monster_is_invalid(registry, cfg):
    request = combat_request(
        enemies=[{"ref": "g1", "monster_id": "tarrasque_9", "zone": "hall", "group": "goblins"}]
    )
    ctx, d = start(registry, cfg, request)
    assert isinstance(d, Invalid)
    assert d.code == "unknown_monster"
    assert ctx.bundle.session.active_combat is None


def test_start_combat_while_combat_is_active_is_invalid(registry, cfg):
    ctx, _ = start(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, combat_request())
    assert isinstance(d, Invalid)
    assert d.code == "combat_already_active"
    assert dump(ctx) == before


# start_combat: лимит врагов

def many_goblins(count):
    return combat_request(enemies=[goblin(f"g{i}") for i in range(1, count + 1)])


def test_start_combat_more_than_six_enemies_is_clamped(registry, cfg):
    ctx, d = start(registry, cfg, many_goblins(8))
    assert d.status == "clamped"
    assert d.report_tag == "limit-exceeded"
    assert d.signal_to_master
    assert [p.ref for p in enemies_of(ctx)] == ["g1", "g2", "g3", "g4", "g5", "g6"]
    assert ctx.marks == ["limit-exceeded"]
    assert isinstance(ctx.bundle.session.active_combat, CombatState)


def test_start_combat_exactly_six_enemies_is_accepted(registry, cfg):
    ctx, d = start(registry, cfg, many_goblins(6))
    assert d.status == "accepted"
    assert len(enemies_of(ctx)) == 6


def test_start_combat_enemy_limit_comes_from_config(registry, cfg):
    small = cfg.model_copy(deep=True)
    small.limits.max_enemies = 2
    ctx, d = start(registry, small, many_goblins(3))
    assert d.status == "clamped"
    assert len(enemies_of(ctx)) == 2


# player_action / npc_action

def test_player_action_without_combat_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, req("player_action", steps=["attack:longsword:g1"]))
    assert isinstance(d, Invalid)
    assert d.code == "no_active_combat"
    assert dump(ctx) == before


def test_player_action_in_combat_is_accepted_and_returns_steps(registry, cfg):
    ctx, _ = start(registry, cfg)
    steps = ["move:hall", "attack:longsword:g1"]
    d = apply(ctx, req("player_action", steps=steps))
    assert d.status == "accepted"
    assert d.result["steps"] == steps


def test_player_action_unsupported_gets_missing_mechanic_tag(registry, cfg):
    ctx, _ = start(registry, cfg)
    d = apply(ctx, req("player_action", steps=[], unsupported="приручить дракона"))
    assert d.report_tag == "missing-mechanic"
    assert "missing-mechanic" in ctx.marks


def test_npc_action_outside_npc_mode_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg, mode="combat_narrate")
    before = dump(ctx)
    d = apply(ctx, req("npc_action", choice="end_turn"))
    assert isinstance(d, Invalid)
    assert d.code == "not_available_in_mode"
    assert dump(ctx) == before


def test_npc_action_in_default_mode_is_invalid(registry, cfg):
    d = apply(make_ctx(registry, cfg), req("npc_action", choice="end_turn"))
    assert isinstance(d, Invalid)


def test_npc_action_in_npc_mode_with_listed_choice_is_accepted(registry, cfg):
    options = ["attack:scimitar:hero", "end_turn"]
    ctx = make_ctx(registry, cfg, mode="npc_choice", npc_options=options)
    d = apply(ctx, req("npc_action", choice="attack:scimitar:hero"))
    assert d.status == "accepted"
    assert d.result["choice"] == "attack:scimitar:hero"


def test_npc_action_with_unlisted_choice_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg, mode="npc_choice", npc_options=["end_turn"])
    d = apply(ctx, req("npc_action", choice="cast:fireball:3:hero"))
    assert isinstance(d, Invalid)
    assert d.code == "unknown_option"


# defeat_outcome

def pending_ctx(registry, cfg, money=1000):
    bundle = make_bundle(registry)
    bundle.heroes[0].money_cp = money
    ctx, _ = start(registry, cfg, bundle=bundle)
    ctx.bundle.session.active_combat.outcome = "defeat_pending"
    return ctx


def test_defeat_outcome_without_combat_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("defeat_outcome", consequences=["scar"], scar_ability="str"))
    assert isinstance(d, Invalid)
    assert d.code == "no_active_combat"


def test_defeat_outcome_without_pending_defeat_is_invalid(registry, cfg):
    ctx, _ = start(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, req("defeat_outcome", consequences=["scar"], scar_ability="str"))
    assert isinstance(d, Invalid)
    assert d.code == "no_defeat_pending"
    assert dump(ctx) == before


def test_defeat_capture_moves_hero_to_lair_and_strips_items(registry, cfg):
    ctx = pending_ctx(registry, cfg)
    d = apply(ctx, req("defeat_outcome", consequences=["capture"], lair_location_id="goblin_den"))
    assert d.status == "accepted"
    assert ctx.hero.location_id == "goblin_den"
    assert ctx.hero.inventory == []
    assert ctx.bundle.world.flags["visited:goblin_den"] is True
    assert d.log or ctx.events


def test_defeat_scar_lowers_ability_and_records_scar(registry, cfg):
    ctx = pending_ctx(registry, cfg)
    before = ctx.hero.sheet.abilities["str"]
    d = apply(
        ctx, req("defeat_outcome", consequences=["scar"], scar_ability="str", scar_text="шрам")
    )
    assert d.status == "accepted"
    assert ctx.hero.sheet.abilities["str"] == before - 1
    assert ctx.hero.scars == ["шрам"]


def test_defeat_rob_takes_half_of_gold(registry, cfg):
    ctx = pending_ctx(registry, cfg, money=1000)
    d = apply(ctx, req("defeat_outcome", consequences=["rob"], rob_items=0))
    assert d.status == "accepted"
    assert ctx.hero.money_cp == 500


def test_defeat_two_consequences(registry, cfg):
    ctx = pending_ctx(registry, cfg)
    d = apply(ctx, req(
        "defeat_outcome", consequences=["scar", "capture"], scar_ability="dex",
        lair_location_id="goblin_den",
    ))
    assert d.status == "accepted"
    assert ctx.hero.location_id == "goblin_den"
    assert len(ctx.hero.scars) == 1


def test_defeat_three_consequences_is_rejected_and_changes_nothing(registry, cfg):
    ctx = pending_ctx(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, req(
        "defeat_outcome", consequences=["scar", "exhaustion", "rob"], scar_ability="dex",
        rob_items=0,
    ))
    assert isinstance(d, Invalid)
    assert d.code == "invalid_defeat"
    assert d.message
    assert dump(ctx) == before


def test_defeat_capture_without_lair_is_rejected(registry, cfg):
    ctx = pending_ctx(registry, cfg)
    d = apply(ctx, req("defeat_outcome", consequences=["capture"]))
    assert isinstance(d, Invalid)
    assert d.code == "invalid_defeat"


def test_defeat_capture_uses_lair_of_defeating_group(registry, cfg):
    request = combat_request(groups=[{
        "id": "goblins", "leader": "g1", "intent": "capture", "lair_location_id": "goblin_den",
    }])
    bundle = make_bundle(registry)
    ctx, _ = start(registry, cfg, request, bundle=bundle)
    ctx.bundle.session.active_combat.outcome = "defeat_pending"
    ctx.bundle.session.active_combat.defeat_group_id = "goblins"
    d = apply(ctx, req("defeat_outcome", consequences=["capture"]))
    assert d.status == "accepted"
    assert ctx.hero.location_id == "goblin_den"


# end_combat

def test_end_combat_without_combat_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("end_combat", reason="враги сдались"))
    assert isinstance(d, Invalid)
    assert d.code == "no_active_combat"


def test_end_combat_marks_outcome_and_flag(registry, cfg):
    ctx, _ = start(registry, cfg)
    state = ctx.bundle.session.active_combat
    d = apply(ctx, req("end_combat", reason="враги сдались"))
    assert d.status == "accepted"
    assert state.outcome == "ended_by_master"
    assert ctx.bundle.world.flags[f"combat_ended:{state.id}"] is True
    assert "combat_ended" in [e.type for e in ctx.events]
    assert d.log


# B1: срез врагов до max_enemies -- группы без участников убираются, лидер переназначается

def seven_enemies_request(groups):
    enemies = [goblin(f"g{i}", group="first") for i in range(1, 7)] + [goblin("g7", group="second")]
    return combat_request(enemies=enemies, groups=groups)


def test_start_combat_cut_enemy_leader_of_empty_group_is_dropped(registry, cfg):
    request = seven_enemies_request([
        {"id": "first", "leader": "g1", "intent": "kill"},
        {"id": "second", "leader": "g7", "intent": "kill"},
    ])
    ctx, d = start(registry, cfg, request)
    assert isinstance(d, Decision)
    assert d.status == "clamped"
    assert d.report_tag == "limit-exceeded"
    state = ctx.bundle.session.active_combat
    assert isinstance(state, CombatState)
    assert sorted(state.groups) == ["first", "party"]
    assert len(enemies_of(ctx)) == 6
    assert ctx.marks == ["limit-exceeded"]


def test_start_combat_cut_leader_is_replaced_by_first_remaining_member(registry, cfg):
    enemies = [goblin(f"g{i}", group="first") for i in range(1, 4)]
    enemies += [goblin(f"g{i}", group="second") for i in range(4, 8)]
    request = combat_request(enemies=enemies, groups=[
        {"id": "first", "leader": "g1", "intent": "kill"},
        {"id": "second", "leader": "g7", "intent": "kill"},
    ])
    ctx, d = start(registry, cfg, request)
    assert d.status == "clamped"
    state = ctx.bundle.session.active_combat
    assert state.groups["second"].leader_id == "g4"
    assert state.groups["first"].leader_id == "g1"


def test_start_combat_without_enemies_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, combat_request(enemies=[]))
    assert isinstance(d, Invalid)
    assert d.code == "no_enemies"
    assert ctx.bundle.session.active_combat is None
    assert dump(ctx) == before


# B2: NPC мира не в статусе alive в бой не идёт

def aldric_request():
    return combat_request(
        enemies=[{"ref": "aldric", "monster_id": "guard", "zone": "hall", "group": "goblins"}],
        groups=[{"id": "goblins", "leader": "aldric", "intent": "drive_off"}],
    )


@pytest.mark.parametrize("status", ["dead", "gone", "changed"])
def test_start_combat_with_unavailable_npc_is_invalid(status, registry, cfg):
    bundle = make_bundle(registry)
    bundle.world.npcs["aldric"].status = status
    ctx = make_ctx(registry, cfg, bundle=bundle)
    before = dump(ctx)
    d = apply(ctx, aldric_request())
    assert isinstance(d, Invalid)
    assert d.code == "npc_unavailable"
    assert ctx.bundle.session.active_combat is None
    assert dump(ctx) == before


def test_start_combat_with_alive_npc_is_accepted(registry, cfg):
    ctx, d = start(registry, cfg, aldric_request())
    assert d.status == "accepted"


# B4: defeat_outcome -- ссылки на мир и срез rob_items

def test_defeat_outcome_unknown_lair_is_invalid(registry, cfg):
    ctx = pending_ctx(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, req("defeat_outcome", consequences=["capture"], lair_location_id="atlantis"))
    assert isinstance(d, Invalid)
    assert d.code == "unknown_location"
    assert dump(ctx) == before


def test_defeat_outcome_unknown_creditor_is_invalid(registry, cfg):
    ctx = pending_ctx(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, req("defeat_outcome", consequences=["debt"], debt_to="nobody"))
    assert isinstance(d, Invalid)
    assert d.code == "unknown_npc"
    assert dump(ctx) == before


def test_defeat_outcome_known_references_are_accepted(registry, cfg):
    ctx = pending_ctx(registry, cfg)
    d = apply(ctx, req(
        "defeat_outcome", consequences=["capture", "debt"], lair_location_id="goblin_den",
        debt_to="aldric",
    ))
    assert d.status == "accepted"
    assert ctx.hero.location_id == "goblin_den"
    assert ctx.bundle.world.flags["debt:hero"] == "aldric"


def units(hero):
    return sum(entry.qty for entry in hero.inventory)


def test_defeat_outcome_rob_items_50_is_clamped_to_two(registry, cfg):
    ctx = pending_ctx(registry, cfg)
    add_item(ctx.hero, "crowbar", 5, cost_cp=0)
    before = units(ctx.hero)
    d = apply(ctx, req("defeat_outcome", consequences=["rob"], rob_items=50))
    assert d.status == "clamped"
    assert d.report_tag == "limit-exceeded"
    assert d.signal_to_master
    assert before - units(ctx.hero) == 2
    assert "limit-exceeded" in ctx.marks


def test_defeat_outcome_rob_items_within_limit_is_accepted(registry, cfg):
    ctx = pending_ctx(registry, cfg)
    add_item(ctx.hero, "crowbar", 5, cost_cp=0)
    before = units(ctx.hero)
    d = apply(ctx, req("defeat_outcome", consequences=["rob"], rob_items=1))
    assert d.status == "accepted"
    assert before - units(ctx.hero) == 1


# B5: ошибки формы defeat_outcome -- Invalid invalid_defeat с причиной в сообщении

def test_defeat_outcome_scar_without_ability_is_invalid_defeat(registry, cfg):
    ctx = pending_ctx(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, req("defeat_outcome", consequences=["scar"]))
    assert isinstance(d, Invalid)
    assert d.code == "invalid_defeat"
    assert "scar_ability" in d.message
    assert dump(ctx) == before


def test_defeat_outcome_duplicate_consequences_is_invalid_defeat(registry, cfg):
    ctx = pending_ctx(registry, cfg)
    d = apply(ctx, req("defeat_outcome", consequences=["exhaustion", "exhaustion"]))
    assert isinstance(d, Invalid)
    assert d.code == "invalid_defeat"


# D4: id боя -- первое n >= 1 без флага combat_ended:combat_<n>

@pytest.mark.parametrize(
    "ended, expected",
    [
        ([], "combat_1"), ([1], "combat_2"), ([1, 2], "combat_3"), ([2], "combat_1"),
        ([1, 3], "combat_2"),
    ],
)
def test_combat_id_is_first_number_without_ended_flag(ended, expected, registry, cfg):
    bundle = make_bundle(registry)
    for number in ended:
        bundle.world.flags[f"combat_ended:combat_{number}"] = True
    ctx, d = start(registry, cfg, bundle=bundle)
    assert d.result["combat_id"] == expected
    assert ctx.bundle.session.active_combat.id == expected


def test_combat_id_ignores_other_combat_ended_flags(registry, cfg):
    bundle = make_bundle(registry)
    bundle.world.flags["combat_ended:old_fight"] = True
    ctx, d = start(registry, cfg, bundle=bundle)
    assert d.result["combat_id"] == "combat_1"


# D5: Invalid от validate_start -- русская подсказка с id сущностей

def has_cyrillic(text):
    return any("а" <= ch.lower() <= "я" or ch.lower() == "ё" for ch in text)


def test_invalid_start_message_is_russian_for_disconnected_graph(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, disconnected_request())
    assert d.code == "graph_disconnected"
    assert has_cyrillic(d.message)


def test_invalid_start_message_names_unknown_group(registry, cfg):
    ctx, d = start(registry, cfg, combat_request(enemies=[goblin("g1", group="ghosts")]))
    assert d.code == "group_unknown"
    assert has_cyrillic(d.message)
    assert "ghosts" in d.message


def test_invalid_start_message_names_unknown_zone(registry, cfg):
    ctx, d = start(registry, cfg, combat_request(enemies=[goblin("g1", zone_id="moon")]))
    assert d.code == "participant_zone_unknown"
    assert has_cyrillic(d.message)
    assert "moon" in d.message


def test_invalid_start_message_names_duplicate_ref(registry, cfg):
    ctx, d = start(registry, cfg, combat_request(enemies=[goblin("g1"), goblin("g1")]))
    assert d.code == "participant_duplicate"
    assert has_cyrillic(d.message)
    assert "g1" in d.message


def test_invalid_start_message_for_missing_intent_names_group(registry, cfg):
    request = combat_request(groups=[{"id": "goblins", "leader": "g1", "intent": "kill"}])
    request.groups[0].intent = None
    ctx, d = start(registry, cfg, request)
    assert isinstance(d, Invalid)
    assert d.code == "group_intent_missing"
    assert has_cyrillic(d.message)
    assert "goblins" in d.message


def test_invalid_start_message_for_few_zones_is_not_the_bare_code(registry, cfg):
    request = combat_request(
        zones=[zone("door", [])], enemies=[goblin("g1", zone_id="door")]
    )
    ctx, d = start(registry, cfg, request)
    assert isinstance(d, Invalid)
    assert d.code == "zones_count"
    assert has_cyrillic(d.message)


# D6: npc_action -- обычный обработчик в HANDLERS, режим проверяет он сам

def test_npc_action_is_in_handlers():
    assert "npc_action" in HANDLERS
    assert set(HANDLERS) == set(VISIBLE_TYPES) | {"npc_action"}


def test_npc_action_handler_checks_mode_itself(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = HANDLERS["npc_action"](ctx, req("npc_action", choice="end_turn"))
    assert isinstance(d, Invalid)
    assert d.code == "not_available_in_mode"


# player_action и варианты боя (ctx.combat_options)

OPTIONS = [
    {"id": "move:hall", "label": "Шаг в зал"},
    {"id": "attack:longsword:g1", "label": "Атака мечом"},
    {"id": "end_turn", "label": "Закончить ход"},
]


def options_ctx(registry, cfg):
    ctx, _ = start(registry, cfg)
    ctx.combat_options = OPTIONS
    return ctx


def test_combat_options_default_to_none(registry, cfg):
    assert make_ctx(registry, cfg).combat_options is None


def test_player_action_first_step_from_options_is_accepted(registry, cfg):
    ctx = options_ctx(registry, cfg)
    d = apply(ctx, req("player_action", steps=["move:hall", "attack:longsword:g1"]))
    assert d.status == "accepted"
    assert d.result["steps"] == ["move:hall", "attack:longsword:g1"]


def test_player_action_first_step_not_from_options_is_unknown_step(registry, cfg):
    ctx = options_ctx(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, req("player_action", steps=["attack:longsword:ghost"]))
    assert isinstance(d, Invalid)
    assert d.code == "unknown_step"
    assert dump(ctx) == before


def test_player_action_later_steps_are_not_checked_against_options(registry, cfg):
    # после первого шага набор вариантов меняется: остальные шаги проверит движок
    ctx = options_ctx(registry, cfg)
    d = apply(ctx, req("player_action", steps=["move:hall", "attack:longsword:g2"]))
    assert d.status == "accepted"
    assert d.result["steps"] == ["move:hall", "attack:longsword:g2"]


def test_player_action_without_options_does_not_check_first_step(registry, cfg):
    ctx, _ = start(registry, cfg)
    assert ctx.combat_options is None
    d = apply(ctx, req("player_action", steps=["attack:longsword:ghost"]))
    assert d.status == "accepted"


# ТБ #56 (docs/plan-tb.md п.2): ошибка start_combat -- монстры пака, существование -- весь реестр

def scoped_registry(registry, scope):
    reg = registry.with_items({})
    reg.monster_scope = scope
    return reg


def unknown_monster_request():
    return combat_request(
        enemies=[{"ref": "g1", "monster_id": "tarrasque_9", "zone": "hall", "group": "goblins"}]
    )


def test_start_combat_unknown_monster_message_lists_scope_only(registry, cfg):
    reg = scoped_registry(registry, ["wolf", "boar"])
    _, d = start(reg, cfg, unknown_monster_request())
    assert d.code == "unknown_monster"
    assert "boar" in d.message
    assert "wolf" in d.message
    assert "goblin_boss" not in d.message


def test_start_combat_unknown_monster_message_without_scope_lists_all(registry, cfg):
    _, d = start(registry, cfg, unknown_monster_request())
    assert "goblin_boss" in d.message


def test_start_combat_monster_outside_scope_is_accepted(registry, cfg):
    reg = scoped_registry(registry, ["wolf"])
    ctx, d = start(reg, cfg)
    assert isinstance(d, Decision)
    assert d.status == "accepted"
    assert ctx.bundle.session.active_combat is not None
