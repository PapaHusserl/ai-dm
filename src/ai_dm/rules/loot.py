from fractions import Fraction

from ai_dm.rules.derived import table_value
from ai_dm.rules.inventory import find_item
from ai_dm.state.hero import InventoryEntry

HOARD_BANDS = ["0-4", "5-10", "11-16", "17+"]
# типы существ, у которых нет монет (за них individual_treasure не бросается)
NO_COIN_TYPES = ("beast", "construct", "elemental")


def treasure_band(cr: str) -> str:
    if "/" in cr:
        return "0-4"
    level = int(cr)
    if level <= 4:
        return "0-4"
    if level <= 10:
        return "5-10"
    if level <= 16:
        return "11-16"
    return "17+"


def level_band(level: int) -> str:
    # полоса клада по уровню героя, те же полосы, что у treasure_band
    if level <= 4:
        return "0-4"
    if level <= 10:
        return "5-10"
    if level <= 16:
        return "11-16"
    return "17+"


def defeated_treasure(monster_ids, rng, registry) -> int:
    # деньги в медных за всех побеждённых врагов (по ПО каждого); звери, конструкты и
    # элементали монет не носят, кубики за них не бросаются
    total = 0
    for monster_id in monster_ids:
        monster = registry.get("monster", monster_id)
        if monster.creature_type in NO_COIN_TYPES:
            continue
        total += individual_treasure(monster.cr, rng, registry)
    return total


def individual_treasure(cr: str, rng, registry) -> int:
    # деньги в медных за одного побеждённого; неизвестный CR -- ValueError до броска
    if cr not in registry.get("table", "cr_xp").rows:
        raise ValueError(f"неизвестный CR: {cr!r}")
    band = treasure_band(cr)
    count = table_value(registry, "individual_treasure", f"{band}:count")
    sides = table_value(registry, "individual_treasure", f"{band}:sides")
    cp = table_value(registry, "individual_treasure", f"{band}:cp")
    total = 0
    for _ in range(count):
        total += rng.d(sides)
    return total * cp


def hoard_band(monster_ids, registry) -> str:
    # полоса клада по самому опасному из побеждённых
    bands = [treasure_band(registry.get("monster", monster_id).cr) for monster_id in monster_ids]
    return max(bands, key=HOARD_BANDS.index, default="0-4")


def hoard_treasure(monster_ids, rng, registry, level=None) -> int:
    # клад логова в медных: кости каждой монеты полосы, множитель в медных;
    # без побеждённых (сцена в логове) полоса -- по уровню героя
    use_defeated = monster_ids or level is None
    band = hoard_band(monster_ids, registry) if use_defeated else level_band(level)
    rows = registry.get("table", "hoard").rows
    total = 0
    for coin in ("cp", "sp", "gp", "pp"):
        if f"{band}:{coin}:count" not in rows:
            continue
        count = rows[f"{band}:{coin}:count"]
        sides = rows[f"{band}:{coin}:sides"]
        mult = rows[f"{band}:{coin}:mult_cp"]
        total += sum(rng.d(sides) for _ in range(count)) * mult
    return total


RARITY_ORDER = ["common", "uncommon", "rare", "very_rare", "legendary", "artifact"]


def rarity_exceeds_cap(item, level, cfg) -> bool:
    # магический предмет выше предела редкости для уровня героя; немагические не проверяются
    if not item.magic or item.rarity is None:
        return False
    cap = cfg.loot.rarity_cap_by_level[level]
    return RARITY_ORDER.index(item.rarity) > RARITY_ORDER.index(cap)


def trophy_quality(cr, cfg):
    # качество трофея с тела по ПО; None -- полная цена (ПО выше последней полосы)
    value = Fraction(cr)
    for band in cfg.loot.trophy_quality:
        if value <= Fraction(band.max_cr):
            return band.quality
    return None


def trophy_cost(base, quality, cfg) -> int:
    # цена трофея в медных: доля цены SRD по качеству, не меньше 1
    if quality is None:
        return base
    band = next(b for b in cfg.loot.trophy_quality if b.quality == quality)
    return max(1, base * band.percent // 100)


def gear_cost(registry, item_id) -> int:
    # цена оружия, доспеха или предмета по SRD в медных; неизвестный id -- ValueError
    found = find_item(registry, item_id)
    if found is None:
        raise ValueError(f"неизвестный предмет: {item_id!r}")
    return found[1].cost_cp


def body_gear(bodies, registry, cfg) -> list[InventoryEntry]:
    # снаряжение с тел: bodies -- (monster_id, id оружия/доспеха/щита, boss); босс -- полная цена
    result = []
    for monster_id, weapon_ids, boss in bodies:
        quality = None
        if not boss:
            quality = trophy_quality(registry.get("monster", monster_id).cr, cfg)
        for weapon_id in weapon_ids:
            cost_cp = trophy_cost(gear_cost(registry, weapon_id), quality, cfg)
            add_stack(result, InventoryEntry(
                item_id=weapon_id, cost_cp=cost_cp, quality=quality
            ))
    return result


def add_stack(stacks, entry) -> None:
    for stack in stacks:
        if (stack.item_id, stack.cost_cp, stack.quality) == (
            entry.item_id, entry.cost_cp, entry.quality
        ):
            stack.qty += entry.qty
            return
    stacks.append(entry)


def quest_gear(world, refs) -> list[InventoryEntry]:
    # квестовые предметы, которыми владеют поверженные NPC (держатель-npc); как есть
    result = []
    for item_id, custom in world.custom_items.items():
        holder = custom.holder
        if custom.quest and holder is not None and holder.kind == "npc" and holder.ref in refs:
            result.append(
                InventoryEntry(item_id=item_id, qty=holder.qty, cost_cp=holder.cost_cp)
            )
    return result
