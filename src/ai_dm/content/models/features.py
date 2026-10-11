from typing import Literal

from ai_dm.content.models.common import Behavior


class Feature(Behavior):
    # умение с выбором: id умений-вариантов (Добыча охотника)
    options: list[str] = []
    # когда работает умение (для /abilities)
    activation: Literal["passive", "action", "bonus_action", "reaction"] = "passive"
