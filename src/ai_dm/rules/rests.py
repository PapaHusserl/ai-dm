from ai_dm.rules import divine
from ai_dm.rules.derived import LONG_REST_FULL, ability_mod, hero_effects
from ai_dm.rules.exhaustion import remove_exhaustion
from ai_dm.rules.healing import heal
from ai_dm.rules.time_ops import long_rest_seconds, short_rest_seconds
from ai_dm.state.creature import ResourcePool


def recover_pools(hero, registry, rest: str) -> None:
    # пулы с recover из умений героя: +amount (не выше max) или all;
    # каждый пул восстанавливается один раз: all или наибольший amount среди дублей
    pools = hero.creature.resources
    best = {}
    for effect in hero_effects(hero, registry):
        if effect.type != "resource" or effect.pool not in pools:
            continue
        for rule in effect.recover:
            if rule.on != rest:
                continue
            if rule.amount == "all" or best.get(effect.pool) == "all":
                best[effect.pool] = "all"
            else:
                best[effect.pool] = max(best.get(effect.pool, 0), rule.amount)
    for name, amount in best.items():
        pool = pools[name]
        if amount == "all":
            pool.current = pool.max
        else:
            pool.current = min(pool.max, pool.current + amount)


def hit_dice_pools(creature) -> list[tuple[str, ResourcePool, int]]:
    # пулы костей хитов (ключ, пул, грани) по убыванию граней
    result = []
    for name, pool in creature.resources.items():
        if name.startswith("hit_dice:d"):
            result.append((name, pool, int(name[len("hit_dice:d"):])))
    return sorted(result, key=lambda item: -item[2])


def short_rest(hero, registry, rng, clock, cfg, *, hit_dice: int = 0) -> int:
    if hero.status == "dead":
        raise ValueError("герой мёртв")
    if hit_dice < 0:
        raise ValueError("hit_dice не может быть отрицательным")
    if hit_dice > sum(pool.current for _, pool, _ in hit_dice_pools(hero.creature)):
        raise ValueError("не хватает костей хитов")
    healed = 0
    for _ in range(hit_dice):
        _, pool, faces = next(p for p in hit_dice_pools(hero.creature) if p[1].current > 0)
        amount = max(0, rng.d(faces) + ability_mod(hero, "con"))
        healed += heal(hero, amount)
        pool.current -= 1
    recover_pools(hero, registry, "short_rest")
    clock.advance(short_rest_seconds(cfg))
    return healed


def long_rest(hero, registry, clock, cfg) -> None:
    if hero.status == "dead":
        raise ValueError("герой мёртв")
    creature = hero.creature
    if creature.hp_current == 0:
        # SRD 5.2: для длинного отдыха нужен хотя бы 1 HP
        raise ValueError("длинный отдых невозможен при 0 HP")
    heal(hero, creature.hp_max - creature.hp_current)
    # кости хитов и ячейки заклинаний восстанавливаются полностью
    # жрец с богом ≤ -6: ячейки высшего круга не восстанавливаются (ТЗ 4.2)
    locked = divine.locked_slot_pool(hero)
    for name, pool in creature.resources.items():
        if name.startswith(LONG_REST_FULL) and name != locked:
            pool.current = pool.max
    recover_pools(hero, registry, "long_rest")
    remove_exhaustion(creature)
    for effect in hero_effects(hero, registry):
        is_inspiration = effect.resource == "heroic_inspiration" and effect.when == "long_rest"
        if effect.type == "resource" and is_inspiration:
            hero.heroic_inspiration = True
    clock.advance(long_rest_seconds(cfg))
    hero.long_rest_end_s = clock.now_s
