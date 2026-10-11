# Партия Б «Сюжетные предметы: показ и мастер» — ревью и решения (2026-10-07)

## Сделано
- /inv: группа «Сюжетное» первой; у предметов мира — описание и «(вес, цена)» (вес 0 и цена 0 не показываются).
- Item.weight_centilb (вес кастомного через overlay реестра; ключ кэша overlay учитывает вес).
- Контекст мастера: name у всех предметов inventory, у кастомных description (≤120) и quest; item_ids без custom_*;
  `lost_items` (только квестовые с держателем, ≤5 свежих) и `last_combat` {gear, gear_looted:false} — только непустые
  (master/prompt.py::items_trail_data, вынесено ради make smells).
- narrator_rules: раздел «Сюжетные предметы» (give_custom_item, след по lost_items, обыск тел).
- «Получено»: TUI — без правок (app.registry строит overlay); simple — предмет строкой ленты.

## Ревью мамы-кабана
Блокеров нет. Исправлено: вес 0; пустые lost_items/last_combat не уходят в контекст. Мелочи: обрезка описания без
многоточия — оставлено. Отклонения разработчика (weight_centilb, name у всех, quest=False, «×N» в gear, LOST_ITEMS_MAX=5
есть в плане) — приняты.

## Проверки
pytest 9017 passed, 1 xfail; cov 96.05%; ruff чисто; smells 210; мутации новых функций — 0 выживших
(inv_lines__mutmut_33 эквивалентный). Старые выжившие master.prompt (state_data секреты/nudge/recent_turns,
divine_data, sheet_data, combat_data, memory_block и др.) — BACKLOG 16.

## Решения проектировщика (2026-10-07, «по рекомендациям»)
1. vulture_allowlist: убраны gear_looted, since_s, weight_centilb (поля читаются).
2. memory_script.py WINDOW 20000→20500 — принято; пересмотреть в партии В.
3. simple: «Получено: …» с предметами (ui/simple.py::gains_lines_text). Дубль строки лога и «Получено: Опыт» —
   «не горит», BACKLOG 16.
4. Некве́стовые кастомные у держателя в контекст не идут (В10) — оставить.

Итог после правок: pytest 9022 passed, 1 xfail; ruff чисто; smells 210 (плавает 210–213).

## Расход
kaban ~95+5+4 тыс. ток. (~23 мин); kaban-doeba ~136+10+4 тыс. (~78 мин); mama-kaban ~23 тыс.
