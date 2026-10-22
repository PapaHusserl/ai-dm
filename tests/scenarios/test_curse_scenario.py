# Сквозной сценарий У0 П3 (docs/plan-u0.md, «Дополнение: проклятие»): «алтарь -> храм» на мок-LLM.
# Мир «Вейл», герой с 3000 мм, в его локации жрица Ильда с услугой uncurse_temple (2500 мм).
# Ход 1 «трогаю алтарь»: saving_throw (нереально высокая СЛ, провал) + curse по roll_ref этого хода:
#   * ход принят, запросы ["saving_throw", "curse"], у героя состояние cursed, деньги целы;
#   * в строках хода «Проклятие: ...»; /sheet показывает «Состояния: проклят».
# Ход 2 «иду в храм, плачу»: service buy uncurse_temple:
#   * деньги −2500, состояний нет, в строках «Проклятие снято»;
#   * curse без броска в другом ходу отклонён, герой не проклят.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "game"))

from game_kit import OPUS, SAVED_AT, make_app, settings  # noqa: E402
from slots_kit import WORLD_TEXT  # noqa: E402

from ai_dm.game.scene import hero_of  # noqa: E402
from ai_dm.game.starter import new_world  # noqa: E402
from ai_dm.llm.mock import ScriptedAdapter  # noqa: E402
from ai_dm.state.world import NPC  # noqa: E402

ALTAR = "Трогаю алтарь"
TEMPLE = "Иду в храм и плачу за снятие проклятия"
CAUSE = "костяной оберег на алтаре"


def save_call():
    return {
        "id": "st-1", "name": "saving_throw",
        "input": {"type": "saving_throw", "ability": "wis", "category": "nearly_impossible",
                  "stakes": "normal"},
    }


def curse_call(ref="r1"):
    return {
        "id": "cu-1", "name": "curse",
        "input": {"type": "curse", "failed_roll_ref": ref, "cause": CAUSE},
    }


def uncurse_call():
    return {
        "id": "sv-1", "name": "service",
        "input": {
            "type": "service", "npc_id": "ilda", "direction": "buy",
            "service_id": "uncurse_temple", "qty": 1,
        },
    }


def chapel_app(registry, root, turns, money=3000):
    bundle = new_world(
        registry, settings().rules, hero="arn", seed=7, world_id="vale-chapel", saved_at=SAVED_AT
    )
    hero = bundle.heroes[0]
    hero.money_cp = money
    bundle.world.npcs["ilda"] = NPC(
        id="ilda", name="Ильда", means=["жрица"], services=["uncurse_temple"],
        location_id=hero.location_id,
    )
    steps = []
    for calls, text in turns:
        steps += [{"tool_calls": calls}, {"text": text}]
    adapter = ScriptedAdapter(steps, provider="anthropic", model=OPUS)
    return make_app(registry, root, adapter, bundle=bundle, world_text=WORLD_TEXT, model=OPUS)


def touched_altar(registry, root, **kw):
    turns = [([save_call(), curse_call()], "Холод ползёт по руке."), ([uncurse_call()], "Обряд.")]
    app = chapel_app(registry, root, turns, **kw)
    return app, app.handle(ALTAR)


def conditions(app):
    return [c.id for c in hero_of(app.bundle).creature.conditions]


# ход 1: алтарь

def test_altar_turn_is_committed_with_save_and_curse(registry, tmp_path):
    _, reply = touched_altar(registry, tmp_path)
    assert reply.turn.committed is True
    assert reply.turn.requests == ["saving_throw", "curse"]


def test_hero_is_cursed_after_failed_save(registry, tmp_path):
    app, _ = touched_altar(registry, tmp_path)
    assert conditions(app) == ["cursed"]


def test_cursing_costs_no_money(registry, tmp_path):
    app, _ = touched_altar(registry, tmp_path)
    assert hero_of(app.bundle).money_cp == 3000


def test_altar_turn_log_has_curse_line(registry, tmp_path):
    _, reply = touched_altar(registry, tmp_path)
    assert f"Проклятие: {CAUSE}" in reply.turn.lines


def test_sheet_shows_curse_after_altar(registry, tmp_path):
    app, _ = touched_altar(registry, tmp_path)
    assert "Состояния: проклят" in app.handle("/sheet").lines


def test_curse_without_roll_in_the_turn_leaves_hero_free(registry, tmp_path):
    app = chapel_app(registry, tmp_path, [([curse_call("r1")], "Ничего не происходит.")])
    reply = app.handle(ALTAR)
    assert conditions(app) == []
    assert not [line for line in reply.turn.lines if line.startswith("Проклятие")]


# ход 2: храм

def test_temple_lifts_the_curse_for_2500(registry, tmp_path):
    app, _ = touched_altar(registry, tmp_path)
    reply = app.handle(TEMPLE)
    assert reply.turn.requests == ["service"]
    assert conditions(app) == []
    assert hero_of(app.bundle).money_cp == 500


def test_temple_turn_log_says_curse_lifted(registry, tmp_path):
    app, _ = touched_altar(registry, tmp_path)
    reply = app.handle(TEMPLE)
    assert len([line for line in reply.turn.lines if line.startswith("Проклятие снято")]) == 1


def test_sheet_has_no_conditions_line_after_temple(registry, tmp_path):
    app, _ = touched_altar(registry, tmp_path)
    app.handle(TEMPLE)
    assert not [line for line in app.handle("/sheet").lines if line.startswith("Состояния")]


def test_temple_without_enough_money_keeps_the_curse(registry, tmp_path):
    app, _ = touched_altar(registry, tmp_path, money=2000)
    reply = app.handle(TEMPLE)
    assert conditions(app) == ["cursed"]
    assert hero_of(app.bundle).money_cp == 2000
    assert not [line for line in reply.turn.lines if line.startswith("Проклятие снято")]


def test_temple_without_curse_takes_no_money(registry, tmp_path):
    app = chapel_app(registry, tmp_path, [([uncurse_call()], "Обряд не нужен.")])
    app.handle(TEMPLE)
    assert hero_of(app.bundle).money_cp == 3000
