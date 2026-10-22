# У0 Реестр услуг (BACKLOG 32)

План — папа-кабан (ниже). Груминг: свинопас ‖ кабан-свекровь, 2026-10-22.

## Решения

Проектировщик, 2026-10-22, окна груминга:
1. Ночлег платный, если в локации есть живой NPC с услугой ночлега; иначе отдых бесплатный (свинопас, вариант А).
2. Лечение у цирюльника и в храме — своя таблица цен (за кость хитов / ПЗ; храм дороже и сильнее).
3. Снятие проклятия в храме — в У0.
4. Нет денег на комнату — решает мастер сюжетно, движок не вмешивается.
5. Класс комнаты — только цена и описание.
6. Услуги NPC — из пака, мастер может назначить на ходу; живые сейвы — разовым скриптом с бэкапом, только с согласия проектировщика.
7. Торг на услуги — да, как в trade.
8. Стрижка/бритьё — в У1.
9. Показ услуг — в `/shop` отдельным блоком.
10. Лимит за сцену — общий, как `ops_per_scene` у trade.
11. Платный короткий отдых (`rest_short`) — в У0.
12. `paid_rest` включить сразу с У0 (отменяет решение 3 R3 «после живого прогона»).
13. Проверка до живого прогона — ответ вне вариантов: «создать свой тестовый мир, где это проверить» (вместо мока «Пьяного дракона» или dusk_academy).
14. `meal` до М5 — только деньги и описание, без эффекта.

Проектировщик, 2026-10-22, по плану папы:
15. Открытый вопрос 1 (проклятий в движке нет) — вариант 3: ввести состояние «проклят» в У0.
16. Р1–Р6 — приняты рекомендации папы (Р1 пак `campaigns/inn_test` в репо; Р2 1к8/5 сп и 2к8+4/2 зм, 4 класса комнат;
    Р3 флаг `haggle:<npc_id>`; Р4 без денег отдых принимается; Р5 скрипт для живых сейвов после живого прогона;
    Р6 формат строки `/shop` как в плане).
17. Р7–Р10 — приняты рекомендации папы (Р7 мастер `curse` после провала броска, проклятие бога — пунктом беклога к
    архитектору; Р8 помеха на проверки и спасброски; Р9 снятие 25 зм; Р10 `/sheet` + строка состояния).
18. «Окей, кабаним» — 2026-10-22. Экономия тестя принята: `/compact` после коммита каждой партии и после каждого
    отчёта ревью. Побочная находка → BACKLOG 147 (проклятие бога на −9).

Проектировщик, 2026-10-22, по ревью П2:
19. Ночлег — одна ночь за оплату (qty = 1, решение кабана подтверждено; рекомендация мамы).
20. Трактирщик отказывает по отношению (≤ −50), у героя есть деньги — `rest long` в этой локации запрещён, отдыхать
    в другом месте; подсказка говорит об этом (против рекомендации мамы «отдых свободен»).
21. Оплата ночлега действует на ночь: оплатил до полуночи, лёг после — оплата в силе (правка `lodging_paid`).
22. Оплата после полуночи (например, в 02:00) действует до утра следующих суток — решение кабана подтверждено
    (рекомендации не было; аудит свекрови, круг 2).
23. Комнату по карману сдаёт только отказывающий хозяин, у согласного она не по карману — «не сдадут», отдыхать в другом
    месте (решение кабана подтверждено; рекомендации не было).
24. Строка статуса показывает все состояния героя, не только «· проклят» (уточнение Р10 б; решение кабана
    подтверждено, рекомендации не было; аудит свекрови П3).

## План (папа-кабан, 2026-10-22)

контур: вне msa; режим: встроить (образец — торговля: `protocol/handlers/trade.py`, `rules/trade.py`,
`[trade.presets]`; план Т5 — docs/plan-trade.md «Т5: план»).

**Задача / проект:** реестр платных услуг NPC (`[services.kinds]`), инструмент `service` по образцу `trade`,
хуки `lodging` / `meal` / `heal` / `rest_short`, платный долгий отдых у трактирщика, показ в `/shop`, услуги в
контексте мастера только у NPC сцены; сейв v11 без новых полей.

**Правило:** было `rest long` всегда свободен (`resources.rest`: только `rest_redundant` / `swap_invalid` /
`prey_invalid`) → станет: при `cfg.services.paid_rest` и живом NPC с услугой-`lodging` в локации героя
`rest long` принимается только после оплаченного ночлега (`service` → флаг `lodging:<hero_id>` = день); без оплаты —
`rejected` «ночлег платный» с подсказкой `service`; нет денег даже на самую дешёвую комнату — отдых разрешён
(Р4). Второе: было торг (`haggle`) только у NPC с `trade` (`trade_pick.npc_problem` → `not_merchant`) → станет
торг и у NPC с `services` (Р3).
**Поведение:** меняется — долгий отдых в локации с трактирщиком; `/shop` (блок услуг); контекст мастера
(`scene_npcs[].services`, ключ `services`); `npc_update`/`npc_create` (поле `services`); новый инструмент `service`.
В локациях без NPC с `lodging` (все живые миры сейчас: `services` у всех `[]`) — ничего не меняется.
**Вне ai-dm:** живые сейвы (`dusk_academy-d3de6c57` у другого человека; `drunk_dragon-*` проектировщика) —
услуги NPC только разовым скриптом с бэкапом по образцу `scripts/migrate_dusk_ferry.py` — решение 6; кому и когда —
вопрос 3. Свой тестовый мир (решение 13) — развилка Р1.

### Разведка (что проверено по коду)

- **Образец trade.** Цена и торг — чистые функции `rules/trade.py` (`buy_quote`, `merchant_buy_quote`,
  `active_haggle`, `apply_haggle`, `haggle_state`); обработчик `handlers/trade.py` (`trade`, `haggle`,
  `short_of_money`, `buy`), проверки NPC — `trade_pick.py` (`scene_problem`, `npc_problem`, `refusal_problem`,
  `merchant_base_problem`); лимит сцены — `SceneState.trades` против `cfg.trade.ops_per_scene`; показ —
  `game/shop_text.py:shop_lines`; контекст — `master/prompt.py:merchant_data`/`trade_data` + `scene_npcs[].merchant`
  (`prompt.py:514`); правила — `narrator_rules.md` раздел «Торговля» (стр. 94–104); регистрация —
  `requests.REQUEST_MODELS`, `schema.MODE_TOOLS["explore"]`, `apply.HANDLERS`; назначение мастером —
  `handlers/world.py:npc_create`/`npc_update` через `make_merchant` с `new_merchant_problem`
  (лимит `scene.merchants_created`, запрет на `key`).
- **Поле `NPC.services: list[str]`** (`state/world.py:104`, m0011) — в сейве и в паке: пак читает NPC той же
  моделью (`campaign/loader.py` → `Pack.npcs: list[NPC]`), значит `services: [..]` в `npcs.yaml` грузится без кода;
  пресеты торговца пака проверяются по конфигу в `loader.py:213–218` — так же проверить id услуг. `merge_new`
  добавляет только новые сущности → живым NPC услуги даст только скрипт (решение 6).
- **Таблица цен.** Ночлег и еда — SRD 5.2 «Food, Drink, and Lodging» (проверено по free rules 2024): комната за
  сутки squalid 7 см / poor 1 сп / modest 5 сп / comfortable 8 сп / wealthy 2 зм / aristocratic 4 зм;
  еда 1 см / 2 см / 1 сп / 2 сп / 3 сп / 6 сп; эль (кружка) 4 см, вино обычное (бутылка) 2 сп. Хранить —
  в `config/defaults.toml` `[services.kinds.<id>]` (образец `[trade.presets]`), `price_cp` в меди. Лечение — SRD цен
  не даёт (Spellcasting Services — 50 зм за заклинание 1-го круга, решение 2 отказалось), таблица своя — там же, Р2.
  В SRD-данных движка (`srd/data`) таблиц расходов нет — вводить их в реестр контента незачем.
- **Проклятия.** В движке проклятия как состояния нет: единственное «проклятие» — помеха при благосклонности бога
  ≤ −6 (`rules/divine.py:209 curse_day_used`, `modifiers/divine_favor.py:15 divine_curse`), она следует из favor и
  снимается только ростом favor (ТЗ 4.2). Заклинаний/предметов с curse в `srd/data` нет (есть только
  `lesser_restoration.yaml`). Решение 3 «снятие проклятия в храме — в У0» снимать нечего → вопрос 1.
- **Долгий отдых.** `resources.rest` → `rests.long_rest` (лечит, ресурсы, двигает часы, `hero.long_rest_end_s`);
  кулдаун — `rest_redundant` (`limits.long_rest_cooldown` 12h). Привязки к локации нет; «в поселении» по решению 1
  = живой NPC с `lodging` в `hero.location_id` (как `merchants_here`/`merchant_ids`).
- **Хранение без новых полей.** Схема v11 не меняется (R8 §5). Состояние, которое нужно У0 сверх `NPC.services`:
  (а) «ночлег оплачен» — до `rest long`; (б) торг с NPC без `TradeProfile`. Оба ложатся в `world.flags`
  (`dict[str, bool|int|str]`, `state/world.py:293`), где движок уже хранит своё под зарезервированными префиксами
  (`rules/auto_flags.py:12 RESERVED_FLAG_PREFIXES`; прецеденты `debt:<hero>`, `danger:<loc>`, `visited:<loc>`,
  `hoard`). Лимит за сцену — общий счётчик `SceneState.trades` (решение 10). Класс комнаты — отдельные виды в
  реестре (решение 5), не поле. Итого: **v11 хватает**, миграции нет.
- **Мок-мир.** `campaigns/test` («Пепел Серой Гавани») — локальный пак проектировщика, в `.gitignore`
  (`campaigns/test/`), мир `saves/test-273aadd1` уже есть; в паке кабак «Ржавый якорь» (Ильва, `trade: general`,
  `key`), Храм Прилива (Сестра Мейра, «исцеление недугов»), локации `docks`/`tide_temple`. Новый мир —
  `ai-dm --new --campaign <id>`. Мок-LLM сценарии — `tests/scenarios/test_trade_scenario.py` (`ScriptedAdapter`,
  `make_app`, мир `vale` + NPC inline). Замер контекста — `make prompt-budget` (`devtools/prompt_budget.py`).

### Модули / файлы / функции

Существующие (grep подтверждён): `handlers/trade.py: trade, haggle, short_of_money`; `handlers/trade_pick.py:
scene_problem, npc_problem, refusal_problem, merchant_base_problem`; `rules/trade.py: buy_quote, active_haggle,
apply_haggle, can_haggle, haggle_state, haggle_dc, haggle_mode, haggle_percent_for, day_of`; `handlers/resources.py:
rest (783), rest_redundant (763), take_holder (519)`; `handlers/world.py: npc_create (63), new_merchant_problem (99),
make_merchant (120), update_problem (345), npc_update (427), merchant_update_problem (458)`; `protocol/requests.py:
Trade, Haggle, Rest, NpcCreate, NpcUpdate, REQUEST_MODELS`; `protocol/schema.py: MODE_TOOLS`; `protocol/apply.py:
HANDLERS`; `protocol/hints.py: merchant_ids, allowed`; `master/prompt.py: merchant_data (157), trade_data (183),
PromptBuilder.state_data (scene_npcs ~508)`; `master/relevance.py: npc_reason_set (29)`; `game/shop_text.py:
merchants_here, shop_lines (87)`; `config/settings.py: TradeConfig (275), RulesConfig (~355)`;
`config/defaults.toml: [trade]`; `campaign/loader.py: check_pack_refs (190, проверка пресетов 213–218)`;
`master/prompts/narrator_rules.md` «Торговля»; `state/scene.py: SceneState.trades`.

Новые: `rules/services.py` — **новая**: `kinds_of(npc, cfg)`, `quote(kind, npc, world, cfg)` (через
`trade_rules.buy_quote(price_cp, attitude, cfg, haggle)`), `haggle_slot(npc, world)` (объект с
`haggle_percent`/`haggle_day`: `npc.trade`, если есть, иначе флаг `haggle:<npc_id>`), `providers_here(world,
location_id)`, `lodging_here(world, location_id)`, `cheapest_lodging_cp(...)`, `LODGING_FLAG = "lodging"`.
`protocol/handlers/services.py` — **новая**: `service(ctx, request)`, `provider_problem` (аналог `npc_problem`
с кодом `no_services`), `service_list` (без сделки, как `category_list`), `apply_effect` по `kind.effect`:
`meal` (деньги + лог), `heal` (`roll_dice(kind.heal, ctx.rng)` × `qty` → `healing.heal`), `lodging` (деньги +
флаг `lodging:<hero_id>` = `day_of(now_s)` + лог «Ночлег оплачен»), `rest_short` (деньги + лог, отдых — `rest short`
мастером). `handlers/resources.py: lodging_unpaid(ctx, request)` — **новая**, в цепочку проверок `rest`.
`requests.py: Service` — **новая** (`npc_id`, `service_id`, `qty: int = 1`, `direction: list|buy` как в `Trade`).
`config/settings.py: ServiceKind, ServicesConfig` — **новые**; `game/shop_text.py: service_lines` — **новая**;
`master/prompt.py: services_data` — **новая**; `scripts/add_services.py` — **новый** (только при Р5 = да).

Образец повторён, не переизобретён: `service` = `trade` с `direction list|buy`, `short_of_money`, `clamped` при
урезании `qty` по деньгам, лимит `scene.trades`, торг через `haggle` с тем же бросанием; `haggle` расширяется
только в `merchant_base_problem`→`npc_problem`: NPC годится, если `trade is not None or services`.

### Конфиг (`[services]`, умолчания — Р2 для чисел лечения)

```toml
[services]
paid_rest = true            # решение 12
[services.kinds.room_poor]        # name = "комната (бедная)", unit = "night", effect = "lodging", price_cp = 10
[services.kinds.room_modest]      # 50
[services.kinds.room_comfortable] # 80
[services.kinds.room_wealthy]     # 200
[services.kinds.meal_poor]        # unit = "meal", effect = "meal", 2
[services.kinds.meal_modest]      # 10
[services.kinds.meal_comfortable] # 20
[services.kinds.ale]              # 4;  wine_common 20
[services.kinds.heal_barber]      # effect = "heal", heal = "1d8", unit = "once", price_cp = 50   (Р2)
[services.kinds.heal_temple]      # effect = "heal", heal = "2d8+4", price_cp = 200               (Р2)
[services.kinds.bed_hour]         # effect = "rest_short", unit = "hour", price_cp = 5  (У1 — проститутка, решение 11)
```
`ServiceKind(extra="forbid")`: `name: str`, `price_cp: int ≥ 0`, `unit: Literal["night","meal","hour","once"]`,
`effect: Literal["lodging","meal","heal","rest_short"]`, `heal: str = ""` (валидатор `parse_dice`, обязателен при
`effect == "heal"`), `description: str = ""` (решение 5 — текст класса комнаты для мастера). Squalid/aristocratic
не вводить (Р2-б). `NPC.services` пака/мастера — id из `kinds`; неизвестный id в паке — ошибка загрузки
(как пресет торговца), у мастера — `Invalid unknown_service` + `allowed(kinds)`.

### Партии

**П1 — реестр, инструмент, показ** (ядро; ответы на вопросы не меняют):
1. `config/settings.py`, `defaults.toml` — `ServiceKind`, `ServicesConfig`, `[services]`; тест загрузки видов.
2. `rules/services.py` — чистые функции цены/торга/поиска поставщиков; `haggle_slot` (при Р3 = флаг).
3. `requests.Service`, `schema.MODE_TOOLS["explore"]` (+ `NON_STRICT` по месту), `apply.HANDLERS["service"]`,
   `hints.provider_ids`; `handlers/services.py`: `list` → позиции NPC с ценами; `buy` → проверки (бой, NPC здесь и
   жив, услуга у NPC, `refuses`, лимит `scene.trades`), `qty` урезается по деньгам (`clamped`), эффекты `meal`,
   `heal`; `trade_pick.npc_problem` — торг и для `services`.
4. `npc_update`/`npc_create`: поле `services: list[str]` (NEUTRAL `[]`; объединение со списком NPC, снятия нет);
   проверка id; без лимита за сцену и без запрета на `key` (умолчание У2 ниже); лог «<NPC> оказывает: …». Хвост 87
   (`npc_update`, `merchant_update_problem`) — мутанты на тронутых строках.
5. `master/prompt.py`: `scene_npcs[].services` (id), ключ `services` (только NPC сцены: `[{npc_id, items:[{id,
   name, price_cp, unit, description}]}, …]`, цены с отношением и торгом) рядом с `trade_data`; `relevance.
   npc_reason_set`: причина `merchant` и при `services` (цель визита, как 132). `narrator_rules.md` — абзац «Услуги»
   в разделе «Торговля» (одним абзацем ради окна). `make prompt-budget` до/после — «замер кэша» в Итог.
6. `game/shop_text.py`: `providers_here` ∪ `merchants_here`; блок «Услуги:» у NPC после ассортимента (у NPC без
   лавки — без кошелька/«Продать»); `NO_MERCHANT` → если нет ни торговцев, ни услуг. Хвост 84 (`shop_lines`).
7. Тестовый мир (Р1) — данные: трактирщик (`room_*`, `meal_*`, `ale`), храм (`heal_temple`), цирюльник
   (`heal_barber`).

**П2 — ночлег и платный отдых:**
1. `handlers/services.py`: эффект `lodging` — деньги, флаг `lodging:<hero_id>` = `day_of(now_s)`, лог
   «Ночлег оплачен: <комната> у <NPC> — <цена>», `signal_to_master`: «затем `rest long` в этом же ходу» (прецедент —
   `rest_redundant`: `until: long_rest` → `rest long` в том же ходу); `rest_short` — деньги + лог + подсказка `rest
   short`. `"lodging"` → в `RESERVED_FLAG_PREFIXES`.
2. `handlers/resources.py: lodging_unpaid` в цепочку `rest`: `kind == "long"` и `cfg.services.paid_rest` и
   `lodging_here(...)` и флаг не на сегодня → если `hero.money_cp >= cheapest_lodging_cp` → `rejected` («ночлег
   платный: `service` <id> у <NPC>, потом `rest long`», `report_tag="rest_unpaid"`), иначе (Р4 = 1) пропустить;
   принятый `rest long` снимает флаг. `rest_redundant` идёт первым (кулдаун важнее оплаты); хвост 113 — мутанты
   `take_holder`/`rest_redundant` на тронутых строках.
3. `narrator_rules.md`: ночлег — два шага, нет денег — сюжетно (решение 4), в глуши отдых свободен.
4. `tests/scenarios/test_services_scenario.py` — мок-сценарий по образцу `test_trade_scenario.py`: «снимаю комнату и
   сплю» → `service room_modest` + `rest long` в одном ходу; WINDOW мока `memory_script.py` перепроверить.
5. (при Р5 = да) `scripts/add_services.py <мир> <npc_id>=<id,id>` по образцу `migrate_dusk_ferry.py` (stdlib, гейт
   схемы 11–12, бэкап слота, идемпотентность) + `docs/migrate-services.md`; запуск — только проектировщик.

Разбиение: П1 без изменения поведения `rest` — отдельное ревью; П2 трогает `rest` (регресс-чувствительно, ЖП3/ЖП4).
Если П1 вырастет до L — стоп-сигнал R4 (образец trade не переиспользован).

### Тестовые сценарии (кабан-доеба, TDD; по образцу `test_apply_trade.py`, `test_apply_haggle.py`, `test_shop_command.py`)

- Конфиг: `[services.kinds]` грузится, `heal` без кости при `effect=heal` → ошибка; `paid_rest` по умолчанию `true`.
- `service list` у NPC с `services=[room_modest, meal_modest]` → позиции с `price_cp` 50/10, без траты лимита и денег.
- `service buy meal_modest qty=3`, деньги 25 → `clamped`, куплено 2, деньги 5, лог «Еда…», `scene.trades` +1.
- `service buy` у NPC без `services` → `Invalid no_services` (+ допустимые id); NPC в другой локации → `npc_absent`;
  в бою → `in_combat`; `attitude ≤ −50` → `rejected`; `scene.trades ≥ ops_per_scene` → `rejected` (общий лимит с `trade`:
  19 сделок `trade` + 1 `service` → 20-я проходит, 21-я нет).
- `heal_barber` при HP 3/10, кость подменена на 5 → HP 8, деньги −50; при полных HP → `rejected` «лечить нечего»
  (без списания); мёртвому — `Invalid`.
- `haggle` у NPC только с `services` (без `trade`) → бросок, `haggle_percent`, цена в `service list` ниже на 10 %;
  второй `haggle` в тот же день → `rejected`; у NPC с `trade` и `services` — один торг на обоих.
- `npc_update services=[room_modest]` → список у NPC, лог; неизвестный id → `Invalid unknown_service`; повтор того
  же id — без дубля; `npc_update services` для `key` NPC — принимается (умолчание У2).
- Контекст: `scene_npcs[grok].services == [...]`; ключ `services` есть только когда NPC сцены с услугами;
  у NPC другой локации — нет; `prompt_budget` статика ≤ +N токенов (N — по факту в Итог).
- `/shop`: без торговцев и услуг — «Здесь никто не торгует»; NPC только с услугами — заголовок, блок «Услуги:»
  с ценами, без «кошелёк торговца»; торговец с услугами — оба блока; `haggle` виден в ценах.
- П2: `rest long` в локации с `lodging`-NPC, флаг нет, деньги 100 → `rejected rest_unpaid`; деньги 5 (< 10) →
  принят (Р4 = 1); `service room_modest` → флаг `lodging:<hero>` = день, деньги −50; затем `rest long` → принят,
  флаг снят, `long_rest_end_s` выставлен; флаг вчерашний → `rejected`; `paid_rest = false` → как раньше; локация без
  `lodging`-NPC → как раньше; `rest_redundant` раньше оплаты (кулдаун) — отказ `rest_repeat`, деньги не списаны.
- Сценарий мок-LLM: ход «снимаю комнату и ложусь» → `service` + `rest long`, деньги −50, HP полные, одна строка
  «Ночлег оплачен» в `turn.lines`.
- Проверка руками: новый мир из тестового пака (Р1) → `/shop` в трактире показывает комнаты и еду; «сплю» без
  оплаты → мастер просит заплатить; «снимаю комнату» → деньги списаны, отдых; в лесу «сплю» → отдых бесплатный;
  храм → лечение за деньги; `/shop` у цирюльника.

### Развилки и риски

**Р1–Р6 приняты по рекомендациям папы (решение 16, 2026-10-22):** Р1 = (2) пак `campaigns/inn_test`; Р2 = (а) 1к8/5 сп,
2к8+4/2 зм, четыре класса комнат; Р3 = (1) флаг `haggle:<npc_id>`; Р4 = (1) без денег отдых принимается; Р5 = (2) скрипт
после живого прогона; Р6 = (1) формат строки как в плане. Ниже — как было поставлено, для истории.

- **Р1 (решение 13) — свой тестовый мир, где проверять до живого прогона.** (1) дополнить локальный пак
  `campaigns/test` (вне git, «Пепел Серой Гавани»): услуги Ильве («Ржавый якорь»: комнаты, еда, эль), Сестре Мейре
  (Храм Прилива: `heal_temple`), новый NPC-цирюльник в `docks`; проектировщик делает `ai-dm --new --campaign test`.
  Дёшево, пак уже есть, мир не живой. Минус: вне репо — ревью не видит, кабан правит файл проектировщика.
  (2) новый пак в репо `campaigns/inn_test` (трактир + храм + цирюльник, 3 локации, 3 NPC, `world.md`) — в git,
  переиспользуется У1 («дописывает данные в мок У0», R4 #18) и будущими прогонами; минус — ещё один пак в
  репо (`vale`, `drunk_dragon`, `dusk_academy` уже есть). (3) только мок-сценарий в тестах, без играбельного мира.
  Рекомендую (2): данные видны конвейеру и останутся У1; (1) — если проектировщик не хочет пака в репо.
  Решает проектировщик.
- **Р2 — таблица лечения (решение 2, числа видны игроку).** (а) `heal_barber` 1к8 за 5 сп, `heal_temple` 2к8+4 за
  2 зм (рекомендую: цирюльник ≈ короткий отдых без траты кости хитов, храм ≈ Лечение ран 2-го круга; против 50 зм
  SRD за каст); (б) цена за ПЗ (1 сп/ПЗ у цирюльника, лечит до полного; храм 5 см/ПЗ, но дороже за «вход»); (в) своя
  сетка. Отдельно: классы комнат — (а) четыре (poor/modest/comfortable/wealthy), (б) все шесть SRD. Рекомендую (а):
  squalid и aristocratic редки в трактире, список короче в контексте.
- **Р3 — торг с NPC без `TradeProfile` (решение 7).** (1) состояние торга во флаге `haggle:<npc_id>` =
  `"<день>:<процент>"` (зарезервированный префикс; прецедент `debt:`/`danger:`), `haggle_slot` отдаёт его как
  профиль; у NPC с лавкой — общий торг с товарами, один в день. (2) торг только у NPC, у кого есть `trade`;
  трактирщик без лавки — цена фиксирована (проще, без флагов, но решение 7 выполняется не везде). (3) поле в
  `NPC` — нельзя до v13. Рекомендую (1). Решает проектировщик.
- **Р4 — `rest long` в трактире при нехватке денег (уточнение решения 4).** (1) отдых принимается, движок не
  вмешивается (сарай/отработка — текст мастера) — так читаю решение 4; (2) отклоняется как и при деньгах, игрок уходит
  за поселение (R3 риск 2). Рекомендую (1) — по букве решения 4; дыра «потратил всё, спи бесплатно» принимается
  сознательно. Решает проектировщик.
- **Р5 — живые сейвы.** (1) в У0 написать `scripts/add_services.py` (общий, параметры — мир и `npc_id=услуги`), запуск
  — проектировщик после прогона тестового мира; (2) отложить до после живого прогона У0 (сейчас `paid_rest`
  включён, но без NPC с `lodging` отдых везде бесплатен — живые миры не ломаются). Рекомендую (2): меньше партия,
  скрипт — отдельной вставкой с бэкапом, когда проектировщик решит, кому из трактирщиков что дать (Грок в
  `drunk_dragon`, чайная в `dusk_academy`).
- **Р6 — показ в `/shop`:** NPC только с услугами — (1) та же команда, заголовок без «кошелёк торговца»
  (рекомендую, решение 9); (2) всегда печатать кошелёк «—». Формат строки услуги: `    комната (скромная) — 5 сп / ночь`
  (единица после цены) — это видимое, подтвердить.
- **Риски.** Окно мока `memory_script.py` (абзац правил + ключ `services`) — перебрать WINDOW, как в Т3/Т5;
  `explore` уже 33 инструмента — `service` без strict (как `trade`), схему проверить `prompt_budget`; ключевой
  трактирщик пака (Ильва `key`) — услуги от пака разрешены как и `trade`; `scene.trades` общий — при 20 сделках
  еда блокируется вместе с покупками (решение 10, принято); мастер может забыть второй шаг `rest long` после оплаты —
  флаг живёт до конца дня, повторная оплата не нужна (`service lodging` при уже стоящем флаге на сегодня →
  `rejected` «ночлег уже оплачен»); `recent_turns` не используем — флаг надёжнее окна памяти.

### Умолчания (внутреннее)

- У1. Имена: `rules/services.py`, `handlers/services.py`, `Service` (`type: "service"`, `direction: list|buy`,
  `service_id`, `qty`), коды `no_services`, `unknown_service`, `rest_unpaid`, `nothing_to_heal`; флаги
  `lodging:<hero_id>` (int день), при Р3 = 1 — `haggle:<npc_id>` (str); префиксы в `RESERVED_FLAG_PREFIXES`.
- У2. `npc_update`/`npc_create` `services`: объединение без дублей, снятия нет (У0 не требует); для `key` NPC
  разрешено (услуги не дают кошелька и ассортимента — злоупотребления, ради которого `new_merchant_problem` запрещает
  `key`, нет); лимита «новых поставщиков за сцену» нет; `trade_kind` и `services` в одном запросе — можно.
- У3. Цена услуги = `buy_quote(price_cp, attitude, cfg, haggle)` — те же коэффициенты отношения и потолок
  `price_mod_cap_percent`, округление вверх; `refuses` — тот же порог `attitude_refuse_at`.
- У4. `heal` лечит только героя (`target` нет); при полных HP — `rejected` без списания; `qty` > 1 — несколько
  бросков, деньги за каждый, урезание по деньгам и по «уже полный» (`clamped`).
- У5. `meal`/`rest_short` — только деньги и лог; события `service_bought` нет (решение Влада по ревью П1).
- У6. Контекст: ключ `services` формируется только для NPC из `scene_npcs` (тест приёмки R4 #17), ≤ 8 позиций на
  NPC; `description` вида — в контекст, в `/shop` — нет.
- У7. Тесты: `tests/unit/rules/test_services.py`, `tests/unit/protocol/test_apply_service.py`,
  `test_apply_rest_lodging.py`, `tests/unit/game/test_shop_services.py`, `tests/unit/master/test_prompt_services.py`,
  `tests/unit/config/test_services_config.py`; mutmut `FUNCS` — по diff партии (`handlers.services:service`,
  `rules.services:quote`, `handlers.resources:lodging_unpaid`, `handlers.world:npc_update`, `shop_text:shop_lines`,
  `prompt:merchant_data`/`services_data`).
- У8. `make prompt-budget` до/после каждой партии — числа в Итог (замер кэша).

### Оценка

M (ROADMAP: 0,95). Две партии; ориентир по Ж3 (M, одна партия, ≈ 1,13 млн токенов конвейера): П1 ≈ 0,8–0,9 млн,
П2 ≈ 0,5–0,6 млн, итого ≈ 1,3–1,5 млн с ревью и мутантами; при Р5 = 1 плюс ≈ 0,2 млн (скрипт + тесты + инструкция).
Данные тестового мира (Р1) — внутри П1.

### Открытые вопросы (первая редакция; вопрос 1 закрыт решением 15, Р1–Р6 — решением 16)

1. **Снятие проклятия в храме (решение 3): снимать нечего** — в движке нет проклятия-состояния (`rules/divine.py:209`,
   `modifiers/divine_favor.py:15` — помеха от favor ≤ −6 снимается только ростом favor). Варианты: (1) исключить из
   У0, завести пункт беклога «проклятия как состояние + снятие в храме» (на реестре У0 это один вид `effect = cure`
   потом); (2) трактовать как подношение: услуга храма поднимает favor бога на +1 за плату — это механика богов (ТЗ 4.2),
   не У0, и ломает «благосклонность — только делами»; (3) ввести состояние «проклят» в У0 — новая механика без источника
   проклятий. Рекомендую (1); разблокирует состав хука `heal`; решает проектировщик. **Блокирующий** для П1 п. 3.
2. Р1–Р4 — выбор проектировщика (см. развилки); до ответа П1 можно начинать с п. 1–3 (конфиг, правила, инструмент
   без чисел лечения — числа подставить по Р2).
3. Р5 — скрипт для живых сейвов в У0 или после прогона; если в У0 — каким NPC каких миров (список от проектировщика).

## Дополнение (папа-кабан, 2026-10-22, по решениям 15–16): проклятие

**Правило:** новое. Состояние `cursed` у героя: помеха на проверки характеристик и спасброски (Р8); накладывает
мастер инструментом `curse` только после непотраченного проваленного броска этого хода (Р7; гейт — как `deadly` в
`resources.damage:65–71`); снимает только услуга храма `effect = "cure"`; отдых, 0 HP и смена дня его не трогают.
**Поведение:** меняется — у героя может появиться состояние «проклят» (контекст мастера, `/sheet`, строка состояния
— Р10); новый инструмент `curse`; в храме — услуга «снять проклятие». **Вне ai-dm:** нет.

### Разведка (что проверено по коду)

- **Хранение без новых полей — есть.** `CreatureState.conditions: list[AppliedCondition]` (`state/creature.py:72`),
  `AppliedCondition.id: str` свободный, `source: str | None`, `expires: Expiry | None` (`creature.py:35–42`);
  в `tests/schema/save_v11.schema.json` (`AppliedCondition`, стр. 225–273) enum по `id` нет → `AppliedCondition(id=
  "cursed", source="master:t<turn_seq>")` — v11 без миграции и без архитектора. Альтернатива `ActiveEffect`
  (`kind`/`params`) хуже: её читают эффекты предметов/заклинаний и `live_effects` по часам, а состояния — конвейер
  бросков и контекст.
- **Карточка состояния — данные.** Реестр грузит `condition` из `srd/data/conditions/*.yaml` (`content/loader.py:36`),
  `ContentObject.source: str = "custom"` (`content/models/common.py:122`) → `cursed.yaml` с `source: custom`
  (не SRD; `test_srd_minimum` проверяет только наличие 15 SRD-состояний, `test_attribution` — файл ATTRIBUTION).
  Побочно: `effects.condition: cursed` у монстра/предмета пройдёт валидацию `loader.py:135` — задел для К/М0п без кода.
- **Эффект — одна строка.** `rules/modifiers/conditions.py: CONDITION_RULES` (таблица «состояние → правила
  преимущества/помехи», образец `poisoned`: `Rule("actor", ("attack", "check"), "disadvantage")`) и `CONDITION_WORDS`
  (подпись в строке броска). `ConditionSource` берёт состояния и у героя, и у существа боя (`creature_of`) → в бою
  работает само. `Modifier` умеет и `flat`/`dice` (вариант «−1к4»), но знак у `dice` не проверен — риск.
- **Кто накладывает — инструмента нет.** В `protocol/requests.py` ни один запрос мастера не ставит состояние (поиск
  `condition` — только `hazard` зоны боя и `cause` смерти); вне боя состояния ставит лишь движок (`0_hp`, `hidden`).
  Монстры ставят состояния атакой (`combat/actions/attack.py:411` по `effects.condition`), но монстров с проклятием в
  `srd/data/monsters` нет. Боги: ТЗ 4.2 «−9 — проклятие / слуги» — в коде на −9 только триггер слуги
  (`rules/divine.py:66 add_servant_trigger`), на −6 помеха раз в день (`divine.py:209`), состояния нет.
- **Снятие.** `rests.long_rest` состояния не трогает (только `remove_exhaustion`), `healing.remove_zero_hp_unconscious`
  — только `0_hp`, `divine.py:117` — только `0_hp` → `cursed` переживает отдых и смену дня без кода. Заклинание
  `lesser_restoration.yaml` без `effects` — не механизировано, `remove_curse` в данных нет; У0 их не трогает.
- **Показ.** Контекст мастера уже отдаёт `hero.conditions` как список id (`master/prompt.py:546`) → мастер увидит
  `cursed` без кода. Игроку состояния героя сейчас не показываются нигде: `game/sheet_text.py` и строка состояния
  `ui/screen.py:52` (`HP x/y · …`) состояний не печатают — Р10.

### Модули / файлы / функции (дополнение)

Существующие: `rules/modifiers/conditions.py: CONDITION_RULES, CONDITION_WORDS` (+ `cursed`); `handlers/resources.py:
damage (59)` — вынести гейт провала в `spent_fail_ref(ctx, ref)` — **новая**, использовать в `damage` и `curse`;
`protocol/requests.py: REQUEST_MODELS`, `schema.MODE_TOOLS["explore"]`/`STRICT_IN_EXPLORE` (`curse` маленький —
можно strict), `apply.HANDLERS`; `master/prompts/narrator_rules.md`; `game/sheet_text.py: sheet_stat_lines (238)` / `game/commands.py: cmd_sheet (169)`
и/или `ui/screen.py: status_line (46)` (Р10); `config/settings.py:
ServiceKind` (`effect` += `"cure"`, поле `cures: list[str] = []`, валидатор: непусто при `cure`); `defaults.toml`
`[services.kinds.uncurse_temple]` (`effect = "cure"`, `cures = ["cursed"]`, `unit = "once"`, цена — Р9);
`handlers/services.py: apply_effect` — ветка `cure`.
Новые: `srd/data/conditions/cursed.yaml` (`id: cursed`, `name: Проклят`, описание по Р8, `source: custom`);
`requests.Curse` (`type: "curse"`, `failed_roll_ref: str`, `cause: str` ≤ 80 знаков — в лог и `source`);
`handlers/resources.py: curse(ctx, request)` — **новая**: герой жив; не проклят (иначе `rejected already_cursed`);
`spent_fail_ref` → иначе `rejected` «проклятие — только после провала броска этого хода» (не `clamped`: частичного
исполнения нет); `AppliedCondition(id="cursed", source=f"master:t{ctx.turn_seq}")`; лог «Проклятие: <cause>»;
`DomainEvent(type="cursed")` в `ctx.events`.

### Развилки (новые; не решены)

- **Р7 — кто накладывает проклятие.** (1) мастер инструментом `curse` с гейтом по проваленному броску этого хода
  (спасбросок/проверка через `saving_throw`/`skill_check`), одно проклятие за раз, только на героя; правило в
  `narrator_rules`: источник — реликвия, ведьма, осквернённое место, ловушка; не чаще раза за главу (просьба в
  правилах, счётчика без поля нет — «одно за раз» ограничивает само). (2) движок: благосклонность бога ≤ −9 →
  `cursed` с `source = "god:<id>"` по ТЗ 4.2; тогда храм против гнева бога бессилен — пока favor ≤ −9, услуга
  отказывает («гнев бога сильнее») или проклятие возвращается на следующей проверке; это правка порогов богов
  (`rules/divine.py`), не У0. (3) оба. Рекомендую (1) в У0; (2) — пунктом беклога «проклятие бога на −9 (ТЗ 4.2)» к
  архитектору: трогает механику богов и мандат R8 на пороги. Решает проектировщик.
- **Р8 — эффект (видимое игроку).** (а) помеха на проверки характеристик и спасброски (`Rule("actor", ("check",
  "save"), "disadvantage")`; как Bestow Curse SRD на все характеристики, без атак) — чувствуется каждый бросок вне боя,
  в бою не калечит; (б) только спасброски — мягко, игрок может не заметить и не пойти в храм; (в) как `poisoned`:
  атаки и проверки; (г) −1к4 к к20 (`Modifier.dice`) — знак у `dice` в конвейере не проверен, риск; (д) нет лечения
  при отдыхе (mummy rot) — трогает `rests`. Рекомендую (а). Решает проектировщик.
- **Р9 — цена снятия в храме (видимое).** (а) 25 зм (2500 см; ≈ 12 × `heal_temple`, по карману с 3–4 уровня —
  `gold_explicit_max_cp_by_level` 3 = 250 зм); (б) 300 зм — SRD Spellcasting Services за заклинание 3-го круга
  (Remove Curse), недостижимо до 6–7 уровня; (в) 10 зм — «просто обряд». Рекомендую (а). Решает проектировщик.
- **Р10 — где игрок видит «проклят» (видимое).** (а) строка «Состояния: проклят» в `/sheet` (общая для всех состояний
  героя — сейчас их не видно вовсе, даже `poisoned`); (б) ещё и в строке состояния TUI/простого режима
  (`ui/screen.py:52`, «· проклят»); (в) только рассказ мастера. Рекомендую (а) + (б): (а) — общая польза, (б) — чтобы
  проклятие не забывалось между сессиями. Решает проектировщик.
- **Риски.** Мастер может звать `curse` «для драмы» без броска — гейт по `failed_roll_ref` отсекает, но мастер может
  сначала запросить спасбросок «по поводу» (как с `deadly`): смягчает правило «не чаще раза за главу» и живой прогон;
  `explore` — 34 инструмента, `prompt_budget` замерить; снятие проклятия у NPC/спутника — нет (только герой; У0 не
  требует); `cursed.yaml` не SRD — пометить `source: custom`, в `ATTRIBUTION.md` не вносить; `test_architecture` —
  `curse` в `resources.py` рядом с `damage`, без новых импортов верхних слоёв.

### Умолчания (внутреннее, дополнение)

- У9. Имена: `cursed` (id состояния), `curse` (инструмент), `uncurse_temple` (вид услуги), `effect = "cure"`,
  `cures: list[str]`; коды `already_cursed`, `curse_needs_fail`, `nothing_to_cure`; `source` состояния
  `master:t<turn_seq>`; событие `cursed`/`cured`.
- У10. `cure` снимает все состояния из `cures` разом за одну цену; если ни одного нет — `rejected nothing_to_cure` без
  списания; `qty` для `cure` всегда 1.
- У11. Пак `inn_test` (Р1 = 2) получает локацию-источник для живой проверки (осквернённая часовня/реликвия с текстом
  триггера «при касании — спасбросок Мудрости, провал — `curse`») и храм с `uncurse_temple`.
- У12. Тесты: `tests/unit/rules/test_modifiers.py` (+ `cursed`), `tests/unit/protocol/test_apply_curse.py`,
  `test_apply_service.py` (ветка `cure`), `tests/unit/content/test_content_loader.py` (`registry.has("condition",
  "cursed")`), `tests/unit/game/test_sheet_conditions.py` (Р10); mutmut `FUNCS` += `handlers.resources:curse`,
  `handlers.resources:spent_fail_ref`, `handlers.resources:damage`.

### Тестовые сценарии (дополнение, TDD)

- `curse` без `failed_roll_ref` / с успешным броском / с уже потраченным (`deadly` в том же ходу) → `rejected
  curse_needs_fail`, состояний нет; с провалом `saving_throw` этого хода → `conditions == [cursed]`, лог «Проклятие: …»,
  `ctx.used_rolls` содержит ref; повторный `curse` → `rejected already_cursed`; герой мёртв → `Invalid hero_dead`.
- Проклятый герой: `skill_check` → помеха с подписью «проклят»; `saving_throw` → помеха; атака в бою — без помехи
  (при Р8 = а); `with_implied` не добавляет лишнего.
- `rest long` / `rest short` / смена дня / 0 HP и подъём → `cursed` остаётся; `remove_zero_hp_unconscious` его не трогает.
- `service buy uncurse_temple` у храма: деньги −2500 (при Р9 = а), состояний нет, лог «Проклятие снято»; не проклят →
  `rejected nothing_to_cure`, деньги целы; у NPC без этой услуги → `no_services`/`unknown_service`.
- Контекст: `hero.conditions == ["cursed"]` в state; `/sheet` — строка «Состояния: проклят» (Р10 а); строка состояния
  «· проклят» (Р10 б); отпечаток схемы v11 не изменился (`test_schema_fingerprint`).
- Сценарий мок-LLM: ход «трогаю алтарь» → `saving_throw` (провал по сиду) + `curse`; ход «иду в храм, плачу» →
  `service uncurse_temple`; деньги и состояния по шагам.
- Руками (мир из `inn_test`): коснуться реликвии → провал → мастер объявляет проклятие, `/sheet` показывает; проверка
  с помехой в строке броска; храм снимает за деньги; без денег — отказ по факту.

### Партии и оценка (пересмотр)

Три партии: **П1** реестр + `service` (`meal`, `heal`) + `npc_update/npc_create services` + контекст/правила + `/shop` +
пак `inn_test` (данные); **П2** ночлег: `service lodging` → флаг → `rest long`, `lodging_unpaid`, `rest_short`,
мок-сценарий; **П3** проклятие: `cursed.yaml` + `CONDITION_RULES` + инструмент `curse` (`spent_fail_ref` из `damage`)
+ услуга `cure`/`uncurse_temple` + показ (Р10) + абзац правил + локация-источник в `inn_test` + мок-сценарий.
П3 последней: не зависит от П2, но добавляет инструмент и правила — отдельное ревью и свой замер `prompt_budget`.
Порядок П2/П3 взаимозаменяем.

Оценка: П1 ≈ 0,8–0,9 млн, П2 ≈ 0,5–0,6 млн, П3 ≈ 0,4–0,5 млн → ≈ 1,7–2,0 млн токенов конвейера; размер шага — M+
(ROADMAP 0,95 задан под У0 без проклятия). Стоп-сигнал R4 «вырос до L — образец trade не переиспользован» здесь не
про переиспользование: рост — решение 15 (новая механика состояния и инструмент), образец trade в П1/П2 соблюдён;
архитектору — отметить в ROADMAP (M+ или П3 отдельной строкой «У0п Проклятие», если так удобнее учёту).

### Открытые вопросы (вторая редакция)

Нет блокирующих. Р7–Р10 — выбор проектировщика до старта П3 (П1 и П2 от них не зависят); если Р7 = (2) или (3) —
стоп и вопрос архитектору (пороги богов, `rules/divine.py`).

## Смета (кабан-тесть, режим 1)

2026-10-22. Цены — тариф metrics.py от 2026-10-17 (https://platform.claude.com/docs/en/about-claude/pricing), страницу
на сегодня не сверял; fable — по ценам Opus. Модели — `model:` из `~/.claude/agents/<роль>.md`. Токены — от последнего
«Итога» (docs/plan-ferry-npcs.md: S, одна партия, 17,3 M, $10,85), пересчитаны на три партии (П3 ≈ 0,6 П1 по
оценке папы): исполнители, ревью и аудит ×2,6, оркестратор ×2,4, папа — план + дополнение «проклятие» ≈ 1,3× Парома;
$ за 1 M — по фактическому соотношению ролей в том «Итоге» (кэш-чтение доминирует). Оценка папы (1,7–2,0 M) — только
исполнители и ревью, без оркестратора — с ней не расходится. Р5 = 2 (решение 16): скрипта живых сейвов в шаге нет.

Платных позиций вне конвейера нет: новых API, подписок, хостинга нет. Рантайм игры: абзацы «Услуги» и «Проклятие» в
narrator_rules.md и схемы `service`/`curse` в `explore` — статичны, в кэше (+≈300–500 токенов по 0,1× цены входа на
ход); ключ `services` — только при NPC с услугами в сцене; на чек хода — доли цента. Замер — `make prompt-budget` (У8).

| Партия | Время |
|---|---|
| груминг + план + дополнение (сделано) | ≈ 60 мин |
| П1 — реестр, `service`, `/shop`, контекст, пак `inn_test` | ≈ 130 мин |
| П2 — ночлег, платный отдых, мок-сценарий | ≈ 100 мин |
| П3 — проклятие, `curse`, `cure`, `/sheet`, мок-сценарий | ≈ 90 мин |
| итого | ≈ 380 мин |

| Роль | Модель | Токены | $ (тариф metrics.py 2026-10-17) |
|---|---|---|---|
| оркестратор | opus | ≈ 26 M | ≈ 11,35 |
| papa-kaban | fable (цены Opus) | ≈ 3,2 M | ≈ 3,75 |
| kaban-svekrov | opus | ≈ 1,2 M | ≈ 1,80 |
| mama-kaban | opus | ≈ 1,2 M | ≈ 1,80 |
| kaban | sonnet | ≈ 3,1 M | ≈ 1,50 |
| kaban-test | opus | ≈ 0,7 M | ≈ 0,85 |
| kaban-doeba | sonnet | ≈ 1,8 M | ≈ 0,75 |
| svinopas | opus | ≈ 0,5 M | ≈ 0,30 |
| итого | | ≈ 38 M | ≈ $22,1 |

Дешевле (выбор за проектировщиком; ревью и аудит не трогаем):
- Оркестратор (половина $): `/compact` сразу после коммита каждой партии и после каждого хэнд-бэка ревью, субагентам —
  пути к файлам; в Пароме лишние +3 M дали три круга ревью и четыре `/compact` посреди партии. Экономия ≈ 4–6 M,
  ≈ $2–2,5. Теряем: ничего, кроме дисциплины.
- П3 отдельным шагом «У0п» (как предлагает папа для учёта) — денег не экономит, только делит смету; новая сессия
  оркестратора для П3 срежет накопленный контекст (≈ 2–3 M, ≈ $1). Теряем: ещё один груминг-заход, если архитектор
  сочтёт нужным.
- kaban и kaban-doeba уже на sonnet; разбор выживших мутантов — на haiku (правило 7 AGENTS.md), если ещё не так.

## Правки по ревью

### П1, круг 1 (мама-кабан ‖ кабан-свекровь, 2026-10-22)

Решения проектировщика (окна 2026-10-22, по рекомендациям свекрови):
- Локация `forest_edge` в паке `inn_test` сверх Р1 — оставить: в П2 на ней проверяется бесплатный отдых вне поселения.
- Оплата `lodging`/`rest_short` уже в П1 (без влияния на отдых) — оставить, П2 идёт сразу следом без живого прогона.
- Лечение: при полных хитах — отказ без списания; при `qty` > 1 — стоп на полных хитах, оплата только сделанного.
- Событие `service_bought` — убрать.
- `paid_rest` без потребителя до П2 (решение 12) — оставить, в allowlist не добавлять; prompt-budget explore +652 токена — цена фичи, в «Итог».

Правки кабану (по ревью мамы):
- `heal_service` → `paid`: причина остановки на полных хитах — «исцелён раньше: оплачено N из M», не «не хватило денег» (обязательно).
- `hints.provider_ids` строится через `rules/services.providers_here` (дубль).
- Ключ вида услуги в ответе `service list` — `id`, как в контексте мастера (план п. 5).
- `campaign/loader.unknown_service_errors` — реестр как у проверки пресета торговца, без `load_rules_config()` на пак.
- smells — сверить с числом до партии (правило нулевого баланса), при превышении снизить.

Сделано (кабан): все пункты; smells до/после 200/200; ruff — новых ошибок нет (16 старых).

### П1, круг 2 (2026-10-22)

Мама — мержить можно, свекровь — чисто. Правка кабану по новому замечанию мамы:
- `clamped` при урезании `qty` по `give_item_max_qty` — причина «лимит количества», не «не хватило денег»
  (`pay_service` и `heal_service`).

Сделано (кабан): `short_cause` — «лимит количества за раз: N», если денег хватило бы на лимит, иначе деньги;
у лечения «исцелён раньше» главнее. smells 200.

Круг 3: мама — мержить, свекровь — чисто.

### П1, проверки перед коммитом (2026-10-22)

- `make cov` — 98 %; 3 падения `test_cli_preset.py` из-за нового героического пака `inn_test` в меню — тесты
  отвязаны от состава паков (доеба). Решение проектировщика: `inn_test` виден в меню и может советоваться
  подсказкой пресета — оставить.
- smells 200 (до партии 200); `make dead` — только `paid_rest` (решение 12, потребитель в П2); ruff — новых нет.
- mutmut: 23 выживших → доеба (sonnet) добил тестами; повторный прогон — 2 эквивалентных
  (`short_cause_3`, `short_cause_7`).

### П2, круг 1 (мама-кабан ‖ кабан-свекровь, 2026-10-22)

Регресс отдыха (short, без NPC-ночлега, порядок проверок, снятие флага) — не найден (мама).
К правке (кабан):
- Решение 20: враждебный NPC с ночлегом при деньгах у героя — отказ `rest long` с подсказкой «здесь не сдадут, отдыхать
  в другом месте»; подсказка `service` называет только NPC, который сдаст (сейчас `options[0]` может быть отказником);
  условие отказа — общей проверкой с `refusal_problem`.
- Решение 21: `lodging_paid` — оплата действует через полночь до утра.
- Перепроверить окно `WINDOW` в `memory_script.py` (план П2 п. 4 и «Риски», свекровь).
- Решение 19 — без правки кода.
Решение оркестратора: порог статического бюджета 22310 → 23090 (замер 22418 + 3 %) по прецеденту П1 — рост П2 в «Итог»
отдельной строкой (свекровь).

Сделано (кабан): `lodging_unpaid` — только комнаты по карману (нет — отдых свободен, Р4); все такие хозяева отказывают
(`trade_rules.refuses`) — `rejected` «комнату не сдадут», подсказка «в другом месте»; иначе подсказка — самый дешёвый из
сдающих. `lodging_paid(world, hero_id, cfg)` — оплата до `cfg.time.morning_hour` (6:00) следующих суток; оплата в 02:00
тоже до 6:00 следующих суток (решение кабана, ночь и день не различаются); нецелый флаг — неоплата. `WINDOW`
(`MEMORY_CONTEXT_CAP`) — сценарии памяти проходят, не менялся. Доеба: 7 тестов приведены, новые на решения 20–21;
318 passed.

### П2, круг 2 (мама-кабан ‖ кабан-свекровь, 2026-10-22)

Мама: замечания круга 1 закрыты, регресса нет — можно мержить. Свекровь: правки в пределах решений 19–21, порог бюджета
уместен; два краевых решения кабана вынесены проектировщику — решения 22–23, код не меняется. Мелочи мамы (текст «на
сегодня уже оплачен» → «на эту ночь», имя `options` → `affordable`) — без правки, чтобы не открывать круг 3 (решение
оркестратора); в беклог не выносятся.

### П2, проверки перед коммитом (2026-10-22)

- `make cov` — 98,02 %, 20752 passed; smells 200 (до партии 200); `make dead` чист; ruff — новых нет.
- mutmut по `lodging_here`, `lodging_paid`, `pay_service`, `lodging_unpaid`, `rest`, `rest_redundant`: 67 выживших; 7 на
  новых строках (тексты сигналов) — доеба (sonnet) добил тестами; 60 на старых строках `rest`/`rest_redundant` →
  BACKLOG 148.
- Расход П2: kaban 82k / 4,6 мин + правки 89k; doeba 64k / 3,6 мин + правки 77k; мама 22k + круг 2 29k; свекровь 45k +
  круг 2 54k; doeba-мутанты (sonnet) 35k / 1,3 мин. Статический бюджет промпта: порог 22310 → 23090 (замер 22418) —
  рост П2.

### П3, круг 1 (мама-кабан ‖ кабан-свекровь, 2026-10-22)

- Мама: план дополнения выполнен, правок кода нет. Заметки без правки: тексты `cure_service` под один вид `cure` —
  учесть при новых; `curse` не в `STRICT_IN_EXPLORE` (план разрешал), бюджет промпта замерен — 22849 при пороге 23090.
- Свекровь: выхода за план нет; одно решение за пользователя — `status_line` выводит все состояния → решение 24
  (подтверждено). Переделка подсчёта в `test_srd_minimum` обоснована.
- Код после ревью не менялся — круга 2 нет.

### П3, проверки перед коммитом (2026-10-22)

- `make cov` — 98 %, 20859 passed; smells 199 (до партии 200); `make dead` чист; ruff — 16 старых E501, новых нет.
- mutmut по `curse`, `spent_fail_ref`, `damage`, `cure_service`, `service`, `condition_names`, `cmd_sheet`, `status_line`:
  94 выживших. На новых строках — тексты отказов (шум) и `apply_events(None, …)` (эквивалентен: `cursed`/`cured` нет в
  `FLAG_BY_EVENT`); тестов не добавлено. 61 на старых строках `damage`/`cmd_sheet` → BACKLOG 149.
- Расход П3: kaban 107k / 19,5 мин; doeba 131k / 14 мин; мама 43k / 1,6 мин; свекровь 42k / 0,7 мин; doeba-мутанты
  (sonnet) 37k / 1,7 мин. Бюджет промпта explore: 22849 при пороге 23090.
