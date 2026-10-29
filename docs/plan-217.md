# Шаг 217. Сон перемоткой времени не восстанавливает ячейки (BACKLOG 217)

## Суть
Репорт t1341: мастер вместо `rest long` перемотал время `until=morning` — ячейки и HP не восстановились.
Груминг: свинопас, аудит груминга — кабан-свекровь (2026-10-29).

## Решения
Проектировщик, 2026-10-29:
- Вариант А (NOTES.md 2026-10-29): сдвиг ≥ порога, долгий отдых доступен, `rest` в ходе не было — движок
  отказывает с подсказкой «сон — rest long». Отклонены «движок сам применяет отдых» и «только промпт».
- 1. Охват — Б: `until` и `category=hour` с count ≥ порога; дни, недели, месяцы и `travel_to` не трогать.
- 2. Неоплаченный ночлег в трактире — отдых считается доступным, сдвиг отклоняется (А); вне трактира А и Б
  совпадают (отдых бесплатный).
- 2а. Обхода «герой не спит» (караул, плен) нет; после такого сдвига отдых тоже применяется через отказ.
- 3. Отказ кладёт репорт в issues/ со своей меткой (например `sleep_not_rest`).
- 4. Порог — `[time] long_rest_s` из конфига.
- 5. Промпт (`narrator_rules.md`) не трогать.
- 6. Сейв drunk_dragon не править: игрок выспится в игре.
- 7. priority: medium остаётся.

- Аппрув плана (2026-10-29): умолчания папы 1–5 приняты; «окей, кабаним».

Побочная находка груминга (t1364, t1367, `time_repeat`) — BACKLOG 219, не в этом шаге.

## План (папа-кабан, 2026-10-29)

Контур: вне msa; режим: встроить. Входы: решения 1–7 выше, NOTES.md 2026-10-29, груминг свинопаса и аудит
свекрови (scratchpad сессии 2026-10-29). Размер — S, одна партия: две новые функции, две точки вызова, тесты, две
строки документов.

**Задача:** сдвиг времени на ≥ `[time] long_rest_s` при доступном долгом отдыхе и без `rest` в ходе движок
отклоняет (`rejected`, метка репорта), подсказывая рассказчику «сон — `rest long`».

### Правила, которые меняются (первым пунктом аппрува)

1. `time_until` (`protocol/handlers/resources.py:1009-1033`), ветки `morning` и `hour`. Было: `seconds = target -
   now_s; world.clock.advance(seconds)` без условий → станет: перед `advance` — `if seconds >= cfg.time.long_rest_s
   and not ctx.rested and long_rest_available(ctx): return rejected(..., report_tag="sleep_not_rest")`; часы и
   `ctx.until_done` не трогаются. Ветка `until == "long_rest"` (:1014-1021) не меняется: при доступном отдыхе она уже
   отклоняется «вызови rest long» (`test_rest_repeat.py:471-497`).
2. `time_by_category` (`resources.py:957-986`), `category == "hour"`. Было: проверка `time_repeated` → цикл →
   `advance` → станет: первой — та же проверка 217 с `seconds = count * cfg.time.advance_categories["hour"]`
   (при умолчаниях `count >= 8`), затем всё как сейчас. `day`/`week`/`month` и `travel` (:1072) — без правок
   (решение 1).
3. «Долгий отдых доступен» — новая `long_rest_available(ctx)` = условия, при которых `rest long` сейчас проходит или
   ждёт сам: `hero.status != "dead"`, `hp_current > 0` (`rules/rests.py:60-65`), кулдаун — `next_long_rest_s` None
   или `next_s - now_s <= Duration.parse(cfg.limits.long_rest_wait_max).seconds` (как `rest_redundant`,
   `resources.py:813-818`). Оплата ночлега не учитывается (решение 2 = А): после отказа 217 `rest long` сам скажет
   «ночлег платный: service buy …» (`lodging_unpaid`, :840-870) — цепочка подсказок, как в 173
   (`docs/plan-fix-dusk.md`, 2026-10-24).

**Поведение:** меняется — (а) `until=morning`/`until=hour` и `hour` × N на ≥ 8 ч без `rest` при доступном отдыхе
→ отказ, часы стоят; (б) порядок «`until` принят, затем `rest` в том же ходу» (тег `until_then_rest`,
`resources.py:877-879`) при сдвиге ≥ 8 ч больше не случается — `until` отклонён, `rest` проходит без тега
(двойного сдвига нет); при сдвиге < 8 ч — как сейчас (`test_xp_time_repeat.py:571-577`, 2:15 → 6:00). Всё
остальное (`day`, `travel_to`, `until=long_rest`, сдвиг после `rest`, кулдаун > 8 ч, 0 HP) — как сейчас.
**Вне ai-dm:** нет.

### Модули, файлы, функции

- `src/ai_dm/protocol/handlers/resources.py`:
  - `long_rest_available(ctx)` — новая (п. 3), рядом с `rest_wait_s` (:802).
  - `sleep_without_rest(ctx, seconds)` — новая: `None`, если `seconds < cfg.time.long_rest_s`, или `ctx.rested`, или
    отдых недоступен; иначе `rejected("сон без отдыха", <подсказка>, report_tag="sleep_not_rest")`. Подсказка (видит
    рассказчик, не игрок): «Это сон: время не двигай, вызови rest long в этом же ходу — отдых сам сдвинет часы и
    восстановит HP и ресурсы.»
  - `time_until` (:1009) — вызов `sleep_without_rest` перед `world.clock.advance` в ветке `morning`/`hour`.
  - `time_by_category` (:957) — вызов до `time_repeated` для `hour` (иначе после праздного часа на прошлом ходу
    «сон 8 часов» получит чужой отказ `time_repeat` «час уже прошёл»).
  - `advance_time` (:1054), `rest` (:873), `rest_apply` (:883), `travel` (:1072) — без правок.
- `src/ai_dm/protocol/context.py:35-36` (`rested`, `until_done`) — без правок.
- Тесты: новый `tests/unit/protocol/test_sleep_not_rest.py` (стиль `test_rest_repeat.py`, `test_xp_time_repeat.py` —
  файл на фикс, `protocol_kit.make_ctx`/`req`); правка `tests/unit/protocol/test_apply_resources.py:648-651`
  (`clock_at`) — см. умолчания; `tests/unit/game/test_tm_auto_reports.py` — один тест на метку в `meta.json`.
- Документы: `docs/ARCHITECTURE.md:503-509` (перечень защит с тегами — добавить `sleep_not_rest`),
  `docs/rules-adaptation.md:65-67` («`until` и `rest`» — одна фраза об отказе при сдвиге ≥ `long_rest_s`).
  `narrator_rules.md` — не трогать (решение 5).

### Партия (одна)

1. `resources.py` — `long_rest_available`, `sleep_without_rest`, вызовы в `time_until` и `time_by_category`;
   проверка: `uv run pytest tests/unit/protocol/test_apply_resources.py tests/unit/protocol/test_xp_time_repeat.py
   tests/unit/protocol/test_rest_repeat.py tests/unit/protocol/test_apply_rest_lodging.py` — ожидаю 5 падений в
   `test_apply_resources.py` (список ниже), остальное зелёное.
2. Тесты — новый файл + правка `clock_at` + авто-репорт; `uv run ruff check src tests`.
3. Документы (2 строки), BACKLOG 217 → `docs/done/217-…`, стоимость — тесть.
4. Перед коммитом: `make cov`, `make smells`, `make dead`, `make mutate FUNCS="ai_dm.protocol.handlers.resources:
   long_rest_available ai_dm.protocol.handlers.resources:sleep_without_rest ai_dm.protocol.handlers.resources:
   time_until ai_dm.protocol.handlers.resources:time_by_category" TESTS="tests/unit/protocol"` (каталог целиком —
   AGENTS.md, шаг 202 решение 16; 3197 тестов в каталоге, `--co` 2026-10-29; четыре файла выше — 380 тестов,
   128 с одним потоком, измерено; весь каталог не измерял), `make mutate-diff`.

Существующие тесты, которые падают от правила (измерено чтением: сдвиг ≥ 8 ч, герой `make_hero` без кулдауна и с
HP 200, `rest` не было) — все в `tests/unit/protocol/test_apply_resources.py`:
`test_until_morning_in_evening_goes_to_next_morning` (:721, 35640 с), `test_until_morning_log_is_time_line` (:729),
`test_until_morning_exactly_at_dawn_goes_to_tomorrow` (:741, DAY), `test_until_hour_after_it_goes_to_tomorrow`
(:759, 23 ч), `test_until_hour_later_today` (:766, 10,5 ч). Они про арифметику часов, не про сон — чинить
контекстом, не ожиданиями (умолчание ниже). Остальные `until`-тесты (`test_game_turn.py:686`, 2:00 → 6:00;
`test_master_session_loop.py:910`, 2:15; `test_xp_time_repeat.py:542-600`, 2:15) — сдвиг < 8 ч, не задеты.
`hour` с `count` ≥ 8 в тестах нет (grep `counted("hour"` — максимум 3).

### Тестовые сценарии (для кабана-доебы)

Все — `apply(ctx, req(...))`, герой `make_hero` (HP 200, `long_rest_end_s=None`), если не сказано иное; «ожидание,
не проверено» — везде, прогона с правкой нет.
- t1341: 20:00, `until=morning` (36000 с ≥ 28800) → `rejected`, `report_tag == "sleep_not_rest"`, в
  `signal_to_master` есть «rest long», часы и `dump(ctx)` не изменились, `ctx.until_done is False`.
- 22:30, `until=morning` (27000 с < 28800) → `accepted`, как сейчас (граница снизу).
- Ровно 28800 с (22:00 → 6:00) → `rejected` (граница ≥).
- `until=hour, until_hour=18` в 7:30 (10,5 ч) → `rejected` (решение 1 — Б: любой `until`).
- `category=hour, count=8` → `rejected` с той же меткой; `count=7` → `accepted`; `count=8` после `rest long` в том
  же ходу → `accepted` (`ctx.rested`); `count=8` при записи праздного часа в `recent_turns`
  (`make_ctx_with(..., [hour_turn(4)])`) → `rejected` с меткой `sleep_not_rest`, не `time_repeat`.
- `category=day, count=1` и `travel_to` с дорогой ≥ 8 ч → `accepted`, как сейчас (решение 1).
- `rest long` принят, затем `until=morning` → `Invalid until_with_rest`, как сейчас (`test_xp_time_repeat.py:546`).
- `until=morning` ≥ 8 ч, затем `rest long` в том же ходу → `until` отклонён, `rest` принят, `report_tag is None`
  (поведение «б» выше); при сдвиге < 8 ч — `until_then_rest`, как сейчас (:571).
- Отдых недоступен → сдвиг проходит: `long_rest_end_s = now` (ждать 12 ч > 8 ч), 20:00 `until=morning` →
  `accepted`; `hp_current = 0` → `accepted`; `hero.status = "dead"` → `accepted`.
- Кулдаун ждать ≤ 8 ч (`long_rest_end_s = now - 4h`, ждать 8 ч) + `until=morning` ≥ 8 ч → `rejected`
  (`rest long` подождал бы сам — `wait_for_long_rest`).
- `until=long_rest` при кулдауне с ожиданием 10 ч → `accepted`, как сейчас (ветка не трогается).
- Трактир, комната не оплачена, денег хватает (`test_apply_rest_lodging.inn_ctx`), 20:00 `until=morning` →
  `rejected sleep_not_rest`; следом `rest long` → `rejected rest_unpaid` «ночлег платный» (решение 2 — А, цепочка).
- Порог из конфига: `load_rules_config("[time]\nlong_rest_s = 36000\n")`, сдвиг 9 ч → `accepted`, 10 ч → `rejected`.
- Авто-репорт (`test_tm_auto_reports.py`, `make_app` + `scripted`): ход с `advance_time until=morning` ночью (при
  `now_s` = 20:00) → каталог `issues/…-t<N>-sleep_not_rest`, `meta.json["tags"] == ["sleep_not_rest"]`.
- Проверка руками (живой прогон, drunk_dragon): «лягу спать» вечером → в журнале `calls-*.jsonl` отказ
  `sleep_not_rest`, затем `rest long` в том же ходу; утром ячейки полные; в `issues/` появился каталог с меткой.

### Развилки и риски

Развилок к проектировщику нет: все решения приняты (1–7 выше). Риски:
- Сдвиг < 8 ч не ловится: «лёг в 23:00, проснулся в 6:00» (7 ч) проходит, ячейки не восстанавливаются — следствие
  решения 4 (порог = `long_rest_s`), не 217; если всплывёт в прогоне — пункт беклога, не этот шаг.
- Дневное ожидание ≥ 8 ч (`until_hour=18` в 7:30, `hour` × 8 за работой) теперь отказ → рассказчик вызовет
  `rest long`, герой «спит» днём и восстанавливается — следствие решений 1 (Б) и 2а (обхода нет).
- Отказ при кулдауне с ожиданием ≤ 8 ч: `rest long` подождёт конца кулдауна и прибавит 8 ч отдыха — герой
  проснётся позже, чем просил `until=morning`; допустимо (`wait_for_long_rest`, 173).
- Порядок проверок в `time_by_category` (217 до `time_repeat`) — внутренний; BACKLOG 219 рядом, конфликта нет.

### Умолчания (внутреннее)

- Имена: `long_rest_available`, `sleep_without_rest`, метка `sleep_not_rest` (решение 3 — «например»), `reason`
  «сон без отдыха» (стиль «повтор часа», «отдых уже был»). Текст подсказки — выше в «Модули»; видит рассказчик.
- Порог: `seconds >= cfg.time.long_rest_s` (включительно); для `hour` — `count * advance_categories["hour"]`, не
  цикл по `category_seconds`.
- `test_apply_resources.clock_at` — герою ставится `long_rest_end_s = now_s` (кулдаун 12 ч > 8 ч, отдых недоступен):
  пять арифметических тестов проходят без смены ожиданий; `until=long_rest` в этом файле — только через
  `until_hour_only_with_hour` (Invalid до ветки). Альтернатива — `hp_current = 0`; хуже: смешивает с
  `rest_impossible`.
- Новый файл тестов `test_sleep_not_rest.py`, не дописывание в `test_apply_resources.py` (1167 строк).
- `ctx.until_done` при отказе не ставится — `rest` следом идёт без тега.

### Открытые вопросы

нет.

## Смета (кабан-тесть, режим 1)

**Что проверено:** план 217 (одна партия, размер S). Подписок, хостинга, внешних API в шаге нет: живые вызовы API
рассказчика — только в прогоне Влада, вне сметы. Платное — токены цепочки. Источник масштаба — «Итог» шага 190
(`docs/plan-190.md`, две партии, M) × ≈ 0,4–0,5. «Уже прошло» — `metrics.py` по сессии ab560c60 (id из `agents.md`).
Цены — тариф metrics.py от 2026-10-25 (opus/fable 4/5/0,20/20, sonnet 2/2,5/0,10/10 $ за 1M), с сайтом не сверял.

| Статья | Сейчас ($/мес) | Допущения | Дешевле | Экономия | Что теряем |
|---|---|---|---|---|---|
| токены цепочки шага 217 | разово ≈ 10–16 $ | 1 партия, без повторных кругов ревью | оркестратору — /compact перед партией | ≈ 1–3 $ | ничего, если состояние в документе |
| mutmut по `tests/unit/protocol` (3197 тестов) | 0 $ (локально), время ≈ 1–2,5 ч фоном | 4 функции; в 190 — 2,5–3 ч | нет: каталог целиком требует AGENTS.md (решение 16 шага 202) | — | — |

| Партия | Время |
|---|---|
| груминг + аудит + план (прошло) | ≈ 14 мин работы (свинопас 5,3, свекровь 0,5, папа 8,4) |
| П1 kaban | 15–30 мин |
| П1 doeba (тесты, cov ≈ 15 мин) | 25–40 мин + mutmut 1–2,5 ч фоном |
| П1 мама ‖ свекровь + коммит | 5–15 мин |
| Декарт (1 партия + 1 сводный) | 5–10 мин |
| итого | ≈ 1–1,5 ч агентов + mutmut фоном |

| Роль | Модель | Токены | $ (тариф metrics.py 2026-10-25) |
|---|---|---|---|
| svinopas (прошло) | opus | 1,90 M | 1,66 |
| kaban-svekrov, груминг (прошло) | opus | 0,08 M | 0,16 |
| papa-kaban (прошло) | fable | 1,16 M | 1,23 |
| kaban | sonnet | 3–5 M | 1,0–1,5 |
| kaban-doeba (+ разбор мутантов меньшей моделью) | sonnet | 4–5 M | 1,5–2,0 |
| mama-kaban | opus | 0,6–0,9 M | 0,7–1,0 |
| kaban-svekrov | opus | 0,6–0,9 M | 0,7–1,0 |
| kaban-dekart (2 вызова, выжимки ≤ 400 KB каждая) | fable | 0,4–0,8 M | 0,4–0,9 |
| оркестратор | opus | 10–18 M | 4–7 |
| итого | | ≈ 22–34 M | ≈ 11–16 |

Оговорки: в 190 оркестратор и папа вышли в 2–2,5 раза выше сметы из-за двух сессий и повторных запусков; здесь
развилок нет, риск ниже. Ревью и аудит не урезаются. Бюджет решений не ведёт (решение Влада 2026-10-18) — вердикт
справочный: ок по бабкам.

## Правки по ревью

П1, круг 1 (2026-10-29): мама — можно мержить, одно мелкое замечание; свекровь — чисто, решений за пользователя нет.
- Мама: `test_unpaid_inn_rejects_sleep_then_rest_says_lodging_paid` собирал трактир вручную, план ссылается на
  `test_apply_rest_lodging.inn_ctx`. Исправил кабан: тест берёт `inn_ctx`, время 20:00 выставляется после вызова;
  ручная сборка NPC убрана (решение мамы, условие «если можно выставить 20:00» выполнено). 23 passed, ruff чисто,
  smells 200.

П1, круг 2 (2026-10-29): мама и свекровь — чисто.

Мутанты (2026-10-29, решение Влада «запускать»): в диффе 9 выживших — `sleep_without_rest` 12–15, 17–19 (тексты
отказа), `time_until` 43–44 (`until != "long_rest"`); доеба добавил `test_sleep_rejection_reason_and_signal_text` и
`test_until_long_rest_with_wait_over_threshold_is_accepted`, эквивалентных нет. Старые строки (9) — BACKLOG 220.
Повтор mutmut и cov — решение Влада «запускать повтор».

П1, круг 3 (тесты доебы по мутантам): мама и свекровь — чисто.

Повтор (15:30–15:53, load average 70–87): 9 выживших в диффе убиты; в диффе 3 timeout — `time_by_category` 8, 9, 13
(в первом прогоне их не было, причина не установлена); старые строки — survived те же 9 (BACKLOG 220) + 12 timeout.
cov 98,15 %; 2 failed — `test_tui_entry_points.py::test_error_menu_save_and_quit_ends_app_and_saves`,
`::test_quit_command_ends_app` (DeadlockError Pilot под нагрузкой; TUI шаг не трогал); повтор файла — 91 passed.
dead чист, smells 200.

Закрытие (2026-10-29): архитектор — 217 ✅, 219 после ФС перед 212, 220 — при касании в 219. Р1 место 219 —
решение Влада «б — после ФС» (рекомендация архитектора); Р2 (220 без своей строки) — не блокирует, как поставлено.

## Итог

**Источник токенов:** `metrics.py` по `~/.claude/projects/-Users-vladislavahtamov-projects-ai-dm/ab560c60-d4a9-462f-a7af-88de771d0b69.jsonl`
(id ролей — scratchpad `agents.md`); **цены:** тариф metrics.py от 2026-10-25,
https://platform.claude.com/docs/en/about-claude/pricing (с сайтом сегодня не сверял; fable — по ценам Opus).
Закрыт BACKLOG 217 (`docs/done/217-…`); заведены 219, 220. Коммита на момент подсчёта нет.

| Партия | Смета | Факт |
|---|---|---|
| груминг + аудит + план | ≈ 14 мин (прошло) | 14,2 мин работы (свинопас 5,3, свекровь 0,5, папа 8,4) |
| П1 kaban | 15–30 мин | 2,2 мин (сегменты 1,9 + 0,3, вкл. правку `inn_ctx`) — правка S и точный план |
| П1 doeba | 25–40 мин + mutmut 1–2,5 ч фоном | 1,2 мин агента (два запуска); cov 21,6 + 22 мин, mutmut ≈ 23 + 23 мин фоном (два круга — решение Влада) — mutmut быстрее сметы: 4 функции |
| П1 мама ‖ свекровь (3 круга) + закрытие | 5–15 мин | 1,5 / 1,9 мин работы (интервал 35 мин — ожидание mutmut); архитектор 2,3 мин — в смете не было |
| Декарт (1 + 1 сводный) | 5–10 мин | не запускался на момент подсчёта |
| итого | ≈ 1–1,5 ч + mutmut фоном | ≈ 23 мин работы агентов + ≈ 1,5 ч cov/mutmut фоном; сессия — 143 мин интервал, в т. ч. окна Влада |

| Роль | Модель | Токены | $ |
|---|---|---|---|
| оркестратор | opus | 9,43 M | 4,17 — на момент подсчёта 16:01 |
| svinopas | opus | 1,90 M | 1,66 |
| papa-kaban (план + архитектор ROADMAP) | fable | 1,87 M | 1,90 |
| kaban | sonnet | 0,74 M | 0,32 |
| kaban-doeba | sonnet | 0,30 M | 0,21 |
| mama-kaban | opus | 0,41 M | 0,56 |
| kaban-svekrov (груминг + П1) | opus | 0,70 M | 0,82 |
| kaban-test | opus | 0,22 M | 0,43 — на момент подсчёта 16:01 |
| kaban-dekart | fable | — | не запускался |
| итого шага | | 15,59 M | 10,08 |

Расхождение: смета ≈ 11–16 $ → факт 10,08 $. Ниже сметы — кабан (0,32 при 1,0–1,5) и доеба (0,21 при 1,5–2,0):
план с готовыми сценариями и правкой S. Выше — папа (1,90 при 1,23 прошедших): второй запуск архитектором на ROADMAP.
Оркестратор 4,17 — у нижней границы сметы (/compact между этапами). Декарт в факт не вошёл.

**Итого:** смета ≈ 11–16 $, 1–1,5 ч → факт 10,08 $ (без Декарта), ≈ 23 мин агентов + ≈ 1,5 ч cov/mutmut фоном.
Разбор — кабан Декарта.
