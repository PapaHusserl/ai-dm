# Ожидаемый API: ai_dm.protocol.apply.apply, HANDLERS -- см. контракт в protocol_kit.py.
# Скрытые запросы (STAGE2-PLAN A2): модели и тесты есть, мастеру на этапе 2 не показываются
# (этапы 3, 8) -- вызов -> Invalid("not_available_on_stage"), состояние и rng не меняются.
# npc_action вне режима NPC -> Invalid (подробнее -- test_apply_combat.py).
import pytest
from protocol_kit import dump, make_ctx, req

from ai_dm.protocol.apply import HANDLERS, apply
from ai_dm.protocol.decision import Invalid
from ai_dm.protocol.requests import HIDDEN_TYPES, VISIBLE_TYPES

HIDDEN = {
    "afterlife_action": {"kind": "short"},
}


def test_hidden_examples_cover_all_hidden_types():
    assert sorted(HIDDEN) == sorted(HIDDEN_TYPES)


@pytest.mark.parametrize("type_name", sorted(HIDDEN))
def test_hidden_request_is_invalid_not_available_on_stage(type_name, registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    draws = ctx.rng.draws
    d = apply(ctx, req(type_name, **HIDDEN[type_name]))
    assert isinstance(d, Invalid)
    assert d.code == "not_available_on_stage"
    assert d.message
    assert dump(ctx) == before
    assert ctx.rng.draws == draws
    assert ctx.marks == []
    assert ctx.events == []


def test_handlers_table_has_all_visible_types(registry, cfg):
    for name in VISIBLE_TYPES:
        assert name in HANDLERS, name


def test_handlers_table_has_no_hidden_types():
    for name in HIDDEN_TYPES:
        assert name not in HANDLERS, name


def test_npc_action_outside_npc_mode_is_invalid(registry, cfg):
    d = apply(make_ctx(registry, cfg), req("npc_action", choice="end_turn"))
    assert isinstance(d, Invalid)


def test_there_is_no_heal_handler():
    assert not [name for name in HANDLERS if "heal" in name]
