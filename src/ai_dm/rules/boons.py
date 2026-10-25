from ai_dm.core.boon_ids import BOON_IDS
from ai_dm.core.clock import DAY
from ai_dm.rules.creatures import live_effects
from ai_dm.rules.hygiene import wash
from ai_dm.state.creature import ActiveEffect, Expiry

# id бонуса услуги -> (название для лога и показа, фраза, если бонус уже действует)
BOONS = {
    "groomed": ("ухожен", "уже действует"),
    "inspired": ("вдохновение", "уже воодушевлён"),
    "washed": ("чист", ""),
}

assert tuple(BOONS) == BOON_IDS, "BOONS и core.boon_ids.BOON_IDS разошлись"

GROOMED_SECONDS = DAY


def grant_boon(ctx, boon_id, npc) -> tuple[str, bool]:
    # выдаёт бонус герою; (строка лога, выдан ли). Повторный бонус не удваивается
    hero = ctx.hero
    world = ctx.bundle.world
    now_s = world.clock.now_s
    name, already = BOONS[boon_id]
    if boon_id == "groomed":
        if any(e.id == "groomed" for e in live_effects(hero.creature, now_s)):
            return f"Бонус: {name} — {already}", False
        # истёкший бонус не копим
        hero.creature.active_effects = [
            e for e in hero.creature.active_effects if e.id != "groomed"
        ]
        hero.creature.active_effects.append(
            ActiveEffect(
                id="groomed", source=f"service:{npc.id}", kind="modifier",
                params={
                    "target": "ability_check", "ability": "cha", "dice": "1d4", "consume": True,
                },
                expires=Expiry(kind="seconds", value=now_s + GROOMED_SECONDS),
            )
        )
    elif boon_id == "inspired":
        if hero.heroic_inspiration:
            return f"Бонус: {name} — {already}", False
        hero.heroic_inspiration = True
    else:
        if wash(world, hero, now_s):
            return f"Бонус: {name} — вонь смыта", True
    return f"Бонус: {name}", True
