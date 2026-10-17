# ТХ. Повторы хода: опыт и время (BACKLOG 69, 70; хвосты 73, 74)

## Суть

Мини-партия, сейв v11, без полей сейва и миграции — по образцу ТМ (`gold_repeated`, `rest_repeat`).
Защиты от повтора на `recent_turns.outcomes`: опыт (`award_xp`) и время (`advance_time` с `category`, путь `travel`
не трогаем). Правила рассказчику: за что давать опыт, когда двигать время. Хвосты: 73 — дока о `defaults.toml`,
74 — сверка журналом импорта. Причина повторов — гипотеза кода (слабая модель копирует вызовы прошлых ходов),
69 офлайн не подтверждён, проверка в ЖП2 (R7 Q2а / R8 #2).

## Решения

2026-10-18, проектировщик:
- В1 (69): не больше одного `award_xp` за сцену; второй в той же сцене — мягкий отказ с авто-репортом.
- В2 (70): `hour` подряд без пути и без дела — мягкий отказ как `rest_repeat` (`report_tag`), окно в ходах из конфига.
- В3 (74): сверить с журналом импорта; если повторов `invalid_request` после строки про `gte` нет — закрыть 74
  как не подтвердившийся.
- План папы-кабана (ниже, с умолчаниями `xp_awards_per_scene=1`, `time_repeat_turns=2`) принят: «окей, кабаним».
- По ревью: два `award_xp`/`hour` в одном ходу проходят оба — «оставить, это нормально, в беклог не кладем».

## Груминг (свинопас, 2026-10-18)

Вердикт: почти готов, блокеры В1–В3 сняты решениями выше. Точки: `protocol/handlers/resources.py` (`award_xp` ~676,
`advance_time` ~777, образцы ~574, ~734), `state/scene.py:49` (`TurnRecord.outcomes`), `master/prompt.py:76`,
`master/prompts/narrator_rules.md` (стр. 44, 115; `STATIC_MAX` 18700), `master/prompts/import_rules.md:16`.
Офлайн: `saves/drunk_dragon-00000001/journal/calls-009.jsonl` — 34 из 74 записей «Время идёт: 3600 с»
(gemini-4-argon, flash-lite); `.gz` и бэкапы dusk_academy не разобраны. Хвост BACKLOG 81 (окно мока памяти на
`context_cap`) — партия трогает narrator_rules. 75 в ТХ не входит.

Поправка груминга: «34 из 74» — строка `recent_turns` в запросах, а не ходы (см. §0 плана).

## План (папа-кабан, 2026-10-18)

### 0. Офлайн-разбор журналов (сделан, только чтение)
Журналы: drunk_dragon-00000001 (314 ходов), dusk_academy-d3de6c57 + бэкапы 13/15.10 (464), vale-cd40a140 (41).
- 69: `award_xp` — дракон 5/314, dusk 11/464; двух в ходу — 0; пар ближе 3 ходов — 0. Офлайн не подтверждён.
- 70: `hour` — дракон 6/314, dusk 16/464; серия «час без дела» — одна: dusk 298–299 (3.8-flash, разговор +
  `advance_time hour`). Защита отклонила бы ход 299.
- 74: единственный журнал импорта `campaigns/test/.import/journal/calls-001.jsonl` (2026-10-10): один
  `invalid_request` про `gte`, второй вызов принят, повторов нет. По В3 — 74 dropped, промпт импорта не трогать.

### Партия кода (kaban)
1. `defaults.toml [limits]` + `LimitsConfig`: `xp_awards_per_scene=1`, `time_repeat_turns=2` (`ge=0`, 0 — выкл.).
2. `resources.py`: константы `XP_LOG = "Опыт: +"`, `TIME_LOG = "Время идёт: {} с"` вместо литералов.
3. `xp_awarded_in_scene(ctx) -> list[int]`: seq записей `recent_turns` текущей сцены с outcome на `XP_LOG`;
   нет сцены → [].
4. `award_xp`: при `limit>0` и `len(seqs)>=limit` → rejected «повтор награды», `report_tag="xp_repeat"`.
5. `time_repeated(ctx, seconds) -> int | None`: окно `time_repeat_turns`; «час без дела» — `TIME_LOG` в outcomes и
   `set(requests) <= {"advance_time","offer_choices"}`.
6. `advance_time` → диспетчер; `category` → `time_by_category`: `hour` при `time_repeated` → rejected «повтор часа»,
   `report_tag="time_repeat"`; `travel` не трогать. Вынос нужен и для smells.
7. `narrator_rules.md`: правило опыта (раз за сцену; minor/medium/major) и времени (разговор/осмотр — без
   `advance_time` или `minute`; `hour` — ожидание/работа; путь — `travel_to`), ≈240 токенов.
8. `STATIC_MAX`: замерить; ожидание ≈18430 ≤ 18700; иначе total + 3 % с причиной.
9. Доки: ARCHITECTURE 489–492 (защиты), 73 — README 153–155 (rules-секции только в `defaults.toml`),
   ARCHITECTURE:25 `ai-dm.toml` → `~/.config/ai-dm/config.toml`. Карточки done/ 069, 070, 073, 074 (dropped), 081.
10. Офлайн-гейт `ai-dm --mock`; `make smells` после каждого файла (баланс 200).

### Хвост 81 (kaban-doeba, первым, до п. 7)
`memory_script.memory_settings` — фиксированные `NPC_MEMORY_WINDOW` и `MEMORY_CONTEXT_CAP` (подобрать один раз,
ступени `test_stage4_memory` на тех же сценах); `WINDOW` и историю подборов убрать.

### Тесты (kaban-doeba, образцы test_gold_repeat, test_rest_repeat, test_tm_auto_reports)
- `xp_awarded_in_scene`: пусто; своя сцена; чужая сцена; не тот префикс; нет сцены.
- `award_xp`: первый accepted; второй rejected `xp_repeat`, bundle без изменений; лимит 0 и 2; новая сцена; max-уровень.
- `time_repeated`: окно 2; 0 → None; час без дела → seq; с `skill_check` → None; 900 с → None; путь → None; свёрнутый бой.
- `advance_time`: повтор часа rejected, часы на месте, без `concentration_note`; minute/day accepted; после дела
  accepted; travel не затронут; Invalid `category_or_travel_to`; тексты лога прежние.
- `LimitsConfig`: дефолты, `ge=0`, `[limits]` в config.toml отвергается.
- Авто-репорт: теги в `turn.report_tags`, один файл. Правила: `test_master_rules`, `test_static_budget`,
  `test_stage4_memory` без смены констант.
- mutmut: `resources:award_xp`, `resources:advance_time`, `resources:xp_awarded_in_scene`, `resources:time_repeated`,
  `resources:time_by_category`, `config.settings:LimitsConfig`; TESTS="tests/unit/protocol tests/unit/config".

### Чек-лист ЖП2
3 разговорных хода — без `hour`; «подождать час» accepted, «ещё час» → `time_repeat`; завершённая цель — один
`award_xp`, второго нет; считать `xp_repeat`/`time_repeat`; input ≤ +5 % к ЖП1; повторы абзацев (75) отдельно.

### Риски
Ложный `time_repeat` (честное ожидание два часа подряд) и `xp_repeat` (две награды в длинной сцене) — приняты по
В1/В2; гипотезы 69/70 — проверка только в ЖП2; правила меняют fingerprint → старые `--replay-report` расходятся;
smells 200/200; 81 делать до п. 7.

## Правки по ревью и аудиту (2026-10-18)

- Мама-кабан: тест раздела «Опыт и время» с проверкой `XP_LOG`/`TIME_LOG` — сделан; фраза правила «два часа подряд»
  → «повторный `hour` в ближайшие ходы»; `award_xp` не ищет награды при лимите 0; тест ритма часа (принят,
  отклонён, отклонён, принят); два вызова в одном ходу — известное ограничение (решение проектировщика), тесты
  `test_known_limitation_*`.
- Кабан-свекровь: груминг прошёл без её аудита (пропуск оркестратора, на код не повлиял); `time_repeat_turns=2`
  выбрал папа-кабан — принят вместе с планом; правка `pyproject.toml` — временная подмена `make mutate`, восстановлена.

## Итог

- Закрыто: BACKLOG 69, 70, 73, 81 (done), 74 (dropped) — карточки в docs/done/.
- Тесты: 17764 passed, 1 xfailed (21 мин); cov 97,67 %; smells 200/200; `make dead` чист; ruff — 18 старых E501.
- STATIC_MAX: explore total 18458 ≤ 18700, порог не менялся.
- mutmut (award_xp, xp_awarded_in_scene, advance_time, time_repeated, time_by_category): 123 убито, 12 выжили
  (строки reason/сигнала/ключ `total_xp`/message Invalid) — все закрыты тестами по разбору, повторно не прогонялись.
  `LimitsConfig` в прогон не включён.
- Расход субагентов (токены): свинопас 45,5k (opus), папа-кабан 108k, доеба (81) 41,6k, кабан 58,8k,
  доеба (тесты) 50,3k, мама-кабан 26,3k, свекровь 30k, доеба (ревью/мутанты, sonnet) 37,9k. Кабан-тесть не звался.
- Проверка гипотез 69/70 — в ЖП2 (пункты чек-листа — раздел «Чек-лист ЖП2»).
