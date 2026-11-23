import re

from ai_dm.rules import time_ops
from ai_dm.rules import trade as trade_rules
from ai_dm.rules.attitude import at_least

# заведение по имени локации ↔ ремесло хозяина в means ↔ подсказка по услугам (Л1 П3);
# стемы по casefold
KEEPER_FAMILIES = (
    (
        r"таверн|трактир(?!н)|корчм|постоял|харчевн|кабак",
        r"трактир|таверн|корчм|постоял|харчевн|кабак|стойк(а|е|и|у|ой)\b",
        "services (например room_poor, meal_modest, ale)",
    ),
    (
        r"лавк|магазин|аптек(?!ар)",
        r"лавк|лавочн|торгов|аптек|товар(?!ищ)",
        "trade_kind (например general)",
    ),
    (r"кузниц", r"кузн|ковк|наковальн|горнил", "trade_kind smith"),
    (
        r"\bхрам(?!ов)|святилищ",
        r"жрец|жриц|священ|настоятел|исцел|благослов",
        "services (например heal_temple, uncurse_temple)",
    ),
)

HAGGLE_FLAG = "haggle"
LODGING_FLAG = "lodging"
# берег перевозчика: ferry_home:<id NPC> = id локации, где он стоял при первом найме героем
FERRY_HOME_FLAG = "ferry_home"
# герой платил NPC за близость: romance в памяти пишется только с порога отношения (У1 П2)
PAID_COMPANY_FLAG = "paid_company"
# день даровой услуги вида у NPC: free_service:<id NPC>:<id вида> = день (П6б)
FREE_FLAG = "free_service"


class FlagHaggle:
    # торг с NPC без лавки: состояние во флаге haggle:<npc_id> = "<день>:<процент>"; поля те же,
    # что у TradeProfile, поэтому правила trade (active_haggle, can_haggle, apply_haggle) подходят
    def __init__(self, flags, npc_id):
        self.flags = flags
        self.key = f"{HAGGLE_FLAG}:{npc_id}"
        self.haggle_day = None
        self.haggle_percent = 0
        raw = flags.get(self.key)
        if isinstance(raw, str):
            day, percent = raw.split(":")
            self.haggle_day = int(day)
            self.haggle_percent = int(percent)

    def save(self):
        self.flags[self.key] = f"{self.haggle_day}:{self.haggle_percent}"


def keeper_hint(location_name, means) -> str | None:
    # NPC похож на хозяина заведения: имя локации и ремесло из одного семейства KEEPER_FAMILIES;
    # возвращает подсказку семейства по услугам, иначе None
    place = location_name.casefold()
    text = " ".join(means).casefold()
    for spot, craft, hint in KEEPER_FAMILIES:
        if re.search(spot, place) and re.search(craft, text):
            return hint
    return None


def haggle_slot(npc, world):
    # где лежит торг NPC: профиль лавки, если он есть (общий торг с товарами), иначе флаг мира
    if npc.trade is not None:
        return npc.trade
    return FlagHaggle(world.flags, npc.id)


def save_haggle(slot) -> None:
    if isinstance(slot, FlagHaggle):
        slot.save()


def kinds_of(npc, cfg) -> list:
    # [(id, ServiceKind)] услуг NPC, известных конфигу, в порядке NPC
    kinds = cfg.services.kinds
    return [(kind_id, kinds[kind_id]) for kind_id in npc.services if kind_id in kinds]


def free_key(npc, kind_id) -> str:
    return f"{FREE_FLAG}:{npc.id}:{kind_id}"


def free_today(kind_id, npc, world, cfg) -> bool:
    # друг (ступень не ниже free_tier) ещё не брал даровую услугу этого вида у этого NPC сегодня
    day = trade_rules.day_of(world.clock.now_s)
    return (
        at_least(npc.attitude, cfg.services.free_tier, cfg)
        and world.flags.get(free_key(npc, kind_id)) != day
    )


def mark_free(kind_id, npc, world) -> None:
    world.flags[free_key(npc, kind_id)] = trade_rules.day_of(world.clock.now_s)


def is_free(kind_id, kind, npc, world, cfg) -> bool:
    # перевозка у друга -- даром всегда, прочие виды -- раз в день (решения 148, 149, 154)
    if kind.effect == "passage":
        return at_least(npc.attitude, cfg.services.free_tier, cfg)
    return free_today(kind_id, npc, world, cfg)


def quote(kind, npc, world, cfg, kind_id) -> int:
    # цена услуги за единицу: даром у друга, иначе отношение и торг, как у покупки в trade
    if is_free(kind_id, kind, npc, world, cfg):
        return 0
    slot = haggle_slot(npc, world)
    haggle = trade_rules.active_haggle(slot, world.clock.now_s)
    return trade_rules.buy_quote(kind.price_cp, npc.attitude, cfg, haggle)


def providers_here(world, location_id) -> list:
    # живые NPC с услугами в локации
    return [
        npc for npc in world.npcs.values()
        if npc.services and npc.status == "alive" and npc.location_id == location_id
    ]


def passage_providers(world, location_id, transport, cfg) -> list:
    # живые NPC локации с услугой перевозки рода transport
    return [
        npc for npc in providers_here(world, location_id)
        if any(
            kind.effect == "passage" and kind.transport == transport
            for _, kind in kinds_of(npc, cfg)
        )
    ]


def passage_targets(world, location_id, transport, cfg) -> dict:
    # {id соседа: ребро} -- куда везёт перевозка рода transport из локации: сосед в любую сторону
    # по ребру, чей род пути требует этот транспорт; из рёбер пары -- с меньшим временем
    result = {}
    for target, edges in time_ops.linked_edges(world, world.locations[location_id]).items():
        fits = [c for c in edges if cfg.time.route_kinds[c.kind].transport == transport]
        if fits:
            result[target] = min(
                fits, key=lambda c: time_ops.edge_seconds(c.distance_m, c.kind, "normal", cfg)
            )
    return result


def remember_ferry_home(world, npc) -> None:
    # перевозка принята: берег -- где перевозчик стоял до неё; уже записанный не меняется
    world.flags.setdefault(f"{FERRY_HOME_FLAG}:{npc.id}", npc.location_id)


def return_ferrymen(world, location_id) -> list:
    # герой пришёл на берег: записи с этим берегом сняты; живые перевозчики не на берегу вернулись
    prefix = f"{FERRY_HOME_FLAG}:"
    ids = {key[len(prefix):] for key, home in world.flags.items()
           if key.startswith(prefix) and home == location_id}
    for npc_id in ids:
        del world.flags[prefix + npc_id]
    returned = [n for n in world.npcs.values()
                if n.id in ids and n.status == "alive" and n.location_id != location_id]
    for npc in returned:
        npc.location_id = location_id
    return returned


def returned_signal(world, returned) -> str:
    return "; ".join(
        f"{n.name} вернулся на свой берег — «{world.locations[n.location_id].name}»"
        for n in returned
    )


def service_entries(npc, world, cfg) -> list:
    # [(подпись строки, id вида, ServiceKind)] услуг NPC для /shop; перевозка -- строка на каждое
    # место, куда везёт
    entries = []
    for kind_id, kind in kinds_of(npc, cfg):
        if kind.effect != "passage":
            entries.append((kind.name, kind_id, kind))
            continue
        targets = passage_targets(world, npc.location_id, kind.transport, cfg)
        entries += [(f"{kind.name}: {world.locations[t].name}", kind_id, kind) for t in targets]
    return entries


def lodging_here(world, location_id, cfg) -> list:
    # [(NPC, id, ServiceKind)] ночлега у живых NPC в локации (по цене, дешёвый первым)
    found = [
        (npc, kind_id, kind)
        for npc in providers_here(world, location_id)
        for kind_id, kind in kinds_of(npc, cfg)
        if kind.effect == "lodging"
    ]
    return sorted(found, key=lambda item: quote(item[2], item[0], world, cfg, item[1]))


def lodging_paid(world, hero_id, cfg) -> bool:
    # ночлег героя оплачен на ночь: флаг -- день оплаты, действует до утра (morning_hour) следующего
    day = world.flags.get(f"{LODGING_FLAG}:{hero_id}")
    if not isinstance(day, int) or isinstance(day, bool):
        return False
    until_s = (day + 1) * trade_rules.DAY_S + cfg.time.morning_hour * 3600
    return world.clock.now_s < until_s
