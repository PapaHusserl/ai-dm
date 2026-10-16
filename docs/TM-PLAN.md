# План мини-партии #20 «ТМ Повторы механики» (T6 + Ф3; BACKLOG 64)

Автор: papa-kaban, 2026-10-16. Статус: **утверждён 2026-10-16** («окей, кабаним»); Q1–Q4 — (а), (б) 12h, (а), (а), как рекомендовал papa. Груминга нет (техдолг по правилу фикса, прецедент TV-PLAN).
Smells 200/200 — нулевой баланс. Сейв: **v10** при Q1а (миграция чистая `dict -> dict`), иначе v9 без изменений.
Источники: ROADMAP #20; BACKLOG 64 T6; tech-debt-2026-10-14.md T6; zhp1-findings.md Ф3; handoff (хвост), 19f-review.md;
прецеденты: K0-PLAN (фикстура сейва на main до правок), B0-PLAN/test_migration_v8 (чистая миграция), TV-PLAN (теги →
авто-репорт, замена правил → старые реплеи расходятся).

## 0. Офлайн-проверка гипотез (сделано; saves/ только чтение, сети нет)
**T6 — подтверждён** (`saves/drunk_dragon-00000001/journal/calls-004.jsonl`, flash-lite, нумерация `turn_seq` журнала):
- 128 (`run-20261011T182834-2d0820-1`, «Обыскать тела»): `gold loot_individual` → accepted, «Добыча: +20 зм», money 16800.
- 129 (`run-20261014T183915-2c23c8-1`, «Перевязать раны мазью»): `use_item bran_mountain_salve` → **rejected** «нечего
  применить» (сигнал «опиши по факту»); `gold explicit 2000 gain` → accepted (18800); текст описывает и мазь, и «кошель с
  двадцатью коронами» повторно.
- 130 (`-2`, «повернуть ключ»): снова `use_item` (rejected) + `gold 2000` (20800); текст «кошель перекочевывает» + мазь.
- 131 (`-3`, «да»): `gold 2000` (22800); текст про ключ, золото не упомянуто вовсе.
- В `recent_turns` модель видела: запись 129 `requests: ["gold"]` (rejected `use_item` не записан) и рассказ про кошель/мазь.
  На 130 повторён и `use_item` → копирует не только `requests`, но и рассказ. Код: `game/turn.py:402 recording` пишет в
  `requests` только accepted/clamped имена без итога; `TurnRecord` (`state/scene.py:36`) — `requests`, `rolls` строками;
  `protocol/handlers/resources.py:573 gold` — explicit gain без защиты от повтора (кап `gold_explicit_max_cp_by_level`).
- Побочно: `bran_mountain_salve` — предмет без эффекта применения (кастомный, пак дракона) — не наша задача, движок
  отказывает верно; проблема в том, что модель игнорирует «опиши по факту» (правило стр. 64 есть). В ТМ: отказ попадает в
  `outcomes` следующего хода («use_item: отклонено (нечего применить)»), чтобы хотя бы не повторялся.

**Ф3 — подтверждён, та же причина** (`saves/vale-cd40a140/journal/calls-001.jsonl`, flash-lite):
- 18 (`run-…-bdcaa3-20`, «отдохнуть»): `rest long` → accepted, hp 3→11, часы 42→28842, концентрация Метки снята. Норма.
- 19 (`-21`, ввод «Снова спуститься в подвал…» — вариант меню): `rest long` + `offer_choices` → accepted (hp уже 11/11,
  часы →57642), текст «Ты просыпаешься…» — повтор пробуждения из 18 (в репорте это «Ход 20»). Ввод игрока проигнорирован.
- 20 (`-22`, «Спуститься к Гарту, позавтракать»): третий `rest long` (часы →86442 = 00:00 следующих суток), текст про
  завтрак. В `recent_turns` обеих записей — `requests: ["rest", "offer_choices"]`.
- Код: `rules/rests.py:59 long_rest` отказывает только мёртвому и при 0 HP; при полных ресурсах принимает, +8 ч каждый раз.
  Ни отметки последнего отдыха, ни кулдауна нет.
- Итог: «повторы предыдущих сообщений» = повтор механики (`rest`) + повтор текста прошлого хода. Отдельная причина у
  текста не найдена: приписок/ошибок в этих ходах нет, `choices_retry` сработал штатно.

**Частота**: копирование наблюдается только на flash-lite (3.8-flash/sonnet — 0 случаев в разобранных журналах);
на flash-lite — 2 эпизода из ~45 explore-ходов (дракон 129–131, vale 19–20), оба — хвост «большой механики» (добыча, отдых).

## 1. Решения (архитектура)
1. **Защита `gold explicit gain` от повтора** (`handlers/resources.py`). Новая `gold_repeated(ctx, amount_cp) -> int | None`:
   смотрит `ctx.bundle.memory.recent_turns[-N:]` (N = `cfg.limits.gold_repeat_turns`, по умолчанию 3; 0 = выкл.) и
   возвращает `turn_seq` записи с `money_delta_cp == amount_cp` (> 0). В `gold` explicit gain: `amount = min(request.amount_cp,
   cap)`; если `gold_repeated(ctx, amount)` → `rejected("повтор начисления", "Сумма <X> уже начислена на ходу <N>; кошель
   героя <money>. Повторно не начисляй и не описывай эту находку снова.", report_tag="gold_repeat")`. Rejected (не Invalid):
   Invalid жжёт бюджет невалидных (2/ход → `TurnFailed`). `lose`, `loot_individual`, `hoard` — не трогаем (у них свои
   «один раз»: `last_combat.looted`, `hoard:<lair>`). Чтение `bundle.memory` из хендлера — новое; слой protocol → state,
   сторожа архитектуры не задевает. Повтор внутри одного хода (два `gold` в одном ответе) не ловим — в корпусе нет; риск в §7.
2. **Защита длинного отдыха от повтора** (кулдаун, Q2). `HeroState.long_rest_end_s: int | None = None` (новое поле, v10);
   `rests.long_rest` после `clock.advance(...)` пишет `hero.long_rest_end_s = clock.now_s`. В хендлере `rest` перед `try` —
   новая `rest_redundant(ctx, request) -> Decision | None`: `kind == "long"` и `hero.long_rest_end_s is not None` и
   `now_s < long_rest_end_s + cooldown` (`cfg.limits.long_rest_cooldown`, строка `Duration` как `servant_cooldown`,
   по умолчанию по Q2) → `rejected("отдых уже был", "Длинный отдых кончился в <clock_text>; следующий — не раньше
   <clock_text>. Отдых не повторяй; сон или ожидание дай через advance_time.", report_tag="rest_repeat")`. `prepared_swap`/
   `prey_swap` при отказе не применяются. Короткий отдых не трогаем. Отвергнут вариант «отказ при полных HP/ресурсах»
   (без состояния) — ложно режет обычную ночёвку при полном HP.
3. **Итог инструментов в памяти хода.** `TurnRecord.outcomes: list[str] = []` (v10) и `TurnRecord.money_delta_cp: int = 0`.
   `TurnResult.outcomes = []`; `TurnRunner.recording`: accepted/clamped → `outcomes += outcome.log`, rejected →
   `outcomes.append(f"{request.type}: отклонено ({outcome.reason})")` (в `lines`/UI не попадает); Invalid — нет.
   `TurnRunner.commit`: `outcomes=list(result.outcomes)`, `money_delta_cp=hero_of(work).money_cp - hero_of(self.bundle).money_cp`
   (ловит и trade/hoard). `combat_fold.fold_fight` — запись свёртки с `outcomes=[]`, `money_delta_cp` = сумма свёрнутых.
4. **Промпт.** `PromptBuilder.state_data` (`master/prompt.py:446`): вместо `t.model_dump(mode="json")` — функция модуля
   `turn_data(turn) -> dict`: `{"turn_seq", "at_s", "player_input", "narration", "outcomes"}` — без `requests`, `rolls`,
   `scene_id`. Меняет fingerprint всех запросов → старые `--replay-report` расходятся (прецедент B59/T60/ТВ).
5. **Правила.** `narrator_rules.md`, блок «В состоянии» (стр. 44) — одно предложение: «`recent_turns` — последние сыгранные
   ходы: `player_input`, `narration`, `outcomes` (что движок уже исполнил или отклонил). Это прошлое: их вызовы не повторяй —
   золото, отдых, предметы уже учтены; текст не пересказывай; отвечай только на текущий `player_input`.» (~250 симв.).
6. **Конфиг.** `[limits]` в `defaults.toml`: `gold_repeat_turns = 3`, `long_rest_cooldown` (по Q2); `LimitsConfig` — поля +
   валидатор `Duration.parse` (как `check_cooldown`).
7. **Сейв v10** (Q1а). `CURRENT_SCHEMA_VERSION = 10`; `m0010_v9_to_v10.migrate_v9_to_v10(data, context=None)` — чистая
   `dict -> dict`: `setdefault("outcomes", [])`, `setdefault("money_delta_cp", 0)` по `memory.recent_turns`,
   `setdefault("long_rest_end_s", None)` по `heroes`; `MIGRATIONS[9]`; `tests/schema/save_v10.schema.json`; фикстура
   `tests/fixtures/saves/v9` — сгенерировать на main до правок из `v8` (прецедент K0-PLAN шаг 0). ARCHITECTURE: «E7. Сейв v10».
   При Q1б (v9): п.1 — окно по `"gold" in t.requests` (грубее), п.2 — `world.flags["long_rest_end_s"]`, п.3–4 — не делаем.
8. **Теги → авто-репорт.** `gold_repeat`, `rest_repeat` через `Decision.report_tag` → `result.report_tags` → `GameApp.auto_report`.
9. **Smells (нулевой баланс).** `gold` → диспетчер, ветка explicit в `gold_explicit`; `rest_redundant` отдельно; `turn_data`
   снимает вложенность с `state_data`. Компенсация при 201+: из `rest` вынести `short_rest_dice(ctx, request) -> (int, bool)`.
10. **Не делаем:** `reports/markdown.py recent_lines`; эвристику повтора текста; перестановку `player_input` (Q3); правку
    сейвов dragon/vale.

## 2. Затронутые файлы
`src/ai_dm/state/scene.py`; `src/ai_dm/state/hero.py`; `src/ai_dm/rules/rests.py`; `src/ai_dm/protocol/handlers/resources.py`;
`src/ai_dm/game/turn.py`; `src/ai_dm/game/combat_fold.py`; `src/ai_dm/master/prompt.py`;
`src/ai_dm/master/prompts/narrator_rules.md:44`; `src/ai_dm/config/settings.py`, `src/ai_dm/config/defaults.toml`;
`src/ai_dm/persistence/migrations/__init__.py`, новый `m0010_v9_to_v10.py`; `tests/schema/save_v10.schema.json`,
`tests/fixtures/saves/v9/` (doeba, на main). Без изменений: `ui/session.py offer_is_stale`, `master/summarizer.py`,
`master/relevance.py`, `reports/markdown.py`. Документы: ARCHITECTURE.md (C3, E7, абзац защит); шапки `master_kit.py`,
`game_kit.py`; BACKLOG 64, ROADMAP #20, handoff; `docs/checklist-tm-live.md` (не коммитить).

## 3. Шаги kaban
0. Дождаться фикстуры `tests/fixtures/saves/v9` от doeba.
1. Поля моделей; `CURRENT_SCHEMA_VERSION = 10`, `m0010`, `MIGRATIONS[9]`; перегенерировать `save_v10.schema.json`.
2. `LimitsConfig` + `defaults.toml`.
3. `resources.py`: `gold_explicit`, `gold_repeated`, `rest_redundant`; `rests.long_rest` пишет `long_rest_end_s`.
4. `turn.py`: `TurnResult.outcomes`, `recording`, `commit`; `combat_fold.fold_fight`.
5. `prompt.py`: `turn_data`, `state_data`; `narrator_rules.md:44`; `make smells` после каждого файла.
6. Офлайн-гейт (без сети): `ai-dm --mock` код 0; скрипт в scratchpad — по копии `drunk_dragon-00000001/slots/auto`:
   второй и третий explicit 2000 → rejected `gold_repeat`, money не растёт; по копии vale: `rest long` → accepted,
   повторный через 8 ч → rejected `rest_repeat`, часы на месте, после кулдауна → accepted.
7. Доки (§2); `docs/checklist-tm-live.md` для ЖП на flash-lite (20 ходов): бой → «обыскать тела» → два хода (нет повтора
   денег); длинный отдых → accepted; следующий ход — нет второго `rest` (или `rest_repeat`); ночёвка после кулдауна →
   accepted; в журнале `recent_turns` с `outcomes`, без `requests`/`rolls`; повтор абзаца прошлого хода — 0 на 20 ходов;
   input-токены не выросли > 5 % против ЖП1; sonnet/3.8-flash: 5 ходов без изменений.

## 4. kaban-doeba (TDD; cov/mutmut гоняет оркестратор фоном)
- Шаг 0 (на main до правок kaban): фикстура v9 из v8; `test_migration_v10.py` по образцу `test_migration_v8.py`
  (чистая, вход не мутирует, `MIGRATIONS[9]`, версия 10, дефолты полей, round-trip фикстуры, `test_schema_fingerprint`).
- Защита золота: сценарий дракона → rejected с суммой и номером хода, `gold_repeat`, money не изменился; вне окна,
  другая сумма, окно 0, отрицательная дельта, `lose` → accepted; сравнение после капа; loot/hoard не затронуты; пустые
  `recent_turns`; свёрнутая запись боя видна защите.
- Защита отдыха: `long_rest` ставит `long_rest_end_s`; сценарий vale; отказ не двигает часы и не применяет swap'ы, сигнал
  с `clock_text` и `advance_time`; ровно на границе кулдауна → accepted; кулдаун `"0h"`; старый сейв (None); short не
  затронут; 0 HP → прежний Invalid (порядок проверок); `LimitsConfig` парсинг/мусор.
- Память хода: `outcomes`/`money_delta_cp` после хода; rejected в `outcomes`, не в UI; Invalid нет; clamped есть; trade →
  отрицательная дельта; `fold_fight`; `recent_turns_keep`.
- Промпт: ключи `recent_turns` ровно `{turn_seq, at_s, player_input, narration, outcomes}`; окно/вытеснение без изменений;
  summarizer без изменений; правило в `narrator_rules.md`.
- Теги → авто-репорт; `--replay-report` синтетического репорта с отказом — код 0.
- mutmut: `resources:gold`, `gold_explicit`, `gold_repeated`, `rest`, `rest_redundant`; `rests:long_rest`;
  `turn:TurnRunner.commit`, `TurnRunner.recording`; `combat_fold:fold_fight`; `prompt:turn_data`, `PromptBuilder.state_data`;
  `m0010_v9_to_v10:migrate_v9_to_v10`; `settings:LimitsConfig`. Пик контекста doeba > 200k — делить на «тесты» и «мутанты/cov».

## 5. Критерии готовности
Тесты зелёные, cov ≥ 97 %, smells ≤ 200, ruff/dead чисто, mutmut по списку без живых (кроме эквивалентных/текста);
`ai-dm --mock` код 0; офлайн-гейт §3 п.6; фикстура v9 и `save_v10.schema.json` в репо; живых вызовов нет; ревью mama-kaban;
`docs/checklist-tm-live.md` (не коммитить).

## 6. Оценка
papa ~120 тыс. (факт, fable); kaban 80–110; doeba 150–200; mama ~30. Итого ≈ 0,4–0,46 млн (роадмап 0,4). При Q1б ≈ 0,3.

## 7. Риски
- Ложный `gold_repeat`: две разные награды одной суммы за 3 хода — вторая отклонена. Два `gold` в одном ответе не ловятся.
- Ложный `rest_repeat`: ночёвка раньше кулдауна — отказ без восстановления; `advance_time` «до утра» выразить нечем
  (кандидат в BACKLOG по итогам ЖП). Q2а усиливает риск.
- Копирование текста слабой моделью защитами не лечится — только правилом и итогами; при повторах в ЖП — Q3б отдельно.
- `WINDOW` мока памяти (25500) может потребовать подъёма — отметить в handoff.
- Старые `--replay-report` расходятся на вызове 1 (прецедент B59/T60/ТВ).
- Сейвы пользователя мигрируют в v10 при загрузке; старые записи защиту золота не питают; первый отдых всегда принят.
- `use_item` предмета без эффекта (мазь Брана) — модель может описать лечение; в ТМ только запись отказа в `outcomes`.

## 8. Вопросы проектировщику (рекомендации papa)
1. **Сейв**: (а) v10 — `outcomes`, `money_delta_cp`, `long_rest_end_s`, чистая миграция; (б) v9 — защиты грубее, итогов
   в промпте нет. Рек.: **(а)**.
2. **Кулдаун длинного отдыха**: (а) `"16h"` — строго SRD; (б) `"12h"` — утренний бой + вечерняя ночёвка проходят. Рек.: **(б)**.
3. **Порядок `player_input` в JSON**: (а) не трогать в ТМ, смотреть ЖП; (б) вынести ввод в конец сообщения. Рек.: **(а)**,
   кандидат в BACKLOG.
4. **Сейв vale** (+16 ч фантомного времени): (а) не править; (б) откатить часы вручную. Рек.: **(а)**.
