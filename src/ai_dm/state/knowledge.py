from pydantic import BaseModel, ConfigDict

# журнал знаний героя (Ж3); перечни открыты -- поля модели str
KNOWLEDGE_KINDS = ("npc", "location", "faction", "god", "creature", "situation")
# seen -- видел сам; told -- рассказал NPC (from_ref); rumor -- слух; read -- прочитал;
# deduced -- понял сам или узнал по ходу дела
KNOWLEDGE_SOURCES = ("seen", "told", "rumor", "read", "deduced")
# предел текста записи рассказчика
KNOWLEDGE_TEXT_MAX = 160


class KnowledgeEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # вид из KNOWLEDGE_KINDS
    kind: str
    # npc/location/faction/god -- id сущности мира; creature -- id монстра реестра;
    # situation -- слаг латиницей от рассказчика
    ref: str
    text: str
    # источник из KNOWLEDGE_SOURCES
    source: str
    # кто рассказал (id NPC); None -- узнал сам
    from_ref: str | None = None
    at_s: int
