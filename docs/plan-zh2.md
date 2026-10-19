# Ж2: мстители и должники

## Суть

ROADMAP «Ж2» (BACKLOG 9, 10, 20 — часть о целях и мстителях, код хвоста 46 `pending_acts`, 85, 86; хвосты мутантов 80,
82, 87 — при касании). У NPC появляются цели (`NpcGoal`): месть, долги в обе стороны. Цели превращаются в события через
триггеры world_sim. Сюда же смена бога и hazard (BACKLOG 10) и нарративный `ends_when` (BACKLOG 9).

## Решения

- 2026-10-18, проектировщик (груминг свинопаса, П1–П12; П12 — свой вариант, остальные — по рекомендации свинопаса):
  - П1 (в): цели ставят движок (по фактам: бой, сделка, долг) и рассказчик/world (запросом).
  - П2 (в): «должники» — оба направления: NPC должен герою (`debt`/`life_debt`) и герой должен NPC (`combat/defeat.py`
    `do_debt`).
  - П3 (а): цель превращается в событие через триггер NPC; механизм окончательно выбирает архитектор.
  - П4 (в): цель закрывает и движок по фактам, и рассказчик/world запросом.
  - П5 (в): мстители за убитых — только уже существующие NPC той же группы/родни; новых движок не создаёт (с Ж4).
  - П6: цели проверяются реже, как у богов (не на каждой границе сцены).
  - П7 (нет): «сын убитого вырастает и мстит» — не в Ж2 (Н5).
  - П8 (б): смену бога запускает рассказчик запросом после сделки/квеста в сцене; триггер пака — позже. Стартовая
    благосклонность +1 к новому богу (ТЗ 4.2) — без изменений.
  - П9 (б): hazard глобального события в тике бросается только герою, когда он в зоне, автоматически.
  - П10 (б): бежавший/безымянный выживший попадает в `known_npcs` только при активной цели (BACKLOG 85).
  - П11 (а): имя, совпадающее с видом существа, отклоняется (BACKLOG 86), раз Ж2 трогает `name_problem`.
  - П12: Ж2 целиком (BACKLOG 9, 10, 20, 46, 85, 86) с миграцией m0012, если понадобятся поля. Номер схемы и состав
    шага — архитектору (v12 занята под М0).
- 2026-10-18, проектировщик (развилка архитектора): версия сейва — вариант А: m0012 → v12 в Ж2 под поле
  `WorldSim.goals_checked_s`; М0 → v13, С0 → v14.
- 2026-10-18, проектировщик (вопросы по плану, «окей, кабаним»): В1 — перечень F1–F5 утверждён как есть (порог −40,
  отряд мстит при отношении ≤ 0); после ревью коммита 1 (п. 2): F2 — месть только за врагов, убитых самим героем
  (убил напарник — мести герою нет); убийца пишется в `Participant.last_hit_by` в `downed.kill_monster` (без смены
  схемы); смерть без убийцы (взрыв при смерти, окружение) засчитывается герою; старые триггеры `debt_<hero>` в сейвах
  остаются как есть, без миграции (п. 6 ревью); В2 (а) — провал спасброска от hazard = +1 истощение; В3 (а) — смена бога отклоняется
  только при `unknown_god`/`same_deity`, старый бог не трогается.
- 2026-10-18, проектировщик (ревью и аудит коммита 2, все — по рекомендации): 1А — hazard в тике бросают все активные
  герои в зоне; 2А — при `affects` без «все» герой hazard не бросает (как множитель смертности); 3А — не больше одного
  hazard от события на героя в день (тик и запрос рассказчика); 4А — постановка цели мёртвому NPC отклоняется
  `npc_not_alive`, закрытие разрешено; 5А — закадровая смерть с `by=<герой>` даёт мстителей; 6А — пустой `goal_target`
  = текущий герой. Уточнение 3А (2026-10-19, вариант Б): ограничение «раз в день» только внутри тика; запрос урона
  рассказчика с событием не связан и не ограничивается.
- 2026-10-19, проектировщик (повторный аудит коммита 2, R1): вариант Б — при мягком сбое world откладываются только
  act, по чьему `then_ref` не прошёл ни один запрос (без потерь и дублей по остальным).
- 2026-10-19, проектировщик (ревью коммита 3, п. 1 — накрутка сменой бога туда-обратно): +1 даётся только богу, которому
  герой раньше не служил; возврат к прежнему богу — без прибавки. Уточнение (2026-10-19): «служил» — по ключу бога
  в `hero.favor`, без нового поля сейва; неточность (бог из `favor_change` при принятии без +1) — в «Итог».
- 2026-10-19, проектировщик (повторный аудит коммита 3): прежний бог после смены виден рассказчику в `divine_data` как
  «равнодушен» (favor 0) — оставить.

## Груминг

- Свинопас (2026-10-18): вердикт до ответов — не готов. Ни ТЗ, ни код не описывают, как цель становится событием:
  цель ставится только в `rules/survivors.py` (`life_debt`), не закрывается; `NpcUpdate`/`WorldNpcUpdate` полей цели
  не имеют; кандидаты world (`world_sim/triggers.py`, `candidates.py`) собираются только из `opportunity`. Расхождения:
  - ROADMAP: строка Ж2 решает 85 «если ЖП3 не покажет иначе», а ЖП3 идёт после Ж2 — архитектору (снято П10).
  - ТЗ 4.1.3, ARCHITECTURE E11: о целях — только список видов и «код записи — позже».
  - «Должники» в коде — два разных долга (`do_debt` и `GOAL_KINDS`) — снято П2.
  - BACKLOG 20 не отмечает, что часть о выживших закрыта в Ж1 — архитектору.
  - BACKLOG 10: `change_deity` нигде не вызывается, `Trigger.then` — только текст (П8); hazard NPC дал бы двойной счёт
    смерти с `mortality_multiplier` (П9).
  - BACKLOG 9: `close_events` молча пропускает `NEEDS_NARRATIVE`; переиспользовать `candidates.verdict_candidates`.
  - BACKLOG 46: триггер срабатывает (`fire`) до вызова world, при `world_skipped` его act теряется — папе-кабану.
  - Объём L 1,4 занижен для такого состава.
- 2026-10-18, проектировщик: сменить бога может любой герой, не только жрец (П8; = А1 аудита).
- 2026-10-18, проектировщик (вопросы аудита груминга):
  - А2 (в): список событий, которые сами ставят NPC цель, предлагает папа-кабан, проектировщик утверждает (черновик —
    вариант а свекрови: бежавший/сдавшийся с отношением ≤ −40 мстит; родня/отряд убитого мстит; пощажённый благодарен;
    проигравший бой герой в долгу).
  - А3 (в): частота проверки целей — настройка, как у богов, по умолчанию раз в игровой день.
  - А4 (б): долг героя перед NPC — при поражении кредитору ставится обычная цель «долг», дальше она работает как остальные
    цели (одна механика для обоих направлений).

## Решения архитектора

2026-10-18, kaban-arhitektor (по вопросам свинопаса и свекрови; детали — папе-кабану в плане):

- **Механизм «цель → событие» (П3а).** Цель `NpcGoal` при создании порождает триггер-спутник в `npc.opportunity` —
  ровно так уже делает `combat/defeat.do_debt`: `id = goal:<kind>:<target>`, `if` = структурная часть (что выводится из
  состояния: герой жив, носитель жив…) + нарративный остаток (`narrative: text`), `then` = текст цели, `once`. Дальше
  работает готовая цепочка без новых видов кандидатов: `candidates.verdict_candidates` → вердикт world → `fire` →
  act → `WorldNpcUpdate(then_ref)` (перемещение NPC к герою, появление в сюжете). Связь цель↔триггер — по id, нового поля
  в `NpcGoal` нет. Отказ от варианта б (отдельный вид кандидата): дублирует verdict/act и требует правок `apply_verdicts`
  и промпта world. Закрытие (П4): `fire` триггера цели → `done`; смерть/`gone` носителя или цели → `dropped` и триггер
  `disabled` (движок); `goal_status` запросом рассказчика/world. Долг героя (А4б): `do_debt` вместо прямого триггера
  ставит кредитору `NpcGoal(debt, target=hero)` — триггер строится общей функцией, одна механика на оба направления.
- **Редкая проверка целей (П6/А3).** Триггеры-спутники целей пропускаются в `triggers.check` и `verdict_candidates`,
  пока не истёк `[world] goals_check_every_days` (конфиг `RulesConfig`, по умолчанию 1) от последней проверки; после
  проверки метка обновляется — как `god_checked_s` у богов, но одна на мир (`WorldSim.goals_checked_s`): отдельная метка
  на NPC из требований не следует, цели проверяются «пачкой» раз в день. Обычные триггеры пака у NPC не затронуты.
  `max_calls_per_day` world остаётся вторым потолком.
- **Версия схемы (П12).** Единственное новое поле — `WorldSim.goals_checked_s`; поля запросов (`goal_*` в
  `NpcUpdate`/`WorldNpcUpdate`), 9, 10 (смена бога, hazard), 46, 85, 86 полей сейва не требуют. Развилка проектировщику:
  (А, рекомендация) m0012 → v12 в Ж2: чисто, по образцу Ж0 (миграция `setdefault`, отпечаток `save_v12.schema.json`,
  фикстура v11, dusk-скрипт +12), цена ≈ 0,15–0,2; М0 → v13, С0 → v14 (шапка ROADMAP поправлена). (Б) без версии —
  метка в `world.flags["sim:goals_checked_s"]` (`int` там допустим): дешевле, но учёт симуляции в игровых флагах —
  смесь ответственности, которую потом всё равно переносить в М0.
- **Смета.** L+ ≈ 1,9 млн ток. (цели с протоколом/промптом/мстителями ≈ L 1,4 — Ж1 при сравнимом составе вышел в L;
  хвосты 9, 10, 46, 85, 86 ≈ S 0,5); ×1,4 ≈ 2,7; по мерке Ж1 (L → $19) ≈ $26–28. Коммиты — ориентир, уточняет папа-кабан:
  1) ядро целей (`rules/goals.py`: создание/закрытие/триггер-спутник, перечень фактов А2, `do_debt` → цель, частота,
  85 `known_npcs` только с целью, 86 `name_problem`) [+ m0012]; 2) протокол и world — поля `goal_*`, 46 `pending_acts`
  (act при `world_skipped` — в `pending_acts`, исполняется на следующей границе), 9 `ends_when` verdict-кандидатом
  (`close_events` + ref `event:<id>` в `apply_verdicts`), hazard герою в тике (П9б, `roll_hazard` без запроса);
  3) смена бога — запрос `change_deity` любому герою (А1), +1 к новому, 82 `favor_change`; 4) доки и «Итог».
  46 должен лечь не позже коммита 2: act мстителя иначе теряется при `world_skipped`.
- **Граница BACKLOG 20.** Выжившие боя — Ж1 ✅; цели/мстители/должники — Ж2; соратники (`follows`) — Ж5; «сын вырастает»
  (П7) — Н5, где пункт закрывается и уходит в done/. Отметки — в строках Ж2/Ж5/Н5 ROADMAP; тело пункта в BACKLOG.md не
  правится (RULES).
- **Строки Ж2/ЖП3 про 85** — противоречие снято: 85 решён П10 здесь, ЖП3 наблюдает результат (мститель виден, прочие
  бежавшие — нет).
- Папе-кабану открыто: структурная часть `if` у триггера цели (нужна ли близость к герою для `revenge`/`debt` или это
  решает world); состав `goal_*` полей запросов; что именно кладётся в `pending_acts` (ref или сериализованный act).

## Аудит груминга

- Кабан-свекровь (2026-10-18): решений за проектировщика нет; буква П5 исправлена (а → в, смысл прежний). Противоречий
  с Ж0/Ж1 нет (Q7 Ж0 запрещал world писать только память NPC, не цели); в доках E11/E12 — кто пишет цели. П9(б) не
  трогает закадровую смерть NPC от hazard (world) — отметить в «Итоге». Вопросы А2–А4 — проектировщику. Архитектору:
  версия схемы при m0012, смета «целиком», механизм П3/П6, противоречие строк Ж2/ЖП3 про 85, отметка в BACKLOG 20.
  Папе-кабану: 46 `pending_acts`.

## План

Папа-кабан, 2026-10-18, версия 1. Сейв v12 (m0012, поле `WorldSim.goals_checked_s`).

### 0. Решения папы-кабана (в рамках П1–П12, А2–А4)

1. **Триггер-спутник.** `rules/goals.py` (новый): `add_goal(npc, kind, target, text, now_s)` создаёт `NpcGoal` и триггер
   `Trigger(id=f"goal:{kind}:{target}", if={"all": [<структурная часть>, {"narrative": NARRATIVE[kind]}]}, then=text,
   once=True)` в `npc.opportunity`. Структурная часть: цель на героя — `{"not": {"hero_dead": true}}`; на NPC —
   `{"npc_status": {"id": target, "is": "alive"}}`. Близости к герою в `if` нет — приход мстителя решает world через
   `WorldNpcUpdate(location_id, then_ref)`. `NARRATIVE` — константы текстов по виду (как `LIFE_DEBT_TEXT`). Одна
   активная цель на `(kind, target)`: повтор → `None` (протокол — `Invalid goal_exists`). Старый спутник закрытой цели
   при новой цели убирается. Связь цель↔триггер — только по id.
2. **Факты, по которым движок ставит цели (А2, на утверждение — В1).**
   - F1 `revenge` — бежавший или сдавшийся при материализации с отношением ≤ `[survivors] revenge_attitude_max`
     (по умолчанию −40: бежавший попадает, сдавшийся с 0 — нет) — `survivors.remember_fight`.
   - F2 `revenge` за убитого героем (участник боя `dead` в `end_fight`; NPC мира — `npc_update status=dead by=<hero>`):
     (а) родня — живые NPC с `FamilyLink.ref` = убитый; (б) отряд — живые NPC с группой убитого в `npc.groups`, не
     участники боя, не `follows` героя, с отношением ≤ 0. Мстителям — память `kin_killed` (если есть сцена). Новых NPC
     не создаётся (П5).
   - F3 `gratitude` — пощажённый при материализации; `life_debt` перебежчику — как в Ж1, но через `add_goal`.
   - F4 `debt` героя — `do_debt`: кредитору `add_goal(npc, "debt", hero.id, text)` вместо `Trigger("debt_<hero>")`;
     `world.flags["debt:<hero>"]` остаётся (А4б).
   - F5 — рассказчик/world: поля `goal_*` (п. 0.5). «Сын вырастает» — Н5 (П7).
3. **Закрытие (П4).** `goals.mark_fired` после `fire` в `triggers.check` и `verdicts.apply_verdicts` → `done`.
   `goals.sweep(world, heroes)` в начале `triggers.check`: носитель не `alive` → `dropped`; мишень мертва/ушла →
   `dropped` + спутник `disabled`. `goal_status` done/dropped — запросом.
4. **Редкая проверка (П6/А3).** `WorldSim.goals_checked_s: int | None = None`; `goals.due(sim, now_s, every_days)` —
   как `god_due`. `triggers.check(bundle, cfg)` считает `due` один раз, передаёт в `verdict_candidates(..., skip_goals=
   not due)`; после проверки `goals_checked_s = now_s`. Конфиг `[world] goals_check_every_days = 1` в
   `settings.WorldConfig`. Обычные триггеры не затронуты; `max_calls_per_day` — второй потолок.
5. **Протокол `goal_*`** в `NpcUpdateBase`: `goal_kind` (`GOAL_KINDS` + "none"), `goal_target` (пусто = герой),
   `goal_text`, `goal_status` (none/done/dropped). `handlers/world.goal_problem`: `goal_fields_without_kind`,
   `unknown_goal_target`, `goal_exists`, `no_such_goal`; `change_goal` — `add_goal`/`close_goal`, лог через
   `npc_label`. Оба пути `npc_update` (рассказчик и `offscreen`). У world `then_ref` обязателен.
6. **46 `pending_acts`** — сериализованный `Candidate.model_dump_json()`, не ref. `candidates.stash_acts` (только
   `act`, дедуп по ref) на `world_skipped`; `candidates.take_acts` до вызова world: восстановленные (владелец жив) +
   новые, сортировка `sort_key`, очистка; повторный пропуск — снова в stash. Без сессии world не копится. Потолок 20.
   Битые записи отбрасываются молча.
7. **9 `ends_when`** — verdict-кандидат `event:<id>` (`candidates.event_candidates`, `OWNER_RANK["event"] = 4`);
   `apply_verdicts` при holds → `event.ends_at_s = now_s` (хронику пишет тик). `nudge.mark_not_participating`
   пропускает `event:`. `close_events` не меняется.
8. **hazard в тике (П9б).** `world_sim/hazard.py`: `roll_hazards` из `tick.tick_days` раз в день после
   `mortality.roll_day`: герой в зоне события с `hazard` → спасбросок `saving_throw`; провал — по В2; хроника `event`.
   Закадровая смерть NPC от hazard у world не меняется (отметить в «Итоге»).
9. **Смена бога (П8/А1, В3).** Запрос `ChangeDeity(god_id, reason)` в `MODE_TOOLS["explore"]`,
   `handlers/world.change_deity`: `unknown_god` / `same_deity`, затем `divine.change_deity` (+1 к новому), хроника
   `favor`, журнал `god`. Любой герой. `PromptBuilder.divine_data` — поле `deity`. `favor_change`/`reveal_secret`
   не трогаются (хвост 82 остаётся).
10. **85 (П10).** `master/relevance.npc_reasons`: `not (npc.named or goals.has_active_goal(npc))`.
11. **86 (П11).** `rules/npc_names.looks_like_kind` — имя = метка/метка без номера/имя монстра реестра → `rejected`.
12. **m0012 → v12.** `migrate_v11_to_v12`: `world["sim"].setdefault("goals_checked_s", None)`;
    `CURRENT_SCHEMA_VERSION = 12`; отпечаток `tests/schema/save_v12.schema.json`; фикстура `tests/fixtures/saves/v11`
    снимается до правок кода; `scripts/migrate_dusk_18plus.py` += 12; `test_migration_v12.py`.
13. **Промпты.** `narrator_rules.md`: когда ставить/закрывать цели, безымянные с целью в `known_npcs`,
    `change_deity`. `world_rules.md`: verdict на `event:`, `goal_*` при исполнении then, act мстителя — `location_id`.
    `STATIC_MAX` — по замеру.
14. smells 200/200: отдельные `goal_problem`/`change_goal`; `tick_days` — одна строка вызова `hazard.py`.

### 1. Файлы

Новые: `rules/goals.py`, `world_sim/hazard.py`, `persistence/migrations/m0012_v11_to_v12.py`,
`tests/schema/save_v12.schema.json`, `tests/fixtures/saves/v11`.
Правки: `state/world.py`, `config/settings.py` + `defaults.toml`, `rules/survivors.py`, `combat/defeat.py`,
`game/turn.py`, `world_sim/{triggers,candidates,verdicts,nudge,tick}.py`, `game/boundary.py`, `master/relevance.py`,
`master/prompt.py`, `master/world.py` (при нужде), `protocol/{requests,schema,apply}.py`,
`protocol/handlers/{world,offscreen}.py`, `rules/npc_names.py`, `persistence/migrations/__init__.py`,
`scripts/migrate_dusk_18plus.py`, `master/prompts/{narrator_rules,world_rules}.md`,
`tests/unit/master/test_static_budget.py`.
Доки (коммит 4): TZ 4.1.2, 4.1.3 «Цели NPC (Ж2)», 4.2; ARCHITECTURE — E11 «Цели NPC», «Сейв v12 (Ж2)», E12, A6;
glossary; карточки done/ 9, 46, 85, 86; BACKLOG 10 и 20 остаются.

### 2. Партии

- Коммит 1 — ядро целей и сейв v12 (≈ 40 %): п. 0.1–0.4, 0.10–0.12, F1–F4 (кроме F2 вне боя), конфиг, gating,
  `relevance`, `looks_like_kind`.
- Коммит 2 — протокол и world (≈ 35 %): п. 0.5–0.8, F2 вне боя, промпты, `STATIC_MAX`, 46.
- Коммит 3 — смена бога (≈ 10 %): п. 0.9.
- Коммит 4 — доки и «Итог» (≈ 15 %).

### 3. Тесты (kaban-doeba, TDD)

- `tests/unit/rules/test_goals.py`: `add_goal`/спутник, повтор, замена закрытого, `close_goal`, `mark_fired`, `sweep`,
  `due`, `avengers` (родня, отряд, исключения), `on_kill` и `kin_killed`.
- `test_survivors.py`: бежавший −40 → `revenge`, порог из конфига, сдавшийся 0 → нет, пощажённый → `gratitude`,
  перебежчик → `life_debt` со спутником.
- combat/defeat: `do_debt` → цель `debt` + `goal:debt:<hero>`, флаг остаётся, старого `debt_<hero>` нет.
- world_sim: gating по `due`, `goals_checked_s`, вторая граница в тот же день, `fire` → `done`; verdict `event:`;
  `nudge` на `event:`; `test_tick_hazard.py` (зона, раз в день, провал по В2, смерть на 6-м истощении, детерминизм).
- game: `pending_acts` — stash/take, повтор, мёртвый владелец, потолок 20, nudge-act с тем же `then`.
- protocol: `goal_*` (все отказы), `change_status by=hero` → мстители, `name_problem` (вид), `change_deity`, схемы
  `tool_set`.
- master: безымянный с целью в `known_npcs`; `STATIC_MAX`; `divine.deity`.
- persistence: `test_migration_v12.py`, отпечаток схемы, `migrate_dusk_18plus` (+12).
- Сценарий `tests/scenarios/test_zh2_goals.py`: бежавший −40 → verdict → act → мститель в сцене; `world_skipped` и
  доигрывание.

### 4. mutmut

`ai_dm.rules.goals:*`, `rules.survivors:remember_fight`, `combat.defeat:do_debt`, `game.turn:TurnRunner.end_fight`,
`world_sim.triggers:check`, `world_sim.candidates:{verdict_candidates,sort_key,event_ref,event_candidates}`,
`world_sim.pending:{load_acts,stash_acts,stash_unapplied,take_acts,owner_present}` (коммит 2: вынесено из candidates),
`protocol.apply:{apply,note_applied}`, `master.world:WorldSession.run`, `master.session:TurnFailed.__init__`,
`world_sim.verdicts:{apply_verdicts,find_owner}`, `world_sim.nudge:mark_not_participating`, `world_sim.tick:tick_days`,
`world_sim.hazard:*`, `game.boundary:{check_triggers,call_world}`, `master.relevance:npc_reasons`,
`master.prompt:PromptBuilder.divine_data`, `protocol.handlers.world:{name_problem,update_problem,npc_update,
change_status,goal_problem,change_goal,change_deity}`, `protocol.handlers.offscreen:npc_update`,
`rules.npc_names:looks_like_kind`, `persistence.migrations.m0012_v11_to_v12:migrate_v11_to_v12`. TESTS — по модулю.
Хвосты: 80/87 — `update_problem`, `npc_update` касаются → старых выживших разобрать; прочие — остаются. 82 — остаётся.

### 5. Риски

- Лавина мстителей при `goals_check_every_days = 1` — крутить настройку (наблюдение ЖП3).
- F2б «отряд» по `groups` может задеть NPC пака — проверить на мини-паке.
- `triggers.check(bundle, cfg)` ломает контракт world_sim_kit — обновить одним коммитом.
- `pending_acts` как JSON — битые строки отбрасываются.
- Рост `known_npcs` и схемы `npc_update` — `STATIC_MAX` по замеру (≈ 19,7k при 20050).
- Фикстуру v11 снять до правок; `tests/golden/zh0_turn.json` не меняется.
- В2а: чума в зоне на 30 дней может убить истощением — ожидаемо.

### 6. Объём

L+ ≈ 1,7–1,9 млн ток.: kaban 0,55, doeba 0,75, mama 0,2, svekrov 0,08, доки/тесть 0,1; ×1,4 ≈ 2,5–2,7; ≈ $26–28.

## Ревью и аудит

- Коммит 1, кабан-свекровь (2026-10-18): чисто, сверх плана ничего; тексты целей (`GRATITUDE_TEXT`, `REVENGE_TEXT`,
  `NARRATIVE`) — служебные, оставить. Замечание: F2 «убитого героем» vs код «любой мёртвый враг» — вопрос проектировщику.
  Шапка ROADMAP про v12 «выбор за проектировщиком» устарела — архитектору.
- Коммит 2, кабан-свекровь (2026-10-18): сверх плана ничего; вопросы — hazard всем героям, `affects` без героя, цель
  мёртвому NPC; вмешательство бога при смерти от hazard — общее правило ТЗ 4.2.
- Коммит 2, мама-кабан (2026-10-18): нужны правки — R1 повтор act при мягком сбое после частичного применения;
  R2 двойной hazard за день; R3 закадровая смерть и мстители; R4 пустой `debt_scene` у hazard без сцены; FUNCS mutmut —
  `world_sim.pending`; `goal_target or hero.id` дважды; `goal_fields_problem` раньше `empty_update`; цель применяется
  раньше `status=dead`; стиль — `merchant_goal_problem`, комментарий verdicts.py:38, `event.type` в хронике hazard.
- Коммит 1, мама-кабан (2026-10-18): нужны правки — smells 204 (п. 1), F2 убийца (п. 2), имя без номера (п. 3),
  `mark_fired` в `check` не срабатывает (п. 4, «если не хватит smells»), 86400 (п. 5), старые `debt_<hero>` (п. 6).
- Коммит 3, кабан-свекровь (2026-10-19): чисто; снятие `change_deity` из vulture_allowlist — устаревшая заглушка, оставить.
- Коммит 3, мама-кабан (2026-10-19): можно мержить после п. 1 — п. 1 накрутка сменой бога A→B→A→B; п. 2 при `FAVOR_MAX`
  прибавка молча обрезается, а лог обещает +1 (в «Итог»); п. 3 повторный mutmut по `change_deity`; п. 4 фраза про механику
  в narrator_rules.md лишняя.
- Коммит 3, повторно (2026-10-19): мама — можно мержить (п. 1, 2, 4 закрыты; mutmut обработчика 59/59, divine 0 выживших);
  свекровь — чисто, вопрос о видимости прежнего бога решён проектировщиком (оставить).

## Правки по ревью

- Коммит 1 (кабан, 2026-10-18): п. 1 — smells 204 → 200 (`add_npc_goal`/`put_goal` вместо `npc_target`, `on_kill(bundle,
  hero, part, state, cfg)`, `fire_trigger` из `check`, `goals.skipped`, `rejected_name`); п. 3 — `participant_name`,
  в тексте «Воин-гоблин 1»; п. 5 — `rules.trade.DAY_S`; п. 4 — не нужен (smells уложились, тест на `mark_fired`
  в `check` есть). П. 6 — известный хвост в «Итог»: в старых сейвах триггеры `debt_<hero>` без цели, миграции нет.
  П. 2 — по решению проектировщика (см. «Решения»): `downed.kill_monster` пишет `last_hit_by = attacker_ref`;
  `goals.on_kill` выходит, если `last_hit_by` не `None` и не герой; `end_fight` обрабатывает одного героя, неоднозначности
  нет. smells 200/200, схема v12 не менялась.
- Коммит 2 (кабан, 2026-10-18): R1 — отката у `world.run` нет; `call_world` снимает дамп мира, `pending.stash_if_unchanged`
  откладывает act только при неизменённом мире (при частичном применении act теряются, дублей нет); 3А — по решению
  проектировщика (Б) код не менялся; 4А — `goal_state_problem` даёт `npc_not_alive` при постановке цели мёртвому/ушедшему
  или при `status` в том же запросе; 5А/R3 — как есть; R4 — пустой `debt_scene` безопасен; `goal_target_of`;
  `GOAL_FIELDS` в `nothing_to_change` — `goal_fields_without_kind` раньше `empty_update`; `merchant_goal_problem`
  оставлена ради smells (комментарий); комментарий verdicts.py уточнён. smells 200/200.
- Коммит 2, вариант Б по R1 (кабан, 2026-10-19): `TurnContext.applied_refs`, `protocol.apply.note_applied`,
  `TurnFailed.applied_refs` (проброс из `WorldSession.run`), `pending.stash_unapplied` вместо `stash_if_unchanged`, дамп
  мира удалён; цель вместе со `status` — отказ `goal_kind_with_status`. Повторное ревью и аудит — можно мержить.
  Известное ограничение (в «Итог»): act, исполненный через `set_flag`/`world_notice` без `then_ref`, при сбое world
  повторится на следующей границе (для `world_notice` — повторная заметка).
- Коммит 3 (кабан, 2026-10-19): п. 1 — по решению проектировщика: `divine.change_deity` возвращает сдвиг; прежний бог
  получает ключ `favor` (0), новый +1 только без ключа; хроника и лог пишут «благосклонность +1» лишь при прибавке;
  п. 2 закрыт тем же (бог без ключа стартует с 0, обрезки нет); п. 3 — повторный mutmut 54/54; п. 4 — фраза убрана.
  Побочно: прежний бог виден в `divine_data` как «равнодушен».

## Итог

Ж2 закрыт 2026-10-19 (коммиты: ядро целей и сейв v12; протокол и world; смена бога; доки).

### Закрытые пункты

- BACKLOG 9 (нарративный `ends_when` — verdict-кандидат `event:<id>`), 46 (`pending_acts`), 85 (безымянный с активной
  целью виден в `known_npcs`), 86 (имя = вид отклоняется) — карточки в `docs/done/`.
- BACKLOG 10 — частично: смена бога (`change_deity`) и hazard в тике сделаны; `favor_change`/`reveal_secret` не
  трогались (хвост 82), триггер пака для смены бога — позже (П8).
- BACKLOG 20 — частично: цели, мстители и должники сделаны; соратники (`follows`) — Ж5, «сын вырастает» — Н5.

### Стоимость

Кабан-тесть, 2026-10-19 04:48 UTC (`metrics.py` по основной сессии; fable — по ценам Opus). Время — интервал запусков
с ожиданием возобновлений.

| Роль | Модель | Запусков | Токены, млн | Время, мин | $ |
|---|---|---|---|---|---|
| kaban | sonnet-5-5 | 4 | 16,7 | 217 | 4,76 |
| kaban-doeba | sonnet-5-5 | 4 | 26,7 | 208 | 6,40 |
| mama-kaban | opus-5-5 | 3 | 1,8 | 163 | 1,80 |
| kaban-svekrov | opus-5-5 | 4 | 1,2 | 117 | 1,60 |
| papa-kaban / архитектор | fable-5-1 | 2 / 3 | 1,9 / 0,8 | 64 / 8 | 1,85 / 1,16 |
| svinopas | opus-5-5 | 1 | 0,9 | 4 | 0,53 |
| оркестратор* | opus-5-5 | 1 | 21,8 | 876 | 8,59 |
| kaban-test | opus-5-5 | 1 | 0,03 | — | 0,10 |
| **итого** | | 23 | 71,8 (кэш-чтение 67,3) | шаг 851 | **26,81** |

\* на момент подсчёта; kaban коммита 4 (доки, sonnet, 88k ток., 2,6 мин) не учтён.

Смета ≈ $26–28 — факт в смете. Сверх сметы — оркестратор ($8,6, в смете не было) и мама/свекровь ($3,4 против 0,28 млн
ток.); ниже — kaban + doeba ($11,2). Переделки после первого ревью — 49 % времени субагентов (коммиты 2–3).

### Известные ограничения

- Старые триггеры `debt_<hero>` в уже идущих сейвах остаются без цели: миграции нет (решение проектировщика, п. 6 ревью
  коммита 1). Новые долги идут целью `debt` и триггером `goal:debt:<hero>`.
- Hazard NPC у world не менялся (П9): закадровая смерть NPC от события по-прежнему идёт через `mortality_multiplier` и
  запрос world; hazard бросается только героям в зоне.
- `act`, исполненный через `set_flag`/`world_notice` без `then_ref`, при мягком сбое world повторится на следующей
  границе (для `world_notice` — повторная заметка): учёт «применено» идёт по `then_ref`.
- Бог, получивший ключ `favor` через `favor_change`, при принятии героем не получает +1: «служил» определяется по
  ключу бога в `hero.favor`.
- Выжившие мутанты `PromptBuilder.divine_data` на старых строках (35) — BACKLOG 95.
