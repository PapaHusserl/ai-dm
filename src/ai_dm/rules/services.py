from ai_dm.rules import trade as trade_rules

HAGGLE_FLAG = "haggle"
LODGING_FLAG = "lodging"
# герой платил NPC за близость: romance в памяти пишется только с порога отношения (У1 П2)
PAID_COMPANY_FLAG = "paid_company"


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


def quote(kind, npc, world, cfg) -> int:
    # цена услуги за единицу: отношение и торг, как у покупки в trade
    slot = haggle_slot(npc, world)
    haggle = trade_rules.active_haggle(slot, world.clock.now_s)
    return trade_rules.buy_quote(kind.price_cp, npc.attitude, cfg, haggle)


def providers_here(world, location_id) -> list:
    # живые NPC с услугами в локации
    return [
        npc for npc in world.npcs.values()
        if npc.services and npc.status == "alive" and npc.location_id == location_id
    ]


def lodging_here(world, location_id, cfg) -> list:
    # [(NPC, id, ServiceKind)] ночлега у живых NPC в локации (по цене, дешёвый первым)
    found = [
        (npc, kind_id, kind)
        for npc in providers_here(world, location_id)
        for kind_id, kind in kinds_of(npc, cfg)
        if kind.effect == "lodging"
    ]
    return sorted(found, key=lambda item: quote(item[2], item[0], world, cfg))


def lodging_paid(world, hero_id, cfg) -> bool:
    # ночлег героя оплачен на ночь: флаг -- день оплаты, действует до утра (morning_hour) следующего
    day = world.flags.get(f"{LODGING_FLAG}:{hero_id}")
    if not isinstance(day, int) or isinstance(day, bool):
        return False
    until_s = (day + 1) * trade_rules.DAY_S + cfg.time.morning_hour * 3600
    return world.clock.now_s < until_s
