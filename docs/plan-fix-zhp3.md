# Фикс ЖП3

Фикс-резерв после живого прогона ЖП3 (docs/plan-zhp3.md «Итог»). Состав: BACKLOG 104 (high, первым), 103, 99, 101, 100.
Без полей сейва. Рамка — строка «Фикс ЖП3» в docs/ROADMAP.md.

## Груминг

- Свинопас (2026-10-20): 104, 103, 99 готовы; 101, 100 — после решений проектировщика. Находка: утёкший JSON попадает в
  `recent_turns` и повторяется рассказчиком — чистить текст до записи хода.
- Кабан-свекровь (2026-10-20): решений за проектировщика нет; сверх пунктов — обобщение санитайзера 104 на все
  инструменты и новое поле в состоянии героя для 100; пропущен вариант «усилить правило промпта» для 101.
  Решение 2026-10-07 о 103 — plan-trade.md:505 (п. 3 «Решений» партии Т2).

## Решения

Проектировщик, 2026-10-20:
1. 101 — усилить правило промпта (narrator_rules); детектора и служебного повтора нет.
2. 100 — при отказе в длинном отдыхе игрок видит время, когда можно снова, и что можно сейчас (короткий отдых или
   подремать — время идёт, без восстановления). Заранее в состоянии героя «длинный отдых доступен с …» не давать.
3. 103 — отмена решения 2026-10-07 (plan-trade.md, Т2 п. 3) только для `why=spent`: сюжетный предмет без держателя
   можно потратить, в том числе `quest: true` (вернуть потом нельзя). `given`/`lost`/`stolen` — по-прежнему с держателем.
4. 104 — санитайзер только для `offer_choices` (JSON и хвост описания `OfferChoices`), не для всех инструментов.
5. 104, живой мир drunk_dragon — испорченные ходы 418–441 в `recent_turns` не чистить; проверить на первых ходах ЖП4.
6. Модель кабана и кабана-доебы на шаг — sonnet.
8. После разбора репортов t446–t458 (2026-10-20): в состав добавлены BACKLOG 106 (рассказчик боя без options,
   `end_combat` только сдача/бегство), 107 (`travel_to "none"`), 108 (спутник даёт зелье герою), 109 (оценка токенов
   gemini). 110, 111 — в беклог, не в шаг.
9. 104 — решение 4 пересмотрено: чистить все найденные формы утечки — JSON, «offer_choices\n- …» без `{`,
   самоинструкция модели («Подсказка по результатам…»), варианты списком в тексте при принятом `offer_choices`, HTML.
10. 104 — прошлые ходы чистить при сборке промпта (`recent_turns`), сейв не трогать (решение 5 в силе).
11. 103 — правило рассказчика: сюжетный предмет уничтожен/вылит = `take_item why=spent`; `lost` без держателя не вводить.
12. План ниже написан до пп. 8–11 — переписать папой-кабаном, затем смета заново.
13. Редакция 2 плана (3 партии, sonnet; смета тестя ≈ 1,1–1,3 млн субагентских токенов, ок по бабкам) — «окей, кабаним»
   (2026-10-20); холд п. 7 снят.
7. План — «холдим» (после сметы тестя: ок по бабкам, ≈ 0,7–0,9 млн субагентских токенов на 2 партии); в работу не передан.

## План (папа-кабан, 2026-10-20, редакция 2 — по решениям 6, 8–11)

Контур: вне msa; режим: встроить. Код на bc652da; ссылки на строки — по нему. Образцы форм утечки — журнал
`saves/drunk_dragon-00000001/journal/calls-012.jsonl.gz`, `calls-013.jsonl` (только чтение); разбор t446–t458 —
scratchpad `reports-446-458.md` оркестратора.

**Задача / проект:** девять находок ЖП3 — утечка служебного текста во всех формах и чистка `recent_turns` (104),
`take_item why=spent` сюжетного (103), остаток костей хитов (99), правило «вещь от NPC — инструментом» (101), текст отказа
в длинном отдыхе (100), рассказчик боя без `options` и `end_combat` только после сдачи/бегства (106), `travel_to "none"`
(107), спутник/NPC даёт зелье герою (108), оценка токенов gemini (109).

**Правила (аппрув первым пунктом):**
- 104 (решения 9, 10): было `result.narration = plain_text("\n\n".join(texts))` (`master/session.py:321`, `finish`) →
  станет `narration, leaked = cut_leaks(plain_text(...), accepted_choices)`; формы, которые режет `cut_leaks`:
  (а) JSON `{ "offer_choices": [...] }` и `{ "type": "offer_choices", "choices": [...] }` (ходы 428, 437);
  (б) строка `offer_choices` (в бэктиках/жирном/с двоеточием) и под ней `- [...]` или маркированный список (451–455);
  (в) абзац, начинающийся с «Подсказка по результатам», и всё до разделителя `---` включительно, без разделителя —
  только этот абзац (446, 458); (г) хвостовой нумерованный/маркированный блок, когда `offer_choices` принят (457, 458);
  (д) HTML-теги `<p>`, `<strong>`, `<em>`, `<br>` — снять теги, текст оставить (450). Варианты из (а)/(б) при
  отсутствии вызова и допустимости (`choices_allowed`) применяются как вызов `offer_choices`. Было
  `turn_data(turn)["narration"] = turn.narration` (`master/prompt.py:91`) → станет `cut_leaks(turn.narration)[0]` —
  прошлые ходы чистятся при сборке промпта, сейв не трогается.
- 103 (решения 3, 11): было `if request.holder_npc_id is None: return None, Invalid(holder_required)` (`resources.py:516`,
  `take_holder`, для любого `why`) → станет `if request.why == "spent": return None, None` до проверки держателя;
  `given`/`lost`/`stolen` — как было. Правило рассказчика: уничтожен/вылит/сожжён = `spent`; `lost` без держателя не
  вводится.
- 99: новое — `sheet_data` (`prompt.py:378`) отдаёт `hit_dice: {"current", "max"}` суммой по `rests.hit_dice_pools`
  (одно число — как движок режет в `rest`, `resources.py:770`).
- 100: было `signal` «Длинный отдых кончился в …; следующий — не раньше …. Отдых не повторяй; сон или ожидание дай через
  advance_time.» (`resources.py:755–757`, `rest_redundant`) → станет «Скажи игроку: длинный отдых снова возможен с
  {clock_text(next_s)}; сейчас можно короткий отдых (`rest short`) или просто подремать/подождать — время двигай
  `advance_time`, HP и ресурсы при этом не восстанавливаются.» Reason и тег `rest_repeat` прежние.
- 101: новое — пункт в «Чего нельзя» (narrator_rules.md:134–138); детектора нет (решение 1).
- 106: было `if ctx.mode in ("combat_classify", "combat_narrate"): combat["options"] = …` (`prompt.py:452`) → станет
  `if ctx.mode == "combat_classify"`. Было `end_combat` принимается при любом составе боя (`handlers/combat.py:341–355`)
  → станет: ни один участник стороны `enemies` не в статусе `fled`/`surrendered` → `rejected("бой идёт", …,
  report_tag="end_combat_refused")`. `end_combat` есть только в `combat_narrate` (`schema.py:27`), режим в хендлере не
  нужен.
- 107: было `NEUTRAL = {"category": "none", "travel_to": ""}` (`requests.py:400`, `AdvanceTime`) → станет `travel_to`
  `"none"` → `None` наравне с `""` (валидатор поля `mode="before"`: `"none"` → `""`, дальше `cut_neutral` как сейчас).
- 108: новое — правило рассказчика: зелье/эликсир герою даёт спутник или NPC (в том числе бессознательному) →
  в том же ходу `give_item` (id зелья) + `use_item`; код не меняется.
- 109: было `[master.chars_per_token_by_provider] anthropic = 2.2` (`app_defaults.toml:135–136`) → станет
  `anthropic = 2.2`, `gemini = 3.0`. Замер по журналу calls-013 (71 вызов gemini): оценка/факт медиана 1,23,
  разброс 0,88–1,28; 2,5 × 1,2 = 3,0 — с запасом ≈ 2,5 % к факту (переоценка безопаснее недооценки: `overflow`).

**Поведение:** меняется — 104: игрок не видит JSON, служебных строк, самоинструкций и HTML; `recent_turns` в промпте
без мусора (сейв прежний); при утечке без вызова варианты всё равно предлагаются без платного повтора. 103: сюжетный
предмет (и `quest: true`) уходит по `spent`, остаётся в `world.custom_items` с `holder = None`, в `lost_items` не
попадает. 106: рассказчик боя не видит `options` (−6,5k токенов входа на вызов), `end_combat` при дерущихся врагах
отклоняется. 107: `travel_to: "none"` = «пути нет». 109: вытеснение мягче — `recent_turns` в промпте полнее (ложных
`xp_repeat` из-за невидимого «Опыт: +» меньше). 99, 100, 101, 108 — только вход рассказчика (данные, сигнал, правила).

**Вне ai-dm:** нет. Полей сейва нет, версия сейва не меняется.

**Модули/файлы/функции (все найдены grep, кроме «новая»):**
- `src/ai_dm/master/session.py`: `plain_text` (117, не меняется), `MasterResult` (136), `MasterSession.finish` (318),
  `choices_missing` (324), `ask_choices` (347), `run` (цикл; выходы ~437/445/462), `MARKED_LINE` (58); новые:
  `cut_leaks`, `MasterSession.choices_allowed` (вынос условия `over` из `choices_missing`),
  `MasterSession.apply_leaked_choices`.
- `src/ai_dm/master/prompt.py`: `turn_data` (87), `PromptBuilder.sheet_data` (378), `PromptBuilder.combat_data` (421,
  строка 452); импорт `ai_dm.rules.rests` (prompt.py уже импортирует `rules.derived`, `rules.inventory` — цикла нет).
- `src/ai_dm/protocol/requests.py`: `OfferChoices` (641, docstring), `TakeItem` (322, описания `why`,
  `holder_npc_id`), `EndCombat` (253, docstring), `AdvanceTime` (389, новый валидатор `travel_to`), `UseItem` (296,
  docstring).
- `src/ai_dm/protocol/handlers/resources.py`: `take_holder` (506), `rest_redundant` (741); `take_item` (538) без правок.
- `src/ai_dm/protocol/handlers/combat.py`: `end_combat` (341).
- `src/ai_dm/game/turn.py`: `narrate_combat` (558, строка 561 — убрать `combat_options=next_options(...)`);
  `src/ai_dm/game/combat_flow.py`: `next_options` (158) — единственный вызов на 561, после правки удалить (`make dead`).
- `src/ai_dm/config/app_defaults.toml`: `[master.chars_per_token_by_provider]` (135–136).
- `src/ai_dm/master/prompts/narrator_rules.md`: 18 (не меняется), 38 (бой: `end_combat`), 72 (`use_item`: зелье от
  спутника/NPC), 88 (сюжетные предметы: `spent`), 108 (состояние героя: `hit_dice`), 134–138 («Чего нельзя»: вещь от NPC).
- Тесты, которые меняются: `tests/unit/master/test_master_prompt.py:449–461` (параметризация `combat_narrate` у
  `options` — на «ключа нет»), `tests/unit/protocol/test_apply_combat.py:457` (`end_combat` при активных врагах — фикстуре
  нужен сдавшийся/бежавший), `tests/unit/protocol/test_take_item_holder.py:113,121` (без держателя — Invalid «для любого
  why» → «кроме spent»), `tests/unit/protocol/test_rest_repeat.py` (текст сигнала), `tests/unit/protocol/test_requests.py:342`
  (рядом — `"none"`), `tests/unit/config/test_app.py:661–676` (`by_provider` по умолчанию: `{"anthropic": 2.2}` → с
  `gemini`), `tests/unit/master/test_static_budget.py` (STATIC_MAX 20960, замер Ж2 20344; docstring короче, правил +5
  строк — порог поднимать только при превышении, с причиной в шапке). Не затронуты: `tests/golden/k0_sheet_data_*`
  (лист героя, миграция v9), «WINDOW в memory_script.py» (не найден, есть только `NPC_MEMORY_WINDOW`).

**Партии (три; под sonnet — каждая однородна: один слой кода, ≤ 5 функций с логикой):**

П1 — 104 целиком (high): утечка и чистка. Только `session.py`, `prompt.py:turn_data`, docstring `OfferChoices`.
1. `requests.py:642` `OfferChoices` — docstring «Предложить игроку два-три варианта ответа.» (вторая фраза — дубль
   narrator_rules.md:18). Проверка: `tool_defs(["offer_choices"])[0]["description"]` без «последнем ответе».
2. `session.py` — новая `cut_leaks(text, choices_taken=False) -> (text, choices | None)` рядом с `plain_text`,
   чистая функция, порядок шагов:
   - (д) HTML: `re.sub(r"</?(p|strong|em|b|i|br)\s*/?>", "", text)`; других тегов не трогать;
   - `LEAK_LINE = "Вызывай в последнем ответе, после результатов механики и текста сцены."` — убрать вхождения;
   - (в) абзацы по `\n\n`: абзац, чья первая строка после снятия `*`/`#`/пробелов начинается с «Подсказка по
     результатам» — удалить его и все следующие абзацы до первого абзаца-разделителя `---` включительно; разделителя
     нет — только этот абзац;
   - (а) якорь `\{\s*"(?:type"\s*:\s*"offer_choices"|offer_choices"\s*:)`; от `{` разобрать `json.JSONDecoder().raw_decode`
     (без счёта скобок), вырезать `[idx:end]`; варианты — `obj["choices"]` или `obj["offer_choices"]`, принять только
     список из 2–3 строк; `raw_decode` упал (оборван) — вырезать от `{` до конца, вариантов нет;
   - (б) строка целиком `^\W*offer_choices\W*$` (бэктики, `**`, двоеточие): удалить её и следующий за ней блок —
     либо `- [` + `raw_decode` массива (варианты как в (а)), либо подряд идущие строки `MARKED_LINE` (варианты не
     извлекать — это текст, не JSON);
   - (г) `choices_taken=True` и последний непустой абзац — блок строк `MARKED_LINE` (тот же разбор, что в
     `ends_with_choice`, session.py:84–96): убрать блок; при `choices_taken=False` не трогать — это и есть сигнал для
     `choices_missing`;
   - просто `{…}` без якоря на имя инструмента не трогать; схлопнуть тройные переводы строк, `.strip()`.
   Возвращает текст и варианты из (а)/(б), флаг «что-то вырезано» — через сравнение текста до/после.
3. `MasterResult` — поле `leaked_choices = None`; `finish` — для `self.role == "narrator"`: `cut_leaks(text,
   choices_taken="offer_choices" in result.accepted)`; текст изменился → тег `leak_cleaned` (один раз); варианты →
   `result.leaked_choices`. Другие роли — `plain_text` как сейчас.
4. `choices_allowed(ctx, mode)` — вынос из `choices_missing` (строки 327–335: роль, `CHOICE_MODES`, `over` по бою);
   `choices_missing` вызывает его.
5. `apply_leaked_choices(ctx, result, executor, mode)` — если `result.leaked_choices`, `"offer_choices" not in
   result.accepted` и `choices_allowed`: `self.run_round(ctx, [ToolCall(id="leak", name="offer_choices",
   input={"type": "offer_choices", "choices": …})], executor, result, mode)` — тот же путь, что у модели (`run_call` →
   `parse_request` → хендлер `world.offer_choices:576`, `requests`/`decisions` хода). Вызывать в `run` на финальном
   выходе (462) перед `choices_missing` — тогда `ask_choices` не нужен. На ранних выходах (437/445) `offer_choices` уже
   принят — только вырезание (`choices_taken=True` режет и (г)). Посреди боя (журнал: «Твой ход продолжается…
   { "type": "offer_choices" …}») — вырезать, не применять.
6. `prompt.py:turn_data` — `"narration": cut_leaks(turn.narration, choices_taken=True)[0]` (прошлый ход: варианты
   списком — всегда мусор). Сейв и `memory.recent_turns` не меняются (решение 5/10). `summarizer`/`relevance`/`knowledge`
   читают `turn.narration` напрямую — вне шага (выжимка от мусора не страдает, вытеснение считается по промпту).
7. Проверка руками: `uv run pytest -q tests/unit/master tests/unit/protocol/test_schema.py`; ЖП4 — первые ходы, тег
   `leak_cleaned` в репортах, `narration` в `recent_turns` промпта чистая (журнал `calls-*`).

П2 — 106, 107, 109: бой, протокол, бюджет контекста (движок и конфиг, без правил героя).
1. 106 — `prompt.py:452` — `options` только в `combat_classify`; `turn.py:561` — убрать `combat_options=…`;
   `combat_flow.next_options` удалить (единственный вызов; `make dead`). Проверка: `test_master_prompt.py` — в
   `combat_narrate` ключа `options` нет; `test_static_budget` не задет (options — динамика).
2. 106 — `handlers/combat.py:end_combat` после проверки `is_over`: `enemies = [p for p in state.participants if p.side
   == "enemies"]`; нет ни одного с `status in ("fled", "surrendered")` → `rejected("бой идёт", "Враги не сдались и не
   бежали — бой продолжается, рассказывай по логу; end_combat — только после сдачи или бегства из лога.",
   report_tag="end_combat_refused")` (хелпер `rejected` — `handlers/world.py:25`). `EndCombat` docstring: «Завершить
   бой после сдачи или бегства врагов по логу (переговоры); пока враги дерутся — отклоняется.» narrator_rules.md:38 —
   добавить: «`end_combat` — только когда в логе враги сдались или ушли; при живых врагах его отклонят».
3. 107 — `requests.py:AdvanceTime`: `@field_validator("travel_to", mode="before")` — `"none"` → `""` (дальше
   `cut_neutral` даёт `None`); описание поля: «…пусто = нет (не "none")». Альтернатива — `NEUTRAL` с кортежем значений и
   правка `Request.cut_neutral` (requests.py:31–36) — шире, задевает параметризованный `test_requests.py:304`; не
   рекомендую.
4. 109 — `app_defaults.toml:136` — `gemini = 3.0` с комментарием «ЖП3: оценка/факт 1,23 по журналу drunk_dragon
   (calls-013)». Код не меняется (`cpt_for`, `prompt.py:243` уже по провайдеру роли). BACKLOG 77 (калибровка
   anthropic) — не закрывается, только gemini. Проверка: `test_app.py:661` — словарь по умолчанию с двумя ключами.

П3 — 103, 99, 100, 101, 108: ресурсы, данные героя, правила. Один замер статики в конце.
1. 103 — `resources.py:take_holder`: ветка `why == "spent"` → `(None, None)` до проверки держателя (комментарий:
   «кроме spent»); `holder_npc_id` при `spent` игнорируется. `requests.py:TakeItem`: `why` — «spent израсходован не
   применением (вылит, сожжён, сломан, уничтожен)»; `holder_npc_id` — «для сюжетных предметов при given/lost/stolen: id
   NPC в этой локации, у которого вещь оказалась (обязателен); при spent и для обычных предметов пусто».
   narrator_rules.md:88 — добавить: «Сюжетную вещь, которую герой уничтожил, вылил, сжёг или сломал, — `take_item`
   `why: spent` без держателя, в том же ходу; вернуть её потом нельзя. `lost`/`stolen`/`given` — только с `holder_npc_id`:
   вещь не может «пропасть в хаосе» без того, у кого она оказалась». Проверка: `test_take_item_holder.py` — тесты 113 и
   121 переписать под «кроме spent».
2. 99 — `prompt.py:sheet_data` после `favored_enemy`: `pools = hit_dice_pools(hero.creature)`; есть —
   `data["hit_dice"] = {"current": sum, "max": sum}`; нет — ключа нет. narrator_rules.md:108 — «… счётчик «Избранного
   врага» и остаток костей хитов `hit_dice` (`current`/`max`): в `rest` `short` `hit_dice` не больше `current`; при 0 —
   короткий отдых без лечения».
3. 100 — `resources.py:rest_redundant`: текст `signal` по «Правилам» выше; reason и тег прежние; поле в `hero_data` не
   добавлять (решение 2); правил не добавлять — сигнал приходит в том же ходу.
4. 101 — narrator_rules.md «Чего нельзя» (после 135 «Нельзя выдавать золото…»): «- NPC дал, протянул, вручил или оставил
   герою вещь — в том же ходу `give_item` (есть в `item_ids`) или `give_custom_item`; одного текста мало: без вызова вещи
   в инвентаре нет, и выпить, прочитать или применить её герой не сможет.» Строку 88 не трогать (её фразы держат
   `test_narrator_custom_item_rules.py`).
5. 108 — narrator_rules.md:72 (абзац `use_item`) — добавить: «Если зелье или эликсир герою даёт спутник или NPC (вливает
   раненому, протягивает) — в том же ходу `give_item` с id зелья и сразу `use_item`: движок применит эффект; без вызовов
   герой не лечится и в сознание не приходит». `UseItem` docstring: «Герой применяет расходник из инвентаря (сам или ему
   его дают): выпивает эликсир или зелье (вне боя).» Код не меняется: `give_item` + `use_item` уже работают подряд
   (лимит `consumables_per_scene` — на оба, resources.py:157/344). Альтернатива — поле `UseItem.by_npc_id` и инвентарь
   NPC — это Ж5 (у NPC нет инвентаря в сейве).
6. `test_static_budget`: замер; порог 20960 менять только при превышении, с причиной в шапке.

**mutmut:**
- П1: `ai_dm.master.session:cut_leaks` (новая), `ai_dm.master.session:MasterSession.finish`,
  `ai_dm.master.session:MasterSession.choices_allowed` (новая), `ai_dm.master.session:MasterSession.choices_missing`,
  `ai_dm.master.session:MasterSession.apply_leaked_choices` (новая), `ai_dm.master.prompt:turn_data`;
  TESTS=`tests/unit/master`.
- П2: `ai_dm.master.prompt:PromptBuilder.combat_data`, `ai_dm.protocol.handlers.combat:end_combat`,
  `ai_dm.protocol.requests:AdvanceTime.<валидатор>` (новый), `ai_dm.game.turn:TurnRunner.narrate_combat`; TESTS=`tests/unit/master/test_master_prompt.py tests/unit/protocol tests/unit/game`.
- П3: `ai_dm.protocol.handlers.resources:take_holder`, `ai_dm.protocol.handlers.resources:rest_redundant`,
  `ai_dm.master.prompt:PromptBuilder.sheet_data`; TESTS=`tests/unit/protocol tests/unit/master/test_master_hero_data.py`.

**Тестовые сценарии (кабан-доеба, TDD):**
П1, `cut_leaks` (образцы — из журнала, цитировать с заменой имён):
- текст + `\n\n{ "offer_choices": [ "А", "Б" ] }` → текст без JSON, choices `["А", "Б"]`;
- `{ "type": "offer_choices", "choices": [ "А", "Б", "В" ] }` → то же, 3 варианта;
- JSON с 1 или 4 вариантами → вырезан, choices `None`; оборванный `{ "offer_choices": [ "А",` → от `{` до конца, `None`;
- (б) «`offer_choices`\n- ["А", "Б"]» → строка и массив убраны, choices `["А", "Б"]`; «**offer_choices:**\n- А\n- Б» →
  убрано, choices `None`;
- (в) «**Подсказка по результатам:**\n- …\n\nОпиши ответ Лиры…\n\n---\n\nЛира осторожно…» → остаётся только «Лира
  осторожно…»; без `---` — убран только абзац-подсказка;
- (г) `choices_taken=True`, хвост «**Что ты решишь?**\n\n1. А\n2. Б» → список убран, вопрос остался;
  `choices_taken=False` → без изменений;
- (д) `<p><strong>Осталось флаконов: 1.</strong></p>` → «Осталось флаконов: 1.»; `<div>` не трогается;
- `LEAK_LINE` отдельной строкой и внутри абзаца → убрана, пустых двойных строк нет;
- рассказ с `{тайный знак}` и слово offer_choices в реплике без `{` и не отдельной строкой → без изменений, `None`;
- чистый текст → без изменений, `None`.
П1, `MasterSession.run` (образец `test_master_choices_ask.py`, `master_kit`):
- explore, текст с JSON-утечкой, вызова нет → `narration` без JSON, `offer_choices` в `accepted`, `session.offered_choices`
  = варианты, теги содержат `leak_cleaned`, нет `choices_retry`, адаптер вызван один раз;
- та же утечка + вызов `offer_choices` в ответе → JSON вырезан, второго `offer_choices` в `requests` нет;
- combat_narrate, бой не в `COMBAT_OVER` + утечка → вырезано, не применено, `offered_choices` пусты;
- combat_narrate, `victory` + утечка без вызова → применено;
- утечка с 1 вариантом, рассказ кончается вопросом → вырезано, дальше обычный `ask_choices` (`choices_retry`);
- роль `world`/summarizer: `finish` текст с `{ "offer_choices": … }` не трогает;
- `choices_missing` — прежние тесты зелёные после выноса `choices_allowed`;
- описание `offer_choices` без «последнем ответе»; `test_static_budget` зелёный.
П1, `turn_data`: ход с `narration` «…\n\n{ "offer_choices": […] }» → в данных промпта без JSON; `memory.recent_turns`
не изменился; ход с хвостовым списком → список убран.
П2:
- 106: `build(ctx, mode="combat_narrate")` при `ctx.combat_options = OPTIONS` → в `combat` нет ключа `options`;
  `combat_classify` — как было;
- 106: `end_combat` при всех врагах `active` → `rejected`, reason «бой идёт», тег `end_combat_refused`, `outcome`
  не менялся, `events` пусты; один враг `surrendered` → accepted, `ended_by_master`; один `fled` → accepted;
  враги мертвы, бой не окончен (`is_over` False) и прочие `active` → rejected;
- 107: `parse_request({"type": "advance_time", "travel_to": "none", "category": "minute"})` → `travel_to is None`,
  `category == "minute"`; `"forest"` — как было; `""` — как было;
- 109: `app().master.chars_per_token_by_provider == {"anthropic": 2.2, "gemini": 3.0}`; `cpt_for("gemini") == 3.0`;
  `cpt_for("openai") == 2.5`; слой пользователя с общим `chars_per_token` перекрывает оба (app.py:245 — старый тест).
П3:
- 103: `give_custom_item quest: true` → `take_item why=spent` без держателя → accepted, у героя 0, `custom_items[id].holder
  is None`, `lost_items_data` пуст, log «Израсходовано: …»; `spent` с `holder_npc_id` живого NPC → accepted, держатель
  не назначен; `given`/`lost`/`stolen` без держателя → `Invalid holder_required`; `qty` больше, чем есть → `clamped`;
- 99: следопыт 3-го уровня → `hero_data["hit_dice"] == {"current": 3, "max": 3}`; после `short_rest` с 1 костью →
  `current 2`; герой без пулов → ключа нет; правила содержат «`hit_dice`» и «не больше»;
- 100: отказ раньше кулдауна → `signal_to_master` содержит `clock_text(next_s)`, «короткий отдых», «advance_time»,
  «не восстанавливаются»; тег `rest_repeat`; на границе — accepted (старые тесты);
- 101: в «Чего нельзя» строка с `give_item`, `give_custom_item` и «одного текста мало»;
- 108: абзац `use_item` содержит «спутник или NPC», «`give_item`» и «`use_item`»; описание `UseItem` — «ему его дают»;
- Проверка руками (ЖП4): репорты с `leak_cleaned`; флакон `custom_19` — рассказчик списывает `spent`; сон раньше 12 ч —
  игрок видит время и «короткий отдых / подремать»; бой — вход `combat_narrate` без 6,5k options, `end_combat_refused`
  в репортах при попытке; `travel_to "none"` не даёт Invalid; `meta.context.estimate` к `api_tokens` ≈ 1,0–1,05,
  `dropped` короче.

**Развилки и риски:**
- 104, разбор JSON: `raw_decode` от якоря (рекомендую — обе формы и (б), без регулярок на вложенные скобки) против
  регулярки до последней `}`. Применение: синтетический `ToolCall` через `run_round` (рекомендую — путь модели, журнал,
  `requests`) против прямой записи `session.offered_choices`. Место: `finish` (единственная сборка `narration`, до
  `game/turn.py:461`) против `plain_text` (другие роли и UI-тесты).
- 104 (в): якорь «Подсказка по результатам» — модель сама сочинила себе инструкцию (в src строки нет); другая модель
  даст другой заголовок — тег покажет в ЖП4; расширять список якорей — беклог, не угадывать.
- 104 (г): режется только хвостовой блок и только при принятом `offer_choices`/в `turn_data`; список в середине
  рассказа (опись, перечень) не трогается.
- 104: после вырезания рассказ может стать короче `min_narration_chars` → `TurnFailed "short"` и повтор
  (`game/turn.py:480`). Ожидаемо — рассказ из одного JSON не рассказ.
- 104: `cut_leaks` на 8 ходов при каждой сборке промпта — регулярки по ~8×3k символов, незаметно.
- 103: потраченный предмет живёт в `custom_items` с `holder = None`, как «в обороте»; отметка «потрачен» — поле, М0.
- 106: переговоры ставят статусы сами (`combat/actions/parley.py:225` `surrendered`, 232 `fled`, 241 `side = "heroes"`),
  защита `end_combat` их не ломает: перешедший на сторону героя из `enemies` выпадает, остальные дерущиеся держат отказ
  — так и нужно. Все враги мертвы/перешли — бой кончает движок (`combat/end.py`), `end_combat` там `combat_already_over`.
- 106: без `options` рассказчик боя не знает, что доступно герою дальше — и не должен: ход героя классифицирует
  `combat_classify` с options.
- 107: валидатор на одно поле; «none» в других строковых полях (`holder_npc_id`, `target`) в репортах не встречался —
  не обобщать.
- 108: лечение через `give_item`+`use_item` при 0 HP — снимает ли движок «без сознания» при HP > 0 (`rules/death_saves`)
  — проверить при реализации; если нет — это BACKLOG 110/111 (бессознательный герой вне боя), не этот шаг.
- 109: недооценка опаснее переоценки — 3,0 вместо 3,08; `meta.context.overflow`/`raised` в ЖП4 покажут. Тесты
  `test_t60_models`/`test_game_commands` с `context_windows` не зависят от cpt.
- 100: «подремать» вторым `hour` подряд без дела отклоняет `time_repeat` (resources.py:814) — существующее правило;
  упрётся в ЖП4 — беклог.
- Статика: правил +5 строк ≈ +250–350 токенов, docstring −20; запас до STATIC_MAX ≈ 600 — впритык; при превышении
  поднять с причиной.

**Открытые вопросы:** нет — продуктовые развилки закрыты «Решениями» 1–11; технические выбраны выше с
обоснованием и альтернативой.

## Правки по ревью

П1 (104), 2026-10-20:
- Отступление кабана (принято мамой и свекровью): `cut_leaks` и хелперы — в новом `src/ai_dm/master/leaks.py`, не в
  `session.py` (иначе цикл импортов `session` ↔ `prompt`); `MARKED_LINE` перенесён туда же. mutmut-цели — `ai_dm.master.leaks:*`.
- `turn_data` зовёт `cut_leaks(..., choices_taken=True)` — нужно для сценария «хвостовой список убран»; допущение: честный
  хвостовой список прошлого хода без `offer_choices` тоже срежется из промпта (мама, п. 1).
- Мелочи мамы без правок кода (решение оркестратора, мама — «можно мержить»): аварийные `finish` (session.py 457/465) не
  применяют утечку; `HTML_TAG` без `re.I` — в журнале только нижний регистр.
- Аудит свекрови — чисто, решений за пользователя нет.

П2 (106, 107, 109), 2026-10-20:
- Ошибка оркестратора: в промпте доебе добавлен вариант `travel_to "None"` (с заглавной), которого нет в плане; отозван
  оркестратором, тест убран, код не менялся (свекровь подтвердила по диффу).
- Доеба вне плана (принято мамой и свекровью): хелпер `enemies_surrender` в `tests/unit/game/game_kit.py` (сдаётся первый
  враг — иначе бой кончится победой до рассказа); в `tests/scenarios/memory_script.py::memory_settings`
  `chars_per_token_by_provider = {}` — калибровка сценария памяти подобрана при 2.5, новый `gemini = 3.0` её сбивал;
  починены `test_zh1_survivors.py` (8) и `test_stage4_memory.py` (2, через `memory_script.py`, сам файл не менялся),
  которых не было в списке кабана.
- Мама, пп. 1–3 (доеба): тест «враг dead, остальные active → rejected»; проверка `reason == "бой идёт"`; проверка
  `category` в тесте `travel_to "none"` (тест на `""` уже был). П. 4 (кабан): в docstring `EndCombat` возвращено
  «(переговоры)» по плану, строка обёрнута под E501.
- Аудит свекрови — чисто, решений за пользователя нет; её мелочи совпали с пп. мамы.

П3 (103, 99, 100, 101, 108), 2026-10-20:
- Доеба по п. 6 плана: `STATIC_MAX` 20960 → 21620 (замер explore 20988 + 3 %, причина в шапке); свекровь — покрыто планом.
- Полный прогон (make cov) — 3 падения от нового `hit_dice` в данных героя, чинил доеба тестами (src не менялся):
  `hit_dice` в список полей `test_master_rules.py` (не инструмент); golden `tests/golden/k0_sheet_data_v4_dragon.json`
  дополнен `hit_dice`; `MEMORY_CONTEXT_CAP` в `tests/scenarios/memory_script.py` 2775 → 2800, по повтору мамы (край окна)
  → 2806 — середина рабочего окна ≈ 2780–2830 (2775 ломает `test_no_overflow_on_any_narrator_call`, 2838 —
  `test_every_stage_fires_somewhere`); окно узкое, следующая добавка в данные героя может снова его сдвинуть.
  Доеба при подборе дважды правил `memory_script.py` через `sed -i` (нарушение, итог внесён Edit).
- Мама: шапка `test_static_budget.py` — порядок записей, формулировка, комментарий над `STATIC_MAX` (доеба);
  `narrator_rules.md:108` — перечисление без двойного «и» (кабан). Убранное из сигнала отдыха время конца — по плану,
  без правок (решение оркестратора по плану).
- Аудит свекрови — чисто, решений за пользователя нет; «+3 %» — прежняя практика шапки, с пользователем отдельно не обсуждалось.

## Итог

П1 (104), 2026-10-20 — kaban/doeba/mama/svekrov на sonnet; токены: кабан 52k, доеба 52k + 47k (мутанты), мама 36k,
свекровь 35k, архитектор (ROADMAP) 54k. pytest 19564 passed, cov 97,93 %, dead чист, smells 201/200 — было 201 и до
партии (баланс нулевой, долг прошлых шагов). mutmut: 19 выживших → доеба убил 15, повтор подтвердил; эквивалентны 4 —
`cut_hints_12` (split по несуществующей строке: первая строка абзаца и абзац начинаются одинаково), `cut_name_lines_9`
(начальное значение всегда перезаписывается), `apply_leaked_choices_18/19` (id синтетического вызова не читается).

П2 (106, 107, 109), 2026-10-20 — kaban/doeba/mama/svekrov на sonnet; токены: кабан 46k (с правкой docstring), доеба 76k
(с правками по ревью) + 35k (мутанты), мама 33k, свекровь 35k (с повторами). pytest 19585 passed, 1 xfailed (до правок
тестов по ревью; затронутые файлы после правок — 375 passed), cov 97,44 %, dead чист, smells 200/200. mutmut: на новых
строках выжили только `x_end_combat_51–55` (текст `signal_to_master` отказа — шум, поведение проверено тегом и статусом);
`AdvanceTime.none_travel_is_empty` mutmut не мутирует (`@field_validator` + `@classmethod`), покрыт обычным тестом;
выжившие на старых строках — BACKLOG 112.

П3 (103, 99, 100, 101, 108), 2026-10-20 — kaban/doeba/mama/svekrov на sonnet; токены: кабан 52k (с правкой по ревью),
доеба 66k (с починкой полного прогона и правками по ревью) + 24k (мутанты), мама 38k, свекровь 44k (с двумя повторами).
make cov: 19602 passed, 1 xfailed, 3 failed (все от нового `hit_dice`, починены тестами — см. «Правки по ревью»; затронутые
файлы после правок — 4213 passed), cov 97,94 %, dead чист, smells 200/200. mutmut: на новых строках выживших нет;
`x_rest_redundant_25, 27, 28` — новый текст `signal_to_master` (шум); выжившие на старых строках — BACKLOG 113.

Стоимость шага (кабан-тесть, 2026-10-20). **Источник токенов:** `metrics.py`
`~/.claude/projects/-Users-vladislavahtamov-projects-ai-dm/8a2d8e64-4dfc-43cc-9e24-b760414ceaed.jsonl`;
**цены:** https://platform.claude.com/docs/en/about-claude/pricing, тариф 2026-10-17 (из `metrics.py`, тестем
повторно не сверены); fable — по цене Opus.

| Партия | Смета | Факт (токены из «Итога» партий) |
|---|---|---|
| Планирование | ≈ 320k (свинопас 165k, свекровь 40k, папа 92k, тесть 25k) | папа переписал план (ред. 2) — 3 запуска, 588 мин у последнего; свинопас 3,94 млн с кэшем |
| П1 (104) | ≈ 1,1–1,3 млн на 3 партии ≈ 0,4 млн | 222k + архитектор 54k |
| П2 (106, 107, 109) | ≈ 0,4 млн | 225k |
| П3 (103, 99, 100, 101, 108) | ≈ 0,4 млн | 224k |
| Итого партии | 1,1–1,3 млн | ≈ 0,67 млн (+ архитектор) — ниже сметы: партии на sonnet, правки ревью мелкие |

Расхождение «Итога» партий и `metrics.py`: в «Итоге» — пиковый контекст/вывод запуска, в `metrics.py` — сумма с
чтением кэша по всем вызовам (субагенты ≈ 21,9 млн, из них чтение кэша ≈ 20,1 млн).

| Роль | Модель | Токены (`metrics.py`, всего) | $ |
|---|---|---|---|
| papa-kaban | fable (по Opus) | 2 853 252 | 3,54 |
| svinopas | opus | 4 102 305 | 1,64 |
| kaban | sonnet | 1 367 729 | 0,87 |
| kaban-doeba | sonnet | 4 491 495 | 1,41 |
| mama-kaban | opus (груминг) / sonnet | 710 616 | 0,71 |
| kaban-svekrov | opus / sonnet | 1 075 754 | 1,02 |
| general-purpose (ресёрч) | sonnet | 7 138 171 | 1,27 |
| оркестратор | opus | 13 222 625 — на момент подсчёта 06:57 UTC | 5,57 — на момент подсчёта |
| kaban-test | opus | 201 641 — на момент подсчёта 06:57 UTC | 0,35 — на момент подсчёта |

**Итого:** смета 1,1–1,3 млн субагентских токенов (без $) → факт ≈ 0,67 млн по «Итогам» партий; по `metrics.py`
35,2 млн токенов (в основном чтение кэша), $16,37 на момент подсчёта, из них оркестратор $5,57 и папа $3,54.

правки: Edit 1 («Итог»), из bash 0

Разбор — кабан Декарта.
