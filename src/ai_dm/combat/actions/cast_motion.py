from ai_dm.combat.actions.cast_guards import place, place_pairs
from ai_dm.combat.actions.cast_support import hold_concentration
from ai_dm.core.events import DomainEvent
from ai_dm.rules.derived import spell_save_dc
from ai_dm.rules.spellcasting import effect_of

# Газообразная форма: сопротивление этим типам урона и преимущество на эти спасброски
GAS_RESISTS = ("bludgeoning", "piercing", "slashing")
GAS_SAVES = ("str", "dex", "con")


def cast_mirror_image(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    # образы на срок по часам мира (не концентрация); кости разбития -- mirror.deflect
    images = effect_of(spell, "mirror_image").value
    place(engine, ref, spell, target_ref, {"mirror_image": {"images": images}})
    return []


def cast_blink(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    # метка Мерцания на срок по часам мира; бросок в конце каждого хода -- blink.end_turn
    place(engine, ref, spell, target_ref, {"blink": {}})
    return []


def cast_flight(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    # Полёт и Газообразная форма на согласного, Левитация на врага (спасбросок, провал -- поднят)
    mode = effect_of(spell, "flight").mode
    hold_concentration(engine, ref, spell, circle)
    pairs = [("flying", {})]
    if mode == "levitate":
        save = effect_of(spell, "save_effect")
        dc = spell_save_dc(engine.heroes[ref], engine.registry)
        if engine.save(target_ref, save.ability, dc).outcome == "success":
            return []
        pairs = [("levitating", {})]
    if mode == "gaseous":
        pairs = [("gaseous", {})]
        pairs += [("resist", {"damage_type": t}) for t in GAS_RESISTS]
        pairs += [
            ("modifier", {"target": "saving_throw", "ability": a, "mode": "advantage"})
            for a in GAS_SAVES
        ]
    place_pairs(engine, ref, spell, target_ref, pairs)
    return []


def cast_size(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    # вариант (enlarge | reduce) уже подставлен в mode; чужой стороне -- спасбросок Телосложения.
    # Размер -- метка size, +1d4 / −1d4 к урону оружием -- обычный модификатор weapon_damage
    effect = effect_of(spell, "size")
    hold_concentration(engine, ref, spell, circle)
    if engine.part(target_ref).side != engine.part(ref).side:
        save = effect_of(spell, "save_effect")
        dc = spell_save_dc(engine.heroes[ref], engine.registry)
        if engine.save(target_ref, save.ability, dc).outcome == "success":
            return []
    damage = {"target": "weapon_damage", "dice": effect.dice}
    step = 1
    if effect.mode == "reduce":
        damage["mode"] = "penalty"
        step = -1
    place(engine, ref, spell, target_ref, {"size": {"step": step}, "modifier": damage})
    return []
