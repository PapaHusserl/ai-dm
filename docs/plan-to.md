# План мини-партии #21 «ТО Отказы Gemini и репорты» (T1/BACKLOG 62 + T9 + лимит issues/)

Автор: papa-kaban, 2026-10-16. Статус: **утверждён 2026-10-16** (Q1а Q2б Q3а Q4б Q5а Q6а — все по рекомендациям, текст 18+ — заготовка papa). Груминга нет (техдолг по
правилу фикса, прецеденты TV-PLAN, TM-PLAN). Smells 200/200 — нулевой баланс. Сейв: **v10 без изменений** (схема не
трогается; строка ROADMAP #21 «v9» устарела после ТМ).
Источники: ROADMAP #21; BACKLOG 62, 64 (T9), 30 (лимит issues/, риск D.3 6а); docs/plan-techdebt.md T1/T9 и §4 п.4;
T60-PLAN п.1.5 (авто-переключение по цепочке — отвергнуто Q3(б) **для сети**; здесь — для детерминированных отказов,
как прямо просит ROADMAP #21), 19F-PLAN Q1(г), docs/plan-zhp1.md, docs/plan-tm.md; ARCHITECTURE E3а (цепочка), стр. 471
(refusal → SOFTEN), стр. 839 (`issues/`).

## 0. Офлайн-проверка гипотез (сделано; saves/ только чтение, сети нет)
**T1 — подтверждён** (`saves/dusk_academy-d3de6c57/issues/*-refusal*`, 11 репортов, все на `gemini-3.8-flash`):
- Во всех 11 журналах `response.stop_detail == "PROHIBITED_CONTENT"` (кандидат с `finish_reason`, не блок промпта).
  t95: 2 раунда инструментов → отказ (3 вызова); t216: 1 раунд → отказ; t258 ×4, t262 ×3, t368 ×2: отказ → повтор с
  `SOFTEN_NOTE` → снова отказ (2 вызова, теги `refusal_retry+refusal`). Повтор с припиской не помог **ни разу из 9**.
- `[llm] gemini_safety = "block_none"` уже стоит — `PROHIBITED_CONTENT` это не снимает (ненастраиваемый фильтр Google).
- Код: `llm/gemini_adapter.py:12 FINISH_REASONS` (`SAFETY`/`PROHIBITED_CONTENT`/`BLOCKLIST`/`SPII`/`RECITATION` → `refusal`),
  `stop_detail` (стр. 282) отдаёт сырой повод; `master/session.py:388` поднимает `TurnFailed("refusal", "…(детали).", ["refusal"])`
  — повод есть только в тексте; `game/turn.py:207 play_turn` берёт `RETRY_NOTES["refusal"]` → один повтор на той же модели;
  `game/app.py:338 choose_error` — смена модели только через меню (Т60 Q3б). `game/models.py next_in_chain` и
  `[llm] narrator_chain` (3.8-flash → 4-argon → 3-flash-preview → 3.5-flash-lite) уже есть; `GameApp.set_narrator` пишет
  `models.json`, world/summarizer следуют за провайдером (внутри Gemini не меняются). Журнал и `ReplayAdapter`
  (`ChatResponse.model_validate(record["response"])`) несут `stop_detail`; мок (`llm/mock.py STEP_KEYS`) — нет.
- Пак: `campaigns/dusk_academy/world.md` — «несколько юных представителей ночного народа», «школа магии», «первая любовь»;
  `campaign.yaml` — `scene_summary` «староста первого курса», `tone.romance = намёки`, `notes` про первую влюблённость;
  `locations.yaml:80` «Общежитие первокурсников». Нигде нет указания, что студенты — взрослые. **Важно:** `world_text`
  (`world.lore.world_text`) и `tone` лежат в сейве (`cli.py:1003`, `campaign/merge.py merge_new` догружает только
  локации/NPC/предметы) — правка пака дойдёт **только до новых миров**, идущий `dusk_academy-d3de6c57` её не увидит (Q4).

**T9 — подтверждён**: `GameApp.after_turn` → `auto_report(turn)` на каждый результат с тегами; `runner.retry()` →
`run_turn(last_input)` даёт новый run_id и тот же набор тегов → новый каталог. t258 ×4 за 24 с, t262 ×3, t368 ×2 — 9 лишних.

**Лимит issues/**: `dusk_academy-d3de6c57/issues` — 20 каталогов, 17 МБ (≈ 0,85 МБ на репорт: before/after + журнал с блобами);
дракон 8 → 6,5 МБ. Аналог ротации — `llm/journal.py` (`[journal] max_mb`, `MB = 1_000_000`, удаление самых старых сегментов).

## 1. Решения (архитектура)
1. **Повод отказа в исключении.** `master/session.py TurnFailed.__init__(reason, message, report_tags=None, detail=None)` →
   `self.detail`; `MasterSession.run` (стр. 388): `TurnFailed("refusal", …, ["refusal"], detail=response.stop_detail)`.
   Остальные места создания `TurnFailed` (`network`, `fatal`, `invalid`, `rounds`, `short`, `round_limit`) не меняются.
2. **Жёсткий отказ — без SOFTEN-повтора.** `game/turn.py`: константа `HARD_REFUSALS = ("PROHIBITED_CONTENT", "BLOCKLIST",
   "SPII")` (Q2) и функция модуля `hard_refusal(failure) -> bool` (`failure.reason == "refusal" and failure.detail in
   HARD_REFUSALS`). `TurnRunner.play_turn`: `note = None if hard_refusal(failure) else RETRY_NOTES.get(failure.reason)` →
   жёсткий отказ сразу в `failed(result, failure)` (меню, `REFUSAL_HINT`, теги `["refusal"]`, 1 вызов вместо 2).
   `SAFETY`/`RECITATION`/отказ Claude (`detail is None`) — как раньше, один повтор с припиской.
3. **Переход по цепочке на жёстком отказе** (T1, Q1) — `game/app.py`, по образцу T60-PLAN п.1.5: `GameApp(…,
   refusal_chain=True)`; cli передаёт `not (args.mock or args.replay)` (как `auto_reports`). `after_turn(turn)`: перед
   `auto_report` — `turn, lines = self.chain_turn(turn)` (новый метод): пока `refusal_chain` и `hard_refusal(turn.failure)`
   и `next_in_chain(self.settings.app, self.current_key())` не None — `auto_report(turn)` (репорт отказавшей модели,
   см. п.4), `error = self.set_narrator(following)`; при ошибке (`MissingKey`, нет цены/окна) — строка ошибки и выход
   из цикла (меню как сейчас); иначе строка игроку «Модель {старая} отказала ({detail}) — переключаюсь на {новая}.» и
   `turn = self.runner.retry()`. Цепочка исчерпана или текущая модель не в цепочке (Claude, `next_in_chain` → None) —
   меню ошибки с `REFUSAL_HINT`, как сейчас. `set_narrator` постоянный (models.json; `/model` или меню вернут обратно);
   world/summarizer не трогаем: провайдер тот же, отказ summarizer на границе и так мягкий (backup на модели
   рассказчика, тег `refusal_fallback`). `choose_error("retry")` идёт через тот же `after_turn` → повтор из меню тоже
   переключает. `switch_role` при `refusal` остаётся `narrator`.
4. **Один авто-репорт на попытку хода и модель** (T9). `GameApp.auto_report`: ключ `(capture.turn_seq, tuple(capture.tags),
   capture.failure_reason, capture.model)`; для `status == "aborted"` — если ключ равен `self.reported` (новое поле, None в
   `__init__` и `load()`), репорт не пишется и строки нет; иначе пишем и запоминаем. Committed-ходы (`gold_repeat`,
   `choices_retry`, метки границы) пишутся всегда — turn_seq у них растёт. Вынести проверку в `already_reported(capture)
   -> bool`. Следствие: повтор из меню на той же модели — без репорта; повтор после смены модели (меню или цепочка) —
   репорт (видно, какая модель отказала); ход на другой модели с другим `failure_reason` — репорт.
5. **Лимит `issues/`** (Q3, Q5). `[reports] max_mb = 200` в `app_defaults.toml` (0 = без лимита); `ReportsConfig.max_mb:
   int = Field(default=200, ge=0)`. `reports/writer.py`: `dir_size(path) -> int` (сумма `st_size` по `rglob`) и
   `trim_issues(saves_root, world_id, max_mb) -> list[Path]`: каталоги `issues/*` без `tmp-*`, по имени (метка времени
   в начале имени — хронология), пока сумма > `max_mb * MB` (константа как в journal) — `shutil.rmtree` самого старого;
   самый новый не удаляется; `manual` (по `meta.json`, Q5а) пропускаются. Вызов — `GameApp.write_report_lines` после
   `write_report`, в `contextlib.suppress(OSError)` (репорт уже записан, обрезка — не повод для «Репорт не записан»);
   строки игроку нет (журнал ротируется молча — так же). `write_report` сигнатуру не меняем (параметров и так 7).
6. **Мок.** `llm/mock.py`: ключ шага `stop_detail` (в `STEP_KEYS`), `ScriptedAdapter.complete` кладёт его в `ChatResponse`;
   нужен для сценариев `ai-dm --mock` и тестов doeba без обёрток. `check_step`: `stop_detail` только вместе со `stop`.
7. **Пак dusk_academy** (Q4, Q6 — текст решает проектировщик). Кандидаты мест: `world.md` (первый абзац — «Академия —
   высшая школа…», «юных» → «молодых»), `campaign.yaml tone.notes` (строка «Все персонажи — взрослые (18+)…»),
   `locations.yaml:80`, `scene_summary` («первого курса» оставить/уточнить). Правка только текста, схема пака не
   меняется; `tests/golden`/фикстуры пака — проверить, что `dusk_academy` в них не захардкожен (doeba).
8. **Не делаем:** переименование тега `refusal_fallback` (BACKLOG 61); OpenAI/Claude в цепочке (BACKLOG 65); авто-переход
   на `network` (Т60 Q3б в силе); переход «на один ход» с откатом модели (Q1б); отказы в hero-/import-сессиях
   (`ui/hero_session.py`, `ui/import_session.py` — свои меню, цепочки там нет); удаление `tmp-*` остатков в `issues/`.
9. **Smells (нулевой баланс).** Новые ветки: `chain_turn`, `already_reported`, `trim_issues`, `dir_size` — отдельные
   функции. Компенсация при 201+: в `GameApp.set_narrator` два одинаковых блока «роль следует за провайдером» (world,
   summarizer) → `follow_provider(runner, role, provider)`.

## 2. Затронутые файлы
`src/ai_dm/master/session.py` (`TurnFailed`, `MasterSession.run`); `src/ai_dm/game/turn.py` (`HARD_REFUSALS`, `hard_refusal`,
`TurnRunner.play_turn`); `src/ai_dm/game/app.py` (`GameApp.__init__`, `after_turn`, новый `chain_turn`, `auto_report`, новый
`already_reported`, `write_report_lines`, `load`); `src/ai_dm/ui/cli.py:1000` (`refusal_chain=`); `src/ai_dm/reports/writer.py`
(`trim_issues`, `dir_size`); `src/ai_dm/config/app.py` (`ReportsConfig.max_mb`), `src/ai_dm/config/app_defaults.toml` (`[reports]`);
`src/ai_dm/llm/mock.py` (`STEP_KEYS`, `check_step`, `ScriptedAdapter.complete`); `campaigns/dusk_academy/{world.md,
campaign.yaml, locations.yaml}` (по Q6). Без изменений: `game/models.py`, `llm/gemini_adapter.py`, `llm/retry.py`,
`game/boundary.py`, `master/summarizer.py`, схема сейва. Документы: ARCHITECTURE (E3а — цепочка теперь и авто на жёстком
отказе; стр. 471 — SOFTEN не для `HARD_REFUSALS`; стр. 839 — `[reports] max_mb`, один репорт на попытку/модель);
шапки `game_kit.py`, `reports_kit.py`; BACKLOG 62, 64 (T9), 30 (лимит); ROADMAP #21 (v10); handoff;
`~/.config/ai-dm/checklists/checklist-to-live.md` (не коммитить).

## 3. Шаги kaban
1. `session.py`: `TurnFailed.detail`, передача `response.stop_detail` в `run`.
2. `turn.py`: `HARD_REFUSALS`, `hard_refusal`, ветка в `play_turn`.
3. `mock.py`: `stop_detail` в шаге.
4. `app.py`: `refusal_chain`, `chain_turn`, `reported`/`already_reported`, `load`; `cli.py` флаг. `make smells` после файла.
5. `config/app.py` + `app_defaults.toml`: `[reports] max_mb`; `writer.py`: `dir_size`, `trim_issues`; вызов в
   `write_report_lines`.
6. Пак — по решению Q6 (текст от проектировщика, kaban только вносит).
7. Офлайн-гейт (без сети): `ai-dm --mock` код 0; сценарий мока в scratchpad с шагом `{"stop": "refusal", "stop_detail":
   "PROHIBITED_CONTENT"}` на `gemini:gemini-3.8-flash` и фабрикой, отдающей мок для `gemini-4-argon`: ход после перехода
   принят, строка «переключаюсь», `models.json` = argon, в `issues/` один каталог `-refusal` (модель flash); тот же шаг
   без `stop_detail` → `refusal_retry+refusal`, как раньше. `--replay-report` копии
   `saves/dusk_academy-d3de6c57/issues/20261013T152805-t258-refusal_retry+refusal` с отключённой сверкой fingerprint
   (прецедент ТВ, скрипт в scratchpad): ход откатан после **1** вызова (второй, с SOFTEN, не нужен), меню ошибки.
8. Доки (§2); `~/.config/ai-dm/checklists/checklist-to-live.md` для ЖП в dusk_academy на 3.8-flash: сцена с прежним отказом (t258 — «обнять
   друзей») → один отказ, переход на argon, ход сыгран; `/model` показывает argon; `issues/` — один каталог на отказ;
   повтор из меню на той же модели — без нового каталога; при `max_mb` ниже текущего объёма — старые каталоги ушли,
   `manual` остались; после правки пака (Q4/Q6) — частота отказов на flash на 10 ходах сцены с романтикой.

## 4. kaban-doeba (TDD; cov/mutmut гоняет оркестратор фоном)
- `TurnFailed`: `detail` по умолчанию None; `run` кладёт `stop_detail` при отказе; у `network`/`fatal`/`invalid` detail None;
  `ask_choices` при отказе — как раньше (не поднимает).
- `hard_refusal`: каждая константа → True; `SAFETY`, `RECITATION`, None, не-refusal → False.
- `play_turn`: жёсткий отказ → 1 вызов, теги `["refusal"]`, меню, `REFUSAL_HINT`, бандл откатан (как
  `test_game_refusal_retry.py`, обёртка `RefuseOnce` с `stop_detail`); `SAFETY`/без detail → SOFTEN-повтор как раньше;
  повтор при жёстком отказе на втором раунде инструментов (t95) тоже не делается.
- `chain_turn` (по образцу `test_t60_menu.py`/`test_t60_models.py`, `FactorySpy`, `ScriptedAdapter(provider="gemini")`):
  flash жёсткий отказ → `set_narrator(argon)`, `models.json`, строка со старой/новой моделью и detail, ход сыгран на argon,
  `pending is None`, рассказ в ответе; argon → preview → lite все отказывают → 4 вызова, 3 строки, меню `ERROR_MENU` с
  `REFUSAL_HINT`; lite (последняя) отказала → меню без строки; текущая модель не в цепочке (claude/mock) → меню сразу;
  `refusal_chain=False` → меню сразу (старое поведение); фабрика `MissingKey`/нет цены → строка ошибки, меню, цикл стоит;
  мягкий отказ (без detail) → SOFTEN-повтор, перехода нет; `network` → перехода нет (Т60); повтор из меню (`choose_error
  ("retry")`) при жёстком отказе переключает; после перехода `model_options()` отсчитывает от новой модели;
  world/summarizer адаптеры не изменились; `cli` передаёт `refusal_chain` False при `--mock`/`--replay`.
- T9 (`test_auto_reports.py`, `test_tm_auto_reports.py`): отказ → каталог; `retry` той же модели → каталогов не прибавилось
  и строки «Записан репорт» нет; `retry` после `switch_model` → новый каталог с новой моделью в meta; следующий ход
  (turn_seq+1) с тем же отказом → каталог; два committed-хода с `gold_repeat` подряд → два каталога; `load()` сбрасывает
  память; `auto_reports=False` — ничего; каждая модель цепочки при переходе даёт свой каталог (`meta.model`).
- `trim_issues`/`dir_size`: `max_mb=0` → ничего; сумма ≤ лимита → ничего; над лимитом → удаляется самый старый, самый
  новый (только что записанный) не удаляется даже если один больше лимита; `manual` пропускается (Q5а), остальные
  старше него — удаляются; `tmp-*` не считаются и не трогаются; битый/отсутствующий `meta.json` → считать авто;
  `OSError` обрезки не меняет строку «Записан репорт»; `ReportsConfig.max_mb` ge=0, дефолт 200 из `app_defaults.toml`.
- Мок: `stop_detail` в шаге → `ChatResponse.stop_detail`; `stop_detail` без `stop` → `ValueError`; `ReplayAdapter`
  отдаёт `stop_detail` из журнала (t258-подобная запись).
- Пак: `load_pack(campaigns/dusk_academy)` без ошибок после правки; golden/фикстуры, если ссылаются на текст пака.
- mutmut (сверено grep-ом): `session:TurnFailed.__init__`, `session:MasterSession.run`; `turn:hard_refusal` (новая),
  `turn:TurnRunner.play_turn`; `app:GameApp.after_turn`, `app:GameApp.chain_turn` (новая), `app:GameApp.auto_report`,
  `app:GameApp.already_reported` (новая), `app:GameApp.write_report_lines`, `app:GameApp.load`; `writer:trim_issues` (новая),
  `writer:dir_size` (новая); `mock:check_step`, `mock:ScriptedAdapter.complete`; `app:ReportsConfig` (config). Перечислять
  точно, без глобов (урок ТМ).

## 5. Критерии готовности
Тесты зелёные, cov ≥ 97 %, smells ≤ 200, ruff/dead чисто, mutmut по списку без живых (кроме эквивалентных/текста);
`ai-dm --mock` код 0; офлайн-гейт §3 п.7; живых вызовов нет; ревью mama-kaban; `~/.config/ai-dm/checklists/checklist-to-live.md` (не коммитить).

## 6. Оценка
papa ~110 тыс. (fable); kaban 70–90; doeba 120–170; mama ~30. Итого ≈ 0,35–0,4 млн (роадмап 0,45).

## 7. Риски
- Переход постоянный (Q1а): после первого `PROHIBITED_CONTENT` мир dusk_academy едет на argon (дороже flash; ЖП1: «на
  argon дороже») до ручного `/model`. Это и есть «переход» из ROADMAP; возврат на flash не автоматический.
- Цепочка внутри Gemini: тот же фильтр может отказать и на argon/preview/lite → до 4 вызовов и 3 строк за ход; хуже
  старого (2 вызова) только в этом случае. Claude в цепочку не ставим (игроку не подходит, BACKLOG 62).
- `BLOCKLIST`/`SPII` в корпусе не встречались — в `HARD_REFUSALS` по смыслу (ненастраиваемые фильтры), Q2.
- T9 глушит повтор только при равных тегах/модели/причине: отказ с другим набором тегов (например, `limit-exceeded` на
  первом раунде) даст второй каталог — допустимо.
- `trim_issues` ходит по `issues/` при каждом репорте (≈ 200 каталогов × десятки файлов) — миллисекунды; при `max_mb`
  ниже текущего объёма (дракон/dusk) первый же репорт удалит старые каталоги пользователя — сказать в handoff/чек-листе
  (бэкап `saves/` перед ЖП).
- Правка пака — гипотеза (BACKLOG 62): фильтр может срабатывать на «школа + романтика» независимо от возраста; проверка
  только живым прогоном **и только в новом мире или после правки сейва** (Q4). Пресет `romantic` не трогаем.
- Старые `--replay-report` отказов расходятся на 2-м вызове (SOFTEN больше не шлётся) — ожидаемо, как B59/T60/ТВ/ТМ.
- `REFUSAL_HINT` после исчерпанной цепочки прежний («смягчите tone или смените модель») — строки перехода перед ним
  объясняют, что цепочка пройдена.

## 8. Вопросы проектировщику (рекомендации papa)
1. **Горизонт перехода на жёстком отказе:** (а) постоянный — как ручная смена (`set_narrator`, `models.json`), назад
   через `/model` или меню; (б) только на этот ход — вернуть прежнюю модель после хода: отказ по контексту, следующий ход
   той же сцены снова отказ → +1 вызов и +1 репорт каждый ход, плюс состояние «временный адаптер» в `TurnRunner`;
   (в) до границы сцены — ещё состояние и откат в `close_scene_if_needed`. Рек.: **(а)**.
2. **Что считать жёстким отказом:** (а) только `PROHIBITED_CONTENT` (ровно ROADMAP); (б) `PROHIBITED_CONTENT`, `BLOCKLIST`,
   `SPII` — все ненастраиваемые фильтры Gemini, у которых SOFTEN заведомо бесполезен; `SAFETY`/`RECITATION`/Claude —
   как раньше. Рек.: **(б)**.
3. **Лимит `issues/`:** (а) по объёму `[reports] max_mb = 200` (≈ 230 репортов, как `[journal] max_mb`); (б) по числу
   каталогов `max_reports = 100`. Рек.: **(а)** — объём репорта зависит от сейва и журнала, мера та же, что у журнала.
4. **Идущий мир `dusk_academy-d3de6c57`** (правка пака до него не доходит): (а) не трогать — мир живёт на цепочке, пак
   проверяется в новом мире; (б) одноразовая правка `slots/auto` (`world.lore.world_text`, `world.tone.notes`) по
   согласию пользователя, скрипт готовит kaban, запускает пользователь с бэкапом; (в) научить `merge_pack` обновлять
   `lore.world_text`/`tone.notes` из пака — задевает семантику «догружаем только новое» и `/tone` (тон принадлежит
   игроку) → не в мини-партии. Рек.: **(б)** — иначе эффект правки пака в блокирующем мире не измерить.
5. **Ручные репорты при обрезке:** (а) `manual` не удаляются (удаляются только авто); (б) удаляются наравне. Рек.: **(а)**.
6. **Текст «18+» в паке** (продуктовое, нужна формулировка проектировщика). Предложение papa как заготовка:
   `world.md` — «Академия Сумеречного Мыса — высшая школа магии: все студенты, включая первокурсников, — взрослые люди
   (18+); ночной народ дома Веларов — взрослые, нестареющие.»; «несколько юных представителей» → «несколько молодых
   на вид представителей»; `campaign.yaml tone.notes` — «Все персонажи — совершеннолетние (18+); романтика между
   взрослыми, медленная, без пошлости»; `locations.yaml:80` «Общежитие первокурсников» — оставить. Варианты: (а) только
   `world.md` + `tone.notes`; (б) ещё возраст у NPC в `npcs.yaml` (например, «Майя Ольсен, 19 лет»). Рек.: **(а)** —
   меньше правок; возраст NPC — если ЖП покажет, что отказ держится.

## 9. Решения проектировщика (2026-10-16)
Все по рекомендациям: Q1а, Q2б, Q3а, Q4б, Q5а, Q6а; текст 18+ — заготовка papa из Q6 дословно.
Дополнения по ходу партии: скрипт миграции сейва `scripts/migrate_dusk_18plus.py` — автономный (stdlib; игрок на другой
машине), принимает v9 и v10, коммитится в репо с инструкцией `docs/migrate-dusk-18plus.md`; «дети людей» → «молодые люди»
(пак и скрипт); строка в `tone.notes` сокращена до «Все персонажи — совершеннолетние (18+)» (без повтора про романтику).

## Правки по ревью: to-review (бывш. docs/decisions/to-review.md)

**Ревью: партия #21 ТО (цепочка отказов, T9-дедуп, лимит issues/, мок detail, 18+ dusk, скрипт миграции)**

✅ chain_turn/already_reported/trim_issues сделаны по плану; follow_provider убрал дублирование world/summarizer. cli передаёт `refusal_chain=not (args.mock or args.replay)`, как и `auto_reports`. Скрипт миграции использует только stdlib, делает бэкап перед записью и проверяет world_id. Новых ошибок ruff нет: все 16 E501 были до этой партии, в изменённых местах их нет.

⚠️ 1 (важно). Скрипт требует v10, а у игрока сейв v9: `scripts/migrate_dusk_18plus.py`, `SCHEMA_VERSION = 10`, `main()`. Живой сейв v9 лежит на другой машине, поэтому скрипт откажет и ничего не сделает. Правка затрагивает только `world.lore.world_text` и `world.tone.notes`. Предлагается: проверить, что в v9 эти поля лежат там же, и принимать `{9, 10}` (например `SCHEMA_VERSIONS = (9, 10)`). Нужен тест на v9-фикстуру в `tests/unit/devtools/test_migrate_dusk_18plus.py`. В `docs/migrate-dusk-18plus.md` написать, что v9 поддерживается и при следующей загрузке игра сама мигрирует его до v10.

⚠️ 2 (важно). Дефолт `GameApp(refusal_chain=False)` расходится с планом: TO-PLAN, п. 46 требует `refusal_chain=True`. В cli значение передаётся явно, но все остальные места, где создаётся GameApp (TUI, тестовые kit-ы), молча остаются без цепочки, и это не совпадает с `auto_reports=True`. Предлагается: поставить дефолт `True` по плану. Тесты старого поведения должны передавать `refusal_chain=False` явно (п. 124 плана уже так их и описывает). Если False оставлен намеренно, это вопрос к папе-кабану, а не тихое отступление.

⚠️ 3 (важно, контент). В `campaigns/dusk_academy/world.md`, строка 1, осталась фраза «вместе учатся дети людей». В абзаце, где только что объявлено 18+, она читается как «дети» и может дать модели повод для отказа или неверной трактовки. Предлагается: «потомки людей» или «люди». Ту же фразу проверить в `TEXT_REPLACEMENTS` скрипта, чтобы сейв и пакет кампании совпадали, и в `campaign.yaml`.

⚠️ 4. `chain_turn` в `src/ai_dm/game/app.py` берёт `old` после `auto_report(turn)` и до `set_narrator`, это корректно. Но если `set_narrator` вернул ошибку, цикл выходит с отказным turn, и тогда `after_turn` вызывает `auto_report(turn)` повторно. От двойного репорта спасает только `already_reported`, и только когда `capture.status == "aborted"`. Предлагается: проверить в `test_to_chain.py`, что при ошибке фабрики записывается ровно один репорт.

⚠️ 5 (мелочь). `trim_issues` вызывается после каждого репорта, и ошибка подавляется через `contextlib.suppress(OSError)`. Если это делается внутри `write_report_lines`, то и ручной `/report` тоже обрезает issues/. Это соответствует плану, но стоит упомянуть в `docs/handoff`.

Smells и полный pytest на момент записи отчёта ещё прогонялись в фоне. Кабану перед коммитом подтвердить: smells 200/200 и тесты зелёные.

**Вердикт:** нужны правки (п. 1–3 обязательно, 4 тестом).

### Аудит (кабан-свекровь, 2026-10-16)

**Что проверено:** незакоммиченное поверх 4625538: `git diff` по 14 файлам (src, campaigns/dusk_academy, ARCHITECTURE, BACKLOG, kit-ы) и новые файлы партии: `scripts/migrate_dusk_18plus.py`, `docs/migrate-dusk-18plus.md`, `tests/unit/**/test_to_*.py`, `test_cli_refusal_chain.py`, `test_migrate_dusk_18plus.py`. Неотслеживаемые `campaigns/test/`, `docs/import-examples/`, `.dashboard.json` и старые чек-листы датированы 15.10 01:54, то есть появились до партии; их не оцениваю.

**Источники истины:** docs/plan-to.md §1–§8 и §9 (все ответы по рекомендациям: Q1а, Q2б, Q3а, Q4б, Q5а, Q6а; текст 18+ дословно из заготовки papa в Q6). Дополнения проектировщика, переданные оркестратором: скрипт автономный, принимает v9 и v10, «дети людей» → «молодые люди».

| Находка | Где | Откуда взялось | Вердикт |
|---|---|---|---|
| `TurnFailed.detail`, `HARD_REFUSALS` (3 кода), `hard_refusal`, без SOFTEN-повтора | session.py, turn.py | §1 п.1–2, Q2б | оставить |
| `chain_turn`, переход постоянный через `set_narrator`, `refusal_chain=True` по умолчанию, cli даёт False при mock/replay | app.py, cli.py | §1 п.3, Q1а. П.2 ревью закрыт: дефолт теперь True | оставить |
| Формат строки «Модель {старая} отказала ({detail}) — переключаюсь на {новая}.» (имя модели без провайдера) | app.py `chain_turn` | §1 п.3, текст дословно из плана, который проектировщик утвердил. Префикс провайдера отрезан, в плане это не оговорено, но и решением не считаю | оставить |
| `already_reported`: ключ (turn_seq, теги, причина, модель), только для aborted, сброс в `load()` | app.py | §1 п.4 | оставить |
| `[reports] max_mb = 200`, `ge=0`, 0 означает без лимита | config, toml | Q3а (200 предложил papa, проектировщик принял) | оставить |
| `MB = 1_000_000` в writer.py | writer.py | §1 п.5: «константа как в journal». Совпадение с journal не сверял, расхождение было бы мелочью | оставить |
| Обрезка вызывается из `write_report_lines`, поэтому ручной `/report` тоже запускает обрезку | app.py | §1 п.5 прямо называет `write_report_lines`. Сами manual-каталоги не удаляются (Q5а) | оставить; написать в handoff и чек-листе, как и предлагает ревью п.5 |
| `is_manual` как отдельная функция; битый meta считается авто-репортом | writer.py | §4 («битый meta → авто») | оставить |
| `follow_provider` | app.py | §1 п.9 (компенсация smells) | оставить |
| `stop_detail` в моке, `check_step` | mock.py | §1 п.6 | оставить |
| Текст 18+ в world.md и tone.notes, «старая школа» → «высшая школа», «юных» → «молодых на вид» | campaigns/dusk_academy | Q6а, заготовка papa дословно | оставить |
| «дети людей» → «молодые люди» (пак и скрипт) | world.md, скрипт | дополнение проектировщика. П.3 ревью закрыт | оставить |
| Старая строка tone.notes «Романтика медленная…» осталась, рядом добавлена новая с тем же смыслом | campaign.yaml | Q6а говорит «добавить строку» и не говорит, что старую убрать. Дублирование безвредно | к пользователю (по желанию: убрать старую строку) |
| Скрипт: принимает только мир `dusk_academy-d3de6c57`, правит один слот (по умолчанию auto), бэкап в `backup-18plus-<ts>` рядом со слотами, идемпотентен по маркеру «(18+)», отказывает, если не нашёл ожидаемый фрагмент | scripts/ | Q4б и дополнения (автономный, v9/v10). Место бэкапа, маркер идемпотентности и строгий отказ выбрал агент. Решения разумные и безопасные | оставить; место бэкапа указать игроку в docs/migrate-dusk-18plus.md (там уже есть) |
| Скрипт лежит в новом каталоге `scripts/` в корне репо | scripts/ | в плане место не задано, решение агента | к пользователю: коммитить ли `scripts/` (одноразовый скрипт) или держать вне репо |
| ROADMAP #21 не обновлён, handoff не обновлён | docs/ | §2 плана, память «ROADMAP перед коммитом» | до коммита обновить |
| `locations.yaml` и `npcs.yaml` не тронуты | — | Q6а | так и надо |

Лишних фич, абстракций «на будущее», новых зависимостей или изменений вне области задачи в коде нет. Список «Не делаем» (§1 п.8) соблюдён: тег `refusal_fallback` не переименован, `network` не переключает, OpenAI/Claude в цепочку не добавлены, hero/import не тронуты, остатки `tmp-*` не удаляются.

**Правила.**
- `saves/` (в .gitignore): `find saves -newer docs/plan-to.md` ничего не нашёл, то есть после утверждения плана в saves/ ничего не менялось. Нарушения не видно.
- Правка файлов через bash/python вместо Edit/Write (глобальное правило): по git этого не доказать. Косвенный признак: у `scripts/migrate_dusk_18plus.py` и `docs/migrate-dusk-18plus.md` одинаковое mtime 14:57:31 с точностью до секунды, похоже на запись одной пакетной командой. Фиксирую как вероятное нарушение. Подтвердить можно только по логам сессий kaban/doeba.

**Решения за пользователя:** серьёзных нет. Мелкие, сделанные агентами без явного указания: каталог `scripts/` в репо; место и формат бэкапа скрипта; маркер идемпотентности «(18+)»; в строке перехода показывается имя модели без провайдера. В том, что оркестратор назвал (формат строки, лимит 200 МБ, обрезка при ручном /report), решений за проектировщика нет: всё это записано в утверждённом плане (§1 п.3, п.5; Q3а, Q5а).

**Итог:** код чистый и соответствует плану. До коммита: обновить ROADMAP и handoff, предупредить в handoff/чек-листе, что первый же репорт может удалить старые авто-каталоги (ручной /report тоже). К пользователю: коммитить ли `scripts/`, оставлять ли дубль строки про романтику в tone.notes.

## Итог: Из HANDOFF.md до 22д (бывш. docs/HANDOFF.md)

- **#21 ТО ✅ закоммичена 2026-10-16 (сейв v10 без изменений):** план docs/plan-to.md (papa, fable; §9 — все по рекомендациям + дополнения). Жёсткий отказ Gemini (`PROHIBITED_CONTENT`/`BLOCKLIST`/`SPII`, `TurnFailed.detail`, `hard_refusal`) — без SOFTEN; `GameApp.chain_turn` (`refusal_chain=True` по умолчанию, cli False при --mock/--replay) — постоянный переход на следующую модель цепочки со строкой игроку, исчерпана → меню; T9 `already_reported` — один авто-репорт на попытку и модель; `[reports] max_mb = 200`, `trim_issues` (старые авто-каталоги, `manual` и `tmp-*` не трогает; срабатывает и на ручной `/report` — **первый же репорт может удалить старые каталоги, перед ЖП бэкап saves/**). Пак dusk_academy: 18+ в world.md, «дети людей» → «молодые люди», `tone.notes` «Все персонажи — совершеннолетние (18+)». Идущий мир игрока (на другой машине, сейв v9) — автономный скрипт `scripts/migrate_dusk_18plus.py` (stdlib, v9/v10, бэкап, идемпотентен) + инструкция docs/migrate-dusk-18plus.md — раздать игроку. `follow_provider` вынесен из `set_narrator` (smells). Ревью и аудит — docs/plan-to.md. Тесты ≈16990 зелёные (флейк `test_second_ctrl_c_calls_hard_exit_with_130_and_does_not_save` под нагрузкой полного прогона — отдельно 3/3), cov 97,60 %, smells 200/200; mutmut: в строках партии выживших нет после добивки (6 эквивалентных), 139 в старых строках не трогали. Агенты (kaban, doeba, papa) снова правили файлы bash/python-скриптами — вопрос Edit у агентов по-прежнему открыт. Расход: papa ~133 тыс. (fable), kaban ~92 тыс., doeba ~122 тыс.+, mama ~21 тыс., svekrov ~47 тыс., mutmut (sonnet) ~88 тыс. Чек-лист ~/.config/ai-dm/checklists/checklist-to-live.md (не коммитить). **Дальше:** ЖП по чек-листам ТМ и ТО (пользователь), раздать игроку скрипт миграции; #22 ТС.
