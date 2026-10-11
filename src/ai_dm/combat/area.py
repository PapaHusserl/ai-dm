def affected_zones(zones, origin_id, shape, size_ft, target_id) -> list[str]:
    # id накрытых зон в порядке списка zones
    by_id = {z.id: z for z in zones}
    if shape in ("sphere", "cube"):
        if size_ft <= 20:
            return [target_id]
        near = by_id[target_id].adjacent
        return [z.id for z in zones if z.id == target_id or z.id in near]
    if shape in ("cone", "line"):
        if target_id != origin_id and target_id not in by_id[origin_id].adjacent:
            raise ValueError(f"зона {target_id!r} вне досягаемости от {origin_id!r}")
        return [target_id]
    raise ValueError(f"неизвестная форма площади: {shape!r}")
