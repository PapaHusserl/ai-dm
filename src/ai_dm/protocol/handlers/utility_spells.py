from ai_dm.combat.actions.cast_conditions import STAGED
from ai_dm.protocol.decision import Invalid
from ai_dm.protocol.hints import allowed
from ai_dm.rules.derived import spell_save_dc
from ai_dm.rules.healing import grant_max_hp
from ai_dm.rules.inventory import count_item, find_item
from ai_dm.rules.roll_pipeline import RollRequest, roll
from ai_dm.rules.spellcasting import (
    defense_effect,
    effect_line,
    effect_of,
    start_concentration,
)
from ai_dm.state.creature import ActiveEffect, AppliedCondition, Expiry


def expiry_of(spell, hero, now_s, fallback_s) -> Expiry:
    # срок эффекта на цели вне боя: концентрация героя либо часы мира
    if spell.concentration:
        return Expiry(kind="concentration", owner=hero.id)
    return Expiry(kind="seconds", value=now_s + (spell.duration_s or fallback_s))


def apply_defense(ctx, spell, who, now_s) -> None:
    # КД, сопротивление, невидимость, помеха атакам по цели; прежнее действие заклинания заменяется
    hero = ctx.hero
    creature = who.creature
    creature.active_effects = [e for e in creature.active_effects if e.id != spell.id]
    creature.conditions = [c for c in creature.conditions if c.source != spell.id]
    expires = expiry_of(spell, hero, now_s, ctx.cfg.time.round_s)
    for effect in spell.effects:
        if effect.type == "invisible":
            creature.conditions.append(
                AppliedCondition(id="invisible", source=spell.id, expires=expires)
            )
            continue
        built = defense_effect(effect, spell)
        if built is None:
            continue
        kind, params = built
        creature.active_effects.append(
            ActiveEffect(id=spell.id, source=hero.id, kind=kind, params=params, expires=expires)
        )


def apply_max_hp(ctx, spell, who, now_s) -> str:
    # Помощь: +N к максимуму и текущим HP на срок заклинания; строка лога
    amount = effect_of(spell, "max_hp").value
    creature = who.creature
    if not grant_max_hp(creature, spell.id, ctx.hero.id, amount, now_s + spell.duration_s):
        return f"  {spell.name}: {who.name} уже под более сильной Помощью, без изменений"
    return f"  {spell.name}: {who.name} +{amount} HP, {creature.hp_current}/{creature.hp_max}"


def apply_condition(ctx, spell, who, now_s) -> list[str]:
    # одна цель: спасбросок цели, при провале -- состояния заклинания; строки лога
    save = effect_of(spell, "save_effect")
    result = roll(
        RollRequest(
            kind="save", actor=who.creature, actor_id=who.id, ability=save.ability,
            dc=spell_save_dc(ctx.hero, ctx.registry), now_s=now_s,
        ),
        ctx.rng, ctx.registry,
    )
    lines = [f"  {who.name}: {result.log.text}"]
    if result.outcome == "success":
        return lines
    conditions = [e.condition for e in spell.effects if e.type == "apply_condition"]
    if len(conditions) > 1 and conditions[-1] == STAGED:
        conditions = conditions[:-1]
    expires = expiry_of(spell, ctx.hero, now_s, ctx.cfg.time.round_s)
    for condition in conditions:
        who.creature.conditions.append(
            AppliedCondition(id=condition, source=ctx.hero.id, expires=expires)
        )
    lines.append(f"  {who.name}: {', '.join(conditions)}")
    return lines


def utility_target(ctx, spell, target):
    # особая цель: предмет инвентаря (Опознание) -> (None, None); тело мёртвого NPC (Покой);
    # None -- цель обычная
    hero = ctx.hero
    if spell.id == "identify" and target and count_item(hero, target) > 0:
        return None, None
    if spell.id != "gentle_repose":
        return None
    npcs = ctx.bundle.world.npcs
    if target not in npcs:
        return None, Invalid(
            code="unknown_npc", message=f"нет NPC {target!r}" + allowed(npcs)
        )
    npc = npcs[target]
    if npc.status != "dead" or npc.creature is None or npc.location_id != hero.location_id:
        return None, Invalid(
            code="bad_target", message=f"{npc.name}: нужно тело мёртвого NPC рядом с героем"
        )
    return npc, None


def identify(ctx, spell, who, target) -> dict:
    # who None -- цель предмет инвентаря: его свойства в ответ
    if who is not None:
        return {}
    model = find_item(ctx.registry, target)[1]
    effects = [effect.type for effect in getattr(model, "effects", [])]
    return {"item": {
        "effects": effects, "magic": getattr(model, "magic", False),
        "rarity": getattr(model, "rarity", None),
    }}


def timed_effect(ctx, spell, carrier, kind, params) -> dict:
    # метка действия заклинания на носителе до конца срока; прежняя того же заклинания заменяется
    carrier.active_effects = [
        e for e in carrier.active_effects if not (e.kind == kind and e.id == spell.id)
    ]
    until = ctx.bundle.world.clock.now_s + spell.duration_s
    carrier.active_effects.append(
        ActiveEffect(
            id=spell.id, source=ctx.hero.id, kind=kind, params=params,
            expires=Expiry(kind="seconds", value=until),
        )
    )
    return {}


def languages(ctx, spell, who, target) -> dict:
    if who.creature is None:
        return {}
    return timed_effect(ctx, spell, who.creature, "languages", {"all": True})


def gentle_repose(ctx, spell, who, target) -> dict:
    return timed_effect(ctx, spell, who.creature, "gentle_repose", {})


def phantom_steed(ctx, spell, who, target) -> dict:
    return timed_effect(ctx, spell, ctx.hero.creature, "travel_fast", {})


# заклинания-utility с привязкой к движку (решение 16): (ctx, заклинание, цель, id цели) -> result
UTILITY_HOOKS = {
    "identify": identify, "gentle_repose": gentle_repose, "phantom_steed": phantom_steed,
    "tongues": languages, "comprehend_languages": languages,
}


def cast_utility(ctx, spell, who, request, result) -> list[str]:
    # без боевого эффекта: концентрация, строка эффекта, привязки; прежняя метка срока заменяется
    hero = ctx.hero
    if spell.concentration:
        now_s = ctx.bundle.world.clock.now_s
        start_concentration(hero, ctx.bundle.world, spell, request.circle, now_s)
        result["concentration"] = spell.id
    hero.creature.active_effects = [
        e for e in hero.creature.active_effects if not (e.kind == "spell" and e.id == spell.id)
    ]
    line = effect_line(spell)
    result["effect"] = line
    hook = UTILITY_HOOKS.get(spell.id)
    if hook is not None:
        result.update(hook(ctx, spell, who, request.target))
    return [f"  {line}"]


def travel_fast_left(hero, now_s) -> int:
    # секунды до конца Призрачного скакуна (0 -- скакуна нет)
    return max(
        [e.expires.value - now_s for e in hero.creature.active_effects
         if e.kind == "travel_fast" and e.expires.value > now_s],
        default=0,
    )


def steed_seconds(hero, now_s, seconds) -> int:
    # путь в `seconds` пешком: вдвое быстрее только в оставшийся срок скакуна (SRD)
    fast_part = min(2 * travel_fast_left(hero, now_s), seconds)
    return fast_part // 2 + (seconds - fast_part)
