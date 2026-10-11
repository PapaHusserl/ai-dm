import re
import textwrap

from ai_dm.combat.stealth import hidden_condition

WIDTH = 80

GAP = 3
MIN_BOX = 22
MAX_BOX = 36
MAX_ZONES_BOXES = 8
LEGEND = "● ты  ◆ союзник  ○ спутник  ✕ враг  † упал"
FEATURE_MARKS = {
    "cover_half": "укр.½",
    "cover_three_quarters": "укр.¾",
    "obscured": "темно",
    "dark": "темно",
    "difficult": "труднопрох.",
    "hazard": "опасно",
}
# хвост строки участника, который нельзя обрезать: HP (и пометка «скрыт»)
HP_TAIL = re.compile(r" \d+/\d+(?: \(скрыт\))?$")


def wrap_block(text, width, first, rest):
    return textwrap.wrap(text, width, initial_indent=first, subsequent_indent=rest)


def zone_marks(zone):
    marks = []
    if zone.elevation > 0:
        marks.append(f"▲{zone.elevation}")
    if zone.elevation < 0:
        marks.append(f"▼{-zone.elevation}")
    for feature in zone.features:
        mark = FEATURE_MARKS.get(feature.kind)
        if mark and mark not in marks:
            marks.append(mark)
    if zone.exit:
        marks.append("выход")
    return " ".join(marks)


def part_name(state, world, hero, ref):
    # как engine.name: одинаковые имена различаются номером по порядку участников
    if ref == hero.id:
        return hero.name
    part = [p for p in state.participants if p.ref == ref][0]
    if part.name == "":
        npc = world.npcs.get(ref)
        return ref if npc is None else npc.name
    same = [p.ref for p in state.participants if p.name == part.name and p.ref != hero.id]
    if len(same) > 1:
        return f"{part.name} {same.index(ref) + 1}"
    return part.name


def part_hp(world, part, hero):
    if part.ref == hero.id:
        creature = hero.creature
    elif part.creature is not None:
        creature = part.creature
    else:
        creature = world.npcs[part.ref].creature
    return f"{creature.hp_current}/{creature.hp_max}", creature


def members(state, world, hero, zone_id):
    lines = []
    for part in state.participants:
        if part.zone_id != zone_id or part.status == "fled":
            continue
        name = part_name(state, world, hero, part.ref)
        hp, creature = part_hp(world, part, hero)
        if part.status in ("down", "dead"):
            lines.append(f"† {name}")
        elif part.status == "surrendered":
            lines.append(f"✕ {name} {hp} (сдался)")
        elif part.ref == hero.id:
            text = f"● {name} {hp}"
            if hidden_condition(creature) is not None:
                text += " (скрыт)"
            lines.append(text)
        elif part.side == "heroes":
            lines.append(f"◆ {name} {hp}")
        else:
            lines.append(f"✕ {name} {hp}")
    hero_zone = [p.zone_id for p in state.participants if p.ref == hero.id][0]
    if zone_id == hero_zone:
        for npc in sorted(world.npcs.values(), key=lambda n: n.id):
            if npc.status == "alive" and npc.follows == hero.id:
                lines.append(f"○ {npc.name}")
    return lines


def start_zone_id(state, hero):
    # зона героя на старте боя: откуда он впервые пошёл, иначе где стоит сейчас
    for move in state.moves:
        if move.ref == hero.id:
            return move.from_zone
    return [p.zone_id for p in state.participants if p.ref == hero.id][0]


def bfs_layers(state, start_id):
    by_id = {z.id: z for z in state.zones}
    layers = []
    seen = set()
    first = start_id
    while True:
        layer = [first]
        seen.add(first)
        while layer:
            layers.append(layer)
            nxt = []
            for zone_id in layer:
                for other in by_id[zone_id].adjacent:
                    if other in by_id and other not in seen and other not in nxt:
                        nxt.append(other)
            # внутри слоя -- по порядку зон
            order = [z.id for z in state.zones]
            nxt.sort(key=order.index)
            seen.update(nxt)
            layer = nxt
        rest = [z.id for z in state.zones if z.id not in seen]
        if not rest:
            return layers
        first = rest[0]


def layout(state, hero):
    # зона -> (ряд, колонка); слои BFS от зоны героя на старте боя, pos мастера главнее
    cells = {}
    for col, layer in enumerate(bfs_layers(state, start_zone_id(state, hero))):
        for row, zone_id in enumerate(layer):
            cells[zone_id] = (row, col)
    taken = set()
    for zone in state.zones:
        if zone.pos is not None:
            cells[zone.id] = (zone.pos[0], zone.pos[1])
            taken.add(cells[zone.id])
    for zone in state.zones:
        if zone.pos is None:
            row, col = cells[zone.id]
            while (row, col) in taken:
                row += 1
            cells[zone.id] = (row, col)
            taken.add((row, col))
    return cells


def fit(text, width):
    # не влезает -- укорачивается имя с «…», HP в конце остаётся
    if len(text) <= width:
        return text
    tail = HP_TAIL.search(text)
    tail = tail.group() if tail else ""
    head = text[: len(text) - len(tail)]
    room = width - len(tail) - 1
    if room < 1:
        return text[: width - 1] + "…"
    return head[:room] + "…" + tail


def box_lines(zone, who, width):
    inner = width - 2
    title = f"─ {zone.name} "
    if len(title) > inner:
        title = title[: inner - 1] + "…"
    lines = ["┌" + title.ljust(inner, "─") + "┐"]
    body = []
    marks = zone_marks(zone)
    if marks:
        body.append(marks)
    body += who
    if not body:
        body = [""]
    for text in body:
        text = fit(" " + text, inner)
        lines.append("│" + text.ljust(inner) + "│")
    lines.append("└" + "─" * inner + "┘")
    return lines


def zone_list_lines(state, world, hero, width):
    lines = []
    for zone in state.zones:
        who = ", ".join(members(state, world, hero, zone.id)) or "пусто"
        marks = zone_marks(zone)
        head = f"{zone.name} [{marks}]" if marks else zone.name
        lines += wrap_block(f"{head}: {who}", width, "  ", "    ")
    return lines


def boxes_lines(state, world, hero, width):
    cells = layout(state, hero)
    rows_count = max(row for row, _ in cells.values()) + 1
    cols_count = max(col for _, col in cells.values()) + 1
    max_cols = (width + GAP) // (MIN_BOX + GAP)
    if cols_count > max_cols:
        # не помещается в ширину: лишние слои переносятся вниз
        cells = {
            zone_id: (row + (col // max_cols) * rows_count, col % max_cols)
            for zone_id, (row, col) in cells.items()
        }
        rows_count *= (cols_count + max_cols - 1) // max_cols
        cols_count = max_cols
    box_width = min(MAX_BOX, (width - 2 - GAP * (cols_count - 1)) // cols_count)
    zone_at = {cell: zone for zone in state.zones for cell in [cells[zone.id]]}
    by_id = {z.id: z for z in state.zones}

    def linked(a, b):
        return a is not None and b is not None and b.id in a.adjacent

    lines = []
    for row in range(rows_count):
        boxes = []
        for col in range(cols_count):
            zone = zone_at.get((row, col))
            boxes.append(
                None if zone is None
                else box_lines(zone, members(state, world, hero, zone.id), box_width)
            )
        height = max((len(b) for b in boxes if b is not None), default=0)
        if height == 0:
            continue
        for b in boxes:
            if b is not None:
                b[-1:-1] = [b[-2][0] + " " * (box_width - 2) + b[-2][-1]] * (height - len(b))
        for i in range(height):
            text = ""
            for col in range(cols_count):
                text += " " * box_width if boxes[col] is None else boxes[col][i]
                if col < cols_count - 1:
                    join = linked(zone_at.get((row, col)), zone_at.get((row, col + 1)))
                    text += "─" * GAP if join and i == 1 else " " * GAP
            lines.append("  " + text.rstrip())
        below = row + 1
        text = ""
        for col in range(cols_count):
            if linked(zone_at.get((row, col)), zone_at.get((below, col))):
                text += " " * (box_width // 2) + "│" + " " * (box_width - box_width // 2 - 1)
            else:
                text += " " * box_width
            text += " " * GAP
        if text.strip():
            lines.append("  " + text.rstrip())
    # переходы, которые линией не нарисованы (по диагонали, через несколько колонок, через перенос)
    drawn = set()
    for zone in state.zones:
        for other_id in zone.adjacent:
            if other_id not in by_id:
                continue
            (r1, c1), (r2, c2) = cells[zone.id], cells[other_id]
            if (r1 == r2 and abs(c1 - c2) == 1) or (c1 == c2 and abs(r1 - r2) == 1):
                drawn.add(frozenset((zone.id, other_id)))
    extra = []
    for zone in state.zones:
        for other_id in zone.adjacent:
            pair = frozenset((zone.id, other_id))
            if other_id in by_id and pair not in drawn and pair not in extra:
                extra.append(pair)
    if extra:
        names = [
            " — ".join(by_id[i].name for i in sorted(pair, key=[z.id for z in state.zones].index))
            for pair in extra
        ]
        lines += wrap_block("Ещё переходы: " + "; ".join(names), width, "  ", "    ")
    return lines


def moves_line(state, world, hero, width=WIDTH):
    # перемещения с прошлого хода игрока: после последнего заголовка его хода;
    # если ход героя уже идёт -- после предыдущего заголовка
    marker = f"ход: {hero.name} ---"
    heads = [i for i, line in enumerate(state.log) if line.startswith("--- раунд ") and
             line.endswith(marker)]
    if state.turn_started_for == hero.id:
        heads = heads[:-1]
    since = heads[-1] if heads else 0
    names = {z.id: z.name for z in state.zones}
    texts = [
        f"{part_name(state, world, hero, m.ref)} {names[m.from_zone]} → {names[m.to_zone]}"
        for m in state.moves
        if m.log_index >= since
    ]
    if not texts:
        return []
    return wrap_block("Движение: " + "; ".join(texts), width, "  ", "    ")


def ground_line(state, registry, width=WIDTH):
    # выбитое оружие на земле: «На земле: скимитар (Поляна)»
    if registry is None or not state.ground_items:
        return []
    names = {z.id: z.name for z in state.zones}
    texts = [
        f"{registry.get('weapon', item.item_id).name.lower()} ({names[item.zone_id]})"
        for item in state.ground_items
    ]
    return wrap_block("На земле: " + "; ".join(texts), width, "  ", "    ")


def battle_map_lines(state, world, hero, width=WIDTH, registry=None):
    # карта зон боя: рамки и линии (до 8 зон) или список; легенда; движение с прошлого хода
    title = f"Карта боя, раунд {state.round}"
    lines = [f"  {title}"]
    if len(state.zones) > MAX_ZONES_BOXES:
        lines += zone_list_lines(state, world, hero, width)
    else:
        lines += boxes_lines(state, world, hero, width)
    lines.append("  " + LEGEND)
    return lines + moves_line(state, world, hero, width) + ground_line(state, registry, width)
