# Ревью Б1б

## Решения проектировщика
1. Кодовые имена пресетов мира (2026-10-08): поле `codename` в presets.yaml (heroic — «Властелин колец», grim — «Ведьмак»,
   romantic — «Сумерки», fairytale — «Хроники Нарнии»); показывается только в меню пресета
   «<name> (в духе «<codename>») — <description>»; в tone/промпт рассказчика не передаётся.
2. В-5: смена модели в меню 2.2 при создании героя может выбрать другого провайдера; смешение с world/summarizer
   допустимо (нужно для Q12: grim на Gemini → Claude при refusal). Запись в models.json — BACKLOG 16.
3. В-3: строки HeroSession остаются в ui/hero_session.py (без textual); проверка «русские строки» — отдельным тестом.

## Отступления kaban от плана (приняты ревью)
choose_hero → id | NEW_HERO | None (создание в prepare); choose_number с кортежем menu (smells); строки HeroSession
в ui/hero_session.py; расход создания в app.ledger.session_lines; «Как в паке»/Esc → preset=None без заметки;
текст отказа --replay дополнен.

## Замечания мамы-кабана → правки
1. (блокер) pyproject.toml `[tool.mutmut]` выборка тестов сужена — вернуть `["tests/"]`.
2. Пустой `--hero-describe` → отказ в hero_flag_refusal (код 2).
3. discard_world — только в ветке нового мира.
4. Не мутировать args.preset в prepare (локальная переменная).
5. HeroCreateApp: исключения сессии кроме TurnFailed — как в AiDmApp.
6. Мелочи: явное состояние model_choice; «поля» одним блоком raw.

## Итог правок kaban
Правки 2–6 внесены; smells 202/202. П.5: HeroSession ловит только TurnFailed, прочие исключения роняют HeroCreateApp
(в игре их ловит PlaySession) — оставлено как есть; защита в HeroSession.submit — кандидат в BACKLOG 16.

## Тесты и mutmut (kaban-doeba)
mutmut по функциям Б1б: 1058 мутантов, 53 выживших → 16 (все эквивалентны/недостижимы, разбор в отчёте doeba:
model_dump mode, ключи меню при 3 пунктах, remark≈None, partition/rpartition, known= при narrative-правке, регистр SLOTS).
Старые выжившие → BACKLOG 16: cli.make_game_adapter mutmut_15, cli.prepare mutmut_568 (opening только без --mock).
Расхождения с планом: `previous` в SheetTask — вложенная форма model_dump(by_alias), а не плоская HeroSheetRequest (A3);
ветка «пак без пресетов героя» (В14) недостижима через loader (требует ≥1 пресет) — покрыта юнитом на заглушке.
