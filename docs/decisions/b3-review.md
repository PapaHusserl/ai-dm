# Ревью партии Б3 — import пака (2026-10-10)

План: docs/B3-PLAN.md (Q1–Q12 «а»). Код — kaban, тесты — kaban-doeba, ревью — mama-kaban (два прохода, блокеров нет).

## Правки по ревью (внесены)
- `calls_cost_line` → `game/commands.py` (hero_create не тянет import).
- `--campaign` только `[a-z0-9_-]+` (`CAMPAIGN_ID_RE`), иначе код 2 (защита от `/`, `..`).
- `RolesConfig.import_` необязателен, `pick_import` откатывается на `roles.import_` (риск 8 плана).
- `ALWAYS_FILES`, `ImportTask.mode = IMPORT_MODE`, `pack_report_lines(files)`.
- Промпт: оси тона «из tone_axes или none»; `species_id` пусто, если вида нет; справочник осей через `tone_axis`.

## Отступления от плана (приняты оркестратором)
- `PackTone` вместо `Tone` как есть (в strict-enum нет `""`, вместо него `none`).
- `import_refusal` — только флаги; `import_text` — id занят/чтение/размер; `import_pack` → `import_pack/import_run/import_dialog` (лимит smells).
- Битая ссылка и конфликт 5.3 не приходят одним отказом (`check_pack_dir` до 5.3 не доходит при ошибках загрузчика).
- П. 30: фикстура v2 (m0003 ставит campaign_id только v2).

## Инцидент
Тест kaban-doeba «живой import без ключа» без `dotenv_path` подхватил реальный `.env` и дважды вызвал gemini (выжимка ~300 симв., центы). Исправлено: такие тесты указывают `dotenv_path` на несуществующий файл. Финальный прогон оркестратора — с убранным `.env` и без ключей в окружении: 11963 passed.

## Итог
Тесты 11963 passed, 1 xfail; cov 96,78%; smells 204/205; dead чист; ruff: 5 длинных строк в старых файлах (не Б3).
mutmut: новые строки добиты; эквиваленты (utf-8/UTF-8, months 30 дней и т.п.) и ветки `import_pack`, не пробиваемые без живого API, оставлены. Старые выжившие (`load_pack` 32, `apply`, `tool_defs`) → BACKLOG 16.
Дальше — живой прогон пользователя (B3-PLAN, В10а) → docs/decisions/b3-live.md.
