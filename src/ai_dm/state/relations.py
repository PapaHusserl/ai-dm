from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

NPC_EVENT_TEXT_MAX = 120

# открытые перечни -- str в моделях (расширение перечня не меняет схему сейва)
MEMORY_KINDS = (
    "spared", "saved", "helped", "gift", "promise", "betrayal", "insult", "threat", "theft",
    "harm", "kin_killed", "romance", "deal", "other", "friendship", "joke", "shared_deed", "battle",
)
# подписи видов для ленты (игроку не показываем сырой код)
# (порядок -- как в MEMORY_KINDS)
MEMORY_KIND_TITLES = dict(zip(MEMORY_KINDS, (
    "пощада", "спасение", "помощь", "подарок", "обещание", "предательство", "оскорбление",
    "угроза", "кража", "вред", "убийство близкого", "роман", "сделка", "другое", "дружба",
    "шутка", "общее дело", "бой плечом к плечу",
), strict=True))
# тёплые виды: на вытеснении вес не ниже warm_min_weight; одна запись вида на сцену
WARM_KINDS = ("romance", "friendship", "joke", "shared_deed", "battle")
GOAL_KINDS = ("revenge", "life_debt", "debt", "gratitude", "love", "rivalry")


class NpcEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # вид из MEMORY_KINDS
    kind: str
    turn_seq: int
    text: str = Field(max_length=NPC_EVENT_TEXT_MAX)


class NpcSceneMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scene_id: str
    at_s: int
    # насколько сцена изменила отношения NPC к герою (по модулю); вытесняется наименьший
    weight: int = Field(ge=0)
    events: list[NpcEvent] = Field(min_length=1)


class NpcGoal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # вид из GOAL_KINDS
    kind: str
    # id героя или NPC, на кого направлена цель
    target: str
    text: str = ""
    since_s: int
    status: Literal["active", "done", "dropped"] = "active"


class FamilyLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["parent", "spouse", "child"]
    ref: str
    ref_kind: Literal["npc", "hero"]
