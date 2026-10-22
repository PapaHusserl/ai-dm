# Сквозной сценарий У1 П2 (docs/plan-u1.md, П2 п. 4): платная компания и порог романа на мок-LLM.
# Мир «Вейл», в локации героя Лира (услуга companion_common, 100 мм, отношение 40).
# Ход 1: service buy -> флаг paid_company:<герой>:lira и событие deal в памяти Лиры.
# Ход 2: npc_update memory_kind romance при отношении 40 -> в памяти deal, не romance.
# Ход 3: отношение 90 (правка бандла между ходами), та же просьба -> romance.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "game"))

from game_kit import OPUS, SAVED_AT, make_app, settings  # noqa: E402
from slots_kit import WORLD_TEXT  # noqa: E402

from ai_dm.game.scene import hero_of  # noqa: E402
from ai_dm.game.starter import new_world  # noqa: E402
from ai_dm.llm.mock import ScriptedAdapter  # noqa: E402
from ai_dm.state.world import NPC  # noqa: E402


def buy_call():
    return {
        "id": "sv-1", "name": "service",
        "input": {
            "type": "service", "npc_id": "lira", "direction": "buy",
            "service_id": "companion_common", "qty": 1,
        },
    }


def romance_call(call_id):
    return {
        "id": call_id, "name": "npc_update",
        "input": {
            "type": "npc_update", "npc_id": "lira",
            "memory_kind": "romance", "memory_text": "осталась до утра",
        },
    }


def story(registry, root):
    bundle = new_world(
        registry, settings().rules, hero="arn", seed=7, world_id="vale-inn", saved_at=SAVED_AT
    )
    bundle.heroes[0].money_cp = 1000
    bundle.world.npcs["lira"] = NPC(
        id="lira", name="Лира", named=True, means=["компания"], services=["companion_common"],
        location_id=bundle.heroes[0].location_id, attitude=40,
    )
    steps = [
        {"tool_calls": [buy_call()]}, {"text": "Лира улыбается и уводит тебя."},
        {"tool_calls": [romance_call("rm-1")]}, {"text": "Утро было тихим."},
        {"tool_calls": [romance_call("rm-2")]}, {"text": "Она осталась."},
    ]
    adapter = ScriptedAdapter(steps, provider="anthropic", model=OPUS)
    app = make_app(registry, root, adapter, bundle=bundle, world_text=WORLD_TEXT, model=OPUS)
    return app


def lira(app):
    return app.bundle.world.npcs["lira"]


def kinds(app):
    return [e.kind for m in lira(app).memory for e in m.events]


def test_purchase_sets_flag_and_writes_deal(registry, tmp_path):
    app = story(registry, tmp_path)
    reply = app.handle("Беру компанию на час")
    assert reply.turn.committed is True
    assert reply.turn.requests == ["service"]
    assert app.bundle.world.flags[f"paid_company:{hero_of(app.bundle).id}:lira"] is True
    assert kinds(app) == ["deal"]
    assert hero_of(app.bundle).money_cp == 900


def test_romance_at_40_after_payment_becomes_deal(registry, tmp_path):
    app = story(registry, tmp_path)
    app.handle("Беру компанию на час")
    reply = app.handle("Прошу её остаться до утра")
    assert reply.turn.requests == ["npc_update"]
    assert "romance" not in kinds(app)
    assert kinds(app) == ["deal"]


def test_romance_at_90_after_payment_is_romance(registry, tmp_path):
    app = story(registry, tmp_path)
    app.handle("Беру компанию на час")
    app.handle("Прошу её остаться до утра")
    lira(app).attitude = 90
    app.handle("Остаёмся вместе")
    assert kinds(app) == ["deal", "romance"]
