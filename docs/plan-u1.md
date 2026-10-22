# У1 Атмосферные услуги (BACKLOG 32)

План — папа-кабан (ниже, после груминга).

## Решения

Груминг 2026-10-22 (свинопас ‖ кабан-свекровь, ответы проектировщика в окнах):

1. Эффект услуги проститутки — отдых + бонус (вариант «б» свинопаса; какой бонус — не выбран, развилка к папе).
2. Мир с `tone.romance: нет` — услуга есть, мастер проводит её за кадром.
3. Где NPC — пак `inn_test` + назначение мастером на ходу, и ещё в живых мирах (скрипт с бэкапом в шаге).
4. В `/shop` — отдельный вид услуги; `bed_hour` остаётся комнатой на час.
5. Цена — ответ вне вариантов: «разные проститутки — разные цены».
6. Память — ответ вне вариантов: «запоминает, но не как близость; если услугу покупают — потом нужно достигнуть
   отношения = 90 и больше, чтобы человек начал воспринимать это как роман».
7. Стрижка/бритьё — и описание (мастер учитывает новый вид героя), и бонус к следующей проверке Харизмы.
8. Состав шага — проститутка, стрижка/бритьё и ещё атмосферные услуги (баня, бард, гадалка — примеры свинопаса;
   состав и эффекты — развилки к папе).
9. Последствия услуги (болезнь, кража, слухи, ревность спутника) — механикой в У1.
10. Откровенность — по действующей шкале `tone.romance`, в абзац «Услуги» правил рассказчика — фраза-ссылка;
    правило ТЗ 3 не меняется.
11. Живой прогон — новый мир `inn_test --preset grim`.
12. Мастер назначает услугу любому NPC свободно, «по смыслу ремесла».
13. Пол NPC — через существующие `gender`/`pronouns`, без новых полей.

Аппрув плана 2026-10-22 (окна по плану папы):

14. Умолчания У1–У8 — приняты по одному (У7–У8 оркестратор свёл в одно окно — процесс проверки).
15. Р1 (вдохновение, не удваивать), Р2 (+1к4 к Харизме на сутки, стрижка 2 мд / бритьё 1 мд), Р3 (порог 90 стережёт
    движок) — по рекомендациям папы.
16. Р4 — ответ вне вариантов: «долго грязным ходить нельзя, иначе харизма уменьшается. Раз в неделю необходимо мыться.
    Если больше недели не мылся, то появляется доп. статус — вонь, и харизма идёт с помехой».
17. Р5а болезнь — СЛ: простая 10, обычная 5, дорогая — нет (вне вариантов по числам; помеха как «отравлен», храм — как в плане).
18. Р5б кража — СЛ: простая 12, обычная 7, дорогая — не крадут (размер потери не назван).
19. Р5в ревность — только влюблённые спутники, −10 и `betrayal`. Р5г слухи — только рассказ, репутация — в беклог.
20. Р5д `bed_hour` — 1 сп.
21. Р6 — бонусы в `/sheet` и в строке статуса.
22. Р7 — три класса компаньонов: 2 сп / 1 зм / 5 зм за час.
23. Р8–Р10 (редакция 2 плана) — по рекомендациям папы.
24. «Окей, кабаним» — 2026-10-22, смета ≈ $28,4 / ≈ 595 мин (редакция 2).
25. Экономия тестя: kaban и kaban-doeba — новые на каждую партию; правки по ревью внутри партии — тому же id.
    Разбор мутантов haiku — уже правило 7 AGENTS; слияние П4 с П3 — не берём (ревью партии не сокращаем).
26. 2026-10-23: BACKLOG 150–151 (записаны до сессии) — в коммит П1. 155–156 (одежда надевается; механика у каждого
    предмета — книга молитв, плащ «Снежный Призрак») — по вопросам проектировщика, в коммит П1.
27. 2026-10-23: «Действует:» в `/sheet` скрывает все `kind="modifier"` (правка кабана в `effects_line`) — «Оставить»
    (рекомендация мамы).
28. 2026-10-23: `make dead` — поля конфига под П2/П3 (`disease_dc`, `theft_dc`, `intimate`, `risks`, `romance_from`,
    `hygiene_days`) и `washed_at` — «Временно в allowlist»; снять в П2/П3, когда появятся читатели.

## Правки по ревью

**П1** (ревью мамы-кабана и аудит свекрови 2026-10-23):
- Строка эффекта в `/sheet` — «до 07:00, завтра» вместо примера плана «2-й день»; мама: понятнее игроку; при сроке
  > 1 дня — «через N дн.» (кабан, по ревью мамы); тест сравнивает строку целиком (доеба, по ревью мамы).
- `config/settings.py` не импортирует `rules.boons`: id бонусов — константой без зависимостей (кабан, по ревью мамы).
- `rules/inventory.py:effects_line` скрывает все `kind="modifier"` из «Действует:» — вне плана (кабан); мама: обосновано
  (бонус услуги не предмет реестра, Sap/Vex/боевые модификаторы срока в секундах не имеют); свекровь вынесла
  к решению — оставлено как техническое (оркестратор), сужать до BOONS не стали.
- Р9(б) (ночлег в удобной/богатой комнате снимает «вонь», решение 23) не попал ни в одну партию — делать в П3 вместе
  с гигиеной (находка свекрови; П3 — по плану партия гигиены).
- Гадание (`fortune`) в паке никто не даёт — назначает мастер; в шпаргалку прогона — «назначить гадание
  через `npc_update`» (мама).
- Риск для П3: `boon_effects` покажет любой эффект с id из `BOONS` — учесть, если в П3 появится эффект `washed` (мама).
- Мутанты: 184 выживших; на новых строках добито 8 тестами, 2 эквивалентных; старые строки — BACKLOG 157.
- Проверки: `make cov` 98,03 % (20964 passed, 1 xfailed, 39 мин), smells 199, `make dead` — после решения 28.
- Расход П1 (токены субагентов): kaban ≈ 112k (opus), doeba ≈ 127k (opus), мутанты doeba ≈ 56k (sonnet),
  мама ≈ 52k, свекровь ≈ 56k, папа (ROADMAP) ≈ 61k.

Груминг: отчёты свинопаса и аудита свекрови — в scratchpad сессии 2026-10-22 (не в репо).

## План (папа-кабан, 2026-10-22; редакция 2 — по решениям 14–22)

контур: вне msa; режим: встроить (образцы — У0: реестр `[services.kinds]`, диспетчер `handlers/services.py:service`
по `kind.effect`, состояние `cursed` П3; Sap/Vex — `ActiveEffect(kind="modifier", consume)` в `combat/mastery.py:24`;
дневной тик мира — `world_sim/tick.py:tick_days`).

**Задача / проект:** атмосферные услуги на реестре У0: компаньон(ка) трёх классов (отдых + вдохновение), стрижка/бритьё
(+1к4 к следующей проверке Харизмы на сутки), баня и гигиена (неделя без мытья → состояние «вонь», помеха на Харизму),
бард и гадалка (данные + правила); память NPC о платной близости и порог романа 90 движком; последствия (болезнь, кража,
ревность спутника) — механикой; живые миры — паком и скриптом.

**Правило:** (1) было `memory_kind == "romance"` пишется любому NPC без условий (`handlers/world.py:210
change_memory`) → станет: у NPC с флагом `paid_company:<npc_id>` при `npc.attitude < cfg.services.romance_from` (90)
событие `romance` переписывается в `deal` (`clamped`, лог «запомнит как сделку»), цель `love` на героя — `rejected`;
при ≥ 90 — как было. (2) было `effect: Literal["lodging","meal","heal","rest_short","cure"]` — эффект есть всё, что
делает услуга → станет `effect` (+ `"plain"`, только деньги) и ортогональные поля вида `boon` (бонус герою) и `risks`
(последствия). (3) было `EffectSource.modifiers` читает `creature.active_effects` целиком и знает цели
`attack_roll`/`saving_throw` (`rules/modifiers/effects.py:9,24`) → станет: только `live_effects(creature,
request.now_s)` и ещё цель `ability_check` (фильтр `ability` уже есть). (4) новое: проверки Харизмы героя не зависели
от времени с последнего мытья → станет: в дневном тике при `at − flags["washed:<hero>"] ≥ cfg.services.hygiene_days ×
DAY` (7) герою ставится состояние `smelly` («вонь»): `Rule("actor", ("check",), "disadvantage", abilities=("cha",))`;
снимает услуга с `boon = "washed"` (баня): флаг = `now_s`, состояние убирается.
**Поведение:** меняется — у NPC новые услуги (`/shop`, контекст мастера); после оплаты у героя бонус (строка броска,
`/sheet`, строка статуса — решение 21), запись в память NPC, возможные болезнь/потеря денег/реакция спутника; герой,
не мывшийся неделю, получает «вонь» (видно в `/sheet`, строке статуса, контексте мастера `hero.conditions`) — **это
касается всех миров, не только тех, где есть баня** (см. Р8); `romance` у «купленных» NPC до 90 не пишется;
`bed_hour` дорожает 5 см → 1 сп. Новых инструментов мастера нет (всё через `service`, `npc_update.services`).
**Вне ai-dm:** живые миры — новый NPC в `campaigns/drunk_dragon`/`dusk_academy` подхватит догрузка `merge_new` без
скрипта (прецедент: паром, докстринг `scripts/migrate_dusk_ferry.py`); услуги существующим NPC — только
`scripts/add_services.py` с бэкапом; каким мирам и NPC — вопрос 2 проектировщику. `dusk_academy` — школа (метка 18+
скриптом `migrate_dusk_18plus.py`): уместна ли там услуга — решает проектировщик. Гигиена в живых мирах: без бани в
мире «вонь» не снять — П4 обязана дать баню там, где включится тик (Р8).

### Расхождения для архитектора (из аудита; ROADMAP не правлю до аппрува)

- Строка У1 ROADMAP:99 без стрижки/бритья (решение 8 У0) и со ссылкой «п. 25.4» → предлагаю: «У1 Атмосферные услуги
  (BACKLOG 32 — компаньон(ка), стрижка/бритьё, баня и гигиена, бард/гадалка, память/порог романа, последствия;
  откровенность по пресету, BACKLOG 25 отв. 4) — R8 #11, д → M+, ≈ 1,8 — на реестре У0 — docs/plan-u1.md».
- `bed_hour` («У1 — проститутка», `plan-u0.md:153`) — по решению 4 комната на час, по решению 20 цена 1 сп (10 см).
- BACKLOG 32 остаётся `started` до У2 (наёмник) — в done/ после У1 не переносить.

### Разведка (проверено по коду)

- **Реестр и диспетчер.** `ServiceKind(extra="forbid")` (`config/settings.py:326`): `name, price_cp, unit, effect,
  heal, cures, description`; `service()` выбирает `heal_service`/`cure_service`/`pay_service` по `kind.effect`
  (`handlers/services.py`), `pay_service` — деньги + лог + `signal_to_master` для `lodging`/`rest_short`. Новые виды —
  данные; новые поля вида — конфиг, не схема сейва (v12 не трогаем, R8 п. 3).
- **Бонус «к следующей проверке» — механизм есть.** `ActiveEffect(kind="modifier", params={target, mode|dice,
  ability?, consume: True})` читается `EffectSource` (`modifiers/effects.py:42–60`) и снимается конвейером после
  броска (`roll_pipeline.py:240 consumes`). Не хватает: цели `ability_check` (`EFFECT_TARGETS`), фильтра истёкших по
  часам (`live_effects` есть в `rules/creatures.py:25`, `EffectSource` его не зовёт — истёкший `seconds`-эффект сейчас
  всё ещё действует: регресс-находка, чинится в П1), подписи (`source_label`, `roll_pipeline.py:287`, для не-реестровых
  источников отдаёт сырой id → `SOURCE_WORDS`). `dice` в `extra_terms` складывается положительным — «+1к4» безопасен.
  `request.now_s` у `skill_check` — передаётся (`checks.py`).
- **Вдохновение** — `hero.heroic_inspiration: bool` (`state/hero.py:201`), переброс в `roll_pipeline.py:127`, подпись
  «вдохновение»; ставится людям на долгом отдыхе (`rests.py:76`). Решение 15: бонус компаньона = оно.
- **Гигиена — тик есть.** `world_sim/tick.py:tick_days` идёт по дням от `sim.last_day + 1` до сегодня (смертность,
  hazard, события, сезон, год), зовётся на границе сцены (`game/boundary.py:103`) с `rng`; потолок
  `cfg.world.max_tick_days`. Состояние — `AppliedCondition` у героя (как `cursed`): показ `/sheet`/строка статуса
  (`sheet_text.py:285 condition_names`, `ui/screen.py:52`) и контекст мастера (`prompt.py:546 hero.conditions`) — без
  кода. Помеха только на Харизму — `Rule.abilities` работает и для `check` (`conditions.py:87 rule_matches`;
  `skill_check` ставит `ability = SKILLS[skill]`). Время последнего мытья — флаг мира `washed:<hero_id>` (int `now_s`;
  прецедент `lodging:<hero>`), поля не нужны.
- **Память и отношение.** `attitude` −100..100; мастер двигает ≤ `step` 10 за запрос и ≤ `per_scene` 20 за сцену
  (`defaults.toml:85`, `world.py:187 change_attitude`); виды памяти — открытый перечень `MEMORY_KINDS`
  (`relations.py:8`), `deal` есть; `romance` — тёплый вид, одно на сцену. Движок сам пишет только `battle`. Цель
  `love` — `GOAL_KINDS`. 90 = почти потолок (≥ 5 сцен максимального роста; на 100 — BACKLOG 144).
- **Состояния.** `cursed` П3 — образец: `srd/data/conditions/cursed.yaml` (`source: custom`), `CONDITION_RULES`
  (`modifiers/conditions.py`), снятие — `cure_service` по `kind.cures`.
- **Спутники и ревность.** Спутник = `npc.follows == hero.id` в локации героя (`prompt.py:539`); «любит» — активная
  цель `love` с `target` героя или `romance` в памяти. `change_attitude`/`remember` переиспользуемы из обработчика.
- **Слухи/репутация** — системы нет (grep пуст) → решение 19: только рассказ, репутация — беклог.
- **Тон.** `world.tone.romance` → контекст (`prompt.py:359`), шкала — `narrator_rules.md:152`; отказ провайдера —
  `turn.py:28`. Решение 2 — только текст правил.
- **Пак и живые миры.** `inn_test`: Брум (комнаты/еда), Ильда (`heal_temple`, `uncurse_temple`), Тобб (`heal_barber`);
  проверка id услуг пака — `campaign/loader.py:190 unknown_service_errors`. Живые миры: `drunk_dragon-00000001`
  (проектировщик), `dusk_academy-d3de6c57` (другой человек); `merge_new` добавляет новые сущности пака.
- **Тесты У0 как ориентир объёма:** 2114 строк в 5 файлах + `tests/scenarios/test_services_scenario.py`,
  `test_curse_scenario.py` (мок `ScriptedAdapter`).

### Модули / файлы / функции

Существующие (grep подтверждён): `config/settings.py: ServiceKind (326), ServicesConfig (351)`; `defaults.toml
[services.kinds]` (`bed_hour` → 10); `handlers/services.py: service, pay_service, paid, service_result, LOG_WORDS`;
`rules/services.py: kinds_of, quote, providers_here`; `rules/modifiers/effects.py: EFFECT_TARGETS,
EffectSource.modifiers`; `rules/roll_pipeline.py: SOURCE_WORDS, source_label`; `rules/modifiers/conditions.py:
CONDITION_RULES, CONDITION_WORDS`; `handlers/world.py: change_attitude (187), change_memory (210), memory_problem
(424), npc_update (453)`; `rules/npc_memory.py: remember, has_kind`; `rules/auto_flags.py: RESERVED_FLAG_PREFIXES`;
`rules/money.py: spend_money`; `rules/checks.py: saving_throw`; `world_sim/tick.py: tick_days`; `game/sheet_text.py:
condition_names, sheet_stat_lines`; `ui/screen.py: status_line`; `game/shop_text.py: service_lines`;
`master/prompt.py: services_data, provider_data`; `master/prompts/narrator_rules.md` абзацы «Услуги» (:106), «Тон»
(:149); `campaigns/inn_test/npcs.yaml`, `locations.yaml`.
Новые: `rules/boons.py` — **новая**: `BOONS` (id → спецификация), `grant_boon(ctx, boon_id, npc)` (`groomed` →
`ActiveEffect`; `inspired` → `hero.heroic_inspiration = True`; `washed` → флаг `washed:<hero>` = `now_s` + снять
`smelly`); `rules/hygiene.py` — **новая**: `WASHED_FLAG`, `washed_at(world, hero_id)`, `is_stale(world, hero, cfg,
at)`, `mark_washed(world, hero, now_s)`; `world_sim/hygiene.py` — **новая**: `roll_day(bundle, cfg, at)` (ставит
`smelly`, пишет запись хроники); `rules/consequences.py` — **новая**: `disease_check(ctx, kind, npc)`,
`theft_check(ctx, kind, npc)`, `jealousy(ctx, npc)`; `handlers/services.py: boon_and_risks(ctx, npc, kind, decision)`
— **новая** (из `service` после принятого `pay_service`); `handlers/services.py: remember_deal(ctx, npc, kind)` —
**новая**; `handlers/world.py: romance_gate(ctx, npc, request)` — **новая** (в `change_memory` и для `goal_kind ==
"love"`); `game/sheet_text.py: effect_lines(hero, now_s)` — **новая** (Р6); `srd/data/conditions/diseased.yaml`,
`smelly.yaml` — **новые**; `scripts/add_services.py` — **новый** (П4; по образцу `migrate_dusk_ferry.py`: stdlib,
гейт схемы, бэкап слота, идемпотентность).

### Конфиг (по решениям 15–22; `bath`, `bard_song`, `fortune` — Р9)

```toml
[services]
romance_from = 90        # решение 6/15: ниже -- romance у «купленного» NPC пишется как deal, love-цель отклоняется
hygiene_days = 7         # решение 16: столько дней без мытья -> состояние smelly
[services.kinds.bed_hour]           # price_cp = 10 (решение 20), остальное как было
[services.kinds.companion_cheap]    # name = "компания на час (простая)", unit = "hour", effect = "rest_short",
                                    # boon = "inspired", intimate = true, price_cp = 20, risks = {disease_dc = 10, theft_dc = 12}
[services.kinds.companion_common]   # "компания на час (обычная)", price_cp = 100, risks = {disease_dc = 5, theft_dc = 7}
[services.kinds.companion_fine]     # "компания на час (куртизанка/куртизан)", price_cp = 500, risks = {} (нет)
[services.kinds.haircut]            # "стрижка", effect = "plain", boon = "groomed", unit = "once", price_cp = 2
[services.kinds.shave]              # "бритьё", effect = "plain", boon = "groomed", price_cp = 1
[services.kinds.bath]               # "баня", effect = "plain", boon = "washed", price_cp = 10 (Р9: цена -- предложение)
[services.kinds.bard_song]          # "песня барда", effect = "plain", price_cp = 10 (Р9)
[services.kinds.fortune]            # "гадание", effect = "plain", price_cp = 50 (Р9)
```
`ServiceKind`: `effect += "plain"`; `boon: str = ""` (валидатор: id из `BOONS`); `intimate: bool = False`;
`risks: ServiceRisks = ServiceRisks()` (`disease_dc: int = 0`, `theft_dc: int = 0`; 0 = нет). `LOG_WORDS["plain"] =
"Оплачено"`. Бонус `groomed`: `ActiveEffect(id="groomed", source="service:<npc>", kind="modifier", params={"target":
"ability_check", "ability": "cha", "dice": "1d4", "consume": True}, expires=Expiry("seconds", now_s + 86400))`; при
живом бонусе того же id повторная покупка — деньги берём, бонус не удваиваем, лог «бонус уже действует» (решение 15);
`inspired` при `heroic_inspiration == True` — так же. Флаги `paid_company:<npc_id>` (bool), `washed:<hero_id>` (int) →
`RESERVED_FLAG_PREFIXES`.

### Партии

**П1 — каталог, бонусы, показ** (решения 7, 8, 12, 13, 15, 20, 21, 22):
1. `settings.py`/`defaults.toml` — поля `boon`, `intimate`, `risks`, `effect = "plain"`, `romance_from`,
   `hygiene_days`; виды из таблицы; `bed_hour` = 10; тест конфига (неизвестный `boon` → ошибка загрузки).
2. `rules/boons.py` — `BOONS`, `grant_boon` (`groomed`, `inspired`; `washed` — ставит флаг, снятие `smelly` — П3);
   `rules/hygiene.py` — флаг и `mark_washed`; `modifiers/effects.py` — `EFFECT_TARGETS["ability_check"] = ("check",)`,
   фильтр `live_effects(creature, request.now_s)`; `roll_pipeline.source_label` — `SOURCE_WORDS.get(source)` до сырого
   id; подпись «ухожен». Регресс конвейера бросков — `tests/unit/rules/test_modifiers.py`, `test_roll_pipeline.py` целиком.
3. `handlers/services.py` — `pay_service` принимает `plain`; `boon_and_risks` в П1 выдаёт только бонус
   (`result["boon"]`, лог «Бонус: …», `signal_to_master`); сигнал `rest_short` прежний.
4. Показ (решение 21): `/sheet` — строка «Эффекты: ухожен (до 07:00, 2-й день); вдохновение» из `live_effects` +
   `heroic_inspiration` (`effect_lines`, рядом с состояниями); строка статуса — «· ухожен», «· вдохновение» после
   состояний (`status_line`).
5. `narrator_rules.md` абзац «Услуги»: стрижка — учитывать новый вид героя; компания — описание по `tone.romance`,
   при `нет` — одной фразой за кадром (решения 2, 10); баня — герой чист (гигиена — П3); бард — после оплаты слух
   `knowledge_note rumor`; гадалка — намёк на ближайшую нить, секреты не раскрывать; услугу назначать по смыслу ремесла,
   пол — по `gender` (12, 13).
6. `inn_test/npcs.yaml`: Тобб += `haircut`, `shave`; новые NPC в «Медном котле» — компаньонка «простая» и компаньон
   «обычный» (`gender` разный), куртизанка — назначает мастер (проверка решения 12); баня — услуга `bath` у Брума
   (банька при трактире, `locations.yaml` описание); бард — NPC в зале (У4). `make prompt-budget` до/после.

**П2 — память и порог романа** (решения 6, 15):
1. `handlers/services.py: remember_deal` — после принятой покупки `intimate`: флаг `paid_company:<npc_id>`, событие
   `deal` в память NPC (одно на сцену через `has_kind`, текст «купил(а) услугу: <name>»), лог.
2. `handlers/world.py: romance_gate` — в `change_memory`: флаг стоит и `attitude < romance_from` → `memory_kind` →
   `deal`, `clamped`, `report_tag="paid_not_romance"`, сигнал «для NPC это сделка, роман — при отношении ≥ 90»;
   `goal_kind == "love"` с целью-героем у такого NPC ниже 90 → `rejected` тем же кодом (У5).
3. `narrator_rules.md` — фраза: платная близость — не роман; память пишет движок (`deal`), `romance` — после 90.
4. Мок-сценарий `tests/scenarios/test_company_scenario.py`: покупка → флаг и `deal`; `romance` при 40 → `deal`;
   при 90 → `romance`.

**П3 — состояния и последствия** (решения 9, 16–19):
1. `srd/data/conditions/diseased.yaml` («Болен»), `smelly.yaml` («Вонь»), оба `source: custom`;
   `CONDITION_RULES["diseased"]` = как `poisoned` (решение 17), `CONDITION_RULES["smelly"]` = помеха на `check` с
   `abilities=("cha",)`; `CONDITION_WORDS` «болен», «вонь»; `uncurse_temple.cures += ["diseased"]` (У6);
   `test_srd_minimum` — счёт custom-состояний, как в П3 У0.
2. `world_sim/hygiene.py: roll_day` — в цикле `tick_days` после `hazard`: герой жив, флага `washed` нет → поставить
   `= at` (отсчёт с первого тика, Р8-б); `at − washed ≥ hygiene_days × DAY` и `smelly` нет → `AppliedCondition(
   "smelly", source="hygiene")`, запись хроники «Герой неделю не мылся — от него несёт». `grant_boon("washed")` —
   `mark_washed` + снять `smelly`, лог «Герой вымылся». Старые миры: флага нет → отсчёт с первого тика после обновления.
3. `rules/consequences.py`: `disease_check` — спасбросок Телосложения СЛ `risks.disease_dc` через `checks.saving_throw`
   (строка броска видна игроку), провал → `AppliedCondition("diseased", source="service:<npc_id>")`, событие
   `diseased`; `theft_check` — спасбросок Мудрости СЛ `theft_dc`, провал → `spend_money` на `1к4 × 10 %` кошелька, не
   больше 10 зм (**размер не утверждён — рекомендация папы, решение 18**), лог «Кошелёк полегчал на …»; `jealousy` —
   для NPC с `follows == hero.id` в локации с активной целью `love` на героя или `romance` в памяти: `change_attitude`
   −`attitude.step` (10) и событие `betrayal` («измена»), лог и сигнал мастеру (решение 19). Только для `intimate`;
   порядок: ревность → кража → болезнь; `result["consequences"]`; `qty` > 1 — проверки один раз за покупку.
4. `handlers/services.py: boon_and_risks` — зовёт последствия после бонуса.
5. `narrator_rules.md`: последствия объявляет движок логом, мастер описывает по факту (кражу герой замечает сразу или
   позже — по тексту мастера, деньги уже списаны); слухи — только рассказ (решение 19); «вонь» — NPC морщатся, помеха
   на Харизму уже в бросках, снимает баня.
6. Мок-сценарии: покупка с сидом провала → `diseased` в `/sheet`, деньги −; спутница с `love` → отношение −10, память
   `betrayal`; храм снимает болезнь; `advance_time` на 8 дней + граница сцены → `smelly`, Убеждение с помехой «вонь»,
   `service bath` → чисто.

**П4 — живые миры** (решение 3; после живого прогона П1–П3, по списку проектировщика — вопрос 2):
новые NPC — в `npcs.yaml` паков `drunk_dragon`/`dusk_academy` (догрузка `merge_new`, скрипт не нужен); услуги
существующим NPC (в том числе `bath` — обязательно, раз тик гигиены общий) — `scripts/add_services.py <мир>
<npc_id>=<kind,…>` + `docs/migrate-services.md`; запуск — только проектировщик, бэкап слота.

Порядок: П1 → П2 → П3 (П2 и П3 независимы, взаимозаменяемы); живой прогон `inn_test --preset grim` (решение 11) —
после П3; П4 — после прогона. Каждая партия — своё ревью и замер `prompt_budget`.

### Тестовые сценарии (кабан-доеба, TDD)

- Конфиг: вид с `boon = "nope"` → ошибка; `effect = "plain"` грузится; `risks` по умолчанию нули; `romance_from = 90`,
  `hygiene_days = 7`; `bed_hour.price_cp == 10`; классы компаньонов 20 / 100 / 500, стрижка 2, бритьё 1.
- `service buy haircut` → деньги −2, `ActiveEffect(id="groomed")` с `expires.seconds = now + 86400`, лог «Бонус:
  ухожен»; `skill_check persuasion` → в строке броска «+1к4 (ухожен)», эффект снят; `skill_check athletics` → бонуса
  нет, эффект остаётся; часы > срока → `live_effects` пуст, бонус не применяется; повторная стрижка при живом бонусе →
  деньги списаны, второго эффекта нет, лог «уже действует».
- `service buy companion_common` → сигнал `rest short`, `heroic_inspiration == True`; уже было → лог «уже
  воодушевлён», деньги списаны; флаг `paid_company:<npc>`; в памяти NPC `deal` (вторая покупка в сцене — без дубля).
- `npc_update memory_kind=romance` у NPC с флагом и `attitude` 40 → `clamped paid_not_romance`, в памяти `deal`;
  `goal_kind=love` → `rejected`; `attitude` 90 → `romance` и `love` проходят; NPC без флага при 40 → как раньше.
- Последствия: `companion_cheap`, сид провала Кон (СЛ 10) → `conditions == ["diseased"]`, атака и проверка с помехой
  «болен»; `companion_fine` → бросков нет; успех → чисто; провал Муд (СЛ 12) → деньги −1к4×10 % (≤ 1000 см), лог;
  спутник с `love` → `attitude −10`, память `betrayal`, сигнал; спутник без `love`/`romance` → ничего; спутник в
  другой локации → ничего; `uncurse_temple` снимает `diseased` (и `cursed` разом, одна цена).
- Гигиена: новый мир, флага нет → первый тик ставит `washed = at`, состояния нет; `tick_days` через 6 дней → нет; через
  7 → `smelly`, хроника; Убеждение/Обман → помеха «вонь», Атлетика → нет; `service bath` → флаг = `now_s`, `smelly`
  снят, лог; `rest long` «вонь» не трогает; `max_tick_days` прокрутка 30 дней → одно состояние, не 24; `/sheet` и
  строка статуса показывают «вонь»; контекст мастера `hero.conditions` содержит `smelly`.
- Показ (решение 21): `/sheet` «Эффекты: ухожен (до …); вдохновение»; строка статуса «HP … · ухожен · вдохновение»;
  без эффектов — строк нет (регресс `status_line`).
- Контекст: ключ `services` у новых NPC с `description`; `prompt_budget` ≤ порог + N (N в Итог); `/shop` показывает
  «компания на час (простая) — 2 сп / час», «баня — 1 сп / раз».
- `EffectSource` с истёкшим `seconds`-эффектом → модификатора нет; с `now_s=None` → как раньше (регресс Sap/Vex в бою).
- Руками (`inn_test --preset grim`): `/shop` в трактире — компания двух классов и баня; покупка → сцена по тону, отдых,
  вдохновение в следующем броске; `/tone romance нет` → одной фразой за кадром; цирюльник — стрижка, мастер описывает
  вид; спутница (назначить `follows` + `love` через мастера) → ревность; храм лечит болезнь; неделя в лесу → «вонь» в
  строке статуса, баня снимает; отказ модели — текст `turn.py:28`.

### Развилки (новые, по решению 16; решает проектировщик)

- **Р8 — отсчёт «недели без мытья» и кого он касается.** Тика по часам нет, есть дневной тик мира на границе сцены
  (`tick_days`) — проверка там: (а) считать от начала мира: герой «вымыт» в день создания, старые миры — флаг ставится
  в день первого тика после обновления (без ретро-вони); (б) то же, но в мирах без NPC с `bath` тик не работает (нечем
  снять) — проверка `any(kind.boon == "washed" for provider in world.npcs)`; (в) тик только при `cfg.services.hygiene_days
  > 0`, умолчание 7 — выключатель для миров без бани через конфиг. Рекомендую (а) + (в): простое правило, старые миры
  не наказываются; П4 даёт баню живым мирам до того, как у них накопится неделя. Видимое: проверка идёт на границе
  сцены, а не в момент истечения недели — в длинной сцене вонь появится с опозданием до конца сцены.
- **Р9 — что ещё снимает вонь и состав атмосферных.** Снятие: (а) только баня (`boon = "washed"`); (б) ещё ночлег в
  удобной/богатой комнате (`room_comfortable`, `room_wealthy` получают `boon = "washed"` — «комната с лоханью»);
  (в) ещё купание в реке/озере — мастеру нужен инструмент или флаг, в У1 нет → беклог. Рекомендую (а) + (б): без (б)
  городской герой, живущий в богатой комнате, воняет, пока не найдёт баню. Состав сверх бани: решение 16 ответило
  только про гигиену — бард и гадалка остаются? (1) да, на данных и правилах (кода нет; цены 1 сп / 5 сп —
  предложение); (2) нет, только компания, стрижка/бритьё, баня. Рекомендую (1). Цена бани 1 сп — предложение.
- **Р10 — сила «вони» и порог.** Решение 16 — помеха на Харизму; (а) все проверки Харизмы (Убеждение, Обман,
  Запугивание, Выступление) — так читаю решение; (б) кроме Запугивания (вонь не мешает пугать). Рекомендую (а) —
  буквально. Порог — ровно 7 дней (`hygiene_days`, число в конфиге); бой/отдых не влияют.
- **Риски.** Отказ провайдера при `откровенно` (BACKLOG 25 открыт) — ловится прогоном; мастер может дать
  `companion_*` ключевому NPC (решение 12 — свободно) — видно в прогоне; фильтр `now_s` в `EffectSource` — регресс для
  эффектов с `seconds` (в `cast.py` — `concentration`, не задето), прогнать `tests/unit/rules` целиком; `explore` без
  новых инструментов — бюджет растёт только на абзац правил; `qty` > 1 у компаньона — отдых один, последствия раз;
  `inn_test` растёт до 6–7 NPC — `prompt_budget`; «вонь» — первое состояние, которое движок ставит всем мирам по
  времени: живые миры без бани (П4 ещё не было) могут получить его на первом же прогоне после недели пути — (в) Р8
  или П4 раньше прогона живых миров; `tick_days` потолок `max_tick_days` — при прокрутке месяца состояние одно.

### Умолчания (внутреннее)

- У1. Имена: `boon`, `intimate`, `risks` (`disease_dc`, `theft_dc`), `effect = "plain"`, `romance_from`,
  `hygiene_days`; бонусы `groomed` («ухожен»), `inspired` («вдохновение»), `washed`; состояния `diseased` («болен»),
  `smelly` («вонь», `source = "hygiene"`); флаги `paid_company:<npc_id>`, `washed:<hero_id>`; коды `paid_not_romance`,
  `boon_active`; события `diseased`, `robbed`, `smelly`, `washed`; источник эффекта/состояния `service:<npc_id>`.
- У2. Срок `groomed` — `Expiry(kind="seconds", value=now_s + 86400)`; проверка истечения — в `EffectSource` и в
  показе; чистки по таймеру нет (как у `lodging_paid`).
- У3. Последствия и бонус — в `result`/`log`/`signal_to_master` одного `Decision` (`clamped` не используем: покупка
  исполнена целиком); спасброски — через `checks.saving_throw` с `decisions`, строка броска в логе хода.
- У4. Пак `inn_test`: компаньонка «простая» и компаньон «обычный» в «Медном котле», баня — услуга у Брума (описание
  локации дополняется), бард — NPC в зале; описания видов — в `description`.
- У5. `love`-цель мастера на героя у NPC с флагом ниже 90 → `rejected paid_not_romance`; цели NPC→NPC не трогаем.
- У6. Болезнь снимает `uncurse_temple` (`cures += diseased`, цена та же, имя вида — «обряд очищения»); `heal_*` не
  лечат; долгий отдых — нет (как `cursed`). Вонь снимает только `boon = "washed"` (Р9).
- У7. Тесты: `tests/unit/rules/test_boons.py`, `test_hygiene.py`, `test_consequences.py`, `tests/unit/world_sim/
  test_hygiene_tick.py`, `tests/unit/rules/test_modifiers.py` (+ `ability_check`, `live_effects`, `smelly`),
  `tests/unit/protocol/test_apply_service.py` (+ `plain`, бонус, последствия), `test_npc_update_memory.py` (гейт),
  `tests/unit/game/test_sheet_effects.py` (новый), `tests/unit/config/test_services_config.py`; mutmut `FUNCS`:
  `rules.boons:grant_boon`, `rules.hygiene:is_stale`, `rules.hygiene:mark_washed`, `world_sim.hygiene:roll_day`,
  `world_sim.tick:tick_days`, `rules.consequences:disease_check`, `rules.consequences:theft_check`,
  `rules.consequences:jealousy`, `handlers.services:boon_and_risks`, `handlers.services:remember_deal`,
  `handlers.services:pay_service`, `handlers.world:romance_gate`, `handlers.world:change_memory`,
  `rules.modifiers.effects:EffectSource.modifiers`, `rules.roll_pipeline:source_label`, `sheet_text:effect_lines`,
  `screen:status_line`.
- У8. `make prompt-budget` до/после каждой партии — в Итог.

### Оценка и деление

Пять новых механик (решения 1, 7, 9, 16 и порог 90) — «д, 0,3» не держится. По образцу У0 (П1 ≈ 0,8–0,9 M,
П3-проклятие ≈ 0,4–0,5 M): П1 ≈ 0,6–0,7 M (данные + бонусы + показ в двух местах), П2 ≈ 0,3–0,4 M, П3 ≈ 0,6–0,7 M
(два состояния, тик мира, три последствия), П4 ≈ 0,2 M → ≈ 1,7–2,0 M токенов конвейера, размер M+ (как У0 с
проклятием). Делить на шаги не рекомендую: тесть по У0 — деление денег не экономит; механики ложатся в один реестр и
один обработчик, П2/П3 без П1 не проверить. Гигиена — единственная часть, которая меняет все миры (тик), поэтому П3 идёт
последней и перед живым прогоном; если проектировщик захочет вынести её — отдельная партия «П3б гигиена» внутри шага,
не отдельный шаг.

### Открытые вопросы

1. Р8–Р10 — выбор проектировщика до старта П3 (П1 и П2 от них не зависят; П1 п. 6 — баня в паке — от Р9 состава).
   Решает проектировщик. Не блокирует П1, кроме Р9 (бард/гадалка в данных пака и правилах).
2. П4: какие живые миры и NPC получают услуги (новый NPC-компаньон в `drunk_dragon`? услуги Гроку, баня?
   `dusk_academy` — школа, уместно ли) — список от проектировщика после живого прогона; без списка П4 не стартует.
   При Р8 = (а) без (в) баня живым мирам нужна до того, как в них накопится неделя.

### Побочные находки (в беклог, после аппрува — оркестратору)

- `EffectSource.modifiers` не фильтрует истёкшие по часам эффекты (`live_effects` не зовётся) — чинится в П1; если
  П1 отложат — пункт беклога.
- Репутация/слухи о герое в поселении — системы нет (решение 19): пункт беклога, связь с 29 (кто есть в поселении), 20.
- Отложенные эффекты вне боя (болезнь «к утру», инкубация) — тика по часам у состояний героя нет, есть только дневной
  тик на границе сцены; при желании «реалистичной» задержки — пункт беклога (связь ДН, BACKLOG 36).
- Купание в реке/озере как снятие «вони» без услуги — мастеру нужен инструмент или флаг (Р9-в) — пункт беклога.
- `source_label` для не-реестровых источников отдаёт сырой id в строке броска (`roll_pipeline.py:287`) — чинится в П1.

## Смета (кабан-тесть, режим 1)

Редакция 2 плана, 2026-10-22. Платного нового нет: подписок, хостинга, БД и зависимостей план не добавляет; живой
прогон `inn_test --preset grim` — вызовы API рассказчика за счёт пользователя, в смету цепочки не входят. Токены по ролям —
из «Итога» `docs/plan-u0.md` (50,35 M / $22,39), умноженного на объём: У1 ≈ 1,7–2,0 M токенов плана против У0 ≈ 1,4–1,5 M →
коэффициент ≈ 1,3; у mama-kaban — 1,4 (четыре ревью вместо трёх). Модели — `model:` из `~/.claude/agents/<роль>.md`.
$ — тариф metrics.py от 2026-10-17 (https://platform.claude.com/docs/en/about-claude/pricing), страницу не сверял;
fable — по ценам Opus; $/токен — средний по факту У0 для роли (та же доля кэш-чтения).

| Партия | Время |
|---|---|
| груминг + план + редакция 2 | ≈ 130 мин (уже прошло: два круга окон, 23 решения) |
| П1 каталог, бонусы, показ | ≈ 130 мин (как П1 У0) |
| П2 память и порог 90 | ≈ 85 мин (как П2 У0) |
| П3 состояния, последствия, гигиена | ≈ 200 мин (как П3 У0 с mutmut; 17 функций в FUNCS) |
| живой прогон | время пользователя, вне сметы |
| П4 живые миры | ≈ 50 мин (скрипт + документ) |
| итого | ≈ 595 мин без ожидания пользователя |

| Роль | Модель | Токены | $ (тариф metrics.py 2026-10-17) |
|---|---|---|---|
| оркестратор | opus | ≈ 21,9 M | ≈ 10,5 |
| papa-kaban | fable (цены Opus) | ≈ 4,0 M (план + редакция 2) | ≈ 4,1 |
| kaban | sonnet | ≈ 20,5 M | ≈ 5,2 |
| kaban-doeba | sonnet | ≈ 14,7 M | ≈ 4,0 |
| kaban-svekrov | opus | ≈ 1,6 M | ≈ 2,0 |
| mama-kaban | opus | ≈ 1,4 M | ≈ 1,4 |
| kaban-test | opus | ≈ 0,4 M | ≈ 0,9 |
| svinopas | opus | ≈ 0,36 M (уже прошло) | ≈ 0,3 |
| итого | | ≈ 65 M | ≈ 28,4 |

Варианты дешевле (выбор за пользователем; ревью и аудит не трогаем):
- kaban/doeba — главный рост токенов в У0 (кэш-чтение длинных сессий): новый запуск субагента на партию вместо
  возобновления — ≈ −30 % их токенов, ≈ −$2,7; теряем контекст прошлой партии (даётся ссылкой на документ шага).
- разбор выживших мутантов — отдельный вызов haiku по выводу `mutmut results` (правило 7 AGENTS) — ≈ −$0,5; теряем
  глубину разбора на пограничных мутантах.
- П4 не запускать отдельным циклом, если список проектировщика короткий (скрипт по образцу) — ≈ −$1,5; теряем отдельное
  ревью, но ревью партии не сокращаем — значит, только если П4 сольётся с последней правкой П3.
- оркестратор — `/compact` после каждой партии и ревью (как в У0): уже в оценке, без него ≈ +$5.
