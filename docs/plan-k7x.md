# План партии К7х «Хвосты боя: отбор оружия, падение, толчок монстров, следопыт, снаряжение в бою» (papa-kaban, 2026-10-14; на аппрув проектировщика)

Вписано оркестратором (у papa-kaban нет Write).

Задача: R4 #10 / R5 #14 по решениям `docs/plan-k7x.md` («Решения проектировщика», 2026-10-14): **В1+В13** высота падения — разница `elevation` зон, 10 фт на ступень, 1d6 за 10 фт, не больше 20d6, параметра запроса нет; **В2** падение при `push` в зону ниже — урон и `prone`, **монстры тоже толкают** (ИИ получает толчок; политика — Q1); **В3** `[disarm].mode = save`: спас Сил/Лов на выбор цели, СЛ 8 + Сил/Лов + БМ атакующего, одно правило для всех; **В4** `enemy_chance` — бросок раз за бой при старте, по умолчанию 0; **В5** монстр идёт к своему оружию в соседней зоне, если в его зоне некого бить; **В6** Метка 8/24 ч → К8+ (BACKLOG 11, :237); **В7** Истребитель орд — пункт меню после любой атаки оружием, раз в ход, цель в зоне первой; **В8** `prey_swap` в `Rest` на коротком и продолжительном; **В9** КД = `ac` − вклад статблоковых доспеха/щита + вклад надетого, `NPC.equipment` → `Participant` при старте, запроса «надеть/снять» нет; **В10** оружия нет в `equipment.weapons` — оно потеряно; **В11** хвост «уровни 2–5» из ROADMAP:25 убрать; **В12** BACKLOG 51 попутно; **В14** яма считается так же, выход — обычным движением; **В15** строка в `narrator_rules.md`. Сейв v9: новых полей сейва нет (`TurnState`/`Participant`/`CombatState` — в отпечатке `test_schema_fingerprint.py`, поэтому всё состояние «раз в ход / раз за бой» — `ActiveEffect`-флаги, как `disarm_used`). Схема запросов рассказчика **меняется** (`Rest.prey_swap`, текст `ImproviseSpec.effect`) — прецедент К1 `prepared_swap`. Код на 4fc2ce8, smells 204/206 (запас 2), WINDOW мока 25000 (пик 19666/20000).

## Что показал код (сверка перед планом)

- **Толчок.** `improvise.apply_push` (`combat/actions/improvise.py:98–102`) — `record_move` + смена `zone_id`, урона нет; `check_request` → `not_a_hero` (:45). `Zone.elevation` (`state/combat.py:43`) ставит рассказчик (`ZoneSpec`, `requests.py:53`), читает `attack_tags` (`attack.py:217`) и `ElevationSource` (`zones.py:56`). Урон в бою — только `engine.damage` (К7к), состояния — `engine.impose`; `stand_up` (`engine.py:83`) снимает `prone` с `source != "0_hp"` в начале хода и обнуляет перемещение — лежащий в яме встаёт, выходит обычным ходом (В14). `roll_damage(engine, ref, dice, bonus, crit, label=, damage_type=)` даёт стандартную строку лога. `downed.after_damage(engine, target, dealt, by_ref)` — общий хвост урона (падение героя, смерть монстра, события).
- **Отбор оружия.** `DisarmConfig` (`config/settings.py:73`, `extra=forbid`): `unarmed_types`, `unarmed_proficiency`. `disarm.perform` (`disarm.py:174`): `target_mode` → `target_check` → `roll_attack(... dc=check.total + 1)`. `may_disarm` (:20): герой всегда, монстр — тег `disarmer` и нет флага `disarm_used`. `engine.save(ref, ability, dc, cover=0, base_adv=)` (`engine.py:235`) — готовый спасбросок героя/монстра с `base_adv`; `saving_throw_parts` для героя, `ability_modifier` для монстра. БМ героя — `derived.proficiency(hero, registry)` (`derived.py:19`), монстра — `cfg.disarm.unarmed_proficiency` (так уже в `monster_unarmed`). `settle_ground` (`end.py:110–116`) снимает с монстров `disarmed`, `disarm_used`.
- **ИИ.** `EngineTactics.choose_turn` (`controllers.py:39`): `pick_special` (escape > pickup > disarm, монстру) → multiattack → `pick_attack` (ближняя по своей зоне, иначе дальняя по всем) → `nearest_enemy` → dash/`step_towards`. `pickup_options` (`available.py:351`) — только своя зона; `can_pick` монстра — `item_id in lost_weapons(...)[1]`; `pickup` монстра (`disarm.py:222`) снимает флаг `disarmed` (`flags.remove(lost[0])` — упадёт, если оружие «потеряно» по `equipment`, а флага нет; см. шаг 5.3). `run_controller` зовёт `choose` в цикле: после хода к оружию `pickup` сработает тем же ходом (свободное взаимодействие).
- **КД и снаряжение.** `engine.armor_class` (`engine.py:191`): монстр — `monster.ac` (+pierce, +эффекты `ac`), `equipment` не читается. Формула героя — `armor_class_parts` (`derived.py:120`): доспех + Лов до `dex_cap` (0 — без Лов) + щит. `Monster.armor/shield` есть (К7к), у трёх монстров сходятся с `ac`. `engine.start()` (`engine.py:307`) заводит `npc.creature` — аналог для переноса `NPC.equipment`. `trophies.body_equipment(engine, ref, weapon_ids)` читает `part.equipment`, затем `npc.equipment`, иначе статблок. `lost_weapons` (`attack.py:132`) — только флаги `disarmed`; его читают `attacks_of`, `disarm.weapon_ids`, `can_pick`, `body_equipment`, `monster_unarmed`.
- **Истребитель орд.** `horde_breaker.yaml` без `effects` («в движке не считается»); `colossus_damage` (`attack.py:282`) — через `hero_effects`/`turn.colossus_used`. `hero_feature_ids` (`derived.py:290`) включает `feature_choices`. `attack.perform` (`attack.py:518`) — точка «атака оружием в свой ход» (`info.weapon_id is not None`; безоружный/импровизированное — нет); провоцированная атака идёт мимо `perform` (`opportunity.provoke`) — флаг там не ставим. `engine.expire("end_of_turn", ref)` снимает эффекты с `Expiry(kind="end_of_turn", owner=ref, value=0)` в конце хода героя. `AutoHeroController.choose_turn` (`controllers.py:151`). Пресеты паков `hunters_prey` не выбирают (grep пуст), `grid_heroes` берёт первый вариант (`colossus_slayer`) — базовая линия сетки не затронута.
- **Смена Добычи.** `sheet.feature_choices` (`hero.py:62`), валидация вариантов — `progression.choice_errors` (:278, `registry.get("feature", id).options`). `Rest` (`requests.py:399`): `prepared_swap`, `NEUTRAL={"hit_dice": 0}`; `handlers/resources.rest` (:692): `swap_invalid` до отдыха → отдых → `apply_swap` → `concentration_note`. Образец теста — `tests/unit/protocol/test_apply_rest_swap.py`.
- **enemy_chance и RNG.** `initiative.roll_initiative` в `engine.start()` тратит RNG; лишний `randbelow` сдвинет golden `goblins3_win.txt` и `sim_grid_baseline.yaml` — бросать только при `enemy_chance > 0`.
- **BACKLOG 51.** Единственный импорт rules из content — `loader.py:19` (`DAMAGE_TYPE_WORDS`); константы контента живут в `content/models/common.py` (`SKILLS`, `ABILITIES`).
- **Сетка/golden.** `goblins3` без `elevation`, `equipment` ни у кого, `mode` по умолчанию `check`, `enemy_chance` 0, герои сетки с `colossus_slayer` → поведение сим-боёв не меняется; подтвердить `make sim-grid` и golden.
- **Промпт.** `narrator_rules.md` абзац «Высота зон» (:28) — место для В15; `ImproviseSpec.effect` описание `push` (:95) — добавить «в зону ниже — падение». Запас WINDOW ≈ 330 токенов: ≤ 2 предложений.

## Реализация (kaban; src, data, docs)

### 1. Падение и толчок (В1, В2, В13, В14, В15) — `combat/falling.py` (новый), `combat/actions/improvise.py`, `config/settings.py`, `config/defaults.toml`, `protocol/requests.py`, `master/prompts/narrator_rules.md`
1.1. `CombatConfig`: `fall_step_ft: int = 10` (`[combat] fall_step_ft = 10`, комментарий «ступень elevation в футах»). В `falling.py` константы SRD: `FALL_DICE_PER_10FT = "1d6"`, `FALL_MAX_DICE = 20`.
1.2. `falling.drop_steps(zones, from_id, to_id) -> int` = `max(0, from.elevation - to.elevation)` (яма: 0 → −1 даёт 1, В14). `falling.fall_dice(steps, cfg) -> str | None`: `count = min(steps * cfg.combat.fall_step_ft // 10, FALL_MAX_DICE)`, `None` при 0.
1.3. `falling.fall(engine, target, from_zone_id, by_ref) -> list[DomainEvent]`: кости по 1.2 (нет — `[]`); лог `  {имя} падает с высоты {фт} фт`; `roll_damage(engine, target, dice, 0, False, label="Падение", damage_type="bludgeoning")` → `engine.damage(target, total, "bludgeoning")` → `log_notes`, `hp_text`; если `dealt.final > 0` — `engine.impose(target, AppliedCondition(id="prone", source="fall"))` + лог «сбит с ног» (SRD 5.2: лежит, если урон не нулевой; иммунный к дробящему — не лежит); `return downed.after_damage(engine, target, dealt, by_ref)`.
1.4. `falling.push(engine, ref, target, zone) -> list[DomainEvent]`: текущая логика `apply_push` (`record_move`, `zone_id`, лог «отброшен в зону») + `fall(engine, target, from_zone, ref)`. `improvise.apply_push` → `return falling.push(engine, ref, target, zone)` (возвращает события — падение монстра в яму может его убить, `after_damage` их даёт). Толчок вверх/вровень — как сейчас, без урона. Провоцированной атаки при вынужденном движении нет (как сейчас).
1.5. Промпт: в абзац «Высота зон» (`narrator_rules.md:28`) одно предложение: «Толчок (`push`) в зону ниже — падение: 1d6 дробящего за каждые 10 фт (ступень `elevation` = 10 фт), упавший сбит с ног; враги тоже могут толкнуть героя с высоты.» `ImproviseSpec.effect` описание `push`: «…в соседнюю зону (target и zone …); в зону ниже — урон от падения». Проверить `test_stage4_memory` без подъёма WINDOW.

### 2. Толчок монстров (В2) — `combat/shove.py` (новый), `combat/available.py`, `combat/engine.py` (`PERFORM`), `combat/controllers.py`, `combat/end.py`
2.1. `shove.contest_dc(engine, ref, abilities) -> tuple[int, list]` — СЛ 8 + лучший мод. из `abilities` атакующего + БМ (герой — `derived.proficiency`, монстр — `cfg.disarm.unarmed_proficiency`); возвращает (СЛ, слагаемые для лога). `shove.best_save_ability(engine, target) -> str` — `str`/`dex` с большим бонусом спасброска (герой — сумма `saving_throw_parts`, монстр — `ability_modifier`). Оба помощника общие с режимом `save` отбора оружия (шаг 3).
2.2. `shove.may_shove(engine, ref) -> bool`: не герой, `creature_type in cfg.disarm.unarmed_types` (толчок — вариант безоружного удара, SRD 5.2; тем же списком, что и кулак), боеспособен. `available.shove_options(engine, ref)`: при `p.turn.action or attacks_left > 0`; цели — `attack_targets` боеспособные в своей зоне; по строке на каждую соседнюю зону цели: `ActionOption(id=f"shove:{target}:{zone}", kind="shove", label=f"Толкнуть: {имя} → {зона}", params={"target", "zone"})`. Добавить в `list_options` в ту же ветку, что `attack_options`/`disarm_options` (без новой ветки — smells). Герой через меню не толкает (остаётся `improvise push`, Q3).
2.3. `shove.perform(engine, ref, option)`: `spend_attack`; флаг `ActiveEffect(id="shove_used", kind="flag", source=ref)` на монстра (как `disarm_used`); лог `{имя}: толчок → {цель} (СЛ N)`; `dc = contest_dc(engine, ref, ("str",))` (SRD: Сила; Q4); `ability = best_save_ability(engine, target)`; `engine.save(target, ability, dc)`; `fail` → `falling.push(engine, ref, target, zone)`; `success` → лог «устоял», `[]`. `PERFORM["shove"] = shove.perform`. `settle_ground` снимает `shove_used` вместе с `disarmed`/`disarm_used`.
2.4. Политика ИИ (вариант по умолчанию, Q1): `EngineTactics.pick_shove(options, ref)` — среди `kind == "shove"` выбрать вариант с наибольшим `drop_steps(цель.zone → zone)`; вернуть его, только если drop ≥ 1, у монстра нет `shove_used` (один толчок за бой на монстра) и намерение группы `kill` или `drive_off`; при равенстве — первый. Вызов в `choose_turn` после `pick_special` и до `multiattack`. Вровень/вверх ИИ не толкает (сбить в яму — да). Шаг «подняться к герою» после толчка — штатный `step_towards` на следующем ходу.
2.5. Ключевой NPC (`controller="external"`) видит `shove:*` в `combat.options` для `npc_action` — без правок протокола.

### 3. Отбор оружия: режим `save`, `enemy_chance` (В3, В4) — `config/settings.py`, `config/defaults.toml`, `combat/disarm.py`, `combat/engine.py` (`start`), `combat/end.py`
3.1. `DisarmConfig.mode: Literal["check", "save"] = "check"` (Q2), `enemy_chance: int = 0` (`ge=0, le=100`, процент); `[disarm]` в `defaults.toml` с комментариями («check — состязание DMG: бросок атаки против проверки цели; save — спасбросок цели Сил/Лов против СЛ 8 + Сил/Лов + БМ»; «enemy_chance — шанс (%) монстра без тега disarmer получить роль обезоруживающего при старте боя, раз за бой»).
3.2. `disarm.perform`: после подготовки и лога — `won = contest(engine, ref, target, weapon_id, info)`; `contest` ветвится по `cfg.disarm.mode`: `check` — текущие `target_check` + `roll_attack(..., dc=check.total + 1)`; `save` — `mode, label = target_mode(...)` → `base_adv` спасброска цели (двуручный хват/крупнее — преимущество, мельче — помеха, те же подписи); `dc, parts = shove.contest_dc(engine, ref, ("str", "dex"))`; лог `  СЛ {dc} ({слагаемые})`; `engine.save(target, shove.best_save_ability(engine, target), dc, base_adv=mode)`; `fail` → выбито. Атака тратится в обоих режимах, grab и исход — `disarm_target` как сейчас. `apply_disarm` (импровизация) режимом не пользуется (проверка навыка задана рассказчиком).
3.3. `enemy_chance`: в `engine.start()` после `cast.convert_pending_marks`, до инициативы: `disarm.assign_roles(engine)` — если `cfg.disarm.enemy_chance > 0`, для каждого участника `side == "enemies"`, `monster_of`, без тега `disarmer`, с `weapon_ids`-оружием: `rng.randbelow(100) < chance` → `ActiveEffect(id="disarmer", kind="flag", source=ref)`, лог `  {имя} метит выбить оружие` (при 0 — ни одного вызова RNG). `may_disarm`: `"disarmer" in engine.tags(ref) or флаг "disarmer"` и нет `disarm_used`. `settle_ground` снимает `disarmer`.

### 4. Шаг ИИ к оружию (В5) — `combat/controllers.py`
4.1. `EngineTactics.step_to_weapon(options, ref)`: если у монстра есть потерянное оружие (`lost_weapons(...)[1]` непусто) и в своей зоне нет боеспособного врага (`own_zone` пуст, как в `pick_attack`), найти `ground_items` с `disarm.can_pick(engine, ref, item)` в зонах, куда есть `move:*`; вернуть `move:<зона>` (при нескольких — ближайшая к цели / первая). Вызов в `choose_turn` после `pick_shove`, до `pick_attack` (решение В5: оружие важнее стрельбы, если бить рядом некого). Герой (`AutoHeroController` через `EngineTactics`) этим шагом не пользуется (`is_hero` → `None`). Подбор — на том же ходу (`run_controller` перечитывает меню, `pick_special` берёт `pickup`).

### 5. Снаряжение монстра в бою (В9, В10) — `combat/engine.py`, `rules/derived.py`, `combat/actions/attack.py`, `combat/disarm.py`, `combat/trophies.py`, `content/models/monsters.py` (комментарий)
5.1. `engine.start()`: рядом с заведением `npc.creature` — `if npc is not None and p.equipment is None and npc.equipment is not None: p.equipment = npc.equipment.model_copy(deep=True)` (В9: перенос при старте). `CombatEngine.equipment(ref) -> Equipment | None`: `part.equipment`, иначе `world.npcs[ref].equipment` (бой, начатый до К7х, без копии), иначе `None`. `trophies.body_equipment` берёт `worn = engine.equipment(ref)` (минус дубль).
5.2. КД (В9): `derived.armor_dex(armor, dex) -> int` — Лов с учётом `dex_cap` (вынести из `armor_class_parts`, там использовать); `derived.gear_ac(registry, armor_id, shield_id, dex) -> int` = (`armor.ac + armor_dex` | `10 + dex`) + (`shield.ac` | 0). `engine.monster_armor_class(ref, pierce, ignore_magic)` (вынести из `armor_class`, чтобы не растить сложность): `ac = monster.ac`; `worn = self.equipment(ref)`; если не `None`: `ac += gear_ac(worn.armor, worn.shield, dex) - gear_ac(monster.armor, monster.shield, dex)` (природная броня и прочие надбавки `ac` сохраняются; `Equipment()` после обыска: гоблин 15 → 15 − 4 − 2 + 2 = 11); дальше pierce и эффекты как сейчас. Комментарий в `Monster.armor` («КД — число `ac`, по снаряжению не пересчитывается (К7х)») → «`equipment` участника/NPC переопределяет вклад доспеха и щита (`engine.armor_class`)».
5.3. Оружие (В10): `attack.lost_weapons(engine, ref)`: к флагам `disarmed` добавить оружие действий, которого нет в `engine.equipment(ref).weapons` (если `equipment` задан; `None` — как сейчас); порядок без повторов. Через него автоматически: `attacks_of` (нет оружия → `monster_unarmed`), `disarm.weapon_ids`, `strike_info`, `multiattack_options` (`weapons` из `attack_options`), `can_pick`, `body_equipment`. `disarm.pickup` монстра: если флаг `disarmed` на это оружие есть — снять (как сейчас); иначе (потеряно по `equipment`) — `engine.equipment(ref).weapons.append(item_id)` (копия участника). `mark_looted` — без изменений (NPC после обыска бьёт кулаком или ничем).

### 6. Истребитель орд (В7) — `combat/actions/features.py`, `combat/actions/attack.py` (`perform`), `combat/available.py`, `combat/engine.py` (`PERFORM`), `combat/controllers.py`, `srd/data/features/horde_breaker.yaml`
6.1. `features.horde_mark(engine, ref, info, target_ref)`: герой, `"horde_breaker" in hero_feature_ids`, `info.weapon_id is not None`, флага ещё нет → `ActiveEffect(id="horde_breaker", source=ref, kind="flag", params={"weapon": info.id, "target": target_ref, "zone": engine.part(target_ref).zone_id, "used": False}, expires=Expiry(kind="end_of_turn", value=0, owner=ref))`. Вызов в `attack.perform` после `attack(...)` (любая атака оружием в свой ход, попадание не нужно; вторая атака Доп. атаки флаг не дублирует; провоцированная атака — мимо). Снимается `engine.expire("end_of_turn", ref)`.
6.2. `available.horde_options(engine, ref)`: флаг есть и `not used` → для `attack_targets` в зоне `params["zone"]`, кроме `params["target"]`, с `info = attacks_of` по `params["weapon"]` и `base_advantage(...) is not None`: `ActionOption(id=f"horde_breaker:{target}", kind="horde_breaker", label=f"Истребитель орд: {оружие} → {имя}", params={"weapon", "target"}, cost="free")`. В `list_options` — строкой рядом с `pickup_options` (без условия на действие: атака бесплатная).
6.3. `features.horde_breaker(engine, ref, option)`: `params["used"] = True`; `info` по `params["weapon"]`; `return attack.attack(engine, ref, option.params["target"], info)` без `spend_attack`. `PERFORM["horde_breaker"]`. Убийца колоссов на этой атаке — по общему `colossus_used` (раз в ход, SRD).
6.4. `AutoHeroController.choose_turn`: первым делом `kind == "horde_breaker"`, если есть (бесплатная атака). `horde_breaker.yaml`: описание без «В движке боя не считается…» → «Движок: после атаки оружием раз в ход — пункт меню «Истребитель орд» по другой цели в зоне первой.»

### 7. Смена Добычи после отдыха (В8) — `protocol/requests.py`, `protocol/handlers/resources.py`, `rules/progression.py`
7.1. `Rest.prey_swap: str = Field("", description="Смена приёма Добычи охотника после отдыха (следопыт 3+): id варианта colossus_slayer или horde_breaker; пусто = без смены.")`, `NEUTRAL` + `"prey_swap": ""`. Любой `kind` (SRD: короткий или продолжительный).
7.2. `progression.feature_swap_problem(hero, registry, feature_id, option) -> tuple | None`: умение не в `hero_feature_ids` или без `options` → `("no_feature", …)`; вариант не из `options` → `("unknown_option", … допустимые …)`; уже выбран → `("same_option", …)`. `progression.swap_feature_choice(hero, registry, feature_id, option)` → `sheet.feature_choices[feature_id] = [option]`.
7.3. `resources.py`: `PREY_FEATURE = "hunters_prey"`; `swap_invalid` → дополнительно `prey_invalid` (Invalid до отдыха, бандл не тронут); `apply_swap` → `apply_prey`: лог `Добыча охотника: {новое} (было: {старое})`, `result["prey"] = option`. Держать `rest` плоским: две проверки — через список `(spec, checker)` или два вызова, не вложенные `if`.

### 8. BACKLOG 51 (В12) — `content/models/common.py`, `rules/roll_pipeline.py`, `content/loader.py`
8.1. `DAMAGE_TYPE_WORDS` переезжает в `content/models/common.py`; `roll_pipeline.py` импортирует оттуда (прежнее имя остаётся — `attack.py` и прочие импорты не меняются); `loader.py:19` импортирует из `content.models.common`. Тест-страж: `grep`-тест «в `src/ai_dm/content/` нет `from ai_dm.rules`».

### 9. Docs
`docs/BACKLOG.md`: 11 — «Метка 8/24 ч → К8+ (В6, 2026-10-14: ячейки 3 круга у следопыта с 9 ур.); Истребитель орд ✅ К7х; смена Добычи ✅ К7х (`rest.prey_swap`)»; :237 «(8/24 ч — К7х)» → «К8+»; 38 з ✅ К7х (падение при `push`, `elevation` × 10 фт); 51 ✅ К7х. `docs/ROADMAP.md:25`: К7х ✅ факт расхода, убрать «+ уровни 2–5 сетки, если перенесены» (В11), отметить «R5:164 высота зоны в Ж0 не нужна (В1б)». `docs/plan-roadmap-r2.md:202` — строка К7х ✅. `docs/ARCHITECTURE.md` п. 17: режим `[disarm].mode`, `enemy_chance` (роль-флаг при старте), шаг к оружию, толчок монстров (`shove:*`, политика ИИ), падение (`combat/falling.py`, формула, `prone`), `equipment` в бою (КД, потерянное оружие, перенос при старте), Истребитель орд (`horde_breaker` флаг/пункт), `prey_swap`; п. 18 — `pick_shove`, `step_to_weapon`. `docs/TZ.md:553` — «оттолкнуть (в зону ниже — падение)». `docs/HANDOFF.md` — строка К7х. Чек-лист `checklist-k7x-live.md` (не коммитить; живой прогон — общий на К7 после К7д): (1) бой на крыше (`elevation` 1 → 0): `push` героя через импровизацию → «падает с высоты 10 фт», урон 1d6, «сбит с ног»; (2) гоблин на крыше толкает героя (намерение kill) — один раз за бой; (3) `/difficulty`-мир без высоты — толчков монстров нет; (4) `[disarm] mode = "save"` в `~/.config/ai-dm/config.toml` → обезоруживание со спасброском, лог «СЛ N»; (5) `enemy_chance = 100` → «метит выбить оружие», гоблин выбивает один раз; (6) выбитый у гоблина скимитар — герой отходит, гоблин идёт за оружием и подбирает; (7) следопыт 3 ур. с `horde_breaker` → после атаки пункт «Истребитель орд» по второму гоблину в зоне; `rest short` с `prey_swap: colossus_slayer` → лог смены; (8) именованный NPC после обыска (К7к) во втором бою бьёт кулаком, КД ниже на доспех и щит; (9) `--replay-report` старого хода с `rest` — ожидаемо код 1 (схема), нового — 0.

## Изменённые функции для mutmut (`make mutate FUNCS=… TESTS=…`)
- `ai_dm.combat.zones:drop_steps ai_dm.combat.falling:fall_dice ai_dm.combat.falling:fall ai_dm.combat.falling:push ai_dm.combat.actions.improvise:apply_push` — TESTS tests/unit/combat/test_falling.py tests/unit/combat/test_improvise.py
- `ai_dm.combat.shove:contest_dc ai_dm.combat.shove:best_save_ability ai_dm.combat.shove:may_shove ai_dm.combat.shove:perform ai_dm.combat.available:shove_options ai_dm.combat.controllers:EngineTactics.pick_shove` — TESTS tests/unit/combat/test_shove.py tests/unit/combat/test_shove_tactics.py
- `ai_dm.combat.disarm:perform ai_dm.combat.disarm:contest ai_dm.combat.disarm:may_disarm ai_dm.combat.roles:assign_roles ai_dm.combat.engine:CombatEngine.start ai_dm.combat.end:settle_ground` — TESTS tests/unit/combat/test_disarm_save.py tests/unit/combat/test_disarm_roles.py tests/unit/combat/test_disarm.py tests/unit/combat/test_disarm_end.py
- `ai_dm.combat.controllers:EngineTactics.step_to_weapon ai_dm.combat.controllers:EngineTactics.choose_turn ai_dm.combat.controllers:AutoHeroController.choose_turn` — TESTS tests/unit/combat/test_disarm_tactics.py tests/unit/combat/test_controllers.py tests/unit/combat/test_horde_breaker.py
- `ai_dm.combat.engine:CombatEngine.equipment ai_dm.combat.engine:CombatEngine.monster_armor_class ai_dm.rules.derived:armor_dex ai_dm.rules.derived:gear_ac ai_dm.combat.actions.attack:lost_weapons ai_dm.combat.disarm:pickup ai_dm.combat.trophies:body_equipment` — TESTS tests/unit/combat/test_equipment_in_combat.py tests/unit/rules/test_derived.py tests/unit/combat/test_trophy_armor.py tests/unit/combat/test_pickup.py
- `ai_dm.combat.actions.features:horde_mark ai_dm.combat.actions.features:horde_breaker ai_dm.combat.available:horde_options ai_dm.combat.actions.attack:perform` — TESTS tests/unit/combat/test_horde_breaker.py tests/unit/combat/test_actions_attack.py
- `ai_dm.rules.progression:feature_swap_problem ai_dm.rules.progression:swap_feature_choice ai_dm.protocol.handlers.resources:rest ai_dm.protocol.handlers.resources:swap_invalid ai_dm.protocol.handlers.resources:apply_swap` — TESTS tests/unit/protocol/test_apply_rest_prey.py tests/unit/protocol/test_apply_rest_swap.py tests/unit/rules/test_progression_choices.py
- `ai_dm.content.loader:check_monster_gear` (импорт) — TESTS tests/unit/content/test_content_loader.py tests/unit/content/test_layers.py (grep-тест)

## Тесты (kaban-doeba, TDD; параллельно с kaban)

Правка существующих: `test_disarm.py`/`test_disarm_details.py` шапка (режим `check` по умолчанию — поведение прежнее; `mode = save` — отдельный файл); `test_disarm_tactics.py` шапка (`pick_special` + `pick_shove` + `step_to_weapon`, порядок); `test_improvise.py` шапка (`push` в зону ниже — падение, события); `test_pickup.py` (подбор монстром оружия, потерянного по `equipment`); `test_trophy_armor.py` (`body_equipment` через `engine.equipment`); `test_schema_fingerprint` — зелёный без правок (новых полей сейва нет); `tests/golden`/`test_criterion1.py`/`test_sim_grid` — зелёные без правок (нет `elevation`, `equipment`, `enemy_chance` 0, `mode` check); `test_stage4_memory` — без подъёма WINDOW; тесты схемы инструментов (`protocol/schema`) — `Rest.prey_swap` в strict-схеме.

Падение (`tests/unit/combat/test_falling.py`; `make_zones` с `elevation`: `balcony` 1, `hall` 0, яма −1; `ScriptedRng`): `drop_steps` 1→0 = 1, 0→−1 = 1 (яма), 0→1 = 0, 2→0 = 2; `fall_dice`: 1 ступень → `1d6`, 3 → `3d6`, 25 ступеней (250 фт) → `20d6` (потолок), 0 → `None`; `fall_step_ft = 5` в cfg → 2 ступени = `1d6`; `fall`: лог «падает с высоты 10 фт», строка урона «Падение», дробящий через `engine.damage` (монстр с `damage_immunities: [bludgeoning]` → 0 и **не** лежит; сопротивление — половина), `prone` с `source="fall"` при уроне > 0, `after_damage` события (гоблин с 2 HP умирает от падения → событие/XP как от удара; герой 0 HP → `down`, спасброски); `improvise push` в `hall` с `balcony` → перемещение + падение одним действием; `push` вровень — урона нет (регресс); `push` вверх — без урона; в начале хода упавший встаёт (`stand_up`), `move = 0`, затем выходит из ямы обычным `move:*` (В14); мутант «без `prone`»/«без потолка» умирает.

Толчок монстров (`tests/unit/combat/test_shove.py`, `test_shove_tactics.py`): `shove_options` у гоблина (fey ∈ `unarmed_types`) с героем в зоне — по строке на соседнюю зону, id `shove:hero:hall`; у героя пунктов `shove` нет; у монстра не из `unarmed_types` (подставной `beast`) — нет; без действия и `attacks_left` — нет; `perform`: тратит атаку, `shove_used`, СЛ = 8 + Сил + 2 (гоблин Сил 8 → 9), спасбросок героя лучшей из Сил/Лов (воин Сил 16 → `str`; плут — `dex`), провал → герой в `hall`, падение, `prone`; успех → «устоял», герой на месте; второй `shove` того же монстра в бою недоступен ИИ, но в меню ключевого NPC есть; `settle_ground` снимает `shove_used`. Тактика: гоблин на балконе (1) с героем, `hall` (0) рядом, намерение `kill` → `pick_shove` даёт `shove:hero:hall`; с намерением `capture`/`spare` — `None`; зоны вровень — `None`; две соседние ниже (−1 и 0) — выбирает большую разницу; после `shove_used` — атакует; порядок `choose_turn`: escape/pickup/disarm раньше толчка, толчок раньше мультиатаки; `MasterChoiceController`/external — опции в `combat.options` (протокол `npc_action` принимает `shove:*`).

Отбор оружия (`test_disarm_save.py`, `test_disarm_roles.py`): cfg `mode="save"`: герой выбивает скимитар — лог «СЛ N (8 + Сил/Лов + БМ)», гоблин бросает спас лучшей характеристикой (Лов 14 > Сил 8 → `dex`), провал → выбито, успех → у цели; двуручный хват цели → спасбросок с преимуществом (подпись «двуручный хват»), мельче → помеха; атака тратится в обоих исходах; `check` — байт-в-байт прежние логи (`test_disarm.py`); `cfg.disarm.mode = "foo"` → `ValidationError`; `enemy_chance`: 0 → `engine.start()` не трогает RNG (длина очереди `ScriptedRng` прежняя), флагов нет; 100 → у каждого вооружённого врага без тега флаг `disarmer`, лог «метит выбить оружие»; 50 с `ScriptedRng(percent=[10, 90])` → первый получил, второй нет; монстр с тегом `disarmer` не бросает; герой-«враг» (переговоры) не бросает; `may_disarm` по флагу → `disarm_options` есть, `EngineTactics` выбивает один раз, дальше атакует; `settle_ground` снимает `disarmer`; `enemy_chance = 101` → `ValidationError`.

Шаг к оружию (`test_disarm_tactics.py`): гоблин без скимитара в `hall`, оружие в `door` (переложить `GroundItem.zone_id`), герой на балконе: ход гоблина → `move:door`, затем на том же ходу `pickup`; герой в зоне гоблина → бьёт кулаком, не идёт; оружие в зоне через одну (`make_line(4)`) → `move` в сторону оружия, не `dash`? (решить по коду: `step_to_weapon` — только соседняя зона, иначе штатная тактика к врагу; тест фиксирует); чужое оружие (owner другой монстр) — не идёт; без потерь — не идёт; авто-герой без оружия — не идёт (поведение `AutoHeroController` прежнее).

Снаряжение в бою (`test_equipment_in_combat.py`): именованный гоблин с `npc.equipment = Equipment()` → после `engine.start()` у участника копия, `armor_class` 11 (15 − 4 − 2 + 2… ровно по формуле: `gear_ac(None, None, dex 2) = 12`, `gear_ac(leather, shield, 2) = 15` → 15 − 15 + 12 = 12; зафиксировать число по данным), `attacks_of` → только безоружный удар (fey), `disarm_options` героя пусты; `equipment = Equipment(armor=None, shield="shield", weapons=["scimitar"])` → КД без доспеха, скимитар есть, лук «потерян»; `Equipment(armor="chain_mail", shield=None, weapons=[...])` → КД 16 + 0 Лов (dex_cap 0) + 0; `equipment=None` — КД и атаки как раньше (регресс на трёх монстрах); подставной монстр с природной бронёй (`ac` 17, `armor: None`) и `equipment=Equipment(armor="leather_armor")` → 17 − (10+dex) + (11+dex) = 18; pierce поверх пересчёта; `pickup` монстром «потерянного по equipment» скимитара → добавлен в `equipment.weapons`, `attacks_of` снова с ним; `mark_looted` в конце → NPC `Equipment()`; участник безымянный с `equipment` — `engine.equipment` отдаёт его; `body_equipment` прежние тесты зелёные; `derived.gear_ac`/`armor_dex` на герое — `armor_class_parts` байт-в-байт (мутмут на `dex_cap`).

Истребитель орд (`test_horde_breaker.py`; следопыт 3 ур. с `feature_choices={"hunters_prey": ["horde_breaker"]}` через `make_fighter`-аналог/`build_character`, два гоблина в зоне): после `attack:longsword:g1` (попал или промахнулся) появляется `horde_breaker:g2` (`cost free`), нет `horde_breaker:g1`; `perform` → вторая атака без траты `attacks_left`/действия, лог; второй раз в ход пункта нет; в следующем ходу — снова после атаки; безоружный удар/импровизированное флаг не ставят; гоблин в другой зоне — пункта нет; лук: цель в зоне первой, дальность по `base_advantage`; флаг снимается в конце хода (после `step()` эффекта нет); с `colossus_slayer` — пункта нет; Убийца колоссов на второй атаке не срабатывает повторно (`colossus_used`); `AutoHeroController` берёт пункт первым; провоцированная атака флаг не ставит; флаг `horde_breaker` в сейве боя (`ActiveEffect`) — сериализуется (`test_save_combat_extras`-подобный раунд-трип).

Смена Добычи (`tests/unit/protocol/test_apply_rest_prey.py`, по образцу `test_apply_rest_swap.py`, следопыт-охотник 3 ур., собранный явно (Грей из drunk_dragon — beast_master, даёт no_feature)): `rest short prey_swap: horde_breaker` → отдых применён, `feature_choices["hunters_prey"] == ["horde_breaker"]`, лог «Добыча охотника: Истребитель орд (было: Убийца колоссов)», `result["prey"]`; `long` — то же; `prey_swap: ""` → поле `None`, без смены; `colossus_slayer` при уже выбранном → `Invalid same_option`, бандл байт-в-байт; `prey_swap: foo` → `Invalid unknown_option` с допустимыми; воин → `Invalid no_feature`; `prepared_swap` + `prey_swap` вместе на `long` — оба применены; `rest_impossible` (0 HP) — Добыча не меняется; в следующем бою `hero_feature_ids` содержит новый вариант (Истребитель орд доступен, Убийца колоссов — нет); strict-схема `Rest` содержит `prey_swap` (`protocol/schema` тест).

Контент/слои: `DAMAGE_TYPE_WORDS` доступен из `content.models.common` и `rules.roll_pipeline` (один объект); grep-тест «`src/ai_dm/content/` не импортирует `ai_dm.rules`»; `check_monster_gear` прежние тесты зелёные.

Общее в конце: `uv run pytest -q`, `make cov` (≥ 94 %), `make smells` (≤ 206 — см. риски), `make dead` (новые функции — в allowlist только с согласия), `uv run ruff check src tests`; mutmut по списку выше; `make sim-grid` один раз (`--check` зелёный, базовая линия без перегенерации) и golden `goblins3_win.txt` без изменений.

## Критерии приёмки
1. `push` (импровизация героя и толчок монстра) в зону ниже — урон 1d6 за 10 фт (ступень = `fall_step_ft`, потолок 20d6) через `engine.damage`, `prone` при уроне > 0, события падения; вровень/вверх — как раньше; яма — так же; выход из ямы движением (R5:244: бой на крыше `elevation` 1 → 0 даёт урон и `prone`).
2. Монстры из `unarmed_types` имеют `shove:<цель>:<зона>` (атака, СЛ 8 + Сил + БМ, спас цели Сил/Лов лучшей); ИИ толкает по политике Q1 (ниже, kill/drive_off, раз за бой); ключевой NPC видит пункт.
3. `[disarm].mode` check/save (save: спас цели против 8 + Сил/Лов + БМ, модификаторы хвата/размера как преимущество/помеха), `enemy_chance` — роль при старте без расхода RNG при 0; монстр идёт к своему оружию в соседней зоне, когда бить рядом некого.
4. `equipment` участника/NPC (копия при старте) меняет КД по формуле В9 и список оружия (В10); обобранный NPC бьёт кулаком с КД без доспеха и щита; `equipment=None` — поведение прежнее.
5. Истребитель орд — пункт `horde_breaker:<цель>` после атаки оружием раз в ход, бесплатная атака по цели в зоне первой; `rest.prey_swap` меняет Добычу на коротком и продолжительном отдыхе с проверками до отдыха.
6. Тесты зелёные, cov ≥ 94 %, smells ≤ 206, сейв v9 (отпечаток без правок), golden и `sim_grid_baseline` без перегенерации, WINDOW не поднят; content не импортирует rules.
7. Docs: BACKLOG 11/38 з/51, ROADMAP :25 (В11, Ж0-отметка), ROADMAP-PLAN :202, ARCHITECTURE п. 17–18, TZ :553, HANDOFF; чек-лист живого прогона.

## Оценка
S+/M− ≈ 0,8 млн по шкале R6 (груминг: 0,75–0,85): kaban ~180–220 тыс. (~25 мин; два новых модуля `falling`/`shove`, правки в 10 файлах боя, протокол `Rest`, перенос константы); kaban-doeba ~400–480 тыс. (~2,5 ч с mutmut: ~110 тестов, 8 файлов новых, 6 правок шапок); mama-kaban ~40 тыс. Прогон `make sim-grid` один раз (3–6 мин) — только как проверка неизменности.

## Риски / на что обратить внимание
- **Smells 204/206, запас 2.** Растут `EngineTactics.choose_turn` (+2 вызова), `list_options` (+2 строки), `engine.armor_class`, `disarm.perform`, `resources.rest`. Обязательно выносить: `monster_armor_class`, `disarm.contest`, `pick_shove`/`step_to_weapon`, `apply_prey`/`prey_invalid`; `shove_options` — в существующую ветку `attack_options`. Если `qlty` всё же даёт 207 — упростить `list_options` (сгруппировать «пункты без условий» в один `options += pickup_options(...) + horde_options(...)`), лимит не поднимать.
- **RNG и golden.** Любой новый бросок в `engine.start()` или в ходу гоблина без высоты сдвинет `goblins3_win.txt`, `test_criterion1` и базовую линию сетки. `assign_roles` — ни одного `randbelow` при `enemy_chance = 0`; `pick_shove` возвращает `None` без разницы высот; `step_to_weapon` — только при потерянном оружии. Падение golden — баг, не повод перегенерировать.
- **Сейв v9.** Никаких полей в `TurnState`/`Participant`/`CombatState`/`Zone`; флаги `shove_used`, `disarmer`, `horde_breaker` — `ActiveEffect` (сериализуется как есть). `settle_ground` снимает `shove_used`/`disarmer`; `horde_breaker` живёт до конца хода героя.
- **Схема запросов меняется** (`Rest.prey_swap`, текст `push`): `request_fingerprint` старых журналов разойдётся → `--replay-report` старых репортов с `rest`/боем даст код 1 (прецедент К1/AD1 Q4); новые — штатно. Отметить в HANDOFF/чек-листе.
- **Копия `equipment` при старте** (В9): подбор монстром «потерянного по `equipment`» оружия пишется в копию участника; у выжившего необобранного NPC копия пропадает (его `NPC.equipment` не менялось — выбитое оружие он и так теряет по `settle_ground`). Для обобранного NPC `mark_looted` пишет `Equipment()` в NPC — согласовано.
- **`disarm.pickup` монстра** сейчас падает `IndexError`, если флага нет; после 5.3 ветка «потеряно по equipment» обязательна и покрыта тестом.
- **Иммунный к дробящему при падении** — урон 0, `prone` не ложится (SRD); конструкты К7д — по данным. Концентрация героя при уроне от падения — тем же путём, что у прочего урона (`after_damage`), проверить тестом, что ничего не теряется.
- **Монстр с луком и потерянным скимитаром** по В5 идёт за оружием вместо стрельбы, если в зоне бить некого — так решено; `ranged`-монстры без потерь не затронуты.
- **WINDOW мока** (пик 19666/20000): правило В15 — одно предложение (~40 токенов); при превышении ужать `narrator_rules.md:44`/`:64`, как в К7к, не поднимать WINDOW.
- **Истребитель орд и Доп. атака** (следопыт 5): флаг ставится первой атакой, вторая атака действия его не дублирует; пункт `horde_breaker` доступен и при `attacks_left > 0`, и после — не путать с «ещё N из 2».
- **Mutmut на macOS** — segfault (BACKLOG 16): узкие TESTS.

## Открытые вопросы
- **Q1 Политика толчка ИИ.** (а) **рекомендация** — монстр из `unarmed_types` толкает цель в своей зоне в соседнюю зону с меньшей `elevation` (разница ≥ 1), один раз за бой на монстра (`shove_used`), только при намерении группы `kill` или `drive_off` (capture/spare/rob — нет: сброс с высоты может убить); приоритет после escape/pickup/disarm, до мультиатаки/атаки; вровень и вверх не толкает; (б) без ограничения «раз за бой» — на крыше каждый гоблин каждый ход сталкивает героя, бой на высоте становится смертельным; (в) только монстры с тегом `shover` (как `disarmer`) — поведение невидимо до К7д.
- **Q2 Значение `[disarm].mode` по умолчанию.** (а) **рекомендация** — `check` (состязание DMG, как сейчас; golden, тесты и логи не меняются; `save` включается в конфиге); (б) `save` по умолчанию — проще (один бросок цели), ближе к SRD 2024 Shove/Disarm-подобным механикам, но меняет видимое поведение и логи `test_disarm*`.
- **Q3 Толчок героя.** (а) **рекомендация** — герой толкает только через `improvise push` (как сейчас, рассказчик задаёт навык и СЛ); (б) добавить герою пункт меню `shove:*` по тем же правилам, что монстру (SRD 5.2: безоружный удар-толчок) — рост объёма и меню, по решению В2 не требовалось.
- **Q4 СЛ толчка монстра.** (а) **рекомендация** — 8 + Сил + БМ (SRD 5.2, Shove — только Сила); спас цели — Сил или Лов лучший (как В3); (б) 8 + лучший из Сил/Лов + БМ — единообразно с В3 для отбора оружия, одна формула на оба состязания.

**Ответы проектировщика (2026-10-14): Q1 (а), Q2 (а), Q3 (а), Q4 (а) — всё по рекомендациям.** Аппрув и «окей, кабаним»
подтверждены проектировщиком дословно 2026-10-14 («подтверждаю», по аудиту docs/plan-k7x.md).

## Отклонения при реализации
Текст отчёта kaban (номера — как в docs/plan-k7x.md; вписано оркестратором после аудита).
1. `drop_steps` лежит в `combat/zones.py`, а не в `falling.py`: `controllers.py` не может импортировать `falling` из-за цикла импортов.
2. `assign_roles` — в новом `combat/roles.py`, а не в `disarm.py`: иначе сложность `disarm.py` превышала порог qlty (smells 208).
3. Режим `save` вынесен в `shove.save_contest`, `disarm.contest` его вызывает (причина та же; по ревью ветка затем перенесена в `disarm.contest`).
4. `engine.save` не получил параметра `base_adv_label`; подпись «двуручный хват/мельче» дописывается в строку лога `СЛ N (8 + Сил X + мастерство Y); <подпись>`.
5. В `controllers.py` добавлен `pick_early` — цикл по `pick_special`, `pick_shove`, `step_to_weapon`; без него у `choose_turn` слишком много `return`.
6. Константа `FALL_DICE_PER_10FT` заменена на `FALL_DIE = "d6"` (vulture: неиспользуемая константа).
7. Часть импортов в `controllers.py` и `features.py` локальная (`step_to_weapon`, `horde_breaker`) — циклы импортов.
8. В `horde_breaker.yaml` «Движок —» вместо «Движок:» (двоеточие ломало YAML; по ревью исправлено на «Движок: …» в кавычках).
9. Истребитель орд у `AutoHeroController` проверяется вместе со `stabilize`, после Второго дыхания, а не «первым делом» — лимит `many returns`; на исход боя не влияет.
10. `Rest.prey_swap` при `old` читал `feature_choices[PREY_FEATURE][0]` без защиты от пустого выбора — по ревью исправлено (код `no_choice`, тест).

Расход papa-kaban ≈ 185 тыс. (субагентный счётчик).

## Решения: Груминг партии К7х — хвосты боя (свинопас, 2026-10-14) (бывш. docs/decisions/k7x-grooming.md)

Вписано оркестратором (у свинопаса нет Write).

Источники:
- ROADMAP:25 (#13–16);
- roadmap-r5-proposal:17, 127–132, 161, 164, 244, 284, 296;
- roadmap-r4-unified:61 (#10), :169;
- ROADMAP-PLAN:202;
- K7K-PLAN:10–12, 89, 106, 153, 301, «Отклонения» :342–350;
- k7k-review, k7k-sim-grid, k7k-grooming В6/В8;
- BACKLOG 11 (:121), 38 з (:448), 50, 51, :237;
- HANDOFF:175–225;
- COMBAT-DISARM-PLAN:44, 111, 164.

Код на 4fc2ce8: `combat/disarm.py`, `combat/actions/{improvise,attack}.py`, `combat/{engine,controllers,available,trophies,zones}.py`, `state/{combat,creature,world,hero}.py`, `rules/{derived,spellcasting,damage,progression}.py`, `protocol/{requests,handlers/resources,handlers/combat}.py`, `config/settings.py`, `config/defaults.toml`, `srd/data/{spells/hunters_mark,features/horde_breaker,features/hunters_prey,tables/spell_slots_half,monsters/*}.yaml`.

### Объём К7х по источникам
1. Хвосты отбора оружия по R4 #10: `[disarm].mode = save`, `enemy_chance`, шаг ИИ к оружию в соседней зоне.
2. Мелочи следопыта по R4 #10 и BACKLOG 11:
   - перенос Метки — уже ✅ (BACKLOG:121);
   - Метка 8/24 ч от круга;
   - Истребитель орд;
   - смена Добычи после отдыха.
3. 38 з: урон от падения при `push`. По R5 это параметр запроса, без поля зоны.
4. Из К7к:
   - пересчёт КД по `equipment` (В6);
   - чтение `equipment.weapons` в бою;
   - уровни 2–5 сетки, «если перенесены».

### Готовность

**Не готова к плану до ответов на В1, В3, В6 и В9** (блокирующие). Остальное закрывается по рекомендации.

Расхождения источников с кодом:
- **У зоны уже есть поле высоты.** `Zone.elevation: int` (`state/combat.py:43`) есть в запросе (`protocol/requests.py:53`), в обработчике (`handlers/combat.py:92`), в модификаторе атаки (`combat/zones.py:59–67`, `attack.py:217`), на карте (`game/battle_map.py:31`) и в правиле рассказчика (`narrator_rules.md:28`). R5 исходил из того, что поля высоты нет, и предлагал параметр запроса либо поле в Ж0. Но `elevation` хранит условные ступени («1 и больше»), а не футы, и перевести их в кубы падения нечем (В1).
- **Метку 8/24 ч в игре не получить.** SRD 5.2 даёт 8 ч на ячейке 3–4 круга и 24 ч на ячейке 5+. Ячейки 3 круга у полузаклинателя появляются только с 9 уровня (`spell_slots_half.yaml:18–20`; на 5 ур. есть только круги 1–2, `:10–11`), а классы в движке есть только до 5 уровня. Сделанное увидит только тест (В6).
- **Уровни 2–5 сетки в К7х не переносились.** Они сделаны в К7к: таблица 1–5 в docs/plan-k7k.md, `devtools/sim_grid_baseline.yaml`. Хвост «если перенесены» в ROADMAP:25 пуст, его нужно убрать из строки (В11).
- **`equipment` почти никто не пишет.** Записывает его только `mark_looted`, и только `Equipment()` у NPC (`combat/trophies.py:55`). `Participant.equipment` всегда `None`: поле никто не заполняет, при старте боя из NPC оно не копируется. Поэтому у «пересчёта КД» и «чтения `weapons`» сейчас одна видимая точка: обобранный, но выживший именованный NPC в следующем бою (В9, В10).

### Что есть в коде (факты)

1. **Отбор оружия.**
   - В `DisarmConfig` (`config/settings.py:73`, `extra=forbid`) и `[disarm]` (`defaults.toml:44`) только `unarmed_types` и `unarmed_proficiency`. Полей `mode` и `enemy_chance` нет.
   - Проверка цели: `target_mode` и `target_check` (`disarm.py:68`, `:84`), спасброска нет. В COMBAT-DISARM-PLAN:164 задана формула режима save: «СЛ 8+мод+БМ, спас цели».
   - Монстр выбивает только с тегом `disarmer`, один раз за бой (`may_disarm`, `disarm.py:20–25`). Ни у одного из трёх монстров этого тега нет.
   - Выбитое оружие всегда падает в зону цели (`disarm_target`, `disarm.py:148–152`). Подобрать его можно только в своей зоне (`pickup_options`, `available.py:359`).
   - ИИ подбирает оружие первым делом, если оно лежит рядом (`controllers.py:61–71`). К оружию в соседней зоне ИИ не идёт: такого шага нет.
2. **Толчок и падение.**
   - `apply_push` (`improvise.py:98–102`) только переносит цель в соседнюю зону, урона нет. Толкает только герой (`check_request` → `not_a_hero`, `:45`).
   - Урон вне боя по тяжести: `hazard_dice`/`roll_hazard` (`rules/damage.py:111–135`, таблица `damage_severity`). В бою весь урон идёт через `engine.damage`.
   - В `ImproviseSpec` (`requests.py:86–100`) поля под высоту или тяжесть падения нет.
3. **Метка охотника.**
   - В `hunters_mark.yaml` нет `upcast`, `duration: 1h`. Поэтому круг выше 1 даёт `bad_circle` (`circle_allowed`, `rules/spellcasting.py:52–56`, `:101–105`).
   - Длительность одна на заклинание: `spell.duration_s` (`spellcasting.py:197`, `:214–220`). Длительности по кругу в модели нет.
4. **Истребитель орд.** Данные есть (`features/horde_breaker.yaml`, «в движке боя не считается»). В бою считается только Убийца колоссов (`attack.py:294`).
5. **Смена Добычи.**
   - Выбор лежит в `sheet.feature_choices` (`state/hero.py:62`). Пишут его только создание героя и повышение уровня (`game/app.py:302`, `rules/progression.py:362`).
   - У запроса `Rest` (`requests.py:399–409`) есть `prepared_swap`, а поля для смены выбора умения нет.
6. **КД монстра.**
   - `engine.armor_class` (`engine.py:191–203`) берёт число `monster.ac` плюс эффекты `ac`. `equipment` при этом не читается.
   - У героя есть формула по доспеху: доспех + Лов до предела + щит (`rules/derived.py:120–147`).
   - По этой формуле статблоки сходятся с `ac`: goblin_warrior 11+2+2=15, goblin_boss 13+2+2=17, guard 13+1+2=16.
7. **Оружие монстра в бою.**
   - `attacks_of` и `weapon_ids` монстра читают `monster.actions` за вычетом выбитого (`attack.py:58`…, `disarm.py:28–42`).
   - `equipment.weapons` учитывает только `body_equipment` для трофеев (`trophies.py:24–36`). Оружие у обобранного NPC (`weapons=[]`) из трофеев пропадёт, но в бою он продолжит бить им по статблоку.
8. **Схема.** Сейв не меняется ни в одном пункте: `elevation`, `feature_choices` и `equipment` уже есть в v9, конфиг и поля запросов в сейв не входят. Smells 204/206, запас 2 (HANDOFF:225).

### Вопросы

**В1 (блок.) Откуда берётся высота падения.**
- (а) Параметр запроса импровизации, как в R5: например, `drop: none/nuisance/dangerous/deadly` по `damage_severity` или высота в футах.
- (б) Разница `elevation` между зонами × N футов (N в конфиге, например 10 фт на ступень), по SRD 1d6 за 10 фт, не больше 20d6. Схема не меняется.
- (в) По умолчанию (б), параметр запроса может переопределить.

Рекомендация: **(б)**. Поле уже есть, и ИИ его ставит. С (а) у рассказчика будет два несогласованных источника высоты. N решает проектировщик.

**В2. Когда наступает падение.**
- (а) Только `push` в зону ниже.
- (б) Плюс сбитый с ног на краю.
- (в) Плюс любое движение вниз.

Отдельно: класть ли `prone` при падении (SRD 5.2: упавший сбит с ног, если урон не нулевой) и что делать с героем (его толкать сейчас некому).

Рекомендация: **(а)** + `prone` через `engine.impose`.

**В3 (блок.) `[disarm].mode = save`.**
- Спасбросок Сил или Лов, на выбор цели (лучший)? Или фиксированный?
- СЛ: 8 + мод + БМ, но какой характеристики атакующего?
- Режим на всех или только на монстров?

Варианты:
- (а) спас Сил/Лов на выбор цели, СЛ 8 + Сил/Лов + БМ атакующего, для всех;
- (б) только Сил;
- (в) режим отдельно для героев и монстров.

Рекомендация: **(а)**. Ответ нужен до плана.

**В4. `enemy_chance`.**
- Что это: шанс в процентах на каждый ход монстра с оружием или однократный бросок при старте боя, который выдаёт роль «disarmer»?
- Лимит «раз за бой» сохраняем?

Варианты:
- (а) бросок раз за бой при старте, по умолчанию 0;
- (б) шанс каждый ход;
- (в) снять пункт.

Рекомендация: **(а)**: не ломает «иначе только и выбивает» (`disarm.py:21`).

**В5. Шаг к оружию в соседней зоне.**

Оружие падает всегда в зону цели. В соседней зоне оно окажется, только если монстр ушёл или его толкнули.
- (а) Если в своей зоне нет врага в досягаемости, монстр идёт к своему оружию.
- (б) Оружие всегда важнее атаки.
- (в) Снять пункт как редкий.

Рекомендация: **(а)**.

**В6 (блок.) Метка 8/24 ч.** Получить её нельзя до 9 ур. следопыта (ступень II).
- (а) Сделать сейчас общий механизм «длительность по кругу» (`upcast` с `duration`), проверка только тестом.
- (б) Перенести пункт в К8+, к уровням 6–20, там же поправить BACKLOG 11 и :237.
- (в) Только данные `upcast` без длительности.

Рекомендация: **(б)**. Это не трогает видимое поведение и снимает объём.

**В7. Истребитель орд.** Условие «в пределах 5 фт от первой цели» = «та же зона»?
- (а) После попадания (или любой атаки?) раз в ход появляется пункт меню «вторая атака» по другой цели в зоне первой.
- (б) Атака автоматическая.
- (в) ИИ `auto_hero` учит в сетке.

Рекомендация: **(а)**. Попадание или любую атаку решает проектировщик. В SRD 5.2 условие «атакуя оружием», без требования попасть.

**В8. Смена Добычи после отдыха.**
- (а) Поле в `Rest` (`prey_swap`) по образцу `prepared_swap`. Это протокол, сейв не меняется.
- (б) Команда игрока.
- (в) Вопрос в меню после отдыха.

Нужно и для короткого отдыха (SRD: «после короткого или продолжительного»).

Рекомендация: **(а)**.

**В9 (блок.) Пересчёт КД по `equipment`.**
- (а) Только если `equipment` задано: КД = доспех + Лов до предела + щит, для `None` остаётся `ac`.
- (б) Всегда по формуле, а загрузчик проверяет совпадение с `ac`.
- (в) `ac` минус вклад статблокового доспеха/щита плюс вклад надетого. Так сохраняется природная броня у монстров К7д.

Отдельно:
- переносить ли `NPC.equipment` в `Participant` при старте боя;
- нужен ли рассказчику запрос «надеть/снять» на NPC. Сейчас писателей нет, без них пункт почти невидим.

Рекомендация: **(в)** + перенос из NPC. Запрос «надеть» — отдельный вопрос объёма, по умолчанию не делать.

**В10. `equipment.weapons` в бою.**
- (а) Действие с `weapon_id`, которого нет в заданном `equipment.weapons`, считается потерянным, как `lost_weapons`. Остаётся безоружный удар по `unarmed_types`.
- (б) Только трофеи, как сейчас, а в бою не читать.

Рекомендация: **(а)**: иначе обобранный NPC бьёт мечом, которого у него нет.

**В11. Сетка 2–5.** Сделана в К7к. Убрать хвост из ROADMAP:25, К7х его не делает?

Рекомендация: **да**.

**В12. BACKLOG 51** (content импортирует rules, `loader.check_monster_gear`).
- (а) Взять в К7х попутно: правка малая и в том же слое.
- (б) Оставить без приоритета.

BACKLOG 50 (сетка плута/жреца) относится к К2/К3, не к К7х.

Рекомендация: **(а)**, если smells не растут.

### Оценка и границы
- R5: S+ ≈ 0,7 млн, из них +0,1 на падение. Сверх этого К7к добавила В6 и чтение `weapons`: ≈ +0,1–0,15. При В6(б) (Метка в К8+) минус ≈ 0,05. Итог ≈ **0,75–0,85 млн (S+/M−)**. Риск: smells 204/206, а три новых правила (save, Истребитель орд, падение) — новые ветки.
- **К7д** (данные): 20–30 монстров. Им нужны:
  - формула КД из В9: природная броня при варианте (в);
  - тег `disarmer` на подходящих монстров;
  - пересчёт базовой линии сетки (k7k-sim-grid, замечание 9).

  К7х кода данных не пишет.
- **5а**: рисунки локаций, пересечений нет.
- **Ж0** (v10): при В1(б) поле высоты в Ж0 не нужно, пункт R5:164 «проверить высоту зоны» закрывается. Сделать это нужно отметкой в ROADMAP/R5.
- Приёмка (R5:244): бой на крыше — `push` с `elevation` 1 в зону 0 даёт урон и `prone`. Плюс тесты disarm save, `enemy_chance`, шаг к оружию.
- Решения за проектировщика молча не приняты. Факт про `elevation` меняет посылку R5 п. 8 («без поля зоны»), поэтому нужен явный ответ на В1.

### Аудит (кабан-свекровь, 2026-10-14)

Факты выборочно подтверждены на 4fc2ce8: `elevation`, ячейки полузаклинателя и Метка, писатели `equipment`, КД статблоков, отсутствие тега `disarmer`. Лишнего объёма нет. Решений за проектировщика не принято.

Правки к классификации:
- **В2, В7, В10 — блокирующие.**
  - В2: толкает ли монстр героя — это новый объём.
  - В7: «попадание или любая атака».
  - В10: меняет видимое поведение.
- **В9:** перенос `NPC.equipment` в `Participant` — отдельное решение проектировщика.

Пропущенные вопросы:
- **В13.** Сколько футов на ступень `elevation` (N).
- **В14.** Падение в яму (отрицательная `elevation`) и выход из неё.
- **В15.** Строка в `narrator_rules.md` о том, что высота даёт урон.

Ремарка: R4-unified по шаблону не найден, поэтому объём сверен по ROADMAP:25 и цитатам груминга.

### Решения проектировщика (2026-10-14)

- **В1 + В13:** высота падения — разница `elevation` между зонами, 10 фт на ступень. Урон 1d6 за 10 фт, не больше 20d6. Параметр запроса не делаем.
- **В2:** падение — при `push` в зону ниже: урон и `prone`. **Монстры тоже толкают** — это новый объём, ИИ монстров получает толчок.
- **В3:** спас Сил или Лов на выбор цели. СЛ 8 + Сил/Лов + БМ атакующего. Правило одно для всех.
- **В4:** `enemy_chance` — бросок раз за бой при старте, по умолчанию 0.
- **В5:** монстр идёт к своему оружию в соседней зоне, если в его зоне некого бить.
- **В6:** Метка 8/24 ч переносится в К8+. Поправить BACKLOG 11 и :237.
- **В7:** Истребитель орд — пункт меню «вторая атака» после любой атаки оружием, раз в ход, по цели в той же зоне.
- **В8:** `prey_swap` в `Rest`, на коротком и продолжительном отдыхе.
- **В9:** КД = `ac` − вклад статблоковых доспеха и щита + вклад надетого. `NPC.equipment` переносится в `Participant` при старте боя. Запрос «надеть/снять» не делаем.
- **В10:** оружия нет в заданном `equipment.weapons` — оно потеряно, NPC бьёт безоружным.
- **В11:** хвост «уровни 2–5» убрать из ROADMAP:25.
- **В12:** BACKLOG 51 берём попутно, если smells не растут.
- **В14:** падение в яму считается так же. Выход из ямы — обычным движением.
- **В15:** в `narrator_rules.md` добавить строку о том, что высота даёт урон при падении.

## Правки по ревью: Ревью К7х (mama-kaban, 2026-10-14) (бывш. docs/decisions/k7x-review.md)

Вписано оркестратором. Ревьюер проверял чтением кода и `git diff`. Полный зелёный прогон — за kaban-doeba.

Шаги плана 1–8 сделаны. RNG при `enemy_chance = 0` не тратится (`roles.py:116`). Сейв v9 не тронут. Строка в `narrator_rules` — одно предложение. Docs по п. 9 обновлены.

### Отклонения кабана
Приняты все, кроме п. 10:
- **1, 2 — обязательно.** В плане mutmut поправить `falling:drop_steps` → `zones:drop_steps` и `disarm:assign_roles` → `roles:assign_roles`.
- **3 — желательно.** Ветку save из `shove.save_contest` перенести в `disarm.contest`, если smells позволяют.
- **7 — желательно.** У локальных импортов (`controllers.py:96–97`, `features.py:207`) поставить комментарий о причине: цикл импортов.
- **8 — желательно.** В `horde_breaker.yaml:3` написать «Движок: …», без двух тире подряд.
- **9 — приемлемо.** Сетку не задевает.
- **10 — обязательно.** `apply_prey` и `feature_swap_problem` должны работать без записи в `feature_choices`: сейчас это `KeyError` после того, как отдых уже применён. Нужен тест.

### Свои замечания
- **Обязательно.** `available.py:279` и `features.py:209/211`: `[...][0]` по `attacks_of` даёт `IndexError`, если оружие пропало после первой атаки. Без оружия — `[]`.
- **Желательно.** `disarm.py:471`: в бою, начатом до К7х, `append` пишет в `NPC.equipment` мимо копии участника. Сначала копировать.
- **Желательно.** `engine.py:538/542`: `dex` считается дважды.
- **На будущее (BACKLOG).** Толчок не проверяет размер цели (по SRD — не больше чем на 1 крупнее). Важно перед К7д.
- **На будущее.** `fall_step_ft < 10` округляет вниз — так и задумано.

### Замечания доебы
- `step_to_weapon` по `owner_ref` — оставить.
- В плане (:92) Грей указан как охотник, а он `beast_master` — поправить.

## Итог: Аудит партии К7х (kaban-svekrov, 2026-10-14) (бывш. docs/decisions/k7x-audit.md)

_Вписано оркестратором: у аудитора нет Write._

**Что проверено:** коммит c25f254, по `git show --stat` и диффу. config, content, combat/{roles,zones,shove,controllers},
rules/{progression,roll_pipeline}, BACKLOG/HANDOFF/ROADMAP/TZ, narrator_rules.md, horde_breaker.yaml,
tests/unit/combat/test_import_cycles.py.

**Источники истины:** docs/plan-k7x.md («Решения проектировщика», В1–В15); docs/plan-k7x.md (Q1–Q4,
«Ответы проектировщика»); docs/plan-k7x.md.

| Находка | Где | Откуда взялось | Вердикт |
|---|---|---|---|
| Падение: `fall_step_ft = 10`, 1d6 за 10 фт, не больше 20d6, `prone`, яма | combat/falling.py, zones.drop_steps, [combat] | В1, В2, В13, В14; план, шаг 1 | оставить |
| Толчок монстров `shove:*`: СЛ 8 + Сил + БМ, раз за бой, только при намерении kill/drive_off | combat/shove.py, controllers.pick_shove | В2, Q1(а), Q4(а) | оставить |
| `[disarm].mode` check/save, `enemy_chance` = 0 | settings, defaults.toml, disarm.contest | В3, В4, Q2(а) | оставить |
| Модуль `combat/roles.py` вместо функции `disarm.assign_roles` | combat/roles.py | отклонение кабана (цикл импортов), принято ревью | оставить |
| Обёртка `EngineTactics.pick_early` (в плане вызовы прямо в `choose_turn`) | controllers.py | вне плана; видимо, ради smells | оставить: структура, не поведение |
| Код ошибки `no_choice` в `feature_swap_problem` | rules/progression.py | ревью, п. 10 (KeyError) | оставить |
| Тест-страж `test_import_cycles.py` | tests/unit/combat | вне плана; следствие локальных импортов | оставить |
| Строка рассказчику «враги тоже могут толкнуть героя с высоты» | narrator_rules.md | план, шаг 1.5 | оставить |
| BACKLOG 52 с приоритетом «важно сделать перед К7д» | docs/BACKLOG.md | замечание mama-kaban; приоритет поставили агенты | к пользователю |
| Отклонения кабана 1–10 не записаны: ревью ссылается на номера, текста в репо нет (в К7к был раздел «Отклонения» в плане) | docs/plan-k7x.md, docs/plan-k7x.md | — | к пользователю: дописать |
| Аппрув плана «Q1–Q4 — всё по рекомендациям» — пересказ оркестратора, без дословной цитаты и «окей, кабаним» | docs/plan-k7x.md | слова оркестратора | к пользователю: подтвердить |
| HANDOFF: «все обязательные и желательные правки внесены» | HANDOFF.md:228 | выборочно подтвердилось | оставить |

Незапрошенных фич, лишнего контента и правок вне области задачи нет.

**Решения за пользователя:**
1. Приоритет BACKLOG 52 («перед К7д») поставил ревьюер, а не проектировщик; по сути меняет объём К7д.
2. В12 — «BACKLOG 51 берём, если smells не растут»; smells выросли 204 → 206, агенты поняли как «не выше лимита».

**Итог:** по объёму чисто; нужны решения пользователя по BACKLOG 52, трактовке В12, записи отклонений и дословного аппрува.

### Решения проектировщика (2026-10-14)
1. BACKLOG 52 — «маму надо слушать»: приоритет оставить, берётся в К7д.
2. В12 (204 → 206) — принимаю.
3. Аппрув К7х — подтверждаю; отклонения 1–10 дописаны в K7X-PLAN «Отклонения при реализации».
4. Smells — вариант 2 + 4 (первый шаг плана К7д + правило нулевого баланса).
5. Экономия kaban-test (docs/plan-k7x.md, п. 1–4) — принята.

### Проба fable у papa-kaban
Проба закрыта 2026-10-09 (fable оставлен). На К7х план себя оправдал.
- Плюсы: точно следует В1–В15; Q1–Q4 — настоящие развилки; заранее увидены риски (RNG и golden, `IndexError` в
  `disarm.pickup`, давление на smells с конкретными выносами); оценка 0,8 при факте 0,86 (+7 %).
- Минусы: неверные места кода (`drop_steps`, `assign_roles`) → правка списка mutmut; Грей — не охотник, а beast_master;
  не увидены `KeyError` при пустом `feature_choices` и `IndexError` в `[...][0]` у Истребителя орд (нашла mama-kaban).
  Расход ~185 тыс.
- Вывод: польза есть, пересматривать не нужно.

### Smells 206/206: варианты перед К7д (только варианты)
1. Мини-партия «смеллы» до К7д (≈0,1–0,2 млн): `available.list_options`, `EngineTactics.choose_turn`, `resources.rest`,
   `engine.armor_class`; цель 196–200.
2. Первый шаг плана К7д: −4–6 smells, потом данные. Дешевле, но рефакторинг смешивается с контентом.
3. Поднять `SMELLS_MAX` (Makefile:4, например 212). Быстро, но лимит теряет смысл.
4. Правило нулевого баланса: партия не повышает smells, рост компенсируется в ней же.
5. Проверить, что считает `qlty smells`; если тесты/devtools — исключить, убедившись, что это не скроет реальный рост.

## Итог: К7х — разбор полётов по расходам (кабан-тесть, 2026-10-14) (бывш. docs/decisions/k7x-cost.md)

Источники: docs/HANDOFF.md (строки К7х, К7к, К1), docs/plan-k7x.md «Оценка», docs/plan-k7x.md,
docs/plan-k1.md, docs/ROADMAP.md (R6), логи субагентов сессии 61078a96 (выборочно: счёт вызовов).

### План и факт (тыс. ток., субагентные счётчики)
| Статья | План | Факт |
|---|---|---|
| Подготовка: svinopas 72 + svekrov 19 + papa 185 | в 0,8 входит | 276 (32 %) |
| kaban | 180–220 (~25 мин) | 143 + 25 = 168 |
| kaban-doeba | 400–480 (~2,5 ч) | 289 + 61 = 350 |
| mama-kaban | ~40 | 65 |
| **Итого** | ≈ 800 | ≈ 859 (+7 %) |
Оркестратор — не измерен (с К7к должен писать свой расход; в строке К7х его нет).

### Куда ушли деньги
1. kaban-doeba — 41 %. Лог (agent-a653…): 132 вызова, 26 ожиданий. Правило К1 работает: опрос
   `sleep 60; tail` заменён блокирующим циклом `for i in $(seq 9); do grep EXIT…; sleep 30/60; done` — ожиданий
   26 против 63 в К1 и 40 в К7к. Но: 12 из 26 ожиданий — `make cov` (≥4 полных прогона cov), 10 — mutmut
   (3 прогона), 2 — sim-grid. Каждый цикл обрезан 9 мин, поэтому длинный прогон даёт 2–4 вызова вместо одного.
   Дозадача +61 тыс. (12 ожиданий, 6 вызовов mutmut) — по правкам ревью (п. 1, 2, 10 и IndexError).
2. Подготовка — 276 тыс., из них papa (fable) 185 — дороже всего кода kaban (168).
3. mama-kaban 65 — выше обычных 30–55: 10 отклонений кабана + свои замечания.
4. kaban — в норме, 6 ожиданий из 70 вызовов; дозадача 25 тыс. по ревью.

### Сравнение с К7к
| | К7к | К7х |
|---|---|---|
| Оценка | 0,85–0,9 | 0,8 |
| Факт | ≈ 1,21 (63+25+187+530+347+55) | ≈ 0,86 |
| kaban | 530 (три захода) | 168 |
| doeba / ожиданий | 347 / 40 | 350 (289+61) / 26 |
К7х дешевле К7к на ≈ 0,35 млн почти целиком за счёт kaban (один заход вместо трёх). doeba не подешевела:
меньше ожиданий, но повторные cov и дозадача съели выигрыш.

### Оценка кабанов
| Кабан | Оценка (1–5) | Расход | Что хорошо | Что улучшить |
|---|---|---|---|---|
| svinopas | 4 | ~72 | в коридоре 63–94 | — |
| kaban-svekrov | 5 | ~19 | самый дешёвый аудит серии | — |
| papa-kaban (fable) | 3 | ~185 | оценка точна (+7 %), Q1–Q4 по рекомендациям | ошибки в плане: имена модулей mutmut (`falling:drop_steps`, `disarm:assign_roles`), Грей «охотник» — две обязательные правки ревью из плана; 22 % партии на план |
| kaban | 4 | ~168, 6 ожиданий | ниже плана, один заход | п. 10 ревью (`KeyError` после отдыха) и `[0]`→`IndexError` — дозадача |
| kaban-doeba | 3 | ~350, 26 ожиданий | правило К1 соблюдено, mutmut чист, выживших нет | cov гонялся ≥4 раз; цикл 9 мин дробит ожидание; mutmut по неверным именам из плана — лишний прогон не исключён (не видно точно) |
| mama-kaban | 4 | ~65 | нашла реальный баг (IndexError, KeyError) | дороже нормы; ок при 10 отклонениях |
| оркестратор | — | не видно | — | расход не записан, хотя решение с К7к |

### Что удешевить в К7д
1. doeba: `make cov` — один раз в конце; в процессе — `pytest` по затронутым файлам. ≈ −40–60 тыс.
2. doeba/kaban: длинные прогоны — `run_in_background` и ждать уведомления, без цикла с обрезкой 9 мин
   (k1-cost п.1 доведён наполовину). ≈ −20–40 тыс.
3. papa: перед сдачей плана проверить список mutmut `модуль:функция` по коду (`grep def`). Убирает 1–2 обязательные
   правки ревью и дозадачу. ≈ −20–40 тыс.
4. Оркестратор пишет свой расход в строку партии.
5. fable у papa (185 тыс. против 30–60 до fable) — решает проектировщик; теряем качество плана.
Итого К7д (S+, R6): без правок ≈ 0,75–0,85; с 1–3 ≈ 0,65–0,75 млн.

### Шкала R6
Не править. К1 0,84 (оценка 1,25 до R6), К7к 1,21 (0,85–0,9: перебор из-за трёх заходов kaban), К7х 0,86 (0,8).
Среднее двух партий по R6 ≈ 1,03 против ≈ 0,85 — +20 %, но выброс один (К7к). Пересмотреть после К7д: если снова
> +15 % — множитель ×0,7 → ×0,8.

## Итог: Из HANDOFF.md до 22д (бывш. docs/HANDOFF.md)

- **К7х груминг и план ✅ 2026-10-14:** груминг, аудит и решения — docs/plan-k7x.md (В2: монстры тоже толкают). План — docs/plan-k7x.md, Q1–Q4 по рекомендациям, оценка ≈0,8 млн. Расход: svinopas ~72, svekrov ~19, papa ~185 тыс. **Дальше (устарело, см. ниже):** аппрув плана проектировщиком → «окей, кабаним» (kaban + kaban-doeba параллельно, затем mama-kaban).
- **К7х код ✅ 2026-10-14 (kaban; тесты doeba и ревью mama-kaban впереди, не закоммичено):** `combat/falling.py` (падение при `push`), `combat/shove.py` (толчок монстров, `shove:*`, `pick_shove`), `[disarm].mode`/`enemy_chance`, `step_to_weapon`, `equipment` в бою (КД, потерянное оружие, перенос при старте), Истребитель орд (`horde_breaker`), `rest.prey_swap`, BACKLOG 51. Схема запросов изменилась (`Rest.prey_swap`, текст `push`): `--replay-report` старых репортов с `rest`/боем даст код 1. Чек-лист — checklist-k7x-live.md.
- **К7х ✅ закоммичена 2026-10-14:** тесты 15307 passed, cov 97,39 %, **smells 206/206 — запас исчерпан**, dead чисто; mutmut — выживших по К7х нет (эквивалентные разобраны). Ревью docs/plan-k7x.md (все обязательные и желательные правки внесены), отклонения кабана — там же. BACKLOG 52 (размер цели толчка — до К7д). TUI-тест `test_second_ctrl_c_calls_hard_exit…` падает и на чистом HEAD (флак, не К7х). Расход: svinopas ~72, svekrov ~19, papa ~185, kaban ~143+25, doeba ~289+61, mama ~65 тыс. ≈ **0,86 млн** (оценка 0,8). Живой прогон отложен (чек-листы r1-f1-r2, k1, k7k, k7x). **Дальше:** аудит К7х (kaban-svekrov) + разбор полётов (kaban-test), затем груминг К7д (svinopas + kaban-svekrov); перед К7д решить, как освободить запас smells.
- **К7х аудит и разбор полётов ✅ 2026-10-14:** docs/plan-k7x.md (по объёму чисто, fable у papa оправдан), docs/plan-k7x.md (факт 0,86 при 0,8; шкалу R6 не трогать до К7д, пересмотр при переборе >15 %). Решения проектировщика: BACKLOG 52 — в К7д («маму надо слушать»); В12 (smells 204 → 206) принят; аппрув К7х подтверждён, отклонения 1–10 дописаны в K7X-PLAN; **smells — первый шаг плана К7д (−4–6) + правило нулевого баланса (партия не повышает smells, рост компенсирует сама)**; экономия kaban-test принята: doeba гоняет `make cov` один раз в конце (по ходу — pytest затронутых файлов), длинные прогоны kaban/doeba — в фоне с ожиданием уведомления, papa сверяет список mutmut `модуль:функция` с кодом, оркестратор пишет свой расход в строку партии. Правка промптов агентов — через skill-intake. Расход: svekrov ~64, kaban-test ~31 тыс. Промпты поправлены (skill-intake, бэкап skills-agents-20261014-1640): doeba — cov один раз в конце, papa — п.7 сверка функций grep-ом; ожидание прогонов не менялось (уже фон + блокирующее ожидание, дробление — потолок Bash 10 мин). **Дальше:** груминг К7д (svinopas + kaban-svekrov) с BACKLOG 52 и правилом smells.
