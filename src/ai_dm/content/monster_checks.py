from ai_dm.content.models.common import DAMAGE_TYPE_WORDS
from ai_dm.core.dice import DiceParseError, parse_dice


def check_dice(id, field, dice, bad) -> None:
    if dice is None:
        return
    try:
        parse_dice(dice)
    except DiceParseError:
        bad("monster", id, field, f"не кубики '{dice}'")


def check_type(id, field, damage_type, bad) -> None:
    if damage_type is not None and damage_type not in DAMAGE_TYPE_WORDS:
        bad("monster", id, field, f"неизвестный тип урона '{damage_type}'")


def check_action(action, id, has, bad) -> None:
    if action.weapon_id is not None and not has("weapon", action.weapon_id):
        bad("monster", id, "actions", f"неизвестное оружие '{action.weapon_id}'")
    check_type(id, "actions", action.damage_type, bad)
    check_type(id, "actions", action.extra_damage_type, bad)
    for dice in (action.damage_dice, action.advantage_damage_dice, action.extra_damage_dice):
        check_dice(id, "actions", dice, bad)
    rider = action.on_hit
    if rider is None:
        return
    if not has("condition", rider.condition):
        bad("monster", id, "on_hit", f"неизвестное состояние '{rider.condition}'")
    check_type(id, "on_hit", rider.damage_type, bad)
    check_dice(id, "on_hit", rider.dice, bad)


def check_monster_actions(monster, id, has, bad) -> None:
    # оружие, типы урона, кубики и состояние эффектов при попадании, предсмертный взрыв
    for action in monster.actions:
        check_action(action, id, has, bad)
    burst = monster.death_burst
    if burst is not None:
        check_type(id, "death_burst", burst.damage_type, bad)
        check_dice(id, "death_burst", burst.dice, bad)
