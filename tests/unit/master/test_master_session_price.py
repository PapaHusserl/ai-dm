# Шаг 265, П2 (docs/plan-265.md, «Тесты» 9-12, 20): MasterSession не принимает ход после провала
# в позиции risky / desperate без цены. Заметка модели называет roll_ref; финал без цены и ранний
# выход через offer_choices не завершают ход; третий финал без цены -- TurnFailed("invalid").
# MasterSession.price_note(ctx, mode) -> текст заметки или None (роль narrator, режим explore).
import pytest
from master_kit import ScriptedRng, make_ctx, make_session, scripted, text_step, tools_step

from ai_dm.master.session import TurnFailed
from ai_dm.protocol.apply import apply

RISKY = "risky"


def check_call(position=RISKY, call_id="c1", category="very_hard"):
    return {
        "id": call_id, "name": "skill_check",
        "input": {
            "type": "skill_check", "skill": "athletics", "category": category,
            "position": position,
        },
    }


def damage_call(ref="r1", severity="dangerous", call_id="d1"):
    return {
        "id": call_id, "name": "damage",
        "input": {
            "type": "damage", "severity": severity, "damage_type": "fire",
            "failed_roll_ref": ref,
        },
    }


def choices_call(call_id="o1"):
    return {
        "id": call_id, "name": "offer_choices",
        "input": {"type": "offer_choices", "choices": ["Бежать", "Драться"]},
    }


def go(steps, tmp_path, registry, cfg, d20=(1,), mode="explore", **kw):
    adapter = scripted(steps)
    session, _, _, _ = make_session(adapter, tmp_path, **kw)
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=list(d20), d10=[3] * 10), mode=mode)
    result = session.run(ctx, "Лезу.", apply, mode)
    return adapter, result, ctx


def last_user_text(request):
    # весь текст последнего сообщения запроса (tool_result и Text-блоки)
    parts = []
    for block in request.messages[-1].content:
        parts.append(getattr(block, "text", None) or str(getattr(block, "content", "")))
    return "\n".join(parts)


# 9: провал без цены -- заметка, после цены ход принят

def test_final_text_after_risky_fail_without_price_is_not_accepted(tmp_path, registry, cfg):
    steps = [
        tools_step(check_call()), text_step("Ты сорвался."), tools_step(damage_call()),
        text_step("Ты сорвался и ушибся."),
    ]
    adapter, _, _ = go(steps, tmp_path, registry, cfg)
    assert len(adapter.requests) == 4


def test_note_after_unpaid_fail_names_the_roll_ref(tmp_path, registry, cfg):
    steps = [
        tools_step(check_call()), text_step("Ты сорвался."), tools_step(damage_call()),
        text_step("Ты сорвался и ушибся."),
    ]
    adapter, _, _ = go(steps, tmp_path, registry, cfg)
    assert "r1" in last_user_text(adapter.requests[2])


def test_turn_is_accepted_after_damage_with_the_failed_roll_ref(tmp_path, registry, cfg):
    steps = [
        tools_step(check_call()), text_step("Ты сорвался."), tools_step(damage_call()),
        text_step("Ты сорвался и ушибся."),
    ]
    _, result, _ = go(steps, tmp_path, registry, cfg)
    assert result.narration == "Ты сорвался и ушибся."
    assert result.accepted >= {"skill_check", "damage"}


def test_text_in_the_same_round_as_the_fail_does_not_pay(tmp_path, registry, cfg):
    steps = [
        tools_step(check_call(), text="Ты срываешься."), text_step("Ушибся."),
        tools_step(damage_call()), text_step("Конец."),
    ]
    adapter, _, _ = go(steps, tmp_path, registry, cfg)
    assert len(adapter.requests) == 4


def test_desperate_fail_without_price_is_not_accepted(tmp_path, registry, cfg):
    steps = [
        tools_step(check_call("desperate")), text_step("Провал."),
        tools_step(damage_call(severity="deadly")), text_step("Конец."),
    ]
    adapter, _, _ = go(steps, tmp_path, registry, cfg)
    assert len(adapter.requests) == 4


def test_curse_with_the_ref_pays_the_price(tmp_path, registry, cfg):
    curse = {
        "id": "k1", "name": "curse",
        "input": {"type": "curse", "failed_roll_ref": "r1", "cause": "оберег"},
    }
    steps = [tools_step(check_call()), tools_step(curse), text_step("Тебя накрыло проклятие.")]
    adapter, result, _ = go(steps, tmp_path, registry, cfg)
    assert len(adapter.requests) == 3
    assert result.narration == "Тебя накрыло проклятие."


def test_start_combat_pays_the_price(tmp_path, registry, cfg):
    from protocol_kit import combat_request

    body = combat_request().model_dump(exclude_none=True)
    combat = {"id": "s1", "name": "start_combat", "input": body}
    steps = [tools_step(check_call()), tools_step(combat), text_step("Из тьмы выскочили гоблины.")]
    adapter, result, _ = go(steps, tmp_path, registry, cfg)
    assert len(adapter.requests) == 3
    assert result.narration == "Из тьмы выскочили гоблины."


# 10: три финала без цены -- TurnFailed("invalid")

def test_three_finals_without_price_fail_the_turn_as_invalid(tmp_path, registry, cfg):
    steps = [tools_step(check_call())] + [text_step("Ты сорвался.")] * 3
    with pytest.raises(TurnFailed) as info:
        go(steps, tmp_path, registry, cfg)
    assert info.value.reason == "invalid"
    assert str(info.value) == "Модель не смогла дать корректный ответ."


def test_two_finals_without_price_then_damage_is_still_accepted(tmp_path, registry, cfg):
    steps = [tools_step(check_call())] + [text_step("Ты сорвался.")] * 2 + [
        tools_step(damage_call()), text_step("Ушибся."),
    ]
    _, result, _ = go(steps, tmp_path, registry, cfg)
    assert result.narration == "Ушибся."


# 11: ранний выход через offer_choices не завершает ход

def test_offer_choices_round_with_text_does_not_end_the_unpaid_turn(tmp_path, registry, cfg):
    steps = [
        tools_step(check_call()), tools_step(choices_call(), text="Ты сорвался. Что дальше?"),
        tools_step(damage_call()), text_step("Ушибся."),
    ]
    adapter, _, _ = go(steps, tmp_path, registry, cfg)
    assert len(adapter.requests) == 4
    assert "r1" in last_user_text(adapter.requests[2])


def test_three_offer_choices_exits_without_price_fail_the_turn_as_invalid(
    tmp_path, registry, cfg
):
    exit_step = tools_step(choices_call(), text="Ты сорвался. Что дальше?")
    steps = [tools_step(check_call()), exit_step, exit_step, exit_step]
    with pytest.raises(TurnFailed) as info:
        go(steps, tmp_path, registry, cfg)
    assert info.value.reason == "invalid"


def test_two_offer_choices_exits_without_price_then_damage_is_accepted(tmp_path, registry, cfg):
    exit_step = tools_step(choices_call(), text="Ты сорвался. Что дальше?")
    steps = [
        tools_step(check_call()), exit_step, exit_step, tools_step(damage_call()),
        text_step("Ушибся."),
    ]
    _, result, _ = go(steps, tmp_path, registry, cfg)
    assert result.narration.endswith("Ушибся.")
    assert result.invalid_count == 2


# 12: цены нет -- ход принимается сразу

@pytest.mark.parametrize(
    ("call", "d20"),
    [
        (check_call("risky", category="very_easy"), [20]),
        (check_call("desperate", category="very_easy"), [20]),
        (check_call("controlled"), [1]),
        (check_call("controlled", category="very_easy"), [20]),
    ],
)
def test_turn_without_unpaid_fail_is_accepted_at_once(tmp_path, registry, cfg, call, d20):
    adapter, result, _ = go(
        [tools_step(call), text_step("Всё прошло.")], tmp_path, registry, cfg, d20=d20
    )
    assert len(adapter.requests) == 2
    assert result.narration == "Всё прошло."


def test_fail_rescued_by_inspiration_needs_no_price(tmp_path, registry, cfg):
    adapter = scripted([tools_step(check_call(category="medium")), text_step("Повезло.")])
    session, _, _, _ = make_session(adapter, tmp_path)
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1, 20]))
    ctx.hero.heroic_inspiration = True
    result = session.run(ctx, "Лезу.", apply, "explore")
    assert len(adapter.requests) == 2
    assert result.narration == "Повезло."


def test_turn_without_any_check_is_accepted_at_once(tmp_path, registry, cfg):
    adapter, result, _ = go([text_step("Тихо.")], tmp_path, registry, cfg)
    assert len(adapter.requests) == 1
    assert result.narration == "Тихо."


# price_note

def unpaid_ctx(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1]))
    apply(
        ctx,
        make_request("skill_check", skill="athletics", category="very_hard", position=RISKY),
    )
    return ctx


def make_request(type_name, **fields):
    from protocol_kit import req

    return req(type_name, **fields)


def test_price_note_names_the_unpaid_roll_ref(tmp_path, registry, cfg):
    session, _, _, _ = make_session(scripted([]), tmp_path)
    note = session.price_note(unpaid_ctx(registry, cfg), "explore")
    assert isinstance(note, str)
    assert "r1" in note


def test_price_note_names_the_position_of_the_roll(tmp_path, registry, cfg):
    session, _, _, _ = make_session(scripted([]), tmp_path)
    note = session.price_note(unpaid_ctx(registry, cfg), "explore")
    assert "(risky)" in note


def test_price_note_ends_with_describe_consequence(tmp_path, registry, cfg):
    session, _, _, _ = make_session(scripted([]), tmp_path)
    note = session.price_note(unpaid_ctx(registry, cfg), "explore")
    assert note.endswith("потом опиши последствие.")


def test_price_note_names_the_tools_that_pay(tmp_path, registry, cfg):
    session, _, _, _ = make_session(scripted([]), tmp_path)
    note = session.price_note(unpaid_ctx(registry, cfg), "explore")
    for name in ("damage", "take_item", "curse", "delayed_condition", "start_combat"):
        assert name in note


def test_price_note_is_none_without_unpaid_fail(tmp_path, registry, cfg):
    session, _, _, _ = make_session(scripted([]), tmp_path)
    assert session.price_note(make_ctx(registry, cfg), "explore") is None


def test_price_note_is_none_once_the_fail_is_paid(tmp_path, registry, cfg):
    session, _, _, _ = make_session(scripted([]), tmp_path)
    ctx = unpaid_ctx(registry, cfg)
    ctx.rng.queues["d10"] = [3] * 10
    apply(ctx, make_request("damage", severity="dangerous", damage_type="fire",
                            failed_roll_ref="r1"))
    assert session.price_note(ctx, "explore") is None


def test_price_note_names_the_second_fail_when_one_is_paid(tmp_path, registry, cfg):
    session, _, _, _ = make_session(scripted([]), tmp_path)
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1, 1], d10=[3] * 10))
    for position in ("risky", "desperate"):
        apply(
            ctx,
            make_request("skill_check", skill="athletics", category="very_hard",
                         position=position),
        )
    apply(ctx, make_request("damage", severity="dangerous", damage_type="fire",
                            failed_roll_ref="r1"))
    note = session.price_note(ctx, "explore")
    assert "r2" in note
    assert "r1" not in note


# 20: другие режимы и роли -- заметки нет

@pytest.mark.parametrize(
    "mode",
    ["combat_classify", "combat_narrate", "world", "summarize_scene", "summarize_chapter",
     "summarize_game"],
)
def test_price_note_is_none_outside_explore(tmp_path, registry, cfg, mode):
    session, _, _, _ = make_session(scripted([]), tmp_path)
    ctx = unpaid_ctx(registry, cfg)
    ctx.mode = mode
    assert session.price_note(ctx, mode) is None


@pytest.mark.parametrize("role", ["world", "summarizer"])
def test_price_note_is_none_for_other_roles(tmp_path, registry, cfg, role):
    session, _, _, _ = make_session(scripted([]), tmp_path, role=role)
    assert session.price_note(unpaid_ctx(registry, cfg), "explore") is None
