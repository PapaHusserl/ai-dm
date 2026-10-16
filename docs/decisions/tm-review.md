**Ревью: партия #20 ТМ «Повторы механики» (TM-PLAN, v10, кулдаун 12h)**

✅ План пунктов 1–9 выполнен полностью: gold_explicit/gold_repeated, rest_redundant + long_rest_end_s, outcomes/money_delta_cp в commit и fold_fight, turn_data, правило в narrator_rules, конфиг с валидатором Duration, чистая миграция m0010 (deepcopy, setdefault), MIGRATIONS[9]. Стиль соседний (rejected + report_tag, как у других защит). Сравнение идёт после капа. money_delta в commit считается от self.bundle (снимок до хода, work — deep copy, turn.py:226) — верно, trade и hoard тоже попадают в дельту. Сумма в fold_fight корректна. Тесты test_gold_repeat, test_rest_repeat и test_stage4_memory проходят (91 passed), WINDOW=25500 поднимать не нужно.

Замечания по важности:

⚠️ 1 (низкая, ложное срабатывание по плану) — resources.py gold_repeated: сравнивается чистая дельта хода, а не начисление золота. Продажа через trade на ту же сумму в последних 3 ходах — следующее законное explicit gain отклоняется. Обратный случай: золото и покупка в одном ходу — дельта не совпадёт, и повтор пройдёт. Риск записан в плане §7, правка не нужна; в checklist-tm-live.md стоит добавить шаг «продажа → награда той же суммы».

⚠️ 2 (низкая) — resources.py rest, порядок проверок `(swap_invalid, prey_invalid, rest_redundant)`: повторный отдых с ошибочным prepared_swap или prey_swap получает Invalid (сжигает бюджет 2 невалидных за ход) вместо мягкого rejected rest_repeat. Если поставить rest_redundant первым, ошибка не тратит бюджет, а swap'ы и так не применяются. Порядок соответствует плану («перед try»), так что это на выбор оркестратора. Пропуск при 0 HP — известное отступление, сделано верно.

⚠️ 3 (косметика) — E501 в новых тестах: test_tm_fold.py:1, test_tm_turn_memory.py:31, test_tm_prompt.py:2,21,22,85, test_migration_v10.py:5, test_gold_repeat.py:2,5,6, test_rest_repeat.py:4,5, test_master_rules.py:281+ (новый тест). В репо уже есть старые E501, и `make lint`, судя по всему, их не валит, но по правилу «новый код не добавляет долг» предлагаю перенести строки (это 13 комментариев/строк, правка дешёвая).

⚠️ 4 (инфо) — resources.py rest_redundant: `Duration.parse(cfg.limits.long_rest_cooldown)` разбирается на каждый вызов. Так же сделан servant_cooldown, так что это нормально, не трогать.

⚠️ 5 (инфо) — fingerprint: turn_data меняет все запросы, старые `--replay-report` расходятся (по плану). Не забыть записать это в handoff вместе с ARCHITECTURE C3/E7.

**Вердикт:** можно мержить; п.3 желательно поправить, п.2 на выбор оркестратора.

## Аудит (kaban-svekrov, 2026-10-16)

**Что проверено:** `git diff` (src/, tests/, docs/ARCHITECTURE.md, ROADMAP.md, BACKLOG.md) и новые файлы
партии из `git status` (m0010, фикстура v9, save_v10.schema.json, тесты tm/gold_repeat/rest_repeat/migration_v10).
checklist*.md не смотрел.

**Источники истины:** docs/TM-PLAN.md (утверждён: Q1а v10, Q2б 12h, Q3а, Q4а), ревью выше.

| Находка | Где | Откуда взялось | Вердикт |
|---|---|---|---|
| gold → диспетчер + gold_explicit, gold_repeated (окно, 0 = выкл., сравнение после капа), rejected `gold_repeat` | handlers/resources.py | план §1 п.1, п.9 | оставить |
| rest_redundant, `long_rest_end_s`, rejected `rest_repeat`, кулдаун 12h | resources.py, rests.py, hero.py | план §1 п.2, Q2б | оставить |
| Пропуск rest_redundant при 0 HP | resources.py rest_redundant | план §4: «0 HP → прежний Invalid» — без пропуска тест плана не выполним; это реализация плана, а не новое решение | оставить |
| `outcomes`/`money_delta_cp`, recording, commit, fold_fight | state/scene.py, game/turn.py, combat_fold.py | план §1 п.3 | оставить |
| turn_data (5 ключей), правило в narrator_rules (текст дословно по плану) | master/prompt.py, narrator_rules.md | план §1 п.4–5 | оставить |
| `[limits]` gold_repeat_turns=3, long_rest_cooldown="12h", валидатор | defaults.toml, settings.py | план §1 п.6 | оставить |
| Сейв v10, миграция, MIGRATIONS[9], фикстура v9, схема | migrations/, tests/ | план §1 п.7, Q1а | оставить |
| Правка test_migration_v9 (`== 9` → `>= 9`, `current_version=9`) и прочих сейв-тестов под v10 | tests/unit/persistence/* | следствие Q1а; смысл старых проверок сохранён | оставить |
| ARCHITECTURE: раздел назван E10, а не «E7» из плана | ARCHITECTURE.md | нумерация по версии сейва (как E9 = v9); смысл тот же | оставить |
| ROADMAP: версии Ж0/М0/С0 сдвинуты +1 | ROADMAP.md | прямое следствие Q1а (v10 занята) | оставить (механика, не выбор) |
| ROADMAP: «#20 ✅ … закоммичена 2026-10-16», BACKLOG T6 ✅ — до коммита и до ЖП по checklist-tm-live | ROADMAP.md, BACKLOG.md | ниоткуда (статус опережает факт) | к пользователю: закрывать ли #20/T6 до живого прогона на flash-lite, или «✅ код, ЖП ждёт» |
| ROADMAP: оценка 0,6 вместо 0,4 | ROADMAP.md | факт расхода | оставить |

Лишних абстракций, фич, контента и изменений вне области не найдено. Мутанты (со слов оркестратора): 4 выживших —
текст и 2 эквивалентных; это допуск плана §5 — не перепроверял.

**Решения за пользователя:** п.2 ревью (порядок проверок в rest) — вынесен проектировщику, верно. Отметка ✅ #20/T6
в ROADMAP/BACKLOG до живого прогона — решение оркестратора о закрытии партии; критерии §5 ЖП не требуют, но Ф3/T6
подтверждаются только на flash-lite — пусть решит проектировщик. Других нет.

**Итог:** чисто по коду; нужно одно решение пользователя (статус ✅ до ЖП) и ответ по п.2 ревью.

## Решения проектировщика (2026-10-16)
1. П.2 ревью: `rest_redundant` — первой проверкой в `rest` (повтор с ошибочным swap → мягкий отказ `rest_repeat`,
   бюджет невалидных не тратится; после кулдауна плохой swap — по-прежнему Invalid). Внёс оркестратор, тесты обновлены.
2. Статус: ✅ при коммите, как 19ф/ТВ; ЖП на flash-lite — по docs/checklist-tm-live.md, находки — фиксом.
3. П.3 ревью (E501 в новых тестах) — поправлено оркестратором.
