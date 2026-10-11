from dataclasses import dataclass

from ai_dm.protocol.decision import Invalid
from ai_dm.protocol.handlers.world import rejected
from ai_dm.protocol.hints import allowed, item_ids, merchant_ids, sold_ids
from ai_dm.rules import trade as trade_rules
from ai_dm.rules.inventory import SLOTS, find_item
from ai_dm.rules.loot import rarity_exceeds_cap


@dataclass
class Source:
    # откуда герой покупает: стек торговца или держатель сюжетного предмета (или ни то ни другое)
    cost_cp: int
    quality: str | None
    cap: int
    stack: object = None
    holder: object = None


def merchant_base_problem(ctx, request, npc):
    # общая часть trade и haggle: бой, NPC, отказ торговать; qty (если есть) проверяет вызывающий
    problem = scene_problem(ctx, request, npc)
    if problem is not None:
        return problem
    return refusal_problem(ctx, npc)


def scene_problem(ctx, request, npc):
    if ctx.bundle.session.active_combat is not None:
        return Invalid(code="in_combat", message="во время боя не торгуют")
    return npc_problem(ctx, request, npc)


def refusal_problem(ctx, npc):
    if trade_rules.refuses(npc.attitude, ctx.cfg):
        return rejected(
            f"{npc.name} отказывается торговать",
            f"{npc.name} отказывается торговать с героем: опиши отказ по факту.",
        )
    return None


def merchant_problem(ctx, request, npc):
    # Invalid/rejected, если торговать нельзя, иначе None
    problem = scene_problem(ctx, request, npc)
    if problem is not None:
        return problem
    if request.direction != "list" and request.qty < 1:
        return Invalid(code="bad_amount", message="количество должно быть не меньше 1")
    return refusal_problem(ctx, npc)


def npc_problem(ctx, request, npc):
    here = merchant_ids(ctx.bundle.world, ctx.hero.location_id)
    if npc is None:
        return Invalid(
            code="unknown_npc", message=f"нет NPC {request.npc_id!r}" + allowed(here)
        )
    if npc.status != "alive" or npc.location_id != ctx.hero.location_id:
        return Invalid(
            code="npc_absent", message=f"{npc.name} сейчас не здесь" + allowed(here)
        )
    if npc.trade is None:
        return Invalid(
            code="not_merchant",
            message=f"{npc.name} не торговец: сначала npc_update с trade_kind" + allowed(here),
        )
    return None


def category_problem(ctx, request, npc):
    # (модели категории, None) или (None, Invalid)
    preset = ctx.cfg.trade.presets[npc.trade.kind]
    by_category = trade_rules.category_models(
        ctx.registry, preset, ctx.hero.sheet.level, ctx.cfg
    )
    models = by_category.get(request.category)
    if models is None:
        return None, Invalid(
            code="unknown_category",
            message=f"{npc.name} не продаёт категорию {request.category!r}"
            + allowed(by_category),
        )
    return models, None


def quality_matches(entry, quality):
    # quality запроса: None -- любой стек, new -- стек без качества
    if quality is None:
        return True
    return entry.quality == (None if quality == "new" else quality)


def too_rare(ctx, found):
    kind, model = found
    level = ctx.hero.sheet.level
    return kind == "item" and model.magic and rarity_exceeds_cap(model, level, ctx.cfg)


def too_rare_rejected(found):
    return rejected(
        f"редкость {found[1].rarity} выше предела для уровня героя",
        "Такой магический предмет герою этого уровня не продать: опиши отказ по факту.",
    )


def not_sold(ctx, request, npc):
    return Invalid(
        code="not_sold",
        message=(
            f"{npc.name} не продаёт {request.item_id!r}" + allowed(sold_ids(ctx, npc))
            + "; полный список -- trade list по category"
        ),
    )


def buy_source(ctx, request, npc):
    # (Source, None) или (None, проблема)
    found = find_item(ctx.registry, request.item_id)
    if found is None:
        return None, not_sold(ctx, request, npc)
    custom = ctx.bundle.world.custom_items.get(request.item_id)
    if custom is None:
        return catalog_source(ctx, request, npc, found)
    # выкуп своего же предмета у держателя: редкость и качество запроса не проверяются
    holder = custom.holder
    if holder is None or holder.kind != "npc" or holder.ref != npc.id:
        return None, not_sold(ctx, request, npc)
    return Source(holder.cost_cp, None, holder.qty, holder=holder), None


def catalog_source(ctx, request, npc, found):
    profile = npc.trade
    stacks = [
        e for e in profile.stock
        if e.item_id == request.item_id and quality_matches(e, request.quality)
    ]
    if stacks:
        if too_rare(ctx, found):
            return None, too_rare_rejected(found)
        stack = min(stacks, key=lambda e: e.cost_cp)
        return Source(stack.cost_cp, stack.quality, stack.qty, stack=stack), None
    preset = ctx.cfg.trade.presets[profile.kind]
    level = ctx.hero.sheet.level
    if request.quality in (None, "new") and trade_rules.merchant_sells(
        *found, preset, level, ctx.cfg
    ):
        return Source(found[1].cost_cp, None, ctx.cfg.limits.give_item_max_qty), None
    if too_rare(ctx, found) and trade_rules.item_category(*found) in preset.categories:
        return None, too_rare_rejected(found)
    return None, not_sold(ctx, request, npc)


def sellable_stacks(hero, request):
    # (все стеки предмета, [(стек, сколько можно продать)]): надетый экземпляр -- самый дорогой
    # стек -- не продаётся
    mine = [e for e in hero.inventory if e.item_id == request.item_id]
    worn = sum(1 for slot in SLOTS if getattr(hero.equipped, slot) == request.item_id)
    dearest = max(mine, key=lambda e: e.cost_cp) if mine else None
    result = []
    for entry in mine:
        free = entry.qty - (worn if entry is dearest else 0)
        if free > 0 and quality_matches(entry, request.quality):
            result.append((entry, free))
    return mine, result


def sell_stack(ctx, request, npc):
    # (стек, сколько можно продать, None) или (None, 0, проблема)
    world = ctx.bundle.world
    found = find_item(ctx.registry, request.item_id)
    if found is None:
        return None, 0, Invalid(
            code="unknown_item",
            message=f"нет предмета {request.item_id!r} в реестре" + allowed(item_ids(ctx.registry)),
        )
    mine, stacks = sellable_stacks(ctx.hero, request)
    if not any(quality_matches(e, request.quality) for e in mine):
        return None, 0, Invalid(
            code="not_in_inventory", message=f"у героя нет предмета {request.item_id!r}"
        )
    if not stacks:
        return None, 0, rejected("предмет надет", "Предмет надет: сначала пусть герой его снимет.")
    preset = ctx.cfg.trade.presets[npc.trade.kind]
    custom = request.item_id in world.custom_items
    if not custom and not trade_rules.merchant_buys(*found, preset):
        return None, 0, rejected(
            f"{npc.name} такое не скупает",
            f"{npc.name} такое не скупает: опиши отказ по факту.",
        )
    stack, free = max(stacks, key=lambda pair: pair[0].cost_cp)
    return stack, free, None
