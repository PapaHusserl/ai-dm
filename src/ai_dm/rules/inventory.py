from ai_dm.core.dice import roll_dice
from ai_dm.rules.creatures import live_effects
from ai_dm.rules.derived import clock_text, effect_amount
from ai_dm.rules.healing import heal
from ai_dm.state.creature import ActiveEffect, Expiry
from ai_dm.state.hero import InventoryEntry

SLOTS = ("armor", "shield", "main_hand", "off_hand")
# SRD 5.2: минуты на надеть / снять доспех по типу
ARMOR_MINUTES = {"light": (1, 1), "medium": (5, 1), "heavy": (10, 5)}


QUALITY_WORDS = {"junk": "ржавый", "worn": "поношенный", "used": "потёртый"}


class InventoryError(ValueError):
    pass


def find_item(registry, item_id):
    # возвращает (вид, модель) или None
    for kind in ("weapon", "armor", "item"):
        if registry.has(kind, item_id):
            return kind, registry.get(kind, item_id)
    return None


def entry_name(entry, registry) -> str:
    # имя стека: название предмета и, если есть, качество приставкой («ржавый скимитар»)
    found = find_item(registry, entry.item_id)
    name = entry.item_id if found is None else found[1].name
    if entry.quality is not None:
        name = f"{QUALITY_WORDS[entry.quality].capitalize()} {name.lower()}"
    return name


def count_item(hero, item_id: str) -> int:
    return sum(entry.qty for entry in hero.inventory if entry.item_id == item_id)


def item_totals(hero) -> dict[str, int]:
    # id предмета -> количество по всем стекам (порядок первого появления)
    totals = {}
    for entry in hero.inventory:
        totals[entry.item_id] = totals.get(entry.item_id, 0) + entry.qty
    return totals


def dearest_cost(hero, item_id: str) -> int:
    # цена самого дорогого стека: надетая вещь берётся из него
    return max(entry.cost_cp for entry in hero.inventory if entry.item_id == item_id)


def add_item(hero, item_id: str, qty: int = 1, *, cost_cp: int, quality=None) -> None:
    if qty < 1:
        raise InventoryError("количество должно быть >= 1")
    for entry in hero.inventory:
        if entry.item_id == item_id and entry.cost_cp == cost_cp and entry.quality == quality:
            entry.qty += qty
            return
    hero.inventory.append(
        InventoryEntry(item_id=item_id, qty=qty, cost_cp=cost_cp, quality=quality)
    )


def add_catalog_item(hero, registry, item_id: str, qty: int = 1) -> None:
    # обычная выдача: цена из реестра
    found = find_item(registry, item_id)
    if found is None:
        raise InventoryError(f"неизвестный предмет: {item_id}")
    add_item(hero, item_id, qty, cost_cp=found[1].cost_cp)


def remove_item(
    hero, item_id: str, qty: int = 1, *, cost_cp=None, quality="any"
) -> list[InventoryEntry]:
    # cost_cp=None: сначала самые дешёвые стеки; с ценой -- только стеки этой цены.
    # quality="any": любое качество; None или значение -- только такой стек.
    # Возвращает снятое (по записи на стек).
    if qty < 1:
        raise InventoryError("количество должно быть >= 1")
    stacks = [
        e for e in hero.inventory
        if e.item_id == item_id
        and (cost_cp is None or e.cost_cp == cost_cp)
        and (quality == "any" or e.quality == quality)
    ]
    if sum(e.qty for e in stacks) < qty:
        raise InventoryError(f"нет столько предметов: {item_id}")
    stacks.sort(key=lambda e: e.cost_cp)
    removed = []
    left = qty
    for entry in stacks:
        taken = min(entry.qty, left)
        entry.qty -= taken
        left -= taken
        removed.append(
            InventoryEntry(item_id=item_id, qty=taken, cost_cp=entry.cost_cp, quality=entry.quality)
        )
        if left == 0:
            break
    hero.inventory = [e for e in hero.inventory if e.qty > 0]
    if count_item(hero, item_id) == 0:
        for slot in SLOTS:
            if getattr(hero.equipped, slot) == item_id:
                setattr(hero.equipped, slot, None)
    return removed


def equip(hero, item_id: str, registry, slot: str = "main_hand") -> None:
    # slot нужен только оружию: "main_hand" (по умолчанию) или "off_hand" (только лёгкое)
    if count_item(hero, item_id) == 0:
        raise InventoryError(f"предмета нет в инвентаре: {item_id}")
    found = find_item(registry, item_id)
    if found is None:
        raise InventoryError(f"неизвестный предмет: {item_id}")
    kind, item = found
    if kind == "weapon":
        if slot not in ("main_hand", "off_hand"):
            raise InventoryError(f"оружие нельзя надеть в слот: {slot}")
        if slot == "off_hand" and "light" not in item.properties:
            raise InventoryError(f"в левую руку только лёгкое оружие: {item_id}")
        if slot == "off_hand" and hero.equipped.shield is not None:
            raise InventoryError(f"левая рука занята щитом: {item_id}")
        if slot == "off_hand" and hero.equipped.main_hand is not None:
            main_hand = registry.get("weapon", hero.equipped.main_hand)
            if "two_handed" in main_hand.properties:
                raise InventoryError(f"в правой руке двуручное оружие: {item_id}")
        if "two_handed" in item.properties and hero.equipped.shield is not None:
            raise InventoryError(f"двуручное оружие нельзя со щитом: {item_id}")
        if "two_handed" in item.properties and hero.equipped.off_hand is not None:
            raise InventoryError(f"двуручное оружие нельзя с оружием в левой руке: {item_id}")
        other = "main_hand" if slot == "off_hand" else "off_hand"
        if getattr(hero.equipped, other) == item_id and count_item(hero, item_id) < 2:
            raise InventoryError(f"один предмет нельзя взять в обе руки: {item_id}")
        setattr(hero.equipped, slot, item_id)
    elif kind == "armor" and item.category == "shield":
        main_hand = hero.equipped.main_hand
        if main_hand is not None and "two_handed" in registry.get("weapon", main_hand).properties:
            raise InventoryError(f"щит нельзя с двуручным оружием: {main_hand}")
        if hero.equipped.off_hand is not None:
            raise InventoryError(f"щит нельзя с оружием в левой руке: {hero.equipped.off_hand}")
        hero.equipped.shield = item_id
    elif kind == "armor":
        char_class = registry.get("class", hero.sheet.class_id)
        if item.category not in char_class.armor_training:
            raise InventoryError(f"нет владения доспехом: {item_id}")
        hero.equipped.armor = item_id
    else:
        raise InventoryError(f"предмет нельзя экипировать: {item_id}")


def blocking_slots(hero, item_id: str, registry, slot: str = "main_hand") -> list[str]:
    # занятые слоты, которые мешают надеть предмет (equip откажет): их снимают до equip
    found = find_item(registry, item_id)
    if found is None:
        return []
    kind, item = found
    equipped = hero.equipped
    two_handed_held = equipped.main_hand is not None and (
        "two_handed" in registry.get("weapon", equipped.main_hand).properties
    )
    blockers = []
    if kind == "weapon" and "two_handed" in item.properties:
        blockers = ["shield", "off_hand"]
    elif kind == "weapon" and slot == "off_hand" and "light" in item.properties:
        blockers = ["shield"] + ["main_hand"] * two_handed_held
    elif kind == "armor" and item.category == "shield":
        blockers = ["off_hand"] + ["main_hand"] * two_handed_held
    return [s for s in blockers if getattr(equipped, s) is not None]


def unequip(hero, slot: str) -> str:
    # снимает предмет со слота; возвращает его id
    if slot not in SLOTS:
        raise InventoryError(f"нет такого слота: {slot}")
    item_id = getattr(hero.equipped, slot)
    if item_id is None:
        raise InventoryError(f"слот пуст: {slot}")
    setattr(hero.equipped, slot, None)
    return item_id


def use_item(hero, item_id: str, registry, rng) -> int:
    if count_item(hero, item_id) == 0:
        raise InventoryError(f"предмета нет в инвентаре: {item_id}")
    found = find_item(registry, item_id)
    if found is None or found[0] != "item" or not found[1].effects:
        raise InventoryError(f"предмет нельзя использовать: {item_id}")
    effect = found[1].effects[0]
    if effect.type != "heal":
        raise InventoryError(f"предмет нельзя использовать: {item_id}")
    amount = roll_dice(effect.dice, rng).total + effect_amount(effect, hero, registry)
    healed = heal(hero, amount)
    remove_item(hero, item_id)
    return healed


RESIST_WORDS = {
    "bludgeoning": "дробящему", "piercing": "колющему", "slashing": "рубящему",
    "fire": "огненному", "cold": "холодному", "lightning": "электрическому",
    "thunder": "звуковому", "acid": "кислотному", "poison": "ядовитому",
    "necrotic": "некротическому", "radiant": "излучению", "psychic": "психическому",
    "force": "силовому",
}


def active_item_until(hero, item_id: str, now_s: int):
    # до какого момента действует эффект этого предмета (секунды мира); None -- не действует
    ends = [
        e.expires.value for e in live_effects(hero.creature, now_s)
        if e.id == item_id and e.expires is not None and e.expires.kind == "seconds"
    ]
    return max(ends) if ends else None


def effects_line(hero, registry, now_s: int) -> str:
    # «Действует: Каменная Кожа (+2 КД, сопр. рубящему/дробящему) до 03:12»; пусто, если нет
    order = []
    for effect in live_effects(hero.creature, now_s):
        if effect.expires is None or effect.expires.kind != "seconds":
            continue
        # заклинания и бонусы услуг (groomed) -- не предметы реестра
        if effect.kind in ("spell", "modifier"):
            continue
        if effect.id not in order:
            order.append(effect.id)
    texts = []
    for item_id in order:
        item = registry.get("item", item_id)
        plus = []
        resists = []
        for effect in live_effects(hero.creature, now_s):
            if effect.id != item_id:
                continue
            if effect.kind == "ac":
                plus.append(f"+{effect.params['amount']} КД")
            elif effect.kind == "resist":
                damage_type = effect.params["damage_type"]
                resists.append(RESIST_WORDS.get(damage_type, damage_type))
        if resists:
            plus.append("сопр. " + "/".join(resists))
        until = clock_text(active_item_until(hero, item_id, now_s))
        texts.append(f"{item.short_name or item.name} ({', '.join(plus)}) до {until}")
    if not texts:
        return ""
    return "Действует: " + "; ".join(texts)


def drink_item(hero, item_id: str, registry, now_s: int) -> bool:
    # эликсир с эффектом на время (ac_bonus, resist): ActiveEffect до момента now_s + duration_s.
    # Уже действующий эффект не складывается: старый заменяется, срок идёт заново.
    # Возвращает True, если эффект уже действовал.
    if count_item(hero, item_id) == 0:
        raise InventoryError(f"предмета нет в инвентаре: {item_id}")
    found = find_item(registry, item_id)
    if found is None or found[0] != "item" or not found[1].effects:
        raise InventoryError(f"предмет нельзя выпить: {item_id}")
    item = found[1]
    label = item.short_name or item.name
    was_active = active_item_until(hero, item_id, now_s) is not None
    if was_active:
        hero.creature.active_effects = [e for e in hero.creature.active_effects if e.id != item_id]
    for effect in item.effects:
        expires = Expiry(kind="seconds", value=now_s + (effect.duration_s or 0))
        if effect.type == "ac_bonus":
            params = {"amount": effect.value, "label": label, "magic": True}
            hero.creature.active_effects.append(
                ActiveEffect(id=item_id, source=hero.id, kind="ac", params=params, expires=expires)
            )
        elif effect.type == "resist":
            params = {"damage_type": effect.damage_type}
            hero.creature.active_effects.append(
                ActiveEffect(
                    id=item_id, source=hero.id, kind="resist", params=params, expires=expires
                )
            )
        else:
            raise InventoryError(f"предмет нельзя выпить: {item_id}")
    remove_item(hero, item_id)
    return was_active


def pick_valuables(hero, registry, rng, count: int) -> list[InventoryEntry]:
    # по одной вещи (qty=1) с ценой стека. Надетое (все слоты equipped) не берётся:
    # из количества вычитается число слотов с этим id, сначала из самых дорогих стеков
    worn_left = {}
    for slot in SLOTS:
        item_id = getattr(hero.equipped, slot)
        if item_id is not None:
            worn_left[item_id] = worn_left.get(item_id, 0) + 1
    # цена по убыванию, при равной цене сначала по id
    # неизвестный реестру id пропускается
    known = [e for e in hero.inventory if find_item(registry, e.item_id) is not None]
    stacks = sorted(known, key=lambda e: (-e.cost_cp, e.item_id))
    # (цена стека, стек, свободное количество)
    entries = []
    for entry in stacks:
        worn = min(worn_left.get(entry.item_id, 0), entry.qty)
        worn_left[entry.item_id] = worn_left.get(entry.item_id, 0) - worn
        if entry.qty - worn > 0:
            entries.append((entry.cost_cp, entry, entry.qty - worn))
    result = []
    start = 0
    while start < len(entries) and len(result) < count:
        end = start
        while end < len(entries) and entries[end][0] == entries[start][0]:
            end += 1
        group = entries[start:end]
        # ничья по цене между разными стеками: перемешиваем через rng (Фишер-Йетс)
        for i in range(len(group) - 1, 0, -1):
            j = rng.randint(0, i)
            group[i], group[j] = group[j], group[i]
        for _, entry, qty in group:
            one = InventoryEntry(
                item_id=entry.item_id, qty=1, cost_cp=entry.cost_cp, quality=entry.quality
            )
            result.extend([one] * qty)
        start = end
    return result[:count]
