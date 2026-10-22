# Сквозной сценарий У0 П2 (docs/plan-u0.md, п. 4 и «Тесты»): «снимаю комнату и ложусь» на мок-LLM.
# Мир «Вейл», в локации героя трактирщик Грок с услугой room_modest (50 мм), герой ранен.
# Мок-мастер за ход делает service buy + rest long и рассказывает:
#   * ход принят, запросы ["service", "rest"];
#   * деньги героя −50, HP полные, флаг ночлега после отдыха снят, часы ушли вперёд;
#   * в строках хода одна строка «Ночлег оплачен»;
#   * rest long без оплаты в том же мире отклонён: деньги и часы не тронуты.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "game"))

from game_kit import OPUS, SAVED_AT, make_app, settings  # noqa: E402
from slots_kit import WORLD_TEXT  # noqa: E402

from ai_dm.game.scene import hero_of  # noqa: E402
from ai_dm.game.starter import new_world  # noqa: E402
from ai_dm.llm.mock import ScriptedAdapter  # noqa: E402
from ai_dm.state.world import NPC  # noqa: E402

NIGHT = "Снимаю комнату и ложусь спать"


def buy_call():
    return {
        "id": "sv-1", "name": "service",
        "input": {
            "type": "service", "npc_id": "grok", "direction": "buy",
            "service_id": "room_modest", "qty": 1,
        },
    }


def rest_call():
    return {"id": "rs-1", "name": "rest", "input": {"type": "rest", "kind": "long"}}


def inn_story(registry, root, calls):
    bundle = new_world(
        registry, settings().rules, hero="arn", seed=7, world_id="vale-inn", saved_at=SAVED_AT
    )
    hero = bundle.heroes[0]
    hero.money_cp = 200
    hero.creature.hp_current = 1
    bundle.world.npcs["grok"] = NPC(
        id="grok", name="Грок", means=["трактир"], services=["room_modest"],
        location_id=hero.location_id,
    )
    steps = [{"tool_calls": calls}, {"text": "Грок кивает и ведёт тебя наверх."}]
    adapter = ScriptedAdapter(steps, provider="anthropic", model=OPUS)
    app = make_app(registry, root, adapter, bundle=bundle, world_text=WORLD_TEXT, model=OPUS)
    clock = bundle.world.clock.now_s
    reply = app.handle(NIGHT)
    return app, reply, clock


def test_night_turn_is_committed(registry, tmp_path):
    _, reply, _ = inn_story(registry, tmp_path, [buy_call(), rest_call()])
    assert reply.turn.committed is True
    assert reply.turn.requests == ["service", "rest"]


def test_room_costs_50(registry, tmp_path):
    app, _, _ = inn_story(registry, tmp_path, [buy_call(), rest_call()])
    assert hero_of(app.bundle).money_cp == 150


def test_hero_wakes_up_with_full_hp(registry, tmp_path):
    app, _, _ = inn_story(registry, tmp_path, [buy_call(), rest_call()])
    hero = hero_of(app.bundle)
    assert hero.creature.hp_current == hero.creature.hp_max


def test_clock_moves_and_flag_is_cleared(registry, tmp_path):
    app, _, before = inn_story(registry, tmp_path, [buy_call(), rest_call()])
    assert app.bundle.world.clock.now_s > before
    assert not [name for name in app.bundle.world.flags if name.startswith("lodging:")]


def test_log_has_one_lodging_line(registry, tmp_path):
    _, reply, _ = inn_story(registry, tmp_path, [buy_call(), rest_call()])
    lines = [line for line in reply.turn.lines if line.startswith("Ночлег оплачен")]
    assert len(lines) == 1


def test_rest_without_payment_is_refused(registry, tmp_path):
    app, _, before = inn_story(registry, tmp_path, [rest_call()])
    hero = hero_of(app.bundle)
    assert hero.money_cp == 200
    assert hero.creature.hp_current == 1
    assert app.bundle.world.clock.now_s == before
