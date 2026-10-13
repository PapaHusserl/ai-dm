from ai_dm.combat.actions import cast, parley
from ai_dm.combat.engine import CombatEngine, CombatRoundLimit
from ai_dm.core.events import DomainEvent
from ai_dm.core.rng import Rng
from ai_dm.game.controllers import MasterChoiceController, PlayerController
from ai_dm.game.scene import hero_of
from ai_dm.rules.derived import ac_summary, clock_text
from ai_dm.rules.inventory import effects_line
from ai_dm.rules.xp import combat_xp
from ai_dm.state.session import LastCombat


def is_finished(state) -> bool:
    # hero_dying: герой лежит, но бой ещё идёт
    return state.outcome not in (None, "hero_dying")


def wakes_up(engine, hero_id) -> bool:
    # упавший герой в свой шаг бросает спасбросок от смерти; натуральная 20 -- он в сознании,
    # и ход переходит к игроку (герой действует в этот же ход). Остальное -- как engine.step()
    state = engine.state
    events = [DomainEvent(type="turn_started", data={"round": state.round, "id": hero_id})]
    engine.log(f"--- раунд {state.round}, ход: {engine.name(hero_id)} ---")
    events += engine.start_turn(hero_id)
    engine.finish(events)
    if engine.is_over:
        return True
    if engine.is_capable(hero_id):
        state.turn_started_for = hero_id
        return True
    engine.expire("end_of_turn", hero_id)
    engine.next_turn()
    return False


def advance_until_player(engine, hero_id) -> list[str]:
    # ходы остальных до боеспособного героя или конца боя; героя не трогает
    start = len(engine.state.log)
    state = engine.state
    while not engine.is_over:
        if state.round > engine.cfg.combat.max_rounds:
            raise CombatRoundLimit(f"бой не кончился за {engine.cfg.combat.max_rounds} раундов")
        current = state.initiative_order[state.turn_index]
        if current == hero_id and engine.is_capable(hero_id):
            break
        down = engine.part(hero_id).status == "down"
        if current == hero_id and down and wakes_up(engine, hero_id):
            break
        engine.step()
    return state.log[start:]


def make_engine(ctx, session, run_id, world_text, player):
    # движок на состоянии боя из бандла; герой -- player, ключевые NPC -- через модель
    bundle = ctx.bundle
    hero = hero_of(bundle)
    state = bundle.session.active_combat
    controllers = {hero.id: player}
    for part in state.participants:
        if part.controller == "external" and part.ref != hero.id:
            controllers[part.ref] = MasterChoiceController(
                ctx, session, run_id=run_id, world_text=world_text
            )
    engine = CombatEngine(
        state, bundle.world, {hero.id: hero}, ctx.registry, ctx.cfg, ctx.rng, controllers
    )
    for controller in controllers.values():
        controller.attach(engine)
    chapter = bundle.session.current_chapter
    if chapter is not None:
        engine.chapter_id = chapter.id
    scene = bundle.session.current_scene
    if scene is not None:
        engine.scene_id = scene.id
    return engine


def start_fight(ctx, session, run_id, world_text) -> list[str]:
    # после start_combat: бросок инициативы и ходы остальных до героя
    engine = make_engine(ctx, session, run_id, world_text, PlayerController())
    engine.start()
    advance_until_player(engine, hero_of(ctx.bundle).id)
    return list(engine.state.log)


def preview_engine(bundle, registry, cfg):
    # движок на одноразовой копии: бандл и RNG не меняются
    work = bundle.model_copy(deep=True)
    rng = Rng.from_state(work.world.rng)
    hero = hero_of(work)
    engine = CombatEngine(
        work.session.active_combat, work.world, {hero.id: hero}, registry, cfg, rng
    )
    if work.session.active_combat.turn_started_for != hero.id:
        engine.start_turn(hero.id)
    return engine, hero


def preview_turn(bundle, registry, cfg):
    # действия героя и остаток его хода
    engine, hero = preview_engine(bundle, registry, cfg)
    return engine.available_actions(hero.id), engine.part(hero.id).turn


def preview_screen(bundle, registry, cfg):
    # варианты, остаток хода и недоступные заклинания героя -- одним preview-движком
    engine, hero = preview_engine(bundle, registry, cfg)
    inert = [spell.name for spell in cast.inert_spells(engine, hero.id)]
    return engine.available_actions(hero.id), engine.part(hero.id).turn, inert


def inert_spell_names(bundle, registry, cfg) -> list[str]:
    # названия заклинаний героя без механики в бою; в нумерацию меню не входят
    engine, hero = preview_engine(bundle, registry, cfg)
    return [spell.name for spell in cast.inert_spells(engine, hero.id)]


def concentration_line(bundle, registry, cfg) -> str:
    # «Концентрация: Метка охотника → Стражник»; пусто, если героя ничто не держит
    hero = hero_of(bundle)
    held = hero.creature.concentration
    if held is None:
        return ""
    spell_id = held.spell_id
    line = "Концентрация: " + registry.get("spell", spell_id).name
    if bundle.session.active_combat is not None:
        engine, hero = preview_engine(bundle, registry, cfg)
        names = engine.concentration_targets(hero.id).get(spell_id, [])
        if names:
            line += " → " + ", ".join(names)
    if held.until_s is not None:
        line += " до " + clock_text(held.until_s)
    return line


def hero_ac_text(bundle, registry) -> str:
    # «КД 17 (Каменная Кожа до 03:12)»
    return ac_summary(hero_of(bundle), registry, bundle.world.clock.now_s)


def hero_effects_line(bundle, registry) -> str:
    return effects_line(hero_of(bundle), registry, bundle.world.clock.now_s)


def preview_options(bundle, registry, cfg):
    return preview_turn(bundle, registry, cfg)[0]


def option_list(bundle, registry, cfg) -> list[dict]:
    # варианты героя для промпта: [{id, label}]
    return [
        {"id": option.id, "label": option.label, "cost": option.cost}
        for option in preview_options(bundle, registry, cfg)
    ]


def next_options(bundle, registry, cfg) -> list[dict]:
    # варианты следующего хода героя после хода остальных; бой кончился или герой лежит -- пусто
    state = bundle.session.active_combat
    if state is None or is_finished(state):
        return []
    hero = hero_of(bundle)
    for part in state.participants:
        if part.ref == hero.id and (part.status != "active" or hero.creature.hp_current <= 0):
            return []
    return option_list(bundle, registry, cfg)


def part_creature(bundle, part):
    # состояние существа участника-не героя: своё (безымянный) или из записи NPC
    if part.creature is not None:
        return part.creature
    return bundle.world.npcs[part.ref].creature


def has_parley_flag(bundle, part, flag_id) -> bool:
    return any(e.id == flag_id for e in part_creature(bundle, part).active_effects)


def settle_parley(bundle, cfg) -> None:
    # итоги переговоров для именованных NPC: сдался +10, перешёл +20, оскорблён -10 к отношению,
    # в пределах [attitude] per_scene; зовётся до finish_combat (тот убирает метки)
    state = bundle.session.active_combat
    scene = bundle.session.current_scene
    spent = {}
    if scene is not None:
        spent = scene.attitude_spent
    for part in state.participants:
        npc = bundle.world.npcs.get(part.ref)
        if npc is None or part.monster_id is None:
            continue
        # исходы взаимоисключающи (одна попытка на цель); при совпадении сильнее то, что ниже
        # по тексту: оскорблён > перешёл > сдался
        delta = 0
        if part.status == "surrendered":
            delta = cfg.parley.surrender_attitude
        if has_parley_flag(bundle, part, "parley_defected"):
            delta = cfg.parley.defect_attitude
        if has_parley_flag(bundle, part, "parley_offended"):
            delta = cfg.parley.offended_attitude
        left = max(0, cfg.attitude.per_scene - spent.get(npc.id, 0))
        amount = min(abs(delta), left)
        if delta < 0:
            amount = -amount
        before = npc.attitude
        npc.attitude = max(-100, min(100, npc.attitude + amount))
        spent[npc.id] = spent.get(npc.id, 0) + abs(npc.attitude - before)


def finish_combat(bundle, registry) -> str:
    # опыт и добыча за врагов dead/down/fled/surrendered и перебежчиков, а при ended_by_master
    # и за оставшихся на ногах (сдались), если бой кончился без поражения и смерти героя
    # (victory, fled, ended_by_master).
    # Побеждённые запоминаются в last_combat для gold loot_individual.
    # Сброс боя; флаг combat_ended уже поставил движок
    state = bundle.session.active_combat
    bundle.session.last_combat = None
    # перебежчики и сдавшиеся -- как побеждённые; метки переговоров на NPC после боя не нужны
    defected = [
        p.ref for p in state.participants
        if p.monster_id is not None and has_parley_flag(bundle, p, "parley_defected")
    ]
    for p in state.participants:
        if p.monster_id is not None:
            creature = part_creature(bundle, p)
            creature.active_effects = [
                e for e in creature.active_effects if e.id not in parley.FLAG_IDS
            ]
    if state.outcome in ("victory", "fled", "ended_by_master") and hero_of(bundle).status != "dead":
        defeated = [
            p.monster_id for p in state.participants
            if p.side == "enemies"
            and (
                p.status in ("dead", "down", "fled", "surrendered")
                or state.outcome == "ended_by_master"
            )
        ]
        # перебежчики дают опыт, но не лут: они на стороне героя
        turned = [p.monster_id for p in state.participants if p.ref in defected]
        hero_of(bundle).sheet.xp += combat_xp(defeated + turned, registry)
        lair = next(
            (g.lair_location_id for g in state.groups.values() if g.lair_location_id), None
        )
        bundle.session.last_combat = LastCombat(
            defeated=defeated, lair_location_id=lair, gear=state.gear
        )
    bundle.session.active_combat = None
    return state.outcome
