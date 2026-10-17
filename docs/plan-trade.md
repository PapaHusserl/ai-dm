# Партия «Торговля» (BACKLOG 23) — план

Папа-кабан, 2026-10-07, на утверждение. Код не меняется до аппрува.

**Задача:** герой покупает и продаёт предметы у NPC-торговца в своей локации. Цену считает движок по цене
экземпляра (`InventoryEntry.cost_cp`) и коэффициентам конфига. Мастер только вызывает инструмент
`trade` и пересказывает результат.

## 0. Что уже есть (опора)
- `rules/money.py`: `add_money`, `spend_money` (`NotEnoughMoney`), `format_cp`; `HeroState.money_cp`.
- `rules/inventory.py`: `add_item(..., cost_cp=, quality=)`, `remove_item(..., cost_cp=None|N, quality=)`
  (None снимает с самых дешёвых стеков), `count_item`, `dearest_cost`, `entry_name` (качество приставкой), `find_item`.
- `protocol/handlers/resources.py`: `give_item` (rarity cap `loot.rarity_exceeds_cap`, `give_item_max_qty`,
  `clamped(...)`, событие `item_gained`), `take_item` (`TAKE_WORDS`), `gold` (`gold_explicit_max_cp_by_level`).
- `rules/custom_items.py`: `hand_over(world, id, ItemHolder)`, `recover`; `ItemHolder(kind="npc", ref, label,
  location_id, since_s, qty, cost_cp)` уже поддерживает держателя-NPC (В13).
- `state/world.py::NPC` (`location_id`, `status`, `attitude`, `means`, `tags`, `origin`), пак `npcs.yaml`
  (в фикстуре mini: Мара, `means: [товары]`), `npc_create`/`npc_update` в `protocol/handlers/world.py`.
- Контекст мастера `master/prompt.py`: `inventory_data` (с `cost_cp`/`quality`), `scene_npcs`, `items_trail_data`.
- `/inv` — `game/sheet_text.py::inv_lines` (цена сейчас только у сюжетных, `world_item_text`); TUI-модалка
  справочных команд `ui/tui/modals.py`; простой режим — `ui/screen.py::reply_blocks/gains_lines` («Получено»).
- Сейв v6, отпечаток `tests/schema/save_v6.schema.json`; правило теста-отпечатка: любое изменение схемы → +1 версия.

## 1. Модель торговца (В-Т1)
**Рек.: торговец — свойство NPC, а не локации.** Поле `NPC.trade: TradeProfile | None = None` (`state/world.py`):
- `kind: str` — пресет ассортимента из конфига (`general`, `smith`, `armorer`, `alchemist`, `fence`);
- `purse_cp: int` — деньги торговца на скупку (лимит продаж героя); `restock_at_s: int` — когда пополнится;
- `stock: list[InventoryEntry]` — купленное у героя (перепродаётся по цене экземпляра) — сюда же идут проданные
  SRD-трофеи; сюжетные (`custom_*`) в `stock` не кладутся — у них держатель (раздел 4).
Ассортимент SRD **не хранится** в сейве: вычисляется из пресета (категории + предел редкости) по реестру —
бесконечный запас обычных товаров (как в SRD: «всё из Equipment есть в городе»). Локация — только место:
торговать можно с торговцем в `hero.location_id`. Магазин-локация без NPC — не нужен (NPC-«лавочник» безымянный).

Пресеты `config/defaults.toml [trade.presets.<kind>]`: `categories` (weapon/armor/ammo/gear/consumable/clothing),
`magic: bool` (по умолчанию false), `purse_cp` (общий 5000, кузнец 10000, скупщик 3000), `buys` (что скупает:
категории; скупщик `fence` — всё, включая краденое и ценности).

Кто торговец:
- пак: `npcs.yaml` поле `trade: {kind: general}` (Мара в фикстуре mini; в паке кампании — разметить торговцев);
- мастер: `npc_create` и `npc_update` получают параметр `trade_kind` (`"none"` = не менять/нет), лимит
  `[trade].new_merchants_per_scene = 1` (счётчик `SceneState.merchants_created`); ключевого NPC пака мастер в
  торговцы не превращает (rejected) — только пак.

## 2. Цены (rules/trade.py, чистые функции)
- **Покупка SRD** из ассортимента: `buy_price = ceil(item.cost_cp * buy_factor)`, `buy_factor = 1.0`; экземпляр
  кладётся с `cost_cp = item.cost_cp`, `quality=None` (новое).
- **Покупка из `stock`** (перепродажа): `ceil(entry.cost_cp * buy_factor)`, качество сохраняется.
- **Продажа:** `sell_price = floor(entry.cost_cp * sell_factor)` за штуку, `sell_factor = 0.5` (SRD 5.2:
  «продать снаряжение — за полцены»); трофеи — уже уценены качеством (`trophy_cost`), второй раз не режем сверх 0.5.
  «Ценности по полной цене» отменено (решение проектировщика): ценности — как все. Предмет с ценой 0 → продажа
  `rejected` «ничего не стоит».
- **Инвариант цен (все категории):** покупка героем при макс. скидке (`buy_factor × (1 − price_mod_cap_percent/100)`,
  потолок 20%) ≥ лучшая продажа героем (`max(sell_factor, attitude_good_sell_factor)`) × `trade.min_margin` (1.3).
  Валидатор `TradeConfig` проверяет худший случай; дефолты: 0.8 ≥ 0.6 × 1.3 = 0.78. Если торг начнёт влиять на
  продажу — включить это в худший случай. Также: `attitude_refuse_at < attitude_good_from`, `attitude_good_sell_factor
  ≥ sell_factor`, `attitude_good_buy_factor ≤ buy_factor`.
- **Отношение NPC (В-Т3):** модификатор от `attitude` — рек. простая ступень: `attitude ≥ 50` → покупка ×0.9,
  продажа ×0.6; `attitude ≤ -50` → торговец отказывает (`rejected`). Торг броском — не в этой партии.
- Округление в пользу торговца; итог через `format_cp`.
- Функции: `assortment(registry, preset, level, cfg) -> list[(id, price)]`, `buy_quote`, `sell_quote`,
  `restock(npc, now_s, cfg)` (ленивое: при обращении, если `now_s ≥ restock_at_s` → `purse_cp = preset.purse_cp`,
  `restock_at_s = now_s + 7d`; `stock` не чистится — рек., В-Т4).

## 3. Протокол: один инструмент `trade` (В-Т2)
`protocol/requests.py::Trade(Request)`: `type: Literal["trade"]`, `npc_id`, `direction: Literal["buy","sell"]`,
`item_id`, `qty`, `quality: Literal["junk","worn","used","new","any"] = "any"` (какой стек; NEUTRAL "any").
**Цену мастер не передаёт** — её считает движок (защита от «продам за 1000 зм»).
Регистрация: `protocol/apply.py` (`"trade": trade.trade`), `protocol/schema.py` (перечень), новый модуль
`protocol/handlers/trade.py` (по образцу `loot_gear.py`, чтобы не раздувать `resources.py`).

Обработчик `trade(ctx, request)`:
1. `active_combat` есть → Invalid `in_combat`; NPC не найден / не `alive` / не в `hero.location_id` →
   Invalid `unknown_npc|npc_absent` (+ `allowed(...)` торговцев сцены); `npc.trade is None` → Invalid `not_merchant`;
   `qty < 1` → `bad_amount`; `attitude ≤ hostile` → rejected «отказывается торговать».
2. `restock(npc, now)`.
3. **buy:** id из ассортимента (пресет+реестр) или из `stock`; иначе Invalid `not_sold` + список (до 20 id).
   Магический — только при `preset.magic` и не выше `rarity_exceeds_cap` уровня героя. `qty ≤ give_item_max_qty`.
   Денег мало → урезать qty до доступного (clamped), 0 → rejected «не хватает денег: нужно X, есть Y».
   `spend_money`, `add_item(cost_cp=экземпляра)`, при покупке из stock — `remove` из stock; если `item_id` — сюжетный
   с `holder.ref == npc_id` → `recover` и `add_item(cost_cp=holder.cost_cp)` (выкуп у торговца, В13).
   Лог: «Куплено: <имя> ×N за <цена>». Событие `item_gained`.
4. **sell:** стеки героя с `item_id` (+ `quality`), **кроме надетого экземпляра** (если надет и стек единственный —
   rejected «сначала сними»); выбор стека — самый дорогой (выгодно герою, детерминированно). Категория не в `buys`
   пресета → rejected «<торговец> такое не скупает». qty урезается до наличия и до `purse_cp // price`
   (clamped «у торговца не хватает денег»). `remove_item(cost_cp=стека)`, `add_money`, `purse_cp -= сумма`;
   SRD → `stock.append/merge`; сюжетный → `hand_over(kind="npc", ref=npc_id, label=npc.name,
   location_id=npc.location_id, since_s=now, qty, cost_cp)`. Лог: «Продано: <имя> ×N за <сумма>».
   Событие `item_sold` (новый тип DomainEvent, без реакции world_sim; для журнала).
5. Результат `{direction, item_id, qty, price_cp, total_cp, money_cp, purse_cp}`.

**Лимиты против злоупотреблений LLM:**
- цена только движком; кошелёк торговца ограничивает продажу; ступень отношения ограничена ±10%;
- торговец только в локации героя и не в бою; перепродажа купленного у торговца — с убытком (1.0 → 0.5),
  арбитраж невозможен: инвариант цен с маржой 1.3 проверяется валидатором конфига;
- `[trade].ops_per_scene = 20` (счётчик `SceneState.trades`), сверх — rejected;
- новые торговцы мастером — 1 за сцену, ключевые NPC — нет;
- `gold` explicit по-прежнему капится — «торговля без trade» (мастер дал золото за проданное) запрещается правилом
  narrator_rules и подсказкой отказа.
- `take_item why=given` при торговце в сцене — не блокировать (подарок возможен), но рек. подсказка в правилах.

## 4. Квестовые предметы (В13)
Продажа сюжетного: держатель = NPC-торговец (`hand_over`), предмет появляется в `lost_items` контекста мастера
(как «у торговца Мары, рынок, с ...»). Выкуп — `trade buy item_id=custom_N` у того же NPC по `holder.cost_cp ×
buy_factor`; у другого NPC — Invalid. Ценность квестового с `cost_cp = 0` продать нельзя (rejected), но «отдать»
торговцу — `take_item why=given` (по-прежнему без держателя; В-Т6 — добавить `holder_npc_id` в take_item).

## 5. Показ
- **/inv** (pV-review п.3): у **каждой** строки с `cost_cp > 0` — цена экземпляра: «Поношенный скимитар x2 — 1 зм»
  (оценка за штуку, рек.: полная цена экземпляра, не цена продажи — В-Т5). `inv_lines`: для не-сюжетных добавить
  `format_cp(entry.cost_cp)` в хвост после эффектов.
- **/shop** (новая команда вне хода, не тратит время, `game/commands.py::COMMANDS`, `ui/tui/strings.py`):
  торговцы локации героя → ассортимент с ценами (группы как в /inv, до 40 строк), stock торговца, кошелёк, и
  «Продать: <ваши предметы> — <цена продажи>». Без торговца — «Здесь никто не торгует». TUI — та же модалка
  справочных команд (`ui/tui/modals.py`); простой режим — строки как у /inv.
- **Лента хода:** строки лога «Куплено/Продано» уже идут блоками-заметками; `gains_lines` (простой режим и TUI)
  показывают прирост — при продаже «Деньги: +X» появится сама; рек. добавить «Потрачено: −X» при уменьшении денег
  (`loot_snapshot` уже хранит money_before) — чтобы покупка была видна в «Получено» (В-Т7).
- Статус-строка — без изменений.

## 6. Контекст мастера и narrator_rules
- `scene_npcs[i]["merchant"] = kind` у торговцев.
- Новый ключ `trade` (только если в сцене есть торговец, `items_trail_data`-стиль, непустой):
  `{npc_id, kind, purse_cp, sell_factor, buy: [{item_id, price_cp}] (до 25, сначала stock, затем дешёвое по
  категориям пресета), sells_hint: "цена продажи = cost_cp из inventory × sell_factor"}`. Ассортимент режется
  по бюджету контекста; полный список — в ответе Invalid `not_sold`.
- `narrator_rules.md` раздел «Торговля»: купить/продать — только `trade` (не `gold` + `give_item`/`take_item`);
  цену не называй до ответа движка, пересказывай `total_cp`; торговец только из `scene_npcs` с `merchant`;
  отказ/урезание — опиши по факту (нет денег, не скупает); проданная сюжетная вещь остаётся у торговца и её можно
  выкупить; «торговец» среди `means` без `merchant` — сначала `npc_update trade_kind`.
- `protocol/hints.py`: подсказки для `not_merchant`/`not_sold`.

## 7. Сейв: миграция v7 (В-Т8)
Новые поля меняют `SaveBundle` (`NPC.trade`, `SceneState.trades/merchants_created`) → по правилу теста-отпечатка
**нужна v7**: `CURRENT_SCHEMA_VERSION = 7`, `persistence/migrations/m0007_v6_to_v7.py` — аддитивная (поля с
умолчаниями; NPC пака, у которых в новом паке есть `trade`, — подхватываются при наложении пака? нет:
мир в сейве — источник истины; рек. миграция проставляет `trade` NPC сейва по id из пака через
`MigrationContext.npc_trade: dict[id, kind]`, как `item_cost` в v6), `tests/schema/save_v7.schema.json`, фикстура v6.

## Вопросы к Т1
- Категория `Item.category == ""` (снаряжение): в `TradeCategory` её нет; решить в Т1, считать ли её `gear` (рек.: да).

## Партии
- **Т0 (модель + конфиг + миграция):** `TradeProfile`, `NPC.trade`, счётчики сцены, `[trade]` в
  `config/defaults.toml` + `TradeConfig` в `config/settings.py` (валидатор инварианта цен, пресеты),
  пак `trade:` в загрузчике, m0007 + отпечаток v7.
- **Т1 (правила):** `rules/trade.py` — ассортимент, котировки, restock, ступень отношения. Чистые функции.
- **Т2 (протокол):** `Trade`, `protocol/handlers/trade.py`, `trade_kind` в `npc_create/npc_update`, события,
  apply/schema/hints, квестовые (hand_over/recover).
- **Т3 (мастер):** `scene_npcs.merchant`, ключ `trade`, narrator_rules, мок-LLM сценарий devtools.
- **Т4 (показ):** /inv цены, /shop (TUI + простой), «Потрачено» в gains.
Ревью мамы-кабана и мутации — на каждую партию.

## Тесты (TDD, писать первыми)
Т0: v6-фикстура → v7: у всех NPC `trade=None`, сцена `trades=0`; NPC пака с `trade` в паке → получил профиль;
отпечаток v7; конфиг, нарушающий инвариант цен → ошибка загрузки; неизвестный пресет у NPC пака → ошибка пака.
Т1:
- `assortment(general)` содержит верёвку, не содержит магию; `smith` — оружие/доспехи, не зелья.
- buy длинный меч 1500 мм → 1500; sell длинный меч `cost_cp=1500` → 750; поношенный скимитар 100 → 50;
  `valuable` 5000 → 5000; цена 1 мм ×0.5 → 0 → «ничего не стоит».
- attitude 60 → покупка ×0.9 (округление вверх), продажа ×0.6; attitude −60 → отказ.
- restock: `now < restock_at_s` — кошелёк прежний; после — полный, `restock_at_s` сдвинут на 7д.
Т2 (обработчик):
- торговец не в локации героя → Invalid `npc_absent`; NPC без trade → `not_merchant`; в бою → `in_combat`;
  мёртвый торговец → Invalid.
- buy: денег 1000, верёвка 100 ×20 → куплено 10 (clamped), деньги 0, в инвентаре 10 шт. `cost_cp=100`;
  денег 0 → rejected, инвентарь не изменён.
- buy магического у `general` → `not_sold`; у `alchemist` выше предела редкости → rejected.
- sell: два стека скимитара (1000 и 100) → продаётся дорогой первым; надетый единственный → rejected;
  надетый + второй стек → продаётся ненадетый.
- sell сверх кошелька: кошелёк 300, цена 750 → rejected; кошелёк 1600, 3 меча → продано 2 (clamped).
- sell SRD → появился в `stock` с исходной `cost_cp/quality`; buy из stock → цена по экземпляру, stock уменьшился.
- sell квестового `custom_1` → у героя нет, `holder.kind="npc", ref=mara, cost_cp` сохранена, в `lost_items`;
  buy `custom_1` у mara → вернулся с той же ценой, holder=None; buy `custom_1` у другого NPC → Invalid.
- sell предмета с `cost_cp=0` → rejected; категория не в `buys` → rejected.
- `ops_per_scene` превышен → rejected; `trade_kind` у ключевого NPC от мастера → rejected; второй новый торговец
  за сцену → rejected.
- Запрос с лишним полем `price` → Invalid по схеме (цена не задаётся мастером).
Т3: контекст — `scene_npcs` с `merchant`; ключ `trade` есть только при торговце в сцене, ≤ 25 позиций, stock первым;
без торговца ключа нет. Мок-сценарий: «продаю трофеи Маре» → `trade sell` ×2, деньги выросли, лог «Продано».
Т4: `/inv` — «Поношенный скимитар — 1 зм», у предмета без цены хвоста нет; `/shop` без торговца — сообщение;
с торговцем — ассортимент и «Продать»; простой режим после покупки — «Потрачено: −1 зм» и «Получено: Верёвка ×1».

## Риски
- Надетый экземпляр при продаже считается самым дорогим стеком предмета (экипировка не помнит свой стек) — эвристика
  (`trade.py::sellable_stacks`); при равной цене стеков разного качества выбор условный.
- Раздувание контекста ассортиментом — кап 25 и только при торговце в сцене.
- Мастер обходит `trade` через `gold`+`take_item` — правило narrator_rules + кап `gold explicit`; полностью не закрыть
  (рек.: наблюдать по журналу, при повторении — `rejected` у `take_item why=given` при торговце в сцене).
- Экономика: трофеи по 0.5 от уже уценённой цены — дешёвые; если игроку покажется мало — крутить `sell_factor` конфигом.
- Бесконечный ассортимент SRD — нереалистично для деревни; смягчение — пресеты по типу торговца.
- Надетый экземпляр определяется по `dearest_cost` (как в /inv) — при равной цене двух стеков разного качества
  возможна неоднозначность; тест на это.
- Миграция v7 требует данных пака (как v6 реестра) — тот же путь `MigrationContext`.

## Вопросы проектировщику (с рекомендацией)
- **В-Т1** Торговец — свойство NPC (`NPC.trade`) или локации? Рек.: NPC (держатель квестовых = NPC, отношение влияет).
- **В-Т2** Один инструмент `trade` (buy/sell) или два? Рек.: один, цену мастер не передаёт.
- **В-Т3** Влияние отношения на цену и торг броском Убеждения? Рек.: ступень по attitude (±10%) сейчас; торг броском
  — отдельной вставкой (по образцу parley).
- **В-Т4** Ассортимент: бесконечный по пресету или конечный склад? Рек.: бесконечный SRD по пресету + конечный
  `stock` купленного у героя; кошелёк торговца пополняется раз в 7 дней.
- **В-Т5** /inv: показывать полную цену экземпляра или цену продажи? Рек.: полную (оценка), цену продажи — в /shop.
- **В-Т6** `take_item` с `holder_npc_id` (подарил квестовое NPC) — сейчас? Рек.: да, дёшево, в Т2.
- **В-Т7** Показывать траты («Потрачено: −X») в блоке «Получено»? Рек.: да.
- **В-Т8** Миграция v7 с проставлением `trade` из пака в старые сейвы? Рек.: да (иначе в старых сейвах торговцев нет,
  пока мастер не назначит).
- **В-Т9** Продажа краденого/квестового обычному торговцу — разрешать всем или только `fence`? Рек.: квестовые
  принимают все (держатель = NPC), «краденое» как понятие не вводить в этой партии.

## Ответы проектировщика (2026-10-07)
- В-Т1 — NPC. В-Т2 — по рек. (один `trade`, цена движком). В-Т3 — ступень ±10% по рек.; торг Убеждением — вопрос
  проектировщика «почему позже» (ответ оркестратора ниже, решение ждёт). В-Т4 — по рек. В-Т5 — по рек.
- В-Т6 — да (`holder_npc_id` в take_item, партия Т2). В-Т7 — да. В-Т8 — да. В-Т9 — да.
- В-Т3 доп. — РЕШЕНО: торг Убеждением включить партией **Т5** (после Т4).

## Партия Т5: торг Убеждением (набросок оркестратора, детали — папа-кабан перед Т5)
- Мастер запрашивает проверку Убеждения (механика check_request, как в переговорах) с пометкой торга у NPC-торговца;
  результат пишется в TradeProfile (модификатор цены у этого торговца до конца дня): успех −10%, сильный успех −20%,
  провал +10% (числа — в `[trade]` конфига, подтвердить у проектировщика перед Т5).
- Не больше одного торга с торговцем в игровой день (защита от перебросов); модификатор складывается со ступенью
  отношения, итог ограничен потолком конфига; перепродажа в плюс по-прежнему невозможна (валидатор).
- narrator_rules: когда предлагать торг; без броска цену не менять.
- Поля в TradeProfile — сразу в Т0 (одна миграция v7).

## Т1: API (`src/ai_dm/rules/trade.py`, чистые функции; `cfg` = `RulesConfig`)
- `DAY_S = 86400`.
- `item_category(kind, model) -> TradeCategory | None`: `kind` — "weapon"/"armor"/"item". weapon→"weapon", armor→"armor";
  item: `ammo_for` непуст→"ammo"; `category` ""→"gear" (решение), consumable/clothing/gear/valuable как есть;
  "quest"→None (не торгуется обычным путём).
- `merchant_sells(kind, model, preset, level, cfg) -> bool`: категория в `preset.categories`; `cost_cp > 0`;
  магический (`item.magic`) — только при `preset.magic` и не `rarity_exceeds_cap(item, level, cfg)`.
- `merchant_buys(kind, model, preset) -> bool`: категория (не None) в `preset.buys`.
- `refuses(attitude, cfg) -> bool`: `attitude <= trade.attitude_refuse_at`.
- `buy_factor(attitude, cfg) -> float`, `sell_factor(attitude, cfg) -> float`: при `attitude >= attitude_good_from` —
  `attitude_good_*`, иначе базовые.
- `buy_quote(cost_cp, attitude, cfg) -> int`: `ceil(cost_cp * buy_factor)` за штуку (SRD и из stock одинаково;
  вычисление через Fraction, без ошибок float).
- `sell_quote(cost_cp, attitude, cfg) -> int`: `floor(cost_cp * sell_factor)` за штуку; 0 = «ничего не стоит».
- `assortment(registry, preset, level, cfg) -> list[tuple[str, int]]`: `(id, базовая цена покупки)` без учёта отношения
  (`ceil(cost_cp * trade.buy_factor)`); порядок: weapon, armor, item, внутри — по id; только `merchant_sells`.
- `restock(profile, now_s, cfg) -> bool`: ленивое; при `now_s >= profile.restock_at_s`: `purse_cp = presets[kind].purse_cp`,
  `restock_at_s = now_s + restock_days * DAY_S`, `stock` не трогает; возвращает True, если пополнил.
  Неизвестный `profile.kind` — KeyError.
Отказ (`refuses`) сам quote-функции не проверяют — это делает вызывающий (обработчик Т2).

### Т1: заметки для Т2 (ревью Т1)
- Сюжетное (category quest): продажа — мимо `merchant_buys` (принимают все, В-Т9), цена `sell_quote(custom.cost_cp)`;
  выкуп — `buy_quote(holder.cost_cp)` только у `holder.ref == npc_id`.
- `sell_quote == 0` → rejected «ничего не стоит» ДО `purse_cp // price` (иначе деление на ноль).
- Правило контента: предмет с `effects` обязан иметь `category` (иначе /inv и торговля разойдутся) — тест на пак в Т2.
- `restock` с неизвестным `kind` → KeyError (пресет удалили из конфига при живом сейве) — риск, принят.

## Т5: план (папа-кабан, 2026-10-07)

**Задача:** торг Убеждением с NPC-торговцем: отдельный инструмент `haggle`, движок сам считает СЛ и бросает,
исход пишется в `TradeProfile.haggle_percent/haggle_day` (до конца игрового дня), поправка входит в котировки
покупки (`trade`, контекст мастера, `/shop`) с потолком `price_mod_cap_percent`; сейв v7 не меняется.

### Решения (почему так)
- **Отдельный инструмент `haggle`, а не `skill_check` с пометкой.** `skill_check` даёт мастеру выбрать `category`
  (СЛ) — прямой путь к злоупотреблению (very_easy → −20%). Как в parley: СЛ и режим броска считает движок
  (`haggle_dc`), мастер передаёт только `npc_id`. Бросок — тот же `rules.checks.skill_check(..., dc=...)` +
  `ctx.add_roll` (как `protocol/handlers/checks.roll_decision`), т.е. благосклонность богов/перебросы работают.
- **Только покупка героем** (рек., В-Т5-1): поправка торга меняет `buy_quote`, `sell_quote` не трогает. Тогда
  инвариант маржи (валидатор `TradeConfig.check_no_arbitrage`: `buy_factor*(1-cap) >= max(sell)*min_margin`,
  0.8 ≥ 0.78) остаётся верным без изменений: итоговый коэффициент покупки зажимается снизу ровно
  `buy_factor*(100-cap)/100`.
- **Сложение с отношением — по коэффициентам, через Fraction:** `f = buy_factor(attitude) * (100+haggle)/100`,
  затем `clamp(f, buy_factor*(100-cap)/100, buy_factor*(100+cap)/100)`. Дефолты: хорошее отношение 0.9 × 0.8 = 0.72
  → зажим 0.80; провал при обычном 1.0 × 1.1 = 1.10.
- **Срок — игровой день** `day_of(now_s) = now_s // DAY_S` (как `rules/divine.day_of`, сутки от 0 часов).
  Поправка активна только при `haggle_day == today`; на следующий день гаснет лениво (без сброса полей, без тиков).
- **Один торг с торговцем в день, независимо от исхода** (провал тоже фиксирует +10% на день) — главная защита
  от перебросов. Отдельный счётчик за сцену НЕ вводим (потребовал бы поле в `SceneState` = изменение сейва);
  достаточно «раз в день на торговца» + лимит назначения новых торговцев за сцену (уже есть, Т2).
- **Сейв v7 не меняется:** `haggle_percent: int = 0`, `haggle_day: int | None = None` заложены в Т0. Новые
  только поля конфига (`TradeConfig`), это не сейв.

### Затронутые модули/файлы
- `src/ai_dm/config/settings.py` (`TradeConfig`), `src/ai_dm/config/defaults.toml` (`[trade]`)
- `src/ai_dm/rules/trade.py` (новые чистые функции, сигнатура `buy_quote`)
- `src/ai_dm/protocol/requests.py` (новый `Haggle`, реестр типов стр. ~636), `src/ai_dm/protocol/schema.py`
  (список инструментов вне боя), `src/ai_dm/protocol/apply.py` (`"haggle": trade.haggle`)
- `src/ai_dm/protocol/handlers/trade.py` (новый `haggle`; котировки `buy`/`category_list` с торгом),
  `src/ai_dm/protocol/handlers/trade_pick.py` (вынести общую часть `merchant_problem`)
- `src/ai_dm/master/prompt.py` (`merchant_data`: цены с торгом + поле `haggle`)
- `src/ai_dm/master/prompts/narrator_rules.md` (раздел «Торговля»)
- `src/ai_dm/game/shop_text.py` (`sale_rows` с торгом, строка торга в заголовке торговца)
- `vulture_allowlist.py` (убрать `haggle_*`), `tests/scenarios/memory_script.py` (WINDOW мока — подобрать заново)

### API (`src/ai_dm/rules/trade.py`, чистые функции)
- `day_of(now_s) -> int` — `now_s // DAY_S` (или реэкспорт из `rules/divine`; рек. своя строка, без зависимости
  торговли от divine).
- `active_haggle(profile, now_s) -> int` — `profile.haggle_percent`, если `profile.haggle_day == day_of(now_s)`,
  иначе 0. `haggle_day == 0` — валидный день (тест Т0 уже требует `0 is not None`).
- `can_haggle(profile, now_s) -> bool` — `profile.haggle_day != day_of(now_s)`.
- `haggle_dc(attitude, cfg) -> int` — `cfg.trade.haggle_good_dc` при `attitude >= attitude_good_from`, иначе
  `cfg.trade.haggle_dc`.
- `haggle_mode(attitude, cfg) -> str` — `"disadvantage"` при `attitude < haggle_hostile_below`, иначе `"normal"`
  (передаётся в `skill_check(base_adv=..., base_adv_label="недружелюбен")`).
- `haggle_percent_for(outcome, total, dc, cfg) -> int` — `success` и `total >= dc + haggle_strong_margin` →
  `haggle_strong_percent`; `success` → `haggle_success_percent`; иначе `haggle_fail_percent`.
- `buy_factor_total(attitude, haggle, cfg) -> Fraction` — формула с зажимом выше (вся арифметика в Fraction,
  `Fraction(str(float))` как сейчас).
- `buy_quote(cost_cp, attitude, cfg, haggle=0) -> int` — `ceil(cost_cp * buy_factor_total(...))`. Параметр
  по умолчанию 0 — старые вызовы и тесты Т1 неизменны (при haggle=0 и дефолтах зажим не срабатывает: 0.9 ≥ 0.8).
  ⚠ если кто-то настроит `attitude_good_buy_factor` < `buy_factor*(1-cap)`, зажим сработает и без торга — это
  правильно (потолок суммарной скидки), но поменяет цены; тест.
- `merchant_buy_quote(cost_cp, npc, now_s, cfg) -> int` — удобная обёртка
  `buy_quote(cost_cp, npc.attitude, cfg, active_haggle(npc.trade, now_s))`; все 6 мест покупки зовут её.
- `apply_haggle(profile, percent, now_s) -> None` — пишет `haggle_percent`, `haggle_day = day_of(now_s)`.
- `assortment` (базовая цена без отношения) — не меняется.

### Конфиг (`TradeConfig`, `[trade]`)
- Новые: `haggle_dc: int = 15` (SRD Influence, безразличный), `haggle_good_dc: int = 10`,
  `haggle_strong_margin: int = Field(5, ge=1)`, `haggle_hostile_below: int = 0` (помеха при attitude < 0).
- Ограничения существующих (в валидатор): `haggle_strong_percent <= haggle_success_percent <= 0 <=
  haggle_fail_percent`; `-haggle_strong_percent <= price_mod_cap_percent` не требовать (зажим и так), но
  `haggle_fail_percent <= price_mod_cap_percent` — не требовать тоже (зажим). Рек.: только порядок знаков.
- Инвариант маржи — без изменений (рек. «только покупка»). Если проектировщик выберет и продажу (В-Т5-1 б), то
  валидатор: `buy_factor*(1-cap) >= min(max_sell*(1+cap), 1) * min_margin` → при дефолтах 0.8 ≥ 0.72*1.3 = 0.936
  ЛОМАЕТСЯ — нужно менять числа конфига. Это аргумент за «только покупка».

### Протокол
- `Haggle(Request)` в `requests.py`: `type: Literal["haggle"]`, `npc_id: str` (описание: «Id NPC-торговца из
  scene_npcs с merchant»). Без `skill`, `category`, `percent` — мастер ничего не выбирает. Docstring:
  «Торг Убеждением с торговцем: движок бросает Убеждение героя против СЛ торговца, итог — скидка/наценка
  покупки у него до конца дня. Раз в день на торговца.»
- `schema.py`: добавить `"haggle"` рядом с `"trade"` (вне боя; в бою недоступен).
- Обработчик `protocol/handlers/trade.py::haggle(ctx, request)`:
  1. `trade_pick.merchant_base_problem(ctx, request, npc)` — новая функция: бой → Invalid `in_combat`,
     `npc_problem`, `refuses` → rejected. `merchant_problem` = base + проверка qty (поведение trade неизменно).
  2. `not can_haggle(...)` → rejected «уже торговались сегодня», подсказка мастеру: «Сегодня с {name} уже
     торговались ({±N}%): опиши отказ по факту.»
  3. `dc = haggle_dc`, `mode = haggle_mode`; `checks.skill_check(ctx.hero, ctx.registry, ctx.rng, "persuasion",
     dc=dc, base_adv=mode, base_adv_label=..., tags={"stakes": "normal"}, now_s=...)`; `ref = ctx.add_roll(result,
     ctx.hero.id)`.
  4. `percent = haggle_percent_for(...)`; `apply_haggle(npc.trade, percent, now_s)`.
  5. Decision accepted: `result = {"roll_ref", "outcome", "dc", "total", "haggle_percent": percent,
     "until": "конец дня"}`, `log = [result.log.text, "Торг с {name}: цены покупки {−10%|…} до конца дня"]`.
  - Лимит сделок `scene.trades` торг НЕ тратит (это не сделка; защищено днём). Время не идёт.
- Котировки `trade`: `category_list` и `buy` → `merchant_buy_quote(..., world.clock.now_s, ...)`. `sell` — без
  изменений. В `trade_result` добавить `"haggle_percent"` только если активен (не ломать существующие тесты
  результата — проверить, нет ли сравнения dict целиком).

### Контекст мастера (`master/prompt.py::merchant_data`)
- `stock[].price_cp` и `categories[].min_cp/max_cp` — через `merchant_buy_quote` (нужен `now_s`: прокинуть
  `world.clock.now_s` из `trade_data`).
- Поле `"haggle"`: отсутствует, если сегодня не торговались (экономия окна); иначе `{"percent": N}` — мастер видит
  и что цены уже с поправкой, и что повторный торг сегодня будет отклонён. Отдельный флаг `can_haggle` не нужен.

### narrator_rules («Торговля», один абзац, коротко ради WINDOW)
«Торг — только инструментом `haggle`, когда игрок сам торгуется (просит скидку, уговаривает). Бросок и СЛ —
движка; без `haggle` цену не меняй и скидок не обещай. Исход — в `haggle_percent`: отрицательный — скидка,
положительный — торговец обиделся и накинул; действует на покупки у этого торговца до конца дня, цены в `trade`
уже с поправкой. Если у торговца есть `haggle`, сегодня уже торговались: второй раз движок откажет.»
- Тест на белый список имён полей в «Торговле» (Т3, п.8) — добавить `haggle`, `haggle_percent`.

### /shop (`game/shop_text.py`)
- `sale_rows(npc, world, registry, level, cfg)`: три `buy_quote` → `merchant_buy_quote(..., world.clock.now_s, cfg)`.
- `shop_lines`: в заголовке торговца хвост при активном торге: «… — кошелёк торговца: X; торг: −10% до конца дня»
  (провал: «торг: +10% …»). `sell_lines` не меняется.

### Чистка
- `vulture_allowlist.py`: удалить строки 76–80 (`haggle_*`) — поля теперь используются; `make dead` чистый.
- HANDOFF: Т5 ✅, ревью `docs/plan-trade.md`.

### Тесты (TDD, для кабана-доебы)
`tests/unit/rules/test_trade.py`:
- `day_of(0)==0`, `day_of(86399)==0`, `day_of(86400)==1`.
- `active_haggle`: тот же день → percent; следующий день → 0; `haggle_day=None` → 0; `haggle_day=0`, now 100 → percent.
- `can_haggle`: None → True; сегодня → False; вчера → True.
- `haggle_percent_for`: success total=dc → −10; total=dc+4 → −10; total=dc+5 → −20; fail → +10.
- `buy_quote` без haggle — старые числа Т1 неизменны (регрессия).
- обычное отношение, −10 → 0.9×; −20 → 0.8×; +10 → 1.1×; хорошее отношение (0.9) + −20 → зажим 0.8× (не 0.72);
  хорошее + −10 → 0.81×; хорошее + +10 → 0.99×; округление вверх на нечётных (cost 7, −10 → ceil(6.3)=7).
- зажим сверху: конфиг с cap=5, +10 → 1.05×.
- Свойство: для всех attitude ∈ {−49, 0, 49, 50, 100} × haggle ∈ {−20,−10,0,10} × cost ∈ 1..500
  `buy_quote(cost, a, cfg, h) * 1 >= sell_quote(cost, a', cfg) * 1.3` для любого a' (арбитража нет).
`tests/unit/config/test_trade_config.py`:
- дефолты новых полей; валидатор: success > 0 → ошибка; strong > success → ошибка; fail < 0 → ошибка.
`tests/unit/protocol/test_apply_trade.py` (или новый `test_apply_haggle.py`):
- успех (rng подобран): accepted, `haggle_percent == -10`, профиль `haggle_day == today`, roll_ref есть, бросок —
  Убеждение, СЛ 15.
- сильный успех → −20; провал → +10 и цены `trade buy` выросли.
- повтор в тот же день (после успеха и после провала) → rejected, бросок НЕ сделан (rng не тронут), профиль не изменён.
- на следующий игровой день (advance clock на DAY_S) → торг снова разрешён; старая поправка не действует.
- хорошее отношение → СЛ 10; attitude < 0 → бросок с помехой; attitude ≤ refuse_at → rejected «отказывается».
- в бою → Invalid `in_combat`; чужой/отсутствующий/не торговец/мёртвый NPC → те же Invalid, что у trade.
- торг не тратит `scene.trades`.
- после торга −10: `trade list` и `trade buy` дают цену −10% (stock, SRD, сюжетное у держателя); `trade sell` —
  прежняя цена.
- `trade` без торга — все существующие тесты Т2 зелёные без правок.
`tests/unit/protocol/test_schema_trade.py`: `haggle` в схеме вне боя, поля только `type`,`npc_id`; нет в бою.
`tests/unit/master/test_prompt_trade.py`: без торга нет ключа `haggle`; после торга `{"percent": -10}` и цены
stock/categories снижены; на следующий день ключа нет и цены прежние.
`tests/unit/master/test_narrator_trade_rules.py`: абзац упоминает `haggle`, «без `haggle` цену не меняй».
`tests/unit/game/test_shop_command.py`: после торга цены в /shop −10%, строка «торг: −10% до конца дня»; провал →
«+10%»; без торга строки нет; продажа в /shop без изменений; на следующий день — без строки.
`tests/scenarios/test_trade_scenario.py`: мок-сценарий «игрок торгуется → haggle → trade buy по сниженной цене»;
WINDOW мока подобрать заново (narrator_rules вырос).
Сейв: тест загрузки v7 с `haggle_percent=-10, haggle_day=N` → round-trip без миграции (версия остаётся 7).

### Риски
- **Переброс через сон/advance_time:** ждать сутки ради −20% — допустимо (время стоит ресурсов, сцена
  закрывается `time_jump`). Принять.
- **Переброс через новых торговцев:** мастер назначает нового торговца и торгуется с ним — ограничено
  `new_merchants_per_scene=1` и запретом смены `trade_kind`. Принять.
- **LLM зовёт `haggle` без просьбы игрока** — только правило narrator_rules; провал (+10%) делает это невыгодным
  мастеру «в пользу героя». Принять.
- **Граница дня** — полночь игровых часов: торг в 23:50 живёт 10 минут. Принять (просто и предсказуемо); альтернатива
  «24 часа от торга» — `haggle_day` хранит день, не время; потребовала бы смены смысла поля. Не делать.
- **`buy_quote` с зажимом** меняет цену при «хорошем отношении» только если конфиг выйдет за потолок — тест
  регрессии чисел Т1.
- **Окно контекста:** +абзац правил, +ключ `haggle` у торговца — WINDOW мока перебрать (как в Т2/Т3).
- **`trade_result`:** если тесты сравнивают dict целиком — добавлять `haggle_percent` только при активном торге.

### Вопросы проектировщику (с рекомендацией)
- **В-Т5-1** Торг влияет только на покупку героем или и на продажу? Рек.: только покупка (инвариант маржи цел без
  изменения конфига; при симметрии дефолты ломают валидатор — 0.8 < 0.936).
- **В-Т5-2** Числа: успех −10%, сильный успех (≥ СЛ+5) −20%, провал +10%, СЛ 15 / 10 при хорошем отношении,
  помеха при attitude < 0. Рек.: так.
- **В-Т5-3** Провал тоже «сжигает» торг на день (+10% до конца дня)? Рек.: да — иначе переброс до успеха.
- **В-Т5-4** Только Убеждение или также Обман/Запугивание (как в parley)? Рек.: только Убеждение в Т5; другие
  навыки — в BACKLOG (у Запугивания свой исход — падение отношения).
- **В-Т5-5** Отдельный инструмент `haggle` вместо `skill_check` с пометкой (как в наброске)? Рек.: отдельный —
  СЛ считает движок, мастер не может занизить сложность.

### Т5: ответы проектировщика (2026-10-07)
В-Т5-1…В-Т5-5 — по рекомендациям: торг только на цену покупки; −10/−20 (СЛ+5)/+10, СЛ 15 (10 при хорошем отношении),
помеха при attitude < 0; провал закрывает торг на день; только Убеждение; отдельный инструмент `haggle`.

## Правки по ревью: Торговля, партия Т0: ревью и решения (бывш. docs/decisions/trade-t0-review.md)

### Решения проектировщика (2026-10-07)
1. Инвариант цен для ВСЕХ категорий (включая ценности): цена продажи торговцем герою даже при максимальной скидке
   (отношение + торг, потолок 20%) не ниже цены скупки у героя при самых выгодных для героя условиях × 1.3 (маржа 30%).
   «Ценности по полной цене» отменено. Валидатор конфига проверяет худший случай.
2. Пресеты кабана — ок на этом этапе. Позже — обязательное питание → понадобится продавец еды (BACKLOG).
3. «Хорошая» продажа — абсолютный коэффициент; валидатор: attitude_good_sell_factor ≥ sell_factor,
   attitude_good_buy_factor ≤ buy_factor.
4. Пак не загрузился при миграции v7 — грузить, но писать предупреждение в отчёт миграции.

### Ревью мамы-кабана
Пп. 1 (арбитраж), 2 (ge=0 и порядок attitude_refuse_at < attitude_good_from), 3 (комментарий к TradeCategory,
category="" — вопрос к Т1), 4 (report при сбое пака) — в правку. 5–7 на усмотрение; п. 6 — тест в Т1/Т2.

### Итог правок
min_margin=1.3, price_mod_cap_percent=20, full_price_categories удалён; ограничения Field; pack_npc_trade → None при
сбое пака, строка в report миграции. Мутации: новые строки — 0 выживших (эквивалентный setdefault("trade",)).
Не покрыт тестом ui/cli.py::prepare (присваивание npc_trade); GameApp.load покрыт.

## Правки по ревью: Торговля, партия Т1: ревью и решения (бывш. docs/decisions/trade-t1-review.md)

### Решения оркестратора (проектировщик может переиграть)
1. `Item.category == ""` → `gear` (рекомендация плана).
2. `potion_of_healing.yaml`: `category: consumable` — иначе ассортимент `alchemist` пуст. На /inv, лут, бой не влияет (ревью).

### Ревью мамы-кабана — вердикт: мержить
1, 2, 5, 6 — записаны в TRADE-PLAN «Т1: заметки для Т2». 3 (дубль формулы в assortment), 4 (магия оружия/доспехов
не моделируется) — низкие, не правились.

### Итог
80 тестов tests/unit/rules/test_trade.py; mutmut rules/trade.py — 101 мутант, 0 выживших. Полный pytest 9392 passed,
cov 96.13%. make smells 211 (плавает 208–212, лимит 210), make dead — старые находки ui/tui (долг BACKLOG 16).

## Правки по ревью: Торговля, партия Т2: ревью (бывш. docs/decisions/trade-t2-review.md)

### Отступления кабана — оценка
1. Латинская «x» в логах вместо «×» — принять: так уже в take_item/loot (`x{qty}`), единый стиль важнее плана.
2. Смена trade_kind у уже торговца — rejected — принять (иначе мастер сбрасывает кошелёк сменой пресета).
3. Лимиты ops_per_scene/new_merchants не действуют без сцены — принять, так же устроены прочие сценовые лимиты.
4. Одна сделка — один стек (clamped при нехватке в стеке) — принять: проще, мастер дозапросит; clamped-подсказка
   это покрывает.
5. WorldNpcUpdate наследует trade_kind, world-обработчик его игнорирует — НЕ принять (см. п.1 ниже).

### Ревью мамы-кабана — вердикт: нужны правки (п.1, п.2), остальное — низкие
1. (средн.) requests.py::WorldNpcUpdate — поле trade_kind попадает в схему world_sim: лишние токены
   (вероятно часть +87 в test_stage4_memory) и молча игнорируемое поле, которое LLM будет заполнять.
   Предложение: убрать поле из схемы наследника (как сделано для других полей, не нужных закадру), либо
   отдельный базовый класс без trade_kind. Проверить, не снимет ли это красные test_stage4_memory.
2. (средн.) world.py::npc_update — trade_kind + status=dead в одном запросе: merchant_update_problem проверяет
   alive ДО change_status, затем make_merchant делает торговцем уже мёртвого NPC. Предложение: при
   request.status не None и trade_kind не None — Invalid (или make_merchant только если npc.status == "alive"
   после изменений). Тест.
3. (низк.) resources.py::take_item — holder_npc_id для не-сюжетного item_id молча игнорируется; NPC не проверяется
   на alive/локацию героя. Предложение: для несюжетного — игнор допустим, но отразить в description поля
   («только для сюжетных»); NPC вне локации — Invalid npc_absent, как в trade.
4. (низк.) trade.py::sellable_stacks — надетый экземпляр считается самым дорогим стеком (equipped не знает
   стека). Эвристика; записать в план как известное ограничение.
5. (низк.) trade.py::buy сюжетного — rarity/too_rare и quality запроса не проверяются; выкуп своего же
   предмета — корректно, просто зафиксировать в комментарии.
6. (низк.) В npc_update счётчик merchants_created инкрементируется в make_merchant — ок; в npc_create
   проверка лимита идёт до конфликта имён, но инкремент после — корректно, без замечаний.

### Соответствие плану
Разделы 3–4 и «Т1: заметки для Т2» закрыты: in_combat/unknown_npc/npc_absent/not_merchant/bad_amount, refuses,
restock до сделки, rejected «ничего не стоит» до деления на purse, сюжетное мимо merchant_buys, выкуп только у
holder.ref, hand_to_npc/recover, item_sold, результат с 7 полями, правило effects→category (stoneskin_elixir).
tests/unit/protocol + content: 1329 passed.

### Решения проектировщика (2026-10-07)
1. Бюджет мока памяти (+87 ток. от схемы trade): только поднять WINDOW в memory_script.py, описания не ужимать.
2. `trade_kind` в WorldNpcUpdate — скрыть из схемы роли world (п.1 ревью).
3. `take_item` сюжетного предмета без `holder_npc_id` — Invalid (держатель обязателен).
Приняты отступления кабана: латинская «x», rejected при смене trade_kind, лимиты без сцены не действуют, одна сделка — один стек.

## Правки по ревью: Торговля, партия Т3: ревью (бывш. docs/decisions/trade-t3-review.md)

### Ревью мамы-кабана — вердикт: нужны правки
1. (блокер) pyproject.toml — mutmut перенацелен на файлы Т3. Снят: kaban-doeba восстановила.
2. (средн.) WINDOW +750: дубли в narrator_rules («Торговля»: sells_hint ≈ правило, holder_npc_id ≈ описание схемы
   take_item, запрет gold+take_item ≈ «только trade»); комментарий WINDOW — указать прирост оценки.
3. (средн.) Дубль item_id в buy, если вещь есть и в stock, и в ассортименте пресета.
4. (средн.) У stock-позиций нет quality — одинаковые item_id с разной ценой неразличимы.
5. (низк.) Ассортимент глобально по цене — дешёвое вытесняет категории у смешанного пресета.
6. (низк.) Двойной поиск модели в merchant_data (assortment + find_item) — оставить, меняет Т1.
7. (низк.) trade — список и при одном торговце.
8. (низк.) Имена полей без бэктиков в «Торговле» из-за белого списка теста.
Подсказки not_merchant/not_sold — в trade_pick.py (merchant_ids/sold_ids), не в hints.py; принято.

### Решения проектировщика (2026-10-07)
- п.2 — убрать дубли (правила не урезать), WINDOW пересчитать.
- п.3 — оставить как есть.
- п.4 — да: quality в позиции stock, если непустое.
- п.5 — двухступенчатый выбор: в контексте `trade` — stock + сводка категорий пресета (количество, диапазон цен);
  полный список категории мастер получает новым действием `trade` «list» (без сделки, не тратит лимит ops_per_scene).
- п.6 — оставить. п.7 — принять. п.8 — расширить белый список теста, вернуть бэктики.

### Повторное ревью — вердикт: можно мержить
1. Тесты list на бой/мёртвый/не в локации/пустую category/отказ по отношению — kaban-doeba.
2. Подсказка not_sold — добавить отсылку к `trade` list по категории (решение проектировщика 2026-10-07: да).
3. category в buy/sell игнорируется — принято.
4. WINDOW 21555 — оправдан; убрать три мелких дубля схема↔правила (docstring Trade, перечень полей в абз. 1 и 3 «Торговли»), WINDOW подобрать заново.

## Правки по ревью: Ревью: торговля, партия Т4 (показ: /inv цены, /shop, «Потрачено») (бывш. docs/decisions/trade-t4-review.md)

Проверено: git diff (commands.py, sheet_text.py, ui/screen.py, ui/simple.py, ui/tui/modals.py, ui/tui/strings.py,
тесты) и новые файлы game/shop_text.py, tests/unit/game/test_inv_prices.py, test_shop_command.py,
tests/unit/ui/test_gains_spent.py, tests/unit/ui/tui/test_tui_shop.py. Сверено с docs/plan-trade.md §5, Т4, В-Т5, В-Т7
и с обработчиком protocol/handlers/trade.py + trade_pick.py. Новые тесты: 71 passed.

### Хорошо
- Цены не дублируются: /shop берёт `buy_quote`/`sell_quote`/`merchant_buys`/`refuses`/`assortment` из rules/trade.py.
  Покупка из stock — `buy_quote(entry.cost_cp)`, из каталога — `buy_quote(model.cost_cp)`, продажа —
  `sell_quote(stack.cost_cp)`: ровно те же формулы и аргументы, что в `buy`/`sell` обработчика.
- /inv: полная цена экземпляра (В-Т5), сюжетные (source == "world") без хвоста — по плану.
- «Потрачено: −X» в gains_lines (В-Т7), простой режим выносит его отдельной строкой, не в «Получено».
- /shop не тратит время и не меняет состояние (есть тесты).

### Обязательно
1. **Дублирование заголовков групп** — `shop_text.py::shop_item_lines`. Сортировка по `(r[0], группа, имя)` ставит
   весь stock раньше всего ассортимента, поэтому при stock-оружии + stock-доспехе + каталожном оружии выходит
   «Оружие: A / Доспехи: P / Оружие: B» (проверено вызовом). План: «группы как в /inv». Ключ сортировки поменять на
   `(order.index(r[4]), r[0], r[1])` — stock первым внутри своей группы (так и называется тест
   `test_stock_comes_before_the_preset_in_its_group`). Добавить тест: две группы в stock + каталог — каждый
   заголовок ровно один раз.

### Желательно
2. **Выкуп сюжетного не виден** — `sale_rows`. Проданный сюжетный предмет уходит не в `stock`, а в держателя
   (`custom_items.hand_to_npc`), и обработчик даёт его выкупить у этого NPC по `buy_quote(holder.cost_cp)` (§4
   плана). В /shop его нет. Предложение: строки по `world.custom_items` с `holder.kind == "npc"` и
   `holder.ref == npc.id` в группу «Сюжетное» с ценой `buy_quote(holder.cost_cp, …)`. Если проектировщик считает это
   вне Т4 — записать в бэклог.
3. **Stock-предмет «слишком редкий»** — `catalog_source` отказывает в stock-стеке при `too_rare`, а /shop его
   показывает с ценой. Редкий случай (герой сам продал редкое); либо фильтровать тем же `too_rare`, либо оставить и
   записать как известное расхождение.
4. **Одноимённые строки stock и каталога** (например «Скимитар» новый и поношенный) — обработчик без quality купит
   самый дешёвый стек stock. Это видно по цене, правка не нужна.
5. `sell_lines`: `custom = …` вычисляется до `continue` по `found is None` — порядок проверок как в
   `sell_stack` (сначала found, потом custom) читался бы проще. Косметика.
6. `modals.py`: комментарий переразбит на две строки — постороннее форматирование, лучше одной строкой как было
   (если упирается в длину — допустимо).

### Вопросы разработчика — оценка
1. **Кошелёк с ленивым restock без изменения состояния** (`purse_now`) — верно: показывает ровно то, что увидит
   `trade` после `restock`. Дублирует условие из `rules.trade.restock`; рек. перенести `purse_now` в rules/trade.py
   (рядом с `restock`, одна точка правды), не обязательно.
2. **Лимит 40 на stock+ассортимент вместе, stock первым** — согласен (stock конечен и уникален). После правки п.1
   «первым» — внутри группы; лимит режет хвост отсортированного списка, stock всё равно сверху каждой группы, но
   может быть отрезан в последних группах. Рек.: принять, т.к. stock обычно мал; строки «Продать» в лимит не входят —
   тоже нормально.
3. **Одна строка «Продать: …» на предмет** (по стеку) — принять: разные стеки = разные цены, так и продаёт
   обработчик. Количество «xN» в строке продажи не выводится — рек. добавить `x{free}` при free > 1 (желательно).
4. **haggle (Т5) не учтён** — правильно, Т5 ещё нет. Т5 должна будет показать в /shop цену с учётом скидки, если
   скидка хранится в TradeProfile; отметить в плане Т5.
5. **Дубль «надетого экземпляра» с `sellable_stacks`** — дубль реальный, и логика уже расходится в мелочи (в
   sell_lines «dearest» — первый стек с max cost по `marked`, в sellable_stacks — `max(...)`, совпадает только
   потому, что оба берут первый). Рек.: вызывать `sellable_stacks` из sell_lines (нужен лишь объект с
   `item_id`/`quality=None`), либо вынести функцию «свободно к продаже» в rules/inventory.py и звать из обоих мест.
   Можно отложить, но не копить третий вариант.
6. **custom в sell_lines через оверлей мира в app.registry** — так же работает и обработчик (`find_item(ctx.registry)`),
   значит поведение согласовано. Тест `test_sell_block_lists_custom_item_whatever_the_preset_buys` это фиксирует.
   Рек.: принять, добавить комментарий в одну строку у ветки custom.

### Вердикт
Нужны правки: п.1 обязательно; остальное — по усмотрению/в бэклог.

### Итог правок (оркестратор)
Внесены: обязательная (сортировка группа → stock → каталог → имя), желательные — purse_now в rules/trade.py,
sell_lines через sellable_stacks, stock too_rare скрыт, сюжетные у торговца-держателя в «Сюжетное», «Продать … xN».
Старые выжившие мутанты sheet_text/ui.screen/ui.simple — BACKLOG 16. Haggle в /shop — учесть в плане Т5.

## Правки по ревью: Ревью: торговля, партия Т5 (торг Убеждением) — мама-кабан, 2026-10-07 (бывш. docs/decisions/trade-t5-review.md)

Объект: незакоммиченный дифф Т5 + новые tests/unit/protocol/test_apply_haggle.py, tests/unit/persistence/test_save_haggle.py.
План: docs/plan-trade.md «Т5: план» и «Т5: ответы проектировщика». Полный прогон: 9915 passed, 1 xfailed.

### Что сделано хорошо
- Мастер не задаёт ни СЛ, ни процент: `Haggle` = только `type` + `npc_id`; СЛ (`haggle_dc`), режим (`haggle_mode`)
  и процент (`haggle_percent_for`) считает движок; бросок через `checks.skill_check` + `ctx.add_roll` (боги/перебросы работают).
- Инвариант маржи: торг только на покупку, `buy_factor_total` зажимает снизу ровно `buy_factor*(100-cap)/100` —
  то же число, что в `check_no_arbitrage`; `sell_quote` не тронут. Вся арифметика во Fraction. Валидатор знаков торга добавлен.
- Повтор в тот же день: `can_haggle` проверяется до броска, rng не трогается, профиль не меняется; провал тоже
  «сжигает» день. `haggle_day == 0` обрабатывается верно (сравнение, не truthiness).
- Все места покупки (trade list/buy, контекст мастера stock/categories, /shop — stock, сюжетное, ассортимент) идут
  через `merchant_buy_quote`; продажа неизменна. Сейв v7 не менялся, round-trip покрыт тестом.
- Порядок проверок `merchant_problem` (бой → NPC → qty → отказ) сохранён — существующие тесты Т2 без правок.

### Оценка отступлений разработчика
1. `scene_problem` / `refusal_problem` / `merchant_base_problem` — приемлемо: сохраняет порядок проверок trade
   (qty между NPC и отказом). Три функции вместо одной с флагом — проще для чтения. Принять.
2. `haggle_state` в rules/trade.py — принять (чистая функция, без неё `prompt.py` дублировал бы условие).
   Замечание по месту: это форма для контекста мастера, логичнее в `master/prompt.py`; не блокер.
3. `haggle_percent` в `trade_result` только для buy — верно и соответствует решению «только покупка».
4. Знак ASCII «-10%» в /shop — расхождение с планом и с Т4 (`ui/screen.py:202` «Потрачено: −X» с U+2212). См. «Обязательно» 1.
5. WINDOW 21470→21900 — обосновано комментарием с пиком оценки (17201→17520, +319 ток. при +430 окна — запас как в Т3). Принять.
6. «now_s не передаётся в skill_check» — в текущем коде `now_s=now_s` ПЕРЕДАЁТСЯ (handlers/trade.py, haggle),
   как в плане. Отступления нет; пометка разработчика устарела.
7. HANDOFF помечен ✅ до ревью — формально рано, но текст корректен и ссылается на этот файл; оставить, если правки
   ниже будут внесены до коммита.

### Обязательно
1. **Минус в /shop и логе** — `game/shop_text.py::shop_lines` и `protocol/handlers/trade.py::haggle` (лог и подсказка
   отказа) печатают `{percent:+d}` → «-10%». План: «торг: −10% до конца дня»; Т4 в gains использует «−» (U+2212).
   Привести к единому знаку для игрока: в /shop — «−10%»/«+10%» (например `f"{'−' if percent < 0 else '+'}{abs(percent)}%"`
   одной строкой на месте, без хелпера-абстракции, либо маленький хелпер в shop_text, если нужен в двух местах).
   Тест test_shop_command — проверять «−10%». Для лога/подсказки мастеру ASCII допустим, но лучше одинаково.

### Желательно
1. `shop_lines`: условие `not can_haggle(...)` + `active_haggle(...)` повторяет логику `haggle_state`; можно
   `state = trade_rules.haggle_state(npc.trade, now)` и брать `state["haggle"]["percent"]` — одно правило «торговались сегодня».
   Также `world.clock.now_s` берётся трижды — локальная переменная как в `sale_rows`.
2. `haggle`: в `result` нет `npc_id`/имени — мастеру хватает контекста, но для лога сессии/отладки полезно; по желанию.
3. Тест на граничный случай конфига из плана (⚠ `attitude_good_buy_factor` < `buy_factor*(1-cap)` → зажим без торга)
   — проверить, что есть; если нет, добавить в test_trade.py.
4. narrator_rules: «Если у торговца есть `haggle`» — уточнить «ключ `haggle` в `trade`», чтобы не путать с инструментом. Окно не растёт заметно.

### Вопросы проектировщику
- **В-Т5-R1** Знак минуса в игровом тексте: единый U+2212 во всех строках для игрока (/shop, gains), ASCII — только
  в логах/подсказках мастеру? Рек.: да.
- **В-Т5-R2** Отметка ✅ в HANDOFF до ревью — допустимо, если в той же партии? Рек.: ставить ✅ после ревью и правок
  (в коммите партии), как в Т0–Т4.

**Вердикт:** нужны правки (обязательно 1), остальное — по желанию.

### Итог правок (оркестратор)
Обязательная внесена: /shop печатает «торг: −10%» (U+2212), через haggle_state, now_s одной переменной; narrator_rules —
«ключ `haggle` в `trade`». В-Т5-R1/R2 — по рекомендации (U+2212 для игрока; отметка в HANDOFF после ревью).
Старые выжившие мутанты handlers/trade, trade_pick, shop_text — BACKLOG 16.

## Итог: Из HANDOFF.md до 22д (бывш. docs/HANDOFF.md)

Партии Т0 → Т1 → Т2 → Т3 → Т4 → Т5 (торг Убеждением), одна версия сейва v7. ⚠ Не играть живые миры до конца вставки.
- Т0 ✅: TradeProfile у NPC (поля торга Т5 сразу), TradeConfig/пресеты (инвариант маржи 1.3 при скидке до 20%),
  миграция v7 (торговцы из пака через MigrationContext.npc_trade, предупреждение при сбое пака);
  ревью и решения 1–4 — docs/plan-trade.md. Дальше — Т1 (чистые функции rules/trade.py; вопрос
  category="" → gear в плане).
- Т1 ✅: rules/trade.py (item_category, merchant_sells/buys, refuses, buy/sell_quote через Fraction, assortment, restock);
  зелье лечения category: consumable; ревью docs/plan-trade.md, заметки для Т2 — в конце TRADE-PLAN.
- Т2 ✅: protocol/handlers/trade.py + trade_pick.py (buy/sell, stock, выкуп сюжетного у держателя), trade_kind в
  npc_create/npc_update (не у роли world; вместе со status — Invalid), take_item сюжетного — holder_npc_id обязателен,
  WINDOW мока 20650; ревью и решения 1–3 — docs/plan-trade.md. make dead: haggle_* (Т0, под Т5) — ждёт
  решения по allowlist (решено: haggle_* в vulture_allowlist до Т5).
- Т3 ✅: контекст мастера — scene_npcs.merchant, ключ trade (stock с quality + сводка categories), двухступенчатая покупка
  trade direction=list category (без сделки, не тратит лимит), narrator_rules «Торговля», not_sold отсылает к list,
  мок-сценарий tests/scenarios/test_trade_scenario.py, WINDOW мока 21470; ревью и решения — docs/plan-trade.md.
  Дальше — Т4 (показ: /inv цены, /shop, «Потрачено» в gains).
- Т4 ✅: /inv — цена экземпляра хвостом; /shop (game/shop_text.py, модалка «Торговля», вне хода; purse_now в rules/trade.py,
  продажа через sellable_stacks, сюжетные у торговца-держателя); «Потрачено: −X» в gains; ревью docs/plan-trade.md.
- Т5 ✅ (ревью и решения R1/R2 — docs/plan-trade.md; WINDOW мока 21900): инструмент haggle (СЛ и бросок Убеждения — движок, раз в игровой
  день на торговца, поправка только на покупку, потолок price_mod_cap_percent), rules/trade.py (merchant_buy_quote, haggle_*),
  цены с торгом в trade/контексте мастера/ /shop («торг: −10%»); haggle_* убраны из vulture_allowlist.
  Вставка «Торговля» закрыта — живые миры (v7) можно играть. Дальше — этап 6 (P1 BACKLOG).
- Торговля, план: papa-kaban ~56 тыс. Т0: kaban ~69+84 тыс. (~10 мин); kaban-doeba ~132+147 тыс. (~38 мин); mama-kaban ~32 тыс.
- Т1: kaban ~39 тыс. (~1 мин); kaban-doeba ~47 тыс. (~3 мин); mama-kaban ~25 тыс.
- Т2: kaban ~77+87+112 тыс. (~12 мин); kaban-doeba ~152+171 тыс. (~40 мин); mama-kaban ~32 тыс.
- Т3: kaban ~66+68 тыс. (~36 мин); kaban-doeba ~90+39 тыс. (~24 мин, mutmut); mama-kaban ~18+21 тыс.
- Т4: kaban ~55+63 тыс. (~20 мин); kaban-doeba ~129+144 тыс. (~49 мин); mama-kaban ~28 тыс.
- Т5: papa-kaban ~51 тыс.; kaban ~69 тыс. (~21 мин); kaban-doeba ~153 тыс. (~36 мин); mama-kaban ~36 тыс.
