# Решения по ревью партии 3 (спецификация правок)

Источник: ревью мамы-кабана партии 3. Решения — оркестратор в рамках ARCHITECTURE.md.
Исполнители: кабан (K) — `src/**`; кабан-доеба (T) — `tests/**`. Работают параллельно по этой спецификации.

## Блокирующие

**B1. Перебросы при adv/dis.** Пара костей хранится (`kept_pair`); переброс (Luck, вдохновение) заменяет
одну кость пары (ту, что дала natural; при равенстве — первую), natural пересчитывается тем же max/min.
Общий помощник `reroll_kept(...)` для всех перебросов.

**B2. Стабилизация полем.** `DeathSaves.stable: bool = False` (`state/creature.py`).
- 3 успеха → `stable=True`, счётчики `successes=failures=0`;
- `is_stable(hero) = hp == 0 and death_saves.stable`;
- урон на 0 HP → `stable=False`, провалы +1 (крит +2), **успехи сохраняются**;
- `heal` → `DeathSaves()` (сброс всего).

**B3. Мёртвый — окончательно.**
- `mark_dead` переносится в `mortality_guard.py`; на уже мёртвом — no-op (DeathRecord не перезаписывается), возвращает `[]` событий;
- `roll_death_save`, `heal`, `short_rest`, `long_rest` на мёртвом (`status == "dead"`) → `ValueError`;
- `after_damage` на мёртвом → возвращает `"dead"` без записи;
- `long_rest` при 0 HP → `ValueError` (SRD 5.2: для длинного отдыха нужен хотя бы 1 HP);
- `remove_creature` на уже мёртвом NPC → `Rejected(reason="already_dead", report_tag=None)`, запись не трогается.

**B4. Концентрация.** Общий `end_concentration(creature)` (в `damage.py` или `creatures.py`): снимает эффекты
с `expires.kind == "concentration"` и `concentration = None`. Вызывается из `concentration_check` (провал),
при падении на 0 HP (`after_damage`, ветка dropped) и в `mark_dead`.

**B5. Спасбросок от смерти = спасбросок и D20 Test.** `death_save` добавляется в kinds перебросов
(Luck, вдохновение) и в цели `saving_throw` для `EffectSource` (Bless). Истощение — как сейчас.

**B6. Грани урона в логе.** `roll_damage_dice(dice, bonus, rng, crit=False) -> DiceRoll` в `core/dice.py`
(крит удваивает число кубиков). Лог:
- `урон 2d8 (3, 7) + 3 = 13 (крит)`;
- Savage Attacker: `урон 1d8 (2 | 6 → 6) + 3 = 9 [savage_attacker]`.
`roll_hazard` возвращает результат с `RollLogEntry`. Отложенный импорт в конвейере убирается.

**B7. Проброс модификаторов.** `modifiers=None` (kwarg) в `checks.skill_check`, `checks.saving_throw`,
`damage.concentration_check`, `death_saves.roll_death_save` → пробрасывается в `roll`. Аналогично `rerollers=None` (D1).

**B8. CastCheck и критический момент.**
- `rules/cast_checks.py`: `CastCheckRegistry` (`register(source)`, `check(caster, spell_id, registry) -> list`),
  `default_cast_check_registry()` — пустой;
- `roll_death_save` ставит `tags["critical_moment"] = True`.

## Желательные (делаются в этой же партии)

**D1. Перебросы списком.** `REROLLERS = [luck, heroic_inspiration]` — функции
`(request, kept_pair, rng, registry, decisions) -> reroll_id | None` поверх `reroll_kept`; `roll(..., rerollers=None)`.
Расширения конвейера под будущие этапы:
- `Modifier.dc_bonus: int = 0` (прибавляется к цели — КД/СЛ — в исходе и логе; укрытие партии 5);
- `Modifier.crit_min: int | None` (диапазон крита; итоговый — минимальный из источников, по умолчанию 20);
- `RollRequest.now_s: int | None` (для источников «раз в день»);
- `EffectSource` смотрит и на `active_effects` цели (`request.target`) — для эффектов, действующих «по цели»
  (Dodge, Help, Vex уже так); параметр эффекта `side: Literal["actor","target"] = "actor"`.
- «Отвести беду» — НЕ конвейер (это процентный бросок world_sim, этап 3). Молитва +6 — источник читает `tags["prayer"]`.

**D2.** `rules/creatures.py` остаётся утилитой (`is_hero`, `creature_of`, `D20_KINDS` — единственное объявление).

**D3. Доменные события.** `core/events.py`: `DomainEvent(BaseModel): type: str; data: dict[str, int | str | bool | None]`
(`extra="forbid"`). `remove_creature` и `mark_dead` возвращают `list[DomainEvent]`
(`creature_removed`, `hero_died` / `npc_died` с `id`, `cause`, `by`).

**D4. Отдых.** Константа `LONG_REST_FULL = ("hit_dice", "spell_slot:")` в `derived.py` рядом с `resource_maxes`;
`recover` не применяется дважды к одному пулу (дубли эффектов — один раз, берётся максимальный amount);
Resourceful учитывает `when: long_rest`. Кость хитов короткого отдыха — как сейчас (`max(0, …)`), сверка — трек 1.5.

**D5. Состояния SRD 5.2.**
- вложенные: unconscious ⇒ incapacitated + prone; paralyzed, stunned, petrified ⇒ incapacitated
  (поэтому дальняя атака по лежащему без сознания — adv + dis = обычная);
- grappled: помеха на атаки по всем, кроме схватившего (`AppliedCondition.source` = id схватившего, `request.target_id`);
- invisible: преимущество на инициативу; incapacitated: помеха на инициативу.

**D6.** `add_exhaustion(..., cause=...)` — `cause` обязательный keyword.

**D7. Дубли.** Одна `remove_zero_hp_unconscious`; nat 20 death save → `heal(hero, 1)`; `D20_KINDS` — одно объявление.

**D8. Лог и мелочи.**
- переброс в логе: `d20 (1 → удача 12)`, `d20 (4 → вдохновение 15)`; при adv/dis: `d20 (1, 5 → удача 18 → 5)`;
- `after_damage` при `was_down` считает провал, только если `hp_lost + overkill > 0` (временные HP съели всё — нет провала);
- `remove_creature` с неизвестным id — `KeyError` (как сейчас, задокументировать);
- Savage Attacker «раз в ход»: флаг `tags["savage_attacker_used"]` ставит вызывающий по `result.rerolls` — записать в docstring.

## Тесты (T)
Обновить существующие под изменения API (B2 `stable`, B3 ValueError, B6 `DiceRoll`/лог, D3 события, D6 cause) и добавить:
Luck+dis, Luck+adv, вдохновение+adv, вдохновение+dis; урон по стабильному с прежними провалами (→ 1 провал, не смерть);
успехи сохраняются после урона; спасбросок / урон / отдых / лечение мёртвого героя; DeathRecord не перезаписывается;
`long_rest` при 0 HP; концентрация снимается при падении на 0 HP и при смерти; Bless и Luck на death save;
`critical_moment` у death save; `modifiers=` через `saving_throw`/`skill_check`/`concentration_check`/`roll_death_save`;
`rerollers=`; грани урона в логе (обычный, крит, Savage); `roll_hazard` с логом; `dc_bonus` (укрытие: лог «vs КД 17»),
`crit_min`; эффект со стороны цели; вложенные состояния (дальняя атака по unconscious — обычная); grappled;
инициатива invisible/incapacitated; `CastCheckRegistry` пустой и с зарегистрированным источником; `DomainEvent`;
дубль `recover` не удваивает восстановление; временные HP при 0 HP — без провала.
