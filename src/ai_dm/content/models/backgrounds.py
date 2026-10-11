from ai_dm.content.models.common import Ability, ContentObject, Skill


class Background(ContentObject):
    abilities: list[Ability]
    skills: list[Skill]
    tool: str
    feat: str
    # вариант A: набор предметов (повтор id = количество) и золото
    equipment: list[str] = []
    gold_cp: int = 0
    # вариант B: вместо набора предметов золото (50 зм)
    gold_option_cp: int = 5000
