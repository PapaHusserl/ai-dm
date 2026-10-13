# Общие помощники тестов боя (партия 5). Не фикстуры pytest, а обычные функции: тесты импортируют
# их напрямую (`from combat_kit import ...`, каталог теста попадает в sys.path).
#
# КОНТРАКТ БОЯ (ARCHITECTURE A1/A2, шаги 15-21), на который опираются все тесты tests/unit/combat:
#
#   ai_dm.state.combat (только данные, extra="forbid")
#     ZoneFeature(kind: str, damage: str | None = None, damage_type: str = "fire",
#                 save: Ability | None = None, dc: int = 10)
#         kind: "cover_half" | "cover_three_quarters" | "difficult" | "hazard" -- механические;
#         любой другой kind ("high_ground", "chandelier") допустим, механики не имеет (топливо для
#         импровизации). hazard без damage или без save -> ValidationError.
#     Zone(id, name, features: list[ZoneFeature] = [], adjacent: list[str], exit: bool = False)
#     TurnState(action: bool = True, bonus: bool = True, reaction: bool = True, move: int = 1,
#               disengaged: bool = False)   -- True = ещё доступно; move = сколько зон осталось
#     Participant(ref, side: "heroes"|"enemies", group_id, zone_id: str | None = None,
#                 initiative: int | None = None, turn: TurnState = TurnState(),
#                 controller: "engine"|"auto_hero"|"external" = "engine",
#                 status: "active"|"down"|"dead"|"fled" = "active", monster_id: str | None = None,
#                 intent: Intent | None = None, surprised: bool = False,
#                 last_hit_by: str | None = None)
#         creature: CreatureState | None = None -- где живёт состояние (HP, состояния, эффекты):
#           * безымянный монстр (monster_id задан, записи в world.npcs НЕТ): в Participant.creature;
#             ref -- id участника внутри боя ("goblin_1"), имена могут совпадать, мир не трогается;
#           * именованный NPC из мира: ref = id в world.npcs, creature None, состояние у
#             NPC.creature (нет -- движок заводит его при start из monster_id);
#           * герой: ref = id героя, creature None, состояние в HeroState.creature.
#         name: str = "" -- отображаемое имя, может повторяться у безымянных (три «Воина-гоблина»);
#           в state.log участник выводится по name (не по ref), при одинаковых именах -- с номером
#           по порядку в participants ("Воин-гоблин 2"); см. test_log_names.py.
#         monster_id -- id монстра в реестре (статы: КД, атаки, черты); у героя None.
#         status: down = на 0 HP (герой умирает / выбит, монстр без сознания), dead = убит,
#         fled = ушёл через exit-зону. Боеспособный = status "active" и hp > 0.
#     Group(leader_id: str, intent: Intent | None = None, lair_location_id: str | None = None)
#     Intent = "kill" | "capture" | "rob" | "drive_off" | "spare"
#     Outcome = "victory" | "defeat_pending" | "hero_dying" | "hero_dead" | "fled" |
#               "ended_by_master"
#     CombatState(id: str, zones: list[Zone], participants: list[Participant],
#                 groups: dict[str, Group], round: int = 0, turn_index: int = 0,
#                 initiative_order: list[str] = [], budget_override_reason: str | None = None,
#                 outcome: Outcome | None = None, log: list[str] = [],
#                 defeat_group_id: str | None = None, savage_used: list[str] = [])
#         defeat_group_id -- группа, чьё намерение применено при падении героя (последний удар):
#           падение от опасности (без атакующего) -> None; удар по лежащему герою обновляет её.
#         savage_used -- герои, уже бросавшие кубики Savage Attacker в этом ходу (раз за любой ход);
#           сбрасывается в start_turn, переживает сейв (в движке счётчика нет).
#     DecisionPoint(kind: "turn_action"|"intent_reconsider", actor: str, options: list[str],
#                   subject: str | None = None, attacker: str | None = None)
#         actor -- кто решает; options -- id вариантов; subject / attacker -- упавший герой /
#         ударивший.
#
#   ai_dm.combat.engine
#     CombatEngine(state, world, heroes: dict[str, HeroState], registry, cfg, rng: Rng,
#                  controllers: dict[str, Controller] | None = None)
#         публичные атрибуты: state, world, heroes, registry, cfg, rng, controllers (по ref).
#         Конструктор валидирует старт (CombatSetupError) и НЕ меняет состояние.
#         Контроллер участника: из controllers[ref]; иначе по Participant.controller:
#         "engine" -> EngineTactics(engine), "auto_hero" -> AutoHeroController(engine).
#       start() -> list[DomainEvent]: инициатива, round = 1, turn_index = 0; повторно -> ValueError
#       start_turn(ref): начало хода (turn сброшен, savage_used = [], истечение start_of_turn,
#           вставание prone с source != "0_hp" -- перемещение хода = 0, hazard / спасбросок
#           от смерти;
#           nat 20 на спасброске -- герой в сознании и действует в этом же step())
#       available_actions(ref) -> list[ActionOption]
#       perform(ref, option_id) -> list[DomainEvent] | Rejected   (очередь хода не проверяет;
#           id вне available_actions -> Rejected(reason="not_available"))
#       improvise(ref, *, skill, category, effect, target=None, zone=None)
#           -> list[DomainEvent] | Rejected
#       step() -> list[DomainEvent]: ход одного участника (контроллер выбирает, пока не end_turn);
#           после конца боя -> ValueError
#       run_to_end(max_rounds=None) -> list[DomainEvent]; лимит (по умолчанию cfg.combat.max_rounds)
#           -> CombatRoundLimit (RuntimeError)
#       end_combat() -> list[DomainEvent]: outcome "ended_by_master"
#       is_over: bool -- outcome терминален (все, кроме None и "hero_dying")
#     Id вариантов действий (ActionOption(id, kind, label, params)); end_turn всегда последний:
#       multiattack                          у монстра с Monster.multiattack (goblin_boss): шаги
#                                            multiattack, цели по тактике, одно действие
#       attack:<оружие>:<цель>[:nonlethal]   оружие героя -- id оружия в main_hand; у монстра --
#                                            имя действия: нижний регистр, пробелы -> "_"
#                                            ("скимитар", "короткий_лук");
#                                            nonlethal -- только ближний бой
#       move:<зона>  dash  disengage  disengage_bonus (Nimble Escape)  dodge  help:<союзник>:<враг>
#       second_wind  use_item:<предмет>  stabilize:<цель>  flee (в exit-зоне)  end_turn
#       cast:<заклинание>:<круг>:<цель>      круг 0 у заговора; цель -- ref или id зоны (площадь);
#                                            у заклинания с targets > 1 (bless: 3) цели через
#                                            запятую: cast:bless:1:<t1>[,<t2>[,<t3>]], без повторов
#       (dodge: два эффекта "dodge" -- помеха атакующим и преимущество на спасброски ЛОВ)
#     События (DomainEvent.data -- только int | str | bool | None):
#       turn_started {round, id}; attack {attacker, target, weapon, mode: melee|ranged|spell,
#       outcome: hit|miss|crit|auto, damage: int}; npc_died / hero_died (rules.mortality_guard);
#       combat_ended {id}; location_visited {id}; item_gained {hero, item}.
#
#   ai_dm.combat.controllers:
#       Controller.choose(options: list[ActionOption], ctx: DecisionPoint) -> str
#       EngineTactics(engine), AutoHeroController(engine), ScriptedController(script: list[str])
#   ai_dm.combat.setup: validate_start(state) -> list[str] (коды), CombatSetupError(.codes)
#   ai_dm.combat.zones, area, downed, defeat, end -- см. шапки соответствующих тестов.
#
# Бросками управляет ScriptedRng: очереди граней по размеру кости, порядок между разными костями
# не важен (d20 / d8 / d6 ...); пустая очередь при броске -> AssertionError (лишний бросок).
import sys
from pathlib import Path

# fighter_choices живёт в kit-е протокола (общий, без дубля); каталог теста в sys.path один
PROTOCOL_DIR = Path(__file__).resolve().parents[1] / "protocol"
if str(PROTOCOL_DIR) not in sys.path:
    sys.path.insert(0, str(PROTOCOL_DIR))

from protocol_kit import fighter_choices  # noqa: E402, F401

from ai_dm.combat.engine import CombatEngine  # noqa: E402
from ai_dm.core.rng import Rng  # noqa: E402
from ai_dm.rules.builder import CharacterChoices, build_character  # noqa: E402
from ai_dm.rules.inventory import add_item, count_item, equip  # noqa: E402
from ai_dm.state.combat import CombatState, Group, Participant, Zone, ZoneFeature  # noqa: E402
from ai_dm.state.creature import AppliedCondition, CreatureState  # noqa: E402
from ai_dm.state.world import NPC, Location, WorldState  # noqa: E402


class ScriptedRng(Rng):
    def __init__(self, **queues):
        super().__init__(1)
        self.queues = {name: list(faces) for name, faces in queues.items()}
        self.calls = []

    def randbelow(self, n):
        name = f"d{n}"
        assert self.queues.get(name), f"неожиданный бросок {name}"
        self.calls.append(name)
        return self.queues[name].pop(0) - 1

    def left(self, name):
        return len(self.queues.get(name, []))


def feature(kind, **kwargs):
    return ZoneFeature(kind=kind, **kwargs)


def make_zones(door=(), hall=(), balcony=(), door_exit=False):
    # линейная карта из ARCHITECTURE: у двери -- центр зала -- балкон
    return [
        Zone(id="door", name="У двери", adjacent=["hall"], features=list(door), exit=door_exit),
        Zone(id="hall", name="Центр зала", adjacent=["door", "balcony"], features=list(hall)),
        Zone(id="balcony", name="Балкон", adjacent=["hall"], features=list(balcony)),
    ]


def make_line(count):
    # линейная карта из count зон z0 - z1 - ... (2..5): расстояние между зонами i и j = |i - j|
    ids = [f"z{i}" for i in range(count)]
    return [
        Zone(
            id=zid, name=f"Зона {i}",
            adjacent=[ids[j] for j in (i - 1, i + 1) if 0 <= j < count],
        )
        for i, zid in enumerate(ids)
    ]


def wizard_choices(hero_id):
    return CharacterChoices(
        name="Лиэль",
        species_id="elf",
        class_id="wizard",
        background="sage",
        ability_method="standard_array",
        ability_scores={"str": 8, "dex": 13, "con": 14, "int": 15, "wis": 12, "cha": 10},
        background_bonus={"int": 2, "con": 1},
        class_skills=["investigation", "medicine"],
        weapon_masteries=[],
        spells=["fire_bolt", "magic_missile", "burning_hands"],
        prepared=["magic_missile", "burning_hands"],
        hero_id=hero_id,
    )


def make_fighter(registry, hero_id="hero"):
    # человек-воин 1 ур., солдат: КД 19, HP 12, длинный меч +5 (1d8+3), мед. +2, Second Wind 2/2.
    # Savage Attacker (черта предыстории) снят: он бросает кубики урона дважды, а тесты
    # задают грани урона один раз.
    hero = build_character(fighter_choices(hero_id), registry)
    hero.sheet.feats = [f for f in hero.sheet.feats if f != "savage_attacker"]
    return hero


def make_wizard(registry, hero_id="wiz"):
    # эльф-волшебник 1 ур.: HP 8, КД 11, СЛ 13, атака заклинанием +5, ячейки spell_slot:1 2/2
    return build_character(wizard_choices(hero_id), registry)


def give_weapon(hero, registry, weapon_id):
    # кладёт оружие в main_hand (двуручное -- без щита)
    if count_item(hero, weapon_id) == 0:
        add_item(hero, weapon_id, cost_cp=0)
    if "two_handed" in registry.get("weapon", weapon_id).properties:
        hero.equipped.shield = None
    equip(hero, weapon_id, registry)


def make_npc(registry, ref, monster_id):
    # именованный NPC мира (уникальное имя), состояние -- в NPC.creature
    monster = registry.get("monster", monster_id)
    return NPC(
        id=ref, name=f"{monster.name} {ref}", means=["бой"],
        creature=CreatureState(hp_current=monster.hp, hp_max=monster.hp),
    )


def mon(ref, monster, zone, side="enemies", group="goblins", named=False):
    # named=False -- безымянный монстр (состояние в участнике); named=True -- NPC из world.npcs
    return {
        "ref": ref, "monster": monster, "zone": zone, "side": side, "group": group,
        "named": named,
    }


def make_engine(
    registry, cfg, *, heroes=(), monsters=(), zones=None, rng=None, controllers=None,
    intent="kill", started=True, groups=None, hero_zone="hall", hero_controller="auto_hero",
):
    # heroes: список HeroState или пар (HeroState, id зоны); monsters: список mon(...).
    # Порядок хода при started=True -- в порядке перечисления (героя первым, затем монстров).
    # Группы по умолчанию: "party" (лидер -- первый герой, намерения нет) и по группе на каждый
    # group_id монстров (лидер -- первый в группе, intent = intent у врагов, None у союзников).
    if zones is None:
        zones = make_zones()
    world = WorldState(world_id="w1", rng=Rng(1).state)
    world.locations["goblin_den"] = Location(id="goblin_den", name="Логово")
    hero_map = {}
    participants = []
    for item in heroes:
        hero, zone_id = item if isinstance(item, tuple) else (item, hero_zone)
        hero_map[hero.id] = hero
        participants.append(
            Participant(
                ref=hero.id, side="heroes", group_id="party", zone_id=zone_id,
                controller=hero_controller,
            )
        )
    for spec in monsters:
        own = None
        if spec["named"]:
            world.npcs[spec["ref"]] = make_npc(registry, spec["ref"], spec["monster"])
        else:
            hit_points = registry.get("monster", spec["monster"]).hp
            own = CreatureState(hp_current=hit_points, hp_max=hit_points)
        participants.append(
            Participant(
                ref=spec["ref"], side=spec["side"], group_id=spec["group"], zone_id=spec["zone"],
                monster_id=spec["monster"], creature=own,
                name="" if spec["named"] else "Воин-гоблин",
            )
        )
    built = {}
    for p in participants:
        if p.group_id not in built:
            intent_value = intent if p.side == "enemies" else None
            built[p.group_id] = Group(leader_id=p.ref, intent=intent_value)
    built.update(groups or {})
    state = CombatState(id="fight_1", zones=zones, participants=participants, groups=built)
    if started:
        state.round = 1
        state.initiative_order = [p.ref for p in participants]
        for i, p in enumerate(participants):
            p.initiative = 100 - i
    if rng is None:
        rng = ScriptedRng()
    return CombatEngine(state, world, hero_map, registry, cfg, rng, controllers)


def part(engine, ref):
    for p in engine.state.participants:
        if p.ref == ref:
            return p
    raise KeyError(ref)


def creature(engine, ref):
    if ref in engine.heroes:
        return engine.heroes[ref].creature
    own = part(engine, ref).creature
    if own is not None:
        return own
    return engine.world.npcs[ref].creature


def hp(engine, ref):
    return creature(engine, ref).hp_current


def set_hp(engine, ref, value):
    creature(engine, ref).hp_current = value


def move_to(engine, ref, zone_id):
    part(engine, ref).zone_id = zone_id


def down_hero(engine, ref, by=None):
    # герой уже лежит на 0 HP: без сознания, участник status="down"
    c = engine.heroes[ref].creature
    c.hp_current = 0
    c.conditions.append(AppliedCondition(id="unconscious", source="0_hp"))
    p = part(engine, ref)
    p.status = "down"
    p.last_hit_by = by


def option_ids(engine, ref):
    return [o.id for o in engine.available_actions(ref)]


def turn(engine, ref):
    return part(engine, ref).turn
