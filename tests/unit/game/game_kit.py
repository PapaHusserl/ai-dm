# Общие помощники тестов слоя game (этап 2, партия 5). Не фикстуры pytest, а обычные функции:
# тесты импортируют их напрямую (`from game_kit import ...`). Живых вызовов и сети нет: только
# ScriptedAdapter / YAML-сценарии / ReactiveAdapter (ниже) / ReplayAdapter.
# Импорты ai_dm.game.* -- ВНУТРИ функций: пока слоя нет, тесты падают по одному (red), а не весь
# сбор.
#
# КОНТРАКТ СЛОЯ game (STAGE2-PLAN A5, A4 «контракт для партии 5», ТЗ 2.2, 4.0, 5.1, 7, 10, 11).
# Где план не даёт точных имён, они выбраны здесь -- это ТРЕБОВАНИЕ к реализации. game
# склеивает master/protocol/persistence/combat/rules/llm; game НЕ импортирует ui (сторож в
# test_architecture.py). game синхронный, без ввода-вывода: UI (партия 6) вызывает GameApp.
#
#   ai_dm.game.starter
#     fighter_choices(hero_id="hero") -> CharacterChoices   Арн: человек-воин, солдат (те же
#       выборы, что в devtools/sim_combat до переезда); wizard_choices(hero_id="hero") -- Лиэль,
#       эльф-волшебница. devtools.sim_combat импортирует их отсюда (is-тождество объектов).
#     HEROES = ("arn", "liel")
#     WORLD_TEXT: str -- абзац мира для PromptBuilder (world_text), непустой, упоминает «Вейл».
#     new_world(registry, cfg, *, hero, seed, world_id=None, saved_at) -> SaveBundle
#       hero in HEROES, иначе ValueError; cfg -- RulesConfig; world_id=None -> уникальный
#       (разные вызовы -- разные id, подходит под persistence.layout.check_world_id); saved_at --
#       строка в manifest (время внутри не берётся: одинаковые аргументы -- равные бандлы).
#       Бандл: manifest.world_id == world.world_id, current_hero_id "hero", heroes ["hero"],
#       schema_version == CURRENT_SCHEMA_VERSION; world.rng == Rng(seed).state; один герой "hero"
#       (из choices, xp 0, location_id "lame_goose"); часы world.clock.now_s == 0.
#       Локации: "vale" (Вейл), "lame_goose" (название содержит «Хромой гусь», parent_id "vale"),
#       "cellar" (подвал; description содержит «гоблин» -- гоблины живут там; parent_id
#       "lame_goose"); связи: vale <-> lame_goose и lame_goose <-> cellar (в любом из двух
#       направлений есть Connection с distance_m > 0), чтобы advance_time(travel_to) работал по
#       цепочке. NPC: "innkeeper" -- трактирщик (named True, key False, location_id
#       "lame_goose"); "grakh" -- Гракх (named True, key True, location_id "cellar",
#       combat == {"monster_id": "goblin_boss", "intent": "capture"} -- намерение оформлено
#       данными). Стартовая сцена: session.current_scene == SceneState(id "scene_1",
#       started_at_s 0, location_id "lame_goose"); active_combat None; turn_seq 0.
#
#   ai_dm.game.turn
#     TurnRunner(bundle, registry, cfg, app_cfg, adapter, *, saves_root, journal=None,
#                ledger=None, world_text="", sleeper=time.sleep, now=None, model=None,
#                run_tag=None)
#       cfg -- RulesConfig, app_cfg -- AppConfig; now -- callable() -> datetime (метки журнала,
#       saved_at автосейвов); model -- id модели для PromptBuilder и бюджета (по умолчанию
#       adapter.info().model; для ReplayAdapter, у которого model == "replay", нужен id
#       записанной модели). PromptBuilder(app_cfg, model=<модель>) создаёт runner
#       и передаёт в MasterSession(builder=...).
#       .bundle -- последний ЗАВЕРШЁННЫЙ (committed) бандл; abort его не трогает.
#       .adapter; .set_adapter(adapter, model=None) -- заменяет адаптер и пересоздаёт builder
#       (/model, «сменить модель»).
#       .play(player_input: str) -> TurnResult -- один ход игрока: вне боя (active_combat None)
#         MasterSession(explore); в бою -- ход героя (см. combat_flow). Работает на
#         bundle.model_copy(deep=True) и Rng.from_state(world.rng). Один новый run_id на ход
#         (непустая строка, разный у разных ходов и у повтора): все вызовы мастера хода
#         (classify / npc_choice / narrate / explore) идут с ним. run_id уникален и между
#         перезапусками: метка = f"{now:%Y%m%dT%H%M%S}-{tag}", tag = run_tag or uuid4().hex[:6]
#         (два раннера с одним `now` на одном журнале -- разные run_id); тесты (make_rig /
#         make_app) передают фиксированный run_tag="t" -- run_id детерминирован.
#         Успех (commit): world.rng = rng.state; session.turn_seq += 1; в memory.recent_turns
#         TurnRecord(turn_seq=<новое значение>, at_s, player_input, narration,
#         requests=[type принятых запросов по порядку], rolls=[строки бросков хода]); в
#         memory.recent_turns остаются последние app_cfg.master.recent_turns_keep (50) записей
#         (окно промпта -- recent_turns, 4, отдельно);
#         scene.player_turns += 1; journal.mark_turn(run_id, "committed"); затем закрытие
#         сцены (game.scene) и автосейв.
#         TurnFailed -> abort: бандл и RNG прежние, journal.mark_turn(run_id, "aborted"),
#         результат с committed=False. ЛЮБОЕ другое исключение (ScriptExhausted,
#         ReplayDivergence, ...) -- тоже abort (бандл прежний) и повторный raise.
#       .retry() -> TurnResult -- повтор последнего упавшего ввода с НОВЫМ run_id.
#       .preview_turn() -> list[ActionOption] -- только в бою, когда ход героя ждёт решения:
#         действия героя на одноразовой копии (start_turn героя + available_actions);
#         бандл и RNG не меняются; список совпадает с тем, что PlayerController увидит в
#         настоящем ходе; end_turn -- последний.
#     TurnResult: .committed: bool; .run_id: str; .narration: str ("" при abort);
#       .lines: list[str] -- log принятых Decision хода по порядку (строки бросков ТЗ 6);
#       .log: list[str] -- строки лога боя, появившиеся за ход (ход героя + ходы NPC до его
#       следующего решения; в ходе со start_combat -- от «Бой начался» до решения героя), вне
#       боя []; .requests: list[str] (type принятых запросов); .report_tags: list[str] (метки
#       решений; при refusal ["refusal"]); .failure: TurnFailed | None; .menu: list[str] | None
#       -- при abort ровно ["retry", "switch_model", "save_and_quit"] (при любой причине, в т.ч.
#       fatal); .hint: str | None -- при refusal текст со словами «tone» и «модел»; при прочих
#       причинах без «tone»; .combat_outcome: str | None -- итог боя, закончившегося в этом ходу;
#       .hero_dead:
#       bool -- герой в committed-бандле status == "dead"; .scene_summary / .chapter_title --
#       из TurnContext хода (end_scene.summary / end_chapter.title), иначе None. CombatRoundLimit
#       в ходе боя -- TurnFailed("round_limit") -> обычное меню ошибки.
#
#   ai_dm.game.scene
#     start_scene(bundle) -> SceneState -- кладёт в bundle.session.current_scene новую сцену:
#       id "scene_<n+1>" (n из id прежней "scene_<n>"; сцены нет -> "scene_1"), started_at_s =
#       world.clock.now_s, player_turns 0, location_id = локация героя, closed_reason None.
#     check_close(bundle, cfg, *, time_before_s, combat_ended=False) -> str | None -- причина
#       закрытия по приоритету: уже выставленный scene.closed_reason (end_scene) >
#       "location_changed" (hero.location_id != scene.location_id) > "time_jump" (clock.now_s -
#       time_before_s > cfg.scene.max_time_jump_s, строго больше) > "combat_ended" (флаг) >
#       "turn_limit" (scene.player_turns > cfg.scene.max_player_turns); иначе None. Бандл не
#       меняется.
#     close_scene(bundle, reason, cfg) -- scene.closed_reason = reason; rules.time_ops.
#       ensure_min_advance(clock, scene.started_at_s, cfg) (+min_advance_s, если время не
#       сдвигалось с начала сцены).
#     ensure_chapter(bundle) -> ChapterState -- глава 1 для сейва без главы.
#     В ходе (TurnRunner): после commit -> check_close -> close_scene -> автосейв
#       persistence.store.save_auto(saves_root, bundle, saved_at=..., cfg=cfg) (в сейв попадает
#       ЗАКРЫТАЯ сцена) -> boundary.run -> start_scene (runner.bundle получает новую).
#
#   ai_dm.game.combat_flow
#     advance_until_player(engine, hero_id) -> list[str] -- ходы остальных (engine.step()) до
#       тех пор, пока очередь не дойдёт до боеспособного героя или бой не окончится (герой,
#       пришедший в сознание нат-20 в своём шаге спасброска, -- тоже остановка: ход у игрока);
#       возвращает
#       строки engine.state.log, добавленные за вызов (по порядку). Героя не трогает.
#     Остальное -- поведение TurnRunner: start_combat (после apply: engine.start() +
#     advance_until_player; строки -> Decision.log -> tool_result); ход героя: номер (1-based
#     в preview_turn, ввод «3» -- без вызова модели, ровно один вариант) или текст
#     (MasterSession combat_classify -> PlayerAction: steps / improvise); TurnContext получает
#     combat_options=[{id, label}] из preview_options: в state-JSON запроса combat_classify
#     лежит combat.options (варианты на границе хода), в combat_narrate -- варианты СЛЕДУЮЩЕГО
#     хода героя (бой кончился -- []); в system вариантов нет (префикс стабилен); первый шаг
#     player_action обязан быть из них, иначе Invalid unknown_step; после хода героя --
#     ходы остальных до его следующего решения; затем ВСЕГДА MasterSession(combat_narrate)
#     (player_input = текст игрока (если был) + строки лога боя за ход); конец боя: опыт за
#     победу или ended_by_master при живом герое (rules.xp.combat_xp по врагам status
#     dead/down; fled и оставшиеся на ногах при ended_by_master -- без опыта), флаг
#     combat_ended:<id>
#     (ставит движок), session.active_combat = None, сцена закрывается "combat_ended";
#     defeat_pending -> в narrate обязателен defeat_outcome (иначе невалидный ответ, бюджет).
#     Номер вне 1..len(preview) -- не определён (не тестируется).
#
#   ai_dm.game.controllers
#     PlayerController(steps=None, improvise=None)   steps: list[str] id вариантов;
#       improvise: protocol.requests.ImproviseSpec | None (skill, category, effect, target, zone)
#       .attach(engine); .choose(options, point) -> str: если есть improvise и он ещё не
#       выполнен -- engine.improvise(point.actor, skill=, category=, effect=, target=, zone=)
#       (бросок, действие потрачено) и дальше шаги; затем steps по очереди; кончились -- "end_turn".
#     MasterChoiceController(ctx, session, *, run_id, world_text="")  ключевой NPC
#       .attach(engine); .choose(options, point) -> str.
#       intent_reconsider: MasterSession.run(npc_ctx, text, protocol.apply, "npc_choice", run_id=,
#       world_text=) с npc_ctx = TurnContext(ctx.bundle, ctx.registry, ctx.cfg, ctx.rng,
#       mode="npc_choice", npc_options=point.options); выбор -- request npc_action.choice.
#       turn_action: если hp актёра <= app_cfg.master.key_npc_consult_hp_percent % от hp_max и
#       модель этим контроллером ещё не спрашивали про ход -- тот же вызов (npc_options =
#       [o.id for o in options]); во ВСЕХ остальных решениях хода -- EngineTactics(engine).
#       Текст запроса к модели (player_input npc_choice-запроса) содержит каждый id варианта в
#       отдельной строке вида «- <id>». Невалидные ответы (>2) -> TurnFailed("invalid") наружу.
#
#   ai_dm.game.commands
#     COMMANDS: dict[str, callable] -- имена без «/»: help save load model cost sheet inv quit
#       report tone retire. Команды исполняются через GameApp.handle("/...").
#
#   ai_dm.game.app
#     GameApp(settings, registry, bundle, adapter, *, saves_root, adapter_factory=None,
#             world_text="", sleeper=time.sleep, now=None, model=None, run_tag=None,
#             use_stored_model=True)
#       settings -- config.app.Settings (rules + app); adapter_factory(provider, model) ->
#       адаптер (llm.factory.make_adapter-совместимая; MissingKey/ValueError -- ошибка выбора);
#       .runner (TurnRunner), .bundle (= runner.bundle), .adapter, .journal (Journal(saves_root,
#       world_id, app.journal)), .ledger (CostLedger(saves_root, world_id)) -- создаются в app.
#       Если saves_root/<world_id>/meta/models.json есть -- при создании применяется (вызов
#       adapter_factory для narrator). Формат файла: {"narrator": {"provider": ..., "model": ...}}.
#       use_stored_model=False -- файл игнорируется (CLI для --mock/--replay). Битый файл / нет
#       ключей / модель без цены или окна -- старт с переданным адаптером и строка
#       startup_lines «Сохранённая модель не подключена: ...» (одна проверка check_model для
#       старта и /model); запись models.json атомарна (tmp + os.replace).
#       .pending: None | "level_up" | "error_menu" | "model_choice" | "hero_dead"
#       .handle(line: str) -> Reply -- «/...» -- команда; иначе ход (TurnRunner.play), пока
#         pending не None -- ход НЕ запускается (команды можно), Reply повторяет меню.
#       .choose(key: str) -> Reply -- ответ на меню pending.
#     Reply: .lines: list[str] (вывод команд и сообщения), .narration: str (повествование
#       хода, иначе ""), .turn: TurnResult | None, .pending: str | None, .menu: list[str] |
#       None, .hint: str | None, .quit: bool.
#     Меню: error_menu -> ["retry", "switch_model", "save_and_quit"]: retry = runner.retry();
#       switch_model -> pending "model_choice", menu = id вариантов вида «provider:model»
#       (narrator, alternatives.narrator, профили), выбор -> adapter_factory(provider, model),
#       возврат в error_menu; save_and_quit -> save_auto committed-состояния, quit True.
#       level_up -> ["average", "roll"]: после committed-хода, если rules.progression.
#       can_level_up(hero): choose("average"|"roll") -> level_up(hero, registry, hp_method=,
#       rng=Rng.from_state(world.rng) -> world.rng синхронизируется); снова pending, если опыта
#       хватает на следующий. hero_dead -> ["load_last_save", "quit"] (временное правило 5.1:
#       смерть героя -> загрузка последнего сейва): load_last_save = загрузка слота "auto"
#       (нет сейва -- сообщение «нет сохранений», pending остаётся), quit -> quit True.
#       Загрузка слота с героем status == "dead" (load / load_last_save) -- pending "hero_dead".
#     Команды: /help -- все 11 команд со «/»; /save [имя] -> слот
#       "manual-<имя>" (при pending "hero_dead" -- запрещён, сообщение, слот не
#       пишется; без имени -- "manual-quick"; плохое имя -- сообщение, без
#       исключения); /load [имя] -> слот
#       "manual-<имя>" (без имени -- "auto"); нет слота -- сообщение, состояние прежнее;
#       загруженная закрытая сцена (closed_reason не None) заменяется новой (start_scene);
#       успешная загрузка сбрасывает pending (меню ошибки / смерти / уровня);
#       /model -- без аргументов список ролей и моделей; /model <роль> <провайдер:модель> --
#       narrator: adapter_factory -> новый адаптер (запросы идут с новой моделью и бюджетом),
#       выбор пишется в saves/<world>/meta/models.json; неизвестная роль / модель без цены в
#       конфиге / ошибка фабрики -- сообщение, ничего не меняется; /cost -- отчёт ledger с
#       блоками «сессия», «день», «мир» и именами ролей/моделей; /sheet -- имя героя и HP;
#       /inv -- предметы героя; /quit -- quit True (без сохранения); /report -- «появится на
#       этапе 6», /tone -- «появится на этапе 3», /retire -- «появится на этапе 9»;
#       неизвестная команда -- сообщение со словом «/help». Команды не зовут модель и не
#       меняют бандл (кроме /load) и RNG.
import json
import sys
from dataclasses import dataclass
from pathlib import Path

# рядом лежат kit-ы соседних слоёв: каталог теста в sys.path один, добавляем нужные явно
TESTS_UNIT = Path(__file__).resolve().parents[1]
for sub in ("master", "protocol", "llm", "combat"):
    if str(TESTS_UNIT / sub) not in sys.path:
        sys.path.insert(0, str(TESTS_UNIT / sub))

from master_kit import (  # noqa: E402, F401
    NOW,
    Recorder,
    flag_call,
    scripted,
    text_step,
    tools_step,
)
from protocol_kit import make_bundle  # noqa: E402, F401

from ai_dm.config.app import load_settings  # noqa: E402
from ai_dm.llm.cost import CostLedger  # noqa: E402
from ai_dm.llm.journal import Journal  # noqa: E402
from ai_dm.llm.mock import ScriptedAdapter, load_script  # noqa: E402
from ai_dm.llm.types import ChatResponse, Text, ToolCall, Usage  # noqa: E402

OPUS = "claude-opus-5-5"
SONNET = "claude-sonnet-5-5"
SCRIPTS = Path(__file__).resolve().parents[2] / "fixtures" / "scripts"
SAVED_AT = "2026-10-03T12:00:00Z"

BAD_CHECK = {
    "id": "bad", "name": "skill_check",
    "input": {"type": "skill_check", "skill": "nope", "category": "medium", "stakes": "normal"},
}


def settings():
    return load_settings()


def skill_check_call(call_id="sc-1", skill="persuasion", category="medium"):
    return {
        "id": call_id, "name": "skill_check",
        "input": {"type": "skill_check", "skill": skill, "category": category, "stakes": "normal"},
    }


def advance_call(call_id="adv-1", **fields):
    # advance_time: category или travel_to
    data = {"type": "advance_time", "category": "none", "travel_to": "", "pace": "normal"}
    data.update(fields)
    return {"id": call_id, "name": "advance_time", "input": data}


def end_scene_call(call_id="es-1", summary=""):
    return {
        "id": call_id, "name": "end_scene", "input": {"type": "end_scene", "summary": summary},
    }


def damage_call(call_id="dm-1", severity="dangerous"):
    return {
        "id": call_id, "name": "damage",
        "input": {
            "type": "damage", "severity": severity, "damage_type": "fire", "failed_roll_ref": "",
        },
    }


def start_combat_input(grakh=False, intent="kill", hazard=False):
    # три зоны в линию door - hall - balcony; два гоблина в hall (+ Гракх -- ключевой NPC мира
    # make_bundle -- в hall); герой в door
    enemies = [
        {"ref": "g1", "monster_id": "goblin_warrior", "zone": "hall", "group": "goblins"},
        {"ref": "g2", "monster_id": "goblin_warrior", "zone": "hall", "group": "goblins"},
    ]
    leader = "g1"
    if grakh:
        enemies.append(
            {"ref": "grakh", "monster_id": "goblin_boss", "zone": "hall", "group": "goblins"}
        )
        leader = "grakh"
    door = {"id": "door", "name": "У двери", "adjacent": ["hall"]}
    if hazard:
        # огонь у двери: в начале хода героя спасбросок и кубики -- проверка «preview ничего не
        # меняет»
        door["features"] = [
            {"kind": "hazard", "damage": "1d4", "damage_type": "fire", "save": "dex", "dc": 10}
        ]
    return {
        "type": "start_combat",
        "zones": [
            door,
            {"id": "hall", "name": "Центр зала", "adjacent": ["door", "balcony"]},
            {"id": "balcony", "name": "Балкон", "adjacent": ["hall"]},
        ],
        "enemies": enemies,
        "groups": [{"id": "goblins", "leader": leader, "intent": intent}],
        "hero_zone": "door",
        # бюджет боя (П6б) проверяет test_apply_budget.py; здесь бой без урезания
        "initiated_by": "hero",
    }


def start_combat_call(call_id="sc-1", **kw):
    return {"id": call_id, "name": "start_combat", "input": start_combat_input(**kw)}


def player_action_input(steps, improvise=None):
    data = {"type": "player_action", "steps": list(steps), "unsupported": ""}
    if improvise is not None:
        data["improvise"] = improvise
    return data


# адаптеры

class CountingAdapter(Recorder):
    # Recorder, который считает вызовы count_tokens
    def __init__(self, inner):
        super().__init__(inner)
        self.count_calls = 0

    def count_tokens(self, request):
        self.count_calls += 1
        return self.inner.count_tokens(request)


class ReactiveAdapter:
    # Детерминированный мок «по режимам»: смотрит на набор инструментов запроса.
    #   combat_classify {player_action, unsupported_action}: первый ответ -- вызов player_action с
    #     очередным словарём из classify (очередь); после результата -- текст «Принято.»
    #   npc_choice {npc_action}: первый ответ -- npc_action с choice = npc_pick(options), где
    #     options -- id из строк «- <id>» в player_input; после результата -- текст
    #   combat_narrate: при outcome defeat_pending: defeat="call" -- вызов defeat_outcome
    #     (шрам в силу), "text_first" -- один ответ текстом, потом вызов, "never" -- только текст;
    #     end_combat=True -- вызов end_combat; иначе текст «Бой идёт.»
    #   explore и прочее: текст «Рассказ.»
    def __init__(
        self, *, classify=None, npc_pick=None, defeat="call", end_combat=False,
        provider="anthropic", model=OPUS,
    ):
        self.classify = list(classify or [])
        self.npc_pick = npc_pick or pick_end_turn_or_first
        self.defeat = defeat
        self.end_combat = end_combat
        self.provider = provider
        self.model = model
        self.requests = []

    def info(self):
        from ai_dm.llm.adapter import AdapterInfo

        return AdapterInfo(provider=self.provider, model=self.model)

    def complete(self, request):
        self.requests.append(request.model_copy(deep=True))
        number = len(self.requests)
        names = {t.name for t in request.tools}
        called = {
            b.name for m in request.messages for b in m.content if isinstance(b, ToolCall)
        }
        data = json.loads(request.messages[0].content[0].text)
        content, text = [], "Рассказ."
        if names == {"player_action", "unsupported_action"}:
            text = "Принято."
            if "player_action" not in called:
                content = [self.call(number, "player_action", self.classify.pop(0))]
        elif names == {"npc_action"}:
            text = "Решено."
            if "npc_action" not in called:
                options = [
                    line[2:] for line in data["player_input"].splitlines()
                    if line.startswith("- ")
                ]
                choice = self.npc_pick(options)
                data_in = {"type": "npc_action", "choice": choice}
                content = [self.call(number, "npc_action", data_in)]
        elif "defeat_outcome" in names:
            text = "Бой идёт."
            pending = (data["combat"] or {}).get("outcome") == "defeat_pending"
            first_round = len(request.messages) == 1
            if pending and "defeat_outcome" not in called:
                if self.defeat == "call" or (self.defeat == "text_first" and not first_round):
                    content = [self.call(number, "defeat_outcome", defeat_input())]
            elif self.end_combat and "end_combat" not in called:
                content = [self.call(
                    number, "end_combat", {"type": "end_combat", "reason": "гоблины сдались"}
                )]
        blocks = [Text(text=text)] if not content else []
        blocks += content
        stop = "tool_use" if content else "end_turn"
        return ChatResponse(
            content=blocks, stop_reason=stop, usage=Usage(input=100, output=20),
            request_id=f"react-{number}", model=request.model,
        )

    def call(self, number, name, data):
        return ToolCall(id=f"react-{number}-{name}", name=name, input=data)


def defeat_input():
    return {
        "type": "defeat_outcome", "consequences": ["scar"], "scar_ability": "str",
        "scar_text": "Шрам на плече",
    }


def pick_end_turn_or_first(options):
    if "end_turn" in options:
        return "end_turn"
    return "keep" if "keep" in options else options[0]


def pick_keep(options):
    return "keep"


def pick_bogus(options):
    return "bogus"


class ScriptThenReactive:
    # сначала шаги сценария (YAML), когда они кончились -- ReactiveAdapter; общий список запросов
    def __init__(self, scripted_adapter, reactive):
        self.first = scripted_adapter
        self.then = reactive
        self.requests = []

    def info(self):
        return self.first.info()

    def complete(self, request):
        self.requests.append(request.model_copy(deep=True))
        if self.first.steps:
            return self.first.complete(request)
        return self.then.complete(request)


def script_then_react(steps, **reactive_kw):
    # шаги сценария для первых ходов (explore), дальше -- ReactiveAdapter
    first = ScriptedAdapter(steps, provider="anthropic", model=OPUS)
    return ScriptThenReactive(first, ReactiveAdapter(**reactive_kw))


def scripted_from_yaml(name):
    return ScriptedAdapter(load_script(SCRIPTS / name), provider="anthropic", model=OPUS)


# сборка

@dataclass
class Rig:
    runner: object
    adapter: object
    journal: object
    ledger: object
    sleeps: list
    root: Path
    app_cfg: object


def make_rig(
    registry, cfg, tmp_path, adapter, *, bundle=None, world_text="", model=None, run_tag="t",
):
    from ai_dm.game.turn import TurnRunner

    app = settings().app
    if bundle is None:
        bundle = make_bundle(registry)
    world_id = bundle.world.world_id
    journal = Journal(tmp_path, world_id, app.journal)
    ledger = CostLedger(tmp_path, world_id)
    sleeps = []
    extra = {}
    if model is not None:
        extra["model"] = model
    runner = TurnRunner(
        bundle, registry, cfg, app, adapter, saves_root=tmp_path, journal=journal,
        ledger=ledger, world_text=world_text, sleeper=sleeps.append, now=lambda: NOW,
        run_tag=run_tag, **extra,
    )
    # по умолчанию summarizer -- запасная выжимка без вызова модели (этап 4, P1)
    runner.new_summarizer_session = lambda: None
    return Rig(runner, adapter, journal, ledger, sleeps, tmp_path, app)


def make_app(
    registry, tmp_path, adapter, *, bundle=None, adapter_factory=None, model=None, world_text="",
    run_tag="t", use_stored_model=None, auto_reports=None,
):
    from ai_dm.game.app import GameApp

    if bundle is None:
        bundle = make_bundle(registry)
    extra = {}
    if model is not None:
        extra["model"] = model
    if use_stored_model is not None:
        extra["use_stored_model"] = use_stored_model
    if auto_reports is not None:
        extra["auto_reports"] = auto_reports
    sleeps = []
    app = GameApp(
        settings(), registry, bundle, adapter, saves_root=tmp_path,
        adapter_factory=adapter_factory, world_text=world_text, sleeper=sleeps.append,
        now=lambda: NOW, run_tag=run_tag, **extra,
    )
    app.runner.new_summarizer_session = lambda: None
    return app


class FactorySpy:
    # adapter_factory для /model: запоминает вызовы, отдаёт ReactiveAdapter с нужной моделью
    def __init__(self, error=None):
        self.calls = []
        self.error = error
        self.made = []

    def __call__(self, provider, model):
        self.calls.append((provider, model))
        if self.error is not None:
            raise self.error
        adapter = ReactiveAdapter(provider=provider, model=model)
        self.made.append(adapter)
        return adapter


# проверки и разбор

def state_of(request):
    # JSON состояния в первом user-сообщении запроса (master_kit: json.dumps(data))
    return json.loads(request.messages[0].content[0].text)


def tool_names(request):
    return {t.name for t in request.tools}


def requests_with_tools(adapter, names):
    return [r for r in adapter.requests if tool_names(r) == set(names)]


def core_dump(bundle):
    # всё, кроме manifest (slot / saved_at различаются у загруженного и «живого» бандла)
    return json.dumps(
        {
            "world": json.loads(bundle.world.model_dump_json()),
            "session": json.loads(bundle.session.model_dump_json()),
            "heroes": [json.loads(h.model_dump_json()) for h in bundle.heroes],
            "memory": json.loads(bundle.memory.model_dump_json()),
            "chronicle": json.loads(bundle.chronicle.model_dump_json()),
        },
        sort_keys=True, ensure_ascii=False,
    )


def run_records(journal, run_id):
    return [r for r in journal.read_records() if r["run_id"] == run_id]


def combat_of(runner):
    return runner.bundle.session.active_combat


# ходы боя по номерам

def option_ids(runner):
    return [o.id for o in runner.preview_turn()]


def number_of(runner, option_id):
    return option_ids(runner).index(option_id) + 1


def attack_or_move_number(runner):
    # жадная тактика героя: атака в своей зоне, иначе шаг в зону с боеспособным врагом
    ids = option_ids(runner)
    state = combat_of(runner)
    for i, option_id in enumerate(ids):
        if option_id.startswith("attack:longsword:") and not option_id.endswith(":nonlethal"):
            return i + 1
    enemy_zones = {
        p.zone_id for p in state.participants
        if p.side == "enemies" and p.status == "active"
    }
    for i, option_id in enumerate(ids):
        if option_id.startswith("move:") and option_id[len("move:"):] in enemy_zones:
            return i + 1
    return len(ids)


def end_turn_number(runner):
    return len(option_ids(runner))


def drive(runner_like, pick, limit=60):
    # ходы героя по номерам, пока бой идёт; возвращает результаты ходов; останавливается на
    # откате хода. runner_like -- TurnRunner (preview_turn / play)
    results = []
    for _ in range(limit):
        if runner_like.bundle.session.active_combat is None:
            break
        result = runner_like.play(str(pick(runner_like)))
        results.append(result)
        if not result.committed:
            break
    return results
