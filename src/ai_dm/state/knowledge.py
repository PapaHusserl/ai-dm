from pydantic import BaseModel, ConfigDict

# журнал знаний героя; наполнение -- Ж3
KNOWLEDGE_KINDS = ("fact", "rumor", "secret", "person", "place")
KNOWLEDGE_SOURCES = ("seen", "told", "read", "deduced")


class KnowledgeEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # вид из KNOWLEDGE_KINDS
    kind: str
    # id NPC / локации / факта, к которому относится запись
    ref: str
    text: str
    # источник из KNOWLEDGE_SOURCES
    source: str
    # кто рассказал (id NPC); None -- узнал сам
    from_ref: str | None = None
    at_s: int
