# Ожидаемый API: ai_dm.protocol.apply.apply(ctx, request) -- см. контракт в protocol_kit.py.
# Мир и сцена (ТЗ 2.1, 2.3, 4.0, 4.1, 5.3, 8.1): set_flag, npc_create, location_create,
# npc_update, offer_choices, end_scene, end_chapter, unsupported_action.
#   * set_flag: префиксы npc_dead:, hero_dead:, visited:, combat_ended:, item_gained: заняты
#     (их ставит только движок по событиям) -> Invalid reserved_flag; прочие флаги ставятся;
#   * npc_create / location_create: нарушение уникальности (rules.uniqueness) -> Decision rejected
#     с signal_to_master, мир не меняется; имя локации в другом родителе -- можно;
#   * npc_update: attitude_delta урезается до +-cfg.attitude.step (10), сумма |delta| по NPC за
#     сцену -- до cfg.attitude.per_scene (20), всё через report_tag "limit-exceeded";
#     status dead|gone только с cause in {goal, hazard} И evidence_ref на бросок ЭТОГО хода,
#     иначе rejected, report_tag "invalid-death", NPC жив; принятая смерть -> событие npc_died,
#     флаг npc_dead:<id>, NPC.death.cause / by;
#     (ревью партии 2) условия смерти проверяются первыми, до мутаций; пустой запрос -> Invalid
#     empty_update; roll_ref тратится: один бросок -- одно смертельное последствие (damage deadly
#     или смерть NPC); у предела отношения +-100 лог и лимит сцены -- по фактическому изменению;
#   * offer_choices: 2-3 варианта (иначе Invalid choices_count), кладутся в session.offered_choices;
#   * end_scene: current_scene.closed_reason == "end_scene"; end_chapter: ctx.chapter_ended;
#   * unsupported_action: accepted + report_tag "missing-mechanic", метка в ctx.marks.
import pytest
from protocol_kit import ScriptedRng, dump, make_bundle, make_ctx, req

from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid

RESERVED = [
    "npc_dead:aldric", "hero_dead:hero", "visited:forest", "combat_ended:c1",
    "item_gained:crowbar",
]


# set_flag

def test_set_flag_sets_value(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("set_flag", name="met_aldric", value="true"))
    assert isinstance(d, Decision)
    assert d.status == "accepted"
    assert ctx.bundle.world.flags["met_aldric"] is True
    assert d.log


@pytest.mark.parametrize("value, stored", [("true", True), ("false", False), ("friend", "friend")])
def test_set_flag_converts_string_value(value, stored, registry, cfg):
    # value в схеме -- одна строка: "true"/"false" становятся bool, прочее остаётся текстом
    ctx = make_ctx(registry, cfg)
    apply(ctx, req("set_flag", name="quest_state", value=value))
    assert ctx.bundle.world.flags["quest_state"] == stored
    assert type(ctx.bundle.world.flags["quest_state"]) is type(stored)


def test_set_flag_overwrites(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, req("set_flag", name="mood", value="a"))
    apply(ctx, req("set_flag", name="mood", value="b"))
    assert ctx.bundle.world.flags["mood"] == "b"


@pytest.mark.parametrize("name", RESERVED)
def test_set_flag_reserved_prefix_is_invalid(name, registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, req("set_flag", name=name, value="true"))
    assert isinstance(d, Invalid)
    assert d.code == "reserved_flag"
    assert dump(ctx) == before


def test_set_flag_similar_but_not_reserved_prefix_is_ok(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("set_flag", name="npc_dead_rumor", value="true"))
    assert d.status == "accepted"


# npc_create

def new_npc(**kwargs):
    fields = {"id": "brana", "name": "Бранка", "means": ["кузница"], "named": True}
    fields.update(kwargs)
    return req("npc_create", **fields)


def test_npc_create_adds_npc(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, new_npc(motive="отомстить", key=False, location_id="vale"))
    assert d.status == "accepted"
    npc = ctx.bundle.world.npcs["brana"]
    assert npc.name == "Бранка"
    assert npc.named is True
    assert npc.motive == "отомстить"
    assert npc.means == ["кузница"]
    assert npc.location_id == "vale"
    assert npc.origin == "ai"
    assert d.log


def test_npc_create_named_defaults_to_false(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, new_npc(id="guard_7", name="Стражник", named=False))
    assert ctx.bundle.world.npcs["guard_7"].named is False


def test_npc_create_taken_named_name_is_rejected(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, new_npc(id="aldric_2", name="Олдрик"))
    assert isinstance(d, Decision)
    assert d.status == "rejected"
    assert d.signal_to_master
    assert "aldric_2" not in ctx.bundle.world.npcs
    assert dump(ctx) == before


def test_npc_create_name_clash_ignores_case(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, new_npc(id="aldric_2", name="  олдрик "))
    assert d.status == "rejected"


def test_npc_create_taken_id_is_rejected(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, new_npc(id="aldric", name="Совсем Другой"))
    assert d.status == "rejected"
    assert d.signal_to_master
    assert ctx.bundle.world.npcs["aldric"].name == "Олдрик"


def test_npc_create_hero_id_is_rejected(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, new_npc(id="hero", name="Совсем Другой"))
    assert d.status == "rejected"
    assert d.signal_to_master
    assert dump(ctx) == before


def test_npc_create_hero_name_is_rejected(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, new_npc(id="arn_2", name="Арн"))
    assert d.status == "rejected"
    assert d.signal_to_master
    assert dump(ctx) == before


def test_npc_create_unnamed_may_repeat_name(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, new_npc(id="guard_1", name="Стражник", named=False))
    d = apply(ctx, new_npc(id="guard_2", name="Стражник", named=False))
    assert d.status == "accepted"


def test_npc_create_rejection_is_not_a_limit_mark(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, new_npc(id="aldric_2", name="Олдрик"))
    assert "limit-exceeded" not in ctx.marks


# location_create

def new_location(**kwargs):
    fields = {"id": "cellar", "name": "Подвал", "parent_id": "vale_tavern"}
    fields.update(kwargs)
    return req("location_create", **fields)


def test_location_create_adds_location(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, new_location(
        description="сырой", connections=[{"to": "vale_tavern", "distance_m": 10}]
    ))
    assert d.status == "accepted"
    loc = ctx.bundle.world.locations["cellar"]
    assert loc.name == "Подвал"
    assert loc.parent_id == "vale_tavern"
    assert loc.description == "сырой"
    assert loc.connections[0].to == "vale_tavern"
    assert loc.connections[0].distance_m == 10
    assert loc.origin == "ai"
    assert d.log


def test_location_create_same_name_other_parent_is_accepted(registry, cfg):
    # «Таверна» есть в Вейле, вторая «Таверна» в Лесу -- можно (ТЗ 5.3)
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, new_location(id="forest_tavern", name="Таверна", parent_id="forest"))
    assert d.status == "accepted"
    assert "forest_tavern" in ctx.bundle.world.locations


def test_location_create_same_name_same_parent_is_rejected(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, new_location(id="vale_tavern_2", name="Таверна", parent_id="vale"))
    assert d.status == "rejected"
    assert d.signal_to_master
    assert dump(ctx) == before


def test_location_create_taken_id_is_rejected(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, new_location(id="forest", name="Другая Чаща", parent_id=""))
    assert d.status == "rejected"
    assert ctx.bundle.world.locations["forest"].name == "Лес"


# npc_update: attitude

def attitude(ctx, delta, npc_id="aldric"):
    return apply(ctx, req("npc_update", npc_id=npc_id, attitude_delta=delta))


def test_attitude_delta_within_step_is_accepted(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = attitude(ctx, 7)
    assert d.status == "accepted"
    assert ctx.bundle.world.npcs["aldric"].attitude == 7
    assert d.log


def test_attitude_negative_delta(registry, cfg):
    ctx = make_ctx(registry, cfg)
    attitude(ctx, -8)
    assert ctx.bundle.world.npcs["aldric"].attitude == -8


def test_attitude_plus_15_is_clamped_to_10(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = attitude(ctx, 15)
    assert d.status == "clamped"
    assert d.report_tag == "limit-exceeded"
    assert d.signal_to_master
    assert ctx.bundle.world.npcs["aldric"].attitude == 10
    assert ctx.marks == ["limit-exceeded"]


def test_attitude_minus_15_is_clamped_to_minus_10(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = attitude(ctx, -15)
    assert d.status == "clamped"
    assert ctx.bundle.world.npcs["aldric"].attitude == -10


def test_attitude_step_comes_from_config(registry, cfg):
    small = cfg.model_copy(deep=True)
    small.attitude.step = 3
    ctx = make_ctx(registry, small)
    d = attitude(ctx, 5)
    assert d.status == "clamped"
    assert ctx.bundle.world.npcs["aldric"].attitude == 3


def test_attitude_scene_total_is_clamped_to_20(registry, cfg):
    ctx = make_ctx(registry, cfg)
    first = attitude(ctx, 10)
    second = attitude(ctx, 10)
    third = attitude(ctx, 10)
    assert [first.status, second.status, third.status] == ["accepted", "accepted", "clamped"]
    assert third.report_tag == "limit-exceeded"
    assert ctx.bundle.world.npcs["aldric"].attitude == 20
    assert ctx.attitude_spent["aldric"] == 20


def test_attitude_scene_remainder_is_applied_partially(registry, cfg):
    ctx = make_ctx(registry, cfg)
    attitude(ctx, 10)
    attitude(ctx, 8)
    d = attitude(ctx, 10)
    assert d.status == "clamped"
    assert ctx.bundle.world.npcs["aldric"].attitude == 20


def test_attitude_scene_cap_is_per_npc(registry, cfg):
    ctx = make_ctx(registry, cfg)
    attitude(ctx, 10)
    attitude(ctx, 10)
    d = attitude(ctx, 10, npc_id="grakh")
    assert d.status == "accepted"
    assert ctx.bundle.world.npcs["grakh"].attitude == 10


def test_attitude_scene_cap_comes_from_config(registry, cfg):
    small = cfg.model_copy(deep=True)
    small.attitude.per_scene = 12
    ctx = make_ctx(registry, small)
    attitude(ctx, 10)
    d = attitude(ctx, 10)
    assert d.status == "clamped"
    assert ctx.bundle.world.npcs["aldric"].attitude == 12


def test_attitude_spent_is_kept_in_scene_between_contexts(registry, cfg):
    # накопитель живёт в сцене бандла, а не в контексте хода
    bundle = make_bundle(registry)
    attitude(make_ctx(registry, cfg, bundle=bundle), 10)
    attitude(make_ctx(registry, cfg, bundle=bundle), 10)
    d = attitude(make_ctx(registry, cfg, bundle=bundle), 10)
    assert d.status == "clamped"
    assert bundle.world.npcs["aldric"].attitude == 20


def test_npc_update_unknown_npc_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    d = attitude(ctx, 5, npc_id="nobody")
    assert isinstance(d, Invalid)
    assert d.code == "unknown_npc"
    assert dump(ctx) == before


# npc_update: смерть (4.1)

def kill(ctx, **kwargs):
    fields = {"npc_id": "aldric", "status": "dead"}
    fields.update(kwargs)
    return apply(ctx, req("npc_update", **fields))


def roll_ref(ctx):
    return apply(ctx, req("skill_check", skill="athletics", category="easy")).result["roll_ref"]


def assert_alive_and_invalid_death(ctx, d):
    assert isinstance(d, Decision)
    assert d.status == "rejected"
    assert d.report_tag == "invalid-death"
    assert d.signal_to_master
    assert ctx.bundle.world.npcs["aldric"].status == "alive"
    assert ctx.bundle.world.npcs["aldric"].death is None
    assert "npc_dead:aldric" not in ctx.bundle.world.flags
    assert "invalid-death" in ctx.marks


def test_death_without_cause_and_evidence_is_rejected(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert_alive_and_invalid_death(ctx, kill(ctx))


def test_death_without_evidence_is_rejected(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert_alive_and_invalid_death(ctx, kill(ctx, cause="goal"))


def test_death_without_cause_is_rejected(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1]))
    ref = roll_ref(ctx)
    assert_alive_and_invalid_death(ctx, kill(ctx, evidence_ref=ref))


@pytest.mark.parametrize("cause", ["chance", "old_age"])
def test_death_by_chance_or_old_age_is_rejected(cause, registry, cfg):
    # случайность и старость бросает только движок, мастер так убить не может
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1]))
    ref = roll_ref(ctx)
    assert_alive_and_invalid_death(ctx, kill(ctx, cause=cause, evidence_ref=ref))


def test_death_with_unknown_evidence_is_rejected(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert_alive_and_invalid_death(ctx, kill(ctx, cause="goal", evidence_ref="r42"))


def test_gone_without_cause_is_rejected_too(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = kill(ctx, status="gone")
    assert d.status == "rejected"
    assert d.report_tag == "invalid-death"
    assert ctx.bundle.world.npcs["aldric"].status == "alive"


def test_death_by_goal_with_evidence_is_accepted(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1]))
    ref = roll_ref(ctx)
    d = kill(ctx, cause="goal", evidence_ref=ref, by="grakh")
    assert d.status == "accepted"
    assert d.report_tag is None
    npc = ctx.bundle.world.npcs["aldric"]
    assert npc.status == "dead"
    assert npc.death.cause == "goal"
    assert npc.death.by == "grakh"
    assert ctx.bundle.world.flags["npc_dead:aldric"] is True
    assert "npc_died" in [e.type for e in ctx.events]
    assert d.log


def test_death_by_hazard_with_evidence_is_accepted(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1]))
    ref = apply(ctx, req("saving_throw", ability="dex", category="hard")).result["roll_ref"]
    d = kill(ctx, cause="hazard", evidence_ref=ref)
    assert d.status == "accepted"
    assert ctx.bundle.world.npcs["aldric"].death.cause == "hazard"


def test_gone_by_goal_with_evidence_is_accepted(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1]))
    ref = roll_ref(ctx)
    d = kill(ctx, status="gone", cause="goal", evidence_ref=ref)
    assert d.status == "accepted"
    assert ctx.bundle.world.npcs["aldric"].status == "gone"
    assert "npc_died" not in [e.type for e in ctx.events]


def test_killing_dead_npc_again_is_not_a_second_death(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1]))
    ref = roll_ref(ctx)
    kill(ctx, cause="goal", evidence_ref=ref)
    kill(ctx, cause="goal", evidence_ref=ref)
    assert [e.type for e in ctx.events].count("npc_died") == 1


def test_death_text_goes_to_death_record(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1]))
    ref = roll_ref(ctx)
    kill(ctx, cause="goal", evidence_ref=ref, text="упал с башни")
    assert ctx.bundle.world.npcs["aldric"].death.text == "упал с башни"


def test_death_without_text_has_empty_record_text(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1]))
    ref = roll_ref(ctx)
    kill(ctx, cause="goal", evidence_ref=ref)
    assert ctx.bundle.world.npcs["aldric"].death.text == ""


def test_death_result_carries_new_status(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1]))
    ref = roll_ref(ctx)
    assert kill(ctx, cause="goal", evidence_ref=ref).result == {"status": "dead"}


def test_gone_result_carries_new_status(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1]))
    ref = roll_ref(ctx)
    assert kill(ctx, status="gone", cause="goal", evidence_ref=ref).result == {"status": "gone"}


def test_killing_dead_npc_again_logs_nothing_changed(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1, 1]))
    kill(ctx, cause="goal", evidence_ref=roll_ref(ctx))
    again = kill(ctx, cause="goal", evidence_ref=roll_ref(ctx))
    assert again.log == ["Олдрик: уже мёртв, ничего не изменилось"]
    assert again.result == {"status": "dead"}


# offer_choices / end_scene / end_chapter / unsupported_action

@pytest.mark.parametrize("choices", [["Войти", "Уйти"], ["Войти", "Уйти", "Ждать"]])
def test_offer_choices_two_or_three(choices, registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("offer_choices", choices=choices))
    assert d.status == "accepted"
    assert ctx.bundle.session.offered_choices == choices


@pytest.mark.parametrize("choices", [[], ["Одно"], ["а", "б", "в", "г"]])
def test_offer_choices_wrong_count_is_invalid(choices, registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, req("offer_choices", choices=choices))
    assert isinstance(d, Invalid)
    assert d.code == "choices_count"
    assert dump(ctx) == before


def test_offer_choices_replaces_previous(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, req("offer_choices", choices=["а", "б"]))
    apply(ctx, req("offer_choices", choices=["в", "г", "д"]))
    assert ctx.bundle.session.offered_choices == ["в", "г", "д"]


def test_end_scene_marks_scene_closed(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("end_scene", summary="разговор окончен"))
    assert d.status == "accepted"
    assert ctx.bundle.session.current_scene.closed_reason == "end_scene"


def test_end_chapter_is_accepted(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("end_chapter", title="Глава 1: Таверна"))
    assert d.status == "accepted"


def test_unsupported_action_is_accepted_with_missing_mechanic(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("unsupported_action", description="приручить дракона"))
    assert d.status == "accepted"
    assert d.report_tag == "missing-mechanic"
    assert ctx.marks == ["missing-mechanic"]


def test_unsupported_action_changes_no_state(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    apply(ctx, req("unsupported_action", description="приручить дракона"))
    assert dump(ctx) == before


# B3: npc_update -- сначала условия смерти, до любых мутаций; пустой запрос -- Invalid

def test_combined_update_with_invalid_death_changes_nothing(registry, cfg):
    # attitude_delta=50 + status=dead + cause=chance: отказ до мутаций, отношение прежнее
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1]))
    ref = roll_ref(ctx)
    d = apply(ctx, req(
        "npc_update", npc_id="aldric", attitude_delta=50, status="dead", cause="chance",
        evidence_ref=ref,
    ))
    assert isinstance(d, Decision)
    assert d.status == "rejected"
    assert d.report_tag == "invalid-death"
    assert ctx.bundle.world.npcs["aldric"].attitude == 0
    assert ctx.bundle.world.npcs["aldric"].status == "alive"
    assert ctx.attitude_spent.get("aldric", 0) == 0
    assert "invalid-death" in ctx.marks


def test_combined_update_with_invalid_death_does_not_spend_scene_limit(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, req("npc_update", npc_id="aldric", attitude_delta=10, status="dead"))
    assert ctx.attitude_spent.get("aldric", 0) == 0
    assert ctx.bundle.world.npcs["aldric"].attitude == 0


def test_combined_update_with_valid_death_and_big_delta_keeps_both_marks(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1]))
    ref = roll_ref(ctx)
    d = apply(ctx, req(
        "npc_update", npc_id="aldric", attitude_delta=50, status="dead", cause="goal",
        evidence_ref=ref,
    ))
    npc = ctx.bundle.world.npcs["aldric"]
    assert npc.status == "dead"
    assert npc.attitude == 10
    assert d.status == "clamped"
    assert d.report_tag == "limit-exceeded"
    assert "limit-exceeded" in ctx.marks


def test_empty_npc_update_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, req("npc_update", npc_id="aldric"))
    assert isinstance(d, Invalid)
    assert d.code == "empty_update"
    assert dump(ctx) == before


def test_npc_update_with_only_neutral_values_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    d = apply(ctx, req("npc_update", npc_id="aldric", attitude_delta=0, evidence_ref="", by=""))
    assert isinstance(d, Invalid)
    assert d.code == "empty_update"


# D2: roll_ref тратится -- один проваленный бросок, одно смертельное последствие

def test_same_roll_cannot_kill_two_npcs(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1]))
    ref = roll_ref(ctx)
    first = kill(ctx, cause="goal", evidence_ref=ref)
    second = kill(ctx, npc_id="grakh", cause="goal", evidence_ref=ref)
    assert first.status == "accepted"
    assert isinstance(second, Decision)
    assert second.status == "rejected"
    assert second.report_tag == "invalid-death"
    assert ctx.bundle.world.npcs["grakh"].status == "alive"
    assert "npc_dead:grakh" not in ctx.bundle.world.flags


def test_two_rolls_can_kill_two_npcs(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1, 1]))
    first = kill(ctx, cause="goal", evidence_ref=roll_ref(ctx))
    second = kill(ctx, npc_id="grakh", cause="goal", evidence_ref=roll_ref(ctx))
    assert first.status == "accepted"
    assert second.status == "accepted"


def test_roll_spent_on_deadly_damage_cannot_kill_npc(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1], d10=[1, 1, 1, 1]))
    ref = roll_ref(ctx)
    hit = apply(ctx, req("damage", severity="deadly", damage_type="fire", failed_roll_ref=ref))
    assert hit.status == "accepted"
    d = kill(ctx, cause="goal", evidence_ref=ref)
    assert d.status == "rejected"
    assert d.report_tag == "invalid-death"
    assert ctx.bundle.world.npcs["aldric"].status == "alive"


def test_roll_spent_on_npc_death_cannot_back_deadly_damage(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1], d10=[1, 1]))
    ref = roll_ref(ctx)
    assert kill(ctx, cause="goal", evidence_ref=ref).status == "accepted"
    d = apply(ctx, req("damage", severity="deadly", damage_type="fire", failed_roll_ref=ref))
    assert d.status == "clamped"
    assert d.report_tag == "limit-exceeded"


def test_rejected_death_does_not_spend_the_roll(registry, cfg):
    # отказ (cause=chance) бросок не тратит: потом тот же ref годится для goal
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1]))
    ref = roll_ref(ctx)
    assert kill(ctx, cause="chance", evidence_ref=ref).status == "rejected"
    assert kill(ctx, cause="goal", evidence_ref=ref).status == "accepted"


# D3: отношение у предела +-100 -- лог и лимит сцены по фактическому изменению

def test_attitude_near_cap_logs_and_spends_actual_change(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.npcs["aldric"].attitude = 95
    d = attitude(ctx, 10)
    assert ctx.bundle.world.npcs["aldric"].attitude == 100
    assert ctx.attitude_spent["aldric"] == 5
    assert "+5 (" in d.log[-1]
    assert "+10 (" not in d.log[-1]


def test_attitude_near_negative_cap_logs_and_spends_actual_change(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.npcs["aldric"].attitude = -95
    d = attitude(ctx, -10)
    assert ctx.bundle.world.npcs["aldric"].attitude == -100
    assert ctx.attitude_spent["aldric"] == 5
    assert "-5 (" in d.log[-1]
    assert "-10 (" not in d.log[-1]


def test_attitude_at_cap_spends_nothing_from_scene_limit(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.npcs["aldric"].attitude = 100
    attitude(ctx, 10)
    assert ctx.bundle.world.npcs["aldric"].attitude == 100
    assert ctx.attitude_spent.get("aldric", 0) == 0


def test_attitude_at_cap_does_not_eat_limit_for_later_opposite_change(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.world.npcs["aldric"].attitude = 100
    attitude(ctx, 10)
    attitude(ctx, 10)
    d = attitude(ctx, -10)
    assert d.status == "accepted"
    assert ctx.bundle.world.npcs["aldric"].attitude == 90
