def tier_of(attitude, cfg):
    # ступень отношения: последняя, чья нижняя граница не выше числа; ниже первой границы -- первая
    found = cfg.attitude.tiers[0]
    for tier in cfg.attitude.tiers:
        if tier.low <= attitude:
            found = tier
    return found


def tier_index(tier_id, cfg) -> int:
    return [t.id for t in cfg.attitude.tiers].index(tier_id)


def tier_name(tier_id, cfg) -> str:
    return cfg.attitude.tiers[tier_index(tier_id, cfg)].name


def at_least(attitude, tier_id, cfg) -> bool:
    # ступень не ниже tier_id: «друг» -- это и «близкий»
    return tier_index(tier_of(attitude, cfg).id, cfg) >= tier_index(tier_id, cfg)


def at_most(attitude, tier_id, cfg) -> bool:
    # ступень не выше tier_id: «недруг» -- это и «враг»
    return tier_index(tier_of(attitude, cfg).id, cfg) <= tier_index(tier_id, cfg)
