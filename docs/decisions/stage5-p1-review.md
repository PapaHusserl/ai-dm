# Ревью P1 этапа 5 (мама-кабан, 2026-10-05)

Проверено: незакоммиченные `ui/cli.py`, `ui/tui/__init__.py`, `pyproject.toml`/`uv.lock`, `Makefile`, `devtools/check_install.py`,
`tests/unit/test_architecture.py`, `tests/unit/ui/test_ui_cli_mode.py`; сверка с STAGE5-PLAN (P1, часть F, ответы проектировщика),
stage5-grooming. `pytest tests/unit/ui tests/unit/test_architecture.py` — 410 passed; `ruff` чисто; `vulture` — только старые находки.
Старые тесты cli не правились (`git diff` по `tests/` — только `test_architecture.py`, добавление).

## Хорошо
- `choose_mode` — чистая функция, все ветки покрыты (флаг, подмена ввода/вывода, не-tty по каждому потоку, `TERM=dumb`, без `TERM`).
- Строки старта: в TUI копятся в `CaptureOutput` и уходят в ленту; при раннем отказе и при fallback печатаются один раз;
  в простом режиме `notes is stdout` — вывод байт-в-байт прежний. Тесты на «нет в stdout при TUI» и «есть после fallback» есть.
- Fallback: одна строка, через `redact`, без трейсбека; тест на утечку ключа есть. Порядок: сообщение, потом строки старта, потом игра.
- `textual` лениво (импорт внутри `run_tui`), два AST-сторожа; worker `thread=True, exclusive=True`, результат через `call_from_thread`,
  поле ввода блокируется на время хода.
- Pilot-тесты через `asyncio.run`, фиксированный размер, без сна. `devtools/check_install.py` + `make install-check` — как в ответе Q8.

## Отступления от плана
- HeroPicker отложен (Т-4): допустимо, в TUI-режиме выбор героя идёт старым `ask_hero` в терминале до запуска App. Записать перенос в план.
- Ctrl+C / русские BINDINGS — на P2/P3 по плану; допустимо, но см. блокер 1: заглушка сразу становится режимом по умолчанию.

## Блокеры
1. **Нет автосейва при выходе не через /quit** — `ui/tui/__init__.py`. `PlaySession.finish()` в TUI не вызывается никогда; встроенный
   выход Textual (Ctrl+Q) закрывает игру без сохранения auto. После мержа P1 любой запуск из терминала идёт в TUI-заглушку — это
   регресс против простого режима (там EOF/Ctrl+D → `finish`). Минимально: в `run_tui` после `app.run()`, если выход был не по
   `step.quit`, вызвать `session.finish()` (App уже закрыт, worker завершён — гонки нет) и вернуть его `exit_code`. Тест: Pilot жмёт
   выход-клавишу → слот auto есть. Полное поведение Ctrl+C во время хода (Q10) — в P3, как в плане.
2. **Слишком широкий перехват для fallback** — `cli.play`. `except Exception` + `isinstance(error, ImportError)` + сравнение
   `type(error).__name__ == "TuiStartError"` по строке. `ImportError`, вылетевший уже из работающей TUI (после первого кадра, например
   из хода), уйдёт в fallback, и `run(...)` запустит игру заново в простом режиме поверх сыгранной — дубли старта/повторный opening.
   Предложение (проще и точнее): в `cli.run_tui` разделить шаги —
   `try: from ai_dm.ui import tui` / `except ImportError as error: return None, error`, затем `except tui.TuiStartError` вокруг
   `tui.run_tui(...)`; в `play` ловить только эти два случая. Тогда и сравнение имени класса строкой не нужно.

## Желательно
3. **vulture `ignore_names`** (`pyproject.toml`): добавлены `ENABLE_COMMAND_PALETTE`, `compose`, `on_mount`, `on_input_submitted`,
   `disabled` — это расширение allowlist без согласия пользователя (правило в шапке `vulture_allowlist.py`). Хуже того, `ignore_names`
   глобален: `compose`/`disabled` будут скрыты во всём `src`, а не только в TUI. Альтернативы (любая — с согласия пользователя):
   (а) строки в `vulture_allowlist.py` с комментарием «API Textual, вызывается фреймворком» — как уже сделано для полей pydantic,
   видно и узко; (б) один раз согласовать шаблоны `on_*`, `action_*`, `compose`, `BINDINGS`, `CSS*` — в P2/P3 их станет много.
   Без согласия — откатить и вынести вопрос пользователю, P1 при этом vulture не пройдёт (`make quality`), значит согласие нужно до мержа.
4. **`pytest-asyncio` не используется** — тесты идут через `asyncio.run`. Лишняя dev-зависимость; убрать из `pyproject.toml`/`uv.lock`.
5. **Ctrl+C во время подготовки в TUI-режиме** — `cli.main` ловит `KeyboardInterrupt` и пишет «Прервано.», но накопленные в
   `CaptureOutput` строки старта теряются (например, предупреждения `pick_narrator`). Мелочь; можно печатать `notes` при прерывании
   или оставить до HeroPicker (P3) — записать.
6. **Порядок вывода при `ask_hero` в TUI-режиме** — подсказка выбора героя печатается в терминал, а строки, накопленные до неё
   (выбор рассказчика), появятся позже, в ленте. Уйдёт с HeroPicker; записать как известное до P3.
7. **Исключение вне `try` в `PlaySession.submit`** (`reply_blocks`/`screen_blocks`) в worker-потоке роняет App с трейсбеком Textual и без
   автосейва. В простом режиме то же падение, так что не регресс; закрывается вместе с п.1, если `finish` вызывать после любого выхода.

## Вердикт
Нужны правки: блокеры 1–2 и решение пользователя по п.3 до мержа; 4 — попутно; 5–7 — в бэклог/план P3.
