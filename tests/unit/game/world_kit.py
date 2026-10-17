# Помощники тестов роли world (этап 3, партия 4; контракт сбоя обновлён партией #22 ТС). Не
# фикстуры pytest, а функции. Импорты ai_dm.* для новых модулей -- внутри функций: пока кода нет,
# тесты падают по одному (red).
#
# КОНТРАКТ (STAGE3-PLAN A4, П4, Т-9..Т-11; TS-PLAN п.5). Где план не даёт имён, они выбраны здесь --
# это ТРЕБОВАНИЕ к реализации:
#   TurnRunner(..., world_adapter=None): адаптер роли world; None -> тот же, что у нарратора.
#     Запросы роли world: req.role == "world", набор инструментов tool_set("world").
#   Вход вызова world: messages[0].content[0].text -- JSON с ключом "candidates": список
#     {ref, kind: verdict|act, owner{id, name, motive, means}, condition_text, then}, порядок =
#     порядок world_sim.candidates (вердикты триггеров, вердикты секретов, затем act).
#   Инструменты (поле input): world_verdict {type, items: [{ref, holds, reason}]};
#     world_notice {type, text, visibility: visible|rumor|hidden, delay: none|day|week, refs};
#     npc_update получает location_id ("" = не менять) и then_ref ("" = нет);
#     skill_check/saving_throw получают actor (id NPC, "" = герой).
#   Журнал: записи world -- role "world", run_id "bnd-..." (общий на границу), turn_status
#     "committed" / "aborted".
#   Мягкий сбой world (refusal, invalid -- бюджет невалидных исчерпан, network): вызов
#     пропускается, граница завершается: метка отчёта "world_skipped",
#     вердикты не применяются, boundary_pending False, игроку строк нет.
#     Записи пропущенного вызова world в журнале -- aborted (вердикты не применены), записи
#     summarizer той же границы -- committed (ТБ #71, docs/plan-tb.md п.6).
#   Жёсткий сбой world (fatal, rounds): TurnResult.boundary_failed, bundle.session.boundary_pending
#     True, бандл как после автосейва закрытой сцены, меню 2.2. TurnResult.offscreen --
#     доставленные закадровые тексты.
#   Конфиг: app.world.max_calls_per_day (0 = выключено).
#   ai_dm.devtools.world_run.run_world(registry, cfg, pack_dir, *, days, seed, world_adapter,
#       saves_root, flags=None, mortality_per_day=None) -> WorldRun(bundle, journal, chronicle);
#     30 границ: advance_time day + end_scene синтетическим «нарратором» без модели; flags --
#     флаги мира на старте; mortality_per_day -- замена world.mortality_per_day (пресет
#     «Жестокий» из П5); пак грузится load_pack + new_world_from_pack.
#     main(argv) -> int: --pack DIR --days N --seed N --mock FILE.yaml [--out DIR] [--flag NAME].
import json
import sys
from pathlib import Path

from game_kit import (
    NOW,
    advance_call,
    end_scene_call,
    flag_call,
    scripted,
    settings,
    text_step,
    tools_step,
)

from ai_dm.llm.cost import CostLedger
from ai_dm.llm.journal import Journal
from ai_dm.llm.types import ChatResponse, Text, ToolCall, ToolResult, Usage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "world_sim"))
from world_sim_kit import MINI_DIR, mini_bundle  # noqa: E402, F401

BRANN = "trigger:brann:brann_trust"
OATH = "secret:aldric:oath"
GRAIL = "trigger:aldric:steal_grail"
MARA = "trigger:mara:mara_trust"


def verdict_call(items, call_id="wv-1"):
    # items: список (ref, holds)
    return {
        "id": call_id, "name": "world_verdict",
        "input": {
            "type": "world_verdict",
            "items": [{"ref": r, "holds": h, "reason": "тест"} for r, h in items],
        },
    }


def notice_call(text, visibility="visible", delay="none", refs=(), call_id="wn-1"):
    return {
        "id": call_id, "name": "world_notice",
        "input": {
            "type": "world_notice", "text": text, "visibility": visibility, "delay": delay,
            "refs": list(refs),
        },
    }


def npc_update_call(npc_id, then_ref="", call_id="nu-1", **fields):
    data = {
        "type": "npc_update", "npc_id": npc_id, "attitude_delta": 0, "status": "none",
        "cause": "none", "evidence_ref": "", "by": "", "text": "", "location_id": "",
        "then_ref": then_ref,
    }
    data.update(fields)
    return {"id": call_id, "name": "npc_update", "input": data}


def world_step(*calls):
    # вызов world целиком: вызовы инструментов, затем итоговый текст
    return [tools_step(*calls), text_step("Готово.")]


def add_mara_trigger(bundle):
    # третий NPC с нарративным триггером: brann, mara, aldric (секрет oath) -> три кандидата
    from ai_dm.state.triggers import Trigger

    bundle.world.npcs["mara"].opportunity.append(
        Trigger.model_validate(
            {
                "id": "mara_trust", "if": {"narrative": "Мара доверяет герою"},
                "then": "Мара помогает",
            }
        )
    )


def bundle_with_brann(registry, cfg, seed=1):
    # кандидаты: brann_trust (флаг met_brann + нарратив) и секрет oath (сцена в таверне)
    bundle = mini_bundle(registry, cfg, seed)
    bundle.world.flags["met_brann"] = True
    return bundle


def bundle_without_candidates(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.world.npcs["aldric"].secrets[1].narrative_ok = True
    return bundle


def make_world_rig(
    registry, cfg, tmp_path, narrator_steps, world_steps, *, bundle, max_calls_per_day=0,
    world_model=None,
):
    from ai_dm.game.turn import TurnRunner

    app = settings().app.model_copy(deep=True)
    app.world.max_calls_per_day = max_calls_per_day
    narrator = scripted(narrator_steps)
    world = world_steps if hasattr(world_steps, "complete") else scripted(world_steps)
    journal = Journal(tmp_path, bundle.world.world_id, app.journal)
    ledger = CostLedger(tmp_path, bundle.world.world_id)
    runner = TurnRunner(
        bundle, registry, cfg, app, narrator, saves_root=tmp_path, journal=journal,
        ledger=ledger, sleeper=lambda s: None, now=lambda: NOW, run_tag="t",
        world_adapter=world, world_model=world_model,
    )
    runner.new_summarizer_session = lambda: None
    return WorldRig(runner, narrator, world, journal)


class WorldRig:
    def __init__(self, runner, narrator, world, journal):
        self.runner = runner
        self.narrator = narrator
        self.world = world
        self.journal = journal

    def play(self, n=1):
        return [self.runner.play(f"ход {i}") for i in range(n)]

    def world_records(self):
        return [r for r in self.journal.read_records() if r["role"] == "world"]


def narrator_turns(*turns):
    # turns: списки вызовов; каждый ход = вызовы + рассказ
    steps = []
    for calls in turns:
        steps += [tools_step(*calls), text_step("Конец сцены.")]
    return steps


def end_turn(n=1, flag=None):
    calls = []
    if flag:
        calls.append(flag_call(flag, f"f{n}"))
    calls.append(end_scene_call(f"e{n}"))
    return calls


def day_turn(n=1):
    return [advance_call(f"a{n}", category="day"), end_scene_call(f"e{n}")]


def candidates_of(request):
    return json.loads(request.messages[0].content[0].text)["candidates"]


def candidate_refs(request):
    return [c["ref"] for c in candidates_of(request)]


class ReactiveWorld:
    # детерминированный world: вердикт по всем verdict-кандидатам запроса; Бранн доверяет один раз
    provider = "anthropic"
    model = "claude-sonnet-5-5"

    def __init__(self):
        self.requests = []
        self.trusted = False

    def info(self):
        from ai_dm.llm.adapter import AdapterInfo

        return AdapterInfo(provider=self.provider, model=self.model)

    def complete(self, request):
        self.requests.append(request.model_copy(deep=True))
        number = len(self.requests)
        answered = any(
            isinstance(b, ToolResult) for m in request.messages for b in m.content
        )
        items = []
        if not answered:
            for c in candidates_of(request):
                if c["kind"] != "verdict":
                    continue
                holds = c["ref"] == BRANN and not self.trusted
                self.trusted = self.trusted or holds
                items.append({"ref": c["ref"], "holds": holds, "reason": "мок"})
        if not items:
            content = [Text(text="Готово.")]
            stop = "end_turn"
        else:
            data = {"type": "world_verdict", "items": items}
            content = [ToolCall(id=f"rw-{number}", name="world_verdict", input=data)]
            stop = "tool_use"
        return ChatResponse(
            content=content, stop_reason=stop, usage=Usage(input=100, output=20),
            request_id=f"rw-{number}", model=request.model,
        )


def set_flag_call(name, then_ref="", call_id="sf-1"):
    return {
        "id": call_id, "name": "set_flag",
        "input": {"type": "set_flag", "name": name, "value": "true", "then_ref": then_ref},
    }
