from ai_dm.content.models.common import ContentObject


class Species(ContentObject):
    speed_ft: int
    size: str = "medium"
    traits: list[str] = []
