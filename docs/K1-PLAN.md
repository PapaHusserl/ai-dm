# План партии К1 «Заклинания и дальность» (papa-kaban, 2026-10-13; на аппрув проектировщика)

Вписано оркестратором (у papa-kaban нет Write).

Задача: BACKLOG 13 (дальность), 14 (концентрация по часам), 18 (апкаст), остаток 11 (смена подготовленных) по решениям
docs/decisions/k1-grooming.md («Решения проектировщика»): **В1а** единая шкала 10/30/60/120 для оружия и заклинаний, подмена
в `cast_targets` убирается, баланс принят явно, sim_combat до и после; **В2а** одна функция истечения после каждого сдвига часов
и в конце хода; **В3а** `until_s` вне боя и в бою; **В4а** Метка вне боя — срок 1 ч, `mark_pending` уходит с концентрацией;
**В5а** из п. 11 только смена подготовленных; **В6а** через `rest` длинного отдыха (`prepared_swap`), лимит — поле данных
класса; **В7** снят (в промпт идут только подготовленные — уже так; мутмут `master.prompt` оставить); **апкаст в бою и вне боя**,
**В8а** пункт меню на каждый круг, **В9а** бесплатное применение — только базовый круг, **В10** Метка 8/24 ч — К7х, новый пункт
не заводить. Сейв v9, новых полей и миграций нет; данные классов получают поле `prepared_swap`. Размер M ≈ 1,25 млн по шкале R5.
Код на bd576a5, src чистый; smells 200/206, WINDOW мока 24500 (пик 19302, бюджет 19600).

## Что показал код (сверка перед планом)

- **Дальность.** `range_band_ft` (`combat/zones.py:24–30`): 0 → 10, 1 → 30, иначе 120. Подмена «2 шага = 60» — только в
  `cast_targets` для `attack/darts/mark` (`combat/actions/cast.py:95–99`); `buff` (строка 121) и оружие
  (`attack.py:173, 191` — `base_advantage`, `base_label`) считают по 120. Других читателей нет (`grep range_band_ft`).
  Тактика (`controllers.py`) меряет `distance`, не полосы. Последствия 2 шага = 60: короткий лук/лёгкий арбалет 80/320 —
  помеха «дальность» пропадает (в т.ч. у гоблина с луком, `goblin_warrior.yaml:37`); кинжал/копьё 20/60 и
  `improvised_thrown` 20/60 на 2 шагах становятся возможны с помехой (раньше — варианта нет); Метка 90 — как сейчас (60);
  Благословение 30 — как сейчас (нет). В goblins3 goblin_3 на балконе в 2 шагах от двери героя стреляет без помехи → бой
  труднее для героя. Golden `tests/golden/goblins3_win.txt` и `S_WIN` (`test_criterion1.py:53`) меняются осознанно по
  правилу перегенерации criterion1; порога доли побед в тестах нет — «сетка» = распределение исходов на 200 сидах.
- **Концентрация.** `Concentration.until_s` всегда `None` (`state/creature.py:49`, `m0009:28`). Вне боя:
  `start_concentration(hero, world, spell, circle)` → `drop_concentration` (`spellcasting.py:123–151`), эффект
  `kind=spell` + `Expiry seconds` только в ветке «прочее» (`resources.py:486`). В бою три одинаковых блока
  «`end_concentration` + `drop_concentration_effects` + `Concentration(...)`» (`cast.py:214–217, 233–236, 326–329`).
  Часы в бою стоят: движок всюду берёт `world.clock.now_s` (`engine.py:191–200`, `cast.py:166`), раунды переводятся в
  секунды один раз в `end.conclude` (`end.py:120`), там же снимается концентрация `rider`. `mark_pending` имеет
  `Expiry(kind="concentration")` → `end_concentration` снимает его сам (В4а почти даром).
- **Сдвиги часов (карта).** Протокол: `rest` (`resources.py:650`, внутри `rests.short_rest/long_rest` `clock.advance`),
  `advance_time` по категории (682), `travel` (723). Бой: `end.conclude` (120), `defeat.do_left_to_die` (149, часы после
  поражения — внутри хода боя). Граница сцены: `scene.close_scene` → `ensure_min_advance` (`scene.py:43`). Вне хода:
  `world_run.py:54` (devtools), `campaign/build.py:32` (старт). Единой точки нет (факт 4) — отсюда В2а «и в конце хода»:
  `TurnRunner.attempt` (`turn.py:214–230`) — одно место для всех веток хода (explore/combat).
- **Апкаст.** `Upcast.per_slot_level{dice,count,targets}` (`content/models/spells.py:11–19`) нигде не читается; данные у
  `cure_wounds` (+2d8), `burning_hands` (+1d6), `bless` (+1 цель), `magic_missile` (+1 дротик), `ensnaring_strike` (+1d6);
  у `hunters_mark` нет. `cast_problem` отклоняет `circle != spell.level` (`spellcasting.py:59–64`), `spend_cast` списывает
  `spell.level` (80–87), `cast_options` ставит `circle = spell.level` и смотрит ячейку только своего круга
  (`available.py:118–161`), `castable_spells` — тоже (`cast.py:53–61`): при пустых ячейках 1 круга и живых 2 круга
  заклинание 1 круга сейчас не предлагается вовсе. `cast_rider` уже строит кости `f"{circle}d{sides}"` (`cast.py:239–245`) и
  есть тест `test_upcast_charge_deals_one_die_per_slot_level`. Авто-герой `pick_spell` берёт первый `cast` по цели
  (`controllers.py:168–173`) — при порядке кругов по возрастанию выберет базовый. Меню TUI (`ui/combat_menu.py`) группирует
  `cast` по цели, `short_label` режет только суффикс «ещё N из 2» — подпись «(2 круг)» уцелеет; `fit` вытесняет лишние
  строки в «Ещё».
- **Подготовленные.** Меняются только в `builder` (382–392, 503) и на уровне (`progression.py:188–201, 316–373`:
  `spell_candidates` берёт весь список класса по `spell.classes` и кругу ≤ max ячейки, `apply_level_choices` пишет и в
  `known_of`, и в `prepared_of`). Лимит — `derived.prepared_limit` (326); `always_prepared` (340) в лимит не входит.
  `Spellcasting` класса (`classes.py:11–19`) без признака смены. SRD 5.2: следопыт — одно за длинный отдых, жрец и волшебник —
  любые (волшебник — из книги; в проекте книга = подготовленные, см. Q2).
- **Запросы.** `Rest{kind, hit_dice}` (`requests.py:389–395`); вложенные необязательные модели — по образцу
  `PlayerAction.improvise: ImproviseSpec` + `model_validator cut_improvise` (184–194). `CastSpell.circle` описан как «круг
  заклинания» (297). Схема строгая, без union; `tests/unit/protocol/test_requests.py:277` держит список необязательных полей
  `rest`, `protocol_kit.py` — контракт `rest{kind, hit_dice}`.
- **Промпт.** `sheet_data` шлёт `spells_prepared/always_prepared/spell_slots` (`prompt.py:309–312`); концентрацию героя
  рассказчик не видит вовсе (`grep concentration src/ai_dm/master` пуст) — об истечении он узнаёт только из `log`
  обработчика в том же ходу. `narrator_rules.md:100` — абзац про `cast_spell` (`circle` — круг заклинания), про смену
  подготовленных ничего. Replay: `request_fingerprint` = sha256 всего запроса, включая схемы инструментов
  (`llm/journal.py:15`) → правка `Rest`/`CastSpell` ломает воспроизведение старых живых репортов (как Ф1), фикстуры тестов —
  скриптовые (`tests/fixtures/scripts/*.yaml`), не журналы.
- **Тесты, которые изменят ожидание.** `test_zones.py:303–312` (полоса 2 шага), `test_actions_attack.py:161`
  (`beyond_normal_range_has_disadvantage`: шортбоу через зону — теперь без помехи), `:255`
  (`monster_ranged_attack_uses_its_own_ranges`, гоблин с балкона), `test_actions_cast.py` шапка-контракт, `test_bless.py`
  id `cast:bless:1:…` (остаются), `test_cast_explore.py:234–286` (`circle` в результате/концентрации — остаются),
  `test_criterion1.py` `S_WIN`/golden, `test_sim_combat.py` (поведение не меняется), `test_requests.py:277`,
  `protocol_kit.py` контракт `rest`.

## Реализация (kaban; src и docs)

### 1. Дальность (В1а) — `src/ai_dm/combat/zones.py`, `src/ai_dm/combat/actions/cast.py`
1.1. `range_band_ft`: 0 → 10, 1 → 30, 2 → 60, ≥ 3 → 120; комментарий «та же зона 10, соседняя 30, через одну 60, дальше 120».
1.2. `cast_targets`: убрать подмену `if steps == 2: band = 60` (строки 97–99); ветка `buff` без правок (та же функция).
   Оружие (`attack.base_advantage/base_label`) — без правок: полоса приходит из `range_band_ft`.
1.3. Сетка sim_combat: **до** правки (на bd576a5) и **после** — распределение исходов и среднее число раундов на
   `SEEDS = range(200)` для `variant in (default, weak)`, `intent = kill` (скрипт в scratchpad на `build_scenario/simulate`,
   в репозиторий не кладётся); таблицу «до/после» — в `docs/decisions/k1-sim-combat.md` (вместе с ревью). Затем
   `--find-outcome victory` → новый `S_WIN` (и проверить `S_DOWN_*`), перегенерировать golden по инструкции в шапке
   `test_criterion1.py`, дифф golden просмотреть (ожидаемо: выстрел goblin_3 с балкона без «помеха: дальность»).

### 2. Концентрация по часам (В2а, В3а, В4а) — `src/ai_dm/rules/spellcasting.py`, `src/ai_dm/combat/actions/cast.py`, `src/ai_dm/combat/end.py`, `src/ai_dm/protocol/handlers/resources.py`, `src/ai_dm/game/turn.py`, `src/ai_dm/game/scene.py`, `src/ai_dm/game/combat_flow.py`
2.1. `spellcasting.start_concentration(hero, world, spell, circle, now_s=None)`: `until_s = now_s + spell.duration_s`, если оба
   заданы, иначе `None` (5 параметров). Новая `expire_concentration(hero, world) -> str | None`: если
   `concentration.until_s is not None and until_s <= world.clock.now_s` → `drop_concentration(hero, world)`, вернуть
   `spell_id`; иначе `None`. Старые сейвы с `until_s=None` — бессрочно до следующего заклинания (В3а), миграции нет.
2.2. `cast.py`: один помощник `hold_concentration(engine, ref, spell, circle)` — сброс прежней (`end_concentration` +
   `engine.drop_concentration_effects`) и `Concentration(spell_id, circle, until_s=engine.world.clock.now_s + duration_s)`
   (по Q1а; `duration_s None` → `until_s None`); заменить три дубля в `cast_mark`, `cast_rider`, `cast_buff`.
2.3. `end.conclude`: после `clock.advance(rounds…)` для каждого героя: концентрация `rider` — как сейчас; иначе
   `if expire_concentration(hero, engine.world): engine.drop_concentration_effects(ref); engine.log(f"{name}: {spell} кончается")`
   (участники-безымянные монстры не в `world.npcs` — поэтому и `drop_concentration_effects`). Вынести обе ветки в
   `end.release_concentration(engine)` (≤ 5 return в `conclude`).
2.4. `resources.cast_spell`: `start_concentration(..., now_s)` в ветках Метки и «прочее»; `add_spell_duration` и
   `result["until"]` — из ветки `else` в общий хвост (у `heal` `duration_s None` → ничего; у Метки — эффект `kind=spell` до
   `now_s + 3600` и `until` в результате, В4а). Ветки меньше — smells ниже.
2.5. Точки истечения в протоколе: в `rest` (после `short_rest/long_rest`), `advance_time` (ветка категории) и `travel` (после
   `clock.advance`) — `ended = expire_concentration(hero, world)`; если есть — `log.append(f"Концентрация: {name} кончилась")`,
   `result["concentration_ended"] = spell_id`. Один помощник `concentration_note(ctx, log, result)` на три обработчика.
2.6. Конец хода: `TurnRunner.attempt` после `explore_turn/combat_turn` — `expire_concentration(hero_of(work), work.world)`
   (ловит `left_to_die`, старые сейвы и всё, что не прошло через 2.5). Граница сцены: `scene.close_scene` после
   `ensure_min_advance` — тот же вызов (`hero_of(bundle)` там уже используется). Движок на входе в бой ничего не делает:
   `convert_pending_marks` как сейчас.
2.7. `combat_flow.concentration_line`: при `until_s` добавить « до HH:MM» (`clock_text`) — видимая проверка в живом прогоне.

### 3. Апкаст (В8а, В9а, В10; в бою и вне боя) — `src/ai_dm/rules/spellcasting.py`, `src/ai_dm/combat/actions/cast.py`, `src/ai_dm/combat/available.py`, `src/ai_dm/protocol/handlers/resources.py`, `src/ai_dm/protocol/requests.py`
3.1. `spellcasting.py`: `circle_allowed(spell, circle, free) -> bool` (`circle == spell.level`, либо `spell.upcast` есть, не
   `free` и `circle > spell.level`); `upcast_steps(spell, circle) -> int` (0 без `upcast`); `upcast_dice(base, step, steps) -> str`
   («2d8» + 2×«2d8» = «6d8», модификатор базы сохраняется; разные грани → `ValueError`, в данных таких нет);
   `usable_circles(hero, spell) -> list[int]` — `[0]` для заговора; иначе круги `spell_slot:<c>` с `current > 0` и
   `c >= spell.level`, по возрастанию; без `upcast` — только `[spell.level]`. `cast_problem`: вместо `circle != spell.level` —
   `not circle_allowed(...)` → `bad_circle` с текстом «круг N, запрошен M; повышение — только у заклинаний с усилением и не для
   бесплатного применения»; ячейка — `spell_slot:{circle}` (`no_slot` «нет ячейки M круга»). `spend_cast(hero, registry,
   spell, free, circle)` — списывает `spell_slot:{circle}`. `roll_heal(spell, hero, registry, rng, circle=None)` — кости через
   `upcast_dice` при `steps > 0`.
3.2. `cast.py`: `castable_spells` — `usable = bool(usable_circles(hero, spell)) or free_cast_left(...)`;
   `cast_targets(engine, ref, spell, circle=None)` — у `buff` `limit += steps × (upcast.targets or 0)`;
   `scaled_dice(spell, hero, effect, circle)` — после заговорного роста добавка `upcast.dice × steps`; `cast_darts` —
   `count = effect.count + steps × (upcast.count or 0)`; `cast_rider` — `circle` из параметра, кости
   `upcast_dice(effect.dice, upcast.dice, steps)` (для 1d6 = `{circle}d6`, как сейчас); `CASTERS` получают пятый параметр
   `circle` (`cast_attack`, `cast_heal`, `cast_mark`, `cast_area` принимают и передают дальше); `perform`: `circle =
   option.params["circle"]`, списание `spell_slot:{circle}`, лог «читает X (2 круг)» при `circle > spell.level`;
   `hold_concentration(..., circle)` → `Concentration.circle` = фактический круг.
3.3. `available.cast_options`: вынести тело цикла в `spell_entries(engine, ref, spell, cost) -> list[ActionOption]`:
   для `circle in usable_circles(hero, spell)` — `cast_targets(engine, ref, spell, circle)`, id
   `cast:{spell.id}:{circle}:{target}`, `params {spell, circle, target}`, подпись `f"{spell.name} ({circle} круг) {where}"`
   только при `circle > spell.level`; бесплатный вариант — только для `spell.level` (В9а), как сейчас. Порядок: базовый
   круг первым (авто-герой берёт его).
3.4. `resources.cast_spell`: `spend_cast(..., request.circle)`; заголовок лога «(2 круг, ячейки 1/1)» по `request.circle`;
   `roll_heal(..., circle=request.circle)`; `buff` с `circle > level` — по Q4а `Invalid bad_circle` («вне боя Благословение —
   базовым кругом: цель одна»); `rider` — `combat_only` как сейчас; Метка без `upcast` → `bad_circle` (В10, К7х).
3.5. `requests.CastSpell.circle` — описание: «Круг ячейки: круг заклинания или выше у заклинаний с усилением (upcast); 0 для
   заговоров; бесплатное применение — только круг заклинания.» (≤ 150 символов — WINDOW).

### 4. Смена подготовленных после длинного отдыха (В5а, В6а) — `src/ai_dm/content/models/classes.py`, `src/ai_dm/srd/data/classes/{ranger,cleric,wizard}.yaml`, `src/ai_dm/protocol/requests.py`, `src/ai_dm/rules/spellcasting.py`, `src/ai_dm/protocol/handlers/resources.py`, `src/ai_dm/master/prompts/narrator_rules.md`
4.1. `Spellcasting.prepared_swap: int | Literal["all"] | None = None` (комментарий «сколько подготовленных можно заменить
   после длинного отдыха; None = нельзя»). Данные: `ranger.yaml` `prepared_swap: 1`, `cleric.yaml` и `wizard.yaml` `all`.
   Контентные тесты `test_srd_minimum`/`test_classes_1_20` — проверка поля.
4.2. `requests.py`: `PreparedSwapSpec(Request)`: `drop: list[str] = []` («id подготовленных, которые снять; пусто = нет»),
   `take: list[str] = []` («id заклинаний класса, которые подготовить; пусто = нет»). `Rest.prepared_swap:
   PreparedSwapSpec = Field(default_factory=PreparedSwapSpec, description="Смена подготовленных после длинного отдыха; без
   неё оба списка пусты.")` + `model_validator cut_swap` (оба пусты → `None`), по образцу `cut_improvise`. Описания короткие
   (WINDOW).
4.3. `spellcasting.py`: `swap_problem(hero, registry, drop, take) -> (code, message) | None` — порядок проверок:
   `no_spellcasting` (у класса нет `spellcasting` или `prepared_swap is None`); `swap_limit` (`len(drop) > limit` или
   `len(take) > limit` при целом лимите; текст «следопыт меняет одно заклинание за отдых»); `unknown_spell` (+ `allowed`
   из `hints`); `not_prepared` (в `drop` нет в `prepared_of`; `always_prepared` снимать нельзя); `already_prepared`;
   `bad_spell` (`take`: не из `spell.classes` класса, заговор, круг выше max ячейки по `spell_slots` — как
   `progression.spell_errors`); `prepared_limit` (`len(prepared) - len(drop) + len(take) > prepared_limit`). Повторы в
   списках — `bad_swap`. `swap_prepared(hero, registry, drop, take)`: убрать из `prepared_of`, добавить `take` в
   `prepared_of` и (если нет) в `known_of` — как `apply_level_choices` (Q2а: источник — список класса).
4.4. `resources.rest`: если `request.prepared_swap` задан: `kind != "long"` → `Invalid swap_long_only`; `swap_problem` →
   `Invalid` до отдыха (Q3а); после `long_rest` — `swap_prepared`, `log.append("Подготовлено: X; снято: Y")`,
   `result["prepared"] = list(prepared_of)`. Вынести в `apply_swap(ctx, request, log, result)` (smells).
4.5. `narrator_rules.md:100` — дописать в абзац про `cast_spell` два предложения (≤ 350 символов суммарно): «`circle` можно
   поднять у заклинаний с усилением (лечение, стрела, огненные руки, благословение, опутывающий удар), если есть ячейка;
   движок откажет `bad_circle`, если нельзя. После длинного отдыха по просьбе игрока смени подготовленные: `rest` `long` с
   `prepared_swap` (`drop` — id снимаемых, `take` — id новых заклинаний класса; следопыт — одно, жрец и волшебник — любые);
   без просьбы список не трогай.» Формулировку финально — kaban. Прогнать `test_stage4_memory`; при превышении бюджета —
   6-й подъём `WINDOW` (24500 → 25000) с комментарием в том же стиле, строка в BACKLOG 45.

### 5. Docs
`docs/BACKLOG.md`: 13 ✅, 14 ✅, 18 ✅ (ссылка на план/ревью); 11 — `cast_spell` вне боя ✅ (было сделано раньше, факт 3
груминга), смена подготовленных ✅, «улучшение Метки от круга 8/24 ч — К7х»; 45 — строка про WINDOW, если поднимали.
`docs/ROADMAP.md`: #12 ✅, пересчёт шкалы после К1 (факт расхода). `docs/HANDOFF.md`: строка К1. `docs/ARCHITECTURE.md`:
:65 (`until_s` — конец концентрации по часам, `None` = бессрочно), :304 «полосы 10/30/60/120 фт», :312 (заряд: кости по кругу
через `upcast`), раздел 17 — апкаст (`usable_circles`, `cast:<id>:<круг>:<цель>`), «Сдвиг часов → `expire_concentration`»
(перечень точек 2.5–2.6). `docs/TZ.md:62` — `rest` с `prepared_swap`. `docs/decisions/k1-sim-combat.md` — таблица до/после.
Чек-лист `docs/checklist-k1-live.md` (не коммитить): (1) следопыт: Метка вне боя на NPC → `advance_time` «hour» ×2 → в ответе
движка «Концентрация: Метка охотника кончилась», строка статуса без концентрации; до того — «Концентрация: Метка охотника до
HH:MM»; (2) бой с лучником через зону: у короткого лука нет «помеха: дальность», кинжал броском через зону предлагается с
помехой; (3) жрец ≥ 3 ур. (или волшебник ≥ 3 с Волшебной стрелой): в меню боя «Волшебная стрела (2 круг) → цель», списана
ячейка 2 круга, 4 дротика; вне боя `cast_spell` `circle: 2` Лечения ран → 4d8; (4) длинный отдых с просьбой «подготовь
вместо X — Y» → `rest` с `prepared_swap`, `/sheet` показывает новое; следопыт просит два — отказ `swap_limit`; (5)
`--replay-report` репорта с пп. 1–4 → код 0.

## Изменённые функции для mutmut (`make mutate FUNCS=… TESTS=…`)
- `ai_dm.combat.zones:range_band_ft` — TESTS tests/unit/combat/test_zones.py tests/unit/combat/test_actions_attack.py
  tests/unit/combat/test_range_bands.py
- `ai_dm.combat.actions.cast:castable_spells ai_dm.combat.actions.cast:cast_targets ai_dm.combat.actions.cast:scaled_dice
  ai_dm.combat.actions.cast:hold_concentration ai_dm.combat.actions.cast:cast_darts ai_dm.combat.actions.cast:cast_rider
  ai_dm.combat.actions.cast:cast_buff ai_dm.combat.actions.cast:cast_heal ai_dm.combat.actions.cast:cast_area
  ai_dm.combat.actions.cast:perform` — TESTS tests/unit/combat/test_actions_cast.py tests/unit/combat/test_bless.py
  tests/unit/combat/test_ensnaring_strike.py tests/unit/combat/test_upcast.py tests/unit/combat/test_mark_concentration.py
- `ai_dm.combat.available:cast_options ai_dm.combat.available:spell_entries` — TESTS tests/unit/combat/test_available.py
  tests/unit/combat/test_upcast.py tests/unit/combat/test_option_cost.py
- `ai_dm.combat.end:conclude ai_dm.combat.end:release_concentration` — TESTS tests/unit/combat/test_end.py
  tests/unit/combat/test_ensnaring_strike.py tests/unit/combat/test_concentration_clock.py
- `ai_dm.rules.spellcasting:cast_problem ai_dm.rules.spellcasting:spend_cast ai_dm.rules.spellcasting:circle_allowed
  ai_dm.rules.spellcasting:upcast_steps ai_dm.rules.spellcasting:upcast_dice ai_dm.rules.spellcasting:usable_circles
  ai_dm.rules.spellcasting:roll_heal ai_dm.rules.spellcasting:start_concentration
  ai_dm.rules.spellcasting:expire_concentration ai_dm.rules.spellcasting:swap_problem
  ai_dm.rules.spellcasting:swap_prepared` — TESTS tests/unit/rules/test_spellcasting_upcast.py
  tests/unit/rules/test_spellcasting_concentration.py tests/unit/rules/test_prepared_swap.py tests/unit/game/test_cast_explore.py
- `ai_dm.protocol.handlers.resources:cast_spell ai_dm.protocol.handlers.resources:rest
  ai_dm.protocol.handlers.resources:apply_swap ai_dm.protocol.handlers.resources:concentration_note
  ai_dm.protocol.handlers.resources:advance_time ai_dm.protocol.handlers.resources:travel` — TESTS
  tests/unit/protocol/test_apply_resources.py tests/unit/protocol/test_apply_rest_swap.py tests/unit/game/test_cast_explore.py
  tests/unit/protocol/test_concentration_expiry.py
- `ai_dm.protocol.requests:PreparedSwapSpec ai_dm.protocol.requests:Rest.cut_swap` — TESTS tests/unit/protocol/test_requests.py
  tests/unit/protocol/test_schema.py
- `ai_dm.game.turn:TurnRunner.attempt ai_dm.game.scene:close_scene` — TESTS tests/unit/game/test_game_turn.py
  tests/unit/game/test_game_scene.py tests/unit/game/test_game_concentration.py
- `ai_dm.game.combat_flow:concentration_line` — TESTS tests/unit/game/test_game_combat_flow.py
- `ai_dm.master.prompt:PromptBuilder.sheet_data ai_dm.master.prompt:PromptBuilder.state_data
  ai_dm.master.prompt:PromptBuilder.memory_block` (В7: оставить) — TESTS tests/unit/master/test_master_prompt.py
  tests/unit/master/test_master_memory_block.py tests/unit/master/test_master_hero_data.py

## Тесты (kaban-doeba, TDD; параллельно с kaban)

Правка существующих: `test_zones.py:303–312` и шапка (2 → 60, 3 → 120); `test_actions_attack.py:161`
(`beyond_normal_range…`: шортбоу через зону теперь без помехи — переписать на 4 зоны/3 шага, чтобы помеха осталась у «3 шага =
120»), `:255` (гоблин с балкона: тот же бросок, без помехи — ожидание HP); `test_improvised_weapon` / тесты кинжала: бросок на 2
шагах предлагается с помехой; `test_actions_cast.py` шапка-контракт (id `cast:<id>:<круг>:<цель>`, круг может быть выше
базового); `test_requests.py:277` (`rest`: `prepared_swap` необязателен, `cut_swap`), `protocol_kit.py` контракт `rest`;
`test_criterion1.py` `S_WIN`/golden по п. 1.3 (дифф golden — в ревью); `test_bless.py`, `test_cast_explore.py:234–286`,
`test_sim_combat.py` — зелёные без правок (проверить).

Дальность (`tests/unit/combat/test_range_bands.py`, рига `combat_kit.make_engine` с 4–5 зонами в линию): `range_band_ft`
0/1/2/3/4 → 10/30/60/120/120; шортбоу 80/320: 2 шага — обычная (`base_label == ""`), 3 шага — «дальность»; длинный лук 150/600:
3 шага обычная; кинжал 20/60: 1 шаг — помеха, 2 шага — помеха (вариант есть), 3 шага — варианта нет; `improvised_thrown`
20/60 — так же; гоблин с луком с 2 шагов — без помехи; `fire_bolt` 120 — достаёт 3 шага; Метка 90 — 2 шага да, 3 нет;
Благословение 30 — 1 шаг да, 2 нет (как раньше); `cast_targets` без подмены (мутант «band = 60» умирает тестом «3 шага для
Метки»). Сетка sim_combat: тест-свойство `test_criterion1` (200 сидов, время = раунды × 6 с) зелёный; числа до/после — в
`docs/decisions/k1-sim-combat.md`.

Концентрация (`tests/unit/rules/test_spellcasting_concentration.py`, `tests/unit/protocol/test_concentration_expiry.py` на
`protocol_kit.make_ctx`+`apply`, `tests/unit/combat/test_concentration_clock.py`, `tests/unit/game/test_game_concentration.py` на
`game_kit.make_rig`):
- `start_concentration(..., now_s=1000)` для Метки (1h) → `until_s == 4600`; без `now_s` → `None`; у `cure_wounds`
  (`duration_s None`) → `None`.
- `expire_concentration`: `until_s None` → `None`, ничего не снято (старый сейв); `until_s > now` → `None`; `until_s == now` →
  снята, вернул `spell_id`; снимает `mark_pending` у героя, `modifier` у NPC мира (`Expiry concentration owner=hero`), эффект
  `kind=spell`; чужие эффекты NPC остаются.
- Воспроизведение п. 14: Метка вне боя на NPC + `advance_time hour` ×2 → после первого (ровно 1 ч, срок наступил) `concentration is None`, `mark_pending`
  нет, в `log` «Концентрация: Метка охотника кончилась», `result["concentration_ended"]`; через минуту — держится. То же
  через `travel` (маршрут > 1 ч) и `rest` (длинный 8 ч; короткий 1 ч — `until_s <= now` → кончилась на границе: зафиксировать
  правило «ровно в срок — кончилась»).
- Метка вне боя (В4а): в результате `until`, эффект `kind=spell` с `Expiry seconds = now+3600`; `mark_pending` с
  `Expiry concentration`; бой начался до срока → `convert_pending_marks` кладёт метку (тест
  `test_mark_outside_combat_goes_onto_target_when_combat_starts` остаётся).
- Бой: `cast:bless:1:ally` → `concentration.until_s == now + 60`; `hunters_mark` → `+3600`; `ensnaring_strike` → `+60`; бой
  11 раундов (66 с) → после `conclude` Благословение снято у заклинателя и целей, лог «Благословение кончается»; Метка после
  того же боя держится; `rider` снят как раньше; старый сейв (`until_s None`) после боя держится.
- Конец хода: рига, у героя `until_s` в прошлом (сейв загружен) → после любого хода `concentration is None`; ход, где
  `left_to_die` сдвинул часы на часы → концентрация снята. Граница сцены: `close_scene` с `ensure_min_advance` (10 мин) при
  Благословении вне боя (1 мин) → снято до автосейва.
- UI: `concentration_line` «Концентрация: Метка охотника до HH:MM» при `until_s`, без «до» при `None`.
- Replay: ход с `cast_spell` Метки + ход с `advance_time` 2 ч → `--replay-report` код 0 (стиль `test_r2_replay`).

Апкаст (`tests/unit/rules/test_spellcasting_upcast.py`, `tests/unit/combat/test_upcast.py` на `make_wizard`/жреце/следопыте
с ячейками 2 круга через `resources["spell_slot:2"]`, `tests/unit/game/test_cast_explore.py` дополнение):
- `upcast_dice("2d8","2d8",2) == "6d8"`, `("1d4+1","1d4",1) == "2d4+1"`, разные грани → `ValueError`; `upcast_steps` без
  `upcast` → 0; `circle_allowed`: `(level, free)` да; `(level+1, free=False)` да при `upcast`, нет без; `(level+1, free=True)`
  нет; `(level-1)` нет; заговор только 0.
- `usable_circles`: ячейки 1 и 2 → `[1, 2]` для `cure_wounds`, `[1]` для `hunters_mark`, `[0]` для заговора; ячейка 1 пуста,
  2 есть → `[2]` (и заклинание в `castable_spells`); без ячеек → `[]`.
- Меню: `cast:magic_missile:1:goblin_1` и `cast:magic_missile:2:goblin_1` при ячейках обоих кругов, подпись второго
  «Волшебная стрела (2 круг) → …»; без ячейки 2 круга — только 1; у Метки с ячейкой 2 — только `:1:`; бесплатный вариант —
  только `:1:…:free` (В9а); базовый круг раньше повышенного; `cost` тот же; авто-герой `pick_spell` берёт `:1:`.
- Каждое из пяти в бою: `cure_wounds` 2 круг → 4d8 (ScriptedRng d8 ×4), списана `spell_slot:2`, `spell_slot:1` цела;
  `magic_missile` 2 круг → 4 дротика (4 × d4); `burning_hands` 2 круг → 4d6, один бросок на всех; `bless` 2 круг → до 4 целей
  (`cast:bless:2:a,b,c,d` есть, `:1:a,b,c,d` нет), `concentration.circle == 2`; `ensnaring_strike` 2 круг → заряд `2d6`,
  `params["circle"] == 2`, спасбросок тот же; заговор `fire_bolt` — один пункт. Повышенный круг с провалом проверки
  (`cast_wasted`) тратит именно ячейку круга запроса.
- Вне боя: `cast_spell cure_wounds circle=2` → 4d8, списана 2, лог «(2 круг, ячейки …)», `result["circle"] == 2`; `circle=2`
  без ячейки 2 → `no_slot` «нет ячейки 2 круга»; `hunters_mark circle=2` → `bad_circle`; `circle=0` для заклинания 1 круга →
  `bad_circle` (как сейчас); `free=True, circle=2` → `bad_circle`; `bless circle=2` вне боя → `bad_circle` (Q4а); `ensnaring`
  → `combat_only`; `fog_cloud circle=2` (без `upcast`) → `bad_circle`.
- Replay: ход с `cast_spell circle=2` и бой с `cast:…:2:…` → код 0.

Подготовленные (`tests/unit/rules/test_prepared_swap.py` на `ranger_kit.ranger_at/make_class_hero`,
`tests/unit/protocol/test_apply_rest_swap.py`, контент):
- Данные: `ranger.spellcasting.prepared_swap == 1`, `cleric`/`wizard` `"all"`, `fighter`/`rogue` `spellcasting is None`.
- Запрос: `rest{kind: long}` без `prepared_swap` → `prepared_swap is None`; с `{drop: [], take: []}` → `None`; с `drop` →
  объект; схема строгая (нет union, `test_schema` как для `improvise`); `parse_request` в explore.
- `swap_problem`: следопыт 2 ур. (`cure_wounds`, `fog_cloud`): `drop [fog_cloud] take [longstrider]` → `None`;
  `drop [fog_cloud, cure_wounds] take [...]` → `swap_limit`; `take` неизвестный → `unknown_spell` с «допустимые id»;
  `drop [hunters_mark]` (always) → `not_prepared`; `take [cure_wounds]` → `already_prepared`; `take [burning_hands]` (не
  следопыт) / `take [spike_growth]` на 1–4 ур. (круг 2 недоступен) / заговор → `bad_spell`; `drop [] take [x]` при полном
  лимите → `prepared_limit`; `drop [] take [x]` при свободном месте → `None`; жрец `all`: три за раз → `None`; воин →
  `no_spellcasting`; повторы → `bad_swap`.
- `swap_prepared`: `prepared_of` обновлён, `take` попал в `known_of`, `always_prepared` цел, порядок остальных сохранён.
- Обработчик: длинный отдых + swap → `accepted`, HP/ячейки восстановлены, часы +8 ч, лог «Подготовлено…; снято…»,
  `result["prepared"]`; `kind short` + swap → `Invalid swap_long_only`, часы не сдвинуты; плохой swap → `Invalid`, бандл
  байт-в-байт прежний (Q3а); swap при 0 HP → `rest_impossible` (ничего не изменилось); после swap новое заклинание доступно
  `cast_spell` (`cast_problem` `None`), снятое → `not_prepared`.
- Промпт: `narrator_rules.md` содержит «prepared_swap», «bad_circle»; `test_stage4_memory` зелёный (при подъёме `WINDOW` —
  новый порог); `sheet_data` после swap отдаёт новый `spells_prepared`.
- Replay: ход с `rest` + `prepared_swap` → `--replay-report` код 0.

Общее в конце: `uv run pytest -q`, `make cov` (≥ 94 %), `make smells` (≤ 206; ожидание ≤ 203 — `hold_concentration`,
`spell_entries`, `apply_swap`, `release_concentration`, хвост `cast_spell`), `make dead`, `uv run ruff check src tests`;
mutmut по списку выше.

## Критерии приёмки
1. Полоса дальности 10/30/60/120 одна для оружия героя, монстров и всех видов заклинаний; подмены в `cast_targets` нет; сетка
   sim_combat до/после записана, golden перегенерирован осознанно с диффом в ревью.
2. Концентрация с `until_s` кончается ровно по часам после любого сдвига (`rest`, `advance_time`, `travel`, конец боя, конец
   хода, граница сцены): снимаются и объект, и эффекты у героя и NPC, `mark_pending` в том числе; Метка вне боя — 1 ч; в
   бою `until_s` ставится, проверка — после боя; старый сейв с `until_s=None` — бессрочно до следующего заклинания, без
   миграции.
3. Апкаст: в бою — отдельный пункт на каждый доступный круг только у пяти заклинаний с `upcast`, бесплатное применение — базовый
   круг; вне боя — `circle` выше базового принимается у тех же заклинаний (кроме Благословения — Q4), иначе `bad_circle`;
   ячейка списывается круга запроса; эффекты растут по `per_slot_level`; Метка — только базовый круг (8/24 ч — К7х).
4. `rest long` с `prepared_swap` меняет подготовленные в пределах лимита класса (`1 | all`) и `prepared_limit`, не трогает
   `always_prepared`; ошибки — `Invalid` без отдыха; короткий отдых — отказ.
5. Replay ходов с новыми параметрами — код 0. В промпт по-прежнему только подготовленные (В7); мутмут `master.prompt` прогнан.
6. Сейв v9, схема без правок; тесты зелёные, cov ≥ 94 %, smells ≤ 206 (ожидание ≤ 203); `WINDOW` — подъём только при
   превышении, с записью в BACKLOG 45.

## Оценка
M ≈ 1,25 млн: kaban ~220–280 тыс. (~25 мин); kaban-doeba ~550–650 тыс. (~3 ч с mutmut и сеткой: ~130 тестов, сетка до/после,
golden); mama-kaban ~40 тыс. Фактически меньше роадмапа: `cast_spell` вне боя и промпт уже сделаны.

## Риски / на что обратить внимание
- **Баланс (В1а, принято явно).** Лучники (80/320) через зону теряют помеху, метательное 20/60 через зону становится
  возможным; в goblins3 это усиливает goblin_3 — доля побед воина на 200 сидах упадёт; это изменение правил, не баг. Числа
  до/после — обязательны в ревью; порога в тестах нет, решение по сетке — проектировщик.
- **Golden и сиды.** `S_WIN`/`S_DOWN_*` и `goblins3_win.txt` менять только по инструкции `test_criterion1.py` с просмотром
  диффа; падение golden без правки правил — баг.
- **Рост меню боя.** Варианты × круги × цели: у `bless` на 2 круге до 4 целей → сочетания C(n,1..4); в TUI лишние строки
  уходят в «Ещё» (`fit`), простой режим покажет всё. На практике союзников 1–2. Повышенный круг предлагать только при
  ячейке этого круга; базовый круг первым.
- **Пропуск сдвига часов — самый вероятный брак.** Страховка — вызов в `attempt` (конец любого хода) и в `close_scene`. Новые
  сдвиги часов в будущих партиях должны звать `expire_concentration` — записать правило в ARCHITECTURE.
- **Часы в бою стоят** (Q1а): Благословение в бою не кончится на 11-м раунде, а после боя; приемлемо для К1.
- **Старые сейвы** с `until_s=None` — бессрочно до следующего заклинания (В3а); dusk_academy — проверить в прогоне.
- **Replay старых живых репортов** ломается изменённой схемой (`Rest`, `CastSpell`), как после Ф1. Новые — штатно.
- **Рассказчик не знает id заклинаний класса** — `take` будет угадываться; `Invalid` с `allowed` подскажет. Если бьёт — Q5б.
- **Smells 200/206.** Выносить помощники (п. 2.4–2.5, 3.3, 4.4); `hold_concentration` убирает три дубля. Лимит не поднимать.
- **WINDOW мока.** Запас ≈ 300 токенов; 6-й подъём 24500 → 25000 допустим с записью в BACKLOG 45; тексты держать короткими.
- **Волшебник** (Q2а): смена из списка класса расходится с SRD (книга), но совпадает с уровнем в проекте; книга — не К1.
- **Mutmut на macOS** — segfault (BACKLOG 16): узкие TESTS.

## Открытые вопросы
- **Q1 `until_s` в бою.** (а) **рекомендация** — `clock.now_s + duration_s` при касте (часы в бою стоят), истечение — в
  `conclude` после сдвига на раунды; (б) раунды внутри боя отдельным `Expiry rounds` — новая механика, не К1.
- **Q2 Откуда волшебнику брать `take`.** (а) **рекомендация** — из списка класса, как `spell_candidates` на уровне; (б) только
  из `known_of` — по SRD, но смена пустая до появления книги.
- **Q3 Ошибка в `prepared_swap`.** (а) **рекомендация** — `Invalid` до отдыха, отдых не применён; (б) отдых применить, смену
  отбросить `clamped`.
- **Q4 Апкаст Благословения вне боя.** (а) **рекомендация** — `bad_circle`; (б) принимать, круг только в `Concentration.circle`.
- **Q5 Подсказка рассказчику об апкасте.** (а) **рекомендация** — не добавлять; (б) `spells_upcast: [id]` в `sheet_data`.

Расход papa-kaban ≈ 210 тыс.

## Решения проектировщика (2026-10-13)
Q1 (а), Q2 (а) — волшебник берёт `take` из списка класса; книга заклинаний — BACKLOG 47; Q3 (а), Q4 (а), Q5 (а).
