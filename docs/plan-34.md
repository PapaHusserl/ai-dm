# Шаг 34 — means/opportunity в пресетах героев пака (BACKLOG 34)

## Суть
`campaign/build.py` переносит из `HeroPreset` в `HeroState` только `motive`. Добавить `means` и `opportunity` в
`HeroPreset` и перенос в `build_hero`. Без полей сейва. Шаг взят наполнителем на время живого прогона ЖП3.

## Решения (проектировщик, 2026-10-19)
- В1. Пресет при загрузке пака проверяется по правилам листа героя, ссылки в триггерах — тоже; `means` 0..3
  (пустой разрешён, у листа 1..3).
- В2. `opportunity` в пресете — не больше двух, как у листа.
- В3. Наполнить паки: drunk_dragon/grey и vale (arn, grey, liel — им же `motive`); тексты — проектировщику на вычитку.
- В4. Живые сейвы не трогаем — касается только новых миров.
- В5. Расхождение пресета и листа героя (`apply_hooks`): главнее лист; пресет — только когда в листе пусто.
- В6. TZ: `character.yaml` → `heroes/<id>.yaml` (TZ.md ≈ 125, 556, 559) — поправить в этом шаге.

## Груминг
Свинопас и аудит свекрови — отчёты в чате (scratchpad), факты по коду подтверждены; паки — в `campaigns/`.

## План

Папа-кабан, 2026-10-19. Один коммит. Факты груминга и аудита сверены по коду HEAD 9149cf7 — верны; аналоги: перенос
хуков листа `apply_hooks` (build.py:46), проверка NPC-триггеров в загрузчике (`trigger_refs`, loader.py:135), правила
листа `means_problems`/`opportunity_problems` (rules/builder.py:577/546).

**Задача:** `HeroPreset` получает `means` и `opportunity`, `build_hero` переносит их в `HeroState`; загрузчик проверяет
пресет по правилам листа (В1, В2); лист главнее пресета (В5); паки наполнены (В3); TZ — `heroes/<id>.yaml` (В6).
Полей сейва нет, живые сейвы не трогаем (В4): пресет читается только в `build_world` нового мира и в `merge.preset_choices`
(только `choices` — не задето).

**Правила (было → станет):**
1. `campaign/build.py:build_hero` — было `hero.motive = preset.motive` → станет `hero.motive = preset.motive;
   hero.means = list(preset.means); hero.opportunity = [t.model_copy(deep=True) for t in preset.opportunity]`
   (копии, как в `apply_hooks`).
2. `campaign/build.py:apply_hooks` (В5) — было безусловно `hero.motive = sheet.motive; hero.means = list(sheet.means);
   hero.opportunity = [...]` → станет каждое присваивание под `if sheet.motive:` / `if sheet.means:` /
   `if sheet.opportunity:` — лист главнее, пустое поле листа оставляет значение пресета.
3. `campaign/loader.py:check_hero` (В1, В2) — новое: `means` — пусто допустимо, иначе `means_problems(preset.means)`
   (1..3, элемент ≤ `MEANS_ITEM_MAX` 120); `opportunity_problems(preset, known, registry)` — ≤ `OPPORTUNITY_MAX` 2,
   id непустые и без повторов, `then` 1..200, ссылки условий (`validate_refs`: npc/location/god/item) по id пака;
   `known = KnownIds(npcs=…, locations=…, pantheon=…)` собирается в loader (импорт `campaign.build.known_ids` нельзя:
   цикл loader → build → uniqueness → loader). Строки ошибок — в стиле файла: `{where}: поле means: …`,
   `{where}: поле opportunity: …`.

**Поведение:** меняется — (а) новый мир из пресета с `means`/`opportunity` получает их в `HeroState` (лист `/sheet`
`hooks_lines`, промпт `means`, триггеры героя в `world_sim.candidates.owners` — срабатывают по-настоящему);
(б) пак с битым пресетом (ссылка, лимит) не загружается — `PackError` со строкой файла; (в) `apply_hooks` с пустым
полем листа больше не затирает значение (В5; затрагивает только `test_apply_hooks_replaces_previous_hooks`).
Герой на лету — как прежде (`resolve_hero_preset` не меняется: пресет `custom` несёт только `motive`, `means`/
`opportunity` пустые, лист заполняет через `apply_hooks`). Промпт (`master/prompt.py:530`), показ (`sheet_text.py:227`),
`world_sim` — без правок.

**Вне репо:** нет.

### Файлы и функции — kaban (src, campaigns, docs)

1. `src/ai_dm/campaign/models.py:HeroPreset` — `means: list[str] = Field(default_factory=list)`,
   `opportunity: list[Trigger] = Field(default_factory=list)` (`Trigger` из `state.triggers`, как у `NPC`); комментарий
   «как у листа героя; проверка — loader.check_hero».
2. `src/ai_dm/campaign/build.py:build_hero` — правило 1, рядом с `hero.motive`.
3. `src/ai_dm/campaign/build.py:apply_hooks` — правило 2.
4. `src/ai_dm/campaign/loader.py:check_hero` — правило 3; импорт `means_problems`, `opportunity_problems` из
   `rules.builder`, `KnownIds` из `rules.triggers_eval`.
5. Паки (В3; тексты пишет kaban по образцу `motive` Грея и `means` NPC vale, проектировщик вычитывает):
   - `campaigns/drunk_dragon/heroes/grey.yaml` — `means` 2–3 (из того, что у него есть: следопыт-егерь, снаряжение
     Брана, ключ ратуши/перстень Ольбрехта — по `inventory_extra`) и 1 `opportunity` (`once: true`, id латиницей;
     условие — `all` со структурной частью, ложной на старте (герой стартует в `iron_ridge_foothills`): `hero_at`
     другой локации пака и/или `npc_status`/`flag`; ссылки только на id `locations.yaml`/`npcs.yaml`/`pantheon.yaml`;
     без чистого `narrative` — иначе кандидат роли `world` на каждой границе).
   - `campaigns/vale/heroes/arn.yaml`, `grey.yaml`, `liel.yaml` — `motive` (1 фраза, ≤ 200) и `means` 1–2; `opportunity`
     не обязательна (0–1, только с ссылками на `innkeeper`/`grakh`/`lame_goose`/`cellar`/`old_crypt`/`vale`).
     Комментарий и `money_cp: 700` у vale/grey сохранить.
6. Доки:
   - `docs/TZ.md:125` — `character.yaml — готовый герой (опционально)` → `heroes/<id>.yaml — пресеты героев
     (опционально)`; `:556` и `:559` — `character.yaml` пака → `heroes/<id>.yaml` пака (В6). Больше в TZ ничего.
   - `docs/ARCHITECTURE.md` D2 (:556–565) — одна фраза: пресет героя несёт `motive`/`means`/`opportunity` как лист героя
     на лету; при загрузке — правила листа (`means` 0..3, `opportunity` ≤ 2, ссылки условий); лист главнее пресета.
     Строка таблицы `campaign.build` (:635) — дописать «пресет пака: `build_hero` переносит те же три поля».
   - `docs/plan-34.md` — «Правки по ревью» / «Итог» по ходу (оркестратор/тесть).

### Файлы — kaban-doeba (tests/**)

- `tests/unit/campaign/test_pack_build.py` — пресет с `means`/`opportunity` (мини-пак `campaign_kit.default_files`,
  `heroes/arn.yaml`); «на лету» (:519, :664) — зелёные без правок; `test_apply_hooks_replaces_previous_hooks` (:677) —
  переписать под В5 (см. сценарии).
- `tests/unit/campaign/test_pack_loader.py` — ошибки загрузки через `check_error(..., "arn.yaml", needle)`.
- `tests/unit/campaign/test_dragon_pack.py` (:274 образец) и `test_vale_pack.py` — паки после наполнения.
- `tests/unit/campaign/test_vale_pack.py:117/122` — регресс: эталон `tests/fixtures/packs/vale_stage2_world.json`
  держит у героя `motive: ""`, `means: []`, `opportunity: []`, `contains` требует равенства → после В3 упадут.
  Исправление в тесте, а не в эталоне: хелпер `stage2_hero(key)` снимает три ключа хуков (как `stage2_locations`
  снимает описание подвала, К7д) — эталон этапа 2 остаётся как есть.
- `tests/unit/world_sim/` (рядом с `test_triggers_check.py`) — один интеграционный: мир из мини-пака с пресетом,
  у которого `opportunity` с условием, истинным на старте (`hero_at: tavern`), → проверка триггеров даёт кандидата/
  срабатывание владельца `("hero", hero, hero)` (`candidates.owners`).

### Тестовые сценарии (TDD)

- Пресет `means: ["а", "б"]`, `opportunity: [{id: o1, if: {hero_at: tavern}, then: "…", once: true}]` →
  `build_world`: `hero.means == ["а", "б"]`, `[t.id for t in hero.opportunity] == ["o1"]`; `hero.means is not
  preset.means`, `hero.opportunity[0] is not preset.opportunity[0]` (копии).
- Пресет без полей → `hero.means == []`, `hero.opportunity == []`; YAML с `means`/`opportunity` проходит
  `extra="forbid"`.
- Загрузчик: `means` из 4 строк → ошибка с `arn.yaml` и «от одного до трёх»; элемент 121 символ → «длиннее 120»;
  `means: []` → пак годен; 3 `opportunity` → «не больше 2»; повтор id → «повторный id»; пустой `then` → «намерение»;
  `hero_at: nowhere` → «неизвестная локация 'nowhere'»; `npc_status` неизвестного NPC, `favor` неизвестного бога,
  `hero_has` неизвестного предмета → по строке; `narrative`/`flag` — ссылок нет, годен.
- `apply_hooks` (В5): лист с полными полями затирает прежние (как :664); лист с `opportunity=[]` → прежние
  `hero.opportunity` остаются, `means`/`motive` из листа; все три пустые → герой не тронут.
- Герой на лету через `build_world(hero_id=HeroSheet)` — `motive`/`means`/`opportunity` из листа (:519 не меняется).
- Паки: `load_pack(drunk_dragon)` — у `grey` `means` непусто и `opportunity` ≤ 2, в мире `heroes[0].means == preset.means`;
  `vale` — у `arn`/`grey`/`liel` `motive` непуст; `test_arn_hero_equals_stage2`/`liel` зелёные с `stage2_hero`.
- world_sim: триггер героя из пресета с условием, истинным на старте, срабатывает (один тест).
- Проверка руками: `uv run ai-dm` → новый мир drunk_dragon, Грей → `/sheet` показывает «Средства: …» и
  «Возможности: <id> — <then>»; `/lore`/промпт без правок.

### mutmut (после `git diff`; TESTS — только эти модули)

`make mutate FUNCS="ai_dm.campaign.build:build_hero ai_dm.campaign.build:apply_hooks ai_dm.campaign.loader:check_hero"
TESTS="tests/unit/campaign"` (все три функции существуют; `HeroPreset` — поля модели, мутировать нечего).

### Риски

- Триггер героя из пака оживает в `world_sim` на старте нового мира — плохое условие даст событие/вызов `world` в
  первую же границу. Страховка: проверка ссылок (В1), условие со структурной частью, ложной на старте, вычитка (В3).
- Эталон vale этапа 2 (`test_vale_pack.py`) — см. регресс выше; без хелпера красный.
- `apply_hooks` после В5 не чистит хуки пустым листом — вызывающие (`build_world` на лету, `hero_create.preview_lines`
  на свежем герое) этого не используют; затронут один юнит-тест.
- Смысловой: `opportunity` героя в промпт рассказчика не идёт (только в `world_sim`) — как у листа на лету, не
  правим.

### Развилки

- В5 реализуется в `apply_hooks` условными присваиваниями (правило 2); альтернатива — передавать все три поля листа в
  пресет `custom` в `resolve_hero_preset` и `apply_hooks` не трогать (конфликта тогда нет по построению). Рекомендую
  правило 2: буквально В5, одно место, пресет «на лету» не раздувается.
- Проверка ссылок через `opportunity_problems(known)` (одна функция листа) против `trigger_refs` + `ref_exists`
  загрузчика (стиль NPC). Рекомендую первое: В1 «по правилам листа» — один набор правил, сообщения те же, что видит
  игрок в мастере листа.

### Оценка

Мини (ROADMAP ≈ 0,2 млн ток.): kaban — 3 функции, 4 YAML, 2 дока; doeba — ~15 тестов, 3 мутируемые функции; ревью
+ аудит обычные, не сокращать. Один коммит: «34: means/opportunity в пресетах героев пака (BACKLOG 34)».

**Открытые вопросы:** нет.

## Правки по ревью
- Мама-кабан п. 2: `check_hero` — ошибки `means` через `errors.append`, как в файле (исправил kaban).
- Мама п. 1 / свекровь: правка `pyproject.toml` `[tool.mutmut]` — временная от `make mutate`, после прогона файл
  вернулся, в диффе её нет.
- Свекровь, В3: факты мира в текстах паков (прежняя служба Арна, бумаги Ольбрехта в сейфе Ратуши, книга Лиэль) —
  проектировщик 2026-10-19: оставить как есть.

## Итог

**Закрыто:** BACKLOG 34; заведён BACKLOG 97 (17 старых выживших мутантов).

**Тесты:** 19109 passed; cov 97,91 %; smells 200/200; dead чист; mutmut — 2 новых мутанта убиты, 17 старых → BACKLOG 97.

**Источник токенов:** `metrics.py ~/.claude/projects/-Users-vladislavahtamov-projects-ai-dm/0a786d43-91fe-432a-8175-e16cea2992d3.jsonl`
(токены = input + cache_read + cache_creation + output); **цены:** https://platform.claude.com/docs/en/about-claude/pricing,
тариф 2026-10-17 из `metrics.py`; fable — по ценам Opus.

| Партия | Смета | Факт |
|---|---|---|
| Шаг 34 (одна партия, мини) | ≈ 0,2 млн ток. | subagent_tokens ≈ 0,50 млн; с кэш-чтением ≈ 4,1 млн; шаг 119 мин |

Расхождение: смета мини не учитывала два круга ревью/аудита и правку kaban после ревью (переделки — 36 % по `metrics.py`);
кэш-чтение в смету не входит.

| Роль | Модель | Токены (subagent_tokens / metrics.py всего) | $ |
|---|---|---|---|
| svinopas | opus-5-5 | 48 795 / 0,40 млн | 0,32 |
| kaban-svekrov (груминг + аудит ×2) | opus-5-5 | 22 535 + 28 217 + 20 502 / 0,29 млн | 0,40 |
| papa-kaban (план; роадмап ≈ 30k, оценка) | fable-5-1 | 90 827 / 0,76 млн | 0,76 |
| kaban (код + правка) | sonnet-5-5 | 56 499 + 58 190 / 1,19 млн | 0,41 |
| kaban-doeba (тесты; мутанты) | sonnet-5-5 | 65 713 + 26 336 / 1,27 млн | 0,38 |
| mama-kaban (ревью ×2) | opus-5-5 | 35 819 + 19 419 / 0,19 млн | 0,30 |
| оркестратор | opus-5-5 | 5,49 млн (на момент подсчёта 08:58 UTC) | 2,09 (на момент подсчёта) |
| kaban-test | opus-5-5 | 0,03 млн (на момент подсчёта) | 0,09 (на момент подсчёта) |

**Итого:** смета ≈ 0,2 млн → факт субагентов ≈ 0,50 млн (subagent_tokens); $ 4,74 по `metrics.py` вместе с оркестратором
(сессия ещё шла — с итоговыми цифрами не сверять).

**Проблемы:** `ruff check src tests` — 18 замечаний, были и на main до шага. Модели kaban и kaban-doeba по `metrics.py` —
sonnet, а не opus, как в сводке оркестратора.

правки: Edit 1 («Итог»), из bash 0.

Разбор — кабан Декарта.
