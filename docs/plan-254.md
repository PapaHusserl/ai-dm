# Шаг 254. Окно торговли: серия сделок за одно открытие

Контур: вне msa; режим: встроить. Папа-кабан, 2026-11-09, HEAD `fac836e`.
Входы: груминг свинопаса с добором и аудит свекрови (scratchpad сессии), BACKLOG 254, ROADMAP:208,
docs/plan-roadmap-r13.md (Р1), решения Влада 2026-11-09 (ниже).

## Решения

Влад, 2026-11-09 (окна по вопросам груминга свинопаса 1–4 и добора А1–А5; через оркестратора):

1. Окно не закрывается после сделки: Enter — сделка сразу прошла, строка обновилась, курсор на месте.
   Корзины нет. (вопрос 1 = 1, по рекомендации)
2. В окне сверху две строки: «Деньги: X · Кошелёк торговца: Y» и итог последней сделки или отказ.
   В ленте всё как сейчас. (вопрос 2 = 1, по рекомендации)
3. Мастер и время как сейчас: часы стоят, мастер молчит, на следующем словесном ходе получает приписку
   (решение Р7 а 164, `docs/plan-164.md:241-246`). (вопрос 3 = 1, по рекомендации)
4. Лимит сделок за сцену поднять с 20 до 50 всем — и окну, и мастеру. (вопрос 4 = 2, по рекомендации)
5. Серию заканчивает только Esc. (А1 = 1, по рекомендации)
6. Окно остаётся открытым и после услуг. (А2 = 1, по рекомендации)
7. Несколько торговцев: Esc из окна — сразу в игру, сменить торговца — снова `/shop` (как сейчас).
   (А3 = 1; рекомендация свинопаса была 2 — Esc к списку торговцев)
8. Шаг только про окно TUI, простой режим как есть, пункта в беклог про него нет. (А4 = 1)
9. Рассказчику одинаковые сделки склеить: «купил «Зелье» x2 у Мары (1 зм)», остальное как есть.
   (А5 = 2; рекомендация свинопаса была 1 — каждая отдельно)

Влад, 2026-11-09 (окна по развилкам плана, все по рекомендации папы):

10. Р1 = 1: набор вкладок фиксирован при открытии окна; опустевшая вкладка остаётся, новая категория — при следующем `/shop`.
11. Р2 = 1: у NPC без `trade` строка только «Деньги: X».
12. Р3 = 1: вторая верхняя строка до первой сделки пустая.
13. Р4 = 1: итог сделки в окне — все строки, что уходят в ленту (итог, урезание, отказ).
14. Умолчания папы приняты: склейка приписки действует и для набранной `/shop`, в том числе в простом режиме (уточняет решение 8); качество вещи склейку не разделяет.

Влад, 2026-11-10 (окна по ревью П1, все по рекомендации папы; вопросы — абзац «Вопросы Владу из круга 1» в конце
п. 6 «Правок по ревью»):

15. `on_shop_modal_picked` — строкой в `vulture_allowlist.py`, как соседние обработчики Textual (п. 4 = 1).
16. BACKLOG 296 остаётся (idea, низкий приоритет); нет пауз в живом прогоне — при закрытии шага снять с причиной (п. 5 = 1).
17. `start_me_after_reboot` из корня репо удалить (п. 6 = 1).
18. Проверки перед коммитом — режим «долго» (`taskpolicy -b`, по очереди, 4 потока): mutmut, cov, один повтор mutmut (по рекомендации папы).
19. mutmut: догнать только 34 мутанта новых строк (по рекомендации папы, 04:47). Ответ пришёл в 09:49, когда прогон дошёл до 659 из 670: оркестратор его не останавливал, прогон доходит целиком (проверка шире выбранной).
20. Второй повтор mutmut по `update_20` — запустить (окно 12:19, по правилу testy.md); cov не повторять, src не менялся.
21. Живой прогон отложен; шаг закрыть и закоммитить без него (Влад, 2026-11-10 12:27, окно; рекомендации не было).
   Долг — строкой в handoff; BACKLOG 296 решается по итогам отложенного прогона.

Решения из прошлых шагов, на которые план опирается: 45–47, 50, 52, 53 (`docs/plan-u1.md:74-83`, Влад,
2026-10-23) — услуги, покупка и продажа в одном окне, только отказы движка, без новых полей сейва, клавиши как
у InvModal; Р7 а (`docs/plan-164.md:241`) — приписка-факт мастеру на следующем ходе; 10 и 16 ФД2
(`docs/plan-fd2.md`) — товар прилавка в `trade.stock` покупается как обычный.

## Суть

**Задача:** окно `/shop` в TUI не закрывается после сделки; после каждой сделки строки пересчитываются,
вкладка и курсор на месте, сверху — деньги героя, кошелёк торговца и итог последней сделки. Плюс два
маленьких изменения вне окна: лимит сделок за сцену 20 → 50 и склейка одинаковых сделок в приписке мастеру.

**Правило** (было → станет):

- `ShopModal` наследует `InvModal.on_option_list_option_selected`: было `self.dismiss(actions[0])`
  (`src/ai_dm/ui/tui/modals.py:208-211`) → станет `self.post_message(self.Picked(actions[0]))` + `event.prevent_default()`
  (новый переопределённый метод в `ShopModal`; `npc_id` из `Picked` убран — правки по ревью 1, 6); окно живёт до Esc
  (`action_close` → `dismiss(None)` без изменений).
- `ops_per_scene = 20` (`src/ai_dm/config/defaults.toml:153`, `settings.py:309` `Field(default=20, ge=1)`)
  → `50` в обоих местах.
- Заметка мастеру: было `app.inv_notes += [note]` на каждую сделку (`game/inv_actions.py:43` через
  `shop_actions.run`) → станет: заметка той же сделки (тот же NPC, тот же вид, тот же товар или услуга)
  заменяется в `inv_notes` на месте суммой `qty` и `total_cp` («купил «Зелье» x2 у Мары (1 зм)»);
  разные сделки — как сейчас.

**Поведение:** меняется — только окно `/shop` в TUI (`ui/tui/app.py`, `modals.py`, `shop_blocks.py`,
`strings.py`); текст отказа «лимит сделок за сцену: 50» — везде, где лимит срабатывает (окно, набранная
команда, инструменты мастера `trade`/`service`); склейка приписки — везде, где идёт `shop_actions.run`
(окно и набранная команда `/shop купить …`, в т. ч. простой режим; отдельного пути для окна нет и делать
его незачем — приписки простого режима мастер читает так же). Простой режим окна не имеет — решение 8.

**Поправка к карте** (аудит свекрови «[неточно]», свинопас «Вердикт»): BACKLOG 254 пишет «одна сделка — один
ход». Неверно: сделка из окна — команда `/shop …`, `is_game_line` даёт False (`ui/tui/app.py:431-438`),
мастер не зовётся, часы стоят (`docs/rules-adaptation.md:61`). Цель шага — жизнь окна, не слияние ходов. Тело
пункта в карточке done копируется без правок (RULES), поправка — здесь. Связи с 133 (ассортимент) и Л1
(перемещение) нет — аудит свекрови, строки 42–43; при закрытии шага убрать «связь 133» из строки ROADMAP:208
и записать реальный состав файлов вместо «только `ShopModal`».

**Вне репо:** нет.

## Файлы

Все функции найдены grep-ом 2026-11-09, кроме помеченных «новая».

| Файл | Функция | Что |
|---|---|---|
| `src/ai_dm/ui/tui/modals.py` | `ShopModal` (224–232) | `__init__(title, tabs, npc_id, head)` без дефолтов; класс сообщения `Picked(action)` (как `Choices.Picked` в `widgets.py:78`; `npc_id` в сообщении не нужен — правка по ревью 6); `compose` — своя или хук `head_widgets()` у `InvModal` (по умолчанию пусто), у `ShopModal` — `Static(id="shop-head")` над `#inv-title`; `on_option_list_option_selected` — `post_message(Picked)` вместо `dismiss`; `update(rows, head)` — новая: перегруппировать `rows` по **тем же вкладкам** (`self.tabs`, пустые не выкидывать — Р1), `fill(активная вкладка)`, вернуть подсветку на `min(старый индекс, len(rows) − 1)`, при пустой вкладке очистить описание; `head` → `#shop-head` |
| `src/ai_dm/ui/tui/modals.py` | `InvModal.fill` (178) | без изменений, если `update` сам ставит `highlighted` после `fill`; при пустой вкладке — `show_description` не вызывается, описание надо очистить в `update` |
| `src/ai_dm/ui/tui/app.py` | `show_shop` (569) | `ShopModal(title, shop_tabs(rows), npc_id, [shop_money(game, npc)])`; `push_screen(modal, self.shop_closed)` — коллбэк только для Esc (`None`) |
| `src/ai_dm/ui/tui/app.py` | `shop_chosen` (574); `shop_closed` — новая | ветка `action is None` уходит в `shop_closed` (фокус в поле ввода, как сейчас 575–577); сигнатура `shop_chosen(action)` — `npc_id` убран (правка по ревью 6); остальное без изменений: `cap <= 1` → `start_turn`, иначе `QtyModal` поверх открытого `ShopModal` |
| `src/ai_dm/ui/tui/app.py` | `on_shop_modal_picked` — новая | `if self.busy: return` (защита от второго Enter, пока сделка идёт); иначе `shop_chosen(event.action)` |
| `src/ai_dm/ui/tui/app.py` | `qty_chosen` (587) | сигнатура `qty_chosen(action, qty)` (правка по ревью 6); `qty is None` → `return` (ShopModal уже под окном количества; `show_shop` тут больше не зовётся) |
| `src/ai_dm/ui/tui/app.py` | `finish_turn` (456) | после `show_step`: если `command == "/shop"`, `len(words) > 1` и `isinstance(self.screen, ShopModal)` — `refresh_shop(step)` вместо `entry.focus()`; `entry.disabled = False` остаётся |
| `src/ai_dm/ui/tui/app.py` | `refresh_shop(step)` — новая | `npc = world.npcs[self.screen.npc_id]`; `self.screen.update(shop_rows(self.game, npc), [shop_money(self.game, npc), *modal_lines(step.blocks)])`; вынесено из `finish_turn`, чтобы не растить его ветвление (smells) |
| `src/ai_dm/ui/tui/shop_blocks.py` | `shop_money(game, npc)` — новая | `strings.SHOP_MONEY.format(money=format_cp(hero.money_cp), purse=format_cp(purse_now(npc.trade, now_s, cfg)))`; у NPC без `trade` — `strings.SHOP_MONEY_PLAIN` (Р2); `purse_now` — `rules/trade.py:143`, как в `shop_text.shop_head:111` |
| `src/ai_dm/ui/tui/strings.py` | константы | `SHOP_MONEY = "Деньги: {money} · Кошелёк торговца: {purse}"`, `SHOP_MONEY_PLAIN = "Деньги: {money}"` (текст — решение 2) |
| `src/ai_dm/ui/tui/app.tcss` | `#shop-head` | высота `auto`; строки окна: head + hint + tabs 2 + list ≤ 14 + body ≤ 12 — в 40 строк экрана входит (max-height 90 %) |
| `src/ai_dm/game/shop_actions.py` | `note_of` (75) | принимать (вид сделки, направление, title, имя NPC, qty, total_cp) — чистый текст, чтобы собрать и старую, и новую заметку |
| `src/ai_dm/game/shop_actions.py` | `remember(app, request, npc, decision, title)` — новая | ключ `(request.type, direction, npc.id, item_id или service_id)`; `old = app.deals.get(key)`; если есть — заменить в `app.inv_notes` сохранённый старый текст `old[2]` на месте текстом с `qty + old_qty`, `total_cp + old_cp`; иначе добавить; `app.deals[key] = (qty + old_qty, total_cp + old_cp, note)` — накопленная сумма и текст заметки (правки по ревью 4, 8) |
| `src/ai_dm/game/shop_actions.py` | `run` (86) | `note = remember(...)`; `finish(app, lines_of(outcome), [note] если новая, иначе [])` |
| `src/ai_dm/game/app.py` | `GameApp.__init__` (158), `with_notes` (222–228), `load` (487) | `self.deals = {}` рядом с `inv_notes`; сбрасывать вместе с `inv_notes` в `with_notes` и `load` (в памяти, не в сейве — решение 52 «без новых полей сейва» держится) |
| `src/ai_dm/config/defaults.toml` | строка 153 | `ops_per_scene = 50` |
| `src/ai_dm/config/settings.py` | строка 309 | `Field(default=50, ge=1)` |
| `tests/unit/config/test_trade_config.py` | строки 4 (комментарий), 26, 69 | `20` → `50` (grep `ops_per_scene` по tests/ — остальные места берут `cfg.trade.ops_per_scene` символически и не меняются; `cap=20` в `test_tui_shop_modal.py:497` — это `limits.give_item_max_qty`, другой лимит, не трогать) |
| `tests/unit/ui/tui/test_tui_shop_modal.py` | 6 Pilot-тестов исходят из закрытия окна: `assert depth == 1` в строках 412, 430, 445, 512, 531, 544 | станет `depth == 2` и `isinstance(app.screen, ShopModal)`; остальные (633 Esc из количества, 657 два Esc, 466 подмена `start_turn`) проходят как есть — проверить прогоном |
| `tests/unit/ui/tui/test_tui_shop_modal.py`, `test_tui_shop_blocks.py`, `tests/unit/game/test_shop_actions.py`, `tests/unit/game/test_game_app.py` или `test_game_load_trade.py` | новые тесты | раздел «Тесты» |

**Объём:** одна партия; код ≈ 110 строк src (modals ≈ 30, app ≈ 20, shop_blocks ≈ 10, strings 2, shop_actions ≈ 25,
game/app 3, config 2) + тесты ≈ 250 — оценка по плану, не проверено; < 400.

**Не трогаем:** `protocol/handlers/trade.py`, `services.py` (лимит читают из конфига), `InvModal` для `/inv`
(переопределение только в `ShopModal`), `NpcModal`, `QtyModal`, `shop_text.py`, простой UI, промпт
(`STATIC_MAX` 24830 не задет: `INV_NOTES_PREFIX` — динамический вход, не статика).

## Партии

Одна партия (П1). Делить на «окно» и «лимит + склейка» (как 164 П1/П2) не стоит: вторая часть ≈ 30 строк
и трогает только `shop_actions`, `game/app.py`, конфиг — отдельного ревью движка не требует.

1. Конфиг и тесты лимита — `defaults.toml:153`, `settings.py:309`, `test_trade_config.py:4,26,69` →
   `uv run pytest -q tests/unit/config tests/unit/protocol/test_apply_trade.py tests/unit/protocol/test_apply_service.py`
   зелёные; отказ после 50 сделок: «лимит сделок за сцену: 50».
2. Склейка приписки — `shop_actions.note_of`/`remember`/`run`, `game/app.py` (`deals`) → тесты
   `tests/unit/game/test_shop_actions.py` старые зелёные (заметки одиночных сделок не меняются: строки 168,
   174, 219, 334, 384), новые — ниже.
3. Строка денег — `shop_blocks.shop_money`, `strings.SHOP_MONEY*` → `test_tui_shop_blocks.py` (торговец /
   NPC с услугами).
4. Окно — `ShopModal` (`Picked`, `head`, `update`), `app.py` (`show_shop`, `shop_closed`,
   `on_shop_modal_picked`, `qty_chosen`, `finish_turn` → `refresh_shop`), `app.tcss` → Pilot-тесты;
   `uv run ruff check src tests`.
5. Перед коммитом по AGENTS: `make cov` (≥ 94 %), `make smells` (≤ 200; базу не замерял — `finish_turn` с
   новой ветвью рискует +1, поэтому `refresh_shop` отдельным методом), `make dead`,
   `make mutate FUNCS="…" TESTS="…"` (список в «Тестах»), `make mutate-diff`.
6. Живой прогон Влада (решение 2026-10-19): торговец с товаром и услугами, 3–5 сделок подряд, в т. ч. отказ
   (денег нет) и продажа до конца стека; два торговца в локации — Esc из окна в игру.

## Тесты

Для кабана-доебы (TDD). «ожидание, не проверено» — везде, где не сказано иначе; прогона нового кода нет.

Pilot (`tests/unit/ui/tui/test_tui_shop_modal.py`, хелперы `shop_game`, `choose`, `enter_qty`, `option_texts`):

- `/shop` у Грока (услуги), Enter на «эль», количество 3 → `len(screen_stack) == 2`,
  `isinstance(app.screen, ShopModal)`, в ленте «▸ Ты: Оплатить: эль (кружка) (Грок) x3» и «Заказано: эль
  (кружка) x3», в `#gains` «Потрачено: −1 см 2 мм», `#shop-head` содержит «Деньги: 13 зм 8 см 8 мм» (1400 − 12)
  и «Заказано: эль (кружка) x3»; `adapter.requests == []`. (переделка 502–517)
- Строка денег у Грока без `trade` — только «Деньги: …», слов «Кошелёк торговца» нет (при Р2 = 1).
- У Мары (`trade`, purse 5000) купить Колчан x2 → `#shop-head` «Деньги: 12 зм · Кошелёк торговца: 50 зм»
  (кошелёк от покупки героя не меняется — `handlers/trade.py:173` тратит его только на скупку; правка по ревью 5),
  вкладка та же, курсор на той же строке, подпись строки пересчитана (cap по деньгам).
- Деньги 0, Enter на «эль» → окно открыто, `#shop-head` содержит «не хватает денег», деньги 0. (переделка
  421–434)
- Продать: у героя Колчан x3, продать 2 → строка «Колчан x1 — …» на той же позиции; продать последний →
  строки нет, подсветка на соседней строке (или вкладка пуста — список без строк, описание пустое).
- Esc из окна после двух сделок → `screen_stack == 1`, фокус `input`, мастер не вызван (решения 5, 7).
- Esc в окне количества → снова тот же `ShopModal`, `screen_stack == 2`, без сделки (633 — как есть).
- Два Enter подряд, пока первая сделка идёт: `app.busy = True`, `app.on_shop_modal_picked(Picked(action))` →
  `start_turn` не вызван (юнит-тест на обработчик с подменой `start_turn`, как в 466–477).
- Комната (cap 1) → оплата без вопроса количества, окно открыто (переделка 403–418); вторая комната — отказ
  в `#shop-head`.
- Вкладка «Услуги» активна, сделка → после обновления активна «Услуги» (не первая).
- Лента: после трёх сделок три «▸ Ты:» и три строки итога — «в ленте всё как сейчас» (решение 2).

`tests/unit/game/test_shop_actions.py` (хелперы `make_inn`, `merchant_app`, `add_mara`):

- `/shop услуга grok ale 2` дважды → `app.inv_notes == ["оплатил услугу «эль (кружка)» x4 у Грок (1 см 6 мм)"]`
  (8 мм + 8 мм — формат `format_cp(16)` проверить прогоном).
- Купить Колчан 1, продать Кинжал 1, купить Колчан 1 → две заметки, первая «купил «Колчан» x2 у Мара (2 зм)»,
  вторая «продал «Кинжал» x1 Мара (…)» — склейка на месте, порядок прочих не меняется.
- Купить и продать один и тот же товар — две заметки (направление в ключе).
- Словесный ход между двумя покупками (`with_notes`) → заметки не склеиваются: после хода `app.deals == {}`,
  вторая покупка даёт новую заметку x1.
- `load` сбрасывает `deals` вместе с `inv_notes` (`tests/unit/game/test_game_load_trade.py` или рядом с
  тестами `inv_notes` в `test_travel_actions.py:175`).
- Отказ (`rejected`) и `Invalid` заметку и `deals` не трогают (есть 244–317 — дополнить `app.deals == {}`).
- Переименование NPC между двумя одинаковыми покупками (`npcs["mara"].name = "Марта"`) → одна заметка под новым
  именем «купил «Колчан» x2 у Марта (2 зм)», третья покупка — x3 (3 зм); `ValueError` нет (правка по ревью 8).

`tests/unit/config/test_trade_config.py`: `trade().ops_per_scene == 50` (26), кортеж (69), комментарий (4).

Проверка в форме/руками: TUI, `/shop` у торговца — после Enter окно на месте, две верхние строки обновились,
курсор на той же строке; Esc — в игру; следующий словесный ход — у мастера приписка «(Перед этим герой сам:
купил «…» x2 у …; …)» — смотреть в `saves/<мир>/journal/calls-*.jsonl` (только чтение).

mutmut (`make mutate FUNCS="…" TESTS="…"`, TESTS — каталог модуля по правилу AGENTS):

- `ai_dm.ui.tui.app:AiDmApp.finish_turn ai_dm.ui.tui.app:AiDmApp.refresh_shop ai_dm.ui.tui.app:AiDmApp.show_shop
  ai_dm.ui.tui.app:AiDmApp.shop_chosen ai_dm.ui.tui.app:AiDmApp.shop_closed
  ai_dm.ui.tui.app:AiDmApp.on_shop_modal_picked ai_dm.ui.tui.app:AiDmApp.qty_chosen
  ai_dm.ui.tui.modals:ShopModal.update ai_dm.ui.tui.modals:ShopModal.on_option_list_option_selected
  ai_dm.ui.tui.shop_blocks:shop_money` — TESTS `tests/unit/ui/tui` (Pilot-тесты, долго; время не измерено —
  фоном, по правилу 1 «Экономии конвейера»). Новые: `refresh_shop`, `shop_closed`, `on_shop_modal_picked`,
  `ShopModal.update`, `ShopModal.on_option_list_option_selected` (переопределение), `shop_money`.
- `ai_dm.game.shop_actions:note_of ai_dm.game.shop_actions:remember ai_dm.game.shop_actions:run
  ai_dm.game.app:GameApp.with_notes ai_dm.game.app:GameApp.load` — TESTS `tests/unit/game`. Новая: `remember`.
- Итоговая строка перед коммитом (папа, 2026-11-10, все функции — по `git diff HEAD` через ast по строкам ханков;
  к двум спискам выше добавлены задетые `GameApp.__init__` (`self.deals`), `InvModal.compose` и хук
  `InvModal.head_widgets`, `ShopModal.__init__`, `ShopModal.head_widgets`; `ShopModal.Picked.__init__` в FUNCS не
  входит — mutmut 3.8.0 методы вложенного класса не мутирует, `mutmut/mutation/file_mutation.py:420`; `TradeConfig`
  — поле, не функция). TESTS — оба каталога одной командой (Makefile принимает список; одна фаза stats вместо двух):

  `make mutate FUNCS="ai_dm.game.shop_actions:note_of ai_dm.game.shop_actions:remember ai_dm.game.shop_actions:run
  ai_dm.game.app:GameApp.__init__ ai_dm.game.app:GameApp.with_notes ai_dm.game.app:GameApp.load
  ai_dm.ui.tui.app:AiDmApp.finish_turn ai_dm.ui.tui.app:AiDmApp.refresh_shop ai_dm.ui.tui.app:AiDmApp.show_shop
  ai_dm.ui.tui.app:AiDmApp.shop_chosen ai_dm.ui.tui.app:AiDmApp.shop_closed ai_dm.ui.tui.app:AiDmApp.on_shop_modal_picked
  ai_dm.ui.tui.app:AiDmApp.qty_chosen ai_dm.ui.tui.modals:InvModal.compose ai_dm.ui.tui.modals:InvModal.head_widgets
  ai_dm.ui.tui.modals:ShopModal.__init__ ai_dm.ui.tui.modals:ShopModal.head_widgets ai_dm.ui.tui.modals:ShopModal.update
  ai_dm.ui.tui.modals:ShopModal.on_option_list_option_selected ai_dm.ui.tui.shop_blocks:shop_money"
  TESTS="tests/unit/game tests/unit/ui/tui"` — 20 функций, 274 строки тела (ast), 3357 тестов в TESTS
  (`pytest --collect-only`), затем `make mutate-diff`.
  Оценка времени (папа, 2026-11-10): TESTS последовательно — 6 мин 50 с (замер: `pytest -q tests/unit/game
  tests/unit/ui/tui`, 3356 passed, 1 xfailed, 410 с, load 1,7–2,3); фазы stats и clean у mutmut идут в один поток →
  ≈ 14 мин фиксированных; мутантов ≈ 250–450 (ожидание: ФД2 П1 — 5 функций/211 мутантов), TUI-мутанты гонят Pilot-тесты →
  mutmut при `MUT_CHILDREN=4` ≈ 35–45 мин, при 8 ≈ 25–30 мин (ожидание, не проверено). cov — 41 мин 44 с при `XDIST=4`
  (замер ФД2 П2), при `XDIST=8` ≈ 30–40 мин (ожидание; `-n 6` уже перегружал машину — plan-202 решение 12).
  Режимы testy.md: «долго» (`taskpolicy -b`, cov; mutmut, половина ядер) ≈ 75–90 мин, машина отзывчива;
  «тяжело» (все ядра, cov ‖ mutmut) ≈ 45–55 мин стеной, машина занята, выше риск плавающего TUI-теста (BACKLOG 294)
  и segfault mutmut на широком TESTS (комментарий Makefile:55). Режим — решение Влада, в «Решения».
  Факт прогона (папа, 2026-11-10, лог `mutate-254.log` в scratchpad, `mutants/*.meta`, `mutmut-stats.json`): режим
  «долго» (`taskpolicy -b`, `MUT_CHILDREN=4`); мутантов 670 (а не 250–450); фазы stats + clean ≈ 90 мин (а не 14:
  трассировка coverage + фоновый приоритет, доли не разделить); 435 мутантов за первые ≈ 30 мин, дальше 16–19 за 30 мин.
  Причина — цена одного мутанта определяется числом покрывающих тестов из stats: `finish_turn`/`refresh_shop` — 309
  тестов (все Pilot-прогоны хода), `GameApp.__init__` — 1445 из 3357; мутанты сортируются по этой оценке, быстрые идут
  первыми (`mutmut/__main__.py:1014`). На новые строки диффа у `GameApp.__init__` приходится 1 мутант из 104
  (`self.deals = None`), у `finish_turn` — 7 из 169, у `load` — 1 из 92 (скрипт `mutants_new_lines.py` в scratchpad).
  Повтор `mutmut run` с шаблонами перегоняет все названные мутанты, даже с результатом (`__main__.py:1029`); смена
  `pytest_add_cli_args_test_selection` сбрасывает все результаты и stats (`:638-643`); `make mutate` с TESTS делает
  `rm -rf mutants` (Makefile:61) — продолжить можно только прямым `uv run mutmut run` с тем же TESTS в `pyproject.toml`.

## Развилки

Видимое игроку — решает Влад до «кабаним». Рекомендация папы у каждой.

- **Р1. Вкладки во время серии.** (1) **Набор вкладок зафиксирован при открытии**: сделка пересчитывает
  строки внутри тех же вкладок; вкладка, из которой всё продано или скуплено, остаётся пустой (список без
  строк); новая категория товара у торговца (продал ему кинжал — у него появилась бы вкладка «Оружие»)
  видна только при следующем `/shop`. Только `fill` + подсветка, без перестройки виджета `Tabs`, всё
  синхронно. (2) Пересобирать вкладки после каждой сделки (`Tabs.clear()`/`add_tab`/`recompose`): Textual
  8.2.8 при добавлении в пустые `Tabs` сам активирует первую вкладку асинхронно
  (`_tabs.py:490-500 refresh_active`), наш выбор вкладки перебивается — нужно хранить «куда вернуться» и
  ловить `TabActivated`; ≈ +20 строк и риск гонок в Pilot. Рекомендую (1): оба случая — край (скупить
  категорию целиком, выкупить назад только что проданное), и `/shop` снова показывает всё верно.
- **Р2. Строка денег у NPC только с услугами** (нет `trade`, кошелька нет — `shop_text.py:110-114`).
  (1) **«Деньги: X»** без второй части; (2) «Деньги: X · Кошелёк торговца: —». Рекомендую (1).
- **Р3. Вторая строка при открытии окна**, пока сделок не было: (1) **пустая**; (2) подсказка вроде «Сделок
  ещё нет». Рекомендую (1): меньше текста, итог появится после первого Enter.
- **Р4. Что считать «итогом сделки»** во второй строке: (1) **те же строки, что уходят в ленту**
  (`modal_lines(step.blocks)`: «Куплено: … за …», при урезании — плюс причина «Оплачено только 2 из 5
  (…)», при отказе — его текст, при `Invalid` — сообщение); две строки движка — две строки в окне;
  (2) только первая строка. Рекомендую (1): ничего не придумываем, отказ и урезание видны целиком.

Риски:

- Фокус: `finish_turn` сейчас всегда `entry.focus()`; при открытом `ShopModal` этого делать нельзя (фокус
  на нижнем экране при модалке — поведение Textual не проверял) — поэтому ветка `refresh_shop` вместо
  фокуса. Esc во время идущей сделки: окно закроется (`dismiss(None)`), `finish_turn` увидит базовый экран
  и пойдёт обычным путём, строки — в ленту. Приемлемо, тест не обязателен.
- Второй Enter во время сделки: `run_worker(..., exclusive=True)` (`app.py:449`) отменил бы предыдущего
  воркера; защита — `if self.busy: return` в `on_shop_modal_picked`. Без неё — риск потерянного
  `finish_turn`.
- Автосейв на каждую сделку (`inv_actions.finish:44`) — как сейчас; на большом сейве серия из 10 сделок —
  10 записей. Время записи не мерил. Если живой прогон покажет паузы — пункт в беклог, не этот шаг.
- Заметки `inv_notes`/`deals` живут в памяти: выход из игры до словесного хода — мастер о сделках не узнает
  (так и сейчас; риск свинопаса, пункт в беклог — оркестратору).
- Склейка по ключу без качества: «купил «Кинжал»» junk и used сольются в x2 с суммой цен — мастер качество в
  заметке и так не видит (`note_of` его не пишет). Если нужно разделять — ключ + `quality`, 1 слово.
- `make smells`: базу на HEAD не замерял; `finish_turn` уже длинная цепочка `if/elif` — новая ветка вынесена
  в `refresh_shop`, иначе ожидаю +1 smell.
- mutmut по `tests/unit/ui/tui` — долгий (Pilot); запускать фоном, по правилу 1 «Экономии конвейера».

## Умолчания (внутреннее)

- Канал «выбор строки» — сообщение `ShopModal.Picked(action)` (правка по ревью 6) по образцу `Choices.Picked`
  (`widgets.py:78`, обработчик `on_choices_picked` `app.py:266`); Esc — как сейчас, `dismiss(None)` →
  коллбэк `push_screen` (`shop_closed`). Альтернатива «после сделки переоткрывать окно с запомненной
  вкладкой» (как `qty_chosen(None)` → `show_shop` сейчас) отвергнута: на время сделки и автосейва окно
  мигает.
- `ShopModal.__init__(title, tabs, npc_id, head)`; `head` — список строк, виджет `Static(id="shop-head")`
  над `#inv-title`; у `InvModal` хук `head_widgets()` → `()` (используется сразу подклассом, не «на будущее»).
- `update(rows, head)`: перегруппировка `[(name, [r for r in rows if r[3] == name]) for name, _ in self.tabs]`
  (при Р1 = 1); индекс подсветки `min(старый, len − 1)`, при пустом списке — описание `""`.
- Ключ склейки `(request.type, direction, npc.id, item_id | service_id)`; `app.deals: dict[key, (qty, total_cp, note)]`
  в `GameApp`, рядом с `inv_notes`, сброс в `with_notes` и `load`; заменяем старую заметку на месте
  (`inv_notes[i] = new`), порядок прочих не трогаем. Старый текст для поиска — сохранённый `note`, не пересборка
  `note_of` (имя NPC могло смениться — правка по ревью 8); имя в ключ не входит, склейка идёт под текущим именем.
- Имена: `shop_money`, `refresh_shop`, `shop_closed`, `remember`, `SHOP_MONEY`, `SHOP_MONEY_PLAIN`, `#shop-head`.
- Тесты — в существующих файлах (`test_tui_shop_modal.py`, `test_tui_shop_blocks.py`, `test_shop_actions.py`,
  `test_trade_config.py`); новый файл не нужен.
- Правило ОВ/ДГ (BACKLOG 283): концепции у шага нет — строк «без ОВ-X» нет.
- При закрытии: строка ROADMAP:208 — убрать «связь 133», состав файлов по факту; карточка done 254 — тело без
  правок, поправка «одна сделка — один ход» живёт в «Сути» этого документа.

## Открытые вопросы

Нет блокирующих. Р1–Р4 — окно Владу до «кабаним» (видимое игроку); при молчании кабан берёт рекомендации,
но это нарушит правило 4 — лучше ответить.

## Правки по ревью

Папа-кабан, 2026-11-09, по отчёту кабана об отступлениях П1 (код в рабочем дереве, проверено по коду):

1. `ShopModal.on_option_list_option_selected` — принято с `event.prevent_default()`. План считал переопределение
   обычным Python-override; в Textual 8.2.8 `MessagePump._get_dispatch_methods` (`message_pump.py:743-760`) зовёт
   обработчик каждого класса MRO и останавливается только по `message._no_default_action` — без `prevent_default()`
   после `ShopModal` отработал бы `InvModal.on_option_list_option_selected` → `dismiss(actions[0])`, окно
   закрывалось бы. Строка «Файлы» для `ShopModal` читается с этой поправкой; тест на удаление строки — Pilot
   `depth == (2, True)` (mutmut по `ShopModal.on_option_list_option_selected` из списка «Тестов» его ловит).
2. Guard `if actions` в том же методе не нужен — подтверждено: все строки `shop_rows` строятся с `[action]`
   (`shop_blocks.py:41,58,76`), строка с cap 0 («денег нет») действие имеет (отказ приходит от движка в
   `#shop-head`); пустая вкладка — `OptionList` без опций, `OptionList.action_select` при `highlighted is None`
   сообщение не шлёт (`_option_list.py:1034-1036`). Guard в `InvModal` — для строк `/inv` без действий.
   `make smells` после правки — 200 (измерено 2026-11-09, порог 200); `modals.py` из списка «High total
   complexity» ушёл.
3. `refresh_shop(step, command, words) -> bool` с условием внутри; в `finish_turn` — `if not
   self.refresh_shop(...): entry.focus()`. Принято вместо плановой ветки с тремя условиями в `finish_turn`:
   `app.py` уже «High total complexity 124», плановый вариант добавил бы ветвление туда. Строки «Файлы» для
   `finish_turn` и `refresh_shop` читаются так. mutmut — тот же список.

Папа-кабан, 2026-11-10, по отчётам круга 1 (мама, свекровь; код рабочего дерева проверен по диффу):

4. Накопление в `deals` — права реализация: `app.deals[key] = (qty + old_qty, total_cp + old_cp)`
   (`shop_actions.py:92`). Строка «Файлы» писала `(qty, total_cp)` — опечатка плана: по ней на третьей одинаковой
   сделке `inv_notes.index(note_of(..., *old))` искал бы заметку x1, которой уже нет, и падал. «Суть» (:55) и
   «Умолчания» (:241–242) с кодом согласны. Строка «Файлы» поправлена.
5. Тест Мары — прав тест: после покупки «Кошелёк торговца: 50 зм», не 52. Кошелёк движок меняет только при скупке
   (`protocol/handlers/trade.py:173` `profile.purse_cp -= unit * qty`), пополнения при покупке героем нет — так с У1,
   шаг 254 поведение кошелька не трогает. Строка «Тестов» поправлена; план сам пометил «проверить прогоном». Если
   Владу нужно, чтобы кошелёк рос от покупок героя — отдельный пункт беклога, не этот шаг.
6. `npc_id` в цепочке `Picked` → `on_shop_modal_picked` → `shop_chosen` → `qty_chosen` мёртвый (мама): после отмены
   `show_shop(npc_id)` из `qty_chosen` его никто не читает, `refresh_shop` берёт `self.screen.npc_id`. Принято
   удаление: `Picked(action)`, `shop_chosen(action)`, `qty_chosen(action, qty)`, `self.shop_chosen(event.action)`;
   тест `test_picked_while_busy_does_not_start_a_deal` (`test_tui_shop_modal.py:906`) → `ShopModal.Picked(action)`.
   `ShopModal.npc_id` остаётся (его читает `refresh_shop`). Строки «Файлы» и «Умолчания» поправлены. Остальные
   замечания мамы (дефолты `npc_id=None, head=()` в `ShopModal.__init__` — убрать, план задаёт
   `(title, tabs, npc_id, head)`; `getattr(request, "direction")` → `request.direction`; два комментария; порядок и
   импорт в `test_tui_shop_blocks.py`) плану не противоречат — кабану сделать.

   Вопросы Владу из круга 1 (выносит оркестратор): `make dead` на `on_shop_modal_picked` — строка в
   `vulture_allowlist.py` или иной путь; BACKLOG 296 заведён до условия «если прогон покажет паузы»;
   `start_me_after_reboot` в корне репо. Ответы — сюда, в «Решения».

Папа-кабан, 2026-11-10, по отчёту кабана после круга 1 (код рабочего дерева проверен по коду):

7. Сделано по п. 6 и решению 15, принято: `Picked(action)` (`modals.py:258`), `shop_chosen(self, action)` и
   `qty_chosen(self, action, qty)` (`ui/tui/app.py:582,593,603`); `ShopModal.__init__(self, title, tabs, npc_id, head)`
   без дефолтов (`modals.py:246`); в `remember` `getattr` только у `item_id`; комментарии `modals.py:231`
   («результат -- None (Esc); выбор строки -- сообщение Picked…») и `game/app.py:159` («сделок /shop»);
   `shop_money` в модульном импорте `test_tui_shop_blocks.py:30`, блок «строка денег» (:291) выше «описание» (:314);
   строка `on_shop_modal_picked  # unused method (254: …)` в `vulture_allowlist.py` — решение 15 (Влад, 2026-11-10).
8. Защита от переименования NPC в `remember` (`shop_actions.py:92-94`: старой заметки нет в `inv_notes` → сделка
   считается новой, вторая заметка с новым именем) — не принята, решил папа. Предпосылка мамы верна (`npc_update`
   в бою не запрещён — `world.py:105` проверяет только `mode == "world"`; `shop_actions.run` боя не проверяет;
   заметки переживают номерной ход боя — `game/app.py:228`), но лечение расходится с решением 9 и принятым
   умолчанием (:245, решение 14): «та же сделка» — тот же `npc.id`, имя в ключ не входит; у одного NPC получались бы
   две заметки «x1 у Мара» и «x1 у Марта». Причина `ValueError` — не рассинхрон заметок (`inv_notes` только
   дописывают: `inv_actions.py:43`, `travel_actions.py:110`; сброс всегда парой с `deals` — `game/app.py:230,490-491`),
   а то, что старый текст пересобирается `note_of` по новому имени. Переделать: хранить текст заметки в `deals` —
   `app.deals[key] = (qty, total_cp, note)`, замена `app.inv_notes[app.inv_notes.index(old[2])] = note`; ветка
   `not in app.inv_notes` и второй вызов `note_of(..., *old)` уходят (минус 3 строки, не измерено). Комментарий
   `game/app.py:159` — «(кол-во, медь, текст заметки)». Тест
   `test_renamed_npc_between_equal_deals_gives_a_second_note` (`test_shop_actions.py:532`) переписать на склейку
   под новым именем: после переименования `["купил «Колчан» x2 у Марта (2 зм)"]`, третья покупка — x3 (3 зм).
   Строки «Файлы» (:97) и «Умолчания» (:245–248) поправлены; mutmut — тот же `ai_dm.game.shop_actions:remember`.
9. Сделано по п. 8 (кабан), тест переписан доебой: `test_equal_deals_merge_by_npc_id_even_after_a_rename` (красный
   до правки 1 из 1), `test_merged_deal_is_remembered_with_totals` — тройка. Круг 2 мамы и свекрови: чисто.
10. mutmut (20 функций, 670 мутантов, решение 19): в диффе выжили 23, на старых строках 66 → BACKLOG 297. Разбор
   доебы (sonnet): убиты новыми тестами 8 (повтор: 7, `update_20` выжил — п. 11) — `shop_money_11`, `ShopModal.head_widgets_7`, `update_20`, `update_52`,
   `refresh_shop_2/6/7/25` (5 тестов и `FakeStep` в `test_tui_shop_modal.py`, 1 тест в `test_tui_shop_blocks.py`);
   эквивалентны 15 — `update_6/7/8/13/14/15/37/39/45/46/47`, `shop_closed_2/3/4` (`query_one` с единственным
   виджетом: тип `None`/без типа/без селектора результат не меняет), `update_32` (`OptionList.validate_highlighted`
   зажимает индекс). Эквивалентность приняла мама (круг 3). Тесты дописаны доебой из bash, не Edit — нарушение
   процесса, в отклик. По ревью мамы круга 3 доеба усиливает три теста: кошелёк Мары ≠ пресету, склейка head
   через `"\n"` по несхлопнутому `render()`. Убийство 8 мутантов подтверждает повтор mutmut (решение 18).
11. Повтор mutmut по 8 именам: убиты 7, выжил `update_20` — тест не доходил до сделки («Эль» cap > 1 → QtyModal).
   Доеба (Edit) добавила `enter_qty(app, pilot, "1")` и проверки окна; красная на копии с мутантом 1 из 1;
   подтвердит второй повтор mutmut (окно Владу). cov: 98,38 %, 24943 passed — до этой правки теста.
   Второй повтор (решение 20): mutmut снова «выжил» — по старым stats тест не числится за `update`, mutmut его
   не запускает. Проверено оркестратором тем же механизмом mutmut: в `mutants/` с `MUTANT_UNDER_TEST=…update__mutmut_20`
   тест падает (`assert 1 == 0`), без мутанта — проходит. Итог: 8 из 8 убиты; `mutmut results` числит `update_20`
   выжившим до пересчёта stats (BACKLOG 298).

## Смета (кабан-тесть, режим 1)

**Что проверено:** план шага 254 (окно `/shop`, лимит 50, склейка приписки), цепочка одной партии П1. Платного вне LLM нет (подписки, хостинг, БД,
железо не добавляются). Цены — тариф `metrics.py` от 2026-10-25 (Opus 4 / 5 / 0,20 / 20, Sonnet 2 / 2,50 / 0,10 / 10 $ за 1M; fable — цена Opus; страницу
[pricing](https://platform.claude.com/docs/en/about-claude/pricing) сегодня не открывал). Допущения: база — ФД2 (`docs/plan-fd2.md`, «Итог», 2 партии,
тот же слой TUI/`shop_actions`, факт-таблица); ФД2 на партию ≈ 240 строк src (churn +327/−154 на 2), здесь ≈ 110–130 (из «Файлы» и «Объём» плана,
оценка не проверена) → коэффициент к среднему на партию ФД2 0,35–0,8 (оверхед ревью-кругов от размера не зависит). Партия < 400 строк кода — резать не надо.
База: ФД2 → 254 (последний шаг ai-dm с тем же составом ролей и Pilot-тестами окна).

| Статья | Сейчас ($/мес) | Допущения | Дешевле | Экономия | Что теряем |
|---|---|---|---|---|---|
| kaban-dekart ×2 (партий 1 + сводный) | ≈ 6,9 за шаг | 3,47 $ за вызов — последний факт семьи (`plan-sh9.md:241`, повтор в `plan-sh42.md:287`) | не звать: в ФД2 решение 15 сняло его (5,2 $), план 254 Декарта не требует | до 6,9 | разбор конвейера после шага; выбор за пользователем |
| orchestrator (Opus) | 3,5–6,0 | основной расход; растёт от `/compact`-пауз и числа кругов | меньше кругов ревью — только через меньшую партию; модель слабее оркестратору не предлагаем | — | — |
| kaban-svekrov, mama-kaban (ревью/аудит) | 1,9–4,3 | Opus, 2 круга как в ФД2 П2 | не трогаем (ревью и аудит) | — | — |
| kaban-doeba (Sonnet) | 0,6–1,5 | уже Sonnet; разбор выживших мутантов | разбор по выводу `mutmut results` отдельным вызовом haiku (правило 7 «Экономии конвейера») | ≈ 0,1–0,3 | точность разбора эквивалентных мутантов |
| mutmut, cov | локально, 0 $ | 15 функций; cov 35–50 мин, mutmut 10–25 мин | `make test-fast` в итерациях (уже по плану) | время, не $ | — |

| Партия | Время |
|---|---|
| Груминг и план (свинопас, свекровь, папа) | уже прошло: свинопас ≈ 5, свекровь ≈ 2,3, папа ≈ 11,5 мин |
| П1 (конфиг, склейка, строка денег, окно; доеба → кабан → мама‖свекровь → папа-сценарий) | 40–70 мин агентов |
| cov (`make cov`) | 35–50 мин |
| mutmut 15 функций (фоном) + `mutate-diff` | 10–25 мин |
| Декарт ×2 (если звать) | 15–25 мин |
| Закрытие (папа-архитектор, тесть р.3) | 5–8 мин |
| Итого цепочка | 105–180 мин агентов; с живым прогоном Влада и ожиданием — на его стороне |

| Роль | Модель | Токены | $ (тариф metrics.py 2026-10-25) |
|---|---|---|---|
| уже прошло: svinopas, kaban-svekrov (груминг), papa-kaban (план) | opus / opus / fable (цена Opus) | ≈ 3,2 M | 3,83 (1,36 + 0,70 + 1,77; `metrics.py` по id из `agents.md`; нижняя граница ≥ 3,83) |
| orchestrator | opus | 8–13 M | 3,5–6,0 |
| kaban-doeba | sonnet | 2,2–5,0 M | 0,6–1,5 |
| kaban | sonnet | 2,0–4,5 M | 0,5–1,1 |
| mama-kaban | opus | 0,45–1,0 M | 0,7–1,6 |
| kaban-svekrov (аудит П1) | opus | 0,9–2,0 M | 1,2–2,7 |
| papa-kaban (сценарий П1, закрытие) | fable (цена Opus) | 1,2–2,7 M | 1,1–2,5 |
| kaban-test (р.1 уже 0,17 + р.3) | opus (цена Opus) | 0,4–0,6 M | 0,5–0,9 |
| kaban-dekart ×2 | fable (цена Opus) | ≈ 7,8 M (по факту sh9, не по выжимке) | ≈ 6,9 |
| **Итого без «уже прошло»** | | 23–37 M | 15,1–23,3 с Декартом; 8,1–16,3 без |
| **Итого с «уже прошло»** | | 26–40 M | 18,9–27,1 с Декартом; 11,9–20,1 без |

Модели (`grep -H '^model:' ~/.claude/agents/<роль>.md`): `kaban.md:model: sonnet`, `kaban-doeba.md:model: sonnet`, `mama-kaban.md:model: opus`,
`kaban-svekrov.md:model: opus`, `kaban-test.md:model: opus`, `kaban-dekart.md:model: fable`, `papa-kaban.md:model: fable`, `svinopas.md:model: opus`.
Факт текущего запуска тестя шёл на sonnet (по `metrics.py`), в таблице — модель по определению (opus).

## Итог

**Источник токенов:** `metrics.py ~/.claude/projects/-Users-vladislavahtamov-projects-ai-dm/b4ed8070-07bf-4a89-af16-b8943ed8a251.jsonl`
(сессия одного шага, `--from` не нужен); **цены:** тариф `metrics.py` от 2026-10-25,
[pricing](https://platform.claude.com/docs/en/about-claude/pricing) — сегодня не сверял, не проверено; fable — по цене Opus.
Шаг закрыт без живого прогона (решение 21), Декарт ещё не звался. BACKLOG закрыт: 254.

| Партия | Смета | Факт |
|---|---|---|
| Груминг и план | уже прошло ≈ 19 мин | 2,3 + 11,5 мин работы (свинопас и свекровь параллельно) |
| П1 (доеба → кабан → мама‖свекровь → папа, 3 круга) | 40–70 мин | ≈ 70 мин работы субагентов (сумма «минут работы» `metrics.py`); интервалы мамы/свекрови 689 мин — в т. ч. простой: ожидание ответов Влада и фоновый mutmut |
| cov | 35–50 мин | 72 мин (режим «долго», `taskpolicy -b`, решение 18) — фоновый приоритет, не объём |
| mutmut + повторы | 10–25 мин (15 функций) | ≈ 9 ч + 20 мин + повтор 2: 20 функций, 670 мутантов вместо 250–450, stats+clean ≈ 90 мин, Pilot-тесты на мутант (`finish_turn` 309 тестов), режим «долго» |
| Декарт ×2 | 15–25 мин | не звался на момент итога |
| Закрытие (архитектор, тесть) | 5–8 мин | 2,4 мин + тесть идёт |
| Итого цепочка | 105–180 мин агентов | 132 мин шага по `metrics.py`; ожидание 703 мин (вопросы текстом 347), пауза лимита 74 мин |

| Роль | Модель | Токены | $ |
|---|---|---|---|
| orchestrator | opus | 26,7 M (на момент подсчёта 2026-11-10 07:57 UTC) | 10,83 (на момент подсчёта) |
| kaban | sonnet | 5,1 M | 1,54 |
| kaban-doeba | sonnet | 5,3 M | 2,12 |
| mama-kaban | opus | 1,97 M | 3,17 |
| kaban-svekrov | opus | 3,21 M (груминг 0,70 $ + П1 3,10 $) | 3,80 |
| papa-kaban (5 запусков) | fable (цена Opus) | 6,46 M | 6,95 |
| svinopas | opus | 1,48 M | 1,36 |
| kaban-test (р.1 + р.3) | opus | 0,70 M (на момент подсчёта) | 0,62 (на момент подсчёта) |
| kaban-dekart | fable | — (не звался) | — |
| **итого** | | 50,9 M | 30,40 |

**Итого:** смета 11,9–20,1 $ без Декарта (18,9–27,1 с ним) → факт 30,40 $ без Декарта, оркестратор и тесть неполные;
время 105–180 → 132 мин агентов (mutmut ≈ 9 ч фоном вне сметы). Превышение: оркестратор 10,8 вместо 3,5–6,0 (885 мин
жизни сессии, 2 `/compact`, 21 окно вопросов), папа 6,95 вместо 1,1–2,5 (5 запусков вместо 2: отступления, круг 1,
mutmut, архитектор), мама и свекровь — 3 круга вместо 2. Нарушение: доеба `a1841b47` дописала тесты из bash (2 записи).
Churn после ревью: код +35/−32, тесты +62/−53 (24 % от строк до T0)
Разбор — кабан Декарта.
