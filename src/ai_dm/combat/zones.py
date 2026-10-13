from ai_dm.rules.modifiers.base import Modifier

COVER_BONUS = {"cover_half": 2, "cover_three_quarters": 5}


def distance(zones, a_id, b_id) -> int:
    # число шагов по adjacent (BFS)
    by_id = {z.id: z for z in zones}
    if a_id not in by_id or b_id not in by_id:
        raise ValueError(f"неизвестная зона: {a_id!r} или {b_id!r}")
    steps = {a_id: 0}
    queue = [a_id]
    while queue:
        current = queue.pop(0)
        for other_id in by_id[current].adjacent:
            if other_id in by_id and other_id not in steps:
                steps[other_id] = steps[current] + 1
                queue.append(other_id)
    if b_id not in steps:
        raise ValueError(f"нет пути из {a_id!r} в {b_id!r}")
    return steps[b_id]


def range_band_ft(steps: int) -> int:
    # та же зона -- 10 фт, соседняя -- 30, через одну -- 60, дальше -- 120
    if steps == 0:
        return 10
    if steps == 1:
        return 30
    if steps == 2:
        return 60
    return 120


def cover_dc_bonus(zone) -> int:
    # больший из бонусов, не сумма
    bonus = 0
    for feature in zone.features:
        bonus = max(bonus, COVER_BONUS.get(feature.kind, 0))
    return bonus


def is_difficult(zone) -> bool:
    return any(f.kind == "difficult" for f in zone.features)


def hazards(zone) -> list:
    return [f for f in zone.features if f.kind == "hazard"]


def has_hiding_place(zone) -> bool:
    # укрытие (cover_*) или сильно затенённая/заслонённая зона
    return any(f.kind.startswith("cover_") or f.kind == "obscured" for f in zone.features)


class ElevationSource:
    # источник конвейера: атака сверху -- преимущество «высота», снизу -- помеха «ниже цели»
    # (домашнее правило); tags["height"] -- высота зоны бьющего минус высота зоны цели
    id = "elevation"

    def modifiers(self, request, registry) -> list[Modifier]:
        height = request.tags.get("height", 0)
        if request.kind != "attack" or not height:
            return []
        if height > 0:
            return [Modifier(source="elevation", label="высота", advantage=True)]
        return [Modifier(source="elevation", label="ниже цели", disadvantage=True)]


class CoverSource:
    # источник конвейера: укрытие (tags["cover"]) прибавляется к КД атаки и к спасброску Ловкости
    id = "cover"

    def modifiers(self, request, registry) -> list[Modifier]:
        bonus = request.tags.get("cover", 0)
        if not bonus:
            return []
        if request.kind == "attack":
            return [Modifier(source="cover", dc_bonus=bonus)]
        # спасбросок Ловкости: укрытие цели даёт бонус к самому броску
        if request.kind == "save" and request.ability == "dex":
            return [Modifier(source="cover", flat=bonus)]
        return []
