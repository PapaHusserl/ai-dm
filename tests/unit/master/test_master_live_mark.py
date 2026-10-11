# Живой прогон Дракона (docs/decisions/stage3-live-mark-option.md, B2/B3, раздел T):
# в combat_narrate нет unsupported_action; «метка на X и атака зажигательной» -- два шага
# одного player_action без unsupported (мок-модель отвечает двумя шагами по списку вариантов).
import sys
from pathlib import Path

from master_kit import combat_ctx, make_session, scripted, text_step, tools_step

from ai_dm.protocol.apply import apply
from ai_dm.protocol.schema import tool_set

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "combat"))

from test_mark_options_position import dragon_engine  # noqa: E402

TEXT = "метка охотника на гоблине лучнике и атака луком с зажигательной стрелой"
MARK = "cast:hunters_mark:1:goblin_2"
SHOOT = "attack:longbow:goblin_2"


def test_narrate_set_has_no_unsupported_action():
    assert "unsupported_action" not in [d["name"] for d in tool_set("combat_narrate")]


def test_classify_set_still_has_unsupported_action():
    assert "unsupported_action" in [d["name"] for d in tool_set("combat_classify")]


def test_mark_and_shot_phrase_is_classified_into_two_steps(tmp_path, registry, cfg):
    engine = dragon_engine(registry, cfg)
    options = [{"id": o.id, "label": o.label, "cost": o.cost}
               for o in engine.available_actions("hero")]
    assert MARK in [o["id"] for o in options]
    assert SHOOT in [o["id"] for o in options]
    ctx = combat_ctx(registry, cfg, "combat_classify", combat_options=options)
    call = {"id": "pa-1", "name": "player_action",
            "input": {"type": "player_action", "steps": [MARK, SHOOT]}}
    plans = []

    def execute(ctx, request):
        outcome = apply(ctx, request)
        if request.type == "player_action" and outcome.status != "rejected":
            plans.append(request)
        return outcome

    session, _, _, _ = make_session(scripted([tools_step(call), text_step("Готово.")]), tmp_path)
    result = session.run(ctx, TEXT, execute, "combat_classify")
    assert plans[-1].steps == [MARK, SHOOT]
    assert not plans[-1].unsupported
    assert "missing-mechanic" not in result.report_tags
