# Сквозной тест E2 (stage2-audit): мок «как живая модель». В сценарии нет ни одного подсказанного
# id: модель берёт travel_to и ref из state-JSON запроса (locations / known_npcs), а id монстров --
# из блока мира в system. Сцена «Спускаюсь в подвал -> бой с Гракхом как ключевым NPC».
# Остальные режимы (классификация, выбор NPC, рассказ боя) отвечает ReactiveAdapter из game_kit.
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "game"))

from game_kit import (  # noqa: E402
    OPUS,
    SAVED_AT,
    ReactiveAdapter,
    attack_or_move_number,
    make_app,
    settings,
    state_of,
    tool_names,
)

from ai_dm.llm.types import ChatResponse, Text, ToolCall, ToolResult, Usage  # noqa: E402

SEED = 1  # К7д: с 7 Гракх не умирает (у goblin_boss тег disarmer -- другой расход бросков)
DESCEND = "Спускаюсь в подвал"
ALL_EXPLORE = {"advance_time", "start_combat"}


def tool_results_in(request):
    return [
        b for m in request.messages for b in m.content if isinstance(b, ToolResult)
    ]


def called_in(request):
    return {b.name for m in request.messages for b in m.content if isinstance(b, ToolCall)}


class LiveLikeAdapter:
    # explore-запросы: id берутся ТОЛЬКО из state-JSON (locations, known_npcs) и system[1]
    def __init__(self):
        self.inner = ReactiveAdapter(provider="anthropic", model=OPUS)
        self.requests = []
        self.picked = {}

    def info(self):
        return self.inner.info()

    def complete(self, request):
        self.requests.append(request.model_copy(deep=True))
        if not tool_names(request) >= ALL_EXPLORE:
            return self.inner.complete(request)
        state = state_of(request)
        called = called_in(request)
        if state["player_input"] != DESCEND or "start_combat" in called:
            return self.say("Гоблины бросаются на вас.", request)
        if "advance_time" not in called:
            cellar = [p for p in state["locations"] if "подвал" in p["name"].lower()][0]
            self.picked["travel_to"] = cellar["id"]
            return self.call(request, "advance_time", {
                "type": "advance_time", "category": "none", "travel_to": cellar["id"],
                "pace": "normal",
            })
        grakh = [n for n in state["known_npcs"] if n["name"] == "Гракх" and n["key"]][0]
        self.picked["grakh_ref"] = grakh["id"]
        monsters = json.loads(request.system[1].text)["monster_ids"]
        boss = [m for m in monsters if m.endswith("boss")][0]
        warrior = [m for m in monsters if m.endswith("warrior")][0]
        self.picked["boss"] = boss
        enemies = [
            {"ref": "goblin_1", "monster_id": warrior, "zone": "floor", "group": "goblins"},
            {"ref": grakh["id"], "monster_id": boss, "zone": "barrels", "group": "goblins"},
        ]
        return self.call(request, "start_combat", {
            "type": "start_combat", "hero_zone": "stairs", "initiated_by": "hero",
            "zones": [
                {"id": "stairs", "name": "Лестница", "adjacent": ["floor"]},
                {"id": "floor", "name": "Земляной пол", "adjacent": ["stairs", "barrels"]},
                {"id": "barrels", "name": "Бочки", "adjacent": ["floor"]},
            ],
            "enemies": enemies,
            "groups": [{"id": "goblins", "leader": grakh["id"], "intent": "kill"}],
        })

    def call(self, request, name, data):
        number = len(self.requests)
        return ChatResponse(
            content=[ToolCall(id=f"live-{number}-{name}", name=name, input=data)],
            stop_reason="tool_use", usage=Usage(input=100, output=20),
            request_id=f"live-{number}", model=request.model,
        )

    def say(self, text, request):
        return ChatResponse(
            content=[Text(text=text)], stop_reason="end_turn", usage=Usage(input=100, output=20),
            request_id=f"live-{len(self.requests)}", model=request.model,
        )


def live_app(registry, root):
    from slots_kit import WORLD_TEXT

    from ai_dm.game.starter import new_world

    bundle = new_world(
        registry, settings().rules, hero="arn", seed=SEED, world_id="vale-live",
        saved_at=SAVED_AT,
    )
    hero = bundle.heroes[0]
    hero.creature.hp_max = hero.creature.hp_current = 200
    adapter = LiveLikeAdapter()
    app = make_app(registry, root, adapter, bundle=bundle, world_text=WORLD_TEXT, model=OPUS)
    return app, adapter


def descend(registry, root):
    app, adapter = live_app(registry, root)
    reply = app.handle(DESCEND)
    return app, adapter, reply


def test_first_request_state_has_ids_the_model_needs(registry, tmp_path):
    app, adapter, _ = descend(registry, tmp_path)
    state = state_of(adapter.requests[0])
    assert "cellar" in [p["id"] for p in state["locations"]]
    assert "grakh" in [n["id"] for n in state["known_npcs"]]


def test_descend_turn_is_committed_without_invalid_ids(registry, tmp_path):
    app, adapter, reply = descend(registry, tmp_path)
    assert reply.turn.committed is True
    assert reply.turn.requests == ["advance_time", "start_combat"]


def test_model_took_travel_to_from_state_and_hero_is_in_cellar(registry, tmp_path):
    app, adapter, _ = descend(registry, tmp_path)
    assert adapter.picked["travel_to"] == "cellar"
    assert app.bundle.heroes[0].location_id == "cellar"


def test_grakh_is_a_key_npc_in_combat_by_ref_from_state(registry, tmp_path):
    app, adapter, _ = descend(registry, tmp_path)
    parts = {p.ref: p for p in app.bundle.session.active_combat.participants}
    assert adapter.picked["grakh_ref"] == "grakh"
    assert parts["grakh"].controller == "external"
    assert parts["goblin_1"].controller == "engine"


def test_no_tool_result_of_the_descend_turn_is_an_error(registry, tmp_path):
    app, adapter, _ = descend(registry, tmp_path)
    results = [r for request in adapter.requests for r in tool_results_in(request)]
    assert results
    assert not [r for r in results if r.is_error]


def test_scene_to_victory_with_grakh_dead(registry, tmp_path):
    app, adapter, _ = descend(registry, tmp_path)
    for _ in range(80):
        if app.bundle.session.active_combat is None:
            break
        reply = app.handle(str(attack_or_move_number(app.runner)))
        assert reply.turn.committed is True
    assert app.bundle.session.active_combat is None
    assert app.bundle.world.npcs["grakh"].status == "dead"
    assert app.bundle.heroes[0].sheet.xp > 0
