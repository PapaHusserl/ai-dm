# М0 П5 (docs/plan-m0.md, «Тесты» П5, решения 10, 45, 136-139): npc_update ставит и снимает
# состояния bound и unconscious у NPC вне боя.
# Ожидаемый API (имя поля и значений -- контракт: docs/plan-m0.md, «Умолчания» п. 28, «Контракт
# поля»):
#   NpcUpdate.condition: Literal["bound", "unbound", "unconscious", "conscious", "keep"],
#       "keep" -- нейтраль («не менять»); в WorldNpcUpdate поля нет;
#   постановка: ensure_creature (NPC без creature получает его), затем AppliedCondition без срока
#       со своим источником (не "0_hp", не "pending"); повтор -- вторая запись не вешается;
#   снятие -- только записей со своим источником; «без сознания» от 0 HP и чужие источники
#       не трогаются; снятие отсутствующего -- accepted, ничего не меняется (creature не заводится);
#   мёртвый или ушедший NPC -> Invalid npc_not_alive до любых изменений запроса;
#   бросок не нужен (Р60 а = 1, evidence_ref не требуется);
#   строки ленты (Р61 = 1): «<имя>: связан», «: без сознания», «: развязан», «: приходит в себя»;
#   повтор и снятие отсутствующего -- без строки; имя -- по npc_label.
import pytest
from protocol_kit import dump, make_bundle, make_ctx, req

from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.protocol.requests import NpcUpdate
from ai_dm.protocol.schema import tool_defs
from ai_dm.state.creature import AppliedCondition, CreatureState
from ai_dm.state.world import NPC

FIELD = "condition"
LABEL = "Воин-гоблин 1"


@pytest.fixture
def ctx(registry, cfg):
    bundle = make_bundle(registry)
    bundle.world.npcs["bran"] = NPC(
        id="bran", name="Бран", named=True, means=["сторожит"], location_id="vale"
    )
    return make_ctx(registry, cfg, bundle=bundle)


def bran(ctx):
    return ctx.bundle.world.npcs["bran"]


def change(ctx, value, npc_id="bran", **fields):
    return apply(ctx, req("npc_update", npc_id=npc_id, **{FIELD: value}, **fields))


def ids_of(npc):
    return [c.id for c in npc.creature.conditions]


def survivor_ctx(registry, cfg):
    bundle = make_bundle(registry)
    bundle.world.npcs["goblin_warrior_t1_1"] = NPC(
        id="goblin_warrior_t1_1", name=LABEL, named=False, means=[LABEL], origin="engine",
        location_id="vale", combat={"monster_id": "goblin_warrior", "label": LABEL},
    )
    return make_ctx(registry, cfg, bundle=bundle)


# запрос и схема

def test_condition_neutral_is_keep():
    assert NpcUpdate.NEUTRAL[FIELD] == "keep"


def test_condition_absent_in_parsed_request_is_none():
    assert req("npc_update", npc_id="bran", attitude_delta=1).condition is None


def test_tool_schema_has_required_condition_field():
    schema = tool_defs(["npc_update"])[0]["input_schema"]
    assert FIELD in schema["properties"]
    assert FIELD in schema["required"]


def test_world_role_npc_update_has_no_condition_field():
    schema = tool_defs(["npc_update"], "world")[0]["input_schema"]
    assert FIELD not in schema["properties"]


# постановка

def test_bound_gives_creature_to_npc_without_one(ctx):
    decision = change(ctx, "bound")
    assert isinstance(decision, Decision)
    assert decision.status == "accepted"
    assert (bran(ctx).creature.hp_current, bran(ctx).creature.hp_max) == (1, 1)


def test_bound_is_one_record_without_expiry(ctx):
    change(ctx, "bound")
    records = bran(ctx).creature.conditions
    assert [c.id for c in records] == ["bound"]
    assert records[0].source == "npc_update"
    assert records[0].expires is None


def test_bound_twice_stays_one_record(ctx):
    change(ctx, "bound")
    again = change(ctx, "bound")
    assert again.status == "accepted"
    assert ids_of(bran(ctx)) == ["bound"]


def test_bound_does_not_touch_hp_of_npc_with_creature(ctx):
    bran(ctx).creature = CreatureState(hp_current=5, hp_max=27)
    change(ctx, "bound")
    assert (bran(ctx).creature.hp_current, bran(ctx).creature.hp_max) == (5, 27)
    assert ids_of(bran(ctx)) == ["bound"]


def test_bound_takes_hp_from_monster_of_npc_combat(ctx):
    bran(ctx).combat = {"monster_id": "goblin_boss"}
    change(ctx, "bound")
    assert (bran(ctx).creature.hp_current, bran(ctx).creature.hp_max) == (21, 21)


def test_unconscious_source_is_npc_update(ctx):
    change(ctx, "unconscious")
    records = bran(ctx).creature.conditions
    assert [c.id for c in records] == ["unconscious"]
    assert records[0].source == "npc_update"
    assert records[0].expires is None


def test_unconscious_and_bound_live_together(ctx):
    change(ctx, "bound")
    change(ctx, "unconscious")
    assert sorted(ids_of(bran(ctx))) == ["bound", "unconscious"]


def test_condition_needs_no_evidence_roll(ctx):
    decision = change(ctx, "bound", evidence_ref="")
    assert isinstance(decision, Decision)
    assert decision.status == "accepted"


def test_condition_with_attitude_in_one_request_applies_both(ctx):
    decision = change(ctx, "bound", attitude_delta=3)
    assert decision.status == "accepted"
    assert bran(ctx).attitude == 3
    assert ids_of(bran(ctx)) == ["bound"]


def test_condition_applies_to_npc_outside_hero_location(ctx):
    bran(ctx).location_id = "forest"
    assert change(ctx, "bound").status == "accepted"
    assert ids_of(bran(ctx)) == ["bound"]


# снятие

def test_unbound_removes_bound(ctx):
    change(ctx, "bound")
    change(ctx, "unbound")
    assert ids_of(bran(ctx)) == []


def test_conscious_removes_unconscious(ctx):
    change(ctx, "unconscious")
    change(ctx, "conscious")
    assert ids_of(bran(ctx)) == []


def test_unbound_keeps_unconscious(ctx):
    change(ctx, "bound")
    change(ctx, "unconscious")
    change(ctx, "unbound")
    assert ids_of(bran(ctx)) == ["unconscious"]


def test_conscious_does_not_remove_unconscious_from_zero_hp(ctx):
    bran(ctx).creature = CreatureState(
        hp_current=0, hp_max=10, conditions=[AppliedCondition(id="unconscious", source="0_hp")]
    )
    before = dump(ctx)
    decision = change(ctx, "conscious")
    assert decision.status == "accepted"
    assert dump(ctx) == before


def test_unbound_does_not_remove_bound_of_another_source(ctx):
    bran(ctx).creature = CreatureState(
        hp_current=5, hp_max=5, conditions=[AppliedCondition(id="bound", source="spell")]
    )
    before = dump(ctx)
    decision = change(ctx, "unbound")
    assert decision.status == "accepted"
    assert dump(ctx) == before


def test_removing_absent_condition_changes_nothing(ctx):
    before = dump(ctx)
    decision = change(ctx, "unbound")
    assert isinstance(decision, Decision)
    assert decision.status == "accepted"
    assert dump(ctx) == before


def test_removing_absent_condition_does_not_give_creature(ctx):
    change(ctx, "conscious")
    assert bran(ctx).creature is None


def test_condition_only_request_is_not_empty_update(ctx):
    result = change(ctx, "unbound")
    assert not isinstance(result, Invalid)


# мёртвый и ушедший

@pytest.mark.parametrize("status", ["dead", "gone"])
@pytest.mark.parametrize("value", ["bound", "unbound", "unconscious", "conscious"])
def test_not_alive_npc_is_invalid_and_unchanged(ctx, status, value):
    bran(ctx).status = status
    before = dump(ctx)
    result = change(ctx, value)
    assert isinstance(result, Invalid)
    assert result.code == "npc_not_alive"
    assert dump(ctx) == before


def test_not_alive_npc_does_not_get_attitude_from_same_request(ctx):
    bran(ctx).status = "dead"
    before = dump(ctx)
    result = change(ctx, "bound", attitude_delta=5)
    assert isinstance(result, Invalid)
    assert dump(ctx) == before


# живёт в сейве, сцене и часах

def test_bound_survives_save_and_load(ctx):
    change(ctx, "bound")
    restored = type(ctx.bundle).model_validate_json(ctx.bundle.model_dump_json())
    assert [c.id for c in restored.world.npcs["bran"].creature.conditions] == ["bound"]


def test_bound_survives_scene_change(ctx, cfg):
    from ai_dm.game.scene import close_scene

    change(ctx, "bound")
    close_scene(ctx.bundle, "end_scene", cfg)
    assert ids_of(bran(ctx)) == ["bound"]


def test_bound_survives_clock_shift_by_a_day(ctx):
    from ai_dm.rules.creatures import purge_expired

    change(ctx, "bound")
    ctx.bundle.world.clock.now_s += 86400
    purge_expired(ctx.bundle)
    assert ids_of(bran(ctx)) == ["bound"]


def test_unconscious_survives_clock_shift_by_a_day(ctx):
    from ai_dm.rules.creatures import purge_expired

    change(ctx, "unconscious")
    ctx.bundle.world.clock.now_s += 86400
    purge_expired(ctx.bundle)
    assert ids_of(bran(ctx)) == ["unconscious"]


# строки ленты (Р61 = 1)

@pytest.mark.parametrize("value, line", [
    ("bound", "Бран: связан"),
    ("unconscious", "Бран: без сознания"),
])
def test_setting_logs_one_line(ctx, value, line):
    assert change(ctx, value).log == [line]


def test_unbound_logs_line(ctx):
    change(ctx, "bound")
    assert change(ctx, "unbound").log == ["Бран: развязан"]


def test_conscious_logs_line(ctx):
    change(ctx, "unconscious")
    assert change(ctx, "conscious").log == ["Бран: приходит в себя"]


def test_repeated_setting_has_no_line(ctx):
    change(ctx, "bound")
    assert change(ctx, "bound").log == []


def test_removing_absent_condition_has_no_line(ctx):
    assert change(ctx, "unbound").log == []


def test_unconscious_from_zero_hp_removal_has_no_line(ctx):
    bran(ctx).creature = CreatureState(
        hp_current=0, hp_max=10, conditions=[AppliedCondition(id="unconscious", source="0_hp")]
    )
    assert change(ctx, "conscious").log == []


def test_survivor_line_uses_label_not_real_name(registry, cfg):
    ctx = survivor_ctx(registry, cfg)
    npc = ctx.bundle.world.npcs["goblin_warrior_t1_1"]
    npc.name, npc.named, npc.known_name = "Мурк", True, None
    result = change(ctx, "bound", npc_id="goblin_warrior_t1_1")
    assert result.log == [f"{LABEL}: связан"]
    assert "Мурк" not in "".join(result.log)
