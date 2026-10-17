import json
from importlib import resources

from ai_dm.llm.types import ChatRequest, Message, SystemBlock, Text, ToolSpec
from ai_dm.master.context import (
    Candidates,
    ContextPlan,
    budget,
    estimate_tokens,
    plan,
    recent_window,
    window_budget,
)
from ai_dm.master.relevance import nearby_locations, npc_reasons, rank_npcs
from ai_dm.protocol.schema import tool_set
from ai_dm.rules import divine
from ai_dm.rules.derived import always_prepared, companion_due, hero_feature_ids
from ai_dm.rules.inventory import entry_name, find_item
from ai_dm.rules.secrets import hidden_secrets
from ai_dm.rules.trade import (
    category_models,
    haggle_state,
    merchant_buy_quote,
    sell_factor,
)

DESCRIPTION_MAX = 120
LOST_ITEMS_MAX = 5
TRADE_STOCK_MAX = 25


def clip(text, limit):
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def dump(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=False)


def identity_data(who):
    # пол и местоимения NPC или героя: ключи только если заданы
    data = {}
    if who.gender is not None:
        data["gender"] = who.gender
    if who.pronouns:
        data["pronouns"] = who.pronouns
    return data


def turn_data(turn):
    # прошлый ход для рассказчика: без requests, rolls и scene_id (их модель копировала)
    return {
        "turn_seq": turn.turn_seq, "at_s": turn.at_s, "player_input": turn.player_input,
        "narration": turn.narration, "outcomes": list(turn.outcomes),
    }


def inventory_data(hero, registry):
    # стек с названием и ценой одной вещи; качество только если оно есть (экономия токенов);
    # у сюжетных предметов мира ещё описание и признак квестового
    result = []
    for i in hero.inventory:
        found = find_item(registry, i.item_id)
        item = {"item_id": i.item_id, "qty": i.qty, "cost_cp": i.cost_cp}
        if found is not None:
            item["name"] = found[1].name
            if found[1].source == "world":
                item["description"] = clip(found[1].description, DESCRIPTION_MAX)
                item["quest"] = found[1].category == "quest"
        if i.quality is not None:
            item["quality"] = i.quality
        result.append(item)
    return result


def items_trail_data(world, session, registry):
    """Украденные квестовые и неразобранное снаряжение боя — только непустые ключи."""
    data = {}
    lost = lost_items_data(world)
    if lost:
        data["lost_items"] = lost
    last_combat = last_combat_data(session.last_combat, registry)
    if last_combat is not None:
        data["last_combat"] = last_combat
    return data


def lost_items_data(world):
    # квестовые вещи героя у других (самые свежие); в контекст идут только квестовые с держателем
    lost = [c for c in world.custom_items.values() if c.quest and c.holder is not None]
    lost.sort(key=lambda c: (-c.holder.since_s, c.id))
    return [
        {
            "item_id": c.id, "name": c.name, "qty": c.holder.qty,
            "holder": {
                "label": c.holder.label, "location_id": c.holder.location_id,
                "since_s": c.holder.since_s,
            },
        }
        for c in lost[:LOST_ITEMS_MAX]
    ]


def gear_names(gear, registry):
    names = []
    for entry in gear:
        name = entry_name(entry, registry)
        names.append(f"{name} ×{entry.qty}" if entry.qty > 1 else name)
    return names


def last_combat_data(last, registry):
    # снаряжение на телах последнего боя; None, если его нет или оно уже забрано
    if last is None or not last.gear or last.gear_looted:
        return None
    return {"gear": gear_names(last.gear, registry)}


def merchant_data(npc, registry, level, cfg, now_s):
    # торговец сцены: кошелёк, коэффициент продажи, до 25 позиций stock и сводка категорий пресета
    preset = cfg.trade.presets[npc.trade.kind]
    stock = []
    for entry in npc.trade.stock[:TRADE_STOCK_MAX]:
        price = merchant_buy_quote(entry.cost_cp, npc, now_s, cfg)
        position = {"item_id": entry.item_id, "price_cp": price}
        if entry.quality:
            position["quality"] = entry.quality
        stock.append(position)
    categories = []
    for category, models in sorted(category_models(registry, preset, level, cfg).items()):
        prices = [merchant_buy_quote(m.cost_cp, npc, now_s, cfg) for m in models]
        categories.append({
            "category": category, "count": len(models),
            "min_cp": min(prices), "max_cp": max(prices),
        })
    return {
        "npc_id": npc.id, "kind": npc.trade.kind, "purse_cp": npc.trade.purse_cp,
        "sell_factor": sell_factor(npc.attitude, cfg), "stock": stock, "categories": categories,
        **haggle_state(npc.trade, now_s),
    }


def trade_data(world, scene_npcs, ctx, level):
    # ключ trade: торговцы сцены; пусто, если их нет
    merchants = [
        merchant_data(world.npcs[n["id"]], ctx.registry, level, ctx.cfg, world.clock.now_s)
        for n in scene_npcs if "merchant" in n
    ]
    return {"trade": merchants} if merchants else {}


def monster_trait_notes(participants, registry):
    # черты монстров боя для рассказчика: «Имя: Черта — текст», строка не длиннее 100
    notes = []
    for p in participants:
        if p.monster_id is None or p.status == "dead":
            continue
        monster = registry.get("monster", p.monster_id)
        for trait in monster.traits:
            feature = registry.get("feature", trait)
            text = feature.description.split(" Движок:")[0]
            line = clip(f"{monster.name}: {feature.name} — {text}", 100)
            if line not in notes:
                notes.append(line)
    return notes


def draft_plan(c):
    # черновик плана для оценки запроса при вытеснении (budget/cap/estimate не используются)
    return ContextPlan(
        budget=0, cap=0, estimate=0, turns=c.turns, scene_summaries=c.scenes,
        npc_ids=c.fixed_npcs + c.npcs, location_ids=c.fixed_locations + c.locations,
        dropped=[], raised=False, overflow=False,
    )


class PromptBuilder:
    def __init__(self, app_cfg, *, role="narrator", model=None):
        self.app_cfg = app_cfg
        self.role = role
        self.role_cfg = self.find_role_cfg(role, model)
        self.model = model or self.role_cfg.model
        self.last_plan = None
        self.rules = (resources.files("ai_dm.master") / "prompts" / "narrator_rules.md").read_text(
            encoding="utf-8"
        )

    def find_role_cfg(self, role, model):
        # effort и max_tokens берутся у роли выбранной модели (основная, альтернативная, профили)
        default = getattr(self.app_cfg.roles, role)
        if model is None or role != "narrator":
            return default
        candidates = [default, self.app_cfg.alternatives.narrator]
        candidates += [profile.narrator for profile in self.app_cfg.profiles.values()]
        for candidate in candidates:
            if candidate.model == model:
                return candidate
        return default

    def build(self, ctx, user_input, mode, *, world_text=""):
        tools = [ToolSpec.model_validate(d) for d in tool_set(mode)]

        def render(c):
            return self.request(ctx, user_input, tools, world_text, draft_plan(c))

        result = plan(
            self.candidates(ctx), render,
            cap=budget(self.app_cfg, self.model),
            window80=window_budget(self.app_cfg, self.model),
            cpt=self.app_cfg.master.cpt_for(self.role_cfg.provider),
        )
        self.last_plan = result
        return self.request(ctx, user_input, tools, world_text, result)

    def static_tokens(self, mode):
        # статика запроса: правила и схемы инструментов режима (общий chars_per_token, без пака)
        cpt = self.app_cfg.master.chars_per_token
        tools = [ToolSpec.model_validate(d) for d in tool_set(mode)]
        rules = estimate_tokens(self.rules, cpt)
        tools = estimate_tokens(json.dumps([t.model_dump(mode="json") for t in tools]), cpt)
        return {"rules": rules, "tools": tools, "total": rules + tools}

    def request(self, ctx, user_input, tools, world_text, context_plan):
        system = [
            SystemBlock(text=self.rules, cache=True),
            SystemBlock(text=self.world_block(ctx, world_text), cache=True),
            SystemBlock(text=self.memory_block(ctx, context_plan), cache=True, stable=False),
        ]
        text = dump(self.state_data(ctx, user_input, context_plan))
        return ChatRequest(
            role=self.role, model=self.model, system=system, tools=tools,
            messages=[Message(role="user", content=[Text(text=text)], cache=True)],
            max_tokens=self.role_cfg.max_tokens, effort=self.role_cfg.effort,
        )

    def candidates(self, ctx):
        # всё, что можно вытеснить, в порядке вытеснения (ТЗ 11); неустранимое -- в fixed_*
        bundle = ctx.bundle
        world = bundle.world
        chapter = bundle.session.current_chapter
        chapter_id = "" if chapter is None else chapter.id
        cfg = self.app_cfg.master
        fixed_locations = []
        locations = []
        nearby = []
        if ctx.hero.location_id is not None:
            place = world.locations[ctx.hero.location_id]
            fixed_locations = [place.id]
            nearby = nearby_locations(world, place)[1:]
            # дальние первыми, при равенстве по id
            far_first = sorted(nearby, key=lambda x: (-x["distance_m"], x["id"]))
            locations = [x["id"] for x in far_first]
        reasons = npc_reasons(bundle, {x["id"] for x in nearby})
        fixed_npcs, npcs = rank_npcs(reasons)
        return Candidates(
            turns=recent_window(bundle.memory, cfg.recent_turns),
            floor=cfg.recent_turns_floor,
            scenes=[s for s in bundle.memory.scenes if s.chapter_id == chapter_id],
            npcs=npcs, locations=locations,
            fixed_npcs=fixed_npcs, fixed_locations=fixed_locations,
        )

    def world_block(self, ctx, world_text):
        world = ctx.bundle.world
        data = {
            "world_id": world.world_id,
            "tone": world.tone.model_dump(mode="json"),
            "settings": world.settings,
            "world_text": world_text,
            "monster_ids": ctx.registry.narrator_monster_ids(),
            "item_ids": [i.id for i in ctx.registry.all("item") if i.source != "world"],
        }
        return dump(data)

    def memory_block(self, ctx, context_plan):
        # память: свёртка игры, выжимки глав, выжимки сцен текущей главы; блок есть всегда (Т-11)
        memory = ctx.bundle.memory
        data = {
            "game_summary": memory.game_summary,
            "chapters": [
                {"number": c.number, "title": c.title, "summary": c.summary}
                for c in memory.chapters
            ],
            "scenes": [
                {"title": s.title, "summary": s.summary} for s in context_plan.scene_summaries
            ],
        }
        return dump(data)

    def divine_data(self, world, hero):
        # благосклонность приблизительно (без чисел), знамения от ±3, молитва, долги
        gods = []
        can_pray = []
        for god_id in sorted(hero.favor):
            favor = hero.favor[god_id]
            god = world.pantheon.get(god_id)
            name = god_id if god is None else god.name
            item = {"id": god_id, "name": name, "mood": divine.approx_label(favor)}
            if favor >= 3:
                item["omens"] = "знамения"
            if favor <= -3:
                item["omens"] = "дурные знамения"
            bonus = divine.season_bonus(god, world.clock.season())
            if bonus > 0:
                item["power"] = "растёт"
            elif bonus < 0:
                item["power"] = "убывает"
            elif god is not None and god.season_power:
                item["power"] = "обычна"
            if god_id in hero.divine.frozen:
                item["frozen"] = "бог ждёт услугу за спасение от смерти"
            gods.append(item)
            if divine.can_pray(hero, god_id, world.clock.now_s):
                can_pray.append(god_id)
        return {"gods": gods, "can_pray": can_pray, "debts": list(hero.divine.debts)}

    def sheet_data(self, hero, registry):
        # класс, подкласс, текстовые и выбранные умения, заклинания, ячейки, спутник
        sheet = hero.sheet
        features = []
        for feature_id in hero_feature_ids(hero, registry):
            feature = registry.get("feature", feature_id)
            # умения с механикой движок считает сам, с вариантами -- мастеру нужен выбранный
            if not feature.effects and not feature.options:
                features.append(
                    {"id": feature.id, "name": feature.name, "description": feature.description}
                )
        data = {
            "class": sheet.class_id,
            "subclass": sheet.subclass_id,
            "features": features,
        }
        if sheet.languages:
            data["languages"] = list(sheet.languages)
        resources = hero.creature.resources
        slots = {}
        for pool_id, pool in resources.items():
            if pool_id.startswith("spell_slot:"):
                slots[pool_id.split(":")[1]] = {"current": pool.current, "max": pool.max}
        if registry.get("class", sheet.class_id).spellcasting is not None:
            data["spells_prepared"] = list(sheet.prepared_of())
            data["spells_always_prepared"] = always_prepared(hero, registry)
            data["spell_slots"] = slots
        if "favored_enemy" in resources:
            pool = resources["favored_enemy"]
            data["favored_enemy"] = {"current": pool.current, "max": pool.max}
        if hero.companions:
            data["companion"] = hero.companions[0].model_dump(mode="json")
        if companion_due(hero, registry):
            data["companion_due"] = True
        return data

    def nudge_signal(self, world):
        # ступень 2 подталкивания: NPC сам выходит на героя (сигнал нарратору, без инструмента)
        nudge = world.sim.nudge
        if nudge.stage == 2 and nudge.contact_npc:
            return f"contact {nudge.contact_npc}"
        return None

    def combat_data(self, ctx):
        session = ctx.bundle.session
        world = ctx.bundle.world
        hero = ctx.hero
        combat = None
        if session.active_combat is not None:
            c = session.active_combat
            combat = {
                "id": c.id, "round": c.round, "outcome": c.outcome,
                "participants": [
                    {"ref": p.ref, "side": p.side, "zone_id": p.zone_id, "status": p.status}
                    for p in c.participants
                ],
            }
            # спутники героя в бою мех. не участвуют (этап 7), но рядом: для повествования
            combat["companions_nearby"] = [
                {"id": n.id, "name": n.name}
                for n in world.npcs.values()
                if n.status == "alive" and n.follows == hero.id
            ]
            combat["companions_nearby"].sort(key=lambda n: n["id"])
            traits = monster_trait_notes(c.participants, ctx.registry)
            if traits:
                combat["monster_traits"] = traits
            if ctx.mode in ("combat_classify", "combat_narrate"):
                combat["options"] = ctx.combat_options or []
        return combat

    def state_data(self, ctx, user_input, context_plan):
        world = ctx.bundle.world
        session = ctx.bundle.session
        hero = ctx.hero
        location = None
        scene_npcs = []
        locations = []
        if hero.location_id is not None:
            place = world.locations[hero.location_id]
            location = {"id": place.id, "name": place.name}
            locations = [
                x for x in nearby_locations(world, place) if x["id"] in context_plan.location_ids
            ]
            for npc in world.npcs.values():
                if npc.status == "alive" and npc.location_id == hero.location_id:
                    item = {"id": npc.id, "name": npc.name, "attitude": npc.attitude}
                    if npc.follows == hero.id:
                        item["follows"] = hero.id
                    item.update(identity_data(npc))
                    if npc.trade is not None:
                        item["merchant"] = npc.trade.kind
                    scene_npcs.append(item)
            scene_npcs.sort(key=lambda n: n["id"])
        known_npcs = []
        for npc_id in sorted(context_plan.npc_ids):
            n = world.npcs[npc_id]
            item = {"id": n.id, "name": n.name, "location_id": n.location_id, "key": n.key}
            item.update(identity_data(n))
            if n.follows == hero.id:
                item["follows"] = hero.id
            known_npcs.append(item)
        secrets = []
        # секреты только у NPC сцены (локация героя: ход идёт)
        for npc, secret in hidden_secrets(world, hero.location_id):
            secrets.append(
                {
                    "npc_id": npc.id, "id": secret.id, "text": secret.text,
                    "note": (
                        "скрыто: играй с учётом, не раскрывай; "
                        "раскрытие — только через reveal_secret"
                    ),
                }
            )
        combat = self.combat_data(ctx)
        hero_data = {
            "name": hero.name,
            "hp": hero.creature.hp_current,
            "hp_max": hero.creature.hp_max,
            "conditions": [c.id for c in hero.creature.conditions],
            "inventory": inventory_data(hero, ctx.registry),
            "gold_cp": hero.money_cp,
            "level": hero.sheet.level,
            "xp": hero.sheet.xp,
        }
        hero_data.update(self.sheet_data(hero, ctx.registry))
        hero_data.update(identity_data(hero))
        if hero.motive:
            hero_data["motive"] = hero.motive
        if hero.means:
            hero_data["means"] = list(hero.means)
        if hero.sheet.background.description:
            hero_data["background_description"] = hero.sheet.background.description
        data = {
            "time": {"date": world.clock.to_date(), "now_s": world.clock.now_s},
            "location": location,
            "locations": locations,
            "known_npcs": known_npcs,
            "hero": hero_data,
            "scene_npcs": scene_npcs,
            "secrets": secrets,
            "divine": self.divine_data(world, hero),
            "nudge": self.nudge_signal(world),
            "combat": combat,
            "recent_turns": [turn_data(t) for t in context_plan.turns],
            "offered_choices": session.offered_choices,
            "player_input": user_input,
        }
        data.update(items_trail_data(world, session, ctx.registry))
        data.update(trade_data(world, scene_npcs, ctx, hero.sheet.level))
        return data
