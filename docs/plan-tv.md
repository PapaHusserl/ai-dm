# План мини-партии #18 «ТВ Текст и выбор» (T3 + T5 + живая проверка T4; BACKLOG 64)

Автор: papa-kaban, 2026-10-15. Статус: **утверждён 2026-10-15** («окей, кабаним»); Q1–Q3 — (а), (а), (а), как рекомендовал papa.
Груминга нет (R6 §10 п.2а: техдолг по правилу фикса). Сейв v9 без изменений. Оценка ≈ 0,3–0,37 млн (роадмап 0,45).
Smells 200/200 — нулевой баланс. Источники: docs/plan-roadmap-r6.md «ТВ», §6 (критерии), §8 (разбор списка «- …» без
модели — не делаем); docs/plan-techdebt.md T3/T5/п.2; BACKLOG 64; docs/plan-b59.md, docs/plan-b59.md; HANDOFF 17а (багфикс —
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
5. **T4 — живая проверка**, кода нет: пункты 3, 10, 11, 12 `checklist-b59-live.md` входят в чек-лист ЖП1 (#18п); в
   `checklist-tv-live.md` — ссылка на них, не дубль.
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
checklist-tv-live.md (не коммитить).

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
7. Чек-лист `checklist-tv-live.md` для ЖП1 (20 ходов на flash-lite — `/model narrator gemini:gemini-3.5-flash-lite`):
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
ревью mama-kaban; `checklist-tv-live.md` для ЖП1 (#18п).

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

## Правки по ревью: Ревью #18 «ТВ Текст и выбор» (мама-кабан, 2026-10-15) (бывш. docs/decisions/tv-review.md)

Проверено: `git diff` по src/, tests/, docs/ARCHITECTURE.md, BACKLOG.md; новые test_master_choices_ask.py,
test_narrator_choices_rules.py, test_game_choices_ask.py, tests/scenarios/test_tv_replay.py. Сверено с docs/plan-tv.md
(Q1–Q3 = а, а, а). cov/smells/mutmut не запускались (их гоняет оркестратор).

### Хорошо
- T3: в `run`, ветка `elif calls:`, `result.texts += texts` теперь без условия; в ветке `max_tokens` текст по-прежнему
  отбрасывается. `choices_unseen(done, told, accepted)`, ворота `has_invalid` убраны, как в п.1.2 плана.
- T5: `MasterResult.accepted`, `ends_with_choice`, `choices_missing`, `ask_choices`, `CHOICES_ASK` сделаны по п.1.3.
  `ask_choices` исполняет только первый `offer_choices`, тексты не добавляет, `rounds` и `invalid_count` не трогает,
  `TurnFailed` и `refusal` глотает. Вызов стоит только в ветке `note is None`, ранний выход и SINGLE_SHOT не задеты.
- Компенсация smells: из `run_call` убран `allowed` (п.1.6).
- `narrator_rules.md`: «2–3» и фраза про список текстом (Q1а).
- Q2а: текст после приписки не трогается. Q3а: авто-репорт на `choices_retry` есть (test_game_choices_ask).
- Сомнительного места с `offer_choices` из 4 пунктов в ответе на приписку нет: `TurnResult.requests` копит только
  accepted/clamped (`turn.py` `recording`), поэтому `offer_is_stale` не оживит варианты прошлого хода.
- Замена `test_narration_with_rejected_round_does_not_excuse_empty_final` смысл не теряет. Старый тест проверял
  «текст invalid-раунда не считается рассказом, пустой финал повторяется». По T3 это утверждение перевёрнуто
  (`..._invalid_round_excuses_empty_final`: 2 вызова, narration = текст раунда). Ветка «invalid без текста, потом пустой
  финал → повтор, invalid_count 2, narration "Рассказ."» сохранена во втором тесте. Покрыты обе стороны.
- Тесты по §4 плана закрыты: ends_with_choice (включая 4 хвоста дракона и границу 120/121), запрос приписки, сбои,
  случаи «приписки нет», журнал, game-уровень, реплей. Реализацию под тесты не подгоняли.

### Замечания (необязательные, мержу не мешают)
1. `ends_with_choice`: маркер «—» совпадает с репликами диалога. Если последний абзац — две реплики «— …», функция
   вернёт True, даже если они кончаются точкой. В плане «—» назван явно, а корпус §0 проверял ложные срабатывания на
   ходах с `offer_choices`. Ходы без него, которые кончаются диалогом, там почти не встречаются. Цена ошибки — один вызов
   (Risk §7). Предложение: на ЖП1 отдельно смотреть репорты `choices_retry` с хвостом-диалогом. Если такие будут —
   в BACKLOG: для «—» требовать отсутствия конечной пунктуации, как для голых строк.
2. `ends_with_choice` разбирает текст двумя проходами: `lines`, потом `reversed(narration.split("\n"))`. Можно один:
   набрать `block` и взять `block[0]` как последнюю строку для проверок «?» и «|». Простота, не баг.
3. `ask_choices`: если ответ на приписку пришёл с `stop_reason == "max_tokens"`, его `offer_choices` всё равно
   исполняется. В основном цикле вызовы из `max_tokens` считаются невалидными. Обрезанный JSON отсеет `parse_request`,
   так что вред маловероятен; есть тест `test_ask_stop_reason_is_from_ask_answer`, значит поведение закреплено
   сознательно. Оставить, но упомянуть одной фразой в ARCHITECTURE (абзац `CHOICES_ASK`) или в комментарии.
4. `run_round` по-прежнему считает `allowed` (нужен только для `summarize_chapter`), и `run_call` считает его ещё раз
   на каждый вызов. Это цена компенсации smells по плану, приемлемо.
5. Офлайн-реплей t436 (§3 п.6) прошёл не через `--replay-report`, а скриптом с отключённым fingerprint: 3 вызова,
   без `short_retry`, сцена сохранена. Отклонение оправдано, потому что запрос вызова 1 менялся в B59/Т60. Предложение:
   записать в HANDOFF способ проверки и где лежит скрипт/вывод (вне проекта), чтобы аудит мог повторить.

### Вердикт
Можно мержить. Обязательных правок нет; п.1 — наблюдение на ЖП1, п.5 — одна строка в HANDOFF.

### Мутанты

Выжившие мутанты mutmut по `src/ai_dm/master/session.py` (41 шт.). Тесты: `tests/unit/master/test_master_session_loop.py` (SL), `test_master_empty_note.py` (EN), `test_master_choices_ask.py` (CA).

| Мутант (run_call / run_round / ask_choices / run) | Исход |
|---|---|
| run_call 1, 2 (дефолт mode) | убит: SL `test_run_call_default_mode_is_explore` |
| run_call 15 (разделитель в «Доступны») | убит: SL `test_run_call_not_in_mode_lists_allowed_with_comma` |
| run_call 17, 18 (ключ "type" в input) | убит: SL `test_run_call_type_mismatch_is_invalid_with_both_names` (при мутации тип перезаписывался бы и расхождение не ловилось); SL `test_run_call_missing_type_is_filled_from_name` |
| run_call 33, 34, 35 (get('type') в тексте) | убит: SL `test_run_call_type_mismatch_is_invalid_with_both_names` (в message есть 'skill_check') |
| run_call 45, 46, 47 (код/текст invalid_request) | убит: SL `test_run_call_bad_fields_is_invalid_request_with_validation_text` |
| run_call 56 (report_tag Invalid -> result) | убит: SL `test_run_call_report_tag_of_invalid_from_executor_goes_to_result` |
| run_round 6 (has_invalid = None) | убит: SL `test_run_round_without_invalid_returns_false_flag` (`is False`); по сути почти эквивалентен: везде используется как truthy |
| run_round 53 (текст ноты «Нужны оба вызова») | текстовый: подсказка модели; подстрока при этом проверяется в `test_chapter_incomplete_round_tells_model_to_send_both`, поведение не меняет |
| run_round 58, 59 (has_invalid = True в неполной свёртке) | убит: EN `test_chapter_incomplete_round_counts_as_invalid` |
| ask_choices 29, 33 (plan не передаётся в call) | убит: CA `test_ask_call_in_journal_has_context_meta_like_main_call` |
| ask_choices 36, 37 (сравнение с "refusal") | убит: CA `test_ask_refusal_answer_with_offer_choices_is_not_executed` |
| run 1 (дефолт world_text "XXXX") | убит: SL `test_run_without_world_text_has_empty_world_text_in_system` |
| run 45 (required_done = None) | эквивалентный: значение используется только как булево (`not required_done`, `done`, `empty_ok`) |
| run 152 (required_done = None в свёртке) | эквивалентный: то же, только булево |
| run 111, 114, 115, 116 (текст TurnFailed «корректный вызов», max_tokens) | текстовый: пояснение исключения, поведение (reason="invalid") то же |
| run 212, 215, 216, 217 (тот же текст, ветка has_invalid) | текстовый: пояснение исключения |
| run 266, 269, 270, 271 (текст «корректный ответ») | текстовый: пояснение исключения |
| run 128, 133, 134, 135 (текст TurnFailed rounds) | текстовый: пояснение исключения, reason="rounds" проверен |
| run 161 (`texts +=` -> `=` в одноразовом выходе) | убит: EN `test_single_shot_texts_of_earlier_rounds_are_kept` |
| run 253 (plan=None в ask_choices) | убит: CA `test_ask_call_in_journal_has_context_meta_like_main_call` |

Примечание: mutmut заново не гонялся, убийство подтверждено разбором диффов и прогоном своих файлов (174 passed).

## Итог: Из HANDOFF.md до 22д (бывш. docs/HANDOFF.md)

- **18 ТВ ✅ закоммичена 2026-10-15:** план docs/plan-tv.md (Q1–Q3 = а,а,а: правила «2–3» варианта; список в тексте не срезаем; авто-репорт на `choices_retry`). T3 — текст раунда с invalid сохраняется (кроме `max_tokens`); T5 — `ends_with_choice` + `MasterSession.choices_missing`/`ask_choices`, приписка `CHOICES_ASK` одним вызовом без повтора хода (тег `choices_retry`, вне боя). Ревью — docs/plan-tv.md (обязательных правок нет; к ЖП1: «—»-реплики диалога могут давать ложный `choices_retry` — смотреть репорты, при частоте завести в BACKLOG), там же разбор 41 выжившего мутанта (21 убит, 2 эквивалентных, 18 текстовых). Офлайн-гейт t436: `--replay-report` расходится на вызове 1 (запрос менялся в B59/Т60), поэтому kaban прогнал копию репорта скриптом с отключённой проверкой fingerprint в `ReplayAdapter` — 3 вызова, сцена сохранена, `short_retry` нет (скрипт был в scratchpad сессии, не сохранён; повторить — так же, отключив сверку fingerprint). Тесты 16397 passed (+ мутантные), cov 98 %, smells 200/200, dead чисто. Расход ≈ 0,39 млн: papa 129 тыс. (fable), kaban 54 тыс., doeba 96 тыс. + мутанты 51 тыс. (sonnet), mama 61 тыс. Чек-лист checklist-tv-live.md (не коммитить) — в ЖП1. **Дальше:** 18п ЖП1 — papa собирает единый ~/.config/ai-dm/checklists/checklist-zhp1-live.md, прогон за пользователем.
