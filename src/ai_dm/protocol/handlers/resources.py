from ai_dm.core.duration import Duration
from ai_dm.core.events import DomainEvent
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.protocol.handlers.loot_gear import gold_loot
from ai_dm.protocol.handlers.world import rejected
from ai_dm.protocol.hints import allowed, item_ids, reachable_ids
from ai_dm.rules import custom_items, divine, loot, money, rests, time_ops, xp
from ai_dm.rules.auto_flags import apply_events
from ai_dm.rules.cast_checks import default_cast_check_registry
from ai_dm.rules.damage import roll_hazard
from ai_dm.rules.death_saves import after_damage, is_stable, resolve_out_of_combat
from ai_dm.rules.derived import clock_text
from ai_dm.rules.healing import heal
from ai_dm.rules.inventory import (
    add_catalog_item,
    add_item,
    count_item,
    drink_item,
    find_item,
    remove_item,
)
from ai_dm.rules.inventory import use_item as use_inventory_item
from ai_dm.rules.modifiers import default_modifier_registry
from ai_dm.rules.progression import feature_swap_problem, swap_feature_choice
from ai_dm.rules.spellcasting import (
    add_spell_duration,
    cast_problem,
    effect_of,
    expire_concentration,
    roll_cast_checks,
    roll_heal,
    spell_kind,
    spend_cast,
    start_concentration,
    swap_prepared,
    swap_problem,
)
from ai_dm.state.creature import ActiveEffect, Expiry
from ai_dm.state.hero import InventoryEntry
from ai_dm.state.memory import add_entry
from ai_dm.state.world import CustomItem

PREY_FEATURE = "hunters_prey"
USE_EFFECTS = ("heal", "ac_bonus", "resist")
# строки лога, по которым защиты от повтора находят прошлые начисления в outcomes
XP_LOG = "Опыт: +"
TIME_LOG = "Время идёт: {} с"
TAKE_WORDS = {"given": "Отдано", "lost": "Потеряно", "stolen": "Украдено", "spent": "Израсходовано"}


def clamped(reason, signal, result, log):
    return Decision(
        status="clamped", reason=reason, signal_to_master=signal, report_tag="limit-exceeded",
        result=result, log=log,
    )


def damage(ctx, request):
    hero = ctx.hero
    if hero.status == "dead":
        return Invalid(code="hero_dead", message="герой уже мёртв, урон по нему не применяется")
    severity = request.severity
    cut = False
    if severity == "deadly":
        ref = ctx.rolls.get(request.failed_roll_ref)
        if ref is None or ref.outcome != "fail" or request.failed_roll_ref in ctx.used_rolls:
            severity = "dangerous"
            cut = True
        else:
            ctx.used_rolls.add(request.failed_roll_ref)
    hazard = roll_hazard(
        hero, severity, request.damage_type, ctx.registry, ctx.rng,
        failed_save=(severity == "deadly"),
    )
    log = [hazard.log.text] + hazard.damage.notes
    now_s = ctx.bundle.world.clock.now_s

    def intervene(target):
        # божественное вмешательство (+9) вместо смерти героя
        chapter = ctx.bundle.session.current_chapter
        chapter_id = "" if chapter is None else chapter.id
        scene = ctx.scene
        scene_id = "" if scene is None else scene.id
        return divine.try_intervention(
            target, ctx.bundle.world, ctx.rng, ctx.cfg, chapter_id, scene_id
        )

    after = after_damage(hero, hazard.damage, cause="hazard", now_s=now_s, intervene=intervene)
    if after in ("down", "failure"):
        if after == "down":
            log.append(f"{hero.name} падает без сознания")
        else:
            log.append(f"{hero.name} получает урон лёжа: провал спасброска от смерти")
        after, save_logs = resolve_out_of_combat(
            hero, ctx.registry, ctx.rng, now_s=now_s, cause="hazard", intervene=intervene
        )
        log += save_logs
        log.append(f"Спасброски от смерти вне боя: {after}")
    if after == "saved":
        god = ctx.bundle.world.pantheon[hero.divine.intervention_god]
        log.append(f"{god.name} вмешивается и спасает {hero.name}: 1 HP, бог ждёт услугу")
        add_entry(
            ctx.bundle, "favor", f"{god.name} спас {hero.name} от смерти", [hero.id, god.id]
        )
    if hero.status == "dead":
        event = DomainEvent(type="hero_died", data={"id": hero.id, "cause": "hazard", "by": None})
        apply_events(ctx.bundle.world, [event])
        ctx.events.append(event)
        log.append(f"{hero.name} погиб")
        hero_status = "dead"
    elif is_stable(hero.creature):
        hero_status = "stable"
    else:
        hero_status = "alive"
    result = {
        "damage": hazard.damage.final, "hp": hero.creature.hp_current, "severity": severity,
        "hero_status": hero_status, "death_saves": after,
    }
    if cut:
        return clamped(
            "смертельный урон без проваленного броска этого хода",
            "Смертельный урон возможен только после ещё не использованного проваленного "
            "броска этого хода: применён опасный урон. Опиши последствия по факту.",
            result, log,
        )
    return Decision(status="accepted", result=result, log=log)


def give_item_problem(ctx, request, found):
    # Invalid для неизвестного предмета или неверного количества, иначе None
    if found is None:
        return Invalid(
            code="unknown_item",
            message=f"нет предмета {request.item_id!r} в реестре" + allowed(item_ids(ctx.registry)),
        )
    if request.qty < 1:
        return Invalid(code="bad_amount", message="количество должно быть не меньше 1")
    return None


def give_item(ctx, request):
    found = find_item(ctx.registry, request.item_id)
    problem = give_item_problem(ctx, request, found)
    if problem is not None:
        return problem
    qty = min(request.qty, ctx.cfg.limits.give_item_max_qty)
    scene = ctx.scene
    consumable = found[0] == "item" and any(e.type == "heal" for e in found[1].effects)
    if found[0] == "item" and loot.rarity_exceeds_cap(found[1], ctx.hero.sheet.level, ctx.cfg):
        return clamped(
            f"редкость {found[1].rarity} выше предела для уровня {ctx.hero.sheet.level}",
            "Такой магический предмет герою этого уровня не выдать: предмет не выдан, "
            "опиши находку иначе (обычная вещь или предмет попроще).",
            {"item_id": request.item_id, "qty": 0}, [],
        )
    if consumable and scene is not None:
        left = ctx.cfg.limits.consumables_per_scene - scene.consumables_given
        qty = max(0, min(qty, left))
        if qty == 0:
            return clamped(
                f"лимит расходников за сцену: {ctx.cfg.limits.consumables_per_scene}",
                "В этой сцене больше нельзя выдавать расходники: предмет не выдан, "
                "опиши по факту.",
                {"item_id": request.item_id, "qty": 0}, [],
            )
        scene.consumables_given += qty
    world = ctx.bundle.world
    holder = None
    if request.item_id in world.custom_items:
        holder = custom_items.recover(world, request.item_id)
    if holder is not None and holder.qty < qty:
        # вернуть можно не больше, чем отобрали
        qty = holder.qty
    if holder is None:
        add_catalog_item(ctx.hero, ctx.registry, request.item_id, qty)
        log = [f"Получено: {found[1].name} x{qty}"]
    else:
        add_item(ctx.hero, request.item_id, qty, cost_cp=holder.cost_cp)
        log = [f"Возвращён предмет: {found[1].name} x{qty}"]
    event = DomainEvent(type="item_gained", data={"item": request.item_id, "qty": qty})
    apply_events(world, [event])
    ctx.events.append(event)
    result = {"item_id": request.item_id, "qty": qty}
    if qty < request.qty:
        return clamped(
            f"запрошено {request.qty}, выдано {qty}",
            f"Выдано только {qty} шт. вместо {request.qty}: опиши находку по факту.",
            result, log,
        )
    return Decision(status="accepted", result=result, log=log)


def srd_item_id(registry, name):
    # id предмета реестра (не сюжетного) с таким названием или None
    for kind in ("weapon", "armor", "item"):
        for model in registry.all(kind):
            if model.source != "world" and model.name.casefold() == name.casefold():
                return model.id
    return None


def custom_item_problem(cfg, request, name):
    # Invalid для неверных полей запроса или None
    checks = [
        (
            not name or len(name) > cfg.name_max, "bad_name",
            f"название: от 1 до {cfg.name_max} символов",
        ),
        (
            len(request.description) > cfg.description_max, "bad_description",
            f"описание: не больше {cfg.description_max} символов",
        ),
        (request.qty < 1, "bad_amount", "количество должно быть не меньше 1"),
        (request.cost_cp < 0, "bad_cost", "цена не может быть отрицательной"),
        (
            request.weight_lb is not None and request.weight_lb < 0, "bad_weight",
            "вес не может быть отрицательным",
        ),
    ]
    for wrong, code, message in checks:
        if wrong:
            return Invalid(code=code, message=message)
    return None


def create_custom_item(ctx, request, name, reasons):
    # новый сюжетный предмет в каталоге мира; возвращает (id, цена одной вещи)
    cfg = ctx.cfg.custom_items
    world = ctx.bundle.world
    weight = None
    if request.weight_lb is not None:
        weight = round(request.weight_lb * 100)
    cost_cp = request.cost_cp
    cap = cfg.cost_cap_cp
    if ctx.hero.sheet.level >= cfg.high_from_level:
        cap = cfg.cost_cap_high_cp
    if cost_cp > cap:
        reasons.append(f"цена {cost_cp} выше предела {cap}, взято {cap}")
        cost_cp = cap
    world.custom_item_seq += 1
    item_id = f"custom_{world.custom_item_seq}"
    world.custom_items[item_id] = CustomItem(
        id=item_id, name=name, description=request.description, weight_centilb=weight,
        cost_cp=cost_cp, quest=request.quest, created_s=world.clock.now_s,
    )
    # следующие запросы этого хода видят предмет
    ctx.registry = custom_items.world_registry(ctx.base_registry, world)
    if ctx.scene is not None:
        ctx.scene.custom_created += 1
    return item_id, cost_cp


def custom_item_refusal(ctx, request, name, existing):
    # отказ до выдачи: плохие поля, предмет из реестра, квестовый предмет уже у героя
    problem = custom_item_problem(ctx.cfg.custom_items, request, name)
    if problem is not None:
        return problem
    srd_id = srd_item_id(ctx.registry, name)
    if srd_id is not None:
        return rejected(
            f"{name!r} есть в реестре: {srd_id}",
            f"Предмет {name!r} уже есть в реестре: выдай give_item {srd_id}.",
        )
    if (
        existing is not None and existing.holder is None and existing.quest
        and count_item(ctx.hero, existing.id) > 0
    ):
        return rejected(
            f"{name!r} уже у героя",
            f"Предмет {name!r} уже у героя: повторно не выдаётся, опиши по факту.",
        )
    return None


def give_custom_item(ctx, request):
    cfg = ctx.cfg.custom_items
    world = ctx.bundle.world
    name = request.name.strip()
    existing = next(
        (c for c in world.custom_items.values() if c.name.casefold() == name.casefold()), None
    )
    refusal = custom_item_refusal(ctx, request, name, existing)
    if refusal is not None:
        return refusal
    qty = min(request.qty, ctx.cfg.limits.give_item_max_qty)
    reasons = []
    holder = None
    if existing is not None:
        item_id = existing.id
        cost_cp = existing.cost_cp
        holder = custom_items.recover(world, item_id)
        if holder is not None:
            cost_cp = holder.cost_cp
    elif ctx.scene is not None and ctx.scene.custom_created >= cfg.per_scene:
        return clamped(
            f"лимит новых сюжетных предметов за сцену: {cfg.per_scene}",
            "В этой сцене больше нельзя создавать сюжетные предметы: предмет не выдан, "
            "опиши по факту.",
            {"item_id": None, "qty": 0, "created": False}, [],
        )
    else:
        item_id, cost_cp = create_custom_item(ctx, request, name, reasons)
    add_item(ctx.hero, item_id, qty, cost_cp=cost_cp)
    event = DomainEvent(type="item_gained", data={"item": item_id, "qty": qty})
    apply_events(world, [event])
    ctx.events.append(event)
    word = "Получен предмет" if holder is None else "Возвращён предмет"
    log = [f"{word}: {name} x{qty}"]
    result = {"item_id": item_id, "qty": qty, "created": existing is None}
    if qty < request.qty:
        reasons.append(f"запрошено {request.qty}, выдано {qty}")
    if reasons:
        text = "; ".join(reasons)
        return clamped(
            text, f"Предмет выдан с поправками ({text}): опиши по факту.", result, log,
        )
    return Decision(status="accepted", result=result, log=log)


def use_item(ctx, request):
    hero = ctx.hero
    found = find_item(ctx.registry, request.item_id)
    if found is None:
        return Invalid(
            code="unknown_item",
            message=f"нет предмета {request.item_id!r} в реестре" + allowed(item_ids(ctx.registry)),
        )
    if request.qty < 1:
        return Invalid(code="bad_amount", message="количество должно быть не меньше 1")
    have = count_item(hero, request.item_id)
    if have < 1:
        return Invalid(code="no_item", message=f"у героя нет предмета {request.item_id!r}")
    item = found[1] if found[0] == "item" else None
    if item is None or not item.effects or item.effects[0].type not in USE_EFFECTS:
        return rejected(
            "нечего применить",
            f"У предмета {found[1].name} нет эффекта применения: опиши по факту.",
        )
    now_s = ctx.bundle.world.clock.now_s
    if item.effects[0].type == "heal":
        scene = ctx.scene
        qty = min(request.qty, have)
        left = consumables_left(scene, ctx.cfg.limits)
        if left is not None:
            qty = max(0, min(qty, left))
            if qty == 0:
                return rejected(
                    f"лимит расходников за сцену: {ctx.cfg.limits.consumables_per_scene}",
                    "В этой сцене больше нельзя применять лечебные расходники: "
                    "предмет не применён, опиши по факту.",
                )
            scene.consumables_used += qty
        log = [heal_once(hero, item, ctx.registry, ctx.rng) for _ in range(qty)]
        return Decision(status="accepted", result={"item_id": request.item_id, "qty": qty}, log=log)
    line, until, was_active = drink_once(hero, item, ctx.registry, now_s)
    result = {"item_id": request.item_id, "qty": 1, "until": until}
    if was_active:
        result["extended"] = True
    return Decision(status="accepted", result=result, log=[line])


def consumables_left(scene, limits):
    # сколько лечебных расходников ещё можно применить за сцену; None -- сцены нет, лимита нет
    if scene is None:
        return None
    return limits.consumables_per_scene - scene.consumables_used


def heal_once(hero, item, registry, rng) -> str:
    # одно лечебное зелье: применяет и возвращает строку лога
    healed = use_inventory_item(hero, item.id, registry, rng)
    hp = f"{hero.creature.hp_current}/{hero.creature.hp_max}"
    return f"{hero.name}: {item.name} +{healed} HP, {hp}"


def drink_once(hero, item, registry, now_s):
    # эликсир с эффектом на время: (строка лога, «до hh:mm», действовал ли уже)
    was_active = drink_item(hero, item.id, registry, now_s)
    until = clock_text(now_s + (item.effects[0].duration_s or 0))
    if was_active:
        name = item.short_name or item.name
        return f"{hero.name}: {name} уже действовала — продлена до {until}", until, True
    parts = []
    for effect in item.effects:
        if effect.type == "ac_bonus":
            parts.append(f"+{effect.value} КД")
        elif effect.type == "resist":
            parts.append(f"сопротивление {effect.damage_type}")
    return f"{hero.name}: {item.name} — {', '.join(parts)} до {until}", until, False


def spell_target(ctx, spell, kind, target):
    # цель заклинания: (герой или NPC или None, Invalid или None)
    hero = ctx.hero
    npc = None
    if target is not None and target != "hero":
        npc = ctx.bundle.world.npcs.get(target)
        if npc is None:
            return None, Invalid(
                code="unknown_npc",
                message=f"нет NPC {target!r}" + allowed(ctx.bundle.world.npcs),
            )
        if npc.status != "alive" or npc.location_id != hero.location_id:
            return None, Invalid(
                code="bad_target", message=f"{npc.name} сейчас не рядом с героем или не жив"
            )
    if kind == "mark" and npc is None:
        return None, Invalid(code="bad_target", message=f"{spell.name} нужна цель: NPC в локации")
    if kind in ("heal", "buff") and npc is not None and npc.creature is None:
        return None, Invalid(
            code="bad_target", message=f"у {npc.name} нет состояния здоровья: цель не подходит"
        )
    if npc is not None:
        return npc, None
    return hero, None


def cast_spell(ctx, request):
    hero = ctx.hero
    if hero.status == "dead":
        return Invalid(code="hero_dead", message="герой мёртв и не творит заклинаний")
    if ctx.bundle.session.active_combat is not None:
        return Invalid(
            code="in_combat", message="в бою заклинания творятся пунктами cast:… из списка боя"
        )
    if not ctx.registry.has("spell", request.spell_id):
        return Invalid(
            code="unknown_spell",
            message=f"нет заклинания {request.spell_id!r}" + allowed(ctx.registry.ids("spell")),
        )
    spell = ctx.registry.get("spell", request.spell_id)
    problem = cast_problem(
        hero, spell, request.circle, request.free, ctx.registry, default_cast_check_registry()
    )
    if problem is not None:
        return Invalid(code=problem[0], message=problem[1])
    kind = spell_kind(spell)
    if kind == "rider":
        return Invalid(code="combat_only", message=f"{spell.name} заряжается только в бою")
    if kind == "buff" and request.circle > spell.level:
        return Invalid(
            code="bad_circle",
            message=f"вне боя {spell.name} — базовым кругом: цель одна",
        )
    who, invalid = spell_target(ctx, spell, kind, request.target)
    if invalid is not None:
        return invalid
    world = ctx.bundle.world
    now_s = world.clock.now_s
    spend_cast(hero, ctx.registry, spell, request.free, request.circle)
    if spell.level == 0:
        head = f"{hero.name} читает {spell.name} (заговор)"
    elif request.free:
        head = f"{hero.name} читает {spell.name} ({spell.level} круг, бесплатное применение)"
    else:
        pool = hero.creature.resources[f"spell_slot:{request.circle}"]
        head = (
            f"{hero.name} читает {spell.name} "
            f"({request.circle} круг, ячейки {pool.current}/{pool.max})"
        )
    log = [head]
    result = {"spell_id": spell.id, "circle": request.circle}
    wasted, lines = roll_cast_checks(
        hero, spell, default_cast_check_registry(), ctx.registry, ctx.rng,
        default_modifier_registry(), now_s,
    )
    log += lines
    if wasted:
        log.append("  заклинание не удалось, ячейка потрачена впустую")
        result["wasted"] = True
        return Decision(status="accepted", result=result, log=log)
    if kind == "heal":
        amount, text = roll_heal(spell, hero, ctx.registry, ctx.rng, request.circle)
        healed = heal(who, amount)
        creature = who.creature
        log.append(
            f"{spell.name}: {text} → {who.name} HP {creature.hp_current}/{creature.hp_max}"
        )
        result["healed"] = healed
        result["target"] = who.name
        result["hp"] = creature.hp_current
    elif kind == "mark":
        effect = effect_of(spell, "extra_damage")
        start_concentration(hero, world, spell, request.circle, now_s)
        hero.creature.active_effects.append(
            ActiveEffect(
                id=spell.id, source=hero.id, kind="mark_pending",
                params={"target": who.id, "dice": effect.dice, "damage_type": effect.damage_type},
                expires=Expiry(kind="concentration", owner=hero.id),
            )
        )
        log.append(f"  {spell.name}: цель {who.name}, держится концентрация")
        result["target"] = who.name
        result["concentration"] = spell.id
    else:
        if spell.concentration or kind == "buff":
            start_concentration(hero, world, spell, request.circle, now_s)
            result["concentration"] = spell.id
        if kind == "buff":
            for effect in spell.effects:
                if effect.type == "modifier":
                    creature = who.creature
                    creature.active_effects.append(
                        ActiveEffect(
                            id=spell.id, source=hero.id, kind="modifier",
                            params={"target": effect.target, "dice": effect.dice},
                            expires=Expiry(kind="concentration", owner=hero.id),
                        )
                    )
            result["target"] = who.name
            log.append(f"  {spell.name}: на {who.name}")
    add_spell_duration(hero, spell, now_s)
    if spell.duration_s is not None:
        result["until"] = clock_text(now_s + spell.duration_s)
    return Decision(status="accepted", result=result, log=log)


def take_holder(ctx, request):
    # сюжетный предмет уходит к держателю: NPC из локации героя обязателен, кроме spent
    # возвращает (NPC, None) или (None, проблема)
    world = ctx.bundle.world
    if request.item_id not in world.custom_items or request.why == "spent":
        return None, None
    here = [
        n.id for n in world.npcs.values()
        if n.status == "alive" and n.location_id == ctx.hero.location_id
    ]
    if request.holder_npc_id is None:
        return None, Invalid(
            code="holder_required",
            message="сюжетный предмет отдают NPC: укажи holder_npc_id" + allowed(here),
        )
    npc = world.npcs.get(request.holder_npc_id)
    if npc is None:
        return None, Invalid(
            code="unknown_npc", message=f"нет NPC {request.holder_npc_id!r}" + allowed(here)
        )
    if npc.status != "alive" or npc.location_id != ctx.hero.location_id:
        return None, Invalid(
            code="npc_absent", message=f"{npc.name} сейчас не здесь" + allowed(here)
        )
    return npc, None


def take_item(ctx, request):
    found = find_item(ctx.registry, request.item_id)
    if found is None:
        return Invalid(
            code="unknown_item",
            message=f"нет предмета {request.item_id!r} в реестре" + allowed(item_ids(ctx.registry)),
        )
    if request.qty < 1:
        return Invalid(code="bad_amount", message="количество должно быть не меньше 1")
    have = count_item(ctx.hero, request.item_id)
    if have < 1:
        return Invalid(
            code="not_in_inventory",
            message=f"у героя нет предмета {request.item_id!r}",
        )
    item = found[1] if found[0] == "item" else None
    if (
        request.why == "spent" and item is not None and item.effects
        and item.effects[0].type in USE_EFFECTS
    ):
        return rejected(
            "предмет применяется через use_item",
            f"Герой применяет предмет {item.name}: вызови use_item, а не take_item.",
        )
    world = ctx.bundle.world
    npc, problem = take_holder(ctx, request)
    if problem is not None:
        return problem
    qty = min(request.qty, have)
    removed = remove_item(ctx.hero, request.item_id, qty)
    if npc is not None:
        given = InventoryEntry(item_id=request.item_id, qty=qty, cost_cp=removed[0].cost_cp)
        custom_items.hand_to_npc(world, npc, given, world.clock.now_s)
    log = [f"{TAKE_WORDS[request.why]}: {found[1].name} x{qty}"]
    result = {"item_id": request.item_id, "qty": qty}
    if qty < request.qty:
        return clamped(
            f"запрошено {request.qty}, отдано {qty}",
            f"Отдано только {qty} шт. вместо {request.qty}: опиши по факту.",
            result, log,
        )
    return Decision(status="accepted", result=result, log=log)


def gold_repeated(ctx, amount_cp):
    # turn_seq хода из последних gold_repeat_turns с той же суммой начисления или None
    window = ctx.cfg.limits.gold_repeat_turns
    if window == 0:
        return None
    for turn in ctx.bundle.memory.recent_turns[-window:]:
        if turn.money_delta_cp == amount_cp:
            return turn.turn_seq
    return None


def gold_explicit(ctx, request):
    hero = ctx.hero
    if request.amount_cp is None or request.amount_cp < 1:
        return Invalid(code="bad_amount", message="для explicit нужна amount_cp не меньше 1")
    amount = request.amount_cp
    if request.direction == "gain":
        cap = ctx.cfg.limits.gold_explicit_max_cp_by_level[hero.sheet.level]
        amount = min(amount, cap)
        seq = gold_repeated(ctx, amount)
        if seq is not None:
            return rejected(
                "повтор начисления",
                f"Сумма {money.format_cp(amount)} уже начислена на ходу {seq}; кошель героя "
                f"{money.format_cp(hero.money_cp)}. Повторно не начисляй и не описывай эту "
                "находку снова.",
                report_tag="gold_repeat",
            )
        money.add_money(hero, amount)
        log = [f"Золото: +{money.format_cp(amount)}"]
    else:
        amount = min(amount, hero.money_cp)
        money.spend_money(hero, amount)
        log = [f"Золото: -{money.format_cp(amount)}"]
    result = {"amount_cp": amount, "money_cp": hero.money_cp}
    if amount < request.amount_cp:
        return clamped(
            f"запрошено {request.amount_cp} мм, применено {amount}",
            f"Сумма урезана до {money.format_cp(amount)}: опиши по факту.",
            result, log,
        )
    return Decision(status="accepted", result=result, log=log)


def gold(ctx, request):
    if request.kind == "loot_individual":
        return gold_loot(ctx, request)
    if request.kind == "hoard":
        return gold_hoard(ctx, request)
    return gold_explicit(ctx, request)


def lair_here(ctx):
    # логово, где сейчас герой: локация боя (last_combat.lair_location_id) или локация с тегом
    # lair -- сама локация героя или её предок; нет -- None
    world = ctx.bundle.world
    last = ctx.bundle.session.last_combat
    lair = None if last is None else last.lair_location_id
    place_id = ctx.hero.location_id
    seen = set()
    while place_id is not None and place_id in world.locations and place_id not in seen:
        seen.add(place_id)
        place = world.locations[place_id]
        if place_id == lair or "lair" in place.tags:
            return place_id
        place_id = place.parent_id
    return None


def gold_hoard(ctx, request):
    if request.direction != "gain":
        return Invalid(code="bad_amount", message="hoard только для gain")
    world = ctx.bundle.world
    last = ctx.bundle.session.last_combat
    if ctx.bundle.session.active_combat is not None:
        return Invalid(code="no_combat_loot", message="клад берут не во время боя")
    # после боя с группой-логовом клад берут в её логове, иначе -- в сцене в локации-логове
    lair = None if last is None else last.lair_location_id
    if lair is None:
        lair = lair_here(ctx)
    if lair is None:
        return Invalid(
            code="no_lair", message="клад берут после боя в логове или в сцене в самом логове"
        )
    flag = f"hoard:{lair}"
    if flag in world.flags or (last is not None and last.hoard_looted):
        return Decision(
            status="rejected", reason="клад этого логова уже получен",
            signal_to_master="Клад этого логова уже выдан: больше сокровищ там нет.",
        )
    defeated = [] if last is None else last.defeated
    amount = loot.hoard_treasure(defeated, ctx.rng, ctx.registry, ctx.hero.sheet.level)
    world.flags[flag] = True
    if last is not None:
        last.hoard_looted = True
    money.add_money(ctx.hero, amount)
    return Decision(
        status="accepted", result={"amount_cp": amount, "money_cp": ctx.hero.money_cp},
        log=[f"Клад логова: +{money.format_cp(amount)}"],
    )


def xp_awarded_in_scene(ctx) -> list[int]:
    # turn_seq записей recent_turns текущей сцены, где герою уже начислен опыт
    if ctx.scene is None:
        return []
    return [
        turn.turn_seq for turn in ctx.bundle.memory.recent_turns
        if turn.scene_id == ctx.scene.id
        and any(line.startswith(XP_LOG) for line in turn.outcomes)
    ]


def award_xp(ctx, request):
    limit = ctx.cfg.limits.xp_awards_per_scene
    seqs = xp_awarded_in_scene(ctx) if limit > 0 else []
    if seqs and len(seqs) >= limit:
        return rejected(
            "повтор награды",
            f"За эту сцену опыт уже начислен (ход {seqs[-1]}). Повторно не начисляй; "
            "новая награда — за новую цель в следующей сцене.",
            report_tag="xp_repeat",
        )
    amount = xp.quest_xp(ctx.hero, request.scale, ctx.registry, ctx.cfg)
    ctx.hero.sheet.xp += amount
    return Decision(
        status="accepted", result={"xp": amount, "total_xp": ctx.hero.sheet.xp},
        log=[f"{XP_LOG}{amount} ({request.reason})"],
    )


def concentration_note(ctx, log, result) -> None:
    # после сдвига часов: концентрация героя кончилась по сроку
    ended = expire_concentration(ctx.hero, ctx.bundle.world)
    if ended is not None:
        name = ctx.registry.get("spell", ended).name
        log.append(f"Концентрация: {name} кончилась")
        result["concentration_ended"] = ended


def apply_swap(ctx, request, log, result) -> None:
    # смена подготовленных после длинного отдыха (проверена в rest до отдыха)
    spec = request.prepared_swap
    if spec is None:
        return
    swap_prepared(ctx.hero, ctx.registry, spec.drop, spec.take)
    taken = ", ".join(spec.take) or "ничего"
    dropped = ", ".join(spec.drop) or "ничего"
    log.append(f"Подготовлено: {taken}; снято: {dropped}")
    result["prepared"] = list(ctx.hero.sheet.prepared_of())


def swap_invalid(ctx, request):
    # смена подготовленных не годится: Invalid до отдыха (отдых не применяется)
    spec = request.prepared_swap
    if spec is None:
        return None
    if request.kind != "long":
        return Invalid(code="swap_long_only", message="подготовленные меняют после длинного отдыха")
    problem = swap_problem(ctx.hero, ctx.registry, spec.drop, spec.take)
    if problem is None:
        return None
    return Invalid(code=problem[0], message=problem[1])


def rest_redundant(ctx, request):
    # длинный отдых раньше кулдауна от конца предыдущего: rejected до отдыха;
    # при 0 HP отдых по-прежнему отклоняет long_rest (Invalid)
    hero = ctx.hero
    end_s = hero.long_rest_end_s
    if request.kind != "long" or end_s is None or hero.creature.hp_current == 0:
        return None
    now_s = ctx.bundle.world.clock.now_s
    next_s = end_s + Duration.parse(ctx.cfg.limits.long_rest_cooldown).seconds
    if now_s >= next_s:
        return None
    return rejected(
        "отдых уже был",
        f"Скажи игроку: длинный отдых снова возможен с {clock_text(next_s)}; сейчас можно "
        "короткий отдых (rest short) или просто подремать/подождать — время двигай "
        "advance_time, HP и ресурсы при этом не восстанавливаются.",
        report_tag="rest_repeat",
    )


def rest(ctx, request):
    hero = ctx.hero
    world = ctx.bundle.world
    for check in (rest_redundant, swap_invalid, prey_invalid):
        invalid = check(ctx, request)
        if invalid is not None:
            return invalid
    hit_dice = request.hit_dice or 0
    cut = False
    if request.kind == "short" and hit_dice > 0:
        have = sum(pool.current for _, pool, _ in rests.hit_dice_pools(hero.creature))
        if hit_dice > have:
            hit_dice = have
            cut = True
    try:
        if request.kind == "short":
            healed = rests.short_rest(
                hero, ctx.registry, ctx.rng, world.clock, ctx.cfg, hit_dice=hit_dice
            )
            log = [f"Короткий отдых: восстановлено {healed} HP"]
        else:
            rests.long_rest(hero, ctx.registry, world.clock, ctx.cfg)
            log = ["Длинный отдых: HP и ресурсы восстановлены"]
    except ValueError as error:
        return Invalid(code="rest_impossible", message=str(error))
    result = {"hp": hero.creature.hp_current, "now_s": world.clock.now_s}
    apply_swap(ctx, request, log, result)
    apply_prey(ctx, request, log, result)
    concentration_note(ctx, log, result)
    if cut:
        return clamped(
            f"запрошено костей хитов {request.hit_dice}, потрачено {hit_dice}",
            f"Потрачено только {hit_dice} костей хитов вместо {request.hit_dice}: "
            "опиши отдых по факту.",
            result, log,
        )
    return Decision(status="accepted", result=result, log=log)


def time_repeated(ctx, seconds):
    # turn_seq хода из последних time_repeat_turns, где уже шёл тот же сдвиг времени без пути
    # и дела (в requests только advance_time и offer_choices), или None
    window = ctx.cfg.limits.time_repeat_turns
    if window == 0:
        return None
    idle = {"advance_time", "offer_choices"}
    for turn in ctx.bundle.memory.recent_turns[-window:]:
        if TIME_LOG.format(seconds) in turn.outcomes and set(turn.requests) <= idle:
            return turn.turn_seq
    return None


def time_by_category(ctx, request):
    world = ctx.bundle.world
    if request.category == "hour":
        seq = time_repeated(ctx, ctx.cfg.time.advance_categories["hour"])
        if seq is not None:
            return rejected(
                "повтор часа",
                f"Час уже прошёл на ходу {seq} без пути и дела. Время не двигай: опиши "
                "сцену по факту, а ожидание продолжай только по просьбе героя.",
                report_tag="time_repeat",
            )
    seconds = time_ops.advance_by_category(world.clock, request.category, ctx.cfg)
    result = {"seconds": seconds, "now_s": world.clock.now_s}
    log = [TIME_LOG.format(seconds)]
    concentration_note(ctx, log, result)
    return Decision(status="accepted", result=result, log=log)


def advance_time(ctx, request):
    if (request.category is None) == (request.travel_to is None):
        return Invalid(
            code="category_or_travel_to", message="нужно ровно одно из category и travel_to"
        )
    if request.category is not None:
        return time_by_category(ctx, request)
    return travel(ctx, request)


def travel(ctx, request):
    hero = ctx.hero
    world = ctx.bundle.world
    if request.travel_to not in world.locations:
        return Invalid(
            code="unknown_location",
            message=f"нет локации {request.travel_to!r}"
            + allowed(reachable_ids(world, hero.location_id)),
        )
    here = world.locations.get(hero.location_id)
    route = None
    if here is not None:
        for connection in here.connections:
            if connection.to == request.travel_to:
                route = connection
        if route is None:
            for connection in world.locations[request.travel_to].connections:
                if connection.to == here.id:
                    route = connection
    if route is None:
        return Invalid(
            code="no_route",
            message=f"отсюда нет пути в {request.travel_to!r}"
            + allowed(reachable_ids(world, hero.location_id)),
        )
    seconds = time_ops.travel_seconds(route.distance_m, request.pace or "normal", ctx.cfg)
    world.clock.advance(seconds)
    hero.location_id = request.travel_to
    companions = []
    for npc in world.npcs.values():
        if npc.follows == hero.id and npc.status == "alive":
            npc.location_id = request.travel_to
            companions.append(npc.name)
    event = DomainEvent(type="location_visited", data={"id": request.travel_to})
    apply_events(world, [event])
    ctx.events.append(event)
    name = world.locations[request.travel_to].name
    log = [f"Путь в «{name}»: {seconds} с"]
    if companions:
        log.append("С тобой: " + ", ".join(companions))
    result = {"seconds": seconds, "now_s": world.clock.now_s, "location_id": request.travel_to}
    concentration_note(ctx, log, result)
    return Decision(status="accepted", result=result, log=log)


def prey_invalid(ctx, request):
    # смена Добычи охотника не годится: Invalid до отдыха
    if request.prey_swap is None:
        return None
    problem = feature_swap_problem(ctx.hero, ctx.registry, PREY_FEATURE, request.prey_swap)
    if problem is None:
        return None
    return Invalid(code=problem[0], message=problem[1])


def apply_prey(ctx, request, log, result) -> None:
    # смена Добычи охотника после отдыха (проверена в rest до отдыха)
    if request.prey_swap is None:
        return
    old = ctx.hero.sheet.feature_choices[PREY_FEATURE][0]
    swap_feature_choice(ctx.hero, ctx.registry, PREY_FEATURE, request.prey_swap)
    names = [ctx.registry.get("feature", i).name for i in (request.prey_swap, old)]
    log.append(f"Добыча охотника: {names[0]} (было: {names[1]})")
    result["prey"] = request.prey_swap
