# 182 Мытьё вне бани снимает вонь

BACKLOG 182 (medium; поглощает 154). Строка ROADMAP — «182 Мытьё вне бани снимает вонь».

## Суть

Вонь (`smelly`) снимает только платная услуга с бонусом `washed` (баня, удобная и богатая комната —
`rules/boons.py:grant_boon` → `rules/hygiene.py:mark_washed`). Мытьё в рассказе (река, бочка, бесплатная баня у
хозяев — drunk_dragon, ход 1112) движок не видит: флаг `washed:<hero>` не обновляется, ночной тик
`world_sim/hygiene.py:roll_day` через `hygiene_days` снова ставит вонь. Нужен путь рассказчика отметить мытьё.

## Решения

2026-10-25, Влад (груминг, окна свинопаса и свекрови):

1. Мытьё вне платной услуги — новый инструмент рассказчика «герой помылся»; движок снимает вонь, игрок видит в ленте
   строку «Вонь смыта», как после бани (1А).
2. Воды в локации не требуется — решает рассказчик по сцене (2А).
3. Мытьё без бани полное, как баня: вонь снята, отсчёт `hygiene_days` заново (3А).
4. Согласие на правку сейва drunk_dragon записано в `NOTES.md` 2026-10-25; шаг сейв не меняет.
5. В этом шаге — раздел «Гигиена» в `docs/rules-adaptation.md` (6А).
6. Порядок: 182 раньше ДН (окно в начале сессии, 2026-10-25) — закрывает открытый вопрос 1.
7. Развилки плана — по рекомендациям папы (окно аппрува, 2026-10-25): Р1 (а) строка «Помылся» при мытье без вони;
   Р2 (а) повтор `wash` принимается молча, идемпотентно.

## Груминг

Отчёты: свинопас — scratchpad `svinopas-182.md`, аудит свекрови — `svekrov-182-grooming.md` (вопросы 1–6 покрыты
решениями 1–5; вопрос 4 свекрови «баня сохраняет преимущество» снят решением 3 — баня остаётся покупным путём, мытьё в
походе надо отыграть).

## План (папа-кабан, 2026-10-25)

Режим «встроить». Одна партия, S: инструмент по образцу `curse`/`scene_mood`, общий код снятия вони вынести из
`grant_boon` в `rules/hygiene.py`.

**Правило:** было (`rules/boons.py:44-49`, ветка `else` в `grant_boon`)
`mark_washed(world, hero, now_s)`; `if any(c.id == SMELLY for c in conditions): conditions[:] = [c … if c.id != SMELLY]; return "Бонус: чист — вонь смыта"` —
достижимо только через `service` buy с `kind.boon == "washed"` →
станет: тот же код — новая `rules/hygiene.py:wash(world, hero, now_s) -> bool` (вернёт, была ли снята вонь);
`grant_boon` зовёт её вместо своих четырёх строк (строки лога те же); новый обработчик `wash` зовёт её по
инструменту рассказчика без услуги и денег. Отсчёт заново — из `mark_washed(now_s)` + `is_stale` без правок (решение 3).
Промпт `narrator_rules.md:106`: было «…помеха на Харизму в бросках, снимает баня» → станет «…снимает баня; мытьё без
услуги (река, бочка, хозяйская баня даром) — инструмент `wash`, когда герой по рассказу вымылся» (решение 2: условия
воды нет, судит рассказчик).

**Поведение:** меняется — (1) рассказчик получает инструмент `wash` (режим explore, не strict); (2) в ленте строка
«Вонь смыта» при снятии вони; без вони — Р1; (3) в контексте мастера `smelly` пропадает из `hero.conditions`
(`master/prompt.py:588`) тем же ходом; (4) бани и комнаты — без изменений (`Бонус: чист — вонь смыта` остаётся).

**Вне репо:** нет.

**Модули/файлы/функции:**
- `rules/hygiene.py`: `wash(world, hero, now_s) -> bool` — новая: `mark_washed` + снять `smelly` из
  `hero.creature.conditions` (код из `grant_boon`); `mark_washed`, `is_stale`, `washed_at` — без правок.
- `rules/boons.py`: `grant_boon` — ветка `else` → `if wash(world, hero, now_s): return f"Бонус: {name} — вонь смыта", True`.
- `protocol/requests.py`: класс `Wash(Request)` — новый, `type: Literal["wash"]`, без полей (у схемы остаётся
  свойство `type`, как у всех — `test_schema.py:77`); докстринг = описание инструмента: «Герой вымылся по рассказу без
  платной услуги (река, озеро, бочка, баня даром): снимает вонь, отсчёт недели заново. Не для бани за деньги — там
  `service`». Добавить в `REQUEST_MODELS` (строка 1057) и в `MasterRequest` (1135).
- `protocol/schema.py`: `"wash"` в `MODE_TOOLS["explore"]` (строки 19–25); в `STRICT_IN_EXPLORE` не добавлять —
  попадёт в `NON_STRICT` сам (строгих в explore остаётся 6 ≤ 16).
- `protocol/apply.py`: `"wash": hero.wash` в `HANDLERS` (строка 17–58).
- `protocol/handlers/hero.py`: `wash(ctx, request)` — новая: `hero.status == "dead"` → `Invalid(code="hero_dead", …)`
  (как `resources.curse:76`); иначе `removed = hygiene.wash(world, hero, world.clock.now_s)`;
  `Decision(status="accepted", result={"washed": True, "smelly_removed": removed}, log=[…])` — строка по Р1.
  Место — `hero.py` (178 строк, рядом с `companion_update`), не `resources.py` (1071 строка).
- `master/prompts/narrator_rules.md:106` — фраза выше.
- `srd/data/conditions/smelly.yaml` — `description`: «…её смывает баня, ночлег в комнате с лоханью или любое мытьё»
  (игроку не показывается: `sheet_text.py:293` и `combat/engine.py:416` берут только `name` — внутреннее).
- `docs/rules-adaptation.md` — новый раздел `## Гигиена` после «Состояния» (решение 5): вонь — не SRD; `hygiene_days`
  (7, 0 — выключено, `config/defaults.toml:192`); помеха на проверки Харизмы (`rules/modifiers/conditions.py:83`);
  ставит ночной тик от начала суток последнего мытья; снимают услуги с бонусом `washed` и инструмент `wash` по
  рассказу; отдых не снимает; миры без флага — отсчёт с первого тика.
- Тесты (doeba): `tests/unit/protocol/test_requests.py` — `VALID["wash"] = {}`, счётчики 40→41 (строка 95), 38→39
  (104), список `plan` (118–119); `tests/unit/protocol/test_schema.py:283` — 38→39, плюс параметризация «в explore и
  не strict / не в боевых режимах» по образцу Ж3 (строки 333–345); `tests/unit/master/test_static_budget.py` —
  `STATIC_MAX` (см. Риски); новый `tests/unit/protocol/test_apply_wash.py`; `tests/unit/rules/test_hygiene.py` —
  `wash`; `tests/unit/rules/test_boons.py`, `tests/unit/protocol/test_apply_service.py:1113`,
  `tests/unit/game/test_shop_actions.py:222`, `tests/scenarios/test_consequences_scenario.py:207` — регресс бани
  (строки лога не меняются, зелёные без правок).
- Не трогать: `rules/auto_flags.py:RESERVED_FLAG_PREFIXES` и `set_flag` (префикс `washed` остаётся закрытым),
  `world_sim/hygiene.py:roll_day`, модель `Location` (решение 2), сейвы (решение 4), `docs/ARCHITECTURE.md`
  (гигиены там нет — grep пуст; не обязателен), `docs/glossary.md` (в таблице состояний только SRD; `cursed`/`diseased`
  тоже не внесены — не добавлять).

**Партия (одна):**
1. `rules/hygiene.py:wash` + `rules/boons.py:grant_boon` на неё — `uv run pytest tests/unit/rules -q` зелёный, строки
   бани прежние.
2. `requests.py:Wash`, `schema.py`, `apply.py`, `handlers/hero.py:wash` — `tests/unit/protocol` зелёные (счётчики
   поправлены), `tests/unit/master/test_static_budget.py` — замер и порог.
3. `narrator_rules.md:106`, `smelly.yaml`, `docs/rules-adaptation.md` «Гигиена»; `make smells` (≤ 200: `grant_boon`
   короче, новые функции ≤ 8 строк), `make cov`, `make dead`,
   `make mutate FUNCS="ai_dm.rules.hygiene:wash ai_dm.rules.boons:grant_boon ai_dm.protocol.handlers.hero:wash" TESTS="tests/unit/rules/test_hygiene.py tests/unit/rules/test_boons.py tests/unit/protocol/test_apply_wash.py tests/unit/protocol/test_apply_service.py"`.

**Тестовые сценарии (кабан-доеба, TDD; `ctx`/`req`/`apply` как в `test_apply_divine.py`, `AppliedCondition` как в
`test_shop_actions.py:225`):**
- `hygiene.wash`: герой со `smelly` → `True`, `conditions` без `smelly`, `flags["washed:<id>"] == now_s`; без `smelly`
  → `False`, флаг обновлён; другие состояния (`cursed`) остаются; старый флаг перезаписан. Ожидание, не проверено.
- `grant_boon("washed")`: со `smelly` → `("Бонус: чист — вонь смыта", True)`; без → `("Бонус: чист", True)` — те же
  строки, что сейчас (`test_boons.py` зелёный без правок).
- `apply(ctx, req("wash"))`: `smelly` → `accepted`, `result == {"washed": True, "smelly_removed": True}`,
  `log == ["Вонь смыта"]`, флаг `== now_s`; без `smelly` → `accepted`, `smelly_removed False`, лог по Р1; повторный
  вызов в том же ходу → `accepted` (идемпотентно, строка по Р1); `hero.status == "dead"` → `Invalid hero_dead`;
  `hygiene_days = 0` → `accepted`, флаг пишется (ночной тик выключен, вреда нет).
- Схема: `wash` в `tool_set("explore")` со `strict False`; нет в `combat_*`, `npc_choice`, `world`; `len(VISIBLE_TYPES) == 39`.
- Регресс хода 1112 (сценарий, по образцу `test_consequences_scenario.py:207` со scripted master): `smelly` на герое,
  ответ мастера с `wash` без `service` → в `reply.turn.lines` «Вонь смыта», `conditions(app) == []`, флаг `== now_s`;
  следующий ночной тик через `hygiene_days − 1` дней вонь не ставит, через `hygiene_days` — ставит (решение 3).
- Проверка руками: `inn_test`, `/sheet` со «вонь» (сейв с `smelly` или `hygiene_days = 1` + сутки); сказать мастеру
  «моюсь в реке» — в ленте «Вонь смыта», `/sheet` без «вонь», в следующем контексте `hero.conditions` без `smelly`.

**Развилки (решает Влад):**
- Р1 — строка в ленте, когда герой моется без вони (отсчёт недели заново, снимать нечего). (а) «Помылся» —
  одна строка, по образцу «Бонус: чист» у бани без вони: игрок видит, что движок принял мытьё; (б) строки нет — тихий
  сброс отсчёта (`log=[]`; `recording` в `game/turn.py:424` тогда добавит только `requests`). Рекомендую (а).
- Р2 — повтор `wash` в том же ходу или на уже чистом герое: (а) принимать молча, идемпотентно (как `scene_mood`);
  (б) `rejected` «герой уже чист» с `signal_to_master` — лишний отказ ради лишней строки. Рекомендую (а); при (б)
  в лог ничего, строка только при Р1 = а и первом вызове.

**Риски:**
- `STATIC_MAX` 23490 (`test_static_budget.py:60`), замер сейчас explore.total 23475 (`static_tokens('explore')`,
  2026-10-25: rules 11874, tools 11601) — запас 15 токенов; схема `wash` и фраза в правилах порог превысят (ожидание,
  не проверено) → поднять по правилу файла: новый замер + 3 %, запись причины в комментарий теста («182: инструмент
  wash и фраза о мытье»).
- Ложные вызовы рассказчика («вымыло паводком», ход 1108) — принято решением 1: судит рассказчик; при живом
  всплеске — отдельный пункт BACKLOG, не этот шаг.
- smells на потолке 200 — `grant_boon` укорачивается, новые функции малые; `hero.py` не раздувать.
- Для роли world инструмента нет (`WORLD_HANDLERS`) — мытьё закадрового NPC не нужно, героя моет только рассказчик.

**Умолчания (внутреннее):** имя инструмента `wash` (коллизий нет: grep `"wash"` по `src/` пуст), без полей — место и
способ мытья уже в тексте рассказчика, в лог не идут; `result` `{"washed": True, "smelly_removed": bool}`;
`DomainEvent` и `add_entry` не пишем (баня тоже не пишет — `grant_boon`); `signal_to_master` нет — вызов инициировал сам
рассказчик, итог видит в `outcomes`; `smelly.yaml` description — обновить (игроку не показывается); карточка done 182 —
тело пункта без правок по RULES, неточный путь `mark_washed` (он в `rules/hygiene.py`, не `boons.py`) остаётся в теле и
пояснён здесь; при Р1 = а строка «Помылся», при Р1 = б — `log=[]`; при Р2 = а повтор даёт ту же строку, что и первый
вызов.

**Открытые вопросы:**
1. Порядок 182 ↔ ДН (`docs/handoff.md:13`) — не блокирует шаг; решает Влад при аппруве, ROADMAP правлю после.

## Смета (кабан-тесть, режим 1)

**Что проверено:** план 182 (одна партия S) — прогон цепочки. Масштаб — «Итог» docs/plan-165.md (тоже 1 партия S:
факт $10,3 / 18,4 M / 145 мин). «Уже прошло» (свинопас, свекровь, папа) по `metrics.py` не сверено — id сессии не
передан, оценка по факту 165. Цены — тариф metrics.py от 2026-10-17 (opus/fable $4 in / $20 out / $0,20 cache read;
sonnet $2 / $10 / $0,10), страницу не сверял; fable — по ценам Opus. Игра: +≈ 60–80 токенов статического промпта
(схема `wash` + фраза) на вызов рассказчика — в основном в кэше, копейки.

| Статья | Сейчас ($/мес) | Допущения | Дешевле | Экономия | Что теряем |
|---|---|---|---|---|---|
| Прогон цепочки 182 (разово) | ≈ $9 за шаг, не помесячно | 1 партия, 1 круг ревью, как 165 | см. ниже | — | — |
| Оркестратор (opus) | ≈ $4 | ≈ 9 M, в основном cache read | /compact перед партией (по правилам) | ≈ $1 | ничего |
| papa-kaban (fable) | ≈ $1,2 (прошло) + закрытие | 1 сегмент плана | закрытие (ROADMAP/done) одним сегментом | ≈ $0,8 | ничего |
| mutmut 3 функции | 0 $ (локально), ≈ 20 мин | фоном | — | — | — |
| API игры | +≈ 70 ток/вызов статики | кэшируется | — | — | — |

| Партия | Время |
|---|---|
| груминг + план (прошло) | ≈ 25 мин |
| П1: код + тесты (kaban ‖ doeba) | ≈ 15–20 мин |
| П1: ревью mama + аудит svekrov, правки | ≈ 10–20 мин |
| П1: `make cov` | ≈ 40 мин |
| П1: mutmut по 3 функциям + разбор | ≈ 20–30 мин |
| итого | ≈ 2–2,5 ч |

| Роль | Модель | Токены | $ (тариф metrics.py 2026-10-17) |
|---|---|---|---|
| оркестратор | opus | ≈ 9 M | ≈ 4 |
| papa-kaban | fable (цены Opus) | ≈ 1,5–2 M | ≈ 1,5–2,4 (часть прошла) |
| svinopas | opus | ≈ 0,6 M | ≈ 0,35 (прошло) |
| kaban | sonnet | ≈ 0,5 M | ≈ 0,3 |
| kaban-doeba | sonnet (+ разбор мутантов) | ≈ 3 M | ≈ 1,2 |
| mama-kaban | opus | ≈ 0,15 M | ≈ 0,2 |
| kaban-svekrov | opus | ≈ 0,2 M (груминг + аудит) | ≈ 0,3 |
| kaban-test | opus | ≈ 0,2 M (смета + итог) | ≈ 0,3 |
| Декарт | opus (допущение) | 2 вызова (1 партия + сводный), выжимки ≤ 400 KB ≈ 0,2 M | ≈ 0,4 |
| итого | | ≈ 15–16 M | ≈ 8,5–9,5 |

Модели (`grep -H '^model:'`): `kaban.md:model: sonnet`, `kaban-doeba.md:model: sonnet`, `mama-kaban.md:model: opus`,
`kaban-svekrov.md:model: opus`, `svinopas.md:model: opus`, `papa-kaban.md:model: fable`. Свой запуск — claude-opus-5-5.

**Вердикт:** ок по бабкам — шаг дешёвый, дорогих позиций нет; ревью и аудит не трогать.

## Правки по ревью

Ревью мамы-кабана и аудит свекрови (2026-10-25): план выполнен, сценарии покрыты.

1. STATIC_MAX = 23680 (замер 23661 + 19), а не «замер + 3 %» по плану: так делались подъёмы с У1 П2, +3 % дали бы
   ≈ 700 токенов запаса. Решение Влада 2026-10-25: оставить 23680.
2. Мелочи мамы — кабану: строка шапки test_static_budget.py про «+ ~3 %» привести к практике; в schema.py
   `"unsupported_action"` — на одну строку с `"wash",`, если укладывается в 100 символов. Перезапись
   `conditions[:]` в hygiene.wash без вони — по маме правка не нужна, не трогаем.
   Сделано кабаном 2026-10-25: шапка — «замер + небольшой запас (раньше +3 %, с У1 П2 — десятки токенов)»;
   schema.py — одна строка (84 символа). ruff по файлам шага чист; 16 E501 в нетронутых шагом файлах — старые.
