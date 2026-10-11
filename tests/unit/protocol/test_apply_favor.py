# Ожидаемый API (STAGE3-PLAN A8, П6а, ТЗ 4.2): apply(ctx, req("favor_change", target, god_id,
#   delta, reason)).
#   target -- "hero" или id NPC; reason -- текст (строка, может быть пустой).
#   Нарратор (mode explore): только target="hero", NPC -> Invalid. Роль world (mode="world"): NPC.
#   Лимиты: шаг +-2 за запрос ([favor] step), +-3 к одному богу за сцену (scene.favor_spent[god],
#   сумма модулей) -- урезание: Decision clamped, report_tag "limit-exceeded", signal_to_master.
#   Шкала -10..10. Бог из hero.divine.frozen -- rejected (долг не выполнен), благосклонность не
#     меняется.
#   Соперники бога автоматически не меняются (решение G1а). Неизвестный бог/NPC -- Invalid.
#   Благосклонность -9 -- богу добавляется триггер с then == "послать слугу" (kills_hero False).
import pytest
from protocol_kit import dump, make_ctx, req

from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.state.world import God


def make_favor_ctx(registry, cfg, **kwargs):
    ctx = make_ctx(registry, cfg, **kwargs)
    ctx.bundle.world.pantheon["selune"] = God(id="selune", name="Селунэ", rivals=["morrah"])
    ctx.bundle.world.pantheon["morrah"] = God(id="morrah", name="Моррах", rivals=["selune"])
    return ctx


def favor_req(delta, target="hero", god="selune", reason="поступок"):
    return req("favor_change", target=target, god_id=god, delta=delta, reason=reason)


def test_hero_favor_change_is_accepted(registry, cfg):
    ctx = make_favor_ctx(registry, cfg)
    d = apply(ctx, favor_req(1))
    assert isinstance(d, Decision)
    assert d.status == "accepted"
    assert ctx.hero.favor["selune"] == 1


def test_negative_change_lowers_favor(registry, cfg):
    ctx = make_favor_ctx(registry, cfg)
    apply(ctx, favor_req(-2))
    assert ctx.hero.favor["selune"] == -2


def test_step_is_clamped_to_two(registry, cfg):
    ctx = make_favor_ctx(registry, cfg)
    d = apply(ctx, favor_req(5))
    assert d.status == "clamped"
    assert d.report_tag == "limit-exceeded"
    assert d.signal_to_master
    assert ctx.hero.favor["selune"] == 2


def test_negative_step_is_clamped_to_minus_two(registry, cfg):
    ctx = make_favor_ctx(registry, cfg)
    d = apply(ctx, favor_req(-4))
    assert d.status == "clamped"
    assert ctx.hero.favor["selune"] == -2


def test_scene_limit_is_three_per_god(registry, cfg):
    ctx = make_favor_ctx(registry, cfg)
    apply(ctx, favor_req(2))
    d = apply(ctx, favor_req(2))
    assert d.status == "clamped"
    assert d.report_tag == "limit-exceeded"
    assert ctx.hero.favor["selune"] == 3
    assert ctx.scene.favor_spent["selune"] == 3


def test_scene_limit_blocks_further_change(registry, cfg):
    ctx = make_favor_ctx(registry, cfg)
    apply(ctx, favor_req(2))
    apply(ctx, favor_req(1))
    d = apply(ctx, favor_req(1))
    assert d.status in ("clamped", "rejected")
    assert d.signal_to_master
    assert ctx.hero.favor["selune"] == 3


def test_scene_limit_counts_negative_changes_too(registry, cfg):
    ctx = make_favor_ctx(registry, cfg)
    apply(ctx, favor_req(2))
    apply(ctx, favor_req(-2))
    apply(ctx, favor_req(-2))
    assert ctx.scene.favor_spent["selune"] == 3


def test_scene_limit_is_per_god(registry, cfg):
    ctx = make_favor_ctx(registry, cfg)
    apply(ctx, favor_req(2, god="selune"))
    apply(ctx, favor_req(1, god="selune"))
    d = apply(ctx, favor_req(2, god="morrah"))
    assert d.status == "accepted"
    assert ctx.hero.favor["morrah"] == 2


def test_favor_does_not_go_above_ten(registry, cfg):
    ctx = make_favor_ctx(registry, cfg)
    ctx.hero.favor["selune"] = 10
    apply(ctx, favor_req(1))
    assert ctx.hero.favor["selune"] == 10


def test_favor_does_not_go_below_minus_ten(registry, cfg):
    ctx = make_favor_ctx(registry, cfg)
    ctx.hero.favor["selune"] = -10
    apply(ctx, favor_req(-1))
    assert ctx.hero.favor["selune"] == -10


def test_rival_favor_is_not_changed_automatically(registry, cfg):
    ctx = make_favor_ctx(registry, cfg)
    ctx.hero.favor["morrah"] = 4
    apply(ctx, favor_req(2, god="selune"))
    assert ctx.hero.favor["morrah"] == 4


def test_rival_favor_changes_by_explicit_second_request(registry, cfg):
    ctx = make_favor_ctx(registry, cfg)
    apply(ctx, favor_req(2, god="selune"))
    apply(ctx, favor_req(-1, god="morrah"))
    assert ctx.hero.favor["morrah"] == -1


def test_frozen_god_is_rejected(registry, cfg):
    ctx = make_favor_ctx(registry, cfg)
    ctx.hero.favor["selune"] = 9
    ctx.hero.divine.frozen = ["selune"]
    d = apply(ctx, favor_req(1))
    assert isinstance(d, Decision)
    assert d.status == "rejected"
    assert d.signal_to_master
    assert ctx.hero.favor["selune"] == 9


def test_frozen_god_does_not_freeze_other_gods(registry, cfg):
    ctx = make_favor_ctx(registry, cfg)
    ctx.hero.divine.frozen = ["selune"]
    d = apply(ctx, favor_req(1, god="morrah"))
    assert d.status == "accepted"


def test_narrator_with_npc_target_is_invalid(registry, cfg):
    ctx = make_favor_ctx(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, favor_req(1, target="aldric"))
    assert isinstance(d, Invalid)
    assert dump(ctx) == before


def test_unknown_god_is_invalid(registry, cfg):
    ctx = make_favor_ctx(registry, cfg)
    before = dump(ctx)
    d = apply(ctx, favor_req(1, god="nobody"))
    assert isinstance(d, Invalid)
    assert dump(ctx) == before


def test_world_role_changes_npc_favor(registry, cfg):
    ctx = make_favor_ctx(registry, cfg, mode="world")
    d = apply(ctx, favor_req(1, target="aldric"))
    assert isinstance(d, Decision)
    assert d.status == "accepted"
    assert ctx.bundle.world.npcs["aldric"].favor["selune"] == 1


def test_world_role_npc_step_is_clamped(registry, cfg):
    ctx = make_favor_ctx(registry, cfg, mode="world")
    d = apply(ctx, favor_req(5, target="aldric"))
    assert d.status == "clamped"
    assert ctx.bundle.world.npcs["aldric"].favor["selune"] == 2


def test_world_role_npc_scene_limit(registry, cfg):
    ctx = make_favor_ctx(registry, cfg, mode="world")
    apply(ctx, favor_req(2, target="aldric"))
    d = apply(ctx, favor_req(2, target="aldric"))
    assert d.status == "clamped"
    assert ctx.bundle.world.npcs["aldric"].favor["selune"] == 3


def test_world_role_unknown_npc_is_invalid(registry, cfg):
    ctx = make_favor_ctx(registry, cfg, mode="world")
    d = apply(ctx, favor_req(1, target="nobody"))
    assert isinstance(d, Invalid)


def test_reaching_minus_nine_adds_servant_trigger_to_god(registry, cfg):
    ctx = make_favor_ctx(registry, cfg)
    ctx.hero.favor["selune"] = -8
    apply(ctx, favor_req(-1))
    triggers = ctx.bundle.world.pantheon["selune"].opportunity
    servants = [t for t in triggers if t.then == "послать слугу"]
    assert len(servants) == 1
    assert servants[0].kills_hero is False


def test_servant_trigger_is_not_added_above_minus_nine(registry, cfg):
    ctx = make_favor_ctx(registry, cfg)
    ctx.hero.favor["selune"] = -7
    apply(ctx, favor_req(-1))
    assert ctx.bundle.world.pantheon["selune"].opportunity == []


def test_servant_trigger_is_not_duplicated(registry, cfg):
    ctx = make_favor_ctx(registry, cfg)
    ctx.hero.favor["selune"] = -8
    apply(ctx, favor_req(-1))
    apply(ctx, favor_req(-1))
    triggers = ctx.bundle.world.pantheon["selune"].opportunity
    assert len([t for t in triggers if t.then == "послать слугу"]) == 1


@pytest.mark.parametrize("field", ["target", "god_id", "delta", "reason"])
def test_favor_change_has_required_field(field):
    data = {"type": "favor_change", "target": "hero", "god_id": "selune", "delta": 1, "reason": "x"}
    del data[field]
    from pydantic import ValidationError

    from ai_dm.protocol.requests import parse_request

    with pytest.raises(ValidationError):
        parse_request(data)
