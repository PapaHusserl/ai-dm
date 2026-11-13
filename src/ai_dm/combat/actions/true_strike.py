from ai_dm.combat import ammo
from ai_dm.combat.actions import attack
from ai_dm.content.models.common import EffectSpec
from ai_dm.core.events import DomainEvent
from ai_dm.rules.derived import (
    ability_part,
    spell_attack_bonus,
    spell_attack_parts,
    spellcasting_ability,
)

# с этого уровня попадание добавляет 1d6 излучением
RADIANT_LEVEL = 5


def strike_refs(engine, ref) -> list[str]:
    # цели -- как у пункта «Атака» главным оружием: без боеприпасов целей нет, недосягаемые отсечены
    info = attack.attacks_of(engine, ref)[0]
    if not ammo.can_shoot(engine, ref, info):
        return []
    return [
        t for t in attack.attack_targets(engine, ref)
        if attack.base_advantage(engine, ref, t, info) is not None
    ]


def cast_true_strike(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    # атака главным оружием с заклинательной характеристикой вместо Силы или Ловкости
    hero = engine.heroes[ref]
    info = attack.attacks_of(engine, ref)[0]
    ability = ability_part(hero, spellcasting_ability(hero, engine.registry))
    info.bonus = spell_attack_bonus(hero, engine.registry)
    info.bonus_parts = spell_attack_parts(hero, engine.registry)
    info.damage_bonus = ability[1]
    info.damage_parts = [ability]
    if hero.sheet.level >= RADIANT_LEVEL:
        radiant = EffectSpec(type="extra_damage", dice="1d6", damage_type="radiant")
        info.extra = [(spell.name, radiant)]
    engine.log(f"  {spell.name}: {info.name}, бонус заклинаний")
    return attack.attack(engine, ref, target_ref, info)
