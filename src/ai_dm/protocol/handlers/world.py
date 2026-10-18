from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.protocol.hints import allowed
from ai_dm.rules import divine, uniqueness
from ai_dm.rules.auto_flags import RESERVED_FLAG_PREFIXES, apply_events
from ai_dm.rules.knowledge import note_favor, note_secret, shorten_text
from ai_dm.rules.mortality_guard import remove_creature
from ai_dm.rules.npc_memory import events_full, refresh_weight, remember
from ai_dm.rules.npc_names import looks_like_kind, shown_name
from ai_dm.rules.results import Rejected
from ai_dm.rules.secrets import reveal
from ai_dm.rules.trade import DAY_S
from ai_dm.rules.triggers_eval import event_active
from ai_dm.state.gender import GENDER_WORDS
from ai_dm.state.memory import add_entry
from ai_dm.state.relations import NPC_EVENT_TEXT_MAX, NpcEvent
from ai_dm.state.world import NPC, Connection, DangerMark, GlobalEvent, Location, TradeProfile

MASTER_DEATH_CAUSES = ("goal", "hazard")
# события, которые возникают только из сработавшего триггера (ТЗ 4.1.2)
CAUSED_EVENT_TYPES = ("war", "plague")


def rejected(reason, signal, report_tag=None):
    return Decision(
        status="rejected", reason=reason, signal_to_master=signal, report_tag=report_tag
    )


def set_flag(ctx, request):
    for prefix in RESERVED_FLAG_PREFIXES:
        if request.name.startswith(prefix + ":"):
            return Invalid(
                code="reserved_flag",
                message=f"префикс {prefix}: занят, этот флаг ставит только движок",
            )
    value = request.value
    if value in ("true", "false"):
        value = value == "true"
    ctx.bundle.world.flags[request.name] = value
    log = [f"Флаг {request.name} = {value}"]
    if request.name.startswith("debt_paid:") and value is True:
        # услуга богу выполнена: долг снят, благосклонность разморожена
        key = request.name[len("debt_paid:"):]
        scene = ctx.scene
        if scene is not None and divine.debt_in_scene(ctx.bundle.heroes, key, scene.id):
            return rejected(
                "долг ещё не исполнен",
                "Долг богу нельзя снять в той же сцене, где бог спас героя: услуга ещё не "
                "исполнена. Флаг не поставлен.",
            )
        if divine.pay_debt(ctx.bundle.world, ctx.bundle.heroes, key):
            log.append(f"Долг богу выплачен: {key}")
    return Decision(status="accepted", log=log)


def npc_create(ctx, request):
    world = ctx.bundle.world
    if not 1 <= len(request.means) <= 3:
        return Invalid(code="means_count", message="у NPC от одного до трёх средств")
    if request.location_id is not None and request.location_id not in world.locations:
        return Invalid(
            code="unknown_location",
            message=f"нет локации {request.location_id!r}" + allowed(world.locations),
        )
    problem = new_merchant_problem(ctx, request.trade_kind, request.key)
    if problem is not None:
        return problem
    npc = NPC(
        id=request.id, name=request.name, named=bool(request.named), key=bool(request.key),
        motive=request.motive or "", means=request.means, location_id=request.location_id,
        origin="ai",
    )
    conflicts = uniqueness.check_npc(world, npc, ctx.bundle.heroes)
    if conflicts:
        return rejected(
            "; ".join(conflicts),
            "NPC не создан: " + "; ".join(conflicts) + ". Придумай другое имя и id.",
        )
    world.npcs[npc.id] = npc
    decision = Decision(
        status="accepted", result={"npc_id": npc.id}, log=[f"Новый NPC: {npc.name}"]
    )
    change_identity(npc, request, decision)
    if request.trade_kind is not None:
        make_merchant(ctx, npc, request.trade_kind)
        decision.log.append(f"{npc.name} торгует: {request.trade_kind}")
    return decision


def new_merchant_problem(ctx, kind, key):
    # Invalid/rejected для назначения торговца мастером или None; kind None -- не назначают
    if kind is None:
        return None
    presets = ctx.cfg.trade.presets
    if kind not in presets:
        return Invalid(
            code="unknown_trade_kind", message=f"нет типа торговца {kind!r}" + allowed(presets)
        )
    if key:
        return rejected(
            "ключевого NPC в торговцы превращает только пак",
            "NPC не стал торговцем: ключевых NPC мастер в торговцы не превращает. Опиши иначе.",
        )
    scene = ctx.scene
    if scene is not None and scene.merchants_created >= ctx.cfg.trade.new_merchants_per_scene:
        return rejected(
            f"лимит новых торговцев за сцену: {ctx.cfg.trade.new_merchants_per_scene}",
            "В этой сцене больше нельзя назначать торговцев: опиши иначе.",
        )
    return None


def make_merchant(ctx, npc, kind):
    now_s = ctx.bundle.world.clock.now_s
    preset = ctx.cfg.trade.presets[kind]
    npc.trade = TradeProfile(
        kind=kind, purse_cp=preset.purse_cp, restock_at_s=now_s + ctx.cfg.trade.restock_days * DAY_S
    )
    if ctx.scene is not None:
        ctx.scene.merchants_created += 1


def location_create(ctx, request):
    world = ctx.bundle.world
    if request.parent_id is not None and request.parent_id not in world.locations:
        return Invalid(
            code="unknown_location",
            message=f"нет локации {request.parent_id!r}" + allowed(world.locations),
        )
    connections = []
    for spec in request.connections or []:
        if spec.to not in world.locations:
            return Invalid(
                code="unknown_location",
                message=f"нет локации {spec.to!r}" + allowed(world.locations),
            )
        if spec.distance_m < 0:
            return Invalid(code="bad_amount", message="расстояние не может быть отрицательным")
        connections.append(Connection(to=spec.to, distance_m=spec.distance_m))
    location = Location(
        id=request.id, name=request.name, parent_id=request.parent_id,
        description=request.description or "", connections=connections, origin="ai",
    )
    conflicts = uniqueness.check_location(world, location, ctx.bundle.heroes)
    if conflicts:
        return rejected(
            "; ".join(conflicts),
            "Локация не создана: " + "; ".join(conflicts) + ". Придумай другое имя и id.",
        )
    world.locations[location.id] = location
    return Decision(
        status="accepted", result={"location_id": location.id},
        log=[f"Новая локация: {location.name}"],
    )


def change_attitude(ctx, npc, delta, decision):
    spent = ctx.attitude_spent
    left = max(0, ctx.cfg.attitude.per_scene - spent.get(npc.id, 0))
    amount = min(abs(delta), ctx.cfg.attitude.step, left)
    wanted = amount if delta > 0 else -amount
    before = npc.attitude
    npc.attitude = max(-100, min(100, npc.attitude + wanted))
    # лимит сцены и лог -- по фактическому изменению (у предела ±100 оно меньше)
    applied = npc.attitude - before
    spent[npc.id] = spent.get(npc.id, 0) + abs(applied)
    decision.result["attitude"] = npc.attitude
    decision.log.append(f"Отношение {npc_label(npc)}: {applied:+d} (теперь {npc.attitude})")
    if ctx.scene is not None:
        refresh_weight(npc, ctx.scene)
    if abs(applied) < abs(delta):
        decision.status = "clamped"
        decision.report_tag = "limit-exceeded"
        decision.reason = f"запрошено {delta:+d}, применено {applied:+d}"
        decision.signal_to_master = (
            f"Отношение изменено только на {applied:+d}: опиши реакцию по факту."
        )


def change_memory(ctx, npc, request, decision):
    # событие в память NPC о герое (сцена обязательна: проверено в memory_problem);
    # вес новой записи -- потраченное за сцену отношение (звать после change_attitude)
    scene = ctx.scene
    text = request.memory_text or ""
    short = shorten_text(text, NPC_EVENT_TEXT_MAX)
    event = NpcEvent(kind=request.memory_kind, turn_seq=ctx.turn_seq, text=short)
    remember(npc, scene, event, ctx.cfg.npc_memory)
    decision.log.append(f"{npc_label(npc)} запомнил: {request.memory_kind}")
    if short != text:
        note = f"текст укорочен до {NPC_EVENT_TEXT_MAX}"
        decision.log.append(f"{npc_label(npc)}: {note}")
        decision.reason = f"{decision.reason}; {note}" if decision.reason else note
        decision.signal_to_master = (
            f"{decision.signal_to_master} " if decision.signal_to_master else ""
        ) + f"Память NPC: {note} знаков."
        if decision.status == "accepted":
            decision.status = "clamped"
            decision.report_tag = "text-shortened"


def change_follows(ctx, npc, request, decision):
    # hero -- NPC идёт с героем, none -- отстал; живой NPC обязателен для присоединения
    if request.follows == "hero":
        npc.follows = ctx.hero.id
        decision.log.append(f"{npc_label(npc)} идёт с героем")
    else:
        npc.follows = None
        decision.log.append(f"{npc_label(npc)} остаётся (не идёт с героем)")
    decision.result["follows"] = npc.follows


def npc_label(npc) -> str:
    # имя NPC для логов и сообщений игроку: настоящее имя выжившего боя до знакомства не светится
    return shown_name(npc)


def change_name(npc, request, decision):
    # рассказчик дал безымянному выжившему имя; игроку оно откроется, когда прозвучит в тексте
    npc.name = request.name.strip()
    npc.named = True
    decision.log.append(f"{npc_label(npc)}: получил имя")


def change_identity(npc, request, decision):
    # пол и местоимения: None -- не менять
    # gender "unset" и pronouns "-" (только npc_update) -- сбросить
    if request.gender is not None:
        npc.gender = None if request.gender == "unset" else request.gender
        word = "не задан" if npc.gender is None else GENDER_WORDS[npc.gender]
        decision.log.append(f"{npc_label(npc)}: пол {word}")
    if request.pronouns is not None:
        npc.pronouns = "" if request.pronouns == "-" else request.pronouns
        decision.log.append(f"{npc_label(npc)}: местоимения {npc.pronouns or 'не заданы'}")


def death_refused(ctx, npc, request) -> bool:
    # смерть или уход принимаются: причина goal/hazard и ещё не потраченный бросок этого хода
    evidence = ctx.rolls.get(request.evidence_ref)
    if request.cause not in MASTER_DEATH_CAUSES or evidence is None:
        return True
    return request.evidence_ref in ctx.used_rolls


def change_status(ctx, npc, request, decision):
    world = ctx.bundle.world
    done = remove_creature(
        world, npc.id, request.status, request.cause, by=request.by, text=request.text or ""
    )
    if isinstance(done, list):
        ctx.used_rolls.add(request.evidence_ref)
        apply_events(world, done)
        ctx.events.extend(done)
        decision.log.append(f"{npc_label(npc)}: {request.status} ({request.cause})")
    else:
        decision.log.append(f"{npc_label(npc)}: уже мёртв, ничего не изменилось")
    decision.result["status"] = npc.status


def nothing_to_change(request, *names) -> bool:
    return all(getattr(request, name) is None for name in names)


def update_problem(ctx, npc, request):
    # Invalid/rejected, если изменение не принимается, иначе None
    if nothing_to_change(
        request, "attitude_delta", "status", "follows", "trade_kind", "gender", "pronouns",
        "memory_kind", "memory_text", "name",
    ):
        return Invalid(code="empty_update", message="в npc_update нечего менять")
    if request.follows == "hero" and npc.status != "alive":
        return Invalid(code="npc_not_alive", message=f"{npc_label(npc)} не жив: не идёт с героем")
    if request.trade_kind is not None and request.status is not None:
        return Invalid(
            code="trade_kind_with_status", message="trade_kind и status нельзя в одном запросе"
        )
    return (
        name_problem(ctx, npc, request) or memory_problem(ctx, npc, request)
        or death_problem(ctx, npc, request) or merchant_update_problem(ctx, npc, request)
    )


def name_problem(ctx, npc, request):
    # имя назначается один раз и только безымянному выжившему боя
    if request.name is None:
        return None
    if npc.origin != "engine" or npc.named:
        return Invalid(code="name_locked", message=f"{npc_label(npc)}: имя не меняется")
    name = request.name.strip()
    if not name:
        return Invalid(code="empty_name", message="имя пустое")
    return rejected_name(ctx, npc, name)


def rejected_name(ctx, npc, name):
    # имя совпадает с видом существа или занято -- отказ; иначе None
    if looks_like_kind(ctx.registry, npc, name):
        return rejected(
            f"имя {name!r} совпадает с видом существа",
            f"Имя не назначено: {name!r} — название вида, а не имя. Придумай личное имя.",
        )
    if uniqueness.name_conflict(ctx.bundle.world, ctx.bundle.heroes, name):
        return rejected(
            f"имя {name!r} уже занято",
            f"Имя не назначено: {name!r} уже занято (NPC, бог, фракция или герой). "
            "Придумай другое имя.",
        )
    return None


def memory_problem(ctx, npc, request):
    if request.memory_kind is None:
        if request.memory_text is None:
            return None
        return Invalid(code="memory_text_without_kind", message="memory_text нужен с memory_kind")
    if ctx.scene is None:
        return Invalid(code="no_scene", message="память NPC пишется в сцене, а сцены сейчас нет")
    if not events_full(npc, ctx.scene, ctx.cfg.npc_memory):
        return None
    # до любых изменений: отношение тоже не применяется
    return rejected(
        f"в сцене уже {ctx.cfg.npc_memory.max_events_per_scene} событий памяти",
        f"{npc_label(npc)} больше не запомнит в этой сцене: лимит событий памяти. Опиши по факту.",
        report_tag="limit-exceeded",
    )


def death_problem(ctx, npc, request):
    if request.status is None or not death_refused(ctx, npc, request):
        return None
    # до любых изменений: отношение тоже не применяется
    return rejected(
        "у смерти должна быть причина (goal или hazard) и не потраченный бросок этого хода",
        f"{npc_label(npc)} остаётся жив: смерть или уход без причины goal/hazard и "
        "evidence_ref на не потраченный бросок этого хода не принимаются. Опиши иначе.",
        report_tag="invalid-death",
    )


def npc_update(ctx, request):
    npc = ctx.bundle.world.npcs.get(request.npc_id)
    if npc is None:
        return Invalid(
            code="unknown_npc",
            message=f"нет NPC {request.npc_id!r}" + allowed(ctx.bundle.world.npcs),
        )
    problem = update_problem(ctx, npc, request)
    if problem is not None:
        return problem
    decision = Decision(status="accepted")
    if request.follows is not None:
        change_follows(ctx, npc, request, decision)
    if request.name is not None:
        change_name(npc, request, decision)
    change_identity(npc, request, decision)
    if request.attitude_delta is not None:
        change_attitude(ctx, npc, request.attitude_delta, decision)
    if request.memory_kind is not None:
        change_memory(ctx, npc, request, decision)
    if request.status is not None:
        change_status(ctx, npc, request, decision)
    if request.trade_kind is not None:
        make_merchant(ctx, npc, request.trade_kind)
        decision.log.append(f"{npc_label(npc)} торгует: {request.trade_kind}")
        decision.result["trade_kind"] = request.trade_kind
    return decision


def merchant_update_problem(ctx, npc, request):
    kind = request.trade_kind
    if kind is None:
        return None
    if npc.status != "alive":
        return Invalid(code="npc_not_alive", message=f"{npc_label(npc)} не жив: не торгует")
    if npc.trade is not None:
        return rejected(
            f"{npc_label(npc)} уже торговец",
            f"{npc_label(npc)} уже торгует: тип торговца не меняется.",
        )
    return new_merchant_problem(ctx, kind, npc.key)


def favor_change_for(ctx, owner, key, request, frozen=False):
    # общая часть favor_change: лимиты шага и сцены, хроника, слуга при -9
    world = ctx.bundle.world
    if request.god_id not in world.pantheon:
        return Invalid(
            code="unknown_god",
            message=f"нет бога {request.god_id!r}" + allowed(world.pantheon),
        )
    if request.delta == 0:
        return Invalid(code="bad_amount", message="сдвиг благосклонности не может быть нулевым")
    god = world.pantheon[request.god_id]
    if frozen:
        return rejected(
            "долг не выполнен",
            f"Благосклонность {god.name} заморожена: герой не выплатил долг за спасение. "
            "Опиши иначе.",
        )
    applied = divine.change_favor(
        owner, request.god_id, request.delta, ctx.favor_spent, key, ctx.cfg
    )
    decision = Decision(status="accepted")
    decision.result["mood"] = divine.approx_label(owner.favor[request.god_id])
    decision.result["applied"] = applied
    decision.log.append(
        f"Благосклонность {god.name} к {owner.name}: {applied:+d} ({request.reason})"
    )
    if applied != 0:
        add_entry(
            ctx.bundle, "favor",
            f"{god.name} к {owner.name}: {applied:+d} ({request.reason})",
            [owner.id, god.id],
        )
    if abs(applied) < abs(request.delta):
        decision.status = "clamped"
        decision.report_tag = "limit-exceeded"
        decision.reason = f"запрошено {request.delta:+d}, применено {applied:+d}"
        decision.signal_to_master = (
            f"Благосклонность изменена только на {applied:+d}: опиши реакцию по факту."
        )
    return decision


def favor_change(ctx, request):
    # мастер меняет только благосклонность героя; NPC -- роль world
    if request.target != "hero":
        return Invalid(
            code="hero_only", message="благосклонность NPC меняет только ход мира: target = hero"
        )
    hero = ctx.hero
    decision = favor_change_for(
        ctx, hero, request.god_id, request, frozen=request.god_id in hero.divine.frozen
    )
    if isinstance(decision, Invalid) or decision.status == "rejected":
        return decision
    note_favor(
        hero, ctx.bundle.world.pantheon[request.god_id],
        f"{decision.result['mood']} ({request.reason})", ctx.bundle.world.clock.now_s,
        ctx.cfg.knowledge,
    )
    hated = divine.tier(hero.favor[request.god_id]) == -3
    if hated and divine.add_servant_trigger(ctx.bundle.world, hero, request.god_id, ctx.cfg):
        decision.log.append("Бог пошлёт слугу охотиться на героя")
    return decision


def pray(ctx, request):
    hero = ctx.hero
    world = ctx.bundle.world
    if request.god_id not in world.pantheon:
        return Invalid(
            code="unknown_god",
            message=f"нет бога {request.god_id!r}" + allowed(world.pantheon),
        )
    god = world.pantheon[request.god_id]
    now_s = world.clock.now_s
    if hero.favor.get(request.god_id, 0) < 6:
        return rejected(
            "бог не слышит молитву",
            f"{god.name} не отвечает на молитву: благосклонности недостаточно. "
            "Опиши молитву без чудесного ответа.",
        )
    if request.god_id in hero.divine.frozen:
        return rejected(
            "бог ждёт услугу",
            f"{god.name} не отвечает на молитву: герой не выплатил долг. "
            "Опиши молитву без чудесного ответа.",
        )
    if not divine.can_pray(hero, request.god_id, now_s):
        return rejected(
            "сегодня герой уже молился",
            f"Сегодня герой уже молился: {god.name} больше не отвечает до завтра. "
            "Опиши молитву без чудесного ответа.",
        )
    divine.pray(hero, request.god_id, now_s)
    return Decision(
        status="accepted", result={"god_id": god.id},
        log=[f"Молитва {god.name} услышана: на сегодня преимущество в критический момент"],
    )


def offer_choices(ctx, request):
    if not 2 <= len(request.choices) <= 3:
        return Invalid(code="choices_count", message="нужно два или три варианта")
    ctx.bundle.session.offered_choices = list(request.choices)
    return Decision(status="accepted", log=["Варианты ответа предложены"])


def end_scene(ctx, request):
    if ctx.scene is not None:
        ctx.scene.closed_reason = "end_scene"
        if request.summary:
            ctx.scene.summary = request.summary
    ctx.scene_summary = request.summary
    return Decision(status="accepted", log=["Сцена закрыта"])


def end_chapter(ctx, request):
    ctx.chapter_title = request.title
    chapter = ctx.bundle.session.current_chapter
    if chapter is not None:
        chapter.closed_reason = "end_chapter"
        if request.title:
            chapter.title = request.title
    return Decision(status="accepted", log=["Глава закрыта"])


def reveal_secret(ctx, request):
    npc = ctx.bundle.world.npcs.get(request.npc_id)
    if npc is None:
        return Invalid(
            code="unknown_npc",
            message=f"нет NPC {request.npc_id!r}" + allowed(ctx.bundle.world.npcs),
        )
    secret = next((s for s in npc.secrets if s.id == request.secret_id), None)
    if secret is None:
        return Invalid(
            code="unknown_secret",
            message=f"у {npc.name} нет секрета {request.secret_id!r}"
            + allowed([s.id for s in npc.secrets]),
        )
    if secret.revealed:
        return Decision(status="accepted", log=[f"Секрет {npc.name} уже раскрыт"])
    done = reveal(
        npc, secret.id, ctx.bundle.world, ctx.hero, narrative_confirmed=secret.narrative_ok
    )
    if isinstance(done, Rejected):
        return rejected(
            "ещё рано",
            f"Секрет {npc.name} раскрывать ещё рано: условие не выполнено. Не раскрывай его.",
        )
    ctx.events.extend(done)
    note_secret(ctx.hero, npc, secret, ctx.bundle.world.clock.now_s, ctx.cfg.knowledge)
    return Decision(
        status="accepted", result={"npc_id": npc.id, "secret_id": secret.id, "text": secret.text},
        log=[f"Секрет раскрыт: {npc.name}"],
    )


def warn_danger(ctx, request):
    world = ctx.bundle.world
    if request.location_id not in world.locations:
        return Invalid(
            code="unknown_location",
            message=f"нет локации {request.location_id!r}" + allowed(world.locations),
        )
    now_s = world.clock.now_s
    mark = next((m for m in world.dangers if m.location_id == request.location_id), None)
    if mark is None:
        world.dangers.append(
            DangerMark(location_id=request.location_id, text=request.text, at_s=now_s)
        )
    else:
        mark.text = request.text
        mark.at_s = now_s
    world.flags[f"danger:{request.location_id}"] = True
    name = world.locations[request.location_id].name
    return Decision(
        status="accepted", result={"location_id": request.location_id},
        log=[f"Опасность в «{name}»: {request.text}"],
    )


def event_start(ctx, request):
    world = ctx.bundle.world
    if any(event.id == request.id for event in world.events):
        return Invalid(code="duplicate_event", message=f"событие {request.id!r} уже есть")
    for region in request.regions:
        if region not in world.locations:
            return Invalid(
                code="unknown_location",
                message=f"нет локации {region!r}" + allowed(world.locations),
            )
    if request.event_type in CAUSED_EVENT_TYPES:
        if not request.regions:
            return Invalid(
                code="regions_required",
                message=f"{request.event_type}: нужны regions (id локаций)",
            )
        fired = [item.ref for item in world.fired]
        if request.cause not in fired:
            return rejected(
                "война и чума возникают только из сработавшего триггера (cause)",
                f"Событие {request.event_type} не начато: cause должен быть ref сработавшего "
                "триггера. Опиши иначе.",
            )
    now_s = world.clock.now_s
    event = GlobalEvent(
        id=request.id, type=request.event_type, regions=list(request.regions), started_s=now_s,
        cause=request.cause,
        mortality_multiplier=ctx.cfg.world.event_multipliers.get(request.event_type, 1),
    )
    world.events.append(event)
    add_entry(ctx.bundle, "event", f"Началось событие: {event.type}", [event.id])
    return Decision(
        status="accepted", result={"event_id": event.id}, log=[f"Началось событие: {event.type}"]
    )


def event_end(ctx, request):
    world = ctx.bundle.world
    event = next((e for e in world.events if e.id == request.id), None)
    if event is None:
        return Invalid(
            code="unknown_event",
            message=f"нет события {request.id!r}" + allowed([e.id for e in world.events]),
        )
    now_s = world.clock.now_s
    if not event_active(event, now_s):
        return Decision(status="accepted", log=[f"Событие {event.type} уже закончено"])
    # закрытие запишет в хронику тик, один раз
    event.ends_at_s = now_s
    return Decision(status="accepted", log=[f"Событие закончилось: {event.type}"])


def unsupported_action(ctx, request):
    return Decision(
        status="accepted", report_tag="missing-mechanic",
        log=[f"Нет механики: {request.description}"],
    )
