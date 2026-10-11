from ai_dm.rules import divine
from ai_dm.rules.modifiers.base import Modifier


class DivineFavorSource:
    id = "divine_favor"

    def modifiers(self, request, registry) -> list[Modifier]:
        # +6: молитва даёт преимущество, -6: помеха; раз в день на первый критический бросок
        advantage, disadvantage = divine.hero_critical_modifier(request)
        result = []
        if advantage:
            result.append(Modifier(source="divine_favor", advantage=True))
        if disadvantage:
            result.append(Modifier(source="divine_curse", disadvantage=True))
        return result
