from ai_dm.content.models.common import Behavior


class Feat(Behavior):
    category: str
    # SRD: черту со свойством Repeatable можно взять повторно (Одарённый, Посвящённый в магию)
    repeatable: bool = False
