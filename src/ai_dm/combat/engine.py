from ai_dm.combat import disarm, downed, end, initiative, roles, shove, stealth
from ai_dm.combat.actions import (
    attack,
    cast,
    features,
    improvise,
    item,
    move,
    multiattack,
    parley,
    standard,
)
from ai_dm.combat.actions.attack import roll_damage, split_dice
from ai_dm.combat.available import ActionOption, list_options
from ai_dm.combat.controllers import AutoHeroController, EngineTactics
from ai_dm.combat.monster_traits import PackTacticsSource
from ai_dm.combat.setup import CombatSetupError, validate_start
from ai_dm.combat.zones import CoverSource, ElevationSource
from ai_dm.core.events import DomainEvent
from ai_dm.rules import divine
from ai_dm.rules.auto_flags import apply_events
from ai_dm.rules.cast_checks import default_cast_check_registry
from ai_dm.rules.creatures import live_effects
from ai_dm.rules.damage import DamageResult, apply_damage
from ai_dm.rules.derived import ability_modifier, armor_class, gear_ac, saving_throw_parts
from ai_dm.rules.modifiers import default_modifier_registry
from ai_dm.rules.modifiers.conditions import with_implied
from ai_dm.rules.names import ABILITY_SHORT
from ai_dm.rules.results import Rejected
from ai_dm.rules.roll_pipeline import RollRequest, roll
from ai_dm.state.combat import DecisionPoint, MoveRecord, TurnState
from ai_dm.state.creature import CreatureState


class CombatRoundLimit(RuntimeError):
    pass


# вид варианта -> функция, которая его выполняет
PERFORM = {
    "attack": attack.perform,
    "multiattack": multiattack.perform,
    "cast": cast.perform,
    "move": move.perform,
    "dash": standard.dash,
    "disengage": standard.disengage,
    "dodge": standard.dodge,
    "hide": stealth.hide,
    "help": standard.help_ally,
    "stabilize": standard.stabilize,
    "flee": standard.flee,
    "parley": parley.perform,
    "disarm": disarm.perform,
    "pickup": disarm.pickup,
    "shove": shove.perform,
    "horde_breaker": features.horde_breaker,
    "second_wind": features.second_wind,
    "use_item": item.use,
    "equip": item.swap,
    "unequip": item.swap,
    "transfer_mark": cast.transfer_mark,
    "escape": standard.escape,
    "end_turn": lambda engine, ref, option: [],
}


def ends_now(thing, kind, holder_ref, ref) -> bool:
    # эффект или состояние кончается в этот момент хода ref
    if thing.expires is None or thing.expires.kind != kind:
        return False
    return (thing.expires.owner or holder_ref) == ref


def round_over(thing) -> bool:
    return thing.expires is not None and thing.expires.kind == "rounds" and thing.expires.value <= 0


def survives(thing, kind, holder_ref, ref) -> bool:
    # эффект или состояние остаётся после этого момента хода ref
    if not ends_now(thing, kind, holder_ref, ref):
        return True
    # end_of_turn со value > 0 пропускает столько концов хода владельца (Досада, импровизация)
    if kind == "end_of_turn" and thing.expires.value > 0:
        thing.expires.value -= 1
        return True
    return False


def stand_up(engine, ref) -> None:
    # в начале хода встаёт: лежание не от 0 HP снимается, перемещение хода тратится
    creature = engine.creature(ref)
    if not any(c.id == "prone" and c.source != "0_hp" for c in creature.conditions):
        return
    creature.conditions = [
        c for c in creature.conditions if not (c.id == "prone" and c.source != "0_hp")
    ]
    engine.part(ref).turn.move = 0
    engine.log(f"{engine.name(ref)} встаёт")


def participant_name(state, heroes, ref) -> str:
    if ref in heroes:
        return heroes[ref].name
    name = next(p.name for p in state.participants if p.ref == ref)
    if name == "":
        return ref
    # одинаковые имена различаются номером по порядку участников
    same = [p.ref for p in state.participants if p.name == name and p.ref not in heroes]
    if len(same) > 1:
        return f"{name} {same.index(ref) + 1}"
    return name


class CombatEngine:
    def __init__(self, state, world, heroes, registry, cfg, rng, controllers=None):
        self.held = False
        # конструктор состояние не меняет
        codes = validate_start(state)
        if codes:
            raise CombatSetupError(codes)
        self.state = state
        self.world = world
        self.heroes = heroes
        self.registry = registry
        self.cfg = cfg
        self.rng = rng
        self.modifiers = default_modifier_registry()
        self.modifiers.register(CoverSource())
        self.modifiers.register(ElevationSource())
        self.modifiers.register(PackTacticsSource())
        self.cast_checks = default_cast_check_registry()
        self.controllers = dict(controllers or {})
        # id главы для «раз за главу» у божественного вмешательства; ставит слой game
        self.chapter_id = ""
        self.scene_id = ""
        for p in state.participants:
            if p.ref in self.controllers:
                continue
            if p.controller == "engine":
                self.controllers[p.ref] = EngineTactics(self)
            if p.controller == "auto_hero":
                self.controllers[p.ref] = AutoHeroController(self)

    # вопросы к состоянию

    @property
    def is_over(self) -> bool:
        return self.state.outcome not in (None, "hero_dying")

    def part(self, ref):
        for p in self.state.participants:
            if p.ref == ref:
                return p
        raise KeyError(ref)

    def is_hero(self, ref) -> bool:
        return ref in self.heroes

    def creature(self, ref) -> CreatureState:
        if ref in self.heroes:
            return self.heroes[ref].creature
        own = self.part(ref).creature
        if own is not None:
            return own
        return self.world.npcs[ref].creature

    def actor(self, ref):
        # для запросов конвейера: лист героя или состояние существа
        if ref in self.heroes:
            return self.heroes[ref]
        return self.creature(ref)

    def monster(self, ref):
        return self.registry.get("monster", self.part(ref).monster_id)

    def monster_of(self, ref) -> bool:
        # у участника есть запись монстра (не герой)
        return not self.is_hero(ref) and self.part(ref).monster_id is not None

    def name(self, ref) -> str:
        return participant_name(self.state, self.heroes, ref)

    def hp_text(self, ref) -> str:
        creature = self.creature(ref)
        return f"HP {creature.hp_current}/{creature.hp_max}"

    def is_capable(self, ref) -> bool:
        return self.part(ref).status == "active" and self.creature(ref).hp_current > 0

    def enemy_nearby(self, ref) -> bool:
        # боеспособный враг в зоне участника
        p = self.part(ref)
        for q in self.state.participants:
            if q.side != p.side and q.zone_id == p.zone_id and self.is_capable(q.ref):
                return True
        return False

    def armor_class(self, ref, pierce=False, ignore_magic=False) -> int:
        # pierce -- бронебойная стрела, ignore_magic -- Клинок Северного Ветра
        now_s = self.world.clock.now_s
        if ref in self.heroes:
            return armor_class(self.heroes[ref], self.registry, now_s, pierce, ignore_magic)
        return self.monster_armor_class(ref, pierce, ignore_magic)

    def monster_armor_class(self, ref, pierce, ignore_magic) -> int:
        # число ac статблока; equipment участника/NPC заменяет вклад доспеха и щита статблока
        now_s = self.world.clock.now_s
        monster = self.monster(ref)
        ac = monster.ac
        worn = self.equipment(ref)
        dex = ability_modifier(monster.abilities["dex"])
        if worn is not None:
            ac += gear_ac(self.registry, worn.armor, worn.shield, dex)
            ac -= gear_ac(self.registry, monster.armor, monster.shield, dex)
        if pierce and ac > 12:
            ac = min(ac, 12 + max(dex, 0))
        for effect in live_effects(self.creature(ref), now_s):
            if effect.kind == "ac" and not (ignore_magic and effect.params.get("magic")):
                ac += effect.params["amount"]
        return ac

    def equipment(self, ref):
        # надето на существе: копия у участника (с начала боя), иначе у NPC; None -- по статблоку
        worn = self.part(ref).equipment
        if worn is None and ref in self.world.npcs:
            worn = self.world.npcs[ref].equipment
        return worn

    def tags(self, ref) -> set:
        # теги цели для доп. урона: тип существа, теги монстра и NPC (undead, mor)
        if ref in self.heroes:
            return set()
        result = set()
        if self.part(ref).monster_id is not None:
            monster = self.monster(ref)
            result.add(monster.creature_type)
            result.update(monster.tags)
        if ref in self.world.npcs:
            result.update(self.world.npcs[ref].tags)
        return result

    def log(self, text) -> None:
        self.state.log.append(text)

    def record_move(self, ref, from_zone, to_zone) -> None:
        self.state.moves.append(
            MoveRecord(ref=ref, from_zone=from_zone, to_zone=to_zone, log_index=len(self.state.log))
        )

    def intervene(self, hero):
        # божественное вмешательство (+9) вместо смерти героя; id бога или None
        god_id = divine.try_intervention(
            hero, self.world, self.rng, self.cfg, self.chapter_id, self.scene_id
        )
        if god_id is not None:
            self.log(f"  {hero.name}: {self.world.pantheon[god_id].name} вмешивается и спасает")
        return god_id

    def save(self, ref, ability, dc, cover=0, base_adv="normal"):
        # спасбросок участника (герой с мастерством, монстр -- по модификатору);
        # cover -- бонус укрытия от источника в другой зоне (работает для Ловкости)
        if ref in self.heroes:
            parts = saving_throw_parts(self.heroes[ref], self.registry, ability)
        else:
            score = self.monster(ref).abilities[ability]
            parts = [(ABILITY_SHORT[ability], ability_modifier(score))]
        bonus = sum(value for _, value in parts)
        tags = {}
        if cover:
            tags["cover"] = cover
        request = RollRequest(
            kind="save", actor=self.actor(ref), actor_id=ref, ability=ability, bonus=bonus, dc=dc,
            tags=tags, bonus_parts=parts, base_adv=base_adv,
        )
        result = roll(request, self.rng, self.registry, modifiers=self.modifiers)
        self.log(f"  {self.name(ref)}: спасбросок {ability}: {result.log.text}")
        return result

    def all_creatures(self) -> list:
        return [(p.ref, self.creature(p.ref)) for p in self.state.participants]

    def concentration_targets(self, owner_ref) -> dict:
        # эффекты концентрации владельца: {id заклинания: [имена целей]}
        result = {}
        for ref, creature in self.all_creatures():
            for e in creature.active_effects:
                if e.expires is not None and e.expires.kind == "concentration" \
                        and e.expires.owner == owner_ref:
                    names = result.setdefault(e.id, [])
                    if self.name(ref) not in names:
                        names.append(self.name(ref))
        return result

    def drop_concentration_effects(self, owner_ref) -> None:
        # концентрация владельца кончилась: снимаем его эффекты со всех участников
        for _, creature in self.all_creatures():
            creature.active_effects = [
                e for e in creature.active_effects
                if not (e.expires is not None and e.expires.kind == "concentration"
                        and e.expires.owner == owner_ref)
            ]
            creature.conditions = [
                c for c in creature.conditions
                if not (c.expires is not None and c.expires.kind == "concentration"
                        and c.expires.owner == owner_ref)
            ]

    # истечение эффектов

    def expire(self, kind, ref) -> None:
        # start_of_turn / end_of_turn: снимаем эффекты и состояния, чей хозяин -- ref
        for holder_ref, creature in self.all_creatures():
            creature.active_effects = [
                e for e in creature.active_effects if survives(e, kind, holder_ref, ref)
            ]
            creature.conditions = [
                c for c in creature.conditions if survives(c, kind, holder_ref, ref)
            ]

    def tick_rounds(self) -> None:
        # конец раунда: value уменьшается, при 0 снимается
        for _, creature in self.all_creatures():
            for thing in creature.active_effects + creature.conditions:
                if thing.expires is not None and thing.expires.kind == "rounds":
                    thing.expires.value -= 1
            creature.active_effects = [e for e in creature.active_effects if not round_over(e)]
            creature.conditions = [c for c in creature.conditions if not round_over(c)]

    # бой

    def start(self) -> list[DomainEvent]:
        if self.state.round != 0:
            raise ValueError("бой уже начат")
        # у именованного NPC без состояния оно заводится из записи монстра
        for p in self.state.participants:
            npc = self.world.npcs.get(p.ref)
            if npc is not None and p.creature is None and npc.creature is None:
                hit_points = self.monster(p.ref).hp
                npc.creature = CreatureState(hp_current=hit_points, hp_max=hit_points)
            if npc is not None and p.equipment is None and npc.equipment is not None:
                p.equipment = npc.equipment.model_copy(deep=True)
        cast.convert_pending_marks(self)
        roles.assign_roles(self)
        initiative.roll_initiative(self)
        self.state.round = 1
        self.state.turn_index = 0
        self.log("Бой начался")
        return []

    def available_actions(self, ref) -> list[ActionOption]:
        return list_options(self, ref)

    def finish(self, events) -> list[DomainEvent]:
        # флаги мира по событиям, затем проверка конца боя
        apply_events(self.world, events)
        return events + end.check_end(self)

    def perform(self, ref, option_id) -> list[DomainEvent] | Rejected:
        option = None
        for candidate in self.available_actions(ref):
            if candidate.id == option_id:
                option = candidate
        if option is None:
            return Rejected(reason="not_available", report_tag=None)
        events = PERFORM[option.kind](self, ref, option)
        return self.finish(events)

    def improvise(self, ref, *, skill, category, effect, target=None, zone=None):
        return improvise.improvise(
            self, ref, skill=skill, category=category, effect=effect, target=target, zone=zone
        )

    def parley(self, ref, *, skill, outcome, target=None):
        return parley.parley(self, ref, skill, outcome, target)

    def start_turn(self, ref) -> list[DomainEvent]:
        p = self.part(ref)
        p.turn = TurnState()
        # Убийца колоссов: раз в ход, в том числе при атаке по возможности в чужой ход
        for other in self.state.participants:
            other.turn.colossus_used = False
        self.state.savage_used = []
        events = self.burn(ref)
        self.expire("start_of_turn", ref)
        asleep = "incapacitated" in {c.id for c in with_implied(self.creature(ref))}
        if p.status == "active" and p.side == "enemies" and self.monster_of(ref) and not asleep:
            stealth.search(self, ref)
        if p.status == "active":
            stand_up(self, ref)
            return events + move.hazard_check(self, ref)
        return events + downed.death_save(self, ref)

    def log_notes(self, dealt) -> None:
        # сопротивление, уязвимость, иммунитет, временные HP -- когда итог отличается от броска
        for note in dealt.notes:
            self.log(f"  {note}")

    def damage(self, ref, amount, damage_type) -> DamageResult:
        # единственный путь урона в бою: иммунитеты, сопротивления и уязвимости монстра из статблока
        lists = {"resistances": [], "vulnerabilities": [], "immunities": []}
        if self.monster_of(ref):
            monster = self.monster(ref)
            lists = {
                "resistances": monster.damage_resistances,
                "vulnerabilities": monster.damage_vulnerabilities,
                "immunities": monster.damage_immunities,
            }
        return apply_damage(
            self.actor(ref), amount, damage_type, self.registry,
            now_s=self.world.clock.now_s, **lists,
        )

    def impose(self, ref, condition) -> bool:
        # состояние на существо; монстр с иммунитетом к нему его не получает
        if self.monster_of(ref) and condition.id in self.monster(ref).condition_immunities:
            word = self.registry.get("condition", condition.id).name
            self.log(f"  {self.name(ref)}: иммунитет к состоянию {word}")
            return False
        self.creature(ref).conditions.append(condition)
        return True

    def burn(self, ref) -> list[DomainEvent]:
        # зажигательная стрела: в начале хода цели ещё урон огнём (эффект сам снимается далее);
        # опутанная лозами цель получает урон Опутывающего удара
        events = []
        for effect in list(self.creature(ref).active_effects):
            if effect.kind not in ("burning", "ensnared") or not self.is_capable(ref):
                continue
            label = "Горение"
            if effect.kind == "ensnared":
                label = self.registry.get("spell", effect.id).name
            dice, bonus = split_dice(effect.params["dice"])
            rolled = roll_damage(
                self, effect.source, dice, bonus, False, label=label,
                damage_type=effect.params["damage_type"],
            )
            dealt = self.damage(ref, rolled.total, effect.params["damage_type"])
            self.log_notes(dealt)
            self.log(f"  {self.name(ref)}: {self.hp_text(ref)}")
            events += downed.after_damage(self, ref, dealt, effect.source)
        return events

    def run_controller(self, ref) -> list[DomainEvent]:
        events = []
        controller = self.controllers[ref]
        while True:
            options = self.available_actions(ref)
            ids = [o.id for o in options]
            point = DecisionPoint(kind="turn_action", actor=ref, options=ids)
            choice = controller.choose(options, point)
            if choice not in ids and choice != "hold":
                raise ValueError(f"{ref}: вариант {choice!r} недоступен")
            if choice == "end_turn":
                break
            if choice == "hold":
                # один шаг игрока: ход остаётся открытым, меню покажет, что осталось
                self.held = True
                break
            events += self.perform(ref, choice)
            if self.is_over or not self.is_capable(ref):
                break
        return events

    def next_turn(self) -> None:
        self.state.turn_index += 1
        if self.state.turn_index >= len(self.state.initiative_order):
            self.state.turn_index = 0
            self.tick_rounds()
            self.state.round += 1

    def step(self) -> list[DomainEvent]:
        if self.is_over:
            raise ValueError("бой окончен")
        ref = self.state.initiative_order[self.state.turn_index]
        if self.part(ref).status in ("dead", "fled", "surrendered"):
            self.next_turn()
            return []
        events = []
        if self.state.turn_started_for == ref:
            # ход уже начат (герой очнулся в фазе NPC): start_turn и заголовок не повторяем
            self.state.turn_started_for = None
        else:
            events = [DomainEvent(type="turn_started", data={"round": self.state.round, "id": ref})]
            self.log(f"--- раунд {self.state.round}, ход: {self.name(ref)} ---")
            events += self.start_turn(ref)
            events = self.finish(events)
            if self.is_over:
                return events
        # упавший герой, вставший от спасброска (натуральная 20), действует в этот же ход
        # колеблющийся теряет ход, но эффекты начала хода (горение и т.п.) уже сработали
        if self.is_capable(ref) and not parley.lose_turn(self, ref):
            events += self.run_controller(ref)
            if self.is_over:
                return events
            if self.held:
                self.held = False
                self.state.turn_started_for = ref
                return events
        self.expire("end_of_turn", ref)
        self.next_turn()
        return events

    def run_to_end(self, max_rounds=None) -> list[DomainEvent]:
        if max_rounds is None:
            max_rounds = self.cfg.combat.max_rounds
        events = []
        while not self.is_over:
            if self.state.round > max_rounds:
                raise CombatRoundLimit(f"бой не кончился за {max_rounds} раундов")
            events += self.step()
        return events

    def end_combat(self) -> list[DomainEvent]:
        if self.is_over:
            raise ValueError("бой уже окончен")
        self.state.outcome = "ended_by_master"
        return end.conclude(self)
