# Шаг 93 — Эффект стрелы «усыпление» (BACKLOG 93)

контур: вне msa; режим: встроить.

## Суть
У особых стрел пака drunk_dragon есть только `extra_damage`, `burn`, `slow` (`EffectType`, common.py:73–80; движок —
`attack.special_damage`/`attack.arrow_conditions`). Нужен эффект боеприпаса «сонный яд»: спасбросок Телосложения,
при провале цель отравлена и без сознания (SRD 5.2, яды). Затем временный `arrow_sleep` (+1d4 ядом + замедление)
в паке заменить настоящим. Без полей сейва, S, наполнитель (ROADMAP:81). Факты сверены по коду HEAD 812e7a1.

Ближайший аналог в коде — эффект при попадании у монстров `monster_traits.on_hit` / `HitRider` (models/monsters.py:9):
спасбросок → `engine.impose` состояния с `Expiry`, длительность `minute` = `MINUTE_ROUNDS` (10). Стрелы кладут
состояния/эффекты в `attack.arrow_conditions` (attack.py:429) после события атаки, до `downed.after_damage`.
Иммунитет к состоянию — `CombatEngine.impose` (engine.py:409, только `condition_immunities`). «Без сознания» сейчас
бывает только от 0 HP (`downed.add_unconscious`, source `"0_hp"`); вложенные состояния (несп., лежит) —
`IMPLIED_CONDITIONS` (rules/modifiers/conditions.py:20); несп. участник получает только `end_turn`
(available.py:490); преимущество/автокрит по спящему уже в `CONDITION_RULES`. Пробуждения от урона в коде нет.
Повторных спасбросков в конце хода в движке нет (rules-adaptation.md:118 — упрощение принято для `on_hit`).

## Решения (проектировщик)
2026-10-19: В4 — урон стрелы (1d4 ядом) оставить, `slow` убрать (сон его заменяет); В1–В3, В5–В11 — по рекомендациям
ниже (В1 отравлен+сон сразу, В2 СЛ 12, В3 1 мин = 10 раундов, В5 иммунные к яду/отравлению без броска, В6 и В10 в партию,
В7 проснувшийся prone, В8 id и сейв не трогать, В9 `conditions` в `combat_data`, В11 бой продолжается).

## План

**Задача:** новый тип эффекта предмета `sleep` (спасбросок Тел СЛ `dc`, провал — `poisoned` + `unconscious` на
`duration_s`), срабатывает у стрелы в `arrow_conditions`; «без сознания» не от 0 HP снимается любым уроном
(`downed.after_damage`); `arrow_sleep` в паке переписать на `sleep`.

**Правило:** было `arrow_conditions`: `if effect.type == "burn": … / if effect.type == "slow": …` (attack.py:431, 440)
→ станет ещё ветка `if effect.type == "sleep": sleep_arrow(engine, ref, target_ref, effect)`;
было `after_damage` сразу `if target_ref in engine.heroes: …` (downed.py:47) → станет первым
`wake_sleeping(engine, target_ref, dealt)` (снять `unconscious` с `source != "0_hp"` при `dealt.final > 0`).
Новое: `EffectType += "sleep"`, `EffectSpec.dc: int | None`.
**Поведение:** меняется — выстрел `arrow_sleep` больше не даёт +1d4 ядом и −10 фт (если В4 = убрать), а бросает
спасбросок цели; спящая цель не ищет скрытых героев (В6); остальное (атаки по спящему с преимуществом, автокрит в
ближнем бою, только `end_turn` в его ход) — уже работает через `IMPLIED_CONDITIONS`.
**Вне ai-dm:** нет. Живой сейв `saves/drunk_dragon-00000001` — см. В8 (правка не нужна, если id `arrow_sleep` остаётся).

### Файлы и функции — kaban (src, campaigns, docs)

1. `src/ai_dm/content/models/common.py` — `EffectType`: `"sleep"` в блоке «особые стрелы» после `"slow"`;
   `EffectSpec.dc: int | None = None` (комментарий «СЛ спасброска (sleep)»); в `EffectSpec.check_class_id`
   (common.py:181) или новым валидатором `check_sleep` (новая): `type == "sleep"` требует `dc` и `duration_s`.
   `effect.condition` для `sleep` не нужен — состояния фиксированы правилом (`poisoned`, `unconscious`).
2. `src/ai_dm/combat/actions/attack.py:arrow_conditions` (attack.py:429) — третья ветка `sleep` (охрана «цель на 0 HP —
   не накладываем» уже есть).
3. `src/ai_dm/combat/actions/attack.py:sleep_arrow` (новая), рядом с `arrow_conditions`:
   а) `poison_immune(engine, target_ref)` (новая, маленькая): монстр/NPC со статблоком, у которого `"poisoned"` в
      `condition_immunities` или `"poison"` в `damage_immunities` — лог `  <имя>: иммунитет к яду`, выход без броска (В5);
   б) `saved = engine.save(target_ref, "con", effect.dc)` (engine.py:256; строка броска в лог пишется там);
      успех — лог `  <имя> стряхивает сонный яд`, выход;
   в) провал — `rounds = effect.duration_s // engine.cfg.time.round_s` (как `rounds_to_seconds`, time_ops.py:5);
      `expires = Expiry(kind="rounds", value=rounds)`; `engine.impose(target_ref, AppliedCondition(id="poisoned",
      source=ref, expires=expires))`; по В1 — `impose(... id="unconscious", source=ref, expires=expires.model_copy())`
      (отдельный объект: `tick_rounds` мутирует `expires.value`); лог
      `  <имя>: отравлен, засыпает (без сознания до урона или N раундов)` — рассказчик читает именно лог (turn.py:466).
4. `src/ai_dm/combat/downed.py:wake_sleeping` (новая) + вызов первой строкой `after_damage` (downed.py:43): при
   `dealt.final > 0` снять с цели `unconscious` с `source != "0_hp"`, лог `  <имя> просыпается от боли`; `poisoned`
   остаётся. `after_damage` — единственная точка после любого урона (attack, burn, cast, falling, death_burst,
   improvise, mastery, move — 12 вызовов), поэтому хук общий; урон 0 от иммунитета не будит (SRD: «получает урон»).
   По В7 — здесь же `impose(prone, source=ref)`, чтобы проснувшийся лежал и вставал за перемещение (`stand_up`).
5. `src/ai_dm/combat/engine.py:CombatEngine.start_turn` (engine.py:367) — В6: `stealth.search` только если
   `"incapacitated" not in {c.id for c in with_implied(creature)}` (образец — `monster_traits.pack_ally`:22).
6. `src/ai_dm/game/sheet_text.py:effect_texts` (sheet_text.py:101) — `elif effect.type == "sleep":
   texts.append(f"сон: СЛ {effect.dc} Тел")`; длительность приклеится из `duration_s` («1 мин») существующим кодом.
7. `campaigns/drunk_dragon/content/items/arrow_sleep.yaml` — `effects: [{type: sleep, dc: <В2>, duration_s: <В3>}]`,
   `extra_damage`/`slow` — по В4; `description` переписать («Сонный яд Греты: спасбросок Телосложения, при провале цель
   отравлена и спит»). id не менять (В8).
8. По В9 (если «да») — `src/ai_dm/master/prompt.py:PromptBuilder.combat_data` (prompt.py:431): участнику добавить
   `"conditions": [c.id …]`, только когда список непуст (меньше токенов; `master_kit.py:52` — обновить комментарий).
9. По В10 (если «да») — `src/ai_dm/combat/end.py:settle_ground` (end.py:92, цикл по не-героям у 113–118): кроме
   `active_effects` снимать `conditions` с `expires.kind == "rounds"` — боевые сроки не живут вне боя.
10. Документы: `docs/rules-adaptation.md` — пункт после «Эффект при попадании» (:115–119): сонная стрела, иммунитет к
    яду, пробуждение уроном, срок в раундах, нет повторных спасбросков и «растолкать» (как у `on_hit`);
    `docs/ARCHITECTURE.md` у :1148 — `attack.arrow_conditions`/`sleep_arrow`, `downed.wake_sleeping`;
    `docs/BACKLOG.md` 93 → `docs/done/093-effekt-strely-usyplenie.md`; ROADMAP — архитектор.

### Тесты — kaban-doeba (tests/**), TDD
Место: `tests/unit/combat/test_dragon_arrows.py` (фикстура `dragon` — Грей из пака, реестр с добавочным монстром) или
новый `tests/unit/combat/test_sleep_arrow.py` на том же `combat_kit`; `ScriptedRng` задаёт d20 спасброска.
- `EffectSpec(type="sleep")` без `dc` или без `duration_s` → `ValidationError`; с обоими — ок; пак drunk_dragon грузится,
  у `arrow_sleep` эффект `sleep` (и нет `extra_damage`/`slow`, если В4 = убрать).
- Попадание сонной стрелой, спасбросок провален → у цели `poisoned` и `unconscious` (source = герой, `Expiry rounds N`);
  в логе строка спасброска, «отравлен, засыпает»; следующая атака героя по ней — с преимуществом (строка броска
  содержит «без сознания»); ближняя — автокрит.
- Спасбросок успешен → состояний нет, лог «стряхивает сонный яд». Промах → броска нет. Цель упала от урона стрелы
  (0 HP) → броска нет (охрана `arrow_conditions`).
- Скелет (`condition_immunities: [poisoned]`) → броска нет, лог «иммунитет к яду»; монстр с `damage_immunities: [poison]`
  без `poisoned` в иммунитетах — тоже (В5).
- Урон по спящему (атака, горение) → `unconscious` снят, `poisoned` остался, лог «просыпается»; урон 0 (иммунитет к
  типу) — не будит; по В7 — после пробуждения `prone`, в своём ходу встаёт (`move == 0`).
- Через N раундов (`tick_rounds`) оба состояния сняты; `expires` у них независимы.
- Ход спящего монстра: `available_actions` == [`end_turn`], `step()` без ошибок, по В6 — `stealth.search` не идёт
  (скрытый герой остаётся скрытым); спящий не союзник стаи (уже есть, не ломается).
- Бой со спящим единственным врагом не заканчивается (`outcome is None`) — фиксирует В11 (MVP).
- `effect_texts` → «сон: СЛ 12 Тел 1 мин» (`tests/unit/game/test_inv_*.py` — образец).
- По В9 — `combat_data` с `conditions` у участника; без состояний ключа нет (`tests/unit/master/test_master_prompt.py`).
- По В10 — после `conclude` у NPC нет состояний с `Expiry rounds`.
- Руками (живой прогон): Грей стреляет `arrow_sleep` — в логе боя спасбросок и «засыпает»; рассказчик описывает сон;
  `/inv` показывает «сон: СЛ 12 Тел 1 мин».

### mutmut — `make mutate FUNCS="…" TESTS="tests/unit/combat/test_dragon_arrows.py tests/unit/game"`
Существующие (grep ✓): `ai_dm.combat.actions.attack:arrow_conditions`, `ai_dm.combat.downed:after_damage`,
`ai_dm.content.models.common:EffectSpec.check_class_id` (если валидатор там), `ai_dm.game.sheet_text:effect_texts`,
`ai_dm.combat.engine:CombatEngine.start_turn` (В6), `ai_dm.combat.end:settle_ground` (В10),
`ai_dm.master.prompt:PromptBuilder.combat_data` (В9).
Новые: `ai_dm.combat.actions.attack:sleep_arrow`, `ai_dm.combat.actions.attack:poison_immune`,
`ai_dm.combat.downed:wake_sleeping`, `ai_dm.content.models.common:EffectSpec.check_sleep` (если отдельный).

## Правки по ревью
- Тесты нашли: стрела будила цель своим же уроном → `arrow_conditions` перенесён в `attack` после `downed.after_damage`
  (весь вызов, не только сон). Следствия (ревью mama-kaban): строки поджога/замедления в логе идут после «убит / без
  сознания»; монстр со стойкостью (`endures`, остаётся на 1 HP) теперь получает burn/slow и спасбросок от сна — по
  правилам вернее. Тест «стойкий монстр + стрела горения» — добавлен по ревью.
- `sleep_arrow` без параметра `ammo` (не нужен). Ревью — без блокирующих замечаний.

## Развилки и риски
- Тип эффекта: отдельный `sleep` (рекомендую: правило «яд → отравлен + сон, будит урон» специфично; один спасбросок
  на два состояния) против общего `save_condition` (ability/dc/condition) — потребовал бы список состояний и два броска
  или новое поле; «на будущее» для 92/94 не делаем, при надобности `sleep` — частный случай.
- СЛ в `dc` (как `HitRider.dc`), срок в `duration_s` (как эликсир; раунды = `// cfg.time.round_s`) — без новых полей
  длительности; альтернатива `value` как раунды отвергнута — `value` у `slow` уже «футы».
- Риск: длительность 1 мин у NPC переживёт бой (вне боя `Expiry rounds` не тикает) — то же у `on_hit minute`; В10.
- Риск: спящий враг с `status == "active"` держит бой открытым — В11; `end_combat` мастера есть.
- Риск: `expires` общий объект на два состояния — `tick_rounds` уменьшит дважды; копировать (п. 3в).
- Герои под сонную стрелу не попадают (боеприпасы только у героев: `available.ammo_options`) — спасброски смерти не
  задеты. SRD «растолкать действием» — не реализуем (нет такого действия), в rules-adaptation.
- Проснувшийся по SRD остаётся лежать; у нас `prone` — вложенное и уходит с `unconscious` (В7).

## Открытые вопросы (проектировщику; первый — блокирующий)
1. В1. Что при провале (`attack.py:429` `arrow_conditions`, новая `sleep_arrow`): (1) отравлен + без сознания сразу;
   (2) как яд дроу SRD: отравлен, а без сознания — только при провале на 5+ (`saved.total <= dc - 5`); рекомендую (1) —
   стрел 10, расходник уровня 1-го круга (Усыпление без спасброска), (2) почти не усыпляет; разблокирует п. 3в и тесты.
2. В2. СЛ: (1) 12; (2) 13 (яд дроу); (3) 11; рекомендую 12 — гоблин (Тел +0) спит ~55 %, волк/огр (+1/+3) реже.
3. В3. Срок: (1) 1 мин = 10 раундов (`duration_s: 60`, как `on_hit minute`); (2) до конца боя (большое число);
   рекомендую (1) — тот же срок обоим состояниям.
4. В4. Доп. урон: (1) убрать `extra_damage 1d4 poison` и `slow` — стрела только усыпляет (отличие от `arrow_poison`);
   (2) оставить 1d4 ядом; рекомендую (1), по SRD сонный яд урона не наносит.
5. В5. Иммунные: (1) `poisoned` в `condition_immunities` ИЛИ `poison` в `damage_immunities` — броска нет, лог
   «иммунитет к яду» (нежить, конструкты, элементали закрыты); (2) только `condition_immunities` через `impose`
   (тогда «без сознания» ляжет на скелета); рекомендую (1).
6. В6. Спящий враг не ищет скрытых героев (`engine.py:367` `start_turn` → `stealth.search`): (1) да, в партию;
   (2) оставить; рекомендую (1) — регресс в области шага, две строки.
7. В7. После пробуждения уроном цель лежит (`downed.py:43`, impose `prone`, source герой): (1) да — по SRD, встаёт за
   перемещение; (2) нет; рекомендую (1).
8. В8. Живой сейв `saves/drunk_dragon-00000001`: в `hero.json` только `item_id: arrow_sleep, qty: 10` — эффекты берутся
   из реестра пака, правка сейва не нужна при сохранении id; (1) id оставить, сейв не трогать; (2) новый id → правка
   сейва с бэкапом по согласию; рекомендую (1).
9. В9. Рассказчику (`prompt.py:421` `combat_data`): сейчас видит только строки лога («засыпает», «просыпается») и
   `status` участника; (1) добавить участникам `conditions` (когда непусто); (2) только лог; рекомендую (1) — иначе
   спящий в JSON выглядит как `active` боец.
10. В10. Снимать у не-героев состояния с `Expiry rounds` при `conclude` (`end.py:92` `settle_ground`): (1) да, в партию;
    (2) в бэклог; рекомендую (1) — иначе NPC уснёт до следующего боя.
11. В11. Все враги спят — бой: (1) продолжается (MVP; герой добивает/вяжет/мастер завершает `end_combat`);
    (2) считать несп. врагов не боеспособными в `set_outcome` → победа/плен — задевает трофеи и defeat, отдельный шаг;
    рекомендую (1), (2) — в бэклог при желании.

## Итог
- Закрыт BACKLOG 93 (карточка done/093). Старые выжившие мутанты → BACKLOG 98.
- Проверки: полный pytest 19502 passed, 3 skipped, 1 xfailed (59 мин); cov 98 %; smells 200/200; dead чист; ruff — 18
  прежних замечаний main. mutmut по 11 функциям: 88 выживших, на новых строках 6 — 3 закрыты тестами, 3 эквивалентны
  (`combat_data` `strict=` у `zip`).
- Ревью mama-kaban — без блокирующих (см. «Правки по ревью»).
- Ручная проверка: у Грея в пресете сонных стрел нет — только в живом сейве drunk_dragon-00000001 (id `arrow_sleep` не
  менялся, сейв не правился).
- Расход (токены субагентов): papa-kaban ≈ 120 тыс.; kaban (opus) ≈ 77 тыс.; kaban-doeba (opus) ≈ 105 тыс.; mama-kaban
  ≈ 29 тыс.; разбор мутантов kaban-doeba (sonnet) ≈ 44 тыс.
