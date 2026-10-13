# Ревью партии Р2 «Темп и отказы» (мама-кабан, 2026-10-13)

Вписано оркестратором (у ревьюера нет Write). План docs/R2-PLAN.md, груминг docs/decisions/r2-grooming.md.
Тесты: 14068 passed, 1 xfailed, 1 failed (ожидаемый `test_game_refusal_retry_calls.py`).

## Сделано по плану
- Повтор хода (`turn.py: run/attempt/retry_result`): новая глубокая копия бандла на попытку, броски из копии
  (`Rng.from_state`), `self.note` сбрасывается в `finally`; `time_before_s` снимается до первой попытки.
- Q1а: `with_note` — второй `Text` в `messages[0].content`; при `note=None` запрос прежний.
- Q2а: бэкап не строится, если summarizer = рассказчик.
- Summarizer: к запасному только `refusal`/`invalid`; `failed_role` — только при жёстком сбое; `concat` без
  обновления `game_summary`.
- Replay: `summarizer_backup` в `play_report` и на старте с `--replay`.
- Новые тесты не пустые (83 в новых файлах).

## Замечания
1. **(блокер)** `turn.py: new_session` не передаёт `call_numbers` → обе попытки пишут один `call_id`; план п. 2.5 —
   сквозная нумерация. Передать `call_numbers=self.call_numbers`, проверив, что нумерация обычных ходов не сдвинется;
   иначе — отдельный словарь на ход в `run`.
2. `turn.py: attempt` — лишний `except TurnFailed: raise`, удалить.
3. Порядок тегов при двойном отказе `["refusal_retry","refusal"]` — допустимо по плану; тест фиксирует порядок,
   формулировку TZ:605 привести в соответствие.
4. `summarizer.py: try_scene` — `summary_text is not None` пропускает `""`; глава — `bool(...)`. Согласовать
   (`bool`) и добавить тест на пустой текст.
5. `SOFTEN_NOTE` длиннее плана п. 2.2 — это решение проектировщика Q4б, правка не нужна; тесты — по константе.
6. `turn.py: new_summarizer_session` — путающий комментарий про Q2, переписать.
7. Тег `refusal_fallback` ставится и при `invalid` (по В11а/В14а) — отметить в TZ.
8. WINDOW мока 24000→24500 (пятый подъём, блок «Темп») — дописать в BACKLOG 45.

Исход (kaban): 1 ✅ (`call_numbers` в `new_session`, `pop` в `mark_journal`); 2 — **отклонено**: `TurnFailed` — подкласс
`Exception`, без ветки первая попытка ловится `except Exception` и ход помечается `aborted` до повтора (падали тесты
журнала); 3, 7 ✅ TZ; 4 ✅ `bool(...)`; 6 ✅; 8 ✅ BACKLOG 45.

Вердикт: обязательно 1, 2; желательно 4, 6; остальное — документы.
Расход ~37 тыс.
