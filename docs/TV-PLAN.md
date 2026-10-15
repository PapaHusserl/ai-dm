# План мини-партии #18 «ТВ Текст и выбор» (T3 + T5 + живая проверка T4; BACKLOG 64)

Автор: papa-kaban, 2026-10-15. Статус: **утверждён 2026-10-15** («окей, кабаним»); Q1–Q3 — (а), (а), (а), как рекомендовал papa.
Груминга нет (R6 §10 п.2а: техдолг по правилу фикса). Сейв v9 без изменений. Оценка ≈ 0,3–0,37 млн (роадмап 0,45).
Smells 200/200 — нулевой баланс. Источники: roadmap-r6-proposal.md «ТВ», §6 (критерии), §8 (разбор списка «- …» без
модели — не делаем); tech-debt-2026-10-14.md T3/T5/п.2; BACKLOG 64; B59-PLAN.md, b59-review.md; HANDOFF 17а (багфикс —
сначала офлайн-реплей гипотезы).

## 0. Офлайн-проверка гипотез (сделано, без сети; saves/ только чтение)
**T3 — подтверждён** (dusk_academy t436, `issues/20261014T173713-t436-short_retry/journal/calls.jsonl`, 5 вызовов):
- вызов 1: текст сцены **1555 симв.** + `give_custom_item` (`bad_description`, описание >200) + `offer_choices` (accepted);
- вызов 2: только исправленный `give_custom_item` (accepted), текста нет;
- вызов 3: текст 64 симв. «Письмо теперь у тебя…» → `narration` = 64 < 80 → `check_told` → `short_retry`;
- вызовы 4–5: повтор хода целиком: `skill_check` perception (**новый бросок**, d20=13) + `give_custom_item` + сцена 1383 симв.
  + `offer_choices`. Цена хода ×2, сцена другая.
- Код: `master/session.py:335 if not has_invalid: result.texts += texts` — текст раунда с invalid выброшен. С сохранением
  текста `narration` = 1555 + 64 → повтора нет, 3 вызова вместо 5.
- По всем журналам saves/ (не .bak): раундов «текст + invalid» в explore всего **2** (оба sonnet, dusk, run-…-17 и -37);
  в обоих следующий ответ — только исправленный вызов, **без текста** → дублей сцены при сохранении текста не ожидается.
  У Gemini таких раундов нет (пишет текст после результатов).

**T5 — подтверждён** (drunk_dragon-00000001 `journal/calls-004.jsonl`, run-20261014T183915-2c23c8-1…4, flash-lite):
- ход 130 (-1-3): «Выбери дальнейшее действие:» + 3 строки «- …»; ход 131 (-2-3): последняя строка — вопрос
  «Осмотреть замок и повернуть ключ в решётчатой двери?»; ход 132 (-3-2): список «- …»; ход 133 (-4-2): **три строки
  вариантов без маркеров** (голые строки, без точек). `offer_choices` — ни в одном из 4 ходов. Разделителя «|» в корпусе нет.
- Статистика по всем explore-ходам рассказчика (первое сообщение `combat: null`, без ошибок):

  | модель | ходов | с offer_choices | без, эвристика сработала | без, не сработала |
  |---|---|---|---|---|
  | gemini-3.8-flash | 671 | 646 | 6 — **все 6 ходы со `start_combat`** («Твой ход — как ты атакуешь?») | 19 |
  | claude-sonnet-5-5 | 94 | 91 | 0 | 3 |
  | gemini-3.5-flash-lite | 4 | 0 | **4** (2 списка, 1 вопрос, 1 голые строки) | 0 |

  Среди 737 ходов с `offer_choices` эвристика «список/голые строки» не срабатывает ни разу; «вопрос» — 181 раз, но при
  вызванном `offer_choices` приписка не нужна. Вывод: ложных срабатываний нет при одном условии — **не проверять, если в
  этом ходу начался бой** (`active_combat` не None: варианты даёт движок, правило стр. 108 это и говорит).
- Побочная находка: правила (`narrator_rules.md:108`) требуют «2–4 варианта», а хендлер `offer_choices`
  (`handlers/world.py:384`, `choices_count`) и докстринг `OfferChoices` принимают 2–3 → Q1.

## 1. Решения (архитектура)
1. **T3 — текст раунда с invalid сохраняется.** `MasterSession.run`, ветка `elif calls:`: `result.texts += texts` без условия
   `not has_invalid` (ветка `max_tokens` не меняется — там текст по-прежнему отбрасывается). Исправление вызова идёт тем же
   `count_invalid`-циклом, как сейчас. Приписки «текст принят, не повторяй» не вводим (по данным §0 модель после invalid
   текст не повторяет; реплеи не трогаем лишним сообщением). `check_told` (`game/turn.py:452`) уже смотрит на
   `master.narration` всего хода — без изменений.
2. **`choices_unseen` без ворот `has_invalid`.** Сигнатура → `choices_unseen(done, told, accepted)`: единственная причина
   ворот (текст invalid-раунда выпадал из `told`) исчезает с п.1; случай «invalid + принятый `offer_choices` без текста»
   получает `CHOICES_NOTE` вместе с ошибкой инструмента (модель чинит вызов и пишет сцену одним ответом).
   Тест `test_invalid_call_next_to_accepted_offer_has_no_choices_note` переворачивается.
3. **T5 — приписка-повтор внутри сессии (не повтор хода).** Один дополнительный вызов в том же цикле, по механизму
   `CHOICES_NOTE`, без `RETRY_NOTES` (повтор хода = двойная цена и новый бросок — ровно то, что чинит T3).
   - `MasterResult.accepted: set[str]` (новое поле) — имена принятых (accepted/clamped) инструментов за весь ход;
     `run_round` делает `result.accepted |= accepted_names`.
   - `ends_with_choice(narration) -> bool` (новая функция уровня модуля `master/session.py`): последняя непустая строка
     кончается `?`; **или** последний абзац — ≥ 2 строк, все с маркером (`-`, `—`, `•`, `*`, `1.`/`1)`); **или** последний
     абзац — ≥ 2 коротких (≤ 120 симв.) строк без конечной пунктуации (`.!…»"`); **или** в последней строке `|`.
     Абзацы — по пустой строке, вход — `result.narration` (после `plain_text`).
   - `MasterSession.choices_missing(ctx, result, mode) -> bool` (новая): `role == "narrator"` и `mode == "explore"` и
     `ctx.bundle.session.active_combat is None` и `"offer_choices" not in result.accepted` и `ends_with_choice(result.narration)`.
   - `MasterSession.ask_choices(ctx, req, response, run_id, plan, executor, mode, result)` (новая): к `req.messages`
     добавляются `assistant(response.content)` и `user([Text(CHOICES_ASK)])`; один `self.call`; тег `choices_retry` в
     `result.report_tags` всегда; из ответа исполняется **только первый `ToolCall` с именем `offer_choices`** через
     `run_round` (другие вызовы — skill_check и т.п. — не исполняются: ни решения, ни броска); тексты ответа **не** попадают в
     `result.texts` (рассказ уже принят); `rounds`/`invalid_count` не меняются (иначе `check_told`/бюджет invalid
     срабатывают на служебном вызове); `TurnFailed` из `self.call` (network/fatal) и `refusal` ответа — проглатываются,
     ход принимается как есть (служебный вызов не должен откатывать удачный ход; запись ошибки в журнал остаётся).
     Второй приписки нет. `stop_reason` результата — от ответа на приписку (журнал/репорт).
   - Точка вызова — в `run`, ветка `if note is None:` (финальный текст): `result = self.finish(result)`; если
     `choices_missing` → `ask_choices` → `return result`. Ранний выход `clean and done and told` не задет (там `offer_choices`
     принят). SINGLE_SHOT и world/summarizer — не задеты (роль/режим).
   - `CHOICES_ASK` (константа рядом с `CHOICES_NOTE`): «Ход кончился вопросом к игроку или списком вариантов, а `offer_choices`
     не вызван. Вызови `offer_choices` с этими вариантами (два или три коротких, по смыслу разных); текст сцены не повторяй.»
   - Разбор списка в варианты без модели — не делаем (решение R6 §8).
4. **Правила.** `narrator_rules.md:108`: «2–4» → «2–3» (по Q1а; хендлер и докстринг уже 2–3) и одна фраза: «Список вариантов
   текстом (строки с «-», вопрос в конце) без вызова `offer_choices` — ошибка». Меняет `system_sha256` → старые реплеи с
   рассказчиком расходятся (прецедент B59 В1, принято).
5. **T4 — живая проверка**, кода нет: пункты 3, 10, 11, 12 `docs/checklist-b59-live.md` входят в чек-лист ЖП1 (#18п); в
   `docs/checklist-tv-live.md` — ссылка на них, не дубль.
6. **Smells (нулевой баланс).** `run` уже помечен (complexity 48, файл 102) — две новые строки в нём новых smells не дают.
   `ask_choices` с 8 параметрами = +1 «many parameters»; компенсация: `run_call(ctx, call, executor, allowed, result, mode)`
   (6 параметров, помечен) → убрать `allowed`, считать `{d["name"] for d in tool_set(mode)}` внутри (`run_round` тогда
   `allowed` не передаёт; `tool_set` дёшев) = −1. `ends_with_choice`/`choices_missing` — простые (≤ 5 условий).
   Если всё равно 201+ — вынести тело `elif calls:` из `run` в `tool_round` (снимет «high complexity» с `run`, −1).

## 2. Затронутые файлы
`master/session.py` (`MasterResult.accepted` — новое поле; `MasterSession.run`, `run_round`, `run_call`, `choices_unseen`;
`ends_with_choice`, `MasterSession.choices_missing`, `MasterSession.ask_choices` — новые; `CHOICES_ASK` — новая константа);
`master/prompts/narrator_rules.md:108`; `game/turn.py` — без изменений кода (`check_told`, `explore_turn`, `retry_result`
только проверяются тестами); `protocol/handlers/world.py offer_choices` и `protocol/requests.py OfferChoices` — без изменений
(при Q1б — хендлер, докстринг, `tests/unit/protocol/test_apply_world.py:413`).
Документы: ARCHITECTURE.md:473–474 (абзац про бюджеты цикла: текст invalid-раунда сохраняется; приписка `CHOICES_ASK`,
тег `choices_retry`, не в бою, один раз); tests/unit/master/master_kit.py шапка (контракт `.texts` — «отбракованные по
пустоте / без обязательного / max_tokens», текст раунда с invalid — принят; `.accepted`; `choices_unseen` без `has_invalid`);
BACKLOG 64 (T3, T5 ✅, остальное остаётся), ROADMAP #18, HANDOFF (оркестратор: расход и модель каждой роли);
docs/checklist-tv-live.md (не коммитить).

## 3. Шаги kaban
1. `MasterResult.accepted = set()`; `run_round`: `result.accepted |= accepted_names`.
2. `run`: `result.texts += texts` без `not has_invalid`; `choices_unseen(done, told, accepted)`; вызов обновить.
3. `ends_with_choice`, `CHOICES_ASK`, `choices_missing`, `ask_choices`; точка вызова в ветке `note is None`.
4. `run_call` без `allowed` (компенсация smells); `make smells` после файла.
5. `narrator_rules.md:108` по п.1.4 (после Q1); `master_kit.py` шапка; ARCHITECTURE.md:473–474.
6. **Офлайн-реплей после шагов 1–3** (не коммитить, копия репорта в каталог вне проекта): `--replay-report` копии
   `issues/20261014T173713-t436-short_retry` → ожидаемо **код 1** (журнал старого хода содержит повтор с другим броском),
   но в выводе: рассказ начинается с «Ты отступаешь от стола и киваешь Каю», тега `short_retry` нет, использовано 3 вызова.
   T5: одноразовый скрипт по `calls-004.jsonl` дракона — `ends_with_choice` даёт True на 4/4 финальных текстов
   run-…-2c23c8-1…4 и False на всех 737 explore-ходах с `offer_choices` (кроме «?», где приписка всё равно не идёт).
7. Чек-лист `docs/checklist-tv-live.md` для ЖП1 (20 ходов на flash-lite — `/model narrator gemini:gemini-3.5-flash-lite`):
   нет односторонних ходов (текст без меню вариантов, когда ход кончается вопросом/списком); в репортах `choices_retry`
   тег есть, в журнале приписка видна, после неё `offer_choices`; нет `short_retry` при отклонённом инструменте с полной
   сценой; нет двойных бросков в одном ходу (`rolls` репорта); в бою приписки нет; sonnet: пункты 3, 10–12 checklist-b59-live.
8. BACKLOG 64, ROADMAP #18; `make smells`.

## 4. kaban-doeba (TDD; cov/mutmut гоняет оркестратор фоном)
T3 (`tests/unit/master/test_master_session_loop.py`, `test_master_session_errors.py`):
- раунд «текст + invalid», затем исправленный вызов, затем короткий финал → `result.texts == [сцена, финал]`, `narration`
  содержит оба, `invalid_count == 1`, 3 вызова; раунд «текст + invalid» → финал текстом → оба текста;
- invalid без текста → `texts` как раньше; `max_tokens` с вызовами → текст по-прежнему отброшен (существующий тест);
- паттерн t436: «сцена + invalid + accepted offer_choices» → `CHOICES_NOTE` нет (told), раунд 2 без текста → раунд 3 текст →
  3 вызова, `narration` = сцена + финал; третий invalid → `TurnFailed("invalid")` как раньше;
- `choices_unseen`: «invalid + accepted offer_choices без текста» → `CHOICES_NOTE` после ToolResult с ошибкой (перевернуть
  `test_invalid_call_next_to_accepted_offer_has_no_choices_note`); `offer_choices` сам invalid без текста → приписки нет;
- `result.accepted`: accepted и clamped попадают, rejected/Invalid — нет, копится по раундам;
- game-уровень (`tests/unit/game/test_game_short_retry.py`): t436-паттерн через `TurnRunner` → тегов нет, один проход,
  `rolls` один, RNG как у одного прохода; реплей синтетического репорта (`game_kit`, как `test_b59_replay.py`) — код 0.
T5 (`tests/unit/master/test_master_session_loop.py` или новый `test_master_choices_ask.py`; game — `test_game_choices_ask.py`):
- `ends_with_choice`: «?» в конце → True; «- a\n- b», «— a\n— b», «1. a\n2) b», «• a\n• b» → True; одна строка с маркером →
  False; 3 голые короткие строки в последнем абзаце → True; те же с точками → False; строка > 120 → False; «a | b» в
  последней строке → True; проза с «.» → False; «— Ну что? — спрашивает Селена.» → False; пустая/пробельная → False;
  4 реальных хвоста drunk_dragon 130–133 (фикстуры-строки) → True;
- сессия: финальный текст с «?» без `offer_choices` в ходу → ещё один вызов: `messages[-2]` = assistant(content ответа),
  `messages[-1]` = user Text(`CHOICES_ASK`), cache False, первое сообщение не изменилось; ответ `offer_choices` → Decision
  accepted, `session.offered_choices` заданы, `result.requests` содержит offer_choices, тексты ответа не в `texts`/`narration`,
  тег `choices_retry`, `rounds` и `invalid_count` не выросли, `stop_reason` от ответа на приписку;
- ответ на приписку текстом → ход принят, `narration` прежний, тег есть, вызовов ровно +1; `offer_choices` из 4 пунктов
  (Invalid `choices_count`) → принят как есть, `invalid_count` прежний, больше вызовов нет; `skill_check` + `offer_choices` →
  исполнен только `offer_choices` (нет решения/броска по skill_check), `offer_choices` в любом порядке; `refusal` /
  transient×4 (`RetriesExhausted`) / `LlmFatal` на приписке → ход принят без ошибки, тег есть (sleeper как в тестах сети);
- приписки нет: `offer_choices` принят в любом раунде (в т.ч. ранний выход), роль world/summarizer, режимы combat_narrate /
  combat_classify, `start_combat` в этом ходу (`active_combat` не None), текст без признаков, `offer_choices` отклонён ранее
  и текст без признаков; `offer_choices` отклонён ранее и текст со списком → приписка один раз;
- текст-только ход (rounds 0) короче 80 симв. с «?» → приписка, `check_told` не срабатывает (rounds 0), `short_retry` нет;
- game-уровень: после приписки `TurnRecord.requests` содержит offer_choices → `offer_is_stale` False, цифра игрока
  подставляет вариант; тег → авто-репорт записан (стиль `test_auto_reports.py`), `--replay-report` этого репорта код 0;
  журнал: вызов приписки с тем же `run_id`, номер продолжается; в `combat_turn` приписки нет;
- `CHOICES_ASK`: упоминает `offer_choices`, «два или три», «не повторяй»; правила: стр. 108 «2–3» (по Q1).
mutmut (сверено grep-ом; «новая» — создаётся в партии): `ai_dm.master.session:MasterSession.run`, `run_round`, `run_call`,
`choices_unseen`, `finish`; `ai_dm.master.session:ends_with_choice` (новая), `MasterSession.choices_missing` (новая),
`MasterSession.ask_choices` (новая); `ai_dm.game.turn:TurnRunner.check_told`, `TurnRunner.explore_turn` (регресс).
Пик контекста doeba > 200k — делить на «тесты» и «мутанты/cov» (family.md).

## 5. Критерии готовности
Тесты зелёные, cov ≥ 97 %, smells ≤ 200, ruff/dead чисто, mutmut по списку без живых (кроме эквивалентных/текста);
`ai-dm --mock` код 0; офлайн-реплей t436 по §3 п.6 (3 вызова, без `short_retry`); живые вызовы в партии не делаются;
ревью mama-kaban; `docs/checklist-tv-live.md` для ЖП1 (#18п).

## 6. Оценка
papa ~100 тыс. (факт, fable); kaban 60–80; doeba 120–160; mama ~25. Итого ≈ 0,3–0,37 млн.

## 7. Риски
- T3: если модель после ошибки инструмента перепишет сцену (в корпусе 0 случаев из 2), игрок увидит дубль; лечение — приписка
  «текст принят, не повторяй» (не в этой партии, по ЖП1).
- T3: текст раунда может описывать исход отклонённого инструмента («письмо у тебя») до исправления — сейчас то же самое
  попадало после повтора; правило «подстрой рассказ под фактический результат» уже есть.
- T5: приписка — лишний вызов с полным контекстом (~15–20 тыс. вх. токенов на flash-lite ≈ $0,002); на 3.8-flash/sonnet по
  корпусу 0 срабатываний вне боя. Эвристика «голые строки» — единственная без маркеров; при ложном срабатывании цена —
  один вызов, модель ответит текстом, ход принят.
- T5: список остаётся в тексте рассказа и дублируется меню (Q2). Варианты из 4 пунктов → `choices_count` → приписка впустую (Q1).
- Авто-репорт на каждый `choices_retry` — на flash-lite почти каждый ход, папка issues растёт до ТО (лимит issues/, T9) (Q3).
- Старые репорты: изменение правил (system sha) → `--replay-report` старых ходов рассказчика код 1 (прецедент B59 В1);
  ходы с паттерном T3/T5 расходятся и без правил (лишний/недостающий вызов, прецедент AD1 Q4).
- `check_told` остаётся на пороге 80 по всему ходу; `short_retry` после T3 ждём только для «сцена в мышлении» (T4).

## 8. Вопросы проектировщику (рекомендации papa)
1. **Число вариантов** — правила «2–4» против движка «2–3» (`choices_count`): (а) правила → «2–3», движок не трогаем;
   (б) движок и докстринг → 2–4 (хендлер, тест protocol, меню). Рек.: (а) — минимальная правка, flash-lite и так даёт 3.
2. **Список в тексте после успешной приписки**: (а) рассказ не трогаем — варианты продублируются меню (игрок видит список и
   меню «1–3»); (б) срезать хвостовой абзац-список / строку-вопрос из `narration`, когда `offer_choices` после приписки принят.
   Рек.: (а) — без хирургии текста (в духе «разбор списка не делаем»); (б) — кандидат в BACKLOG после ЖП1, если глаз режет.
3. **Авто-репорт на `choices_retry`**: (а) да, как `short_retry` (любой тег → репорт; ЖП1 меряет частоту); (б) тег без репорта —
   список «тихих» тегов в `GameApp.auto_report`. Рек.: (а) на ЖП1, пересмотреть в ТО вместе с T9 и лимитом issues/.
