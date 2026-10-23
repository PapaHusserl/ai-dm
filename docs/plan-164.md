# 164. Выбор услуги и товара в /shop, как в инвентаре (подшаг У1, BACKLOG 164)

План — папа-кабан, 2026-10-23. Груминг: свинопас и свекровь (scratchpad сессии), решения проектировщика 41–53 —
`docs/plan-u1.md`. ROADMAP и handoff не правлю до аппрува.

контур: вне msa; режим: встроить (образцы — окно `/inv`: `ui/tui/modals.py:InvModal`, `ui/tui/blocks.py:inv_rows`,
`game/inv_actions.py` + заметки `GameApp.with_notes`; движок вне хода мастера — `game/fight_debug.py:run_fight`
строит `TurnContext` и зовёт `protocol.apply`).

**Задача / проект:** в TUI `/shop` открывает окно по образцу `InvModal`: выбор NPC → вкладки товаров, продажи и
услуг → количество → покупка/продажа/оплата движком, без мастера (решения 43–47, 53); мастер следующим ходом получает
пометку о сделке и знает услуги NPC только по названиям (48, 51); покупка словами через `service`/`trade` остаётся (49),
отказы — только движка (50); полей сейва нет (52).

**Правило:**
1. было `/shop` — `cmd_shop(app, arg)` игнорирует `arg`, всегда `shop_lines` (`game/commands.py:251`) → станет
   `arg` непустой → `shop_actions.run(app, arg)` (подкоманды `услуга|купить|продать`, как `cmd_inv` → `inv_actions.run`);
   без `arg` — текст как был.
2. было `provider_data`: `items = [{id, name, price_cp, unit, description?}]` (`master/prompt.py:207–213`) → станет
   без `price_cp` (решение 48); срез `[:SERVICE_ITEMS_MAX]` остаётся (51).
3. было `finish_turn`: `elif modal_text and command == "/inv" and self.can_pick_item(): push InvModal`
   (`ui/tui/app.py:469`) → добавится ветка `command == "/shop" and self.can_shop()` → окно NPC/товаров; иначе
   TextModal как сейчас.
4. было `narrator_rules.md:106` «…(id услуг; цены, `unit` и `description` — в ключе `services` состояния)…» → станет:
   цен в `services` нет (узнать — `service` list или `total_cp` после buy); покупка из окна приходит пометкой
   «Перед этим герой сам: …» — деньги списаны, повторно `service`/`trade` не вызывать; комната из окна — только оплата,
   `rest long` — когда игрок ложится (решение 45).

**Поведение:** меняется — TUI: `/shop` вне боя открывает окно вместо текста (в бою, при `pending`, меню лимита, без
NPC или когда все отказывают — текст как сейчас); после выбора в ленте строки движка («Оплачено: …», «Куплено: …»,
«Продано: …», броски последствий, отказ), панель «Получено/Потрачено» (уже работает через `loot_snapshot` для любой
строки — `ui/session.py:109`), автосейв; следующий словесный ход несёт пометку мастеру. Простой режим (`ui/simple.py`):
`/shop` без аргументов как был; подкоманды работают, но ids игрок не видит — не рекламируем (Р5). Контекст мастера:
`services[].items` без цен во всех мирах. Текст `/shop` не меняется.

**Вне ai-dm:** нет.

## Решения

- Груминг — решения 41–53 в `docs/plan-u1.md`.
- 2026-10-23: рекомендации папы по Р1–Р8 приняты («Принять Развилки 1–8»): Р1 а, Р2 а, Р3 б, Р4 а, Р5 тексты как
  в плане, Р6 в (порог ≈ 23340 + чистка абзаца), Р7 а (пометка-факт + фраза в правилах), Р8 а.
- 2026-10-23: умолчания У1–У8 приняты.

## Разведка (проверено по коду)

- `/inv` вне боя — не ход: `GameApp.handle` → `COMMANDS["inv"]` → `inv_actions` правит бандл, `finish` кладёт заметку в
  `app.inv_notes` и автосейвит; `with_notes` (`game/app.py:210`) приклеивает «(Перед этим герой сам: …) » к следующему
  словесному ходу ровно раз. В `narrator_rules.md` этого префикса нет — мастер читает его как текст игрока. TUI:
  `is_game_line` для `/inv …` вне боя → False (варианты не чистятся), `finish_turn` при `len(words) > 1` окно не
  открывает, строки идут в ленту. Тот же путь годится для `/shop …` без правок `is_game_line`.
- Движок вне хода мастера: `fight_debug.run_fight` строит `TurnContext(bundle, registry, cfg, rng, mode="explore",
  base_registry=…)`, зовёт `apply(ctx, request)`, пишет `bundle.world.rng = rng.state`. `apply` диспетчирует по
  `HANDLERS` (`protocol/apply.py:53`) и ничего не журналирует. `ctx.events` снаружи обработчиков никто не читает
  (grep по `game/`, `master/`, `protocol/` пуст) — `apply_events` вызывается внутри обработчиков. Значит
  `apply(ctx, Service(...))` / `apply(ctx, Trade(...))` из команды самодостаточны: лимит `scene.trades`, `refuses`,
  `lodging_paid`, `boon_and_risks`, `remember_deal`, броски последствий (`ctx.add_roll(engine=True)`, строки в
  `decision.log`) — всё как у мастера.
- Отказы движка (решение 50) уже есть: `trade_pick.scene_problem` (бой → Invalid `in_combat`), `refusal_problem`
  (`rejected`, reason «<имя> отказывается торговать»), лимит сцены (`services.py:45`, `trade.py:29`),
  `short_of_money`, `lodging_paid` («ночлег уже оплачен»), `cure_service` «снимать нечего», `heal_service` «лечить
  нечего», `sell_stack` («предмет надет», «такое не скупает»). `Decision.reason` — короткая строка, годится в ленту.
- Данные для строк окна: `shop_text.sale_rows` (stock + сюжетные у держателя + ассортимент пресета; кортеж без
  `item_id` и `quality` — дополнить), `sell_lines` (логика свободных экземпляров через `sellable_stacks`, строки сразу
  текстом — вынести `sell_rows`), `kinds_of` + `quote` (услуги, все позиции, без среза), `shop_npcs` (торговцы, затем
  NPC только с услугами), `refuses`. Группы товаров: `inv_section(found, [])` даёт вкладку по `strings.INV_TABS`.
- Окна: `InvModal(title, tabs)` — вкладки `(имя, [строки])`, строка `(подпись, описание, действия, вкладка)`, действие
  `(клавиша, подсказка, строка команды, эхо)`; Enter → `actions[0]`, подсказки собираются из `actions`; текст
  приглашения `strings.INV_PICK` зашит в `compose`. `ModelModal` — список с цифрами, результат — ключ/None. Окна с
  полем ввода в `modals.py` нет; `Input` используется в `app.py`/`create.py` (Textual 8.2.8 в `uv.lock`, `Input(type=
  "integer")` поддерживается).
- Бюджет: `make prompt-budget` сегодня — explore 23235 (rules 11632 на 47647 символов ≈ 4,1 симв./токен), порог
  `STATIC_MAX = 23240` (`tests/unit/master/test_static_budget.py:45`) — запас 5 токенов: любая правка правил длиннее
  20 символов ломает тест (прецеденты — решения 30, 33: «Поднять порог», причина в комментарии теста).
- `inn_test`: торговцев (`trade`) нет, у всех семи NPC только услуги; у Брума 10 услуг, баня десятая. Торговец в тестах —
  `tests/unit/ui/test_gains_spent.py:merchant_app` (Мара, `general`).
- Тесты-образцы: `tests/unit/game/test_inv_actions.py` (команды через `GameApp.handle`), `test_shop_services.py`
  (`make_inn`), `tests/unit/ui/tui/test_tui_inv.py` и `test_tui_shop.py` (Pilot, фикстура `tui`),
  `tests/unit/master/test_prompt_services.py` (`add_provider`, `services_of`), `tests/unit/protocol/test_apply_service.py`.

## Модули / файлы / функции

Существующие (grep подтверждён): `game/commands.py: cmd_shop, HELP`; `game/inv_actions.py: finish, run, SELECT_FIRST`;
`game/shop_text.py: sale_rows, shop_item_lines, sell_lines, shop_npcs, service_lines, UNIT_WORDS`; `game/app.py:
GameApp.with_notes, INV_NOTES_PREFIX`; `game/fight_debug.py: run_fight` (образец); `protocol/apply.py: apply`;
`protocol/requests.py: Service, Trade`; `protocol/handlers/services.py: service, pay_service`; `protocol/handlers/
trade.py: trade, buy, sell`; `protocol/handlers/trade_pick.py: sellable_stacks, refusal_problem, scene_problem`;
`master/prompt.py: provider_data, services_data, SERVICE_ITEMS_MAX`; `master/prompts/narrator_rules.md` абзац «Услуги»
(:106); `ui/tui/app.py: AiDmApp.finish_turn, can_pick_item, inv_chosen, start_turn, write_echo`; `ui/tui/blocks.py:
inv_rows, inv_actions_of`; `ui/tui/inv_sections.py: inv_section, inv_tabs`; `ui/tui/modals.py: InvModal, ModelModal,
TextModal`; `ui/tui/strings.py: MODAL_TITLES, INV_PICK, INV_TABS`; `rules/services.py: kinds_of, quote`; `rules/trade.py:
merchant_buy_quote, sell_quote, refuses`; `tests/unit/master/test_static_budget.py: STATIC_MAX`.

Новые: `game/shop_actions.py` — **новый**: `run(app, arg)`, `parse(arg)` → `(verb, npc_id, item_id, qty, quality)`,
`shop_request(verb, …)` → `Service`/`Trade`, `apply_shop(app, request)` (TurnContext + `apply` + `world.rng`),
`lines_of(decision)`, `note_of(verb, npc, decision)`; `game/shop_text.py: sell_rows(hero, world, registry, npc, cfg)` —
**новая** (из `sell_lines`); `ui/tui/blocks.py: shop_rows(game, npc)` — **новая**; `ui/tui/inv_sections.py:
shop_tabs(rows)` — **новая**; `ui/tui/modals.py: ShopModal(InvModal)`, `NpcModal`, `QtyModal` — **новые**;
`ui/tui/app.py: AiDmApp.can_shop, npc_chosen, shop_chosen, qty_chosen` — **новые**; `ui/tui/strings.py: SHOP_*` —
**новые**.

## Партии

Две партии: П1 — движок, протокол и мастер (проверяется без TUI, через `GameApp.handle`, и даёт мастеру новый контекст
сразу); П2 — окно TUI поверх П1. Деление по границе слоёв: П1 ≈ 0,3 M, П2 ≈ 0,4 M (три окна + Pilot-тесты); одной
партией ревью окна и движка смешались бы, а правка правил (Р6/Р7) блокировала бы окно. Каждая — своё ревью мамы и
аудит свекрови, замер `prompt-budget` в П1.

**П1 — покупка командой, пометка мастеру, контекст без цен** (решения 43, 45, 48–51):
1. `game/shop_actions.py:run` — `arg` → `parse`: `услуга <npc_id> <service_id> [qty]`, `купить <npc_id> <item_id>
   [qty] [quality]`, `продать <npc_id> <item_id> [qty]`; `qty` по умолчанию 1; ошибка разбора → строка `USAGE`;
   `app.pending is not None` → `SELECT_FIRST` (как `inv_actions.run`). `apply_shop`: `TurnContext(app.bundle,
   runner.registry, runner.cfg, Rng.from_state(world.rng), mode="explore", base_registry=runner.base_registry)` →
   `apply(ctx, request)` → `world.rng = rng.state`. Исход: `Decision accepted|clamped` → строки `decision.log`
   (+ `reason` при clamped), заметка в `app.inv_notes`, автосейв — всё через `inv_actions.finish(app, lines, [note])`;
   `rejected` → `[reason]`, без заметки и сейва; `Invalid` → `[message]` (бой, нет NPC — на случай ручного ввода).
   Заметка (Р7, при Р7 = а): `оплатил услугу «баня» x1 у Брум Лодочник (1 сп)` / `купил «Колчан» x2 у Мары (2 зм)` /
   `продал «…» x1 Маре (…)`. Проверка: `GameApp.handle("/shop услуга grok room_modest")` → деньги списаны, флаг
   `lodging:<hero>`, `scene.trades == 1`, `inv_notes == [...]`, следующий `handle("Ложусь спать")` уходит мастеру с
   префиксом; `/shop услуга grok room_modest` второй раз → «ночлег уже оплачен», `inv_notes` пуст.
2. `game/commands.py:cmd_shop` — `if arg: return shop_actions.run(app, arg)`; `HELP["shop"]` — по Р5.
3. `master/prompt.py:provider_data` — убрать `price_cp` из `items`; срез и `haggle_state` оставить. Тесты
   `test_prompt_services.py` (`test_entry_has_exactly_the_documented_keys`, ключи позиции) — обновить (доеба).
4. `narrator_rules.md:106` — правка по «Правилу 4»; `STATIC_MAX` — по Р6 (при Р6 = а: ≈ 23340, причина в комментарии
   теста: «164: пометка о покупке из окна /shop, services без цен»). `make prompt-budget` до/после — в «Итог».
5. Регресс: `tests/unit/game/test_shop_command.py`, `test_shop_services.py` (текст `/shop` без `arg` не меняется),
   `tests/unit/protocol/test_apply_service.py`, `test_apply_trade.py` целиком.

**П2 — окно TUI** (решения 44, 46, 47, 53; Р1–Р5, Р8):
1. `game/shop_text.py` — `sale_rows` отдаёт ещё `item_id` и `quality` (stock: `entry.quality`; каталог и сюжетные:
   `None`), `shop_item_lines` распаковывает новый кортеж (текст не меняется); `sell_rows(hero, world, registry, npc,
   cfg)` → `(item_id, имя, цена, free)`; `sell_lines` строит строки из него (текст не меняется).
2. `ui/tui/blocks.py:shop_rows(game, npc)` — строки `(подпись, описание, [действие], вкладка)`: товары из `sale_rows`
   (подпись «<имя> x<qty> — <цена>», описание `item.description`/`effect_texts`, вкладка `inv_section(found, [])`,
   действие `("Enter", SHOP_BUY, f"/shop купить {npc.id} {item_id}[ {quality}]", эхо)`); продажа из `sell_rows`
   (вкладка «Продать», `("Enter", SHOP_SELL, f"/shop продать {npc.id} {item_id}", эхо)`); услуги из `kinds_of` +
   `quote` (подпись «<название> — <цена> / <единица>» как в `service_lines`, описание `kind.description`, вкладка
   «Услуги», `("Enter", SHOP_SERVICE, f"/shop услуга {npc.id} {kind_id}", эхо)`). В действии ещё потолок количества
   `cap` для окна (Р3): `min(cfg.limits.give_item_max_qty, деньги // цена, запас стека | free)`; комната на ночь и
   `cure` — `cap = 1`. Строка команды и эхо получают ` {qty}` в `qty_chosen`.
3. `ui/tui/inv_sections.py:shop_tabs(rows)` — порядок `strings.SHOP_TABS` (Р2), пустые вкладки опущены (как `inv_tabs`).
4. `ui/tui/modals.py`: `InvModal.PICK = strings.INV_PICK` (атрибут класса вместо константы в `compose`);
   `ShopModal(InvModal)` — `PICK = strings.SHOP_PICK`, буквенных биндингов нет (одно действие на строку, Enter);
   `NpcModal(title, rows)` по образцу `ModelModal` — `rows = [(npc_id, подпись `shop_head`)]`, цифра/Enter/клик →
   `npc_id`, Esc → None; `QtyModal(title, name, cap)` — `Static` с подсказкой `SHOP_QTY.format(cap=…)`, `Input(type=
   "integer", value="1")`, Enter → `int` в `1..cap` (иначе остаётся в поле), Esc → None.
5. `ui/tui/app.py`: `can_shop()` — `pending is None`, не `limit_menu`, не бой, есть NPC из `shop_npcs`, не все
   `refuses`; `finish_turn`: ветка `/shop` перед общей `TextModal` — один NPC (Р1 = а) → сразу
   `ShopModal(title, shop_tabs(shop_rows(game, npc)))` с колбэком `shop_chosen`; несколько → `NpcModal` →
   `npc_chosen(npc_id)` → `ShopModal`; `shop_chosen(action)` — `None` → фокус в ввод; `cap <= 1` → сразу
   `write_echo` + `start_turn(f"{cmd} 1")`; иначе `QtyModal` → `qty_chosen(qty)`: `None` → снова `ShopModal` (Р4 = а),
   число → `write_echo(f"{эхо} x{qty}")`, `start_turn(f"{cmd} {qty}")`. `MODALS` += новые окна (`app.py:48`: поверх окна цифры и клавиши боевого меню не
   срабатывают — `menu_ready`, `can_pick`).
6. `ui/tui/strings.py`: `SHOP_PICK`, `SHOP_NPC_PICK`, `SHOP_TABS`, `SHOP_BUY`, `SHOP_SELL`, `SHOP_SERVICE`, `SHOP_QTY`,
   форматы эха — тексты по Р5.
7. Регресс: `tests/unit/ui/tui/test_tui_shop.py` (без торговца и в бою — `TextModal`, «Здесь никто не торгует»),
   `test_tui_inv.py` целиком (рефакторинг `PICK`), `test_tui_combat_menu.py` (`MODALS`).

## Тестовые сценарии (кабан-доеба, TDD)

П1 (`tests/unit/game/test_shop_actions.py` — новый, на `make_inn`/`merchant_app`; `tests/unit/master/
test_prompt_services.py`; `test_static_budget.py`):
- `/shop услуга grok ale 2` → деньги −8 см, строка «Оплачено: эль (кружка) x2 у Грок за 8 см», `scene.trades == 1`,
  `inv_notes == ["оплатил услугу «эль (кружка)» x2 у Грок (8 см)"]`, автосейв (`saves/.../auto` обновлён, как в
  `test_inv_actions`); следующий `handle("Пью")` → `adapter.requests[-1]` player_input начинается с
  `(Перед этим герой сам: оплатил …)`; второй ход — без префикса.
- `/shop услуга grok room_modest` → флаг `lodging:<hero>`, часы мира не двигаются, `rest` не вызван; повтор → строка
  «ночлег уже оплачен», `inv_notes` без второй записи, денег не меньше.
- `/shop услуга grok ale 100` → clamped: куплено по деньгам/лимиту 20, строки log + reason «запрошено 100, оплачено N».
- `/shop услуга grok bath` при `smelly` → состояние снято, лог «вымылся» (регресс `grant_boon` через команду).
- `/shop услуга liss companion_cheap` с сидом провала → строки бросков последствий в ответе, `diseased` у героя,
  `scene.trades == 1`, память `deal` (регресс `boon_and_risks`/`remember_deal` вне хода мастера).
- Отказы: `attitude` ниже порога `refuses` → строка «Грок отказывается торговать», денег столько же, заметки нет;
  `scene.trades = ops_per_scene` → «лимит сделок за сцену: 20»; в бою (`start_combat_call`) → «во время боя не торгуют»;
  `pending = "level_up"` → `SELECT_FIRST`; `/shop купить mara nope` → Invalid `message` (не исключение);
  `/shop чепуха` и `/shop купить mara` → `USAGE`; денег 0 → «не хватает денег: …».
- `/shop купить mara quiver 2` → в инвентаре колчан ×2, деньги −2 зм, лог «Куплено: Колчан x2 за 2 зм», заметка
  «купил «Колчан» x2 у Мары (2 зм)»; `/shop продать mara dagger` → предмет ушёл в `stock`, деньги +, заметка «продал…»;
  надетый → «предмет надет». `quality` в команде → куплен стек нужного качества.
- `world.rng` после покупки с бросками ≠ до (состояние записано), без бросков — не меняется.
- `/shop` без аргумента — тот же текст, что раньше (все тесты `test_shop_command.py`, `test_shop_services.py` зелёные).
- Контекст: `services_of(ctx)[0]["items"][0]` без ключа `price_cp`, с `id`, `name`, `unit`, `description`; срез 8 и
  порядок как были; `haggle` у NPC без `trade` остаётся; `test_items_are_capped_at_eight` без изменений.
- `static_tokens("explore")["total"] <= STATIC_MAX` (новый порог по Р6), фактическое число — в «Итог».

П2 (`tests/unit/ui/tui/test_tui_shop.py` + новый `test_tui_shop_modal.py`; `tests/unit/game/test_shop_text.py` для
`sale_rows`/`sell_rows`):
- `shop_rows` у Брума (`inn_test`-подобный NPC без `trade`, 10 услуг) → 10 строк на вкладке «Услуги», подписи как в
  `service_lines` («баня — 1 сп / раз»), действие одно, команда `/shop услуга innkeeper_brum bath`, `cap` по деньгам.
- `shop_rows` у Мары: товары по вкладкам инвентаря (колчан → «Боеприпасы»), stock ×N с ценой торговца и `quality`
  в команде, сюжетный предмет у держателя — строка с его ценой; «Продать» — только то, что `sell_lines` показывает
  (надетый экземпляр не предлагается, `free` в `cap`); дороже кошелька — строка есть, `cap == 0` (Р8).
- `shop_tabs` — порядок `SHOP_TABS`, пустые опущены; NPC только с услугами → одна вкладка «Услуги».
- Pilot: `/shop` без NPC → `TextModal`; с одним NPC → сразу `ShopModal` (Р1 = а), заголовок «Торговля», подсказка
  `SHOP_PICK`; с двумя (Тобб + Мара) → `NpcModal`, цифра `2` → `ShopModal` с товарами второго; Esc в `NpcModal` →
  фокус в ввод, хода нет (`adapter.requests == []`).
- Pilot: Enter на «баня» при `cap == 1` → без вопроса количества, в ленте эхо «Оплатить: баня у Брума», строка
  «Оплачено: …», «Потрачено: −1 сп» в `#gains`, деньги в `#status`; `adapter.requests == []` (мастер не звался).
- Pilot: Enter на «эль» при `cap >= 2` → `QtyModal`, ввод `3` Enter → команда `/shop услуга … ale 3`, эхо «… x3»;
  ввод `0`/`99`/пусто → окно не закрывается; Esc → снова `ShopModal` (Р4 = а), хода нет.
- Pilot: в бою `/shop` → `TextModal` (как сейчас); `pending` (меню уровня) → `TextModal`; все NPC отказывают →
  `TextModal` с «отказывается торговать».
- Pilot: ←/→ меняют вкладку «Услуги» ↔ «Боеприпасы» у торговца с услугами; описание строки — `kind.description`;
  клавиши `e/l/u/r/d` в `ShopModal` ничего не делают.
- Регресс `InvModal`: подсказка `INV_PICK` на месте после рефакторинга `PICK`; `MODALS` содержит новые окна
  (`isinstance(app.screen, MODALS)` для `ShopModal`, `NpcModal`, `QtyModal` — цифра поверх окна не идёт в боевое меню).
- Руками (`inn_test --preset grim`): в «Медном котле» `/shop` → `NpcModal` (Брум, Лисса, Марек, Тильда) → Брум →
  вкладка «Услуги» с десятью позициями, баня на месте; Enter на бане → строка оплаты, «вонь» снята, следующий ход
  мастер описывает баню, не вызывает `service` повторно (проверить `calls-*.jsonl`); комната → оплата, «ложусь спать» →
  мастер зовёт `rest long`; на площади Тобб/Мара — выбор NPC; в бою `/shop` — текст.

## Развилки и риски

- **Р1 — один NPC в локации.** (а) сразу окно его товаров и услуг, без списка NPC; (б) список NPC всегда, даже из
  одного. Рекомендую (а): лишний Enter у Брума в трактире ни к чему; решение 46 говорит о «нескольких NPC».
- **Р2 — вкладки окна (состав и порядок).** (а) вкладки инвентаря по типу товара (`INV_TABS` без «Надето»: Оружие,
  Боеприпасы, Доспехи, Расходники, Снаряжение, Ценности, Сюжетное) → «Продать» → «Услуги» — порядок, как в тексте
  `/shop` (товары, «Продать:», «Услуги:»); (б) то же, но «Услуги» первой вкладкой; (в) три вкладки «Купить» / «Продать» /
  «Услуги» без деления товаров по типу. Рекомендую (а): один порядок с текстом и те же разделы, что в окне `/inv`
  («как в инвентаре», решение 53); у NPC без товаров (весь `inn_test`) остаётся одна вкладка «Услуги».
- **Р3 — когда окно спрашивает количество.** (а) всегда после Enter (буквально решение 44); (б) не спрашивать, когда
  движок всё равно берёт одну (комната на ночь — `pay_service` ставит `qty = 1`; обряд `cure` — `qty` не важен) и
  когда потолок 1 (денег или запаса хватает на одну). Потолок `cap = min(20, деньги // цена, запас / свободные
  экземпляры)`, ввод вне `1..cap` окно не принимает. Рекомендую (б).
- **Р4 — Esc в вопросе количества.** (а) назад в окно товаров того же NPC (с первой вкладки — положение вкладки не
  храним); (б) закрыть всё. Рекомендую (а).
- **Р5 — тексты окна и ленты** (предложения, принять списком или поправить): приглашение `SHOP_PICK` «Товар или услуга
  (←/→ — раздел, Enter — выбрать, Esc — закрыть):»; `SHOP_NPC_PICK` «У кого (цифра, щелчок или Enter, Esc — закрыть):»
  со строками `shop_head` («Брум Лодочник — услуги», «Мара (general) — кошелёк торговца: 50 зм»); подсказки под
  описанием «Enter — Купить» / «Enter — Продать» / «Enter — Оплатить»; `SHOP_QTY` «Сколько? (1–{cap}, Enter —
  подтвердить, Esc — назад)»; эхо в ленте «Купить: Колчан x2 у Мары», «Продать: Кинжал x1 Маре», «Оплатить: баня x1 у
  Брума»; строки движка — `decision.log` как есть («Оплачено: баня x1 у Брум Лодочник за 1 сп», «Куплено: Колчан x2 за
  2 зм»), отказ — `reason` как есть («Брум Лодочник отказывается торговать», «не хватает денег: нужно 1 сп, есть 3 см»);
  `/help shop` — без подкоманд (служебные, ids игрок не видит; как `/model` окно). Альтернатива: добавить в `HELP`
  «услуга|купить|продать <npc> <id> [кол-во]».
- **Р6 — статический бюджет.** Правка абзаца «Услуги» (Правило 4) ≈ +330 символов ≈ +80 токенов: 23235 → ≈ 23315 при
  `STATIC_MAX = 23240`. (а) поднять порог до ≈ 23340 с причиной в комментарии теста (прецеденты — решения 30, 33);
  (б) ужать соседние фразы абзаца до нулевого прироста (кабан режет формулировки, смысл не теряем); (в) (а) + убрать
  из абзаца ставшее лишним («цены, `unit` и `description` — в ключе `services` состояния»). Рекомендую (в): порог
  растёт меньше, лишнее уходит.
- **Р7 — как мастер узнаёт о покупке из окна.** (а) пометка-факт «Перед этим герой сам: оплатил услугу «баня» x1 у
  Брум Лодочник (1 сп)» + фраза в правилах: деньги списаны, повторно `service`/`trade` не вызывать, комната — только
  оплата (Правило 4, стоит Р6); (б) факт + инструкция прямо в пометке («…деньги списаны движком, service не вызывай»),
  правила не трогаем, статика не растёт, но инструкция едет в каждом таком ходе и в `player_input`. Рекомендую (а):
  дисциплина инструментов — в правилах, пометка остаётся фактом, как у `/inv`. Риск без фразы: мастер видит «оплатил
  баню», зовёт `service buy bath` и списывает второй раз.
- **Р8 — товар дороже кошелька.** (а) строка в окне с ценой, Enter → отказ движка «не хватает денег» (решение 50 —
  отказы движка; `cap == 0` → количество не спрашиваем); (б) строка помечена «нет денег» и не выбирается (как «нет
  ячейки» в `SpellModal`). Рекомендую (а): цены видны, поведение единое с мастером, кода меньше.
- **Риски.** (1) Двойная покупка мастером — Р7. (2) `boon_and_risks` вне хода: броски последствий в `ctx.rolls`
  никуда, кроме `decision.log`, не идут — строки бросков в ленте есть, панели `#rolls` нет (как у `/inv выпить`);
  приемлемо, отметить в «Итог». (3) `scene.trades` растёт от покупок из окна — лимит 20 общий с мастером (решение 50
  это и подразумевает). (4) `is_game_line("/shop …")` → False — варианты хода на экране не чистятся, как у `/inv`;
  `show_step` всё равно обновляет `#hero`/`#status`. (5) `sale_rows`/`sell_lines` меняют форму кортежа — регресс
  `test_shop_command.py`, `test_shop_services.py`, `test_inv_prices.py`; старые мутанты `shop_lines` (BACKLOG 84, по
  ROADMAP «при касании») — разобрать только на новых строках, остальное остаётся в 84. (6) `QtyModal` — первое окно с
  `Input` внутри `ModalScreen`: фокус и Enter в Textual 8 проверить Pilot-тестом до логики. (7) Простой режим: окна
  нет, подкоманды доступны, но без ids бесполезны — не регресс, `/shop` текст прежний.

## Умолчания (внутреннее)

- У1. Имена: модуль `game/shop_actions.py`; глаголы подкоманд `услуга`, `купить`, `продать` (строка команды —
  протокол окна, как `/inv надеть <id>`), формат `/shop <глагол> <npc_id> <id> [qty] [quality]`, `qty` по умолчанию 1,
  `quality` только у `купить` (стек торговца: `junk|worn|used`; каталог — без слова → `Trade.quality = "any"`);
  `USAGE` по образцу `inv_actions.USAGE`. Окна `ShopModal`, `NpcModal`, `QtyModal`; строки `SHOP_*` в `strings.py`;
  кортеж действия тот же, что у `/inv`, с пятым элементом `cap` (при Р3 = б; при Р3 = а — `cap` всё равно нужен для
  верхней границы).
- У2. `TurnContext` для команды — как в `run_fight`; `ctx.rolls`/`ctx.events` после `apply` не читаем; журнал
  `calls-*.jsonl` не пишем (как `/inv`); `boundary_pending` не проверяем (как `inv_actions`; `run_fight` проверяет —
  там старт боя).
- У3. Заметка мастеру — одна строка на сделку в `app.inv_notes` (при Р7 = а — только факт; формат «оплатил услугу
  «<имя>» x<qty> у <npc.name> (<сумма>)», «купил «<имя>» x<qty> у <npc.name> (<сумма>)», «продал «<имя>» x<qty>
  <npc.name> (<сумма>)»); при `rejected`/`Invalid` заметки нет.
- У4. `provider_data`: убираем только `price_cp`; `unit`, `description`, `haggle` остаются (мастеру «за ночь»/«за
  порцию» и описание нужны для сцены, цен — нет). `services_item` (`id` услуг в `scene_npcs`) не трогаем. Текст `/shop`
  и `service_list` (`service` list) с ценами — без изменений (решение 49: мастер может продать сам, цену узнаёт list).
- У5. `sale_rows` → `(порядок, имя, цена, qty, группа, item_id, quality)`; `sell_rows` → `(item_id, имя, цена, free)`,
  `sell_lines` = форматирование `sell_rows`. Вкладка товара — `inv_section(found, [])`; сюжетный предмет у держателя —
  по его `found`.
- У6. `ShopModal` наследует `InvModal`: `PICK` — атрибут класса (единственная правка `InvModal`), биндинги букв
  остаются у родителя, но действий с такими клавишами в строках окна нет — `action_act` ничего не находит.
  `NpcModal.rows = [(npc_id, shop_head(npc, world, cfg))]`; отказывающие NPC в список не попадают (окно их не продаст),
  но текстовая строка «отказывается торговать» остаётся в `/shop` без аргументов.
- У7. Тесты: `tests/unit/game/test_shop_actions.py`, `tests/unit/game/test_shop_text.py` (новые), правки
  `tests/unit/master/test_prompt_services.py`, `test_static_budget.py`, `tests/unit/ui/tui/test_tui_shop.py`
  (+ новый `test_tui_shop_modal.py`); mutmut `FUNCS`: П1 — `ai_dm.game.shop_actions:run`, `shop_actions:parse`,
  `shop_actions:shop_request`, `shop_actions:apply_shop`, `shop_actions:lines_of`, `shop_actions:note_of`,
  `ai_dm.game.commands:cmd_shop`, `ai_dm.master.prompt:provider_data`; П2 — `ai_dm.game.shop_text:sale_rows`,
  `shop_text:sell_rows`, `shop_text:sell_lines`, `shop_text:shop_item_lines`, `ai_dm.ui.tui.blocks:shop_rows`,
  `ai_dm.ui.tui.inv_sections:shop_tabs`, `ai_dm.ui.tui.app:AiDmApp.can_shop`, `AiDmApp.finish_turn`,
  `AiDmApp.npc_chosen`, `AiDmApp.shop_chosen`, `AiDmApp.qty_chosen`, `ai_dm.ui.tui.modals:QtyModal.on_input_submitted`,
  `NpcModal.action_pick` (имена методов новых окон — за кабаном, список уточнить по diff).
- У8. `make prompt-budget` до/после П1 — в «Итог»; `make smells` — `finish_turn` уже длинная цепочка `elif`: ветку
  `/shop` вынести в `shop_modal(title)` по образцу `lore_modal`, чтобы не поднять сложность (правило нулевого баланса).

## Открытые вопросы

1. Р6/Р7 — порог `STATIC_MAX` и способ сообщить мастеру о покупке (`narrator_rules.md:106`, `test_static_budget.py:45`,
   `game/app.py:210 with_notes`): варианты выше; рекомендую Р7 = а и Р6 = в; разблокирует П1 п. 4; решает проектировщик.
   Блокирующий для П1.
2. Р1–Р5, Р8 — вид окна (`ui/tui/app.py:443 finish_turn`, `modals.py:147 InvModal`): рекомендации выше; разблокирует
   П2; решает проектировщик. П1 от них не зависит.

## Правки по ревью

П1 (2026-10-23):
- Мама: `title_of` берёт `app.registry`, а сделка — `runner.registry`. Кабан проверил: `GameApp.registry` — property на
  `self.runner.registry` (`game/app.py:152`), объект один; кода не меняли.
- Мама: тест `/shop услуга grok ale 0` (Invalid, без заметки и сейва) — добавил доеба.
- Мама/свекровь: в FUNCS mutmut добавлена `shop_actions:title_of` (новая вспомогательная функция, не в У7).
- Расхождения с примерами плана приняты по У3/Р5 (мама, оркестратор): имена NPC в заметке без склонения («у Мара»),
  цены в мм/см через `format_cp`, лог еды «Заказано:».
- mutmut: 7 выживших в `shop_actions`; `parse_19` убит тестом `test_parse_without_quality_gives_none`; `shop_request_29`,
  `apply_shop_11/16/17/18/19` эквивалентны (умолчания `Trade.quality`, `TurnContext.base_registry`/`mode`) — доеба.
- Замеры: prompt-budget explore.total 23235 → 23325 (`STATIC_MAX` 23340), cov 98,06 %, smells 199, dead чисто.

## Итог

П1 (2026-10-23, 17:20–18:00): kaban opus 85k + правка 1k; kaban-doeba opus 94k + правка 1k; разбор мутантов
kaban-doeba sonnet 35k; mama-kaban opus 44k + повтор 20k; kaban-svekrov opus 40k + повтор 21k. Тесты: +47
(`test_shop_actions.py`), 8 переписаны (`test_prompt_services.py`); полный прогон 21266 passed. Риск 2 остаётся:
броски последствий покупки из окна видны только строками в ленте, панели `#rolls` нет.

## Смета (кабан-тесть, режим 1)

Платных позиций, кроме токенов конвейера, нет (живые вызовы API рассказчика — только у пользователя, в смету не входят).
Источник токенов — последний «Итог» в `docs/` (`docs/plan-u0.md`, три партии, 50,35 M). Допущение: роли партий
(kaban, kaban-doeba, mama-kaban, kaban-svekrov, оркестратор) × 2/3 (две партии вместо трёх, объём П1 ≈ 0,3 M +
П2 ≈ 0,4 M строк диффа по плану); papa-kaban × 0,5 (план уже написан, осталась редакция по Р1–Р8); svinopas и
тесть — как в У0. Модели — `model:` из `~/.claude/agents/<роль>.md`; $ — тариф metrics.py от 2026-10-17
(opus/fable: $4 вход, $5 запись кэша, $0,20 чтение кэша, $20 выход за M; sonnet — вдвое дешевле), средняя цена M
каждой роли — из «Итога» У0.

| Партия | Время |
|---|---|
| груминг + план (сделано) + редакция по Р1–Р8 | ≈ 30 мин после ответов проектировщика |
| П1 — команда, пометка, контекст без цен | ≈ 90 мин (+ mutmut фоном) |
| П2 — окно TUI, Pilot-тесты | ≈ 120 мин (риск 6: `Input` в `ModalScreen`) |
| итого | ≈ 240 мин |

| Роль | Модель | Токены | $ (тариф metrics.py 2026-10-17) |
|---|---|---|---|
| оркестратор | opus | ≈ 11,2 M | ≈ 5,40 |
| papa-kaban | fable (цены Opus) | ≈ 1,7 M | ≈ 1,75 |
| kaban | sonnet | ≈ 10,5 M | ≈ 2,70 |
| kaban-doeba | sonnet | ≈ 7,6 M | ≈ 2,05 |
| kaban-svekrov | opus | ≈ 0,8 M | ≈ 1,00 |
| mama-kaban | opus | ≈ 0,7 M | ≈ 0,70 |
| kaban-test | opus | ≈ 0,4 M | ≈ 0,80 |
| svinopas | opus | ≈ 0,4 M | ≈ 0,30 |
| итого | | ≈ 33 M | ≈ 14,70 |
