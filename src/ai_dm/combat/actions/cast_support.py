from ai_dm.combat import downed
from ai_dm.combat.actions.attack import (
    attack_event,
    mark_damage,
    roll_attack,
    roll_damage,
    split_dice,
)
from ai_dm.core.events import DomainEvent
from ai_dm.rules.creatures import end_concentration
from ai_dm.rules.derived import hero_feature_ids, spell_attack_bonus, spell_attack_parts
from ai_dm.rules.spellcasting import effect_of, upcast_dice, upcast_steps
from ai_dm.state.creature import Concentration, Expiry

# по кому бьют: боеспособные, лежащие и сдавшиеся (лежачего бить можно)
TARGETABLE = ("active", "down", "surrendered")


def with_variant(spell, variant):
    # выбранное значение EffectSpec.variants подставляется в эффект (тип урона или
    # характеристика): дальше заклинание читается как обычное
    effects = []
    for effect in spell.effects:
        if effect.variants:
            field = "ability" if effect.type == "modifier" else "damage_type"
            effect = effect.model_copy(update={field: variant, "variants": []})
        effects.append(effect)
    return spell.model_copy(update={"effects": effects})


def scaled_dice(spell, hero, effect, circle) -> str:
    # заговоры растут с уровнем героя, заклинания -- с кругом ячейки
    dice = effect.dice
    if spell.cantrip_scaling is not None:
        for level in sorted(spell.cantrip_scaling):
            if level <= hero.sheet.level:
                dice = spell.cantrip_scaling[level]
    steps = upcast_steps(spell, circle)
    if steps > 0 and spell.upcast.per_slot_level.dice is not None:
        dice = upcast_dice(dice, spell.upcast.per_slot_level.dice, steps)
    return dice


def hold_concentration(engine, ref, spell, circle) -> None:
    # новая концентрация сбрасывает прежнюю; срок -- по часам мира
    caster = engine.creature(ref)
    if caster.concentration is not None:
        end_concentration(caster)
        engine.drop_concentration_effects(ref)
    until_s = None
    if spell.duration_s is not None:
        until_s = engine.world.clock.now_s + spell.duration_s
    caster.concentration = Concentration(spell_id=spell.id, circle=circle, until_s=until_s)


def spell_expiry(engine, ref, spell) -> Expiry | None:
    # срок эффекта на цели: концентрация заклинателя либо часы мира
    if spell.concentration:
        return Expiry(kind="concentration", owner=ref)
    if spell.duration_s is not None:
        return Expiry(kind="seconds", value=engine.world.clock.now_s + spell.duration_s)
    return None


def condition_expiry(engine, ref, spell) -> Expiry:
    # состояние от заклинания: концентрация; мгновенное -- до конца следующего хода заклинателя;
    # иначе раунды боя
    if spell.concentration:
        return Expiry(kind="concentration", owner=ref)
    if spell.duration_s is None:
        return Expiry(kind="end_of_turn", value=1, owner=ref)
    return Expiry(kind="rounds", value=spell.duration_s // engine.cfg.time.round_s)


def is_potent(engine, hero, spell) -> bool:
    # Мощный заговор Воплотителя: половина урона заговора при успешном спасброске или промахе
    return spell.level == 0 and "potent_cantrip" in hero_feature_ids(hero, engine.registry)


def roll_spell_attack(engine, ref, spell, target_ref):
    # бросок атаки заклинанием; дальнобойная при враге рядом -- с помехой
    hero = engine.heroes[ref]
    base_adv = "normal"
    base_note = ""
    if spell.range_kind == "ranged" and engine.enemy_nearby(ref):
        base_adv = "disadvantage"
        base_note = "враг рядом"
    return roll_attack(
        engine, ref, target_ref, spell_attack_bonus(hero, engine.registry), base_adv, spell.name,
        spell_attack_parts(hero, engine.registry), base_note=base_note,
    )


def hit_damage(engine, pair, spell, damage, crit):
    # урон атаки заклинанием; pair = (заклинатель, цель); damage = (кости, тип урона, половина:
    # Мощный заговор при промахе)
    ref, target_ref = pair
    dice, bonus = split_dice(damage[0])
    rolled = roll_damage(
        engine, ref, dice, bonus, crit, label=f"Урон ({spell.name})",
        parts=[(spell.name, bonus)], damage_type=damage[1],
    )
    total = rolled.total
    if damage[2]:
        total //= 2
    dealt = engine.damage(target_ref, total, damage[1])
    dealt = mark_damage(engine, ref, target_ref, crit, dealt)
    engine.log_notes(dealt)
    engine.log(f"  {engine.name(target_ref)}: {engine.hp_text(target_ref)}")
    return dealt


def damage_on_save(engine, pair, spell, total, saved) -> list[DomainEvent]:
    # урон заклинания со спасброском: успех -- половина (mode half, Мощный заговор) или ничего
    ref, target_ref = pair
    save = effect_of(spell, "save_effect")
    effect = effect_of(spell, "damage")
    amount = total
    if saved:
        half = save.mode == "half" or is_potent(engine, engine.heroes[ref], spell)
        amount = total // 2 if half else 0
    dealt = engine.damage(target_ref, amount, effect.damage_type)
    engine.log_notes(dealt)
    engine.log(f"  {engine.name(target_ref)}: {engine.hp_text(target_ref)}")
    events = [attack_event(ref, target_ref, spell.id, "spell", "auto", dealt.final)]
    return events + downed.after_damage(engine, target_ref, dealt, ref)
