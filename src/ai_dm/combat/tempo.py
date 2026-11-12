from ai_dm.combat.actions import cast_conditions, cast_guards
from ai_dm.combat.actions.cast_support import condition_expiry, hold_concentration
from ai_dm.core.events import DomainEvent
from ai_dm.rules.creatures import live_effects
from ai_dm.rules.derived import spell_save_dc
from ai_dm.rules.spellcasting import effect_of
from ai_dm.state.creature import ActiveEffect


def active(engine, ref, mode) -> bool:
    # на существе действует Ускорение (haste) или Замедление (slow)
    now_s = engine.world.clock.now_s
    return any(
        e.kind == "tempo" and e.params["mode"] == mode
        for e in live_effects(engine.creature(ref), now_s)
    )


def start_turn(engine, ref) -> None:
    # Ускорение: лишняя атака и шаг; Замедление: нет реакции, через раунд -- без движения
    turn = engine.part(ref).turn
    name = engine.name(ref)
    if active(engine, ref, "haste"):
        turn.attacks_left += 1
        turn.move += 1
        engine.log(f"Ускорение: {name} — лишняя атака и шаг")
    if active(engine, ref, "slow"):
        turn.reaction = False
        if engine.state.round % 2 == 0:
            turn.move = 0
            engine.log(f"Замедление: {name} медлит")


def slow_marks(engine, ref, spell, target_ref) -> None:
    # провал спасброска Замедления: −2 к КД и метка темпа (Лов −2 и повтор спасброска даёт
    # impose_effects)
    effect = effect_of(spell, "tempo")
    expires = condition_expiry(engine, ref, spell)
    marks = (
        ("ac", {"label": spell.name, "amount": -effect.value, "magic": True}),
        ("tempo", {"mode": "slow"}),
    )
    for kind, params in marks:
        engine.creature(target_ref).active_effects.append(
            ActiveEffect(
                id=spell.id, source=ref, kind=kind, params=params, expires=expires.model_copy()
            )
        )


def cast_tempo(engine, ref, spell, target, circle) -> list[DomainEvent]:
    effect = effect_of(spell, "tempo")
    hold_concentration(engine, ref, spell, circle)
    if effect.mode == "haste":
        kinds = {
            "ac": {"label": spell.name, "amount": effect.value, "magic": True},
            "modifier": {"target": "saving_throw", "ability": "dex", "mode": "advantage"},
            "tempo": {"mode": "haste"},
        }
        cast_guards.place(engine, ref, spell, target, kinds)
        return []
    # Замедление: все существа зоны, кроме заклинателя, бросают Мудрость; провал -- замедлен
    save = effect_of(spell, "save_effect")
    dc = spell_save_dc(engine.heroes[ref], engine.registry)
    for one in cast_conditions.condition_targets(engine, ref, spell, target):
        if engine.save(one, save.ability, dc).outcome != "success":
            cast_conditions.impose_effects(engine, ref, spell, one, dc)
            slow_marks(engine, ref, spell, one)
    return []
