# Ревью: этап 6а, партия P2 (`--replay-report`, критерий ТЗ 13)

Проверено: незакоммиченный diff (reports/replay.py — новый, reports/writer.py, ui/cli.py, README.md,
docs/ARCHITECTURE.md) и тесты tests/scenarios/test_stage6a_done.py, tests/unit/reports/test_replay_*.py,
test_writer_replayable.py. `uv run pytest tests/scenarios/test_stage6a_done.py tests/unit/reports`: 164 passed.

## Хорошо
- План P2 закрыт по пунктам: `load_report` грузит `before`/`after` через копию во временную папку (живой `saves/`
  не трогается, тест побайтно), `compare` с исключениями в одном месте (`TIME_FIELDS`), флаги-конфликты → код 2,
  `replayable=false`/пустой репорт → код 2, `ReplayDivergence` и расхождение состояния → код 1.
- Оба замечания P1 закрыты: пропавший блоб → `replayable=false` (`write_journal` возвращает `complete`),
  `manifest.saved_at` исключён из сравнения (тест `test_saved_at_of_snapshots_does_not_matter`).
- Критерий покрыт сценариями: исследование, авто-метка, бой с моделью и без, несколько ходов боя, откат
  (тот же `failure.reason`, состояние == before), граница сцены world+summarizer, retry границы, ход после
  транзиентной ошибки; порча ответа / удаление записи / отпечаток / RNG / after.
- Модели запроса — из журнала (`journal_role_model`), `auto_reports=False`, `use_stored_model=False`, сон отключён.
- Код плоский, функции короткие, стиль соседний (`role_replay` повторяет логику нынешнего `--replay`).

## Замечания
- Не обновлён HANDOFF (план P2 п.4: README, ARCHITECTURE, HANDOFF). README и ARCHITECTURE есть, HANDOFF в diff
  нет. Предложение: дописать статус 6а P2 и как воспроизводить репорт. **Нужно до мержа.**
- Риск D.5 не учтён: при `ReplayDivergence` сообщение «Расхождение с журналом: …» без версии формата
  репорта/схемы сейва. Предложение: в `play_report` к сообщению добавить `report_format` из meta и версию схемы
  снимка `before` (одна строка), чтобы репорт после будущей v8 объяснял себя.
- ui/cli.py `play_report`: путь достройки границы через `app.pending = "error_menu"; app.choose("retry")` —
  прямая запись внутреннего состояния GameApp. Работает (тесты 234/255 проходят), но завязано на имя состояния
  меню. Предложение: оставить, но комментарием указать, почему так (у хода без фразы — только retry-путь), или
  если в GameApp есть публичный способ войти в retry — использовать его.
- Выживший мутант `ReplayAdapter(records, role=None)` для narrator: в текущих сценариях записи narrator идут
  раньше world/summarizer, поэтому адаптер без фильтра роли не отличим. Предложение: в
  `test_replay_wiring_fixed_now_...` (шпион уже есть) проверить `role == "narrator"` у адаптера рассказчика —
  дёшево и убивает мутант.
- `campaign_registry`/`pack_npc_trade` с None на дефолтном паке не отличимы — принимаемо; убивать только если
  появится второй пак в фикстурах. Не блокер.
- `now=lambda: now` ни на что не влияет в тестах (отпечаток не зависит от `run_id`/stamp — это проверено
  сценариями). Оставить по плану (D.1: защищает от недетерминизма в `saved_at` новых сейвов и stamp), но
  добавить комментарий «отпечаток от времени не зависит; now фиксируем для stamp/saved_at». Не блокер.
- `replay_report`: реестр достаётся через побочный эффект `registries.append` в замыкании и `registries[0]`.
  Просто, но неочевидно. Можно оставить; если будет правка рядом — возвращать реестр из `load_report` вместе с
  `before`. Не блокер.
- Регистр имён файлов отчёта на macOS (case-insensitive ФС) не проверяется — на Linux CI поймается. Не блокер.
- `make cov`/`make smells` (≤ 210, запаса нет)/`make dead`/`make mutate` для reports/replay.py в этом ревью не
  перезапускались — разработчику приложить цифры к коммиту.

## Вердикт
Нужны правки: HANDOFF (обязательно); остальное — рекомендации (версия формата в сообщении о расхождении,
проверка role у адаптера рассказчика, комментарии к retry-пути и `now`). После HANDOFF и подтверждения
`make smells`/`cov` — можно мержить.

## Итог оркестратора (2026-10-08)
- Правки: версия формата/схемы в сообщении ReplayDivergence, комментарии у retry-пути и now; тест role="narrator"; HANDOFF обновлён.
- Полный pytest (make cov): 10193 passed, 1 xfailed; покрытие 96.36%; ruff чист; make smells 210; make dead — новых находок в reports/cli нет.
- Оставлено: registries.append/[0]; мутанты campaign_registry/pack_npc_trade с None (нужен мир с другим паком); регистр имён файлов — проверится на Linux.
