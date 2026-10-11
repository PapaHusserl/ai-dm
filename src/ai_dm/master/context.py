import math
from collections.abc import Callable

from pydantic import BaseModel, ConfigDict

from ai_dm.llm.types import ChatRequest
from ai_dm.state.memory import Memory, SceneSummary
from ai_dm.state.scene import TurnRecord

# порядок вытеснения (ТЗ 11)
STAGES = ("turns", "scenes", "npcs", "locations")


class Candidates(BaseModel):
    # что можно урезать; списки в порядке «первым выкидывать -- первым»
    turns: list[TurnRecord] = []
    # ходы, которые до ступени 2 не вытесняются
    floor: int = 0
    scenes: list[SceneSummary] = []
    npcs: list[str] = []
    locations: list[str] = []
    # неустранимое: в запросе всегда
    fixed_npcs: list[str] = []
    fixed_locations: list[str] = []


class ContextPlan(BaseModel):
    model_config = ConfigDict(frozen=True)
    budget: int
    cap: int
    estimate: int
    turns: list[TurnRecord]
    scene_summaries: list[SceneSummary]
    npc_ids: list[str]
    location_ids: list[str]
    dropped: list[tuple[str, str]]
    raised: bool
    overflow: bool

    def meta(self) -> dict:
        return {
            "budget": self.budget,
            "cap": self.cap,
            "estimate": self.estimate,
            "dropped": [[stage, item] for stage, item in self.dropped],
            "raised": self.raised,
            "overflow": self.overflow,
        }


# app_cfg без аннотации: master.context не импортирует config (сторож)
def window_budget(app_cfg, model: str) -> int:
    return app_cfg.context_windows[model] * 80 // 100


def budget(app_cfg, model: str) -> int:
    return min(window_budget(app_cfg, model), app_cfg.master.context_cap)


def estimate_tokens(text: str, chars_per_token: float) -> int:
    return math.ceil(len(text) / chars_per_token)


def request_tokens(req: ChatRequest, chars_per_token: float) -> int:
    return estimate_tokens(req.model_dump_json(), chars_per_token)


def recent_window(memory: Memory, n: int) -> list[TurnRecord]:
    if n <= 0:
        return []
    return memory.recent_turns[-n:]


def _has_candidates(left, stage) -> bool:
    if stage == "turns":
        return len(left.turns) > left.floor
    return len(getattr(left, stage)) > 0


def _item_id(stage, item) -> str:
    if stage == "turns":
        return str(item.turn_seq)
    if stage == "scenes":
        return item.id
    return item


def plan(
    candidates: Candidates,
    render: Callable[[Candidates], ChatRequest],
    *,
    cap: int,
    window80: int,
    cpt: float,
) -> ContextPlan:
    left = candidates.model_copy(deep=True)
    dropped = []
    estimate = request_tokens(render(left), cpt)
    for stage in STAGES:
        while estimate > cap and _has_candidates(left, stage):
            # старейший (первый в списке) уходит первым; пересчёт целиком, не разницей
            item = getattr(left, stage).pop(0)
            dropped.append((stage, _item_id(stage, item)))
            estimate = request_tokens(render(left), cpt)
    raised = estimate > cap
    return ContextPlan(
        budget=window80 if raised else cap,
        cap=cap,
        estimate=estimate,
        turns=left.turns,
        scene_summaries=left.scenes,
        npc_ids=left.fixed_npcs + left.npcs,
        location_ids=left.fixed_locations + left.locations,
        dropped=dropped,
        raised=raised,
        overflow=raised,
    )
