# План партии «Б1-фикс» (papa-kaban, 2026-10-09; одобрен проектировщиком)

Задача: BACKLOG 35 пп. 1–5. Контекст и решения — docs/decisions/b1-live.md.

## Реализация (kaban)
1. п.1 — `src/ai_dm/master/session.py`: рядом с `SINGLE_SHOT_MODES` константа `FREE_TOOLS = ("offer_choices",)`.
   В `run()` после `run_round` (после ветки SINGLE_SHOT_MODES, до `messages.append`): если `self.role == "narrator"`,
   `not has_invalid`, все вызовы раунда (по `calls`) — из `FREE_TOOLS`, `accepted` непуст, `(required is None or required_done)`,
   и в `result.texts + texts` есть непустой текст → `result.texts += texts; return self.finish(result)`.
   Комментарий: «варианты предложены, рассказ уже есть — завершающий вызов не нужен». `stop_reason` не трогать;
   `empty_note`/`told`/ветку `max_tokens` не трогать. Golden/fixtures не меняются (offer_choices там без текста).
2. п.2 — `src/ai_dm/ui/session.py`: помощник `last_narration_block(app)` (Block narration или None по
   `recent_turns[-1].narration`), использовать в `start()` (поведение то же) и в `render_step`: для `/load`, если загрузка
   удалась и `reply.narration` пуст — блок рассказа после `reply_blocks`, до `screen_blocks`. Признак удачи — первая строка
   ответа начинается с `LOADED_PREFIX = "Загружено: "` (константа в `game/app.py`, использовать и в `GameApp.load`).
   Порядок: заметки → рассказ → меню → статус. Для hero_dead рассказ тоже показывать.
3. п.3 — `master/prompts/narrator_rules.md`, «Порядок работы»: строку «Не раскрывай игроку служебные данные…» заменить на:
   «Всё, что ты пишешь текстом, игрок увидит как рассказ, в том числе текст в одном ответе с вызовом инструмента. Не пиши
   туда рассуждений о выборе инструмента или механики: думай молча, текстом давай только повествование. Не раскрывай игроку
   служебные данные: названия инструментов, коды, внутренние числа движка.»
4. п.4 — там же, «Сюжетные предметы», к строке «Не превращай в предметы мелочи…» дописать: «Вещь, которой герой потом
   сможет воспользоваться (питьё, еда, лампа, верёвка, ключ), — не мелочь: если NPC её даёт, выдай инструментом (`give_item`,
   если она есть в `item_ids`, иначе `give_custom_item`); то, что выдано только рассказом, в инвентаре не появляется, и герой
   не сможет это выпить или применить.» К строке про `use_item` дописать: «Если такой вещи в инвентаре нет — не описывай,
   что герой её пьёт или применяет: её у него нет.»
5. п.5 — код не менять (цепочка проверена, в мир пришёл preset_id heroic, причина вне кода).
6. Docs: `docs/decisions/b1-live.md` — итог п.5 (следы: строка «Мир: …, пресет …» и chronicle kind=tone; вопрос пользователю:
   цифрой или кликом) и риск: «репорты/журналы до Б1-фикс не воспроизводятся через --replay на ходах текст+offer_choices».
   `docs/BACKLOG.md` п.35: пп.1–4 сделаны, п.5 — не воспроизведено.

## Тесты (kaban-doeba, TDD)
- п.1, tests/unit/master/test_master_session_loop.py (master_kit: ScriptedAdapter, tools_step, text_step):
  текст+offer_choices → 1 вызов, texts без дубля, второй шаг не потреблён; offer_choices без текста → затем text_step: 2 вызова;
  текст+offer_choices+set_flag → 2 вызова; offer_choices отклонён → 2 вызова, invalid_count как раньше;
  обязательный инструмент не выполнен / роль не narrator → ранний выход не срабатывает; SINGLE_SHOT_MODES (hero_sheet) — 1 вызов.
- п.2, tests/unit/ui/test_ui_session.py / test_session_play_branches.py: ход → save auto → `/load auto` → narration с текстом,
  порядок note … narration … menu … status; `/load` несуществующего слота → без narration; мёртвый герой → narration + меню
  hero_dead; существующие test_load_command_* зелёные; TUI (tests/unit/ui/tui/test_tui_entry_points.py, по образцу
  test_continued_world_shows_last_narration_in_the_feed) — после `/load auto` рассказ в #feed.
- пп.3–4, tests/unit/master/test_master_rules.py: фразы «рассужден», «думай молча»; «give_custom_item» рядом с «не мелочь»,
  «в инвентаре не появляется»; test_rules_mention_only_known_tools зелёный.
- п.5: PickerApp с реальными preset_label при size=(80,24): press 3 → 3, клик по пункту 3 (и по его перенесённой строке) → 3,
  press 2 → 2; tests/unit/ui/test_ui_cli.py: choose_preset 3 → "grim", 1 → None, 2 → "heroic".
