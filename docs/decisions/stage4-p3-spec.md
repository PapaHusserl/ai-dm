# Этап 4, P3: единый сборщик контекста с бюджетом Д1 и вытеснением ТЗ 11 — уточнённая спецификация (папа-кабан, 2026-10-04)

Источник: STAGE4-PLAN A6, P3, «Решение проектировщика по G1» (заменяет «запрос уходит как есть»). Код сверен на c3411c1.
K — kaban (src/**, docs/**), T — kaban-doeba (tests/**). TDD: T первым, параллельно с K, затем ревью мамы-кабана.

## 1. Расхождения плана с кодом
| # | План | Код сейчас | Решение |
|---|---|---|---|
| 1 | `budget()`, `estimate_tokens`, `plan` в новом `master/context.py` | `master/memory.py`: `context_limit` (80% окна, без потолка), `recent_window`, `trim_turns`; цикл `estimate` в `PromptBuilder.build` | `memory.py` удалить, все три функции заменить `context.py` (`recent_window` переносится как есть) |
| 2 | Оценка детерминированная `ceil(len/2.5)` | `build` зовёт `adapter.count_tokens` на полном запросе (живой API в live, мок/replay — другое число) + эвристика `len//3`; `default_count_tokens` = `len(json)//3+1` | `count_tokens` из `PromptBuilder` убрать совсем (параметр конструктора, `default_count_tokens`, `turn.py:set_adapter`), докстринг `MasterSession` переписать |
| 3 | `meta.context.api_tokens` — калибровка живым `count_tokens` | — | В P3 НЕ делать отдельный вызов: калибровка — по `usage` той же записи журнала (input+cache_read+cache_write — реальные токены запроса). Лишний сетевой вызов на ход не нужен (см. вопрос В3) |
| 4 | `meta.context` в записи журнала | `Journal.record_call` не имеет поля `meta`; replay сравнивает только `request.fingerprint` | `record_call(..., meta=None)` → ключ `"meta": meta or {}`; replay не меняется |
| 5 | Авто-репорт `context_overflow` (ТЗ 9) | Модуля `reports` нет (этап 6). «Авто-репорт» сейчас = `report_tags` в записи журнала + `TurnResult.report_tags` (как `invalid-death`). `MasterResult.report_tags` в `TurnResult` НЕ попадает (в turn.py теги идут только из `executor`) | Тег `context_overflow` пишется в `report_tags` записи журнала narrator и пробрасывается в `TurnResult.report_tags` (см. шаг 6) |
| 6 | `/model` без окна → отказ (`game/commands.py`) | Уже есть: `game/app.py:check_model` отказывает при отсутствии `prices`/`context_windows`; валидатор `AppConfig.check_models_known` — для ролей/профилей | Код не трогать, только тест |
| 7 | `relevant_npcs` → `dict[id, set[reason]]` | `relevant_npcs(bundle) -> list[str]` используют `prompt.py` и `master/world.py` | Новая `npc_reasons(bundle) -> dict[str, set[str]]`; `relevant_npcs` остаётся (обёртка, тот же результат, БЕЗ причины `nearby`) — вход роли world и её replay не меняются |
| 8 | `recent_turns = 8` | `recent_turns = 4`, тест `test_default_config_window_is_4` | Поднять до 8; тест переписать сознательно |
| 9 | Блок памяти строится после вытеснения | `memory_block(ctx)` берёт все выжимки сцен текущей главы, без плана | `memory_block(ctx, plan)` — сцены из `plan.scene_summaries` |
| 10 | Gemini-кэш памяти (P1+ E1) | `GeminiAdapter.cache_key` включает весь `system` (с памятью); новый ключ той же (модель, tools, роль) удаляет старый кэш | Вытеснение выжимки сцены = новый явный кэш Gemini (~$0.01). Принимается (ступень 2 редка); см. риск Р2 |
| 11 | Инструменты качества | — | `make quality`: ruff (E,F,W,I,B,SIM,UP; 100 симв.), покрытие `fail_under = 94`, Qlty smells ≤ 210 (ratchet — не расти), vulture (min_conf 60; allowlist — только с решения пользователя), `make mutate MOD=ai_dm.master.context` |

## 2. Контракты (`src/ai_dm/master/context.py`, новый)
Импорты: только `ai_dm.llm.types`, `ai_dm.state.*`, `ai_dm.master.relevance` (сторож: не `llm`-адаптеры, не `game`, не `ui`).
```python
STAGES = ("turns", "scenes", "npcs", "locations")      # порядок вытеснения

class ContextPlan(BaseModel):                            # frozen
    budget: int            # действующий потолок хода (cap или поднятый по G1)
    cap: int               # min(80% окна, master.context_cap)
    estimate: int          # оценка итогового запроса
    turns: list[TurnRecord]
    scene_summaries: list[SceneSummary]
    npc_ids: list[str]     # known_npcs
    location_ids: list[str]# locations (текущая — всегда первая)
    dropped: list[tuple[str, str]]   # (ступень, id) в порядке вытеснения; id хода = str(turn.turn_seq), сцены = scene_id
    raised: bool           # G1: потолок поднят до 80% окна
    overflow: bool         # = raised (неустранимое > cap); оставлено ради теста P4 «overflow ни разу»
    def meta(self) -> dict  # {"budget","cap","estimate","dropped":[[s,id],...],"raised","overflow"}

def window_budget(app_cfg, model) -> int     # context_windows[model] * 80 // 100
def budget(app_cfg, model) -> int            # min(window_budget, master.context_cap)  (Д1)
def estimate_tokens(text: str, chars_per_token: float) -> int   # ceil(len(text)/cpt), чисто
def request_tokens(req: ChatRequest, cpt) -> int  # estimate_tokens(req.model_dump_json()) — весь запрос
def recent_window(memory, n) -> list[TurnRecord]  # перенос из memory.py
def plan(candidates: Candidates, render: Callable[[Candidates], ChatRequest], *, cap, window80, cpt) -> ContextPlan
```
`Candidates` — что можно урезать (списки в порядке «первым выкидывать — первым»), готовит `PromptBuilder`:
`turns` (окно `recent_turns`), `floor` (`master.recent_turns_floor`), `scenes` (выжимки текущей главы), `npcs` (ранжированные
вытесняемые NPC), `locations` (вытесняемые соседние локации, дальние первыми). Неустранимое `plan` не знает — оно в `render`.
В `Candidates` есть ещё `fixed_npcs`/`fixed_locations` (неустранимое, по умолчанию пустые): `ContextPlan.npc_ids`/`location_ids` = fixed + оставшееся вытесняемое.
Алгоритм: оценивать `request_tokens(render(c))` целиком (не разницей, как сейчас) — дорого, но детерминированно; для скорости
допустимо снимать по одному элементу и пересчитывать (≤ 8+N+M+K рендеров; N,M,K — десятки). Ступени строго по порядку; ступень
N+1 начинается только когда у N кандидатов не осталось (ходы — до `floor`).
**G1:** если после всех ступеней `estimate > cap` → `budget = window80`, `raised = overflow = True`; вытесненное не возвращается
(запрос = неустранимое + floor-ходы). Если и `estimate > window80` — запрос всё равно уходит (см. вопрос В1).
Бюджет считается только на первом `build` хода; раунды инструментов дописывают сообщения без пересчёта (как сейчас).

Ранги NPC (`relevance.npc_reasons`, причины: `with_hero`, `here`, `active`, `key`, `said`, `nearby`):
- неустранимы: `with_hero`, `here`, `active` (и все `scene_npcs` — отдельный список, не трогается);
- вытесняемы, по порядку: только `said` → `key` (без `active`) → `nearby` (только). У NPC с несколькими причинами — самая
  защищённая. Внутри ранга — по id возрастанию. `nearby` = живой именованный NPC, чья `location_id` в `nearby_locations`
  (связь в любую сторону), кроме текущей. Мёртвый/безымянный — не релевантен.
Локации: текущая неустранима; соседние — по `distance_m` убыванию, при равенстве по id.

## 3. План работ K (src/docs)
1. `config/app.py` `MasterConfig`: `context_cap: int = Field(gt=0)`, `chars_per_token: float = Field(gt=0)`,
   `recent_turns_floor: int = Field(ge=0)`; валидатор `recent_turns_floor <= recent_turns`. `app_defaults.toml [master]`:
   `recent_turns = 8`, `context_cap = 30000`, `chars_per_token = 2.5`, `recent_turns_floor = 1`.
2. `master/context.py` — §2. `master/memory.py` удалить.
3. `master/relevance.py`: `npc_reasons(bundle, nearby_ids=())`, `relevant_npcs` = обёртка без `nearby` (вход world неизменен).
   Вынести `nearby_locations` из `PromptBuilder` в `relevance` (нужен и для причин) — чистая функция, `prompt.py` зовёт её.
4. `master/prompt.py`: конструктор без `count_tokens`; `build` → собирает `Candidates`, `render`, зовёт `context.plan`,
   кладёт `self.last_plan`; `state_data(ctx, user_input, plan)` и `memory_block(ctx, plan)` берут ходы/сцены/NPC/локации из
   плана. Байты `system[0..1]` не зависят от плана. Функции держать короткими (Qlty smells ≤ 210).
5. `llm/journal.py`: `record_call(..., meta=None)` → `"meta"`. `master/session.py`: в `call` передавать
   `meta={"context": plan.meta()}` для role narrator (берётся из `builder.last_plan`, у world/summarizer — `None` → `{}`);
   при `plan.overflow` — `report_tags=["context_overflow"]` в записи и `MasterResult.report_tags.append("context_overflow")`
   (один раз за `run`). Докстринг `MasterSession` (count_tokens) обновить.
6. `game/turn.py`: `set_adapter` без `count_tokens`; после каждого `session.run(...)` narrator переносить
   `master.report_tags` в `result.report_tags` (без дублей). Проверить три места вызова (стр. ~308, 355, 383).
7. vulture: после удаления `count_tokens` из builder методы `count_tokens` адаптеров останутся без вызова в src — проверить
   `make dead`; allowlist без решения пользователя не трогать (вопрос В2).
8. Docs: STAGE4-PLAN P3 — ссылка на эту спецификацию; ARCHITECTURE (master.context вместо master.memory); HANDOFF после приёмки.
9. Replay-фикстуры этапов 2–3 (`tests/fixtures/scripts`, golden), если сломаются от `recent_turns=8` / новой оценки —
   перезапись сознательно отдельным коммитом (делает T, K сообщает).

## 4. Тесты T (tests/**)
Новый `tests/unit/master/test_master_context.py`; `test_master_memory.py` удалить/перенести; дополнить `test_master_relevance.py`,
`test_master_prompt.py`, `test_master_session_log.py`, `tests/unit/config/*`, `tests/unit/test_architecture.py`, `tests/unit/game/*`.
- config: дефолты 8/30000/2.5/1; `context_cap=0`, `chars_per_token=0`, `floor<0`, `floor>recent_turns` → ошибка.
- `budget`: окно 1M → 30 000; окно 20 000 → 16 000; cap 10 000 при окне 200k → 10 000.
- `estimate_tokens`: ceil (5 симв./2.5 → 2; 6 → 3; "" → 0); детерминирован; шпион `adapter.count_tokens` — 0 вызовов за ход.
- ступень 1: лишнее на 3 хода → `dropped` = 3 старейших `("turns", seq)`, сцены целы; floor=1 — последний ход остаётся; floor=0 — можно все.
- ступень 2 только после исчерпания ходов до floor; старейшие сцены первыми; главы и `game_summary` в `system[2]` на месте;
  сцены других глав в блок не попадают вовсе (не считаются вытесненными).
- ступень 3: `said` раньше `key`, `key` раньше `nearby`; `with_hero`/`here`/`active` и `scene_npcs` не выкидываются; NPC
  с `key`+`said` идёт как `key`; затем локации: дальние первыми, текущая всегда.
- `dropped` — точный порядок; ступени неубывающие; ни одна ступень N+1 при остатке у N.
- итог: `estimate ≤ budget` при любом наполнении (параметризовать размеры) и `estimate == request_tokens(итоговый req)`.
- G1: неустранимое > cap → `raised=overflow=True`, `budget == window80`, все вытесняемые выкинуты, запрос отправлен;
  запись журнала: `meta.context.raised`, `report_tags == ["context_overflow"]`; `TurnResult.report_tags` содержит тег ровно раз
  даже при нескольких раундах инструментов; без переполнения — тега нет, `meta.context.raised=False`.
- relevance: NPC в соседней локации (связь в любую сторону) → `nearby`; мёртвый — нет; `relevant_npcs` (вход world) не изменился.
- `/model` с 1M на тестовую модель окна 10 000 → следующий `build` с бюджетом 8 000, вытеснение есть; модель без окна → отказ `check_model`.
- идемпотентность: один бандл → `build` дважды → равные байты; `system[0]`, `system[1]` равны при разной памяти/вытеснении.
- `meta.context` только у narrator; replay прогона с вытеснением → тот же запрос, без `ReplayDivergence`.
- сторож: `master.context` не импортирует `ai_dm.llm.*_adapter`, `game`, `ui`; `master.memory` отсутствует.
- мутации: `make mutate MOD=ai_dm.master.context` (и `ai_dm.master.relevance`) — выживших добить или обосновать.

## 5. Риски
Р1. Оценка `len(JSON)/2.5` по `model_dump_json` экранирует кириллицу? Pydantic пишет UTF-8 без `\u` — проверить тестом; при
    `\uXXXX` оценка завышена в ~6 раз и вытеснение будет агрессивным.
Р2. Вытеснение выжимки сцены меняет `system[2]` → новый явный кэш Gemini и запись 5m у Anthropic. Если ступень 2 «мигает»
    между ходами (ход вырос/сократился) — кэш пересоздаётся каждый ход. Ограничение: ступень 2 срабатывает только после ходов
    до floor; на потолке 30k по замеру P0 (≈20k без ходов) — практически не сработает в Драконе.
Р3. Пересчёт рендером целиком — O(кандидатов) сериализаций запроса (~50–100 × ~80 КБ) на ход; приемлемо (<100 мс), иначе — разница.
Р4. `recent_turns` 4 → 8: +2–3k токенов входа на ход (A7) и перезапись replay-фикстур.
Р5. Qlty smells ratchet (≤ 210): `build`/`state_data` уже длинные — новый код дробить на функции, иначе `make smells` красный.
Р6. Покрытие 94% глобально: удаление `memory.py` и его тестов не должно опустить порог — тесты context.py обязательны до слияния.

## 6. Открытые вопросы (только проектировщик)
В1. G1, крайний случай: неустранимое > 80% окна (реально только у малых окон, напр. Haiku 200k → 160k — маловероятно). Отправлять
    как есть с тем же тегом (рек.) или ошибка хода → меню 2.2?
В2. После P3 `count_tokens` адаптеров в src никем не вызывается (vulture может пометить). Оставить в интерфейсе адаптера под
    будущую калибровку (внести в vulture_allowlist — нужно ваше «да») или удалить из адаптеров и протокола (рек.: удалить; калибровка — по usage журнала)?
В3. Калибровка `meta.context.api_tokens` (чек-лист E): брать из `usage` ответа (рек., бесплатно) вместо живого `count_tokens`
    (+1 сетевой вызов на ход)?
В4. При поднятом потолке (G1) вытесняемое всё равно выкидывается (рек.: запрос = неустранимое + floor-ходы, растёт только
    неизбежное) — или наоборот заполнять до 80% окна (дороже, но больше контекста)?

## Решения проектировщика по вопросам В1–В4 (2026-10-04)
- В1: неустранимая часть > 80% окна → запрос уходит как есть, тег `context_overflow`, `overflow=True`.
- В2: `count_tokens` удалить из адаптеров и интерфейса (vulture_allowlist не трогать).
- В3: калибровка — из `usage` ответа (без живого `count_tokens`), в `meta.context`.
- В4: при поднятом потолке вытесненное не возвращается.
