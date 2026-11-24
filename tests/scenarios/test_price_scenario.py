# Сквозной сценарий шага 265 П2 (docs/plan-265.md, «Тесты»): цена провала вне боя на мок-LLM.
# Ход «лезу по стене»: skill_check в позиции risky (нереально высокая СЛ, провал).
#   * цена названа (damage с failed_roll_ref этого броска) -- ход принят, у героя меньше HP;
#   * цены нет, рассказчик трижды отвечает текстом -- ход не принят, HP целы;
#   * провал в controlled -- цены не требуется, ход принят.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "game"))

from game_kit import OPUS, SAVED_AT, make_app, settings  # noqa: E402
from slots_kit import WORLD_TEXT  # noqa: E402

from ai_dm.game.scene import hero_of  # noqa: E402
from ai_dm.game.starter import new_world  # noqa: E402
from ai_dm.llm.mock import ScriptedAdapter  # noqa: E402

CLIMB = "Лезу по стене"
FALL = "Ты срываешься со стены."


def check_call(position):
    return {
        "id": "ck-1", "name": "skill_check",
        "input": {
            "type": "skill_check", "skill": "athletics", "category": "nearly_impossible",
            "position": position,
        },
    }


def damage_call():
    return {
        "id": "dm-1", "name": "damage",
        "input": {
            "type": "damage", "severity": "dangerous", "damage_type": "bludgeoning",
            "failed_roll_ref": "r1",
        },
    }


def climb_app(registry, root, steps):
    bundle = new_world(
        registry, settings().rules, hero="arn", seed=7, world_id="vale-wall", saved_at=SAVED_AT
    )
    adapter = ScriptedAdapter(steps, provider="anthropic", model=OPUS)
    return make_app(registry, root, adapter, bundle=bundle, world_text=WORLD_TEXT, model=OPUS)


def hp(app):
    return hero_of(app.bundle).creature.hp_current


def test_risky_fail_with_price_is_committed_and_hurts(registry, tmp_path):
    steps = [{"tool_calls": [check_call("risky"), damage_call()]}, {"text": FALL}]
    app = climb_app(registry, tmp_path, steps)
    before = hp(app)
    reply = app.handle(CLIMB)
    assert reply.turn.committed is True
    assert reply.turn.requests == ["skill_check", "damage"]
    assert hp(app) < before


def test_risky_fail_without_price_is_not_committed(registry, tmp_path):
    steps = [{"tool_calls": [check_call("risky")]}] + [{"text": FALL}] * 3
    app = climb_app(registry, tmp_path, steps)
    before = hp(app)
    reply = app.handle(CLIMB)
    assert reply.turn.committed is False
    assert hp(app) == before


def test_risky_fail_with_price_given_after_a_reminder_is_committed(registry, tmp_path):
    steps = [
        {"tool_calls": [check_call("risky")]}, {"text": FALL},
        {"tool_calls": [damage_call()]}, {"text": FALL},
    ]
    app = climb_app(registry, tmp_path, steps)
    reply = app.handle(CLIMB)
    assert reply.turn.committed is True
    assert reply.turn.requests == ["skill_check", "damage"]


def test_controlled_fail_needs_no_price(registry, tmp_path):
    steps = [{"tool_calls": [check_call("controlled")]}, {"text": FALL}]
    app = climb_app(registry, tmp_path, steps)
    before = hp(app)
    reply = app.handle(CLIMB)
    assert reply.turn.committed is True
    assert hp(app) == before
