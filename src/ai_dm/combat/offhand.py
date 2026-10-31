from ai_dm.combat.actions import attack
from ai_dm.rules.inventory import count_item
from ai_dm.state.creature import ActiveEffect, Expiry

# флаг хода: удар второй рукой уже сделан (бонусным действием или с Проворством)
USED = "offhand_used"


def info(engine, ref):
    # удар второй рукой: после атаки лёгким оружием (флаг light_attack), лёгкое оружие в левой руке,
    # другое, чем в атаке (один предмет в обеих руках -- только если их два); None -- ударить нечем
    if not engine.is_hero(ref):
        return None
    hero = engine.heroes[ref]
    off_hand = hero.equipped.off_hand
    flags = {e.id: e for e in engine.creature(ref).active_effects}
    if off_hand is None or "light_attack" not in flags or USED in flags:
        return None
    if flags["light_attack"].params["weapon"] == off_hand and count_item(hero, off_hand) < 2:
        return None
    return attack.weapon_info(engine, hero, off_hand, "off_hand")


def nick(engine, ref, weapon_id) -> bool:
    # Проворство: оружие второй руки выбрано в мастерствах героя
    weapon = engine.registry.get("weapon", weapon_id)
    return weapon.mastery == "nick" and weapon_id in engine.heroes[ref].sheet.weapon_masteries


def cost(engine, ref, weapon_id) -> str | None:
    # free -- Проворство, bonus -- бонусное действие, None -- нечем платить
    if nick(engine, ref, weapon_id):
        return "free"
    return "bonus" if engine.part(ref).turn.bonus else None


def perform(engine, ref, option) -> list:
    one = info(engine, ref)
    if option.cost == "bonus":
        engine.part(ref).turn.bonus = False
    engine.creature(ref).active_effects.append(
        ActiveEffect(
            id=USED, source=ref, kind="flag",
            expires=Expiry(kind="end_of_turn", value=0, owner=ref),
        )
    )
    return attack.attack(engine, ref, option.params["target"], one)
