# ТБ Бюджет контекста (BACKLOG 56, 45, 15, 71, 76; хвост 30 `records_for`)

R7 #1, мини, без груминга. Сейв v10 без изменений. Smells 200/200 — нулевой баланс. Смета ≈ 0,45 млн.
План — papa-kaban (fable), 2026-10-17. Статус: реализация, правки по ревью.

## Суть
- 76 (шаг 0): mutmut в `mutants/` — `also_copy += ["README.md", "Makefile"]` (`docs/` тесты не читают).
- 56: рассказчик видит в `monster_ids` только монстров пака (поле манифеста `monsters`), реестр остаётся полным.
- 45: замер статики (правила + схемы инструментов) с порогом `STATIC_MAX` в тесте (ratchet).
- 15: `chars_per_token` по провайдеру; `api_tokens` у Gemini без двойного счёта `cache_write`.
- 71: при мягком сбое world его записи журнала — `aborted`, summarizer — `committed` (разметка по роли).
- 30: ревизия `records_for` — предпосылка «прогоны подряд» подтверждена, только комментарий.

## Решения (архитектура)
1. **76** — `pyproject.toml` `[tool.mutmut] also_copy` + `README.md`, `Makefile`. Проверка: `rm -rf mutants && make mutate
   FUNCS="ai_dm.content.registry:ContentRegistry.ids" TESTS="tests/unit/content tests/unit/devtools"` — stats без
   `FileNotFoundError`. Запасной вариант — `cp` в цели `make mutate`.
2. **56** — `CampaignManifest.monsters: list[str] = []` (пусто — все). `check_manifest_monsters(pack, registry)` (вызов из
   `check_manifest`): неизвестный id → `campaign.yaml: поле monsters: неизвестный монстр 'x'`; NPC пака с `monster_id` вне
   непустого списка → ошибка. `campaign/loader.py:pack_monster_scope(pack_dir) -> list[str] | None` (только `campaign.yaml`;
   `None` при отсутствии/невалидности/пустом списке). `ContentRegistry(items, monster_scope=None)`, `with_items` переносит
   scope, `narrator_monster_ids()` = `sorted(scope ∩ ids("monster"))` или все. `cli.campaign_registry` ставит scope.
   `PromptBuilder.world_block` и сообщение об ошибке `start_combat` — через `narrator_monster_ids()`; проверка существования
   монстра — по полному реестру. `fight_debug` не трогаем.
3. **45** — `PromptBuilder.static_tokens(mode) -> {rules, tools, total}` по общему `chars_per_token`. Тест
   `tests/unit/master/test_static_budget.py`: `STATIC_MAX` = текущий `explore.total` + ~3 % после 56, на реестре без пака;
   подъём — только с причиной в шапке теста. `devtools/prompt_budget.py` + `make prompt-budget` (не в `quality`) — по Q2.
   `world.md` паков — без порога. Ужимка `narrator_rules.md` — не в ТБ.
4. **15 cpt** — `MasterConfig.chars_per_token_by_provider: dict[str, float]` (`gt=0`), `cpt_for(provider)`;
   `app_defaults.toml`: `anthropic = 2.2` (Q3); gemini/mock — общий 2.5. `PromptBuilder.build` берёт `cpt_for(role.provider)`.
5. **15 api_tokens** — `master/session.py:api_tokens(usage, provider)`: `input + cache_read` + `cache_write + cache_write_1h`
   кроме gemini (у Gemini токены явного кэша уже в `cache_read`).
6. **71** — `Journal.mark_turn(run_id, status, role=None)`; `TurnRunner.mark_journal(..., role=None)`; `take_boundary`: при
   `done.error is None`, теге `world_skipped` и `run_id == done.world_run_id` — сначала `aborted` для `role="world"`, затем
   общая разметка. Отдельный `run_id` у world отклонён (ломает «записи прогона подряд»). Новых полей нет.
7. **30** — правка комментариев `records_for`/`mark_turn`; в BACKLOG 30 строка `records_for` → ✅ ТБ (пункт заморожен).
8. **Не делаем**: пятая ступень вытеснения и `WINDOW` мока (Ж0/Ж3), отказ `start_combat` вне списка пака, ужимка правил,
   `plan.meta()`, cpt gemini ≠ 2.5.
9. **Smells**: проверка `monsters` — отдельной функцией; при 201+ — компенсация в том же файле.

## Затронутые функции (mutmut)
`ai_dm.content.registry:ContentRegistry.narrator_monster_ids ai_dm.content.registry:ContentRegistry.with_items
ai_dm.campaign.loader:pack_monster_scope ai_dm.campaign.loader:check_manifest_monsters ai_dm.ui.cli:campaign_registry
ai_dm.master.prompt:PromptBuilder.world_block ai_dm.master.prompt:PromptBuilder.static_tokens
ai_dm.master.prompt:PromptBuilder.build ai_dm.protocol.handlers.combat:start_combat ai_dm.config.app:MasterConfig.cpt_for
ai_dm.master.session:api_tokens ai_dm.llm.journal:Journal.mark_turn ai_dm.game.turn:TurnRunner.mark_journal
ai_dm.game.turn:TurnRunner.take_boundary`; TESTS — `tests/unit/{content,campaign,master,config,llm}`,
`tests/unit/game/test_ts_world_skip.py`, `tests/unit/game/test_game_world_boundary.py`.
Без изменений: схема сейва, `state/*`, `persistence/*`, `game/boundary.py`, адаптеры, `narrator_rules.md`, `memory_script.py`.

## Шаги kaban
0. 76 + проверка mutmut. 1. 56 (+ списки в `campaign.yaml` по Q1). 2. 45 (число `STATIC_MAX` — кабан, через оркестратора
doeba). 3. 15. 4. 71 + 30. 5. smells/dead, доки (ARCHITECTURE: `master.context`, журнал E, паки; TZ.md:606), BACKLOG
(56/45/71/76 → done/, пометки 15 и 30), handoff; ROADMAP — архитектор.

## Тесты kaban-doeba
- 76: `also_copy` содержит `README.md`, `Makefile`.
- 56: манифест (валидный список, неизвестный id, NPC вне списка, пусто/нет поля — совместимость `vale`, `test`);
  `pack_monster_scope` (None/нет файла/битый YAML/пусто/список); `narrator_monster_ids` (сортировка, пересечение),
  `with_items` сохраняет scope, `ids("monster")` полный; `system[1]` со scope; `campaign_registry` для dusk_academy/vale/None;
  `start_combat` — ошибка перечисляет scope, монстр вне scope принимается; оба пака грузятся, списки по Q1.
- 45: порог по всем режимам `MODE_TOOLS`, `total == rules + tools`, `explore` максимальный; `prompt_budget.main`, Makefile.
- 15: дефолты и перекрытие `chars_per_token_by_provider`, `0` → ошибка; `cpt_for`; оценка anthropic > gemini;
  `static_tokens` не зависит от провайдера; `api_tokens` anthropic=10 / gemini=3; через `MasterSession.call` с gemini.
- 71: `mark_turn(role=)` — только своя роль, `aborted` не перезаписывается, `role=None` как раньше, сжатые сегменты;
  граница: мягкий сбой world → world aborted / summarizer committed; успех — всё committed; фатальный — всё aborted;
  `resume_boundary` так же.

## Точки проверки
Мок: порог статики зелёный; `prompt_budget` — у dusk_academy/drunk_dragon `monster_ids` короче на ~150–200 ток.; мок-граница
с отказом world — разметка по роли. Эффект на `api_tokens` Gemini — смотреть в ЖП2.

## Риски
1. Тесты на `ScriptedAdapter(provider="anthropic")` — оценки +14 % при cpt 2.2; `test_master_session_log.py:299` может
   потребовать пересчёта — прогнать `tests/unit/master tests/unit/game` после шага 3.
2. `with_items` без scope — фильтр молча пропадает у миров с сюжетными предметами; тест обязателен.
3. `STATIC_MAX` — на реестре без пака; зафиксировать в шапке теста.
4. `also_copy` файлов может не поддерживаться — запасной `cp`.
5. Паки игрока: списки действуют со следующего запуска без миграции; бой с монстрами вне списка работает.

## Вопросы к проектировщику
- **Q1 списки `monsters`.** dusk_academy: `wolf, dire_wolf, giant_rat, swarm_of_rats, giant_spider, hawk, mastiff, panther,
  black_bear, boar, shadow, specter, animated_armor, homunculus, guard`. drunk_dragon: `guard, goblin_warrior, goblin_boss,
  wolf, dire_wolf, giant_rat, swarm_of_rats, giant_spider, black_bear, boar, ghoul, ghast, zombie, ogre_zombie, skeleton,
  wight, shadow, specter, gargoyle, magmin, fire_elemental, earth_elemental, dust_mephit, steam_mephit, homunculus`.
  vale, test — без списка. (а) принять — рек.; (б) свои.
- **Q2 `make prompt-budget`.** (а) делать — рек.; (б) только тест с порогом.
- **Q3 cpt Anthropic.** (а) 2.2 — рек.; (б) 2.3.

## Решения
2026-10-17, проектировщик: Q1 (а) списки как предложены; Q2 (а) `make prompt-budget` делать; Q3 (а) anthropic = 2.2.
2026-10-17, проектировщик, Q4 (после ревью): статика explore на anthropic при 2.2 ≈ 32k > `context_cap` 30000 — каждый ход
вытеснял бы всю динамику. Вариант (в): механизм `chars_per_token_by_provider` остаётся, дефолт пуст (anthropic = 2.5);
значение 2.2 и пересмотр `context_cap` — в Ж0 (BACKLOG 77). Q3 тем самым отложен.

## Правки по ревью
Ревью mama-kaban, 2026-10-17:
1. Блокер: статика anthropic при 2.2 > `context_cap` → `context_overflow` каждый ход. Решение Q4 (в); тест «дефолтный конфиг,
   anthropic, explore, пустая история — без вытеснения»; BACKLOG 77.
2. `STATIC_MAX` 28900 при `context_cap` 30000 оставляет 1–2k на динамику — в BACKLOG 77 (Ж0).
3. `test_model_keeps_big_window_budget_before_switch`: `context_cap` возвращён к 30 000.
4. `take_boundary`: повторный `call_numbers.pop` — безвреден, без правки.
5. Хелперы `scoped()` в тестах — через `with_items({})` вместо приватного `_items`.
6. Отклонение kaban: `also_copy` += `scripts/` (иначе stats падал на `test_migrate_dusk_18plus`).
7. `chars_per_token_by_provider` — `Field(default_factory=dict)`.
8. Переносы вставок в ARCHITECTURE.md.
Факт по 56: весь `monster_ids` — 158 ток.; dusk_academy −85, drunk_dragon −30 (план ждал 150–200).
2026-10-17, проектировщик, по аудиту: запас под динамику (`STATIC_MAX` ≈ `context_cap`) — в Ж0, BACKLOG 77 (а);
приоритет 77 — high.

## Итог

Закрыто 2026-10-17. Пункты беклога: 45, 56, 71, 76 → docs/done/; 15 — частично (механизм cpt и `api_tokens`),
п. 2.2 → BACKLOG 77; 30 — `records_for`.

**Источник токенов:** `metrics.py` по сессии
`~/.claude/projects/-Users-vladislavahtamov-projects-ai-dm/f212eb91-0b65-4778-8876-10fc02515fe9/`
(каталог `2b7ea4c1-…` из промпта — сессия R0 от 2026-10-14, не этот шаг); ориентир оркестратора — `tokens` хэнд-бэков.
**Цены:** https://platform.claude.com/docs/en/about-claude/pricing, 2026-10-17 (fable — по ценам Opus).

| Партия | Смета | Факт (tokens хэнд-бэков) |
|---|---|---|
| ТБ целиком | 0,45 млн | ≈ 0,65 млн (+45 %): правки doeba (164k) и разбор мутантов (43k) сметой не заложены |

| Роль | Модель | Токены (ориентир / пик контекста metrics.py) | $ |
|---|---|---|---|
| papa-kaban | fable-5-1 | 125k / 114k | 0,90 |
| kaban | sonnet-5-5 | 84k / 81k | 0,41 |
| kaban-doeba (2 запуска: тесты + правки) | sonnet-5-5 | 159k + 164k / 164k | 2,34 |
| разбор мутантов | sonnet | 43k / в таблице metrics.py не выделен | не посчитано |
| mama-kaban | opus-5-5 | 42k / 41k | 0,24 |
| kaban-svekrov | opus-5-5 | 36k / 35k | 0,21 |
| kaban-arhitektor (ROADMAP) | fable-5-1 | — / 26k | 0,13 |
| оркестратор | opus-5-5 | пик 120k | 1,88 на момент подсчёта 20:02 |
| kaban-test | opus-5-5 | пик 22k | 0,13 на момент подсчёта 20:02 |

**Итого:** смета 0,45 млн → факт ≈ 0,65 млн токенов субагентов; $6,25 по metrics.py (без разбора мутантов,
оркестратор и тесть — неполные). Главная статья — kaban-doeba ($2,34, 37 %).

**Тесты:** полный прогон 17297 passed / 1 failed (`test_architecture` — исправлено: devtools не импортирует ui);
cov 97 %; smells 200/200; `make dead` чисто; mutmut — 221 выживший: 4 убиты новыми тестами, 4 эквивалентных,
остальные на старых строках → BACKLOG 78.

**Проблемы:**
- Экономия по 56 меньше плана: −85 (dusk_academy) / −30 (drunk_dragon) ток. против 150–200.
- Блокер п. 2.2 (статика > `context_cap`) → BACKLOG 77.
- kaban делал `git stash` поверх файлов doeba.
- `mutmut run` одного мутанта гоняет stats по всему tests/.

Разбор — кабан Декарта.
