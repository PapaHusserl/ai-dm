# Этап 1: приёмка, аудит и ревью партий

## Суть

Этап 1 — приёмка, аудит и ревью партий 1–5. Здесь собраны решения проектировщика по аудиту 1 (внесены в TZ.md), спецификации правок после ревью партий 2–5 и решения приёмки этапа 1 (2026-10-03). Плана этапа как отдельного документа не было.

## Правки по ревью: Аудит 1 (после партии 3): решения и спецификация правок (бывш. docs/decisions/audit-1.md)

Источник: независимый аудит партий 1–3. Раздел 1 — решения **проектировщика** (внесены в TZ.md).
Раздел 2 — технические правки (оркестратор). Исполнители: кабан (K) — `src/**`, `docs/**` кроме TZ;
кабан-доеба (T) — `tests/**`.

### 1. Решения проектировщика (2026-10-02)

| # | Вопрос | Решение |
|---|---|---|
| P1 | Категории `advance_time` | `minute` = 15 мин (900 с), **`hour` = 1 ч (3600 с)** — не закрывает сцену (порог ТЗ 4.0: > 1 часа) |
| P2 | HP при повышении уровня | **выбор игрока**: фиксированное среднее (по умолчанию) или бросок кости хитов (+ мод. ТЕЛ, минимум 1) |
| P3 | Снаряжение/золото свободной предыстории | **бюджет 50 зм**: сумма цен предметов + `gold_cp` ≤ 5000 мм |
| P4 | Подготовленные заклинания | **игрок выбирает явно** (`CharacterChoices.prepared`), в пределах лимита класса и из известных |
| P5 | Повтор черты через Versatile | **по SRD**: повтор разрешён для черт со свойством Repeatable (Skilled, Magic Initiate), остальные — нельзя |
| P6 | Навык класса совпал с навыком предыстории | **ошибка «выбери другой»** (`class_skills_invalid`) — как сейчас |
| P7 | Ограбление | **кроме надетого** (`equipped` — доспех, щит, оружие в руках) |
| P8 | Метод характеристик `explicit` | **доступен и при создании на лету** (3..20 до бонуса, ≤ 20 после) |
| P9 | Названия месяцев стандартного календаря | **оставить** (Заревень … Темнозим) |

### 2. Технические правки

2.1. **Skilled механически** (план, таблица B): выбор 3 навыков/инструментов. `CharacterChoices.feat_choices:
     dict[feat_id, list[str]]` (для Skilled — 3 элемента: навыки из `Skill` или id инструментов); навык,
     уже имеющийся, — ошибка `feat_choices_invalid`; Skilled от предыстории и от Versatile — у каждого свой выбор
     (ключ — `<feat_id>` и `<feat_id>#2` для повтора, либо список выборов — на усмотрение K, зафиксировать в контракте).
2.2. **P5:** `Feat.repeatable: bool = False`; `true` у `skilled`, `magic_initiate`; Versatile разрешает черту,
     уже выданную предысторией, только если `repeatable`.
2.3. **P3:** `validate_background` проверяет бюджет 50 зм (цены из реестра); код `background_budget_invalid`.
     SRD-предыстории ему соответствуют (проверить тестом).
2.4. **P4:** `CharacterChoices.prepared: list[str]` — подмножество выбранных заклинаний 1+ круга, длина ≤ лимита
     `Spellcasting.prepared`; иначе `spells_invalid`. Убрать «первые N».
2.5. **P2:** `level_up(hero, registry, *, hp_method: Literal["average","roll"]="average", rng=None)`;
     `roll` требует rng, бросок кости хитов + мод. ТЕЛ, минимум 1.
2.6. **P7:** `pick_valuables` исключает предметы в `equipped` (все слоты, включая `off_hand`).
2.7. **P1:** `defaults.toml` `hour = 3600`; ARCHITECTURE шаг 4 — поправить значение.
2.8. **Конфиг явно** (план п.5): `cfg: RulesConfig` — обязательный аргумент во всех функциях `time_ops`, `rests`
     и прочих местах, где сейчас `cfg=None` → `load_rules_config()`. Fallback убрать.
2.9. **Герой и правило 4.1:** `mark_dead` с невалидной причиной → `Rejected(report_tag="invalid-death")`, а не
     ValidationError; статус «выведен из игры» для героя — `HeroState.status` получает `"gone"` (если ещё нет) и
     `mortality_guard.remove_hero(hero, status, cause, ...)` по тем же правилам, что `remove_creature`.
2.10. **Константы SRD в данные:** стандартный набор, покупка очков (стоимость, бюджет 27, диапазон 8..15),
      таблицы ячеек полного/половинного заклинателя → `srd/data/tables/` (`standard_array`, `point_buy`,
      `spell_slots_full`, `spell_slots_half`; формат `Table` допускает, что нужно — расширить минимально);
      `BACKGROUND_GOLD_B_CP` — поле предыстории `gold_option_cp` (у SRD-предысторий 5000).
2.11. **`Monster.xp` убрать** — опыт берётся из `tables/cr_xp` по `cr`.
2.12. **Мёртвый код:** `core/dice.format_attack_log` — использовать в конвейере для строки атаки (одна реализация)
      либо удалить; `damage.roll_damage` — удалить (все вызовы — `roll_damage_dice`); `ContentRegistry.subclasses_of`
      и `RollRequest.skill` — оставить (нужны партиям 4–5 / логу), это не мёртвый код по плану.
2.13. **`off_hand`** — в `inventory.SLOTS`, `equip(..., slot="off_hand")` для лёгкого оружия, `unequip` работает.
2.14. **Bless upcast:** `upcast.per_slot_level.targets` вместо `count`.
2.15. **Документы:**
      - `docs/rules-adaptation.md` — завести: Frightened без линии обзора; «в пределах 5 фт» = `tags.melee`;
        `unconscious(source="0_hp")`; стабилизация полем; переброс заменяет кость пары; кость хитов короткого отдыха
        `max(0, …)` (сверка — трек 1.5); прочие адаптации из decisions batch2/batch3;
      - `docs/glossary.md` — дописать термины 2024 из YAML (Находчивость, Умелость, Универсальность, Одарённый,
        Свирепый атакующий, Бдительность, Посвящённый в магию, Проворное бегство и др.); единый термин для
        acolyte — «Прислужник» (ТЗ поправит оркестратор);
      - ARCHITECTURE A5/A6 — синхронизировать раскладку (`rules/cast_checks.py`, `content/models/tables.py`, нет
        `core/ids.py`/`errors.py`/`modifiers/feats.py` — логика черт в `derived`/`roll_pipeline`), `feat_choice`
        в списке видов эффектов;
      - в `docs/plan-stage1.md` (этот файл) K дописывает раздел «3. Записано без изменений»: quarterstaff
        (нужен мудрецу), предметы стартовых наборов, полные таблицы XP/CR (данные SRD без логики), `feat_choice`,
        `Spellcasting.cantrips/spells/prepared`, Skillful запрещает дубль навыка.

### Тесты (T)
Обновить существующие под 2.4 (prepared), 2.5, 2.7, 2.8 (cfg обязателен), 2.10–2.14; добавить: Skilled (3 выбора,
повтор через Versatile с отдельным выбором, дубль навыка → ошибка); Versatile + Magic Initiate у мудреца разрешён,
Versatile + Alert у… (не-repeatable дубль) → ошибка; бюджет 50 зм (SRD-предыстории проходят, 51 зм → ошибка);
явный `prepared` (вне выбранных / сверх лимита → ошибка); `level_up` roll и average, минимум 1; ограбление не берёт
надетое (включая `off_hand`); `hour == 3600`; `mark_dead` с невалидной причиной → Rejected; `remove_hero`;
таблицы standard_array/point_buy/spell_slots из реестра; опыт монстра по cr; `off_hand` equip/unequip; Bless upcast
`targets`; отдых с пользовательским cfg (например `long_rest_s = 7200` → часы +2 ч).

### 3. Записано без изменений

Сделано сознательно, правок не требует (аудит это отметил, решение — оставить как есть):

- **quarterstaff** в SRD-контенте нужен мудрецу (стартовое оружие), хотя в минимуме оружия не заявлен.
- **Предметы стартовых наборов** (бумага, молитвенник, одежда и пр.) заведены простыми записями `items/` без механики.
- **Полные таблицы XP/CR** (`xp` до 20 уровня, `cr_xp`) — данные SRD без логики; движок читает только уровни 1..5.
- **`feat_choice`** — вид эффекта (Универсальность), читается только `builder`; сам выбор хранится в
  `CharacterChoices.species_choices`.
- **`Spellcasting.cantrips/spells/prepared`** — числа при создании героя; `None` = без ограничения.
- **Умелость запрещает дубль навыка**: навык, уже данный предысторией, классом или чертой, выбрать нельзя.

### 4. Дополнения при приёмке (оркестратор)
- `off_hand`: только лёгкое оружие, несовместимо со щитом и двуручным в main_hand — следует из свойства Light SRD 5.2.
- `Item.tool: bool` — признак инструмента; `thieves_tools`, `calligraphers_supplies`, `gaming_set` — инструменты.
  Skilled принимает только инструменты (лом, зелья — нет); загрузчик проверяет, что `background.tool` — инструмент.
- `BACKGROUND_BUDGET_CP = 5000` остаётся константой в builder (это решение проектировщика P3, не таблица SRD).

## Правки по ревью: Решения по ревью партии 2 (спецификация правок) (бывш. docs/decisions/batch2-review.md)

Источник: ревью мамы-кабана партии 2. Решения принимает оркестратор в рамках ARCHITECTURE.md.
Все пункты меняют схему сейва/контента — делаются до шага 22 (отпечаток схемы), миграции не нужны.
Исполнители: кабан «state» (S), кабан «content+rules» (C), кабан-доеба (T) — тесты на всё ниже.

### 1. Состояние (`src/ai_dm/state/`) — исполнитель S

1.1. **Нет float в сейве.** `GlobalEvent.mortality_multiplier: int = Field(1, ge=0)`.
     Тест-сторож: в `SaveBundle.model_json_schema()` нет `"type": "number"` (рекурсивно).
1.2. **`GlobalEvent` по ТЗ 4.1.2:**
     - `hazard: EventHazard | None`, `EventHazard {save: Ability, dc_category: DcCategory}`;
     - `started_s: int | None` (вместо `started: str`); `ends_at_s: int | None`; `ends_when: Condition | None`.
     - Перевод дат пака в секунды — при загрузке пака (этап 3), не сейчас.
     - `NPC.birth_date: str` → `birth_s: int | None`.
     - `Ability` = `Literal["str","dex","con","int","wis","cha"]`, `DcCategory` =
       `Literal["very_easy","easy","medium","hard","very_hard","nearly_impossible"]` — объявить в
       `ai_dm/content/models/common.py` (рядом с `ABILITIES`), state импортирует оттуда.
1.3. **Благосклонность по богам:** `HeroState.favor` и `NPC.favor` → `dict[str, int]`, значения −10..10 (валидатор).
1.4. **Связи локаций:** `Connection {to: str, distance_m: int (ge=0)}`; `Location.connections: list[Connection]`.
1.5. **`ActiveEffect`** (`state/creature.py`): `id: str`, `source: str`, `kind: str`,
     `params: dict[str, int | str | bool]`, `expires: Expiry | None`;
     `Expiry {kind: Literal["rounds","end_of_turn","start_of_turn","seconds","concentration"], value: int = 0, owner: str | None}`.
     `CreatureState.active_effects: list[ActiveEffect]`.
1.6. **Состояния с источником:** `CreatureState.conditions: list[AppliedCondition]`,
     `AppliedCondition {id: str, source: str | None, expires: Expiry | None}`.
1.7. **`DeathRecord`** (`state/death.py`): `cause: Literal["goal","hazard","chance","old_age"]`,
     `by: str | None`, `at_s: int`, `location_id: str | None`, `text: str = ""`.
     `HeroState.death`, `NPC.death` → `DeathRecord | None`.
1.8. **`Trigger.state: Literal["active","fired","disabled"] = "active"`**; `cooldown` валидируется через
     `Duration.parse` (`field_validator`).
1.9. `WorldState.settings: dict[str, int | str | bool]`.
1.10. `Equipped.off_hand: str | None = None`.
1.11. `CharacterSheet.spells_prepared: list[str] = []` (в дополнение к `spells_known`).
1.12. `NPC.means`: `min_length=1, max_length=3`.
1.13. `WorldState.npcs|factions|pantheon|locations`: валидатор «ключ словаря == obj.id».
1.14. `Memory.*`: `list[dict]` вместо голого `list`.
1.15. Переименовать класс условия `Any` → `AnyOf`, `All` → `AllOf`, `Not` → `NotOf` (YAML-тип по-прежнему
      `any`/`all`/`not`), чтобы не затенять `typing.Any`.
1.16. Заглушками остаются до своих этапов: `afterlife`, `Chronicle.entries`, `Memory.*`,
      `session.current_scene|current_chapter`, `NPC.combat`. `SessionState.active_combat` и
      `pending_decision` типизируются в партии 5 (шаги 15–21), до шага 22.

### 2. Контент (`src/ai_dm/content/`, `srd/data/`) — исполнитель C

2.1. **Закрытые значения effects** (`content/models/common.py`):
     - `add: Literal["proficiency_bonus","spellcasting_modifier","class_level"] | None` + `class_id: str | None`
       (обязателен при `add == "class_level"`); `check_refs` проверяет `class_id`;
     - `target`, `when`, `mode`, `shape` — `Literal` с перечнем значений, которые читает движок
       (собери из текущего YAML; новое значение = правка Literal);
     - `count` разделить: `targets: int | None` (число целей, Bless), `count` — количество (дротики, выборы).
     - Всё сложнее — только через `handler`.
2.2. `SKILLS` перенести из `rules/derived.py` в `content/models/common.py` (`Skill` Literal); rules импортирует оттуда.
2.3. **Загрузчик:** собирать ошибки всех файлов, а не падать на первом; проверять ссылки
     `EffectSpec.condition` → состояния, навыки в `skill_choices.options` и предысториях → `Skill`,
     `background.feat` → черта категории `origin`.
2.4. `Monster.abilities: dict[Ability, int]` (все 6).
2.5. **Заклинания:** `range_kind: Literal["self","touch","ranged"]` + `range_ft: int | None` (для ranged);
     `duration: str` в формате `Duration` (`1m` = 1 минута, `instant`/`instantaneous` → `None`) — поле
     `duration_s: int | None`; усиление — данными: `upcast: {per_slot_level: {dice?: str, count?: int}} | None`,
     рост заговора — `cantrip_scaling: {5: dice, ...} | None`.
2.6. **Классы:** `Spellcasting.progression: Literal["full","half"]`; убрать `HALF_CASTERS` из кода.
     Плут: `weapon_training_properties: list[Literal["finesse","light"]]` — владение воинским оружием с любым
     из свойств (по SRD 5.2); учесть в `attack_bonus`.
2.7. **Ресурсы данными:** `EffectSpec(kind="resource")` получает `pool: str`, `max: int | None`,
     `max_add` (как `add`), `recover: list[{on: Literal["short_rest","long_rest"], amount: int | "all"}]`.
     Second Wind: max 2, short_rest +1, long_rest all. Ключи пулов: `second_wind`, `spell_slot:1`…`spell_slot:9`.
2.8. **Таблицы SRD данными:** `srd/data/tables/{xp,proficiency,dc,cr_xp}.yaml` + модель `Table`;
     `progression.py` и проверки читают таблицы из реестра (вид `table`).
2.9. **Предыстории SRD:** добавить стартовое снаряжение и золото по SRD 5.2 (вариант A — набор предметов,
     вариант B — золото); `BackgroundSpec.equipment: list[str]`, `gold_cp: int`; валидатор проверяет id предметов.
     Предметы, которых нет в минимуме, — добавить простыми записями `items/` (без механики) или опустить с
     пометкой в отчёте.
2.10. **Монстры по SRD 5.2:** Goblin Warrior — +1d4 урона при атаке с преимуществом (скимитар и короткий лук);
      Goblin Boss — сверить действия по SRD 5.2 (в т.ч. Shortbow вместо метательного копья, если так в 5.2),
      мультиатака — полем данных `multiattack: [{action, count}]`. Если не уверен — указать в отчёте.
2.11. Навыки волшебника по SRD 5.2 (добавить Nature, если так в 5.2 — сверить).
2.12. Вид человека: Skillful (1 навык на выбор) и Versatile (черта происхождения на выбор) — механически,
      через `CharacterChoices.species_choices`. Dwarven Toughness, Keen Senses, Darkvision — трек 1.5.

### 3. Правила (`src/ai_dm/rules/`) — исполнитель C

3.1. `builder`:
     - `fighting_style` — только если у класса есть умение `fighting_style` (иначе `fighting_style_invalid`);
     - повторы в `weapon_masteries` и мастерство по оружию без владения → `mastery_weapon_invalid`;
     - пересечение навыка класса с навыком предыстории → `class_skills_invalid`;
     - `abilities_invalid`: значения `explicit` вне 3..20 до бонуса и > 20 после бонуса;
     - `spells: list[str]` в `CharacterChoices`: заклинание в списке класса и круг ≤ доступного
       (код `spells_invalid`); заговоры и заклинания 1 круга по числу из класса (если данных нет — без ограничения
       количества, пометить в отчёте);
     - заводит пулы ресурсов (`second_wind`, `spell_slot:N`) и выдаёт снаряжение/золото предыстории;
     - человеческие Skillful/Versatile через `species_choices` (код `species_choices_invalid`);
     - сообщения ошибок — человекочитаемые по-русски, не `"предыстория: {code}"`.
     - коды `item_unknown`, `equip_invalid` — оставить, задокументировать в контракте.
3.2. `derived`: одна функция `effect_amount(effect, hero, registry)` для КД, инициативы и пр.; ячейки — по
     `Spellcasting.progression`.
3.3. `progression`: таблицы из реестра; `level_up` обновляет пулы ресурсов; docstring — вызывающий проверяет опыт.
3.4. `inventory`:
     - `pick_valuables` тасует только группы ничьих, которые нужны до набора `count`, и только различные id;
       неизвестный id → `InventoryError`;
     - `equip`: двуручное оружие со щитом → ошибка; доспех без владения → ошибка (`InventoryError`);
     - `use_item` остаётся как есть; на шаге 11 переводится на `rules/healing.py` (пометка TODO в коде).

### 4. Документы — оркестратор
- A2/A6 в ARCHITECTURE.md приводятся к фактической раскладке (`state/save.py`, NPC/Location в `world.py`,
  `srd/data` — файл на объект), `distance_m` вместо `distance_km`.

### 5. Разделение файлов между исполнителями (чтобы не конфликтовать)
- S: только `src/ai_dm/state/**`. Импортирует `Ability`, `DcCategory` из `ai_dm.content.models.common`
  (уже объявлены оркестратором), сам `common.py` не трогает.
- C: `src/ai_dm/content/**`, `src/ai_dm/srd/data/**`, `src/ai_dm/rules/**`. Может читать state, но не правит его;
  если для пункта 3.x нужно поле state из раздела 1 — оно появится у S, ориентироваться на имена из раздела 1.
- T: только `tests/**`.

## Правки по ревью: Решения по ревью партии 3 (спецификация правок) (бывш. docs/decisions/batch3-review.md)

Источник: ревью мамы-кабана партии 3. Решения — оркестратор в рамках ARCHITECTURE.md.
Исполнители: кабан (K) — `src/**`; кабан-доеба (T) — `tests/**`. Работают параллельно по этой спецификации.

### Блокирующие

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

### Желательные (делаются в этой же партии)

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

### Тесты (T)
Обновить существующие под изменения API (B2 `stable`, B3 ValueError, B6 `DiceRoll`/лог, D3 события, D6 cause) и добавить:
Luck+dis, Luck+adv, вдохновение+adv, вдохновение+dis; урон по стабильному с прежними провалами (→ 1 провал, не смерть);
успехи сохраняются после урона; спасбросок / урон / отдых / лечение мёртвого героя; DeathRecord не перезаписывается;
`long_rest` при 0 HP; концентрация снимается при падении на 0 HP и при смерти; Bless и Luck на death save;
`critical_moment` у death save; `modifiers=` через `saving_throw`/`skill_check`/`concentration_check`/`roll_death_save`;
`rerollers=`; грани урона в логе (обычный, крит, Savage); `roll_hazard` с логом; `dc_bonus` (укрытие: лог «vs КД 17»),
`crit_min`; эффект со стороны цели; вложенные состояния (дальняя атака по unconscious — обычная); grappled;
инициатива invisible/incapacitated; `CastCheckRegistry` пустой и с зарегистрированным источником; `DomainEvent`;
дубль `recover` не удваивает восстановление; временные HP при 0 HP — без провала.

## Правки по ревью: Решения по ревью партии 4 (спецификация правок) (бывш. docs/decisions/batch4-review.md)

Источник: ревью мамы-кабана партии 4. Решения — оркестратор в рамках ARCHITECTURE.md.
Исполнители: кабан (K) — `src/**`, `docs/**` кроме TZ; кабан-доеба (T) — `tests/**`. Параллельно.

### Блокирующие

**B1. `world_id` безопасен.** `layout.check_world_id(world_id)`: непустой, только `[\w-]` (юникодные буквы,
цифры, `_`, `-`), не начинается с `.`, без `/`, `\`, `..`; иначе `ValueError`. Вызывается из `slot_dir`
(значит — во всех входах store/backup). Абсолютный путь невозможен.
`slot_dir` проверяет и `world_id`, и имя слота.

**B2. Мир — по каталогу.** `write_slot(root, world_id, bundle, slot, *, saved_at)` — `world_id` явным аргументом;
`load_slot` при `bundle.world.world_id != world_id` или `manifest.world_id != world_id` → `ValueError`
(до бэкапа и до записи); миграция перезаписывает именно загружаемый каталог.

**B3. Уникальность героев в сейве.** `write_slot` до записи проверяет уникальность `hero.id` и имён каталогов
`hero_dir_name`; повтор → `ValueError`, слот не тронут.

**B4. Ротация без моделей.** `move_slot` правит `manifest.json` как сырой JSON (`raw["slot"] = new_name`),
без `Manifest.model_validate_json`. Принцип (записать в ARCHITECTURE A3): persistence никогда не читает
файлы старой версии текущими моделями — только сырой dict до миграции.

**B5. Мусор в каталогах.** При чтении `heroes/` и `slots/` учитываются только каталоги, имя которых не
начинается с `.` (`.DS_Store`, `.tmp-*`, `.old-*` игнорируются).

**B6. Нарратив с логикой.** `Evaluation` получает `residual: Condition | None` — остаток дерева условия:
выполненные структурные листья выброшены (TRUE-ветки `all` убираются, `any` с TRUE → вся ветка TRUE),
нарративные листья и `not`/`all`/`any` над ними сохранены. При `truth == NEEDS_NARRATIVE` residual — непустое
дерево (оно уходит модели `world`), при TRUE/FALSE — `None`. `narrative: list[str]` остаётся (плоский список
текстов для промпта). Тест «not: тот же narrative» заменяется: `{not: {narrative: X}}` → residual `NotOf(Narrative(X))`.

### Желательные (делаются в этой же партии)

**D1.** `load_slot` до бэкапа проверяет, что цепочка миграций полна (`MigrationMissing` без бэкапа, файлы не тронуты);
коллизия имени бэкапа → суффикс `-2`, `-3`…
**D2. Восстановление.** `recover_slots(root, world_id)` вызывается в начале `list_slots` и `load_slot`:
- `.old-*` есть, а слота с именем из его `manifest.slot` (сырой JSON) нет → вернуть на место; иначе удалить;
- `.tmp-*` с `manifest.json` (запись полная) → поставить на место, если слота нет; иначе удалить;
- `.tmp-*` без `manifest.json` → удалить.
Порядок: сначала `.tmp-*` (полный — новая запись, ставится на место), затем `.old-*` (удаляется, если слот уже есть).
Durability при отключении питания (fsync, F_FULLFSYNC) — вне этапа 1 (записать в BACKLOG одной строкой).
**D3.** `load_slot` после валидации ставит `bundle.manifest.slot = slot` (истина — каталог). Удаление `auto-<keep>`
при ротации — через `os.replace` в `.old-<uuid>`, затем rmtree.
**D4.** (T) тест на падение второго `os.replace` (откат old→final).
**D5.** (T) тесты m0001 сравнивают с литералами, не с `Memory()`/`Tone()`. (K) m0001 — `setdefault` вместо перезаписи.
**D6.** Порядок «типизация боевой сессии после отпечатка» записан здесь осознанно: **партия 5 обязана**
типизировать `SessionState.active_combat` (`CombatState | None`) и `pending_decision` (`DecisionPoint | None`) и
перегенерировать `tests/schema/save_v1.schema.json` без подъёма версии. (T) сторож: в `SessionState` нет полей
типа голый `dict` — `xfail(strict=True)` до партии 5 только для `active_combat`/`pending_decision`/`current_scene`/
`current_chapter`. Чек-лист релиза этапа 1 — пункт в BACKLOG: «в SaveBundle.session нет голых dict».
**D7.** `event_active` учитывает время: `(started_s is None or started_s <= now_s) and (ends_at_s is None or now_s < ends_at_s)`,
`now_s = world.clock.now_s`. `validate_refs` **не** проверяет `event_active` (события возникают позже по TZ 4.1.2).
**D8.** `validate_refs(cond, world, registry=None)`: при переданном реестре `hero_has` проверяется по предметам
(weapon/armor/item).
**D9.** `flag`: совпадение только при `isinstance(v, bool) and v == condition.value`; не-bool → FALSE.
**D10.** `secrets.reveal(..., narrative_confirmed: bool = False)`: при NEEDS_NARRATIVE и `narrative_confirmed=True`
раскрывает. `Rejected` переносится в нейтральный `rules/results.py` (mortality_guard и secrets импортируют оттуда;
реэкспорт из mortality_guard сохранить).
**D11.** Контракт событий для партии 5 (записать в ARCHITECTURE шаги 13/21): `location_visited {id}`,
`combat_ended {id}`, `item_gained {hero, item}` — ровно эти ключи. `hero_died → hero_dead:<id>` — принято.
**D12.** Имена слотов — только строчные (`manual-A` → `ValueError`); `make_backup(root, world_id, slot, old_version, ts=None)`
(без `folder`); `evaluate(..., hero=None)` допустим — условия о герое (`hero_has`, `hero_at`, `hero_dead`, `favor`) → FALSE.

### Тесты (T)
По B1–B6, D1–D12: world_id с `..`/`/`/абсолютный/пустой/`.x` → ValueError во всех входах; переименованный каталог
мира + v0 → ValueError, ничего не записано; два героя с одним ordinal+именем / одним id → ValueError, слот цел;
ротация с v0-фикстурой в `auto` и в `auto-1`; `.DS_Store` в `heroes/` и `slots/`; residual для not/all/any над
нарративом и смешанных деревьев; MigrationMissing дважды подряд с одним ts → 0 бэкапов; коллизия бэкапа → `-2`;
recover_slots (три сценария); `manifest.slot` после загрузки = каталог; второй os.replace падает → откат;
m0001 с литералами и setdefault; xfail-сторож SessionState; event_active по времени; validate_refs с registry;
flag с int-значениями; reveal с narrative_confirmed; `Rejected` из `rules.results`; заглавные в слоте; evaluate с hero=None.

## Правки по ревью: Решения по ревью партии 5 (спецификация правок) (бывш. docs/decisions/batch5-review.md)

Источник: ревью мамы-кабана партии 5. Принцип решений: **точность по SRD 5.2, где это недорого**; упрощение —
только с записанной причиной в rules-adaptation. Исполнители: кабан (K) — `src/**`, `docs/**` кроме TZ;
кабан-доеба (T) — `tests/**`. Параллельно.

### Блокирующие
1. **`hero_dead` только при мёртвом герое** — `end.update_outcome`: убрать ветки, дающие `hero_dead` при смерти
   NPC-союзника. Герой сбежал, союзник убит → `fled`.
2. **Вставание** — в `start_turn` активного участника снимается `prone` с `source != "0_hp"`, оставшееся
   перемещение хода = 0 (встать — половина скорости ≈ всё перемещение в зонах). Строка в rules-adaptation.
3. **Savage Attacker в сейве** — `CombatState.savage_used: list[str] = []` (поле CombatState, не TurnState: «раз за
   любой ход»), сброс в `start_turn`; убрать счётчик из памяти движка. Перегенерировать отпечаток схемы.
4. **Bless по SRD** — накладываются **все** `modifier`-эффекты заклинания (атака и спасброски), и **до `targets`
   целей**: id варианта `cast:bless:1:<t1>[,<t2>[,<t3>]]` (союзники в пределах дальности; повтор цели — отказ).
   Общий механизм для любого заклинания с `targets` > 1.

### Желательные (делаются в этой партии)
5. **Vex точно** — если атакующий попал в свой ход: эффект до конца его следующего хода (`end_of_turn` следующего
   хода владельца — реализуй через счётчик ходов владельца или `rounds`, если владелец ходит раз в раунд);
   вне своего хода (провоцированная): до конца его ближайшего хода. Обновить rules-adaptation.
6. **Импровизация «преимущество»** — эффект на следующую атаку **героя** до конца его следующего хода (как Vex,
   `consume` при атаке), а не до начала следующего хода.
7. **Группа последнего удара** — при падении от опасности (`attacker_ref is None`) `defeat_group_id = None`;
   удар по уже лежащему герою обновляет `defeat_group_id` группой ударившего.
8. `kill_monster` — `Rejected` от `remove_creature` → исключение (ошибка программы).
9. **Мультиатака** — действие атаки монстра с `multiattack` выполняет шаги `multiattack` (`[{action, count}]`);
   варианты выбора в `available_actions`: `multiattack` как отдельное действие; цели — по тактике для каждой атаки.
10. **Площади и спасброски ЛОВ** — укрытие даёт `+2/+5` к спасброску ЛОВ (из зоны укрытия против источника из
    другой зоны); Dodge даёт преимущество на спасброски ЛОВ.
11. **Бегство** — если все **герои** сбежали, бой для героя заканчивается `fled`, даже если союзные NPC остались
    (их судьба — нарратив мастера, этап 2). Записать в rules-adaptation.
12. **Nat 20 на спасброске от смерти** — по SRD: 1 HP, герой приходит в сознание и **действует в этот же ход**.
13. rules-adaptation: уточнить «нет боеспособных врагов → victory, если стоит хоть один герой или союзник;
    иначе умирающие продолжают спасброски (`hero_dying`)».
14. Мёртвый код в `zones.py` (`range_band_ft(None)`, `OUT_OF_FIELD_FT`) — удалить.
15. (T) шапка `tests/scenarios/test_criterion1.py` — убрать устаревшие «ПОДОБРАТЬ / файла нет».
16. `Participant.name` выводится в лог боя для безымянных монстров (вместо `ref`); при одинаковых именах —
    с номером («Воин-гоблин 2»).

### Тесты (T)
Обновить существующие под 12 (nat 20 — герой действует), 5, 6, 16 (лог), 4 (id `cast:bless:1:a,b`); добавить:
союзник убит + герой сбежал → `fled`; Topple → монстр встаёт в начале своего хода, перемещение 0, `prone` от `0_hp`
не снимается; сейв после атаки посреди хода → Savage не срабатывает второй раз (через диск/JSON); Bless на 3 цели
(+d4 к атаке и спасброску, повтор цели — отказ, > targets — отказ); Bless на спасбросок от смерти; Vex в свой ход и
провоцированной атакой; импровизация-преимущество работает на атаке в следующем ходу; группа последнего удара
(опасность сбрасывает, удар по лежащему обновляет); мультиатака босса (2 атаки за действие, детерминизм);
укрытие +2 к спасброску ЛОВ от Burning Hands из другой зоны; Dodge — преимущество на спасбросок ЛОВ;
все герои сбежали при живом союзнике → `fled`; имена монстров в логе с номерами.
После правок K перегенерирует golden и отпечаток (по правилам из шапок) — T проверяет, что тесты зелёные на новых артефактах.

## Итог: Приёмка этапа 1: решения проектировщика (2026-10-03) (бывш. docs/decisions/stage1-acceptance.md)

Источник: продуктовые решения партий 4–6, вынесенные проектировщику (независимый аудит 2 не состоялся — 4 обрыва
по таймауту API; список составлен оркестратором). Внесены в TZ.md (5.1, 7, 11).

| # | Решение |
|---|---|
| 1 | **Смерть героя не обрывает бой** — бой продолжается, пока стоят союзники; итог `hero_dead` при мёртвом герое (приоритет над любым итогом). |
| 2 | Враг не хочет убивать → упавший герой сразу стабилен, без спасбросков. |
| 3 | Бегство — только из exit-зоны, тратит действие. |
| 4 | Опасная зона: успех спасброска — 0 урона. |
| 5 | Вставание — всё перемещение хода. |
| 6 | Тактика врагов — как реализовано. |
| 7 | Число хранимых автосейвов — `config` (по умолчанию 3). |

### Спецификация правок
- K: `combat/end.update_outcome` — смерть героя не завершает бой; бой кончается по обычным условиям сторон;
  итоговый `outcome = "hero_dead"`, если хоть один герой из `engine.heroes` мёртв (приоритет над любым итогом);
  если мёртвый герой — единственный участник своей стороны, бой кончается сразу (как раньше).
  Мёртвый герой не ходит, не цель тактики. `rules-adaptation.md` — обновить строку.
- K: `RulesConfig.saves.autosave_keep: int = 3` (`[saves]` в defaults.toml); `save_auto(root, bundle, *, saved_at, cfg, keep=None)` —
  `cfg` обязателен (принцип «конфиг явно»), `keep` при передаче важнее `cfg`. Golden/сиды — перегенерировать, если поведение изменилось.
- T: тесты — герой + Guard против гоблинов: герой умер, Guard продолжает и побеждает → бой шёл после смерти, итог `hero_dead`;
  герой умер, Guard пал → `hero_dead`; герой один → бой кончается сразу; `autosave_keep` из cfg и явный keep;
  поправить комментарий в tests/scenarios/test_stage1_done.py (воин погибает при kill — сид находится; сценарии смерти/плена
  идут на слабом герое как в критерии 1); обновить тесты, ждавшие немедленного конца боя при смерти героя с живым союзником.
