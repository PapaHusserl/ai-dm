# Передача контекста (оркестратор → новая сессия), 2026-10-04

## Проект и роли
Текстовая RPG по D&D 5e с ИИ-мастером (`~/projects/ai-dm`, Python, uv). Пользователь — проектировщик: продуктовые решения
только его. Оркестратор (основная сессия) ведёт конвейер агентов: груминг — svinopas (мини-влад) + kaban-svekrov (аудит);
план — papa-kaban; после «окей, кабаним» — kaban (код, src/docs) и kaban-doeba (тесты, tests/**) параллельно, затем
mama-kaban (ревью), правки, коммит. Финансы — kaban-test. Отвечать по-русски.
Правила: перед каждым коммитом — обновить docs/ROADMAP.md (живой срез очереди); коммит после каждой принятой партии (коммитить только нужные пути, НЕ `git commit -a`, не добавлять checklist*.md);
перед каждым живым прогоном пользователя — чек-лист docs/checklist-<партия>-live.md (не коммитить); ключи API не печатать/не логировать; живые вызовы API — только пользователь; saves/ — живые миры пользователя, агентам только
читать (копии — во временном каталоге); правка сейва — только с согласия пользователя и с бэкапом.
Глобально (~/.claude/CLAUDE.md): между партиями/этапами чистить контекст, состояние — в docs; ревью партий не сокращать.

## Где состояние
- ТЗ: docs/TZ.md (этапы — раздел 13; 1–3 приняты, теги stage-1..3).
- Архитектура: docs/ARCHITECTURE.md (части A–E). Бэклог: docs/BACKLOG.md.
- Этап 4 (Память): план docs/STAGE4-PLAN.md; груминг/аудит/решения docs/decisions/stage4-grooming.md
  (Д1 бюджет = min(80% окна, 30 000 ток.); Д2 сбой summarizer → меню 2.2; G1 — переполнение неустранимой части → потолок 80% окна).
- Решения живых прогонов этапа 3: docs/decisions/stage3-live-*.md.

## Где мы (этап 4)
- P0 ✅ (a394fca, c414de1): выжимки в контексте нарратора (system[2] «память»).
- P1 ✅ (d897366): summarizer на границе сцены, схема v5.
- P1+ ✅: правки ревью P1 + экономия E1–E3 (docs/decisions/stage4-p1-review-and-cost.md, там же отчёт E2).
- P2 ✅ (7de2bd5): свёртка главы summarizer'ом; concat при summarizer=None оставлен (решение); лишний вызов — BACKLOG 12.
- P3 ✅ (9e35c70): сборщик контекста master/context.py, вытеснение, G1; спецификация и решения В1–В4 —
  docs/decisions/stage4-p3-spec.md. Мутации context/relevance — 0 выживших.
- P4 мок ✅ (da7ce9c): tests/scenarios/test_stage4_memory.py + memory_script.py; окно мока 20 000 (решение, см. план P4).
- Живой прогон (часть E) ✅, фикс боя M5 ✅ (fb5e2b5), аудит свекрови ✅ (docs/decisions/stage4-audit.md). Тег stage-4.
- Хвосты этапа 4 — BACKLOG 15.

## Этап 5 (TUI на Textual)
- Груминг+аудит+решения проектировщика: docs/decisions/stage5-grooming.md (V4 снят, В1–В9 по рекомендациям, цвет разрешён).
- План: docs/STAGE5-PLAN.md (партии P0–P5, ответы на Q1–Q10 в конце).
- P0 ✅ (b011503): ui/screen.py + ui/session.py, simple.py — тонкий цикл; ревью docs/decisions/stage5-p0-review.md; мутации 0 выживших.
- P1 ✅: textual, --simple, choose_mode, fallback, заглушка ui/tui, make install-check; ревью docs/decisions/stage5-p1-review.md;
  хвосты — BACKLOG 16. Имена API Textual — в vulture_allowlist.py (согласие пользователя).
- P2 ✅: каркас TUI (app/widgets/strings/tcss), ревью docs/decisions/stage5-p2-review.md; «vs»→«против» в строке броска; хвосты — BACKLOG 16.
- P3 ✅: меню и режимы (modals.py, blocks.py, HeroPickerApp, варианты кликом/цифрой, жёсткий выход по 2-му Ctrl+C,
  /model без арг. — окном, с арг. — в ленту, варианты скрываются только в TUI); ревью и решения проектировщика 1–6 —
  docs/decisions/stage5-p3-review.md; хвосты — BACKLOG 16. make smells 205, make dead — 24 старые находки (долг, BACKLOG 16).
- P4 ✅: /cost роль × модель (cost_rows/cost_lines, by_role_model, CostModal с DataTable), все команды HELP в обоих режимах; ревью и решение — docs/decisions/stage5-p4-review.md; мутации нового кода — 0 выживших.
- P5 ✅ (dd04492, 62736e2): приёмка — сценарий этапа 2 в TUI = простой режим (бандл), латиница лога боя переведена без белого списка,
  make linux-check зелёный; ревью/решения docs/decisions/stage5-p5-review.md, аудит docs/decisions/stage5-audit.md; долги — BACKLOG 16.
- Живой прогон 1 ✅ (правки п.1–11): docs/decisions/stage5-live-1.md, ревью stage5-live-1-review.md.
- P6 ✅ «ASCII-рисунки»: src/ai_dm/art/ (22 рисунка, index.yaml, pick_picture); монстр — крупно в ленту при начале боя (Р-2),
  локации/события — в #picture; простой режим — только заставка. Ревью, решения Р-1/Р-2, мутанты — docs/decisions/stage5-p6-review.md.
  Хвосты — BACKLOG 5а (31 локация), 16 (заставка в HeroPickerApp, мутанты simple.run).
- Вставка «Боевые дополнения» ✅: безоружный удар, импровизированное оружие (ближний + бросок 20/60), Опутывающий удар
  (заряд, спасбросок Силы, Large+ с преимуществом, escape); план docs/COMBAT-EXTRAS-PLAN.md, ревью docs/decisions/combat-extras-review.md.
  Хвосты: BACKLOG 16 (мутанты attacks_of), 18 (апкаст), строка безоружного в карточке героя не добавлена.
- Вставка «Переговоры в бою» ✅: combat/actions/parley.py, статус surrendered, [parley] в конфиге; план docs/COMBAT-PARLEY-PLAN.md,
  ревью docs/decisions/combat-parley-review.md. Мутации check_request/menu_entries/parley_options/CombatEngine.parley не доведены.
  make smells = 210 (запас 0).
- Вставка «Меню боя: сначала цель» ✅: ui/combat_menu.py (чистые функции + MenuState), CombatMenu/TargetBar/MoreModal в TUI;
  движок/протокол/простой режим не менялись; ревью и решения Р-1..Р-4 — docs/decisions/combat-menu-review.md.
- Вставка «Отбор оружия» ✅: combat/disarm.py, ground_items/GroundItem/free_interaction, MonsterAction.weapon_id, [disarm];
  ревью docs/decisions/combat-disarm-review.md; лут с не обезоруженных — BACKLOG 22.
- Этап 5 принят проектировщиком 2026-10-07, тег stage-5. Дальше — P1 по приоритетам BACKLOG (п. 17 кастомные предметы).
- Замечено: make dead падает на ui/io.py ещё до P0 (InputSource понадобится в P1); make smells плавает 208–212 при лимите 210.
- Решения проектировщика по экономии: не урезать длину/мышление рассказчика; экономить на кэше/входе.

## P1: кастомные предметы (BACKLOG 17 + трофеи 22) — docs/CUSTOM-ITEMS-PLAN.md
Партии 0 → А → Б → В, одна версия сейва v6 (В23). ⚠ Не выпускать/не играть живые миры между партиями 0 и В (иначе v7).
- Партия 0 ✅: цена у каждого экземпляра (InventoryEntry cost_cp/quality, стеки), миграция v6 с MigrationContext
  (обязателен в load_slot/migrate), реестр пака до сейва (peek_campaign_id), предупреждение отчёта миграции;
  ревью docs/decisions/custom-items-p0-review.md. Старые выжившие мутанты (pick_valuables ничья, settle_ground логи,
  disarm take quality, load_slot ошибки) — в BACKLOG 16.
- Партия А ✅: CustomItem+ItemHolder (вес — weight_centilb), WorldState.custom_items, LastCombat.gear, world_registry (одна
  пара overlay у базового реестра, TurnContext.base_registry), give_custom_item (per_scene=5), hand_over/recover,
  rob/capture с держателем и notes «Отобрано…», capture — все кастомные в тайник логова; ревью и решения 1–7 —
  docs/decisions/custom-items-pA-review.md.
- Партия Б ✅: /inv «Сюжетное» (описание, вес, цена), контекст мастера (name/description/quest, lost_items,
  last_combat — только непустые), narrator_rules «Сюжетные предметы», simple «Получено» с предметами;
  ревью и решения 1–4 — docs/decisions/custom-items-pB-review.md.
- Партия В ✅: трофеи с тел (rules/loot.py body_gear/quest_gear/trophy_cost, [[loot.trophy_quality]], combat/trophies.py
  is_boss/weapon_price/enemy_gear, расчёт в settle_ground → CombatState.gear → LastCombat.gear), выдача обыском
  (protocol/handlers/loot_gear.py), качество приставкой «Ржавый скимитар», выбитое оружие монстра — цена трофея;
  ревью и решения 1–4 — docs/decisions/custom-items-pV-review.md. WINDOW мока 20500 оставлен (торговля Т2: 20650). BACKLOG 17 закрыт —
  живые миры можно играть (v6). Дальше — торговля BACKLOG 23 (решение проектировщика 2026-10-07), потом этап 6.
## Торговля (BACKLOG 23) — docs/TRADE-PLAN.md
Партии Т0 → Т1 → Т2 → Т3 → Т4 → Т5 (торг Убеждением), одна версия сейва v7. ⚠ Не играть живые миры до конца вставки.
- Т0 ✅: TradeProfile у NPC (поля торга Т5 сразу), TradeConfig/пресеты (инвариант маржи 1.3 при скидке до 20%),
  миграция v7 (торговцы из пака через MigrationContext.npc_trade, предупреждение при сбое пака);
  ревью и решения 1–4 — docs/decisions/trade-t0-review.md. Дальше — Т1 (чистые функции rules/trade.py; вопрос
  category="" → gear в плане).
- Т1 ✅: rules/trade.py (item_category, merchant_sells/buys, refuses, buy/sell_quote через Fraction, assortment, restock);
  зелье лечения category: consumable; ревью docs/decisions/trade-t1-review.md, заметки для Т2 — в конце TRADE-PLAN.
- Т2 ✅: protocol/handlers/trade.py + trade_pick.py (buy/sell, stock, выкуп сюжетного у держателя), trade_kind в
  npc_create/npc_update (не у роли world; вместе со status — Invalid), take_item сюжетного — holder_npc_id обязателен,
  WINDOW мока 20650; ревью и решения 1–3 — docs/decisions/trade-t2-review.md. make dead: haggle_* (Т0, под Т5) — ждёт
  решения по allowlist (решено: haggle_* в vulture_allowlist до Т5).
- Т3 ✅: контекст мастера — scene_npcs.merchant, ключ trade (stock с quality + сводка categories), двухступенчатая покупка
  trade direction=list category (без сделки, не тратит лимит), narrator_rules «Торговля», not_sold отсылает к list,
  мок-сценарий tests/scenarios/test_trade_scenario.py, WINDOW мока 21470; ревью и решения — docs/decisions/trade-t3-review.md.
  Дальше — Т4 (показ: /inv цены, /shop, «Потрачено» в gains).
- Т4 ✅: /inv — цена экземпляра хвостом; /shop (game/shop_text.py, модалка «Торговля», вне хода; purse_now в rules/trade.py,
  продажа через sellable_stacks, сюжетные у торговца-держателя); «Потрачено: −X» в gains; ревью docs/decisions/trade-t4-review.md.
- Т5 ✅ (ревью и решения R1/R2 — docs/decisions/trade-t5-review.md; WINDOW мока 21900): инструмент haggle (СЛ и бросок Убеждения — движок, раз в игровой
  день на торговца, поправка только на покупку, потолок price_mod_cap_percent), rules/trade.py (merchant_buy_quote, haggle_*),
  цены с торгом в trade/контексте мастера/ /shop («торг: −10%»); haggle_* убраны из vulture_allowlist.
  Вставка «Торговля» закрыта — живые миры (v7) можно играть. Дальше — этап 6 (P1 BACKLOG).

## Этап 6 (репорты, воспроизведение, import, герой на лету, предыстории)
- Груминг + аудит свекрови: docs/decisions/stage6-grooming.md. Аудит подтвердил оркестратор: context_overflow и refusal в
  report_tags уже есть (master/session.py), поля героя motive/means/opportunity есть (state/hero.py) — миграция v8 не нужна.
- Решения: В1–В8 по рекомендациям, деление 6а (репорты+replay) / 6б. План 6а готов: docs/STAGE6A-PLAN.md (P0–P2, сейв v7 без миграций) — одобрен.
- P0 ✅: reports/ (capture, writer, markdown), /report, авто-метки (вкл. invalid-defeat через Invalid.report_tag,
  метки границы), WINDOW мока 21910; ревью docs/decisions/stage6a-p0-review.md.
- P1 ✅: полный репорт (before/after слоты «auto», journal/calls.jsonl + blobs через Journal.records_for, N последних ходов
  с самим ходом, [reports] recent_turns, снимки — deep copy); ревью docs/decisions/stage6a-p1-review.md. 
- P2 ✅: reports/replay.py (load_report, compare, TIME_FIELDS — только manifest.saved_at), ai-dm --replay-report (коды 0/1/2,
  в сообщении расхождения — версия формата и схемы снимка), replayable=false при пропавшем блобе; детерминизм подтверждён
  (run_id в отпечаток не входит); ревью docs/decisions/stage6a-p2-review.md. Аудит docs/decisions/stage6a-audit.md; план и этап 6а
  подтверждены проектировщиком 2026-10-08, тег stage-6a. Дальше — переприоритизация BACKLOG, затем 6б.
- Расходы: svinopas ~57 тыс.; kaban-svekrov ~25 тыс.; papa-kaban (план 6а) ~49 тыс.; dyadya-kaban (ресёрч 18+) ~27 тыс.
- 6а P0: kaban ~90+108+113 тыс. (~17 мин); kaban-doeba ~178+196 тыс. (~38 мин); mama-kaban ~29 тыс.
- 6а P1: kaban ~57 тыс. (~7 мин); kaban-doeba ~104 тыс. (~29 мин); mama-kaban ~26 тыс.
- 6а P2: kaban ~94+7 тыс. (~10 мин); kaban-doeba ~148+2 тыс. (~34 мин); mama-kaban ~22 тыс.

## Приоритеты
Действует единая очередь R5 (docs/decisions/roadmap-r5-proposal.md, утверждена 2026-10-11; R4 — docs/decisions/roadmap-r4-unified.md); порядок P0–P5 в начале
docs/BACKLOG.md заменён ею (история). AD1 (BACKLOG 3, 12, хвосты 16/30) закрыт — коммит 0f75d5c. Сейчас — Б0 (этап 6б):
груминг и план. Порядок — раздел «Роадмап остатка BACKLOG».

## Живая игра пользователя
Миры: saves/drunk_dragon-29a049dc (текущий, Грей 3 ур.), saves/drunk_dragon-ee8aa926. Модель по умолчанию — Gemini 3.8 Flash
(рассказчик), Flash-Lite (world, summarizer). Цена ≈ $0.022 за ход.
Тесты: `uv run pytest -q` (~9150 зелёных, 1 xfail), `uv run ruff check src tests`.

## Инструменты качества (кабан-кволити, 1a6b45b)
Перед коммитом партии: `make cov` (≥94%), `make smells` (≤202), `make dead`, `make mutate FUNCS="модуль:функция модуль:Класс.метод" TESTS="tests/..."` для изменённых функций (старый вариант по модулям — `MOD="..."`; TESTS — только тесты этих модулей, иначе фазы stats/clean гоняют весь tests/ по ~12 мин)
(при устаревшем mutants/ — удалить каталог, он генерируемый). vulture_allowlist — только с согласия пользователя.
Коммитить только пути своей партии.
FUNCS разворачивается в шаблоны mutmut `ai_dm.mod.x_func__mutmut_*` и `ai_dm.mod.xǁClassǁmethod__mutmut_*`; пример: `make mutate FUNCS="ai_dm.ui.session:PlaySession.submit" TESTS="tests/unit/ui"`.

## Правила экономии конвейера (предложения кабана-тестя, приняты пользователем 2026-10-05)
1. mutmut — только по функциям, изменённым в партии (из `git diff`), запуск фоном; агент лишь разбирает результат.
2. Полный `pytest` и `make cov` — один раз в конце партии (совместно); во время итераций — тесты затронутых модулей.
3. Мутантов разбирает kaban-doeba (или кабан-кволити) в своей задаче, а не kaban.
4. Выжившие мутанты разбираются только на новых строках партии; старые — сразу в BACKLOG.
5. Решения проектировщика сразу записывать в review.md партии.
6. Токены и время субагентов каждой партии записывать сюда (handoff), раздел ниже.
7. (AD1, решение 4) kaban-doeba получает diff партии и список изменённых функций (`модуль:функция`), mutmut — `make mutate FUNCS=…`; разбор выживших — отдельным вызовом меньшей модели (sonnet/haiku) по выводу `mutmut results`. Оркестратор подставляет это в задание; глобальные агенты (`~/.claude/agents/`) не правятся.

## Расходы агентов
- Этап 5, P5: kaban ~88 тыс. ток./~117 мин; kaban-doeba ~78 тыс. (вкл. дозадачу); mama-kaban ~28 тыс.; kaban-svekrov ~45 тыс.; kaban-test ~12 тыс.
- Этап 5, живой прогон 1: kaban ~139 тыс. ток.; kaban-doeba ~184 тыс. (131 вызов, ~110 мин — mutmut); mama-kaban ~38 тыс.; papa-kaban (план P6) ~25 тыс.
- Этап 5, P6: kaban ~142 тыс. ток.; kaban-doeba ~150 тыс. (~90 мин, mutmut); mama-kaban ~31 тыс.
- Боевые дополнения: papa-kaban ~30 тыс.; kaban ~154 тыс.; kaban-doeba ~186 тыс. (~4 ч, mutmut — следить за шаблоном x_функция__mutmut_*); mama-kaban ~31 тыс.
- Переговоры: papa-kaban ~33 тыс.; kaban ~133 тыс.; kaban-doeba ~173 тыс. (~1,8 ч); mama-kaban ~39 тыс.
- Меню боя: papa-kaban ~49 тыс.; kaban ~137 тыс.; kaban-doeba ~199 тыс. (mutmut с TESTS — 2,5 мин); mama-kaban ~29 тыс.
- Отбор оружия: papa-kaban ~36 тыс.; kaban ~164 тыс.; kaban-doeba ~238 тыс. (~1,3 ч); mama-kaban ~30 тыс.
- Кастом. предметы, план: papa-kaban ~49+60 тыс. Партия 0: kaban ~134+158 тыс. (~27 мин); kaban-doeba ~247 тыс. (~54 мин); mama-kaban ~49 тыс.
- Партия А: kaban ~124+52+39 тыс. (~40 мин); kaban-doeba ~229+76+50 тыс. (~85 мин); mama-kaban ~33 тыс.
- Партия Б: kaban ~104 тыс. (~23 мин); kaban-doeba ~150 тыс. (~78 мин); mama-kaban ~23 тыс.
- Партия В: kaban ~74+81 тыс. (~28 мин); kaban-doeba ~161+172 тыс. (~42 мин); mama-kaban ~31 тыс.
- Торговля, план: papa-kaban ~56 тыс. Т0: kaban ~69+84 тыс. (~10 мин); kaban-doeba ~132+147 тыс. (~38 мин); mama-kaban ~32 тыс.
- Т1: kaban ~39 тыс. (~1 мин); kaban-doeba ~47 тыс. (~3 мин); mama-kaban ~25 тыс.
- Т2: kaban ~77+87+112 тыс. (~12 мин); kaban-doeba ~152+171 тыс. (~40 мин); mama-kaban ~32 тыс.
- Т3: kaban ~66+68 тыс. (~36 мин); kaban-doeba ~90+39 тыс. (~24 мин, mutmut); mama-kaban ~18+21 тыс.
- Т4: kaban ~55+63 тыс. (~20 мин); kaban-doeba ~129+144 тыс. (~49 мин); mama-kaban ~28 тыс.
- Т5: papa-kaban ~51 тыс.; kaban ~69 тыс. (~21 мин); kaban-doeba ~153 тыс. (~36 мин); mama-kaban ~36 тыс.

## Роадмап остатка BACKLOG (2026-10-08)
- **Действует ред. 4 — единая очередь 56 партий:** docs/decisions/roadmap-r4-unified.md (решения проектировщика в конце; все по рекомендациям, Э10 последним). Сводка — в начале docs/ROADMAP-PLAN.md (ред. 2 ниже — история). Ред. 3: docs/decisions/roadmap-r3-proposal.md, roadmap-r3-cost.md. Музыка: docs/decisions/music-research.md. Проверка цены ред. 2: docs/decisions/roadmap-cost-review.md.
- Порядок R4: AD1 ✅ → Б0 → Б1 → Б2 → Б3 → **Му** (BACKLOG 33, музыка; M, v8 без миграции, `[audio]` необязательна, режим без звука) → Д1 → К0 → К1 → К7к → К7х → К7д → 5а → Ж0 → Ж1 → Ж2 → Ж3 → У0 → У1 → К2–К6 → К-мульти → Ж4–Ж7 → У2 → К8–К10 (ступень II) → М0–М6 → П1–П2 → С0–С3 → Н0–Н4 → К11–К14 (ступень III) → Э10а → Э10б.
- Бюджет — по факту HANDOFF: ≈ 24,7 млн + Му ≈ 0,42 → **≈ 25,1 млн** (шкала R3 ≈ 18,3); с накладными ≈ 28–30 млн. Пересмотреть оценку после Б0–Б1.
- **Б0 (6б):** груминг+аудит+решения — docs/decisions/b0-grooming.md; план docs/B0-PLAN.md (шаги П0 сейв v8 → П1 предыстория → П2 пресет), решения в конце плана. Версии сейва сдвинуты: v8 Б0, v9 К0, v10 Ж0, v11 М0, v12 С0. П0 ✅ (сейв v8, m0008, «есть»→«откровенно», BackgroundSpec.description, раздел «Тон», WINDOW мока 22070); ревью docs/decisions/b0-p0-review.md. П1 ✅ (протокол hero_background, background_check/background_problems, BackgroundPromptBuilder, game/hero_create.py; ревью docs/decisions/b0-p1-review.md; smells 202 без запаса). П2 ✅ (campaign/presets.py+yaml, 4 пресета, `--preset`, `pack` = «как в паке», лимиты — объединение; ревью docs/decisions/b0-p2-review.md; smells 202/202). Б0 закончен; аудит ✅ docs/decisions/b0-audit.md (хвосты → BACKLOG 16; fable: план лучше, дозадач не меньше — продлить пробу на Б1). Б0 принят проектировщиком 2026-10-08 (вкл. фразу в «Тоне»); fable у papa-kaban оставлен на Б1. Груминг Б1 ✅ docs/decisions/b1-grooming.md (В1–В15 по рекомендациям, деление Б1а/Б1б). План docs/B1-PLAN.md, Q1–Q12 по рекомендациям. Б1а ✅: HeroSheet/sheet_check, наборы классов (A5), режим hero_sheet (обработчики по режимам), HeroPromptBuilder, game/hero_create (правка листа, meta/hero_sheet.json), build_world(HeroSheet) со StartRefused по имени; ревью и решения 1–5 — docs/decisions/b1-a-review.md (allowlist Б1а — снять в Б1б; пределы только в limits); тесты 10986, cov 96,57%, smells 201. Б1б (код, ревью, тесты) — docs/decisions/b1-b-review.md; codename пресетов мира (только меню); дальше — живой прогон пользователя (B1-PLAN Б1б шаг 6) → docs/decisions/b1-live.md. Живой прогон ✅ (docs/decisions/b1-live.md): баги → BACKLOG 35, партия «Б1-фикс» (план docs/B1-FIX-PLAN.md, ревью docs/decisions/b1-fix-review.md) ✅: ранний выход после offer_choices (старые журналы с текст+offer_choices не реплеятся), рассказ после загрузки, правила пп.3–4; п.5 (grim→heroic, выбор цифрой) не воспроизведён — сверить в следующем прогоне. Б2: груминг+аудит+решения ✅ docs/decisions/b2-grooming.md (L, Б2а/Б2б, лимит smells поднять — 203 на main); план ✅ docs/B2-PLAN.md, Q1–Q12 по рекомендациям (smells 205). Б2а ✅: rules/hero_options.py, game/hero_steps.py, ui/hero_wizard.py, RetryMenu, пункт «Создать пошагово»; ревью и решения Р1–Р3 — docs/decisions/b2-a-review.md; заклинаний в контенте мало → count=min(лимит, контент), пополнение — отдельная партия (BACKLOG 16, решение 2026-10-09); тесты 11595, cov 96,68%, smells 204. Б2б ✅ (код+тесты+ревью): placeholder STEPS_PLACEHOLDER, заставка только в пикере героя (splash, меню choose_number — кортеж из 4) и на экране создания, REVIEW_HINT; ревью и Р1 (править всё) — docs/decisions/b2-b-review.md; тесты 11631, cov 96,69%, smells 204/205 (лимит не опущен: >203). Живой прогон ✅ (docs/decisions/b2-live.md): багов нет, ИИ-шаг ≈ $0,01, хвост Б1 п.5 закрыт. Б2 закрыта. Б3: груминг+аудит+догруминг+решения ✅ docs/decisions/b3-grooming.md (все по рекомендациям; флаг `--import`, пак без героя разрешён, test_stage6b_done полностью, refusal на grim не блокирует). План ✅ docs/B3-PLAN.md (papa-kaban, fable), Q1–Q12 по рекомендациям. Б3 код+тесты+ревью ✅ docs/decisions/b3-review.md (тесты 11963, cov 96,78%, smells 204/205); живой прогон ✅ docs/decisions/b3-live.md (багов нет, import $0,036). Б3 закрыта. Му: груминг+аудит+решения ✅ docs/decisions/mu-grooming.md (Му-а/Му-б, эмбиент, звук только в TUI, польз. конфиг); план ✅ docs/MU-PLAN.md (Q1–Q15 по рекомендациям), Му-а ✅ (bf1ed11; ревью и решения — docs/decisions/mu-a-review.md). Дальше — Му-б (MU-PLAN B2): код kaban + тесты kaban-doeba + шаг «данные» (кандидаты треков → docs/decisions/mu-tracks.md, прослушивание пользователем). Артефакт роадмапы обновлён под R4 (та же ссылка); факт Б0–Б2а ≈3,6 млн — в 2–3 раза выше оценки, пересмотр бюджета — кабану-тестю.
- Му: svinopas ~100 тыс.; kaban-svekrov ~41 тыс.; papa-kaban (план, fable) ~208 тыс. (~15 мин).
- Му-б: kaban ~71 тыс. (~6 мин); dyadya-kaban (кандидаты треков) ~66 тыс. (~3 мин); kaban-doeba ~95+111+128 тыс. (~68 мин, mutmut); kaban правки ~83+84+90 тыс.; mama-kaban ~37 тыс.; dyadya-kaban добор ~45+30 тыс. Статус: код ✅ 1ab741a, треки ✅ 5df0aaf (15 OGG ≈32 МБ, ATTRIBUTION, test_audio_data; решения 1–10 — docs/decisions/mu-b-review.md; OGG кодирован через libsndfile — в brew-ffmpeg нет libvorbis). Живой прогон ✅ docs/decisions/mu-live.md (багов нет, CPU ~9 %). Му закрыта. Дальше по R4 — Д1. kaban (треки) ~60 тыс. (~9 мин). Ротация треков в теме — не нужна (решение 2026-10-10, один трек на тему).
- Д1 ✅ (2026-10-10): груминг+аудит+решения docs/decisions/d1-grooming.md (В1а — перенос пикеров не в Д1, строка BACKLOG 16; В4/В5 не чинить); план docs/D1-PLAN.md (Q1–Q4 по рекомендациям); код+тесты+ревью — docs/decisions/d1-review.md. Тесты 12436, cov 96,83 %, smells 206/206. Segfault mutmut не починен: forkserver ломает stats (_scproxy macOS), правило — узкие TESTS, segfault-мутантов перепроверять другими файлами (Makefile, BACKLOG 16). Живого прогона нет. Дальше по R4 — К0 (груминг: выписать поля 12 классов на 1–20 и мультикласса).
- Д1 расходы: svinopas ~94 тыс.; kaban-svekrov ~40 тыс.; papa-kaban ~191 тыс. (~16 мин); kaban ~49+54 тыс.; kaban-doeba ~133 тыс. (~83 мин, mutmut + E1–E3 сверх потолка); mama-kaban ~37 тыс.
- К0а: kaban ~151 тыс. (~7 мин); kaban-doeba ~373 тыс. (~2,9 ч, mutmut); тесты 12794, cov 96,97 %, smells 206/206; allowlist +4 поля под К1/К5 (согласие 2026-10-11). Ревью ✅ docs/decisions/k0a-review.md (В-1 а, В-2 а); mama-kaban ~57 тыс.; К0а закрыта. Дальше — К0б (kaban + kaban-doeba по K0-PLAN).
- К0б: код (kaban) ✅ 2026-10-11 — потолок из данных (`max_level`, `LEVEL_CAP`), таблицы 1–20 (ячейки, бюджет боя, `pact_slots`, `damage_severity`), клад 11-16/17+, редкость и золото по уровням, ПХ и `prepared_by_level` в данных классов; сейв остаётся v9. Тесты/ревью/живой прогон (docs/checklist-k0-live.md, не коммитить) — впереди; результат → docs/decisions/k0-live.md. Тесты+ревью ✅ (docs/decisions/k0b-review.md, В-1а, В-2а, клад 11-16 ≈ 11 900 зм, ПХ в паке обязательны): тесты 13336, cov 96,99 %, smells 206/206. Расходы: kaban ~117 тыс. (~10 мин); kaban-doeba ~131 тыс. (~16 мин, mutmut 296/336); mama-kaban ~48 тыс. Дальше — живой прогон пользователя по docs/checklist-k0-live.md → docs/decisions/k0-live.md.
- Живой прогон К0 (2026-10-11, мир drunk_dragon-00000001 — копия 29a049dc): миграция ✅; находки → BACKLOG 38; Грею выставлен xp 2050→2690 (согласие пользователя, бэкап в scratchpad сессии) — повышение 3→4 проверено ✅. Прогон закрыт: docs/decisions/k0-live.md. **К0 закрыта.** Роадмап R5 утверждён (docs/decisions/roadmap-r5-proposal.md, kaban-arhitektor ~133 тыс.). Дальше: К0-фикс (BACKLOG 38 а–г + safety_settings Gemini); П37 — груминг параллельно.
- **К0-фикс (2026-10-12):** план docs/K0-FIX-PLAN.md (papa-kaban ~149+41 тыс.), + BACKLOG 39 (пол и местоимения NPC/героя, решение проектировщика — в К0-фикс). Решения Q1–Q14 — в конце плана (все (а), кроме Q12 — пол в /sheet не показывать). Деление: К0-фикс-а (шаги 1–6), К0-фикс-б (шаг 7 + данные паков), два коммита/ревью. Размер S ≈ 0,9–1,1 млн. Ждёт «окей, кабаним».
- **П37:** груминг+аудит+решения ✅ docs/decisions/p37-grooming.md (svinopas ~52 тыс., kaban-svekrov ~36 тыс.). В1 — `manifest.preset` (тон пака меняется — принято), пары romantic→dusk_academy, grim→drunk_dragon, heroic→vale; пикер пака → BACKLOG 40. План ✅ docs/P37-PLAN.md (papa-kaban ~178 тыс.), Q1–Q4 решены (Q1/Q2 — смягчить данными паков). Старт кода — после К0-фикс-а.
- К0-фикс-а ✅ (код+тесты+ревью docs/decisions/k0-fix-a-review.md, В-1а, В-2а; расходы там же). К0-фикс-б ✅ (пол и местоимения, сброс unset/«-»; ревью docs/decisions/k0-fix-b-review.md). Дальше — живой прогон пользователя по docs/checklist-k0-fix-live.md → docs/decisions/k0-fix-live.md, затем П37 («окей, кабаним»). Обход summarizer (38 к) — в Р2.
- ⚠ 2026-10-12: обход BACKLOG 38 к) — ~/.config/ai-dm/config.toml переводит summarizer на gemini-3.8-flash (flash-lite отказывал в выжимке, мир dusk_academy-d3de6c57 стоял). Снять после фикса отказа summarizer.
- ⚠ 2026-10-11 `.git` удалён (rm -rf), копий/remote не было — репозиторий пересоздан одним коммитом-снимком. Хэши коммитов в docs (до 4978d2e) — из утраченной истории, `git show` по ним не работает. Remote — приватный GitHub PapaHusserl/ai-dm (origin); после коммита каждой партии — `git push`.
- К0: груминг+аудит+решения ✅ docs/decisions/k0-grooming.md (В1–В12; В4 по SRD 5.2 — пересмотр К-3; снаряжение NPC и список спутников в v9; деление К0а/К0б; В7 — числа сверить с SRD в плане). План ✅ docs/K0-PLAN.md (papa-kaban, fable; Q1–Q15 — все (а), решение 2026-10-11) — ждёт «окей, кабаним». К0а: код (kaban) ✅ 2026-10-11 — сейв v9 (m0009), `rules/level_up.py`, `pending_level`; тесты/ревью — в работе. Живой мир 29a049dc — схема v4 (миграция v4→v9). Расходы: svinopas ~113 тыс.; kaban-svekrov ~46 тыс.; papa-kaban (план, fable) ~256 тыс. (~17 мин).
- Пак dusk_academy (романтическая магическая академия) — 43b7760, вне R4. BACKLOG 37 — подсказка пака к пресету, вставка сразу после К0 (груминг svinopas).
- BACKLOG 36 (2026-10-11): день и ночь — распорядок NPC и лавок, без приоритета.
- Му-а: kaban ~139+146+155 тыс. (~25 мин); kaban-doeba ~162+167+200 тыс. (~54 мин, mutmut); mama-kaban ~73 тыс.
- Б3: kaban ~191+204 тыс. (~23 мин); kaban-doeba ~315 тыс. (~52 мин, mutmut); mama-kaban ~39+51 тыс.
- Б3 план: papa-kaban (fable) ~277 тыс. (~15 мин).
- Б3 груминг: svinopas ~63+73 тыс.; kaban-svekrov ~37 тыс.
- Б2б: kaban ~53+58+65 тыс.; kaban-doeba ~91+100 тыс. (~46 мин); mama-kaban ~46 тыс.; артефакт роадмапы ~99 тыс.
- Б2а: kaban ~200+10 тыс. (~18 мин); kaban-doeba ~279+17 тыс. (~1,9 ч, mutmut); mama-kaban ~75 тыс.
- Б2 груминг: svinopas ~93 тыс. (~4 мин); kaban-svekrov ~37 тыс.; papa-kaban (план) ~186 тыс. (~13 мин).
- Б1 расходы: svinopas ~39 тыс.; kaban-svekrov ~24 тыс.; papa-kaban (fable) ~257 тыс. (~18 мин).
- Б1б: kaban ~157+163 тыс. (~25 мин); kaban-doeba ~229 тыс. (~2 ч, mutmut); mama-kaban ~43 тыс.
- Б1а: kaban ~188 тыс. (~27 мин, вкл. правки ревью); kaban-doeba ~381 тыс. (~2,8 ч, mutmut); mama-kaban ~64 тыс. (3 прохода).
- Б0 расходы: svinopas ~41 тыс.; kaban-svekrov ~22 тыс. (+аудит ~36 тыс.); papa-kaban (fable, впервые) ~177 тыс. (~17 мин). П0: kaban ~62 тыс. (~5 мин); kaban-doeba ~92 тыс. (~22 мин); mama-kaban ~30 тыс. П1: kaban ~74+82+90 тыс. (~20 мин); kaban-doeba ~142 тыс.+дозадачи (~40 мин); mama-kaban ~42 тыс. П2: kaban ~47+51 тыс. (~13 мин); kaban-doeba ~92+97 тыс. (~76 мин); mama-kaban ~21 тыс.
- Сейв: v8 Б0, v9 К0, v10 Ж0, v11 М0, v12 С0; миграции нейтральны по поведению — живые миры играть можно.
- Важно: трек 1.5 не закрыт (4 класса только 1 ур., 3 монстра). BACKLOG 31 — остальные 7 классов.
- План AD1 ✅: docs/AD1-PLAN.md, решения Q1–Q5 по рекомендациям — docs/decisions/ad1-review.md. Дальше — «окей, кабаним».
- AD1 план: papa-kaban ~63 тыс. (~3 мин).
- AD1 код: durable (fsync слота, `[persistence] durable`), устойчивый PlaySession.submit (apply_line/render_step/offer_is_stale), досрочный выход summarizer (run_round), fence в report.md, make dead зелёный (vulture_allowlist по Q2), `make mutate FUNCS`; ревью — docs/decisions/ad1-review.md. Allowlist 13 имён (решение 1а + 3 имени kit-ов), smells 202, cov 96,4%, тесты 10310.
- AD1 расходы: kaban ~132+161 тыс. (~27 мин); kaban-doeba ~240+243 тыс. (~1,9 ч, mutmut); mama-kaban ~23 тыс.
- Роадмап ред. 3 (BACKLOG 24–32, блок У «Услуги NPC»): docs/decisions/roadmap-r3-proposal.md (компромисс с кабаном-тестем, решения проектировщика в конце), docs/decisions/roadmap-r3-cost.md (заменён ред. 4). HTML: https://claude.ai/artifact/4J8j5zwtaoKNACPgTK9NA3. Расходы: papa-kaban ~46+54 тыс.; kaban-test ~22 тыс.
- AD1, Q4 (решение проектировщика): после раннего выхода summarizer старые репорты 6а с границей сцены/главы (в журнале лишний вызов summarizer с текстом «Готово.») могут не воспроизвестись: `--replay-report` вернёт код 1 «расхождение». Новые репорты не затронуты; в tests/fixtures и tests/golden журналов с summarizer нет, эталонов replay для правки нет.
- Расходы: papa-kaban ~45+77+45 тыс.; kaban-test ~34 тыс.
- **2026-10-12:** живой прогон К0-фикс отменён проектировщиком; К0-фикс закрыта без прогона (чек-лист остаётся для будущих прогонов). Дальше — П37 (код kaban + тесты kaban-doeba по docs/P37-PLAN.md).
- **П37:** код kaban ✅ 2026-10-12 (manifest.preset у 3 паков, `preset_packs`, подсказка в меню/заметках cli.py, Q1/Q2 данными); тесты kaban-doeba и ревью — дальше.
- П37 расходы: kaban ~51 тыс. (~12 мин); kaban-doeba ~83 тыс. (~27 мин, mutmut); mama-kaban ~25 тыс. Ревью docs/decisions/p37-review.md (В-1 — по умолчанию а).
- **П37 ✅ 3ae371f (2026-10-12):** тесты 13708, cov 97 %, smells 205/206. Дальше по R5 — Р1 «Память боя» (груминг: svinopas + kaban-svekrov). Живой прогон П37 не нужен (чек-лист docs/checklist-p37-live.md — на --mock, по желанию).
- **Р1 груминг+аудит ✅ 2026-10-12** — docs/decisions/r1-grooming.md (В1–В4 блок., В3-доп, В5–В9). Решения приняты (В3-доп б, В6б, В7б — не по рекомендации); план docs/R1-PLAN.md ✅, Q1–Q4 по рекомендациям; ждём «окей, кабаним».
- **Р1 «Память боя»:** код kaban ✅ 2026-10-12 (game/combat_fold.py, TurnRunner.end_fight, combat.engine.participant_name; сейв v9, миграций нет). Тесты kaban-doeba и ревью — дальше. Риск: репорты ходов, закончивших бой до Р1, при `--replay-report` дадут код 1 (свёртка в `after`) — как прецедент AD1 Q4.
- **Р1 ✅ закоммичена 2026-10-12:** тесты 13829 (+121), mutmut 216/218 (2 эквивалентных), smells 206/206 (запаса нет — до следующей партии упростить или решить про лимит). Ревью docs/decisions/r1-review.md, п.3 «потери по hp<max» — оставлено проектировщиком; флак TUI → BACKLOG 41. Replay старого репорта боя на сценарии дал код 0. Расход: kaban ~100+19 тыс., doeba ~170 тыс., mama ~24 тыс., svinopas ~63 тыс., svekrov ~22 тыс., papa ~152 тыс. Дальше — живой прогон Р1 у проектировщика (docs/checklist-r1-live.md), затем Р2 (груминг).
- **2026-10-13:** сейв dusk_academy-d3de6c57 поправлен вручную (пол 6 NPC из пака, Мире — зверь «Булочка», капибара; бэкапы *.bak-20261012-2122, *.bak-20261013-091929; Брандоку пол не задаём). BACKLOG 41–44. Решения проектировщика: фикс-партия **Ф1** = BACKLOG 43 (пол NPC старых миров из пака) + 44 (зверь Повелителя зверей) + разгрузка smells (упрощать, лимит 206 не поднимать); по правилу R5 фикс без груминга — план papa-kaban docs/F1-PLAN.md ✅, Q1–Q6 по рекомендациям; ждём «окей, кабаним». Живой прогон Р1 перенесён на следующий раз (совместить с прогоном Ф1/Р2).
- **Ф1:** код kaban ✅ 2026-10-13 (merge.fill_identity — пол NPC/героя пака при загрузке; companion_update + companion_due; разгрузка smells ярус 1: fold_text, check_close, session.py, hero_flag_refusal). Тесты kaban-doeba (вкл. ярус 2 smells) и ревью — дальше.
- **Ф1 ✅ закоммичена 2026-10-13:** тесты 13919 passed (флак TUI в этот раз прошёл), cov 97 %, smells 200/206, mutmut — выжившие только на тексте message и дефолтах. Ревью docs/decisions/f1-review.md; правка текста правила companion_due (тире, дубль) — оркестратором. WINDOW мока 23500→24000 (4-й подъём подряд) — вопрос проектировщику про BACKLOG «бюджет статической части промпта». Дальше — живой прогон Р1+Ф1 (docs/checklist-r1-live.md, docs/checklist-f1-live.md; мир dusk_academy — Булочка уже в сейве, проверять companion_due на другом beast_master), затем груминг Р2.
- **2026-10-13 решения:** BACKLOG 45 (бюджет статической части промпта) — без приоритета. Живой прогон Р1+Ф1 — после Р2, одним прогоном на три партии. Дальше — груминг Р2 (svinopas + kaban-svekrov).
- **Р2 груминг+аудит ✅ 2026-10-13** — docs/decisions/r2-grooming.md (В1–В14; блок. В1, В2, В5, В8, В10 + В13 по аудиту). Решения приняты (В1б — только затишье, не по рекомендации; В13 → BACKLOG 46; остальное по рекомендациям). План papa-kaban ✅ docs/R2-PLAN.md (~150 тыс.); Q1–Q3 по рекомендации, Q4б (приписка с «за кадром или намёком»); ждём «окей, кабаним». Расход: svinopas ~73 тыс., svekrov ~25 тыс.
- **Р2 «Темп и отказы»:** код kaban ✅ 2026-10-13 (narrator_rules «Темп», TurnRunner.attempt/retry_result/SOFTEN_NOTE, MasterSession.note, SummarizerSession.chain/backup, boundary.concat_chapter, summarizer_backup в GameApp/cli). Тесты kaban-doeba и ревью — дальше; живой прогон — docs/checklist-r2-live.md (папа/оркестратор).
- **Р2 ✅ закоммичена 2026-10-13:** тесты 14072 passed, cov 97 %, smells 200/206, mutmut — выжившие только эквивалентные/старый код. Ревью docs/decisions/r2-review.md (п.2 «лишний except TurnFailed» отклонён — ветка нужна). WINDOW мока 24000→24500 (5-й подъём, BACKLOG 45). Расход: kaban ~66+78 тыс., doeba ~243+248 тыс., mama ~25 тыс., papa ~174 тыс. Дальше — живой прогон Р1+Ф1+Р2 у проектировщика по единому чек-листу docs/checklist-r1-f1-r2-live.md (три прежних объединены 2026-10-13; обход summarizer в ~/.config/ai-dm/config.toml снимается в его п.12); затем К1 (груминг).
- **К1 груминг+аудит ✅ 2026-10-13** — docs/decisions/k1-grooming.md; решения все (а), В7 снят (уже сделано), апкаст в бою и вне. План papa-kaban ✅ docs/K1-PLAN.md (~229 тыс.); Q1–Q5 по рекомендациям (Q2: книга заклинаний → BACKLOG 47); ждём «окей, кабаним». Расход: svinopas ~65 тыс., svekrov ~31 тыс.
- **К1 код (kaban) ✅ 2026-10-13:** дальность 10/30/60/120, концентрация по часам (`expire_concentration` во всех точках сдвига часов), апкаст (бой и вне боя), `rest` с `prepared_swap`; сетка sim_combat — docs/decisions/k1-sim-combat.md (S_WIN 3→2, golden перегенерировать). Тесты kaban-doeba, ревью, живой прогон (docs/checklist-k1-live.md, не коммитить) — дальше.
- **К1 ✅ закоммичена 2026-10-13:** тесты 14368 passed, cov 97,3 %, smells 204/206, dead/ruff чисто; mutmut — выжившие эквивалентные/шум/старый код. Ревью docs/decisions/k1-review.md: В-1а (метание оружия → BACKLOG 48, в чек-листе improvised_thrown), В-2а (Метка кончается ровно в срок, SRD). Сетка боёв (воин 42,5 %→32 % побед) — сложность принята проектировщиком (docs/decisions/k1-sim-combat.md). HONEST_SEED 57→156, S_WIN 3→2, WINDOW мока 24500→25000 (6-й подъём, BACKLOG 45). Расход: kaban ~128+3 тыс. (~19 мин), doeba ~318+11 тыс. (~1,7 ч, mutmut ~1 млн по оценке doeba), mama ~51 тыс. Дальше — живой прогон Р1+Ф1+Р2 (docs/checklist-r1-f1-r2-live.md) и К1 (docs/checklist-k1-live.md), затем К7к (груминг).
- **К1 аудит+разбор полётов ✅ 2026-10-13:** docs/decisions/k1-audit.md (В7 подтверждён задним числом; fable у papa-kaban оставлен), docs/decisions/k1-cost.md (факт ≈0,84 млн при оценке 1,25). Шкала роадмапа R6 (×0,7, остаток ≈45 млн) — в docs/ROADMAP.md. Агенты kaban и kaban-doeba: раздел «Долгие прогоны» — фон + блокирующее ожидание ≤10 мин вместо опроса `sleep 60; tail` (бэкап ~/.claude/backups/skills-agents-20261013-2323); проверить экономию на К7к. Оркестратор пишет свой расход в строку партии (с К7к). Расход: svekrov ~41 тыс., kaban-test ~28+21 тыс. **Дальше:** живой прогон проектировщика по docs/checklist-r1-f1-r2-live.md и docs/checklist-k1-live.md, затем груминг К7к (svinopas + kaban-svekrov).
- **К7к груминг+аудит+решения ✅ 2026-10-13** — docs/decisions/k7k-grooming.md (живой прогон по-прежнему отложен проектировщиком). Решения: В1а (порог 80 % снят), В3а, В4а (warn_danger сделан), В6 — пересчёт КД в К7х, В8 — запас уровней 2–5 в К7х, В11 (снято/не задано) — ок; прочее по рекомендациям. Расход: svinopas ~63 тыс., svekrov ~25 тыс. Дальше — план papa-kaban docs/K7K-PLAN.md (в работе), затем аппрув.
- **К7к план papa-kaban ✅ 2026-10-14** — docs/K7K-PLAN.md (≈0,85–0,9 млн; расход papa ~187 тыс.). Ждём ответы на Q1–Q7 и «окей, кабаним».
- **К7к код ✅ 2026-10-14 (kaban; ревью mama-kaban и тесты doeba впереди, не закоммичено):** `engine.damage`/`engine.impose` (иммунитеты/сопротивления/уязвимости и иммунитет к состояниям), `Monster.armor/shield` + `chain_shirt`, трофеи доспех/щит (`trophies.body_equipment`, `mark_looted`), сложность (`/difficulty`, `--difficulty`, меню, `encounter.tier_of`), сетка `sim_grid` + `make sim-grid` + `devtools/sim_grid_baseline.yaml` (docs/decisions/k7k-sim-grid.md). smells 206/206, ruff/dead чисто. Чек-лист живого прогона — docs/checklist-k7k-live.md.
- **К7к ✅ закоммичена 2026-10-14:** тесты 14829 passed, cov 97,35 %, smells 204/206, dead чисто; mutmut — K7k-строки убиты. Ревью docs/decisions/k7k-review.md (все правки внесены; 3а — difficulty в сетке «на будущее, К7д»), отклонения — K7K-PLAN «Отклонения при реализации», сетка — docs/decisions/k7k-sim-grid.md. BACKLOG 50, 51. Расход: svinopas ~63, svekrov ~25, papa ~187, kaban ~160+180+190, doeba ~347, mama ~55 тыс. (субагентные счётчики). Му-р вставлен в роадмап (поле в Ж0, код хвостом Ж3; замер BACKLOG 45 в Ж0; papa ~75 тыс.). Живой прогон по-прежнему отложен проектировщиком (чек-листы r1-f1-r2, k1, k7k). **Дальше:** груминг К7х (svinopas + kaban-svekrov).
- **К7х груминг и план ✅ 2026-10-14:** груминг, аудит и решения — docs/decisions/k7x-grooming.md (В2: монстры тоже толкают). План — docs/K7X-PLAN.md, Q1–Q4 по рекомендациям, оценка ≈0,8 млн. Расход: svinopas ~72, svekrov ~19, papa ~185 тыс. **Дальше (устарело, см. ниже):** аппрув плана проектировщиком → «окей, кабаним» (kaban + kaban-doeba параллельно, затем mama-kaban).
- **К7х код ✅ 2026-10-14 (kaban; тесты doeba и ревью mama-kaban впереди, не закоммичено):** `combat/falling.py` (падение при `push`), `combat/shove.py` (толчок монстров, `shove:*`, `pick_shove`), `[disarm].mode`/`enemy_chance`, `step_to_weapon`, `equipment` в бою (КД, потерянное оружие, перенос при старте), Истребитель орд (`horde_breaker`), `rest.prey_swap`, BACKLOG 51. Схема запросов изменилась (`Rest.prey_swap`, текст `push`): `--replay-report` старых репортов с `rest`/боем даст код 1. Чек-лист — docs/checklist-k7x-live.md.
- **К7х ✅ закоммичена 2026-10-14:** тесты 15307 passed, cov 97,39 %, **smells 206/206 — запас исчерпан**, dead чисто; mutmut — выживших по К7х нет (эквивалентные разобраны). Ревью docs/decisions/k7x-review.md (все обязательные и желательные правки внесены), отклонения кабана — там же. BACKLOG 52 (размер цели толчка — до К7д). TUI-тест `test_second_ctrl_c_calls_hard_exit…` падает и на чистом HEAD (флак, не К7х). Расход: svinopas ~72, svekrov ~19, papa ~185, kaban ~143+25, doeba ~289+61, mama ~65 тыс. ≈ **0,86 млн** (оценка 0,8). Живой прогон отложен (чек-листы r1-f1-r2, k1, k7k, k7x). **Дальше:** аудит К7х (kaban-svekrov) + разбор полётов (kaban-test), затем груминг К7д (svinopas + kaban-svekrov); перед К7д решить, как освободить запас smells.
- **К7х аудит и разбор полётов ✅ 2026-10-14:** docs/decisions/k7x-audit.md (по объёму чисто, fable у papa оправдан), docs/decisions/k7x-cost.md (факт 0,86 при 0,8; шкалу R6 не трогать до К7д, пересмотр при переборе >15 %). Решения проектировщика: BACKLOG 52 — в К7д («маму надо слушать»); В12 (smells 204 → 206) принят; аппрув К7х подтверждён, отклонения 1–10 дописаны в K7X-PLAN; **smells — первый шаг плана К7д (−4–6) + правило нулевого баланса (партия не повышает smells, рост компенсирует сама)**; экономия kaban-test принята: doeba гоняет `make cov` один раз в конце (по ходу — pytest затронутых файлов), длинные прогоны kaban/doeba — в фоне с ожиданием уведомления, papa сверяет список mutmut `модуль:функция` с кодом, оркестратор пишет свой расход в строку партии. Правка промптов агентов — через skill-intake. Расход: svekrov ~64, kaban-test ~31 тыс. Промпты поправлены (skill-intake, бэкап skills-agents-20261014-1640): doeba — cov один раз в конце, papa — п.7 сверка функций grep-ом; ожидание прогонов не менялось (уже фон + блокирующее ожидание, дробление — потолок Bash 10 мин). **Дальше:** груминг К7д (svinopas + kaban-svekrov) с BACKLOG 52 и правилом smells.
- **К7д код ✅ 2026-10-14 (kaban; тесты doeba, ревью mama-kaban, mutmut и `make cov` впереди, не закоммичено):** по docs/K7D-PLAN.md + ответы проектировщика (Q5а — взрыв механикой). Шаг 0: разгрузка smells 206 → 200 (`death_saves.fatal/hit_while_down`, `derived.base_armor_parts/feat_ac_parts/effect_ac_parts/pierce_parts`, `available.standard_actions/bonus_actions/circle_options`, `controllers.approach`), `SMELLS_MAX = 200`. 27 монстров ПО 0–5 (`srd/data/monsters`, 21 новая feature) — импорт Open5e `srd-2024` + иммунитеты из PDF SRD 5.2.1 (в Open5e они неполны у 7 монстров), скрипт вне репозитория (`~/projects/ai-dm-k7d-import/`). Код: `combat/monster_traits.py` (Тактика стаи, Стойкость нежити, доп. урон, `on_hit`), `combat/death_burst.py`, `DamageResult.damage_types`, `Monster.fly_ft/death_burst`, `MonsterAction.extra_damage_*/on_hit`, `content/monster_checks.py`, `falling.hovers`, `loot.NO_COIN_TYPES`, `shove.size_ok` + `improvise.size_problem` (BACKLOG 52 ✅), `prompt.monster_trait_notes` → `combat.monster_traits`, `devtools/sim_cellar.py` (сцена `cellar`, пересчёт базовой линии), подвал Вейла: `old_crypt`, `disarmer` у `goblin_boss`/`wight`. Сейв v9 без изменений. Отклонения и открытые вопросы — в отчёте kaban (чат) и docs/K7D-PLAN.md. BACKLOG 53–58. Чек-лист — docs/checklist-k7d-live.md (не коммитить).
- **К7д ✅ закоммичена 2026-10-14:** тесты 16056 passed, cov 97,51 %, smells 200/200 (−6, нулевой баланс соблюдён), dead чисто, sim-grid --check 0. Ревью docs/decisions/k7d-review.md (все обязательные и желательные правки внесены, отклонения 1–9 приняты; калибровка `cellar` — после живого прогона К7; narrator_rules не трогаем). Шаг 0 отдельным коммитом не вышел — один коммит партии. Расход ≈ 1,01 млн при оценке 0,89. Живой прогон отложен (чек-листы r1-f1-r2, k1, k7k, k7x, k7d). **Дальше:** BACKLOG 59 — пустая сцена на запасной модели рассказчика (dusk_academy, ход 396): (2) повтор хода при коротком финальном тексте после инструментов, (3) разбор `refusal_fallback`/thinking в anthropic_adapter — мини-партия; затем аудит К7д (kaban-svekrov) и разбор полётов (kaban-test).
- **B59 код ✅ 2026-10-14 (kaban; тесты doeba впереди, не закоммичено):** `min_narration_chars` (80), `TEXT_NOTE`/`RETRY_NOTES`, `check_told` в `explore_turn` (вне боя), `retry_result(started, reason)` с тегом `{reason}_retry`, `[llm] thinking`/`thinking_display`, `AnthropicAdapter.thinking_of` и `usage_of`. Офлайн-реплей репорта 396: код 1 «лишний вызов 4». Чек-лист — docs/checklist-b59-live.md. smells 200/200.
- **B59 ✅ закоммичена 2026-10-14:** ревью (2 раунда) — docs/decisions/b59-review.md (haiku-4* без thinking, `disabled` убран). Живой ход 399 показал, что `short_retry` не лечит причину: Sonnet пишет сцену в мышлении, после `offer_choices` выдаёт одну строку (схема старая, с 5 октября). Разбор papa и решения проектировщика — docs/B59-PLAN.md «Дополнение»: В2 `CHOICES_NOTE` (`MasterSession.run`/`choices_unseen`, при `done`, все провайдеры), В1 правило в narrator_rules.md и docstring `OfferChoices`, В3 effort narrator medium (и Opus — решение). Все старые репорты расходятся с журналом на вызове 1 (system). Тесты 16136 passed, cov 97,51 %, smells 200/200, dead чисто; WINDOW мока памяти 25200. Живой прогон по docs/checklist-b59-live.md — за пользователем (на Gemini был 503, IPv6 до googleapis не работает). BACKLOG 60, 61 заведены. **Дальше:** мини-партия BACKLOG 60 (план papa-kaban), затем аудит К7д+B59 (kaban-svekrov) и разбор полётов (kaban-test).
- **Gemini, техдолг, R6 — 2026-10-14/15 (без кода):** Gemini 503 «high demand» с 14.10 14:15 UTC — отказ Google по ёмкости (ping curl-ом тоже 503; отвечают gemini-4-argon, gemini-3-flash-preview, gemini-3.5-flash-lite), зависания — наши: IPv6 до googleapis сломан + пофазный таймаут 180 с (docs/decisions/gemini-503-research.md). Временно в ~/.config/ai-dm/config.toml: summarizer 3-flash-preview, запасной рассказчик argon, цены/окна (бэкап config.toml.bak-20261014). OpenAI исследован и отложен (docs/decisions/openai-research.md, BACKLOG 65). Сбор техдолга по 32 репортам — docs/decisions/tech-debt-2026-10-14.md (T1–T9 → BACKLOG 62–64). dusk_academy откатан на ход 395 (снимок репорта t396; бэкап saves/dusk_academy-d3de6c57.bak-20261015-0026; auto-1…3 с отменённым прогрессом не удалять). Лишние 6000 cp в drunk_dragon — оставить. **R6 утверждена** — docs/decisions/roadmap-r6-proposal.md (решения §10), docs/ROADMAP.md переписан. **Дальше:** #17 Т60 «Сеть» (без груминга: план papa-kaban по BACKLOG 60 + решения в нём), затем 17а аудит К7д+B59 и разбор полётов, 18 ТВ, 18п ЖП1.
