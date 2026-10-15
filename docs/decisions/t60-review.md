# Ревью Т60 «Сеть» (мама-кабан, 2026-10-15)

Проверено: `git diff` по src/ и pyproject.toml, новый `src/ai_dm/game/models.py`, сверка с docs/T60-PLAN.md (с учётом раздела 10). tests/** не ревьюились.

## Хорошо
- Авто-переключения нет, у MasterSession нет `chain_next`/`fast_policy` — по разделу 10.
- `chain_delays` применяется только к primary summarizer при наличии backup (turn.py `new_summarizer_session`); backup идёт с полной политикой.
- `narrator_chain` валидируется (формат ключа, цена, окно) в AppConfig.
- Вынос models.json/check_model/model_options в `game/models.py` — чисто, поведение то же.

## Обязательные правки
1. **Порядок по цепочке не доходит до TUI и /model.** `GameApp.model_options()` (app.py:166) зовёт `model_options(self.settings.app)` без `current`. Им пользуются `ui/tui/app.py:454` (ModelModal — основной путь выбора модели в TUI после меню ошибки) и `game/commands.py:80`. Значит в TUI первой в списке НЕ будет `next_in_chain` — главная цель п. narrator_chain из раздела 10 не выполнена. Предложение: `GameApp.model_options()` возвращает `model_options(self.settings.app, self.current_key())` и `menu_for` зовёт его же (убрать дубль).

## Желательные правки
2. `ui/hero_session.py:4` импортирует `check_model, model_options` из `ai_dm.game.app` — работает только как побочный реимпорт. Импортировать из `ai_dm.game.models`.
3. `switch_role == "both"`: `set_narrator(key)` и `set_summarizer(key)` создают два разных адаптера одной модели; в `new_summarizer_session` проверка `adapter is not self.adapter` истинна, и создаётся бесполезный backup на той же модели (primary с `chain_delays=[]` → одна попытка, затем backup с полными повторами). По сути работает, но лучше в ветке both после `set_narrator` ставить `self.runner.summarizer_adapter = self.runner.adapter` (или сравнивать в turn.py по `info()` provider+model, а не по identity).
4. `gemini_adapter.py`: при `gemini_ipv4=true` свой `httpx.HTTPTransport` теряет SSL-контекст genai (SSL_CERT_FILE) — в комментарии toml это сказано, ок; но `async_client_args` не задан — если где-то используется async-клиент genai, IPv4 на него не распространится. Проверить, что async не используется, либо дописать комментарий.
5. `GameApp.failed_reason` выставляется в `after_turn` до проверки committed — ок, но не сбрасывается при загрузке сейва/новом ходе вне after_turn; убедиться, что `choose_error` недостижим без свежего after_turn (сейчас похоже так).

## Оценка заявленных отклонений
- `Journal.note_start(*fields)` позиционно — приемлемо: порядок полей задокументирован в комментарии, вызов один (MasterSession.note_start). Минус — нет проверки числа полей; не критично.
- `menu_for` словарём — ок, поведение то же (None для прочих). Небольшой минус: списки создаются на каждый вызов, неважно.
- Удаление `GameApp.models_path`/`read_models` — ок, внешних вызовов в src нет (проверить, что тесты doeba не на них).
- Политика summarizer в `new_summarizer_session` без `fast_policy` — соответствует разделу 10, ок. `MasterSession(policy=...)` с `policy or app_cfg.retry` — ок.
- `both` только если failed_role не summarizer — разумно: если упал именно summarizer на границе, менять рассказчика незачем. Соответствует п.7 плана по смыслу.

## Вопросы проектировщику
- В ветке `both` при сбое сети модель рассказчика пишется в models.json, а summarizer — только на сессию. Это ожидаемо?
- `SOFT_REASONS` теперь включает `network` — сетевой сбой summarizer при наличии backup больше не валит ход (уходит в backup/запасную выжимку). Подтвердить, что так задумано (план Q-решения, вероятно, да).

**Вердикт:** нужны правки (п.1 обязательно).

## Решения проектировщика (2026-10-15)
- Правка 1: порядок `narrator_chain` везде. `GameApp.model_options()` передаёт `current=self.current_key()`, `menu_for` зовёт этот же метод, так что `/model` и TUI-пикер тоже начинают со следующей по цепочке модели.
- Summarizer в ветке `both` меняется только на сессию, `models.json` не трогаем (как сейчас).
- `network` в `SOFT_REASONS` подтверждён планом (раздел 10).

## Сделано по правкам 2-5
- 2: `ui/hero_session.py` импортирует `check_model`, `model_options` из `ai_dm.game.models`.
- 3: в ветке `both` после `set_narrator` и `set_summarizer` стоит `runner.summarizer_adapter = runner.adapter`: лишний backup на той же модели не создаётся.
- 4: async-клиент genai в `src/ai_dm/llm` не используется; комментарий в `GeminiAdapter.get_client`.
- 5: меню ошибки достижимо без `after_turn` только через `load()` (недостроенная граница); `GameApp.load` сбрасывает `failed_reason`.
- 1: сделана (см. выше).

## Раунд 2 (мама-кабан, 2026-10-15)
Проверен текущий `git diff` src/.
- 1: ок. `GameApp.model_options()` передаёт `current_key()`, `menu_for` (model_choice) вызывает этот метод, TUI-пикер и `/model` получают тот же порядок.
- 2: ок, `hero_session` импортирует из `game.models`.
- 3: ок. В ветке `both` `summarizer_adapter = runner.adapter` ставится только при `error is None`. `summarizer_model` уже выставлен в `set_summarizer` и совпадает с моделью рассказчика, поэтому `new_summarizer_session` не создаёт backup.
- 4: ок, комментарий есть.
- 5: ок, `load()` сбрасывает `failed_reason`.

Мелочь (желательно, не блокирует): после `choose_model` поле `switch_role` не возвращается в `"narrator"`. Если после сбоя summarizer игрок откроет `/model` или TUI-пикер вне меню ошибки, `current_key()` возьмёт ключ summarizer, и порядок в списке будет от него. На поведение (какую роль меняет `/model`) это не влияет. Можно сбрасывать `switch_role = "narrator"` в конце `choose_model`.

**Вердикт раунда 2:** можно мержить.
