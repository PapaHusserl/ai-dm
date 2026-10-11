# Общие помощники тестов протокола мастера (этап 2, партия 2). Не фикстуры pytest, а обычные
# функции: тесты импортируют их напрямую (`from protocol_kit import ...`).
#
# КОНТРАКТ ПРОТОКОЛА (STAGE2-PLAN A0/A2, ТЗ 2.1/2.3), на него опираются тесты tests/unit/protocol.
# Где план не даёт точных имён, они выбраны здесь -- это ТРЕБОВАНИЕ к реализации.
#
#   ai_dm.protocol.requests  (Pydantic, extra="forbid", поле type: Literal["<имя>"] у каждой модели)
#     Обязательные поля -- без значения по умолчанию. Необязательные в схеме для модели --
#     обязательные
#     НЕ-nullable с нейтральным значением ("" / false / [] / 0 / "normal" / "none"; S1 ревью
#     партии 2, union в схеме нет нигде); Pydantic при разборе превращает нейтральное в None, так
#     что внутри протокола «нет» = None. Ниже типы необязательных полей записаны как `X | None`.
#     set_flag.value -- одна строка: "true"/"false" становятся bool, прочее остаётся текстом.
#     skill_check{skill: Skill, category: DcCategory, stakes: "critical"|None}
#     saving_throw{ability: Ability, category: DcCategory, stakes: "critical"|None}
#     start_combat{zones: [ZoneSpec], enemies: [EnemySpec], groups: [GroupSpec], hero_zone: str}
#       ZoneSpec{id, name, adjacent: [str]; exit: bool|None, features: [FeatureSpec]|None}
#       FeatureSpec{kind: str; damage, damage_type: str|None, save: Ability|None, dc: int|None}
#       EnemySpec{ref, monster_id, zone, group: str; name: str|None}
#         ref, найденный в world.npcs, -- именованный NPC мира (Participant.ref = id NPC, creature
#         None, controller "external" у ключевого NPC (npc.key), "engine" у обычного); иначе --
#         безымянный монстр (состояние в Participant.creature из registry, controller "engine")
#       GroupSpec{id, leader: str; intent: Intent; lair_location_id: str|None}
#     player_action{steps: [str]; improvise: ImproviseSpec|None, unsupported: str|None}
#       ImproviseSpec{skill, category, effect: str; target, zone: str|None}
#     npc_action{choice: str}
#     defeat_outcome{consequences: [capture|rob|left_to_die|scar|exhaustion|debt];
#                    lair_location_id, scar_ability, scar_skill, scar_text, debt_to, debt_text,
#                    rob_items -- все необязательные (поля combat.defeat.DefeatParams)}
#     end_combat{reason: str|None}
#     damage{severity: nuisance|dangerous|deadly, damage_type: str, failed_roll_ref: str|None}
#     give_item{item_id: str, qty: int}
#     take_item{item_id: str, qty: int, why: given|lost|stolen|spent}
#     gold{direction: gain|lose, kind: explicit|loot_individual; amount_cp: int|None, cr: str|None}
#       explicit -- amount_cp; loot_individual (только gain) -- cr побеждённого, сумма по таблице
#     award_xp{scale: minor|medium|major, reason: str}
#     advance_time{category: minute|hour|day|week|month|None, travel_to: str|None,
#                  pace: slow|normal|fast|None}   -- ровно одно из category / travel_to проверяет
#                  обработчик (Invalid("category_or_travel_to")), не модель
#     rest{kind: short|long, hit_dice: int|None}
#     set_flag{name: str, value: bool|int|str}
#     npc_create{id, name: str, means: [str]; named: bool|None, key: bool|None, motive: str|None,
#                location_id: str|None}   -- named=None -> False; origin созданного NPC = "ai"
#     location_create{id, name: str; parent_id: str|None, description: str|None,
#                     connections: [ConnectionSpec]|None}
#       ConnectionSpec{to: str, distance_m: int}; origin созданной локации = "ai"
#     npc_update{npc_id: str; attitude_delta: int|None, status: dead|gone|None,
#                cause: goal|hazard|chance|old_age|None, evidence_ref: str|None, by: str|None,
#                text: str|None}
#     warn_danger{location_id, text}  favor_change{npc_id, god_id: str, delta: int}
#     reveal_secret{npc_id, secret_id}  event_start{id, event_type: str; cause: str|None,
#       regions: [str]|None}  event_end{id}  afterlife_action{kind: short|long|epic}
#     offer_choices{choices: [str]}  end_scene{summary: str|None}  end_chapter{title: str|None}
#     unsupported_action{description: str}
#     REQUEST_MODELS: dict[str, type] -- имя -> модель, все 28 запросов ТЗ 2.1
#     ALL_TYPES, VISIBLE_TYPES, HIDDEN_TYPES, NPC_ONLY_TYPES: tuple[str, ...]
#       VISIBLE -- 22 (21 из плана A2 + reveal_secret с П3 этапа 3); HIDDEN -- warn_danger,
#       favor_change, event_start, event_end, afterlife_action; NPC_ONLY -- ("npc_action",);
#       вместе = ALL_TYPES (28)
#     MasterRequest -- Annotated-union по type (TypeAdapter(MasterRequest).validate_python);
#     parse_request(data: dict) -> MasterRequest -- то же (ValidationError при неизвестном type)
#
#   ai_dm.protocol.schema
#     tool_defs(exposed: Iterable[str]) -> list[dict]: инструменты для имён из exposed (порядок
#       входа не важен), отсортированы по name; неизвестное имя -> ValueError. Форма элемента:
#       {"name": str, "description": str (русский), "strict": True, "input_schema": {...}}
#       input_schema: type=object, properties включает "type" (enum из одного имени), всё в
#       required, additionalProperties false, без $ref/$defs (инлайн), без anyOf и type-списков;
#       tool_set(mode) -- определения набора режима (explore, combat_classify, combat_narrate,
#       npc_choice; редкие инструменты explore идут с strict False); у каждого свойства
#       верхнего уровня, кроме "type", непустое русское description.
#
#   ai_dm.protocol.decision
#     Decision(status: "accepted"|"clamped"|"rejected", reason: str = "",
#              signal_to_master: str | None = None, report_tag: str | None = None,
#              result: dict = {}, log: list[str] = [])    -- Pydantic, extra="forbid"
#       clamped/rejected всегда с непустым signal_to_master; accepted -- без сигнала
#     Invalid(code: str, message: str)  -- ошибка схемы/ссылок (бюджет «невалидный <= 2»)
#       коды: not_available_on_stage, not_available_in_mode, unknown_item, unknown_npc,
#       unknown_monster, unknown_cr, unknown_option, no_active_combat, combat_already_active,
#       no_defeat_pending, no_route,
#       category_or_travel_to, reserved_flag, choices_count, not_in_inventory, graph_disconnected
#       (и прочие коды combat.setup.validate_start -- берётся первый)
#
#   ai_dm.protocol.context
#     TurnContext(bundle, registry, cfg, rng=None, *, mode="explore", npc_options=None)
#       bundle -- РАБОЧАЯ копия (ход на model_copy(deep=True) делает вызывающий, контекст не
#       копирует: ctx.bundle is bundle); rng=None -> Rng.from_state(bundle.world.rng);
#       world.rng в бандле контекст НЕ синхронизирует (это commit игры).
#       mode: "explore" | "combat_classify" | "combat_narrate" | "npc_choice";
#       npc_options -- допустимые choice для npc_action в режиме npc_choice.
#       .hero -- герой с id == manifest.current_hero_id; .scene -- session.current_scene | None;
#       .rolls: dict[str, RollResult] -- журнал бросков хода ("r1", "r2", ... по порядку);
#       .add_roll(result: RollResult) -> str -- кладёт бросок, возвращает roll_ref;
#       .events: list[DomainEvent] -- доменные события хода по порядку;
#       .marks: list[str] -- метки авто-репортов ("limit-exceeded", "missing-mechanic",
#       "invalid-death") по порядку; .attitude_spent -- scene.attitude_spent (npc_id -> int,
#       сумма |delta| за сцену); .chapter_ended: bool (False -> True после end_chapter).
#
#   ai_dm.protocol.apply
#     apply(ctx, request) -> Decision | Invalid;  HANDLERS: dict[str, callable] по type видимых.
#     Invalid не меняет ни бандл, ни rng. Decision.report_tag: "limit-exceeded" (урезание),
#     "invalid-death", "missing-mechanic"; у остальных None. Урезание -- status "clamped".
#     Результаты (Decision.result): skill_check/saving_throw -> {"roll_ref", "outcome", "dc",
#     "total"}, строка броска (ТЗ 6) -- первая в Decision.log; start_combat -> {"combat_id"}.
#
#   ai_dm.protocol.render
#     render_tool_result(outcome: Decision | Invalid) -> dict {"content": str, "is_error": bool}
#       content -- JSON с sort_keys=True (на всех уровнях), ensure_ascii=False; Decision ->
#       is_error False, поля Decision целиком; Invalid -> is_error True, {"code", "message"}.
#
# Бросками управляет ScriptedRng: очереди граней по размеру кости; пустая очередь -> AssertionError.
import json

from ai_dm.core.rng import Rng
from ai_dm.protocol.context import TurnContext
from ai_dm.protocol.requests import parse_request
from ai_dm.rules.builder import CharacterChoices, build_character
from ai_dm.state.hero import HeroState  # noqa: F401  (для аннотаций в тестах)
from ai_dm.state.memory import Chronicle, Memory
from ai_dm.state.save import Manifest, SaveBundle
from ai_dm.state.scene import SceneState
from ai_dm.state.session import SessionState
from ai_dm.state.world import NPC, Connection, Location, WorldState


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


def fighter_choices(hero_id):
    return CharacterChoices(
        name="Арн",
        species_id="human",
        class_id="fighter",
        background="soldier",
        ability_method="standard_array",
        ability_scores={"str": 15, "dex": 13, "con": 14, "int": 8, "wis": 10, "cha": 12},
        background_bonus={"str": 2, "con": 1},
        class_skills=["perception", "survival"],
        weapon_masteries=["longsword", "greatsword", "shortsword"],
        fighting_style="defense",
        inventory=["chain_mail", "shield", "longsword"],
        equip=["chain_mail", "shield", "longsword"],
        species_choices={"skill": "stealth", "feat": "skilled"},
        feat_choices={"skilled": ["medicine", "religion", "nature"]},
        hero_id=hero_id,
    )


def make_hero(registry, hp=200):
    # человек-воин 1 ур.; запас HP, чтобы урон вне боя не убивал героя
    hero = build_character(fighter_choices("hero"), registry)
    hero.creature.hp_max = hp
    hero.creature.hp_current = hp
    hero.location_id = "vale"
    return hero


def make_world():
    # Вейл -> Лес (4800 м); Олдрик -- именованный NPC с attitude 0; Таверна в Вейле
    world = WorldState(world_id="w1", rng=Rng(7).state)
    world.locations["vale"] = Location(
        id="vale", name="Вейл", connections=[Connection(to="forest", distance_m=4800)]
    )
    world.locations["forest"] = Location(id="forest", name="Лес")
    world.locations["vale_tavern"] = Location(id="vale_tavern", name="Таверна", parent_id="vale")
    world.locations["goblin_den"] = Location(id="goblin_den", name="Логово")
    world.npcs["aldric"] = NPC(id="aldric", name="Олдрик", named=True, means=["связи"])
    world.npcs["grakh"] = NPC(
        id="grakh", name="Гракх", named=True, key=True, means=["клан"], location_id="vale"
    )
    return world


def make_bundle(registry, hp=200, with_scene=True):
    scene = None
    if with_scene:
        scene = SceneState(id="scene_1", started_at_s=0, location_id="vale")
    return SaveBundle(
        manifest=Manifest(
            schema_version=3, engine_version="0.1.0", world_id="w1", campaign_id=None,
            slot="auto", saved_at="2026-01-01T12:00:00Z", current_hero_id="hero",
            heroes=["hero"],
        ),
        world=make_world(),
        chronicle=Chronicle(),
        memory=Memory(),
        heroes=[make_hero(registry, hp)],
        session=SessionState(current_scene=scene),
    )


def make_ctx(registry, cfg, rng=None, bundle=None, **kwargs):
    if bundle is None:
        bundle = make_bundle(registry)
    return TurnContext(bundle, registry, cfg, rng, **kwargs)


def dump(ctx):
    # снимок бандла для сравнений «не изменилось» / «побайтно равно»
    return ctx.bundle.model_dump_json()


def req(type_name, **fields):
    # запрос мастера из полей: проходит ту же валидацию, что JSON от модели
    return parse_request({"type": type_name, **fields})


def zone(zone_id, adjacent, exit=False):
    return {"id": zone_id, "name": zone_id.capitalize(), "adjacent": adjacent, "exit": exit}


def goblin(ref, group="goblins", zone_id="hall"):
    return {"ref": ref, "monster_id": "goblin_warrior", "zone": zone_id, "group": group}


def combat_request(
    enemies=None, zones=None, groups=None, hero_zone="door", initiated_by="hero"
):
    # три зоны в линию: door - hall - balcony; группа goblins с лидером g1 и намерением kill
    if zones is None:
        zones = [
            zone("door", ["hall"]), zone("hall", ["door", "balcony"]), zone("balcony", ["hall"]),
        ]
    if enemies is None:
        enemies = [goblin("g1"), goblin("g2")]
    if groups is None:
        groups = [{"id": "goblins", "leader": "g1", "intent": "kill"}]
    # initiated_by="hero" по умолчанию: бой без урезания по бюджету (бюджет -- test_apply_budget.py)
    return req(
        "start_combat", zones=zones, enemies=enemies, groups=groups, hero_zone=hero_zone,
        initiated_by=initiated_by,
    )


def canonical(text):
    return json.dumps(json.loads(text), sort_keys=True, ensure_ascii=False)
